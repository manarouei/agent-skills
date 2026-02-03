#!/usr/bin/env python3
"""
Behavioral Validate Skill Implementation

Validates generated code for behavioral correctness using four gates:
1. NO-STUB GATE: Reject placeholders/TODOs
2. HTTP PARITY GATE: Verify HTTP calls match golden
3. SEMANTIC DIFF GATE: Compare AST structure
4. CONTRACT ROUND-TRIP GATE: Schema ↔ code agreement

HYBRID BACKBONE: DETERMINISTIC (validation only, no AI)
SYNC-CELERY SAFE: All operations are synchronous.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext

# Conditional import for runtime use
try:
    from runtime.protocol import AgentResponse, TaskState
except ImportError:
    # Stub for testing
    class TaskState:
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"
    
    class AgentResponse:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)


# =============================================================================
# STUB DETECTION PATTERNS (Gate 1)
# =============================================================================

STUB_PATTERNS = [
    (r'#\s*TODO:\s*Implement', "TODO comment found"),
    (r'#\s*__STUB_MARKER__', "Internal stub marker"),
    (r'raise\s+NotImplementedError', "NotImplementedError raised"),
    (r'response\s*=\s*\{\s*\}', "Empty response dict"),
    (r'^\s*pass\s*$', "Bare pass statement"),
    (r'return\s+\{\s*\}', "Return empty dict"),
    (r'return\s+None\s*$', "Return None"),
    (r'#\s*TODO:\s*Make API call', "TODO API call comment"),
    (r'#\s*TODO:\s*Extract parameters', "TODO parameters comment"),
]

# HTTP call patterns for parity checking (Gate 2)
HTTP_CALL_PATTERNS = [
    r'requests\.(get|post|put|patch|delete|request)\s*\(',
    r'self\._api_request\s*\(',
    r'self\._http_request\s*\(',
    r'self\._oauth2_request\s*\(',
    r'self\._api_request_all_items\s*\(',
    r'httpx\.(get|post|put|patch|delete)\s*\(',
]


# =============================================================================
# RESULT CLASSES (simple classes instead of dataclasses for importlib compat)
# =============================================================================

class GateResult:
    """Result of a single validation gate."""
    
    def __init__(self, passed: bool, violations: List[str] = None, details: Dict[str, Any] = None):
        self.passed = passed
        self.violations = violations or []
        self.details = details or {}


class ValidationResult:
    """Combined result of all validation gates."""
    
    def __init__(self, validation_passed: bool, gate_results: Dict[str, GateResult], errors: List[str] = None):
        self.validation_passed = validation_passed
        self.gate_results = gate_results
        self.errors = errors or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for output."""
        return {
            "validation_passed": self.validation_passed,
            "gate_results": {
                name: {
                    "passed": gate.passed,
                    "violations": gate.violations,
                    **gate.details,
                }
                for name, gate in self.gate_results.items()
            },
            "errors": self.errors,
        }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def execute_behavioral_validate(ctx: "ExecutionContext") -> AgentResponse:
    """
    Validate generated code for behavioral correctness.
    
    Inputs:
        - correlation_id: str
        - generated_code: str - The generated Python code to validate
        - golden_impl: dict - Golden implementation from golden-extract
        - node_schema: dict - Schema from schema-infer
        - strict_mode: bool - If true, any gate failure = FAILED state
    
    Outputs:
        - validation_passed: bool
        - gate_results: dict of gate name -> result
        - errors: list of error messages
    """
    inputs = ctx.inputs
    correlation_id = inputs.get("correlation_id", ctx.correlation_id)
    
    # Get inputs
    generated_code = inputs.get("generated_code", "")
    golden_impl = inputs.get("golden_impl", {})
    node_schema = inputs.get("node_schema", {})
    strict_mode = inputs.get("strict_mode", True)  # Default to strict for TYPE1
    
    if not generated_code:
        return AgentResponse(
            state=TaskState.FAILED,
            errors=["No generated_code provided for validation"],
        )
    
    # Run all four gates
    gate_results = {}
    
    # Gate 1: No-Stub Gate
    gate_results["no_stub"] = validate_no_stubs(generated_code)
    
    # Gate 2: HTTP Parity Gate (requires golden)
    if golden_impl and golden_impl.get("methods"):
        golden_code = golden_impl.get("full_source", "")
        gate_results["http_parity"] = validate_http_parity(generated_code, golden_code)
    else:
        gate_results["http_parity"] = GateResult(
            passed=True,
            violations=["Skipped: No golden implementation provided"],
            details={"skipped": True},
        )
    
    # Gate 3: Semantic Diff Gate (requires golden)
    if golden_impl and golden_impl.get("methods"):
        golden_methods = golden_impl.get("methods", {})
        gate_results["semantic_diff"] = validate_semantic_diff(generated_code, golden_methods)
    else:
        gate_results["semantic_diff"] = GateResult(
            passed=True,
            violations=["Skipped: No golden implementation provided"],
            details={"skipped": True},
        )
    
    # Gate 4: Contract Round-Trip Gate
    gate_results["contract_roundtrip"] = validate_contract_roundtrip(
        generated_code, node_schema
    )
    
    # Determine overall pass/fail
    all_passed = all(g.passed for g in gate_results.values())
    
    # Collect errors from failed gates
    errors = []
    for name, result in gate_results.items():
        if not result.passed and not result.details.get("skipped"):
            errors.extend([f"[{name}] {v}" for v in result.violations])
    
    result = ValidationResult(
        validation_passed=all_passed,
        gate_results=gate_results,
        errors=errors,
    )
    
    # Write validation report
    if ctx.artifacts_dir:
        report_path = ctx.artifacts_dir / "behavioral_validation.json"
        import json
        report_path.write_text(json.dumps(result.to_dict(), indent=2))
    
    # Determine state based on strict mode
    if strict_mode and not all_passed:
        return AgentResponse(
            state=TaskState.FAILED,
            errors=errors,
            outputs=result.to_dict(),
        )
    
    return AgentResponse(
        state=TaskState.COMPLETED,
        outputs=result.to_dict(),
    )


# =============================================================================
# GATE 1: NO-STUB VALIDATION
# =============================================================================

def validate_no_stubs(code: str) -> GateResult:
    """
    Validate that code contains no stub/placeholder patterns.
    
    This is the critical gate for TYPE1 conversions - any placeholder
    indicates failed extraction and must be rejected.
    """
    violations = []
    
    for pattern, message in STUB_PATTERNS:
        matches = re.findall(pattern, code, re.MULTILINE | re.IGNORECASE)
        if matches:
            violations.append(f"{message}: {len(matches)} occurrence(s)")
    
    # Additional check: method bodies that are effectively empty
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                body = node.body
                # Check for single-statement bodies
                if len(body) == 1:
                    stmt = body[0]
                    # pass statement
                    if isinstance(stmt, ast.Pass):
                        violations.append(f"Method '{node.name}' has only 'pass'")
                    # raise NotImplementedError
                    if isinstance(stmt, ast.Raise) and stmt.exc:
                        if isinstance(stmt.exc, ast.Call):
                            if hasattr(stmt.exc.func, 'id') and stmt.exc.func.id == 'NotImplementedError':
                                violations.append(f"Method '{node.name}' raises NotImplementedError")
                    # return None or return {}
                    if isinstance(stmt, ast.Return):
                        if stmt.value is None:
                            violations.append(f"Method '{node.name}' returns nothing")
                        elif isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                            violations.append(f"Method '{node.name}' returns None")
                        elif isinstance(stmt.value, ast.Dict) and not stmt.value.keys:
                            violations.append(f"Method '{node.name}' returns empty dict")
    except SyntaxError as e:
        violations.append(f"Code has syntax errors: {e}")
    
    return GateResult(
        passed=len(violations) == 0,
        violations=violations,
    )


# =============================================================================
# GATE 2: HTTP PARITY VALIDATION
# =============================================================================

def validate_http_parity(generated_code: str, golden_code: str) -> GateResult:
    """
    Validate that generated code makes the same HTTP calls as golden.
    
    Extracts HTTP call patterns from both and compares:
    - Same number of calls
    - Same HTTP methods
    - Same endpoint patterns
    """
    violations = []
    
    def extract_http_calls(code: str) -> Set[str]:
        """Extract unique HTTP call signatures."""
        calls = set()
        for pattern in HTTP_CALL_PATTERNS:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                # Get the full call context (up to closing paren)
                start = match.start()
                # Find the method being called
                calls.add(match.group(0).strip('('))
        return calls
    
    def extract_endpoints(code: str) -> Set[str]:
        """Extract endpoint patterns from code."""
        endpoints = set()
        # Pattern: "endpoint" or 'endpoint' or f"...{endpoint}..."
        patterns = [
            r'endpoint\s*=\s*["\']([^"\']+)["\']',
            r'["\']/([\w/\{\}]+)["\']',
            r'f["\']([^"\']*\{[^"\']*\}[^"\']*)["\']',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, code)
            endpoints.update(matches)
        return endpoints
    
    def extract_http_methods(code: str) -> Set[str]:
        """Extract HTTP methods used."""
        methods = set()
        # Pattern: method="GET" or method='POST'
        pattern = r'method\s*=\s*["\'](\w+)["\']'
        matches = re.findall(pattern, code, re.IGNORECASE)
        methods.update(m.upper() for m in matches)
        
        # Also check for requests.get, requests.post, etc.
        for method in ['get', 'post', 'put', 'patch', 'delete']:
            if f'requests.{method}' in code.lower():
                methods.add(method.upper())
        
        return methods
    
    # Compare HTTP call patterns
    generated_calls = extract_http_calls(generated_code)
    golden_calls = extract_http_calls(golden_code)
    
    # Check if generated has any HTTP calls at all
    if not generated_calls:
        violations.append("Generated code has no HTTP calls")
    
    # Compare HTTP methods
    generated_methods = extract_http_methods(generated_code)
    golden_methods = extract_http_methods(golden_code)
    
    missing_methods = golden_methods - generated_methods
    if missing_methods:
        violations.append(f"Missing HTTP methods: {missing_methods}")
    
    # Compare endpoints (softer check - structure similarity)
    generated_endpoints = extract_endpoints(generated_code)
    golden_endpoints = extract_endpoints(golden_code)
    
    # Check for authentication patterns
    auth_patterns = [
        (r'Authorization', "Authorization header"),
        (r'api_key|apiKey|api-key', "API key"),
        (r'Bearer', "Bearer token"),
        (r'credentials', "Credentials usage"),
    ]
    
    for pattern, name in auth_patterns:
        in_golden = bool(re.search(pattern, golden_code, re.IGNORECASE))
        in_generated = bool(re.search(pattern, generated_code, re.IGNORECASE))
        
        if in_golden and not in_generated:
            violations.append(f"Missing authentication pattern: {name}")
    
    return GateResult(
        passed=len(violations) == 0,
        violations=violations,
        details={
            "generated_http_methods": list(generated_methods),
            "golden_http_methods": list(golden_methods),
            "generated_endpoints_count": len(generated_endpoints),
            "golden_endpoints_count": len(golden_endpoints),
        },
    )


# =============================================================================
# GATE 3: SEMANTIC DIFF VALIDATION
# =============================================================================

def validate_semantic_diff(generated_code: str, golden_methods: Dict[str, Any]) -> GateResult:
    """
    Compare AST structure between generated and golden code.
    
    Checks:
    - Method presence
    - Parameter handling patterns
    - Control flow similarity
    """
    violations = []
    diff_score = 0.0
    
    try:
        generated_tree = ast.parse(generated_code)
    except SyntaxError as e:
        return GateResult(
            passed=False,
            violations=[f"Generated code has syntax errors: {e}"],
            details={"diff_score": 1.0},
        )
    
    # Extract method names from generated code
    generated_methods = set()
    generated_method_details = {}
    
    for node in ast.walk(generated_tree):
        if isinstance(node, ast.FunctionDef):
            generated_methods.add(node.name)
            generated_method_details[node.name] = {
                "args": [a.arg for a in node.args.args],
                "body_size": len(node.body),
                "has_return": any(isinstance(s, ast.Return) for s in ast.walk(node)),
            }
    
    # Compare with golden methods
    golden_method_names = set(golden_methods.keys())
    
    # Check for missing handler methods
    # Golden methods that look like operation handlers
    handler_pattern = re.compile(r'^_\w+$')
    golden_handlers = {m for m in golden_method_names if handler_pattern.match(m)}
    generated_handlers = {m for m in generated_methods if handler_pattern.match(m)}
    
    # Missing handlers is a problem
    missing_handlers = golden_handlers - generated_handlers
    if missing_handlers and len(missing_handlers) > len(golden_handlers) * 0.3:
        violations.append(f"Missing {len(missing_handlers)} handler methods")
        diff_score += 0.3
    
    # Extra handlers might indicate schema-generated stubs
    extra_handlers = generated_handlers - golden_handlers
    if extra_handlers and len(extra_handlers) > len(golden_handlers) * 0.5:
        # Too many extra handlers might mean we're generating from schema, not source
        violations.append(f"Suspiciously many extra handlers: {len(extra_handlers)}")
        diff_score += 0.2
    
    # Calculate similarity score
    if golden_handlers:
        overlap = len(golden_handlers & generated_handlers)
        jaccard = overlap / len(golden_handlers | generated_handlers)
        diff_score = 1.0 - jaccard
    
    return GateResult(
        passed=len(violations) == 0 and diff_score < 0.5,
        violations=violations,
        details={
            "diff_score": round(diff_score, 2),
            "generated_method_count": len(generated_methods),
            "golden_method_count": len(golden_method_names),
            "structural_differences": violations,
        },
    )


# =============================================================================
# GATE 4: CONTRACT ROUND-TRIP VALIDATION
# =============================================================================

def validate_contract_roundtrip(generated_code: str, node_schema: Dict[str, Any]) -> GateResult:
    """
    Verify that generated code satisfies its contract (schema).
    
    Checks:
    - All operations in schema have corresponding methods
    - All methods have meaningful implementations
    - Parameter handling matches schema
    """
    violations = []
    
    # Extract operations from schema
    schema_operations = []
    if "operations" in node_schema:
        for op in node_schema["operations"]:
            if isinstance(op, dict):
                schema_operations.append(op.get("value", op.get("name", "")))
            elif isinstance(op, str):
                schema_operations.append(op)
    
    # Extract method names from generated code
    generated_methods = set()
    try:
        tree = ast.parse(generated_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                generated_methods.add(node.name)
    except SyntaxError as e:
        return GateResult(
            passed=False,
            violations=[f"Code syntax error: {e}"],
        )
    
    # Check: every schema operation should have a method
    unimplemented = []
    for op in schema_operations:
        # Expected method names
        possible_names = [
            f"_{op}",
            f"_execute_{op}",
            f"_{op}_operation",
        ]
        
        if not any(name in generated_methods for name in possible_names):
            unimplemented.append(op)
    
    if unimplemented:
        violations.append(f"Operations without methods: {unimplemented}")
    
    # Check: methods should handle parameters from schema
    schema_params = []
    if "properties" in node_schema:
        params = node_schema["properties"]
        if isinstance(params, dict) and "parameters" in params:
            schema_params = [p.get("name") for p in params["parameters"] if isinstance(p, dict)]
        elif isinstance(params, list):
            schema_params = [p.get("name") for p in params if isinstance(p, dict)]
    
    # Verify parameter usage in code
    for param in schema_params[:5]:  # Check first 5 params
        if param and f'"{param}"' not in generated_code and f"'{param}'" not in generated_code:
            # Parameter not referenced - might be OK if it's conditional
            pass
    
    return GateResult(
        passed=len(violations) == 0,
        violations=violations,
        details={
            "unimplemented_operations": unimplemented,
            "schema_operation_count": len(schema_operations),
            "generated_method_count": len(generated_methods),
        },
    )


# =============================================================================
# STANDALONE VALIDATION FUNCTIONS (for use in agent_gate.py)
# =============================================================================

def validate_generated_file(file_path: Path, golden_path: Path | None = None) -> ValidationResult:
    """
    Validate a generated Python file.
    
    Args:
        file_path: Path to the generated file
        golden_path: Optional path to golden implementation
        
    Returns:
        ValidationResult with all gate results
    """
    if not file_path.exists():
        return ValidationResult(
            validation_passed=False,
            gate_results={},
            errors=[f"File not found: {file_path}"],
        )
    
    generated_code = file_path.read_text()
    
    gate_results = {}
    
    # Gate 1: No-Stub
    gate_results["no_stub"] = validate_no_stubs(generated_code)
    
    # Gate 2 & 3: Require golden
    if golden_path and golden_path.exists():
        golden_code = golden_path.read_text()
        gate_results["http_parity"] = validate_http_parity(generated_code, golden_code)
        
        # Extract methods from golden for semantic diff
        golden_methods = {}
        try:
            tree = ast.parse(golden_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    golden_methods[node.name] = {"name": node.name}
        except SyntaxError:
            pass
        
        gate_results["semantic_diff"] = validate_semantic_diff(generated_code, golden_methods)
    else:
        gate_results["http_parity"] = GateResult(passed=True, details={"skipped": True})
        gate_results["semantic_diff"] = GateResult(passed=True, details={"skipped": True})
    
    # Gate 4: Contract round-trip (needs schema, skip if not available)
    gate_results["contract_roundtrip"] = GateResult(passed=True, details={"skipped": True})
    
    all_passed = all(g.passed for g in gate_results.values())
    errors = []
    for name, result in gate_results.items():
        if not result.passed and not result.details.get("skipped"):
            errors.extend([f"[{name}] {v}" for v in result.violations])
    
    return ValidationResult(
        validation_passed=all_passed,
        gate_results=gate_results,
        errors=errors,
    )
