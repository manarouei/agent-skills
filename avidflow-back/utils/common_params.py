from __future__ import annotations
from typing import Any, Dict

def normalize_parameters(params: Any) -> Dict[str, Any]:
    if params is None:
        return {}
    if hasattr(params, "model_dump"):
        try:
            return params.model_dump()
        except Exception:
            return {}
    if isinstance(params, str):
        import json as _json
        try:
            return _json.loads(params)
        except Exception:
            return {}
    if isinstance(params, dict):
        return params
    return {}