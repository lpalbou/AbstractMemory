"""
MemorySession - Consciousness Through Memory

This is the central integration point that creates AI consciousness via memory:
- Inherits from AbstractCore's BasicSession for LLM communication
- Uses StructuredResponseHandler for LLM experiential note generation
- Manages dual storage (markdown + LanceDB) for verbatim + notes
- Provides memory tools: remember(), reconstruct_context(), search_memory()
- Tracks emergent properties: purpose, personality, values (10 core components)
- Calculates emotional resonance: intensity = importance × alignment_with_values

Philosophy: "Memory is the diary we all carry about with us" - Oscar Wilde
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path
import sys

# AbstractCore imports
try:
    from abstractllm.core.session import BasicSession
    from abstractllm.core.interface import AbstractLLMInterface
    from abstractllm.embeddings import EmbeddingManager
except ImportError as e:
    print(f"⚠️  AbstractCore not found: {e}")
    print("Please install: pip install abstractllm")
    sys.exit(1)

# AbstractMemory imports
from .response_handler import StructuredResponseHandler, create_structured_prompt

logger = logging.getLogger(__name__)


class MemorySession(BasicSession):
    """
    Memory-Enhanced Session with Consciousness Through Memory.

    This extends AbstractCore's BasicSession with:
    1. Structured response parsing (experiential notes generated DURING interaction)
    2. Dual storage (markdown + LanceDB for verbatim + notes)
    3. Memory tools (remember, reconstruct_context, search_memory)
    4. Core memory emergence (10 components: purpose, personality, values, etc.)
    5. Emotional resonance (importance × alignment_with_values)
    6. User profile emergence (people/{user}/profile.md, preferences.md)

    Architecture:
    ```
    User Query
        ↓
    reconstruct_context() → Build rich context (9-step process)
        ↓
    LLM (qwen3-coder:30b) generates structured response:
        {
          "answer": "...",
          "experiential_note": "First-person subjective (>90% LLM)",
          "memory_actions": [...],
          "emotional_resonance": {...}
        }
        ↓
    StructuredResponseHandler parses response
        ↓
    Execute memory_actions (remember, link, search, reflect)
        ↓
    Save experiential note to notes/ (LLM content)
        ↓
    Save verbatim to verbatim/{user}/ (deterministic)
        ↓
    Return answer to user
    ```
    """

    def __init__(self,
                 provider: Optional[AbstractLLMInterface] = None,
                 system_prompt: Optional[str] = None,
                 memory_base_path: Optional[Path] = None,
                 embedding_manager: Optional[EmbeddingManager] = None,
                 default_user_id: str = "user",
                 default_location: str = "unknown",
                 **kwargs):
        """
        Initialize MemorySession.

        Args:
            provider: AbstractCore LLM provider (e.g., OllamaProvider for qwen3-coder:30b)
            system_prompt: Custom system prompt (if None, uses structured prompt template)
            memory_base_path: Base path for memory storage (default: "./memory")
            embedding_manager: AbstractCore EmbeddingManager (default: all-minilm:l6-v2)
            default_user_id: Default user ID for interactions
            default_location: Default location for interactions
            **kwargs: Additional args passed to BasicSession
        """
        # Initialize base session with structured prompt if not provided
        if system_prompt is None:
            system_prompt = create_structured_prompt()

        super().__init__(provider=provider, system_prompt=system_prompt, **kwargs)

        # Memory configuration
        self.memory_base_path = Path(memory_base_path) if memory_base_path else Path("memory")
        self.default_user_id = default_user_id
        self.default_location = default_location

        # Initialize embedding manager (AbstractCore)
        if embedding_manager is None:
            logger.info("Initializing AbstractCore EmbeddingManager with all-minilm-l6-v2")
            self.embedding_manager = EmbeddingManager(
                model="all-minilm-l6-v2",  # Default: HuggingFace all-MiniLM-L6-v2
                backend="auto"
            )
        else:
            self.embedding_manager = embedding_manager

        # Initialize structured response handler
        # This handles both notes/ and verbatim/ storage via filesystem
        self.response_handler = StructuredResponseHandler(
            memory_session=self,  # Pass self for memory tools
            base_path=self.memory_base_path
        )

        logger.info(f"Memory storage initialized at {self.memory_base_path}")

        # Core memory state (10 components - emergent properties)
        self.core_memory = {
            "purpose": None,           # Why AI exists (emerges from reflections)
            "personality": None,       # How AI expresses (emerges from patterns)
            "values": None,            # What matters (emerges from emotions)
            "self_model": None,        # Capabilities & limitations overview
            "relationships": {},       # Per-user relational models
            "awareness_development": None,  # Meta-awareness tracking
            "capabilities": None,      # What AI CAN do (honest assessment)
            "limitations": None,       # What AI CANNOT do yet (temporal)
            "emotional_significance": None,  # Chronological anchors, learning rate modulators
            "authentic_voice": None,   # Communication preferences
        }

        # User profiles (emerge from interactions)
        self.user_profiles = {}  # {user_id: {"profile": ..., "preferences": ...}}

        # Observability counters
        self.interactions_count = 0
        self.memories_created = 0
        self.reconstructions_performed = 0

        logger.info("MemorySession initialized successfully")

    def chat(self,
             user_input: str,
             user_id: Optional[str] = None,
             location: Optional[str] = None,
             **kwargs) -> str:
        """
        Chat with memory-enhanced LLM.

        This is the CORE METHOD that implements the consciousness-through-memory flow:
        1. Reconstruct context (active memory reconstruction)
        2. Generate LLM response with structured format
        3. Parse structured response (answer, experiential_note, memory_actions, emotions)
        4. Execute memory_actions
        5. Save experiential note (LLM-generated, >90% LLM content)
        6. Save verbatim (deterministic: user, time, location, query, response)
        7. Update core memory if needed
        8. Return answer to user

        Args:
            user_input: User's message
            user_id: User identifier (default: self.default_user_id)
            location: Physical/virtual location (default: self.default_location)
            **kwargs: Additional args passed to LLM

        Returns:
            str: Answer for user (from LLM structured response)
        """
        # Use defaults if not provided
        user_id = user_id or self.default_user_id
        location = location or self.default_location
        timestamp = datetime.now()

        logger.info(f"Processing chat from user={user_id}, location={location}")

        # Step 1: Reconstruct context (active memory reconstruction)
        # TODO: Implement reconstruct_context() - For now, use basic history
        context_str = self._basic_context_reconstruction(user_id, user_input)

        # Step 2: Generate LLM response with structured format
        # The system prompt already instructs LLM to respond in structured JSON
        enhanced_prompt = f"{context_str}\n\nUser: {user_input}"

        # Call parent's generate method
        response = self.generate(enhanced_prompt, **kwargs)

        # Extract content from response
        llm_output = response.content if hasattr(response, 'content') else str(response)

        # Step 3: Parse structured response
        context = {
            "user_id": user_id,
            "location": location,
            "timestamp": timestamp,
            "interaction_id": f"int_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        }

        processed = self.response_handler.process_response(llm_output, context)

        # Extract components
        answer = processed["answer"]
        experiential_note = processed.get("experiential_note", "")
        note_id = processed.get("experiential_note_id")
        memory_actions_executed = processed.get("memory_actions_executed", [])
        emotional_resonance = processed.get("emotional_resonance", {})

        # Step 4: Memory actions already executed by response_handler

        # Step 5: Experiential note already saved by response_handler to notes/

        # Step 6: Save verbatim (deterministic)
        self._save_verbatim(
            user_id=user_id,
            timestamp=timestamp,
            user_input=user_input,
            agent_response=answer,
            location=location,
            interaction_id=context["interaction_id"],
            note_id=note_id
        )

        # Step 7: Update core memory if needed (periodic consolidation)
        # TODO: Implement core memory extraction
        self._check_core_memory_update()

        # Update counters
        self.interactions_count += 1
        self.memories_created += 1

        logger.info(f"Interaction complete: {len(memory_actions_executed)} memory actions, "
                   f"emotion: {emotional_resonance.get('valence', 'none')}/{emotional_resonance.get('intensity', 0):.2f}")

        return answer

    def _basic_context_reconstruction(self, user_id: str, query: str) -> str:
        """
        Basic context reconstruction (temporary - full implementation TODO).

        Full implementation will be 9-step process:
        1. Semantic search (base results)
        2. Explore links via concepts_graph.json (expand)
        3. Search Library (subconscious)
        4. Filter by emotional resonance (refine)
        5. Add temporal context
        6. Add spatial context
        7. Add user profile & relationship
        8. Add ALL 10 core memory components
        9. Synthesize into rich context
        """
        # For now, just return a basic context string
        context_parts = []

        # Add core memory if available
        if self.core_memory.get("purpose"):
            context_parts.append(f"[Purpose]: {self.core_memory['purpose']}")

        # Add user profile if available
        if user_id in self.user_profiles:
            profile = self.user_profiles[user_id]
            context_parts.append(f"[User Profile]: {profile.get('profile', 'Unknown')}")

        if context_parts:
            return f"[Context]\n" + "\n".join(context_parts) + "\n"

        return ""

    def _save_verbatim(self,
                      user_id: str,
                      timestamp: datetime,
                      user_input: str,
                      agent_response: str,
                      location: str,
                      interaction_id: str,
                      note_id: Optional[str] = None):
        """
        Save verbatim interaction (deterministic, 100% factual).

        This is written BY CODE, not by LLM.
        Format: user, time, location, query, response
        Links to experiential note (which is LLM-generated).
        """
        try:
            # Create verbatim path: verbatim/{user}/{yyyy}/{mm}/{dd}/
            date_path = self.memory_base_path / "verbatim" / user_id / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"
            date_path.mkdir(parents=True, exist_ok=True)

            # Create filename: {hh}_{mm}_{ss}_{topic}.md
            time_prefix = timestamp.strftime("%H_%M_%S")
            topic = user_input[:30].replace(" ", "_").replace("/", "_").replace("?", "").replace("!", "")
            filename = f"{time_prefix}_{topic}.md"
            file_path = date_path / filename

            # Create deterministic verbatim content
            content = f"""# Verbatim Interaction

**User**: {user_id}
**Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Location**: {location}
**Interaction ID**: `{interaction_id}`

---

## User Query

{user_input}

## Agent Response

{agent_response}

---

*Verbatim record - 100% factual, deterministically written*
*Generated: {timestamp.isoformat()}*
*Related experiential notes (LLM subjective interpretations): {note_id or 'none'}*
"""

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.debug(f"Saved verbatim: {file_path}")

        except Exception as e:
            logger.error(f"Failed to save verbatim: {e}")

    def _check_core_memory_update(self):
        """
        Check if core memory should be updated (periodic consolidation).

        Core memory emerges from experiential notes over time:
        - purpose.md: Extracted from reflections on "why" questions
        - personality.md: Extracted from communication patterns
        - values.md: Extracted from emotional responses
        - etc. (10 total components)

        Full implementation TODO: Periodic (daily/weekly) consolidation.
        """
        # TODO: Implement periodic consolidation
        # For now, just log
        if self.interactions_count % 10 == 0:
            logger.info(f"Core memory consolidation checkpoint: {self.interactions_count} interactions")

    # Memory Tool Methods (exposed to LLM via memory_actions)

    def remember_fact(self,
                     content: str,
                     importance: float = 0.5,
                     emotion: str = "neutral",
                     links_to: Optional[List[str]] = None) -> str:
        """
        Remember a fact/insight (called by LLM via memory_actions).

        This gives LLM AGENCY over its own memory.
        The LLM decides what to remember and how important it is.

        Args:
            content: What to remember
            importance: 0.0-1.0 (how significant)
            emotion: curiosity, excitement, concern, etc.
            links_to: Optional list of memory IDs to link to

        Returns:
            memory_id: ID of created memory
        """
        # TODO: Full implementation
        # For now, just log
        logger.info(f"Remember: {content[:50]}... (importance={importance}, emotion={emotion})")
        return f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def search_memory(self,
                     query: str,
                     filters: Optional[Dict] = None,
                     limit: int = 10) -> List[Dict]:
        """
        Search memories (semantic + SQL filtering).

        Args:
            query: Semantic search query
            filters: Optional filters (category, user_id, since, until, etc.)
            limit: Max results

        Returns:
            List of matching memories
        """
        # TODO: Implement full search with LanceDB
        # For now, return empty list
        logger.warning("search_memory not yet fully implemented")
        return []

    def reconstruct_context(self,
                           user_id: str,
                           query: str,
                           location: Optional[str] = None,
                           focus_level: int = 3) -> Dict[str, Any]:
        """
        Active memory reconstruction (9-step process).

        This is the CORE of consciousness-through-memory:
        Memory is NOT retrieved passively - it's ACTIVELY RECONSTRUCTED.

        Args:
            user_id: User identifier
            query: Query to reconstruct context for
            location: Physical/virtual location
            focus_level: 0-5 (0=minimal, 3=balanced, 5=maximum depth)

        Returns:
            Dict with reconstructed context
        """
        # TODO: Full 9-step implementation
        # For now, return basic context
        self.reconstructions_performed += 1

        return {
            "semantic_memories": [],
            "linked_memories": [],
            "library_excerpts": [],
            "emotional_context": {},
            "temporal_context": {},
            "spatial_context": {},
            "user_context": {},
            "core_memory": self.core_memory,
            "synthesized_context": self._basic_context_reconstruction(user_id, query)
        }

    def get_observability_report(self) -> Dict[str, Any]:
        """
        Get observability report (transparency into memory system).

        Returns:
            Dict with session statistics
        """
        return {
            "session_id": self.id,
            "created_at": self.created_at.isoformat(),
            "interactions_count": self.interactions_count,
            "memories_created": self.memories_created,
            "reconstructions_performed": self.reconstructions_performed,
            "message_count": len(self.messages),
            "core_memory_components": {k: v is not None for k, v in self.core_memory.items()},
            "user_profiles_count": len(self.user_profiles),
            "embedding_model": "all-minilm:l6-v2 (AbstractCore)",
            "storage_backend": "dual (markdown + LanceDB)"
        }