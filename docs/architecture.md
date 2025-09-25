# AbstractMemory: Technical Architecture

**Why AbstractMemory is designed the way it is**

## 🧠 Core Design Philosophy

### The Context Window Problem
Traditional AI is limited by context windows (~100k tokens). AbstractMemory solves this by implementing human-like memory:

- **Conscious Memory** = Active context (recent interactions)
- **Subconscious Memory** = Persistent storage (unlimited history)
- **Selective Recall** = Retrieve relevant memories when needed

### Memory as Human Consciousness
```
Human Memory              AbstractMemory Implementation
────────────────          ──────────────────────────────
Working Memory            → Core + Working Memory (always active)
Long-term Memory          → Semantic + Episodic Memory (selective)
Automatic Recall          → Context injection based on relevance
```

## 🏗️ Four-Tier Memory Architecture

### Tier Hierarchy & Purpose

| Tier | Purpose | Always Available | Persistence | Example |
|------|---------|------------------|-------------|---------|
| **Core** | Agent identity/persona | ✅ Yes (system prompt) | Permanent | "I specialize in Python development" |
| **Working** | Recent context | ✅ Yes | Session | Last 10-15 interactions |
| **Semantic** | Validated facts | ✅ Yes | Persistent | "Alice prefers FastAPI" (confidence ≥ 0.8) |
| **Episodic** | Historical events | ❌ Query-dependent | Persistent | "Yesterday Alice asked about databases" |

### Memory Flow & Consolidation

```
User Input → Working Memory → Semantic Memory (if validated)
     ↓              ↓              ↓
Storage ────→ Episodic Memory ←──────┘
     ↓              ↓
Vector Search ←─────┴─── Context Retrieval
```

**Validation Process:**
1. Facts start in Working Memory
2. Repeated mentions increase confidence
3. High confidence (≥0.8) → moves to Semantic Memory
4. All interactions archived in Episodic Memory

### Memory Injection Strategy (MemGPT Pattern)

**System Prompt Structure:**
```
[Base System Prompt]

=== AGENT IDENTITY ===
[Core Memory - Always Present]

=== MEMORY CONTEXT ===
[Selective Context Based on Query Relevance]
├─ User Profile (relationship, key facts)
├─ Recent Context (working memory)
├─ Learned Facts (semantic memory)
└─ Relevant Events (episodic memory)
```

**Why Core Memory is in System Prompt:**
- Agent identity must be persistent across all interactions
- Core memory shapes how the agent interprets everything
- System prompt is never truncated unlike regular context

## 🔍 Embedding Strategy & Consistency

### The Golden Rule: One Model Forever

**Critical Requirement:** Same embedding model for entire storage lifespan

```python
# ✅ CORRECT: Consistent embeddings
embedder = create_sentence_transformer_provider("all-MiniLM-L6-v2")
session = MemorySession(provider, embedding_provider=embedder)

# ❌ WRONG: Changing models breaks search
# Day 1: all-MiniLM-L6-v2
# Day 2: bge-base-en-v1.5  ← Vector space completely different!
```

### Recommended Model: all-MiniLM-L6-v2

**Why this model:**
- **Accuracy**: 100% P@5, R@5, F1 scores on AbstractMemory test suite
- **Performance**: 13ms embedding generation (vs 40ms for larger models)
- **Efficiency**: 384D vectors (vs 768D) = 50% storage savings
- **Balance**: Best accuracy/performance ratio

### LLM vs Embedding Provider Separation

```python
# Different purposes, different providers
llm_provider = create_llm("ollama", model="qwen3-coder:30b")      # Text generation
embedding_provider = create_sentence_transformer_provider(...)    # Semantic search

# LLM provider can change freely
# Embedding provider must stay consistent per storage
```

## 💾 Storage Architecture

### Storage Options Comparison

| Backend | Observable | Searchable | Performance | Use Case |
|---------|------------|------------|-------------|----------|
| **None** | ❌ | ❌ | Fastest (0ms) | Development/Testing |
| **Markdown** | ✅ | ❌ | Fast (~5ms) | Debugging/Transparency |
| **LanceDB** | ❌ | ✅ | Fast (~100ms) | Production Search |
| **Dual** | ✅ | ✅ | Good (~105ms) | **Recommended** |

### Dual Storage Benefits

**Markdown Storage (Observable):**
- Human-readable memory evolution
- Version controllable with git
- Perfect for debugging and transparency
- Organized by user/date/interaction type

**LanceDB Storage (Searchable):**
- Vector similarity search
- SQL-like querying capabilities
- Sub-second search across thousands of memories
- Automatic indexing and optimization

### Storage Structure
```
memory/
├── markdown/
│   ├── verbatim/alice/2025/09/25/10-30-45_python_abc123.md
│   ├── experiential/2025/09/25/10-31-02_learning_def456.md
│   └── links/2025/09/25/int_abc123_to_note_def456.json
└── vectors.db  (LanceDB vector storage)
```

## ⚡ Performance Characteristics

### Real-World Benchmarks
- **Memory Context Injection**: ~5ms (system prompt enhancement)
- **Fact Extraction**: ~2ms (pattern matching from user input)
- **Embedding Generation**: ~13ms (all-MiniLM-L6-v2 model)
- **Vector Search**: ~100ms (1000+ stored interactions)
- **Storage Write**: ~15ms (dual storage)

### Scalability Limits
- **Working Memory**: 10-15 items (context window management)
- **Semantic Facts**: No limit (confidence-based retrieval)
- **Episodic Events**: No limit (query-dependent retrieval)
- **Vector Storage**: 100K+ interactions tested

## 🤖 Autonomous Agent Integration

### Memory Tools Architecture

When `enable_memory_tools=True`, agents get:

```python
@tool("Search your memory for specific information")
def search_memory(query, user_id, memory_types, limit=5):
    # Cross-tier search with relevance ranking

@tool("Remember an important fact")
def remember_fact(fact, user_id):
    # Direct injection into semantic memory

@tool("Update your core identity")
def update_core_memory(block, content, reason):
    # Permanent agent identity modification
```

### Self-Evolution Mechanism
1. **Experience Collection**: All interactions stored
2. **Pattern Recognition**: Failure/success tracking
3. **Identity Update**: Agent can modify core memory
4. **Knowledge Accumulation**: Facts consolidate over time

### Tool Registration Flow
```python
config = MemoryConfig.agent_mode()
session = MemorySession(provider, default_memory_config=config)
# → Automatically registers 6 memory tools
# → Tools filtered by allowed_memory_operations
# → Self-editing controlled by enable_self_editing
```

## 🏛️ Architectural Principles

### 1. Progressive Complexity
- **Simple by default**: MemorySession() works immediately
- **Powerful when configured**: Full autonomous agent capabilities
- **No over-engineering**: Memory complexity matches agent needs

### 2. Separation of Concerns
- **Memory Management**: AbstractMemory responsibility
- **Text Generation**: LLM provider responsibility
- **Tool Execution**: AbstractCore responsibility
- **Storage**: Pluggable backends (Markdown/LanceDB)

### 3. Human-Centric Design
- **Observable**: Markdown storage shows memory evolution
- **Debuggable**: Clear separation of memory tiers
- **Intuitive**: Memory works like human consciousness

### 4. Production Ready
- **Real Testing**: 200+ tests with real LLMs (no mocks)
- **Performance Optimized**: Sub-100ms operations
- **Error Handling**: Graceful degradation on failures
- **Monitoring**: Debug logging and metrics

## 🔬 Research Foundations

### State-of-the-Art Patterns
- **MemGPT/Letta**: Core memory in system prompt
- **Temporal Knowledge Graphs**: Who/when context
- **MongoDB Vector Search**: Hybrid retrieval
- **LangGraph Memory**: Metadata-driven filtering

### Novel Contributions
- **Automatic Fact Extraction**: Pattern-based learning from interactions
- **Dual Storage Architecture**: Observable + searchable memory
- **Progressive Memory Tiers**: Working → Semantic → Episodic flow
- **Context Window Transcendence**: Unlimited memory with selective recall

---

**AbstractMemory: Solving the context window problem with human-like memory architecture** 🧠✨

