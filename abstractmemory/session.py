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
            # For now, assume neutral alignment (0.5) until values emerge
            alignment = 0.5
            emotion_intensity = importance * alignment

            # Create markdown content
            markdown_content = f"""# Memory: {topic}

**Memory ID**: `{memory_id}`
**Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Importance**: {importance:.2f}
**Emotion**: {emotion}
**Emotion Intensity**: {emotion_intensity:.2f}

---

## Content

{content}

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

            # TODO: Store in LanceDB with embedding (Phase 2+)
            # TODO: Calculate full emotional resonance using actual values

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

        For now, implements filesystem-based text search.
        Full semantic search with LanceDB will be added in Phase 2+.

        Args:
            query: Search query
            filters: Optional filters (category, user_id, since, until, etc.)
            limit: Max results

        Returns:
            List of matching memories with metadata
        """
        try:
            filters = filters or {}
            results = []

            logger.info(f"Searching memories: query='{query}', filters={filters}")

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

            logger.info(f"Library search complete: {len(results)} results")

            # TODO: Use LanceDB library_table for semantic search (Phase 2+)
            # TODO: Calculate importance_score from access patterns + emotion

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

            # TODO: Store in LanceDB links_table (Phase 2+)

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

            # TODO: Store in LanceDB with embedding (Phase 2+)
            # TODO: Update core memory if insights are significant

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