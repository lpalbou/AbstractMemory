# Detailed Actionable Plan for AbstractMemory Improvements

## Core Insight
The 9 memory types are **cognitively correct** - they mirror human memory architecture. The issue isn't complexity but **implementation efficiency** and **lack of progressive exploration**.

## Memory Types (Keep All 9)
Each serves a distinct cognitive function:
1. **Core** - Identity foundation (values, purpose, personality)
2. **Working** - Active cognition (current tasks, unresolved questions)
3. **Episodic** - Temporal experiences (events, moments, discoveries)
4. **Semantic** - Conceptual knowledge (insights, rules, patterns)
5. **People** - Social cognition (relationships, preferences)
6. **Library** - Subconscious repository (absorbed knowledge)
7. **Notes** - Experiential stream (ongoing reflections)
8. **Verbatim** - Factual record (exact interactions)
9. **Links** - Associative network (memory connections)

## Problem Analysis

### Current Issues
1. **No ReAct Loop** - Single-shot retrieval instead of progressive exploration
2. **Monolithic session.py** - 2600+ lines mixing concerns
3. **String-based Tools** - No structured feedback for iteration
4. **Multiple LLM Calls** - Retrieval plan → Synthesis → Response (3x latency)
5. **Missing REPL Commands** - No progressive exploration commands

### What's Working Well
- Cognitive memory architecture is sound
- LanceDB indexing works
- File attachment capture works
- Memory tools are registered correctly

## Implementation Plan

### Phase 1: Add ReAct Memory Agent (Week 1)
**Goal**: Enable progressive memory exploration without changing existing structure

#### 1.1 Create `abstractmemory/agents/react_memory_agent.py`
```python
class ReactMemoryAgent:
    """
    ReAct agent for progressive memory exploration.
    Works alongside existing MemorySession, not replacing it.
    """

    def __init__(self, session: MemorySession):
        self.session = session
        self.exploration_history = []

    def explore_progressively(self, query: str, max_iterations: int = 5):
        """
        Progressive memory diving with ReAct loop.

        1. Start with minimal context (focus_level=0)
        2. Observe retrieved memories
        3. Reason: Do I need more context?
        4. Act: Increase focus_level or search different memory type
        5. Repeat until sufficient context
        """

        focus_level = 0
        all_memories = {}
        iteration = 0

        while iteration < max_iterations:
            # Think
            thought = self._think_about_context(query, all_memories, focus_level)

            if thought.sufficient_context:
                break

            # Act
            if thought.action == "increase_depth":
                focus_level = min(focus_level + 1, 5)
                new_memories = self._search_at_level(query, focus_level)
            elif thought.action == "search_specific":
                new_memories = self._search_memory_type(
                    query,
                    thought.memory_type,
                    thought.search_query
                )

            # Observe
            all_memories.update(new_memories)
            self.exploration_history.append({
                'iteration': iteration,
                'thought': thought,
                'memories_found': len(new_memories),
                'total_memories': len(all_memories)
            })

            iteration += 1

        return self._synthesize_context(all_memories, query)
```

#### 1.2 Add Structured Memory Search Results
```python
@dataclass
class MemorySearchResult:
    """Structured result for memory searches."""
    memories: List[Dict]
    total_found: int
    relevance_scores: List[float]
    memory_types_covered: List[str]
    suggests_deeper_search: bool
    next_search_hints: List[str]
```

### Phase 2: Refactor Tools for Structured Feedback (Week 1)
**Goal**: Make tools return structured data that AI can reason about

#### 2.1 Update `abstractmemory/tools.py`
```python
def search_memories_structured(query: str, memory_type: Optional[str] = None,
                               focus_level: int = 1) -> Dict:
    """
    Returns structured data instead of formatted string.

    Returns:
        {
            "memories": [...],
            "metadata": {
                "total_found": 10,
                "types_searched": ["semantic", "episodic"],
                "average_relevance": 0.75,
                "suggests_deeper": True,
                "next_queries": ["related_concept", "earlier_discussion"]
            }
        }
    """
```

#### 2.2 Add Progressive Search Tool
```python
def search_incrementally(query: str, previous_depth: int = 0) -> Dict:
    """
    Search with awareness of previous results.

    Returns:
        {
            "new_memories": [...],  # Not seen at previous depth
            "total_available": 50,   # How many more exist
            "search_quality": "good", # good/poor/exhausted
            "suggested_action": "go_deeper"  # go_deeper/sufficient/too_broad
        }
    """
```

### Phase 3: Optimize LLM Calls (Week 2)
**Goal**: Reduce to single LLM call with iterative memory retrieval

#### 3.1 Create `abstractmemory/context/stream_context_builder.py`
```python
class StreamContextBuilder:
    """
    Builds context incrementally in a single LLM conversation.
    """

    def build_with_react(self, query: str, llm_provider) -> str:
        """
        Single LLM call that can request more memories as needed.

        Prompt includes:
        - Initial shallow memories
        - Tools to request more
        - Instruction to explore progressively
        """

        prompt = f"""
        Query: {query}

        Initial context (shallow):
        {self.get_shallow_context(query)}

        You can use these tools to explore deeper:
        - search_deeper(memory_type, query)
        - get_memory_stats()
        - link_memories(id1, id2)

        Progressively build context, then answer.
        """

        # Single LLM call handles entire exploration
        return llm_provider.generate_with_tools(prompt)
```

### Phase 4: Clean Architecture Without Breaking Changes (Week 2)
**Goal**: Modularize session.py while maintaining backward compatibility

#### 4.1 Extract Concerns from Session.py
```python
# Keep session.py as facade, extract internals to:
abstractmemory/
    core/
        memory_operations.py  # remember_fact, search, etc.
        context_operations.py # reconstruct_context logic
        consolidation.py      # trigger_consolidation logic
        reflection.py         # reflect_on logic

    session.py  # Thin facade that delegates to modules
```

#### 4.2 Create MemoryOrchestrator
```python
class MemoryOrchestrator:
    """
    Coordinates between different memory subsystems.
    Extracted from MemorySession for cleaner separation.
    """

    def __init__(self, memory_managers: Dict):
        self.managers = memory_managers  # working, episodic, semantic, etc.

    def coordinate_retrieval(self, query: str, strategy: str = "balanced"):
        """
        Coordinates retrieval across all memory types.
        """
        if strategy == "balanced":
            return self._balanced_retrieval(query)
        elif strategy == "focused":
            return self._focused_retrieval(query)
        elif strategy == "exhaustive":
            return self._exhaustive_retrieval(query)
```

### Phase 5: Enhanced REPL Commands (Week 3)
**Goal**: Add commands for progressive exploration and memory management

#### 5.1 Add Progressive Exploration Commands
```python
# In repl.py handle_command()

elif command == "/dive":
    """Progressive memory exploration with ReAct."""
    agent = ReactMemoryAgent(session)
    result = agent.explore_progressively(args)

    # Show exploration trace
    print("Memory Exploration Trace:")
    for step in agent.exploration_history:
        print(f"  Step {step['iteration']}: {step['thought'].action}")
        print(f"    Found: {step['memories_found']} new memories")

    print(f"\nFinal Context: {result}")

elif command == "/focus":
    """Set default focus level."""
    session.default_focus_level = int(args)
    print(f"Default focus level set to {args}")

elif command == "/trace":
    """Show last memory retrieval reasoning."""
    if hasattr(session, 'last_retrieval_trace'):
        print(session.last_retrieval_trace)
```

#### 5.2 Add Memory Management Commands
```python
elif command == "/memory-stats":
    """Show memory distribution and patterns."""
    stats = session.get_memory_statistics()
    print(f"Memory Distribution:")
    for memory_type, count in stats['distribution'].items():
        print(f"  {memory_type}: {count} items")

elif command == "/link":
    """Create association between memories."""
    mem1, mem2 = args.split()
    session.link_memories(mem1, mem2, relationship="related")
    print(f"Linked {mem1} ↔ {mem2}")

elif command == "/forget":
    """De-emphasize a memory."""
    session.deprioritize_memory(args, reason="user_request")
    print(f"De-emphasized memory: {args}")
```

### Phase 6: Performance Optimizations (Week 3)
**Goal**: Speed up memory operations without changing functionality

#### 6.1 Implement Caching Layer
```python
class MemoryCache:
    """
    LRU cache for frequently accessed memories and retrieval plans.
    """

    @lru_cache(maxsize=1000)
    def get_retrieval_plan(self, query_hash: str, focus_level: int):
        """Cache retrieval plans for common queries."""
        pass

    @lru_cache(maxsize=5000)
    def get_memory_by_id(self, memory_id: str):
        """Cache individual memories."""
        pass
```

#### 6.2 Parallel Memory Type Search
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class ParallelMemorySearch:
    """
    Search all memory types in parallel for speed.
    """

    async def search_all_types(self, query: str):
        """Search all 9 memory types concurrently."""

        tasks = [
            self.search_core(query),
            self.search_working(query),
            self.search_episodic(query),
            self.search_semantic(query),
            self.search_people(query),
            self.search_library(query),
            self.search_notes(query),
            self.search_verbatim(query),
            self.search_links(query)
        ]

        results = await asyncio.gather(*tasks)
        return self.merge_results(results)
```

## Implementation Order

### Week 1: Core Improvements
1. ✅ Create ReactMemoryAgent for progressive exploration
2. ✅ Add structured return types to tools
3. ✅ Implement search_incrementally tool
4. ✅ Test ReAct loop with existing memory types

### Week 2: Architecture & Optimization
1. ✅ Create StreamContextBuilder for single LLM call
2. ✅ Extract modules from session.py (keep backward compatibility)
3. ✅ Implement MemoryOrchestrator
4. ✅ Add caching layer

### Week 3: REPL & Polish
1. ✅ Add /dive command for progressive exploration
2. ✅ Add /focus, /trace, /memory-stats commands
3. ✅ Implement parallel memory search
4. ✅ Add /link and /forget commands
5. ✅ Complete testing and documentation

## Success Metrics

### Performance
- ⬇️ 50% reduction in latency (from single LLM call)
- ⬇️ 70% reduction in redundant memory retrievals (from caching)
- ⬆️ 3x faster multi-type search (from parallel execution)

### Functionality
- ✅ Progressive memory exploration working
- ✅ All 9 memory types preserved and accessible
- ✅ Structured tool feedback enabling iteration
- ✅ REPL commands for memory management

### Code Quality
- ⬇️ Session.py reduced from 2600 to <500 lines
- ✅ Each module independently testable
- ✅ Backward compatibility maintained
- ✅ Clear separation of concerns

## Key Design Decisions

### Keep What Works
- All 9 memory types (cognitively correct)
- LanceDB indexing system
- File attachment capture
- Tool registration with AbstractCore

### Fix What's Broken
- Add ReAct loop for progressive exploration
- Return structured data from tools
- Single LLM call instead of multiple
- Modularize monolithic code

### Enhance What's Missing
- Progressive exploration commands
- Memory management commands
- Caching for performance
- Parallel search capabilities

## Testing Strategy

### Unit Tests
- Test each memory type independently
- Test ReAct agent iterations
- Test structured tool returns
- Test caching behavior

### Integration Tests
- Test progressive exploration end-to-end
- Test all REPL commands
- Test backward compatibility
- Test parallel search

### Performance Tests
- Measure latency reduction
- Measure cache hit rates
- Measure parallel vs sequential search
- Measure memory usage

## Risk Mitigation

### Backward Compatibility
- Keep MemorySession interface unchanged
- Add new features alongside existing ones
- Use feature flags for experimental features
- Comprehensive test coverage

### Performance Risks
- Profile before optimizing
- Add metrics collection
- Use caching judiciously
- Monitor memory usage

### Complexity Risks
- Keep modules focused (single responsibility)
- Document cognitive purpose of each memory type
- Provide clear examples
- Maintain clean interfaces

## Conclusion

This plan preserves the sophisticated 9-type memory architecture while fixing the real issues:
1. Lack of progressive exploration (solved with ReAct)
2. Monolithic code (solved with modularization)
3. Inefficient LLM calls (solved with streaming)
4. Missing REPL commands (solved with new commands)

The result will be a clean, efficient implementation that gives the AI true agency over its rich memory system.