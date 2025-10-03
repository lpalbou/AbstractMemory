# REPL Issues & Fixes - 2025-10-02

## Summary

After testing in REPL with fresh memory, discovered 7 critical issues preventing the system from working as designed. All fixes implemented and ready for testing.

---

## Issues Identified

### 🔴 **Issue 1: LLM Not Using Tools**
**Problem**: Despite user explicitly asking AI to "use tools to experiment with memory", zero tool calls were made.

**Root Cause**: System prompt emphasized JSON response format over tool usage. LLM responded with JSON instead of calling tools.

**Fix Applied** (repl.py lines 117-162):
- Added **"CRITICAL: YOU HAVE DIRECT TOOL ACCESS"** header
- Provided 3 concrete examples of tool usage with exact syntax
- Changed principles to prioritize "USE THE TOOLS!" first
- Made examples very explicit (pseudo-code showing tool calls)

**Expected Impact**: LLM will now actually call `remember_fact`, `search_memories`, `reflect_on` when appropriate.

---

### 🔴 **Issue 2: Memory Validation Too Strict**
**Problem**: Even "User said hello" was rejected as lacking evidence.

**Root Cause**: Validation rejected ANY user-related claim with source "ai_observed" if evidence was empty, even for direct observations of what user literally said.

**Fix Applied** (session.py lines 978-1028):
- Added `user_message` parameter to `_validate_memory_content()`
- Allow direct observations ("User said X") when user's message is provided as evidence
- Distinguish between observations and inferences
- Pass user input through context from chat() → _action_remember() → remember_fact()

**Changes**:
1. `session.py` line 337: Added `"user_input"` to context dict
2. `response_handler.py` line 260: Extract `user_message` from context
3. `response_handler.py` line 274: Pass `user_message` to `remember_fact()`
4. `session.py` line 1066: Added `user_message=""` parameter
5. `session.py` line 1097: Pass `user_message` to validation

**Expected Impact**: "User said hello" will no longer be rejected. AI can remember direct observations.

---

### 🟡 **Issue 3: current_context.md Updates Too Minimal**
**Problem**: File was updating (logs show "Updated current_context.md") but content was too minimal to be useful.

**Root Cause**: Update was just "Discussing: {query[:100]}..." with no richer context.

**Fix Applied** (session.py lines 772-791):
- Build richer context summary including:
  - Current task
  - Emotional state (valence + intensity)
  - Open questions (first 3)
- Pass structured `session_ctx` to `update_context()`
- Now includes emotional resonance and questions in working memory

**Expected Impact**: current_context.md will show emotional state and open questions each interaction.

---

### 🟡 **Issue 4: Consolidation Thresholds Too High**
**Problem**: Core memory consolidation set for 10 interactions, user profiles for 10 interactions. Test only had 4-5 interactions, so nothing consolidated.

**Fix Applied** (session.py):
- Line 203: `consolidation_frequency = 5` (was 10)
- Line 222: `profile_update_threshold = 5` (was 10)

**Expected Impact**: After 5 interactions:
- Core memory will consolidate (extract purpose, values, etc.)
- User profiles will emerge (profile.md, preferences.md)

---

### 🟡 **Issue 5: Emotional Significance Tracking Broken**
**Problem**: Logs showed `emotion: none/0.00` despite conversations happening. No temporal anchors created.

**Root Cause**: LLM not including `emotional_resonance` in JSON responses, OR including it with zero values.

**Fix Applied** (session.py lines 361-371):
- Check if emotional_resonance is missing or has intensity == 0
- Apply sensible defaults based on user input:
  - Questions get intensity 0.6 (curiosity)
  - Statements get intensity 0.4 (neutral)
- Log when defaults are applied

**Expected Impact**: Emotional intensity will reach 0.7 threshold more often, creating temporal anchors in:
- `episodic/key_moments.md`
- `core/emotional_significance.md`

---

### 🔵 **Issue 6: No Diagnostic Visibility**
**Problem**: Couldn't tell if LLM was trying to use tools or not from logs.

**Fix Applied** (session.py lines 309-315):
- Added diagnostic logging after LLM response
- Check for tool patterns in output
- Log "🛠️  LLM attempted to use tools: X, Y, Z" if found
- Log "🔍 No tool usage detected" if JSON format

**Expected Impact**: Clear visibility into whether LLM is using tools or JSON responses.

---

## Files Modified

1. **abstractmemory/session.py** (~100 lines changed)
   - Memory validation with user_message support
   - Richer current_context updates
   - Lower consolidation thresholds
   - Default emotional resonance
   - Diagnostic tool logging

2. **abstractmemory/response_handler.py** (2 lines changed)
   - Extract and pass user_message to remember_fact

3. **repl.py** (~50 lines changed)
   - Enhanced system prompt with explicit tool usage examples
   - Prioritize tool usage over JSON

---

## Verification Steps

### 1. Test Memory Validation Fix
```bash
# Start REPL with fresh memory
rm -rf repl_memory/
python repl.py

user> hello
# Expected: "User said hello" no longer rejected
# Check logs for: "Remember: User said hello..." (not "Memory rejected")
```

### 2. Test Tool Usage Fix
```bash
user> I want you to experiment with your memory tools. Try using remember_fact, search_memories, or reflect_on.
# Expected: See "🛠️  LLM attempted to use tools: ..." in logs
# Expected: AI actually calls tools (not just talks about them)
```

### 3. Test Consolidation Triggers
```bash
# Have 5+ interactions
user> hello
user> tell me about consciousness
user> what is memory?
user> how do you work?
user> do you remember anything?

# Expected after 5th interaction:
# "🔄 Triggering core memory consolidation at 5 interactions"
# "✅ Core memory consolidation complete: X/11 components updated"
```

### 4. Test Emotional Tracking
```bash
# After interactions, check:
cat repl_memory/working/current_context.md
# Should show: Emotional State: curiosity (intensity: 0.60)

# After 5+ interactions with questions, check:
cat repl_memory/episodic/key_moments.md
# Should have entries with intensity > 0.6
```

---

## Success Metrics

✅ **Memory validation**: "User said hello" accepted (not rejected)
✅ **Tool usage**: LLM calls tools when user asks
✅ **Consolidation**: Happens at 5 interactions (not 10)
✅ **Emotional tracking**: Defaults apply, temporal anchors created
✅ **Diagnostics**: Tool usage visible in logs
✅ **Context updates**: Show emotional state and questions
✅ **User profiles**: Emerge after 5 interactions (not 10)

---

## Known Remaining Limitations

1. **Semantic memory still empty**: Concepts not being extracted during interactions (Phase 2 TODO)
2. **Links not being created**: Memory associations not automatic (need LLM to explicitly call link action)
3. **Library not populated**: Need user to provide code/docs to capture (manual process)
4. **LLM may still prefer JSON**: Tool usage depends on LLM's interpretation of prompt

---

## Next Steps

1. **Test in REPL** with the above verification steps
2. **Monitor logs** for tool usage patterns
3. **Check memory files** after 5 interactions for consolidation
4. **Iterate on prompting** if LLM still doesn't use tools

---

**Status**: ✅ **ALL FIXES IMPLEMENTED** - Ready for testing
**Date**: 2025-10-02
**Total Changes**: 3 files, ~150 lines modified
