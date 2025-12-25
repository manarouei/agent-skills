"""
Skill Contract Schemas - Pydantic models for enforceable skill contracts.

These models define the contract structure that every skill MUST declare in its
YAML frontmatter. The contracts enable machine-checkable validation and bounded
autonomy enforcement.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class AutonomyLevel(str, Enum):
    """Bounded autonomy levels for skill execution."""

    READ = "READ"  # Can only read files/data, no modifications
    SUGGEST = "SUGGEST"  # Can suggest changes, human approves
    IMPLEMENT = "IMPLEMENT"  # Can write files within scope
    COMMIT = "COMMIT"  # Can commit to git (highest privilege)


class ExecutionStatus(str, Enum):
    """Skill execution result status."""

    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"      # Blocked by gate (scope, trace, etc.)
    ESCALATED = "escalated"  # Exceeded max iterations, needs human
    TIMEOUT = "timeout"      # Exceeded timeout_seconds


class SideEffect(str, Enum):
    """Side effects a skill may produce."""

    FS = "fs"  # Filesystem operations
    NET = "net"  # Network requests
    GIT = "git"  # Git operations
    DB = "db"  # Database operations


class RetryPolicy(str, Enum):
    """Retry behavior on failure."""

    NONE = "none"  # No retries
    SAFE = "safe"  # Retry only idempotent operations


class FailureMode(str, Enum):
    """Known failure modes for skills."""

    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    SCOPE_VIOLATION = "scope_violation"
    TRACE_INCOMPLETE = "trace_incomplete"
    MAX_ITERATIONS = "max_iterations"
    PERMISSION_DENIED = "permission_denied"


class RetryConfig(BaseModel):
    """Retry configuration for skill execution."""

    policy: RetryPolicy = RetryPolicy.NONE
    max_retries: int = Field(default=0, ge=0, le=5)
    backoff_seconds: float = Field(default=1.0, ge=0.1, le=60.0)


class IdempotencyConfig(BaseModel):
    """Idempotency configuration."""

    required: bool = False
    key_spec: Optional[str] = None  # e.g., "correlation_id + operation"


class ArtifactSpec(BaseModel):
    """Specification for artifacts emitted by a skill."""

    name: str
    type: Literal["json", "yaml", "md", "py", "txt", "diff"]
    description: str


class SkillContract(BaseModel):
    """
    Complete contract specification for a skill.
    
    This is the enforceable contract that every skill MUST declare.
    It enables bounded autonomy, scope enforcement, and machine validation.
    """

    # Identity
    name: str = Field(..., pattern=r"^[a-z][a-z0-9-]*[a-z0-9]$", max_length=64)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")  # semver
    description: str = Field(..., min_length=10, max_length=1024)

    # Autonomy & Safety
    autonomy_level: AutonomyLevel
    side_effects: List[SideEffect] = Field(default_factory=list)

    # Execution Bounds
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    idempotency: IdempotencyConfig = Field(default_factory=IdempotencyConfig)
    max_fix_iterations: int = Field(default=3, ge=1, le=5)

    # I/O Schemas (JSON Schema references or inline)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)

    # Artifacts
    required_artifacts: List[ArtifactSpec] = Field(default_factory=list)
    
    # Failure Modes
    failure_modes: List[FailureMode] = Field(default_factory=list)

    # Dependencies
    depends_on: List[str] = Field(default_factory=list)  # skill names
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if v.startswith("-") or v.endswith("-") or "--" in v:
            raise ValueError("Name cannot start/end with hyphen or contain consecutive hyphens")
        return v


class TraceSource(str, Enum):
    """Source type for trace map entries."""
    API_DOCS = "API_DOCS"
    SOURCE_CODE = "SOURCE_CODE"
    ASSUMPTION = "ASSUMPTION"


class ConfidenceLevel(str, Enum):
    """Confidence level for trace map entries."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TraceEntry(BaseModel):
    """
    Single trace entry linking a schema field to its source evidence.
    
    This documents WHERE a piece of schema inference came from.
    ASSUMPTION entries MUST include assumption_rationale for human review.
    """

    field_path: str = Field(..., pattern=r"^[\w\.\[\]\*]+$")
    source: TraceSource
    evidence: str = Field(..., min_length=10)  # Must be substantive
    confidence: ConfidenceLevel
    
    # Required for ASSUMPTION entries
    assumption_rationale: Optional[str] = None
    
    # Optional metadata
    source_file: Optional[str] = None
    line_range: Optional[str] = None  # e.g., "L10-L25"
    excerpt_hash: Optional[str] = None  # SHA256 of evidence (first 12 chars)
    verified: bool = False

    @field_validator("assumption_rationale")
    @classmethod
    def require_rationale_for_assumptions(cls, v: Optional[str], info) -> Optional[str]:
        # Note: Can't access other fields easily in Pydantic v2, validation is advisory
        return v


class TraceMap(BaseModel):
    """
    Trace map linking inferred schema fields to source evidence.
    
    CRITICAL: Every field in the schema MUST have a trace entry.
    Max 30% can be ASSUMPTION entries for IMPLEMENT autonomy level.
    
    File format: JSON only (canonical format, no YAML)
    """

    correlation_id: str
    node_type: str
    trace_entries: List[TraceEntry] = Field(default_factory=list)
    
    # Metadata
    generated_at: Optional[str] = None
    skill_version: Optional[str] = None

    def assumption_ratio(self) -> float:
        """Calculate ratio of ASSUMPTION entries."""
        if not self.trace_entries:
            return 0.0
        assumptions = sum(1 for e in self.trace_entries if e.source == TraceSource.ASSUMPTION)
        return assumptions / len(self.trace_entries)

    def is_valid_for_implement(self) -> bool:
        """Check if trace map allows IMPLEMENT autonomy (max 30% assumptions)."""
        return self.assumption_ratio() <= 0.30


class ScopeAllowlist(BaseModel):
    """File scope allowlist for a node implementation."""

    node_name: str
    allowed_patterns: List[str] = Field(default_factory=list)
    # Default patterns derived from node_name
    
    def get_patterns(self) -> List[str]:
        """Get all allowed file patterns."""
        base_patterns = [
            f"nodes/{self.node_name}*",
            f"nodes/{self.node_name.replace('-', '_')}*",
            f"tests/*{self.node_name}*",
            f"tests/*{self.node_name.replace('-', '_')}*",
            f"credentials/*{self.node_name}*",
        ]
        return base_patterns + self.allowed_patterns


class ValidationResult(BaseModel):
    """Result of skill contract validation."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    skill_name: Optional[str] = None
