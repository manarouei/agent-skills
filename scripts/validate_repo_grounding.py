#!/usr/bin/env python3
"""
Repo Grounding Gate Validator

Ensures IMPLEMENT/COMMIT skills have proper repo context before execution.
This gate verifies that the agent has consulted canonical grounding sources
and recorded them in artifacts/{correlation_id}/repo_facts.json.

Policy references:
- .copilot/agent.md: "Repo-grounded: read actual repo files before decisions"
- .copilot/policy.yaml: confirmation_required_if.modifies_basenode/node_loader

Run: python3 scripts/validate_repo_grounding.py <artifacts_dir> [--correlation-id ID]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Canonical grounding sources that MUST be consulted for node work
REQUIRED_GROUNDING_FIELDS = {
    "basenode_contract_path": {
        "description": "Path to BaseNode contract (BASENODE_CONTRACT.md or basenode_contract.py)",
        "example": "contracts/BASENODE_CONTRACT.md",
    },
    "node_loader_paths": {
        "description": "Paths to node registration/loading mechanisms",
        "example": ["contracts/basenode_contract.py", "runtime/executor.py"],
    },
    "golden_node_paths": {
        "description": "Paths to reference node implementations consulted",
        "example": ["/home/toni/n8n/back/nodes/telegram.py"],
    },
    "test_command": {
        "description": "Command to run tests for validation",
        "example": "python3 -m pytest -q",
    },
}

# Optional but recommended fields
OPTIONAL_GROUNDING_FIELDS = {
    "basenode_source_path": {
        "description": "Path to actual BaseNode class source (external repo)",
        "example": "/home/toni/n8n/back/nodes/base.py",
    },
    "node_registry_path": {
        "description": "Path to node registry file",
        "example": "/home/toni/n8n/back/nodes/__init__.py",
    },
    "schema_consulted": {
        "description": "JSON schema files consulted",
        "example": [".copilot/schemas/trace_map.schema.json"],
    },
    "policy_version": {
        "description": "Hash or timestamp of policy files when grounding was done",
        "example": "sha256:abc123",
    },
}


class RepoGroundingValidator:
    """Validates repo grounding facts for bounded autonomy compliance."""

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(self, correlation_id: str | None = None) -> bool:
        """
        Validate repo grounding for a correlation ID or all correlations.
        
        Returns True if valid, False otherwise.
        """
        if correlation_id:
            return self._validate_single(correlation_id)
        
        # Validate all correlation IDs in artifacts dir
        if not self.artifacts_dir.exists():
            self.errors.append(f"Artifacts directory does not exist: {self.artifacts_dir}")
            return False
        
        correlation_dirs = [d for d in self.artifacts_dir.iterdir() if d.is_dir()]
        if not correlation_dirs:
            self.errors.append("No correlation directories found in artifacts")
            return False
        
        all_valid = True
        for corr_dir in correlation_dirs:
            if not self._validate_single(corr_dir.name):
                all_valid = False
        
        return all_valid

    def _validate_single(self, correlation_id: str) -> bool:
        """Validate repo grounding for a single correlation ID."""
        corr_dir = self.artifacts_dir / correlation_id
        repo_facts_path = corr_dir / "repo_facts.json"
        
        if not corr_dir.exists():
            self.errors.append(f"Correlation directory does not exist: {corr_dir}")
            return False
        
        if not repo_facts_path.exists():
            self.errors.append(
                f"Missing repo_facts.json for {correlation_id}\n"
                f"  Required for IMPLEMENT/COMMIT autonomy levels.\n"
                f"  Create: {repo_facts_path}\n"
                f"  Required fields: {list(REQUIRED_GROUNDING_FIELDS.keys())}"
            )
            return False
        
        try:
            with open(repo_facts_path) as f:
                repo_facts = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {repo_facts_path}: {e}")
            return False
        
        return self._validate_repo_facts(repo_facts, correlation_id)

    def _validate_repo_facts(self, repo_facts: dict[str, Any], correlation_id: str) -> bool:
        """Validate the contents of repo_facts.json."""
        valid = True
        
        # Check required fields
        for field, spec in REQUIRED_GROUNDING_FIELDS.items():
            if field not in repo_facts:
                self.errors.append(
                    f"[{correlation_id}] Missing required field: {field}\n"
                    f"  Description: {spec['description']}\n"
                    f"  Example: {spec['example']}"
                )
                valid = False
            elif not repo_facts[field]:
                self.errors.append(
                    f"[{correlation_id}] Empty value for required field: {field}"
                )
                valid = False
        
        # Validate field types and content
        if valid:
            valid = self._validate_field_content(repo_facts, correlation_id)
        
        # Check optional fields (warnings only)
        for field, spec in OPTIONAL_GROUNDING_FIELDS.items():
            if field not in repo_facts:
                self.warnings.append(
                    f"[{correlation_id}] Missing optional field: {field} - {spec['description']}"
                )
        
        return valid

    def _validate_field_content(self, repo_facts: dict[str, Any], correlation_id: str) -> bool:
        """Validate field content beyond just presence."""
        valid = True
        
        # basenode_contract_path must be a string path
        basenode_path = repo_facts.get("basenode_contract_path")
        if basenode_path and not isinstance(basenode_path, str):
            self.errors.append(f"[{correlation_id}] basenode_contract_path must be a string")
            valid = False
        
        # node_loader_paths must be a list
        loader_paths = repo_facts.get("node_loader_paths")
        if loader_paths and not isinstance(loader_paths, list):
            self.errors.append(f"[{correlation_id}] node_loader_paths must be a list")
            valid = False
        elif loader_paths and len(loader_paths) == 0:
            self.errors.append(f"[{correlation_id}] node_loader_paths cannot be empty")
            valid = False
        
        # golden_node_paths must be a list with at least one entry
        golden_paths = repo_facts.get("golden_node_paths")
        if golden_paths and not isinstance(golden_paths, list):
            self.errors.append(f"[{correlation_id}] golden_node_paths must be a list")
            valid = False
        elif golden_paths and len(golden_paths) == 0:
            self.warnings.append(
                f"[{correlation_id}] golden_node_paths is empty - "
                "recommend consulting at least one reference implementation"
            )
        
        # test_command must be a non-empty string
        test_cmd = repo_facts.get("test_command")
        if test_cmd and not isinstance(test_cmd, str):
            self.errors.append(f"[{correlation_id}] test_command must be a string")
            valid = False
        elif test_cmd and len(test_cmd.strip()) == 0:
            self.errors.append(f"[{correlation_id}] test_command cannot be empty")
            valid = False
        
        return valid

    def print_report(self) -> None:
        """Print validation report."""
        if self.errors:
            print("\nErrors (MUST FIX):")
            for error in self.errors:
                print(f"  ✗ {error}")
        
        if self.warnings:
            print("\nWarnings (RECOMMENDED):")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✓ Repo grounding is complete and valid")
        elif not self.errors:
            print("\n✓ Repo grounding is valid (with warnings)")


def create_example_repo_facts(output_path: Path) -> None:
    """Create an example repo_facts.json file."""
    example = {
        "basenode_contract_path": "contracts/BASENODE_CONTRACT.md",
        "node_loader_paths": [
            "contracts/basenode_contract.py",
            "runtime/executor.py",
        ],
        "golden_node_paths": [
            "/home/toni/n8n/back/nodes/telegram.py",
        ],
        "test_command": "python3 -m pytest -q",
        "basenode_source_path": "/home/toni/n8n/back/nodes/base.py",
        "node_registry_path": "/home/toni/n8n/back/nodes/__init__.py",
        "schema_consulted": [
            ".copilot/schemas/trace_map.schema.json",
        ],
        "policy_version": "2025-12-26",
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(example, f, indent=2)
    
    print(f"Created example repo_facts.json at: {output_path}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate repo grounding facts for bounded autonomy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all correlations in artifacts/
  python3 scripts/validate_repo_grounding.py artifacts/

  # Validate specific correlation
  python3 scripts/validate_repo_grounding.py artifacts/ --correlation-id abc-123

  # Create example repo_facts.json
  python3 scripts/validate_repo_grounding.py --create-example artifacts/test-123/repo_facts.json
""",
    )
    parser.add_argument(
        "artifacts_dir",
        nargs="?",
        type=Path,
        default=Path("artifacts"),
        help="Path to artifacts directory",
    )
    parser.add_argument(
        "--correlation-id",
        type=str,
        help="Validate specific correlation ID only",
    )
    parser.add_argument(
        "--create-example",
        type=Path,
        metavar="PATH",
        help="Create example repo_facts.json at specified path",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    
    args = parser.parse_args()
    
    # Create example mode
    if args.create_example:
        create_example_repo_facts(args.create_example)
        return 0
    
    # Validation mode
    print(f"Validating repo grounding in: {args.artifacts_dir}")
    if args.correlation_id:
        print(f"  Correlation ID: {args.correlation_id}")
    
    validator = RepoGroundingValidator(args.artifacts_dir)
    valid = validator.validate(args.correlation_id)
    
    if args.json:
        result = {
            "valid": valid,
            "errors": validator.errors,
            "warnings": validator.warnings,
        }
        print(json.dumps(result, indent=2))
    else:
        validator.print_report()
    
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
