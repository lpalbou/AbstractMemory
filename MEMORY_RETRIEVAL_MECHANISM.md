# Memory Retrieval Mechanism - Complete Technical Breakdown

## Overview

Memory retrieval happens in **2 phases** during `reconstruct_context()`:
1. **Semantic Search** (Step 1) - Find directly relevant memories via embedding similarity
2. **Link Exploration** (Step 2) - Follow connections to find related context

---

## Phase 1: Semantic Search (Step 1/9)

### Entry Point
```python
# session.py:1810
semantic_memories = self.search_memories(
    query,
    filters={"user_id": user_id, "since": since},
    limit=config["limit"]
)
```

### Parameters
- **query**: User's input (e.g., "do you remember anything?")
- **filters**: Dict with:
  - `user_id`: Filter by user (e.g., "user")
  - `since`: Datetime threshold (e.g., last 24 hours for focus_level=3)
- **limit**: Max results (10 for focus_level=3)

### Execution Flow

#### 1. LanceDB Hybrid Search (Primary)
**File**: `lancedb_storage.py:225-304`

**Step 1.1: Generate Query Embedding**
```python
# Line 246
query_embedding = self._get_embedding(query)
# Uses: all-minilm-l6-v2 model via AbstractCore EmbeddingManager
# Returns: 384-dim vector [0.123, -0.456, ...]
```

**Step 1.2: Vector Similarity Search**
```python
# Line 254
results = table.search(query_embedding).limit(limit * 2)
# Database: repl_memory/lancedb/notes.lance/
# Method: Cosine similarity between query_embedding and stored embeddings
# Returns: Top 20 most similar notes (2x limit for filtering)
```

**Step 1.3: Apply SQL Filters**
```python
# Lines 259-286
if filters.get("user_id"):
    results = results.where(f"user_id = '{filters['user_id']}'")

if filters.get("since"):
    since_iso = filters["since"].isoformat()
    results = results.where(f"CAST(timestamp AS TIMESTAMP) >= CAST('{since_iso}' AS TIMESTAMP)")
```

**SQL Filters Available**:
- `user_id` - String match
- `category` - String match
- `min_importance` - Float >= threshold
- `emotion_valence` - String match
- `since` - Timestamp >= (with CAST for proper comparison)
- `until` - Timestamp <=

**Step 1.4: Final Limit & Parse**
```python
# Line 289
results = results.limit(limit).to_list()  # Top 10 after filtering

# Lines 292-298: Parse JSON fields
for result in results:
    result["linked_memory_ids"] = json.loads(result["linked_memory_ids"])
    result["tags"] = json.loads(result["tags"])
    result["metadata"] = json.loads(result["metadata"])
```

#### 2. Filesystem Fallback (If LanceDB Fails)
**File**: `session.py:1134-1165`

**Method**: Simple text search through markdown files
```python
# Line 1144
memory_files = list(notes_dir.rglob("*.md"))

# Line 1154
if query.lower() in content.lower():
    results.append({
        "file_path": str(file_path),
        "content": content[:500],
        "id": file_path.stem
    })
```

**Storage Location**: `repl_memory/notes/YYYY/MM/DD/*.md`

### What's Returned

**List[Dict]** with structure:
```python
{
    "id": "mem_20251001_202707_577108",
    "content": "Full memory content...",
    "user_id": "user",
    "category": "episodic",
    "importance": 0.95,
    "emotion_type": "curiosity",
    "emotion_intensity": 0.81,
    "emotion_valence": "positive",
    "timestamp": "2025-10-01T20:27:07",
    "linked_memory_ids": ["mem_123", "mem_456"],
    "tags": ["memory", "consciousness"],
    "file_path": "repl_memory/notes/2025/10/01/20_27_07_memory_mem_20251001_202707_577108.md",
    "_distance": 0.234  # Embedding similarity score (lower = more similar)
}
```

---

## Phase 2: Link Exploration (Step 2/9)

### Entry Point
```python
# session.py:1824
related_ids = self.lancedb_storage.get_related_memories(
    mem_id,
    depth=config["link_depth"]  # depth=2 for focus_level=3
)
```

### Parameters
- **memory_id**: ID of a memory from semantic search (e.g., "mem_20251001_202707_577108")
- **depth**: How many hops to follow (1-3 depending on focus_level)

### Execution Flow

**File**: `lancedb_storage.py:464-514`

**Step 2.1: Initialize BFS (Breadth-First Search)**
```python
# Line 480
visited = set([memory_id])  # Track visited to avoid cycles
current_level = [memory_id]  # Current hop level
```

**Step 2.2: For Each Depth Level**
```python
# Lines 483-504
for _ in range(depth):  # e.g., depth=2 → 2 hops
    next_level = []

    for mid in current_level:
        # Find outgoing links (A → B)
        outgoing = table.search().where(f"from_id = '{mid}'").to_list()

        # Find incoming links (B → A)
        incoming = table.search().where(f"to_id = '{mid}'").to_list()

        # Add unvisited to next_level
        for link in outgoing + incoming:
            target_id = link["to_id"] if "to_id" in link else link["from_id"]
            if target_id not in visited:
                visited.add(target_id)
                next_level.append(target_id)

    current_level = next_level
```

**Example**:
```
Depth 0: [mem_A]
Depth 1: [mem_B, mem_C, mem_D]  (directly linked to mem_A)
Depth 2: [mem_E, mem_F, mem_G]  (linked to B/C/D)

Final: visited = {mem_A, mem_B, mem_C, mem_D, mem_E, mem_F, mem_G}
Return: [mem_B, mem_C, mem_D, mem_E, mem_F, mem_G]  (excludes mem_A)
```

**Database**: `repl_memory/lancedb/links.lance/`

**Link Table Schema**:
```python
{
    "from_id": "mem_20251001_202707_577108",
    "to_id": "mem_20251001_101142_272191",
    "link_type": "relates_to",
    "timestamp": "2025-10-01T20:27:07"
}
```

### What's Returned

**List[str]**: List of memory IDs
```python
[
    "mem_20251001_101142_272191",
    "mem_20251001_182207_698804",
    "mem_20251001_104855_516693",
    ...
]
```

---

## Phase 3: Deduplication & Full Content Retrieval

### Entry Point
```python
# session.py:1893-1907
semantic_ids = {m.get("id") for m in semantic_memories}
linked_ids_only = set(linked_memories) - semantic_ids

# Retrieve full content for linked IDs not in semantic
linked_memory_objects = self.lancedb_storage.get_notes_by_ids(list(linked_ids_only))

# Combine and deduplicate
all_memories = semantic_memories + linked_memory_objects
unique_memories = {m.get("id"): m for m in all_memories if m.get("id")}
```

### Deduplication Logic

1. **Semantic memories** (from Step 1): Already have full content
2. **Linked memories** (from Step 2): Only IDs, need content retrieval
3. **Deduplicate**: Remove linked IDs that are already in semantic
4. **Retrieve**: Fetch full content for remaining linked IDs
5. **Merge**: Combine into unique set

**Example**:
```
Semantic (10): [mem_A, mem_B, mem_C, ..., mem_J]
Linked (12):   [mem_A, mem_B, mem_K, mem_L, ...]  (includes duplicates)

Dedup:
- linked_ids_only = {mem_K, mem_L, ...}  (removes A, B)
- Retrieve full content for mem_K, mem_L
- Final unique: {mem_A, mem_B, ..., mem_J, mem_K, mem_L} = 11 unique
```

### Full Content Retrieval

**File**: `lancedb_storage.py:423-462`

```python
def get_notes_by_ids(self, note_ids: List[str]) -> List[Dict]:
    # Build WHERE clause
    ids_str = "', '".join(note_ids)
    where_clause = f"id IN ('{ids_str}')"

    # Retrieve from LanceDB
    results = table.search().where(where_clause).limit(len(note_ids)).to_list()

    # Parse JSON fields
    for result in results:
        result["linked_memory_ids"] = json.loads(result["linked_memory_ids"])
        ...

    return results
```

---

## Focus Level Configuration

**File**: `session.py:1797-1805`

```python
focus_configs = {
    0: {"limit": 2,  "hours": 1,   "link_depth": 0},  # Minimal
    1: {"limit": 5,  "hours": 4,   "link_depth": 1},
    2: {"limit": 8,  "hours": 12,  "link_depth": 1},
    3: {"limit": 10, "hours": 24,  "link_depth": 2},  # Default (medium)
    4: {"limit": 15, "hours": 72,  "link_depth": 3},
    5: {"limit": 20, "hours": 168, "link_depth": 3}   # Exhaustive
}
```

**Focus Level 3 (Default)**:
- **Semantic limit**: 10 memories
- **Time window**: Last 24 hours
- **Link depth**: 2 hops
- **Expected total**: 10-20 unique memories (after dedup)

---

## Storage Locations

### LanceDB (Vector Database)
**Path**: `repl_memory/lancedb/`

**Tables**:
1. **notes.lance** - Memory embeddings + metadata
   - Schema: id, content, embedding[384], user_id, timestamp, importance, emotion_*, tags, etc.
   - Indexed on: embedding (for semantic search)

2. **links.lance** - Memory relationships
   - Schema: from_id, to_id, link_type, timestamp
   - Indexed on: from_id, to_id (for graph traversal)

3. **library.lance** - Captured documents (code, articles)
   - Schema: doc_id, content_excerpt, embedding[384], source_path, etc.

### Filesystem (Markdown Files)
**Path**: `repl_memory/notes/YYYY/MM/DD/`

**Format**: `HH_MM_SS_memory_<memory_id>.md`

**Example**: `repl_memory/notes/2025/10/01/20_27_07_memory_mem_20251001_202707_577108.md`

**Content**:
```markdown
# Memory: mem_20251001_202707_577108

**Category**: episodic
**Importance**: 0.95
**Emotion**: curiosity (0.81, positive)
**Created**: 2025-10-01 20:27:07
**User**: user

## Content

User repeatedly asks if I remember anything, suggesting they're exploring...

## Links
- relates_to: mem_20251001_101142_272191
- relates_to: mem_20251001_182207_698804
```

---

## Complete Retrieval Example

**Query**: "do you remember anything?"
**User**: "user"
**Focus Level**: 3

### Step 1: Semantic Search
```python
# Parameters
query = "do you remember anything?"
filters = {"user_id": "user", "since": "2025-09-30T20:27:00"}
limit = 10

# Embedding
query_embedding = [0.123, -0.456, ...]  # 384-dim vector

# LanceDB Search
SELECT * FROM notes
WHERE embedding <-> query_embedding  # Cosine similarity
  AND user_id = 'user'
  AND CAST(timestamp AS TIMESTAMP) >= CAST('2025-09-30T20:27:00' AS TIMESTAMP)
ORDER BY _distance ASC
LIMIT 10

# Results: 10 semantic memories
```

### Step 2: Link Exploration (Depth=2)
```python
# For top 5 semantic memories, follow links
for mem in semantic_memories[:5]:
    related = get_related_memories(mem["id"], depth=2)
    # mem_A: finds [mem_B, mem_C] (depth 1) → [mem_D] (depth 2)
    # mem_B: finds [mem_A, mem_E] → [mem_F]
    # ...

# Total linked IDs: 12 (includes duplicates)
```

### Step 3: Deduplication
```python
semantic_ids = {mem_A, mem_B, mem_C, ..., mem_J}  # 10
linked_ids = {mem_A, mem_B, mem_D, mem_E, mem_F, ...}  # 12

linked_ids_only = linked_ids - semantic_ids  # {mem_D, mem_E, mem_F}

# Retrieve full content for mem_D, mem_E, mem_F
linked_objects = get_notes_by_ids([mem_D, mem_E, mem_F])

# Merge
unique_memories = {
    mem_A: {...}, mem_B: {...}, ..., mem_J: {...},
    mem_D: {...}, mem_E: {...}, mem_F: {...}
}  # 13 unique

# But only 11 shown because mem_E, mem_F were actually duplicates too
```

### Final Output
```python
{
    "total_memories": 11,  # Unique count
    "memories_retrieved": [
        {"id": "mem_A", "content": "...", ...},
        {"id": "mem_B", "content": "...", ...},
        ...
    ],
    "synthesized_context": "[Retrieved Memories]:\n1. [mem_A]\n   ...",
    "context_tokens": 523
}
```

---

## Summary

**Retrieval happens from 2 sources**:
1. ✅ **LanceDB Vector Database** (primary) - Semantic search via embeddings
2. ✅ **Markdown Filesystem** (fallback) - Text search if LanceDB fails

**2-Phase Process**:
1. ✅ **Semantic Search** → Find directly relevant memories (embedding similarity)
2. ✅ **Link Exploration** → Follow connections to related memories (graph traversal)

**Final Output**: Deduplicated list of memory objects with full content, synthesized into prompt for LLM
