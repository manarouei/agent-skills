"""
Custom exceptions for Qdrant Vector Store operations.
Provides structured error handling with detailed context.
"""
from typing import Dict, Any, Optional


class QdrantBaseException(Exception):
    """Base exception for all Qdrant-related errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize exception with message and optional details.
        
        Args:
            message: Human-readable error message
            details: Additional context (collection name, field names, etc.)
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        result = {
            "error": self.__class__.__name__,
            "message": self.message
        }
        if self.details:
            result["details"] = self.details
        return result


class ParameterError(QdrantBaseException):
    """
    Raised when node parameters are invalid or missing.
    
    Examples:
    - Missing collection name
    - Invalid limit value
    - Malformed filter JSON
    """
    pass


class EmbeddingError(QdrantBaseException):
    """
    Raised when embedding generation fails.
    
    Examples:
    - No embedding provider configured
    - OpenAI API error
    - Dimension mismatch
    """
    pass


class QdrantError(QdrantBaseException):
    """
    Raised when Qdrant API operations fail.
    
    Examples:
    - Collection not found
    - Connection timeout
    - Invalid search parameters
    """
    
    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None
    ):
        """
        Initialize with HTTP response context.
        
        Args:
            message: Error message
            details: Additional context
            status_code: HTTP status code from Qdrant API
            response_body: Raw response body (truncated if too long)
        """
        super().__init__(message, details)
        self.status_code = status_code
        self.response_body = response_body[:500] if response_body else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Include HTTP context in response."""
        result = super().to_dict()
        if self.status_code:
            result["status_code"] = self.status_code
        if self.response_body:
            result["response_body"] = self.response_body
        return result
