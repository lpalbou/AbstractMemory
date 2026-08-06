# Completed: Lessons layer — conventions, source-linking, tending

## Metadata
- Created: 2026-07-12
- Status: Completed (2026-07-20)
- Completed: 2026-07-20

## ADR status
- Governing ADRs: None
- ADR impact: None — attribute conventions + report additions inside
  existing formation invariants.

## Context
Maintainer (2026-07-12): "in codex, we were also creating 'lessons',
something actionable that can reference actual memories and serve
essentially as both distilled knowledge and wisdom. they are critical also
for the long term evolution of the entity." Fork 095 (completed, read
2026-07-12): Lesson nodes immutable, indexed but prompt-INACTIVE by
default, `derived_from` edges to source memories, applies_when + caveats
+ evidence-strength labels (proposed → single_source → corroborated →
operator_accepted → validated_by_action → disputed → stale), corrections
as NEW lessons linked refines/replaces/disagrees_with, probe ordering
prefers lessons first ("semantic guidance points reconstruction toward
source evidence before the model reads raw memories").

## Current code reality
- `kind="lesson"` and `kind="instruction"` exist (records.py) with the
  BEST ranks among learned kinds (lesson=0, instruction=1) — surfacing
  preference already stronger than the fork's probe-ordering trick.
- Edges: `derived_from`/`supports`/`answers` are already
  COMPONENT_RELATIONS members; formation accepts arbitrary edge tuples.
- NO conventions: nothing distinguishes a taught procedure from a world
  lesson; applies_when/caveats/evidence class are undocumented free
  attributes nobody writes; nothing checks that a lesson references its
  sources (summary has that guard; lesson does not).
- `maintenance._metadata_gaps`: reports missing keywords/intents/outcomes;
  says nothing about unsourced lessons.

## Problem
Lessons that reference nothing are opinions wearing wisdom's rank. Without
applicability conventions, a lesson learned in one context surfaces
without its caveats; without evidence classes, a dream-derived hunch and
an operator-validated rule read identically.

## What we want to do
1. **Conventions, validated at formation** (records.py, additive):
   - `attributes.applies_when` (str|list) and `attributes.caveats` (list)
     normalized like other list attributes; contribute to derived
     KEYWORDS (applies_when tokens join the keyword set — a lesson about
     "sqlite migrations" is FINDABLE when migrations come up; ADR-0017
     compliant: plumbing tokenization, not cognition filtering);
   - `attributes.evidence_class` ∈ frozenset {proposed, single_source,
     corroborated, validated, disputed} — validated loudly when present,
     never required (absent = unlabeled, honest default);
   - `instruction` records accept `attributes.category` ∈ {rule,
     instruction, process} (fork 490) — same optional-but-validated shape.
2. **Sourcing discipline via TENDING, not refusal** (maintenance.py): a
   lesson/instruction with ZERO derivation edges (derived_from/supports/
   answers/from_session/summarizes) and no import provenance joins
   `metadata_gaps` as `unsourced_lesson` — report-only (archive-imported
   and operator-taught lessons stay legal; the gap surfaces for a waking
   re-digestion). Hard refusal deliberately rejected: real teachings
   arrive without machine-readable sources.
3. **Correction chain documented**: a corrected lesson is a NEW record
   with `refines`/`disagrees_with` edge + supersede closure of the old —
   composition of existing verbs; documented in docs/memory-system.md
   with the evidence-class ladder.

## Why
Lessons are the entity's long-term evolution currency; these conventions
make them findable (applies_when keywords), honest (evidence class,
sourcing gaps), and correctable (append-only revision chain) without any
new machinery.

## Requirements
- Additive validation only — existing lessons stay legal.
- No prompt-activation changes (rank already prefers lessons; no new
  gating).
- Tending check bounded like other gap lists.

## Scope
records.py validation + keyword derivation; maintenance.py check;
docs/memory-system.md section; tests.

## Non-goals
- No auto-generated lessons (proposal machinery is a later wave).
- No evidence-class-based recall gating (relevance admits; class is
  presentation/judgment data).
- No cross-scope promotion machinery (scope ladder already exists).

## Dependencies and related tasks
- Fork 095/490 as reference; 0031 P2-20/21.

## Expected outcomes
- A lesson formed with applies_when="sqlite migrations" is keyword-
  reachable via "migrations" (test-pinned).
- evidence_class typos refuse loudly; valid classes store (test-pinned).
- An unsourced lesson appears in the tending report; a sourced one does
  not (test-pinned).

## Validation
Unit tests per convention + full suite green.

## Progress checklist
- [x] conventions + keyword derivation (applies_when/caveats/
      evidence_class/category, optional-but-validated; non-Latin
      applies_when warns #FALLBACK — adversary P2)
- [x] tending check (`unsourced_lessons`; provenance read matches the
      REAL archive-importer shape — adversary P1.1)
- [x] docs + tests + CHANGELOG (test_lessons_layer.py, 7 pins)

Status note (2026-07-12): implemented + adversary-reviewed + fixes
absorbed; uncommitted. Entity-elected lessons (a ```lesson reflection
grammar) is a runtime-lane follow-up, not authorized yet.

## Guidance for the implementing agent
Keep every convention OPTIONAL-but-validated: absence is honest, presence
is checked. The evidence ladder is data for judgment, never a gate.


## Completion report (2026-07-20)

Shipped: kind=lesson (KIND_RANKS), diary_type='lesson' (DIARY_TYPES + runtime clamp sync at chat.py:219), the card's lessons section (build 5), W2 miner lesson OFFERS from resolved cross-session tensions (correction-7 shape), and runtime's election-site teaching. The wisdom axis is live end-to-end.
