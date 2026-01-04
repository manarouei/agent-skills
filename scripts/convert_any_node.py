#!/usr/bin/env python3
"""
Generic Node Converter: schema-infer → node-scaffold → code-convert

Converts any n8n TypeScript node to Python using the agent-skills pipeline.

Usage:
    python3 scripts/convert_any_node.py <correlation_id>
    
Expected structure:
    artifacts/<correlation_id>/source_bundle/
        - <NodeName>.node.ts    (required - main node file)
        - GenericFunctions.ts   (required - API helper functions)
        - *Description.ts       (optional - resource descriptions)
"""

import json
import sys
import re
import importlib.util
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_skill_impl(skill_name: str):
    """Load skill impl.py by path (handles hyphenated names)."""
    impl_path = PROJECT_ROOT / "skills" / skill_name / "impl.py"
    if not impl_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"{skill_name}_impl", impl_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SimpleContext:
    """Minimal context for direct skill execution."""
    def __init__(self, cid: str, inputs: dict, artifacts_dir: Path):
        self.correlation_id = cid
        self.inputs = inputs
        self.artifacts_dir = artifacts_dir
    
    def log(self, event: str, data: dict):
        pass


def detect_node_name(source_bundle: Path) -> str:
    """Detect node name from the .node.ts file."""
    node_files = list(source_bundle.glob("*.node.ts"))
    if not node_files:
        raise FileNotFoundError("No *.node.ts file found in source bundle")
    
    # Extract name: "Hunter.node.ts" → "Hunter"
    node_file = node_files[0]
    return node_file.stem.replace(".node", "")


def read_source_files(source_bundle: Path) -> tuple[str, dict]:
    """Read all TypeScript files from source bundle.
    
    Returns:
        (node_name, parsed_sections)
    """
    ts_files = sorted(source_bundle.glob("*.ts"))
    if not ts_files:
        raise FileNotFoundError(f"No TypeScript files in {source_bundle}")
    
    node_name = detect_node_name(source_bundle)
    code_sections = []
    
    for ts_file in ts_files:
        code_sections.append({
            "content": ts_file.read_text(),
            "file": ts_file.name,
        })
    
    parsed_sections = {
        "node_name": node_name,
        "code": code_sections,
    }
    
    return node_name, parsed_sections


def run_schema_infer(cid: str, parsed_sections: dict, artifacts: Path) -> dict:
    """Run schema-infer skill."""
    print("┌" + "─" * 68 + "┐")
    print("│ STEP 1: schema-infer" + " " * 47 + "│")
    print("└" + "─" * 68 + "┘")
    
    schema_infer_impl = load_skill_impl("schema-infer")
    if schema_infer_impl is None:
        raise RuntimeError("schema-infer skill not found")
    
    ctx = SimpleContext(cid, {
        "correlation_id": cid,
        "source_type": "TYPE1",
        "parsed_sections": parsed_sections,
    }, artifacts)
    
    result = schema_infer_impl.execute_schema_infer(ctx)
    print(f"  Status: {result.state.value}")
    
    inferred_schema = result.outputs.get("inferred_schema", {})
    trace_map = result.outputs.get("trace_map", {})
    operations = inferred_schema.get("operations", [])
    
    print(f"  Node: {inferred_schema.get('type', 'unknown')}")
    print(f"  Operations: {len(operations)}")
    for op in operations[:5]:  # Show first 5
        print(f"    - {op.get('name', 'unnamed')}")
    print(f"  Trace entries: {len(trace_map.get('trace_entries', []))}")
    
    # Save artifacts
    (artifacts / "inferred_schema.json").write_text(json.dumps(inferred_schema, indent=2))
    (artifacts / "trace_map.json").write_text(json.dumps(trace_map, indent=2))
    print(f"  Saved: inferred_schema.json, trace_map.json")
    print()
    
    return inferred_schema, trace_map


def run_node_scaffold(cid: str, node_name: str, inferred_schema: dict, artifacts: Path) -> dict:
    """Run node-scaffold skill."""
    print("┌" + "─" * 68 + "┐")
    print("│ STEP 2: node-scaffold" + " " * 46 + "│")
    print("└" + "─" * 68 + "┘")
    
    scaffold_impl = load_skill_impl("node-scaffold")
    if scaffold_impl is None:
        raise RuntimeError("node-scaffold skill not found")
    
    # Normalize name: "Hunter" → "hunter"
    normalized_name = node_name.lower()
    
    ctx = SimpleContext(cid, {
        "correlation_id": cid,
        "node_schema": inferred_schema,
        "normalized_name": normalized_name,
    }, artifacts)
    
    result = scaffold_impl.execute_node_scaffold(ctx)
    
    if hasattr(result, 'state'):
        status = result.state.value if hasattr(result.state, 'value') else str(result.state)
        outputs = result.outputs or {}
    else:
        status = result.get("status", "completed")
        outputs = result.get("outputs", result)
    
    print(f"  Status: {status}")
    files_created = outputs.get("files_created", [])
    print(f"  Files created: {len(files_created)}")
    for f in files_created:
        print(f"    - {Path(f).name}")
    print()
    
    return outputs


def run_code_convert(cid: str, parsed_sections: dict, inferred_schema: dict, artifacts: Path) -> dict:
    """Run code-convert skill."""
    print("┌" + "─" * 68 + "┐")
    print("│ STEP 3: code-convert" + " " * 47 + "│")
    print("└" + "─" * 68 + "┘")
    
    code_convert_impl = load_skill_impl("code-convert")
    if code_convert_impl is None:
        print("  ⚠ code-convert skill not implemented - skipping")
        print()
        return {}
    
    ctx = SimpleContext(cid, {
        "correlation_id": cid,
        "source_type": "TYPE1",
        "parsed_sections": parsed_sections,
        "node_schema": inferred_schema,
    }, artifacts)
    
    result = code_convert_impl.execute_code_convert(ctx)
    
    if hasattr(result, 'state'):
        status = result.state.value if hasattr(result.state, 'value') else str(result.state)
        outputs = result.outputs or {}
    else:
        status = result.get("status", "completed")
        outputs = result.get("outputs", result)
    
    print(f"  Status: {status}")
    
    converted_files = outputs.get("converted_files", [])
    if converted_files:
        print(f"  Converted files: {len(converted_files)}")
        for f in converted_files:
            print(f"    - {f}")
    print()
    
    return outputs


def create_request_snapshot(cid: str, node_name: str, source_files: list, artifacts: Path):
    """Create request snapshot for audit trail."""
    snapshot = {
        "correlation_id": cid,
        "timestamp": datetime.utcnow().isoformat(),
        "source_type": "TYPE1",
        "source_files": source_files,
        "node_name": node_name,
        "target_language": "python",
    }
    
    snapshot_path = artifacts / "request_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2))
    return snapshot


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/convert_any_node.py <correlation_id>")
        print()
        print("Example:")
        print("  python3 scripts/convert_any_node.py convert-hunter-421aa861a8")
        sys.exit(1)
    
    cid = sys.argv[1]
    artifacts = PROJECT_ROOT / "artifacts" / cid
    source_bundle = artifacts / "source_bundle"
    
    if not artifacts.exists():
        print(f"Error: Artifacts directory not found: {artifacts}")
        sys.exit(1)
    
    if not source_bundle.exists():
        print(f"Error: Source bundle not found: {source_bundle}")
        sys.exit(1)
    
    # Banner
    print("=" * 70)
    print("GENERIC NODE CONVERSION PIPELINE")
    print("=" * 70)
    print(f"Correlation ID: {cid}")
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    # Clear idempotency state
    idem_state = artifacts / "idempotency_state.json"
    if idem_state.exists():
        idem_state.unlink()
    
    # Read source files
    node_name, parsed_sections = read_source_files(source_bundle)
    source_files = [s["file"] for s in parsed_sections["code"]]
    
    print(f"Node Name: {node_name}")
    print(f"Source Files: {source_files}")
    print()
    
    # Create request snapshot
    create_request_snapshot(cid, node_name, source_files, artifacts)
    
    # Run pipeline
    inferred_schema, trace_map = run_schema_infer(cid, parsed_sections, artifacts)
    scaffold_outputs = run_node_scaffold(cid, node_name, inferred_schema, artifacts)
    convert_outputs = run_code_convert(cid, parsed_sections, inferred_schema, artifacts)
    
    # Summary
    print("=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"Artifacts directory: {artifacts}")
    print()
    print("Generated files:")
    for f in artifacts.iterdir():
        if f.is_file():
            print(f"  - {f.name}")
    
    # List converted_node/ if exists
    converted_dir = artifacts / "converted_node"
    if converted_dir.exists():
        print()
        print("Converted node files:")
        for f in converted_dir.iterdir():
            print(f"  - converted_node/{f.name}")
    
    print()
    print(f"Completed: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
