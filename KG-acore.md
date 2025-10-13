# AbstractCore/AbstractLLM Knowledge Graph

## Overview
AbstractCore (packaged as AbstractLLM v1.1.0) provides unified LLM communication with tool support, structured responses, and memory capabilities. Core principle: Provider abstraction with universal tool system.

## 1. Core Architecture

### Session Management
```python
# Main entry point: abstractllm.session.Session
from abstractllm.session import Session

class Session:
    def __init__(self, provider=None, system_prompt=None, **kwargs)
    def generate(...) -> GenerateResponse
    def generate_with_tools(...) -> GenerateResponse  # Tool loop
    def add_message(role, content, metadata=None) -> Message
    def add_tool(tool_fn or ToolDefinition)
    def execute_tool_call(tool_call) -> ToolResult
```

**Key Discovery**: No "core" subdirectory exists. Import is `abstractllm.session`, not `abstractllm.core.session`.

### Provider System
```python
# Universal interface
class AbstractLLMInterface:
    def generate(...) -> GenerateResponse
    def generate_stream(...) -> Generator
    def detect_capabilities() -> List[ModelCapability]

# LMStudio Provider (OpenAI-compatible)
from abstractllm.providers.lmstudio_provider import LMStudioProvider
provider = LMStudioProvider(
    base_url="http://localhost:1234/v1",
    model="qwen/qwen3-coder-30b"  # Default as requested
)
```

## 2. Tool System

### Architecture
```python
# Core types
ToolDefinition(name, description, parameters)  # JSON Schema format
ToolCall(name, arguments, id)
ToolResult(tool_call_id, output, error)

# Registration patterns
@register  # Decorator for function-to-tool conversion
Session.add_tool(callable)  # Auto-converts to ToolDefinition
```

### Tool Detection & Execution
1. **Native API Tools**: OpenAI/Anthropic function_call API
2. **Prompted Tools**: Ollama/LMStudio use XML/JSON tags in prompts
3. **Tool Loop**: `generate_with_tools()` automatically handles:
   - Generate with tools available
   - Detect tool calls
   - Execute tools
   - Add results to messages
   - Synthesis response
4. **Max Tool Calls**: Configurable limit to prevent infinite loops

### Tool Format Examples
```python
# Function to tool conversion
def remember_fact(content: str, importance: float):
    """Store important information in memory."""
    return {"memory_id": "...", "status": "stored"}

# Session auto-converts to:
ToolDefinition(
    name="remember_fact",
    description="Store important information in memory.",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "importance": {"type": "number"}
        }
    }
)
```

## 3. Structured Response System

### StructuredResponseHandler
```python
from abstractllm.structured_response import (
    StructuredResponseHandler,
    StructuredResponseConfig,
    ResponseFormat
)

class StructuredResponseHandler:
    def __init__(self, provider_name):
        self.supports_native_json = provider_name in ["openai", "anthropic"]

    def prepare_request(prompt, config):
        # Adds schema, examples, JSON instructions
        # Returns: modified_prompt, system_prompt, params

    def parse_response(response, config):
        # Strips markdown, extracts JSON
        # Validates against schema/Pydantic
        # Returns: parsed_object

    def generate_with_retry(generate_fn, prompt, config):
        # Retries with error feedback on validation failures
```

### Response Formats
- `ResponseFormat.JSON` - Basic JSON output
- `ResponseFormat.JSON_SCHEMA` - With schema validation
- `ResponseFormat.PYDANTIC` - Pydantic model validation
- `ResponseFormat.YAML` - YAML output
- `ResponseFormat.XML` - XML output

### Configuration
```python
config = StructuredResponseConfig(
    response_format=ResponseFormat.PYDANTIC,
    model=YourPydanticModel,
    max_retries=3,
    examples=[...],
    additional_instructions="Be concise"
)
```

## 4. Embedding System

### EmbeddingManager
```python
from abstractllm.embeddings import EmbeddingManager

class EmbeddingManager:
    def __init__(self, model_name="ibm-granite/granite-embedding-30m-english"):
        # Offline-first: Downloads to ~/.abstractllm/embeddings/
        # Persistent cache: ~/.abstractllm/embeddings/cache/

    @lru_cache(maxsize=1000)
    def embed_text(text: str) -> List[float]:
        # Memory cache + disk cache
        # Periodic saves every 10 embeddings

    def embed_batch(texts: List[str]) -> List[List[float]]:
        # Batch processing for efficiency

    def compute_similarity(text1: str, text2: str) -> float:
        # Cosine similarity
```

### LanceDB Integration
```python
from abstractllm.storage.lancedb_store import ObservabilityStore

# Pattern: Store interactions with embeddings for semantic search
store = ObservabilityStore(db_path="./lance_db")
store.add_interaction(
    query="...",
    response="...",
    metadata={},
    embedding=embedding_manager.embed_text(query)
)
```

## 5. Logging System

### Structured Logging
```python
from abstractllm.utils.logging import (
    configure_logging,
    log_request,
    log_response,
    log_step,
    suppress_third_party_warnings
)

# Dual-level logging
configure_logging(
    log_dir="logs",
    console_level=logging.WARNING,  # Clean console
    file_level=logging.DEBUG        # Verbose files
)

# Features:
# - Colored console with truncation
# - Full verbatim file logs
# - Per-interaction JSON files
# - Third-party warning suppression
# - LRU caching logs
```

### Log Files Structure
```
logs/
├── {provider}_{model}_{type}_{timestamp}.json  # Interaction logs
├── abstractllm_{timestamp}.log                 # Main log file
└── request/response matching via _pending_requests
```

### Logging Functions
```python
log_request(provider, prompt, parameters)
log_response(provider, response, **kwargs)
log_step(step_number, step_name, message)  # For ReAct cycles
suppress_third_party_warnings()            # HuggingFace, transformers
```

## 6. Capabilities & Model Support

### ModelCapability Enum
```python
ModelCapability.CHAT
ModelCapability.COMPLETION
ModelCapability.EMBEDDINGS
ModelCapability.VISION
ModelCapability.TOOL_CALLING
ModelCapability.STREAMING
```

### Provider Capabilities
- **LMStudio**: CHAT, TOOL_CALLING, STREAMING (OpenAI-compatible)
- **Ollama**: CHAT, TOOL_CALLING, STREAMING (prompted tools)
- **OpenAI**: All capabilities (native function calling)
- **Anthropic**: All capabilities (native tool use)
- **HuggingFace**: CHAT, COMPLETION, EMBEDDINGS
- **MLX**: CHAT, COMPLETION (local Apple Silicon)

## 7. Memory & Observability

### Built-in Memory
```python
# Session has built-in conversation memory
session.messages = []  # Message history
session.add_message(role="user", content="...", metadata={})
```

### Observability Store
```python
# Optional LanceDB-based observability
from abstractllm.storage.lancedb_store import ObservabilityStore

# Stores interactions with embeddings for RAG
# Schema: id, timestamp, provider, model, query, response, metadata, embedding
```

## 8. Event System Analysis

**Status**: AbstractLLM does NOT have a formal event emitter/listener system.

**Current Patterns**:
- Context logging captures interactions
- Scratchpad manager tracks ReAct cycles
- Provider-level streaming callbacks
- Session-level telemetry/observability

**Implication**: AbstractMemory could implement its own event system if needed for memory operations.

## 9. Key Integration Patterns

### Session Extension Pattern
```python
from abstractllm.session import Session

class MySession(Session):
    def __init__(self, provider, **kwargs):
        super().__init__(provider, **kwargs)
        # Add custom functionality
        self._register_custom_tools()

    def custom_method(self):
        # Override or extend
        pass
```

### Tool Registration Pattern
```python
# Create callables
def my_tool(arg1: str, arg2: int) -> dict:
    return {"result": "..."}

# Session auto-converts
session = Session(provider)
session.add_tool(my_tool)  # Becomes ToolDefinition automatically
```

### Structured Response Pattern
```python
from abstractllm.structured_response import StructuredResponseHandler
from pydantic import BaseModel

class MyOutput(BaseModel):
    answer: str
    confidence: float

handler = StructuredResponseHandler(provider_name="lmstudio")
response = handler.generate_with_retry(
    session.generate,
    prompt="...",
    config=StructuredResponseConfig(
        response_format=ResponseFormat.PYDANTIC,
        model=MyOutput
    )
)
```

## 10. Critical Discoveries for AbstractMemory Integration

### What AbstractMemory Does Right
- ✅ Uses EmbeddingManager correctly
- ✅ Follows tool registration patterns (callables → auto-conversion)
- ✅ Similar LanceDB storage approach
- ✅ Proper Session extension pattern

### Critical Issues to Fix
- ❌ **Import Path**: `abstractllm.core.session.BasicSession` doesn't exist
  - Should be: `abstractllm.session.Session`
- ⚠️ **Duplication**: Custom `response_handler.py` duplicates `StructuredResponseHandler`
- ⚠️ **Logging**: Not using AbstractLLM's logging utilities
- ⚠️ **Provider**: Should default to LMStudio + qwen/qwen3-coder-30b

### Refactoring Opportunities
1. **Session Import Fix** (Critical)
2. **Structured Response Integration** - Replace custom handler
3. **Logging Integration** - Use AbstractLLM logging
4. **Provider Standardization** - Default to LMStudio
5. **Tool Return Standardization** - Consistent return types
6. **Type Hints** - Comprehensive typing throughout

### AbstractCore Capabilities for AbstractMemory
- **Summarizer**: Use for memory content summarization
- **Extractor**: Use for fact extraction from conversations
- **Judge**: Use for memory importance scoring
- **Structured Response**: Use for memory operations that need validation
- **Tool System**: Already well-integrated
- **Embedding Manager**: Already well-integrated
- **Logging**: Should integrate for better observability