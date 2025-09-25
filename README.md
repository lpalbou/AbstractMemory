# AbstractMemory: Long-Term Memory for AI Evolution

**Beyond context windows: Unlimited subconscious-like memory for AI agents**

AbstractMemory enables AI agents to remember, learn, and evolve beyond the limitations of chat history and context windows. Like human memory, it provides both conscious awareness (active context) and subconscious knowledge (persistent memory) - recalling facts, people, events, and strategies precisely when needed.

## 🧠 The Context Window Problem

**Current AI Limitation:**
- BasicSession: Has chat history in active context (~100k tokens max)
- Real-world needs: Years of interactions, millions of facts, continuous learning
- Result: AI "forgets" everything outside the context window

**AbstractMemory Solution:**
- **Conscious Memory** = Active context (limited, like human working memory)
- **Subconscious Memory** = Persistent storage (unlimited, like human long-term memory)
- **Selective Recall** = Retrieve relevant memories when needed, not all at once

Just like humans know thousands of facts but only think about relevant ones, AI with AbstractMemory has vast knowledge but selective awareness.

## 🚀 Drop-in BasicSession Replacement

**MemorySession**: Same simple API, now with unlimited memory

```python
# Before: BasicSession (context-limited memory)
from abstractllm import BasicSession
session = BasicSession(provider)
response = session.generate("Hello, I'm Alice and I love Python programming")
# Later... context fills up, Alice and Python preference are forgotten

# After: MemorySession (unlimited persistent memory)
from abstractmemory import MemorySession
session = MemorySession(provider)
response = session.generate("Hello, I'm Alice and I love Python programming")
# Later... years later, AI still remembers Alice loves Python
response = session.generate("What programming language do I prefer?")
# → "You mentioned you love Python programming"
```

**Key Insight**: Same API, but now the AI can evolve and remember indefinitely.

## 🧠 Memory Architecture: Conscious + Subconscious

Like human consciousness, AI needs both immediate awareness and deep knowledge:

```
Active Context (Conscious)          Persistent Memory (Subconscious)
├─ Recent conversation             ├─ Core Identity (who am I?)
├─ Current task context           ├─ Semantic Facts (what do I know?)
├─ Immediate working memory       ├─ User Relationships (who are they?)
└─ [Limited by context window]    └─ Historical Events (what happened?)
```

**Human Analogy**: You know thousands of facts about your life, but you're only consciously thinking about what's relevant right now. When someone mentions "Python," your brain recalls relevant memories about programming - not everything you've ever learned.

**AI with MemorySession**: Same principle - vast subconscious knowledge, selective conscious awareness.

## 🧠 Identity Through Subjective Experience

**The Key Insight**: AI identity emerges from how it interprets experiences through its core values.

Same objective fact → Different subjective meaning based on values → Unique identity over time

### Example: Values as Interpretive Lens

```python
from abstractmemory import GroundedMemory

# Same fact, different AI identities
fact = "The team worked 80 hours this week to meet the deadline"

# Productivity-focused AI
productivity_ai = GroundedMemory()
productivity_ai.set_core_values({'approach': 'productivity', 'purpose': 'efficiency'})
interpretation1 = productivity_ai.interpret_fact_subjectively(fact)
# → "opportunity for optimized execution and efficiency gains"

# Wellbeing-focused AI
wellbeing_ai = GroundedMemory()
wellbeing_ai.set_core_values({'approach': 'wellbeing', 'purpose': 'balance'})
interpretation2 = wellbeing_ai.interpret_fact_subjectively(fact)
# → "potential stress factor requiring mindful balance and sustainable practices"

# Same fact, different meanings = different identities
```

### Identity Persistence Across Sessions

```python
# Session 1: AI develops identity through experiences
ai_session1 = MemorySession(provider)
ai_session1.load_identity("./researcher_identity")
ai_session1.generate("I discovered that multi-layered memory enables autonomous agents")
# AI interprets this through its research-focused values
ai_session1.save_current_identity()

# Session 2: AI remembers both the fact AND its subjective interpretation
ai_session2 = MemorySession(provider)
ai_session2.load_identity("./researcher_identity")
ai_session2.generate("What did I learn about agent architecture?")
# → "You discovered that multi-layered memory enables autonomous agents,
#    which aligns with your research focus on systematic analysis..."
```

**Why This Matters**: Traditional AI forgets everything. AI with identity-based memory accumulates subjective experiences that shape its personality, decision-making, and responses over time - enabling true AI evolution.

## 🚀 Quick Start (30 Seconds)

### Installation
```bash
# Basic installation
pip install abstractmemory

# With semantic search capabilities
pip install abstractmemory[all]
```

### Three Ways to Use

**1. Simple (No Configuration)**
```python
from abstractmemory import MemorySession
from abstractllm import create_llm

provider = create_llm("ollama", model="qwen3-coder:30b")
session = MemorySession(provider)

# Works immediately - unlimited memory!
response = session.generate("Hi, I'm Alice and I love Python programming")
response = session.generate("What do you remember about me?")
# → "You're Alice and you love Python programming"
```

**2. With Persistent Storage**
```python
session = MemorySession(
    provider,
    memory_config={"path": "./memory"}  # Auto-configures storage + embeddings
)

# Now memories persist across sessions and are searchable
# Restart your app later - memories are still there!
```

**3. Autonomous Agent with Memory Tools**
```python
from abstractmemory import MemoryConfig

# Enable agent to manage its own memory
config = MemoryConfig.agent_mode()
session = MemorySession(provider, default_memory_config=config)

# Agent can now search and modify its own memory
response = session.generate("Remember that API limit is 100 requests per hour")
# → Agent automatically uses remember_fact tool

response = session.generate("Search your memory for API information")
# → Agent uses search_memory tool to find API limit info
```

## 💡 Why This Enables AI Evolution

**Traditional AI**: Resets with each conversation, cannot learn from past experiences
**AI with MemorySession**:
- Accumulates knowledge across all interactions
- Learns from failures and successes
- Develops persistent personality and preferences
- Can modify its own core identity based on experience
- Remembers user relationships and history

This is the foundation for truly autonomous, self-evolving AI agents.

## 📚 Complete Documentation

| Document | Purpose | Start Here If... |
|----------|---------|------------------|
| **[📖 GUIDE.md](docs/GUIDE.md)** | Complete usage guide with real-world examples | You want to learn how to use MemorySession |
| **[🏗️ ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Technical architecture and design decisions | You want to understand how memory works internally |
| **[📋 API.md](docs/API.md)** | Full API reference and method signatures | You need quick reference while coding |

**New to AbstractMemory?** Start with the [Quick Start](#-quick-start-30-seconds) above, then read [GUIDE.md](docs/GUIDE.md).

## 🧪 Testing (Real Implementations Only)

```bash
# All tests use real LLMs, real embeddings, real storage - NO MOCKS
python -m pytest tests/ -v

# Test with real Ollama LLM
python -m pytest tests/integration/test_real_llm_memory.py -v
```

## Migration from BasicSession

```python
# Old code - works but limited by context window
from abstractllm import BasicSession
session = BasicSession(provider, system_prompt="You are helpful")

# New code - same API, unlimited memory (just change import!)
from abstractmemory import MemorySession
session = MemorySession(provider, system_prompt="You are helpful")
```

---

**AbstractMemory: Because forgetting is for humans, not AI** 🧠✨