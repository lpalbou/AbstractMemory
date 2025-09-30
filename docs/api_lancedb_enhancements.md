# LanceDB Storage Enhancements API

## Overview

AbstractMemory's LanceDB storage has been enhanced with category support, confidence scoring, tags, and powerful hybrid search capabilities combining semantic similarity with SQL filtering.

---

## Schema Enhancements

### Interactions Table

The `interactions` table now includes additional fields:

```python
{
    'id': str,
    'user_id': str,
    'timestamp': datetime,
    'user_input': str,
    'agent_response': str,
    'topic': str,
    'category': str,          # NEW: Memory category
    'confidence': float,      # NEW: Confidence score 0.0-1.0
    'tags': str,              # NEW: JSON array of tags
    'metadata': str,          # JSON string
    'embedding': vector       # Vector embedding
}
```

### Saving with New Fields

```python
storage.save_interaction(
    user_id="alice",
    timestamp=datetime.now(),
    user_input="I love Python",
    agent_response="Great choice!",
    topic="preference",
    metadata={
        'category': 'preference',      # Stored as top-level field
        'confidence': 0.95,            # Stored as top-level field
        'tags': ['python', 'programming'],  # Stored as top-level field
        'custom_data': 'value'         # Stored in metadata JSON
    }
)
```

---

## `hybrid_search()`

Powerful hybrid search combining semantic similarity with SQL filtering.

### Signature

```python
def hybrid_search(
    self,
    semantic_query: str,
    sql_filters: Optional[Dict[str, Any]] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 10
) -> List[Dict]
```

### Parameters

- **`semantic_query`** (str): Query for semantic similarity search
- **`sql_filters`** (Optional[Dict]): Dictionary of SQL filters:
  - `category`: Filter by memory category
  - `user_id`: Filter by user
  - `min_confidence`: Minimum confidence threshold
  - `tags`: Filter by tags (any match)
- **`since`** (Optional[datetime]): Only return results after this time
- **`until`** (Optional[datetime]): Only return results before this time
- **`limit`** (int): Maximum number of results

### Returns

```python
List[Dict]  # List of matching interaction dictionaries
```

Each result includes:
- `id`, `user_id`, `timestamp`
- `user_input`, `agent_response`, `topic`
- `category`, `confidence`, `tags`
- `metadata`

### Examples

#### 1. Semantic + Category + User Filter

```python
# "What did Alice say about Python?"
results = storage.hybrid_search(
    semantic_query="Python programming",
    sql_filters={
        'category': 'preference',
        'user_id': 'alice'
    },
    limit=10
)
```

#### 2. Semantic + Confidence + Temporal Filter

```python
from datetime import datetime, timedelta

# High-confidence knowledge from last week
yesterday = datetime.now() - timedelta(days=1)
last_week = datetime.now() - timedelta(days=7)

results = storage.hybrid_search(
    semantic_query="debugging techniques",
    sql_filters={
        'category': 'knowledge',
        'min_confidence': 0.8
    },
    since=last_week,
    until=yesterday,
    limit=5
)
```

#### 3. Tags + User Filter

```python
# Find all Python-tagged interactions for Alice
results = storage.hybrid_search(
    semantic_query="",  # Empty = SQL-only filtering
    sql_filters={
        'user_id': 'alice',
        'tags': ['python']  # Matches if 'python' is in tags array
    },
    limit=20
)
```

#### 4. Multiple Tag Filter

```python
# Find interactions with either 'async' or 'concurrency' tags
results = storage.hybrid_search(
    semantic_query="async programming",
    sql_filters={
        'category': 'knowledge',
        'tags': ['async', 'concurrency']  # Match any
    }
)
```

### Search Behavior

1. **Semantic Query Provided**:
   - Generate embedding from query
   - Vector similarity search on `embedding` field
   - Apply SQL filters via `.where()` clause
   - Return top `limit` results

2. **Empty Semantic Query**:
   - SQL-only filtering
   - No vector search
   - Useful for pure category/user/time queries

---

## `search_by_category()`

Convenience method for category-based searches.

### Signature

```python
def search_by_category(
    self,
    category: str,
    user_id: Optional[str] = None,
    limit: int = 10
) -> List[Dict]
```

### Parameters

- **`category`** (str): Memory category to search
- **`user_id`** (Optional[str]): Optional user filter
- **`limit`** (int): Maximum results

### Examples

```python
# Get all Alice's preferences
preferences = storage.search_by_category(
    "preference",
    user_id="alice",
    limit=20
)

# Get all knowledge items (any user)
knowledge = storage.search_by_category(
    "knowledge",
    limit=50
)

# Get all events for Bob
events = storage.search_by_category(
    "event",
    user_id="bob"
)
```

---

## `temporal_search()`

Search within a specific time range with semantic query.

### Signature

```python
def temporal_search(
    self,
    query: str,
    since: datetime,
    until: Optional[datetime] = None,
    user_id: Optional[str] = None,
    limit: int = 10
) -> List[Dict]
```

### Parameters

- **`query`** (str): Semantic search query
- **`since`** (datetime): Start of time range
- **`until`** (Optional[datetime]): End of time range (defaults to now)
- **`user_id`** (Optional[str]): Optional user filter
- **`limit`** (int): Maximum results

### Examples

```python
from datetime import datetime, timedelta

# Find Python discussions in last 24 hours
yesterday = datetime.now() - timedelta(days=1)
recent = storage.temporal_search(
    "Python",
    since=yesterday,
    user_id="alice"
)

# Find errors from last week
last_week = datetime.now() - timedelta(days=7)
errors = storage.temporal_search(
    "error debugging",
    since=last_week,
    limit=20
)

# Find interactions between specific dates
start = datetime(2025, 1, 1)
end = datetime(2025, 1, 31)
january = storage.temporal_search(
    "project",
    since=start,
    until=end,
    user_id="alice"
)
```

---

## `get_user_timeline()`

Get chronological timeline of interactions for a user.

### Signature

```python
def get_user_timeline(
    self,
    user_id: str,
    since: Optional[datetime] = None,
    limit: int = 50
) -> List[Dict]
```

### Parameters

- **`user_id`** (str): User identifier
- **`since`** (Optional[datetime]): Optional start date (defaults to all time)
- **`limit`** (int): Maximum results

### Returns

List of interactions sorted by timestamp (newest first).

### Examples

```python
# Get Alice's full timeline
timeline = storage.get_user_timeline("alice", limit=100)

# Get last 30 days
thirty_days_ago = datetime.now() - timedelta(days=30)
recent_timeline = storage.get_user_timeline(
    "alice",
    since=thirty_days_ago,
    limit=50
)

# Iterate through timeline
for interaction in timeline:
    print(f"{interaction['timestamp']}: {interaction['user_input']}")
```

---

## Advanced Query Patterns

### 1. Complex Multi-Filter Query

```python
# Find high-confidence Python knowledge from Alice in last month
from datetime import datetime, timedelta

last_month = datetime.now() - timedelta(days=30)

results = storage.hybrid_search(
    semantic_query="Python best practices",
    sql_filters={
        'category': 'knowledge',
        'user_id': 'alice',
        'min_confidence': 0.85,
        'tags': ['python', 'best-practices']
    },
    since=last_month,
    limit=15
)
```

### 2. Category-Specific User Analysis

```python
# Analyze user's preferences
preferences = storage.search_by_category("preference", user_id="alice")

# Analyze user's knowledge base
knowledge = storage.search_by_category("knowledge", user_id="alice")

# Analyze user's events
events = storage.search_by_category("event", user_id="alice")

# Build user profile from categories
profile = {
    'preferences': preferences,
    'knowledge': knowledge,
    'events': events
}
```

### 3. Temporal Pattern Analysis

```python
# Get interactions for each day of last week
from datetime import datetime, timedelta

daily_interactions = {}
for day in range(7):
    day_start = datetime.now().replace(hour=0, minute=0, second=0) - timedelta(days=day+1)
    day_end = datetime.now().replace(hour=23, minute=59, second=59) - timedelta(days=day+1)

    daily = storage.temporal_search(
        "",  # All interactions
        since=day_start,
        until=day_end,
        user_id="alice"
    )

    daily_interactions[day_start.date()] = daily
```

### 4. Tag-Based Analytics

```python
# Get all programming language discussions
languages = ['python', 'javascript', 'rust', 'go']
language_discussions = {}

for lang in languages:
    results = storage.hybrid_search(
        semantic_query="",
        sql_filters={'tags': [lang]},
        limit=100
    )
    language_discussions[lang] = results

# Find most discussed language
most_discussed = max(language_discussions.items(), key=lambda x: len(x[1]))
```

---

## Integration with MemorySession

The enhanced LanceDB methods are automatically used by `MemorySession.search_memory_for()` when available:

```python
# MemorySession automatically uses hybrid_search if available
results = session.search_memory_for(
    "Python",
    category="preference",
    user_id="alice",
    since=yesterday,
    min_confidence=0.8
)

# Falls back to manual filtering if hybrid_search not implemented
# This happens transparently - user code doesn't change
```

---

## Storage Statistics

Get detailed storage statistics including new fields:

```python
stats = storage.get_stats()

print(f"Total interactions: {stats['total_interactions']}")
print(f"Total notes: {stats['total_notes']}")
print(f"Embedding provider: {stats['embedding_info']}")
print(f"Embedding consistency: {stats.get('embedding_consistency', 'N/A')}")
```

---

## Memory Categories

Standard categories supported:

1. **user_profile**: Facts about specific users
2. **preference**: User preferences and likes
3. **context**: Situational or environmental context
4. **knowledge**: General knowledge and facts
5. **event**: Specific events or occurrences
6. **people**: Information about other people mentioned
7. **document**: Facts extracted from documents
8. **conversation**: Facts from conversations

Custom categories can be added via metadata.

---

## Tags Best Practices

### Tag Naming

```python
# Use lowercase, hyphenated tags
tags = ['python', 'async-programming', 'best-practices']

# Group related concepts
tags = ['language:python', 'framework:django', 'tool:vscode']

# Use hierarchical tags
tags = ['programming', 'programming:python', 'programming:python:async']
```

### Tag Queries

```python
# Single tag
results = storage.hybrid_search("", sql_filters={'tags': ['python']})

# Multiple tags (OR logic)
results = storage.hybrid_search("", sql_filters={'tags': ['python', 'javascript']})

# Tags + Category
results = storage.hybrid_search(
    "async",
    sql_filters={
        'category': 'knowledge',
        'tags': ['python', 'async']
    }
)
```

---

## Performance Considerations

### Vector Search

- LanceDB vector search is highly optimized
- Embedding generation happens once per save
- Search uses approximate nearest neighbors (ANN)
- Fast even with millions of records

### SQL Filtering

- Category, user_id, confidence are indexed fields
- Timestamp queries are optimized
- Tags use JSON containment checks (slightly slower)

### Hybrid Queries

- Semantic search narrows results first
- SQL filters applied to semantic results
- Most efficient: semantic query + filters
- Less efficient: empty query + filters only (full scan)

### Recommendations

1. **Use semantic queries when possible** - narrows search space
2. **Combine filters** - category + user_id is very efficient
3. **Limit results** - use appropriate `limit` values
4. **Index frequently queried fields** - category and user_id are indexed

---

## Migration Guide

### Existing Databases

If you have an existing LanceDB database without the new fields:

1. **New interactions automatically use new schema**
2. **Old interactions will have default values**:
   - `category` = "conversation"
   - `confidence` = 1.0
   - `tags` = []

3. **No migration script needed** - backward compatible

### Schema Compatibility

```python
# Old code still works
storage.save_interaction(
    user_id="alice",
    timestamp=datetime.now(),
    user_input="test",
    agent_response="response",
    topic="test"
)
# Automatically gets: category="conversation", confidence=1.0, tags=[]

# New code uses enhanced features
storage.save_interaction(
    user_id="alice",
    timestamp=datetime.now(),
    user_input="test",
    agent_response="response",
    topic="test",
    metadata={
        'category': 'preference',
        'confidence': 0.9,
        'tags': ['test', 'example']
    }
)
```

---

## Error Handling

All methods include comprehensive error handling:

```python
try:
    results = storage.hybrid_search(
        "query",
        sql_filters={'category': 'knowledge'}
    )
except Exception as e:
    logger.error(f"Hybrid search failed: {e}")
    results = []  # Returns empty list on error
```

Errors are logged but don't crash - methods return empty lists on failure.

---

## See Also

- [Memory Operations API](./api_memory_operations.md)
- [Architecture Overview](./architecture_current_state.md)
- [Testing Guide](./testing_guide.md)
- [LanceDB Documentation](https://lancedb.com/docs/)