# AbstractMemory Documentation

**Simple, powerful memory for AI agents - from basic chat to autonomous evolution**

## 📖 Documentation Structure

AbstractMemory's documentation is organized into three focused documents:

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **[📖 GUIDE.md](GUIDE.md)** | Complete usage guide | Learn how to use MemorySession with real examples |
| **[🏗️ ARCHITECTURE.md](ARCHITECTURE.md)** | Technical architecture | Understand memory tiers, embedding strategy, and design decisions |
| **[📋 API.md](API.md)** | API reference | Quick method lookup while coding |

## 🚀 Getting Started Path

1. **[Quick Start](../README.md#-quick-start-30-seconds)** - Get running in 30 seconds
2. **[GUIDE.md](GUIDE.md)** - Learn the three usage patterns and configuration options
3. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Understand the technical details (optional)

## 🎯 Find What You Need

| **I want to...** | **Go to...** | **Section** |
|-------------------|--------------|-------------|
| **Get started immediately** | [README](../README.md) | Quick Start |
| **Learn usage patterns** | [GUIDE.md](GUIDE.md) | Three Ways to Use |
| **Understand memory tiers** | [ARCHITECTURE.md](ARCHITECTURE.md) | Four-Tier Memory Architecture |
| **Configure for production** | [GUIDE.md](GUIDE.md) | Production Deployment |
| **Enable autonomous agents** | [GUIDE.md](GUIDE.md) | Autonomous Agent Memory Tools |
| **See method signatures** | [API.md](API.md) | All methods with parameters |
| **Debug issues** | [GUIDE.md](GUIDE.md) | Troubleshooting |
| **Migrate from BasicSession** | [GUIDE.md](GUIDE.md) | Migration from BasicSession |

## ⚡ Quick Example

```python
from abstractmemory import MemorySession
from abstractllm import create_llm

provider = create_llm("ollama", model="qwen3-coder:30b")
session = MemorySession(provider)

# Same API as BasicSession, but with unlimited memory
response = session.generate("Hi, I'm Alice and I love Python programming")
response = session.generate("What do you remember about me?")
# → "You're Alice and you love Python programming"
```

---

**Ready to start?** Go to **[GUIDE.md](GUIDE.md)** for complete examples and usage patterns.