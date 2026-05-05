# 001 - Semantics-Aligned Memory Record Conventions

**Status**: Planned  
**Date**: 2026-05-05  
**Priority**: High  
**Components**: abstractmemory, abstractsemantics, AbstractRuntime/AbstractFlow integration

## Summary

Define a small convention for representing higher-level memory records on top of
AbstractMemory triples, using AbstractSemantics as the vocabulary source. The
goal is to support richer graph-memory records without turning AbstractMemory
into an agent, extractor, or prompt manager.

## Design Signal

Several graph-memory designs benefit from a compact typed graph:

- record kinds such as plans, episodes, summaries, decisions, claims, lessons,
  and entities;
- relationship kinds such as summarizes, precedes, derives from, refines,
  disagrees with, requires, mentions, answers, and supports;
- digest metadata such as titles, summaries, intents, outcomes, keywords, token
  estimates, payload refs, and source provenance.

Those concepts are useful, but in AbstractFramework they should be expressed as
semantics-aligned triples and/or host-side conventions, not as a second ontology
inside AbstractMemory.

## ADR Constraints

- ADR-0001: keep package boundaries strict; integration belongs in higher
  packages.
- ADR-0005: AbstractMemory is long-term memory, not runtime state.
- ADR-0007/0009: source provenance and active context are separate.
- ADR-0025: stable CURIEs and entity normalization belong at ingestion
  boundaries.
- AbstractSemantics owns predicate/type allowlists.

## Proposed Shape

Document and optionally provide helper functions for common memory record
encodings:

- `Plan` as a document-like record (`rdf:type dcterms:Text`,
  `dcterms:title`, `dcterms:description`, `schema:result` for outcomes).
- `Episode` as a temporal event-like record (`rdf:type schema:Event`,
  `schema:startDate`, `schema:endDate`, `schema:participant`,
  `schema:result`, `schema:nextItem`/`schema:previousItem`).
- `Lesson` as scoped semantic guidance (`rdf:type skos:Concept`,
  `skos:prefLabel`, `skos:definition`, `cito:supports` to evidence).
- `Claim` as `rdf:type cito:Claim`, with `cito:supports` and
  `cito:disagreesWith` for evidence/conflict.
- `Summary` as a source-linked document (`dcterms:abstract` plus
  `dcterms:references` or source lineage metadata).
- `Entity` as a normalized CURIE with label triples (`schema:name`,
  `skos:prefLabel`, `skos:altLabel`).

Keep these as conventions over `TripleAssertion` so existing stores remain
simple and append-only.

## In Scope

- A docs page that maps Codex memory record concepts to AbstractSemantics
  predicates/entity types.
- Optional lightweight helper builders that return `TripleAssertion` lists.
- Tests that helpers emit canonical triples and preserve provenance.
- Guidance for Runtime/Flow extractors to use these conventions.

## Out Of Scope

- LLM extraction or classification.
- Active prompt selection.
- Runtime artifact storage.
- A new graph database or RDF store.

## Acceptance Criteria

- Documentation explains how to encode at least Plan, Episode, Lesson, Claim,
  Summary, and Entity records as triples.
- No hard dependency from AbstractMemory to AbstractRuntime, AbstractAgent, or
  AbstractCore.
- Any optional AbstractSemantics integration is either dependency-light or kept
  behind an extra/helper API.
- Existing stores continue to accept ordinary triples without requiring record
  kinds.
