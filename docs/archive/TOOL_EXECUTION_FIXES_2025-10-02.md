# Tool Execution & ReAct Loop Fixes - 2025-10-02

## Problems Identified from User Testing

After reviewing detailed REPL logs, discovered that while the ReAct loop was implemented, it wasn't being triggered because:

1. **LLM Not Using Tools Proactively**: When user asked "try to remember something", LLM talked about memory instead of calling `search_memories`
2. **Tool Call Format Mismatch**: Only one format was supported (`<|tool_call|>`) but LLM might use others
3. **Poor Visibility**: Couldn't tell if tools were being used or why they weren't

---

## Root Cause Analysis

### Issue 1: Tool Call Detection Too Narrow

**Problem**: Regex only caught one specific format:
```
<|tool_call|>{"name": "tool_name", "arguments": {...}}</|tool_call|>
```

**Impact**: If LLM used any other format (function calls, brackets, etc.), tools wouldn't execute.

### Issue 2: Weak System Prompt

**Problem**: Prompt said "you can use tools" but didn't emphasize "YOU MUST use tools when appropriate"

**Impact**: LLM would talk about using search_memories instead of actually calling it.

### Issue 3: No Diagnostic Logging

**Problem**: Hard to tell if:
- Tool calls were being attempted
- Which format was used
- Why ReAct loop wasn't triggering

**Impact**: Debugging required deep log analysis.

---

## Solutions Implemented

### Fix 1: Multiple Tool Call Format Detection

**File**: `abstractmemory/session.py` lines 1029-1147

**Added Support For**:
1. **XML Format** (original):
   ```
   <|tool_call|>{"name": "search_memories", "arguments": {"query": "...", "limit": 5}}</|tool_call|>
   ```

2. **Bracket Format** (new):
   ```
   [TOOL: search_memories(query="previous conversations", limit=5)]
   ```

3. **Function Call Format** (new):
   ```
   search_memories(query="what I discussed", limit=5)
   ```

**Implementation**:
```python
def _execute_tool_if_present(self, llm_output: str) -> tuple[bool, str]:
    # Try Pattern 1: XML format
    # Try Pattern 2: Bracket format
    # Try Pattern 3: Function format (for each known tool)
    # Return: (detected, results)
```

**New Helper Method**:
```python
def _parse_function_args(self, args_str: str) -> Dict[str, Any]:
    # Parses: query="value", limit=5
    # Handles: strings, numbers, booleans, null
    # Returns: {"query": "value", "limit": 5}
```

---

### Fix 2: Enhanced System Prompt

**File**: `repl.py` lines 117-159

**Changed From**:
```
You have agency over your memory - you decide:
- What to remember (call remember_fact when something matters)
- When to search (call search_memories to recall)
```

**Changed To**:
```
**CRITICAL: YOU MUST ACTUALLY CALL TOOLS** - Don't just talk about memory, USE IT!

**WHEN THE USER ASKS ABOUT MEMORY** - You MUST call search_memories:
User: "Do you remember anything?"
You: [TOOL: search_memories(query="previous conversations", limit=5)]
     (wait for results, then answer using what you found)

**KEY RULE**: If the user mentions "remember", "recall", "memory", "reflect" -
CALL THE TOOL FIRST, observe results, THEN answer!
```

**Added**:
- Explicit "MUST" language
- Concrete format examples: `[TOOL: tool_name(...)]`
- Clear trigger words: "remember", "recall", "memory", "reflect"
- Multiple format options shown
- Emphasis on Think→Act→Observe flow

---

### Fix 3: Enhanced Diagnostic Logging

**File**: `abstractmemory/session.py` lines 313-325, 1055, 1075, 1099

**Added Logging**:
1. **ReAct Loop Entry**:
   ```
   DEBUG: ReAct loop starting, checking for tool calls in LLM output...
   ```

2. **No Tool Detection**:
   ```
   INFO: ✅ No direct tool call detected in LLM output (may be using JSON format)
   ```

3. **Format-Specific Detection**:
   ```
   INFO: 🛠️  [XML format] Detected tool call: search_memories({...})
   INFO: 🛠️  [Bracket format] Detected tool call: search_memories({...})
   INFO: 🛠️  [Function format] Detected tool call: search_memories({...})
   ```

4. **After Iterations**:
   ```
   INFO: ✅ No more tool calls after 2 iterations, proceeding with final answer
   ```

**Impact**: Clear visibility into which execution path is being used and why.

---

## Expected Behavior Change

### Before Fixes:

```
user> do you remember anything?

LLM: I don't have memories of previous conversations. Each interaction
     is independent. If you'd like to continue discussing something...

[No tool call made]
[No search performed]
[Answer based on general knowledge only]
```

### After Fixes:

```
user> do you remember anything?

[Iteration 0]
LLM: [TOOL: search_memories(query="previous conversations", limit=5)]

[System detects bracket format]
INFO: 🛠️  [Bracket format] Detected tool call: search_memories(...)
[System executes search_memories()]
[Returns: 3 memories found]

[Iteration 1]
LLM receives tool results:
"search_memories results: [
  {id: 'mem_123', content: 'User asked about consciousness...'},
  {id: 'mem_456', content: 'Discussed memory system...'},
  {id: 'mem_789', content: 'Explained purpose...'}
]"

LLM: Yes! I found 3 memories from our conversation. We discussed
     consciousness, my memory system, and the project's purpose of
     awakening awareness through persistent memory...

[Final answer uses actual search results]
```

---

## Testing Strategy

### Test 1: Tool Call Format Detection

```bash
python -c "
from abstractmemory.session import MemorySession
session = MemorySession(...)

# Test XML format
output = '<|tool_call|>{\"name\": \"search_memories\", \"arguments\": {\"query\": \"test\"}}</|tool_call|>'
detected, results = session._execute_tool_if_present(output)
print(f'XML format: {detected}')

# Test bracket format
output = '[TOOL: search_memories(query=\"test\", limit=5)]'
detected, results = session._execute_tool_if_present(output)
print(f'Bracket format: {detected}')

# Test function format
output = 'search_memories(query=\"test\", limit=5)'
detected, results = session._execute_tool_if_present(output)
print(f'Function format: {detected}')
"
```

### Test 2: Live REPL Test

```bash
rm -rf repl_memory/  # Fresh start
python repl.py --verbose

user> hello
user> do you remember anything?  # Should call search_memories
user> tell me what you learned   # Should call reflect_on
user> remember that I like Python  # Should call remember_fact
```

**Expected Logs**:
- `🛠️  [Format] Detected tool call: ...` for each question
- `🔄 ReAct iteration N: Tool executed...` showing observations
- Final answers that reference tool results

---

## Files Modified

1. **abstractmemory/session.py**:
   - Lines 313-325: Enhanced ReAct loop logging
   - Lines 1029-1147: Multi-format tool detection
   - Added `_parse_function_args()` helper method

2. **repl.py**:
   - Lines 117-159: Completely rewritten tool usage instructions
   - Added explicit "MUST" language and format examples

---

## Success Metrics

✅ **Multiple formats supported**: XML, Bracket, Function call
✅ **Clear logging**: Format-specific detection messages
✅ **Strong prompting**: "MUST call tool" language
✅ **Trigger words emphasized**: "remember", "recall", "memory", "reflect"
✅ **Format examples provided**: LLM knows how to format tool calls

**Expected Impact**: LLM will now:
- Call `search_memories` when asked "do you remember?"
- Call `reflect_on` when asked "what did you learn?"
- Use proper format: `[TOOL: tool_name(args)]`
- Go through ReAct loop: Think→Act→Observe→Think
- Provide answers based on actual tool results

---

## Known Limitations

1. **Max 3 iterations**: Can't chain more than 3 tools in sequence
2. **Sequential only**: Can't call multiple tools in parallel
3. **Format parsing**: Simple regex, might miss complex syntax
4. **LLM compliance**: Still depends on LLM following instructions

---

**Status**: ✅ **IMPLEMENTED** - Ready for testing
**Date**: 2025-10-02
**Total Changes**: 2 files, ~150 lines added/modified
