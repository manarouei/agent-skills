from __future__ import annotations
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import DynamicNodeCRUD
from database.models import DynamicNode

router = APIRouter()

async def get_db_from_app(request: Request) -> AsyncSession:
    """Get database session from app state"""
    # Create a new session using the factory
    async with request.app.state.session_factory() as session:
        yield session


def _to_tool_item(n: DynamicNode) -> Dict[str, Any]:
    desc = (n.description or {}) if isinstance(n.description, dict) else {}
    return {
        "id": n.id,
        "type": n.type,
        "version": n.version,
        "name": n.name,
        "displayName": desc.get("displayName", n.name),
        "description": desc.get("description", ""),
        "icon": str(n.icon) if n.icon else None,
        "category": n.category,
        "group": desc.get("group", []),
        "properties": n.properties or {},
        "isStart": n.is_start,
        "isEnd": n.is_end,
        "isWebhook": n.is_webhook,
        "isSchedule": n.is_schedule,
    }

@router.get("/list")
async def list_tools(db: AsyncSession = Depends(get_db_from_app)) -> Dict[str, Any]:
    """
    List dynamic nodes that can be used as tools (description.usableAsTool == True),
    returning the same shape the FE expects for nodes.
    """
    nodes = await DynamicNodeCRUD.get_all_nodes(db, active_only=True)
    tools: List[Dict[str, Any]] = []
    for n in nodes:
        desc = (n.description or {}) if isinstance(n.description, dict) else {}
        if desc.get("usableAsTool") is True:
            tools.append(_to_tool_item(n))
    # Optional: stable ordering by group, then displayName
    tools.sort(key=lambda t: (",".join(t.get("group") or []), t.get("displayName") or t.get("name")))
    return {"tools": tools}