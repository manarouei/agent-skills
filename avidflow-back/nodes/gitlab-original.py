"""
GitLab node for interacting with GitLab repositories and resources.
Supports operations on issues, files, releases, repositories, and users.
"""
import requests
import json
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, quote
from models import NodeExecutionData
from utils.serialization import deep_serialize

from .base import BaseNode, NodeParameterType

# Set up logging
logger = logging.getLogger(__name__)


class GitLabNode(BaseNode):
    """GitLab node implementation"""
    
    type = "gitlab"
    version = 1
    
    description = {
        "displayName": "GitLab",
        "name": "gitlab",
        "group": ["transform"],
        "subtitle": "={{$parameter['operation'] + ': ' + $parameter['resource']}}",
        "description": "Interact with GitLab repositories, issues, files, releases, and users",
        "inputs": [
            {"name": "main", "type": "main", "required": True}
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True}
        ],
    }
    
    properties = {
        "credentials": [
            {
                "name": "gitlabApi",
                "required": True,
            }
        ],
        "parameters": [
            {
                "name": "resource",
                "displayName": "Resource",
                "type": NodeParameterType.OPTIONS,
                "options": [
                    {"name": "Issue", "value": "issue"},
                    {"name": "File", "value": "file"},
                    {"name": "Release", "value": "release"},
                    {"name": "Repository", "value": "repository"},
                    {"name": "User", "value": "user"}
                ],
                "default": "issue",
                "required": True,
                "description": "The GitLab resource to operate on"
            },
            {
                "name": "operation",
                "displayName": "Operation",
                "type": NodeParameterType.OPTIONS,
                "options": [
                    {"name": "Get", "value": "get"},
                    {"name": "Get All", "value": "getAll"},
                    {"name": "Create", "value": "create"},
                    {"name": "Update", "value": "update"},
                    {"name": "Delete", "value": "delete"}
                ],
                "default": "get",
                "required": True,
                "description": "The operation to perform"
            },
            {
                "name": "projectId",
                "displayName": "Project ID",
                "type": NodeParameterType.STRING,
                "required": True,
                "description": "GitLab project ID or path (e.g., 'group/project' or '123')",
                "displayOptions": {
                    "show": {
                        "resource": ["issue", "file", "release", "repository"]
                    }
                }
            },
            {
                "name": "issueIid",
                "displayName": "Issue IID",
                "type": NodeParameterType.NUMBER,
                "required": True,
                "description": "The internal ID of the issue within the project",
                "displayOptions": {
                    "show": {
                        "resource": ["issue"],
                        "operation": ["get", "update", "delete"]
                    }
                }
            },
            {
                "name": "issueTitle",
                "displayName": "Title",
                "type": NodeParameterType.STRING,
                "required": True,
                "description": "Issue title",
                "displayOptions": {
                    "show": {
                        "resource": ["issue"],
                        "operation": ["create", "update"]
                    }
                }
            },
            {
                "name": "issueDescription",
                "displayName": "Description",
                "type": NodeParameterType.STRING,
                "required": False,
                "description": "Issue description",
                "displayOptions": {
                    "show": {
                        "resource": ["issue"],
                        "operation": ["create", "update"]
                    }
                }
            },
            {
                "name": "filePath",
                "displayName": "File Path",
                "type": NodeParameterType.STRING,
                "required": True,
                "description": "Path to the file in the repository",
                "displayOptions": {
                    "show": {
                        "resource": ["file"]
                    }
                }
            },
            {
                "name": "fileContent",
                "displayName": "Content",
                "type": NodeParameterType.STRING,
                "required": True,
                "description": "File content",
                "displayOptions": {
                    "show": {
                        "resource": ["file"],
                        "operation": ["create", "update"]
                    }
                }
            },
            {
                "name": "commitMessage",
                "displayName": "Commit Message",
                "type": NodeParameterType.STRING,
                "required": True,
                "description": "Commit message for file operations",
                "displayOptions": {
                    "show": {
                        "resource": ["file"],
                        "operation": ["create", "update", "delete"]
                    }
                }
            },
            {
                "name": "branch",
                "displayName": "Branch",
                "type": NodeParameterType.STRING,
                "default": "main",
                "required": False,
                "description": "Branch name (defaults to 'main')",
                "displayOptions": {
                    "show": {
                        "resource": ["file"]
                    }
                }
            },
            {
                "name": "tagName",
                "displayName": "Tag Name",
                "type": NodeParameterType.STRING,
                "required": True,
                "description": "Release tag name",
                "displayOptions": {
                    "show": {
                        "resource": ["release"],
                        "operation": ["get", "create", "update", "delete"]
                    }
                }
            },
            {
                "name": "releaseName",
                "displayName": "Release Name",
                "type": NodeParameterType.STRING,
                "required": False,
                "description": "Release name/title",
                "displayOptions": {
                    "show": {
                        "resource": ["release"],
                        "operation": ["create", "update"]
                    }
                }
            },
            {
                "name": "releaseDescription",
                "displayName": "Description",
                "type": NodeParameterType.STRING,
                "required": False,
                "description": "Release description",
                "displayOptions": {
                    "show": {
                        "resource": ["release"],
                        "operation": ["create", "update"]
                    }
                }
            },
            {
                "name": "userId",
                "displayName": "User ID",
                "type": NodeParameterType.STRING,
                "required": True,
                "description": "GitLab user ID or username",
                "displayOptions": {
                    "show": {
                        "resource": ["user"],
                        "operation": ["get"]
                    }
                }
            },
            {
                "name": "limit",
                "displayName": "Limit",
                "type": NodeParameterType.NUMBER,
                "default": 20,
                "required": False,
                "description": "Maximum number of items to return",
                "displayOptions": {
                    "show": {
                        "operation": ["getAll"]
                    }
                }
            }
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute the GitLab node"""
        output_items = []
        input_data = self.get_input_data()
        
        for i, item in enumerate(input_data):
            try:
                # Get parameters
                resource = self.get_node_parameter("resource", i)
                operation = self.get_node_parameter("operation", i)
                
                # Get credential
                credential = self.get_credentials("gitlabApi")
                if not credential:
                    raise Exception("GitLab API credential not found")
                
                # Get server URL and auth headers
                server_url = credential.get("server", "https://gitlab.com").rstrip("/")
                access_token = credential.get("accessToken")
                if not access_token:
                    raise Exception("Access token not found in credentials")
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                
                result = None
                
                if resource == "issue":
                    result = self._handle_issue_operations(
                        operation, i, headers, server_url
                    )
                elif resource == "file":
                    result = self._handle_file_operations(
                        operation, i, headers, server_url
                    )
                elif resource == "release":
                    result = self._handle_release_operations(
                        operation, i, headers, server_url
                    )
                elif resource == "repository":
                    result = self._handle_repository_operations(
                        operation, i, headers, server_url
                    )
                elif resource == "user":
                    result = self._handle_user_operations(
                        operation, i, headers, server_url
                    )
                else:
                    raise Exception(f"Unknown resource: {resource}")
                
                # Process the result - handle both single items and arrays
                if isinstance(result, list):
                    if len(result) == 0:
                        # For empty arrays, create a single item indicating successful but empty result
                        empty_result = {"message": f"No items found for {operation} operation", "count": 0}
                        serialized_data = deep_serialize(empty_result)
                        output_items.append(NodeExecutionData(json_data=serialized_data))
                    else:
                        for r in result:
                            serialized_data = deep_serialize(r)
                            output_items.append(NodeExecutionData(json_data=serialized_data))
                else:
                    serialized_data = deep_serialize(result)
                    output_items.append(NodeExecutionData(json_data=serialized_data))
                    
            except Exception as e:
                logger.error(f"GitLab node error: {str(e)}")
                error_data = {"error": str(e)}
                serialized_error = deep_serialize(error_data)
                output_items.append(NodeExecutionData(json_data=serialized_error))
        
        return [output_items]
    
    def _handle_issue_operations(self, operation: str, item_index: int, 
                               headers: Dict, server_url: str) -> Any:
        """Handle issue operations"""
        project_id = self.get_node_parameter("projectId", item_index)
        project_id_encoded = quote(str(project_id), safe='')
        
        if operation == "get":
            issue_iid = self.get_node_parameter("issueIid", item_index)
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/issues/{issue_iid}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
                
        elif operation == "getAll":
            limit = self.get_node_parameter("limit", item_index, 20)
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/issues"
            params = {"per_page": limit}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
                
        elif operation == "create":
            title = self.get_node_parameter("issueTitle", item_index)
            description = self.get_node_parameter("issueDescription", item_index, "")
            
            data = {
                "title": title,
                "description": description
            }
            
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/issues"
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
                
        elif operation == "update":
            issue_iid = self.get_node_parameter("issueIid", item_index)
            title = self.get_node_parameter("issueTitle", item_index)
            description = self.get_node_parameter("issueDescription", item_index, "")
            
            data = {
                "title": title,
                "description": description
            }
            
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/issues/{issue_iid}"
            response = requests.put(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
                
        elif operation == "delete":
            issue_iid = self.get_node_parameter("issueIid", item_index)
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/issues/{issue_iid}"
            response = requests.delete(url, headers=headers)
            response.raise_for_status()
            return {"success": True, "message": f"Issue {issue_iid} deleted"}
    
    def _handle_file_operations(self, operation: str, item_index: int,
                              headers: Dict, server_url: str) -> Any:
        """Handle file operations"""
        project_id = self.get_node_parameter("projectId", item_index)
        project_id_encoded = quote(str(project_id), safe='')
        file_path = self.get_node_parameter("filePath", item_index)
        file_path_encoded = quote(file_path, safe='')
        branch = self.get_node_parameter("branch", item_index, "main")
        
        if operation == "get":
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/repository/files/{file_path_encoded}"
            params = {"ref": branch}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
                
        elif operation == "create":
            content = self.get_node_parameter("fileContent", item_index)
            commit_message = self.get_node_parameter("commitMessage", item_index)
            
            data = {
                "branch": branch,
                "content": content,
                "commit_message": commit_message
            }
            
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/repository/files/{file_path_encoded}"
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
                
        elif operation == "update":
            content = self.get_node_parameter("fileContent", item_index)
            commit_message = self.get_node_parameter("commitMessage", item_index)
            
            data = {
                "branch": branch,
                "content": content,
                "commit_message": commit_message
            }
            
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/repository/files/{file_path_encoded}"
            response = requests.put(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
                
        elif operation == "delete":
            commit_message = self.get_node_parameter("commitMessage", item_index)
            
            data = {
                "branch": branch,
                "commit_message": commit_message
            }
            
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/repository/files/{file_path_encoded}"
            response = requests.delete(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
    
    def _handle_release_operations(self, operation: str, item_index: int,
                                 headers: Dict, server_url: str) -> Any:
        """Handle release operations"""
        project_id = self.get_node_parameter("projectId", item_index)
        project_id_encoded = quote(str(project_id), safe='')
        
        if operation == "get":
            tag_name = self.get_node_parameter("tagName", item_index)
            tag_name_encoded = quote(tag_name, safe='')
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/releases/{tag_name_encoded}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
                
        elif operation == "getAll":
            limit = self.get_node_parameter("limit", item_index, 20)
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/releases"
            params = {"per_page": limit}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
                
        elif operation == "create":
            tag_name = self.get_node_parameter("tagName", item_index)
            release_name = self.get_node_parameter("releaseName", item_index, tag_name)
            description = self.get_node_parameter("releaseDescription", item_index, "")
            
            data = {
                "tag_name": tag_name,
                "name": release_name,
                "description": description
            }
            
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/releases"
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
                
        elif operation == "update":
            tag_name = self.get_node_parameter("tagName", item_index)
            tag_name_encoded = quote(tag_name, safe='')
            release_name = self.get_node_parameter("releaseName", item_index, tag_name)
            description = self.get_node_parameter("releaseDescription", item_index, "")
            
            data = {
                "name": release_name,
                "description": description
            }
            
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/releases/{tag_name_encoded}"
            response = requests.put(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
                
        elif operation == "delete":
            tag_name = self.get_node_parameter("tagName", item_index)
            tag_name_encoded = quote(tag_name, safe='')
            url = f"{server_url}/api/v4/projects/{project_id_encoded}/releases/{tag_name_encoded}"
            response = requests.delete(url, headers=headers)
            response.raise_for_status()
            return {"success": True, "message": f"Release {tag_name} deleted"}
    
    def _handle_repository_operations(self, operation: str, item_index: int,
                                    headers: Dict, server_url: str) -> Any:
        """Handle repository operations"""
        if operation == "get":
            project_id = self.get_node_parameter("projectId", item_index)
            project_id_encoded = quote(str(project_id), safe='')
            url = f"{server_url}/api/v4/projects/{project_id_encoded}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
                
        elif operation == "getAll":
            limit = self.get_node_parameter("limit", item_index, 20)
            url = f"{server_url}/api/v4/projects"
            params = {"per_page": limit, "membership": True}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    
    def _handle_user_operations(self, operation: str, item_index: int,
                              headers: Dict, server_url: str) -> Any:
        """Handle user operations"""
        if operation == "get":
            user_id = self.get_node_parameter("userId", item_index)
            url = f"{server_url}/api/v4/users/{user_id}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
                
        elif operation == "getAll":
            limit = self.get_node_parameter("limit", item_index, 20)
            url = f"{server_url}/api/v4/users"
            params = {"per_page": limit}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
