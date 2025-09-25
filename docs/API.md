# AbstractMemory: API Reference

**Quick reference for all MemorySession methods and configurations**

See [GUIDE.md](GUIDE.md) for usage examples and [ARCHITECTURE.md](ARCHITECTURE.md) for technical details.

## MemorySession

### Constructor

```python
MemorySession(
    provider,                                    # LLM provider (required)
    memory_config: Optional[Dict[str, Any]] = None,    # Storage configuration
    default_memory_config: Optional[MemoryConfig] = None,  # Memory behavior
    embedding_provider: Optional[Any] = None,   # Embedding provider (auto-configured if storage enabled)
    system_prompt: Optional[str] = None         # Base system prompt
)
```

### Core Methods

```python
# Generate with memory context
generate(
    prompt: str,
    user_id: Optional[str] = None,
    include_memory: bool = True,
    max_memory_items: int = 10,
    memory_config: Optional[MemoryConfig] = None,
    **kwargs
) -> Union[Any, Iterator[Any]]

# Get memory context without generating
get_memory_context(
    query: str,
    user_id: Optional[str] = None,
    memory_config: Optional[MemoryConfig] = None
) -> str

# Search stored memories
search_memory(
    query: str,
    user_id: Optional[str] = None,
    limit: int = 5
) -> List[Dict]

# Learn facts about users
learn_about_user(
    fact: str,
    user_id: Optional[str] = None
)

# Get user profile
get_user_profile(
    user_id: Optional[str] = None
) -> Dict[str, Any]
```

## MemoryConfig

### Preset Configurations

```python
# Minimal memory usage
MemoryConfig.minimal()

# Full memory capabilities
MemoryConfig.comprehensive()

# Agent with memory tools
MemoryConfig.agent_mode()
```

### Configuration Options

```python
MemoryConfig(
    # Memory tier inclusion
    include_user: bool = True,           # User profile information
    include_working: bool = True,        # Recent context
    include_semantic: bool = True,       # Learned facts
    include_episodic: bool = False,      # Historical events
    include_storage: bool = True,        # Stored interactions

    # Memory limits
    max_memory_items: int = 15,          # Total context items
    max_items_per_tier: Dict[str, int] = {
        'working': 5,
        'semantic': 3,
        'episodic': 3,
        'storage': 3
    },

    # Episodic formatting
    episodic_strategy: str = "summary",  # "verbatim", "summary", "semantic_summary"
    episodic_include_metadata: bool = True,

    # Agent tools
    enable_memory_tools: bool = False,   # Enable agent memory management
    enable_self_editing: bool = False,   # Allow core memory modification
    allowed_memory_operations: List[str] = [
        "search_memory",
        "remember_fact",
        "get_user_profile"
    ],

    # Performance
    compact_format: bool = False,        # Minimize token usage
    show_confidence: bool = True,        # Show memory confidence scores
    use_semantic_ranking: bool = True    # Better relevance scoring
)
```

## Storage Configuration

### Basic Storage

```python
memory_config = {
    "path": "./memory"                   # Storage location
}
# Auto-configures: dual storage + all-MiniLM-L6-v2 embeddings
```

### Advanced Storage

```python
memory_config = {
    "path": "./memory",                  # Base path
    "storage": "dual",                   # "markdown", "lancedb", "dual"
    "working_capacity": 15,              # Working memory size
    "enable_kg": True                    # Knowledge graph
}
```

## Memory Tools (Agent Mode)

When `enable_memory_tools=True`, agents automatically get:

### search_memory
```python
@tool("Search your memory for specific information")
def search_memory(
    query: str,
    user_id: Optional[str] = None,
    memory_types: Optional[List[str]] = None,
    limit: int = 5
) -> str
```

### remember_fact
```python
@tool("Remember an important fact for future reference")
def remember_fact(
    fact: str,
    user_id: Optional[str] = None
) -> str
```

### get_user_profile
```python
@tool("Get detailed profile information about a user")
def get_user_profile(
    user_id: Optional[str] = None
) -> str
```

### update_core_memory
```python
@tool("Update your core identity or persona")
def update_core_memory(
    block: str,          # "persona" or "user_info"
    content: str,        # New content
    reason: str = ""     # Explanation
) -> str
```

### get_recent_context
```python
@tool("Get recent working memory items")
def get_recent_context(
    limit: int = 10
) -> str
```

### get_semantic_facts
```python
@tool("Get validated semantic facts")
def get_semantic_facts(
    topic: Optional[str] = None,
    limit: int = 10
) -> str
```

## Migration from BasicSession

### Simple Replacement
```python
# Old
from abstractllm import BasicSession
session = BasicSession(provider)

# New
from abstractmemory import MemorySession
session = MemorySession(provider)
```

### Add Persistence
```python
# Add storage
session = MemorySession(
    provider,
    memory_config={"path": "./memory"}
)
```

### Enable Agent Tools
```python
from abstractmemory import MemoryConfig

config = MemoryConfig.agent_mode()
session = MemorySession(
    provider,
    default_memory_config=config
)
```

---

**Complete documentation:** [GUIDE.md](GUIDE.md) | **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) | **Overview:** [README.md](../README.md)