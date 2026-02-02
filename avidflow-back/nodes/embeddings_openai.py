"""
OpenAI Embeddings node for generating text embeddings using OpenAI's API.

This node outputs ai_embedding type connections that can be consumed by:
- QdrantVectorStore (typed mode)
- Other vector store nodes
- Retrieval/similarity search operations

Architecture:
- Follows BaseNode pattern from base.py
- Outputs ai_embedding typed connection
- Synchronous operation (compatible with Celery)
- Uses OpenAI's text-embedding models
"""
from typing import Dict, List, Any, Optional
from models import NodeExecutionData
from nodes.base import BaseNode, NodeParameterType
import requests
import json
import logging

logger = logging.getLogger(__name__)


class EmbeddingsOpenAINode(BaseNode):
    """
    OpenAI Embeddings node for generating text embeddings.
    
    This node provides embedding configuration via ai_embedding output type.
    The actual embedding generation happens in consuming nodes (like QdrantVectorStore).
    """
    
    type = "ai_embedding"
    version = 1.0
    
    description = {
        "displayName": "OpenAI Embeddings",
        "name": "ai_embedding",
        "icon": "file:openai.svg",
        "group": ["ai"],
        "description": "Generate text embeddings using OpenAI's embedding models",
        "defaults": {"name": "OpenAI Embeddings"},
        "inputs": [
            {"name": "main", "type": "main", "required": True}
        ],
        "outputs": [
            {"name": "ai_embedding", "type": "ai_embedding", "required": True}
        ]
    }
    
    properties = {
        "parameters": [
            {
                "name": "model",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "description": "The embedding model to use",
                "options": [
                    {
                        "name": "text-embedding-3-small",
                        "value": "text-embedding-3-small",
                        "description": "Smaller, faster, cost-effective (1536 dimensions)"
                    },
                    {
                        "name": "text-embedding-3-large", 
                        "value": "text-embedding-3-large",
                        "description": "Larger, more accurate (3072 dimensions)"
                    },
                    {
                        "name": "text-embedding-ada-002",
                        "value": "text-embedding-ada-002",
                        "description": "Legacy model (1536 dimensions)"
                    }
                ],
                "default": "text-embedding-3-small"
            },
            {
                "name": "dimensions",
                "type": NodeParameterType.NUMBER,
                "display_name": "Dimensions",
                "description": "Number of dimensions for the embeddings (optional, model-specific defaults)",
                "default": 1536,
                "typeOptions": {
                    "minValue": 1,
                    "maxValue": 3072
                },
                "placeholder": "1536"
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "description": "Additional options for OpenAI embeddings",
                "default": {},
                "options": [
                    {
                        "name": "batchSize",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Batch Size",
                        "description": "Number of texts to send in each API request (max 2048 for OpenAI)",
                        "default": 100,
                        "typeOptions": {
                            "minValue": 1,
                            "maxValue": 2048
                        }
                    },
                    {
                        "name": "stripNewLines",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Strip New Lines",
                        "description": "Whether to strip new lines from text before embedding",
                        "default": True
                    },
                    {
                        "name": "timeout",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Timeout (seconds)",
                        "description": "Request timeout in seconds",
                        "default": 60,
                        "typeOptions": {
                            "minValue": 1,
                            "maxValue": 300
                        }
                    },
                    {
                        "name": "baseUrl",
                        "type": NodeParameterType.STRING,
                        "display_name": "Base URL",
                        "description": "Custom OpenAI API base URL (for proxies or custom deployments)",
                        "default": "",
                        "placeholder": "https://api.openai.com/v1"
                    },
                    {
                        "name": "organization",
                        "type": NodeParameterType.STRING,
                        "display_name": "Organization ID",
                        "description": "OpenAI organization ID (optional)",
                        "default": "",
                        "placeholder": "org-..."
                    }
                ]
            }
        ],
        "credentials": [
            {
                "name": "openAiApi",
                "required": True,
                "displayOptions": {
                    "show": {
                        "@version": [1]
                    }
                }
            }
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the embeddings node.
        
        This node outputs embedding configuration (provider metadata) that consuming
        nodes use to generate embeddings. It does NOT generate embeddings itself.
        
        Returns:
            List[List[NodeExecutionData]]: Output items with ai_embedding config
        """
        try:
            # Get input data (can be empty, we just pass through with embedding config)
            input_data = self.get_input_data()
            
            # If no input data, create a single item to carry the embedding config
            if not input_data:
                logger.debug("[OpenAI Embeddings] No input data, creating default item with embedding config")
                input_data = [[]]
            
            results: List[NodeExecutionData] = []
            
            for item_index, item in enumerate(input_data):
                # Get parameters for this item
                model = self.get_node_parameter("model", item_index, "text-embedding-3-small")
                dimensions = self.get_node_parameter("dimensions", item_index, 1536)
                options = self.get_node_parameter("options", item_index, {}) or {}
                
                # Get credentials
                credentials = self.get_credentials("openAiApi")
                if not credentials:
                    logger.error("[OpenAI Embeddings] No OpenAI credentials found")
                    results.append(NodeExecutionData(
                        json_data={"error": "No OpenAI credentials found"},
                        binary_data=None
                    ))
                    continue
                
                # Extract credential data
                api_key = credentials.get("apiKey", "")
                if not api_key:
                    logger.error("[OpenAI Embeddings] API key is missing in credentials")
                    results.append(NodeExecutionData(
                        json_data={"error": "API key is missing"},
                        binary_data=None
                    ))
                    continue
                
                # Build base URL
                base_url = options.get("baseUrl", "").strip()
                if not base_url:
                    base_url = credentials.get("baseUrl", "https://api.openai.com/v1")
                base_url = base_url.rstrip('/')
                
                # Build embedding provider configuration
                # This is what consuming nodes (like QdrantVectorStore) will use
                embedding_config = {
                    "type": "openai",
                    "model": model,
                    "dimensions": int(dimensions),
                    "api_key": api_key,  # SECURITY: Only passed internally, never exposed in output
                    "base_url": base_url,
                }
                
                # Add optional parameters
                if options.get("organization"):
                    embedding_config["organization"] = options["organization"]
                if options.get("timeout"):
                    embedding_config["timeout"] = int(options["timeout"])
                if options.get("batchSize"):
                    embedding_config["batchSize"] = int(options["batchSize"])
                if options.get("stripNewLines") is not None:
                    embedding_config["stripNewLines"] = bool(options["stripNewLines"])
                
                logger.debug(f"[OpenAI Embeddings] Item {item_index}: model={model}, dimensions={dimensions}")
                
                # Check if there's text input that needs embedding
                # Common text fields: query, text, content, message, input
                text_to_embed = None
                text_field = None
                for field in ["query", "text", "content", "message", "input", "chatInput"]:
                    if field in item.json_data and item.json_data[field]:
                        text_to_embed = str(item.json_data[field])
                        text_field = field
                        break
                
                # SECURITY: Create sanitized config for output (without API key)
                sanitized_config = {
                    "type": embedding_config["type"],
                    "model": embedding_config["model"],
                    "dimensions": embedding_config["dimensions"],
                    "base_url": embedding_config["base_url"],
                }
                # Copy optional params (excluding sensitive data)
                if "timeout" in embedding_config:
                    sanitized_config["timeout"] = embedding_config["timeout"]
                if "batchSize" in embedding_config:
                    sanitized_config["batchSize"] = embedding_config["batchSize"]
                if "stripNewLines" in embedding_config:
                    sanitized_config["stripNewLines"] = embedding_config["stripNewLines"]
                
                # Output item with embedding configuration
                # The ai_embedding field is what typed connections look for
                output_data = {
                    **item.json_data,  # Preserve original data
                    "ai_embedding": sanitized_config,  # Add sanitized config (no API key)
                    "embedding_provider": sanitized_config,  # Alternative key for compatibility
                    "_embedding_config_internal": embedding_config  # Full config with API key (for internal use)
                }
                
                # If there's text to embed, generate the embedding
                if text_to_embed:
                    logger.info(f"[OpenAI Embeddings] Generating embedding for {text_field}='{text_to_embed[:50]}...'")
                    try:
                        embeddings = self._generate_embeddings_sync(
                            [text_to_embed],
                            model=model,
                            api_key=api_key,
                            base_url=base_url,
                            dimensions=dimensions,
                            timeout=embedding_config.get("timeout", 60)
                        )
                        if embeddings and len(embeddings) > 0:
                            output_data["embedding"] = embeddings[0]
                            logger.info(f"[OpenAI Embeddings] Generated {len(embeddings[0])}-dimensional embedding")
                    except Exception as embed_error:
                        logger.error(f"[OpenAI Embeddings] Failed to generate embedding: {embed_error}")
                        output_data["embedding_error"] = str(embed_error)
                
                results.append(NodeExecutionData(
                    json_data=output_data,
                    binary_data=item.binary_data
                ))
            
            logger.info(f"[OpenAI Embeddings] Processed {len(results)} items with embedding config")
            return [results]
            
        except Exception as e:
            logger.error(f"[OpenAI Embeddings] Error: {e}", exc_info=True)
            return [[NodeExecutionData(
                json_data={"error": f"OpenAI Embeddings error: {str(e)}"},
                binary_data=None
            )]]
    
    # ============================================================================
    # Utility Methods (for future direct embedding generation if needed)
    # ============================================================================
    
    def _generate_embeddings_sync(
        self,
        texts: List[str],
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        dimensions: Optional[int] = None,
        organization: Optional[str] = None,
        timeout: int = 60
    ) -> List[List[float]]:
        """
        Generate embeddings synchronously using OpenAI API.
        
        NOTE: This method is currently NOT used by execute().
        It's provided for future direct embedding generation if needed.
        
        Args:
            texts: List of text strings to embed
            model: OpenAI embedding model name
            api_key: OpenAI API key
            base_url: API base URL
            dimensions: Number of dimensions (optional)
            organization: Organization ID (optional)
            timeout: Request timeout in seconds
            
        Returns:
            List[List[float]]: List of embedding vectors
            
        Raises:
            ValueError: If API request fails
        """
        url = f"{base_url}/embeddings"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        if organization:
            headers["OpenAI-Organization"] = organization
        
        payload = {
            "input": texts,
            "model": model
        }
        
        if dimensions:
            payload["dimensions"] = dimensions
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code != 200:
                error_text = response.text
                raise ValueError(f"OpenAI API error ({response.status_code}): {error_text}")
            
            data = response.json()
            
            # Extract embeddings from response
            embeddings = []
            for item in data.get("data", []):
                embedding = item.get("embedding", [])
                embeddings.append(embedding)
            
            if len(embeddings) != len(texts):
                raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")
            
            return embeddings
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Request failed: {str(e)}")
    
    def _batch_generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = 100,
        **kwargs
    ) -> List[List[float]]:
        """
        Generate embeddings in batches to handle large text lists.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch
            **kwargs: Additional parameters for _generate_embeddings_sync
            
        Returns:
            List[List[float]]: All embedding vectors
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.debug(f"[OpenAI Embeddings] Generating batch {i//batch_size + 1} ({len(batch)} texts)")
            
            batch_embeddings = self._generate_embeddings_sync(batch, **kwargs)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
