# 005 - Source-Linked Summaries And Derived Assertion Lineage

**Status**: Planned  
**Date**: 2026-05-05  
**Priority**: High  
**Components**: abstractmemory, abstractsemantics, AbstractRuntime/Flow ingestion

## Summary

Define and test a lineage convention for summaries and derived assertions.
Summaries should be compact handles to source evidence, not replacements for it;
derived triples should preserve the source assertions/spans/artifacts that led to
them.

## Design Signal

Source-linked memory designs benefit from two useful rules:

- summary nodes cannot become searchable or prompt-active until they have a
  `summarizes` edge to source memory;
- probe reports and derived memories cite source ids and preserve the path back
  to source evidence.

AbstractMemory already has provenance and temporal fields, so this can be
adapted as a convention over triples rather than as a new node store.

## ADR Constraints

- ADR-0007/0009: summaries must preserve source provenance.
- Memory recall levels: deep recall may write derived shortcut assertions, but
  must preserve lineage and never overwrite atomic assertions.
- ADR-0025: prefer append-only links/validity metadata over destructive cleanup.

## Proposed Shape

Define reserved provenance/attribute keys for lineage:

- `provenance["source_assertion_ids"]`
- `provenance["source_span_ids"]`
- `provenance["source_artifact_ids"]`
- `attributes["memory_kind"]` such as `summary`, `probe_report`, `derived`
- `attributes["derived_from"]` for compact source ids when provenance is too
  rich for query filters
- `attributes["lineage_policy"]` for `summary_of`, `derived_shortcut`, or
  `reconciliation`

Optionally add helper validators:

- reject or warn when a summary-like assertion lacks source ids;
- mark derived assertions clearly in canonical text for vector stores;
- expose source ids in query results for observer/debug surfaces.

## In Scope

- Documentation and tests for source-linked summary conventions.
- Helper validation functions that can be called by Runtime/Flow before write.
- Examples using AbstractSemantics predicates such as `dcterms:abstract`,
  `dcterms:references`, `cito:supports`, and `cito:usesDataFrom`.

## Out Of Scope

- Running summarizers.
- Deciding what should become prompt-visible.
- Deleting or rewriting source assertions.
- A general RDF reasoner.

## Acceptance Criteria

- There is a documented way to identify source evidence for a summary or derived
  assertion.
- Query results preserve enough metadata for a host to reopen the source path.
- Validation helpers are optional and do not make plain triple storage harder.
- Tests show lineage metadata round-trips across all stores.
