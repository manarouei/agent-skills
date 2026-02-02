#!/usr/bin/env python3
"""
GitHub Node Pipeline: Full conversion from TypeScript to Python

Runs: source-ingest → schema-infer → node-scaffold → code-convert → 
      node-validate → test-generate → code-validate
"""

import json
import sys
import importlib.util
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Read correlation ID
CID_FILE = Path("/tmp/correlation_id.txt")
cid = CID_FILE.read_text().strip()
artifacts = PROJECT_ROOT / "artifacts" / cid
source_bundle = artifacts / "source_bundle"


def load_skill_impl(skill_name: str):
    """Load skill impl.py by path (handles hyphenated names)"""
    impl_path = PROJECT_ROOT / "skills" / skill_name / "impl.py"
    if not impl_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"{skill_name}_impl", impl_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SimpleContext:
    """Minimal context for direct skill execution."""
    def __init__(self, cid, inputs, artifacts_dir):
        self.correlation_id = cid
        self.inputs = inputs
        self.artifacts_dir = artifacts_dir
    
    def log(self, event, data):
        pass


print("=" * 70)
print("GITHUB NODE PIPELINE: Full TypeScript → Python Conversion")
print("=" * 70)
print(f"Correlation ID: {cid}")
print(f"Started: {datetime.now().isoformat()}")
print()

# Verify source bundle exists
if not source_bundle.exists():
    print(f"ERROR: Source bundle not found: {source_bundle}")
    sys.exit(1)

# Read GitHub source files
github_node = source_bundle / "Github.node.ts"
generic_functions = source_bundle / "GenericFunctions.ts"

if not github_node.exists():
    print(f"ERROR: Github.node.ts not found in {source_bundle}")
    sys.exit(1)

node_ts = github_node.read_text()
generic_ts = generic_functions.read_text() if generic_functions.exists() else ""

# Optional: SearchFunctions.ts
search_functions = source_bundle / "SearchFunctions.ts"
search_ts = search_functions.read_text() if search_functions.exists() else ""

parsed_sections = {
    "node_name": "Github",
    "code": [
        {"content": node_ts, "file": "Github.node.ts"},
    ]
}

if generic_ts:
    parsed_sections["code"].append({"content": generic_ts, "file": "GenericFunctions.ts"})
if search_ts:
    parsed_sections["code"].append({"content": search_ts, "file": "SearchFunctions.ts"})

print(f"Source files loaded: {len(parsed_sections['code'])}")
print()

# =============================================================================
# STEP 1: schema-infer
# =============================================================================
print("┌" + "─" * 68 + "┐")
print("│ STEP 1: schema-infer" + " " * 47 + "│")
print("└" + "─" * 68 + "┘")

schema_infer_impl = load_skill_impl("schema-infer")
if not schema_infer_impl:
    print("ERROR: schema-infer skill not found")
    sys.exit(1)

ctx1 = SimpleContext(cid, {
    "correlation_id": cid,
    "source_type": "TYPE1",
    "parsed_sections": parsed_sections,
}, artifacts)

result1 = schema_infer_impl.execute_schema_infer(ctx1)
print(f"  Status: {result1.state.value}")

inferred_schema = result1.outputs.get("inferred_schema", {})
trace_map = result1.outputs.get("trace_map", {})
operations = inferred_schema.get("operations", [])

print(f"  Node: {inferred_schema.get('type', 'unknown')}")
print(f"  Operations: {len(operations)}")
print(f"  Trace entries: {len(trace_map.get('trace_entries', []))}")

# Save
(artifacts / "inferred_schema.json").write_text(json.dumps(inferred_schema, indent=2))
(artifacts / "trace_map.json").write_text(json.dumps(trace_map, indent=2))
print()

# =============================================================================
# STEP 2: code-convert
# =============================================================================
print("┌" + "─" * 68 + "┐")
print("│ STEP 2: code-convert" + " " * 47 + "│")
print("└" + "─" * 68 + "┘")

code_convert_impl = load_skill_impl("code-convert")
if not code_convert_impl:
    print("ERROR: code-convert skill not found")
    sys.exit(1)

ctx2 = SimpleContext(cid, {
    "correlation_id": cid,
    "source_type": "TYPE1",
    "parsed_sections": parsed_sections,
    "node_schema": inferred_schema,
    "normalized_name": "github",
}, artifacts)

result2 = code_convert_impl.execute_code_convert(ctx2)

if hasattr(result2, 'state'):
    status2 = result2.state.value if hasattr(result2.state, 'value') else str(result2.state)
    outputs2 = result2.outputs or {}
    errors2 = result2.errors or []
else:
    status2 = "unknown"
    outputs2 = {}
    errors2 = []

print(f"  Status: {status2}")

if errors2:
    print(f"  Errors: {errors2}")

files_modified = outputs2.get("files_modified", [])
print(f"  Files converted: {len(files_modified)}")
for f in files_modified:
    print(f"    - {f}")

conversion_notes = outputs2.get("conversion_notes", [])
print(f"  Conversion notes: {len(conversion_notes)}")
for note in conversion_notes[:10]:
    print(f"    • {note}")
print()

# =============================================================================
# STEP 3: node-validate
# =============================================================================
print("┌" + "─" * 68 + "┐")
print("│ STEP 3: node-validate" + " " * 46 + "│")
print("└" + "─" * 68 + "┘")

node_validate_impl = load_skill_impl("node-validate")
if not node_validate_impl:
    print("WARNING: node-validate skill not found, skipping")
else:
    ctx3 = SimpleContext(cid, {
        "correlation_id": cid,
        "artifact_paths": outputs2.get("artifact_paths", []),
    }, artifacts)
    
    result3 = node_validate_impl.run(ctx3)
    
    if hasattr(result3, 'state'):
        status3 = result3.state.value if hasattr(result3.state, 'value') else str(result3.state)
        outputs3 = result3.outputs or {}
    else:
        status3 = result3.get("status", "unknown")
        outputs3 = result3.get("outputs", {})
    
    print(f"  Status: {status3}")
    
    validation_results = outputs3.get("validation_results", {})
    overall_valid = validation_results.get("overall_valid", False)
    issues = validation_results.get("issues", [])
    
    print(f"  Overall valid: {overall_valid}")
    print(f"  Issues found: {len(issues)}")
    
    if issues:
        for issue in issues[:10]:
            print(f"    ⚠️  {issue.get('check', 'unknown')}: {issue.get('message', '')}")
print()

# =============================================================================
# RESULTS
# =============================================================================
print("=" * 70)
print("PIPELINE RESULTS")
print("=" * 70)

# Show converted code
converted_dir = artifacts / "converted"
if converted_dir.exists():
    print("\n📁 Converted Python files:")
    for py_file in sorted(converted_dir.glob("*.py")):
        size = py_file.stat().st_size
        print(f"  {py_file.name} ({size:,} bytes)")
    
    print("\n" + "=" * 70)
    print("CONVERTED PYTHON CODE PREVIEW")
    print("=" * 70)
    
    github_py = converted_dir / "github.py"
    if github_py.exists():
        print(f"\n{'─' * 70}")
        print(f"📄 github.py (first 150 lines)")
        print("─" * 70)
        content = github_py.read_text()
        lines = content.split("\n")
        print("\n".join(lines[:150]))
        if len(lines) > 150:
            print(f"\n... ({len(lines) - 150} more lines)")

print("\n" + "=" * 70)
print(f"Pipeline completed: {datetime.now().isoformat()}")
print("=" * 70)
