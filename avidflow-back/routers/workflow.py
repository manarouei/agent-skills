import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from database import crud
from services.scheduler import SchedulerService
from models import ExecutionSummary
from models.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    CopyWorkflow,
    WorkflowModel,
)
from database.models import User
from auth.dependencies import get_current_user
from fastapi_pagination import Page, Params

router = APIRouter()


async def get_db_from_app(request: Request) -> AsyncSession:
    """Get database session from app state"""
    # Create a new session using the factory
    async with request.app.state.session_factory() as session:
        yield session


@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow: WorkflowCreate,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Create a new workflow for the current user"""
    workflow = await crud.WorkflowCRUD.create_workflow(db, workflow, current_user.id)
    workflow_model = WorkflowModel.model_validate(workflow)
    await SchedulerService.schedule_workflow(db, workflow_model, "update")

    return workflow


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Get a specific workflow by ID"""
    workflow = await crud.WorkflowCRUD.get_workflow(db, workflow_id)
    if (
        not workflow or workflow.user_id != current_user.id
    ):  # Fixed: owner_id -> user_id
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.get("/", response_model=Page[WorkflowResponse])
async def list_workflows(
    params: Params = Depends(),
    active_only: bool = False,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """List all workflows for the current user with pagination"""
    return await crud.WorkflowCRUD.get_all_workflows(
        db, params=params, user_id=current_user.id, active_only=active_only
    )


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    workflow_update: WorkflowUpdate,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Update an existing workflow"""
    # First check if the workflow exists and belongs to the user
    workflow = await crud.WorkflowCRUD.get_workflow(db, workflow_id)
    if (
        not workflow or workflow.user_id != current_user.id
    ):  # Fixed: owner_id -> user_id
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Update the workflow
    workflow = await crud.WorkflowCRUD.update_workflow(
        db, workflow_id, workflow_update.model_dump(mode="json", exclude_unset=True)
    )

    if workflow:
        workflow_model = WorkflowModel.model_validate(workflow)
        await SchedulerService.schedule_workflow(db, workflow_model, "update")

    return workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Delete a workflow"""
    # First check if the workflow exists and belongs to the user
    workflow = await crud.WorkflowCRUD.get_workflow(db, workflow_id)
    if (
        not workflow or workflow.user_id != current_user.id
    ):  # Fixed: owner_id -> user_id
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Delete the workflow
    result = await crud.WorkflowCRUD.delete_workflow(db, workflow_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to delete workflow")

    workflow_model = WorkflowModel.model_validate(workflow)
    await SchedulerService.schedule_workflow(db, workflow_model, "delete")


@router.post("/{workflow_id}/activate", response_model=WorkflowResponse)
async def activate_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Activate a workflow"""
    # First check if the workflow exists and belongs to the user
    workflow = await crud.WorkflowCRUD.get_workflow(db, workflow_id)
    if (
        not workflow or workflow.user_id != current_user.id
    ):  # Fixed: owner_id -> user_id
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Activate the workflow
    workflow = await crud.WorkflowCRUD.activate_workflow(db, workflow_id)
    if workflow:
        workflow_model = WorkflowModel.model_validate(workflow)
        await SchedulerService.schedule_workflow(db, workflow_model, "activate")

    return workflow


@router.post("/{workflow_id}/deactivate", response_model=WorkflowResponse)
async def deactivate_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a workflow"""
    # First check if the workflow exists and belongs to the user
    workflow = await crud.WorkflowCRUD.get_workflow(db, workflow_id)
    if (
        not workflow or workflow.user_id != current_user.id
    ):  # Fixed: owner_id -> user_id
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Deactivate the workflow
    workflow = await crud.WorkflowCRUD.deactivate_workflow(db, workflow_id)
    if workflow:
        workflow_model = WorkflowModel.model_validate(workflow)
        await SchedulerService.schedule_workflow(db, workflow_model, "deactivate")

    return workflow


@router.post("/{workflow_id}/copy", response_model=WorkflowResponse)
async def copy_workflow(
    workflow_id: str,
    new_name: CopyWorkflow,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Create a copy of an existing workflow"""
    # First check if the workflow exists and belongs to the user
    workflow = await crud.WorkflowCRUD.get_workflow(db, workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Copy the workflow
    workflow = await crud.WorkflowCRUD.copy_workflow(
        db, workflow_id, current_user.id, new_name.new_name
    )
    if workflow:
        workflow_model = WorkflowModel.model_validate(workflow)
        await SchedulerService.schedule_workflow(db, workflow_model, "update")

    return workflow


@router.get("/search/", response_model=Page[WorkflowResponse])
async def search_workflows(
    query: str = Query(None),
    active_only: bool = False,
    params: Params = Depends(),
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Search for workflows by name or description"""
    return await crud.WorkflowCRUD.search_workflows(
        db,
        params=params,
        user_id=current_user.id,
        query=query,
        active_only=active_only,
    )


@router.get("/{workflow_id}/executions", response_model=Page[ExecutionSummary])
async def list_workflow_executions(
    workflow_id: str,
    params: Params = Depends(),
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """
    List executions for a specific workflow
    """
    # First check if the workflow exists and belongs to the user
    workflow = await crud.WorkflowCRUD.get_workflow(db, workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get the executions for this workflow
    executions = await crud.ExecutionCRUD.get_workflow_executions(
        db, workflow_id=workflow_id, params=params
    )

    return executions


@router.post("/{workflow_id}/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute_workflow(
    workflow_id: str,
    input_data: Dict[str, Any] = Body({}),
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Execute a workflow synchronously and return the result"""
    # First check if the workflow exists and belongs to the user
    workflow = await crud.WorkflowCRUD.get_workflow(db, workflow_id)
    if (
        not workflow or workflow.user_id != current_user.id
    ):  # Fixed: owner_id -> user_id
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    workflow_model = WorkflowModel.model_validate(workflow)
    node = next(
        (
            n
            for n in workflow_model.nodes
            if n.is_webhook == True or n.is_schedule == True
        ),
        None,
    )

    if node:
        raise HTTPException(status_code=400, detail="گردش کار قابلیت اجرای دستی ندارد.")

    workflow_data = workflow_model.model_dump(mode='json')
    execution_id = str(uuid.uuid4())
    execution = await crud.ExecutionCRUD.create_execution(
        db=db,
        workflow_id=workflow_id,
        execution_id=execution_id,
        mode="manual",
        status="pending",
        workflow_data=workflow_data,
        data={"input": input_data},
    )

    task_arguments = {
        "workflow_data": workflow_data,
        "user_id": current_user.id,
        "primary_result": input_data,
        "execution_id": execution_id,
        "pub_sub": True,  # Enable WebSocket updates for REST API too
    }
    task_result = execute_workflow.apply_async(
        kwargs=task_arguments, task_id=execution_id
    )

    return {
        "execution_id": execution.id,
        "status": "pending",
    }
