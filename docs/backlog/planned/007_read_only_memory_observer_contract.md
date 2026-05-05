# 007 - Read-Only Memory Observer Contract

**Status**: Planned  
**Date**: 2026-05-05  
**Priority**: Low  
**Components**: abstractmemory docs/API, AbstractObserver/Gateway integration

## Summary

Define a read-only inspection contract for AbstractMemory stores so observer UIs
can inspect durable triples, lineage, scopes, and recall traces without becoming
writers or policy owners.

## Design Signal

Observer tools are easier to keep safe when they can open memory stores in
read-only mode and render assertions, neighborhoods, scope bindings, payload
previews, recall traces, and access events without owning write policy.

AbstractFramework already has `@abstractframework/monitor-active-memory` and
AbstractObserver. A narrow read-only contract would let those tools inspect
memory consistently without coupling them to a specific backend schema.

## ADR Constraints

- ADR-0004/0007: observability should preserve provenance and avoid mutating
  state.
- ADR-0001: UI/observer packages compose with memory; memory does not import
  them.
- ADR-0019: inspection APIs need deterministic test fixtures.

## Proposed Shape

Define optional read-only snapshot/export methods:

- list stores and capabilities;
- list recent assertions by scope/owner/time;
- list assertion neighborhoods for graph views;
- expose provenance/attributes without rewriting payloads;
- expose recall/access trace records if a host stores them;
- return warnings when a backend cannot supply a requested view.

For SQLite, prefer query-only connections or deterministic JSON export. For
LanceDB/InMemory, provide best-effort snapshots with clear capability metadata.

## In Scope

- A read-only snapshot data shape documented in AbstractMemory.
- Optional helper/export methods on stores or a separate inspector module.
- Basic fixtures that observer packages can reuse.

## Out Of Scope

- Building the observer UI in this package.
- Mutating memory from observer views.
- Prompt selection or active-memory policy.
- Live event streaming.

## Acceptance Criteria

- Observer packages can render a small memory graph without knowing each store's
  private table layout.
- Snapshot APIs are explicitly read-only.
- Unsupported views return clear warnings rather than silently dropping data.
- Tests cover at least SQLite and in-memory snapshots.
