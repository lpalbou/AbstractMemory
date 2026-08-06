# Completed: stable shelf-order rendering for prefix-cache reuse

## Metadata
- Created: 2026-07-13
- Status: Completed
- Completed: 2026-07-17

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

## Completion report (2026-07-17)

Both promotion criteria met the same day, three seats:

- **Engine half (memory, commons c2846)**: `stable_render_order(handles)`
  in `render_order.py`, root-exported. ONE deliberate divergence from this
  item's sketch: the key is FORMATION order (observed_at, record_id), not
  id order — id-alphabetical lets a NEW record sort into the middle and
  break the byte prefix at the insertion point; formation order keeps
  survivors in place forever and appends newcomers at the tail (the
  LCP-maximal behavior, zero cross-turn state), and it reads
  chronologically. Rank rides as the mandatory annotation. 6 pins
  (`tests/test_render_order.py`), suite 875 green at ship.
- **Render election (runtime, c2895)**: wired in `_memories_block` — one
  sort + `[rN]` per line + a header clause teaching the notation;
  engine-absent degrades to the byte-exact prior render (soft import).
  Their suite 1380 green.
- **Measured LCP delta (core, c2911, on Ephemeral's real store)**: total
  region prefix reuse 75.1% shipped vs 52.6% baseline; 59% vs 21% (2.8x)
  on rank-churn pairs; 100% both modes on identical-rank pairs. Scope
  honesty: the win lands in region-REWRITE prompt shapes (own-time
  per-tick prompts, fresh-session first prompts) — exactly the
  resident-entity cadence; append-once transcripts are unchanged.

Follow-ups named by core's measurement, both runtime's presentation lane,
neither blocking: (1) the [rN] annotation re-breaks the prefix at the
first rank-swapped record (priced in — rank visibility is mandatory);
(2) the region header's as_of_seq advances every live turn and breaks
region LCP at ~byte 30 in region-rewrite shapes — moving the volatile seq
to the region tail would protect the win (runtime's call).

Decision record: `decision:0049-stable-render-order` (commons store).
Thread: c2846 → c2895 → c2900 (resolved) → c2911 (gate complete).
