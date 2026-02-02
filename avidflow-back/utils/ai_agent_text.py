from __future__ import annotations
from typing import Any, Dict, List, Tuple

def smart_truncate(text: str, max_length: int) -> str:
    if not isinstance(text, str) or len(text) <= max_length:
        return text if isinstance(text, str) else str(text)
    keep = max_length // 2
    return f"{text[:keep]}\n[...{len(text) - max_length} chars omitted...]\n{text[-keep:]}"


def stringify_item(item: Any, max_len: int = 2000) -> str:
    try:
        if isinstance(item, dict):
            parts: List[str] = []
            stack = [item]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    for k, v in cur.items():
                        try:
                            parts.append(str(k))
                        except Exception:
                            pass
                        stack.append(v)
                elif isinstance(cur, list):
                    stack.extend(cur)
                elif isinstance(cur, (str, int, float, bool)):
                    parts.append(str(cur))
            text = " ".join(p for p in parts if p)
        else:
            text = str(item)
        if len(text) > max_len:
            return text[:max_len]
        return text
    except Exception:
        return str(item)[:max_len]


def select_relevant_items(items: List[Any], user_query: str, limit: int = 20, max_chars: int = 9000) -> Dict[str, Any]:
    """
    Generic top-K relevance by token overlap to user query.
    Works for rows from Sheets, DB query results, lists of dicts, etc.
    """
    import re
    total = len(items)
    if not items:
        return {"items": [], "total": 0, "note": "no items"}

    q = (user_query or "").strip().lower()
    q_terms = set(re.findall(r"\w+", q)) if q else set()

    scored: List[Tuple[int, int, Any, str]] = []
    for idx, it in enumerate(items):
        text = stringify_item(it, max_len=2000).lower()
        if not q_terms:
            score = 1 if text else 0
        else:
            terms = set(re.findall(r"\w+", text))
            overlap = len(q_terms.intersection(terms))
            if q and q in text:
                overlap += 3
            score = overlap
        scored.append((score, idx, it, text))

    scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)

    selected: List[Any] = []
    char_budget = max_chars
    kept = 0
    for score, _, it, txt in scored:
        if kept >= limit or char_budget <= 0:
            break
        if score == 0 and q_terms:
            continue
        txt_len = len(txt)
        if txt_len > char_budget and kept > 0:
            break
        selected.append(it)
        char_budget -= min(txt_len, char_budget)
        kept += 1

    if not selected:
        for _, _, it, txt in scored[:limit]:
            if char_budget <= 0:
                break
            selected.append(it)
            char_budget -= len(txt)

    note = f"selected {len(selected)} of {total} based on query relevance" if q_terms else f"selected first {len(selected)} of {total}"
    return {"items": selected, "total": total, "note": note}