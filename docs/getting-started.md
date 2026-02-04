# Getting started

> Source of truth (public API exports): [`src/abstractmemory/__init__.py`](../src/abstractmemory/__init__.py)

Requires: Python 3.10+ (see [`pyproject.toml`](../pyproject.toml)).

## 1) Install

From PyPI (when published):

```bash
python -m pip install AbstractMemory
```

Optional persistence + vector search via LanceDB:

```bash
python -m pip install "AbstractMemory[lancedb]"
```

Note: the distribution name is `AbstractMemory` (pip is case-insensitive). The import name is `abstractmemory`.

From source (recommended for this monorepo package):

```bash
python -m pip install -e .
```

Optional persistence + vector search via LanceDB:

```bash
python -m pip install -e ".[lancedb]"
```

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

Next:
- Stores/backends: [`docs/stores.md`](stores.md)
- API reference: [`docs/api.md`](api.md)
- Architecture and boundaries: [`docs/architecture.md`](architecture.md)
- Common questions: [`docs/faq.md`](faq.md)
