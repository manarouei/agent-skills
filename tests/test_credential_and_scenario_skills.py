"""
Tests for credential conversion and scenario testing skills.

Tests:
- Credential TS parsing
- Credential generation (API key, OAuth2, database)
- Platform client (mocked HTTP)
- Credential provisioning
- Scenario workflow building and execution
- Self-heal error classification
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest


# =============================================================================
# HELPER: DYNAMIC SKILL IMPORT
# =============================================================================

def _import_skill_module(skill_name: str):
    """Import a skill module dynamically (handles hyphenated directory names)."""
    skill_path = Path(__file__).parent.parent / "skills" / skill_name / "impl.py"
    if not skill_path.exists():
        raise ImportError(f"Skill impl not found: {skill_path}")
    
    spec = importlib.util.spec_from_file_location(
        f"skill_impl_{skill_name.replace('-', '_')}",
        skill_path,
    )
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load skill: {skill_name}")
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# =============================================================================
# CREDENTIAL-CONVERT TESTS
# =============================================================================

class TestCredentialConvert:
    """Test credential-convert skill."""
    
    def test_ts_parser_api_key_credential(self):
        """Test parsing simple API key credential."""
        mod = _import_skill_module("credential-convert")
        TSCredentialParser = mod.TSCredentialParser
        
        ts_content = """
        export class BitlyApi implements ICredentialType {
            name = 'bitlyApi';
            displayName = 'Bitly API';
            properties: INodeProperties[] = [
                {
                    displayName: 'Access Token',
                    name: 'accessToken',
                    type: 'string',
                    required: true,
                    default: '',
                },
                {
                    displayName: 'Base URL',
                    name: 'baseUrl',
                    type: 'string',
                    required: false,
                    default: 'https://api-ssl.bitly.com/v4',
                },
            ];
        }
        """
        
        parser = TSCredentialParser(ts_content, "bitlyApi")
        metadata = parser.parse()
        
        assert metadata["class_name"] == "BitlyApi"
        assert metadata["display_name"] == "Bitly API"
        assert len(metadata["properties"]) == 2
        
        # Check first property
        prop1 = metadata["properties"][0]
        assert prop1["name"] == "accessToken"
        assert prop1["displayName"] == "Access Token"
        assert prop1["type"] == "string"
        assert prop1["required"] is True
    
    def test_ts_parser_oauth2_credential(self):
        """Test parsing OAuth2 credential that extends base."""
        mod = _import_skill_module("credential-convert")
        TSCredentialParser = mod.TSCredentialParser
        
        ts_content = """
        export class SlackOAuth2Api implements ICredentialType {
            name = 'slackOAuth2Api';
            displayName = 'Slack OAuth2 API';
            extends = ['oAuth2Api'];
            properties: INodeProperties[] = [
                {
                    displayName: 'Scope',
                    name: 'scope',
                    type: 'hidden',
                    default: 'channels:read chat:write users:read',
                },
            ];
        }
        """
        
        parser = TSCredentialParser(ts_content, "slackOAuth2Api")
        metadata = parser.parse()
        
        assert metadata["extends"] == "oAuth2Api"
        assert metadata["class_name"] == "SlackOAuth2Api"
    
    def test_credential_generator_api_key(self):
        """Test generating API key credential."""
        mod = _import_skill_module("credential-convert"); CredentialGenerator = mod.CredentialGenerator
        
        metadata = {
            "class_name": "BitlyApi",
            "display_name": "Bitly API",
            "properties": [
                {
                    "name": "accessToken",
                    "displayName": "Access Token",
                    "type": "string",
                    "required": True,
                }
            ],
        }
        
        generator = CredentialGenerator(metadata, {})
        python_code = generator.generate()
        
        assert "class BitlyApiCredential(BaseCredential)" in python_code
        assert 'name = "bitlyApi"' in python_code
        assert '"accessToken"' in python_code
    
    def test_credential_generator_oauth2(self):
        """Test generating OAuth2 credential."""
        mod = _import_skill_module("credential-convert"); CredentialGenerator = mod.CredentialGenerator
        
        metadata = {
            "class_name": "SlackOAuth2Api",
            "display_name": "Slack OAuth2 API",
            "extends": "oAuth2Api",
            "properties": [
                {
                    "name": "scope",
                    "type": "hidden",
                    "default": "channels:read chat:write",
                }
            ],
        }
        
        generator = CredentialGenerator(metadata, {})
        python_code = generator.generate()
        
        assert "class SlackOAuth2ApiCredential(OAuth2ApiCredential)" in python_code
        assert "SCOPES" in python_code


# =============================================================================
# PLATFORM CLIENT TESTS
# =============================================================================

class TestPlatformClient:
    """Test platform client."""
    
    @patch('requests.request')
    def test_credential_create(self, mock_request):
        """Test credential creation."""
        from runtime.platform_client import PlatformClient
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "cred_123", "name": "test-cred"}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response
        
        client = PlatformClient(
            base_url="http://localhost:8000",
            auth_token="test-token",
        )
        
        result = client.credentials.create(
            name="test-cred",
            credential_type="bitlyApi",
            data={"accessToken": "secret"},
        )
        
        assert result["id"] == "cred_123"
        assert mock_request.called
        
        # Verify request
        call_args = mock_request.call_args
        assert call_args[1]["method"] == "POST"
        assert "credentials" in call_args[1]["url"]
        assert call_args[1]["json"]["name"] == "test-cred"
    
    @patch('requests.request')
    def test_workflow_execute_rest(self, mock_request):
        """Test workflow execution via REST."""
        from runtime.platform_client import PlatformClient
        
        # Mock responses
        exec_response = Mock()
        exec_response.status_code = 200
        exec_response.json.return_value = {"execution_id": "exec_123"}
        exec_response.raise_for_status = Mock()
        
        status_response = Mock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "execution_id": "exec_123",
            "status": "completed",
        }
        status_response.raise_for_status = Mock()
        
        mock_request.side_effect = [exec_response, status_response]
        
        client = PlatformClient(
            base_url="http://localhost:8000",
            auth_token="test-token",
        )
        
        result = client.workflows.execute_rest(
            workflow_id="wf_123",
            wait_for_completion=True,
            timeout=10,
        )
        
        assert result["status"] == "completed"
        assert mock_request.call_count == 2


# =============================================================================
# CREDENTIAL-PROVISION TESTS
# =============================================================================

class TestCredentialProvision:
    """Test credential-provision skill."""
    
    def test_env_var_resolution(self):
        """Test environment variable resolution in credential data."""
        mod = _import_skill_module("credential-provision"); _resolve_env_var = mod._resolve_env_var
        
        # Required env var (present)
        with patch.dict('os.environ', {'MY_TOKEN': 'secret123'}):
            result = _resolve_env_var("${MY_TOKEN}")
            assert result == "secret123"
        
        # Required env var (missing)
        with pytest.raises(ValueError, match="Required environment variable"):
            _resolve_env_var("${MISSING_VAR}")
        
        # Optional with default
        result = _resolve_env_var("${MISSING_VAR:-default_value}")
        assert result == "default_value"
    
    def test_credential_data_resolution(self):
        """Test resolving credential data dict."""
        mod = _import_skill_module("credential-provision"); _resolve_credential_data = mod._resolve_credential_data
        
        with patch.dict('os.environ', {'API_KEY': 'key123'}):
            data = {
                "apiKey": "${API_KEY}",
                "baseUrl": "https://api.example.com",
                "timeout": 30,
            }
            
            resolved = _resolve_credential_data(data)
            
            assert resolved["apiKey"] == "key123"
            assert resolved["baseUrl"] == "https://api.example.com"
            assert resolved["timeout"] == 30
    
    def test_sanitize_credential(self):
        """Test credential sanitization for artifacts."""
        mod = _import_skill_module("credential-provision"); _sanitize_credential = mod._sanitize_credential
        
        credential = {
            "id": "cred_123",
            "name": "test-cred",
            "type": "bitlyApi",
            "data": {
                "accessToken": "secret123",
                "baseUrl": "https://api.bitly.com",
            },
            "created_at": "2025-01-06T00:00:00Z",
        }
        
        sanitized = _sanitize_credential(credential)
        
        assert sanitized["id"] == "cred_123"
        assert sanitized["name"] == "test-cred"
        assert "data" not in sanitized
        assert sanitized["fields"] == ["accessToken", "baseUrl"]


# =============================================================================
# SCENARIO-WORKFLOW-TEST TESTS
# =============================================================================

class TestScenarioWorkflowTest:
    """Test scenario-workflow-test skill."""
    
    def test_build_minimal_workflow(self):
        """Test building minimal workflow."""
        mod = _import_skill_module("scenario-workflow-test"); _build_minimal_workflow = mod._build_minimal_workflow
        
        workflow = _build_minimal_workflow(
            node_type="bitly",
            parameters={"resource": "link", "operation": "create"},
            credentials={"bitlyApi": "cred_123"},
        )
        
        assert len(workflow["nodes"]) == 3
        assert workflow["nodes"][0]["type"] == "start"
        assert workflow["nodes"][1]["type"] == "bitly"
        assert workflow["nodes"][2]["type"] == "end"
        
        assert len(workflow["connections"]) == 2
        assert workflow["nodes"][1]["credentials"] == {"bitlyApi": "cred_123"}
    
    def test_error_classification(self):
        """Test error type classification."""
        mod = _import_skill_module("scenario-workflow-test"); _classify_error = mod._classify_error
        
        # Mock execution result
        execution_result = {"status": "failed", "error": "test error"}
        
        # ImportError
        assert _classify_error("No module named 'requests'", execution_result) == "ImportError"
        assert _classify_error("cannot import name 'Foo'", execution_result) == "ImportError"
        
        # AttributeError
        assert _classify_error("'Node' object has no attribute 'execute'", execution_result) == "AttributeError"
        
        # CredentialError
        assert _classify_error("Authentication failed", execution_result) == "CredentialError"
        assert _classify_error("Credential authentication error", execution_result) == "CredentialError"
        
        # TimeoutError
        assert _classify_error("Request timeout after 30s", execution_result) == "TimeoutError"
        
        # SchemaError
        assert _classify_error("Invalid schema for field", execution_result) == "SchemaError"
        
        # RuntimeError
        assert _classify_error("Runtime error during execution", execution_result) == "RuntimeError"
        
        # Unknown
        assert _classify_error("Something went wrong", execution_result) == "Unknown"
    
    def test_extract_node_outputs(self):
        """Test extracting node outputs from execution result."""
        mod = _import_skill_module("scenario-workflow-test"); _extract_node_outputs = mod._extract_node_outputs
        
        execution_result = {
            "data": {
                "resultData": {
                    "runData": {
                        "node-under-test": [
                            {
                                "data": {
                                    "main": [[{"json": {"result": "success"}}]]
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        outputs = _extract_node_outputs(execution_result)
        
        assert "node-under-test" in outputs
        assert outputs["node-under-test"]["main"][0][0]["json"]["result"] == "success"


# =============================================================================
# SELF-HEAL-COORDINATOR TESTS
# =============================================================================

class TestSelfHealCoordinator:
    """Test self-heal-coordinator skill."""
    
    def test_classify_error(self):
        """Test error classification."""
        mod = _import_skill_module("self-heal-coordinator"); classify_error = mod.classify_error
        
        # ImportError
        error_type, config = classify_error("No module named 'requests'")
        assert error_type == "ImportError"
        assert config["fixable"] is True
        assert config["fix_strategy"] == "add_import_or_dependency"
        
        # SchemaError
        error_type, config = classify_error("Invalid schema: missing required field")
        assert error_type == "SchemaError"
        assert config["fixable"] is True
        
        # Unknown
        error_type, config = classify_error("Something weird happened")
        assert error_type == "Unknown"
        assert config["fixable"] is False
    
    def test_fix_import_error(self):
        """Test ImportError fix."""
        mod = _import_skill_module("self-heal-coordinator"); _fix_import_error = mod._fix_import_error
        
        mock_ctx = Mock()
        artifact_base = Path("/tmp/test")
        
        # Standard library module
        result = _fix_import_error(
            "No module named 'json'",
            artifact_base,
            "bitly",
            mock_ctx,
        )
        
        assert result["success"] is False
        assert result["module"] == "json"
        assert "standard library" in result["message"]
        
        # Third-party module
        result = _fix_import_error(
            "No module named 'requests'",
            artifact_base,
            "bitly",
            mock_ctx,
        )
        
        assert result["success"] is False
        assert result["module"] == "requests"
        assert "third-party" in result["message"]


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for full pipeline."""
    
    def test_skill_contracts_exist(self):
        """Verify all new skills have valid contracts."""
        from pathlib import Path
        
        skills = [
            "credential-convert",
            "credential-provision",
            "scenario-workflow-test",
            "self-heal-coordinator",
        ]
        
        for skill_name in skills:
            skill_dir = Path("skills") / skill_name
            assert skill_dir.exists(), f"Skill directory not found: {skill_name}"
            
            skill_file = skill_dir / "SKILL.md"
            assert skill_file.exists(), f"SKILL.md not found: {skill_name}"
            
            impl_file = skill_dir / "impl.py"
            assert impl_file.exists(), f"impl.py not found: {skill_name}"
            
            # Check frontmatter
            content = skill_file.read_text()
            assert "---" in content
            assert f"name: {skill_name}" in content
            assert "autonomy_level:" in content
            assert "sync_celery:" in content
    
    def test_pipeline_config_has_scenario_pipeline(self):
        """Verify pipeline config includes scenario testing pipeline."""
        from pathlib import Path
        import yaml
        
        config_file = Path("configs/pipelines.yaml")
        config = yaml.safe_load(config_file.read_text())
        
        assert "type1-convert-with-scenarios" in config
        
        pipeline = config["type1-convert-with-scenarios"]
        step_names = [step["name"] for step in pipeline["steps"]]
        
        assert "convert-credentials" in step_names
        assert "provision-credentials" in step_names
        assert "scenario-test" in step_names
        assert "self-heal" in step_names
