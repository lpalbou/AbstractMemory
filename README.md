# AbstractMemory Documentation

AbstractMemory is a multi-layer memory system that extends AbstractCore's BasicSession with sophisticated memory capabilities. It provides both voluntary memory operations (through exposed tools) and automated memory processes (background indexing, consolidation, and context reconstruction).

## Documentation Structure

- **[Getting Started](getting-started.md)** - Installation, setup, and first steps
- **[Architecture](architecture.md)** - System design and component overview  
- **[Capabilities](capabilities.md)** - What AbstractMemory can do
- **[Examples](examples.md)** - Code examples and usage patterns
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

## Quick Overview

AbstractMemory provides:

### Voluntary Memory Operations (Tool-Based)
- **remember_fact()** - Explicitly store important information
- **search_memories()** - Query past interactions and stored knowledge
- **reflect_on()** - Analyze patterns across memories
- **reconstruct_context()** - Build rich context for current interaction

### Automated Memory Processes  
- **Context Reconstruction** - Automatically builds relevant context for each interaction
- **Memory Indexing** - Indexes all memories for semantic search
- **Fact Extraction** - Extracts knowledge from conversations in background
- **Memory Consolidation** - Periodically consolidates memories into core components

### Dual Storage Architecture
- **Markdown Files** - Human-readable, version-controlled memory storage
- **LanceDB Vectors** - Semantic search with embeddings and metadata

## Core Concepts

AbstractMemory organizes memory into layers similar to human memory systems:

- **Core Memory** - Identity components that emerge from interactions (purpose, values, personality, etc.)
- **Working Memory** - Current context, active tasks, and immediate focus
- **Episodic Memory** - Significant events, experiments, and discoveries  
- **Semantic Memory** - Knowledge, concepts, and insights
- **Library Memory** - Documents and external knowledge sources
- **User Profiles** - Understanding of individual users through interaction patterns

## Integration with AbstractCore

AbstractMemory is built on [AbstractCore](https://lpalbou.github.io/AbstractCore) and leverages:

- **BasicSession** - Foundation for conversation management
- **BasicExtractor** - Semantic knowledge extraction  
- **EmbeddingManager** - Vector embeddings for search
- **StructuredOutputHandler** - Response parsing and validation

## Philosophy

AbstractMemory draws inspiration from human memory systems, providing:

1. **Voluntary Control** - Like conscious memory, you can explicitly choose what to remember and search
2. **Automatic Processing** - Like subconscious processes, memory indexing and consolidation happen automatically
3. **Emergence** - Identity components develop naturally from interaction patterns
4. **Transparency** - All memory operations are observable and debuggable
5. **Dual Storage** - Both human-readable files and machine-searchable vectors

The system aims to create more contextual, personalized AI interactions while maintaining full transparency and user control.