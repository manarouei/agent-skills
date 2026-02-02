from __future__ import annotations
from typing import Any, Dict, List

def classify_tools(tools: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Heuristically classify tools by schema (no hardcoding)."""
    delivery, retrieval, other = [], [], []
    for t in tools or []:
        fn = (t or {}).get("function", {}) or {}
        name = str(fn.get("name", "")).strip()
        params = fn.get("parameters") or {}
        props = (params.get("properties") or {})
        pnames = {p.lower() for p in props.keys()}
        if "text" in pnames:
            delivery.append(name)
        elif any(k in pnames for k in {"query","search","q","documentid","sheetid","table","collection","index","dataset"}):
            retrieval.append(name)
        else:
            other.append(name)
    return {"delivery": delivery, "retrieval": retrieval, "other": other}


def tool_instruction(tools: List[Dict[str, Any]]) -> str | None:
    """
    Build a concise, model-driven instruction that mirrors n8n:
    - List available tools and their required arguments (only those without usable defaults)
    - Keep guidance generic (no workflow-specific logic)
    """
    try:
        if not tools:
            return None

        def summarize_tool(t):
            fn = (t or {}).get("function", {}) or {}
            name = str(fn.get("name", "")).strip()
            params = fn.get("parameters") or {}
            props = (params.get("properties") or {})
            required = list(params.get("required") or [])
            req = [r for r in required if props.get(r, {}).get("default") in (None, "")]
            if req:
                return f"- {name}: required -> {', '.join(req)}"
            sample = [p for p in list(props.keys())[:4]]
            return f"- {name}" + (f": args -> {', '.join(sample)}" if sample else "")

        lines = []
        lines.append("You can call tools to perform actions. When helpful, call a tool by name with a valid JSON arguments object.")
        lines.append("Available tools:")
        for t in tools:
            lines.append(summarize_tool(t))
        try:
            classes = classify_tools(tools)
            if classes.get("retrieval"):
                lines.append("If the user asks for factual/stored info, first call a retrieval/search tool, then decide next steps.")
            if classes.get("delivery"):
                lines.append("Do not put the final answer in assistant content. After deciding the final answer, call one delivery tool to send it, passing the message in the 'text' argument.")
        except Exception:
            pass
        lines.append("Think briefly whether a tool is needed. If needed, call exactly one tool and wait for its result before deciding next steps.")
        return "\n".join(lines)
    except Exception:
        return "Use tools when they help you perform the user’s requested action."