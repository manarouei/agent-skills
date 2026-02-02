from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from sqlalchemy.future import select
from sqlalchemy import desc, func, and_
from database.models import User, Workflow, Execution
from auth.dependencies import get_current_user

router = APIRouter()

async def get_db_from_app(request: Request) -> AsyncSession:
    """Get database session from app state"""
    async with request.app.state.session_factory() as session:
        yield session

@router.get("/", response_model=Dict[str, Any])
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """
    Get all dashboard data in a single request:
    - Statistics (total workflows, active workflows, execution stats)
    - Recent workflows (5 most recent)
    - Recent executions (5 most recent)
    """
    # Get workflow statistics using SQL COUNT
    total_workflows_query = select(func.count()).select_from(Workflow).where(
        Workflow.user_id == current_user.id
    )
    active_workflows_query = select(func.count()).select_from(Workflow).where(
        and_(Workflow.user_id == current_user.id, Workflow.active == True)
    )
    
    # Get all workflow IDs for this user to use in execution queries
    workflow_ids_query = select(Workflow.id).where(Workflow.user_id == current_user.id)
    workflow_ids_result = await db.execute(workflow_ids_query)
    workflow_ids = [row[0] for row in workflow_ids_result]
    
    # Execution statistics with SQL COUNT
    successful_executions_query = select(func.count()).select_from(Execution).where(
        and_(Execution.workflow_id.in_(workflow_ids), Execution.status == 'success')
    ) if workflow_ids else select(func.count().label('count')).select_from(Execution).where(
        Execution.id == None  # No workflows, so no executions
    )
    
    failed_executions_query = select(func.count()).select_from(Execution).where(
        and_(Execution.workflow_id.in_(workflow_ids), Execution.status == 'error')
    ) if workflow_ids else select(func.count().label('count')).select_from(Execution).where(
        Execution.id == None  # No workflows, so no executions
    )
    
    pending_executions_query = select(func.count()).select_from(Execution).where(
        and_(
            Execution.workflow_id.in_(workflow_ids), 
            Execution.status.in_(['pending', 'running', 'queued'])
        )
    ) if workflow_ids else select(func.count().label('count')).select_from(Execution).where(
        Execution.id == None  # No workflows, so no executions
    )
    
    # Execute all count queries
    total_workflows_result = await db.execute(total_workflows_query)
    active_workflows_result = await db.execute(active_workflows_query)
    successful_executions_result = await db.execute(successful_executions_query)
    failed_executions_result = await db.execute(failed_executions_query)
    pending_executions_result = await db.execute(pending_executions_query)
    
    # Extract count values
    total_workflows = total_workflows_result.scalar() or 0
    active_workflows = active_workflows_result.scalar() or 0
    successful_executions = successful_executions_result.scalar() or 0
    failed_executions = failed_executions_result.scalar() or 0
    pending_executions = pending_executions_result.scalar() or 0
    
    # Get recent workflows (5 most recent)
    recent_workflows_query = (
        select(Workflow)
        .where(Workflow.user_id == current_user.id)
        .order_by(desc(Workflow.updated_at))
        .limit(5)
    )
    recent_workflows_result = await db.execute(recent_workflows_query)
    recent_workflows = recent_workflows_result.scalars().all()
    
    # Get recent executions with workflow name
    recent_executions_query = (
        select(
            Execution, 
            Workflow.name.label("workflow_name")
        )
        .join(Workflow, Execution.workflow_id == Workflow.id)
        .where(Execution.workflow_id.in_(workflow_ids))
        .order_by(desc(Execution.started_at))
        .limit(5)
    )
    recent_executions_result = await db.execute(recent_executions_query)
    recent_executions_data = recent_executions_result.fetchall()
    
    recent_executions = []
    for execution, workflow_name in recent_executions_data:
        # Calculate duration if execution is finished
        duration_ms = None
        if execution.finished and execution.stopped_at:
            duration = execution.stopped_at - execution.started_at
            duration_ms = int(duration.total_seconds() * 1000)
        
        recent_executions.append({
            "id": execution.id,
            "workflow_id": execution.workflow_id,
            "workflow_name": workflow_name,
            "status": execution.status,
            "mode": execution.mode,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "finished_at": execution.stopped_at.isoformat() if execution.stopped_at else None,
            "duration_ms": duration_ms,
            "finished": execution.finished
        })
    
    # Prepare response
    return {
        "stats": {
            "totalWorkflows": total_workflows,
            "activeWorkflows": active_workflows,
            "successfulExecutions": successful_executions,
            "failedExecutions": failed_executions,
            "pendingExecutions": pending_executions,
        },
        "recentWorkflows": [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "active": w.active,
                "created_at": w.created_at.isoformat(),
                "updated_at": w.updated_at.isoformat() if w.updated_at else w.created_at.isoformat(),
            }
            for w in recent_workflows
        ],
        "recentExecutions": recent_executions
    }
