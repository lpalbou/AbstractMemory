"""
Real embedding providers for semantic search capabilities.

Provides a unified interface for generating embeddings from real providers:
AbstractCore EmbeddingManager, OpenAI, Ollama with semantic capabilities.

NO FALLBACKS - only real semantic embedding providers are supported.
"""

import logging
import hashlib
from typing import List, Optional, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class EmbeddingAdapter:
    """
    Unified embedding interface for various providers.

    IMPORTANT: The embedding provider/model must remain consistent within a storage space.
    You can change LLM providers freely, but changing embedding models requires recreating
    your vector database as different models produce incompatible vector spaces.
    """

    def __init__(self, provider: Optional[Any] = None):
        """
        Initialize embedding adapter.

        Args:
            provider: Embedding provider (AbstractCore EmbeddingManager, OpenAI client, etc.)
                     Note: This is for EMBEDDINGS only, not LLM text generation.

        Raises:
            ValueError: If no embedding provider is available
        """
        if provider is None:
            raise ValueError(
                "AbstractMemory semantic search requires a dedicated embedding provider. "
                "This is separate from your LLM provider for text generation. "
                "Please provide: AbstractCore EmbeddingManager, OpenAI client, Ollama with embeddings, etc."
            )

        self.provider = provider
        self.provider_type = self._detect_provider_type()
        self.embedding_dimension = self._get_embedding_dimension()
        self.model_info = self._get_model_info()

    def _detect_provider_type(self) -> str:
        """Detect the type of provider and its embedding capabilities."""
        # Check for AbstractCore EmbeddingManager (preferred)
        try:
            from abstractllm.embeddings import EmbeddingManager
            if isinstance(self.provider, EmbeddingManager):
                return "abstractcore_embeddings"
        except ImportError:
            pass

        # Check for AbstractCore provider with embedding support (has specific AbstractCore attributes)
        if hasattr(self.provider, 'generate_embedding') and hasattr(self.provider, 'provider_name'):
            return "abstractcore"

        # Check for OpenAI client
        if hasattr(self.provider, 'embeddings'):
            return "openai"

        # Check for provider name attribute (Ollama, MLX, etc.)
        if hasattr(self.provider, 'provider_name'):
            provider_name = getattr(self.provider, 'provider_name', '').lower()
            if 'ollama' in provider_name:
                return "ollama"
            elif 'mlx' in provider_name:
                return "mlx"

        # Check if provider has generate_embedding method (generic embedding provider)
        if hasattr(self.provider, 'generate_embedding') and callable(getattr(self.provider, 'generate_embedding')):
            return "generic_embedding_provider"

        # If we can't identify an embedding provider, raise an error
        raise ValueError(
            f"Unable to identify an embedding provider from: {type(self.provider)}. "
            "Supported providers: AbstractCore EmbeddingManager, OpenAI client, "
            "Ollama with embeddings, or any object with 'generate_embedding()' method."
        )

    def _get_embedding_dimension(self) -> int:
        """Get the embedding dimension based on provider type."""
        if self.provider_type == "abstractcore_embeddings":
            # Get dimension from a test embedding
            try:
                test_embedding = self.provider.embed("dimension_test")
                return len(test_embedding)
            except Exception as e:
                logger.error(f"Failed to get embedding dimension from AbstractCore: {e}")
                raise ValueError("Unable to determine embedding dimension from AbstractCore provider")
        elif self.provider_type == "openai":
            return 1536  # text-embedding-3-small default
        elif self.provider_type == "ollama":
            # Try to get dimension from test embedding
            try:
                test_embedding = self._generate_ollama_embedding("dimension_test")
                return len(test_embedding)
            except:
                return 1024  # Common Ollama embedding dimension
        elif self.provider_type == "generic_embedding_provider":
            # For any provider with generate_embedding method
            try:
                test_embedding = self.provider.generate_embedding("dimension_test")
                return len(test_embedding)
            except Exception as e:
                logger.error(f"Failed to determine embedding dimension from generic provider: {e}")
                raise ValueError(f"Unable to determine embedding dimension: {e}")
        else:
            # For any other provider, attempt to generate a test embedding
            try:
                test_embedding = self.generate_embedding("dimension_test")
                return len(test_embedding)
            except Exception as e:
                logger.error(f"Failed to determine embedding dimension: {e}")
                raise ValueError(f"Unable to determine embedding dimension for provider type: {self.provider_type}")

    def _get_model_info(self) -> dict:
        """Get detailed information about the embedding model for consistency tracking."""
        info = {
            "provider_type": self.provider_type,
            "dimension": self.embedding_dimension,
            "created_at": datetime.now().isoformat()
        }

        if self.provider_type == "abstractcore_embeddings":
            # Try to get model name from AbstractCore - only store serializable strings
            try:
                if hasattr(self.provider, 'model'):
                    model_attr = getattr(self.provider, 'model')
                    if isinstance(model_attr, str):
                        info["model_name"] = model_attr
                    else:
                        # Get string representation of the model
                        info["model_name"] = str(type(model_attr).__name__)
                if hasattr(self.provider, 'backend'):
                    info["backend"] = str(self.provider.backend)
            except Exception as e:
                logger.debug(f"Could not extract model info: {e}")
        elif self.provider_type == "openai":
            info["model_name"] = "text-embedding-3-small"  # Default assumption

        return info

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for the given text using the configured provider.

        Args:
            text: Input text to embed

        Returns:
            List[float]: Embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        try:
            if self.provider_type == "abstractcore_embeddings":
                return self._generate_abstractcore_embeddings(text)
            elif self.provider_type == "abstractcore":
                return self._generate_abstractcore_embedding(text)
            elif self.provider_type == "openai":
                return self._generate_openai_embedding(text)
            elif self.provider_type == "ollama":
                return self._generate_ollama_embedding(text)
            elif self.provider_type == "mlx":
                return self._generate_mlx_embedding(text)
            elif self.provider_type == "generic_embedding_provider":
                return self.provider.generate_embedding(text)
            else:
                raise EmbeddingError(f"Unknown provider type: {self.provider_type}")

        except Exception as e:
            logger.error(f"Embedding generation failed with {self.provider_type}: {e}")
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    def _generate_abstractcore_embeddings(self, text: str) -> List[float]:
        """Generate embedding using AbstractCore EmbeddingManager."""
        return self.provider.embed(text)

    def _generate_abstractcore_embedding(self, text: str) -> List[float]:
        """Generate embedding using AbstractCore provider."""
        return self.provider.generate_embedding(text)

    def _generate_openai_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI client."""
        response = self.provider.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    def _generate_ollama_embedding(self, text: str) -> List[float]:
        """Generate embedding using Ollama provider."""
        try:
            import requests
            response = requests.post(
                "http://localhost:11434/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": text
                },
                timeout=30
            )
            if response.status_code == 200:
                embedding = response.json()["embedding"]
                if embedding and isinstance(embedding, list):
                    return embedding
            raise EmbeddingError(f"Ollama API returned status {response.status_code}")
        except ImportError:
            raise EmbeddingError("requests library not available for Ollama embedding API")
        except Exception as e:
            raise EmbeddingError(f"Ollama embedding generation failed: {e}") from e

    def _generate_mlx_embedding(self, text: str) -> List[float]:
        """Generate embedding using MLX provider."""
        # MLX provider should implement actual MLX embedding model
        raise EmbeddingError(
            "MLX embedding implementation not yet available. "
            "Please use AbstractCore EmbeddingManager or another provider."
        )

    def is_real_embedding(self) -> bool:
        """Check if this adapter provides real semantic embeddings."""
        return self.provider_type in ["abstractcore_embeddings", "abstractcore", "openai", "ollama", "generic_embedding_provider"]

    def get_embedding_info(self) -> dict:
        """Get comprehensive information about the embedding provider for consistency tracking."""
        info = self.model_info.copy()
        info.update({
            "is_real_embedding": self.is_real_embedding(),
            "provider_available": self.provider is not None
        })
        return info

    def check_consistency_with(self, other_model_info: dict) -> bool:
        """
        Check if this adapter is consistent with previously stored model info.

        Args:
            other_model_info: Previously stored model information

        Returns:
            bool: True if models are compatible for semantic search
        """
        current_info = self.get_embedding_info()

        # Check critical compatibility factors
        if current_info.get("provider_type") != other_model_info.get("provider_type"):
            logger.warning(f"Provider type mismatch: {current_info.get('provider_type')} vs {other_model_info.get('provider_type')}")
            return False

        if current_info.get("dimension") != other_model_info.get("dimension"):
            logger.warning(f"Dimension mismatch: {current_info.get('dimension')} vs {other_model_info.get('dimension')}")
            return False

        if current_info.get("model_name") != other_model_info.get("model_name"):
            logger.warning(f"Model name mismatch: {current_info.get('model_name')} vs {other_model_info.get('model_name')}")
            return False

        return True

    def warn_about_consistency(self, stored_model_info: dict) -> None:
        """
        Issue warnings about embedding model consistency issues.

        Args:
            stored_model_info: Information about previously stored embeddings
        """
        if not self.check_consistency_with(stored_model_info):
            current_info = self.get_embedding_info()
            logger.warning(
                "\n" + "="*80 + "\n"
                "🚨 CRITICAL: EMBEDDING MODEL INCONSISTENCY DETECTED 🚨\n"
                "="*80 + "\n"
                "You are attempting to use a different embedding model than what was\n"
                "previously used in this storage space. This BREAKS semantic search!\n\n"
                f"CURRENT embedding model:\n"
                f"  • Provider: {current_info.get('provider_type', 'Unknown')}\n"
                f"  • Model: {current_info.get('model_name', 'Unknown')}\n"
                f"  • Dimensions: {current_info.get('dimension', 'Unknown')}\n\n"
                f"STORED embedding model:\n"
                f"  • Provider: {stored_model_info.get('provider_type', 'Unknown')}\n"
                f"  • Model: {stored_model_info.get('model_name', 'Unknown')}\n"
                f"  • Dimensions: {stored_model_info.get('dimension', 'Unknown')}\n\n"
                "IMPORTANT: You can change LLM providers freely (Anthropic ↔ OpenAI ↔ Ollama)\n"
                "but embedding models must remain consistent within a storage space.\n\n"
                "TO FIX THIS ISSUE:\n"
                "1. Use the SAME embedding model as stored, OR\n"
                "2. Delete your vector database and start fresh with the new model\n"
                "   (this will re-embed all interactions with the new model)\n"
                "="*80
            )


class EmbeddingError(Exception):
    """Base exception for embedding-related errors."""
    pass


def create_embedding_adapter(provider: Optional[Any] = None) -> EmbeddingAdapter:
    """
    Create an embedding adapter for the given provider.

    Args:
        provider: LLM provider instance

    Returns:
        EmbeddingAdapter: Configured adapter
    """
    return EmbeddingAdapter(provider)