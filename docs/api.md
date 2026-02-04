# API Reference (v0)

> This package is early/WIP. The API is intentionally small and may change.

## Public exports

All public exports are defined in [`src/abstractmemory/__init__.py`](../src/abstractmemory/__init__.py):
- Data model: `TripleAssertion`
- Query model: `TripleQuery`
- Store interface: `TripleStore` (typing protocol)
- Stores: `InMemoryTripleStore`, `LanceDBTripleStore`
- Embeddings: `TextEmbedder` (protocol), `AbstractGatewayTextEmbedder`

## `TripleAssertion`

Source: [`src/abstractmemory/models.py`](../src/abstractmemory/models.py)

An **append-only semantic assertion** with temporal + provenance metadata.

Fields (selected):
- `subject`, `predicate`, `object` (strings)
- `scope`: `"run" | "session" | "global"` (string)
- `owner_id`: identifier within the scope (e.g. a session id)
- `observed_at`: ISO-8601/RFC-3339 timestamp string (default: current UTC to seconds)
- `valid_from`, `valid_until`: optional validity window (see `TripleQuery.active_at`)
- `provenance`: free-form dict (e.g. `{"span_id": "...", "artifact_id": "..."}`)
- `attributes`: free-form dict (extractor evidence/context, retrieval metadata, etc.)

Behavior:
- `TripleAssertion` is immutable (`@dataclass(frozen=True)`).
- Terms are **canonicalized on creation** (trim + lowercase). This is part of the matching contract. Evidence: `TripleAssertion.__post_init__` in [`src/abstractmemory/models.py`](../src/abstractmemory/models.py) and [`tests/test_term_canonicalization.py`](../tests/test_term_canonicalization.py).
  - Canonicalization discards original casing/whitespace. Preserve raw strings separately (e.g. in `attributes`) if needed.
- Serialization helpers: `to_dict()` / `from_dict(...)` (same file).

## `TripleQuery`

Source: [`src/abstractmemory/store.py`](../src/abstractmemory/store.py)

Used by `TripleStore.query(...)`.

Core filters:
- `subject`, `predicate`, `object` (exact match after canonicalization)
- `scope`, `owner_id`
- `since`, `until`: compare `observed_at` timestamps
- `active_at`: filters by validity window intersection:
  - include if `(valid_from is None or valid_from <= active_at)` and `(valid_until is None or valid_until > active_at)`
  - end is **exclusive** (`valid_until > active_at`), consistent across stores

Semantic/vector filters (optional):
- `query_text`: text to embed for vector search (requires a configured `embedder`)
- `query_vector`: bypass embedding generation (vector provided by caller)
- `vector_column`: column name to use (default `"vector"`)
- `min_score`: cosine similarity threshold

Result shaping:
- `limit`: `<= 0` means “unbounded” (see tests in [`tests/test_triple_store_limits.py`](../tests/test_triple_store_limits.py))
- `order`: `"asc" | "desc"` (by `observed_at` for non-semantic queries)

Vector query results:
- When using `query_text` or `query_vector`, stores attach retrieval metadata to `TripleAssertion.attributes["_retrieval"]`.
  - In-memory: `{ "score": <cosine>, "metric": "cosine" }`
  - LanceDB: `{ "score": <cosine>, "distance": <_distance>, "metric": "cosine" }`

## `TripleStore` (protocol)

Source: [`src/abstractmemory/store.py`](../src/abstractmemory/store.py)

Minimal store interface:
- `add(assertions: Iterable[TripleAssertion]) -> list[str]` (returns generated assertion ids)
- `query(q: TripleQuery) -> list[TripleAssertion]`
- `close() -> None`

## Stores

Implementation sources:
- In-memory: [`src/abstractmemory/in_memory_store.py`](../src/abstractmemory/in_memory_store.py)
- LanceDB: [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py)

See [`docs/stores.md`](stores.md) for behavior differences and persistence details.

## Embeddings

Source: [`src/abstractmemory/embeddings.py`](../src/abstractmemory/embeddings.py)

`TextEmbedder` protocol:
- `embed_texts(texts: Sequence[str]) -> list[list[float]]`

`AbstractGatewayTextEmbedder`:
- Calls an AbstractGateway embeddings endpoint via HTTP (`POST` JSON `{ "input": [...] }`)
- Expects an OpenAI-like response shape with a `data` list containing `embedding` (and optionally `index`)

Tip: keep a stable provider/model per store instance to preserve a consistent embedding space (the store itself does not enforce this).
