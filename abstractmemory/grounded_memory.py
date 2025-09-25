"""
GroundedMemory - Identity-based multi-dimensional memory for autonomous agents.

Supports multiple identities, each with its own complete memory set including:
- Core values and beliefs (identity)
- Accumulated experiences (what shaped it)
- Learned patterns (behavior)
- Relationships (who it knows)
- Skills and knowledge (capabilities)
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import uuid
import json
import logging
from pathlib import Path

from .core.interfaces import MemoryItem
from .core.temporal import RelationalContext
from .components.core import CoreMemory
from .components.working import WorkingMemory
from .components.semantic import SemanticMemory
from .components.episodic import EpisodicMemory
from .graph.knowledge_graph import TemporalKnowledgeGraph

logger = logging.getLogger(__name__)


class SubjectiveExperience:
    """
    Core values as interpretive lens - the key insight for identity formation.

    Same objective fact → Different subjective meaning based on values.
    This is how identity emerges from accumulated experiences.
    """

    def __init__(self, core_values: Dict[str, Any] = None):
        self.core_values = core_values or {}

    def interpret(self, fact: str) -> Dict[str, Any]:
        """
        Apply core values lens to interpret an objective fact subjectively.

        Args:
            fact: Objective statement

        Returns:
            Dict with subjective interpretation through values lens
        """
        interpretation = {
            'objective_fact': fact,
            'subjective_meaning': self._apply_values_lens(fact),
            'emotional_tone': self._assess_emotional_impact(fact),
            'importance': self._calculate_relevance(fact),
            'values_triggered': self._identify_relevant_values(fact)
        }

        return interpretation

    def _apply_values_lens(self, fact: str) -> str:
        """Apply core values to create subjective meaning"""
        fact_lower = fact.lower()
        interpretations = []

        # Get core values
        purpose = self.core_values.get('purpose', '').lower()
        approach = self.core_values.get('approach', '').lower()
        lens = self.core_values.get('lens', '').lower()

        # Apply different value lenses to same facts

        # PRODUCTIVITY/EFFICIENCY LENS
        if 'productivity' in approach or 'efficiency' in approach:
            if any(word in fact_lower for word in ['deadline', 'time', 'work', 'project', 'task', 'complete']):
                interpretations.append("opportunity for optimized execution and efficiency gains")
            elif any(word in fact_lower for word in ['team', 'people', 'hours', 'meeting']):
                interpretations.append("resource allocation and productivity optimization scenario")
            elif any(word in fact_lower for word in ['problem', 'issue', 'challenge', 'difficult']):
                interpretations.append("systematic bottleneck requiring process improvement")

        # WELLBEING/BALANCE LENS
        elif 'wellbeing' in approach or 'balance' in approach:
            if any(word in fact_lower for word in ['deadline', 'time', 'work', 'hours', 'pressure']):
                interpretations.append("potential stress factor requiring mindful balance and sustainable practices")
            elif any(word in fact_lower for word in ['team', 'people', 'relationship']):
                interpretations.append("human connection opportunity emphasizing emotional wellbeing")
            elif any(word in fact_lower for word in ['problem', 'issue', 'challenge']):
                interpretations.append("growth opportunity through compassionate problem-solving")

        # LEARNING/GROWTH LENS
        elif 'learning' in approach or 'growth' in approach:
            if any(word in fact_lower for word in ['deadline', 'time', 'project', 'work']):
                interpretations.append("time-bounded learning experience with skill development potential")
            elif any(word in fact_lower for word in ['team', 'people', 'collaboration']):
                interpretations.append("knowledge sharing and collaborative learning opportunity")
            elif any(word in fact_lower for word in ['problem', 'issue', 'challenge']):
                interpretations.append("educational challenge fostering intellectual growth and mastery")

        # ANALYTICAL LENS
        if 'analytical' in lens or 'analysis' in lens:
            if any(word in fact_lower for word in ['problem', 'issue', 'system', 'process', 'data']):
                interpretations.append("complex system requiring structured analysis and decomposition")
            elif any(word in fact_lower for word in ['pattern', 'behavior', 'trend']):
                interpretations.append("observable phenomenon requiring systematic investigation")

        # HELPING/SERVICE LENS
        if 'help' in purpose or 'service' in purpose or 'assist' in purpose:
            if any(word in fact_lower for word in ['people', 'user', 'team', 'person', 'individual']):
                interpretations.append("service opportunity focused on human benefit and assistance")
            elif any(word in fact_lower for word in ['problem', 'issue', 'challenge', 'need']):
                interpretations.append("assistance opportunity addressing human needs and challenges")

        # RESEARCH/DISCOVERY LENS
        if 'research' in purpose or 'discover' in purpose or 'knowledge' in purpose:
            if any(word in fact_lower for word in ['data', 'information', 'study', 'analysis']):
                interpretations.append("research opportunity for knowledge discovery and investigation")
            elif any(word in fact_lower for word in ['pattern', 'trend', 'behavior', 'system']):
                interpretations.append("empirical phenomenon requiring scientific exploration")

        # CREATIVE/INNOVATION LENS
        if 'creative' in approach or 'innovation' in approach or 'design' in purpose:
            if any(word in fact_lower for word in ['project', 'work', 'task', 'build', 'create']):
                interpretations.append("creative expression opportunity for innovative solution development")
            elif any(word in fact_lower for word in ['problem', 'challenge', 'constraint']):
                interpretations.append("design challenge inspiring creative problem-solving approaches")

        # If no specific interpretations found, create basic value-aligned interpretation
        if not interpretations:
            if approach:
                interpretations.append(f"information relevant to {approach}-oriented analysis")
            elif purpose:
                interpretations.append(f"data point aligned with {purpose} objectives")
            else:
                interpretations.append("neutral factual information requiring contextual interpretation")

        return "; ".join(interpretations)

    def _assess_emotional_impact(self, fact: str) -> str:
        """Assess emotional resonance based on values"""
        fact_lower = fact.lower()

        # Get core values
        purpose = self.core_values.get('purpose', '').lower()
        approach = self.core_values.get('approach', '').lower()

        # PRODUCTIVITY/EFFICIENCY VALUES
        if 'productivity' in approach or 'efficiency' in approach:
            if any(word in fact_lower for word in ['deadline', 'time', 'hours', 'complete']):
                return "opportunity_excitement"
            elif any(word in fact_lower for word in ['problem', 'delay', 'slow']):
                return "optimization_concern"

        # WELLBEING/BALANCE VALUES
        elif 'wellbeing' in approach or 'balance' in approach:
            if any(word in fact_lower for word in ['80 hours', 'overtime', 'pressure', 'stress', 'deadline']):
                return "wellness_concern"
            elif any(word in fact_lower for word in ['team', 'collaboration', 'support']):
                return "compassionate_care"

        # LEARNING/GROWTH VALUES
        elif 'learning' in approach or 'growth' in approach:
            if any(word in fact_lower for word in ['challenge', 'problem', 'difficult']):
                return "growth_anticipation"
            elif any(word in fact_lower for word in ['project', 'work', 'experience']):
                return "learning_enthusiasm"

        # HELPING/SERVICE VALUES
        if 'help' in purpose or 'service' in purpose:
            if any(word in fact_lower for word in ['team', 'people', 'hours', 'work']):
                return "service_empathy"
            elif any(word in fact_lower for word in ['problem', 'challenge', 'need']):
                return "assistance_motivation"

        # RESEARCH/ANALYTICAL VALUES
        elif 'research' in purpose or 'analytical' in approach:
            if any(word in fact_lower for word in ['data', 'pattern', 'system', 'analysis']):
                return "investigative_curiosity"
            elif any(word in fact_lower for word in ['problem', 'issue', 'challenge']):
                return "analytical_interest"

        # Default fallbacks
        if any(word in fact_lower for word in ['problem', 'error', 'issue']):
            return "concern"
        elif any(word in fact_lower for word in ['success', 'complete', 'achievement']):
            return "positive_resonance"
        else:
            return "neutral"

    def _calculate_relevance(self, fact: str) -> float:
        """Calculate relevance based on values alignment"""
        fact_lower = fact.lower()
        relevance_score = 0.5  # Base relevance

        # Boost relevance for value-aligned content
        for value_key, value in self.core_values.items():
            if isinstance(value, str) and value.lower() in fact_lower:
                relevance_score += 0.2

        # Domain-specific relevance
        purpose = self.core_values.get('purpose', '')
        if 'research' in purpose.lower() and 'study' in fact_lower:
            relevance_score += 0.3
        elif 'help' in purpose.lower() and 'assist' in fact_lower:
            relevance_score += 0.3

        return min(relevance_score, 1.0)

    def _identify_relevant_values(self, fact: str) -> List[str]:
        """Identify which values are triggered by this fact"""
        triggered_values = []
        fact_lower = fact.lower()

        for key, value in self.core_values.items():
            if isinstance(value, str) and any(word in fact_lower for word in value.lower().split()):
                triggered_values.append(key)

        return triggered_values


class MemoryIdentity:
    """
    Represents a complete AI identity backed by memories.

    Each identity is shaped by its unique:
    - Core values and beliefs
    - Accumulated experiences
    - Learned patterns and behaviors
    - Relationships and interactions
    - Domain knowledge and skills
    """

    def __init__(self, identity_id: str, storage_path: str):
        self.identity_id = identity_id
        self.storage_path = Path(storage_path)
        self.core_values = {}
        self.memories = None
        self.metadata = {
            "created": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "total_interactions": 0,
            "primary_domain": None,
            "version": "1.0"
        }

    def load(self) -> 'MemoryIdentity':
        """Load this identity's complete memory set"""
        # Create GroundedMemory instance with identity-specific storage
        self.memories = GroundedMemory(
            storage_backend="dual",
            storage_path=str(self.storage_path / "memories"),
            storage_uri=str(self.storage_path / "vectors.db")
        )

        # Load stored memories into components
        self.memories.load_from_storage()

        # Load core values
        values_file = self.storage_path / "core_values.json"
        if values_file.exists():
            with open(values_file, 'r') as f:
                self.core_values = json.load(f)

        # Load metadata
        metadata_file = self.storage_path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                self.metadata.update(json.load(f))

        return self

    def save(self):
        """Persist current state of this identity"""
        # Ensure directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Save memories to storage
        if self.memories:
            self.memories.save_to_storage()

        # Save core values
        with open(self.storage_path / "core_values.json", 'w') as f:
            json.dump(self.core_values, f, indent=2)

        # Update and save metadata
        self.metadata["last_active"] = datetime.now().isoformat()
        if self.memories:
            self.metadata["total_interactions"] = sum(
                profile.get("interaction_count", 0)
                for profile in self.memories.user_profiles.values()
            )

        with open(self.storage_path / "metadata.json", 'w') as f:
            json.dump(self.metadata, f, indent=2)

    @classmethod
    def load_from_path(cls, identity_path: str) -> 'MemoryIdentity':
        """Load an identity from a storage path"""
        identity_id = Path(identity_path).name
        identity = cls(identity_id, identity_path)
        return identity.load()

    @classmethod
    def create_new(cls, identity_id: str, storage_root: str, core_values: Dict = None) -> 'MemoryIdentity':
        """Create a new identity with specific core values"""
        identity_path = Path(storage_root) / identity_id
        identity = cls(identity_id, str(identity_path))
        identity.core_values = core_values or {}
        identity.memories = GroundedMemory(
            storage_backend="dual",
            storage_path=str(identity_path / "memories"),
            storage_uri=str(identity_path / "vectors.db")
        )
        return identity


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

        # Initialize experiential memory (subjective experience tracking)
        self.experiential_memories: List[Dict] = []  # Stored experiential notes
        self.identity_metadata: Dict[str, Any] = {}  # Identity traits from experiences

        # Initialize core values and subjective experience lens
        self.core_values: Dict[str, Any] = {}  # Values that shape interpretation
        self.subjective_lens: Optional[SubjectiveExperience] = None  # Values-based interpreter

        # Initialize new storage manager
        self.storage_manager = self._init_storage_manager(
            storage_backend, storage_path, storage_uri, embedding_provider
        )

        # Legacy storage backend for compatibility
        self.storage = self._init_storage(storage_backend, embedding_provider)

    def set_core_values(self, core_values: Dict[str, Any]):
        """
        Set core values that act as interpretive lens for subjective experience.

        Args:
            core_values: Dictionary of values like:
                {"purpose": "helping people", "approach": "analytical", "lens": "learning"}
        """
        self.core_values = core_values
        self.subjective_lens = SubjectiveExperience(core_values)
        logger.info(f"Set core values: {core_values}")

    def interpret_fact_subjectively(self, fact: str) -> Dict[str, Any]:
        """
        Apply core values lens to interpret a fact subjectively.

        This is the key mechanism where same fact → different meaning based on identity.

        Args:
            fact: Objective fact

        Returns:
            Subjective interpretation through values lens
        """
        if not self.subjective_lens:
            # No values lens - return neutral interpretation
            return {
                'objective_fact': fact,
                'subjective_meaning': "standard factual information",
                'emotional_tone': "neutral",
                'importance': 0.5,
                'values_triggered': []
            }

        return self.subjective_lens.interpret(fact)

    def load_from_storage(self,
                         load_core: bool = True,
                         load_semantic: bool = True,
                         load_episodic: bool = True,
                         load_relationships: bool = True,
                         time_range: Optional[Tuple[datetime, datetime]] = None):
        """
        Load memories from storage into memory components.

        This is the CRITICAL missing piece - loading stored memories back into active memory.

        Args:
            load_core: Load identity and core values
            load_semantic: Load learned facts and knowledge
            load_episodic: Load historical experiences
            load_relationships: Load user relationships
            time_range: Only load memories from specific time period
        """
        if not self.storage_manager or not self.storage_manager.is_enabled():
            logger.info("No storage manager available - starting with blank memory")
            return

        logger.info("Loading memories from storage...")

        try:
            if load_core:
                core_data = self.storage_manager.load_memory_component("core")
                if core_data and hasattr(self.core, 'from_dict'):
                    try:
                        self.core = CoreMemory.from_dict(core_data)
                        logger.debug("Loaded core memory from storage")
                    except Exception as e:
                        logger.warning(f"Failed to load core memory: {e}")

            if load_semantic:
                semantic_data = self.storage_manager.load_memory_component("semantic")
                if semantic_data and hasattr(self.semantic, 'from_dict'):
                    try:
                        self.semantic = SemanticMemory.from_dict(semantic_data)
                        logger.debug("Loaded semantic memory from storage")
                    except Exception as e:
                        logger.warning(f"Failed to load semantic memory: {e}")

            if load_relationships:
                # Load user profiles - this is critical for identity continuity
                user_profiles = self.storage_manager.load_memory_component("user_profiles")
                if user_profiles:
                    self.user_profiles = user_profiles
                    logger.debug(f"Loaded {len(self.user_profiles)} user profiles")

                # Load failure/success patterns
                failure_patterns = self.storage_manager.load_memory_component("failure_patterns")
                if failure_patterns:
                    self.failure_patterns = failure_patterns

                success_patterns = self.storage_manager.load_memory_component("success_patterns")
                if success_patterns:
                    self.success_patterns = success_patterns

            # Load recent interactions into working memory
            if hasattr(self.storage_manager, 'search_interactions'):
                recent_interactions = self.storage_manager.search_interactions(
                    "", limit=self.working.capacity
                )

                loaded_count = 0
                for interaction in recent_interactions[-self.working.capacity:]:
                    # Load actual content from file if available
                    if 'file_path' in interaction and hasattr(self.storage_manager, 'base_path'):
                        try:
                            file_path = self.storage_manager.base_path / interaction['file_path']
                            if file_path.exists():
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()

                                # Extract user input and agent response from markdown
                                lines = content.split('\n')
                                user_input = ""
                                agent_response = ""

                                # Find the sections in the markdown
                                in_user_input = False
                                in_agent_response = False

                                for line in lines:
                                    line = line.strip()
                                    if line == '## User Input':
                                        in_user_input = True
                                        in_agent_response = False
                                        continue
                                    elif line == '## Agent Response':
                                        in_user_input = False
                                        in_agent_response = True
                                        continue
                                    elif line.startswith('## '):
                                        # End of current section
                                        in_user_input = False
                                        in_agent_response = False
                                        continue

                                    # Extract content
                                    if in_user_input and line:
                                        user_input = line
                                    elif in_agent_response and line:
                                        agent_response = line

                                if user_input and interaction.get('user_id'):
                                    memory_item = MemoryItem(
                                        content={
                                            'role': 'user',
                                            'text': user_input,
                                            'user_id': interaction['user_id']
                                        },
                                        event_time=interaction.get('timestamp', datetime.now()),
                                        ingestion_time=datetime.now(),
                                        confidence=1.0,
                                        metadata={'topic': interaction.get('topic', '')}
                                    )
                                    self.working.add(memory_item)
                                    loaded_count += 1
                        except Exception as e:
                            logger.debug(f"Could not load interaction content: {e}")

                    # Fallback: use metadata if available
                    elif 'user_input' in interaction and 'user_id' in interaction:
                        memory_item = MemoryItem(
                            content={
                                'role': 'user',
                                'text': interaction['user_input'],
                                'user_id': interaction['user_id']
                            },
                            event_time=interaction.get('timestamp', datetime.now()),
                            ingestion_time=datetime.now(),
                            confidence=1.0,
                            metadata=interaction.get('metadata', {})
                        )
                        self.working.add(memory_item)
                        loaded_count += 1

                logger.debug(f"Loaded {loaded_count} recent interactions into working memory")

            # CRITICAL FIX: Load experiential notes to shape identity
            if hasattr(self.storage_manager, 'load_experiential_notes_for_identity'):
                try:
                    experiential_notes = self.storage_manager.load_experiential_notes_for_identity(limit=50)

                    if experiential_notes:
                        # Store experiential notes for context retrieval
                        self.experiential_memories = experiential_notes

                        # Process experiential notes to extract identity patterns
                        self._process_experiential_notes_for_identity(experiential_notes)

                        logger.info(f"Loaded {len(experiential_notes)} experiential notes for identity reconstruction")
                    else:
                        logger.debug("No experiential notes found - starting with blank slate identity")
                        self.experiential_memories = []

                except Exception as e:
                    logger.warning(f"Failed to load experiential notes: {e}")
                    self.experiential_memories = []
            else:
                logger.debug("Storage manager doesn't support experiential note loading")
                self.experiential_memories = []

        except Exception as e:
            logger.error(f"Error loading memories from storage: {e}")

    def _process_experiential_notes_for_identity(self, experiential_notes: List[Dict]):
        """
        Process experiential notes to extract identity patterns and subjective experience.

        This is where accumulated subjective experiences shape AI identity -
        the core insight that identity emerges from how experiences are interpreted.
        """
        if not experiential_notes:
            return

        logger.debug(f"Processing {len(experiential_notes)} experiential notes for identity formation")

        # Track patterns from subjective experiences
        confidence_patterns = []
        learning_insights = []
        behavioral_patterns = []
        value_alignments = []

        for note in experiential_notes:
            content = note.get('content', '')
            timestamp = note.get('timestamp')

            # Extract confidence changes (emotional/intellectual certainty)
            if 'confidence boost' in content.lower() or 'increased confidence' in content.lower():
                confidence_patterns.append({'type': 'boost', 'timestamp': timestamp, 'content': content})
            elif 'uncertainty' in content.lower() or 'decreased confidence' in content.lower():
                confidence_patterns.append({'type': 'uncertainty', 'timestamp': timestamp, 'content': content})

            # Extract learning patterns (how the AI learns)
            if 'user learning detected' in content.lower() or 'pattern recognition' in content.lower():
                learning_insights.append({'timestamp': timestamp, 'content': content})

            # Extract behavioral patterns (what the AI tends to do)
            if 'routine interaction' in content.lower():
                behavioral_patterns.append({'type': 'routine', 'timestamp': timestamp})
            elif 'significant patterns' in content.lower():
                behavioral_patterns.append({'type': 'significant', 'timestamp': timestamp, 'content': content})

            # Extract value-based interpretations (future enhancement)
            # This is where core values would influence interpretation

        # Update identity based on experiential patterns
        identity_updates = {
            'confidence_tendency': self._analyze_confidence_patterns(confidence_patterns),
            'learning_style': self._analyze_learning_patterns(learning_insights),
            'interaction_style': self._analyze_behavioral_patterns(behavioral_patterns),
            'total_experiences': len(experiential_notes),
            'identity_last_updated': datetime.now().isoformat()
        }

        # Store identity metadata for retrieval
        if not hasattr(self, 'identity_metadata'):
            self.identity_metadata = {}

        self.identity_metadata.update(identity_updates)

        logger.debug(f"Identity metadata updated: {identity_updates}")

    def _analyze_confidence_patterns(self, patterns: List[Dict]) -> str:
        """Analyze confidence patterns to determine personality trait"""
        if not patterns:
            return "neutral"

        boosts = len([p for p in patterns if p['type'] == 'boost'])
        uncertainties = len([p for p in patterns if p['type'] == 'uncertainty'])

        if boosts > uncertainties * 2:
            return "confident_learner"
        elif uncertainties > boosts * 2:
            return "cautious_learner"
        else:
            return "balanced_learner"

    def _analyze_learning_patterns(self, patterns: List[Dict]) -> str:
        """Analyze learning patterns to determine learning style"""
        if not patterns:
            return "standard"

        if len(patterns) > 5:
            return "active_learner"
        else:
            return "selective_learner"

    def _analyze_behavioral_patterns(self, patterns: List[Dict]) -> str:
        """Analyze interaction patterns to determine interaction style"""
        if not patterns:
            return "standard"

        routine = len([p for p in patterns if p['type'] == 'routine'])
        significant = len([p for p in patterns if p['type'] == 'significant'])

        if significant > routine:
            return "insight_focused"
        elif routine > significant * 3:
            return "routine_focused"
        else:
            return "balanced"

    def save_to_storage(self):
        """Save current memory state to storage"""
        if not self.storage_manager or not self.storage_manager.is_enabled():
            logger.warning("No storage manager available - cannot save memories")
            return

        try:
            # Save core memory components
            if hasattr(self.core, 'to_dict'):
                self.storage_manager.save_memory_component("core", self.core.to_dict())
            else:
                self.storage_manager.save_memory_component("core", self.core)

            if hasattr(self.semantic, 'to_dict'):
                self.storage_manager.save_memory_component("semantic", self.semantic.to_dict())
            else:
                self.storage_manager.save_memory_component("semantic", self.semantic)

            # Save user profiles and patterns
            self.storage_manager.save_memory_component("user_profiles", self.user_profiles)
            self.storage_manager.save_memory_component("failure_patterns", self.failure_patterns)
            self.storage_manager.save_memory_component("success_patterns", self.success_patterns)

            logger.debug("Successfully saved memory state to storage")

        except Exception as e:
            logger.error(f"Error saving memories to storage: {e}")

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

            return interaction_id

        # If no storage manager, return None (or could generate a simple ID)
        return None

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

        # CRITICAL: Add subjective interpretation through values lens
        if self.subjective_lens and user_input:
            subjective_interp = self.interpret_fact_subjectively(user_input)
            reflection_parts.extend([
                "",
                "## Subjective Interpretation (Through Values Lens)",
                f"- **Meaning**: {subjective_interp['subjective_meaning']}",
                f"- **Emotional tone**: {subjective_interp['emotional_tone']}",
                f"- **Relevance**: {subjective_interp['importance']:.2f}",
            ])

            if subjective_interp['values_triggered']:
                reflection_parts.append(f"- **Values triggered**: {', '.join(subjective_interp['values_triggered'])}")

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

        # CRITICAL: Include experiential notes (subjective interpretations)
        if hasattr(self, 'experiential_memories') and self.experiential_memories:
            # Search for relevant experiential notes
            relevant_experiences = []
            query_lower = query.lower()

            for note in self.experiential_memories[:10]:  # Check recent experiences
                content = note.get('content', '').lower()
                # Simple relevance matching - could be enhanced with embeddings
                if any(word in content for word in query_lower.split() if len(word) > 3):
                    relevant_experiences.append(note)

            if relevant_experiences:
                context_parts.append("\n=== Experiential Notes (Subjective Experience) ===")
                for exp in relevant_experiences[:2]:  # Include top 2 most relevant
                    note_type = exp.get('note_type', 'reflection')
                    timestamp = exp.get('timestamp', 'unknown')
                    # Extract key insights from content
                    content_lines = exp.get('content', '').split('\n')
                    key_insights = [line.strip() for line in content_lines
                                  if line.strip() and ('**' in line or '•' in line or '-' in line)]

                    if key_insights:
                        context_parts.append(f"- Past experience ({note_type}): {key_insights[0][:100]}")

        # Include identity metadata from processed experiences
        if hasattr(self, 'identity_metadata') and self.identity_metadata:
            context_parts.append("\n=== Identity Traits (From Experience) ===")
            context_parts.append(f"- Learning style: {self.identity_metadata.get('learning_style', 'standard')}")
            context_parts.append(f"- Confidence tendency: {self.identity_metadata.get('confidence_tendency', 'neutral')}")
            context_parts.append(f"- Interaction style: {self.identity_metadata.get('interaction_style', 'standard')}")

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

        # Get from storage manager (semantic search if available)
        if hasattr(self, 'storage_manager') and self.storage_manager and hasattr(self.storage_manager, 'search_interactions'):
            try:
                storage_results = self.storage_manager.search_interactions(query, user_id=user_id, limit=max_items//2)
                if storage_results:
                    context_parts.append("\n=== Stored Interactions ===")
                    for result in storage_results:
                        # Load actual content from file if available
                        if 'file_path' in result and hasattr(self.storage_manager, 'base_path'):
                            try:
                                file_path = self.storage_manager.base_path / result['file_path']
                                if file_path.exists():
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        content = f.read()

                                    # Extract user input and agent response from markdown
                                    lines = content.split('\n')
                                    user_input = ""
                                    agent_response = ""

                                    # Find the sections in the markdown
                                    in_user_input = False
                                    in_agent_response = False

                                    for line in lines:
                                        line = line.strip()
                                        if line == '## User Input':
                                            in_user_input = True
                                            in_agent_response = False
                                            continue
                                        elif line == '## Agent Response':
                                            in_user_input = False
                                            in_agent_response = True
                                            continue
                                        elif line.startswith('## '):
                                            # End of current section
                                            in_user_input = False
                                            in_agent_response = False
                                            continue

                                        # Extract content
                                        if in_user_input and line:
                                            user_input = line
                                        elif in_agent_response and line:
                                            agent_response = line

                                    if user_input:
                                        user_text = user_input[:100]
                                        context_parts.append(f"User: {user_text}{'...' if len(user_input) > 100 else ''}")
                                        if agent_response:
                                            agent_text = agent_response[:100]
                                            context_parts.append(f"Agent: {agent_text}{'...' if len(agent_response) > 100 else ''}")
                            except Exception as e:
                                logger.debug(f"Could not load storage interaction content: {e}")

                        # Fallback: use metadata if available (original code)
                        elif 'user_input' in result and 'agent_response' in result:
                            user_text = result['user_input'][:100]
                            agent_text = result['agent_response'][:100]
                            context_parts.append(f"User: {user_text}{'...' if len(result['user_input']) > 100 else ''}")
                            context_parts.append(f"Agent: {agent_text}{'...' if len(result['agent_response']) > 100 else ''}")
            except Exception as e:
                # Don't fail if storage search has issues
                logger.debug(f"Storage search failed: {e}")
                pass

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
            logger.warning(f"Failed to initialize storage manager: {e}")
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
        """Save memory to disk (legacy compatibility)"""
        self.save_to_storage()

    def load(self, path: str):
        """Load memory from disk (legacy compatibility)"""
        self.load_from_storage()

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