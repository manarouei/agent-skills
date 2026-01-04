#!/usr/bin/env python3
"""Pipeline status summary for the Bitly conversion."""

import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
CID_FILE = Path("/tmp/correlation_id.txt")

cid = CID_FILE.read_text().strip()
artifacts = PROJECT_ROOT / "artifacts" / cid

print("=" * 60)
print("PIPELINE STATUS REPORT")
print("=" * 60)
print(f"Correlation ID: {cid}")
print(f"Generated: {datetime.now().isoformat()}")
print()

# Skills and their implementations
import sys
sys.path.insert(0, str(PROJECT_ROOT))
from runtime.executor import create_executor
executor = create_executor(PROJECT_ROOT, register_implementations=True)

print("SKILL IMPLEMENTATIONS:")
print("-" * 40)
skills = [
    "node-normalize",
    "source-classify", 
    "source-ingest",
    "schema-infer",
    "schema-build",
    "node-scaffold",
    "code-convert",    # TYPE1
    "code-implement",  # TYPE2
    "test-generate",
    "code-validate",
    "code-fix",
    "pr-prepare"
]

for skill in skills:
    has_impl = "✅" if skill in executor._implementations else "❌ (stub)"
    print(f"  {skill}: {has_impl}")

print()
print("ARTIFACTS PRODUCED:")
print("-" * 40)
for f in sorted(artifacts.iterdir()):
    if f.is_file():
        size = f.stat().st_size
        print(f"  {f.name}: {size:,} bytes")
    elif f.is_dir():
        count = len(list(f.iterdir()))
        print(f"  {f.name}/: {count} files")

print()
print("PIPELINE EXECUTION STATUS:")
print("-" * 40)

# Check each step
steps = []

# 1. Source bundle
source_bundle = artifacts / "source_bundle"
if source_bundle.exists():
    files = list(source_bundle.iterdir())
    steps.append(("source-bundle", "✅ COMPLETE", f"{len(files)} files"))
else:
    steps.append(("source-bundle", "❌ MISSING", "N/A"))

# 2. Schema inference
schema_path = artifacts / "inferred_schema.json"
trace_path = artifacts / "trace_map.json"
if schema_path.exists():
    schema = json.loads(schema_path.read_text())
    steps.append(("schema-infer", "✅ COMPLETE", f"Node: {schema['type']}"))
    
    if trace_path.exists():
        trace = json.loads(trace_path.read_text())
        entries = len(trace.get("trace_entries", []))
        assumptions = sum(1 for e in trace["trace_entries"] if e.get("source") == "ASSUMPTION")
        ratio = (assumptions / entries * 100) if entries else 0
        steps.append(("trace-map", "✅ VALID" if ratio <= 30 else "⚠️ HIGH ASSUMPTIONS", 
                     f"{entries} entries, {ratio:.0f}% assumptions"))
else:
    steps.append(("schema-infer", "❌ NOT RUN", "N/A"))
    steps.append(("trace-map", "❌ NOT RUN", "N/A"))

# 3. Node scaffold
scaffold = artifacts / "scaffold_manifest.json"
if scaffold.exists():
    steps.append(("node-scaffold", "✅ COMPLETE", "Files generated"))
else:
    steps.append(("node-scaffold", "⏸️ BLOCKED", "45 files > 20 limit"))

# 4. Code conversion
code_dir = artifacts / "generated_code"
if code_dir.exists():
    steps.append(("code-convert", "✅ COMPLETE", ""))
else:
    steps.append(("code-convert", "⏸️ NOT RUN", "No implementation"))

for step_name, status, detail in steps:
    print(f"  {step_name}: {status}")
    if detail:
        print(f"    └── {detail}")

print()
print("NEXT ACTIONS NEEDED:")
print("-" * 40)

# Check what's blocking
if not schema_path.exists():
    print("  1. Run schema-infer skill")
elif trace_path.exists():
    trace = json.loads(trace_path.read_text())
    entries = trace.get("trace_entries", [])
    operations = [e for e in entries if "operation" in e.get("field_path", "")]
    print(f"  Schema inferred {len(operations)} operations")
    
    # Filter out false positives
    bad_ops = [e for e in operations if e.get("evidence", "").split("'")[1] in ("if", "for", "while", "switch")]
    if bad_ops:
        print(f"  ⚠️  {len(bad_ops)} false positives detected (control flow keywords)")
        print("  → Improve schema-infer regex patterns")
    
if "code-convert" not in executor._implementations:
    print("  → Implement code-convert skill (TYPE1 conversion)")
if "code-implement" not in executor._implementations:
    print("  → Implement code-implement skill (TYPE2 from docs)")

print()
print("=" * 60)
