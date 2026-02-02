"""
Qdrant Vector Store node for managing vector embeddings and similarity search.

REFACTORED ARCHITECTURE:
- Thin orchestrator delegating to specialized components
- Uses Pydantic models for parameter validation
- QdrantClientAdapter for all HTTP operations (with pooling + retry)
- Embedding providers via factory pattern (supports OpenAI, future: Cohere, etc.)
- Retriever abstraction composing client + provider
- Proper exception handling (no error dicts)

Operations:
- createCollection: Create vector collection
- insert: Insert documents with embeddings
- search: Vector similarity search
- delete: Delete vectors by ID or filter
- getCollection: Get collection info
- retrieve-as-tool: AI agent tool mode (auto-detected)
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import ValidationError
import logging
import traceback
import requests
import json
import time
import uuid

from models import NodeExecutionData
from models.connection import ConnectionType
from .base import BaseNode, NodeParameterType
from utils.serialization import deep_serialize
from utils.connection_resolver import ConnectionResolver

# New infrastructure (refactored)
from utils.qdrant_client import QdrantClientAdapter
from utils.embedding_providers import EmbeddingProviderFactory
from utils.qdrant_retriever import Retriever
from utils.qdrant_models import (
    SearchParams,
    InsertParams,
    CollectionParams,
    DeleteParams,
    EmbeddingProviderConfig,
    QdrantConnectionConfig
)
from utils.qdrant_exceptions import (
    QdrantBaseException,
    ParameterError,
    EmbeddingError,
    QdrantError
)

logger = logging.getLogger(__name__)


class QdrantVectorStoreNode(BaseNode):
    """
    Qdrant Vector Store node for vector database operations
    """
    
    type = "qdrantVectorStore"
    version = 1.0
    
    description = {
        "displayName": "Qdrant Vector Store",
        "name": "qdrantVectorStore",
        "icon": "file:qdrant.svg",
        "group": ["transform"],
        "description": "Interact with Qdrant vector database for storing and searching embeddings",
        "usableAsTool": True,  # Enables use as AI Agent tool
        "inputs": [
            {"name": "main", "type": "main", "required": True},
            {"name": "ai_document", "type": "ai_document", "required": False},
            {"name": "ai_embedding", "type": "ai_embedding", "required": False}
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True},
            {"name": "ai_tool", "type": "ai_tool", "required": False}
        ],
    }
    
    properties = {
        "parameters": [
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "options": [
                    {
                        "name": "Create Collection",
                        "value": "createCollection",
                        "description": "Create a new vector collection"
                    },
                    {
                        "name": "Insert",
                        "value": "insert",
                        "description": "Insert vectors into a collection"
                    },
                    {
                        "name": "Search",
                        "value": "search",
                        "description": "Search for similar vectors"
                    },
                    {
                        "name": "Retrieve",
                        "value": "retrieve",
                        "description": "Retrieve vectors by ID or filter"
                    },
                    {
                        "name": "Delete",
                        "value": "delete",
                        "description": "Delete vectors from collection"
                    },
                    {
                        "name": "Get Collection Info",
                        "value": "getCollection",
                        "description": "Get information about a collection"
                    }
                ],
                "default": "search"
            },
            
            # Collection name (common to all operations)
            {
                "name": "collectionName",
                "type": NodeParameterType.STRING,
                "display_name": "Collection Name",
                "default": "",
                "required": True,
                "description": "Name of the Qdrant collection"
            },
            
            # Create Collection parameters
            {
                "name": "vectorSize",
                "type": NodeParameterType.NUMBER,
                "display_name": "Vector Size",
                "default": 1536,
                "required": True,
                "display_options": {
                    "show": {
                        "operation": ["createCollection"]
                    }
                },
                "description": "Dimension of the vectors (e.g., 1536 for OpenAI embeddings)"
            },
            {
                "name": "distance",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Distance Metric",
                "default": "Cosine",
                "display_options": {
                    "show": {
                        "operation": ["createCollection"]
                    }
                },
                "options": [
                    {"name": "Cosine", "value": "Cosine"},
                    {"name": "Euclidean", "value": "Euclid"},
                    {"name": "Dot Product", "value": "Dot"}
                ],
                "description": "Distance metric for similarity calculation"
            },
            {
                "name": "onDiskPayload",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Store Payload on Disk",
                "default": False,
                "display_options": {
                    "show": {
                        "operation": ["createCollection"]
                    }
                },
                "description": "Store payload data on disk instead of RAM (useful for large payloads)"
            },
            
            # Insert parameters
            {
                "name": "inputMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Input Mode",
                "default": "auto",
                "display_options": {
                    "show": {
                        "operation": ["insert"]
                    }
                },
                "options": [
                    {"name": "Auto-detect", "value": "auto", "description": "Automatically detect from connections"},
                    {"name": "Manual (Pre-computed Vectors)", "value": "manual", "description": "Use pre-computed vectors from input data"},
                    {"name": "Typed (Documents + Embeddings)", "value": "typed", "description": "Use ai_document and ai_embedding connections"}
                ],
                "description": "How to provide vectors: manual (pre-computed) or typed (auto-generate)"
            },
            {
                "name": "vectorsInput",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Vectors Input Mode",
                "default": "fromItems",
                "display_options": {
                    "show": {
                        "operation": ["insert"],
                        "inputMode": ["manual", "auto"]
                    }
                },
                "options": [
                    {"name": "From Input Items", "value": "fromItems"},
                    {"name": "Define Below", "value": "define"}
                ],
                "description": "How to provide the vectors to insert"
            },
            {
                "name": "vectorField",
                "type": NodeParameterType.STRING,
                "display_name": "Vector Field Name",
                "default": "vector",
                "display_options": {
                    "show": {
                        "operation": ["insert"],
                        "inputMode": ["manual", "auto"],
                        "vectorsInput": ["fromItems"]
                    }
                },
                "description": "Field name containing the vector in input items"
            },
            {
                "name": "payloadFields",
                "type": NodeParameterType.STRING,
                "display_name": "Payload Fields",
                "default": "",
                "display_options": {
                    "show": {
                        "operation": ["insert"],
                        "inputMode": ["manual", "auto"],
                        "vectorsInput": ["fromItems"]
                    }
                },
                "description": "Comma-separated list of fields to store as payload (leave empty for all fields)"
            },
            {
                "name": "vectors",
                "type": NodeParameterType.JSON,
                "display_name": "Vectors",
                "default": [],
                "display_options": {
                    "show": {
                        "operation": ["insert"],
                        "inputMode": ["manual", "auto"],
                        "vectorsInput": ["define"]
                    }
                },
                "description": "Array of objects with 'id', 'vector', and 'payload' fields"
            },
            {
                "name": "wait",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Wait for Completion",
                "default": True,
                "display_options": {
                    "show": {
                        "operation": ["insert"]
                    }
                },
                "description": "Wait for the operation to complete before returning"
            },
            
            # Search parameters
            {
                "name": "query",
                "type": NodeParameterType.STRING,
                "display_name": "Query Text",
                "default": "",
                "display_options": {
                    "show": {
                        "operation": ["search"]
                    }
                },
                "description": "Text query to search for (will be converted to embedding automatically if ai_embedding connection is present)"
            },
            {
                "name": "queryVector",
                "type": NodeParameterType.JSON,
                "display_name": "Query Vector",
                "default": [],
                "display_options": {
                    "show": {
                        "operation": ["search"]
                    }
                },
                "description": "Vector to search for (array of numbers). Alternative to query text."
            },
            {
                "name": "topK",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 10,
                "display_options": {
                    "show": {
                        "operation": ["search", "retrieve"]
                    }
                },
                "description": "Number of results to return"
            },
            {
                "name": "scoreThreshold",
                "type": NodeParameterType.NUMBER,
                "display_name": "Score Threshold",
                "default": 0,
                "display_options": {
                    "show": {
                        "operation": ["search", "retrieve"]
                    }
                },
                "description": "Minimum similarity score (0-1). Results below this threshold will be filtered out. Only applies when used as retriever tool."
            },
            {
                "name": "filter",
                "type": NodeParameterType.JSON,
                "display_name": "Filter",
                "default": {},
                "display_options": {
                    "show": {
                        "operation": ["search", "retrieve", "delete"]
                    }
                },
                "description": "Qdrant filter object to narrow down results"
            },
            {
                "name": "withPayload",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Include Payload",
                "default": True,
                "display_options": {
                    "show": {
                        "operation": ["search", "retrieve"]
                    }
                },
                "description": "Include payload data in results"
            },
            {
                "name": "withVector",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Include Vector",
                "default": False,
                "display_options": {
                    "show": {
                        "operation": ["search", "retrieve"]
                    }
                },
                "description": "Include vector data in results"
            },
            
            # Retrieve parameters
            {
                "name": "pointIds",
                "type": NodeParameterType.JSON,
                "display_name": "Point IDs",
                "default": [],
                "display_options": {
                    "show": {
                        "operation": ["retrieve", "delete"]
                    }
                },
                "description": "Array of point IDs to retrieve or delete"
            },
            {
                "name": "retrieveLimit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 100,
                "display_options": {
                    "show": {
                        "operation": ["retrieve"]
                    }
                },
                "description": "Maximum number of points to retrieve"
            },
            {
                "name": "retrieveOffset",
                "type": NodeParameterType.NUMBER,
                "display_name": "Offset",
                "default": 0,
                "display_options": {
                    "show": {
                        "operation": ["retrieve"]
                    }
                },
                "description": "Number of points to skip"
            },
            
            # Options
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Options",
                "default": {},
                "options": [
                    {
                        "name": "timeout",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Request Timeout",
                        "default": 30,
                        "description": "Request timeout in seconds"
                    },
                    {
                        "name": "batch_size",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Batch Size",
                        "default": 100,
                        "description": "Number of points to insert in a single batch"
                    }
                ]
            },
            {
                "name": "mode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Mode",
                "default": "insert",
                "options": [
                    {"name": "Insert", "value": "insert"},
                    {"name": "Search", "value": "search"},  
                    {"name": "Retrieve as Tool", "value": "retrieve-as-tool"}
                ],
                "description": "Deprecated: Mode is now auto-detected based on connection type. Set to 'retrieve-as-tool' only if auto-detection fails.",
                "displayOptions": {
                    "show": {
                        "__never__": [True]  # Hidden - kept for backward compatibility only
                    }
                }
            }
        ],
        "credentials": [
            {
                "name": "qdrantApi",
                "required": True
            }
        ]
    }
    
    icon = "file:qdrant.svg"
    color = "#DC244C"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Qdrant Vector Store node operations"""
        
        try:
            # Auto-detect if being used as an AI Agent tool
            # This follows n8n's pattern: nodes detect usage context automatically
            is_tool_mode = self._is_used_as_tool()
            
            # Also check explicit mode parameter for backward compatibility
            mode = self.get_node_parameter("mode", 0, None)
            
            if is_tool_mode or mode == "retrieve-as-tool":
                # Special handling for AI Agent tool mode
                #logger.info("[Qdrant] Running in retriever tool mode (auto-detected or explicit)")
                result = self._retrieve_as_tool()
            else:
                # Normal operation routing
                operation = self.get_node_parameter("operation", 0, "search")
                input_data = self.get_input_data()

                if not input_data:
                    return [[]]
                
                # Route to appropriate operation handler
                if operation == "createCollection":
                    result = self._create_collection()
                elif operation == "insert":
                    result = self._insert_vectors(input_data)
                elif operation == "search":
                    result = self._search_vectors()
                elif operation == "retrieve":
                    result = self._retrieve_vectors()
                elif operation == "delete":
                    result = self._delete_vectors()
                elif operation == "getCollection":
                    result = self._get_collection_info()
                else:
                    raise ParameterError(f"Operation {operation} is not supported")
            
            # Check if result contains an error (legacy format)
            if isinstance(result, dict) and "error" in result:
                return self._prepare_error_data(result["error"])
            
            # Serialize the result for proper JSON handling
            serialized_result = deep_serialize(result)
            
            # If result is a list, return each item as separate output
            if isinstance(serialized_result, list):
                return [[NodeExecutionData(json_data=item) for item in serialized_result]]
            else:
                return [[NodeExecutionData(json_data=serialized_result)]]
        
        except QdrantBaseException as e:
            # Handle our custom exceptions (ParameterError, EmbeddingError, QdrantError)
            logger.error(f"[Qdrant] {e.__class__.__name__}: {e.message}")
            return self._prepare_error_data(json.dumps(e.to_dict()))
            
        except ValidationError as e:
            # Handle Pydantic validation errors
            logger.error(f"[Qdrant] Validation error: {e}")
            error_dict = {
                "error": "ValidationError",
                "message": "Invalid parameters",
                "details": e.errors()
            }
            return self._prepare_error_data(json.dumps(error_dict))
            
        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"[Qdrant] Unexpected error: {str(e)}")
            traceback.print_exc()
            error_dict = {
                "error": "InternalError",
                "message": f"Unexpected error: {str(e)}",
                "details": {"type": type(e).__name__}
            }
            return self._prepare_error_data(json.dumps(error_dict))

    def _prepare_error_data(self, error_message: str) -> List[List[NodeExecutionData]]:
        """Create error data structure for failed executions"""
        return [[NodeExecutionData(json_data={"error": error_message})]]

    def _get_base_url(self) -> str:
        """Get base URL for Qdrant requests"""
        credentials = self.get_credentials("qdrantApi")
        
        if not credentials:
            raise Exception("No credentials found. Please set up Qdrant API credentials.")
        
        url = credentials.get("qdrantUrl", "").rstrip("/")
        if not url:
            raise Exception("Qdrant URL is required")
        
        return url

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Qdrant requests"""
        credentials = self.get_credentials("qdrantApi")
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Add API key if provided
        api_key = credentials.get("apiKey", "") if credentials else ""
        if api_key:
            headers["api-key"] = api_key
        
        return headers

    def _parse_options(self, options: Any) -> Dict[str, Any]:
        """
        Parse options parameter safely using JSON.
        Handles both proper JSON and Python dict syntax (single quotes).
        
        Accepted keys:
        - timeout (int): Request timeout in seconds
        - batch_size (int): Batch size for operations
        - scoreThreshold (float): Score threshold for search
        
        Args:
            options: Options dict or JSON string
            
        Returns:
            Parsed options dict (empty on parse failure)
        """
        if isinstance(options, dict):
            return options
        
        if isinstance(options, str):
            # Try JSON parsing first
            try:
                parsed = json.loads(options)
                if isinstance(parsed, dict):
                    return parsed
                logger.warning(f"[Qdrant] Options string parsed to non-dict type: {type(parsed)}")
            except json.JSONDecodeError as e:
                # If JSON fails, try replacing single quotes with double quotes (common issue)
                logger.debug(f"[Qdrant] JSON parse failed, trying with quote replacement: {e}")
                try:
                    # Replace single quotes with double quotes for Python-style dicts
                    fixed_options = options.replace("'", '"')
                    parsed = json.loads(fixed_options)
                    if isinstance(parsed, dict):
                        #logger.info(f"[Qdrant] Successfully parsed options after quote fix")
                        return parsed
                except json.JSONDecodeError as e2:
                    logger.warning(f"[Qdrant] Failed to parse options even after quote fix: {e2}")
        
        return {}

    def _get_timeout(self) -> int:
        """Get request timeout from options"""
        options = self.get_node_parameter("options", 0, {})
        options = self._parse_options(options)
        return options.get("timeout", 30)

    # ============================================================================
    # NEW REFACTORED INFRASTRUCTURE (Connection Pooling + Provider Pattern)
    # ============================================================================

    def _initialize_qdrant_adapter(self) -> QdrantClientAdapter:
        """
        Initialize Qdrant client adapter with connection pooling.
        
        Returns:
            Configured QdrantClientAdapter
            
        Raises:
            ParameterError: If credentials are invalid
        """
        try:
            config = QdrantConnectionConfig(
                url=self._get_base_url(),
                api_key=self.get_credentials("qdrantApi").get("apiKey"),
                timeout=self._get_timeout(),
                max_retries=3
            )
            
            adapter = QdrantClientAdapter(
                base_url=config.url,
                api_key=config.api_key,
                timeout=config.timeout,
                max_retries=config.max_retries
            )
            
            logger.debug(f"[Qdrant] Initialized adapter with pooling: {config.url}")
            return adapter
            
        except ValidationError as e:
            raise ParameterError(f"Invalid Qdrant connection config: {e}")
    
    def _initialize_embedding_provider(self) -> Optional[Any]:
        """
        Initialize embedding provider from credentials.
        Returns None if no embeddings credential is configured.
        
        Returns:
            Configured embedding provider or None
            
        Raises:
            ParameterError: If provider config is invalid
        """
        # Try to get embeddings credential (use openAiApi for OpenAI embeddings)
        embeddings_cred = self.get_credentials("openAiApi")
        
        if embeddings_cred:
            try:
                # Build provider config
                config = EmbeddingProviderConfig(
                    provider_type="openai",
                    api_key=embeddings_cred.get("apiKey", ""),
                    model=embeddings_cred.get("model", "text-embedding-3-small"),
                    base_url=embeddings_cred.get("baseUrl"),
                    dimensions=embeddings_cred.get("dimensions"),
                    organization=embeddings_cred.get("organization"),
                    timeout=embeddings_cred.get("timeout", 60),
                    batch_size=100
                )
                
                # Create provider via factory
                provider = EmbeddingProviderFactory.create(
                    provider_type="openai",
                    config=config.dict()
                )
                
                #logger.info(f"[Qdrant] Initialized {config.provider_type} provider from credentials: {config.model}")
                return provider
                
            except ValidationError as e:
                raise ParameterError(f"Invalid embedding provider config: {e}")
        
        # N8N pattern: No credentials, check ai_embedding typed connection
        #logger.info("[Qdrant] No credentials, checking ai_embedding connection...")
        embedding_config = self._get_embedding_provider()
        
        if embedding_config:
            try:
                provider = EmbeddingProviderFactory.create(
                    provider_type=embedding_config.get("provider_type", "openai"),
                    config=embedding_config
                )
                #logger.info(f"[Qdrant] Initialized provider from ai_embedding connection: {embedding_config.get('model')}")
                return provider
            except Exception as e:
                logger.error(f"[Qdrant] Failed to create provider from ai_embedding config: {e}")
                return None
        
        #logger.info("[Qdrant] No embedding provider available (no credentials or ai_embedding connection)")
        return None
    
    def _initialize_retriever(self) -> Retriever:
        """
        Initialize retriever composing adapter + provider.
        Tries multiple sources for embedding provider:
        1. From credentials (embeddingsOpenAi)
        2. From ai_embedding connection (typed mode / AI Agent tool)
        
        Returns:
            Configured Retriever
            
        Raises:
            ParameterError: If initialization fails
        """
        adapter = self._initialize_qdrant_adapter()
        
        # Try to get provider from credentials first
        provider = self._initialize_embedding_provider()
        
        # If no credential-based provider, try ai_embedding connection
        if not provider:
            #logger.info("[Qdrant] No credentials provider, checking ai_embedding connection...")
            provider_config = self._get_embedding_provider()
            
            if provider_config:
                try:
                    # Build provider from connection config
                    provider_type = provider_config.get("type", "openai").lower()
                    
                    config = EmbeddingProviderConfig(
                        provider_type=provider_type,
                        api_key=provider_config.get("api_key", ""),
                        model=provider_config.get("model", "text-embedding-3-small"),
                        base_url=provider_config.get("base_url"),
                        dimensions=provider_config.get("dimensions"),
                        organization=provider_config.get("organization"),
                        timeout=provider_config.get("timeout", 60),
                        batch_size=100
                    )
                    
                    provider = EmbeddingProviderFactory.create(
                        provider_type=provider_type,
                        config=config.dict()
                    )
                    
                    #logger.info(f"[Qdrant] Initialized {provider_type} provider from ai_embedding connection")
                    
                except Exception as e:
                    logger.error(f"[Qdrant] Failed to create provider from connection: {e}")
        
        if not provider:
            raise ParameterError(
                "Embeddings provider is required for retriever operations. "
                "Please connect an OpenAI Embeddings node or configure embeddingsOpenAi credential."
            )
        
        retriever = Retriever(adapter, provider)
        #logger.info("[Qdrant] Initialized retriever with adapter + provider")
        
        return retriever

    # ============================================================================
    # OLD INFRASTRUCTURE (kept for backward compatibility during migration)
    # ============================================================================

    def _is_used_as_tool(self) -> bool:
        """
        Check if this node is being used as a tool by an AI Agent.
        
        n8n's design: Vector stores can provide an ai_tool output. When connected
        to an AI Agent's ai_tool input, the agent calls the node automatically
        during tool execution.
        
        Detection strategy:
        1. Check if there's an ai_tool downstream connection (AI Agent connected)
        2. Check if we're being called in a tool execution context (has expr_json with query)
        
        Returns:
            bool: True if node is being used as a retriever tool
        """
        try:
            # Strategy 1: Check for downstream AI Agent connection
            # In n8n, when a node provides ai_tool output and it's connected to AI Agent,
            # the agent will call it during tool execution
            from utils.connection_resolver import ConnectionResolver
            
            # Check if any downstream node is consuming our ai_tool output
            # This would indicate we're connected as a tool
            if hasattr(self, 'workflow') and hasattr(self, 'node_data'):
                # Look for connections from this node's ai_tool output
                for conn in self.workflow.connections:
                    if (conn.source_node == self.node_data.name and 
                        conn.source == "ai_tool"):
                        #logger.info("[Qdrant] Detected ai_tool connection - auto-enabling retriever mode")
                        return True
            
            # Strategy 2: Check execution context - if we have query data in expr_json
            # This indicates we're being called by AI Agent's tool executor
            input_data = self.get_input_data()
            if input_data and len(input_data) > 0:
                item = input_data[0]
                json_data = getattr(item, "json_data", {}) or {}
                
                # AI Agent passes context via expr_json with fields like user_query, chatInput
                if any(field in json_data for field in ["user_query", "chatInput", "query"]):
                    #logger.info("[Qdrant] Detected tool execution context (query in input) - auto-enabling retriever mode")
                    return True
                    
        except Exception as e:
            logger.debug(f"[Qdrant] Error detecting tool usage: {e}")
        
        return False

    def _has_typed_document_input(self) -> bool:
        """
        Check if ai_document connection is present.
        Uses ConnectionResolver to find upstream nodes providing ai_document type.
        """
        try:
            upstream = ConnectionResolver.get_upstream_nodes(
                self.workflow,
                self.node_data.name,
                "ai_document"
            )
            return len(upstream) > 0
        except Exception as e:
            logger.debug(f"Error checking for ai_document input: {e}")
            return False

    def _has_typed_embedding_input(self) -> bool:
        """
        Check if ai_embedding connection is present.
        Uses ConnectionResolver to find upstream nodes providing ai_embedding type.
        """
        try:
            upstream = ConnectionResolver.get_upstream_nodes(
                self.workflow,
                self.node_data.name,
                "ai_embedding"
            )
            return len(upstream) > 0
        except Exception as e:
            logger.debug(f"Error checking for ai_embedding input: {e}")
            return False

    def _get_typed_documents(self) -> List[Dict[str, Any]]:
        """
        Get documents from ai_document typed connection.
        Documents should have structure: {pageContent: str, metadata: dict}
        """
        try:
            items = ConnectionResolver.get_items(
                self.workflow,
                self.execution_data,
                self.node_data.name,
                "ai_document"
            )
            
            documents = []
            for item in items:
                data = item.json_data or {}
                
                # Support both direct Document format and wrapped format
                if "pageContent" in data:
                    # Direct Document format
                    documents.append({
                        "pageContent": data.get("pageContent", ""),
                        "metadata": data.get("metadata", {})
                    })
                elif "document" in data:
                    # Wrapped format
                    doc = data.get("document", {})
                    documents.append({
                        "pageContent": doc.get("pageContent", ""),
                        "metadata": doc.get("metadata", {})
                    })
                else:
                    # Fallback: treat entire data as potential document
                    logger.warning(f"Document format not recognized, attempting to extract text fields")
                    # Look for common text field names
                    text_content = (
                        data.get("text") or 
                        data.get("content") or 
                        data.get("body") or 
                        str(data)
                    )
                    documents.append({
                        "pageContent": text_content,
                        "metadata": {k: v for k, v in data.items() if k not in ["text", "content", "body"]}
                    })
            
            logger.info(f"[Qdrant] Extracted {len(documents)} documents from ai_document connection")
            return documents
            
        except Exception as e:
            logger.error(f"Error getting typed documents: {e}")
            traceback.print_exc()
            return []

    def _get_embedding_provider(self) -> Optional[Dict[str, Any]]:
        """
        Get embedding provider configuration from ai_embedding typed connection.
        Returns a dict with provider configuration that can be used to generate embeddings.
        
        SECURITY: Looks for _embedding_config_internal first (contains API key),
        falls back to sanitized public configs.
        
        N8N Architecture: Typed connections provide configuration via upstream nodes.
        When called as a tool, we need to manually execute the upstream embedding provider node.
        """
        try:
            items = ConnectionResolver.get_items(
                self.workflow,
                self.execution_data,
                self.node_data.name,
                "ai_embedding"
            )
            
            if not items:
                # N8N pattern: When called as tool, typed connection data hasn't been materialized yet.
                # Solution: Get the upstream embedding node and force-execute it to get config.
                # logger.info("[Qdrant] No ai_embedding items found, checking for upstream provider node")
                # logger.info(f"[Qdrant] Current node: '{self.node_data.name}' (id={self.node_data.id})")
                
                upstream_nodes = ConnectionResolver.get_upstream_nodes(
                    self.workflow, 
                    self.node_data.name, 
                    "ai_embedding"
                )
                
                #logger.info(f"[Qdrant] Found {len(upstream_nodes)} upstream ai_embedding nodes")
                
                if upstream_nodes:
                    embedding_node = upstream_nodes[0]
                    # logger.info(f"[Qdrant] DEBUG: embedding_node object type: {type(embedding_node)}")
                    # logger.info(f"[Qdrant] DEBUG: embedding_node.__dict__: {embedding_node.__dict__ if hasattr(embedding_node, '__dict__') else 'N/A'}")
                    # logger.info(f"[Qdrant] DEBUG: embedding_node.type value: '{embedding_node.type}'")
                    # logger.info(f"[Qdrant] DEBUG: embedding_node.name value: '{embedding_node.name}'")
                    # logger.info(f"[Qdrant] Found upstream embedding node: '{embedding_node.name}' (type={embedding_node.type})")
                    
                    # Force-execute the embedding provider node to get its config
                    try:
                        from nodes import node_definitions
                        #logger.info(f"[Qdrant] Looking up node type '{embedding_node.type}' in node_definitions")
                        node_info = node_definitions.get(embedding_node.type)
                        if node_info:
                            #logger.info(f"[Qdrant] Found node class for '{embedding_node.type}'")
                            node_cls = node_info["node_class"]
                            # Create instance with same exec_ref as our tool context
                            embedding_inst = node_cls(embedding_node, self.workflow, self.execution_data)
                            # Provide dummy input data (provider nodes don't need real input)
                            embedding_inst.input_data = {"main": [[NodeExecutionData(json_data={}, binary_data=None)]]}
                            #logger.info(f"[Qdrant] Executing upstream embedding node '{embedding_node.name}'")
                            # Execute to get configuration output
                            result = embedding_inst.execute()
                            #logger.info(f"[Qdrant] Embedding node returned {len(result[0]) if result and result else 0} items")
                            
                            if result and len(result) > 0 and result[0]:
                                provider_data = result[0][0].json_data or {}
                                #logger.info(f"[Qdrant] Provider data keys: {list(provider_data.keys())}")
                                
                                if "_embedding_config_internal" in provider_data:
                                    #logger.info(f"[Qdrant] Successfully obtained embedding config from '{embedding_node.name}'")
                                    return provider_data["_embedding_config_internal"]
                                elif "ai_embedding" in provider_data:
                                    #logger.info(f"[Qdrant] Using ai_embedding config from '{embedding_node.name}'")
                                    return provider_data["ai_embedding"]
                                else:
                                    logger.warning(f"[Qdrant] No embedding config found in provider data")
                        else:
                            logger.warning(f"[Qdrant] Node type '{embedding_node.type}' not found in node_definitions")
                        
                    except Exception as e:
                        logger.error(f"[Qdrant] Failed to execute upstream embedding provider: {e}")
                        import traceback
                        traceback.print_exc()
                
                logger.warning("[Qdrant] No embedding provider found or could not execute upstream node")
                return None
            
            # Get the first item (embedding provider config)
            provider_data = items[0].json_data or {}
            
            # SECURITY: Check for internal config first (contains API key for actual API calls)
            if "_embedding_config_internal" in provider_data:
                return provider_data["_embedding_config_internal"]
            
            # Support multiple formats (fallback to public/sanitized configs)
            if "embedding_provider" in provider_data:
                return provider_data["embedding_provider"]
            elif "ai_embedding" in provider_data:
                return provider_data["ai_embedding"]
            else:
                # Assume the entire data is the provider config
                return provider_data
                
        except Exception as e:
            logger.error(f"Error getting embedding provider: {e}")
            traceback.print_exc()
            return None

    def _create_collection(self) -> Dict[str, Any]:
        """
        Create a new Qdrant collection with specified configuration.
        Uses typed parameters and adapter.
        
        Returns:
            Dictionary with operation status
            
        Raises:
            ParameterError, QdrantError
        """
        # Get raw parameters
        collection_name = self.get_node_parameter("collectionName", 0, "")
        vector_size = self.get_node_parameter("vectorSize", 0, 1536)
        distance = self.get_node_parameter("distance", 0, "Cosine")
        on_disk_payload = self.get_node_parameter("onDiskPayload", 0, False)
        
        # Validate with Pydantic model
        try:
            params = CollectionParams(
                collection_name=collection_name,
                distance=distance,
                on_disk_payload=on_disk_payload
            )
            #logger.info(f"[Qdrant CreateCollection] Validated params: {params.collection_name}")
        except ValidationError as e:
            raise ParameterError(f"Invalid collection parameters: {e}")
        
        # Validate vector size
        if vector_size <= 0:
            raise ParameterError(f"Vector size must be positive, got {vector_size}")
        
        # Use adapter
        adapter = self._initialize_qdrant_adapter()
        
        try:
            result = adapter.create_collection(
                collection_name=params.collection_name,
                vector_size=int(vector_size),
                distance=params.distance,
                on_disk_payload=params.on_disk_payload
            )
            
            #logger.info(f"[Qdrant] Created collection '{params.collection_name}' ({vector_size}D, {params.distance})")
            
            return {
                "status": "success",
                "collection": params.collection_name,
                "vector_size": vector_size,
                "distance": params.distance,
                "result": result
            }
            
        finally:
            adapter.close()

    def _insert_vectors(self, input_data: List[NodeExecutionData]) -> Dict[str, Any]:
        """
        Insert vectors into a Qdrant collection.
        Uses InsertParams for validation and QdrantRetriever/Adapter for insertion.
        
        Supports two modes:
        1. Manual mode: Pre-computed vectors from input data
        2. Typed mode: Auto-generate embeddings from Documents via ai_document + ai_embedding
        
        Args:
            input_data: Input data from previous node
            
        Returns:
            Dictionary with operation status
        """
        try:
            # Get parameters
            collection_name = self.get_node_parameter("collectionName", 0, "")
            input_mode = self.get_node_parameter("inputMode", 0, "auto")
            wait = self.get_node_parameter("wait", 0, True)
            options = self._parse_options(self.get_node_parameter("options", 0, {}))
            batch_size = options.get("batch_size", 100)
            
            # Validate base parameters
            params = InsertParams(
                collection_name=collection_name,
                text_field="pageContent",  # Default for typed mode
                wait=wait
            )
            
            # Determine actual mode (auto-detect if needed)
            actual_mode = input_mode
            if input_mode == "auto":
                # Auto-detect based on available connections
                has_documents = self._has_typed_document_input()
                has_embeddings = self._has_typed_embedding_input()
                
                if has_documents and has_embeddings:
                    actual_mode = "typed"
                    #logger.info("[Qdrant] Auto-detected typed mode (ai_document + ai_embedding)")
                else:
                    actual_mode = "manual"
                    #logger.info("[Qdrant] Auto-detected manual mode (pre-computed vectors)")
            
            # Route to appropriate handler
            if actual_mode == "typed":
                return self._insert_vectors_typed(
                    params, batch_size
                )
            else:
                return self._insert_vectors_manual(
                    input_data, params, batch_size
                )
                
        except (ParameterError, EmbeddingError, QdrantError) as e:
            logger.error(f"[Qdrant Insert] {e.__class__.__name__}: {e.message}")
            return e.to_dict()
            
        except Exception as e:
            logger.error(f"Error inserting vectors: {str(e)}")
            traceback.print_exc()
            return {"error": "InternalError", "message": f"Error inserting vectors: {str(e)}"}

    def _insert_vectors_manual(
        self,
        input_data: List[NodeExecutionData],
        params: InsertParams,
        batch_size: int
    ) -> Dict[str, Any]:
        """
        Insert pre-computed vectors (manual mode).
        Uses QdrantClientAdapter with payload size validation.
        """
        adapter = None
        try:
            vectors_input = self.get_node_parameter("vectorsInput", 0, "fromItems")
            
            # Prepare points to insert
            points = []
            
            if vectors_input == "fromItems":
                # Extract vectors from input items
                vector_field = self.get_node_parameter("vectorField", 0, "vector")
                payload_fields_str = self.get_node_parameter("payloadFields", 0, "")
                payload_fields = [f.strip() for f in payload_fields_str.split(",") if f.strip()] if payload_fields_str else []
                
                for idx, item in enumerate(input_data):
                    item_json = item.json_data or {}
                    
                    # Get vector
                    vector = item_json.get(vector_field)
                    if not vector:
                        logger.warning(f"Item {idx} missing vector field '{vector_field}', skipping")
                        continue
                    
                    # Prepare payload
                    if payload_fields:
                        # Only include specified fields
                        payload = {k: item_json.get(k) for k in payload_fields if k in item_json}
                    else:
                        # Include all fields except the vector
                        payload = {k: v for k, v in item_json.items() if k != vector_field}
                    
                    # Generate ID if not provided
                    point_id = item_json.get("id") or idx
                    
                    points.append({
                        "id": point_id,
                        "vector": vector,
                        "payload": payload
                    })
            else:
                # Use manually defined vectors
                vectors = self.get_node_parameter("vectors", 0, [])
                if not vectors:
                    raise ParameterError("No vectors provided")
                points = vectors
            
            if not points:
                raise ParameterError("No valid points to insert")
            
            # Initialize adapter
            adapter = self._initialize_qdrant_adapter()
            
            # Check payload size and split if necessary
            payload_json = json.dumps({"points": points})
            payload_size = len(payload_json.encode('utf-8'))
            max_size = 30 * 1024 * 1024  # 30MB (QdrantClientAdapter.MAX_PAYLOAD_SIZE)
            
            if payload_size > max_size:
                logger.warning(f"[Qdrant] Payload size {payload_size} bytes exceeds max {max_size} bytes, splitting into batches...")
                # Calculate batch size to keep under limit
                estimated_batch_size = int(len(points) * max_size / payload_size * 0.9)  # 90% safety margin
                batch_size = max(1, min(batch_size, estimated_batch_size))
                #logger.info(f"[Qdrant] Adjusted batch size to {batch_size}")
            
            # Insert points in batches
            total_inserted = 0
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                
                result = adapter.upsert_points(
                    collection_name=params.collection_name,
                    points=batch,
                    wait=params.wait
                )
                
                total_inserted += len(batch)
                #logger.info(f"[Qdrant] Inserted batch {i//batch_size + 1}, total: {total_inserted}/{len(points)}")
            
            return {
                "success": True,
                "message": f"Successfully inserted {total_inserted} vectors into collection '{params.collection_name}'",
                "collection": params.collection_name,
                "inserted": total_inserted,
                "mode": "manual"
            }
            
        finally:
            if adapter:
                adapter.close()

    def _insert_vectors_typed(
        self,
        params: InsertParams,
        batch_size: int
    ) -> Dict[str, Any]:
        """
        Insert vectors with automatic embedding generation (typed mode).
        Uses QdrantRetriever for high-level document insertion with embeddings.
        
        This method:
        1. Gets Documents from ai_document connection
        2. Uses Retriever (which handles embedding provider internally)
        3. Inserts documents with auto-generated embeddings
        """
        # Get typed inputs
        documents = self._get_typed_documents()
        if not documents:
            raise ParameterError("No documents received from ai_document connection")
        
        #logger.info(f"[Qdrant] Processing {len(documents)} documents in typed mode")
        
        # Initialize retriever (handles adapter + embedding provider)
        retriever = self._initialize_retriever()
        
        # Use retriever for document insertion (handles embedding generation internally)
        # Note: batch_size is handled internally by the provider, not passed here
        result = retriever.insert_documents(
            collection_name=params.collection_name,
            documents=documents,
            text_field=params.text_field,
            wait=params.wait
        )
        
        inserted_count = result.get("documents_inserted", 0)
        #logger.info(f"[Qdrant] Inserted {inserted_count} documents in typed mode")
        
        return {
            "success": True,
            "message": f"Successfully inserted {inserted_count} documents into collection '{params.collection_name}'",
            "collection": params.collection_name,
            "inserted": inserted_count,
            "mode": "typed"
        }

    def _search_vectors(self) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in a Qdrant collection.
        Uses new refactored infrastructure: typed params, adapter, retriever.
        
        Returns:
            List of search results with scores
            
        Raises:
            ParameterError, EmbeddingError, QdrantError (converted to error dicts by execute())
        """
        # Get raw parameters
        collection_name = self.get_node_parameter("collectionName", 0, "")
        query_text_param = self.get_node_parameter("query", 0, "")
        query_vector = self.get_node_parameter("queryVector", 0, [])
        top_k = self.get_node_parameter("topK", 0, 10)  # UI param is topK
        score_threshold = self.get_node_parameter("scoreThreshold", 0, 0.0)
        filter_obj = self.get_node_parameter("filter", 0, {})
        with_payload = self.get_node_parameter("withPayload", 0, True)
        with_vector = self.get_node_parameter("withVector", 0, False)
        
        # Validate with Pydantic model (enforces topK → top_k naming)
        try:
            # Convert filter dict to JSON string for Pydantic validation
            filter_str = json.dumps(filter_obj) if filter_obj else None
            
            params = SearchParams(
                collection_name=collection_name,
                top_k=top_k,
                score_threshold=score_threshold,
                filter=filter_str
            )
            #logger.info(f"[Qdrant Search] Validated params: collection={params.collection_name}, top_k={params.top_k}")
        except ValidationError as e:
            raise ParameterError(f"Invalid search parameters: {e}")
        
        # Determine query source
        query_text = query_text_param or None
        
        # If no explicit query, check input data
        if not query_text and not query_vector:
            input_data = self.get_input_data()
            if input_data and input_data[0].json_data:
                item_data = input_data[0].json_data
                
                # Check common query fields
                for field in ["query", "text", "message", "input", "chatInput", "question"]:
                    if field in item_data and item_data[field]:
                        query_text = str(item_data[field])
                        #logger.info(f"[Qdrant Search] Found query in '{field}': {query_text[:50]}...")
                        break
                
                # Check for pre-computed vector from main input (ALWAYS check, not just when no query_text)
                if not query_vector:
                    for field in ["queryVector", "query_vector", "embedding", "vector"]:
                        if field in item_data and isinstance(item_data[field], list):
                            query_vector = item_data[field]
                            #logger.info(f"[Qdrant Search] Using {field} from input ({len(query_vector)}D)")
                            break
        
        # Check ai_embedding connection for pre-computed embeddings
        if not query_vector:
            ai_embedding_data = self.get_input_data("ai_embedding", 0)
            if ai_embedding_data:
                #logger.info(f"[Qdrant Search] Checking ai_embedding connection ({len(ai_embedding_data)} items)")
                for item in ai_embedding_data:
                    if item.json_data:
                        # Check for embedding field
                        if "embedding" in item.json_data and isinstance(item.json_data["embedding"], list):
                            query_vector = item.json_data["embedding"]
                            #logger.info(f"[Qdrant Search] Using embedding from ai_embedding connection ({len(query_vector)}D)")
                            break
        
        # If we have text but no vector, generate embedding
        if query_text and not query_vector:
            #logger.info(f"[Qdrant Search] Generating embedding for query...")
            
            try:
                provider = self._initialize_embedding_provider()
                if not provider:
                    raise EmbeddingError(
                        "Query text provided but no embedding provider configured. "
                        "Connect an embeddings node or configure embeddingsOpenAi credential."
                    )
                
                embeddings = provider.generate_embeddings([query_text])
                query_vector = embeddings[0]
                #logger.info(f"[Qdrant Search] Generated {len(query_vector)}D embedding")
                
            except EmbeddingError:
                raise  # Re-raise our errors
            except Exception as e:
                raise EmbeddingError(f"Failed to generate embedding: {str(e)}")
        
        # Validate we have a query vector
        if not query_vector:
            raise ParameterError(
                "Query vector is required. Provide either: "
                "1) 'query' parameter with text + embedding provider, "
                "2) 'queryVector' parameter with pre-computed vector, or "
                "3) Input data with 'query'/'embedding' field"
            )
        
        # Use adapter for search (with connection pooling + retry)
        adapter = self._initialize_qdrant_adapter()
        
        try:
            results = adapter.search(
                collection_name=params.collection_name,
                query_vector=query_vector,
                limit=params.top_k,
                score_threshold=params.score_threshold if params.score_threshold > 0 else None,
                filter_obj=params.filter_obj,
                with_payload=with_payload,
                with_vector=with_vector
            )
            
            logger.info(f"[Qdrant Search] Found {len(results)} results")
            
            # Format results for output
            formatted_results = []
            for item in results:
                formatted = {
                    "id": item.get("id"),
                    "score": item.get("score")
                }
                
                if with_payload:
                    formatted["payload"] = item.get("payload", {})
                
                if with_vector:
                    formatted["vector"] = item.get("vector")
                
                formatted_results.append(formatted)
            
            # Return single dict with query + results (preserves query for downstream nodes like AI Agent)
            return [{
                "query": query_text or "",  # Preserve original query text
                "results": formatted_results,
                "count": len(formatted_results),
                "collection": params.collection_name
            }]
            
        finally:
            adapter.close()  # Clean up connection pool

    def _retrieve_as_tool(self) -> List[Dict[str, Any]]:
        """
        Legacy tool mode retrieval (still used in production).
        
        Implements the retriever interface for AI Agent tool mode:
        - Input: query string from AI Agent tool call
        - Output: List of relevant documents with pageContent + metadata
        
        Returns:
            List of documents in n8n format (pageContent + metadata)
        """
        
        try:
            # Get configuration
            collection_name = self.get_node_parameter("collectionName", 0, "")
            if not collection_name:
                raise ParameterError("Collection name is required")
            
            limit = self.get_node_parameter("topK", 0, 30)
            # Get scoreThreshold from parameter (not options)
            score_threshold = self.get_node_parameter("scoreThreshold", 0, 0.0)
            
            # Extract query from tool call arguments or input data
            input_data = self.get_input_data()
            if not input_data or not input_data[0].json_data:
                raise ParameterError("No input data available")
            
            query_data = input_data[0].json_data
            
            # When called as tool, query is in the 'query' field from tool args
            # When called normally, query is in various possible fields
            if isinstance(query_data, dict) and "query" in query_data:
                # Tool mode: extract query text
                query_text = query_data["query"]
                query_data = {"query": query_text}
            
            # Initialize retriever (uses adapter + provider)
            retriever = self._initialize_retriever()
            
            # Use retriever's search_as_tool_output for RAG
            results = retriever.search_as_tool_output(
                collection_name=collection_name,
                query_data=query_data,
                top_k=limit,
                score_threshold=score_threshold
            )
            
            logger.info(f"[Qdrant Retriever] Found {len(results)} documents")
            
            return results
            
        except (ParameterError, EmbeddingError, QdrantError) as e:
            # Structured errors from our infrastructure
            logger.error(f"[Qdrant Retriever] {e.__class__.__name__}: {e.message}")
            return [e.to_dict()]
            
        except Exception as e:
            # Catch unexpected errors
            logger.error(f"[Qdrant Retriever] Unexpected error: {str(e)}")
            traceback.print_exc()
            error_dict = {
                "error": "InternalError",
                "message": f"Retriever operation failed: {str(e)}",
                "details": {"type": type(e).__name__}
            }
            return [error_dict]

    def _retrieve_vectors(self) -> List[Dict[str, Any]]:
        """
        Retrieve vectors by ID or filter.
        Uses QdrantClientAdapter for retrieval.
        
        Returns:
            List of retrieved points
        """
        adapter = None
        try:
            # Get parameters
            collection_name = self.get_node_parameter("collectionName", 0, "")
            point_ids = self.get_node_parameter("pointIds", 0, [])
            filter_str = self.get_node_parameter("filter", 0, "")
            with_payload = self.get_node_parameter("withPayload", 0, True)
            with_vector = self.get_node_parameter("withVector", 0, False)
            limit = self.get_node_parameter("retrieveLimit", 0, 100)
            offset = self.get_node_parameter("retrieveOffset", 0, 0)
            
            if not collection_name:
                raise ParameterError("Collection name is required")
            
            # Initialize adapter
            adapter = self._initialize_qdrant_adapter()
            
            if point_ids:
                # Retrieve specific points by IDs
                # Parse filter if provided
                filter_obj = None
                if filter_str:
                    try:
                        filter_obj = json.loads(filter_str) if isinstance(filter_str, str) else filter_str
                    except json.JSONDecodeError as e:
                        logger.warning(f"[Qdrant] Invalid filter JSON: {e}")
                
                # Use scroll with ID filter
                result = adapter.scroll(
                    collection_name=collection_name,
                    limit=len(point_ids),
                    offset=None,
                    filter_obj=filter_obj,
                    with_payload=with_payload,
                    with_vector=with_vector
                )
                
                # Filter results to only requested IDs
                all_points = result.get("result", {}).get("points", [])
                points = [p for p in all_points if p.get("id") in point_ids]
            else:
                # Scroll through collection with optional filter
                filter_obj = None
                if filter_str:
                    try:
                        filter_obj = json.loads(filter_str) if isinstance(filter_str, str) else filter_str
                    except json.JSONDecodeError as e:
                        logger.warning(f"[Qdrant] Invalid filter JSON: {e}")
                
                result = adapter.scroll(
                    collection_name=collection_name,
                    limit=int(limit),
                    offset=int(offset),
                    filter_obj=filter_obj,
                    with_payload=with_payload,
                    with_vector=with_vector
                )
                
                points = result.get("result", {}).get("points", [])
            
            return points
            
        finally:
            if adapter:
                adapter.close()

    def _delete_vectors(self) -> Dict[str, Any]:
        """
        Delete vectors from a collection by IDs or filter.
        Uses DeleteParams for validation and QdrantClientAdapter for deletion.
        
        Returns:
            Dictionary with operation status
        """
        adapter = None
        try:
            # Get parameters
            collection_name = self.get_node_parameter("collectionName", 0, "")
            point_ids = self.get_node_parameter("pointIds", 0, [])
            filter_str = self.get_node_parameter("filter", 0, "")
            
            # Validate with Pydantic
            params = DeleteParams(
                collection_name=collection_name,
                point_ids=point_ids,
                filter=filter_str
            )
            
            # Initialize adapter
            adapter = self._initialize_qdrant_adapter()
            
            # Delete using adapter
            result = adapter.delete_points(
                collection_name=params.collection_name,
                point_ids=params.point_ids_list if params.point_ids_list else None,
                filter_obj=params.filter_obj if params.filter_obj else None
            )
            
            deleted_count = result.get("result", {}).get("operation_id") or "unknown"
            logger.info(f"[Qdrant Delete] Deleted vectors from '{params.collection_name}' (operation: {deleted_count})")
            
            return {
                "success": True,
                "message": f"Successfully deleted vectors from collection '{params.collection_name}'",
                "collection": params.collection_name,
                "response": result
            }
            
        finally:
            if adapter:
                adapter.close()

    def _get_collection_info(self) -> Dict[str, Any]:
        """
        Get information about a Qdrant collection.
        Uses QdrantClientAdapter for retrieval.
        
        Returns:
            Dictionary with collection information
        """
        adapter = None
        try:
            # Get parameter
            collection_name = self.get_node_parameter("collectionName", 0, "")
            
            if not collection_name:
                raise ParameterError("Collection name is required")
            
            # Initialize adapter
            adapter = self._initialize_qdrant_adapter()
            
            # Get collection info using adapter
            result = adapter.get_collection_info(collection_name)
            
            return result.get("result", {})
            
        finally:
            if adapter:
                adapter.close()
    
    # ==================== LangChain Runnable Integration ====================
    
    def get_runnable(self, item_index: int = 0):
        """
        Get LangChain-compatible QdrantRetrieverRunnable for LCEL composition.
        
        This method wraps Qdrant vector search as a Runnable, enabling:
        - Composition with other Runnables using LCEL (|)
        - RAG (Retrieval-Augmented Generation) patterns
        - Integration with LangChain chains and agents
        
        Args:
            item_index: Index of the input item to use for configuration (default: 0)
        
        Returns:
            QdrantRetrieverRunnable: A Runnable that performs vector similarity search
        
        Example:
            # Get the retriever as a Runnable
            retriever = qdrant_node.get_runnable()
            
            # Search for relevant documents
            result = retriever.invoke({
                "query": "What is LangChain?"
            })
            
            # Use in RAG chain
            rag_chain = retriever | format_docs | chat_model | output_parser
        """
        
        from utils.langchain_retrievers import QdrantRetrieverRunnable
        from utils.langchain_base import RunnableRegistry
        
        # Get parameters
        collection_name = self.get_node_parameter("collectionName", item_index, "documents")
        top_k = int(self.get_node_parameter("topK", item_index, 30))
        
        # Initialize retriever (uses existing infrastructure)
        retriever = self._initialize_retriever()
        
        # Create executor function that wraps the retriever
        def executor(args: Dict[str, Any]) -> Dict[str, Any]:
            """Execute retrieval with Qdrant retriever"""
            query = args.get("query", "")
            k = args.get("top_k", top_k)
            filter_obj = args.get("filter", None)
            
            try:
                # Call retriever's search method directly
                results = retriever.search(
                    collection_name=collection_name,
                    query=query,
                    top_k=k,
                    score_threshold=0.0,
                    filter_obj=filter_obj,
                    include_metadata=True
                )
                
                # CRITICAL FIX: Format results to match n8n's document structure
                # n8n uses 'pageContent' (camelCase), not 'page_content' (snake_case)
                documents = []
                for hit in results:
                    payload = hit.get("payload", {})
                    # Extract text content from various possible fields
                    text_content = payload.get("text", "") or payload.get("content", "") or payload.get("pageContent", "")
                    
                    # CRITICAL: Extract metadata from nested metadata field, not entire payload
                    # n8n stores metadata separately from content
                    metadata = payload.get("metadata", {})
                    
                    doc = {
                        "pageContent": text_content,  # Use camelCase to match n8n
                        "metadata": metadata,  # Only metadata, not entire payload
                        "score": hit.get("score", 0.0)
                    }
                    documents.append(doc)
                return {
                    "documents": documents,
                    "count": len(documents)
                }
            
            except Exception as e:
                logger.error(f"[Qdrant] Retriever executor error: {e}")
                logger.error(f"[Qdrant] Error type: {type(e)}")
                import traceback
                logger.error(f"[Qdrant] Traceback:\n{traceback.format_exc()}")
                raise
        
        # Create Runnable
        runnable = QdrantRetrieverRunnable(
            retriever_executor=executor,
            top_k=top_k,
            collection_name=collection_name
        )
        
        # NOTE: Registry cleanup removed - use managed_runnable() context manager instead
        # For manual registration, call RunnableRegistry.register(runnable) explicitly
        # See utils.runnable_helpers.managed_runnable for automatic lifecycle management
        
        return runnable


        if hasattr(self, '_runnable'):
            delattr(self, '_runnable')
        
        logger.debug("[QdrantVectorStoreNode] Cleaned up QdrantRetrieverRunnable")
    
    @classmethod
    def get_custom_tool_schema(cls, selected_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Custom tool schema for AI Agent integration.
        
        When Qdrant is used as a tool, the agent should pass a 'query' parameter (text to search for),
        not the internal 'operation' parameter.
        
        Args:
            selected_params: The node's configured parameters from workflow JSON
        
        Returns:
            Custom tool schema dict with query parameter, or None to use default
        """
        collection_name = selected_params.get('collectionName', 'knowledge base')
        
        return {
            "description": f"Search the '{collection_name}' vector database for relevant information. Use this when you need to find documents related to the user's query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query text to find relevant documents"
                    }
                },
                "required": ["query"]
            }
        }
