# Memory Operations API Documentation

## Overview

AbstractMemory provides powerful, categorized memory operations with full observability. This document covers the three main memory operations added in the recent architecture enhancement.

---

## `remember_fact()`

Store facts with categorization, confidence scoring, and metadata.

### Signature

```python
def remember_fact(
    self,
    fact: str,
    category: str = "general",
    user_id: Optional[str] = None,
    confidence: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None
) -> None
```

### Parameters

- **`fact`** (str): The fact to remember
- **`category`** (str): Memory category (default: "general")
  - `user_profile` - Facts about specific users
  - `preference` - User preferences and likes
  - `context` - Situational or environmental context
  - `knowledge` - General knowledge and facts
  - `event` - Specific events or occurrences
  - `people` - Information about other people mentioned
  - `document` - Facts extracted from documents
  - `conversation` - Facts from conversations
- **`user_id`** (Optional[str]): Associated user (uses `current_user_id` if None)
- **`confidence`** (float): Confidence score 0.0-1.0 (default: 1.0)
- **`metadata`** (Optional[Dict]): Additional metadata to store

### Examples

```python
# Store user preference
session.remember_fact(
    "Alice loves Python programming",
    category="preference",
    user_id="alice",
    confidence=0.95
)

# Store knowledge with metadata
session.remember_fact(
    "Python 3.11 added task groups",
    category="knowledge",
    confidence=0.9,
    metadata={
        "source": "documentation",
        "version": "3.11",
        "importance": "high"
    }
)

# Store event
session.remember_fact(
    "Alice completed the async tutorial",
    category="event",
    user_id="alice",
    confidence=0.85
)
```

### Observability

Every `remember_fact()` call is logged with structured data:

```python
{
    'operation': 'remember_fact',
    'category': category,
    'confidence': confidence,
    'user_id': user_id,
    'fact_preview': fact[:50] + '...',
    'timestamp': '2025-09-29T21:00:00'
}
```

Access counter: `session.facts_learned`

---

## `search_memory_for()`

Advanced hybrid search combining semantic similarity with SQL-style filtering.

### Signature

```python
def search_memory_for(
    self,
    query: str,
    category: Optional[str] = None,
    user_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    min_confidence: float = 0.0,
    limit: int = 10
) -> List[Dict[str, Any]]
```

### Parameters

- **`query`** (str): Semantic search query
- **`category`** (Optional[str]): Filter by memory category
- **`user_id`** (Optional[str]): Filter by specific user
- **`since`** (Optional[datetime]): Only return memories after this time
- **`until`** (Optional[datetime]): Only return memories before this time
- **`min_confidence`** (float): Minimum confidence threshold (default: 0.0)
- **`limit`** (int): Maximum number of results (default: 10)

### Returns

```python
List[Dict[str, Any]]  # List of matching memory items
```

Each result dictionary contains:
- `content`: The memory content
- `confidence`: Confidence score
- `category`: Memory category
- `user_id`: Associated user
- `timestamp`: When the memory was created
- `source`: Where the memory came from (semantic/storage)
- `metadata`: Additional metadata

### Examples

```python
# Find Alice's Python preferences
results = session.search_memory_for(
    "Python",
    category="preference",
    user_id="alice"
)

# Find recent errors
from datetime import datetime, timedelta
yesterday = datetime.now() - timedelta(days=1)
errors = session.search_memory_for(
    "error",
    since=yesterday,
    min_confidence=0.8
)

# Find high-confidence knowledge about async
knowledge = session.search_memory_for(
    "async Python",
    category="knowledge",
    min_confidence=0.9,
    limit=5
)

# Find all people mentioned in last week
last_week = datetime.now() - timedelta(days=7)
people = session.search_memory_for(
    "",  # Empty query = SQL-only filtering
    category="people",
    since=last_week
)
```

### Search Behavior

1. **Hybrid Search** (if LanceDB with `hybrid_search()` available):
   - Semantic similarity via embeddings
   - SQL filtering for category, user, time, confidence
   - Best performance

2. **Fallback** (if hybrid_search not available):
   - Semantic memory search
   - Manual filtering by category, user, time, confidence
   - Searches storage backend
   - Merges and deduplicates results

### Observability

Every `search_memory_for()` call is logged:

```python
{
    'operation': 'search_memory_for',
    'query_preview': query[:50] + '...',
    'category': category,
    'user_id': user_id,
    'results_count': len(results),
    'search_type': 'hybrid',
    'timestamp': '2025-09-29T21:00:00'
}
```

Access counter: `session.searches_performed`

---

## `reconstruct_context()`

Reconstruct comprehensive context based on user, query, time, location, and mood.

### Signature

```python
def reconstruct_context(
    self,
    user_id: str,
    query: str,
    timestamp: Optional[datetime] = None,
    location: Optional[str] = None,
    mood: Optional[str] = None,
    focus_level: int = 3
) -> Dict[str, Any]
```

### Parameters

- **`user_id`** (str): The user for whom to reconstruct context
- **`query`** (str): The query/topic for context relevance
- **`timestamp`** (Optional[datetime]): Specific time context (defaults to now)
- **`location`** (Optional[str]): Location context (e.g., "office", "home")
- **`mood`** (Optional[str]): Emotional context (e.g., "focused", "casual", "stressed")
- **`focus_level`** (int): How much context to retrieve (0-5, default: 3)
  - `0`: Minimal (lazy - quick responses, 2 memories, 1 hour back)
  - `1`: Light (basic context, 5 memories, 4 hours back)
  - `2`: Moderate (standard context, 8 memories, 12 hours back)
  - `3`: Balanced (default - good context, 10 memories, 24 hours back)
  - `4`: Deep (extensive context, 15 memories, 3 days back)
  - `5`: Maximum (super focused, 20 memories, 1 week back)

### Returns

```python
Dict[str, Any]  # Comprehensive context dictionary
```

The returned context includes:

```python
{
    'user_id': str,
    'query': str,
    'timestamp': str,  # ISO format
    'focus_level': int,

    'user_profile': Dict,  # User's profile data

    'relevant_memories': List[Dict],  # Memories matching the query

    'recent_interactions': List[Dict],  # Recent interactions

    'temporal_context': {
        'time_of_day': int,  # 0-23
        'day_of_week': str,  # Monday, Tuesday, etc.
        'date': str,  # ISO date
        'hours_window': int,  # How many hours back searched
        'is_working_hours': bool,  # 9 AM - 5 PM
        'is_weekend': bool
    },

    'spatial_context': {  # Only if location provided
        'location': str,
        'location_memories': List[Dict]  # Memories associated with location
    },

    'emotional_context': {  # Only if mood provided
        'mood': str,
        'suggested_approach': str,  # Communication approach for this mood
        'mood_relevant_memories': List[Dict]
    },

    'metadata': {
        'reconstruction_time': str,  # When context was built
        'total_memories_retrieved': int,
        'context_quality': str  # 'basic', 'medium', or 'high'
    }
}
```

### Examples

```python
# Basic context reconstruction
context = session.reconstruct_context(
    user_id="alice",
    query="Python debugging"
)

# Deep context with location and mood
context = session.reconstruct_context(
    user_id="alice",
    query="debugging async Python code",
    location="home office",
    mood="focused",
    focus_level=4  # Deep context
)

# Minimal context for quick response
context = session.reconstruct_context(
    user_id="alice",
    query="quick question",
    focus_level=0  # Lazy/minimal
)

# Context at specific time
from datetime import datetime
past_time = datetime(2025, 1, 15, 14, 30)
context = session.reconstruct_context(
    user_id="alice",
    query="what was I working on",
    timestamp=past_time
)
```

### Mood Approaches

When `mood` is specified, `suggested_approach` provides communication guidance:

- **focused**: "Be concise and technical. User wants efficiency."
- **casual**: "Be conversational and friendly. Take time to explain."
- **stressed**: "Be supportive and clear. Avoid complexity."
- **curious**: "Be detailed and explorative. Share interesting context."
- **frustrated**: "Be patient and solution-focused. Acknowledge challenges."
- **excited**: "Match enthusiasm. Share in the positive energy."

### Use Cases

1. **Personalized Responses**
   ```python
   context = session.reconstruct_context(user_id, user_query, focus_level=3)
   # Use context['user_profile'] and context['relevant_memories'] to personalize
   ```

2. **Time-Aware Assistance**
   ```python
   context = session.reconstruct_context(user_id, query)
   if context['temporal_context']['is_working_hours']:
       # Professional tone
   else:
       # Casual tone
   ```

3. **Location-Aware Support**
   ```python
   context = session.reconstruct_context(user_id, query, location="office")
   # Access context['spatial_context']['location_memories']
   ```

4. **Mood-Adaptive Interaction**
   ```python
   context = session.reconstruct_context(user_id, query, mood="stressed")
   approach = context['emotional_context']['suggested_approach']
   # Adjust response style based on mood
   ```

---

## Observability

All memory operations use AbstractCore's structured logging system (with fallback to standard logging).

### Accessing Observability Data

```python
# Get comprehensive observability report
report = session.get_observability_report()

print(f"Total interactions: {report['session_stats']['total_interactions']}")
print(f"Facts learned: {report['session_stats']['facts_learned']}")
print(f"Searches performed: {report['session_stats']['searches_performed']}")
print(f"Logging backend: {report['session_stats']['logging_backend']}")

# Memory state per tier
print(f"Working memory items: {report['memory_state']['working']['items']}")
print(f"Semantic facts: {report['memory_state']['semantic']['facts']}")
print(f"Document chunks: {report['memory_state']['document']['chunks']}")
```

### Observability Report Structure

```python
{
    'last_generation': {
        'memory_items_injected': int,
        'memory_items': List[...],  # First 5
        'context_preview': str,
        'context_length_chars': int,
        'estimated_tokens': int
    },

    'session_stats': {
        'total_interactions': int,
        'users_seen': int,
        'facts_learned': int,
        'searches_performed': int,
        'logging_backend': str  # 'AbstractCore' or 'standard'
    },

    'memory_state': {
        'working': {...},
        'semantic': {...},
        'episodic': {...},
        'document': {...}
    },

    'storage': {
        # Storage statistics from DualStorageManager
    }
}
```

---

## Best Practices

### 1. Choose Appropriate Categories

```python
# User-specific information
session.remember_fact("Alice uses VSCode", category="user_profile", user_id="alice")
session.remember_fact("Alice prefers dark mode", category="preference", user_id="alice")

# General knowledge
session.remember_fact("Python 3.11 is faster", category="knowledge")

# Events and people
session.remember_fact("Meeting with Bob at 2pm", category="event", user_id="alice")
session.remember_fact("Bob is the team lead", category="people")
```

### 2. Use Confidence Appropriately

```python
# High confidence for direct statements
session.remember_fact("User explicitly said they love Python", confidence=1.0)

# Medium confidence for inferred facts
session.remember_fact("User seems to prefer functional style", confidence=0.7)

# Low confidence for guesses
session.remember_fact("User might be interested in Rust", confidence=0.3)
```

### 3. Optimize Focus Levels

```python
# Quick responses (lazy)
context = session.reconstruct_context(user_id, query, focus_level=0)

# Standard responses (balanced)
context = session.reconstruct_context(user_id, query, focus_level=3)

# Deep analysis (maximum)
context = session.reconstruct_context(user_id, query, focus_level=5)
```

### 4. Combine Filters Effectively

```python
# Find high-confidence recent preferences
results = session.search_memory_for(
    "programming language",
    category="preference",
    user_id="alice",
    since=datetime.now() - timedelta(days=7),
    min_confidence=0.9
)
```

---

## Integration with Storage

All memory operations integrate with AbstractMemory's dual storage system:

- **Markdown Storage**: Human-readable, observable, version-controllable
- **LanceDB Storage**: SQL + vector search for powerful querying

Storage is automatic when `DualStorageManager` is configured in mode `"dual"`, `"markdown"`, or `"lancedb"`.

---

## See Also

- [LanceDB Enhancements Documentation](./api_lancedb_enhancements.md)
- [Architecture Overview](./architecture_current_state.md)
- [Testing Guide](./testing_guide.md)