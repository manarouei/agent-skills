from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from typing import Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
from database.crud import WorkflowCRUD ,ExecutionCRUD
from models.workflow import WorkflowModel
from tasks.workflow import execute_workflow
from services.redis_manager import RedisManager
from auth.dependencies import get_current_user_websocket
import logging


router = APIRouter()
logger = logging.getLogger(__name__)

async def get_db_from_app_websocket(websocket: WebSocket) -> AsyncSession:
    """Get database session from app state for WebSocket connections"""
    async with websocket.app.state.session_factory() as session:
        yield session


@router.websocket("/ws/workflows/execute/{workflow_id}")
async def workflow_execution_websocket(
    websocket: WebSocket,
    workflow_id: str,
    input_data: Optional[str] = Query(None),
    chatInput: Optional[str] = Query(None),
    sessionId: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_websocket),
    db: AsyncSession = Depends(get_db_from_app_websocket)
):
    """
    WebSocket endpoint that automatically starts workflow execution on connection.
    """
    # Accept the connection
    await websocket.accept()
    
    # Get application state from websocket scope
    app = websocket.app
    
    try:
        # Generate unique execution ID for this connection
        execution_id = str(uuid.uuid4())

        workflow_db = await WorkflowCRUD.get_workflow(db, workflow_id)
        if not workflow_db:
            await websocket.send_json({"type": "error", "error": "Workflow not found"})
            await websocket.close()
            return
        workflow_model = WorkflowModel.model_validate(workflow_db)
        workflow_data = workflow_model.model_dump(mode='json')
        # Register websocket for updates
        await app.state.message_handler.register_execution(workflow_id, execution_id, websocket)
        connection_key = f"{workflow_id}:{execution_id}"
        # Notify execution started
        await websocket.send_json({
            "type": "execution_started",
            "executionId": execution_id,
            "workflowId": workflow_id
        })
        # Save execution row
        await ExecutionCRUD.create_execution(
            db=db,
            workflow_id=workflow_id,
            execution_id=execution_id,
            mode="manual",
            status="pending",
            workflow_data=workflow_data,
            data={}
        )

        primary_result = {}
        # Chat mode payload
        if chatInput and sessionId:
            primary_result = {"chatInput": chatInput, "sessionId": sessionId}

        node = next((n for n in workflow_model.nodes if n.is_webhook == True and n.type != 'chat'), None)
        if node:
            test_token = node.webhook_id
            await app.state.message_handler.register_test_webhook_waiter(connection_key, test_token)

            await websocket.send_json({
                "type": "waiting_for_test_webhook",
                "workflowId": workflow_id,
                "webhookToken": test_token,
                "timeoutSeconds": 120
            })

            await app.state.redis.set_test_webhook_state(test_token, {'test_node': node.type})

            # Wait for payload delivery
            payload = await app.state.message_handler.wait_for_test_webhook(test_token, timeout=120.0)
            if not payload:
                await websocket.send_json({
                    "type": "error",
                    "error": "Timed out waiting for test webhook payload"
                })
                await websocket.close()
                return

            primary_result = payload

        # Start the workflow execution (Celery)
        task_arguments = {
            "workflow_data": workflow_data,
            "user_id": current_user.id,
            "primary_result": primary_result,
            "execution_id": execution_id,
            "pub_sub": True
        }
        task_result = execute_workflow.apply_async(
            kwargs=task_arguments,
            task_id=execution_id
        )

        # Wait for completion event
        if connection_key in app.state.message_handler.execution_complete_events:
            await app.state.message_handler.execution_complete_events[connection_key].wait()

        await websocket.close()
        logger.info('WEB SOCKET CLOSED SUCCESSFULY')

    except WebSocketDisconnect:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
            await websocket.close()
            logger.info(f'WEB SOCKET CLOSED WITH EXCEPTION')
        except Exception as e:
            logger.info(f'WEB SOCKET CLOSED WITH EXCEPTION {str(e)}')
            pass
    finally:
        logger.info('WEB SOCKET CLOSED IN FINALLY')
        pass
