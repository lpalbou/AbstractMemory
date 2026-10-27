# Document-knowledge retrieval: search, expansion, timelines, then-versus-now, change feed

Created: 2026-10-27 (operator ruling, [ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md)).
Track: `knowledge_graph_convergence` · Priority: Medium · Status: Planned

## Summary
Reads any consumer needs over the graph: hybrid search (full-text + vector, rank-fused) with filters and facets
and an `as_of`; graph expansion (entity cards as of a moment, claim and relation timelines, neighbours, the
evidence chain of a claim); then-versus-now (earliest and latest understanding and the turning points, in history
order); a system-time change feed with a lossless cursor; the as-received view (what the archive held on a date);
an embedding cache keyed by text hash and model, and an incremental vector index.

## Why
These are the reads that make a graph useful to a person or an agent, and they are generic. AbstractEntity
needs then-versus-now about the people it knows as much as AbstractNote needs it about documents.

## Current code reality
- AbstractMemory: channels (exact, keyword over FTS5, vector) and spreading activation for agent recall
  (`channels.py`, `spreading.py`, `probe.py`, `reconstruct.py`), embedding pins (`embedding_pin.py`, `reembed.py`),
  `recall_reads.py`, entity and world-model cards. No faceted search API, no claim timelines, no then-versus-now,
  no change-feed cursor, no as-received axis, no embedding cache by text hash.
- AbstractNote (prior art): `recall/search.py` (FTS5 BM25 + cosine, RRF, facets, `as_of`), `recall/expand.py`,
  `recall/then_now.py` (cached per entity revision count), `recall/changes.py` (cursor of high-water second plus
  items returned at that second), `store/archive.py` (as-received), `store/embeddings.py` (`VectorCache`),
  `store/vector_index.py`.

## Scope
In: the reads above as public API over the store and revision log (0051), deterministic, no model call except
one embedder call for a query vector. Out: HTTP routes (AbstractGateway), landing/cue-card wording (consumer).

## Dependencies
0051 (timelines and then-versus-now read the revision log), 0050 (entity cards).

## Validation
Scenario tests ported from AbstractNote's recall tests, run against AbstractMemory's public API; a change-feed
test proving nothing lost or repeated across calls at one second; as-of and as-received tests with an import
whose own dates are older than its arrival.
