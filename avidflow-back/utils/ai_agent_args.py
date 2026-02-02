from __future__ import annotations
from typing import Any, Dict, List, Tuple

import json

def coerce_primitive(expected_type: str, value: Any) -> Tuple[bool, Any]:
    if expected_type == "string":
        if value is None:
            return True, ""
        return True, str(value)
    if expected_type in ("number", "integer"):
        if isinstance(value, (int, float)):
            return True, int(value) if expected_type == "integer" else float(value)
        if isinstance(value, str):
            v = value.strip()
            try:
                if expected_type == "integer":
                    return True, int(float(v))
                return True, float(v)
            except Exception:
                return False, value
        return False, value
    if expected_type == "boolean":
        if isinstance(value, bool):
            return True, value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1", "yes", "y", "on"):
                return True, True
            if v in ("false", "0", "no", "n", "off"):
                return True, False
        return False, value
    if expected_type == "array":
        if isinstance(value, list):
            return True, value
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return True, parts
        return False, value
    if expected_type == "object":
        if isinstance(value, dict):
            return True, value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return True, parsed
            except Exception:
                return False, value
        return False, value
    return True, value


def validate_and_coerce_args(param_schema: Dict[str, Any], args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Dict[str, Any]]:
    if not param_schema:
        return True, args or {}, {}
    props = (param_schema.get("properties") or {})
    required = list(param_schema.get("required") or [])
    incoming = args or {}
    coerced: Dict[str, Any] = {}
    details: Dict[str, Any] = {}
    missing: List[str] = []
    type_errors: Dict[str, Any] = {}

    ci_prop_map = {p.lower(): p for p in props.keys()}

    for r in required:
        schema_key = ci_prop_map.get(r.lower(), r)
        if any(k.lower() == r.lower() for k in incoming.keys()):
            continue
        prop_def = props.get(schema_key, {})
        if "default" in prop_def:
            continue
        missing.append(schema_key)

    for key, raw_val in incoming.items():
        prop_key = ci_prop_map.get(key.lower(), key)
        schema_def = props.get(prop_key, {})
        expected_type = schema_def.get("type")
        if expected_type:
            ok, coerced_val = coerce_primitive(expected_type, raw_val)
            if not ok:
                type_errors[prop_key] = {"expected": expected_type, "value": raw_val}
                coerced[prop_key] = raw_val
            else:
                coerced[prop_key] = coerced_val
        else:
            coerced[prop_key] = raw_val

    if missing:
        details["missing"] = missing
    if type_errors:
        details["typeErrors"] = type_errors
    if details:
        return False, coerced, details
    return True, coerced, {}

def _is_blank(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        return val.strip() == ""
    if isinstance(val, (list, dict)):
        return len(val) == 0
    return False

def _coerce_scalar(v: Any) -> Any:
    if isinstance(v, str):
        low = v.strip().lower()
        if low == "true":
            return True
        if low == "false":
            return False
        return v.strip()
    return v

def _clean_any(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in value.items():
            cv = _clean_any(v)
            if not _is_blank(cv):
                cleaned[k] = cv
        return cleaned
    if isinstance(value, list):
        out: List[Any] = []
        for it in value:
            cit = _clean_any(it)
            if not _is_blank(cit):
                out.append(cit)
        return out
    return _coerce_scalar(value)

def clean_tool_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove empty/null/blank values and coerce string booleans.
    Non-destructive: returns a new dict.
    """
    if not isinstance(args, dict):
        return {}
    return _clean_any(dict(args))