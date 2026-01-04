#!/usr/bin/env python3
"""Run the schema-infer skill on the Bitly node."""

import json
import re
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent
CID_FILE = Path("/tmp/correlation_id.txt")

if not CID_FILE.exists():
    print("Error: No correlation ID found. Run the setup first.")
    exit(1)

cid = CID_FILE.read_text().strip()
artifacts = PROJECT_ROOT / "artifacts" / cid
source_bundle = artifacts / "source_bundle"

print(f"Correlation ID: {cid}")
print(f"Source bundle: {source_bundle}")

# Clear idempotency state for fresh run
idem_state = artifacts / "idempotency_state.json"
if idem_state.exists():
    idem_state.unlink()
    print("Cleared idempotency state")

# Read TypeScript sources
node_ts = (source_bundle / "Bitly.node.ts").read_text()
generic_ts = (source_bundle / "GenericFunctions.ts").read_text()
link_ts = (source_bundle / "LinkDescription.ts").read_text()

# Parse sections in the format expected by schema-infer impl
# The impl expects 'code' array with {content, file} entries
parsed_sections = {
    "node_name": "Bitly",
    "code": [
        {"content": node_ts, "file": "Bitly.node.ts"},
        {"content": generic_ts, "file": "GenericFunctions.ts"},
        {"content": link_ts, "file": "LinkDescription.ts"},
    ]
}

# Preview what we're sending
print(f"\nParsed sections:")
print(f"  Node name: {parsed_sections['node_name']}")
print(f"  Code files: {[c['file'] for c in parsed_sections['code']]}")
print(f"  Total code size: {sum(len(c['content']) for c in parsed_sections['code'])} chars")

# Import executor
import sys
sys.path.insert(0, str(PROJECT_ROOT))
from runtime.executor import create_executor

# Create executor with implementations
executor = create_executor(PROJECT_ROOT, register_implementations=True)
print(f"\nSkills with implementations: {list(executor._implementations.keys())}")

# Prepare inputs
inputs = {
    "correlation_id": cid,
    "source_type": "TYPE1",
    "parsed_sections": parsed_sections,
    "source_url": "file://Bitly.node.ts",
}

# Run schema-infer
print("\n" + "=" * 50)
print("Running schema-infer skill...")
print("=" * 50)

result = executor.execute("schema-infer", inputs, cid)

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
    
    if "inferred_schema" in result.outputs:
        schema = result.outputs["inferred_schema"]
        print(f"\nInferred Schema:")
        print(json.dumps(schema, indent=2)[:1500])
    
    if "trace_map" in result.outputs:
        trace = result.outputs["trace_map"]
        print(f"\nTrace Map entries: {len(trace.get('trace_entries', []))}")

# List artifacts
print(f"\nArtifacts created:")
for f in sorted(artifacts.iterdir()):
    if f.is_file():
        print(f"  {f.name} ({f.stat().st_size} bytes)")
