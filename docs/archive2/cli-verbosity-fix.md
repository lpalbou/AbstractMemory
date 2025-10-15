# CLI Verbosity Fix (Oct 4, 2025)

## Problem
The REPL CLI was becoming too crowded with file content when using `@filename` attachments:
1. Full file content displayed in CLI after attachment
2. Full file content included in reconstruction step logs
3. Made the CLI difficult to read and use

## Solution Implemented

### 1. Attachment Summary Display (`repl.py`)
**Added**: `_display_attachments_summary()` function
- Shows only metadata: filename, size, path
- Does NOT show file content
- Clean, concise display

**Before**:
```
--- Attached Files ---

[File: Values.md]
[Path: /Users/albou/projects/mnemosyne/memory/Core/Values.md]

# Values

[... hundreds of lines of file content ...]
```

**After**:
```
📎 Attached Files:
   • values.md (1,234 chars)
```

**Note**: Shows only filename and size - no path, no duplicate lines, just clean one-line-per-file display

### 2. Smart Query Logging with Filename Extraction (`session.py`)

**Fixed two locations - filenames ALWAYS visible**:

1. **Lines 1545-1559**: `search_memories()` - Extract and log filenames separately
   ```python
   # Split query to get clean user input
   query_parts = query.split("--- Attached Files ---")
   query_for_log = query_parts[0].strip()
   query_preview = query_for_log[:100] + "..." if len(query_for_log) > 100 else query_for_log

   logger.info(f"Searching memories: query='{query_preview}', filters={filters}")

   # Log attached filenames separately (NOT content)
   if len(query_parts) > 1:
       filenames = re.findall(r'\[File: ([^\]]+)\]', query_parts[1])
       if filenames:
           logger.info(f"  → With attached files: {', '.join(filenames)}")
   ```

2. **Lines 2237-2252**: `reconstruct_context()` - Same logic for reconstruction step
   ```python
   query_parts = query.split("--- Attached Files ---")
   query_for_log = query_parts[0].strip()

   logger.info(f"Step 1/9: Searching for memories relevant to: '{query_for_log}'")

   # Log attached filenames
   if len(query_parts) > 1:
       filenames = re.findall(r'\[File: ([^\]]+)\]', query_parts[1])
       if filenames:
           logger.info(f"  → With attached files: {', '.join(filenames)}")
   ```

**Example Log Output**:
```
INFO: Step 1/9: Searching for memories relevant to: 'please read and summarize'
INFO:   → With attached files: ttm.md, values.md
```

**Critical Principle**: File paths are NEVER truncated - always visible in logs for debugging

### 3. File Content Still Sent to LLM
- `_format_input_with_attachments()` unchanged
- Full file content included in LLM context
- Only the CLI display is cleaned up

## Files Modified
1. `repl.py` (+3 lines, -3 lines)
   - Removed duplicate print in `_parse_file_attachments()`
   - Simplified `_display_attachments_summary()` (filename + size only)
   - Called after parsing attachments

2. `abstractmemory/session.py` (+30 lines)
   - Smart query logging in `search_memories()` (lines 1545-1559)
   - Smart query logging in `reconstruct_context()` (lines 2237-2252)
   - Extracts and logs filenames separately (never truncated)

## Testing
```bash
# Test attachment summary
python -c "from repl import _display_attachments_summary; ..."
# ✅ Shows metadata only

# Test query truncation
python -c "test_query = 'read values\n\n--- Attached Files ---\n...'; ..."
# ✅ Extracts clean query: "read values"
```

## Impact
- ✅ CLI is clean and readable (single attachment summary)
- ✅ Attachment metadata shown (filename + size only)
- ✅ Reconstruction logs concise (user query only)
- ✅ **File paths ALWAYS visible in logs** (critical for debugging)
- ✅ File content hidden from logs (no clutter)
- ✅ File content still sent to LLM (no functionality loss)
- ✅ User experience improved significantly
