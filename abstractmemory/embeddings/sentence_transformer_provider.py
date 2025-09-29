"""
SentenceTransformer-based embedding provider for testing different models.
Supports BAAI/bge-base-en-v1.5, all-MiniLM-L6-v2, and other sentence-transformers models.
"""

import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class SentenceTransformerProvider:
    """
    A provider for SentenceTransformer models that can be used with the EmbeddingAdapter.
    Supports various models including BAAI/bge-base-en-v1.5 and all-MiniLM-L6-v2.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", device: Optional[str] = None):
        """
        Initialize the SentenceTransformer provider.

        Args:
            model_name: Name of the sentence-transformers model to use
            device: Device to run the model on ('cpu', 'cuda', or None for auto)
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.provider_name = f"sentence_transformers_{model_name.replace('/', '_').replace('-', '_')}"

        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer model: {model_name}")

            # Check if we're in offline mode
            import os
            offline_mode = (
                os.environ.get('TRANSFORMERS_OFFLINE') == '1' or
                os.environ.get('HF_HUB_OFFLINE') == '1'
            )

            if offline_mode:
                logger.info("Offline mode detected - using local files only")
                # Try to load with local_files_only flag
                try:
                    # First try to find the cached model path
                    cache_base = os.path.expanduser('~/.cache/huggingface/hub')
                    model_folder = f"models--{model_name.replace('/', '--')}"
                    model_cache_path = os.path.join(cache_base, model_folder)

                    if os.path.exists(model_cache_path):
                        snapshots_path = os.path.join(model_cache_path, 'snapshots')
                        if os.path.exists(snapshots_path):
                            # Get the latest snapshot
                            snapshots = [d for d in os.listdir(snapshots_path) if os.path.isdir(os.path.join(snapshots_path, d))]
                            if snapshots:
                                # Use the first (usually only) snapshot
                                snapshot_path = os.path.join(snapshots_path, snapshots[0])
                                logger.info(f"Found cached model at: {snapshot_path}")
                                # Load from the local snapshot path directly
                                self.model = SentenceTransformer(snapshot_path, device=device)
                            else:
                                raise RuntimeError(f"No snapshots found in {snapshots_path}")
                        else:
                            raise RuntimeError(f"No snapshots directory in {model_cache_path}")
                    else:
                        raise RuntimeError(f"Model not found in cache: {model_cache_path}")

                except Exception as e:
                    logger.warning(f"Failed to load model in offline mode: {e}")
                    # Re-raise with clearer error message
                    raise RuntimeError(
                        f"Cannot load embedding model '{model_name}' in offline mode. "
                        f"Model may not be cached. Run with internet connection once to cache the model, "
                        f"or disable semantic features. Error: {e}"
                    )
            else:
                self.model = SentenceTransformer(model_name, device=device)

            logger.info(f"Successfully loaded model: {model_name}")
        except ImportError:
            raise ImportError(
                "sentence-transformers library is required. Install with: "
                "pip install sentence-transformers"
            )
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for the given text.

        Args:
            text: Input text to embed

        Returns:
            List[float]: Embedding vector
        """
        if not self.model:
            raise RuntimeError("Model not initialized")

        try:
            # Generate embedding and convert to list
            embedding = self.model.encode([text], normalize_embeddings=True)[0]
            if isinstance(embedding, np.ndarray):
                return embedding.tolist()
            return list(embedding)
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts (more efficient).

        Args:
            texts: List of input texts to embed

        Returns:
            List[List[float]]: List of embedding vectors
        """
        if not self.model:
            raise RuntimeError("Model not initialized")

        try:
            # Generate embeddings and convert to list of lists
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            if isinstance(embeddings, np.ndarray):
                return embeddings.tolist()
            return [list(emb) for emb in embeddings]
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension of the model."""
        if not self.model:
            raise RuntimeError("Model not initialized")
        return self.model.get_sentence_embedding_dimension()

    def get_model_info(self) -> dict:
        """Get information about the model."""
        return {
            "model_name": self.model_name,
            "provider": "sentence_transformers",
            "dimension": self.get_embedding_dimension() if self.model else None,
            "device": str(self.device) if self.device else "auto",
            "provider_name": self.provider_name
        }


# Common model configurations
MODEL_CONFIGS = {
    "bge-base-en-v1.5": {
        "model_name": "BAAI/bge-base-en-v1.5",
        "dimension": 768,
        "description": "BAAI BGE Base English v1.5 - High performance retrieval model",
        "max_sequence_length": 512,
        "parameters": "109M"
    },
    "all-MiniLM-L6-v2": {
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "dimension": 384,
        "description": "All MiniLM L6 v2 - Fast and efficient sentence transformer",
        "max_sequence_length": 256,
        "parameters": "22M"
    },
    "all-mpnet-base-v2": {
        "model_name": "sentence-transformers/all-mpnet-base-v2",
        "dimension": 768,
        "description": "All MPNet Base v2 - High quality general purpose model",
        "max_sequence_length": 384,
        "parameters": "109M"
    },
    "bge-small-en-v1.5": {
        "model_name": "BAAI/bge-small-en-v1.5",
        "dimension": 384,
        "description": "BAAI BGE Small English v1.5 - Compact high performance model",
        "max_sequence_length": 512,
        "parameters": "33M"
    }
}


def create_sentence_transformer_provider(model_key: str = "all-MiniLM-L6-v2",
                                       device: Optional[str] = None) -> SentenceTransformerProvider:
    """
    Create a SentenceTransformer provider with a predefined model configuration.

    Args:
        model_key: Key from MODEL_CONFIGS or full model name
        device: Device to run on

    Returns:
        SentenceTransformerProvider: Configured provider
    """
    if model_key in MODEL_CONFIGS:
        model_name = MODEL_CONFIGS[model_key]["model_name"]
    else:
        model_name = model_key

    return SentenceTransformerProvider(model_name, device)