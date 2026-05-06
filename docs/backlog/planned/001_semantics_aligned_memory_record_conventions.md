# Planned: Semantics-aligned memory record conventions

## Metadata

- Created: 2026-05-05
- Status: Planned
- Completed: N/A
- Priority: High
- Components: AbstractMemory docs/helpers, AbstractSemantics registry alignment, Runtime/Flow ingestion guidance

## Context

AbstractMemory stores append-only `TripleAssertion` records. Higher layers will
eventually want richer memory records such as plans, episodes, lessons, claims,
summaries, and normalized entities. Those records must not become a private
AbstractMemory ontology.

The vocabulary source of truth is AbstractSemantics:

- `abstractsemantics/src/abstractsemantics/semantics.yaml`
- `abstractsemantics/docs/guide/semantics/semantic-triple-prompt-v4-optimized.md`
- `abstractsemantics/docs/schema.md`

The optimized semantic triple prompt says extraction workflows must emit JSON
conforming to `abstractsemantics:kg_assertion_schema_v0`, use only registry
predicate ids/entity-type ids, and include a verbatim
`attributes.evidence_quote` for every assertion.

## Current code reality

- `src/abstractmemory/models.py` defines immutable `TripleAssertion` and
  canonicalizes `subject`, `predicate`, and `object`.
- `src/abstractmemory/store.py` defines `TripleQuery` and the minimal
  `TripleStore` protocol.
- `src/abstractmemory/__init__.py` exports store/model primitives only; there
  are no memory-record helper builders.
- `src/abstractmemory/in_memory_store.py`,
  `src/abstractmemory/sqlite_store.py`, and
  `src/abstractmemory/lancedb_store.py` store arbitrary triples and preserve
  `provenance`/`attributes`.
- AbstractMemory currently has no runtime dependency on AbstractSemantics,
  AbstractRuntime, AbstractAgent, or AbstractCore.

Re-check these files before implementation. If AbstractSemantics has added
predicates or entity types by then, update the mappings below to match the
current registry instead of copying this plan mechanically.

## Problem

Without a semantics-aligned convention, future memory work could drift into
three bad shapes:

- inventing `memory:*` predicates that bypass the shared registry;
- hiding record kinds in free-form `attributes` so graph traversal cannot use
  ordinary triples;
- coupling AbstractMemory to extraction, prompt selection, or runtime state.

That would violate the package boundary ADRs and make memory records harder to
validate with AbstractSemantics tooling.

## What we want to do

Create a documented convention, and optionally small helper builders, for
encoding common memory records as ordinary AbstractSemantics-aligned triples.
The convention should be strict enough for ingestion/extraction workflows and
simple enough that all existing stores keep working unchanged.

## Why

Semantics alignment gives AbstractMemory a shared vocabulary with the rest of
the framework. It lets Runtime/Flow/Agent code write richer memory without
turning AbstractMemory into a model-driven extractor or a second schema
authority.

## Requirements

- Use only predicate ids from `abstractsemantics/semantics.yaml`.
- Use only entity-type ids from `abstractsemantics/semantics.yaml` in
  `attributes.subject_type` and `attributes.object_type`.
- Do not introduce `memory:*` or other package-private predicate ids in
  AbstractMemory docs or helpers.
- If a required predicate/type is missing, create a separate AbstractSemantics
  backlog item or registry change before using it.
- Every extracted fact example must include a short verbatim
  `attributes.evidence_quote`, matching the semantic triple prompt.
- Preserve `attributes.original_context` only when the quote alone is
  insufficient.
- Preserve `scope`, `owner_id`, `observed_at`, validity windows, confidence,
  and provenance exactly as ordinary `TripleAssertion` fields.
- Keep helper builders optional. Plain `TripleAssertion` writes must remain the
  core API.
- Avoid adding a hard AbstractRuntime, AbstractAgent, AbstractFlow, or
  AbstractCore dependency.

## Suggested implementation

Add a docs page such as `docs/memory-record-conventions.md` with registry-backed
examples:

- Plan:
  - type as `rdf:type -> dcterms:Text` or `schema:ItemList`, depending on the
    current AbstractSemantics registry;
  - title with `dcterms:title`;
  - description with `dcterms:description`;
  - ordered steps with `dcterms:hasPart`, `dcterms:isPartOf`,
    `schema:nextItem`, and `schema:previousItem`;
  - outcomes with `schema:result`.
- Episode:
  - type as `rdf:type -> schema:Event`;
  - participants with `schema:participant`;
  - time bounds with `schema:startDate` and `schema:endDate`;
  - sequence with `schema:nextItem` and `schema:previousItem`;
  - result with `schema:result`.
- Lesson:
  - type as `rdf:type -> skos:Concept`;
  - label/definition with `skos:prefLabel` and `skos:definition`;
  - related topics with `skos:related`, `skos:broader`, or `skos:narrower`;
  - evidence links with `cito:supports` or `cito:usesDataFrom`.
- Claim:
  - type as `rdf:type -> cito:Claim`;
  - supporting evidence with `cito:supports`;
  - disagreement/conflict with `cito:disagreesWith`;
  - confirmation with `cito:confirms`.
- Summary:
  - type as `rdf:type -> dcterms:Text`;
  - title/abstract with `dcterms:title` and `dcterms:abstract`;
  - source links with `dcterms:references` and/or `cito:usesDataFrom`.
- Entity:
  - type as one of the registry entity types such as `schema:Person`,
    `schema:Organization`, `schema:SoftwareSourceCode`, `schema:Dataset`,
    `skos:Concept`, or `schema:Thing`;
  - labels with `schema:name`, `skos:prefLabel`, and `skos:altLabel`;
  - aliases/canonical matches with `schema:sameAs`, `skos:exactMatch`, or
    `skos:closeMatch`.

If helper code is useful, add a small module that builds lists of
`TripleAssertion` objects and accepts an optional registry/validator object. Do
not make helpers run LLM extraction.

## Scope

- Documentation for the conventions.
- Optional dependency-light helper builders.
- Tests that helper outputs use registry ids and round-trip through all stores.
- Guidance for Runtime/Flow ingestion code to validate against
  `abstractsemantics:kg_assertion_schema_v0`.

## Non-goals

- No LLM extraction pipeline in AbstractMemory.
- No active-memory prompt projection.
- No private memory ontology.
- No RDF reasoner or graph database.
- No automatic registry mutation from this package.

## Dependencies and related tasks

- AbstractFramework central ADRs:
  - `0001-layered-architecture.md`
  - `0005-memory-architecture.md`
  - `0007-active-context-and-memory-provenance.md`
  - `0009-connected-memory-recall-and-provenance.md`
  - `0025-kg-entity-normalization-and-dedup.md`
- AbstractSemantics docs:
  - `docs/guide/semantics/semantic-triple-prompt-v4-optimized.md`
  - `docs/schema.md`
  - `docs/registry.md`
- Related planned work:
  - `002_sqlite_database_compatibility_and_store_capabilities.md`
  - `003_bounded_graph_traversal_over_triples.md`
  - `005_source_linked_summaries_and_derived_assertion_lineage.md`

## Expected outcomes

- A future extractor can emit memory records that validate against the shared
  AbstractSemantics registry.
- AbstractMemory users can inspect records as ordinary triples.
- Store implementations do not need special case logic for record kinds.
- Higher packages can opt into the convention without AbstractMemory importing
  them.

## Validation

A-level:

- Confirm every documented predicate and entity type exists in the current
  AbstractSemantics registry.
- Add examples that can be converted into `TripleAssertion` objects.
- Run `python -m pytest -q`.

B-level:

- If helper builders are added, test each helper emits canonical triples with
  evidence/provenance preserved.
- Round-trip helper output through in-memory and SQLite stores.
- Validate sample extractor JSON with
  `abstractsemantics:kg_assertion_schema_v0`.

C-level:

- Round-trip examples through LanceDB when the optional dependency is installed.
- Exercise one small Plan -> Episode -> Lesson -> Evidence graph with bounded
  traversal from planned item 003 after that work lands.

## Progress checklist

- [ ] Re-read AbstractSemantics registry, schema docs, and optimized prompt.
- [ ] Re-check current AbstractMemory model/store APIs.
- [ ] Draft the conventions doc with registry-only predicates/types.
- [ ] Add helper builders only if they reduce repeated boilerplate.
- [ ] Add tests for examples/helpers.
- [ ] Update README/API/docs index if a new conventions doc is added.
- [ ] Record any missing vocabulary as AbstractSemantics follow-up work.

## Guidance for the implementing agent

Treat AbstractSemantics as the schema authority. If a tempting memory concept
does not map cleanly, do not smuggle it into attributes as permanent truth.
Either model it with existing registry terms, keep it as host-side provenance,
or propose a registry extension in AbstractSemantics first.
