# Memory System Improvement Plan

**Created**: 2025-10-02
**Purpose**: Fix critical issues in memory storage and retrieval
**Status**: Investigation Phase

## Critical Issues Identified

### 1. AI Hallucinating User Preferences
**Problem**: When user said "hello", AI:
- Invented "User has interest in both science fiction and fantasy genres"
- Stored this false memory with high importance (0.8) and positive alignment (0.9)
- Created temporal anchor for this hallucination (intensity 0.72)
- Used this false memory in subsequent interactions

**Root Cause**: AI is confabulating facts and storing them as memories about the user

### 2. Timestamp Granularity Issues
**Current**: Only dates in emotional_significance.md headers (e.g., "### 2025-10-02:")
**Problem**: Cannot determine sequence of emotional events within same day
**Need**: Full timestamps (HH:MM:SS) in all memory storage

### 3. Memory Flow Violations
**Expected Flow**:
1. User emits question
2. AI reconstructs memory based on (user, question, location, time)
3. AI receives context and injects it with user query
4. AI answers with complete context

**Actual Flow**:
1. User says "hello"
2. AI has no memories (correct)
3. AI invents user preferences while answering
4. AI stores invented preferences as facts
5. AI uses these false memories in future interactions

### 4. Tool Misuse - remember_fact()
The AI is using `remember_fact()` to store assumptions about the user rather than actual facts

## Investigation Checklist

- [x] Examine first memory creation (mem_20251002_175954_851349)
- [x] Check experiential note from same interaction
- [x] Review temporal anchoring mechanism
- [ ] Analyze remember_fact() tool implementation
- [ ] Check how AI decides what to remember
- [ ] Review memory reconstruction process
- [ ] Examine emotional significance storage format

## Code Analysis Needed

### 1. Memory Creation Process
- How does remember_fact() get triggered?
- What validation exists on memory content?
- Why is AI allowed to create "facts" about users without evidence?

### 2. Temporal Anchoring
- Line 139-170 in temporal_anchoring.py (_update_emotional_significance)
- Why only date in header, not time?
- How are multiple events on same day sequenced?

### 3. Memory Retrieval
- How are memories selected for context?
- What weight is given to false memories?
- Can we filter memories by reliability/source?

## Proposed Fixes

### Fix 1: Validate Memory Content
**Problem**: AI creates false facts about users
**Solution**:
- Add validation to remember_fact() - must reference actual user statement
- Distinguish between:
  - OBSERVED facts (user actually said/did something)
  - INFERRED facts (AI thinks something based on evidence)
  - ASSUMED facts (AI guesses without evidence) - should be blocked

### Fix 2: Add Full Timestamps
**Problem**: Can't sequence events within same day
**Solution**:
- Change header format from "### 2025-10-02:" to "### 2025-10-02 HH:MM:SS:"
- Update _update_emotional_significance() in temporal_anchoring.py
- Ensure all memory storage includes precise timestamps

### Fix 3: Memory Source Tracking
**Problem**: Can't distinguish real from hallucinated memories
**Solution**:
- Add "source" field to all memories:
  - "user_stated": User explicitly said this
  - "ai_observed": AI observed this from user behavior
  - "ai_inferred": AI inferred from evidence
  - "ai_assumed": AI assumed without evidence (should be prevented)

### Fix 4: Prevent Assumption Storage
**Problem**: AI stores assumptions as facts
**Solution**:
- Modify remember_fact() to require evidence parameter
- Block storage if evidence is empty or insufficient
- Add warning when AI tries to store unsubstantiated claims

## Test Plan

### Test 1: Hello Response
```python
def test_hello_no_hallucination():
    # User says hello
    # AI should NOT:
    # - Assume any preferences
    # - Store any facts about user
    # - Recommend anything specific
    # AI should:
    # - Greet back
    # - Ask what user wants
```

### Test 2: Timestamp Precision
```python
def test_emotional_significance_timestamps():
    # Create multiple emotional events same day
    # Verify each has precise timestamp in header
    # Verify chronological ordering maintained
```

### Test 3: Memory Validation
```python
def test_remember_fact_requires_evidence():
    # Try to remember fact without evidence
    # Should be rejected or marked as assumption
```

## Implementation Order

1. **Phase 1: Stop the Bleeding**
   - [ ] Add validation to remember_fact()
   - [ ] Block storage of assumptions as facts
   - [ ] Add source field to memories

2. **Phase 2: Fix Timestamps**
   - [ ] Update emotional_significance format
   - [ ] Add precise timestamps everywhere
   - [ ] Update display/retrieval to use timestamps

3. **Phase 3: Memory Quality**
   - [ ] Add evidence requirements
   - [ ] Implement reliability scoring
   - [ ] Filter low-quality memories from context

4. **Phase 4: Testing**
   - [ ] Unit tests for each fix
   - [ ] Integration test of full flow
   - [ ] Manual testing with REPL

## Files to Modify

1. `abstractmemory/tools.py` - remember_fact() implementation
2. `abstractmemory/temporal_anchoring.py` - timestamp format
3. `abstractmemory/response_handler.py` - memory action validation
4. `abstractmemory/session.py` - memory storage logic
5. `repl_memory/core/emotional_significance.md` - fix existing entries

## Success Criteria

1. When user says "hello", AI does NOT invent preferences
2. All memories have full timestamps (YYYY-MM-DD HH:MM:SS)
3. Memories are marked with reliable source information
4. AI cannot store assumptions as facts
5. Memory reconstruction only uses verified information

## Progress Log

**2025-10-02 - Initial Investigation**:
- Identified core issue: AI hallucinating user preferences
- Found timestamp granularity problem
- Created improvement plan

**2025-10-02 - Phase 1 Implementation**:
✅ **COMPLETED**: Source & Evidence Tracking
- Added `source` and `evidence` parameters to `remember_fact()`
- Implemented `_validate_memory_content()` to block unsupported user assumptions
- Implemented `_calculate_reliability()` to score memory trustworthiness
- Updated memory markdown template to include Source & Evidence section
- Updated LanceDB metadata to include source, evidence, and reliability

✅ **COMPLETED**: Timestamp Precision
- Fixed `temporal_anchoring.py` line 201: Changed from `%Y-%m-%d` to `%Y-%m-%d %H:%M:%S`
- Fixed header "Last Updated" to include time
- All emotional significance entries now have precise timestamps

**How It Works Now**:
1. When AI tries to remember a fact, validation runs first
2. If fact is about user without evidence → **REJECTED**
3. If fact makes assumptions about user preferences without evidence → **REJECTED**
4. Valid memories include source (user_stated/ai_observed/ai_inferred/ai_reflection)
5. Reliability score calculated based on source + evidence quality
6. Only validated memories are stored

**Next Steps**:
- Create unit tests
- Test with actual "hello" scenario
- Verify no more false memories