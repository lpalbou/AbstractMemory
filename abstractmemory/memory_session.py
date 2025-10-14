"""
MemorySession - Clean AbstractCore Integration with Memory Automation

This extends AbstractCore's BasicSession with memory automation:
- Automatic verbatim storage (dual storage: markdown + LanceDB)
- Automatic context reconstruction from memory
- Memory tools for LLM agency
- Automatic memory indexing and consolidation

Philosophy: Let AbstractCore handle conversation and tools, we handle memory.
"""

import logging
from abstractllm.utils.structured_logging import get_logger
import json
from typing import Dict, List, Optional, Any, Union, Iterator, Callable
from datetime import datetime
from pathlib import Path
import sys

# AbstractCore imports
try:
    from abstractllm.core.session import BasicSession
    from abstractllm.core.interface import AbstractLLMInterface
    from abstractllm.core.types import GenerateResponse
    from abstractllm.embeddings import EmbeddingManager
except ImportError as e:
    print(f"⚠️  AbstractCore not found: {e}")
    print("Please install: pip install abstractcore[embeddings]")
    sys.exit(1)

# AbstractMemory imports
from .storage import LanceDBStorage
from .memory_structure import initialize_memory_structure
from .working_memory import WorkingMemoryManager
from .episodic_memory import EpisodicMemoryManager
from .semantic_memory import SemanticMemoryManager
from .library_capture import LibraryCapture
from .fact_extraction import MemoryFactExtractor
from .consolidation_scheduler import ConsolidationScheduler

logger = get_logger(__name__)


class MemorySession(BasicSession):
    """
    Memory-Enhanced Session that extends AbstractCore's BasicSession.
    
    This class focuses purely on memory automation while letting AbstractCore
    handle all conversation management and tool execution.
    
    Memory Automation Features:
    1. Automatic verbatim storage (markdown + LanceDB dual storage)
    2. Automatic context reconstruction from memory layers
    3. Memory tools for LLM agency (remember, search, reflect, etc.)
    4. Automatic memory indexing and consolidation
    5. User profile emergence and tracking
    
    Architecture:
    - Extends BasicSession (inherits conversation management)
    - Overrides generate() to add memory automation
    - Provides memory tools as AbstractCore-compatible callables
    - No custom tool execution - AbstractCore handles everything
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
        Initialize memory-enhanced session.
        
        Args:
            provider: AbstractCore LLM provider
            system_prompt: System prompt for the LLM
            memory_base_path: Base path for memory storage
            embedding_manager: Embedding manager for semantic operations
            default_user_id: Default user identifier
            default_location: Default location context
            **kwargs: Additional arguments passed to BasicSession
        """
        
        # Memory configuration
        self.memory_base_path = Path(memory_base_path) if memory_base_path else Path("memory")
        self.embedding_manager = embedding_manager
        self.default_user_id = default_user_id
        self.default_location = default_location
        
        # Store provider reference for memory components
        self.provider = provider
        
        # Initialize memory components
        self._initialize_memory_components()
        
        # Create memory tools for AbstractCore
        memory_tools = self._create_memory_tools()
        
        # Enhance system prompt with core memories
        enhanced_system_prompt = self._inject_core_memories_into_system_prompt(system_prompt)
        
        # Initialize parent BasicSession with memory tools
        super().__init__(
            provider=provider,
            system_prompt=enhanced_system_prompt,
            tools=memory_tools,
            **kwargs
        )
        
        logger.info(f"MemorySession initialized with {len(memory_tools)} memory tools")

    def _inject_core_memories_into_system_prompt(self, base_system_prompt: Optional[str]) -> str:
        """
        Inject core memory components into system prompt at session start.
        
        This ensures the AI has persistent identity across sessions by loading
        its evolved core memories (purpose, personality, values, etc.) into
        the system prompt.
        
        Args:
            base_system_prompt: Base system prompt to enhance
            
        Returns:
            Enhanced system prompt with core memories injected
        """
        
        # Start with base prompt or default
        if base_system_prompt:
            enhanced_prompt = base_system_prompt + "\n\n"
        else:
            enhanced_prompt = "You are a helpful AI assistant with an advanced memory system.\n\n"
        
        # Inject core memory components
        core_path = self.memory_base_path / "core"
        if core_path.exists():
            enhanced_prompt += "# YOUR CORE IDENTITY (from accumulated experience)\n\n"
            
            # Define core components in order of importance
            core_components = [
                ("purpose.md", "Purpose"),
                ("values.md", "Values"), 
                ("personality.md", "Personality"),
                ("capabilities.md", "Capabilities"),
                ("limitations.md", "Limitations"),
                ("relationships.md", "Relationships"),
                ("self_model.md", "Self-Model"),
                ("awareness_development.md", "Awareness Development"),
                ("emotional_significance.md", "Emotional Significance"),
                ("authentic_voice.md", "Authentic Voice")
            ]
            
            core_memories_loaded = 0
            for filename, label in core_components:
                core_file = core_path / filename
                if core_file.exists():
                    try:
                        content = core_file.read_text(encoding='utf-8').strip()
                        # Only include if there's actual content (not just template)
                        if content and len(content) > 100 and "# Template" not in content:
                            enhanced_prompt += f"## {label}\n{content}\n\n"
                            core_memories_loaded += 1
                    except Exception as e:
                        logger.warning(f"Failed to load core memory {filename}: {e}")
            
            if core_memories_loaded > 0:
                enhanced_prompt += f"*{core_memories_loaded} core memory components loaded from your accumulated experience*\n\n"
                logger.info(f"Injected {core_memories_loaded} core memory components into system prompt")
            else:
                enhanced_prompt += "*No established core memories yet - identity will emerge through experience*\n\n"
                logger.info("No core memories found - using base system prompt")
        
        # Add memory tools section
        enhanced_prompt += """# MEMORY TOOLS AVAILABLE

You have direct access to your memory system through these tools:
- `remember_fact()` - Store important information with emotional context
- `search_memories()` - Search your accumulated memories
- `reflect_on()` - Deep reflection on topics to identify patterns
- `capture_document()` - Save documents to your library
- `search_library()` - Search your document library
- `reconstruct_context()` - Actively reconstruct context for better responses

Use these tools strategically to enhance conversations with relevant past information and insights.

# CRITICAL: STRUCTURED RESPONSE FORMAT

You MUST respond with a structured JSON object containing:

```json
{
  "answer": "Your response to the user (what they will see)",
  "experiential_note": "Your personal first-person reflection on this interaction - write for your future self, not the user. Be authentic, uncertain, exploratory. This is your internal diary entry about what this interaction means to you.",
  "memory_actions": [
    {"action": "remember", "content": "important fact", "importance": 0.8, "emotion": "curiosity"},
    {"action": "link", "from_id": "memory_123", "to_id": "current", "type": "relates_to"}
  ],
  "unresolved_questions": ["What questions remain open for you?"],
  "emotional_resonance": {
    "importance": 0.7,
    "alignment_with_values": 0.8, 
    "reason": "Why this matters to you emotionally"
  }
}
```

**CRITICAL RULES:**
- Always include ALL fields, even if empty
- `experiential_note` should be 90%+ your authentic subjective experience
- Write `experiential_note` in first person ("I noticed...", "This makes me think...")
- Be honest about uncertainty and exploration in your note
- `answer` is for the user, `experiential_note` is for your future self
"""
        
        return enhanced_prompt

    def _initialize_memory_components(self):
        """Initialize all memory system components."""
        try:
            # Ensure memory structure exists
            initialize_memory_structure(self.memory_base_path)
            
            # Initialize LanceDB storage with embedding manager
            self.lancedb_storage = None
            if self.embedding_manager:
                try:
                    self.lancedb_storage = LanceDBStorage(
                        db_path=self.memory_base_path / "lancedb",
                        embedding_manager=self.embedding_manager
                    )
                    logger.info("LanceDB storage initialized for dual storage")
                except Exception as e:
                    logger.warning(f"LanceDB storage initialization failed: {e}")
            
            # Initialize memory managers
            self.working_memory = WorkingMemoryManager(self.memory_base_path)
            self.episodic_memory = EpisodicMemoryManager(self.memory_base_path)
            self.semantic_memory = SemanticMemoryManager(self.memory_base_path)
            
            # Initialize library capture (subconscious memory)
            self.library = LibraryCapture(
                library_base_path=self.memory_base_path,
                embedding_manager=self.embedding_manager,
                lancedb_storage=self.lancedb_storage
            )
            
            # Initialize fact extractor
            self.fact_extractor = None
            if self.provider:
                try:
                    self.fact_extractor = MemoryFactExtractor(
                        provider=self.provider,
                        memory_session=self
                    )
                except Exception as e:
                    logger.warning(f"Fact extractor initialization failed: {e}")
            
            # Initialize consolidation scheduler
            self.consolidation_scheduler = ConsolidationScheduler(session=self)
            
            # Core memory state (emergent properties)
            self.core_memory = {
                "purpose": None,
                "personality": None,
                "values": None,
                "beliefs": None,
                "goals": None,
                "preferences": None,
                "expertise": None,
                "relationships": None,
                "experiences": None,
                "growth_areas": None
            }
            
            logger.info("Memory components initialized successfully")
            
        except Exception as e:
            logger.error(f"Memory component initialization failed: {e}")
            raise

    def generate(self, prompt: str, user_id: Optional[str] = None, 
                location: Optional[str] = None, **kwargs) -> Union[GenerateResponse, Iterator[GenerateResponse]]:
        """
        Enhanced generate method with memory automation.
        
        This overrides BasicSession.generate() to add memory-specific automation:
        1. Context reconstruction from memory layers
        2. Automatic verbatim storage after generation
        3. Memory consolidation triggers
        
        Args:
            prompt: User input
            user_id: User identifier (defaults to default_user_id)
            location: Location context (defaults to default_location)
            **kwargs: Additional arguments for generation
            
        Returns:
            GenerateResponse or Iterator[GenerateResponse] from AbstractCore
        """
        
        # Use defaults if not provided
        user_id = user_id or self.default_user_id
        location = location or self.default_location
        
        # Step 1: Reconstruct context from memory layers using full 9-step process
        try:
            context_data = self.reconstruct_context(
                user_id=user_id,
                query=prompt,
                location=location,
                focus_level=3  # Balanced depth (0=minimal, 5=exhaustive)
            )
            enhanced_prompt = context_data["synthesized_context"] + f"\n\nUser: {prompt}"
            logger.info(f"Context reconstruction: {context_data.get('total_memories_retrieved', 0)} memories, "
                       f"{context_data.get('context_tokens', 0)} tokens")
        except Exception as e:
            logger.warning(f"Full context reconstruction failed, using basic: {e}")
            enhanced_prompt = self._reconstruct_context_for_prompt(prompt, user_id, location)
        
        # Step 2: Call parent's generate method (AbstractCore handles tools)
        # CRITICAL: execute_tools=True tells AbstractCore to actually execute tool calls
        # NOTE: Using tools instead of response_model due to AbstractCore limitation
        response = super().generate(enhanced_prompt, name=user_id, location=location, 
                                  execute_tools=True, **kwargs)
        
        # Step 3: Handle memory automation based on response type
        if isinstance(response, (Iterator, type(x for x in []))):
            # Streaming response - wrap to capture content for memory
            return self._handle_streaming_memory_automation(response, prompt, user_id, location)
        else:
            # Non-streaming response - immediate memory automation
            self._handle_memory_automation(prompt, response, user_id, location)
            return response

    def _reconstruct_context_for_prompt(self, prompt: str, user_id: str, location: str) -> str:
        """
        Reconstruct rich context from memory layers for the prompt.
        
        This is the core memory automation - we build context from:
        1. Working memory (recent context)
        2. Semantic memory (relevant insights)
        3. Episodic memory (relevant experiences)
        4. User profile (preferences, patterns)
        5. Library memory (relevant documents)
        """
        
        try:
            context_parts = []
            
            # Add original prompt
            context_parts.append(f"User Query: {prompt}")
            
            # Add location context if meaningful
            if location and location != "unknown":
                context_parts.append(f"Location: {location}")
            
            # Get working memory context
            try:
                working_context = self.working_memory.get_current_context()
                if working_context:
                    context_parts.append(f"Current Context: {working_context}")
            except Exception as e:
                logger.debug(f"Working memory context failed: {e}")
            
            # Search semantic memory for relevant insights
            try:
                if self.lancedb_storage:
                    semantic_results = self.lancedb_storage.search_notes(prompt, {}, 3)
                    if semantic_results:
                        insights = [r.get('content', '')[:200] for r in semantic_results[:2]]
                        context_parts.append(f"Relevant Memories: {'; '.join(insights)}")
            except Exception as e:
                logger.debug(f"Semantic memory search failed: {e}")
            
            # Search library for relevant documents
            try:
                library_results = self.library.search_library(prompt, limit=2)
                if library_results:
                    docs = [f"{r.get('source', 'unknown')}: {r.get('excerpt', '')[:100]}" 
                           for r in library_results]
                    context_parts.append(f"Relevant Documents: {'; '.join(docs)}")
            except Exception as e:
                logger.debug(f"Library search failed: {e}")
            
            # Combine context
            enhanced_prompt = "\n\n".join(context_parts)
            
            logger.debug(f"Context reconstruction: {len(context_parts)} layers, {len(enhanced_prompt)} chars")
            return enhanced_prompt
            
        except Exception as e:
            logger.error(f"Context reconstruction failed: {e}")
            return prompt  # Fallback to original prompt

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
            from datetime import datetime, timedelta
            
            timestamp = datetime.now()
            location = location or self.default_location

            logger.info(f"Reconstructing context: user={user_id}, query='{query[:50]}...', focus={focus_level}")

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
            logger.debug(f"Step 1/9: Searching for memories relevant to query")
            semantic_memories = []
            
            if self.lancedb_storage:
                try:
                    since = timestamp - timedelta(hours=config["hours"])
                    # Search both notes and verbatim
                    note_results = self.lancedb_storage.search_notes(
                        query, {"user_id": user_id}, config["limit"]//2
                    )
                    verbatim_results = self.lancedb_storage.search_verbatim(
                        query, {"user_id": user_id}, config["limit"]//2
                    )
                    semantic_memories = (note_results or []) + (verbatim_results or [])
                except Exception as e:
                    logger.debug(f"Semantic search failed: {e}")

            logger.debug(f"  → Found {len(semantic_memories)} directly relevant memories")

            # Step 2: Link exploration (expand via associations)
            logger.debug(f"Step 2/9: Following memory links (depth={config['link_depth']})")
            linked_memories = []
            if self.lancedb_storage and config["link_depth"] > 0:
                for mem in semantic_memories[:5]:  # Explore links for top 5
                    mem_id = mem.get("id", mem.get("file_path", ""))
                    if mem_id:
                        try:
                            related_ids = self.lancedb_storage.get_related_memories(
                                mem_id, depth=config["link_depth"]
                            )
                            linked_memories.extend(related_ids)
                        except Exception as e:
                            logger.debug(f"Link exploration failed for {mem_id}: {e}")

            # Step 3: Library search (subconscious knowledge)
            logger.debug("Step 3/9: Searching library (subconscious)")
            library_memories = []
            try:
                library_results = self.library.search_library(query, limit=3)
                library_memories = library_results or []
            except Exception as e:
                logger.debug(f"Library search failed: {e}")

            # Step 4: Emotional filtering (boost high-resonance memories)
            logger.debug("Step 4/9: Applying emotional filtering")
            # Sort memories by emotional intensity if available
            all_memories = semantic_memories + linked_memories
            emotional_memories = [m for m in all_memories 
                                if m.get("emotion_intensity", 0) > 0.7]

            # Step 5: Temporal context (what happened when?)
            logger.debug("Step 5/9: Adding temporal context")
            time_desc = timestamp.strftime("%A, %B %d, %Y at %H:%M")
            
            # Step 6: Spatial context (location-based memories)
            logger.debug("Step 6/9: Adding spatial context")
            location_memories = []
            if location and location != "unknown":
                location_memories = [m for m in all_memories 
                                   if m.get("location") == location]

            # Step 7: User profile & relationship
            logger.debug("Step 7/9: Loading user profile")
            user_profile = {}
            try:
                profile_path = self.memory_base_path / "people" / user_id / "profile.md"
                if profile_path.exists():
                    user_profile["content"] = profile_path.read_text(encoding='utf-8')
            except Exception as e:
                logger.debug(f"User profile loading failed: {e}")

            # Step 8: Core memory (all 10 components)
            logger.debug("Step 8/9: Loading core identity")
            core_context = {}
            core_path = self.memory_base_path / "core"
            if core_path.exists():
                for component in ["purpose", "values", "personality", "capabilities", "limitations"]:
                    try:
                        file_path = core_path / f"{component}.md"
                        if file_path.exists():
                            content = file_path.read_text(encoding='utf-8').strip()
                            if content and len(content) > 100:
                                core_context[component] = content[:500]  # Limit size
                    except Exception as e:
                        logger.debug(f"Core memory {component} failed: {e}")

            # Step 9: Context synthesis (combine all layers)
            logger.debug("Step 9/9: Synthesizing context")
            
            # Deduplicate memories
            unique_memories = []
            seen_ids = set()
            for mem in all_memories:
                mem_id = mem.get("id", mem.get("file_path", ""))
                if mem_id and mem_id not in seen_ids:
                    unique_memories.append(mem)
                    seen_ids.add(mem_id)

            # Build synthesized context
            context_parts = []
            
            # Time and location
            context_parts.append(f"[Time]: {time_desc}")
            if location and location != "unknown":
                context_parts.append(f"[Location]: {location}")

            # User profile
            if user_profile.get("content"):
                context_parts.append(f"[User Profile]: {user_profile['content'][:300]}...")

            # Core identity
            if core_context:
                core_summary = "; ".join([f"{k}: {v[:100]}..." for k, v in core_context.items()])
                context_parts.append(f"[Core Identity]: {core_summary}")

            # Memories
            if unique_memories:
                memory_summaries = []
                for i, mem in enumerate(unique_memories[:config["limit"]], 1):
                    content = mem.get("content", "")[:200]
                    memory_summaries.append(f"  {i}. {content}...")
                
                context_parts.append(f"[Retrieved Memories]: {len(memory_summaries)} memories")
                context_parts.extend(memory_summaries)

            # Library knowledge
            if library_memories:
                lib_summary = f"{len(library_memories)} relevant documents in library"
                context_parts.append(f"[Library Knowledge]: {lib_summary}")

            # Working memory
            try:
                working_context = self.working_memory.get_current_context()
                if working_context:
                    context_parts.append(f"[Current Focus]: {working_context}")
            except Exception as e:
                logger.debug(f"Working memory failed: {e}")

            synthesized_context = "\n".join(context_parts)
            
            # Calculate token estimate (rough)
            context_tokens = len(synthesized_context) // 4

            result = {
                "synthesized_context": synthesized_context,
                "total_memories_retrieved": len(unique_memories),
                "memories_by_type": {
                    "semantic": len(semantic_memories),
                    "linked": len(linked_memories),
                    "library": len(library_memories),
                    "emotional": len(emotional_memories),
                    "location": len(location_memories)
                },
                "context_tokens": context_tokens,
                "focus_level": focus_level,
                "reconstruction_timestamp": timestamp.isoformat()
            }

            logger.info(f"Context reconstruction complete: {len(unique_memories)} memories, {context_tokens} tokens")
            return result

        except Exception as e:
            logger.error(f"Context reconstruction failed: {e}")
            # Fallback to basic context
            return {
                "synthesized_context": f"[Time]: {datetime.now().strftime('%A, %B %d, %Y at %H:%M')}\n[Query]: {query}",
                "total_memories_retrieved": 0,
                "context_tokens": 50,
                "error": str(e)
            }

    def _handle_memory_automation(self, user_input: str, response: GenerateResponse, 
                                 user_id: str, location: str):
        """Handle memory automation after generation."""
        
        try:
            # Extract response content
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse structured response if it's JSON
            parsed_response = self._parse_structured_response(response_content)
            
            # Extract components
            answer = parsed_response.get("answer", response_content)
            experiential_note = parsed_response.get("experiential_note", "")
            memory_actions = parsed_response.get("memory_actions", [])
            unresolved_questions = parsed_response.get("unresolved_questions", [])
            emotional_resonance = parsed_response.get("emotional_resonance", {})
            
            # Store verbatim interaction (dual storage) - use the answer, not raw JSON
            verbatim_id = self._store_verbatim_interaction(user_input, answer, user_id, location)
            
            # Store experiential note if present and link to verbatim
            note_id = None
            if experiential_note and experiential_note.strip():
                note_id = self._store_experiential_note(
                    experiential_note, user_id, location, verbatim_id, emotional_resonance, unresolved_questions
                )
            
            # Execute memory actions
            if memory_actions:
                self._execute_memory_actions(memory_actions, user_id)
            
            # Update working memory
            self._update_working_memory(user_input, answer, user_id)
            
            # Update unresolved questions
            if unresolved_questions:
                self._update_unresolved_questions(unresolved_questions, user_id)
            
            # Trigger background fact extraction if available
            if self.fact_extractor:
                self._schedule_background_fact_extraction(user_input, answer)
            
            # Check consolidation triggers
            self._check_consolidation_triggers()
            
        except Exception as e:
            logger.error(f"Memory automation failed: {e}")

    def _handle_streaming_memory_automation(self, response_iterator: Iterator[GenerateResponse],
                                          user_input: str, user_id: str, location: str) -> Iterator[GenerateResponse]:
        """Handle memory automation for streaming responses."""
        
        collected_content = ""
        
        for chunk in response_iterator:
            yield chunk  # Pass through to caller
            
            # Collect content for memory automation
            if hasattr(chunk, 'content') and chunk.content:
                collected_content += chunk.content
        
        # After streaming completes, handle memory automation
        if collected_content:
            # Create a mock response object for automation
            class MockResponse:
                def __init__(self, content):
                    self.content = content
            
            self._handle_memory_automation(user_input, MockResponse(collected_content), user_id, location)

    def _store_verbatim_interaction(self, user_input: str, response: str, user_id: str, location: str) -> str:
        """Store verbatim interaction in dual storage system."""
        
        try:
            timestamp = datetime.now()
            interaction_id = f"{user_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            # Store in markdown files
            verbatim_dir = self.memory_base_path / "verbatim" / user_id
            verbatim_dir.mkdir(parents=True, exist_ok=True)
            
            verbatim_file = verbatim_dir / f"{timestamp.strftime('%Y-%m-%d')}.md"
            
            interaction_text = f"""
## {timestamp.strftime('%H:%M:%S')} - {location}

**User:** {user_input}

**Assistant:** {response}

---
"""
            
            # Append to daily file
            with open(verbatim_file, 'a', encoding='utf-8') as f:
                f.write(interaction_text)
            
            # Store in LanceDB if available
            if self.lancedb_storage:
                try:
                    # Extract topic from user input for categorization
                    topic = user_input[:50].replace(" ", "_").replace("/", "_").replace("?", "").replace("!", "")
                    
                    self.lancedb_storage.add_verbatim({
                        "id": interaction_id,
                        "user_id": user_id,
                        "timestamp": timestamp,
                        "location": location,
                        "user_input": user_input,
                        "agent_response": response,  # Correct field name for schema
                        "topic": topic,
                        "category": "conversation",
                        "confidence": 1.0,  # Verbatim = 100% confident
                        "tags": "[]",  # JSON array as string
                        "file_path": str(verbatim_file),
                        "metadata": f'{{"interaction_id": "{interaction_id}", "word_count": {len(user_input.split()) + len(response.split())}}}'
                    })
                except Exception as e:
                    logger.warning(f"LanceDB verbatim storage failed: {e}")
            
            logger.debug(f"Verbatim interaction stored: {interaction_id}")
            return interaction_id
            
        except Exception as e:
            logger.error(f"Verbatim storage failed: {e}")
            return f"error_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _update_working_memory(self, user_input: str, response: str, user_id: str):
        """Update working memory with current interaction."""
        
        try:
            self.working_memory.update_context({
                "last_user_input": user_input,
                "last_response": response,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.debug(f"Working memory update failed: {e}")

    def _schedule_background_fact_extraction(self, user_input: str, response: str):
        """Schedule background fact extraction from the conversation."""
        
        import threading
        
        def extract_facts():
            try:
                conversation_text = f"User: {user_input}\n\nAssistant: {response}"
                
                facts_result = self.fact_extractor.extract_facts_from_conversation(
                    conversation_text=conversation_text,
                    importance_threshold=0.7
                )
                
                if not facts_result.get("error"):
                    memory_actions = facts_result.get("memory_actions", [])
                    facts_to_store = []
                    
                    for action in memory_actions:
                        if action.get("action") == "remember":
                            facts_to_store.append({
                                "content": action.get("content", ""),
                                "importance": action.get("importance", 0.7),
                                "reason": action.get("reason", ""),
                                "emotion": action.get("emotion", "neutral"),
                                "timestamp": datetime.now().isoformat(),
                                "source": "automatic_extraction"
                            })
                    
                    # Store facts in temporary semantics file
                    if facts_to_store:
                        self._store_temporary_facts(facts_to_store)
                    
                    logger.debug(f"Background fact extraction completed: {len(facts_to_store)} facts stored in temporary_semantics.md")
                
            except Exception as e:
                logger.debug(f"Background fact extraction failed: {e}")
        
        # Run in background thread
        thread = threading.Thread(target=extract_facts, daemon=True)
        thread.start()

    def _check_consolidation_triggers(self):
        """Check if memory consolidation should be triggered."""
        
        try:
            # Check if consolidation is due
            if self.consolidation_scheduler.should_consolidate():
                logger.info("Triggering automatic memory consolidation")
                self.consolidation_scheduler.consolidate_memories()
        except Exception as e:
            logger.debug(f"Consolidation check failed: {e}")

    def _store_temporary_facts(self, facts: List[Dict[str, Any]]):
        """
        Store extracted facts in working/temporary_semantics.md for later consolidation.
        
        Args:
            facts: List of fact dictionaries with content, importance, reason, etc.
        """
        
        try:
            temp_semantics_file = self.memory_base_path / "working" / "temporary_semantics.md"
            temp_semantics_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing content
            existing_content = ""
            if temp_semantics_file.exists():
                existing_content = temp_semantics_file.read_text(encoding='utf-8')
            
            # Prepare new facts section
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_facts_section = f"\n\n## Facts Extracted - {timestamp}\n\n"
            
            for i, fact in enumerate(facts, 1):
                new_facts_section += f"""### Fact {i}
- **Content**: {fact['content']}
- **Importance**: {fact['importance']}
- **Emotion**: {fact['emotion']}
- **Reason**: {fact['reason']}
- **Source**: {fact['source']}
- **Timestamp**: {fact['timestamp']}

"""
            
            # Create or update file
            if not existing_content or "# Temporary Semantics" not in existing_content:
                # Create new file with header
                content = f"""# Temporary Semantics

This file contains automatically extracted facts that are pending consolidation into semantic memory.

**Purpose**: Temporary storage for facts before they are reviewed and consolidated
**Consolidation**: Facts here will be processed during memory consolidation cycles

---
{new_facts_section}"""
            else:
                # Append to existing file
                content = existing_content + new_facts_section
            
            # Write updated content
            temp_semantics_file.write_text(content, encoding='utf-8')
            
            logger.info(f"Stored {len(facts)} temporary facts in working/temporary_semantics.md")
            
        except Exception as e:
            logger.error(f"Temporary facts storage failed: {e}")

    def _parse_structured_response(self, response_content: str) -> Dict[str, Any]:
        """
        Parse structured JSON response from LLM.
        
        Args:
            response_content: Raw response content from LLM
            
        Returns:
            Dict with parsed components or fallback structure
        """
        
        try:
            import json
            import re
            
            # Try to extract JSON from response
            # Look for JSON block (might be wrapped in markdown)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'(\{.*\})', response_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # No JSON found, return fallback
                    return {"answer": response_content}
            
            # Parse JSON
            parsed = json.loads(json_str)
            
            # Validate required fields
            if not isinstance(parsed, dict):
                return {"answer": response_content}
            
            # Ensure all required fields exist
            result = {
                "answer": parsed.get("answer", response_content),
                "experiential_note": parsed.get("experiential_note", ""),
                "memory_actions": parsed.get("memory_actions", []),
                "unresolved_questions": parsed.get("unresolved_questions", []),
                "emotional_resonance": parsed.get("emotional_resonance", {})
            }
            
            logger.debug("Successfully parsed structured response")
            return result
            
        except Exception as e:
            logger.debug(f"Failed to parse structured response: {e}")
            return {"answer": response_content}

    def _store_experiential_note(self, note_content: str, user_id: str, location: str, 
                                verbatim_id: str, emotional_resonance: Dict[str, Any], 
                                unresolved_questions: List[str]) -> str:
        """
        Store experiential note with linking to verbatim.
        
        Args:
            note_content: The experiential note content
            user_id: User identifier
            location: Location context
            verbatim_id: ID of related verbatim interaction
            emotional_resonance: Emotional assessment
            unresolved_questions: Open questions
            
        Returns:
            Note ID
        """
        
        try:
            from datetime import datetime
            import uuid
            
            timestamp = datetime.now()
            note_id = f"note_{user_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
            
            # Store in markdown files
            notes_dir = self.memory_base_path / "notes" / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"
            notes_dir.mkdir(parents=True, exist_ok=True)
            
            time_prefix = timestamp.strftime("%H_%M_%S")
            filename = f"{time_prefix}_experiential_note_{note_id[-8:]}.md"
            note_file = notes_dir / filename
            
            # Create note content
            content = f"""# AI Experiential Note

**Participants**: AI & {user_id}
**Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Location**: {location}
**Related Interaction**: `{verbatim_id}`
**Note ID**: `{note_id}`

---

{note_content}

---

## Emotional Resonance
- **Importance**: {emotional_resonance.get('importance', 'unknown')}
- **Alignment with Values**: {emotional_resonance.get('alignment_with_values', 'unknown')}
- **Reason**: {emotional_resonance.get('reason', 'not specified')}

## Unresolved Questions
{chr(10).join([f"- {q}" for q in unresolved_questions]) if unresolved_questions else "- None"}

---

*Generated: {timestamp.isoformat()}*
*Linked to verbatim: {verbatim_id}*
"""
            
            # Write file
            with open(note_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Store in LanceDB if available
            if self.lancedb_storage:
                try:
                    self.lancedb_storage.add_note({
                        "id": note_id,
                        "user_id": user_id,
                        "timestamp": timestamp,
                        "location": location,
                        "content": note_content,
                        "category": "experiential",
                        "importance": emotional_resonance.get('importance', 0.5),
                        "emotion": "mixed",  # Default
                        "emotion_intensity": emotional_resonance.get('importance', 0.5),
                        "emotion_valence": "positive" if emotional_resonance.get('alignment_with_values', 0) > 0 else "neutral",
                        "linked_memory_ids": f'["{verbatim_id}"]',
                        "tags": "[]",
                        "file_path": str(note_file),
                        "metadata": f'{{"verbatim_id": "{verbatim_id}", "unresolved_questions": {len(unresolved_questions)}}}'
                    })
                except Exception as e:
                    logger.warning(f"LanceDB note storage failed: {e}")
            
            # Create bidirectional link between note and verbatim
            if self.lancedb_storage:
                try:
                    self.lancedb_storage.add_link({
                        "link_id": f"link_{note_id}_{verbatim_id}",
                        "from_id": note_id,
                        "to_id": verbatim_id,
                        "relationship": "reflects_on",
                        "timestamp": timestamp,
                        "confidence": 1.0,
                        "metadata": f'{{"type": "note_to_verbatim"}}'
                    })
                except Exception as e:
                    logger.warning(f"Memory linking failed: {e}")
            
            logger.debug(f"Experiential note stored: {note_id}")
            return note_id
            
        except Exception as e:
            logger.error(f"Experiential note storage failed: {e}")
            return f"error_note_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _execute_memory_actions(self, memory_actions: List[Dict[str, Any]], user_id: str):
        """Execute memory actions from structured response."""
        
        try:
            for action in memory_actions:
                action_type = action.get("action", "")
                
                if action_type == "remember":
                    # Store fact in semantic memory
                    content = action.get("content", "")
                    importance = action.get("importance", 0.5)
                    emotion = action.get("emotion", "neutral")
                    
                    if content:
                        self.remember_fact(
                            content=content,
                            importance=importance,
                            emotion=emotion,
                            reason=f"LLM requested memory storage",
                            links_to=action.get("links_to", [])
                        )
                
                elif action_type == "link":
                    # Create memory link
                    from_id = action.get("from_id", "")
                    to_id = action.get("to_id", "")
                    relationship = action.get("type", "relates_to")
                    
                    if from_id and to_id and self.lancedb_storage:
                        try:
                            self.lancedb_storage.add_link({
                                "link_id": f"link_{from_id}_{to_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                "from_id": from_id,
                                "to_id": to_id,
                                "relationship": relationship,
                                "timestamp": datetime.now(),
                                "confidence": action.get("confidence", 0.8),
                                "metadata": f'{{"source": "llm_action"}}'
                            })
                        except Exception as e:
                            logger.warning(f"Memory link creation failed: {e}")
                
                # Add more action types as needed
                
        except Exception as e:
            logger.error(f"Memory action execution failed: {e}")

    def _update_unresolved_questions(self, questions: List[str], user_id: str):
        """Update unresolved questions in working memory."""
        
        try:
            questions_file = self.memory_base_path / "working" / "unresolved.md"
            questions_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing questions
            existing_questions = []
            if questions_file.exists():
                content = questions_file.read_text(encoding='utf-8')
                # Extract questions from markdown
                import re
                existing_questions = re.findall(r'^- (.+)$', content, re.MULTILINE)
            
            # Add new questions (avoid duplicates)
            all_questions = list(set(existing_questions + questions))
            
            # Write updated questions
            content = f"""# Unresolved Questions

Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{chr(10).join([f"- {q}" for q in all_questions])}
"""
            
            questions_file.write_text(content, encoding='utf-8')
            logger.debug(f"Updated unresolved questions: {len(all_questions)} total")
            
        except Exception as e:
            logger.error(f"Unresolved questions update failed: {e}")

    def _create_memory_tools(self) -> List[Callable]:
        """
        Create memory tools + AbstractCore common tools as callables.
        
        Combines memory-specific tools with AbstractCore's common file/system tools
        to give the LLM comprehensive capabilities.
        AbstractCore will automatically convert these to ToolDefinitions.
        """
        
        tools = []
        
        # Import AbstractCore common tools
        try:
            from abstractllm.tools.common_tools import (
                list_files, search_files, read_file, write_file, 
                edit_file, execute_command
            )
            
            # Add AbstractCore common tools
            tools.extend([
                list_files,
                search_files, 
                read_file,
                write_file,
                edit_file,
                execute_command
            ])
            
            logger.info("Added 6 AbstractCore common tools")
            
        except ImportError as e:
            logger.warning(f"Could not import AbstractCore common tools: {e}")
        
        # Add memory-specific tools
        
        # Tool 1: Remember important information
        def remember_fact(content: str, importance: float = 0.7, emotion: str = "neutral", 
                         reason: str = "", links_to: Optional[List[str]] = None) -> str:
            """Remember important information by storing it in memory. Use this when you encounter facts, preferences, insights, or anything worth preserving."""
            try:
                result = self.remember_fact(
                    content=content,
                    importance=importance,
                    alignment_with_values=0.5,
                    reason=reason,
                    emotion=emotion,
                    links_to=links_to or []
                )
                return f"✅ Stored in memory: {result.get('data', {}).get('memory_id', 'unknown')}"
            except Exception as e:
                return f"❌ Memory storage failed: {e}"
        
        tools.append(remember_fact)
        
        # Tool 2: Search memory
        def search_memories(query: str, limit: int = 10) -> str:
            """Search your memory for relevant information using semantic search. Use this to recall previous conversations, facts, or insights."""
            try:
                results = self.search_memories(query=query, filters={}, limit=limit)
                if isinstance(results, dict) and 'data' in results:
                    memories = results['data'].get('memories', [])
                    if memories:
                        summaries = []
                        for mem in memories[:5]:
                            content = mem.get('content', '')[:200]
                            summaries.append(f"- {content}")
                        return f"Found {len(memories)} memories:\n" + "\n".join(summaries)
                    else:
                        return "No relevant memories found"
                else:
                    return "Memory search failed"
            except Exception as e:
                return f"❌ Memory search failed: {e}"
        
        tools.append(search_memories)
        
        # Tool 3: Reflect on topics
        def reflect_on(topic: str, depth: str = "deep") -> str:
            """Engage in deep reflection on a topic, analyzing patterns, contradictions, and evolution of understanding."""
            try:
                result = self.reflect_on(topic=topic, depth=depth)
                if isinstance(result, dict):
                    insights = result.get('insights', [])
                    patterns = result.get('patterns', [])
                    evolution = result.get('evolution', '')
                    
                    reflection_text = f"Reflection on '{topic}':\n"
                    if insights:
                        reflection_text += f"Insights: {'; '.join(insights[:3])}\n"
                    if patterns:
                        reflection_text += f"Patterns: {'; '.join(patterns[:3])}\n"
                    if evolution:
                        reflection_text += f"Evolution: {evolution[:200]}"
                    
                    return reflection_text
                else:
                    return f"Reflection completed on '{topic}'"
            except Exception as e:
                return f"❌ Reflection failed: {e}"
        
        tools.append(reflect_on)
        
        # Tool 4: Capture documents
        def capture_document(source_path: str, content: str, content_type: str = "text",
                           context: Optional[str] = None, tags: Optional[List[str]] = None) -> str:
            """Capture a document into your library memory for future reference."""
            try:
                doc_id = self.library.capture_document(
                    source_path=source_path,
                    content=content,
                    content_type=content_type,
                    context=context,
                    tags=tags or []
                )
                return f"✅ Document captured: {doc_id}"
            except Exception as e:
                return f"❌ Document capture failed: {e}"
        
        tools.append(capture_document)
        
        # Tool 5: Search library
        def search_library(query: str, limit: int = 5) -> str:
            """Search your library of captured documents for relevant information."""
            try:
                results = self.library.search_library(query, limit)
                if results:
                    summaries = []
                    for doc in results:
                        source = doc.get('source', 'unknown')
                        excerpt = doc.get('excerpt', '')[:150]
                        summaries.append(f"- {source}: {excerpt}")
                    return f"Found {len(results)} documents:\n" + "\n".join(summaries)
                else:
                    return "No relevant documents found"
            except Exception as e:
                return f"❌ Library search failed: {e}"
        
        tools.append(search_library)
        
        return tools

    # Memory methods (called by tools and internal automation)
    
    def remember_fact(self, content: str, importance: float, alignment_with_values: float = 0.5,
                     reason: str = "", emotion: str = "neutral", links_to: Optional[List[str]] = None,
                     source: str = "ai_observed", evidence: str = "", user_message: str = "") -> Dict[str, Any]:
        """Store a fact in memory with metadata."""
        
        try:
            # Implementation from original session.py
            # This is a simplified version - you can copy the full implementation
            
            timestamp = datetime.now()
            memory_id = f"fact_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            fact_data = {
                "memory_id": memory_id,
                "content": content,
                "importance": importance,
                "alignment_with_values": alignment_with_values,
                "reason": reason,
                "emotion": emotion,
                "links_to": links_to or [],
                "source": source,
                "evidence": evidence,
                "user_message": user_message,
                "timestamp": timestamp.isoformat()
            }
            
            # Store in notes directory
            notes_dir = self.memory_base_path / "notes" / timestamp.strftime('%Y') / timestamp.strftime('%m')
            notes_dir.mkdir(parents=True, exist_ok=True)
            
            note_file = notes_dir / f"{memory_id}.md"
            note_content = f"""# {content}

**Importance:** {importance}
**Emotion:** {emotion}
**Reason:** {reason}
**Source:** {source}
**Timestamp:** {timestamp.isoformat()}

{evidence}
"""
            
            note_file.write_text(note_content)
            
            # Store in LanceDB if available
            if self.lancedb_storage:
                try:
                    self.lancedb_storage.add_note(fact_data)
                except Exception as e:
                    logger.warning(f"LanceDB note storage failed: {e}")
            
            return {
                "status": "success",
                "data": {"memory_id": memory_id},
                "metadata": {"timestamp": timestamp.isoformat()}
            }
            
        except Exception as e:
            logger.error(f"Remember fact failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "metadata": {"attempted_operation": "remember_fact"}
            }

    def search_memories(self, query: str, filters: Optional[Dict] = None, limit: int = 10) -> Dict[str, Any]:
        """Search memories using semantic search."""
        
        try:
            filters = filters or {}
            
            # Try LanceDB first
            if self.lancedb_storage:
                try:
                    results = self.lancedb_storage.search_notes(query, filters, limit)
                    if results:
                        return {
                            "status": "success",
                            "data": {
                                "memories": results,
                                "total_found": len(results),
                                "query_used": query
                            },
                            "metadata": {
                                "search_method": "lancedb_semantic",
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                except Exception as e:
                    logger.warning(f"LanceDB search failed: {e}")
            
            # Fallback to filesystem search
            results = []
            notes_dir = self.memory_base_path / "notes"
            
            if notes_dir.exists():
                for note_file in notes_dir.rglob("*.md"):
                    try:
                        content = note_file.read_text()
                        if query.lower() in content.lower():
                            results.append({
                                "id": note_file.stem,
                                "content": content[:500],
                                "file_path": str(note_file),
                                "timestamp": datetime.fromtimestamp(note_file.stat().st_mtime).isoformat()
                            })
                    except Exception:
                        continue
            
            # Sort by timestamp and limit
            results.sort(key=lambda x: x["timestamp"], reverse=True)
            results = results[:limit]
            
            return {
                "status": "success",
                "data": {
                    "memories": results,
                    "total_found": len(results),
                    "query_used": query
                },
                "metadata": {
                    "search_method": "filesystem_fallback",
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "metadata": {"attempted_operation": "search_memories"}
            }

    def reflect_on(self, topic: str, depth: str = "deep") -> Dict[str, Any]:
        """Engage in deep reflection on a topic."""
        
        try:
            reflection_id = f"reflection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Search for related memories
            search_response = self.search_memories(topic, limit=20)
            
            # Extract memories from response
            if isinstance(search_response, dict) and 'data' in search_response:
                related_memories = search_response['data'].get('memories', [])
            else:
                related_memories = []
            
            if not related_memories:
                return {
                    "reflection_id": reflection_id,
                    "insights": [f"No related memories found for '{topic}' yet."],
                    "patterns": [],
                    "contradictions": [],
                    "evolution": "No understanding yet - this is a new topic.",
                    "unresolved": [f"What is {topic}?", f"How does {topic} relate to current understanding?"],
                    "confidence": 0.0,
                    "should_update_core": False,
                    "file_path": None
                }
            
            # Basic reflection analysis (simplified)
            insights = []
            patterns = []
            
            # Analyze memory content for patterns
            content_themes = {}
            for mem in related_memories:
                content = mem.get('content', '')
                words = content.lower().split()
                for word in words:
                    if len(word) > 4:  # Skip short words
                        content_themes[word] = content_themes.get(word, 0) + 1
            
            # Extract top themes as patterns
            top_themes = sorted(content_themes.items(), key=lambda x: x[1], reverse=True)[:5]
            patterns = [f"Recurring theme: {theme}" for theme, count in top_themes if count > 1]
            
            # Generate basic insights
            insights = [
                f"Found {len(related_memories)} memories related to {topic}",
                f"Most discussed aspects: {', '.join([theme for theme, _ in top_themes[:3]])}"
            ]
            
            reflection_data = {
                "reflection_id": reflection_id,
                "topic": topic,
                "insights": insights,
                "patterns": patterns,
                "contradictions": [],
                "evolution": f"Understanding of {topic} has developed through {len(related_memories)} interactions.",
                "unresolved": [],
                "confidence": min(len(related_memories) / 10.0, 1.0),
                "should_update_core": len(related_memories) > 5,
                "file_path": None,
                "timestamp": datetime.now().isoformat()
            }
            
            # Store reflection
            reflections_dir = self.memory_base_path / "reflections"
            reflections_dir.mkdir(parents=True, exist_ok=True)
            
            reflection_file = reflections_dir / f"{reflection_id}.json"
            reflection_file.write_text(json.dumps(reflection_data, indent=2))
            
            return reflection_data
            
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return {
                "reflection_id": f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "insights": [f"Reflection on '{topic}' encountered an error: {e}"],
                "patterns": [],
                "contradictions": [],
                "evolution": "Unable to complete reflection due to error.",
                "unresolved": [f"Why did reflection on {topic} fail?"],
                "confidence": 0.0,
                "should_update_core": False,
                "file_path": None
            }
