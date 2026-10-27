# One mind per plane: the SQLite home store, LanceDB optional, the plane store imported once

Created: 2026-10-27 ([ADR 0003](../../../adr/0003-one-graph-ledger-provenance-and-revisions.md) decisions 2-3).
Track: `knowledge_graph_convergence` · Priority: High · Status: Pending decision; comparison in
`abstractframework/untracked/memory-transition/report.md` decision 2 (operator, 2026-10-27: not taken, "we never
migrate to migrate"; options named in [ADR 0003](../../../adr/0003-one-graph-ledger-provenance-and-revisions.md)
decision 3: SQLite as written, a SQLite graph/provenance/revision store with LanceDB kept for vectors and multimodal
embeddings, or LanceDB behind the same `MemoryGraph` interface). Do not start before the decision.

## Summary
Make the SQLite home store the record of truth of a plane's mind (`<plane>/abstractmemory/memory.sqlite3`: triples,
journal, revision log, provenance index in one file), demote LanceDB to an optional vector accelerator over the same
ids, and import the existing LanceDB plane store (run/session/global scopes) once. The gateway's plane default
changes accordingly (its item), the notebook's private `kg.sqlite3` and note index fold into the plane mind (AbstractNote
0033/0037), entity homes keep their own file (same implementation).

## Why
Three stores per account today (audit 2026-10-27); the LanceDB plane store fails the contracts the graph needs (no
`close_assertion`, duplicate ids accepted, schema guessed from the first write so `active_at` errors on some homes,
7 s for "latest 100 in scope" at 50k rows). One home file is what makes a revision atomic (ADR 0003 decision 6).

## Current code reality
- `lancedb_store.py` (288 lines): `add`/`query`/`close` only; gateway default `<plane>/abstractmemory/kg`
  (`abstractgateway/memory_store.py:81-98`).
- `sqlite_store.py`: the home store used by entities and by AbstractNote's projection.
- `abstractnote/store/kg.py:23`: opens its own `SQLiteTripleStore` on `kg.sqlite3`.

## Scope
In: a `open_mind(path)` constructor returning the graph over one file; an importer from a LanceDB store (ids kept,
provenance `{"kind":"run","run_id":...}` derived from the existing `writer_run_id`, `cause: migration`); an optional
`VectorIndex` protocol with a LanceDB implementation keyed by assertion id; docs. Out: the gateway code change (its
item), the notebook projection (AbstractNote 0037).

## Dependencies
0056. Operator decision on the gateway default and on the import of existing plane stores.

## Validation
A plane store imported into a home answers the same `TripleQuery` set; `active_at` works on a home whose first row had
no `valid_until`; a LanceDB-less install loses only vector acceleration (labelled), nothing else.
