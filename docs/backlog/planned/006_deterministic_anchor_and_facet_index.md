# 006 - Deterministic Anchor And Facet Index

**Status**: Planned  
**Date**: 2026-05-05  
**Priority**: Medium  
**Components**: abstractmemory query helpers, AbstractSemantics-aligned metadata

## Summary

Prototype deterministic anchors and typed facets as a cheap recall layer before
semantic/vector search or deep graph traversal. The goal is fast, explainable
candidate selection for concrete memory questions.

## Design Signal

Cheap anchor/facet methods can be surprisingly strong:

- direct lexical/entity/facet scans had good precision for concrete questions;
- deterministic anchors connected related memories through shared concepts;
- graph traversal improved recall but was too noisy as a default;
- entity/facet indexes were valuable for paths, commands, model names, ADR ids,
  backlog ids, and implementation symbols.

## ADR Constraints

- Recall effort must be explicit: anchors fit `urgent` or `standard` recall, not
  hidden deep search.
- Generated anchors are cues, not durable truth.
- Scope/owner filters must apply before candidate expansion.
- AbstractSemantics remains the vocabulary source for typed entity metadata.

## Proposed Shape

Add a helper that can score candidate assertions or memory-record triples using
deterministic cues:

- exact subject/object/predicate matches;
- normalized concepts from labels, summaries, intents, outcomes, and keywords
  when those exist in attributes;
- typed facets from `attributes.subject_type`, `attributes.object_type`,
  provenance source paths, commands, URLs, route/model names, or other bounded
  metadata;
- bounded co-occurrence expansion, with `min_sources` and `max_sources` to avoid
  one-off noise and huge generic topics.

Return ranked ids with explanation cues. Do not write anchors as assertions
unless a later deep-recall workflow explicitly persists a derived shortcut with
lineage.

## In Scope

- Research prototype or helper module with deterministic scoring.
- A small fixture set based on triples and attributes, not full transcripts.
- Result explanations: cue label, source ids, score, and whether expansion was
  direct or co-occurrence-based.
- Tests showing exact/facet matches beat unrelated high-frequency anchors.

## Out Of Scope

- LLM embedding or clustering.
- Automatic prompt injection.
- Broad/global search without an explicit recall trace.
- Treating anchors as evidence.

## Acceptance Criteria

- Anchor scoring is deterministic and dependency-light.
- Explanations make it clear why each candidate surfaced.
- Scope/owner filters are respected before scoring.
- The helper can be used by Runtime/Flow without adding a dependency from
  AbstractMemory to those packages.
