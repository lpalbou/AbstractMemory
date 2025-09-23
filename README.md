# AbstractMemory

**Intelligent memory system for LLM agents with two-tier architecture**

AbstractMemory provides efficient, purpose-built memory solutions for different types of LLM agents - from simple task-specific tools to sophisticated autonomous agents with persistent, grounded memory.

## 🎯 Project Goals

AbstractMemory is part of the **AbstractLLM ecosystem** refactoring, designed to power both simple and complex AI agents:

- **Simple agents** (ReAct, task tools) get lightweight, efficient memory
- **Autonomous agents** get sophisticated temporal memory with user tracking
- **No over-engineering** - memory complexity matches agent purpose

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     AbstractLLM Ecosystem                  │
├─────────────────┬─────────────────┬─────────────────────────┤
│  AbstractCore   │ AbstractMemory  │    AbstractAgent        │
│                 │                 │                         │
│ • LLM Providers │ • Simple Memory │ • ReAct Agents          │
│ • Sessions      │ • Complex Memory│ • Autonomous Agents     │
│ • Tools         │ • Temporal KG   │ • Multi-user Agents     │
└─────────────────┴─────────────────┴─────────────────────────┘
```

## 🧠 Two-Tier Memory Strategy

### Tier 1: Simple Memory (Task Agents)
Perfect for focused, single-purpose agents:

```python
from abstractmemory import create_memory

# ReAct agent memory
scratchpad = create_memory("scratchpad", max_entries=50)
scratchpad.add_thought("User wants to learn Python")
scratchpad.add_action("search", {"query": "Python tutorials"})
scratchpad.add_observation("Found great tutorials")

# Simple chatbot memory
buffer = create_memory("buffer", max_messages=100)
buffer.add_message("user", "Hello!")
buffer.add_message("assistant", "Hi there!")
```

### Tier 2: Complex Memory (Autonomous Agents)
For sophisticated agents with persistence and learning:

```python
# Autonomous agent with full memory capabilities
memory = create_memory("grounded", working_capacity=10, enable_kg=True)

# Multi-user context
memory.set_current_user("alice", relationship="owner")
memory.add_interaction("I love Python", "Python is excellent!")
memory.learn_about_user("Python developer")

# Get personalized context
context = memory.get_full_context("programming", user_id="alice")
```

## 🔧 Quick Start

### Installation

```bash
pip install abstractmemory

# For real LLM integration tests
pip install abstractmemory[llm]

# For LanceDB storage (optional)
pip install lancedb
```

### Basic Usage

```python
from abstractmemory import create_memory

# 1. Choose memory type based on agent purpose
memory = create_memory("scratchpad")  # Simple task agent
memory = create_memory("buffer")      # Simple chatbot
memory = create_memory("grounded")    # Autonomous agent

# 2. Use memory in your agent
if agent_type == "react":
    memory.add_thought("Planning the solution...")
    memory.add_action("execute", {"command": "analyze"})
    memory.add_observation("Analysis complete")

elif agent_type == "autonomous":
    memory.set_current_user("user123")
    memory.add_interaction(user_input, agent_response)
    context = memory.get_full_context(query)
```

### 🗂️ Persistent Storage Options

AbstractMemory now supports sophisticated storage for observable, searchable AI memory:

#### Observable Markdown Storage
Perfect for development, debugging, and transparency:

```python
# Human-readable, version-controllable AI memory
memory = create_memory(
    "grounded",
    storage_backend="markdown",
    storage_path="./memory"
)

# Generates organized structure:
# memory/
# ├── verbatim/alice/2025/09/24/10-30-45_python_int_abc123.md
# ├── experiential/2025/09/24/10-31-02_learning_note_def456.md
# ├── links/2025/09/24/int_abc123_to_note_def456.json
# └── index.json
```

#### Powerful Vector Search
High-performance search with AbstractCore embeddings:

```python
from abstractllm import create_llm

# Create provider with embedding support
provider = create_llm("openai", embedding_model="text-embedding-3-small")

# Vector search storage
memory = create_memory(
    "grounded",
    storage_backend="lancedb",
    storage_uri="./memory.db",
    embedding_provider=provider
)

# Semantic search across stored interactions
results = memory.search_stored_interactions("machine learning concepts")
```

#### Dual Storage - Best of Both Worlds
Complete observability with powerful search:

```python
# Dual storage: markdown (observable) + LanceDB (searchable)
memory = create_memory(
    "grounded",
    storage_backend="dual",
    storage_path="./memory",
    storage_uri="./memory.db",
    embedding_provider=provider
)

# Every interaction stored in both formats
# - Markdown files for complete transparency
# - Vector database for semantic search
```

## 📚 Documentation

- **[Architecture Guide](docs/architecture.md)** - Complete system design
- **[Memory Types](docs/memory-types.md)** - Detailed component guide
- **[Storage Systems](docs/storage-systems.md)** - Persistent storage with dual backends
- **[Usage Patterns](docs/usage-patterns.md)** - Real-world examples
- **[API Reference](docs/api-reference.md)** - Complete API documentation
- **[Integration Guide](docs/integration.md)** - AbstractLLM ecosystem integration
- **[AbstractCore Embedding Specs](docs/abstractcore-embedding-specs.md)** - Embedding integration requirements

## 🔬 Key Features

### ✅ Purpose-Built Memory Types
- **ScratchpadMemory**: ReAct thought-action-observation cycles
- **BufferMemory**: Simple conversation history
- **GroundedMemory**: Multi-dimensional temporal memory

### ✅ State-of-the-Art Research Integration
- **MemGPT/Letta Pattern**: Self-editing core memory
- **Temporal Grounding**: WHO (relational) + WHEN (temporal) context
- **Zep/Graphiti Architecture**: Bi-temporal knowledge graphs

### ✅ Four-Tier Memory Architecture (Autonomous Agents)
```
Core Memory ──→ Semantic Memory ──→ Working Memory ──→ Episodic Memory
   (Identity)     (Validated Facts)    (Recent Context)   (Event Archive)
```

### ✅ Learning Capabilities
- **Failure/Success Tracking**: Learn from experience
- **User Personalization**: Multi-user context separation
- **Fact Validation**: Confidence-based knowledge consolidation

### ✅ Dual Storage Architecture
- **📄 Markdown Storage**: Human-readable, observable AI memory evolution
- **🔍 LanceDB Storage**: Vector search with SQL capabilities via AbstractCore
- **🔄 Dual Mode**: Best of both worlds - transparency + powerful search
- **🧠 AI Reflections**: Automatic experiential notes about interactions
- **🔗 Bidirectional Links**: Connect interactions to AI insights
- **📊 Search Capabilities**: Text-based and semantic similarity search

## 🧪 Testing & Validation

AbstractMemory includes **200+ comprehensive tests** with real implementations:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test suites
python -m pytest tests/simple/ -v          # Simple memory types
python -m pytest tests/components/ -v      # Memory components
python -m pytest tests/storage/ -v         # Storage system tests
python -m pytest tests/integration/ -v     # Full system integration

# Test with real LLM providers (requires AbstractCore)
python -m pytest tests/integration/test_llm_real_usage.py -v

# Test comprehensive dual storage serialization
python -m pytest tests/storage/test_dual_storage_comprehensive.py -v
```

## 🔗 AbstractLLM Ecosystem Integration

AbstractMemory seamlessly integrates with the broader ecosystem:

### With AbstractCore
```python
from abstractllm import create_llm
from abstractmemory import create_memory

# Create LLM provider
provider = create_llm("anthropic", model="claude-3-5-haiku-latest")

# Create memory with embedding integration
memory = create_memory(
    "grounded",
    enable_kg=True,
    storage_backend="dual",
    storage_path="./memory",
    storage_uri="./memory.db",
    embedding_provider=provider
)

# Use together in agent reasoning
context = memory.get_full_context(query)
response = provider.generate(prompt, system_prompt=context)
memory.add_interaction(query, response.content)

# Search stored memories with semantic similarity
similar_memories = memory.search_stored_interactions("related concepts")
```

### With AbstractAgent (Future)
```python
from abstractagent import create_agent
from abstractmemory import create_memory

# Autonomous agent with sophisticated memory
memory = create_memory("grounded", working_capacity=20)
agent = create_agent("autonomous", memory=memory, provider=provider)

# Agent automatically uses memory for consistency and personalization
response = agent.execute(task, user_id="alice")
```

## 🏛️ Architecture Principles

1. **No Over-Engineering**: Memory complexity matches agent requirements
2. **Real Implementation Testing**: No mocks - all tests use real implementations
3. **SOTA Research Foundation**: Built on proven patterns (MemGPT, Zep, Graphiti)
4. **Clean Abstractions**: Simple interfaces, powerful implementations
5. **Performance Optimized**: Fast operations for simple agents, scalable for complex ones

## 📈 Performance Characteristics

- **Simple Memory**: < 1ms operations, minimal overhead
- **Complex Memory**: < 100ms context generation, efficient consolidation
- **Scalability**: Handles thousands of memory items efficiently
- **Real LLM Integration**: Context + LLM calls complete in seconds

## 🤝 Contributing

AbstractMemory is part of the AbstractLLM ecosystem. See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## 📄 License

[License details]

---

**AbstractMemory: Smart memory for smart agents** 🧠✨