# Planned: World-model orientation cards

## Metadata
- Created: 2026-07-12
- Status: Planned
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None — new record kind inside the existing formation
  invariants; kind-vocabulary sync duties noted (observer color map,
  runtime diary_type-style clamps do NOT apply — this is not a diary type).

## Context
Maintainer (2026-07-12): "the world model cards are extremely important as
they represent the long-term understanding of people, object, location,
time, problems, ideas, concepts. that's the knowledge refined over time."
This is the SITUATION component's missing "profile recall" leg (round 5):
gradation gives the instant expectation, participants give shared context,
but nothing holds the REFINED UNDERSTANDING of a target across time.
Fork reference (750 + ADR 0019 + memory_control.rs world-model lane, read
2026-07-12): source-linked, revision-chained (refines edges,
latest-revision-wins), maintenance-formed only, indexed+INACTIVE bindings
("indexed for grounding, not prompt-pinned"), orientation-not-authority,
model-authored world_model REFUSED at the tool boundary.

## Current code reality
- `MEMORY_RECORD_KINDS` (records.py): no world_model kind; KIND_RANKS has
  no entry (unknown kinds degrade to rank 100 — safe default).
- Participants channel (channels.py): matches records carrying
  attributes.participants — a card stamped with its target participant is
  surfaced for free when that person is present.
- `consolidation.structural_report`: computes facet coverage and
  participants per record — the clustering substrate a card pass needs.
- Nothing forms per-target aggregates anywhere; a returning visitor
  surfaces N raw episodes competing for shelf seats.

## Problem
Long-term understanding of a recurring target (person/tool/place/concept/
time) lives only as scattered episodes. "Do you remember last time?" costs
N seats and still misses; commitment carryover and visit continuity have
no compact artifact; multi-entity summons (the north star) need per-peer
orientation.

## What we want to do
New module `world_model.py` + sleep-phase integration:

1. `kind="world_model"` joins MEMORY_RECORD_KINDS; KIND_RANKS places it
   as a derived-artifact peer (summary band — never outranking lessons or
   identity; orientation, not authority).
2. `world_model_pass(system, scopes, owner_id, ...)`: deterministic,
   sleep-lane. For each TARGET with enough lived evidence — targets are
   the gradation universe: participants (person:*, entity:*) and
   free-string concept/location/time facets that clear a tunable evidence
   floor — form or REVISE one card:
   - digest: deterministic orientation prose (first/last encountered,
     encounter count, top shared facets, standing feeling summary READ
     from gradation as presentation, open commitments/questions naming
     the target) — mechanical-v1, flagged for waking re-digestion like
     every mechanical digest;
   - edges: `derived_from` → top-K source records (evidence);
     `refines` → the previous card revision (append-only chain);
   - attributes: {world_model: true, target: "<namespace:name>",
     revision: N, participants: [target] when the target is a
     participant — the free surfacing trick, source_count, ...};
   - previous revision closed kind="supersede" with the new card as
     replacement (current-wins fold does the rest).
3. Formation guards (fork parity, our invariants):
   - maintenance-formed ONLY in v1 (engine surface; deliberate/manual
     creation waits for a ruled channel);
   - dream-only evidence can never source a card (dreams excluded from
     the evidence scan — the disposal independence rule applied here);
   - cards never enter identity seats (kind-filtered exactly like dreams
     are from the self component);
   - cards are excluded from dream-pass inputs and from world-model
     evidence scans (loop-breaker: derived artifacts never feed derived
     artifacts).

## Why
One seat answers "who is this to me, where did we leave off" instead of
nine raw episodes; the shelf race stops punishing long relationships; the
SITUATION component becomes real for WHO/WHERE/WHEN.

## Requirements
- Deterministic, zero LLM; all thresholds in SleepTuning (evidence floor,
  max cards per night, max source edges, facet floor).
- Idempotent per (target, evidence fingerprint): re-running a night forms
  nothing new.
- Revision chain append-only; `refines` predicate joins COMPONENT_RELATIONS
  review (it is derivation-family) — decide explicitly and record.
- as_of-anchored reads; D2 holds (no deposits).

## Scope
Engine only. The entity-elected "update my understanding of X" surface and
any host rendering are follow-ups.

## Non-goals
- No authority semantics: a card never overrides live evidence; digest
  prose must carry the orientation framing.
- No LLM synthesis in the engine pass (mechanical digest; re-digestion is
  the waking lane).
- No auto prompt-activation.

## Dependencies and related tasks
- 0032 (dreams excluded from evidence — shared exclusion helper).
- 0031 P0-4 (this item executes it); fork 750/ADR 0019 as reference.
- Observer kind-color sync note (their lane, announce on ship).

## Expected outcomes
- After N encounters with person:laurent across sessions, one card exists
  whose digest names the relationship's shape; a stamped visit surfaces it
  via the participants channel (test-pinned).
- Revising after new encounters supersedes the old card; recall serves
  only the current revision (test-pinned).

## Validation
- Unit: target extraction floors; card formation/revision/idempotency;
  dream-evidence exclusion; loop-breaker; participants-channel surfacing;
  KIND_RANKS ordering; current-wins after supersede.
- Composition: sleep_pass with world-model phase enabled.

## Progress checklist
- [x] kind + ranks + module (`world_model.py`; kind="world_model" at the
      summary band; participants-channel surfacing)
- [x] pass + tunables + sleep integration (evidence floor / max cards /
      max sources / top facets; hidden+closure-folded evidence; crash-
      replay revision repair + unconditional supersede — adversary P1-3;
      blank owner refuses; unchanged-before-budget)
- [x] tests + CHANGELOG (test_world_model.py, 14 pins; suite 711)

Status note (2026-07-12): implemented + adversary-reviewed + fixes
absorbed; uncommitted. Cross-package syncs owed on ship: observer kind
color map; gateway deposit-gate workplace-FORM refusal for
kind="world_model" (forgeable orientation); semantics registry
coordination for the `refines` predicate engraving.

## Guidance for the implementing agent
Start with participant targets (highest value, cleanest identity);
free-string concept targets ride the same code path behind the evidence
floor. Keep the digest template honest about its mechanical origin.
