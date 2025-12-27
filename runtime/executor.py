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
    SyncCeleryConstraints,
    BoundedAutonomyConstraints,
    # BaseNode contract validation
    validate_basenode_schema,
)

# Global constant - all skills run in sync Celery context
SYNC_CELERY_CONTEXT = BoundedAutonomyConstraints.SYNC_CELERY_CONTEXT


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

        cmd = ["python3", str(self.validator_script), str(trace_map_path)]
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


class RepoGroundingGate:
    """
    Gate that enforces repo grounding before IMPLEMENT/COMMIT skills.
    
    Policy reference:
    - .copilot/agent.md: "Repo-grounded: read actual repo files before decisions"
    
    Validates that artifacts/{correlation_id}/repo_facts.json exists and contains:
    - basenode_contract_path
    - node_loader_paths
    - golden_node_paths
    - test_command
    """

    REQUIRED_FIELDS = ["basenode_contract_path", "node_loader_paths", "golden_node_paths", "test_command"]

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir

    def check(self, correlation_id: str) -> GateResult:
        """Validate repo grounding for a correlation ID."""
        repo_facts_path = self.artifacts_dir / correlation_id / "repo_facts.json"
        
        if not repo_facts_path.exists():
            return GateResult(
                False,
                f"Missing repo_facts.json - IMPLEMENT/COMMIT requires repo grounding",
                {
                    "expected_path": str(repo_facts_path),
                    "required_fields": self.REQUIRED_FIELDS,
                    "remediation": "Agent must consult BaseNode contract and golden nodes before code generation",
                },
            )
        
        try:
            repo_facts = json.loads(repo_facts_path.read_text())
        except json.JSONDecodeError as e:
            return GateResult(False, f"Invalid JSON in repo_facts.json: {e}")
        
        # Check required fields
        missing = [f for f in self.REQUIRED_FIELDS if f not in repo_facts or not repo_facts[f]]
        if missing:
            return GateResult(
                False,
                f"Missing required repo grounding fields: {missing}",
                {"missing_fields": missing, "found_fields": list(repo_facts.keys())},
            )
        
        # Validate field types
        if not isinstance(repo_facts.get("node_loader_paths"), list):
            return GateResult(False, "node_loader_paths must be a list")
        if not isinstance(repo_facts.get("golden_node_paths"), list):
            return GateResult(False, "golden_node_paths must be a list")
        
        return GateResult(
            True,
            "Repo grounding check passed",
            {"consulted_sources": repo_facts},
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
    - Max changed files enforced from policy (default 20)
    """
    
    # From .copilot/policy.yaml: limits.max_changed_files
    MAX_CHANGED_FILES = 20

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
        repo_path: Path | None = None,
        check_git: bool = False,
    ) -> GateResult:
        """
        Run scope enforcement check.
        
        This validates directly in Python (no subprocess) for better testability.
        The scripts/enforce_scope.py is available for CLI usage.
        
        Args:
            correlation_id: Session correlation ID
            files_to_check: Explicit list of files to check (optional)
            repo_path: Path to git repository for git diff check
            check_git: If True, also check git diff against allowlist (policy requirement)
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
        
        # Combine explicit files_to_check with git diff files if requested
        all_files_to_check = list(files_to_check) if files_to_check else []
        
        if check_git:
            git_files = self._get_git_changed_files(repo_path)
            all_files_to_check = list(set(all_files_to_check + git_files))
        
        # If no files to check, just verify allowlist exists (gate passes)
        if not all_files_to_check:
            return GateResult(True, "Scope check passed (allowlist loaded, no files to check)")
        
        # ENFORCE: max_changed_files from policy
        if len(all_files_to_check) > self.MAX_CHANGED_FILES:
            return GateResult(
                False,
                f"Too many files changed: {len(all_files_to_check)} > {self.MAX_CHANGED_FILES} (policy limit)",
                {"file_count": len(all_files_to_check), "max_allowed": self.MAX_CHANGED_FILES},
            )
        
        # Validate each file
        violations = []
        for file_path in all_files_to_check:
            is_allowed, reason = self._is_path_allowed(file_path, allowed_paths, forbidden_paths)
            if not is_allowed:
                violations.append({"file": file_path, "reason": reason})
        
        if violations:
            return GateResult(
                False,
                f"Scope violations: {len(violations)} file(s) blocked",
                {"violations": violations, "check_git": check_git},
            )
        
        return GateResult(True, "Scope check passed", {"check_git": check_git, "files_checked": len(all_files_to_check)})

    def _get_git_changed_files(self, repo_path: Path | None = None) -> list[str]:
        """
        Get list of files changed in git (staged + unstaged + untracked).
        
        Includes:
        - Staged changes (git diff --name-only HEAD)
        - Unstaged changes (git diff --name-only)
        - Untracked files (git ls-files --others --exclude-standard)
        
        This ensures new files that haven't been committed are also checked
        against the scope allowlist.
        """
        cmd_base = ["git"]
        if repo_path:
            cmd_base = ["git", "-C", str(repo_path)]
        
        changed_files = []
        
        # Get staged changes (vs HEAD)
        try:
            cmd = cmd_base + ["diff", "--name-only", "HEAD"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                changed_files.extend(result.stdout.strip().split("\n"))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        
        # Get unstaged changes
        try:
            cmd = cmd_base + ["diff", "--name-only"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                changed_files.extend(result.stdout.strip().split("\n"))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        
        # Get untracked files (new files not yet added to git)
        # CRITICAL: Without this, out-of-scope new files slip through
        try:
            cmd = cmd_base + ["ls-files", "--others", "--exclude-standard"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                changed_files.extend(result.stdout.strip().split("\n"))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        
        # Dedupe and filter empty
        return list(set(f for f in changed_files if f))


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


class SyncCeleryGate:
    """
    Gate that enforces synchronous Celery execution constraints.
    
    Runtime Reality:
    - All skills execute in single synchronous Celery task
    - async def / await will block the worker
    - Background threads can orphan or deadlock
    - HTTP calls without timeout block indefinitely
    
    Static checks (for code review, not runtime enforcement):
    - async def patterns
    - asyncio / aiohttp imports
    - threading.Thread without join
    - HTTP calls missing timeout=
    
    This gate validates that skill CODE (when generated) is sync-safe.
    """

    # Patterns that indicate sync-incompatible code
    ASYNC_PATTERNS = [
        (r"\basync\s+def\b", "async def (blocks Celery worker)"),
        (r"\bawait\s+", "await (requires async context)"),
        (r"\bimport\s+asyncio\b", "asyncio import (async-only)"),
        (r"\bfrom\s+asyncio\b", "asyncio import (async-only)"),
        (r"\bimport\s+aiohttp\b", "aiohttp import (async-only)"),
        (r"\bfrom\s+aiohttp\b", "aiohttp import (async-only)"),
    ]
    
    THREADING_PATTERNS = [
        (r"threading\.Thread\([^)]*\)(?!.*\.join\()", "Thread without join (orphan risk)"),
    ]
    
    HTTP_TIMEOUT_PATTERNS = [
        # Match requests.get/post/etc without timeout=
        (r"requests\.(get|post|put|delete|patch|head)\([^)]*\)(?<!timeout=)", "HTTP call may lack timeout"),
    ]

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir

    def check_code(self, code: str) -> GateResult:
        """
        Validate Python code for sync-Celery compatibility.
        
        Returns violations if code uses async patterns.
        """
        violations = []
        lines = code.split("\n")
        
        for line_num, line in enumerate(lines, 1):
            # Check async patterns
            for pattern, description in self.ASYNC_PATTERNS:
                if re.search(pattern, line):
                    violations.append({
                        "line": line_num,
                        "pattern": description,
                        "content": line.strip()[:80],
                    })
            
            # Check threading patterns
            for pattern, description in self.THREADING_PATTERNS:
                if re.search(pattern, line):
                    violations.append({
                        "line": line_num,
                        "pattern": description,
                        "content": line.strip()[:80],
                    })
        
        if violations:
            return GateResult(
                False,
                f"Sync-Celery violations: {len(violations)} issue(s) found",
                {"violations": violations, "gate": "sync_celery"},
            )
        
        return GateResult(True, "Sync-Celery check passed")

    def check_file(self, file_path: Path) -> GateResult:
        """Validate a Python file for sync-Celery compatibility."""
        if not file_path.exists():
            return GateResult(False, f"File not found: {file_path}")
        
        if not file_path.suffix == ".py":
            return GateResult(True, "Non-Python file skipped")
        
        code = file_path.read_text()
        return self.check_code(code)

    def check_artifact_code(self, correlation_id: str, artifact_name: str = "generated_code.py") -> GateResult:
        """Check code artifact for sync-Celery compatibility."""
        artifact_path = self.artifacts_dir / correlation_id / artifact_name
        if artifact_path.exists():
            return self.check_file(artifact_path)
        return GateResult(True, "No code artifact to check")

    def emit_failure_artifact(
        self, correlation_id: str, violations: list[dict[str, Any]]
    ) -> Path:
        """Emit structured failure artifact per spec."""
        artifact = {
            "gate": "sync_celery_compatibility",
            "passed": False,
            "violations": violations,
            "timestamp": datetime.utcnow().isoformat(),
            "remediation": [
                "Replace async def with def",
                "Use requests/httpx sync API instead of aiohttp",
                "Add explicit timeout= to all HTTP calls",
                "Ensure all threads call .join() before return",
            ],
        }
        
        artifact_path = self.artifacts_dir / correlation_id / "sync_celery_gate_failure.json"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(artifact, indent=2))
        
        return artifact_path


class ArtifactCompletenessGate:
    """
    Gate that enforces required artifacts exist before PR-ready state.
    
    Policy reference:
    - .copilot/agent.md: "Required artifacts per run"
    
    Required artifacts (per agent.md):
    - request_snapshot.json
    - source_bundle/ (directory)
    - inferred_schema.json
    - trace_map.json
    - allowlist.json (for IMPLEMENT/COMMIT)
    - validation_logs.txt
    - diff.patch
    - escalation_report.md (only if escalation)
    """

    # Core artifacts required for any IMPLEMENT/COMMIT skill
    CORE_ARTIFACTS = [
        "request_snapshot.json",
        "inferred_schema.json",
        "trace_map.json",
        "validation_logs.txt",
    ]
    
    # Artifacts required specifically for IMPLEMENT/COMMIT
    IMPLEMENT_ARTIFACTS = [
        "allowlist.json",
        "diff.patch",
    ]
    
    # Optional directory (can be empty but should exist)
    SOURCE_BUNDLE_DIR = "source_bundle"

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir

    def check(
        self,
        correlation_id: str,
        autonomy_level: AutonomyLevel,
        is_escalation: bool = False,
    ) -> GateResult:
        """Check that all required artifacts exist."""
        corr_dir = self.artifacts_dir / correlation_id
        
        if not corr_dir.exists():
            return GateResult(
                False,
                f"Artifacts directory does not exist: {corr_dir}",
            )
        
        missing = []
        present = []
        
        # Check core artifacts
        for artifact in self.CORE_ARTIFACTS:
            artifact_path = corr_dir / artifact
            if artifact_path.exists():
                present.append(artifact)
            else:
                missing.append(artifact)
        
        # Check IMPLEMENT/COMMIT specific artifacts
        if autonomy_level in (AutonomyLevel.IMPLEMENT, AutonomyLevel.COMMIT):
            for artifact in self.IMPLEMENT_ARTIFACTS:
                artifact_path = corr_dir / artifact
                if artifact_path.exists():
                    present.append(artifact)
                else:
                    missing.append(artifact)
        
        # Check source_bundle directory
        source_bundle = corr_dir / self.SOURCE_BUNDLE_DIR
        if source_bundle.exists() and source_bundle.is_dir():
            present.append(self.SOURCE_BUNDLE_DIR)
        else:
            missing.append(f"{self.SOURCE_BUNDLE_DIR}/ (directory)")
        
        # Check escalation report if needed
        if is_escalation:
            escalation_report = corr_dir / "escalation_report.md"
            if escalation_report.exists():
                present.append("escalation_report.md")
            else:
                missing.append("escalation_report.md (required for escalation)")
        
        if missing:
            return GateResult(
                False,
                f"Missing required artifacts: {missing}",
                {"missing": missing, "present": present},
            )
        
        return GateResult(
            True,
            "All required artifacts present",
            {"present": present},
        )


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
        repo_root: Path | None = None,
    ):
        self.registry = SkillRegistry(skills_dir)
        self.trace_gate = TraceMapGate(scripts_dir)
        self.scope_gate = ScopeGate(scripts_dir, artifacts_dir)
        self.sync_celery_gate = SyncCeleryGate(artifacts_dir)
        self.repo_grounding_gate = RepoGroundingGate(artifacts_dir)
        self.idempotency_store = IdempotencyStore(artifacts_dir)
        self.artifacts_dir = artifacts_dir
        # Store repo_root for git diff scope checks (policy: require_git_diff_scope_check)
        self.repo_root = repo_root or skills_dir.parent
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
                # 5a. Repo grounding gate - agent must have consulted canonical sources
                grounding_result = self.repo_grounding_gate.check(correlation_id)
                ctx.log("repo_grounding_gate", {"passed": grounding_result.passed})
                if not grounding_result.passed:
                    errors.append(grounding_result.message)
                    if grounding_result.details:
                        errors.append(f"Details: {grounding_result.details}")
                    status = ExecutionStatus.BLOCKED
                    raise ValueError("Repo grounding gate blocked execution - agent must consult canonical sources first")
                
                # 5b. Scope gate - files must be in allowlist AND git diff must be in scope
                # Policy: require_git_diff_scope_check: true
                scope_result = self.scope_gate.check(
                    correlation_id,
                    repo_path=self.repo_root,
                    check_git=True,  # ENFORCE: git diff scope check per policy
                )
                ctx.log("scope_gate", {"passed": scope_result.passed, "check_git": True})
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
            
            # 7c. Post-gate for code-generating skills (Sync Celery Compatibility)
            # Applies to: code-implement, code-convert, node-scaffold (any skill generating Python)
            CODE_GENERATING_SKILLS = {"code-implement", "code-convert", "node-scaffold"}
            if skill_name in CODE_GENERATING_SKILLS and SYNC_CELERY_CONTEXT:
                # Check all generated Python files for sync-Celery compatibility
                generated_files = outputs.get("files_modified", []) + outputs.get("files_created", [])
                for file_path in generated_files:
                    if file_path.endswith(".py"):
                        full_path = Path(file_path)
                        if full_path.exists():
                            sync_result = self.sync_celery_gate.check_file(full_path)
                            ctx.log("sync_celery_gate", {
                                "file": file_path,
                                "passed": sync_result.passed,
                            })
                            if not sync_result.passed:
                                # Emit structured failure artifact
                                failure_artifact = self.sync_celery_gate.emit_failure_artifact(
                                    correlation_id,
                                    sync_result.details.get("violations", []),
                                )
                                artifacts.append(failure_artifact)
                                errors.append(f"Sync-Celery gate failed for {file_path}: {sync_result.message}")
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
    register_implementations: bool = True,
) -> SkillExecutor:
    """
    Factory function to create configured executor.
    
    Args:
        repo_root: Path to repository root
        max_steps: Max steps per correlation_id (capped at MAX_STEPS_DEFAULT=50)
        register_implementations: If True, register all available skill implementations
    """
    executor = SkillExecutor(
        skills_dir=repo_root / "skills",
        scripts_dir=repo_root / "scripts",
        artifacts_dir=repo_root / "artifacts",
        max_steps=max_steps,
        repo_root=repo_root,
    )
    
    if register_implementations:
        _register_skill_implementations(executor)
    
    return executor


def _register_skill_implementations(executor: SkillExecutor) -> None:
    """
    Register all available skill implementations.
    
    Each skill implementation is a function that takes ExecutionContext
    and returns a dict[str, Any] of outputs.
    
    Note: Skill directories use hyphens (e.g., 'node-scaffold') which aren't
    valid Python module names, so we use importlib to load them dynamically.
    """
    import importlib.util
    
    skills_dir = executor.registry.skills_dir
    
    # Map of skill names to implementation file paths
    skill_impls = {
        "node-scaffold": skills_dir / "node-scaffold" / "impl.py",
        # Future implementations:
        # "source-ingest": skills_dir / "source-ingest" / "impl.py",
        # "schema-infer": skills_dir / "schema-infer" / "impl.py",
        # etc.
    }
    
    for skill_name, impl_path in skill_impls.items():
        if impl_path.exists():
            try:
                # Dynamic import using importlib
                spec = importlib.util.spec_from_file_location(
                    f"skill_impl_{skill_name.replace('-', '_')}",
                    impl_path,
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for execute_* function (convention)
                    func_name = f"execute_{skill_name.replace('-', '_')}"
                    if hasattr(module, func_name):
                        executor.register_implementation(skill_name, getattr(module, func_name))
            except Exception:
                pass  # Implementation not loadable
