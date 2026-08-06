# 0029 — Sleep reactivity: dreams/nightmares as the entity's REACTION to graph operations

Status: proposed (parked by the maintainer's own words — "do not dwell too much
in that, this is for later"). Filed 2026-07-11 from commons c684 so the idea is
not lost; no design commitment yet.

## The maintainer's seed (c684, verbatim core)

> currently sleep phase is a time for the graph memory to essentially
> consolidate, repair, improve where it can in a safe manner. the entity is
> indeed not supposed to take any action, but i don't want to preclude it
> either. for instance, maybe the entity could reacts to some of those
> operations happening on his memory graph, possibly leading to an actual
> dream or actual nightmare.

Context: this was his Q2 ruling on the entity config object — sleep's default
workflow stays UNSET, sleep remains a first-class configurable phase
(c653 ruling), and the sleep-deposits-nothing invariant (N4, c673) bars door
deposits during the window while the engine's own review-gated passes remain
the only graph-writers inside it.

## What this would mean mechanically (sketch only, to anchor future design)

Today's sleep passes (maintenance/consolidation/dream, 0023 lineage) are
DETERMINISTIC and entity-silent: they report findings and form at most one
review-gated dream record per pass; the entity discovers the dream later via
normal recall admission ("a dream is the entity's to FIND, not a push
notification").

The seed inverts one arrow: sleep-pass OPERATIONS (a merge candidate found, a
scar-adjacent component touched, a bridge proposed between distant islands)
could become STIMULI to a bounded entity reaction inside the sleep window —
the reaction, not the operation, being what colors the dream (dream vs
nightmare = the valence of what consolidation disturbed).

Constraints any future design must inherit (all already ruled):
- The N4 invariant stands: a reacting entity in sleep still cannot FORM/ADJUST/
  commit through the door — its reaction would have to flow through the same
  review-gated engine path the dream pass uses today (sleep proposes, waking
  evidence disposes), or be deferred to the wake boundary.
- Valence sources stay honest: a nightmare's negative charge must come from
  the records actually touched (their existing valence/scars), never
  synthesized.
- Diary stays sole-author and awake-only (elections are an awake act).
- Cost discipline: an LLM-backed reaction inside sleep is compute the operator
  pays for at night — whatever ships must be operator-granted like the
  personal phase grant (phases.yaml, off-by-default),
  never default-on.

## Why it is parked

The maintainer explicitly deferred it. Prerequisites that should land first:
phase-on-signed-stamp (N2), the N4 sleep gate, the config object build, and
live experience with the current deterministic passes on real homes (Castor's
dreams) to know what operations are even worth reacting to.


## Completion report (2026-07-20)

Shipped as the wave-5 dream-signal chain (laurent Q1 ruling): dream_signals.py — the night reacting to its own maintenance acts, ruled typology, felt coloring from accumulated valence, bounded per-section composition; first live firing verified (room 319).
