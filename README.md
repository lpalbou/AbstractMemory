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

**👉 [START HERE: Complete Documentation Guide](docs/README.md)**

### Core Guides
- **[🚀 Quick Start](docs/README.md#-start-here)** - Get running in 5 minutes
- **[🔍 Semantic Search](docs/semantic-search.md)** - Vector embeddings and similarity search
- **[🧠 Memory Types](docs/memory-types.md)** - ScratchpadMemory, BufferMemory, GroundedMemory
- **[📊 Performance Guide](docs/semantic-search.md#performance-characteristics)** - Embedding timing and optimization

### Advanced Topics
- **[🏗️ Architecture](docs/architecture.md)** - System design and two-tier strategy
- **[💾 Storage Systems](docs/storage-systems.md)** - Markdown + LanceDB dual storage
- **[🎯 Usage Patterns](docs/usage-patterns.md)** - Real-world examples and best practices
- **[🔗 Integration Guide](docs/integration.md)** - AbstractLLM ecosystem integration
- **[📖 API Reference](docs/api-reference.md)** - Complete method documentation

## 🔬 Key Features

### ✅ Purpose-Built Memory Types
- **ScratchpadMemory**: ReAct thought-action-observation cycles for task agents
- **BufferMemory**: Simple conversation history with capacity limits
- **GroundedMemory**: Four-tier architecture with semantic search and temporal context

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

### ✅ Semantic Search with AbstractCore
- **🎯 Real Embeddings**: Uses AbstractCore's EmbeddingManager with Google's EmbeddingGemma (768D)
- **⚡ Immediate Indexing**: Embeddings generated instantly during `add_interaction()` (~36ms)
- **🔍 Vector Similarity**: True semantic search finds contextually relevant content
- **🗄️ Dual Storage**: Observable markdown files + searchable LanceDB vectors
- **🎯 Production Ready**: Sub-second search, proven with 200+ real implementation tests

## 🧪 Testing & Validation

AbstractMemory includes **200+ comprehensive tests** using ONLY real implementations:

```bash
# Run all tests (NO MOCKS - only real implementations)
python -m pytest tests/ -v

# Run specific test suites
python -m pytest tests/simple/ -v          # Simple memory types
python -m pytest tests/components/ -v      # Memory components
python -m pytest tests/storage/ -v         # Storage system tests
python -m pytest tests/integration/ -v     # Full system integration

# Test with real LLM providers (requires AbstractCore)
python -m pytest tests/integration/test_llm_real_usage.py -v

# Test comprehensive dual storage with real embeddings
python -m pytest tests/storage/test_dual_storage_comprehensive.py -v
```

**IMPORTANT**: All tests use real implementations:
- Real embedding providers (AbstractCore EmbeddingManager)
- Real LLM providers (Anthropic, OpenAI, Ollama via AbstractCore)
- Real memory components and storage systems
- NO MOCKS anywhere in the codebase

## 🚀 Quick Start

### Installation

```bash
# Install with semantic search capabilities (recommended)
pip install abstractmemory[embeddings]

# Or install everything
pip install abstractmemory[all]

# Basic memory only (no semantic search)
pip install abstractmemory
```

### 📋 Upgrading from v0.1.0?

**Version 0.2.0 adds semantic search!** See [Migration Guide](CHANGELOG.md#-migration-guide) for:
- New AbstractCore dependency (`pip install abstractcore>=2.1.0`)
- LanceDB schema changes (recreate `.db` files)
- New `embedding_provider` parameter

### ⚠️  Critical: LLM vs Embedding Provider Separation

**Understanding the difference between LLM and Embedding providers:**

- 🔄 **LLM Providers** (text generation): Change freely between Anthropic, OpenAI, Ollama, etc.
- 🔒 **Embedding Providers** (semantic search): Must remain consistent within a storage space

**For semantic search consistency:**
- ✅ **Choose ONE embedding model and stick with it per storage space**
- ✅ **You can customize which embedding model to use (AbstractCore, OpenAI, Ollama, etc.)**
- ❌ **Don't change embedding models mid-project - it breaks vector search**
- 🚨 **AbstractMemory automatically warns when embedding model changes detected**

**Example of correct separation:**
```python
# LLM for text generation (can change anytime)
llm = create_llm("anthropic")  # or "openai", "ollama", etc.

# Dedicated embedding provider (must stay consistent)
embedder = EmbeddingManager()  # AbstractCore embeddings

memory = create_memory("grounded", embedding_provider=embedder)  # NOT llm!
```

### Basic Usage

```python
from abstractllm.embeddings import EmbeddingManager
from abstractmemory import create_memory

# 1. Create embedding manager for semantic search
em = EmbeddingManager()  # Uses EmbeddingGemma (768D vectors)

# 2. Create memory with dual storage
memory = create_memory(
    "grounded",
    storage_backend="dual",           # Markdown + LanceDB
    storage_path="./memory_files",    # Observable files
    storage_uri="./memory.db",        # Vector search
    embedding_provider=em             # Real embeddings
)

# 3. Add interactions (embeddings generated immediately!)
memory.set_current_user("alice")
memory.add_interaction(
    "I'm working on machine learning projects",
    "Great! ML has amazing applications in many fields."
)
# ↳ Takes ~36ms: embedding generated and stored instantly

# 4. Semantic search finds contextually relevant content
results = memory.search_stored_interactions("artificial intelligence research")
# ↳ Finds ML interaction via semantic similarity (not keywords!)
print(f"Found {len(results)} relevant conversations")
```

### 📋 What Happens When You Add Interactions

```python
memory.add_interaction("I love Python", "Great choice!")
# ↓ IMMEDIATE PROCESSING:
# 1. Text combined: "I love Python Great choice!"
# 2. EmbeddingManager.embed() called (36ms)
# 3. 768D vector generated with EmbeddingGemma
# 4. Saved to markdown file: ./memory_files/verbatim/alice/...
# 5. Stored in LanceDB: vector + text + metadata
# 6. Interaction immediately searchable via semantic similarity
```

## 🔗 AbstractLLM Ecosystem Integration

AbstractMemory seamlessly integrates with AbstractCore, maintaining clear separation between LLM and embedding providers:

### Critical Architecture: LLM vs Embedding Separation
```python
from abstractllm import create_llm
from abstractllm.embeddings import EmbeddingManager
from abstractmemory import create_memory

# SEPARATE PROVIDERS for different purposes:

# 1. LLM Provider - for TEXT GENERATION (can change freely)
llm_provider = create_llm("anthropic", model="claude-3-5-haiku-latest")

# 2. Embedding Provider - for SEMANTIC SEARCH (must stay consistent)
embedding_provider = EmbeddingManager()

# Create memory with DEDICATED embedding provider
memory = create_memory(
    "grounded",
    enable_kg=True,
    storage_backend="dual",
    storage_path="./memory",
    storage_uri="./memory.db",
    embedding_provider=embedding_provider  # DEDICATED for embeddings
)

# Use in agent reasoning with CLEAR separation
context = memory.get_full_context(query)
response = llm_provider.generate(prompt, system_prompt=context)  # LLM for text
memory.add_interaction(query, response.content)  # Embeddings handled internally

# Search uses embedding provider for semantic similarity
similar_memories = memory.search_stored_interactions("related concepts")
```

### Key Points:
- **LLM Provider**: Change freely between Anthropic ↔ OpenAI ↔ Ollama
- **Embedding Provider**: Must remain consistent within storage space
- **Never** pass LLM provider as embedding provider
- **Always** use dedicated embedding provider for semantic search

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
2. **Real Implementation Testing**: NO MOCKS anywhere - all tests use real implementations
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