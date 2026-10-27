# A notes and diary layer on top of the graph, shared by AbstractNote and AbstractEntity

Created: 2026-10-27 (operator ruling, [ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md)).
Track: `knowledge_graph_convergence` · Priority: Medium · Status: Planned

## Summary
A thin public abstraction over the graph for "a note": a dated text with attachments and links, whose
knowledge (entities, claims, topics) is extracted into the graph with provenance back to it, and which can be
recalled, revised and connected. The same abstraction serves AbstractNote's notebook and AbstractEntity's
diaries and notes to self.

## Why
Persistent agents write diaries and leave notes for themselves; AbstractNote's abstractions for notes are
useful to them too (operator, 2026-10-27). Built once over the graph, both apps get the same recall,
then-versus-now and ripple behaviour over what was written.

## Current code reality
- AbstractMemory: `diary.py` (diary entries with a hash chain, `verify_diary_chain`, open ideas/questions/
  problems/commitments and triggered commitments), `records.py` (formation), `archive_import.py` (dated markdown
  lineage archives). Diaries are agent records; there is no general note record with attachments, links and
  extraction provenance.
- AbstractNote (prior art): `model.py`, `store/notes.py` (notes, attachments, links), `ingest/` (capture,
  normalise, dates, extract, blobs), `importers/` (Markdown, Claude sessions, agora). Capture and importers stay
  AbstractNote's (ADR 0002 decision 6); the note record and its provenance into the graph are what moves.

## Scope
In: the note record and its links to graph records; extraction into the graph through an injected reader using
0050/0051; diary entries expressed as notes without breaking the hash chain. Out: capture UX, importers, the
gateway routes.

## Dependencies
0050, 0051, 0052.

## Validation
The same fixture written as an AbstractNote note and as an AbstractEntity diary entry yields the same entities
and claims with provenance; `verify_diary_chain` stays green on existing diaries.
