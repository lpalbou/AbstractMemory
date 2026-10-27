# Claim lifecycle and revision log

Created: 2026-10-27 (operator ruling, [ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md)).
Track: `knowledge_graph_convergence` · Priority: High · Status: Planned

## Summary
Make a claim (a statement about entities with a validity window and provenance) a first-class, revisable record
in AbstractMemory, and keep an append-only revision log: every change to entities or claims is one revision with
its cause (the source note or memory), its operations and its time, so the graph can be replayed, explained and
rebuilt. Expose the window operations publicly, starting with `narrow_assertion(assertion_id, valid_until)`.

## Why
AbstractNote's ADR 0003 made its revision log the truth and AbstractMemory a projection, because AbstractMemory
had no revision log. ADR 0002 reverses the direction: the log belongs to the graph. `narrow_assertion` is the
smallest piece and the most urgent one: without it AbstractNote writes AbstractMemory's private table.

## Current code reality
- AbstractMemory: `TripleAssertion` with `valid_from`/`valid_until`, append-only stores, `close_assertion`
  (`sqlite_store.py`) and closure records (`retract`, `supersede`, `reinterpreted`); the journal records
  attention and valence events. No revision log grouping operations under one cause; no public way to move an
  already-closed window earlier.
- AbstractNote (prior art): `store/notes.py` (`NoteStore.project`: the only code that changes entities, aliases,
  claims and relations, applying a revision), `store/notebook.py` (one revision log, rebuildable index),
  `process/revise.py` (Extraction + Linking → revision ops), `store/kg.py` (the projection, including the private
  `store._table`/`_conn`/`_lock` write that narrows a window).

## Scope
In: revision records (id, cause, ops, recorded/occurred time) over the store and journal; claims with provenance
to their source; `narrow_assertion` (additive, both backends); replay of the log into a fresh store; docs.
Out: the extraction prompt and its schema (consumer framing).

## Dependencies
None to start. `narrow_assertion` can ship alone first (also listed in `proposed/ripple_wave/0001`; implement it
once, close both).

## Validation
Replay test: a log replayed into an empty store yields the same graph; `narrow_assertion` refuses to widen a
window and is visible in history; a scan of AbstractNote for `_table`/`_conn`/`_lock` returns nothing once its
item 0034 closes; mutation tests per operation.
