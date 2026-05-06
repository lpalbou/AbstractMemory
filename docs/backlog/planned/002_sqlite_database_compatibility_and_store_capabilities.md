# Planned: SQLite database compatibility and store capabilities

## Metadata

- Created: 2026-05-05
- Status: Planned
- Completed: N/A
- Priority: High
- Components: SQLiteTripleStore, InMemoryTripleStore, LanceDBTripleStore, docs, tests

## Context

AbstractMemory has three store implementations:

- `InMemoryTripleStore`: dependency-free and volatile.
- `SQLiteTripleStore`: dependency-free, persistent, structured-query only.
- `LanceDBTripleStore`: optional dependency, persistent, vector-capable.

The SQLite work here is not about replacing in-memory or LanceDB. It is a
compatibility and capability task: make the SQLite backend safer and more
inspectable across local SQLite installations while giving hosts a uniform way
to ask all stores what they support.

## Current code reality

- `src/abstractmemory/sqlite_store.py` uses Python stdlib `sqlite3`.
- The SQLite store creates one table and three indexes during construction.
- SQLite currently interpolates `table_name` into SQL and should validate safe
  identifiers before broader usage.
- SQLite rejects `query_text` and `query_vector`; this is intentional.
- There is no capability descriptor API for any store.
- There is no keyword-search API distinct from semantic `query_text`.
- There is no deterministic export/import helper.
- `tests/test_sqlite_triple_store.py` covers persistence, ordering/limit,
  active-at filtering, and semantic rejection.
- `src/abstractmemory/in_memory_store.py` and
  `src/abstractmemory/lancedb_store.py` must remain first-class stores.

Re-check these files before implementation. If the current SQLite store has
already gained some of this behavior, update this item before coding.

## Problem

SQLite is the most inspectable durable backend, but host packages cannot yet
ask precise questions such as:

- Is this store persistent?
- Does it support semantic search?
- Does it support keyword/FTS search?
- Does it support bounded graph traversal efficiently?
- Can it export deterministic records for audit?
- Is the current SQLite build compatible with FTS5 if keyword search is
  requested?

Without explicit capabilities, callers will infer behavior from class names or
try a query and catch failures. That is brittle, especially as in-memory,
SQLite, and LanceDB continue to coexist.

## What we want to do

Add store capability metadata and harden SQLite compatibility without changing
the meaning of `query_text`. SQLite may gain explicit keyword/FTS support later,
but it must remain separate from semantic/vector retrieval.

## Why

The framework needs local-first durable memory that is boring, inspectable, and
portable. SQLite can serve that role, while LanceDB remains the vector-capable
backend and in-memory remains the simplest development/test backend. A common
capability contract lets higher packages choose the right store without
violating package boundaries.

## Requirements

- Keep all three store implementations supported.
- Do not make SQLite replace LanceDB vector search.
- Do not make `query_text` perform keyword fallback in SQLite.
- Add a small capability shape available from every store, such as:
  - `supports_persistence`
  - `supports_semantic`
  - `supports_query_vector`
  - `supports_keyword_search`
  - `supports_structured_query`
  - `supports_graph_walk`
  - `supports_deterministic_export`
- Validate or quote SQLite table/index identifiers safely.
- Detect optional SQLite features such as FTS5 before exposing keyword search.
- If keyword search is implemented, expose it through an explicit API/query
  field that cannot be confused with semantic `query_text`.
- Keep SQLite dependency-free by default.
- Preserve existing structured-query behavior and test expectations.
- Document capability differences in `docs/stores.md` and `docs/api.md`.

## Suggested implementation

Start with a small `StoreCapabilities` dataclass or frozen mapping in
`src/abstractmemory/store.py`.

Possible shape:

```python
@dataclass(frozen=True)
class StoreCapabilities:
    persistence: bool
    structured_query: bool
    semantic_query: bool
    vector_query: bool
    keyword_query: bool
    graph_walk: str  # none | generic | native
    deterministic_export: bool
```

Then add either:

- a `capabilities` property on concrete stores; or
- a helper `store_capabilities(store)` that recognizes the current concrete
  stores without changing the `TripleStore` protocol.

For SQLite compatibility:

- add table-name validation for safe SQL identifiers;
- add a small FTS5 probe helper, but do not require FTS5 for normal operation;
- keep any FTS table/search work opt-in and explicitly keyword-oriented;
- add deterministic export as JSON-compatible rows sorted by stable fields if
  that remains useful after capability metadata lands.

## Scope

- Store capability metadata for all current stores.
- SQLite identifier validation and compatibility probes.
- Optional explicit keyword-search prototype if it can be kept small and clearly
  separate from semantic search.
- Tests and docs for capability differences.

## Non-goals

- No schema-version framework unless a future concrete schema change
  needs one.
- No remote database or service.
- No SQLite vector extension dependency.
- No deprecation of in-memory or LanceDB stores.
- No hidden keyword fallback for `query_text`.
- No Runtime/Flow recall policy.

## Dependencies and related tasks

- AbstractFramework central ADRs:
  - `0001-layered-architecture.md`
  - `0005-memory-architecture.md`
  - `0009-connected-memory-recall-and-provenance.md`
  - `0019-testing-strategy-and-levels.md`
  - `0029-permissive-dependency-and-licensing-policy.md`
- Related planned work:
  - `001_semantics_aligned_memory_record_conventions.md`
  - `003_bounded_graph_traversal_over_triples.md`
  - `007_read_only_memory_observer_contract.md`

## Expected outcomes

- Callers can choose between in-memory, SQLite, and LanceDB based on explicit
  capabilities.
- SQLite is safer to construct with custom table names.
- SQLite remains structured-query only unless an explicit keyword API is added.
- Documentation no longer relies on informal backend descriptions alone.

## Validation

A-level:

- Unit tests for each store's capability descriptor.
- Unit tests that invalid SQLite table names are rejected.
- Existing tests continue to pass with `python -m pytest -q`.

B-level:

- Test SQLite behavior with and without FTS5 availability if keyword search is
  added.
- Test that SQLite `query_text` and `query_vector` still raise clear
  `ValueError`s.
- Test capability docs examples against actual capability values.

C-level:

- Deterministic export/import test over a mixed set of scoped assertions if the
  export helper is added.
- Optional LanceDB capability test when the dependency is installed.

## Progress checklist

- [ ] Re-read current store implementations and tests.
- [ ] Decide whether capabilities are a protocol property or external helper.
- [ ] Add capability metadata for all stores.
- [ ] Harden SQLite identifier handling.
- [ ] Probe FTS5 only if implementing explicit keyword search.
- [ ] Add tests for capabilities and SQLite compatibility.
- [ ] Update docs/API/backlog references to the final filename and behavior.

## Guidance for the implementing agent

Keep the compatibility story boring. The win is not "SQLite grows into every
feature"; the win is that every store is honest about what it can do, and
higher layers can make policy choices without guessing.
