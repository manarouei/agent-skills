#!/usr/bin/env python3
"""
Github Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: node-github-007
Generated: 2026-01-06T08:11:07.913121

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
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Get Repositories", "value": "getRepositories", "description": "Returns all repositories of an organization"},
                {"name": "checkExists", "value": "checkExists", "description": "Operation: checkExists"},
                {"name": "create", "value": "create", "description": "Operation: create"},
                {"name": "webhook", "value": "webhook", "description": "Operation: webhook"},
                {"name": "getUsers", "value": "getUsers", "description": "Operation: getUsers"},
                {"name": "getRepositories", "value": "getRepositories", "description": "Operation: getRepositories"},
                {"name": "getWorkflows", "value": "getWorkflows", "description": "Operation: getWorkflows"},
                {"name": "getRefs", "value": "getRefs", "description": "Operation: getRefs"}
            ], "default": "getRepositories", "description": "Operation to perform"},
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Authentication", "options": [
                {"name": "Access Token", "value": "accessToken"},
                {"name": "OAuth2", "value": "oAuth2"}
            ], "default": "accessToken"},
            {"name": "OAuth2", "type": NodeParameterType.OPTIONS, "display_name": "Access Token"},
            {"name": "Issue", "type": NodeParameterType.OPTIONS, "display_name": "File"},
            {"name": "Create Comment", "type": NodeParameterType.OPTIONS, "display_name": "Create", "description": "Create a new issue"},
            {"name": "Delete", "type": NodeParameterType.OPTIONS, "display_name": "Create", "description": "Create a new file in repository"},
            {"name": "Get Issues", "type": NodeParameterType.OPTIONS, "display_name": "Get", "description": "Get the data of a single repository"},
            {"name": "Invite", "type": NodeParameterType.OPTIONS, "display_name": "Get Repositories", "description": "Returns the repositories of a user"},
            {"name": "Delete", "type": NodeParameterType.OPTIONS, "display_name": "Create", "description": "Creates a new release"},
            {"name": "Get", "type": NodeParameterType.OPTIONS, "display_name": "Create", "description": "Creates a new review"},
            {"name": "Dispatch", "type": NodeParameterType.STRING, "display_name": "Disable", "description": "Disable a workflow"},
            {"name": "owner", "type": NodeParameterType.STRING, "display_name": "Repository Owner", "default": "{ mode: 'list", "required": True},
            {"name": "list", "type": NodeParameterType.STRING, "display_name": "Repository Owner"},
            {"name": "url", "type": NodeParameterType.STRING, "display_name": "Link"},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "By Name"},
            {"name": "repository", "type": NodeParameterType.STRING, "display_name": "Repository Name", "default": "{", "required": True},
            {"name": "list", "type": NodeParameterType.STRING, "display_name": "Repository Name"},
            {"name": "url", "type": NodeParameterType.STRING, "display_name": "Link"},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "By Name"},
            {"name": "workflowId", "type": NodeParameterType.STRING, "display_name": "Workflow", "default": "{", "required": True, "description": "The workflow to dispatch", "display_options": {'show': {'operation': ['disable', 'dispatch', 'dispatchAndWait', 'get', 'getUsage', 'enable']}}},
            {"name": "list", "type": NodeParameterType.STRING, "display_name": "Workflow"},
            {"name": "filename", "type": NodeParameterType.STRING, "display_name": "By File Name"},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "By ID"},
            {"name": "ref", "type": NodeParameterType.STRING, "display_name": "Ref", "default": "main", "required": True, "description": "The git reference for the workflow dispatch (branch or tag name)", "display_options": {'show': {'operation': ['dispatch', 'dispatchAndWait']}}},
            {"name": "ref", "type": NodeParameterType.STRING, "display_name": "Ref", "default": "{", "required": True, "description": "The git reference for the workflow dispatch (branch, tag, or commit SHA)", "display_options": {'show': {'operation': ['dispatch', 'dispatchAndWait']}}},
            {"name": "list", "type": NodeParameterType.STRING, "display_name": "From List"},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "By Name"},
            {"name": "inputs", "type": NodeParameterType.JSON, "display_name": "Inputs", "default": "{", "description": "JSON object with input parameters for the workflow", "display_options": {'show': {'operation': ['dispatch', 'dispatchAndWait']}}},
            {"name": "filePath", "type": NodeParameterType.STRING, "display_name": "File Path", "default": "", "required": True, "description": "The file path of the file. Has to contain the full path."},
            {"name": "filePath", "type": NodeParameterType.STRING, "display_name": "Path", "default": "", "description": "The path of the folder to list", "display_options": {'show': {'operation': ['list']}}},
            {"name": "binaryData", "type": NodeParameterType.BOOLEAN, "display_name": "Binary File", "default": False, "required": True, "description": "Whether the data to upload should be taken from binary field", "display_options": {'show': {'operation': ['create', 'edit']}}},
            {"name": "fileContent", "type": NodeParameterType.STRING, "display_name": "File Content", "default": "", "required": True, "description": "The text content of the file", "display_options": {'show': {'operation': ['create', 'edit']}}},
            {"name": "binaryPropertyName", "type": NodeParameterType.STRING, "display_name": "Input Binary Field", "default": "data", "required": True, "display_options": {'show': {'operation': ['create', 'edit']}}},
            {"name": "commitMessage", "type": NodeParameterType.STRING, "display_name": "Commit Message", "default": "", "required": True, "display_options": {'show': {'operation': ['create', 'delete', 'edit']}}},
            {"name": "additionalParameters", "type": NodeParameterType.COLLECTION, "display_name": "Additional Parameters", "default": "{", "description": "Additional fields to add", "display_options": {'show': {'operation': ['create', 'delete', 'edit']}}},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "author", "default": "", "description": "The name of the author of the commit"},
            {"name": "email", "type": NodeParameterType.STRING, "display_name": "Email", "default": "", "description": "The email of the author of the commit"},
            {"name": "branch", "type": NodeParameterType.STRING, "display_name": "branch", "default": "", "description": "The branch to commit to. If not set the repository’s default branch (usually master) is used."},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "committer", "default": "", "description": "The name of the committer of the commit"},
            {"name": "email", "type": NodeParameterType.STRING, "display_name": "Email", "default": "", "description": "The email of the committer of the commit"},
            {"name": "asBinaryProperty", "type": NodeParameterType.BOOLEAN, "display_name": "As Binary Property", "default": True, "description": "Whether to set the data of the file as binary property instead of returning the raw API response", "display_options": {'show': {'operation': ['get']}}},
            {"name": "binaryPropertyName", "type": NodeParameterType.STRING, "display_name": "Put Output File in Field", "default": "data", "required": True, "display_options": {'show': {'operation': ['get']}}},
            {"name": "additionalParameters", "type": NodeParameterType.COLLECTION, "display_name": "Additional Parameters", "default": "{", "description": "Additional fields to add", "display_options": {'show': {'operation': ['get']}}},
            {"name": "reference", "type": NodeParameterType.STRING, "display_name": "Reference", "default": "", "description": "The name of the commit/branch/tag. Default: the repository’s default branch (usually master)."},
            {"name": "title", "type": NodeParameterType.STRING, "display_name": "Title", "default": "", "required": True, "description": "The title of the issue", "display_options": {'show': {'operation': ['create']}}},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the issue", "display_options": {'show': {'operation': ['create']}}},
            {"name": "labels", "type": NodeParameterType.COLLECTION, "display_name": "Labels", "default": "{ label: ", "description": "Label to add to issue", "display_options": {'show': {'operation': ['create']}}},
            {"name": "label", "type": NodeParameterType.STRING, "display_name": "Label", "default": "", "description": "Label to add to issue"},
            {"name": "assignees", "type": NodeParameterType.COLLECTION, "display_name": "Assignees", "default": "{ assignee: ", "description": "User to assign issue too", "display_options": {'show': {'operation': ['create']}}},
            {"name": "assignee", "type": NodeParameterType.STRING, "display_name": "Assignee", "default": "", "description": "User to assign issue too"},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The number of the issue on which to create the comment on", "display_options": {'show': {'operation': ['createComment']}}},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the comment", "display_options": {'show': {'operation': ['createComment']}}},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The number of the issue edit", "display_options": {'show': {'operation': ['edit']}}},
            {"name": "editFields", "type": NodeParameterType.COLLECTION, "display_name": "Edit Fields", "default": "{", "description": "User to assign issue to", "display_options": {'show': {'operation': ['edit']}}},
            {"name": "assignees", "type": NodeParameterType.COLLECTION, "display_name": "Assignees", "default": "{ assignee: ", "description": "User to assign issue to"},
            {"name": "assignee", "type": NodeParameterType.STRING, "display_name": "Assignees", "default": "", "description": "User to assign issue to"},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the issue"},
            {"name": "labels", "type": NodeParameterType.COLLECTION, "display_name": "Labels", "default": "{ label: ", "description": "Label to add to issue"},
            {"name": "label", "type": NodeParameterType.STRING, "display_name": "Label", "default": "", "description": "Label to add to issue"},
            {"name": "state", "type": NodeParameterType.OPTIONS, "display_name": "State", "options": [
                {"name": "Closed", "value": "closed"},
                {"name": "Open", "value": "open"}
            ], "default": "open", "description": "Set the state to "},
            {"name": "Open", "type": NodeParameterType.OPTIONS, "display_name": "Closed", "description": "Set the state to "},
            {"name": "Not Planned", "type": NodeParameterType.STRING, "display_name": "Completed", "description": "Issue is completed"},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The issue number to get data for", "display_options": {'show': {'operation': ['get']}}},
            {"name": "issueNumber", "type": NodeParameterType.NUMBER, "display_name": "Issue Number", "default": 0, "required": True, "description": "The issue number to lock", "display_options": {'show': {'operation': ['lock']}}},
            {"name": "lockReason", "type": NodeParameterType.OPTIONS, "display_name": "Lock Reason", "options": [
                {"name": "Off-Topic", "value": "off-topic"},
                {"name": "Too Heated", "value": "too heated"},
                {"name": "Resolved", "value": "resolved"},
                {"name": "Spam", "value": "spam"}
            ], "default": "resolved", "description": "The issue is Off-Topic", "display_options": {'show': {'operation': ['lock']}}},
            {"name": "Too Heated", "type": NodeParameterType.STRING, "display_name": "Off-Topic", "description": "The issue is Off-Topic"},
            {"name": "additionalFields", "type": NodeParameterType.COLLECTION, "display_name": "Additional Fields", "default": "{", "description": "The name of the issue", "display_options": {'show': {'operation': ['create']}}},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "Name", "default": "", "description": "The name of the issue"},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the release"},
            {"name": "draft", "type": NodeParameterType.BOOLEAN, "display_name": "Draft", "default": False, "description": "Whether to create a draft (unpublished) release, "},
            {"name": "prerelease", "type": NodeParameterType.BOOLEAN, "display_name": "Prerelease", "default": False, "description": "Whether to point out that the release is non-production ready"},
            {"name": "target_commitish", "type": NodeParameterType.STRING, "display_name": "Target Commitish", "default": "", "description": "Specifies the commitish value that determines where the Git tag is created from. Can be any branch or commit SHA. Unused if the Git tag already exists. Default: the repository"},
            {"name": "release_id", "type": NodeParameterType.STRING, "display_name": "Release ID", "default": "", "required": True, "display_options": {'show': {'operation': ['get', 'delete', 'update']}}},
            {"name": "additionalFields", "type": NodeParameterType.COLLECTION, "display_name": "Additional Fields", "default": "{", "description": "The body of the release", "display_options": {'show': {'operation': ['update']}}},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the release"},
            {"name": "draft", "type": NodeParameterType.BOOLEAN, "display_name": "Draft", "default": False, "description": "Whether to create a draft (unpublished) release, "},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "Name", "default": "", "description": "The name of the release"},
            {"name": "prerelease", "type": NodeParameterType.BOOLEAN, "display_name": "Prerelease", "default": False, "description": "Whether to point out that the release is non-production ready"},
            {"name": "tag_name", "type": NodeParameterType.STRING, "display_name": "Tag Name", "default": "", "description": "The name of the tag"},
            {"name": "target_commitish", "type": NodeParameterType.STRING, "display_name": "Target Commitish", "default": "", "description": "Specifies the commitish value that determines where the Git tag is created from. Can be any branch or commit SHA. Unused if the Git tag already exists. Default: the repository"},
            {"name": "returnAll", "type": NodeParameterType.BOOLEAN, "display_name": "Return All", "default": False, "description": "Whether to return all results or only up to a given limit", "display_options": {'show': {'operation': ['getAll']}}},
            {"name": "limit", "type": NodeParameterType.NUMBER, "display_name": "Limit", "default": 50, "description": "Max number of results to return", "display_options": {'show': {'operation': ['getAll']}}},
            {"name": "returnAll", "type": NodeParameterType.BOOLEAN, "display_name": "Return All", "default": False, "description": "Whether to return all results or only up to a given limit", "display_options": {'show': {'operation': ['getIssues']}}},
            {"name": "limit", "type": NodeParameterType.NUMBER, "display_name": "Limit", "default": 50, "description": "Max number of results to return", "display_options": {'show': {'operation': ['getIssues']}}},
            {"name": "getRepositoryIssuesFilters", "type": NodeParameterType.COLLECTION, "display_name": "Filters", "default": "{", "description": "Return only issues which are assigned to a specific user", "display_options": {'show': {'operation': ['getIssues']}}},
            {"name": "assignee", "type": NodeParameterType.STRING, "display_name": "Assignee", "default": "", "description": "Return only issues which are assigned to a specific user"},
            {"name": "creator", "type": NodeParameterType.STRING, "display_name": "Creator", "default": "", "description": "Return only issues which were created by a specific user"},
            {"name": "mentioned", "type": NodeParameterType.STRING, "display_name": "Mentioned", "default": "", "description": "Return only issues in which a specific user was mentioned"},
            {"name": "labels", "type": NodeParameterType.STRING, "display_name": "Labels", "default": "", "description": "Return only issues with the given labels. Multiple labels can be separated by comma."},
            {"name": "since", "type": NodeParameterType.STRING, "display_name": "Updated Since", "default": "", "description": "Return only issues updated at or after this time"},
            {"name": "state", "type": NodeParameterType.OPTIONS, "display_name": "State", "options": [
                {"name": "All", "value": "all"},
                {"name": "Closed", "value": "closed"},
                {"name": "Open", "value": "open"}
            ], "default": "open", "description": "Returns issues with any state"},
            {"name": "Closed", "type": NodeParameterType.OPTIONS, "display_name": "All", "description": "Returns issues with any state"},
            {"name": "Updated", "type": NodeParameterType.OPTIONS, "display_name": "Created", "description": "Sort by created date"},
            {"name": "Descending", "type": NodeParameterType.BOOLEAN, "display_name": "Ascending", "description": "Sort in ascending order"},
            {"name": "limit", "type": NodeParameterType.NUMBER, "display_name": "Limit", "default": 50, "description": "Max number of results to return. Maximum value is <a href=", "display_options": {'show': {'operation': ['getPullRequests']}}},
            {"name": "getRepositoryPullRequestsFilters", "type": NodeParameterType.COLLECTION, "display_name": "Filters", "default": "{", "description": "Returns pull requests with any state", "display_options": {'show': {'operation': ['getPullRequests']}}},
            {"name": "state", "type": NodeParameterType.OPTIONS, "display_name": "State", "options": [
                {"name": "All", "value": "all"},
                {"name": "Closed", "value": "closed"},
                {"name": "Open", "value": "open"}
            ], "default": "open", "description": "Returns pull requests with any state"},
            {"name": "Closed", "type": NodeParameterType.OPTIONS, "display_name": "All", "description": "Returns pull requests with any state"},
            {"name": "Updated", "type": NodeParameterType.OPTIONS, "display_name": "Created", "description": "Sort by created date"},
            {"name": "Descending", "type": NodeParameterType.NUMBER, "display_name": "Ascending", "description": "Sort in ascending order"},
            {"name": "reviewId", "type": NodeParameterType.STRING, "display_name": "Review ID", "default": "", "required": True, "description": "ID of the review", "display_options": {'show': {'operation': ['get', 'update']}}},
            {"name": "pullRequestNumber", "type": NodeParameterType.NUMBER, "display_name": "PR Number", "default": 0, "required": True, "description": "The number of the pull request", "display_options": {'show': {'operation': ['getAll']}}},
            {"name": "returnAll", "type": NodeParameterType.BOOLEAN, "display_name": "Return All", "default": False, "description": "Whether to return all results or only up to a given limit", "display_options": {'show': {'operation': ['getAll']}}},
            {"name": "limit", "type": NodeParameterType.NUMBER, "display_name": "Limit", "default": 50, "description": "Max number of results to return", "display_options": {'show': {'operation': ['getAll']}}},
            {"name": "pullRequestNumber", "type": NodeParameterType.NUMBER, "display_name": "PR Number", "default": 0, "required": True, "description": "The number of the pull request to review", "display_options": {'show': {'operation': ['create']}}},
            {"name": "event", "type": NodeParameterType.OPTIONS, "display_name": "Event", "options": [
                {"name": "Approve", "value": "approve"},
                {"name": "Request Change", "value": "requestChanges"},
                {"name": "Comment", "value": "comment"},
                {"name": "Pending", "value": "pending"}
            ], "default": "approve", "description": "Approve the pull request", "display_options": {'show': {'operation': ['create']}}},
            {"name": "Request Change", "type": NodeParameterType.STRING, "display_name": "Approve", "description": "Approve the pull request"},
            {"name": "additionalFields", "type": NodeParameterType.COLLECTION, "display_name": "Additional Fields", "default": "{", "description": "The SHA of the commit that needs a review, if different from the latest", "display_options": {'show': {'operation': ['create']}}},
            {"name": "commitId", "type": NodeParameterType.STRING, "display_name": "Commit ID", "default": "", "description": "The SHA of the commit that needs a review, if different from the latest"},
            {"name": "body", "type": NodeParameterType.STRING, "display_name": "Body", "default": "", "description": "The body of the review", "display_options": {'show': {'operation': ['update']}}},
            {"name": "returnAll", "type": NodeParameterType.BOOLEAN, "display_name": "Return All", "default": False, "description": "Whether to return all results or only up to a given limit", "display_options": {'show': {'operation': ['getRepositories']}}},
            {"name": "limit", "type": NodeParameterType.NUMBER, "display_name": "Limit", "default": 50, "description": "Max number of results to return", "display_options": {'show': {'operation': ['getRepositories']}}},
            {"name": "organization", "type": NodeParameterType.STRING, "display_name": "Organization", "default": "", "required": True, "description": "The GitHub organization that the user is being invited to", "display_options": {'show': {'operation': ['invite']}}},
            {"name": "email", "type": NodeParameterType.STRING, "display_name": "Email", "default": "", "required": True, "description": "The email address of the invited user", "display_options": {'show': {'operation': ['invite']}}},
            {"name": "returnAll", "type": NodeParameterType.BOOLEAN, "display_name": "Return All", "default": False, "description": "Whether to return all results or only up to a given limit", "display_options": {'show': {'operation': ['getRepositories']}}},
            {"name": "limit", "type": NodeParameterType.NUMBER, "display_name": "Limit", "default": 50, "description": "Max number of results to return", "display_options": {'show': {'operation': ['getRepositories']}}},
            {"name": "notice", "type": NodeParameterType.STRING, "display_name": "Only members with owner privileges for an organization or admin privileges for a repository can set up the webhooks this node requires.", "default": ""},
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Authentication", "options": [
                {"name": "Access Token", "value": "accessToken"},
                {"name": "OAuth2", "value": "oAuth2"}
            ], "default": "accessToken"},
            {"name": "OAuth2", "type": NodeParameterType.STRING, "display_name": "Access Token"},
            {"name": "list", "type": NodeParameterType.STRING, "display_name": "Repository Owner", "required": True},
            {"name": "url", "type": NodeParameterType.STRING, "display_name": "Link"},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "By Name"},
            {"name": "repository", "type": NodeParameterType.STRING, "display_name": "Repository Name", "default": "{ mode: 'list", "required": True},
            {"name": "list", "type": NodeParameterType.STRING, "display_name": "Repository Name"},
            {"name": "url", "type": NodeParameterType.STRING, "display_name": "Link"},
            {"name": "name", "type": NodeParameterType.STRING, "display_name": "By Name"},
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
            ], "default": "[]", "required": True, "description": "Any time any event is triggered (Wildcard Event)"},
            {"name": "Check Run", "type": NodeParameterType.COLLECTION, "display_name": "*", "description": "Any time any event is triggered (Wildcard Event)"},
            {"name": "insecureSSL", "type": NodeParameterType.BOOLEAN, "display_name": "Insecure SSL", "default": False, "description": "Whether the SSL certificate of the n8n host be verified by GitHub when delivering payloads"}
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
                operation = self.get_node_parameter("operation", i)
                item_data = item.json_data if hasattr(item, 'json_data') else item.get('json', {})
                
                if operation == "getRepositories":
                    result = self._getRepositories(i, item_data)
                elif operation == "checkExists":
                    result = self._checkExists(i, item_data)
                elif operation == "create":
                    result = self._create(i, item_data)
                elif operation == "webhook":
                    result = self._webhook(i, item_data)
                elif operation == "getUsers":
                    result = self._getUsers(i, item_data)
                elif operation == "getRepositories":
                    result = self._getRepositories(i, item_data)
                elif operation == "getWorkflows":
                    result = self._getWorkflows(i, item_data)
                elif operation == "getRefs":
                    result = self._getRefs(i, item_data)
                else:
                    raise ValueError(f"Unknown operation: {operation}")
                
                # Handle array results
                if isinstance(result, list):
                    for r in result:
                        return_items.append(NodeExecutionData(json_data=r))
                else:
                    return_items.append(NodeExecutionData(json_data=result))
                    
            except Exception as e:
                logger.error(f"Error in operation {operation}: {e}")
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

    def _getRepositories(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        getRepositories operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("getRepositories operation not implemented")

    def _checkExists(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        checkExists operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("checkExists operation not implemented")

    def _create(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        create operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("create operation not implemented")

    def _webhook(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        webhook operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("webhook operation not implemented")

    def _getUsers(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        getUsers operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("getUsers operation not implemented")

    def _getRepositories(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        getRepositories operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("getRepositories operation not implemented")

    def _getWorkflows(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        getWorkflows operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("getWorkflows operation not implemented")

    def _getRefs(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        getRefs operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("getRefs operation not implemented")

