"""
LangChain-compatible Retriever implementations.

Wraps our existing retriever implementations (Qdrant, etc.) as LangChain Runnables,
enabling them to be composed in LCEL chains for RAG (Retrieval-Augmented Generation).
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable
import logging

from utils.langchain_base import BaseLangChainRunnable

logger = logging.getLogger(__name__)


class QdrantRetrieverRunnable(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    LangChain-compatible wrapper for Qdrant retriever.
    
    Wraps Qdrant vector store retrieval operations with LangChain Runnable interface,
    enabling document retrieval in LCEL chains for RAG patterns.
    
    Input format:
        {
            "query": str,  # search query text
            "top_k": Optional[int],  # number of results (overrides default)
            "filter": Optional[Dict],  # metadata filter conditions
            "context": Optional[Dict[str, Any]]  # additional context
        }
    
    Output format:
        {
            "documents": List[Dict],  # retrieved documents with content and metadata
            "count": int,  # number of documents returned
            "success": bool,  # retrieval status
            "query": str  # original query
        }
    
    Example:
        retriever = QdrantRetrieverRunnable(
            retriever_executor=qdrant_search_fn,
            top_k=4,
            collection_name="documents"
        )
        
        # Search for relevant documents
        result = retriever.invoke({
            "query": "What is LangChain?"
        })
        # result: {
        #     "documents": [
        #         {"page_content": "...", "metadata": {...}},
        #         ...
        #     ],
        #     "count": 4,
        #     "success": True
        # }
    """
    
    def __init__(
        self,
        retriever_executor: Callable[[Dict[str, Any]], Dict[str, Any]],
        top_k: int = 4,
        collection_name: str = "documents",
        name: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize Qdrant Retriever Runnable.
        
        Args:
            retriever_executor: Callable that executes the retrieval
            top_k: Default number of documents to retrieve
            collection_name: Name of the Qdrant collection
            name: Optional retriever name
            **kwargs: Additional config
        """
        super().__init__(name=name or f"Retriever:{collection_name}", **kwargs)
        self.retriever_executor = retriever_executor
        self.top_k = top_k
        self.collection_name = collection_name
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute document retrieval.
        
        Args:
            input: Dict with "query" and optional "top_k", "filter"
            config: Runtime config
        
        Returns:
            Dict with documents, count, and status
        """
        query = input.get("query", "")
        if not query:
            return {
                "documents": [],
                "count": 0,
                "success": False,
                "error": "No query provided",
                "query": ""
            }
        
        top_k = input.get("top_k", self.top_k)
        filter_conditions = input.get("filter", {})
        
        try:
            # Execute retrieval
            result = self._execute_retrieval(query, top_k, filter_conditions)
            
            documents = result.get("documents", [])
            
            logger.info(
                f"[QdrantRetrieverRunnable] Retrieved {len(documents)} documents "
                f"for query: '{query[:50]}...'"
            )
            
            return {
                "documents": documents,
                "count": len(documents),
                "success": True,
                "query": query
            }
        
        except Exception as e:
            logger.error(f"[QdrantRetrieverRunnable] Retrieval error: {e}")
            return {
                "documents": [],
                "count": 0,
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def _execute_retrieval(
        self,
        query: str,
        top_k: int,
        filter_conditions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the retrieval operation.
        
        Args:
            query: Search query text
            top_k: Number of results
            filter_conditions: Metadata filters
        
        Returns:
            Dict with documents and metadata
        """
        try:
            # Call the retriever executor with parameters
            retrieval_args = {
                "query": query,
                "top_k": top_k
            }
            
            if filter_conditions:
                retrieval_args["filter"] = filter_conditions
            
            result = self.retriever_executor(retrieval_args)
            
            # Ensure result has expected structure
            if not isinstance(result, dict):
                result = {"documents": result if isinstance(result, list) else []}
            
            if "documents" not in result:
                result["documents"] = []
            
            return result
        
        except Exception as e:
            logger.error(f"[QdrantRetrieverRunnable] Executor error: {e}")
            logger.error(f"[QdrantRetrieverRunnable] Executor error type: {type(e)}")
            import traceback
            logger.error(f"[QdrantRetrieverRunnable] Traceback:\n{traceback.format_exc()}")
            raise
    
    def _get_metadata(self) -> Dict[str, Any]:
        """
        Override: Provide retriever-specific metadata.
        
        Returns:
            Metadata about retriever configuration
        """
        return {
            "runnable_type": "QdrantRetrieverRunnable",
            "runnable_name": self.name,
            "collection_name": self.collection_name,
            "top_k": self.top_k
        }
    
    def with_top_k(self, top_k: int) -> "QdrantRetrieverRunnable":
        """
        Create a new retriever with different top_k value.
        
        Args:
            top_k: New number of documents to retrieve
        
        Returns:
            New QdrantRetrieverRunnable instance
        """
        return QdrantRetrieverRunnable(
            retriever_executor=self.retriever_executor,
            top_k=top_k,
            collection_name=self.collection_name,
            name=self.name,
            **self._config
        )
    
    def with_filter(self, filter_conditions: Dict[str, Any]) -> "QdrantRetrieverRunnable":
        """
        Create a new retriever with predefined filter conditions.
        
        Args:
            filter_conditions: Metadata filter conditions
        
        Returns:
            New QdrantRetrieverRunnable with filter injected
        """
        def filtered_executor(args: Dict[str, Any]) -> Dict[str, Any]:
            # Merge predefined filter with runtime filter
            runtime_filter = args.get("filter", {})
            merged_filter = {**filter_conditions, **runtime_filter}
            args["filter"] = merged_filter
            return self.retriever_executor(args)
        
        return QdrantRetrieverRunnable(
            retriever_executor=filtered_executor,
            top_k=self.top_k,
            collection_name=self.collection_name,
            name=self.name,
            **self._config
        )
    
    def __repr__(self) -> str:
        return (
            f"QdrantRetrieverRunnable("
            f"collection='{self.collection_name}', "
            f"top_k={self.top_k}"
            f")"
        )


# ============================================================================
# Factory Functions
# ============================================================================

def create_retriever(
    retriever_executor: Callable[[Dict[str, Any]], Dict[str, Any]],
    top_k: int = 4,
    collection_name: str = "documents"
) -> QdrantRetrieverRunnable:
    """
    Factory function to create a QdrantRetrieverRunnable.
    
    Args:
        retriever_executor: Callable that executes retrieval
        top_k: Number of documents to retrieve
        collection_name: Name of the collection
    
    Returns:
        QdrantRetrieverRunnable instance
    """
    return QdrantRetrieverRunnable(
        retriever_executor=retriever_executor,
        top_k=top_k,
        collection_name=collection_name
    )
