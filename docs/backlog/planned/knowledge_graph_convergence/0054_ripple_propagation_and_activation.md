# Ripple propagation and activation (ADR 0001, the process)

Created: 2026-10-27 (operator ruling, [ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md)).
Track: `knowledge_graph_convergence` · Priority: High · Status: Planned

## Summary
Implement in AbstractMemory the whole ripple of [ADR 0001](../../../adr/0001-altered-memories-ripple.md): from a
change record, compute reliance-weighted impact on connected memories, gate it through the activation function
(accumulated potential, mass, smooth gate, floor, refractory period, loop gain below one), reconsider the activated
memories through an injected reader under a budget, measure their change, propagate onward, record every gate
decision and everything left out, and settle unchanged reconsiderations without a reader call.

## Why
The ripple was first prototyped inside AbstractNote. The operator ruled (2026-10-27) that it belongs to
AbstractMemory so every consumer, AbstractEntity first, has memories that revise what leaned on them.

## Current code reality
- 2026-11-08: the first slice landed as [0061](../../completed/knowledge_graph_convergence/0061_ripple_v1_over_the_task_queue.md) (the logistic gate and its
  constants in `activation_gate.py`; propagation, the unchanged settle, budget and `left_out`, gate decisions on
  record, sleep consolidation in `ripple.py`, over the 0060 task queue). What remains here: mass, refractory across
  passes, edge learning, closures caused by a ripple, the calibration on the entity homes' reader.
- 2026-11-10: 0061 completed (abstractmemory 0.5.0, `5c6136b`); nothing seeds a ripple yet (root 1172 / 1171 paused),
  memory's side of that seam is `proposed/ripple_wave/0063_ripple_v1_consumer_seam.md`.
- Before 0061: none of the process existed. The primitives are planned in
  `proposed/ripple_wave/0001_change_records_and_ripple_primitives.md` (change records with magnitude, closure
  causes, `narrow_assertion`, ripple-aware `maintenance_due`, the bound read).
- AbstractNote (prototype to absorb, not to keep): ADR 0008 and its lane R6 (2026-10-20/21: calibrated thresholds,
  decay 0.5, floor 0.1, one hop per pass, budgeted stage, no-call settle); code on the unmerged branch
  `retro/integration`: `src/abstractnote/recall/propagation.py`, `src/abstractnote/recall/activation.py`; design
  brief `abstractnote/untracked/briefs/R6-propagation-design.md`.

## Handover from AbstractNote
AbstractNote backlog 0035 (`abstractnote/docs/backlog/planned/memory_convergence/0035_hand_the_ripple_prototype_to_abstractmemory.md`)
splits `retro/integration` into note-specific parts (stay there) and generic parts (come here: propagation,
activation, dependency-bounded invalidation, no-call settle, calibrated constants and their tests).

## Scope
In: propagation, activation, budget and `left_out`, reconsideration through an injected reader, calibration of the
summary-distance threshold against the reader's rewrite noise (constants in one module with the calibration
quoted), docs (`memory-system.md` "Sleep and dreams"). Out: what a reader prompt says for one consumer.

## Dependencies
`proposed/ripple_wave/0001` (promote it with this item), 0051 (revisions carry ripple causes).

## Validation
ADR 0001's validation list, item by item (unit tests with mutants, calibration report, the project→person
scenario); the AbstractNote prototype's tests ported to the public API as a parity check.
