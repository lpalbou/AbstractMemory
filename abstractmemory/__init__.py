"""
AbstractMemory - Two-tier memory strategy for different agent types.

Simple agents use ScratchpadMemory or BufferMemory.
Complex agents use full GroundedMemory.
"""

from typing import Dict, List, Optional, Any, Union, Literal
from datetime import datetime
import uuid

from .simple import ScratchpadMemory, BufferMemory
from .session import MemorySession, MemoryConfig
from .grounded_memory import GroundedMemory, MemoryIdentity
from .core.interfaces import MemoryItem
from .core.temporal import RelationalContext
from .components.core import CoreMemory
from .components.working import WorkingMemory
from .components.semantic import SemanticMemory
from .components.episodic import EpisodicMemory
from .components.document import DocumentMemory
from .graph.knowledge_graph import TemporalKnowledgeGraph


def create_memory(
    memory_type: Literal["scratchpad", "buffer", "grounded"] = "scratchpad",
    **kwargs
) -> Union[ScratchpadMemory, BufferMemory, 'GroundedMemory']:
    """
    Factory function to create appropriate memory for agent type.

    Args:
        memory_type: Type of memory to create
            - "scratchpad": For ReAct agents and task tools
            - "buffer": For simple chatbots
            - "grounded": For autonomous agents (multi-dimensional memory)

        For grounded memory with storage:
            storage_backend: "markdown", "lancedb", "dual", or None
            storage_path: Path for markdown storage
            storage_uri: URI for LanceDB storage
            embedding_provider: Embedding provider for semantic search (defaults to all-MiniLM-L6-v2)

    Examples:
        # For a ReAct agent
        memory = create_memory("scratchpad", max_entries=50)

        # For a simple chatbot
        memory = create_memory("buffer", max_messages=100)

        # For an autonomous assistant with user tracking
        memory = create_memory("grounded", working_capacity=10, enable_kg=True)
        memory.set_current_user("alice", relationship="owner")

        # With markdown storage (observable AI memory)
        memory = create_memory("grounded",
            storage_backend="markdown",
            storage_path="./memory"
        )

        # With LanceDB storage (uses default all-MiniLM-L6-v2 embeddings)
        memory = create_memory("grounded",
            storage_backend="lancedb",
            storage_uri="./lance.db"
        )

        # With custom embedding provider
        from abstractmemory.embeddings.sentence_transformer_provider import create_sentence_transformer_provider
        custom_provider = create_sentence_transformer_provider("bge-base-en-v1.5")
        memory = create_memory("grounded",
            storage_backend="dual",
            storage_path="./memory",
            storage_uri="./lance.db",
            embedding_provider=custom_provider
        )
    """
    if memory_type == "scratchpad":
        return ScratchpadMemory(**kwargs)
    elif memory_type == "buffer":
        return BufferMemory(**kwargs)
    elif memory_type == "grounded":
        # Auto-configure default embedding provider if needed
        storage_backend = kwargs.get('storage_backend')
        embedding_provider = kwargs.get('embedding_provider')

        # If storage requires embeddings but no provider specified, use default
        if storage_backend in ['lancedb', 'dual'] and embedding_provider is None:
            try:
                from .embeddings.sentence_transformer_provider import create_sentence_transformer_provider
                default_provider = create_sentence_transformer_provider("all-MiniLM-L6-v2")
                kwargs['embedding_provider'] = default_provider

                import logging
                logging.info("Using default all-MiniLM-L6-v2 embedding model for semantic search")

            except ImportError:
                import logging
                logging.warning(
                    "sentence-transformers not available. Install with: pip install sentence-transformers. "
                    "Vector search will not be available."
                )
            except Exception as e:
                import logging
                logging.warning(f"Could not initialize default embedding provider: {e}")

        return GroundedMemory(**kwargs)
    else:
        raise ValueError(f"Unknown memory type: {memory_type}")


# Export main classes and factory
__all__ = [
    # Memory types
    'ScratchpadMemory',
    'BufferMemory',
    'GroundedMemory',

    # Identity system
    'MemoryIdentity',

    # Session and configuration
    'MemorySession',
    'MemoryConfig',

    # Factory function
    'create_memory',

    # Core interfaces
    'MemoryItem',
    'RelationalContext',

    # Memory components
    'CoreMemory',
    'WorkingMemory',
    'SemanticMemory',
    'EpisodicMemory',
    'DocumentMemory',
    'TemporalKnowledgeGraph'
]
