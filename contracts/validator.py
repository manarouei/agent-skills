#!/usr/bin/env python3
"""
Contract Validator - Mechanical Contract Enforcement

Validates node contracts and provides deterministic accept/reject decisions.

Usage:
    python -m contracts.validator validate github.contract.yaml
    python -m contracts.validator score redis.contract.yaml
    python -m contracts.validator batch contracts/

SYNC-CELERY SAFE: No I/O operations, pure validation logic.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import ValidationError

from .node_contract import (
    NodeContract,
    ContractValidationResult,
    validate_contract,
)


def load_contract_from_yaml(path: Path) -> Optional[NodeContract]:
    """Load and parse contract from YAML file."""
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return NodeContract(**data)
    except FileNotFoundError:
        print(f"❌ Contract file not found: {path}", file=sys.stderr)
        return None
    except ValidationError as e:
        print(f"❌ Contract validation failed for {path}:", file=sys.stderr)
        print(e, file=sys.stderr)
        return None
    except Exception as e:
        print(f"❌ Failed to load contract {path}: {e}", file=sys.stderr)
        return None


def format_validation_result(result: ContractValidationResult, verbose: bool = False) -> str:
    """Format validation result for console output."""
    lines = []
    
    # Status
    if result.acceptable:
        lines.append(f"✅ ACCEPTED - Score: {result.score}/100")
    elif result.valid:
        lines.append(f"⚠️  REJECTED - Score: {result.score}/100 (below 80 threshold)")
    else:
        lines.append(f"❌ HARD-FAIL - Score: {result.score}/100")
    
    # Score breakdown
    lines.append(f"\n📊 Score Breakdown:")
    lines.append(f"  • Contract Completeness: {result.contract_completeness_score}/40")
    lines.append(f"  • Side-Effects & Credentials: {result.side_effects_score}/25")
    lines.append(f"  • Execution Semantics: {result.execution_semantics_score}/25")
    lines.append(f"  • n8n Normalization: {result.n8n_normalization_score}/10")
    
    # Hard-fail violations
    if result.hard_fail_violations:
        lines.append(f"\n🚨 HARD-FAIL VIOLATIONS ({len(result.hard_fail_violations)}):")
        for violation in result.hard_fail_violations:
            lines.append(f"  • {violation}")
    
    # Warnings
    if verbose and result.warnings:
        lines.append(f"\n⚠️  Warnings ({len(result.warnings)}):")
        for warning in result.warnings:
            lines.append(f"  • {warning}")
    
    # Recommendations
    if verbose and result.recommendations:
        lines.append(f"\n💡 Recommendations ({len(result.recommendations)}):")
        for rec in result.recommendations:
            lines.append(f"  • {rec}")
    
    return "\n".join(lines)


def validate_contract_file(path: Path, verbose: bool = False) -> ContractValidationResult:
    """
    Validate a single contract file.
    
    Returns ContractValidationResult with score and pass/fail status.
    """
    path = Path(path)  # Convert string to Path if needed
    print(f"\n{'='*70}")
    print(f"Validating: {path.name}")
    print(f"{'='*70}")
    
    contract = load_contract_from_yaml(path)
    if contract is None:
        # Return failed result
        return ContractValidationResult(
            valid=False,
            score=0,
            acceptable=False,
            contract_completeness_score=0,
            side_effects_score=0,
            execution_semantics_score=0,
            n8n_normalization_score=0,
            hard_fail_violations=["Failed to load contract from YAML"],
            warnings=[],
            recommendations=[]
        )
    
    try:
        result = validate_contract(contract)
        print(format_validation_result(result, verbose=verbose))
        return result
    except Exception as e:
        print(f"❌ Validation error: {e}", file=sys.stderr)
        return ContractValidationResult(
            valid=False,
            score=0,
            acceptable=False,
            contract_completeness_score=0,
            side_effects_score=0,
            execution_semantics_score=0,
            n8n_normalization_score=0,
            hard_fail_violations=[f"Exception during validation: {str(e)}"],
            warnings=[],
            recommendations=[]
        )


def batch_validate(directory: Path, verbose: bool = False) -> Dict[str, bool]:
    """
    Validate all .contract.yaml files in directory.
    
    Returns dict mapping filename to acceptance status.
    """
    results = {}
    
    contract_files = list(directory.glob("*.contract.yaml"))
    if not contract_files:
        print(f"⚠️  No .contract.yaml files found in {directory}", file=sys.stderr)
        return results
    
    print(f"\n🔍 Found {len(contract_files)} contract files")
    
    for path in sorted(contract_files):
        accepted = validate_contract_file(path, verbose=verbose)
        results[path.name] = accepted
    
    # Summary
    accepted_count = sum(1 for v in results.values() if v)
    rejected_count = len(results) - accepted_count
    
    print(f"\n{'='*70}")
    print(f"📈 BATCH SUMMARY")
    print(f"{'='*70}")
    print(f"✅ Accepted: {accepted_count}/{len(results)}")
    print(f"❌ Rejected: {rejected_count}/{len(results)}")
    
    if rejected_count > 0:
        print(f"\n🚨 Rejected contracts:")
        for name, accepted in results.items():
            if not accepted:
                print(f"  • {name}")
    
    return results


def generate_contract_template(
    node_type: str, 
    semantic_class: str,
    output_path: Optional[Path] = None
) -> str:
    """Generate a contract template for a node type."""
    
    template = {
        "node_type": node_type,
        "version": "1.0.0",
        "semantic_class": semantic_class,
        "input_schema": {
            "fields": [
                {
                    "name": "example_field",
                    "type": "string",
                    "required": True,
                    "description": "Example input field"
                }
            ],
            "additional_properties": False,
            "strict": True
        },
        "output_schema": {
            "success_fields": [
                {
                    "name": "result",
                    "type": "object",
                    "description": "Operation result"
                }
            ],
            "error_fields": [
                {
                    "name": "error",
                    "type": "string",
                    "description": "Error message"
                }
            ],
            "deterministic": True
        },
        "error_categories": ["validation", "timeout", "unknown"],
        "side_effects": {
            "types": ["network"] if semantic_class == "http_rest" else ["database"],
            "network_destinations": ["api.example.org"] if semantic_class == "http_rest" else None,
            "database_operations": ["read", "write"] if semantic_class == "tcp_client" else None
        },
        "credential_scope": {
            "credential_type": f"{node_type}Api",
            "required": True,
            "host_allowlist": ["api.example.org"] if semantic_class == "http_rest" else None,
            "database_allowlist": ["production_db"] if semantic_class == "tcp_client" else None
        },
        "execution_semantics": {
            "timeout_seconds": 60,
            "retry_policy": "none",
            "idempotent": False,
            "transactional": False,
            "max_retries": 0,
            "retry_delay_seconds": 1
        },
        "n8n_normalization": {
            "defaults_explicit": True,
            "expression_boundaries": [],
            "eval_disabled": False
        },
        "generated_by": "contract-validator/template",
        "correlation_id": "template-001",
        "generated_at": "2026-02-02T00:00:00Z"
    }
    
    yaml_content = yaml.dump(template, default_flow_style=False, sort_keys=False)
    
    if output_path:
        output_path.write_text(yaml_content)
        print(f"✅ Template written to: {output_path}")
    
    return yaml_content


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate node execution contracts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single contract
  python -m contracts.validator validate github.contract.yaml
  
  # Validate with verbose output
  python -m contracts.validator validate --verbose redis.contract.yaml
  
  # Batch validate directory
  python -m contracts.validator batch contracts/
  
  # Generate template
  python -m contracts.validator template --node-type redis --semantic-class tcp_client
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a single contract")
    validate_parser.add_argument("contract_file", type=Path, help="Path to .contract.yaml file")
    validate_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Validate all contracts in directory")
    batch_parser.add_argument("directory", type=Path, help="Directory containing .contract.yaml files")
    batch_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    # Template command
    template_parser = subparsers.add_parser("template", help="Generate contract template")
    template_parser.add_argument("--node-type", required=True, help="Node type (e.g., redis)")
    template_parser.add_argument(
        "--semantic-class", 
        required=True, 
        choices=["http_rest", "tcp_client", "sdk_client", "pure_transform", "stateful"],
        help="Semantic class"
    )
    template_parser.add_argument("--output", "-o", type=Path, help="Output file path")
    
    args = parser.parse_args()
    
    if args.command == "validate":
        accepted = validate_contract_file(args.contract_file, verbose=args.verbose)
        sys.exit(0 if accepted else 1)
    
    elif args.command == "batch":
        results = batch_validate(args.directory, verbose=args.verbose)
        all_accepted = all(results.values())
        sys.exit(0 if all_accepted else 1)
    
    elif args.command == "template":
        generate_contract_template(
            args.node_type,
            args.semantic_class,
            args.output
        )
        sys.exit(0)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
