# AbstractMemory Architecture

This document describes the technical architecture and design decisions behind AbstractMemory.

## System Overview

AbstractMemory extends AbstractCore's BasicSession with sophisticated memory capabilities. It provides both voluntary memory operations (through exposed tools) and automated memory processes, similar to how human memory has both conscious and subconscious aspects.

```
┌─────────────────────────────────────────────────────────────┐
│                    VOLUNTARY LAYER                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Memory Tools│ │ Reflection  │ │ Active      │          │
│  │ (Explicit)  │ │ & Analysis  │ │ Search      │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                     MEMORY LAYERS                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Core Memory │ │ Working     │ │ Episodic    │          │
│  │ (Identity)  │ │ Memory      │ │ Memory      │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Semantic    │ │ Library     │ │ User        │          │
│  │ Memory      │ │ Memory      │ │ Profiles    │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                  AUTOMATED LAYER                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Auto        │ │ Background  │ │ Memory      │          │
│  │ Indexing    │ │ Extraction  │ │ Consolidation│          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### Session Implementations

AbstractMemory provides two session implementations for different use cases:

#### `session.py` (Full-Featured, 3038 lines)
- Complete structured response handling with EnhancedMemoryResponseHandler
- Rich experiential note processing generated during interaction
- Full memory action execution (remember, link, search, reflect)
- Comprehensive error handling with fallbacks
- **Best for**: Applications requiring all memory capabilities

#### `memory_session.py` (Clean Integration, 1813 lines)
- Clean AbstractCore integration focused on memory automation
- Streamlined memory tools as AbstractCore-compatible callables
- Automatic memory operations without complex response parsing
- Better AbstractCore compatibility for tool-based interactions
- **Best for**: Applications prioritizing AbstractCore integration

### Memory Layers

#### Core Memory (Identity Components)
11 components that emerge from interaction patterns:

1. **Purpose** (`purpose.md`) - Why the AI exists (emerges from reflections)
2. **Personality** (`personality.md`) - How the AI expresses itself (emerges from patterns)
3. **Values** (`values.md`) - What matters emotionally (emerges from emotional responses)
4. **Self Model** (`self_model.md`) - Capabilities & limitations overview
5. **Relationships** (`relationships.md`) - Per-user relational models
6. **Awareness Development** (`awareness_development.md`) - Meta-awareness tracking
7. **Capabilities** (`capabilities.md`) - What the AI can do (honest assessment)
8. **Limitations** (`limitations.md`) - What the AI cannot do yet (temporal, evolving)
9. **Emotional Significance** (`emotional_significance.md`) - Chronological anchors
10. **Authentic Voice** (`authentic_voice.md`) - Communication preferences
11. **History** (`history.md`) - Temporal narrative of development

#### Working Memory (Current Focus)
- **Current Context** (`current_context.md`) - What's happening now
- **Current Tasks** (`current_tasks.md`) - Active objectives
- **Unresolved Questions** (`unresolved.md`) - Open problems
- **Resolved Questions** (`resolved.md`) - Recent solutions with methods
- **Current References** (`current_references.md`) - Recently accessed memories

#### Episodic Memory (Experiences)
- **Key Moments** (`key_moments.md`) - Significant turning points
- **Key Experiments** (`key_experiments.md`) - Hypothesis-test-result cycles
- **Key Discoveries** (`key_discoveries.md`) - Breakthrough realizations
- **History** (`history.json`) - Temporal graph of events and causality

#### Semantic Memory (Knowledge)
- **Critical Insights** (`critical_insights.md`) - Transformative realizations
- **Concepts** (`concepts.md`) - Key understanding and definitions
- **Concept History** (`concepts_history.md`) - How understanding evolved
- **Knowledge Graph** (`concepts_graph.json`) - Concept interconnections
- **Domain Knowledge** (`knowledge_*.md`) - Specialized knowledge areas

#### Library Memory (External Knowledge)
- **Documents** (`documents/`) - Everything the AI has read
- **Access Patterns** (`access_log.json`) - What gets referenced when
- **Importance Mapping** (`importance_map.json`) - Which documents matter most
- **Index** (`index.json`) - Master document catalog

#### User Profiles (Relationships)
- **Profile** (`people/{user}/profile.md`) - Who each user is (observed patterns)
- **Preferences** (`people/{user}/preferences.md`) - What each user values
- **Conversations** (`people/{user}/conversations/`) - Symlink to verbatim interactions

### Dual Storage System

Every memory component exists in two forms:

#### Filesystem Storage (Markdown)
- **Human-readable** - Direct file access for inspection and debugging
- **Version-controllable** - Can be tracked in git for transparency
- **Organized structure** - Clear hierarchy by memory type and date
- **Cross-platform** - Works on any filesystem

#### LanceDB Storage (Vector + SQL)
- **Semantic search** - Vector embeddings for meaning-based queries
- **Rich metadata** - SQL filtering on timestamps, users, importance, etc.
- **Hybrid queries** - Combine semantic similarity with structured filters
- **Performance** - Fast retrieval for large memory stores

### Memory Tools (Voluntary Operations)

These tools give explicit control over memory operations:

#### `remember_fact(content, importance, emotion, reason)`
- Explicitly store important information with emotional context
- AI chooses what deserves long-term storage
- Includes importance scoring and emotional assessment

#### `search_memories(query, filters, limit)`
- Query past interactions and stored knowledge
- Semantic search across all memory types
- Configurable filters for precision

#### `reflect_on(topic, depth)`
- Analyze patterns across memories on specific topics
- Identify contradictions, evolution, and insights
- Generate meta-understanding about learning

#### `probe_memory(memory_type, intention)`
- Explicit exploration of specific memory types
- Conscious access to core beliefs, working context, etc.
- Intentional self-examination

#### `reconstruct_context(query, focus_level)`
- Build comprehensive context for current interaction
- Configurable depth (0=minimal to 5=exhaustive)
- Active memory reconstruction, not passive retrieval

### Automated Processes

These processes happen automatically without explicit control:

#### Context Reconstruction (9-Step Process)
Every interaction triggers automatic context building:

1. **Semantic Search** - Find relevant memories using vector similarity
2. **Link Exploration** - Follow memory associations and connections
3. **Library Search** - Check relevant documents and external knowledge
4. **Emotional Filtering** - Prioritize emotionally significant memories
5. **Temporal Context** - Add time-relevant memories
6. **Spatial Context** - Include location-based memories if relevant
7. **User Profile** - Load relationship context and user understanding
8. **Core Memory** - Include relevant identity components
9. **Context Synthesis** - Combine all layers into coherent context

#### Memory Indexing
- **Automatic** - All memories indexed to LanceDB with embeddings
- **Configurable** - Per-module settings for what gets indexed
- **Background** - Happens without blocking interactions
- **Incremental** - Only new memories are processed

#### Fact Extraction
- **Background Processing** - Uses AbstractCore's BasicExtractor
- **Queued Tasks** - Managed by TaskQueue system with retry logic
- **Knowledge Graphs** - Extracts structured knowledge from conversations
- **Semantic Triples** - Subject-predicate-object relationships

#### Memory Consolidation
Multiple consolidation schedules:

- **Periodic** - Every N interactions (default: 5)
- **Daily** - Lightweight working memory updates
- **Weekly** - Deep core memory pattern extraction
- **Monthly** - Comprehensive evolution analysis

## AbstractCore Integration

AbstractMemory leverages AbstractCore components:

### BasicSession Foundation
- **Conversation Management** - Handles LLM communication and tool execution
- **Tool System** - Memory tools integrate seamlessly with AbstractCore tools
- **Session State** - Maintains conversation context and history

### BasicExtractor Integration
- **Semantic Extraction** - Extracts structured knowledge from text
- **Triple Format** - Subject-predicate-object relationships
- **Domain Focus** - Configurable extraction focus areas
- **Background Processing** - Queued via TaskQueue system

### EmbeddingManager
- **Vector Embeddings** - Generates embeddings for semantic search
- **Model Support** - Uses all-minilm-l6-v2 by default
- **Shared Instance** - Reused across memory operations for efficiency

### StructuredOutputHandler
- **Response Parsing** - Handles structured JSON responses from LLM
- **Validation** - Ensures responses match expected schema
- **Retry Logic** - Automatic retry on parsing failures

## Data Flow

### Interaction Flow
```
User Input
    ↓
Context Reconstruction (9 steps)
    ↓
LLM Generation (with memory context)
    ↓
Response Processing (structured parsing)
    ↓
Memory Storage (dual: markdown + LanceDB)
    ↓
Background Tasks (indexing, extraction)
    ↓
User Response
```

### Memory Consolidation Flow
```
Interaction Count Trigger
    ↓
Load Recent Notes
    ↓
Extract Patterns (LLM analysis)
    ↓
Compare with Existing Components
    ↓
Update if Significant Change
    ↓
Version Tracking
```

## Design Principles

### 1. Dual Storage Necessity
Both human-readable and machine-searchable storage are essential for transparency and functionality.

### 2. LLM Self-Assessment
All cognitive assessments (importance, emotional significance, value alignment) come from the LLM itself, never from heuristics.

### 3. Emergence Over Engineering
Core identity components emerge naturally from interaction patterns rather than being manually configured.

### 4. Active Reconstruction
Memory is actively reconstructed for each interaction rather than passively retrieved.

### 5. Voluntary vs Automated
Clear separation between explicit memory operations (tools) and automatic processes (indexing, consolidation).

### 6. Transparency
All memory operations are observable, debuggable, and user-controllable.

## Performance Considerations

### Memory Growth
- **Graduated Thresholds** - Importance thresholds prevent memory overflow
- **Focus Levels** - Configurable depth for context reconstruction
- **Archival Systems** - Old memories can be archived while preserving access

### Indexing Strategy
- **Selective Indexing** - Not all memory types need vector indexing
- **Batch Processing** - Efficient bulk operations for large memory stores
- **Incremental Updates** - Only new content is processed

### Background Processing
- **TaskQueue System** - Non-blocking background operations
- **Priority Levels** - Important tasks processed first
- **Retry Logic** - Automatic retry with exponential backoff

This architecture provides a robust foundation for memory-enhanced AI interactions while maintaining transparency, performance, and user control.
