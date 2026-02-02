#!/usr/bin/env python3
"""
Gitlab Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: node-gitlab-comparison-test
Generated: 2026-01-07T08:28:36.689904

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from .base import BaseNode, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class GitlabNode(BaseNode):
    """
    GitLab node.
    
    
    """

    type = "gitlab"
    version = 1
    
    description = {
        "displayName": "GitLab",
        "name": "gitlab",
        "icon": "file:gitlab.svg",
        "group": ['output'],
        "description": "",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }
    
    properties = {
        "parameters": [
            {"name": "resource", "type": NodeParameterType.OPTIONS, "display_name": "Resource", "options": [
                {"name": "File", "value": "file"},
                {"name": "Issue", "value": "issue"},
                {"name": "Release", "value": "release"},
                {"name": "Repository", "value": "repository"},
                {"name": "User", "value": "user"}
            ], "default": "issue", "description": "The resource to operate on"},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create a new issue", "display_options": {'show': {'resource': ['issue', 'release']}}},
                {"name": "Create Comment", "value": "createComment", "description": "Create a new comment on an issue", "display_options": {'show': {'resource': ['issue']}}},
                {"name": "Edit", "value": "edit", "description": "Edit an issue", "display_options": {'show': {'resource': ['issue']}}},
                {"name": "Get", "value": "get", "description": "Get the data of a single issue", "display_options": {'show': {'resource': ['issue', 'file', 'release', 'repository']}}},
                {"name": "Lock", "value": "lock", "description": "Lock an issue", "display_options": {'show': {'resource': ['issue']}}},
                {"name": "Get Issues", "value": "getIssues", "description": "Returns issues of a repository", "display_options": {'show': {'resource': ['repository']}}},
                {"name": "Get Repositories", "value": "getRepositories", "description": "Returns the repositories of a user", "display_options": {'show': {'resource': ['user']}}},
                {"name": "Delete", "value": "delete", "description": "Delete a release", "display_options": {'show': {'resource': ['file', 'release']}}},
                {"name": "Get Many", "value": "getAll", "description": "Get many releases", "display_options": {'show': {'resource': ['release']}}},
                {"name": "Update", "value": "update", "description": "Update a release", "display_options": {'show': {'resource': ['release']}}},
                {"name": "List", "value": "list", "description": "List contents of a folder", "display_options": {'show': {'resource': ['file']}}}
            ], "default": "create", "description": "Operation to perform"},
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Authentication", "options": [
                {"name": "Access Token", "value": "accessToken"},
                {"name": "OAuth2", "value": "oAuth2"}
            ], "default": "accessToken"},
            {"name": "owner", "type": NodeParameterType.STRING, "display_name": "Project Owner", "default": "", "required": True, "description": "User, group or namespace of the project", "display_options": {'show': {'operation': ['getRepositories']}}},
            {"name": "title", "type": NodeParameterType.STRING, "display_name": "Title", "default": "", "required": True, "description": "The title of the issue", "display_options": {'show': {'operation': ['create'], 'resource': ['issue']}}},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the issue", "display_options": {'show': {'operation': ['create'], 'resource': ['issue']}}},
            {"name": "due_date", "type": NodeParameterType.STRING, "display_name": "Due Date", "default": "", "description": "Due Date for issue", "display_options": {'show': {'operation': ['create'], 'resource': ['issue']}}},
            {"name": "labels", "type": NodeParameterType.COLLECTION, "display_name": "Labels", "default": "", "description": "Label to add to issue", "display_options": {'show': {'operation': ['create'], 'resource': ['issue']}}},
            {"name": "assignee_ids", "type": NodeParameterType.COLLECTION, "display_name": "Assignees", "default": "", "description": "User ID to assign issue to", "display_options": {'show': {'operation': ['create'], 'resource': ['issue']}}},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The number of the issue on which to create the comment on", "display_options": {'show': {'operation': ['createComment'], 'resource': ['issue']}}},
            {"name": "editFields", "type": NodeParameterType.COLLECTION, "display_name": "Edit Fields", "default": "", "description": "The title of the issue", "display_options": {'show': {'operation': ['edit'], 'resource': ['issue']}}},
            {"name": "lockReason", "type": NodeParameterType.OPTIONS, "display_name": "Lock Reason", "options": [
                {"name": "Off-Topic", "value": "off-topic"},
                {"name": "Too Heated", "value": "too heated"},
                {"name": "Resolved", "value": "resolved"},
                {"name": "Spam", "value": "spam"}
            ], "default": "resolved", "description": "The issue is Off-Topic", "display_options": {'show': {'operation': ['lock'], 'resource': ['issue']}}},
            {"name": "releaseTag", "type": NodeParameterType.STRING, "display_name": "Tag", "default": "", "required": True, "description": "The tag of the release", "display_options": {'show': {'operation': ['create'], 'resource': ['release']}}},
            {"name": "additionalFields", "type": NodeParameterType.COLLECTION, "display_name": "Additional Fields", "default": "", "description": "The name of the release", "display_options": {'show': {'operation': ['create'], 'resource': ['release']}}},
            {"name": "projectId", "type": NodeParameterType.STRING, "display_name": "Project ID", "default": "", "required": True, "description": "The ID or URL-encoded path of the project", "display_options": {'show': {'operation': ['delete', 'get'], 'resource': ['release']}}},
            {"name": "tag_name", "type": NodeParameterType.STRING, "display_name": "Tag Name", "default": "", "required": True, "description": "The Git tag the release is associated with", "display_options": {'show': {'operation': ['delete', 'get'], 'resource': ['release']}}},
            {"name": "returnAll", "type": NodeParameterType.BOOLEAN, "display_name": "Return All", "default": False, "description": "Whether to return all results or only up to a given limit", "display_options": {'show': {'operation': ['getAll', 'list', 'getIssues'], 'resource': ['release', 'file', 'repository']}}},
            {"name": "limit", "type": NodeParameterType.NUMBER, "display_name": "Limit", "default": 20, "description": "Max number of results to return", "display_options": {'show': {'operation': ['getAll', 'list', 'getIssues'], 'resource': ['release', 'file', 'repository']}}},
            {"name": "getRepositoryIssuesFilters", "type": NodeParameterType.COLLECTION, "display_name": "Filters", "default": "", "description": "Return only issues which are assigned to a specific user", "display_options": {'show': {'operation': ['getIssues'], 'resource': ['repository']}}},
            {"name": "filePath", "type": NodeParameterType.STRING, "display_name": "File Path", "default": "", "description": "The file path of the file. Has to contain the full path or leave it empty for root folder.", "display_options": {'show': {'resource': ['file']}}},
            {"name": "page", "type": NodeParameterType.NUMBER, "display_name": "Page", "default": 1, "description": "Page of results to display", "display_options": {'show': {'operation': ['list'], 'resource': ['file']}}},
            {"name": "additionalParameters", "type": NodeParameterType.COLLECTION, "display_name": "Additional Parameters", "default": "", "description": "Additional fields to add", "display_options": {'show': {'operation': ['list'], 'resource': ['file']}}},
            {"name": "asBinaryProperty", "type": NodeParameterType.BOOLEAN, "display_name": "As Binary Property", "default": True, "description": "Whether to set the data of the file as binary property instead of returning the raw API response", "display_options": {'show': {'operation': ['get'], 'resource': ['file']}}},
            {"name": "binaryPropertyName", "type": NodeParameterType.STRING, "display_name": "Put Output File in Field", "default": "data", "required": True, "display_options": {'show': {'operation': ['get'], 'resource': ['file']}}},
            {"name": "binaryData", "type": NodeParameterType.BOOLEAN, "display_name": "Binary File", "default": False, "required": True, "description": "Whether the data to upload should be taken from binary field", "display_options": {'show': {'operation': ['create', 'edit'], 'resource': ['file']}}},
            {"name": "fileContent", "type": NodeParameterType.STRING, "display_name": "File Content", "default": "", "required": True, "description": "The text content of the file", "display_options": {'show': {'operation': ['create', 'edit'], 'resource': ['file']}}},
            {"name": "commitMessage", "type": NodeParameterType.STRING, "display_name": "Commit Message", "default": "", "required": True, "display_options": {'show': {'operation': ['create', 'delete', 'edit'], 'resource': ['file']}}},
            {"name": "branch", "type": NodeParameterType.STRING, "display_name": "Branch", "default": "", "required": True, "description": "Name of the new branch to create. The commit is added to this branch.", "display_options": {'show': {'operation': ['create', 'delete', 'edit'], 'resource': ['file']}}},
            {"name": "events", "type": NodeParameterType.MULTI_OPTIONS, "display_name": "Events", "options": [
                {"name": "*", "value": "*"}
            ], "default": [], "required": True, "description": "Any time any event is triggered (Wildcard Event)"}
        ],
        "credentials": [
            {"name": "gitlabApi", "required": False},
            {"name": "gitlabOAuth2Api", "required": False}
        ]
    }
    
    icon = "gitlab.svg"

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
                
                if resource == "issue" and operation == "create":
                    result = self._issue_create(i, item_data)
                elif resource == "issue" and operation == "createComment":
                    result = self._issue_createComment(i, item_data)
                elif resource == "issue" and operation == "edit":
                    result = self._issue_edit(i, item_data)
                elif resource == "issue" and operation == "get":
                    result = self._issue_get(i, item_data)
                elif resource == "issue" and operation == "lock":
                    result = self._issue_lock(i, item_data)
                elif resource == "release" and operation == "create":
                    result = self._release_create(i, item_data)
                elif resource == "release" and operation == "delete":
                    result = self._release_delete(i, item_data)
                elif resource == "release" and operation == "get":
                    result = self._release_get(i, item_data)
                elif resource == "release" and operation == "getAll":
                    result = self._release_getAll(i, item_data)
                elif resource == "release" and operation == "update":
                    result = self._release_update(i, item_data)
                elif resource == "repository" and operation == "get":
                    result = self._repository_get(i, item_data)
                elif resource == "repository" and operation == "getIssues":
                    result = self._repository_getIssues(i, item_data)
                elif resource == "user" and operation == "getRepositories":
                    result = self._user_getRepositories(i, item_data)
                elif resource == "file" and operation == "delete":
                    result = self._file_delete(i, item_data)
                elif resource == "file" and operation == "get":
                    result = self._file_get(i, item_data)
                elif resource == "file" and operation == "list":
                    result = self._file_list(i, item_data)
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

    # API Base URL
    BASE_URL = "https://gitlab.com/api/v4"
    
    def _api_request(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated API request.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        import requests

        # FIX #22: Respect authentication selector
        auth_type = self.get_node_parameter('authentication', 0)
        if auth_type == 'oAuth2':
            credentials = self.get_credentials("gitlabOAuth2Api")
        else:
            credentials = self.get_credentials("gitlabApi")
        
        # Build full URL
        url = f"{self.BASE_URL}{endpoint}"
        
        # Get auth headers
        headers = self._get_auth_headers(credentials)
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=body,
            params=query,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()
    
    def _api_request_all_items(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Make paginated API request and return all items.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        import requests

        # FIX #22: Respect authentication selector
        auth_type = self.get_node_parameter('authentication', 0)
        if auth_type == 'oAuth2':
            credentials = self.get_credentials("gitlabOAuth2Api")
        else:
            credentials = self.get_credentials("gitlabApi")
        
        results = []
        query = query or {}
        page = 1
        per_page = 100
        
        while True:
            # Add pagination params
            page_query = query.copy()
            page_query["page"] = page
            page_query["per_page"] = per_page
            
            url = f"{self.BASE_URL}{endpoint}"
            headers = self._get_auth_headers(credentials)
            
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body,
                params=page_query,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            
            # Handle different pagination response formats
            if isinstance(data, list):
                if not data:
                    break
                results.extend(data)
                if len(data) < per_page:
                    break
            elif isinstance(data, dict):
                items = data.get("items", data.get("data", []))
                if not items:
                    break
                results.extend(items)
                if len(items) < per_page:
                    break
            else:
                break
            
            page += 1
        
        return results
    
    def _get_auth_headers(self, credentials: Dict[str, Any]) -> Dict[str, str]:
        """Get authentication headers from credentials."""
        headers = {"Content-Type": "application/json"}
        
        # FIXED: Use Bearer token for GitHub/GitLab/Discord, not "Bot"
        if "accessToken" in credentials:
            headers["Authorization"] = f"Bearer {credentials['accessToken']}"
        elif "access_token" in credentials:
            headers["Authorization"] = f"Bearer {credentials['access_token']}"
        elif "token" in credentials:
            headers["Authorization"] = f"Bearer {credentials['token']}"
        elif "apiKey" in credentials:
            # API key in header (some services)
            headers["Authorization"] = f"Bearer {credentials['apiKey']}"
        
        return headers


    def _issue_create(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Issue Create operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        title = self.get_node_parameter('title', item_index)
        description = self.get_node_parameter('body', item_index)
        due_date = self.get_node_parameter('due_date', item_index)
        labels = self.get_node_parameter('labels', item_index)
        assignee_ids = self.get_node_parameter('assignee_ids', item_index)
        title_text = self.get_node_parameter('title', item_index)
        body_text = self.get_node_parameter('body', item_index)
        due_date_text = self.get_node_parameter('due_date', item_index)
        
        # Validate parameters
        if not title or not title.strip():
            raise ValueError("Parameter 'title' is required for issue creation")
        
        # Build request body
        body = {'title': title_text, 'description': body_text, 'due_date': due_date_text, 'labels': labels, 'assignee_ids': assignee_ids}
        
        # Make API request
        response = self._api_request('POST', f'{baseEndpoint}/issues', body=body, query=None)
        
        return response

    def _issue_createComment(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Issue Createcomment operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        issue_number = self.get_node_parameter('issueNumber', item_index)
        body = self.get_node_parameter('body', item_index)
        body_text = self.get_node_parameter('body', item_index)
        
        # Validate parameters
        if not isinstance(issue_number, int) or issue_number <= 0:
            raise ValueError("Parameter 'issueNumber' must be a positive integer")
        
        # Build request body (avoid parameter shadowing)
        body = {'body': body}
        
        # Make API request
        response = self._api_request('POST', f'{baseEndpoint}/issues/{issue_number}/notes', body=body, query=None)
        
        return response

    def _issue_edit(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Issue Edit operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        issue_number = self.get_node_parameter('issueNumber', item_index)
        body = self.get_node_parameter('editFields', item_index)
        
        # Validate parameters
        if not isinstance(issue_number, int) or issue_number <= 0:
            raise ValueError("Parameter 'issueNumber' must be a positive integer")
        
        # Make API request
        response = self._api_request('PUT', f'{baseEndpoint}/issues/{issue_number}', body=body, query=None)
        
        return response

    def _issue_get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Issue Get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        issue_number = self.get_node_parameter('issueNumber', item_index)
        
        # Make API request
        response = self._api_request('GET', f'{baseEndpoint}/issues/{issue_number}', body=None, query=None)
        
        return response

    def _issue_lock(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Issue Lock operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        issue_number = self.get_node_parameter('issueNumber', item_index)
        
        # Validate parameters
        if not isinstance(issue_number, int) or issue_number <= 0:
            raise ValueError("Parameter 'issueNumber' must be a positive integer")
        
        
        # Build request body (extracted parameters)
        body = {}
        # Make API request
        response = self._api_request('PUT', f'{baseEndpoint}/issues/{issue_number}', body=body, query=None)
        
        return response

    def _release_create(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Release Create operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        body = self.get_node_parameter('additionalFields', item_index)
        tag_name = self.get_node_parameter('releaseTag', item_index)
        
        # Add required fields to body
        body['tag_name'] = tag_name
        
        # Make API request
        response = self._api_request('POST', f'{baseEndpoint}/releases', body=body, query=None)
        
        return response

    def _release_delete(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Release Delete operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        # TODO: Implement delete operation
        # Similar pattern to insert: get parameters, build SQL, execute with connection
        raise NotImplementedError('delete operation not yet fully implemented')

    def _release_get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Release Get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        id = self.get_node_parameter('projectId', item_index)
        tag_name = self.get_node_parameter('tag_name', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/projects/{id}/releases/{tag_name}', body=None, query=None)
        
        return response

    def _release_getAll(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Release Getall operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        id = self.get_node_parameter('projectId', item_index)
        qs = self.get_node_parameter('additionalFields', item_index)
        return_all = self.get_node_parameter('returnAll', item_index)
        per_page = self.get_node_parameter('limit', item_index)
        
        # Make API request
        if return_all:
            response = self._api_request_all_items('GET', f'/projects/{id}/releases', body=None, query=None)
        else:
            query = {}
            query['per_page'] = per_page
            response = self._api_request('GET', f'/projects/{id}/releases', body=None, query=query)
        
        return response

    def _release_update(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Release Update operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        # TODO: Implement update operation
        # Similar pattern to insert: get parameters, build SQL, execute with connection
        raise NotImplementedError('update operation not yet fully implemented')

    def _repository_get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repository Get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        
        # Make API request
        response = self._api_request('GET', f'{baseEndpoint}', body=None, query=None)
        
        return response

    def _repository_getIssues(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repository Getissues operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        qs = self.get_node_parameter('getRepositoryIssuesFilters', item_index)
        return_all = self.get_node_parameter('returnAll', item_index)
        per_page = self.get_node_parameter('limit', item_index)
        
        # Make API request
        if return_all:
            response = self._api_request_all_items('GET', f'{baseEndpoint}/issues', body=None, query=None)
        else:
            query = {}
            query['per_page'] = per_page
            response = self._api_request('GET', f'{baseEndpoint}/issues', body=None, query=query)
        
        return response

    def _user_getRepositories(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        User Getrepositories operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        owner = self.get_node_parameter('owner', item_index)
        
        # Validate parameters
        if not owner or not owner.strip():
            raise ValueError("Parameter 'owner' is required")
        
        # Make API request
        response = self._api_request('GET', f'/users/{owner}/projects', body=None, query=None)
        
        return response

    def _file_delete(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        File Delete operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        # TODO: Implement delete operation
        # Similar pattern to insert: get parameters, build SQL, execute with connection
        raise NotImplementedError('delete operation not yet fully implemented')

    def _file_get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        File Get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        file_path = self.get_node_parameter('filePath', item_index)
        additional_parameters = self.get_node_parameter('additionalParameters', item_index)
        
        # Validate parameters
        if not file_path or not file_path.strip():
            raise ValueError("Parameter 'filePath' cannot be empty")
        if file_path.startswith('/'):
            raise ValueError("Parameter 'filePath' should not start with '/'. Use relative path from repository root.")
        
        # Build query parameters
        query = {}
        query['ref'] = additional_parameters.get('reference')
        query['ref'] = 'master'
        
        # Make API request
        response = self._api_request('GET', f'{baseEndpoint}/repository/files/{file_path}', body=None, query=query)
        
        return response

    def _file_list(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        File List operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        file_path = self.get_node_parameter('filePath', item_index)
        qs = self.get_node_parameter('additionalParameters', item_index)
        return_all = self.get_node_parameter('returnAll', item_index)
        per_page = self.get_node_parameter('limit', item_index)
        page = self.get_node_parameter('page', item_index)
        
        # Validate parameters
        if not file_path or not file_path.strip():
            raise ValueError("Parameter 'filePath' cannot be empty")
        if file_path.startswith('/'):
            raise ValueError("Parameter 'filePath' should not start with '/'. Use relative path from repository root.")
        
        # Build query parameters
        query = {}
        query['page'] = page
        query['path'] = file_path
        
        # Make API request
        if return_all:
            response = self._api_request_all_items('GET', f'{baseEndpoint}/repository/tree', body=None, query=query)
        else:
            query['per_page'] = per_page
            response = self._api_request('GET', f'{baseEndpoint}/repository/tree', body=None, query=query)
        
        return response

