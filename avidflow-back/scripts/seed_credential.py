#!/usr/bin/env python3
"""
Credential Seeding Tool for Staging Environment

This tool helps you create test credentials on your staging server
without needing to go through the full OAuth flow.

Usage:
    # Create from OAuth Playground tokens
    python scripts/seed_credential.py --type gmailOAuth2 --from-playground
    
    # Create with manual token input
    python scripts/seed_credential.py --type googleDriveApi --access-token "..." --refresh-token "..."
    
    # Export credential for backup (your own only!)
    python scripts/seed_credential.py --export --credential-id 123
    
    # Import credential from exported file
    python scripts/seed_credential.py --import-file credential_backup.json
"""

import os
import sys
import json
import time
import argparse
import getpass
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
settings = get_settings()


class Colors:
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


# Credential type configurations
CREDENTIAL_CONFIGS = {
    "gmailOAuth2": {
        "name": "Gmail OAuth2",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.compose",
            "https://www.googleapis.com/auth/gmail.modify",
        ],
        "required_fields": ["access_token", "refresh_token", "client_id", "client_secret"],
    },
    "googleDriveApi": {
        "name": "Google Drive",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/drive.file",
        ],
        "required_fields": ["access_token", "refresh_token", "client_id", "client_secret"],
    },
    "googleSheetsApi": {
        "name": "Google Sheets",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/spreadsheets",
        ],
        "required_fields": ["access_token", "refresh_token", "client_id", "client_secret"],
    },
    "googleCalendarApi": {
        "name": "Google Calendar",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
        ],
        "required_fields": ["access_token", "refresh_token", "client_id", "client_secret"],
    },
    "googleDocsApi": {
        "name": "Google Docs",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/documents",
        ],
        "required_fields": ["access_token", "refresh_token", "client_id", "client_secret"],
    },
    "googleFormApi": {
        "name": "Google Forms",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/forms.body.readonly",
            "https://www.googleapis.com/auth/forms.responses.readonly",
        ],
        "required_fields": ["access_token", "refresh_token", "client_id", "client_secret"],
    },
}


def get_oauth_client_credentials() -> tuple:
    """
    Get OAuth client credentials from user input or environment.
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID") or input("Enter Google Client ID: ").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or getpass.getpass("Enter Google Client Secret: ").strip()
    
    if not client_id or not client_secret:
        raise ValueError("Client ID and Client Secret are required")
    
    return client_id, client_secret


def create_from_playground(credential_type: str, user_id: int) -> bool:
    """
    Guide user through creating a credential from Google OAuth Playground tokens.
    """
    config = CREDENTIAL_CONFIGS.get(credential_type)
    if not config:
        log_error(f"Unknown credential type: {credential_type}")
        return False
    
    print(f"\n{Colors.BOLD}Creating {config['name']} Credential from OAuth Playground{Colors.RESET}\n")
    
    print(f"""
{Colors.CYAN}Step 1: Go to Google OAuth Playground{Colors.RESET}
  https://developers.google.com/oauthplayground

{Colors.CYAN}Step 2: Configure your OAuth credentials{Colors.RESET}
  - Click the ⚙️ (settings) icon
  - Check "Use your own OAuth credentials"
  - Enter your Client ID and Client Secret

{Colors.CYAN}Step 3: Select scopes{Colors.RESET}
  Select these scopes:
""")
    
    for scope in config["scopes"]:
        print(f"    - {scope}")
    
    print(f"""
{Colors.CYAN}Step 4: Authorize and exchange code{Colors.RESET}
  - Click "Authorize APIs"
  - Sign in with your Google account
  - Click "Exchange authorization code for tokens"
  - Copy the access_token and refresh_token

{Colors.CYAN}Step 5: Enter the tokens below{Colors.RESET}
""")
    
    # Get credentials
    try:
        client_id, client_secret = get_oauth_client_credentials()
    except ValueError as e:
        log_error(str(e))
        return False
    
    access_token = input("Enter Access Token: ").strip()
    refresh_token = input("Enter Refresh Token: ").strip()
    
    if not access_token or not refresh_token:
        log_error("Access Token and Refresh Token are required")
        return False
    
    # Ask for credential name
    default_name = f"Staging Test - {config['name']}"
    name = input(f"Credential name [{default_name}]: ").strip() or default_name
    
    # Build credential data
    credential_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_type": "Bearer",
        "expires_at": int(time.time()) + 3600,  # Assume 1 hour validity
        "scope": " ".join(config["scopes"]),
    }
    
    return save_credential(credential_type, name, credential_data, user_id)


def create_from_tokens(
    credential_type: str,
    access_token: str,
    refresh_token: str,
    user_id: int,
    name: Optional[str] = None
) -> bool:
    """
    Create a credential directly from provided tokens.
    """
    config = CREDENTIAL_CONFIGS.get(credential_type)
    if not config:
        log_error(f"Unknown credential type: {credential_type}")
        return False
    
    print(f"\n{Colors.BOLD}Creating {config['name']} Credential{Colors.RESET}\n")
    
    try:
        client_id, client_secret = get_oauth_client_credentials()
    except ValueError as e:
        log_error(str(e))
        return False
    
    if not name:
        name = f"Staging Test - {config['name']}"
    
    credential_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_type": "Bearer",
        "expires_at": int(time.time()) + 3600,
        "scope": " ".join(config["scopes"]),
    }
    
    return save_credential(credential_type, name, credential_data, user_id)


def save_credential(
    credential_type: str,
    name: str,
    data: Dict[str, Any],
    user_id: int
) -> bool:
    """
    Save the credential to the database.
    """
    from database.config import get_sync_session_manual
    from models.credential import Credential
    from utils.encryption import encrypt_data
    
    log_info("Saving credential to database...")
    
    try:
        with get_sync_session_manual() as session:
            # Check if credential with same name exists
            existing = session.query(Credential).filter(
                Credential.user_id == user_id,
                Credential.name == name
            ).first()
            
            if existing:
                log_warning(f"Credential '{name}' already exists (ID: {existing.id})")
                update = input("Update existing credential? [y/N]: ").strip().lower()
                
                if update == 'y':
                    existing.encrypted_data = encrypt_data(data)
                    existing.type = credential_type
                    session.commit()
                    log_success(f"Updated credential ID: {existing.id}")
                    return True
                else:
                    log_info("Aborted")
                    return False
            
            # Create new credential
            credential = Credential(
                user_id=user_id,
                type=credential_type,
                name=name,
                encrypted_data=encrypt_data(data),
            )
            session.add(credential)
            session.commit()
            
            log_success(f"Created credential ID: {credential.id}")
            log_info(f"Type: {credential_type}")
            log_info(f"Name: {name}")
            log_info(f"User ID: {user_id}")
            
            return True
            
    except Exception as e:
        log_error(f"Failed to save credential: {e}")
        return False


def export_credential(credential_id: int, output_file: Optional[str] = None) -> bool:
    """
    Export a credential to a JSON file for backup.
    WARNING: Only use for your own test credentials!
    """
    from database.config import get_sync_session_manual
    from models.credential import Credential
    from utils.encryption import decrypt_data
    
    log_warning("⚠️  Only export YOUR OWN test credentials, never user data!")
    confirm = input("Confirm you own this credential [y/N]: ").strip().lower()
    
    if confirm != 'y':
        log_info("Aborted")
        return False
    
    with get_sync_session_manual() as session:
        credential = session.query(Credential).filter(
            Credential.id == credential_id
        ).first()
        
        if not credential:
            log_error(f"Credential {credential_id} not found")
            return False
        
        data = decrypt_data(credential.encrypted_data)
        
        export_data = {
            "type": credential.type,
            "name": credential.name,
            "data": data,
            "exported_at": datetime.utcnow().isoformat(),
            "source_env": settings.ENV,
        }
        
        if not output_file:
            output_file = f"credential_{credential_id}_{credential.type}.json"
        
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        log_success(f"Exported to: {output_file}")
        log_warning("Keep this file secure - it contains sensitive tokens!")
        
        return True


def import_credential(input_file: str, user_id: int) -> bool:
    """
    Import a credential from an exported JSON file.
    """
    log_info(f"Importing from: {input_file}")
    
    try:
        with open(input_file, 'r') as f:
            export_data = json.load(f)
    except Exception as e:
        log_error(f"Failed to read file: {e}")
        return False
    
    credential_type = export_data.get("type")
    name = export_data.get("name", "Imported Credential")
    data = export_data.get("data", {})
    
    if not credential_type or not data:
        log_error("Invalid export file format")
        return False
    
    log_info(f"Type: {credential_type}")
    log_info(f"Name: {name}")
    log_info(f"Original source: {export_data.get('source_env', 'unknown')}")
    
    confirm = input("Import this credential? [y/N]: ").strip().lower()
    if confirm != 'y':
        log_info("Aborted")
        return False
    
    return save_credential(credential_type, name, data, user_id)


def list_users():
    """List users in the database."""
    from database.config import get_sync_session_manual
    from models.user import User
    
    with get_sync_session_manual() as session:
        users = session.query(User).limit(20).all()
        
        if not users:
            log_warning("No users found")
            return
        
        print(f"\n{'ID':<6} {'Email':<40} {'Active':<8}")
        print("-" * 60)
        
        for user in users:
            print(f"{user.id:<6} {user.email[:38]:<40} {user.is_active}")


def main():
    parser = argparse.ArgumentParser(
        description="Credential Seeding Tool for Staging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create from OAuth Playground (interactive)
  python scripts/seed_credential.py --type gmailOAuth2 --from-playground --user-id 1
  
  # Create with tokens directly
  python scripts/seed_credential.py --type googleDriveApi \\
    --access-token "ya29.xxx" \\
    --refresh-token "1//xxx" \\
    --user-id 1
  
  # Export credential for backup
  python scripts/seed_credential.py --export --credential-id 123
  
  # Import credential
  python scripts/seed_credential.py --import-file backup.json --user-id 1
  
  # List users
  python scripts/seed_credential.py --list-users
  
  # List supported credential types
  python scripts/seed_credential.py --list-types
        """
    )
    
    parser.add_argument(
        "--type",
        choices=list(CREDENTIAL_CONFIGS.keys()),
        help="Credential type to create"
    )
    
    parser.add_argument(
        "--from-playground",
        action="store_true",
        help="Interactive mode using OAuth Playground tokens"
    )
    
    parser.add_argument(
        "--access-token",
        help="Access token (for direct creation)"
    )
    
    parser.add_argument(
        "--refresh-token",
        help="Refresh token (for direct creation)"
    )
    
    parser.add_argument(
        "--name",
        help="Credential name"
    )
    
    parser.add_argument(
        "--user-id",
        type=int,
        help="User ID to associate credential with"
    )
    
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export a credential"
    )
    
    parser.add_argument(
        "--credential-id",
        type=int,
        help="Credential ID for export"
    )
    
    parser.add_argument(
        "--output-file",
        help="Output file for export"
    )
    
    parser.add_argument(
        "--import-file",
        help="Import credential from file"
    )
    
    parser.add_argument(
        "--list-users",
        action="store_true",
        help="List users in database"
    )
    
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="List supported credential types"
    )
    
    args = parser.parse_args()
    
    print(f"\n{Colors.BOLD}Credential Seeding Tool{Colors.RESET}")
    print(f"Environment: {settings.ENV}")
    
    if settings.ENV == "production":
        log_error("This tool should NOT be run on production!")
        log_error("It is designed for staging/development environments only.")
        sys.exit(1)
    
    if args.list_types:
        print(f"\n{Colors.BOLD}Supported Credential Types:{Colors.RESET}\n")
        for type_id, config in CREDENTIAL_CONFIGS.items():
            print(f"  {Colors.CYAN}{type_id}{Colors.RESET}")
            print(f"    Name: {config['name']}")
            print(f"    Scopes: {len(config['scopes'])}")
            print()
        return
    
    if args.list_users:
        list_users()
        return
    
    if args.export:
        if not args.credential_id:
            log_error("--credential-id required for export")
            sys.exit(1)
        success = export_credential(args.credential_id, args.output_file)
        sys.exit(0 if success else 1)
    
    if args.import_file:
        if not args.user_id:
            log_error("--user-id required for import")
            sys.exit(1)
        success = import_credential(args.import_file, args.user_id)
        sys.exit(0 if success else 1)
    
    if args.from_playground:
        if not args.type:
            log_error("--type required with --from-playground")
            sys.exit(1)
        if not args.user_id:
            log_error("--user-id required")
            sys.exit(1)
        success = create_from_playground(args.type, args.user_id)
        sys.exit(0 if success else 1)
    
    if args.access_token and args.refresh_token:
        if not args.type:
            log_error("--type required")
            sys.exit(1)
        if not args.user_id:
            log_error("--user-id required")
            sys.exit(1)
        success = create_from_tokens(
            args.type,
            args.access_token,
            args.refresh_token,
            args.user_id,
            args.name
        )
        sys.exit(0 if success else 1)
    
    parser.print_help()


if __name__ == "__main__":
    main()
