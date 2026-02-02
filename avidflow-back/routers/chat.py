from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database.crud import WorkflowCRUD, WebhookCRUD
from models import WorkflowModel

router = APIRouter()


async def get_db_from_app(request: Request):
    """Get database session from app state - fixed to yield properly"""
    async with request.app.state.session_factory() as session:
        yield session


@router.get("/chat-info/{webhook_token}")
async def get_chat_information(
    webhook_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db_from_app),
):
    """
    Get chat configuration for a given webhook token.
    """
    # Validate webhook exists
    webhook = await WebhookCRUD.get_webhook_by_id(db, webhook_token)
    if not webhook:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    # Get workflow
    workflow = await WorkflowCRUD.get_workflow(db, webhook.workflow_id)
    if not workflow or not workflow.active:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    workflow_data = WorkflowModel.model_validate(workflow)

    # Find the chat_trigger node - IMPROVED SEARCH LOGIC
    chat_node = None
    for node in workflow_data.nodes:
        # Debug logging
        print(f"Checking node: type={node.type}, is_webhook={node.is_webhook}, webhook_id={node.webhook_id}")

        if (node.type == "chat" and
            node.is_webhook and 
            str(node.webhook_id) == str(webhook_token)):  # Ensure string comparison
            chat_node = node
            break

    if not chat_node:
        # Additional debug info
        chat_nodes = [n for n in workflow_data.nodes if n.type == "chat"]
        print(f"Found {len(chat_nodes)} chat_trigger nodes")
        for i, n in enumerate(chat_nodes):
            print(f"  Node {i}: webhook_id={n.webhook_id}, is_webhook={n.is_webhook}")

        raise HTTPException(status_code=404, detail="Chat trigger node not found")

    # Extract and return configuration
    node_params = chat_node.parameters.model_dump(mode="json")

    # Dynamically determine API base address from request
    api_base_address = str(request.base_url).rstrip("/")

    
    return {
        "initial message": node_params.get("initial message"), 
    }
