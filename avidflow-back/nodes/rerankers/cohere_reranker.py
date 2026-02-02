"""
Cohere Reranker node using LangChain integration.

This node provides a reranker connection point for vector stores.
It uses LangChain's native CohereRerank for better compatibility.
"""
from typing import Dict, List, Any, Optional
import logging

from models import NodeExecutionData
from nodes.base import BaseNode, NodeParameterType
from credentials.cohereApi import CohereApiCredential
from utils.cohere_client import CohereReranker

logger = logging.getLogger(__name__)

class RerankerCohereNode(BaseNode):
    """
    Cohere Reranker node for improving retrieval relevance.
    
    Re-ranks retrieved documents using Cohere's cross-encoder models,
    which provide more accurate relevance scores than embedding similarity alone.
    
    This node is designed to be connected to vector store nodes via the
    'ai_reranker' connection type. It doesn't process data directly but provides
    a reranker instance when the vector store calls get_reranker().
    """
    
    type = "rerankerCohere"
    version = 1
    
    description = {
        "displayName": "Reranker Cohere",
        "name": "rerankerCohere",
        "icon": "file:cohere.svg",
        "group": ["ai"],
        "description": "Rerank documents using Cohere's rerank models",
        "defaults": {"name": "Reranker Cohere"},
        "inputs": [],  # No main input - this is a connection provider
        "outputs": [
            {"name": "ai_reranker", "type": "ai_reranker", "required": True}
        ],
        "credentials": [
            {
                "name": "cohereApi",
                "required": True
            }
        ]
    }
    
    properties = {
        "parameters": [
            {
                "name": "model",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "options": [
                    {
                        "name": "Rerank English v3.0",
                        "value": "rerank-english-v3.0",
                        "description": "Best for English text"
                    },
                    {
                        "name": "Rerank Multilingual v3.0",
                        "value": "rerank-multilingual-v3.0",
                        "description": "Supports 100+ languages including Persian"
                    },
                    {
                        "name": "Rerank English v2.0",
                        "value": "rerank-english-v2.0",
                        "description": "Legacy English model"
                    }
                ],
                "default": "rerank-multilingual-v3.0",
                "description": "Cohere reranking model to use"
            },
            {
                "name": "topK",
                "type": NodeParameterType.NUMBER,
                "display_name": "Top K",
                "default": 5,
                "description": "Number of top results to return after reranking",
                "placeholder": "5"
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "options": [
                    {
                        "name": "timeout",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Timeout (seconds)",
                        "default": 30,
                        "description": "API request timeout"
                    }
                ]
            }
        ],
        "credentials": [
            {
                "name": "cohereApi",
                "required": True
            }
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute reranking operation.
        
        Note: This node is designed to be called by QdrantVectorStoreNode
        through the ai_reranker connection, not executed standalone.
        The actual reranking happens when connected nodes call get_reranker().
        """
        try:
            # Get input data
            input_data = self.get_input_data()
            
            # Handle empty input data case
            if not input_data:
                return [[]]
            
            # This node provides a reranker interface, not direct execution
            # Return status information
            return [[NodeExecutionData(
                json_data={
                    "message": "Reranker Cohere node is active and ready",
                    "model": self.get_node_parameter("model", 0, "rerank-multilingual-v3.0"),
                    "top_k": self.get_node_parameter("topK", 0, 5),
                    "note": "This node provides reranking through ai_reranker connection"
                }
            )]]
            
        except Exception as e:
            logger.error(f"[RerankerCohere] Execute error: {e}")
            return [[NodeExecutionData(
                json_data={
                    "error": True,
                    "message": str(e)
                }
            )]]
    
    def get_reranker(self) -> CohereReranker:
        """
        Get configured Cohere reranker instance.
        
        This method is called by nodes that connect to this reranker
        (e.g., QdrantVectorStoreNode with useReranker=True).
        
        Returns:
            CohereReranker instance configured with node parameters
        
        Raises:
            ValueError: If credentials are missing or invalid
        """
        # Get credential
        credentials = self.get_credentials("cohereApi")
        if not credentials:
            raise ValueError("Cohere API credentials not configured")
        
        api_key = credentials.get("apiKey")
        if not api_key:
            raise ValueError("Cohere API key not found in credentials")
        
        # Get parameters
        model = self.get_node_parameter("model", 0, "rerank-multilingual-v3.0")
        top_k = self.get_node_parameter("topK", 0, 5)
        options = self.get_node_parameter("options", 0, {})
        timeout = options.get("timeout", 30)
        
        logger.info(
            f"[RerankerCohere] Initializing reranker with model={model}, top_k={top_k}"
        )
        
        return CohereReranker(
            api_key=api_key,
            model=model,
            top_k=top_k,
            timeout=timeout
        )
