#!/usr/bin/env python3
"""
Skill Contract Validator

Validates that all skills in registry.yaml have valid contracts using Pydantic models.
Uses the canonical contract definitions from contracts/ package.

Run: python scripts/validate_skill_contracts.py
"""

import sys
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from contracts import (
    AutonomyLevel,
    SideEffect,
    RetryPolicy,
    FailureMode,
    SkillContract,
    RetryConfig,
    IdempotencyConfig,
    ArtifactSpec,
    ValidationResult,
)


# Legacy field names for backwards compatibility during transition
REQUIRED_CONTRACT_FIELDS = [
    "name",
    "version", 
    "description",
    "autonomy_level",
    "side_effects",
    "timeout_seconds",
    "retry",
    "idempotency",
    "input_schema",
    "output_schema",
    "required_artifacts",
    "failure_modes",
    "depends_on",
]


def parse_skill_frontmatter(skill_path: Path) -> dict[str, Any] | None:
    """Parse YAML frontmatter from SKILL.md file."""
    content = skill_path.read_text()
    
    # Extract frontmatter between --- markers
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        print(f"  ERROR: YAML parse error: {e}")
        return None


def validate_with_pydantic(skill_name: str, data: dict[str, Any]) -> list[str]:
    """
    Validate skill contract using Pydantic models.
    
    This is the canonical validation method using the models from contracts/.
    """
    errors = []
    
    try:
        # Convert YAML data to Pydantic model
        # Transform side_effects strings to SideEffect enum
        side_effects = []
        for se in data.get("side_effects", []):
            try:
                side_effects.append(SideEffect(se))
            except ValueError:
                errors.append(f"Invalid side_effect: {se} (valid: {[e.value for e in SideEffect]})")
        
        # Convert autonomy_level string to enum
        try:
            autonomy = AutonomyLevel(data.get("autonomy_level", "READ"))
        except ValueError:
            errors.append(f"Invalid autonomy_level: {data.get('autonomy_level')}")
            autonomy = AutonomyLevel.READ
        
        # Convert retry config
        retry_data = data.get("retry", {})
        try:
            retry_policy = RetryPolicy(retry_data.get("policy", "none"))
        except ValueError:
            errors.append(f"Invalid retry policy: {retry_data.get('policy')}")
            retry_policy = RetryPolicy.NONE
        
        retry = RetryConfig(
            policy=retry_policy,
            max_retries=retry_data.get("max_retries", 0),
            backoff_seconds=retry_data.get("backoff_seconds", 1.0),
        )
        
        # Convert idempotency config
        idem_data = data.get("idempotency", {})
        idempotency = IdempotencyConfig(
            required=idem_data.get("required", False),
            key_spec=idem_data.get("key_spec"),
        )
        
        # Convert required_artifacts
        artifacts = []
        for art in data.get("required_artifacts", []):
            if isinstance(art, dict):
                artifacts.append(ArtifactSpec(
                    name=art.get("name", "unnamed"),
                    type=art.get("type", "file"),
                    description=art.get("description", ""),
                ))
            else:
                errors.append(f"Invalid artifact spec: {art}")
        
        # Convert failure_modes strings to FailureMode enum
        failure_modes = []
        for fm in data.get("failure_modes", []):
            try:
                failure_modes.append(FailureMode(fm))
            except ValueError:
                errors.append(f"Invalid failure_mode: {fm} (valid: {[e.value for e in FailureMode]})")
        
        # Create the contract model (this validates all fields)
        contract = SkillContract(
            name=data.get("name", ""),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            autonomy_level=autonomy,
            side_effects=side_effects,
            timeout_seconds=data.get("timeout_seconds", 60),
            retry=retry,
            idempotency=idempotency,
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            required_artifacts=artifacts,
            failure_modes=failure_modes,
            depends_on=data.get("depends_on", []),
        )
        
        # Additional name validation
        if contract.name != skill_name:
            errors.append(f"Name mismatch: contract has '{contract.name}', expected '{skill_name}'")
        
    except ValidationError as e:
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            errors.append(f"Validation error at {loc}: {error['msg']}")
    except Exception as e:
        errors.append(f"Unexpected error: {e}")
    
    return errors


def validate_contract_legacy(skill_name: str, contract: dict[str, Any]) -> list[str]:
    """
    Legacy validation (pre-Pydantic) - kept for reference.
    
    DEPRECATED: Use validate_with_pydantic() instead.
    """
    errors = []
    
    # Check required fields
    for field in REQUIRED_CONTRACT_FIELDS:
        if field not in contract:
            errors.append(f"Missing required field: {field}")
    
    # Validate name matches directory
    if contract.get("name") != skill_name:
        errors.append(f"Name mismatch: contract has '{contract.get('name')}', expected '{skill_name}'")
    
    # Validate version format (semver)
    version = contract.get("version", "")
    if not re.match(r"^\d+\.\d+\.\d+$", str(version).strip('"')):
        errors.append(f"Invalid version format: {version} (expected semver X.Y.Z)")
    
    return errors


def main() -> int:
    """Main validation function."""
    repo_root = Path(__file__).parent.parent
    registry_path = repo_root / "registry.yaml"
    
    if not registry_path.exists():
        print("ERROR: registry.yaml not found")
        return 1
    
    # Load registry
    with open(registry_path) as f:
        registry = yaml.safe_load(f)
    
    skills = registry.get("skills", [])
    if not skills:
        print("ERROR: No skills found in registry")
        return 1
    
    print(f"Validating {len(skills)} skills using Pydantic models...\n")
    
    total_errors = 0
    validated = 0
    
    for skill_entry in skills:
        skill_name = skill_entry.get("name")
        skill_path = repo_root / skill_entry.get("path", f"skills/{skill_name}/SKILL.md")
        
        print(f"[{skill_name}]")
        
        if not skill_path.exists():
            print(f"  ERROR: SKILL.md not found at {skill_path}")
            total_errors += 1
            continue
        
        data = parse_skill_frontmatter(skill_path)
        if data is None:
            print("  ERROR: Could not parse YAML frontmatter")
            total_errors += 1
            continue
        
        # Use Pydantic validation (canonical)
        errors = validate_with_pydantic(skill_name, data)
        
        if errors:
            for error in errors:
                print(f"  ERROR: {error}")
            total_errors += len(errors)
        else:
            print("  ✓ Valid (Pydantic)")
            validated += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {validated}/{len(skills)} skills valid")
    print(f"Total errors: {total_errors}")
    
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
