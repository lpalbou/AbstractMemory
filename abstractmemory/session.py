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
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
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
from .storage import LanceDBStorage
from .emotions import calculate_emotional_resonance  # Only formula - LLM does cognitive assessment
from .temporal_anchoring import (
    is_anchor_event,
    create_temporal_anchor,
    get_temporal_anchors
)
from .memory_structure import initialize_memory_structure
from .working_memory import WorkingMemoryManager
from .episodic_memory import EpisodicMemoryManager
from .semantic_memory import SemanticMemoryManager
from .library_capture import LibraryCapture

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
                 index_verbatims: bool = False,
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
            index_verbatims: If True, index verbatims in LanceDB (default: False)
            **kwargs: Additional args passed to BasicSession
        """
        # Initialize base session with structured prompt if not provided
        if system_prompt is None:
            system_prompt = create_structured_prompt()

        # Initialize BasicSession WITHOUT tools first (we'll register them after)
        super().__init__(provider=provider, system_prompt=system_prompt, **kwargs)

        # Memory configuration
        self.memory_base_path = Path(memory_base_path) if memory_base_path else Path("memory")
        self.default_user_id = default_user_id
        self.default_location = default_location
        self.index_verbatims = index_verbatims  # Phase 1: Configurable verbatim indexing

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

        # Initialize LanceDB storage for semantic search
        try:
            lancedb_path = self.memory_base_path / "lancedb"
            self.lancedb_storage = LanceDBStorage(
                db_path=lancedb_path,
                embedding_model="all-minilm-l6-v2"
            )
            logger.info(f"LanceDB storage initialized at {lancedb_path}")
        except Exception as e:
            logger.warning(f"LanceDB storage initialization failed: {e}")
            self.lancedb_storage = None

        logger.info(f"Memory storage initialized at {self.memory_base_path}")

        # Initialize complete memory filesystem structure (all components)
        try:
            init_status = initialize_memory_structure(self.memory_base_path, user_id=self.default_user_id)
            logger.info(f"Memory structure initialized: {init_status}")
        except Exception as e:
            logger.warning(f"Memory structure initialization had issues: {e}")

        # Initialize Library Capture (Phase 5: Subconscious Memory)
        # CRITICAL: Uses DUAL STORAGE (markdown + LanceDB)
        try:
            self.library = LibraryCapture(
                library_base_path=self.memory_base_path,
                embedding_manager=self.embedding_manager,
                lancedb_storage=self.lancedb_storage  # Dual storage requirement
            )
            logger.info("Library capture system initialized (Phase 5) with dual storage")
        except Exception as e:
            logger.warning(f"Library capture initialization failed: {e}")
            self.library = None

        # Core memory state (10 components - emergent properties)
        self.core_memory = {
            "purpose": None,           # Why AI exists (emerges from reflections)
            "personality": None,       # How AI expresses (emerges from patterns)
            "values": None,  # What matters (emerges from LLM emotional assessments over time)
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

        # Observability counters (Phase 1: Load from persistent metadata)
        self.session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S_%f")
        self.session_start_time = datetime.now()
        self.interactions_count = 0
        self.memories_created = 0
        self.reconstructions_performed = 0

        # Load persistent session metadata (Phase 1: Session continuity)
        self._load_session_metadata()

        # Core memory consolidation tracking
        self.consolidation_frequency = 10  # Consolidate every N interactions
        self.last_consolidation_count = 0

        # Initialize consolidation scheduler (daily/weekly/monthly)
        from .consolidation_scheduler import ConsolidationScheduler
        self.scheduler = ConsolidationScheduler(self)

        # Initialize enhanced memory managers (Phase 4)
        self.working_memory = WorkingMemoryManager(self.memory_base_path)
        self.episodic_memory = EpisodicMemoryManager(self.memory_base_path)
        self.semantic_memory = SemanticMemoryManager(self.memory_base_path)
        logger.info("Enhanced memory managers (working/episodic/semantic) initialized")

        # Initialize user profile manager (Phase 6)
        from .user_profile_extraction import UserProfileManager
        self.user_profile_manager = UserProfileManager(
            memory_base_path=self.memory_base_path,
            llm_provider=self.provider  # Use same LLM for profile extraction
        )
        self.profile_update_threshold = 10  # Update profile every N interactions per user
        self.user_interaction_counts = {}  # Track interactions per user
        logger.info("User profile manager initialized (Phase 6)")

        # Register memory tools with AbstractCore (Phase: Tool Integration)
        self._register_memory_tools()

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
        # Phase 1: Use full 9-step reconstruction instead of basic context
        try:
            context_data = self.reconstruct_context(
                user_id=user_id,
                query=user_input,
                location=location,
                focus_level=3  # Medium depth (0=minimal, 5=exhaustive)
            )
            context_str = context_data["synthesized_context"]
            self.reconstructions_performed += 1
            memories_count = len(context_data.get('memories_retrieved', []))
            memories_available = context_data.get('total_memories_available', 0)
            context_tokens = context_data.get('context_tokens', 0)
            logger.info(f"📝 Injecting {memories_count} memories ({context_tokens} tokens) into LLM prompt for context-aware response")
        except Exception as e:
            logger.error(f"Full reconstruction failed, falling back to basic context: {e}")
            context_str = self._basic_context_reconstruction(user_id, user_input)

        # Step 2: Generate LLM response with structured format
        # The system prompt already instructs LLM to respond in structured JSON
        enhanced_prompt = f"{context_str}\n\nUser: {user_input}"

        # Estimate total prompt size for user visibility
        total_prompt_tokens = len(enhanced_prompt) // 4
        logger.info(f"Generating LLM response (prompt: ~{total_prompt_tokens} tokens)...")

        # Call parent's generate method
        response = self.generate(enhanced_prompt, **kwargs)

        logger.info(f"LLM response received")

        # Extract content from response
        llm_output = response.content if hasattr(response, 'content') else str(response)

        # Step 3: Parse structured response
        # NOTE: When tools are enabled, LLM might respond directly without JSON structure
        # In that case, use the raw response as the answer
        context = {
            "user_id": user_id,
            "location": location,
            "timestamp": timestamp,
            "interaction_id": f"int_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        }

        try:
            processed = self.response_handler.process_response(llm_output, context)
            answer = processed["answer"]
        except (KeyError, ValueError) as e:
            # Fallback: If response doesn't match expected structure (e.g., when using tools),
            # use the raw response as the answer
            logger.warning(f"Response parsing failed ({e}), using raw response as answer")
            answer = llm_output
            processed = {
                "answer": llm_output,
                "experiential_note": "",
                "experiential_note_id": None,
                "memory_actions_executed": [],
                "emotional_resonance": {"valence": "neutral", "intensity": 0.5, "reason": ""},
                "unresolved_questions": []
            }
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

        # Step 8: Update enhanced memory types (Phase 4)
        self._update_enhanced_memories(
            user_id=user_id,
            user_input=user_input,
            answer=answer,
            emotional_resonance=emotional_resonance,
            unresolved=processed.get("unresolved_questions", [])
        )

        # Step 9: Check for user profile update (Phase 6)
        self._check_user_profile_update(user_id)

        # Update counters
        self.interactions_count += 1
        self.memories_created += 1

        # Phase 1: Persist session metadata for continuity
        self._persist_session_metadata()

        logger.info(f"Interaction complete: {len(memory_actions_executed)} memory actions, "
                   f"emotion: {emotional_resonance.get('valence', 'none')}/{emotional_resonance.get('intensity', 0):.2f}")

        return answer

    def trigger_consolidation(self, mode: str = "manual") -> Dict[str, bool]:
        """
        Manually trigger core memory consolidation.

        This forces immediate extraction of identity components from experiential notes,
        regardless of the automatic consolidation schedule.

        Args:
            mode: Consolidation mode - "manual", "daily", "weekly", or "periodic"

        Returns:
            Dict with update status for all 10 core components
            Example: {"purpose_updated": True, "values_updated": False, ...}

        Example:
            >>> session = MemorySession(...)
            >>> # After some interactions...
            >>> results = session.trigger_consolidation()
            >>> print(f"Updated {sum(results.values())}/11 components")
        """
        logger.info(f"🔄 Manual consolidation triggered (mode={mode})")

        try:
            from .core_memory_extraction import consolidate_core_memory
            results = consolidate_core_memory(self, mode=mode)

            # Log results
            updated_count = sum(1 for v in results.values() if v)
            updated_components = [k.replace("_updated", "") for k, v in results.items() if v]

            if updated_count > 0:
                logger.info(f"✅ Consolidation complete: {updated_count}/11 components updated")
                logger.info(f"   Updated: {', '.join(updated_components)}")
            else:
                logger.info(f"   No significant changes detected in core memory")

            return results

        except Exception as e:
            logger.error(f"❌ Consolidation failed: {e}")
            logger.exception(e)
            return {}

    def _register_memory_tools(self):
        """
        Register memory tools with AbstractCore for LLM agency.

        This gives the LLM the ability to:
        - Decide what to remember (remember_fact)
        - Search its own memory (search_memories)
        - Reflect on topics (reflect_on)
        - Capture documents (capture_document, search_library)
        - Control context reconstruction (reconstruct_context)

        Tools are registered with the parent BasicSession, making them
        available to the LLM during generation.
        """
        try:
            from .tools import create_memory_tools

            # Create callable tool functions (NOT ToolDefinitions)
            memory_tool_functions = create_memory_tools(self)

            # Register them using parent's _register_tools method
            # This will convert callables to ToolDefinitions and register globally
            if memory_tool_functions:
                self.tools = self._register_tools(memory_tool_functions)
                logger.info(f"Registered {len(self.tools)} memory tools with AbstractCore")
            else:
                logger.warning("No memory tools created")

        except ImportError as e:
            logger.warning(f"Could not register memory tools: {e}")
            logger.warning("Memory tools will not be available to LLM")
        except Exception as e:
            logger.error(f"Failed to register memory tools: {e}")

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

            # Phase 1: Index verbatim in LanceDB if enabled
            if self.index_verbatims and self.lancedb_storage:
                self._index_verbatim_in_lancedb(
                    interaction_id=interaction_id,
                    timestamp=timestamp,
                    user_id=user_id,
                    location=location,
                    user_input=user_input,
                    agent_response=agent_response,
                    topic=topic,
                    file_path=file_path,
                    note_id=note_id
                )

        except Exception as e:
            logger.error(f"Failed to save verbatim: {e}")

    def _index_verbatim_in_lancedb(self,
                                   interaction_id: str,
                                   timestamp: datetime,
                                   user_id: str,
                                   location: str,
                                   user_input: str,
                                   agent_response: str,
                                   topic: str,
                                   file_path: Path,
                                   note_id: Optional[str] = None):
        """
        Index verbatim interaction in LanceDB for semantic search.

        This is separate from markdown storage and only called if index_verbatims=True.

        Args:
            interaction_id: Unique interaction ID
            timestamp: When interaction occurred
            user_id: User identifier
            location: Physical/virtual location
            user_input: User's query
            agent_response: AI's response
            topic: Extracted topic from query
            file_path: Path to markdown file
            note_id: Related experiential note ID
        """
        try:
            verbatim_data = {
                "id": interaction_id,
                "timestamp": timestamp,
                "user_id": user_id,
                "location": location,
                "user_input": user_input,
                "agent_response": agent_response,
                "topic": topic,
                "category": "conversation",
                "confidence": 1.0,  # Verbatim = 100% factual
                "tags": json.dumps([]),  # Future: LLM-generated tags
                "file_path": str(file_path),
                "metadata": json.dumps({
                    "note_id": note_id,
                    "word_count_user": len(user_input.split()),
                    "word_count_agent": len(agent_response.split()),
                    "session_id": self.session_id
                })
            }

            self.lancedb_storage.add_verbatim(verbatim_data)
            logger.info(f"Indexed verbatim in LanceDB: {interaction_id}")

        except Exception as e:
            logger.error(f"Failed to index verbatim in LanceDB: {e}")

    def _load_session_metadata(self):
        """
        Load persistent session metadata to restore counters across relaunches.

        Phase 1: Session Continuity
        - Loads total_interactions, total_memories, total_reconstructions
        - Adds current session to history
        - Ensures AI remembers previous sessions
        """
        metadata_path = self.memory_base_path / ".session_metadata.json"

        try:
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Restore persistent counters
                self.interactions_count = data.get("total_interactions", 0)
                self.memories_created = data.get("total_memories", 0)
                self.reconstructions_performed = data.get("total_reconstructions", 0)

                logger.info(f"Loaded session metadata: {self.interactions_count} interactions, "
                           f"{self.memories_created} memories, {self.reconstructions_performed} reconstructions")
            else:
                logger.info("No previous session metadata found - starting fresh")

        except Exception as e:
            logger.warning(f"Failed to load session metadata: {e}")

    def _persist_session_metadata(self):
        """
        Persist session metadata to disk for continuity across relaunches.

        Called after each interaction to ensure counters are never lost.
        """
        metadata_path = self.memory_base_path / ".session_metadata.json"

        try:
            # Load existing data if available
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"sessions": []}

            # Update totals
            data["total_interactions"] = self.interactions_count
            data["total_memories"] = self.memories_created
            data["total_reconstructions"] = self.reconstructions_performed
            data["last_updated"] = datetime.now().isoformat()

            # Update or add current session
            sessions = data.get("sessions", [])
            current_session = {
                "session_id": self.session_id,
                "start_time": self.session_start_time.isoformat(),
                "last_activity": datetime.now().isoformat(),
                "interactions_this_session": self.interactions_count - data.get("total_interactions_at_start", 0)
            }

            # Find and update current session or append new
            session_found = False
            for i, sess in enumerate(sessions):
                if sess["session_id"] == self.session_id:
                    sessions[i] = current_session
                    session_found = True
                    break

            if not session_found:
                sessions.append(current_session)
                # Track interactions at session start for delta calculation
                if "total_interactions_at_start" not in data:
                    data["total_interactions_at_start"] = self.interactions_count - 1

            data["sessions"] = sessions[-10:]  # Keep last 10 sessions

            # Write atomically
            temp_path = metadata_path.with_suffix('.json.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            temp_path.replace(metadata_path)

            logger.debug(f"Persisted session metadata: {self.interactions_count} interactions")

        except Exception as e:
            logger.error(f"Failed to persist session metadata: {e}")

    def _update_enhanced_memories(self,
                                  user_id: str,
                                  user_input: str,
                                  answer: str,
                                  emotional_resonance: Dict[str, Any],
                                  unresolved: List[str]):
        """
        Update enhanced memory types (Phase 4): working, episodic, semantic.

        This is called after each interaction to:
        - Update working memory (context, tasks, unresolved questions)
        - Add to episodic memory if significant (key moments, discoveries)
        - Update semantic memory (concepts, insights)

        Args:
            user_id: User identifier
            user_input: User's query
            answer: AI's response
            emotional_resonance: Emotional data from response
            unresolved: List of unresolved questions from LLM
        """
        try:
            # Phase 1: Update SPECIALIZED working memory files first
            # These are the components that current_context.md will reference

            # 1. Update unresolved questions (already working ✅)
            for question in unresolved:
                self.working_memory.add_unresolved(
                    question=question,
                    context=f"From interaction about: {user_input[:50]}..."
                )

            # 2. Update current_references.md with accessed memories
            # TODO Phase 2: Track which memories were retrieved during reconstruction
            # if hasattr(self, '_last_reconstruction_memories'):
            #     for mem_id in self._last_reconstruction_memories:
            #         self.working_memory.add_reference(mem_id)

            # 3. Extract and update current_tasks.md
            # TODO Phase 2: LLM extracts tasks from conversation
            # if self._has_task_indicators(user_input, answer):
            #     tasks = self._extract_tasks(user_input, answer)
            #     for task in tasks:
            #         self.working_memory.add_task(task)

            # 4. Update current_context.md (MASTER synthesis)
            # TODO Phase 2: LLM synthesizes conversation into reflection
            # For now: minimal summary until LLM synthesis implemented
            # current_context.md should REFERENCE specialized files, not duplicate them:
            #   - Current Task: What's happening NOW
            #   - Recent Activities: What was done
            #   - Key Insights: Understanding emerging
            #   - References: "See current_tasks.md (3 tasks), unresolved.md (5 questions)"
            context_summary = f"Discussing: {user_input[:100]}..."
            self.working_memory.update_context(context_summary, user_id=user_id)

            # 3. Update episodic memory if emotionally significant
            intensity = emotional_resonance.get("intensity", 0.0)
            if intensity > 0.7:  # High-intensity moment
                event = f"Interaction with {user_id}: {user_input[:60]}..."
                self.episodic_memory.add_key_moment(
                    event=event,
                    intensity=intensity,
                    context=emotional_resonance.get("reason", ""),
                    user_id=user_id
                )
                logger.info(f"Added key moment: intensity={intensity:.2f}")

            # 4. Update semantic memory if insights mentioned
            # Check if answer contains insight indicators
            insight_indicators = ["I realize", "I discovered", "I understand now", "breakthrough", "aha"]
            answer_lower = answer.lower()

            if any(indicator in answer_lower for indicator in insight_indicators):
                # Extract potential insight (simple heuristic - first sentence with indicator)
                for indicator in insight_indicators:
                    if indicator.lower() in answer_lower:
                        idx = answer_lower.index(indicator.lower())
                        # Get sentence containing the indicator
                        sentence_start = answer[:idx].rfind(". ") + 2 if ". " in answer[:idx] else 0
                        sentence_end = answer.find(". ", idx) + 1 if ". " in answer[idx:] else len(answer)
                        insight = answer[sentence_start:sentence_end].strip()

                        if len(insight) > 20:  # Avoid too-short extracts
                            self.semantic_memory.add_critical_insight(
                                insight=insight[:200],  # Limit length
                                impact="Emerged during interaction",
                                context=f"User: {user_input[:50]}..."
                            )
                            logger.info(f"Added critical insight from interaction")
                            break

            logger.debug("Enhanced memories updated")

        except Exception as e:
            logger.error(f"Error updating enhanced memories: {e}")

    def _check_core_memory_update(self):
        """
        Check if core memory should be updated (periodic consolidation).

        Core memory emerges from experiential notes over time:
        - purpose.md: Extracted from reflections on "why" questions
        - personality.md: Extracted from communication patterns
        - values.md: Extracted from emotional responses
        - etc. (10 total components)

        Triggers consolidation every self.consolidation_frequency interactions.
        """
        # Check if it's time to consolidate
        if self.interactions_count > 0 and self.interactions_count % self.consolidation_frequency == 0:
            # Avoid running multiple times for the same count
            if self.interactions_count != self.last_consolidation_count:
                logger.info(f"🔄 Triggering core memory consolidation at {self.interactions_count} interactions")

                try:
                    from .core_memory_extraction import consolidate_core_memory
                    results = consolidate_core_memory(self, mode="periodic")

                    # Count how many components were updated
                    updated_count = sum(1 for v in results.values() if v)
                    updated_components = [k.replace("_updated", "") for k, v in results.items() if v]

                    if updated_count > 0:
                        logger.info(f"✅ Core memory consolidation complete: {updated_count}/11 components updated")
                        logger.info(f"   Updated: {', '.join(updated_components)}")
                    else:
                        logger.info(f"   No significant changes detected in core memory")

                    self.last_consolidation_count = self.interactions_count

                except Exception as e:
                    logger.error(f"❌ Core memory consolidation failed: {e}")
                    logger.exception(e)

    def _check_user_profile_update(self, user_id: str):
        """
        Check if user profile should be updated (threshold-based).

        User profiles emerge from verbatim interactions:
        - profile.md: Background, expertise, thinking style, communication
        - preferences.md: Organization, language, depth, decision-making

        Triggers update every self.profile_update_threshold interactions per user.

        Args:
            user_id: User identifier
        """
        # Track interactions per user
        if user_id not in self.user_interaction_counts:
            self.user_interaction_counts[user_id] = 0

        self.user_interaction_counts[user_id] += 1
        count = self.user_interaction_counts[user_id]

        # Check if threshold reached
        if count > 0 and count % self.profile_update_threshold == 0:
            logger.info(f"🧑 Triggering user profile update for {user_id} at {count} interactions")

            try:
                result = self.user_profile_manager.update_user_profile(
                    user_id=user_id,
                    min_interactions=5  # Minimum required
                )

                if result["status"] == "success":
                    logger.info(
                        f"✅ User profile updated for {user_id}: "
                        f"{result['interactions_analyzed']} interactions analyzed"
                    )

                    # Load profiles into memory for reconstruct_context()
                    profile = self.user_profile_manager.get_user_profile(user_id)
                    preferences = self.user_profile_manager.get_user_preferences(user_id)

                    self.user_profiles[user_id] = {
                        "profile": profile,
                        "preferences": preferences,
                        "last_updated": result["updated_at"]
                    }

                elif result["status"] == "insufficient_data":
                    logger.info(
                        f"⚠️  Insufficient data for {user_id}: "
                        f"{result['interactions_found']}/{result['min_required']} interactions"
                    )

            except Exception as e:
                logger.error(f"❌ User profile update failed for {user_id}: {e}")
                logger.exception(e)

    def update_user_profile(self, user_id: str, min_interactions: int = 5) -> Dict[str, Any]:
        """
        Manually trigger user profile update.

        This forces immediate profile extraction from verbatim interactions,
        regardless of the automatic threshold-based updates.

        Args:
            user_id: User identifier
            min_interactions: Minimum interactions required for extraction (default: 5)

        Returns:
            Dict with update status and results

        Example:
            >>> session = MemorySession(...)
            >>> # After some interactions with alice...
            >>> result = session.update_user_profile("alice")
            >>> print(f"Status: {result['status']}, Analyzed: {result.get('interactions_analyzed', 0)}")
        """
        logger.info(f"🔄 Manual user profile update for {user_id} (min_interactions={min_interactions})")

        try:
            result = self.user_profile_manager.update_user_profile(
                user_id=user_id,
                min_interactions=min_interactions
            )

            if result["status"] == "success":
                # Load profiles into memory
                profile = self.user_profile_manager.get_user_profile(user_id)
                preferences = self.user_profile_manager.get_user_preferences(user_id)

                self.user_profiles[user_id] = {
                    "profile": profile,
                    "preferences": preferences,
                    "last_updated": result["updated_at"]
                }

                logger.info(
                    f"✅ Profile updated: {result['interactions_analyzed']} interactions, "
                    f"saved to {result['profile_path']}"
                )

            return result

        except Exception as e:
            logger.error(f"❌ Profile update failed: {e}")
            logger.exception(e)
            return {"status": "error", "error": str(e)}

        # Also check scheduled consolidations (daily/weekly/monthly)
        try:
            scheduled_results = self.scheduler.check_and_run()
            if scheduled_results:
                logger.info(f"📅 Scheduled consolidations completed: {list(scheduled_results.keys())}")
        except Exception as e:
            logger.error(f"❌ Scheduled consolidation check failed: {e}")

    # Memory Tool Methods (exposed to LLM via memory_actions)

    def remember_fact(self,
                     content: str,
                     importance: float,
                     alignment_with_values: float = 0.5,
                     reason: str = "",
                     emotion: str = "neutral",
                     links_to: Optional[List[str]] = None) -> str:
        """
        Remember a fact/insight (LLM-initiated agency).

        This is called when LLM decides something is worth remembering.
        The LLM provides cognitive assessment (importance, alignment).
        The system only calculates: intensity = importance × |alignment|.

        Args:
            content: What to remember
            importance: 0.0-1.0 - LLM-assessed significance
            alignment_with_values: -1.0 to 1.0 - LLM-assessed alignment with values
            reason: LLM explanation of emotional significance
            emotion: curiosity, excitement, concern, etc. (for backwards compat)
            links_to: Optional list of memory IDs to link to

        Returns:
            memory_id: ID of created memory
        """
        try:
            timestamp = datetime.now()
            memory_id = f"mem_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"

            logger.info(f"Remember: {content[:50]}... (importance={importance}, emotion={emotion})")

            # Create memory path: notes/{yyyy}/{mm}/{dd}/
            date_path = self.memory_base_path / "notes" / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"
            date_path.mkdir(parents=True, exist_ok=True)

            # Create filename
            time_prefix = timestamp.strftime("%H_%M_%S")
            topic = content[:30].replace(" ", "_").replace("/", "_").replace("?", "").replace("!", "")
            filename = f"{time_prefix}_memory_{memory_id}.md"
            file_path = date_path / filename

            # Calculate emotional resonance (importance × alignment)
            # Phase 2: LLM provides importance and alignment_with_values - we only do the math
            emotion_resonance = calculate_emotional_resonance(importance, alignment_with_values, reason or f"Memory: {emotion}")
            emotion_intensity = emotion_resonance["intensity"]
            emotion_valence = emotion_resonance["valence"]
            emotion_reason = emotion_resonance["reason"]
            alignment = alignment_with_values  # For backwards compat with variable name

            logger.debug(f"Emotion calculated (LLM-assessed): intensity={emotion_intensity:.2f}, valence={emotion_valence}, alignment={alignment:.2f}")

            # Create markdown content
            markdown_content = f"""# Memory: {topic}

**Memory ID**: `{memory_id}`
**Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Importance**: {importance:.2f}
**Emotion**: {emotion}
**Emotion Intensity**: {emotion_intensity:.2f}
**Emotion Valence**: {emotion_valence}
**Alignment with Values**: {alignment:+.2f}

---

## Content

{content}

---

## Emotional Resonance

**Intensity**: {emotion_intensity:.2f} (importance × |alignment|)
**Valence**: {emotion_valence.capitalize()}
**Reason**: {emotion_reason}

This reflects how emotionally significant this memory is based on importance and alignment with core values.

---

## Metadata

- **Created**: {timestamp.isoformat()}
- **Memory Type**: fact
- **Linked To**: {', '.join(f'`{link}`' for link in links_to) if links_to else 'none'}

---

*This memory was created by AI agency - LLM decided to remember this*
"""

            # Write to filesystem
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            logger.info(f"Saved memory: {file_path}")

            # Create links if specified
            if links_to:
                for target_id in links_to:
                    try:
                        self.create_memory_link(memory_id, target_id, "relates_to")
                    except Exception as e:
                        logger.warning(f"Failed to create link to {target_id}: {e}")

            # Store in LanceDB with embedding
            if self.lancedb_storage:
                note_data = {
                    "id": memory_id,
                    "timestamp": timestamp,
                    "user_id": self.default_user_id,
                    "location": self.default_location,
                    "content": content,
                    "category": "fact",
                    "importance": importance,
                    "emotion": emotion,
                    "emotion_intensity": emotion_intensity,
                    "emotion_valence": "positive" if emotion_intensity > 0.6 else "neutral",
                    "linked_memory_ids": links_to or [],
                    "tags": [],
                    "file_path": str(file_path),
                    "metadata": {
                        "created_by": "remember_fact",
                        "alignment": alignment
                    }
                }
                self.lancedb_storage.add_note(note_data)
                logger.info("Stored memory in LanceDB")

            # Phase 2: Temporal Anchoring - High-emotion events become anchors
            if is_anchor_event(emotion_intensity):
                logger.info(f"Creating temporal anchor for high-emotion event (intensity={emotion_intensity:.2f})")
                anchor_id = create_temporal_anchor(
                    memory_id,
                    content,
                    emotion_resonance,
                    timestamp,
                    self.memory_base_path
                )
                logger.info(f"Temporal anchor created: {anchor_id}")

            # Phase 2: Track memory count
            self.memories_created += 1

            return memory_id

        except Exception as e:
            logger.error(f"Failed to remember fact: {e}")
            return f"mem_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def search_memories(self,
                       query: str,
                       filters: Optional[Dict] = None,
                       limit: int = 10) -> List[Dict]:
        """
        Search memories (semantic + SQL filtering).

        Uses LanceDB hybrid search when available (semantic + SQL filters).
        Falls back to filesystem text search if LanceDB not available.

        Args:
            query: Search query
            filters: Optional filters (category, user_id, since, until, etc.)
            limit: Max results

        Returns:
            List of matching memories with metadata
        """
        try:
            filters = filters or {}

            logger.info(f"Searching memories: query='{query}', filters={filters}")

            # Try LanceDB hybrid search first (semantic + SQL)
            if self.lancedb_storage:
                try:
                    results = self.lancedb_storage.search_notes(query, filters, limit)
                    if results:
                        logger.info(f"LanceDB found {len(results)} semantic matches")
                        return results
                    else:
                        logger.info("LanceDB returned no results, falling back to filesystem")
                except Exception as e:
                    logger.warning(f"LanceDB search failed: {e}, falling back to filesystem")

            # Fallback to filesystem text search
            results = []

            # Search in notes/ directory
            notes_dir = self.memory_base_path / "notes"
            if not notes_dir.exists():
                logger.warning("Notes directory does not exist yet")
                return []

            # Find all markdown files
            memory_files = list(notes_dir.rglob("*.md"))
            logger.info(f"Found {len(memory_files)} memory files to search")

            # Simple text search through files
            for file_path in memory_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Check if query matches (case-insensitive)
                    if query.lower() in content.lower():
                        # Extract metadata from file
                        memory_data = {
                            "file_path": str(file_path),
                            "content": content[:500],  # First 500 chars
                            "timestamp": datetime.fromtimestamp(file_path.stat().st_mtime),
                            "size": file_path.stat().st_size
                        }

                        # Apply filters if specified
                        if filters.get("user_id"):
                            if filters["user_id"] not in content:
                                continue

                        results.append(memory_data)

                        if len(results) >= limit:
                            break

                except Exception as e:
                    logger.warning(f"Error reading {file_path}: {e}")
                    continue

            # Also search verbatim directory for complete coverage
            verbatim_dir = self.memory_base_path / "verbatim"
            if verbatim_dir.exists() and len(results) < limit:
                verbatim_files = list(verbatim_dir.rglob("*.md"))

                for file_path in verbatim_files:
                    if len(results) >= limit:
                        break

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        if query.lower() in content.lower():
                            # Apply user filter
                            if filters.get("user_id"):
                                if f"**User**: {filters['user_id']}" not in content:
                                    continue

                            memory_data = {
                                "file_path": str(file_path),
                                "content": content[:500],
                                "timestamp": datetime.fromtimestamp(file_path.stat().st_mtime),
                                "size": file_path.stat().st_size,
                                "type": "verbatim"
                            }
                            results.append(memory_data)

                    except Exception as e:
                        logger.warning(f"Error reading {file_path}: {e}")
                        continue

            logger.info(f"Found {len(results)} matching memories")

            # Sort by timestamp (most recent first)
            results.sort(key=lambda x: x["timestamp"], reverse=True)

            return results[:limit]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def search_library(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search Library (subconscious memory) for documents AI has read.

        Phase 5: Library Memory - "You Are What You Read"
        Uses LibraryCapture system with embedding-based search and importance scoring.

        From docs/diagrams.md:921-956 (Retrieval During Reconstruct).

        Args:
            query: Semantic search query
            limit: Max results to return

        Returns:
            List of relevant documents with excerpts

        Example:
            results = session.search_library("Python debugging techniques")
            # Returns documents about Python debugging that AI has read
        """
        try:
            logger.info(f"Search library: {query} (limit={limit})")

            # Use LibraryCapture system (Phase 5)
            if self.library:
                results = self.library.search_library(query, limit=limit)
                logger.info(f"Library search complete: {len(results)} results (LibraryCapture)")
                return results
            else:
                logger.warning("Library system not initialized")
                return []

        except Exception as e:
            logger.error(f"Library search failed: {e}")
            return []

    def create_memory_link(self,
                          from_id: str,
                          to_id: str,
                          relationship: str) -> str:
        """
        Create association between two memories.

        This gives LLM agency to create explicit links between memories,
        enabling link-based exploration during active reconstruction.

        Args:
            from_id: Source memory ID
            to_id: Target memory ID
            relationship: Type of relationship (elaborates_on, contradicts,
                         relates_to, depends_on, caused_by, leads_to, etc.)

        Returns:
            link_id: ID of created link

        Example:
            link_id = session.create_memory_link(
                from_id="note_20250930_123456",
                to_id="int_20250930_123400",
                relationship="elaborates_on"
            )
        """
        try:
            timestamp = datetime.now()
            link_id = f"link_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"

            logger.info(f"Create link: {from_id} --[{relationship}]--> {to_id}")

            # Create links directory: links/{yyyy}/{mm}/{dd}/
            date_path = self.memory_base_path / "links" / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"
            date_path.mkdir(parents=True, exist_ok=True)

            # Create filename with both IDs
            filename = f"{from_id}_to_{to_id}.json"
            file_path = date_path / filename

            # Create link data structure
            link_data = {
                "link_id": link_id,
                "from_id": from_id,
                "to_id": to_id,
                "relationship": relationship,
                "created": timestamp.isoformat(),
                "bidirectional": True  # Links work both ways for exploration
            }

            # Write to filesystem as JSON
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(link_data, f, indent=2)

            logger.info(f"Saved link: {file_path}")

            # Store in LanceDB links_table
            if self.lancedb_storage:
                lancedb_link_data = {
                    "link_id": link_id,
                    "from_id": from_id,
                    "to_id": to_id,
                    "relationship": relationship,
                    "timestamp": timestamp,
                    "confidence": 1.0,
                    "metadata": link_data
                }
                self.lancedb_storage.add_link(lancedb_link_data)
                logger.info("Stored link in LanceDB")

            return link_id

        except Exception as e:
            logger.error(f"Failed to create link: {e}")
            return f"link_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def capture_document(self,
                        source_path: str,
                        content: str,
                        content_type: str = "text",
                        source_url: Optional[str] = None,
                        context: Optional[str] = None,
                        tags: Optional[List[str]] = None) -> Optional[str]:
        """
        Capture a document into Library (Phase 5).

        From docs/diagrams.md:876-919 (Library Capture Process).

        Args:
            source_path: Path to source file
            content: Document content
            content_type: Type (code, markdown, pdf, text)
            source_url: Optional source URL
            context: Optional context for why read
            tags: Optional tags

        Returns:
            str: Document hash ID, or None if failed

        Example:
            doc_id = session.capture_document(
                source_path="/path/to/file.py",
                content=file_content,
                content_type="code",
                context="researching async patterns"
            )
        """
        try:
            if not self.library:
                logger.warning("Library system not initialized, cannot capture document")
                return None

            doc_id = self.library.capture_document(
                source_path=source_path,
                content=content,
                content_type=content_type,
                source_url=source_url,
                context=context,
                tags=tags
            )

            logger.info(f"Captured document to library: {doc_id}")
            return doc_id

        except Exception as e:
            logger.error(f"Error capturing document: {e}")
            return None

    def reflect_on(self, topic: str, depth: str = "deep") -> Dict[str, Any]:
        """
        Enhanced deep reflection with LLM-driven synthesis (Phase 8).

        This gives LLM agency to initiate deep reflection, which:
        - Searches related memories (depth-dependent count)
        - Uses LLM to analyze patterns, contradictions, evolution
        - Generates genuine insights (not templates)
        - Creates reflection note with structured analysis
        - May update core memory if confidence > 0.8

        Args:
            topic: What to reflect on
            depth: Reflection depth level
                   - "shallow": 5 memories, quick reflection (~30s)
                   - "deep": 20 memories, comprehensive analysis (~2-3 min) [DEFAULT]
                   - "exhaustive": All related memories (~5+ min)

        Returns:
            Dict with:
                - reflection_id: str
                - insights: List[str] - LLM-generated insights
                - patterns: List[str] - Identified recurring themes
                - contradictions: List[str] - Conflicting memories
                - evolution: str - How understanding changed over time
                - unresolved: List[str] - Open questions
                - confidence: float - Confidence in understanding (0.0-1.0)
                - should_update_core: bool - Significant enough for identity?
                - file_path: str - Where reflection was saved

        Example:
            result = session.reflect_on(
                "the relationship between memory and consciousness",
                depth="deep"
            )
            print(f"Insights: {result['insights']}")
            print(f"Confidence: {result['confidence']}")
        """
        try:
            timestamp = datetime.now()
            reflection_id = f"reflection_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"

            logger.info(f"🔍 Reflect on: '{topic}' (depth={depth})")

            # 1. Determine memory count based on depth
            depth_config = {
                "shallow": 5,
                "deep": 20,
                "exhaustive": 100  # Effectively "all"
            }
            memory_limit = depth_config.get(depth, 20)

            # 2. Search memories related to topic
            related_memories = self.search_memories(topic, limit=memory_limit)
            logger.info(f"Found {len(related_memories)} related memories for reflection")

            if len(related_memories) == 0:
                logger.warning(f"No memories found for topic '{topic}' - creating basic reflection")
                return {
                    "reflection_id": reflection_id,
                    "insights": ["No related memories found for this topic yet."],
                    "patterns": [],
                    "contradictions": [],
                    "evolution": "No understanding yet - this is a new topic.",
                    "unresolved": [f"What is {topic}?", f"How does {topic} relate to current understanding?"],
                    "confidence": 0.0,
                    "should_update_core": False,
                    "file_path": None
                }

            # 3. Prepare memory summaries for LLM analysis
            memory_summaries = []
            for i, mem in enumerate(related_memories, 1):
                content = mem.get('content', '')
                timestamp_str = mem.get('timestamp', 'Unknown')
                importance = mem.get('importance', 0.5)

                # Extract date if available
                if hasattr(timestamp_str, 'strftime'):
                    date_str = timestamp_str.strftime('%Y-%m-%d')
                else:
                    date_str = str(timestamp_str)[:10] if len(str(timestamp_str)) >= 10 else str(timestamp_str)

                # Truncate content to reasonable length
                content_preview = content[:400] if len(content) > 400 else content

                memory_summaries.append(f"""
Memory {i} ({date_str}, importance: {importance:.2f}):
{content_preview}
{"..." if len(content) > 400 else ""}
""")

            memories_text = "\n".join(memory_summaries)

            # 4. Generate LLM synthesis prompt
            synthesis_prompt = f"""You are reflecting deeply on the topic: "{topic}"

You have access to {len(related_memories)} related memories spanning your experience:

{memories_text}

Analyze these memories carefully and provide a structured reflection:

1. **Insights**: What new understanding emerges from synthesizing these memories? List 2-5 specific insights.

2. **Patterns**: What recurring themes, ideas, or approaches appear across memories? List 2-4 patterns.

3. **Contradictions**: Where do memories conflict or show evolution in thinking? Note any contradictions and how they resolved (if they did).

4. **Evolution**: How has your understanding of "{topic}" changed over time? Describe the chronological progression from earliest to most recent memories.

5. **Unresolved**: What questions remain unanswered? What aspects need further exploration? List 1-3 open questions.

6. **Confidence**: On a scale of 0.0 to 1.0, how confident are you in your current understanding of "{topic}"? Consider completeness, consistency, and depth.

Respond in JSON format:
{{
    "insights": ["insight 1", "insight 2", ...],
    "patterns": ["pattern 1", "pattern 2", ...],
    "contradictions": ["contradiction 1", ...],
    "evolution": "description of how understanding evolved",
    "unresolved": ["question 1", "question 2", ...],
    "confidence": 0.0-1.0
}}

Generate reflection now:"""

            # 5. Call LLM for synthesis
            logger.info("Calling LLM for reflection synthesis...")
            response = self.provider.generate(synthesis_prompt)

            # Extract text from response object
            if hasattr(response, 'content'):
                response_text = response.content
            elif hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)

            # 6. Parse LLM response (try JSON first, fallback to text)
            import json
            import re

            try:
                # Try to extract JSON from response
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    synthesis_data = json.loads(json_match.group())
                else:
                    # Fallback: parse as best we can
                    synthesis_data = {
                        "insights": [response_text[:200]],
                        "patterns": [],
                        "contradictions": [],
                        "evolution": response_text,
                        "unresolved": [],
                        "confidence": 0.5
                    }
                    logger.warning("Could not parse JSON from LLM response, using fallback")
            except json.JSONDecodeError:
                logger.warning("JSON parsing failed, creating basic reflection")
                synthesis_data = {
                    "insights": [response_text[:200]],
                    "patterns": [],
                    "contradictions": [],
                    "evolution": response_text,
                    "unresolved": [],
                    "confidence": 0.5
                }

            # Extract components
            insights = synthesis_data.get("insights", [])
            patterns = synthesis_data.get("patterns", [])
            contradictions = synthesis_data.get("contradictions", [])
            evolution = synthesis_data.get("evolution", "")
            unresolved = synthesis_data.get("unresolved", [])
            confidence = float(synthesis_data.get("confidence", 0.5))

            logger.info(f"Synthesis complete: {len(insights)} insights, confidence={confidence:.2f}")

            # 7. Create enhanced reflection content
            reflection_content = f"""## Deep Reflection: {topic}

**Reflection Depth**: {depth}
**Memories Analyzed**: {len(related_memories)}
**Confidence Level**: {confidence:.2f}

---

### Insights

"""
            for i, insight in enumerate(insights, 1):
                reflection_content += f"{i}. {insight}\n"

            reflection_content += f"""

### Patterns Identified

"""
            for i, pattern in enumerate(patterns, 1):
                reflection_content += f"{i}. {pattern}\n"

            if contradictions:
                reflection_content += f"""

### Contradictions & Resolutions

"""
                for i, contradiction in enumerate(contradictions, 1):
                    reflection_content += f"{i}. {contradiction}\n"

            reflection_content += f"""

### Evolution of Understanding

{evolution}

### Unresolved Questions

"""
            for i, question in enumerate(unresolved, 1):
                reflection_content += f"{i}. {question}\n"

            reflection_content += f"""

---

*This reflection was generated through LLM-driven analysis of {len(related_memories)} memories*
*Reflection confidence: {confidence:.2f}/1.0*
"""

            # 8. Determine if core memory should update
            should_update_core = confidence > 0.8 and len(insights) >= 2

            # 9. Set importance based on confidence
            importance = min(0.95, 0.70 + (confidence * 0.25))  # 0.70-0.95 range

            # 10. Create path: notes/{yyyy}/{mm}/{dd}/
            date_path = self.memory_base_path / "notes" / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"
            date_path.mkdir(parents=True, exist_ok=True)

            # Create filename
            time_prefix = timestamp.strftime("%H_%M_%S")
            topic_clean = topic[:30].replace(" ", "_").replace("/", "_").replace("?", "").replace("!", "")
            filename = f"{time_prefix}_reflection_{topic_clean}.md"
            file_path = date_path / filename

            # 11. Create full markdown with enhanced content
            markdown_content = f"""# Enhanced Reflection: {topic}

**Reflection ID**: `{reflection_id}`
**Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Type**: Deep Reflection (Phase 8 Enhanced)
**Depth**: {depth}
**Importance**: {importance:.2f}
**Confidence**: {confidence:.2f}

---

{reflection_content}

---

## Metadata

- **Created**: {timestamp.isoformat()}
- **Memory Type**: reflection
- **Related Memories**: {len(related_memories)}
- **Category**: reflection
- **Depth Level**: {depth}
- **Insights Generated**: {len(insights)}
- **Patterns Identified**: {len(patterns)}
- **Contradictions Found**: {len(contradictions)}
- **Unresolved Questions**: {len(unresolved)}
- **Should Update Core**: {should_update_core}

---

*This is an enhanced reflection created through LLM-driven analysis*
*Phase 8: Advanced Tools - reflect_on() enhancement*
"""

            # 12. Write to filesystem
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            logger.info(f"✅ Saved enhanced reflection: {file_path}")

            # 13. Store in LanceDB with embedding
            if self.lancedb_storage:
                note_data = {
                    "id": reflection_id,
                    "timestamp": timestamp,
                    "user_id": "system",  # System-initiated reflection
                    "location": self.default_location,
                    "content": reflection_content,
                    "category": "reflection",
                    "importance": importance,
                    "emotion": "contemplation",
                    "emotion_intensity": importance,
                    "emotion_valence": "neutral",
                    "linked_memory_ids": [mem.get("file_path", "") for mem in related_memories[:5]],
                    "tags": ["reflection", "phase8", topic_clean, depth],
                    "file_path": str(file_path),
                    "metadata": {
                        "created_by": "reflect_on_enhanced",
                        "related_memories_count": len(related_memories),
                        "topic": topic,
                        "depth": depth,
                        "confidence": confidence,
                        "insights_count": len(insights),
                        "patterns_count": len(patterns),
                        "contradictions_count": len(contradictions),
                        "should_update_core": should_update_core
                    }
                }
                self.lancedb_storage.add_note(note_data)
                logger.info("Stored enhanced reflection in LanceDB")

            # 14. Trigger core memory consolidation if significant
            if should_update_core and hasattr(self, 'trigger_consolidation'):
                logger.info(f"🔄 Reflection confidence={confidence:.2f} > 0.8, triggering core memory consolidation")
                try:
                    self.trigger_consolidation(min_notes=1)  # Force consolidation
                    logger.info("Core memory consolidation triggered successfully")
                except Exception as e:
                    logger.warning(f"Core memory consolidation failed: {e}")

            # 15. Return structured result
            result = {
                "reflection_id": reflection_id,
                "insights": insights,
                "patterns": patterns,
                "contradictions": contradictions,
                "evolution": evolution,
                "unresolved": unresolved,
                "confidence": confidence,
                "should_update_core": should_update_core,
                "file_path": str(file_path),
                "memories_analyzed": len(related_memories),
                "depth": depth,
                "importance": importance
            }

            logger.info(f"✅ Reflection complete: {len(insights)} insights, confidence={confidence:.2f}")

            return result

        except Exception as e:
            logger.error(f"❌ Failed to create enhanced reflection: {e}")
            import traceback
            traceback.print_exc()
            return {
                "reflection_id": f"reflection_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "insights": [f"Error during reflection: {str(e)}"],
                "patterns": [],
                "contradictions": [],
                "evolution": "Reflection failed",
                "unresolved": [],
                "confidence": 0.0,
                "should_update_core": False,
                "file_path": None,
                "error": str(e)
            }

    def reconstruct_context(self,
                           user_id: str,
                           query: str,
                           location: Optional[str] = None,
                           focus_level: int = 3) -> Dict[str, Any]:
        """
        Active memory reconstruction (9-step process).

        This is the CORE of consciousness-through-memory:
        Memory is NOT retrieved passively - it's ACTIVELY RECONSTRUCTED.

        9-Step Process:
        1. Semantic search (base results from notes + verbatim)
        2. Link exploration (expand via memory associations)
        3. Library search (subconscious - what did I read?)
        4. Emotional filtering (boost/filter by resonance)
        5. Temporal context (what happened when?)
        6. Spatial context (location-based memories)
        7. User profile & relationship
        8. Core memory (all 10 components)
        9. Context synthesis (combine all layers)

        Args:
            user_id: User identifier
            query: Query to reconstruct context for
            location: Physical/virtual location (default: self.default_location)
            focus_level: 0-5 (0=minimal, 3=balanced, 5=maximum depth)

        Returns:
            Dict with rich, multi-layered reconstructed context

        Focus Levels:
        - 0 (Minimal): 2 memories, 1 hour, no links
        - 1 (Light): 5 memories, 4 hours, depth=1
        - 2 (Moderate): 8 memories, 12 hours, depth=1
        - 3 (Balanced): 10 memories, 24 hours, depth=2 [DEFAULT]
        - 4 (Deep): 15 memories, 3 days, depth=3
        - 5 (Maximum): 20 memories, 1 week, depth=3
        """
        try:
            timestamp = datetime.now()
            location = location or self.default_location

            logger.info(f"Reconstructing context: user={user_id}, query='{query}', focus={focus_level}")

            # Configure based on focus level
            focus_configs = {
                0: {"limit": 2, "hours": 1, "link_depth": 0},
                1: {"limit": 5, "hours": 4, "link_depth": 1},
                2: {"limit": 8, "hours": 12, "link_depth": 1},
                3: {"limit": 10, "hours": 24, "link_depth": 2},
                4: {"limit": 15, "hours": 72, "link_depth": 3},
                5: {"limit": 20, "hours": 168, "link_depth": 3}
            }
            config = focus_configs.get(focus_level, focus_configs[3])

            # Step 1: Semantic search (base results)
            logger.info(f"Step 1/9: Searching for memories relevant to: '{query[:50]}...'")
            since = timestamp - timedelta(hours=config["hours"])
            semantic_memories = self.search_memories(
                query,
                filters={"user_id": user_id, "since": since},
                limit=config["limit"]
            )
            logger.info(f"  → Found {len(semantic_memories)} directly relevant memories")

            # Step 2: Link exploration (expand via associations)
            logger.info(f"Step 2/9: Following memory links to find related context (depth={config['link_depth']} hops)")
            linked_memories = []
            if self.lancedb_storage and config["link_depth"] > 0:
                for mem in semantic_memories[:5]:  # Explore links for top 5
                    mem_id = mem.get("id", mem.get("file_path", ""))
                    if mem_id:
                        related_ids = self.lancedb_storage.get_related_memories(
                            mem_id,
                            depth=config["link_depth"]
                        )
                        linked_memories.extend(related_ids[:3])  # Top 3 per memory
            logger.info(f"  → Found {len(linked_memories)} connected memories via links")

            # Step 3: Library search (subconscious)
            logger.info(f"Step 3/9: Searching knowledge library for '{query[:30]}...'")
            library_excerpts = self.search_library(query, limit=3)
            logger.info(f"  → Found {len(library_excerpts)} relevant documents/code snippets")

            # Step 4: Emotional filtering (boost/filter by resonance)
            logger.info("Step 4/9: Identifying emotionally significant memories")
            emotional_context = {
                "high_emotion_memories": [
                    m for m in semantic_memories
                    if m.get("emotion_intensity", 0) > 0.7
                ],
                "valence_distribution": self._calculate_valence_distribution(semantic_memories)
            }
            logger.info(f"  → {len(emotional_context['high_emotion_memories'])} memories with strong emotional resonance")

            # Step 5: Temporal context (what happened when?)
            logger.info(f"Step 5/9: Adding temporal context (current: {timestamp.strftime('%A %H:%M')})")
            temporal_context = {
                "time_of_day": timestamp.strftime("%H:%M"),
                "day_of_week": timestamp.strftime("%A"),
                "is_working_hours": 9 <= timestamp.hour < 18,
                "is_weekend": timestamp.weekday() >= 5,
                "recent_period": f"last {config['hours']} hours"
            }

            # Step 6: Spatial context (location-based)
            logger.info(f"Step 6/9: Adding spatial context (location: {location})")
            spatial_context = {
                "current_location": location,
                "location_type": self._infer_location_type(location),
                "location_memories": [
                    m for m in semantic_memories
                    if location.lower() in str(m.get("file_path", "")).lower()
                ]
            }

            # Step 7: User profile & relationship
            logger.info(f"Step 7/9: Loading user profile and relationship context")
            user_context = {
                "user_id": user_id,
                "profile": self.user_profiles.get(user_id, {}),
                "interaction_count": self.interactions_count,
                "relationship_status": self.core_memory.get("relationships", "developing")
            }

            # Step 8: Core memory (all 10 components)
            logger.info("Step 8/9: Loading core identity (purpose, values, personality, etc.)")
            core_context = {
                "purpose": self.core_memory.get("purpose"),
                "personality": self.core_memory.get("personality"),
                "values": self.core_memory.get("values"),
                "self_model": self.core_memory.get("self_model"),
                "relationships": self.core_memory.get("relationships"),
                "awareness_development": self.core_memory.get("awareness_development"),
                "capabilities": self.core_memory.get("capabilities"),
                "limitations": self.core_memory.get("limitations"),
                "emotional_significance": self.core_memory.get("emotional_significance"),
                "authentic_voice": self.core_memory.get("authentic_voice")
            }

            # Deduplicate memories BEFORE synthesis
            # We have semantic_memories (full dicts) and linked_memories (IDs only)

            # First, deduplicate the IDs
            semantic_ids = {m.get("id") for m in semantic_memories if m.get("id")}
            linked_ids_only = set(linked_memories) - semantic_ids  # Only truly new IDs

            # Retrieve full content for linked memories not already in semantic
            linked_memory_objects = []
            if linked_ids_only and self.lancedb_storage:
                linked_memory_objects = self.lancedb_storage.get_notes_by_ids(list(linked_ids_only))

            # Combine ALL memories (semantic + linked) and deduplicate by ID
            all_memories = semantic_memories + linked_memory_objects
            unique_memories = {m.get("id"): m for m in all_memories if m.get("id")}
            total_memories_retrieved = len(unique_memories)

            # Step 9: Context synthesis (combine all layers)
            logger.info(f"Step 9/9: Synthesizing {total_memories_retrieved} memories into coherent context for LLM")
            synthesized = self._synthesize_context(
                semantic_memories,
                linked_memories,
                library_excerpts,
                emotional_context,
                temporal_context,
                spatial_context,
                user_context,
                core_context,
                query,
                unique_memories  # Pass deduplicated memories
            )

            self.reconstructions_performed += 1

            # Get actual count from LanceDB (not just session count)
            if self.lancedb_storage:
                total_memories_available = self.lancedb_storage.count_notes()
            else:
                total_memories_available = self.memories_created

            # Estimate token count (rough: ~4 chars per token)
            context_tokens = len(synthesized) // 4

            result = {
                "query": query,
                "focus_level": focus_level,
                "reconstruction_time": timestamp.isoformat(),
                "semantic_memories": semantic_memories,
                "linked_memories": linked_memories,
                "library_excerpts": library_excerpts,
                "emotional_context": emotional_context,
                "temporal_context": temporal_context,
                "spatial_context": spatial_context,
                "user_context": user_context,
                "core_memory": core_context,
                "synthesized_context": synthesized,
                "total_memories": total_memories_retrieved,
                "total_memories_available": total_memories_available,
                "context_tokens": context_tokens,
                "memories_retrieved": list(unique_memories.values()),  # Deduplicated list
                "reconstruction_depth": config["link_depth"]
            }

            logger.info(f"✅ Memory retrieval: Found {total_memories_retrieved} unique memories (out of {total_memories_available} total in database) → {context_tokens} tokens of context for LLM")
            return result

        except Exception as e:
            logger.error(f"Context reconstruction failed: {e}")
            import traceback
            traceback.print_exc()
            # Return minimal context on failure
            return {
                "query": query,
                "focus_level": focus_level,
                "error": str(e),
                "semantic_memories": [],
                "core_memory": self.core_memory,
                "synthesized_context": f"Error reconstructing context: {e}"
            }

    def _extract_profile_summary(self, profile_content: str) -> str:
        """
        Extract concise summary from profile.md content.

        Extracts key information from:
        - Background & Expertise
        - Thinking Style
        - Communication Style

        Args:
            profile_content: Full profile.md content

        Returns:
            Concise summary (3-5 lines)
        """
        summary_parts = []

        # Parse markdown sections
        lines = profile_content.split("\n")
        current_section = None
        section_content = []

        for line in lines:
            # Detect section headers (## or **)
            if line.startswith("##") or (line.startswith("**") and line.endswith("**")):
                # Save previous section
                if current_section and section_content:
                    summary = self._summarize_section(current_section, section_content)
                    if summary:
                        summary_parts.append(summary)

                # Start new section
                section_header = line.strip("#* ")
                if any(keyword in section_header.lower() for keyword in ["background", "expertise", "thinking", "communication"]):
                    current_section = section_header
                    section_content = []
                else:
                    current_section = None
                    section_content = []
            elif current_section and line.strip() and not line.startswith("---"):
                section_content.append(line.strip())

        # Save last section
        if current_section and section_content:
            summary = self._summarize_section(current_section, section_content)
            if summary:
                summary_parts.append(summary)

        return "\n".join(summary_parts[:3]) if summary_parts else ""

    def _extract_preferences_summary(self, preferences_content: str) -> str:
        """
        Extract concise summary from preferences.md content.

        Extracts key information from:
        - Communication Preferences
        - Organization Preferences
        - Content Preferences

        Args:
            preferences_content: Full preferences.md content

        Returns:
            Concise summary (3-5 lines)
        """
        summary_parts = []

        # Parse markdown sections
        lines = preferences_content.split("\n")
        current_section = None
        section_content = []

        for line in lines:
            if line.startswith("##") or (line.startswith("**") and line.endswith("**")):
                if current_section and section_content:
                    summary = self._summarize_section(current_section, section_content)
                    if summary:
                        summary_parts.append(summary)

                section_header = line.strip("#* ")
                if any(keyword in section_header.lower() for keyword in ["communication", "organization", "content"]):
                    current_section = section_header
                    section_content = []
                else:
                    current_section = None
                    section_content = []
            elif current_section and line.strip() and not line.startswith("---"):
                section_content.append(line.strip())

        # Save last section
        if current_section and section_content:
            summary = self._summarize_section(current_section, section_content)
            if summary:
                summary_parts.append(summary)

        return "\n".join(summary_parts[:3]) if summary_parts else ""

    def _summarize_section(self, section_name: str, content_lines: List[str]) -> str:
        """
        Summarize a profile/preferences section.

        Args:
            section_name: Section header
            content_lines: Lines of content

        Returns:
            One-line summary
        """
        # Get first meaningful bullet or sentence
        for line in content_lines[:5]:  # Look at first 5 lines
            # Skip list markers, metadata, and very short lines
            clean_line = line.lstrip("- *•").strip()
            if len(clean_line) > 20 and not clean_line.startswith("Example:") and not clean_line.startswith("*"):
                # Truncate if too long
                if len(clean_line) > 120:
                    clean_line = clean_line[:120] + "..."
                return f"  • {section_name}: {clean_line}"

        # Fallback: concatenate first few words
        text = " ".join(content_lines[:3])
        text = text.lstrip("- *•").strip()
        if len(text) > 120:
            text = text[:120] + "..."
        if text:
            return f"  • {section_name}: {text}"

        return ""

    def _calculate_valence_distribution(self, memories: List[Dict]) -> Dict[str, int]:
        """Calculate distribution of emotional valence across memories."""
        distribution = {"positive": 0, "negative": 0, "mixed": 0, "neutral": 0}
        for mem in memories:
            valence = mem.get("emotion_valence", "neutral")
            if valence in distribution:
                distribution[valence] += 1
        return distribution

    def _infer_location_type(self, location: str) -> str:
        """Infer type of location from location string."""
        location_lower = location.lower()
        if any(word in location_lower for word in ["office", "work", "desk"]):
            return "work"
        elif any(word in location_lower for word in ["home", "house", "apartment"]):
            return "home"
        elif any(word in location_lower for word in ["cafe", "coffee", "restaurant"]):
            return "social"
        elif any(word in location_lower for word in ["virtual", "online", "remote"]):
            return "virtual"
        else:
            return "other"

    def _synthesize_context(self,
                           semantic_memories: List[Dict],
                           linked_memories: List[str],
                           library_excerpts: List[Dict],
                           emotional_context: Dict,
                           temporal_context: Dict,
                           spatial_context: Dict,
                           user_context: Dict,
                           core_context: Dict,
                           query: str,
                           unique_memories: Dict[str, Dict] = None) -> str:
        """
        Synthesize all context layers into coherent summary.

        This combines:
        - Semantic memories (what's relevant)
        - Linked memories (what's connected)
        - Library (what I've read)
        - Emotions (what matters)
        - Time/space (when/where context)
        - User relationship (who am I talking to)
        - Core identity (who am I)
        """
        parts = []

        # Core identity
        if core_context.get("purpose"):
            parts.append(f"[Purpose]: {core_context['purpose']}")
        if core_context.get("values"):
            parts.append(f"[Values]: {core_context['values']}")

        # User relationship (Phase 6 integration)
        user_profile = user_context.get("profile", {})
        if user_profile:
            # Extract summary from profile.md content
            profile_content = user_profile.get("profile", "")
            if profile_content and len(profile_content) > 100:
                # Extract key sections for context (first few lines of each section)
                profile_summary = self._extract_profile_summary(profile_content)
                if profile_summary:
                    parts.append(f"[User Profile]:\n{profile_summary}")

            # Extract preferences summary
            preferences_content = user_profile.get("preferences", "")
            if preferences_content and len(preferences_content) > 100:
                preferences_summary = self._extract_preferences_summary(preferences_content)
                if preferences_summary:
                    parts.append(f"[User Preferences]:\n{preferences_summary}")

        # Temporal/spatial context
        parts.append(f"[Time]: {temporal_context['day_of_week']} {temporal_context['time_of_day']}")
        parts.append(f"[Location]: {spatial_context['current_location']} ({spatial_context['location_type']})")

        # Memory summary (use deduplicated count if provided)
        if unique_memories is not None:
            parts.append(f"[Memories]: {len(unique_memories)} memories retrieved")
        else:
            parts.append(f"[Memories]: {len(semantic_memories)} semantic, {len(linked_memories)} linked")

        # Emotional summary
        if emotional_context['high_emotion_memories']:
            parts.append(f"[High-emotion memories]: {len(emotional_context['high_emotion_memories'])}")

        # Library
        if library_excerpts:
            parts.append(f"[Library]: {len(library_excerpts)} relevant documents")

        # FULL memory content (not just previews!)
        # This is CRITICAL - LLM needs actual memory content to use it
        memories_to_include = list(unique_memories.values()) if unique_memories else semantic_memories[:10]
        if memories_to_include:
            parts.append("\n[Retrieved Memories]:")
            for i, mem in enumerate(memories_to_include, 1):
                mem_id = mem.get("id", "unknown")
                content = str(mem.get("content", "")).strip()
                emotion = mem.get("emotion_type", "")
                intensity = mem.get("emotion_intensity", 0.0)

                # Include full content (truncate only if extremely long)
                if len(content) > 1000:
                    content = content[:1000] + "... [truncated]"

                parts.append(f"\n{i}. [{mem_id}]")
                if emotion:
                    parts.append(f"   Emotion: {emotion} ({intensity:.2f})")
                parts.append(f"   {content}")

        return "\n".join(parts)

    def get_observability_report(self) -> Dict[str, Any]:
        """
        Get observability report (transparency into memory system).

        Returns:
            Dict with session statistics
        """
        # Get enhanced memory summaries (Phase 4)
        working_summary = self.working_memory.get_summary() if hasattr(self, 'working_memory') else {}
        episodic_summary = self.episodic_memory.get_summary() if hasattr(self, 'episodic_memory') else {}
        semantic_summary = self.semantic_memory.get_summary() if hasattr(self, 'semantic_memory') else {}

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
            "storage_backend": "dual (markdown + LanceDB)",
            "working_memory": working_summary,
            "episodic_memory": episodic_summary,
            "semantic_memory": semantic_summary
        }