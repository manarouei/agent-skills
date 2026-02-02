# tool_schema.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _is_active(param: Dict[str, Any], selected: Dict[str, Any]) -> bool:
    """
    n8n-like visibility:
      - If any `displayOptions.hide` condition matches -> inactive
      - All `displayOptions.show` conditions must match for it to be active
    """
    disp = param.get("displayOptions") or {}
    show = disp.get("show") or {}
    hide = disp.get("hide") or {}

    # Hide branch
    if isinstance(hide, dict):
        for key, vals in hide.items():
            cur = selected.get(key)
            if isinstance(vals, list):
                if cur in vals:
                    return False
            else:
                if cur == vals:
                    return False

    # Show branch: all must match (if present)
    if isinstance(show, dict):
        for key, vals in show.items():
            cur = selected.get(key)
            if isinstance(vals, list):
                if cur not in vals:
                    return False
            else:
                if cur != vals:
                    return False

    return True


def _json_type(p_type: Any) -> str:
    """Map node param types to JSON Schema types (best-effort)."""
    t = (str(p_type) if p_type is not None else "").lower()
    if t in {"string", "str", "text", "options"}:
        return "string"
    if t in {"number", "float", "double"}:
        return "number"
    if t in {"integer", "int"}:
        return "integer"
    if t in {"boolean", "bool"}:
        return "boolean"
    if t in {"array", "list"}:
        return "array"
    if t in {"object", "json"}:
        return "object"
    return "string"


def _selected_params_dict(selected_params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize node instance parameters to a plain dict."""
    if not selected_params:
        return {}
    if hasattr(selected_params, "model_dump"):
        try:
            return selected_params.model_dump()
        except Exception:
            pass
    if isinstance(selected_params, dict):
        return dict(selected_params)
    try:
        return dict(selected_params)  # type: ignore[arg-type]
    except Exception:
        return {}


def node_to_openai_function(
    node_cls: Any,
    selected_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a generic OpenAI tool/function schema from an n8n-style node class.

    Rules (tight & generic):
    - Include a parameter IFF:
        * it is active per displayOptions, AND
        * (it is explicitly set on the node instance) OR (it is 'resource'/'operation').
      (We intentionally DO NOT include class-required fields if they are not explicitly set.
       This avoids "wide" schemas when node definitions don't gate them with displayOptions.)
    - Required list contains only fields that are class-required AND explicitly present
      on the instance AND not already provided (None/empty-string counts as not provided).
    - Instance values appear as `default`; for 'resource'/'operation' they also get `const`.
    """
    # Description (best-effort)
    try:
        description = (
            node_cls.description.get("description")
            or node_cls.description.get("displayName")
            or ""
        )
    except Exception:
        description = ""

    # Parameter definitions from the node class
    try:
        params: List[Dict[str, Any]] = node_cls.properties.get("parameters", [])  # type: ignore[attr-defined]
    except Exception:
        params = []

    # Explicit values configured on THIS node instance
    explicit_selected = _selected_params_dict(selected_params)

    # For visibility checks, allow defaults so show/hide still works
    selected_for_visibility = dict(explicit_selected)
    for p in params:
        n = p.get("name")
        if n and n not in selected_for_visibility and "default" in p:
            selected_for_visibility[n] = p.get("default")


    properties: Dict[str, Any] = {}
    required: List[str] = []

    for p in params:
        name = p.get("name")
        if not name or name in {"nodeType"}:
            continue

        # Respect displayOptions
        if not _is_active(p, selected_for_visibility):
            continue

        # ---- Tight inclusion rule (n8n-feel, node-agnostic) ----
        include = False
        if name in ("resource", "operation"):
            include = True
        elif name in explicit_selected:  # explicitly configured in workflow JSON
            include = True
        else:
            include = False  # don't include class-required fields unless explicitly set

        if not include:
            continue

        jtype = _json_type(p.get("type"))
        prop_schema: Dict[str, Any] = {"type": jtype}

        if "description" in p:
            prop_schema["description"] = p["description"]

        # Base default from class
        if "default" in p:
            prop_schema["default"] = p["default"]

        # Enum options -> enum
        opts = p.get("options")
        if isinstance(opts, list):
            enum_vals = [opt.get("value") for opt in opts if isinstance(opt, dict) and "value" in opt]
            if enum_vals:
                prop_schema["enum"] = enum_vals

        # Overlay instance value
        if name in explicit_selected:
            inst_val = explicit_selected[name]
            if inst_val not in (None, ""):
                # CRITICAL FIX: Intelligently hide/show parameters based on their nature
                # OpenAI doesn't respect 'const', so we remove truly fixed params
                
                # Always show resource/operation (LLM needs to see what operation it's calling)
                if name in ("resource", "operation"):
                    prop_schema["default"] = inst_val
                    prop_schema["const"] = inst_val
                # Keep template/expression parameters visible (e.g., {{$json.message}})
                # LLM needs to know these exist even if they have placeholder values
                elif isinstance(inst_val, str) and ("{{" in inst_val or "$json" in inst_val or "$input" in inst_val):
                    prop_schema["description"] = (prop_schema.get("description", "") + 
                                                f" [Template: {inst_val}]").strip()
                # Hide truly fixed scalar values (documentId, sheetName, chatId, etc.)
                # These are pre-configured and LLM shouldn't override them
                else:
                    # Skip this parameter - it's a fixed value
                    continue

        properties[name] = prop_schema

        # Required only when:
        #  - class marks it required
        #  - and the node explicitly has the field
        #  - and the explicit value is missing/empty (so model must supply)
        if p.get("required") and (name in explicit_selected):
            provided = explicit_selected.get(name, None)
            if provided in (None, ""):
                required.append(name)

    # Safety: intersect required with present keys
    present = set(properties.keys())
    required = [r for r in required if r in present]

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
    }


    return {
        "description": description,
        "parameters": parameters,
    }


def fallback_schema_from_node(
    node_cls: Any,
    selected_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Permissive fallback with the same tight inclusion principles.
    """
    try:
        desc = (
            node_cls.description.get("description")
            or node_cls.description.get("displayName")
            or ""
        )
    except Exception:
        desc = ""

    try:
        params: List[Dict[str, Any]] = node_cls.properties.get("parameters", [])  # type: ignore[attr-defined]
    except Exception:
        params = []

    explicit_selected = _selected_params_dict(selected_params)

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for p in params:
        name = p.get("name")
        if not name or name in {"nodeType"}:
            continue

        # Inclusion rule identical to main path
        include = False
        if name in ("resource", "operation"):
            include = True
        elif name in explicit_selected:
            include = True
        else:
            include = False
        if not include:
            continue

        jtype = _json_type(p.get("type"))
        schema: Dict[str, Any] = {"type": jtype}

        if "description" in p:
            schema["description"] = p["description"]
        if "default" in p:
            schema["default"] = p["default"]

        opts = p.get("options")
        if isinstance(opts, list):
            enum_vals = [opt.get("value") for opt in opts if isinstance(opt, dict) and "value" in opt]
            if enum_vals:
                schema["enum"] = enum_vals

        # Overlay explicit value
        if name in explicit_selected and explicit_selected[name] not in (None, ""):
            schema["default"] = explicit_selected[name]
        if name in ("resource", "operation"):
            inst_val = explicit_selected.get(name)
            if inst_val not in (None, ""):
                schema["const"] = inst_val

        properties[name] = schema

        if p.get("required") and (name in explicit_selected):
            provided = explicit_selected.get(name, None)
            if provided in (None, ""):
                required.append(name)

    present = set(properties.keys())
    required = [r for r in required if r in present]

    return {
        "description": desc,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }


def build_tool_schema(
    node_cls: Any,
    selected_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Public entry for building tool schemas.
    
    Priority:
    1. Check if node class has a custom get_custom_tool_schema() classmethod
    2. Fall back to generic schema generation from parameters
    """
    # Check if node class provides a custom tool schema
    if hasattr(node_cls, 'get_custom_tool_schema') and callable(getattr(node_cls, 'get_custom_tool_schema', None)):
        try:
            params_dict = _selected_params_dict(selected_params)
            custom_schema = node_cls.get_custom_tool_schema(params_dict)
            if custom_schema and isinstance(custom_schema, dict):
                return custom_schema
        except Exception as e:
            logger.warning(f"[TOOL SCHEMA] Custom schema failed, falling back to generic: {e}")
    
    try:
        return node_to_openai_function(node_cls, selected_params=selected_params)
    except Exception as e:
        logger.warning(f"[TOOL SCHEMA] Falling back due to error: {e}")
        return fallback_schema_from_node(node_cls, selected_params=selected_params)
