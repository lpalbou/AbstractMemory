# Ledger provenance contract and the revision log (`abstractmemory.graph`)

Created: 2026-10-27 (operator goal 2026-10-27, [ADR 0003](../../../adr/0003-one-graph-ledger-provenance-and-revisions.md)).
Track: `knowledge_graph_convergence` · Priority: High · Status: In progress (first slice landed on
`feat/memory-graph-provenance`, 0.4.0 unreleased; see "Report")

## Summary
The first concrete slice of ADR 0003: a typed, mandatory provenance contract (`SourceRef`, `Provenance`,
`ProvenanceRequired`), an append-only revision log whose ops apply atomically over the SQLite home (and the in-memory
store), closures that carry their cause and successor, `narrow_assertion` as the `narrow` op, the reads `history`,
`sources_of`, `derived_from_source` and the lossless change feed `revisions(after=)`, and replay of the log into an
empty store. Delivered as the new sub-package `abstractmemory.graph` plus `narrow_assertion` on the stores.

## Why
Nothing in a mind points back to the ledger today (audit 2026-10-27: 0 of 21,951 notebook triples carry a run id;
entity records carry `run_id`/`turn_id` only; passes write `{source, actor}`; closures have no provenance), and
`close_assertion` is an unjournaled in-place update that AbstractNote complements by writing the private table.
The operator requires every derived memory to be tied to ledger messages, events and artifacts so the verbatim
source of any understanding can be reconstructed. This is also 0051's revision log and the `narrow_assertion` of
`ripple_wave/0001`; implement once, close all three.

## Current code reality
- `models.py`: `TripleAssertion.provenance` is a free dict, unvalidated, stored as JSON text, not queryable.
- `sqlite_store.py:530` `close_assertion` (in place, unjournaled); `in_memory_store.py` same; `lancedb_store.py` none.
- `journal.py:225-266` `ClosureRecord(kind, reason, replacement_ids, actor, provenance)` with no scope/owner and no
  cause fields; `system.py:848-897` `close_assertions`/`close_record` take no provenance.
- Runtime writers: `seam_handlers.py:484-486` (`run_id`, `turn_id`), `effect_handlers.py:300-306` (`writer_run_id`),
  `identity_support.py:165,229` (diary `entry_id` + origin).
- AbstractNote prior art: `store/notes.py` revision rows and `_OpContext.apply`; `store/kg.py:120-218` projection and
  the private narrow.

## Scope
In:
- `abstractmemory/graph/provenance.py`: `SOURCE_KINDS`, `SourceRef` (dict in/out, `key()`, per-kind required ids,
  optional `runtime_id`), `Provenance(sources, derived_from, actor, reader, reason, extra)`, `ProvenanceRequired`.
- `abstractmemory/graph/revisions.py`: `RevisionOp`, `Revision`, `REVISION_CAUSES`, ops `assert` / `close` / `narrow`
  in this slice (entity and alias ops arrive with 0050).
- `abstractmemory/graph/graph.py`: `MemoryGraph(store, journal)` with `apply_revision` (validation; one SQLite
  transaction covering triples, closure, revision row, provenance and history rows; idempotent on `revision_id`),
  `history(memory_id)`, `sources_of(memory_id, transitive=)`, `derived_from_source(ref)`, `revisions(after=, limit=)`,
  `replay_into(target_graph)`.
- Tables in the home file: `memg_revisions`, `memg_provenance`, `memg_derivations`, `memg_history` (names and
  columns in `api.md`).
- `narrow_assertion(assertion_id, valid_until) -> bool` on `SQLiteTripleStore` and `InMemoryTripleStore` (refuses to
  widen; `LanceDBTripleStore` raises `NotImplementedError` naming 0057).
- Docs: `api.md`, `memory-system.md` ("Time axes", "Provenance"), CHANGELOG, llms-full regenerated.
Out: the entity registry (0050), retrieval reads (0052), the runtime facade (AbstractRuntime), routes (gateway).

## Dependencies
None to start. 0050-0055 build on it. Supersedes the revision-log half of 0051 and the `narrow_assertion` item of
`ripple_wave/0001` (closure causes there become the `close` op's cause fields).

## Validation
ADR 0003 "Validation" unit list with its mutant list in `tests/test_graph_provenance.py` and
`tests/test_graph_revisions.py`; the end-to-end on a temporary SQLite home in `tests/test_graph_e2e.py` (two
consumers, no mocks); the before/after benchmark numbers for provenance lookups quoted in the completion report.

## Report

### Slice 1 (2026-10-27, branch `feat/memory-graph-provenance`, version 0.4.0 unreleased)

What landed:
- `abstractmemory.graph`: `SourceRef` / `SOURCE_KINDS` / `InvalidSourceRef`, `Provenance` (+ `from_legacy`) /
  `ProvenanceRequired`, `Revision` / `RevisionOp` / `RevisionResult` / `REVISION_CAUSES` / `CLOSE_KINDS`, and
  `MemoryGraph` with `apply_revision`, `history`, `sources_of`, `derived_from_source`, `revisions(after=)`,
  `replay_into`, `repair`; the four `memg_*` tables in the home file. Contract names as in
  `untracked/memory-transition/contract.md` §1-§4.
- `narrow_assertion` on the SQLite and in-memory stores (9818c79); `NotImplementedError` on LanceDB (0057).
- `CLOSURE_KINDS` gains `merged`; `SQLiteJournal._append_closure_on` lets the closure ride a caller-owned
  transaction on the same file.
- Rules the graph enforces beyond the shape check: a `derived_from` chain must reach a ledger source (cycles,
  self-derivation and chains to nothing refused); a store row written outside the graph is adopted only by an
  `import` / `migration` revision carrying it as stored (provenance rewritten to the graph shape, the old one kept in
  the history); `close` / `narrow` refuse rows the graph never adopted and ids named before the op that asserts
  them; a memory is closed once, and a close of a bounded window keeps the window but still writes the closure (a
  retracted "until June" claim leaves ranked retrieval); a refused revision leaves no embedding pin behind (the
  first-write pin is written inside the transaction).
- Docs: `api.md` (graph section, tables, measured costs), `memory-system.md` ("Time axes", "Provenance"), README,
  `stores.md`, `architecture.md`, `faq.md`, `llms.txt`, `llms-full.txt`; CHANGELOG 0.4.0.

Tests (mutants listed in each file's docstring, each applied by hand and seen red):
- `tests/test_graph_provenance.py` (45), `tests/test_graph_revisions.py` (45, on three deployments: SQLite with the
  journal in the same file, SQLite with the journal in another file, in-memory), `tests/test_graph_e2e.py` (1: two
  consumer-shaped clients on their own connections to one temporary home), `tests/test_graph_performance.py` (4:
  every keyed read's `EXPLAIN QUERY PLAN`, and graph-written rows served by the 0058 vector matrix), with
  `tests/test_narrow_assertion.py`: 106 passed.
- Full suite: 1249 passed, 4 skipped before merging `feat/memory-graph-performance` (0058); 1297 passed, 4 skipped
  after (main: 1148 passed).

Performance (`tests/bench/bench_graph.py --size 50000`: a temporary SQLite home, 50,000 assertions written only
through `apply_revision` in 10,000 revisions, 999 supersede closes, a tenth derived memories; no embedder; 200
lookups per row, macOS, Python 3.12). "Before" is the only provenance lookup a 0.3 home had, a scan of every row's
provenance JSON:

| read @ 50,000 assertions | median ms | p95 ms | rows |
|---|---:|---:|---:|
| `derived_from_source(step)` | 0.051 | 0.065 | 6 |
| `derived_from_source(run)` | 0.773 | 0.904 | 128 |
| `sources_of` (sourced memory) | 0.043 | 0.047 | 2 |
| `sources_of` (derived memory, transitive) | 0.102 | 0.115 | 4 |
| `history(memory)` | 0.022 | 0.028 | 1 |
| `revisions(after=cursor, limit=100)` | 4.043 | 4.484 | 100 |
| `apply_revision` of a revision already applied | 0.106 | 0.123 | 1 |
| before: `provenance_json LIKE` scan by run | 18.467 | 20.009 | 100 |

Build: 1016 revisions/s (5078 assertions/s). With `--embed` (384-d fake embedder, after merging 0058's float32 BLOB
vectors: the graph writes its rows with `encode_vector`): 950 revisions/s, the same lookups within 10%, and a vector
query (limit 20) over the 50,000 graph-written rows served by the matrix cache in 1.18 ms median
(`vector_engine == "numpy-matrix-cache"`). Every keyed read is an index search at that size (the bench asserts the
plans of `tests/test_graph_performance.py`; the change-feed page is dominated by decoding and re-validating each
logged revision).

### Adversarial review (2026-10-27): SHIP WITH FIXES, fixed on the branch

One commit per finding, each with tests and its mutants (listed in the test docstrings):
- M1 (blocker): a close ends the row at min(current end, the close), compared as instants, so a claim "valid until
  December" retracted in March leaves `TripleQuery(active_at=June)` too; history records `previous_valid_until`.
- M2: every time of a revision is parsed and normalized at op construction ("next tuesday" refused); a close or
  narrow before `valid_from` is refused (whole revision rolls back).
- M3: `narrow_assertion` (both stores) compares instants, not strings. Canonical form: the package's existing UTC
  text form (`journal_common.normalize_iso_ts`: microseconds, `+00:00`), not `Z`: `Z` sorts after both `+` and `.`,
  so a `Z` value would mis-order against every stored `utc_now_iso_seconds` value and every `+00:00` query.
- M4: the JSON->BLOB vector rewrite is documented as a one-way migration (CHANGELOG); a 0.4.0 home declares
  `vector_encoding = float32-blob` in its meta table.
- M5: `SYNTHETIC_RUN_ID_PREFIXES` / `is_synthetic_run_id`: a `run`/`step` ref naming a synthetic run id is refused;
  `from_legacy` never lifts one into a ref.
- M6: a different claim under an id the graph holds is refused (identity: terms, scope, owner, `valid_from`); an
  identical re-assert stays a reported skip.
- M7: a close/narrow-only revision must name a source or a memory other than the ones it changes.
- M8: an adoption is logged with its previous provenance (`adoption` on the assert op), so a replay reproduces it.
- M9: `revisions(after=)` refuses a cursor beyond the log's head.
- M11, M14: docs (passes write `derived_from` as the track lands; the 0.3 scan baseline is 18 ms vectorless / 38 ms
  with vectors).
- M13: opening a graph on a home whose tables exist runs no DDL transaction (a reader does not wait for a writer).
- R8 (runtime review): `from_legacy` reads the mixed shape the runtime stamps (flat keys + `sources`).
- M10, M12, M15: notes, left as they are by the lead's decision (see the review).
- The reviewer's informational probes that pinned the old behaviour (`test_cursor_from_another_graph_is_silently_
  accepted`, `test_revision_derived_from_grounded_only_by_close`, `test_diary_run_id_direct_ref_accepted`,
  `test_close_before_valid_from_inverts_window`) now fail by design: those inputs raise.
- After the fixes: graph tests + narrow + marker 133 passed; full suite 1324 passed, 4 skipped.

Re-measured 2026-10-27 15:20 after the review fixes (`bench_graph.py --size 50000`, generator now writes strictly
increasing timestamps so supersede closes never precede the claim's valid_from), on a contended machine (load
average 10): `derived_from_source(step)` 0.078 ms, by run 1.13 ms, `sources_of` 0.061 / 0.138 ms (transitive),
`history` 0.033 ms, a change-feed page of 100 revisions 8.1 ms, a replayed revision 0.22 ms, and the untouched 0.3
baseline scan 24.5 ms (18.5 ms in the first run): the untouched baseline moved 1.3x, so most of the movement is load.
The one real cost added by the fixes is timestamp normalization when a logged revision is decoded: measured A/B in
one process, 50.9 us vs 43.6 us per 5-claim revision (+17%, about 0.7 ms per page of 100). The first table stays the
reference figure; every read is still an index search (the bench asserts the plans).

### Architect review (Fable, 2026-10-27): clear changes, each its own commit with tests and mutants

- A3: record time is the store's (`apply_revision` stamps `recorded_at` under the write lock; `replay=True`, used
  by `replay_into`, keeps the logged value). A5: a revision already in the log returns its logged outcome (ids read
  back through a new `(revision_id, seq)` history index). A4: `SourceRef.digest` (sha256 hex beside the address).
  A7: every memory is also indexed by the sources of the revision that wrote it (`via`), so a lineage-only memory is
  found from its producing step; `sources_of(labelled=True)`. A6: `repair()` documented as off-file only.
- B3: `derived_from` never crosses `owner_id` (other owners' knowledge enters as a source). B6:
  `names_ref(ref, owner_ids)`, the owner gate in one covering-index probe (`memg_provenance.owner_id`,
  denormalized and backfilled; `(ref_key, owner_id)` / `(run_id, owner_id)` indexes): at 1201 memories naming one
  artifact, the last one's owner is allowed in one probe.
- C1: opening a home is a read (store, journal and graph take no write lock on an up-to-date home; cursors kept
  current by every insert path; the encoding marker written by the first write). C2: the matrix reserves its rows
  at a build and grows by at most 10 %; 100k x 1024 holds 424 MB (552 MB before), build peak 460 MB (833 MB).
  The old matrix was already freed before a rebuild allocated (proved with a weak reference); the 2.35 GB RSS was
  the high-water mark of doubling growth copies.
- E1: re-observation, not duplication (an open assert of a held open claim adds sources, no second row).
- After the batch: full suite 1347 passed, 4 skipped.

Open (next slices): `as_of` / `as_recorded` reads (0052); entity and alias ops (0050); the runtime facade that stamps
step refs and reconstructs sources (AbstractRuntime ADR 0009); the gateway routes; AbstractNote and the runtime's
writers moving onto `apply_revision`; the LanceDB plane store (0057).
