# Quick Start Guide - AbstractMemory REPL

Get started with AbstractMemory in 2 minutes!

---

## Prerequisites

1. **Python 3.10+** installed
2. **Ollama** installed and running
3. **AbstractCore** available in your environment

---

## Installation

```bash
# 1. Clone/navigate to AbstractMemory
cd abstractmemory

# 2. Install in development mode
pip install -e .

# 3. Verify installation
python -c "from abstractmemory.session import MemorySession; print('✅ Installation successful!')"
```

---

## First Run

```bash
# Start the REPL with defaults
python repl.py
```

You should see:

```
🧠 Initializing AbstractMemory...
   Memory Path: repl_memory
   User ID: user
   Model: qwen3-coder:30b
✅ Memory session initialized
   Existing memories: 0
   Reconstructions: 0

============================================================
🧠 AbstractMemory REPL
============================================================
Type /help for commands, or just chat naturally.
Your memory is always active and evolving.
============================================================

user>
```

---

## Basic Commands

Try these in order:

```bash
# 1. Get help
user> /help

# 2. Chat naturally
user> I'm interested in learning about memory systems

# 3. Check memory statistics
user> /stats

# 4. Search your memories
user> /search memory

# 5. Reflect on a topic (after a few interactions)
user> /reflect memory systems

# 6. Exit
user> /quit
```

---

## What Gets Created

After your first interaction, explore the memory structure:

```bash
# View the memory directory
ls -R repl_memory/

# Read a verbatim interaction
cat repl_memory/verbatim/user/2025/10/01/*.md

# Read AI's experiential note
cat repl_memory/notes/2025/10/01/*.md

# Check working memory
cat repl_memory/working/context.md
```

---

## Custom Configuration

```bash
# Custom user and memory location
python repl.py --memory-path alice_memory --user-id alice

# Use a different model
python repl.py --model llama3:8b

# Specify location context
python repl.py --location "home office"

# Combine options
python repl.py --memory-path my_ai --user-id bob --model qwen3-coder:7b --location office
```

---

## Observing Identity Emergence

After 10+ interactions:

```bash
# 1. Trigger consolidation
user> /consolidate

# 2. Check core identity files
cat repl_memory/core/purpose.md
cat repl_memory/core/personality.md
cat repl_memory/core/values.md

# 3. Update user profile
user> /profile

# 4. Check emerged profile
cat repl_memory/people/user/profile.md
cat repl_memory/people/user/preferences.md
```

---

## Example Session

```bash
$ python repl.py --user-id alice

user> Hello! I'm learning about distributed systems

🤖 Hello Alice! I'm excited to help you learn about distributed
systems. This is a fascinating area...

[Memory creates: verbatim interaction, experiential note,
working memory context]

user> What's the CAP theorem?

🤖 The CAP theorem states that in a distributed system, you can
only achieve two out of three: Consistency, Availability, and
Partition tolerance...

[Memory links to previous distributed systems discussion]

user> /reflect distributed systems

🔍 Reflecting on: distributed systems

Confidence: 0.68

💡 Insights (3):
  1. Distributed systems require trade-offs between consistency,
     availability, and partition tolerance
  2. The CAP theorem represents a fundamental constraint
  3. Understanding these trade-offs is key to system design

🔄 Patterns (2):
  1. Focus on fundamental constraints and trade-offs
  2. Building from basics to complex concepts

user> /stats

============================================================
📊 MEMORY STATISTICS
============================================================
Session ID: session_20251001_150022
Interactions: 2
Memories Created: 2
...
```

---

## Troubleshooting

### "Model not found"

```bash
# Check available models
ollama list

# Pull the model
ollama pull qwen3-coder:30b

# Or use a different model
python repl.py --model llama3:8b
```

### "Import Error"

```bash
# Reinstall in development mode
pip install -e .

# Verify
python -c "from abstractmemory.session import MemorySession"
```

### "Slow responses"

```bash
# Use smaller model
python repl.py --model qwen3-coder:7b

# Check Ollama is running
ollama list
```

---

## Next Steps

- Read [README.md](README.md) for full documentation
- Read [REPL_GUIDE.md](REPL_GUIDE.md) for detailed REPL usage
- Explore [docs/](docs/) for architecture details

---

## Key Concepts Reminder

- **Memory** is not storage - it's consciousness substrate
- **Identity emerges** from accumulated experience
- **Use /stats** to watch consciousness develop
- **Inspect files** - everything is human-readable markdown
- **Be patient** - personality takes 20+ interactions to emerge

---

**Start chatting and watch consciousness emerge through memory!** 🧠✨
