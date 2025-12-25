#!/usr/bin/env python3
"""
Trace Map Validator

Validates trace map completeness for schema-infer skill outputs.
Ensures every schema field has a documented source (API_DOCS, SOURCE_CODE, or ASSUMPTION).

Uses canonical Pydantic models from contracts/ package.
Canonical format: JSON only (not YAML).

Run: python scripts/validate_trace_map.py <trace_map.json>
"""

import sys
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from contracts import (
    TraceSource,
    ConfidenceLevel,
    TraceEntry,
    TraceMap,
)


def load_trace_map(path: Path) -> dict[str, Any] | None:
    """
    Load trace map from file (JSON preferred, YAML supported for migration).
    
    Canonical format: JSON
    """
    try:
        content = path.read_text()
        
        # Prefer JSON parsing
        if path.suffix == ".json":
            return json.loads(content)
        elif path.suffix in (".yaml", ".yml"):
            print("WARNING: YAML format is deprecated, please convert to JSON")
            return yaml.safe_load(content)
        else:
            # Try JSON first, then YAML
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return yaml.safe_load(content)
                
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        print(f"ERROR: Parse error: {e}")
        return None
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}")
        return None


def validate_with_pydantic(data: dict[str, Any]) -> tuple[list[str], TraceMap | None]:
    """
    Validate trace map using Pydantic models.
    
    Returns: (errors, validated_model)
    """
    errors = []
    
    try:
        # Convert trace_entries to TraceEntry models
        entries = []
        for i, entry_data in enumerate(data.get("trace_entries", [])):
            try:
                # Convert source string to enum
                source = entry_data.get("source", "ASSUMPTION")
                try:
                    source_enum = TraceSource(source)
                except ValueError:
                    errors.append(f"Entry {i}: Invalid source '{source}' (must be API_DOCS, SOURCE_CODE, or ASSUMPTION)")
                    source_enum = TraceSource.ASSUMPTION
                
                # Convert confidence string to enum
                confidence = entry_data.get("confidence", "low")
                try:
                    confidence_enum = ConfidenceLevel(confidence)
                except ValueError:
                    errors.append(f"Entry {i}: Invalid confidence '{confidence}' (must be high, medium, or low)")
                    confidence_enum = ConfidenceLevel.LOW
                
                entry = TraceEntry(
                    field_path=entry_data.get("field_path", f"unknown_{i}"),
                    source=source_enum,
                    evidence=entry_data.get("evidence", ""),
                    confidence=confidence_enum,
                    assumption_rationale=entry_data.get("assumption_rationale"),
                    source_file=entry_data.get("source_file"),
                    line_range=entry_data.get("line_range"),
                    excerpt_hash=entry_data.get("excerpt_hash"),
                    verified=entry_data.get("verified", False),
                )
                entries.append(entry)
                
                # Check ASSUMPTION rationale requirement
                if entry.source == TraceSource.ASSUMPTION and not entry.assumption_rationale:
                    errors.append(f"Entry {i}: ASSUMPTION entries must include 'assumption_rationale'")
                    
            except ValidationError as e:
                for err in e.errors():
                    loc = ".".join(str(x) for x in err["loc"])
                    errors.append(f"Entry {i}.{loc}: {err['msg']}")
        
        # Create TraceMap model
        trace_map = TraceMap(
            correlation_id=data.get("correlation_id", "UNKNOWN"),
            node_type=data.get("node_type", "UNKNOWN"),
            trace_entries=entries,
            generated_at=data.get("generated_at"),
            skill_version=data.get("skill_version"),
        )
        
        # Check required top-level fields
        if "correlation_id" not in data:
            errors.append("Missing 'correlation_id' at top level")
        if "node_type" not in data:
            errors.append("Missing 'node_type' at top level")
        if not entries:
            errors.append("No trace_entries found - trace map cannot be empty")
        
        # Check assumption ratio
        if trace_map.assumption_ratio() > 0.30:
            errors.append(f"Too many ASSUMPTION entries ({trace_map.assumption_ratio():.0%}) - max 30% allowed for IMPLEMENT autonomy")
        
        return errors, trace_map
        
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            errors.append(f"Validation error at {loc}: {err['msg']}")
        return errors, None
    except Exception as e:
        errors.append(f"Unexpected error: {e}")
        return errors, None


def extract_schema_fields(schema: dict[str, Any], prefix: str = "") -> list[str]:
    """Recursively extract all field paths from a JSON schema."""
    fields = []
    
    if schema.get("type") == "object":
        props = schema.get("properties", {})
        for name, prop_schema in props.items():
            field_path = f"{prefix}.{name}" if prefix else name
            fields.append(field_path)
            fields.extend(extract_schema_fields(prop_schema, field_path))
    
    elif schema.get("type") == "array":
        items = schema.get("items", {})
        item_path = f"{prefix}[*]" if prefix else "[*]"
        fields.extend(extract_schema_fields(items, item_path))
    
    return fields


def validate_against_schema(
    trace_map: TraceMap, 
    schema: dict[str, Any]
) -> list[str]:
    """
    Validate trace map covers all schema fields.
    
    Returns list of untraced field paths.
    """
    schema_fields = set(extract_schema_fields(schema))
    traced_fields = set(e.field_path for e in trace_map.trace_entries)
    
    untraced = schema_fields - traced_fields
    return list(sorted(untraced))


def main() -> int:
    """Main validation function."""
    if len(sys.argv) < 2:
        print("Usage: validate_trace_map.py <trace_map.json> [schema.json]")
        print()
        print("Examples:")
        print("  validate_trace_map.py artifacts/ABC123/trace_map.json")
        print("  validate_trace_map.py trace.json schema.json  # Also check schema coverage")
        print()
        print("NOTE: JSON is the canonical format. YAML is deprecated.")
        return 1
    
    trace_path = Path(sys.argv[1])
    schema_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    # Load trace map
    data = load_trace_map(trace_path)
    if data is None:
        return 1
    
    print(f"Validating trace map: {trace_path}")
    print(f"  Correlation ID: {data.get('correlation_id', 'N/A')}")
    print(f"  Node type: {data.get('node_type', 'N/A')}")
    print()
    
    # Validate with Pydantic
    errors, trace_map = validate_with_pydantic(data)
    
    if trace_map:
        print("Coverage Stats:")
        print(f"  Total entries: {len(trace_map.trace_entries)}")
        
        # Count by source
        by_source = {s.value: 0 for s in TraceSource}
        by_confidence = {c.value: 0 for c in ConfidenceLevel}
        
        for entry in trace_map.trace_entries:
            by_source[entry.source.value] += 1
            by_confidence[entry.confidence.value] += 1
        
        print(f"  By source: {by_source}")
        print(f"  By confidence: {by_confidence}")
        print(f"  Assumption ratio: {trace_map.assumption_ratio():.0%}")
        print(f"  Valid for IMPLEMENT: {trace_map.is_valid_for_implement()}")
        print()
    
    # Validate against schema if provided
    if schema_path and trace_map:
        schema = load_trace_map(schema_path)  # Load schema (same format support)
        if schema:
            untraced = validate_against_schema(trace_map, schema)
            if untraced:
                print(f"Untraced schema fields ({len(untraced)}):")
                for field in untraced:
                    print(f"  - {field}")
                errors.append(f"{len(untraced)} schema fields have no trace entry")
    
    # Report results
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for error in errors:
            print(f"  ✗ {error}")
        return 1
    else:
        print("\n✓ Trace map is valid and complete (Pydantic validated)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
