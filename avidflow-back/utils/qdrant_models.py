"""
Pydantic parameter models for Qdrant operations.
Provides validation and type safety for node parameters.
"""
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import json


class SearchParams(BaseModel):
    """
    Parameters for vector search operation.
    NOTE: UI parameter is 'topK' but this fixes the naming to be consistent.
    """
    
    collection_name: str = Field(..., description="Name of the collection to search")
    top_k: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum number of results to return (UI: topK)"
    )
    score_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold"
    )
    filter: Optional[str] = Field(
        default=None,
        description="Qdrant filter as JSON string"
    )
    
    # Parsed filter object (set by validator)
    filter_obj: Optional[Dict[str, Any]] = None
    
    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, v):
        """Validate collection name is not empty."""
        if not v or not v.strip():
            raise ValueError("Collection name cannot be empty")
        return v.strip()
    
    @field_validator("filter")
    @classmethod
    def parse_filter(cls, v):
        """Parse filter JSON string to dict."""
        if v is None or not v.strip():
            return None
        
        try:
            # Parse JSON string
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("Filter must be a JSON object")
            return v  # Return original string (we'll use filter_obj)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid filter JSON: {str(e)}")
    
    @model_validator(mode='after')
    def set_filter_obj(self):
        """Set filter_obj from parsed filter string."""
        if self.filter:
            try:
                self.filter_obj = json.loads(self.filter)
            except json.JSONDecodeError:
                pass  # Already validated above
        return self
    
    class Config:
        extra = "forbid"  # Reject unknown fields


class InsertParams(BaseModel):
    """
    Parameters for inserting documents into collection.
    """
    
    collection_name: str = Field(..., description="Name of the collection")
    text_field: str = Field(
        default="text",
        description="Field name containing text to embed"
    )
    metadata_fields: Optional[List[str]] = Field(
        default=None,
        description="Additional fields to store as metadata"
    )
    wait: bool = Field(
        default=True,
        description="Wait for operation to complete"
    )
    
    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, v):
        """Validate collection name."""
        if not v or not v.strip():
            raise ValueError("Collection name cannot be empty")
        return v.strip()
    
    @field_validator("text_field")
    @classmethod
    def validate_text_field(cls, v):
        """Validate text field name."""
        if not v or not v.strip():
            raise ValueError("Text field name cannot be empty")
        return v.strip()
    
    class Config:
        extra = "forbid"


class CollectionParams(BaseModel):
    """
    Parameters for collection operations (create, info, etc.)
    """
    
    collection_name: str = Field(..., description="Name of the collection")
    distance: Literal["Cosine", "Euclid", "Dot"] = Field(
        default="Cosine",
        description="Distance metric for similarity"
    )
    on_disk_payload: bool = Field(
        default=False,
        description="Store payload on disk (for large collections)"
    )
    
    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, v):
        """Validate collection name."""
        if not v or not v.strip():
            raise ValueError("Collection name cannot be empty")
        return v.strip()
    
    class Config:
        extra = "forbid"


class DeleteParams(BaseModel):
    """
    Parameters for deleting points from collection.
    """
    
    collection_name: str = Field(..., description="Name of the collection")
    point_ids: Optional[str] = Field(
        default=None,
        description="Comma-separated point IDs to delete"
    )
    filter: Optional[str] = Field(
        default=None,
        description="Qdrant filter as JSON string"
    )
    wait: bool = Field(
        default=True,
        description="Wait for operation to complete"
    )
    
    # Parsed values
    point_ids_list: Optional[List[int]] = None
    filter_obj: Optional[Dict[str, Any]] = None
    
    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, v):
        """Validate collection name."""
        if not v or not v.strip():
            raise ValueError("Collection name cannot be empty")
        return v.strip()
    
    @field_validator("point_ids")
    @classmethod
    def parse_point_ids(cls, v):
        """Parse comma-separated point IDs."""
        if v is None or not v.strip():
            return None
        
        try:
            # Parse comma-separated integers
            ids = [int(x.strip()) for x in v.split(",") if x.strip()]
            if not ids:
                return None
            return v  # Return original string
        except ValueError as e:
            raise ValueError(f"Invalid point IDs (must be integers): {str(e)}")
    
    @field_validator("filter")
    @classmethod
    def parse_filter(cls, v):
        """Parse filter JSON string."""
        if v is None or not v.strip():
            return None
        
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("Filter must be a JSON object")
            return v
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid filter JSON: {str(e)}")
    
    @model_validator(mode='after')
    def validate_deletion_criteria(self):
        """Ensure at least one deletion criterion is provided."""
        if not self.point_ids and not self.filter:
            raise ValueError("Must provide either point_ids or filter for deletion")
        
        # Set parsed values
        if self.point_ids:
            self.point_ids_list = [
                int(x.strip()) for x in self.point_ids.split(",") if x.strip()
            ]
        
        if self.filter:
            try:
                self.filter_obj = json.loads(self.filter)
            except json.JSONDecodeError:
                pass  # Already validated
        
        return self
    
    class Config:
        extra = "forbid"


class EmbeddingProviderConfig(BaseModel):
    """
    Configuration for embedding provider.
    """
    
    provider_type: str = Field(..., description="Provider type (e.g., 'openai')")
    api_key: str = Field(..., description="API key for provider")
    model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model name"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Custom API base URL"
    )
    dimensions: Optional[int] = Field(
        default=None,
        ge=1,
        le=4096,
        description="Custom embedding dimensions"
    )
    organization: Optional[str] = Field(
        default=None,
        description="Organization ID (OpenAI)"
    )
    timeout: int = Field(
        default=60,
        ge=1,
        le=300,
        description="Request timeout in seconds"
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Batch size for embedding generation"
    )
    
    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, v):
        """Validate provider type."""
        if not v or not v.strip():
            raise ValueError("Provider type is required")
        return v.strip().lower()
    
    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v):
        """Validate API key."""
        if not v or not v.strip():
            raise ValueError("API key is required")
        return v.strip()
    
    @field_validator("model")
    @classmethod
    def validate_model(cls, v):
        """Validate model name."""
        if not v or not v.strip():
            raise ValueError("Model name is required")
        return v.strip()
    
    class Config:
        extra = "forbid"


class QdrantConnectionConfig(BaseModel):
    """
    Configuration for Qdrant connection.
    """
    
    url: str = Field(..., description="Qdrant server URL")
    api_key: Optional[str] = Field(
        default=None,
        description="Qdrant API key (optional for local)"
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts"
    )
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        """Validate URL format."""
        if not v or not v.strip():
            raise ValueError("Qdrant URL is required")
        
        # Basic URL validation
        from urllib.parse import urlparse
        parsed = urlparse(v.strip())
        
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
        
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("URL scheme must be http or https")
        
        return v.strip()
    
    class Config:
        extra = "forbid"
