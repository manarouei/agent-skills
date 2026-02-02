#!/usr/bin/env python3
"""
Node Contract Manifest - Machine-Checkable Execution Contract

CRITICAL: This is the authoritative contract specification for generated nodes.
Every converted node MUST have a corresponding .contract.yaml manifest.

Contract-first means:
1. Contract is written FIRST (defines ALL behavior)
2. Implementation MUST conform to contract (no hidden behavior)
3. Runtime enforces contract (centralized in Celery/executor)
4. Violations are mechanically rejectable (<80% correctness)

Hard-Fail Invariants (ANY failure = automatic rejection):
- No machine-readable contract manifest
- Input/output schema cannot be validated
- Undeclared side-effects
- No hard execution timeout
- Retry policy without idempotency semantics
- Placeholder endpoints (example.com, TODO, empty DSN)
- Unknown inputs silently accepted
- Error model is implicit

≥80% Correctness Scoring:
- Contract completeness: 40pts
- Side-effects & credentials: 25pts
- Execution semantics: 25pts
- n8n normalization: 10pts

SYNC-CELERY SAFE: Pure schema definitions, no I/O.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class SideEffectType(str, Enum):
    """Types of side-effects a node can have."""
    NETWORK = "network"          # HTTP requests, API calls
    DATABASE = "database"        # SQL/NoSQL database operations
    FILESYSTEM = "filesystem"    # File read/write
    MESSAGING = "messaging"      # Queue/pub-sub operations
    STATEFUL = "stateful"        # Maintains state across executions
    NONE = "none"                # Pure data transformation


class ErrorCategory(str, Enum):
    """Normalized error categories for deterministic handling."""
    AUTH_FAILED = "auth_failed"           # 401, 403, invalid credentials
    RATE_LIMIT = "rate_limit"             # 429, quota exceeded
    NOT_FOUND = "not_found"               # 404, resource doesn't exist
    VALIDATION = "validation"             # 400, invalid input
    TIMEOUT = "timeout"                   # Operation timed out
    NETWORK = "network"                   # Connection failures
    SERVER_ERROR = "server_error"         # 5xx errors
    CONFLICT = "conflict"                 # 409, state conflict
    QUOTA_EXCEEDED = "quota_exceeded"     # Usage limits
    UNKNOWN = "unknown"                   # Unclassified errors


class RetryPolicy(str, Enum):
    """Retry behavior policy."""
    NONE = "none"                    # Never retry
    IDEMPOTENT_ONLY = "idempotent"   # Retry only if operation is idempotent
    ALWAYS = "always"                # Always retry (dangerous)
    TRANSIENT_ERRORS = "transient"   # Retry only on transient errors


class InputFieldSchema(BaseModel):
    """Schema for a single input field."""
    name: str = Field(..., description="Field name")
    type: Literal["string", "number", "boolean", "array", "object", "json", "binary"] = Field(
        ..., description="Field type"
    )
    required: bool = Field(False, description="Whether field is required")
    default: Optional[Any] = Field(None, description="Explicit default value")
    description: str = Field("", description="Field description")
    enum: Optional[List[Any]] = Field(None, description="Allowed values (if enum)")
    pattern: Optional[str] = Field(None, description="Regex pattern (for strings)")
    min_value: Optional[float] = Field(None, description="Minimum value (numbers)")
    max_value: Optional[float] = Field(None, description="Maximum value (numbers)")
    min_length: Optional[int] = Field(None, description="Minimum length (strings/arrays)")
    max_length: Optional[int] = Field(None, description="Maximum length (strings/arrays)")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field name cannot be empty")
        return v


class OutputFieldSchema(BaseModel):
    """Schema for a single output field."""
    name: str = Field(..., description="Field name")
    type: Literal["string", "number", "boolean", "array", "object", "json", "binary", "any"] = Field(
        ..., description="Field type"
    )
    description: str = Field("", description="Field description")
    nullable: bool = Field(False, description="Whether field can be null")


class InputContractSchema(BaseModel):
    """Complete input schema contract."""
    fields: List[InputFieldSchema] = Field(default_factory=list, description="Input fields")
    additional_properties: bool = Field(
        False, 
        description="Whether to accept unknown fields (MUST be false for generated nodes)"
    )
    strict: bool = Field(True, description="Whether to strictly validate inputs")


class OutputContractSchema(BaseModel):
    """Complete output schema contract."""
    success_fields: List[OutputFieldSchema] = Field(
        default_factory=list, 
        description="Fields present in successful execution"
    )
    error_fields: List[OutputFieldSchema] = Field(
        default_factory=list,
        description="Fields present in error responses"
    )
    deterministic: bool = Field(
        True, 
        description="Whether output is deterministic for same input"
    )


class CredentialScope(BaseModel):
    """Credential usage and security scope."""
    credential_type: str = Field(..., description="Type of credential required")
    required: bool = Field(True, description="Whether credential is required")
    host_allowlist: Optional[List[str]] = Field(
        None, 
        description="Allowed hosts (for network operations). MUST NOT contain example.com or TODO"
    )
    database_allowlist: Optional[List[str]] = Field(
        None,
        description="Allowed database names. MUST NOT be empty or contain placeholders"
    )
    path_allowlist: Optional[List[str]] = Field(
        None,
        description="Allowed filesystem paths. MUST NOT contain /tmp or placeholders"
    )
    
    @field_validator("host_allowlist")
    @classmethod
    def validate_hosts(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        # Check for empty strings first
        if any(not host or not host.strip() for host in v):
            raise ValueError("Host allowlist contains empty or whitespace-only entries")
        # Check for placeholder strings (case-insensitive)
        invalid = ["example.com", "localhost", "todo", "dummy", "placeholder"]
        for host in v:
            host_lower = host.lower()
            if any(inv in host_lower for inv in invalid):
                raise ValueError(f"Invalid placeholder host in allowlist: {host}")
        return v
    
    @field_validator("database_allowlist")
    @classmethod
    def validate_databases(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        if not v:
            raise ValueError("Database allowlist cannot be empty if specified")
        # Check for empty strings first
        if any(not db or not db.strip() for db in v):
            raise ValueError("Database allowlist contains empty or whitespace-only entries")
        # Check for placeholder strings (case-insensitive)
        invalid = ["test", "example", "todo", "dummy"]
        for db in v:
            db_lower = db.lower()
            if any(inv in db_lower for inv in invalid):
                raise ValueError(f"Invalid placeholder database in allowlist: {db}")
        return v


class ExecutionSemantics(BaseModel):
    """Execution behavior and constraints."""
    timeout_seconds: int = Field(..., ge=1, le=300, description="Hard execution timeout")
    retry_policy: RetryPolicy = Field(
        RetryPolicy.NONE, 
        description="Retry behavior policy"
    )
    idempotent: bool = Field(
        False, 
        description="Whether operation can be safely retried"
    )
    transactional: bool = Field(
        False,
        description="Whether operation is part of a transaction"
    )
    max_retries: int = Field(0, ge=0, le=5, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(1, ge=1, le=60, description="Delay between retries")
    
    @model_validator(mode="after")
    def validate_retry_semantics(self) -> "ExecutionSemantics":
        # Hard-fail: Retry without idempotency is dangerous
        if self.max_retries > 0 and not self.idempotent and self.retry_policy != RetryPolicy.NONE:
            raise ValueError(
                "HARD-FAIL: Cannot have max_retries > 0 without idempotent=True. "
                "This would cause data corruption."
            )
        
        # Retry policy must be consistent
        if self.retry_policy == RetryPolicy.IDEMPOTENT_ONLY and not self.idempotent:
            raise ValueError("Cannot use IDEMPOTENT_ONLY retry policy when idempotent=False")
            
        return self


class SideEffectDeclaration(BaseModel):
    """Explicit declaration of side-effects."""
    types: List[SideEffectType] = Field(
        default_factory=list, 
        description="Types of side-effects this node has"
    )
    network_destinations: Optional[List[str]] = Field(
        None,
        description="Network destinations (hosts/IPs). MUST NOT contain placeholders"
    )
    database_operations: Optional[List[Literal["read", "write", "delete", "schema"]]] = Field(
        None,
        description="Database operation types"
    )
    filesystem_paths: Optional[List[str]] = Field(
        None,
        description="Filesystem paths accessed. MUST NOT contain /tmp"
    )
    
    @field_validator("network_destinations")
    @classmethod
    def validate_network(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        # Check for empty strings first
        if any(not dest or not dest.strip() for dest in v):
            raise ValueError("Network destinations contain empty or whitespace-only entries")
        # Check for placeholder strings (case-insensitive)
        invalid = ["example.com", "todo", "dummy", "placeholder"]
        for dest in v:
            dest_lower = dest.lower()
            if any(inv in dest_lower for inv in invalid):
                raise ValueError(f"Invalid placeholder in network_destinations: {dest}")
        return v


class N8nSemanticNormalization(BaseModel):
    """Explicit n8n default and expression handling."""
    defaults_explicit: bool = Field(
        True,
        description="Whether all n8n defaults are made explicit (no inherited behavior)"
    )
    expression_boundaries: List[str] = Field(
        default_factory=list,
        description="Fields that support n8n expressions"
    )
    eval_disabled: bool = Field(
        False,
        description="Whether n8n expression evaluation is disabled"
    )


class NodeContract(BaseModel):
    """
    Complete execution contract for a converted node.
    
    This is the AUTHORITATIVE specification. Implementation must conform exactly.
    Any deviation is a contract violation.
    """
    
    # Identity
    node_type: str = Field(..., description="Node type identifier")
    version: str = Field(..., description="Node version (semver)")
    semantic_class: str = Field(..., description="Semantic class (http_rest, tcp_client, etc.)")
    
    # Contract schemas
    input_schema: InputContractSchema = Field(..., description="Input contract")
    output_schema: OutputContractSchema = Field(..., description="Output contract")
    
    # Error handling
    error_categories: List[ErrorCategory] = Field(
        default_factory=list,
        description="Normalized error categories this node can produce"
    )
    
    # Side-effects and security
    side_effects: SideEffectDeclaration = Field(..., description="Explicit side-effects")
    credential_scope: Optional[CredentialScope] = Field(
        None,
        description="Credential requirements and security scope"
    )
    
    # Execution behavior
    execution_semantics: ExecutionSemantics = Field(..., description="Execution constraints")
    
    # n8n compatibility
    n8n_normalization: N8nSemanticNormalization = Field(
        ..., 
        description="n8n semantic normalization"
    )
    
    # Metadata
    generated_by: str = Field(..., description="Generator identifier")
    correlation_id: str = Field(..., description="Generation correlation ID")
    generated_at: str = Field(..., description="Generation timestamp (ISO 8601)")
    
    @model_validator(mode="after")
    def validate_contract_completeness(self) -> "NodeContract":
        """Validate contract meets minimum completeness requirements."""
        
        # Hard-fail: Must have at least one input or be a trigger
        if not self.input_schema.fields and "trigger" not in self.node_type.lower():
            raise ValueError("HARD-FAIL: Non-trigger nodes must have at least one input field")
        
        # Hard-fail: Must have output schema
        if not self.output_schema.success_fields:
            raise ValueError("HARD-FAIL: Must define success output fields")
        
        # Hard-fail: Side-effects must match semantic class
        if self.semantic_class == "tcp_client":
            if SideEffectType.DATABASE not in self.side_effects.types:
                raise ValueError("HARD-FAIL: tcp_client nodes must declare DATABASE side-effect")
        
        if self.semantic_class == "http_rest":
            if SideEffectType.NETWORK not in self.side_effects.types:
                raise ValueError("HARD-FAIL: http_rest nodes must declare NETWORK side-effect")
        
        # Hard-fail: Credential scope required for nodes with network/database side-effects
        if (SideEffectType.NETWORK in self.side_effects.types or 
            SideEffectType.DATABASE in self.side_effects.types):
            if self.credential_scope is None:
                raise ValueError(
                    "HARD-FAIL: Nodes with NETWORK or DATABASE side-effects must declare credential_scope"
                )
        
        return self


class ContractValidationResult(BaseModel):
    """Result of contract validation with scoring."""
    valid: bool = Field(..., description="Whether contract passes hard-fail checks")
    score: int = Field(..., ge=0, le=100, description="Correctness score (0-100)")
    acceptable: bool = Field(..., description="Whether score >= 80")
    
    # Scoring breakdown
    contract_completeness_score: int = Field(..., ge=0, le=40)
    side_effects_score: int = Field(..., ge=0, le=25)
    execution_semantics_score: int = Field(..., ge=0, le=25)
    n8n_normalization_score: int = Field(..., ge=0, le=10)
    
    # Validation details
    hard_fail_violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


def validate_contract(contract: NodeContract) -> ContractValidationResult:
    """
    Validate a node contract and compute correctness score.
    
    Returns validation result with score breakdown.
    If score < 80, node is mechanically rejected.
    """
    hard_fails: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = []
    
    # Will be computed
    contract_score = 0
    side_effects_score = 0
    execution_score = 0
    n8n_score = 0
    
    # Contract completeness (40 pts)
    # Input schema complete & strict (15)
    if contract.input_schema.fields:
        contract_score += 7
        if contract.input_schema.strict:
            contract_score += 3
        if not contract.input_schema.additional_properties:
            contract_score += 5
    else:
        warnings.append("No input fields defined")
    
    # Output schema complete & strict (15)
    if contract.output_schema.success_fields:
        contract_score += 7
        if contract.output_schema.error_fields:
            contract_score += 5
        if contract.output_schema.deterministic:
            contract_score += 3
    else:
        hard_fails.append("No success output fields defined")
    
    # Error contract normalized (10)
    if contract.error_categories:
        contract_score += 7
        if len(contract.error_categories) >= 3:
            contract_score += 3
    else:
        warnings.append("No error categories defined")
    
    # Side-effects & credentials (25 pts)
    # Side-effects explicitly declared (15)
    if contract.side_effects.types:
        side_effects_score += 10
        if SideEffectType.NONE not in contract.side_effects.types:
            # Has real side-effects
            if (SideEffectType.NETWORK in contract.side_effects.types and 
                contract.side_effects.network_destinations):
                side_effects_score += 3
            if (SideEffectType.DATABASE in contract.side_effects.types and
                contract.side_effects.database_operations):
                side_effects_score += 2
    else:
        hard_fails.append("No side-effects declared")
    
    # Credential scope + allowlists (10)
    if contract.credential_scope:
        side_effects_score += 5
        if (contract.credential_scope.host_allowlist or 
            contract.credential_scope.database_allowlist or
            contract.credential_scope.path_allowlist):
            side_effects_score += 5
    elif SideEffectType.NONE not in contract.side_effects.types:
        warnings.append("No credential scope defined for node with side-effects")
    
    # Execution semantics (25 pts)
    # Hard timeout enforced (10)
    if 1 <= contract.execution_semantics.timeout_seconds <= 300:
        execution_score += 10
    else:
        hard_fails.append(f"Invalid timeout: {contract.execution_semantics.timeout_seconds}")
    
    # Retry rules consistent with idempotency (10)
    if contract.execution_semantics.max_retries > 0:
        if contract.execution_semantics.idempotent:
            execution_score += 10
        else:
            hard_fails.append("max_retries > 0 but idempotent=False")
    else:
        execution_score += 10  # No retries is safe
    
    # Deterministic failure categories (5)
    if contract.error_categories:
        execution_score += 5
    
    # n8n semantic normalization (10 pts)
    # Defaults explicit (5)
    if contract.n8n_normalization.defaults_explicit:
        n8n_score += 5
    else:
        warnings.append("n8n defaults not made explicit")
    
    # Expression/eval boundaries explicit (5)
    if contract.n8n_normalization.expression_boundaries is not None:
        n8n_score += 5
    else:
        recommendations.append("Consider documenting expression boundaries")
    
    total_score = contract_score + side_effects_score + execution_score + n8n_score
    
    return ContractValidationResult(
        valid=len(hard_fails) == 0,
        score=total_score,
        acceptable=total_score >= 80 and len(hard_fails) == 0,
        contract_completeness_score=contract_score,
        side_effects_score=side_effects_score,
        execution_semantics_score=execution_score,
        n8n_normalization_score=n8n_score,
        hard_fail_violations=hard_fails,
        warnings=warnings,
        recommendations=recommendations
    )
