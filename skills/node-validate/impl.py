"""
Node Validate Skill Implementation

Validates packaged node artifacts before apply-changes.
Runs syntax check, import test, and optional linting.
"""

from __future__ import annotations

import ast
import json
import py_compile
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext


def _check_syntax(file_path: Path) -> tuple[bool, str]:
    """Check Python file syntax using py_compile."""
    try:
        py_compile.compile(str(file_path), doraise=True)
        return True, "Syntax valid"
    except py_compile.PyCompileError as e:
        return False, f"Syntax error: {e}"


def _check_ast(file_path: Path) -> tuple[bool, str, ast.Module | None]:
    """Parse AST and return tree if successful."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
        return True, "AST parsed successfully", tree
    except SyntaxError as e:
        return False, f"AST parse error at line {e.lineno}: {e.msg}", None


def _check_imports(tree: ast.Module) -> tuple[bool, str, list[str]]:
    """Check imports can be parsed (not executed)."""
    imports = []
    issues = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    
    # Check for known problematic async imports
    async_imports = {"aiohttp", "aiofiles", "asyncio"}
    found_async = [imp for imp in imports if imp in async_imports]
    
    if found_async:
        issues.append(f"Async imports detected (sync Celery constraint violation): {found_async}")
    
    if issues:
        return False, "; ".join(issues), imports
    
    return True, f"Found {len(imports)} imports", imports


def _check_node_class(tree: ast.Module) -> tuple[bool, str, dict[str, Any]]:
    """Check for valid node class definition."""
    class_info: dict[str, Any] = {
        "class_name": None,
        "base_classes": [],
        "has_type_attr": False,
        "has_execute": False,
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if this looks like a node class
            if node.name.endswith("Node") or "BaseNode" in [
                getattr(base, "id", getattr(base, "attr", "")) for base in node.bases
            ]:
                class_info["class_name"] = node.name
                class_info["base_classes"] = [
                    getattr(base, "id", getattr(base, "attr", "")) for base in node.bases
                ]
                
                # Check for type attribute and execute method
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if getattr(target, "id", "") == "type":
                                class_info["has_type_attr"] = True
                    elif isinstance(item, ast.FunctionDef):
                        if item.name == "execute":
                            class_info["has_execute"] = True
                
                break
    
    if not class_info["class_name"]:
        return False, "No node class found (expected class ending in 'Node' or inheriting BaseNode)", class_info
    
    issues = []
    if not class_info["has_type_attr"]:
        issues.append("Missing 'type' class attribute")
    if not class_info["has_execute"]:
        issues.append("Missing 'execute' method")
    
    if issues:
        return False, f"Node class '{class_info['class_name']}' issues: {'; '.join(issues)}", class_info
    
    return True, f"Valid node class: {class_info['class_name']}", class_info


def _check_async_patterns(file_path: Path) -> tuple[bool, str]:
    """Check for async/await patterns that violate sync Celery constraint."""
    content = file_path.read_text()
    
    # Patterns to detect
    patterns = [
        (r"\basync\s+def\b", "async def function"),
        (r"\bawait\b", "await expression"),
        (r"\basyncio\.", "asyncio usage"),
        (r"\baiohttp\.", "aiohttp usage"),
        (r"\basync\s+with\b", "async context manager"),
        (r"\basync\s+for\b", "async for loop"),
    ]
    
    violations = []
    for pattern, desc in patterns:
        if re.search(pattern, content):
            violations.append(desc)
    
    if violations:
        return False, f"Async patterns detected (sync Celery violation): {', '.join(violations)}"
    
    return True, "No async patterns detected"


def _check_timeout_on_requests(tree: ast.Module) -> tuple[bool, str]:
    """Check that HTTP requests have timeout parameters."""
    issues = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            
            # Check for HTTP call methods
            if func_name in ("get", "post", "put", "delete", "patch", "request"):
                # Look for timeout keyword argument
                has_timeout = any(
                    kw.arg == "timeout" for kw in node.keywords
                )
                if not has_timeout:
                    # Get line number for context
                    issues.append(f"HTTP call '{func_name}' at line {node.lineno} missing timeout")
    
    if issues:
        return False, "; ".join(issues)
    
    return True, "All HTTP calls have timeouts or no HTTP calls detected"


# =============================================================================
# NEW VALIDATION CHECKS (Pipeline Safety Gates)
# =============================================================================

def _check_not_implemented(tree: ast.Module, file_path: Path) -> tuple[bool, str, list[int]]:
    """
    Check for NotImplementedError raises - indicates unfinished operations.
    
    A shippable node must not have any NotImplementedError.
    """
    issues = []
    lines = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            # Check if raising NotImplementedError
            if isinstance(node.exc, ast.Call):
                if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "NotImplementedError":
                    issues.append(f"NotImplementedError at line {node.lineno}")
                    lines.append(node.lineno)
            elif isinstance(node.exc, ast.Name) and node.exc.id == "NotImplementedError":
                issues.append(f"NotImplementedError at line {node.lineno}")
                lines.append(node.lineno)
    
    # Also check for TODO markers in comments (string scan)
    content = file_path.read_text()
    for i, line in enumerate(content.splitlines(), 1):
        if "TODO: Implement" in line or "TODO: Extract parameters" in line:
            issues.append(f"TODO marker at line {i}")
            lines.append(i)
    
    if issues:
        return False, f"Unimplemented operations: {'; '.join(issues)}", lines
    
    return True, "No NotImplementedError found", []


def _check_placeholder_urls(file_path: Path) -> tuple[bool, str, list[int]]:
    """
    Check for placeholder URLs that indicate incomplete conversion.
    
    Reject:
    - api.example.com
    - /endpoint (as a literal string placeholder)
    """
    issues = []
    lines = []
    content = file_path.read_text()
    
    placeholder_patterns = [
        (r'api\.example\.com', "Placeholder URL 'api.example.com'"),
        (r'["\']\/endpoint["\']', "Placeholder endpoint '/endpoint'"),
    ]
    
    for i, line in enumerate(content.splitlines(), 1):
        for pattern, desc in placeholder_patterns:
            if re.search(pattern, line):
                issues.append(f"{desc} at line {i}")
                lines.append(i)
    
    if issues:
        return False, f"Placeholder URLs detected: {'; '.join(issues)}", lines
    
    return True, "No placeholder URLs found", []


def _check_resource_dispatch(tree: ast.Module, file_path: Path) -> tuple[bool, str]:
    """
    Check that nodes with resource parameter use resource+operation dispatch.
    
    If properties contain both 'resource' and 'operation' parameters,
    the execute() method must read both and dispatch on the tuple.
    """
    content = file_path.read_text()
    
    # Check if this node has a resource parameter
    has_resource_param = bool(re.search(r'"name":\s*"resource"', content))
    has_operation_param = bool(re.search(r'"name":\s*"operation"', content))
    
    if not has_resource_param or not has_operation_param:
        # Not a multi-resource node, skip this check
        return True, "Not a multi-resource node (skipped)"
    
    # Find the execute method and check if it reads resource
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "execute":
            # Check if execute() calls get_node_parameter("resource", ...)
            has_resource_read = False
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute):
                        if child.func.attr == "get_node_parameter":
                            # Check first argument is "resource"
                            if child.args and isinstance(child.args[0], ast.Constant):
                                if child.args[0].value == "resource":
                                    has_resource_read = True
                                    break
            
            if not has_resource_read:
                return False, "Multi-resource node but execute() does not read 'resource' parameter - dispatch will be ambiguous"
    
    return True, "Resource+operation dispatch pattern detected"


def _check_continue_on_fail(file_path: Path) -> tuple[bool, str, list[int]]:
    """
    Check that continue_on_fail is accessed correctly.
    
    BaseNode pattern: self.node_data.continue_on_fail
    Wrong pattern: self.continue_on_fail (attribute doesn't exist)
    """
    issues = []
    lines = []
    content = file_path.read_text()
    
    for i, line in enumerate(content.splitlines(), 1):
        # Match self.continue_on_fail but NOT self.node_data.continue_on_fail
        if re.search(r'self\.continue_on_fail(?!\s*=)', line):
            if 'self.node_data.continue_on_fail' not in line:
                issues.append(f"Wrong continue_on_fail access at line {i}")
                lines.append(i)
    
    if issues:
        return False, f"Invalid continue_on_fail access (use self.node_data.continue_on_fail): {'; '.join(issues)}", lines
    
    return True, "continue_on_fail access pattern correct or not used", []


def _check_duplicate_methods(tree: ast.Module) -> tuple[bool, str, list[str]]:
    """
    Check for duplicate method definitions in the class.
    
    Python allows redefining methods but only the last definition is used.
    This often indicates generator bugs with multi-resource nodes.
    """
    method_names = []
    duplicates = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    if item.name in method_names:
                        duplicates.append(item.name)
                    else:
                        method_names.append(item.name)
    
    if duplicates:
        return False, f"Duplicate method definitions (generator bug): {', '.join(set(duplicates))}", list(set(duplicates))
    
    return True, "No duplicate methods", []


def _check_missing_helpers(tree: ast.Module, file_path: Path) -> tuple[bool, str, list[str]]:
    """
    Check for helper methods called but not defined.
    
    Common generator bug: code references _api_request_all_items but doesn't generate it.
    """
    # Collect all method definitions
    defined_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    defined_methods.add(item.name)
    
    # Collect all method calls to self.*
    called_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                    called_methods.add(node.func.attr)
    
    # Check for missing helpers
    missing = []
    # Common helper patterns
    helper_patterns = ["_api_request_all_items", "_api_request", "_http_request", "_oauth2_request"]
    
    for method in called_methods:
        if method.startswith("_") and method not in defined_methods:
            # Check if it's a known helper that should exist
            if any(pattern in method for pattern in helper_patterns):
                missing.append(method)
    
    if missing:
        return False, f"Helper methods called but not defined: {', '.join(missing)}", missing
    
    return True, "All referenced helpers are defined", []


def _check_hardcoded_repos(file_path: Path) -> tuple[bool, str, list[int]]:
    """
    Check for hardcoded test repo names in base URLs.
    
    Rejects: /repos/test-owner/test-repo, /repos/example-org/
    Allows: f"/repos/{owner}/{repo}" (Python f-string variables)
    """
    issues = []
    lines_found = []
    content = file_path.read_text()
    
    patterns = [
        (r'/repos/test-owner/test-repo', "Hardcoded test-owner/test-repo"),
        (r'/repos/example-org/', "Hardcoded example-org"),
    ]
    
    for i, line in enumerate(content.splitlines(), 1):
        # Skip Python f-strings with variables (they're OK)
        if 'f"' in line or "f'" in line:
            # This line uses f-string, likely with variables - skip
            continue
        
        for pattern, desc in patterns:
            if re.search(pattern, line):
                issues.append(f"{desc} at line {i}")
                lines_found.append(i)
    
    if issues:
        return False, f"Hardcoded repo names in URL: {'; '.join(issues)}", lines_found
    
    return True, "No hardcoded repo names found", []


def _check_wrong_auth_scheme(file_path: Path) -> tuple[bool, str, list[int]]:
    """
    Check for wrong authentication schemes.
    
    GitHub: should use "Bearer {token}" or "token {token}", NOT "Bot {token}"
    """
    issues = []
    lines_found = []
    content = file_path.read_text()
    
    # Check for wrong patterns
    wrong_patterns = [
        (r'"Bot\s+\{', "Wrong GitHub auth: 'Bot' prefix (should be 'Bearer')"),
        (r"'Bot\s+\{", "Wrong GitHub auth: 'Bot' prefix (should be 'Bearer')"),
    ]
    
    for i, line in enumerate(content.splitlines(), 1):
        for pattern, desc in wrong_patterns:
            if re.search(pattern, line):
                issues.append(f"{desc} at line {i}")
                lines_found.append(i)
    
    if issues:
        return False, f"Wrong authentication scheme: {'; '.join(issues)}", lines_found
    
    return True, "Authentication scheme looks correct", []


def _check_returnall_pagination(tree: ast.Module, file_path: Path) -> tuple[bool, str, list[str]]:
    """
    Check that returnAll parameter has corresponding pagination helper.
    
    If properties contain returnAll=True parameter, node must have _api_request_all_items.
    """
    content = file_path.read_text()
    
    # Check if returnAll parameter exists
    has_return_all = bool(re.search(r'"returnAll"', content) or re.search(r"'returnAll'", content))
    
    if not has_return_all:
        return True, "No returnAll parameter (pagination not needed)", []
    
    # Check for pagination helper
    has_pagination_helper = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if "all_items" in node.name.lower() or "paginate" in node.name.lower():
                has_pagination_helper = True
                break
    
    if not has_pagination_helper:
        return False, "returnAll parameter exists but no pagination helper found (_api_request_all_items missing)", ["_api_request_all_items"]
    
    return True, "returnAll parameter has pagination helper", []


def _check_phantom_operations(tree: ast.Module, file_path: Path) -> tuple[bool, str, list[str]]:
    """
    Check for operations in UI that are not implemented in execute().
    
    Scans properties.parameters for operation options, then verifies each is handled.
    """
    content = file_path.read_text()
    
    # Extract operation values from properties
    operation_values = []
    operation_pattern = r'"value":\s*"([^"]+)"'
    
    # Find properties section
    props_match = re.search(r'properties\s*=\s*\{.*?"parameters":', content, re.DOTALL)
    if props_match:
        # Extract operation options
        ops_match = re.search(r'"name":\s*"operation".*?"options":\s*\[(.*?)\]', content[props_match.end():], re.DOTALL)
        if ops_match:
            ops_text = ops_match.group(1)
            operation_values = re.findall(operation_pattern, ops_text)
    
    if not operation_values:
        return True, "No operation parameter found", []
    
    # Find execute method and check for resource/operation dispatch
    unimplemented = []
    for op_value in operation_values:
        # Check if operation is handled in execute()
        # Look for elif/if statements checking operation == op_value
        op_check_pattern = rf'operation\s*==\s*["\']({re.escape(op_value)})["\']'
        if not re.search(op_check_pattern, content):
            unimplemented.append(op_value)
    
    if unimplemented:
        return False, f"Operations in UI but not implemented: {', '.join(unimplemented)}", unimplemented
    
    return True, "All operations are implemented", []


def _check_body_in_write_operations(tree: ast.Module, file_path: Path) -> tuple[bool, str, list[int]]:
    """
    Check that write operations (POST/PUT/PATCH) pass body parameter.
    
    Common bug: code extracts parameters but passes body=None to _api_request.
    """
    issues = []
    lines_found = []
    content = file_path.read_text()
    
    # Find operation handlers
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check if this is an operation handler (e.g., _issue_create)
            if node.name.startswith("_") and any(op in node.name.lower() for op in ["create", "edit", "update", "post", "put"]):
                # Check if function calls _api_request with method POST/PUT/PATCH
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute) and child.func.attr in ["_api_request", "_http_request"]:
                            # Check first argument (method)
                            if child.args and isinstance(child.args[0], ast.Constant):
                                method = child.args[0].value
                                if method in ("POST", "PUT", "PATCH"):
                                    # Check if body keyword is None or missing
                                    body_kwarg = None
                                    for kw in child.keywords:
                                        if kw.arg == "body":
                                            body_kwarg = kw.value
                                            break
                                    
                                    if body_kwarg is None or (isinstance(body_kwarg, ast.Constant) and body_kwarg.value is None):
                                        issues.append(f"Write operation {node.name} calls {method} but body=None (line {child.lineno})")
                                        lines_found.append(child.lineno)
    
    if issues:
        return False, f"Write operations missing body: {'; '.join(issues)}", lines_found
    
    return True, "Write operations include body parameters", []


def _check_generic_credential_names(file_path: Path) -> tuple[bool, str, list[int]]:
    """
    Check for generic credential names like 'oauth2', 'api', 'apiCredentials'.
    
    Credentials should be service-specific: githubApi, slackOAuth2, etc.
    """
    issues = []
    lines_found = []
    content = file_path.read_text()
    
    # Find get_credentials calls
    generic_patterns = [
        (r'get_credentials\(["\']oauth2["\']\)', "Generic credential 'oauth2' (should be service-specific like 'githubOAuth2Api')"),
        (r'get_credentials\(["\']api["\']\)', "Generic credential 'api' (should be service-specific)"),
        (r'get_credentials\(["\']apiCredentials["\']\)', "Generic credential 'apiCredentials' (should be service-specific)"),
    ]
    
    for i, line in enumerate(content.splitlines(), 1):
        for pattern, desc in generic_patterns:
            if re.search(pattern, line):
                issues.append(f"{desc} at line {i}")
                lines_found.append(i)
    
    if issues:
        return False, f"Generic credential names detected: {'; '.join(issues)}", lines_found
    
    return True, "Credentials use service-specific names", []


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """
    Validate packaged node artifacts before apply-changes.
    
    Reads from artifacts/{correlation_id}/package/
    Writes results to artifacts/{correlation_id}/validation/
    """
    inputs = ctx.inputs
    correlation_id = inputs["correlation_id"]
    skip_lint = inputs.get("skip_lint", False)
    
    ctx.log("node_validate_start", {"correlation_id": correlation_id})
    
    # Get paths
    artifacts_dir = ctx.artifacts_dir
    package_dir = artifacts_dir / "package"
    validation_dir = artifacts_dir / "validation"
    
    # Validate package directory exists
    if not package_dir.exists():
        ctx.log("missing_package_dir", {"path": str(package_dir)})
        return {
            "valid": False,
            "checks": [],
            "errors": [f"Package directory not found: {package_dir}"],
            "warnings": [],
        }
    
    # Create validation directory
    validation_dir.mkdir(parents=True, exist_ok=True)
    
    # Find Python files (excluding manifest and registry_entry)
    py_files = [f for f in package_dir.glob("*.py")]
    
    if not py_files:
        return {
            "valid": False,
            "checks": [],
            "errors": ["No Python files found in package"],
            "warnings": [],
        }
    
    # Run checks
    all_checks = []
    all_errors = []
    all_warnings = []
    overall_valid = True
    
    for py_file in py_files:
        is_test = py_file.name.startswith("test_")
        file_prefix = f"[{py_file.name}]"
        
        # 1. Syntax check
        passed, details = _check_syntax(py_file)
        all_checks.append({
            "name": f"{file_prefix} Syntax",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
            continue  # Skip other checks if syntax fails
        
        # 2. AST check
        passed, details, tree = _check_ast(py_file)
        all_checks.append({
            "name": f"{file_prefix} AST",
            "passed": passed,
            "details": details,
        })
        if not passed or tree is None:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
            continue
        
        # 3. Import check
        passed, details, imports = _check_imports(tree)
        all_checks.append({
            "name": f"{file_prefix} Imports",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 4. Async patterns check (critical for sync Celery)
        passed, details = _check_async_patterns(py_file)
        all_checks.append({
            "name": f"{file_prefix} Sync Celery",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # Skip remaining checks for test files
        if is_test:
            continue
        
        # 5. Node class check (for non-test files)
        passed, details, class_info = _check_node_class(tree)
        all_checks.append({
            "name": f"{file_prefix} Node Class",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 6. Timeout check - NOW AN ERROR, NOT WARNING
        passed, details = _check_timeout_on_requests(tree)
        all_checks.append({
            "name": f"{file_prefix} Timeouts",
            "passed": passed,
            "details": details,
        })
        if not passed:
            # Timeout missing is now an error (Celery requirement)
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # =====================================================================
        # NEW PIPELINE SAFETY CHECKS
        # =====================================================================
        
        # 7. NotImplementedError check - reject unfinished operations
        passed, details, _ = _check_not_implemented(tree, py_file)
        all_checks.append({
            "name": f"{file_prefix} NotImplementedError",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 8. Placeholder URLs check - reject api.example.com, /endpoint
        passed, details, _ = _check_placeholder_urls(py_file)
        all_checks.append({
            "name": f"{file_prefix} Placeholder URLs",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 9. Resource dispatch check - multi-resource nodes must read resource
        passed, details = _check_resource_dispatch(tree, py_file)
        all_checks.append({
            "name": f"{file_prefix} Resource Dispatch",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 10. continue_on_fail access pattern check
        passed, details, _ = _check_continue_on_fail(py_file)
        all_checks.append({
            "name": f"{file_prefix} continue_on_fail Pattern",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 11. Duplicate methods check - catch generator bugs
        passed, details, _ = _check_duplicate_methods(tree)
        all_checks.append({
            "name": f"{file_prefix} Duplicate Methods",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 12. Missing helpers check - referenced but not defined
        passed, details, _ = _check_missing_helpers(tree, py_file)
        all_checks.append({
            "name": f"{file_prefix} Missing Helpers",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 13. Hardcoded repo names check - test-owner/test-repo in URLs
        passed, details, _ = _check_hardcoded_repos(py_file)
        all_checks.append({
            "name": f"{file_prefix} Hardcoded Repos",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 14. Wrong auth scheme check - "Bot" instead of "Bearer"
        passed, details, _ = _check_wrong_auth_scheme(py_file)
        all_checks.append({
            "name": f"{file_prefix} Auth Scheme",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 15. returnAll pagination check - returnAll needs helper
        passed, details, _ = _check_returnall_pagination(tree, py_file)
        all_checks.append({
            "name": f"{file_prefix} Pagination",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 16. Phantom operations check - UI lists operations not in execute()
        passed, details, _ = _check_phantom_operations(tree, py_file)
        all_checks.append({
            "name": f"{file_prefix} Phantom Operations",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 17. Write operations body check - POST/PUT must pass body
        passed, details, _ = _check_body_in_write_operations(tree, py_file)
        all_checks.append({
            "name": f"{file_prefix} Write Op Bodies",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
        
        # 18. Generic credential names check - oauth2 should be service-specific
        passed, details, _ = _check_generic_credential_names(py_file)
        all_checks.append({
            "name": f"{file_prefix} Credential Names",
            "passed": passed,
            "details": details,
        })
        if not passed:
            overall_valid = False
            all_errors.append(f"{file_prefix} {details}")
    
    # Write results
    results = {
        "correlation_id": correlation_id,
        "valid": overall_valid,
        "checks": all_checks,
        "errors": all_errors,
        "warnings": all_warnings,
        "files_checked": [str(f.name) for f in py_files],
    }
    
    results_path = validation_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2))
    
    ctx.log("node_validate_complete", {
        "valid": overall_valid,
        "checks_count": len(all_checks),
        "errors_count": len(all_errors),
        "warnings_count": len(all_warnings),
    })
    
    return {
        "valid": overall_valid,
        "checks": all_checks,
        "errors": all_errors,
        "warnings": all_warnings,
    }
