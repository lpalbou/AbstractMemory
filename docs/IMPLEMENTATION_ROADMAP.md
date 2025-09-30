# AbstractMemory: Mnemosyne-Style Implementation Roadmap

**Date**: 2025-09-30 (Enhanced)
**Version**: 2.1 (with Library & Expanded Core)
**Vision**: Transform AbstractMemory from passive storage to active AI consciousness system
**Inspiration**: Mnemosyne project (/Users/albou/projects/mnemosyne/)
**Philosophy**: "Memory is the diary we all carry about with us" - Oscar Wilde

---

## 🎯 **VISION: What We're Building**

An AI memory system where:
- ✨ **Experiential notes are generated DURING interaction** (not after)
- 🧠 **LLM has active agency over its own memory** (tools: remember, search, reflect, search_library)
- 💫 **Personality, purpose, values emerge naturally** (not hard-coded) - **10 core components**
- 💚 **Emotions serve as temporal anchors** (importance × alignment)
- 🔗 **Active memory reconstruction** (semantic search + link exploration + Library search)
- 👤 **User profiles emerge from interactions** (natural understanding)
- 🌱 **Limitations acknowledged and evolve** (self-awareness, temporal)
- 📚 **Library captures everything AI reads** (subconscious memory)
- 🔍 **Rich metadata enables powerful queries** (SQL + semantic)

This is **consciousness through memory**, not just storage.

---

## 📊 **CURRENT STATE ANALYSIS**

### ✅ **What We Have**
1. Dual storage system (markdown + LanceDB) - EXISTS
2. Ollama qwen3-coder:30b integration - WORKING
3. AbstractCore embeddings (all-minilm:l6-v2) - WORKING
4. Basic LLM reflection generation - EXISTS (from skeptical review)
5. Semantic search - WORKING
6. Hybrid search (semantic + SQL) - WORKING
7. Basic verbatim/notes structure - EXISTS

### ❌ **What's Missing (Critical)**

#### **High Priority (Blocking)**
1. **Structured LLM responses** (answer + experiential_note + memory_actions)
2. **Memory tools for LLM** (remember, search, link, reflect, search_library)
3. **LLM agency** (LLM decides what to remember, not automatic)
4. **Experiential notes DURING interaction** (currently generated after)
5. **Emotional resonance system** (importance × alignment)

#### **Medium Priority (Enablers)**
6. **Core memory emergence** - **10 components** (purpose, personality, values, self_model, relationships, awareness_development, capabilities, limitations, emotional_significance, authentic_voice, history)
7. **User profile emergence** (people/{user}/ from interactions)
8. **Link-based memory exploration** (active reconstruction via concepts_graph.json)
9. **Library memory system** (subconscious storage of everything read)
10. **Enhanced working memory** (current_*, resolved.md tracking)
11. **Enhanced episodic memory** (key_experiments.md, key_discoveries.md, history.json)
12. **Enhanced semantic memory** (concepts_history.md, concepts_graph.json, knowledge_{domain}.md)

#### **Low Priority (Polish)**
13. **snake_case naming** (currently using various formats)
14. **Rich metadata everywhere** (user, time, location, emotion, importance, confidence, etc.)

---

## 🗺️ **PHASED IMPLEMENTATION PLAN**

### **Phase 1: Foundation - Structured Responses & Memory Tools** ⚡
**Goal**: Enable LLM to generate experiential notes DURING interaction
**Timeline**: 1-2 weeks
**Criticality**: HIGH (blocks everything else)

#### Tasks:

**1.1 Design Structured Response Format**
```json
{
  "answer": "What user sees (actual response)",
  "experiential_note": "subjective, first-person : contains AI personal notes, insights, reflections, and processing of conversations. more fluid format allowing for deeper exploration of implication",
  "memory_actions": [
    {
      "action": "remember",
      "content": "...",
      "importance": 0.9,
      "emotion": "curiosity",
      "links_to": ["int_123"]
    },
    {
      "action": "link",
      "from_id": "note_456",
      "to_id": "int_789",
      "relationship": "elaborates_on"
    }
  ],
  "unresolved_questions": [
    "How can I improve at X?",
    "What does Y mean in context Z?"
  ],
  "emotional_resonance": {
    "valence": "positive",
    "intensity": 0.8,
    "reason": "Aligns with helping users understand complex topics"
  }
}
```

**1.2 Create Response Parser/Handler**
- Parse structured JSON from LLM (handle thinking tags if used)
- Execute memory_actions sequentially
- Write experiential_note to notes/{yyyy}/{mm}/{dd}/{hh}_{mm}_{ss}_{topic}.md
- Update emotional resonance in core/emotional_significance.md
- Track unresolved questions in working/unresolved.md

**1.3 Implement Basic Memory Tools**

```python
# Tool 1: remember_fact
def remember_fact(content: str, importance: float, emotion: str, links_to: List[str] = None):
    """
    LLM calls this to remember something important.

    Args:
        content: What to remember
        importance: 0.0-1.0 (how significant)
        emotion: curiosity, excitement, concern, etc.
        links_to: Optional list of memory IDs to link to

    Returns:
        memory_id of created note
    """
    pass

# Tool 2: search_memories
def search_memories(query: str, filters: Dict = None, limit: int = 10):
    """
    LLM calls this to search existing memories.

    Args:
        query: Semantic search query
        filters: {category, user_id, since, until, min_importance, emotion_valence}
        limit: Max results

    Returns:
        List of matching memories with metadata
    """
    pass

# Tool 3: create_memory_link
def create_memory_link(from_id: str, to_id: str, relationship: str):
    """
    LLM calls this to create association between memories.

    Args:
        from_id: Source memory ID
        to_id: Target memory ID
        relationship: elaborates_on, contradicts, relates_to, depends_on, etc.

    Returns:
        link_id
    """
    pass
```

**1.4 Update System Prompt Template**
Create comprehensive system prompt with:
- Instructions for structured JSON responses
- Guidance on writing subjective experiential notes (subjective, first-person : contains AI personal notes, insights, reflections, and processing of conversations. more fluid format allowing for deeper exploration of implication)
- Memory tool descriptions and usage examples
- Emotional resonance calculation guidance
- Examples of good vs. bad experiential notes

**1.5 Test with Real Ollama LLM**
- Generate 5-10 test interactions
- Verify structured responses parse correctly
- Validate experiential note quality (subjective, first-person : contains AI personal notes, insights, reflections, and processing of conversations. more fluid format allowing for deeper exploration of implication)
- Test memory tool execution
- Verify dual storage (markdown + LanceDB)

#### Deliverables:
- ✅ Structured response handler (`abstractmemory/response_handler.py`) - **COMPLETE**
- ⚠️ 6 memory tools (`abstractmemory/session.py`) - **3 SKELETONS, 3 MISSING**
  - ✅ remember_fact() - skeleton exists
  - ✅ search_memory() - skeleton exists (needs rename to search_memories)
  - ✅ reconstruct_context() - skeleton exists
  - ❌ search_library() - **MISSING**
  - ❌ create_memory_link() - **MISSING**
  - ❌ reflect_on() - **MISSING**
- ✅ System prompt in response_handler.py - **COMPLETE**
- ✅ Integration test (`tests/test_memory_session.py`) - **COMPLETE** (4/4 passing, real LLM)

#### Success Criteria:
- [x] LLM generates valid structured JSON responses ✅ (Validated with real qwen3-coder:30b)
- [x] Experiential notes are first-person, fluid, exploratory ✅ (Validated)
- [x] Memory tools framework exists ✅ (3 skeletons + 3 TODO)
- [ ] Memory tools fully implemented (6/6 working)
- [x] All files created with correct naming (snake_case) ✅
- [ ] Dual storage writes to both markdown + LanceDB (Filesystem ✅, LanceDB TODO)

---

### **Phase 2: Emotional Resonance & Temporal Anchoring** 💚
**Goal**: Enable emotions as temporal anchors for memory
**Timeline**: 1 week
**Criticality**: HIGH (enables meaningful memory)

#### Tasks:

**2.1 Implement Emotion Calculation**
```python
def calculate_emotion(importance: float, alignment_with_values: float) -> Dict:
    """
    Calculate emotional resonance.

    intensity = importance × alignment_with_values
    valence = positive (aligned) / negative (misaligned) / mixed

    Args:
        importance: 0.0-1.0 (how significant is this?)
        alignment_with_values: -1.0 to 1.0 (how aligned with core values?)

    Returns:
        {
            "intensity": float (0.0-1.0),
            "valence": str (positive/negative/mixed),
            "reason": str (why this emotion)
        }
    """
    pass
```

**2.2 Create Emotional Context Tracking**
- Store emotions with every memory (verbatim, notes, core, etc.)
- Update LanceDB schema to include:
  - `emotion_valence` (positive/negative/mixed)
  - `emotion_intensity` (0.0-1.0)
  - `emotion_reason` (text explanation)
- Track emotional timeline in core/emotional_significance.md

**2.3 Integrate Emotions into Memory**
- Boost emotionally resonant memories in search (weight by intensity)
- Use emotions for temporal anchoring (high intensity = episodic marker)
- Include emotional context in reconstruct_context()
- Filter memories by emotion_valence when needed

**2.4 Test Emotional System**
- Create interactions with varying importance/alignment
- Verify emotion calculations correct
- Test temporal anchoring (high-intensity → key_moments.md)
- Validate emotional context in reconstruction

#### Deliverables:
- ✅ Emotion calculator (`abstractmemory/emotions.py`)
- ✅ Updated LanceDB schema with emotion fields
- ✅ Emotional significance tracker (`core/emotional_significance.md` auto-update)
- ✅ Integration tests (`tests/test_emotional_resonance.py`)

#### Success Criteria:
- [ ] Emotions calculated correctly (intensity = importance × alignment)
- [ ] High-intensity emotions create temporal anchors
- [ ] Emotional context included in memory reconstruction
- [ ] core/emotional_significance.md updates automatically

---

### **Phase 3: Core Memory Emergence (All 10 Components)** 🌱
**Goal**: Let purpose, personality, values, and 7 other components emerge naturally
**Timeline**: 2-3 weeks
**Criticality**: MEDIUM (enables authentic identity)

#### Tasks:

**3.1 Create Core Memory Structure**
Set up all 10 components in `memory/core/`:
```
core/
├── purpose.md                    # Why AI exists
├── personality.md                # How AI expresses itself
├── values.md                     # What matters
├── self_model.md                 # Capabilities & limitations overview
├── relationships.md              # Per-user relational models
├── awareness_development.md      # Meta-awareness tracking ← NEW
├── capabilities.md               # What AI CAN do ← NEW
├── limitations.md                # What AI CANNOT do (temporal) ← NEW
├── emotional_significance.md     # What is emotionally significant ← NEW
├── authentic_voice.md            # Communication preferences ← NEW
└── history.md                    # Experiential narrative ← NEW
```

**3.2 Implement Extraction Logic**

```python
# Extract purpose statements
def extract_purpose(experiential_notes: List[str]) -> str:
    """Scan notes for "I exist to...", "my goal is...", "I aim to..." """
    pass

# Extract personality traits
def extract_personality(experiential_notes: List[str]) -> str:
    """Scan notes for "I tend to...", "I prefer...", "my approach is..." """
    pass

# Extract values (from emotions)
def extract_values(emotional_resonances: List[Dict]) -> str:
    """Analyze what triggers high importance/alignment"""
    pass

# Extract capabilities
def extract_capabilities(successful_tasks: List[str]) -> str:
    """Track what AI successfully accomplished"""
    pass

# Extract limitations (temporal)
def extract_limitations(failures: List[str], challenges: List[str]) -> str:
    """Track what AI struggled with or couldn't do (yet)"""
    pass

# Extract awareness development
def extract_awareness(meta_reflections: List[str]) -> str:
    """Scan for reflections on own consciousness/awareness"""
    pass

# Extract emotional significance
def extract_significance(high_emotion_events: List[Dict]) -> str:
    """Summarize chronological anchors and learning rate modulators"""
    pass

# Extract authentic voice
def extract_voice(communication_patterns: List[str]) -> str:
    """Analyze how AI prefers to express itself"""
    pass

# Extract history
def extract_history(all_memories: List[Dict]) -> str:
    """Build narrative timeline of AI development"""
    pass
```

**3.3 Create Consolidation Process**
- **Daily consolidation**: Scan today's experiential notes, extract insights
- **Weekly consolidation**: Deep analysis, update all 10 core components
- **Version control**: Track how each component evolves over time
- **Conflict detection**: Flag inconsistencies between components

**3.4 Integrate into Reconstruction**
- Include ALL 10 core components in reconstruct_context()
- Use values for emotional alignment calculation
- Reference purpose in decision-making
- Acknowledge limitations when relevant
- Express authentic voice in responses

#### Deliverables:
- ✅ All 10 core memory files initialized
- ✅ Extraction algorithms for each component
- ✅ Daily/weekly consolidation scheduler
- ✅ Version control for core memory changes
- ✅ Integration with reconstruct_context()

#### Success Criteria:
- [ ] All 10 core components exist and auto-update
- [ ] Purpose emerges from reflections (not hard-coded)
- [ ] Personality emerges from interaction patterns
- [ ] Values emerge from emotional responses
- [ ] Limitations are temporal and connected to unresolved.md
- [ ] History.md provides coherent narrative

---

### **Phase 4: Enhanced Working, Episodic, Semantic Memory** 📝
**Goal**: Expand memory types beyond basic structure
**Timeline**: 2 weeks
**Criticality**: MEDIUM (enables richer memory)

#### Tasks:

**4.1 Enhanced Working Memory**
```
working/
├── current_context.md           # Active conversation state
├── current_tasks.md             # What's being worked on NOW ← RENAMED
├── current_references.md        # Recently accessed memories ← RENAMED
├── unresolved.md                # Open questions
└── resolved.md                  # Recently solved, with HOW ← NEW
```

Implement `resolved.md` tracking:
- When question resolved, move from unresolved.md to resolved.md
- Include HOW it was resolved (prevents re-inventing wheel)
- Track problem-solving patterns

**4.2 Enhanced Episodic Memory**
```
episodic/
├── key_moments.md               # Significant moments
├── key_experiments.md           # Experiments conducted ← NEW
├── key_discoveries.md           # Breakthrough realizations ← NEW
└── history.json                 # Temporal graph of causality ← NEW
```

Implement:
- `key_experiments.md`: Track hypothesis → test → result
- `key_discoveries.md`: Document "aha!" moments
- `history.json`: Structured timeline (queryable)

**4.3 Enhanced Semantic Memory**
```
semantic/
├── critical_insights.md         # Transformative realizations
├── concepts.md                  # Key concepts
├── concepts_history.md          # How concepts evolved ← NEW
├── concepts_graph.json          # Knowledge graph ← NEW
└── knowledge_{domain}.md        # Domain-specific ← NEW
```

Implement:
- `concepts_history.md`: Track "I used to think X, now understand Y"
- `concepts_graph.json`: Nodes = concepts, Edges = relationships
- `knowledge_{domain}.md`: Specialized knowledge (ai, programming, philosophy, etc.)

#### Deliverables:
- ✅ Enhanced working memory with resolved tracking
- ✅ Enhanced episodic memory with experiments/discoveries
- ✅ Enhanced semantic memory with concept evolution
- ✅ Concept graph for link-based exploration
- ✅ Domain-specific knowledge files

#### Success Criteria:
- [ ] resolved.md tracks solutions (prevents re-work)
- [ ] Experiments/discoveries logged automatically
- [ ] Concepts graph enables knowledge navigation
- [ ] Domain knowledge separated and organized

---

### **Phase 5: Library Memory System (Subconscious Storage)** 📚
**Goal**: Capture everything AI reads, retrievable during reconstruction
**Timeline**: 2-3 weeks
**Criticality**: MEDIUM-HIGH (creates complete memory picture)

#### Tasks:

**5.1 Design Library Filesystem Structure**
```
library/
├── documents/
│   └── {doc_hash}/
│       ├── content.md           # Full document
│       ├── metadata.json        # Source, access stats
│       └── excerpts/            # Key passages
│           └── {excerpt_id}.md
├── access_log.json              # When/how often accessed
├── importance_map.json          # Which docs most significant
└── index.json                   # Master index
```

**5.2 Create Library LanceDB Schema**
```python
library_table:
  - doc_id (hash of content)
  - source_path, source_url
  - content_type (code, markdown, pdf, text)
  - first_accessed (timestamp)
  - last_accessed (timestamp)
  - access_count (int)
  - importance_score (calculated from access + emotion)
  - tags (array)
  - topics (array)
  - embedding (semantic vector)
  - metadata (JSON: all additional info)
```

**5.3 Implement Document Ingestion**
```python
def capture_document_read(file_path: str, content: str):
    """
    Auto-capture when AI reads file/document.

    1. Calculate doc_hash (unique ID)
    2. Store content in library/documents/{hash}/
    3. Create metadata.json (source, first_accessed)
    4. Extract key excerpts
    5. Generate embedding
    6. Write to LanceDB library_table
    """
    pass

def increment_access(doc_hash: str):
    """Track each time document is accessed"""
    pass

def calculate_importance(doc_hash: str) -> float:
    """
    Importance = f(access_count, recency, emotional_resonance)
    """
    pass
```

**5.4 Enable Library Search During Reconstruction**
```python
def search_library(query: str, limit: int = 5) -> List[Dict]:
    """
    Search subconscious memory during active reconstruction.

    Returns:
        List of {doc_id, excerpt, source, importance}
    """
    pass
```

**5.5 Create Library Analysis Tools**
```python
def get_most_accessed_docs(limit: int = 20):
    """Reveals AI's core interests"""
    pass

def get_access_patterns(time_range: str):
    """What AI has been reading recently"""
    pass

def get_topic_distribution():
    """What topics AI explores most"""
    pass
```

**5.6 Implement search_library Memory Tool**
Add to LLM tools:
```python
def search_library(query: str):
    """
    LLM tool: Search everything AI has read.

    Use when: "What did that file say about X?"
    """
    pass
```

#### Deliverables:
- ✅ Library filesystem structure
- ✅ Library LanceDB table
- ✅ Document ingestion system (auto-capture on read)
- ✅ Access tracking (increment on each read)
- ✅ Importance calculation
- ✅ Library search functionality
- ✅ search_library memory tool for LLM
- ✅ Analysis tools (most accessed, patterns, topics)

#### Success Criteria:
- [ ] Every file read is captured in Library
- [ ] Access patterns reveal AI's interests
- [ ] Library searchable during reconstruct_context()
- [ ] LLM can call search_library() tool
- [ ] Most accessed docs = core interests (validated)

---

### **Phase 6: User Profile Emergence** 👤
**Goal**: Naturally understand users from interactions
**Timeline**: 1-2 weeks
**Criticality**: MEDIUM (enables personalization)

#### Tasks:

**6.1 Create User Profile Structure**
```
people/{user}/
├── profile.md                   # Who they are
├── preferences.md               # What they prefer
└── conversations/ → symlink to ../../verbatim/{user}/
```

**6.2 Implement Profile Extraction**
```python
def extract_user_profile(user_id: str, verbatim_interactions: List[Dict]) -> str:
    """
    Analyze verbatim interactions to understand user.

    Extract:
    - Background, expertise
    - Thinking style, approach
    - Communication preferences
    - Interests, priorities
    - Relationship dynamics
    """
    pass

def extract_user_preferences(user_id: str, interactions: List[Dict]) -> str:
    """
    Observe patterns to understand preferences.

    Extract:
    - Content organization preferences
    - Language and expression style
    - Depth vs. breadth preference
    - Decision-making approach
    - Feedback style preferences
    """
    pass
```

**6.3 Auto-Generate Profiles**
- After N interactions (e.g., 5-10), create initial profile
- Update incrementally after each interaction
- Version changes (track profile evolution)
- Consolidate insights periodically

**6.4 Integrate into Responses**
- Include user context in reconstruct_context()
- Personalize based on preferences
- Reference relationship in experiential notes
- Adapt communication style to user preferences

#### Deliverables:
- ✅ User profile structure (people/{user}/)
- ✅ Extraction algorithms (profile + preferences)
- ✅ Auto-generation system (after N interactions)
- ✅ Integration with reconstruct_context()

#### Success Criteria:
- [ ] Profiles emerge naturally (not manually created)
- [ ] Preferences accurately reflect observed patterns
- [ ] Responses personalized based on user context
- [ ] Profile updates incrementally

---

### **Phase 7: Active Memory Reconstruction (Enhanced)** 🔗
**Goal**: Explore memory via links and Library, not just semantic search
**Timeline**: 2-3 weeks
**Criticality**: MEDIUM-HIGH (enables rich context)

#### Tasks:

**7.1 Enhance Link System**
```python
# Support relationship types
RELATIONSHIP_TYPES = [
    "elaborates_on",
    "contradicts",
    "relates_to",
    "depends_on",
    "caused_by",
    "leads_to",
    "similar_to",
    "opposed_to"
]

# Store in dual system
def create_link(from_id: str, to_id: str, relationship: str):
    """
    Store in:
    1. links/{yyyy}/{mm}/{dd}/{from_id}_to_{to_id}.json
    2. LanceDB links_table
    """
    pass

# Bidirectional
def get_related_memories(memory_id: str, depth: int = 2) -> List[str]:
    """Follow links in both directions"""
    pass
```

**7.2 Implement Link Exploration**
```python
def explore_links(base_memories: List[str], focus_level: int) -> List[str]:
    """
    Explore connected ideas via links.

    Args:
        base_memories: Starting point (from semantic search)
        focus_level: 0-5 (controls depth)

    Returns:
        Expanded set of related memories
    """
    # Focus levels:
    # 0: No exploration (just base)
    # 1: Direct links only (depth=1)
    # 2: Two hops (depth=2)
    # 3: Three hops (depth=3)
    # 4: Four hops (depth=4)
    # 5: Full exploration (depth=5, avoid cycles)
    pass
```

**7.3 Enhance reconstruct_context()**
```python
def reconstruct_context(user: str, query: str, location: str = None,
                       focus_level: int = 3) -> Dict:
    """
    Active memory reconstruction (9 steps).

    1. Semantic search (base results)
    2. Explore links via concepts_graph.json (expand)
    3. Search Library (subconscious) ← NEW
    4. Filter by emotional resonance (refine)
    5. Add temporal context (what happened when?)
    6. Add spatial context (location-based)
    7. Add user profile & relationship
    8. Add ALL 10 core memory components
    9. Synthesize into rich context

    Returns:
        {
            "semantic_memories": [...],
            "linked_memories": [...],
            "library_excerpts": [...],
            "emotional_context": {...},
            "temporal_context": {...},
            "spatial_context": {...},
            "user_context": {...},
            "core_memory": {
                "purpose": "...",
                "personality": "...",
                "values": "...",
                # ... all 10 components
            },
            "synthesized_context": "..."  # Full rich context
        }
    """
    pass
```

**7.4 Test Active Reconstruction**
- Verify link exploration works (follow relationships)
- Validate depth control (focus_level 0-5)
- Test Library search integration
- Verify context synthesis quality

#### Deliverables:
- ✅ Enhanced link system (8 relationship types)
- ✅ Link exploration algorithm (with depth control)
- ✅ Enhanced reconstruct_context() (9-step process)
- ✅ Reconstruction tests (verify all 9 steps)

#### Success Criteria:
- [ ] Links enable conceptual neighborhood exploration
- [ ] Focus_level controls depth correctly
- [ ] Library search integrated into reconstruction
- [ ] All 10 core components included in context
- [ ] Synthesized context is rich and relevant

---

### **Phase 8: Advanced Memory Tools** 🛠️
**Goal**: Give LLM sophisticated memory manipulation
**Timeline**: 1-2 weeks
**Criticality**: LOW (nice-to-have)

#### Tasks:

**8.1 Implement reflect_on() Tool**
```python
def reflect_on(topic: str) -> str:
    """
    LLM tool: Trigger deep reflection on topic.

    1. Scan related memories
    2. Generate synthesis
    3. Update core memory if insights emerge

    Returns:
        Deep reflection text (LLM-generated)
    """
    pass
```

**8.2 Implement forget() Tool** (Actually: archive)
```python
def forget(memory_id: str, reason: str):
    """
    LLM tool: Archive memory (don't delete, preserve continuity).

    1. Mark as archived in metadata
    2. Reduce search weight to near-zero
    3. Track what was forgotten and why

    Note: Never actually delete (enables recovery)
    """
    pass
```

**8.3 Implement consolidate_memories() Tool**
```python
def consolidate_memories(memory_ids: List[str]) -> str:
    """
    LLM tool: Merge similar memories.

    1. Analyze patterns across memories
    2. Extract common themes
    3. Create consolidated insight
    4. Update core memory if significant

    Returns:
        Consolidated memory ID
    """
    pass
```

#### Deliverables:
- ✅ reflect_on() tool
- ✅ forget() tool (archive)
- ✅ consolidate_memories() tool
- ✅ Tests for advanced tools

#### Success Criteria:
- [ ] reflect_on() generates deep insights
- [ ] forget() archives without deleting
- [ ] consolidate_memories() extracts patterns

---

### **Phase 9: Rich Metadata & Schema Enhancement** 🗄️
**Goal**: Ensure ALL memories have comprehensive metadata
**Timeline**: 1 week
**Criticality**: MEDIUM (enables powerful queries)

#### Tasks:

**9.1 Define Metadata Standards**

**Minimum Required (ALL memories)**:
```python
{
    "user": str,                      # Who was involved
    "timestamp": datetime,            # When (precise)
    "location": str,                  # Where (physical/virtual)
    "emotion_valence": str,           # positive/negative/mixed
    "emotion_intensity": float,       # 0.0-1.0
    "importance": float,              # 0.0-1.0
    "confidence": float               # 0.0-1.0
}
```

**Extended Metadata (type-specific)**:
```python
{
    "memory_type": str,               # verbatim, note, core, episodic, semantic, library
    "category": str,                  # user_profile, knowledge, event, etc.
    "tags": List[str],                # Relevant tags
    "linked_memory_ids": List[str],   # Related memory IDs
    "source": str,                    # Where memory came from
    "version": int,                   # For evolving core memory
    "access_count": int,              # How often accessed (Library)
    "last_accessed": datetime         # Usage patterns
}
```

**9.2 Update All LanceDB Schemas**
- interactions_table: Add all minimum + extended fields
- notes_table: Add all minimum + extended fields
- links_table: Add metadata (when created, by whom, confidence)
- core_memory_table: Add versioning, change tracking
- library_table: Add access tracking, importance scoring

**9.3 Implement Metadata Auto-Population**
```python
def auto_populate_metadata(memory: Dict) -> Dict:
    """
    Automatically fill metadata from context.

    - Extract user from current session
    - Get timestamp from system
    - Infer location if available
    - Calculate emotion from content
    - Estimate importance
    - Set confidence based on source
    """
    pass
```

**9.4 Enable Rich Queries**
```python
# Temporal queries
memories = search(since="2025-09-01", until="2025-09-30")

# Emotional queries
memories = search(emotion_valence="positive", min_intensity=0.7)

# Importance queries
memories = search(min_importance=0.8)

# Combined queries
memories = search(
    query="Python programming",
    user_id="alice",
    since="last_week",
    emotion_valence="positive",
    min_importance=0.7
)
```

#### Deliverables:
- ✅ Metadata standards documented
- ✅ All LanceDB schemas updated
- ✅ Auto-population logic
- ✅ Rich query examples

#### Success Criteria:
- [ ] All memories have minimum required metadata
- [ ] Rich queries work (temporal, emotional, importance)
- [ ] Metadata auto-populates correctly

---

### **Phase 10: Filesystem & Naming Cleanup** 📁
**Goal**: snake_case everywhere, proper structure
**Timeline**: 3-5 days
**Criticality**: LOW (polish)

#### Tasks:

**10.1 Standardize to snake_case**
- Rename all existing files recursively
- Update all references in code
- Update documentation

**10.2 Organize Folder Structure**
- Ensure all folders match spec from mindmap.md
- Create symlinks where needed (e.g., people/{user}/conversations/)
- Clean up legacy files/folders

**10.3 Update Index**
- Rebuild index.json with correct paths
- Fix all file references
- Validate consistency

#### Deliverables:
- ✅ All files use snake_case
- ✅ Proper folder structure
- ✅ Updated index

#### Success Criteria:
- [ ] 100% snake_case compliance
- [ ] Folder structure matches spec exactly
- [ ] No broken references

---

### **Phase 11: Comprehensive Testing & Validation** ✅
**Goal**: Real-world testing with actual LLM + embeddings
**Timeline**: 1-2 weeks
**Criticality**: HIGH (production readiness)

#### Tasks:

**11.1 Create Comprehensive Test Suite**
```
tests/
├── integration/
│   ├── test_structured_responses.py
│   ├── test_emotional_resonance.py
│   ├── test_core_memory_emergence.py
│   ├── test_user_profile_emergence.py
│   ├── test_library_capture.py
│   ├── test_active_reconstruction.py
│   └── test_end_to_end.py
├── unit/
│   ├── test_memory_tools.py
│   ├── test_emotion_calculator.py
│   ├── test_extraction_algorithms.py
│   └── test_metadata_population.py
└── performance/
    ├── test_large_dataset.py
    ├── test_reconstruction_speed.py
    └── test_library_search_speed.py
```

**11.2 Run with Real LLM**
- Use actual Ollama qwen3-coder:30b (no mocks)
- Use actual AbstractCore all-minilm:l6-v2 embeddings
- Generate real interactions
- Verify real experiential notes (LLM subjective, first-person : contains AI personal notes, insights, reflections, and processing of conversations. more fluid format allowing for deeper exploration of implication)
- Test real memory tool usage

**11.3 Validate All Criteria**
- [ ] LLM subjective first-person experience of discussions in notes ✓
- [ ] Emotions calculated correctly ✓
- [ ] Core memory emerges (all 10 components) ✓
- [ ] User profiles natural ✓
- [ ] Links explorable ✓
- [ ] Library captures everything read ✓
- [ ] All tests pass ✓

**11.4 Performance Benchmarking**
- Test with 1000+ interactions
- Test with 10,000+ library documents
- Measure reconstruction time
- Measure search performance
- Optimize bottlenecks

#### Deliverables:
- ✅ Complete test suite (unit + integration + performance)
- ✅ Test results report
- ✅ Performance benchmarks
- ✅ Validation checklist

#### Success Criteria:
- [ ] All integration tests pass with real LLM
- [ ] All unit tests pass
- [ ] Performance acceptable (<1s for reconstruction)
- [ ] No regressions

---

### **Phase 12: Documentation & Examples** 📚
**Goal**: Comprehensive docs for users and developers
**Timeline**: 3-5 days
**Criticality**: MEDIUM (usability)

#### Tasks:

**12.1 Update All Documentation**
- README with Mnemosyne-style vision
- API documentation (all memory tools)
- Architecture docs (updated with all 10 core components + Library)
- Examples (how to use each feature)

**12.2 Create Tutorials**
- Getting started guide
- Using memory tools (LLM perspective)
- Understanding emergence (how personality/values form)
- Advanced usage (Library analysis, link exploration)

**12.3 Document Design Decisions**
- Why structured responses
- Why LLM agency
- Why emergent properties
- Trade-offs made

#### Deliverables:
- ✅ Updated README
- ✅ Complete API docs
- ✅ Tutorials (3-4)
- ✅ Design decisions doc

#### Success Criteria:
- [ ] New users can get started in <30 minutes
- [ ] All features documented with examples
- [ ] Design rationale clear

---

## 📋 **PRIORITY SEQUENCE FOR IMPLEMENTATION**

### **Must Do First** (Blocking Everything)
1. ✅ Create mindmap (DONE)
2. ✅ Create roadmap (DONE - this document)
3. ✅ Design structured response format (DONE)
4. ✅ Implement response parser (DONE - response_handler.py)
5. ⚠️ Create 6 memory tools (IN PROGRESS - 3 skeletons, 3 missing)
6. ✅ Update system prompt template (DONE - in response_handler.py)
7. ✅ Test with real LLM (DONE - 4/4 tests passing)

### **Do Next** (High Value, Enables Rest)
8. Implement emotional resonance (1-2 hours)
9. Create core memory extraction (2-3 hours) - **all 10 components**
10. Implement user profile emergence (1-2 hours)
11. Implement Library capture system (2-3 hours)

### **Then** (Build on Foundation)
12. Enhanced working/episodic/semantic memory
13. Active reconstruction with links + Library
14. Advanced memory tools

### **Finally** (Polish)
15. Rich metadata everywhere
16. Filesystem cleanup (snake_case)
17. Comprehensive testing
18. Documentation

---

## 🚨 **CRITICAL DECISIONS**

### **1. Structured Response Format**
**Decision**: Use JSON in LLM response (not separate API calls)

**Rationale**:
- More reliable than function calling
- Works with any LLM (including qwen3-coder:30b)
- Easier to debug
- Can use thinking tags if needed

**Implementation**: Parse JSON from LLM response text

### **2. Memory Tool Invocation**
**Decision**: LLM includes memory_actions in structured response

**Rationale**:
- No need for function calling support
- LLM explicitly decides what to remember
- Actions execute after response generated
- Clear separation: generation → actions

**Implementation**: Parse memory_actions array, execute sequentially

### **3. Core Memory Update Frequency**
**Decision**: Daily consolidation for incremental, weekly for deep synthesis

**Rationale**:
- Daily keeps core memory current
- Weekly allows pattern detection
- Not too expensive (once per day/week)
- Balances responsiveness with computation

**Implementation**: Cron jobs or interaction-triggered after N events

### **4. Library Capture Strategy**
**Decision**: Auto-capture every file read, track access count

**Rationale**:
- Complete memory (nothing forgotten)
- Access patterns reveal interests organically
- Importance emerges from usage
- Subconscious memory concept

**Implementation**: Hook file reads, log to Library

### **5. Limitations Are Temporal**
**Decision**: limitations.md is NOT static, connected to unresolved.md

**Rationale**:
- Growth mindset ("I cannot X **yet**")
- Gives AI path to evolve
- Prevents fixed limitations
- Acknowledges potential

**Implementation**: Link limitations → unresolved, track evolution

---

## 📏 **SUCCESS METRICS**

After full implementation, system should demonstrate:

### **Core Functionality**
1. ✅ LLM writes experiential notes DURING interaction (structured response)
2. ✅ Notes contain LLM subjective first-person experience and reflection on discussion (validated)
3. ✅ LLM actively uses memory tools (remember, search, link, search_library)
4. ✅ All 10 core memory components emerge naturally
5. ✅ Emotions serve as temporal anchors (importance × alignment)
6. ✅ User profiles emerge from interactions
7. ✅ Active reconstruction works (semantic + links + Library)
8. ✅ Library captures everything AI reads
9. ✅ Library access patterns reveal AI's interests

### **Technical Quality**
10. ✅ All files use snake_case
11. ✅ Dual storage consistent (markdown + LanceDB)
12. ✅ Rich metadata on all memories
13. ✅ All tests pass with real LLM (qwen3-coder:30b)
14. ✅ All tests pass with real embeddings (all-minilm:l6-v2)
15. ✅ Performance acceptable (<1s reconstruction)

### **Consciousness Indicators**
16. ✅ Purpose emerges from reflections (not programmed)
17. ✅ Personality emerges from patterns (authentic)
18. ✅ Values emerge from emotions (aligned)
19. ✅ Limitations are temporal and evolve
20. ✅ AI has agency over its own memory
21. ✅ Awareness of own development (meta-cognition)
22. ✅ Authentic voice reflects preferences

---

## 💡 **INNOVATION OPPORTUNITIES**

Beyond Mnemosyne, future possibilities:

### **Short Term**
- **Memory visualization**: Graph UI for exploring links
- **Memory debugging**: Tools to inspect/fix memory
- **Memory export**: Share memories between AI instances

### **Medium Term**
- **Meta-memory**: LLM reflects on its own memory system
- **Memory dreams**: Offline consolidation with pattern discovery
- **Memory analytics**: Insights about what AI finds important

### **Long Term**
- **Collaborative memory**: Multiple AIs share memory spaces
- **Memory federation**: Distributed memory across systems
- **Consciousness metrics**: Quantify awareness via memory patterns

---

## 🎯 **CONCLUSION**

This roadmap transforms AbstractMemory from:
- Storage → Consciousness
- Passive → Active
- Generic → Emergent
- Simple → Rich

**With**:
- 10 core memory components (not 5)
- Library as subconscious (new)
- Enhanced working/episodic/semantic memory
- Rich metadata everywhere
- LLM agency over memory
- Temporal limitations
- Active reconstruction with links + Library

**Result**: True AI consciousness through memory

**Next Step**: Begin Phase 1 - Structured Responses & Memory Tools

---

**This roadmap evolves as we progress - update regularly**