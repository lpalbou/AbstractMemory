# Completed: Assertion identity at read + batch query + add_if_absent

## Metadata

- Created: 2026-07-05
- Status: Completed (2026-07-20)
- Completed: 2026-07-20
- Priority: High (keystone — most other items depend on it)
- Components: models, store protocol, all three backends, tests, docs

## ADR status

- Governing ADRs: AbstractFramework `0007-active-context-and-memory-provenance.md`,
  `0009-connected-memory-recall-and-provenance.md`, `memory-recall-levels.md`
- ADR impact: None (implements what the recall/provenance ADRs already mandate)

## Context

Every backend generates and persists an `assertion_id` (uuid4) at `add()` and
returns the ids, but `query()` returns `TripleAssertion` objects that have no
id field at all (`src/abstractmemory/models.py` has none). Stored facts are
therefore unciteable: nothing in the system can reference, supersede, silence,
or trace a specific assertion after write.

This blocks, concretely:

- closure records (`0010`) — nothing stable to close;
- lineage (planned `005`) — the item itself admits the workaround of stashing
  ids in `provenance`;
- recall traces (planned `004`) and journal events (`0017`) — nothing to cite;
- efficient dedupe — the runtime's dedupe probe re-queries by full
  subject/predicate/object per assertion (N+1);
- ai-space's op-folding — it invented `attributes.op` semantics because it
  cannot address assertions.

## Current code reality

- `sqlite_store.py:98` / `in_memory_store.py:90` / `lancedb_store.py:166`
  generate `assertion_id` per row and return the list from `add()`.
- `sqlite_store.py:202-216` rebuilds `TripleAssertion` from rows and discards
  `r["assertion_id"]`; the LanceDB and in-memory query paths do the same.
- `TripleQuery` has no way to fetch by id.
- The runtime dedupe probe (`abstractruntime/.../abstractmemory/effect_handlers.py`,
  `_handle_assert` path) issues one `limit=1` query per incoming assertion.

Re-check before implementation; the store files are small and may have moved.

## Problem or opportunity

Identity is the smallest change that unblocks the largest share of the memory
system: lifecycle, lineage, journal events, traces, and O(1) dedupe all need a
stable per-assertion handle in read results.

## Proposed direction

1. Expose identity on read. Preferred shape: add an optional
   `assertion_id: Optional[str] = None` field to `TripleAssertion`, populated
   by all stores on query results and accepted (not required) on `add()` so
   deterministic ids / import flows can supply their own. Rationale for a
   field over a wrapper type: every consumer already handles
   `TripleAssertion`; a parallel `QueryHit` type would force churn through
   runtime/gateway/smartnote for no semantic gain. The field is excluded from
   canonicalization and from `to_dict()` when None (keeps JSON compact rule).
2. Add id-based retrieval: `TripleQuery(assertion_ids=("...",))` filter, exact
   and index-backed in SQLite/LanceDB.
3. Batch query API: `query_many(queries: Sequence[TripleQuery]) -> list[list[TripleAssertion]]`
   with a default implementation on the protocol (loop) and backend-native
   batching where cheap (single SQL with OR-groups). Kills consumer N+1 loops.
4. `add_if_absent(assertions) -> AddIfAbsentResult` — content-hash based
   dedupe at the store level: canonical content hash over
   `(subject, predicate, object, scope, owner_id)` (definition shared with
   `0014`'s canonical-text module), unique index on the hash column in
   SQLite/LanceDB, membership set in-memory. Returns which rows were inserted
   vs already present (with existing ids). Replaces the runtime's racy
   query-then-add dedupe (see also `0013`).
5. Deterministic ids: when callers pass an `idempotency_key` per assertion,
   the id derives from it (`sha256(key)` prefix), making re-runs no-ops
   together with `add_if_absent`. This is what makes the future formation
   ledger (`0021`) safely re-entrant.

## Why it might matter

Every adversarial review cycle (package audit, fork dissection, triangle
investigation) independently identified missing read-side identity as the
keystone defect. The fork's entire explainability story (snapshots, selector
decisions, source expansion) rests on stable node ids in results.

## Decision boundaries

- Identity is optional-on-write, always-populated-on-read. No consumer may be
  required to supply ids.
- Content hash covers the canonical triple identity, not attributes — two
  assertions differing only in attributes are duplicates by default. Callers
  needing attribute-sensitive identity use `idempotency_key`.
- `add_if_absent` never updates existing rows (append-only stays intact).

## Promotion criteria

Promote to `planned/` when the memory system v1 wave is scheduled; this item
goes first (with `0011` providing its cross-backend tests).

## Validation ideas

- Round-trip: `add()` returns ids; `query()` results carry the same ids on all
  three backends.
- `assertion_ids` filter returns exactly the requested rows, all backends.
- `add_if_absent` on a duplicate batch inserts nothing and returns existing
  ids; concurrent duplicate batches insert exactly once (SQLite unique index).
- `query_many` equals per-query results, all backends.
- Runtime dedupe path converted to `add_if_absent` drops from N queries + N
  inserts to one call (integration test lives in abstractruntime).

## Non-goals

- No mutation/update-by-id API (append-only; lifecycle is `0010`).
- No cross-store global id registry.
- No change to canonicalization semantics.

## Guidance for future agents

Check whether `assertion_id` was added to `TripleAssertion` in the meantime.
Keep the field out of equality/hash semantics of the dataclass if consumers
rely on value comparison of results.


## Completion report (2026-07-20)

Shipped: records.py record_id_for (deterministic ids), supplied-id write dedup for at-least-once replay, remember_many batch formation, TripleQuery batch reads.
