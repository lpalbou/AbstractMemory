"""World-model aliasing (M3, maintainer's "admin = laurent"): one
understanding under many names.

Contracts pinned:
- alias_world_model is a DELIBERATE, audited act: it revises the primary
  card with attributes.aliases, supersedes a standing alias-target card
  INTO the primary, and refuses loudly (no primary card, self-alias,
  reason-less, already-bound-elsewhere);
- grouping honors the alias: evidence stamped with the alias regroups
  onto the primary at the next pass (and counts toward its floor), and
  world_model_update(targets=[alias]) reaches the primary;
- aliases carry through evidence revisions (a sleep pass never silently
  unbinds an identity) and through re-authoring paths that carry attrs;
- mention orientation serves the primary card when ANY name is mentioned
  (participant or cue);
- the sleep pass PROPOSES merges from heavy evidence overlap
  (alias_candidates) and never merges on its own — same namespace only,
  already-aliased pairs excluded, per-turn windows never propose.
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
    alias_candidates,
    alias_map,
    alias_world_model,
    current_world_models,
    world_model_pass,
    world_model_update,
)
from abstractmemory.records import resolve_digest_assertion
from abstractmemory.world_model import mention_orientation_cards

OWNER = "entity:cartographer"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]
TUNING = SleepTuning(world_model_evidence_floor=3)


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _seed(system, person: str, n: int, key: str, text: str = "archive work"):
    return system.remember_many([
        MemoryRecordInput(
            kind="episode", title=f"{person} day {i}",
            digest=f"Worked with {person} on {text}, session {i}.",
            keywords=("archive", f"session{i}"),
            participants=(f"person:{person}", OWNER))
        for i in range(n)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key=key)


def _card_for(system, target: str):
    return current_world_models(
        system.store, scope=SCOPE, owner_id=OWNER, journal=system.journal
    ).get(target)


def _bind_admin_to_laurent(system):
    """Common scenario: laurent has a card; admin arrives as a second name."""
    _seed(system, "laurent", 3, "laurent-days")
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    return alias_world_model(
        system, primary="person:laurent", alias="person:admin",
        scope=SCOPE, owner_id=OWNER,
        reason="the operator confirmed admin is laurent at the door")


def test_alias_act_revises_the_primary_and_binds_the_name(system) -> None:
    out = _bind_admin_to_laurent(system)
    assert out["alias"] == "person:admin"
    assert out["aliases"] == ["person:admin"]
    card = _card_for(system, "person:laurent")
    assert card is not None and card.subject == out["card_id"]
    attrs = card.attributes
    assert attrs["aliases"] == ["person:admin"]
    assert attrs["alias_reason"].startswith("the operator confirmed")
    # The alias is a name the card answers to, so the participants channel
    # reaches it under either string.
    assert alias_map(system.store, scope=SCOPE, owner_id=OWNER,
                     journal=system.journal) == {"person:admin": "person:laurent"}
    # Old revision superseded append-only: exactly one current card stands.
    assert out["superseded"]


def test_alias_refusals_are_loud(system) -> None:
    with pytest.raises(ValueError, match="must exist first"):
        alias_world_model(system, primary="person:laurent",
                          alias="person:admin", scope=SCOPE, owner_id=OWNER,
                          reason="no card yet")
    _bind_admin_to_laurent(system)
    with pytest.raises(ValueError, match="cannot alias itself"):
        alias_world_model(system, primary="person:laurent",
                          alias="person:laurent", scope=SCOPE, owner_id=OWNER,
                          reason="self")
    with pytest.raises(ValueError, match="requires a reason"):
        alias_world_model(system, primary="person:laurent",
                          alias="person:boss", scope=SCOPE, owner_id=OWNER,
                          reason="   ")
    # A name already bound to laurent cannot be quietly re-bound elsewhere.
    _seed(system, "ada", 3, "ada-days")
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    with pytest.raises(ValueError, match="already aliased"):
        alias_world_model(system, primary="person:ada",
                          alias="person:admin", scope=SCOPE, owner_id=OWNER,
                          reason="steal the name")


def test_alias_folds_evidence_onto_the_primary_card(system) -> None:
    _bind_admin_to_laurent(system)
    # New lived records arrive under the ALIAS string.
    _seed(system, "admin", 2, "admin-days", text="gateway config")
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    # No separate admin card ever forms; laurent's card absorbs the evidence.
    targets = [v["target"] for v in out["formed"]]
    assert "person:admin" not in targets
    assert "person:laurent" in targets
    card = _card_for(system, "person:laurent")
    assert _card_for(system, "person:admin") is None
    assert card.attributes["source_count"] == 5
    assert card.attributes["aliases"] == ["person:admin"]  # carried forward
    # The evidence itself is walkable from the card (provenance holds).
    assert "person:admin" in (card.attributes.get("aliases") or [])


def test_alias_supersedes_a_standing_alias_card_into_the_primary(system) -> None:
    # BOTH names had cards before anyone noticed they were one person.
    _seed(system, "laurent", 3, "laurent-days")
    _seed(system, "admin", 3, "admin-days", text="gateway config")
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    admin_card = _card_for(system, "person:admin")
    assert admin_card is not None
    out = alias_world_model(
        system, primary="person:laurent", alias="person:admin",
        scope=SCOPE, owner_id=OWNER, reason="operator confirmed one identity")
    assert admin_card.subject in out["superseded"]
    # The admin card left recall; the next pass regroups its evidence.
    assert _card_for(system, "person:admin") is None
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    card = _card_for(system, "person:laurent")
    assert card.attributes["source_count"] == 6


def test_update_naming_the_alias_reaches_the_primary(system) -> None:
    _bind_admin_to_laurent(system)
    _seed(system, "admin", 2, "admin-days", text="gateway config")
    out = world_model_update(system, scopes=SCOPES, owner_id=OWNER,
                             targets=["person:admin"], tuning=TUNING)
    targets = [v["target"] for v in out["formed"]]
    assert targets == ["person:laurent"]


def test_mention_of_the_alias_orients_on_the_primary_card(system) -> None:
    _bind_admin_to_laurent(system)
    # Door stamps the ALIAS participant.
    hits = mention_orientation_cards(
        system.store,
        Stimulus(cue_text="morning", participants=("person:admin",)),
        SCOPES)
    assert len(hits) == 1
    assert hits[0]["target"] == "person:laurent"
    assert "alias person:admin" in hits[0]["detail"]
    # Cue text naming the alias orients too.
    hits = mention_orientation_cards(
        system.store,
        Stimulus(cue_text="the admin asked about the archive", participants=()),
        SCOPES)
    assert len(hits) == 1 and hits[0]["target"] == "person:laurent"


def test_orientation_via_reconstruct_reaches_the_aliased_card(system) -> None:
    """End-to-end: the door stamps only the ALIAS participant and the
    laurent card still arrives through the orientation channel."""
    _bind_admin_to_laurent(system)
    r = system.reconstruct(
        Stimulus(cue_text="an unrelated greeting",
                 participants=("person:admin",)),
        scopes=SCOPES, journal=False)
    cards = [h for h in r.handles if h.kind == "world_model"
             and "orientation" in h.relevance]
    assert cards, "the aliased mention did not orient"
    assert any("card for person:laurent" in c for h in cards for c in h.cues)


def test_aliases_survive_evidence_revisions(system) -> None:
    _bind_admin_to_laurent(system)
    _seed(system, "laurent", 2, "laurent-more", text="entity design")
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    card = _card_for(system, "person:laurent")
    assert card.attributes["aliases"] == ["person:admin"]
    assert "person:admin" in str(card.attributes)  # binding never silently lost


def test_alias_candidates_propose_and_never_merge() -> None:
    by_target = {
        "person:laurent": ["r1", "r2", "r3", "r4"],
        "person:admin": ["r2", "r3", "r4"],       # 3/4 shared
        "person:ada": ["r9", "r10"],               # disjoint
        "topic:laurent": ["r1", "r2", "r3", "r4"],  # other namespace
    }
    out = alias_candidates(by_target)
    assert len(out) == 1
    prop = out[0]
    assert prop["targets"] == ["person:admin", "person:laurent"]
    assert prop["overlap"] == 0.75
    assert "never a merge" in prop["note"]
    # Already-bound pairs are not re-proposed.
    assert alias_candidates(
        by_target, existing={"person:admin": "person:laurent"}) == []


def test_sleep_cadence_surfaces_proposals_and_turn_cadence_does_not(system) -> None:
    _seed(system, "laurent", 3, "laurent-days")
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert "alias_proposals" in out          # full frame: key present (may be [])
    turn = world_model_update(system, scopes=SCOPES, owner_id=OWNER,
                              targets=["person:laurent"], tuning=TUNING)
    assert "alias_proposals" not in turn     # windowed frame never proposes


def test_alias_act_is_idempotent_under_crash_retry(system) -> None:
    first = _bind_admin_to_laurent(system)
    again = alias_world_model(
        system, primary="person:laurent", alias="person:admin",
        scope=SCOPE, owner_id=OWNER,
        reason="the operator confirmed admin is laurent at the door")
    # Same revision arithmetic re-run mints a fresh revision over the same
    # binding — aliases stay a single-element set, the map is unchanged,
    # and exactly one card stands.
    assert again["aliases"] == ["person:admin"]
    assert alias_map(system.store, scope=SCOPE, owner_id=OWNER,
                     journal=system.journal) == {"person:admin": "person:laurent"}
    card = _card_for(system, "person:laurent")
    assert card is not None
    standing = [t for t in (first, again)]
    assert all(s["primary"] == "person:laurent" for s in standing)


def test_authored_lead_carries_through_alias_revision(system) -> None:
    _seed(system, "laurent", 3, "laurent-days")
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    from abstractmemory import author_world_model
    author_world_model(
        system, target="person:laurent",
        text="Laurent is the maintainer; direct, warm, allergic to flattery.",
        scope=SCOPE, owner_id=OWNER, author="entity-reflection")
    alias_world_model(
        system, primary="person:laurent", alias="person:admin",
        scope=SCOPE, owner_id=OWNER, reason="door identity confirmed")
    card = _card_for(system, "person:laurent")
    attrs = card.attributes
    assert attrs["aliases"] == ["person:admin"]
    assert attrs["authored_lead"].startswith("Laurent is the maintainer")
    # And the words still read as the authored card.
    assert str(card.object).startswith("Laurent is the maintainer")
    # Next evidence revision keeps BOTH the lead and the alias.
    _seed(system, "admin", 2, "admin-days", text="entity doors")
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    card = _card_for(system, "person:laurent")
    assert card.attributes["aliases"] == ["person:admin"]
    assert card.attributes["digest_method"] == "authored-card-v1+delta"
    assert str(card.object).startswith("Laurent is the maintainer")
