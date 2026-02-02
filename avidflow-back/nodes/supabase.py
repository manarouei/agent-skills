from typing import Dict, List, Optional, Any, Union
from models import NodeExecutionData
import requests
import json
import traceback
from utils.serialization import deep_serialize
from .base import *
import logging

logger = logging.getLogger(__name__)

class SupabaseNode(BaseNode):
    """
    Supabase node for database operations
    """
    
    type = "supabase"
    version = 1.0
    
    description = {
        "displayName": "Supabase",
        "name": "supabase",
        "group": ["input"],
        "description": "Interact with Supabase database and services",
        "inputs": [
            {"name": "main", "type": "main", "required": True}
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True}
        ],
    }
    
    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "required": True,
                "options": [
                    {
                        "name": "Database",
                        "value": "database"
                    },
                    {
                        "name": "Auth",
                        "value": "auth"
                    },
                    {
                        "name": "Storage",
                        "value": "storage"
                    },
                    {
                        "name": "Edge Functions",
                        "value": "functions"
                    }
                ],
                "default": "database"
            },
            # Database operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["database"]
                    }
                },
                "options": [
                    {"name": "Select", "value": "select"},
                    {"name": "Insert", "value": "insert"},
                    {"name": "Update", "value": "update"},
                    {"name": "Delete", "value": "delete"},
                    {"name": "Upsert", "value": "upsert"},
                    {"name": "RPC", "value": "rpc"}
                ],
                "default": "select"
            },
            # Auth operations
            {
                "name": "authOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["auth"]
                    }
                },
                "options": [
                    {"name": "Sign Up", "value": "signup"},
                    {"name": "Sign In", "value": "signin"},
                    {"name": "Sign Out", "value": "signout"},
                    {"name": "Get User", "value": "getUser"},
                    {"name": "Update User", "value": "updateUser"},
                    {"name": "Delete User", "value": "deleteUser"}
                ],
                "default": "getUser"
            },
            # Storage operations
            {
                "name": "storageOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["storage"]
                    }
                },
                "options": [
                    {"name": "Upload", "value": "upload"},
                    {"name": "Download", "value": "download"},
                    {"name": "List", "value": "list"},
                    {"name": "Delete", "value": "delete"},
                    {"name": "Create Bucket", "value": "createBucket"},
                    {"name": "Get Public URL", "value": "getPublicUrl"}
                ],
                "default": "list"
            },
            # Functions operations
            {
                "name": "functionsOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["functions"]
                    }
                },
                "options": [
                    {"name": "Invoke", "value": "invoke"}
                ],
                "default": "invoke"
            },
            # Database parameters
            {
                "name": "table",
                "type": NodeParameterType.STRING,
                "display_name": "Table",
                "default": "",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["select", "insert", "update", "delete", "upsert"]
                    }
                },
                "description": "Name of the table to operate on"
            },
            {
                "name": "columns",
                "type": NodeParameterType.STRING,
                "display_name": "Columns",
                "default": "*",
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["select"]
                    }
                },
                "description": "Columns to select (comma-separated or *)"
            },
            {
                "name": "filter",
                "type": NodeParameterType.STRING,
                "display_name": "Filter",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["select", "update", "delete"]
                    }
                },
                "description": "Filter conditions (e.g., id=eq.1, name=like.*john*)"
            },
            {
                "name": "order",
                "type": NodeParameterType.STRING,
                "display_name": "Order By",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["select"]
                    }
                },
                "description": "Order by columns (e.g., created_at.desc, name.asc)"
            },
            {
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 100,
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["select"]
                    }
                },
                "description": "Maximum number of rows to return"
            },
            {
                "name": "offset",
                "type": NodeParameterType.NUMBER,
                "display_name": "Offset",
                "default": 0,
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["select"]
                    }
                },
                "description": "Number of rows to skip"
            },
            {
                "name": "data",
                "type": NodeParameterType.JSON,
                "display_name": "Data",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["insert", "update", "upsert"]
                    }
                },
                "description": "Data to insert/update"
            },
            {
                "name": "conflictResolution",
                "type": NodeParameterType.OPTIONS,
                "display_name": "On Conflict",
                "default": "merge",
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["upsert"]
                    }
                },
                "options": [
                    {"name": "Merge", "value": "merge"},
                    {"name": "Ignore", "value": "ignore"}
                ],
                "description": "How to handle conflicts during upsert"
            },
            {
                "name": "rpcFunction",
                "type": NodeParameterType.STRING,
                "display_name": "Function Name",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["rpc"]
                    }
                },
                "description": "Name of the stored procedure to call"
            },
            {
                "name": "rpcParams",
                "type": NodeParameterType.JSON,
                "display_name": "Parameters",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["rpc"]
                    }
                },
                "description": "Parameters for the stored procedure"
            },
            # Auth parameters
            {
                "name": "email",
                "type": NodeParameterType.STRING,
                "display_name": "Email",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["auth"],
                        "authOperation": ["signup", "signin"]
                    }
                },
                "description": "User email address"
            },
            {
                "name": "password",
                "type": NodeParameterType.STRING,  # FIXED: Changed from PASSWORD to STRING
                "display_name": "Password",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["auth"],
                        "authOperation": ["signup", "signin"]
                    }
                },
                "description": "User password"
            },
            {
                "name": "userId",
                "type": NodeParameterType.STRING,
                "display_name": "User ID",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["auth"],
                        "authOperation": ["getUser", "updateUser", "deleteUser"]
                    }
                },
                "description": "User ID to operate on"
            },
            {
                "name": "userMetadata",
                "type": NodeParameterType.JSON,
                "display_name": "User Metadata",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["auth"],
                        "authOperation": ["signup", "updateUser"]
                    }
                },
                "description": "Additional user metadata"
            },
            # Storage parameters
            {
                "name": "bucket",
                "type": NodeParameterType.STRING,
                "display_name": "Bucket",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["storage"]
                    }
                },
                "description": "Storage bucket name"
            },
            {
                "name": "filePath",
                "type": NodeParameterType.STRING,
                "display_name": "File Path",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["storage"],
                        "storageOperation": ["upload", "download", "delete", "getPublicUrl"]
                    }
                },
                "description": "Path to the file in storage"
            },
            {
                "name": "fileData",
                "type": NodeParameterType.STRING,
                "display_name": "File Data",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["storage"],
                        "storageOperation": ["upload"]
                    }
                },
                "description": "File data (base64 encoded or local file path)"
            },
            {
                "name": "contentType",
                "type": NodeParameterType.STRING,
                "display_name": "Content Type",
                "default": "application/octet-stream",
                "display_options": {
                    "show": {
                        "resource": ["storage"],
                        "storageOperation": ["upload"]
                    }
                },
                "description": "MIME type of the file"
            },
            {
                "name": "bucketOptions",
                "type": NodeParameterType.JSON,
                "display_name": "Bucket Options",
                "default": {"public": False},
                "display_options": {
                    "show": {
                        "resource": ["storage"],
                        "storageOperation": ["createBucket"]
                    }
                },
                "description": "Bucket configuration options"
            },
            # Functions parameters
            {
                "name": "functionName",
                "type": NodeParameterType.STRING,
                "display_name": "Function Name",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["functions"],
                        "functionsOperation": ["invoke"]
                    }
                },
                "description": "Name of the edge function to invoke"
            },
            {
                "name": "functionPayload",
                "type": NodeParameterType.JSON,
                "display_name": "Payload",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["functions"],
                        "functionsOperation": ["invoke"]
                    }
                },
                "description": "Payload to send to the function"
            },
            # Common parameters
            {
                "name": "returnRepresentation",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Return Representation",
                "default": True,
                "display_options": {
                    "show": {
                        "resource": ["database"],
                        "operation": ["insert", "update", "delete", "upsert"]
                    }
                },
                "description": "Return the modified rows"
            }
        ],
        "credentials": [
            {
                "name": "supabaseApi",
                "required": True
            }
        ]
    }
    
    icon = "file:supabase.svg"
    color = "#3ECF8E"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Supabase node operations"""
        
        try:
            # Get parameters
            resource = self.get_node_parameter("resource", 0, "database")
            operation = self._get_operation_for_resource(resource)
            
            input_data = self.get_input_data()
            
            result = self._process_resource_operation(resource, operation, input_data)
            
            # Check if result contains an error
            if isinstance(result, dict) and "error" in result:
                return self._prepare_error_data(result["error"])
            
            # Serialize the result for proper JSON handling
            serialized_result = deep_serialize(result)
            return [[NodeExecutionData(json_data=serialized_result)]]
            
        except Exception as e:
            traceback.print_exc()
            return self._prepare_error_data(f"Error executing Supabase node: {str(e)}")

    def _get_operation_for_resource(self, resource):
        """Get the appropriate operation for the given resource"""
        if resource == "database":
            return self.get_node_parameter("operation", 0, "select")
        elif resource == "auth":
            return self.get_node_parameter("authOperation", 0, "getUser")
        elif resource == "storage":
            return self.get_node_parameter("storageOperation", 0, "list")
        elif resource == "functions":
            return self.get_node_parameter("functionsOperation", 0, "invoke")
        else:
            return "select"

    def _process_resource_operation(self, resource, operation, input_data):
        """Process the requested resource operation"""
        try:
            if resource == "database":
                return self._process_database(operation, input_data)
            elif resource == "auth":
                return self._process_auth(operation, input_data)
            elif resource == "storage":
                return self._process_storage(operation, input_data)
            elif resource == "functions":
                return self._process_functions(operation, input_data)
            else:
                return {"error": f"Resource {resource} is not supported"}
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing {resource}.{operation}: {str(e)}"}

    def _prepare_error_data(self, error_message: str) -> List[List[NodeExecutionData]]:
        """Create error data structure for failed executions"""
        return [[NodeExecutionData(json_data={"error": error_message})]]

    def _get_base_headers(self):
        """Get base headers for Supabase requests"""
        credentials = self.get_credentials("supabaseApi")
        
        if not credentials:
            raise Exception("No credentials found. Please set up Supabase API credentials.")
        
        service_key = credentials.get("serviceKey")
        if not service_key:
            raise Exception("Service key is required for Supabase integration")
        
        return {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json"
        }

    def _get_base_url(self):
        """Get base URL for Supabase requests"""
        credentials = self.get_credentials("supabaseApi")
        
        if not credentials:
            raise Exception("No credentials found. Please set up Supabase API credentials.")
        
        host = credentials.get("host", "").rstrip("/")
        if not host:
            raise Exception("Host is required for Supabase integration")
        
        return host

    def _process_database(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle database operations"""
        try:
            base_url = self._get_base_url()
            headers = self._get_base_headers()
            
            if operation == "select":
                table = self.get_node_parameter("table", 0, "")
                columns = self.get_node_parameter("columns", 0, "*")
                filter_param = self.get_node_parameter("filter", 0, "")
                order = self.get_node_parameter("order", 0, "")
                limit = self.get_node_parameter("limit", 0, 100)
                offset = self.get_node_parameter("offset", 0, 0)
                
                if not table:
                    return {"error": "Table name is required"}
                
                # Build URL with query parameters
                url = f"{base_url}/rest/v1/{table}"
                params = {}
                
                if columns != "*":
                    params["select"] = columns
                
                if filter_param:
                    # Parse filter conditions
                    filters = filter_param.split(",")
                    for f in filters:
                        if "=" in f:
                            key, value = f.split("=", 1)
                            params[key.strip()] = value.strip()
                
                if order:
                    params["order"] = order
                
                if limit:
                    params["limit"] = str(limit)
                
                if offset:
                    params["offset"] = str(offset)
                
                response = requests.get(url, headers=headers, params=params)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase API error: {response.text}"}
                
                return {"data": response.json()}
                
            elif operation in ["insert", "update", "upsert"]:
                table = self.get_node_parameter("table", 0, "")
                data = self.get_node_parameter("data", 0, {})
                return_representation = self.get_node_parameter("returnRepresentation", 0, True)
                
                if not table:
                    return {"error": "Table name is required"}
                
                if not data:
                    return {"error": "Data is required"}
                
                url = f"{base_url}/rest/v1/{table}"
                
                if return_representation:
                    headers["Prefer"] = "return=representation"
                
                if operation == "insert":
                    response = requests.post(url, headers=headers, json=data)
                elif operation == "update":
                    filter_param = self.get_node_parameter("filter", 0, "")
                    if filter_param:
                        # Parse filter conditions
                        filters = filter_param.split(",")
                        params = {}
                        for f in filters:
                            if "=" in f:
                                key, value = f.split("=", 1)
                                params[key.strip()] = value.strip()
                        response = requests.patch(url, headers=headers, json=data, params=params)
                    else:
                        return {"error": "Filter is required for update operation"}
                elif operation == "upsert":
                    conflict_resolution = self.get_node_parameter("conflictResolution", 0, "merge")
                    if conflict_resolution == "merge":
                        headers["Prefer"] += ",resolution=merge-duplicates"
                    else:
                        headers["Prefer"] += ",resolution=ignore-duplicates"
                    response = requests.post(url, headers=headers, json=data)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase API error: {response.text}"}
                
                if return_representation:
                    return {"data": response.json()}
                else:
                    return {"message": f"{operation.capitalize()} successful"}
                
            elif operation == "delete":
                table = self.get_node_parameter("table", 0, "")
                filter_param = self.get_node_parameter("filter", 0, "")
                return_representation = self.get_node_parameter("returnRepresentation", 0, True)
                
                if not table:
                    return {"error": "Table name is required"}
                
                if not filter_param:
                    return {"error": "Filter is required for delete operation"}
                
                url = f"{base_url}/rest/v1/{table}"
                
                if return_representation:
                    headers["Prefer"] = "return=representation"
                
                # Parse filter conditions
                filters = filter_param.split(",")
                params = {}
                for f in filters:
                    if "=" in f:
                        key, value = f.split("=", 1)
                        params[key.strip()] = value.strip()
                
                response = requests.delete(url, headers=headers, params=params)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase API error: {response.text}"}
                
                if return_representation:
                    return {"data": response.json()}
                else:
                    return {"message": "Delete successful"}
                
            elif operation == "rpc":
                function_name = self.get_node_parameter("rpcFunction", 0, "")
                params = self.get_node_parameter("rpcParams", 0, {})
                
                if not function_name:
                    return {"error": "Function name is required"}
                
                url = f"{base_url}/rest/v1/rpc/{function_name}"
                
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase API error: {response.text}"}
                
                return {"data": response.json()}
            
            return {"error": f"Operation {operation} is not supported for database resource"}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing database operation: {str(e)}"}

    def _process_auth(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle auth operations"""
        try:
            base_url = self._get_base_url()
            headers = self._get_base_headers()
            
            if operation == "signup":
                email = self.get_node_parameter("email", 0, "")
                password = self.get_node_parameter("password", 0, "")
                metadata = self.get_node_parameter("userMetadata", 0, {})
                
                if not email or not password:
                    return {"error": "Email and password are required"}
                
                url = f"{base_url}/auth/v1/signup"
                data = {
                    "email": email,
                    "password": password
                }
                
                if metadata:
                    data["data"] = metadata
                
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Auth error: {response.text}"}
                
                return response.json()
                
            elif operation == "signin":
                email = self.get_node_parameter("email", 0, "")
                password = self.get_node_parameter("password", 0, "")
                
                if not email or not password:
                    return {"error": "Email and password are required"}
                
                url = f"{base_url}/auth/v1/token?grant_type=password"
                data = {
                    "email": email,
                    "password": password
                }
                
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Auth error: {response.text}"}
                
                return response.json()
                
            elif operation == "getUser":
                user_id = self.get_node_parameter("userId", 0, "")
                
                if not user_id:
                    return {"error": "User ID is required"}
                
                url = f"{base_url}/auth/v1/admin/users/{user_id}"
                
                response = requests.get(url, headers=headers)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Auth error: {response.text}"}
                
                return response.json()
                
            elif operation == "updateUser":
                user_id = self.get_node_parameter("userId", 0, "")
                metadata = self.get_node_parameter("userMetadata", 0, {})
                
                if not user_id:
                    return {"error": "User ID is required"}
                
                url = f"{base_url}/auth/v1/admin/users/{user_id}"
                
                response = requests.put(url, headers=headers, json=metadata)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Auth error: {response.text}"}
                
                return response.json()
                
            elif operation == "deleteUser":
                user_id = self.get_node_parameter("userId", 0, "")
                
                if not user_id:
                    return {"error": "User ID is required"}
                
                url = f"{base_url}/auth/v1/admin/users/{user_id}"
                
                response = requests.delete(url, headers=headers)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Auth error: {response.text}"}
                
                return {"message": "User deleted successfully"}
            
            return {"error": f"Operation {operation} is not supported for auth resource"}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing auth operation: {str(e)}"}

    def _process_storage(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle storage operations"""
        try:
            base_url = self._get_base_url()
            headers = self._get_base_headers()
            
            bucket = self.get_node_parameter("bucket", 0, "")
            
            if operation == "list":
                if not bucket:
                    # List buckets
                    url = f"{base_url}/storage/v1/bucket"
                    response = requests.get(url, headers=headers)
                else:
                    # List files in bucket
                    url = f"{base_url}/storage/v1/object/list/{bucket}"
                    response = requests.post(url, headers=headers, json={})
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Storage error: {response.text}"}
                
                return {"data": response.json()}
                
            elif operation == "upload":
                file_path = self.get_node_parameter("filePath", 0, "")
                file_data = self.get_node_parameter("fileData", 0, "")
                content_type = self.get_node_parameter("contentType", 0, "application/octet-stream")
                
                if not bucket or not file_path or not file_data:
                    return {"error": "Bucket, file path, and file data are required"}
                
                url = f"{base_url}/storage/v1/object/{bucket}/{file_path}"
                
                # Handle file data
                if file_data.startswith("data:"):
                    # Base64 data
                    import base64
                    _, data = file_data.split(",", 1)
                    file_content = base64.b64decode(data)
                else:
                    # File path
                    try:
                        with open(file_data, "rb") as f:
                            file_content = f.read()
                    except Exception as e:
                        return {"error": f"Error reading file: {str(e)}"}
                
                upload_headers = headers.copy()
                upload_headers["Content-Type"] = content_type
                
                response = requests.post(url, headers=upload_headers, data=file_content)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Storage error: {response.text}"}
                
                return response.json()
                
            elif operation == "download":
                file_path = self.get_node_parameter("filePath", 0, "")
                
                if not bucket or not file_path:
                    return {"error": "Bucket and file path are required"}
                
                url = f"{base_url}/storage/v1/object/{bucket}/{file_path}"
                
                response = requests.get(url, headers=headers)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Storage error: {response.text}"}
                
                # Return base64 encoded content
                import base64
                content = base64.b64encode(response.content).decode('utf-8')
                
                return {
                    "content": content,
                    "contentType": response.headers.get("Content-Type", "application/octet-stream"),
                    "size": len(response.content)
                }
                
            elif operation == "delete":
                file_path = self.get_node_parameter("filePath", 0, "")
                
                if not bucket or not file_path:
                    return {"error": "Bucket and file path are required"}
                
                url = f"{base_url}/storage/v1/object/{bucket}/{file_path}"
                
                response = requests.delete(url, headers=headers)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Storage error: {response.text}"}
                
                return {"message": "File deleted successfully"}
                
            elif operation == "createBucket":
                bucket_options = self.get_node_parameter("bucketOptions", 0, {"public": False})
                
                if not bucket:
                    return {"error": "Bucket name is required"}
                
                url = f"{base_url}/storage/v1/bucket"
                data = {
                    "id": bucket,
                    "name": bucket,
                    **bucket_options
                }
                
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Storage error: {response.text}"}
                
                return response.json()
                
            elif operation == "getPublicUrl":
                file_path = self.get_node_parameter("filePath", 0, "")
                
                if not bucket or not file_path:
                    return {"error": "Bucket and file path are required"}
                
                # Public URL format
                public_url = f"{base_url}/storage/v1/object/public/{bucket}/{file_path}"
                
                return {"publicUrl": public_url}
            
            return {"error": f"Operation {operation} is not supported for storage resource"}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing storage operation: {str(e)}"}

    def _process_functions(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle edge functions operations"""
        try:
            base_url = self._get_base_url()
            headers = self._get_base_headers()
            
            if operation == "invoke":
                function_name = self.get_node_parameter("functionName", 0, "")
                payload = self.get_node_parameter("functionPayload", 0, {})
                
                if not function_name:
                    return {"error": "Function name is required"}
                
                url = f"{base_url}/functions/v1/{function_name}"
                
                response = requests.post(url, headers=headers, json=payload)
                
                if response.status_code >= 400:
                    return {"error": f"Supabase Functions error: {response.text}"}
                
                try:
                    return response.json()
                except:
                    return {"result": response.text}
            
            return {"error": f"Operation {operation} is not supported for functions resource"}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing functions operation: {str(e)}"}