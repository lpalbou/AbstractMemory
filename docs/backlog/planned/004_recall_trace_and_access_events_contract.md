# Planned: Recall trace and access events contract

## Metadata

- Created: 2026-05-05
- Status: Planned
- Completed: N/A
- Priority: Medium
- Components: AbstractMemory data contracts, Runtime/Gateway/Observer integration guidance

## Context

Memory recall is more than a query result. A host often needs to know why a
memory search happened, which scopes were searched, which candidates were
visited, why traversal stopped, and which results became active context.

AbstractMemory should support audit-friendly recall telemetry as a contract,
while leaving active prompt selection and recall policy to higher packages.

## Current code reality

- Store queries currently return only `TripleAssertion` objects.
- Query results do not include assertion ids unless callers store ids in
  provenance/attributes themselves.
- There is no `RecallTrace`, `MemoryAccessEvent`, or event store type.
- There is no active-memory snapshot model in AbstractMemory.
- The framework ADRs distinguish durable memory from active context; Runtime or
  host packages own prompt-visible selection.

Re-check whether planned item 002 has added capabilities or item 003 has added
graph walk result metadata before implementing this contract.

## Problem

Without trace contracts, hosts may implement recall observability differently:

- one package logs only the query text;
- another logs selected assertions but not skipped candidates;
- another stores access history as a mutation of the assertion itself;
- observer UIs cannot explain why memory influenced a turn.

That makes recall hard to debug and can blur the line between durable memory,
derived attention metadata, and active prompt context.

## What we want to do

Define storage-neutral JSON-serializable contracts for recall traces and memory
access events. These contracts should be usable by Runtime/Gateway/Flow without
making ordinary `TripleStore.query(...)` mutate memory or select active context.

## Why

Auditable recall is central to safe memory. It should be possible to answer:

- what was the normalized recall need?
- which scopes and backends were searched?
- what candidates were considered?
- what graph paths were expanded?
- why did recall stop?
- which records, if any, became active context?

## Requirements

- Keep recall trace writing optional.
- Do not mutate `TripleAssertion` truth when a memory is accessed.
- Do not make ordinary `TripleStore.query(...)` write access events.
- Represent searched scopes explicitly; avoid a bare `global=true` flag.
- Record recall effort/level when supplied by a host.
- Record candidate-set fingerprints for reproducibility.
- Record budgets and stop reasons:
  - max candidates;
  - max hops;
  - max tokens or token estimate;
  - timeout/deadline;
  - enough evidence;
  - low confidence;
  - operator stop.
- Record warnings and partial-result flags.
- Link access events to trace ids when available.
- Keep contracts JSON-compatible and stable enough for audit export.

## Suggested implementation

Add dataclasses or TypedDicts in a small module such as
`src/abstractmemory/trace.py`:

```python
@dataclass(frozen=True)
class RecallTrace:
    trace_id: str
    query: str
    query_fingerprint: str
    recall_level: str | None
    searched_scopes: tuple[dict[str, str], ...]
    candidate_ids: tuple[str, ...]
    selected_ids: tuple[str, ...]
    visited_terms: tuple[str, ...]
    budgets: dict[str, int | float | str]
    stop_reason: str
    partial: bool
    warnings: tuple[str, ...]
    provenance: dict[str, object]
```

```python
@dataclass(frozen=True)
class MemoryAccessEvent:
    event_id: str
    trace_id: str | None
    assertion_id: str | None
    access_kind: str
    scope: str | None
    owner_id: str | None
    observed_at: str
    provenance: dict[str, object]
```

Keep the first pass as data contracts plus serialization helpers. Add a concrete
event store only if a host package needs AbstractMemory to persist these records
directly.

## Scope

- Contract docs for recall traces and access events.
- JSON serialization/deserialization helpers.
- Tests for stable serialization, ordering, and no assertion mutation.
- Guidance showing which layer owns writes:
  - AbstractMemory: contract and optional storage helper.
  - Runtime/Gateway/Flow: recall policy, trace creation, active context.
  - Observer: read-only rendering.

## Non-goals

- No active prompt packing.
- No automatic attention ranking.
- No hidden access logging in `query(...)`.
- No UI implementation.
- No requirement that every AbstractMemory user write traces.

## Dependencies and related tasks

- AbstractFramework central ADRs:
  - `0004-observability-strategy.md`
  - `0007-active-context-and-memory-provenance.md`
  - `0009-connected-memory-recall-and-provenance.md`
  - `0016-tool-calling-pipeline-and-responsibility-boundaries.md`
- Related planned work:
  - `002_sqlite_database_compatibility_and_store_capabilities.md`
  - `003_bounded_graph_traversal_over_triples.md`
  - `007_read_only_memory_observer_contract.md`

## Expected outcomes

- Higher packages can log recall decisions in a consistent shape.
- Access events remain append-only telemetry, not truth mutation.
- Observer/audit tools can explain recall without knowing every host's private
  log format.
- AbstractMemory remains usable without telemetry.

## Validation

A-level:

- Unit tests for JSON round-trip of trace and access event records.
- Unit tests that stable fingerprints are deterministic for the same inputs.
- Run `python -m pytest -q`.

B-level:

- Tests covering partial recall, warnings, and stop reasons.
- Tests linking a graph-walk result from item 003 into a recall trace if that
  item has landed.
- Docs examples showing active context is referenced, not duplicated.

C-level:

- Optional integration fixture that simulates a host recall operation and emits:
  query, candidates, traversal steps, selected ids, and access events.
- Audit/export sample that distinguishes durable memory from active selection.

## Progress checklist

- [ ] Re-read ADRs on active context, recall, and observability.
- [ ] Decide whether this task is contracts-only or includes optional storage.
- [ ] Define dataclasses/TypedDicts and serialization helpers.
- [ ] Add tests for JSON stability and no mutation.
- [ ] Document ownership boundaries by package.
- [ ] Update observer/read-only backlog item if the trace shape changes.

## Guidance for the implementing agent

Be precise about ownership. AbstractMemory can define and optionally persist
recall telemetry, but it must not decide that a memory is prompt-visible. That
decision belongs to the host/runtime layer and should be recorded as a reference
in trace data, not hidden inside the store query path.
