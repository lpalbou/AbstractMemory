# Proposed: Memory journal (events/traces/snapshots) + append-only scope bindings

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: High
- Components: new journal module + per-backend implementations, bindings fold, tests, docs

## ADR status

- Governing ADRs: AbstractFramework `0007-active-context-and-memory-provenance.md`,
  `0004-observability-strategy.md`
- ADR impact: Needs new ADR (bindings visibility model + journal event
  taxonomy are durable cross-package contracts; write at promotion)

## Context

Two structural pieces the high-level memory system needs, both proven in the
Open Codex Memory prototype and deliberately kept OUT of the triple truth
tables:

1. An append-only JOURNAL: access events (the neurotransmitter substrate,
   `0018`), reconstruction traces (`0020`), active-memory snapshots, and
   closure records (`0010`) — sidecar records with a different lifecycle than
   assertions (no valid-time, never superseded, write-heavy, read by "recent
   N per scope").
2. SCOPE BINDINGS: append-only latest-wins visibility events per
   `(record_id, scope, owner_id)` with two orthogonal axes —
   `search_state: indexed|hidden` × `prompt_state: active|inactive`
   (invariant: hidden ⇒ inactive) and a candidate lifecycle label
   (`none|inactive_candidate|reviewed|promoted|rejected|superseded`).
   Bindings answer "where is this record visible and how", which closure
   records (truth lifecycle) and the immutable `scope`/`owner_id` write
   partition cannot express. Promotion to a broader scope appends a binding —
   it never copies assertions.

Design decisions carried from the fork dissection (with reasons):

- Events are NOT triples with reserved predicates: they would pollute
  FTS/vector indexes, break "structured queries are complete", and require
  excluding reserved predicates from every query path forever. Separate
  storage, one protocol.
- Bindings are events, not mutable state: visibility changes become auditable
  history for free (the fork's most load-bearing safety property: everything
  machine-created defaults to indexed + prompt-INACTIVE, so a bad write costs
  zero prompt tokens).
- Fork regrets to avoid: mutable probe traces (make traces append-only);
  candidate lifecycle buried in provenance JSON (make it a typed column);
  token-estimate columns in durable schema (derive, don't store).

## Current code reality

- Nothing exists: no journal, no bindings, no traces. `0009`/`0010` may land
  closure records in a minimal dedicated table first; this item generalizes
  the storage home.
- Backends: SQLite gains sidecar tables in the same file
  (`sequence INTEGER PRIMARY KEY AUTOINCREMENT` is the event sequence; two
  indexes: `(scope, sequence DESC)`, `(created_at)`); LanceDB gains sidecar
  tables in the same db dir (append-only fits Lance) or an SQLite sidecar —
  hidden behind the protocol; in-memory is lists+dicts (volatile, warned).

## Problem or opportunity

Without the journal there is no attention, no explainability, no
reconstruction traces — the memory system stays a passive row store. Without
bindings there is no safe machine formation (everything lands prompt-visible
or invisible with no middle state) and no scope promotion/election.

## Proposed direction

1. `MemoryJournal` protocol + three implementations:
   `append_events / events(scope, …, since_seq, limit)`,
   `append_binding / bindings(record_id|scope, fold=True)`,
   `append_closure / closures(...)` (home for `0010`),
   `append_trace / traces(...)`, `append_snapshot / snapshots(...)`,
   `selected_count(assertion_id)` (denormalized counter, rebuildable from
   events; incremented ONLY by selected-use events — see `0018`).
2. Record shapes (normative, JSON-serializable dataclasses):
   - `MemoryEvent`: `event_id, seq, kind, assertion_id|record_id, pair_ids
     (trail), weight (signed), ttl_activity, query_fingerprint, trace_id,
     scope, owner_id, observed_at, actor, reason, provenance`;
   - `ScopeBinding`: `binding_id, seq, record_id, scope, owner_id,
     search_state, prompt_state, lifecycle, source
     (remember|election|operator|maintenance|revision), reason, observed_at,
     provenance`;
   - `ReconstructionTrace` / `ActiveMemorySnapshot`: as specified in `0020`.
3. Bindings fold: latest `seq` wins per `(record_id, scope, owner_id)`; shared
   fold module (never per-backend logic). Guards enforced at append:
   hidden ⇒ inactive; raw (untyped) records cannot be bound `indexed` in a
   broad scope without `source="operator"`; summary-kind records (`0021`)
   cannot be indexed without a summarizes link. Broad scopes are
   host-configurable (`broad_scopes={"global"}` default).
4. Visibility integration: retrieval (`0019`/`0020`) folds bindings to build
   its candidate universe; plain layer-1 `TripleStore.query()` remains
   binding-agnostic (structured queries stay complete; the facade applies
   visibility).
5. Journal lines join the JSONL export (`0015`).

## Why it might matter

This is the enabling layer for `0018` (neurotransmitters), `0020`
(traces/shelves), `0021` (safe formation defaults), `0023` (maintenance), and
the observer story — the single biggest step from "row store" to "memory
system".

## Decision boundaries

- Journal grows without bound by design; archival/compaction of JOURNAL
  records (never truth) is host policy, explicitly deferred — `0023`'s report
  surfaces journal pressure.
- Bindings apply to record ids (subjects); per-assertion visibility is closure
  (`0010`), not bindings.
- No global mutable state; every store+journal pair is self-contained.

## Promotion criteria

Promote after Track A lands (needs ids from `0009`, concurrency contract from
`0013`, export from `0015`). First item of Track B.

## Validation ideas

- Fold: enable→disable→enable sequences resolve latest-wins; per-scope
  independence verified.
- Guards: hidden⇒inactive enforced; broad-scope raw binding rejected without
  operator source.
- Sequence monotonicity per (scope, owner) under threaded writers (reuses
  `0013` stress harness).
- Export/import round-trips journal records (`0015`).
- Volatile in-memory journal emits the documented warning once per process.

## Non-goals

- No attention scoring here (that is `0018` — this item only stores events).
- No retrieval changes here (that is `0019`/`0020`).
- No UI/HTTP surface (gateway/observer items live in their own repos).

## Guidance for future agents

Keep the journal protocol minimal and the fold pure. If closure records
already landed in a dedicated table via `0010`, migrate their home here with
the `0015` recipe rather than maintaining two closure stores.
