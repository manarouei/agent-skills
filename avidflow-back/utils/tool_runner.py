from __future__ import annotations
from typing import Any, Dict, Optional, List
from copy import deepcopy
import json as _json
import logging
import re

from models import NodeExecutionData
from utils.execution_data import get_execution_data_ref
from utils.common_params import normalize_parameters

logger = logging.getLogger(__name__)

def execute_tool(owner: Any, node_cls: Any, node_model: Any, args: Dict[str, Any], expr_json: Optional[Dict[str, Any]] = None):
    """
    Execute an upstream tool node with merged parameters.
    - expr_json is injected as the tool node's $json (current item) context, so expressions like {{$json.message}} work.
    - owner is the calling node instance (used to discover workflow/execution_data).
    """
    model_copy = deepcopy(node_model)
    node_params = normalize_parameters(getattr(model_copy, "parameters", None)) or {}
    
    # CRITICAL FIX: Pre-configured values should OVERRIDE LLM values
    # First apply LLM args, then override with configured node params
    merged = {**(args or {}), **node_params}

    existing = getattr(model_copy, "parameters", None)
    if existing is not None and hasattr(existing, "model_dump"):
        try:
            model_copy.parameters = existing.__class__(**merged)
        except Exception:
            model_copy.parameters = merged
    else:
        model_copy.parameters = merged

    logger.info(
        "[AI Agent] Executing tool node '%s__%s' with effective_args: %s",
        getattr(node_model, "name", "<unnamed>"),
        getattr(node_model, "id", "<no-id>"),
        _json.dumps(merged, default=str),
    )

    # Get composite reference: {"execution_data": ..., "all_results": ...}
    exec_ref = get_execution_data_ref(owner)

    # Instantiate tool node; pass the same exec_ref object used by the agent
    # Build $json context for template evaluation
    # Strategy: For parameters with template expressions like {{$json.message}},
    # extract the variable name and populate $json with the LLM's generated value
    current_item_json = {**(expr_json or {})}
    
    # For each configured parameter that contains a template expression,
    # extract the template variable and populate $json with the LLM's generated value
    for param_name, param_value in node_params.items():
        if isinstance(param_value, str) and "{{$json." in param_value:
            # Extract variable name from template like "{{$json.message}}" -> "message"
            match = re.search(r'\{\{\$json\.(\w+)\}\}', param_value)
            if match:
                var_name = match.group(1)
                # Get the LLM's generated value for this parameter
                llm_value = (args or {}).get(param_name)
                if llm_value is not None and llm_value != param_value:
                    # Populate $json with the LLM's value under the template variable name
                    current_item_json[var_name] = llm_value
                    logger.info(
                        "[Tool Runner] Template found: %s=%s -> Setting $json.%s=%s",
                        param_name, param_value, var_name, llm_value
                    )
    
    inst = node_cls(model_copy, owner.workflow, exec_ref)
    inst.input_data = {"main": [[NodeExecutionData(json_data=current_item_json, binary_data=None)]]}

    out = inst.execute() or [[]]
    produced = out[0] if out and len(out) > 0 else []
    if produced is None:
        produced = []

    try:
        execution_data = exec_ref.get("execution_data", {})
        all_results = exec_ref.get("all_results", {})

        # Persist into execution_data (channel 0)
        execution_data.setdefault(node_model.name, [])
        execution_data[node_model.name] = [produced]

        # Persist into all_results (append into channel 0, preserving list-of-lists)
        ar = all_results.setdefault(node_model.name, [])
        if not ar or not (isinstance(ar, list) and ar and isinstance(ar[0], list)):
            all_results[node_model.name] = [[]]
            ar = all_results[node_model.name]
        if len(ar) == 0:
            ar.append([])
        ar[0].extend(produced)

        logger.info("[AI Agent] Persisted tool node results under '%s' -> %d item(s)", node_model.name, len(produced))
    except Exception as e:
        logger.warning("[AI Agent] Failed to persist tool node results: %s", e)

    if not produced:
        return {"ok": False, "error": "Tool returned no output"}

    rows: List[Dict[str, Any]] = []
    for it in produced:
        try:
            rows.append((getattr(it, "json_data", {}) or {}))
        except Exception:
            rows.append({})
    
    # LOG: Number of rows returned
    logger.info(f"[Tool Runner] Tool returned {len(rows)} row(s)")
    
    # Return all rows as items (for filtering by process_tool_response)
    if len(rows) > 1:
        logger.info(f"[Tool Runner] Multiple rows - returning as items list")
        result = {"items": rows, "count": len(rows)}
    elif len(rows) == 1:
        # Single row - check if it should be treated as a list result
        # (Google Sheets with returnAllData but only 1 row should still be {"items": [...]})
        single_row = rows[0]
        
        # If the tool is explicitly a data source (Google Sheets, Database, etc.),
        # always return as items even if only 1 row
        is_data_source = node_model.type in ["googleSheets", "postgres", "mysql", "mongodb"]
        
        if is_data_source:
            logger.info(f"[Tool Runner] Single row from data source - returning as items list")
            result = {"items": rows, "count": 1}
        else:
            logger.info(f"[Tool Runner] Single row from non-data-source - returning directly")
            result = single_row
    else:
        result = {"items": [], "count": 0}
    
    # Check if this is an MCP tool execution
    is_mcp = node_model.type == "mcpClientTool"
    
    if is_mcp and hasattr(owner, 'mcp_handler'):
        # Extract MCP tool name and prepare args
        mcp_tool_name, mcp_args = owner.mcp_handler.prepare_tool_call_for_mcp(
            tool_name=args.get("toolName", ""),
            agent_args=args
        )
        
        logger.info(f"[Tool Runner] Executing MCP tool: {mcp_tool_name}")
        
        # Update args with prepared MCP format
        args["toolName"] = mcp_tool_name
        args["toolArguments"] = mcp_args

    try:
        # Normal tool response
        if is_mcp and hasattr(owner, 'mcp_handler'):
            tool_name = args.get("toolName", "")
            raw_response = result  # Use the result we prepared above
            
            # Process through MCP handler
            processed = owner.mcp_handler.process_mcp_tool_response(
                tool_name=tool_name,
                tool_args=args,
                raw_response=raw_response,
                item_index=0
            )
            
            return processed
        
        return result  # Return the formatted result
    except Exception as e:
        logger.error(f"[Tool Runner] Error executing tool: {e}")
        return {"error": str(e), "status": "failed"}