# Planned: Deterministic anchors and facet indexing

## Metadata

- Created: 2026-05-05
- Status: Planned
- Completed: N/A
- Priority: Medium
- Components: query helpers, store capability metadata, AbstractSemantics-aligned metadata

## Context

Semantic/vector search is useful, but it is not always the best first recall
step. Many memory questions have concrete anchors: entity ids, file paths,
commands, ADR ids, backlog ids, model/provider names, source URLs, predicates,
or registry entity types.

AbstractMemory can provide deterministic anchor/facet helpers that higher
layers use before escalating to semantic search or graph traversal.

## Current code reality

- `TripleQuery` supports exact subject/predicate/object, scope/owner, and time
  filters.
- Stores preserve `provenance` and `attributes`, including
  `attributes.subject_type`, `attributes.object_type`, evidence quotes, and
  original context.
- There is no normalized anchor extraction or facet index.
- SQLite has no FTS or explicit keyword API yet.
- LanceDB vector search is optional and should remain separate from anchor
  scoring.

Re-check planned item 002 before implementing this item. Capability metadata may
change the best place to expose anchor/facet support.

## Problem

If recall starts with only vector search or broad graph traversal:

- exact known ids may be missed or buried;
- high-frequency generic topics may dominate;
- hosts cannot easily explain why a candidate surfaced;
- in-memory/SQLite users lack a deterministic retrieval primitive between exact
  query and semantic search.

At the same time, anchors must not become unverified facts.

## What we want to do

Prototype deterministic anchor and facet scoring over existing triples and
metadata. Return ranked candidates with explanation cues, without mutating the
store and without making anchors prompt-visible by default.

## Why

Anchor/facet search is cheap, auditable, and dependency-light. It supports
urgent/standard recall paths and gives graph traversal better seeds while
keeping deep recall explicit.

## Requirements

- Respect `scope` and `owner_id` before scoring.
- Keep anchor extraction deterministic.
- Treat anchors as retrieval cues, not durable truth.
- Use AbstractSemantics metadata where available:
  - predicates;
  - `attributes.subject_type`;
  - `attributes.object_type`;
  - labels from `schema:name`, `skos:prefLabel`, `skos:altLabel`;
  - topics from `schema:about`, `schema:mentions`, `dcterms:subject`.
- Consider bounded provenance facets:
  - source path;
  - source URL;
  - artifact/span id;
  - command;
  - provider/model;
  - route/tool id.
- Return explanation data:
  - cue type;
  - normalized cue;
  - matched assertion ids or stable source references;
  - direct vs co-occurrence match;
  - score contribution.
- Avoid unbounded generic cues. Provide stopword/min-length/max-frequency
  guards.
- Do not write anchors as assertions unless a separate derived-lineage workflow
  explicitly persists them with source evidence.

## Suggested implementation

Start as a helper module, not a store schema change:

```python
rank_by_anchors(
    assertions: Iterable[TripleAssertion],
    query_terms: Iterable[str],
    *,
    scope: str | None = None,
    owner_id: str | None = None,
    max_results: int = 20,
) -> AnchorRankResult
```

For store-backed usage, provide a wrapper that first runs a bounded structured
query by scope/owner/time, then ranks the returned assertions.

Scoring can begin simply:

- exact subject/object/predicate match: high score;
- exact normalized metadata facet match: high score;
- label/topic/evidence keyword match: medium score;
- co-occurrence through shared anchors across multiple source assertions:
  bounded lower score;
- penalize generic cues that appear too often.

If planned item 002 later adds SQLite keyword/FTS capabilities, this helper can
use those capabilities for candidate preselection, but it should still return
the same explanation shape.

## Scope

- Anchor/facet extraction rules.
- Deterministic ranking helper.
- Explanation result shape.
- Tests using small triple fixtures.
- Documentation explaining anchor search vs semantic search vs graph traversal.

## Non-goals

- No embedding/vector search.
- No LLM clustering or entity extraction.
- No automatic prompt injection.
- No broad/global recall policy.
- No persisted anchor index in the first implementation unless tests prove the
  helper is too slow for realistic fixtures.

## Dependencies and related tasks

- AbstractFramework central ADRs:
  - `0009-connected-memory-recall-and-provenance.md`
  - `0025-kg-entity-normalization-and-dedup.md`
- AbstractSemantics docs:
  - `docs/registry.md`
  - `docs/schema.md`
- Related planned work:
  - `001_semantics_aligned_memory_record_conventions.md`
  - `002_sqlite_database_compatibility_and_store_capabilities.md`
  - `003_bounded_graph_traversal_over_triples.md`
  - `004_recall_trace_and_access_events_contract.md`

## Expected outcomes

- Hosts can get deterministic candidate rankings for concrete memory questions.
- Result explanations show why each candidate surfaced.
- Anchor ranking works without optional dependencies.
- Semantic/vector search remains a separate retrieval path.

## Validation

A-level:

- Unit tests for normalized exact anchors.
- Unit tests for scope/owner filtering before scoring.
- Unit tests proving deterministic order for ties.
- Run `python -m pytest -q`.

B-level:

- Tests that generic high-frequency cues are capped or penalized.
- Tests that typed facets beat unrelated evidence keyword matches.
- Tests that explanation objects include cue/source/score details.

C-level:

- Combine anchor ranking with graph traversal from item 003 to seed a bounded
  neighborhood.
- Compare candidate output with and without optional SQLite keyword capability
  if item 002 adds it.

## Progress checklist

- [ ] Re-check current store/query APIs and planned capability metadata.
- [ ] Define anchor and facet extraction rules.
- [ ] Define ranking/explanation result types.
- [ ] Implement deterministic helper over in-memory assertions.
- [ ] Add tests for exact, facet, generic, and co-occurrence cases.
- [ ] Document how hosts should use anchors as recall cues only.

## Guidance for the implementing agent

Favor transparent scoring over cleverness. If a candidate cannot explain its
score in a short data structure, the helper is becoming too opaque for
audit-friendly memory.
