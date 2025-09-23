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

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


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

    @abstractmethod
    def save_interaction(self, user_id: str, timestamp: datetime,
                        user_input: str, agent_response: str,
                        topic: str, metadata: Optional[Dict] = None) -> str:
        """Save verbatim interaction, return interaction ID"""
        pass

    @abstractmethod
    def save_experiential_note(self, timestamp: datetime, reflection: str,
                              interaction_id: str, note_type: str = "reflection",
                              metadata: Optional[Dict] = None) -> str:
        """Save AI experiential note, return note ID"""
        pass

    @abstractmethod
    def link_interaction_to_note(self, interaction_id: str, note_id: str) -> None:
        """Create bidirectional link between interaction and note"""
        pass

    @abstractmethod
    def search_interactions(self, query: str, user_id: Optional[str] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> List[Dict]:
        """Search interactions with filters"""
        pass