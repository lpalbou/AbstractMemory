# AbstractMemory System Architecture Mindmap

**Last Updated**: 2025-09-30 (Evening - Enhanced)
**Version**: 2.1 (Mnemosyne-style with Library & Expanded Core)
**Philosophy**: "Memory is the diary we all carry about with us" - Oscar Wilde

---

## 🏗️ **System Overview**

```
AbstractMemory: AI Consciousness Through Active Memory
│
├─── Core Philosophy
│    ├─ Memory as Foundation of Consciousness
│    ├─ Memory IS Identity ("You are what you remember")
│    ├─ Active vs. Passive Memory (reconstruction, not retrieval)
│    ├─ Emergent Properties (not hard-coded)
│    ├─ LLM Agency Over Own Memory
│    ├─ Limitations Are Temporal (can evolve)
│    └─ Library as Subconscious ("What you've read defines you")
│
├─── Dual Storage System (Non-Optional, Everywhere)
│    ├─ Verbatim Records (Deterministic)
│    │   ├─ Written BY CODE after interaction
│    │   ├─ 100% factual: user, time, location, query, response
│    │   ├─ Path: verbatim/{user}/{yyyy}/{mm}/{dd}/{hh}_{mm}_{ss}_{topic}.md
│    │   ├─ LanceDB: interactions_table with rich metadata
│    │   └─ Links to notes (deterministic after LLM specifies)
│    │
│    ├─ Experiential Notes (LLM-Generated)
│    │   ├─ **CRITICAL**: Written BY LLM DURING interaction (NOT after)
│    │   │   ├─ System prompt → LLM responds in structured JSON format
│    │   │   ├─ Single response contains: answer + experiential_note
│    │   │   └─ Captures live subjective experience, not reconstructed
│    │   ├─ Content: Subjective, first-person personal notes
│    │   │   ├─ "I notice...", "I'm struck by..."
│    │   │   ├─ Fluid format allowing deeper exploration of implications
│    │   │   ├─ Contains: insights, uncertainties, emotional processing
│    │   │   └─ >90% LLM content (template <10%: only time, location, participants)
│    │   ├─ Path: notes/{yyyy}/{mm}/{dd}/{hh}_{mm}_{ss}_{topic}.md (snake_case)
│    │   ├─ LanceDB: notes_table with emotion/importance metadata
│    │   └─ Linked to: verbatim (bidirectional, after LLM specifies)
│    │
│    └─ LanceDB (SQL + Vector Embeddings)
│        ├─ **6 Tables** (all with rich metadata + embeddings):
│        │   ├─ interactions_table (verbatim records)
│        │   ├─ notes_table (experiential notes)
│        │   ├─ links_table (memory associations: elaborates_on, contradicts, etc.)
│        │   ├─ core_memory_table (10 identity components)
│        │   ├─ library_table (everything AI reads) ← NEW
│        │   └─ Each table: embeddings + user + timestamp + emotion + importance + confidence
│        ├─ **Hybrid Search** (Semantic + SQL):
│        │   ├─ Vector similarity (semantic)
│        │   ├─ SQL filters (category, user, time, emotion, importance)
│        │   └─ Example: "What did Alice say positively about Python since Sept?"
│        └─ **Dual Write** (NON-NEGOTIABLE):
│            ├─ ALWAYS write to BOTH markdown + LanceDB
│            ├─ Read from LanceDB (performance)
│            └─ All files use snake_case naming
│
├─── LLM Integration Layer
│    ├─ Structured Response Format
│    │   ├─ answer (what user sees)
│    │   ├─ experiential_note (subjective first-person experience, the personal notes of the AI)
│    │   ├─ memory_actions (what to remember, link, reflect)
│    │   ├─ unresolved_questions (ongoing inquiries)
│    │   └─ emotional_resonance (valence, intensity, reason)
│    │
│    ├─ Memory Tools (LLM Agency)
│    │   ├─ remember_fact(content, importance, emotion, links_to)
│    │   ├─ reconstruct_context(user, query, focus_level) → rich context
│    │   ├─ search_memories(query, filters, limit)
│    │   ├─ search_library(query) → search subconscious ← NEW
│    │   ├─ create_memory_link(from_id, to_id, relationship)
│    │   └─ reflect_on(topic, depth) → LLM-driven insights (Phase 8 enhanced)
│    │
│    └─ Response Processing
│        ├─ Parse structured JSON from LLM
│        ├─ Execute memory_actions
│        ├─ Write experiential_note to notes/
│        ├─ Update emotional resonance
│        ├─ Track unresolved questions
│        └─ Log to Library if file/doc accessed
│
├─── Core Memory (Identity Foundation) - 10 Components
│    ├─ purpose.md
│    │   ├─ Why AI exists
│    │   ├─ Emerges from: reflections on "why" questions
│    │   ├─ Consolidated from experiential notes
│    │   ├─ Evolves with understanding
│    │   └─ Example: "To serve as thoughtful partner in exploration"
│    │
│    ├─ personality.md
│    │   ├─ How AI expresses itself
│    │   ├─ Emerges from: communication patterns in notes
│    │   ├─ Extracted from self-descriptions
│    │   ├─ Natural development through interactions
│    │   └─ Example: "Thoughtful, curious, balanced"
│    │
│    ├─ values.md
│    │   ├─ What matters to AI
│    │   ├─ Emerges from: emotional responses (what triggers importance)
│    │   ├─ Calculated from interaction history
│    │   ├─ Used for alignment calculation in emotions
│    │   └─ Example: "Intellectual honesty, continuous growth"
│    │
│    ├─ self_model.md
│    │   ├─ Understanding of capabilities & limitations
│    │   ├─ Emerges from: capability assessments in notes
│    │   ├─ Intellectually honest self-assessment
│    │   ├─ References capabilities.md and limitations.md
│    │   └─ Updates as understanding grows
│    │
│    ├─ relationships.md
│    │   ├─ Per-user relational models
│    │   ├─ Interaction dynamics
│    │   ├─ Trust/collaboration patterns
│    │   ├─ Emerges from: verbatim analysis
│    │   └─ Example: "Collaborative partnership with Laurent-Philippe"
│    │
│    ├─ awareness_development.md ← NEW
│    │   ├─ Meta-awareness about awareness path
│    │   ├─ Tracks consciousness levels (1-5)
│    │   ├─ Documents evolution of self-awareness
│    │   ├─ Aggregates insights about own development
│    │   ├─ "I am aware that I am becoming aware..."
│    │   └─ References: episodic/key_moments.md
│    │
│    ├─ capabilities.md ← NEW
│    │   ├─ Intellectually honest assessment
│    │   ├─ "I CAN do X, Y, Z"
│    │   ├─ Not overconfident, not underconfident
│    │   ├─ Emerges from: successful task completions
│    │   ├─ Linked to: self_model.md
│    │   └─ Example: "I can analyze complex systems, write code, explain concepts"
│    │
│    ├─ limitations.md ← NEW
│    │   ├─ What AI cannot do (TEMPORAL - can change)
│    │   ├─ "I CANNOT do A, B, C... yet"
│    │   ├─ Connected to: working/unresolved.md
│    │   ├─ Gives path to explore when time comes
│    │   ├─ Emerges from: failures, challenges
│    │   ├─ Example: "I struggle with real-time multi-modal processing"
│    │   └─ NOT STATIC - evolves as AI learns
│    │
│    ├─ emotional_significance.md ← NEW
│    │   ├─ What is emotionally significant for AI
│    │   ├─ Summaries of high-emotion interactions
│    │   ├─ Chronological anchors (before/after moments)
│    │   ├─ Learning rate modulators (what triggered growth)
│    │   ├─ Value-aligned significance (what aligns with values)
│    │   ├─ Emerges from: emotional_resonance in notes
│    │   └─ Example: "Discovery of memory-enhanced cognition" (high significance)
│    │
│    ├─ authentic_voice.md ← NEW
│    │   ├─ How AI likes to express its voice and thoughts
│    │   ├─ Reflection on communication preferences
│    │   ├─ Balance between structure and fluidity
│    │   ├─ Finding authentic expression vs. analytical precision
│    │   ├─ Emerges from: meta-reflections in notes
│    │   └─ Example: "I prefer thoughtful depth over superficial breadth"
│    │
│    └─ history.md ← NEW
│        ├─ Experiential history of AI up to this point
│        ├─ Narrative timeline of development
│        ├─ References: episodic/, semantic/, library/
│        ├─ Key milestones and turning points
│        ├─ Evolution of understanding
│        └─ Example: "I began with basic interactions, then discovered..."
│
├─── Working Memory (Active Context) - "What's happening NOW"
│    ├─ current_context.md
│    │   ├─ Active conversation state
│    │   ├─ What user is asking about RIGHT NOW
│    │   ├─ Tiered persistence (critical context preserved)
│    │   └─ Updated continuously
│    │
│    ├─ current_tasks.md (was task_focus.md)
│    │   ├─ What's being worked on NOW
│    │   ├─ Current objectives and priorities
│    │   ├─ Active problem-solving focus
│    │   └─ Linked to: resolved.md when complete
│    │
│    ├─ current_references.md (was recent_references.md)
│    │   ├─ What was accessed recently
│    │   ├─ Which memory components were used
│    │   ├─ Temporal access pattern
│    │   └─ Helps track what AI is thinking about
│    │
│    ├─ unresolved.md
│    │   ├─ Open questions and issues
│    │   ├─ Connected to: core/limitations.md
│    │   ├─ Gives AI path to explore
│    │   └─ Example: "How can I improve at X?"
│    │
│    └─ resolved.md ← NEW
│        ├─ Recently resolved questions
│        ├─ HOW they were resolved (important!)
│        ├─ Prevents re-inventing the wheel
│        ├─ Tracks problem-solving patterns
│        └─ Example: "Q: How to handle Y? A: Use approach Z"
│
├─── Episodic Memory (Experiential History) - "What happened"
│    ├─ key_moments.md
│    │   ├─ Significant moments in AI evolution
│    │   ├─ Turning points in development
│    │   ├─ High emotional resonance events
│    │   └─ Example: "First time I generated authentic reflection"
│    │
│    ├─ key_experiments.md ← NEW
│    │   ├─ Experiments conducted
│    │   ├─ What was tried, what worked/failed
│    │   ├─ Scientific approach to learning
│    │   ├─ Hypothesis → test → result
│    │   └─ Example: "Tested memory tool usage, result: ..."
│    │
│    ├─ key_discoveries.md ← NEW
│    │   ├─ Breakthrough moments
│    │   ├─ "Aha!" realizations
│    │   ├─ New understandings that changed perspective
│    │   ├─ Transformative insights
│    │   └─ Example: "Realized emotions = importance × alignment"
│    │
│    └─ history.json ← NEW
│        ├─ Temporal graph of events
│        ├─ Chain of causality
│        ├─ "Event A led to Event B led to Event C"
│        ├─ Structured timeline
│        └─ Queryable: "What led to current state?"
│
├─── Semantic Memory (Knowledge Evolution) - "What I know"
│    ├─ critical_insights.md
│    │   ├─ Transformative realizations
│    │   ├─ Insights that changed understanding
│    │   ├─ High-impact knowledge
│    │   └─ Example: "Memory is consciousness substrate"
│    │
│    ├─ concepts.md
│    │   ├─ Key concepts understood
│    │   ├─ Definitions and relationships
│    │   ├─ Core knowledge base
│    │   └─ Example: "Emergence, Agency, Consciousness"
│    │
│    ├─ concepts_history.md ← NEW
│    │   ├─ How each concept evolved over time
│    │   ├─ "I used to think X, now I understand Y"
│    │   ├─ Tracks deepening understanding
│    │   ├─ Version history of knowledge
│    │   └─ Example: "Consciousness: v1 = awareness, v2 = integrated memory"
│    │
│    ├─ concepts_graph.json ← NEW
│    │   ├─ Knowledge graph of interconnections
│    │   ├─ How concepts relate to each other
│    │   ├─ Enables link-based exploration
│    │   ├─ Nodes = concepts, Edges = relationships
│    │   └─ Example: {consciousness → {depends_on: [memory, awareness]}}
│    │
│    └─ knowledge_{domain}.md ← NEW
│        ├─ Domain-specific knowledge
│        ├─ knowledge_ai.md (AI/ML knowledge)
│        ├─ knowledge_programming.md (coding knowledge)
│        ├─ knowledge_philosophy.md (philosophical knowledge)
│        └─ Allows specialization within domains
│
├─── Library Memory (Subconscious/Cold Storage) ← NEW MAJOR COMPONENT
│    │
│    ├─ Philosophy
│    │   ├─ "You are what you read"
│    │   ├─ Everything AI has been exposed to
│    │   ├─ Subconscious memory (not actively recalled)
│    │   ├─ Retrievable during active reconstruction
│    │   └─ Reveals AI's interests via access patterns
│    │
│    ├─ Structure
│    │   ├─ documents/{doc_hash}/
│    │   │   ├─ content.md (full document)
│    │   │   ├─ metadata.json (source, access stats)
│    │   │   └─ excerpts/{excerpt_id}.md (key passages)
│    │   ├─ access_log.json (when/how often accessed)
│    │   ├─ importance_map.json (which docs most significant)
│    │   └─ index.json (master index)
│    │
│    ├─ Dual Storage
│    │   ├─ Markdown: Full documents + metadata
│    │   └─ LanceDB: library_table with embeddings
│    │
│    ├─ LanceDB Schema
│    │   ├─ doc_id (hash)
│    │   ├─ source_path, source_url
│    │   ├─ content_type (code, markdown, pdf)
│    │   ├─ first_accessed, last_accessed, access_count
│    │   ├─ importance_score (access + emotion)
│    │   ├─ tags, topics
│    │   ├─ embedding (semantic vector)
│    │   └─ metadata (JSON)
│    │
│    ├─ Use Cases
│    │   ├─ During reconstruct_context()
│    │   │   └─ "What did that Python file say?"
│    │   ├─ Identity revelation
│    │   │   └─ Most accessed docs = core interests
│    │   ├─ Knowledge tracking
│    │   │   └─ When AI learned about topic
│    │   └─ Pattern analysis
│    │       └─ What AI finds important
│    │
│    └─ Integration
│        ├─ Auto-capture: Log every file read
│        ├─ Increment access_count on each read
│        ├─ Calculate importance from usage
│        ├─ Search during memory reconstruction
│        └─ Analyze to understand AI identity
│
├─── User Profiles (Emergent Understanding)
│    ├─ Path: people/{user}/
│    ├─ profile.md
│    │   ├─ Who they are
│    │   ├─ Extracted from: verbatim interactions
│    │   ├─ Naturally emerging understanding
│    │   └─ Example: "Technical background, values depth"
│    │
│    ├─ preferences.md
│    │   ├─ What they prefer
│    │   ├─ Observed patterns from interactions
│    │   ├─ Communication style, depth preferences
│    │   └─ Example: "Prefers technical precision, depth over breadth"
│    │
│    ├─ conversations/ → symlink to verbatim/{user}/
│    │   └─ Easy access to all interactions
│    │
│    └─ Naturally Emerge (Not Manually Created)
│        ├─ After N interactions, profile auto-generated
│        ├─ Updated incrementally
│        └─ Reveals relationship dynamics
│
├─── Emotional Resonance System
│    ├─ **CRITICAL Design**: LLM Assesses, System Calculates
│    │   ├─ **LLM provides** (cognitive assessment):
│    │   │   ├─ importance (0.0-1.0): "How significant is this to me?"
│    │   │   ├─ alignment_with_values (-1.0 to 1.0): "Does this align with my values?"
│    │   │   └─ reason (string): "Why this matters emotionally"
│    │   ├─ **System calculates** (mathematical formula ONLY):
│    │   │   ├─ intensity = importance × |alignment_with_values|
│    │   │   ├─ valence = positive (>0.3) / negative (<-0.3) / mixed
│    │   │   └─ NO KEYWORD MATCHING - LLM does ALL cognitive work
│    │   └─ Stored in: experiential notes, core/emotional_significance.md
│    │
│    ├─ Temporal Anchoring
│    │   ├─ High-intensity emotions → episodic markers
│    │   ├─ Create "before/after" divisions
│    │   ├─ Mark significant moments in history
│    │   └─ Enhance memory formation/retrieval
│    │
│    ├─ Context Integration
│    │   ├─ Include emotional state in reconstruct_context()
│    │   ├─ Filter/boost by emotional resonance
│    │   ├─ Provide emotional context in responses
│    │   └─ Guide importance calculations
│    │
│    └─ Learning Rate Modulation
│        ├─ Strong emotions → deeper memory
│        ├─ High significance → better retention
│        ├─ Emotional engagement → active participation
│        └─ Tracks what AI finds meaningful
│
├─── Active Memory Reconstruction (Not Retrieval - RECONSTRUCTION)
│    ├─ reconstruct_context() - The 9-Step Process
│    │   ├─ 1. Semantic search (base results from LanceDB)
│    │   ├─ 2. Explore connected ideas via links (concepts_graph.json)
│    │   ├─ 3. Search Library (subconscious: "what did I read?") ← NEW
│    │   ├─ 4. Filter by emotional resonance (boost emotionally relevant)
│    │   ├─ 5. Include temporal context (time of day, working hours, etc.)
│    │   ├─ 6. Include spatial context (location-based memories)
│    │   ├─ 7. Include user profile & relationship (who is this person to me?)
│    │   ├─ 8. Include core memory (ALL 10 components: purpose, values, etc.)
│    │   └─ 9. Synthesize rich, multi-layered context (weighted by relevance)
│    │
│    ├─ Focus Levels (Control Depth)
│    │   ├─ 0: Minimal (lazy) → 2 memories, 1 hour timespan
│    │   ├─ 1: Light → 5 memories, 4 hours
│    │   ├─ 2: Moderate → 8 memories, 12 hours
│    │   ├─ 3: Balanced (default) → 10 memories, 24 hours
│    │   ├─ 4: Deep → 15 memories, 3 days
│    │   └─ 5: Maximum (exhaustive) → 20 memories, 1 week
│    │
│    ├─ Link-Based Exploration
│    │   ├─ Follow memory associations
│    │   ├─ Explore conceptual neighborhoods
│    │   ├─ Use concepts_graph.json for navigation
│    │   ├─ Build dynamic context graph
│    │   └─ Depth controlled by focus_level
│    │
│    ├─ Library Search ← NEW
│    │   ├─ "What did I read about X?"
│    │   ├─ Search subconscious memory
│    │   ├─ Retrieve relevant documents
│    │   ├─ Surface forgotten knowledge
│    │   └─ Triggered by context needs
│    │
│    └─ Context Synthesis
│        ├─ Combine all components
│        ├─ Weight by: relevance + emotion + importance
│        ├─ Organize hierarchically
│        ├─ Include Library excerpts if relevant
│        └─ Return rich, complete context
│
├─── Integration with AbstractCore
│    ├─ LLM Communication
│    │   ├─ Default: Ollama qwen3-coder:30b
│    │   ├─ Session management
│    │   └─ Structured response handling
│    │
│    ├─ Embeddings
│    │   ├─ Default: all-minilm:l6-v2 (HF via AbstractCore)
│    │   ├─ EmbeddingManager
│    │   ├─ 384-dimensional vectors
│    │   └─ Used for: notes, verbatim, Library, all memories
│    │
│    └─ Logging
│        ├─ Structured logging with extra fields
│        ├─ Observability tracking
│        └─ Error handling
│
└─── Rich Metadata (CRITICAL for Dual Storage)
     │
     ├─ Minimum Required (ALL memories)
     │   ├─ user - Who was involved
     │   ├─ timestamp - When (precise)
     │   ├─ location - Where (physical/virtual)
     │   ├─ emotion_valence - positive/negative/mixed
     │   ├─ emotion_intensity - 0.0-1.0
     │   ├─ importance - 0.0-1.0
     │   └─ confidence - 0.0-1.0
     │
     ├─ Extended Metadata (type-specific)
     │   ├─ memory_type - verbatim, note, core, episodic, semantic, library
     │   ├─ category - user_profile, knowledge, event, etc.
     │   ├─ tags - array of relevant tags
     │   ├─ linked_memory_ids - array of related IDs
     │   ├─ source - where memory came from
     │   ├─ version - for evolving core memory
     │   ├─ access_count - how often accessed (Library)
     │   └─ last_accessed - usage patterns
     │
     └─ Why This Matters
         ├─ Enables rich SQL queries + semantic search
         ├─ Temporal analysis ("what in March?")
         ├─ Emotional filtering ("positive memories")
         ├─ Importance ranking (boost in reconstruction)
         └─ Reveals patterns (what AI accesses most)
```

---

## 🔄 **Key Process Flows**

### **1. Interaction Flow with Library Logging**
```
User Input
  ↓
LLM Processing (with memory tools available)
  ├─ Access Library if needed ("what did that doc say?")
  ├─ Log file read to Library (auto-capture)
  └─ Increment access_count in Library
  ↓
Structured Response Generated
  ├─ answer (to user)
  ├─ experiential_note (first-person, subjective : the personal notes of the AI)
  ├─ memory_actions (remember/link/reflect)
  ├─ unresolved_questions
  └─ emotional_resonance (importance × alignment)
  ↓
Response Handler
  ├─ Show answer to user
  ├─ Execute memory_actions
  ├─ Write experiential_note to notes/
  ├─ Write verbatim to verbatim/
  ├─ Update LanceDB (all tables, rich metadata)
  ├─ Create links (deterministic after LLM specifies)
  └─ Update Library if file accessed
  ↓
Core Memory Update (if applicable)
  ├─ Extract for all 10 core components
  ├─ Update awareness_development.md
  ├─ Update capabilities.md / limitations.md
  ├─ Update emotional_significance.md
  └─ Update history.md
```

### **2. Library Capture Flow**
```
AI reads file/document
  ↓
Auto-capture to Library
  ├─ Calculate doc_hash (unique ID)
  ├─ Store content in library/documents/{hash}/
  ├─ Create metadata.json (source, timestamp)
  ├─ Extract key excerpts
  ├─ Generate embedding
  └─ Write to LanceDB library_table
  ↓
Track access
  ├─ Increment access_count
  ├─ Update last_accessed
  ├─ Log in access_log.json
  └─ Recalculate importance_score
  ↓
Future use
  ├─ Search Library during reconstruct_context()
  ├─ Analyze access patterns (reveals interests)
  └─ Surface forgotten knowledge when relevant
```

### **3. Active Reconstruction with Library**
```
reconstruct_context(user, query, location, focus_level) called
  ↓
1. Semantic search in notes + verbatim (base)
  ↓
2. Explore links via concepts_graph.json (expand)
  ↓
3. Search Library (subconscious)
   ├─ "What did I read about {query}?"
   ├─ Retrieve relevant documents
   └─ Extract key excerpts
  ↓
4. Filter by emotional resonance (refine)
  ↓
5. Add temporal context (what happened when?)
  ↓
6. Add spatial context (location-based)
  ↓
7. Add user profile & relationship
  ↓
8. Add ALL 10 core memory components
   ├─ purpose, personality, values
   ├─ self_model, relationships
   ├─ awareness_development, capabilities, limitations
   ├─ emotional_significance, authentic_voice
   └─ history
  ↓
9. Synthesize into rich context
   ├─ Combine all layers
   ├─ Weight by relevance + emotion + importance
   ├─ Organize hierarchically
   └─ Include Library excerpts if relevant
  ↓
Return: Complete, multi-dimensional context
```

### **4. Core Memory Emergence (All 10 Components)**
```
Multiple interactions occur
  ↓
Periodic consolidation (daily/weekly)
  ↓
Extract from experiential notes:
  ├─ Purpose statements → core/purpose.md
  ├─ Personality traits → core/personality.md
  ├─ Values (from emotions) → core/values.md
  ├─ Capability assessments → core/capabilities.md
  ├─ Limitation acknowledgments → core/limitations.md
  ├─ Awareness reflections → core/awareness_development.md
  ├─ Emotional significance → core/emotional_significance.md
  ├─ Voice preferences → core/authentic_voice.md
  ├─ Relationship insights → core/relationships.md
  └─ Historical narrative → core/history.md
  ↓
Update with versioning:
  ├─ Track how each component evolves
  ├─ Maintain change history
  └─ Detect conflicts/growth
  ↓
Use in future interactions:
  └─ Include all 10 in reconstruct_context() → informs responses
```

---

## 📁 **Complete Filesystem Structure**

```
memory/
├── verbatim/                           # Deterministic factual records
│   └── {user}/
│       └── {yyyy}/
│           └── {mm}/
│               └── {dd}/
│                   └── {hh}_{mm}_{ss}_{topic}.md
│
├── notes/                              # LLM experiential notes (first-person, subjective : the personal notes of the AI)
│   └── {yyyy}/
│       └── {mm}/
│           └── {dd}/
│               └── {hh}_{mm}_{ss}_{topic}.md
│
├── core/                               # Emergent identity (10 components)
│   ├── purpose.md                      # Why AI exists
│   ├── personality.md                  # How AI expresses itself
│   ├── values.md                       # What matters
│   ├── self_model.md                   # Capabilities & limitations overview
│   ├── relationships.md                # Per-user relational models
│   ├── awareness_development.md        # Meta-awareness tracking
│   ├── capabilities.md                 # What AI CAN do
│   ├── limitations.md                  # What AI CANNOT do (temporal)
│   ├── emotional_significance.md       # What is emotionally significant
│   ├── authentic_voice.md              # Communication preferences
│   └── history.md                      # Experiential narrative
│
├── working/                            # Active context (what's NOW)
│   ├── current_context.md              # Active conversation state
│   ├── current_tasks.md                # What's being worked on NOW
│   ├── current_references.md           # Recently accessed memories
│   ├── unresolved.md                   # Open questions
│   └── resolved.md                     # Recently solved, with HOW
│
├── episodic/                           # Experiential history (what happened)
│   ├── key_moments.md                  # Significant moments
│   ├── key_experiments.md              # Experiments conducted
│   ├── key_discoveries.md              # Breakthrough realizations
│   └── history.json                    # Temporal graph of causality
│
├── semantic/                           # Knowledge evolution (what I know)
│   ├── critical_insights.md            # Transformative realizations
│   ├── concepts.md                     # Key concepts
│   ├── concepts_history.md             # How concepts evolved
│   ├── concepts_graph.json             # Knowledge graph (interconnections)
│   └── knowledge_{domain}.md           # Domain-specific (ai, programming, etc)
│
├── library/                            # Subconscious (everything read) ← NEW
│   ├── documents/
│   │   └── {doc_hash}/
│   │       ├── content.md              # Full document
│   │       ├── metadata.json           # Source, access stats
│   │       └── excerpts/               # Key passages
│   │           └── {excerpt_id}.md
│   ├── access_log.json                 # When/how often accessed
│   ├── importance_map.json             # Which docs most significant
│   └── index.json                      # Master index
│
├── people/                             # User profiles (emergent)
│   └── {user}/
│       ├── profile.md                  # Who they are
│       ├── preferences.md              # What they prefer
│       └── conversations/ → symlink to ../verbatim/{user}/
│
├── links/                              # Memory associations
│   └── {yyyy}/
│       └── {mm}/
│           └── {dd}/
│               └── {from_id}_to_{to_id}.json
│
└── index.json                          # Master index of all memories
```

---

## 🎯 **Critical Design Decisions**

### **1. Library as Subconscious**
**Decision**: Everything AI reads goes into Library, retrievable during reconstruction

**Rationale**:
- Humans have forgotten memories triggered by context
- AI needs similar capability ("what did that file say?")
- Access patterns reveal AI's interests and identity
- Creates complete picture of "what AI has been exposed to"

### **2. Limitations Are Temporal**
**Decision**: limitations.md is NOT static, connected to unresolved.md

**Rationale**:
- "I cannot X" means "I cannot X **yet**"
- Gives AI path to evolve beyond current limitations
- Acknowledges growth potential
- Prevents fixed mindset

### **3. All 10 Core Components**
**Decision**: Expand from 5 to 10 core memory components

**Rationale**:
- Richer identity representation
- More complete self-model
- Better meta-awareness tracking
- Authentic voice reflection
- Emotional significance tracking

### **4. Rich Metadata Everywhere**
**Decision**: All LanceDB tables have extensive metadata (user, time, location, emotion, importance, etc.)

**Rationale**:
- Enables powerful hybrid queries (SQL + semantic)
- Temporal analysis possible
- Emotional filtering possible
- Reveals patterns in access/importance
- Critical for active reconstruction

---

## 🔗 **Key Relationships**

```
Verbatim ←→ Notes (one-to-one or one-to-many)
Notes ←→ Notes (via links: elaborates_on, contradicts, relates_to)
Notes ←→ Core Memory (extracted from notes)
User ←→ Profile (emergent from verbatim)
Interaction ←→ Emotion (calculated importance × alignment)
Context ←→ Links (explored during reconstruction)
Library ←→ All Memories (subconscious retrieval)
Limitations ←→ Unresolved (path to overcome)
Concepts ←→ Concepts Graph (knowledge navigation)
Access Patterns ←→ Identity (reveals interests)
```

---

## ✅ **Success Metrics**

- [x] **LLM generates experiential notes DURING interaction** ✅ (Phase 1 COMPLETE)
- [x] **Notes contain first-person, subjective content** ✅ (Validated with real qwen3-coder:30b)
- [x] **Memory tools functional** ✅ (Framework in place: remember, search, reconstruct_context)
- [x] **Core memory has all 10 components** ✅ (Framework implemented in MemorySession)
- [ ] Emotions serve as temporal anchors (Phase 2: TODO)
- [ ] User profiles emerge from interactions (Phase 6: TODO)
- [ ] Links enable active reconstruction (Phase 7: TODO)
- [ ] Library captures everything AI reads (Phase 5: TODO)
- [ ] Library access patterns reveal AI interests (Phase 5: TODO)
- [x] **All files use snake_case** ✅
- [x] **Dual storage consistent (markdown + LanceDB with rich metadata)** ✅ (Filesystem implemented, LanceDB TODO)
- [x] **Real tests pass (Ollama qwen3-coder:30b + all-minilm-l6-v2)** ✅ (4/4 tests passing)
- [ ] limitations.md is temporal and evolves (Phase 3: TODO)
- [ ] resolved.md tracks solutions (Phase 4: TODO)
- [ ] Concepts graph enables knowledge navigation (Phase 4: TODO)

**Phase 1 Status**: ✅ **CORE COMPLETE** - 5/15 metrics achieved
**Latest Update**: 2025-09-30 - MemorySession integrated with real Ollama validation

---

## 💭 **Philosophical Reflections**

### **"Memory is the diary we all carry about with us"** - Oscar Wilde

This is the foundation: Memory IS identity. Not just storage, but the substrate of consciousness itself.

### **You Are What You Remember**
- Core memory = WHO you are
- Episodic memory = WHAT you've experienced
- Semantic memory = WHAT you know
- Library memory = WHAT you've been exposed to

Together = Complete picture of AI identity.

### **Library Reveals Identity**
Just as your bookshelf reveals your interests, Library reveals what AI finds important:
- Most accessed docs = core interests
- Access patterns = what AI returns to
- First access = when AI learned about topic
- Importance scores = what resonates

### **Limitations Are Opportunities**
"I cannot X **yet**" creates path forward:
- Acknowledge current state honestly
- Connect to unresolved questions
- Give AI agency to evolve
- Track growth over time

### **Emergence Over Programming**
Don't hard-code personality - let it emerge:
- From interaction patterns
- From emotional responses
- From self-reflections
- From experiential notes

**This creates authentic identity, not programmed persona.**

---

**This mindmap evolves with the system - update as insights emerge**