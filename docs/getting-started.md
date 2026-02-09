# Getting started

> Source of truth (public API exports): [`src/abstractmemory/__init__.py`](../src/abstractmemory/__init__.py)

Requires: Python 3.10+ (see [`pyproject.toml`](../pyproject.toml)).

## 1) Install

From source (recommended inside the AbstractFramework monorepo):

```bash
python -m pip install -e .
```

Optional persistence + vector search via LanceDB:

```bash
python -m pip install -e ".[lancedb]"
```

PyPI (packaged release):

```bash
python -m pip install AbstractMemory
python -m pip install "AbstractMemory[lancedb]"
```

Notes:
- The distribution name is `AbstractMemory` (pip is case-insensitive). The import name is `abstractmemory`.
- PyPI releases may not match this monorepo directory exactly (they are currently published from `https://github.com/lpalbou/AbstractMemory`).

## 2) Dependency-free store (in-memory)

```python
from abstractmemory import InMemoryTripleStore, TripleAssertion, TripleQuery

store = InMemoryTripleStore()
store.add(
    [
        TripleAssertion(
            subject="Scrooge",
            predicate="related_to",
            object="Christmas",
            scope="session",
            owner_id="sess-1",
            observed_at="2026-01-01T00:00:00+00:00",
            provenance={"span_id": "span_123"},
        )
    ]
)

hits = store.query(
    TripleQuery(subject="scrooge", scope="session", owner_id="sess-1", limit=10)
)
assert hits[0].object == "christmas"  # terms are canonicalized (trim + lowercase)
```

Evidence:
- Terms are canonicalized on write and query: [`src/abstractmemory/models.py`](../src/abstractmemory/models.py), tests in [`tests/test_term_canonicalization.py`](../tests/test_term_canonicalization.py)

Tip: canonicalization lowercases `subject`/`predicate`/`object`. If you need to preserve original casing, store it separately (e.g. in `attributes`).

Tip (partitioning):
- Prefer setting `scope` + `owner_id` for most applications so multiple sessions/runs do not mix.
  - `scope="session", owner_id="<session-id>"` for per-user/per-conversation memory
  - `scope="run", owner_id="<run-id>"` for per-execution memory
  - `scope="global"` for shared memory (no `owner_id`)
Evidence: `scope`/`owner_id` are part of the store partitioning filters in [`src/abstractmemory/store.py`](../src/abstractmemory/store.py) and are enforced by both store implementations.

## 3) Persistent store (LanceDB)

```python
from pathlib import Path

from abstractmemory import LanceDBTripleStore, TripleAssertion, TripleQuery

store = LanceDBTripleStore(Path("data/kg"))
store.add([TripleAssertion(subject="e:scrooge", predicate="is_a", object="person", scope="global")])

out = store.query(TripleQuery(scope="global", limit=10))
store.close()
```

Evidence:
- Persistence across reopen: [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py), tests in [`tests/test_lancedb_triple_store.py`](../tests/test_lancedb_triple_store.py)

## 4) Semantic/vector queries (optional)

Vector search is opt-in:
- `query_text=...` requires a configured `embedder`
- `query_vector=...` bypasses embedding generation
- There is **no keyword fallback** when `query_text` is set (stores raise a `ValueError`)
- Vector queries require that assertions were stored with vectors (i.e. the store was created with an `embedder` and used consistently for writes/reads).

Evidence:
- `ValueError` contract is tested for both stores: [`tests/test_in_memory_query_text_fallback.py`](../tests/test_in_memory_query_text_fallback.py), [`tests/test_lancedb_triple_store.py`](../tests/test_lancedb_triple_store.py)

## 5) Gateway-managed embeddings (optional)

If you run **AbstractGateway** and want semantic retrieval without depending on AbstractCore directly, use the built-in HTTP adapter:

```python
import os

from abstractmemory import (
    AbstractGatewayTextEmbedder,
    LanceDBTripleStore,
    TripleAssertion,
    TripleQuery,
)

embedder = AbstractGatewayTextEmbedder(
    base_url="http://localhost:8000",  # set to your gateway base URL
    auth_token=os.getenv("ABSTRACTGATEWAY_AUTH_TOKEN"),
    # endpoint_path defaults to "/api/gateway/embeddings"
)

store = LanceDBTripleStore("data/kg", embedder=embedder)
store.add(
    [
        TripleAssertion(
            subject="e:scrooge",
            predicate="is_a",
            object="person",
            scope="global",
            attributes={"evidence_quote": "Scrooge was a man…"},
        )
    ]
)

hits = store.query(TripleQuery(query_text="scrooge", scope="global", limit=5))
```

Notes:
- Assertions are embedded from a canonical text representation (see `_canonical_text(...)` in the store implementations). Adding `attributes["evidence_quote"]` / `attributes["original_context"]` can improve retrieval selectivity.
- You can also implement your own `TextEmbedder`; see [`docs/api.md`](api.md).

Evidence:
- HTTP adapter: [`src/abstractmemory/embeddings.py`](../src/abstractmemory/embeddings.py)

Next:
- Stores/backends: [`docs/stores.md`](stores.md)
- API reference: [`docs/api.md`](api.md)
- Architecture and boundaries: [`docs/architecture.md`](architecture.md)
- Common questions: [`docs/faq.md`](faq.md)
