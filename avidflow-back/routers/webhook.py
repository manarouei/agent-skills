from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime, timezone
from database.crud import WorkflowCRUD, WebhookCRUD, ExecutionCRUD
from datetime import datetime, timezone
from typing import Dict, Any
from models import WorkflowModel

router = APIRouter()


async def get_db_from_app(request: Request):
    """Get database session from app state - fixed to yield properly"""
    async with request.app.state.session_factory() as session:
        yield session


@router.api_route("/webhook/{webhook_id}/{node_type}", methods=["GET", "POST"])
async def webhook_listener(
    webhook_id: str,
    node_type: str,
    request: Request,
    db: AsyncSession = Depends(get_db_from_app),
):
    webhook = await WebhookCRUD.get_webhook_by_id(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    workflow = await WorkflowCRUD.get_workflow(db, webhook.workflow_id)

    if not workflow or not workflow.active:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    workflow_data = WorkflowModel.model_validate(workflow)

    node = next((n for n in workflow_data.nodes if n.type == node_type), None)
    if not node or not node.is_webhook:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    http_method = node.parameters.model_dump(mode="json").get("httpMethod")
    if (not http_method or http_method != request.method.upper()) and node.type != "chat":
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    payload = {}
    if request.method.upper() == "POST":
        try:
            payload = await request.json()
        except Exception:
            body_bytes = await request.body()
            payload = (
                {"raw": body_bytes.decode(errors="ignore")} if body_bytes else None
            )

    webhook_data = {
        "body": payload,
        "headers": dict(request.headers),
        "query": dict(request.query_params),
        "method": request.method,
        "url": str(request.url),
        "webhookData": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    execution_id = str(uuid.uuid4())

    task_arguments = {
        "workflow_data": workflow_data.model_dump(),
        "user_id": workflow.user_id,
        "primary_result": payload if node.type == "chat" else webhook_data,
        "execution_id": execution_id,
        "pub_sub": False,
    }

    await ExecutionCRUD.create_execution(
        db=db,
        workflow_id=workflow.id,
        execution_id=execution_id,
        mode="trigger",
        status="pending",
        workflow_data=workflow_data.model_dump(mode='json'),
        data={},
    )

    # Use the SAME Celery task as other workflow executions
    from tasks.workflow import execute_workflow

    if node.type == "chat":
        task_result = execute_workflow.apply_async(
            kwargs=task_arguments, task_id=execution_id
        ).get()
        return (
            "خطا در پردازش درخواست چت"
            if task_result.get("error") or task_result.get("status", None) == "error"
            else task_result.get("result").get("final_result")[0][0]['json_data']
        )

    task_result = execute_workflow.apply_async(
        kwargs=task_arguments, task_id=execution_id
    )

    return {
        "status": "started",
        "executionId": execution_id,
        "taskId": task_result.id,
        "message": "پردازش جریان کار آغاز شد",
    }


@router.api_route(
    "/webhook/test/execute/{node_type}/{webhook_token}", methods=["GET", "POST"]
)
async def execute_webhook_test(
    node_type: str,
    webhook_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db_from_app),
):
    """
    Test webhook endpoint:
    - Receives GET/POST.
    - Packages headers/query/body into a unified payload.
    - Delivers payload to the waiting WebSocket via message handler.
    """
    test_state = await request.app.state.redis.get_test_webhook_state(webhook_token)
    if not test_state:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    webhook = await WebhookCRUD.get_webhook_by_id(db, webhook_token)
    if not webhook:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    workflow = await WorkflowCRUD.get_workflow(db, webhook.workflow_id)

    if not workflow:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    workflow_data = WorkflowModel.model_validate(workflow)

    node = next((n for n in workflow_data.nodes if n.type == node_type), None)
    if not node or not node.is_webhook:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    http_method = node.parameters.model_dump(mode="json").get("httpMethod")
    if not http_method or http_method != request.method.upper():
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    body = None
    if request.method.upper() == "POST":
        try:
            body = await request.json()
        except Exception:
            body_bytes = await request.body()
            body = {"raw": body_bytes.decode(errors="ignore")} if body_bytes else None

    payload: Dict[str, Any] = {
        "body": body,
        "headers": dict(request.headers),
        "query": dict(request.query_params),
        "method": request.method,
        "url": str(request.url),
        "webhookData": body if body is not None else dict(request.query_params),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await request.app.state.redis.delete_test_webhook_state(webhook_token)

    await request.app.state.message_handler.receive_test_webhook_payload(
        webhook_token, payload
    )

    return {"status": "accepted", "token": webhook_token, "nodeType": node_type}
