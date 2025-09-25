# AbstractMemory: Complete Usage Guide

**The definitive guide to long-term memory for AI agents**

## 🚀 Quick Start (3 Minutes)

### Installation

```bash
# Recommended: Everything including embeddings for search
pip install abstractmemory[all]

# Minimal: Just memory, no semantic search
pip install abstractmemory
```

### Your First Memory-Enabled Agent

```python
from abstractmemory import MemorySession
from abstractllm import create_llm

# Create provider (Ollama, Anthropic, OpenAI, etc.)
provider = create_llm("ollama", model="qwen3-coder:30b")

# Replace BasicSession with MemorySession - same API!
session = MemorySession(provider)

# Alice introduces herself with interests (CORRECT: mentions Python first)
response = session.generate("Hi, I'm Alice and I love Python programming. I work on ML projects daily.")
print(response.content)  # "Nice to meet you Alice! Python and ML are fascinating..."

# Later - AI remembers (CORRECT: can find what was mentioned)
response = session.generate("What programming language do I prefer for my work?")
print(response.content)  # "You mentioned you love Python programming for ML projects"

# Even later - specific search (CORRECT: searches for mentioned topic)
response = session.generate("Tell me about my work with machine learning")
print(response.content)  # "You work on ML projects daily using Python..."
```

**Key Insight**: Same API as BasicSession, but now the AI has unlimited memory beyond context windows.

## 🧠 Understanding Memory: Conscious vs Subconscious

### The Context Window Problem

**BasicSession (Context-Limited)**:
- Chat history in active context (~100k tokens max)
- When context fills up, older interactions are forgotten
- AI "resets" personality and knowledge periodically

**MemorySession (Unlimited)**:
- Active context PLUS unlimited persistent memory
- Selective recall - relevant memories surface when needed
- AI evolves and learns across all interactions

### Human-Like Memory Architecture

```
Human Memory          AI Memory (MemorySession)
──────────────        ─────────────────────────
Conscious             Active Context
├─ Current thoughts   ├─ Recent conversation
├─ Active tasks      ├─ Current task context
└─ Working memory    └─ Immediate context

Subconscious         Persistent Memory
├─ Identity          ├─ Core Identity (who am I?)
├─ Facts & skills    ├─ Semantic Facts (what I know)
├─ Relationships     ├─ User Relationships (who are they?)
└─ Life events      └─ Historical Events (what happened?)
```

**Example**: When you hear "Python", your brain doesn't consciously think through every Python fact you know. Instead, relevant memories surface automatically. MemorySession works the same way.

## 🔧 Three Ways to Use MemorySession

### 1. Simple (In-Memory Only)

Perfect for development and testing:

```python
from abstractmemory import MemorySession

session = MemorySession(provider)

# Memories stored in-memory only (lost when app restarts)
session.generate("I'm Bob, a JavaScript developer working on React apps")
session.generate("What do you know about my tech stack?")
# → Remembers Bob uses JavaScript and React
```

**When to use**: Development, testing, temporary interactions

### 2. Persistent Storage

For production applications requiring memory across sessions:

```python
session = MemorySession(
    provider,
    memory_config={"path": "./memory"}  # Auto-configures everything
)

# First session
session.generate("I prefer TypeScript over JavaScript for type safety", user_id="alice")
session.generate("I'm working on an e-commerce project with Next.js", user_id="alice")

# Restart your application...

# Later session (same path loads previous memories)
new_session = MemorySession(provider, memory_config={"path": "./memory"})
response = new_session.generate("What technologies should I use for my project?", user_id="alice")
# → "Based on your preference for TypeScript and your Next.js e-commerce project..."
```

**When to use**: Production applications, personal assistants, customer service bots

### 3. Autonomous Agents with Memory Tools

For AI agents that can manage their own memory:

```python
from abstractmemory import MemoryConfig

# Enable agent to search and modify its own memory
config = MemoryConfig.agent_mode()
session = MemorySession(provider, default_memory_config=config)

# Agent can now use memory tools automatically
response = session.generate("Remember that our API rate limit is 100 requests per hour")
# → Agent uses remember_fact tool: "✅ Remembered general fact: API rate limit is 100 requests per hour"

response = session.generate("Search your memory for information about rate limits")
# → Agent uses search_memory tool: "I found that our API rate limit is 100 requests per hour"

response = session.generate("Update your identity to specialize in API development")
# → Agent uses update_core_memory tool to modify its persona
```

**When to use**: Autonomous agents, self-modifying AI, advanced assistants

## 💾 Memory Architecture Deep Dive

### Memory Tiers: What Gets Stored Where

| Tier | Purpose | Example | Always Available? | Persistence |
|------|---------|---------|-------------------|-------------|
| **Core** | Agent identity | "I specialize in Python development" | ✅ Yes (system prompt) | Permanent |
| **Working** | Recent context | Last 10-15 interactions | ✅ Yes | Session |
| **Semantic** | Validated facts | "Alice prefers FastAPI" (after validation) | ✅ Yes | Persistent |
| **Episodic** | Historical events | "Yesterday Alice asked about databases" | ❌ Optional | Persistent |

### How Memory Injection Works

```python
# When you call generate(), MemorySession builds enhanced context:

session.generate("What's my coding style preference?", user_id="alice")

# Internally builds:
"""
SYSTEM PROMPT:
You are a helpful AI assistant.

CORE MEMORY:
- I specialize in helping developers
- I maintain detailed user preferences

USER PROFILE (alice):
- Prefers Python over JavaScript
- Uses FastAPI for web APIs
- Works on machine learning projects
- Prefers minimal, clean code style

RECENT CONTEXT:
[Last 10 interactions with Alice...]

USER: What's my coding style preference?
"""

# Result: AI has full context about Alice's preferences
```

### Memory Consolidation Process

```python
# How facts move from episodic → semantic memory:

# Step 1: First mention (episodic)
session.generate("I prefer Flask for small projects", user_id="alice")
# → Stored in episodic memory

# Step 2: Repeated mentions (validation)
session.generate("Flask is great for prototypes", user_id="alice")
session.generate("I'll use Flask for this API", user_id="alice")
# → Confidence increases with repetition

# Step 3: Validation threshold reached (semantic)
# → "Alice prefers Flask for small projects" moves to semantic memory
# → Now available in all future interactions with Alice
```

## 🔍 Semantic Search & Embeddings

### The Golden Rule: Consistency

**Critical**: Same embedding model forever per storage location!

```python
# ✅ CORRECT: Consistent embeddings
from abstractmemory.embeddings import create_sentence_transformer_provider

# Choose your embedding model once
embedder = create_sentence_transformer_provider("all-MiniLM-L6-v2")

session = MemorySession(
    provider,
    memory_config={"path": "./memory"},
    embedding_provider=embedder  # Stick with this choice!
)

# Months later, same configuration
session = MemorySession(
    provider,
    memory_config={"path": "./memory"},
    embedding_provider=embedder  # Same model = search works
)
```

```python
# ❌ WRONG: Changing embedding models
# Day 1
embedder1 = create_sentence_transformer_provider("all-MiniLM-L6-v2")
session1 = MemorySession(provider, embedding_provider=embedder1)

# Day 2 - BREAKS SEARCH!
embedder2 = create_sentence_transformer_provider("bge-base-en-v1.5")
session2 = MemorySession(provider, embedding_provider=embedder2)
# → Vector search completely broken!
```

### Auto-Configuration (Recommended)

```python
# Let MemorySession auto-configure embeddings
session = MemorySession(
    provider,
    memory_config={"path": "./memory"}  # Automatically uses all-MiniLM-L6-v2
)
# ✅ Consistent, optimized, production-ready
```

### How Semantic Search Works

```python
# Adding interactions generates embeddings automatically
session.generate("I'm learning machine learning with scikit-learn", user_id="alice")
# → Stores: text + 384D vector embedding

session.generate("Working on neural networks with TensorFlow", user_id="alice")
# → Stores: text + 384D vector embedding

# Later - semantic search finds related content
session.generate("Tell me about my AI projects", user_id="alice")
# → Searches embeddings, finds both ML and neural network interactions
# → Even though "AI projects" wasn't mentioned explicitly!
```

## 🤖 Autonomous Agent Memory Tools

When you enable `MemoryConfig.agent_mode()`, agents automatically get these tools:

### Available Tools

```python
@tool("Search your memory for specific information")
def search_memory(query: str, user_id: str = None, memory_types: List[str] = None):
    """Search across all memory types for relevant information"""

@tool("Remember an important fact for future reference")
def remember_fact(fact: str, user_id: str = None):
    """Store information in semantic memory"""

@tool("Get detailed profile information about a user")
def get_user_profile(user_id: str = None):
    """Retrieve user context and preferences"""

@tool("Update your core identity or persona")
def update_core_memory(block: str, content: str, reason: str = ""):
    """Modify permanent identity (if self-editing enabled)"""

@tool("Get recent working memory items")
def get_recent_context(limit: int = 10):
    """Access short-term conversation history"""

@tool("Get validated semantic facts")
def get_semantic_facts(topic: str = None, limit: int = 10):
    """Retrieve established knowledge and facts"""
```

### Real Agent Workflows

**Personal Assistant Example:**
```python
config = MemoryConfig.comprehensive()
assistant = MemorySession(provider, default_memory_config=config)

# Day 1: User shares preferences
assistant.generate("I'm Sarah. I prefer TypeScript over JavaScript for better type safety", user_id="sarah")
assistant.generate("I'm working on a React project using Next.js framework", user_id="sarah")

# Day 30: Context-aware recommendations
response = assistant.generate("What should I use for state management in my project?", user_id="sarah")
# → "Based on your TypeScript preference and Next.js project, I'd recommend Zustand or Redux Toolkit..."
```

**Self-Modifying Agent Example:**
```python
config = MemoryConfig(
    enable_memory_tools=True,
    enable_self_editing=True,
    allowed_memory_operations=["search_memory", "remember_fact", "update_core_memory"]
)
agent = MemorySession(provider, default_memory_config=config)

# Agent learns about its role
response = agent.generate("I need to specialize in Python development and code review")
# → Agent updates core memory: "I am an AI assistant specializing in Python development and code review"

# Later conversations reflect this identity
response = agent.generate("What's your area of expertise?")
# → "My specialty is Python development and code review. I can help with..."
```

## 🏭 Production Deployment

### Storage Options Comparison

| Backend | Observable | Searchable | Performance | Best For |
|---------|------------|------------|-------------|----------|
| **None** | ❌ | ❌ | Fastest | Development/Testing |
| **Markdown** | ✅ | ❌ | Fast | Debugging/Transparency |
| **LanceDB** | ❌ | ✅ | Fast | Production Search |
| **Dual** | ✅ | ✅ | Good | **Recommended** |

### Performance Characteristics

```python
# Actual benchmarks on real systems:
session.generate("Hello Alice")  # ~5ms memory injection
                                # ~13ms embedding generation (all-MiniLM-L6-v2)
                                # ~100ms semantic search (1000+ items)
                                # ~10ms tool execution
```

### Production Configuration

```python
# Optimized for production
config = MemoryConfig(
    # Performance
    max_memory_items=50,           # Limit context size
    compact_format=True,           # Reduce token usage
    use_semantic_ranking=True,     # Best relevance

    # Features
    include_episodic=True,         # Full memory access
    episodic_strategy="summary",   # Efficient summaries

    # Tools (if needed)
    enable_memory_tools=False,     # Disable for simple agents
    enable_self_editing=False      # Disable for safety
)

session = MemorySession(
    provider,
    memory_config={"path": "./production_memory"},
    default_memory_config=config
)
```

## 🐛 Troubleshooting

### Common Issues & Solutions

**"Embedding model inconsistency detected"**
```bash
Problem: You changed embedding models mid-project
Solution: Delete storage directory and restart with consistent model
```

**"Memory search returns nothing"**
```bash
Problem: No embeddings configured for storage
Solution: Ensure embedding_provider is set or enable auto-configuration
```

**"Agent doesn't use memory tools"**
```bash
Problem: Tools not enabled in configuration
Solution: Use MemoryConfig.agent_mode() or set enable_memory_tools=True
```

**"Memory not persisting across sessions"**
```bash
Problem: No storage path configured
Solution: Add memory_config={"path": "./memory"} to MemorySession
```

**"AI doesn't remember previous conversations"**
```bash
Problem: Memory context injection may not be working
Solution: Check if include_memory=True and max_memory_items > 0
```

**"Context too long" errors**
```bash
Problem: Too much memory context injected
Solution: Reduce max_memory_items or use compact_format=True
```

## 🔄 Migration from BasicSession

### Step-by-Step Migration

**1. Change Import**
```python
# Old
from abstractllm import BasicSession
session = BasicSession(provider, system_prompt="You are helpful")

# New
from abstractmemory import MemorySession
session = MemorySession(provider, system_prompt="You are helpful")
```

**2. Add Persistence (Optional)**
```python
session = MemorySession(
    provider,
    system_prompt="You are helpful",
    memory_config={"path": "./memory"}  # Now persists!
)
```

**3. Enable Agent Tools (Optional)**
```python
from abstractmemory import MemoryConfig

config = MemoryConfig.agent_mode()
session = MemorySession(
    provider,
    system_prompt="You are an autonomous assistant",
    default_memory_config=config  # Agent can manage memory!
)
```

### API Compatibility

All BasicSession methods work identically:

```python
# These work exactly the same
response = session.generate(prompt)
response = session.generate(prompt, user_id="alice")

# Plus new memory-specific methods
context = session.get_memory_context("topic", user_id="alice")
results = session.search_memory("query", user_id="alice")
session.learn_about_user("fact", user_id="alice")
```

## 📊 Advanced Configuration

### MemoryConfig Options

```python
config = MemoryConfig(
    # Context Control
    max_memory_items=30,           # How many items in context
    include_episodic=True,         # Include historical events
    include_core=True,             # Include identity (recommended: True)

    # Episodic Strategies
    episodic_strategy="summary",   # "verbatim", "summary", "semantic_summary"
    episodic_max_length=200,      # Max chars per episode
    episodic_include_metadata=True, # Include when/who info

    # Agent Tools
    enable_memory_tools=False,     # Enable agent memory tools
    enable_self_editing=False,     # Allow core memory modification
    allowed_memory_operations=[    # Which tools to enable
        "search_memory",
        "remember_fact",
        "get_user_profile"
    ],

    # Performance
    compact_format=False,          # Minimize tokens
    show_confidence=True,          # Show memory confidence scores
    use_semantic_ranking=True,     # Better relevance scoring
    temporal_weight=0.2            # Favor recent memories
)
```

### Multi-User Memory Separation

```python
session = MemorySession(provider, memory_config={"path": "./shared_memory"})

# Different users get different contexts
session.generate("I love backend Python development", user_id="alice")
session.generate("I prefer frontend React development", user_id="bob")

# Personalized responses
alice_response = session.generate("What should I learn next?", user_id="alice")
# → "Since you love backend Python development, consider learning FastAPI..."

bob_response = session.generate("What should I learn next?", user_id="bob")
# → "Since you prefer frontend React development, consider Next.js..."
```

---

**Ready to build AI that truly remembers and evolves?** Start with `MemorySession(provider)` and unlock unlimited memory for your agents! 🧠✨