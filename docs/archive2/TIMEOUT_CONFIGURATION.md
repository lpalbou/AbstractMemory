# Timeout Configuration for AbstractMemory

## Overview
This document summarizes the timeout configuration changes made to ensure critical memory operations can complete without time limits.

## Changes Made

### 1. Task Queue Timeouts (`abstractmemory/task_queue.py`)

**Critical Operations - Infinite Timeout:**
- `fact_extraction`: No timeout (was 300 seconds)
- `consolidation`: No timeout (was 300 seconds) 
- `judge_assessment`: No timeout (was 300 seconds)
- `summarization`: No timeout (was 300 seconds)

**Other Operations:**
- General tasks: 300 seconds (5 minutes) - unchanged
- Embedding generation: No timeout (was 120 seconds)

### 2. Implementation Details

```python
# Task execution timeout logic
if task.name in ['fact_extraction', 'consolidation', 'judge_assessment', 'summarization']:
    # No timeout for critical memory operations - let them complete
    success = future.result(timeout=None)
    logger.info(f"Task {task.task_id} ({task.name}) running with infinite timeout")
else:
    # 5 minutes timeout for other tasks
    success = future.result(timeout=300)
```

```python
# Embedding generation timeout
embedding = future.result(timeout=None)  # No timeout
```

### 3. File Operations (Unchanged)
- File write operations: 5 seconds timeout (appropriate for I/O)
- Thread cleanup: 5 seconds timeout (appropriate for cleanup)

## Task Restart Instructions

### To Restart Failed Task:
1. Launch CLI: `python -m memory_cli --provider lmstudio --model qwen/qwen3-next-80b`
2. Check queue: `/queue`
3. Restart specific task: `/queue 16038c7e retry`

### Queue Management Commands:
- `/queue` - Show all tasks
- `/queue <task_id>` - Show task details  
- `/queue <task_id> retry` - Retry failed task
- `/queue <task_id> remove` - Remove task

## Benefits

1. **No More Timeouts**: Critical memory operations (fact extraction, consolidation, judge assessment, summarization) will never timeout
2. **Reliability**: Complex reasoning tasks can take as long as needed
3. **Flexibility**: Non-critical tasks still have reasonable timeouts
4. **Restart Capability**: Failed tasks can be easily restarted via CLI

## Monitoring

- Tasks with infinite timeout will log: "Task {id} ({name}) running with infinite timeout"
- Use `/queue` command to monitor long-running tasks
- Failed tasks can be retried without losing progress

## Notes

- Embedding generation also has infinite timeout since it's critical for semantic search
- File I/O operations keep short timeouts for responsiveness
- Thread cleanup operations keep short timeouts for proper resource management
