"""
Execution Router - Handles execution data retrieval and formatting.

This module provides API endpoints for:
- Listing executions
- Getting execution details
- Getting formatted execution data with node outputs

Node Output Formatting Strategy:
- AI Agent: message, success (NO metrics - those go to ai_model)
- AI Model (Language Model): iterations, total_tokens, ai_model config
- AI Memory: memory_type, session_id, config
- AI Tool (Vector Store, etc.): tool_results from intermediate_steps
- AI Embedding: model, dimensions, status
- Chat: chatInput, sessionId
- Other nodes: pass-through with sensitive field stripping
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional, AsyncGenerator
from database import crud
from database.models import User
from models import ExecutionSummary
from auth.dependencies import get_current_user
from fastapi_pagination import Page, Params
import logging
import json

logger = logging.getLogger(__name__)


# ==================== Constants ====================

# Fields that should NEVER be exposed in API responses
SENSITIVE_FIELDS = {
    "credentials", "password", "api_key", "apiKey", "secret",
    "private_key", "privateKey", "access_token", "accessToken", 
    "refresh_token", "refreshToken", "auth", "authorization",
    "client_secret", "clientSecret", "webhook_secret", "webhookSecret",
    "encryption_key", "encryptionKey", "ssh_key", "sshKey",
}

# Fields that should NOT be filtered (safe token-related fields)
SAFE_FIELDS = {
    "total_tokens", "totalTokens", "input_tokens", "inputTokens",
    "output_tokens", "outputTokens", "prompt_tokens", "promptTokens",
    "completion_tokens", "completionTokens", "token_count", "tokenCount",
}

# AI connection types
AI_CONNECTION_TYPES = ("ai_tool", "ai_memory", "ai_languageModel", "ai_embedding", "ai_document")


# ==================== Security Utilities ====================

def _strip_sensitive_fields(data: Any, depth: int = 0) -> Any:
    """Recursively strip sensitive fields from data."""
    if depth > 10:
        return data
    
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            k_lower = k.lower()
            # Always keep safe fields
            if k in SAFE_FIELDS or k_lower in {s.lower() for s in SAFE_FIELDS}:
                result[k] = _strip_sensitive_fields(v, depth + 1)
            # Remove sensitive fields
            elif k_lower in SENSITIVE_FIELDS or any(s in k_lower for s in SENSITIVE_FIELDS):
                continue
            else:
                result[k] = _strip_sensitive_fields(v, depth + 1)
        return result
    elif isinstance(data, list):
        return [_strip_sensitive_fields(item, depth + 1) for item in data]
    return data


# ==================== Data Extraction Utilities ====================

def _extract_json_data(node_result: Any) -> Optional[Dict[str, Any]]:
    """Extract json_data from various node result formats."""
    if isinstance(node_result, list) and node_result:
        item = node_result[0]
        if isinstance(item, dict):
            return item.get("json_data", item) if "json_data" in item else item
    elif isinstance(node_result, dict):
        return node_result.get("json_data", node_result) if "json_data" in node_result else node_result
    return None


def _extract_raw_node_outputs(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract raw node outputs from execution data."""
    node_outputs = {}
    
    # Process node_results (primary source)
    source = data.get("node_results") or data.get("all_results") or {}
    
    for node_name, node_result in source.items():
        try:
            if isinstance(node_result, list) and node_result:
                flat_results = []
                for result_group in node_result:
                    if isinstance(result_group, list):
                        for item in result_group:
                            if isinstance(item, dict) and "json_data" in item:
                                flat_results.append({
                                    "json_data": item["json_data"],
                                    "binary_data": item.get("binary_data")
                                })
                            elif hasattr(item, 'json_data'):
                                flat_results.append({
                                    "json_data": item.json_data,
                                    "binary_data": getattr(item, 'binary_data', None)
                                })
                    elif isinstance(result_group, dict) and "json_data" in result_group:
                        flat_results.append({
                            "json_data": result_group["json_data"],
                            "binary_data": result_group.get("binary_data")
                        })
                node_outputs[node_name] = flat_results if flat_results else node_result
            else:
                node_outputs[node_name] = node_result
        except Exception as e:
            logger.warning(f"Error processing node_results for {node_name}: {e}")
    
    # Process shadow nodes if present
    for node_id, node_data in data.get("shadow_nodes", {}).items():
        try:
            node_name = node_data.get("name", node_id)
            shadow_data = node_data.get("data", {})
            if node_name not in node_outputs:
                node_outputs[node_name] = [{"json_data": shadow_data, "is_shadow": True}]
        except Exception as e:
            logger.warning(f"Error processing shadow_nodes for {node_id}: {e}")
    
    return node_outputs


# ==================== Workflow Analysis ====================

def _build_workflow_maps(workflow_data: Dict[str, Any]) -> tuple:
    """
    Build mappings from workflow data.
    
    Returns:
        - node_type_map: {node_name: node_type}
        - workflow_node_names: set of valid node names
        - ai_connections: {node_name: {"connection_type": str, "target_node": str}}
        - nodes_list: list of node definitions
    """
    node_type_map = {}
    workflow_node_names = set()
    ai_connections = {}
    
    nodes_list = workflow_data.get("nodes", []) if workflow_data else []
    
    # Build node type map
    for node in nodes_list:
        node_name = node.get("name", "")
        node_type = node.get("type", "")
        if node_name and node_type:
            node_type_map[node_name] = node_type.lower()
            workflow_node_names.add(node_name)
    
    # Extract AI connections
    connections = workflow_data.get("connections", {}) if workflow_data else {}
    
    for source_node, conn_outputs in connections.items():
        for output_type, conn_list in conn_outputs.items():
            # Extract target node and connection type from the inner structure
            # Connection format: {"node": "AI Agent", "type": "ai_tool", "index": 0}
            if isinstance(conn_list, list):
                for conn_group in conn_list:
                    if isinstance(conn_group, list):
                        for conn in conn_group:
                            if isinstance(conn, dict):
                                target_node = conn.get("node", "")
                                conn_type = conn.get("type", "")
                                # Check if this is an AI connection
                                if conn_type in AI_CONNECTION_TYPES:
                                    ai_connections[source_node] = {
                                        "connection_type": conn_type,
                                        "target_node": target_node
                                    }
                                break
                        if source_node in ai_connections:
                            break
    
    return node_type_map, workflow_node_names, ai_connections, nodes_list


def _collect_ai_agents(node_outputs: Dict, workflow_node_names: set, node_type_map: Dict) -> Dict:
    """
    Collect all AI Agent nodes and their data.
    
    Returns:
        {agent_name: {"data": json_data, "tool_results": {tool_name: result}, "tool_names": [...]}}
    """
    ai_agents = {}
    
    for node_name, node_result in node_outputs.items():
        if node_name not in workflow_node_names:
            continue
        
        if node_type_map.get(node_name) != "ai_agent":
            continue
        
        json_data = _extract_json_data(node_result)
        if not json_data or not isinstance(json_data, dict):
            continue
        
        if "message" not in json_data and "intermediate_steps" not in json_data:
            continue
        
        # Extract tool results from intermediate_steps
        tool_results = {}
        for step in json_data.get("intermediate_steps", []):
            action = step.get("action", {})
            tool_name = action.get("tool")
            if tool_name:
                tool_input = action.get("tool_input", {})
                observation = step.get("observation", {})
                tool_results[tool_name] = {
                    "tool": tool_name,
                    "query": tool_input.get("query") if isinstance(tool_input, dict) else tool_input,
                    "observation": _format_tool_observation(observation),
                }
        
        # Get the list of tool names from providers (for mapping to canvas nodes)
        tool_names = json_data.get("providers", {}).get("tools", [])
        
        ai_agents[node_name] = {
            "data": json_data,
            "tool_results": tool_results,
            "tool_names": tool_names,
        }
    
    return ai_agents


# ==================== Node Formatters (Single Source of Truth) ====================

def _format_ai_agent(agent_data: Dict) -> Dict:
    """
    Format AI Agent output.
    
    AI Agent shows: message, success
    Metrics (iterations, total_tokens) go to the connected ai_model node.
    """
    return {
        "message": agent_data.get("message"),
        "success": agent_data.get("success"),
    }


def _format_ai_model(agent_data: Dict) -> Dict:
    """
    Format AI Language Model output.
    
    AI Model shows: iterations, total_tokens, ai_model config
    This is where execution metrics belong (not on AI Agent).
    """
    result = {}
    
    # Execution metrics from the AI Agent's execution
    if "iterations" in agent_data:
        result["iterations"] = agent_data["iterations"]
    if "total_tokens" in agent_data:
        result["total_tokens"] = agent_data["total_tokens"]
    
    # Model configuration from providers
    providers = agent_data.get("providers", {})
    ai_model = providers.get("ai_model", {})
    if ai_model:
        result["ai_model"] = {
            k: v for k, v in {
                "provider": ai_model.get("provider"),
                "model": ai_model.get("model"),
                "temperature": ai_model.get("temperature"),
            }.items() if v is not None
        }
    
    return result


def _format_ai_memory(json_data: Dict, providers_memory: Dict = None) -> Dict:
    """Format AI Memory node output."""
    # Try to get memory info from json_data first, then from providers
    ai_memory = json_data.get("ai_memory", {}) if json_data else {}
    if not ai_memory and providers_memory:
        ai_memory = providers_memory
    
    result = {
        "memory_type": json_data.get("type") or ai_memory.get("type"),
        "session_id": json_data.get("session_id") or ai_memory.get("session_id") or json_data.get("sessionId"),
    }
    
    if isinstance(ai_memory, dict):
        if ai_memory.get("context_window_length"):
            result["context_window_length"] = ai_memory["context_window_length"]
        if ai_memory.get("ttl_seconds"):
            result["ttl_seconds"] = ai_memory["ttl_seconds"]
    
    return {k: v for k, v in result.items() if v is not None}


def _format_ai_embedding(json_data: Dict = None, node_params: Dict = None) -> Dict:
    """Format AI Embedding node output."""
    # Try json_data first, then node parameters
    ai_embedding = {}
    if json_data:
        ai_embedding = json_data.get("ai_embedding", json_data)
    
    result = {
        "type": "ai_embedding",
        "model": ai_embedding.get("model") or (node_params or {}).get("model"),
        "dimensions": ai_embedding.get("dimensions") or (node_params or {}).get("dimensions"),
        "status": "embedding_provider",
    }
    return {k: v for k, v in result.items() if v is not None}


def _format_tool_results(tool_results: List[Dict]) -> Dict:
    """Format AI Tool node output with tool results."""
    return {"tool_results": tool_results}


def _format_chat(json_data: Dict) -> Dict:
    """Format Chat trigger node output."""
    return {
        "chatInput": json_data.get("chatInput"),
        "sessionId": json_data.get("sessionId"),
    }


def _format_vector_store(json_data: Dict) -> Dict:
    """Format Vector Store node output."""
    if "items" in json_data:
        return {
            "operation": json_data.get("operation", "retrieve"),
            "results_count": json_data.get("count", len(json_data.get("items", []))),
            "items": _format_vector_items(json_data.get("items", []))[:10],
        }
    return json_data


def _format_tool_observation(observation: Any) -> Any:
    """Format tool observation into a clean structure."""
    if not observation:
        return None
    
    if isinstance(observation, str):
        return {"result": observation[:500]}
    
    if isinstance(observation, dict):
        if "items" in observation:
            return {
                "type": "vector_search",
                "results_count": observation.get("count", len(observation.get("items", []))),
                "items": _format_vector_items(observation.get("items", []))[:10],
            }
        
        if "payload" in observation:
            payload = observation.get("payload", {})
            result = {"type": "document"}
            if isinstance(payload, dict):
                if "pageContent" in payload:
                    result["content"] = payload["pageContent"][:500]
            return result
        
        safe_keys = {"status", "success", "message", "count", "result", "data"}
        return {k: v for k, v in observation.items() if k in safe_keys}
    
    if isinstance(observation, list):
        return {"type": "list", "count": len(observation)}
    
    return observation


def _format_vector_items(items: List[Dict]) -> List[Dict]:
    """Format vector search result items."""
    formatted = []
    
    for item in items:
        formatted_item = {}
        text = item.get("text", "")
        
        if isinstance(text, str) and text.startswith("{"):
            try:
                parsed = json.loads(text)
                content = parsed.get("pageContent", "")
                formatted_item["content"] = content[:500] if content else ""
                metadata = parsed.get("metadata", {})
                if metadata.get("search_title") or metadata.get("title_normalized"):
                    formatted_item["title"] = metadata.get("search_title") or metadata.get("title_normalized")
                if metadata.get("clause"):
                    formatted_item["clause"] = metadata["clause"]
                if metadata.get("type"):
                    formatted_item["type"] = metadata["type"]
            except (json.JSONDecodeError, TypeError):
                formatted_item["content"] = text[:500] if text else ""
        elif text:
            formatted_item["content"] = str(text)[:500]
        
        if "score" in item:
            formatted_item["score"] = item["score"]
        
        if formatted_item.get("content") or formatted_item.get("title"):
            formatted.append(formatted_item)
    
    return formatted


# ==================== Main Formatting Function ====================

def build_formatted_node_logs(
    node_outputs: Dict[str, Any],
    workflow_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build formatted logs for all nodes in the execution.
    
    Formatting strategy:
    1. AI Agent: message, success (metrics go to ai_model)
    2. AI Model: iterations, total_tokens, ai_model config
    3. AI Memory: memory_type, session_id, config
    4. AI Tool: tool_results from intermediate_steps
    5. AI Embedding: model, dimensions
    6. Other nodes: type-specific formatting
    """
    formatted_logs = {}
    
    # Build workflow maps
    node_type_map, workflow_node_names, ai_connections, nodes_list = _build_workflow_maps(workflow_data)
    
    # Collect AI Agents and their data
    ai_agents = _collect_ai_agents(node_outputs, workflow_node_names, node_type_map)
    
    # Build canvas node -> tool name mapping
    # Tool name for Qdrant is: search_{collection_name}
    # We need to map "Qdrant Vector Store" -> "search_tax_laws"
    canvas_to_tool_name = {}
    for node in nodes_list:
        node_name = node.get("name", "")
        node_type_raw = node.get("type", "").lower()
        params = node.get("parameters", {})
        
        # For Qdrant vector stores, tool name is search_{collection_name}
        if node_type_raw == "qdrantvectorstore":
            collection_name = params.get("collectionName", "")
            if collection_name:
                tool_name = f"search_{collection_name.lower().replace(' ', '_')}"
                canvas_to_tool_name[node_name] = tool_name
    
    # Build tool results mapping: {canvas_node_name: [tool_results]}
    tool_node_results = {}
    for agent_name, agent_info in ai_agents.items():
        tool_results = agent_info["tool_results"]  # {tool_name: result}
        
        # Find tool nodes connected to this agent
        for canvas_node_name, conn_info in ai_connections.items():
            if conn_info.get("connection_type") == "ai_tool" and conn_info.get("target_node") == agent_name:
                # Try to find the tool name for this canvas node
                tool_name = canvas_to_tool_name.get(canvas_node_name)
                if tool_name and tool_name in tool_results:
                    tool_node_results[canvas_node_name] = [tool_results[tool_name]]
                elif tool_results:
                    # Fallback: if only one tool, use it
                    if len(tool_results) == 1:
                        tool_node_results[canvas_node_name] = list(tool_results.values())
    
    # Format each node
    for node_name, node_result in node_outputs.items():
        # Skip non-workflow nodes (tool execution results)
        if node_name not in workflow_node_names:
            continue
        
        node_type = node_type_map.get(node_name, "")
        conn_info = ai_connections.get(node_name, {})
        connection_type = conn_info.get("connection_type")
        target_agent = conn_info.get("target_node")
        json_data = _extract_json_data(node_result)
        
        if not json_data:
            continue
        
        try:
            # ==================== AI Agent ====================
            if node_type == "ai_agent" and node_name in ai_agents:
                formatted_logs[node_name] = _format_ai_agent(ai_agents[node_name]["data"])
                continue
            
            # ==================== AI Language Model ====================
            if node_type == "ai_languagemodel" or connection_type == "ai_languageModel":
                # Get the parent agent's data
                parent_agent_data = ai_agents.get(target_agent, {}).get("data")
                if not parent_agent_data and ai_agents:
                    # Fallback: if no specific target, use any available agent
                    parent_agent_data = next(iter(ai_agents.values()), {}).get("data")
                
                if parent_agent_data:
                    formatted_logs[node_name] = _format_ai_model(parent_agent_data)
                continue
            
            # ==================== AI Memory ====================
            if node_type in ("buffer_memory", "redis_memory") or connection_type == "ai_memory":
                parent_agent_data = ai_agents.get(target_agent, {}).get("data") if target_agent else None
                providers_memory = parent_agent_data.get("providers", {}).get("ai_memory") if parent_agent_data else None
                formatted_logs[node_name] = _format_ai_memory(json_data, providers_memory)
                continue
            
            # ==================== AI Tool (Vector Store in tool mode) ====================
            if connection_type == "ai_tool":
                if node_name in tool_node_results and tool_node_results[node_name]:
                    formatted_logs[node_name] = _format_tool_results(tool_node_results[node_name])
                else:
                    # Tool was connected but not called
                    formatted_logs[node_name] = {"status": "tool_not_called"}
                continue
            
            # ==================== AI Embedding ====================
            if node_type == "ai_embedding" or connection_type == "ai_embedding":
                node_params = next((n.get("parameters", {}) for n in nodes_list if n.get("name") == node_name), {})
                formatted_logs[node_name] = _format_ai_embedding(json_data, node_params)
                continue
            
            # ==================== Chat Trigger ====================
            if node_type == "chat" or ("chat" in node_name.lower() and "chatInput" in json_data):
                formatted_logs[node_name] = _format_chat(json_data)
                continue
            
            # ==================== Vector Store (regular mode, not as tool) ====================
            if node_type == "qdrantvectorstore" and connection_type != "ai_tool":
                formatted_logs[node_name] = _format_vector_store(json_data)
                continue
            
            # ==================== Default: pass through ====================
            formatted_logs[node_name] = json_data
            
        except Exception as e:
            logger.warning(f"Error formatting node {node_name}: {e}")
            formatted_logs[node_name] = json_data
    
    # Add AI-connected nodes that aren't in node_outputs
    for node_name, conn_info in ai_connections.items():
        if node_name in formatted_logs:
            continue
        
        connection_type = conn_info.get("connection_type")
        target_agent = conn_info.get("target_node")
        parent_agent_data = ai_agents.get(target_agent, {}).get("data") if target_agent else None
        
        if connection_type == "ai_languageModel" and parent_agent_data:
            formatted_logs[node_name] = _format_ai_model(parent_agent_data)
        elif connection_type == "ai_memory" and parent_agent_data:
            providers_memory = parent_agent_data.get("providers", {}).get("ai_memory")
            formatted_logs[node_name] = _format_ai_memory({}, providers_memory)
        elif connection_type == "ai_embedding":
            node_params = next((n.get("parameters", {}) for n in nodes_list if n.get("name") == node_name), {})
            formatted_logs[node_name] = _format_ai_embedding(None, node_params)
        elif connection_type == "ai_tool":
            if node_name in tool_node_results and tool_node_results[node_name]:
                formatted_logs[node_name] = _format_tool_results(tool_node_results[node_name])
            else:
                formatted_logs[node_name] = {"status": "tool_not_called"}
    
    return formatted_logs


# ==================== API Router ====================

router = APIRouter()


async def get_db_from_app(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get database session from app state."""
    async with request.app.state.session_factory() as session:
        yield session


@router.get("/", response_model=Page[ExecutionSummary])
async def list_executions(
    params: Params = Depends(),
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """List all executions for the current user with pagination."""
    return await crud.ExecutionCRUD.get_all_executions(
        db, user_id=current_user.id, params=params
    )


@router.get("/{execution_id}", operation_id="get_execution_by_id")
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Get details for a specific execution."""
    execution = await crud.ExecutionCRUD.get_execution(db, execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    workflow = await crud.WorkflowCRUD.get_workflow(db, execution['workflow_id'])
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return execution


@router.get("/{execution_id}/data", operation_id="get_execution_data_by_id")
async def get_execution_data(
    execution_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """
    Get execution data for a specific execution.
    
    Returns:
        - output: Raw output from the workflow
        - error: Any execution error
        - workflow_data: Full workflow definition
        - node_outputs: Formatted node outputs
        - langfuse_trace_id: Trace ID for observability
    """
    execution = await crud.ExecutionCRUD.get_execution_with_data(db, execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    workflow = await crud.WorkflowCRUD.get_workflow(db, execution.workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if not execution.executionData:
        raise HTTPException(status_code=404, detail="No execution data available")
    
    try:
        data = json.loads(execution.executionData.data) if execution.executionData.data else {}
        workflow_data = execution.executionData.workflow_data or {}
        
        # Build formatted node outputs
        node_outputs = build_formatted_node_logs(
            _extract_raw_node_outputs(data),
            workflow_data
        )
        
        # Build response
        response = {
            "output": data.get("output", {}),
            "error": data.get("error"),
            "workflow_data": workflow_data,
            "node_outputs": node_outputs,
            "langfuse_trace_id": data.get("langfuse_trace_id"),
        }
        
        # Strip sensitive fields
        return _strip_sensitive_fields(response)
        
    except Exception as e:
        import traceback
        logger.error(f"Error parsing execution data: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing execution data: {str(e)}")
