# Next Steps Implementation Plan

**Date**: 2025-09-30
**Status**: Phase 1 Partially Complete - Adding Missing Memory Tools
**Source**: Based on `2025-09-30-critical-refactor-implementation1.txt`
**Last Updated**: 2025-09-30 (Session 2)

---

## 📊 **Current Session Status (Session 4)**

**Working On**: LanceDB Integration + Memory Tools Implementation
**Progress**: 4/6 tools complete (67%)
**Completed This Session**:
- ✅ LanceDB storage layer with AbstractCore embeddings (all-minilm-l6-v2)
- ✅ remember_fact() - Dual storage (filesystem + LanceDB)
- ✅ search_memories() - Hybrid search (semantic + SQL filters)
- ✅ create_memory_link() - Dual storage with bidirectional links
- ✅ search_library() - Subconscious document search
- ✅ All tests passing (5/5) with real Ollama qwen3-coder:30b
**Next**: reflect_on(), full 9-step reconstruct_context()

---

## ✅ What's Complete (Phase 1)

### Core Architecture
- [x] MemorySession inherits from AbstractCore.BasicSession
- [x] Integration with Ollama qwen3-coder:30b
- [x] Integration with AbstractCore all-minilm-l6-v2 embeddings
- [x] StructuredResponseHandler for parsing LLM responses
- [x] Dual storage (filesystem): verbatim + notes
- [x] 10 core memory components framework
- [x] Tests passing (4/4) with real LLM - NO MOCKING

---

## ✅ What's Complete (Session 2 Update)

### Memory Tools Framework - All 6 Exist

According to `2025-09-30-critical-refactor-implementation1.txt` lines 48-54:

```
Memory Tools (LLM Agency)
├─ remember_fact(content, importance, emotion, links_to)
├─ reconstruct_context(user, query, focus_level) → rich context
├─ search_memories(query, filters, limit)
├─ search_library(query) → search subconscious ← NEW
├─ create_memory_link(from_id, to_id, relationship)
└─ reflect_on(topic) → triggers deep reflection
```

---

## 🔄 Session 4 Update - Implementation Progress

**Current Status** (2025-09-30 Session 4):
1. ✅ `remember_fact()` - **FULLY IMPLEMENTED**
   - Creates memory files in notes/ with metadata
   - Calculates emotional resonance (importance × alignment)
   - Creates links to related memories if specified
   - **Stores in LanceDB with embeddings** ✅
   - Returns unique memory_id
   - **Tests passing ✅**

2. ✅ `search_memories()` - **FULLY IMPLEMENTED**
   - **LanceDB hybrid search (semantic + SQL)** ✅
   - Filters: user_id, category, min_importance, emotion_valence
   - Temporal filters: since, until
   - Fallback to filesystem text search
   - **Tests passing ✅**

3. ⚠️ `reconstruct_context()` - Skeleton exists - 9-step implementation TODO

4. ✅ `search_library()` - **FULLY IMPLEMENTED**
   - Filesystem document search
   - Access count tracking
   - LanceDB semantic search integration
   - **Tests passing ✅**

5. ✅ `create_memory_link()` - **FULLY IMPLEMENTED**
   - Creates links in links/{yyyy}/{mm}/{dd}/
   - **Stores in LanceDB links_table** ✅
   - Bidirectional link support
   - **Tests passing ✅**

6. ⚠️ `reflect_on()` - Skeleton exists - Full implementation TODO

**Implementation Count**: 4/6 complete (67%)

---

## 📋 Implementation Priorities

### Priority 1: Complete Memory Tools (Week 1-2)

#### Task 1.1: Implement `remember_fact()` (lines 2952-2970)
**Reference**: `2025-09-30-critical-refactor-implementation1.txt` lines 2952-2970

```python
def remember_fact(content: str, importance: float, emotion: str, links_to: List[str] = None):
    """
    LLM calls this to remember something important.

    Args:
        content: What to remember
        importance: 0.0-1.0 (how significant)
        emotion: curiosity/excitement/concern/etc
        links_to: Optional list of memory IDs to link to

    Returns:
        memory_id of created note
    """
    # 1. Create unique memory_id
    # 2. Calculate emotional_resonance (importance × alignment_with_values)
    # 3. Store in notes/ with rich metadata
    # 4. Store in LanceDB with embedding
    # 5. Create links if links_to provided
    # 6. Update core memory if highly important
```

**Requirements**:
- Store in `notes/` filesystem
- Store in LanceDB `notes_table` with embedding
- Rich metadata: user, time, location, importance, emotion
- Create memory links if `links_to` provided
- Return unique `memory_id`

#### Task 1.2: Rename + Implement `search_memories()` (lines 2973-2984)
**Reference**: `2025-09-30-critical-refactor-implementation1.txt` lines 2973-2984

```python
def search_memories(query: str, filters: Dict = None, limit: int = 10):
    """
    LLM calls this to search existing memories.

    Args:
        query: Semantic search query
        filters: Optional {category, user_id, since, until, min_confidence}
        limit: Max results

    Returns:
        List of matching memories with metadata
    """
    # 1. Use LanceDB hybrid search (semantic + SQL)
    # 2. Apply filters (category, user_id, temporal, confidence)
    # 3. Weight by emotional resonance
    # 4. Return sorted by relevance
```

**Requirements**:
- LanceDB hybrid search (semantic + SQL filters)
- Support filters: category, user_id, since, until, min_confidence
- Weight results by emotional_resonance
- Return list with metadata

#### Task 1.3: Implement Full `reconstruct_context()` (lines 2461-2542)
**Reference**: `2025-09-30-critical-refactor-implementation1.txt` lines 2461-2542

**9-Step Process**:
```python
def reconstruct_context(user_id, query, location, focus_level):
    # 1. Semantic search in notes + verbatim (base)
    base = semantic_search(query)

    # 2. Explore links via concepts_graph.json (expand)
    linked = explore_links(base, depth=focus_level)

    # 3. Search Library (subconscious) ← NEW
    library_results = search_library(query)

    # 4. Filter by emotional resonance (refine)
    emotional = filter_by_emotion(linked + library_results)

    # 5. Add temporal context
    temporal = add_temporal_context(time)

    # 6. Add spatial context
    spatial = add_spatial_context(location)

    # 7. Add user profile & relationship
    user_ctx = get_user_context(user_id)

    # 8. Add ALL 10 core memory components
    core_ctx = get_all_core_memory()

    # 9. Synthesize into rich context
    return synthesize(emotional + temporal + spatial + user_ctx + core_ctx)
```

**Requirements**:
- Semantic search (LanceDB)
- Link exploration (concepts_graph.json)
- Library search integration
- Emotional filtering
- Temporal + spatial context
- User profile integration
- All 10 core components included

#### Task 1.4: Create `search_library()` (NEW)
**Reference**: `2025-09-30-critical-refactor-implementation1.txt` lines 1937, 2276-2281, 2452-2454

```python
def search_library(query: str) -> List[Dict]:
    """
    Search Library (subconscious memory) for documents AI has read.

    Args:
        query: Semantic search query

    Returns:
        List of relevant documents with excerpts
    """
    # 1. Search LanceDB library_table
    # 2. Return relevant documents
    # 3. Include key excerpts
    # 4. Increment access_count
    # 5. Update last_accessed timestamp
```

**Requirements**:
- Search `library/documents/{doc_hash}/`
- LanceDB `library_table` search
- Increment `access_count` on access
- Update `last_accessed` timestamp
- Return excerpts, not full documents

#### Task 1.5: Create `create_memory_link()` (lines 2988-2998)
**Reference**: `2025-09-30-critical-refactor-implementation1.txt` lines 2988-2998

```python
def create_memory_link(from_id: str, to_id: str, relationship: str):
    """
    LLM calls this to create association between memories.

    Args:
        from_id: Source memory ID
        to_id: Target memory ID
        relationship: Type (elaborates_on, contradicts, relates_to, etc)

    Returns:
        link_id of created link
    """
    # 1. Validate both memory IDs exist
    # 2. Create link in links/ filesystem
    # 3. Store in LanceDB links_table
    # 4. Return link_id
```

**Requirements**:
- Validate memory IDs exist
- Store in `links/{yyyy}/{mm}/{dd}/{from_id}_to_{to_id}.json`
- Store in LanceDB `links_table`
- Support relationship types: elaborates_on, contradicts, relates_to, caused_by, etc

#### Task 1.6: Create `reflect_on()` (lines 1939, 2990-3010)
**Reference**: `2025-09-30-critical-refactor-implementation1.txt` lines 2990-3010

```python
def reflect_on(topic: str) -> str:
    """
    LLM calls this to trigger deep reflection on a topic.

    Args:
        topic: What to reflect on

    Returns:
        reflection_id of created reflection note
    """
    # 1. Search memories related to topic
    # 2. Reconstruct context around topic
    # 3. Create special "reflection" note type
    # 4. Higher importance (0.8+)
    # 5. Store in notes/ with category="reflection"
```

**Requirements**:
- Search related memories
- Trigger context reconstruction
- Create reflection note (category="reflection")
- Higher default importance (0.8+)
- Store in notes/ + LanceDB

---

### Priority 2: Emotional Resonance System (Week 2)

**Reference**: `2025-09-30-critical-refactor-implementation1.txt` lines 3070-3141

#### Task 2.1: Implement Emotional Resonance Calculation
```python
def calculate_emotional_resonance(importance: float, alignment_with_values: float) -> Dict:
    """
    emotion_intensity = importance × alignment_with_values
    """
    intensity = importance * alignment_with_values
    valence = "positive" if alignment_with_values > 0 else "negative"

    return {
        "intensity": intensity,
        "valence": valence,
        "reason": "..." # LLM provides this
    }
```

#### Task 2.2: Integrate Emotions into Memory
- Boost emotionally resonant memories in search
- Use for temporal anchoring (high intensity = episodic marker)
- Include emotional context in `reconstruct_context()`
- Track in `core/emotional_significance.md`

---

### Priority 3: Library Memory System (Week 3)

**Reference**: `2025-09-30-critical-refactor-implementation1.txt` lines 1596-1663, 2423-2434

#### Task 3.1: Auto-Capture Files Read
```python
def capture_to_library(file_path: str, content: str):
    """
    Auto-capture when AI reads a file.
    """
    # 1. Calculate doc_hash (unique ID)
    # 2. Store content in library/documents/{hash}/content.md
    # 3. Create metadata.json
    # 4. Extract key excerpts
    # 5. Generate embedding
    # 6. Store in LanceDB library_table
```

#### Task 3.2: Library LanceDB Schema
```python
library_table:
    - doc_id (hash)
    - source_path, source_url
    - content_type (code, markdown, pdf)
    - first_accessed, last_accessed, access_count
    - importance_score (calculated from access + emotion)
    - tags, topics
    - embedding (semantic vector)
    - metadata (JSON)
```

---

### Priority 4: LanceDB Integration (Week 3-4)

**Reference**: Multiple sections in critical refactor document

#### Task 4.1: Create LanceDB Tables
```python
# 1. interactions_table (verbatim)
# 2. notes_table (experiential)
# 3. links_table (memory associations)
# 4. core_memory_table (10 components)
# 5. library_table (documents)
```

#### Task 4.2: Rich Metadata Schema
All tables need:
- user, timestamp, location
- emotion_valence, emotion_intensity
- importance, confidence
- memory_type, category
- tags, linked_memory_ids
- embedding (384-dim vector from all-minilm-l6-v2)

---

### Priority 5: Core Memory Extraction (Week 4)

**Reference**: `2025-09-30-critical-refactor-implementation1.txt` lines 3143-3244, 2527-2542

#### Task 5.1: Extract from Experiential Notes
```python
# Daily/weekly consolidation:
# 1. Analyze experiential notes
# 2. Extract patterns for each of 10 components:
#    - purpose.md (from "why" reflections)
#    - personality.md (from communication patterns)
#    - values.md (from emotional responses)
#    - self_model.md (from capability assessments)
#    - relationships.md (from user interactions)
#    - awareness_development.md (from meta-reflections)
#    - capabilities.md (from successes)
#    - limitations.md (from challenges - temporal "yet")
#    - emotional_significance.md (from high-emotion moments)
#    - authentic_voice.md (from voice preferences)
```

---

## 🔧 Implementation Strategy

### Step 1: Extend MemorySession with Missing Methods
1. Add 3 missing methods to `abstractmemory/session.py`:
   - `search_library()`
   - `create_memory_link()`
   - `reflect_on()`
2. Rename `search_memory()` → `search_memories()`

### Step 2: Implement Full Logic for All 6 Tools
1. Start with `remember_fact()` (most critical)
2. Then `search_memories()` (needed by reconstruct)
3. Then `reconstruct_context()` (9-step process)
4. Then supporting tools: `search_library()`, `create_memory_link()`, `reflect_on()`

### Step 3: Add LanceDB Storage
1. Create `abstractmemory/storage/lancedb_storage.py`
2. Implement 5 tables with rich metadata
3. Integrate with memory tools

### Step 4: Implement Emotional Resonance
1. Add calculation function
2. Integrate into `remember_fact()`
3. Use for memory ranking
4. Track in `core/emotional_significance.md`

### Step 5: Create Library System
1. Auto-capture file reads
2. Create library/ filesystem structure
3. Implement `search_library()`
4. Track access patterns

---

## 📊 Success Criteria

### Memory Tools Complete When:
- [x] All 6 methods exist in MemorySession
- [ ] All methods have full implementation (not TODO)
- [ ] All methods tested with real LLM
- [ ] All methods integrate with LanceDB
- [ ] Documentation updated

### Emotional Resonance Complete When:
- [ ] Calculation formula implemented
- [ ] Integrated into remember_fact()
- [ ] Used in search ranking
- [ ] Tracked in core/emotional_significance.md
- [ ] Tests passing

### Library Complete When:
- [ ] Auto-capture working
- [ ] search_library() functional
- [ ] Access patterns tracked
- [ ] Used in reconstruct_context()
- [ ] Tests passing

---

## 🎯 Next Session Priorities

1. **IMMEDIATE**: Add 3 missing methods to MemorySession
   - `search_library()`
   - `create_memory_link()`
   - `reflect_on()`
   - Rename `search_memory()` → `search_memories()`

2. **HIGH**: Implement `remember_fact()` fully
   - LanceDB storage
   - Emotional resonance calculation
   - Memory links creation

3. **HIGH**: Implement `search_memories()` fully
   - LanceDB hybrid search
   - Filter support
   - Emotional weighting

4. **MEDIUM**: Implement `reconstruct_context()` 9-step process
   - Semantic search
   - Link exploration
   - Library search
   - Context synthesis

---

**Source Document**: `/Users/albou/projects/abstractmemory/2025-09-30-critical-refactor-implementation1.txt`
**Key Sections**: Lines 48-54, 856-867, 962-970, 1063-1071, 1131-1147, 2929-3010

**Philosophy**: "Memory is the diary we all carry about with us" - Oscar Wilde
**Approach**: Ground every implementation in the critical refactor document specifications
