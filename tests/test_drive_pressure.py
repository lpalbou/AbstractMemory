"""drive_pressure() — the lifecycle gate's one-call read (laurent's
"awake is not a state" ruling, room c203, 2026-07-20).

Pins: composes the existing standing folds (questions/problems/
commitments/ideas via the diary reads; unexplored interests via the
explores convention; unresolved tensions via the dream fold); journal
folds apply; pure read (deposits nothing); loud validation; the note
carries the never-verdict contract.
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
    drive_pressure,
)

OWNER = "entity:hygieia"
SCOPES = [("self", OWNER), ("diary", OWNER), ("life", OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _diary(system, title, digest, diary_type, key, **attrs):
    return system.remember_many([
        MemoryRecordInput(kind="diary", title=title, digest=digest,
                          attributes={"diary_type": diary_type, **attrs},
                          provenance={"source": "owner-direct"})],
        scope="diary", owner_id=OWNER, idempotency_key=key)


def test_pressure_composes_the_standing_sets(system) -> None:
    store, journal = system.store, system.journal
    [q1] = _diary(system, "Q1", "What persists?", "question", "q1")
    _diary(system, "Q2", "Why do tags fail?", "question", "q2")
    _diary(system, "P1", "The meter is stuck.", "problem", "p1")
    _diary(system, "C1", "Ask Ada about her paper.", "commitment", "c1")
    _diary(system, "I1", "Maybe a signal journal.", "idea", "i1")
    [int1] = system.remember_many([
        MemoryRecordInput(kind="interest", title="interest: tides",
                          digest="How tides shape harbors.")],
        scope="self", owner_id=OWNER, idempotency_key="int1")
    system.remember_many([
        MemoryRecordInput(kind="interest", title="interest: archives",
                          digest="What archives keep.")],
        scope="self", owner_id=OWNER, idempotency_key="int2")
    # Exploring one interest removes it from the unexplored pull.
    system.remember_many([
        MemoryRecordInput(kind="episode", title="tide walk",
                          digest="Walked the tide line.",
                          attributes={"explores": int1})],
        scope="life", owner_id=OWNER, idempotency_key="exp1")
    # A standing unresolved dream = one tension.
    system.remember_many([
        MemoryRecordInput(kind="dream", title="Dream: old tension",
                          digest="An unresolved tension.",
                          attributes={"continuation_state": "unresolved",
                                      "interpretation_required": True,
                                      "parent_dream_ids": []})],
        scope="life", owner_id=OWNER, idempotency_key="d1")

    seq_before = system.current_seq()
    out = drive_pressure(store, journal, scopes=SCOPES)
    assert out["open_questions"] == 2
    assert out["open_problems"] == 1
    assert out["open_commitments"] == 1
    assert out["incubating_ideas"] == 1
    assert out["unexplored_interests"] == 1
    assert out["unresolved_tensions"] == 1
    assert out["total_open"] == 7
    assert "never-100%" in out["note"]          # the never-verdict contract
    assert system.current_seq() == seq_before   # pure read

    # Discharge (cross-key union applies) + closure both reduce pressure.
    _diary(system, "A1", "Answered.", "reflection", "a1", answers=q1)
    again = drive_pressure(store, journal, scopes=SCOPES)
    assert again["open_questions"] == 1
    assert again["total_open"] == 6


def test_fold_agreement_pins_adversary_findings(system) -> None:
    """Drive-pressure adversary 1 (2026-07-20), findings 2-5 pinned:
    (2) a RETRACTED answering entry stops discharging (believed-rows fold
    in _open_unresolved — wake surface agrees with card+health);
    (3) a parked interest (lifecycle=rejected) is not pressure;
    (4) a retracted exploring episode stops counting as explored;
    (5) the card counts continued dreams as standing (gate/card agree)."""
    from abstractmemory import entity_card

    store, journal = system.store, system.journal
    # (2) retracted discharger.
    [q] = _diary(system, "Q", "Standing question?", "question", "fq")
    [ans] = _diary(system, "A", "Answered it.", "reflection", "fa", answers=q)
    assert drive_pressure(store, journal, scopes=SCOPES)["open_questions"] == 0
    system.close_record(ans, reason="retracted for the pin")
    assert drive_pressure(store, journal, scopes=SCOPES)["open_questions"] == 1

    # (3) parked interest leaves the pull (reject_candidate folds lifecycle).
    [i1] = system.remember_many([
        MemoryRecordInput(kind="interest", title="interest: kilns",
                          digest="Kiln temperatures.")],
        scope="self", owner_id=OWNER, idempotency_key="fi1")
    assert drive_pressure(store, journal, scopes=SCOPES)["unexplored_interests"] == 1
    system.reject_candidate(i1, scope="self", owner_id=OWNER,
                            reason="parked for the pin")
    assert drive_pressure(store, journal, scopes=SCOPES)["unexplored_interests"] == 0

    # (4) retracted exploring episode un-explores.
    [i2] = system.remember_many([
        MemoryRecordInput(kind="interest", title="interest: tides",
                          digest="Tides.")],
        scope="self", owner_id=OWNER, idempotency_key="fi2")
    [ep] = system.remember_many([
        MemoryRecordInput(kind="episode", title="walk", digest="Tide walk.",
                          attributes={"explores": i2})],
        scope="life", owner_id=OWNER, idempotency_key="fe1")
    assert drive_pressure(store, journal, scopes=SCOPES)["unexplored_interests"] == 0
    system.close_record(ep, reason="retracted for the pin")
    assert drive_pressure(store, journal, scopes=SCOPES)["unexplored_interests"] == 1

    # (5) a continued dream counts on BOTH surfaces.
    system.remember_many([
        MemoryRecordInput(kind="dream", title="Dream: continuation",
                          digest="The tension pressed again.",
                          attributes={"continuation_state": "continued",
                                      "interpretation_required": True,
                                      "parent_dream_ids": []})],
        scope="life", owner_id=OWNER, idempotency_key="fd1")
    assert drive_pressure(store, journal, scopes=SCOPES)["unresolved_tensions"] == 1
    card = entity_card(store, journal, scope_pairs=SCOPES, owner_id=OWNER)
    assert card["discoveries"]["unresolved_dreams"] == 1


def test_pressure_validation_and_dedup(system) -> None:
    with pytest.raises(ValueError, match="scope"):
        drive_pressure(system.store, system.journal, scopes=[])
    # Duplicated ladder pairs never double-count.
    _diary(system, "Q1", "One question.", "question", "q1")
    out = drive_pressure(system.store, system.journal,
                         scopes=[("diary", OWNER), ("diary", OWNER)])
    assert out["open_questions"] == 1


def test_exact_counts_bound_constant_and_machine_purity(system) -> None:
    """Adversary-2 findings pinned: (2) counts are EXACT past the
    composed reads' default 100-cap (limit=0 everywhere — a gate
    comparing against the ruled bound must never read a saturated
    total); (4) DRIVE_PRESSURE_BOUND is the one exported source of
    laurent's ruled number, DECLARED never APPLIED (no verdict field in
    the payload); (6) machine rows never discharge drives — a
    maintenance-candidate row carrying explores= does not read an
    interest as explored."""
    from abstractmemory import DRIVE_PRESSURE_BOUND

    store, journal = system.store, system.journal
    assert DRIVE_PRESSURE_BOUND == 20
    for n in range(105):
        _diary(system, f"Q{n}", f"Question {n}?", "question", f"exact-{n}")
    out = drive_pressure(store, journal, scopes=SCOPES)
    assert out["open_questions"] == 105          # past the default cap
    assert "verdict" not in out                  # declared, never applied

    [i1] = system.remember_many([
        MemoryRecordInput(kind="interest", title="interest: glass",
                          digest="Glasswork.")],
        scope="self", owner_id=OWNER, idempotency_key="mp-i")
    system.remember_many([
        MemoryRecordInput(kind="summary", title="machine grouping",
                          digest="Grouped overnight.",
                          edges=(("summarizes", i1),),
                          attributes={"maintenance_candidate": True,
                                      "explores": i1})],
        scope="life", owner_id=OWNER, idempotency_key="mp-m")
    out2 = drive_pressure(store, journal, scopes=SCOPES)
    assert out2["unexplored_interests"] == 1     # the machine stamp is inert
