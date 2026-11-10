# Proposed: ripple v1 has no consumer yet; memory's side of the seam when the runtime starts seeding

## Metadata
- Created: 2026-11-10 (residual of [0061](../../completed/knowledge_graph_convergence/0061_ripple_v1_over_the_task_queue.md))
- Status: Proposed
- Completed: N/A
- Priority: P2 (follows root backlog 1172)

## ADR status
- Governing ADRs: [ADR 0001](../../../adr/0001-altered-memories-ripple.md) (AbstractMemory owns the ripple end to
  end), [ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md)
- ADR impact: None

## Context
Ripple v1 shipped in abstractmemory 0.5.0 (`09686e0`, release commit `5c6136b`): `seed_ripple`,
`settle_reconsideration`, `form_consolidation`, `refresh_ripples`, `revert_ripple`, the reads `ripples` / `ripple`,
and the `ripple.reconsider` / `ripple.consolidate` task kinds on the 0060 queue. It was built ahead of its consumers
on purpose: detection (the entity's `revise` election) and the drain of the ripple kinds are the runtime's and the
gateway's, tracked as root backlog 1172 (proposed, paused) over root 1171 (planned, paused).

## Current code reality (2026-11-10)
- No caller: `seed_ripple`, `settle_reconsideration` and `form_consolidation` have 0 hits in `abstractruntime/src`
  and `abstractgateway/src`.
- The tracked runtime drain (`abstractruntime/identity/authoring.py` `drain_authoring`) leases only `title.author` /
  `digest.author` (`AUTHORING_TASK_KINDS`); no live home ever holds a ripple task.
- `maintenance_due(tasks=)` already reports pending ripple and night-only tasks as due, and `KIND_WINDOWS` leases
  `ripple.consolidate` only in a `night` window (`memory_tasks.py`).
- The gate constants (`activation_gate.py`) are AbstractNote's R7 calibration, never measured on an entity home's
  reader; that calibration is in 0054's scope.

## Problem or opportunity
Shipped code without a caller rots silently: the first real seeding will be the first time the verbs meet a live
home's graph, a real reader's rewrite noise and a real night window.

## Proposed direction
When root 1172 resumes (memory's part only; the election, the prompts and the drain stay the runtime's):
1. Read the runtime's calls in the live artifact and confirm they use the verbs as shipped (an election re-reads the
   seed first; `dry_run` is the bound read; `settle_reconsideration` gets the reader's `unchanged` / `rewritten`).
2. Run a ripple end to end on a COPY of a lived home with the real reader (never the live gateway) and record: hops,
   gate decisions, `left_out`, reconsideration count, and the measured `cosine_distance` of `unchanged` vs
   `rewritten` settles. Feed the numbers to 0054's calibration.
3. Fix in memory whatever the first consumer finds (a named refusal it cannot act on, a missing read field), with a
   red test each.

## Why it might matter
ADR 0001's promise (an altered memory ripples) is only true once something seeds a ripple on a real home.

## Promotion criteria
Root 1172 is promoted to planned, or the operator asks for the ripple live.

## Validation ideas
The end-to-end run above as a scripted proof under `untracked/`; any fix lands with a mutant that turns its test red.

## Non-goals
Building the `revise` election, the drain, prompts or the wake cue (root 1172 / 1171); the rest of the process
(mass, refractory, edge learning, ripple closures: 0054).

## Guidance for future agents
Start from 0061's completion report and `ripple.py`'s module docstring; never seed ripples on the live gateway's homes
(review on copies, `:8080` untouched).
