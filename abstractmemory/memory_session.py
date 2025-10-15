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
    from abstractllm.tools import tool
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
from .task_queue import TaskQueue
from .understanding_evolution import UnderstandingEvolutionDetector
from .storage.knowledge_graph import KnowledgeGraphStorage
from .triple_storage_manager import TripleStorageManager

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
        
        # Ensure embedding cache is saved to the correct location
        if self.embedding_manager and hasattr(self.embedding_manager, 'save_caches'):
            # Register cleanup to save cache in the correct location
            import atexit
            atexit.register(self._cleanup_embedding_cache)
        
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
            
            # Initialize Phase 1 components: Knowledge Graph and Understanding Evolution
            self.knowledge_graph = None
            self.understanding_detector = None
            self.triple_storage_manager = None
            
            try:
                # Initialize Knowledge Graph Storage
                self.knowledge_graph = KnowledgeGraphStorage(
                    storage_path=self.memory_base_path / "knowledge_graph"
                )
                logger.info("Knowledge Graph Storage initialized")
                
                # Initialize Understanding Evolution Detector
                if self.provider:
                    self.understanding_detector = UnderstandingEvolutionDetector(
                        memory_session=self,
                        llm_provider=self.provider
                    )
                    logger.info("Understanding Evolution Detector initialized")
                
                # Initialize Triple Storage Manager
                if self.lancedb_storage and self.knowledge_graph:
                    self.triple_storage_manager = TripleStorageManager(
                        base_path=self.memory_base_path,
                        embedding_manager=self.embedding_manager,
                        lancedb_storage=self.lancedb_storage,
                        knowledge_graph=self.knowledge_graph
                    )
                    logger.info("Triple Storage Manager initialized - Phase 1 complete!")
                
            except Exception as e:
                logger.warning(f"Phase 1 components initialization failed: {e}")
                logger.info("Continuing with basic memory functionality")
            
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
            
            # Initialize task queue
            try:
                queue_file = self.memory_base_path / "task_queue.json"
                self.task_queue = TaskQueue(
                    queue_file=queue_file,
                    notification_callback=getattr(self, '_notification_callback', None)
                )
                logger.info("Task queue initialized")
            except Exception as e:
                logger.error(f"Task queue initialization failed: {e}")
                self.task_queue = None
            
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
        
        logger.debug(f"MemorySession.generate called with prompt length: {len(prompt)}")
        logger.debug(f"User ID: {user_id}, Location: {location}")
        
        # Step 1: Reconstruct context from memory layers using full 9-step process
        logger.debug("Step 1: Starting context reconstruction...")
        try:
            context_data = self.reconstruct_context(
                user_id=user_id,
                query=prompt,
                location=location,
                focus_level=3  # Balanced depth (0=minimal, 5=exhaustive)
            )
            enhanced_prompt = context_data["synthesized_context"] + f"\n\nUser: {prompt}"
            logger.debug(f"Context reconstruction complete. Enhanced prompt length: {len(enhanced_prompt)}")
            logger.info(f"Context reconstruction: {context_data.get('total_memories_retrieved', 0)} memories, "
                       f"{context_data.get('context_tokens', 0)} tokens")
        except Exception as e:
            logger.warning(f"Full context reconstruction failed, using basic: {e}")
            enhanced_prompt = self._reconstruct_context_for_prompt(prompt, user_id, location)
            logger.debug(f"Basic context reconstruction complete. Enhanced prompt length: {len(enhanced_prompt)}")
        
        # Step 2: Call parent's generate method (AbstractCore handles tools)
        # CRITICAL: execute_tools=True tells AbstractCore to actually execute tool calls
        # NEW in 2.3.5: Can now use both tools AND response_model simultaneously!
        from .memory_response_models import MemoryResponse
        
        # Ensure non-streaming for structured responses (unless explicitly requested)
        if 'stream' not in kwargs:
            kwargs['stream'] = False
        
        logger.debug(f"Step 2: Calling BasicSession.generate...")
        logger.debug(f"Parameters: execute_tools=True, response_model=MemoryResponse, stream={kwargs.get('stream', False)}")
        
        response = super().generate(
            enhanced_prompt, 
            name=user_id, 
            location=location,
            execute_tools=True,
            response_model=MemoryResponse,
            **kwargs
        )
        
        logger.debug(f"BasicSession.generate returned. Response type: {type(response)}")
        logger.debug(f"Response is generator: {hasattr(response, '__iter__') and hasattr(response, '__next__')}")
        
        
        # Step 3: Handle memory automation based on response type
        logger.debug("Step 3: Starting memory automation...")
        from .memory_response_models import MemoryResponse
        
        if isinstance(response, MemoryResponse):
            logger.debug("Response is MemoryResponse - handling direct structured response")
            # Direct structured response - immediate memory automation
            self._handle_memory_automation(prompt, response, user_id, location)
            logger.debug("Memory automation complete for MemoryResponse")
            return response
        elif hasattr(response, '__iter__') and hasattr(response, '__next__'):
            logger.debug("Response is generator - handling structured generator response")
            # BasicSession returns a generator of (field, value) tuples for structured responses
            # We need to reconstruct the MemoryResponse and handle memory automation
            result = self._handle_structured_generator_response(response, prompt, user_id, location)
            logger.debug(f"Generator response handling complete, returning: {type(result)}")
            logger.debug("About to return from MemorySession.generate...")
            return result
        else:
            logger.debug(f"Response is GenerateResponse - handling non-structured response: {type(response)}")
            # Non-streaming GenerateResponse - immediate memory automation
            self._handle_memory_automation(prompt, response, user_id, location)
            logger.debug("Memory automation complete for GenerateResponse")
            return response

    def _handle_structured_generator_response(self, response_generator, prompt: str, user_id: str, location: str):
        """
        Handle BasicSession's structured response generator.
        
        BasicSession deconstructs MemoryResponse into (field, value) tuples.
        We reconstruct the MemoryResponse, handle memory automation, and return it.
        """
        
        logger.debug("Starting structured generator response handling...")
        
        try:
            from .memory_response_models import MemoryResponse
            
            # Collect all field-value pairs from the generator
            logger.debug("Collecting field-value pairs from generator...")
            response_data = {}
            field_count = 0
            
            try:
                while True:
                    try:
                        field, value = next(response_generator)
                        logger.debug(f"Received field: {field}, value type: {type(value)}")
                        response_data[field] = value
                        field_count += 1
                    except StopIteration as e:
                        logger.debug(f"Generator exhausted. Return value: {e.value}")
                        # Check if there's a return value from the generator
                        if hasattr(e, 'value') and e.value is not None:
                            logger.debug(f"Generator returned: {e.value}")
                        break
            except Exception as e:
                logger.error(f"Error consuming generator: {e}")
                import traceback
                traceback.print_exc()
            
            logger.debug(f"Collected {field_count} fields from generator: {list(response_data.keys())}")
            
            # Reconstruct the MemoryResponse
            logger.debug("Reconstructing MemoryResponse from collected data...")
            logger.debug(f"Response data keys: {list(response_data.keys())}")
            
            try:
                structured_response = MemoryResponse(**response_data)
                logger.debug("MemoryResponse reconstructed successfully")
            except Exception as e:
                logger.error(f"Failed to reconstruct MemoryResponse: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Handle memory automation
            logger.debug("Starting memory automation for reconstructed response...")
            try:
                self._handle_memory_automation(prompt, structured_response, user_id, location)
                logger.debug("Memory automation complete for reconstructed response")
            except Exception as e:
                logger.error(f"Memory automation failed: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            logger.debug("About to return structured response...")
            logger.debug(f"Structured response type: {type(structured_response)}")
            logger.debug(f"Structured response answer length: {len(structured_response.answer) if structured_response.answer else 0}")
            result = structured_response
            logger.debug("Returning from _handle_structured_generator_response...")
            return result
            
        except Exception as e:
            logger.error(f"Failed to reconstruct structured response from generator: {e}")
            # Fallback: return a basic response
            from .memory_response_models import MemoryResponse
            return MemoryResponse(
                answer="I apologize, but I encountered an issue processing your request.",
                experiential_note="There was a technical issue with response processing."
            )

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
                working_context = self.working_memory.get_context()
                if working_context:
                    context_parts.append(f"Current Context: {working_context}")
            except Exception as e:
                logger.debug(f"Working memory context failed: {e}")
            
            # Add temporary semantics (recent extracted facts)
            try:
                temp_semantics_file = self.memory_base_path / "working" / "temporary_semantics.md"
                if temp_semantics_file.exists():
                    temp_content = temp_semantics_file.read_text(encoding='utf-8')
                    # Extract most recent facts for context
                    lines = temp_content.split('\n')
                    recent_facts = []
                    
                    for line in lines[-30:]:  # Look at last 30 lines
                        if line.startswith('- ') and ('→' in line or ':' in line):  # Both SPO and entity facts
                            recent_facts.append(line[2:])  # Remove "- " prefix
                    
                    if recent_facts:
                        facts_summary = '; '.join(recent_facts[-5:])  # Last 5 facts
                        context_parts.append(f"Recent Facts: {facts_summary}")
            except Exception as e:
                logger.debug(f"Temporary semantics context failed: {e}")
            
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
                working_context = self.working_memory.get_context()
                if working_context:
                    context_parts.append(f"[Current Focus]: {working_context}")
            except Exception as e:
                logger.debug(f"Working memory failed: {e}")
            
            # Temporary semantics (extracted facts pending consolidation)
            try:
                temp_semantics_file = self.memory_base_path / "working" / "temporary_semantics.md"
                if temp_semantics_file.exists():
                    temp_content = temp_semantics_file.read_text(encoding='utf-8')
                    # Extract recent facts (last 2 sections to avoid overwhelming context)
                    lines = temp_content.split('\n')
                    recent_facts = []
                    section_count = 0
                    
                    for line in lines:
                        if line.startswith('## ') and 'id:' in line:
                            section_count += 1
                            if section_count > 2:  # Only include last 2 interaction sections
                                break
                        if line.startswith('- ') and section_count > 0 and ('→' in line or ':' in line):
                            recent_facts.append(line[2:])  # Remove "- " prefix
                    
                    if recent_facts:
                        facts_summary = '; '.join(recent_facts[-10:])  # Last 10 facts max
                        context_parts.append(f"[Recent Facts]: {facts_summary}")
            except Exception as e:
                logger.debug(f"Temporary semantics injection failed: {e}")

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

    def _handle_memory_automation(self, user_input: str, response, 
                                 user_id: str, location: str):
        """Handle memory automation after generation."""
        
        logger.debug("_handle_memory_automation called")
        logger.debug(f"Response type: {type(response)}")
        
        try:
            # Handle structured MemoryResponse (new in AbstractCore 2.3.5)
            from .memory_response_models import MemoryResponse
            
            if isinstance(response, MemoryResponse):
                logger.debug("Processing MemoryResponse")
                # Native structured response - direct access to fields
                answer = response.answer
                logger.debug(f"Extracted answer: {len(answer) if answer else 0} chars")
                experiential_note = response.experiential_note or ""
                logger.debug(f"Extracted experiential_note: {len(experiential_note)} chars")
                memory_actions = response.memory_actions or []
                logger.debug(f"Extracted memory_actions: {len(memory_actions)} actions")
                unresolved_questions = response.unresolved_questions or []
                logger.debug(f"Extracted unresolved_questions: {len(unresolved_questions)} questions")
                emotional_resonance = response.emotional_resonance.dict() if response.emotional_resonance else {}
                logger.debug(f"Extracted emotional_resonance: {bool(emotional_resonance)}")
            else:
                # Fallback for non-structured responses (GenerateResponse)
                response_content = response.content if hasattr(response, 'content') else str(response)
                
                # Parse structured response if it's JSON (legacy support)
                parsed_response = self._parse_structured_response(response_content)
                
                # Extract components
                answer = parsed_response.get("answer", response_content)
                experiential_note = parsed_response.get("experiential_note", "")
                memory_actions = parsed_response.get("memory_actions", [])
                unresolved_questions = parsed_response.get("unresolved_questions", [])
                emotional_resonance = parsed_response.get("emotional_resonance", {})
            
            # Store verbatim interaction (dual storage) - use the answer, not raw JSON
            logger.debug("About to store verbatim interaction...")
            verbatim_id = self._store_verbatim_interaction(user_input, answer, user_id, location)
            logger.debug(f"Verbatim interaction stored with ID: {verbatim_id}")
            
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
            logger.debug("About to update unresolved questions...")
            if unresolved_questions:
                logger.debug(f"Updating {len(unresolved_questions)} unresolved questions...")
                self._update_unresolved_questions(unresolved_questions, user_id)
                logger.debug("Unresolved questions updated successfully")
            else:
                logger.debug("No unresolved questions to update")
            
            # Trigger background fact extraction if available
            logger.debug("About to trigger background fact extraction...")
            if self.fact_extractor:
                logger.debug("Fact extractor available, scheduling background fact extraction...")
                self._schedule_background_fact_extraction(user_input, answer)
                logger.debug("Background fact extraction scheduled")
            else:
                logger.debug("No fact extractor available, skipping fact extraction")
            
            # Phase 1: Check for understanding evolution (automatic question resolution)
            logger.debug("About to check understanding evolution...")
            if self.understanding_detector:
                logger.debug("Understanding detector available, checking question resolution...")
                self._check_understanding_evolution(user_input, answer, user_id)
                logger.debug("Understanding evolution check completed")
            else:
                logger.debug("No understanding detector available, skipping evolution check")
            
            # Check consolidation triggers
            logger.debug("About to check consolidation triggers...")
            self._check_consolidation_triggers()
            logger.debug("Consolidation triggers checked")
            
            logger.debug("Memory automation completed successfully")
            
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
        
        logger.debug("_store_verbatim_interaction called")
        logger.debug(f"User input length: {len(user_input)}")
        logger.debug(f"Response length: {len(response)}")
        
        try:
            timestamp = datetime.now()
            interaction_id = f"{user_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            logger.debug(f"Generated interaction_id: {interaction_id}")
            
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
                    
                    # Create verbatim content for embedding
                    verbatim_content = f"User: {user_input}\n\nAssistant: {response}"
                    
                    # Schedule background embedding generation
                    self._schedule_background_embedding(
                        content=verbatim_content,
                        content_type="verbatim",
                        content_id=interaction_id,
                        metadata={
                            'user_input': user_input,
                            'response': response,
                            'user_id': user_id,
                            'location': location,
                            'topic': topic,
                            'category': 'conversation',
                            'confidence': 1.0,
                            'tags': '[]',
                            'file_path': str(verbatim_file),
                            'word_count': len(user_input.split()) + len(response.split())
                        }
                    )
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
        """Schedule background fact extraction using the task queue."""
        
        if not self.task_queue or not self.fact_extractor:
            logger.debug("⚠️  [MemorySession] Task queue or fact extractor not available for background processing")
            return
        
        conversation_text = f"User: {user_input}\n\nAssistant: {response}"
        
        logger.debug(f"📋 [MemorySession] Scheduling background fact extraction task")
        logger.debug(f"📝 [MemorySession] Conversation length: {len(conversation_text)} chars")
        
        # Add fact extraction task to queue
        task_id = self.task_queue.add_task(
            name="fact_extraction",
            description=f"Extract facts from conversation ({len(conversation_text)} chars)",
            parameters={
                'fact_extractor': self.fact_extractor,
                'conversation_text': conversation_text,
                'importance_threshold': 0.7,
                'store_facts_callback': self._store_temporary_facts
            },
            priority=3,  # Medium priority
            max_attempts=2  # Retry once if failed
        )
        
        logger.info(f"✅ [MemorySession] Scheduled fact extraction task: {task_id}")
        logger.debug(f"🔄 [MemorySession] Task queue now has {len(self.task_queue.get_all_tasks())} total tasks")

    def _schedule_background_embedding(self, content: str, content_type: str, content_id: str, metadata: dict):
        """Schedule background embedding generation to avoid blocking main thread."""
        
        if not self.task_queue or not self.embedding_manager:
            logger.debug("⚠️  [MemorySession] Task queue or embedding manager not available for background embedding")
            return
        
        logger.debug(f"📋 [MemorySession] Scheduling background embedding task for {content_type}")
        logger.debug(f"📝 [MemorySession] Content length: {len(content)} chars")
        
        # Add embedding task to queue
        task_id = self.task_queue.add_task(
            name="embedding_generation",
            description=f"Generate embedding for {content_type} ({len(content)} chars)",
            parameters={
                'embedding_manager': self.embedding_manager,
                'lancedb_storage': self.lancedb_storage,
                'content': content,
                'content_type': content_type,
                'content_id': content_id,
                'metadata': metadata
            },
            priority=2,  # High priority for embeddings
            max_attempts=2
        )
        
        logger.info(f"✅ [MemorySession] Scheduled embedding task: {task_id}")
        logger.debug(f"🔄 [MemorySession] Task queue now has {len(self.task_queue.get_all_tasks())} total tasks")
        
        # Periodically save embedding cache to ensure it's in the correct location
        if hasattr(self.embedding_manager, 'save_caches'):
            try:
                self.embedding_manager.save_caches()
                logger.debug(f"💾 [MemorySession] Embedding cache saved to: {self.embedding_manager.cache_dir}")
            except Exception as e:
                logger.debug(f"⚠️  [MemorySession] Cache save failed: {e}")

    def _check_understanding_evolution(self, user_input: str, response: str, user_id: str):
        """Check if new information resolves any unresolved questions (Phase 1 feature)."""
        
        if not self.understanding_detector:
            logger.debug("⚠️  [MemorySession] Understanding detector not available for evolution check")
            return
        
        logger.debug(f"🧠 [MemorySession] Checking understanding evolution for user: {user_id}")
        
        try:
            # Create conversation context
            conversation_context = f"User: {user_input}\nAssistant: {response}"
            logger.debug(f"📝 [MemorySession] Conversation context length: {len(conversation_context)} chars")
            
            # Check for question resolutions
            logger.debug("❓ [MemorySession] Checking for question resolutions...")
            resolutions = self.understanding_detector.check_question_resolution(
                new_information=response,
                conversation_context=conversation_context,
                user_id=user_id
            )
            
            if resolutions:
                logger.info(f"💡 [MemorySession] Found {len(resolutions)} resolved questions - processing understanding evolution")
                logger.debug(f"🔍 [MemorySession] Resolved questions: {[r['question'][:50] + '...' for r in resolutions]}")
                
                # Process resolutions (move to resolved, create semantic memories, generate self-awareness notes)
                logger.debug("🔄 [MemorySession] Processing understanding evolution...")
                success = self.understanding_detector.process_resolutions(resolutions)
                
                if success:
                    logger.info("✅ [MemorySession] Understanding evolution processing completed successfully")
                else:
                    logger.warning("⚠️  [MemorySession] Understanding evolution processing encountered errors")
            else:
                logger.debug("ℹ️  [MemorySession] No questions resolved in this interaction")
                
        except Exception as e:
            logger.error(f"❌ [MemorySession] Understanding evolution check failed: {e}")

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
        
        Uses a compact, graph-oriented format that preserves Subject-Predicate-Object structure
        while being actionable for LLM processing.
        
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
            
            # Generate interaction ID for this batch
            interaction_id = datetime.now().strftime('%H%M%S')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Prepare new facts section in compact graph format
            new_facts_section = f"\n## {timestamp} | id:{interaction_id}\n"
            
            for fact in facts:
                content = fact['content']
                importance = fact['importance']
                confidence = fact.get('confidence', importance)  # Fallback to importance if no confidence
                emotion = fact['emotion']
                
                # Always try to extract SPO structure - convert entities to triples using "is"
                spo = self._parse_semantic_triple(content)
                if spo:
                    # Format: Subject → Predicate → Object | importance | confidence | emotion
                    new_facts_section += f"- {spo['subject']} → {spo['predicate']} → {spo['object']} | {importance:.1f} | {confidence:.1f} | {emotion}\n"
                else:
                    # Fallback: keep original format for truly unparseable content
                    new_facts_section += f"- {content} | {importance:.1f} | {confidence:.1f} | {emotion}\n"
            
            # Create or update file
            if not existing_content or "# Temporary Semantics" not in existing_content:
                # Create new file with compact header
                content = f"""# Temporary Semantics

Graph-oriented facts for consolidation. Format: Subject → Predicate → Object | importance | confidence | emotion

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

    def _is_semantic_triple(self, content: str) -> bool:
        """Check if content represents a semantic triple (Subject-Predicate-Object)."""
        
        # Look for patterns that indicate semantic triples
        triple_indicators = [
            " describes ", " explores ", " reads ", " works_with ", " provides ",
            " supports ", " manages ", " requires ", " creates ", " mentions ",
            " executes ", " relates_to ", " contains ", " influences "
        ]
        
        return any(indicator in content.lower() for indicator in triple_indicators)

    def _parse_semantic_triple(self, content: str) -> Optional[Dict[str, str]]:
        """Parse semantic triple from content string."""
        
        try:
            import re
            
            # Pattern 1: Explicit relationship verbs (including missing ones)
            relationship_pattern = r"(.+?)\s+(describes|explores|reads|works_with|provides|supports|manages|requires|creates|mentions|executes|relates_to|contains|influences|constitutes|transforms|enables|uses|models|occurs_in|part_of|precedes|draws_parallels_to|refers_to|formalizes|develops|evolves_into|integrates|related_to|works_with|created_by)\s+(.+)"
            match = re.search(relationship_pattern, content, re.IGNORECASE)
            if match:
                return {
                    'subject': match.group(1).strip(),
                    'predicate': match.group(2).strip(),
                    'object': match.group(3).strip()
                }
            
            # Pattern 2: Entity definition format "Subject: Definition" -> "Subject is Definition"
            definition_pattern = r"^(.+?):\s*(.+)$"
            match = re.search(definition_pattern, content.strip())
            if match:
                subject = match.group(1).strip()
                definition = match.group(2).strip()
                
                # Clean up common definition prefixes
                if definition.lower().startswith(('the ', 'a ', 'an ')):
                    # Keep the article for natural language
                    pass
                elif definition.lower().startswith(('concept of', 'process of', 'system for', 'method for')):
                    # These are already well-formed definitions
                    pass
                
                return {
                    'subject': subject,
                    'predicate': 'is',
                    'object': definition
                }
            
            # Pattern 3: Look for implicit relationships with common verbs
            implicit_verbs = ['has', 'contains', 'includes', 'involves', 'affects', 'impacts', 'changes', 'modifies']
            for verb in implicit_verbs:
                verb_pattern = rf"(.+?)\s+{verb}\s+(.+)"
                match = re.search(verb_pattern, content, re.IGNORECASE)
                if match:
                    return {
                        'subject': match.group(1).strip(),
                        'predicate': verb,
                        'object': match.group(2).strip()
                    }
            
            return None
            
        except Exception:
            return None

    def _parse_structured_response(self, response_content: str) -> Dict[str, Any]:
        """
        DEPRECATED: Parse structured JSON response from LLM.
        
        This method is kept for backward compatibility but is no longer needed
        since AbstractCore 2.3.5 supports native structured output with tools.
        
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

    def _execute_memory_actions(self, memory_actions, user_id: str):
        """Execute memory actions from structured response."""
        
        try:
            from .memory_response_models import MemoryAction
            
            for action in memory_actions:
                # Handle both MemoryAction objects and dict format (legacy support)
                if isinstance(action, MemoryAction):
                    action_type = action.action
                    content = action.content
                    importance = action.importance or 0.5
                    emotion = action.emotion or "neutral"
                    links_to = action.links_to or []
                else:
                    # Legacy dict format
                    action_type = action.get("action", "")
                    content = action.get("content", "")
                    importance = action.get("importance", 0.5)
                    emotion = action.get("emotion", "neutral")
                    links_to = action.get("links_to", [])
                
                if action_type == "remember":
                    # Store fact in semantic memory
                    if content:
                        self.remember_fact(
                            content=content,
                            importance=importance,
                            emotion=emotion,
                            reason=f"LLM requested memory storage",
                            links_to=links_to
                        )
                
                elif action_type == "link":
                    # Create memory link
                    if isinstance(action, MemoryAction):
                        from_id = action.from_id or ""
                        to_id = action.to_id or ""
                        relationship = action.relationship or "relates_to"
                    else:
                        from_id = action.get("from_id", "")
                        to_id = action.get("to_id", "")
                        relationship = action.get("type", "relates_to")
                    
                    if from_id and to_id and self.lancedb_storage:
                        try:
                            confidence = 0.8
                            if isinstance(action, MemoryAction):
                                # MemoryAction doesn't have confidence field, use default
                                pass
                            else:
                                confidence = action.get("confidence", 0.8)
                                
                            self.lancedb_storage.add_link({
                                "link_id": f"link_{from_id}_{to_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                "from_id": from_id,
                                "to_id": to_id,
                                "relationship": relationship,
                                "timestamp": datetime.now(),
                                "confidence": confidence,
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
            
            # Use a timeout-based approach to prevent hanging on file write
            import time
            
            try:
                # Use thread-safe timeout for file write operation
                import concurrent.futures
                
                def write_file():
                    logger.debug("About to write unresolved questions file...")
                    questions_file.write_text(content, encoding='utf-8')
                    logger.debug("File write completed successfully")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(write_file)
                    try:
                        future.result(timeout=5)  # 5 seconds timeout
                    except concurrent.futures.TimeoutError:
                        raise TimeoutError("File write operation timed out after 5 seconds")
                
                logger.debug(f"Updated unresolved questions: {len(all_questions)} total")
                logger.debug("About to return from _update_unresolved_questions")
                
            except TimeoutError:
                logger.error("File write operation timed out after 5 seconds")
                raise
            except Exception as write_error:
                logger.error(f"File write failed: {write_error}")
                raise
            
        except Exception as e:
            logger.error(f"Unresolved questions update failed: {e}")
            logger.debug("Exception occurred in _update_unresolved_questions, about to return")
        
        logger.debug("Returning from _update_unresolved_questions")

    def _cleanup_embedding_cache(self):
        """Ensure embedding cache is saved to the correct location on cleanup."""
        try:
            if self.embedding_manager and hasattr(self.embedding_manager, 'save_caches'):
                logger.debug(f"💾 [MemorySession] Saving embedding cache to: {self.embedding_manager.cache_dir}")
                self.embedding_manager.save_caches()
                logger.info(f"✅ [MemorySession] Embedding cache saved to memory folder")
        except Exception as e:
            logger.warning(f"⚠️  [MemorySession] Failed to save embedding cache: {e}")

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
            """
            Remember important information by storing it in memory.
            
            Use this when you encounter facts, preferences, insights, or anything worth preserving.
            The AI can consciously choose what to remember based on importance and emotional significance.
            
            Args:
                content: The information to remember (required)
                importance: Importance level from 0.0 to 1.0 (default: 0.7)
                emotion: Emotional context - "neutral", "positive", "negative", "excited", "concerned" (default: "neutral")
                reason: Why this information is worth remembering (default: "")
                links_to: List of related memory IDs or concepts (default: None)
            
            Returns:
                Confirmation message with memory ID or error message
            
            Examples:
                remember_fact("User prefers Python over JavaScript", 0.8, "neutral", "Programming preference")
                remember_fact("Important deadline: Project due March 15", 0.9, "concerned", "Critical timeline")
            """
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
            """
            Search your memory for relevant information using semantic search.
            
            Use this to recall previous conversations, facts you've stored, or insights you've developed.
            Searches across notes, conversations, and stored memories using semantic similarity.
            
            Args:
                query: Search query describing what you're looking for (required)
                limit: Maximum number of results to return (default: 10)
            
            Returns:
                Formatted list of relevant memories with content snippets or "No memories found"
            
            Examples:
                search_memories("Python programming tips")
                search_memories("user preferences about databases", 5)
                search_memories("previous discussions about AI ethics")
            """
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
            """
            Engage in deep reflection on a topic, analyzing patterns, contradictions, and evolution of understanding.
            
            Use this to gain deeper insights by analyzing stored memories, identifying patterns,
            and understanding how your knowledge on a topic has evolved over time.
            
            Args:
                topic: The topic or concept to reflect on (required)
                depth: Reflection depth - "surface", "deep", or "comprehensive" (default: "deep")
            
            Returns:
                Structured reflection with insights, patterns, and understanding evolution
            
            Examples:
                reflect_on("machine learning ethics")
                reflect_on("user communication patterns", "comprehensive")
                reflect_on("programming best practices", "surface")
            """
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
        
        # Enhanced Tool: Unified search using high-level interface
        def search_all_memories(query: str, include_relationships: bool = True, max_results: int = 10) -> str:
            """
            Search across all memory layers using enhanced triple storage interface.
            
            This is the most comprehensive search tool, querying filesystem, LanceDB embeddings,
            and knowledge graph relationships simultaneously for the most complete results.
            
            Args:
                query: Search query describing what you're looking for (required)
                include_relationships: Whether to include knowledge graph relationships (default: True)
                max_results: Maximum number of results to return (default: 10)
            
            Returns:
                Unified search results from all storage layers with relevance scores and source indicators
            
            Examples:
                search_all_memories("Python async programming")
                search_all_memories("user feedback on UI design", False, 5)
                search_all_memories("database optimization techniques", True, 15)
            """
            try:
                if not self.triple_storage_manager:
                    # Fallback to regular memory search
                    return search_memories(query, limit=max_results)
                
                # Use enhanced unified search
                results = self.triple_storage_manager.unified_search(
                    query=query,
                    include_relationships=include_relationships,
                    max_results=max_results
                )
                
                if not results:
                    return f"No memories found for '{query}'"
                
                # Format results by source layer
                formatted_results = []
                for result in results:
                    source = result.source_layer
                    content = result.content[:200] + "..." if len(result.content) > 200 else result.content
                    score = f"{result.relevance_score:.2f}"
                    
                    formatted_results.append(f"[{source}] ({score}) {content}")
                
                return f"Found {len(results)} memories:\n" + "\n".join(formatted_results)
                
            except Exception as e:
                return f"❌ Unified search failed: {e}"
        
        tools.append(search_all_memories)
        
        # Phase 1 Tool: Get relationship context for concepts
        def explore_relationships(concept: str, depth: int = 2) -> str:
            """
            Explore relationship context for a concept using the knowledge graph.
            
            Discovers how concepts are connected through the knowledge graph, showing
            direct relationships, related concepts, and relationship patterns.
            
            Args:
                concept: The concept or entity to explore relationships for (required)
                depth: How many relationship hops to explore (default: 2)
            
            Returns:
                Detailed relationship context with connections, types, and related concepts
            
            Examples:
                explore_relationships("machine learning")
                explore_relationships("user authentication", 3)
                explore_relationships("database design patterns", 1)
            """
            try:
                if not self.triple_storage_manager:
                    return f"Knowledge graph not available for relationship exploration"
                
                context = self.triple_storage_manager.get_relationship_context(concept, depth)
                
                if not context.get('exists', False):
                    return f"No relationships found for concept '{concept}'"
                
                # Format relationship context
                total_rels = context.get('direct_relationships', 0)
                related_concepts = context.get('related_concepts', [])
                rel_types = context.get('relationship_types', {})
                
                result = f"Relationship context for '{concept}':\n"
                result += f"Direct relationships: {total_rels}\n"
                result += f"Related concepts: {len(related_concepts)}\n"
                
                # Show relationship types
                for rel_type, rels in rel_types.items():
                    if rels:
                        result += f"{rel_type}: {len(rels)} connections\n"
                
                # Show top related concepts
                if related_concepts:
                    result += "\nTop related:\n"
                    for rel in related_concepts[:5]:
                        result += f"- {rel['concept']} ({rel['relationship']}, {rel['confidence']:.2f})\n"
                
                return result
                
            except Exception as e:
                return f"❌ Relationship exploration failed: {e}"
        
        tools.append(explore_relationships)
        
        # Enhanced High-Level Interface Tools
        def deep_reflect(topic: str, depth: str = "deep") -> str:
            """
            Deep reflection using enhanced triple storage with relationship context.
            
            Advanced reflection that leverages all storage layers and relationship context
            to provide comprehensive insights, patterns, and understanding evolution analysis.
            
            Args:
                topic: The topic or concept to reflect deeply on (required)
                depth: Reflection depth - "surface", "deep", or "comprehensive" (default: "deep")
            
            Returns:
                Enhanced reflection with insights, relationship patterns, evolution tracking, and contradictions
            
            Examples:
                deep_reflect("artificial intelligence ethics")
                deep_reflect("software architecture decisions", "comprehensive")
                deep_reflect("team collaboration patterns", "surface")
            """
            try:
                if not self.triple_storage_manager:
                    return reflect_on(topic, depth)  # Fallback to basic reflection
                
                reflection = self.triple_storage_manager.reflect(
                    topic=topic,
                    reflection_depth=depth,
                    include_contradictions=True
                )
                
                if reflection.get('error'):
                    return f"❌ Reflection failed: {reflection['error']}"
                
                # Format reflection results
                result = f"Deep reflection on '{topic}':\n\n"
                
                insights = reflection.get('insights', [])
                if insights:
                    result += f"💡 Insights ({len(insights)}):\n"
                    for insight in insights[:3]:
                        result += f"  - {insight}\n"
                    result += "\n"
                
                patterns = reflection.get('patterns', [])
                if patterns:
                    result += f"🔗 Relationship patterns:\n"
                    for pattern in patterns[:3]:
                        result += f"  - {pattern}\n"
                    result += "\n"
                
                evolution = reflection.get('evolution', '')
                if evolution:
                    result += f"📈 Understanding evolution: {evolution}\n\n"
                
                contradictions = reflection.get('contradictions', [])
                if contradictions:
                    result += f"⚠️  Contradictions detected: {len(contradictions)}\n"
                
                confidence = reflection.get('confidence', 0)
                result += f"🎯 Confidence: {confidence:.2f}"
                
                return result
                
            except Exception as e:
                return f"❌ Deep reflection failed: {e}"
        
        tools.append(deep_reflect)
        
        def smart_reconstruct(query: str, depth: int = 3) -> str:
            """
            Intelligent context reconstruction across all storage layers.
            
            Reconstructs comprehensive context by analyzing filesystem, embeddings, and knowledge graph
            to provide the most relevant background information for a query or topic.
            
            Args:
                query: The query or topic to reconstruct context for (required)
                depth: Context depth level from 1 (basic) to 5 (comprehensive) (default: 3)
            
            Returns:
                Comprehensive context reconstruction with summary, semantic context, and relationship analysis
            
            Examples:
                smart_reconstruct("Python web development best practices")
                smart_reconstruct("user onboarding process improvements", 5)
                smart_reconstruct("database performance optimization", 2)
            """
            try:
                if not self.triple_storage_manager:
                    return f"Enhanced reconstruction not available - triple storage manager not initialized"
                
                context = self.triple_storage_manager.reconstruct(
                    query=query,
                    user_id=self.default_user_id,
                    context_depth=depth,
                    relationship_depth=2
                )
                
                if context.get('error'):
                    return f"❌ Reconstruction failed: {context['error']}"
                
                # Format reconstruction results
                result = f"Context reconstruction for '{query}':\n\n"
                
                synthesis = context.get('synthesis', '')
                result += f"📋 Summary: {synthesis}\n\n"
                
                semantic_context = context.get('semantic_context', [])
                if semantic_context:
                    result += f"🔍 Semantic context ({len(semantic_context)} memories):\n"
                    for i, mem in enumerate(semantic_context[:3], 1):
                        content = mem.content[:100] + "..." if len(mem.content) > 100 else mem.content
                        result += f"  {i}. [{mem.source_layer}] {content}\n"
                    result += "\n"
                
                relationship_context = context.get('relationship_context', {})
                if relationship_context.get('exists'):
                    result += f"🕸️  Relationship context: {relationship_context.get('total_relationships', 0)} connections\n"
                
                confidence = context.get('confidence', 0)
                result += f"🎯 Confidence: {confidence:.2f}"
                
                return result
                
            except Exception as e:
                return f"❌ Smart reconstruction failed: {e}"
        
        tools.append(smart_reconstruct)
        
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
