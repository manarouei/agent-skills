from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database.crud import WorkflowCRUD, WebhookCRUD
from models import WorkflowModel
import json
from typing import Any, Dict, List, Optional

router = APIRouter()


async def get_db_from_app(request: Request):
    """Get database session from app state - fixed to yield properly"""
    async with request.app.state.session_factory() as session:
        yield session


def _safe_to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        s = v.strip().lower()
        return s in ("true", "1", "yes", "on")
    return bool(v)


def _parse_nodes(raw_nodes: Any) -> List[Dict[str, Any]]:
    """
    Accept nodes as:
    - list[dict]
    - JSON string
    - pydantic model with model_dump()
    - dict with 'root'
    Otherwise returns []
    """
    try:
        if isinstance(raw_nodes, list):
            return [n for n in raw_nodes if isinstance(n, dict)]
        if isinstance(raw_nodes, str):
            parsed = json.loads(raw_nodes)
            if isinstance(parsed, list):
                return [n for n in parsed if isinstance(n, dict)]
            if isinstance(parsed, dict) and isinstance(parsed.get("root"), list):
                return [n for n in parsed["root"] if isinstance(n, dict)]
            return []
        if hasattr(raw_nodes, "model_dump"):
            dumped = raw_nodes.model_dump(mode="json")
            if isinstance(dumped, list):
                return [n for n in dumped if isinstance(n, dict)]
            if isinstance(dumped, dict) and isinstance(dumped.get("root"), list):
                return [n for n in dumped["root"] if isinstance(n, dict)]
            return []
        if isinstance(raw_nodes, dict) and isinstance(raw_nodes.get("root"), list):
            return [n for n in raw_nodes["root"] if isinstance(n, dict)]
    except Exception as e:
        print(f"[form-info] Failed to parse nodes: {e}")
    return []


def _get_raw_form_params(workflow: Any, webhook_token: str) -> Optional[Dict[str, Any]]:
    nodes = _parse_nodes(getattr(workflow, "nodes", None))
    # Fallback: try direct attribute in case nodes was already dict list on the object
    if not nodes and isinstance(workflow, dict):
        nodes = _parse_nodes(workflow.get("nodes"))
    for rn in nodes:
        try:
            if (
                rn.get("type") == "form_trigger"
                and rn.get("is_webhook")
                and str(rn.get("webhook_id")) == str(webhook_token)
            ):
                params = rn.get("parameters") or {}
                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except Exception:
                        params = {}
                if hasattr(params, "model_dump"):
                    params = params.model_dump(mode="json")
                if isinstance(params, dict):
                    return params
        except Exception:
            continue
    return None


@router.get("/form-info/{webhook_token}")
async def get_form_information(
    webhook_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db_from_app),
):
    """
    Get form configuration for a given webhook token.
    Useful for dynamically generating forms or inspecting configuration.
    """
    # Validate webhook exists
    webhook = await WebhookCRUD.get_webhook_by_id(db, webhook_token)
    if not webhook:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    # Get workflow
    workflow = await WorkflowCRUD.get_workflow(db, webhook.workflow_id)
    if not workflow or not workflow.active:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    # Build model for traversal but prefer RAW params for accuracy
    workflow_data = WorkflowModel(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        nodes=workflow.nodes,
        connections=workflow.connections,
        settings=workflow.settings,
        pin_data=workflow.pin_data,
        active=workflow.active,
    )

    # Find node reference (for existence)
    form_node = None
    for node in workflow_data.nodes:
        print(f"[form-info] Checking node: type={node.type}, is_webhook={node.is_webhook}, webhook_id={node.webhook_id}")
        if node.type == "form_trigger" and node.is_webhook and str(node.webhook_id) == str(webhook_token):
            form_node = node
            break

    if not form_node:
        form_nodes = [n for n in workflow_data.nodes if n.type == "form_trigger"]
        print(f"[form-info] Found {len(form_nodes)} form_trigger nodes")
        for i, n in enumerate(form_nodes):
            print(f"[form-info]   Node {i}: webhook_id={n.webhook_id}, is_webhook={n.is_webhook}")
        raise HTTPException(status_code=404, detail="Form trigger node not found")

    # Strongly prefer RAW parameters from DB to avoid defaults
    node_params = _get_raw_form_params(workflow, webhook_token)
    if not node_params:
        # Final fallback to pydantic dump (may apply defaults)
        print("[form-info] RAW parameters not found; falling back to model_dump")
        node_params = form_node.parameters.model_dump(mode="json")

    # API base
    api_base_address = str(request.base_url).rstrip("/")

    # Normalize form fields
    form_fields = node_params.get("formFields", []) or []
    processed_form_fields = []
    for field in form_fields:
        if not isinstance(field, dict):
            continue
        field_copy = dict(field)

        # Normalize required explicitly (default False when missing)
        if "required" in field_copy:
            field_copy["required"] = _safe_to_bool(field_copy.get("required"))
        else:
            field_copy["required"] = False

        # Ensure fileFormat for file fields
        if field_copy.get("fieldType") == "file" and "fileFormat" not in field_copy:
            field_copy["fileFormat"] = "*/*"

        processed_form_fields.append(field_copy)

    return {
        "webhookId": webhook_token,
        "workflowId": workflow.id,
        "workflowName": workflow.name,
        "formTitle": node_params.get("formTitle", "Submit Form"),
        "formDescription": node_params.get("formDescription", ""),
        "httpMethod": node_params.get("httpMethod", "POST"),
        "formFields": processed_form_fields,
        #"test_path_url": f"{api_base_address}/webhook/test/execute/form_trigger/{webhook_token}",
        "path_url": f"{api_base_address}/webhook/{webhook_token}/form_trigger",
        "active": workflow.active,
    }
