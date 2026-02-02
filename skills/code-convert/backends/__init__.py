#!/usr/bin/env python3
"""
Converter Backends Package

Each backend handles conversion for a specific semantic class of nodes:
- http_rest: REST API nodes (GitHub, GitLab, Slack, etc.)
- tcp_client: TCP/binary protocol nodes (Redis, Postgres, MySQL)
- sdk_client: SDK-based nodes (OpenAI, Google APIs, etc.)
- pure_transform: Data transformation nodes (Merge, IF, Switch, Filter)
- stateful: Stateful/control flow nodes (Wait, Loop, Memory)

The router in code-convert/impl.py selects the appropriate backend
based on the semantic_class in the node's execution contract.
"""

from .http_rest import convert_http_rest_node
from .tcp_client import convert_tcp_client_node
from .sdk_client import convert_sdk_client_node
from .pure_transform import convert_pure_transform_node
from .stateful import convert_stateful_node
from .router import route_to_backend

__all__ = [
    "convert_http_rest_node",
    "convert_tcp_client_node",
    "convert_sdk_client_node",
    "convert_pure_transform_node",
    "convert_stateful_node",
    "route_to_backend",
]
