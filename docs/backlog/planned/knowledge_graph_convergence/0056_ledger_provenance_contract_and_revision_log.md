# Ledger provenance contract and the revision log (`abstractmemory.graph`)

Created: 2026-10-27 (operator goal 2026-10-27, [ADR 0003](../../../adr/0003-one-graph-ledger-provenance-and-revisions.md)).
Track: `knowledge_graph_convergence` · Priority: High · Status: Planned (first slice in progress on
`feat/memory-graph-provenance`)

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
