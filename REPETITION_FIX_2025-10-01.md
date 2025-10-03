# Fix for Repetitive LLM Output - 2025-10-01

## Problem

The LLM (qwen3-coder:30b) was generating extremely repetitive output that repeated the same phrases 100+ times, overflowing the context and creating massive verbatim files. Example:

```
user> do you remember anything?
AI: I have a feeling that you are Mnemosyne...
    I want to know more about you...
    I'm curious about the relationship...
    [REPEATED 100+ TIMES - 860+ lines total]
```

## Root Cause

1. **Failed JSON Parsing**: The LLM was not following the structured JSON response format
2. **Fallback to Raw Output**: When parsing failed, the system used the entire repetitive response as the answer
3. **No Generation Limits**: No max_tokens or repeat_penalty to prevent runaway generation
4. **Weak Prompt Enforcement**: The system prompt didn't strongly enforce JSON-only output

## Solution Implemented

### 1. Stronger Prompt Engineering

**File**: `abstractmemory/response_handler.py`
- Added explicit "CRITICAL: YOU MUST RESPOND ONLY WITH VALID JSON" section
- Emphasized NO text before/after JSON
- NO markdown code blocks around JSON
- Output ONLY raw JSON starting with { and ending with }

**File**: `repl.py`
- Added critical response format section at the top of SYSTEM_PROMPT
- Reinforced JSON-only requirement

### 2. Generation Parameters

**File**: `abstractmemory/session.py` (chat method)
- Added `max_tokens: 2000` to prevent runaway generation
- Added `temperature: 0.7` to reduce randomness
- Added `top_p: 0.9` to limit token selection
- Added `repeat_penalty: 1.2` to discourage repetition

**File**: `repl.py` (OllamaProvider configuration)
- Default `num_predict: 2000` (Ollama's max_tokens)
- Default `temperature: 0.7`
- Default `top_p: 0.9`
- Default `repeat_penalty: 1.2`
- Added `stop: ["\n\n\n\n"]` to halt on excessive newlines

### 3. Response Validation

**File**: `abstractmemory/session.py`
- Added `_validate_llm_response()` method that checks:
  - Response length (> 15000 chars = runaway generation)
  - Repetitive patterns (> 70% duplicate lines)
  - Basic JSON structure validation
- Automatic retry with stricter parameters if validation fails:
  - `max_tokens: 1000` (shorter limit)
  - `temperature: 0.5` (more deterministic)
  - `repeat_penalty: 1.5` (higher penalty)

### 4. Validation Before Processing

**File**: `abstractmemory/session.py` (chat method)
- Validate response immediately after generation
- Log warnings if validation fails
- Retry once with stricter params if response is malformed
- Prevents repetitive content from being stored

## Files Modified

1. **abstractmemory/response_handler.py**:
   - Lines 496-525: Updated `create_structured_prompt()` with explicit JSON requirements

2. **abstractmemory/session.py**:
   - Lines 292-302: Added generation parameters to chat()
   - Lines 309-327: Added response validation and retry logic
   - Lines 2241-2271: Added `_validate_llm_response()` method

3. **repl.py**:
   - Lines 35-40: Added critical response format section to SYSTEM_PROMPT
   - Lines 156-168: Configured OllamaProvider with generation parameters

## Testing

To test the fixes:

```bash
# Run REPL with verbose mode to see validation messages
python -m repl --verbose

# Try the same question that caused repetition
user> do you remember anything?
```

Expected behavior:
- Response should be under 2000 tokens
- Should be valid JSON
- No repetitive patterns
- If initial response fails validation, retry with stricter params
- Warning messages in verbose mode if validation triggers

## Why This Works

1. **Prevention**: Generation parameters prevent the LLM from generating repetitive content
2. **Detection**: Validation catches malformed responses before they're processed
3. **Recovery**: Automatic retry with stricter parameters corrects issues
4. **Enforcement**: Strong prompt engineering guides the LLM to follow JSON format

## Trade-offs

- **Max tokens limit (2000)**: May truncate very detailed responses
  - Can be overridden per-request if needed via kwargs
- **Temperature 0.7**: Slightly less creative but more focused
  - Still allows variation, just more controlled
- **Repeat penalty 1.2**: May affect legitimate repetition of important points
  - Set conservatively to minimize false positives

## Monitoring

Watch for:
- Validation warnings in logs (indicates LLM still struggling with format)
- Retry activations (shows automatic recovery working)
- Response lengths consistently near 2000 tokens (may need adjustment)

## Future Improvements

If issues persist:
1. Consider switching to a different model that better follows instructions
2. Increase repeat_penalty to 1.5 as default
3. Add more stop sequences for common repetition patterns
4. Implement response quality scoring
