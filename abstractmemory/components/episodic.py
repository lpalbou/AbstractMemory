"""
Episodic memory for experiences and events.
"""

from typing import List, Dict
from datetime import datetime

from abstractmemory.core.interfaces import IMemoryComponent, MemoryItem
from abstractmemory.core.temporal import GroundingAnchor, TemporalSpan, RelationalContext


class EpisodicMemory(IMemoryComponent):
    """Long-term episodic memory with temporal organization"""

    def __init__(self):
        self.episodes = {}  # ID -> Episode
        self.temporal_index = {}  # For temporal queries

    def add(self, item: MemoryItem) -> str:
        """Add episode to memory"""
        episode_id = f"ep_{len(self.episodes)}_{datetime.now().timestamp()}"

        # Create grounding anchor with minimal relational context
        anchor = GroundingAnchor(
            event_time=item.event_time,
            ingestion_time=item.ingestion_time,
            validity_span=TemporalSpan(start=item.event_time),
            relational=RelationalContext(user_id="default"),  # Will be updated when used in GroundedMemory
            confidence=item.confidence
        )

        self.episodes[episode_id] = {
            'item': item,
            'anchor': anchor,
            'related': []  # Links to related episodes
        }

        # Update temporal index
        self.temporal_index[episode_id] = anchor

        return episode_id

    def retrieve(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """Retrieve episodes matching query"""
        # Simple implementation - would use embeddings in production
        results = []
        query_lower = query.lower()

        for episode in self.episodes.values():
            if query_lower in str(episode['item'].content).lower():
                results.append(episode['item'])
                if len(results) >= limit:
                    break

        return results

    def consolidate(self) -> int:
        """Consolidate similar episodes"""
        # Would implement clustering/summarization
        return 0

    def get_episodes_between(self, start: datetime, end: datetime) -> List[MemoryItem]:
        """Get episodes between times"""
        results = []
        for episode in self.episodes.values():
            if start <= episode['anchor'].event_time <= end:
                results.append(episode['item'])
        return sorted(results, key=lambda x: x.event_time)