# 002 - SQLite Store Migrations, FTS, And Capabilities

**Status**: Planned  
**Date**: 2026-05-05  
**Priority**: High  
**Components**: abstractmemory SQLite store, docs, tests

## Summary

Strengthen `SQLiteTripleStore` as the boring, inspectable durable backend. The
goal is local portability, schema visibility, deterministic tests, and
debuggability without introducing a server dependency.

## Design Signal

Inspectable local graph-memory stores commonly need:

- explicit SQLite schema versions and migrations;
- FTS5 for keyword/facet search;
- indexes for scope, kind, entities, and edges;
- immutable node/edge triggers;
- deterministic export/import;
- read-only observer access over the same SQLite file.

AbstractMemory's current SQLite store is intentionally small: one assertion
table, JSON columns, and structured filters. That is a good v0 baseline, but it
needs a planned path before host packages rely on it as the durable local KG.

## ADR Constraints

- ADR-0019: keep default tests fast and deterministic; use temp file stores.
- ADR-0005/0009: storage should preserve provenance and support future recall,
  but Runtime owns active context.
- `query_text` must remain semantic/vector-oriented; do not add a hidden keyword
  fallback that changes current semantics.

## Proposed Shape

Add backend metadata and SQLite improvements in small slices:

- store capability descriptors, e.g. `supports_persistence`,
  `supports_semantic`, `supports_keyword_search`, `supports_graph_walk`;
- schema version tracking and migrations for the SQLite backend;
- table-name validation/quoting so custom table names cannot produce invalid or
  unsafe SQL;
- optional FTS5-backed keyword query as a separate API or query field, clearly
  distinct from semantic `query_text`;
- deterministic JSON export for inspection and tests;
- optional stable assertion id exposure for query results, either through
  attributes metadata or a new result wrapper.

## In Scope

- SQLite-only schema hardening.
- Capability flags on all store implementations.
- Tests for migration, capability metadata, custom table-name validation, FTS
  availability handling, and export determinism.

## Out Of Scope

- Replacing LanceDB vector search.
- Keyword fallback when callers use `query_text`.
- Runtime recall policy or prompt selection.
- A remote SQLite service.

## Acceptance Criteria

- Host packages can ask a store what it supports without inspecting class names.
- SQLite remains dependency-free by default.
- Keyword search, if added, has its own explicit surface and produces warnings or
  clear errors when FTS5 is unavailable.
- Existing structured queries keep their current behavior.
