"""
Abstract base class for reranker implementations.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BaseReranker(ABC):
    """
    Abstract base class for reranker implementations.
    
    Rerankers re-score a list of documents based on their relevance to a query,
    typically using more sophisticated models (cross-encoders) than initial 
    retrieval (bi-encoders).
    """
    
    def __init__(self, model: str, top_k: int = 5):
        """
        Initialize reranker.
        
        Args:
            model: Model name/identifier
            top_k: Default number of top results to return
        """
        self.model = model
        self.top_k = top_k
    
    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents based on relevance to query.
        
        Args:
            query: The search query
            documents: List of document dicts with 'pageContent' and optional 'metadata'
            top_k: Number of top results to return (overrides instance default)
            
        Returns:
            Reranked list of documents with updated relevance scores in metadata
        """
        pass
    
    def _format_documents_for_reranking(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract text content from document dicts for reranking API.
        
        Different document formats use different field names. This method
        handles common variations.
        
        Args:
            documents: List of document dicts
            
        Returns:
            List of text strings for reranking
        """
        texts = []
        for doc in documents:
            if isinstance(doc, dict):
                # Try different possible text fields
                text = (
                    doc.get("pageContent") or
                    doc.get("page_content") or
                    doc.get("text") or
                    doc.get("content") or
                    str(doc.get("payload", {}).get("text", ""))
                )
                texts.append(text)
            else:
                # Fallback: convert to string
                texts.append(str(doc))
        
        return texts
    
    def _merge_reranked_results(
        self,
        original_documents: List[Dict[str, Any]],
        reranked_indices: List[int],
        scores: List[float]
    ) -> List[Dict[str, Any]]:
        """
        Merge reranked results with original document metadata.
        
        This preserves all original document data while:
        1. Reordering based on reranker scores
        2. Adding reranker_score to metadata
        3. Preserving original retrieval_score if present
        
        Args:
            original_documents: Original document list
            reranked_indices: Indices in original list, in new order
            scores: Reranker scores for each document
            
        Returns:
            Reordered documents with enriched metadata
        """
        reranked_docs = []
        
        for idx, score in zip(reranked_indices, scores):
            doc = original_documents[idx].copy()
            
            # Ensure metadata dict exists
            if "metadata" not in doc:
                doc["metadata"] = {}
            
            # Add reranker score
            doc["metadata"]["reranker_score"] = score
            
            # Preserve original retrieval score if present
            if "score" in doc:
                doc["metadata"]["retrieval_score"] = doc["score"]
                # Update primary score to reranker score
                doc["score"] = score
            
            reranked_docs.append(doc)
        
        return reranked_docs
