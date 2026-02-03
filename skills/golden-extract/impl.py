#!/usr/bin/env python3
"""
Golden Extract Skill Implementation

Extracts working implementations from avidflow-back/nodes/ as behavioral ground truth.
When a golden implementation exists, it becomes the source-of-truth for code-convert.

SOURCE OF TRUTH HIERARCHY (for TYPE1):
1. Golden implementations (existing Python) - HIGHEST PRIORITY
2. TypeScript source extraction - if no golden exists
3. Schema/contract - validation only, NEVER code generation

SYNC-CELERY SAFE: No async patterns, pure file I/O with Path operations.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext

from runtime.protocol import AgentResponse, TaskState


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default path to golden implementations
DEFAULT_GOLDEN_PATH = Path(__file__).parent.parent.parent / "avidflow-back" / "nodes"

# Method name patterns that indicate operation handlers
OPERATION_METHOD_PATTERN = re.compile(r'^_([a-z]+)_([a-zA-Z]+)$')

# Helper method patterns to also extract
HELPER_METHOD_PATTERNS = [
    '_api_request',
    '_api_request_all_items',
    '_get_auth_headers',
    '_http_request',
    '_oauth2_request',
    '_make_request',
]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def execute_golden_extract(ctx: "ExecutionContext") -> AgentResponse:
    """
    Extract golden implementation from avidflow-back/nodes/.
    
    Inputs:
        - correlation_id: str
        - node_name: str (e.g., "github", "gitlab", "hunter")
        - golden_path: Optional[str] - path to golden nodes directory
    
    Outputs:
        - golden_found: bool
        - golden_impl: Dict[str, str] - method_name -> code_body
        - golden_operations: List[Dict] - detected operations
        - golden_snapshot_path: str - path to snapshot file
    """
    inputs = ctx.inputs
    correlation_id = inputs.get("correlation_id", ctx.correlation_id)
    artifacts_dir = ctx.artifacts_dir
    
    # Get node name
    node_name = inputs.get("node_name", "")
    if not node_name:
        return AgentResponse(
            state=TaskState.FAILED,
            errors=["node_name is required"],
        )
    
    # Normalize node name
    node_name_normalized = node_name.lower().replace("node", "").strip()
    
    # Get golden path
    golden_path_str = inputs.get("golden_path", "")
    if golden_path_str:
        golden_path = Path(golden_path_str)
    else:
        golden_path = DEFAULT_GOLDEN_PATH
    
    # Look for golden node file
    golden_file = _find_golden_file(golden_path, node_name_normalized)
    
    if not golden_file:
        # No golden found - this is OK, not a failure
        # Write empty golden_impl.json
        golden_impl_path = artifacts_dir / "golden_impl.json"
        golden_impl_path.parent.mkdir(parents=True, exist_ok=True)
        golden_impl_path.write_text(json.dumps({
            "golden_found": False,
            "node_name": node_name_normalized,
            "searched_path": str(golden_path),
            "message": f"No golden implementation found for '{node_name_normalized}'",
        }, indent=2))
        
        return AgentResponse(
            state=TaskState.COMPLETED,
            outputs={
                "golden_found": False,
                "golden_impl": {},
                "golden_operations": [],
                "golden_snapshot_path": "",
                "message": f"No golden implementation found for '{node_name_normalized}' in {golden_path}",
            },
        )
    
    # Read and parse golden file
    try:
        golden_content = golden_file.read_text()
    except Exception as e:
        return AgentResponse(
            state=TaskState.FAILED,
            errors=[f"Failed to read golden file {golden_file}: {e}"],
        )
    
    # Extract method bodies
    golden_impl, operations, extraction_notes = _extract_golden_methods(golden_content)
    
    if not golden_impl:
        return AgentResponse(
            state=TaskState.FAILED,
            errors=[f"Failed to extract methods from golden file {golden_file}. File may be malformed."],
        )
    
    # Write golden snapshot
    snapshot_path = artifacts_dir / "golden_node_snapshot.py"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(golden_content)
    
    # Write golden_impl.json
    golden_impl_data = {
        "golden_found": True,
        "node_name": node_name_normalized,
        "source_file": str(golden_file),
        "methods": golden_impl,
        "operations": operations,
        "extraction_notes": extraction_notes,
        "extracted_at": datetime.utcnow().isoformat(),
    }
    golden_impl_path = artifacts_dir / "golden_impl.json"
    golden_impl_path.write_text(json.dumps(golden_impl_data, indent=2))
    
    return AgentResponse(
        state=TaskState.COMPLETED,
        outputs={
            "golden_found": True,
            "golden_impl": golden_impl,
            "golden_operations": operations,
            "golden_snapshot_path": str(snapshot_path),
            "source_file": str(golden_file),
            "extraction_notes": extraction_notes,
        },
    )


# =============================================================================
# GOLDEN FILE DISCOVERY
# =============================================================================

def _find_golden_file(golden_path: Path, node_name: str) -> Optional[Path]:
    """
    Find golden node file by name.
    
    Tries multiple naming patterns:
    - github.py
    - github_node.py
    - Github.py
    """
    if not golden_path.exists():
        return None
    
    # Patterns to try
    patterns = [
        f"{node_name}.py",
        f"{node_name}_node.py",
        f"{node_name.capitalize()}.py",
        f"{node_name.capitalize()}Node.py",
    ]
    
    for pattern in patterns:
        candidate = golden_path / pattern
        if candidate.exists():
            return candidate
    
    # Fallback: scan directory for files containing the node name
    for py_file in golden_path.glob("*.py"):
        if py_file.name.startswith("_") or py_file.name == "__init__.py":
            continue
        if node_name.lower() in py_file.stem.lower():
            return py_file
    
    return None


# =============================================================================
# GOLDEN METHOD EXTRACTION
# =============================================================================

def _extract_golden_methods(source: str) -> Tuple[Dict[str, str], List[Dict], List[str]]:
    """
    Extract method bodies from golden Python source.
    
    Returns:
        (methods_dict, operations_list, extraction_notes)
        
        methods_dict: {method_name: code_body}
        operations_list: [{"resource": "...", "operation": "..."}, ...]
        extraction_notes: List of notes about extraction
    """
    methods = {}
    operations = []
    notes = []
    
    # Parse with AST for accurate extraction
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        notes.append(f"AST parse failed: {e}")
        # Fall back to regex extraction
        return _extract_golden_methods_regex(source)
    
    # Find the node class
    node_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.endswith("Node"):
            node_class = node
            break
    
    if not node_class:
        notes.append("No Node class found in source")
        return _extract_golden_methods_regex(source)
    
    notes.append(f"Found class: {node_class.name}")
    
    # Extract all methods
    source_lines = source.split('\n')
    
    for item in node_class.body:
        if isinstance(item, ast.FunctionDef):
            method_name = item.name
            
            # Get method source using line numbers
            start_line = item.lineno - 1
            end_line = item.end_lineno if hasattr(item, 'end_lineno') else _find_method_end(source_lines, start_line)
            
            method_source = '\n'.join(source_lines[start_line:end_line])
            methods[method_name] = method_source
            
            # Check if this is an operation handler
            op_match = OPERATION_METHOD_PATTERN.match(method_name)
            if op_match:
                resource = op_match.group(1)
                operation = op_match.group(2)
                operations.append({
                    "resource": resource,
                    "operation": operation,
                    "method_name": method_name,
                })
    
    notes.append(f"Extracted {len(methods)} methods, {len(operations)} operations")
    
    # Also extract class attributes
    class_attrs = _extract_class_attributes(source, node_class.name)
    methods["__class_attributes__"] = class_attrs
    
    return methods, operations, notes


def _extract_golden_methods_regex(source: str) -> Tuple[Dict[str, str], List[Dict], List[str]]:
    """
    Fallback regex-based method extraction when AST fails.
    """
    methods = {}
    operations = []
    notes = ["Using regex fallback extraction"]
    
    # Pattern for method definitions
    method_pattern = re.compile(
        r'^    def (\w+)\(self[^)]*\)(?:\s*->\s*[^:]+)?:\s*\n((?:        .*\n)*)',
        re.MULTILINE
    )
    
    for match in method_pattern.finditer(source):
        method_name = match.group(1)
        method_body = match.group(0)
        methods[method_name] = method_body
        
        # Check if operation handler
        op_match = OPERATION_METHOD_PATTERN.match(method_name)
        if op_match:
            operations.append({
                "resource": op_match.group(1),
                "operation": op_match.group(2),
                "method_name": method_name,
            })
    
    notes.append(f"Regex extracted {len(methods)} methods, {len(operations)} operations")
    
    return methods, operations, notes


def _find_method_end(lines: List[str], start_line: int) -> int:
    """Find the end line of a method by indentation."""
    if start_line >= len(lines):
        return start_line + 1
    
    # Get base indentation of the def line
    base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
    
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        
        # Skip empty lines
        if not line.strip():
            continue
        
        current_indent = len(line) - len(line.lstrip())
        
        # If we find a line with same or less indentation, method ended
        if current_indent <= base_indent:
            return i
    
    return len(lines)


def _extract_class_attributes(source: str, class_name: str) -> str:
    """
    Extract class-level attributes (type, version, description, properties).
    """
    # Find the class body
    class_pattern = re.compile(
        rf'class {class_name}\([^)]*\):\s*\n((?:    [^\n]+\n)*)',
        re.MULTILINE
    )
    
    match = class_pattern.search(source)
    if match:
        return match.group(1)
    return ""


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_golden_has_implementations(golden_impl: Dict[str, str]) -> List[str]:
    """
    Validate that golden implementation has real code, not stubs.
    
    Returns list of validation errors (empty if valid).
    """
    errors = []
    
    stub_patterns = [
        r'#\s*TODO:\s*Implement',
        r'response\s*=\s*\{\s*\}',
        r'raise\s+NotImplementedError',
        r'^\s*pass\s*$',
    ]
    
    for method_name, method_body in golden_impl.items():
        if method_name.startswith('_') and not method_name.startswith('__'):
            # This is an operation or helper method
            for pattern in stub_patterns:
                if re.search(pattern, method_body, re.MULTILINE):
                    errors.append(f"Golden method '{method_name}' contains stub pattern: {pattern}")
    
    return errors
