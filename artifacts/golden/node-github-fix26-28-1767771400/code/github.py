#!/usr/bin/env python3
"""
Github Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: node-github-fix26-28-1767771400
Generated: 2026-01-07T07:52:47.734668

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from .base import BaseNode, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class GithubNode(BaseNode):
    """
    GitHub node.
    
    
    """

    type = "github"
    version = 1
    
    description = {
        "displayName": "GitHub",
        "name": "github",
        "icon": "file:github.svg",
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
                {"name": "Organization", "value": "organization"},
                {"name": "Release", "value": "release"},
                {"name": "Repository", "value": "repository"},
                {"name": "Review", "value": "review"},
                {"name": "User", "value": "user"},
                {"name": "Workflow", "value": "workflow"}
            ], "default": "issue", "description": "The resource to operate on"},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Get Repositories", "value": "getRepositories", "description": "Returns all repositories of an organization", "display_options": {'show': {'resource': ['user', 'organization']}}},
                {"name": "Create", "value": "create", "description": "Create a new issue", "display_options": {'show': {'resource': ['release', 'issue', 'review']}}},
                {"name": "Create Comment", "value": "createComment", "description": "Create a new comment on an issue", "display_options": {'show': {'resource': ['issue']}}},
                {"name": "Edit", "value": "edit", "description": "Edit an issue", "display_options": {'show': {'resource': ['file', 'issue']}}},
                {"name": "Get", "value": "get", "description": "Get the data of a single issue", "display_options": {'show': {'resource': ['file', 'release', 'workflow', 'issue', 'review', 'repository']}}},
                {"name": "Lock", "value": "lock", "description": "Lock an issue", "display_options": {'show': {'resource': ['issue']}}},
                {"name": "Delete", "value": "delete", "description": "Delete a file in repository", "display_options": {'show': {'resource': ['file', 'release']}}},
                {"name": "List", "value": "list", "description": "List contents of a folder", "display_options": {'show': {'resource': ['file', 'workflow']}}},
                {"name": "Get Issues", "value": "getIssues", "description": "Returns issues of a repository", "display_options": {'show': {'resource': ['repository']}}},
                {"name": "Get License", "value": "getLicense", "description": "Returns the contents of the repository", "display_options": {'show': {'resource': ['repository']}}},
                {"name": "Get Pull Requests", "value": "getPullRequests", "description": "Returns pull requests of a repository", "display_options": {'show': {'resource': ['repository']}}},
                {"name": "List Popular Paths", "value": "listPopularPaths", "description": "Get the top 10 popular content paths over the last 14 days", "display_options": {'show': {'resource': ['repository']}}},
                {"name": "List Referrers", "value": "listReferrers", "description": "Get the top 10 referrering domains over the last 14 days", "display_options": {'show': {'resource': ['repository']}}},
                {"name": "Invite", "value": "invite", "description": "Invites a user to an organization", "display_options": {'show': {'resource': ['user']}}},
                {"name": "Get Many", "value": "getAll", "description": "Get many repository releases", "display_options": {'show': {'resource': ['release', 'review']}}},
                {"name": "Update", "value": "update", "description": "Update a release", "display_options": {'show': {'resource': ['release', 'review']}}},
                {"name": "Disable", "value": "disable", "description": "Disable a workflow", "display_options": {'show': {'resource': ['workflow']}}},
                {"name": "Dispatch", "value": "dispatch", "description": "Dispatch a workflow event", "display_options": {'show': {'resource': ['workflow']}}},
                {"name": "Enable", "value": "enable", "description": "Enable a workflow", "display_options": {'show': {'resource': ['workflow']}}},
                {"name": "Get Usage", "value": "getUsage", "description": "Get the usage of a workflow", "display_options": {'show': {'resource': ['workflow']}}}
            ], "default": "getRepositories", "description": "Operation to perform"},
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Authentication", "options": [
                {"name": "Access Token", "value": "accessToken"},
                {"name": "OAuth2", "value": "oAuth2"}
            ], "default": "accessToken"},
            {"name": "webhookNotice", "type": NodeParameterType.STRING, "display_name": "Your execution will pause until a webhook is called. This URL will be generated at runtime and passed to your Github workflow as a resumeUrl input.", "default": "", "display_options": {'show': {'operation': ['dispatchAndWait'], 'resource': ['workflow']}}},
            {"name": "owner", "type": NodeParameterType.STRING, "display_name": "Repository Owner", "default": "", "required": True, "display_options": {'show': {'operation': ['createComment', 'delete', 'get', 'list', 'lock', 'edit', 'create', 'getIssues', 'getRepositories', 'getLicense', 'getAll', 'getPullRequests', 'listReferrers', 'enable', 'getUsage', 'dispatch', 'listPopularPaths', 'update', 'disable']}}},
            {"name": "repository", "type": NodeParameterType.STRING, "display_name": "Repository Name", "default": "", "required": True, "display_options": {'show': {'operation': ['createComment', 'create', 'delete', 'getIssues', 'get', 'listPopularPaths', 'listReferrers', 'dispatch', 'enable', 'list', 'update', 'getLicense', 'getAll', 'getPullRequests', 'disable', 'getUsage', 'lock', 'edit']}}},
            {"name": "workflowId", "type": NodeParameterType.STRING, "display_name": "Workflow", "default": "", "required": True, "description": "The workflow to dispatch", "display_options": {'show': {'operation': ['disable', 'dispatch', 'dispatchAndWait', 'get', 'getUsage', 'enable'], 'resource': ['workflow']}}},
            {"name": "ref", "type": NodeParameterType.STRING, "display_name": "Ref", "default": "main", "required": True, "description": "The git reference for the workflow dispatch (branch or tag name)", "display_options": {'show': {'operation': ['dispatch', 'dispatchAndWait'], 'resource': ['workflow']}}},
            {"name": "inputs", "type": NodeParameterType.JSON, "display_name": "Inputs", "default": "{}", "description": "JSON object with input parameters for the workflow", "display_options": {'show': {'operation': ['dispatch', 'dispatchAndWait'], 'resource': ['workflow']}}},
            {"name": "filePath", "type": NodeParameterType.STRING, "display_name": "File Path", "default": "", "required": True, "description": "The file path of the file. Has to contain the full path.", "display_options": {'show': {'resource': ['file']}}},
            {"name": "binaryData", "type": NodeParameterType.BOOLEAN, "display_name": "Binary File", "default": False, "required": True, "description": "Whether the data to upload should be taken from binary field", "display_options": {'show': {'operation': ['create', 'edit'], 'resource': ['file']}}},
            {"name": "fileContent", "type": NodeParameterType.STRING, "display_name": "File Content", "default": "", "required": True, "description": "The text content of the file", "display_options": {'show': {'operation': ['create', 'edit'], 'resource': ['file']}}},
            {"name": "binaryPropertyName", "type": NodeParameterType.STRING, "display_name": "Input Binary Field", "default": "data", "required": True, "display_options": {'show': {'operation': ['create', 'edit'], 'resource': ['file']}}},
            {"name": "commitMessage", "type": NodeParameterType.STRING, "display_name": "Commit Message", "default": "", "required": True, "display_options": {'show': {'operation': ['create', 'delete', 'edit'], 'resource': ['file']}}},
            {"name": "additionalParameters", "type": NodeParameterType.COLLECTION, "display_name": "Additional Parameters", "default": "", "description": "Additional fields to add", "display_options": {'show': {'operation': ['create', 'delete', 'edit'], 'resource': ['file']}}},
            {"name": "asBinaryProperty", "type": NodeParameterType.BOOLEAN, "display_name": "As Binary Property", "default": True, "description": "Whether to set the data of the file as binary property instead of returning the raw API response", "display_options": {'show': {'operation': ['get'], 'resource': ['file']}}},
            {"name": "title", "type": NodeParameterType.STRING, "display_name": "Title", "default": "", "required": True, "description": "The title of the issue", "display_options": {'show': {'operation': ['create'], 'resource': ['issue']}}},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the issue", "display_options": {'show': {'operation': ['create'], 'resource': ['issue']}}},
            {"name": "labels", "type": NodeParameterType.COLLECTION, "display_name": "Labels", "default": "", "description": "Label to add to issue", "display_options": {'show': {'operation': ['create'], 'resource': ['issue']}}},
            {"name": "assignees", "type": NodeParameterType.COLLECTION, "display_name": "Assignees", "default": "", "description": "User to assign issue too", "display_options": {'show': {'operation': ['create'], 'resource': ['issue']}}},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The number of the issue on which to create the comment on", "display_options": {'show': {'operation': ['createComment'], 'resource': ['issue']}}},
            {"name": "editFields", "type": NodeParameterType.COLLECTION, "display_name": "Edit Fields", "default": "", "description": "User to assign issue to", "display_options": {'show': {'operation': ['edit'], 'resource': ['issue']}}},
            {"name": "lockReason", "type": NodeParameterType.OPTIONS, "display_name": "Lock Reason", "options": [
                {"name": "Off-Topic", "value": "off-topic"},
                {"name": "Too Heated", "value": "too heated"},
                {"name": "Resolved", "value": "resolved"},
                {"name": "Spam", "value": "spam"}
            ], "default": "resolved", "description": "The issue is Off-Topic", "display_options": {'show': {'operation': ['lock'], 'resource': ['issue']}}},
            {"name": "releaseTag", "type": NodeParameterType.STRING, "display_name": "Tag", "default": "", "required": True, "description": "The tag of the release", "display_options": {'show': {'operation': ['create'], 'resource': ['release']}}},
            {"name": "additionalFields", "type": NodeParameterType.COLLECTION, "display_name": "Additional Fields", "default": "", "description": "The name of the issue", "display_options": {'show': {'operation': ['create'], 'resource': ['release']}}},
            {"name": "release_id", "type": NodeParameterType.STRING, "display_name": "Release ID", "default": "", "required": True, "display_options": {'show': {'operation': ['get', 'delete', 'update'], 'resource': ['release']}}},
            {"name": "returnAll", "type": NodeParameterType.BOOLEAN, "display_name": "Return All", "default": False, "description": "Whether to return all results or only up to a given limit", "display_options": {'show': {'operation': ['getAll'], 'resource': ['release']}}},
            {"name": "limit", "type": NodeParameterType.NUMBER, "display_name": "Limit", "default": 50, "description": "Max number of results to return", "display_options": {'show': {'operation': ['getAll'], 'resource': ['release']}}},
            {"name": "getRepositoryIssuesFilters", "type": NodeParameterType.COLLECTION, "display_name": "Filters", "default": "", "description": "Return only issues which are assigned to a specific user", "display_options": {'show': {'operation': ['getIssues'], 'resource': ['repository']}}},
            {"name": "getRepositoryPullRequestsFilters", "type": NodeParameterType.COLLECTION, "display_name": "Filters", "default": "", "description": "Returns pull requests with any state", "display_options": {'show': {'operation': ['getPullRequests'], 'resource': ['repository']}}},
            {"name": "pullRequestNumber", "type": NodeParameterType.NUMBER, "display_name": "PR Number", "default": 0, "required": True, "description": "The number of the pull request", "display_options": {'show': {'operation': ['get', 'update'], 'resource': ['review']}}},
            {"name": "reviewId", "type": NodeParameterType.STRING, "display_name": "Review ID", "default": "", "required": True, "description": "ID of the review", "display_options": {'show': {'operation': ['get', 'update'], 'resource': ['review']}}},
            {"name": "event", "type": NodeParameterType.OPTIONS, "display_name": "Event", "options": [
                {"name": "Approve", "value": "approve"},
                {"name": "Request Change", "value": "requestChanges"},
                {"name": "Comment", "value": "comment"},
                {"name": "Pending", "value": "pending"}
            ], "default": "approve", "description": "Approve the pull request", "display_options": {'show': {'operation': ['create'], 'resource': ['review']}}},
            {"name": "organization", "type": NodeParameterType.STRING, "display_name": "Organization", "default": "", "required": True, "description": "The GitHub organization that the user is being invited to", "display_options": {'show': {'operation': ['invite'], 'resource': ['user']}}},
            {"name": "email", "type": NodeParameterType.STRING, "display_name": "Email", "default": "", "required": True, "description": "The email address of the invited user", "display_options": {'show': {'operation': ['invite'], 'resource': ['user']}}},
            {"name": "notice", "type": NodeParameterType.STRING, "display_name": "Only members with owner privileges for an organization or admin privileges for a repository can set up the webhooks this node requires.", "default": ""},
            {"name": "events", "type": NodeParameterType.MULTI_OPTIONS, "display_name": "Events", "options": [
                {"name": "*", "value": "*"},
                {"name": "Check Run", "value": "check_run"},
                {"name": "Check Suite", "value": "check_suite"},
                {"name": "Commit Comment", "value": "commit_comment"},
                {"name": "Create", "value": "create"},
                {"name": "Delete", "value": "delete"},
                {"name": "Deploy Key", "value": "deploy_key"},
                {"name": "Deployment", "value": "deployment"},
                {"name": "Deployment Status", "value": "deployment_status"},
                {"name": "Fork", "value": "fork"},
                {"name": "Github App Authorization", "value": "github_app_authorization"},
                {"name": "Gollum", "value": "gollum"},
                {"name": "Installation", "value": "installation"},
                {"name": "Installation Repositories", "value": "installation_repositories"},
                {"name": "Issue Comment", "value": "issue_comment"},
                {"name": "Issues", "value": "issues"},
                {"name": "Label", "value": "label"},
                {"name": "Marketplace Purchase", "value": "marketplace_purchase"},
                {"name": "Member", "value": "member"},
                {"name": "Membership", "value": "membership"},
                {"name": "Meta", "value": "meta"},
                {"name": "Milestone", "value": "milestone"},
                {"name": "Org Block", "value": "org_block"},
                {"name": "Organization", "value": "organization"},
                {"name": "Page Build", "value": "page_build"},
                {"name": "Project", "value": "project"},
                {"name": "Project Card", "value": "project_card"},
                {"name": "Project Column", "value": "project_column"},
                {"name": "Public", "value": "public"},
                {"name": "Pull Request", "value": "pull_request"},
                {"name": "Pull Request Review", "value": "pull_request_review"},
                {"name": "Pull Request Review Comment", "value": "pull_request_review_comment"},
                {"name": "Push", "value": "push"},
                {"name": "Release", "value": "release"},
                {"name": "Repository", "value": "repository"},
                {"name": "Repository Import", "value": "repository_import"},
                {"name": "Repository Vulnerability Alert", "value": "repository_vulnerability_alert"},
                {"name": "Security Advisory", "value": "security_advisory"},
                {"name": "Star", "value": "star"},
                {"name": "Status", "value": "status"},
                {"name": "Team", "value": "team"},
                {"name": "Team Add", "value": "team_add"},
                {"name": "Watch", "value": "watch"}
            ], "default": [], "required": True, "description": "Any time any event is triggered (Wildcard Event)"},
            {"name": "options", "type": NodeParameterType.COLLECTION, "display_name": "Options", "default": "", "description": "Whether the SSL certificate of the n8n host be verified by GitHub when delivering payloads"}
        ],
        "credentials": [
            {"name": "githubApi", "required": False},
            {"name": "githubOAuth2Api", "required": False}
        ]
    }
    
    icon = "github.svg"

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
                
                if resource == "file" and operation == "edit":
                    result = self._file_edit(i, item_data)
                elif resource == "file" and operation == "delete":
                    result = self._file_delete(i, item_data)
                elif resource == "file" and operation == "get":
                    result = self._file_get(i, item_data)
                elif resource == "file" and operation == "list":
                    result = self._file_list(i, item_data)
                elif resource == "issue" and operation == "create":
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
                elif resource == "repository" and operation == "listPopularPaths":
                    result = self._repository_listPopularPaths(i, item_data)
                elif resource == "repository" and operation == "listReferrers":
                    result = self._repository_listReferrers(i, item_data)
                elif resource == "repository" and operation == "get":
                    result = self._repository_get(i, item_data)
                elif resource == "repository" and operation == "getLicense":
                    result = self._repository_getLicense(i, item_data)
                elif resource == "repository" and operation == "getIssues":
                    result = self._repository_getIssues(i, item_data)
                elif resource == "repository" and operation == "getPullRequests":
                    result = self._repository_getPullRequests(i, item_data)
                elif resource == "review" and operation == "get":
                    result = self._review_get(i, item_data)
                elif resource == "review" and operation == "getAll":
                    result = self._review_getAll(i, item_data)
                elif resource == "review" and operation == "create":
                    result = self._review_create(i, item_data)
                elif resource == "review" and operation == "update":
                    result = self._review_update(i, item_data)
                elif resource == "user" and operation == "getRepositories":
                    result = self._user_getRepositories(i, item_data)
                elif resource == "user" and operation == "invite":
                    result = self._user_invite(i, item_data)
                elif resource == "organization" and operation == "getRepositories":
                    result = self._organization_getRepositories(i, item_data)
                elif resource == "workflow" and operation == "disable":
                    result = self._workflow_disable(i, item_data)
                elif resource == "workflow" and operation == "dispatch":
                    result = self._workflow_dispatch(i, item_data)
                elif resource == "workflow" and operation == "enable":
                    result = self._workflow_enable(i, item_data)
                elif resource == "workflow" and operation == "get":
                    result = self._workflow_get(i, item_data)
                elif resource == "workflow" and operation == "getUsage":
                    result = self._workflow_getUsage(i, item_data)
                elif resource == "workflow" and operation == "list":
                    result = self._workflow_list(i, item_data)
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
    BASE_URL = "https://api.github.com"
    
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
            credentials = self.get_credentials("githubOAuth2Api")
        else:
            credentials = self.get_credentials("githubApi")
        
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
            credentials = self.get_credentials("githubOAuth2Api")
        else:
            credentials = self.get_credentials("githubApi")
        
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


    def _file_edit(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        File Edit operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        
        # ============================================================================
        # LACK OF IMPLEMENTATION IN AVIDFLOW PLATFORM
        # ============================================================================
        # Operation: file/edit
        #
        # This operation requires async helper functions that are not available
        # in the AvidFlow platform. The TypeScript code uses:
        #   - getFile() or getFileSha() helper
        #   - Pattern: Get metadata → Extract file path → Download file
        #   - See: runtime/kb/binary_handling/file_download_pattern.py
        #   - async/await calls
        #   - Must be converted to synchronous requests
        #   - See: runtime/kb/async_to_sync/conversion_guide.py
        #
        # TODO: Implement this operation manually by:
        #   1. Reading the TypeScript source code for this operation
        #   2. Following patterns in runtime/kb/ for similar operations
        #   3. Using requests library with timeout (Celery+gevent safe)
        #   4. Testing with real API credentials
        # ============================================================================
        
        raise NotImplementedError(
            f'file/edit operation not yet implemented in AvidFlow platform. '
            'This operation requires complex logic or helper functions that are '
            'not available. See the TODO comment above for implementation guidance.'
        )

    def _file_delete(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        File Delete operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        additional_parameters = self.get_node_parameter('additionalParameters', item_index)
        message = self.get_node_parameter('commitMessage', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        file_path = self.get_node_parameter('filePath', item_index)
        
        # Build request body
        body = {'message': message}
        
        # Make API request
        response = self._api_request('DELETE', f'/repos/{owner}/{repository}/contents/{file_path}', body=body, query=None)
        
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
        additional_parameters = self.get_node_parameter('additionalParameters', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        file_path = self.get_node_parameter('filePath', item_index)
        
        # Build query parameters
        query = {}
        query['ref'] = additional_parameters.get('reference')
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/contents/{file_path}', body=None, query=query)
        
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
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        file_path = self.get_node_parameter('filePath', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/contents/{file_path}', body=None, query=None)
        
        return response

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
        body = self.get_node_parameter('body', item_index)
        labels = self.get_node_parameter('labels', item_index)
        assignees = self.get_node_parameter('assignees', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        title_text = self.get_node_parameter('title', item_index)
        body_text = self.get_node_parameter('body', item_index)
        
        # Build request body (avoid parameter shadowing)
        body = {'title': title_text, 'body': body, 'labels': labels, 'assignees': assignees}
        
        # Make API request
        response = self._api_request('POST', f'/repos/{owner}/{repository}/issues', body=body, query=None)
        
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
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        body_text = self.get_node_parameter('body', item_index)
        
        # Build request body (avoid parameter shadowing)
        body = {'body': body}
        
        # Make API request
        response = self._api_request('POST', f'/repos/{owner}/{repository}/issues/{issue_number}/comments', body=body, query=None)
        
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
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('PATCH', f'/repos/{owner}/{repository}/issues/{issue_number}', body=body, query=None)
        
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
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/issues/{issue_number}', body=None, query=None)
        
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
        lock_reason = self.get_node_parameter('lockReason', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Build query parameters
        query = {}
        query['lock_reason'] = lock_reason
        
        
        # Build request body (extracted parameters)
        body = {}
        # Make API request
        response = self._api_request('PUT', f'/repos/{owner}/{repository}/issues/{issue_number}/lock', body=body, query=query)
        
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
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Add required fields to body
        body['tag_name'] = tag_name
        
        # Make API request
        response = self._api_request('POST', f'/repos/{owner}/{repository}/releases', body=body, query=None)
        
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
        release_id = self.get_node_parameter('release_id', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('DELETE', f'/repos/{owner}/{repository}/releases/{release_id}', body=None, query=None)
        
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
        release_id = self.get_node_parameter('release_id', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/releases/{release_id}', body=None, query=None)
        
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
        return_all = self.get_node_parameter('returnAll', item_index)
        per_page = self.get_node_parameter('limit', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        if return_all:
            response = self._api_request_all_items('GET', f'/repos/{owner}/{repository}/releases', body=None, query=None)
        else:
            query = {}
            query['per_page'] = per_page
            response = self._api_request('GET', f'/repos/{owner}/{repository}/releases', body=None, query=query)
        
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
        release_id = self.get_node_parameter('release_id', item_index)
        body = self.get_node_parameter('additionalFields', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('PATCH', f'/repos/{owner}/{repository}/releases/{release_id}', body=body, query=None)
        
        return response

    def _repository_listPopularPaths(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repository Listpopularpaths operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/traffic/popular/paths', body=None, query=None)
        
        return response

    def _repository_listReferrers(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repository Listreferrers operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/traffic/popular/referrers', body=None, query=None)
        
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
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}', body=None, query=None)
        
        return response

    def _repository_getLicense(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repository Getlicense operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/license', body=None, query=None)
        
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
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        if return_all:
            response = self._api_request_all_items('GET', f'/repos/{owner}/{repository}/issues', body=None, query=None)
        else:
            query = {}
            query['per_page'] = per_page
            response = self._api_request('GET', f'/repos/{owner}/{repository}/issues', body=None, query=query)
        
        return response

    def _repository_getPullRequests(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repository Getpullrequests operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        qs = self.get_node_parameter('getRepositoryPullRequestsFilters', item_index)
        return_all = self.get_node_parameter('returnAll', item_index)
        per_page = self.get_node_parameter('limit', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        if return_all:
            response = self._api_request_all_items('GET', f'/repos/{owner}/{repository}/pulls', body=None, query=None)
        else:
            query = {}
            query['per_page'] = per_page
            response = self._api_request('GET', f'/repos/{owner}/{repository}/pulls', body=None, query=query)
        
        return response

    def _review_get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review Get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        review_id = self.get_node_parameter('reviewId', item_index)
        pull_request_number = self.get_node_parameter('pullRequestNumber', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/pulls/{pull_request_number}/reviews/{review_id}', body=None, query=None)
        
        return response

    def _review_getAll(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review Getall operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        return_all = self.get_node_parameter('returnAll', item_index)
        pull_request_number = self.get_node_parameter('pullRequestNumber', item_index)
        per_page = self.get_node_parameter('limit', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        if return_all:
            response = self._api_request_all_items('GET', f'/repos/{owner}/{repository}/pulls/{pull_request_number}/reviews', body=None, query=None)
        else:
            query = {}
            query['per_page'] = per_page
            response = self._api_request('GET', f'/repos/{owner}/{repository}/pulls/{pull_request_number}/reviews', body=None, query=query)
        
        return response

    def _review_create(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review Create operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        pull_request_number = self.get_node_parameter('pullRequestNumber', item_index)
        additional_fields = self.get_node_parameter('additionalFields', item_index)
        body = self.get_node_parameter('body', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        event_text = self.get_node_parameter('event', item_index)
        body_text = self.get_node_parameter('body', item_index)
        
        # Add required fields to body
        body['event'] = event_text
        body['event'] = body_text
        
        # Make API request
        response = self._api_request('POST', f'/repos/{owner}/{repository}/pulls/{pull_request_number}/reviews', body=body, query=None)
        
        return response

    def _review_update(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review Update operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        pull_request_number = self.get_node_parameter('pullRequestNumber', item_index)
        review_id = self.get_node_parameter('reviewId', item_index)
        body = self.get_node_parameter('body', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        body_text = self.get_node_parameter('body', item_index)
        
        # Build request body (avoid parameter shadowing)
        body = {'body': body}
        
        # Make API request
        response = self._api_request('PUT', f'/repos/{owner}/{repository}/pulls/{pull_request_number}/reviews/{review_id}', body=body, query=None)
        
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
        return_all = self.get_node_parameter('returnAll', item_index)
        per_page = self.get_node_parameter('limit', item_index)
        owner = self.get_node_parameter('owner', item_index)
        
        # Make API request
        if return_all:
            response = self._api_request_all_items('GET', f'/users/{owner}/repos', body=None, query=None)
        else:
            query = {}
            query['per_page'] = per_page
            response = self._api_request('GET', f'/users/{owner}/repos', body=None, query=query)
        
        return response

    def _user_invite(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        User Invite operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        org = self.get_node_parameter('organization', item_index)
        email = self.get_node_parameter('email', item_index)
        email_text = self.get_node_parameter('email', item_index)
        
        # Build request body
        body = {'email': email_text}
        
        # Make API request
        response = self._api_request('POST', f'/orgs/{org}/invitations', body=body, query=None)
        
        return response

    def _organization_getRepositories(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Organization Getrepositories operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        return_all = self.get_node_parameter('returnAll', item_index)
        per_page = self.get_node_parameter('limit', item_index)
        owner = self.get_node_parameter('owner', item_index)
        
        # Make API request
        if return_all:
            response = self._api_request_all_items('GET', f'/orgs/{owner}/repos', body=None, query=None)
        else:
            query = {}
            query['per_page'] = per_page
            response = self._api_request('GET', f'/orgs/{owner}/repos', body=None, query=query)
        
        return response

    def _workflow_disable(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Workflow Disable operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        workflow_id = self.get_node_parameter('workflowId', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        
        # Build request body (extracted parameters)
        body = {}
        # Make API request
        response = self._api_request('PUT', f'/repos/{owner}/{repository}/actions/workflows/{workflow_id}/disable', body=body, query=None)
        
        return response

    def _workflow_dispatch(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Workflow Dispatch operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        workflow_id = self.get_node_parameter('workflowId', item_index)
        ref = self.get_node_parameter('ref', item_index)
        # Parse JSON parameter 'inputs'
        inputs_str = self.get_node_parameter('inputs', item_index)
        try:
            import json
            inputs = json.loads(inputs_str) if inputs_str else {}
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in 'inputs' parameter")
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Build request body
        body = {'ref': ref, 'inputs': inputs}
        
        # Make API request
        response = self._api_request('POST', f'/repos/{owner}/{repository}/actions/workflows/{workflow_id}/dispatches', body=body, query=None)
        
        return response

    def _workflow_enable(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Workflow Enable operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        workflow_id = self.get_node_parameter('workflowId', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        
        # Build request body (extracted parameters)
        body = {}
        # Make API request
        response = self._api_request('PUT', f'/repos/{owner}/{repository}/actions/workflows/{workflow_id}/enable', body=body, query=None)
        
        return response

    def _workflow_get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Workflow Get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        workflow_id = self.get_node_parameter('workflowId', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/actions/workflows/{workflow_id}', body=None, query=None)
        
        return response

    def _workflow_getUsage(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Workflow Getusage operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        workflow_id = self.get_node_parameter('workflowId', item_index)
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/actions/workflows/{workflow_id}/timing', body=None, query=None)
        
        return response

    def _workflow_list(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Workflow List operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        owner = self.get_node_parameter('owner', item_index)
        repository = self.get_node_parameter('repository', item_index)
        
        # Make API request
        response = self._api_request('GET', f'/repos/{owner}/{repository}/actions/workflows', body=None, query=None)
        
        return response

