# Planned: Read-only memory observer contract

## Metadata

- Created: 2026-05-05
- Status: Planned
- Completed: N/A
- Priority: Low
- Components: AbstractMemory inspector API/docs, Observer/Gateway integration guidance

## Context

Observer tools should be able to inspect durable memory stores without becoming
writers or recall-policy owners. They need a stable read-only shape for recent
assertions, scopes, provenance, source lineage, graph neighborhoods, and recall
trace records when hosts provide them.

## Current code reality

- Store APIs expose `add`, `query`, and `close`.
- There is no read-only snapshot/inspector API.
- SQLite can be inspected manually with SQLite tools, but there is no stable
  package-level view shape.
- In-memory and LanceDB have different private storage details.
- Recall traces/access events do not exist yet; planned item 004 defines the
  contract.
- Capability metadata does not exist yet; planned item 002 covers it.

Re-check items 002, 003, 004, and 005 before implementation. This contract
should reuse their result shapes rather than invent parallel observer models.

## Problem

Without a read-only observer contract:

- UI/observer packages may learn each backend's private schema;
- inspection code may accidentally become writer code;
- unsupported views may silently omit data;
- graph/lineage/recall views may diverge by store.

That would make memory harder to debug and would couple AbstractObserver or
Gateway code too tightly to one backend.

## What we want to do

Define an explicit read-only snapshot/inspection shape that observer packages
can consume. The first implementation can be a helper/export API rather than a
live event stream.

## Why

Memory needs trust. Users and developers should be able to inspect what exists,
where it came from, and how it connects without triggering writes or active
context changes.

## Requirements

- Snapshot APIs must be explicitly read-only.
- Snapshot calls must not mutate assertions, access counters, or active context.
- Unsupported views must return clear warnings/capability flags.
- Snapshot shape should include:
  - store capabilities;
  - assertion records;
  - scope/owner summaries;
  - provenance and attributes;
  - lineage/source ids when present;
  - graph neighborhood paths when item 003 is available;
  - recall/access traces when item 004 is available.
- Avoid exposing backend-private table details as the public observer contract.
- Preserve deterministic ordering for tests and UI diffs.
- Keep observer packages as consumers; AbstractMemory must not import UI code.

## Suggested implementation

Add an inspector module such as `src/abstractmemory/inspect.py`:

```python
@dataclass(frozen=True)
class MemorySnapshot:
    capabilities: StoreCapabilities
    assertions: tuple[TripleAssertion, ...]
    scopes: tuple[ScopeSummary, ...]
    warnings: tuple[str, ...]
```

Possible helper functions:

- `snapshot_store(store, query=None, limit=...)`
- `snapshot_scope_summary(store)`
- `snapshot_neighborhood(store, seed, ...)` using item 003 when available
- `snapshot_lineage(store, assertion_id)` using item 005 conventions when
  available

For SQLite, optionally support opening a path in read-only mode if that can be
done portably. For in-memory and LanceDB, return best-effort snapshots using
public query APIs and capability warnings.

## Scope

- Read-only snapshot shape.
- Helper APIs built on current store/query contracts.
- Deterministic tests for in-memory and SQLite.
- Optional LanceDB tests when installed.
- Documentation for observer integration boundaries.

## Non-goals

- No observer UI implementation.
- No live streaming/event subscription.
- No write or edit methods.
- No active prompt selection.
- No backend-private schema guarantee.

## Dependencies and related tasks

- AbstractFramework central ADRs:
  - `0001-layered-architecture.md`
  - `0004-observability-strategy.md`
  - `0007-active-context-and-memory-provenance.md`
  - `0019-testing-strategy-and-levels.md`
- Related planned work:
  - `002_sqlite_database_compatibility_and_store_capabilities.md`
  - `003_bounded_graph_traversal_over_triples.md`
  - `004_recall_trace_and_access_events_contract.md`
  - `005_source_linked_summaries_and_derived_assertion_lineage.md`

## Expected outcomes

- Observer/Gateway packages can render memory without knowing backend internals.
- Snapshot results are deterministic and warning-rich.
- Memory inspection remains separate from memory mutation.
- The same UI concepts can work for in-memory, SQLite, and LanceDB stores with
  capability-specific degradation.

## Validation

A-level:

- Unit tests for in-memory snapshot determinism.
- Unit tests for SQLite snapshot determinism.
- Tests that snapshot helpers do not mutate store contents.
- Run `python -m pytest -q`.

B-level:

- Tests for unsupported view warnings.
- Tests for scope/owner summary output.
- Tests for lineage fields when metadata exists.

C-level:

- Optional LanceDB snapshot test when installed.
- Integrate graph-neighborhood snapshots after item 003 lands.
- Integrate recall-trace snapshots after item 004 lands.

## Progress checklist

- [ ] Re-check capability, traversal, trace, and lineage planned items.
- [ ] Define snapshot dataclasses.
- [ ] Implement snapshot helper using public query APIs.
- [ ] Add deterministic ordering and warning behavior.
- [ ] Add in-memory and SQLite tests.
- [ ] Document observer boundaries and unsupported-view behavior.

## Guidance for the implementing agent

Do not let inspection turn into control. If a feature would edit memory,
select prompt context, or create access events, it belongs in a separate writer
or host-layer task. This item is read-only on purpose.
