#!/usr/bin/env python3
"""
Code Convert Skill Implementation

Converts TypeScript n8n node source code to Python BaseNode implementation.
TYPE1 conversion only - direct code translation with KB pattern matching.

HYBRID BACKBONE: ADVISOR_ONLY (AI-assisted conversion with validation)
SYNC-CELERY SAFE: No async patterns, all state persisted.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext

from runtime.protocol import AgentResponse, TaskState


# =============================================================================
# CONVERSION PATTERNS (KB-backed)
# =============================================================================

# TypeScript → Python method/accessor mappings
TS_TO_PY_MAPPINGS = {
    # n8n helper methods
    "this.getNodeParameter": "self.get_node_parameter",
    "this.getCredentials": "self.get_credentials",
    "this.helpers.request": "self._http_request",
    "this.helpers.requestOAuth2.call": "self._oauth2_request",
    "this.getInputData()": "input_data",
    "this.continueOnFail()": "self.continue_on_fail",
    "this.helpers.returnJsonArray": "",  # handled inline
    "this.helpers.constructExecutionMetaData": "",  # handled inline
    # Type casts - must use regex, order matters (longer first)
    "as string": "",
    "as boolean": "",
    "as number": "",
    "as IDataObject": "",
    "as string[]": "",
    "as IDataObject[]": "",
    # Keywords
    "const ": "",
    "let ": "",
    "async ": "",
    "await ": "",
}

# JavaScript/TypeScript patterns that must be eliminated in output (FIX: Gate 3 enforcement)
# These are detected and converted or rejected
JS_ARTIFACT_PATTERNS = [
    # encodeURIComponent -> Python equivalent (multiple forms)
    (r'\$\{encodeURIComponent\(([^)]+)\)\}', r'{quote(str(\1), safe="")}'),  # Template literal
    (r'encodeURIComponent\(([^)]+)\)', r'quote(str(\1), safe="")'),          # Direct call
    
    # this.getNodeParameter without proper conversion
    (r'this\.getNodeParameter\(', 'self.get_node_parameter('),
    (r'this_get_node_parameter\(', 'self.get_node_parameter('),
    
    # Template literal syntax ${...} -> {var} for f-strings
    (r'\$\{([^}]+)\}', r'{\1}'),
    
    # NOTE: DO NOT add `, i)` → `, item_index)` here - execute loop uses `item_index` directly
    
    # additional_parameters_reference -> proper variable name
    (r'\badditional_parameters_reference\b', 'additional_params'),
    (r'\bparams_reference\b', 'params'),
    
    # Raw 'this.' in any context (should be 'self.')
    (r'\bthis\.', 'self.'),
]

# Known base URLs for HTTP REST services
KNOWN_BASE_URLS: dict[str, str] = {
    "github": "https://api.github.com",
    "gitlab": "https://gitlab.com/api/v4",
    "slack": "https://slack.com/api",
    "discord": "https://discord.com/api/v10",
    "trello": "https://api.trello.com/1",
    "bitly": "https://api-ssl.bitly.com",
    "hunter": "https://api.hunter.io/v2",
    "clearbit": "https://person.clearbit.com/v2",
    "notion": "https://api.notion.com/v1",
}

# Regex patterns for TypeScript type cast removal (FIX #47: strip TS type casts)
# IMPORTANT: Be careful not to match Python 'except Exception as e:' pattern
TS_TYPE_CAST_PATTERNS = [
    (r'\s+as\s+I[A-Z]\w+\[\]', ''),       # " as IDiscountCode[]" → ""
    (r'\s+as\s+I[A-Z]\w+', ''),            # " as IDataObject" → ""  
    (r'\s+as\s+string\[\]', ''),           # " as string[]" → ""
    (r'\s+as\s+number\[\]', ''),           # " as number[]" → ""
    (r'\s+as\s+string', ''),               # " as string" → ""
    (r'\s+as\s+number', ''),               # " as number" → ""
    (r'\s+as\s+boolean', ''),              # " as boolean" → ""
    # Catch-all for TS types: require uppercase first letter (TS types) or known TS types
    # Excludes lowercase single letters like 'e' (Python exception binding)
    (r'\s+as\s+[A-Z]\w*', ''),             # " as AnyType" → "" (TS types start uppercase)
]

# Boolean literal conversions (FIX #48: JS booleans to Python)
JS_TO_PY_LITERALS = {
    'true': 'True',
    'false': 'False',
    'null': 'None',
    'undefined': 'None',
}


# =============================================================================
# STUB DETECTION (TYPE1 HARD-FAIL ENFORCEMENT)
# =============================================================================

# Patterns that indicate a stub/placeholder implementation
STUB_PATTERNS = [
    r'#\s*TODO:\s*Implement',          # TODO comment
    r'#\s*__STUB_MARKER__',            # Internal stub marker
    r'raise\s+NotImplementedError',     # NotImplementedError
    r'response\s*=\s*\{\s*\}',          # Empty response dict
    r'pass\s*$',                        # Bare pass statement
    r'return\s+\{\s*\}',                # Return empty dict
    r'return\s+None',                   # Return None
]


def _is_stub_implementation(code: str) -> bool:
    """Detect if generated code is a stub/placeholder.
    
    TYPE1 ENFORCEMENT: Stubs are never allowed for TYPE1 conversions.
    This function detects stub patterns that indicate failed extraction.
    
    Args:
        code: Generated Python code for an operation handler
        
    Returns:
        True if the code contains stub patterns (should be rejected)
    """
    if not code or not code.strip():
        return True
    
    for pattern in STUB_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
            return True
    
    # Check for minimal implementation (just parameter extraction, no HTTP call)
    has_http_call = any(p in code for p in [
        'self._api_request',
        'self._http_request', 
        'self._oauth2_request',
        'requests.request',
        'requests.get',
        'requests.post',
    ])
    
    # If no HTTP call and no return with data, it's likely a stub
    if not has_http_call and 'return' in code:
        # Check if return is meaningful
        return_match = re.search(r'return\s+(.+)', code)
        if return_match:
            return_value = return_match.group(1).strip()
            # Empty or trivial returns are stubs
            if return_value in ['{}', 'None', '[]', "{'json': {}}"]:
                return True
    
    return False


def _strip_ts_type_casts(code: str) -> str:
    """Remove all TypeScript type casts from code.
    
    Handles patterns like:
        - expr as string
        - expr as IDataObject
        - expr as IDiscountCode[]
        - (expr as Type).method()
    
    FIX #47: Systemic fix for TypeScript type cast artifacts in generated Python.
    """
    result = code
    for pattern, replacement in TS_TYPE_CAST_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def _convert_js_literals(code: str) -> str:
    """Convert JavaScript boolean literals to Python.
    
    FIX #48: Systemic fix for JS boolean literals in generated Python.
    """
    result = code
    # Use word boundaries to avoid replacing inside strings
    for js_lit, py_lit in JS_TO_PY_LITERALS.items():
        # Match whole word only, not inside quotes
        result = re.sub(rf'\b{js_lit}\b', py_lit, result)
    return result


def _eliminate_js_artifacts(code: str) -> str:
    """Eliminate JavaScript/TypeScript artifacts from generated Python.
    
    SYSTEMIC FIX: Converts or removes JS patterns that should never appear in output:
    - encodeURIComponent() → quote()
    - this_get_node_parameter() → self.get_node_parameter()
    - Template literals ${...} → f-string {...}
    - Undefined loop variable 'i' → item_index
    
    This is the LAST RESORT - patterns should be caught earlier, but this
    ensures nothing leaks through.
    """
    result = code
    for pattern, replacement in JS_ARTIFACT_PATTERNS:
        result = re.sub(pattern, replacement, result)
    
    # Additional specific fixes
    # NOTE: Do not replace 'i' with 'item_index' here - execute loop now uses item_index directly
    
    # Fix any malformed nested f-strings like f'{f'/...'}'
    # This can happen when endpoint replacement created nested f-strings
    result = re.sub(r"f'\{f'([^']+)'\}", r"f'\1", result)
    
    # Fix undefined self._base_endpoint references if still present
    if "self._base_endpoint" in result and "self._base_endpoint =" not in result:
        result = result.replace("self._base_endpoint", "'/projects/' + quote(str(project_id), safe='')")
    
    # SYSTEMIC FIX: Convert JS camelCase variable names inside f-string interpolations to snake_case
    # Pattern: {quote(str(filePath), safe="")} -> {quote(str(file_path), safe="")}
    # Pattern: {varName} -> {var_name}
    def _camel_to_snake_in_fstring(match):
        inner = match.group(1)
        # Apply snake_case conversion to the variable name part
        # Be careful not to break function calls like quote(), str()
        # Only convert bare identifiers that are camelCase
        def convert_camel(m):
            name = m.group(0)
            # Skip Python builtins and common functions
            if name in ('str', 'int', 'quote', 'safe', 'encode', 'decode', 'format', 'get', 'None', 'True', 'False'):
                return name
            # Convert camelCase to snake_case
            s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
            return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        # Find all word tokens in the interpolation and convert them
        converted = re.sub(r'\b([a-z][a-zA-Z0-9]*)\b', convert_camel, inner)
        return '{' + converted + '}'
    
    result = re.sub(r'\{([^{}]+)\}', _camel_to_snake_in_fstring, result)
    
    return result


def _apply_ts_to_py_transformations(code: str) -> str:
    """Apply all TypeScript to Python transformations.
    
    This combines type cast stripping, literal conversion, and JS artifact elimination.
    """
    code = _strip_ts_type_casts(code)
    code = _convert_js_literals(code)
    code = _eliminate_js_artifacts(code)
    return code

# API request pattern
API_REQUEST_TEMPLATE = Template('''response = self._http_request(
            method="${method}",
            endpoint="${endpoint}",
            body=${body},
            credentials=credentials,
        )''')

# Operation handler template
OPERATION_HANDLER_TEMPLATE = Template('''
    def _execute_${resource}_${operation}(
        self,
        item_index: int,
        item: Dict[str, Any],
        credentials: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute ${resource}/${operation} operation."""
${body}
        return {"json": response}
''')


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def execute_code_convert(ctx: "ExecutionContext") -> AgentResponse:
    """
    Convert TypeScript n8n node to Python BaseNode.
    
    SOURCE-OF-TRUTH HIERARCHY (TYPE1):
        1. golden_impl (avidflow-back/nodes/*.py) - HIGHEST PRIORITY
        2. TypeScript source code extraction
        3. HARD-FAIL if neither provides implementation
    
    NEVER generate stubs, placeholders, or NotImplementedError for TYPE1.
    
    Inputs:
        - correlation_id: str
        - source_type: "TYPE1" 
        - parsed_sections: dict with code content
        - node_schema: inferred schema from schema-infer
        - golden_impl: dict from golden-extract skill (optional but preferred)
        - scaffold_path: path to scaffold files (optional)
    
    Outputs:
        - files_modified: list of file paths
        - conversion_notes: list of conversion decisions
        - generated_code: dict of filename -> content
    """
    inputs = ctx.inputs
    correlation_id = inputs.get("correlation_id", ctx.correlation_id)
    artifacts_dir = ctx.artifacts_dir
    
    # Validate source type
    source_type = inputs.get("source_type", "TYPE1")
    if source_type != "TYPE1":
        return AgentResponse(
            state=TaskState.FAILED,
            errors=["code-convert only handles TYPE1 (TypeScript source). Use code-implement for TYPE2."],
        )
    
    # Get source code
    parsed_sections = inputs.get("parsed_sections", {})
    code_sections = parsed_sections.get("code", [])
    if not code_sections:
        return AgentResponse(
            state=TaskState.FAILED,
            errors=["No source code provided in parsed_sections.code"],
        )
    
    # Get golden implementation (HIGHEST PRIORITY for TYPE1)
    golden_impl = inputs.get("golden_impl", {})
    has_golden = bool(golden_impl and golden_impl.get("methods"))
    
    # Get schema for structure
    node_schema = inputs.get("node_schema", {})
    node_name = node_schema.get("type", parsed_sections.get("node_name", "Unknown"))
    
    # Load KB patterns if available
    kb_patterns = inputs.get("kb_patterns", {})
    
    conversion_notes = []
    
    # =================================================================
    # PHASE 1: Parse TypeScript source
    # =================================================================
    
    # Find main node file - improved selection logic
    # Priority: 1) File matching node name with async execute, 2) Any file with async execute
    main_node_ts = None
    generic_functions_ts = None
    main_node_candidates = []
    
    for section in code_sections:
        content = section.get("content", "") if isinstance(section, dict) else str(section)
        filename = section.get("file", "") if isinstance(section, dict) else ""
        
        if "implements INodeType" in content or "export class" in content:
            # Collect candidates with their properties
            has_execute = "async execute" in content
            name_match = node_name.lower() in filename.lower() and "trigger" not in filename.lower()
            main_node_candidates.append({
                "content": content,
                "filename": filename,
                "has_execute": has_execute,
                "name_match": name_match,
            })
        if "ApiRequest" in filename or "GenericFunctions" in filename:
            generic_functions_ts = content
    
    # Select best candidate for main node
    if main_node_candidates:
        # Priority 1: File matching name AND has async execute
        for candidate in main_node_candidates:
            if candidate["name_match"] and candidate["has_execute"]:
                main_node_ts = candidate["content"]
                conversion_notes.append(f"Selected {candidate['filename']} as main node (name match + execute)")
                break
        
        # Priority 2: Any file with async execute
        if not main_node_ts:
            for candidate in main_node_candidates:
                if candidate["has_execute"]:
                    main_node_ts = candidate["content"]
                    conversion_notes.append(f"Selected {candidate['filename']} as main node (has execute)")
                    break
        
        # Priority 3: First candidate (fallback)
        if not main_node_ts and main_node_candidates:
            main_node_ts = main_node_candidates[0]["content"]
            conversion_notes.append(f"Selected {main_node_candidates[0]['filename']} as main node (fallback)")
    
    if not main_node_ts:
        return AgentResponse(
            state=TaskState.FAILED,
            errors=["Could not find main node class in source code"],
        )
    
    conversion_notes.append(f"Found main node class for {node_name}")
    
    # =================================================================
    # PHASE 1.5: Check golden implementation (SOURCE-OF-TRUTH PRIORITY)
    # =================================================================
    
    if has_golden:
        golden_methods = golden_impl.get("methods", {})
        conversion_notes.append(f"GOLDEN: Found {len(golden_methods)} methods from working node")
        conversion_notes.append(f"GOLDEN: Source file: {golden_impl.get('source_file', 'unknown')}")
    else:
        conversion_notes.append("GOLDEN: No golden implementation provided, using TS extraction")
    
    # =================================================================
    # PHASE 2: Extract operations and convert execute() method
    # =================================================================
    
    # Extract execute method body
    execute_body = _extract_execute_body(main_node_ts)
    if not execute_body:
        if has_golden:
            conversion_notes.append("TS extraction failed, relying on golden implementation")
        else:
            # TYPE1 HARD-FAIL: No golden and no TS extraction
            return AgentResponse(
                state=TaskState.FAILED,
                errors=[
                    "TYPE1 HARD-FAIL: Could not extract execute() body from TypeScript",
                    "No golden implementation available as fallback",
                    "SOURCE-OF-TRUTH HIERARCHY: golden > TS > FAIL (stubs never allowed)",
                ],
            )
    
    # Extract resource/operation routing
    operations = _extract_operations(execute_body)
    conversion_notes.append(f"Found {len(operations)} operation handlers from TS")
    
    # Convert each operation - prefer golden when available
    converted_handlers = []
    failed_operations = []  # Track operations that couldn't be converted
    
    for resource, operation, ts_code in operations:
        handler_key = f"{resource}_{operation}" if resource else operation
        
        # SOURCE-OF-TRUTH HIERARCHY: Check golden first
        golden_method = None
        if has_golden:
            golden_methods = golden_impl.get("methods", {})
            # Try exact match first
            golden_method = golden_methods.get(handler_key)
            if not golden_method:
                # Try operation-only match for resource+operation nodes
                golden_method = golden_methods.get(operation)
        
        if golden_method:
            # Use golden implementation directly
            py_code = golden_method.get("body", "")
            if py_code:
                converted_handlers.append((resource, operation, py_code))
                conversion_notes.append(f"GOLDEN: Used golden impl for {handler_key}")
                continue
        
        # Fall back to TS extraction
        py_code = _convert_operation_handler(resource, operation, ts_code, generic_functions_ts)
        
        # TYPE1 VALIDATION: Check if conversion produced a stub
        if _is_stub_implementation(py_code):
            failed_operations.append(handler_key)
            conversion_notes.append(f"FAILED: {handler_key} produced stub, no golden fallback")
        else:
            converted_handlers.append((resource, operation, py_code))
            conversion_notes.append(f"TS: Converted {handler_key}")
    
    # TYPE1 HARD-FAIL: If any operations produced stubs without golden fallback
    if failed_operations:
        return AgentResponse(
            state=TaskState.FAILED,
            errors=[
                f"TYPE1 HARD-FAIL: {len(failed_operations)} operations could not be fully converted",
                f"Failed operations: {', '.join(failed_operations)}",
                "SOURCE-OF-TRUTH HIERARCHY: golden > TS > FAIL (stubs never allowed)",
                "Provide golden_impl from working avidflow-back/nodes/ or fix TS extraction",
            ],
        )
    
    # =================================================================
    # PHASE 3: Extract and convert API helper functions
    # =================================================================
    
    api_helpers = ""
    if generic_functions_ts:
        api_helpers = _convert_generic_functions(generic_functions_ts, node_name)
        conversion_notes.append("Converted GenericFunctions.ts to Python helpers")
    
    # =================================================================
    # PHASE 4: Generate Python node file
    # =================================================================
    
    # Extract description/properties - prefer schema over TS extraction
    description = node_schema.get("description", {}) or _extract_description(main_node_ts)
    credentials = node_schema.get("credentials", []) or _extract_credentials(main_node_ts)
    
    # Get parameters from schema (preferred) or extract from TS
    schema_params = node_schema.get("properties", {}).get("parameters", [])
    if schema_params:
        properties = schema_params
        conversion_notes.append(f"Using {len(properties)} parameters from inferred schema")
    else:
        properties = _extract_properties(main_node_ts)
        conversion_notes.append(f"Extracted {len(properties)} properties from TypeScript")
    
    # Generate full Python file
    python_code = _generate_python_node(
        node_name=node_name,
        description=description,
        credentials=credentials,
        properties=properties,
        converted_handlers=converted_handlers,
        api_helpers=api_helpers,
        correlation_id=correlation_id,
        node_schema=node_schema,
    )
    
    # FIX #47/#48: Final safety net - apply all TS→Py transformations to generated code
    # This catches any TypeScript artifacts that slipped through individual converters
    python_code = _apply_ts_to_py_transformations(python_code)
    
    # =================================================================
    # PHASE 5: Write output files
    # =================================================================
    
    output_dir = artifacts_dir / "converted_node"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    module_name = _to_snake_case(node_name)
    node_file = output_dir / f"{module_name}.py"
    node_file.write_text(python_code)
    
    init_file = output_dir / "__init__.py"
    init_content = f'''"""
{node_name} Node Package
Converted from TypeScript by agent-skills/code-convert
"""

from .{module_name} import {node_name}Node

__all__ = ["{node_name}Node"]
'''
    init_file.write_text(init_content)
    
    files_modified = [str(node_file), str(init_file)]
    
    # Write conversion log
    conversion_log = {
        "correlation_id": correlation_id,
        "node_name": node_name,
        "source_type": "TYPE1",
        "operations_converted": len(converted_handlers),
        "files_generated": files_modified,
        "notes": conversion_notes,
        "generated_at": datetime.utcnow().isoformat(),
    }
    log_path = artifacts_dir / "conversion_log.json"
    log_path.write_text(json.dumps(conversion_log, indent=2))
    
    return AgentResponse(
        state=TaskState.COMPLETED,
        outputs={
            "files_modified": files_modified,
            "conversion_notes": conversion_notes,
            "generated_code": {
                f"{module_name}.py": python_code,
                "__init__.py": init_content,
            },
        },
    )


# =============================================================================
# TYPESCRIPT PARSING HELPERS
# =============================================================================

def _extract_execute_body(ts_code: str) -> str:
    """Extract the body of the execute() method."""
    # Pattern: async execute(this: IExecuteFunctions): Promise<...> { ... }
    pattern = r"async\s+execute\s*\([^)]*\)\s*:\s*Promise<[^>]+>\s*\{([\s\S]*?)\n\t\}"
    match = re.search(pattern, ts_code)
    if match:
        return match.group(1)
    
    # Fallback: simpler pattern
    pattern2 = r"execute\s*\([^)]*\)\s*(?::\s*[^{]+)?\s*\{([\s\S]*?)\n\t\}"
    match2 = re.search(pattern2, ts_code)
    if match2:
        return match2.group(1)
    
    return ""


def _extract_brace_block(text: str, start: int) -> str:
    """Extract content between matching braces starting at position."""
    brace_start = text.find('{', start)
    if brace_start == -1:
        return ""
    
    depth = 1
    pos = brace_start + 1
    while pos < len(text) and depth > 0:
        if text[pos] == '{':
            depth += 1
        elif text[pos] == '}':
            depth -= 1
        pos += 1
    
    return text[brace_start + 1:pos - 1]


def _extract_operations(execute_body: str) -> List[Tuple[str, str, str]]:
    """Extract resource/operation handlers from execute body.
    
    Handles two patterns:
    1. Resource + Operation: if (resource === 'link') { if (operation === 'create') { CODE } }
    2. Operation only: if (operation === 'domainSearch') { CODE }
    
    Returns:
        List of (resource, operation, code_body) tuples.
        For operation-only nodes, resource is empty string.
    """
    operations = []
    
    resource_pattern = r"if\s*\(\s*resource\s*===?\s*['\"](\w+)['\"]\s*\)"
    operation_pattern = r"if\s*\(\s*operation\s*===?\s*['\"](\w+)['\"]\s*\)"
    
    # First, try to find resource+operation pattern
    resource_matches = list(re.finditer(resource_pattern, execute_body))
    
    if resource_matches:
        # Pattern 1: Resource + Operation nodes (like Bitly)
        for resource_match in resource_matches:
            resource = resource_match.group(1)
            resource_body = _extract_brace_block(execute_body, resource_match.end())
            
            for op_match in re.finditer(operation_pattern, resource_body):
                operation = op_match.group(1)
                op_body = _extract_brace_block(resource_body, op_match.end())
                operations.append((resource, operation, op_body))
    else:
        # Pattern 2: Operation-only nodes (like Hunter)
        # Find all operation blocks at top level of execute body
        for op_match in re.finditer(operation_pattern, execute_body):
            operation = op_match.group(1)
            op_body = _extract_brace_block(execute_body, op_match.end())
            # Use empty string for resource to indicate operation-only
            operations.append(("", operation, op_body))
    
    return operations


def _extract_description(ts_code: str) -> Dict[str, Any]:
    """Extract node description from TypeScript."""
    desc = {
        "displayName": "Node",
        "name": "node",
        "icon": "file:node.svg",
        "group": ["output"],
        "version": 1,
        "description": "Node description",
    }
    
    # Extract displayName
    match = re.search(r"displayName:\s*['\"]([^'\"]+)['\"]", ts_code)
    if match:
        desc["displayName"] = match.group(1)
        desc["name"] = match.group(1).lower()
    
    # Extract icon
    match = re.search(r"icon:\s*['\"]([^'\"]+)['\"]", ts_code)
    if match:
        desc["icon"] = match.group(1)
    
    # Extract description
    match = re.search(r"description:\s*['\"]([^'\"]+)['\"]", ts_code)
    if match:
        desc["description"] = match.group(1)
    
    return desc


def _extract_credentials(ts_code: str) -> List[Dict[str, Any]]:
    """Extract credentials configuration from TypeScript."""
    credentials = []
    
    # Pattern: { name: 'bitlyApi', required: true, ... }
    cred_pattern = r"\{\s*name:\s*['\"](\w+)['\"][^}]*required:\s*(true|false)[^}]*\}"
    
    for match in re.finditer(cred_pattern, ts_code):
        cred_name = match.group(1)
        required = match.group(2) == "true"
        credentials.append({
            "name": cred_name,
            "required": required,
        })
    
    return credentials


def _extract_properties(ts_code: str) -> List[Dict[str, Any]]:
    """Extract properties/parameters from TypeScript with full detail.
    
    Extracts:
    - displayName, name, type
    - default value
    - required flag
    - displayOptions for conditional visibility
    - options array for OPTIONS/MULTIOPTIONS types
    - nested options for COLLECTION type
    """
    properties = []
    
    # Find properties array in TypeScript
    props_match = re.search(r'properties:\s*\[([\s\S]*?)\n\t\]', ts_code)
    if not props_match:
        return properties
    
    props_content = props_match.group(1)
    
    # Split into individual property objects using brace matching
    depth = 0
    current_prop = ""
    prop_strings = []
    
    for char in props_content:
        if char == '{':
            depth += 1
            current_prop += char
        elif char == '}':
            depth -= 1
            current_prop += char
            if depth == 0 and current_prop.strip():
                prop_strings.append(current_prop.strip())
                current_prop = ""
        elif depth > 0:
            current_prop += char
    
    # Parse each property object
    for prop_str in prop_strings:
        prop = _parse_single_property(prop_str)
        if prop:
            properties.append(prop)
    
    return properties


def _parse_single_property(prop_str: str) -> Dict[str, Any] | None:
    """Parse a single TypeScript property object into a Python dict."""
    prop = {}
    
    # Extract displayName
    display_match = re.search(r"displayName:\s*['\"]([^'\"]+)['\"]", prop_str)
    if display_match:
        prop["displayName"] = display_match.group(1)
    
    # Extract name
    name_match = re.search(r"name:\s*['\"]([^'\"]+)['\"]", prop_str)
    if name_match:
        prop["name"] = name_match.group(1)
    else:
        return None  # name is required
    
    # Extract type
    type_match = re.search(r"type:\s*['\"]([^'\"]+)['\"]", prop_str)
    if type_match:
        prop["type"] = type_match.group(1).upper()
    
    # Extract default
    default_match = re.search(r"default:\s*([^,\n]+)", prop_str)
    if default_match:
        default_val = default_match.group(1).strip()
        # Clean up the default value
        if default_val.startswith("'") or default_val.startswith('"'):
            prop["default"] = default_val.strip("'\"")
        elif default_val == "true":
            prop["default"] = True
        elif default_val == "false":
            prop["default"] = False
        elif default_val == "{}":
            prop["default"] = {}
        elif default_val == "[]":
            prop["default"] = []
        elif default_val.isdigit():
            prop["default"] = int(default_val)
    
    # Extract required
    if "required: true" in prop_str:
        prop["required"] = True
    
    # Extract description
    desc_match = re.search(r"description:\s*['\"]([^'\"]+)['\"]", prop_str)
    if desc_match:
        prop["description"] = desc_match.group(1)
    
    # Extract placeholder
    placeholder_match = re.search(r"placeholder:\s*['\"]([^'\"]+)['\"]", prop_str)
    if placeholder_match:
        prop["placeholder"] = placeholder_match.group(1)
    
    # Extract displayOptions
    display_opts_match = re.search(r"displayOptions:\s*\{([^}]+)\}", prop_str)
    if display_opts_match:
        opts_content = display_opts_match.group(1)
        show_match = re.search(r"show:\s*\{([^}]+)\}", opts_content)
        if show_match:
            show_content = show_match.group(1)
            show_dict = {}
            # Parse key: [values] patterns
            for kv_match in re.finditer(r"(\w+):\s*\[([^\]]+)\]", show_content):
                key = kv_match.group(1)
                values_str = kv_match.group(2)
                values = [v.strip().strip("'\"") for v in values_str.split(",")]
                # Convert string booleans
                values = [v if v not in ("true", "false") else v == "true" for v in values]
                show_dict[key] = values
            if show_dict:
                prop["display_options"] = {"show": show_dict}
    
    # Extract options array for OPTIONS/MULTIOPTIONS
    if prop.get("type") in ("OPTIONS", "MULTIOPTIONS", "options", "multiOptions"):
        prop["options"] = _extract_options_array(prop_str)
    
    # Extract nested options for COLLECTION type
    if prop.get("type") in ("COLLECTION", "collection"):
        prop["options"] = _extract_collection_options(prop_str)
    
    return prop


def _extract_options_array(prop_str: str) -> List[Dict[str, Any]]:
    """Extract options array from a property string."""
    options = []
    
    # Find options array - skip nested options in collection
    # Look for options: [ that's not part of sub-properties
    options_match = re.search(r"options:\s*\[([\s\S]*?)\](?=,|\n\t\t\})", prop_str)
    if not options_match:
        return options
    
    opts_content = options_match.group(1)
    
    # Parse each option object
    for opt_match in re.finditer(r"\{\s*name:\s*['\"]([^'\"]+)['\"],\s*value:\s*['\"]([^'\"]+)['\"](?:,\s*description:\s*['\"]([^'\"]+)['\"])?[^}]*\}", opts_content):
        opt = {
            "name": opt_match.group(1),
            "value": opt_match.group(2),
        }
        if opt_match.group(3):
            opt["description"] = opt_match.group(3)
        options.append(opt)
    
    return options


def _extract_collection_options(prop_str: str) -> List[Dict[str, Any]]:
    """Extract nested options for COLLECTION type properties."""
    options = []
    
    # Find options array after placeholder
    opts_match = re.search(r"options:\s*\[([\s\S]+)\]\s*,?\s*\}$", prop_str)
    if not opts_match:
        return options
    
    opts_content = opts_match.group(1)
    
    # Split into individual option objects using brace matching
    depth = 0
    current_opt = ""
    opt_strings = []
    
    for char in opts_content:
        if char == '{':
            depth += 1
            current_opt += char
        elif char == '}':
            depth -= 1
            current_opt += char
            if depth == 0 and current_opt.strip():
                opt_strings.append(current_opt.strip())
                current_opt = ""
        elif depth > 0:
            current_opt += char
    
    # Parse each nested option
    for opt_str in opt_strings:
        opt = _parse_single_property(opt_str)
        if opt:
            options.append(opt)
    
    return options


# =============================================================================
# CONVERSION HELPERS
# =============================================================================

def _convert_operation_handler(
    resource: str,
    operation: str,
    ts_code: str,
    generic_ts: str | None,
) -> str:
    """Convert a TypeScript operation handler to Python using BaseNode patterns.
    
    Handles:
    - getNodeParameter() calls → self.get_node_parameter()
    - Query string (qs) construction
    - Body construction  
    - API calls with various patterns
    - Conditional logic for filters, returnAll, etc.
    - GitLab baseEndpoint pattern with owner/repository extraction
    - SYSTEMIC FIX: Ensure all endpoint template vars are extracted
    """
    lines = []
    qs_fields = []
    body_fields = []
    has_return_all = False
    has_filters = False
    needs_base_endpoint = False
    endpoint_vars_needed = set()  # SYSTEMIC FIX: Track vars needed in endpoint
    
    # Check if this operation uses baseEndpoint pattern (GitLab-style)
    if 'baseEndpoint' in ts_code or '${baseEndpoint}' in (generic_ts or ''):
        needs_base_endpoint = True
    
    # SYSTEMIC FIX: Detect all template variables in endpoints
    # Pattern: endpoint = `...${varName}...`
    endpoint_pattern = r"endpoint\s*=\s*['\"`]([^'\"`]+)['\"`]"
    endpoint_match = re.search(endpoint_pattern, ts_code)
    if endpoint_match:
        endpoint_template = endpoint_match.group(1)
        # Extract all ${varName} references
        for var_match in re.finditer(r'\$\{(\w+)\}', endpoint_template):
            var_name = var_match.group(1)
            if var_name != 'baseEndpoint':  # baseEndpoint is handled separately
                endpoint_vars_needed.add(var_name)
    
    # =================================================================
    # Step 0: If GitLab-style, add owner/repository extraction first
    # =================================================================
    if needs_base_endpoint:
        lines.append("owner = self.get_node_parameter('owner', item_index)")
        lines.append("repository = self.get_node_parameter('repository', item_index)")
        lines.append("")
        lines.append("# Build base endpoint for GitLab API")
        lines.append("# FIX: URL-encode project path for GitLab API")
        lines.append("project_path = quote(f'{owner}/{repository}', safe='')")
        lines.append("base_endpoint = f'/projects/{project_path}'")
        lines.append("")
        # Mark these as extracted so we don't duplicate
        endpoint_vars_needed.discard('owner')
        endpoint_vars_needed.discard('repository')
    
    # =================================================================
    # Step 1: Extract all getNodeParameter calls
    # =================================================================
    # Pattern: const varName = this.getNodeParameter('paramName', i)
    # Also handles: this.getNodeParameter('paramName', i) as string
    param_pattern = r"(?:const\s+)?(\w+)\s*=\s*(?:this\.)?getNodeParameter\(['\"](\w+)['\"],\s*\w+(?:\s*,\s*[^)]+)?\)(?:\s*as\s+\w+)?"
    
    extracted_params = {}
    for match in re.finditer(param_pattern, ts_code):
        var_name = match.group(1)
        param_name = match.group(2)
        py_var = _to_snake_case(var_name)
        extracted_params[var_name] = (py_var, param_name)
        lines.append(f"{py_var} = self.get_node_parameter('{param_name}', item_index)")
        
        if param_name == 'returnAll':
            has_return_all = True
        if param_name == 'filters':
            has_filters = True
        # Mark as extracted for endpoint vars
        endpoint_vars_needed.discard(var_name)
    
    # SYSTEMIC FIX: Extract any remaining endpoint template variables
    # These weren't found in getNodeParameter calls but are used in the endpoint
    for var_name in list(endpoint_vars_needed):
        py_var = _to_snake_case(var_name)
        # Map common TS var names to parameter names
        param_name_map = {
            'owner': 'owner',
            'repo': 'repository',
            'repository': 'repository',
            'projectId': 'projectId',
            'id': 'projectId',
            'issueNumber': 'issueNumber',
            'issueIid': 'issueNumber',
            'tagName': 'tag_name',
            'releaseTag': 'releaseTag',
            'filePath': 'filePath',
        }
        param_name = param_name_map.get(var_name, var_name)
        extracted_params[var_name] = (py_var, param_name)
        lines.append(f"{py_var} = self.get_node_parameter('{param_name}', item_index)")
        endpoint_vars_needed.discard(var_name)
    
    # =================================================================
    # Step 2: Extract query string (qs) assignments
    # =================================================================
    # Pattern: qs.field = value or qs.field = variable
    qs_pattern = r"qs\.(\w+)\s*=\s*([^;]+)"
    for match in re.finditer(qs_pattern, ts_code):
        field = match.group(1)
        value_expr = match.group(2).strip()
        
        # Convert the value expression
        py_value = _convert_ts_expression(value_expr, extracted_params)
        qs_fields.append((field, py_value))
    
    # =================================================================
    # Step 3: Extract body construction
    # =================================================================
    # Pattern: const body = { field: value, ... }
    body_init_pattern = r"const\s+body\s*(?::\s*\w+)?\s*=\s*\{([^}]*)\}"
    body_init_match = re.search(body_init_pattern, ts_code)
    if body_init_match:
        init_content = body_init_match.group(1)
        field_pattern = r"(\w+):\s*(\w+)"
        for fm in re.finditer(field_pattern, init_content):
            field_name = fm.group(1)
            value_var = fm.group(2)
            py_value = _convert_ts_expression(value_var, extracted_params)
            body_fields.append((field_name, py_value))
    
    # Pattern: body.field = value (simple assignment, NOT inside conditionals)
    # FIX #51: Be more conservative - only capture simple expressions
    # Avoid capturing conditional logic like `body.event == 'x' ||` etc
    body_assign_pattern = r"(?<![\|&=!])body\.(\w+)\s*=\s*([^;{\n]+?)(?=;|\n|$)"
    for match in re.finditer(body_assign_pattern, ts_code):
        field = match.group(1)
        value_expr = match.group(2).strip()
        # Skip if this looks like a conditional (contains comparison operators)
        if '==' in value_expr or '||' in value_expr or '&&' in value_expr or '{' in value_expr:
            continue
        # FIX #52: Skip incomplete expressions (unclosed parens, await calls, etc.)
        if value_expr.count('(') != value_expr.count(')'):
            continue
        if value_expr.startswith('await ') or value_expr.startswith('this.'):
            # Complex async call or method call - skip, too complex for simple extraction
            continue
        # FIX #55: Skip complex function calls with method chaining
        # If it contains function calls (has parentheses), skip - too complex
        if '(' in value_expr and ')' in value_expr:
            # Exception: simple additionalFields.get('x') style is OK
            if not re.match(r'^[a-zA-Z_]\w*\.get\([\'"][^\'\"]+[\'"]\)$', value_expr):
                continue
        py_value = _convert_ts_expression(value_expr, extracted_params)
        # Skip empty or clearly invalid values
        if py_value and py_value not in ('', 'undefined', 'None'):
            body_fields.append((field, py_value))
    
    # =================================================================
    # Step 4: Build query dict if we have qs fields
    # =================================================================
    if qs_fields:
        lines.append("")
        lines.append("# Build query parameters")
        lines.append("query = {}")
        for field, value in qs_fields:
            # Check if this is a direct assignment or conditional
            if value.startswith("filters.") or "filters[" in value:
                # This is a filter field - will be handled separately
                continue
            lines.append(f"query['{field}'] = {value}")
    
    # =================================================================
    # Step 5: Handle filters (collection type parameter)
    # =================================================================
    if has_filters:
        lines.append("")
        lines.append("# Apply filters")
        # Look for filter field access patterns: filters.type, filters.seniority, etc.
        filter_pattern = r"if\s*\(filters\.(\w+)\)\s*\{[^}]*qs\.(\w+)\s*=\s*([^;]+)"
        for match in re.finditer(filter_pattern, ts_code):
            filter_field = match.group(1)
            qs_field = match.group(2)
            value_expr = match.group(3).strip()
            
            # Check if it's an array join
            if ".join(" in value_expr:
                lines.append(f"if filters.get('{filter_field}'):")
                lines.append(f"    query['{qs_field}'] = ','.join(filters['{filter_field}'])")
            else:
                lines.append(f"if filters.get('{filter_field}'):")
                lines.append(f"    query['{qs_field}'] = filters['{filter_field}']")
    
    # =================================================================
    # Step 6: Build body dict if we have body fields
    # =================================================================
    if body_fields:
        lines.append("")
        lines.append("# Build request body")
        # FIX #47/#48: Apply TS transformations to body field values
        clean_fields = []
        for f, v in body_fields:
            clean_v = _apply_ts_to_py_transformations(v)
            clean_fields.append((f, clean_v))
        body_dict = ", ".join(f"'{f}': {v}" for f, v in clean_fields)
        lines.append(f"body = {{{body_dict}}}")
    
    # =================================================================
    # Step 7: Extract and convert API call
    # =================================================================
    # Pattern variations:
    # - hunterApiRequest.call(this, 'GET', '/endpoint', {}, qs)
    # - await bitlyApiRequest.call(this, 'POST', '/endpoint', body)
    # - hunterApiRequestAllItems.call(this, 'data', 'GET', '/endpoint', {}, qs)
    # - gitlabApiRequest.call(this, requestMethod, endpoint, body, qs)  # Variables!
    
    # Pattern 1: String literals for method/endpoint (most common)
    api_all_pattern = r"(\w+)ApiRequestAllItems\.call\(\s*this\s*,\s*['\"](\w+)['\"],\s*['\"](\w+)['\"],\s*['\"`]([^'\"]+)['\"`](?:\s*,\s*\{\})?(?:\s*,\s*(\w+))?\s*\)"
    api_pattern_str = r"(\w+)ApiRequest\.call\(\s*this\s*,\s*['\"](\w+)['\"],\s*['\"`]([^'\"]+)['\"`](?:\s*,\s*(\w+|\{\}))?(?:\s*,\s*(\w+))?\s*\)"
    
    # Pattern 2: Variables for method/endpoint (GitLab pattern)
    # gitlabApiRequest.call(this, requestMethod, endpoint, body, qs)
    api_pattern_var = r"(\w+)ApiRequest\.call\(\s*this\s*,\s*(\w+)\s*,\s*(\w+)(?:\s*,\s*(\w+))?(?:\s*,\s*(\w+))?\s*\)"
    
    api_all_match = re.search(api_all_pattern, ts_code)
    api_match = re.search(api_pattern_str, ts_code)
    api_var_match = re.search(api_pattern_var, ts_code) if not api_match else None
    
    lines.append("")
    
    if has_return_all and api_all_match:
        # Node has returnAll pattern - generate conditional
        method = api_all_match.group(3)
        endpoint = api_all_match.group(4)
        
        lines.append("# Make API request")
        lines.append("if return_all:")
        lines.append(f"    response = self._api_request_all_items('{method}', '{endpoint}', query=query)")
        lines.append("else:")
        if 'limit' in [p[1] for p in extracted_params.values()]:
            lines.append("    query['limit'] = limit")
        lines.append(f"    response = self._api_request('{method}', '{endpoint}', query=query)")
        lines.append("    response = response.get('data', response)")
    elif api_match:
        method = api_match.group(2)
        endpoint = api_match.group(3)
        body_arg = api_match.group(4)
        qs_arg = api_match.group(5)
        
        # Determine parameters
        body_param = "body" if body_fields else "None"
        query_param = "query" if qs_fields or qs_arg else "None"
        
        lines.append("# Make API request")
        lines.append(f"response = self._api_request('{method}', '{endpoint}', body={body_param}, query={query_param})")
        lines.append("response = response.get('data', response)")
    elif api_var_match:
        # GitLab pattern: variables for method/endpoint
        # gitlabApiRequest.call(this, requestMethod, endpoint, body, qs)
        method_var = api_var_match.group(2)  # 'requestMethod'
        endpoint_var = api_var_match.group(3)  # 'endpoint'
        body_arg = api_var_match.group(4)  # 'body'
        qs_arg = api_var_match.group(5)  # 'qs'
        
        # Convert variable names to snake_case
        method_py = _to_snake_case(method_var)
        endpoint_py = _to_snake_case(endpoint_var)
        
        # Look for method/endpoint assignments in the TS code
        # e.g., let requestMethod: string = 'POST';
        method_assign = re.search(rf"(?:let|const)\s+{method_var}[^=]*=\s*['\"](\w+)['\"]", ts_code)
        endpoint_assign = re.search(rf"(?:let|const)\s+{endpoint_var}[^=]*=\s*['\"`]([^'\"`]+)['\"`]", ts_code)
        
        # Use extracted values or fall back to the variable approach
        method_value = f"'{method_assign.group(1)}'" if method_assign else method_py
        endpoint_value = f"'{endpoint_assign.group(1)}'" if endpoint_assign else endpoint_py
        
        # Determine body/query parameters
        body_param = "body" if body_fields else "None"
        query_param = "query" if qs_fields else "None"
        if qs_arg and qs_arg.lower() in ('qs', 'query'):
            query_param = "query"
        if body_arg and body_arg.lower() in ('body',):
            body_param = "body"
        
        lines.append("# Make API request")
        # If we extracted literal values, use them; otherwise use dynamic
        if method_assign and endpoint_assign:
            lines.append(f"response = self._api_request({method_value}, {endpoint_value}, body={body_param}, query={query_param})")
        else:
            # Dynamic: method and endpoint come from variables defined in the operation
            lines.append(f"# Note: method={method_py}, endpoint={endpoint_py} are set dynamically")
            lines.append(f"response = self._api_request({method_py}, {endpoint_py}, body={body_param}, query={query_param})")
        lines.append("response = response.get('data', response)")
    else:
        # Pattern 3: GitLab-style - method/endpoint assigned in block, API call outside
        # Check if this block sets requestMethod/endpoint variables
        method_assign = re.search(r"requestMethod\s*=\s*['\"](\w+)['\"]", ts_code)
        endpoint_assign = re.search(r"endpoint\s*=\s*['\"`]([^'\"`]+)['\"`]", ts_code)
        
        if method_assign and endpoint_assign:
            # Found method/endpoint assignments - generate API call with extracted values
            method_value = method_assign.group(1)
            endpoint_template = endpoint_assign.group(1)
            
            # Convert template literals like ${baseEndpoint}/issues to f-string style
            # Handle known variable names that should become Python expressions
            def convert_ts_var(m):
                var_name = m.group(1)
                if var_name == 'baseEndpoint':
                    # baseEndpoint should reference the base_endpoint variable we built earlier
                    return '{base_endpoint}'
                elif var_name in ('owner',):
                    return '{owner}'
                elif var_name in ('repo', 'repository'):
                    return '{repository}'
                elif var_name in ('projectId', 'project_id', 'id'):
                    # For cases like release operations that use just `id`
                    return '{quote(str(owner) + "%2F" + str(repository), safe="")}'
                elif var_name == 'issueNumber' or var_name == 'issueIid':
                    return '{issue_number}'
                elif var_name == 'releaseTag' or var_name == 'tag_name' or var_name == 'tagName':
                    return '{quote(str(tag_name), safe="")}'
                elif var_name == 'filePath':
                    return '{quote(str(file_path), safe="")}'
                else:
                    # Default: convert to snake_case local variable
                    py_var = _to_snake_case(var_name)
                    return f'{{{py_var}}}'
            
            py_endpoint = re.sub(r'\$\{(\w+)\}', convert_ts_var, endpoint_template)
            
            # Determine body/query params from what we extracted
            body_param = "body" if body_fields else "None"
            query_param = "query" if qs_fields else "None"
            
            lines.append("# Make API request (method/endpoint from operation block)")
            lines.append(f"response = self._api_request('{method_value}', f'{py_endpoint}', body={body_param}, query={query_param})")
            lines.append("response = response.get('data', response)")
        else:
            # No API call found - TYPE1 STUB MARKER (will be detected and rejected)
            # This marker signals that TS extraction failed and golden fallback is needed
            lines.append("# __STUB_MARKER__: API call extraction failed")
            lines.append("raise NotImplementedError('TYPE1 extraction failed - no API call found in TS source')")
    
    # =================================================================
    # Step 8: Return statement
    # =================================================================
    lines.append("")
    lines.append("return response")
    
    # Indent all lines
    return "\n".join("        " + line for line in lines)


def _convert_ts_expression(expr: str, extracted_params: dict) -> str:
    """Convert a TypeScript expression to Python.
    
    Args:
        expr: TypeScript expression string
        extracted_params: Dict mapping TS var names to (py_var, param_name)
    
    FIX #47/#48: Apply type cast stripping and literal conversion early.
    """
    expr = expr.strip()
    
    # FIX #47: Strip TypeScript type casts first
    expr = _strip_ts_type_casts(expr)
    
    # FIX #48: Convert JS literals
    expr = _convert_js_literals(expr)
    
    # FIX #53: Remove wrapping parentheses
    while expr.startswith('(') and expr.endswith(')'):
        # Check if the parens are balanced and actually wrap the whole expr
        if expr[1:-1].count('(') == expr[1:-1].count(')'):
            expr = expr[1:-1].strip()
        else:
            break
    
    # FIX #54: Handle (expr).property pattern - extract inner and append property
    paren_property_match = re.match(r'^\(([^)]+)\)\.(\w+)$', expr)
    if paren_property_match:
        inner_expr = paren_property_match.group(1)
        property_name = paren_property_match.group(2)
        # Recursively convert the inner expression
        inner_py = _convert_ts_expression(inner_expr, extracted_params)
        # If it's a dict access pattern, chain .get()
        if '.get(' in inner_py or inner_py.endswith(')'):
            return f"{inner_py}.get('{property_name}')"
        else:
            return f"{inner_py}.get('{property_name}')"
    
    # Direct variable reference
    if expr in extracted_params:
        return extracted_params[expr][0]  # Return Python var name
    
    # Already looks like a Python variable (snake_case)
    if re.match(r'^[a-z_][a-z0-9_]*$', expr):
        return _to_snake_case(expr)
    
    # String literal - but check for embedded type casts in the string key
    if expr.startswith("'") or expr.startswith('"'):
        # Clean type casts from inside string literals
        # e.g., 'fulfillmentStatus as string' → 'fulfillmentStatus'
        inner = expr[1:-1]  # Remove quotes
        inner = _strip_ts_type_casts(inner)
        return f"'{inner}'"
    
    # Number
    if re.match(r'^-?\d+\.?\d*$', expr):
        return expr
    
    # Array/object cast: (filters.seniority as string[]).join(',')
    join_pattern = r"\(([^)]+)\s+as\s+\w+\[\]\)\.join\(['\"]([^'\"]+)['\"]\)"
    join_match = re.search(join_pattern, expr)
    if join_match:
        array_expr = join_match.group(1)
        separator = join_match.group(2)
        py_array = _convert_ts_expression(array_expr, extracted_params)
        return f"'{separator}'.join({py_array})"
    
    # FIX #53: Handle nested property access like additionalParameters.branch.value
    # For complex expressions, recursively process
    if '.' in expr:
        parts = expr.split('.')
        # First part - might be a known param or just a variable
        if parts[0] in extracted_params:
            base = extracted_params[parts[0]][0]
            # Chain .get() calls for nested access
            result = base
            for part in parts[1:]:
                result = f"{result}.get('{part}')"
            return result
        else:
            # SYSTEMIC FIX: Check if it's a known parameter name that should use .get()
            # Common patterns: additionalParameters.field, additionalFields.field, etc.
            param_like_names = ['additionalParameters', 'additionalFields', 'filters', 'options', 'editFields']
            if parts[0] in param_like_names:
                base = _to_snake_case(parts[0])
                result = base
                for part in parts[1:]:
                    result = f"{result}.get('{part}')"
                return result
            # Convert the whole thing to snake_case as a flat variable
            return _to_snake_case('_'.join(parts))
    
    # Fallback: convert to snake_case
    return _to_snake_case(expr)


def _convert_generic_functions(ts_code: str, node_name: str) -> str:
    """Convert GenericFunctions.ts to Python helper methods."""
    
    # Extract base URL
    base_url_match = re.search(r"uri:\s*['\"`]([^'\"]+)['\"`]", ts_code)
    base_url = base_url_match.group(1) if base_url_match else "https://api.example.com"
    # Clean up template parts
    base_url = re.sub(r"\$\{[^}]+\}", "", base_url)
    
    python_helpers = f'''
    # API Base URL
    BASE_URL = "{base_url}"
    
    def _api_request(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
        credentials: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated API request.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        import requests
        
        url = f"{{self.BASE_URL}}{{endpoint}}"
        headers = self._get_auth_headers(credentials or {{}})
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=body,
            params=query,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()
    
    def _api_request_all_items(
        self,
        property_name: str,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
        credentials: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Make paginated API request and return all items.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        import requests
        
        results = []
        query = query or {{}}
        query["size"] = 50
        
        url = f"{{self.BASE_URL}}{{endpoint}}"
        
        while url:
            headers = self._get_auth_headers(credentials or {{}})
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body,
                params=query,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            
            results.extend(data.get(property_name, []))
            
            # Check for pagination
            pagination = data.get("pagination", {{}})
            url = pagination.get("next")
            query = {{}}  # Clear query params for next page URL
        
        return results
    
    def _get_auth_headers(self, credentials: Dict[str, Any]) -> Dict[str, str]:
        """Get authentication headers from credentials."""
        headers = {{"Content-Type": "application/json"}}
        
        if "accessToken" in credentials:
            headers["Authorization"] = f"Bearer {{credentials['accessToken']}}"
        elif "access_token" in credentials:
            headers["Authorization"] = f"Bearer {{credentials['access_token']}}"
        
        return headers
'''
    return python_helpers


def _generate_python_node(
    node_name: str,
    description: Dict[str, Any],
    credentials: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    converted_handlers: List[Tuple[str, str, str]],
    api_helpers: str,
    correlation_id: str,
    node_schema: Dict[str, Any] | None = None,
) -> str:
    """Generate complete Python node file following BaseNode patterns."""
    
    class_name = node_name.replace("-", "").replace("_", "")
    module_name = _to_snake_case(node_name)
    
    # Determine if this node uses resource+operation or just operation
    has_resource = any(p.get("name") == "resource" for p in properties)
    
    # Extract operations from schema or properties
    operations = []
    if node_schema and "operations" in node_schema:
        operations = node_schema["operations"]
    else:
        # Try to get from operation property options
        for prop in properties:
            if prop.get("name") == "operation" and "options" in prop:
                operations = prop["options"]
                break
    
    # Build a map of converted handlers: (resource, operation) -> code
    handler_map = {}
    for resource, operation, py_code in converted_handlers:
        handler_map[(resource, operation)] = py_code
    
    # Determine if we have resource+operation handlers (non-empty resource keys)
    has_resource_handlers = any(k[0] for k in handler_map.keys())
    
    # Generate operation method handlers
    handlers_code = ""
    
    if has_resource_handlers:
        # Resource+operation pattern: generate methods for each (resource, operation) pair
        for (resource, operation), py_code in handler_map.items():
            if resource:  # Has resource prefix
                method_name = f"_{resource}_{operation}"
                op_display = f"{resource.title()} {operation.title()}"
            else:
                method_name = f"_{operation}"
                op_display = operation.title()
            
            handlers_code += f'''
    def {method_name}(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        {op_display} operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
{py_code}
'''
    else:
        # Operation-only pattern: generate methods from schema operations
        for op in operations:
            op_name = op.get("value", op.get("name", ""))
            if op_name:
                method_name = f"_{op_name}"
                op_display = op.get("name", op_name)
                
                # Check if we have converted code for this operation
                converted_code = handler_map.get(("", op_name))
                
                if converted_code:
                    handlers_code += f'''
    def {method_name}(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        {op_display} operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
{converted_code}
'''
                else:
                    # TYPE1 HARD-FAIL: This branch should never be reached with proper source hierarchy
                    # If we get here, it means an operation exists but has no implementation
                    # Previously this generated a stub - now we fail early in PHASE 2
                    raise RuntimeError(
                        f"TYPE1 HARD-FAIL: Operation '{op_name}' has no converted code. "
                        f"This indicates a bug in the source hierarchy enforcement. "
                        f"All operations must be converted or fail in PHASE 2."
                    )
    
    # Generate execute routing
    if has_resource_handlers:
        # Resource + operation pattern - build dispatch from handler_map
        dispatch_cases = []
        for idx, (resource, operation) in enumerate(handler_map.keys()):
            if resource:
                method_name = f"_{resource}_{operation}"
                # First case uses 'if', subsequent use 'elif'
                keyword = 'if' if idx == 0 else 'elif'
                dispatch_cases.append(
                    f'                {keyword} resource == "{resource}" and operation == "{operation}":\n'
                    f'                    result = self.{method_name}(item_index, item_data)'
                )
        
        dispatch_code = "\n".join(dispatch_cases) if dispatch_cases else '                pass'
        
        execute_routing = f'''
        for item_index, item in enumerate(input_data):
            try:
                resource = self.get_node_parameter("resource", item_index)
                operation = self.get_node_parameter("operation", item_index)
                item_data = item.json_data if hasattr(item, 'json_data') else item.get('json', {{}})
                
{dispatch_code}
                else:
                    raise ValueError(f"Unknown resource/operation: {{resource}}/{{operation}}")
                
                # Handle array results
                if isinstance(result, list):
                    for r in result:
                        return_items.append(NodeExecutionData(json_data=r))
                else:
                    return_items.append(NodeExecutionData(json_data=result))
                
            except Exception as e:
                logger.error(f"Error in {{resource}}/{{operation}}: {{e}}")
                # BaseNode does not support continue_on_fail - always raise
                raise
        
        return [return_items]'''
    else:
        # Operation-only pattern (like Hunter)
        op_dispatch_lines = []
        for idx, op in enumerate(operations):
            op_name = op.get("value", op.get("name", ""))
            if op_name:
                if idx == 0:
                    op_dispatch_lines.append(f'''                if operation == "{op_name}":
                    result = self._{op_name}(item_index, item_data)''')
                else:
                    op_dispatch_lines.append(f'''                elif operation == "{op_name}":
                    result = self._{op_name}(item_index, item_data)''')
        
        op_dispatch = "\n".join(op_dispatch_lines) if op_dispatch_lines else '                pass  # No operations defined'
        
        execute_routing = f'''
        for item_index, item in enumerate(input_data):
            try:
                operation = self.get_node_parameter("operation", item_index)
                item_data = item.json_data if hasattr(item, 'json_data') else item.get('json', {{}})
                
{op_dispatch}
                else:
                    raise ValueError(f"Unknown operation: {{operation}}")
                
                # Handle array results
                if isinstance(result, list):
                    for r in result:
                        return_items.append(NodeExecutionData(json_data=r))
                else:
                    return_items.append(NodeExecutionData(json_data=result))
                    
            except Exception as e:
                logger.error(f"Error in operation {{operation}}: {{e}}")
                # BaseNode does not support continue_on_fail - always raise
                raise
        
        return [return_items]'''
    
    # Build credential type name
    cred_name = f"{module_name}Api"
    if credentials:
        first_cred = credentials[0]
        if isinstance(first_cred, dict):
            cred_name = first_cred.get("name", cred_name)
        elif isinstance(first_cred, str):
            # Schema may store just the credential type name
            cred_name = first_cred if first_cred != "apiKey" else f"{module_name}Api"
    
    # Get base URL from known services or credentials
    base_url = KNOWN_BASE_URLS.get(module_name.lower(), "")
    base_url_from_creds = not base_url  # If not known, get from credentials
    
    # Build proper description dict (GROUND TRUTH: must be dict, not string)
    display_name = description.get('displayName', node_name)
    node_description_text = description.get('description', f"Consume the {display_name} API")
    group_list = description.get('group', ['transform'])
    
    # Build proper properties dict with credentials + parameters (GROUND TRUTH)
    formatted_params = _format_parameters(properties)
    
    # Build full Python code following BaseNode GROUND TRUTH pattern
    python_code = f'''#!/usr/bin/env python3
"""
{node_name} Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: {correlation_id}
Generated: {datetime.utcnow().isoformat()}

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from .base import BaseNode, NodeParameterType
from models import NodeExecutionData

logger = logging.getLogger(__name__)


class {class_name}Node(BaseNode):
    """
    {display_name} node implementation.
    
    {node_description_text}
    """

    type = "{node_name.lower()}"
    version = {description.get('version', 1)}
    
    # GROUND TRUTH: description must be a dict with these fields
    description = {{
        "displayName": "{display_name}",
        "name": "{node_name.lower()}",
        "group": {group_list},
        "subtitle": "={{{{$parameter['operation'] + ': ' + $parameter['resource']}}}}",
        "description": "{node_description_text}",
        "inputs": [{{"name": "main", "type": "main", "required": True}}],
        "outputs": [{{"name": "main", "type": "main", "required": True}}],
    }}
    
    # GROUND TRUTH: properties must be dict with credentials + parameters
    properties = {{
        "credentials": [
            {{
                "name": "{cred_name}",
                "required": True,
            }}
        ],
        "parameters": {formatted_params}
    }}

    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the node operations.
        
        SYNC-CELERY SAFE: All HTTP calls use timeout parameter.
        
        Returns:
            List[List[NodeExecutionData]]: Nested list where outer list is output branches,
            inner list is items in that branch.
        """
        # Get input data from previous node
        input_data = self.get_input_data()
        
        # Handle empty input
        if not input_data:
            return [[]]
        
        return_items: List[NodeExecutionData] = []
{execute_routing}
{_generate_api_request_method(module_name, cred_name, base_url, base_url_from_creds)}
{handlers_code}
'''
    
    # FIX: Apply TS→Py transformations BEFORE gate validation
    # This ensures JS artifacts are cleaned up before we validate
    python_code = _apply_ts_to_py_transformations(python_code)
    
    # GATE ENFORCEMENT: Validate generated code before returning
    # Pass schema for operation coverage gate (Gate 6)
    # Pass baseline path for parity gate (Gate 7) if available
    baseline_path = None
    if node_schema and "baseline_path" in node_schema:
        baseline_path = node_schema.get("baseline_path")
    
    validation_errors = _validate_generated_code(python_code, schema=node_schema, baseline_path=baseline_path)
    if validation_errors:
        error_msgs = "\n".join(f"  - {e}" for e in validation_errors)
        raise RuntimeError(
            f"Generated code failed hard gates. Errors:\n{error_msgs}"
        )
    
    return python_code


def _generate_api_request_method(
    module_name: str,
    cred_name: str,
    base_url: str,
    base_url_from_creds: bool,
) -> str:
    """Generate _api_request method following ground-truth patterns.
    
    GROUND TRUTH: Must not contain TODO, example URLs, or placeholder comments.
    Based on avidflow-back/nodes/gitlab.py pattern.
    """
    if base_url_from_creds:
        url_code = '''
        # Get server URL from credentials (e.g., self-hosted GitLab)
        server_url = credentials.get("server", credentials.get("baseUrl", "https://gitlab.com")).rstrip("/")
        url = f"{server_url}/api/v4{endpoint}"'''
    else:
        url_code = f'''
        url = f"{base_url}{{endpoint}}"'''
    
    return f'''
    def _api_request(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated API request.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        credentials = self.get_credentials("{cred_name}")
        if not credentials:
            raise ValueError("API credentials not found")
        
        # Build auth headers (Bearer token pattern)
        access_token = credentials.get("accessToken", credentials.get("token", credentials.get("apiKey", "")))
        if not access_token:
            raise ValueError("Access token not found in credentials")
        
        headers = {{
            "Authorization": f"Bearer {{access_token}}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }}
        {url_code}
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=query,
            json=body,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()
    
    def _api_request_all_items(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Make paginated API request, returning all items.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        all_items: List[Dict[str, Any]] = []
        query = query or {{}}
        page = 1
        per_page = 100
        
        while True:
            query["page"] = page
            query["per_page"] = per_page
            
            response = self._api_request(method, endpoint, body, query)
            
            # Handle different response formats
            if isinstance(response, list):
                items = response
            elif isinstance(response, dict):
                items = response.get("items", response.get("data", []))
            else:
                break
            
            if not items:
                break
            
            all_items.extend(items)
            
            if len(items) < per_page:
                break
            
            page += 1
        
        return all_items
'''


def _validate_generated_code(code: str, schema: Dict[str, Any] = None, baseline_path: str = None) -> List[str]:
    """Validate generated code against hard gates.
    
    GATE 1: No placeholder/TODO/example URLs
    GATE 2: Properties structure correctness (description dict, properties dict)
    GATE 3: No undefined symbols or JS template leaks
    GATE 4: Symbol Binding Integrity (all used symbols must be defined)
    GATE 5: Semantic Dead-Read Detector (catch reads from never-written locals)
    GATE 6: Operation Coverage (schema.operations == generated handlers)
    GATE 7: Baseline Behavioral Parity (optional, if baseline provided)
    
    Returns list of validation errors (empty = passed).
    """
    import ast
    
    errors = []
    
    # GATE 1: No placeholders, TODOs, or example URLs
    gate1_patterns = [
        (r'api\.example\.com', "Contains example URL: api.example.com"),
        (r'#\s*TODO:', "Contains TODO comment"),
        (r'NotImplementedError', "Contains NotImplementedError"),
        (r'this_get_node_parameter', "Contains JS artifact: this_get_node_parameter"),
        (r'encodeURIComponent', "Contains JS artifact: encodeURIComponent"),
        (r'\$\{{[^}}]+\}}', "Contains JS template literal: ${...}"),
    ]
    
    for pattern, msg in gate1_patterns:
        if re.search(pattern, code):
            errors.append(f"GATE 1 FAIL: {msg}")
    
    # GATE 2: Properties structure
    # Check that description is a dict (contains displayName, not just a string)
    if 'description = "' in code and 'description = {' not in code:
        # This is the old wrong pattern - description as string
        errors.append("GATE 2 FAIL: description is a string, must be a dict")
    
    # Check properties is a dict with credentials/parameters
    if 'properties = [' in code:
        errors.append("GATE 2 FAIL: properties is a list, must be dict with credentials/parameters")
    
    if 'credentials = [' in code and 'properties = {' in code:
        # Check if credentials is OUTSIDE properties (wrong)
        cred_pos = code.find('credentials = [')
        prop_pos = code.find('properties = {')
        if cred_pos < prop_pos and cred_pos != -1:
            errors.append("GATE 2 FAIL: credentials defined outside properties dict")
    
    # Check that credentials key exists inside properties dict
    if 'properties = {' in code:
        if '"credentials":' not in code and "'credentials':" not in code:
            errors.append("GATE 2 FAIL: properties dict is missing credentials key")
    
    # GATE 3: Undefined symbols / JS template leaks
    gate3_patterns = [
        # Raw JS this references that weren't converted
        (r'\bthis\.', "Contains raw JS 'this.' reference"),
        # JS-style template literals
        (r'\$\{[^}]+\}', "Contains JS template literal ${...}"),
        # Undefined parameters from TypeScript
        (r'\badditional_parameters_reference\b', "Undefined: additional_parameters_reference"),
        (r'\bparams_reference\b', "Undefined: params_reference"),
    ]
    
    for pattern, msg in gate3_patterns:
        if re.search(pattern, code):
            errors.append(f"GATE 3 FAIL: {msg}")
    
    # GATE 4 & 5: Symbol Binding Integrity + Dead-Read Detection
    # Use AST analysis if code parses
    try:
        tree = ast.parse(code)
        gate4_5_errors = _validate_symbol_binding(tree, code)
        errors.extend(gate4_5_errors)
    except SyntaxError as se:
        errors.append(f"GATE 4 FAIL: Code has syntax error at line {se.lineno}: {se.msg}")
    
    # GATE 6: Operation Coverage (if schema provided)
    if schema:
        gate6_errors = _validate_operation_coverage(code, schema)
        errors.extend(gate6_errors)
    
    # GATE 7: Baseline Behavioral Parity (if baseline provided)
    if baseline_path and Path(baseline_path).exists():
        gate7_errors = _validate_baseline_parity(code, baseline_path)
        errors.extend(gate7_errors)
    
    return errors


def _validate_symbol_binding(tree, code: str) -> List[str]:
    """GATE 4 & 5: Validate symbol binding integrity and detect dead reads.
    
    Uses AST to check that all symbols used (Load context) are defined (Store context).
    Operates per-function to respect local scope.
    
    Args:
        tree: AST tree (ast.AST type)
        code: Source code string
    """
    import ast
    
    errors = []
    
    # Known builtins and imports that don't need local definition
    known_symbols = {
        # Python builtins
        'True', 'False', 'None', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict',
        'isinstance', 'range', 'enumerate', 'zip', 'map', 'filter', 'any', 'all',
        'print', 'open', 'repr', 'type', 'hasattr', 'getattr', 'setattr', 'Exception',
        'ValueError', 'TypeError', 'KeyError', 'AttributeError', 'IndexError',
        # Common imports
        'logging', 'logger', 'json', 'requests', 're', 'os', 'sys', 'Path',
        'datetime', 'quote', 'hashlib',
        # Node-specific
        'self', 'BaseNode', 'NodeParameterType', 'NodeExecutionData', 'NodeOperationError',
        'Dict', 'List', 'Any', 'Optional', 'Tuple', 'Union',
    }
    
    # Critical undefined symbols that must be caught
    critical_undefined = {
        'project_id': "project_id used but never assigned (need owner+repository)",
        # NOTE: item_index is now the loop variable, not a bug
        'issue_iid': "issue_iid used but issue_number is the parameter",
        'author_name': "author_name used without extraction from additionalParameters",
        'author_email': "author_email used without extraction from additionalParameters",
        'additional_params': "additional_params misspelled (is additional_parameters)",
        'filePath': "filePath is JS camelCase (should be file_path)",
        'issueNumber': "issueNumber is JS camelCase (should be issue_number)",
    }
    
    # Check for critical undefined symbols in code
    for symbol, msg in critical_undefined.items():
        # Must appear as a Name (not in string or as parameter name definition)
        pattern = rf'\b{symbol}\b'
        if re.search(pattern, code):
            # Verify it's not a parameter definition
            def_pattern = rf'(?:def|self\.get_node_parameter\()[^)]*["\']?{symbol}["\']?\s*[,)]'
            param_def_pattern = rf'["\']{symbol}["\']'
            
            # If it appears outside of a string/parameter definition, it's undefined
            for line in code.split('\n'):
                if symbol in line:
                    # Check if it's used as a variable (not in a string for parameter access)
                    if f"'{symbol}'" not in line and f'"{symbol}"' not in line:
                        if f'{symbol}' in line and '=' not in line.split(symbol)[0][-20:]:
                            errors.append(f"GATE 4 FAIL: {msg}")
                            break
    
    # Additional check: exception handler must bind exception variable
    exception_pattern = r'except\s+Exception\s*:'
    if re.search(exception_pattern, code):
        # Check if 'as e' is missing
        if not re.search(r'except\s+Exception\s+as\s+\w+\s*:', code):
            errors.append("GATE 5 FAIL: exception handler 'except Exception:' must use 'except Exception as e:'")
    
    # Check for 'e' being used in error message without being defined
    if "except Exception:" in code:
        if re.search(r'\berror.*\{e\}|\berror.*\be\b', code):
            errors.append("GATE 5 FAIL: Variable 'e' used in error message but exception not bound")
    
    return errors


def _validate_operation_coverage(code: str, schema: Dict[str, Any]) -> List[str]:
    """GATE 6: Verify schema.operations == generated handlers.
    
    Checks that every operation defined in schema has a corresponding handler method.
    """
    errors = []
    
    # Extract expected operations from schema
    expected_ops = set()
    
    # Schema may have operations list or resource/operation structure
    if "operations" in schema:
        for op in schema["operations"]:
            if isinstance(op, dict):
                resource = op.get("resource", "")
                operation = op.get("name", op.get("operation", ""))
                if resource and operation:
                    expected_ops.add(f"{resource}_{operation}".lower())
                elif operation:
                    expected_ops.add(operation.lower())
    
    # Also check properties.parameters for operation definitions
    if "properties" in schema and "parameters" in schema["properties"]:
        for param in schema["properties"]["parameters"]:
            if param.get("name") == "operation":
                for opt in param.get("options", []):
                    if isinstance(opt, dict):
                        op_value = opt.get("value", "")
                        if op_value:
                            expected_ops.add(op_value.lower())
    
    # Extract actual handler methods from code
    actual_handlers = set()
    handler_pattern = r'def\s+_(\w+)_(\w+)\s*\('
    for match in re.finditer(handler_pattern, code):
        resource = match.group(1)
        operation = match.group(2)
        actual_handlers.add(f"{resource}_{operation}".lower())
    
    # Also check dispatch table in execute()
    dispatch_pattern = r'elif\s+resource\s*==\s*["\'](\w+)["\']\s+and\s+operation\s*==\s*["\'](\w+)["\']'
    for match in re.finditer(dispatch_pattern, code):
        resource = match.group(1)
        operation = match.group(2)
        actual_handlers.add(f"{resource}_{operation}".lower())
    
    # Compare expected vs actual
    missing = expected_ops - actual_handlers
    extra = actual_handlers - expected_ops
    
    for op in missing:
        if op and '_' in op:  # Only report valid resource_operation pairs
            errors.append(f"GATE 6 FAIL: Missing handler for operation: {op}")
    
    # Extra handlers are warnings, not errors
    # for op in extra:
    #     errors.append(f"GATE 6 WARN: Extra handler not in schema: {op}")
    
    return errors


def _validate_baseline_parity(code: str, baseline_path: str) -> List[str]:
    """GATE 7: Compare against golden baseline for behavioral parity.
    
    Checks that key patterns from baseline are present in generated code.
    """
    errors = []
    
    try:
        baseline_code = Path(baseline_path).read_text()
    except Exception:
        return []  # Skip if baseline can't be read
    
    # Extract baseline handlers
    baseline_handlers = set()
    handler_pattern = r'def\s+_(\w+)_(\w+)\s*\('
    for match in re.finditer(handler_pattern, baseline_code):
        resource = match.group(1)
        operation = match.group(2)
        baseline_handlers.add(f"{resource}_{operation}".lower())
    
    # Extract generated handlers
    generated_handlers = set()
    for match in re.finditer(handler_pattern, code):
        resource = match.group(1)
        operation = match.group(2)
        generated_handlers.add(f"{resource}_{operation}".lower())
    
    # Check for missing handlers
    missing = baseline_handlers - generated_handlers
    for handler in missing:
        errors.append(f"GATE 7 FAIL: Handler missing vs baseline: {handler}")
    
    # Check for key patterns that must exist
    key_patterns = [
        (r'def _api_request\(', "Missing _api_request method"),
        (r'def _api_request_all_items\(', "Missing pagination helper _api_request_all_items"),
        (r'def _get_auth_headers\(', "Missing _get_auth_headers method (auth pattern)"),
        (r'base_endpoint\s*=', "Missing base_endpoint construction"),
        (r'owner\s*=\s*self\.get_node_parameter', "Missing owner parameter read"),
        (r'repository\s*=\s*self\.get_node_parameter', "Missing repository parameter read"),
    ]
    
    # Only check patterns that exist in baseline
    for pattern, msg in key_patterns:
        if re.search(pattern, baseline_code) and not re.search(pattern, code):
            errors.append(f"GATE 7 FAIL: {msg}")
    
    # Calculate parity score
    if baseline_handlers:
        parity = len(generated_handlers & baseline_handlers) / len(baseline_handlers)
        if parity < 0.8:
            errors.append(f"GATE 7 FAIL: Handler parity {parity:.1%} < 80% threshold")
    
    return errors


def _format_parameters(properties: List[Dict[str, Any]]) -> str:
    """Format properties list as dict format (like Bale node pattern)."""
    if not properties:
        return "[]"
    
    formatted = []
    for prop in properties:
        parts = []
        
        # Name (required)
        parts.append(f'"name": "{prop.get("name", "")}"')
        
        # Type - use NodeParameterType enum
        param_type = prop.get("type", "STRING").upper()
        type_mapping = {
            "OPTIONS": "OPTIONS",
            "MULTIOPTIONS": "MULTI_OPTIONS",
            "STRING": "STRING",
            "NUMBER": "NUMBER",
            "BOOLEAN": "BOOLEAN",
            "COLLECTION": "COLLECTION",
            "FIXEDCOLLECTION": "FIXED_COLLECTION",
            "JSON": "JSON",
        }
        mapped_type = type_mapping.get(param_type, "STRING")
        parts.append(f'"type": NodeParameterType.{mapped_type}')
        
        # Display name
        display_name = prop.get("displayName", prop.get("display_name", prop.get("name", "")))
        parts.append(f'"display_name": "{display_name}"')
        
        # Options for OPTIONS/MULTIOPTIONS types
        if "options" in prop and prop.get("type", "").upper() in ("OPTIONS", "MULTIOPTIONS", "options", "multiOptions"):
            options_str = _format_options_array(prop["options"])
            parts.append(f'"options": {options_str}')
        
        # Default value
        if "default" in prop:
            default_val = prop["default"]
            if isinstance(default_val, str):
                parts.append(f'"default": "{default_val}"')
            elif isinstance(default_val, bool):
                parts.append(f'"default": {default_val}')
            elif isinstance(default_val, (int, float)):
                parts.append(f'"default": {default_val}')
            elif isinstance(default_val, dict):
                parts.append(f'"default": {repr(default_val)}')
            elif isinstance(default_val, list):
                parts.append(f'"default": {repr(default_val)}')
        
        # Required flag
        if prop.get("required"):
            parts.append('"required": True')
        
        # Description
        if "description" in prop:
            desc = prop["description"].replace('"', '\\"')
            parts.append(f'"description": "{desc}"')
        
        # Display options for conditional visibility
        if "display_options" in prop:
            display_opts = prop["display_options"]
            parts.append(f'"display_options": {repr(display_opts)}')
        elif "displayOptions" in prop:
            display_opts = prop["displayOptions"]
            parts.append(f'"display_options": {repr(display_opts)}')
        
        # Placeholder
        if "placeholder" in prop:
            placeholder = prop["placeholder"].replace('"', '\\"')
            parts.append(f'"placeholder": "{placeholder}"')
        
        # Nested options for COLLECTION type
        if "options" in prop and prop.get("type", "").upper() in ("COLLECTION", "collection"):
            nested_opts = _format_collection_options(prop["options"])
            parts.append(f'"options": {nested_opts}')
        
        formatted.append("            {" + ", ".join(parts) + "}")
    
    return "[\n" + ",\n".join(formatted) + "\n        ]"


def _format_options_array(options: List[Dict[str, Any]]) -> str:
    """Format options array for NodeParameter."""
    if not options:
        return "[]"
    
    formatted = []
    for opt in options:
        parts = []
        if "name" in opt:
            parts.append(f'"name": "{opt["name"]}"')
        if "value" in opt:
            parts.append(f'"value": "{opt["value"]}"')
        if "description" in opt:
            desc = opt["description"].replace('"', '\\"')
            parts.append(f'"description": "{desc}"')
        formatted.append("{" + ", ".join(parts) + "}")
    
    return "[\n                " + ",\n                ".join(formatted) + "\n            ]"


def _format_collection_options(options: List[Dict[str, Any]]) -> str:
    """Format nested options for COLLECTION type."""
    if not options:
        return "[]"
    
    formatted = []
    for opt in options:
        parts = []
        if "displayName" in opt:
            parts.append(f'"displayName": "{opt["displayName"]}"')
        if "name" in opt:
            parts.append(f'"name": "{opt["name"]}"')
        if "type" in opt:
            parts.append(f'"type": "{opt["type"].lower()}"')
        if "default" in opt:
            parts.append(f'"default": {repr(opt["default"])}')
        if "options" in opt:
            nested = _format_options_array(opt["options"])
            parts.append(f'"options": {nested}')
        formatted.append("{" + ", ".join(parts) + "}")
    
    return "[\n                " + ",\n                ".join(formatted) + "\n            ]"


def _extract_base_url(api_helpers: str) -> str:
    """Extract BASE_URL from api_helpers string."""
    match = re.search(r'BASE_URL\s*=\s*["\']([^"\']+)["\']', api_helpers)
    if match:
        return match.group(1)
    return "https://api-ssl.bitly.com/v4"


def _to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
