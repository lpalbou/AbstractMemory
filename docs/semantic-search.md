# Semantic Search with AbstractMemory

AbstractMemory now provides powerful semantic search capabilities through integration with AbstractCore's EmbeddingManager, enabling AI agents to find contextually relevant information beyond simple keyword matching.

## Overview

Semantic search allows AbstractMemory to understand the *meaning* behind queries, not just exact word matches. This enables more intelligent memory retrieval for AI agents.

### Key Features

- **Real Embeddings**: Uses AbstractCore's state-of-the-art EmbeddingManager with EmbeddingGemma model
- **Vector Similarity**: Finds semantically similar content even without keyword overlap
- **Hybrid Search**: Combines vector similarity with SQL filtering for precision
- **Multiple Storage Backends**: Works with both LanceDB (vector search) and markdown (text search)
- **Embedding Consistency**: Automatic validation and warnings to maintain search quality over time

⚠️  **CRITICAL ARCHITECTURE NOTE**:
- **LLM Providers** (text generation): You can change freely between Anthropic, OpenAI, Ollama, etc.
- **Embedding Providers** (semantic search): Must remain consistent within a storage space
- **Embedding models** create incompatible vector spaces - switching breaks semantic search

## Quick Start

### Basic Usage

```python
import sys
sys.path.insert(0, '/path/to/abstractllm_core')  # Until package integration complete
from abstractllm.embeddings import EmbeddingManager
from abstractmemory import create_memory

# Create SEPARATE providers for different purposes
llm_provider = create_llm("anthropic")  # For text generation
embedding_provider = EmbeddingManager()  # For semantic search

# Create memory with semantic search
memory = create_memory(
    "grounded",
    storage_backend="lancedb",
    storage_uri="./memory.db",
    embedding_provider=embedding_provider,  # Dedicated embedding provider
    working_capacity=10
)

# Your LLM provider is separate - you can change it freely
response = llm_provider.generate("Some query", system_prompt=context)

# Add interactions
memory.set_current_user("alice")
memory.add_interaction(
    "I'm working on machine learning models",
    "That's exciting! What type of models?"
)
memory.add_interaction(
    "Python is my favorite programming language",
    "Python is great for AI development!"
)

# Semantic search finds related content
results = memory.search_stored_interactions("artificial intelligence")
# Finds the ML interaction even though "AI" wasn't mentioned exactly

results = memory.search_stored_interactions("coding")
# Finds the Python interaction through semantic similarity
```

### Dual Storage with Observability

```python
# Get both semantic search AND observable files
memory = create_memory(
    "grounded",
    storage_backend="dual",
    storage_path="./memory_files",      # Human-readable markdown
    storage_uri="./memory_vector.db",   # Vector search database
    embedding_provider=embedding_manager
)

# All interactions stored in both formats:
# 1. Markdown files for transparency
# 2. Vector database for semantic search
```

## How It Works

### 1. Embedding Generation Timing

**⏰ WHEN Embeddings Are Generated:**

Embeddings are generated **IMMEDIATELY** when content is added to memory:

```python
# Embedding generated RIGHT NOW during this call
memory.add_interaction(
    "I love machine learning",
    "Great topic!"
)
# ↳ EmbeddingManager.embed() called synchronously
# ↳ 768D vector generated and stored instantly
# ↳ Both user input + agent response embedded together
```

**📋 Embedding Generation Process:**

1. **Immediate Generation**: No lazy loading - embeddings created during `add_interaction()`
2. **Synchronous Operation**: Call blocks until embedding is generated (~36ms)
3. **Dual Text Processing**: User input + agent response combined into single embedding
4. **Automatic Storage**: Vector immediately stored in LanceDB alongside verbatim text
5. **Cache Integration**: EmbeddingManager caches results for identical text

**🔄 No Manual Triggering Required:**

- ❌ **No batch processing** - each interaction embedded individually
- ❌ **No manual indexing** - completely automatic
- ❌ **No lazy loading** - embeddings ready immediately for search
- ✅ **Real-time availability** - searchable the moment it's added

### 2. Technical Implementation Details

**📊 Exact Flow When Adding Interactions:**

```python
memory.add_interaction("I love ML", "Great!")
# ↓
# 1. GroundedMemory.add_interaction() called
# 2. Creates MemoryItem objects for working memory
# 3. Calls storage_manager.save_interaction()
# 4. DualStorageManager saves to both:
#    └─ MarkdownStorage: writes verbatim .md file
#    └─ LanceDBStorage: calls embedding generation
# 5. LanceDBStorage._generate_embedding() calls:
#    └─ EmbeddingAdapter.generate_embedding()
#    └─ EmbeddingManager.embed("I love ML Great!")
# 6. 768D vector generated (~36ms)
# 7. Vector + text stored in LanceDB table row
# 8. Function returns - interaction immediately searchable
```

**🔍 Exact Flow When Searching:**

```python
results = memory.search_stored_interactions("artificial intelligence")
# ↓
# 1. Call reaches LanceDBStorage.search_interactions()
# 2. Query embedding generated: EmbeddingManager.embed("artificial intelligence")
# 3. Vector search: table.search(query_embedding, vector_column_name="embedding")
# 4. SQL filters applied (user_id, date_range if specified)
# 5. Results ranked by cosine similarity
# 6. Converted to dictionaries and returned (~100ms total)
```

### 3. Semantic Search Process

When you search stored interactions:

```python
results = memory.search_stored_interactions("machine learning", user_id="alice")
```

The system:

1. **Generates query embedding** for "machine learning" (immediate)
2. **Performs vector similarity search** in LanceDB with proper vector column
3. **Applies user/date filters** if specified via SQL WHERE clauses
4. **Ranks results by cosine similarity** of embedding vectors
5. **Returns structured results** with metadata and similarity scores

### 3. Search Modes

| Storage Backend | Search Capability | Performance | Use Case |
|----------------|-------------------|-------------|----------|
| `lancedb` | Vector + SQL + Text | Fast | Production semantic search |
| `markdown` | Text-based only | Medium | Development, transparency |
| `dual` | Vector + SQL + Text + Files | Fast + Observable | Best of both worlds |

## Advanced Usage

### Custom Search Parameters

```python
# Search with filters
results = memory.search_stored_interactions(
    query="neural networks",
    user_id="alice",                    # Filter by user
    start_date=datetime(2024, 1, 1),    # Date range
    end_date=datetime(2024, 12, 31)
)

# Search across all users
all_results = memory.search_stored_interactions("programming concepts")
```

### Embedding Information

```python
# Check embedding provider status
if hasattr(memory, 'storage_manager') and hasattr(memory.storage_manager, 'lancedb_storage'):
    storage = memory.storage_manager.lancedb_storage
    adapter = storage.embedding_adapter

    print(f"Provider type: {adapter.provider_type}")
    print(f"Embedding dimension: {adapter.embedding_dimension}")
    print(f"Real embeddings: {adapter.is_real_embedding()}")

    # Get embedding info
    info = adapter.get_embedding_info()
    print(f"Embedding info: {info}")
```

## Configuration Options

### EmbeddingManager Configuration

```python
from abstractllm.embeddings import EmbeddingManager

# Default configuration (EmbeddingGemma)
em = EmbeddingManager()

# Custom model
em = EmbeddingManager(
    model="stella-400m",        # Alternative model
    backend="onnx",             # ONNX for speed
    cache_size=2000,            # Larger cache
    output_dims=384             # Matryoshka truncation
)

# Custom HuggingFace model
em = EmbeddingManager(
    model="sentence-transformers/all-MiniLM-L6-v2",
    trust_remote_code=False
)
```

### Storage Configuration

```python
# LanceDB only (best performance)
memory = create_memory(
    "grounded",
    storage_backend="lancedb",
    storage_uri="./memory.db",
    embedding_provider=embedding_manager
)

# Dual storage (performance + observability)
memory = create_memory(
    "grounded",
    storage_backend="dual",
    storage_path="./memory_files",
    storage_uri="./memory_vector.db",
    embedding_provider=embedding_manager
)

# Markdown only (no semantic search, but observable)
memory = create_memory(
    "grounded",
    storage_backend="markdown",
    storage_path="./memory_files"
    # No embedding_provider needed
)
```

## Performance Characteristics

### ⏰ Embedding Generation Timing (IMMEDIATE INDEXING)

**Real-World Performance:**

```python
# First embedding (includes model loading)
start = time.time()
memory.add_interaction("Hello world", "Hi there!")
# Takes ~300ms (model loading + embedding generation)

# Subsequent embeddings (model cached)
memory.add_interaction("How are you?", "I'm good!")
# Takes ~36ms (just embedding generation)

# Identical text (cached)
memory.add_interaction("Hello world", "Hi there!")
# Takes ~5ms (cache hit)
```

**📊 Performance Breakdown:**
- **Model Loading**: 200-250ms (first call only)
- **Embedding Generation**: 10-50ms per interaction
- **LanceDB Storage**: 5-15ms per row
- **Total Add Time**: 36ms average (after model loaded)
- **Cache Hit Time**: <5ms for identical text

**⚠️ Performance Implications:**

1. **Synchronous Blocking**: Each `add_interaction()` blocks until embedding complete
2. **Model Memory**: EmbeddingManager uses ~1-2GB RAM when loaded
3. **CPU Usage**: Embedding generation is CPU-intensive (~100% for 36ms)
4. **No Queuing**: Each interaction processed individually, not batched
5. **Real-Time Cost**: 36ms latency added to every interaction save

### 🔍 Search Performance

- **Vector search**: ~10-100ms depending on database size
- **Query embedding**: ~10-30ms (same as storage embedding)
- **Hybrid search**: ~20-150ms (vector + SQL filters)
- **Memory usage**: ~1-2GB for EmbeddingManager (model in memory)
- **No text fallback**: Pure vector search, no degradation

### 💾 Storage Space

- **Embeddings**: ~3KB per interaction (768 floats)
- **Markdown files**: ~1-5KB per interaction (human-readable)
- **LanceDB**: Compressed vector storage
- **Dual storage**: ~4-8KB per interaction total

## Troubleshooting

### Common Issues

**1. No results found**
```python
# Check if embeddings are working
results = memory.search_stored_interactions("test query")
if not results:
    # Try without user filter
    results = memory.search_stored_interactions("test query", user_id=None)

    # Check storage stats
    stats = memory.storage_manager.get_stats()
    print(f"Total interactions: {stats['total_interactions']}")
```

**2. "No module named 'abstractllm.embeddings'"**
```bash
# Make sure AbstractCore is installed with embeddings
pip install abstractcore>=2.1.0

# Or use development version
pip install -e /path/to/abstractllm_core
```

**3. Slow embedding generation**
```python
# Install ONNX for 2-3x faster inference
pip install optimum[onnxruntime]

# Use smaller model for speed
em = EmbeddingManager(model="nomic-embed", backend="onnx")
```

### Debug Mode

```python
import logging
logging.getLogger('abstractmemory').setLevel(logging.DEBUG)

# This will show:
# - Embedding generation times
# - Search query details
# - Storage operations
# - Fallback activations
```

## Semantic Search Examples

### Example 1: Code Help Assistant

```python
memory.add_interaction(
    "How do I iterate through a Python list?",
    "Use a for loop: for item in my_list: print(item)"
)

memory.add_interaction(
    "What's the difference between lists and tuples?",
    "Lists are mutable, tuples are immutable..."
)

# Semantic search finds relevant programming help
results = memory.search_stored_interactions("looping through arrays")
# Finds the list iteration answer

results = memory.search_stored_interactions("mutable vs immutable data structures")
# Finds the lists vs tuples explanation
```

### Example 2: Learning Assistant

```python
memory.add_interaction(
    "Explain backpropagation in neural networks",
    "Backpropagation is the algorithm used to train neural networks..."
)

memory.add_interaction(
    "What is gradient descent?",
    "Gradient descent is an optimization algorithm..."
)

# Student asks related questions with different terminology
results = memory.search_stored_interactions("how do neural nets learn")
# Finds backpropagation explanation

results = memory.search_stored_interactions("optimization in machine learning")
# Finds gradient descent explanation
```

### Example 3: Multi-User Context

```python
# Alice (data scientist)
memory.set_current_user("alice")
memory.add_interaction("I work with pandas dataframes", "Great for data analysis!")

# Bob (web developer)
memory.set_current_user("bob")
memory.add_interaction("I use React for frontend", "Excellent choice!")

# Search respects user context
alice_results = memory.search_stored_interactions("data processing", user_id="alice")
# Finds pandas context

bob_results = memory.search_stored_interactions("UI development", user_id="bob")
# Finds React context

# Cross-user search when needed
all_results = memory.search_stored_interactions("programming frameworks")
# Finds both pandas and React
```

## 🚨 Embedding Consistency: Critical for Production

### Why Consistency Matters

**The fundamental principle**: Different embedding models create **incompatible vector spaces**. Mixing them breaks semantic search entirely.

- **EmbeddingGemma (768D)** vectors cannot search **OpenAI (1536D)** vectors
- Even same-dimension models from different families are incompatible
- Changing models mid-deployment makes existing memories **unsearchable**

### Production Best Practices

#### ✅ **Recommended Approach**
```python
# 1. Choose your embedding provider ONCE
embedding_manager = EmbeddingManager()  # AbstractCore EmbeddingGemma

# 2. Use it consistently throughout system lifetime
memory = create_memory(
    "grounded",
    storage_backend="dual",
    storage_uri="./memory.db",
    embedding_provider=embedding_manager  # Same provider always
)

# 3. AbstractMemory automatically tracks model consistency
# It will warn you if model changes between sessions
```

#### ❌ **What NOT to Do**
```python
# DON'T switch between providers
memory1 = create_memory("grounded", embedding_provider=EmbeddingManager())  # EmbeddingGemma
# Later...
memory2 = create_memory("grounded", embedding_provider=openai_client)       # OpenAI - BREAKS SEARCH!
```

### Consistency Enforcement

AbstractMemory now **automatically enforces** embedding consistency:

1. **Stores Model Metadata**: First-time initialization stores embedding model info
2. **Validates on Startup**: Subsequent startups check for model changes
3. **Issues Warnings**: Clear warnings when model inconsistency detected
4. **No Hash Fallbacks**: No misleading "graceful degradation" to meaningless hash vectors

### Migration Strategies

If you **must** change embedding models:

#### Option 1: Clean Slate (Recommended)
```bash
# Delete existing vector database
rm -rf ./memory.db

# Start fresh with new embedding model
# All previous interactions will be re-embedded with new model
```

#### Option 2: Dual Deployment
```python
# Keep old system running
memory_old = create_memory("grounded", storage_uri="./memory_old.db", embedding_provider=old_provider)

# Start new system alongside
memory_new = create_memory("grounded", storage_uri="./memory_new.db", embedding_provider=new_provider)

# Gradually migrate interactions
```

### Error Messages You Might See

```
⚠️  EMBEDDING CONSISTENCY WARNING ⚠️
You are using a different embedding model than previously stored vectors.
This will make your existing stored interactions unsearchable via semantic search.

Current model: {'provider_type': 'openai', 'dimension': 1536, 'model_name': 'text-embedding-3-small'}
Previously stored: {'provider_type': 'abstractcore_embeddings', 'dimension': 768, 'model_name': 'EmbeddingGemma'}

To maintain semantic search capabilities, you should either:
1. Use the same embedding model as before, OR
2. Re-generate all embeddings with the new model (requires recreating your vector database)

For production systems, embedding model consistency is critical.
```

## Future Enhancements

1. **Reranking**: Use cross-encoders for more accurate results
2. **Hybrid Scoring**: Combine vector similarity with keyword matching
3. **Query Expansion**: Automatically expand queries with related terms
4. **Fine-tuned Models**: Domain-specific embedding models
5. **Semantic Clustering**: Group related memories automatically
6. **Migration Tools**: Automated embedding model migration utilities

## Integration with AbstractLLM Ecosystem

### With AbstractAgent (Future)

```python
# Agents will automatically use semantic memory
from abstractagent import create_agent

agent = create_agent(
    "autonomous",
    memory=memory,  # Memory with semantic search
    provider=llm_provider
)

# Agent reasoning benefits from semantic memory retrieval
response = agent.execute("Help me with machine learning", user_id="alice")
# Agent finds all relevant ML conversations automatically
```

### With AbstractCore Providers

```python
# Use same provider for both LLM and embeddings
from abstractllm import create_llm

llm_provider = create_llm("anthropic", model="claude-3-5-haiku-latest")
embedding_provider = EmbeddingManager()  # Separate for now

# Future: unified provider
# provider = create_llm("anthropic", model="claude-3-5-haiku", embedding_model="claude-embed")
```

## Conclusion

Semantic search transforms AbstractMemory from simple storage to intelligent memory that understands meaning and context. This enables AI agents to:

- **Find relevant information** even with different terminology
- **Build on previous conversations** more effectively
- **Provide personalized responses** based on user history
- **Learn from experience** through semantic connections

The integration with AbstractCore's EmbeddingManager provides production-ready performance with state-of-the-art models, making semantic search practical for real AI applications.