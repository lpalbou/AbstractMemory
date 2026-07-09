# Proposed: Store concurrency and thread-safety contract

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: High
- Components: sqlite_store, lancedb_store, in_memory_store, docs, tests

## ADR status

- Governing ADRs: AbstractFramework `0018-durable-run-gateway-and-remote-host-control-plane.md`
  (gateway execution model), `0022-orchestrator-host-and-runtime-daemonization.md`
- ADR impact: None (documents and implements a contract; no new policy)

## Context

The stores were written single-threaded; their primary consumer is not. The
gateway builds one store per bundle host and executes memory effects on a
`ThreadPoolExecutor` (tick workers), and the gateway HTTP KG routes open
per-request connections against the same files.

Verified failures (2026-07-05 audit):

- `SQLiteTripleStore` holds ONE connection created with the default
  `check_same_thread=True` (`sqlite_store.py:53`); the first query from
  another thread raises `sqlite3.ProgrammingError`. With
  `ABSTRACTGATEWAY_MEMORY_STORE_BACKEND=sqlite`, the first `memory_kg_*`
  effect on a tick worker fails, always.
- No WAL mode, no `busy_timeout`: reader/writer contention under default
  DELETE journaling for the per-request route connections.
- LanceDB first-write create race loses batches (detailed in `0012`).
- In-memory store has zero synchronization (`in_memory_store.py`) — GIL makes
  it tolerable, not correct (result lists can interleave with writers).
- Consumer-level read-modify-write dedupe race: the runtime's query-then-add
  probe means two concurrent runs asserting the same triple both insert.
  `0009`'s `add_if_absent` + unique content-hash index is the store-level fix.

## Current code reality

See citations above. The Open Codex Memory prototype sidesteps all of this
with an app-level single-writer (`Arc<Mutex<Store>>`) — a model that does NOT
port to the gateway's thread-pool + per-request-connection reality, so this
package must define its own contract.

## Problem or opportunity

"Which threads may touch a store?" currently has no documented answer and the
de facto answer for SQLite is "only the constructor's". A package this low in
the stack must state and implement its concurrency contract explicitly.

## Proposed direction

1. Contract (documented in `docs/stores.md`): a store instance is safe for
   concurrent use from multiple threads within one process; multi-process
   access is safe for SQLite (WAL) with documented staleness/locking
   semantics, and follows LanceDB's documented multi-process behavior for
   Lance; in-memory is process-local by definition.
2. SQLite implementation: `check_same_thread=False` + one internal
   `threading.RLock` around all cursor use; `PRAGMA journal_mode=WAL`;
   `PRAGMA busy_timeout` (configurable, sane default); `PRAGMA synchronous=NORMAL`
   documented. Existing databases get WAL enabled on open (safe, reversible).
3. LanceDB: lock around the create/add window (with `0012`'s
   create-if-not-exists); document Lance's optimistic-concurrency behavior for
   concurrent appends and surface conflicts as retried-or-raised, never
   swallowed.
4. In-memory: same RLock pattern; results already isolated per `0011`.
5. Unique content-hash index (from `0009`) so `add_if_absent` is atomic at the
   storage layer — the dedupe race dies at the store, not in consumer code.
6. A small threaded stress test per backend in the conformance suite
   (`0011`): N writer threads + M reader threads, zero exceptions, zero lost
   writes, consistent counts.

## Why it might matter

This is a guaranteed crash today for the SQLite backend under the gateway — a
configuration the gateway explicitly offers. Correctness under the framework's
actual execution model is not optional hardening; it is the minimum for the
"three first-class backends" claim.

## Decision boundaries

- Locking granularity: coarse per-store RLock is acceptable at this scale
  (single-user local-first, 10k–1M triples); do not build finer-grained
  locking without benchmark evidence.
- No daemon/server mode to "solve" concurrency (framework is local-first
  in-process; the gateway is the multiplexing point).

## Promotion criteria

Promote with the wave; must land before or with `0012` (they touch the same
files) and before any journal work (`0017` inherits the same contract).

## Validation ideas

- Cross-thread smoke: construct on thread A, query/add on thread B — passes on
  all backends.
- Threaded stress (see above) green on all backends.
- SQLite: WAL active (`PRAGMA journal_mode` returns `wal`), busy_timeout set;
  concurrent process-B reader sees committed writes.
- Concurrent duplicate `add_if_absent` batches: exactly one insert.
- Gateway integration check (in abstractgateway): sqlite backend memory
  effects succeed from tick workers.

## Non-goals

- No async API (`asyncio`) in this wave.
- No distributed/multi-host coordination.
- No connection pooling framework; one guarded connection per store is enough
  at target scale.

## Guidance for future agents

Keep the lock inside the store (self-contained safety), not in consumers.
Verify the per-request connections in the gateway KG routes also benefit
(WAL) — if the route constructs its own store instances, staleness semantics
should be documented there too.
