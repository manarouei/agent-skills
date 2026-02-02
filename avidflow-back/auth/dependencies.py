from fastapi import Depends, HTTPException, status, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import WebSocket, WebSocketException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from jose import JWTError
from database.models import User, Subscription
from .utils import decode_token


security = HTTPBearer()


async def get_db_from_app(request: Request) -> AsyncSession:
    """Get database session from app state"""
    # Create a new session using the factory
    async with request.app.state.session_factory() as session:
        yield session

async def get_db_from_app_websocket(websocket: WebSocket) -> AsyncSession:
    """Get database session from app state for WebSocket connections"""
    async with websocket.app.state.session_factory() as session:
        yield session

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db_from_app),
):
    """
    Dependency that validates the JWT token and returns the current user.
    """
    try:
        # Get the JWT token from the Authorization header
        token = credentials.credentials

        # Decode and validate the token
        token_data = decode_token(token)

        # Check if it's an access token
        if token_data.type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get the user from the database with subscriptions eagerly loaded
        result = await db.execute(
            select(User)
            .options(selectinload(User.subscriptions))
            .where(User.id == token_data.sub)
        )
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_websocket(
    websocket: WebSocket, db: AsyncSession = Depends(get_db_from_app_websocket)
):
    """
    Dependency that validates the JWT token and returns the current user.
    """
    try:
        token = websocket.query_params.get("token")
        if not token:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Authentication token required",
            )

        user_data = decode_token(token)
        if not user_data:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid authentication token",
            )

        result = await db.execute(select(User).where(User.id == user_data.sub))
        user = result.scalars().first()

        if not user:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid authentication token",
            )

        if not user.is_active:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Inactive user"
            )

        return user

    except JWTError as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=f"Invalid authentication credentials: {str(e)}",
        )
    except Exception as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            detail=f"Authentication error: {str(e)}",
        )


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# ==============================================================================
# Node Access Dependencies
# ==============================================================================

def get_node_access_service():
    """
    Dependency that provides the DynamicNodeAccessService.
    
    Usage:
        @router.get("/nodes")
        async def list_nodes(
            access_service: DynamicNodeAccessService = Depends(get_node_access_service)
        ):
            ...
    """
    from services.dynamic_node_access import get_dynamic_node_access_service
    return get_dynamic_node_access_service()


class NodeAccessFilter:
    """
    Dependency class for filtering nodes based on user's subscription plan.
    
    Supports:
    - Free users: nodes from "free" plan in config
    - Custom plan users: nodes from subscription.node_overrides.nodes
    - Per-user overrides: add/remove nodes via node_overrides
    
    Usage:
        @router.get("/nodes")
        async def list_nodes(
            node_filter: NodeAccessFilter = Depends(NodeAccessFilter)
        ):
            all_nodes = await get_all_nodes(db)
            return node_filter.filter(all_nodes)
    """
    
    def __init__(
        self,
        current_user: User = Depends(get_current_user),
    ):
        from services.dynamic_node_access import get_dynamic_node_access_service
        self.user = current_user
        self.service = get_dynamic_node_access_service()
    
    def filter(self, nodes):
        """Filter nodes based on user's plan and overrides"""
        return self.service.filter_nodes_for_user(self.user, nodes)
    
    def can_access(self, node) -> bool:
        """Check if user can access a specific node"""
        return self.service.can_user_access_node(self.user, node)
    
    @property
    def is_subscribed(self) -> bool:
        """Check if current user has active subscription"""
        return self.service.is_subscribed_user(self.user)
    
    @property
    def plan_type(self) -> str:
        """Get user's current plan type"""
        return self.service.get_plan_for_user(self.user)
    
    @property
    def plan_info(self):
        """Get detailed plan info for the user"""
        return self.service.get_user_plan_info(self.user)
    
    @property
    def accessible_node_types(self):
        """Get set of accessible node types for user"""
        return self.service.get_user_accessible_nodes(self.user)
