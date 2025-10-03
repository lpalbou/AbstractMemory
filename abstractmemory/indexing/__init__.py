"""
Memory indexing system for AbstractMemory.

This module provides configurable indexing of memory modules to LanceDB
for efficient semantic search and dynamic context injection.
"""

from .config import MemoryIndexConfig
from .memory_indexer import MemoryIndexer

__all__ = ['MemoryIndexConfig', 'MemoryIndexer']