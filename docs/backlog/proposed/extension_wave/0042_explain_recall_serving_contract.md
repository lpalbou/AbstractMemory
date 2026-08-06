# Proposed: explain_recall() — the recall-explanation serving contract

## Metadata
- Created: 2026-07-13
- Status: Proposed
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None

## Context
Every cue-dilution and bridge-attractor diagnosis this month was a
hand-written forensic script, while the engine already answers the
question: `recall_reads.py` ships `recall_history` (per-trace status) and
`absence_diagnosis` (structural why-not). What is missing is ONE serving
shape an observer/gateway can render — "why did/didn't record X surface
in THIS recall?" in pixels.

## Current code reality
`recall_history`/`absence_diagnosis` shipped and tested; no composed
serving dict; the observer has no recall-explanation surface. Dependency
finding (relevance audit): until `search_memory` rides `probe()`
(memory_system_v1 0031-3), voluntary exploration reads as absence — a
truth surface that lies is worse than none.

## Problem or opportunity
Memory debugging requires the memory seat; the operator cannot ask the
obvious question at a glance.

## Proposed direction
`explain_recall(store, journal, record_id, *, trace_id=None) -> dict`
composing the two reads: status (selected/dropped/candidate_only/absent),
admission (self/stm/stimulus/both), per-channel relevance parts, shelf
position vs cut + budgets, origin, absence reasons. HONESTY RULE:
activation reports only what the trace RECORDED at recall time
(`{"recorded": false}` + "not recorded in this trace" on old traces) —
never recomputed fresh numbers presented as the explanation.

## Why it might matter
Turns the diagnosis method that worked live ("felt absence decomposed
measurably") into a surface anyone can use.

## Promotion criteria
0031-3 (probe migration) landing, or maintainer acceptance for the
engine-side dict alone (pixels ride the observer redesign).

## Validation ideas
Golden traces: selected, budget-cut, silenced, and never-formed records
each explain correctly; old-trace nulls carry the honest label.

## Non-goals
No HTTP here (host lane); no recomputation-as-explanation; explaining is
not use (no deposits).

## Guidance for future agents
Compose, don't reimplement; version by field presence, not schema forks.
