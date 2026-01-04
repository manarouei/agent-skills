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
    # Type casts
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
    
    Inputs:
        - correlation_id: str
        - source_type: "TYPE1" 
        - parsed_sections: dict with code content
        - node_schema: inferred schema from schema-infer
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
    
    # Get schema for structure
    node_schema = inputs.get("node_schema", {})
    node_name = node_schema.get("type", parsed_sections.get("node_name", "Unknown"))
    
    # Load KB patterns if available
    kb_patterns = inputs.get("kb_patterns", {})
    
    conversion_notes = []
    
    # =================================================================
    # PHASE 1: Parse TypeScript source
    # =================================================================
    
    # Find main node file
    main_node_ts = None
    generic_functions_ts = None
    
    for section in code_sections:
        content = section.get("content", "") if isinstance(section, dict) else str(section)
        filename = section.get("file", "") if isinstance(section, dict) else ""
        
        if "implements INodeType" in content or "export class" in content:
            main_node_ts = content
        if "ApiRequest" in filename or "GenericFunctions" in filename:
            generic_functions_ts = content
    
    if not main_node_ts:
        return AgentResponse(
            state=TaskState.FAILED,
            errors=["Could not find main node class in source code"],
        )
    
    conversion_notes.append(f"Found main node class for {node_name}")
    
    # =================================================================
    # PHASE 2: Extract operations and convert execute() method
    # =================================================================
    
    # Extract execute method body
    execute_body = _extract_execute_body(main_node_ts)
    if not execute_body:
        conversion_notes.append("WARNING: Could not extract execute() body, using scaffold")
        execute_body = ""
    
    # Extract resource/operation routing
    operations = _extract_operations(execute_body)
    conversion_notes.append(f"Found {len(operations)} operation handlers")
    
    # Convert each operation
    converted_handlers = []
    for resource, operation, ts_code in operations:
        py_code = _convert_operation_handler(resource, operation, ts_code, generic_functions_ts)
        converted_handlers.append((resource, operation, py_code))
        conversion_notes.append(f"Converted {resource}/{operation}")
    
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
    """
    lines = []
    qs_fields = []
    body_fields = []
    has_return_all = False
    has_filters = False
    
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
    
    # Pattern: body.field = value
    body_assign_pattern = r"body\.(\w+)\s*=\s*([^;]+)"
    for match in re.finditer(body_assign_pattern, ts_code):
        field = match.group(1)
        value_expr = match.group(2).strip()
        py_value = _convert_ts_expression(value_expr, extracted_params)
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
        body_dict = ", ".join(f"'{f}': {v}" for f, v in body_fields)
        lines.append(f"body = {{{body_dict}}}")
    
    # =================================================================
    # Step 7: Extract and convert API call
    # =================================================================
    # Pattern variations:
    # - hunterApiRequest.call(this, 'GET', '/endpoint', {}, qs)
    # - await bitlyApiRequest.call(this, 'POST', '/endpoint', body)
    # - hunterApiRequestAllItems.call(this, 'data', 'GET', '/endpoint', {}, qs)
    
    api_all_pattern = r"(\w+)ApiRequestAllItems\.call\(\s*this\s*,\s*['\"](\w+)['\"],\s*['\"](\w+)['\"],\s*['\"`]([^'\"]+)['\"`](?:\s*,\s*\{\})?(?:\s*,\s*(\w+))?\s*\)"
    api_pattern = r"(\w+)ApiRequest\.call\(\s*this\s*,\s*['\"](\w+)['\"],\s*['\"`]([^'\"]+)['\"`](?:\s*,\s*(\w+|\{\}))?(?:\s*,\s*(\w+))?\s*\)"
    
    api_all_match = re.search(api_all_pattern, ts_code)
    api_match = re.search(api_pattern, ts_code)
    
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
    else:
        # No API call found - add placeholder
        lines.append("# TODO: Implement API call")
        lines.append("response = {}")
    
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
    """
    expr = expr.strip()
    
    # Direct variable reference
    if expr in extracted_params:
        return extracted_params[expr][0]  # Return Python var name
    
    # Already looks like a Python variable (snake_case)
    if re.match(r'^[a-z_][a-z0-9_]*$', expr):
        return _to_snake_case(expr)
    
    # String literal
    if expr.startswith("'") or expr.startswith('"'):
        return expr
    
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
    
    # Property access: filters.type
    if '.' in expr:
        parts = expr.split('.')
        if parts[0] in extracted_params:
            base = extracted_params[parts[0]][0]
            return f"{base}.get('{parts[1]}')"
        return _to_snake_case(expr.replace('.', '_'))
    
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
                    handlers_code += f'''
    def {method_name}(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        {op_display} operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={{"param": param}})
        
        raise NotImplementedError("{op_name} operation not implemented")
'''
    
    # Generate execute routing
    if has_resource_handlers:
        # Resource + operation pattern - build dispatch from handler_map
        dispatch_cases = []
        for (resource, operation) in handler_map.keys():
            if resource:
                method_name = f"_{resource}_{operation}"
                dispatch_cases.append(
                    f'                if resource == "{resource}" and operation == "{operation}":\n'
                    f'                    result = self.{method_name}(i, item_data)'
                )
        
        dispatch_code = "\n                el".join(dispatch_cases) if dispatch_cases else '                pass'
        
        execute_routing = f'''
        for i, item in enumerate(input_data):
            try:
                resource = self.get_node_parameter("resource", i)
                operation = self.get_node_parameter("operation", i)
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
                if self.continue_on_fail:
                    return_items.append(NodeExecutionData(json_data={{"error": str(e)}}))
                else:
                    raise
        
        return [return_items]'''
    else:
        # Operation-only pattern (like Hunter)
        op_dispatch_lines = []
        for i, op in enumerate(operations):
            op_name = op.get("value", op.get("name", ""))
            if op_name:
                if i == 0:
                    op_dispatch_lines.append(f'''                if operation == "{op_name}":
                    result = self._{op_name}(i, item_data)''')
                else:
                    op_dispatch_lines.append(f'''                elif operation == "{op_name}":
                    result = self._{op_name}(i, item_data)''')
        
        op_dispatch = "\n".join(op_dispatch_lines) if op_dispatch_lines else '                pass  # No operations defined'
        
        execute_routing = f'''
        for i, item in enumerate(input_data):
            try:
                operation = self.get_node_parameter("operation", i)
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
                if self.continue_on_fail:
                    return_items.append(NodeExecutionData(json_data={{"error": str(e)}}))
                else:
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
    
    # Extract base URL from api_helpers or use placeholder
    base_url = _extract_base_url(api_helpers)
    
    # Build full Python code following BaseNode pattern
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
from typing import Any, Dict, List

import requests

from .base import BaseNode, NodeParameter, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class {class_name}Node(BaseNode):
    """
    {description.get('displayName', node_name)} node.
    
    {description.get('description', '')}
    """

    node_type = "{node_name.lower()}"
    node_version = {description.get('version', 1)}
    display_name = "{description.get('displayName', node_name)}"
    description = "{description.get('description', '')}"
    icon = "file:{module_name}.svg"
    group = {description.get('group', ['output'])}
    
    credentials = [
        {{
            "name": "{cred_name}",
            "required": True,
        }}
    ]

    properties = {_format_parameters(properties)}

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
        
        # TODO: Configure authentication based on credential type
        query = query or {{}}
        # For API key auth: query["api_key"] = credentials.get("apiKey")
        # For Bearer auth: headers["Authorization"] = f"Bearer {{credentials.get('accessToken')}}"
        
        url = f"{base_url}{{endpoint}}"
        
        response = requests.request(
            method,
            url,
            params=query,
            json=body,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()
{handlers_code}
'''
    
    return python_code


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
