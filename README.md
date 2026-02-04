# AbstractMemory (early / WIP)

AbstractMemory is a small Python library for **append-only, temporal, provenance-aware triple assertions** with a **deterministic query API** and optional **vector/semantic retrieval**.

## Status
- This package is still early: API and storage details may change.
- Implemented today: `TripleAssertion`, `TripleQuery`, `InMemoryTripleStore`, `LanceDBTripleStore`, `AbstractGatewayTextEmbedder`.
  - Source of truth for exports: [`src/abstractmemory/__init__.py`](src/abstractmemory/__init__.py)
- Requires Python 3.10+ (see [`pyproject.toml`](pyproject.toml))

## Install

From PyPI (when published):

```bash
python -m pip install AbstractMemory
```

Optional persistent backend + vector search:

```bash
python -m pip install "AbstractMemory[lancedb]"
```

Note: the distribution name is `AbstractMemory` (pip is case-insensitive). The import name is `abstractmemory`.

From source (recommended for this monorepo package):

```bash
python -m pip install -e .
```

Optional persistent backend + vector search:

```bash
python -m pip install -e ".[lancedb]"
```

## Quick example

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
            provenance={"span_id": "span_123"},
        )
    ]
)

hits = store.query(TripleQuery(subject="scrooge", scope="session", owner_id="sess-1"))
assert hits[0].object == "christmas"  # terms are canonicalized (trim + lowercase)
```

## Documentation

- Getting started: [`docs/getting-started.md`](docs/getting-started.md)
- FAQ: [`docs/faq.md`](docs/faq.md)
- Architecture (with diagrams): [`docs/architecture.md`](docs/architecture.md)
- Stores/backends: [`docs/stores.md`](docs/stores.md)
- API reference: [`docs/api.md`](docs/api.md)
- Development: [`docs/development.md`](docs/development.md)

## Project

- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security: [`SECURITY.md`](SECURITY.md)
- License: [`LICENSE`](LICENSE)
- Acknowledgments: [`ACKNOWLEDGMENTS.md`](ACKNOWLEDGMENTS.md)

## Design principles (v0)

- **Triples-first** representation with temporal fields (`observed_at`, `valid_from`, `valid_until`).
  - Implemented in `TripleAssertion`: [`src/abstractmemory/models.py`](src/abstractmemory/models.py)
- **Append-only**: represent updates by adding a new assertion with fresh provenance.
  - Implemented by both stores: [`src/abstractmemory/in_memory_store.py`](src/abstractmemory/in_memory_store.py), [`src/abstractmemory/lancedb_store.py`](src/abstractmemory/lancedb_store.py)
- **No direct AbstractCore dependency**: embeddings can be obtained via an AbstractGateway HTTP API.
  - Implemented by `AbstractGatewayTextEmbedder`: [`src/abstractmemory/embeddings.py`](src/abstractmemory/embeddings.py)
