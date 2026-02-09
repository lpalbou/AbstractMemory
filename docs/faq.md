# FAQ

## Where should I start?

- Installation + first examples: [`docs/getting-started.md`](getting-started.md)
- Concepts and boundaries: [`docs/architecture.md`](architecture.md)
- Public API contracts: [`docs/api.md`](api.md)
- Store behavior: [`docs/stores.md`](stores.md)

## What is AbstractMemory (and what is it not)?

AbstractMemory is a small Python library for **append-only, temporal, provenance-aware triple assertions** plus **deterministic structured queries**, with optional vector/semantic retrieval.

It is **not**:
- A knowledge-graph reasoner (no inference/joins/ontologies in v0)
- A text extraction/summarization library (no AbstractCore dependency)
- A runtime provenance system (it stores provenance pointers, but does not create spans/artifacts)

Evidence: module map in [`docs/architecture.md`](architecture.md) and exports in [`src/abstractmemory/__init__.py`](../src/abstractmemory/__init__.py).

## How does AbstractMemory fit into AbstractFramework?

AbstractMemory is one component in the **AbstractFramework** ecosystem:
- **AbstractMemory**: storage/query of temporal + provenance-aware triples (this package)
- **AbstractGateway**: optional HTTP boundary for embeddings (used by `AbstractGatewayTextEmbedder`)
- **AbstractRuntime** + **AbstractCore**: typically sit behind the gateway to run models and manage provenance

Related projects:
- AbstractFramework: `https://github.com/lpalbou/AbstractFramework`
- AbstractCore: `https://github.com/lpalbou/abstractcore`
- AbstractRuntime: `https://github.com/lpalbou/abstractruntime`

Evidence:
- Gateway adapter boundary: [`src/abstractmemory/embeddings.py`](../src/abstractmemory/embeddings.py)
- No direct AbstractCore/AbstractRuntime dependency: [`pyproject.toml`](../pyproject.toml)
- Monorepo context (tests keep sibling packages import-stable): [`tests/conftest.py`](../tests/conftest.py)

See also: [`docs/architecture.md`](architecture.md) and [`README.md`](../README.md).

## What is the core data model?

`TripleAssertion` is the single write primitive:
`(subject, predicate, object)` plus `scope`, `owner_id`, time fields, and metadata dicts (`provenance`, `attributes`).

Evidence: [`src/abstractmemory/models.py`](../src/abstractmemory/models.py) and the API summary in [`docs/api.md`](api.md).

## Why are `subject` / `predicate` / `object` lowercased?

Canonicalization (trim + lowercase) is part of the matching contract to avoid missed matches due to casing drift.

Evidence:
- Canonicalization implementation: `canonicalize_term(...)` and `TripleAssertion.__post_init__` in [`src/abstractmemory/models.py`](../src/abstractmemory/models.py)
- Contract test: [`tests/test_term_canonicalization.py`](../tests/test_term_canonicalization.py)

If you need to preserve original casing/formatting, store it separately (e.g. `attributes={"raw_subject": "Alice"}`).

## Does AbstractMemory support updates or deletes?

No. Stores are append-only in v0: represent changes by **adding a new** `TripleAssertion` with updated fields and fresh provenance.

Evidence: store implementations in [`src/abstractmemory/in_memory_store.py`](../src/abstractmemory/in_memory_store.py) and [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py) expose `add(...)` and `query(...)` only.

## What do `scope` and `owner_id` mean?

They partition data for multi-tenant or multi-run usage:
- `scope`: `"run" | "session" | "global"`
- `owner_id`: optional identifier within the selected scope (e.g. session id)

Evidence: `TripleAssertion` and `TripleQuery` fields in [`src/abstractmemory/models.py`](../src/abstractmemory/models.py) and [`src/abstractmemory/store.py`](../src/abstractmemory/store.py).

## How are time filters evaluated?

Time fields are stored and compared as **strings**:
- `since` / `until` compare against `observed_at` (`>= since`, `<= until`)
- `active_at` intersects the `(valid_from, valid_until)` window
  - end is **exclusive**: `valid_until > active_at`

Use RFC-3339/ISO-8601 UTC strings (e.g. `2026-01-01T00:00:00+00:00`) to keep comparisons predictable.

Evidence:
- Query logic: [`src/abstractmemory/in_memory_store.py`](../src/abstractmemory/in_memory_store.py) and `_build_where_clause(...)` in [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py)
- Query field semantics: [`docs/api.md`](api.md)

## Which store should I use?

- `InMemoryTripleStore`: dependency-free, volatile (tests/dev or ephemeral agents)
- `LanceDBTripleStore`: persistent local-path store (durable memory)

Evidence: store implementations and behavior tests in [`docs/stores.md`](stores.md).

## Does `order` apply before `limit`?

Yes for **non-semantic** queries: results are ordered by `observed_at` and then limited.

Evidence: ordering tests in [`tests/test_triple_store_limits.py`](../tests/test_triple_store_limits.py).

Note: `LanceDBTripleStore` enforces this by fetching all matching rows and sorting in Python (no `order_by` API on the query builder used here). For large tables, filter aggressively by `scope`/`owner_id` and time bounds.

## How do I do semantic search?

Semantic/vector search is opt-in:
- `query_text=...` requires a configured embedder; there is **no keyword fallback** (stores raise `ValueError`)
- `query_vector=...` bypasses embedding generation

Evidence:
- Store contracts: [`src/abstractmemory/in_memory_store.py`](../src/abstractmemory/in_memory_store.py), [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py)
- Tests: [`tests/test_in_memory_query_text_fallback.py`](../tests/test_in_memory_query_text_fallback.py), [`tests/test_lancedb_triple_store.py`](../tests/test_lancedb_triple_store.py)

## Are queries deterministic?

For **structured** queries, yes: filters are explicit and non-semantic queries are ordered by `observed_at` and then limited.

For **vector** queries:
- ranking is similarity-based and depends on the configured embedder/backend
- ties are not specified

Evidence:
- Ordering/limit contract tests: [`tests/test_triple_store_limits.py`](../tests/test_triple_store_limits.py)
- Backend-specific notes: [`docs/stores.md`](stores.md)

## What gets embedded for vector search?

On `add(...)`, stores embed a canonical text representation derived from each `TripleAssertion`:
- always includes `subject predicate object`
- may include selected `attributes` keys (`subject_type`, `object_type`, `evidence_quote`, `original_context`), with context truncated

On `query(...)` with `query_text=...`, stores embed the query string and run vector search against stored vectors.

Evidence:
- `_canonical_text(...)` in [`src/abstractmemory/in_memory_store.py`](../src/abstractmemory/in_memory_store.py)
- `_canonical_text(...)` in [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py)

## What embedding interface do I need to implement?

Implement the `TextEmbedder` protocol:

- `embed_texts(texts: Sequence[str]) -> list[list[float]]`

Evidence: [`src/abstractmemory/embeddings.py`](../src/abstractmemory/embeddings.py).

## How does `AbstractGatewayTextEmbedder` work?

`AbstractGatewayTextEmbedder` is a thin HTTP client:
- `POST` JSON `{ "input": [ ... ] }` to `base_url + endpoint_path` (default `endpoint_path="/api/gateway/embeddings"`)
- Expects a response with a `data` list containing `embedding` arrays (and optionally `index` for stable ordering)
- Supports Bearer auth via the `auth_token` constructor parameter

Evidence: [`src/abstractmemory/embeddings.py`](../src/abstractmemory/embeddings.py).

## Where does vector retrieval metadata appear?

On results, stores attach retrieval metadata to `TripleAssertion.attributes["_retrieval"]`:
- In-memory: cosine `score` + `metric`
- LanceDB: cosine `score`, `distance` (from LanceDB `_distance`), + `metric`

Evidence: vector query code paths in [`src/abstractmemory/in_memory_store.py`](../src/abstractmemory/in_memory_store.py) and [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py).

## How do I inspect the LanceDB data on disk?

Data is stored under the `uri` path passed to `LanceDBTripleStore`. You can open it with LanceDB and inspect the table.

Evidence: `LanceDBTripleStore.__init__` and `add(...)` in [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py) describe the connection and stored columns (also summarized in [`docs/stores.md`](stores.md)).
