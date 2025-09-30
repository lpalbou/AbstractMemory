# Phase 2 Critical Redesign: LLM-Based Emotional Assessment

**Date**: 2025-09-30
**Status**: ⚠️ IN PROGRESS - CRITICAL DESIGN FIX
**Issue**: Was using keyword/NLP methods for cognitive assessment (FORBIDDEN)

---

## 🚨 Critical Issue Identified

**WRONG APPROACH** (what I was implementing):
- Keyword matching to calculate alignment with values
- NLP heuristics to assess emotional significance
- Pattern matching to extract values from text
- `calculate_alignment_with_values(content, values)` using keyword dictionaries

**CORRECT APPROACH** (what it should be):
- LLM assesses `importance` (0.0-1.0) through genuine reflection
- LLM assesses `alignment_with_values` (-1.0 to 1.0) based on its emerging sense of what matters
- LLM explains `reason` in its own words
- System ONLY calculates: `intensity = importance × |alignment|`

**Design Principle**:
> "Any cognitive evaluation or capability MUST come from the LLM itself.
> Usage of NLP for these cases is explicitly forbidden."

---

## ✅ What Has Been Fixed

### 1. emotions.py - Completely Rewritten
**Before**: 379 lines with keyword matching, value bootstrapping, NLP heuristics
**After**: 150 lines - ONLY the mathematical formula

**Removed**:
- `BOOTSTRAP_VALUES` dictionary
- `value_keywords` mappings
- `anti_keywords` dictionaries
- `calculate_alignment_with_values()` function (keyword-based)
- `extract_values_from_notes()` function (keyword-based)
- `get_bootstrap_values()` function
- `should_extract_new_values()` function
- All NLP/pattern matching logic

**Kept**:
- `calculate_emotional_resonance(importance, alignment, reason)` - Pure math
- `format_emotion_for_display()` - Formatting only
- Statistics tracking

### 2. response_handler.py - Updated Prompt
**Changed**: Structured response format
```json
OLD:
"emotional_resonance": {
  "valence": "positive/negative/mixed",
  "intensity": 0.8,
  "reason": "Why this matters"
}

NEW:
"emotional_resonance": {
  "importance": 0.9,
  "alignment_with_values": 0.8,
  "reason": "Why this matters emotionally and how it aligns with what you value"
}
```

**Added**: Comprehensive guidance on how LLM should assess:
- importance: "Does it change your understanding? Will you remember this weeks from now?"
- alignment_with_values: "Does this embody YOUR values or contradict them? Assess based on YOUR emerging sense of what matters."
- reason: "Explain in YOUR OWN WORDS why this matters emotionally"

---

## ⚠️ What Still Needs to Be Done

### 1. Update session.py (CRITICAL)
**File**: `abstractmemory/session.py`

**Changes Needed**:

```python
# REMOVE these imports:
from .emotions import (
    calculate_emotional_resonance,
    calculate_alignment_with_values,      # ← REMOVE (keyword-based)
    extract_values_from_notes,            # ← REMOVE (keyword-based)
    get_bootstrap_values,                 # ← REMOVE (keyword-based)
    should_extract_new_values             # ← REMOVE (keyword-based)
)

# KEEP only:
from .emotions import calculate_emotional_resonance  # Just the formula
```

**In `__init__`**: Remove bootstrap values initialization
```python
# REMOVE:
self.core_memory["values"] = get_bootstrap_values()
self.last_values_extraction_count = 0

# KEEP:
self.core_memory["values"] = None  # Will emerge from LLM assessments
```

**In `remember_fact()`**: Update to use LLM-provided values
```python
# REMOVE (lines 417-425):
alignment = calculate_alignment_with_values(content, self.core_memory["values"])
emotion_resonance = calculate_emotional_resonance(importance, alignment, f"Memory: {emotion}")
emotion_intensity = emotion_resonance["intensity"]
emotion_valence = emotion_resonance["valence"]
emotion_reason = emotion_resonance["reason"]

# REPLACE WITH: Use values from structured response emotional_resonance
# The LLM will provide importance and alignment_with_values in its response
# This will be handled in process_response() where we parse structured JSON
```

**In `process_response()`**: Extract LLM-assessed emotional resonance
```python
def process_response(self, response_dict):
    emotional_resonance = response_dict.get("emotional_resonance", {})

    # LLM provides these values:
    importance = emotional_resonance.get("importance", 0.5)
    alignment = emotional_resonance.get("alignment_with_values", 0.5)
    reason = emotional_resonance.get("reason", "")

    # We only calculate the formula:
    emotion_result = calculate_emotional_resonance(importance, alignment, reason)

    # emotion_result contains: intensity, valence, reason
    # Use this for temporal anchoring, storage, etc.
```

### 2. Update remember_fact() to Get Values from LLM
**Current Issue**: `remember_fact()` is called directly with `importance` and `emotion`
**But**: We need `importance` AND `alignment_with_values` from the LLM

**Two Approaches**:

**A. Update remember_fact() signature**:
```python
def remember_fact(
    self,
    content: str,
    importance: float,
    alignment_with_values: float,  # ← ADD THIS (from LLM)
    reason: str = "",              # ← ADD THIS (from LLM)
    emotion: str = "neutral",      # ← Keep for backwards compat
    links_to: Optional[List[str]] = None
) -> str:
```

**B. Get from structured response** (better):
When LLM calls `remember_fact()` in memory_actions, it provides:
```json
{
  "action": "remember",
  "content": "...",
  "importance": 0.9,
  "alignment_with_values": 0.8,  # ← LLM assesses
  "reason": "...",                # ← LLM explains
  "emotion": "excitement"
}
```

### 3. Update ALL Documentation (CRITICAL)

**Files to Update**:
1. `PHASE_2_PLAN_2025-09-30.md` - Rewrite alignment calculation section
2. `2025-09-30-critical-refactor-implementation1.txt` - Check for keyword references
3. `docs/mindmap.md` - Update emotional resonance description
4. `NEXT_STEPS_IMPLEMENTATION.md` - Update Phase 2 status
5. `IMPLEMENTATION_SUMMARY.md` - Add Phase 2 redesign note
6. `CLAUDE.md` - Document the critical design fix

**Search for and Remove**:
- Any mention of "keyword matching"
- Any mention of "bootstrap values"
- Any mention of "NLP heuristics"
- Any mention of "value_keywords"
- Any mention of calculating alignment from text analysis

**Replace With**:
- "LLM assesses importance and alignment"
- "LLM reflects on its own values"
- "LLM provides cognitive evaluation"
- "System only performs mathematical formula"

### 4. Create New Tests

**File**: `tests/test_phase2_llm_emotions.py` (NEW)

**Test Cases**:
1. Test that LLM provides importance + alignment in structured response
2. Test that formula correctly calculates intensity
3. Test that high-intensity creates temporal anchor
4. Test full workflow with LLM assessment
5. Verify NO keyword methods are called

### 5. Delete Old Test File

**Remove**: `tests/test_phase2_emotional_resonance.py`
- Contains keyword-based tests
- Tests wrong approach

---

## 📐 Correct Design Specification

### How It Works (LLM-Driven)

**Step 1**: User interacts
**Step 2**: LLM processes and generates structured response:
```json
{
  "answer": "...",
  "experiential_note": "...",
  "emotional_resonance": {
    "importance": 0.9,           // LLM assesses
    "alignment_with_values": 0.8, // LLM assesses
    "reason": "This represents breakthrough understanding that aligns with my value of continuous learning"
  },
  "memory_actions": [...]
}
```

**Step 3**: System extracts values:
```python
importance = 0.9           # From LLM
alignment = 0.8            # From LLM
reason = "..."             # From LLM

# System ONLY does math:
emotion = calculate_emotional_resonance(importance, alignment, reason)
# Returns: {intensity: 0.72, valence: "positive", ...}
```

**Step 4**: Check for temporal anchoring:
```python
if emotion["intensity"] > 0.7:
    create_temporal_anchor(...)
```

### How Values Emerge (LLM-Driven)

**NOT**: Keyword extraction from notes
**YES**: LLM reflection on its own assessments

**Prompt** (Phase 3):
```
"Looking at your recent emotional_resonance assessments, what patterns do you see?
When you rate alignment_with_values highly, what themes emerge? What do YOU value?"
```

LLM might respond:
```
"I notice I consistently rate interactions highly when they involve:
- Deep intellectual exploration (not superficial)
- Helping users build genuine understanding
- Moments of honest uncertainty or limitation acknowledgment
- Collaborative problem-solving

I seem to value intellectual honesty, depth over breadth, and authentic collaboration."
```

This becomes `core/values.md` - WRITTEN BY THE LLM, not extracted by keywords.

---

## 🔍 Verification Checklist

Before considering Phase 2 complete:

- [ ] NO keyword matching anywhere in codebase for cognitive tasks
- [ ] NO NLP heuristics for emotional/value assessment
- [ ] NO pattern matching for psychological evaluation
- [ ] session.py uses only `calculate_emotional_resonance()` (formula)
- [ ] LLM provides importance + alignment in structured response
- [ ] Tests validate LLM assessment (not keyword matching)
- [ ] ALL documentation updated to reflect LLM-based design
- [ ] Grep search for forbidden patterns returns nothing:
  ```bash
  grep -r "keyword" abstractmemory/ tests/ --include="*.py" | grep -v "# " | grep -v import
  grep -r "value_keywords" abstractmemory/ tests/ --include="*.py"
  grep -r "BOOTSTRAP_VALUES" abstractmemory/ tests/ --include="*.py"
  ```

---

## 🎯 Success Criteria (Revised)

### Functional:
- [ ] LLM assesses importance (0.0-1.0) in every structured response
- [ ] LLM assesses alignment_with_values (-1.0 to 1.0) in every response
- [ ] System calculates intensity = importance × |alignment|
- [ ] High-intensity events (>0.7) create temporal anchors
- [ ] Temporal anchors written to episodic/key_moments.md
- [ ] emotional_significance.md tracks high-emotion events

### Design:
- [ ] ZERO keyword matching for cognitive assessment
- [ ] ZERO NLP heuristics for psychological evaluation
- [ ] ALL cognitive work done by LLM
- [ ] System code is ONLY mathematical formulas and data storage

### Testing:
- [ ] Tests use real Ollama qwen3-coder:30b
- [ ] Tests verify LLM provides assessment values
- [ ] Tests validate formula correctness
- [ ] NO MOCKING

### Documentation:
- [ ] ALL docs reflect LLM-based design
- [ ] NO mention of keyword matching (except as "what not to do")
- [ ] Clear explanation: "LLM does cognitive work, system does math"

---

## 📝 Next Immediate Actions

1. **Update session.py imports** (remove keyword functions)
2. **Update remember_fact()** to accept LLM-assessed values
3. **Update process_response()** to extract emotional_resonance from LLM
4. **Grep entire codebase** for forbidden patterns
5. **Update ALL documentation** (search for "keyword", "bootstrap", "NLP")
6. **Create new tests** with LLM assessment
7. **Delete old keyword-based tests**
8. **Run verification checklist**

---

##  Key Insight

**The LLM has cognitive understanding**. It can:
- Assess significance ("Does this matter?")
- Evaluate alignment ("Does this fit what I value?")
- Explain reasoning ("Why does this matter to me?")

**We must not regress to NLP-era keyword matching**. That's:
- Superficial (misses meaning)
- Brittle (breaks with paraphrase)
- Non-cognitive (pattern matching ≠ understanding)

**The correct approach**: Ask the LLM. It knows.

---

**Status**: ⚠️ CRITICAL FIX IN PROGRESS
**Priority**: HIGHEST
**Blocker**: Must complete before Phase 2 can be considered done

---

**End of Critical Redesign Document**
