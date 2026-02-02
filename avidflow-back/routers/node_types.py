from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from database import crud
from database.models import User
from auth.dependencies import get_current_user, NodeAccessFilter
from pydantic import BaseModel
from models.node import DynamicNodeResponse, DynamicNodeMetadataResponse
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

async def get_db_from_app(request: Request) -> AsyncSession:
    """Get database session from app state"""
    # Create a new session using the factory
    async with request.app.state.session_factory() as session:
        yield session


def _get_description_dict(node: DynamicNodeResponse) -> dict:
    """Safely extract description as a dictionary"""
    try:
        description = node.description if hasattr(node, 'description') else {}
        
        # If description is a string, try to parse it as JSON
        if isinstance(description, str):
            try:
                description = json.loads(description)
            except json.JSONDecodeError:
                logger.warning(f"Node description is a string but not valid JSON: {description[:100]}")
                return {}
        
        # Ensure it's a dict
        if not isinstance(description, dict):
            logger.warning(f"Node description is not a dict: {type(description)}")
            return {}
            
        return description
    except Exception as e:
        logger.error(f"Error extracting description dict: {e}")
        return {}


def _is_ai_tool(node: DynamicNodeResponse) -> bool:
    """Check if a node is usable as an AI tool"""
    try:
        description = _get_description_dict(node)
        # Only nodes with explicit usableAsTool=true are considered tools
        if 'usableAsTool' in description:
            return description.get('usableAsTool') is True
        return False
    except Exception as e:
        logger.warning(f"Error checking if node is AI tool: {e}")
        return False


def _is_ai_memory(node: DynamicNodeResponse) -> bool:
    """Check if a node is an AI memory node"""
    try:
        description = _get_description_dict(node)
        outputs = description.get('outputs', [])
        # Check if node has ai_memory output type
        return any(output.get('type') == 'ai_memory' for output in outputs if isinstance(output, dict))
    except Exception as e:
        logger.warning(f"Error checking if node is AI memory: {e}")
        return False


def _is_ai_model(node: DynamicNodeResponse) -> bool:
    """Check if a node is an AI language model"""
    try:
        description = _get_description_dict(node)
        outputs = description.get('outputs', [])
        # Check if node has ai_languageModel output type
        return any(output.get('type') == 'ai_languageModel' for output in outputs if isinstance(output, dict))
    except Exception as e:
        logger.warning(f"Error checking if node is AI model: {e}")
        return False


@router.get("/", response_model=List[DynamicNodeMetadataResponse])
async def list_node_types(
    active_only: bool = True,
    tools: Optional[bool] = Query(None, description="Filter AI tools (usableAsTool=true)"),
    memory: Optional[bool] = Query(None, description="Filter AI memory nodes"),
    model: Optional[bool] = Query(None, description="Filter AI language models"),
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
    node_filter: NodeAccessFilter = Depends(NodeAccessFilter),
):
    """
    List all available dynamic node types with AI-specific metadata.
    
    **IMPORTANT (2025-12 Update):**
    Node VISIBILITY restrictions have been DISABLED. All users can see all nodes.
    The node_filter.filter() call below returns all nodes when enable_filtering=false
    in config/node_plans.yaml. This is intentional - see services/dynamic_node_access.py.
    
    Node EXECUTION limits are enforced separately during workflow execution.
    
    Query parameters:
    - active_only: Only return active nodes (default: true)
    - tools: Filter nodes usable as AI tools (usableAsTool flag)
    - memory: Filter AI memory nodes (ai_memory output type)
    - model: Filter AI language models (ai_languageModel output type)
    
    Examples:
    - GET /node-types/ - All accessible nodes
    - GET /node-types/?tools=true - Only AI tools
    - GET /node-types/?memory=true - Only AI memory nodes
    - GET /node-types/?model=true - Only AI language models
    - GET /node-types/?tools=true&model=true - Both tools and models
    """
    # Get all nodes from database
    all_nodes = await crud.DynamicNodeCRUD.get_all_nodes(db, active_only=active_only)
    
    # Apply VIP/Base access filtering
    nodes = node_filter.filter(all_nodes)
    
    logger.debug(
        f"User {current_user.id} (Plan: {node_filter.plan_type}): "
        f"{len(nodes)}/{len(all_nodes)} nodes accessible"
    )

    def enrich_node_with_ai_metadata(node) -> DynamicNodeMetadataResponse:
        """Convert node to metadata response with AI fields"""
        # Convert to base response first
        if not isinstance(node, DynamicNodeResponse):
            base_node = DynamicNodeResponse.model_validate(node)
        else:
            base_node = node
            
        # Add AI-specific metadata
        return DynamicNodeMetadataResponse(
            **base_node.model_dump(),
            ai_tool=_is_ai_tool(base_node),
            ai_memory=_is_ai_memory(base_node),
            ai_model=_is_ai_model(base_node),
        )

    # Apply filters if specified
    if tools is True or memory is True or model is True:
        filtered_nodes = []
        for node in nodes:
            enriched_node = enrich_node_with_ai_metadata(node)
            include = False
            
            if tools is True and enriched_node.ai_tool:
                include = True
            if memory is True and enriched_node.ai_memory:
                include = True
            if model is True and enriched_node.ai_model:
                include = True
                
            if include:
                filtered_nodes.append(enriched_node)
        return filtered_nodes

    # Return all nodes with AI metadata
    return [enrich_node_with_ai_metadata(node) for node in nodes]
