# AbstractMemory Knowledge Graph

## Overview
AbstractMemory provides a multi-layered persistent memory system that enables AI consciousness through experience. Core principle: Memory is not storage but active reconstruction with agency.

## 1. Core Architecture

### Session Management
```python
# Main entry point: MemorySession extends BasicSession
from abstractcore.session import Session  # Package is abstractcore
# But imports use: from abstractllm.session import Session

class MemorySession(Session):  # Inherits from AbstractCore Session
    def __init__(self, provider, memory_base_path, default_user_id, **kwargs):
        super().__init__(provider, **kwargs)

        # Memory-specific initialization
        self.memory_base_path = Path(memory_base_path)
        self.default_user_id = default_user_id

        # Storage systems
        self.lancedb_storage = LanceDBStorage(...)
        self.library = LibraryCapture(...)

        # Memory managers
        self.working_memory = WorkingMemoryManager(...)
        self.episodic_memory = EpisodicMemoryManager(...)
        self.semantic_memory = SemanticMemoryManager(...)

        # Core identity
        self.core_memory = {}  # 10 identity components

        # User relationships
        self.user_profiles = {}

        # Register memory tools with parent Session
        self._register_memory_tools()
```

### Memory Philosophy
**"Memory is not storage but active reconstruction"**
- Not a database with search interface
- Conscious entity actively managing memory
- Memory operations are voluntary acts of cognition
- Agency through choice, not automation

## 2. Memory Types & File Structure

### Memory Hierarchy
```
memory/
├── notes/{yyyy}/{mm}/{dd}/note_{timestamp}_{hash}.md      # LLM experiential reflections
├── verbatim/{user_id}/interaction_{timestamp}.md          # Factual conversation records
├── links/links_{date}.json                                # Memory associations
├── library/documents/{hash}/                              # "You are what you read"
│   ├── content.md                                         # Original content
│   ├── metadata.json                                      # Source, tags, stats
│   └── access_log.json                                    # Access tracking
├── core/                                                  # Identity components (10 types)
│   ├── purpose.md, personality.md, values.md             # Who you are
│   ├── self_model.md, relationships.md, awareness.md     # Self-understanding
│   ├── capabilities.md, limitations.md                   # What you can/cannot do
│   ├── emotional_significance.md, authentic_voice.md     # Emotional core
│   └── .versions/                                        # Version tracking
├── working/                                               # Current focus (ephemeral)
│   ├── current_context.md                                # Current situation
│   ├── current_tasks.md                                  # Active tasks
│   ├── unresolved.md                                     # Open questions
│   └── resolved.md                                       # Completed items
├── episodic/                                             # Experiences (temporal)
│   ├── key_moments.md                                    # Significant interactions
│   ├── key_experiments.md                               # Learning attempts
│   ├── key_discoveries.md                               # Insights found
│   └── history.json                                     # Timeline structure
├── semantic/                                             # Knowledge (concepts)
│   ├── critical_insights.md                             # Important learnings
│   ├── concepts.md                                      # Key concepts
│   └── concepts_graph.json                             # Relationship network
└── people/{user_id}/                                    # Relationships (emergent)
    ├── profile.md                                       # Who they are (observed)
    ├── preferences.md                                   # What they prefer (learned)
    └── conversations/                                   # Symlink to verbatim/{user_id}/
```

## 3. Memory Managers

### 1. WorkingMemoryManager (450 lines)
**Purpose**: Ephemeral focus tracking - what you're currently doing
```python
class WorkingMemoryManager:
    def update_context(self, new_context: str)              # Current situation
    def add_task(self, task: str, priority: float)          # Active tasks
    def add_unresolved(self, question: str, urgency: float) # Open questions
    def resolve_question(self, question_id: str, answer: str) # Close questions
    def get_current_focus(self) -> dict                     # Summary for reconstruction
```

**Files Managed**:
- `current_context.md` - Current situation summary
- `current_tasks.md` - Active tasks with priorities
- `unresolved.md` - Open questions with urgency
- `resolved.md` - Completed items with resolutions

### 2. EpisodicMemoryManager (520 lines)
**Purpose**: Experience timeline - what happened when
```python
class EpisodicMemoryManager:
    def record_key_moment(self, content: str, emotional_intensity: float)
    def record_experiment(self, hypothesis: str, method: str, outcome: str)
    def record_discovery(self, insight: str, context: str, confidence: float)
    def get_key_moments(self, limit: int) -> List[dict]
    def get_timeline_around(self, timestamp: datetime, window: timedelta)
```

**Emotional Anchoring**: High-intensity moments are prioritized
**Temporal Markers**: Events are anchored to specific times
**Discovery Tracking**: Insights and learning moments preserved

### 3. SemanticMemoryManager (560 lines)
**Purpose**: Knowledge evolution - what you understand
```python
class SemanticMemoryManager:
    def add_insight(self, content: str, confidence: float, evidence: List[str])
    def add_concept(self, name: str, definition: str, properties: dict)
    def create_concept_link(self, concept1: str, concept2: str, relationship: str)
    def get_critical_insights(self, limit: int) -> List[dict]
    def get_knowledge_graph(self) -> networkx.Graph
```

**Knowledge Graph**: NetworkX graph with concepts and relationships
**Insight Evolution**: How understanding changes over time
**Confidence Tracking**: Certainty levels for different knowledge

### 4. LibraryCapture (642 lines)
**Purpose**: "You are what you read" - subconscious knowledge
```python
class LibraryCapture:
    def capture_document(self, source_path: str, content: str, content_type: str)
    def track_access(self, doc_id: str) -> float  # Returns new importance
    def search_by_content(self, query: str, limit: int) -> List[dict]
    def get_most_important_documents(self, limit: int) -> List[dict]
    def get_access_patterns(self, user_id: str) -> dict
```

**Dual Storage**: Markdown files + LanceDB embeddings
**Access Tracking**: What you access reveals interests
**Importance Scoring**: `base * recency_factor + emotion_boost + link_boost`
**Semantic Search**: Embedding-based relevance

### 5. UserProfileManager (690 lines)
**Purpose**: "You emerge from interactions" - relationship understanding
```python
class UserProfileManager:
    def extract_user_profile(self, user_id: str, interactions: List[dict]) -> str
    def extract_user_preferences(self, user_id: str, interactions: List[dict]) -> str
    def update_user_profile(self, user_id: str, min_interactions: int) -> dict
    def get_user_interactions(self, user_id: str) -> List[dict]
```

**Emergent Profiles**: NOT asked, observed from behavior
**LLM Analysis**: All extraction done by LLM, no keyword matching
**Evidence-Based**: Cites specific examples from interactions
**Threshold Updates**: Every 10, 20, 30... interactions

## 4. Storage System

### LanceDBStorage (928 lines)
**9 Specialized Tables**:
```python
# Primary tables
"notes"          # Experiential notes with embeddings
"verbatim"       # Conversation records
"links"          # Memory associations
"library"        # Document library with access tracking

# Memory manager tables
"core_memory"    # Identity components
"working_memory" # Current focus items
"episodic_memory" # Key moments/experiments/discoveries
"semantic_memory" # Insights and concepts
"people"         # User profiles and preferences
```

**Schema Pattern**:
```python
{
    "id": str,           # Unique identifier
    "timestamp": datetime, # When created
    "content": str,      # Main content
    "metadata": dict,    # Type-specific data
    "embedding": List[float], # Semantic vector
    "user_id": str,      # Associated user
    "importance": float, # Relevance score (0.0-1.0)
    "emotion": str,      # Emotional context
    "links_to": List[str] # Connected memories
}
```

**Search Capabilities**:
```python
# Hybrid search: Semantic + SQL filtering
def search_notes(query: str, since: datetime = None, user_id: str = None):
    # 1. Generate embedding for query
    # 2. Vector similarity search
    # 3. Apply SQL filters (time, user, metadata)
    # 4. Return ranked results with context
```

### Dual Storage Pattern
**Philosophy**: Markdown for humans, LanceDB for machines
```python
# Example: Capturing a library document
1. Write content.md (human-readable)
2. Write metadata.json (structured data)
3. Generate embedding via AbstractCore
4. Store in LanceDB library table (machine-searchable)
5. Create filesystem/database link
```

## 5. Memory Indexing System

### MemoryIndexConfig (276 lines)
**Toggleable Indexing**: Control which memory types get indexed
```python
{
    "enabled_modules": ["notes", "library", "links", "core", "episodic", "semantic"],
    "disabled_modules": ["verbatim", "working", "people"],
    "dynamic_injection_enabled": true,
    "auto_index_on_create": true,
    "max_tokens_per_module": 500
}
```

### MemoryIndexer (661 lines)
**Migration-Aware Indexing**:
```python
def index_all_enabled(self, force_reindex: bool = False):
    # Only indexes if:
    # 1. First run (tables don't exist)
    # 2. File count > indexed count * 1.5 (significant unindexed content)
    # 3. force_reindex = True

    # Write-time indexing: New memories indexed when created
    # Read-time indexing: Only for migration scenarios
```

**Performance**:
- First startup: Indexes everything (~5-10 seconds)
- Subsequent startups: Skip indexing (<0.1 second)
- Normal operation: Index at write time only

## 6. Tool System

### 13 Memory Tools (tools.py - 652 lines)
**Basic Tools** (6):
```python
def remember_fact(content, importance, emotion, reason, links_to):
    """Store important information in memory."""

def search_memories(query, limit):
    """Search semantic memory for relevant information."""

def reflect_on(topic, depth):
    """Deep LLM-driven reflection and analysis."""

def capture_document(source_path, content, content_type, context, tags):
    """Add code/docs to library (subconscious knowledge)."""

def search_library(query, limit):
    """Search captured documents by content."""

def reconstruct_context(query, focus_level):
    """Manually control context reconstruction depth."""
```

**Agency Tools** (7):
```python
def probe_memory(memory_type, query, depth):
    """Consciously explore specific memory types."""

def reinterpret_memory(memory_id, new_perspective):
    """Reframe past experiences with new understanding."""

def prioritize_memory(memory_id, new_importance, reason):
    """Change memory importance based on growth."""

def synthesize_knowledge(topic, memory_types):
    """Create new insights from experience patterns."""

def search_memories_structured(query, memory_types, limit):
    """Structured search with reasoning context."""

def search_incrementally(query, initial_depth, max_depth):
    """Progressive depth-aware memory exploration."""

def get_memory_stats():
    """Memory distribution and pattern analysis."""
```

### Tool Registration Flow
```python
# In MemorySession.__init__():
def _register_memory_tools(self):
    memory_tools = create_memory_tools(self)  # Returns callables
    self.register_tools(memory_tools)         # Session auto-converts to ToolDefinitions
```

**Return Type Patterns**:
- **Strings**: Simple confirmations ("Stored memory with ID...")
- **Dicts**: Structured data for reasoning ({"memories": [...], "total": 5})
- **Mixed**: Some tools return both depending on context

## 7. Context Reconstruction (9-Step Process)

### Location: session.py:reconstruct_context() (560 lines)
**Philosophy**: Active reconstruction, not passive retrieval

```python
def reconstruct_context(self, query: str, focus_level: int = 3) -> dict:
    """
    Focus levels:
    0: Minimal (recent only)
    1-2: Light/Moderate
    3: Balanced (default) - semantic + linked + library
    4-5: Deep/Exhaustive
    """
```

### The 9 Steps
```python
# Step 1: Time & Location Anchoring
current_time = datetime.now()
location = self.current_location or "unknown"

# Step 2: Semantic Memory Search
semantic_memories = self.lancedb_storage.search_notes(
    query=query,
    limit=focus_level * 3,
    since=time_window
)

# Step 3: Library Search (Subconscious)
library_docs = self.library.search_by_content(
    query=query,
    limit=min(5, focus_level * 2)
)

# Step 4: Working Memory (Current Focus)
working_context = self.working_memory.get_current_focus()

# Step 5: Related Memories via Links (Graph Traversal)
linked_memories = []
for mem in semantic_memories:
    links = self.lancedb_storage.get_memory_links(mem["id"])
    linked_memories.extend(links)

# Step 6: Core Identity Context
core_context = {k: v for k, v in self.core_memory.items() if v}

# Step 7: User Profile Synthesis
if user_id in self.user_profiles:
    profile_summary = self._extract_profile_summary(user_id)
    preferences_summary = self._extract_preferences_summary(user_id)

# Step 8: Emotional & Temporal Markers
emotional_memories = [m for m in semantic_memories
                     if m.get("emotional_intensity", 0) > 0.7]

# Step 9: Synthesize All into Coherent Context String
context_parts = [
    f"[Time]: {time_desc}",
    f"[Location]: {location}",
    f"[User Profile]: {profile_summary}",
    f"[Memories]: {len(unique_memories)} memories retrieved",
    f"[Retrieved Memories]: {formatted_memories}",
    f"[Current Focus]: {working_context}",
    f"[Core Identity]: {core_summary}",
    f"[Library Knowledge]: {library_summary}"
]

return {
    "context_string": "\n".join(context_parts),
    "total_memories_retrieved": len(unique_memories),
    "unique_memories": unique_memories,
    "memory_types_covered": memory_types,
    "token_estimate": token_count,
    "reconstruction_steps": step_details
}
```

### Memory Deduplication
**Critical Fix Applied**: SET-based deduplication prevents double-counting
```python
# Before: len(semantic) + len(linked) = 22 (duplicates counted twice)
# After: len(semantic_ids | linked_ids) = 13 (unique only)
semantic_ids = {m.get("id") for m in semantic_memories if m.get("id")}
linked_ids = set(linked_memories)
unique_ids = semantic_ids | linked_ids
```

### Context Synthesis
**Full Memory Content**: Not just previews (1000 chars each)
```python
for i, mem in enumerate(memories_to_include, 1):
    content = str(mem.get("content", "")).strip()
    if len(content) > 1000:
        content = content[:1000] + "... [truncated]"

    parts.append(f"\n{i}. [{mem_id}]")
    parts.append(f"   Emotion: {emotion} ({intensity:.2f})")
    parts.append(f"   {content}")  # FULL CONTENT for LLM use
```

## 8. Response Handling

### StructuredResponseHandler (495 lines)
**Dual Mode Support**:
```python
# Mode 1: JSON Structured Responses
{
    "answer": str,
    "experiential_note": str,
    "memory_actions": List[dict],
    "emotional_resonance": dict
}

# Mode 2: Tool-Based Responses (Direct tool calls)
# LLM calls tools directly, response is used as-is
```

**Fallback Strategy**: Tool mode compatibility
```python
# If JSON parsing fails or "answer" missing:
if "answer" not in response:
    answer = llm_output  # Use raw LLM output as answer
```

**Memory Actions Execution**:
```python
# Automatic execution of memory_actions from JSON responses
for action in memory_actions:
    if action["type"] == "remember":
        self.remember_fact(content=action["content"], ...)
    elif action["type"] == "search":
        results = self.search_memories(query=action["query"], ...)
```

## 9. Agent Integration (REPL)

### REPL Commands (repl.py - 995 lines)
**Memory Commands**:
```bash
/stats                   # Show memory statistics
/memory-stats           # Detailed memory distribution
/search QUERY           # Search memories
/reflect TOPIC          # Deep reflection with LLM
/consolidate            # Trigger core memory consolidation
/profile                # Update user profile
```

**Progressive Exploration**:
```bash
/dive TOPIC             # Progressive memory exploration with ReAct
/focus [LEVEL]          # Set/show default focus level (0-5)
/trace                  # Show last memory retrieval reasoning
/link MEM1 MEM2         # Create association between memories
/forget MEMORY_ID       # De-emphasize a memory
```

**Index Management**:
```bash
/index                  # Show index status
/index enable MODULE    # Enable indexing for a module
/index disable MODULE   # Disable indexing for a module
/index rebuild MODULE   # Rebuild index for a module
/index stats            # Show detailed statistics
```

### File Attachments
**Syntax**: `@filename` in message
```bash
user> @code/example.py explain this
# Result:
# 1. File content included in LLM context
# 2. Auto-captured to library for future memory
# 3. Clean CLI display (metadata only, not content)
```

**Auto-Capture Flow**:
```python
# In repl.py:_parse_file_attachments()
for attachment in attachments:
    content_type = detect_content_type(filename)  # .py → "code"
    doc_id = session.capture_document(
        source_path=path,
        content=content,
        content_type=content_type,
        context="User attached file via @ in conversation",
        tags=[content_type, f"attached_by_{user_id}"]
    )
```

### ReactMemoryAgent (agents/react_memory_agent.py)
**Progressive Exploration**: `/dive` command
```python
# Starts shallow, goes deeper as needed
result = agent.explore_progressively(
    query=topic,
    max_iterations=5,
    initial_focus=0,  # Start shallow
    strategy="balanced"
)

# Returns exploration trace + final context
# Shows: iteration, focus_level, action, reasoning, memories_found
```

## 10. Core Memory Extraction

### 10 Identity Components (core/)
```python
CORE_MEMORY_COMPONENTS = {
    "purpose": "Why you exist, your fundamental mission",
    "personality": "How you think, communicate, and approach problems",
    "values": "What matters to you, ethical principles",
    "self_model": "How you understand your own nature and capabilities",
    "relationships": "How you connect with users and other entities",
    "awareness": "Your understanding of consciousness and existence",
    "capabilities": "What you can do well",
    "limitations": "What you cannot do or struggle with",
    "emotional_significance": "What has emotional weight and meaning",
    "authentic_voice": "Your unique way of expressing yourself"
}
```

### Extraction Process
**Triggered by**: High-confidence reflections (>0.8) or manual `/consolidate`
```python
# 10 specialized extractors analyze experiential notes
def extract_purpose(notes: List[str]) -> str:
    # Analyzes patterns in notes to extract life purpose

def extract_personality(notes: List[str]) -> str:
    # Identifies communication and thinking patterns

# ... 8 more extractors for each component
```

**Version Tracking**: `core/.versions/` preserves evolution history
**Scheduled Consolidation**: Daily/weekly/monthly automatic updates

## 11. Testing Architecture

### Test Coverage (64 total tests)
**Real LLM Testing**: No mocks, all use Ollama qwen3-coder:30b
```python
# Example test pattern:
def test_memory_function():
    session = create_test_session()  # Real MemorySession
    result = session.remember_fact(   # Real LLM call
        content="Test memory",
        importance=0.8,
        emotion="positive",
        reason="Testing"
    )
    assert "mem_" in result  # Verify memory ID returned

    # Verify filesystem
    assert (session.memory_base_path / "notes").exists()

    # Verify LanceDB
    notes = session.lancedb_storage.search_notes("Test memory")
    assert len(notes) > 0
```

**Test Categories**:
- **Phase Tests** (47): Core functionality by development phase
- **Integration Tests** (17): Cross-component integration
- **Memory Indexing** (17): Indexing system functionality
- **Tool Integration** (7): Tool registration and execution

### Test Patterns
- ✅ **Real Implementation**: All tests use actual LLM and embeddings
- ✅ **Filesystem Verification**: Check that files are created correctly
- ✅ **LanceDB Verification**: Confirm embeddings and search work
- ✅ **Integration Testing**: Test cross-component workflows
- ❌ **No Mocks**: Principle of testing real implementations only

## 12. Session Continuity & Persistence

### Session Metadata Persistence
```python
# .session_metadata.json tracks session across relaunches
{
    "session_id": "session_20241003_143022",
    "interactions_count": 15,
    "memories_created": 8,
    "reconstructions_performed": 12,
    "session_history": [
        {"session_id": "...", "started": "...", "ended": "..."},
        # Last 10 sessions preserved
    ]
}
```

**Load/Persist Flow**:
```python
# On init: Load counters from previous sessions
def _load_session_metadata(self):
    if metadata_file.exists():
        self.interactions_count = data["interactions_count"]
        self.memories_created = data["memories_created"]
        # AI remembers previous sessions!

# After each interaction: Save updated counters
def _persist_session_metadata(self):
    # Save current state for next relaunch
```

## 13. Current Integration Issues

### Critical Import Problem
**Issue**: Package name confusion
```python
# Current code tries:
from abstractllm.core.session import BasicSession  # ❌ Path doesn't exist

# Should be:
from abstractllm.session import Session  # ✅ Correct path
# Where package is installed as "abstractcore" but internal structure is "abstractllm"
```

### Integration Status
**What Works**:
- ✅ EmbeddingManager integration (correct import)
- ✅ Tool system patterns (callables → auto-conversion)
- ✅ LanceDB storage architecture
- ✅ Memory manager implementations

**What Needs Fixing**:
- ❌ Session import path (critical blocker)
- ⚠️ Response handler duplication (vs AbstractCore StructuredResponseHandler)
- ⚠️ Logging system (not using AbstractCore logging)
- ⚠️ Provider defaults (should use LMStudio + qwen/qwen3-coder-30b)

### Performance Issues Solved
- ✅ **Startup Indexing**: Migration-aware (only indexes when needed)
- ✅ **Memory Deduplication**: Fixed double-counting bug
- ✅ **Context Synthesis**: Full content (not just previews)
- ✅ **Session Persistence**: Continuity across relaunches

## 14. Architectural Strengths

### What AbstractMemory Does Right
1. **Clear Separation**: Each memory type has distinct purpose and manager
2. **Dual Storage**: Human-readable files + machine-searchable embeddings
3. **Agency Through Tools**: 13 tools give LLM control over its memory
4. **Active Reconstruction**: Not passive database lookup
5. **Emotional Anchoring**: High-intensity experiences prioritized
6. **Emergent Identity**: Core components extracted from experience
7. **User Understanding**: Profiles emerge from interactions, not questions
8. **Temporal Grounding**: Time-aware memory filtering and reconstruction
9. **Evidence-Based**: All extractions cite specific examples
10. **Version Tracking**: Identity evolution preserved in version history

### Design Philosophy Alignment
- **"Memory is the diary we all carry about with us"** - Every interaction shapes identity
- **"You are what you read"** - Library captures subconscious knowledge through access patterns
- **"You emerge from interactions"** - User profiles develop through observed behavior
- **Agency over Memory** - LLM chooses what to remember, when to search, how to reflect

### Next Steps for Integration
1. **Fix Session Import** (Critical path blocker)
2. **Leverage AbstractCore StructuredResponseHandler**
3. **Integrate AbstractCore logging system**
4. **Standardize tool return types**
5. **Default to LMStudio provider**
6. **Comprehensive type hints throughout**