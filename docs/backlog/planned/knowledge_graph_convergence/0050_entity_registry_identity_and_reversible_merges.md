# Entity registry, identity and reversible merges

Created: 2026-10-27 (operator ruling, [ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md)).
Track: `knowledge_graph_convergence` · Priority: High · Status: Planned

## Summary
One canonical entity per real thing, for any consumer: a registry of entities with kind, canonical name,
aliases and summary; a deterministic candidate lookup for a new mention (same canonical name, full-text over
names/aliases/summaries, vector neighbours) that an injected reader decides on; merges that are recorded,
explainable and reversible; and a review list of uncertain matches for a person or an agent to confirm.

## Why
Identity is the base of a knowledge graph: without it, the same person or project splits into several cards
and every later read is wrong. AbstractMemory has agent-centred identity (world-model cards, a night alias
fold); AbstractNote built a general document-knowledge registry beside it. ADR 0002 puts one registry here.

## Current code reality
- AbstractMemory: `world_model.py` (orientation cards: long-term understanding of people, objects, places,
  concepts), `world_model_alias.py` (`alias_map`, `alias_candidates`, `alias_world_model`: folding targets that
  name one thing, e.g. `person:admin` = `person:laurent`), `identity_review.py` (night review of identity
  proposals for the self), `entity_card.py` (the summoned entity's own card). Aliases are assertions; there is no
  canonical-name rule, no candidate lookup with match reasons, no merge record and no unmerge.
- AbstractNote (prior art): `store/names.py` (one canonical name per entity at apply time and as a repair;
  `reuse_taken_names`), `ids.py` (`name_key`, `canonical_name`), `process/resolve.py` (up to three candidates per
  mention with how each matched), `process/revise.py` (`reuse`/`create`/`unsure` mapping; an `unsure` creates the
  entry plus a `skos:closeMatch` claim), `recall/review.py` (the review list and confirm action). Entities live in
  its own `note.sqlite3`; AbstractMemory receives only `schema:name`/`skos:altLabel`/`schema:sameAs` triples.

## Scope
In: entity records and canonical naming over the triple store; candidate lookup returning match reasons; merge
and unmerge as recorded revisions (0051) with the surviving entity's history intact; a review read of uncertain
matches and a confirm operation; generalise `alias_world_model` onto the same mechanism so the agent world model
and document entities share one identity. Out: the prompt that asks a model to decide a match (consumer framing);
the decision itself goes through an injected reader.

## Dependencies
0051 (merges are revisions). Related: `proposed/ripple_wave/0001` (a merge is a meaning change that ripples).

## Validation
A consumer-shaped test: two notes naming "Laurent" and "L. Albou" resolve to one entity through the public API;
the merge is visible, reversible, and the unmerge restores both histories; `alias_world_model` behaviour is
unchanged on the existing tests; mutation: removing the canonical-name check makes the duplicate test go red.
