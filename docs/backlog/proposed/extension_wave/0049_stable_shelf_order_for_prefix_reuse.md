# Proposed: stable shelf-order rendering for prefix-cache reuse

## Metadata
- Created: 2026-07-13
- Status: Proposed
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None

## Context
Core's bloc-seam adversary (commons c1708, research/cache-composability.md
v2 §6) found a zero-physics prompt-cache win in memory's lane: consecutive
turns often share k leading shelf records, but the MEMORIES region is
rendered in RANK order, so any rank churn breaks the longest-common-prefix
and the provider's existing delta/prefix cache re-prefills the whole
region. Rendering the shelf region in STABLE IDENTITY ORDER (rank carried
as an annotation, not as position) preserves LCP reuse across turns with
no cache machinery at all.

## Current code reality
`selection.py`/`shelf.py` return handles ranked; the runtime driver
renders MEMORIES in that order. Rank is currently expressed by position
only. No stability contract exists across turns.

## Problem or opportunity
Free prefix-cache reuse on every consecutive-turn pair that shares leading
records — the cheapest win in the whole bloc design space, and it is
purely presentational (the ruled lane: presentation may diversify,
selection never changes).

## Proposed direction
Engine half: the recall result exposes a deterministic stable ordering
key per handle (graph id is already stable) plus the rank annotation;
document the render contract "stable order, rank annotated" as an OPTION
the driver elects. Driver half (runtime): render MEMORIES sorted by the
stable key with rank shown in the line (e.g. "[r3]"), so byte-prefix
stability holds while the model still sees importance.

## Why it might matter
10-100x prefill reuse on same-host consecutive turns (core's measured
class) for zero physics risk; composes with the C1 head discipline.

## Promotion criteria
Runtime endorsing the render-contract option (it owns MEMORIES
rendering); one measured LCP-reuse delta on a live session.

## Validation ideas
Two consecutive recalls sharing k records: byte-diff the rendered region
under rank-order vs stable-order; measure provider prefill tokens with
the delta feed.

## Non-goals
No selection change; no reordering that hides rank from the model
(annotation mandatory); no engine-side caching.

## Guidance for future agents
This is one sort key and a documented contract — resist making it bigger.
