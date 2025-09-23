"""
AbstractMemory - Two-tier memory strategy for different agent types.

Simple agents use ScratchpadMemory or BufferMemory.
Complex agents use full GroundedMemory.
"""

from typing import Dict, List, Optional, Any, Union, Literal
from datetime import datetime
import uuid

from .simple import ScratchpadMemory, BufferMemory
from .core.interfaces import MemoryItem
from .core.temporal import RelationalContext
from .components.core import CoreMemory
from .components.working import WorkingMemory
from .components.semantic import SemanticMemory
from .components.episodic import EpisodicMemory
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

    Examples:
        # For a ReAct agent
        memory = create_memory("scratchpad", max_entries=50)

        # For a simple chatbot
        memory = create_memory("buffer", max_messages=100)

        # For an autonomous assistant with user tracking
        memory = create_memory("grounded", working_capacity=10, enable_kg=True)
        memory.set_current_user("alice", relationship="owner")
    """
    if memory_type == "scratchpad":
        return ScratchpadMemory(**kwargs)
    elif memory_type == "buffer":
        return BufferMemory(**kwargs)
    elif memory_type == "grounded":
        return GroundedMemory(**kwargs)
    else:
        raise ValueError(f"Unknown memory type: {memory_type}")


class GroundedMemory:
    """
    Multi-dimensionally grounded memory for autonomous agents.
    Grounds memory in WHO (relational), WHEN (temporal), and WHERE (spatial).

    Memory Architecture:
    - Core: Agent identity and persona (rarely changes)
    - Semantic: Validated facts and concepts (requires recurrence)
    - Working: Current context (transient)
    - Episodic: Event archive (long-term)
    """

    def __init__(self,
                 working_capacity: int = 10,
                 enable_kg: bool = True,
                 storage_backend: Optional[str] = None,
                 default_user_id: str = "default",
                 semantic_threshold: int = 3):
        """Initialize grounded memory system"""

        # Initialize memory components (Four-tier architecture)
        self.core = CoreMemory()  # Agent identity (rarely updated)
        self.semantic = SemanticMemory(validation_threshold=semantic_threshold)  # Validated facts
        self.working = WorkingMemory(capacity=working_capacity)  # Transient context
        self.episodic = EpisodicMemory()  # Event archive

        # Initialize knowledge graph if enabled
        self.kg = TemporalKnowledgeGraph() if enable_kg else None

        # Relational tracking
        self.current_user = default_user_id
        self.user_profiles: Dict[str, Dict] = {}  # User-specific profiles
        self.user_memories: Dict[str, List] = {}  # User-specific memory indices

        # Learning tracking
        self.failure_patterns: Dict[str, int] = {}  # Track repeated failures
        self.success_patterns: Dict[str, int] = {}  # Track successful patterns

        # Core memory update tracking
        self.core_update_candidates: Dict[str, int] = {}  # Track potential core updates
        self.core_update_threshold = 5  # Require 5 occurrences before core update

        # Storage backend
        self.storage = self._init_storage(storage_backend)

    def set_current_user(self, user_id: str, relationship: Optional[str] = None):
        """Set the current user for relational context"""
        self.current_user = user_id

        # Initialize user profile if new
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                "first_seen": datetime.now(),
                "relationship": relationship or "unknown",
                "interaction_count": 0,
                "preferences": {},
                "facts": []
            }
            self.user_memories[user_id] = []

    def add_interaction(self, user_input: str, agent_response: str,
                       user_id: Optional[str] = None):
        """Add user-agent interaction with relational grounding"""
        now = datetime.now()
        user_id = user_id or self.current_user

        # Create relational context
        relational = RelationalContext(
            user_id=user_id,
            agent_id="main",
            relationship=self.user_profiles.get(user_id, {}).get("relationship"),
            session_id=str(uuid.uuid4())[:8]
        )

        # Add to working memory with relational context
        user_item = MemoryItem(
            content={
                'role': 'user',
                'text': user_input,
                'user_id': user_id  # Track who said it
            },
            event_time=now,
            ingestion_time=now,
            metadata={'relational': relational.__dict__}
        )
        item_id = self.working.add(user_item)

        # Track in user-specific memory index
        if user_id in self.user_memories:
            self.user_memories[user_id].append(item_id)

        # Update user profile
        if user_id in self.user_profiles:
            self.user_profiles[user_id]["interaction_count"] += 1

        # Add to episodic memory with full context
        episode = MemoryItem(
            content={
                'interaction': {
                    'user': user_input,
                    'agent': agent_response,
                    'user_id': user_id
                }
            },
            event_time=now,
            ingestion_time=now,
            metadata={'relational': relational.__dict__}
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

    def get_full_context(self, query: str, max_items: int = 5,
                        user_id: Optional[str] = None) -> str:
        """Get user-specific context through relational lens"""
        user_id = user_id or self.current_user
        context_parts = []

        # Include user profile if known
        if user_id in self.user_profiles:
            profile = self.user_profiles[user_id]
            context_parts.append(f"=== User Profile: {user_id} ===")
            context_parts.append(f"Relationship: {profile['relationship']}")
            context_parts.append(f"Known for: {profile['interaction_count']} interactions")
            if profile.get('facts'):
                context_parts.append(f"Known facts: {', '.join(profile['facts'][:3])}")

        # Always include core memory (agent identity)
        core_context = self.core.get_context()
        if core_context:
            context_parts.append("\n=== Core Memory (Identity) ===")
            context_parts.append(core_context)

        # Include relevant semantic memory (validated facts)
        semantic_facts = self.semantic.retrieve(query, limit=max_items//2)
        if semantic_facts:
            context_parts.append("\n=== Learned Facts ===")
            for fact in semantic_facts:
                context_parts.append(f"- {fact.content} (confidence: {fact.confidence:.2f})")

        # Check for learned failures/successes relevant to query
        for pattern, count in self.failure_patterns.items():
            if query.lower() in pattern.lower() and count >= 2:
                context_parts.append(f"\n⚠️ Warning: Previous failures with similar action ({count} times)")
                break

        # Get from working memory (recent context)
        working_items = self.working.retrieve(query, limit=max_items)
        if working_items:
            context_parts.append("\n=== Recent Context ===")
            for item in working_items:
                if isinstance(item.content, dict):
                    context_parts.append(f"- {item.content.get('text', str(item.content))}")

        # Get from episodic memory (retrieved as needed)
        episodes = self.episodic.retrieve(query, limit=max_items)
        if episodes:
            context_parts.append("\n=== Relevant Episodes ===")
            for episode in episodes:
                context_parts.append(f"- {str(episode.content)[:100]}...")

        # Get from knowledge graph
        if self.kg:
            facts = self.kg.query_at_time(query, datetime.now())
            if facts:
                context_parts.append("\n=== Known Facts ===")
                for fact in facts[:max_items]:
                    context_parts.append(
                        f"- {fact['subject']} {fact['predicate']} {fact['object']}"
                    )

        return "\n\n".join(context_parts) if context_parts else "No relevant context found."

    def retrieve_context(self, query: str, max_items: int = 5) -> str:
        """Backward compatibility wrapper"""
        return self.get_full_context(query, max_items)

    def _init_storage(self, backend: Optional[str]):
        """Initialize storage backend"""
        if backend == 'lancedb':
            try:
                from .storage.lancedb import LanceDBStorage
                return LanceDBStorage()
            except ImportError:
                return None
        elif backend == 'file':
            try:
                from .storage.file_storage import FileStorage
                return FileStorage()
            except ImportError:
                return None
        return None

    def save(self, path: str):
        """Save memory to disk"""
        if self.storage:
            # Save each component (four-tier architecture)
            self.storage.save(f"{path}/core", self.core)
            self.storage.save(f"{path}/working", self.working)
            self.storage.save(f"{path}/episodic", self.episodic)
            if self.kg:
                self.storage.save(f"{path}/kg", self.kg)

    def load(self, path: str):
        """Load memory from disk"""
        if self.storage and self.storage.exists(path):
            # Load components (four-tier architecture)
            if self.storage.exists(f"{path}/core"):
                self.core = self.storage.load(f"{path}/core")
            self.working = self.storage.load(f"{path}/working")
            self.episodic = self.storage.load(f"{path}/episodic")
            if self.storage.exists(f"{path}/kg"):
                self.kg = self.storage.load(f"{path}/kg")

    def learn_about_user(self, fact: str, user_id: Optional[str] = None):
        """Learn and remember a fact about a specific user"""
        user_id = user_id or self.current_user

        if user_id in self.user_profiles:
            # Add to user's facts
            if 'facts' not in self.user_profiles[user_id]:
                self.user_profiles[user_id]['facts'] = []

            # Track for potential core memory update (requires recurrence)
            core_key = f"user:{user_id}:{fact}"
            self.core_update_candidates[core_key] = self.core_update_candidates.get(core_key, 0) + 1

            # Add to user's facts if not already there
            if fact not in self.user_profiles[user_id]['facts']:
                self.user_profiles[user_id]['facts'].append(fact)

            # Only update core memory after threshold met
            if self.core_update_candidates[core_key] >= self.core_update_threshold:
                current_info = self.core.blocks.get("user_info").content
                updated_info = f"{current_info}\n- {fact}"
                self.core.update_block("user_info", updated_info,
                                     f"Validated through recurrence: {fact}")
                del self.core_update_candidates[core_key]

    def track_failure(self, action: str, context: str):
        """Track a failed action to learn from mistakes"""
        failure_key = f"{action}:{context}"
        self.failure_patterns[failure_key] = self.failure_patterns.get(failure_key, 0) + 1

        # After repeated failures, add to semantic memory as a learned constraint
        if self.failure_patterns[failure_key] >= 3:
            fact = f"Action '{action}' tends to fail in context: {context}"
            fact_item = MemoryItem(
                content=fact,
                event_time=datetime.now(),
                ingestion_time=datetime.now(),
                confidence=0.9,
                metadata={'type': 'learned_constraint', 'failure_count': self.failure_patterns[failure_key]}
            )
            # Add multiple times to reach semantic validation threshold
            for _ in range(self.semantic.validation_threshold):
                self.semantic.add(fact_item)

    def track_success(self, action: str, context: str):
        """Track a successful action to reinforce patterns"""
        success_key = f"{action}:{context}"
        self.success_patterns[success_key] = self.success_patterns.get(success_key, 0) + 1

        # After repeated successes, add to semantic memory as a learned strategy
        if self.success_patterns[success_key] >= 3:
            fact = f"Action '{action}' works well in context: {context}"
            fact_item = MemoryItem(
                content=fact,
                event_time=datetime.now(),
                ingestion_time=datetime.now(),
                confidence=0.9,
                metadata={'type': 'learned_strategy', 'success_count': self.success_patterns[success_key]}
            )
            # Add multiple times to reach semantic validation threshold
            for _ in range(self.semantic.validation_threshold):
                self.semantic.add(fact_item)

    def consolidate_memories(self):
        """Consolidate working memory to semantic/episodic based on importance"""
        # Get items from working memory
        working_items = self.working.get_context_window()

        for item in working_items:
            # Extract potential facts for semantic memory
            if isinstance(item.content, dict):
                content_text = item.content.get('text', '')
                # Simple heuristic: statements with "is", "are", "means" are potential facts
                if any(word in content_text.lower() for word in ['is', 'are', 'means', 'equals']):
                    self.semantic.add(item)

            # Important items go to episodic memory
            if item.confidence > 0.7 or (item.metadata and item.metadata.get('important')):
                self.episodic.add(item)

        # Consolidate semantic memory concepts
        self.semantic.consolidate()

    def get_user_context(self, user_id: str) -> Optional[Dict]:
        """Get everything we know about a specific user"""
        return self.user_profiles.get(user_id)

    def update_core_memory(self, block_id: str, content: str, reasoning: str = "") -> bool:
        """Agent can update core memory blocks (self-editing capability)"""
        return self.core.update_block(block_id, content, reasoning)

    def get_core_memory_context(self) -> str:
        """Get core memory context for always-accessible facts"""
        return self.core.get_context()


# Export main classes and factory
__all__ = [
    'create_memory',  # Factory function
    'ScratchpadMemory',  # Simple memory for task agents
    'BufferMemory',  # Simple buffer for chatbots
    'GroundedMemory',  # Multi-dimensional memory for autonomous agents
    'MemoryItem',  # Data structure
    'CoreMemory',  # Core memory component (identity)
    'SemanticMemory',  # Semantic memory component (validated facts)
    'WorkingMemory',  # Working memory component (transient)
    'EpisodicMemory',  # Episodic memory component (events)
    'TemporalKnowledgeGraph',  # Knowledge graph
    'RelationalContext'  # For tracking who
]