# Knowledge graph convergence track (planned)

## Status

Planned — operator ruling 2026-10-27 ([ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md)):
AbstractMemory *is* the semantic temporal memory graph and owns all of its processing. Capabilities that
AbstractNote built for itself over a parallel graph are to be generalised here, so every consumer
(AbstractNote, AbstractEntity, assistants, agents) uses one graph. Not started; no code change is made by
writing this track.

## Purpose

AbstractNote (an application on AbstractGateway) built, between 2026-09 and 2026-10, a document-knowledge
layer of its own: an entity registry with reversible merges, a claim lifecycle with a revision log, hybrid
search with graph expansion and timelines, communities and consolidation, reflection and a review inbox, and a
ripple prototype. It keeps AbstractMemory only as a write-only projection of its claims and writes one of
AbstractMemory's private tables. Several of these designs are stronger than what AbstractMemory has. This track
absorbs them, one capability per item, so that AbstractNote (and AbstractEntity, which keeps diaries and leaves
notes for itself) can drop their own copies.

## Items

- `0050_entity_registry_identity_and_reversible_merges.md`: one canonical entity per real thing; aliases,
  candidate lookup, reversible merges, identity review.
- `0051_claim_lifecycle_and_revision_log.md`: claims as first-class records with a revision log, provenance,
  and public window operations (`narrow_assertion`).
- `0052_document_knowledge_retrieval.md`: hybrid search with facets, graph expansion, entity and claim
  timelines, then-versus-now, a change feed, the embedding cache and vector index.
- `0053_self_organisation_communities_consolidation_reflection.md`: communities, topic normalisation,
  document-knowledge consolidation, reflection candidates and insights, the review inbox.
- `0054_ripple_propagation_and_activation.md`: the ripple process of ADR 0001 (propagation, activation,
  budget, reconsideration through an injected reader).
- `0055_notes_and_diary_layer_for_consumers.md`: a notes/diary abstraction on top of the graph, shared by
  AbstractNote and AbstractEntity.

## Reading order

0051 (records everything else revises) → 0050 (identity, needs merges recorded as revisions) → 0052 (reads)
→ `proposed/ripple_wave/0001` (primitives) → 0054 (ripple) → 0053 (passes) → 0055 (consumer layer).
`narrow_assertion` (in 0051 and ripple_wave/0001) can land first on its own: it removes AbstractNote's only
private-table write.

## Governing ADRs

- [ADR 0001](../../../adr/0001-altered-memories-ripple.md): an altered memory ripples (owned here).
- [ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md): AbstractMemory owns the graph and its
  processing; consumers build on it; gaps are fixed here; better consumer designs are absorbed; the model is
  injected.

## Scope

In: generic memory-graph capabilities, public API, both store backends where applicable, docs, tests that a
consumer-shaped client passes through the public API alone.

Out:
- The durable work queue (leases, retries, priorities) AbstractNote built in `store/queue.py`: generic
  infrastructure for AbstractRuntime/AbstractGateway, not memory.
- Gateway routes and HTTP shapes: AbstractGateway's.
- Note capture, file importers (Markdown, Claude sessions, agora), prompt wording for one kind of input, and
  application views: the consumer's (ADR 0002 decision 6).
- Model calls: every step needing judgement takes an injected reader; AbstractMemory never imports a provider
  (the package-wide import-boundary test stays green).

## Prior art (read before designing each item)

AbstractNote `main` (7d65353, 2026-10-27) under `abstractnote/src/abstractnote/`, its ADRs 0003-0008 and
`docs/cognition.md` / `docs/data-model.md`; its unmerged branch `retro/integration` for the ripple
(`recall/propagation.py`, `recall/activation.py`). Each item names the modules it absorbs. Absorb the design and
its tests, not the code verbatim: AbstractNote's code is written against its own SQLite index.

## Consumer side

AbstractNote backlog items 0033-0036 (its track `planned/memory_convergence/`) track the migration on its side; each is blocked on the items here.
