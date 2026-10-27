# Self-organisation: communities, topics, consolidation, reflection, review

Created: 2026-10-27 (operator ruling, [ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md)).
Track: `knowledge_graph_convergence` · Priority: Medium · Status: Planned

## Summary
The passes that let a graph structure itself: community detection (deterministic, seeded) and their naming
through an injected reader; topic normalisation (one spelling per topic); consolidation stages for document
knowledge (merge duplicates, recompute communities, label, refresh stale summaries); deterministic reflection
candidates with provenance and the insight records they produce; the review list of disagreements and uncertain
matches.

## Why
Self-organisation is what makes AbstractMemory a memory rather than a store. Its sleep passes tend agent memory;
AbstractNote built the document-knowledge equivalent. One set of passes should serve both, scheduled by the host.

## Current code reality
- AbstractMemory: `consolidation.py` (`sleep_pass`, `consolidation_pass`, `dream_pass`: deterministic, zero model
  calls, components, duplicates), `maintenance.py`, `sleep_cadence.py`, `sleep_policy.py`, `dream_resolution.py`,
  `redigestion.py`, `doctoring.py` (dedup, verify), `candidate_miner.py`, `tend.py`. No communities, no topic
  records, no summary refresh, no insight records with provenance.
- AbstractNote (prior art): `recall/communities.py` (Louvain via `networkx`, fixed seed, weights from statements
  and co-mentions), `store/topics.py`, `recall/consolidation.py` (staged `note-consolidate`), `recall/reflect.py`
  (rules with explicit thresholds and repeat guards), `recall/insights.py`, `recall/review.py`.

## Scope
In: the passes as AbstractMemory functions with budgets and recorded results, reader injected where judgement is
needed, wired into the existing maintenance cadence (`maintenance_due`). Out: scheduling (the host's runtime),
prompt wording. Decide in this item whether `networkx` becomes an optional extra (AbstractMemory is
dependency-light).

## Dependencies
0050, 0051, 0052. Ripples triggered by consolidation go through 0054.

## Validation
Seeded community detection is stable across runs; a consolidation pass over a fixture graph produces recorded
stages and respects its budget (nothing dropped silently, root ADR-0026); reflection candidates carry their rule
and provenance; mutation tests per rule.
