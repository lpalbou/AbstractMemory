# Home store performance: owner predicate, column projection, binary vectors, matrix cache

Created: 2026-10-27 ([ADR 0003](../../../adr/0003-one-graph-ledger-provenance-and-revisions.md) decisions 3 and 12).
Track: `knowledge_graph_convergence` · Priority: High · Status: Planned (slice in progress on
`feat/memory-graph-performance`)

## Summary
Make the SQLite home store hold a notebook-sized corpus: owner filters that use the indexes, reads that do not fetch
the embedding column unless asked, vectors stored as float32 blobs and scored from an in-process matrix cache that is
appended on write (never rebuilt from a full scan), bounded `maintenance_due`, and the baseline benchmark kept in the
repo so every later change is measured.

## Why
Measured 2026-10-27 (`untracked/memory-transition/audit/bench_abstractmemory_baseline.py`): subject+scope+owner
query 34 ms at 50k rows (index defeated by `COALESCE(owner_id,'') = ?`), latest-100-in-scope 588 ms, vector query
11.1 s at 50k (JSON-decoded vectors, Python cosine), `reconstruct` 8.4 s at 20k records (67 % vector scoring),
`maintenance_due` 4.8 s. The operator's notebook has 15,631 claims and 5,503 entities; one plane mind will hold more.

## Current code reality
- `sqlite_store.py:423-530` `query` (`SELECT *`, `COALESCE` owner predicate), `:563-616` vectors as JSON text in the
  `embedding` column; `vector_scoring.py` Python cosine; `maintenance.py` full-history reads.

## Scope
In: `owner_id` predicate rewritten so SQLite uses `idx_<table>_scope_owner` (and a covering index where measured);
column projection (vector only when `query_vector`/`query_text` or an explicit flag asks); `embedding` as a float32
BLOB with in-place upgrade of JSON rows on open (one-time, idempotent, high-water cursor like the FTS backfill); a
per-store matrix cache (`numpy` optional: when absent, the labelled Python path stays) appended on `add`, invalidated
on `replace_vectors`; `maintenance_due` bounded by a cursor; the benchmark script moved to `tests/bench/` with the
before/after table in the completion report. Out: ANN libraries (LanceDB stays the optional accelerator, 0057).

## Dependencies
None (parallel with 0056; both touch `sqlite_store.py` in different regions: 0056 adds `narrow_assertion` after
`close_assertion`, 0058 changes `query`/`_row_to_assertion`/schema).

## Validation
The baseline script re-run after the change at 10k and 50k with the table quoted; every existing store test green on
both backends; a mutant that restores `SELECT *` or the `COALESCE` predicate makes the measurement test (an
`EXPLAIN QUERY PLAN` assertion) go red.
