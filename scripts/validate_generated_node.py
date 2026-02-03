#!/usr/bin/env python3
"""
Validator for generated Python node files.

Catches critical runtime blockers that should never pass the pipeline:
1. Missing method references (_api_request_all_items called but not defined)
2. Hardcoded placeholder values (test-owner, example.com, etc.)
3. Wrong auth schemes (Bot instead of Bearer for GitHub/GitLab)
4. Operation options without execute() routing
5. Body parameters read but not passed to request
6. Credentials mismatch (declares oauth2, uses githubApi)
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple, Set


class NodeValidationError(Exception):
    """Validation error with severity."""
    
    def __init__(self, message: str, severity: str = "error", line: int = None):
        self.message = message
        self.severity = severity
        self.line = line
        super().__init__(message)


def validate_no_placeholders(file_path: Path) -> List[NodeValidationError]:
    """Check for hardcoded placeholder values."""
    errors = []
    content = file_path.read_text()
    
    # Placeholder patterns that should never ship
    placeholders = [
        (r"test-owner", "Hardcoded test-owner placeholder"),
        (r"test-repo", "Hardcoded test-repo placeholder"),
        (r"example\.com", "Hardcoded example.com placeholder"),
        (r"your-api-key", "Hardcoded your-api-key placeholder"),
        (r"TODO:", "TODO comment left in generated code"),
    ]
    
    for pattern, message in placeholders:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            errors.append(NodeValidationError(
                f"{message}: '{match.group()}' at line {line_num}",
                severity="error",
                line=line_num
            ))
    
    return errors


def validate_method_references(file_path: Path) -> List[NodeValidationError]:
    """Check that all called methods are defined."""
    errors = []
    content = file_path.read_text()
    
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return [NodeValidationError(f"Syntax error: {e}", severity="error")]
    
    # Find all method calls like self._method_name(...)
    called_methods = set()
    defined_methods = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                    called_methods.add(node.func.attr)
        
        if isinstance(node, ast.FunctionDef):
            # Check if it's a method (has self parameter)
            if node.args.args and node.args.args[0].arg == 'self':
                defined_methods.add(node.name)
    
    # Check for called but not defined
    missing = called_methods - defined_methods - {'get_node_parameter', 'get_credentials', 'get_input_data'}
    for method in missing:
        # Find line number of first call
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == method:
                    errors.append(NodeValidationError(
                        f"Method self.{method}() is called but not defined",
                        severity="error",
                        line=node.lineno
                    ))
                    break
    
    return errors


def validate_auth_scheme(file_path: Path) -> List[NodeValidationError]:
    """Check authentication scheme is correct for service."""
    errors = []
    content = file_path.read_text()
    
    # Detect service from filename or class name
    node_name = file_path.stem.lower()
    
    # Services that should use Bearer, not Bot
    bearer_services = ['github', 'gitlab', 'discord', 'slack']
    
    if any(svc in node_name for svc in bearer_services):
        # Check for wrong "Bot" prefix
        bot_matches = list(re.finditer(r'Authorization.*Bot\s+', content))
        for match in bot_matches:
            line_num = content[:match.start()].count('\n') + 1
            errors.append(NodeValidationError(
                f"Wrong auth scheme: Uses 'Bot' prefix for {node_name} (should be 'Bearer') at line {line_num}",
                severity="error",
                line=line_num
            ))
    
    return errors


def validate_operation_routing(file_path: Path) -> List[NodeValidationError]:
    """Check that all operation options have corresponding execute() branches."""
    errors = []
    content = file_path.read_text()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []  # Already caught by method_references
    
    # Extract operation options from properties
    # FIXED: Only extract from "operation" parameter, not authentication or other params
    declared_operations = set()
    
    # Look for the operation parameter specifically
    # Pattern: {"name": "operation", "type": ..., "options": [...{"value": "create"}, ...]}
    op_param_pattern = r'\{"name":\s*"operation".*?"options":\s*\[(.*?)\]'
    op_match = re.search(op_param_pattern, content, re.DOTALL)
    if op_match:
        options_content = op_match.group(1)
        # Extract operation values from options
        ops = re.findall(r'"value":\s*"([^"]+)"', options_content)
        declared_operations.update(ops)
    
    # Extract execute() routing branches
    routed_operations = set()
    in_execute = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'execute':
            in_execute = True
            # Look for if/elif checking operation
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Compare):
                    # Look for patterns like: operation == "create"
                    if isinstance(stmt.left, ast.Name) and stmt.left.id == 'operation':
                        for comparator in stmt.comparators:
                            if isinstance(comparator, ast.Constant):
                                routed_operations.add(comparator.value)
    
    # Check for declared but not routed
    missing_routing = declared_operations - routed_operations
    if missing_routing and len(declared_operations) > 0:
        for op in sorted(missing_routing):
            errors.append(NodeValidationError(
                f"Operation '{op}' is declared in options but has no routing in execute()",
                severity="warning"  # Warning because it might be intentional (WIP)
            ))
    
    return errors


def validate_body_usage(file_path: Path) -> List[NodeValidationError]:
    """Check that body parameters are actually passed to requests."""
    errors = []
    content = file_path.read_text()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    
    # Find functions that read body-related parameters but pass body=None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check if it reads body/title/data parameters
            reads_body_params = False
            passes_none_body = False
            
            for stmt in ast.walk(node):
                # Check for get_node_parameter calls for body-related params
                if isinstance(stmt, ast.Call):
                    if isinstance(stmt.func, ast.Attribute) and stmt.func.attr == 'get_node_parameter':
                        if stmt.args and isinstance(stmt.args[0], ast.Constant):
                            param_name = stmt.args[0].value
                            if param_name in ('body', 'title', 'data', 'text', 'message', 'content'):
                                reads_body_params = True
                    
                    # Check for _api_request calls with body=None
                    if isinstance(stmt.func, ast.Attribute) and stmt.func.attr in ('_api_request', '_http_request'):
                        for keyword in stmt.keywords:
                            if keyword.arg == 'body':
                                if isinstance(keyword.value, ast.Constant) and keyword.value.value is None:
                                    passes_none_body = True
            
            if reads_body_params and passes_none_body:
                errors.append(NodeValidationError(
                    f"Function {node.name}() reads body parameters but passes body=None to request",
                    severity="error",
                    line=node.lineno
                ))
    
    return errors


def validate_credentials_consistency(file_path: Path) -> List[NodeValidationError]:
    """Check that declared credentials match usage."""
    errors = []
    content = file_path.read_text()
    
    # Extract declared credential name
    declared_cred = None
    cred_match = re.search(r'"credentials":\s*\[\s*\{\s*"name":\s*"([^"]+)"', content)
    if cred_match:
        declared_cred = cred_match.group(1)
    
    # Extract used credential name
    used_creds = set()
    for match in re.finditer(r'get_credentials\(["\']([^"\']+)["\']\)', content):
        used_creds.add(match.group(1))
    
    if declared_cred and used_creds:
        if declared_cred not in used_creds:
            errors.append(NodeValidationError(
                f"Credential mismatch: declares '{declared_cred}' but uses {used_creds}",
                severity="error"
            ))
    
    return errors


def validate_basenode_compatibility(file_path: Path) -> List[NodeValidationError]:
    """
    GATE: Check that generated code only uses BaseNode attributes/methods that exist.
    
    SYSTEMIC FIX: Catches continue_on_fail and other n8n features not in our BaseNode.
    """
    errors = []
    content = file_path.read_text()
    
    # Attributes/methods that exist in our BaseNode
    BASENODE_ATTRS = {
        # Defined methods
        'get_node_parameter', 'get_parameter', 'get_credentials', 'set_credentials',
        'get_input_data', 'execute', 'input_data', 'node_data', 'workflow',
        'execution_data', '_parameters', '_credentials', 'description', 'properties',
        'type', 'version', 'icon', 'color', 'subtitle',
        # Internal helpers
        '_api_request', '_api_request_all_items', '_http_request', '_oauth2_request',
        '_get_auth_headers',
    }
    
    # Attributes that DO NOT exist in BaseNode (n8n-specific)
    FORBIDDEN_ATTRS = {
        'continue_on_fail': "n8n's continueOnFail - use try/except and always raise on error",
        'continueOnFail': "n8n's continueOnFail - use try/except and always raise on error",
        'helpers': "n8n's helpers object - use direct API calls instead",
        'returnJsonArray': "n8n helper - return data directly",
    }
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    
    for node in ast.walk(tree):
        # Check for self.forbidden_attr
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                attr_name = node.attr
                if attr_name in FORBIDDEN_ATTRS:
                    errors.append(NodeValidationError(
                        f"BaseNode compatibility: self.{attr_name} does not exist in BaseNode. "
                        f"Hint: {FORBIDDEN_ATTRS[attr_name]}",
                        severity="error",
                        line=getattr(node, 'lineno', None)
                    ))
    
    return errors


def validate_undefined_variables(file_path: Path) -> List[NodeValidationError]:
    """
    GATE: Check for undefined variables in operation handlers.
    
    SYSTEMIC FIX: Catches 'owner', 'additional_params', etc. used before definition.
    """
    errors = []
    content = file_path.read_text()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    
    # Python builtins we shouldn't flag
    builtins = {'True', 'False', 'None', 'self', 'str', 'int', 'float', 'bool', 'list', 'dict',
                'len', 'range', 'enumerate', 'zip', 'map', 'filter', 'any', 'all',
                'isinstance', 'hasattr', 'getattr', 'setattr', 'Exception', 'ValueError',
                'TypeError', 'KeyError', 'IndexError', 'print', 'quote', 'requests',
                'logger', 'logging', 'json', 'NodeExecutionData', 'Dict', 'List', 'Any',
                'Optional', 'Tuple', 'Set'}
    
    # Check each function definition
    for func_node in ast.walk(tree):
        if not isinstance(func_node, ast.FunctionDef):
            continue
        
        # Track defined names within this function
        defined_names: Set[str] = set()
        
        # Add function parameters
        for arg in func_node.args.args:
            defined_names.add(arg.arg)
        
        # Walk through function body in order
        for stmt in ast.walk(func_node):
            # Track assignments
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                defined_names.add(stmt.target.id)
            elif isinstance(stmt, ast.For):
                # Handle simple: for i in ...
                if isinstance(stmt.target, ast.Name):
                    defined_names.add(stmt.target.id)
                # Handle tuple unpacking: for i, item in ...
                elif isinstance(stmt.target, ast.Tuple):
                    for elt in stmt.target.elts:
                        if isinstance(elt, ast.Name):
                            defined_names.add(elt.id)
            
            # Check for undefined names in expressions
            if isinstance(stmt, ast.Name) and isinstance(stmt.ctx, ast.Load):
                name = stmt.id
                if name not in defined_names and name not in builtins:
                    # Check if it's likely a typo or missing extraction
                    if name in ('owner', 'repository', 'project_id', 'additional_params',
                                'file_path', 'issue_number', 'tag_name', 'author_name',
                                'author_email', 'i'):  # Common missing params
                        errors.append(NodeValidationError(
                            f"Undefined variable: '{name}' used in {func_node.name}() "
                            f"- likely missing get_node_parameter() extraction",
                            severity="error",
                            line=getattr(stmt, 'lineno', None)
                        ))
    
    return errors


def validate_node_file(file_path: Path) -> Tuple[bool, List[NodeValidationError]]:
    """Run all validations on a node file."""
    all_errors = []
    
    validators = [
        validate_no_placeholders,
        validate_method_references,
        validate_auth_scheme,
        validate_operation_routing,
        validate_body_usage,
        validate_credentials_consistency,
        validate_basenode_compatibility,  # SYSTEMIC FIX: Catches continue_on_fail etc
        validate_undefined_variables,      # SYSTEMIC FIX: Catches undefined vars
    ]
    
    for validator in validators:
        try:
            errors = validator(file_path)
            all_errors.extend(errors)
        except Exception as e:
            all_errors.append(NodeValidationError(
                f"Validator {validator.__name__} failed: {e}",
                severity="error"
            ))
    
    # Separate by severity
    errors = [e for e in all_errors if e.severity == "error"]
    warnings = [e for e in all_errors if e.severity == "warning"]
    
    is_valid = len(errors) == 0
    
    return is_valid, all_errors


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_generated_node.py <node_file.py>")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    print(f"Validating: {file_path}")
    print("=" * 60)
    
    is_valid, errors = validate_node_file(file_path)
    
    # Group by severity
    error_list = [e for e in errors if e.severity == "error"]
    warning_list = [e for e in errors if e.severity == "warning"]
    
    if error_list:
        print(f"\n❌ ERRORS ({len(error_list)}):")
        for err in error_list:
            location = f" (line {err.line})" if err.line else ""
            print(f"  - {err.message}{location}")
    
    if warning_list:
        print(f"\n⚠️  WARNINGS ({len(warning_list)}):")
        for warn in warning_list:
            location = f" (line {warn.line})" if warn.line else ""
            print(f"  - {warn.message}{location}")
    
    if not error_list and not warning_list:
        print("\n✅ All validations passed!")
    
    print("\n" + "=" * 60)
    print(f"Result: {'VALID' if is_valid else 'INVALID'}")
    
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
