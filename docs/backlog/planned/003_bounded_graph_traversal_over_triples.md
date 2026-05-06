# Planned: Bounded graph traversal over triples

## Metadata

- Created: 2026-05-05
- Status: Planned
- Completed: N/A
- Priority: High
- Components: TripleQuery helpers, store capability metadata, tests, docs

## Context

AbstractMemory already stores assertions in a graph-shaped form:

```text
subject --predicate--> object
```

Structured queries can find exact triples, but callers cannot yet ask for a
bounded neighborhood around an entity, claim, summary, lesson, or episode. That
neighborhood is important for provenance-first recall and for source expansion,
but it must be explicit and budgeted.

## Current code reality

- `TripleAssertion` stores `subject`, `predicate`, `object`, `scope`,
  `owner_id`, time fields, `provenance`, and `attributes`.
- `TripleQuery` supports exact structured filters and time filters.
- No store exposes graph traversal or path metadata.
- In-memory and SQLite can perform deterministic structured filtering directly.
- LanceDB structured filtering is available but may fetch/sort rows in Python
  for deterministic non-semantic ordering.
- There is no assertion id in query results except what callers store in
  `provenance` or `attributes`.

Re-check the current store APIs before implementation. The traversal API should
not assume a private table schema unless a store explicitly advertises native
support.

## Problem

Future recall workflows need to expand from a seed to connected evidence while
staying understandable:

- follow only allowed predicates;
- stay within scope/owner/time bounds;
- prevent cycles;
- stop at max hops, max edges, max nodes, or token budget;
- explain which paths were included and why traversal stopped.

If graph expansion is hidden inside ordinary `query(...)`, it will be hard to
audit and easy to over-recall noisy context.

## What we want to do

Add a deterministic, bounded traversal helper over existing triples. Start with
a store-agnostic implementation that repeatedly calls `TripleStore.query(...)`.
Allow future stores, especially SQLite, to advertise a native optimized
implementation later.

## Why

Bounded traversal is the smallest reusable graph-memory concept that belongs in
AbstractMemory itself. It is storage/query behavior, not prompt policy. Higher
packages can use it for recall, observer views, or evidence expansion while
keeping active-memory selection outside this package.

## Requirements

- Traversal must be opt-in; ordinary `query(...)` remains exact structured
  query.
- Inputs must include:
  - seed terms;
  - direction (`out`, `in`, or `both`);
  - optional predicate allowlist;
  - `scope` and `owner_id`;
  - optional `since`, `until`, and `active_at`;
  - max hops;
  - max edges;
  - max nodes;
  - optional token/weight budget if available.
- Every hop must apply the same scope/owner/time filters.
- Results must include:
  - assertions;
  - path/depth metadata;
  - visited node ids/terms;
  - budget counters;
  - partial/truncated flags;
  - stop reason;
  - warnings.
- Cycles must terminate deterministically.
- Ordering must be stable across runs given the same store contents.
- Semantic/vector ranking must remain separate from traversal.

## Suggested implementation

Define small result types in a helper module, for example:

```python
@dataclass(frozen=True)
class GraphWalkRequest:
    seeds: tuple[str, ...]
    direction: str = "both"
    predicates: tuple[str, ...] = ()
    scope: str | None = None
    owner_id: str | None = None
    max_hops: int = 1
    max_edges: int = 100
    max_nodes: int = 100
    active_at: str | None = None

@dataclass(frozen=True)
class GraphWalkResult:
    assertions: tuple[TripleAssertion, ...]
    paths: tuple[GraphWalkPath, ...]
    visited_terms: tuple[str, ...]
    partial: bool
    stop_reason: str
    warnings: tuple[str, ...]
```

Start with a breadth-first search:

1. Canonicalize seed terms using the same term canonicalization as assertions.
2. Query outgoing edges by `subject=<frontier term>`.
3. Query incoming edges by `object=<frontier term>` when direction allows it.
4. Filter predicates after canonicalization.
5. Add newly reached terms to the next frontier.
6. Stop when hop, edge, node, or optional token budgets are reached.

After planned item 002 adds capabilities, mark the generic implementation as
`graph_walk="generic"` and leave room for SQLite `graph_walk="native"` using
recursive CTEs.

## Scope

- Public or semi-public helper API for bounded traversal.
- Generic implementation over the existing `TripleStore.query(...)` protocol.
- Tests covering in-memory and SQLite by default.
- Optional LanceDB tests when the dependency is installed.
- Docs explaining traversal vs semantic search.

## Non-goals

- No automatic graph expansion during `TripleStore.query(...)`.
- No LLM-driven traversal decisions.
- No active prompt packing.
- No cross-scope recall policy.
- No graph database dependency.
- No clustering, centrality, PageRank, or community detection.

## Dependencies and related tasks

- AbstractFramework central ADRs:
  - `0007-active-context-and-memory-provenance.md`
  - `0009-connected-memory-recall-and-provenance.md`
  - `0025-kg-entity-normalization-and-dedup.md`
  - `0026-truncation-policy-and-contract.md`
- Related planned work:
  - `001_semantics_aligned_memory_record_conventions.md`
  - `002_sqlite_database_compatibility_and_store_capabilities.md`
  - `004_recall_trace_and_access_events_contract.md`
  - `007_read_only_memory_observer_contract.md`

## Expected outcomes

- Hosts can ask for a small connected subgraph around a memory record or entity.
- Traversal results are explainable and budgeted.
- Cycles and high-degree nodes cannot explode result size silently.
- The same helper works with all structured stores, with optional native
  acceleration later.

## Validation

A-level:

- Test one-hop outgoing, incoming, and both-direction traversal.
- Test predicate allowlists.
- Test scope/owner filters on every hop.
- Test cycle termination.
- Run `python -m pytest -q`.

B-level:

- Test `max_hops`, `max_edges`, and `max_nodes` stop reasons.
- Test deterministic ordering with ties.
- Test SQLite and in-memory result compatibility for the same fixture.

C-level:

- Test optional LanceDB structured traversal when LanceDB is installed.
- Add a fixture with summary -> source -> claim -> evidence records after item
  001/005 conventions exist.
- If native SQLite traversal is added, compare native and generic outputs.

## Progress checklist

- [ ] Re-check current query semantics and canonicalization.
- [ ] Define request/result dataclasses.
- [ ] Implement generic breadth-first traversal.
- [ ] Add budget and warning handling.
- [ ] Add tests for cycles, filters, ordering, and budget stops.
- [ ] Document traversal separately from semantic/vector search.
- [ ] Update capability metadata if item 002 has landed.

## Guidance for the implementing agent

Keep traversal small and explicit. A graph walk is a retrieval primitive, not a
memory policy. If you are tempted to rank, summarize, or decide prompt
visibility, stop and move that concern to Runtime/Flow/Agent backlog instead.
