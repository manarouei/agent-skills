#!/usr/bin/env python3
"""
Node Execution Contract - Pydantic Models

Defines the execution semantics contract for node conversion.
Every node MUST declare its semantic class and execution pattern
to enable correct converter backend selection.

This is the core abstraction that enables pipeline completeness:
- HTTP/REST nodes use http_rest backend
- TCP/Binary nodes use tcp_client backend  
- SDK-based nodes use sdk_client backend
- Data transform nodes use pure_transform backend
- Stateful nodes use stateful backend

SYNC-CELERY SAFE: Pure schema definitions, no I/O.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class SemanticClass(str, Enum):
    """
    Classification of node execution semantics.
    
    Determines which converter backend is used.
    """
    # HTTP/REST API nodes (GitHub, GitLab, Slack, Discord, etc.)
    HTTP_REST = "http_rest"
    
    # TCP/Binary protocol nodes (Redis, Postgres, MySQL, MongoDB)
    TCP_CLIENT = "tcp_client"
    
    # SDK-based nodes (OpenAI, Google APIs, AWS, etc.)
    SDK_CLIENT = "sdk_client"
    
    # Pure data transformation nodes (Merge, IF, Switch, Filter, Set)
    PURE_TRANSFORM = "pure_transform"
    
    # Stateful/control flow nodes (Wait, Loop, SplitInBatches, SubWorkflow)
    STATEFUL = "stateful"


class ConnectionType(str, Enum):
    """Type of external connection the node uses."""
    HTTP = "http"           # HTTP/REST requests
    TCP = "tcp"             # Direct TCP connections (Redis, Postgres)
    SDK = "sdk"             # SDK client library
    NONE = "none"           # No external connection (transforms)


class ItemMapping(str, Enum):
    """
    How input items map to output items.
    
    Critical for understanding node behavior.
    """
    ONE_TO_ONE = "1:1"      # Each input item produces exactly one output item
    ONE_TO_MANY = "1:N"     # Each input item can produce multiple output items
    MANY_TO_ONE = "N:1"     # Multiple input items combine to one output item
    MANY_TO_MANY = "N:M"    # Complex mapping (merge, join)
    FILTER = "filter"       # Subset of input items (0:1 per item)
    ROUTE = "route"         # Items routed to different outputs (if, switch)
    BATCH = "batch"         # Items grouped into batches


class CredentialResolution(str, Enum):
    """How credentials are resolved at runtime."""
    DIRECT = "direct"           # Single credential type: get_credentials("nodeApi")
    SELECTOR = "selector"       # User selects: authentication parameter -> oAuth2 or apiKey
    ENVIRONMENT = "environment" # From environment variables
    NONE = "none"               # No credentials needed


class StatePersistence(str, Enum):
    """Cross-execution state persistence requirements."""
    NONE = "none"               # Stateless execution
    SESSION = "session"         # Session-scoped (memory nodes)
    PERSISTENT = "persistent"   # Persistent storage (databases)


class WithinExecutionState(str, Enum):
    """State requirements within a single execution."""
    NONE = "none"               # No internal state
    ITEM_INDEX = "item_index"   # Tracks current item index (loops)
    ACCUMULATOR = "accumulator" # Accumulates results (aggregation)


# =============================================================================
# EXECUTION CONTRACT MODELS
# =============================================================================

class IOCardinality(BaseModel):
    """
    Input/Output cardinality contract.
    
    Declares how many inputs/outputs the node has and how items flow through.
    """
    input_count: int | Literal["N"] = Field(
        default=1,
        description="Number of input branches. 'N' for variable (merge node)."
    )
    input_required: list[int] = Field(
        default_factory=lambda: [0],
        description="Indices of required input branches."
    )
    output_count: int = Field(
        default=1,
        description="Number of output branches."
    )
    output_names: list[str] = Field(
        default_factory=lambda: ["main"],
        description="Names of output branches. ['true', 'false'] for IF node."
    )
    item_mapping: ItemMapping = Field(
        default=ItemMapping.ONE_TO_ONE,
        description="How input items map to output items."
    )


class ConnectionContract(BaseModel):
    """
    External connection contract.
    
    Declares how the node connects to external services.
    """
    type: ConnectionType = Field(
        ...,
        description="Type of external connection."
    )
    factory_method: str | None = Field(
        default=None,
        description="Method that creates the connection (e.g., '_get_redis_client')."
    )
    library: str | None = Field(
        default=None,
        description="Python library used (e.g., 'redis', 'psycopg', 'openai')."
    )
    pooling: bool = Field(
        default=False,
        description="Whether connection pooling is used."
    )
    cleanup: Literal["context_manager", "explicit_close", "none"] = Field(
        default="none",
        description="How connections are cleaned up."
    )
    
    @model_validator(mode="after")
    def validate_connection(self) -> "ConnectionContract":
        """Validate connection configuration is consistent."""
        if self.type in (ConnectionType.TCP, ConnectionType.SDK):
            if not self.factory_method:
                # Auto-generate factory method name
                pass  # Will be filled by converter
            if not self.library:
                raise ValueError(
                    f"Connection type {self.type} requires 'library' to be specified"
                )
        return self


class StateContract(BaseModel):
    """
    State management contract.
    
    Declares how the node manages state across and within executions.
    """
    cross_execution: StatePersistence = Field(
        default=StatePersistence.NONE,
        description="State persistence across workflow executions."
    )
    within_execution: WithinExecutionState = Field(
        default=WithinExecutionState.NONE,
        description="State management within a single execution."
    )
    persistence_key: str | None = Field(
        default=None,
        description="Parameter name used as state key (e.g., 'sessionKey')."
    )


class CredentialContract(BaseModel):
    """
    Credential resolution contract.
    
    Declares how the node resolves and uses credentials.
    """
    type: str | None = Field(
        default=None,
        description="Credential type name (e.g., 'redisApi', 'githubApi')."
    )
    resolution: CredentialResolution = Field(
        default=CredentialResolution.DIRECT,
        description="How credentials are resolved."
    )
    selector_param: str | None = Field(
        default=None,
        description="Parameter name for credential selection (if resolution=selector)."
    )
    connection_params: list[str] = Field(
        default_factory=list,
        description="Credential fields used for connection (host, port, password, etc.)."
    )


class HTTPConfig(BaseModel):
    """
    HTTP-specific configuration for http_rest nodes.
    """
    base_url: str | None = Field(
        default=None,
        description="API base URL (e.g., 'https://api.github.com')."
    )
    base_url_from_credentials: bool = Field(
        default=False,
        description="Whether base URL comes from credentials (self-hosted instances)."
    )
    auth_header: Literal["bearer", "token", "basic", "custom", "none"] = Field(
        default="bearer",
        description="Authentication header type."
    )
    auth_header_name: str = Field(
        default="Authorization",
        description="Custom auth header name if auth_header='custom'."
    )


class SDKConfig(BaseModel):
    """
    SDK-specific configuration for sdk_client nodes.
    """
    client_class: str = Field(
        ...,
        description="SDK client class (e.g., 'openai.OpenAI', 'redis.Redis')."
    )
    init_from_credentials: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from credential field to SDK init param."
    )


class TransformConfig(BaseModel):
    """
    Transform-specific configuration for pure_transform nodes.
    """
    preserves_binary: bool = Field(
        default=True,
        description="Whether binary data is preserved through transform."
    )
    requires_all_inputs: bool = Field(
        default=False,
        description="Whether all input branches must have data (merge)."
    )


# =============================================================================
# MAIN EXECUTION CONTRACT
# =============================================================================

class NodeExecutionContract(BaseModel):
    """
    Complete execution contract for a node.
    
    This is the core schema that enables universal node conversion.
    Every node must declare its execution semantics to be convertible.
    
    The semantic_class determines which converter backend is used:
    - http_rest -> skills/code-convert/backends/http_rest.py
    - tcp_client -> skills/code-convert/backends/tcp_client.py
    - sdk_client -> skills/code-convert/backends/sdk_client.py
    - pure_transform -> skills/code-convert/backends/pure_transform.py
    - stateful -> skills/code-convert/backends/stateful.py
    """
    semantic_class: SemanticClass = Field(
        ...,
        description="Node's semantic classification. Determines converter backend."
    )
    io_cardinality: IOCardinality = Field(
        default_factory=IOCardinality,
        description="Input/output cardinality contract."
    )
    connection: ConnectionContract = Field(
        ...,
        description="External connection contract."
    )
    state: StateContract = Field(
        default_factory=StateContract,
        description="State management contract."
    )
    credentials: CredentialContract = Field(
        default_factory=CredentialContract,
        description="Credential resolution contract."
    )
    
    # Semantic-class-specific configs (only one should be set)
    http_config: HTTPConfig | None = Field(
        default=None,
        description="HTTP-specific config (only for http_rest nodes)."
    )
    sdk_config: SDKConfig | None = Field(
        default=None,
        description="SDK-specific config (only for sdk_client nodes)."
    )
    transform_config: TransformConfig | None = Field(
        default=None,
        description="Transform-specific config (only for pure_transform nodes)."
    )
    
    @model_validator(mode="after")
    def validate_semantic_class_config(self) -> "NodeExecutionContract":
        """Validate that semantic-class-specific config is provided."""
        if self.semantic_class == SemanticClass.HTTP_REST:
            if not self.http_config:
                # Auto-create with defaults
                self.http_config = HTTPConfig()
        elif self.semantic_class == SemanticClass.SDK_CLIENT:
            if not self.sdk_config:
                raise ValueError(
                    "sdk_client nodes require sdk_config with client_class"
                )
        elif self.semantic_class == SemanticClass.PURE_TRANSFORM:
            if not self.transform_config:
                self.transform_config = TransformConfig()
        return self
    
    def validate_completeness(self) -> list[str]:
        """
        Validate contract completeness for conversion.
        
        Returns list of error messages (empty if valid).
        """
        errors = []
        
        # HTTP nodes need base_url or base_url_from_credentials
        if self.semantic_class == SemanticClass.HTTP_REST:
            if self.http_config:
                if not self.http_config.base_url and not self.http_config.base_url_from_credentials:
                    errors.append("http_rest nodes require base_url or base_url_from_credentials=True")
        
        # TCP/SDK nodes need library
        if self.semantic_class in (SemanticClass.TCP_CLIENT, SemanticClass.SDK_CLIENT):
            if not self.connection.library:
                errors.append(f"{self.semantic_class} nodes require connection.library")
        
        # Multi-output nodes need output names
        if self.io_cardinality.output_count > 1:
            if len(self.io_cardinality.output_names) != self.io_cardinality.output_count:
                errors.append(
                    f"output_count={self.io_cardinality.output_count} but "
                    f"output_names has {len(self.io_cardinality.output_names)} entries"
                )
        
        # Nodes with credentials need credential type
        if self.credentials.resolution != CredentialResolution.NONE:
            if not self.credentials.type:
                errors.append("Nodes with credentials require credentials.type")
        
        return errors


# =============================================================================
# DETECTION HELPERS
# =============================================================================

# Known node type -> semantic class mappings for deterministic detection
KNOWN_SEMANTIC_CLASSES: dict[str, SemanticClass] = {
    # HTTP/REST API nodes
    "github": SemanticClass.HTTP_REST,
    "gitlab": SemanticClass.HTTP_REST,
    "slack": SemanticClass.HTTP_REST,
    "discord": SemanticClass.HTTP_REST,
    "trello": SemanticClass.HTTP_REST,
    "twitter": SemanticClass.HTTP_REST,
    "shopify": SemanticClass.HTTP_REST,
    "airtable": SemanticClass.HTTP_REST,
    "openProject": SemanticClass.HTTP_REST,
    "wooCommerce": SemanticClass.HTTP_REST,
    "linkedin": SemanticClass.HTTP_REST,
    "http_request": SemanticClass.HTTP_REST,
    "webhook": SemanticClass.HTTP_REST,
    "wordpress": SemanticClass.HTTP_REST,
    "hesabfa": SemanticClass.HTTP_REST,
    "neshan": SemanticClass.HTTP_REST,
    "wallex": SemanticClass.HTTP_REST,
    "kavenegar": SemanticClass.HTTP_REST,
    
    # TCP/Binary protocol nodes
    "redis": SemanticClass.TCP_CLIENT,
    "postgres": SemanticClass.TCP_CLIENT,
    "mysql": SemanticClass.TCP_CLIENT,
    "mongodb": SemanticClass.TCP_CLIENT,
    "mssql": SemanticClass.TCP_CLIENT,
    
    # SDK-based nodes
    "openai": SemanticClass.SDK_CLIENT,
    "deepseek": SemanticClass.SDK_CLIENT,
    "grok": SemanticClass.SDK_CLIENT,
    "gemini": SemanticClass.SDK_CLIENT,
    "telegram": SemanticClass.SDK_CLIENT,
    "bale": SemanticClass.SDK_CLIENT,
    "googleSheets": SemanticClass.SDK_CLIENT,
    "googleDocs": SemanticClass.SDK_CLIENT,
    "googleDrive": SemanticClass.SDK_CLIENT,
    "googleCalendar": SemanticClass.SDK_CLIENT,
    "googleForm": SemanticClass.SDK_CLIENT,
    "gmail": SemanticClass.SDK_CLIENT,
    "supabase": SemanticClass.SDK_CLIENT,
    "qdrantVectorStore": SemanticClass.SDK_CLIENT,
    "ai_languageModel": SemanticClass.SDK_CLIENT,
    "ai_embedding": SemanticClass.SDK_CLIENT,
    "rerankerCohere": SemanticClass.SDK_CLIENT,
    
    # Pure transform nodes
    "merge": SemanticClass.PURE_TRANSFORM,
    "if": SemanticClass.PURE_TRANSFORM,
    "switch": SemanticClass.PURE_TRANSFORM,
    "filter": SemanticClass.PURE_TRANSFORM,
    "set": SemanticClass.PURE_TRANSFORM,
    "iterator": SemanticClass.PURE_TRANSFORM,
    "htmlExtractor": SemanticClass.PURE_TRANSFORM,
    "persianTextProcessor": SemanticClass.PURE_TRANSFORM,
    "outputValidator": SemanticClass.PURE_TRANSFORM,
    "start": SemanticClass.PURE_TRANSFORM,
    "end": SemanticClass.PURE_TRANSFORM,
    "stickyNote": SemanticClass.PURE_TRANSFORM,
    "rssFeed": SemanticClass.PURE_TRANSFORM,
    "documentDefaultDataLoader": SemanticClass.PURE_TRANSFORM,
    
    # Stateful/control flow nodes
    "wait": SemanticClass.STATEFUL,
    "loop": SemanticClass.STATEFUL,
    "splitInBatches": SemanticClass.STATEFUL,
    "subWorkflow": SemanticClass.STATEFUL,
    "executeWorkflow": SemanticClass.STATEFUL,
    "buffer_memory": SemanticClass.STATEFUL,
    "redis_memory": SemanticClass.STATEFUL,
    "ai_agent": SemanticClass.STATEFUL,
    "mcpClientTool": SemanticClass.STATEFUL,
    "localGpt": SemanticClass.STATEFUL,
}


# Known connection libraries for TCP/SDK nodes
KNOWN_LIBRARIES: dict[str, str] = {
    "redis": "redis",
    "postgres": "psycopg",
    "mysql": "mysql-connector-python",
    "mongodb": "pymongo",
    "openai": "openai",
    "deepseek": "openai",
    "gemini": "google-generativeai",
    "telegram": "requests",
    "bale": "requests",
    "supabase": "supabase",
    "qdrantVectorStore": "qdrant-client",
}


# Known base URLs for HTTP nodes
KNOWN_BASE_URLS: dict[str, str] = {
    "github": "https://api.github.com",
    "gitlab": "https://gitlab.com/api/v4",
    "slack": "https://slack.com/api",
    "discord": "https://discord.com/api/v10",
    "trello": "https://api.trello.com/1",
    "twitter": "https://api.twitter.com/2",
    "shopify": "",  # From credentials (store URL)
    "airtable": "https://api.airtable.com/v0",
    "bitly": "https://api-ssl.bitly.com",
}


def detect_semantic_class(
    node_type: str,
    ts_code: str = "",
    properties: list[dict] = None,
) -> SemanticClass:
    """
    Detect the semantic class of a node.
    
    Uses multiple signals:
    1. Known node type mapping (deterministic)
    2. Code pattern analysis (heuristic)
    3. Property analysis (heuristic)
    
    Args:
        node_type: The node type name (e.g., 'github', 'redis')
        ts_code: TypeScript source code (optional)
        properties: Node properties from schema (optional)
    
    Returns:
        Detected SemanticClass
    """
    node_type_lower = node_type.lower().replace("-", "").replace("_", "")
    
    # 1. Check known mappings first (most reliable)
    if node_type_lower in KNOWN_SEMANTIC_CLASSES:
        return KNOWN_SEMANTIC_CLASSES[node_type_lower]
    
    # 2. Code pattern analysis
    if ts_code:
        ts_lower = ts_code.lower()
        
        # TCP client indicators
        if any(pattern in ts_lower for pattern in [
            "redis.createclient", "pg.connect", "mysql.createconnection",
            "mongodb.connect", "new redis(", "psycopg", "pymongo"
        ]):
            return SemanticClass.TCP_CLIENT
        
        # SDK client indicators
        if any(pattern in ts_lower for pattern in [
            "openai.", "google.generativeai", "cohere.", "anthropic.",
            "langchain", "new openai("
        ]):
            return SemanticClass.SDK_CLIENT
        
        # HTTP indicators (check after TCP/SDK to avoid false positives)
        if any(pattern in ts_lower for pattern in [
            "this.helpers.request", "this.helpers.requestoauth2",
            "fetch(", "axios.", "got.", "baseurl"
        ]):
            return SemanticClass.HTTP_REST
        
        # Transform indicators
        if any(pattern in ts_lower for pattern in [
            "this.getinputdata()", "merge", "filter", "switch", "if ("
        ]) and "this.helpers.request" not in ts_lower:
            return SemanticClass.PURE_TRANSFORM
    
    # 3. Property analysis
    if properties:
        has_url_param = any(p.get("name") in ("url", "baseUrl") for p in properties)
        has_connection_params = any(
            p.get("name") in ("host", "port", "database", "connectionString")
            for p in properties
        )
        
        if has_connection_params:
            return SemanticClass.TCP_CLIENT
        if has_url_param:
            return SemanticClass.HTTP_REST
    
    # 4. Default to HTTP_REST (most common)
    return SemanticClass.HTTP_REST


def build_execution_contract(
    node_type: str,
    semantic_class: SemanticClass,
    ts_code: str = "",
    properties: list[dict] = None,
    description: dict = None,
) -> NodeExecutionContract:
    """
    Build a complete execution contract for a node.
    
    Args:
        node_type: Node type name
        semantic_class: Detected semantic class
        ts_code: TypeScript source code (optional)
        properties: Node properties (optional)
        description: Node description (optional)
    
    Returns:
        NodeExecutionContract with all fields populated
    """
    node_type_lower = node_type.lower().replace("-", "").replace("_", "")
    properties = properties or []
    description = description or {}
    
    # Build IO cardinality from description
    inputs = description.get("inputs", ["main"])
    outputs = description.get("outputs", ["main"])
    
    if isinstance(inputs, list) and len(inputs) > 0:
        if isinstance(inputs[0], dict):
            input_count = len(inputs)
            input_required = [i for i, inp in enumerate(inputs) if inp.get("required", True)]
        else:
            input_count = len(inputs)
            input_required = [0] if inputs else []
    else:
        input_count = 1
        input_required = [0]
    
    if isinstance(outputs, list) and len(outputs) > 0:
        if isinstance(outputs[0], dict):
            output_count = len(outputs)
            output_names = [o.get("name", f"output_{i}") for i, o in enumerate(outputs)]
        else:
            output_count = len(outputs)
            output_names = outputs if all(isinstance(o, str) for o in outputs) else ["main"]
    else:
        output_count = 1
        output_names = ["main"]
    
    # Determine item mapping from semantic class and outputs
    if output_count > 1:
        item_mapping = ItemMapping.ROUTE
    elif semantic_class == SemanticClass.PURE_TRANSFORM:
        # Check for filter/merge patterns
        if node_type_lower in ("filter",):
            item_mapping = ItemMapping.FILTER
        elif node_type_lower in ("merge",):
            item_mapping = ItemMapping.MANY_TO_MANY
        else:
            item_mapping = ItemMapping.ONE_TO_ONE
    else:
        item_mapping = ItemMapping.ONE_TO_ONE
    
    io_cardinality = IOCardinality(
        input_count=input_count if input_count <= 1 else "N",
        input_required=input_required,
        output_count=output_count,
        output_names=output_names,
        item_mapping=item_mapping,
    )
    
    # Build connection contract
    if semantic_class == SemanticClass.HTTP_REST:
        connection = ConnectionContract(
            type=ConnectionType.HTTP,
            library="requests",
        )
    elif semantic_class == SemanticClass.TCP_CLIENT:
        library = KNOWN_LIBRARIES.get(node_type_lower, "")
        connection = ConnectionContract(
            type=ConnectionType.TCP,
            factory_method=f"_get_{node_type_lower}_client",
            library=library,
            cleanup="context_manager",
        )
    elif semantic_class == SemanticClass.SDK_CLIENT:
        library = KNOWN_LIBRARIES.get(node_type_lower, "")
        connection = ConnectionContract(
            type=ConnectionType.SDK,
            factory_method=f"_get_{node_type_lower}_client",
            library=library,
        )
    else:
        connection = ConnectionContract(type=ConnectionType.NONE)
    
    # Build credential contract
    desc_credentials = description.get("credentials", [])
    prop_credentials = [p for p in properties if p.get("name") == "authentication"]
    
    if desc_credentials:
        cred = desc_credentials[0] if isinstance(desc_credentials, list) else desc_credentials
        cred_type = cred.get("name") if isinstance(cred, dict) else cred
        resolution = CredentialResolution.DIRECT
    elif prop_credentials:
        cred_type = f"{node_type_lower}Api"
        resolution = CredentialResolution.SELECTOR
    elif semantic_class in (SemanticClass.TCP_CLIENT, SemanticClass.SDK_CLIENT, SemanticClass.HTTP_REST):
        cred_type = f"{node_type_lower}Api"
        resolution = CredentialResolution.DIRECT
    else:
        cred_type = None
        resolution = CredentialResolution.NONE
    
    credentials = CredentialContract(
        type=cred_type,
        resolution=resolution,
        selector_param="authentication" if resolution == CredentialResolution.SELECTOR else None,
    )
    
    # Build semantic-class-specific config
    http_config = None
    sdk_config = None
    transform_config = None
    
    if semantic_class == SemanticClass.HTTP_REST:
        base_url = KNOWN_BASE_URLS.get(node_type_lower, "")
        http_config = HTTPConfig(
            base_url=base_url if base_url else None,
            base_url_from_credentials=not base_url,
        )
    elif semantic_class == SemanticClass.SDK_CLIENT:
        library = KNOWN_LIBRARIES.get(node_type_lower, "")
        sdk_config = SDKConfig(
            client_class=library,
            init_from_credentials={"api_key": "apiKey"} if library else {},
        )
    elif semantic_class == SemanticClass.PURE_TRANSFORM:
        transform_config = TransformConfig(
            requires_all_inputs=node_type_lower in ("merge",),
        )
    
    return NodeExecutionContract(
        semantic_class=semantic_class,
        io_cardinality=io_cardinality,
        connection=connection,
        state=StateContract(),
        credentials=credentials,
        http_config=http_config,
        sdk_config=sdk_config,
        transform_config=transform_config,
    )
