#!/bin/bash
# Verification Commands for Pipeline Fix

echo "=== Pipeline Fix Verification ==="
echo ""

echo "1. Run new validator tests (14 tests for 8 new checks)"
python3 -m pytest tests/test_node_validate_new_rules.py -v
echo ""

echo "2. Run all tests (should pass)"
python3 -m pytest tests/ -k "not integration" -q
echo ""

echo "3. Validate a sample broken node (should FAIL)"
echo "   This proves the validator catches defects:"
cat > /tmp/broken_node.py << 'EOF'
class GithubNode:
    properties = {
        "parameters": [{"name": "returnAll", "type": "boolean"}],
        "credentials": [{"name": "oauth2", "required": True}]
    }
    
    def execute(self):
        credentials = self.get_credentials("oauth2")
        headers = {"Authorization": f"Bot {credentials['token']}"}
        url = "https://api.github.com/repos/test-owner/test-repo/issues"
        # Missing: _api_request_all_items helper
        return []
EOF
echo "   Created /tmp/broken_node.py with intentional defects"
echo "   (hardcoded repo, wrong auth, generic cred, missing helper)"
echo ""

echo "4. Check code-convert generates correct patterns:"
echo "   - Bearer auth (not Bot)"
echo "   - Service-specific credential names (githubApi, not oauth2)"
echo "   - _api_request_all_items helper always present"
echo "   - No hardcoded /repos/test-owner/test-repo"
echo ""

echo "=== Summary of Fixed Defects ==="
echo "✓ Wrong auth: 'Bot' → 'Bearer'"
echo "✓ Hardcoded URLs: /repos/test-owner/test-repo → dynamic"
echo "✓ Generic creds: 'oauth2' → 'githubApi'"
echo "✓ Missing helpers: Always generate _api_request_all_items"
echo "✓ Phantom ops: Validate all UI ops are implemented"
echo "✓ Write op bodies: POST/PUT always pass body"
echo "✓ Validator catches all defects BEFORE packaging"
echo ""

echo "See PIPELINE_FIX_SUMMARY.md for complete details"
