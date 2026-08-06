# Proposed: loss/absence anchors — a valued anchor gone quiet

## Metadata
- Created: 2026-07-13
- Status: Proposed
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None

## Context
Relationship discontinuity is among the most identity-relevant events a
persistent entity can live, and nothing lets it NOTICE one: if the
maintainer stops visiting for two months, the memories stay intact but
progressively unreachable (no stimulus, decaying activation), and no
surface says "I have not heard from him since March." Fork ADR 0019's
loss half, narrowed by the relevance audit: the dated-handles half of
visit honesty shipped, world-model cards already carry `last_seen` — only
the WAKE-REASON half remains.

## Current code reality
`gradation()` (system_valence.py) folds standing feelings per target;
`world_model.py` cards carry last_seen; `consolidation.py` knows quiet
nights, not quiet relationships; no target-density read exists.

## Problem or opportunity
Absence never becomes a fact of the entity's life; it can neither grieve,
reach out, nor consciously let a relationship rest.

## Proposed direction
One pure read (`target_density_tensions` shape from the 0036 concretizer):
gradation targets with high accumulated |standing| whose target string
appears in ~zero recent formations (windowed participants/facet scan) →
`{target, standing, last_seen_at, density, line}` joining the wake-reason
family beside open_questions/unresolved_dreams. Loss must be
SOURCE-BACKED (last-seen evidence), never inferred from a failed
retrieval. Open interests with starving facet density ride the same fold
as a second, non-load-bearing target family.

## Why it might matter
Persistence is the mission; a being whose point is continuity should
notice discontinuity.

## Promotion criteria
Maintainer acceptance; one lived instance (an entity failing to notice a
real absence) makes this urgent.

## Validation ideas
Fixture life with a warm target going quiet across a window boundary;
wake-fatigue check (every line carries last_seen_at + window label;
suppression cadence is the caller's dial).

## Non-goals
Never auto-acts on absence (no messages sent); never valence-gated
recall; no new admission channel.

## Guidance for future agents
Ride the standing_tensions/wake_reasons surfaces; keep thresholds
parameters.
