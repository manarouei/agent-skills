from __future__ import annotations
from typing import Any, Dict, List, Optional
import json

from nodes.memory.buffer_memory import MemoryManager

def messages_for_memory(msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for m in msgs or []:
        role = m.get("role")
        if role in ("user", "assistant"):
            cp = dict(m)
            cp.pop("tool_calls", None)
            cleaned.append(cp)
    return cleaned

def build_initial_messages(
    system_message: str,
    tools: List[Dict[str, Any]],
    memory: Optional[Dict[str, Any]],
    user_input: str,
    tool_instruction_builder,
    messages_for_memory_fn=messages_for_memory,
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    if system_message:
        messages.append({"role": "system", "content": system_message})

    tool_instr = tool_instruction_builder(tools)
    if tool_instr:
        messages.append({"role": "system", "content": tool_instr})

    if memory and memory.get("type") == "simple_memory":
        sid = memory.get("session_id")
        if sid:
            loaded = MemoryManager.load(sid, int(memory.get("context_window_length", 5)))
            if loaded:
                messages.extend(messages_for_memory_fn(loaded))

    messages.append({"role": "user", "content": user_input})
    return messages

def assistant_with_tool_calls_message(assistant_msg: Dict[str, Any], tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "role": "assistant",
        "content": assistant_msg.get("content", "") or "",
        "tool_calls": [
            {
                "id": tc.get("id", ""),
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": json.dumps(tc.get("arguments", {}), default=str),
                },
            }
            for tc in (tool_calls or [])
        ],
    }