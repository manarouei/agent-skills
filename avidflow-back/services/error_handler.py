import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException
from datetime import datetime

class WorkflowError(Exception):
    """Base class for workflow execution errors"""
    pass

class CredentialError(Exception):
    """Base class for credential related errors"""
    pass

class ErrorHandler:
    def __init__(self):
        self.logger = logging.getLogger("n8n")
        
    async def log_error(self, 
                       error: Exception, 
                       context: Optional[Dict[str, Any]] = None,
                       workflow_id: Optional[str] = None):
        error_data = {
            "timestamp": datetime.utcnow(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "workflow_id": workflow_id,
            "context": context or {}
        }
        
        if isinstance(error, HTTPException):
            self.logger.warning(error_data)
        else:
            self.logger.error(error_data, exc_info=error)
        
        return error_data

    async def handle_workflow_error(self, workflow_id: str, node_id: str, error: Exception):
        error_data = await self.log_error(
            error,
            context={"node_id": node_id},
            workflow_id=workflow_id
        )
        # Additional workflow-specific error handling
        return error_data
