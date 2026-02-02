from __future__ import annotations

import uuid
import logging
from typing import Any, Dict, List, Optional

from .base import BaseNode, NodeParameterType
from models import NodeExecutionData, WorkflowModel
from database.config import get_sync_session_manual
from database.crud import WorkflowCRUD


logger = logging.getLogger(__name__)


class ExecuteWorkflowNode(BaseNode):
    """
    Execute another workflow synchronously by its ID.
    """

    type = "executeWorkflow"
    version = 1

    description = {
        "displayName": "Execute Workflow",
        "name": "executeWorkflow",
        "icon": "fa:sign-in-alt",
        "iconColor": "orange-red",
        "group": ["transform"],
        "version": 1,
        "description": "Execute another workflow by ID (synchronously)",
        "defaults": {"name": "Execute Workflow", "color": "#ff6d5a"},
        "inputs": [{"name": "main", "type": "main", "required": False}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }

    properties = {
        "parameters": [
            {
                "name": "workflowId",
                "type": NodeParameterType.STRING,
                "display_name": "Workflow ID",
                "default": "",
                "required": True,
                "description": "ID of the workflow to execute",
            },
        ]    
    }

    icon = "fa:sign-in-alt"
    color = "#ff6d5a"

    def execute(self) -> List[List[NodeExecutionData]]:
        workflow_id = str(self.get_node_parameter("workflowId", 0, "")).strip()
        if not workflow_id:
            raise ValueError("workflowId is required")

        workflow = self._load_workflow_by_id(workflow_id)
        items = self.get_input_data() or []
        primary_result = self._build_primary_result(items)

        final_result = self._run_subworkflow_sync(workflow, primary_result)
        return final_result or [[]]

    # ---------- helpers ----------

    def _load_workflow_by_id(self, workflow_id: str) -> WorkflowModel:
        with get_sync_session_manual() as session:
            wf_db = WorkflowCRUD.get_workflow_sync(session, workflow_id)
            if not wf_db:
                raise ValueError(f"Workflow not found: {workflow_id}")
            return WorkflowModel.model_validate(wf_db)

    def _build_primary_result(self, items: List[NodeExecutionData]) -> Dict[str, Any]:
        # Pass current items to the sub-workflow
        return {
            "items": [
                {"json": it.json_data or {}, "binary": it.binary_data or {}, "index": i}
                for i, it in enumerate(items or [])
            ]
        }

    def _run_subworkflow_sync(
        self, workflow: WorkflowModel, primary_result: Dict[str, Any]
    ) -> Optional[List[List[NodeExecutionData]]]:
        from engine.execution import (
            ExecutionPlanBuilder,
            WorkflowExecutionContext,
            WorkflowExecutor,
        )

        builder = ExecutionPlanBuilder(workflow)
        sorted_nodes = builder.topological_sort()
        context = WorkflowExecutionContext(
            workflow=workflow,
            execution_id=str(uuid.uuid4()),
            pub_sub=False,
            primary_result=primary_result,
        )
        executor = WorkflowExecutor(context)
        result = executor.execute_nodes(sorted_nodes)
        if "final_result" in result:
            return result["final_result"]
        return [
            [
                NodeExecutionData(
                    json_data={
                        "error": result.get("error"),
                        "error_node_name": result.get("error_node_name"),
                    }
                )
            ]
        ]
