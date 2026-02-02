"""
contract-validate skill

Mechanically validates execution contracts to enforce ≥80% correctness threshold.
Rejects node conversions with hard-fail invariant violations or insufficient completeness.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from contracts.validator import validate_contract_file, load_contract_from_yaml
from contracts.node_contract import ContractValidationResult


def validate_contract(
    correlation_id: str,
    contract_path: Optional[str] = None,
    artifacts_dir: str = "artifacts"
) -> Dict[str, Any]:
    """
    Validate execution contract and enforce quality threshold.
    
    Args:
        correlation_id: Unique workflow identifier
        contract_path: Path to contract YAML (default: artifacts/{id}/node.contract.yaml)
        artifacts_dir: Base artifacts directory
        
    Returns:
        Dict with validation result including pass/fail status and score breakdown
        
    Raises:
        FileNotFoundError: If contract file doesn't exist
        ValueError: If contract is invalid YAML or fails validation
    """
    # Resolve paths
    artifact_path = Path(artifacts_dir) / correlation_id
    artifact_path.mkdir(parents=True, exist_ok=True)
    
    if contract_path is None:
        contract_path = str(artifact_path / "node.contract.yaml")
    
    contract_file = Path(contract_path)
    if not contract_file.exists():
        raise FileNotFoundError(f"Contract file not found: {contract_path}")
    
    # Validate contract
    result = validate_contract_file(str(contract_file), verbose=False)
    
    # Write validation result
    result_path = artifact_path / "validation_result.json"
    result_data = {
        "correlation_id": correlation_id,
        "contract_path": str(contract_file),
        "score": result.score,
        "passed": result.acceptable,
        "hard_fail_violations": result.hard_fail_violations,
        "score_breakdown": {
            "completeness": result.contract_completeness_score,
            "side_effects": result.side_effects_score,
            "execution": result.execution_semantics_score,
            "n8n": result.n8n_normalization_score
        },
        "validation_errors": [],
        "warnings": result.warnings,
        "recommendations": result.recommendations
    }
    
    with open(result_path, 'w') as f:
        json.dump(result_data, f, indent=2)
    
    return result_data


def main():
    """CLI entry point for contract-validate skill."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate execution contract for node conversion"
    )
    parser.add_argument(
        "--correlation-id",
        required=True,
        help="Unique workflow identifier"
    )
    parser.add_argument(
        "--contract-path",
        help="Path to contract YAML (default: artifacts/{id}/node.contract.yaml)"
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Base artifacts directory"
    )
    
    args = parser.parse_args()
    
    try:
        result = validate_contract(
            correlation_id=args.correlation_id,
            contract_path=args.contract_path,
            artifacts_dir=args.artifacts_dir
        )
        
        # Print result
        status = "✅ PASSED" if result["passed"] else "❌ FAILED"
        print(f"\nContract Validation: {status}")
        print(f"Score: {result['score']}/100")
        print(f"\nScore Breakdown:")
        print(f"  • Completeness: {result['score_breakdown']['completeness']}/40")
        print(f"  • Side-Effects: {result['score_breakdown']['side_effects']}/25")
        print(f"  • Execution: {result['score_breakdown']['execution']}/25")
        print(f"  • n8n: {result['score_breakdown']['n8n']}/10")
        
        if result["hard_fail_violations"]:
            print(f"\n❌ Hard-Fail Violations:")
            for violation in result["hard_fail_violations"]:
                print(f"  • {violation}")
        
        if result["validation_errors"]:
            print(f"\n⚠️  Validation Errors:")
            for error in result["validation_errors"]:
                print(f"  • {error}")
        
        # Exit with appropriate code
        sys.exit(0 if result["passed"] else 1)
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
