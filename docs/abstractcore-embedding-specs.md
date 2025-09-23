# AbstractCore Embedding Specifications for AbstractMemory Integration

## Overview

AbstractMemory requires embedding generation capabilities from AbstractCore to enable vector search in LanceDB storage. This document specifies the exact interface that AbstractCore should implement.

## Required Interface

### Core Embedding Method

```python
def generate_embedding(self, text: str) -> List[float]:
    """
    Generate vector embedding for a single text string.

    Args:
        text (str): Input text to generate embedding for

    Returns:
        List[float]: Vector embedding of consistent dimensionality

    Raises:
        EmbeddingError: If embedding generation fails

    Example:
        >>> provider = create_llm("openai", embedding_model="text-embedding-3-small")
        >>> embedding = provider.generate_embedding("Hello world")
        >>> len(embedding)
        1536
        >>> isinstance(embedding[0], float)
        True
    """
    pass
```

### Batch Embedding Method (Optional)

```python
def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
    """
    Generate vector embeddings for multiple text strings (batch processing).

    Args:
        texts (List[str]): List of input texts to generate embeddings for

    Returns:
        List[List[float]]: List of vector embeddings, same order as input

    Raises:
        EmbeddingError: If any embedding generation fails

    Example:
        >>> provider = create_llm("openai", embedding_model="text-embedding-3-small")
        >>> embeddings = provider.generate_embeddings(["Hello", "World"])
        >>> len(embeddings)
        2
        >>> len(embeddings[0]) == len(embeddings[1])
        True
    """
    pass
```

## Configuration Requirements

### Provider Initialization

AbstractCore should support embedding model configuration:

```python
# OpenAI provider with embedding model
provider = create_llm(
    "openai",
    model="gpt-4",  # For text generation
    embedding_model="text-embedding-3-small"  # For embeddings
)

# Anthropic provider (if they add embedding support)
provider = create_llm(
    "anthropic",
    model="claude-3-5-haiku-latest",
    embedding_model="claude-embed-v1"  # Hypothetical
)

# Local embedding models
provider = create_llm(
    "ollama",
    model="llama3",
    embedding_model="nomic-embed-text"
)

provider = create_llm(
    "mlx",
    model="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
    embedding_model="mlx-community/nomic-embed-text-v1.5-4bit"
)
```

## Embedding Specifications

### Dimensionality

- **Consistent dimensionality**: All embeddings from the same model must have identical dimensions
- **Common dimensions**: Support standard embedding sizes (384, 512, 768, 1024, 1536, etc.)
- **Model-specific**: Dimension should match the underlying embedding model

### Data Types

- **Return type**: `List[float]` (not numpy arrays to avoid dependencies)
- **Float precision**: Standard Python float (64-bit)
- **Value range**: Typically normalized to [-1, 1] or [0, 1] depending on model

### Performance

- **Single embedding**: < 500ms for typical text (< 1000 tokens)
- **Batch processing**: Should be more efficient than individual calls
- **Caching**: Optional but recommended for identical texts
- **Rate limiting**: Handle provider rate limits gracefully

## Error Handling

### Exception Types

```python
class EmbeddingError(Exception):
    """Base exception for embedding-related errors"""
    pass

class EmbeddingModelNotFoundError(EmbeddingError):
    """Raised when specified embedding model is not available"""
    pass

class EmbeddingTokenLimitError(EmbeddingError):
    """Raised when text exceeds model's token limit"""
    pass

class EmbeddingRateLimitError(EmbeddingError):
    """Raised when hitting provider rate limits"""
    pass
```

### Error Handling Requirements

```python
def generate_embedding(self, text: str) -> List[float]:
    try:
        # Attempt embedding generation
        embedding = self._call_embedding_api(text)
        return embedding
    except TokenLimitExceeded:
        raise EmbeddingTokenLimitError(f"Text too long for embedding model: {len(text)} chars")
    except RateLimitExceeded:
        raise EmbeddingRateLimitError("Rate limit exceeded, try again later")
    except ModelNotFound:
        raise EmbeddingModelNotFoundError(f"Embedding model not found: {self.embedding_model}")
    except Exception as e:
        raise EmbeddingError(f"Embedding generation failed: {str(e)}")
```

## Integration Examples

### AbstractMemory Usage

```python
from abstractllm import create_llm
from abstractmemory import create_memory

# Create provider with embedding support
provider = create_llm("openai", embedding_model="text-embedding-3-small")

# Create memory with LanceDB storage and embeddings
memory = create_memory(
    "grounded",
    storage_backend="lancedb",
    storage_uri="./memory.db",
    embedding_provider=provider
)

# Memory will automatically use embeddings for vector search
memory.set_current_user("alice")
memory.add_interaction("I love Python", "Python is great!")

# Search uses vector similarity
results = memory.search_stored_interactions("programming languages")
```

### Dual Storage with Embeddings

```python
# Dual storage: markdown (observable) + LanceDB (searchable)
memory = create_memory(
    "grounded",
    storage_backend="dual",
    storage_path="./memory_files",      # Markdown storage
    storage_uri="./memory_vector.db",   # LanceDB storage
    embedding_provider=provider
)

# All interactions stored in both formats
memory.add_interaction("Machine learning question", "ML answer")

# Search leverages vector similarity in LanceDB
# But files remain observable in markdown format
```

## Provider-Specific Implementation Notes

### OpenAI

```python
# Use OpenAI's embedding API
import openai

class OpenAIProvider:
    def generate_embedding(self, text: str) -> List[float]:
        response = openai.embeddings.create(
            model=self.embedding_model,  # e.g., "text-embedding-3-small"
            input=text
        )
        return response.data[0].embedding
```

### Local Models (Ollama/MLX)

```python
# Use local embedding models
class LocalProvider:
    def generate_embedding(self, text: str) -> List[float]:
        # Implementation depends on local model framework
        # Should support models like nomic-embed-text
        embedding = self.local_model.encode(text)
        return embedding.tolist()  # Convert to List[float]
```

### Anthropic (Future)

```python
# When Anthropic adds embedding support
class AnthropicProvider:
    def generate_embedding(self, text: str) -> List[float]:
        # Future implementation
        response = anthropic.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.embedding
```

## Testing Requirements

### Unit Tests

AbstractCore should include tests for:

```python
def test_embedding_generation():
    provider = create_llm("openai", embedding_model="text-embedding-3-small")

    # Test single embedding
    embedding = provider.generate_embedding("Hello world")
    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert isinstance(embedding[0], float)

    # Test consistency
    embedding2 = provider.generate_embedding("Hello world")
    assert embedding == embedding2  # Same text should give same embedding

    # Test different texts
    embedding3 = provider.generate_embedding("Different text")
    assert embedding != embedding3  # Different text should give different embedding

def test_batch_embeddings():
    provider = create_llm("openai", embedding_model="text-embedding-3-small")

    texts = ["Hello", "World", "Test"]
    embeddings = provider.generate_embeddings(texts)

    assert len(embeddings) == len(texts)
    assert all(isinstance(emb, list) for emb in embeddings)
    assert all(len(emb) == len(embeddings[0]) for emb in embeddings)

def test_error_handling():
    provider = create_llm("openai", embedding_model="invalid-model")

    with pytest.raises(EmbeddingModelNotFoundError):
        provider.generate_embedding("test")
```

### Integration Tests

Tests should verify AbstractMemory integration:

```python
def test_abstractmemory_integration():
    provider = create_llm("openai", embedding_model="text-embedding-3-small")

    memory = create_memory(
        "grounded",
        storage_backend="lancedb",
        storage_uri=":memory:",  # In-memory for testing
        embedding_provider=provider
    )

    memory.add_interaction("Python programming", "Great topic!")
    results = memory.search_stored_interactions("coding")

    # Should find semantically similar results
    assert len(results) > 0
```

## Backward Compatibility

- **Optional embeddings**: If no embedding model specified, provider should work normally for text generation
- **Graceful degradation**: AbstractMemory should work without embeddings (falls back to text search)
- **Provider detection**: AbstractMemory should detect if embedding capability is available

```python
# Check if provider supports embeddings
if hasattr(provider, 'generate_embedding') and callable(provider.generate_embedding):
    # Use embeddings for enhanced search
    embedding = provider.generate_embedding(text)
else:
    # Fall back to text-only search
    embedding = None
```

## Implementation Priority

1. **OpenAI provider** - Most commonly used, well-documented API
2. **Local models (Ollama/MLX)** - Important for privacy and cost
3. **Anthropic provider** - When/if they add embedding support
4. **Batch processing** - Performance optimization
5. **Advanced features** - Caching, rate limiting, etc.

This specification ensures AbstractMemory can leverage AbstractCore's embedding capabilities for powerful vector search while maintaining clean separation of concerns between the packages.