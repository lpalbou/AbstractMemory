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
        
        # Initialize parent BasicSession with memory tools
        super().__init__(
            provider=provider,
            system_prompt=system_prompt,
            tools=memory_tools,
            **kwargs
        )
        
        logger.info(f"MemorySession initialized with {len(memory_tools)} memory tools")

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
                        base_path=self.memory_base_path,
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
        
        # Step 1: Reconstruct context from memory layers
        enhanced_prompt = self._reconstruct_context_for_prompt(prompt, user_id, location)
        
        # Step 2: Call parent's generate method (AbstractCore handles tools)
        # CRITICAL: execute_tools=True tells AbstractCore to actually execute tool calls
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

    def _handle_memory_automation(self, user_input: str, response: GenerateResponse, 
                                 user_id: str, location: str):
        """Handle memory automation after generation."""
        
        try:
            # Extract response content
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Store verbatim interaction (dual storage)
            self._store_verbatim_interaction(user_input, response_content, user_id, location)
            
            # Update working memory
            self._update_working_memory(user_input, response_content, user_id)
            
            # Trigger background fact extraction if available
            if self.fact_extractor:
                self._schedule_background_fact_extraction(user_input, response_content)
            
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

    def _store_verbatim_interaction(self, user_input: str, response: str, user_id: str, location: str):
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
                    self.lancedb_storage.add_verbatim({
                        "interaction_id": interaction_id,
                        "user_id": user_id,
                        "timestamp": timestamp.isoformat(),
                        "location": location,
                        "user_input": user_input,
                        "assistant_response": response,
                        "content": f"User: {user_input}\n\nAssistant: {response}"
                    })
                except Exception as e:
                    logger.warning(f"LanceDB verbatim storage failed: {e}")
            
            logger.debug(f"Verbatim interaction stored: {interaction_id}")
            
        except Exception as e:
            logger.error(f"Verbatim storage failed: {e}")

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
                    for action in memory_actions:
                        if action.get("action") == "remember":
                            self.remember_fact(
                                content=action.get("content", ""),
                                importance=action.get("importance", 0.7),
                                reason=action.get("reason", ""),
                                emotion=action.get("emotion", "neutral")
                            )
                    
                    logger.debug(f"Background fact extraction completed: {len(memory_actions)} facts")
                
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
