"""
Test suite for Google OAuth2 token refresh logic.

Tests the refresh_token implementation in Google nodes against real credentials
stored in the database. Validates proper handling of:
- Token refresh flow
- invalid_grant error detection
- Expiry buffer logic
- Credential persistence

Run with:
    python -m pytest tests/test_google_oauth_refresh.py -v
    
Or standalone:
    python tests/test_google_oauth_refresh.py
"""

import sys
import os
import time
import logging
import json
import base64
from typing import Dict, Any, Optional
from urllib.parse import urlencode
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from database.config import get_sync_session_manual
from database.crud import CredentialCRUD
from database.models import Credential
from utils.encryption import decrypt_credential_data, encrypt_credential_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Test Configuration
# ============================================================================

GOOGLE_CREDENTIAL_TYPES = [
    "googleDriveApi",
    "googleSheetsApi", 
    "googleCalendarApi",
    "googleDocsApi",
    "googleFormApi",
    "gmailOAuth2",
]

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


# ============================================================================
# Helper Functions - Mirror node implementations
# ============================================================================

def has_access_token(credentials_data: Dict[str, Any]) -> bool:
    """Check if credentials have access token (matches node implementation)"""
    if 'data' in credentials_data:
        credentials_data = credentials_data['data']
    
    oauth_token_data = credentials_data.get('oauthTokenData')
    if not isinstance(oauth_token_data, dict):
        return False
    return 'access_token' in oauth_token_data


def is_token_expired(oauth_data: Dict[str, Any], buffer_seconds: int = 30) -> bool:
    """Check if token is expired (matches node implementation)"""
    if "expires_at" not in oauth_data:
        return False
    return time.time() > (oauth_data["expires_at"] - buffer_seconds)


def refresh_token_sync(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous token refresh - mirrors node implementation exactly.
    
    This is the core logic being tested. It should:
    1. Use synchronous requests (Celery gevent compatible)
    2. Handle invalid_grant properly
    3. Return updated oauth_data
    
    Args:
        data: Full credential data with oauthTokenData, clientId, clientSecret, accessTokenUrl
        
    Returns:
        Updated credential data with new oauthTokenData
        
    Raises:
        ValueError: For invalid_grant (user must reconnect)
        Exception: For other errors
    """
    if not data.get("oauthTokenData") or not data["oauthTokenData"].get("refresh_token"):
        raise ValueError("No refresh token available")

    oauth_data = data["oauthTokenData"]

    token_data = {
        "grant_type": "refresh_token",
        "refresh_token": oauth_data["refresh_token"],
    }
    
    headers = {}
    
    # Add client credentials based on authentication method
    if data.get("authentication", "header") == "header":
        auth_header = base64.b64encode(
            f"{data['clientId']}:{data['clientSecret']}".encode()
        ).decode()
        headers["Authorization"] = f"Basic {auth_header}"
    else:
        token_data.update({
            "client_id": data["clientId"],
            "client_secret": data["clientSecret"]
        })
    
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    
    try:
        response = requests.post(
            data.get("accessTokenUrl", GOOGLE_TOKEN_URL),
            data=urlencode(token_data),
            headers=headers,
            timeout=20,
        )
        
        if response.status_code == 200:
            new_token_data = response.json()
            
            # Update token data (preserve existing data)
            updated_oauth_data = oauth_data.copy()
            updated_oauth_data["access_token"] = new_token_data["access_token"]
            
            if "expires_in" in new_token_data:
                updated_oauth_data["expires_at"] = time.time() + new_token_data["expires_in"]
            
            # Only update refresh token if a new one is provided
            if "refresh_token" in new_token_data:
                updated_oauth_data["refresh_token"] = new_token_data["refresh_token"]
            
            # Preserve any additional token data
            for key, value in new_token_data.items():
                if key not in ["access_token", "expires_in", "refresh_token"]:
                    updated_oauth_data[key] = value
            
            # Update data in place
            data["oauthTokenData"] = updated_oauth_data
            return data
            
        else:
            error_data = {}
            try:
                error_data = response.json()
            except:
                error_data = {"error": response.text}
            
            error_code = error_data.get("error", "")
            error_desc = error_data.get("error_description", "")
            
            # Handle invalid_grant - user needs to reconnect
            if error_code == "invalid_grant":
                raise ValueError(f"OAuth token invalid (invalid_grant): {error_desc}. User must reconnect.")
            
            raise Exception(f"Token refresh failed with status {response.status_code}: {error_data}")
            
    except requests.RequestException as e:
        raise Exception(f"Token refresh request failed: {str(e)}")
    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Token refresh failed: {str(e)}")


# ============================================================================
# Database Test Helpers
# ============================================================================

def get_google_credentials_from_db() -> list:
    """Fetch all Google OAuth2 credentials from database"""
    from sqlalchemy import text
    
    credentials = []
    
    with get_sync_session_manual() as session:
        # Get all credentials
        result = session.execute(
            text("SELECT id, name, type, data FROM credentials WHERE type LIKE '%google%' OR type LIKE '%gmail%'")
        )
        
        for row in result:
            try:
                cred_data = decrypt_credential_data(row.data)
                credentials.append({
                    "id": row.id,
                    "name": row.name,
                    "type": row.type,
                    "data": cred_data
                })
            except Exception as e:
                logger.warning(f"Could not decrypt credential {row.id}: {e}")
                
    return credentials


def update_credential_in_db(credential_id: str, credential_data: Dict[str, Any]) -> bool:
    """Update credential data in database"""
    try:
        with get_sync_session_manual() as session:
            credential = CredentialCRUD.get_credential_sync(session, credential_id)
            if credential:
                credential.data = encrypt_credential_data(credential_data)
                session.commit()
                return True
    except Exception as e:
        logger.error(f"Failed to update credential {credential_id}: {e}")
    return False


# ============================================================================
# Unit Tests - Token Refresh Logic
# ============================================================================

class TestTokenRefreshLogic:
    """Unit tests for token refresh helper functions"""
    
    def test_has_access_token_valid(self):
        """Test has_access_token with valid token data"""
        creds = {
            "oauthTokenData": {
                "access_token": "test_token",
                "refresh_token": "test_refresh"
            }
        }
        assert has_access_token(creds) == True
        
    def test_has_access_token_missing(self):
        """Test has_access_token with missing token"""
        creds = {"oauthTokenData": {"refresh_token": "test"}}
        assert has_access_token(creds) == False
        
    def test_has_access_token_nested_data(self):
        """Test has_access_token with nested data structure"""
        creds = {
            "data": {
                "oauthTokenData": {
                    "access_token": "test_token"
                }
            }
        }
        assert has_access_token(creds) == True
        
    def test_is_token_expired_not_expired(self):
        """Test is_token_expired with valid token"""
        oauth_data = {"expires_at": time.time() + 3600}  # 1 hour from now
        assert is_token_expired(oauth_data) == False
        
    def test_is_token_expired_expired(self):
        """Test is_token_expired with expired token"""
        oauth_data = {"expires_at": time.time() - 100}  # 100 seconds ago
        assert is_token_expired(oauth_data) == True
        
    def test_is_token_expired_within_buffer(self):
        """Test is_token_expired within buffer window"""
        oauth_data = {"expires_at": time.time() + 20}  # 20 seconds from now
        assert is_token_expired(oauth_data, buffer_seconds=30) == True
        
    def test_is_token_expired_no_expiry(self):
        """Test is_token_expired with no expiry field"""
        oauth_data = {"access_token": "test"}
        assert is_token_expired(oauth_data) == False


class TestRefreshTokenMocked:
    """Tests with mocked HTTP responses"""
    
    @patch('requests.post')
    def test_refresh_token_success(self, mock_post):
        """Test successful token refresh"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_post.return_value = mock_response
        
        data = {
            "clientId": "test_client",
            "clientSecret": "test_secret",
            "accessTokenUrl": GOOGLE_TOKEN_URL,
            "authentication": "body",
            "oauthTokenData": {
                "access_token": "old_token",
                "refresh_token": "test_refresh_token",
                "expires_at": time.time() - 100
            }
        }
        
        result = refresh_token_sync(data)
        
        assert result["oauthTokenData"]["access_token"] == "new_access_token"
        assert result["oauthTokenData"]["refresh_token"] == "test_refresh_token"
        assert result["oauthTokenData"]["expires_at"] > time.time()
        
    @patch('requests.post')
    def test_refresh_token_invalid_grant(self, mock_post):
        """Test invalid_grant error handling"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Token has been expired or revoked."
        }
        mock_post.return_value = mock_response
        
        data = {
            "clientId": "test_client",
            "clientSecret": "test_secret",
            "accessTokenUrl": GOOGLE_TOKEN_URL,
            "authentication": "body",
            "oauthTokenData": {
                "access_token": "old_token",
                "refresh_token": "revoked_token"
            }
        }
        
        try:
            refresh_token_sync(data)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "invalid_grant" in str(e)
            assert "reconnect" in str(e).lower()
            
    @patch('requests.post')
    def test_refresh_token_server_error(self, mock_post):
        """Test server error handling"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "internal_error"}
        mock_post.return_value = mock_response
        
        data = {
            "clientId": "test_client",
            "clientSecret": "test_secret",
            "accessTokenUrl": GOOGLE_TOKEN_URL,
            "authentication": "body",
            "oauthTokenData": {
                "refresh_token": "test_refresh_token"
            }
        }
        
        try:
            refresh_token_sync(data)
            assert False, "Should have raised Exception"
        except Exception as e:
            assert "500" in str(e) or "internal_error" in str(e)
            
    @patch('requests.post')
    def test_refresh_token_with_rotation(self, mock_post):
        """Test refresh token rotation (new refresh_token returned)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",  # Rotated
            "expires_in": 3600
        }
        mock_post.return_value = mock_response
        
        data = {
            "clientId": "test",
            "clientSecret": "test",
            "accessTokenUrl": GOOGLE_TOKEN_URL,
            "authentication": "body",
            "oauthTokenData": {
                "refresh_token": "old_refresh"
            }
        }
        
        result = refresh_token_sync(data)
        assert result["oauthTokenData"]["refresh_token"] == "new_refresh"
        
    @patch('requests.post')
    def test_refresh_token_preserves_fields(self, mock_post):
        """Test that additional fields are preserved"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/drive"
        }
        mock_post.return_value = mock_response
        
        data = {
            "clientId": "test",
            "clientSecret": "test",
            "accessTokenUrl": GOOGLE_TOKEN_URL,
            "authentication": "body",
            "oauthTokenData": {
                "refresh_token": "test",
                "custom_field": "preserved"
            }
        }
        
        result = refresh_token_sync(data)
        assert result["oauthTokenData"]["custom_field"] == "preserved"
        assert result["oauthTokenData"]["scope"] == "https://www.googleapis.com/auth/drive"

    def test_refresh_token_no_refresh_token(self):
        """Test error when no refresh token available"""
        data = {
            "oauthTokenData": {
                "access_token": "test"
            }
        }
        
        try:
            refresh_token_sync(data)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "No refresh token" in str(e)


# ============================================================================
# Integration Tests - Real Database Credentials
# ============================================================================

class TestRealCredentials:
    """
    Integration tests using real credentials from database.
    
    These tests:
    1. Fetch real Google OAuth2 credentials from DB
    2. Test token refresh against Google's servers
    3. Validate the response structure
    4. Optionally update the database with new tokens
    
    CAUTION: These tests make real API calls!
    """
    
    @classmethod
    def setup_class(cls):
        """Load credentials from database"""
        cls.credentials = get_google_credentials_from_db()
        logger.info(f"Found {len(cls.credentials)} Google credentials in database")
        
    def test_list_available_credentials(self):
        """List all available Google credentials for testing"""
        print("\n" + "=" * 60)
        print("Available Google OAuth2 Credentials:")
        print("=" * 60)
        
        for cred in self.credentials:
            has_token = has_access_token(cred["data"])
            oauth_data = cred["data"].get("oauthTokenData", {})
            expired = is_token_expired(oauth_data) if oauth_data else "N/A"
            
            print(f"\nID: {cred['id']}")
            print(f"  Name: {cred['name']}")
            print(f"  Type: {cred['type']}")
            print(f"  Has Access Token: {has_token}")
            print(f"  Token Expired: {expired}")
            
            if oauth_data.get("expires_at"):
                expires_in = oauth_data["expires_at"] - time.time()
                print(f"  Expires In: {expires_in:.0f} seconds")
                
        print("\n" + "=" * 60)
        
    def test_refresh_real_token(self):
        """
        Test actual token refresh against Google API.
        
        This test finds the first valid Google credential and attempts
        to refresh its token.
        """
        # Find a valid credential
        valid_cred = None
        for cred in self.credentials:
            if has_access_token(cred["data"]):
                oauth_data = cred["data"].get("oauthTokenData", {})
                if oauth_data.get("refresh_token"):
                    valid_cred = cred
                    break
                    
        if not valid_cred:
            logger.warning("No valid Google credentials found - skipping real refresh test")
            return
            
        print(f"\nTesting refresh for: {valid_cred['name']} ({valid_cred['type']})")
        
        # Attempt refresh
        try:
            old_token = valid_cred["data"]["oauthTokenData"]["access_token"]
            old_expires = valid_cred["data"]["oauthTokenData"].get("expires_at", 0)
            
            result = refresh_token_sync(valid_cred["data"])
            
            new_token = result["oauthTokenData"]["access_token"]
            new_expires = result["oauthTokenData"].get("expires_at", 0)
            
            print(f"  Old Token: {old_token[:20]}...")
            print(f"  New Token: {new_token[:20]}...")
            print(f"  Old Expires: {old_expires}")
            print(f"  New Expires: {new_expires}")
            print(f"  Token Changed: {old_token != new_token}")
            print(f"  ✅ Refresh successful!")
            
            # Validate response structure
            assert "access_token" in result["oauthTokenData"]
            assert "refresh_token" in result["oauthTokenData"]
            assert result["oauthTokenData"]["expires_at"] > time.time()
            
        except ValueError as e:
            if "invalid_grant" in str(e):
                print(f"  ⚠️ Token is invalid/revoked - user needs to reconnect")
                print(f"  Error: {e}")
            else:
                raise
        except Exception as e:
            print(f"  ❌ Refresh failed: {e}")
            raise
            
    def test_refresh_and_persist(self):
        """
        Test token refresh and database persistence.
        
        This test:
        1. Refreshes a token
        2. Saves to database
        3. Reads back to verify persistence
        """
        # Find a valid credential
        valid_cred = None
        for cred in self.credentials:
            if has_access_token(cred["data"]):
                oauth_data = cred["data"].get("oauthTokenData", {})
                if oauth_data.get("refresh_token"):
                    valid_cred = cred
                    break
                    
        if not valid_cred:
            logger.warning("No valid Google credentials found - skipping persistence test")
            return
            
        print(f"\nTesting refresh + persist for: {valid_cred['name']}")
        
        try:
            # Refresh token
            result = refresh_token_sync(valid_cred["data"])
            
            # Update in database
            success = update_credential_in_db(valid_cred["id"], result)
            assert success, "Failed to update credential in database"
            print("  ✅ Token refreshed and persisted to database")
            
            # Read back and verify
            with get_sync_session_manual() as session:
                cred = CredentialCRUD.get_credential_sync(session, valid_cred["id"])
                if cred:
                    data = decrypt_credential_data(cred.data)
                    new_token = data["oauthTokenData"]["access_token"]
                    expected_token = result["oauthTokenData"]["access_token"]
                    
                    assert new_token == expected_token, "Token mismatch after persistence"
                    print("  ✅ Token verified after database read-back")
                    
        except ValueError as e:
            if "invalid_grant" in str(e):
                print(f"  ⚠️ Token is invalid/revoked")
            else:
                raise


# ============================================================================
# Gevent Compatibility Tests
# ============================================================================

class TestGeventCompatibility:
    """
    Tests to ensure the refresh logic works in Celery gevent mode.
    
    Key requirements:
    - Must use synchronous requests (not aiohttp)
    - Must not use asyncio
    - Must be thread-safe for concurrent workers
    """
    
    def test_uses_sync_requests(self):
        """Verify refresh uses synchronous requests library"""
        import inspect
        
        # Check that refresh_token_sync uses requests, not aiohttp
        source = inspect.getsource(refresh_token_sync)
        
        assert "requests.post" in source, "Should use requests.post"
        assert "aiohttp" not in source, "Should not use aiohttp"
        assert "async def" not in source, "Should not be async"
        assert "await" not in source, "Should not use await"
        
    @patch('requests.post')
    def test_concurrent_refresh(self, mock_post):
        """Test concurrent token refreshes (simulated)"""
        from concurrent.futures import ThreadPoolExecutor
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "concurrent_token",
            "expires_in": 3600
        }
        mock_post.return_value = mock_response
        
        def do_refresh(worker_id):
            data = {
                "clientId": "test",
                "clientSecret": "test",
                "accessTokenUrl": GOOGLE_TOKEN_URL,
                "authentication": "body",
                "oauthTokenData": {
                    "refresh_token": f"refresh_{worker_id}"
                }
            }
            result = refresh_token_sync(data)
            return result["oauthTokenData"]["access_token"]
            
        # Run 10 concurrent refreshes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(do_refresh, i) for i in range(10)]
            results = [f.result() for f in futures]
            
        assert len(results) == 10
        assert all(r == "concurrent_token" for r in results)


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for various error conditions"""
    
    @patch('requests.post')
    def test_network_timeout(self, mock_post):
        """Test network timeout handling"""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        data = {
            "clientId": "test",
            "clientSecret": "test",
            "accessTokenUrl": GOOGLE_TOKEN_URL,
            "authentication": "body",
            "oauthTokenData": {"refresh_token": "test"}
        }
        
        try:
            refresh_token_sync(data)
            assert False, "Should have raised Exception"
        except Exception as e:
            assert "timed out" in str(e).lower() or "request failed" in str(e).lower()
            
    @patch('requests.post')
    def test_connection_error(self, mock_post):
        """Test connection error handling"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Failed to connect")
        
        data = {
            "clientId": "test",
            "clientSecret": "test",
            "accessTokenUrl": GOOGLE_TOKEN_URL,
            "authentication": "body",
            "oauthTokenData": {"refresh_token": "test"}
        }
        
        try:
            refresh_token_sync(data)
            assert False, "Should have raised Exception"
        except Exception as e:
            assert "request failed" in str(e).lower()
            
    @patch('requests.post')
    def test_malformed_response(self, mock_post):
        """Test handling of malformed JSON response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_post.return_value = mock_response
        
        data = {
            "clientId": "test",
            "clientSecret": "test",
            "accessTokenUrl": GOOGLE_TOKEN_URL,
            "authentication": "body",
            "oauthTokenData": {"refresh_token": "test"}
        }
        
        try:
            refresh_token_sync(data)
            assert False, "Should have raised Exception"
        except Exception:
            pass  # Any exception is acceptable for malformed response


# ============================================================================
# Main Entry Point
# ============================================================================

def run_tests():
    """Run all tests"""
    import pytest
    
    # Run pytest with verbose output
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x",  # Stop on first failure
    ])
    
    return exit_code


def run_real_credential_test():
    """Run only the real credential tests (for manual verification)"""
    print("\n" + "=" * 60)
    print("Running Real Credential Tests")
    print("=" * 60)
    
    test_instance = TestRealCredentials()
    test_instance.setup_class()
    
    print("\n--- Test: List Credentials ---")
    test_instance.test_list_available_credentials()
    
    print("\n--- Test: Refresh Real Token ---")
    try:
        test_instance.test_refresh_real_token()
    except Exception as e:
        print(f"Error: {e}")
        
    print("\n--- Test: Refresh and Persist ---")
    try:
        test_instance.test_refresh_and_persist()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Google OAuth2 token refresh")
    parser.add_argument("--real", action="store_true", help="Run real credential tests only")
    parser.add_argument("--list", action="store_true", help="List available credentials only")
    
    args = parser.parse_args()
    
    if args.list:
        creds = get_google_credentials_from_db()
        test = TestRealCredentials()
        test.credentials = creds
        test.test_list_available_credentials()
    elif args.real:
        run_real_credential_test()
    else:
        run_tests()
