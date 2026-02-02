"""
Retriever abstraction layer composing Qdrant client and embedding provider.
Handles high-level search/insert/delete operations for RAG workflows.
"""
import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime

from utils.qdrant_client import QdrantClientAdapter
from utils.embedding_providers import BaseEmbeddingProvider
from utils.qdrant_exceptions import ParameterError, QdrantError, EmbeddingError

logger = logging.getLogger(__name__)


class Retriever:
    """
    High-level retriever for RAG operations.
    Composes QdrantClientAdapter + BaseEmbeddingProvider.
    """
    
    def __init__(
        self,
        qdrant_adapter: QdrantClientAdapter,
        embedding_provider: BaseEmbeddingProvider
    ):
        """
        Initialize retriever.
        
        Args:
            qdrant_adapter: Qdrant client adapter
            embedding_provider: Embedding provider
        """
        self.adapter = qdrant_adapter
        self.provider = embedding_provider
    
    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 10,
        score_threshold: float = 0.0,
        filter_obj: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for documents similar to query.
        
        Args:
            collection_name: Collection to search
            query: Query text
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            filter_obj: Qdrant filter
            include_metadata: Include document metadata
            
        Returns:
            List of search results with scores and payloads
            
        Raises:
            ParameterError: If parameters are invalid
            EmbeddingError: If embedding generation fails
            QdrantError: If search fails
        """
        if not query or not query.strip():
            raise ParameterError("Query text is required")
        
        logger.info(f"[Retriever] Searching '{collection_name}' for query (top_k={top_k})")
        
        # Generate query embedding
        try:
            query_embeddings = self.provider.generate_embeddings([query])
            query_vector = query_embeddings[0]
        except Exception as e:
            raise EmbeddingError(
                f"Failed to generate query embedding: {str(e)}",
                details={"query_length": len(query)}
            )
        
        # Search Qdrant
        results = self.adapter.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            filter_obj=filter_obj,
            with_payload=True,
            with_vector=False  # Don't return vectors to save bandwidth
        )
        
        logger.info(f"[Retriever] Found {len(results)} results")
        
        # CRITICAL DEBUG: Log the actual articles retrieved
        for i, result in enumerate(results[:5]):  # Log first 5
            if isinstance(result, dict):
                # Qdrant returns: {'id': ..., 'score': ..., 'payload': {...}}
                payload = result.get("payload", {})
                metadata = payload.get("metadata", {})
                page_content = payload.get("content", payload.get("page_content", ""))
                score = result.get("score", 0)
            else:
                metadata = getattr(result, "metadata", {}) or {}
                page_content = getattr(result, "page_content", "")
                score = getattr(result, "score", 0)
            
        return results
    
    def search_as_tool_output(
        self,
        collection_name: str,
        query_data: Dict[str, Any],
        top_k: int = 10,
        score_threshold: float = 0.0
    ) -> Dict[str, Any]:
        """
        Search and format results for n8n ai_tool connection.
        
        Args:
            collection_name: Collection to search
            query_data: Query data dict (expects 'query' or 'user_query' key)
            top_k: Number of results
            score_threshold: Minimum score
            
        Returns:
            Dict with 'response' key containing formatted results
            
        Raises:
            ParameterError: If query is missing
        """
        # Extract query using QueryExtractor pattern
        query = self._extract_query_from_data(query_data)
        
        if not query:
            raise ParameterError(
                "No query found in input data",
                details={"keys": list(query_data.keys())}
            )
        
        # Perform search
        results = self.search(
            collection_name=collection_name,
            query=query,
            top_k=top_k,
            score_threshold=score_threshold
        )
        
        # Format for ai_tool output
        formatted_results = self._format_results_for_tool(results)
        
        return {
            "response": formatted_results,
            "metadata": {
                "collection": collection_name,
                "query": query,
                "results_count": len(results),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    
    def insert_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        text_field: str = "text",
        metadata_fields: Optional[List[str]] = None,
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        Insert documents into collection with embeddings.
        
        Args:
            collection_name: Target collection
            documents: List of documents (must have text_field key)
            text_field: Key containing text to embed
            metadata_fields: Additional fields to store as payload
            wait: Wait for operation to complete
            
        Returns:
            Insert operation result
            
        Raises:
            ParameterError: If documents are invalid
            EmbeddingError: If embedding generation fails
            QdrantError: If insertion fails
        """
        if not documents:
            raise ParameterError("No documents provided for insertion")
        
        logger.info(f"[Retriever] Inserting {len(documents)} documents into '{collection_name}'")
        
        # Extract texts
        texts = []
        for doc in documents:
            if text_field not in doc:
                raise ParameterError(
                    f"Document missing required field: {text_field}",
                    details={"document_keys": list(doc.keys())}
                )
            texts.append(str(doc[text_field]))
        
        # Generate embeddings
        try:
            embeddings = self.provider.generate_embeddings(texts)
        except Exception as e:
            raise EmbeddingError(
                f"Failed to generate embeddings for {len(texts)} documents: {str(e)}",
                details={"document_count": len(texts)}
            )
        
        # Prepare points
        points = []
        for idx, (doc, embedding) in enumerate(zip(documents, embeddings)):
            # Generate point ID from content hash
            point_id = self._generate_point_id(texts[idx])
            
            # Build payload
            payload = {text_field: texts[idx]}
            
            # Add metadata fields
            if metadata_fields:
                for field in metadata_fields:
                    if field in doc:
                        payload[field] = doc[field]
            else:
                # Include all fields except text_field
                for key, value in doc.items():
                    if key != text_field:
                        payload[key] = value
            
            points.append({
                "id": point_id,
                "vector": embedding,
                "payload": payload
            })
        
        # Upsert to Qdrant
        result = self.adapter.upsert_points(
            collection_name=collection_name,
            points=points,
            wait=wait
        )
        
        logger.info(f"[Retriever] Inserted {len(points)} points")
        
        return {
            "status": "success",
            "collection": collection_name,
            "documents_inserted": len(points),
            "result": result
        }
    
    def delete_documents(
        self,
        collection_name: str,
        point_ids: Optional[List[int]] = None,
        filter_obj: Optional[Dict[str, Any]] = None,
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        Delete documents from collection.
        
        Args:
            collection_name: Target collection
            point_ids: List of point IDs to delete
            filter_obj: Qdrant filter (alternative to IDs)
            wait: Wait for operation to complete
            
        Returns:
            Delete operation result
            
        Raises:
            ParameterError: If neither IDs nor filter provided
            QdrantError: If deletion fails
        """
        logger.info(f"[Retriever] Deleting points from '{collection_name}'")
        
        result = self.adapter.delete_points(
            collection_name=collection_name,
            point_ids=point_ids,
            filter_obj=filter_obj,
            wait=wait
        )
        
        return {
            "status": "success",
            "collection": collection_name,
            "result": result
        }
    
    def create_collection(
        self,
        collection_name: str,
        distance: str = "Cosine",
        on_disk_payload: bool = False
    ) -> Dict[str, Any]:
        """
        Create collection with correct vector size from provider.
        
        Args:
            collection_name: Name of collection
            distance: Distance metric
            on_disk_payload: Store payload on disk
            
        Returns:
            Collection creation result
            
        Raises:
            ParameterError: If parameters are invalid
            QdrantError: If creation fails
        """
        vector_size = self.provider.get_vector_size()
        
        logger.info(f"[Retriever] Creating collection '{collection_name}' ({vector_size}D)")
        
        result = self.adapter.create_collection(
            collection_name=collection_name,
            vector_size=vector_size,
            distance=distance,
            on_disk_payload=on_disk_payload
        )
        
        return {
            "status": "success",
            "collection": collection_name,
            "vector_size": vector_size,
            "distance": distance,
            "result": result
        }
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get collection information.
        
        Args:
            collection_name: Collection name
            
        Returns:
            Collection info
        """
        return self.adapter.get_collection_info(collection_name)
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def _extract_query_from_data(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Extract query text from input data.
        Uses the simplified QueryExtractor pattern (3 fields only).
        
        Args:
            data: Input data dict
            
        Returns:
            Query string or None
        """
        # Check priority fields (matching utils/qdrant_helpers.py)
        for key in ["query", "user_query", "chatInput"]:
            if key in data:
                value = data[key]
                if isinstance(value, str) and value.strip():
                    return value.strip()
        
        return None
    
    def _format_results_for_tool(self, results: List[Dict[str, Any]]) -> str:
        """
        Format search results for ai_tool output.
        
        Args:
            results: Raw Qdrant search results
            
        Returns:
            Formatted string
        """
        if not results:
            return "No relevant documents found."
        
        formatted_parts = []
        
        for idx, result in enumerate(results, 1):
            score = result.get("score", 0.0)
            payload = result.get("payload", {})
            
            # Get text content (try common field names)
            text = (
                payload.get("text") or
                payload.get("content") or
                payload.get("pageContent") or
                str(payload)
            )
            
            # Get metadata
            metadata = payload.get("metadata", {})
            
            # Format result
            part = f"[{idx}] (Score: {score:.4f})\n{text}"
            
            if metadata:
                part += f"\nMetadata: {metadata}"
            
            formatted_parts.append(part)
        
        return "\n\n".join(formatted_parts)
    
    def _generate_point_id(self, text: str) -> int:
        """
        Generate deterministic point ID from text content.
        Uses hash to ensure same text gets same ID (enables upsert semantics).
        
        Args:
            text: Text content
            
        Returns:
            Integer point ID
        """
        # Generate SHA256 hash and convert to int
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        # Use first 8 bytes as int (64-bit)
        point_id = int.from_bytes(hash_bytes[:8], byteorder="big")
        return point_id
