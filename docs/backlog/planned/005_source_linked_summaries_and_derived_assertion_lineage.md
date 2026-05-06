# Planned: Source-linked summaries and derived assertion lineage

## Metadata

- Created: 2026-05-05
- Status: Planned
- Completed: N/A
- Priority: High
- Components: AbstractMemory conventions/helpers, AbstractSemantics predicates, Runtime/Flow ingestion guidance

## Context

Summaries and derived assertions are useful memory compression tools, but they
are dangerous if they replace or obscure source evidence. AbstractMemory already
has `provenance`, `attributes`, and temporal fields; the missing piece is a
documented lineage convention that uses AbstractSemantics predicates where
possible and keeps source ids inspectable.

## Current code reality

- `TripleAssertion` stores free-form `provenance` and `attributes`.
- Store implementations preserve these dictionaries through add/query.
- Query results do not include generated assertion ids unless the writer also
  stores stable ids in `provenance` or `attributes`.
- No helper validates that summary-like assertions reference source evidence.
- AbstractSemantics has evidence/source predicates such as
  `dcterms:references`, `cito:supports`, `cito:usesDataFrom`, and
  `cito:providesDataFor`.

Re-check AbstractSemantics before implementation. If the registry changes,
prefer current registry ids over the examples in this item.

## Problem

Derived memory can become misleading when:

- a summary is searchable without a path back to source evidence;
- a derived shortcut looks like an atomic observation;
- source span/artifact/assertion ids are hidden in inconsistent metadata keys;
- contradiction/reconciliation records overwrite older assertions instead of
  linking to them.

This would weaken auditability and violate the provenance-first memory ADRs.

## What we want to do

Define and test a lineage convention for summaries, probe reports, derived
shortcut assertions, and reconciliation records. The convention should combine
ordinary triples with reserved provenance/attribute keys so hosts can reopen the
source path.

## Why

Long-lived memory needs compression, but compression should create handles to
evidence, not new unsupported truth. Source-linked lineage lets hosts use
summaries and derived assertions while preserving the ability to inspect what
they came from.

## Requirements

- Use AbstractSemantics predicates for source/evidence links:
  - `dcterms:references`
  - `cito:supports`
  - `cito:usesDataFrom`
  - `cito:providesDataFor`
  - `cito:confirms`
  - `cito:disagreesWith`
- Use registry entity types such as `dcterms:Text`, `cito:Claim`,
  `schema:Event`, or `skos:Concept` where applicable.
- Define stable reserved metadata keys, for example:
  - `provenance["source_assertion_ids"]`
  - `provenance["source_span_ids"]`
  - `provenance["source_artifact_ids"]`
  - `provenance["source_urls"]`
  - `attributes["memory_kind"]`
  - `attributes["lineage_policy"]`
  - `attributes["source_fingerprint"]`
- Require summary/derived examples to include both:
  - a triple-level source link when the source has a stable id; and
  - provenance source ids for audit.
- Do not delete or mutate source assertions.
- Do not make source-linked summaries automatically prompt-visible.
- Keep validation helpers optional for plain store users.

## Suggested implementation

Add documentation and optional validators:

- `validate_lineage(assertions)`:
  - warns or errors when `attributes["memory_kind"]` is `summary`, `derived`,
    `probe_report`, or `reconciliation` and no source ids are present;
  - verifies known lineage policies;
  - verifies metadata is JSON-serializable.
- helper examples:
  - summary as `rdf:type -> dcterms:Text`;
  - summary text as `dcterms:abstract`;
  - summary source as `dcterms:references` or `cito:usesDataFrom`;
  - claim support as `cito:supports`;
  - contradiction/reconciliation as `cito:disagreesWith` plus validity metadata.

If stable assertion ids are needed before query results expose generated ids,
document the writer-side convention: place a durable id in
`provenance["assertion_id"]` or `attributes["assertion_id"]` and use that same
id in source links.

## Scope

- Lineage convention docs.
- Optional validators for summary/derived/probe/reconciliation records.
- Tests that lineage metadata round-trips through in-memory and SQLite stores.
- Optional LanceDB round-trip tests when installed.
- Examples aligned with AbstractSemantics registry ids.

## Non-goals

- No summarizer implementation.
- No prompt-visible active-memory policy.
- No physical deletion or compaction of source assertions.
- No broad contradiction resolver.
- No general RDF inference.

## Dependencies and related tasks

- AbstractFramework central ADRs:
  - `0007-active-context-and-memory-provenance.md`
  - `0009-connected-memory-recall-and-provenance.md`
  - `0025-kg-entity-normalization-and-dedup.md`
- AbstractSemantics docs:
  - `docs/registry.md`
  - `docs/schema.md`
  - `docs/guide/semantics/semantic-triple-prompt-v4-optimized.md`
- Related planned work:
  - `001_semantics_aligned_memory_record_conventions.md`
  - `003_bounded_graph_traversal_over_triples.md`
  - `004_recall_trace_and_access_events_contract.md`

## Expected outcomes

- Summaries and derived assertions carry inspectable source paths.
- Hosts can distinguish atomic observations from compressed/derived records.
- Source evidence remains durable and queryable.
- Store implementations do not need special summary tables to preserve lineage.

## Validation

A-level:

- Unit tests for lineage validator success/failure cases.
- Round-trip lineage metadata through in-memory and SQLite stores.
- Confirm all documented predicates/types exist in AbstractSemantics.
- Run `python -m pytest -q`.

B-level:

- Test a summary linked to two source assertions and one source artifact id.
- Test a derived claim that supports one source and disagrees with another.
- Test that missing source ids produce a clear warning/error.

C-level:

- Optional LanceDB round-trip when installed.
- Use planned item 003 graph traversal to expand summary -> source -> evidence.
- Export/import lineage fixture deterministically if planned item 002 adds
  export support.

## Progress checklist

- [ ] Re-read current AbstractSemantics registry.
- [ ] Define reserved provenance/attribute keys.
- [ ] Document summary, derived, probe-report, and reconciliation examples.
- [ ] Add optional validation helpers if useful.
- [ ] Add round-trip tests across stores.
- [ ] Update API/docs index if a new lineage doc is added.

## Guidance for the implementing agent

Do not let summaries become orphan facts. If a record compresses or derives from
other evidence, make the source path visible in both triples and provenance
where practical. Keep the old evidence append-only unless a user explicitly
requests deletion elsewhere.
