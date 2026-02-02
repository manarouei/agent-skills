#!/usr/bin/env python3
"""
OAuth2 Token Refresh Test Script for Staging
============================================

Run this directly inside your Docker container:

    # Copy this script to stage server
    scp stage_oauth_test_inline.py root@stage:/var/www/workflow-stage/

    # Run inside container
    docker exec -it workflow_backend_stage python /code/stage_oauth_test_inline.py --mode mock
    docker exec -it workflow_backend_stage python /code/stage_oauth_test_inline.py --mode list
    docker exec -it workflow_backend_stage python /code/stage_oauth_test_inline.py --mode real --id 123

Or paste and run inline:
    docker exec -it workflow_backend_stage python -c "$(cat stage_oauth_test_inline.py)"
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

def log_info(msg): print(f"{BLUE}[INFO]{RESET} {msg}")
def log_success(msg): print(f"{GREEN}[SUCCESS]{RESET} {msg}")
def log_warning(msg): print(f"{YELLOW}[WARNING]{RESET} {msg}")
def log_error(msg): print(f"{RED}[ERROR]{RESET} {msg}")


class MockGoogleServer:
    """Mock Google OAuth server for testing without real credentials"""
    
    def __init__(self, scenario="success"):
        self.scenario = scenario
        self.call_count = 0
    
    def get_response(self):
        self.call_count += 1
        
        if self.scenario == "success":
            return {
                "status_code": 200,
                "json": {
                    "access_token": f"mock_new_token_{int(time.time())}",
                    "expires_in": 3600,
                    "token_type": "Bearer"
                }
            }
        elif self.scenario == "invalid_grant":
            return {
                "status_code": 400,
                "json": {"error": "invalid_grant", "error_description": "Token revoked"}
            }
        elif self.scenario == "rate_limited":
            if self.call_count <= 2:
                return {"status_code": 429, "json": {"error": "rate_limit"}}
            return {"status_code": 200, "json": {"access_token": "after_retry", "expires_in": 3600}}
        else:
            return {"status_code": 500, "json": {"error": "server_error"}}


def create_mock_node_context():
    """Create minimal mock objects for node instantiation"""
    mock_node_data = Mock()
    mock_node_data.name = "TestNode"
    mock_node_data.type = "gmail"
    mock_node_data.parameters = Mock()
    mock_node_data.parameters.model_dump = Mock(return_value={})
    mock_node_data.credentials = {}
    mock_node_data.position = [0, 0]
    
    mock_workflow = Mock()
    mock_workflow.connections = {}
    mock_workflow.id = 1
    
    return mock_node_data, mock_workflow, {}


def test_mock(scenario="success"):
    """Test refresh token logic with mocked Google responses"""
    print(f"\n{BOLD}{'='*50}")
    print(f"MOCK TEST - Scenario: {scenario}")
    print(f"{'='*50}{RESET}\n")
    
    from nodes.gmail import GmailNode
    
    mock_server = MockGoogleServer(scenario)
    
    # Mock credential data matching real structure
    mock_cred = {
        "clientId": "mock.apps.googleusercontent.com",
        "clientSecret": "mock_secret",
        "accessTokenUrl": "https://oauth2.googleapis.com/token",
        "authentication": "header",
        "oauthTokenData": {
            "access_token": "old_expired_token",
            "refresh_token": "mock_refresh_token",
            "expires_at": int(time.time()) - 100,
            "token_type": "Bearer"
        }
    }
    
    log_info("Creating node instance...")
    node_data, workflow, exec_data = create_mock_node_context()
    node = GmailNode(node_data, workflow, exec_data)
    
    log_info(f"Token expired: {node._is_token_expired(mock_cred['oauthTokenData'])}")
    
    def mock_post(*args, **kwargs):
        resp = mock_server.get_response()
        mock_resp = Mock()
        mock_resp.status_code = resp["status_code"]
        mock_resp.json.return_value = resp["json"]
        mock_resp.text = json.dumps(resp["json"])
        return mock_resp
    
    log_info("Attempting token refresh...")
    
    with patch('requests.post', side_effect=mock_post):
        try:
            result = node.refresh_token(mock_cred)
            if result and "oauthTokenData" in result:
                new_token = result["oauthTokenData"].get("access_token", "")
                log_success(f"Token refreshed: {new_token[:20]}...")
                return True
            else:
                log_warning("No result returned")
                return False
        except ValueError as e:
            if "invalid_grant" in str(e):
                if scenario == "invalid_grant":
                    log_success(f"Correctly caught invalid_grant: {e}")
                    return True
                else:
                    log_error(f"Unexpected invalid_grant: {e}")
                    return False
            raise
        except Exception as e:
            if scenario in ["rate_limited", "server_error"]:
                log_warning(f"Expected error for {scenario}: {e}")
                return True
            log_error(f"Error: {e}")
            return False


def list_google_credentials():
    """List all Google OAuth credentials in database"""
    print(f"\n{BOLD}{'='*50}")
    print("GOOGLE CREDENTIALS")
    print(f"{'='*50}{RESET}\n")
    
    from database.config import get_sync_session_manual
    from models.credential import Credential
    
    google_types = [
        'gmailOAuth2', 'googleDriveApi', 'googleSheetsApi',
        'googleCalendarApi', 'googleDocsApi', 'googleFormApi'
    ]
    
    with get_sync_session_manual() as session:
        creds = session.query(Credential).filter(
            Credential.type.in_(google_types)
        ).all()
        
        if not creds:
            log_warning("No Google credentials found")
            return
        
        print(f"{'ID':<6} {'Type':<20} {'Name':<30} {'User':<6}")
        print("-" * 65)
        for c in creds:
            print(f"{c.id:<6} {c.type:<20} {c.name[:28]:<30} {c.user_id:<6}")
        print(f"\nTotal: {len(creds)}")


def check_credential(credential_id: int, refresh: bool = False):
    """Check and optionally refresh a real credential"""
    print(f"\n{BOLD}{'='*50}")
    print(f"CREDENTIAL CHECK - ID: {credential_id}")
    print(f"{'='*50}{RESET}\n")
    
    from database.config import get_sync_session_manual
    from models.credential import Credential
    from utils.encryption import decrypt_data, encrypt_data
    
    with get_sync_session_manual() as session:
        cred = session.query(Credential).filter(Credential.id == credential_id).first()
        
        if not cred:
            log_error(f"Credential {credential_id} not found")
            return False
        
        log_info(f"Type: {cred.type}")
        log_info(f"Name: {cred.name}")
        
        data = decrypt_data(cred.encrypted_data)
        oauth_data = data.get("oauthTokenData", {})
        
        has_access = bool(oauth_data.get("access_token"))
        has_refresh = bool(oauth_data.get("refresh_token"))
        expires_at = oauth_data.get("expires_at", 0)
        
        log_info(f"Has access_token: {has_access}")
        log_info(f"Has refresh_token: {has_refresh}")
        
        if expires_at:
            now = int(time.time())
            if expires_at > now:
                log_info(f"Expires in: {(expires_at - now) // 60} minutes")
            else:
                log_warning(f"EXPIRED: {(now - expires_at) // 60} minutes ago")
        
        if not refresh:
            log_info("Use --refresh to actually refresh the token")
            return True
        
        if not has_refresh:
            log_error("No refresh token - cannot refresh")
            return False
        
        # Get the right node class
        node_map = {
            "gmailOAuth2": ("nodes.gmail", "GmailNode"),
            "googleDriveApi": ("nodes.googleDrive", "GoogleDriveNode"),
            "googleSheetsApi": ("nodes.googleSheets", "GoogleSheetsNode"),
            "googleCalendarApi": ("nodes.googleCalendar", "GoogleCalendarNode"),
            "googleDocsApi": ("nodes.googleDocs", "GoogleDocsNode"),
            "googleFormApi": ("nodes.googleForm", "GoogleFormNode"),
        }
        
        if cred.type not in node_map:
            log_error(f"Unknown type: {cred.type}")
            return False
        
        module_name, class_name = node_map[cred.type]
        
        log_info(f"Loading {class_name}...")
        import importlib
        module = importlib.import_module(module_name)
        node_class = getattr(module, class_name)
        
        node_data, workflow, exec_data = create_mock_node_context()
        node = node_class(node_data, workflow, exec_data)
        
        log_info("Refreshing token...")
        try:
            new_data = node.refresh_token(data)
            
            if new_data:
                new_oauth = new_data.get("oauthTokenData", {})
                log_success("Token refreshed!")
                log_info(f"New token: {new_oauth.get('access_token', '')[:30]}...")
                
                # Save to database
                cred.encrypted_data = encrypt_data(new_data)
                session.commit()
                log_success("Saved to database")
                return True
            else:
                log_error("No data returned")
                return False
                
        except ValueError as e:
            if "invalid_grant" in str(e):
                log_error(f"TOKEN REVOKED: {e}")
                log_warning("User must reconnect their Google account!")
            else:
                log_error(f"Error: {e}")
            return False
        except Exception as e:
            log_error(f"Error: {e}")
            return False


def force_expire(credential_id: int):
    """Force a credential's token to expire for testing"""
    print(f"\n{BOLD}{'='*50}")
    print(f"FORCE EXPIRE - ID: {credential_id}")
    print(f"{'='*50}{RESET}\n")
    
    from database.config import get_sync_session_manual
    from models.credential import Credential
    from utils.encryption import decrypt_data, encrypt_data
    
    with get_sync_session_manual() as session:
        cred = session.query(Credential).filter(Credential.id == credential_id).first()
        
        if not cred:
            log_error(f"Credential {credential_id} not found")
            return False
        
        data = decrypt_data(cred.encrypted_data)
        oauth_data = data.get("oauthTokenData", {})
        
        old_expires = oauth_data.get("expires_at", "N/A")
        oauth_data["expires_at"] = int(time.time()) - 3600  # 1 hour ago
        
        log_info(f"Old expires_at: {old_expires}")
        log_info(f"New expires_at: {oauth_data['expires_at']} (1 hour ago)")
        
        data["oauthTokenData"] = oauth_data
        cred.encrypted_data = encrypt_data(data)
        session.commit()
        
        log_success(f"Token forced to expire!")
        log_info(f"Now run: --mode real --id {credential_id} --refresh")
        return True


def main():
    parser = argparse.ArgumentParser(description="OAuth2 Token Refresh Test for Staging")
    parser.add_argument("--mode", choices=["mock", "mock-all", "list", "real", "expire"],
                        default="mock", help="Test mode")
    parser.add_argument("--id", type=int, help="Credential ID")
    parser.add_argument("--scenario", choices=["success", "invalid_grant", "rate_limited", "server_error"],
                        default="success", help="Mock scenario")
    parser.add_argument("--refresh", action="store_true", help="Actually refresh token")
    
    args = parser.parse_args()
    
    print(f"\n{BOLD}OAuth2 Token Refresh Test{RESET}")
    
    if args.mode == "mock":
        success = test_mock(args.scenario)
        sys.exit(0 if success else 1)
        
    elif args.mode == "mock-all":
        results = {}
        for scenario in ["success", "invalid_grant", "rate_limited", "server_error"]:
            results[scenario] = "PASS" if test_mock(scenario) else "FAIL"
        
        print(f"\n{BOLD}SUMMARY{RESET}")
        for s, r in results.items():
            color = GREEN if r == "PASS" else RED
            print(f"  {s}: {color}{r}{RESET}")
            
    elif args.mode == "list":
        list_google_credentials()
        
    elif args.mode == "real":
        if not args.id:
            log_error("--id required")
            sys.exit(1)
        success = check_credential(args.id, args.refresh)
        sys.exit(0 if success else 1)
        
    elif args.mode == "expire":
        if not args.id:
            log_error("--id required")
            sys.exit(1)
        success = force_expire(args.id)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
