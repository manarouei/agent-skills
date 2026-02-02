import requests
import json
import logging
from typing import Dict, List, Optional, Any
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
import base64

logger = logging.getLogger(__name__)


class OpenProjectNode(BaseNode):
    """
    OpenProject node for managing work packages and projects
    Following the OpenProject REST API v3:
    - https://www.openproject.org/docs/api/endpoints/work-packages/
    - https://www.openproject.org/docs/api/endpoints/projects/
    """

    type = "openProject"
    version = 1.0

    description = {
        "displayName": "OpenProject",
        "name": "openProject",
        "icon": "file:openproject.svg",
        "group": ["transform"],
        "description": "Interact with OpenProject API for work packages and projects",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }

    properties = {
        "credentials": [
            {
                "name": "openProjectApi",
                "required": True,
                "displayName": "OpenProject API",
            }
        ],
        "parameters": [
            # Resource selection
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Work Package", "value": "workPackage"},
                    {"name": "Project", "value": "project"},
                ],
                "default": "workPackage",
                "description": "The resource to operate on",
            },
            
            # ========== WORK PACKAGE OPERATIONS ==========
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "List Work Packages", "value": "list", "description": "Get a collection of work packages"},
                    {"name": "Get Work Package", "value": "get", "description": "Get a single work package by ID"},
                    {"name": "Create Work Package", "value": "create", "description": "Create a new work package"},
                    {"name": "Update Work Package", "value": "update", "description": "Update an existing work package"},
                    {"name": "Delete Work Package", "value": "delete", "description": "Delete a work package"},
                    {"name": "Get Work Package Form", "value": "form", "description": "Get form configuration for work package"},
                    {"name": "Get Work Package Schema", "value": "schema", "description": "Get schema for work package"},
                    {"name": "Get Work Package Activities", "value": "activities", "description": "Get activities of a work package"},
                ],
                "default": "list",
                "display_options": {"show": {"resource": ["workPackage"]}},
            },
            
            # ========== PROJECT OPERATIONS ==========
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "List Projects", "value": "list", "description": "Get a collection of projects"},
                    {"name": "Get Project", "value": "get", "description": "Get a single project by ID"},
                    {"name": "Create Project", "value": "create", "description": "Create a new project"},
                    {"name": "Update Project", "value": "update", "description": "Update an existing project"},
                    {"name": "Delete Project", "value": "delete", "description": "Delete a project"},
                    {"name": "Create Work Package in Project", "value": "createWorkPackage", "description": "Create a work package in a specific project"},
                ],
                "default": "list",
                "display_options": {"show": {"resource": ["project"]}},
            },
            
            # ========== WORK PACKAGE PARAMETERS ==========
            
            # Work Package ID (for get, update, delete, activities)
            {
                "name": "workPackageId",
                "type": NodeParameterType.STRING,
                "display_name": "Work Package ID",
                "default": "",
                "required": True,
                "description": "The ID of the work package",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["get", "update", "delete", "form", "activities"]
                    }
                },
            },
            
            # List filters
            {
                "name": "filters",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Advanced Filters",
                "default": {},
                "options": [
                    {
                        "name": "conditions",
                        "type": NodeParameterType.ARRAY,
                        "display_name": "Filter Conditions",
                        "default": [],
                        "type_options": {
                            "multipleValues": True
                        },
                        "options": [
                            {
                                "name": "field",
                                "type": NodeParameterType.OPTIONS,
                                "display_name": "Field",
                                "options": [
                                    {"name": "Subject or ID", "value": "subjectOrId"},
                                    {"name": "Subject", "value": "subject"},
                                    {"name": "ID", "value": "id"},
                                    {"name": "Status", "value": "status"},
                                    {"name": "Type", "value": "type"},
                                    {"name": "Priority", "value": "priority"},
                                    {"name": "Assignee", "value": "assignee"},
                                    {"name": "Author", "value": "author"},
                                    {"name": "Responsible", "value": "responsible"},
                                    {"name": "Project", "value": "project"},
                                    {"name": "Parent", "value": "parent"},
                                    {"name": "Category", "value": "category"},
                                    {"name": "Version", "value": "version"},
                                    {"name": "Start Date", "value": "startDate"},
                                    {"name": "Due Date", "value": "dueDate"},
                                    {"name": "Estimated Time", "value": "estimatedTime"},
                                    {"name": "Spent Time", "value": "spentTime"},
                                    {"name": "Percentage Done", "value": "percentageDone"},
                                    {"name": "Created At", "value": "createdAt"},
                                    {"name": "Updated At", "value": "updatedAt"}
                                ],
                                "default": "status",
                                "description": "Field to filter on"
                            },
                            {
                                "name": "operator",
                                "type": NodeParameterType.OPTIONS,
                                "display_name": "Operator",
                                "options": [
                                    {"name": "Equal (=)", "value": "="},
                                    {"name": "Not Equal (!)", "value": "!"},
                                    {"name": "Contains All (&=)", "value": "&="},
                                    {"name": "Contains (~)", "value": "~"},
                                    {"name": "Not Contains (!~)", "value": "!~"},
                                    {"name": "Greater or Equal (>=)", "value": ">="},
                                    {"name": "Less or Equal (<=)", "value": "<="},
                                    {"name": "Search All (**)", "value": "**"},
                                    {"name": "Is Set (*)", "value": "*"},
                                    {"name": "Is Not Set (!*)", "value": "!*"},
                                    {"name": "Status Open (o)", "value": "o"},
                                    {"name": "Status Closed (c)", "value": "c"}
                                ],
                                "default": "="
                            },
                            {
                                "name": "values",
                                "type": NodeParameterType.STRING,
                                "display_name": "Values",
                                "default": "",
                                "description": "Comma-separated values (e.g., '1,2,3' for IDs or 't' for true, 'f' for false)"
                            }
                        ]
                    }
                ],
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["list"]
                    }
                },
            },
            
            {
                "name": "pageSize",
                "type": NodeParameterType.NUMBER,
                "display_name": "Page Size",
                "default": 20,
                "required": False,
                "description": "Number of items to return per page",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["list"]
                    }
                },
            },
            
            {
                "name": "offset",
                "type": NodeParameterType.NUMBER,
                "display_name": "Offset",
                "default": 1,
                "required": False,
                "description": "Page number to return (1-based)",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["list"]
                    }
                },
            },
            
            # Work Package Create/Update fields
            {
                "name": "subject",
                "type": NodeParameterType.STRING,
                "display_name": "Subject",
                "default": "",
                "required": True,
                "description": "The subject/title of the work package",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "projectId",
                "type": NodeParameterType.STRING,
                "display_name": "Project ID",
                "default": "",
                "required": True,
                "description": "The ID of the project",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create"]
                    }
                },
            },
            
            {
                "name": "typeId",
                "type": NodeParameterType.STRING,
                "display_name": "Type ID",
                "default": "",
                "required": False,
                "description": "The ID of the work package type",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "description",
                "type": NodeParameterType.STRING,
                "display_name": "Description",
                "default": "",
                "required": False,
                "type_options": {"rows": 4},
                "description": "Description of the work package (supports HTML)",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "statusId",
                "type": NodeParameterType.STRING,
                "display_name": "Status ID",
                "default": "",
                "required": False,
                "description": "The ID of the status",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "priorityId",
                "type": NodeParameterType.STRING,
                "display_name": "Priority ID",
                "default": "",
                "required": False,
                "description": "The ID of the priority",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "assigneeId",
                "type": NodeParameterType.STRING,
                "display_name": "Assignee ID",
                "default": "",
                "required": False,
                "description": "The ID of the user to assign to",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "startDate",
                "type": NodeParameterType.STRING,
                "display_name": "Start Date",
                "default": "",
                "required": False,
                "placeholder": "YYYY-MM-DD",
                "description": "Start date in ISO 8601 format",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "dueDate",
                "type": NodeParameterType.STRING,
                "display_name": "Due Date",
                "default": "",
                "required": False,
                "placeholder": "YYYY-MM-DD",
                "description": "Due date in ISO 8601 format",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "estimatedTime",
                "type": NodeParameterType.STRING,
                "display_name": "Estimated Time",
                "default": "",
                "required": False,
                "placeholder": "PT8H",
                "description": "Estimated time in ISO 8601 duration format (e.g., PT8H for 8 hours)",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "additionalFields",
                "type": NodeParameterType.JSON,
                "display_name": "Additional Fields",
                "default": "{}",
                "required": False,
                "description": "Additional fields as JSON object",
                "display_options": {
                    "show": {
                        "resource": ["workPackage"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            # ========== PROJECT PARAMETERS ==========
            
            # Project ID (for get, update, delete)
            {
                "name": "projectIdParam",
                "type": NodeParameterType.STRING,
                "display_name": "Project ID",
                "default": "",
                "required": True,
                "description": "The ID or identifier of the project",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["get", "update", "delete", "createWorkPackage"]
                    }
                },
            },
            
            # Project list filters
            {
                "name": "projectFilters",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Advanced Filters",
                "default": {},
                "options": [
                    {
                        "name": "conditions",
                        "type": NodeParameterType.ARRAY,
                        "display_name": "Filter Conditions",
                        "default": [],
                        "type_options": {
                            "multipleValues": True
                        },
                        "options": [
                            {
                                "name": "field",
                                "type": NodeParameterType.OPTIONS,
                                "display_name": "Field",
                                "options": [
                                    {"name": "Name or Identifier", "value": "nameAndIdentifier"},
                                    {"name": "Name", "value": "name"},
                                    {"name": "Identifier", "value": "identifier"},
                                    {"name": "ID", "value": "id"},
                                    {"name": "Active", "value": "active"},
                                    {"name": "Public", "value": "public"},
                                    {"name": "Type", "value": "type"},
                                    {"name": "Type or Ancestor", "value": "typeOr"},
                                    {"name": "Ancestor", "value": "ancestor"},
                                    {"name": "Created At", "value": "createdAt"},
                                    {"name": "Updated At", "value": "updatedAt"},
                                    {"name": "Principal", "value": "principal"}
                                ],
                                "default": "active",
                                "description": "Field to filter on"
                            },
                            {
                                "name": "operator",
                                "type": NodeParameterType.OPTIONS,
                                "display_name": "Operator",
                                "options": [
                                    {"name": "Equal (=)", "value": "="},
                                    {"name": "Not Equal (!)", "value": "!"},
                                    {"name": "Contains (~)", "value": "~"},
                                    {"name": "Not Contains (!~)", "value": "!~"},
                                    {"name": "Search All (**)", "value": "**"},
                                    {"name": "Is Set (*)", "value": "*"},
                                    {"name": "Is Not Set (!*)", "value": "!*"}
                                ],
                                "default": "="
                            },
                            {
                                "name": "values",
                                "type": NodeParameterType.STRING,
                                "display_name": "Values",
                                "default": "",
                                "description": "Comma-separated values (use 't' for true, 'f' for false for boolean fields)"
                            }
                        ]
                    }
                ],
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["list"]
                    }
                },
            },
            
            {
                "name": "projectPageSize",
                "type": NodeParameterType.NUMBER,
                "display_name": "Page Size",
                "default": 20,
                "required": False,
                "description": "Number of items to return per page",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["list"]
                    }
                },
            },
            
            {
                "name": "projectOffset",
                "type": NodeParameterType.NUMBER,
                "display_name": "Offset",
                "default": 1,
                "required": False,
                "description": "Page number to return (1-based)",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["list"]
                    }
                },
            },
            
            # Project Create/Update fields
            {
                "name": "projectName",
                "type": NodeParameterType.STRING,
                "display_name": "Name",
                "default": "",
                "required": True,
                "description": "The name of the project",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "projectIdentifier",
                "type": NodeParameterType.STRING,
                "display_name": "Identifier",
                "default": "",
                "required": True,
                "description": "Unique identifier for the project (lowercase, no spaces)",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["create"]
                    }
                },
            },
            
            {
                "name": "projectDescription",
                "type": NodeParameterType.STRING,
                "display_name": "Description",
                "default": "",
                "required": False,
                "type_options": {"rows": 4},
                "description": "Description of the project",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "projectPublic",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Public",
                "default": False,
                "required": False,
                "description": "Whether the project is publicly visible",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "projectActive",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Active",
                "default": True,
                "required": False,
                "description": "Whether the project is active",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "projectStatusCode",
                "type": NodeParameterType.STRING,
                "display_name": "Status Code",
                "default": "",
                "required": False,
                "description": "Status code of the project",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "projectStatusExplanation",
                "type": NodeParameterType.STRING,
                "display_name": "Status Explanation",
                "default": "",
                "required": False,
                "type_options": {"rows": 3},
                "description": "Explanation of the project status",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "projectParentId",
                "type": NodeParameterType.STRING,
                "display_name": "Parent Project ID",
                "default": "",
                "required": False,
                "description": "ID of the parent project (for sub-projects)",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            {
                "name": "projectAdditionalFields",
                "type": NodeParameterType.JSON,
                "display_name": "Additional Fields",
                "default": "{}",
                "required": False,
                "description": "Additional fields as JSON object",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["create", "update"]
                    }
                },
            },
            
            # Work Package creation in project
            {
                "name": "wpSubject",
                "type": NodeParameterType.STRING,
                "display_name": "Subject",
                "default": "",
                "required": True,
                "description": "The subject/title of the work package",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["createWorkPackage"]
                    }
                },
            },
            
            {
                "name": "wpTypeId",
                "type": NodeParameterType.STRING,
                "display_name": "Type ID",
                "default": "",
                "required": False,
                "description": "The ID of the work package type",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["createWorkPackage"]
                    }
                },
            },
            
            {
                "name": "wpDescription",
                "type": NodeParameterType.STRING,
                "display_name": "Description",
                "default": "",
                "required": False,
                "type_options": {"rows": 4},
                "description": "Description of the work package",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["createWorkPackage"]
                    }
                },
            },
            
            {
                "name": "wpAdditionalFields",
                "type": NodeParameterType.JSON,
                "display_name": "Additional Fields",
                "default": "{}",
                "required": False,
                "description": "Additional work package fields as JSON object",
                "display_options": {
                    "show": {
                        "resource": ["project"],
                        "operation": ["createWorkPackage"]
                    }
                },
            },
        ],
    }

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute the OpenProject node operation"""
        try:
            result_items = []
            input_data = self.get_input_data()
            items = input_data or [NodeExecutionData(json_data={}, binary_data=None)]

            for i in range(len(items)):
                try:
                    resource = self.get_node_parameter("resource", i, "workPackage")
                    operation = self.get_node_parameter("operation", i, "list")

                    # Execute the appropriate operation
                    if resource == "workPackage":
                        result = self._execute_work_package_operation(operation, i)
                    elif resource == "project":
                        result = self._execute_project_operation(operation, i)
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")

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
                    logger.error(f"Error executing OpenProject operation: {str(e)}")
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter("resource", i, "workPackage"),
                            "operation": self.get_node_parameter("operation", i, "list"),
                            "item_index": i,
                        },
                        binary_data=None,
                    )
                    result_items.append(error_item)

            return [result_items]

        except Exception as e:
            logger.error(f"Error in OpenProject node: {str(e)}")
            error_data = [
                NodeExecutionData(
                    json_data={"error": f"Error in OpenProject node: {str(e)}"},
                    binary_data=None,
                )
            ]
            return [error_data]

    def _execute_work_package_operation(self, operation: str, item_index: int) -> Any:
        """Execute work package operations"""
        if operation == "list":
            return self._list_work_packages(item_index)
        elif operation == "get":
            return self._get_work_package(item_index)
        elif operation == "create":
            return self._create_work_package(item_index)
        elif operation == "update":
            return self._update_work_package(item_index)
        elif operation == "delete":
            return self._delete_work_package(item_index)
        elif operation == "form":
            return self._get_work_package_form(item_index)
        elif operation == "schema":
            return self._get_work_package_schema(item_index)
        elif operation == "activities":
            return self._get_work_package_activities(item_index)
        else:
            raise ValueError(f"Unsupported work package operation '{operation}'")

    def _execute_project_operation(self, operation: str, item_index: int) -> Any:
        """Execute project operations"""
        if operation == "list":
            return self._list_projects(item_index)
        elif operation == "get":
            return self._get_project(item_index)
        elif operation == "create":
            return self._create_project(item_index)
        elif operation == "update":
            return self._update_project(item_index)
        elif operation == "delete":
            return self._delete_project(item_index)
        elif operation == "createWorkPackage":
            return self._create_work_package_in_project(item_index)
        else:
            raise ValueError(f"Unsupported project operation '{operation}'")

    def _get_base_url(self) -> str:
        """Get OpenProject base URL from credentials"""
        credentials = self.get_credentials("openProjectApi")
        if not credentials:
            raise ValueError("OpenProject credentials not found")
        
        base_url = credentials.get("baseUrl", "").rstrip('/')
        if not base_url:
            raise ValueError("Base URL is required")
        
        return base_url

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers with Basic Auth"""
        credentials = self.get_credentials("openProjectApi")
        if not credentials:
            raise ValueError("OpenProject credentials not found")
        
        api_key = credentials.get("apiKey", "")
        if not api_key:
            raise ValueError("API Key is required")
        
        # Create Basic Auth: base64(apikey:API_KEY)
        # Username is literal "apikey", password is the API key
        auth_string = f"apikey:{api_key}"
        encoded = base64.b64encode(auth_string.encode()).decode()
        
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to OpenProject API"""
        base_url = self._get_base_url()
        headers = self._get_auth_headers()
        url = f"{base_url}/api/v3{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, params=params)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data, params=params)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle responses
            if response.status_code == 204:  # No Content
                return {"success": True, "message": "Operation completed successfully"}
            
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"success": True, "response": response.text}
                
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error: {e}"
            try:
                error_data = e.response.json()
                error_msg = f"HTTP {e.response.status_code}: {error_data.get('message', str(e))}"
            except:
                pass
            raise ValueError(error_msg)
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Request failed: {str(e)}")

    # ========== WORK PACKAGE METHODS ==========

    def _build_openproject_filters(self, filters_collection: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build OpenProject API filters from collection parameter.
        OpenProject format: [{"field": {"operator": "value", "values": ["val1", "val2"]}}]
        """
        if not filters_collection or not isinstance(filters_collection, dict):
            return []
        
        conditions = filters_collection.get("conditions", [])
        if not conditions:
            return []
        
        openproject_filters = []
        
        for condition in conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "=")
            values_str = condition.get("values", "")
            
            if not field:
                continue
            
            # Parse values - split by comma and strip whitespace
            if values_str:
                values = [v.strip() for v in values_str.split(",") if v.strip()]
            else:
                values = []
            
            # Build OpenProject filter structure
            filter_obj = {
                field: {
                    "operator": operator,
                    "values": values
                }
            }
            openproject_filters.append(filter_obj)
        
        return openproject_filters

    def _list_work_packages(self, item_index: int) -> List[Dict[str, Any]]:
        """List work packages with optional filters"""
        params = {}
        
        # Handle filters from collection parameter
        filters_collection = self.get_node_parameter("filters", item_index, {})
        if filters_collection and isinstance(filters_collection, dict):
            openproject_filters = self._build_openproject_filters(filters_collection)
            if openproject_filters:
                params["filters"] = json.dumps(openproject_filters)
        
        # Pagination
        page_size = self.get_node_parameter("pageSize", item_index, 20)
        offset = self.get_node_parameter("offset", item_index, 1)
        params["pageSize"] = page_size
        params["offset"] = offset
        
        response = self._make_request("GET", "/work_packages", params=params)
        
        # Extract embedded work packages
        work_packages = response.get("_embedded", {}).get("elements", [])
        return work_packages

    def _get_work_package(self, item_index: int) -> Dict[str, Any]:
        """Get a single work package by ID"""
        wp_id = self.get_node_parameter("workPackageId", item_index)
        if not wp_id:
            raise ValueError("Work Package ID is required")
        
        return self._make_request("GET", f"/work_packages/{wp_id}")

    def _create_work_package(self, item_index: int) -> Dict[str, Any]:
        """Create a new work package"""
        subject = self.get_node_parameter("subject", item_index)
        project_id = self.get_node_parameter("projectId", item_index)
        
        if not subject:
            raise ValueError("Subject is required")
        if not project_id:
            raise ValueError("Project ID is required")
        
        # Build work package data
        data = {
            "subject": subject,
            "_links": {
                "project": {
                    "href": f"/api/v3/projects/{project_id}"
                }
            }
        }
        
        # Optional fields
        type_id = self.get_node_parameter("typeId", item_index, "")
        if type_id:
            data["_links"]["type"] = {"href": f"/api/v3/types/{type_id}"}
        
        status_id = self.get_node_parameter("statusId", item_index, "")
        if status_id:
            data["_links"]["status"] = {"href": f"/api/v3/statuses/{status_id}"}
        
        priority_id = self.get_node_parameter("priorityId", item_index, "")
        if priority_id:
            data["_links"]["priority"] = {"href": f"/api/v3/priorities/{priority_id}"}
        
        assignee_id = self.get_node_parameter("assigneeId", item_index, "")
        if assignee_id:
            data["_links"]["assignee"] = {"href": f"/api/v3/users/{assignee_id}"}
        
        description = self.get_node_parameter("description", item_index, "")
        if description:
            data["description"] = {
                "format": "textile",
                "raw": description
            }
        
        start_date = self.get_node_parameter("startDate", item_index, "")
        if start_date:
            data["startDate"] = start_date
        
        due_date = self.get_node_parameter("dueDate", item_index, "")
        if due_date:
            data["dueDate"] = due_date
        
        estimated_time = self.get_node_parameter("estimatedTime", item_index, "")
        if estimated_time:
            data["estimatedTime"] = estimated_time
        
        # Additional fields
        additional_fields_str = self.get_node_parameter("additionalFields", item_index, "{}")
        if additional_fields_str:
            try:
                additional = json.loads(additional_fields_str) if isinstance(additional_fields_str, str) else additional_fields_str
                data.update(additional)
            except json.JSONDecodeError:
                logger.warning("Invalid additional fields JSON, ignoring")
        
        return self._make_request("POST", "/work_packages", data=data)

    def _update_work_package(self, item_index: int) -> Dict[str, Any]:
        """Update an existing work package"""
        wp_id = self.get_node_parameter("workPackageId", item_index)
        if not wp_id:
            raise ValueError("Work Package ID is required")
        
        # Build update data
        data = {}
        
        subject = self.get_node_parameter("subject", item_index, "")
        if subject:
            data["subject"] = subject
        
        type_id = self.get_node_parameter("typeId", item_index, "")
        if type_id:
            if "_links" not in data:
                data["_links"] = {}
            data["_links"]["type"] = {"href": f"/api/v3/types/{type_id}"}
        
        status_id = self.get_node_parameter("statusId", item_index, "")
        if status_id:
            if "_links" not in data:
                data["_links"] = {}
            data["_links"]["status"] = {"href": f"/api/v3/statuses/{status_id}"}
        
        priority_id = self.get_node_parameter("priorityId", item_index, "")
        if priority_id:
            if "_links" not in data:
                data["_links"] = {}
            data["_links"]["priority"] = {"href": f"/api/v3/priorities/{priority_id}"}
        
        assignee_id = self.get_node_parameter("assigneeId", item_index, "")
        if assignee_id:
            if "_links" not in data:
                data["_links"] = {}
            data["_links"]["assignee"] = {"href": f"/api/v3/users/{assignee_id}"}
        
        description = self.get_node_parameter("description", item_index, "")
        if description:
            data["description"] = {
                "format": "textile",
                "raw": description
            }
        
        start_date = self.get_node_parameter("startDate", item_index, "")
        if start_date:
            data["startDate"] = start_date
        
        due_date = self.get_node_parameter("dueDate", item_index, "")
        if due_date:
            data["dueDate"] = due_date
        
        estimated_time = self.get_node_parameter("estimatedTime", item_index, "")
        if estimated_time:
            data["estimatedTime"] = estimated_time
        
        # Additional fields
        additional_fields_str = self.get_node_parameter("additionalFields", item_index, "{}")
        if additional_fields_str:
            try:
                additional = json.loads(additional_fields_str) if isinstance(additional_fields_str, str) else additional_fields_str
                data.update(additional)
            except json.JSONDecodeError:
                logger.warning("Invalid additional fields JSON, ignoring")
        
        if not data:
            raise ValueError("No fields to update")
        
        return self._make_request("PATCH", f"/work_packages/{wp_id}", data=data)

    def _delete_work_package(self, item_index: int) -> Dict[str, Any]:
        """Delete a work package"""
        wp_id = self.get_node_parameter("workPackageId", item_index)
        if not wp_id:
            raise ValueError("Work Package ID is required")
        
        return self._make_request("DELETE", f"/work_packages/{wp_id}")

    def _get_work_package_form(self, item_index: int) -> Dict[str, Any]:
        """Get work package form configuration"""
        wp_id = self.get_node_parameter("workPackageId", item_index)
        if not wp_id:
            raise ValueError("Work Package ID is required")
        
        return self._make_request("GET", f"/work_packages/{wp_id}/form")

    def _get_work_package_schema(self, item_index: int) -> Dict[str, Any]:
        """Get work package schema"""
        wp_id = self.get_node_parameter("workPackageId", item_index)
        if not wp_id:
            raise ValueError("Work Package ID is required")
        
        return self._make_request("GET", f"/work_packages/{wp_id}/schema")

    def _get_work_package_activities(self, item_index: int) -> List[Dict[str, Any]]:
        """Get activities of a work package"""
        wp_id = self.get_node_parameter("workPackageId", item_index)
        if not wp_id:
            raise ValueError("Work Package ID is required")
        
        response = self._make_request("GET", f"/work_packages/{wp_id}/activities")
        
        # Extract embedded activities
        activities = response.get("_embedded", {}).get("elements", [])
        return activities

    # ========== PROJECT METHODS ==========

    def _list_projects(self, item_index: int) -> List[Dict[str, Any]]:
        """List projects with optional filters"""
        params = {}
        
        # Handle filters from collection parameter
        filters_collection = self.get_node_parameter("projectFilters", item_index, {})
        if filters_collection and isinstance(filters_collection, dict):
            openproject_filters = self._build_openproject_filters(filters_collection)
            if openproject_filters:
                params["filters"] = json.dumps(openproject_filters)
        
        # Pagination
        page_size = self.get_node_parameter("projectPageSize", item_index, 20)
        offset = self.get_node_parameter("projectOffset", item_index, 1)
        params["pageSize"] = page_size
        params["offset"] = offset
        
        response = self._make_request("GET", "/projects", params=params)
        
        # Extract embedded projects
        projects = response.get("_embedded", {}).get("elements", [])
        return projects

    def _get_project(self, item_index: int) -> Dict[str, Any]:
        """Get a single project by ID"""
        project_id = self.get_node_parameter("projectIdParam", item_index)
        if not project_id:
            raise ValueError("Project ID is required")
        
        return self._make_request("GET", f"/projects/{project_id}")

    def _create_project(self, item_index: int) -> Dict[str, Any]:
        """Create a new project"""
        name = self.get_node_parameter("projectName", item_index)
        identifier = self.get_node_parameter("projectIdentifier", item_index)
        
        if not name:
            raise ValueError("Project name is required")
        if not identifier:
            raise ValueError("Project identifier is required")
        
        # Build project data
        data = {
            "name": name,
            "identifier": identifier
        }
        
        # Optional fields
        description = self.get_node_parameter("projectDescription", item_index, "")
        if description:
            data["description"] = {
                "format": "textile",
                "raw": description
            }
        
        public = self.get_node_parameter("projectPublic", item_index, False)
        data["public"] = public
        
        active = self.get_node_parameter("projectActive", item_index, True)
        data["active"] = active
        
        status_code = self.get_node_parameter("projectStatusCode", item_index, "")
        if status_code:
            data["statusExplanation"] = {
                "format": "textile",
                "raw": self.get_node_parameter("projectStatusExplanation", item_index, "")
            }
        
        parent_id = self.get_node_parameter("projectParentId", item_index, "")
        if parent_id:
            data["_links"] = {
                "parent": {"href": f"/api/v3/projects/{parent_id}"}
            }
        
        # Additional fields
        additional_fields_str = self.get_node_parameter("projectAdditionalFields", item_index, "{}")
        if additional_fields_str:
            try:
                additional = json.loads(additional_fields_str) if isinstance(additional_fields_str, str) else additional_fields_str
                data.update(additional)
            except json.JSONDecodeError:
                logger.warning("Invalid additional fields JSON, ignoring")
        
        return self._make_request("POST", "/projects", data=data)

    def _update_project(self, item_index: int) -> Dict[str, Any]:
        """Update an existing project"""
        project_id = self.get_node_parameter("projectIdParam", item_index)
        if not project_id:
            raise ValueError("Project ID is required")
        
        # Build update data
        data = {}
        
        name = self.get_node_parameter("projectName", item_index, "")
        if name:
            data["name"] = name
        
        description = self.get_node_parameter("projectDescription", item_index, "")
        if description:
            data["description"] = {
                "format": "textile",
                "raw": description
            }
        
        public = self.get_node_parameter("projectPublic", item_index, None)
        if public is not None:
            data["public"] = public
        
        active = self.get_node_parameter("projectActive", item_index, None)
        if active is not None:
            data["active"] = active
        
        status_code = self.get_node_parameter("projectStatusCode", item_index, "")
        if status_code:
            data["statusExplanation"] = {
                "format": "textile",
                "raw": self.get_node_parameter("projectStatusExplanation", item_index, "")
            }
        
        parent_id = self.get_node_parameter("projectParentId", item_index, "")
        if parent_id:
            data["_links"] = {
                "parent": {"href": f"/api/v3/projects/{parent_id}"}
            }
        
        # Additional fields
        additional_fields_str = self.get_node_parameter("projectAdditionalFields", item_index, "{}")
        if additional_fields_str:
            try:
                additional = json.loads(additional_fields_str) if isinstance(additional_fields_str, str) else additional_fields_str
                data.update(additional)
            except json.JSONDecodeError:
                logger.warning("Invalid additional fields JSON, ignoring")
        
        if not data:
            raise ValueError("No fields to update")
        
        return self._make_request("PATCH", f"/projects/{project_id}", data=data)

    def _delete_project(self, item_index: int) -> Dict[str, Any]:
        """Delete a project"""
        project_id = self.get_node_parameter("projectIdParam", item_index)
        if not project_id:
            raise ValueError("Project ID is required")
        
        return self._make_request("DELETE", f"/projects/{project_id}")

    def _create_work_package_in_project(self, item_index: int) -> Dict[str, Any]:
        """Create a work package in a specific project"""
        project_id = self.get_node_parameter("projectIdParam", item_index)
        subject = self.get_node_parameter("wpSubject", item_index)
        
        if not project_id:
            raise ValueError("Project ID is required")
        if not subject:
            raise ValueError("Subject is required")
        
        # Build work package data
        data = {
            "subject": subject
        }
        
        # Optional fields
        type_id = self.get_node_parameter("wpTypeId", item_index, "")
        if type_id:
            if "_links" not in data:
                data["_links"] = {}
            data["_links"]["type"] = {"href": f"/api/v3/types/{type_id}"}
        
        description = self.get_node_parameter("wpDescription", item_index, "")
        if description:
            data["description"] = {
                "format": "textile",
                "raw": description
            }
        
        # Additional fields
        additional_fields_str = self.get_node_parameter("wpAdditionalFields", item_index, "{}")
        if additional_fields_str:
            try:
                additional = json.loads(additional_fields_str) if isinstance(additional_fields_str, str) else additional_fields_str
                data.update(additional)
            except json.JSONDecodeError:
                logger.warning("Invalid additional fields JSON, ignoring")
        
        return self._make_request("POST", f"/projects/{project_id}/work_packages", data=data)
