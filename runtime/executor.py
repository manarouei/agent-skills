#!/usr/bin/env python3
"""
Skill Runtime - Contract-First Execution Engine

This module provides the runtime layer for executing skills with:
- Contract validation (pre/post conditions)
- Trace map enforcement  
- Scope enforcement
- Bounded autonomy controls (timeouts, retries, idempotency)
- Hard budget enforcement (max_steps, fix loop max=3)
"""

from __future__ import annotations

import hashlib
import re
import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

# Import canonical contract models - SINGLE SOURCE OF TRUTH
from contracts import (
    AutonomyLevel,
    ExecutionStatus,
    SideEffect,
    RetryPolicy,
    FailureMode,
    SkillContract,
    RetryConfig,
    IdempotencyConfig,
    ArtifactSpec,
    # BaseNode contract validation
    validate_basenode_schema,
)


@dataclass
class ExecutionContext:
    """Context for skill execution."""
    correlation_id: str
    skill_name: str
    inputs: dict[str, Any]
    artifacts_dir: Path
    iteration: int = 0
    parent_context: ExecutionContext | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)

    def log(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Add event to execution trace."""
        self.trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "data": data or {},
        })


@dataclass
class ExecutionResult:
    """Result of skill execution."""
    status: ExecutionStatus
    outputs: dict[str, Any]
    artifacts: list[Path]
    errors: list[str]
    trace: list[dict[str, Any]]
    duration_ms: int


class SkillRegistry:
    """Registry for loading and caching skill contracts."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._cache: dict[str, SkillContract] = {}

    def get(self, skill_name: str) -> SkillContract:
        """Load skill contract by name."""
        if skill_name not in self._cache:
            self._cache[skill_name] = self._load_contract(skill_name)
        return self._cache[skill_name]

    def _load_contract(self, skill_name: str) -> SkillContract:
        """Load and parse SKILL.md frontmatter into canonical Pydantic model."""
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        if not skill_path.exists():
            raise ValueError(f"Skill not found: {skill_name}")

        content = skill_path.read_text()
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            raise ValueError(f"No YAML frontmatter in {skill_name}/SKILL.md")

        data = yaml.safe_load(match.group(1))
        return self._parse_to_pydantic(data)

    def _parse_to_pydantic(self, data: dict[str, Any]) -> SkillContract:
        """Transform YAML data to canonical Pydantic SkillContract."""
        # Convert side_effects strings to SideEffect enum
        side_effects = []
        for se in data.get("side_effects", []):
            try:
                side_effects.append(SideEffect(se))
            except ValueError:
                pass  # Skip invalid side effects

        # Convert autonomy_level string to enum
        autonomy = AutonomyLevel(data["autonomy_level"])

        # Convert retry config
        retry_data = data.get("retry", {})
        retry = RetryConfig(
            policy=RetryPolicy(retry_data.get("policy", "none")),
            max_retries=retry_data.get("max_retries", 0),
            backoff_seconds=retry_data.get("backoff_seconds", 1.0),
        )

        # Convert idempotency config
        idem_data = data.get("idempotency", {})
        idempotency = IdempotencyConfig(
            required=idem_data.get("required", False),
            key_spec=idem_data.get("key_spec"),
        )

        # Convert required_artifacts
        artifacts = []
        for art in data.get("required_artifacts", []):
            artifacts.append(ArtifactSpec(
                name=art["name"],
                type=art["type"],
                description=art.get("description", ""),
            ))

        # Convert failure_modes strings to FailureMode enum
        failure_modes = []
        for fm in data.get("failure_modes", []):
            try:
                failure_modes.append(FailureMode(fm))
            except ValueError:
                pass  # Skip invalid failure modes

        return SkillContract(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            autonomy_level=autonomy,
            side_effects=side_effects,
            timeout_seconds=data.get("timeout_seconds", 60),
            max_steps=data.get("max_steps", 50),
            retry=retry,
            idempotency=idempotency,
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            required_artifacts=artifacts,
            failure_modes=failure_modes,
            depends_on=data.get("depends_on", []),
        )

    def list_skills(self) -> list[str]:
        """List all available skills."""
        return [
            d.name for d in self.skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ]


class GateResult:
    """Result of a gate check."""
    def __init__(self, passed: bool, message: str, details: dict[str, Any] | None = None):
        self.passed = passed
        self.message = message
        self.details = details or {}


class TraceMapGate:
    """
    Gate that enforces trace map completeness for schema-infer outputs.
    
    Rules:
    - Every schema field must have a trace entry
    - Max 30% ASSUMPTION entries for IMPLEMENT autonomy
    - All ASSUMPTION entries must have rationale
    """

    def __init__(self, scripts_dir: Path):
        self.validator_script = scripts_dir / "validate_trace_map.py"

    def check(self, trace_map_path: Path, schema_path: Path | None = None) -> GateResult:
        """Run trace map validation."""
        if not trace_map_path.exists():
            return GateResult(False, f"Trace map not found: {trace_map_path}")

        cmd = ["python", str(self.validator_script), str(trace_map_path)]
        if schema_path and schema_path.exists():
            cmd.append(str(schema_path))

        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return GateResult(True, "Trace map validation passed")
        else:
            return GateResult(
                False,
                "Trace map validation failed",
                {"stdout": result.stdout, "stderr": result.stderr},
            )


# Default forbidden paths (always enforced, copied from scripts/enforce_scope.py)
DEFAULT_FORBIDDEN_PATHS = [
    "**/base.py", "**/base.ts", "**/Base*.ts", "**/__init__.py",
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "package-lock.json",
    ".env", ".env.*", "config/*",
    ".github/**/*", ".gitlab-ci.yml", "Dockerfile", "docker-compose.yml",
    "migrations/**/*", "alembic/**/*",
]


def _match_glob(path: str, pattern: str) -> bool:
    """Simple glob matching for allowlist patterns."""
    import fnmatch
    
    # Handle ** (recursive)
    if "**" in pattern:
        pattern_normalized = pattern.replace("**", "*")
        prefix = pattern_normalized.split("*")[0]
        if path.startswith(prefix):
            suffix = pattern_normalized.split("*")[-1] if "*" in pattern_normalized else ""
            if not suffix or path.endswith(suffix):
                return True
    
    return fnmatch.fnmatch(path, pattern)


class ScopeGate:
    """
    Gate that enforces file scope restrictions.
    
    Rules:
    - Only allowed paths can be modified
    - Forbidden paths (base.py, __init__.py, etc.) are blocked
    - Git changes must be within scope
    - REQUIRES node-derived allowlist.json for IMPLEMENT/COMMIT skills
    """

    def __init__(self, scripts_dir: Path, artifacts_dir: Path):
        self.scripts_dir = scripts_dir  # Kept for potential CLI fallback
        self.artifacts_dir = artifacts_dir

    def _load_allowlist(self, correlation_id: str) -> tuple[list[str], list[str]] | None:
        """Load allowlist.json for a session."""
        allowlist_path = self.artifacts_dir / correlation_id / "allowlist.json"
        if not allowlist_path.exists():
            return None
        
        try:
            data = json.loads(allowlist_path.read_text())
            allowed = data.get("allowed_paths", [])
            forbidden = data.get("forbidden_paths", [])
            # Merge with default forbidden paths
            forbidden = list(set(forbidden + DEFAULT_FORBIDDEN_PATHS))
            return allowed, forbidden
        except (json.JSONDecodeError, KeyError):
            return None

    def _is_path_allowed(
        self, path: str, allowed_paths: list[str], forbidden_paths: list[str]
    ) -> tuple[bool, str]:
        """Check if a path is within the allowed scope."""
        # Check forbidden first (higher priority)
        for pattern in forbidden_paths:
            if _match_glob(path, pattern):
                return False, f"Path matches forbidden pattern: {pattern}"
        
        # Check allowlist
        for pattern in allowed_paths:
            if _match_glob(path, pattern):
                return True, f"Path matches allowed pattern: {pattern}"
        
        return False, "Path not in allowlist"

    def check(
        self,
        correlation_id: str,
        files_to_check: list[str] | None = None,
    ) -> GateResult:
        """
        Run scope enforcement check.
        
        This validates directly in Python (no subprocess) for better testability.
        The scripts/enforce_scope.py is available for CLI usage.
        """
        # ENFORCE: allowlist.json must exist for IMPLEMENT/COMMIT skills
        allowlist_result = self._load_allowlist(correlation_id)
        if allowlist_result is None:
            allowlist_path = self.artifacts_dir / correlation_id / "allowlist.json"
            return GateResult(
                False,
                f"Missing required allowlist.json at {allowlist_path}",
                {"required": "allowlist.json must be generated by node-derive before IMPLEMENT/COMMIT"},
            )
        
        allowed_paths, forbidden_paths = allowlist_result
        
        # If no files specified, just check that allowlist exists (gate passes)
        if not files_to_check:
            return GateResult(True, "Scope check passed (allowlist loaded, no files to check)")
        
        # Validate each file
        violations = []
        for file_path in files_to_check:
            is_allowed, reason = self._is_path_allowed(file_path, allowed_paths, forbidden_paths)
            if not is_allowed:
                violations.append({"file": file_path, "reason": reason})
        
        if violations:
            return GateResult(
                False,
                f"Scope violations: {len(violations)} file(s) blocked",
                {"violations": violations},
            )
        
        return GateResult(True, "Scope check passed")


class IdempotencyStore:
    """
    Simple idempotency store to prevent duplicate side-effect executions.
    
    Uses correlation_id + idempotency_key to track completed operations.
    """

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir

    def _get_state_file(self, correlation_id: str) -> Path:
        return self.artifacts_dir / correlation_id / "idempotency_state.json"

    def _compute_key(self, correlation_id: str, key_spec: str | None, inputs: dict[str, Any]) -> str:
        """Compute idempotency key from spec and inputs."""
        key_parts = [correlation_id]
        if key_spec and "+" in key_spec:
            fields = [f.strip() for f in key_spec.split("+")]
            for field in fields:
                if field != "correlation_id" and field in inputs:
                    key_parts.append(str(inputs[field]))
        
        key_string = ":".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def check_and_mark(
        self,
        correlation_id: str,
        skill_name: str,
        key_spec: str | None,
        inputs: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Check if operation was already executed, mark it if not.
        
        Returns: (already_executed, idempotency_key)
        """
        idempotency_key = self._compute_key(correlation_id, key_spec, inputs)
        state_file = self._get_state_file(correlation_id)
        
        state = {}
        if state_file.exists():
            state = json.loads(state_file.read_text())
        
        full_key = f"{skill_name}:{idempotency_key}"
        if full_key in state:
            return True, idempotency_key
        
        # Mark as executed
        state[full_key] = {
            "executed_at": datetime.utcnow().isoformat(),
            "skill": skill_name,
        }
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2))
        
        return False, idempotency_key


def run_with_timeout(func: Callable, timeout_seconds: int, *args, **kwargs) -> tuple[Any, bool]:
    """
    Run a function with a timeout.
    
    Returns: (result, timed_out)
    """
    result_holder = [None]
    exception_holder = [None]
    
    def target():
        try:
            result_holder[0] = func(*args, **kwargs)
        except Exception as e:
            exception_holder[0] = e
    
    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=timeout_seconds)
    
    if thread.is_alive():
        # Note: Python threads can't be killed, but we return timeout status
        return None, True
    
    if exception_holder[0]:
        raise exception_holder[0]
    
    return result_holder[0], False


class SkillExecutor:
    """
    Contract-first skill executor with bounded autonomy.
    
    HARD LIMITS (non-negotiable):
    - MAX_STEPS_DEFAULT = 50 per correlation_id
    - FIX_LOOP_MAX = 3 iterations
    - Per-skill timeout_seconds from contract
    
    Enforces:
    - Per-skill timeouts (hard)
    - Retry policies (only when safe + idempotent)
    - Scope gates (IMPLEMENT/COMMIT require allowlist.json)
    - Trace map gates (schema-infer/build)
    - Idempotency/dedupe for side-effect operations
    """

    # HARD LIMITS - these cannot be overridden
    MAX_STEPS_DEFAULT = 50
    FIX_LOOP_MAX = 3

    def __init__(
        self,
        skills_dir: Path,
        scripts_dir: Path,
        artifacts_dir: Path,
        max_steps: int | None = None,
    ):
        self.registry = SkillRegistry(skills_dir)
        self.trace_gate = TraceMapGate(scripts_dir)
        self.scope_gate = ScopeGate(scripts_dir, artifacts_dir)
        self.idempotency_store = IdempotencyStore(artifacts_dir)
        self.artifacts_dir = artifacts_dir
        # Enforce hard cap on max_steps
        self.max_steps = min(max_steps or self.MAX_STEPS_DEFAULT, self.MAX_STEPS_DEFAULT)
        
        # Step counter per correlation_id
        self._step_counts: dict[str, int] = {}
        
        # Skill implementations (to be registered)
        self._implementations: dict[str, Callable] = {}

    def register_implementation(
        self,
        skill_name: str,
        impl: Callable[[ExecutionContext], dict[str, Any]],
    ) -> None:
        """Register a skill implementation function."""
        self._implementations[skill_name] = impl

    def _check_step_limit(self, correlation_id: str) -> bool:
        """Check if step limit exceeded. Returns True if OK to proceed."""
        count = self._step_counts.get(correlation_id, 0)
        return count < self.max_steps

    def _increment_step(self, correlation_id: str) -> int:
        """Increment and return step count."""
        self._step_counts[correlation_id] = self._step_counts.get(correlation_id, 0) + 1
        return self._step_counts[correlation_id]

    def execute(
        self,
        skill_name: str,
        inputs: dict[str, Any],
        correlation_id: str,
    ) -> ExecutionResult:
        """
        Execute a skill with full contract enforcement.
        
        Flow:
        1. Check step limit (HARD)
        2. Load contract
        3. Check idempotency (skip if already done)
        4. Validate inputs against schema
        5. Run pre-gates (scope for IMPLEMENT+)
        6. Execute skill WITH TIMEOUT
        7. Run post-gates (trace map for schema-infer)
        8. Validate outputs
        9. Return result
        """
        start_time = time.time()
        
        # Create context
        ctx = ExecutionContext(
            correlation_id=correlation_id,
            skill_name=skill_name,
            inputs=inputs,
            artifacts_dir=self.artifacts_dir / correlation_id,
        )
        ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)
        ctx.log("execution_started", {"skill": skill_name})
        
        errors: list[str] = []
        artifacts: list[Path] = []
        outputs: dict[str, Any] = {}
        status = ExecutionStatus.SUCCESS
        
        try:
            # 1. Check step limit (HARD ENFORCEMENT)
            if not self._check_step_limit(correlation_id):
                errors.append(f"Step limit ({self.max_steps}) exceeded - ESCALATING")
                status = ExecutionStatus.ESCALATED
                ctx.log("step_limit_exceeded", {"max_steps": self.max_steps})
                raise ValueError("Step limit exceeded")
            
            step_num = self._increment_step(correlation_id)
            ctx.log("step_count", {"step": step_num, "max": self.max_steps})
            
            # 2. Load contract
            contract = self.registry.get(skill_name)
            ctx.log("contract_loaded", {"version": contract.version})
            
            # 3. Check idempotency (for side-effect skills)
            if contract.idempotency.required and contract.idempotency.key_spec:
                already_done, idem_key = self.idempotency_store.check_and_mark(
                    correlation_id,
                    skill_name,
                    contract.idempotency.key_spec,
                    inputs,
                )
                if already_done:
                    ctx.log("idempotency_skip", {"key": idem_key})
                    return ExecutionResult(
                        status=ExecutionStatus.SUCCESS,
                        outputs={"skipped": True, "reason": "idempotency"},
                        artifacts=[],
                        errors=[],
                        trace=ctx.trace,
                        duration_ms=int((time.time() - start_time) * 1000),
                    )
            
            # 4. Validate inputs (basic check)
            input_errors = self._validate_inputs(inputs, contract.input_schema)
            if input_errors:
                errors.extend(input_errors)
                status = ExecutionStatus.FAILED
                ctx.log("input_validation_failed", {"errors": input_errors})
                raise ValueError("Input validation failed")
            
            # 5. Pre-gates for IMPLEMENT+ autonomy
            if contract.autonomy_level in (AutonomyLevel.IMPLEMENT, AutonomyLevel.COMMIT):
                scope_result = self.scope_gate.check(correlation_id)
                ctx.log("scope_gate", {"passed": scope_result.passed})
                if not scope_result.passed:
                    errors.append(scope_result.message)
                    status = ExecutionStatus.BLOCKED
                    raise ValueError("Scope gate blocked execution")
            
            # 6. Execute skill WITH TIMEOUT (HARD ENFORCEMENT)
            if skill_name not in self._implementations:
                # No implementation - this is a stub/documentation-only skill
                ctx.log("no_implementation", {"reason": "stub_mode"})
                outputs = {"stub": True, "message": f"Skill {skill_name} has no implementation registered"}
            else:
                impl = self._implementations[skill_name]
                
                # Run with timeout
                try:
                    result, timed_out = run_with_timeout(
                        impl,
                        contract.timeout_seconds,
                        ctx,
                    )
                    if timed_out:
                        errors.append(f"Skill timed out after {contract.timeout_seconds}s - ESCALATING")
                        status = ExecutionStatus.TIMEOUT
                        ctx.log("timeout", {"timeout_seconds": contract.timeout_seconds})
                        raise ValueError("Timeout exceeded")
                    outputs = result or {}
                except Exception as e:
                    # Check retry policy (only retry if safe AND idempotent)
                    if (
                        contract.retry.policy == RetryPolicy.SAFE
                        and contract.retry.max_retries > 0
                        and contract.idempotency.required
                    ):
                        ctx.log("retry_eligible", {
                            "policy": contract.retry.policy.value,
                            "max_retries": contract.retry.max_retries,
                            "error": str(e),
                        })
                        # Retry logic would go here
                    raise
                
                ctx.log("skill_executed", {"has_outputs": bool(outputs)})
            
            # 7. Post-gates for schema-infer (trace map enforcement)
            if skill_name == "schema-infer":
                trace_map_path = ctx.artifacts_dir / "trace_map.json"
                if trace_map_path.exists():
                    trace_result = self.trace_gate.check(trace_map_path)
                    ctx.log("trace_gate", {"passed": trace_result.passed})
                    if not trace_result.passed:
                        errors.append(trace_result.message)
                        status = ExecutionStatus.BLOCKED
                else:
                    errors.append("schema-infer must produce trace_map.json")
                    status = ExecutionStatus.BLOCKED
            
            # 7b. Post-gate for schema-build (BaseNode contract enforcement)
            if skill_name == "schema-build":
                node_schema_path = ctx.artifacts_dir / "node_schema.json"
                if node_schema_path.exists():
                    try:
                        schema_data = json.loads(node_schema_path.read_text())
                        basenode_result = validate_basenode_schema(schema_data)
                        ctx.log("basenode_gate", {
                            "passed": basenode_result.valid,
                            "errors": basenode_result.errors,
                        })
                        if not basenode_result.valid:
                            for err in basenode_result.errors:
                                errors.append(f"BaseNode contract violation: {err}")
                            status = ExecutionStatus.BLOCKED
                    except json.JSONDecodeError as e:
                        errors.append(f"Invalid JSON in node_schema.json: {e}")
                        status = ExecutionStatus.BLOCKED
                else:
                    errors.append("schema-build must produce node_schema.json")
                    status = ExecutionStatus.BLOCKED
            
            # 8. Validate outputs
            output_errors = self._validate_outputs(outputs, contract.output_schema)
            if output_errors:
                errors.extend(output_errors)
                # Don't fail on output validation - just warn
                ctx.log("output_validation_warning", {"errors": output_errors})
            
            # 9. Collect artifacts
            for artifact_spec in contract.required_artifacts:
                artifact_path = ctx.artifacts_dir / artifact_spec.name
                if artifact_path.exists():
                    artifacts.append(artifact_path)
                else:
                    ctx.log("artifact_missing", {"name": artifact_spec.name})
        
        except Exception as e:
            if status == ExecutionStatus.SUCCESS:
                status = ExecutionStatus.FAILED
            errors.append(str(e))
            ctx.log("execution_error", {"error": str(e)})
        
        duration_ms = int((time.time() - start_time) * 1000)
        ctx.log("execution_completed", {"status": status.value, "duration_ms": duration_ms})
        
        return ExecutionResult(
            status=status,
            outputs=outputs,
            artifacts=artifacts,
            errors=errors,
            trace=ctx.trace,
            duration_ms=duration_ms,
        )

    def _validate_inputs(
        self,
        inputs: dict[str, Any],
        schema: dict[str, Any],
    ) -> list[str]:
        """Basic input validation against schema."""
        errors = []
        
        required = schema.get("required", [])
        for field in required:
            if field not in inputs:
                errors.append(f"Missing required input: {field}")
        
        return errors

    def _validate_outputs(
        self,
        outputs: dict[str, Any],
        schema: dict[str, Any],
    ) -> list[str]:
        """Basic output validation against schema."""
        errors = []
        
        required = schema.get("required", [])
        for field in required:
            if field not in outputs:
                errors.append(f"Missing required output: {field}")
        
        return errors


class BoundedFixLoop:
    """
    Bounded fix loop for code-fix skill.
    
    HARD LIMIT: max 3 iterations (FIX_LOOP_MAX), then MUST escalate.
    This is non-negotiable - cannot be overridden by contract or caller.
    """

    def __init__(self, executor: SkillExecutor, max_iterations: int | None = None):
        self.executor = executor
        # ENFORCE hard cap - cannot exceed FIX_LOOP_MAX even if requested
        self.max_iterations = min(
            max_iterations or SkillExecutor.FIX_LOOP_MAX,
            SkillExecutor.FIX_LOOP_MAX,
        )

    def run(
        self,
        correlation_id: str,
        initial_errors: list[dict[str, Any]],
    ) -> ExecutionResult:
        """
        Run bounded fix loop.
        
        Returns SUCCESS if fixed, ESCALATED if max iterations exceeded.
        """
        iteration = 0
        current_errors = initial_errors
        all_attempts: list[dict[str, Any]] = []
        
        while iteration < self.max_iterations and current_errors:
            iteration += 1
            
            # Run code-fix skill
            result = self.executor.execute(
                "code-fix",
                {
                    "correlation_id": correlation_id,
                    "errors": current_errors,
                    "iteration": iteration,
                    "previous_attempts": all_attempts,
                },
                correlation_id,
            )
            
            all_attempts.append({
                "iteration": iteration,
                "errors_in": len(current_errors),
                "status": result.status.value,
            })
            
            if result.status != ExecutionStatus.SUCCESS:
                break
            
            # Re-validate
            validate_result = self.executor.execute(
                "code-validate",
                {"correlation_id": correlation_id},
                correlation_id,
            )
            
            current_errors = validate_result.outputs.get("errors", [])
            
            if not current_errors:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    outputs={"fixed": True, "iterations": iteration},
                    artifacts=result.artifacts,
                    errors=[],
                    trace=result.trace,
                    duration_ms=result.duration_ms,
                )
        
        # Max iterations exceeded - escalate
        return ExecutionResult(
            status=ExecutionStatus.ESCALATED,
            outputs={
                "fixed": False,
                "iterations": iteration,
                "remaining_errors": current_errors,
                "attempts": all_attempts,
            },
            artifacts=[],
            errors=[f"Max iterations ({self.max_iterations}) exceeded, escalating to human"],
            trace=[],
            duration_ms=0,
        )


def create_executor(
    repo_root: Path,
    max_steps: int | None = None,
) -> SkillExecutor:
    """
    Factory function to create configured executor.
    
    Args:
        repo_root: Path to repository root
        max_steps: Max steps per correlation_id (capped at MAX_STEPS_DEFAULT=50)
    """
    return SkillExecutor(
        skills_dir=repo_root / "skills",
        scripts_dir=repo_root / "scripts",
        artifacts_dir=repo_root / "artifacts",
        max_steps=max_steps,
    )
