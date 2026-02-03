"""
Behavioral Validate Skill

Validates generated code for behavioral correctness, not just syntactic validity.
Implements the four behavioral gates:
1. NO-STUB GATE: Reject any TODO/placeholder/NotImplementedError patterns
2. HTTP PARITY GATE: Verify HTTP calls match golden implementation
3. SEMANTIC DIFF GATE: Compare AST structure with golden
4. CONTRACT ROUND-TRIP GATE: Verify contract -> code -> contract cycle

HYBRID BACKBONE: DETERMINISTIC (validation only, no AI)
SYNC-CELERY SAFE: All operations are synchronous.
"""

from .impl import (
    execute_behavioral_validate,
    validate_no_stubs,
    validate_http_parity,
    validate_semantic_diff,
    validate_contract_roundtrip,
)

__all__ = [
    "execute_behavioral_validate",
    "validate_no_stubs",
    "validate_http_parity",
    "validate_semantic_diff",
    "validate_contract_roundtrip",
]
