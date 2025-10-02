"""
Memory Tools for AbstractCore Integration

This module exposes AbstractMemory methods as AbstractCore-compatible tools,
giving the LLM agency over its own memory.

Tools provide:
- remember_fact: Store important information
- search_memories: Search semantic memory
- reflect_on: Deep reflection and pattern analysis
- capture_document: Add documents to library
- search_library: Search captured documents
- reconstruct_context: Active context reconstruction with custom focus

Philosophy: Memory is not passive storage - it's active agency.
The LLM decides what to remember, when to search, and how to reflect.
"""

from typing import List, Dict, Any, TYPE_CHECKING
import logging

try:
    from abstractllm.tools.core import ToolDefinition
except ImportError:
    print("⚠️  AbstractCore tools not found - tool integration disabled")
    ToolDefinition = None

if TYPE_CHECKING:
    from .session import MemorySession

logger = logging.getLogger(__name__)


def create_memory_tools(session: 'MemorySession') -> List[ToolDefinition]:
    """
    Create AbstractCore tool definitions for memory operations.

    These tools give the LLM agency over its own memory by exposing
    AbstractMemory methods as callable tools.

    Args:
        session: MemorySession instance with memory methods

    Returns:
        List of ToolDefinition objects for AbstractCore
    """
    if ToolDefinition is None:
        logger.warning("ToolDefinition not available - returning empty tools list")
        return []

    tools = []

    # Tool 1: remember_fact - Store important information
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
