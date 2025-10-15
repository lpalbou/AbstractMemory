"""
ReAct Memory Agent for progressive memory exploration.

This agent implements a ReAct (Reasoning and Acting) loop that allows
the AI to progressively explore its memory, starting shallow and going
deeper only when needed.

Key features:
- Progressive exploration (start shallow, go deeper as needed)
- Structured feedback for reasoning
- Exploration history tracking
- Multi-strategy search (depth, breadth, targeted)
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MemorySearchResult:
    """
    Structured result from memory search that AI can reason about.

    This replaces string-based returns with structured data that enables
    the AI to make informed decisions about whether to search deeper.
    """
    memories: List[Dict[str, Any]]
    total_found: int
    relevance_scores: List[float]
    memory_types_covered: List[str]
    suggests_deeper_search: bool
    next_search_hints: List[str]
    search_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def average_relevance(self) -> float:
        """Calculate average relevance score."""
        if not self.relevance_scores:
            return 0.0
        return sum(self.relevance_scores) / len(self.relevance_scores)

    @property
    def has_high_quality_results(self) -> bool:
        """Check if results are high quality (relevance > 0.7)."""
        return self.average_relevance > 0.7 and self.total_found > 0

    def merge_with(self, other: 'MemorySearchResult') -> 'MemorySearchResult':
        """Merge with another search result."""
        return MemorySearchResult(
            memories=self.memories + other.memories,
            total_found=self.total_found + other.total_found,
            relevance_scores=self.relevance_scores + other.relevance_scores,
            memory_types_covered=list(set(self.memory_types_covered + other.memory_types_covered)),
            suggests_deeper_search=self.suggests_deeper_search or other.suggests_deeper_search,
            next_search_hints=list(set(self.next_search_hints + other.next_search_hints)),
            search_metadata={**self.search_metadata, **other.search_metadata}
        )


@dataclass
class ThoughtProcess:
    """
    Represents the agent's reasoning about memory exploration.

    This structures the "thinking" part of the ReAct loop, making
    the agent's reasoning transparent and traceable.
    """
    query: str
    current_context_quality: str  # "insufficient", "partial", "sufficient"
    memories_examined: int
    focus_level: int
    reasoning: str
    action: str  # "increase_depth", "search_specific", "sufficient"
    memory_type: Optional[str] = None
    search_query: Optional[str] = None
    confidence: float = 0.5

    @property
    def sufficient_context(self) -> bool:
        """Check if we have sufficient context."""
        return self.current_context_quality == "sufficient"

    @property
    def needs_deeper_search(self) -> bool:
        """Check if deeper search is needed."""
        return self.action == "increase_depth"

    @property
    def needs_specific_search(self) -> bool:
        """Check if specific memory type search is needed."""
        return self.action == "search_specific"


class ReactMemoryAgent:
    """
    ReAct agent for progressive memory exploration.

    This agent implements a reasoning loop that:
    1. Starts with shallow memory search
    2. Observes and reasons about results
    3. Decides whether more context is needed
    4. Acts by searching deeper or in specific memory types
    5. Repeats until sufficient context is obtained

    This gives the AI agency over its memory exploration rather than
    retrieving everything at once.
    """

    def __init__(self, session):
        """
        Initialize the ReAct memory agent.

        Args:
            session: MemorySession instance with access to all memory systems
        """
        self.session = session
        self.exploration_history = []
        self.llm_provider = session.provider

    def explore_progressively(
        self,
        query: str,
        max_iterations: int = 5,
        initial_focus: int = 0,
        strategy: str = "balanced"
    ) -> Dict[str, Any]:
        """
        Progressively explore memory with ReAct loop.

        Args:
            query: The query to explore memory for
            max_iterations: Maximum exploration iterations
            initial_focus: Starting focus level (0=minimal, 5=exhaustive)
            strategy: Exploration strategy ("balanced", "deep", "broad")

        Returns:
            Dictionary with final context and exploration trace
        """
        focus_level = initial_focus
        all_memories = {}
        iteration = 0

        logger.info(f"Starting progressive exploration for: {query}")

        while iteration < max_iterations:
            # Think: Analyze current context
            thought = self._think_about_context(
                query, all_memories, focus_level, iteration
            )

            logger.info(f"Iteration {iteration}: {thought.action} "
                       f"(confidence: {thought.confidence:.2f})")

            # Check if we have sufficient context
            if thought.sufficient_context:
                logger.info("Sufficient context obtained")
                break

            # Act: Retrieve more memories based on reasoning
            if thought.needs_deeper_search:
                focus_level = min(focus_level + 1, 5)
                new_result = self._search_at_level(query, focus_level)

            elif thought.needs_specific_search:
                new_result = self._search_memory_type(
                    thought.search_query or query,
                    thought.memory_type,
                    focus_level
                )
            else:
                # Default: increase depth slightly
                focus_level = min(focus_level + 1, 5)
                new_result = self._search_at_level(query, focus_level)

            # Observe: Update memory collection
            self._merge_memories(all_memories, new_result)

            # Track exploration history
            self.exploration_history.append({
                'iteration': iteration,
                'thought': thought,
                'memories_found': new_result.total_found,
                'total_memories': len(all_memories),
                'focus_level': focus_level
            })

            iteration += 1

        # Synthesize final context
        final_context = self._synthesize_context(all_memories, query)

        return {
            'context': final_context,
            'memories': all_memories,
            'exploration_trace': self.exploration_history,
            'iterations': iteration,
            'final_focus_level': focus_level
        }

    def _think_about_context(
        self,
        query: str,
        current_memories: Dict,
        focus_level: int,
        iteration: int
    ) -> ThoughtProcess:
        """
        Analyze current context and decide next action.

        This is the "thinking" part of the ReAct loop where the agent
        reasons about whether it has sufficient context.
        """
        memory_count = len(current_memories)

        # Use LLM to reason about context sufficiency
        if self.llm_provider:
            reasoning = self._llm_reasoning(query, current_memories, focus_level)
        else:
            # Fallback heuristic reasoning
            reasoning = self._heuristic_reasoning(
                query, memory_count, focus_level, iteration
            )

        return reasoning

    def _llm_reasoning(
        self,
        query: str,
        current_memories: Dict,
        focus_level: int
    ) -> ThoughtProcess:
        """
        Use LLM to reason about context sufficiency.
        """
        # Format current context for LLM
        context_summary = self._summarize_memories(current_memories)

        prompt = f"""
        Query: {query}
        Current focus level: {focus_level}/5
        Memories retrieved: {len(current_memories)}

        Memory types covered: {', '.join(set(m.get('type', 'unknown') for m in current_memories.values()))}

        Context summary:
        {context_summary}

        Based on this context, determine:
        1. Is the current context sufficient to answer the query?
        2. If not, what action should be taken?
           - "increase_depth": Search deeper in all memory types
           - "search_specific": Search a specific memory type
           - "sufficient": We have enough context

        Respond with your reasoning and decision.
        """

        try:
            response = self.llm_provider.generate(prompt, max_tokens=500)

            # Parse LLM response into ThoughtProcess
            return self._parse_llm_reasoning(response, query, current_memories, focus_level)

        except Exception as e:
            logger.warning(f"LLM reasoning failed: {e}, using heuristics")
            return self._heuristic_reasoning(query, len(current_memories), focus_level, 0)

    def _heuristic_reasoning(
        self,
        query: str,
        memory_count: int,
        focus_level: int,
        iteration: int
    ) -> ThoughtProcess:
        """
        Fallback heuristic reasoning when LLM is not available.
        """
        # Simple heuristics for context sufficiency
        if memory_count == 0 and focus_level < 2:
            return ThoughtProcess(
                query=query,
                current_context_quality="insufficient",
                memories_examined=memory_count,
                focus_level=focus_level,
                reasoning="No memories found yet, need to search deeper",
                action="increase_depth",
                confidence=0.9
            )

        if memory_count < 3 and focus_level < 3:
            return ThoughtProcess(
                query=query,
                current_context_quality="partial",
                memories_examined=memory_count,
                focus_level=focus_level,
                reasoning=f"Only {memory_count} memories found, likely need more context",
                action="increase_depth",
                confidence=0.7
            )

        if memory_count > 10 or focus_level >= 4:
            return ThoughtProcess(
                query=query,
                current_context_quality="sufficient",
                memories_examined=memory_count,
                focus_level=focus_level,
                reasoning=f"Have {memory_count} memories at focus level {focus_level}, sufficient context",
                action="sufficient",
                confidence=0.8
            )

        # Check for specific memory type needs
        if "remember" in query.lower() and iteration < 2:
            return ThoughtProcess(
                query=query,
                current_context_quality="partial",
                memories_examined=memory_count,
                focus_level=focus_level,
                reasoning="Query asks about remembering, search episodic memory",
                action="search_specific",
                memory_type="episodic",
                search_query=query,
                confidence=0.6
            )

        # Default: go deeper
        return ThoughtProcess(
            query=query,
            current_context_quality="partial",
            memories_examined=memory_count,
            focus_level=focus_level,
            reasoning="Need more context for comprehensive answer",
            action="increase_depth",
            confidence=0.5
        )

    def _search_at_level(self, query: str, focus_level: int) -> MemorySearchResult:
        """
        Search memory at a specific focus level.
        """
        # Use existing reconstruct_context with specified focus level
        context_data = self.session.reconstruct_context(
            user_id=self.session.default_user_id,
            query=query,
            location=self.session.default_location,
            focus_level=focus_level
        )

        # Convert to MemorySearchResult
        memories = []
        relevance_scores = []
        memory_types = set()

        # Extract memories from different types in context
        for key in ['semantic_memories', 'episodic_memories', 'library_excerpts']:
            if key in context_data:
                for mem in context_data[key]:
                    memories.append(mem)
                    relevance_scores.append(mem.get('relevance', 0.5))
                    memory_types.add(key.replace('_memories', '').replace('_excerpts', ''))

        return MemorySearchResult(
            memories=memories,
            total_found=len(memories),
            relevance_scores=relevance_scores,
            memory_types_covered=list(memory_types),
            suggests_deeper_search=(focus_level < 3),
            next_search_hints=self._generate_search_hints(query, memories),
            search_metadata={'focus_level': focus_level}
        )

    def _search_memory_type(
        self,
        query: str,
        memory_type: str,
        focus_level: int
    ) -> MemorySearchResult:
        """
        Search a specific memory type.
        """
        memories = []
        relevance_scores = []

        # Route to appropriate memory manager
        if memory_type == "episodic" and hasattr(self.session, 'episodic_memory'):
            results = self.session.episodic_memory.search(query, limit=10)
            memories.extend(results)

        elif memory_type == "semantic" and hasattr(self.session, 'semantic_memory'):
            results = self.session.semantic_memory.search(query, limit=10)
            memories.extend(results)

        elif memory_type == "working" and hasattr(self.session, 'working_memory'):
            context = self.session.working_memory.get_current_context()
            if context:
                memories.append({'type': 'working', 'content': context})

        elif memory_type == "library" and hasattr(self.session, 'library'):
            results = self.session.library.search(query, limit=5)
            memories.extend(results)

        # Calculate relevance scores
        for mem in memories:
            relevance_scores.append(mem.get('relevance', 0.5))

        return MemorySearchResult(
            memories=memories,
            total_found=len(memories),
            relevance_scores=relevance_scores,
            memory_types_covered=[memory_type],
            suggests_deeper_search=(len(memories) < 3),
            next_search_hints=[],
            search_metadata={'memory_type': memory_type, 'focus_level': focus_level}
        )

    def _merge_memories(
        self,
        all_memories: Dict[str, Any],
        new_result: MemorySearchResult
    ) -> None:
        """
        Merge new search results into accumulated memories.
        """
        for mem in new_result.memories:
            # Use memory ID as key, or generate one
            mem_id = mem.get('id', f"mem_{len(all_memories)}")
            if mem_id not in all_memories:
                all_memories[mem_id] = mem

    def _synthesize_context(
        self,
        all_memories: Dict[str, Any],
        query: str
    ) -> str:
        """
        Synthesize final context from accumulated memories.
        """
        if not all_memories:
            return "No relevant memories found."

        # Group memories by type
        by_type = {}
        for mem in all_memories.values():
            mem_type = mem.get('type', 'unknown')
            if mem_type not in by_type:
                by_type[mem_type] = []
            by_type[mem_type].append(mem)

        # Build context string
        context_parts = [f"Context for query: {query}\n"]

        for mem_type, memories in by_type.items():
            context_parts.append(f"\n{mem_type.title()} Memories ({len(memories)}):")
            for mem in memories[:5]:  # Limit per type
                content = str(mem.get('content', ''))[:200]
                context_parts.append(f"  - {content}...")

        return "\n".join(context_parts)

    def _summarize_memories(self, memories: Dict) -> str:
        """
        Create a summary of current memories for LLM reasoning.
        """
        if not memories:
            return "No memories retrieved yet."

        summary = []
        memory_types = {}

        for mem in memories.values():
            mem_type = mem.get('type', 'unknown')
            memory_types[mem_type] = memory_types.get(mem_type, 0) + 1

        for mem_type, count in memory_types.items():
            summary.append(f"- {count} {mem_type} memories")

        return "\n".join(summary)

    def _generate_search_hints(
        self,
        query: str,
        memories: List[Dict]
    ) -> List[str]:
        """
        Generate hints for next search based on current results.
        """
        hints = []

        # Analyze current memories for gaps
        memory_types = set(m.get('type', '') for m in memories)

        if 'episodic' not in memory_types:
            hints.append("Search episodic memory for past events")

        if 'semantic' not in memory_types:
            hints.append("Search semantic memory for knowledge")

        if len(memories) < 3:
            hints.append("Broaden search terms")

        return hints

    def _parse_llm_reasoning(
        self,
        llm_response: str,
        query: str,
        memories: Dict,
        focus_level: int
    ) -> ThoughtProcess:
        """
        Parse LLM response into structured ThoughtProcess.
        """
        response_lower = llm_response.lower()

        # Determine action from response
        if "sufficient" in response_lower or "enough context" in response_lower:
            action = "sufficient"
            quality = "sufficient"
        elif "search specific" in response_lower or "specific memory" in response_lower:
            action = "search_specific"
            quality = "partial"
        else:
            action = "increase_depth"
            quality = "partial" if len(memories) > 0 else "insufficient"

        # Extract memory type if searching specific
        memory_type = None
        if action == "search_specific":
            for mem_type in ['episodic', 'semantic', 'working', 'library', 'core']:
                if mem_type in response_lower:
                    memory_type = mem_type
                    break

        return ThoughtProcess(
            query=query,
            current_context_quality=quality,
            memories_examined=len(memories),
            focus_level=focus_level,
            reasoning=llm_response[:200],  # First 200 chars of reasoning
            action=action,
            memory_type=memory_type,
            search_query=query,
            confidence=0.7  # Default confidence from LLM
        )

    def get_exploration_summary(self) -> str:
        """
        Get a summary of the exploration process.
        """
        if not self.exploration_history:
            return "No exploration performed yet."

        summary = ["Memory Exploration Summary:"]

        for step in self.exploration_history:
            summary.append(
                f"  Step {step['iteration']}: {step['thought'].action} "
                f"(found {step['memories_found']} memories, "
                f"focus level {step['focus_level']})"
            )

        total_memories = self.exploration_history[-1]['total_memories'] if self.exploration_history else 0
        summary.append(f"\nTotal memories retrieved: {total_memories}")

        return "\n".join(summary)

    def reset_exploration(self):
        """
        Reset exploration history for new query.
        """
        self.exploration_history = []