from __future__ import annotations
from typing import Any, Dict, List, Optional
import importlib
import inspect

from nodes.base import BaseNode

def coerce_node_definitions_mapping(raw: Any) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if isinstance(v, dict) and isinstance(v.get("node_class"), type):
            out[k] = {"node_class": v["node_class"]}
        elif isinstance(v, type):
            out[k] = {"node_class": v}
    return out

def dyn_import_node_class_from_type(node_type: str) -> Optional[type]:
    try:
        mod = importlib.import_module(f"nodes.{node_type}")
    except Exception:
        return None

    camel = "".join(part.capitalize() for part in str(node_type).split("_"))
    candidates = [f"{camel}Node"]
    for name in candidates:
        cls = getattr(mod, name, None)
        if isinstance(cls, type):
            return cls

    for _, obj in inspect.getmembers(mod, inspect.isclass):
        try:
            if issubclass(obj, BaseNode) and getattr(obj, "type", None) == node_type:
                return obj
        except Exception:
            continue
    return None

def resolve_node_definitions(preferred: Dict[str, Any] | None, workflow: Any, tool_nodes: List[Any]) -> Dict[str, Dict[str, Any]]:
    # 1) explicit
    nd = coerce_node_definitions_mapping(preferred) if preferred else {}
    if nd:
        return nd

    # 2) workflow-provided registry
    wf_defs = getattr(workflow, "node_definitions", None)
    nd = coerce_node_definitions_mapping(wf_defs) if wf_defs else {}

    # 3) dynamic imports for any missing types among tool_nodes
    need_types = {getattr(n, "type", None) for n in (tool_nodes or [])} - set(nd.keys())
    for t in sorted([x for x in need_types if x]):
        cls = dyn_import_node_class_from_type(t)
        if cls:
            nd[t] = {"node_class": cls}
    return nd