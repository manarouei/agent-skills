#!/usr/bin/env python3
"""
Postgres Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: convert-postgres-001
Generated: 2026-02-02T05:34:18.516068

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from urllib.parse import quote

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
        
        # FIX #40: Handle empty input - create default item so nodes work from Start
        if not input_data:
            input_data = [NodeExecutionData(json_data={})]
        
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
                # Platform doesn't support continue_on_fail - always raise
                raise
        
        return [return_items]

    def _get_postgres_connection(self):
        """
        Create and return a Postgres connection using configured credentials.
        
        SYNC-CELERY SAFE: Synchronous connection with timeout.
        
        Returns:
            psycopg.Connection: Configured Postgres connection
        """
        credentials = self.get_credentials("postgresApi")
        
        if not credentials:
            raise Exception("Postgres credentials not configured")
        
        host = credentials.get("host", "localhost")
        port = int(credentials.get("port", 5432))
        database = credentials.get("database", "postgres")
        user = credentials.get("user", "postgres")
        password = credentials.get("password", "")
        ssl = credentials.get("ssl", False)
        
        # Build connection string
        conn_params = {
            "host": host,
            "port": port,
            "dbname": database,
            "user": user,
            "password": password,
            "connect_timeout": 30,
        }
        
        if ssl:
            conn_params["sslmode"] = "require"
        
        return psycopg.connect(**conn_params, row_factory=dict_row)
    
    def _execute_query(
        self,
        query: str,
        params: tuple | None = None,
        fetch: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute a SQL query with proper connection handling.
        
        SYNC-CELERY SAFE: All operations are synchronous.
        """
        with self._get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                
                if fetch:
                    return cur.fetchall()
                else:
                    conn.commit()
                    return [{"affected_rows": cur.rowcount}]


