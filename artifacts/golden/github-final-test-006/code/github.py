#!/usr/bin/env python3
"""
Github Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: github-final-test-006
Generated: 2026-02-02T14:47:58.538015

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from .base import BaseNode, NodeParameter, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class GithubNode(BaseNode):
    """
    Github node.
    
    
    """

    node_type = "github"
    node_version = 1
    display_name = "Github"
    description = ""
    icon = "file:github.svg"
    group = ['output']
    
    credentials = [
        {
            "name": "githubApi",
            "required": True,
        }
    ]

    properties = [
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Authentication", "options": [
                {"name": "Githubapi", "value": "githubApi"},
                {"name": "Githuboauth2api", "value": "githubOAuth2Api"}
            ], "default": "githubApi", "description": "Authentication method to use"},
            {"name": "resource", "type": NodeParameterType.OPTIONS, "display_name": "Resource", "options": [
                {"name": "Organization", "value": "organization"},
                {"name": "Issue", "value": "issue"},
                {"name": "File", "value": "file"},
                {"name": "Repository", "value": "repository"},
                {"name": "User", "value": "user"},
                {"name": "Release", "value": "release"},
                {"name": "Review", "value": "review"},
                {"name": "Workflow", "value": "workflow"}
            ], "default": "organization", "description": "The resource to operate on"},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create workflow"},
                {"name": "Delete", "value": "delete", "description": "Delete workflow"},
                {"name": "Get", "value": "get", "description": "Get workflow"},
                {"name": "Get Many", "value": "getAll", "description": "Get many workflows"},
                {"name": "Update", "value": "update", "description": "Update workflow"}
            ], "default": "create", "description": "Operation to perform on workflow", "display_options": {'show': {'resource': ['workflow']}}},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create review"},
                {"name": "Delete", "value": "delete", "description": "Delete review"},
                {"name": "Get", "value": "get", "description": "Get review"},
                {"name": "Get Many", "value": "getAll", "description": "Get many reviews"},
                {"name": "Update", "value": "update", "description": "Update review"}
            ], "default": "create", "description": "Operation to perform on review", "display_options": {'show': {'resource': ['review']}}},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create release"},
                {"name": "Delete", "value": "delete", "description": "Delete release"},
                {"name": "Get", "value": "get", "description": "Get release"},
                {"name": "Get Many", "value": "getAll", "description": "Get many releases"},
                {"name": "Update", "value": "update", "description": "Update release"}
            ], "default": "create", "description": "Operation to perform on release", "display_options": {'show': {'resource': ['release']}}},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create user"},
                {"name": "Delete", "value": "delete", "description": "Delete user"},
                {"name": "Get", "value": "get", "description": "Get user"},
                {"name": "Get Many", "value": "getAll", "description": "Get many users"},
                {"name": "Update", "value": "update", "description": "Update user"}
            ], "default": "create", "description": "Operation to perform on user", "display_options": {'show': {'resource': ['user']}}},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create repository"},
                {"name": "Delete", "value": "delete", "description": "Delete repository"},
                {"name": "Get", "value": "get", "description": "Get repository"},
                {"name": "Get Many", "value": "getAll", "description": "Get many repositorys"},
                {"name": "Update", "value": "update", "description": "Update repository"}
            ], "default": "create", "description": "Operation to perform on repository", "display_options": {'show': {'resource': ['repository']}}},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create file"},
                {"name": "Delete", "value": "delete", "description": "Delete file"},
                {"name": "Get", "value": "get", "description": "Get file"},
                {"name": "Get Many", "value": "getAll", "description": "Get many files"},
                {"name": "Update", "value": "update", "description": "Update file"}
            ], "default": "create", "description": "Operation to perform on file", "display_options": {'show': {'resource': ['file']}}},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create issue"},
                {"name": "Delete", "value": "delete", "description": "Delete issue"},
                {"name": "Get", "value": "get", "description": "Get issue"},
                {"name": "Get Many", "value": "getAll", "description": "Get many issues"},
                {"name": "Update", "value": "update", "description": "Update issue"}
            ], "default": "create", "description": "Operation to perform on issue", "display_options": {'show': {'resource': ['issue']}}},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create organization"},
                {"name": "Delete", "value": "delete", "description": "Delete organization"},
                {"name": "Get", "value": "get", "description": "Get organization"},
                {"name": "Get Many", "value": "getAll", "description": "Get many organizations"},
                {"name": "Update", "value": "update", "description": "Update organization"}
            ], "default": "create", "description": "Operation to perform on organization", "display_options": {'show': {'resource': ['organization']}}},
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
            {"name": "asBinaryProperty", "type": NodeParameterType.BOOLEAN, "display_name": "As Binary Property", "default": True, "description": "Whether to set the data of the file property instead of returning the raw API response", "display_options": {'show': {'operation': ['get']}}},
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
        credentials = self.get_credentials("githubApi")
        
        # TODO: Configure authentication based on credential type
        query = query or {}
        # For API key auth: query["api_key"] = credentials.get("apiKey")
        # For Bearer auth: headers["Authorization"] = f"Bearer {credentials.get('accessToken')}"
        
        url = f"https://api.github.com/repos/test-owner/test-repo{endpoint}"
        
        response = requests.request(
            method,
            url,
            params=query,
            json=body,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()

    def _file_edit(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        File Edit operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        
        # TODO: Implement API call
        response = {}
        
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
        message = self.get_node_parameter('commitMessage', item_index)
        
        # Build request body
        body = {'author': additional_parameters_author, 'committer': additional_parameters_committer}
        
        # TODO: Implement API call
        response = {}
        
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
        
        # Build query parameters
        query = {}
        query['ref'] = additional_parameters_reference
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # Build query parameters
        query = {}
        query['lock_reason'] = this_get_node_parameter('lock_reason', i)
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # Build query parameters
        query = {}
        query['per_page'] = this_get_node_parameter('limit', 0)
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # Build query parameters
        query = {}
        query['per_page'] = this_get_node_parameter('limit', 0)
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # Build query parameters
        query = {}
        query['per_page'] = this_get_node_parameter('limit', 0)
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # Build query parameters
        query = {}
        query['per_page'] = this_get_node_parameter('limit', 0)
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # Build query parameters
        query = {}
        query['per_page'] = this_get_node_parameter('limit', 0)
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # Build request body
        body = {'ref': ref, 'inputs': inputs}
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
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
        
        # TODO: Implement API call
        response = {}
        
        return response

