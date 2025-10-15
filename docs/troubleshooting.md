# Troubleshooting AbstractMemory

This guide helps resolve common issues when using AbstractMemory.

## Installation Issues

### AbstractCore Not Found

**Error**: `ImportError: No module named 'abstractllm'`

**Solution**:
```bash
pip install abstractcore[embeddings]
```

**Alternative**: If you need specific providers:
```bash
pip install abstractcore[openai]
pip install abstractcore[anthropic] 
pip install abstractcore[ollama]
```

### LanceDB Installation Problems

**Error**: `ImportError: No module named 'lancedb'`

**Solution**:
```bash
pip install lancedb
```

**On Apple Silicon Macs**:
```bash
# If you encounter compilation issues
pip install --no-binary lancedb lancedb
```

### Permission Errors

**Error**: `PermissionError: [Errno 13] Permission denied`

**Solutions**:
1. Check directory permissions:
   ```bash
   chmod 755 /path/to/memory/directory
   ```

2. Use a different memory path:
   ```python
   session = MemorySession(memory_base_path="./user_memory")
   ```

3. Run with appropriate permissions (avoid sudo if possible)

## Memory System Issues

### Memory Not Persisting

**Symptoms**: Memories don't carry over between sessions

**Diagnosis**:
```python
# Check if memory directory exists and has content
import os
memory_path = "./my_memory"
print(f"Memory directory exists: {os.path.exists(memory_path)}")
print(f"Directory contents: {os.listdir(memory_path) if os.path.exists(memory_path) else 'None'}")
```

**Solutions**:
1. Verify memory path is writable
2. Check if memory path is being cleared between runs
3. Ensure you're using the same memory path consistently

### LanceDB Connection Errors

**Error**: `RuntimeError: LanceDB not installed` or connection failures

**Solutions**:
1. Reinstall LanceDB:
   ```bash
   pip uninstall lancedb
   pip install lancedb
   ```

2. Check disk space:
   ```bash
   df -h /path/to/memory/directory
   ```

3. Verify directory permissions:
   ```python
   import os
   memory_path = "./my_memory/lancedb"
   print(f"Can write to LanceDB directory: {os.access(memory_path, os.W_OK)}")
   ```

### Memory Structure Corruption

**Symptoms**: Missing directories or malformed files

**Solution**: Reinitialize memory structure:
```python
from abstractmemory.memory_structure import initialize_memory_structure
from pathlib import Path

# Reinitialize the memory structure
memory_path = Path("./my_memory")
status = initialize_memory_structure(memory_path, user_id="your_user_id")
print(f"Reinitialization status: {status}")
```

## Performance Issues

### Slow Memory Search

**Symptoms**: `search_memories()` takes a long time

**Diagnosis**:
```python
# Check memory size
stats = session.get_memory_statistics()
print(f"Total memories: {stats.get('total_memories', 0)}")

# Check LanceDB table sizes
if hasattr(session, 'lancedb_storage'):
    tables = session.lancedb_storage.db.table_names()
    print(f"LanceDB tables: {tables}")
```

**Solutions**:
1. Reduce search scope:
   ```python
   # Use filters to narrow search
   results = session.search_memories(
       "query",
       filters={"timestamp": {"gte": "2025-01-01"}},
       limit=5
   )
   ```

2. Disable unnecessary indexing:
   ```json
   // .memory_index_config.json
   {
     "modules": {
       "verbatim": {"enabled": false, "auto_index": false}
     }
   }
   ```

3. Use lower focus levels:
   ```python
   context = session.reconstruct_context(
       user_id="user",
       query="query", 
       focus_level=1  # Reduced from default 3
   )
   ```

### Slow Context Reconstruction

**Symptoms**: Long delays before LLM responses

**Solutions**:
1. Adjust focus level:
   ```python
   # Focus levels: 0=minimal, 1=light, 2=moderate, 3=balanced, 4=deep, 5=maximum
   session.default_focus_level = 1  # If this attribute exists
   ```

2. Check memory indexing status:
   ```python
   if hasattr(session, 'memory_indexer'):
       # Wait for indexing to complete
       import time
       time.sleep(2)
   ```

3. Monitor background tasks:
   ```python
   if hasattr(session, 'task_queue'):
       status = session.task_queue.get_status()
       if status.get('running'):
           print("Background tasks running, performance may be impacted")
   ```

### High Memory Usage

**Symptoms**: System running out of RAM

**Solutions**:
1. Reduce batch size in indexing config:
   ```json
   {
     "batch_size": 50
   }
   ```

2. Clear old memories periodically:
   ```python
   # Manual cleanup (implement based on your needs)
   from datetime import datetime, timedelta
   cutoff_date = datetime.now() - timedelta(days=30)
   # Implement cleanup logic
   ```

3. Use memory-efficient embedding models:
   ```python
   from abstractllm.embeddings import EmbeddingManager
   embedding_manager = EmbeddingManager(model="all-minilm-l6-v2")  # Smaller model
   ```

## LLM Provider Issues

### Ollama Connection Problems

**Error**: Connection refused or model not found

**Solutions**:
1. Check Ollama is running:
   ```bash
   ollama list
   ollama serve
   ```

2. Verify model is available:
   ```bash
   ollama pull qwen3-coder:30b
   ```

3. Test connection:
   ```python
   from abstractllm import create_llm
   try:
       llm = create_llm("ollama", model="qwen3-coder:30b")
       response = llm.generate("test")
       print("Connection successful")
   except Exception as e:
       print(f"Connection failed: {e}")
   ```

### OpenAI API Issues

**Error**: API key or quota problems

**Solutions**:
1. Check API key:
   ```python
   import os
   print(f"API key set: {'OPENAI_API_KEY' in os.environ}")
   ```

2. Test API access:
   ```python
   from abstractllm import create_llm
   llm = create_llm("openai", model="gpt-3.5-turbo")
   # Test with simple query
   ```

3. Check quota and billing in OpenAI dashboard

### Model Context Limits

**Error**: Token limit exceeded

**Solutions**:
1. Reduce context reconstruction scope:
   ```python
   context = session.reconstruct_context(
       user_id="user",
       query="query",
       focus_level=0  # Minimal context
   )
   ```

2. Use models with larger context windows:
   ```python
   # Switch to model with larger context
   llm = create_llm("anthropic", model="claude-3-5-sonnet")
   ```

## Memory Tool Issues

### Tools Not Working

**Symptoms**: Memory tools don't execute or return errors

**Diagnosis**:
```python
# Check if tools are properly registered
print(f"Available tools: {session.tools if hasattr(session, 'tools') else 'None'}")

# Test tool execution
try:
    result = session.remember_fact(
        content="Test fact",
        importance=0.5,
        emotion="testing",
        reason="Diagnostic test"
    )
    print(f"Tool test successful: {result}")
except Exception as e:
    print(f"Tool test failed: {e}")
```

**Solutions**:
1. Verify session initialization:
   ```python
   # Ensure session is properly initialized
   if not hasattr(session, 'memory_base_path'):
       print("Session not properly initialized")
   ```

2. Check memory structure:
   ```python
   from abstractmemory.memory_structure import initialize_memory_structure
   initialize_memory_structure(session.memory_base_path)
   ```

### Structured Response Parsing Errors

**Error**: JSON parsing failures or validation errors

**Solutions**:
1. Check LLM response format:
   ```python
   # Enable debug mode to see raw responses
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. Use fallback parsing:
   ```python
   # The system should automatically fall back, but you can force it
   try:
       response = session.generate("test query")
   except Exception as e:
       print(f"Structured parsing failed, using fallback: {e}")
   ```

3. Simplify system prompt if using custom prompts

## Background Process Issues

### Task Queue Problems

**Symptoms**: Background tasks not completing

**Diagnosis**:
```python
if hasattr(session, 'task_queue'):
    status = session.task_queue.get_status()
    print(f"Queue status: {status}")
    
    # Check for failed tasks
    failed_tasks = [t for t in status.get('completed', []) if t.get('status') == 'failed']
    if failed_tasks:
        print(f"Failed tasks: {len(failed_tasks)}")
        for task in failed_tasks[-3:]:  # Show last 3 failures
            print(f"- {task.get('name')}: {task.get('error')}")
```

**Solutions**:
1. Restart task queue:
   ```python
   if hasattr(session, 'task_queue'):
       session.task_queue.stop_worker()
       session.task_queue.start_worker()
   ```

2. Clear failed tasks:
   ```python
   # Manual cleanup of task queue if needed
   # Implementation depends on your specific needs
   ```

### Consolidation Failures

**Symptoms**: Core memory components not updating

**Solutions**:
1. Manual consolidation:
   ```python
   from abstractmemory.core_memory_extraction import consolidate_core_memory
   results = consolidate_core_memory(session, mode="manual")
   print(f"Consolidation results: {results}")
   ```

2. Check for sufficient memory content:
   ```python
   # Consolidation needs experiential notes to work
   notes_dir = session.memory_base_path / "notes"
   if notes_dir.exists():
       note_files = list(notes_dir.rglob("*.md"))
       print(f"Available note files: {len(note_files)}")
   ```

## Configuration Issues

### Invalid Configuration

**Error**: Configuration file parsing errors

**Solution**: Validate configuration:
```python
import json
from pathlib import Path

config_path = Path("./my_memory/.memory_index_config.json")
if config_path.exists():
    try:
        with open(config_path) as f:
            config = json.load(f)
        print("Configuration is valid JSON")
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in config: {e}")
        # Recreate default config
        default_config = {
            "modules": {
                "notes": {"enabled": True, "auto_index": True},
                "verbatim": {"enabled": False, "auto_index": False},
                "library": {"enabled": True, "auto_index": True}
            }
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
```

## Debugging Tips

### Enable Debug Logging

```python
import logging
from abstractllm.utils.structured_logging import configure_logging

# Enable comprehensive logging
configure_logging(
    console_level=logging.DEBUG,
    file_level=logging.DEBUG,
    log_dir="./debug_logs",
    verbatim_enabled=True,
    console_json=False
)
```

### Memory Inspection

```python
# Inspect memory structure
def inspect_memory(session):
    memory_path = session.memory_base_path
    
    print(f"Memory base path: {memory_path}")
    print(f"Path exists: {memory_path.exists()}")
    
    if memory_path.exists():
        for item in memory_path.iterdir():
            if item.is_dir():
                file_count = len(list(item.rglob("*")))
                print(f"- {item.name}/: {file_count} files")
            else:
                print(f"- {item.name}: {item.stat().st_size} bytes")

inspect_memory(session)
```

### Performance Monitoring

```python
import time
import psutil
import os

def monitor_performance(func, *args, **kwargs):
    """Monitor performance of memory operations."""
    process = psutil.Process(os.getpid())
    
    # Before
    start_time = time.time()
    start_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Execute
    result = func(*args, **kwargs)
    
    # After
    end_time = time.time()
    end_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    print(f"Operation took: {end_time - start_time:.2f}s")
    print(f"Memory usage: {start_memory:.1f}MB -> {end_memory:.1f}MB ({end_memory - start_memory:+.1f}MB)")
    
    return result

# Usage
result = monitor_performance(session.search_memories, "test query", limit=10)
```

## Getting Help

### Collect Diagnostic Information

```python
def collect_diagnostics(session):
    """Collect diagnostic information for support."""
    import sys
    import platform
    
    info = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "memory_path": str(session.memory_base_path),
        "memory_exists": session.memory_base_path.exists(),
        "session_type": type(session).__name__,
    }
    
    # Memory statistics
    try:
        stats = session.get_memory_statistics()
        info["memory_stats"] = stats
    except Exception as e:
        info["memory_stats_error"] = str(e)
    
    # LanceDB status
    try:
        if hasattr(session, 'lancedb_storage'):
            tables = session.lancedb_storage.db.table_names()
            info["lancedb_tables"] = tables
    except Exception as e:
        info["lancedb_error"] = str(e)
    
    return info

# Collect and print diagnostics
diagnostics = collect_diagnostics(session)
print("Diagnostic Information:")
for key, value in diagnostics.items():
    print(f"- {key}: {value}")
```

### Report Issues

When reporting issues, please include:

1. **Error message** - Full traceback if available
2. **Environment** - Python version, OS, AbstractCore version
3. **Configuration** - Memory path, session type, LLM provider
4. **Steps to reproduce** - Minimal code example
5. **Diagnostic information** - Output from `collect_diagnostics()`

### Community Resources

- **GitHub Issues** - Report bugs and feature requests
- **Documentation** - Check other documentation files for detailed information
- **Examples** - Review examples.md for usage patterns

This troubleshooting guide covers the most common issues. For complex problems, enable debug logging and collect diagnostic information before seeking help.
