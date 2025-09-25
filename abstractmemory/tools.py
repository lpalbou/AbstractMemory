"""
Memory management tools for AI agents using MemorySession.

These tools allow agents to query, update, and manage their own memory,
following AbstractCore tool patterns for optimal LLM guidance.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
import json

try:
    from abstractllm.tools.core import tool
    _ABSTRACTCORE_TOOLS_AVAILABLE = True
except ImportError:
    # Fallback decorator when AbstractCore not available
    def tool(description="", tags=None, when_to_use="", examples=None, **kwargs):
        def decorator(func):
            # Store metadata on function
            func._tool_metadata = {
                'description': description,
                'tags': tags or [],
                'when_to_use': when_to_use,
                'examples': examples or [],
                **kwargs
            }
            return func
        return decorator
    _ABSTRACTCORE_TOOLS_AVAILABLE = False


class MemoryTools:
    """Memory management tools for autonomous agents."""

    def __init__(self, memory_session):
        """
        Initialize memory tools with reference to MemorySession.

        Args:
            memory_session: MemorySession instance to operate on
        """
        self.memory_session = memory_session

    @tool(
        description="Search your memory for specific information across all memory types",
        tags=["memory", "search", "recall", "context"],
        when_to_use="When you need to recall past conversations, facts, events, or information about users",
        examples=[
            {
                "description": "Find what user Alice said about Python",
                "arguments": {
                    "query": "Python",
                    "user_id": "alice",
                    "memory_types": ["working", "semantic", "episodic"]
                }
            },
            {
                "description": "Search for recent failures with API calls",
                "arguments": {
                    "query": "API error failed",
                    "memory_types": ["episodic", "working"],
                    "limit": 5
                }
            },
            {
                "description": "Find information about machine learning from last week",
                "arguments": {
                    "query": "machine learning",
                    "start_date": "2024-01-15",
                    "limit": 3
                }
            }
        ]
    )
    def search_memory(self, query: str, user_id: Optional[str] = None,
                     memory_types: Optional[List[str]] = None,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None,
                     limit: int = 5) -> str:
        """
        Search agent memory by query, user, date, or memory type.

        Args:
            query: What to search for (keywords, topics, concepts)
            user_id: Filter by specific user (default: searches all users)
            memory_types: List of memory types to search ["working", "semantic", "episodic", "storage"]
            start_date: Search from this date (YYYY-MM-DD format)
            end_date: Search until this date (YYYY-MM-DD format)
            limit: Maximum number of results to return

        Returns:
            Formatted search results with relevance and context
        """
        try:
            # Default to searching all relevant memory types
            if memory_types is None:
                memory_types = ["working", "semantic", "episodic", "storage"]

            # Search across specified memory types
            results = self.memory_session.search_by_memory_type(
                query=query,
                memory_types=memory_types,
                user_id=user_id,
                limit=limit
            )

            # Format results for agent consumption
            formatted_results = []
            total_found = 0

            for memory_type, items in results.items():
                if items:
                    total_found += len(items)
                    formatted_results.append(f"=== {memory_type.title()} Memory ===")

                    for i, item in enumerate(items[:limit], 1):
                        content = item.get('content', 'No content')
                        confidence = item.get('confidence', 1.0)

                        # Truncate long content
                        if len(str(content)) > 200:
                            content = str(content)[:200] + "..."

                        formatted_results.append(f"{i}. {content} (confidence: {confidence:.2f})")

            if total_found == 0:
                return f"No results found for '{query}' in {', '.join(memory_types)} memory."

            result_summary = f"Found {total_found} results for '{query}':\n\n" + "\n".join(formatted_results)

            # Add helpful suggestions
            if total_found == limit:
                result_summary += f"\n\n💡 More results may be available. Try increasing limit or narrowing your search."

            return result_summary

        except Exception as e:
            return f"Memory search failed: {str(e)}"

    @tool(
        description="Remember an important fact or piece of information for future reference",
        tags=["memory", "remember", "fact", "learning", "knowledge"],
        when_to_use="When users share important information, preferences, or facts you should remember",
        examples=[
            {
                "description": "Remember user's programming language preference",
                "arguments": {
                    "fact": "Alice prefers Python for data science projects",
                    "user_id": "alice"
                }
            },
            {
                "description": "Remember a general rule or constraint",
                "arguments": {
                    "fact": "API rate limit is 1000 requests per hour"
                }
            },
            {
                "description": "Remember successful solution for future reference",
                "arguments": {
                    "fact": "To fix authentication errors, clear cookies and retry login",
                    "category": "troubleshooting"
                }
            }
        ]
    )
    def remember_fact(self, fact: str, user_id: Optional[str] = None,
                     category: Optional[str] = None) -> str:
        """
        Store an important fact in semantic memory for future reference.

        Args:
            fact: The fact or information to remember
            user_id: Associate with specific user (optional)
            category: Categorize the fact (e.g., "preference", "constraint", "solution")

        Returns:
            Confirmation that the fact was stored
        """
        try:
            if user_id:
                # Store as user-specific fact
                self.memory_session.learn_about_user(fact, user_id)
                return f"✅ Remembered about {user_id}: {fact}"
            else:
                # Store as general semantic fact
                # For now, use the learn_about_user with default user
                # In future, could add a general learn_fact method
                effective_user = self.memory_session.current_user_id
                self.memory_session.learn_about_user(fact, effective_user)
                return f"✅ Remembered general fact: {fact}"

        except Exception as e:
            return f"❌ Failed to remember fact: {str(e)}"

    @tool(
        description="Get detailed profile information about a specific user",
        tags=["memory", "user", "profile", "relationship", "context"],
        when_to_use="When you need to understand a user's background, preferences, or interaction history",
        examples=[
            {
                "description": "Get profile for user Alice",
                "arguments": {
                    "user_id": "alice"
                }
            },
            {
                "description": "Get current user's profile",
                "arguments": {}
            }
        ]
    )
    def get_user_profile(self, user_id: Optional[str] = None) -> str:
        """
        Retrieve comprehensive profile information for a user.

        Args:
            user_id: Specific user to get profile for (default: current user)

        Returns:
            Formatted user profile with facts, preferences, and interaction history
        """
        try:
            profile = self.memory_session.get_user_profile(user_id)

            if not profile.get('profile_available'):
                return f"No profile found for user: {user_id or 'current user'}"

            # Format profile information
            lines = [
                f"=== Profile: {profile['user_id']} ===",
                f"Relationship: {profile.get('relationship', 'unknown')}",
                f"Interactions: {profile.get('interaction_count', 0)}",
            ]

            if profile.get('first_seen'):
                lines.append(f"First seen: {profile['first_seen']}")

            facts = profile.get('facts', [])
            if facts:
                lines.append(f"\nKnown facts ({len(facts)}):")
                for i, fact in enumerate(facts[:10], 1):  # Limit to 10 facts
                    lines.append(f"  {i}. {fact}")

                if len(facts) > 10:
                    lines.append(f"  ... and {len(facts) - 10} more facts")

            preferences = profile.get('preferences', {})
            if preferences:
                lines.append(f"\nPreferences:")
                for key, value in preferences.items():
                    lines.append(f"  - {key}: {value}")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to get user profile: {str(e)}"

    @tool(
        description="Update your core identity or persona based on new information",
        tags=["memory", "core", "identity", "persona", "self-editing"],
        when_to_use="When you learn something fundamental about your role, capabilities, or identity that should be remembered permanently",
        examples=[
            {
                "description": "Update specialization in persona",
                "arguments": {
                    "block": "persona",
                    "content": "I am an AI assistant specializing in Python development and machine learning",
                    "reason": "User frequently asks Python/ML questions, specialization will improve responses"
                }
            },
            {
                "description": "Update knowledge about user base",
                "arguments": {
                    "block": "user_info",
                    "content": "Primary users are software developers working on AI applications",
                    "reason": "Pattern observed across multiple user interactions"
                }
            }
        ]
    )
    def update_core_memory(self, block: str, content: str, reason: str = "") -> str:
        """
        Update core memory blocks (agent identity/persona).

        IMPORTANT: This updates your permanent identity. Use carefully and only for
        fundamental changes to your role, capabilities, or persistent knowledge.

        Args:
            block: Memory block to update ("persona" for identity, "user_info" for user knowledge)
            content: New content for the block
            reason: Explanation for why this update is needed

        Returns:
            Confirmation of the update or error message
        """
        try:
            # Check if self-editing is enabled
            config = self.memory_session.memory_injection_config
            if not config.enable_self_editing:
                return "❌ Core memory self-editing is disabled. Contact administrator to enable."

            # Validate block name
            valid_blocks = ["persona", "user_info"]
            if block not in valid_blocks:
                return f"❌ Invalid block '{block}'. Valid blocks: {', '.join(valid_blocks)}"

            # Update the core memory
            if hasattr(self.memory_session.memory, 'update_core_memory'):
                success = self.memory_session.memory.update_core_memory(block, content, reason)

                if success:
                    return f"✅ Updated core memory block '{block}': {content[:100]}{'...' if len(content) > 100 else ''}"
                else:
                    return f"❌ Failed to update core memory block '{block}'. Content may be too long or block invalid."
            else:
                return "❌ Core memory editing not supported by current memory system."

        except Exception as e:
            return f"❌ Core memory update failed: {str(e)}"

    @tool(
        description="Get recent working memory (short-term context)",
        tags=["memory", "working", "recent", "context", "conversation"],
        when_to_use="When you need to review recent conversation context or short-term information",
        examples=[
            {
                "description": "Get last 5 working memory items",
                "arguments": {
                    "limit": 5
                }
            },
            {
                "description": "Get recent context for review",
                "arguments": {
                    "limit": 10
                }
            }
        ]
    )
    def get_recent_context(self, limit: int = 10) -> str:
        """
        Retrieve recent working memory items (short-term context).

        Args:
            limit: Maximum number of recent items to retrieve

        Returns:
            Formatted list of recent memory items
        """
        try:
            working_items = self.memory_session.get_working_memory(limit=limit)

            if not working_items:
                return "No recent context available in working memory."

            lines = [f"=== Recent Context ({len(working_items)} items) ==="]

            for i, item in enumerate(working_items, 1):
                content = item.get('content', 'No content')
                event_time = item.get('event_time')
                confidence = item.get('confidence', 1.0)

                # Format content
                if isinstance(content, dict):
                    content_str = content.get('text', str(content))
                else:
                    content_str = str(content)

                # Truncate if too long
                if len(content_str) > 150:
                    content_str = content_str[:150] + "..."

                # Add timestamp if available
                time_str = ""
                if event_time:
                    try:
                        if isinstance(event_time, str):
                            time_str = f" ({event_time[:19]})"  # YYYY-MM-DD HH:MM:SS
                    except:
                        pass

                lines.append(f"{i}. {content_str}{time_str}")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to get recent context: {str(e)}"

    @tool(
        description="Get validated semantic facts from long-term memory",
        tags=["memory", "semantic", "facts", "knowledge", "learned"],
        when_to_use="When you need to access established facts, learned knowledge, or validated information",
        examples=[
            {
                "description": "Get facts about Python programming",
                "arguments": {
                    "topic": "Python",
                    "limit": 5
                }
            },
            {
                "description": "Get all validated facts",
                "arguments": {
                    "limit": 10
                }
            }
        ]
    )
    def get_semantic_facts(self, topic: Optional[str] = None, limit: int = 10) -> str:
        """
        Retrieve validated semantic facts from long-term memory.

        Args:
            topic: Filter facts by topic/keyword (optional)
            limit: Maximum number of facts to retrieve

        Returns:
            Formatted list of validated facts with confidence scores
        """
        try:
            facts = self.memory_session.get_semantic_facts(topic=topic, limit=limit)

            if not facts:
                topic_str = f" about '{topic}'" if topic else ""
                return f"No validated facts found{topic_str}."

            topic_header = f" about '{topic}'" if topic else ""
            lines = [f"=== Validated Facts{topic_header} ({len(facts)} items) ==="]

            for i, fact in enumerate(facts, 1):
                content = fact.get('content', 'No content')
                confidence = fact.get('confidence', 1.0)

                # Truncate long facts
                if len(str(content)) > 200:
                    content = str(content)[:200] + "..."

                lines.append(f"{i}. {content} (confidence: {confidence:.2f})")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to get semantic facts: {str(e)}"


def create_memory_tools(memory_session) -> List:
    """
    Create memory management tools for a MemorySession.

    Args:
        memory_session: MemorySession instance

    Returns:
        List of memory tool functions
    """
    tools = MemoryTools(memory_session)

    # Return list of tool functions with proper metadata
    tool_functions = [
        tools.search_memory,
        tools.remember_fact,
        tools.get_user_profile,
        tools.get_recent_context,
        tools.get_semantic_facts,
    ]

    # Add core memory editing only if enabled
    config = memory_session.memory_injection_config
    if config.enable_self_editing and 'update_core_memory' in config.allowed_memory_operations:
        tool_functions.append(tools.update_core_memory)

    return tool_functions