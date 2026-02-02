"""
MySQL node for database operations
Supports query execution, insert, update, delete operations
"""
import pymysql
from pymysql.cursors import DictCursor
from typing import Dict, List, Optional, Any, Union
import json
import logging
import traceback

from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class MySQLNode(BaseNode):
    """
    MySQL node for database operations
    """

    type = "mysql"
    version = 1.0

    description = {
        "displayName": "MySQL",
        "name": "mysql",
        "icon": "file:mysql.svg",
        "group": ["input", "output"],
        "description": "Execute MySQL queries and manage database operations",
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
                    {"name": "Execute Query", "value": "executeQuery", "description": "Execute a SQL query"},
                    {"name": "Insert", "value": "insert", "description": "Insert rows into a table"},
                    {"name": "Update", "value": "update", "description": "Update rows in a table"},
                    {"name": "Delete", "value": "delete", "description": "Delete rows from a table"},
                ],
                "default": "executeQuery",
                "description": "The operation to perform",
            },
            # Execute Query operation parameters
            {
                "name": "query",
                "type": NodeParameterType.STRING,
                "display_name": "Query",
                "default": "",
                "required": True,
                "description": "The SQL query to execute",
                "display_options": {"show": {"operation": ["executeQuery"]}},
            },
            # Table parameter (unified for insert, update, delete)
            {
                "name": "table",
                "type": NodeParameterType.RESOURCE_LOCATOR,
                "display_name": "Table",
                "default": {"mode": "list", "value": ""},
                "required": True,
                "modes": [
                    {
                        "displayName": "From List",
                        "name": "list",
                        "type": "list",
                        "placeholder": "Select a Table...",
                        "typeOptions": {
                            "searchListMethod": "searchTables",
                            "searchFilterRequired": False,
                            "searchable": True,
                        },
                    },
                    {
                        "displayName": "Name",
                        "name": "name",
                        "type": "string",
                        "placeholder": "table_name",
                    },
                ],
                "description": "Name of the table to operate on",
                "display_options": {"show": {"operation": ["insert", "update", "delete"]}},
            },
            # Insert operation parameters
            {
                "name": "columns",
                "type": NodeParameterType.STRING,
                "display_name": "Columns",
                "default": "",
                "required": True,
                "description": "Comma-separated list of the properties which should be used as columns for the new rows",
                "display_options": {"show": {"operation": ["insert"]}},
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
                "display_options": {"show": {"operation": ["insert"]}},
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
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "placeholder": "Add modifiers",
                "description": "Modifiers for INSERT statement",
                "display_options": {"show": {"operation": ["insert"]}},
                "options": [
                    {
                        "name": "ignore",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Ignore",
                        "default": True,
                        "description": "Whether to ignore any ignorable errors that occur while executing the INSERT statement",
                    },
                    {
                        "name": "priority",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Priority",
                        "options": [
                            {
                                "name": "Low Priority",
                                "value": "LOW_PRIORITY",
                                "description": "Delays execution of the INSERT until no other clients are reading from the table",
                            },
                            {
                                "name": "High Priority",
                                "value": "HIGH_PRIORITY",
                                "description": "Overrides the effect of the --low-priority-updates option if the server was started with that option",
                            },
                        ],
                        "default": "LOW_PRIORITY",
                        "description": "Priority for INSERT statement execution",
                    },
                ],
            },
            # Update operation parameters
            {
                "name": "updateKey",
                "type": NodeParameterType.STRING,
                "display_name": "Update Key",
                "default": "id",
                "required": True,
                "description": "Name of the property which decides which rows in the database should be updated. Normally that would be 'id'.",
                "display_options": {"show": {"operation": ["update"]}},
            },
            {
                "name": "updateColumns",
                "type": NodeParameterType.STRING,
                "display_name": "Columns to Update",
                "default": "",
                "required": True,
                "description": "Comma-separated list of columns to update",
                "placeholder": "name,email,updated_at",
                "display_options": {"show": {"operation": ["update"]}},
            },
            {
                "name": "updateValues",
                "type": NodeParameterType.STRING,
                "display_name": "Values",
                "default": "",
                "required": True,
                "description": "Comma-separated values (use expressions for dynamic values)",
                "placeholder": "{{ $json.name }},{{ $json.email }},NOW()",
                "display_options": {"show": {"operation": ["update"]}},
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
                "display_options": {"show": {"operation": ["update", "delete"]}},
            },
            # Delete operation parameters
            {
                "name": "deleteKey",
                "type": NodeParameterType.STRING,
                "display_name": "Delete Key",
                "default": "id",
                "required": True,
                "description": "Name of the property which decides which rows in the database should be deleted. Normally that would be 'id'.",
                "display_options": {"show": {"operation": ["delete"]}},
            },
            # General options for all operations
            {
                "name": "additionalOptions",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Options",
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
                        "description": "Whether to return the affected rows"
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
        "credentials": [{"name": "mysqlApi", "required": True}],
    }

    icon = "mysql.svg"
    color = "#00758F"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute MySQL operation and return properly formatted data"""
        
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
            logger.error(f"Error in MySQL node: {str(e)}")
            traceback.print_exc()
            
            error_data = [
                NodeExecutionData(
                    json_data={"error": f"Error in MySQL node: {str(e)}"},
                    binary_data=None,
                )
            ]
            return [error_data]

    def _get_connection(self) -> pymysql.Connection:
        """Get MySQL database connection"""
        credentials = self.get_credentials("mysqlApi")
        if not credentials:
            raise ValueError("MySQL credentials not found")

        try:
            conn = pymysql.connect(
                host=credentials.get("host", "localhost"),
                port=credentials.get("port", 3306),
                user=credentials.get("user", ""),
                password=credentials.get("password", ""),
                database=credentials.get("database", ""),
                cursorclass=DictCursor,
            )
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to MySQL: {str(e)}")
            raise ValueError(f"Failed to connect to database: {str(e)}")

    def _execute_query(self, item_index: int) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Execute a custom SQL query"""
        query = self.get_node_parameter("query", item_index, "")
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        options = self.get_node_parameter("additionalOptions", item_index, {}) or {}
        query_timeout = options.get("queryTimeout", 30)
        output_as_json = options.get("outputAsJson", True)

        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cursor:
                # Set query timeout for MySQL
                cursor.execute(f"SET SESSION max_execution_time = {query_timeout * 1000}")
                
                # Execute query
                cursor.execute(query)
                
                # Check if query returns data
                if cursor.description:
                    results = cursor.fetchall()
                    conn.commit()
                    
                    if not results:
                        return []
                    
                    # Return as list or single item based on option
                    if output_as_json or len(results) > 1:
                        return results
                    else:
                        return results[0]
                else:
                    # Query doesn't return data (INSERT/UPDATE/DELETE)
                    conn.commit()
                    return {
                        "success": True,
                        "rowCount": cursor.rowcount,
                        "message": f"Query executed successfully. {cursor.rowcount} row(s) affected."
                    }
        
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"MySQL error: {str(e)}")
            raise ValueError(f"Database error: {str(e)}")
        
        finally:
            if conn:
                conn.close()

    def _insert(self, item_index: int) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Insert data into a table"""
        # Get table name from resource locator
        table_param = self.get_node_parameter("table", item_index, {"mode": "list", "value": ""})
        if isinstance(table_param, dict):
            table = table_param.get("value", "")
        else:
            table = str(table_param)
            
        if not table:
            raise ValueError("Table name is required for insert operation")

        columns_str = self.get_node_parameter("columns", item_index, "")
        data_mode = self.get_node_parameter("dataMode", item_index, "autoMap")
        options = self.get_node_parameter("options", item_index, {}) or {}
        additional_options = self.get_node_parameter("additionalOptions", item_index, {}) or {}
        
        if not columns_str:
            raise ValueError("Columns are required for insert operation")
        
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
        
        # Get insert options
        insert_ignore = options.get("ignore", False)
        insert_priority = options.get("priority", "")
        return_data = additional_options.get("returnData", True)
        query_timeout = additional_options.get("queryTimeout", 30)
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cursor:
                # Set query timeout
                cursor.execute(f"SET SESSION max_execution_time = {query_timeout * 1000}")
                
                # Build INSERT query with backtick escaping for MySQL
                columns_escaped = ", ".join([f"`{col}`" for col in columns])
                placeholders = ", ".join(["%s"] * len(columns))
                
                priority_clause = f"{insert_priority} " if insert_priority else ""
                ignore_clause = "IGNORE " if insert_ignore else ""
                
                if return_data:
                    # MySQL doesn't support RETURNING, so we use LAST_INSERT_ID()
                    query = f"INSERT {priority_clause}{ignore_clause}INTO `{table}` ({columns_escaped}) VALUES ({placeholders})"
                else:
                    query = f"INSERT {priority_clause}{ignore_clause}INTO `{table}` ({columns_escaped}) VALUES ({placeholders})"
                
                # Execute insert
                cursor.execute(query, values)
                row_count = cursor.rowcount
                
                # Check if insert was successful
                if row_count == 0:
                    conn.rollback()
                    if insert_ignore:
                        raise ValueError(f"Insert failed: No rows were inserted. This typically happens due to duplicate key or constraint violation. Row was ignored due to IGNORE flag.")
                    else:
                        raise ValueError(f"Insert failed: No rows were inserted. This may indicate a constraint violation or invalid data.")
                
                if return_data and cursor.lastrowid:
                    # Fetch the inserted row using lastrowid
                    cursor.execute(f"SELECT * FROM `{table}` WHERE id = %s", (cursor.lastrowid,))
                    result = cursor.fetchone()
                    conn.commit()
                    return result if result else {"success": True, "rowCount": row_count}
                else:
                    conn.commit()
                    return {
                        "success": True,
                        "rowCount": row_count,
                        "message": f"Successfully inserted {row_count} row(s)"
                    }
        
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            error_msg = f"Insert failed for table '{table}': {str(e)}"
            logger.error(f"MySQL insert error: {error_msg}")
            logger.error(f"Columns: {columns}, Values: {values}")
            raise ValueError(error_msg)
        
        except Exception as e:
            if conn:
                conn.rollback()
            error_msg = f"Unexpected error during insert into '{table}': {str(e)}"
            logger.error(error_msg)
            traceback.print_exc()
            raise ValueError(error_msg)
        
        finally:
            if conn:
                conn.close()

    def _update(self, item_index: int) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Update data in a table"""
        # Get table name from resource locator
        table_param = self.get_node_parameter("table", item_index, {"mode": "list", "value": ""})
        if isinstance(table_param, dict):
            table = table_param.get("value", "")
        else:
            table = str(table_param)
            
        if not table:
            raise ValueError("Table name is required for update operation")

        # Support both old (updateKey/columns) and new (updateColumns/updateValues) parameters
        update_columns_str = self.get_node_parameter("updateColumns", item_index, "")
        update_values_str = self.get_node_parameter("updateValues", item_index, "")
        where_clause = self.get_node_parameter("whereClause", item_index, "")
        additional_options = self.get_node_parameter("additionalOptions", item_index, {}) or {}
        
        # Fallback to old parameters if new ones are not provided
        if not update_columns_str:
            update_columns_str = self.get_node_parameter("columns", item_index, "")
            update_key = self.get_node_parameter("updateKey", item_index, "id")
            
            if update_columns_str:
                # Old style: use input data for values
                input_items = self.get_input_data()
                current_item = input_items[item_index] if 0 <= item_index < len(input_items) else None
                json_data = getattr(current_item, "json_data", {}) if current_item else {}
                
                columns = [col.strip() for col in update_columns_str.split(",") if col.strip()]
                values = [json_data.get(col) for col in columns]
                
                # Build WHERE clause from updateKey
                if not where_clause:
                    where_clause = f"`{update_key}` = {json_data.get(update_key)!r}"
        else:
            # New style: use updateColumns and updateValues
            if not update_values_str:
                raise ValueError("Update values are required")
                
            columns = [col.strip() for col in update_columns_str.split(",") if col.strip()]
            values = [val.strip() for val in update_values_str.split(",")]
        
        if not update_columns_str:
            raise ValueError("Update columns are required")
        
        if len(values) != len(columns):
            raise ValueError(f"Number of values ({len(values)}) doesn't match number of columns ({len(columns)})")
        
        return_data = additional_options.get("returnData", True)
        query_timeout = additional_options.get("queryTimeout", 30)
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cursor:
                # Set query timeout
                cursor.execute(f"SET SESSION max_execution_time = {query_timeout * 1000}")
                
                # Build UPDATE query with backtick escaping
                set_clauses = ", ".join([f"`{col}` = %s" for col in columns])
                
                query_parts = [
                    f"UPDATE `{table}`",
                    f"SET {set_clauses}"
                ]
                
                if where_clause:
                    query_parts.append(f"WHERE {where_clause}")
                
                query = " ".join(query_parts)
                
                # Execute update
                cursor.execute(query, values)
                row_count = cursor.rowcount
                
                if return_data and row_count > 0:
                    # MySQL doesn't support RETURNING, so fetch updated rows if WHERE clause exists
                    if where_clause:
                        select_query = f"SELECT * FROM `{table}` WHERE {where_clause}"
                        cursor.execute(select_query)
                        result = cursor.fetchall()
                        conn.commit()
                        return result if result else {"success": True, "rowCount": 0, "message": "No rows matched the criteria"}
                    else:
                        conn.commit()
                        return {
                            "success": True,
                            "rowCount": row_count,
                            "message": f"Successfully updated {row_count} row(s)"
                        }
                else:
                    conn.commit()
                    return {
                        "success": True,
                        "rowCount": row_count,
                        "message": f"Successfully updated {row_count} row(s)"
                    }
        
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            error_msg = f"Update failed for table '{table}': {str(e)}"
            logger.error(f"MySQL update error: {error_msg}")
            logger.error(f"Columns: {columns}, Values: {values}, WHERE: {where_clause}")
            raise ValueError(error_msg)
        
        except Exception as e:
            if conn:
                conn.rollback()
            error_msg = f"Unexpected error during update on '{table}': {str(e)}"
            logger.error(error_msg)
            traceback.print_exc()
            raise ValueError(error_msg)
        
        finally:
            if conn:
                conn.close()

    def _delete(self, item_index: int) -> Dict[str, Any]:
        """Delete data from a table"""
        # Get table name from resource locator
        table_param = self.get_node_parameter("table", item_index, {"mode": "list", "value": ""})
        if isinstance(table_param, dict):
            table = table_param.get("value", "")
        else:
            table = str(table_param)
            
        if not table:
            raise ValueError("Table name is required for delete operation")

        where_clause = self.get_node_parameter("whereClause", item_index, "")
        additional_options = self.get_node_parameter("additionalOptions", item_index, {}) or {}
        
        # Fallback to old deleteKey parameter if whereClause is not provided
        if not where_clause:
            delete_key = self.get_node_parameter("deleteKey", item_index, "id")
            input_items = self.get_input_data()
            current_item = input_items[item_index] if 0 <= item_index < len(input_items) else None
            json_data = getattr(current_item, "json_data", {}) if current_item else {}
            delete_value = json_data.get(delete_key)
            
            if delete_value is not None:
                where_clause = f"`{delete_key}` = {delete_value!r}"
        
        # Safety check: require WHERE clause or explicit confirmation
        if not where_clause:
            logger.warning("DELETE operation without WHERE clause - will delete ALL rows")
            # In production, you might want to require explicit confirmation
            # raise ValueError("WHERE clause is required for DELETE operation (safety check)")
        
        return_data = additional_options.get("returnData", False)  # Default to False for delete
        query_timeout = additional_options.get("queryTimeout", 30)
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cursor:
                # Set query timeout
                cursor.execute(f"SET SESSION max_execution_time = {query_timeout * 1000}")
                
                # Build DELETE query
                query_parts = [f"DELETE FROM `{table}`"]
                
                if where_clause:
                    query_parts.append(f"WHERE {where_clause}")
                
                query = " ".join(query_parts)
                
                # MySQL doesn't support RETURNING, so fetch before delete if needed
                deleted_rows = None
                if return_data and where_clause:
                    select_query = f"SELECT * FROM `{table}` WHERE {where_clause}"
                    cursor.execute(select_query)
                    deleted_rows = cursor.fetchall()
                
                # Execute delete
                cursor.execute(query)
                row_count = cursor.rowcount
                
                conn.commit()
                
                if return_data and deleted_rows:
                    return {
                        "success": True,
                        "rowCount": row_count,
                        "deletedRows": deleted_rows,
                        "message": f"Successfully deleted {row_count} row(s)"
                    }
                else:
                    return {
                        "success": True,
                        "rowCount": row_count,
                        "message": f"Successfully deleted {row_count} row(s)"
                    }
        
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            error_msg = f"Delete failed for table '{table}': {str(e)}"
            logger.error(f"MySQL delete error: {error_msg}")
            logger.error(f"WHERE clause: {where_clause}")
            raise ValueError(error_msg)
        
        except Exception as e:
            if conn:
                conn.rollback()
            error_msg = f"Unexpected error during delete from '{table}': {str(e)}"
            logger.error(error_msg)
            traceback.print_exc()
            raise ValueError(error_msg)
        
        finally:
            if conn:
                conn.close()