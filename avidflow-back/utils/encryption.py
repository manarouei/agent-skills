import json
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
from typing import Dict, Any
from config import settings
import logging

logger = logging.getLogger(__name__)

def get_encryption_key() -> bytes:
    """
    Get or generate a consistent encryption key
    """
    # Try to get key from environment first
    if hasattr(settings, "ENCRYPTION_KEY") and settings.ENCRYPTION_KEY:
        try:
            # Validate the key format
            key = settings.ENCRYPTION_KEY.encode() if isinstance(settings.ENCRYPTION_KEY, str) else settings.ENCRYPTION_KEY
            # Test if it's a valid Fernet key
            Fernet(key)
            return key
        except Exception as e:
            logger.warning(f"Invalid ENCRYPTION_KEY in settings: {e}")
    
    # Generate a consistent key from SECRET_KEY
    salt = b'n8n_credential_encryption_salt_v1'  # Fixed salt for consistency
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    # Use SECRET_KEY as password
    secret_key = getattr(settings, 'SECRET_KEY', 'default-secret-key')
    key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
    
    return key

# Create a global Fernet instance
_fernet_instance = None

def get_fernet() -> Fernet:
    """Get or create Fernet instance"""
    global _fernet_instance
    if _fernet_instance is None:
        encryption_key = get_encryption_key()
        _fernet_instance = Fernet(encryption_key)
    return _fernet_instance

def encrypt_credential_data(data: Dict[str, Any]) -> str:
    """
    Encrypt credential data
    
    Args:
        data: Dictionary containing credential data
        
    Returns:
        Base64-encoded encrypted data as a string
    """
    try:
        # Convert dict to JSON string
        json_data = json.dumps(data, sort_keys=True)  # sort_keys for consistency
        
        # Encrypt the JSON string
        fernet = get_fernet()
        encrypted_data = fernet.encrypt(json_data.encode('utf-8'))
        
        # Return base64 encoded string
        return base64.b64encode(encrypted_data).decode('utf-8')
        
    except Exception as e:
        logger.error(f"Error encrypting credential data: {e}")
        raise ValueError(f"Failed to encrypt credential data: {e}")

def decrypt_credential_data(encrypted_data: str) -> Dict[str, Any]:
    """
    Decrypt credential data
    
    Args:
        encrypted_data: Base64-encoded encrypted data string
        
    Returns:
        Decrypted data as a dictionary
    """
    if not encrypted_data:
        logger.warning("Empty encrypted data provided")
        return {}
    
    try:
        # Decode base64 string
        encrypted_bytes = base64.b64decode(encrypted_data)
        
        # Decrypt data
        fernet = get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        
        # Parse JSON
        json_data = decrypted_bytes.decode('utf-8')
        return json.loads(json_data)
        
    except InvalidToken as e:
        logger.error(f"Invalid token error - encryption key mismatch: {e}")
        logger.error(f"This usually means the encryption key has changed or the data was encrypted with a different key")
        # You might want to handle this differently in production
        return {}
        
    except base64.binascii.Error as e:
        logger.error(f"Base64 decode error: {e}")
        return {}
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {}
        
    except Exception as e:
        logger.error(f"Unexpected error decrypting credential data: {e}")
        return {}

def is_encrypted_data(data: str) -> bool:
    """
    Check if the data appears to be encrypted
    
    Args:
        data: String to check
        
    Returns:
        True if data appears to be encrypted, False otherwise
    """
    try:
        # Try to decode as base64
        decoded = base64.b64decode(data)
        # If it's long enough and not obviously JSON, it's probably encrypted
        return len(decoded) > 20 and not data.strip().startswith('{')
    except Exception:
        return False

def migrate_unencrypted_credential(credential_data: str) -> str:
    """
    Migrate unencrypted credential data to encrypted format
    
    Args:
        credential_data: Existing credential data (might be JSON string)
        
    Returns:
        Encrypted credential data
    """
    try:
        # Try to parse as JSON first
        if isinstance(credential_data, str):
            data = json.loads(credential_data)
        else:
            data = credential_data
            
        # Encrypt the data
        return encrypt_credential_data(data)
        
    except json.JSONDecodeError:
        logger.error(f"Cannot migrate invalid JSON credential data: {credential_data}")
        return credential_data
    except Exception as e:
        logger.error(f"Error migrating credential data: {e}")
        return credential_data
