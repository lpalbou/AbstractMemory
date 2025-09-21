"""
AbstractMemory - Temporal knowledge graph memory for LLM agents.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from .core.interfaces import MemoryItem
from .components.working import WorkingMemory
from .components.episodic import EpisodicMemory
from .graph.knowledge_graph import TemporalKnowledgeGraph


class TemporalMemory:
    """
    Main memory system combining all components.
    """

    def __init__(self,
                 working_capacity: int = 10,
                 enable_kg: bool = True,
                 storage_backend: Optional[str] = None):
        """Initialize temporal memory system"""

        # Initialize components
        self.working = WorkingMemory(capacity=working_capacity)
        self.episodic = EpisodicMemory()

        # Initialize knowledge graph if enabled
        self.kg = TemporalKnowledgeGraph() if enable_kg else None

        # Storage backend
        self.storage = self._init_storage(storage_backend)

    def add_interaction(self, user_input: str, agent_response: str):
        """Add user-agent interaction to memory"""
        now = datetime.now()

        # Add to working memory
        user_item = MemoryItem(
            content={'role': 'user', 'text': user_input},
            event_time=now,
            ingestion_time=now
        )
        self.working.add(user_item)

        # Add to episodic memory
        episode = MemoryItem(
            content={'interaction': {'user': user_input, 'agent': agent_response}},
            event_time=now,
            ingestion_time=now
        )
        self.episodic.add(episode)

        # Extract facts if KG enabled
        if self.kg:
            self._extract_facts_to_kg(agent_response, now)

    def _extract_facts_to_kg(self, text: str, event_time: datetime):
        """Extract facts from text and add to KG"""
        # Simplified extraction - would use NLP/LLM in production
        # Look for patterns like "X is Y" or "X has Y"
        import re

        patterns = [
            r'(\w+)\s+is\s+(\w+)',
            r'(\w+)\s+has\s+(\w+)',
            r'(\w+)\s+can\s+(\w+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    self.kg.add_fact(
                        subject=match[0],
                        predicate='is' if 'is' in pattern else 'has' if 'has' in pattern else 'can',
                        object=match[1],
                        event_time=event_time
                    )

    def retrieve_context(self, query: str, max_items: int = 5) -> str:
        """Retrieve relevant context for query"""
        context_parts = []

        # Get from working memory
        working_items = self.working.retrieve(query, limit=max_items)
        if working_items:
            context_parts.append("Recent context:")
            for item in working_items:
                if isinstance(item.content, dict):
                    context_parts.append(f"- {item.content.get('text', str(item.content))}")

        # Get from episodic memory
        episodes = self.episodic.retrieve(query, limit=max_items)
        if episodes:
            context_parts.append("\nRelevant episodes:")
            for episode in episodes:
                context_parts.append(f"- {str(episode.content)[:100]}...")

        # Get from knowledge graph
        if self.kg:
            facts = self.kg.query_at_time(query, datetime.now())
            if facts:
                context_parts.append("\nKnown facts:")
                for fact in facts[:max_items]:
                    context_parts.append(
                        f"- {fact['subject']} {fact['predicate']} {fact['object']}"
                    )

        return "\n".join(context_parts) if context_parts else "No relevant context found."

    def _init_storage(self, backend: Optional[str]):
        """Initialize storage backend"""
        if backend == 'lancedb':
            from .storage.lancedb import LanceDBStorage
            return LanceDBStorage()
        elif backend == 'file':
            from .storage.file_storage import FileStorage
            return FileStorage()
        return None

    def save(self, path: str):
        """Save memory to disk"""
        if self.storage:
            # Save each component
            self.storage.save(f"{path}/working", self.working)
            self.storage.save(f"{path}/episodic", self.episodic)
            if self.kg:
                self.storage.save(f"{path}/kg", self.kg)

    def load(self, path: str):
        """Load memory from disk"""
        if self.storage and self.storage.exists(path):
            # Load components
            self.working = self.storage.load(f"{path}/working")
            self.episodic = self.storage.load(f"{path}/episodic")
            if self.storage.exists(f"{path}/kg"):
                self.kg = self.storage.load(f"{path}/kg")


# Export main classes
__all__ = ['TemporalMemory', 'MemoryItem', 'TemporalKnowledgeGraph']