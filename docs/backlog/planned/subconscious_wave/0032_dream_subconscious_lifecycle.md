# Planned: Dream subconscious lifecycle (passive resolution + resurfacing)

## Metadata
- Created: 2026-07-12
- Status: Planned
- Completed: N/A

## ADR status
- Governing ADRs: None (repo uses docs/memory-system.md for durable rules)
- ADR impact: None — refines the 0023 sleep design inside its invariants.

## Context
Maintainer ruling (2026-07-12 18:38, correcting the review-queue framing of
backlog 0031): a dream is a PENDING QUESTION the entity does not
consciously know it holds. The day's lived experience may answer it
passively — "I dream I don't know how I can finish that project… during
the day I work so much that I finish it" (a SOFT resolution) — or the
dream RESURFACES when its trigger appears ("I dream about that person…
suddenly I meet the person and the dream resurfaces and concludes").
Mostly passive; deliberate review (disposal.py verbs) stays the rare,
explicit path. A REMEMBERED dream (recalled while awake) INFLUENCES the
day — influence = normal recall admission, never a push.

## Current code reality
- `consolidation.py dream_pass`: forms at most one dream/night with
  `mentions` edges to sources and attributes {salience, parent_dream_ids,
  continuation_state, interpretation_required, proposals, questions} — but
  NO keywords and NO participants: the one artifact sleep produces is the
  least channel-reachable record in the home (templated digest; findable
  mainly by the literal token "dream").
- `unresolved_dreams()`: standing dreams with continuation_state ==
  "unresolved"; chained as continuation anchors; nothing ever RESOLVES one
  except the uncalled disposal verbs.
- `maintenance.sleep_pass`: tend → dream; no resolution phase.
- `disposal.dispose_dream`: deliberate verdict (confirmed/dissolved);
  zero callers anywhere (0031 finding) — and per this ruling that is
  ACCEPTABLE for v1: passive resolution is the primary path.

## Problem
Standing dreams accumulate monotonically. The design says "waking evidence
disposes" but the only disposer is a deliberate verb nobody calls. The
maintainer's model says the common case is PASSIVE: the day resolves the
tension without anyone examining the dream.

## What we want to do
1. **Formation metadata**: dreams (and consolidation candidates) form with
   keywords = shared facets from their proposals/questions and
   participants = shared participants — honest metadata (that IS the
   dream's content), making resurfacing-by-normal-recall possible: when
   the person appears in a cue/participant stamp, the dream is
   channel-matched like any record.
2. **Passive resolution at the sleep boundary** ("the night reviews the
   day"): before dreaming again, `resolve_dreams_pass` examines each
   standing unresolved dream against records formed AFTER it (the lived
   day). A dream resolves softly when waking experience closes its
   tension:
   - bridge proposals: the proposed pair (or ≥ tunable fraction of
     proposals) became SAME-COMPONENT via authored edges, or a warm
     co_selected trail now joins it (used together = associated by use);
   - facet questions: a NEW record (formed after the dream) carries the
     questioned facet together with either dream participant/source —
     the question found its subject in lived experience.
   Soft resolution writes: `close_record(dream, kind="supersede",
   replacement_ids=[resolving records], reason=...)` + a
   `resolution` note in the closure reason naming the mechanism
   ("resolved_by_experience"). Append-only; the dream's history stays.
3. **Resurfacing needs no new machinery**: with (1), normal recall
   channels do it — pinned by test, not by new code.

## Why
Without resolution, recurring dreams chain forever (bridge-attractor
adjacent); with only deliberate disposal, the common case (life answers
the question) never closes. The maintainer's model makes the passive path
primary and the engine can compute it deterministically — no LLM, no
mutation of sources, sleep-boundary only.

## Requirements
- Deterministic; zero LLM calls; report-only unless resolution criteria
  met; every threshold in SleepTuning (no magic numbers).
- Resolution evidence must POST-DATE the dream (journal seq comparison) —
  yesterday's records cannot resolve tomorrow's dream.
- D2-of-sleep holds: no usage deposits; closures + (optionally) one
  resolution note are the only writes.
- Dreams excluded from being resolution evidence for OTHER dreams
  (loop-breaker parity).
- `sleep_pass` order: resolve (yesterday's dreams vs today's life) →
  tend → dream (tonight's new tension).
- Idempotent: re-running resolves nothing twice (closure ids derive from
  the record+kind; a closed dream leaves the unresolved set).

## Scope
Engine only: `consolidation.py` (formation metadata), new
`dream_resolution.py` or extension of `maintenance.py` (the resolve pass),
`sleep_policy.py` (tunables), `system.py` facade threading, tests.

## Non-goals
- No push notification of dreams (a dream is the entity's to FIND).
- No LLM interpretation of dream content.
- No auto-confirmation of bridge proposals into REAL typed edges — soft
  resolution closes the DREAM; promoting a proposal to a load-bearing edge
  stays the deliberate disposal path (waking-evidence invariant).
- No removal of the deliberate disposal verbs (they remain the rare path).

## Dependencies and related tasks
- 0023 (sleep v1), 0029 (dream reactivity, parked), 0031 items 2/10.
- disposal.py stays as-is.

## Expected outcomes
- A dream about an unfinished project closes softly the night after the
  project finishes (test-pinned with authored edges/trails).
- A dream about a person surfaces via normal recall when that person is
  stamped as participant (test-pinned).
- Standing-dream count stops growing monotonically in a lived home.

## Validation
- Unit: formation metadata (keywords/participants from proposals);
  resolution criteria per mechanism; post-dating rule; idempotency;
  D2 guard (no access-count movement through the whole pass).
- Composition: sleep_pass runs resolve→tend→dream; a resolved dream no
  longer feeds continuation anchors.

## Progress checklist
- [x] Dream/candidate formation metadata (keywords/participants from
      tension vocabulary; owner + ambient companions excluded — the
      discriminative gate, adversary P1-2)
- [x] resolve pass + tunables (`dream_resolution.py`; evidence-grade
      report — closures folded, sleep artifacts excluded (P0-1/P0-2);
      trail strength floor `resolution_trail_min_traces`; continuation
      dreams stand and resolve with their lineage)
- [x] sleep_pass composition (resolution first; as_of write guards)
- [x] tests + CHANGELOG (test_dream_resolution.py, 15 pins; suite 711)

Status note (2026-07-12): implemented + adversary-reviewed (fable5) +
fixes absorbed; uncommitted per standing rule. Completion report moves
this item to completed/ when the maintainer's ship review lands.

## Guidance for the implementing agent
Keep the resolution criteria STRUCTURAL (edges/trails/facet+participant
co-occurrence), never semantic guessing. When in doubt, leave the dream
standing — a false resolution erases a real tension silently.
