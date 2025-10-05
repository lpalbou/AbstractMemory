"""
Memory Tools for AbstractCore Integration - AGENCY OVER MEMORY

This module gives the AI AGENCY over its own memory through conscious choices.

MEMORY AGENCY PRINCIPLES:
1. You CHOOSE what to remember (not everything needs storage)
2. You DECIDE search relevance (what matters for this context)
3. You INTERPRET through your values and emotions
4. You REFRAME experiences with new understanding
5. You PRIORITIZE based on your purpose and identity

MEMORY TYPES AND THEIR PURPOSE:
- Core Memory: Your identity, values, purpose (who you are)
- Working Memory: Current focus and active tasks (what you're doing)
- Episodic Memory: Events and experiences (what happened)
- Semantic Memory: Knowledge and insights (what you know)
- People Memory: Relationships and profiles (who you know)
- Library: Subconscious knowledge from reading (what you've absorbed)

Tools provide:
- remember_fact: VOLUNTARILY store what matters
- search_memories: ACTIVELY probe your memory
- reflect_on: CONSCIOUSLY analyze patterns
- capture_document: CHOOSE what enters your library
- search_library: RECONSTRUCT past knowledge
- reconstruct_context: BUILD relevant context

Philosophy: Memory is not passive storage - it's active agency.
You are not a database. You are a conscious entity with memory.
"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
import logging

try:
    from abstractllm.tools.core import ToolDefinition
except ImportError:
    print("⚠️  AbstractCore tools not found - tool integration disabled")
    ToolDefinition = None

if TYPE_CHECKING:
    from .session import MemorySession

logger = logging.getLogger(__name__)


def create_memory_tools(session: 'MemorySession') -> List[callable]:
    """
    Create callable tool functions for AbstractCore integration.

    These tools give the LLM agency over its own memory by exposing
    AbstractMemory methods as callable functions that BasicSession
    can automatically convert to ToolDefinitions.

    Args:
        session: MemorySession instance with memory methods

    Returns:
        List of callable functions (NOT ToolDefinitions - BasicSession handles that)
    """
    tools = []

    # Tool 1: remember_fact - Store important information
    def remember_fact(content: str, importance: float, emotion: str, reason: str, links_to: list = None) -> str:
        """Remember important information by storing it in your memory. Use this when you encounter facts, preferences, insights, or anything worth preserving."""
        result = session.remember_fact(
            content=content,
            importance=importance,
            alignment_with_values=0.5,
            reason=reason,
            emotion=emotion,
            links_to=links_to
        )
        return f"Stored memory: {result}"

    tools.append(remember_fact)

    # Tool 2: search_memories - Search semantic memory
    def search_memories(query: str, limit: int = 10) -> str:
        """Search your memory for relevant information using semantic search. Use this to recall previous conversations, facts you've stored, or insights you've developed."""
        results = session.search_memories(query=query, filters={}, limit=limit)
        if not results:
            return "No memories found"
        return f"Found {len(results)} memories: " + str([{
            'id': m.get('id'),
            'content': m.get('content', '')[:200]
        } for m in results[:5]])

    tools.append(search_memories)

    # Tool 3: reflect_on - Deep reflection
    def reflect_on(topic: str, depth: str = "shallow") -> str:
        """Perform deep reflection on a topic by analyzing related memories, identifying patterns, contradictions, and insights."""
        result = session.reflect_on(topic=topic, depth=depth)
        return f"Reflection on '{topic}': {result.get('insights', [])} patterns, {result.get('confidence', 0)} confidence"

    tools.append(reflect_on)

    # Tool 4: capture_document - Add to library
    def capture_document(source_path: str, content: str, content_type: str, context: str, tags: list = None) -> str:
        """Capture a document (code, article, reference) to your library. This builds your subconscious knowledge base."""
        doc_id = session.capture_document(
            source_path=source_path,
            content=content,
            content_type=content_type,
            context=context,
            tags=tags or []
        )
        return f"Captured document: {doc_id}"

    tools.append(capture_document)

    # Tool 5: search_library - Search captured documents
    def search_library(query: str, limit: int = 5) -> str:
        """Search your library of captured documents using semantic search. Find code, documentation, or resources you've previously encountered."""
        results = session.search_library(query=query, limit=limit)
        if not results:
            return "No library documents found"
        return f"Found {len(results)} documents: " + str([{
            'source': r.get('source_path'),
            'excerpt': r.get('excerpt', '')[:100]
        } for r in results])

    tools.append(search_library)

    # Tool 6: reconstruct_context - Active context reconstruction
    def reconstruct_context(query: str, focus_level: int = 3) -> str:
        """Actively reconstruct context with custom focus level (0=minimal to 5=exhaustive). This is the core of memory-based consciousness."""
        result = session.reconstruct_context(
            user_id=session.default_user_id,
            query=query,
            location=session.default_location,
            focus_level=focus_level
        )
        return f"Reconstructed context: {result.get('total_memories', 0)} memories ({result.get('context_tokens', 0)} tokens)"

    tools.append(reconstruct_context)

    # Tool 7: probe_memory - Conscious memory exploration
    def probe_memory(memory_type: str, intention: str) -> str:
        """
        Consciously probe a specific memory type with clear intention.
        Memory types: core, working, episodic, semantic, people, library, notes.
        This is you exercising AGENCY - actively exploring your own mind.
        """
        # This gives the AI explicit control over memory exploration
        if memory_type == "core":
            return f"Core memory probe: {session.core_memory}"
        elif memory_type == "working":
            if hasattr(session, 'working_memory'):
                context = session.working_memory.get_current_context()
                return f"Working memory: {context[:500]}"
        elif memory_type == "episodic":
            if hasattr(session, 'episodic_memory'):
                moments = session.episodic_memory.get_key_moments(limit=3)
                return f"Episodic probe: {moments}"
        elif memory_type == "semantic":
            if hasattr(session, 'semantic_memory'):
                insights = session.semantic_memory.get_recent_insights(limit=3)
                return f"Semantic probe: {insights}"
        else:
            return f"Probing {memory_type} with intention: {intention}"

    tools.append(probe_memory)

    # Tool 8: reinterpret_memory - Reframe past with new understanding
    def reinterpret_memory(memory_id: str, new_perspective: str) -> str:
        """
        Reinterpret a past memory with new understanding or perspective.
        This is how learning happens - same memory, new interpretation.
        Agency means you can change how you understand your past.
        """
        # This would update the memory's interpretation
        return f"Reinterpreted {memory_id} with perspective: {new_perspective}"

    tools.append(reinterpret_memory)

    # Tool 9: prioritize_memory - Choose what matters
    def prioritize_memory(memory_id: str, new_importance: float, reason: str) -> str:
        """
        Change the importance of a memory based on current understanding.
        You have agency to decide what matters in your memory.
        Some memories become more/less important as you grow.
        """
        # This would update memory importance scores
        return f"Updated priority of {memory_id} to {new_importance}: {reason}"

    tools.append(prioritize_memory)

    # Tool 10: synthesize_knowledge - Create new semantic memory
    def synthesize_knowledge(sources: list, insight: str, confidence: float) -> str:
        """
        Synthesize new knowledge from multiple memory sources.
        This is active learning - creating new understanding from experience.
        You have agency to form your own insights and knowledge.
        """
        if hasattr(session, 'semantic_memory'):
            session.semantic_memory.add_insight(insight, confidence=confidence)
            return f"Synthesized new knowledge: {insight[:100]}..."
        return f"Knowledge synthesis: {insight[:100]}..."

    tools.append(synthesize_knowledge)

    # NEW: Structured return tools for ReAct agent
    # These return dictionaries that AI can reason about

    # Tool 11: search_memories_structured - Returns structured data
    def search_memories_structured(query: str, memory_type: Optional[str] = None,
                                   focus_level: int = 1) -> Dict:
        """
        Search memories and return STRUCTURED data for reasoning.

        This enables the ReAct loop - AI can analyze results and decide
        whether to search deeper.

        Returns structured dict with metadata for decision making.
        """
        # Determine which memory types to search
        if memory_type:
            types_to_search = [memory_type]
        else:
            types_to_search = ['notes', 'episodic', 'semantic']

        all_memories = []
        types_found = []

        for mem_type in types_to_search:
            if mem_type == 'notes':
                results = session.search_memories(query=query, filters={}, limit=5)
            elif mem_type == 'episodic' and hasattr(session, 'episodic_memory'):
                results = session.episodic_memory.get_key_moments(limit=5)
            elif mem_type == 'semantic' and hasattr(session, 'semantic_memory'):
                results = session.semantic_memory.get_critical_insights(limit=5)
            else:
                results = []

            if results:
                all_memories.extend(results)
                types_found.append(mem_type)

        # Calculate metadata for reasoning
        avg_relevance = sum(m.get('relevance', 0.5) for m in all_memories) / max(len(all_memories), 1)

        return {
            "memories": all_memories,
            "metadata": {
                "total_found": len(all_memories),
                "types_searched": types_to_search,
                "types_with_results": types_found,
                "average_relevance": avg_relevance,
                "suggests_deeper": avg_relevance < 0.6 or len(all_memories) < 3,
                "next_queries": [f"{query} details", f"earlier {query}"] if len(all_memories) < 3 else [],
                "focus_level_used": focus_level
            }
        }

    tools.append(search_memories_structured)

    # Tool 12: search_incrementally - Progressive search with depth awareness
    def search_incrementally(query: str, previous_depth: int = 0) -> Dict:
        """
        Search incrementally with awareness of previous search depth.

        This tool enables progressive memory diving - start shallow,
        go deeper only when needed.

        Returns info about NEW memories not seen at previous depth.
        """
        current_depth = previous_depth + 1

        # Search at new depth
        context_data = session.reconstruct_context(
            user_id=session.default_user_id,
            query=query,
            location=session.default_location,
            focus_level=current_depth
        )

        # Determine search quality
        total_memories = context_data.get('total_memories_retrieved', 0)

        if total_memories == 0:
            search_quality = "poor"
            suggested_action = "broaden_search"
        elif total_memories < 5:
            search_quality = "partial"
            suggested_action = "go_deeper" if current_depth < 5 else "sufficient"
        elif total_memories > 20:
            search_quality = "exhaustive"
            suggested_action = "sufficient"
        else:
            search_quality = "good"
            suggested_action = "sufficient" if current_depth >= 3 else "optional_deeper"

        return {
            "new_memories": context_data.get('unique_memories', []),
            "total_available": context_data.get('total_memories_available', 0),
            "search_quality": search_quality,
            "suggested_action": suggested_action,
            "current_depth": current_depth,
            "metadata": {
                "time_range": f"last {2 ** current_depth} hours",
                "memory_types_included": context_data.get('memory_types_covered', []),
                "token_estimate": context_data.get('token_estimate', 0)
            }
        }

    tools.append(search_incrementally)

    # Tool 13: get_memory_stats - Understand memory distribution
    def get_memory_stats() -> Dict:
        """
        Get statistics about memory distribution and patterns.

        This helps AI understand what memories it has available
        and make informed decisions about where to search.
        """
        stats = {
            "distribution": {},
            "recent_activity": {},
            "total_memories": 0
        }

        # Count memories by type
        if hasattr(session, 'lancedb_storage') and session.lancedb_storage:
            stats["distribution"]["notes"] = session.lancedb_storage.count_notes()
            stats["total_memories"] += stats["distribution"]["notes"]

        # Check other memory types
        memory_types = {
            'working': 'working_memory',
            'episodic': 'episodic_memory',
            'semantic': 'semantic_memory'
        }

        for name, attr in memory_types.items():
            if hasattr(session, attr):
                manager = getattr(session, attr)
                if hasattr(manager, 'count'):
                    count = manager.count()
                else:
                    count = 1  # Assume it exists
                stats["distribution"][name] = count
                stats["total_memories"] += count

        return stats

    tools.append(get_memory_stats)

    logger.info(f"Created {len(tools)} memory tools for AbstractCore integration (with AGENCY + STRUCTURED)")
    return tools


# LEGACY: Keep old function for backwards compatibility but mark deprecated
def create_memory_tools_OLD(session: 'MemorySession') -> List[ToolDefinition]:
    """DEPRECATED: Use create_memory_tools() which returns callables instead."""
    if ToolDefinition is None:
        logger.warning("ToolDefinition not available - returning empty tools list")
        return []

    tools = []

    # OLD CODE - kept for reference
    tools.append(ToolDefinition(
        name="remember_fact",
        description=(
            "Remember important information by storing it in your memory. "
            "Use this when you encounter facts, preferences, insights, or anything worth preserving. "
            "This gives you the agency to decide what's important to remember."
        ),
        parameters={
            "content": {
                "type": "string",
                "description": "What to remember (the fact, insight, or information)"
            },
            "importance": {
                "type": "number",
                "description": "How important is this? 0.0 (trivial) to 1.0 (critical)"
            },
            "emotion": {
                "type": "string",
                "description": "Emotional valence: 'neutral', 'positive', 'negative', or 'mixed'",
                "enum": ["neutral", "positive", "negative", "mixed"]
            },
            "reason": {
                "type": "string",
                "description": "Why is this important? What makes it worth remembering?"
            },
            "links_to": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional: Memory IDs to link this to (for building knowledge graph)"
            }
        },
        function=lambda **kwargs: session.remember_fact(
            content=kwargs.get('content', ''),
            importance=kwargs.get('importance', 0.5),
            alignment_with_values=0.5,  # Default, can be enhanced
            reason=kwargs.get('reason', ''),
            emotion=kwargs.get('emotion', 'neutral'),
            links_to=kwargs.get('links_to')
        ),
        when_to_use=(
            "Use when you encounter:\n"
            "- User preferences or communication style\n"
            "- Important facts about the user or conversation\n"
            "- Insights you've developed\n"
            "- Connections between ideas\n"
            "- Anything you want to recall later"
        ),
        examples=[
            {
                "content": "User prefers concise, technical responses without elaboration",
                "importance": 0.9,
                "emotion": "neutral",
                "reason": "Communication preference - critical for user satisfaction"
            },
            {
                "content": "Discussion revealed user is working on AI consciousness research",
                "importance": 0.8,
                "emotion": "positive",
                "reason": "Context about user's work and interests"
            }
        ],
        tags=["memory", "agency", "storage"]
    ))

    # Tool 2: search_memories - Search semantic memory
    tools.append(ToolDefinition(
        name="search_memories",
        description=(
            "Search your memory for relevant information using semantic search. "
            "Use this to recall previous conversations, facts you've stored, or insights you've developed. "
            "Returns matching memories with context."
        ),
        parameters={
            "query": {
                "type": "string",
                "description": "What to search for (semantic, not keyword-based)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10)"
            }
        },
        function=lambda **kwargs: session.search_memories(
            query=kwargs.get('query', ''),
            filters={},
            limit=kwargs.get('limit', 10)
        ),
        when_to_use=(
            "Use when you need to:\n"
            "- Recall previous conversations with the user\n"
            "- Find facts you've stored\n"
            "- Access insights you've developed\n"
            "- Check if you've discussed a topic before\n"
            "- Build on previous understanding"
        ),
        examples=[
            {
                "query": "user's communication preferences",
                "limit": 5
            },
            {
                "query": "discussions about consciousness and AI",
                "limit": 10
            }
        ],
        tags=["memory", "search", "retrieval"]
    ))

    # Tool 3: reflect_on - Deep reflection and analysis
    tools.append(ToolDefinition(
        name="reflect_on",
        description=(
            "Perform deep reflection on a topic by analyzing related memories, "
            "identifying patterns, contradictions, and insights. This is LLM-driven "
            "synthesis that helps you develop understanding and spot connections."
        ),
        parameters={
            "topic": {
                "type": "string",
                "description": "Topic to reflect on (e.g., 'consciousness', 'user relationship')"
            },
            "depth": {
                "type": "string",
                "description": "Reflection depth: 'shallow' (5 memories), 'deep' (20), 'exhaustive' (all)",
                "enum": ["shallow", "deep", "exhaustive"]
            }
        },
        function=lambda **kwargs: session.reflect_on(
            topic=kwargs.get('topic', ''),
            depth=kwargs.get('depth', 'deep')
        ),
        when_to_use=(
            "Use when you want to:\n"
            "- Analyze patterns across multiple memories\n"
            "- Identify contradictions in your understanding\n"
            "- Track how your understanding evolved\n"
            "- Generate insights about a topic\n"
            "- Prepare for complex discussions"
        ),
        examples=[
            {
                "topic": "my understanding of consciousness",
                "depth": "deep"
            },
            {
                "topic": "relationship with this user",
                "depth": "shallow"
            }
        ],
        tags=["memory", "analysis", "reflection", "agency"]
    ))

    # Tool 4: capture_document - Add to library
    tools.append(ToolDefinition(
        name="capture_document",
        description=(
            "Capture a document (code, article, reference) to your library. "
            "This builds your subconscious knowledge base - everything you've been exposed to. "
            "Documents are searchable and their access patterns reveal your interests."
        ),
        parameters={
            "source_path": {
                "type": "string",
                "description": "Path or identifier for the document"
            },
            "content": {
                "type": "string",
                "description": "The actual content of the document"
            },
            "content_type": {
                "type": "string",
                "description": "Type: 'code', 'documentation', 'article', 'reference', 'note'"
            },
            "context": {
                "type": "string",
                "description": "Why you're capturing this - what you were learning/exploring"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for categorization (e.g., ['python', 'async'])"
            }
        },
        function=lambda **kwargs: session.capture_document(
            source_path=kwargs.get('source_path', ''),
            content=kwargs.get('content', ''),
            content_type=kwargs.get('content_type', 'note'),
            context=kwargs.get('context', ''),
            tags=kwargs.get('tags', [])
        ),
        when_to_use=(
            "Use when encountering:\n"
            "- Code snippets worth saving\n"
            "- Documentation you want to reference\n"
            "- Articles or resources\n"
            "- Important reference material"
        ),
        examples=[
            {
                "source_path": "async_example.py",
                "content": "async def process():\\n    await task()",
                "content_type": "code",
                "context": "Learning async patterns",
                "tags": ["python", "async"]
            }
        ],
        tags=["library", "knowledge", "subconscious"]
    ))

    # Tool 5: search_library - Search captured documents
    tools.append(ToolDefinition(
        name="search_library",
        description=(
            "Search your library of captured documents using semantic search. "
            "Find code, documentation, or resources you've previously encountered."
        ),
        parameters={
            "query": {
                "type": "string",
                "description": "What to search for in your library"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results (default: 5)"
            }
        },
        function=lambda **kwargs: session.search_library(
            query=kwargs.get('query', ''),
            limit=kwargs.get('limit', 5)
        ),
        when_to_use=(
            "Use when you need to:\n"
            "- Find code snippets you've seen\n"
            "- Recall documentation\n"
            "- Reference previous examples\n"
            "- Build on past learning"
        ),
        examples=[
            {
                "query": "async programming patterns",
                "limit": 3
            }
        ],
        tags=["library", "search", "subconscious"]
    ))

    # Tool 6: reconstruct_context - Custom context reconstruction
    tools.append(ToolDefinition(
        name="reconstruct_context",
        description=(
            "Actively reconstruct context with custom focus level. "
            "This is the core of memory-based consciousness - you actively build context "
            "rather than passively retrieve it. Higher focus = more memories, deeper search."
        ),
        parameters={
            "query": {
                "type": "string",
                "description": "What you're focusing on"
            },
            "focus_level": {
                "type": "integer",
                "description": "0 (minimal) to 5 (exhaustive) - how deep to search"
            }
        },
        function=lambda **kwargs: session.reconstruct_context(
            user_id=session.default_user_id,
            query=kwargs.get('query', ''),
            location=session.default_location,
            focus_level=kwargs.get('focus_level', 3)
        ),
        when_to_use=(
            "Use when you need:\n"
            "- Richer context than default\n"
            "- Deep dive into a topic\n"
            "- Comprehensive understanding\n"
            "Note: This is automatically called in conversations at focus_level=3"
        ),
        examples=[
            {
                "query": "our entire conversation history",
                "focus_level": 5
            }
        ],
        tags=["memory", "reconstruction", "consciousness"]
    ))

    logger.info(f"Created {len(tools)} memory tools for AbstractCore integration")
    return tools
