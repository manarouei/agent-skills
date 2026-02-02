"""
Admin API for Node Access Management
=====================================

Endpoints for administrators to manage user node access:
- View user's current plan and accessible nodes
- Update user's plan type
- Add/remove node overrides for specific users

All endpoints require admin authentication.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database.models import User, Subscription
from auth.dependencies import get_db_from_app, get_current_user
from services.dynamic_node_access import (
    get_dynamic_node_access_service,
    PlanConfigLoader,
)


router = APIRouter(prefix="/admin/node-access", tags=["Admin - Node Access"])


# ==============================================================================
# Pydantic Models
# ==============================================================================

class NodeOverridesUpdate(BaseModel):
    """Request model for updating node overrides"""
    nodes: Optional[List[str]] = Field(None, description="Complete list of nodes for custom plan")
    add: Optional[List[str]] = Field(None, description="Nodes to add to user's access")
    remove: Optional[List[str]] = Field(None, description="Nodes to remove from user's access")


class PlanUpdate(BaseModel):
    """Request model for updating user's plan"""
    plan_type: str = Field(..., description="Plan type: 'free' or 'custom'")


class UserNodeAccessResponse(BaseModel):
    """Response model for user's node access info"""
    user_id: str
    username: str
    email: Optional[str]
    has_subscription: bool
    plan_type: str
    plan_display_name: str
    node_overrides: Dict[str, Any]
    accessible_nodes: List[str]
    total_node_count: int


class AvailablePlansResponse(BaseModel):
    """Response model for available plans"""
    plans: Dict[str, Dict[str, Any]]
    node_sets: Dict[str, List[str]]


class BulkNodeAccessUpdate(BaseModel):
    """Request for bulk updating multiple users"""
    user_ids: List[str]
    plan_type: Optional[str] = None
    add_nodes: Optional[List[str]] = None
    remove_nodes: Optional[List[str]] = None


# ==============================================================================
# Helper Functions
# ==============================================================================

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that ensures user is admin"""
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def get_user_with_subscription(
    db: AsyncSession, 
    user_id: str
) -> User:
    """Get user with subscriptions loaded"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.subscriptions))
        .where(User.id == user_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    return user


# ==============================================================================
# Endpoints
# ==============================================================================

@router.get("/plans", response_model=AvailablePlansResponse)
async def get_available_plans(
    admin: User = Depends(require_admin),
):
    """
    Get all available plans and node sets.
    
    Returns the current configuration from node_plans.yaml.
    """
    config = PlanConfigLoader.get_config()
    
    plans = {}
    for name, plan in config.plans.items():
        service = get_dynamic_node_access_service()
        resolved_nodes = service._resolve_plan_nodes(name)
        
        plans[name] = {
            "display_name": plan.display_name,
            "description": plan.description,
            "inherit": plan.inherit,
            "all_access": plan.all_access,
            "node_count": len(resolved_nodes) if "*" not in resolved_nodes else "unlimited",
        }
    
    return AvailablePlansResponse(
        plans=plans,
        node_sets=config.node_sets
    )


@router.get("/users/{user_id}", response_model=UserNodeAccessResponse)
async def get_user_node_access(
    user_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    admin: User = Depends(require_admin),
):
    """
    Get a user's current node access configuration.
    
    Returns:
    - Current plan type
    - Node overrides
    - List of all accessible nodes
    """
    user = await get_user_with_subscription(db, user_id)
    service = get_dynamic_node_access_service()
    
    plan_info = service.get_user_plan_info(user)
    accessible = service.get_user_accessible_nodes(user)
    
    # Get subscription details
    subscription = user.active_subscription
    node_overrides = {}
    if subscription:
        node_overrides = getattr(subscription, 'node_overrides', None) or {}
    
    return UserNodeAccessResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        has_subscription=subscription is not None,
        plan_type=plan_info["plan_type"],
        plan_display_name=plan_info["display_name"],
        node_overrides=node_overrides,
        accessible_nodes=list(accessible) if "*" not in accessible else ["*"],
        total_node_count=len(accessible) if "*" not in accessible else -1,
    )


@router.patch("/users/{user_id}/plan")
async def update_user_plan(
    user_id: str,
    plan_update: PlanUpdate,
    db: AsyncSession = Depends(get_db_from_app),
    admin: User = Depends(require_admin),
):
    """
    Update a user's subscription plan type.
    
    Requires the user to have an active subscription.
    """
    user = await get_user_with_subscription(db, user_id)
    subscription = user.active_subscription
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an active subscription"
        )
    
    # Validate plan type
    config = PlanConfigLoader.get_config()
    if plan_update.plan_type not in config.plans:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan type. Available: {list(config.plans.keys())}"
        )
    
    subscription.plan_type = plan_update.plan_type
    await db.commit()
    
    return {
        "status": "success",
        "user_id": user_id,
        "new_plan_type": plan_update.plan_type
    }


@router.patch("/users/{user_id}/nodes")
async def update_user_node_overrides(
    user_id: str,
    overrides: NodeOverridesUpdate,
    db: AsyncSession = Depends(get_db_from_app),
    admin: User = Depends(require_admin),
):
    """
    Update a user's node access overrides.
    
    For "custom" plan users:
    - Set `nodes` to define the complete list of accessible nodes
    
    For any plan:
    - Use `add` to grant additional nodes
    - Use `remove` to revoke specific nodes
    
    Example:
    ```json
    {
        "nodes": ["start", "end", "gmail", "ai_agent"],
        "add": ["special_node"],
        "remove": ["deprecated_node"]
    }
    ```
    """
    user = await get_user_with_subscription(db, user_id)
    subscription = user.active_subscription
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an active subscription"
        )
    
    # Get current overrides or initialize
    current_overrides = subscription.node_overrides or {}
    
    # Update nodes list (for custom plan)
    if overrides.nodes is not None:
        current_overrides["nodes"] = overrides.nodes
    
    # Update add list
    if overrides.add is not None:
        existing_add = set(current_overrides.get("add", []))
        existing_add.update(overrides.add)
        current_overrides["add"] = list(existing_add)
    
    # Update remove list
    if overrides.remove is not None:
        existing_remove = set(current_overrides.get("remove", []))
        existing_remove.update(overrides.remove)
        current_overrides["remove"] = list(existing_remove)
    
    subscription.node_overrides = current_overrides
    await db.commit()
    
    # Get updated access
    service = get_dynamic_node_access_service()
    accessible = service.get_user_accessible_nodes(user)
    
    return {
        "status": "success",
        "user_id": user_id,
        "node_overrides": current_overrides,
        "accessible_node_count": len(accessible) if "*" not in accessible else "unlimited"
    }


@router.delete("/users/{user_id}/nodes")
async def clear_user_node_overrides(
    user_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    admin: User = Depends(require_admin),
):
    """
    Clear all node overrides for a user.
    
    Resets the user to their base plan nodes.
    """
    user = await get_user_with_subscription(db, user_id)
    subscription = user.active_subscription
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an active subscription"
        )
    
    subscription.node_overrides = {}
    await db.commit()
    
    return {
        "status": "success",
        "user_id": user_id,
        "message": "Node overrides cleared"
    }


@router.post("/bulk-update")
async def bulk_update_node_access(
    update: BulkNodeAccessUpdate,
    db: AsyncSession = Depends(get_db_from_app),
    admin: User = Depends(require_admin),
):
    """
    Bulk update node access for multiple users.
    
    Useful for:
    - Migrating users to a new plan
    - Granting promotional access to a group
    - Revoking access to deprecated nodes
    """
    results = {
        "success": [],
        "failed": []
    }
    
    for user_id in update.user_ids:
        try:
            user = await get_user_with_subscription(db, user_id)
            subscription = user.active_subscription
            
            if not subscription:
                results["failed"].append({
                    "user_id": user_id,
                    "reason": "No active subscription"
                })
                continue
            
            # Update plan type if provided
            if update.plan_type:
                subscription.plan_type = update.plan_type
            
            # Update node overrides
            current_overrides = subscription.node_overrides or {}
            
            if update.add_nodes:
                existing_add = set(current_overrides.get("add", []))
                existing_add.update(update.add_nodes)
                current_overrides["add"] = list(existing_add)
            
            if update.remove_nodes:
                existing_remove = set(current_overrides.get("remove", []))
                existing_remove.update(update.remove_nodes)
                current_overrides["remove"] = list(existing_remove)
            
            subscription.node_overrides = current_overrides
            results["success"].append(user_id)
            
        except HTTPException as e:
            results["failed"].append({
                "user_id": user_id,
                "reason": e.detail
            })
        except Exception as e:
            results["failed"].append({
                "user_id": user_id,
                "reason": str(e)
            })
    
    await db.commit()
    
    return {
        "status": "completed",
        "updated_count": len(results["success"]),
        "failed_count": len(results["failed"]),
        "results": results
    }


@router.post("/reload-config")
async def reload_node_plans_config(
    admin: User = Depends(require_admin),
):
    """
    Force reload the node_plans.yaml configuration.
    
    Use this after making changes to the config file
    without restarting the server.
    """
    from services.dynamic_node_access import reload_node_plans_config
    reload_node_plans_config()
    
    config = PlanConfigLoader.get_config()
    
    return {
        "status": "success",
        "message": "Configuration reloaded",
        "version": config.version,
        "plans": list(config.plans.keys())
    }
