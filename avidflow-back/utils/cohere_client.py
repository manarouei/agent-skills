"""
LangChain-based Cohere reranker using native BaseDocumentCompressor.

Uses LangChain's CohereRerank directly, which extends BaseDocumentCompressor.
This is a thin adapter that handles document format conversion between our
internal format and LangChain's Document format.
"""
from typing import List, Dict, Any, Optional
import logging
from langchain_cohere import CohereRerank
from langchain_core.documents import Document
from langchain.retrievers.document_compressors.base import BaseDocumentCompressor

logger = logging.getLogger(__name__)

class CohereReranker:
    """
    Cohere reranker using LangChain's native CohereRerank (BaseDocumentCompressor).
    
    This is a simple adapter that:
    1. Wraps LangChain's CohereRerank (which extends BaseDocumentCompressor)
    2. Converts our internal document format to/from LangChain Documents
    3. Provides a consistent interface for the platform
    
    Design Note:
    - We use LangChain's CohereRerank directly instead of extending BaseDocumentCompressor
    - This allows us to add platform-specific document format handling without
      modifying the LangChain implementation
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "rerank-multilingual-v3.0",
        top_k: int = 5,
        timeout: int = 30
    ):
        self.api_key = api_key
        self.model = model
        self.top_k = top_k
        self.timeout = timeout
        
        # Initialize LangChain's CohereRerank (extends BaseDocumentCompressor)
        self._reranker: BaseDocumentCompressor = CohereRerank(
            cohere_api_key=api_key,
            model=model,
            top_n=top_k,
            # Optional: add client_name for tracking
            client_name="n8n-platform"
        )
        
        logger.info(
            f"[CohereReranker] Initialized LangChain CohereRerank "
            f"(model={model}, top_k={top_k})"
        )
    
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents using LangChain's CohereRerank.compress_documents().
        
        This method wraps LangChain's BaseDocumentCompressor.compress_documents()
        which is the standard interface for all LangChain rerankers.
        
        Args:
            query: The search query
            documents: List of documents with 'pageContent' and optional 'metadata'
            top_k: Number of top results (defaults to instance top_k)
            
        Returns:
            Reranked documents with updated relevance scores in metadata
        """
        if not documents:
            return []
        
        k = top_k if top_k is not None else self.top_k
        
        logger.info(
            f"[CohereReranker] Reranking {len(documents)} documents "
            f"with model {self.model}, returning top {k}"
        )
        
        try:
            # Convert to LangChain Document format
            lc_documents = self._to_langchain_documents(documents)
            
            # Update top_n if different from default
            if k != self.top_k:
                self._reranker.top_n = k
            
            # Call LangChain's BaseDocumentCompressor.compress_documents()
            # This is the standard LangChain reranking interface
            reranked = self._reranker.compress_documents(
                documents=lc_documents,
                query=query
            )
            
            logger.info(
                f"[CohereReranker] Reranked to {len(reranked)} documents"
            )
            
            # Convert back to our format
            results = self._from_langchain_documents(reranked)
            
            # Log top score if available
            if results and "metadata" in results[0]:
                top_score = results[0].get("metadata", {}).get("relevance_score")
                if top_score is not None:
                    logger.info(f"[CohereReranker] Top score: {top_score:.3f}")
            
            return results
            
        except Exception as e:
            logger.error(f"[CohereReranker] Reranking failed: {e}")
            # Fallback: return original order truncated to top_k
            return documents[:k]
    
    def _to_langchain_documents(self, documents: List[Dict[str, Any]]) -> List[Document]:
        """
        Convert our document format to LangChain Documents.
        
        Handles various pageContent formats (string, dict, etc.)
        """
        lc_docs = []
        for doc in documents:
            page_content = doc.get("pageContent", "")
            
            # Handle nested/dict content
            if isinstance(page_content, dict):
                page_content = str(page_content)
            elif not isinstance(page_content, str):
                page_content = str(page_content)
            
            metadata = doc.get("metadata", {})
            
            lc_docs.append(
                Document(page_content=page_content, metadata=metadata)
            )
        
        return lc_docs
    
    def _from_langchain_documents(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """
        Convert LangChain Documents back to our format.
        
        Preserves metadata including relevance_score added by CohereRerank.
        """
        results = []
        for doc in documents:
            result = {
                "pageContent": doc.page_content,
                "metadata": doc.metadata
            }
            
            # Extract relevance_score if present (set by CohereRerank)
            if "relevance_score" in doc.metadata:
                result["score"] = doc.metadata["relevance_score"]
            
            results.append(result)
        
        return results
