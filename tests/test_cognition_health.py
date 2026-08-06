"""cognition_health() — the drive-ratio bars (2026-07-18 directive).

Pins: questions open/resolved via answers; problems via resolves;
interests open/explored via the NEW attributes.explores convention
(either id namespace; exploring never closes the interest); empty
categories yield ratio=None (never a fabricated 100%); closure folds
apply; loud validation.
"""

from __future__ import annotations

import pytest

from abstractmemory import MemorySystem, cognition_health
from abstractmemory.records import MemoryRecordInput

OWNER = "entity:hygieia"
SCOPES = [("self", OWNER), ("diary", OWNER), ("life", OWNER)]


def _seed(system: MemorySystem) -> dict:
    ids = {}
    [ids["q1"]] = system.remember_many([
        MemoryRecordInput(kind="diary", title="Q1", digest="What persists?",
                          attributes={"diary_type": "question"},
                          provenance={"source": "owner-direct"})],
        scope="diary", owner_id=OWNER, idempotency_key="q1")
    [ids["q2"]] = system.remember_many([
        MemoryRecordInput(kind="diary", title="Q2", digest="Why do tags fail?",
                          attributes={"diary_type": "question"},
                          provenance={"source": "owner-direct"})],
        scope="diary", owner_id=OWNER, idempotency_key="q2")
    [ids["a1"]] = system.remember_many([
        MemoryRecordInput(kind="diary", title="A1", digest="Traces persist; keys must be seen.",
                          attributes={"answers": ids["q1"]},
                          provenance={"source": "owner-direct"})],
        scope="diary", owner_id=OWNER, idempotency_key="a1")
    [ids["i1"]] = system.remember_many([
        MemoryRecordInput(kind="interest", title="interest: tides",
                          digest="How tides shape harbors.")],
        scope="self", owner_id=OWNER, idempotency_key="i1")
    [ids["i2"]] = system.remember_many([
        MemoryRecordInput(kind="interest", title="interest: archives",
                          digest="What archives keep and lose.")],
        scope="self", owner_id=OWNER, idempotency_key="i2")
    return ids


def test_ratios_fold_open_resolved_and_explored(system) -> None:
    store, journal = system.store, system.journal
    ids = _seed(system)
    h = cognition_health(store, journal, scopes=SCOPES)
    assert h["questions"] == {"open": 1, "resolved": 1, "ratio": 0.5}
    assert h["problems"]["ratio"] is None          # empty category: no bar, not 100%
    assert h["interests"] == {"open": 2, "explored": 0, "ratio": 0.0}

    # EXPLORING an interest (a work episode carrying explores=) moves the
    # ratio without closing the interest — it remains a standing drive.
    system.remember_many([
        MemoryRecordInput(kind="episode", title="tide walk",
                          digest="Walked the tide line, testing the interest.",
                          attributes={"explores": ids["i1"]})],
        scope="life", owner_id=OWNER, idempotency_key="explore-1")
    h2 = cognition_health(store, journal, scopes=SCOPES)
    assert h2["interests"] == {"open": 1, "explored": 1, "ratio": 0.5}

    # The explored interest is still a STANDING record (never closed).
    from abstractmemory import TripleQuery
    still = [a for a in store.query(TripleQuery(subject=ids["i1"], limit=0))]
    assert still, "exploring must never close the interest"


def test_cross_key_discharge_agrees_with_the_card(system) -> None:
    """Gateway G1 finding (room c59, 2026-07-18): entity_card builds ONE
    resolved_by map from BOTH answers= and resolves=, but the first
    cognition_health folded answers-only for questions and resolves-only
    for problems — a question discharged with resolves= (runtime's
    teaching hands it as a desk-moving key) read RESOLVED on the card and
    OPEN on the drive bar. One fold, one truth: the ref ID targets the
    record, the attribute key is only the verb's flavor."""
    from abstractmemory import entity_card

    store, journal = system.store, system.journal
    ids = _seed(system)
    # Discharge the SECOND question with the "wrong" key (resolves=), and
    # file a problem repaired with the "wrong" key (answers=).
    system.remember_many([
        MemoryRecordInput(kind="diary", title="R2",
                          digest="Tags fail when unseen; fixed the render.",
                          attributes={"resolves": ids["q2"]},
                          provenance={"source": "owner-direct"})],
        scope="diary", owner_id=OWNER, idempotency_key="r2")
    [p1] = system.remember_many([
        MemoryRecordInput(kind="diary", title="P1", digest="The meter is stuck.",
                          attributes={"diary_type": "problem"},
                          provenance={"source": "owner-direct"})],
        scope="diary", owner_id=OWNER, idempotency_key="p1")
    system.remember_many([
        MemoryRecordInput(kind="diary", title="F1", digest="Unstuck the meter.",
                          attributes={"answers": p1},
                          provenance={"source": "owner-direct"})],
        scope="diary", owner_id=OWNER, idempotency_key="f1")

    h = cognition_health(store, journal, scopes=SCOPES)
    assert h["questions"] == {"open": 0, "resolved": 2, "ratio": 1.0}
    assert h["problems"] == {"open": 0, "repaired": 1, "ratio": 1.0}

    # And the card agrees exactly — the divergence gateway found is dead.
    # (Card key is "resolved" for both types; the health dict spells the
    # problems verb "repaired" — same fold, per-surface vocabulary.)
    card = entity_card(store, journal, scope_pairs=SCOPES, owner_id=OWNER)
    assert len(card["questions"]["resolved"]) == 2
    assert not card["questions"]["open"]
    assert len(card["problems"]["resolved"]) == 1
    assert not card["problems"]["open"]


def test_closure_folds_apply_and_validation_is_loud(system) -> None:
    store, journal = system.store, system.journal
    ids = _seed(system)
    system.close_record(ids["q2"], reason="withdrawn")
    h = cognition_health(store, journal, scopes=SCOPES)
    assert h["questions"]["open"] == 0              # the closed question left
    assert h["questions"]["resolved"] == 1
    with pytest.raises(ValueError, match="scope"):
        cognition_health(store, journal, scopes=[])


def test_card_carries_a_lessons_section(system) -> None:
    """Iteration-2 build 5: the card gains a lessons section (newest
    first, believed rows, bounded) — the operator believed zero lessons
    existed because no surface rendered them. Count is an inventory,
    never a ratio; the empty state is honest, not alarming."""
    from abstractmemory import entity_card

    card = entity_card(system.store, system.journal,
                       scope_pairs=SCOPES, owner_id=OWNER)
    assert card["lessons"]["total"] == 0
    assert "young life, not a failure" in card["lessons"]["provenance"]

    system.remember_many([
        MemoryRecordInput(
            kind="lesson", title="lesson: describing is not doing",
            digest="Describing a pattern IS the pattern; break it by acting.",
            edges=(("derived_from", _seed(system)["q1"]),))
    ], scope="life", owner_id=OWNER, idempotency_key="l1")
    card = entity_card(system.store, system.journal,
                       scope_pairs=SCOPES, owner_id=OWNER)
    assert card["lessons"]["total"] == 1
    [brief] = card["lessons"]["lessons"]
    assert brief["title"].startswith("lesson: describing")
    # Retracted lessons leave the section (believed rows only).
    system.close_record(brief["record_id"] if "record_id" in brief
                        else brief.get("id") or brief.get("subject"),
                        reason="withdrawn for the fold pin")
    card = entity_card(system.store, system.journal,
                       scope_pairs=SCOPES, owner_id=OWNER)
    assert card["lessons"]["total"] == 0


def test_card_discoveries_carry_the_explored_split(system) -> None:
    """The card compositor and cognition_health share the explores
    convention — entity's Health bar consumes the CARD payload, so the
    split must ride discoveries (additive keys)."""
    from abstractmemory import entity_card

    ids = _seed(system)
    system.remember_many([
        MemoryRecordInput(kind="episode", title="tide walk",
                          digest="Walked the tide line, exploring the interest.",
                          attributes={"explores": ids["i1"]})],
        scope="life", owner_id=OWNER, idempotency_key="explore-card")
    card = entity_card(system.store, system.journal,
                       scope_pairs=SCOPES, owner_id=OWNER)
    d = card["discoveries"]
    assert d["interests_explored"] == 1
    assert d["interests_open"] == 1
    by_title = {i["title"]: i for i in d["interests"]}
    assert by_title["interest: tides"]["explored"] is True
    assert by_title["interest: archives"]["explored"] is False
