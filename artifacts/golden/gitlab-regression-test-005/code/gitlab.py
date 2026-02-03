#!/usr/bin/env python3
"""
Gitlab Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: gitlab-regression-test-005
Generated: 2026-02-03T07:20:38.377071

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from .base import BaseNode, NodeParameter, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class GitlabNode(BaseNode):
    """
    Gitlab node.
    
    
    """

    node_type = "gitlab"
    node_version = 1
    display_name = "Gitlab"
    description = ""
    icon = "file:gitlab.svg"
    group = ['output']
    
    credentials = [
        {
            "name": "gitlabApi",
            "required": True,
        }
    ]

    properties = [
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Authentication", "options": [
                {"name": "Gitlabapi", "value": "gitlabApi"},
                {"name": "Gitlaboauth2api", "value": "gitlabOAuth2Api"}
            ], "default": "gitlabApi", "description": "Authentication method to use"},
            {"name": "resource", "type": NodeParameterType.OPTIONS, "display_name": "Resource", "options": [
                {"name": "Issue", "value": "issue"},
                {"name": "Repository", "value": "repository"},
                {"name": "User", "value": "user"},
                {"name": "Release", "value": "release"},
                {"name": "File", "value": "file"}
            ], "default": "issue", "description": "The resource to operate on"},
            {"name": "Issue", "type": NodeParameterType.OPTIONS, "display_name": "File"},
            {"name": "Create Comment", "type": NodeParameterType.OPTIONS, "display_name": "Create", "description": "Create a new issue"},
            {"name": "Get Issues", "type": NodeParameterType.OPTIONS, "display_name": "Get", "description": "Get the data of a single repository"},
            {"name": "Delete", "type": NodeParameterType.OPTIONS, "display_name": "Create", "description": "Create a new release"},
            {"name": "Delete", "type": NodeParameterType.STRING, "display_name": "Create", "description": "Create a new file in repository"},
            {"name": "repository", "type": NodeParameterType.STRING, "display_name": "Project Name", "default": "", "required": True, "description": "The name of the project"},
            {"name": "title", "type": NodeParameterType.STRING, "display_name": "Title", "default": "", "required": True, "description": "The title of the issue", "display_options": {'show': {'operation': ['create']}}},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the issue", "display_options": {'show': {'operation': ['create']}}},
            {"name": "due_date", "type": NodeParameterType.STRING, "display_name": "Due Date", "default": "", "description": "Due Date for issue", "display_options": {'show': {'operation': ['create']}}},
            {"name": "labels", "type": NodeParameterType.COLLECTION, "display_name": "Labels", "default": "{ label: ", "description": "Label to add to issue", "display_options": {'show': {'operation': ['create']}}},
            {"name": "label", "type": NodeParameterType.STRING, "display_name": "Label", "default": "", "description": "Label to add to issue"},
            {"name": "assignee_ids", "type": NodeParameterType.COLLECTION, "display_name": "Assignees", "default": "{ assignee: ", "description": "User ID to assign issue to", "display_options": {'show': {'operation': ['create']}}},
            {"name": "assignee", "type": NodeParameterType.NUMBER, "display_name": "Assignee", "default": 0, "description": "User ID to assign issue to"},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The number of the issue on which to create the comment on", "display_options": {'show': {'operation': ['createComment']}}},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the comment", "display_options": {'show': {'operation': ['createComment']}}},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The number of the issue edit", "display_options": {'show': {'operation': ['edit']}}},
            {"name": "editFields", "type": NodeParameterType.COLLECTION, "display_name": "Edit Fields", "default": "{", "description": "The title of the issue", "display_options": {'show': {'operation': ['edit']}}},
            {"name": "title", "type": NodeParameterType.STRING, "display_name": "Title", "default": "", "description": "The title of the issue"},
            {"name": "description", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the issue"},
            {"name": "state", "type": NodeParameterType.OPTIONS, "display_name": "State", "options": [
                {"name": "Closed", "value": "closed"},
                {"name": "Open", "value": "open"}
            ], "default": "open", "description": "Set the state to "},
            {"name": "Open", "type": NodeParameterType.COLLECTION, "display_name": "Closed", "description": "Set the state to "},
            {"name": "label", "type": NodeParameterType.STRING, "display_name": "Label", "default": "", "description": "Label to add to issue"},
            {"name": "assignee_ids", "type": NodeParameterType.COLLECTION, "display_name": "Assignees", "default": "{ assignee: ", "description": "User to assign issue too"},
            {"name": "assignee", "type": NodeParameterType.STRING, "display_name": "Assignees", "default": "", "description": "User to assign issue too"},
            {"name": "due_date", "type": NodeParameterType.STRING, "display_name": "Due Date", "default": "", "description": "Due Date for issue"},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The number of the issue get data of", "display_options": {'show': {'operation': ['get']}}},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The number of the issue to lock", "display_options": {'show': {'operation': ['lock']}}},
            {"name": "lockReason", "type": NodeParameterType.OPTIONS, "display_name": "Lock Reason", "options": [
                {"name": "Off-Topic", "value": "off-topic"},
                {"name": "Too Heated", "value": "too heated"},
                {"name": "Resolved", "value": "resolved"},
                {"name": "Spam", "value": "spam"}
            ], "default": "resolved", "description": "The issue is Off-Topic", "display_options": {'show': {'operation': ['lock']}}},
            {"name": "Too Heated", "type": NodeParameterType.STRING, "display_name": "Off-Topic", "description": "The issue is Off-Topic"},
            {"name": "additionalFields", "type": NodeParameterType.COLLECTION, "display_name": "Additional Fields", "default": "{", "description": "The name of the release", "display_options": {'show': {'operation': ['create']}}},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "Name", "default": "", "description": "The name of the release"},
            {"name": "description", "type": NodeParameterType.STRING, "display_name": "Description", "default": "", "description": "The description of the release"},
            {"name": "ref", "type": NodeParameterType.STRING, "display_name": "Ref", "default": "", "description": "If Tag doesn’t exist, the release will be created from Ref. It can be a commit SHA, another tag name, or a branch name."},
            {"name": "projectId", "type": NodeParameterType.STRING, "display_name": "Project ID", "default": "", "required": True, "description": "The ID or URL-encoded path of the project", "display_options": {'show': {'operation': ['delete', 'get']}}},
            {"name": "tag_name", "type": NodeParameterType.STRING, "display_name": "Tag Name", "default": "", "required": True, "description": "The Git tag the release is associated with", "display_options": {'show': {'operation': ['delete', 'get']}}},
            {"name": "projectId", "type": NodeParameterType.STRING, "display_name": "Project ID", "default": "", "required": True, "description": "The ID or URL-encoded path of the project", "display_options": {'show': {'operation': ['getAll']}}},
            {"name": "returnAll", "type": NodeParameterType.BOOLEAN, "display_name": "Return All", "default": False, "description": "Whether to return all results or only up to a given limit", "display_options": {'show': {'operation': ['getAll', 'list', 'getIssues']}}},
            {"name": "limit", "type": NodeParameterType.NUMBER, "display_name": "Limit", "default": 20, "description": "Max number of results to return", "display_options": {'show': {'operation': ['getAll', 'list', 'getIssues']}}},
            {"name": "additionalFields", "type": NodeParameterType.COLLECTION, "display_name": "Additional Fields", "default": "{", "description": "The field to use", "display_options": {'show': {'operation': ['getAll']}}},
            {"name": "order_by", "type": NodeParameterType.OPTIONS, "display_name": "Order By", "options": [
                {"name": "Created At", "value": "created_at"},
                {"name": "Released At", "value": "released_at"}
            ], "default": "released_at", "description": "The field to use"},
            {"name": "Released At", "type": NodeParameterType.OPTIONS, "display_name": "Created At"},
            {"name": "DESC", "type": NodeParameterType.STRING, "display_name": "ASC"},
            {"name": "tag_name", "type": NodeParameterType.STRING, "display_name": "Tag Name", "default": "", "required": True, "description": "The Git tag the release is associated with", "display_options": {'show': {'operation': ['update']}}},
            {"name": "additionalFields", "type": NodeParameterType.COLLECTION, "display_name": "Additional Fields", "default": "{", "description": "The release name", "display_options": {'show': {'operation': ['update']}}},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "Name", "default": "", "description": "The release name"},
            {"name": "description", "type": NodeParameterType.STRING, "display_name": "Description", "default": "", "description": "The description of the release. You can use Markdown."},
            {"name": "milestones", "type": NodeParameterType.STRING, "display_name": "Milestones", "default": "", "description": "The title of each milestone to associate with the release (provide a titles list spearated with comma)"},
            {"name": "released_at", "type": NodeParameterType.STRING, "display_name": "Released At", "default": "", "description": "The date when the release is/was ready"},
            {"name": "getRepositoryIssuesFilters", "type": NodeParameterType.COLLECTION, "display_name": "Filters", "default": "{", "description": "Return only issues which are assigned to a specific user", "display_options": {'show': {'operation': ['getIssues']}}},
            {"name": "assignee_username", "type": NodeParameterType.STRING, "display_name": "Assignee", "default": "", "description": "Return only issues which are assigned to a specific user"},
            {"name": "author_username", "type": NodeParameterType.STRING, "display_name": "Creator", "default": "", "description": "Return only issues which were created by a specific user"},
            {"name": "search", "type": NodeParameterType.STRING, "display_name": "Search", "default": "", "description": "Search issues against their title and description"},
            {"name": "labels", "type": NodeParameterType.STRING, "display_name": "Labels", "default": "", "description": "Return only issues with the given labels. Multiple lables can be separated by comma."},
            {"name": "updated_after", "type": NodeParameterType.STRING, "display_name": "Updated After", "default": "", "description": "Return only issues updated at or after this time"},
            {"name": "state", "type": NodeParameterType.OPTIONS, "display_name": "State", "options": [
                {"name": "All", "value": "closed"},
                {"name": "Open", "value": "opened"}
            ], "default": "opened", "description": "Returns issues with any state"},
            {"name": "Closed", "type": NodeParameterType.OPTIONS, "display_name": "All", "description": "Returns issues with any state"},
            {"name": "Updated At", "type": NodeParameterType.OPTIONS, "display_name": "Created At", "description": "Sort by created date"},
            {"name": "Descending", "type": NodeParameterType.STRING, "display_name": "Ascending", "description": "Sort in ascending order"},
            {"name": "filePath", "type": NodeParameterType.STRING, "display_name": "Path", "default": "", "description": "The path of the folder to list", "display_options": {'show': {'operation': ['list']}}},
            {"name": "page", "type": NodeParameterType.NUMBER, "display_name": "Page", "default": 1, "description": "Page of results to display", "display_options": {'show': {'operation': ['list']}}},
            {"name": "additionalParameters", "type": NodeParameterType.COLLECTION, "display_name": "Additional Parameters", "default": "{", "description": "Additional fields to add", "display_options": {'show': {'operation': ['list']}}},
            {"name": "ref", "type": NodeParameterType.STRING, "display_name": "Reference", "default": "", "description": "The name of the commit/branch/tag. Default: the repository’s default branch (usually main)."},
            {"name": "recursive", "type": NodeParameterType.BOOLEAN, "display_name": "Recursive", "default": False, "description": "Whether or not to get a recursive file tree. Default is False."},
            {"name": "asBinaryProperty", "type": NodeParameterType.BOOLEAN, "display_name": "As Binary Property", "default": True, "description": "Whether to set the data of the file property instead of returning the raw API response", "display_options": {'show': {'operation': ['get']}}},
            {"name": "binaryPropertyName", "type": NodeParameterType.STRING, "display_name": "Put Output File in Field", "default": "data", "required": True, "display_options": {'show': {'operation': ['get']}}},
            {"name": "additionalParameters", "type": NodeParameterType.COLLECTION, "display_name": "Additional Parameters", "default": "{", "description": "Additional fields to add", "display_options": {'show': {'operation': ['get']}}},
            {"name": "reference", "type": NodeParameterType.STRING, "display_name": "Reference", "default": "", "description": "The name of the commit/branch/tag. Default: the repository’s default branch (usually main)."},
            {"name": "binaryData", "type": NodeParameterType.BOOLEAN, "display_name": "Binary File", "default": False, "required": True, "description": "Whether the data to upload should be taken from binary field", "display_options": {'show': {'operation': ['create', 'edit']}}},
            {"name": "fileContent", "type": NodeParameterType.STRING, "display_name": "File Content", "default": "", "required": True, "description": "The text content of the file", "display_options": {'show': {'operation': ['create', 'edit']}}},
            {"name": "binaryPropertyName", "type": NodeParameterType.STRING, "display_name": "Input Binary Field", "default": "data", "required": True, "display_options": {'show': {'operation': ['create', 'edit']}}},
            {"name": "commitMessage", "type": NodeParameterType.STRING, "display_name": "Commit Message", "default": "", "required": True, "display_options": {'show': {'operation': ['create', 'delete', 'edit']}}},
            {"name": "branch", "type": NodeParameterType.STRING, "display_name": "Branch", "default": "", "required": True, "description": "Name of the new branch to create. The commit is added to this branch.", "display_options": {'show': {'operation': ['create', 'delete', 'edit']}}},
            {"name": "additionalParameters", "type": NodeParameterType.COLLECTION, "display_name": "Additional Parameters", "default": "{", "description": "Additional fields to add", "display_options": {'show': {'operation': ['create', 'delete', 'edit']}}},
            {"name": "branchStart", "type": NodeParameterType.STRING, "display_name": "Start Branch", "default": "", "description": "Name of the base branch to create the new branch from"},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "author", "default": "", "description": "The name of the author of the commit"},
            {"name": "email", "type": NodeParameterType.STRING, "display_name": "Email", "default": "", "description": "The email of the author of the commit"},
            {"name": "encoding", "type": NodeParameterType.STRING, "display_name": "encoding", "default": "text", "description": "Change encoding to base64. Default is text."},
            {"name": "repository", "type": NodeParameterType.STRING, "display_name": "Repository Name", "default": "", "required": True, "description": "The name of the repository"},
            {"name": "events", "type": NodeParameterType.MULTI_OPTIONS, "display_name": "Events", "options": [
                {"name": "*", "value": "*"}
            ], "default": "[]", "required": True, "description": "Any time any event is triggered (Wildcard Event)"}
        ]

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
                
            except Exception:
                logger.error(f"Error in {resource}/{operation}: {e}")
                if self.continue_on_fail:
                    return_items.append(NodeExecutionData(json_data={"error": str(e)}))
                else:
                    raise
        
        return [return_items]

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
        credentials = self.get_credentials("gitlabApi")
        
        # TODO: Configure authentication based on credential type
        query = query or {}
        # For API key auth: query["api_key"] = credentials.get("apiKey")
        # For Bearer auth: headers["Authorization"] = f"Bearer {credentials.get('accessToken')}"
        
        url = f"https://api.example.com{endpoint}"
        
        response = requests.request(
            method,
            url,
            params=query,
            json=body,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()

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
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('POST', f'{self._base_endpoint}/issues', body=None, query=None)
        response = response.get('data', response)
        
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
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('POST', f'{self._base_endpoint}/issues/{self._issue_number}/notes', body=None, query=None)
        response = response.get('data', response)
        
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
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('PUT', f'{self._base_endpoint}/issues/{self._issue_number}', body=None, query=None)
        response = response.get('data', response)
        
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
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('GET', f'{self._base_endpoint}/issues/{self._issue_number}', body=None, query=None)
        response = response.get('data', response)
        
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
        
        # Build request body
        body = {'discussion_locked': True}
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('PUT', f'{self._base_endpoint}/issues/{self._issue_number}', body=body, query=None)
        response = response.get('data', response)
        
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
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('POST', f'{self._base_endpoint}/releases', body=None, query=None)
        response = response.get('data', response)
        
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
        id = self.get_node_parameter('projectId', item_index)
        tag_name = self.get_node_parameter('tag_name', item_index)
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('DELETE', f'/projects/{self._id}/releases/{self._tag_name}', body=None, query=None)
        response = response.get('data', response)
        
        return response

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
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('GET', f'/projects/{self._id}/releases/{self._tag_name}', body=None, query=None)
        response = response.get('data', response)
        
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
        
        # Build query parameters
        query = {}
        query['per_page'] = this_get_node_parameter('limit', 0)
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('GET', f'/projects/{self._id}/releases', body=None, query=query)
        response = response.get('data', response)
        
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
        id = self.get_node_parameter('projectId', item_index)
        tag_name = self.get_node_parameter('tag_name', item_index)
        body = self.get_node_parameter('additionalFields', item_index)
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('PUT', f'/projects/{self._id}/releases/{self._tag_name}', body=None, query=None)
        response = response.get('data', response)
        
        return response

    def _repository_get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repository Get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('GET', f'{self._base_endpoint}', body=None, query=None)
        response = response.get('data', response)
        
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
        
        # Build query parameters
        query = {}
        query['per_page'] = this_get_node_parameter('limit', 0)
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('GET', f'{self._base_endpoint}/issues', body=None, query=query)
        response = response.get('data', response)
        
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
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('GET', f'/users/{self._owner}/projects', body=None, query=None)
        response = response.get('data', response)
        
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
        branch = self.get_node_parameter('branch', item_index)
        commit_message = self.get_node_parameter('commitMessage', item_index)
        file_path = self.get_node_parameter('filePath', item_index)
        
        # Build request body
        body = {'author_name': author_name, 'author_email': author_email}
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('DELETE', f'{self._base_endpoint}/repository/files/${encodeURIComponent(filePath)}', body=body, query=None)
        response = response.get('data', response)
        
        return response

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
        
        # Build query parameters
        query = {}
        query['ref'] = additional_parameters_reference
        query['ref'] = 'master'
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('GET', f'{self._base_endpoint}/repository/files/${encodeURIComponent(filePath)}', body=None, query=query)
        response = response.get('data', response)
        
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
        
        # Build query parameters
        query = {}
        query['per_page'] = this_get_node_parameter('limit', i)
        query['page'] = this_get_node_parameter('page', i)
        query['path'] = file_path
        
        # Make API request (method/endpoint from operation block)
        response = self._api_request('GET', f'{self._base_endpoint}/repository/tree', body=None, query=query)
        response = response.get('data', response)
        
        return response

