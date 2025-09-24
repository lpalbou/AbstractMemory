# AbstractMemory Documentation

**Welcome to AbstractMemory** - the intelligent memory system for LLM agents with semantic search capabilities.

## 🚀 Start Here

### New to AbstractMemory?
1. **[Quick Start](../README.md#-quick-start)** - Get running in 5 minutes
2. **[Architecture Overview](architecture.md)** - Understand the system design
3. **[Memory Types Guide](memory-types.md)** - Choose the right memory for your agent

### Want Semantic Search?
1. **[Semantic Search Guide](semantic-search.md)** - Complete embeddings integration guide
2. **[Installation](../README.md#installation)** - `pip install abstractmemory[embeddings]`
3. **[Performance Guide](semantic-search.md#performance-characteristics)** - Understand embedding timing

## 📚 Complete Documentation

### Core Concepts
- **[Architecture](architecture.md)** - System design and two-tier strategy
- **[Memory Types](memory-types.md)** - ScratchpadMemory, BufferMemory, GroundedMemory
- **[Usage Patterns](usage-patterns.md)** - Real-world examples and best practices

### Advanced Features
- **[Semantic Search](semantic-search.md)** - Vector embeddings and similarity search
- **[Storage Systems](storage-systems.md)** - Markdown + LanceDB dual storage
- **[API Reference](api-reference.md)** - Complete method documentation
- **[Integration Guide](integration.md)** - AbstractLLM ecosystem integration

### Technical Reference
- **[AbstractCore Embedding Specs](abstractcore-embedding-specs.md)** - Embedding provider requirements

## 🎯 Common Use Cases

### Choose Your Path

| **I want to...** | **Documentation** | **Code Example** |
|-------------------|-------------------|------------------|
| **Get started quickly** | [Quick Start](../README.md#-quick-start) | `create_memory("grounded")` |
| **Add semantic search** | [Semantic Search](semantic-search.md#quick-start) | `embedding_provider=EmbeddingManager()` |
| **Build a ReAct agent** | [Memory Types](memory-types.md#scratchpadmemory) | `create_memory("scratchpad")` |
| **Track user conversations** | [Usage Patterns](usage-patterns.md#personal-assistant) | Multi-user examples |
| **Store observable memory** | [Storage Systems](storage-systems.md#markdown-storage) | `storage_backend="markdown"` |
| **Scale for production** | [Performance Guide](semantic-search.md#performance-characteristics) | Benchmarks and optimization |

## ⚡ Quick Reference

### Installation Options
```bash
# Basic memory system
pip install abstractmemory

# With semantic search (recommended)
pip install abstractmemory[embeddings]

# Everything
pip install abstractmemory[all]
```

### Memory Types
```python
# Simple task agents
scratchpad = create_memory("scratchpad")  # ReAct cycles
buffer = create_memory("buffer")          # Conversation history

# Autonomous agents with semantic search
memory = create_memory(
    "grounded",
    embedding_provider=EmbeddingManager(),  # Real embeddings
    storage_backend="dual"                  # Markdown + vector
)
```

### Semantic Search
```python
# Immediate embedding generation (36ms)
memory.add_interaction("I love ML", "Great topic!")

# Vector similarity search (100ms)
results = memory.search_stored_interactions("machine learning")
```

## 🔍 Key Questions Answered

### **When are embeddings generated?**
→ **Immediately** during `add_interaction()` - no lazy loading, no manual triggering
→ See: [Semantic Search - Embedding Timing](semantic-search.md#1-embedding-generation-timing)

### **How fast is semantic search?**
→ **~36ms** to add, **~100ms** to search, **768D** vectors with EmbeddingGemma
→ See: [Performance Characteristics](semantic-search.md#performance-characteristics)

### **What's stored where?**
→ **Markdown files**: Verbatim text (observable), **LanceDB**: Vectors + metadata (searchable)
→ See: [Storage Systems Guide](storage-systems.md)

### **How do I migrate from 0.1.0?**
→ Update dependencies, recreate LanceDB files, add embedding provider
→ See: [CHANGELOG - Migration Guide](../CHANGELOG.md#-migration-guide)

## 🧪 Testing & Examples

### Comprehensive Test Suite
- **[Real Implementation Tests](../tests/integration/)** - No mocks, real LLMs and embeddings
- **[200+ Tests](../README.md#-testing--validation)** - Complete validation suite
- **[Performance Benchmarks](../tests/integration/test_final_vector_search_proof.py)** - Production readiness verified

### Example Applications
- **[Storage Demo](../examples/storage_demo.py)** - Dual storage with semantic search
- **[ReAct Agent Memory](usage-patterns.md#react-agent-scratchpad)** - Task agent examples
- **[Personal Assistant](usage-patterns.md#personal-assistant)** - Multi-user conversations

## 🤝 Contributing & Support

### Getting Help
- **[Issues](https://github.com/lpalbou/AbstractAgent/issues)** - Bug reports and feature requests
- **[Discussions](https://github.com/lpalbou/AbstractAgent/discussions)** - Community support

### Development
- **[Development Logs](devlogs/)** - Implementation history and decisions
- **[Test Examples](../tests/)** - How to write tests for AbstractMemory

---

## 🎯 Documentation Quality Standards

All AbstractMemory documentation follows these principles:

✅ **Actionable**: Every guide includes working code examples
✅ **Explicit**: Clear timing, performance, and behavior specifications
✅ **Tested**: Examples verified with real implementations
✅ **Concise**: Focused content, clear navigation
✅ **Complete**: From quick start to advanced configuration

**Last updated**: 2024-09-24 - v0.2.0 with semantic search integration