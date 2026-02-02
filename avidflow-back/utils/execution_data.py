from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging, time
from models import NodeExecutionData
from utils.connection_resolver import ConnectionResolver

logger = logging.getLogger(__name__)

def get_execution_data_ref(owner: Any) -> Dict[str, Any]:
    """
    Return {"execution_data": <scratch map>, "all_results": <engine node_results or private fallback>}.
    Never write a key named 'all_results' into execution_data to avoid polluting node_results.
    """
    # Scratch holder (node/workflow-level)
    exec_data = getattr(owner, "execution_data", None)
    if exec_data is None and getattr(owner, "workflow", None) is not None:
        exec_data = getattr(owner.workflow, "execution_data", None)
    if exec_data is None:
        exec_data = {}
        try:
            setattr(owner, "execution_data", exec_data)
        except Exception:
            pass

    # Engine all_results when available
    all_results = None
    try:
        execution = getattr(owner, "execution", None)
        ctx = getattr(execution, "context", None) if execution else None
        all_results = getattr(ctx, "node_results", None) if ctx else None
    except Exception:
        all_results = None

    if all_results is None:
        # Private fallback map on the owner; do NOT place inside execution_data
        all_results = getattr(owner, "_all_results_fallback", None)
        if all_results is None:
            all_results = {}
            try:
                setattr(owner, "_all_results_fallback", all_results)
            except Exception:
                # As a last resort, use a local dict (write-only in this run)
                all_results = {}

    return {"execution_data": exec_data, "all_results": all_results}

def persist_provider_snapshot(owner: Any, input_name: str, payload_key: str, payload_value: Dict[str, Any]) -> None:
    """
    Seed a provider snapshot under the upstream node in both execution_data and all_results.
    """
    try:
        upstream = ConnectionResolver.get_upstream_nodes(owner.workflow, owner.node_data.name, input_name) or []
        if not upstream:
            return
        ref = get_execution_data_ref(owner)
        exec_data = ref["execution_data"]
        all_results = ref["all_results"]
        provider_node = upstream[0]
        item = NodeExecutionData(json_data={payload_key: payload_value}, binary_data=None)
        if not exec_data.get(provider_node.name):
            exec_data[provider_node.name] = [[item]]
        if not all_results.get(provider_node.name):
            all_results[provider_node.name] = [[item]]
    except Exception as e:
        logger.debug(f"[exec_data] provider snapshot('{input_name}') failed: {e}")

def seed_provider_items(
    workflow,
    execution_data: Dict[str, Any],
    exec_ref: Dict[str, Any],
    target_node_name: str,
    input_name: str,
    payload_key: str,
    payload: Dict[str, Any],
) -> None:
    upstream = ConnectionResolver.get_upstream_nodes(workflow, target_node_name, input_name) or []
    if not upstream:
        return
    all_results = exec_ref.get("all_results", {})
    for n in upstream:
        has_exec = bool((execution_data or {}).get(n.name))
        has_all = n.name in all_results
        if has_exec and has_all:
            continue
        item = NodeExecutionData(json_data={payload_key: payload}, binary_data=None)
        if not has_exec:
            execution_data[n.name] = [[item]]
        if not has_all:
            all_results[n.name] = [[item]]

def persist_inbound_results_for_input(
    workflow,
    execution_data: Dict[str, Any],
    exec_ref: Dict[str, Any],
    target_node_name: str,
    input_name: str,
) -> None:
    grouped = ConnectionResolver.get_items_grouped(workflow, execution_data, target_node_name, input_name)
    if not grouped:
        return
    all_results = exec_ref.get("all_results", {})
    wrote_any = False
    for node_name, items in grouped.items():
        if node_name == "__merged__":
            continue
        if node_name not in all_results:
            all_results[node_name] = [list(items)]
            wrote_any = True
    if not wrote_any and "__merged__" in grouped:
        upstream = ConnectionResolver.get_upstream_nodes(workflow, target_node_name, input_name) or []
        if len(upstream) == 1:
            node_name = upstream[0].name
            if node_name not in all_results:
                all_results[node_name] = [list(grouped["__merged__"])]

def _append_item_under_node_maps(
    execution_data: Dict[str, Any],
    all_results: Dict[str, Any],
    node_name: str,
    item: NodeExecutionData,
) -> None:
    # execution_data
    ch = execution_data.setdefault(node_name, [])
    if not ch or not isinstance(ch[0], list):
        execution_data[node_name] = [[]]
        ch = execution_data[node_name]
    ch[0].append(item)
    # all_results
    ar = all_results.setdefault(node_name, [])
    if not ar or not isinstance(ar[0], list):
        all_results[node_name] = [[]]
        ar = all_results[node_name]
    ar[0].append(item)

def persist_model_run_result(
    workflow,
    execution_data: Dict[str, Any],
    exec_ref: Dict[str, Any],
    target_node_name: str,
    model_input_name: str,
    run_payload: Dict[str, Any],
) -> None:
    upstream = ConnectionResolver.get_upstream_nodes(workflow, target_node_name, model_input_name) or []
    if not upstream:
        return
    all_results = exec_ref.get("all_results", {})
    item = NodeExecutionData(json_data={"ai_model_run": run_payload}, binary_data=None)
    for n in upstream:
        _append_item_under_node_maps(execution_data, all_results, n.name, item)

def persist_memory_save_result(
    workflow,
    execution_data: Dict[str, Any],
    exec_ref: Dict[str, Any],
    target_node_name: str,
    memory_input_name: str,
    save_payload: Dict[str, Any],
) -> None:
    upstream = ConnectionResolver.get_upstream_nodes(workflow, target_node_name, memory_input_name) or []
    if not upstream:
        return
    all_results = exec_ref.get("all_results", {})
    item = NodeExecutionData(json_data={"ai_memory_save": save_payload}, binary_data=None)
    for n in upstream:
        _append_item_under_node_maps(execution_data, all_results, n.name, item)