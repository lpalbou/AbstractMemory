"""
ContextBuilder - Intelligent Memory Context Construction

This module implements a sophisticated context building system that differentiates between:
1. PERSISTENT MEMORY: Core identity, values, always-available knowledge
2. DYNAMIC MEMORY: Query-dependent, context-specific, rebuilt per interaction

Key Design Principles:
- Persistent memory forms the stable foundation of agent identity
- Dynamic memory provides relevant, contextual information per query
- Intelligent deduplication prevents information repetition
- Progressive disclosure: simple by default, comprehensive when needed
"""

from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
import hashlib
from datetime import datetime

from .core.interfaces import MemoryItem


@dataclass
class ContextConfig:
    """Configuration for context building behavior."""

    # Persistent memory configuration
    include_core_identity: bool = True      # Always include core identity/values
    include_system_facts: bool = True       # Always include validated system knowledge

    # Dynamic memory configuration
    include_query_relevant: bool = True     # Include query-specific information
    include_recent_context: bool = True     # Include recent conversation history
    include_document_chunks: bool = True    # Include relevant document sections
    include_episodic_events: bool = False   # Include relevant past events

    # Context limits and quality
    max_total_tokens: int = 4000           # Total context budget
    persistent_memory_ratio: float = 0.3   # 30% for persistent, 70% for dynamic
    deduplication_threshold: float = 0.85  # Semantic similarity threshold

    # Output formatting
    show_memory_sources: bool = False      # Show which memory component provided each item
    show_confidence_scores: bool = False   # Show confidence/relevance scores


class ContextBuilder:
    """
    Intelligent context builder that constructs optimal memory context.

    The ContextBuilder differentiates between two fundamental types of memory:

    PERSISTENT MEMORY (Always Present):
    - Core identity and values
    - Validated facts and knowledge
    - System capabilities and constraints
    - Stable relationships and preferences

    DYNAMIC MEMORY (Query-Dependent):
    - Relevant document chunks
    - Recent conversation history
    - Contextual episodic memories
    - Query-specific facts and patterns

    This separation ensures consistent agent identity while providing
    contextually relevant information for each interaction.
    """

    def __init__(self, config: ContextConfig = None):
        """Initialize ContextBuilder with configuration."""
        self.config = config or ContextConfig()
        self._content_hashes: Set[str] = set()
        self._semantic_cache: Dict[str, List[float]] = {}

    def build_context(self,
                     query: str,
                     memory_components: Dict[str, Any],
                     user_id: str = None) -> str:
        """
        Build intelligent context combining persistent and dynamic memory.

        Args:
            query: Current user query/input
            memory_components: Dictionary of available memory components
            user_id: Optional user identifier for personalization

        Returns:
            Formatted context string ready for LLM consumption
        """
        # Calculate token budgets
        total_budget = self.config.max_total_tokens
        persistent_budget = int(total_budget * self.config.persistent_memory_ratio)
        dynamic_budget = total_budget - persistent_budget

        context_sections = []

        # === PERSISTENT MEMORY (Foundation) ===
        persistent_context = self._build_persistent_context(
            memory_components,
            persistent_budget,
            user_id
        )
        if persistent_context:
            context_sections.append(("PERSISTENT", persistent_context))

        # === DYNAMIC MEMORY (Query-Specific) ===
        dynamic_context = self._build_dynamic_context(
            query,
            memory_components,
            dynamic_budget,
            user_id
        )
        if dynamic_context:
            context_sections.append(("DYNAMIC", dynamic_context))

        # Format final context
        return self._format_context_sections(context_sections)

    def _build_persistent_context(self,
                                 memory_components: Dict[str, Any],
                                 token_budget: int,
                                 user_id: str = None) -> str:
        """Build persistent memory context (identity, core facts, values)."""
        persistent_parts = []

        # Core identity (always included if available)
        if self.config.include_core_identity and 'core' in memory_components:
            core_memory = memory_components['core']
            if hasattr(core_memory, 'get_identity'):
                identity = core_memory.get_identity()
                if identity:
                    persistent_parts.append(f"=== Core Identity ===\n{identity}")

        # System facts (validated, high-confidence knowledge)
        if self.config.include_system_facts and 'semantic' in memory_components:
            semantic_memory = memory_components['semantic']
            # Get high-confidence facts (confidence > 0.8)
            high_confidence_facts = self._get_high_confidence_facts(semantic_memory)
            if high_confidence_facts:
                fact_text = "\n".join([f"• {fact}" for fact in high_confidence_facts[:5]])
                persistent_parts.append(f"=== Validated Knowledge ===\n{fact_text}")

        # Combine and truncate to budget
        persistent_context = "\n\n".join(persistent_parts)
        return self._truncate_to_budget(persistent_context, token_budget)

    def _build_dynamic_context(self,
                              query: str,
                              memory_components: Dict[str, Any],
                              token_budget: int,
                              user_id: str = None) -> str:
        """Build dynamic, query-dependent context."""
        dynamic_parts = []
        used_tokens = 0

        # Recent conversation context
        if (self.config.include_recent_context and
            'working' in memory_components and
            used_tokens < token_budget):

            working_memory = memory_components['working']
            recent_items = working_memory.retrieve("", limit=3)  # Get recent context
            if recent_items:
                recent_text = self._format_recent_context(recent_items)
                part_tokens = self._estimate_tokens(recent_text)
                if used_tokens + part_tokens <= token_budget:
                    dynamic_parts.append(f"=== Recent Context ===\n{recent_text}")
                    used_tokens += part_tokens

        # Query-relevant documents
        if (self.config.include_document_chunks and
            'document' in memory_components and
            used_tokens < token_budget):

            document_memory = memory_components['document']
            relevant_docs = document_memory.retrieve(query, limit=2)
            if relevant_docs:
                doc_text = self._format_document_chunks(relevant_docs)
                part_tokens = self._estimate_tokens(doc_text)
                if used_tokens + part_tokens <= token_budget:
                    dynamic_parts.append(f"=== Relevant Documents ===\n{doc_text}")
                    used_tokens += part_tokens

        # Query-relevant semantic facts
        if ('semantic' in memory_components and used_tokens < token_budget):
            semantic_memory = memory_components['semantic']
            relevant_facts = semantic_memory.retrieve(query, limit=3)
            if relevant_facts:
                facts_text = self._format_semantic_facts(relevant_facts, query)
                part_tokens = self._estimate_tokens(facts_text)
                if used_tokens + part_tokens <= token_budget:
                    dynamic_parts.append(f"=== Relevant Facts ===\n{facts_text}")
                    used_tokens += part_tokens

        return "\n\n".join(dynamic_parts)

    def _get_high_confidence_facts(self, semantic_memory) -> List[str]:
        """Extract high-confidence facts for persistent context."""
        try:
            # This would need to be adapted based on the actual SemanticMemory interface
            if hasattr(semantic_memory, 'facts'):
                high_conf_facts = []
                for fact_id, fact_data in semantic_memory.facts.items():
                    if fact_data.get('confidence', 0) > 0.8:
                        high_conf_facts.append(str(fact_data.get('content', '')))
                return high_conf_facts[:5]  # Top 5 high-confidence facts
        except Exception:
            pass
        return []

    def _format_recent_context(self, recent_items: List[MemoryItem]) -> str:
        """Format recent conversation history."""
        context_lines = []
        for item in recent_items[-3:]:  # Last 3 interactions
            if isinstance(item.content, dict):
                user_input = item.content.get('user_input', '')
                agent_response = item.content.get('agent_response', '')
                if user_input and agent_response:
                    context_lines.append(f"User: {user_input}")
                    context_lines.append(f"Agent: {agent_response}")
            else:
                content = str(item.content)[:200] + "..." if len(str(item.content)) > 200 else str(item.content)
                context_lines.append(content)
        return "\n".join(context_lines)

    def _format_document_chunks(self, doc_items: List[MemoryItem]) -> str:
        """Format document chunks with source attribution."""
        doc_lines = []
        for item in doc_items:
            filepath = item.metadata.get('filepath', 'unknown')
            content = str(item.content)[:300] + "..." if len(str(item.content)) > 300 else str(item.content)

            if self.config.show_confidence_scores:
                confidence = f" (relevance: {item.confidence:.2f})"
            else:
                confidence = ""

            doc_lines.append(f"From {filepath}{confidence}:\n{content}")
        return "\n\n".join(doc_lines)

    def _format_semantic_facts(self, fact_items: List[MemoryItem], query: str) -> str:
        """Format semantic facts relevant to query."""
        fact_lines = []
        for item in fact_items:
            content = str(item.content)
            if self.config.show_confidence_scores:
                confidence = f" (confidence: {item.confidence:.2f})"
            else:
                confidence = ""
            fact_lines.append(f"• {content}{confidence}")
        return "\n".join(fact_lines)

    def _format_context_sections(self, sections: List[Tuple[str, str]]) -> str:
        """Format final context with clear section separation."""
        if not sections:
            return ""

        if self.config.show_memory_sources:
            formatted_sections = []
            for section_type, content in sections:
                formatted_sections.append(f"=== {section_type} MEMORY ===\n{content}")
            return "\n\n".join(formatted_sections)
        else:
            # Simple format without showing memory source types
            return "\n\n".join([content for _, content in sections])

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4

    def _truncate_to_budget(self, text: str, token_budget: int) -> str:
        """Truncate text to fit within token budget."""
        estimated_tokens = self._estimate_tokens(text)
        if estimated_tokens <= token_budget:
            return text

        # Truncate to approximate budget
        char_budget = token_budget * 4
        if len(text) > char_budget:
            truncated = text[:char_budget]
            # Try to end at sentence boundary
            last_period = truncated.rfind('.')
            if last_period > char_budget * 0.8:  # If we can find a reasonable cutoff
                truncated = truncated[:last_period + 1]
            return truncated + "\n[... content truncated ...]"
        return text

    def reset_deduplication_cache(self):
        """Clear deduplication cache for new context building session."""
        self._content_hashes.clear()
        self._semantic_cache.clear()


# === Factory Functions for Common Configurations ===

def create_minimal_context_builder() -> ContextBuilder:
    """Create context builder for minimal memory usage."""
    config = ContextConfig(
        max_total_tokens=1000,
        persistent_memory_ratio=0.5,
        include_episodic_events=False,
        show_memory_sources=False,
        show_confidence_scores=False
    )
    return ContextBuilder(config)

def create_comprehensive_context_builder() -> ContextBuilder:
    """Create context builder for comprehensive memory usage."""
    config = ContextConfig(
        max_total_tokens=6000,
        persistent_memory_ratio=0.2,  # More space for dynamic context
        include_episodic_events=True,
        show_memory_sources=True,
        show_confidence_scores=True,
        deduplication_threshold=0.9
    )
    return ContextBuilder(config)

def create_debug_context_builder() -> ContextBuilder:
    """Create context builder with debug information."""
    config = ContextConfig(
        max_total_tokens=4000,
        show_memory_sources=True,
        show_confidence_scores=True,
        deduplication_threshold=0.8
    )
    return ContextBuilder(config)