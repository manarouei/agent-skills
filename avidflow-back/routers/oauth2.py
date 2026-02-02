from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import secrets
import base64
import logging
from config import settings
from database.crud import CredentialCRUD
from utils.encryption import encrypt_credential_data, decrypt_credential_data
from credentials import get_credential_by_type
from services.redis_manager import RedisManager
from auth.dependencies import get_current_user
from database.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


class CSRFStateManager:
    """Manages CSRF states with Redis TTL and in-memory fallback"""
    
    def __init__(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager
    
    async def store_state(self, state: str, data: dict) -> bool:
        """Store CSRF state with automatic expiration"""
        # Try Redis first with TTL
        if self.redis_manager and self.redis_manager.redis:
            success = await self.redis_manager.set_oauth_state(
                state, 
                data, 
                expire_seconds=settings.OAUTH_STATE_EXPIRE_SECONDS
            )
            if success:
                return True
            logger.warning("Failed to store state in Redis, falling back to memory")

        return True
    
    async def get_state(self, state: str) -> Optional[dict]:
        """Get CSRF state with automatic expiration check"""
        # Try Redis first
        if self.redis_manager and self.redis_manager.redis:
            data = await self.redis_manager.get_oauth_state(state)
            if data is not None:
                return data
            logger.debug(f"State not found in Redis: {state}")
        
        return None
    
    async def delete_state(self, state: str) -> bool:
        """Delete CSRF state"""
        deleted = False
        
        # Try Redis first
        if self.redis_manager and self.redis_manager.redis:
            redis_deleted = await self.redis_manager.delete_oauth_state(state)
            if redis_deleted:
                deleted = True        
        
        return deleted
    
    async def get_state_info(self, state: str) -> Optional[dict]:
        """Get state info including TTL"""
        if self.redis_manager and self.redis_manager.redis:
            data = await self.redis_manager.get_oauth_state(state)
            if data:
                ttl = await self.redis_manager.get_oauth_state_ttl(state)
                return {
                    "data": data,
                    "ttl": ttl,
                    "source": "redis"
                }
        
        return None


async def get_csrf_state_manager(request: Request) -> CSRFStateManager:
    """Get CSRF state manager with Redis dependency"""
    return CSRFStateManager(request.app.state.redis)

async def get_db_from_app(request: Request) -> AsyncSession:
    """Get database session from app state"""
    async with request.app.state.session_factory() as session:
        yield session


@router.get("/auth/{credential_id}")
async def start_oauth_flow(
    credential_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
    csrf_manager: CSRFStateManager = Depends(get_csrf_state_manager),
):
    """Start OAuth2 authorization flow"""
    # Get credential
    credential = await CredentialCRUD.get_credential(db, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")

    if credential.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get credential class
    credential_class = get_credential_by_type(credential.type)
    if not credential_class:
        raise HTTPException(status_code=400, detail="Invalid credential type")

    # Initialize credential instance
    credential_data = decrypt_credential_data(credential.data)

    # Generate CSRF state - n8n creates [csrfSecret, state] pair
    csrf_secret = secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(32)
    
    state_data = {
        "credential_id": credential_id,
        "user_id": current_user.id,
        "csrf_secret": csrf_secret,  # Store csrf_secret for validation
    }

    # Store state with automatic expiration
    success = await csrf_manager.store_state(state, state_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to store OAuth state")

    # Store csrf_secret in credential (like n8n does)
    credential_data_copy = credential_data.copy()
    credential_data_copy["csrfSecret"] = csrf_secret
    
    # Handle PKCE if needed
    if credential_data.get("grantType") == "pkce":
        
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('=')
        credential_data_copy["codeVerifier"] = code_verifier

    # Update credential with csrf_secret and code_verifier
    credential.data = encrypt_credential_data(credential_data_copy)
    await db.commit()

    # Get redirect URI
    redirect_uri = f"{settings.OAUTH2_CALLBACK_URL}"  # Use consistent callback URL

    cred_instance = credential_class(data=credential_data_copy)
    # Generate authorization URL
    try:
        auth_url = cred_instance.get_authorization_url(state, redirect_uri)
        logger.info(f"Generated OAuth URL for credential {credential_id}")
        # Return authUrl in the expected format
        return {"authUrl": auth_url}
    except Exception as e:
        await csrf_manager.delete_state(state)
        logger.error(f"Failed to generate auth URL: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to generate auth URL: {str(e)}")

@router.get("/callback")
async def oauth_callback(
    state: str = Query(...),
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db_from_app),
    csrf_manager: CSRFStateManager = Depends(get_csrf_state_manager),
):
    """Handle OAuth2 callback - matches n8n's approach"""
    
    # Handle OAuth2 errors first
    if error:
        error_msg = error
        if error_description:
            error_msg = f"{error}: {error_description}"
        elif error == "access_denied":
            error_msg = "User denied access to the application"
        elif error == "invalid_request":
            error_msg = "Invalid OAuth2 request"
        elif error == "unauthorized_client":
            error_msg = "Unauthorized client"
        elif error == "unsupported_response_type":
            error_msg = "Unsupported response type"
        elif error == "invalid_scope":
            error_msg = "Invalid scope"
        elif error == "server_error":
            error_msg = "Authorization server error"
        elif error == "temporarily_unavailable":
            error_msg = "Authorization server temporarily unavailable"
        
        logger.warning(f"OAuth error received: {error_msg}")
        return HTMLResponse(
            f"""
            <html>
                <body>
                    <h1>OAuth Authorization Failed</h1>
                    <p>{error_msg}</p>
                    <p>Please try again or contact support if the problem persists.</p>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'oauth_error',
                                error: '{error_msg}'
                            }}, '{settings.FRONTEND_URL}');
                        }}
                        setTimeout(() => window.close(), 3000);
                    </script>
                </body>
            </html>
            """,
            status_code=400,
        )
    
    # If no error, code is required
    if not code:
        logger.error("No authorization code received")
        return HTMLResponse(
            """
            <html>
                <body>
                    <h1>Authorization Failed</h1>
                    <p>No authorization code received from the provider.</p>
                    <script>
                        if (window.opener) {
                            window.opener.postMessage({
                                type: 'oauth_error',
                                error: 'No authorization code received'
                            }, '""" + settings.FRONTEND_URL + """');
                        }
                        setTimeout(() => window.close(), 3000);
                    </script>
                </body>
            </html>
            """,
            status_code=400,
        )

    # Get and validate CSRF state
    state_data = await csrf_manager.get_state(state)
    if not state_data:
        logger.warning(f"Invalid or expired OAuth state: {state}")
        return HTMLResponse(f"""
            <html>
                <body>
                    <h1>Invalid or Expired State</h1>
                    <p>Invalid or expired authorization state. Please try again.</p>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'oauth_error',
                                error: 'Invalid or expired authorization state'
                            }}, '{settings.FRONTEND_URL}');
                        }}
                        setTimeout(() => window.close(), 3000);
                    </script>
                </body>
            </html>
        """, status_code=400)

    # Delete state (one-time use)
    await csrf_manager.delete_state(state)

    # Get credential
    credential = await CredentialCRUD.get_credential(db, state_data['credential_id'])
    if not credential:
        return HTMLResponse(f"""
            <html><body><h1>Credential Not Found</h1>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'oauth_error', 
                        error: 'Credential not found'
                    }}, '{settings.FRONTEND_URL}');
                }}
                setTimeout(() => window.close(), 3000);
            </script></body></html>
        """, status_code=404)

    # Get credential class and decrypt data
    credential_class = get_credential_by_type(credential.type)
    if not credential_class:
        return HTMLResponse(f"""
            <html><body><h1>Invalid Credential Type</h1>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'oauth_error', 
                        error: 'Invalid credential type'
                    }}, '{settings.FRONTEND_URL}');
                }}
                setTimeout(() => window.close(), 3000);
            </script></body></html>
        """, status_code=400)

    credential_data = decrypt_credential_data(credential.data)
    
    # Validate CSRF secret (like n8n does)
    if credential_data.get("csrfSecret") != state_data.get("csrf_secret"):
        logger.warning("CSRF secret mismatch")
        return HTMLResponse(f"""
            <html><body><h1>Security Error</h1>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'oauth_error', 
                        error: 'Security validation failed'
                    }}, '{settings.FRONTEND_URL}');
                }}
                setTimeout(() => window.close(), 3000);
            </script></body></html>
        """, status_code=400)

    cred_instance = credential_class(
        data=credential_data,
    )

    try:
        redirect_uri = f"{settings.OAUTH2_CALLBACK_URL}"
        
        # Exchange code for token
        new_token_data = await cred_instance.exchange_code_for_token(code, redirect_uri)
        
        # *** KEY: n8n's token merging logic ***
        # Only overwrite supplied data as some providers do for example just return the
        # refresh_token on the very first request and not on subsequent ones.
        existing_oauth_data = credential_data.get("oauthTokenData")
        if isinstance(existing_oauth_data, dict):
            # Merge with existing data, new data takes precedence
            merged_oauth_data = {**existing_oauth_data, **new_token_data}
        else:
            merged_oauth_data = new_token_data
        
        # Handle callback query string (like n8n does)
        if len(request.query_params) > 2:  # More than just 'code' and 'state'
            callback_query = {k: v for k, v in request.query_params.items() 
                            if k not in ['state', 'code', 'error', 'error_description']}
            if callback_query:
                merged_oauth_data["callbackQueryString"] = callback_query

        # Update credential data
        updated_credential_data = credential_data.copy()
        updated_credential_data["oauthTokenData"] = merged_oauth_data
        
        # Remove temporary data (like n8n does)
        fields_to_remove = ["csrfSecret"]
        if credential_data.get("grantType") == "pkce":
            fields_to_remove.append("codeVerifier")
            
        for field in fields_to_remove:
            updated_credential_data.pop(field, None)

        # Save to database
        credential.data = encrypt_credential_data(updated_credential_data)
        await db.commit()

        logger.info(f"OAuth flow completed successfully for credential {credential.id}")
        
        return HTMLResponse(f"""
            <html>
                <body>
                    <h1>Authorization Successful</h1>
                    <p>You can now close this window.</p>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'oauth_success',
                                credentialId: '{credential.id}'
                            }}, '{settings.FRONTEND_URL}');
                        }}
                        setTimeout(() => window.close(), 1000);
                    </script>
                </body>
            </html>
        """)

    except Exception as e:
        logger.error(f"Token exchange failed for credential {credential.id}: {e}")
        return HTMLResponse(f"""
            <html>
                <body>
                    <h1>Token Exchange Failed</h1>
                    <p>Failed to exchange authorization code: {str(e)}</p>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'oauth_error',
                                error: '{str(e)}'
                            }}, '{settings.FRONTEND_URL}');
                        }}
                        setTimeout(() => window.close(), 3000);
                    </script>
                </body>
            </html>
        """, status_code=400)

@router.get("/disconnect/{credential_id}")
async def disconnect_oauth(
    credential_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Disconnect OAuth2 credential"""

    # Get credential
    credential = await CredentialCRUD.get_credential(db, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")

    if credential.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Remove OAuth token data
    credential_data = decrypt_credential_data(credential.data)
    if "oauthTokenData" in credential_data:
        credential_data = credential_data.copy()
        del credential_data["oauthTokenData"]
        credential.data = encrypt_credential_data(credential_data)
        await db.commit()

    return {"message": "OAuth2 credential disconnected successfully"}
