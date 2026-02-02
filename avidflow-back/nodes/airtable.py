import requests
import json
import logging
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
from utils.serialization import deep_serialize

logger = logging.getLogger(__name__)


class AirtableNode(BaseNode):
    """
    Airtable node for managing base and table operations
    Supports CRUD operations on Airtable bases and tables
    """

    type = "airtable"
    version = 1.0

    description = {
        "displayName": "Airtable",
        "name": "airtable", 
        "icon": "file:airtable.svg",
        "group": ["input", "output"],
        "description": "Read, write, and manage data in Airtable bases",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
        "credentials": [
            {
                "name": "airtableApi",
                "required": True
            }
        ]
    }

    properties = {
        "parameters": [
            # Resource selection
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Table", "value": "table"},
                    {"name": "Base", "value": "base"}
                ],
                "default": "table",
                "required": True,
                "description": "The resource to operate on"
            },
            
            # Table operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "List Records", "value": "list"},
                    {"name": "Read Record", "value": "read"},
                    {"name": "Create Record", "value": "create"}, 
                    {"name": "Update Record", "value": "update"},
                    {"name": "Delete Record", "value": "delete"},
                    {"name": "Append Record", "value": "append"}
                ],
                "default": "list",
                "display_options": {"show": {"resource": ["table"]}},
                "description": "Operation to perform on table records"
            },
            
            # Base operations
            {
                "name": "baseOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation", 
                "options": [
                    {"name": "List Bases", "value": "listBases"},
                    {"name": "Get Schema", "value": "getSchema"}
                ],
                "default": "listBases",
                "display_options": {"show": {"resource": ["base"]}},
                "description": "Operation to perform on bases"
            },

            # Base identification
            {
                "name": "baseId",
                "type": NodeParameterType.STRING,
                "display_name": "Base ID",
                "default": "",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["table"],
                        "operation": ["list", "read", "create", "update", "delete", "append"]
                    }
                },
                "description": "The ID of the Airtable base (app...)"
            },

            # Table identification  
            {
                "name": "tableId",
                "type": NodeParameterType.STRING,
                "display_name": "Table ID",
                "default": "",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["table"],
                        "operation": ["list", "read", "create", "update", "delete", "append"]
                    }
                },
                "description": "The ID or name of the table"
            },

            # Record ID for read/update/delete operations
            {
                "name": "recordId",
                "type": NodeParameterType.STRING,
                "display_name": "Record ID",
                "default": "",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["table"],
                        "operation": ["read", "update", "delete"]
                    }
                },
                "description": "The ID of the record"
            },

            # Fields for create/update operations
            {
                "name": "fields",
                "type": NodeParameterType.JSON,
                "display_name": "Fields",
                "default": "{}",
                "display_options": {
                    "show": {
                        "resource": ["table"],
                        "operation": ["create", "update", "append"]
                    }
                },
                "description": "JSON object with field names and values"
            },

            # Query parameters for listing records
            {
                "name": "filterByFormula",
                "type": NodeParameterType.STRING,
                "display_name": "Filter by Formula",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["table"],
                        "operation": ["list"]
                    }
                },
                "description": "Airtable formula to filter records (optional)"
            },

            {
                "name": "sort",
                "type": NodeParameterType.JSON,
                "display_name": "Sort",
                "default": "[]",
                "display_options": {
                    "show": {
                        "resource": ["table"],
                        "operation": ["list"]
                    }
                },
                "description": "Array of sort objects [{'field': 'Name', 'direction': 'asc'}]"
            },

            {
                "name": "view",
                "type": NodeParameterType.STRING,
                "display_name": "View",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["table"],
                        "operation": ["list"]
                    }
                },
                "description": "Name or ID of a view in the table (optional)"
            },

            {
                "name": "maxRecords",
                "type": NodeParameterType.NUMBER,
                "display_name": "Max Records",
                "default": 100,
                "display_options": {
                    "show": {
                        "resource": ["table"],
                        "operation": ["list"]
                    }
                },
                "description": "Maximum number of records to return (1-100)"
            },

            {
                "name": "fields",
                "type": NodeParameterType.STRING,
                "display_name": "Fields",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["table"],
                        "operation": ["list", "read"]
                    }
                },
                "description": "Comma-separated field names to retrieve (leave empty for all)"
            },

            # Advanced options
            {
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Options",
                "default": {},
                "display_options": {
                    "show": {
                        "operation": ["list", "create", "update"]
                    }
                },
                "options": [
                    {
                        "name": "cellFormat",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Cell Format",
                        "options": [
                            {"name": "JSON", "value": "json"},
                            {"name": "String", "value": "string"}
                        ],
                        "default": "json",
                        "description": "Format for cell values"
                    },
                    {
                        "name": "timeZone",
                        "type": NodeParameterType.STRING,
                        "display_name": "Time Zone",
                        "default": "UTC",
                        "description": "Time zone for datetime fields"
                    },
                    {
                        "name": "userLocale",
                        "type": NodeParameterType.STRING,
                        "display_name": "User Locale",
                        "default": "en-US",
                        "description": "Locale for formatting values"
                    },
                    {
                        "name": "typecast",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Typecast",
                        "default": False,
                        "description": "Automatically cast field values to appropriate types"
                    },
                    {
                        "name": "returnFieldsByFieldId",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Return Fields by Field ID",
                        "default": False,
                        "description": "Return field values keyed by field ID instead of field name"
                    }
                ]
            }
        ]
    }

    def __init__(self, node_data, workflow, execution_data):
        """Initialize Airtable node"""
        super().__init__(node_data, workflow, execution_data)
        self.base_url = "https://api.airtable.com/v0"
        self.meta_url = "https://api.airtable.com/v0/meta"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Airtable API requests"""
        credentials = self.get_credentials("airtableApi")
        if not credentials:
            raise ValueError("Airtable credentials not found")
            
        api_key = credentials.get("apiKey")
        if not api_key:
            raise ValueError("Airtable API key not found in credentials")
        
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _make_request(
        self, 
        method: str, 
        url: str, 
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Airtable API"""
        try:
            headers = self._get_headers()
            
            logger.info(f"Making {method} request to: {url}")
            if params:
                logger.debug(f"Request params: {params}")
            if data:
                logger.debug(f"Request data: {data}")

            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=30
            )

            # Handle rate limiting
            if response.status_code == 429:
                logger.warning("Rate limited by Airtable API")
                raise Exception("Rate limited. Please try again later.")

            response.raise_for_status()
            
            # Some responses might be empty (e.g., DELETE)
            if response.status_code == 204 or not response.content:
                return {"success": True}
                
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Airtable API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('error', {}).get('message', str(e))
                except:
                    error_message = str(e)
            else:
                error_message = str(e)
            raise Exception(f"Airtable API error: {error_message}")

    def _list_bases(self) -> Dict[str, Any]:
        """List all accessible bases"""
        url = f"{self.meta_url}/bases"
        return self._make_request("GET", url)

    def _get_base_schema(self, base_id: str) -> Dict[str, Any]:
        """Get schema for a specific base"""
        url = f"{self.meta_url}/bases/{base_id}/tables"
        return self._make_request("GET", url)

    def _list_records(
        self, 
        base_id: str, 
        table_id: str,
        filter_formula: Optional[str] = None,
        sort: Optional[List[Dict]] = None,
        view: Optional[str] = None,
        max_records: Optional[int] = None,
        fields: Optional[List[str]] = None,
        additional_options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """List records from a table"""
        url = f"{self.base_url}/{base_id}/{table_id}"
        
        params = {}
        
        if filter_formula:
            params["filterByFormula"] = filter_formula
        
        if sort and len(sort) > 0:
            # Convert sort array to URL params
            for i, sort_item in enumerate(sort):
                field = sort_item.get("field")
                direction = sort_item.get("direction", "asc")
                params[f"sort[{i}][field]"] = field
                params[f"sort[{i}][direction]"] = direction
        
        if view:
            params["view"] = view
            
        if max_records:
            params["maxRecords"] = min(max_records, 100)  # Airtable limit
            
        if fields:
            for field in fields:
                params.setdefault("fields[]", []).append(field)
        
        # Add additional options
        if additional_options:
            if "cellFormat" in additional_options:
                params["cellFormat"] = additional_options["cellFormat"]
            if "timeZone" in additional_options:
                params["timeZone"] = additional_options["timeZone"] 
            if "userLocale" in additional_options:
                params["userLocale"] = additional_options["userLocale"]

        return self._make_request("GET", url, params=params)

    def _read_record(
        self, 
        base_id: str, 
        table_id: str, 
        record_id: str,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Read a specific record"""
        url = f"{self.base_url}/{base_id}/{table_id}/{record_id}"
        
        params = {}
        if fields:
            params["fields[]"] = fields
            
        return self._make_request("GET", url, params=params)

    def _create_record(
        self, 
        base_id: str, 
        table_id: str, 
        fields: Dict[str, Any],
        typecast: bool = False,
        return_fields_by_field_id: bool = False
    ) -> Dict[str, Any]:
        """Create a new record"""
        url = f"{self.base_url}/{base_id}/{table_id}"
        
        data = {
            "fields": fields
        }
        
        if typecast:
            data["typecast"] = True
            
        if return_fields_by_field_id:
            data["returnFieldsByFieldId"] = True
            
        return self._make_request("POST", url, data=data)

    def _update_record(
        self, 
        base_id: str, 
        table_id: str, 
        record_id: str,
        fields: Dict[str, Any],
        typecast: bool = False,
        return_fields_by_field_id: bool = False
    ) -> Dict[str, Any]:
        """Update an existing record"""
        url = f"{self.base_url}/{base_id}/{table_id}/{record_id}"
        
        data = {
            "fields": fields
        }
        
        if typecast:
            data["typecast"] = True
            
        if return_fields_by_field_id:
            data["returnFieldsByFieldId"] = True
            
        return self._make_request("PATCH", url, data=data)

    def _delete_record(
        self, 
        base_id: str, 
        table_id: str, 
        record_id: str
    ) -> Dict[str, Any]:
        """Delete a record"""
        url = f"{self.base_url}/{base_id}/{table_id}/{record_id}"
        return self._make_request("DELETE", url)

    def _append_record(
        self, 
        base_id: str, 
        table_id: str, 
        fields: Dict[str, Any],
        typecast: bool = False,
        return_fields_by_field_id: bool = False
    ) -> Dict[str, Any]:
        """Append/create a new record (alias for create)"""
        return self._create_record(base_id, table_id, fields, typecast, return_fields_by_field_id)

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute the Airtable node operation"""
        try:
            input_data = self.get_input_data()
            results = []
            
            # Get parameters
            resource = self.get_node_parameter("resource", 0, "table")
            
            # Handle different resources
            if resource == "base":
                operation = self.get_node_parameter("baseOperation", 0, "listBases")
                
                if operation == "listBases":
                    response = self._list_bases()
                    results.append(NodeExecutionData(
                        json_data=response,
                        binary_data={}
                    ))
                    
                elif operation == "getSchema":
                    base_id = self.get_node_parameter("baseId", 0)
                    if not base_id:
                        raise ValueError("Base ID is required for getSchema operation")
                        
                    response = self._get_base_schema(base_id)
                    results.append(NodeExecutionData(
                        json_data=response,
                        binary_data={}
                    ))
                    
            elif resource == "table":
                operation = self.get_node_parameter("operation", 0, "list")
                base_id = self.get_node_parameter("baseId", 0)
                table_id = self.get_node_parameter("tableId", 0)
                
                if not base_id:
                    raise ValueError("Base ID is required for table operations")
                if not table_id:
                    raise ValueError("Table ID is required for table operations")
                
                if operation == "list":
                    # Get list parameters
                    filter_formula = self.get_node_parameter("filterByFormula", 0, "")
                    sort_param = self.get_node_parameter("sort", 0, "[]")
                    view = self.get_node_parameter("view", 0, "")
                    max_records = self.get_node_parameter("maxRecords", 0, 100)
                    fields_param = self.get_node_parameter("fields", 0, "")
                    additional_fields = self.get_node_parameter("additionalFields", 0, {})
                    
                    # Process parameters
                    sort_list = []
                    if sort_param and sort_param != "[]":
                        try:
                            sort_list = json.loads(sort_param) if isinstance(sort_param, str) else sort_param
                        except json.JSONDecodeError:
                            logger.warning("Invalid sort parameter, ignoring")
                    
                    fields_list = []
                    if fields_param:
                        fields_list = [f.strip() for f in fields_param.split(",") if f.strip()]
                    
                    response = self._list_records(
                        base_id=base_id,
                        table_id=table_id,
                        filter_formula=filter_formula if filter_formula else None,
                        sort=sort_list if sort_list else None,
                        view=view if view else None,
                        max_records=max_records,
                        fields=fields_list if fields_list else None,
                        additional_options=additional_fields
                    )
                    
                    # Process records
                    records = response.get("records", [])
                    for record in records:
                        results.append(NodeExecutionData(
                            json_data=record,
                            binary_data={}
                        ))
                    
                    # If no records found, still return one item with the full response
                    if not records:
                        results.append(NodeExecutionData(
                            json_data=response,
                            binary_data={}
                        ))
                
                elif operation == "read":
                    record_id = self.get_node_parameter("recordId", 0)
                    fields_param = self.get_node_parameter("fields", 0, "")
                    
                    if not record_id:
                        raise ValueError("Record ID is required for read operation")
                    
                    fields_list = []
                    if fields_param:
                        fields_list = [f.strip() for f in fields_param.split(",") if f.strip()]
                    
                    response = self._read_record(
                        base_id=base_id,
                        table_id=table_id,
                        record_id=record_id,
                        fields=fields_list if fields_list else None
                    )
                    
                    results.append(NodeExecutionData(
                        json_data=response,
                        binary_data={}
                    ))
                
                elif operation in ["create", "append"]:
                    fields_param = self.get_node_parameter("fields", 0, "{}")
                    additional_fields = self.get_node_parameter("additionalFields", 0, {})
                    typecast = additional_fields.get("typecast", False)
                    return_fields_by_field_id = additional_fields.get("returnFieldsByFieldId", False)
                    
                    # Parse fields
                    if isinstance(fields_param, str):
                        try:
                            fields = json.loads(fields_param)
                        except json.JSONDecodeError:
                            raise ValueError("Fields must be valid JSON")
                    else:
                        fields = fields_param
                    
                    if not fields:
                        raise ValueError("Fields cannot be empty for create/append operation")
                    
                    response = self._create_record(
                        base_id=base_id,
                        table_id=table_id,
                        fields=fields,
                        typecast=typecast,
                        return_fields_by_field_id=return_fields_by_field_id
                    )
                    
                    results.append(NodeExecutionData(
                        json_data=response,
                        binary_data={}
                    ))
                
                elif operation == "update":
                    record_id = self.get_node_parameter("recordId", 0)
                    fields_param = self.get_node_parameter("fields", 0, "{}")
                    additional_fields = self.get_node_parameter("additionalFields", 0, {})
                    typecast = additional_fields.get("typecast", False)
                    return_fields_by_field_id = additional_fields.get("returnFieldsByFieldId", False)
                    
                    if not record_id:
                        raise ValueError("Record ID is required for update operation")
                    
                    # Parse fields
                    if isinstance(fields_param, str):
                        try:
                            fields = json.loads(fields_param)
                        except json.JSONDecodeError:
                            raise ValueError("Fields must be valid JSON")
                    else:
                        fields = fields_param
                    
                    if not fields:
                        raise ValueError("Fields cannot be empty for update operation")
                    
                    response = self._update_record(
                        base_id=base_id,
                        table_id=table_id,
                        record_id=record_id,
                        fields=fields,
                        typecast=typecast,
                        return_fields_by_field_id=return_fields_by_field_id
                    )
                    
                    results.append(NodeExecutionData(
                        json_data=response,
                        binary_data={}
                    ))
                
                elif operation == "delete":
                    record_id = self.get_node_parameter("recordId", 0)
                    
                    if not record_id:
                        raise ValueError("Record ID is required for delete operation")
                    
                    response = self._delete_record(
                        base_id=base_id,
                        table_id=table_id,
                        record_id=record_id
                    )
                    
                    results.append(NodeExecutionData(
                        json_data=response,
                        binary_data={}
                    ))

            # Serialize results to ensure compatibility
            serialized_results = []
            for result in results:
                serialized_results.append(NodeExecutionData(
                    json_data=deep_serialize(result.json_data),
                    binary_data=result.binary_data
                ))

            return [serialized_results]
            
        except Exception as e:
            logger.error(f"Error executing Airtable node: {str(e)}")
            # Return error as a result item for debugging
            error_result = NodeExecutionData(
                json_data={
                    "error": True,
                    "message": str(e),
                    "operation": self.get_node_parameter("operation", 0, "unknown"),
                    "resource": self.get_node_parameter("resource", 0, "unknown")
                },
                binary_data={}
            )
            return [[error_result]]