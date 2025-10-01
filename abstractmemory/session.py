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
from .storage import LanceDBStorage
from .emotions import calculate_emotional_resonance  # Only formula - LLM does cognitive assessment
from .temporal_anchoring import (
    is_anchor_event,
    create_temporal_anchor,
    get_temporal_anchors
)
from .memory_structure import initialize_memory_structure

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

        # Observability counters
        self.interactions_count = 0
        self.memories_created = 0
        self.reconstructions_performed = 0

        # Core memory consolidation tracking
        self.consolidation_frequency = 10  # Consolidate every N interactions
        self.last_consolidation_count = 0

        # Initialize consolidation scheduler (daily/weekly/monthly)
        from .consolidation_scheduler import ConsolidationScheduler
        self.scheduler = ConsolidationScheduler(self)

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

        This searches the library/ directory for documents that have been
        read/accessed by the AI. Useful during active memory reconstruction
        to surface relevant information from documents.

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

            # Check if library directory exists
            library_dir = self.memory_base_path / "library" / "documents"
            if not library_dir.exists():
                logger.warning("Library directory does not exist yet")
                # Create it for future use
                library_dir.mkdir(parents=True, exist_ok=True)
                return []

            results = []

            # Search through library documents
            doc_dirs = [d for d in library_dir.iterdir() if d.is_dir()]
            logger.info(f"Searching {len(doc_dirs)} library documents")

            for doc_dir in doc_dirs:
                if len(results) >= limit:
                    break

                try:
                    # Read content.md
                    content_file = doc_dir / "content.md"
                    if not content_file.exists():
                        continue

                    with open(content_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Check if query matches (case-insensitive)
                    if query.lower() in content.lower():
                        # Read metadata if available
                        metadata_file = doc_dir / "metadata.json"
                        metadata = {}
                        if metadata_file.exists():
                            import json
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)

                        # Update access tracking
                        access_count = metadata.get('access_count', 0) + 1
                        metadata['access_count'] = access_count
                        metadata['last_accessed'] = datetime.now().isoformat()

                        # Write back updated metadata
                        with open(metadata_file, 'w', encoding='utf-8') as f:
                            json.dump(metadata, f, indent=2)

                        # Create result with excerpt
                        # Find context around query match
                        query_pos = content.lower().find(query.lower())
                        if query_pos >= 0:
                            start = max(0, query_pos - 100)
                            end = min(len(content), query_pos + 300)
                            excerpt = content[start:end]
                        else:
                            excerpt = content[:400]

                        result = {
                            "doc_id": doc_dir.name,
                            "source": metadata.get('source_path', 'unknown'),
                            "content_type": metadata.get('content_type', 'unknown'),
                            "excerpt": excerpt,
                            "access_count": access_count,
                            "first_accessed": metadata.get('first_accessed'),
                            "last_accessed": metadata['last_accessed'],
                            "relevance": "high" if query.lower() in excerpt.lower() else "medium"
                        }

                        results.append(result)

                        logger.info(f"Found in library: {doc_dir.name} (accessed {access_count} times)")

                except Exception as e:
                    logger.warning(f"Error reading library document {doc_dir.name}: {e}")
                    continue

            logger.info(f"Library search complete: {len(results)} results (filesystem)")

            # Try LanceDB library search for semantic matching
            if self.lancedb_storage and not results:
                try:
                    lancedb_results = self.lancedb_storage.search_library(query, limit)
                    if lancedb_results:
                        logger.info(f"LanceDB library found {len(lancedb_results)} semantic matches")
                        return lancedb_results
                except Exception as e:
                    logger.warning(f"LanceDB library search failed: {e}")

            return results[:limit]

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

    def reflect_on(self, topic: str) -> str:
        """
        Trigger deep reflection on a topic.

        This gives LLM agency to initiate deep reflection, which:
        - Searches related memories
        - Reconstructs context around the topic
        - Creates a special "reflection" note with higher importance
        - May update core memory if significant insights emerge

        Args:
            topic: What to reflect on

        Returns:
            reflection_id: ID of created reflection note

        Example:
            reflection_id = session.reflect_on(
                "the relationship between memory and consciousness"
            )
        """
        try:
            timestamp = datetime.now()
            reflection_id = f"reflection_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"

            logger.info(f"Reflect on: {topic}")

            # 1. Search memories related to topic
            related_memories = self.search_memories(topic, limit=5)
            logger.info(f"Found {len(related_memories)} related memories")

            # 2. Reconstruct context around topic (basic for now)
            context = self._basic_context_reconstruction("system", topic)

            # 3. Create reflection note content
            reflection_content = f"""## Reflection on: {topic}

### Context Gathered
- Related memories found: {len(related_memories)}
- Current understanding based on: {len(self.messages)} interactions

### Memory Summary
"""
            # Add summaries of related memories
            for i, mem in enumerate(related_memories[:3], 1):
                preview = mem.get('content', '')[:200].replace('\n', ' ')
                reflection_content += f"\n{i}. {preview}...\n"

            reflection_content += f"""

### Reflection Points
This is a deep reflection on "{topic}". Key considerations:
- What patterns emerge from related memories?
- How does this connect to current understanding?
- What questions remain unresolved?
- What implications does this have?

*This reflection was triggered by LLM agency for deeper understanding*
"""

            # 4. Create reflection note with high importance
            importance = 0.85  # Higher importance for reflections

            # Create path: notes/{yyyy}/{mm}/{dd}/
            date_path = self.memory_base_path / "notes" / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"
            date_path.mkdir(parents=True, exist_ok=True)

            # Create filename
            time_prefix = timestamp.strftime("%H_%M_%S")
            topic_clean = topic[:30].replace(" ", "_").replace("/", "_").replace("?", "").replace("!", "")
            filename = f"{time_prefix}_reflection_{topic_clean}.md"
            file_path = date_path / filename

            # Create full markdown
            markdown_content = f"""# Reflection: {topic}

**Reflection ID**: `{reflection_id}`
**Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Type**: Deep Reflection (LLM-initiated)
**Importance**: {importance:.2f}

---

{reflection_content}

---

## Metadata

- **Created**: {timestamp.isoformat()}
- **Memory Type**: reflection
- **Related Memories**: {len(related_memories)}
- **Category**: reflection

---

*This is a deep reflection initiated by AI agency*
*Reflections help consolidate understanding and may update core memory*
"""

            # Write to filesystem
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            logger.info(f"Saved reflection: {file_path}")

            # Store in LanceDB with embedding
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
                    "linked_memory_ids": [mem.get("file_path", "") for mem in related_memories[:3]],
                    "tags": ["reflection", topic_clean],
                    "file_path": str(file_path),
                    "metadata": {
                        "created_by": "reflect_on",
                        "related_memories_count": len(related_memories),
                        "topic": topic
                    }
                }
                self.lancedb_storage.add_note(note_data)
                logger.info("Stored reflection in LanceDB")

            # TODO: Update core memory if insights are significant (Phase 3)

            return reflection_id

        except Exception as e:
            logger.error(f"Failed to create reflection: {e}")
            return f"reflection_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

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
            logger.info("Step 1/9: Semantic search")
            since = timestamp - timedelta(hours=config["hours"])
            semantic_memories = self.search_memories(
                query,
                filters={"user_id": user_id, "since": since},
                limit=config["limit"]
            )
            logger.info(f"  Found {len(semantic_memories)} semantic memories")

            # Step 2: Link exploration (expand via associations)
            logger.info(f"Step 2/9: Link exploration (depth={config['link_depth']})")
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
            logger.info(f"  Found {len(linked_memories)} linked memories")

            # Step 3: Library search (subconscious)
            logger.info("Step 3/9: Library search")
            library_excerpts = self.search_library(query, limit=3)
            logger.info(f"  Found {len(library_excerpts)} library documents")

            # Step 4: Emotional filtering (boost/filter by resonance)
            logger.info("Step 4/9: Emotional filtering")
            emotional_context = {
                "high_emotion_memories": [
                    m for m in semantic_memories
                    if m.get("emotion_intensity", 0) > 0.7
                ],
                "valence_distribution": self._calculate_valence_distribution(semantic_memories)
            }
            logger.info(f"  High-emotion memories: {len(emotional_context['high_emotion_memories'])}")

            # Step 5: Temporal context (what happened when?)
            logger.info("Step 5/9: Temporal context")
            temporal_context = {
                "time_of_day": timestamp.strftime("%H:%M"),
                "day_of_week": timestamp.strftime("%A"),
                "is_working_hours": 9 <= timestamp.hour < 18,
                "is_weekend": timestamp.weekday() >= 5,
                "recent_period": f"last {config['hours']} hours"
            }

            # Step 6: Spatial context (location-based)
            logger.info("Step 6/9: Spatial context")
            spatial_context = {
                "current_location": location,
                "location_type": self._infer_location_type(location),
                "location_memories": [
                    m for m in semantic_memories
                    if location.lower() in str(m.get("file_path", "")).lower()
                ]
            }

            # Step 7: User profile & relationship
            logger.info("Step 7/9: User profile & relationship")
            user_context = {
                "user_id": user_id,
                "profile": self.user_profiles.get(user_id, {}),
                "interaction_count": self.interactions_count,
                "relationship_status": self.core_memory.get("relationships", "developing")
            }

            # Step 8: Core memory (all 10 components)
            logger.info("Step 8/9: Core memory (10 components)")
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

            # Step 9: Context synthesis (combine all layers)
            logger.info("Step 9/9: Context synthesis")
            synthesized = self._synthesize_context(
                semantic_memories,
                linked_memories,
                library_excerpts,
                emotional_context,
                temporal_context,
                spatial_context,
                user_context,
                core_context,
                query
            )

            self.reconstructions_performed += 1

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
                "total_memories": len(semantic_memories) + len(linked_memories),
                "reconstruction_depth": config["link_depth"]
            }

            logger.info(f"Context reconstruction complete: {result['total_memories']} memories")
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
                           query: str) -> str:
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

        # User relationship
        if user_context.get("profile"):
            parts.append(f"[User]: {user_context['profile']}")

        # Temporal/spatial context
        parts.append(f"[Time]: {temporal_context['day_of_week']} {temporal_context['time_of_day']}")
        parts.append(f"[Location]: {spatial_context['current_location']} ({spatial_context['location_type']})")

        # Memory summary
        parts.append(f"[Memories]: {len(semantic_memories)} semantic, {len(linked_memories)} linked")

        # Emotional summary
        if emotional_context['high_emotion_memories']:
            parts.append(f"[High-emotion memories]: {len(emotional_context['high_emotion_memories'])}")

        # Library
        if library_excerpts:
            parts.append(f"[Library]: {len(library_excerpts)} relevant documents")

        # Key memories (top 3)
        if semantic_memories:
            parts.append("\n[Key Memories]:")
            for i, mem in enumerate(semantic_memories[:3], 1):
                content_preview = str(mem.get("content", ""))[:100].replace("\n", " ")
                parts.append(f"  {i}. {content_preview}...")

        return "\n".join(parts)

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