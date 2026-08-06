"""Lessons layer conventions (backlog 0035; fork 095/490 lineage).

Contracts pinned:
- applies_when/caveats are optional-but-validated and applies_when tokens
  JOIN the keywords (a lesson about "sqlite migrations" is findable when
  migrations come up);
- evidence_class validates against the declared ladder, loudly on typos,
  absent = unlabeled (honest default);
- instruction category validates against rule|instruction|process;
- an unsourced lesson (no derivation edges, no import provenance) is named
  by TENDING for a waking re-digestion — never refused at formation;
- lessons keep the strongest learned-kind rank (surfacing preference) and
  the correction chain works by composition (refines + supersede).
"""

from __future__ import annotations

import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    Stimulus,
    maintenance_report,
)
from abstractmemory.records import (
    INSTRUCTION_CATEGORIES,
    KIND_RANKS,
    LESSON_EVIDENCE_CLASSES,
)

OWNER = "entity:learner"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def test_applies_when_tokens_join_keywords_for_findability(system) -> None:
    [gid] = system.remember_many([
        MemoryRecordInput(
            kind="lesson", title="Backfill before swap",
            digest="Always backfill vectors before swapping embedding spaces.",
            keywords=("embedding",),
            attributes={"applies_when": "sqlite migrations and reembedding",
                        "caveats": ["not for in-memory stores"]}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="l1")
    r = system.reconstruct(Stimulus(cue_text="migrations"), scopes=SCOPES)
    from abstractmemory.records import resolve_digest_assertion

    row = resolve_digest_assertion(system.store, gid)
    assert row.assertion_id in {h.record_id for h in r.handles}, (
        "applies_when did not make the lesson findable")
    assert "migrations" in row.attributes.get("keywords", ())
    assert row.attributes["caveats"] == ["not for in-memory stores"]


def test_evidence_class_and_category_validate_loudly(system) -> None:
    assert "corroborated" in LESSON_EVIDENCE_CLASSES
    assert INSTRUCTION_CATEGORIES == {"rule", "instruction", "process"}
    with pytest.raises(ValueError, match="evidence_class"):
        MemoryRecordInput(kind="lesson", title="X", digest="Y.",
                          attributes={"evidence_class": "gut_feeling"})
    with pytest.raises(ValueError, match="category"):
        MemoryRecordInput(kind="instruction", title="X", digest="Y.",
                          attributes={"category": "vibe"})
    ok = MemoryRecordInput(kind="lesson", title="X", digest="Y.",
                           attributes={"evidence_class": "Corroborated"})
    assert ok.attributes["evidence_class"] == "corroborated"
    inst = MemoryRecordInput(kind="instruction", title="X", digest="Y.",
                             attributes={"category": "rule"})
    assert inst.attributes["category"] == "rule"
    with pytest.raises(ValueError, match="applies_when"):
        MemoryRecordInput(kind="lesson", title="X", digest="Y.",
                          attributes={"applies_when": [42]})


def test_absence_of_conventions_stays_legal(system) -> None:
    plain = MemoryRecordInput(kind="lesson", title="Plain", digest="Still fine.")
    assert "evidence_class" not in plain.attributes
    assert "applies_when" not in plain.attributes


def test_unsourced_lessons_named_by_tending_not_refused(system) -> None:
    [src] = system.remember_many([
        MemoryRecordInput(kind="episode", title="The outage",
                          digest="The Tuesday outage from the missing index."),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="src")
    system.remember_many([
        # Sourced: derived_from edge — never flagged.
        MemoryRecordInput(kind="lesson", title="Index first",
                          digest="Create the index before the batch insert.",
                          edges=(("derived_from", src),)),
        # Unsourced, no provenance: flagged for waking re-digestion.
        MemoryRecordInput(kind="lesson", title="Floating wisdom",
                          digest="Trust but verify."),
        # Unsourced but import-provenanced: legal, never flagged.
        MemoryRecordInput(kind="lesson", title="Archive teaching",
                          digest="From the lineage archive.",
                          attributes={"import_provenance": {"path": "notes/l.md"}}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="lessons")
    report = maintenance_report(system.store, system.journal, scopes=SCOPES)
    flagged = {e["title"] for e in report["unsourced_lessons"]}
    assert flagged == {"Floating wisdom"}
    assert report["counts"]["unsourced_lessons"] == 1


def test_supports_direction_sources_the_claim_not_the_evidence(system) -> None:
    """Semantics c1151 ask 1 (direction bug caught pre-engraving):
    cito:supports is subject=EVIDENCE, object=CLAIM. An episode
    supporting a lesson SOURCES the lesson; a lesson supporting
    something else sources nothing about the lesson itself."""
    ids = system.remember_many([
        # local:1 = the episode-evidence, supports -> local:0 lesson.
        MemoryRecordInput(kind="lesson", title="Backed claim",
                          digest="Batch inserts need the index first."),
        MemoryRecordInput(kind="episode", title="The outage evidence",
                          digest="Tuesday outage traced to the missing index.",
                          edges=(("supports", "local:0"),)),
        # This lesson is the SUBJECT of supports (it evidences a claim) —
        # that does not source IT.
        MemoryRecordInput(kind="claim", title="Some claim",
                          digest="Indexes matter."),
        MemoryRecordInput(kind="lesson", title="Evidence-only lesson",
                          digest="I once saw an index help.",
                          edges=(("supports", "local:2"),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="supports-direction")
    report = maintenance_report(system.store, system.journal, scopes=SCOPES)
    flagged = {e["title"] for e in report["unsourced_lessons"]}
    assert "Backed claim" not in flagged, (
        "episode-supports-lesson did not source the lesson (direction bug)")
    assert "Evidence-only lesson" in flagged, (
        "a lesson acting as evidence was wrongly counted as sourced")


def test_archive_imported_lessons_are_never_flagged_unsourced(system, tmp_path) -> None:
    """Adversary P1.1: the engine's own importer writes seeded_from +
    provenance.archive_path — tending must read the REAL writer's shape,
    not a checker-shaped fixture."""
    from abstractmemory.archive_import import ArchiveFile, apply_import, plan_import

    (tmp_path / "knowledge.md").write_text(
        "# Index discipline\nCreate the index before batch inserts.\n")
    plan = plan_import(str(tmp_path), [ArchiveFile(path="knowledge.md",
                                                   category="knowledge")])
    apply_import(system, plan, scope=SCOPE, owner_id=OWNER)
    report = maintenance_report(system.store, system.journal, scopes=SCOPES)
    assert report["unsourced_lessons"] == [], (
        "the importer's own lesson was flagged unsourced")


def test_lessons_keep_the_strongest_learned_rank() -> None:
    assert KIND_RANKS["lesson"] < KIND_RANKS["episode"]
    assert KIND_RANKS["lesson"] < KIND_RANKS["summary"]
    assert KIND_RANKS["instruction"] < KIND_RANKS["episode"]


def test_correction_chain_by_composition(system) -> None:
    """A corrected lesson is a NEW record refining the old; the old is
    superseded — recall serves only the correction."""
    [old] = system.remember_many([
        MemoryRecordInput(kind="lesson", title="Old rule",
                          digest="Retry three times on any failure.",
                          keywords=("retry",)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="old-rule")
    [new] = system.remember_many([
        MemoryRecordInput(kind="lesson", title="Refined rule",
                          digest="Retry only idempotent operations; fail fast otherwise.",
                          keywords=("retry",),
                          edges=(("refines", old),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="new-rule")
    system.close_record(old, kind="supersede", replacement_ids=[new],
                        reason="correction: retries must be idempotent-only")
    r = system.reconstruct(Stimulus(cue_text="retry"), scopes=SCOPES)
    titles = {h.title for h in r.handles}
    assert "Refined rule" in titles
    assert "Old rule" not in titles
