"""
Embedding provider interface and factory.
Delegates to existing embedding nodes to avoid logic duplication.
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import requests

from utils.qdrant_exceptions import EmbeddingError, ParameterError

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    All providers must implement generate_embeddings().
    """
    
    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (each vector is List[float])
            
        Raises:
            EmbeddingError: If embedding generation fails
        """
        pass
    
    @abstractmethod
    def get_vector_size(self) -> int:
        """
        Get the dimension of embeddings produced by this provider.
        
        Returns:
            Embedding dimension
        """
        pass


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    OpenAI embedding provider using logic from embeddings_openai.py.
    Avoids duplication by reusing the same API call pattern.
    """
    
    # Model dimensions (from embeddings_openai.py)
    MODEL_DIMENSIONS = {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072
    }
    
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        dimensions: Optional[int] = None,
        organization: Optional[str] = None,
        timeout: int = 60,
        batch_size: int = 100
    ):
        """
        Initialize OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key
            model: Embedding model name
            base_url: API base URL
            dimensions: Custom dimensions (optional)
            organization: Organization ID (optional)
            timeout: Request timeout in seconds
            batch_size: Maximum texts per API call
            
        Raises:
            ParameterError: If required parameters are missing or invalid
        """
        if not api_key:
            raise ParameterError("OpenAI API key is required")
        
        if not model:
            raise ParameterError("OpenAI model is required")
        
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.dimensions = dimensions
        self.organization = organization
        self.timeout = timeout
        self.batch_size = batch_size
        
        # Determine vector size
        if dimensions:
            self.vector_size = dimensions
        else:
            self.vector_size = self.MODEL_DIMENSIONS.get(model, 1536)  # Default to 1536
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using OpenAI API.
        Uses the same logic as EmbeddingsOpenAINode._generate_embeddings_sync().
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
            
        Raises:
            EmbeddingError: If API call fails
        """
        if not texts:
            raise EmbeddingError("No texts provided for embedding generation")
        
        # Process in batches if needed
        if len(texts) > self.batch_size:
            all_embeddings = []
            
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                batch_embeddings = self._generate_embeddings_batch(batch)
                all_embeddings.extend(batch_embeddings)
            
            return all_embeddings
        else:
            return self._generate_embeddings_batch(texts)
    
    def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a single batch.
        Implements the same logic as embeddings_openai.py.
        
        Args:
            texts: Batch of texts
            
        Returns:
            List of embedding vectors
            
        Raises:
            EmbeddingError: If API call fails
        """
        url = f"{self.base_url}/embeddings"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        
        payload = {
            "input": texts,
            "model": self.model
        }
        
        if self.dimensions:
            payload["dimensions"] = self.dimensions
        
        try:
            logger.debug(f"[OpenAIProvider] Calling OpenAI API for {len(texts)} texts")
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                error_text = response.text
                raise EmbeddingError(
                    f"OpenAI API error ({response.status_code})",
                    details={
                        "status_code": response.status_code,
                        "response": error_text,
                        "model": self.model,
                        "batch_size": len(texts)
                    }
                )
            
            data = response.json()
            
            # Extract embeddings from response
            embeddings = []
            for item in data.get("data", []):
                embedding = item.get("embedding", [])
                if not embedding:
                    raise EmbeddingError(
                        "Empty embedding returned from OpenAI",
                        details={"item": item}
                    )
                embeddings.append(embedding)
            
            if len(embeddings) != len(texts):
                raise EmbeddingError(
                    f"Expected {len(texts)} embeddings, got {len(embeddings)}",
                    details={"expected": len(texts), "actual": len(embeddings)}
                )
            
            logger.debug(f"[OpenAIProvider] Successfully generated {len(embeddings)} embeddings")
            return embeddings
            
        except requests.exceptions.Timeout:
            raise EmbeddingError(
                f"OpenAI API timeout after {self.timeout}s",
                details={"timeout": self.timeout, "batch_size": len(texts)}
            )
        except requests.exceptions.ConnectionError as e:
            raise EmbeddingError(
                f"Connection error: {str(e)}",
                details={"url": url}
            )
        except requests.exceptions.RequestException as e:
            raise EmbeddingError(
                f"Request failed: {str(e)}",
                details={"url": url, "batch_size": len(texts)}
            )
        except EmbeddingError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise EmbeddingError(
                f"Unexpected error generating embeddings: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    def get_vector_size(self) -> int:
        """Get embedding dimension."""
        return self.vector_size


class EmbeddingProviderFactory:
    """
    Factory for creating embedding providers based on type.
    Supports multiple providers (OpenAI, future: Cohere, HuggingFace, etc.)
    """
    
    SUPPORTED_PROVIDERS = {"openai"}
    
    @staticmethod
    def create(provider_type: str, config: Dict[str, Any]) -> BaseEmbeddingProvider:
        """
        Create an embedding provider instance.
        
        Args:
            provider_type: Provider type (e.g., "openai", "cohere")
            config: Provider configuration dict
            
        Returns:
            Configured embedding provider
            
        Raises:
            ParameterError: If provider type is unsupported or config is invalid
        """
        provider_type = provider_type.lower().strip()
        
        if provider_type not in EmbeddingProviderFactory.SUPPORTED_PROVIDERS:
            raise ParameterError(
                f"Unsupported embedding provider: {provider_type}",
                details={
                    "provider": provider_type,
                    "supported": list(EmbeddingProviderFactory.SUPPORTED_PROVIDERS)
                }
            )
        
        if provider_type == "openai":
            return EmbeddingProviderFactory._create_openai_provider(config)
        
        # Future providers:
        # elif provider_type == "cohere":
        #     return EmbeddingProviderFactory._create_cohere_provider(config)
        # elif provider_type == "huggingface":
        #     return EmbeddingProviderFactory._create_huggingface_provider(config)
        
        raise ParameterError(f"Provider {provider_type} not implemented yet")
    
    @staticmethod
    def _create_openai_provider(config: Dict[str, Any]) -> OpenAIEmbeddingProvider:
        """
        Create OpenAI provider from config.
        
        Args:
            config: Provider configuration
            
        Returns:
            OpenAIEmbeddingProvider instance
            
        Raises:
            ParameterError: If required config is missing
        """
        # Extract OpenAI-specific config
        api_key = config.get("api_key") or config.get("apiKey")
        if not api_key:
            raise ParameterError("OpenAI API key is required in provider config")
        
        model = config.get("model", "text-embedding-3-small")
        base_url = config.get("base_url") or config.get("baseUrl", "https://api.openai.com/v1")
        dimensions = config.get("dimensions")
        organization = config.get("organization")
        timeout = config.get("timeout", 60)
        batch_size = config.get("batch_size") or config.get("batchSize", 100)
        
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            dimensions=dimensions,
            organization=organization,
            timeout=timeout,
            batch_size=batch_size
        )
    
    # Future provider factory methods:
    
    # @staticmethod
    # def _create_cohere_provider(config: Dict[str, Any]) -> CohereEmbeddingProvider:
    #     """Create Cohere provider from config."""
    #     pass
    
    # @staticmethod
    # def _create_huggingface_provider(config: Dict[str, Any]) -> HuggingFaceEmbeddingProvider:
    #     """Create HuggingFace provider from config."""
    #     pass
