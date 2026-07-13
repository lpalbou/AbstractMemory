"""World-model orientation cards (backlog 0033): knowledge refined over time.

Contracts pinned:
- a target clearing the evidence floor gets ONE card: source-linked
  (derived_from), fingerprint-idempotent, mechanical-v1 digest that names
  its own limits ("orientation, never authority");
- new evidence REVISES: revision N+1 with a refines edge, the old card
  superseded append-only; recall serves only the current revision;
- the owner's own co-presence stamp never becomes a card target;
- derived artifacts (dreams, cards, maintenance candidates) never evidence
  a card, and cards never enter the dream substrate (loop-breakers);
- a participant card surfaces via the participants channel when the person
  appears (the SITUATION "profile recall" leg — no new recall machinery);
- cards never enter identity seats; forming deposits nothing (D2).
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
    SleepTuning,
    Stimulus,
    current_world_models,
    sleep_pass,
    structural_report,
    world_model_pass,
)
from abstractmemory.records import resolve_digest_assertion

OWNER = "entity:cartographer"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]
TUNING = SleepTuning(world_model_evidence_floor=3)


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _seed_ada(system, n: int = 3, key: str = "ada-days"):
    return system.remember_many([
        MemoryRecordInput(
            kind="episode", title=f"Ada day {i}",
            digest=f"Worked with Ada on the archive, session {i}.",
            keywords=("archive", f"session{i}"),
            participants=("person:ada", OWNER))
        for i in range(n)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key=key)


def test_card_forms_above_floor_with_sources_and_honest_digest(system) -> None:
    ids = _seed_ada(system)
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert out["formed_count"] == 1
    verdict = out["formed"][0]
    assert verdict["target"] == "person:ada"
    assert verdict["revision"] == 1
    card = resolve_digest_assertion(system.store, verdict["card_id"])
    attrs = card.attributes
    assert attrs["record_kind"] == "world_model"
    assert attrs["target"] == "person:ada"
    assert attrs["digest_method"] == "mechanical-v1"
    assert "orientation, never authority" in str(card.object)
    # Source-linked: derived_from edges to the evidence.
    from abstractmemory import TripleQuery
    edges = [a for a in system.store.query(TripleQuery(subject=card.subject, limit=0))
             if isinstance(a.attributes, dict) and a.attributes.get("record_edge")]
    linked = {a.object for a in edges if a.predicate == "derived_from"}
    assert linked == set(ids)


def test_below_floor_forms_nothing_and_owner_is_never_a_target(system) -> None:
    _seed_ada(system, n=2, key="two-only")
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert out["formed_count"] == 0
    assert "person:ada" not in out["eligible"]
    # The owner co-stamps every record — but never becomes a target.
    assert not any(t == OWNER for t in out["eligible"])


def test_new_evidence_revises_append_only_and_current_wins(system) -> None:
    _seed_ada(system)
    first = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    card1 = first["formed"][0]["card_id"]
    # Idempotent night: same evidence, no new card.
    again = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert again["formed_count"] == 0
    assert any(u["card_id"] == card1 for u in again["unchanged"])

    # New encounter → revision 2, refines edge, old card superseded.
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Ada day 9",
                          digest="Ada showed the finished archive index.",
                          keywords=("archive", "index"),
                          participants=("person:ada", OWNER)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="ada-again")
    third = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert third["formed_count"] == 1
    verdict = third["formed"][0]
    assert verdict["revision"] == 2
    card2 = verdict["card_id"]
    from abstractmemory import TripleQuery
    edges = [a for a in system.store.query(TripleQuery(subject=card2, limit=0))
             if isinstance(a.attributes, dict) and a.attributes.get("record_edge")]
    assert any(a.predicate == "refines" and a.object == card1 for a in edges)
    # Current-wins: only revision 2 stands.
    current = current_world_models(system.store, scope=SCOPE, owner_id=OWNER,
                                   journal=system.journal)
    assert current["person:ada"].subject == card2
    # And recall never serves the superseded card.
    r = system.reconstruct(Stimulus(cue_text="archive"), scopes=SCOPES)
    row1 = resolve_digest_assertion(system.store, card1).assertion_id
    assert row1 not in {h.record_id for h in r.handles}


def test_derived_artifacts_never_evidence_and_cards_stay_out_of_dreams(system) -> None:
    _seed_ada(system)
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    # The card itself must not evidence a future card or enter the report.
    out2 = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert out2["formed_count"] == 0  # card didn't feed itself a new target set
    report = structural_report(system.store, system.journal, scopes=SCOPES)
    kinds = {info["kind"] for info in report["records"].values()}
    assert "world_model" not in kinds, "a card entered the dream substrate"


def test_participant_card_surfaces_when_the_person_appears(system) -> None:
    _seed_ada(system)
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    card_id = out["formed"][0]["card_id"]
    row = resolve_digest_assertion(system.store, card_id).assertion_id
    r = system.reconstruct(
        Stimulus(cue_text="zzz nothing lexical", participants=("person:ada",)),
        scopes=SCOPES)
    assert row in {h.record_id for h in r.handles}, (
        "the orientation card did not arrive with the encounter")


def test_topic_targets_ride_the_same_path(system) -> None:
    system.remember_many([
        MemoryRecordInput(kind="episode", title=f"Harbor note {i}",
                          digest=f"Note {i} about the harbor works.",
                          keywords=("harbor",), topic="harbor-works")
        for i in range(3)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="harbor")
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    targets = {v["target"] for v in out["formed"]}
    assert "topic:harbor-works" in targets


def test_cards_never_enter_identity_seats(system) -> None:
    """Identity seats are value/purpose/trait only — a card must not ride
    the self admission even when it exists in the self scope."""
    from abstractmemory.self_component import self_records_read

    _seed_ada(system)
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    identity = self_records_read(system.store, system.journal,
                                 scope=SCOPE, owner_id=OWNER)
    assert all((a.attributes or {}).get("record_kind") in ("value", "purpose", "trait")
               for a in identity)


def test_forming_cards_deposits_nothing(system) -> None:
    ids = _seed_ada(system)
    before = system.access_counts(record_ids=ids)
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert system.access_counts(record_ids=ids) == before


def test_report_only_writes_nothing(system) -> None:
    _seed_ada(system)
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER,
                           report_only=True, tuning=TUNING)
    assert out["formed"] and out["formed"][0]["formed"] is False
    assert current_world_models(system.store, scope=SCOPE, owner_id=OWNER) == {}


def test_sleep_pass_carries_the_world_model_phase(system) -> None:
    _seed_ada(system)
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert night["phases"] == ("resolution", "maintenance", "world_models", "dream")
    assert night["world_models"]["pass_name"] == "world_model_pass"
    assert night["world_models"]["formed_count"] == 1


def test_crash_replay_repairs_an_interrupted_revision(system) -> None:
    """Adversary P1-3: a crash between remember_many (rev N+1 formed) and
    close_record(rev N) must not leave two standing revisions forever —
    the next pass repairs (closure ids are deterministic; re-close is a
    journal no-op)."""
    _seed_ada(system)
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Ada day 9",
                          digest="Ada showed the finished archive index.",
                          keywords=("archive", "index"),
                          participants=("person:ada", OWNER)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="ada-again")

    # Simulate the crash: revision 2 forms but the supersede never lands.
    real_close = system.close_record
    calls = {"n": 0}

    def crashing_close(*args, **kwargs):
        calls["n"] += 1
        raise RuntimeError("simulated crash before the supersede")

    system.close_record = crashing_close  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    system.close_record = real_close  # type: ignore[method-assign]
    from abstractmemory import standing_world_models

    standing = standing_world_models(system.store, scope=SCOPE, owner_id=OWNER,
                                     journal=system.journal)
    assert len(standing["person:ada"]) == 2, "crash simulation did not fork"

    # The replay pass REPAIRS: one standing card, highest revision.
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert out["repaired"], "the interrupted revision was not repaired"
    standing_after = standing_world_models(system.store, scope=SCOPE,
                                           owner_id=OWNER, journal=system.journal)
    assert len(standing_after["person:ada"]) == 1
    assert standing_after["person:ada"][0].attributes["revision"] == 2


def test_cards_never_enter_tending_inputs(system) -> None:
    """Adversary P2: cards are excluded from the maintenance scan too —
    a card must not appear in metadata gaps or duplicate groups."""
    from abstractmemory import maintenance_report

    _seed_ada(system)
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    report = maintenance_report(system.store, system.journal, scopes=SCOPES)
    flagged = {g["record_id"] for g in report["metadata_gaps"]}
    assert not any(rid.startswith("ex:world_model") for rid in flagged), (
        "a world-model card entered tending inputs")


def test_owner_must_be_named(system) -> None:
    with pytest.raises(ValueError, match="owner_id"):
        world_model_pass(system, scopes=SCOPES, owner_id="", tuning=TUNING)


def test_max_cards_budget_bounds_a_night(system) -> None:
    for i in range(3):
        system.remember_many([
            MemoryRecordInput(kind="episode", title=f"P{i} day {j}",
                              digest=f"Time with person {i}, day {j}.",
                              participants=(f"person:p{i}", OWNER))
            for j in range(3)
        ], scope=SCOPE, owner_id=OWNER, idempotency_key=f"p{i}-days")
    tight = SleepTuning(world_model_evidence_floor=3, world_model_max_cards=2)
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=tight)
    assert out["formed_count"] == 2
    assert any("max_cards" in s["reason"] for s in out["skipped"])
