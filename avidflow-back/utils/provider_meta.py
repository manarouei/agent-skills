from __future__ import annotations
from typing import Any, Dict, List

def build_providers_meta(ai_model: Dict[str, Any], memory: Dict[str, Any] | None, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    tool_names: List[str] = []
    for t in tools or []:
        fn = (t or {}).get("function", {}) or {}
        name = str(fn.get("name", "")).strip()
        if name:
            tool_names.append(name)
    meta: Dict[str, Any] = {"ai_model": ai_model or {}, "tools": tool_names}
    if memory and isinstance(memory, dict) and memory.get("type"):
        meta["ai_memory"] = {
            "type": memory.get("type"),
            "session_id": memory.get("session_id"),
            "context_window_length": memory.get("context_window_length"),
            "ttl_seconds": memory.get("ttl_seconds"),
        }
    return meta