# AbstractMemory Examples

This document provides practical examples of using AbstractMemory in various scenarios.

## Basic Usage Examples

### Simple Memory Session

```python
from abstractllm import create_llm
from abstractmemory.memory_session import MemorySession

# Create LLM provider
llm = create_llm("ollama", model="qwen3-coder:30b")

# Create memory session
session = MemorySession(
    provider=llm,
    memory_base_path="./my_memory",
    default_user_id="alice"
)

# Have a conversation
response = session.generate("I'm working on a Python project about data analysis.")
print(response.content)

# Continue the conversation - memory is automatically maintained
response = session.generate("What libraries would you recommend?")
print(response.content)
```

### Using Memory Tools

```python
# Explicitly store important information
session.remember_fact(
    content="Alice prefers pandas over numpy for data manipulation",
    importance=0.8,
    emotion="understanding",
    reason="Important preference for future recommendations"
)

# Search past memories
results = session.search_memories("data analysis libraries", limit=5)
for memory in results:
    print(f"- {memory['content'][:100]}...")

# Reflect on patterns
reflection = session.reflect_on("Alice's programming preferences", depth="deep")
print(reflection['insights'])
```

## Advanced Usage Examples

### Custom Configuration

```python
from abstractmemory.memory_session import MemorySession
from abstractllm.embeddings import EmbeddingManager

# Custom embedding manager
embedding_manager = EmbeddingManager(
    model="all-minilm-l6-v2",
    backend="auto"
)

# Session with custom settings
session = MemorySession(
    provider=llm,
    memory_base_path="./advanced_memory",
    embedding_manager=embedding_manager,
    default_user_id="researcher",
    default_location="lab"
)

# Adjust consolidation frequency
session.consolidation_frequency = 3  # Consolidate every 3 interactions
```

### Context Reconstruction with Focus Levels

```python
# Minimal context (fast)
context = session.reconstruct_context(
    user_id="alice",
    query="machine learning algorithms",
    focus_level=0  # Minimal: 2 memories, 1 hour window
)

# Balanced context (default)
context = session.reconstruct_context(
    user_id="alice", 
    query="machine learning algorithms",
    focus_level=3  # Balanced: 10 memories, 24 hour window
)

# Maximum context (comprehensive)
context = session.reconstruct_context(
    user_id="alice",
    query="machine learning algorithms", 
    focus_level=5  # Maximum: 20 memories, 1 week window
)

print(f"Found {context['total_memories']} relevant memories")
print(f"Context tokens: {context['context_tokens']}")
```

### Background Task Monitoring

```python
# Check background task status
if hasattr(session, 'task_queue'):
    status = session.task_queue.get_status()
    print(f"Queued tasks: {len(status.get('queued', []))}")
    print(f"Running tasks: {len(status.get('running', []))}")
    print(f"Completed tasks: {len(status.get('completed', []))}")

# Manual consolidation
from abstractmemory.core_memory_extraction import consolidate_core_memory
results = consolidate_core_memory(session, mode="manual")
updated_components = [k for k, v in results.items() if v]
print(f"Updated components: {updated_components}")
```

## CLI Usage Examples

### Basic CLI Interaction

```bash
# Start the CLI
python memory_cli.py --memory-path ./demo_memory --name demo_user

# In the CLI session:
demo_user> I'm learning about neural networks and deep learning.

🤖 That's exciting! Neural networks are a fascinating area of AI...

# Use memory tools in conversation
demo_user> search_memories("learning topics")

🤖 I found several memories about your learning interests:
- Previous discussion about neural networks
- Interest in deep learning fundamentals
- Questions about practical applications

# Load a document
demo_user> @neural_networks.pdf

🤖 I've loaded the neural networks document into my library...
```

### CLI with Custom Settings

```bash
# Advanced CLI usage
python memory_cli.py \
  --memory-path ./research_memory \
  --name researcher \
  --provider openai \
  --model gpt-4 \
  --location university \
  --debug

# The CLI will show debug information and use the specified settings
```

## Library Integration Examples

### Document Processing

```python
# Load a document into the library
if hasattr(session, 'library'):
    doc_id = session.library.capture_document(
        source_path="./research_paper.pdf",
        content=open("./research_paper.pdf", "rb").read(),
        content_type="pdf",
        context="Research on transformer architectures",
        tags=["ai", "transformers", "research"]
    )
    print(f"Document captured with ID: {doc_id}")

    # Search the library
    results = session.library.search_library(
        query="transformer attention mechanisms",
        limit=3
    )
    for result in results:
        print(f"- {result['title']}: {result['relevance_score']}")
```

### User Profile Analysis

```python
# Analyze user profile development
if hasattr(session, 'user_profile_manager'):
    profile_data = session.user_profile_manager.get_user_context("alice")
    
    print("User Profile Summary:")
    print(f"- Interactions: {profile_data.get('interaction_count', 0)}")
    print(f"- Interests: {profile_data.get('interests', [])}")
    print(f"- Communication style: {profile_data.get('communication_style', 'unknown')}")
    
    # Update profile based on new interactions
    session.user_profile_manager.update_profile(
        user_id="alice",
        interaction_data={
            "preferences": ["technical discussions", "detailed explanations"],
            "expertise_areas": ["data science", "machine learning"]
        }
    )
```

## Memory Analysis Examples

### Memory Statistics

```python
# Get comprehensive memory statistics
stats = session.get_memory_statistics()

print("Memory Statistics:")
print(f"- Total memories: {stats.get('total_memories', 0)}")
print(f"- Core components: {stats.get('core_components_updated', 0)}")
print(f"- Temporal anchors: {stats.get('temporal_anchors', 0)}")
print(f"- User profiles: {stats.get('user_profiles', 0)}")
print(f"- Library documents: {stats.get('library_documents', 0)}")
```

### Memory Export and Analysis

```python
# Export memory summary for analysis
summary = session.export_memory_summary("memory_analysis.json")

# Analyze memory patterns
from datetime import datetime, timedelta

# Get recent high-importance memories
recent_memories = session.search_memories(
    query="",  # Empty query to get all
    filters={
        "importance": {"gte": 0.7},
        "timestamp": {"gte": (datetime.now() - timedelta(days=7)).isoformat()}
    },
    limit=20
)

print(f"Found {len(recent_memories)} high-importance memories from the last week")
```

## Error Handling Examples

### Graceful Degradation

```python
try:
    # Attempt memory operation
    results = session.search_memories("complex query", limit=10)
except Exception as e:
    print(f"Memory search failed: {e}")
    # Fallback to basic response
    results = []

# Continue with available results
if results:
    print(f"Found {len(results)} memories")
else:
    print("No memories found, continuing without memory context")
```

### Memory Validation

```python
# Validate memory integrity
def validate_memory_structure(session):
    """Check if memory structure is intact."""
    memory_path = session.memory_base_path
    
    required_dirs = ['core', 'working', 'episodic', 'semantic', 'library', 'people']
    missing_dirs = []
    
    for dir_name in required_dirs:
        if not (memory_path / dir_name).exists():
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        print(f"Missing memory directories: {missing_dirs}")
        # Reinitialize structure
        from abstractmemory.memory_structure import initialize_memory_structure
        initialize_memory_structure(memory_path, user_id=session.default_user_id)
        print("Memory structure reinitialized")
    else:
        print("Memory structure is intact")

validate_memory_structure(session)
```

## Integration Examples

### Web Application Integration

```python
from flask import Flask, request, jsonify
from abstractmemory.memory_session import MemorySession

app = Flask(__name__)

# Initialize memory session
llm = create_llm("openai", model="gpt-4")
memory_session = MemorySession(
    provider=llm,
    memory_base_path="./web_memory",
    default_user_id="web_user"
)

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    user_id = request.json.get('user_id', 'anonymous')
    
    try:
        # Generate response with memory
        response = memory_session.generate(
            user_input,
            user_id=user_id,
            location="web_app"
        )
        
        return jsonify({
            'response': response.content,
            'memory_updated': True
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'response': 'Sorry, I encountered an error processing your request.'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
```

### Batch Processing Example

```python
# Process multiple interactions in batch
interactions = [
    {"user": "alice", "message": "I love machine learning"},
    {"user": "bob", "message": "Can you help with Python?"},
    {"user": "alice", "message": "What about deep learning frameworks?"}
]

for interaction in interactions:
    try:
        response = session.generate(
            interaction["message"],
            user_id=interaction["user"]
        )
        print(f"{interaction['user']}: {interaction['message']}")
        print(f"AI: {response.content[:100]}...")
        print("---")
    except Exception as e:
        print(f"Error processing interaction for {interaction['user']}: {e}")
```

## Testing Examples

### Memory Functionality Testing

```python
def test_memory_functionality(session):
    """Test basic memory operations."""
    
    # Test memory storage
    test_fact = "Test fact for validation"
    session.remember_fact(
        content=test_fact,
        importance=0.9,
        emotion="testing",
        reason="Validation test"
    )
    
    # Test memory search
    results = session.search_memories("test fact", limit=5)
    assert len(results) > 0, "Memory search should find stored fact"
    
    # Test context reconstruction
    context = session.reconstruct_context(
        user_id=session.default_user_id,
        query="test",
        focus_level=1
    )
    assert context['total_memories'] >= 0, "Context reconstruction should work"
    
    print("All memory functionality tests passed!")

# Run the test
test_memory_functionality(session)
```

### Performance Testing

```python
import time

def benchmark_memory_operations(session):
    """Benchmark memory operation performance."""
    
    # Benchmark memory search
    start_time = time.time()
    results = session.search_memories("machine learning", limit=10)
    search_time = time.time() - start_time
    
    # Benchmark context reconstruction
    start_time = time.time()
    context = session.reconstruct_context(
        user_id=session.default_user_id,
        query="artificial intelligence",
        focus_level=3
    )
    reconstruction_time = time.time() - start_time
    
    print(f"Memory search: {search_time:.2f}s ({len(results)} results)")
    print(f"Context reconstruction: {reconstruction_time:.2f}s ({context['total_memories']} memories)")

benchmark_memory_operations(session)
```

These examples demonstrate the flexibility and power of AbstractMemory across different use cases, from simple conversations to complex integrations and analysis workflows.
