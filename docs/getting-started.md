# Getting Started with AbstractMemory

This guide will help you set up and start using AbstractMemory for memory-enhanced AI interactions.

## Prerequisites

- Python 3.9+
- AbstractCore library
- LanceDB for vector storage

## Installation

### 1. Install AbstractCore

```bash
# Install AbstractCore with embeddings support
pip install abstractcore[embeddings]
```

### 2. Install LanceDB

```bash
pip install lancedb
```

### 3. Install AbstractMemory

```bash
# Clone the repository
git clone https://github.com/yourusername/abstractmemory.git
cd abstractmemory

# Install in development mode
pip install -e .
```

## Basic Setup

### 1. Choose Your LLM Provider

AbstractMemory works with any AbstractCore-supported provider:

```python
from abstractllm import create_llm

# Recommended: Ollama with local model
llm = create_llm("ollama", model="qwen3-coder:30b")

# Or OpenAI
llm = create_llm("openai", model="gpt-4")

# Or Anthropic
llm = create_llm("anthropic", model="claude-3-5-sonnet")
```

### 2. Choose Your Session Implementation

AbstractMemory provides two session implementations:

#### Option A: Full-Featured Session (`session.py`)
Best for applications needing complete memory capabilities:

```python
from abstractmemory.memory_session import MemorySession

session = MemorySession(
    provider=llm,
    memory_base_path="./my_memory",
    default_user_id="alice"
)
```

#### Option B: Clean Integration (`memory_session.py`)  
Best for AbstractCore-focused applications:

```python
from abstractmemory.memory_session import MemorySession

session = MemorySession(
    provider=llm,
    memory_base_path="./my_memory",
    default_user_id="alice"
)
```

### 3. First Interaction

```python
# Start a conversation
response = session.generate("Hello! I'm interested in learning about machine learning.")
print(response.content)

# The memory system automatically:
# - Stores the interaction
# - Indexes it for future search
# - Begins building user profile
# - Initializes memory structure
```

## Using the CLI

For interactive use, AbstractMemory includes a full CLI:

```bash
# Basic usage
python memory_cli.py

# Custom settings
python memory_cli.py --memory-path ./alice_memory --name alice --provider ollama --model qwen3-coder:30b

# Debug mode
python memory_cli.py --debug
```

### CLI Features

- **Memory-enhanced conversations** - Each response builds on full memory context
- **Document loading** - Use `@filename.pdf` to load documents into library
- **Memory tools** - Use tools like `search_memories()` and `reflect_on()` in conversation
- **Background notifications** - See memory consolidation and fact extraction in real-time

## Memory Structure

After your first interaction, AbstractMemory creates this structure:

```
my_memory/
├── core/                    # Identity components (emerge over time)
│   ├── purpose.md          # Why the AI exists
│   ├── values.md           # What matters emotionally
│   ├── personality.md      # How the AI expresses itself
│   └── ...                 # 8 more components
├── working/                # Current focus
│   ├── current_context.md  # What's happening now
│   ├── current_tasks.md    # Active objectives
│   └── unresolved.md       # Open questions
├── episodic/               # Significant events
│   ├── key_moments.md      # Important turning points
│   └── key_discoveries.md  # Breakthrough insights
├── semantic/               # Knowledge evolution
│   ├── critical_insights.md # Transformative understanding
│   └── concepts.md         # Key concepts learned
├── library/                # Documents and external knowledge
│   └── documents/          # Full document storage
├── people/                 # User relationships
│   └── alice/              # Per-user profiles
├── notes/                  # AI's experiential notes
│   └── 2025/10/14/         # Daily organization
└── verbatim/               # Conversation records
    └── alice/              # Per-user conversations
```

## Configuration

### Memory Indexing

Create `.memory_index_config.json` in your memory directory:

```json
{
  "modules": {
    "notes": {"enabled": true, "auto_index": true},
    "verbatim": {"enabled": false, "auto_index": false},
    "library": {"enabled": true, "auto_index": true},
    "core": {"enabled": true, "auto_index": true}
  },
  "embedding_model": "all-minilm-l6-v2",
  "batch_size": 100
}
```

### Consolidation Schedule

Customize memory consolidation timing:

```python
session.consolidation_frequency = 10  # Every 10 interactions
```

## Verification

Check that everything is working:

```python
# Check memory statistics
stats = session.get_memory_statistics()
print(f"Total memories: {stats.get('total_memories', 0)}")

# Test memory tools
session.remember_fact(
    content="Alice is interested in machine learning",
    importance=0.8,
    emotion="curiosity",
    reason="Important for building relationship"
)

# Search memories
results = session.search_memories("machine learning", limit=5)
print(f"Found {len(results)} relevant memories")
```

## Next Steps

- Read [Architecture](architecture.md) to understand the system design
- Check [Capabilities](capabilities.md) to see what AbstractMemory can do
- Browse [Examples](examples.md) for more usage patterns
- See [Troubleshooting](troubleshooting.md) if you encounter issues

## Common Issues

### LanceDB Connection Errors
If you see LanceDB connection errors, ensure you have write permissions to your memory directory.

### Memory Not Persisting
Check that your `memory_base_path` directory is writable and not being cleared between sessions.

### Slow Performance
For large memory stores, consider adjusting the focus level in `reconstruct_context()` or disabling verbatim indexing.

For more detailed troubleshooting, see [Troubleshooting](troubleshooting.md).
