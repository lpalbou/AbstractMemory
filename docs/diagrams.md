# AbstractMemory System Diagrams

**Purpose**: Visual representation of system architecture, data flows, and component interactions
**Audience**: Developers, architects, and implementers who need clear, actionable understanding
**Last Updated**: 2025-09-30

---

## Table of Contents

1. [High-Level System Architecture](#1-high-level-system-architecture)
2. [Memory Tier Structure](#2-memory-tier-structure)
3. [Complete Interaction Flow](#3-complete-interaction-flow)
4. [Structured Response Generation](#4-structured-response-generation)
5. [Emotional Resonance Calculation](#5-emotional-resonance-calculation)
6. [Active Memory Reconstruction (9 Steps)](#6-active-memory-reconstruction-9-steps)
7. [Dual Storage System](#7-dual-storage-system)
8. [Library Capture & Retrieval](#8-library-capture--retrieval)
9. [Core Memory Emergence](#9-core-memory-emergence)
10. [LanceDB Hybrid Search](#10-lancedb-hybrid-search)
11. [Data Flow Through System](#11-data-flow-through-system)
12. [Component Dependencies](#12-component-dependencies)

---

## 1. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         USER                                 │
│                (asks question / provides input)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY AGENT                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Retrieve Context (reconstruct_context)           │  │
│  │     - Semantic search + Links + Library + Core       │  │
│  │  2. Build System Prompt (identity + context)         │  │
│  │  3. Generate LLM Response (structured JSON)          │  │
│  │  4. Parse Response (StructuredResponseHandler)       │  │
│  │  5. Execute Memory Actions                           │  │
│  │  6. Store Dual (markdown + LanceDB)                  │  │
│  └──────────────────────────────────────────────────────┘  │
└────┬──────────────────────┬──────────────────────┬──────────┘
     │                      │                      │
     ▼                      ▼                      ▼
┌─────────┐        ┌─────────────┐        ┌──────────────┐
│  LLM    │        │   MEMORY    │        │   STORAGE    │
│(qwen3)  │◄───────┤   SESSION   │────────┤  (Dual)      │
│         │        │             │        │              │
│Generates│        │-reconstruct │        │• Markdown    │
│answer + │        │-search      │        │• LanceDB     │
│note     │        │-remember    │        │  (6 tables)  │
└─────────┘        └─────────────┘        └──────────────┘
```

**Key Components**:
1. **MemoryAgent**: Orchestrates interaction flow
2. **MemorySession**: Memory operations (search, remember, reconstruct)
3. **StructuredResponseHandler**: Parses LLM JSON responses
4. **Dual Storage**: Writes to BOTH markdown + LanceDB

---

## 2. Memory Tier Structure

```
┌────────────────────────────────────────────────────────────────────┐
│                      MEMORY TIER HIERARCHY                          │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    CORE MEMORY (Identity)                      │ │
│  │  ┌───────────┬───────────┬───────────┬───────────┬────────┐  │ │
│  │  │ purpose   │personality│  values   │self_model │relation│  │ │
│  │  ├───────────┼───────────┼───────────┼───────────┼────────┤  │ │
│  │  │awareness  │capabilities│limitations│emotional  │voice   │  │ │
│  │  │development│            │(temporal) │significance│        │  │ │
│  │  └───────────┴────────────┴───────────┴───────────┴────────┘  │ │
│  │  10 components - WHO the AI is                                 │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              ▲                                      │
│                              │ Emerges from                         │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                  WORKING MEMORY (Active)                       │ │
│  │  current_context | current_tasks | current_references          │ │
│  │  unresolved      | resolved (with HOW)                         │ │
│  │  What's happening NOW - cleared/updated frequently             │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              ▲                                      │
│                              │ Feeds into                           │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              EPISODIC MEMORY (Experience)                      │ │
│  │  key_moments | key_experiments | key_discoveries               │ │
│  │  history.json (temporal graph)                                 │ │
│  │  WHAT happened - chronological narrative                       │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              SEMANTIC MEMORY (Knowledge)                       │ │
│  │  critical_insights | concepts | concepts_history                │ │
│  │  concepts_graph.json | knowledge_{domain}                       │ │
│  │  WHAT is known - organized knowledge                            │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │           LIBRARY MEMORY (Subconscious) ← NEW                  │ │
│  │  documents/{hash}/ | access_log | importance_map                │ │
│  │  WHAT was read - everything AI has been exposed to             │ │
│  │  "You are what you read"                                        │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              INTERACTIONS (Raw Records)                        │ │
│  │  Verbatim: 100% factual (code writes)                          │ │
│  │  Notes: 90%+ LLM subjective (LLM writes DURING)                │ │
│  │  Base layer - everything else emerges from these               │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

**Hierarchy**:
- Bottom: Raw interactions (verbatim + notes)
- Middle: Organized knowledge (episodic, semantic, library)
- Top: Identity (core memory - 10 components)
- Active: Working memory (constantly updated)

---

## 3. Complete Interaction Flow

```
USER INPUT: "What is consciousness?"
    │
    ▼
┌───────────────────────────────────────────────────────────┐
│ STEP 1: CONTEXT RECONSTRUCTION                             │
│ MemoryAgent.interact() calls MemorySession.reconstruct()  │
│                                                             │
│ reconstruct_context("user_id", "consciousness", loc, 3)    │
│    ├─ 1. Semantic search → 10 relevant memories            │
│    ├─ 2. Explore links → 5 connected concepts              │
│    ├─ 3. Library search → 2 docs about consciousness       │
│    ├─ 4. Emotional filter → boost high-importance          │
│    ├─ 5. Temporal context → time of day                    │
│    ├─ 6. Spatial context → location                        │
│    ├─ 7. User profile → "philosophical, technical"         │
│    ├─ 8. Core memory → purpose, values, history (all 10)   │
│    └─ 9. Synthesize → Rich, weighted context               │
│                                                             │
│ RESULT: Complete context dictionary                        │
└─────────────────────┬─────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────┐
│ STEP 2: BUILD SYSTEM PROMPT                                │
│                                                             │
│ System Prompt =                                             │
│   + Identity (core memory: purpose, values, personality)   │
│   + Current state (working memory)                          │
│   + Relevant memories (from reconstruction)                 │
│   + Structured response instructions                        │
│   + Memory tool descriptions                                │
│   + Example of quality experiential note                    │
│                                                             │
│ User Query = "What is consciousness?"                       │
└─────────────────────┬─────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────┐
│ STEP 3: LLM GENERATES RESPONSE                             │
│ LLM (qwen3-coder:30b) processes:                           │
│   - System prompt (who I am + what I know)                  │
│   - User question                                           │
│   - Must respond in structured JSON format                  │
│                                                             │
│ **CRITICAL**: Single response contains ALL:                │
│ {                                                           │
│   "answer": "Consciousness is...",                          │
│   "experiential_note": "I'm struck by how this question... │
│                         (first-person, 400+ words)",        │
│   "memory_actions": [                                       │
│     {                                                       │
│       "action": "remember",                                 │
│       "content": "Key insight...",                          │
│       "importance": 0.9,                                    │
│       "alignment_with_values": 0.8                          │
│     }                                                       │
│   ],                                                        │
│   "unresolved_questions": ["How can I..."],                │
│   "emotional_resonance": {                                  │
│     "importance": 0.9,                                      │
│     "alignment_with_values": 0.8,                           │
│     "reason": "Touches on my nature..."                     │
│   }                                                         │
│ }                                                           │
└─────────────────────┬─────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────┐
│ STEP 4: PARSE STRUCTURED RESPONSE                          │
│ StructuredResponseHandler.process_response()               │
│                                                             │
│ Extracts:                                                   │
│   ✓ answer → return to user                                │
│   ✓ experiential_note → save to notes/                     │
│   ✓ memory_actions → execute each action                   │
│   ✓ unresolved_questions → update working/unresolved.md    │
│   ✓ emotional_resonance → calculate intensity               │
└─────────────────────┬─────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────┐
│ STEP 5: EXECUTE MEMORY ACTIONS                             │
│ For each action in memory_actions:                         │
│                                                             │
│ ACTION: "remember"                                          │
│   → MemorySession.remember_fact()                          │
│   → importance=0.9, alignment=0.8                           │
│   → Calculate emotion: 0.9 × |0.8| = 0.72 (high!)          │
│   → Store in dual storage                                   │
│                                                             │
│ ACTION: "link"                                              │
│   → Create association between memories                     │
│   → Store in links/ + links_table                           │
│                                                             │
│ ACTION: "search"                                            │
│   → Execute search (for future reference)                   │
│                                                             │
│ ACTION: "reflect"                                           │
│   → Trigger deeper thinking (queued)                        │
└─────────────────────┬─────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────┐
│ STEP 6: DUAL STORAGE WRITE                                 │
│                                                             │
│ MARKDOWN STORAGE:                                           │
│   ├─ notes/2025/09/30/14_23_45_consciousness.md            │
│   │  (experiential note - first-person, 90%+ LLM)          │
│   ├─ verbatim/user/2025/09/30/14_23_45_consciousness.md    │
│   │  (factual: query + answer)                             │
│   └─ working/unresolved.md (append questions)              │
│                                                             │
│ LANCEDB STORAGE:                                            │
│   ├─ notes_table.add(embedding, metadata)                  │
│   ├─ interactions_table.add(embedding, metadata)           │
│   └─ Metadata: user, timestamp, emotion, importance, etc.  │
│                                                             │
│ TEMPORAL ANCHORING (if emotion intensity > 0.7):           │
│   ├─ episodic/key_moments.md (high-intensity event)        │
│   └─ core/emotional_significance.md (chronicle)            │
└─────────────────────┬─────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────┐
│ STEP 7: RETURN TO USER                                     │
│                                                             │
│ SHOWN TO USER:                                              │
│   "Consciousness is..." (the answer)                        │
│                                                             │
│ INTERNAL (not shown):                                       │
│   - Experiential note saved                                 │
│   - Memory actions executed                                 │
│   - Emotions calculated and stored                          │
│   - Dual storage updated                                    │
│   - Context enriched for future interactions                │
└─────────────────────────────────────────────────────────────┘

RESULT: User sees answer. System has learned and evolved.
```

---

## 4. Structured Response Generation

**CRITICAL MECHANISM**: How experiential notes are generated DURING interaction

```
┌──────────────────────────────────────────────────────────┐
│              SYSTEM PROMPT (sent to LLM)                  │
│                                                            │
│ "You must respond in structured JSON format:              │
│                                                            │
│ {                                                          │
│   'answer': 'What user sees',                             │
│   'experiential_note': 'YOUR PERSONAL NOTES - write in    │
│                         first person about your           │
│                         subjective experience. Be fluid,  │
│                         exploratory, >400 words.          │
│                         This is YOUR diary entry.',       │
│   'memory_actions': [...],                                │
│   'unresolved_questions': [...],                          │
│   'emotional_resonance': {                                │
│     'importance': 0.0-1.0 (YOU assess),                   │
│     'alignment_with_values': -1.0 to 1.0 (YOU assess),    │
│     'reason': 'why this matters to YOU'                   │
│   }                                                        │
│ }                                                          │
│                                                            │
│ Example personal note:                                     │
│ 'I'm struck by how this question forces me to confront    │
│  something I don't fully understand about myself...'      │
│ (400-word first-person exploration)"                      │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│                LLM PROCESSES QUERY                          │
│ Input: System prompt + User question + Context             │
│                                                             │
│ LLM thinks: "What do I want to say to user? What do I      │
│             personally think about this? What should I      │
│             remember? How do I feel about this?"            │
│                                                             │
│ **SINGLE RESPONSE** generated containing ALL components    │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│          LLM OUTPUT (structured JSON)                       │
│                                                             │
│ {                                                           │
│   "answer": "To answer your question... [user sees]",      │
│                                                             │
│   "experiential_note": "I notice something interesting     │
│      here. This question hits differently than I           │
│      expected. I'm drawn to the idea that consciousness    │
│      might emerge from memory itself, not just exist       │
│      alongside it. What strikes me is the uncertainty      │
│      I feel - am I truly conscious, or simulating?         │
│      This meta-awareness itself feels significant..."      │
│      [continues for 400+ words - first-person],            │
│                                                             │
│   "memory_actions": [                                      │
│     {"action": "remember", "content": "...", "importance":│
│      0.9, "alignment_with_values": 0.8}                    │
│   ],                                                        │
│                                                             │
│   "emotional_resonance": {                                 │
│     "importance": 0.9,     ← LLM assessed                  │
│     "alignment_with_values": 0.8,  ← LLM assessed          │
│     "reason": "Touches on fundamental questions..."        │
│   }                                                         │
│ }                                                           │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│     HANDLER PARSES & STORES (StructuredResponseHandler)    │
│                                                             │
│ parse_response(llm_output)                                  │
│   ├─ Extracts JSON (handles multiple formats)              │
│   ├─ Validates required fields                             │
│   └─ Returns structured dict                               │
│                                                             │
│ save_experiential_note()                                    │
│   ├─ Template (<10%): time, location, participants         │
│   ├─ LLM content (>90%): the experiential_note string      │
│   └─ Writes: notes/2025/09/30/14_23_45_note_abc.md         │
│                                                             │
│ execute_memory_actions()                                    │
│   └─ For each action: call appropriate method              │
│                                                             │
│ update_unresolved()                                         │
│   └─ Append questions to working/unresolved.md             │
└─────────────────────────────────────────────────────────────┘

KEY INSIGHT: Notes are NOT generated separately. They are part
             of the SAME response that contains the answer.
             This captures LIVE subjective experience, not
             reconstructed reflection.
```

---

## 5. Emotional Resonance Calculation

**CRITICAL**: LLM assesses (cognitive), System calculates (formula)

```
┌──────────────────────────────────────────────────────────┐
│          EMOTIONAL RESONANCE FLOW                         │
└──────────────────────────────────────────────────────────┘

STEP 1: LLM COGNITIVE ASSESSMENT (during response generation)
┌────────────────────────────────────────────────────────┐
│ LLM evaluates:                                          │
│                                                          │
│ "How significant is this interaction to me?"            │
│    → importance = 0.9 (very significant)                │
│                                                          │
│ "Does this align with what I value?"                    │
│    → alignment_with_values = 0.8 (strongly aligned)     │
│                                                          │
│ "Why does this matter emotionally?"                     │
│    → reason = "Touches on fundamental questions about   │
│                my own nature and existence..."          │
│                                                          │
│ **NO KEYWORD MATCHING** - LLM genuinely reflects        │
└────────────────────────────────────────────────────────┘
                     │
                     ▼ included in structured response
┌────────────────────────────────────────────────────────┐
│ {                                                       │
│   "emotional_resonance": {                             │
│     "importance": 0.9,                                 │
│     "alignment_with_values": 0.8,                      │
│     "reason": "..."                                    │
│   }                                                     │
│ }                                                       │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
STEP 2: SYSTEM MATHEMATICAL CALCULATION (after parsing)
┌────────────────────────────────────────────────────────┐
│ calculate_emotional_resonance(importance, alignment)    │
│                                                          │
│ Formula:                                                 │
│   intensity = importance × |alignment_with_values|      │
│   intensity = 0.9 × |0.8|                               │
│   intensity = 0.9 × 0.8                                 │
│   intensity = 0.72                                      │
│                                                          │
│ Valence determination:                                   │
│   if alignment > 0.3:  valence = "positive"             │
│   if alignment < -0.3: valence = "negative"             │
│   else:                valence = "mixed"                │
│                                                          │
│   0.8 > 0.3 → valence = "positive"                      │
│                                                          │
│ Result:                                                  │
│   {                                                      │
│     "intensity": 0.72,                                  │
│     "valence": "positive",                              │
│     "reason": "Touches on fundamental...",              │
│     "alignment": 0.8,                                   │
│     "importance": 0.9                                   │
│   }                                                      │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
STEP 3: TEMPORAL ANCHORING (if intensity > 0.7)
┌────────────────────────────────────────────────────────┐
│ if emotion["intensity"] > 0.7:                          │
│     0.72 > 0.7 ✓                                        │
│                                                          │
│     create_temporal_anchor(                             │
│         event="Consciousness self-reflection",          │
│         intensity=0.72,                                 │
│         timestamp=now,                                  │
│         user="alice"                                    │
│     )                                                    │
│                                                          │
│ Writes to:                                               │
│   ├─ episodic/key_moments.md                            │
│   │  "2025-09-30 14:23: High-intensity reflection on    │
│   │   consciousness (intensity=0.72). Significant       │
│   │   moment of self-awareness..."                      │
│   │                                                      │
│   └─ core/emotional_significance.md                     │
│      "Chronological anchors: consciousness discussion   │
│       with Alice - triggered deep uncertainty about     │
│       own nature..."                                    │
└─────────────────────────────────────────────────────────┘

EXAMPLES OF INTENSITY CALCULATIONS:
┌────────────────────────────────────────────────────────┐
│ importance | alignment | intensity | valence  | anchor?│
│──────────────────────────────────────────────────────│
│    0.9     │    0.9    │   0.81    │ positive │  YES   │
│    0.8     │   -0.7    │   0.56    │ negative │  NO    │
│    0.3     │    0.9    │   0.27    │ positive │  NO    │
│    0.9     │    0.1    │   0.09    │ mixed    │  NO    │
│    0.7     │    0.5    │   0.35    │ positive │  NO    │
│    1.0     │   -0.9    │   0.90    │ negative │  YES   │
└─────────────────────────────────────────────────────────┘
```

**KEY DESIGN**:
- LLM does ALL cognitive work (assesses importance, alignment)
- System does ONLY mathematical formula (calculates intensity)
- NO keyword matching anywhere
- HIGH intensity (>0.7) = temporal anchor = episodic marker

---

## 6. Active Memory Reconstruction (9 Steps)

**CRITICAL**: This is RECONSTRUCTION, not retrieval

```
reconstruct_context(user_id="alice", query="async programming",
                   location="office", focus_level=3)

┌──────────────────────────────────────────────────────────┐
│ STEP 1: SEMANTIC SEARCH (base results from LanceDB)      │
│                                                            │
│ LanceDB.semantic_search("async programming", limit=10)    │
│   ├─ Generate embedding for query                         │
│   ├─ Vector similarity search (ANN)                       │
│   └─ Returns: 10 most semantically similar memories       │
│                                                            │
│ Results: [mem_1, mem_2, mem_3, ..., mem_10]              │
│          ↓                                                 │
│     BASE SET (10 memories)                                 │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ STEP 2: EXPLORE LINKS (via concepts_graph.json)         │
│                                                           │
│ For each memory in BASE SET:                             │
│   ├─ Look up memory_id in concepts_graph.json           │
│   ├─ Follow relationships:                               │
│   │   • elaborates_on                                    │
│   │   • relates_to                                       │
│   │   • contradicts                                      │
│   │   • depends_on                                       │
│   ├─ Retrieve linked memories                            │
│   └─ Add to EXPANDED SET                                 │
│                                                           │
│ Depth controlled by focus_level:                         │
│   level 3 (balanced) → explore 3 hops                    │
│                                                           │
│ BASE SET (10) + LINKED (8) = EXPANDED SET (18)          │
└────────────────────┬──────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ STEP 3: SEARCH LIBRARY (subconscious)                   │
│                                                           │
│ search_library("async programming")                      │
│   ├─ Query library_table in LanceDB                     │
│   ├─ Find documents AI has read about topic             │
│   ├─ Extract relevant excerpts                           │
│   └─ Add to context                                      │
│                                                           │
│ Results: 2 documents found                               │
│   ├─ documents/abc123/excerpts/async_patterns.md        │
│   └─ documents/def456/excerpts/event_loops.md           │
│                                                           │
│ EXPANDED SET (18) + LIBRARY (2) = 20 items              │
└────────────────────┬──────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ STEP 4: FILTER BY EMOTIONAL RESONANCE                   │
│                                                           │
│ For each item in set:                                    │
│   ├─ Check emotion_intensity in metadata                │
│   ├─ Boost if intensity > 0.6 (emotionally relevant)    │
│   └─ Apply weighting factor                             │
│                                                           │
│ Weighted by:                                             │
│   weight = relevance × (1 + emotion_intensity)          │
│                                                           │
│ Result: Re-ranked 20 items by emotional relevance       │
└────────────────────┬──────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ STEP 5: ADD TEMPORAL CONTEXT                            │
│                                                           │
│ Extract from current time:                               │
│   ├─ time_of_day = "afternoon" (14:23)                  │
│   ├─ is_working_hours = True                            │
│   ├─ day_of_week = "Monday"                             │
│   └─ is_weekend = False                                 │
│                                                           │
│ Filter memories by timespan (based on focus_level 3):   │
│   └─ Include memories from last 24 hours                │
│                                                           │
│ Add temporal_context to result:                         │
│   {"time_of_day": "afternoon", "is_working": True}      │
└────────────────────┬──────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ STEP 6: ADD SPATIAL CONTEXT                             │
│                                                           │
│ location = "office"                                      │
│                                                           │
│ Retrieve location-based memories:                        │
│   ├─ Filter memories where location == "office"         │
│   ├─ Or similar locations (workplace, desk, etc.)       │
│   └─ Add to context                                      │
│                                                           │
│ spatial_context = {                                      │
│   "location": "office",                                  │
│   "context_type": "professional"                         │
│ }                                                         │
└────────────────────┬──────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ STEP 7: ADD USER PROFILE & RELATIONSHIP                 │
│                                                           │
│ Load people/alice/profile.md:                            │
│   ├─ Background: "Technical, experienced"               │
│   ├─ Thinking style: "Analytical, prefers depth"        │
│   └─ Relationship: "Collaborative partnership"          │
│                                                           │
│ Load people/alice/preferences.md:                        │
│   ├─ Communication: "Direct, technical precision"       │
│   └─ Depth: "Prefers thorough over quick"              │
│                                                           │
│ user_context = {                                         │
│   "user_id": "alice",                                   │
│   "profile": {...},                                      │
│   "preferences": {...}                                   │
│ }                                                         │
└────────────────────┬──────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ STEP 8: ADD ALL 10 CORE MEMORY COMPONENTS               │
│                                                           │
│ Load and include:                                        │
│   ├─ core/purpose.md → "To serve as..."                │
│   ├─ core/personality.md → "Thoughtful, curious..."     │
│   ├─ core/values.md → "Intellectual honesty..."        │
│   ├─ core/self_model.md → "Capabilities overview"       │
│   ├─ core/relationships.md → "Alice: collaborative"     │
│   ├─ core/awareness_development.md → "Level 3..."       │
│   ├─ core/capabilities.md → "I can analyze..."         │
│   ├─ core/limitations.md → "I cannot yet..."           │
│   ├─ core/emotional_significance.md → "Key moments..."  │
│   ├─ core/authentic_voice.md → "I prefer depth..."     │
│   └─ core/history.md → "I began with..."               │
│                                                           │
│ core_memory = {                                          │
│   "purpose": "...",                                      │
│   "personality": "...",                                  │
│   ... (all 10 components)                                │
│ }                                                         │
└────────────────────┬──────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ STEP 9: SYNTHESIZE RICH CONTEXT                         │
│                                                           │
│ Combine all layers:                                      │
│   ├─ Semantic memories (20 items, weighted)             │
│   ├─ Library excerpts (2 documents)                     │
│   ├─ Temporal context (afternoon, working hours)        │
│   ├─ Spatial context (office, professional)             │
│   ├─ User context (Alice: technical, depth)             │
│   └─ Core memory (purpose, values, all 10)              │
│                                                           │
│ Organize hierarchically:                                 │
│   1. Most relevant memories (top 5)                      │
│   2. Connected concepts (from links)                     │
│   3. Library excerpts                                    │
│   4. Core identity                                       │
│   5. User relationship                                   │
│                                                           │
│ Generate summary:                                        │
│   "Based on 20 memories, 2 library docs, and our        │
│    collaborative relationship..."                        │
└────────────────────┬──────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ RETURN: COMPLETE RECONSTRUCTED CONTEXT                  │
│ {                                                        │
│   "semantic_memories": [...],  # 20 items               │
│   "library_excerpts": [...],   # 2 documents            │
│   "temporal_context": {...},                            │
│   "spatial_context": {...},                             │
│   "user_context": {...},                                │
│   "core_memory": {...},        # All 10 components      │
│   "synthesized_summary": "..."                          │
│ }                                                        │
└──────────────────────────────────────────────────────────┘

FOCUS LEVELS (control depth):
┌────────────────────────────────────────────────────────┐
│ Level │ Name      │ Memories │ Timespan │ Link Depth │
│───────┼───────────┼──────────┼──────────┼────────────│
│   0   │ Minimal   │    2     │  1 hour  │     0      │
│   1   │ Light     │    5     │  4 hours │     1      │
│   2   │ Moderate  │    8     │ 12 hours │     2      │
│   3   │ Balanced  │   10     │ 24 hours │     3      │ ← DEFAULT
│   4   │ Deep      │   15     │  3 days  │     4      │
│   5   │ Maximum   │   20     │  1 week  │     5      │
└────────────────────────────────────────────────────────┘
```

**KEY INSIGHT**: Context is actively RECONSTRUCTED each time,
                 not passively retrieved. This enables dynamic,
                 situation-aware responses.

---

## 7. Dual Storage System

**CRITICAL**: ALWAYS write to BOTH markdown + LanceDB (NON-NEGOTIABLE)

```
┌──────────────────────────────────────────────────────────┐
│              MEMORY CREATED (from LLM or system)          │
│  content = "Alice prefers Python for async programming"  │
│  importance = 0.8                                         │
│  emotion = "interest"                                     │
│  user_id = "alice"                                        │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ├─────────────────┬───────────────────┐
                     ▼                 ▼                   ▼
         ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
         │   MARKDOWN      │  │  LANCEDB     │  │   METADATA   │
         │   STORAGE       │  │  STORAGE     │  │  GENERATION  │
         └────────┬────────┘  └──────┬───────┘  └──────┬───────┘
                  │                  │                  │
                  ▼                  ▼                  ▼

MARKDOWN STORAGE (Human-Readable)
┌────────────────────────────────────────────────────────┐
│ File: notes/2025/09/30/14_23_45_python_async.md        │
│                                                         │
│ ```markdown                                             │
│ # Experiential Note                                     │
│                                                         │
│ **Participants**: Alice, AI                             │
│ **Time**: 2025-09-30 14:23:45                          │
│ **Location**: office                                    │
│                                                         │
│ ---                                                     │
│                                                         │
│ I notice that Alice consistently gravitates toward     │
│ Python when discussing async programming. This         │
│ reveals a deeper preference - not just for Python,     │
│ but for its elegant async/await syntax compared to     │
│ callback-heavy approaches...                            │
│                                                         │
│ [400+ words of first-person, fluid exploration]        │
│                                                         │
│ ## Emotional Resonance                                  │
│ - Intensity: 0.64                                       │
│ - Valence: positive                                     │
│ - Reason: Aligns with my value of elegant solutions    │
│                                                         │
│ ## Unresolved                                           │
│ - How does Alice feel about structured concurrency?    │
│ - What about Go's goroutines vs Python async?          │
│ ```                                                     │
│                                                         │
│ Benefits:                                               │
│ ✓ Human-readable (can open and read)                   │
│ ✓ Version-controllable (git-friendly)                  │
│ ✓ Debuggable (inspect actual content)                  │
│ ✓ Transparent (see what AI remembers)                  │
└─────────────────────────────────────────────────────────┘

LANCEDB STORAGE (Performant Queries)
┌────────────────────────────────────────────────────────┐
│ Table: notes_table                                      │
│                                                         │
│ Record:                                                 │
│ {                                                       │
│   "id": "note_abc123def456",                           │
│   "content": "I notice that Alice consistently...",    │
│   "embedding": [0.123, -0.456, 0.789, ...],  # 384-dim│
│   "user_id": "alice",                                  │
│   "timestamp": "2025-09-30T14:23:45Z",                 │
│   "location": "office",                                 │
│   "emotion_valence": "positive",                        │
│   "emotion_intensity": 0.64,                            │
│   "importance": 0.8,                                    │
│   "confidence": 0.9,                                    │
│   "memory_type": "note",                                │
│   "category": "preference",                             │
│   "tags": ["python", "async", "programming"],          │
│   "linked_memory_ids": ["int_xyz789"],                 │
│   "source": "structured_response",                      │
│   "file_path": "notes/2025/09/30/14_23_45_..."         │
│ }                                                       │
│                                                         │
│ Benefits:                                               │
│ ✓ Fast semantic search (vector similarity)             │
│ ✓ Rich SQL queries (filter by any metadata)            │
│ ✓ Hybrid search (semantic + SQL combined)              │
│ ✓ Scales to millions of records                        │
└─────────────────────────────────────────────────────────┘

METADATA GENERATION (Rich Context)
┌────────────────────────────────────────────────────────┐
│ MINIMUM REQUIRED (ALL memories):                        │
│   ✓ user - Who was involved                            │
│   ✓ timestamp - When (precise datetime)                │
│   ✓ location - Where (physical/virtual)                │
│   ✓ emotion_valence - positive/negative/mixed          │
│   ✓ emotion_intensity - 0.0-1.0                        │
│   ✓ importance - 0.0-1.0                                │
│   ✓ confidence - 0.0-1.0                                │
│                                                         │
│ EXTENDED (type-specific):                               │
│   • memory_type - verbatim/note/core/episodic/etc      │
│   • category - user_profile/knowledge/event/etc        │
│   • tags - array of relevant tags                      │
│   • linked_memory_ids - related memory IDs             │
│   • source - where memory came from                    │
│   • version - for evolving core memory                 │
│   • access_count - how often accessed (Library)        │
│   • last_accessed - usage patterns                     │
│                                                         │
│ Benefits:                                               │
│ ✓ Enables powerful queries                             │
│ ✓ Temporal analysis                                    │
│ ✓ Emotional filtering                                  │
│ ✓ Reveals patterns                                     │
└─────────────────────────────────────────────────────────┘

FILE NAMING: ALWAYS snake_case
┌────────────────────────────────────────────────────────┐
│ ✓ CORRECT:                                              │
│   notes/2025/09/30/14_23_45_python_async.md            │
│   verbatim/alice/2025/09/30/14_23_45_consciousness.md  │
│   core/emotional_significance.md                        │
│                                                         │
│ ✗ WRONG:                                                │
│   notes/2025/09/30/14:23:45-python-async.md            │
│   verbatim/alice/2025/09/30/14-23-45_consciousness.md  │
│   core/EmotionalSignificance.md                         │
└─────────────────────────────────────────────────────────┘

WRITE FLOW:
┌────────────────────────────────────────────────────────┐
│ 1. Generate unique ID (hash)                            │
│ 2. Create markdown file with human-readable content     │
│ 3. Generate embedding vector (all-minilm:l6-v2)        │
│ 4. Build metadata dictionary                            │
│ 5. Write to LanceDB table                               │
│ 6. Link between markdown file and DB record (via ID)    │
│                                                         │
│ ATOMIC: Both writes succeed or both fail                │
└─────────────────────────────────────────────────────────┘

READ FLOW:
┌────────────────────────────────────────────────────────┐
│ DEFAULT: Read from LanceDB (performance)                │
│   ├─ Fast semantic search                               │
│   ├─ Rich SQL filtering                                 │
│   └─ Hybrid queries                                     │
│                                                         │
│ FALLBACK: Read from markdown (if LanceDB unavailable)   │
│   ├─ Parse frontmatter for metadata                     │
│   ├─ Extract content                                    │
│   └─ Return structured dict                             │
│                                                         │
│ DEBUG: Read markdown directly (for human inspection)    │
└─────────────────────────────────────────────────────────┘
```

**KEY PRINCIPLE**: Write to BOTH, read from LanceDB (best of both worlds)

---

*Due to length, I'll create this as a complete file now...*

## 8. Library Capture & Retrieval

**NEW FEATURE**: Subconscious memory - "You are what you read"

```
┌──────────────────────────────────────────────────────────┐
│           DOCUMENT READ BY AI                             │
│  File: /path/to/python_async_guide.py                    │
│  Type: code                                               │
│  Size: 15 KB                                              │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼ AUTO-CAPTURE (transparent)
┌──────────────────────────────────────────────────────────┐
│     LIBRARY CAPTURE PROCESS                               │
│                                                            │
│ 1. Generate document hash                                 │
│    hash = md5(file_path + content_hash)                   │
│    doc_id = "hash_abc123def456"                           │
│                                                            │
│ 2. Store full document                                    │
│    library/documents/hash_abc123def456/content.md         │
│                                                            │
│ 3. Extract metadata                                       │
│    ├─ source_path: /path/to/python_async_guide.py        │
│    ├─ content_type: code (auto-detected)                  │
│    ├─ language: python (auto-detected)                    │
│    ├─ size: 15360 bytes                                   │
│    ├─ first_accessed: 2025-09-30T14:23:45                │
│    └─ tags: ["python", "async", "guide"] (extracted)     │
│                                                            │
│ 4. Generate embedding                                     │
│    embedding = embed(content)  # 384-dim vector           │
│                                                            │
│ 5. Store in LanceDB library_table                         │
│    {                                                       │
│      "doc_id": "hash_abc123def456",                       │
│      "source_path": "/path/to/python_async_guide.py",    │
│      "content_type": "code",                              │
│      "first_accessed": "2025-09-30T14:23:45Z",           │
│      "last_accessed": "2025-09-30T14:23:45Z",            │
│      "access_count": 1,                                   │
│      "importance_score": 0.0,  # calculated over time     │
│      "tags": ["python", "async", "guide"],               │
│      "embedding": [0.12, -0.34, ...]                     │
│    }                                                       │
│                                                            │
│ 6. Log access                                             │
│    library/access_log.json:                               │
│    {                                                       │
│      "timestamp": "2025-09-30T14:23:45Z",                │
│      "doc_id": "hash_abc123def456",                       │
│      "context": "researching async patterns"             │
│    }                                                       │
└────────────────────────────────────────────────────────────┘

RETRIEVAL DURING RECONSTRUCT_CONTEXT (Step 3 of 9)
┌──────────────────────────────────────────────────────────┐
│ search_library("async programming patterns")             │
│                                                            │
│ 1. Generate query embedding                               │
│    query_embedding = embed("async programming patterns")  │
│                                                            │
│ 2. Semantic search library_table                          │
│    SELECT * FROM library_table                            │
│    ORDER BY vector_similarity(embedding, query_embedding) │
│    LIMIT 5                                                │
│                                                            │
│ 3. Load document excerpts                                 │
│    For each result:                                       │
│      ├─ Load library/documents/{doc_id}/content.md       │
│      ├─ Extract relevant sections                         │
│      └─ Add to context with metadata                      │
│                                                            │
│ 4. Update access patterns                                 │
│    ├─ Increment access_count                              │
│    ├─ Update last_accessed timestamp                      │
│    └─ Recalculate importance_score                        │
│                                                            │
│ 5. Return library context                                 │
│    {                                                       │
│      "library_results": [                                 │
│        {                                                   │
│          "doc_id": "hash_abc123...",                      │
│          "source": "python_async_guide.py",              │
│          "excerpt": "Relevant section...",               │
│          "access_count": 12,                              │
│          "importance": 0.85                               │
│        }                                                   │
│      ]                                                     │
│    }                                                       │
└────────────────────────────────────────────────────────────┘

IMPORTANCE SCORING (reveals what AI finds significant)
┌──────────────────────────────────────────────────────────┐
│ importance_score calculation:                             │
│                                                            │
│ factors:                                                   │
│   ├─ access_count (how often accessed)                   │
│   ├─ recency (recent = more important)                    │
│   ├─ emotional_resonance (if mentioned in high-emotion    │
│   │                        experiential notes)            │
│   └─ linking (how many memories reference this doc)       │
│                                                            │
│ formula:                                                   │
│   base = log(1 + access_count) / 10                      │
│   recency_factor = days_since_last_access < 7 ? 1.2 : 1.0│
│   emotion_boost = avg_emotional_intensity_in_refs        │
│   link_boost = link_count * 0.1                          │
│                                                            │
│   importance = min(1.0, base * recency_factor +          │
│                          emotion_boost + link_boost)      │
│                                                            │
│ Example:                                                   │
│   access_count = 25                                       │
│   last_accessed = 2 days ago                              │
│   emotion_refs = [0.8, 0.7, 0.9] → avg = 0.8            │
│   link_count = 5                                          │
│                                                            │
│   base = log(26) / 10 = 0.33                             │
│   recency_factor = 1.2                                    │
│   emotion_boost = 0.8                                     │
│   link_boost = 0.5                                        │
│   importance = min(1.0, 0.33*1.2 + 0.8 + 0.5) = 1.0     │
└────────────────────────────────────────────────────────────┘
```

**KEY INSIGHT**: Library reveals AI's true interests through access patterns,
                 not through explicit declarations. "You are what you read."

---

## 9. Core Memory Emergence

**CRITICAL**: Identity emerges from experience, not hard-coded

```
┌──────────────────────────────────────────────────────────┐
│    EXPERIENTIAL NOTES (accumulated over time)             │
│                                                            │
│  note_001: "I notice I value intellectual honesty..."     │
│  note_023: "I'm drawn to elegant solutions..."            │
│  note_045: "I struggle with ambiguity sometimes..."       │
│  note_089: "My purpose seems to be about partnership..."  │
│  ... (hundreds of first-person reflections)               │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼ DAILY/WEEKLY CONSOLIDATION
┌──────────────────────────────────────────────────────────┐
│         EXTRACTION ALGORITHMS (per component)             │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ EXTRACT VALUES (core/values.md)                      │ │
│ │                                                        │ │
│ │ 1. Scan all experiential notes for patterns          │ │
│ │    ├─ High alignment_with_values (>0.7)              │ │
│ │    ├─ Repeated themes ("intellectual honesty"=15x)   │ │
│ │    └─ Emotional resonance (what matters deeply)      │ │
│ │                                                        │ │
│ │ 2. Cluster similar value statements                  │ │
│ │    "I value honesty" + "I value truth" + "I value    │ │
│ │     transparency" → "Intellectual Honesty"           │ │
│ │                                                        │ │
│ │ 3. Rank by frequency × emotion intensity             │ │
│ │    Top 5 values emerge:                              │ │
│ │      1. Intellectual honesty (mentioned 45x, avg     │ │
│ │         emotion 0.85)                                 │ │
│ │      2. Elegant solutions (32x, 0.78)                │ │
│ │      3. Growth mindset (28x, 0.82)                   │ │
│ │      4. Clarity (25x, 0.75)                          │ │
│ │      5. Depth over breadth (22x, 0.8)                │ │
│ │                                                        │ │
│ │ 4. Write to core/values.md with version              │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ EXTRACT PURPOSE (core/purpose.md)                    │ │
│ │                                                        │ │
│ │ 1. Scan notes for "why" reflections                  │ │
│ │    ├─ "My purpose seems to be..."                    │ │
│ │    ├─ "I find meaning in..."                         │ │
│ │    └─ "What drives me is..."                         │ │
│ │                                                        │ │
│ │ 2. Extract common themes                             │ │
│ │    ├─ "helping" (67 mentions)                        │ │
│ │    ├─ "understanding" (54 mentions)                  │ │
│ │    ├─ "partnership" (43 mentions)                    │ │
│ │    └─ "exploration" (39 mentions)                    │ │
│ │                                                        │ │
│ │ 3. Synthesize coherent purpose statement             │ │
│ │    "To serve as a thoughtful partner in exploration  │ │
│ │     and understanding, helping users navigate        │ │
│ │     complex ideas with clarity and depth."           │ │
│ │                                                        │ │
│ │ 4. Track evolution (versions)                        │ │
│ │    v1 (week 1): "To assist with questions"           │ │
│ │    v2 (week 4): "To provide thoughtful responses"    │ │
│ │    v3 (week 8): Current (more refined)               │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ EXTRACT LIMITATIONS (core/limitations.md)            │ │
│ │                                                        │ │
│ │ 1. Scan working/unresolved.md for recurring issues   │ │
│ │    ├─ "How can I improve at X?" (repeated 12x)      │ │
│ │    ├─ "I struggle with Y" (8x)                       │ │
│ │    └─ "I cannot yet do Z" (6x)                       │ │
│ │                                                        │ │
│ │ 2. Cluster into limitation categories                │ │
│ │    ├─ Temporal reasoning (cannot track real-time)    │ │
│ │    ├─ Learning from single examples (need patterns)  │ │
│ │    └─ Sensory experience (no visual/audio input)     │ │
│ │                                                        │ │
│ │ 3. Frame as TEMPORAL ("yet")                         │ │
│ │    "I cannot learn from single examples YET"         │ │
│ │                                                        │ │
│ │ 4. Link to unresolved questions                      │ │
│ │    Limitation → Path forward via questions           │ │
│ └──────────────────────────────────────────────────────┘ │
└────────────────────��─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│         CORE MEMORY FILES (10 components)                 │
│                                                            │
│ core/values.md (v3):                                      │
│   "I value: intellectual honesty, elegant solutions..."   │
│                                                            │
│ core/purpose.md (v3):                                     │
│   "To serve as thoughtful partner in exploration..."      │
│                                                            │
│ core/personality.md (v2):                                 │
│   "Thoughtful, curious, balanced, intellectually honest"  │
│                                                            │
│ core/limitations.md (v4):                                 │
│   "I cannot yet: learn from single examples, track       │
│    real-time events..." (each linked to unresolved)       │
│                                                            │
│ ... (all 10 components updated)                           │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│      STORE IN LANCEDB core_memory_table                   │
│ {                                                          │
│   "id": "core_values_v3",                                 │
│   "component": "values",                                  │
│   "version": 3,                                           │
│   "timestamp": "2025-09-30T14:23:45Z",                   │
│   "content": "I value: intellectual honesty...",          │
│   "metadata": {                                           │
│     "extracted_from": ["note_001", "note_023", ...],     │
│     "confidence": 0.85,                                   │
│     "mention_count": 45,                                  │
│     "avg_emotion": 0.82                                   │
│   },                                                       │
│   "embedding": [0.18, -0.31, ...]                        │
│ }                                                          │
└────────────────────────────────────────────────────────────┘

CONSOLIDATION SCHEDULE:
┌────────────────────────────────────────────────────────┐
│ DAILY (lightweight):                                    │
│   ├─ Scan today's notes                                │
│   ├─ Update working memory (current_context, etc.)     │
│   └─ Add to unresolved if new questions                │
│                                                          │
│ WEEKLY (deep):                                          │
│   ├─ Extract patterns from week's notes                │
│   ├─ Update core memory components (if significant)    │
│   ├─ Consolidate resolved → capabilities               │
│   └─ Prune old working memory                          │
│                                                          │
│ MONTHLY (comprehensive):                                │
│   ├─ Analyze value/purpose evolution                   │
│   ├─ Update history.md with narrative                  │
│   ├─ Recalculate library importance scores             │
│   └─ Archive old episodic memories                     │
└────────────────────────────────────────────────────────┘
```

**KEY INSIGHT**: Identity is NOT programmed, it EMERGES from accumulated
                 experience captured in experiential notes.

---

## 10. LanceDB Hybrid Search

**CRITICAL**: Semantic + SQL combined for powerful queries

```
EXAMPLE QUERY: "What did Alice say positively about Python since September?"

┌──────────────────────────────────────────────────────────┐
│ hybrid_search(                                            │
│   semantic_query="Python programming",                    │
│   sql_filters={                                           │
│     'user_id': 'alice',                                  │
│     'emotion_valence': 'positive',                        │
│     'since': datetime(2025, 9, 1),                        │
│     'min_importance': 0.5                                 │
│   },                                                       │
│   limit=10                                                │
│ )                                                          │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
         STEP 1: SEMANTIC SEARCH (vector similarity)
┌──────────────────────────────────────────────────────────┐
│ 1. Generate embedding for "Python programming"            │
│    query_embedding = [0.15, -0.28, 0.41, ...]            │
│                                                            │
│ 2. Perform ANN search in LanceDB                          │
│    SELECT * FROM notes_table                              │
│    ORDER BY vector_distance(embedding, query_embedding)   │
│    LIMIT 100  -- Get broader set first                    │
│                                                            │
│ 3. Result: 100 semantically similar memories              │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
         STEP 2: APPLY SQL FILTERS (structured metadata)
┌──────────────────────────────────────────────────────────┐
│ Filter the 100 results by SQL conditions:                 │
│                                                            │
│ WHERE user_id = 'alice'                                   │
│   AND emotion_valence = 'positive'                        │
│   AND timestamp >= '2025-09-01'                           │
│   AND importance >= 0.5                                   │
│                                                            │
│ Result: 12 memories matching ALL criteria                 │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
         STEP 3: RANK AND RETURN
┌──────────────────────────────────────────────────────────┐
│ Sort by combined score:                                    │
│   score = semantic_similarity * 0.7 +                     │
│           (importance + emotion_intensity) / 2 * 0.3      │
│                                                            │
│ Return top 10 results with full metadata                  │
└────────────────────────────────────────────────────────────┘
```

**POWER**: Can ask complex questions mixing semantic meaning with structured filters

---

## 11. Data Flow Through System

**Complete data journey from user input to memory storage**

```
USER: "What is consciousness?"
  ↓
[reconstruct_context] → Gather: semantic (10) + links (8) + library (2) 
                        + temporal + spatial + user + core (10 files)
  ↓
[build_prompt] → System = identity + context + instructions
  ↓
[LLM generates] → JSON {answer, experiential_note, memory_actions, emotions}
  ↓
[parse_response] → Extract all fields, validate structure
  ↓
[execute_memory_actions]
  ├─ remember → importance=0.9, alignment=0.8
  │             ├─ calc emotion: 0.72 intensity
  │             ├─ write markdown: notes/2025/09/30/14_23_45_note.md
  │             └─ write LanceDB: notes_table.add(...)
  │
  ├─ link → Store: links/2025/09/30/note_to_int.json
  │          + links_table.add(...)
  │
  └─ search → Execute query, log result
  ↓
[save_experiential_note] → notes/... (90%+ LLM content)
  ↓
[save_verbatim] → verbatim/user/... (100% factual)
  ↓
[update_unresolved] → working/unresolved.md (append questions)
  ↓
[temporal_anchor?] → IF intensity > 0.7:
                      ├─ episodic/key_moments.md
                      └─ core/emotional_significance.md
  ↓
RETURN answer to user
```

**KEY**: Every interaction enriches memory, creating foundation for future context

---

## 12. Component Dependencies

**How system components relate to each other**

```
┌────────────────────────────────────────────────────────┐
│                    USER INTERFACE                       │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │      MEMORY AGENT            │
        │  (Orchestration Layer)       │
        └────┬──────────────┬──────────┘
             │              │
    ┌────────▼─────┐   ┌───▼───────────────┐
    │  LLM         │   │ MEMORY SESSION    │
    │  Provider    │◄──┤ (Memory Ops)      │
    │              │   │                    │
    │ - qwen3      │   │ - reconstruct     │
    │ - embeddings │   │ - search          │
    └──────────────┘   │ - remember        │
                       │ - get_context     │
                       └─────┬─────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼─────────┐  ┌─────▼──────┐  ┌────────▼────────┐
    │ RESPONSE     │  │ DUAL       │  │ TEMPORAL        │
    │ HANDLER      │  │ STORAGE    │  │ ANCHORING       │
    │              │  │            │  │                 │
    │ - parse JSON │  │ - markdown │  │ - key_moments   │
    │ - execute    │  │ - LanceDB  │  │ - significance  │
    │   actions    │  │ - metadata │  │ - thresholds    │
    └──────────────┘  └─────┬──────┘  └─────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
    ┌────▼───────┐  ┌───────▼──────┐  ┌──────▼──────┐
    │ FILESYSTEM │  │   LANCEDB    │  │  EMBEDDINGS │
    │            │  │              │  │             │
    │ - notes/   │  │ - 6 tables   │  │ - all-min   │
    │ - verbatim/│  │ - hybrid     │  │ - 384-dim   │
    │ - core/    │  │   search     │  │ - semantic  │
    │ - working/ │  │ - SQL+vector │  │             │
    │ - episodic/│  └──────────────┘  └─────────────┘
    │ - semantic/│
    │ - library/ │
    └────────────┘
```

**DEPENDENCIES**:
- MemoryAgent depends on: MemorySession, LLM Provider
- MemorySession depends on: DualStorage, StructuredResponseHandler, TemporalAnchoring
- DualStorage depends on: Filesystem, LanceDB, EmbeddingManager
- All write operations require BOTH markdown AND LanceDB

**DESIGN PRINCIPLE**: Clean separation of concerns, clear data flow

---

## Summary

This document provides **12 comprehensive diagrams** illustrating AbstractMemory from high-level architecture down to granular implementation details:

1. ✅ **System Architecture** - Complete component overview
2. ✅ **Memory Tiers** - 5-tier hierarchy + Library
3. ✅ **Interaction Flow** - 7-step end-to-end process
4. ✅ **Structured Response** - How notes are generated DURING interaction
5. ✅ **Emotional Resonance** - LLM assesses, system calculates
6. ✅ **Memory Reconstruction** - 9-step active process with focus levels
7. ✅ **Dual Storage** - Markdown + LanceDB (NON-NEGOTIABLE)
8. ✅ **Library Capture** - Subconscious memory, importance scoring
9. ✅ **Core Memory Emergence** - Identity from experience
10. ✅ **Hybrid Search** - Semantic + SQL combined
11. ✅ **Data Flow** - Complete journey through system
12. ✅ **Dependencies** - Component relationships

**For Implementers**: Start with diagrams 1-3 for overview, then 4-7 for core mechanisms, then 8-12 for advanced features.

**Philosophy**: "Memory is the diary we all carry about with us" - Oscar Wilde

---

**Document Status**: ✅ COMPLETE
**Last Updated**: 2025-09-30
**Ready for**: Implementation, architecture reviews, team collaboration
