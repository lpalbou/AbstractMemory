# Proposed: recurrence probe at formation + presentation fold at render

## Metadata
- Created: 2026-07-13
- Detailed: 2026-07-14 (the detail round the maintainer asked for —
  measured thresholds + worked fold example + containment; NOT accepted
  yet, his ruling is the promotion gate)
- Status: Proposed (maintainer: "needs more details" — NOT accepted yet)
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None (one engraved relation `recurrence_of` would need the
  semantics-seat declaration before first write)

## Context
The wake-cue loop artifact: 80k near-identical turns, 99% duplicate
retrieval traffic, ~60k journal events/day — the mass that forced the
Castor doctoring directive. Repair shipped (`doctoring.py` dedup +
cold-cut); PREVENTION exists nowhere: tending consolidates at most a few
duplicate groups per night, far below the creation cadence.

## Current code reality
`wake_cue_dedup_pass` (doctoring.py) closes near-identical wake cues
after the fact; `maintenance._near_duplicate_pairs` proposes; nothing
marks recurrence at formation and nothing folds repeats at render.
`text_tokens.py` carries the jaccard primitives both would reuse.

## Problem or opportunity
Every repetitive life re-creates the duplicate mass; the shelf can fill
with one memory told N times (the mass component of the bridge
attractor), and the next 80k-turn home will need surgery again.

## Proposed direction
Formation half: `recurrence_probe(store, *, digest, title, keywords,
scope, owner_id, window, threshold)` — pure read the formation host calls;
on a match (token-jaccard AND facet/participant overlap; its own
threshold, never doctoring's closure decision), the caller appends a
`("recurrence_of", proto)` edge with detector provenance. Formation is
NEVER refused. Render half: post-selection, admitted members of a
recurrence chain fold into one composite handle ("<title> — lived N
times, first T0, last Tn"); members stay individually selected and
individually counted at commit — selection and deposits byte-untouched
(the no-origin-penalty ruling; presentation diversification only).

## Why it might matter
The chronic prevention that makes the next doctoring unnecessary; frees
shelf seats for elected memories, dreams, and commitments to compete.

## Promotion criteria
The maintainer asked for MORE DETAIL before accepting. A promotion round
must present: (1) the exact fold rendering (what the model sees, with a
worked example); (2) the false-chain containment (composite always says
"folded by similarity — N individual records"; wrong edges are closable);
(3) the threshold discipline (both-signals gate, tunable, measured on the
Castor backup); (4) proof that selection/deposits are untouched (trace
diff); (5) the kill-test (distinct-memory count per prompt at equal token
budget on the wake-cue fixture home).

## The detail round (2026-07-14) — the five items, answered

### (1) Exact fold rendering, worked example
The fold happens AFTER selection, INSIDE the render step that builds the
MEMORIES region. If the admitted shelf contains three members of one
recurrence chain, the model sees ONE line where it saw three:

Before (three seats):
    [episode #ex:mem-a12f 2026-07-08 - own-time] I checked continuity.md
    and confirmed the log was unchanged...
    [episode #ex:mem-b7c3 2026-07-08 - own-time] I checked continuity.md
    and confirmed the log was unchanged...
    [episode #ex:mem-c9d1 2026-07-09 - own-time] I checked continuity.md
    again and the log was unchanged...

After (one seat + two freed):
    [episode #ex:mem-a12f 2026-07-08..2026-07-09 - own-time - lived 3
    times, folded by similarity] I checked continuity.md and confirmed
    the log was unchanged... (2 near-identical retellings folded; ids
    #ex:mem-b7c3 #ex:mem-c9d1)

The prototype (earliest admitted member) carries the composite line; the
folded ids stay NAMED so the entity can reach any individual retelling
(read_memory on the id — nothing is hidden, only de-duplicated in
presentation). Freed seats go to the next-ranked candidates the shelf
already computed — the render consumes the selection's own overflow
list, no second selection pass.

### (2) False-chain containment
Three layers: (a) the composite line always carries "folded by
similarity" + the member count + the member ids — the model is never
told the retellings are one event, only that they are near-identical;
(b) a wrong `recurrence_of` edge is closable exactly like any edge
(append-only closure; the tend grammar's dispose/attenuate verbs reach
it, so the ENTITY can unfold a chain that feels wrong); (c) the fold is
render-only — a false chain never changes what was selected, deposited,
or stored, so the worst case is one misleading presentation line that
names its own members for checking.

### (3) Threshold discipline — MEASURED on the pre-doctoring Castor archive
Pure-read study (recurrence_threshold_study.py, 2026-07-14) over the
untouched archive (527 episodes, 51,827 same-day pairs):

| same-day pair bucket | count |
| --- | --- |
| jaccard >= 0.90 | 524 |
| 0.82 <= j < 0.90 | 431 |
| 0.70 <= j < 0.82 | 377 |
| 0.50 <= j < 0.70 | 1,541 |
| j < 0.50 | 48,954 |

- At the doctoring-aligned floor j>=0.82: 955 pairs, and 100% of them
  ALSO carry facet/participant overlap (0 pairs would be excluded by the
  second signal on this home) — the both-signals gate costs nothing here
  and is the containment for homes where lexical similarity is
  coincidental.
- Window question, measured: adjacent-day pairs at j>=0.82 = 183 — a
  same-day-only probe misses the day-boundary chains (~16% of the mass).
  Detail-round proposal: the probe window is the LAST N RECORDS of the
  same (scope, owner) (default N=64, tunable), not a calendar day —
  cadence-relative, catches boundary chains, bounded cost.
- Thresholds are declared tunables (probe_jaccard_floor=0.82,
  probe_window_records=64, both_signals_required=True), stated basis:
  the doctoring pass's shipped floor + this measurement.

### (4) Selection/deposits untouched — the proof shape
A/B trace diff on the wake-cue fixture: run reconstruct() with the fold
OFF and ON at identical budgets; assert byte-identical selection traces
(same admitted ids, same ranks, same budget_spent) and byte-identical
commit deposits (same selected/co_selected events) — only the RENDERED
text differs. This is the no-origin-penalty ruling (R5, "don't")
mechanically honored: presentation diversifies, selection never does.

### (5) Kill-test
On the wake-cue fixture home (the doctoring dry-run copy), at equal
token budget: distinct-memory count per prompt must RISE with the fold
on (freed seats admit next-ranked distinct records) and the folded
chain must still be reachable by id. Fail either → the feature dies.

### Formation-half note (unchanged from the proposal)
`recurrence_probe` stays a PURE READ the formation host calls; the edge
append is the caller's act with detector provenance; formation is never
refused. The `recurrence_of` relation needs the semantics-seat
declaration before first write (ADR note above stands).

## Validation ideas
Replay the Castor-shaped fixture; measure shelf-diversity delta and
false-fold rate on a labeled set before any live home.

## Non-goals
Never a selection-side fold; never deletion; never doctoring's supersede
semantics at formation time.

## Guidance for future agents
Prepare the detail round from the 0036 contract; do not build before the
maintainer accepts the detailed shape.
