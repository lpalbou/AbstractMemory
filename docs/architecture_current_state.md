# AbstractMemory - Current Architecture State

**Date:** 2025-09-29
**Status:** Post-Reorganization - Corrections Needed

---

## ✅ What's Been Completed

### Phase 1-3: Core Reorganization
1. **ReAct Loop Extracted** → `abstractmemory/reasoning/react_loop.py`
   - Standalone, ready for AbstractAgent
   - Zero TUI dependencies

2. **Duplicate Session Deleted** → `aa-tui/core/session.py` removed
   - Single source of truth: `abstractmemory.MemorySession`

3. **Enhanced Memory Operations**
   - `remember_fact(fact, category, confidence, metadata)` - categorized storage
   - `search_memory_for(query, category, user_id, since, until)` - hybrid search interface
   - `reconstruct_context(user_id, query, timestamp, location, mood, focus_level)` - situational memory
   - `get_observability_report()` - transparency (needs AbstractCore integration)

---

## 🏗️ Existing Architecture (Already Built)

### Storage Layer - **DUAL SYSTEM CONFIRMED**

**DualStorageManager** (`abstractmemory/storage/dual_manager.py`):
- **Mode: "dual"** → Writes to both, reads from LanceDB
- **Mode: "markdown"** → Human-readable, observable, version-controlled
- **Mode: "lancedb"** → SQL + vector search via AbstractCore embeddings
- **Mode: None** → No persistence (default)

**MarkdownStorage** (`abstractmemory/storage/markdown_storage.py`):
```
memory/
├── verbatim/{user}/{yyyy}/{mm}/{dd}/{HH}-{MM}-{SS}_{topic}.md
├── experiential/{yyyy}/{mm}/{dd}/{HH}-{MM}-{SS}_reflection.md
├── links/{yyyy}/{mm}/{dd}/{interaction_id}_to_{note_id}.json
├── core/{yyyy}-{mm}-{dd}_snapshot.md
├── semantic/facts_{yyyy}-{mm}.md
└── index.json
```

**LanceDBStorage** (`abstractmemory/storage/lancedb_storage.py`):
- Tables: `interactions`, `experiential_notes`, `links`, `memory_components`, `embedding_metadata`
- Vector search + SQL filtering (already implemented)
- Embedding consistency tracking

### Memory Tiers - **5 TIERS CONFIRMED**

1. **Core** - Identity, values, relationships
2. **Working** - Short-term conversation context
3. **Semantic** - Validated facts and concepts
4. **Episodic** - Historical events and interactions
5. **Document** (aka "Library") - Files, documents, content indexing
   - Location: `abstractmemory/components/document.py`
   - Features: Content chunking, semantic search, deduplication, access tracking
   - Already fully integrated with `get_document_summary()` exposed

---

## 🔧 What Needs Correction

### 1. Observability → Use AbstractCore Logging

**Current:** Custom tracking in `session.py` (lines 256-261):
```python
self.memory_access_log = []      # Custom logging
self.injection_history = []      # Custom logging
self.tool_execution_log = []     # Custom logging
self.facts_learned = 0           # Manual counter
self.searches_performed = 0      # Manual counter
```

**Should Be:** AbstractCore's logging system
```python
from abstractcore.logger import get_logger
logger = get_logger(__name__)

# Use structured logging
logger.info("remember_fact", extra={
    "category": category,
    "confidence": confidence,
    "user_id": user_id
})
```

**Action Required:**
- Remove custom tracking lists
- Replace with AbstractCore structured logging
- Keep `get_observability_report()` but source from AbstractCore logs

---

### 2. Serialization → Already Exists (Verify Integration)

**Already Built:**
- `DualStorageManager.save_memory_component(component_name, data)`
- `DualStorageManager.load_memory_component(component_name)`
- Writes to both markdown (human-readable) and LanceDB (queryable)

**MemorySession Integration:**
- Already has `self.memory.storage_manager` (DualStorageManager)
- Can already save/load via storage_manager

**Action Required:**
- ✅ Verify this works (likely already functional)
- Document the existing serialization API
- Consider adding convenience methods like `save_session_snapshot()` that wrap storage_manager

---

### 3. LanceDB Enhancement → Add Category/Temporal Support

**Current State:**
- `search_interactions()` already has semantic + SQL (lines 332-406)
- Schema has: `user_id`, `timestamp`, `metadata` (JSON)
- Missing: explicit `category` field, temporal helpers

**What to Add:**

1. **Schema Enhancement** (modify `_init_tables()` lines 68-77):
```python
interactions_schema = [
    {"name": "id", "type": "string"},
    {"name": "user_id", "type": "string"},
    {"name": "timestamp", "type": "timestamp"},
    {"name": "user_input", "type": "string"},
    {"name": "agent_response", "type": "string"},
    {"name": "topic", "type": "string"},
    {"name": "category", "type": "string"},        # NEW
    {"name": "confidence", "type": "float"},       # NEW
    {"name": "tags", "type": "string"},            # NEW (JSON array)
    {"name": "metadata", "type": "string"},
    {"name": "embedding", "type": "vector"}
]
```

2. **New Method: `hybrid_search()`**:
```python
def hybrid_search(self, semantic_query: str, sql_filters: Dict[str, Any],
                 since: Optional[datetime] = None,
                 until: Optional[datetime] = None,
                 limit: int = 10) -> List[Dict]:
    """
    Combine semantic similarity with SQL filtering.

    Example:
        hybrid_search("Python", {"category": "preference", "user_id": "alice"})
    """
```

3. **Helper Methods**:
```python
def search_by_category(self, category: str, user_id: Optional[str] = None, limit: int = 10)
def temporal_search(self, query: str, since: datetime, until: datetime, user_id: Optional[str] = None)
def get_user_timeline(self, user_id: str, since: Optional[datetime] = None, limit: int = 50)
```

---

## 📊 Memory Categories (8 Types)

Confirmed in `session.py` `remember_fact()` documentation:

1. **user_profile** - Facts about specific users
2. **preference** - User preferences and likes
3. **context** - Situational or environmental context
4. **knowledge** - General knowledge and facts
5. **event** - Specific events or occurrences
6. **people** - Information about other people mentioned
7. **document** - Facts extracted from documents (already covered by Document tier)
8. **conversation** - Facts from conversations

---

## 🎯 Next Actions (Priority Order)

### Immediate:
1. **Update `session.py` Observability**
   - Replace custom tracking with AbstractCore logging
   - Keep `get_observability_report()` but source from AbstractCore

2. **Enhance `lancedb_storage.py`**
   - Add `category`, `confidence`, `tags` fields to schema
   - Implement `hybrid_search(semantic_query, sql_filters, since, until)`
   - Add `search_by_category()`, `temporal_search()`, `get_user_timeline()`

3. **Document Existing Serialization**
   - Verify `save_memory_component()` / `load_memory_component()` work
   - Add convenience wrapper if needed

### Later:
4. **TUI Enhancement** (Phase 5)
   - Display observability data from AbstractCore logs
   - Show document library status
   - Real-time memory injection visibility

---

## 📦 Package References

- **AbstractCore Logging:** Check `/Users/albou/projects/abstractcore` for logger API
- **LanceDB Explorer:** `/Users/albou/projects/lancedb-explorer/backend` for advanced LanceDB patterns

---

## 🧪 Testing Strategy

1. Test `remember_fact()` with all 8 categories
2. Test `search_memory_for()` with category/temporal filters
3. Test `reconstruct_context()` with different focus levels
4. Test document library integration
5. Verify dual storage (markdown + LanceDB) consistency
6. Test serialization round-trip

---

## 🔑 Key Insight

> **The architecture is already 90% complete!**
> We have dual storage, document library, and LanceDB integration.
> We just need to:
> 1. Use AbstractCore's logging (not custom tracking)
> 2. Add category/temporal helpers to LanceDB
> 3. Document what already exists

---

## Questions for User

1. ✅ Confirmed: Use AbstractCore logging instead of custom tracking?
2. ✅ Confirmed: Dual storage (markdown + LanceDB) is correct approach?
3. ✅ Confirmed: Document memory tier (library) already covers "all documents AI ever read"?
4. Should I check `/Users/albou/projects/lancedb-explorer/backend` for LanceDB patterns to follow?