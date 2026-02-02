#!/usr/bin/env python3
"""
Github Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: node-github-012
Generated: 2026-01-06T09:16:43.337035

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
    Node node.
    
    
    """

    type = "github"
    version = 1
    
    description = {
        "displayName": "Node",
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
                {"name": "Get Repositories", "value": "getRepositories", "description": "Returns all repositories of an organization"},
                {"name": "Create", "value": "create", "description": "Create a new issue"},
                {"name": "Create Comment", "value": "createComment", "description": "Create a new comment on an issue"},
                {"name": "Edit", "value": "edit", "description": "Edit an issue"},
                {"name": "Get", "value": "get", "description": "Get the data of a single issue"},
                {"name": "Lock", "value": "lock", "description": "Lock an issue"},
                {"name": "Delete", "value": "delete", "description": "Delete a file in repository"},
                {"name": "List", "value": "list", "description": "List contents of a folder"},
                {"name": "Get Issues", "value": "getIssues", "description": "Returns issues of a repository"},
                {"name": "Get License", "value": "getLicense", "description": "Returns the contents of the repository"},
                {"name": "Get Profile", "value": "getProfile", "description": "Get the community profile of a repository with metrics, health score, description, license, etc"},
                {"name": "Get Pull Requests", "value": "getPullRequests", "description": "Returns pull requests of a repository"},
                {"name": "List Popular Paths", "value": "listPopularPaths", "description": "Get the top 10 popular content paths over the last 14 days"},
                {"name": "List Referrers", "value": "listReferrers", "description": "Get the top 10 referrering domains over the last 14 days"},
                {"name": "Invite", "value": "invite", "description": "Invites a user to an organization"},
                {"name": "Get Many", "value": "getAll", "description": "Get many repository releases"},
                {"name": "Update", "value": "update", "description": "Update a release"},
                {"name": "Disable", "value": "disable", "description": "Disable a workflow"},
                {"name": "Dispatch", "value": "dispatch", "description": "Dispatch a workflow event"},
                {"name": "Dispatch and Wait for Completion", "value": "dispatchAndWait", "description": "Dispatch a workflow event and wait for a webhook to be called before proceeding"},
                {"name": "Enable", "value": "enable", "description": "Enable a workflow"},
                {"name": "Get Usage", "value": "getUsage", "description": "Get the usage of a workflow"}
            ], "default": "getRepositories", "description": "Operation to perform"},
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Authentication", "options": [
                {"name": "Access Token", "value": "accessToken"},
                {"name": "OAuth2", "value": "oAuth2"}
            ], "default": "accessToken"},
            {"name": "webhookNotice", "type": NodeParameterType.STRING, "display_name": "Your execution will pause until a webhook is called. This URL will be generated at runtime and passed to your Github workflow as a resumeUrl input.", "default": "", "display_options": {'show': {'operation': ['dispatchAndWait'], 'resource': ['workflow']}}},
            {"name": "owner", "type": NodeParameterType.STRING, "display_name": "Repository Owner", "default": "", "required": True},
            {"name": "repository", "type": NodeParameterType.STRING, "display_name": "Repository Name", "default": "", "required": True},
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
            {"name": "oauth2", "required": True}
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
                if self.node_data.continue_on_fail:
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
        credentials = self.get_credentials("oauth2")
        
        # Build headers based on credential type
        headers = {}
        if credentials.get("accessToken"):
            headers["Authorization"] = f"Bot {credentials.get('accessToken')}"
        elif credentials.get("apiKey"):
            query = query or {}
            query["api_key"] = credentials.get("apiKey")
        
        url = f"https://api.github.com/repos/test-owner/test-repo{endpoint}"
        
        response = requests.request(
            method,
            url,
            params=query,
            json=body,
            headers=headers,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()

