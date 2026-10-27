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
- Vectors are stored as float32 little-endian BLOBs (4 bytes per
  dimension; backlog 0058). A home written by an earlier version (JSON text
  vectors) is upgraded in place when the store opens: rows above the
  `vector_blob_high_water` cursor of the meta sidecar are rewritten in
  bounded transactions, so the upgrade is idempotent and an interrupted one
  resumes (about 5 s for 50k rows of 384-d vectors, once). Values float32
  cannot hold are refused at write (`ValueError`) rather than clipped.
- Cosine ranking returns exactly what the reference scan of
  `vector_scoring.py` returns (same rows, same order, bit-identical scores;
  both stores rank identically). With numpy installed
  (`pip install "abstractmemory[fast]"`), the store serves it from an
  in-process float32 matrix cache: built at a handle's first semantic query,
  appended with the rows written since (by any handle or process), rebuilt
  when `replace_vectors` or the upgrade rewrites the vectors
  (`vector_generation` in the meta sidecar). A float32 pass selects the
  candidates with a margin above its error bound and the candidates are
  re-scored with the reference arithmetic. Memory: 4 bytes per dimension
  per vectored row (about 77 MB for 50k rows of 384-d vectors).
  `store.vector_engine` says which path serves: `"numpy-matrix-cache"` or
  `"python-linear-scan"`. The Python scan serves (labelled once per handle
  with a `#FALLBACK` warning) when numpy is absent or a stored vector cannot
  be scored exactly by the matrix (mixed dimensions, non-finite values).
  ANN indexing stays out of scope (LanceDB is the optional accelerator).
- Rows added while no embedder was configured stay vectorless: vector
  queries skip them and layer-2 recall labels the degradation
  (`#FALLBACK`). The `reembed_store(...)` repair pass backfills them.

Embedding-space pin (one store = one embedding space; both stores):
- Pass `embedding_pin={"model_id": ..., "dimension": ...}` at construction
  to declare the space as a birth choice (SQLite persists it in a
  `{table}_meta` sidecar in the same file). `store.embedding_pin()` reads it.
- No silent mixing of spaces: a known embedder identity contradicting the
  pin refuses at open; a wrong-dimension write refuses with zero rows; a
  wrong-dimension query vector refuses at read (layer-2 recall converts
  that into the vector channel's labeled `#FALLBACK` and keeps serving
  exact/keyword).
- Pinless legacy stores pin at their first embedded write with a labeled
  `#FALLBACK` warning — creation pinning is the contract for new homes.
  First-write pins carry `claimed_by: "embedder-attribute"`: the model_id
  is a CLAIM read off the bound embedder object, never verified against
  the serving endpoint (the engine cannot know server truth). Creation and
  reembed pins are operator-vouched and carry no claim marker.
- Embed-time failures name the pin: when the configured embedder fails a
  `query_text` embed (e.g. an HTTP 400 naming the requested model), the
  raised error appends `[store pin: <model>@<dim>d (source, claimed by
  ...)]` so claimed-vs-served identity is visible in one line; the vector
  channel's `#FALLBACK` warning carries the same suffix.
- `reembed_store(system, embedder=..., owner_id=...)` is the deliberate,
  operator-gated migration: all-or-nothing re-embed + atomic swap, pin
  updated last, the act journaled as a bookkeeping record. Same memories,
  different neighbors — a substrate effect, on the record, never silent.

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
- `embedding` (float32 little-endian BLOB since 0.4.0; JSON text in homes
  not yet upgraded; NULL for vectorless rows)

Reads (backlog 0058):
- Structured reads select the assertion columns only (never `embedding` or
  `text`); `stored_vector(id)` and semantic queries read the vector.
- The owner filter is an index-usable equality; partition reads ("latest N
  in a (scope, owner)", as-of windows, per-pair scans) walk
  `idx_<table>_scope_owner_observed` in query order; reads anchored on ids,
  a subject or an object use their own index. `query_plan(q)` returns
  SQLite's `EXPLAIN QUERY PLAN` lines for a query.
- `assertions_after(cursor, *, scope=None, owner_id=None, limit=1000)` is a
  bounded change feed in rowid order (`(rows, next_cursor)`); the
  maintenance cadence folds it so a check reads only the rows written since
  the previous one. `InMemoryTripleStore` offers the same feed over its
  insertion order.

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
- The one in-place change: `InMemoryTripleStore` and `SQLiteTripleStore` offer `close_assertion(assertion_id, valid_until)`, which sets `valid_until` on an assertion whose window is still open (`True` when a row changed; `False` for an unknown id or an already closed window). Every other column, the keyword index and the stored vector stay as written. `LanceDBTripleStore` does not offer it.

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
