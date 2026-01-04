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
from typing import Any, Callable, Optional

import yaml

# Exception for cooperative deadline enforcement
class DeadlineExceeded(Exception):
    pass

# Optional: jsonschema for strict INPUT_REQUIRED payload validation
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    jsonschema = None  # type: ignore

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
    InteractionOutcomes,
    IntermediateState,
    InputFieldSchema,
    StatePersistenceLevel,
    # Skill execution mode (hybrid backbone)
    SkillExecutionMode,
    SKILL_EXECUTION_MODES,
    get_skill_execution_mode,
    # BaseNode contract validation
    validate_basenode_schema,
)

# Import KB for pattern retrieval (LEARNING LOOP)
from .kb import KnowledgeBase, KBValidationError

# Import learning loop for golden artifact and promotion candidate emission
from .learning_loop import (
    LearningLoopEmitter,
    GoldenArtifactPackage,
    PromotionCandidate,
    categorize_error,
    compute_source_hash,
)

# Import protocol types for native AgentResponse handling
from .protocol import (
    AgentResponse,
    AgentResponseMetadata,
    TaskState,
    task_state_to_execution_status_value,
)

# Global constant - all skills run in sync Celery context
SYNC_CELERY_CONTEXT = BoundedAutonomyConstraints.SYNC_CELERY_CONTEXT


@dataclass
class RuntimeConfig:
    """
    Runtime configuration for the skill execution engine.
    
    These settings control bounded autonomy behavior and can be adjusted
    per-deployment without code changes.
    
    SAFETY-CRITICAL DEFAULTS:
    - auto_merge_enabled: False (NEVER auto-merge by default)
    - require_human_review: True (human-in-the-loop for COMMIT)
    """
    
    # PR/Merge behavior (pr-prepare skill)
    auto_merge_enabled: bool = False  # NEVER True by default
    require_human_review: bool = True  # Always require review for COMMIT
    
    # Execution limits (hard caps from policy)
    max_steps: int = 50
    fix_loop_max: int = 3
    max_changed_files: int = 20
    
    # Timeouts
    default_timeout_seconds: int = 300
    
    # Agent capabilities limits
    max_turns_per_context: int = 8
    max_events_per_context: int = 100


# Global runtime config (can be overridden per-instance)
DEFAULT_RUNTIME_CONFIG = RuntimeConfig()


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
    # Cooperative deadline timestamp (monotonic seconds). None = no deadline set.
    _deadline_ts: Optional[float] = None

    def log(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Add event to execution trace."""
        self.trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "data": data or {},
        })

    def set_deadline(self, timeout_seconds: int) -> None:
        """Set a cooperative deadline (monotonic time in seconds).

        Skills should periodically call `check_deadline()` or `time_remaining()` to
        cooperatively abort long-running work. This is the preferred production
        pattern under sync-Celery constraints.
        """
        try:
            self._deadline_ts = time.monotonic() + float(timeout_seconds)
        except Exception:
            self._deadline_ts = None

    def time_remaining(self) -> float:
        """Return remaining seconds until deadline. Returns float('inf') if no deadline."""
        if not self._deadline_ts:
            return float('inf')
        return max(0.0, self._deadline_ts - time.monotonic())

    def check_deadline(self) -> None:
        """Raise DeadlineExceeded if cooperative deadline has passed."""
        if self._deadline_ts is None:
            return
        if time.monotonic() > self._deadline_ts:
            raise DeadlineExceeded(f"Execution deadline exceeded for {self.skill_name}")


@dataclass
class ExecutionResult:
    """Result of skill execution.
    
    For agent-style skills returning AgentResponse, the agent_metadata field
    carries the full response metadata including resume tokens, input requests,
    and delegation information. This enables callers to handle intermediate
    states (INPUT_REQUIRED, PAUSED, DELEGATING) appropriately.
    
    IMPORTANT: Callers MUST check is_terminal before treating this as complete.
    A status of SUCCESS with is_terminal=False means the skill needs more input.
    """
    status: ExecutionStatus
    outputs: dict[str, Any]
    artifacts: list[Path]
    errors: list[str]
    trace: list[dict[str, Any]]
    duration_ms: int
    # Agent-style metadata (None for legacy tool-style returns)
    agent_metadata: Optional[AgentResponseMetadata] = None
    # EXPLICIT terminal flag - callers MUST check this
    # True = skill is done (success or failure), False = needs more input/delegation
    is_terminal: bool = True
    # Semantic agent state (None for tool-style, or "completed"/"input_required"/etc for agent-style)
    agent_state: Optional[str] = None


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
        return self._parse_to_pydantic(data, skill_name)

    def _parse_to_pydantic(self, data: dict[str, Any], skill_name: str = "unknown") -> SkillContract:
        """
        Transform YAML data to canonical Pydantic SkillContract.
        
        CRITICAL: This must parse ALL contract fields. No silent dropping.
        Unknown keys in SKILL.md cause validation error (contract truth principle).
        """
        # Define known top-level keys (to detect unknown keys)
        KNOWN_KEYS = {
            "name", "version", "description",
            "autonomy_level", "side_effects", "timeout_seconds",
            "retry", "idempotency", "max_fix_iterations",
            "input_schema", "output_schema",
            "required_artifacts", "failure_modes", "depends_on",
            "sync_celery", "sync_celery_constraints",  # Both forms accepted
            "interaction_outcomes",
        }
        
        # Check for unknown keys (contract truth enforcement)
        unknown_keys = set(data.keys()) - KNOWN_KEYS
        if unknown_keys:
            raise ValueError(
                f"Unknown keys in {skill_name}/SKILL.md frontmatter: {unknown_keys}. "
                f"Add to SkillContract model or remove from SKILL.md."
            )
        
        # Convert side_effects strings to SideEffect enum
        side_effects = []
        for se in data.get("side_effects", []):
            try:
                side_effects.append(SideEffect(se))
            except ValueError:
                raise ValueError(f"Invalid side_effect '{se}' in {skill_name}/SKILL.md")

        # Convert autonomy_level string to enum
        try:
            autonomy = AutonomyLevel(data["autonomy_level"])
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid/missing autonomy_level in {skill_name}/SKILL.md: {e}")

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
                raise ValueError(f"Invalid failure_mode '{fm}' in {skill_name}/SKILL.md")

        # Convert sync_celery_constraints (supports both 'sync_celery' and 'sync_celery_constraints' keys)
        sync_celery_constraints = None
        sc_data = data.get("sync_celery") or data.get("sync_celery_constraints")
        if sc_data:
            sync_celery_constraints = SyncCeleryConstraints(
                requires_sync_execution=sc_data.get("requires_sync_execution", True),
                forbids_async_dependencies=sc_data.get("forbids_async_dependencies", True),
                requires_timeouts_on_external_calls=sc_data.get("requires_timeouts_on_external_calls", True),
                forbids_background_tasks=sc_data.get("forbids_background_tasks", True),
            )

        # Convert interaction_outcomes (agent capability extension)
        interaction_outcomes = None
        io_data = data.get("interaction_outcomes")
        if io_data:
            # Parse allowed_intermediate_states
            allowed_states = []
            for state in io_data.get("allowed_intermediate_states", []):
                try:
                    allowed_states.append(IntermediateState(state))
                except ValueError:
                    pass  # Skip invalid states
            
            # Parse input_request_schema
            input_fields = []
            for field_data in io_data.get("input_request_schema", []):
                input_fields.append(InputFieldSchema(
                    name=field_data["name"],
                    type=field_data.get("type", "string"),
                    description=field_data.get("description", ""),
                    required=field_data.get("required", False),
                ))
            
            # Parse state_persistence level
            persistence_level = StatePersistenceLevel.FACTS_ONLY  # Default
            if "state_persistence" in io_data:
                try:
                    persistence_level = StatePersistenceLevel(io_data["state_persistence"])
                except ValueError:
                    pass
            
            interaction_outcomes = InteractionOutcomes(
                allowed_intermediate_states=allowed_states,
                max_turns=io_data.get("max_turns", 5),
                supports_resume=io_data.get("supports_resume", True),
                state_persistence=persistence_level,
                input_request_schema=input_fields if input_fields else None,
                input_request_jsonschema=io_data.get("input_request_jsonschema"),
            )

        return SkillContract(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            autonomy_level=autonomy,
            side_effects=side_effects,
            timeout_seconds=data.get("timeout_seconds", 60),
            retry=retry,
            idempotency=idempotency,
            max_fix_iterations=data.get("max_fix_iterations", 3),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            required_artifacts=artifacts,
            failure_modes=failure_modes,
            depends_on=data.get("depends_on", []),
            sync_celery_constraints=sync_celery_constraints,
            interaction_outcomes=interaction_outcomes,
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
        
        DEPRECATED for multi-turn skills: Use check_only() + mark_completed() instead.
        This method marks immediately, which breaks pause/resume.
        
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

    def check_only(
        self,
        correlation_id: str,
        skill_name: str,
        key_spec: str | None,
        inputs: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Check if operation was already TERMINALLY completed (not just started).
        Does NOT mark - use mark_completed() after terminal completion.
        
        For multi-turn skills: call this before execution, then mark_completed()
        only when the skill returns a terminal state.
        
        Returns: (already_completed, idempotency_key)
        """
        idempotency_key = self._compute_key(correlation_id, key_spec, inputs)
        state_file = self._get_state_file(correlation_id)
        
        state = {}
        if state_file.exists():
            state = json.loads(state_file.read_text())
        
        full_key = f"{skill_name}:{idempotency_key}"
        return full_key in state, idempotency_key

    def mark_completed(
        self,
        correlation_id: str,
        skill_name: str,
        idempotency_key: str,
    ) -> None:
        """
        Mark an operation as terminally completed.
        
        Call this ONLY when skill returns a terminal state (COMPLETED/FAILED).
        Do NOT call for intermediate states (INPUT_REQUIRED/PAUSED).
        
        Args:
            correlation_id: The correlation ID
            skill_name: Name of the skill
            idempotency_key: The key returned from check_only()
        """
        state_file = self._get_state_file(correlation_id)
        
        state = {}
        if state_file.exists():
            state = json.loads(state_file.read_text())
        
        full_key = f"{skill_name}:{idempotency_key}"
        state[full_key] = {
            "completed_at": datetime.utcnow().isoformat(),
            "skill": skill_name,
        }
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2))


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


class AdvisorOutputValidator:
    """
    Validator for AI/LLM advisor outputs.
    
    HYBRID BACKBONE PRINCIPLE:
    Advisor outputs must be validated before they can trigger any side effects.
    This ensures AI reasoning is bounded and auditable.
    
    Rules:
    1. Advisor outputs MUST be JSON/Pydantic-serializable
    2. Code outputs MUST pass sync-celery compatibility check
    3. Schema outputs MUST have evidence in trace_map
    4. Patch outputs MUST be within allowlist scope
    5. Advisor NEVER triggers side effects directly - orchestrator validates first
    
    This validator is used by ADVISOR_ONLY and HYBRID skills.
    """
    
    def __init__(self, artifacts_dir: Path, scripts_dir: Path):
        self.artifacts_dir = artifacts_dir
        self.sync_celery_gate = SyncCeleryGate(artifacts_dir)
        self.scripts_dir = scripts_dir
    
    def validate_code_output(
        self,
        code: str,
        correlation_id: str,
        file_path: str | None = None,
    ) -> GateResult:
        """
        Validate code generated by advisor.
        
        Checks:
        - Sync-celery compatibility (no async, no background tasks)
        - Basic syntax validity (Python)
        """
        # Sync-celery check
        sync_result = self.sync_celery_gate.check_code(code)
        if not sync_result.passed:
            return GateResult(
                False,
                f"Advisor code output failed sync-celery validation: {sync_result.message}",
                {"violations": sync_result.details.get("violations", []), "file": file_path},
            )
        
        # Basic Python syntax check
        try:
            compile(code, file_path or "<advisor_output>", "exec")
        except SyntaxError as e:
            return GateResult(
                False,
                f"Advisor code output has syntax error: {e}",
                {"line": e.lineno, "offset": e.offset, "text": e.text},
            )
        
        return GateResult(True, "Advisor code output validated")
    
    def validate_schema_output(
        self,
        schema: dict[str, Any],
        trace_map: dict[str, Any] | None,
        correlation_id: str,
    ) -> GateResult:
        """
        Validate schema extracted by advisor.
        
        Checks:
        - Schema is well-formed
        - If trace_map provided, check evidence coverage
        - Check assumption ratio (<= 30%)
        """
        # Basic schema structure check
        if not isinstance(schema, dict):
            return GateResult(False, "Schema must be a dictionary")
        
        if trace_map is not None:
            # Check trace_map structure
            if not isinstance(trace_map.get("trace_entries"), list):
                return GateResult(False, "trace_map.trace_entries must be a list")
            
            entries = trace_map.get("trace_entries", [])
            if entries:
                assumptions = sum(1 for e in entries if e.get("source") == "ASSUMPTION")
                ratio = assumptions / len(entries)
                if ratio > 0.30:
                    return GateResult(
                        False,
                        f"Too many assumptions: {ratio:.1%} > 30% allowed",
                        {"assumption_count": assumptions, "total": len(entries)},
                    )
        
        return GateResult(True, "Advisor schema output validated")
    
    def validate_patch_output(
        self,
        files_to_modify: list[str],
        allowed_patterns: list[str],
        forbidden_patterns: list[str],
    ) -> GateResult:
        """
        Validate patch/diff output from advisor is within scope.
        
        Advisor must not propose changes outside allowlist.
        """
        violations = []
        for file_path in files_to_modify:
            # Check forbidden first
            for pattern in forbidden_patterns:
                if _match_glob(file_path, pattern):
                    violations.append({"file": file_path, "reason": f"Matches forbidden: {pattern}"})
                    break
            else:
                # Check allowed
                allowed = False
                for pattern in allowed_patterns:
                    if _match_glob(file_path, pattern):
                        allowed = True
                        break
                if not allowed:
                    violations.append({"file": file_path, "reason": "Not in allowlist"})
        
        if violations:
            return GateResult(
                False,
                f"Advisor patch output contains {len(violations)} scope violation(s)",
                {"violations": violations},
            )
        
        return GateResult(True, "Advisor patch output within scope")
    
    def validate_json_output(
        self,
        output: Any,
        schema: dict[str, Any] | None = None,
    ) -> GateResult:
        """
        Validate JSON-serializable output from advisor.
        
        Optionally validates against JSON Schema if provided.
        """
        # JSON serialization check
        try:
            json.dumps(output)
        except (TypeError, ValueError) as e:
            return GateResult(False, f"Advisor output not JSON-serializable: {e}")
        
        # Optional JSON Schema validation
        if schema is not None and HAS_JSONSCHEMA:
            try:
                jsonschema.validate(output, schema)
            except jsonschema.ValidationError as e:
                return GateResult(
                    False,
                    f"Advisor output failed schema validation: {e.message}",
                    {"schema_path": list(e.schema_path)},
                )
        
        return GateResult(True, "Advisor JSON output validated")


def run_with_timeout(func: Callable, timeout_seconds: int, *args, **kwargs) -> tuple[Any, bool]:
    """
    Cooperative timeout runner.

    This implementation sets a cooperative deadline on an ExecutionContext (if
    provided via kwargs as `ctx`), and then calls the function synchronously.
    The function implementation MUST periodically call `ctx.check_deadline()` or
    `ctx.time_remaining()` to cooperatively abort when the deadline is reached.

    Returns: (result, timed_out)
    """
    # Try kwargs first, then positional args for ExecutionContext
    ctx = None
    if isinstance(kwargs.get("ctx"), ExecutionContext):
        ctx = kwargs.get("ctx")
    else:
        for a in args:
            if isinstance(a, ExecutionContext):
                ctx = a
                break

    # If we have an ExecutionContext, set the cooperative deadline
    if ctx is not None and timeout_seconds is not None:
        try:
            ctx.set_deadline(timeout_seconds)
        except Exception:
            # Ignore failures setting deadline; proceed without cooperative deadline
            pass

    try:
        result = func(*args, **kwargs)
        return result, False
    except DeadlineExceeded:
        # Function cooperatively aborted
        return None, True


class SkillExecutor:
    """
    Contract-first skill executor with bounded autonomy.
    
    HARD LIMITS (non-negotiable):
    - MAX_STEPS_DEFAULT = 50 per correlation_id
    - FIX_LOOP_MAX = 3 iterations
    - Per-skill timeout_seconds from contract
    
    HYBRID BACKBONE:
    Skills are classified as DETERMINISTIC, HYBRID, or ADVISOR_ONLY.
    Advisor outputs are validated before any side effects.
    
    Enforces:
    - Per-skill timeouts (hard)
    - Retry policies (only when safe + idempotent)
    - Scope gates (IMPLEMENT/COMMIT require allowlist.json)
    - Trace map gates (schema-infer/build)
    - Idempotency/dedupe for side-effect operations
    - Advisor output validation (HYBRID/ADVISOR_ONLY skills)
    - PR auto-merge prevention (default: human review required)
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
        state_store: Optional[Any] = None,  # Optional StateStore for delegation outbox
        config: RuntimeConfig | None = None,  # Runtime configuration
        kb_dir: Path | None = None,  # Optional KB directory (defaults to runtime/kb)
    ):
        self.registry = SkillRegistry(skills_dir)
        self.trace_gate = TraceMapGate(scripts_dir)
        self.scope_gate = ScopeGate(scripts_dir, artifacts_dir)
        self.sync_celery_gate = SyncCeleryGate(artifacts_dir)
        self.repo_grounding_gate = RepoGroundingGate(artifacts_dir)
        self.artifact_completeness_gate = ArtifactCompletenessGate(artifacts_dir)
        self.idempotency_store = IdempotencyStore(artifacts_dir)
        self.artifacts_dir = artifacts_dir
        self.scripts_dir = scripts_dir
        # Runtime config with safe defaults
        self.config = config or DEFAULT_RUNTIME_CONFIG
        # Advisor output validator (HYBRID BACKBONE)
        self.advisor_validator = AdvisorOutputValidator(artifacts_dir, scripts_dir)
        # Store repo_root for git diff scope checks (policy: require_git_diff_scope_check)
        self.repo_root = repo_root or skills_dir.parent
        # Enforce hard cap on max_steps
        self.max_steps = min(max_steps or self.MAX_STEPS_DEFAULT, self.MAX_STEPS_DEFAULT)
        
        # Step counter per correlation_id
        self._step_counts: dict[str, int] = {}
        
        # Skill implementations (to be registered)
        self._implementations: dict[str, Callable] = {}
        
        # Optional state store for delegation outbox
        # When provided, DELEGATING state persists to outbox instead of blocking
        self._state_store = state_store
        
        # Knowledge Base for pattern retrieval (LEARNING LOOP)
        # Initialize KB - will load and validate patterns on first access
        if kb_dir is None:
            kb_dir = Path(__file__).parent / "kb"
        self._kb: Optional[KnowledgeBase] = None
        self._kb_dir = kb_dir
        
        # Learning Loop Emitter for golden artifacts and promotion candidates
        # Emits artifacts after successful code generation or fix-loop completion
        self._learning_loop_emitter = LearningLoopEmitter(artifacts_dir)
        
        # Track fix loop state per correlation_id for promotion candidate emission
        # Structure: {correlation_id: {"iteration": int, "original_code": str, "error_message": str}}
        self._fix_loop_state: dict[str, dict[str, Any]] = {}

    @property
    def kb(self) -> KnowledgeBase:
        """Lazy-load Knowledge Base on first access."""
        if self._kb is None:
            try:
                self._kb = KnowledgeBase(self._kb_dir)
                # Trigger load to validate patterns early
                self._kb.load_all()
            except KBValidationError as e:
                # Log but don't fail - KB is advisory
                import sys
                print(f"Warning: KB validation failed: {e}", file=sys.stderr)
                # Return empty KB
                self._kb = KnowledgeBase(Path("/nonexistent"))
        return self._kb

    def _retrieve_kb_patterns(
        self,
        skill_name: str,
        inputs: dict[str, Any],
    ) -> str:
        """
        Retrieve relevant KB patterns for advisor-facing skills.
        
        Only retrieves patterns for HYBRID and ADVISOR_ONLY skills.
        Patterns are filtered by service and node_type from inputs.
        
        Returns formatted string for injection into skill context.
        """
        execution_mode = get_skill_execution_mode(skill_name)
        
        # Only retrieve patterns for advisor-facing skills
        if execution_mode == SkillExecutionMode.DETERMINISTIC:
            return ""
        
        # Determine filter criteria from inputs
        service = inputs.get("service_name") or inputs.get("service")
        node_type = inputs.get("node_type") or inputs.get("source_type")
        
        # Map source_type to node_type if needed
        if node_type == "TYPE1":
            node_type = "regular"  # TypeScript node
        elif node_type == "TYPE2":
            node_type = None  # Docs - don't filter by type
        
        # Determine categories based on skill
        categories = None
        if skill_name in ("schema-infer", "schema-build"):
            categories = ["ts_to_python"]
        elif skill_name in ("code-convert", "code-implement"):
            categories = ["auth", "ts_to_python", "pagination"]
        elif skill_name == "code-fix":
            categories = ["ts_to_python", "service_quirk"]
        
        # Retrieve patterns
        patterns = self.kb.retrieve_patterns(
            categories=categories,
            service=service,
            node_type=node_type,
            max_patterns=8,  # Keep token count bounded
        )
        
        if not patterns:
            return ""
        
        return self.kb.format_patterns_for_prompt(patterns)

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
        
        # Retrieve KB patterns for advisor-facing skills (LEARNING LOOP)
        kb_patterns = self._retrieve_kb_patterns(skill_name, inputs)
        
        # Inject KB patterns into inputs if available
        if kb_patterns:
            inputs = dict(inputs)  # Don't mutate original
            inputs["_kb_patterns"] = kb_patterns
        
        # Create context
        ctx = ExecutionContext(
            correlation_id=correlation_id,
            skill_name=skill_name,
            inputs=inputs,
            artifacts_dir=self.artifacts_dir / correlation_id,
        )
        ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)
        ctx.log("execution_started", {"skill": skill_name, "kb_patterns_injected": bool(kb_patterns)})
        
        errors: list[str] = []
        artifacts: list[Path] = []
        outputs: dict[str, Any] = {}
        status = ExecutionStatus.SUCCESS
        agent_response_metadata: Optional[AgentResponseMetadata] = None
        # Terminal state tracking for agent-style skills
        is_terminal_state: bool = True  # Default true for tool-style
        agent_state_value: Optional[str] = None  # None for tool-style
        # Idempotency tracking (for marking completion only on terminal)
        idem_key: Optional[str] = None
        contract: Optional[SkillContract] = None
        
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
            
            # 2b. Determine execution mode (HYBRID BACKBONE)
            execution_mode = get_skill_execution_mode(skill_name)
            ctx.log("execution_mode", {
                "mode": execution_mode.value,
                "skill": skill_name,
                "is_advisor": execution_mode in (SkillExecutionMode.HYBRID, SkillExecutionMode.ADVISOR_ONLY),
            })
            
            # 3. Check idempotency (for side-effect skills)
            # Use check_only() - we'll mark_completed() only on terminal completion
            if contract.idempotency.required and contract.idempotency.key_spec:
                already_done, idem_key = self.idempotency_store.check_only(
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
                        agent_metadata=None,  # Tool-style early return
                        is_terminal=True,  # Idempotency skip is terminal
                        agent_state=None,
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
                result = None  # No result in stub mode - skip agent response handling
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
                        # Cooperative deadline triggered: mark TIMEOUT and continue to finalization
                        errors.append(f"Skill timed out after {contract.timeout_seconds}s - ESCALATING")
                        status = ExecutionStatus.TIMEOUT
                        ctx.log("timeout", {"timeout_seconds": contract.timeout_seconds})
                        # Ensure terminal state is set so post-gates run appropriately
                        is_terminal_state = True
                        outputs = outputs or {}
                        result = None
                        # Skip further processing of result
                        # Do not raise here - return flow should emit TIMEOUT result
                        # Continue to post-processing/finalization
                        pass
                    
                    # Handle AgentResponse returns natively (STEP 3: unified execution interface)
                    # Skills can return either:
                    #   1. AgentResponse - native agent protocol (preferred for multi-turn)
                    #   2. dict - legacy tool-style (degenerate case)
                    
                    if isinstance(result, AgentResponse):
                        # Native AgentResponse - extract outputs and map state
                        outputs = result.outputs
                        agent_response_metadata = result.metadata
                        
                        # Map TaskState to ExecutionStatus for backward compatibility
                        task_state = result.state
                        agent_state_value = task_state.value  # Preserve semantic state
                        
                        # Determine if this is a terminal state
                        is_terminal_state = TaskState.is_terminal(task_state)
                        
                        if task_state == TaskState.COMPLETED:
                            # Terminal success - keep default status
                            pass
                        elif task_state == TaskState.FAILED:
                            status = ExecutionStatus.FAILED
                            if result.errors:
                                errors.extend(result.errors)
                        elif task_state == TaskState.INPUT_REQUIRED:
                            # Intermediate state - NOT an error, just needs more input
                            # Use SUCCESS as ExecutionStatus has no PENDING
                            # Caller MUST check is_terminal to know this isn't done
                            status = ExecutionStatus.SUCCESS
                            ctx.log("agent_input_required", {
                                "input_request": result.input_request.model_dump() if result.input_request else None,
                                "resume_token": result.metadata.resume_token if result.metadata else None,
                            })
                        elif task_state == TaskState.DELEGATING:
                            # Delegation - persist to outbox if configured
                            if self._state_store is not None and result.delegation_target:
                                # Save delegation message to outbox
                                import uuid
                                message_id = str(uuid.uuid4())
                                self._state_store.save_outbox_message(
                                    context_id=correlation_id,
                                    message_id=message_id,
                                    target_agent=result.delegation_target,
                                    message_type="delegate",
                                    payload={
                                        "outputs": result.outputs,
                                        "turn_number": result.turn_number,
                                        "state_handle": result.state_handle,
                                    },
                                    correlation_id=correlation_id,
                                )
                                # DELEGATING is non-terminal - skill is waiting for delegation response
                                status = ExecutionStatus.SUCCESS
                                is_terminal_state = False
                                ctx.log("agent_delegating", {
                                    "target_agent": result.delegation_target,
                                    "message_id": message_id,
                                    "resume_token": result.metadata.resume_token if result.metadata else None,
                                })
                            else:
                                # No outbox configured - reject per .copilot rules
                                errors.append("DELEGATING state requires state_store with outbox support")
                                status = ExecutionStatus.BLOCKED
                                # Note: DELEGATING without outbox is a configuration error, terminal
                                is_terminal_state = True
                        elif task_state == TaskState.PAUSED:
                            # Paused is also intermediate - use SUCCESS
                            status = ExecutionStatus.SUCCESS
                            ctx.log("agent_paused", {"resume_token": result.metadata.resume_token if result.metadata else None})
                        elif task_state == TaskState.BLOCKED:
                            status = ExecutionStatus.BLOCKED
                        elif task_state == TaskState.TIMEOUT:
                            status = ExecutionStatus.TIMEOUT
                        elif task_state == TaskState.ESCALATED:
                            status = ExecutionStatus.ESCALATED
                            errors.append("Skill escalated - exceeded fix loop iterations")
                        # IN_PROGRESS shouldn't be returned from a sync skill, treat as ongoing
                        elif task_state == TaskState.IN_PROGRESS:
                            status = ExecutionStatus.SUCCESS
                            is_terminal_state = False
                        else:
                            # Unknown state - treat as non-terminal to be safe
                            status = ExecutionStatus.SUCCESS
                            is_terminal_state = False
                    else:
                        # Legacy dict return - tool-style degenerate case
                        # Always terminal (one-shot execution)
                        outputs = result or {}
                        is_terminal_state = True
                        agent_state_value = None
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
            
            # ================================================================
            # ADVISOR OUTPUT VALIDATION (HYBRID BACKBONE)
            # For HYBRID and ADVISOR_ONLY skills, validate outputs before
            # they can trigger any side effects. Deterministic skills skip.
            # ================================================================
            if execution_mode in (SkillExecutionMode.HYBRID, SkillExecutionMode.ADVISOR_ONLY):
                advisor_validation_errors = []
                
                # Validate code outputs (if any)
                files_modified = outputs.get("files_modified", []) + outputs.get("files_created", [])
                generated_code = outputs.get("generated_code")
                
                if generated_code:
                    code_result = self.advisor_validator.validate_code_output(
                        generated_code,
                        correlation_id,
                    )
                    if not code_result.passed:
                        advisor_validation_errors.append(code_result.message)
                        ctx.log("advisor_code_validation_failed", {
                            "reason": code_result.message,
                            "details": code_result.details,
                        })
                
                # Validate schema outputs (for schema-infer)
                if skill_name == "schema-infer":
                    inferred_schema = outputs.get("inferred_schema")
                    trace_map = outputs.get("trace_map")
                    if inferred_schema:
                        schema_result = self.advisor_validator.validate_schema_output(
                            inferred_schema,
                            trace_map,
                            correlation_id,
                        )
                        if not schema_result.passed:
                            advisor_validation_errors.append(schema_result.message)
                            ctx.log("advisor_schema_validation_failed", {
                                "reason": schema_result.message,
                                "details": schema_result.details,
                            })
                
                # Validate patch/file outputs are in scope
                if files_modified:
                    # Load allowlist for scope check
                    allowlist_path = ctx.artifacts_dir / "allowlist.json"
                    if allowlist_path.exists():
                        try:
                            allowlist_data = json.loads(allowlist_path.read_text())
                            allowed_patterns = allowlist_data.get("allowed_paths", [])
                            forbidden_patterns = allowlist_data.get("forbidden_paths", []) + DEFAULT_FORBIDDEN_PATHS
                            
                            patch_result = self.advisor_validator.validate_patch_output(
                                files_modified,
                                allowed_patterns,
                                forbidden_patterns,
                            )
                            if not patch_result.passed:
                                advisor_validation_errors.append(patch_result.message)
                                ctx.log("advisor_patch_validation_failed", {
                                    "reason": patch_result.message,
                                    "violations": patch_result.details.get("violations", []),
                                })
                        except json.JSONDecodeError:
                            pass  # Allowlist validation happens in scope gate
                
                # Block execution if advisor validation failed
                if advisor_validation_errors:
                    errors.extend(advisor_validation_errors)
                    status = ExecutionStatus.BLOCKED
                    ctx.log("advisor_validation_blocked", {
                        "execution_mode": execution_mode.value,
                        "errors": advisor_validation_errors,
                    })
                else:
                    ctx.log("advisor_validation_passed", {
                        "execution_mode": execution_mode.value,
                        "skill": skill_name,
                    })
            
            # ================================================================
            # INTERACTION OUTCOMES ENFORCEMENT
            # Validate agent responses against contract's interaction_outcomes
            # ================================================================
            if isinstance(result, AgentResponse) and contract is not None:
                io_errors, should_escalate = self._validate_interaction_outcomes(
                    contract=contract,
                    task_state=result.state,
                    agent_response=result,
                    correlation_id=correlation_id,
                    ctx=ctx,
                )
                if io_errors:
                    errors.extend(io_errors)
                    if should_escalate:
                        status = ExecutionStatus.ESCALATED
                        is_terminal_state = True  # Escalation is terminal
                        ctx.log("interaction_outcomes_escalated", {"errors": io_errors})
                        # Skip post-gates on escalation - already failed definitively
                        raise ValueError("Max turns exceeded - escalating")
                    else:
                        status = ExecutionStatus.BLOCKED
                        is_terminal_state = True  # Contract violation is terminal
                        ctx.log("interaction_outcomes_blocked", {"errors": io_errors})
                        # Skip post-gates on contract violation - already failed definitively
                        raise ValueError("Interaction outcomes contract violation")
            
            # ================================================================
            # POST-GATES: Only enforce for TERMINAL states
            # Non-terminal states (INPUT_REQUIRED, PAUSED) are intermediate
            # and should NOT be blocked by artifact/validation requirements
            # ================================================================
            if is_terminal_state:
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
                
                # 7d. Post-gate for pr-prepare: AUTO-MERGE PREVENTION (HYBRID BACKBONE)
                # By default, pr-prepare only prepares artifacts - NO automatic merge
                # This is a safety-critical control: human review is mandatory
                if skill_name == "pr-prepare":
                    # Check if outputs indicate merge request
                    merge_requested = outputs.get("merge_requested", False)
                    
                    if merge_requested and not self.config.auto_merge_enabled:
                        # Block auto-merge - this is default safe behavior
                        ctx.log("auto_merge_blocked", {
                            "reason": "auto_merge_disabled",
                            "config_auto_merge_enabled": self.config.auto_merge_enabled,
                            "config_require_human_review": self.config.require_human_review,
                        })
                        # Rewrite outputs to ensure merge_executed is False
                        outputs["merge_executed"] = False
                        outputs["merge_blocked_reason"] = "Auto-merge disabled (default safe behavior)"
                        outputs["human_review_required"] = True
                    elif merge_requested and not self.config.require_human_review:
                        # Explicit opt-out of human review (rare, dangerous)
                        ctx.log("auto_merge_warning", {
                            "warning": "Auto-merge enabled WITHOUT human review - dangerous configuration",
                            "merge_requested": merge_requested,
                        })
                    else:
                        # Normal case: prepare PR only, no merge
                        outputs["merge_executed"] = False
                        outputs["human_review_required"] = True
                        ctx.log("pr_prepare_complete", {
                            "merge_executed": False,
                            "human_review_required": True,
                            "artifacts_ready": True,
                        })
                    
                    # 7e. Artifact completeness gate for pr-prepare
                    # All required artifacts must exist before PR is ready
                    is_escalation = status == ExecutionStatus.ESCALATED
                    completeness_result = self.artifact_completeness_gate.check(
                        correlation_id,
                        contract.autonomy_level,
                        is_escalation=is_escalation,
                    )
                    ctx.log("artifact_completeness_gate", {
                        "passed": completeness_result.passed,
                        "details": completeness_result.details,
                    })
                    if not completeness_result.passed:
                        errors.append(f"Artifact completeness check failed: {completeness_result.message}")
                        # Don't block - just warn. PR can be prepared with warnings.
                        outputs["artifact_warnings"] = completeness_result.details.get("missing", [])
                
                # 8. Validate outputs (only for terminal states)
                output_errors = self._validate_outputs(outputs, contract.output_schema)
                if output_errors:
                    errors.extend(output_errors)
                    # Don't fail on output validation - just warn
                    ctx.log("output_validation_warning", {"errors": output_errors})
                
                # 9. Collect artifacts (only required for terminal states)
                for artifact_spec in contract.required_artifacts:
                    artifact_path = ctx.artifacts_dir / artifact_spec.name
                    if artifact_path.exists():
                        artifacts.append(artifact_path)
                    else:
                        ctx.log("artifact_missing", {"name": artifact_spec.name})
            else:
                # Non-terminal state - skip post-gates, just log
                ctx.log("post_gates_skipped", {
                    "reason": "non_terminal_state",
                    "agent_state": agent_state_value,
                })
        
        except Exception as e:
            if status == ExecutionStatus.SUCCESS:
                status = ExecutionStatus.FAILED
            errors.append(str(e))
            ctx.log("execution_error", {"error": str(e)})
            # Exceptions are terminal failures
            is_terminal_state = True
        
        # Mark idempotency ONLY on terminal completion
        # This allows multi-turn skills to resume with same correlation_id
        if is_terminal_state and idem_key and contract and contract.idempotency.required:
            self.idempotency_store.mark_completed(correlation_id, skill_name, idem_key)
            ctx.log("idempotency_marked", {"key": idem_key})
        
        # ================================================================
        # LEARNING LOOP EMISSION
        # Emit golden artifacts after successful code generation
        # Emit promotion candidates after successful fix-loop completion
        # ================================================================
        if is_terminal_state and status == ExecutionStatus.SUCCESS:
            self._emit_learning_artifacts(
                skill_name=skill_name,
                correlation_id=correlation_id,
                outputs=outputs,
                ctx=ctx,
            )
        
        duration_ms = int((time.time() - start_time) * 1000)
        ctx.log("execution_completed", {
            "status": status.value,
            "duration_ms": duration_ms,
            "is_terminal": is_terminal_state,
            "agent_state": agent_state_value,
        })
        
        return ExecutionResult(
            status=status,
            outputs=outputs,
            artifacts=artifacts,
            errors=errors,
            trace=ctx.trace,
            duration_ms=duration_ms,
            agent_metadata=agent_response_metadata,
            is_terminal=is_terminal_state,
            agent_state=agent_state_value,
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

    def _validate_interaction_outcomes(
        self,
        contract: SkillContract,
        task_state: TaskState,
        agent_response: AgentResponse | None,
        correlation_id: str,
        ctx: ExecutionContext,
    ) -> tuple[list[str], bool]:
        """
        Validate agent response against contract's interaction_outcomes.
        
        Enforces:
        1. Intermediate states must be in allowed_intermediate_states
        2. Turn count must not exceed max_turns
        3. INPUT_REQUIRED payload must validate against input_request_jsonschema
        
        Returns:
            (errors, should_escalate): List of errors and whether to escalate
        """
        errors: list[str] = []
        should_escalate = False
        
        # Skip validation for terminal states or tool-style (no interaction_outcomes)
        if TaskState.is_terminal(task_state):
            return errors, should_escalate
        
        if contract.interaction_outcomes is None:
            # No interaction_outcomes defined - skill is tool-style
            # Non-terminal from a tool-style skill is unexpected - error
            errors.append(
                f"Skill '{contract.name}' returned non-terminal state {task_state.value} "
                "but has no interaction_outcomes defined (tool-style skill)"
            )
            return errors, should_escalate
        
        outcomes = contract.interaction_outcomes
        
        # 1. Check allowed intermediate states
        state_to_intermediate = {
            TaskState.INPUT_REQUIRED: IntermediateState.INPUT_REQUIRED,
            TaskState.PAUSED: IntermediateState.PAUSED,
            TaskState.DELEGATING: IntermediateState.DELEGATING,
        }
        
        intermediate = state_to_intermediate.get(task_state)
        if intermediate is not None:
            if intermediate not in outcomes.allowed_intermediate_states:
                errors.append(
                    f"Skill '{contract.name}' returned {task_state.value} but contract "
                    f"only allows: {[s.value for s in outcomes.allowed_intermediate_states]}"
                )
                ctx.log("interaction_outcome_violation", {
                    "state": task_state.value,
                    "allowed": [s.value for s in outcomes.allowed_intermediate_states],
                })
        
        # 2. Check turn count (using step_counts as proxy for turns)
        # Each execute() call increments step count - use as turn proxy
        turn_count = self._step_counts.get(correlation_id, 1)
        if turn_count > outcomes.max_turns:
            errors.append(
                f"Turn count ({turn_count}) exceeds max_turns ({outcomes.max_turns}) - ESCALATING"
            )
            should_escalate = True
            ctx.log("max_turns_exceeded", {
                "turn_count": turn_count,
                "max_turns": outcomes.max_turns,
            })
        
        # 3. Validate INPUT_REQUIRED payload against jsonschema
        if (
            task_state == TaskState.INPUT_REQUIRED
            and agent_response is not None
            and agent_response.input_request is not None
            and outcomes.input_request_jsonschema is not None
        ):
            # Extract payload to validate - input_request contains the schema/request spec
            payload = agent_response.input_request.model_dump()
            
            if HAS_JSONSCHEMA:
                try:
                    jsonschema.validate(payload, outcomes.input_request_jsonschema)
                    ctx.log("input_request_validated", {"valid": True})
                except jsonschema.ValidationError as e:
                    errors.append(f"INPUT_REQUIRED payload invalid: {e.message}")
                    ctx.log("input_request_validated", {
                        "valid": False,
                        "error": e.message,
                    })
            else:
                # jsonschema not available - log warning, skip validation
                ctx.log("input_request_validation_skipped", {
                    "reason": "jsonschema library not installed"
                })
        
        return errors, should_escalate

    def _emit_learning_artifacts(
        self,
        skill_name: str,
        correlation_id: str,
        outputs: dict[str, Any],
        ctx: ExecutionContext,
    ) -> None:
        """
        Emit learning loop artifacts after successful skill execution.
        
        GOLDEN ARTIFACTS: Emitted after successful code-implement or code-convert.
        Contains the generated code, schema, and trace map for future pattern extraction.
        
        PROMOTION CANDIDATES: Emitted after successful fix-loop completion.
        Contains the error pattern and fix applied for review and potential KB promotion.
        
        All artifacts are READ-ONLY at runtime. Promotion requires human review.
        """
        try:
            # Emit golden artifact for code generation skills
            if skill_name in ("code-implement", "code-convert"):
                self._emit_golden_artifact(skill_name, correlation_id, outputs, ctx)
            
            # Emit promotion candidate for successful fix-loop
            if skill_name == "code-fix":
                self._emit_promotion_candidate(correlation_id, outputs, ctx)
                
        except Exception as e:
            # Learning loop emission is non-critical - log and continue
            ctx.log("learning_loop_emission_error", {
                "skill": skill_name,
                "error": str(e),
            })

    def _emit_golden_artifact(
        self,
        skill_name: str,
        correlation_id: str,
        outputs: dict[str, Any],
        ctx: ExecutionContext,
    ) -> None:
        """Emit golden artifact package for successful code generation."""
        # Extract generated code from outputs
        generated_code: dict[str, str] = {}
        
        # Check various output formats
        if "generated_code" in outputs and isinstance(outputs["generated_code"], dict):
            generated_code = outputs["generated_code"]
        elif "files_created" in outputs:
            # Map file paths to content (need to read files)
            for file_path in outputs["files_created"]:
                path = Path(file_path)
                if path.exists() and path.suffix == ".py":
                    try:
                        generated_code[path.name] = path.read_text()
                    except Exception:
                        pass
        
        if not generated_code:
            ctx.log("golden_artifact_skipped", {"reason": "no_generated_code"})
            return
        
        # Load schema and trace_map if available
        node_schema = None
        trace_map = None
        
        schema_path = ctx.artifacts_dir / "inferred_schema.json"
        if schema_path.exists():
            try:
                node_schema = json.loads(schema_path.read_text())
            except json.JSONDecodeError:
                pass
        
        trace_map_path = ctx.artifacts_dir / "trace_map.json"
        if trace_map_path.exists():
            try:
                trace_map = json.loads(trace_map_path.read_text())
            except json.JSONDecodeError:
                pass
        
        # Determine node_type from outputs or schema
        node_type = outputs.get("node_type") or (
            node_schema.get("node_type") if node_schema else "unknown"
        )
        
        # Create golden artifact package
        package = GoldenArtifactPackage(
            correlation_id=correlation_id,
            node_type=node_type,
            skill_name=skill_name,
            created_at=datetime.utcnow().isoformat(),
            generated_code=generated_code,
            node_schema=node_schema,
            trace_map=trace_map,
            tests_passed=outputs.get("tests_passed", False),
            validation_passed=outputs.get("validation_passed", True),
            fix_iterations=outputs.get("fix_iterations", 0),
            source_files=outputs.get("source_files", []),
        )
        
        # Emit the package
        artifact_path = self._learning_loop_emitter.emit_golden_artifact(package)
        ctx.log("golden_artifact_emitted", {
            "path": str(artifact_path),
            "node_type": node_type,
            "code_files": list(generated_code.keys()),
        })

    def _emit_promotion_candidate(
        self,
        correlation_id: str,
        outputs: dict[str, Any],
        ctx: ExecutionContext,
    ) -> None:
        """Emit promotion candidate after successful fix-loop completion."""
        # Only emit if this was a successful fix
        if not outputs.get("fixed", False):
            return
        
        # Check if we have fix loop state for this correlation
        fix_state = self._fix_loop_state.get(correlation_id)
        if not fix_state:
            ctx.log("promotion_candidate_skipped", {"reason": "no_fix_loop_state"})
            return
        
        error_message = fix_state.get("error_message", "")
        original_code = fix_state.get("original_code", "")
        fixed_code = outputs.get("fixed_code", "")
        
        if not original_code or not fixed_code:
            ctx.log("promotion_candidate_skipped", {"reason": "missing_code"})
            return
        
        # Categorize the error for suggested KB placement
        error_category = categorize_error(error_message)
        
        # Map error category to KB category suggestion
        category_mapping = {
            "async_violation": "ts_to_python",
            "type_error": "ts_to_python",
            "import_error": "ts_to_python",
            "missing_timeout": "service_quirk",
            "syntax_error": None,  # Don't promote syntax fixes
            "general_error": None,
        }
        suggested_category = category_mapping.get(error_category)
        
        if not suggested_category:
            ctx.log("promotion_candidate_skipped", {
                "reason": "error_not_promotable",
                "error_category": error_category,
            })
            return
        
        # Create promotion candidate
        candidate = PromotionCandidate(
            correlation_id=correlation_id,
            created_at=datetime.utcnow().isoformat(),
            error_category=error_category,
            error_message=error_message,
            error_location=fix_state.get("error_location"),
            original_code=original_code,
            fixed_code=fixed_code,
            fix_description=outputs.get("fix_description", f"Fixed {error_category}"),
            fix_iteration=fix_state.get("iteration", 1),
            validation_passed=True,  # Only emit on successful fix
            suggested_category=suggested_category,
        )
        
        # Emit the candidate
        candidate_path = self._learning_loop_emitter.emit_promotion_candidate(candidate)
        ctx.log("promotion_candidate_emitted", {
            "path": str(candidate_path),
            "error_category": error_category,
            "suggested_category": suggested_category,
        })
        
        # Clean up fix loop state
        del self._fix_loop_state[correlation_id]

    def track_fix_loop_start(
        self,
        correlation_id: str,
        error_message: str,
        original_code: str,
        error_location: str | None = None,
    ) -> None:
        """
        Track the start of a fix loop for promotion candidate emission.
        
        Call this before starting code-fix iterations.
        """
        self._fix_loop_state[correlation_id] = {
            "iteration": 0,
            "error_message": error_message,
            "original_code": original_code,
            "error_location": error_location,
        }

    def track_fix_loop_iteration(self, correlation_id: str) -> None:
        """Increment fix loop iteration counter."""
        if correlation_id in self._fix_loop_state:
            self._fix_loop_state[correlation_id]["iteration"] += 1


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
                    agent_metadata=None,  # Fix loop terminal success
                    is_terminal=True,
                    agent_state=None,
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
            agent_metadata=None,  # Fix loop escalation - terminal
            is_terminal=True,
            agent_state=None,
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
        "schema-infer": skills_dir / "schema-infer" / "impl.py",
        # Future implementations:
        # "source-ingest": skills_dir / "source-ingest" / "impl.py",
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
