#!/usr/bin/env python3
"""
Full Pipeline: schema-infer → node-scaffold → code-convert

Runs the complete TypeScript to Python node conversion pipeline.
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
print("FULL PIPELINE: TypeScript → Python Node Conversion")
print("=" * 70)
print(f"Correlation ID: {cid}")
print(f"Started: {datetime.now().isoformat()}")
print()

# Clear state
idem_state = artifacts / "idempotency_state.json"
if idem_state.exists():
    idem_state.unlink()

# =============================================================================
# STEP 1: schema-infer
# =============================================================================
print("┌" + "─" * 68 + "┐")
print("│ STEP 1: schema-infer" + " " * 47 + "│")
print("└" + "─" * 68 + "┘")

# Read source files
node_ts = (source_bundle / "Bitly.node.ts").read_text()
generic_ts = (source_bundle / "GenericFunctions.ts").read_text()
link_ts = (source_bundle / "LinkDescription.ts").read_text()

parsed_sections = {
    "node_name": "Bitly",
    "code": [
        {"content": node_ts, "file": "Bitly.node.ts"},
        {"content": generic_ts, "file": "GenericFunctions.ts"},
        {"content": link_ts, "file": "LinkDescription.ts"},
    ]
}

schema_infer_impl = load_skill_impl("schema-infer")
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
# STEP 2: node-scaffold
# =============================================================================
print("┌" + "─" * 68 + "┐")
print("│ STEP 2: node-scaffold" + " " * 46 + "│")
print("└" + "─" * 68 + "┘")

scaffold_impl = load_skill_impl("node-scaffold")
ctx2 = SimpleContext(cid, {
    "correlation_id": cid,
    "node_schema": inferred_schema,
    "normalized_name": "bitly",
}, artifacts)

result2 = scaffold_impl.execute_node_scaffold(ctx2)

if hasattr(result2, 'state'):
    status2 = result2.state.value if hasattr(result2.state, 'value') else str(result2.state)
    outputs2 = result2.outputs or {}
else:
    status2 = result2.get("status", "completed")
    outputs2 = result2.get("outputs", result2)

print(f"  Status: {status2}")
files_created = outputs2.get("files_created", [])
print(f"  Files created: {len(files_created)}")
for f in files_created:
    print(f"    - {Path(f).name}")
print()

# =============================================================================
# STEP 3: code-convert
# =============================================================================
print("┌" + "─" * 68 + "┐")
print("│ STEP 3: code-convert" + " " * 47 + "│")
print("└" + "─" * 68 + "┘")

code_convert_impl = load_skill_impl("code-convert")
if code_convert_impl is None:
    print("  ERROR: code-convert skill not implemented")
else:
    ctx3 = SimpleContext(cid, {
        "correlation_id": cid,
        "source_type": "TYPE1",
        "parsed_sections": parsed_sections,
        "node_schema": inferred_schema,
    }, artifacts)
    
    result3 = code_convert_impl.execute_code_convert(ctx3)
    
    if hasattr(result3, 'state'):
        status3 = result3.state.value if hasattr(result3.state, 'value') else str(result3.state)
        outputs3 = result3.outputs or {}
        errors3 = result3.errors or []
    else:
        status3 = result3.get("status", "unknown")
        outputs3 = result3.get("outputs", result3)
        errors3 = result3.get("errors", [])
    
    print(f"  Status: {status3}")
    
    if errors3:
        print(f"  Errors: {errors3}")
    
    files_modified = outputs3.get("files_modified", [])
    print(f"  Files converted: {len(files_modified)}")
    for f in files_modified:
        print(f"    - {Path(f).name}")
    
    conversion_notes = outputs3.get("conversion_notes", [])
    print(f"  Conversion notes: {len(conversion_notes)}")
    for note in conversion_notes[:5]:
        print(f"    • {note}")

print()

# =============================================================================
# RESULTS
# =============================================================================
print("=" * 70)
print("PIPELINE RESULTS")
print("=" * 70)

# List all artifacts
print("\n📁 Artifacts created:")
for f in sorted(artifacts.rglob("*")):
    if f.is_file() and not f.name.startswith("."):
        rel = f.relative_to(artifacts)
        size = f.stat().st_size
        print(f"  {rel} ({size:,} bytes)")

# Show converted code
converted_dir = artifacts / "converted_node"
if converted_dir.exists():
    print("\n" + "=" * 70)
    print("CONVERTED PYTHON CODE")
    print("=" * 70)
    
    for py_file in sorted(converted_dir.glob("*.py")):
        print(f"\n{'─' * 70}")
        print(f"📄 {py_file.name}")
        print("─" * 70)
        content = py_file.read_text()
        # Show full content for smaller files, truncate larger ones
        lines = content.split("\n")
        if len(lines) <= 150:
            print(content)
        else:
            print("\n".join(lines[:100]))
            print(f"\n... ({len(lines) - 100} more lines)")

print("\n" + "=" * 70)
print(f"Pipeline completed: {datetime.now().isoformat()}")
print("=" * 70)
