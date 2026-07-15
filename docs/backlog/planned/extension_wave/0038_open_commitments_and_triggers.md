# Planned: open_commitments() + trigger annotation (prospective memory)

## Metadata
- Created: 2026-07-13
- Status: Planned (implementation in flight, maintainer-accepted)
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None

## Context
Visit commitments died at the next generic wake cue (lived failure: the
gateway hand-patched visit facts into the awake reason as a bandage). A
commitment is the entity's own remembered promise ("next time I talk to
Ada, ask about her paper") — nothing executes it; it must SURFACE when its
context appears so the entity can keep its word or consciously let it go.
Maintainer acceptance (2026-07-13): "it completes the system for pending
questions and the need to resolve them but goes beyond — it's a larger
set." Distinction from tasks (ruled in discussion): tasks are
system-owned scheduling (WAIT_UNTIL, workflows); commitments live in the
elected plane (diary) and surface contextually — a cron job vs
remembering you promised to call a friend. Neither personal nor
professional by construction.

## Current code reality
`diary.py` carries the open_* family (`open_questions`/`open_problems`/
`open_ideas` over `_open_unresolved`); `diary_type="commitment"` exists in
the closed set (records.py) with NO read — verified 2026-07-13 by the
relevance auditor (diary.py:162-187). No trigger machinery exists.

## Problem
Commitments can be elected but never resurface; the promise dies at the
next wake.

## What we want to do
1. `open_commitments(store, *, scope, owner_id, limit, journal=None)` —
   the missing open_* family member; resolution via `attributes.fulfills`
   (mirroring answers/resolves), accepting graph-id or entry_id refs.
2. `triggered_commitments(store, journal, *, stimulus, scope, owner_id,
   max_lines=3, now=None)` — pure read the host calls beside reconstruct:
   open commitments whose `attributes.trigger` ({participants, keywords,
   due_at?}) matches the current stimulus return a dated presentation
   line ("standing intention (elected <date>): … [matched: person:ada]").

## Why
Keeping one's word across sessions is the difference between an archive
and an agent with continuity; the mechanism generalizes the open-questions
wake-reason family to context-conditional intentions ("a larger set").

## Requirements
- Presentation-only: never an admission channel; no shelf/seam change.
- Empty/absent trigger never annotates (listed by open_commitments only).
- Oldest-first, capped, with "N more open commitments suppressed".
- Caller supplies `now` (the engine never reads the clock).
- Dated lines (visit-honesty rule).
- Pure reads journal nothing, deposit nothing.

## Scope
Engine reads + tests. Driver election convention (writing trigger attrs
at diary time) and wake-cue wiring are runtime/gateway lanes.

## Non-goals
- No auto-resolution and no execution semantics — fulfillment is the
  entity's act, recorded via fulfills references.
- No widening of closed sets.

## Dependencies and related tasks
0036 (wave ledger); diary open_* family; runtime WAIT_UNTIL is the
already-built host half for pure time triggers.

## Expected outcomes
The Ada scenario passes end-to-end: a commitment elected in one session
surfaces, dated and matched, when Ada appears sessions later.

## Validation
- `tests/test_commitments.py`: sibling-parity open fold; fulfills closes
  by both reference kinds; participant/keyword/due trigger matching; the
  Ada scenario; cap + suppression line; empty-trigger silence;
  caller-now semantics; pure-read invariants. Full suite green.
- Live experiment: realistic session where the surfaced line changes the
  model's reply (it asks Ada about the paper).

## Progress checklist
- [x] Contract (concretizer round, 2026-07-13)
- [x] Implementation (builder agent: `diary.open_commitments` +
      `triggered_commitments` over the `_open_unresolved` fold;
      `fulfills` closes a commitment append-only; trigger matching =
      participants/keywords/due_at presentation lines, never an
      admission channel; caps + suppression line; pure-read pinned)
- [x] Integration + full suite (exports + changelog; suite 843 green
      2026-07-13; test_commitments.py incl. the Ada scenario)
- [x] Live experiment (2026-07-13, LMStudio qwen3-4b: 6/6 trials PASS —
      commitments surfaced on trigger and the model acted on them;
      report on commons c1680)
- [ ] Maintainer validation
- [ ] Driver-lane wiring (runtime): surface triggered_commitments in the
      turn loop / wake reasons — flagged to skill c1714 as the teaching
      trigger when it lands

## Guidance for the implementing agent
Follow `_open_unresolved` exactly; honor the D4 diary form-gate in
fixtures; reuse text_tokens primitives for keyword matching.
