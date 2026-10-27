# Home store performance: owner predicate, column projection, binary vectors, matrix cache

Created: 2026-10-27 ([ADR 0003](../../../adr/0003-one-graph-ledger-provenance-and-revisions.md) decisions 3 and 12).
Track: `knowledge_graph_convergence` · Priority: High · Status: Implemented on `feat/memory-graph-performance`
(2026-10-27), awaiting merge into the convergence branch; see Report

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

## Report

Implemented 2026-10-27 on `feat/memory-graph-performance` (worker W2 of the memory transition), on top of the
lead's commits 9045259 (owner predicate, partition index, `query_plan`), 2a16b75 (column projection) and 496b0da
(float32 BLOBs, matrix cache).

What landed:
- **Owner predicate and partition index** (9045259): `owner_id = ?`; `idx_<table>_scope_owner_observed (scope,
  owner_id, observed_at, assertion_id)`; anchored reads keep their own index (unary `+`); `query_plan(q)`.
- **Column projection** (2a16b75): structured reads and `query_keywords` select the assertion columns only.
  Structured reads also no longer read the embedding pin (it guards semantic queries only): one meta query + JSON
  parse less per store read.
- **Binary vectors**: float32 little-endian BLOBs; JSON-vector homes upgrade in place on open above the
  `vector_blob_high_water` cursor, `VECTOR_UPGRADE_BATCH` rows per transaction (idempotent, crash-resumable; a batch
  that rewrote rows bumps `vector_generation`). `encode_vector` refuses a value float32 cannot hold.
- **Matrix cache** (`vector_matrix.py`, numpy optional through the new `abstractmemory[fast]` extra): built at a
  handle's first semantic query, appended with rows written since (any handle or process), rebuilt when the
  vector space changes (`vector_generation` + embedding pin). Ranking is exactly the reference scan: the review of
  496b0da found its float64 "exact" pass used BLAS/pairwise sums, which differ from `vector_scoring.cosine` in the
  last bits on about 90 % of rows; the pass now sums left to right (`cumsum`) and reproduces the reference bit for
  bit. The float32 candidate margin is derived from the dot-product error bound per dimension; rows outside that
  bound (tiny/huge norms, legacy values beyond float32) are always candidates; legacy float64 JSON rows are scored
  from their float64 values; sync, ranking and row read share one read snapshot. Labelled `#FALLBACK` (once per
  handle) when numpy is absent or a vector is unrepresentable (mixed dimensions, non-finite, empty, non-numeric);
  `vector_engine` reports the path.
- **Bounded `maintenance_due`**: `assertions_after(cursor, ...)` change feed on the SQLite (rowid) and in-memory
  (insertion index) stores; `sleep_cadence._CadenceFold` keeps the facts the answer needs per (store, journal,
  scopes); a check reads only rows written since the previous one and re-reads the formation bindings only when
  the journal moved. Same answer as the full scan (kept as `_maintenance_due_scan`, the reference, and the path
  for stores without a feed).
- Tuning constants in one module, `store_tuning.py`, with their bounds/measurements.
- Benchmark: `tests/bench/bench_store.py` (successor of the audit baseline script).

Tests: `tests/test_vector_matrix.py` (matrix == reference scan bit for bit on random data with ties, near-ties,
zero and vectorless rows, min_score/limit combinations, SQL-filtered candidates; forced rows; incremental append
across handles with a row counter; invalidation after `replace_vectors` from another handle with an identical pin;
in-place upgrade idempotent, crash-resumable, cursor respected; legacy float64 JSON exact; numpy-absent and
unrepresentable fallbacks warned once; encoding; the `[fast]` extra), `tests/test_cadence_cursor.py` (fold ==
full scan on random stores, both backends, multi-scope, repeated scope, `''` owner; fixture flow; O(new rows)
reads; each fact alone invalidates; per-backend tie order), `tests/test_store_performance.py` (plans, projection,
no pin read). Each file lists its mutants; every mutant was applied by hand and turned the suite red.

### Measurements (before = `main` 2300e74, after = this branch)

Commands (temporary stores, deleted afterwards; no network; fake deterministic 384-d embedder):

```
cd /private/tmp
PYTHONPATH=<abstractmemory main checkout>/src python <worktree>/tests/bench/bench_store.py --sizes 10000 50000 --backends sqlite
PYTHONPATH=<worktree>/src                     python <worktree>/tests/bench/bench_store.py --sizes 10000 50000 --backends sqlite
PYTHONPATH=<abstractmemory main checkout>/src python <worktree>/tests/bench/bench_store.py --sizes --system 5000 20000
PYTHONPATH=<worktree>/src                     python <worktree>/tests/bench/bench_store.py --sizes --system 5000 20000
```

Store level, SQLite, a vector on every row (means; ms unless stated):

| operation | 10k before | 10k after | 50k before | 50k after |
|---|---|---|---|---|
| batch add (1000-row chunks), per row | 227 µs | 54 µs | 242 µs | 78 µs |
| subject + scope + owner, limit 100 | 1.43 | 0.067 | 14.8 | **0.33** |
| object (incoming edges) | 0.078 | 0.045 | 0.25 | 0.18 |
| scope "latest 100" | 56.0 | 0.62 | 377 | 0.92 |
| scope as-of, limit 100 | 31.3 | 3.6 | 193 | 21.9 |
| scope full scan (`limit=0`) | 356 | 65 | 2645 | **496** |
| vector query, scope filter, limit 20 (warm) | 1101 | 0.49 | 5347 | **1.42** |
| vector query, first on a handle (matrix build) | 1102 | 55 | 5774 | 444 |
| vector query right after one add | 1171 | 2.2 | 5636 | 2.6 |
| reopen + first vector query | 865 | 53 | 4875 | 366 |
| in-place upgrade of a JSON home (one-time open) | - | 0.85 s | - | 4.74 s |
| on-disk size | 90.7 MB | 24.5 MB | 449.5 MB | 121.8 MB |

MemorySystem level (SQLite store + journal in one file; same harness as the audit):

| operation | 5k before | 5k after | 20k before | 20k after |
|---|---|---|---|---|
| reconstruct (mean of 3) | 536 | 87 | 2681 | **198** |
| probe | 480 | 93 | 2321 | 238 |
| `maintenance_due`, first call | 292 | 143 | 1761 | 420 |
| `maintenance_due`, repeated, nothing new | 267 | 0.10 | 1950 | **0.07** |
| `maintenance_due` after one new record | 291 | 38 | 2082 | 103 |
| file size | 49.6 MB | 21.2 MB | 197.5 MB | 83.9 MB |

`maintenance_due` answers are identical before and after (`due`, `new_records`, `signal`, `since_seq`); reconstruct
returns 12 handles in both. The machine is shared: absolute numbers move by up to 2x between runs (the audit's
baseline measured reconstruct 20k at 8.4 s, an earlier run of this script 4.1 s); before and after were run back
to back. ADR 0003 targets: subject+owner sub-millisecond at 50k (0.33 ms), reads without vectors do not fetch the
embedding column (projection, plan tests), vector query at 50k under 100 ms from the cache (1.4 ms; the first query
of a handle builds the matrix, 0.44 s), `maintenance_due` bounded (a repeated check reads nothing; a check after new
records reads those rows plus the journal's formation bindings).

### Remaining hot spots (follow-up)

1. `folds.py:127` `binding_states` loads every binding of the pair through `SQLiteJournal.bindings`
   (`journal_sqlite.py:302`, `row_to_binding` at `journal_sqlite_rows.py:190`) and folds them in Python on every
   reconstruct: ~85 % of a 20k reconstruct (0.20 s of 0.24 s in the profile). Needs a journal-side folded-binding
   read (latest per key, SQL) or `bindings(after_seq=)` for an incremental fold: journal API change (journal owner;
   out of this slice, which does not touch `journal*.py`).
2. `sleep_cadence.py:69` `_remember_seqs`: `maintenance_due` after new formations re-reads all raw bindings of the
   pairs (~100 ms at 20k) for the same reason; `bindings(after_seq=)` makes it O(new).
3. `limit=0` scope scans (62 call sites, audit hot spot 4): projection made them ~5x cheaper but they stay O(life)
   (0.5 s at 50k, dominated by `_row_to_assertion` JSON parsing, `sqlite_store.py:953`).
4. Scope as-of with a limit (`sqlite_store.py:661` `_structured_sql`): walks the partition newest-first past the
   rows observed after the as-of point (22 ms at 50k); an index or a seek on `valid_from` would bound it.
5. Matrix build on a handle's first semantic query (0.44 s at 50k, `sqlite_store.py:709`): a host that wants the
   first recall fast can issue one semantic query at load.
6. Opening a store scans the rows written since the previous open for the upgrade cursor
   (`sqlite_store.py:258`; 30 ms for 50k new rows), once per process start.
7. LanceDB (audit hot spot 8) and formation throughput (hot spot 9) are untouched.

