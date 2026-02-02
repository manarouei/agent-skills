#!/usr/bin/env python3
"""
Stage Server OAuth2 Token Refresh Testing Script

This script helps you test the Google OAuth2 refresh token flow on your staging server.
It supports multiple testing modes:

1. MOCK MODE: Test without real Google credentials (validates code flow)
2. SEEDED MODE: Copy credentials from production to test with real tokens
3. MANUAL MODE: Manually create a test credential via OAuth flow

Usage:
    # Mock test (no real credentials needed)
    python scripts/stage_oauth_test.py --mode mock
    
    # Test with real credential ID from your staging DB
    python scripts/stage_oauth_test.py --mode real --credential-id 123
    
    # Simulate the exact Celery execution flow
    python scripts/stage_oauth_test.py --mode celery-sim --credential-id 123
    
    # Seed a test credential (for initial setup)
    python scripts/stage_oauth_test.py --mode seed --help
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import after path setup
from config import get_settings
settings = get_settings()


class Colors:
    """Terminal colors for output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def log_info(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")

def log_success(msg: str):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {msg}")

def log_warning(msg: str):
    print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} {msg}")

def log_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")

def log_step(step: int, total: int, msg: str):
    print(f"{Colors.CYAN}[{step}/{total}]{Colors.RESET} {msg}")


class MockGoogleTokenServer:
    """
    Mock Google Token Server for testing without real credentials.
    Simulates various scenarios:
    - Successful token refresh
    - Expired refresh token (invalid_grant)
    - Rate limiting
    - Network errors
    """
    
    def __init__(self, scenario: str = "success"):
        self.scenario = scenario
        self.call_count = 0
    
    def get_response(self) -> Dict[str, Any]:
        self.call_count += 1
        
        if self.scenario == "success":
            return {
                "status_code": 200,
                "json": {
                    "access_token": f"mock_access_token_{int(time.time())}",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": "https://www.googleapis.com/auth/gmail.readonly"
                }
            }
        elif self.scenario == "invalid_grant":
            return {
                "status_code": 400,
                "json": {
                    "error": "invalid_grant",
                    "error_description": "Token has been expired or revoked."
                }
            }
        elif self.scenario == "rate_limited":
            if self.call_count <= 2:
                return {
                    "status_code": 429,
                    "json": {"error": "rate_limit_exceeded"},
                    "headers": {"Retry-After": "1"}
                }
            return {
                "status_code": 200,
                "json": {
                    "access_token": f"mock_access_token_after_retry_{int(time.time())}",
                    "expires_in": 3600,
                    "token_type": "Bearer"
                }
            }
        elif self.scenario == "server_error":
            return {
                "status_code": 500,
                "json": {"error": "internal_error"}
            }
        else:
            return {"status_code": 200, "json": {"access_token": "default"}}


def create_mock_node_context():
    """
    Create minimal mock objects for node instantiation.
    Nodes require node_data, workflow, and execution_data.
    """
    # Create mock node_data
    mock_node_data = Mock()
    mock_node_data.name = "TestGmailNode"
    mock_node_data.type = "gmail"
    mock_node_data.parameters = Mock()
    mock_node_data.parameters.model_dump = Mock(return_value={})
    mock_node_data.credentials = {}
    mock_node_data.position = [0, 0]
    
    # Create mock workflow
    mock_workflow = Mock()
    mock_workflow.connections = {}
    mock_workflow.id = 1
    
    # Execution data (previous node outputs)
    mock_execution_data = {}
    
    return mock_node_data, mock_workflow, mock_execution_data


def test_mock_mode(scenario: str = "success"):
    """
    Test the refresh token logic with mocked Google responses.
    No real credentials needed - validates code paths work correctly.
    """
    print(f"\n{Colors.BOLD}{'='*60}")
    print("MOCK MODE TEST - Testing OAuth2 Refresh Logic")
    print(f"{'='*60}{Colors.RESET}\n")
    
    log_info(f"Testing scenario: {scenario}")
    
    # Import the node we want to test
    from nodes.gmail import GmailNode
    
    mock_server = MockGoogleTokenServer(scenario)
    
    # Create mock credential data - matches the actual credential structure
    # The OAuth token data is nested inside oauthTokenData
    mock_credential_data = {
        "clientId": "mock_client_id.apps.googleusercontent.com",
        "clientSecret": "mock_client_secret",
        "accessTokenUrl": "https://oauth2.googleapis.com/token",
        "authentication": "header",
        "oauthTokenData": {
            "access_token": "old_expired_token",
            "refresh_token": "mock_refresh_token_12345",
            "expires_at": int(time.time()) - 100,  # Already expired
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/gmail.readonly"
        }
    }
    
    log_step(1, 4, "Creating GmailNode instance with mock context...")
    mock_node_data, mock_workflow, mock_execution_data = create_mock_node_context()
    node = GmailNode(mock_node_data, mock_workflow, mock_execution_data)
    
    log_step(2, 4, "Checking if token is expired...")
    oauth_data = mock_credential_data.get("oauthTokenData", {})
    is_expired = node._is_token_expired(oauth_data)
    log_info(f"Token expired: {is_expired}")
    
    log_step(3, 4, "Attempting token refresh with mock server...")
    
    # Mock the requests.post call
    def mock_post(*args, **kwargs):
        response = mock_server.get_response()
        mock_response = Mock()
        mock_response.status_code = response["status_code"]
        mock_response.json.return_value = response["json"]
        mock_response.text = json.dumps(response["json"])
        mock_response.headers = response.get("headers", {})
        return mock_response
    
    with patch('requests.post', side_effect=mock_post):
        try:
            result = node.refresh_token(mock_credential_data)
            
            log_step(4, 4, "Processing result...")
            
            if result:
                log_success("Token refresh succeeded!")
                log_info(f"New access token: {result.get('access_token', 'N/A')[:30]}...")
                log_info(f"Expires in: {result.get('expires_in', 'N/A')} seconds")
                return True
            else:
                log_warning("refresh_token returned None")
                return False
                
        except ValueError as e:
            if "invalid_grant" in str(e):
                log_warning(f"Expected error for invalid_grant scenario: {e}")
                return scenario == "invalid_grant"
            raise
        except Exception as e:
            log_error(f"Unexpected error: {e}")
            return False


def test_real_credential(credential_id: int, dry_run: bool = True):
    """
    Test with a real credential from the database.
    
    Args:
        credential_id: The ID of the credential to test
        dry_run: If True, only checks token status without refreshing
    """
    print(f"\n{Colors.BOLD}{'='*60}")
    print("REAL CREDENTIAL TEST")
    print(f"{'='*60}{Colors.RESET}\n")
    
    log_info(f"Testing credential ID: {credential_id}")
    log_info(f"Dry run mode: {dry_run}")
    
    from database.config import get_sync_session_manual
    from models.credential import Credential
    from utils.encryption import decrypt_data
    
    log_step(1, 5, "Fetching credential from database...")
    
    with get_sync_session_manual() as session:
        credential = session.query(Credential).filter(
            Credential.id == credential_id
        ).first()
        
        if not credential:
            log_error(f"Credential ID {credential_id} not found")
            return False
        
        log_info(f"Credential type: {credential.type}")
        log_info(f"Credential name: {credential.name}")
        
        log_step(2, 5, "Decrypting credential data...")
        data = decrypt_data(credential.encrypted_data)
        
        # Check what we have
        has_access = "access_token" in data
        has_refresh = "refresh_token" in data
        has_expiry = "expires_at" in data
        
        log_info(f"Has access_token: {has_access}")
        log_info(f"Has refresh_token: {has_refresh}")
        log_info(f"Has expires_at: {has_expiry}")
        
        if has_expiry:
            expires_at = data.get("expires_at")
            now = int(time.time())
            if expires_at > now:
                remaining = expires_at - now
                log_info(f"Token expires in: {remaining} seconds ({remaining // 60} minutes)")
            else:
                expired_ago = now - expires_at
                log_warning(f"Token expired: {expired_ago} seconds ago ({expired_ago // 60} minutes)")
        
        if dry_run:
            log_info("Dry run - skipping actual refresh")
            return True
        
        log_step(3, 5, "Determining node type...")
        
        # Map credential type to node
        node_map = {
            "gmailOAuth2": "nodes.gmail.GmailNode",
            "googleDriveApi": "nodes.googleDrive.GoogleDriveNode",
            "googleSheetsApi": "nodes.googleSheets.GoogleSheetsNode",
            "googleCalendarApi": "nodes.googleCalendar.GoogleCalendarNode",
            "googleDocsApi": "nodes.googleDocs.GoogleDocsNode",
            "googleFormApi": "nodes.googleForm.GoogleFormNode",
        }
        
        node_path = node_map.get(credential.type)
        if not node_path:
            log_error(f"Unknown credential type: {credential.type}")
            return False
        
        log_step(4, 5, f"Loading node: {node_path}...")
        
        module_path, class_name = node_path.rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        node_class = getattr(module, class_name)
        
        # Create mock context for node instantiation
        mock_node_data, mock_workflow, mock_execution_data = create_mock_node_context()
        node = node_class(mock_node_data, mock_workflow, mock_execution_data)
        
        log_step(5, 5, "Attempting token refresh...")
        
        try:
            new_data = node.refresh_token(data)
            
            if new_data:
                log_success("Token refresh succeeded!")
                log_info(f"New token expires in: {new_data.get('expires_in', 'N/A')} seconds")
                
                # Update in database
                from utils.encryption import encrypt_data
                credential.encrypted_data = encrypt_data(new_data)
                session.commit()
                log_success("New token saved to database")
                
                return True
            else:
                log_warning("refresh_token returned None")
                return False
                
        except ValueError as e:
            if "invalid_grant" in str(e):
                log_error(f"Token revoked or expired: {e}")
                log_info("User needs to reconnect their Google account")
            else:
                log_error(f"Error: {e}")
            return False


def test_celery_simulation(credential_id: int):
    """
    Simulate the exact Celery workflow execution path.
    This tests how the token refresh works in the real execution context.
    """
    print(f"\n{Colors.BOLD}{'='*60}")
    print("CELERY EXECUTION SIMULATION")
    print(f"{'='*60}{Colors.RESET}\n")
    
    log_info("Simulating Celery gevent worker context...")
    
    # Import what Celery workers use
    from database.config import get_sync_session_manual
    from models.credential import Credential
    from utils.encryption import decrypt_data, encrypt_data
    
    log_step(1, 6, "Setting up execution context (like Celery task)...")
    
    # This mimics what happens in engine/execution.py
    with get_sync_session_manual() as session:
        log_step(2, 6, "Fetching credential (as workflow executor would)...")
        
        credential = session.query(Credential).filter(
            Credential.id == credential_id
        ).first()
        
        if not credential:
            log_error(f"Credential {credential_id} not found")
            return False
        
        log_step(3, 6, "Decrypting and checking token status...")
        data = decrypt_data(credential.encrypted_data)
        
        # Import the actual node
        from nodes.gmail import GmailNode
        
        # Create mock context for node instantiation
        mock_node_data, mock_workflow, mock_execution_data = create_mock_node_context()
        node = GmailNode(mock_node_data, mock_workflow, mock_execution_data)
        
        # Check token status
        has_token = node.has_access_token(data)
        is_expired = node._is_token_expired(data) if has_token else True
        
        log_info(f"Has access token: {has_token}")
        log_info(f"Token expired: {is_expired}")
        
        if is_expired and "refresh_token" in data:
            log_step(4, 6, "Token needs refresh - calling refresh_token()...")
            
            try:
                new_data = node.refresh_token(data)
                
                if new_data:
                    log_step(5, 6, "Persisting refreshed token to database...")
                    credential.encrypted_data = encrypt_data(new_data)
                    session.commit()
                    
                    log_step(6, 6, "Verifying saved token...")
                    # Re-read to verify
                    session.refresh(credential)
                    verify_data = decrypt_data(credential.encrypted_data)
                    
                    if verify_data.get("access_token") == new_data.get("access_token"):
                        log_success("Token refresh and persistence verified!")
                        return True
                    else:
                        log_error("Token verification failed!")
                        return False
                        
            except Exception as e:
                log_error(f"Refresh failed: {e}")
                return False
        else:
            log_info("Token is still valid - no refresh needed")
            return True


def seed_test_credential():
    """
    Create a test OAuth2 credential for staging.
    This guides you through obtaining a test token via OAuth flow.
    """
    print(f"\n{Colors.BOLD}{'='*60}")
    print("SEED TEST CREDENTIAL")
    print(f"{'='*60}{Colors.RESET}\n")
    
    print("""
To create a test credential on staging, you have several options:

{bold}OPTION 1: Use the staging frontend{reset}
1. Open your staging frontend (e.g., https://stage.yourplatform.com)
2. Go to Credentials section
3. Add a new Google credential (Gmail, Drive, etc.)
4. Complete the OAuth flow
5. Note the credential ID from the database

{bold}OPTION 2: Copy from production (careful!){reset}
Only copy YOUR OWN test account credentials, never user data!

1. On production, find your test credential:
   SELECT id, name, type, encrypted_data FROM credentials 
   WHERE user_id = YOUR_USER_ID AND type LIKE 'google%';

2. Copy the encrypted_data value

3. On staging, insert:
   INSERT INTO credentials (user_id, name, type, encrypted_data, ...) 
   VALUES (...);

{bold}OPTION 3: Force expire a token for testing{reset}
If you have a working credential, force it to expire:

    python scripts/stage_oauth_test.py --mode force-expire --credential-id 123

{bold}OPTION 4: Use Google OAuth Playground{reset}
1. Go to https://developers.google.com/oauthplayground
2. Select the scopes you need (Gmail, Drive, etc.)
3. Click "Authorize APIs"
4. Exchange authorization code for tokens
5. Copy access_token and refresh_token
6. Create credential manually in staging DB
""".format(bold=Colors.BOLD, reset=Colors.RESET))


def force_expire_credential(credential_id: int):
    """
    Force a credential's token to expire for testing refresh flow.
    """
    print(f"\n{Colors.BOLD}{'='*60}")
    print("FORCE EXPIRE CREDENTIAL")
    print(f"{'='*60}{Colors.RESET}\n")
    
    from database.config import get_sync_session_manual
    from models.credential import Credential
    from utils.encryption import decrypt_data, encrypt_data
    
    with get_sync_session_manual() as session:
        credential = session.query(Credential).filter(
            Credential.id == credential_id
        ).first()
        
        if not credential:
            log_error(f"Credential {credential_id} not found")
            return False
        
        data = decrypt_data(credential.encrypted_data)
        
        # Set expires_at to 1 hour ago
        old_expires = data.get("expires_at", "N/A")
        data["expires_at"] = int(time.time()) - 3600
        
        log_info(f"Old expires_at: {old_expires}")
        log_info(f"New expires_at: {data['expires_at']} (1 hour ago)")
        
        credential.encrypted_data = encrypt_data(data)
        session.commit()
        
        log_success(f"Credential {credential_id} token forced to expire")
        log_info("Now run: python scripts/stage_oauth_test.py --mode real --credential-id {credential_id}")
        
        return True


def list_google_credentials():
    """List all Google-related credentials in the database."""
    print(f"\n{Colors.BOLD}{'='*60}")
    print("GOOGLE CREDENTIALS LIST")
    print(f"{'='*60}{Colors.RESET}\n")
    
    from database.config import get_sync_session_manual
    from models.credential import Credential
    
    google_types = [
        'gmailOAuth2', 'googleDriveApi', 'googleSheetsApi',
        'googleCalendarApi', 'googleDocsApi', 'googleFormApi'
    ]
    
    with get_sync_session_manual() as session:
        credentials = session.query(Credential).filter(
            Credential.type.in_(google_types)
        ).all()
        
        if not credentials:
            log_warning("No Google credentials found in database")
            log_info("Use --mode seed to learn how to create test credentials")
            return
        
        print(f"{'ID':<6} {'Type':<20} {'Name':<30} {'User ID':<10}")
        print("-" * 70)
        
        for cred in credentials:
            print(f"{cred.id:<6} {cred.type:<20} {cred.name[:28]:<30} {cred.user_id:<10}")
        
        print(f"\nTotal: {len(credentials)} credentials")


def run_all_mock_scenarios():
    """Run all mock test scenarios."""
    scenarios = ["success", "invalid_grant", "rate_limited", "server_error"]
    results = {}
    
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Testing scenario: {scenario}")
        print("="*60)
        
        try:
            result = test_mock_mode(scenario)
            results[scenario] = "PASS" if result else "FAIL"
        except Exception as e:
            results[scenario] = f"ERROR: {e}"
    
    print(f"\n{Colors.BOLD}{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}{Colors.RESET}\n")
    
    for scenario, result in results.items():
        color = Colors.GREEN if result == "PASS" else Colors.RED
        print(f"  {scenario}: {color}{result}{Colors.RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Stage Server OAuth2 Token Refresh Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run mock tests (no real credentials)
  python scripts/stage_oauth_test.py --mode mock
  
  # Run all mock scenarios
  python scripts/stage_oauth_test.py --mode mock-all
  
  # List Google credentials in database
  python scripts/stage_oauth_test.py --mode list
  
  # Test real credential (dry run - just check status)
  python scripts/stage_oauth_test.py --mode real --credential-id 123 --dry-run
  
  # Test real credential (actually refresh)
  python scripts/stage_oauth_test.py --mode real --credential-id 123
  
  # Simulate Celery execution
  python scripts/stage_oauth_test.py --mode celery-sim --credential-id 123
  
  # Force expire a credential for testing
  python scripts/stage_oauth_test.py --mode force-expire --credential-id 123
  
  # Learn how to seed credentials
  python scripts/stage_oauth_test.py --mode seed
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["mock", "mock-all", "real", "celery-sim", "seed", "force-expire", "list"],
        default="mock",
        help="Test mode"
    )
    
    parser.add_argument(
        "--credential-id",
        type=int,
        help="Credential ID for real/celery-sim/force-expire modes"
    )
    
    parser.add_argument(
        "--scenario",
        choices=["success", "invalid_grant", "rate_limited", "server_error"],
        default="success",
        help="Mock scenario to test"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only check status, don't actually refresh"
    )
    
    args = parser.parse_args()
    
    print(f"\n{Colors.BOLD}Stage OAuth2 Token Refresh Tester{Colors.RESET}")
    print(f"Environment: {settings.ENV}")
    print(f"Database: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    
    if args.mode == "mock":
        success = test_mock_mode(args.scenario)
        sys.exit(0 if success else 1)
        
    elif args.mode == "mock-all":
        run_all_mock_scenarios()
        
    elif args.mode == "list":
        list_google_credentials()
        
    elif args.mode == "real":
        if not args.credential_id:
            log_error("--credential-id required for real mode")
            sys.exit(1)
        success = test_real_credential(args.credential_id, args.dry_run)
        sys.exit(0 if success else 1)
        
    elif args.mode == "celery-sim":
        if not args.credential_id:
            log_error("--credential-id required for celery-sim mode")
            sys.exit(1)
        success = test_celery_simulation(args.credential_id)
        sys.exit(0 if success else 1)
        
    elif args.mode == "force-expire":
        if not args.credential_id:
            log_error("--credential-id required for force-expire mode")
            sys.exit(1)
        success = force_expire_credential(args.credential_id)
        sys.exit(0 if success else 1)
        
    elif args.mode == "seed":
        seed_test_credential()


if __name__ == "__main__":
    main()
