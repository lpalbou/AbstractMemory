# API Reference

Complete API documentation for AbstractMemory package with detailed method signatures, parameters, and examples.

## 📦 Package Overview

```python
from abstractmemory import (
    create_memory,           # Main factory function
    MemoryItem,             # Core data structure
    ScratchpadMemory,       # Simple memory for ReAct agents
    BufferMemory,           # Simple memory for chatbots
    GroundedMemory,         # Complex memory for autonomous agents
)
```

## 🏗️ Factory Function

### `create_memory()`

Main factory function for creating memory instances.

```python
def create_memory(
    memory_type: Literal["scratchpad", "buffer", "grounded"] = "scratchpad",
    **kwargs
) -> Union[ScratchpadMemory, BufferMemory, GroundedMemory]
```

**Parameters:**
- `memory_type` (str): Type of memory to create
  - `"scratchpad"`: For ReAct agents with thought-action-observation cycles
  - `"buffer"`: For simple chatbots with conversation history
  - `"grounded"`: For autonomous agents with four-tier memory architecture
- `**kwargs`: Memory-specific configuration options

**Returns:**
- Memory instance of the specified type

**Examples:**
```python
# Simple memory types
scratchpad = create_memory("scratchpad", max_entries=100)
buffer = create_memory("buffer", max_messages=200)

# Complex memory type
grounded = create_memory(
    "grounded",
    working_capacity=15,
    enable_kg=True,
    semantic_threshold=3
)
```

## 🧩 Core Data Structures

### `MemoryItem`

Core data structure for all memory items.

```python
@dataclass
class MemoryItem:
    content: Any                 # The actual content
    event_time: datetime        # When it happened
    ingestion_time: datetime    # When we learned about it
    confidence: float = 1.0     # How confident we are (0.0-1.0)
    metadata: Dict[str, Any] = None  # Additional context
```

**Attributes:**
- `content`: The actual memory content (any type)
- `event_time`: When the event actually occurred
- `ingestion_time`: When the memory system learned about it
- `confidence`: Confidence score between 0.0 and 1.0
- `metadata`: Optional dictionary for additional information

**Example:**
```python
from datetime import datetime
from abstractmemory import MemoryItem

item = MemoryItem(
    content="User prefers detailed explanations",
    event_time=datetime.now(),
    ingestion_time=datetime.now(),
    confidence=0.8,
    metadata={"type": "user_preference", "source": "conversation"}
)
```

## 📝 Simple Memory Types

### ScratchpadMemory

Memory for ReAct agents with structured reasoning cycles.

#### Constructor
```python
class ScratchpadMemory:
    def __init__(self, max_entries: int = 50):
        """
        Args:
            max_entries: Maximum number of entries to store (default: 50)
        """
```

#### Methods

##### `add_thought(thought: str) -> None`
Add a thought to the reasoning trace.

**Parameters:**
- `thought` (str): The thought to add

**Example:**
```python
scratchpad.add_thought("I need to analyze this step by step")
```

##### `add_action(action: str, params: Optional[Dict] = None) -> None`
Add an action to the reasoning trace.

**Parameters:**
- `action` (str): The action name
- `params` (dict, optional): Action parameters

**Example:**
```python
scratchpad.add_action("web_search", {"query": "Python tutorials", "num_results": 5})
```

##### `add_observation(observation: str) -> None`
Add an observation to the reasoning trace.

**Parameters:**
- `observation` (str): The observation to add

**Example:**
```python
scratchpad.add_observation("Found 10 relevant tutorials")
```

##### `get_context() -> str`
Get formatted context for LLM consumption.

**Returns:**
- Formatted string with thought-action-observation sequence

**Example:**
```python
context = scratchpad.get_context()
# Returns: "Thought: ...\nAction: ...\nObservation: ..."
```

##### `get_recent_entries(limit: int = 10) -> List[Dict]`
Get recent entries from the scratchpad.

**Parameters:**
- `limit` (int): Maximum number of entries to return (default: 10)

**Returns:**
- List of dictionaries with entry data

### BufferMemory

Memory for simple chatbots with conversation history.

#### Constructor
```python
class BufferMemory:
    def __init__(self, max_messages: int = 100):
        """
        Args:
            max_messages: Maximum number of messages to store (default: 100)
        """
```

#### Methods

##### `add_message(role: str, content: str) -> None`
Add a message to the conversation history.

**Parameters:**
- `role` (str): Message role ("user" or "assistant")
- `content` (str): Message content

**Example:**
```python
buffer.add_message("user", "Hello, how are you?")
buffer.add_message("assistant", "I'm doing well, thank you!")
```

##### `get_context() -> str`
Get formatted conversation context.

**Returns:**
- Human-readable conversation string

**Example:**
```python
context = buffer.get_context()
# Returns: "User: Hello\nAssistant: Hi there!\n..."
```

##### `get_messages_for_llm() -> List[Dict[str, str]]`
Get messages in LLM-compatible format.

**Returns:**
- List of message dictionaries with "role" and "content" keys

**Example:**
```python
messages = buffer.get_messages_for_llm()
# Returns: [{"role": "user", "content": "..."}, ...]
```

##### `get_recent_messages(limit: int = 10) -> List[Dict]`
Get recent messages from the conversation.

**Parameters:**
- `limit` (int): Maximum number of messages to return (default: 10)

**Returns:**
- List of message dictionaries

## 🏛️ Complex Memory Type

### GroundedMemory

Sophisticated memory with four-tier architecture for autonomous agents.

#### Constructor
```python
class GroundedMemory:
    def __init__(
        self,
        working_capacity: int = 10,
        enable_kg: bool = True,
        semantic_threshold: int = 3,
        core_update_threshold: int = 5,
        default_user_id: str = "default"
    ):
        """
        Args:
            working_capacity: Working memory capacity (default: 10)
            enable_kg: Enable temporal knowledge graph (default: True)
            semantic_threshold: Fact validation threshold (default: 3)
            core_update_threshold: Core memory update threshold (default: 5)
            default_user_id: Default user context (default: "default")
        """
```

#### Core Methods

##### `set_current_user(user_id: str, relationship: str = "user") -> None`
Set the current user context.

**Parameters:**
- `user_id` (str): User identifier
- `relationship` (str): Relationship type ("owner", "user", "guest", etc.)

**Example:**
```python
memory.set_current_user("alice", relationship="owner")
```

##### `add_interaction(user_input: str, agent_response: str) -> None`
Add a complete user-agent interaction.

**Parameters:**
- `user_input` (str): User's input message
- `agent_response` (str): Agent's response

**Example:**
```python
memory.add_interaction(
    "I love Python programming",
    "Python is indeed a great language! What aspects do you like most?"
)
```

##### `get_full_context(query: str = "", user_id: Optional[str] = None) -> str`
Get comprehensive context from all memory tiers.

**Parameters:**
- `query` (str): Query for relevant context retrieval (default: "")
- `user_id` (str, optional): Specific user context to retrieve

**Returns:**
- Formatted context string combining all memory tiers

**Example:**
```python
context = memory.get_full_context("Python programming", user_id="alice")
```

##### `learn_about_user(fact: str, user_id: Optional[str] = None) -> None`
Learn a fact about a user.

**Parameters:**
- `fact` (str): Fact about the user
- `user_id` (str, optional): User ID (uses current user if not specified)

**Example:**
```python
memory.learn_about_user("Prefers detailed explanations")
memory.learn_about_user("Expert in machine learning", user_id="alice")
```

##### `track_failure(action: str, context: str) -> None`
Track a failed action to learn from mistakes.

**Parameters:**
- `action` (str): Action that failed
- `context` (str): Context of the failure

**Example:**
```python
memory.track_failure("web_search", "network timeout")
```

##### `track_success(action: str, context: str) -> None`
Track a successful action to reinforce patterns.

**Parameters:**
- `action` (str): Action that succeeded
- `context` (str): Context of the success

**Example:**
```python
memory.track_success("code_generation", "Python function with error handling")
```

##### `update_core_memory(block_id: str, content: str, reasoning: str = "") -> bool`
Update core memory block (self-editing capability).

**Parameters:**
- `block_id` (str): Block identifier ("persona", "user_info", etc.)
- `content` (str): New content for the block
- `reasoning` (str): Reasoning for the update (default: "")

**Returns:**
- True if update was successful, False otherwise

**Example:**
```python
memory.update_core_memory(
    "persona",
    "I am a Python expert assistant specialized in data science",
    "Updated based on user interactions showing data science focus"
)
```

##### `get_user_profile(user_id: Optional[str] = None) -> Dict`
Get user profile information.

**Parameters:**
- `user_id` (str, optional): User ID (uses current user if not specified)

**Returns:**
- Dictionary with user profile data

**Example:**
```python
profile = memory.get_user_profile("alice")
# Returns: {"user_id": "alice", "relationship": "owner", "facts": [...]}
```

##### `consolidate_memories() -> Dict[str, int]`
Consolidate working memory to long-term storage.

**Returns:**
- Dictionary with consolidation statistics

**Example:**
```python
stats = memory.consolidate_memories()
# Returns: {"promoted_to_semantic": 3, "moved_to_episodic": 7}
```

#### Memory Component Access

##### Core Memory
```python
# Access core memory directly
core_context = memory.core.get_context()
blocks = memory.core.get_all_blocks()
```

##### Semantic Memory
```python
# Query validated facts
facts = memory.semantic.retrieve("Python programming", limit=5)
concept_network = memory.semantic.get_concept_network("programming")
```

##### Working Memory
```python
# Access recent context
recent_items = memory.working.get_recent_items(10)
working_context = memory.working.get_context()
```

##### Episodic Memory
```python
# Query episodes
episodes = memory.episodic.retrieve("machine learning")
time_episodes = memory.episodic.retrieve_by_timeframe(start_time, end_time)
```

##### Temporal Knowledge Graph
```python
# Query knowledge at specific time
facts_at_time = memory.kg.query_at_time("works_at", datetime.now())
entity_evolution = memory.kg.get_entity_evolution("alice", start_time, end_time)
```

## 🔧 Memory Components (Advanced)

### CoreMemory

Self-editing memory blocks for agent identity.

```python
class CoreMemory(IMemoryComponent):
    def update_block(self, block_id: str, content: str, reasoning: str = "") -> bool
    def get_context(self) -> str
    def get_all_blocks() -> Dict[str, Block]
```

### SemanticMemory

Validated facts and knowledge storage.

```python
class SemanticMemory(IMemoryComponent):
    def __init__(self, validation_threshold: int = 3)
    def add(self, item: MemoryItem) -> str
    def retrieve(self, query: str, limit: int = 10) -> List[MemoryItem]
    def consolidate(self) -> int
    def get_concept_network(self, concept: str) -> Dict[str, Set[str]]
```

### WorkingMemory

Sliding window memory for recent context.

```python
class WorkingMemory(IMemoryComponent):
    def __init__(self, capacity: int = 10)
    def add(self, item: MemoryItem) -> str
    def retrieve(self, query: str, limit: int = 10) -> List[MemoryItem]
    def get_recent_items(self, limit: int = None) -> List[MemoryItem]
    def consolidate(self) -> int
```

### EpisodicMemory

Long-term event archive with temporal organization.

```python
class EpisodicMemory(IMemoryComponent):
    def add(self, item: MemoryItem) -> str
    def retrieve(self, query: str, limit: int = 10) -> List[MemoryItem]
    def retrieve_by_timeframe(self, start: datetime, end: datetime) -> List[MemoryItem]
    def retrieve_by_user(self, user_id: str) -> List[MemoryItem]
    def consolidate(self) -> int
```

### TemporalKnowledgeGraph

Bi-temporal knowledge representation with contradiction handling.

```python
class TemporalKnowledgeGraph:
    def add_entity(self, value: str, entity_type: str = 'entity') -> str
    def add_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        event_time: datetime,
        confidence: float = 1.0,
        source: Optional[str] = None,
        ingestion_time: Optional[datetime] = None
    ) -> str
    def query_at_time(self, query: str, point_in_time: datetime) -> List[Dict[str, Any]]
    def get_entity_evolution(self, entity: str, start: datetime, end: datetime) -> List[Dict[str, Any]]
```

## 🔍 Temporal Data Structures

### GroundingAnchor

Temporal grounding for memory items.

```python
@dataclass
class GroundingAnchor:
    event_time: datetime              # When it actually happened
    ingestion_time: datetime          # When we learned about it
    validity_span: TemporalSpan      # When it was/is valid
    relational: RelationalContext    # User, agent, relationship context
    confidence: float = 1.0          # Confidence level
    source: Optional[str] = None     # Information source
    location: Optional[str] = None   # Spatial context
```

### TemporalSpan

Time span for fact validity.

```python
@dataclass
class TemporalSpan:
    start: datetime                   # Span start time
    end: Optional[datetime] = None    # Span end time (None = ongoing)
    valid: bool = True               # Whether span is currently valid
```

### RelationalContext

Relational grounding for multi-user scenarios.

```python
@dataclass
class RelationalContext:
    user_id: str                     # User identifier
    relationship: str = "user"       # Relationship type
    session_id: Optional[str] = None # Session identifier
    group_id: Optional[str] = None   # Group context
```

## ⚙️ Configuration Examples

### Development Configuration
```python
# Lightweight development setup
memory = create_memory(
    "grounded",
    working_capacity=5,           # Small capacity for testing
    semantic_threshold=2,         # Lower threshold for faster validation
    core_update_threshold=3,      # Faster core updates
    enable_kg=False              # Disable KG for simpler testing
)
```

### Production Configuration
```python
# Production setup with full capabilities
memory = create_memory(
    "grounded",
    working_capacity=20,          # Larger working memory
    semantic_threshold=3,         # Standard validation threshold
    core_update_threshold=5,      # Conservative core updates
    enable_kg=True               # Full knowledge graph
)
```

### High-Volume Configuration
```python
# High-volume usage optimization
memory = create_memory(
    "grounded",
    working_capacity=30,          # Large working memory
    semantic_threshold=5,         # Higher validation bar
    core_update_threshold=10,     # Very conservative core updates
    enable_kg=True               # Knowledge graph for patterns
)
```

## 🚨 Error Handling

### Common Exceptions

```python
from abstractmemory.exceptions import (
    MemoryCapacityError,     # Memory capacity exceeded
    InvalidUserError,        # Invalid user ID or context
    MemoryItemError,         # Invalid memory item
    ValidationError          # Validation failure
)

try:
    memory.add_interaction(user_input, response)
except MemoryCapacityError as e:
    # Handle capacity issues
    memory.consolidate_memories()
    memory.add_interaction(user_input, response)
except InvalidUserError as e:
    # Handle user context issues
    memory.set_current_user(valid_user_id)
    memory.add_interaction(user_input, response)
```

### Validation

```python
# Validate memory item before adding
def validate_memory_item(item: MemoryItem) -> bool:
    if not item.content:
        return False
    if item.confidence < 0.0 or item.confidence > 1.0:
        return False
    if item.event_time > datetime.now():
        return False  # No future events
    return True

# Safe memory addition
if validate_memory_item(item):
    memory.semantic.add(item)
```

## 📊 Performance Guidelines

### Operation Complexity

| Operation | Simple Memory | Complex Memory | Notes |
|-----------|--------------|----------------|-------|
| Add item | O(1) | O(log n) | Simple append vs. indexing |
| Retrieve | O(n) | O(log n) | Linear scan vs. indexed search |
| Context generation | O(n) | O(k) | Where k = context size |
| Consolidation | N/A | O(n log n) | Sorting and merging |

### Memory Usage Guidelines

```python
# Monitor memory usage
import psutil
import time

def monitor_memory_operation(operation_func):
    start_memory = psutil.Process().memory_info().rss
    start_time = time.time()

    result = operation_func()

    end_time = time.time()
    end_memory = psutil.Process().memory_info().rss

    print(f"Operation took {end_time - start_time:.3f}s")
    print(f"Memory delta: {(end_memory - start_memory) / 1024 / 1024:.2f} MB")

    return result

# Usage
result = monitor_memory_operation(
    lambda: memory.get_full_context("complex query")
)
```

This API reference provides comprehensive documentation for all AbstractMemory components. Use it as a reference while building your intelligent agents with persistent, grounded memory capabilities.