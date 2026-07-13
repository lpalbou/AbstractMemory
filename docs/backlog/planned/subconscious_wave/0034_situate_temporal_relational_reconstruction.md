# Planned: situate() — temporal + relational context reconstruction

## Metadata
- Created: 2026-07-12
- Status: Planned
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None — executes the maintainer's standing temporal-graph
  hard requirement inside the reserved seam label.

## Context
Maintainer (2026-07-12): "'put me back at that time' (or more like: what
was I doing during/when X (time) or when I met X (relational)) is
important. it's essentially rebuilding a full context at a given time, to
help us continue on that path we wouldn't continue at the time. HOWEVER,
when doing so, the identity has evolved, which can help (or not) the
resolution of that path." The seam already reserves
admission="historical" as "future situate() surface" and journal reads
carry until_seq "situate() groundwork". Fork reference: time_anchor mode
(snapshot resolution + branch trail + selector decisions + approximation
labeling) — battle-tested composition shape.

## Current code reality
- Primitives all exist: `journal.seq_at(iso)`, `snapshots(until_seq)`,
  `traces(until_seq)`, `events(until_seq)`, `compute_activation(at_seq)`,
  `binding_states(..., as_of)`, `closure_exclusions(journal, as_of)`,
  `self_records_read(..., as_of)`, diary projections queryable by scope.
- `admission="historical"` reserved in seam.py; NO composed verb exists.
- No relational anchor resolution anywhere ("when I met X").

## Problem
Rebuilding "what was I doing / believing / feeling then" requires hand-
composing six reads; nobody does it, so abandoned paths cannot be resumed
with their context, and the observer's scrub is the only time view.

## What we want to do
New module `situate.py` + facade verb:

1. **Anchor resolution**:
   - temporal: ISO timestamp or seq (`seq_at`);
   - relational: `participant="person:X"` with `occurrence="first"|"last"`
     → resolve to the seq of the first/last record stamped with that
     participant (works-or-loud: unknown participant refuses naming the
     namespace rule).
2. **The composed read** (pure; deposits NOTHING; journal untouched):
   - moment: the nearest trace+snapshot at-or-before the anchor (what the
     mind was actually holding — the fork's snapshot resolution);
   - activity: top-K activation at_seq (what was warm);
   - period: records whose observed_at falls in a window around the
     anchor (wall-clock life);
   - elected: diary projections in the window (act-frames; private words
     never leave the book);
   - then_identity: self_records_read(as_of=anchor_seq) — who I WAS;
   - identity_evolution: the delta between then_identity and the current
     identity read (records added/closed/superseded since) — the
     maintainer's nuance surfaced as DATA: the evolved self reads the
     past and sees what changed in itself;
   - every handle labeled admission="historical".
3. **Continuation hook**: the result carries the period's open
   questions/problems/commitments (diary reads windowed at the anchor) so
   "continue on that path" starts from the tensions of that moment.

## Why
The temporal graph is a hard requirement of the maintainer's model; every
primitive was built for it; this is the missing 200-line composition that
makes it real for entities, hosts, and the observer alike.

## Requirements
- Pure read; no deposits, no journal writes (v1 — an audit-event variant
  can come later with its own ruling); as_of boundary validation like
  reconstruct.
- Window/K/token bounds as declared parameters (SituateBudget dataclass,
  no magic numbers).
- Deterministic ordering everywhere.
- Anti trapped-in-the-past: historical labels on every handle; the result
  is a READ, hosts must not commit it as if displayed memories were
  re-lived (documented contract line).

## Scope
Engine only: `situate.py`, facade `MemorySystem.situate(...)`, exports,
tests. Host prompt-rendering is the runtime's lane.

## Non-goals
- No auto-deposits, no STM mutation, no re-anchoring of activation.
- No LLM narration of the period.

## Dependencies and related tasks
- 0031 P1-5 (this executes it); folds/attention/self_component reads.

## Expected outcomes
- situate(iso) returns the moment/activity/period/elected/then-identity
  composition with historical labels (test-pinned).
- situate(participant=..., occurrence="first") anchors at the first
  encounter (test-pinned).
- identity_evolution names records added/closed since the anchor
  (test-pinned).

## Validation
- Unit: anchor resolution (temporal, relational, invalid); composition
  correctness on a scripted home; purity (journal byte-identical before/
  after; access counts unmoved); boundary validation.

## Progress checklist
- [x] situate.py + budget dataclass (validated bounds, zero=nothing;
      scope-overlapping moment + anchored snapshot; per-scope MAX
      activation fold; tensions resolution-folded as-of anchor —
      adversary P1.2-P1.5; period_axis + token_exhausted honesty labels)
- [x] facade + exports (`MemorySystem.situate`)
- [x] tests + CHANGELOG (test_situate.py, 11 pins incl. SQLite purity)

Status note (2026-07-12): implemented + adversary-reviewed (no P0s) +
fixes absorbed; uncommitted. Known v1 limit, labeled in module docstring:
bind-state flips are not diffed in identity_evolution. Entity-facing
exposure (a tier-1 tool) is a runtime-lane follow-up, not authorized yet.

## Guidance for the implementing agent
Compose existing folds — write no new scans. If a read needs something the
journal protocol lacks, STOP and file the seam delta instead of widening a
backend ad hoc.
