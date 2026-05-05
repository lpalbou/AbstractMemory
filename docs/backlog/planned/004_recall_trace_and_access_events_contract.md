# 004 - Recall Trace And Access Events Contract

**Status**: Planned  
**Date**: 2026-05-05  
**Priority**: Medium  
**Components**: abstractmemory data contracts, AbstractRuntime/Gateway integration

## Summary

Define storage-neutral contracts for recall traces and memory access events so
hosts can audit why memory was searched, expanded, selected, or skipped while
keeping prompt selection owned by Runtime/Agent layers.

## Design Signal

Recall observability is stronger when hosts can store:

- probe traces with query fingerprints, searched scopes, candidate ids, visited
  ids, expansion budgets, remaining tokens, status, and stop reasons;
- active-memory snapshots recording what became prompt-visible for a turn;
- access events for candidate listing, showing, active selection, expansion,
  edge traversal, probe-report citation, auto-memory, operator pinning, and
  refocus.

The important reusable concept is not "put active memory in AbstractMemory"; it
is "make recall influence auditable and query-scoped."

## ADR Constraints

- ADR-0007: active context is a view, not the durable source.
- ADR-0009: recall is provenance-first and graph-ready.
- Memory recall levels require warnings, effort metadata, budgets, and no silent
  downgrade.
- ADR-0016: tool/model behavior remains outside memory storage.

## Proposed Shape

Add docs and optional dataclasses for host-owned recall telemetry:

- `RecallTrace`: query, normalized fingerprint, recall level, scope policy,
  searched scopes, candidate assertion ids, visited ids, selected ids, budgets,
  warnings, stop reason, status, and provenance.
- `MemoryAccessEvent`: assertion id or edge/path id, access kind, scope, query
  fingerprint, trace id, turn/run id, weight, timestamp, and provenance.

These records may be stored by Runtime/Gateway or by an optional
AbstractMemory-side event store. The key is that normal `TripleStore.query(...)`
does not mutate memory or secretly mark anything prompt-active.

## In Scope

- Contract docs and Python dataclasses/types.
- Optional append-only event store abstraction if a concrete user appears.
- Tests for JSON serialization, stable ordering, and no mutation of assertions.
- Guidance on how Runtime/Gateway should attach trace ids to recall operations.

## Out Of Scope

- Active-memory prompt packing.
- Attention ranking implementation.
- UI observer implementation.
- Mandatory event writes for ordinary library users.

## Acceptance Criteria

- Recall traces can represent `urgent`, `standard`, and `deep` recall metadata.
- Broad/deep recall can report explicit partial results and warnings.
- Access telemetry is append-only and does not change triple truth.
- Documentation says exactly which layer owns writes to these records.
