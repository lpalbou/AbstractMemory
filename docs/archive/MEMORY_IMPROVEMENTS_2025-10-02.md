# Memory System Improvements - 2025-10-02

## Problem Summary

The AI was hallucinating facts about users and storing them as memories. When a user simply said "hello", the AI:
1. Invented: "User has interest in both science fiction and fantasy genres"
2. Stored this false memory with high importance (0.8) and positive alignment (0.9)
3. Created a temporal anchor for this hallucination
4. Used this false memory in subsequent interactions

Additionally, timestamps in emotional significance tracking only showed dates, not times, making it impossible to sequence events within a day.

## Root Causes

1. **No Memory Validation**: `remember_fact()` accepted any content without checking if it was supported by evidence
2. **No Source Tracking**: No way to distinguish observed facts from assumptions
3. **Timestamp Granularity**: Only `%Y-%m-%d` instead of `%Y-%m-%d %H:%M:%S`
4. **LLM Confabulation**: AI making claims about users without any actual user statements

## Solutions Implemented

### Fix 1: Memory Validation with Source & Evidence Tracking

**Files Modified**:
- `abstractmemory/session.py`

**Changes**:
1. Added new parameters to `remember_fact()`:
   - `source`: "user_stated" | "ai_observed" | "ai_inferred" | "ai_reflection"
   - `evidence`: What supports this memory (required for user facts)

2. Implemented `_validate_memory_content()` method:
   ```python
   def _validate_memory_content(content, source, evidence):
       # Blocks user-related claims without evidence
       # Blocks assumptions about user preferences
       # Returns (is_valid, error_message)
   ```

3. Implemented `_calculate_reliability()` method:
   ```python
   # Scores based on source:
   # user_stated: 0.95 (most reliable)
   # ai_observed: 0.80
   # ai_inferred: 0.60
   # ai_reflection: 0.70
   ```

4. Updated memory markdown template to include:
   ```markdown
   ## Source & Evidence
   **Source**: {source}
   **Evidence**: {evidence}
   ```

5. Updated LanceDB metadata to include:
   - `source` field
   - `evidence` field
   - `reliability` score

**Behavior**:
- ❌ "User has interest in sci-fi" without evidence → **REJECTED**
- ✅ "User enjoys sci-fi" with evidence "User said: I love sci-fi" → **ACCEPTED**
- ✅ "I notice I default to recommendations" (AI reflection) → **ACCEPTED**

### Fix 2: Timestamp Precision

**Files Modified**:
- `abstractmemory/temporal_anchoring.py`

**Changes**:
1. Line 201: Changed header format from `%Y-%m-%d` to `%Y-%m-%d %H:%M:%S`
2. Line 182: Changed "Last Updated" to include time

**Before**:
```markdown
### 2025-10-02: User has interest in both science fiction
```

**After**:
```markdown
### 2025-10-02 17:59:54: User has interest in both science fiction
```

Now multiple events on the same day can be properly sequenced.

## Testing

### Unit Tests Created

**File**: `tests/test_memory_validation.py`

7 tests covering:
1. ✅ Blocks user assumptions without evidence
2. ✅ Requires evidence for user claims
3. ✅ Accepts user statements with evidence
4. ✅ Allows AI self-reflections
5. ✅ Calculates reliability scores correctly
6. ✅ "Hello" scenario - no false memories created
7. ✅ Memory files include source & evidence

**Run tests**:
```bash
pytest tests/test_memory_validation.py -v -s
```

### Integration Test - "Hello" Scenario

The exact scenario from the bug report:
```python
user> hello
# AI should NOT create any facts about user preferences
# AI should NOT assume user interests
# AI should greet and ask what user wants
```

With the fix:
- Attempts to store "User has interest in sci-fi" → **REJECTED**
- Validation warning logged
- No false memory created
- No temporal anchor created

## Backward Compatibility

### Breaking Changes

**`remember_fact()` signature changed**:
- Added optional `source` parameter (default: "ai_observed")
- Added optional `evidence` parameter (default: "")
- Returns `Optional[str]` instead of `str` (can return None if rejected)

**Mitigation**:
- New parameters are optional with sensible defaults
- Existing code will work but may have memories rejected if they make user claims without evidence
- Return value should be checked for None

### Migration Path

If you have code calling `remember_fact()` that may be affected:

**Before**:
```python
memory_id = session.remember_fact(
    content="User likes Python",
    importance=0.8
)
```

**After** (provide evidence):
```python
memory_id = session.remember_fact(
    content="User likes Python",
    importance=0.8,
    source="user_stated",
    evidence="User said: 'I prefer Python for scripting'"
)
if memory_id is None:
    print("Memory rejected - need evidence for user claims")
```

## Verification Steps

1. **Clear existing memory** (contains false data):
   ```bash
   rm -rf repl_memory/
   ```

2. **Run tests**:
   ```bash
   pytest tests/test_memory_validation.py -v
   ```

3. **Test in REPL**:
   ```bash
   python -m repl
   user> hello
   # Verify: No assumptions about preferences
   # Verify: No false memories created
   ```

4. **Check logs for rejections**:
   ```bash
   python -m repl --verbose
   # Look for "Memory rejected:" warnings
   ```

## Success Metrics

✅ **User says "hello"** → AI does NOT invent preferences
✅ **All memories have full timestamps** (YYYY-MM-DD HH:MM:SS)
✅ **User facts require evidence** from actual user statements
✅ **Clear source tracking** on all memories
✅ **Reliability scoring** based on source quality
✅ **7/7 unit tests passing**

## Files Modified

1. `abstractmemory/session.py` (~100 lines changed)
   - Added `_validate_memory_content()` method
   - Added `_calculate_reliability()` method
   - Updated `remember_fact()` signature and implementation
   - Updated memory markdown template
   - Updated LanceDB metadata storage

2. `abstractmemory/temporal_anchoring.py` (2 lines changed)
   - Line 182: Header timestamp format
   - Line 201: Entry timestamp format

3. `docs/improve-memory.md` (created)
   - Complete investigation and improvement plan

4. `tests/test_memory_validation.py` (created)
   - 7 comprehensive tests

5. `MEMORY_IMPROVEMENTS_2025-10-02.md` (this file)
   - Implementation documentation

## Known Limitations

1. **Evidence is not validated**: System checks IF evidence exists, not if it's truthful
2. **Keyword-based detection**: Uses simple keyword matching to detect user claims
3. **No retroactive validation**: Existing false memories remain until cleared
4. **AI can still try**: AI will attempt to create false memories, they're just rejected

## Future Improvements

1. Add LLM-based evidence validation
2. Implement memory correction/deletion tool
3. Add confidence decay for old memories
4. Track rejection patterns to improve prompting
5. Add user feedback loop to confirm AI observations

## Credits

**Issue Reported By**: User (2025-10-02)
**Root Cause Analysis**: Investigation of "hello" scenario
**Implemented By**: Phase 1 & 2 memory improvements
**Documentation**: Complete improvement tracking in docs/improve-memory.md
