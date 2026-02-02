#!/usr/bin/env python3
"""
OAuth2 Token Refresh Test Script for Staging

Run inside Docker container or via manage.py:
    python scripts/test_oauth_refresh.py mock
    python scripts/test_oauth_refresh.py list
    python scripts/test_oauth_refresh.py check 123
    python scripts/test_oauth_refresh.py expire 123
    python scripts/test_oauth_refresh.py refresh 123
"""

import sys
import os
import time
import json
import importlib
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_mock_node_context():
    """Create minimal mock objects for node instantiation"""
    m = Mock()
    m.name = 'TestNode'
    m.type = 'gmail'
    m.parameters = Mock()
    m.parameters.model_dump = Mock(return_value={})
    m.credentials = {}
    m.position = [0, 0]
    
    w = Mock()
    w.connections = {}
    w.id = 1
    
    return m, w, {}


def cmd_mock(scenario="success"):
    """Test refresh token logic with mocked Google responses"""
    print("\n" + "=" * 50)
    print(f"MOCK TEST - Scenario: {scenario}")
    print("=" * 50 + "\n")
    
    from nodes.gmail import GmailNode
    
    # Mock credential data
    cred = {
        'clientId': 'mock.apps.googleusercontent.com',
        'clientSecret': 'mock_secret',
        'accessTokenUrl': 'https://oauth2.googleapis.com/token',
        'authentication': 'header',
        'oauthTokenData': {
            'access_token': 'old_token',
            'refresh_token': 'mock_refresh',
            'expires_at': int(time.time()) - 100,
            'token_type': 'Bearer'
        }
    }
    
    m, w, e = create_mock_node_context()
    node = GmailNode(m, w, e)
    
    print(f"Token expired: {node._is_token_expired(cred['oauthTokenData'])}")
    
    # Define mock responses
    responses = {
        "success": (200, {'access_token': 'new_token', 'expires_in': 3600}),
        "invalid_grant": (400, {'error': 'invalid_grant'}),
        "server_error": (500, {'error': 'internal'}),
    }
    
    code, resp_data = responses.get(scenario, responses["success"])
    
    def mock_post(*a, **k):
        r = Mock()
        r.status_code = code
        r.json.return_value = resp_data
        r.text = json.dumps(resp_data)
        return r
    
    print(f"Testing scenario: {scenario}")
    
    with patch('requests.post', side_effect=mock_post):
        try:
            result = node.refresh_token(cred)
            if result:
                print(f"✅ SUCCESS: Token refreshed!")
                print(f"New token: {result['oauthTokenData']['access_token'][:20]}...")
                return True
            else:
                print("❌ FAILED: No result")
                return False
        except ValueError as e:
            if "invalid_grant" in str(e) and scenario == "invalid_grant":
                print(f"✅ SUCCESS: Correctly caught invalid_grant")
                return True
            print(f"❌ Error: {e}")
            return False
        except Exception as e:
            if scenario == "server_error":
                print(f"✅ SUCCESS: Correctly caught server error")
                return True
            print(f"❌ Error: {e}")
            return False


def cmd_mock_all():
    """Run all mock test scenarios"""
    print("\n" + "=" * 50)
    print("RUNNING ALL MOCK SCENARIOS")
    print("=" * 50)
    
    results = {}
    for scenario in ["success", "invalid_grant", "server_error"]:
        results[scenario] = "PASS" if cmd_mock(scenario) else "FAIL"
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for name, result in results.items():
        status = "✅" if result == "PASS" else "❌"
        print(f"  {name}: {status} {result}")


def cmd_list():
    """List all Google OAuth credentials"""
    print("\n" + "=" * 50)
    print("GOOGLE CREDENTIALS")
    print("=" * 50 + "\n")
    
    from database.config import get_sync_session_manual
    from sqlalchemy import text
    
    google_types = "('gmailOAuth2','googleDriveApi','googleSheetsApi','googleCalendarApi','googleDocsApi','googleFormApi')"
    
    with get_sync_session_manual() as s:
        # First find the correct column name for encrypted data
        cols = s.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'credentials'"))
        columns = [r[0] for r in cols]
        print(f"Table columns: {columns}\n")
        
        # Query credentials
        result = s.execute(text(f"SELECT id, type, name, user_id FROM credentials WHERE type IN {google_types}"))
        rows = list(result)
        
        if not rows:
            print("No Google credentials found")
            return
        
        print(f"{'ID':<6} {'Type':<22} {'Name':<30} {'User':<6}")
        print("-" * 70)
        for r in rows:
            print(f"{r[0]:<6} {r[1]:<22} {str(r[2])[:28]:<30} {r[3]:<6}")
        print(f"\nTotal: {len(rows)}")


def cmd_check(cred_id: int):
    """Check credential status"""
    print("\n" + "=" * 50)
    print(f"CHECK CREDENTIAL ID: {cred_id}")
    print("=" * 50 + "\n")
    
    from database.config import get_sync_session_manual
    from database.crud import CredentialCRUD
    from utils.encryption import decrypt_credential_data
    
    with get_sync_session_manual() as s:
        cred = CredentialCRUD.get_credential_sync(s, cred_id)
        
        if not cred:
            print(f"❌ Credential {cred_id} not found")
            return False
        
        print(f"Type: {cred.type}")
        print(f"Name: {cred.name}")
        print(f"User ID: {cred.user_id}")
        
        # Decrypt and check oauth data
        data = decrypt_credential_data(cred.data)
        oauth = data.get('oauthTokenData', {})
        
        print(f"Has access_token: {bool(oauth.get('access_token'))}")
        print(f"Has refresh_token: {bool(oauth.get('refresh_token'))}")
        
        exp = oauth.get('expires_at', 0)
        if exp:
            now = int(time.time())
            if exp > now:
                print(f"✅ Expires in: {(exp - now) // 60} minutes")
            else:
                print(f"⚠️  EXPIRED: {(now - exp) // 60} minutes ago")
        
        return True


def cmd_expire(cred_id: int):
    """Force credential token to expire"""
    print("\n" + "=" * 50)
    print(f"FORCE EXPIRE CREDENTIAL ID: {cred_id}")
    print("=" * 50 + "\n")
    
    from database.config import get_sync_session_manual
    from database.crud import CredentialCRUD
    from utils.encryption import decrypt_credential_data, encrypt_credential_data
    
    with get_sync_session_manual() as s:
        cred = CredentialCRUD.get_credential_sync(s, cred_id)
        
        if not cred:
            print(f"❌ Credential {cred_id} not found")
            return False
        
        data = decrypt_credential_data(cred.data)
        oauth = data.get('oauthTokenData', {})
        
        old_exp = oauth.get('expires_at', 'N/A')
        oauth['expires_at'] = int(time.time()) - 3600  # 1 hour ago
        
        print(f"Old expires_at: {old_exp}")
        print(f"New expires_at: {oauth['expires_at']} (1 hour ago)")
        
        data['oauthTokenData'] = oauth
        cred.data = encrypt_credential_data(data)
        s.commit()
        
        print("✅ Token forced to expire!")
        print(f"Now run: python scripts/test_oauth_refresh.py refresh {cred_id}")
        return True


def cmd_refresh(cred_id: int):
    """Actually refresh a credential's token"""
    print("\n" + "=" * 50)
    print(f"REFRESH CREDENTIAL ID: {cred_id}")
    print("=" * 50 + "\n")
    
    from database.config import get_sync_session_manual
    from database.crud import CredentialCRUD
    from utils.encryption import decrypt_credential_data, encrypt_credential_data
    
    node_map = {
        'gmailOAuth2': ('nodes.gmail', 'GmailNode'),
        'googleDriveApi': ('nodes.googleDrive', 'GoogleDriveNode'),
        'googleSheetsApi': ('nodes.googleSheets', 'GoogleSheetsNode'),
        'googleCalendarApi': ('nodes.googleCalendar', 'GoogleCalendarNode'),
        'googleDocsApi': ('nodes.googleDocs', 'GoogleDocsNode'),
        'googleFormApi': ('nodes.googleForm', 'GoogleFormNode'),
    }
    
    with get_sync_session_manual() as s:
        cred = CredentialCRUD.get_credential_sync(s, cred_id)
        
        if not cred:
            print(f"❌ Credential {cred_id} not found")
            return False
        
        print(f"Type: {cred.type}")
        print(f"Name: {cred.name}")
        
        if cred.type not in node_map:
            print(f"❌ Unknown type: {cred.type}")
            return False
        
        data = decrypt_credential_data(cred.data)
        oauth = data.get('oauthTokenData', {})
        
        if not oauth.get('refresh_token'):
            print("❌ No refresh token available")
            return False
        
        # Load the correct node class
        mod_name, cls_name = node_map[cred.type]
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name)
        
        m, w, e = create_mock_node_context()
        node = cls(m, w, e)
        
        print("Refreshing token...")
        try:
            new_data = node.refresh_token(data)
            
            if new_data:
                new_oauth = new_data.get('oauthTokenData', {})
                print(f"✅ Token refreshed!")
                print(f"New token: {new_oauth.get('access_token', '')[:30]}...")
                
                cred.data = encrypt_credential_data(new_data)
                s.commit()
                print("✅ Saved to database")
                return True
            else:
                print("❌ No data returned")
                return False
                
        except ValueError as e:
            if "invalid_grant" in str(e):
                print(f"❌ TOKEN REVOKED: {e}")
                print("⚠️  User must reconnect their Google account!")
            else:
                print(f"❌ Error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


def main():
    if len(sys.argv) < 2:
        print("""
OAuth2 Token Refresh Test Script

Usage:
    python scripts/test_oauth_refresh.py <command> [args]

Commands:
    mock              Run mock test (success scenario)
    mock-all          Run all mock scenarios
    list              List all Google credentials
    check <id>        Check credential status
    expire <id>       Force token to expire
    refresh <id>      Actually refresh the token

Examples:
    python scripts/test_oauth_refresh.py mock
    python scripts/test_oauth_refresh.py list
    python scripts/test_oauth_refresh.py check 123
    python scripts/test_oauth_refresh.py expire 123
    python scripts/test_oauth_refresh.py refresh 123
        """)
        return
    
    cmd = sys.argv[1]
    
    if cmd == "mock":
        scenario = sys.argv[2] if len(sys.argv) > 2 else "success"
        cmd_mock(scenario)
    elif cmd == "mock-all":
        cmd_mock_all()
    elif cmd == "list":
        cmd_list()
    elif cmd == "check":
        if len(sys.argv) < 3:
            print("Error: credential ID required")
            return
        cmd_check(int(sys.argv[2]))
    elif cmd == "expire":
        if len(sys.argv) < 3:
            print("Error: credential ID required")
            return
        cmd_expire(int(sys.argv[2]))
    elif cmd == "refresh":
        if len(sys.argv) < 3:
            print("Error: credential ID required")
            return
        cmd_refresh(int(sys.argv[2]))
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
