"""
Qdrant Client Adapter with connection pooling and retry logic.
Synchronous adapter wrapping requests.Session for Celery compatibility.
"""
import time
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry as Urllib3Retry

from utils.qdrant_exceptions import QdrantError, ParameterError

logger = logging.getLogger(__name__)


class QdrantClientAdapter:
    """
    Synchronous Qdrant API client with connection pooling and retry logic.
    
    Features:
    - Connection pooling via requests.Session
    - Exponential backoff on transient failures (5xx, timeout)
    - Configurable timeouts
    - Structured error handling
    """
    
    # Allowed URL schemes for security
    ALLOWED_SCHEMES = {"http", "https"}
    
    # Maximum payload size (30MB)
    MAX_PAYLOAD_SIZE = 30 * 1024 * 1024
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 0.5
    ):
        """
        Initialize Qdrant client adapter.
        
        Args:
            base_url: Qdrant server URL (e.g., "http://localhost:6333")
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for transient failures
            backoff_factor: Backoff multiplier (wait = backoff_factor * (2 ** retry_count))
        
        Raises:
            ParameterError: If base_url is invalid
        """
        self.base_url = self._validate_and_clean_url(base_url)
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        
        # Initialize session with connection pooling
        self.session = self._create_session()
    
    def _validate_and_clean_url(self, url: str) -> str:
        """
        Validate URL scheme and format.
        
        Args:
            url: Base URL to validate
            
        Returns:
            Cleaned URL without trailing slash
            
        Raises:
            ParameterError: If URL is invalid or uses disallowed scheme
        """
        if not url:
            raise ParameterError("Qdrant URL is required")
        
        parsed = urlparse(url)
        
        if parsed.scheme not in self.ALLOWED_SCHEMES:
            raise ParameterError(
                f"Invalid URL scheme: {parsed.scheme}. Allowed: {self.ALLOWED_SCHEMES}",
                details={"url": url}
            )
        
        if not parsed.netloc:
            raise ParameterError(
                "Invalid URL format: missing host",
                details={"url": url}
            )
        
        return url.rstrip("/")
    
    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry strategy and connection pooling.
        
        Returns:
            Configured requests.Session
        """
        session = requests.Session()
        
        # Configure retry strategy
        # Retry on: 500, 502, 503, 504, connection errors, timeouts
        retry_strategy = Urllib3Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
            raise_on_status=False  # We handle status codes manually
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # Connection pool size
            pool_maxsize=20       # Maximum connections
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        
        if self.api_key:
            headers["api-key"] = self.api_key
        
        return headers
    
    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Qdrant API with error handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., "/collections/{name}")
            json_data: Request body as dict
            params: Query parameters
            
        Returns:
            Response data as dict
            
        Raises:
            QdrantError: On API errors or connection failures
        """
        url = f"{self.base_url}{path}"
        
        try:
            logger.debug(f"[QdrantAdapter] {method} {path}")
            
            response = self.session.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                json=json_data,
                params=params,
                timeout=self.timeout
            )
            
            # Check for HTTP errors
            if response.status_code >= 400:
                raise QdrantError(
                    f"Qdrant API error: {method} {path}",
                    details={"url": url, "method": method},
                    status_code=response.status_code,
                    response_body=response.text
                )
            
            # Parse response
            return response.json() if response.text else {}
            
        except requests.Timeout as e:
            raise QdrantError(
                f"Request timeout after {self.timeout}s",
                details={"url": url, "timeout": self.timeout}
            )
        except requests.ConnectionError as e:
            raise QdrantError(
                f"Connection error: {str(e)}",
                details={"url": url}
            )
        except requests.RequestException as e:
            raise QdrantError(
                f"Request failed: {str(e)}",
                details={"url": url}
            )
    
    def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: str = "Cosine",
        on_disk_payload: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new collection.
        
        Args:
            collection_name: Name of collection to create
            vector_size: Dimension of vectors
            distance: Distance metric (Cosine, Euclid, Dot)
            on_disk_payload: Store payload on disk
            
        Returns:
            API response
            
        Raises:
            ParameterError: If parameters are invalid
            QdrantError: If API call fails
        """
        if not collection_name:
            raise ParameterError("Collection name is required")
        
        if vector_size <= 0:
            raise ParameterError(
                "Vector size must be positive",
                details={"vector_size": vector_size}
            )
        
        payload = {
            "vectors": {
                "size": int(vector_size),
                "distance": distance
            }
        }
        
        if on_disk_payload:
            payload["on_disk_payload"] = True
        
        logger.info(f"[QdrantAdapter] Creating collection '{collection_name}' ({vector_size}D, {distance})")
        
        try:
            return self._request(
                "PUT",
                f"/collections/{collection_name}",
                json_data=payload
            )
        except QdrantError as e:
            # Treat "collection already exists" as success (idempotent operation)
            if e.status_code == 409 and "already exists" in e.response_body.lower():
                logger.info(f"[QdrantAdapter] Collection '{collection_name}' already exists, treating as success")
                return {
                    "status": {"info": "Collection already exists"},
                    "time": 0.0,
                    "result": True
                }
            # Re-raise other errors
            raise
    
    def upsert_points(
        self,
        collection_name: str,
        points: List[Dict[str, Any]],
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        Insert or update points in collection.
        
        Args:
            collection_name: Target collection
            points: List of points with id, vector, payload
            wait: Wait for operation to complete
            
        Returns:
            API response
            
        Raises:
            ParameterError: If parameters are invalid
            QdrantError: If API call fails
        """
        if not collection_name:
            raise ParameterError("Collection name is required")
        
        if not points:
            raise ParameterError("No points provided for upsert")
        
        logger.info(f"[QdrantAdapter] Upserting {len(points)} points to '{collection_name}'")
        
        return self._request(
            "PUT",
            f"/collections/{collection_name}/points",
            json_data={"points": points},
            params={"wait": "true" if wait else "false"}
        )
    
    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_obj: Optional[Dict[str, Any]] = None,
        with_payload: bool = True,
        with_vector: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Args:
            collection_name: Collection to search
            query_vector: Query vector
            limit: Maximum results to return
            score_threshold: Minimum similarity score
            filter_obj: Qdrant filter object
            with_payload: Include payload in results
            with_vector: Include vector in results
            
        Returns:
            List of search results
            
        Raises:
            ParameterError: If parameters are invalid
            QdrantError: If API call fails
        """
        if not collection_name:
            raise ParameterError("Collection name is required")
        
        if not query_vector:
            raise ParameterError("Query vector is required")
        
        payload = {
            "vector": query_vector,
            "limit": int(limit),
            "with_payload": with_payload,
            "with_vector": with_vector
        }
        
        if score_threshold is not None:
            payload["score_threshold"] = float(score_threshold)
        
        if filter_obj:
            payload["filter"] = filter_obj
        
        logger.debug(f"[QdrantAdapter] Searching '{collection_name}' (limit={limit}, threshold={score_threshold})")
        
        response = self._request(
            "POST",
            f"/collections/{collection_name}/points/search",
            json_data=payload
        )
        
        return response.get("result", [])
    
    def scroll(
        self,
        collection_name: str,
        limit: int = 100,
        offset: Optional[int] = None,
        filter_obj: Optional[Dict[str, Any]] = None,
        with_payload: bool = True,
        with_vector: bool = False
    ) -> Dict[str, Any]:
        """
        Scroll through collection points.
        
        Args:
            collection_name: Collection to scroll
            limit: Maximum results per request
            offset: Pagination offset
            filter_obj: Qdrant filter
            with_payload: Include payload
            with_vector: Include vectors
            
        Returns:
            Scroll response with points and next offset
            
        Raises:
            ParameterError: If parameters are invalid
            QdrantError: If API call fails
        """
        if not collection_name:
            raise ParameterError("Collection name is required")
        
        payload = {
            "limit": int(limit),
            "with_payload": with_payload,
            "with_vector": with_vector
        }
        
        if offset is not None:
            payload["offset"] = offset
        
        if filter_obj:
            payload["filter"] = filter_obj
        
        return self._request(
            "POST",
            f"/collections/{collection_name}/points/scroll",
            json_data=payload
        )
    
    def delete_points(
        self,
        collection_name: str,
        point_ids: Optional[List[int]] = None,
        filter_obj: Optional[Dict[str, Any]] = None,
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        Delete points from collection.
        
        Args:
            collection_name: Target collection
            point_ids: List of point IDs to delete
            filter_obj: Qdrant filter (alternative to IDs)
            wait: Wait for operation to complete
            
        Returns:
            API response
            
        Raises:
            ParameterError: If parameters are invalid
            QdrantError: If API call fails
        """
        if not collection_name:
            raise ParameterError("Collection name is required")
        
        if not point_ids and not filter_obj:
            raise ParameterError("Either point_ids or filter_obj must be provided")
        
        payload = {}
        if point_ids:
            payload["points"] = point_ids
        elif filter_obj:
            payload["filter"] = filter_obj
        
        logger.info(f"[QdrantAdapter] Deleting points from '{collection_name}'")
        
        return self._request(
            "POST",
            f"/collections/{collection_name}/points/delete",
            json_data=payload,
            params={"wait": "true" if wait else "false"}
        )
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get collection information.
        
        Args:
            collection_name: Collection name
            
        Returns:
            Collection info
            
        Raises:
            ParameterError: If collection name is missing
            QdrantError: If API call fails
        """
        if not collection_name:
            raise ParameterError("Collection name is required")
        
        response = self._request("GET", f"/collections/{collection_name}")
        return response.get("result", {})
    
    def close(self):
        """Close the session and cleanup resources."""
        if self.session:
            self.session.close()
            logger.debug("[QdrantAdapter] Session closed")
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
