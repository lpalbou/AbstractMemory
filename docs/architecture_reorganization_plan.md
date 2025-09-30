# Architecture Reorganization Plan

## Current State Analysis

### Critical Issues Identified

1. **❌ DUPLICATE SESSION IN aa-tui/core/session.py**
   - This is wrong! AbstractMemory provides `MemorySession`
   - The TUI should NOT reimplement session logic
   - This violates the single responsibility principle

2. **🔀 REACT LOOP MIXED WITH TUI**
   - `react_loop.py` is in `aa-tui/` but belongs in AbstractAgent
   - ReAct reasoning is agent behavior, not UI concern
   - Needs to be extracted as standalone module

3. **📦 ABSTRACTMEMORY SESSION NOT FULLY UTILIZED**
   - `abstractmemory/session.py` has advanced capabilities:
     - Memory injection with MemoryConfig
     - Multi-tier memory (working, semantic, episodic, document, KG)
     - User context separation
     - Memory tools for agents
   - BUT: TUI and tests don't fully leverage these

4. **🔍 OBSERVABILITY GAPS**
   - Memory operations not fully observable
   - No clear way to see what memory was retrieved/injected
   - Missing serialization/deserialization for debugging

5. **💾 LANCEDB INTEGRATION INCOMPLETE**
   - LanceDB used for storage but not fully leveraged
   - SQL filtering capabilities (user, time, topic) underutilized
   - Semantic + SQL hybrid queries not fully implemented

## Architectural Vision

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACES                          │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  AbstractTUI     │  │ AbstractClient   │                │
│  │  (UI only)       │  │  (CLI/API)       │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
└───────────┼────────────────────┼──────────────────────────┘
            │                    │
            └────────┬───────────┘
                     │
┌────────────────────┼──────────────────────────────────────┐
│                    ▼                                       │
│              AbstractAgent                                 │
│  ┌────────────────────────────────────────────────┐       │
│  │  ReAct Loop (reasoning, planning, execution)   │       │
│  │  • Synthesis-first reasoning                   │       │
│  │  • Context management                          │       │
│  │  • Tool execution                              │       │
│  └───────────────────┬────────────────────────────┘       │
└────────────────────┼────────────────────────────────────┘
                     │
                     │ Uses
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   AbstractMemory                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  MemorySession (THE central session)                │    │
│  │  • Multi-tier memory (working, semantic, episodic)  │    │
│  │  • Context injection via MemoryConfig               │    │
│  │  • Memory tools (remember, search, reconstruct)     │    │
│  │  • Full observability (last_memory_items)           │    │
│  │  • Serialization/deserialization                    │    │
│  └─────────────────────┬───────────────────────────────┘    │
│                        │                                     │
│  ┌─────────────────────┴───────────────────────────────┐    │
│  │  Storage Layer (LanceDB + Markdown)                 │    │
│  │  • Semantic search (embeddings)                     │    │
│  │  • SQL filtering (user, time, topic)                │    │
│  │  • Hybrid queries                                   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Reorganization Strategy

### Phase 1: Extract ReAct Loop (Prepare for AbstractAgent)

**Goal:** Make `react_loop.py` standalone and independent of TUI

**Actions:**
1. Move `react_loop.py` → `abstractmemory/reasoning/react_loop.py` (temporary)
2. Remove TUI-specific dependencies
3. Make it work purely with MemorySession
4. Add proper observability hooks
5. Document for future move to AbstractAgent

**Why temporary location?**
- AbstractAgent doesn't exist yet as a package
- Keeping in AbstractMemory for now allows continued development
- Clear path to extract when AbstractAgent is created

---

### Phase 2: Delete Duplicate Session

**Goal:** Remove `aa-tui/core/session.py` completely

**Actions:**
1. Delete `aa-tui/core/session.py`
2. Update all imports to use `abstractmemory.MemorySession`
3. Ensure TUI uses MemorySession directly
4. Remove any session-related logic from TUI core

**Rationale:**
- TUI should be a VIEW layer only
- All session logic belongs in AbstractMemory
- One source of truth for session behavior

---

### Phase 3: Strengthen MemorySession

**Goal:** Make MemorySession the complete, observable, serializable session

**3.1 Enhanced Memory Operations**

Add these methods to MemorySession:

```python
def remember_fact(self, fact: str, category: str = "general",
                 user_id: Optional[str] = None, confidence: float = 1.0):
    """
    Remember a fact with categorization.

    Categories: 'user_profile', 'preference', 'context', 'knowledge', 'event'
    """

def search_memory_for(self, query: str,
                     category: Optional[str] = None,
                     user_id: Optional[str] = None,
                     since: Optional[datetime] = None,
                     until: Optional[datetime] = None) -> List[MemoryItem]:
    """
    Search memory with SQL+semantic hybrid queries.

    Examples:
    - search_memory_for("Python", category="preference", user_id="alice")
    - search_memory_for("error", since=yesterday)
    - search_memory_for("John", category="people")
    """

def reconstruct_context(self, user_id: str, query: str,
                       timestamp: Optional[datetime] = None,
                       location: Optional[str] = None,
                       mood: Optional[str] = None) -> Dict[str, Any]:
    """
    Reconstruct full context based on situational parameters.

    Returns:
    {
        'user_profile': {...},
        'relevant_memories': [...],
        'recent_interactions': [...],
        'temporal_context': {...},
        'spatial_context': {...} if location,
        'emotional_context': {...} if mood
    }
    """
```

**3.2 Full Observability**

Enhance tracking in MemorySession:

```python
class MemorySession:
    def __init__(self, ...):
        # ... existing code ...

        # Observability tracking
        self.memory_access_log = []  # Log of all memory retrievals
        self.injection_history = []  # History of context injections
        self.tool_execution_log = []  # Tool usage tracking

    def get_observability_report(self) -> Dict[str, Any]:
        """
        Get complete observability report.

        Returns:
        {
            'last_generation': {
                'memory_items_injected': [...],
                'tokens_added': 1234,
                'retrieval_time_ms': 45,
                'sources': ['working', 'semantic', 'document']
            },
            'session_stats': {
                'total_interactions': 42,
                'memory_retrievals': 156,
                'facts_learned': 23,
                'documents_indexed': 5
            },
            'memory_state': {
                'working': {'items': 10, 'tokens': 450},
                'semantic': {'facts': 23, 'confidence_avg': 0.87},
                'episodic': {'episodes': 5},
                'document': {'chunks': 45, 'files': 5}
            }
        }
        """
```

**3.3 Serialization/Deserialization**

```python
def save_session_snapshot(self, filepath: str):
    """
    Save complete session state including:
    - Conversation history
    - Memory state (all tiers)
    - User profiles
    - Observability data
    """

def load_session_snapshot(self, filepath: str):
    """
    Restore complete session from snapshot.
    """

def export_memory_to_lancedb(self, table_name: str):
    """
    Export all memory to LanceDB for analysis.
    """
```

---

### Phase 4: Strengthen LanceDB Integration

**Goal:** Fully leverage LanceDB for semantic + SQL hybrid queries

**4.1 Enhanced Storage Manager**

Update `abstractmemory/storage/lancedb_storage.py`:

```python
class LanceDBStorage:
    def hybrid_search(self,
                     semantic_query: str,
                     sql_filters: Optional[Dict[str, Any]] = None,
                     limit: int = 10) -> List[Dict]:
        """
        Perform hybrid semantic + SQL search.

        Examples:
        - hybrid_search("Python", sql_filters={'user_id': 'alice', 'category': 'preference'})
        - hybrid_search("error", sql_filters={'timestamp': {'$gte': yesterday}})
        - hybrid_search("John", sql_filters={'category': 'people', 'confidence': {'$gte': 0.8}})
        """

    def search_by_category(self, category: str,
                          user_id: Optional[str] = None,
                          limit: int = 10) -> List[Dict]:
        """
        Search within a specific memory category.

        Categories: 'user_profile', 'preference', 'context', 'knowledge',
                   'event', 'document', 'conversation'
        """

    def temporal_search(self, query: str,
                       since: Optional[datetime] = None,
                       until: Optional[datetime] = None,
                       user_id: Optional[str] = None) -> List[Dict]:
        """
        Search with temporal constraints.
        """

    def get_user_timeline(self, user_id: str,
                         since: Optional[datetime] = None) -> List[Dict]:
        """
        Get complete timeline of interactions for a user.
        """
```

**4.2 Schema Enhancement**

Ensure LanceDB tables have proper schema:

```python
MEMORY_SCHEMA = {
    'id': 'str',
    'content': 'str',
    'embedding': 'vector(384)',  # or 768 depending on model
    'user_id': 'str',
    'category': 'str',  # NEW: memory category
    'timestamp': 'datetime',
    'confidence': 'float',
    'metadata': 'json',
    'source_type': 'str',  # working, semantic, episodic, document
    'tags': 'list<str>',  # NEW: for flexible categorization
}
```

---

### Phase 5: Update TUI to Use Pure MemorySession

**Goal:** Make TUI a pure VIEW layer that uses MemorySession

**Actions:**

1. **enhanced_tui.py becomes display-only:**
   - Remove all session logic
   - Import and use MemorySession directly
   - Display observability data from session
   - No business logic in TUI

2. **Example structure:**

```python
# aa-tui/enhanced_tui.py

from abstractmemory import MemorySession, MemoryConfig
from abstractmemory.reasoning import ReactLoop, ReactConfig  # Future: from abstractagent

class EnhancedTUI:
    def __init__(self, ...):
        # Create the ONE session
        self.session = MemorySession(
            provider=provider,
            memory_config=memory_config,
            default_memory_config=MemoryConfig.agent_mode(),
            tools=tools
        )

        # ReAct loop uses session
        self.react_loop = ReactLoop(self.session, ReactConfig(...))

    def _process_agent_response(self, user_input: str):
        """Process through ReAct loop and display results."""
        response = await self.react_loop.process_query(user_input, callbacks={
            'on_observation': self._display_observation,
            'on_action': self._display_action,
            ...
        })

        # Display observability
        obs_report = self.session.get_observability_report()
        self._update_observability_panel(obs_report)
```

---

## Implementation Order

### ✅ Week 1: Foundation
1. Extract ReAct loop to `abstractmemory/reasoning/`
2. Delete duplicate session
3. Update TUI imports

### ✅ Week 2: Memory Enhancement
4. Add remember_fact, search_memory_for, reconstruct_context
5. Implement full observability
6. Add serialization

### ✅ Week 3: LanceDB Enhancement
7. Implement hybrid search
8. Add category-based search
9. Implement temporal search

### ✅ Week 4: TUI Update & Testing
10. Refactor TUI to pure view layer
11. Add observability displays
12. Comprehensive testing

---

## Validation Criteria

### ✅ Success Metrics

1. **Single Source of Truth:**
   - Only `abstractmemory.MemorySession` exists
   - No duplicate session implementations

2. **Clear Boundaries:**
   - ReAct loop in reasoning module (ready for AbstractAgent)
   - TUI is pure display
   - MemorySession handles all memory logic

3. **Full Observability:**
   - Can see what memory was injected
   - Can track all memory operations
   - Can serialize/deserialize complete state

4. **LanceDB Power:**
   - Semantic + SQL hybrid queries working
   - Category-based searches
   - Temporal queries
   - User timeline reconstruction

5. **Memory Capabilities:**
   - remember_fact(category, confidence)
   - search_memory_for(category, user, time)
   - reconstruct_context(user, query, time, location)

---

## Migration Notes

### For Future AbstractAgent Package

When creating AbstractAgent:

```python
# Future: abstractagent/reasoning/react_loop.py
# Copy from: abstractmemory/reasoning/react_loop.py

# Dependencies:
# - Must work with any session providing generate() method
# - Should not depend on AbstractMemory internals
# - Pure reasoning logic
```

### For Future AbstractClient/AbstractTUI

```python
# Future: abstractclient/tui/enhanced_tui.py
# OR: abstracttui/enhanced_tui.py

# Dependencies:
# - AbstractMemory (MemorySession)
# - AbstractAgent (ReAct loop)
# - No business logic, pure display
```

---

## Questions for Validation

1. **LanceDB Strategy:** ✅ CORRECT ROUTE
   - Semantic search + SQL filtering is the right approach
   - Enables complex queries: "What did Alice say about Python yesterday?"
   - Hybrid queries are powerful and necessary

2. **Category System:**
   - Proposed: user_profile, preference, context, knowledge, event, document, conversation
   - Should we add more? Remove any?

3. **Observability Depth:**
   - How much detail needed in observability reports?
   - Real-time streaming or post-interaction?

4. **Serialization Format:**
   - JSON for human readability?
   - Binary for efficiency?
   - Both?

---

## Next Steps

**IMMEDIATE:**
1. Get your approval on this plan
2. Answer validation questions
3. Begin Phase 1: Extract ReAct loop

**THIS WEEK:**
- Complete Phases 1-2 (extraction + deletion)
- Begin Phase 3 (MemorySession enhancement)

**BLOCKERS:**
- None identified yet
- Will surface during implementation

---

## Summary

This reorganization will:
- ✅ Establish MemorySession as THE session
- ✅ Prepare ReAct for AbstractAgent extraction
- ✅ Make TUI a pure view layer
- ✅ Enable full observability
- ✅ Leverage LanceDB fully
- ✅ Create clear architectural boundaries

**Key Principle:** AbstractMemory is the brain, ReAct is the reasoning process, TUI is the eyes and voice.