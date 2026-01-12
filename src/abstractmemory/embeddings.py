from __future__ import annotations

from typing import List, Protocol, Sequence


class TextEmbedder(Protocol):
    """Minimal text embedding interface used by AbstractMemory stores."""

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]: ...


class AbstractCoreTextEmbedder:
    """Text embedder backed by AbstractCore's EmbeddingManager.

    This is intentionally a thin adapter so hosts (runtime/gateway) can own:
    - provider/model selection
    - caching policy
    - batching strategy
    - timeouts
    """

    def __init__(self, *, provider: str, model: str):
        from abstractcore.embeddings.manager import EmbeddingManager

        self._mgr = EmbeddingManager(provider=provider, model=model)

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        items = [str(t) for t in texts]
        return self._mgr.embed_batch(items)

