"""
Wrapper for retrievers as tool-callable Runnables.

This module provides RetrieverToolRunnable, which wraps a retriever
(like QdrantRetrieverRunnable) as a LangChain Tool that can be called
by AI agents during reasoning loops.

This enables RAG (Retrieval-Augmented Generation) patterns where the
agent can search knowledge bases and use retrieved context to answer questions.
"""
from __future__ import annotations
from typing import Dict, Any, Tuple, Optional
import logging
import json

from utils.langchain_tools import ToolRunnable
from utils.langchain_retrievers import QdrantRetrieverRunnable

logger = logging.getLogger(__name__)


class RetrieverToolRunnable(ToolRunnable):
    """
    Wraps a QdrantRetrieverRunnable as a tool that can be called by agents.
    
    This allows agents to use vector search as a tool during reasoning,
    enabling RAG patterns where the agent:
    1. Recognizes it needs information
    2. Calls the retriever tool with a query
    3. Receives relevant documents
    4. Uses the context to formulate an answer
    
    Example:
        retriever_runnable = qdrant_node.get_runnable()
        
        retriever_tool = RetrieverToolRunnable(
            retriever_runnable=retriever_runnable,
            collection_name="documentation"
        )
        
        # Agent can now call this as a tool
        result = retriever_tool.invoke({
            "arguments": {"query": "How to use LangChain?"}
        })
        # Returns formatted documents for LLM consumption
    """
    
    def __init__(
        self,
        retriever_runnable: QdrantRetrieverRunnable,
        collection_name: str,
        description: Optional[str] = None,
        max_results: int = 30,
        qdrant_node: Any = None,
        item_index: int = 0,
        **kwargs: Any
    ):
        """
        Initialize Retriever Tool.
        
        Args:
            retriever_runnable: QdrantRetrieverRunnable instance
            collection_name: Name of vector collection
            description: Custom tool description (optional)
            max_results: Maximum number of results to return (default: 30)
            qdrant_node: Optional QdrantVectorStoreNode for dynamic parameter reading
            item_index: Item index for parameter resolution
            **kwargs: Additional config
        """
        # Generate tool name and description
        tool_name = f"search_{collection_name.lower().replace(' ', '_')}"
        
        if description is None:
            description = (
                f"Search the {collection_name} knowledge base for relevant information. "
                f"Use this when you need to find specific facts, documentation, or context "
                f"to answer the user's question accurately."
            )
        
        # Schema for retriever tool
        # Note: top_k is NOT exposed to AI - it uses the configured limit from node parameters
        schema = {
            "query": {
                "type": "string",
                "required": True,
                "description": "The search query to find relevant documents"
            }
        }
        
        # Store references for dynamic parameter reading
        stored_qdrant_node = qdrant_node
        stored_item_index = item_index
        stored_max_results = max_results
        
        # Executor delegates to retriever
        def executor(args: Dict[str, Any]) -> Tuple[Any, Any]:
            try:
                # Extract tool arguments
                query = args.get("query", "")
                
                # Read topK dynamically from Qdrant node if available
                # This allows topK to be updated in workflow without recreating tool
                if stored_qdrant_node is not None:
                    try:
                        top_k = stored_qdrant_node.get_node_parameter("topK", stored_item_index, stored_max_results)
                    except Exception:
                        # Fallback to max_results if parameter reading fails
                        top_k = stored_max_results
                else:
                    # No node reference, use configured max_results
                    top_k = stored_max_results
                
                # Prepare retriever input (only what retriever expects)
                retriever_input = {
                    "query": query,
                    "top_k": top_k
                }
                
                # Invoke retriever with clean input
                result = retriever_runnable.invoke(retriever_input)
                
                if not result.get("success"):
                    error = result.get("error", "Retrieval failed")
                    logger.error(f"[RetrieverToolRunnable] Retrieval error: {error}")
                    raise RuntimeError(error)
                
                # Format documents for LLM consumption
                documents = result.get("documents", [])
                formatted = self._format_documents_for_llm(documents, query)
                
                return formatted, None
                
            except Exception as e:
                logger.error(f"[RetrieverToolRunnable] Error: {e}")
                raise
        
        super().__init__(
            name=tool_name,
            description=description,
            executor=executor,
            schema=schema,
            **kwargs
        )
        
        self.retriever_runnable = retriever_runnable
        self.collection_name = collection_name
        self.max_results = max_results
        self.qdrant_node = qdrant_node
        self.item_index = item_index
    
    @staticmethod
    def _format_documents_for_llm(documents: list, query: str) -> list:
        """
        Format retrieved documents for LLM consumption.
        
        CRITICAL: Returns list of JSON-formatted text strings to match n8n's format.
        n8n sends each document as a stringified JSON object with 'type: text'.
        
        Format matches n8n's retriever tool output:
        [
          {"type": "text", "text": "{\"pageContent\":\"...\",\"metadata\":{...}}"},
          {"type": "text", "text": "{\"pageContent\":\"...\",\"metadata\":{...}}"},
          ...
        ]
        
        Args:
            documents: List of retrieved documents
            query: Original search query
        
        Returns:
            List of text blocks formatted as n8n tool output
        """
        import json
        
        if not documents:
            return [
                {
                    "type": "text",
                    "text": f"No relevant documents found for query: '{query}'"
                }
            ]
        
        formatted_blocks = []
        
        for doc in documents:
            # Extract fields (try both camelCase and snake_case)
            page_content = doc.get("pageContent", "") or doc.get("page_content", "")
            metadata = doc.get("metadata", {})
            
            # CRITICAL: Create the exact structure n8n uses
            # Each document is a JSON string wrapped in {"type": "text", "text": "..."}
            doc_obj = {
                "pageContent": page_content,
                "metadata": metadata
            }
            
            # Serialize to JSON string (this is what n8n does)
            doc_json_str = json.dumps(doc_obj, ensure_ascii=False)
            
            formatted_blocks.append({
                "type": "text",
                "text": doc_json_str
            })
        
        return formatted_blocks
    
    def __repr__(self) -> str:
        return (
            f"RetrieverToolRunnable("
            f"name='{self.name}', "
            f"collection='{self.collection_name}', "
            f"max_results={self.max_results}"
            f")"
        )


# ============================================================================
# Factory Functions
# ============================================================================

def create_retriever_tool(
    retriever_runnable: QdrantRetrieverRunnable,
    collection_name: str,
    description: Optional[str] = None,
    max_results: int = 4
) -> RetrieverToolRunnable:
    """
    Factory function to create a RetrieverToolRunnable.
    
    Args:
        retriever_runnable: Retriever to wrap as tool
        collection_name: Name of collection
        description: Custom description
        max_results: Max number of results
    
    Returns:
        RetrieverToolRunnable instance
    
    Example:
        retriever = qdrant_node.get_runnable()
        tool = create_retriever_tool(
            retriever_runnable=retriever,
            collection_name="documentation",
            max_results=5
        )
    """
    return RetrieverToolRunnable(
        retriever_runnable=retriever_runnable,
        collection_name=collection_name,
        description=description,
        max_results=max_results
    )


def wrap_qdrant_node_as_tool(
    qdrant_node: Any,
    item_index: int = 0,
    max_results: int = 4
) -> RetrieverToolRunnable:
    """
    Convenience function to wrap a QdrantVectorStoreNode as a retriever tool.
    
    This is the recommended way to integrate Qdrant retrievers into agent workflows.
    
    Args:
        qdrant_node: QdrantVectorStoreNode instance
        item_index: Item index for parameter resolution
        max_results: Max number of results
    
    Returns:
        RetrieverToolRunnable that can be added to agent's tool collection
    
    Example:
        # In agent node:
        qdrant_node = self._get_qdrant_node()
        retriever_tool = wrap_qdrant_node_as_tool(qdrant_node, max_results=5)
        
        # Add to tools collection
        all_tools = regular_tools + [retriever_tool]
        tools_collection = ToolCollectionRunnable(all_tools)
    """
    # Get retriever runnable from node
    retriever_runnable = qdrant_node.get_runnable(item_index)
    
    # Get collection name from node parameters
    collection_name = qdrant_node.get_node_parameter("collectionName", item_index, "documents")
    
    # Create tool with dynamic parameter reading capability
    return RetrieverToolRunnable(
        retriever_runnable=retriever_runnable,
        collection_name=collection_name,
        max_results=max_results,
        qdrant_node=qdrant_node,
        item_index=item_index
    )
