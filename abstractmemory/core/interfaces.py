"""
Core memory interfaces based on SOTA research.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass


@dataclass
class MemoryItem:
    """Base class for memory items"""
    content: Any
    event_time: datetime      # When it happened
    ingestion_time: datetime  # When we learned it
    confidence: float = 1.0
    metadata: Dict[str, Any] = None


class IMemoryComponent(ABC):
    """Interface for memory components"""

    @abstractmethod
    def add(self, item: MemoryItem) -> str:
        """Add item to memory, return ID"""
        pass

    @abstractmethod
    def retrieve(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """Retrieve relevant items"""
        pass

    @abstractmethod
    def consolidate(self) -> int:
        """Consolidate memory, return items consolidated"""
        pass


class IRetriever(ABC):
    """Interface for retrieval strategies"""

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[Tuple[float, Any]]:
        """Search and return (score, item) tuples"""
        pass


class IStorage(ABC):
    """Interface for storage backends"""

    @abstractmethod
    def save(self, key: str, value: Any) -> None:
        """Save value with key"""
        pass

    @abstractmethod
    def load(self, key: str) -> Any:
        """Load value by key"""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        pass