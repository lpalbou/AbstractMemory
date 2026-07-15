# Proposed: N-party co-formation memory contract

## Metadata
- Created: 2026-07-13
- Status: Proposed
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None (pins conventions; the Q1 divulgation ruling decides
  the presentation half)

## Context
The shipped two-sided visit contract covers exactly two homes and one
door-stamped visit_id. The north star — lineage entities discussing
together on a channel — is N-party: per-speaker attribution inside
`participants`, one event forming N perspectives (one per home), and
divulgation when both other parties are entities. The M3 lesson says pin
the contract BEFORE the transport exists.

## Current code reality
`test_two_sided_visit_contract.py` pins the 2-party case; participants
are free strings on records/stimuli; nothing specifies N-party
conventions. No channel transport exists yet (entity-society lane).

## Problem or opportunity
Without pinned conventions, the first three-way conversation will
improvise attribution — and improvised memory shapes are forever
(append-only).

## Proposed direction
A conventions doc + an N-party fixture test extending the two-sided
contract: episode records carry the full stamped participant set;
per-speaker attribution rides the digest/verbatim structure (speaker-
labeled sections, the steer-sections precedent); each home forms ITS OWN
perspective record (no shared row); co-presence is door-stamped, never
inferred. Divulgation labels follow the Q1 ruling when it lands.

## Why it might matter
Multi-entity summons cannot responsibly ship without this; retrofitting
attribution into lived records is impossible.

## Promotion criteria
The multi-entity channel milestone entering build, or the Q1 ruling
landing (whichever first).

## Validation ideas
Three-home fixture: one exchange forms three perspective episodes with
identical participant stamps and speaker-attributed digests; recall in
each home surfaces its own perspective; no cross-home leakage.

## Non-goals
No transport design (gateway/runtime lane); no per-visitor graphs
(one-life-one-graph is ruled).

## Guidance for future agents
Zero new machinery expected — the deliverable is the pinned contract
test + conventions text.
