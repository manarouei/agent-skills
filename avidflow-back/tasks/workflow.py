import uuid
from celery_app import celery_app
from typing import Dict, Any, Optional
from functools import reduce
from models import Node, WorkflowModel
from gevent import monkey
from utils.serialization import deep_serialize, to_dict_without_binary
from database.crud import ExecutionCRUD, SubscriptionCRUD, WorkflowCRUD
from database.config import get_sync_session_manual
from engine.execution import (
    ExecutionPlanBuilder,
    WorkflowExecutionContext,
    WorkflowExecutor,
)
from services.queue import QueueService
from datetime import datetime, timezone

# Langfuse observability (gracefully degrades if not configured)
from observability.langfuse_client import (
    is_langfuse_enabled,
    create_workflow_trace,
)

import logging

logger = logging.getLogger(__name__)

queue_service = QueueService()
monkey.patch_select()


def count_workflow_nodes(workflow_data: WorkflowModel) -> int:
    """Count total nodes in workflow"""
    return len(workflow_data.nodes) if workflow_data.nodes else 0


def count_executed_nodes(execution_result: Dict[str, Any]) -> int:
    """Count executed nodes from result dictionary"""
    if not execution_result or 'result' not in execution_result:
        return 0
    
    result_data = execution_result['result']['all_results']
    if isinstance(result_data, dict):
        return len(result_data.keys())
    return 0


@celery_app.task(name="workflow.execute_workflow", pydantic=True)
def execute_workflow(
    workflow_data: WorkflowModel,
    execution_id: str,
    user_id: str,  # Add user_id parameter
    primary_result: Dict[str, Any] | None = None,
    pub_sub: bool = False,
) -> Dict[str, Any]:
    """
    Execute entire workflow with node limit check.
    
    Langfuse Integration:
    - Creates one trace per workflow execution
    - trace_id is stored in ExecutionData and propagated to RabbitMQ messages
    - Frontend can deep-link to Langfuse UI using langfuse_trace_id
    """
    
    # Count total nodes before execution
    total_nodes = count_workflow_nodes(workflow_data)
    langfuse_trace_id: Optional[str] = None
    
    # Wrap entire workflow execution in a Langfuse trace
    # This creates one trace per workflow execution with all node spans nested inside
    with create_workflow_trace(
        name="workflow.execute_workflow",
        workflow_id=str(workflow_data.id),
        execution_id=execution_id,
        user_id=user_id,
        workflow_name=workflow_data.name,
        metadata={
            "total_nodes": total_nodes,
            "pub_sub": pub_sub,
        },
        tags=["workflow-engine", "celery"],
        input_data=deep_serialize(primary_result) if primary_result else None,
    ) as trace_ctx:
        # Capture trace_id early for error handling
        if trace_ctx:
            langfuse_trace_id = trace_ctx.trace_id
            logger.debug("Workflow Exec %s - Langfuse trace: %s", execution_id, langfuse_trace_id)
        
        with get_sync_session_manual() as session:
            try:
                # =========================================================
                # EXECUTION LIMIT ENFORCEMENT (2024-12 Update)
                # =========================================================
                # Check subscription and consume nodes atomically.
                # - Users with active subscription: use plan's nodes_limit
                # - Users without subscription: get default 2000 nodes
                # - If quota exceeded: block execution and return error
                #
                # See SubscriptionCRUD.check_and_consume_nodes_sync() for implementation.
                # =========================================================
                success, subscription = SubscriptionCRUD.check_and_consume_nodes_sync(
                    session, user_id, total_nodes
                )
                
                if not success:
                    # Subscription exists but insufficient nodes
                    remaining = subscription.remaining_nodes if subscription else 0
                    error_msg = f"Node limit exceeded. Required: {total_nodes}, Available: {remaining}"
                    
                    # Update execution status to error
                    ExecutionCRUD.update_execution_status_sync(
                        session, execution_id, "error", finished=True, data={"error": error_msg}
                    )
                    
                    # Publish error if pub_sub enabled
                    if pub_sub:
                        queue_service.publish_sync(
                            queue_name="workflow_updates",
                            message={
                                "event": "workflow_error",
                                "workflow_id": str(workflow_data.id),
                                "execution_id": execution_id,
                                "error": error_msg,
                            },
                        )
                    
                    return {
                        "workflow_id": workflow_data.id,
                        "execution_id": execution_id,
                        "status": "error",
                        "error": error_msg,
                        "error_type": "subscription_limit",
                        "nodes_required": total_nodes,
                        "nodes_available": remaining,
                    }

                ExecutionCRUD.update_execution_status_sync(
                    session, execution_id, status="running",
                    start_time=datetime.now(timezone.utc)
                )

                # Create execution plan with topological sorting
                plan_builder = ExecutionPlanBuilder(workflow_data)
                sorted_nodes = plan_builder.topological_sort()
                # logger.info("Workflow Exec %s - Topological order: %s",
                #             execution_id, [n.name for n in sorted_nodes])

                # Initialize execution context with Langfuse trace context
                execution_context = WorkflowExecutionContext(
                    workflow=workflow_data,
                    execution_id=execution_id,
                    pub_sub=pub_sub,
                    primary_result=primary_result,
                    langfuse_trace_ctx=trace_ctx,  # Pass trace context for per-node spans
                )

                executor = WorkflowExecutor(execution_context)
                #logger.info("Workflow Exec %s - Starting node execution", execution_id)
                result = executor.execute_nodes(sorted_nodes)
                #logger.info("Workflow Exec %s - Finished node execution. Collected node keys=%s",
                            #execution_id, list(result.get("all_results", {}).keys()))

                # Quick diagnostic: show output sizes for each node (if structure supports it)
                try:
                    for node_name, node_res in result.get("all_results", {}).items():
                        outs = node_res.get("outputs") if isinstance(node_res, dict) else None
                        if outs:
                            sizes = [len(o) if isinstance(o, list) else 'n/a' for o in outs]
                            logger.info("Workflow Exec %s - Node %s output sizes=%s",
                                        execution_id, node_name, sizes)
                except Exception as _diag_err:
                    logger.debug("Workflow Exec %s - Output size logging failed: %s",
                                 execution_id, _diag_err)

                # Count actually executed nodes
                executed_nodes = count_executed_nodes({
                    "workflow_id": workflow_data.id,
                    "execution_id": execution_id,
                    "status": "completed",
                    "result": result,
                })

                # Update Langfuse trace with final output
                if trace_ctx:
                    trace_ctx.update(
                        output=deep_serialize(result.get('final_result')) if result.get('final_result') else None,
                        metadata={"nodes_executed": executed_nodes}
                    )

                if 'final_result' in result:
                    # Include langfuse_trace_id in execution data for frontend deep-linking
                    execution_data = {
                        "output": deep_serialize(result['final_result']),
                        "node_results": {k: to_dict_without_binary(v) for k, v in result["all_results"].items()}
                    }
                    if langfuse_trace_id:
                        execution_data["langfuse_trace_id"] = langfuse_trace_id
                    
                    ExecutionCRUD.update_execution_status_sync(
                        session, execution_id, "success", finished=True,
                        data=execution_data,
                    )

                    if pub_sub:
                        # Include langfuse_trace_id in RabbitMQ message for WebSocket forwarding
                        message_payload = {
                            "event": "workflow_completed",
                            "workflow_id": str(workflow_data.id),
                            "final_result": deep_serialize(result['final_result']),
                            "execution_id": execution_id,
                        }
                        if langfuse_trace_id:
                            message_payload["langfuse_trace_id"] = langfuse_trace_id
                        
                        queue_service.publish_sync(
                            queue_name="workflow_updates",
                            message=message_payload,
                        )

                response = {
                    "workflow_id": workflow_data.id,
                    "execution_id": execution_id,
                    "result": deep_serialize(result),
                    "nodes_consumed": total_nodes,
                    "nodes_executed": executed_nodes,
                }
                if langfuse_trace_id:
                    response["langfuse_trace_id"] = langfuse_trace_id
                
                return response

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Workflow {workflow_data.id} execution failed: {error_msg}")
                
                # Update Langfuse trace with error info
                if trace_ctx:
                    trace_ctx.update(
                        level="ERROR",
                        output={"error": error_msg},
                    )
                
                # Include langfuse_trace_id in error data for debugging
                error_data = {"error": error_msg}
                if langfuse_trace_id:
                    error_data["langfuse_trace_id"] = langfuse_trace_id
                
                ExecutionCRUD.update_execution_status_sync(
                    session, execution_id, "error", finished=True, data=error_data
                )

                if pub_sub:
                    # Include langfuse_trace_id in error message for WebSocket forwarding
                    error_message = {
                        "event": "workflow_error",
                        "workflow_id": str(workflow_data.id),
                        "execution_id": execution_id,
                        "error": error_msg,
                    }
                    if langfuse_trace_id:
                        error_message["langfuse_trace_id"] = langfuse_trace_id
                    
                    queue_service.publish_sync(
                        queue_name="workflow_updates",
                        message=error_message,
                    )

                error_response = {
                    "workflow_id": workflow_data.id,
                    "execution_id": execution_id,
                    "status": "error",
                    "error": error_msg,
                }
                if langfuse_trace_id:
                    error_response["langfuse_trace_id"] = langfuse_trace_id
                
                return error_response


@celery_app.task(name="workflow.workflow_executor")
def workflow_executor(workflow_id: str):
    execution_id = str(uuid.uuid4())
    with get_sync_session_manual() as session:
        workflow_db = WorkflowCRUD.get_workflow_sync(session, workflow_id)
        if not workflow_db:
            logger.error(f"Workflow {workflow_id} not found")
            return {"status": "error", "message": "Workflow not found"}

        workflow_model = WorkflowModel.model_validate(workflow_db)
        workflow_data = workflow_model.model_dump(mode='json')
        execution = ExecutionCRUD.create_execution_sync(
            db=session,
            workflow_id=workflow_id,
            execution_id=execution_id,
            mode="trigger",
            status="pending",
            workflow_data=workflow_data,
            data={}
        )

        task_arguments = {
            "workflow_data": workflow_data,
            "user_id": workflow_db.user_id,
            "primary_result": {},
            "execution_id": execution_id,
            "pub_sub": False
        }
        task_result = execute_workflow.apply_async(
            kwargs=task_arguments,
            task_id=execution_id
        )

        return {"status": "success", "execution_id": execution_id}
