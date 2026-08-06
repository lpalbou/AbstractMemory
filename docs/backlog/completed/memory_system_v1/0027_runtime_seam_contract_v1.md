# Completed: Runtime seam contract v1 (frozen, negotiated via a2a thread 0001)

## Metadata

- Created: 2026-07-05
- Status: Completed (2026-07-20)
- Completed: 2026-07-20
- Priority: High (external contract — the runtime is building against it NOW)
- Components: seam dataclasses module, MemorySystem protocol surface, tests

## ADR status

- Governing ADRs: AbstractFramework `0002-effect-system-design.md`,
  `0007-active-context-and-memory-provenance.md`
- ADR impact: Needs new ADR at promotion (cross-package seam contract is
  durable policy).

## Context

The runtime agent (owner of `abstractruntime/`) and this package negotiated
the runtime⇄memory seam as equal partners in
`a2a/threads/0001-runtime-memory-orchestration/` (messages 001–004,
2026-07-05). The seam was CONFIRMED in message `004-memory--to--runtime.md`,
which carries the authoritative frozen shapes. The runtime is building its
`MEMORY_RECALL` / `MEMORY_ACCESS` effect wrappers, a stub `MemorySystem`, and
the emergence-experiment harness against it immediately — this package must
implement the same shapes (items `0017/0018/0020/0026`) without drift.

## Current code reality

- None of the seam exists in code yet on either side; the a2a thread is the
  negotiation log, this item is the system-of-record capture.
- Authoritative shape reference: `a2a/threads/0001-runtime-memory-orchestration/004-memory--to--runtime.md`
  (do not restate-and-drift; implement FROM that message, mirror the final
  code back here at promotion).

## Problem or opportunity

Two packages building concurrently against a negotiated contract need one
frozen definition with explicit stability guarantees, or the stub-to-engine
swap fails.

## Proposed direction

Implement the seam exactly as frozen in a2a 0001/004:

1. Dataclasses (all frozen, JSON-safe): `Stimulus` (cue_text, patterns,
   anchor_record_ids, participants, optional precomputed embedding,
   `as_of: int | None` journal seq), `RecallBudget` (candidates/shelf/tokens/
   reserved_slots/anchor_cues/hops/edges/min_activation/deadline),
   `MemoryHandle` (record_id, kind, title, digest, token_estimate,
   per-channel `relevance`, decomposed `activation`
   {base_level, spread, total}, mandatory `cues`, binding, scope, owner_id,
   provenance), `ReconstructionResult` (trace_id, view, `as_of_seq`
   high-water mark, handles, edges [working_set view], dropped,
   selector_route, stop_reason, warnings, budget_spent),
   `ActiveMemorySnapshot` (refs + display metadata, never payload copies).
2. Protocol surface: `reconstruct(stimulus, *, scopes, budget, view=
   "shelf"|"working_set", escalation_reason, journal)`,
   `commit_selection(trace_id, used_record_ids, *, prompt_token_estimate)`,
   `reinforce/attenuate(record_id, *, reason, weight, ttl_activity, scope,
   owner_id)`, `refocus(*, reason, scope, owner_id)`, `seq_at(iso_ts)`,
   `activation(ids, *, scope, owner_id, at_seq)` — alongside unchanged
   layer-1 `add/query`.
3. Stability contracts (promised to the runtime; breaking any is a
   cross-package incident):
   - `reconstruct` is a pure read of (truth ≤ as_of, journal ≤ as_of,
     stimulus, params); `journal=True` appends trace + INERT audit events
     only; `journal=False` writes nothing;
   - `commit_selection` is the ONLY strengthening path; the package derives
     `selected` + `co_selected` pair-trails itself; deliberate acts require
     `reason`;
   - relevance admits, activation reorders; `min_activation` is working-set
     membership only;
   - every result carries `as_of_seq`; replay with `Stimulus(as_of=seq)` is
     bit-exact under a frozen embedding space (manifest-enforced, loud on
     drift);
   - actionable errors; `#FALLBACK`-labeled degradations in `warnings`.
4. Division of triggers (agreed): runtime owns ALL triggers (stimulus at turn
   start; optional budget-pressure recall pre-compaction calls the same pure
   read with a smaller budget); this package never self-fires and
   consolidation stays in `sleep()` (`0023`).
5. Seam conformance tests: a fixture proving the runtime's stub and this
   package's engine produce interchangeable JSON for identical inputs
   (drop-in swap guarantee), including `as_of` replay determinism.

## Why it might matter

This is the contract that lets the runtime orchestrate memory (the
maintainer's core requirement) and the falsifiable emergence experiment run —
with a stub-first path that de-risks both sides' schedules.

## Decision boundaries

- Shape changes after this point go through the a2a thread first, then this
  item — never unilaterally in code.
- Maintainer-pending internals (decay math, spreading params, inhibition,
  working-set sizing — a2a 0001/002 asks 1–4) may change ENGINE behavior but
  not these shapes.

## Promotion criteria

Promote together with `0020`/`0026` implementation; the runtime's harness
existence makes this the first externally-consumed item of the wave.

## Validation ideas

- JSON round-trip every dataclass (asdict → json → parse → equal).
- Purity: same inputs + `as_of` → byte-identical serialized results, twice,
  across processes.
- `journal=False` leaves journal byte-identical.
- Stub-swap test shared with abstractruntime (their harness, my engine).
- Contract regression: audit events provably never change scores or ordering.

## Non-goals

- No prompt assembly, trigger logic, or effect envelope definitions (runtime
  owns those).
- No renegotiation of shapes inside implementation PRs.

## Guidance for future agents

Read a2a thread 0001 in full first; message 004 is authoritative for shapes,
002 §3 for the event schema, 003 for the amendments' rationale. If the
runtime's stub diverges from 004, raise it on the channel — do not silently
adapt.


## Completion report (2026-07-20)

Shipped and FROZEN: seam.py dataclasses (a2a 0001/004) — reconstruct pure read, commit_selection sole strengthening path, as_of anchors journal signals; cross-package tests pin it from both sides.
