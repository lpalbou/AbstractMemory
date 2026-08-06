# Proposed: LanceDB backend hardening — explicit schema, create-race, honest failures

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: High
- Components: lancedb_store, pyproject (version pin), migration helper, tests

## ADR status

- Governing ADRs: AbstractFramework `0026-truncation-policy-and-contract.md`
  (labeling degraded paths)
- ADR impact: None

## Context

The LanceDB table schema is currently an accident of the first insert:
`lancedb_store.py:188` strips `None` values from rows and `:191-193` creates
the table by inferring the schema from that first batch. Any column absent
from the first batch (`owner_id`, `valid_from`, `valid_until`, `confidence`,
even `vector` when the embedder was unavailable) never exists.

Verified consequences (2026-07-05 audit, lancedb 0.30.0):

- later `add()` with a previously-absent field raises
  `ValueError: field '...' does not exist in table schema`;
- `active_at` queries raise `RuntimeError: No field named valid_from` on any
  table whose first batch lacked validity windows — which is essentially every
  real table today (no current consumer sets `valid_from`);
- 4 threads adding to a fresh store: 3 crash on the create-table check-then-act
  race (`lancedb_store.py:191-195`), losing their batches;
- `open_table` failure is swallowed (`lancedb_store.py:138-142`,
  `self._table = None`) — a corrupt table reads as an EMPTY store and the next
  add tries `create_table` and fails. Silent data-loss façade;
- the `lancedb` dependency is completely unpinned (`pyproject.toml:44-46`)
  despite version-sensitive behavior having already broken release 0.2.5
  (see CHANGELOG 0.2.6).

## Current code reality

See citations above. Also relevant: non-semantic queries fetch ALL matching
rows and sort in Python (`lancedb_store.py:229-233`) — acknowledged in a code
comment; LanceDB has no ORDER BY pushdown by design, so the honest fix is
column-select pushdown + documented capability, not fake pushdown.

## Problem or opportunity

The vector-capable durable backend — the gateway default — is the most fragile
store in the package. Schema-by-accident cannot support the columns that
`0009`/`0010`/`0014` add (assertion id exposure needs nothing new, but content
hash and manifest columns do), so this must land as ONE schema wave with them
to avoid multiple table rewrites for users.

## Proposed direction

1. Explicit PyArrow schema, defined up front, all columns nullable:
   `assertion_id, subject, predicate, object, scope, owner_id, observed_at,
   valid_from, valid_until, confidence, provenance_json, attributes_json,
   text, content_hash` (from `0009`), plus the fixed-size `vector` column
   created as soon as the dimension is known (from the embedding manifest,
   `0014`, or the first embedded batch). Stop stripping `None` — nullable
   columns carry nulls.
2. Concurrency-safe creation: create-if-not-exists semantics under a process
   lock; the create/add window race removed (see `0013` for the full
   concurrency contract).
3. Honest failures: `open_table` errors surface as errors with a
   `#FALLBACK`-labeled message when any degraded mode is offered; never
   silently treat a broken table as empty.
4. Migration: a one-shot helper that migrates inferred-schema tables to the
   explicit schema via JSONL export/import (`0015` provides the substrate).
   Consumer caution: SmartNote currently catches ALL store-open exceptions and
   silently falls back to a volatile in-memory store — a migration that raises
   at open presents to SmartNote users as total memory loss. The migration
   helper must be callable by hosts BEFORE open, and the runtime/gateway wave
   should surface migration-needed as an actionable error, not an exception
   swallowed by consumers.
5. Pin the dependency: `lancedb>=0.24,<0.31`-style floor+ceiling (adjust to
   reality at implementation), documented in CHANGELOG.
6. Column-select pushdown for non-semantic queries (fetch only needed
   columns), keep Python-side ordering, and report `graph_walk`/ordering
   capabilities honestly through the capabilities descriptor (planned `002`).

## Why it might matter

Every production deployment with the LanceDB backend is one heterogeneous
batch away from crashes today, and `active_at` (the bi-temporal read path
`0010` depends on) is broken on virtually all existing tables.

## Decision boundaries

- One schema wave: this item + `0009`'s `content_hash` + `0014`'s manifest
  land together; do not ship two separate table rewrites.
- No silent auto-migration on open by default; explicit migration invocation
  (host-triggered), with a clear error message when needed.

## Promotion criteria

Promote with the wave, sequenced right after `0009`/`0010` decisions are
final (their columns are inputs to the schema).

## Validation ideas

- Heterogeneous batches (first insert minimal, second full) round-trip.
- `active_at` works on a fresh store whose first batch had no validity fields.
- Concurrent first-writes: N threads, zero lost batches, table created once.
- Corrupt/unopenable table: loud error naming the path and remedy; no empty
  reads.
- Migration: inferred-schema fixture → helper → explicit schema, all rows and
  ids preserved (verified via `0015` export before/after).
- Version pin respected in `pyproject.toml`; CI installs the floor version.

## Non-goals

- No ORDER BY pushdown claims (does not exist in LanceDB by design).
- No index tuning / ANN configuration work (separate performance item later).
- No multi-process write coordination beyond documented semantics (`0013`).

## Guidance for future agents

Verify current LanceDB version behavior first — `create_table(exist_ok=...)`,
prefilter defaults, and `list_tables` shapes have churned across versions and
already broke this package once.
