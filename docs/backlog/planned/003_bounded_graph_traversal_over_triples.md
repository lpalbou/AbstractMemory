# 003 - Bounded Graph Traversal Over Triples

**Status**: Planned  
**Date**: 2026-05-05  
**Priority**: High  
**Components**: abstractmemory query helpers, SQLite/LanceDB/InMemory stores

## Summary

Add a deterministic graph traversal helper over existing triples. This would let
Runtime/Flow ask for a bounded neighborhood around entities or memory records
without importing a graph database and without making AbstractMemory responsible
for active prompt construction.

## Design Signal

Graph traversal is useful only when it is explicit and bounded:

- graph walk improved recall but lowered precision when used indiscriminately;
- source expansion must track visited nodes, depth, tokens, and stop reasons;
- cycles must be protected;
- broad traversal should be an effort escalation, not a default query path.

## ADR Constraints

- Memory recall levels require graph traversal budgets: max hops, max expanded
  nodes, and explicit warnings/partial results.
- ADR-0009 keeps provenance-based recall separate from active context.
- ADR-0025 prefers append-only reconciliation and query-time rewriting over
  destructive edits.

## Proposed Shape

Provide a small traversal API, either as a helper function or a protocol
extension:

```python
walk_triples(
    store,
    seeds=[...],
    predicates=[...],
    scope="session",
    owner_id="...",
    max_hops=1,
    max_edges=100,
    active_at=None,
)
```

Return a structured result with:

- matched assertions;
- path/depth metadata;
- visited subjects/objects;
- truncated/partial flags;
- warnings when budgets stop traversal.

Start with a store-agnostic implementation that repeatedly calls
`TripleStore.query(...)`; later optimize SQLite with recursive CTEs if tests show
the generic approach is too slow.

## In Scope

- Bounded one-hop and multi-hop traversal over `subject`/`object` links.
- Predicate allowlists.
- Scope/owner/time filters carried through every hop.
- Deterministic ordering and cycle protection.
- Basic tests for all stores that support structured query.

## Out Of Scope

- Automatic graph expansion during ordinary `query(...)`.
- LLM-driven traversal decisions.
- Cross-scope broad recall policy.
- Community detection or clustering.

## Acceptance Criteria

- A traversal with cycles terminates deterministically.
- A traversal that hits `max_hops` or `max_edges` reports a warning/partial
  result.
- `SQLiteTripleStore`, `InMemoryTripleStore`, and `LanceDBTripleStore` produce
  compatible results for structured traversal.
- Semantic/vector ranking remains separate from graph traversal.
