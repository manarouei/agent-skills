"""
Tests for contract-validate skill
"""

import json
import pytest
import sys
from pathlib import Path

# Import validate_contract function directly
skills_dir = Path(__file__).parent.parent / "skills"
sys.path.insert(0, str(skills_dir))

# Import from the skill module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "contract_validate",
    skills_dir / "contract-validate" / "__init__.py"
)
contract_validate_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract_validate_module)
validate_contract = contract_validate_module.validate_contract


def test_validate_github_contract(tmp_path):
    """Test validation of GitHub golden reference contract."""
    # Setup
    correlation_id = "test-github-001"
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    
    # Copy GitHub contract to test artifacts
    github_contract = Path("contracts/github.contract.yaml")
    if not github_contract.exists():
        pytest.skip("GitHub contract not found")
    
    artifact_path = artifacts_dir / correlation_id
    artifact_path.mkdir()
    test_contract = artifact_path / "node.contract.yaml"
    test_contract.write_text(github_contract.read_text())
    
    # Execute
    result = validate_contract(
        correlation_id=correlation_id,
        artifacts_dir=str(artifacts_dir)
    )
    
    # Verify
    assert result["passed"] is True
    assert result["score"] >= 80
    assert len(result["hard_fail_violations"]) == 0
    
    # Check result file was created
    result_file = artifact_path / "validation_result.json"
    assert result_file.exists()
    
    result_data = json.loads(result_file.read_text())
    assert result_data["correlation_id"] == correlation_id
    assert result_data["score"] >= 80


def test_validate_contract_missing_file(tmp_path):
    """Test validation fails gracefully when contract file is missing."""
    correlation_id = "test-missing-001"
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    
    # Don't create contract file
    with pytest.raises(FileNotFoundError):
        validate_contract(
            correlation_id=correlation_id,
            artifacts_dir=str(artifacts_dir)
        )


def test_validate_contract_with_hard_fail(tmp_path):
    """Test validation correctly detects hard-fail violations."""
    correlation_id = "test-hardfail-001"
    artifacts_dir = tmp_path / "artifacts"
    artifact_path = artifacts_dir / correlation_id
    artifact_path.mkdir(parents=True)
    
    # Create contract with hard-fail violation (retry without idempotency)
    bad_contract = """
node_type: test
version: "1.0.0"
semantic_class: http_rest

input_schema:
  fields:
    - name: operation
      type: string
      required: true

output_schema:
  success_fields:
    - name: result
      type: object
  error_fields:
    - name: error
      type: object

side_effects:
  types: [network]
  network_destinations: [api.test.com]

credential_scope:
  credential_type: testApi
  required: true
  host_allowlist: [api.test.com]

execution_semantics:
  timeout_seconds: 60
  retry_policy: transient
  idempotent: false
  max_retries: 2  # HARD-FAIL: Retry without idempotency!
  retry_delay_seconds: 2

n8n_normalization:
  defaults_explicit: true
  expression_boundaries: []
  eval_disabled: false
"""
    
    contract_path = artifact_path / "node.contract.yaml"
    contract_path.write_text(bad_contract)
    
    # Execute
    result = validate_contract(
        correlation_id=correlation_id,
        artifacts_dir=str(artifacts_dir)
    )
    
    # Verify
    assert result["passed"] is False
    assert len(result["hard_fail_violations"]) > 0
    assert any("max_retries" in v.lower() for v in result["hard_fail_violations"])


def test_validate_contract_low_score(tmp_path):
    """Test validation fails when score is below threshold."""
    correlation_id = "test-lowscore-001"
    artifacts_dir = tmp_path / "artifacts"
    artifact_path = artifacts_dir / correlation_id
    artifact_path.mkdir(parents=True)
    
    # Create minimal contract (will have low score)
    minimal_contract = """
node_type: test
version: "1.0.0"
semantic_class: http_rest

input_schema:
  fields: []

output_schema:
  success_fields: []
  error_fields: []

side_effects:
  types: []

credential_scope:
  credential_type: none
  required: false

execution_semantics:
  timeout_seconds: 60
  retry_policy: none
  idempotent: true
  max_retries: 0
  retry_delay_seconds: 1

n8n_normalization:
  defaults_explicit: false
  expression_boundaries: []
  eval_disabled: false
"""
    
    contract_path = artifact_path / "node.contract.yaml"
    contract_path.write_text(minimal_contract)
    
    # Execute
    result = validate_contract(
        correlation_id=correlation_id,
        artifacts_dir=str(artifacts_dir)
    )
    
    # Verify - should fail due to low completeness score
    assert result["score"] < 80 or result["passed"] is False
