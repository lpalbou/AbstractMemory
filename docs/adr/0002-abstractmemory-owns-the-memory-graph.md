# ADR 0002: AbstractMemory owns the semantic temporal memory graph and all of its processing

Status: Accepted (operator ruling, 2026-10-27). Aspirational for existing consumers: AbstractNote currently
keeps a parallel graph (its ADR 0003) that is to converge here (backlog track `knowledge_graph_convergence/`).

## Context

AbstractMemory is the framework's semantic, temporal memory graph: the place where notes, messages,
documents and an entity's own experience become knowledge that structures and reorganises itself over
time. In October 2026 AbstractNote, an application built on AbstractGateway, needed capabilities AbstractMemory
did not offer for document knowledge (an entity registry with reversible merges, a claim lifecycle with a
revision log, hybrid search and timelines, communities, consolidation, reflection, the ripple of ADR 0001). It
built them inside its own package, over its own SQLite index, and kept AbstractMemory only as a write-only
projection of its claims (AbstractNote ADR 0003), including direct writes to AbstractMemory's private tables.
About half of AbstractNote's code is now generic memory-graph logic that no other application can use.

That is the wrong direction for the framework. AbstractEntity (self-evolving persistent agents that keep
diaries and leave notes for themselves) needs the same capabilities, and so does any assistant or agent that
should learn from what it reads. Some of AbstractNote's designs are newer and stronger than AbstractMemory's;
they belong in AbstractMemory so every consumer benefits, not in one application.

## Decision

1. **One home for memory.** Everything that structures, links, revises, consolidates, reorganises or
   retrieves memories lives in AbstractMemory: entities and identity, claims and their lifecycle, revisions
   and history, retrieval (search, expansion, timelines, then-versus-now), self-organisation (consolidation,
   communities, topics), reflection and review, and the ripple of an altered memory (ADR 0001).
2. **Consumers build on the graph; they never rebuild it.** An application or package may add an abstraction
   on top of AbstractMemory (for example a notes or diary layer) through its public API. It must not keep a
   parallel graph, a second store of the same knowledge, or its own copy of memory processes, and must never
   write AbstractMemory's private tables.
3. **A gap is fixed in AbstractMemory.** When AbstractMemory is not good enough for a consumer, the fix is an
   AbstractMemory change (raised as an AbstractMemory backlog item), not a workaround in the consumer.
4. **Better designs are absorbed.** A design proven in a consumer (as AbstractNote's entity registry, revision
   log or ripple prototype) is generalised into AbstractMemory and the consumer then uses it.
5. **The process lives here; the model is supplied.** Steps that need judgement (a model deciding identity,
   what a revised memory means, a summary) run inside AbstractMemory's process through a reader the host
   supplies (an injected model client or callable). Model choice and cost stay with the host; the process,
   its bounds and its records stay in AbstractMemory.
6. **Note-specific and agent-specific framing stays with the consumer.** Capture, file import, the wording of
   prompts for one kind of input, and the views an application shows remain the consumer's, as long as they
   read and write through AbstractMemory.

## Consequences

### Positive
- Every application (AbstractNote, AbstractEntity, AbstractAssistant, agents) shares one understanding of what
  is known, and improvements to memory reach all of them.
- Knowledge captured through one app is visible to the others through the gateway.

### Negative
- AbstractMemory grows a document and world-knowledge layer beside its agent memory system, and must keep both
  coherent.
- AbstractNote must migrate off its parallel graph capability by capability, which is real work and
  temporarily slows its own features.

### Neutral
- Generic infrastructure AbstractNote also built (a durable work queue with leases and retries, a memory read
  API over HTTP) belongs to AbstractRuntime and AbstractGateway rather than here; this ADR does not decide their
  shape.

## Enforcement

- Review rejects, in any consumer, access to AbstractMemory internals (`_table`, `_conn`, `_lock` or any `_`
  attribute of a store) and any new memory-graph process (entity resolution, claim revision, consolidation,
  communities, ripple, retrieval fusion) added outside AbstractMemory.
- A consumer that needs a missing capability opens an AbstractMemory backlog item and links it from its own
  backlog; the consumer item is blocked on it rather than implementing a workaround.
- New AbstractMemory capabilities absorbed from a consumer cite that consumer's design and tests as prior art.

## Validation

- A search for private-attribute access to AbstractMemory objects in consumer repositories returns nothing once
  each migration item closes (AbstractNote today: `store/kg.py`).
- Each capability in the convergence track has a scenario test that a consumer-shaped client passes through the
  public API alone.
- AbstractNote's backlog shows each parallel-graph capability either migrated or with a linked AbstractMemory item.

## Backlog links

- Planned track: [knowledge_graph_convergence/](../backlog/planned/knowledge_graph_convergence/README.md)
  (items 0050-0055).
- Related: [ripple_wave/0001](../backlog/proposed/ripple_wave/0001_change_records_and_ripple_primitives.md)
  (the ripple primitives).
- Consumer side: AbstractNote backlog 0033-0036 (track `planned/memory_convergence/`).

## Related

- ADR 0001 (an altered memory ripples through the memories connected to it).
- AbstractNote ADR 0003 (its parallel graph, now transitional) and ADR 0008 (its ripple prototype).
