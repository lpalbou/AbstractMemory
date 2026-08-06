# Subconscious + long-term-knowledge wave (backlog track)

## Status
Planned (maintainer-authorized 2026-07-12 18:38 — "I authorize you to work
on those"; design/implement/test/fix/refine until goals met or exceeded).

## Purpose
Four engine capabilities ruled in one maintainer message, all serving the
same arc — how a summoned entity's memory works BELOW deliberate attention
and ACROSS long time:

- dreams are SUBCONSCIOUS OPPORTUNITIES that the day's lived experience may
  passively resolve (or that resurface when their trigger appears);
- world-model cards are the LONG-TERM refined understanding of people,
  objects, locations, times, problems, ideas, concepts;
- situate() rebuilds a full past context ("what was I doing when/at X") so
  an EVOLVED identity can resume an abandoned path;
- lessons are distilled actionable knowledge referencing actual memories —
  both knowledge and wisdom, critical for long-term evolution.

## Items
- `0032_dream_subconscious_lifecycle.md`: dream formation metadata +
  passive resolution at the sleep boundary + resurfacing. Planned.
- `0033_world_model_orientation_cards.md`: per-target orientation records,
  sleep-formed, revision-chained, never authority. Planned.
- `0034_situate_temporal_relational_reconstruction.md`: the composed
  historical read with temporal AND relational anchors. Planned.
- `0035_lessons_layer_conventions.md`: lesson/instruction conventions,
  derived keywords, unsourced-lesson tending. Planned.

## Reading order
0032 → 0033 → 0034 → 0035 (0033 depends on 0032's report exclusion rule;
0034 and 0035 are independent of both).

## Governing ADRs
None — this repo records durable rules in `docs/memory-system.md` and the
workspace `AGENTS.md`; invariants cited inline per item.

## Scope
Engine-side (`abstractmemory`) only. Host wiring (elections, tool
exposure, driver integration) is named per item as the handoff, never
built here.

## Non-goals
- No LLM calls inside any engine pass (sleep stays deterministic).
- No violation of the ruled invariants: storage never decays; commit is
  the only usage-deposit path; valence never gates recall; sleep proposes /
  waking evidence disposes; append-only everything; identity presence ≠ use.

## Notes for future agents
The maintainer's model (verbatim intent, 2026-07-12): dreams are pending
questions the entity "didn't know it has in its graph"; resolution is
"mostly a passive process"; a remembered dream "influences (not directs)
the day". World models are "the knowledge refined over time". situate()
serves "continuing a path we wouldn't continue at the time" WITH an
evolved identity. Lessons come from the codex fork's 095 layer
(evidence-linked, applies_when/caveats, prompt-inactive by default).
