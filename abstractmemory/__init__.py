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

        For grounded memory with storage:
            storage_backend: "markdown", "lancedb", "dual", or None
            storage_path: Path for markdown storage
            storage_uri: URI for LanceDB storage
            embedding_provider: AbstractCore instance for embeddings

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

        # With LanceDB storage (SQL + vector search)
        from abstractllm import create_llm
        provider = create_llm("openai")
        memory = create_memory("grounded",
            storage_backend="lancedb",
            storage_uri="./lance.db",
            embedding_provider=provider
        )

        # With dual storage (both markdown and LanceDB)
        memory = create_memory("grounded",
            storage_backend="dual",
            storage_path="./memory",
            storage_uri="./lance.db",
            embedding_provider=provider
        )
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
                 storage_path: Optional[str] = None,
                 storage_uri: Optional[str] = None,
                 embedding_provider: Optional[Any] = None,
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

        # Initialize new storage manager
        self.storage_manager = self._init_storage_manager(
            storage_backend, storage_path, storage_uri, embedding_provider
        )

        # Legacy storage backend for compatibility
        self.storage = self._init_storage(storage_backend, embedding_provider)

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

        # Save interaction and generate experiential note if storage enabled
        if hasattr(self, 'storage_manager') and self.storage_manager and self.storage_manager.is_enabled():
            # Extract topic for the interaction
            topic = self._extract_topic(user_input, agent_response)

            # Save verbatim interaction
            interaction_id = self.storage_manager.save_interaction(
                user_id=user_id,
                timestamp=now,
                user_input=user_input,
                agent_response=agent_response,
                topic=topic,
                metadata={
                    'relational': relational.__dict__,
                    'session_id': relational.session_id,
                    'confidence': episode.confidence
                }
            )

            # Generate experiential note if conditions met
            if self._should_reflect(user_input, agent_response, user_id):
                reflection = self._generate_reflection(user_input, agent_response, user_id, relational)
                if reflection:
                    note_id = self.storage_manager.save_experiential_note(
                        timestamp=now,
                        reflection=reflection,
                        interaction_id=interaction_id or f"int_{now.timestamp()}",
                        note_type="interaction_reflection",
                        metadata={
                            'user_id': user_id,
                            'trigger': 'interaction',
                            'confidence_change': self._calculate_confidence_change(user_input, agent_response)
                        }
                    )

                    # Create bidirectional link
                    if interaction_id and note_id:
                        self.storage_manager.link_interaction_to_note(interaction_id, note_id)

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

    def _should_reflect(self, user_input: str, agent_response: str, user_id: str) -> bool:
        """Determine if the interaction warrants an experiential note"""

        # Always reflect on learning about users
        if self._contains_user_learning(user_input, agent_response):
            return True

        # Reflect on pattern recognition (failures/successes)
        if self._contains_pattern_learning(user_input, agent_response):
            return True

        # Reflect on significant topic shifts
        if self._is_significant_topic_shift(user_input):
            return True

        # Reflect on high-confidence interactions
        confidence_change = self._calculate_confidence_change(user_input, agent_response)
        if abs(confidence_change) > 0.3:
            return True

        # Periodic reflection (every 10th interaction)
        if user_id in self.user_profiles:
            interaction_count = self.user_profiles[user_id]["interaction_count"]
            if interaction_count % 10 == 0:
                return True

        return False

    def _generate_reflection(self, user_input: str, agent_response: str,
                           user_id: str, relational: RelationalContext) -> str:
        """Generate AI experiential note about the interaction"""

        # Analyze interaction patterns
        patterns = []

        if self._contains_user_learning(user_input, agent_response):
            patterns.append("🧠 **User Learning Detected**: New information about user preferences or characteristics")

        if self._contains_pattern_learning(user_input, agent_response):
            patterns.append("📊 **Pattern Recognition**: Identified recurring behavior or outcome patterns")

        confidence_change = self._calculate_confidence_change(user_input, agent_response)
        if confidence_change > 0.2:
            patterns.append(f"⬆️ **Confidence Boost**: Interaction increased confidence by {confidence_change:.2f}")
        elif confidence_change < -0.2:
            patterns.append(f"⬇️ **Uncertainty Introduced**: Interaction decreased confidence by {abs(confidence_change):.2f}")

        # Generate reflection content
        reflection_parts = [
            f"## Interaction Analysis",
            f"**User**: {user_id} ({relational.relationship})",
            f"**Context**: {user_input[:100]}..." if len(user_input) > 100 else f"**Context**: {user_input}",
            "",
            "## Key Observations"
        ]

        if patterns:
            reflection_parts.extend(patterns)
        else:
            reflection_parts.append("📝 **Routine Interaction**: Standard conversational exchange with no significant patterns detected")

        # Add learning insights
        reflection_parts.extend([
            "",
            "## Memory Impact",
            f"- **Working Memory**: Added interaction to recent context",
            f"- **Episodic Memory**: Stored as complete interaction episode"
        ])

        if self._contains_facts(agent_response):
            reflection_parts.append("- **Semantic Memory**: Potential facts identified for validation")

        if self.kg:
            reflection_parts.append("- **Knowledge Graph**: Updated entity relationships")

        # Future considerations
        reflection_parts.extend([
            "",
            "## Future Considerations",
            self._generate_future_considerations(user_input, agent_response, user_id)
        ])

        return "\n".join(reflection_parts)

    def _contains_user_learning(self, user_input: str, agent_response: str) -> bool:
        """Check if interaction contains learning about the user"""
        user_indicators = [
            "i am", "i'm", "my", "i like", "i prefer", "i work", "i live",
            "i think", "i believe", "i usually", "i tend to"
        ]
        return any(indicator in user_input.lower() for indicator in user_indicators)

    def _contains_pattern_learning(self, user_input: str, agent_response: str) -> bool:
        """Check if interaction contains pattern learning"""
        pattern_indicators = [
            "failed", "error", "worked", "success", "usually", "often",
            "always", "never", "typically", "tends to"
        ]
        combined_text = f"{user_input} {agent_response}".lower()
        return any(indicator in combined_text for indicator in pattern_indicators)

    def _is_significant_topic_shift(self, user_input: str) -> bool:
        """Check if this represents a significant topic shift"""
        # Simple heuristic: check for topic transition words
        transition_words = [
            "by the way", "actually", "also", "now", "next", "moving on",
            "switching topics", "changing subject"
        ]
        return any(word in user_input.lower() for word in transition_words)

    def _calculate_confidence_change(self, user_input: str, agent_response: str) -> float:
        """Calculate the confidence change from this interaction"""
        # Simple heuristic based on certainty indicators
        confidence_boost = [
            "exactly", "definitely", "certainly", "absolutely", "confirmed",
            "correct", "right", "yes", "perfect"
        ]

        confidence_reduction = [
            "maybe", "perhaps", "might", "could be", "not sure",
            "uncertain", "unclear", "confused", "don't know"
        ]

        response_lower = agent_response.lower()

        boost_count = sum(1 for word in confidence_boost if word in response_lower)
        reduction_count = sum(1 for word in confidence_reduction if word in response_lower)

        # Scale to reasonable range
        return (boost_count - reduction_count) * 0.1

    def _contains_facts(self, text: str) -> bool:
        """Check if text contains factual statements"""
        fact_patterns = [
            r'\w+ is \w+', r'\w+ has \w+', r'\w+ can \w+',
            r'\w+ means \w+', r'\w+ equals \w+'
        ]

        import re
        for pattern in fact_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _generate_future_considerations(self, user_input: str, agent_response: str, user_id: str) -> str:
        """Generate considerations for future interactions"""
        considerations = []

        # User-specific considerations
        if user_id in self.user_profiles:
            profile = self.user_profiles[user_id]
            if profile["interaction_count"] < 5:
                considerations.append("👋 Early interaction - continue building user profile")
            elif len(profile.get("facts", [])) < 3:
                considerations.append("🔍 Learn more about user preferences and background")

        # Topic-specific considerations
        if "help" in user_input.lower():
            considerations.append("🤝 User seeking assistance - prioritize helpful, clear responses")

        if "learn" in user_input.lower():
            considerations.append("📚 User in learning mode - provide educational content")

        # Default consideration
        if not considerations:
            considerations.append("💭 Monitor for patterns and user preference indicators")

        return " • ".join(considerations)

    def _extract_topic(self, user_input: str, agent_response: str) -> str:
        """Extract main topic from interaction"""
        # Simple topic extraction - could be enhanced with NLP
        text = f"{user_input} {agent_response}".lower()

        # Look for key terms
        topics = []
        if "python" in text:
            topics.append("python")
        if "code" in text or "programming" in text:
            topics.append("coding")
        if "learn" in text or "teach" in text:
            topics.append("learning")
        if "help" in text or "assist" in text:
            topics.append("assistance")
        if "memory" in text or "remember" in text:
            topics.append("memory")

        # Default topic from first few words of user input
        if not topics:
            words = user_input.split()[:3]
            topic = "_".join(word.lower().strip(".,!?") for word in words if word.isalpha())
            topics.append(topic or "general")

        return topics[0]

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

    def _init_storage_manager(self, backend: Optional[str], storage_path: Optional[str],
                             storage_uri: Optional[str], embedding_provider: Optional[Any]):
        """Initialize dual storage manager"""
        if backend is None:
            return None

        try:
            from .storage.dual_manager import DualStorageManager
            return DualStorageManager(
                mode=backend,
                markdown_path=storage_path,
                lancedb_uri=storage_uri,
                embedding_provider=embedding_provider
            )
        except ImportError as e:
            import logging
            logging.warning(f"Failed to initialize storage manager: {e}")
            return None

    def _init_storage(self, backend: Optional[str], embedding_provider: Optional[Any] = None):
        """Initialize storage backend (legacy compatibility)"""
        if backend == 'lancedb':
            try:
                from .storage.lancedb_storage import LanceDBStorage
                return LanceDBStorage("./lance.db", embedding_provider)
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
        # Use new storage manager if available
        if self.storage_manager and self.storage_manager.is_enabled():
            # Save each component to storage manager
            self.storage_manager.save_memory_component("core", self.core)
            self.storage_manager.save_memory_component("semantic", self.semantic)
            self.storage_manager.save_memory_component("working", self.working)
            self.storage_manager.save_memory_component("episodic", self.episodic)
            if self.kg:
                self.storage_manager.save_memory_component("knowledge_graph", self.kg)

            # Save user profiles and patterns
            self.storage_manager.save_memory_component("user_profiles", self.user_profiles)
            self.storage_manager.save_memory_component("failure_patterns", self.failure_patterns)
            self.storage_manager.save_memory_component("success_patterns", self.success_patterns)

        # Fallback to legacy storage
        elif self.storage:
            # Save each component (four-tier architecture)
            self.storage.save(f"{path}/core", self.core)
            self.storage.save(f"{path}/semantic", self.semantic)
            self.storage.save(f"{path}/working", self.working)
            self.storage.save(f"{path}/episodic", self.episodic)
            if self.kg:
                self.storage.save(f"{path}/kg", self.kg)

    def load(self, path: str):
        """Load memory from disk"""
        # Use new storage manager if available
        if self.storage_manager and self.storage_manager.is_enabled():
            # Load each component from storage manager
            core_data = self.storage_manager.load_memory_component("core")
            if core_data:
                # Reconstruct core memory from data
                pass  # Would need to implement reconstruction logic

            semantic_data = self.storage_manager.load_memory_component("semantic")
            if semantic_data:
                # Reconstruct semantic memory from data
                pass  # Would need to implement reconstruction logic

            # Load user profiles and patterns
            user_profiles = self.storage_manager.load_memory_component("user_profiles")
            if user_profiles:
                self.user_profiles = user_profiles

            failure_patterns = self.storage_manager.load_memory_component("failure_patterns")
            if failure_patterns:
                self.failure_patterns = failure_patterns

            success_patterns = self.storage_manager.load_memory_component("success_patterns")
            if success_patterns:
                self.success_patterns = success_patterns

        # Fallback to legacy storage
        elif self.storage and self.storage.exists(path):
            # Load components (four-tier architecture)
            if self.storage.exists(f"{path}/core"):
                self.core = self.storage.load(f"{path}/core")
            if self.storage.exists(f"{path}/semantic"):
                self.semantic = self.storage.load(f"{path}/semantic")
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

    def search_stored_interactions(self, query: str, user_id: Optional[str] = None,
                                  start_date: Optional[datetime] = None,
                                  end_date: Optional[datetime] = None) -> List[Dict]:
        """Search stored interactions and experiential notes"""
        if self.storage_manager and self.storage_manager.is_enabled():
            return self.storage_manager.search_interactions(query, user_id, start_date, end_date)
        return []

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about stored data"""
        if self.storage_manager and self.storage_manager.is_enabled():
            return self.storage_manager.get_storage_stats()
        return {"storage_enabled": False}

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