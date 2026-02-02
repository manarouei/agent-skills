"""
PostgreSQL node for database operations
Supports query execution, insert, update, delete operations
"""
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from typing import Dict, List, Optional, Any, Union
import json
import logging
import traceback

from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class PostgresNode(BaseNode):
    """
    PostgreSQL node for database operations
    """
    
    type = "postgres"
    version = 2.0
    
    description = {
        "displayName": "Postgres",
        "name": "postgres",
        "icon": "file:postgres.svg",
        "group": ["input", "output"],
        "description": "Execute PostgreSQL queries and manage database operations",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }
    
    properties = {
        "parameters": [
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {
                        "name": "Execute Query",
                        "value": "executeQuery",
                        "description": "Execute a SQL query"
                    },
                    {
                        "name": "Insert",
                        "value": "insert",
                        "description": "Insert rows into a table"
                    },
                    {
                        "name": "Update",
                        "value": "update",
                        "description": "Update rows in a table"
                    },
                    {
                        "name": "Delete",
                        "value": "delete",
                        "description": "Delete rows from a table"
                    },
                ],
                "default": "executeQuery",
                "description": "The operation to perform",
            },
            
            # Execute Query parameters
            {
                "name": "query",
                "type": NodeParameterType.STRING,
                "display_name": "Query",
                "default": "",
                "required": True,
                "type_options": {
                    "rows": 5,
                    "alwaysOpenEditWindow": True,
                },
                "description": "The SQL query to execute",
                "display_options": {
                    "show": {
                        "operation": ["executeQuery"]
                    }
                },
            },
            
            # Table name (for insert, update, delete)
            {
                "name": "table",
                "type": NodeParameterType.STRING,
                "display_name": "Table",
                "default": "",
                "required": True,
                "description": "Name of the table to operate on",
                "display_options": {
                    "show": {
                        "operation": ["insert", "update", "delete"]
                    }
                },
            },
            
            # Insert parameters
            {
                "name": "columns",
                "type": NodeParameterType.STRING,
                "display_name": "Columns",
                "default": "",
                "required": True,
                "description": "Comma-separated list of column names",
                "placeholder": "id,name,email",
                "display_options": {
                    "show": {
                        "operation": ["insert"]
                    }
                },
            },
            
            # Data source for insert
            {
                "name": "dataMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Data Mode",
                "options": [
                    {
                        "name": "Auto-Map Input Data",
                        "value": "autoMap",
                        "description": "Use data from input automatically"
                    },
                    {
                        "name": "Define Below",
                        "value": "defineBelow",
                        "description": "Specify data manually"
                    },
                ],
                "default": "autoMap",
                "description": "How to provide data for insert",
                "display_options": {
                    "show": {
                        "operation": ["insert"]
                    }
                },
            },
            
            {
                "name": "values",
                "type": NodeParameterType.STRING,
                "display_name": "Values",
                "default": "",
                "required": True,
                "description": "Comma-separated values (use expressions for dynamic values)",
                "placeholder": "{{ $json.id }},{{ $json.name }},{{ $json.email }}",
                "display_options": {
                    "show": {
                        "operation": ["insert"],
                        "dataMode": ["defineBelow"]
                    }
                },
            },
            
            # Update parameters
            {
                "name": "updateColumns",
                "type": NodeParameterType.STRING,
                "display_name": "Columns to Update",
                "default": "",
                "required": True,
                "description": "Comma-separated list of columns to update",
                "placeholder": "name,email,updated_at",
                "display_options": {
                    "show": {
                        "operation": ["update"]
                    }
                },
            },
            
            {
                "name": "updateValues",
                "type": NodeParameterType.STRING,
                "display_name": "Values",
                "default": "",
                "required": True,
                "description": "Comma-separated values (use expressions for dynamic values)",
                "placeholder": "{{ $json.name }},{{ $json.email }},NOW()",
                "display_options": {
                    "show": {
                        "operation": ["update"]
                    }
                },
            },
            
            # WHERE clause for update and delete
            {
                "name": "whereClause",
                "type": NodeParameterType.STRING,
                "display_name": "WHERE Condition",
                "default": "",
                "required": False,
                "description": "WHERE clause (without 'WHERE' keyword). Leave empty to affect all rows.",
                "placeholder": "id = {{ $json.id }}",
                "display_options": {
                    "show": {
                        "operation": ["update", "delete"]
                    }
                },
            },
            
            # Options
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "options": [
                    {
                        "name": "queryTimeout",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Query Timeout",
                        "default": 30,
                        "description": "Query execution timeout in seconds"
                    },
                    {
                        "name": "returnData",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Return Data",
                        "default": True,
                        "description": "Whether to return the affected rows (INSERT/UPDATE/DELETE with RETURNING *)"
                    },
                    {
                        "name": "outputAsJson",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Always Output as JSON",
                        "default": True,
                        "description": "Always return data as JSON even if only one row"
                    },
                ],
            },
        ],
        "credentials": [{"name": "postgresApi", "required": True}],
    }
    
    icon = "postgres.svg"
    color = "#336791"
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute PostgreSQL operation and return properly formatted data"""
        
        try:
            # Get input data
            input_data = self.get_input_data()

            if not input_data:
                input_data = [[]]
            
            result_items: List[NodeExecutionData] = []
            
            # Process each input item
            for i, item in enumerate(input_data):
                try:
                    # Get parameters for this item
                    operation = self.get_node_parameter("operation", i, "executeQuery")
                    
                    # Execute the appropriate operation
                    if operation == "executeQuery":
                        result = self._execute_query(i)
                    elif operation == "insert":
                        result = self._insert(i)
                    elif operation == "update":
                        result = self._update(i)
                    elif operation == "delete":
                        result = self._delete(i)
                    else:
                        raise ValueError(f"Unsupported operation '{operation}'")
                    
                    # Add result to items
                    if isinstance(result, list):
                        for res_item in result:
                            result_items.append(
                                NodeExecutionData(json_data=res_item, binary_data=None)
                            )
                    else:
                        result_items.append(
                            NodeExecutionData(json_data=result, binary_data=None)
                        )
                
                except Exception as e:
                    logger.error(f"Error processing item {i}: {str(e)}")
                    traceback.print_exc()
                    
                    # Create error data following project pattern
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "operation": self.get_node_parameter("operation", i, "executeQuery"),
                            "item_index": i,
                        },
                        binary_data=None,
                    )
                    result_items.append(error_item)
            
            return [result_items]
        
        except Exception as e:
            logger.error(f"Error in Postgres node: {str(e)}")
            traceback.print_exc()
            
            error_data = [
                NodeExecutionData(
                    json_data={"error": f"Error in Postgres node: {str(e)}"},
                    binary_data=None,
                )
            ]
            return [error_data]
    
    def _get_connection(self) -> psycopg.Connection:
        """
        Get PostgreSQL database connection
        
        Returns:
            psycopg connection object
            
        Raises:
            ValueError: If credentials are missing or invalid
        """
        credentials = self.get_credentials("postgresApi")
        if not credentials:
            raise ValueError("PostgreSQL credentials not found")
        
        # Extract connection parameters
        host = credentials.get("host", "localhost")
        port = credentials.get("port", 5432)
        database = credentials.get("database", "")
        user = credentials.get("user", "")
        password = credentials.get("password", "")
        ssl = credentials.get("ssl", False)
        timeout = credentials.get("connectionTimeout", 30)
        
        if not database or not user:
            raise ValueError("Database name and user are required")
        
        # Build connection string
        conn_parts = [
            f"host={host}",
            f"port={port}",
            f"dbname={database}",
            f"user={user}",
            f"password={password}",
            f"connect_timeout={timeout}"
        ]
        
        if ssl:
            conn_parts.append("sslmode=require")
        else:
            conn_parts.append("sslmode=prefer")
        
        conn_string = " ".join(conn_parts)
        
        try:
            # Create connection with dict_row factory for easy JSON conversion
            conn = psycopg.connect(conn_string, row_factory=dict_row)
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {str(e)}")
            raise ValueError(f"Failed to connect to database: {str(e)}")
    
    def _execute_query(self, item_index: int) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Execute a custom SQL query
        
        Args:
            item_index: Index of the input item
            
        Returns:
            Query results as list of dictionaries or single dictionary
        """
        query = self.get_node_parameter("query", item_index, "")
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        options = self.get_node_parameter("options", item_index, {}) or {}
        query_timeout = options.get("queryTimeout", 30)
        output_as_json = options.get("outputAsJson", True)
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cur:
                # Set statement timeout
                cur.execute(f"SET statement_timeout = {query_timeout * 1000}")
                
                # Execute query
                cur.execute(query)
                
                # Check if query returns data
                if cur.description:
                    results = cur.fetchall()
                    conn.commit()
                    
                    # Convert to list of dicts (dict_row factory handles this)
                    if not results:
                        return []
                    
                    # Return as list or single item based on option
                    if output_as_json or len(results) > 1:
                        return results
                    else:
                        return results[0]
                else:
                    # Query doesn't return data (INSERT/UPDATE/DELETE without RETURNING)
                    conn.commit()
                    return {
                        "success": True,
                        "rowCount": cur.rowcount,
                        "message": f"Query executed successfully. {cur.rowcount} row(s) affected."
                    }
        
        except psycopg.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"PostgreSQL error: {str(e)}")
            raise ValueError(f"Database error: {str(e)}")
        
        finally:
            if conn:
                conn.close()
    
    def _insert(self, item_index: int) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Insert data into a table
        
        Args:
            item_index: Index of the input item
            
        Returns:
            Inserted row(s) data or success message
        """
        table = self.get_node_parameter("table", item_index, "")
        columns_str = self.get_node_parameter("columns", item_index, "")
        data_mode = self.get_node_parameter("dataMode", item_index, "autoMap")
        options = self.get_node_parameter("options", item_index, {}) or {}
        
        if not table or not columns_str:
            raise ValueError("Table name and columns are required")
        
        # Parse columns
        columns = [col.strip() for col in columns_str.split(",") if col.strip()]
        
        # Get values based on data mode
        if data_mode == "autoMap":
            # Use input item's json data
            input_items = self.get_input_data()
            current_item = input_items[item_index] if 0 <= item_index < len(input_items) else None
            
            if not current_item:
                raise ValueError("No input data available for auto-mapping")
            
            json_data = getattr(current_item, "json_data", {})
            values = [json_data.get(col) for col in columns]
        else:
            # Use manually defined values
            values_str = self.get_node_parameter("values", item_index, "")
            if not values_str:
                raise ValueError("Values are required")
            
            # Parse values (simple comma split - expressions are already evaluated)
            values = [val.strip() for val in values_str.split(",")]
        
        if len(values) != len(columns):
            raise ValueError(f"Number of values ({len(values)}) doesn't match number of columns ({len(columns)})")
        
        return_data = options.get("returnData", True)
        query_timeout = options.get("queryTimeout", 30)
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cur:
                # Set statement timeout
                cur.execute(f"SET statement_timeout = {query_timeout * 1000}")
                
                # Build INSERT query
                placeholders = ", ".join(["%s"] * len(columns))
                columns_joined = ", ".join([sql.Identifier(col).as_string(conn) for col in columns])
                
                if return_data:
                    query = f"INSERT INTO {sql.Identifier(table).as_string(conn)} ({columns_joined}) VALUES ({placeholders}) RETURNING *"
                else:
                    query = f"INSERT INTO {sql.Identifier(table).as_string(conn)} ({columns_joined}) VALUES ({placeholders})"
                
                # Execute insert
                cur.execute(query, values)
                
                if return_data and cur.description:
                    result = cur.fetchall()
                    conn.commit()
                    return result[0] if len(result) == 1 else result
                else:
                    conn.commit()
                    return {
                        "success": True,
                        "rowCount": cur.rowcount,
                        "message": f"Successfully inserted {cur.rowcount} row(s)"
                    }
        
        except psycopg.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"PostgreSQL insert error: {str(e)}")
            raise ValueError(f"Insert failed: {str(e)}")
        
        finally:
            if conn:
                conn.close()
    
    def _update(self, item_index: int) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Update data in a table
        
        Args:
            item_index: Index of the input item
            
        Returns:
            Updated row(s) data or success message
        """
        table = self.get_node_parameter("table", item_index, "")
        update_columns_str = self.get_node_parameter("updateColumns", item_index, "")
        update_values_str = self.get_node_parameter("updateValues", item_index, "")
        where_clause = self.get_node_parameter("whereClause", item_index, "")
        options = self.get_node_parameter("options", item_index, {}) or {}
        
        if not table or not update_columns_str or not update_values_str:
            raise ValueError("Table name, columns, and values are required")
        
        # Parse columns and values
        columns = [col.strip() for col in update_columns_str.split(",") if col.strip()]
        values = [val.strip() for val in update_values_str.split(",")]
        
        if len(values) != len(columns):
            raise ValueError(f"Number of values ({len(values)}) doesn't match number of columns ({len(columns)})")
        
        return_data = options.get("returnData", True)
        query_timeout = options.get("queryTimeout", 30)
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cur:
                # Set statement timeout
                cur.execute(f"SET statement_timeout = {query_timeout * 1000}")
                
                # Build UPDATE query
                set_clauses = ", ".join([
                    f"{sql.Identifier(col).as_string(conn)} = %s"
                    for col in columns
                ])
                
                query_parts = [
                    f"UPDATE {sql.Identifier(table).as_string(conn)}",
                    f"SET {set_clauses}"
                ]
                
                if where_clause:
                    query_parts.append(f"WHERE {where_clause}")
                
                if return_data:
                    query_parts.append("RETURNING *")
                
                query = " ".join(query_parts)
                
                # Execute update
                cur.execute(query, values)
                
                if return_data and cur.description:
                    result = cur.fetchall()
                    conn.commit()
                    return result if result else {"success": True, "rowCount": 0, "message": "No rows matched the criteria"}
                else:
                    row_count = cur.rowcount
                    conn.commit()
                    return {
                        "success": True,
                        "rowCount": row_count,
                        "message": f"Successfully updated {row_count} row(s)"
                    }
        
        except psycopg.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"PostgreSQL update error: {str(e)}")
            raise ValueError(f"Update failed: {str(e)}")
        
        finally:
            if conn:
                conn.close()
    
    def _delete(self, item_index: int) -> Dict[str, Any]:
        """
        Delete data from a table
        
        Args:
            item_index: Index of the input item
            
        Returns:
            Deletion result with row count
        """
        table = self.get_node_parameter("table", item_index, "")
        where_clause = self.get_node_parameter("whereClause", item_index, "")
        options = self.get_node_parameter("options", item_index, {}) or {}
        
        if not table:
            raise ValueError("Table name is required")
        
        # Safety check: require WHERE clause or explicit confirmation
        if not where_clause:
            logger.warning("DELETE operation without WHERE clause - will delete ALL rows")
            # In production, you might want to require explicit confirmation
            # raise ValueError("WHERE clause is required for DELETE operation (safety check)")
        
        return_data = options.get("returnData", False)  # Default to False for delete
        query_timeout = options.get("queryTimeout", 30)
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cur:
                # Set statement timeout
                cur.execute(f"SET statement_timeout = {query_timeout * 1000}")
                
                # Build DELETE query
                query_parts = [f"DELETE FROM {sql.Identifier(table).as_string(conn)}"]
                
                if where_clause:
                    query_parts.append(f"WHERE {where_clause}")
                
                if return_data:
                    query_parts.append("RETURNING *")
                
                query = " ".join(query_parts)
                
                # Execute delete
                cur.execute(query)
                
                if return_data and cur.description:
                    result = cur.fetchall()
                    conn.commit()
                    return {
                        "success": True,
                        "rowCount": len(result),
                        "deletedRows": result,
                        "message": f"Successfully deleted {len(result)} row(s)"
                    }
                else:
                    row_count = cur.rowcount
                    conn.commit()
                    return {
                        "success": True,
                        "rowCount": row_count,
                        "message": f"Successfully deleted {row_count} row(s)"
                    }
        
        except psycopg.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"PostgreSQL delete error: {str(e)}")
            raise ValueError(f"Delete failed: {str(e)}")
        
        finally:
            if conn:
                conn.close()