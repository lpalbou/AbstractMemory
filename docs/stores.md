# Stores / Backends

AbstractMemory provides three append-only triple stores:
- `InMemoryTripleStore` (dependency-free, volatile, vector-capable)
- `SQLiteTripleStore` (stdlib, persistent, vector-capable — the recommended
  single-file pairing for durable homes: construct with an embedder so rows
  embed on write; vectorless rows are a labeled degradation, not the
  default posture)
- `LanceDBTripleStore` (optional dependency, persistent, vector-capable)

Public exports: [`src/abstractmemory/__init__.py`](../src/abstractmemory/__init__.py)

## InMemoryTripleStore

Source: [`src/abstractmemory/in_memory_store.py`](../src/abstractmemory/in_memory_store.py)

What it is:
- A small, dependency-free implementation intended for tests/dev and environments without LanceDB.
- Stores assertions (and optional vectors) in process memory.

Vector search support:
- If constructed with an `embedder`, `add(...)` embeds a canonical text representation per assertion and stores it in-memory.
- `query_text=...` requires an `embedder` (raises `ValueError` otherwise).
- `query_vector=...` is supported, but only rows with stored vectors participate.
- Vector query results attach retrieval metadata to `attributes["_retrieval"]` (score + metric).
  - Embedded text is derived from `subject predicate object` plus selected `attributes` keys; see `_canonical_text(...)` in the store source.

## SQLiteTripleStore

Source: [`src/abstractmemory/sqlite_store.py`](../src/abstractmemory/sqlite_store.py)

What it is:
- A persistent SQLite-backed implementation using the Python standard library.
- The durable single-file store: structured queries AND native vector
  search in one file. Creates the table and indexes during construction;
  files created before the vector column existed upgrade in place
  (`ALTER TABLE` adds the `embedding` column on open — no migration step).

Semantic/vector support (mirrors the InMemory reference semantics exactly):
- Construct with `embedder=` and `add(...)` embeds each assertion's
  canonical text (edge assertions never embed) and persists the vector in
  the same file. An embedder failure aborts the add with zero rows written.
- `query_text=...` requires the embedder (raises the same `ValueError` as
  InMemory — no keyword fallback); `query_vector=...` works directly.
- Cosine ranking runs in Python over the SQL-filtered candidates (shared
  `vector_scoring.py` — both stores rank identically). The scan is linear,
  comfortable at single-home scale; ANN indexing is on the design backlog.
- Rows added while no embedder was configured stay vectorless: vector
  queries skip them and layer-2 recall labels the degradation
  (`#FALLBACK`). Re-embedding backfill is on the design backlog.

Persistence:
- Data (including vectors) is stored in the provided SQLite file path.
- Behavior is covered by [`tests/test_sqlite_triple_store.py`](../tests/test_sqlite_triple_store.py)
  and the cross-store parity suite [`tests/test_store_vectors.py`](../tests/test_store_vectors.py).

Stored columns:
- `assertion_id` (uuid)
- `subject`, `predicate`, `object`, `scope`, `owner_id`
- `observed_at`, `valid_from`, `valid_until`, `confidence`
- `provenance_json`, `attributes_json` (serialized dicts)
- `text` (canonical text, kept inspectable)
- `embedding` (JSON-encoded float list; NULL for vectorless rows)

## LanceDBTripleStore

Source: [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py)

Install:
- From source (recommended inside the AbstractFramework monorepo): `python -m pip install -e ".[lancedb]"`
- PyPI (packaged release): `python -m pip install "AbstractMemory[lancedb]"` (release channel may not match this repository checkout exactly; see [`README.md`](../README.md))

What it is:
- A persistent, local-path LanceDB table storing append-only assertions.
- A durable vector-capable backend with native vector indexing; choose it
  when you want LanceDB's storage format instead of a single SQLite file.

Dependency note:
- `lancedb` is optional; constructing `LanceDBTripleStore` raises an `ImportError` with an install hint when it is missing.
  - Evidence: [`tests/test_lancedb_triple_store.py`](../tests/test_lancedb_triple_store.py)

Persistence:
- Data is stored under the provided `uri` (directory path).
- Behavior is covered by the persistence test: [`tests/test_lancedb_triple_store.py`](../tests/test_lancedb_triple_store.py)

Stored columns (v0):
- `assertion_id` (uuid)
- `subject`, `predicate`, `object`, `scope`, `owner_id`
- `observed_at`, `valid_from`, `valid_until`, `confidence`
- `provenance_json`, `attributes_json` (serialized dicts)
- `text` (canonical text used for embedding, kept inspectable)
- optional vector column (default: `vector`) when `embedder` is configured

Query mechanics:
- Structured filters compile into a SQL-like `where` clause (see `_build_where_clause(...)`).
- Vector search uses LanceDB search with `metric("cosine")`. Returned rows include `_distance`; AbstractMemory attaches similarity metadata to `TripleAssertion.attributes["_retrieval"]`.

## Shared behavior (important contracts)

Canonicalization:
- `TripleAssertion` canonicalizes `subject`, `predicate`, `object` (trim + lowercase) and normalizes `scope`.
- `TripleQuery` canonicalizes the same fields for exact matching.

Append-only:
- There is no update/delete API. Represent changes by adding a new `TripleAssertion` with updated fields and fresh provenance.

Timestamps are strings:
- All stores compare `observed_at` / `valid_*` as strings.
- Use ISO-8601/RFC-3339 in UTC (e.g. `2026-01-01T00:00:00+00:00`) to keep ordering/filtering predictable.

Limit semantics:
- `limit <= 0` means “unbounded” (tested in [`tests/test_triple_store_limits.py`](../tests/test_triple_store_limits.py)).

Ordering + limit semantics:
- For non-semantic queries, all stores order by `observed_at` and apply `limit` after ordering.
  - Covered in [`tests/test_triple_store_limits.py`](../tests/test_triple_store_limits.py) and [`tests/test_sqlite_triple_store.py`](../tests/test_sqlite_triple_store.py).
  - Note: `LanceDBTripleStore` enforces this by fetching all matching rows then sorting in Python (no `order_by` on LanceDB query builders as used here). See [`src/abstractmemory/lancedb_store.py`](../src/abstractmemory/lancedb_store.py).

Vector consistency (all vector-capable stores):
- To use `query_text` / `query_vector`, assertions must have been written with vectors (store constructed with an `embedder`).
- Keep one embedding model per store: vectors from different models are not comparable, and the store does not enforce this.
- If you override `vector_column` (`InMemoryTripleStore` / `LanceDBTripleStore`), use the same name consistently for writes and queries; `SQLiteTripleStore` stores vectors in its `embedding` column.

## Next

- Query fields and semantics: [`docs/api.md`](api.md)
- System view and boundaries: [`docs/architecture.md`](architecture.md)
- Common questions: [`docs/faq.md`](faq.md)
