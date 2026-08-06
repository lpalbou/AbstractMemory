# Proposed: Capabilities extensions + deterministic JSONL export/import

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: High
- Components: store protocol, backends, export/import module, docs, tests

## ADR status

- Governing ADRs: AbstractFramework `0001-layered-architecture.md`,
  `0019-testing-strategy-and-levels.md`
- ADR impact: None

## Context

Planned item `002_sqlite_database_compatibility_and_store_capabilities.md`
already commits to a `StoreCapabilities` descriptor and mentions deterministic
export as a maybe. Two things changed since it was written:

1. The 2026-07-05 audits confirmed its premise emphatically: the gateway
   hand-rolls per-backend capability dicts keyed by class name
   (`abstractgateway/src/abstractgateway/memory_store.py:237-273`), and
   SmartNote/route code sniff class names. Every consumer guesses.
2. The memory-system wave adds surfaces that capabilities must describe
   (journal, closure fold, FTS, vector, manifest) and REQUIRES export/import
   as the migration substrate (`0012`'s LanceDB schema migration; future
   canonical-text version bumps in `0014`).

This item extends 002 rather than replacing it: implement 002's descriptor,
then add the wave's flags and promote export/import from "maybe" to a
first-class contract.

## Current code reality

- No capabilities API on any store (`store.py` protocol has add/query/close).
- No export/import helpers anywhere in the package.
- The Open Codex Memory prototype ships deterministic ordered JSON export
  (tested deterministic) — the proven shape to follow.

## Problem or opportunity

Capabilities kill class-name sniffing across four consumers; export/import is
the substrate that makes every schema-touching item in this wave a one-command
migration instead of a data-loss event.

## Proposed direction

1. Implement planned 002's `StoreCapabilities` (frozen dataclass) with the
   wave's additional flags:
   `persistence, structured_query, semantic_query, vector_query,
   keyword_query, graph_walk (none|generic|native), deterministic_export,
   journal, closure_fold, batch_query, add_if_absent, manifest`.
   Exposed as a `capabilities` property on every store; values must be
   honest (probed where needed, e.g. FTS5 availability).
2. Deterministic export: `export_jsonl(path | stream)` — one JSON object per
   assertion (using `to_dict()` + `assertion_id` + `content_hash`), plus
   closure records and (once `0017` lands) journal records in clearly-typed
   lines (`{"type": "assertion" | "closure" | "event" | "binding" | ...}`),
   ordered by stable keys. Byte-identical output for identical stores.
3. Import: `import_jsonl(path | stream, *, mode="create")` — rebuilds a store
   preserving ids and hashes; refuses non-empty targets unless
   `mode="merge"` (add_if_absent semantics).
4. Migration recipe: export → recreate (new schema) → import; used by `0012`'s
   helper and documented as THE upgrade path in `docs/stores.md`.
5. Gateway migration: replace the hand-rolled capability dicts with the
   package descriptor (a small follow-up in abstractgateway's backlog;
   reference it).

## Why it might matter

Every schema decision in this wave becomes reversible and testable once
export/import exists; capabilities make backend selection and degradation
honest across the framework (the `#FALLBACK` convention needs something
factual to report against).

## Decision boundaries

- Export format is versioned (`"format": "abstractmemory/jsonl@1"` header
  line); import validates the version.
- Export includes everything needed to reconstruct truth + journal; it does
  NOT include derived indexes (FTS tables, vectors are re-derivable — but
  vectors ARE exported when present to avoid forced re-embedding; manifest
  exported too).
- Determinism is a tested contract (fixture store → export twice →
  byte-identical).

## Promotion criteria

Promote together with planned 002 (this extends it); required before `0012`'s
migration helper can be implemented.

## Validation ideas

- Capability values match actual behavior per backend (conformance suite
  asserts: if `semantic_query` is false, `query_text` raises the documented
  error, etc.).
- Export→import round-trip preserves ids, hashes, closure state, manifest;
  equality verified via a second export.
- Merge-mode import is idempotent (re-import inserts nothing).
- 100k-assertion export/import completes within a sane budget (records the
  first performance baseline for the package).

## Non-goals

- No remote/streaming sync protocol.
- No import-time schema evolution beyond the versioned format contract.
- No replacement of planned 002 — this item extends it; reconcile the two at
  promotion time (single implementation, one set of tests).

## Guidance for future agents

Read planned 002 first and implement both as one coherent change. Keep the
JSONL line types open for extension (journal records land in `0017`).
