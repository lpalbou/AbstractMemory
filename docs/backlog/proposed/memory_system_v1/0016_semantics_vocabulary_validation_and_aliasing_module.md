# Proposed: Registry-backed vocabulary validation + aliasing module (hard AbstractSemantics dependency)

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: High
- Components: new vocabulary module, pyproject dependency, tests, docs; AbstractSemantics registry additions (cross-repo prerequisite)

## ADR status

- Governing ADRs: AbstractFramework `0025-kg-entity-normalization-and-dedup.md`,
  `0005-memory-architecture.md`
- ADR impact: May revise existing ADR (dependency direction: AbstractMemory →
  AbstractSemantics becomes a hard dependency — record it at promotion)

## Context

Owner decision (2026-07-05): AbstractMemory takes a HARD dependency on
AbstractSemantics (registry injectable for tests). AbstractSemantics is the
vocabulary authority: 44 predicates / 18 entity types across
dcterms/schema.org/skos/cito families plus `kg_assertion_schema_v0`.

Predicate validation and aliasing are currently duplicated and DIVERGING in
consumers:

- the runtime has `_PREDICATE_ALIAS_MAP` (schema:isPartOf→dcterms:ispartof
  etc.) + registry allowlist validation
  (`abstractruntime/.../abstractmemory/effect_handlers.py:17-70`);
- SmartNote has the allowlist HALF only (`smartnote/src/smartnote/memory/store.py:16-25,80-83`):
  unknown predicates are silently skipped with a printed `#FALLBACK` — so
  predicates the runtime would rescue via aliasing become data loss in
  SmartNote;
- the triangle investigation found alias entries drifting between the runtime
  map and the registry's own synonyms.

Planned item `001_semantics_aligned_memory_record_conventions.md` addresses
the same territory as a documentation page; documentation cannot prevent the
SmartNote failure mode. This item reshapes 001's intent into shared code.

## Current code reality

- AbstractMemory has zero AbstractSemantics awareness (`pyproject.toml` has no
  dependency; `models.py` canonicalizes strings only).
- `abstractsemantics.load_semantics_registry()` / `registry.predicate_ids()`
  is the API both consumers call today.
- CURIE instance-id normalization (`ex:` kebab-slugging) also lives in the
  runtime (`effect_handlers.py:73-112`) — generic string mechanics, same
  duplication risk.

## Problem or opportunity

One vocabulary module in the package gives every consumer identical
validation, aliasing, and normalization — and gives the registry a single
enforcement point instead of N drifting copies.

## Proposed direction

1. `pyproject.toml`: add `abstractsemantics` to core dependencies (hard).
2. New `vocabulary.py` module:
   - `Vocabulary` class wrapping a registry (default: `load_semantics_registry()`;
     injectable for tests) exposing `validate_predicate(p) -> ValidationResult`,
     `resolve_predicate(p) -> str` (alias → canonical, case-normalized),
     `validate_entity_type(t)`, `predicate_ids()`, `alias_map()`;
   - the alias map MOVES here from the runtime (single source; the registry
     may later absorb it — coordinate with AbstractSemantics);
   - rejected predicates produce a structured result with a `#FALLBACK`
     message including the nearest known predicates (actionable, never a bare
     skip);
   - `normalize_curie(value) -> str`: the `ex:` kebab-slug normalization,
     moved from the runtime, exposed for all consumers.
3. Opt-in enforcement at the store boundary: stores stay vocabulary-agnostic
   (layer 1 must accept arbitrary triples), but `remember()`/record builders
   (`0021`) and an optional `ValidatingStore` wrapper (or an
   `add(validate=...)` hook — decide at implementation) run every predicate
   through `Vocabulary`. Consumers migrate off their private copies.
4. Registry prerequisite (cross-repo): the memory-record layer (`0021`) needs
   ~5 additions, all real ontology terms: `dcterms:replaces`,
   `dcterms:requires`, `cito:repliesTo`, `prov:wasDerivedFrom`, and a
   `dcterms:type` kind-discriminator convention. File the corresponding
   proposed item in `abstractsemantics/docs/backlog/` and link it here; do NOT
   invent package-private predicates in the meantime (001's rule stands).

## Why it might matter

Fixes live silent data loss (SmartNote's structural edges), deletes duplicated
divergent code in two consumers, and enacts the owner's decided dependency
direction — the precondition for the typed memory-record layer.

## Decision boundaries

- Layer 1 stores never REQUIRE validation (arbitrary triples remain legal);
  validation is enforced at the record/facade layer and offered as a wrapper.
- The registry stays the authority; this module never mutates it and never
  defines new predicate ids.
- Alias resolution is deterministic and total (unknown stays unknown +
  structured rejection); no fuzzy matching.

## Promotion criteria

Promote with the wave; before `0021` (records need it) and ideally before the
consumer-migration item (`0024`). The AbstractSemantics registry item must be
filed at the same time.

## Validation ideas

- Every alias in the runtime's current map resolves identically through the
  module (golden test); runtime switches to the module and deletes its map
  (integration test in abstractruntime).
- SmartNote's dropped-predicate fixtures now resolve via aliases or produce
  structured rejections (no silent drops).
- Unknown predicate → structured rejection with nearest-known hints.
- Registry injection: tests run with a stub registry, no global state.

## Non-goals

- No LLM extraction or predicate inference.
- No registry mutation from this package.
- No entity RESOLUTION (deciding two entities are the same) — only id/format
  normalization; resolution stays a higher-layer concern (ADR 0025).

## Guidance for future agents

Reconcile with planned 001 at promotion: 001's conventions doc remains
valuable as documentation OF this module's behavior, not as the enforcement
mechanism. Coordinate the alias-map home with AbstractSemantics maintainers —
code here, data possibly in the registry.
