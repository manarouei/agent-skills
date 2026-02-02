#!/usr/bin/env python3
"""
Postgres Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: postgres-FINAL-TEST
Generated: 2026-01-07T09:04:42.094996

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from .base import BaseNode, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class PostgresNode(BaseNode):
    """
    Postgres node.
    
    
    """

    type = "postgres"
    version = 1
    
    description = {
        "displayName": "Postgres",
        "name": "postgres",
        "icon": "file:postgres.svg",
        "group": ['output'],
        "description": "",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }
    
    properties = {
        "parameters": [
            {"name": "resource", "type": NodeParameterType.OPTIONS, "display_name": "Resource", "options": [
                {"name": "Database", "value": "database"}
            ], "default": "database", "description": "The resource to operate on"}
        ],
        "credentials": [
            {"name": "postgres", "required": True}
        ]
    }
    
    icon = "postgres.svg"

    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the node operations.
        
        SYNC-CELERY SAFE: All HTTP calls use timeout parameter.
        
        Returns:
            List[List[NodeExecutionData]]: Nested list where outer list is output branches,
            inner list is items in that branch.
        """
        # Get input data from previous node
        input_data = self.get_input_data()
        
        # Handle empty input
        if not input_data:
            return [[]]
        
        return_items: List[NodeExecutionData] = []

        for i, item in enumerate(input_data):
            try:
                resource = self.get_node_parameter("resource", i)
                operation = self.get_node_parameter("operation", i)
                item_data = item.json_data if hasattr(item, 'json_data') else item.get('json', {})
                
                pass
                else:
                    raise ValueError(f"Unknown resource/operation: {resource}/{operation}")
                
                # Handle array results
                if isinstance(result, list):
                    for r in result:
                        return_items.append(NodeExecutionData(json_data=r))
                else:
                    return_items.append(NodeExecutionData(json_data=result))
                
            except Exception as e:
                logger.error(f"Error in {resource}/{operation}: {e}")
                if self.node_data.continue_on_fail:
                    return_items.append(NodeExecutionData(json_data={"error": str(e)}))
                else:
                    raise
        
        return [return_items]
"""
PostgreSQL connection helpers
"""

import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)

def _get_connection(self) -> Any:
    """
    Get PostgreSQL database connection
    
    Returns:
        Database connection object
        
    Raises:
        ValueError: If credentials are missing or invalid
    """
    credentials = self.get_credentials("postgres")
    if not credentials:
        raise ValueError("PostgreSQL credentials not found")
    
    # Extract connection parameters
    host = credentials.get("host", "localhost")
    port = credentials.get("port", {"postgres": 5432, "mysql": 3306, "mongodb": 27017}.get("postgres", 5432))
    database = credentials.get("database", "")
    user = credentials.get("user", "")
    password = credentials.get("password", "")
    ssl = credentials.get("ssl", False)
    timeout = credentials.get("connectionTimeout", 30)
    
    if not database or not user:
        raise ValueError("Database name and user are required")
    
    try:
        import psycopg
        from psycopg.rows import dict_row
        
        # Build connection string
        conn_parts = [
            f"host={{host}}",
            f"port={{port}}",
            f"dbname={{database}}",
            f"user={{user}}",
            f"password={{password}}",
            f"connect_timeout={{timeout}}"
        ]
        
        if ssl:
            conn_parts.append("sslmode=require")
        else:
            conn_parts.append("sslmode=prefer")
        
        conn_string = " ".join(conn_parts)
        
        # Create connection with dict_row factory for easy JSON conversion
        conn = psycopg.connect(conn_string, row_factory=dict_row)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise ValueError(f"Failed to connect to database: {str(e)}")


