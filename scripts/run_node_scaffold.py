#!/usr/bin/env python3
"""Run the node-scaffold skill on the inferred schema."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CID_FILE = Path("/tmp/correlation_id.txt")

cid = CID_FILE.read_text().strip()
artifacts = PROJECT_ROOT / "artifacts" / cid

print(f"Correlation ID: {cid}")
print(f"Artifacts: {artifacts}")

# Clear idempotency state
idem_state = artifacts / "idempotency_state.json"
if idem_state.exists():
    idem_state.unlink()
    print("Cleared idempotency state")

# Load inferred schema
schema_path = artifacts / "inferred_schema.json"
if not schema_path.exists():
    print("Error: No inferred schema. Run schema-infer first.")
    exit(1)

inferred_schema = json.loads(schema_path.read_text())
print(f"Loaded schema for node: {inferred_schema['type']}")

# Import executor
import sys
sys.path.insert(0, str(PROJECT_ROOT))
from runtime.executor import create_executor

executor = create_executor(PROJECT_ROOT, register_implementations=True)
print(f"Skills with implementations: {list(executor._implementations.keys())}")

# Prepare inputs matching node-scaffold contract
inputs = {
    "correlation_id": cid,
    "node_schema": inferred_schema,  # renamed from inferred_schema
    "normalized_name": inferred_schema['type'].lower(),  # e.g. "bitly"
}

# Run node-scaffold
print("\n" + "=" * 50)
print("Running node-scaffold skill...")
print("=" * 50)

result = executor.execute("node-scaffold", inputs, cid)

print(f"\nResult:")
print(f"  Status: {result.status.value}")
print(f"  Is Terminal: {result.is_terminal}")
print(f"  Agent State: {result.agent_state}")
print(f"  Duration: {result.duration_ms}ms")

if result.errors:
    print(f"\nErrors:")
    for err in result.errors[:5]:
        print(f"  - {err}")

if result.outputs:
    print(f"\nOutput keys: {list(result.outputs.keys())}")
    
    if "scaffold_files" in result.outputs:
        print(f"\nScaffolded files:")
        for f in result.outputs["scaffold_files"]:
            print(f"  - {f}")
    
    if "generated_code" in result.outputs:
        code = result.outputs["generated_code"]
        if isinstance(code, dict):
            print(f"\nGenerated code preview:")
            for fname, content in list(code.items())[:2]:
                print(f"\n  === {fname} (first 500 chars) ===")
                print(content[:500] if isinstance(content, str) else str(content)[:500])

# List artifacts
print(f"\nArtifacts:")
for f in sorted(artifacts.iterdir()):
    if f.is_file():
        print(f"  {f.name} ({f.stat().st_size} bytes)")
