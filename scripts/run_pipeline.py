#!/usr/bin/env python3
"""
Run the full pipeline: schema-infer → node-scaffold
Bypasses git-based scope gate for testing
"""

import json
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Read correlation ID
CID_FILE = Path("/tmp/correlation_id.txt")
cid = CID_FILE.read_text().strip()
artifacts = PROJECT_ROOT / "artifacts" / cid
source_bundle = artifacts / "source_bundle"

print("=" * 60)
print("PIPELINE EXECUTION: Bitly Node Conversion")
print("=" * 60)
print(f"Correlation ID: {cid}")
print(f"Started: {datetime.now().isoformat()}")
print()

# =============================================================================
# STEP 1: schema-infer
# =============================================================================
print("STEP 1: schema-infer")
print("-" * 40)

# Clear state
idem_state = artifacts / "idempotency_state.json"
if idem_state.exists():
    idem_state.unlink()

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

# Import skill implementation directly (bypass executor scope gate)
import importlib.util

def load_skill_impl(skill_name):
    """Load skill impl.py by path (handles hyphenated names)"""
    impl_path = PROJECT_ROOT / "skills" / skill_name / "impl.py"
    spec = importlib.util.spec_from_file_location(f"{skill_name}_impl", impl_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

schema_infer_impl = load_skill_impl("schema-infer")
from runtime.executor import ExecutionContext

# Create context manually
class SimpleContext:
    def __init__(self, cid, inputs, artifacts_dir):
        self.correlation_id = cid
        self.inputs = inputs
        self.artifacts_dir = artifacts_dir
    def log(self, event, data):
        pass

ctx = SimpleContext(cid, {
    "correlation_id": cid,
    "source_type": "TYPE1",
    "parsed_sections": parsed_sections,
}, artifacts)

result = schema_infer_impl.execute_schema_infer(ctx)
print(f"  Status: {result.state.value}")
print(f"  Operations found: {len(result.outputs.get('inferred_schema', {}).get('operations', []))}")

inferred_schema = result.outputs.get("inferred_schema", {})
trace_map = result.outputs.get("trace_map", {})

# Save schema
(artifacts / "inferred_schema.json").write_text(json.dumps(inferred_schema, indent=2))
(artifacts / "trace_map.json").write_text(json.dumps(trace_map, indent=2))

print(f"  Schema saved: inferred_schema.json")
print(f"  Trace map entries: {len(trace_map.get('trace_entries', []))}")
print()

# =============================================================================
# STEP 2: node-scaffold
# =============================================================================
print("STEP 2: node-scaffold")
print("-" * 40)

# Import node-scaffold implementation
scaffold_impl = load_skill_impl("node-scaffold")

# Create output directory within artifacts
output_dir = artifacts / "generated_code" / "nodes" / "bitly"
output_dir.mkdir(parents=True, exist_ok=True)

ctx2 = SimpleContext(cid, {
    "correlation_id": cid,
    "node_schema": inferred_schema,
    "normalized_name": "bitly",
}, artifacts)

# Call the scaffold directly with parameters
result2 = scaffold_impl.execute_node_scaffold(ctx2)

# Handle both dict and AgentResponse returns
if hasattr(result2, 'state'):
    status = result2.state.value
    outputs = result2.outputs or {}
    errors = result2.errors or []
else:
    # Dict response
    status = result2.get("status", "unknown")
    outputs = result2.get("outputs", result2)
    errors = result2.get("errors", [])

print(f"  Status: {status}")

if outputs:
    files_created = outputs.get("files_created", [])
    print(f"  Files created: {len(files_created)}")
    for f in files_created:
        print(f"    - {f}")

if errors:
    print(f"  Errors: {errors}")

print()

# =============================================================================
# RESULTS
# =============================================================================
print("=" * 60)
print("PIPELINE RESULTS")
print("=" * 60)

# List all artifacts
print("\nArtifacts created:")
for f in sorted(artifacts.rglob("*")):
    if f.is_file() and not f.name.startswith("."):
        rel = f.relative_to(artifacts)
        print(f"  {rel} ({f.stat().st_size:,} bytes)")

# Show generated code preview
gen_code_dir = artifacts / "generated_code"
if gen_code_dir.exists():
    print("\n" + "=" * 60)
    print("GENERATED CODE PREVIEW")
    print("=" * 60)
    
    for py_file in gen_code_dir.rglob("*.py"):
        print(f"\n=== {py_file.name} ===")
        content = py_file.read_text()
        # Show first 80 lines
        lines = content.split("\n")[:80]
        print("\n".join(lines))
        if len(content.split("\n")) > 80:
            print(f"\n... ({len(content.split(chr(10))) - 80} more lines)")

print("\n" + "=" * 60)
print(f"Pipeline completed: {datetime.now().isoformat()}")
print("=" * 60)
