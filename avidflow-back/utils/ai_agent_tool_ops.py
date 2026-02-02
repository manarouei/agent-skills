from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Callable
import json
import uuid
import logging

from utils.ai_agent_text import smart_truncate, select_relevant_items
from utils.ai_agent_args import validate_and_coerce_args
from utils.ai_agent_tooling import classify_tools
from utils.tool_schema import build_tool_schema
from utils.common_params import normalize_parameters as normalize_params_util
from utils.node_loader import resolve_node_definitions as resolve_node_definitions_util
from utils.tool_runner import execute_tool as execute_tool_util

logger = logging.getLogger(__name__)


def _is_mcp_tool_node(node_model) -> bool:
    """Check if a tool node is an MCP client."""
    return node_model.type == "mcpClientTool"

def process_tool_response(
    tool_key: str,
    tool_name: str,
    response: Dict[str, Any] | List[Any],
    user_query: str,
    node_type: Optional[str] = None,
) -> Dict[str, Any]:
    if isinstance(response, list):
        response = {"items": response, "count": len(response)}
    if not isinstance(response, dict) or not response or response.get("error"):
        return response if isinstance(response, dict) else {"items": response, "count": len(response) if isinstance(response, list) else 0}

    processed = dict(response)
    items = processed.get("items")
    if isinstance(items, list) and items:
        # CRITICAL FIX: For vector store retrievers (Qdrant, Pinecone, etc),
        # skip relevance filtering since they already did semantic search.
        # For other tools, apply light filtering to fit context window.
        #
        # IMPROVED: Check both node_type (more reliable) and tool_name (backward compat)
        is_vector_store_type = node_type in [
            "qdrantVectorStore", 
            "pineconeVectorStore", 
            "vectorStoreQdrant",
            "weaviateVectorStore",
            "supabaseVectorStore"
        ] if node_type else False
        
        is_vector_store_name = any(key in (tool_name or "").lower() for key in [
            "qdrant", 
            "pinecone", 
            "vector", 
            "retriev",
            "search_tax",  # Custom tool names
            "embeddings",
            "semantic"
        ])
        
        is_vector_store = is_vector_store_type or is_vector_store_name
        
        # DEBUG: Log detection for troubleshooting
        logger.info(
            f"[Tool Response] Detection: tool_name='{tool_name}', node_type='{node_type}', "
            f"is_vector_store={is_vector_store} (type={is_vector_store_type}, name={is_vector_store_name}), "
            f"items_count={len(items)}"
        )
        
        if is_vector_store:
            # Vector stores already returned semantically relevant results
            # Pass ALL items through (no limit, no filtering)
            logger.info(f"[Tool Response] ✓ Vector store detected, passing through ALL {len(items)} items (no filtering)")
            selected = {
                "items": items,  # FIXED: No limit (was items[:50])
                "total": len(items),
                "note": f"all {len(items)} items from vector search (semantic relevance pre-filtered)",
                "_skip_truncation": True  # NEW: Signal to skip aggressive truncation
            }
        else:
            # Other tools: apply relevance filtering with expanded limits
            logger.info(f"[Tool Response] Non-vector tool, applying keyword relevance filter")
            selected = select_relevant_items(items, user_query=user_query, limit=30, max_chars=15000)
        
        processed["items"] = selected["items"]
        processed["selected_count"] = len(selected["items"])
        processed["total_count"] = selected["total"]
        processed["selection_note"] = selected["note"]
        
        # CRITICAL: Propagate the _skip_truncation flag to processed dict
        if "_skip_truncation" in selected:
            processed["_skip_truncation"] = selected["_skip_truncation"]
            processed["_vector_store_max_tokens"] = 40000  # Higher token budget for vector stores
            logger.info("[Tool Response] ✓ Added _skip_truncation flag to processed data")
        
        # DEBUG: Log actual filtering result
        logger.info(
            f"[Tool Response] After processing: selected {len(selected['items'])} of {selected['total']} items "
            f"({100*len(selected['items'])//selected['total']}% retained)"
        )

    large_fields = {"raw", "rawDocument", "rawContent", "binary", "binaryData", "blob", "contentBytes"}
    for fld in large_fields:
        if fld in processed:
            val = processed[fld]
            try:
                size = len(val) if isinstance(val, (str, bytes, bytearray)) else len(json.dumps(val)[:20000])
            except Exception:
                size = 0
            processed[fld] = f"[{fld} removed ({size} bytes)]"

    MAX_TOTAL = 12000
    MAX_FIELD = 8000
    text_fields: List[Tuple[str, int]] = [(k, len(v)) for k, v in processed.items() if isinstance(v, str) and len(v) > 100]

    for k, ln in text_fields:
        if ln > MAX_FIELD:
            processed[k] = smart_truncate(processed[k], MAX_FIELD)
            processed[f"{k}_truncated"] = True
            processed[f"{k}_original_length"] = ln

    def total_len(d: Dict[str, Any]) -> int:
        return sum(len(v) for v in d.values() if isinstance(v, str))

    total = total_len(processed)
    if total > MAX_TOTAL:
        for k, ln in sorted(text_fields, key=lambda x: x[1], reverse=True):
            if total <= MAX_TOTAL:
                break
            val = processed.get(k)
            if not isinstance(val, str):
                continue
            if processed.get(f"{k}_truncated"):
                processed[k] = f"[content omitted to fit context: {ln} chars]"
            else:
                processed[k] = smart_truncate(val, max(MAX_TOTAL // 2, 4000))
                processed[f"{k}_truncated"] = True
                processed[f"{k}_original_length"] = ln
            total = total_len(processed)
    return processed


def prepare_tools(
    owner: Any,
    tool_nodes: List[Any],
    node_definitions: Optional[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Callable], Dict[str, Dict[str, Any]]]:
    """
    Pure util version:
    - Uses utils.common_params.normalize_parameters
    - Uses utils.node_loader.resolve_node_definitions
    - No reliance on owner having helper methods
    """
    tools: List[Dict[str, Any]] = []
    executors: Dict[str, Callable[[], Tuple[Any, Any]]] = {}
    param_schemas: Dict[str, Dict[str, Any]] = {}

    workflow = getattr(owner, "workflow", None)
    nd = resolve_node_definitions_util(node_definitions, workflow, tool_nodes or [])
    if not nd:
        logger.warning("[AI Agent] No node_definitions available; skipping tools.")
        return tools, executors, param_schemas

    for m in (tool_nodes or []):
        # NEW: Check if this is an MCP tool and handle differently
        if _is_mcp_tool_node(m):
            # For MCP tools, we need to list available tools first
            mcp_tools_list = _prepare_mcp_tools(owner, m)
            if mcp_tools_list:
                tools.extend(mcp_tools_list["tools"])  # Changed from schemas to tools
                executors.update(mcp_tools_list["executors"])
                param_schemas.update(mcp_tools_list["param_schemas"])
            continue  # Skip normal tool schema building for MCP
        
        info = nd.get(m.type)
        if not info:
            logger.warning("[Agent Tool Ops] No definition for tool node type '%s' (node '%s')", m.type, m.name)
            continue

        node_cls = info.get("node_class") or info.get("class") or info.get("cls")
        if not node_cls or not isinstance(node_cls, type):
            logger.warning("[Agent Tool Ops] node_definitions entry for type '%s' lacks 'node_class'", m.type)
            continue

        # Sanitize tool name to match OpenAI's pattern: ^[a-zA-Z0-9_-]+$
        # Remove parentheses, brackets, and other special characters
        func_name = f"{m.name}".replace("-", "_").replace(" ", "_")
        func_name = ''.join(c for c in func_name if c.isalnum() or c in ('_', '-'))
        func_key = func_name.lower()

        selected_params = normalize_params_util(getattr(m, "parameters", None)) or {}

        schema = build_tool_schema(node_cls, selected_params=selected_params)
        params = schema.get("parameters", {"type": "object", "properties": {}, "required": []})
        props = params.get("properties") or {}
        
        # DEBUG: Log the tool schema to see what's being sent to the LLM
        logger.info(f"[Tool Schema Debug] Tool: {m.name}")
        logger.info(f"[Tool Schema Debug]   Selected params keys: {list(selected_params.keys())[:10]}")
        logger.info(f"[Tool Schema Debug]   Schema properties: {list(props.keys())}")
        for prop_name, prop_schema in list(props.items())[:5]:
            logger.info(f"[Tool Schema Debug]     {prop_name}: type={prop_schema.get('type')}, default={prop_schema.get('default')}, const={prop_schema.get('const')}")
        
        raw_required = list(params.get("required") or [])
        # Keep required fields that exist in properties
        # Remove fields that have actual default values (non-None, non-empty)
        params["required"] = [
            r for r in raw_required
            if r in props
        ]

        description = schema.get("description", "") or ""
        if m.type:
            node_type = m.type.replace("@n8n/n8n-nodes-langchain.", "").replace("n8n-nodes-base.", "")
            if not description.endswith(node_type):
                description = f"{description} ({node_type})"

        tools.append({
            "type": "function",
            "function": {
                "name": func_name,
                "description": description,
                "parameters": params,
            },
        })

        executors[func_key] = (lambda c=node_cls, mm=m: (c, mm))
        param_schemas[func_key] = params
        logger.info(
            "[AI Agent] Registered tool func_name='%s' func_key='%s' -> node(id='%s', name='%s', type='%s')",
            func_name, func_key, getattr(m, "id", "<no-id>"), getattr(m, "name", "<unnamed>"),
            getattr(m, "type", "<no-type>")
        )

    return tools, executors, param_schemas


def _prepare_mcp_tools(
    agent,
    node_model
) -> Optional[Dict[str, Any]]:
    """
    Prepare MCP tools by listing available tools from the MCP server.
    
    Returns:
        Dict with 'tools', 'executors', 'param_schemas' for all MCP tools
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Execute listTools operation on MCP node
        from utils.tool_runner import execute_tool as _execute_tool_util
        
        node_cls = agent._node_cls(node_model.type)
        if not node_cls:
            return None
        
        # Force listTools operation
        list_tools_args = {
            "nodeType": "mcpClientTool",
            "operation": "listTools",
        }
        
        # Copy transport config from node parameters
        params = node_model.parameters or {}
        for key in ["transport", "command", "args", "env", "url", "headers", "options"]:
            if key in params:
                list_tools_args[key] = params[key]
        
        logger.info(f"[Tool Ops] Listing tools from MCP node: {node_model.name}")
        result = _execute_tool_util(agent, node_cls, node_model, list_tools_args)
        
        # Parse the tools list
        if not result or "error" in result:
            logger.error(f"[Tool Ops] Failed to list MCP tools: {result.get('error')}")
            return None
        
        # Extract tools from response
        tools_data = result.get("tools", [])
        if not tools_data:
            logger.warning(f"[Tool Ops] No tools found in MCP server response")
            return None
        
        logger.info(f"[Tool Ops] Found {len(tools_data)} MCP tools")
        
        # Convert MCP tools to agent tool schemas
        tools = []
        executors = {}
        param_schemas = {}
        
        for mcp_tool in tools_data:
            tool_name = mcp_tool.get("name", "")
            if not tool_name:
                continue
            
            # Get input schema
            input_schema = mcp_tool.get("inputSchema", {})
            
            # Build tool schema in OpenAI function format
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": mcp_tool.get("description", ""),
                    "parameters": input_schema
                }
            }
            tools.append(tool_schema)
            
            # Build executor that will call the MCP tool
            # Store node_model, tool_name, and node_cls for execution
            def make_mcp_executor(node_m, tool_n, mcp_node_cls):
                def executor():
                    return (mcp_node_cls, node_m, tool_n)
                return executor
            
            # Use lowercase for key consistency
            tool_key = tool_name.lower()
            executors[tool_key] = make_mcp_executor(node_model, tool_name, node_cls)
            param_schemas[tool_key] = input_schema
        
        return {
            "tools": tools,  # Changed from "schemas" to "tools"
            "executors": executors,
            "param_schemas": param_schemas
        }
        
    except Exception as e:
        logger.error(f"[Tool Ops] Error preparing MCP tools: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def handle_model_tool_calls(
    owner: Any,
    tool_calls: List[Dict[str, Any]],
    executors: Dict[str, Callable[[], Tuple[Any, Any]]],
    tool_param_schemas: Dict[str, Dict[str, Any]],
    messages: List[Dict[str, Any]],
    intermediate: List[Dict[str, Any]],
    assistant_text: str,
    user_query: str,
) -> None:
    for tc in tool_calls:
        tool_key = str(tc.get("name", "")).strip().lower()
        raw_args = tc.get("arguments", {}) if isinstance(tc.get("arguments"), dict) else {}
        schema = tool_param_schemas.get(tool_key)
        ok_args = raw_args
        validation_info = None

        if schema:
            ok, coerced, details = validate_and_coerce_args(schema, raw_args)
            if not ok:
                obs = {"ok": False, "error": "Invalid tool arguments", "validation": details}
                intermediate.append({"action": {"tool": tool_key, "tool_input": raw_args}, "observation": obs})
                messages.append({
                    "role": "tool",
                    "name": tc.get("name", ""),
                    "content": json.dumps(obs, default=str),
                    "tool_call_id": tc.get("id", ""),
                })
                try:
                    getattr(owner, "_publish_agent_event", lambda *_args, **_kw: None)("tool_result", {"tool": tool_key, "ok": False})
                except Exception:
                    pass
                continue
            ok_args, validation_info = coerced, (details or None)

        if tool_key in executors:
            try:
                # FIXED: Handle both 2-tuple (normal tools) and 3-tuple (MCP tools)
                executor_result = executors[tool_key]()
                
                if len(executor_result) == 3:
                    # MCP tool: (node_cls, node_model, tool_name)
                    node_cls, node_model, mcp_tool_name = executor_result
                    
                    # CRITICAL: Force executeTool operation for MCP tools
                    ok_args = {
                        **ok_args,
                        "operation": "executeTool",  # Force executeTool, not listTools
                        "toolName": mcp_tool_name,
                        "toolArguments": json.dumps(ok_args) if ok_args else "{}"
                    }
                    
                    # Copy transport config from node model if not in args
                    node_params = getattr(node_model, "parameters", None) or {}
                    for key in ["transport", "command", "args", "env", "url", "headers", "options"]:
                        if key not in ok_args and key in node_params:
                            ok_args[key] = node_params[key]
                    
                elif len(executor_result) == 2:
                    # Normal tool: (node_cls, node_model)
                    node_cls, node_model = executor_result
                else:
                    raise ValueError(f"Unexpected executor result length: {len(executor_result)}")
                
                raw_obs = execute_tool_util(owner, node_cls, node_model, ok_args, expr_json={"message": assistant_text, "user_query": user_query, "chatInput": user_query})
                # FIXED: Pass node_type for vector store detection
                obs = process_tool_response(
                    tool_key, 
                    str(tc.get("name", "")), 
                    raw_obs, 
                    user_query or assistant_text or "",
                    node_type=getattr(node_model, "type", None)
                )
                if validation_info:
                    obs["_arg_validation"] = "coerced"
                # publish tool result
                try:
                    getattr(owner, "_publish_agent_event", lambda *_args, **_kw: None)("tool_result", {"tool": tool_key, "ok": "error" not in obs})
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[Tool Ops] Error executing tool {tool_key}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                obs = {"error": str(e)}
                try:
                    getattr(owner, "_publish_agent_event", lambda *_args, **_kw: None)("tool_result", {"tool": tool_key, "ok": False})
                except Exception:
                    pass
        else:
            obs = {"error": f"Tool {tool_key} not registered"}
            try:
                getattr(owner, "_publish_agent_event", lambda *_args, **_kw: None)("tool_result", {"tool": tool_key, "ok": False})
            except Exception:
                pass

        intermediate.append({"action": {"tool": tool_key, "tool_input": ok_args}, "observation": obs})
        messages.append({
            "role": "tool",
            "name": tc.get("name", ""),
            "content": json.dumps(obs, default=str),
            "tool_call_id": tc.get("id", ""),
        })


def maybe_autocall_single_tool(
    owner: Any,
    tools: List[Dict[str, Any]],
    tool_param_schemas: Dict[str, Dict[str, Any]],
    executors: Dict[str, Callable[[], Tuple[Any, Any]]],
    user_input: str,
    messages: List[Dict[str, Any]],
    intermediate: List[Dict[str, Any]],
    assistant_text: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not (tools and len(tools) == 1):
        return None

    fn = (tools[0] or {}).get("function", {})
    fname = str(fn.get("name", "")).strip()
    fkey = fname.lower()

    schema = tool_param_schemas.get(fkey) or {}
    props = schema.get("properties", {}) if schema else {}
    required = list(schema.get("required") or [])

    inferred_args: Dict[str, Any] = {}
    if "text" in required and (props.get("text", {}).get("default") in (None, "")):
        inferred_args["text"] = user_input
    for p, meta in (props or {}).items():
        if p not in inferred_args and "default" in meta:
            inferred_args[p] = meta["default"]

    if not all(r in inferred_args for r in required):
        return None

    ok_args = inferred_args
    try:
        if schema:
            ok, coerced, details = validate_and_coerce_args(schema, inferred_args)
            if not ok:
                obs = {"ok": False, "error": "Invalid tool arguments", "validation": details}
            else:
                ok_args = coerced
                # FIXED: Handle both 2-tuple and 3-tuple
                executor_result = executors[fkey]()
                if len(executor_result) == 3:
                    node_cls, node_model, mcp_tool_name = executor_result
                    # CRITICAL: Force executeTool for MCP
                    ok_args = {
                        **ok_args,
                        "operation": "executeTool",
                        "toolName": mcp_tool_name,
                        "toolArguments": json.dumps(ok_args) if ok_args else "{}"
                    }
                    node_params = getattr(node_model, "parameters", None) or {}
                    for key in ["transport", "command", "args", "env", "url", "headers", "options"]:
                        if key not in ok_args and key in node_params:
                            ok_args[key] = node_params[key]
                else:
                    node_cls, node_model = executor_result
                
                obs = execute_tool_util(
                    owner, node_cls, node_model, ok_args,
                    expr_json={"message": (assistant_text or user_input or ""), "user_query": user_input, "chatInput": user_input}
                )
                if details:
                    obs["_arg_validation"] = "coerced"
        else:
            # FIXED: Handle both 2-tuple and 3-tuple
            executor_result = executors[fkey]()
            if len(executor_result) == 3:
                node_cls, node_model, mcp_tool_name = executor_result
                ok_args = {
                    **ok_args,
                    "operation": "executeTool",
                    "toolName": mcp_tool_name,
                    "toolArguments": json.dumps(ok_args) if ok_args else "{}"
                }
                node_params = getattr(node_model, "parameters", None) or {}
                for key in ["transport", "command", "args", "env", "url", "headers", "options"]:
                    if key not in ok_args and key in node_params:
                        ok_args[key] = node_params[key]
            else:
                node_cls, node_model = executor_result
            
            obs = execute_tool_util(
                owner, node_cls, node_model, ok_args,
                expr_json={"message": (assistant_text or user_input or ""), "user_query": user_input, "chatInput": user_input}
            )
    except Exception as e:
        logger.error(f"[Tool Ops] Error in autocall: {e}")
        import traceback
        logger.error(traceback.format_exc())
        obs = {"error": str(e)}

    intermediate.append({"action": {"tool": fkey, "tool_input": ok_args}, "observation": obs})

    auto_id = f"auto-{uuid.uuid4().hex[:12]}"
    messages.append({
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": auto_id,
            "type": "function",
            "function": {
                "name": fname,
                "arguments": json.dumps(inferred_args, default=str),  # Use original args for message
            },
        }],
    })
    messages.append({
        "role": "tool",
        "name": fname,
        "content": json.dumps(obs, default=str),
        "tool_call_id": auto_id,
    })

    return {"auto_called": True}


def deliver_via_text_tool(
    owner: Any,
    tools: List[Dict[str, Any]],
    executors: Dict[str, Callable[[], Tuple[Any, Any]]],
    tool_param_schemas: Dict[str, Dict[str, Any]],
    messages: List[Dict[str, Any]],
    intermediate: List[Dict[str, Any]],
    final_text: str,
) -> Optional[Dict[str, Any]]:
    if not final_text or not tools:
        return None
    
    classes = classify_tools(tools)
    delivery = (classes or {}).get("delivery") or []
    if not delivery:
        return None

    delivery_keys = {n.lower() for n in delivery}
    if any((isinstance(step, dict) and (step.get("action", {}) or {}).get("tool") in delivery_keys)
           for step in (intermediate or [])):
        return None
    if any(m.get("role") == "tool" and str(m.get("name", "")).lower() in delivery_keys for m in (messages[-10:] or [])):
        return None

    fname = delivery[0]
    fkey = fname.lower()
    schema = tool_param_schemas.get(fkey) or {}
    props = (schema.get("properties") or {})
    if "text" not in props:
        return None

    args: Dict[str, Any] = {"text": final_text}
    for p, meta in (props or {}).items():
        if p not in args and "default" in meta:
            args[p] = meta["default"]

    try:
        if schema:
            ok, coerced, details = validate_and_coerce_args(schema, args)
            if not ok:
                obs = {"ok": False, "error": "Invalid delivery args", "validation": details}
            else:
                args = coerced
                # FIXED: Handle both 2-tuple and 3-tuple
                executor_result = executors[fkey]()
                if len(executor_result) == 3:
                    node_cls, node_model, mcp_tool_name = executor_result
                    args = {
                        **args,
                        "operation": "executeTool",
                        "toolName": mcp_tool_name,
                        "toolArguments": json.dumps(args) if args else "{}"
                    }
                    node_params = getattr(node_model, "parameters", None) or {}
                    for key in ["transport", "command", "args", "env", "url", "headers", "options"]:
                        if key not in args and key in node_params:
                            args[key] = node_params[key]
                else:
                    node_cls, node_model = executor_result
                
                obs = execute_tool_util(owner, node_cls, node_model, args, expr_json={"message": final_text})
                if details:
                    obs["_arg_validation"] = "coerced"
        else:
            # FIXED: Handle both 2-tuple and 3-tuple
            executor_result = executors[fkey]()
            if len(executor_result) == 3:
                node_cls, node_model, mcp_tool_name = executor_result
                args = {
                    **args,
                    "operation": "executeTool",
                    "toolName": mcp_tool_name,
                    "toolArguments": json.dumps(args) if args else "{}"
                }
                node_params = getattr(node_model, "parameters", None) or {}
                for key in ["transport", "command", "args", "env", "url", "headers", "options"]:
                    if key not in args and key in node_params:
                        args[key] = node_params[key]
            else:
                node_cls, node_model = executor_result
            
            obs = execute_tool_util(owner, node_cls, node_model, args, expr_json={"message": final_text})
    except Exception as e:
        logger.error(f"[Tool Ops] Error in delivery: {e}")
        import traceback
        logger.error(traceback.format_exc())
        obs = {"error": str(e)}

    intermediate.append({"action": {"tool": fkey, "tool_input": args, "phase": "post_delivery"}, "observation": obs})
    messages.append({"role": "tool", "name": fname, "content": json.dumps(obs, default=str), "tool_call_id": f"post_{uuid.uuid4().hex[:8]}"})
    return {"delivered_by": fname, "ok": "error" not in obs}