# Extension wave backlog track (planned)

## Status

Planned — maintainer-accepted 2026-07-13 ("enroll 4 sub agents... think,
discuss, design, implement, test, fix and refine the first 3 systems I
accepted until it meets or exceeds the expected goals. You MUST do real
experiments and make sure this works.")

## Purpose

The three systems the maintainer accepted from the third-pass extension
wave (proposal ledger: `../../proposed/memory_system_v1/0036_third_pass_extension_wave.md`),
each with his acceptance notes folded in as requirements. The other nine
wave items live in `../../proposed/extension_wave/`.

## Items

- `0037_familiarity_metamemory_read.md`: pre-answer "do I know X and how
  much" density read + gradation feelings composition. Building.
- `0038_open_commitments_and_triggers.md`: prospective memory — diary
  commitments with context triggers surfacing at the right moment. Building.
- `0039_tend_election_grammar.md`: one fenced grammar over existing
  attention/valence/disposal verbs + iterative revisit reach. Building.

## Reading order

0037 → 0038 → 0039 (independent builds; 0039 depends on the most engine
surfaces).

## Governing ADRs

None identified after review (repo has no ADR system; rulings live in the
memory_system_v1 ledgers and the maintainer's recorded decisions).

## Scope

Engine-side implementations + realistic tests + live experiments
(LMStudio). Runtime driver wiring (fence extraction, prompt lines) is the
runtime seat's lane and is coordinated on the hub, not built here.

## Non-goals

- No new engine mutation paths (0039 maps to existing verbs only).
- No admission-channel changes (0038 is presentation-only).
- No content in 0037's output (density only — the anti-fabrication
  property).
- Identity-scope tending stays refused pending the maintainer's Q2 ruling.

## Notes for future agents

The maintainer's acceptance notes are requirements, not suggestions:
familiarity composes with gradation ("complementary, possibly wouldn't
cost more"); commitments are "a larger set" than open questions; tend's
revisit is ITERATIVE ("selecting first the closest nodes to our need,
then letting it spread a bit, trying to find additional paths").
