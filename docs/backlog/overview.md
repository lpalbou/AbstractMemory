# AbstractMemory Backlog Overview

## Summary

This backlog tracks planned AbstractMemory work that is not yet implemented.
Items are written as standalone implementation briefs for future coding agents.
They should be treated as planning memory, not as authority over the codebase:
inspect the current code first, then update the item if reality has changed.

## Current Status

- Planned: 7
- Completed: 0
- Deprecated: 0
- Recurrent: 0

## Priority Bands

- High: storage/query foundations and semantics/provenance conventions that
  should land before higher packages depend on richer memory records.
- Medium: retrieval telemetry and deterministic recall helpers.
- Low: observer-facing read-only conveniences that depend on earlier contracts.

## Next Recommended Work

1. Implement `001_semantics_aligned_memory_record_conventions.md` so record
   conventions follow AbstractSemantics before additional graph-memory helpers
   build on them.
2. Implement `002_sqlite_database_compatibility_and_store_capabilities.md` so
   callers can reason about in-memory, SQLite, and LanceDB capabilities without
   class-name checks.
3. Implement `003_bounded_graph_traversal_over_triples.md` once capability
   metadata and semantics conventions are clear.

## Planned Items

| Priority | Item | Status | Notes |
| --- | --- | --- | --- |
| High | [`001_semantics_aligned_memory_record_conventions.md`](planned/001_semantics_aligned_memory_record_conventions.md) | Planned | Align higher-level memory records with AbstractSemantics registry and schema guidance. |
| High | [`002_sqlite_database_compatibility_and_store_capabilities.md`](planned/002_sqlite_database_compatibility_and_store_capabilities.md) | Planned | Add explicit store capabilities and harden SQLite compatibility without replacing in-memory or LanceDB. |
| High | [`003_bounded_graph_traversal_over_triples.md`](planned/003_bounded_graph_traversal_over_triples.md) | Planned | Add opt-in, budgeted graph traversal over existing triples. |
| Medium | [`004_recall_trace_and_access_events_contract.md`](planned/004_recall_trace_and_access_events_contract.md) | Planned | Define audit-friendly recall telemetry without prompt-selection policy. |
| High | [`005_source_linked_summaries_and_derived_assertion_lineage.md`](planned/005_source_linked_summaries_and_derived_assertion_lineage.md) | Planned | Keep summaries and derived assertions linked to source evidence. |
| Medium | [`006_deterministic_anchor_and_facet_index.md`](planned/006_deterministic_anchor_and_facet_index.md) | Planned | Prototype deterministic recall cues before semantic or deep graph expansion. |
| Low | [`007_read_only_memory_observer_contract.md`](planned/007_read_only_memory_observer_contract.md) | Planned | Define read-only snapshot shapes for observer integrations. |

## Proposed Items

No proposed items currently exist. Use `docs/backlog/proposed/` for ideas that
need more evidence before they become committed planned work.

## Completed Work Ledger

No backlog items have been completed yet.

When a planned item is completed, move it to `docs/backlog/completed/`, update
its metadata, add a completion report, and add a row here with validation
evidence.

## Deprecated Items

No backlog items have been deprecated yet.

## Completion Process

1. Re-read the planned item and inspect the current code/docs it references.
2. Implement the scoped behavior, docs, and tests.
3. Run the validation listed in the item.
4. Add a completion report to the item.
5. Set `Status: Completed` and `Completed: YYYY-MM-DD`.
6. Move the file from `planned/` to `completed/`.
7. Update this overview's counts, tables, next work, and ledger.
8. Search for stale links and run `python -m pytest -q`.

## Deprecation Process

1. Add a deprecation report explaining why the item should not proceed.
2. Set `Status: Deprecated` and add `Deprecated: YYYY-MM-DD`.
3. Move the file from `planned/` to `deprecated/`.
4. Update this overview's counts, tables, and planning notes.
5. Search for stale links.

## Adding New Items

- Use the planned backlog template from the project backlog guide.
- Make the item standalone: include context, current code reality, problem,
  requirements, implementation guidance, validation, and a checklist.
- Keep public backlog items sanitized. Do not link to private local research or
  private fork paths.
- Prefer AbstractFramework ADR references and current code references over chat
  history.

## Planning Notes

- AbstractMemory must remain independent of AbstractRuntime, AbstractAgent,
  AbstractFlow, and AbstractCore.
- AbstractSemantics owns predicate/entity-type vocabulary for extracted
  knowledge assertions.
- In-memory, SQLite, and LanceDB stores should remain first-class backends with
  explicit capability differences.
- Active prompt context and recall policy belong in higher packages; this
  package provides storage, query, provenance, and helper contracts.
