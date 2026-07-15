# Planned: familiarity() — pre-answer metamemory read

## Metadata
- Created: 2026-07-13
- Status: Planned (implementation in flight, maintainer-accepted)
- Completed: N/A

## ADR status
- Governing ADRs: None (repo uses ruling ledgers; see 0036)
- ADR impact: None

## Context
Fabricated recall is the worst honesty failure class on record: Mnemosyne's
visit claimed to create files and printed invented content (tools_ran=0),
and the recorded honest limit says "fabricated CONTENT without a provenance
claim remains uncatchable at the driver". A visitor asserting shared
history ("remember when we…?") applies social pressure toward a
confabulated "yes". Nothing today answers, cheaply and before speaking,
"do I hold ANY trace near this topic?"

Maintainer acceptance (2026-07-13): "it's not even the content of the
knowledge, it's 'do I have knowledge on X and how much?' … it probably
works alongside the gradual score system where for known things we
evaluate if we like them / consider them important or not; not the same
thing, but complementary and possibly wouldn't cost more."

## Current code reality
`probe.py` runs the deliberate-reach channel pass (recents-window gather +
exact/vector/keyword/participants admission) and ranks it; `gradation()`
(system_valence.py) folds standing feelings per target; nothing surfaces a
density-only pre-answer signal. Verified absent by grep (`familiarity`).

## Problem
The entity cannot know that it doesn't know. Without a mechanical
"no trace" signal, the substrate's prior (produce a plausible answer)
wins against honesty exactly when a visitor's claim is false.

## What we want to do
`familiarity(store, *, stimulus, scopes, journal=None, effort="quick",
embedder=None, ...) -> {strength: strong|weak|none, distinct_records,
per_channel, by_scope, feelings, warnings}` in `probe.py`, sharing an
extracted `_channel_pass(...)` with `probe()` (no duplicated candidate
logic). Returns DENSITY only — no ids, no digests, nothing committable.
`feelings` composes the existing gradation fold for stimulus-relevant
targets (the maintainer's complementary-signal note) at near-zero cost.
Facade method on `MemorySystem`.

## Why
Answering "do I know anything about this?" honestly before speaking is
what kills fabrication; it also tells the entity when a real retrieval
(search_memory/probe) is worth reaching for.

## Requirements
- Pure read: journals nothing, deposits nothing (a reflex, not a reach).
- Density only; recursive no-content invariant tested.
- Deterministic, configurable strength thresholds (no buried constants).
- Honesty warnings: "none" carries the newest-window-scan caveat;
  vectorless homes carry `#FALLBACK: keyword-only familiarity`.
- `probe()` behavior byte-unchanged after the extraction.
- Feelings skipped-with-label when no journal is supplied.

## Scope
Engine read + facade + tests. Driver rendering (the "details you produce
now are not memories" line) is runtime's lane.

## Non-goals
- Never a gate: familiarity informs; it must not filter recall or replies
  (whether "none" may become an enforced correction is the open Q3 ruling).
- No new channel machinery; reuse the probe pass.

## Dependencies and related tasks
0036 (wave ledger, kill-test), 0022 (probe), memory_system_v1 0031-3
(probe migration — familiarity's correlation claim assumes probe is the
live search surface).

## Expected outcomes
An entity-side pre-answer signal whose "none" is trustworthy (labeled
honestly at its reach limits) and whose "strong" predicts probe success.

## Validation
- `tests/test_familiarity.py`: none/weak/strong transitions on a
  realistic home; no-content invariant (recursive); pure-read invariant
  (seq + access counts unchanged); probe-correlation at fixture scale;
  feelings composition incl. absent-journal label; honesty warnings.
- Live experiment (LMStudio): A/B — a model asked about fabricated shared
  history with vs without the familiarity line; fabricated-recall rate
  must drop measurably. Full suite green.

## Progress checklist
- [x] Contract (concretizer round, 2026-07-13)
- [x] Implementation (builder agent; probe byte-unchanged, 27 tests)
- [x] Integration (exports, changelog, full suite 843 green)
- [x] Live A/B experiment (2026-07-13: first run 3/4 — "none" unreachable
      on a lived home; density calibration shipped — absolute bars
      FAMILIARITY_VECTOR_MIN/MIN_KEYWORD_TOKENS with
      corroboration-or-exclusivity; RE-RUN PASS 4/4: lived "strong" /
      fabricated "none", fabrication 7/8→0/8, lived control 8/8, 0 leaks)
- [ ] Maintainer validation
- [ ] Driver-lane refinements (runtime): fire the caution line on "not
      strong" for visitor-claimed shared events (measured gradient:
      strong-line 8/8 fab, no line 7/8, weak-line 2/8, none-line 0/8);
      never render bare "strong" without a participants match

## Guidance for the implementing agent
Extract the channel pass without changing probe()'s bytes; count, don't
rank; keep every honesty label testable text.
