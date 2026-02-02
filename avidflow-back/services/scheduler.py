import logging
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from database.crud import CeleryTasksCrud
from models import WorkflowModel
from nodes import node_definitions


logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Scheduler service that integrates with Celery
    for workflow scheduling.
    """

    @staticmethod
    async def get_node_schedule(workflow: WorkflowModel) -> Dict[str, Any]:
        node = next((n for n in workflow.nodes if n.is_schedule), None)
        if not node:
            return {}

        node_define = node_definitions.get(node.type)

        if not node_define:
            raise ValueError(f"Node executor for type '{node.type}' not found.")

        node_class = node_define.get("node_class")
        if node_class:
            return node_class(node, workflow, {}).register_schedule()
        return {}

    @staticmethod
    async def schedule_workflow(
        db: AsyncSession, workflow: WorkflowModel, operation: str
    ):
        task_name = f"workflow_{workflow.id}"
        await CeleryTasksCrud.delete_task(db, task_name)
        node = next((n for n in workflow.nodes if n.is_schedule), None)
        if not node:
            return False

        node_schedule = await SchedulerService.get_node_schedule(workflow)
        if operation in ["activate", "update"]:
            if workflow.active:
                await CeleryTasksCrud.upsert_cron_task(
                    db, name=task_name, workflow_id=workflow.id, **node_schedule
                )

        return True
