import uuid
import json
from sqlalchemy import desc, delete, update, case, and_, func, Integer
from sqlalchemy.future import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.expression import cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_celery_beat.models import (
    PeriodicTask,
    CrontabSchedule,
)
from typing import Dict, Any, Optional, List, Sequence
from datetime import timezone
from . import models
from models import WorkflowModel, Node
from utils.serialization import deep_serialize
from auth.utils import get_password_hash
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlalchemy import paginate


class WorkflowCRUD:
    @staticmethod
    async def create_workflow(
        db: AsyncSession, workflow_data: WorkflowModel, user_id: str
    ) -> models.Workflow:
        """
        Create a new workflow.

        Args:
            db: Database session
            workflow_data: Workflow data model
            user_id: ID of the workflow owner

        Returns:
            The created Workflow object
        """
        # Convert Pydantic models to dictionaries for JSON serialization
        # Ensure we're using the standard Node model without AI metadata
        nodes_dict = []
        for node in workflow_data.nodes:
            # Convert to standard Node model to strip any extra fields
            if hasattr(node, 'model_dump'):
                node_data = node.model_dump()
            else:
                node_data = node
                
            # Remove AI metadata fields if they exist (defensive programming)
            node_data.pop('ai_tool', None)
            node_data.pop('ai_memory', None) 
            node_data.pop('ai_model', None)
            
            nodes_dict.append(node_data)

        db_workflow = models.Workflow(
            id=str(uuid.uuid4()),
            name=workflow_data.name,
            description=workflow_data.description,
            nodes=nodes_dict,  # Clean nodes without AI metadata
            connections=deep_serialize(workflow_data.connections),
            active=workflow_data.active,
            user_id=user_id,
        )
        db.add(db_workflow)
        await db.commit()
        await db.refresh(db_workflow)

        # ✅ Create webhook records for nodes with webhook_id
        await WorkflowCRUD._create_webhook_records(db, db_workflow, workflow_data.nodes)

        return db_workflow

    @staticmethod
    async def _create_webhook_records(
        db: AsyncSession, workflow: models.Workflow, nodes: List[Node]
    ) -> None:
        """
        Create webhook records for nodes that have webhook_id.

        Args:
            db: Database session
            workflow: The workflow object
            nodes: List of workflow nodes
        """
        webhook_records = []

        for node in nodes:
            # Check if node is a webhook node and has webhook_id
            if node.is_webhook and node.webhook_id:
                # Extract webhook configuration from node parameters
                webhook_config = WorkflowCRUD._extract_webhook_config(node)

                # Create webhook record
                webhook_record = models.Webhook(
                    method=webhook_config.get("method", "POST"),
                    node=node.name,
                    webhook_id=node.webhook_id,
                    workflow_id=workflow.id,
                )

                webhook_records.append(webhook_record)

        # Bulk insert webhook records
        if webhook_records:
            db.add_all(webhook_records)
            await db.commit()

    @staticmethod
    def _extract_webhook_config(node: Node) -> Dict[str, Any]:
        """
        Extract webhook configuration from node parameters.

        Args:
            node: Node object with webhook configuration

        Returns:
            Dictionary with webhook configuration
        """
        # Default webhook configuration
        webhook_config = {"method": "POST"}

        # Extract configuration from node parameters
        if hasattr(node.parameters, "root") and node.parameters.root:
            params = node.parameters.root
            # Extract HTTP method
            if "httpMethod" in params:
                webhook_config["method"] = str(params["httpMethod"]).upper()
            elif "method" in params:
                webhook_config["method"] = str(params["method"]).upper()

        return webhook_config

    @staticmethod
    async def get_workflow(
        db: AsyncSession, workflow_id: str
    ) -> Optional[models.Workflow]:
        """
        Get a workflow by ID.

        Args:
            db: Database session
            workflow_id: ID of the workflow to retrieve

        Returns:
            The Workflow object or None if not found
        """
        result = await db.execute(
            select(models.Workflow).where(models.Workflow.id == workflow_id)
        )
        return result.scalars().first()

    @staticmethod
    def get_workflow_sync(db: Session, workflow_id: str) -> Optional[models.Workflow]:
        """
        Get a workflow by ID (synchronous).

        Args:
            db: Database session
            workflow_id: ID of the workflow to retrieve

        Returns:
            The Workflow object or None if not found
        """
        result = db.execute(
            select(models.Workflow).where(models.Workflow.id == workflow_id)
        )
        return result.scalars().first()

    @staticmethod
    async def update_workflow(
        db: AsyncSession, workflow_id: str, workflow_data: Dict[str, Any]
    ) -> Optional[models.Workflow]:
        """
        Update an existing workflow.

        Args:
            db: Database session
            workflow_id: ID of the workflow to update
            workflow_data: Dictionary of fields to update

        Returns:
            The updated Workflow object or None if not found
        """
        result = await db.execute(
            select(models.Workflow).where(models.Workflow.id == workflow_id)
        )
        workflow = result.scalars().first()

        if not workflow:
            return None

        # Update workflow fields
        for key, value in workflow_data.items():
            if hasattr(workflow, key):
                setattr(workflow, key, value)

        # Update timestamp
        workflow.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(workflow)

        # Update webhook records if nodes were updated
        if "nodes" in workflow_data:
            await WorkflowCRUD._update_webhook_records(
                db, workflow, workflow_data["nodes"]
            )

        return workflow

    @staticmethod
    async def _update_webhook_records(
        db: AsyncSession, workflow: models.Workflow, new_nodes: List[Dict]
    ) -> None:
        """
        Update webhook records when workflow nodes change.

        Args:
            db: Database session
            workflow: Workflow object
            old_nodes: Previous nodes configuration
            new_nodes: New nodes configuration
        """
        # Get current webhook records for this workflow

        await WebhookCRUD.delete_workflow_webhooks(db, workflow.id)

        new_nodes = [Node.model_validate(node_dict) for node_dict in new_nodes]

        await WorkflowCRUD._create_webhook_records(db, workflow, new_nodes)
    @staticmethod
    
    async def delete_workflow(db: AsyncSession, workflow_id: str) -> bool:
        """
        Delete a workflow.

        Args:
            db: Database session
            workflow_id: ID of the workflow to delete

        Returns:
            True if workflow was deleted, False if not found
        """
        result = await db.execute(
            select(models.Workflow).where(models.Workflow.id == workflow_id)
        )
        workflow = result.scalars().first()

        if not workflow:
            return False

        await db.delete(workflow)
        await db.commit()

        return True

    @staticmethod
    async def activate_workflow(
        db: AsyncSession, workflow_id: str
    ) -> Optional[models.Workflow]:
        """
        Set a workflow as active.

        Args:
            db: Database session
            workflow_id: ID of the workflow to activate

        Returns:
            The updated Workflow object or None if not found
        """
        return await WorkflowCRUD.update_workflow(db, workflow_id, {"active": True})

    @staticmethod
    async def deactivate_workflow(
        db: AsyncSession, workflow_id: str
    ) -> Optional[models.Workflow]:
        """
        Set a workflow as inactive.

        Args:
            db: Database session
            workflow_id: ID of the workflow to deactivate

        Returns:
            The updated Workflow object or None if not found
        """
        return await WorkflowCRUD.update_workflow(db, workflow_id, {"active": False})

    @staticmethod
    async def copy_workflow(
        db: AsyncSession, workflow_id: str, user_id: str, new_name: Optional[str] = None
    ) -> Optional[models.Workflow]:
        """
        Create a copy of an existing workflow.

        Args:
            db: Database session
            workflow_id: ID of the workflow to copy
            user_id: ID of the user who will own the copy
            new_name: Optional name for the copy (default: "Copy of {original name}")

        Returns:
            The new Workflow object or None if source not found
        """
        # Get original workflow
        result = await db.execute(
            select(models.Workflow).where(models.Workflow.id == workflow_id)
        )
        original = result.scalars().first()

        if not original:
            return None

        # Create new workflow with copied data
        copy_name = new_name or f"Copy of {original.name}"

        new_workflow = models.Workflow(
            id=str(uuid.uuid4()),
            name=copy_name,
            description=original.description,
            nodes=original.nodes,
            connections=original.connections,
            active=False,  # Always create as inactive
            user_id=user_id,
        )

        db.add(new_workflow)
        await db.commit()
        await db.refresh(new_workflow)

        return new_workflow

    @staticmethod
    async def search_workflows(
        db: AsyncSession,
        params: Params,
        user_id: Optional[str] = None,
        query: Optional[str] = None,
        active_only: bool = False,
    ) -> Sequence[models.Workflow]:
        """
        Search for workflows with optional filtering.

        Args:
            db: Database session
            user_id: Optional user ID to filter by
            query: Optional search text (searches in name and description)
            active_only: Only return active workflows
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching Workflow objects
        """
        # Start with base query
        db_query = select(models.Workflow)

        # Apply filters
        if user_id:
            db_query = db_query.where(models.Workflow.user_id == user_id)

        if active_only:
            db_query = db_query.where(models.Workflow.active == True)

        if query:
            search_term = f"%{query}%"
            db_query = db_query.where(
                models.Workflow.name.ilike(search_term)
                | models.Workflow.description.ilike(search_term)
            )

        # Apply pagination
        db_query = db_query.order_by(models.Workflow.updated_at.desc())

        return await paginate(db, db_query, params)

    @staticmethod
    async def get_all_workflows(
        db: AsyncSession, params: Params, user_id: str, active_only: bool = False
    ) -> Sequence[models.Workflow]:
        """
        Get all workflows for a user for pagination with fastapi-pagination

        Args:
            db: Database session
            user_id: ID of the user
            active_only: Only return active workflows

        Returns:
            List of Workflow objects (will be paginated by fastapi-pagination)
        """
        query = select(models.Workflow).where(models.Workflow.user_id == user_id)

        if active_only:
            query = query.where(models.Workflow.active == True)

        query = query.order_by(models.Workflow.updated_at.desc())
        return await paginate(db, query, params)


class WebhookCRUD:
    """CRUD operations for webhook records"""

    @staticmethod
    async def get_webhook_by_id(
        db: AsyncSession, webhook_id: str
    ) -> Optional[models.Webhook]:
        """
        Get webhook by webhook_id.

        Args:
            db: Database session
            webhook_id: Webhook ID

        Returns:
            Webhook object or None if not found
        """
        result = await db.execute(
            select(models.Webhook).where(models.Webhook.webhook_id == webhook_id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_workflow_webhooks(
        db: AsyncSession, workflow_id: str
    ) -> Sequence[models.Webhook]:
        """
        Get all webhooks for a workflow.

        Args:
            db: Database session
            workflow_id: Workflow ID

        Returns:
            List of Webhook objects
        """
        result = await db.execute(
            select(models.Webhook).where(models.Webhook.workflow_id == workflow_id)
        )
        return result.scalars().all()

    @staticmethod
    async def delete_workflow_webhooks(db: AsyncSession, workflow_id: str) -> bool:
        """
        Delete all webhooks for a workflow.

        Args:
            db: Database session
            workflow_id: Workflow ID

        Returns:
            True if webhooks were deleted
        """
        await db.execute(
            delete(models.Webhook).where(models.Webhook.workflow_id == workflow_id)
        )
        await db.commit()
        return True


class UserCRUD:
    @staticmethod
    async def create_user(
        db: AsyncSession, phone_number: str, password: Optional[str] = None
    ) -> models.User:
        """
        Create a new user with phone number authentication.

        Args:
            db: Database session
            phone_number: User's phone number (will be used as username)
            password: Optional password (if using password auth)

        Returns:
            The created User object
        """
        user = models.User(
            id=str(uuid.uuid4()),  # Generate UUID like in other models
            username=phone_number,  # Use phone number as username
            email=None,  # No email for phone auth
            hashed_password=get_password_hash(password) if password else "",
            is_active=True,
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
            return user
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to create user: {str(e)}")

    @staticmethod
    async def update_last_login(db: AsyncSession, user: models.User) -> models.User:
        """
        Update user's last login timestamp.

        Args:
            db: Database session
            user: User model to update

        Returns:
            Updated User object
        """
        user.last_login = datetime.now(timezone.utc)  # Use timezone-aware datetime
        try:
            await db.commit()
            await db.refresh(user)
            return user
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to update user login time: {str(e)}")

    @staticmethod
    async def get_user(db: AsyncSession, user_id: str) -> Optional[models.User]:
        """
        Get a user by ID.

        Args:
            db: Database session
            user_id: ID of the user

        Returns:
            User object or None if not found
        """
        result = await db.execute(select(models.User).where(models.User.id == user_id))
        return result.scalars().first()

    @staticmethod
    async def get_user_by_phone(
        db: AsyncSession, phone_number: str
    ) -> Optional[models.User]:
        """
        Get a user by phone number (username).

        Args:
            db: Database session
            phone_number: Phone number to search for

        Returns:
            User object or None if not found
        """
        # Corrected to use username field since that's what stores the phone number
        result = await db.execute(
            select(models.User).where(models.User.username == phone_number)
        )
        return result.scalars().first()

    @staticmethod
    async def update_user(
        db: AsyncSession, user_id: str, user_data: Dict[str, Any]
    ) -> Optional[models.User]:
        """
        Update user fields.

        Args:
            db: Database session
            user_id: ID of the user to update
            user_data: Dictionary of fields to update

        Returns:
            Updated User object or None if not found
        """
        result = await db.execute(select(models.User).where(models.User.id == user_id))
        user = result.scalars().first()

        if not user:
            return None

        for key, value in user_data.items():
            if hasattr(user, key):
                setattr(user, key, value)

        try:
            await db.commit()
            await db.refresh(user)
            return user
        except Exception as e:
            await db.rollback()
            raise Exception(f"Failed to update user: {str(e)}")


class ExecutionCRUD:
    """CRUD operations for workflow executions"""

    @staticmethod
    async def get_workflow_executions(
        db: AsyncSession,
        workflow_id: str,
        params: Params
    ) -> Sequence:
        """Get all executions for a specific workflow"""
        duration_ms_expr = case(
            (
                and_(
                    models.Execution.finished.is_(True),
                    models.Execution.started_at.is_not(None),
                    models.Execution.stopped_at.is_not(None),
                ),
                cast(
                    func.round(
                        func.extract(
                            "epoch",
                            (models.Execution.stopped_at - models.Execution.started_at),
                        ) * 1000
                    ),
                    Integer,
                ),
            ),
            else_=None,
        ).label("duration_ms")
        query = (
          select(
             models.Execution.id,
             models.Execution.workflow_id,
             models.Execution.status,
             models.Execution.mode,
             models.Execution.started_at,
             models.Execution.stopped_at.label("finished_at"),
             models.Execution.finished,
             models.Workflow.name.label("workflow_name"),
             duration_ms_expr,
          )
          .join(models.Workflow, models.Execution.workflow_id == models.Workflow.id)
          .filter(models.Execution.workflow_id == workflow_id)
          .order_by(desc(models.Execution.started_at))
        )

        return await paginate(db, query, params)

    @staticmethod
    async def get_all_executions(
        db: AsyncSession, user_id: str, params: Params
    ) -> Sequence:
        """
        Get all executions for a user (paginated).
        Returns a Page object with metadata (total, page, size, pages).
        """
        duration_ms_expr = case(
            (
                and_(
                    models.Execution.finished.is_(True),
                    models.Execution.started_at.is_not(None),
                    models.Execution.stopped_at.is_not(None),
                ),
                cast(
                    func.round(
                        func.extract(
                            "epoch",
                            (models.Execution.stopped_at - models.Execution.started_at),
                        ) * 1000
                    ),
                    Integer,
                ),
            ),
            else_=None,
        ).label("duration_ms")
        query = (
          select(
             models.Execution.id,
             models.Execution.workflow_id,
             models.Execution.status,
             models.Execution.mode,
             models.Execution.started_at,
             models.Execution.stopped_at.label("finished_at"),
             models.Execution.finished,
             models.Workflow.name.label("workflow_name"),
             duration_ms_expr,
          )
          .join(models.Workflow, models.Execution.workflow_id == models.Workflow.id)
          .where(models.Workflow.user_id == user_id)
          .order_by(desc(models.Execution.started_at))
        )

        # Use built-in paginate first (gives us items + total)
        raw_page = await paginate(db, query, params)

        return raw_page

    @staticmethod
    async def create_execution(
        db: AsyncSession,
        workflow_id: str,
        execution_id: Optional[str] = None,
        mode: str = "manual",
        status: str = "running",
        data: Optional[Dict[str, Any]] = None,
        workflow_data: Optional[Dict[str, Any]] = None,
    ) -> models.Execution:
        """
        Create a new execution record for a workflow.

        Args:
            db: Database session
            workflow_id: ID of the workflow being executed
            execution_id: Optional custom execution ID (will be generated if not provided)
            mode: Execution mode (trigger, manual, etc.)
            status: Initial status (running, pending, success, error)
            data: Optional execution data to store
            workflow_data: Optional snapshot of workflow data at execution time

        Returns:
            The created Execution object
        """
        # Create the execution record
        execution = models.Execution(
            id=execution_id or str(uuid.uuid4()),
            workflow_id=workflow_id,
            status=status,
            mode=mode,
            finished=False,
            started_at=datetime.now(),
        )

        db.add(execution)

        # If data is provided, create an ExecutionData record
        if data is not None or workflow_data is not None:
            execution_data = models.ExecutionData(
                execution_id=execution.id,
                data=json.dumps(data or {}),
                workflow_data=deep_serialize(workflow_data) or {},
            )
            db.add(execution_data)

        await db.commit()
        await db.refresh(execution)

        return execution

    @staticmethod
    def create_execution_sync(
        db: Session,
        workflow_id: str,
        execution_id: Optional[str] = None,
        mode: str = "manual",
        status: str = "running",
        data: Optional[Dict[str, Any]] = None,
        workflow_data: Optional[Dict[str, Any]] = None,
    ) -> models.Execution:
        """
        Synchronously create a new execution record for a workflow.

        Args:
            db: Database session
            workflow_id: ID of the workflow being executed
            execution_id: Optional custom execution ID (will be generated if not provided)
            mode: Execution mode (trigger, manual, etc.)
            status: Initial status (running, pending, success, error)
            data: Optional execution data to store
            workflow_data: Optional snapshot of workflow data at execution time

        Returns:
            The created Execution object
        """
        execution = models.Execution(
            id=execution_id or str(uuid.uuid4()),
            workflow_id=workflow_id,
            status=status,
            mode=mode,
            finished=False,
            # started_at=datetime.now(),
        )

        db.add(execution)

        if data is not None or workflow_data is not None:
            execution_data = models.ExecutionData(
                execution_id=execution.id,
                data=json.dumps(data or {}),
                workflow_data=deep_serialize(workflow_data) or {},
            )
            db.add(execution_data)

        db.commit()
        db.refresh(execution)

        return execution

    @staticmethod
    async def update_execution_status(
        db: AsyncSession,
        execution_id: str,
        status: str,
        finished: Optional[bool] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[models.Execution]:
        """
        Update the status of an existing execution.

        Args:
            db: Database session
            execution_id: ID of the execution to update
            status: New status value
            finished: Whether the execution is finished
            data: Updated execution data

        Returns:
            The updated Execution object or None if not found
        """
        # Find the execution
        result = await db.execute(
            select(models.Execution).where(models.Execution.id == execution_id)
        )
        execution = result.scalars().first()

        if not execution:
            return None

        # Update the execution
        execution.status = status

        if finished is not None:
            execution.finished = finished
            if finished:
                execution.stopped_at = datetime.now()

        # Update execution data if provided
        if data is not None and execution.executionData:
            execution_data = execution.executionData
            # Replace data
            execution_data.data = json.dumps(
                json.loads(execution_data.data) | (data or {})
            )

        await db.commit()
        await db.refresh(execution)

        return execution

    @staticmethod
    def update_execution_status_sync(
        db: Session,
        execution_id: str,
        status: str,
        start_time: Optional[datetime] = None,
        finished: Optional[bool] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional["models.Execution"]:
        """
        Synchronously update the status of an existing execution.

        Args:
            db: Database session (sync)
            execution_id: ID of the execution to update
            status: New status value
            start_time: the time execution is start
            finished: Whether the execution is finished
            data: Updated execution data

        Returns:
            The updated Execution object or None if not found
        """
        # Find the execution
        result = db.execute(
            select(models.Execution).where(models.Execution.id == execution_id)
        )
        execution = result.scalars().first()

        if not execution:
            return None

        # Update the execution
        execution.status = status

        if start_time:
            execution.started_at = start_time

        if finished is not None:
            execution.finished = finished
            if finished:
                execution.stopped_at = datetime.now()

        # Update execution data if provided
        if data is not None and execution.executionData:
            execution_data = execution.executionData
            execution_data.data = json.dumps(
                json.loads(execution_data.data) | (data or {})
            )

        db.commit()
        db.refresh(execution)

        return execution

    @staticmethod
    async def get_execution(db: AsyncSession, execution_id: str) -> Optional[dict]:
        """
        Get an execution by ID.

        Args:
            db: Database session
            execution_id: ID of the execution to retrieve

        Returns:
            The Execution object or None if not found
        """
        result = await db.execute(
            select(models.Execution).where(models.Execution.id == execution_id)
        )
        execution = result.scalars().first()
        if not execution:
            return None

        duration_ms = None
        if execution.finished and execution.stopped_at and execution.started_at:
            duration = execution.stopped_at - execution.started_at
            duration_ms = int(duration.total_seconds() * 1000)

        return {
            "id": execution.id,
            "workflow_id": execution.workflow_id,
            "status": execution.status,
            "mode": execution.mode,
            "started_at": (
                execution.started_at.isoformat() if execution.started_at else None
            ),
            "stopped_at": (
                execution.stopped_at.isoformat() if execution.stopped_at else None
            ),
            "duration_ms": duration_ms,
            "finished": execution.finished,
            # Add other fields as needed
        }

    @staticmethod
    async def get_execution_with_data(
        db: AsyncSession, execution_id: str
    ) -> Optional[models.Execution]:
        """
        Get an execution by ID with its associated data.

        Args:
            db: Database session
            execution_id: ID of the execution to retrieve

        Returns:
            The Execution object with executionData loaded or None if not found
        """
        result = await db.execute(
            select(models.Execution)
            .options(selectinload(models.Execution.executionData))
            .where(models.Execution.id == execution_id)
        )
        return result.scalars().first()

    @staticmethod
    def update_execution_data_sync(
        db: Session,
        execution_id: str,
        data: Dict[str, Any],
    ) -> Optional[models.Execution]:
        """
        Synchronously update only the data of an existing execution.
        
        Args:
            db: Database session (sync)
            execution_id: ID of the execution to update
            data: Data to update or add
            
        Returns:
            The updated Execution object or None if not found
        """
        # Find the execution with its data
        result = db.execute(
            select(models.Execution)
            .options(selectinload(models.Execution.executionData))
            .where(models.Execution.id == execution_id)
        )
        execution = result.scalars().first()
        
        if not execution:
            return None
            
        # If execution data doesn't exist, create it
        if not execution.executionData:
            execution_data = models.ExecutionData(
                execution_id=execution.id,
                data=json.dumps(data or {}),
                workflow_data={},
            )
            db.add(execution_data)
        else:
            # Update existing execution data
            execution_data = execution.executionData
            current_data = json.loads(execution_data.data) if execution_data.data else {}
            
            # Deep merge dictionaries
            for key, value in data.items():
                if key in current_data and isinstance(current_data[key], dict) and isinstance(value, dict):
                    current_data[key].update(value)
                else:
                    current_data[key] = value
                    
            execution_data.data = json.dumps(current_data)
    
        db.commit()
        db.refresh(execution)
    
        return execution

class DynamicNodeCRUD:
    """CRUD operations for dynamic nodes"""

    @staticmethod
    async def get_all_nodes(
        db: AsyncSession, active_only: bool = True
    ) -> Sequence[models.DynamicNode]:
        """
        Get all dynamic nodes.

        Args:
            db: Database session
            active_only: If True, only return active nodes

        Returns:
            List of DynamicNode objects
        """
        query = select(models.DynamicNode)

        if active_only:
            query = query.where(models.DynamicNode.is_active == True)

        query = query.order_by(models.DynamicNode.category, models.DynamicNode.name)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_node_by_type(
        db: AsyncSession, node_type: str
    ) -> Optional[models.DynamicNode]:
        """
        Get a dynamic node by type.

        Args:
            db: Database session
            node_type: Type of the node to retrieve

        Returns:
            DynamicNode object or None if not found
        """
        result = await db.execute(
            select(models.DynamicNode).where(models.DynamicNode.type == node_type)
        )
        return result.scalars().first()


class CredentialCRUD:
    @staticmethod
    async def get_credential(
        db: AsyncSession, credential_id: str
    ) -> Optional[models.Credential]:
        """
        Get a credential by ID.

        Args:
            db: Database session
            credential_id: ID of the credential

        Returns:
            Credential object or None if not found
        """
        result = await db.execute(
            select(models.Credential).where(models.Credential.id == credential_id)
        )
        return result.scalars().first()

    @staticmethod
    def get_credential_sync(
        db: Session, credential_id: str
    ) -> Optional[models.Credential]:
        """
        Get a credential by ID (synchronous).

        Args:
            db: Database session
            credential_id: ID of the credential

        Returns:
            Credential object or None if not found
        """
        result = db.execute(
            select(models.Credential).where(models.Credential.id == credential_id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_credentials_by_type(
        db: AsyncSession, user_id: str, credential_type: str
    ) -> Sequence[models.Credential]:
        """
        Get all credentials of a specific type for a user.

        Args:
            db: Database session
            user_id: ID of the user
            credential_type: Type of credential to retrieve

        Returns:
            List of Credential objects
        """
        query = select(models.Credential).where(
            models.Credential.user_id == user_id,
            models.Credential.type == credential_type,
        )
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_all_credentials(
        db: AsyncSession, user_id: str, params: Params
    ) -> Sequence[models.Credential]:
        """
        Get all credentials for a user.

        Args:
            db: Database session
            user_id: ID of the user
            params: Pagination parameters

        Returns:
            List of Credential objects
        """
        query = select(
            models.Credential.id,
            models.Credential.name,
            models.Credential.type,
            models.Credential.created_at,
            models.Credential.updated_at,
        ).where(models.Credential.user_id == user_id)
        query = query.order_by(desc(models.Credential.created_at))
        return await paginate(db, query, params)


class CredentialTypeCRUD:
    @staticmethod
    async def get_all_credential_types(
        db: AsyncSession, active_only: bool = True
    ) -> Sequence[models.CredentialType]:
        """
        Get all credential types from database.

        Args:
            db: Database session
            active_only: If True, only return active credential types

        Returns:
            List of CredentialType objects
        """
        query = select(models.CredentialType)

        if active_only:
            query = query.where(models.CredentialType.is_active == True)

        query = query.order_by(models.CredentialType.display_name)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_credential_type_by_name(
        db: AsyncSession, name: str
    ) -> Optional[models.CredentialType]:
        """
        Get a credential type by name.

        Args:
            db: Database session
            name: Name of the credential type

        Returns:
            CredentialType object or None if not found
        """
        result = await db.execute(
            select(models.CredentialType).where(models.CredentialType.name == name)
        )
        return result.scalars().first()

    @staticmethod
    async def create_credential_type(
        db: AsyncSession, name: str, display_name: str, properties: List[Dict[str, Any]]
    ) -> models.CredentialType:
        """
        Create a new credential type.

        Args:
            db: Database session
            name: Unique name for credential type
            display_name: Human-readable name
            properties: List of property objects

        Returns:
            Created CredentialType object
        """
        credential_type = models.CredentialType(
            id=str(uuid.uuid4()),
            name=name,
            display_name=display_name,
            properties=properties,
        )

        db.add(credential_type)
        await db.commit()
        await db.refresh(credential_type)

        return credential_type


class OptionCRUD:
    @staticmethod
    async def get_options_by_key(db: AsyncSession, key: str) -> Optional[models.Option]:
        """Get option by key."""
        result = await db.execute(
            select(models.Option).where(models.Option.name == key)
        )
        return result.scalars().first()


class PlanCRUD:
    @staticmethod
    async def get_all_plans(db: AsyncSession) -> Sequence[models.Plan]:
        """Get all plans from database."""
        query = select(models.Plan).where(models.Plan.is_active == True)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_plan(db: AsyncSession, plan_id: int) -> Optional[models.Plan]:
        """Get subscription plan by ID"""
        result = await db.execute(select(models.Plan).where(models.Plan.id == plan_id))
        return result.scalars().first()


class OrderCRUD:
    @staticmethod
    async def create_order(
        db: AsyncSession,
        user_id: str,
        plan_id: int,
    ) -> models.Order:
        """Create a new order."""
        plan = await PlanCRUD.get_plan(db, plan_id)
        if not plan:
            raise ValueError("Invalid plan ID")

        tax_rate = await OptionCRUD.get_options_by_key(db, "tax_rate")
        order = models.Order(
            user_id=user_id,
            plan_snapshot={
                "plan_id": plan.id,
                "price": int(plan.price),
                "duration_days": plan.duration_days,
                "nodes_limit": plan.nodes_limit,
                "title": plan.title,
            },
            amount=plan.price,
            tax=(
                int((Decimal(tax_rate.value) / Decimal(100)) * plan.price)
                if tax_rate
                else 0
            ),
        )

        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    @staticmethod
    async def get_user_orders(db: AsyncSession, user_id: str, params: Params) -> Sequence[models.Order]:
        """List user orders"""
        query = (
            select(models.Order)
            .where(models.Order.user_id == user_id)
            .order_by(models.Order.created_at.desc())
        )
        return await paginate(db, query, params)

    @staticmethod
    async def get_order(db: AsyncSession, order_id: int) -> Optional[models.Order]:
        """Get order by ID."""
        result = await db.execute(
            select(models.Order).where(models.Order.id == order_id)
        )
        return result.scalars().first()


class TransactionCRUD:
    @staticmethod
    async def create_transaction(
        db: AsyncSession,
        authority: str,
        order_id: int,
    ) -> models.Transaction:
        """Create a new transaction."""
        transaction = models.Transaction(authority=authority, order_id=order_id)

        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)
        return transaction

    @staticmethod
    async def get_transaction(
        db: AsyncSession, transaction_id: str
    ) -> Optional[models.Transaction]:
        """Get transaction by ID."""
        result = await db.execute(
            select(models.Transaction).where(models.Transaction.id == transaction_id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_transaction_by_authority(
        db: AsyncSession, authority: str
    ) -> Optional[models.Transaction]:
        """Get transaction by authority."""
        result = await db.execute(
            select(models.Transaction).where(models.Transaction.authority == authority)
        )
        return result.scalars().first()


class SubscriptionCRUD:
    @staticmethod
    async def create_subscription(
        db: AsyncSession, user_id: str, order_id: int
    ) -> models.Subscription:
        """Create a new user subscription."""
        order = await OrderCRUD.get_order(db, order_id)
        if not order:
            raise ValueError("Invalid order ID")
        days = order.plan_snapshot["duration_days"]
        end_date = datetime.now(timezone.utc) + timedelta(days=days)
        subscription = models.Subscription(
            user_id=user_id,
            nodes_limit=order.plan_snapshot["nodes_limit"],
            is_active=True,
            end_date=end_date,
        )

        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        return subscription

    @staticmethod
    async def get_user_active_subscription(
        db: AsyncSession, user_id: str
    ) -> Optional[models.Subscription]:
        """Get active subscription for a user"""
        result = await db.execute(
            select(models.Subscription)
            .where(
                models.Subscription.user_id == user_id,
                models.Subscription.is_active == True,
                models.Subscription.end_date > datetime.now(timezone.utc),
            )
            .limit(1)
        )
        return result.scalars().first()

    @staticmethod
    async def get_user_subscriptions(db: AsyncSession, user_id: str):
        """Get all subscriptions for a user"""
        result = await db.execute(
            select(models.Subscription)
            .where(models.Subscription.user_id == user_id)
            .order_by(models.Subscription.created_at.desc())
        )
        return result.scalars().all()

    # Default node limit for users without an active subscription
    # This is the free tier quota that all users receive
    DEFAULT_NODES_LIMIT = 2000

    @staticmethod
    def check_and_consume_nodes_sync(
        db: Session, user_id: str, nodes_to_consume: int
    ) -> tuple[bool, Optional[models.Subscription]]:
        """
        Check and consume nodes from a user's subscription or default quota.
        
        EXECUTION LIMIT ENFORCEMENT (2025-12 Update):
        =============================================
        This is where node execution limits are ENFORCED.
        
        Logic:
        1. If user has an active subscription → use subscription's nodes_limit
        2. If user has NO subscription → create/use a default subscription with 2000 nodes
        3. Check if user has enough remaining nodes
        4. If yes, increment nodes_used and return success
        5. If no, return failure (execution should be blocked)
        
        Args:
            db: Database session
            user_id: User's ID
            nodes_to_consume: Number of nodes to consume in this execution
            
        Returns:
            tuple[bool, Optional[Subscription]]: (success, subscription)
            - (True, subscription) if nodes consumed successfully
            - (False, subscription) if insufficient nodes
            - (False, None) should not happen with new logic (creates default sub)
        """
        subscription: Optional[models.Subscription] = None

        with db.begin():
            # Try to find an active subscription
            result = db.execute(
                select(models.Subscription)
                .where(
                    models.Subscription.user_id == user_id,
                    models.Subscription.is_active == True,
                    models.Subscription.end_date > datetime.now(timezone.utc),
                )
                .limit(1)
                .with_for_update()
            )
            subscription = result.scalars().first()
            
            # If no active subscription, look for a default/free tier subscription
            # or create one if it doesn't exist
            if not subscription:
                # Check for existing default subscription (plan_type='default')
                result = db.execute(
                    select(models.Subscription)
                    .where(
                        models.Subscription.user_id == user_id,
                        models.Subscription.plan_type == 'default',
                    )
                    .limit(1)
                    .with_for_update()
                )
                subscription = result.scalars().first()
                
                if not subscription:
                    # Create a new default subscription for this user
                    # This provides the free tier 2000 node limit
                    subscription = models.Subscription(
                        user_id=user_id,
                        nodes_used=0,
                        nodes_limit=SubscriptionCRUD.DEFAULT_NODES_LIMIT,
                        start_date=datetime.now(timezone.utc),
                        # Set far future end date for default subscriptions
                        end_date=datetime.now(timezone.utc).replace(year=2099),
                        is_active=True,
                        plan_type='default',  # Mark as default/free tier
                    )
                    db.add(subscription)
                    db.flush()  # Get the ID assigned
            
            # Check if user has enough remaining nodes
            if subscription.remaining_nodes < nodes_to_consume:
                return False, subscription

            # Consume the nodes
            subscription.nodes_used += nodes_to_consume
            db.add(subscription)

        db.refresh(subscription)
        return True, subscription


class CeleryTasksCrud:
    @staticmethod
    async def list_enabled_tasks(db: AsyncSession):
        res = await db.execute(select(PeriodicTask).where(PeriodicTask.enabled == True))
        return res.scalars().all()

    @staticmethod
    async def set_task_enabled(db: AsyncSession, name: str, enabled: bool):
        await db.execute(
            update(PeriodicTask)
            .where(PeriodicTask.name == name)
            .values(enabled=enabled)
        )
        await db.commit()

    @staticmethod
    async def upsert_cron_task(
        db: AsyncSession,
        name: str,
        workflow_id: str,
        minute="*",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    ):
        res = await db.execute(
            select(CrontabSchedule).where(
                CrontabSchedule.minute == minute,
                CrontabSchedule.hour == hour,
                CrontabSchedule.day_of_week == day_of_week,
                CrontabSchedule.day_of_month == day_of_month,
                CrontabSchedule.month_of_year == month_of_year,
                CrontabSchedule.timezone == timezone,
            )
        )
        cron = res.scalars().first()
        if not cron:
            cron = CrontabSchedule(
                minute=minute,
                hour=hour,
                day_of_week=day_of_week,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
                timezone=timezone,
            )
            db.add(cron)
            await db.flush()

        res = await db.execute(select(PeriodicTask).where(PeriodicTask.name == name))
        task = res.scalars().first()
        if not task:
            task = PeriodicTask(
                name=name,
                task="workflow.workflow_executor",
                args=json.dumps([workflow_id]),
                kwargs="{}",
                schedule_model=cron,
                enabled=True,
            )
            db.add(task)
        else:
            task.schedule_model = cron
            task.interval = None
            task.clocked = None
            task.solar = None
            task.kwargs = "{}"
            task.enabled = True

        await db.commit()

    @staticmethod
    async def delete_task(db: AsyncSession, name: str):
        res = await db.execute(select(PeriodicTask).where(PeriodicTask.name == name))
        task = res.scalars().first()
        if task:
            await db.delete(task)
            await db.commit()
