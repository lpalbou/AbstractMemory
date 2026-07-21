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
    author_world_model,
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
    # v2 floor (2026-07-18 redesign): a BRIEFING quoting the evidence's
    # actual sentences, not a keyword cloud — the maintainer's "content is
    # completely wrong" fix at the mechanical layer.
    assert attrs["digest_method"] == "mechanical-card-v2"
    body = str(card.object)
    assert body.startswith("What I know of ada:")
    assert "Worked with Ada on the archive" in body   # evidence gist quoted
    assert "Orientation, never authority" in body
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


def test_elected_topics_on_summaries_evidence_cards(system) -> None:
    """The seam runtime's topic-election lane builds against (room c102,
    2026-07-19): the entity elects the day's subjects at reflection; the
    elected topics land as attributes.topics (LIST — a day may circle two
    subjects) on the session SUMMARY record. Pins: (a) summary is
    ELIGIBLE evidence (not a derived-artifact exclusion — only
    dream/world_model are); (b) the topics list fans out to one target
    per subject; (c) three sessions circling one concept cross the floor
    and the card forms; (d) the single attributes.topic spelling still
    works and folds with the list."""
    for i in range(3):
        [ep] = system.remember_many([
            MemoryRecordInput(
                kind="episode", title=f"day {i} exchange",
                digest=f"Worked through day {i}'s thread.")
        ], scope=SCOPE, owner_id=OWNER, idempotency_key=f"day-ep-{i}")
        system.remember_many([
            MemoryRecordInput(
                kind="summary", title=f"session reflection {i}",
                digest=f"Day {i} circled coherence — what holds a self together.",
                keywords=("reflection",),
                edges=(("summarizes", ep),),
                attributes={"topics": ["coherence", "continuity"]})
        ], scope=SCOPE, owner_id=OWNER, idempotency_key=f"day-{i}")
    # One record with the single spelling joins the same fold.
    system.remember_many([
        MemoryRecordInput(
            kind="episode", title="coherence checker run",
            digest="Ran the coherence checker honestly.",
            attributes={"topic": "coherence"})
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="checker")
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    targets = {v["target"]: v for v in out["formed"]}
    assert "topic:coherence" in targets          # 4 evidence records
    assert "topic:continuity" in targets         # 3 (floor exactly)
    assert targets["topic:coherence"]["source_count"] == 4
    assert targets["topic:continuity"]["source_count"] == 3


def test_sleep_discovery_mints_recurring_subjects_without_stamps(system) -> None:
    """Target discovery (2026-07-19, laurent c158 'cards must accumulate'):
    a COMPOUND keyword recurring across >= discovery_sessions DISTINCT
    sessions becomes a topic card at the sleep pass with ZERO stamps on
    any record. Guards pinned: compound-only (live simulation on the real
    store showed single-word recurrence yields function-word residue —
    'without', 'because'; no frequency gate turns residue into subjects);
    underscore identifiers never subjects; one chatty session never
    mints; the per-turn windowed lane never discovers."""
    # 12 records across 4 sessions: "clinical trials" (compound) rides 3
    # records in 3 DISTINCT sessions; "coherence" (single word) recurs
    # identically but stays elected-lane-only; "diary_read" (identifier)
    # recurs and is machine vocabulary; "kiln-work" recurs inside ONE
    # session only.
    for i in range(4):
        for j in range(3):
            kws = ["morning"]
            if j == 0 and i < 3:
                kws += ["clinical trials", "coherence", "diary_read"]
            if i == 0:
                kws.append("kiln-work")
            system.remember_many([
                MemoryRecordInput(
                    kind="episode", title=f"s{i} r{j}",
                    digest=f"Session {i} record {j}.",
                    keywords=tuple(kws),
                    provenance={"run_id": f"run-{i}"})
            ], scope=SCOPE, owner_id=OWNER, idempotency_key=f"disc-{i}-{j}")

    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    targets = {v["target"] for v in out["formed"]}
    assert "topic:clinical trials" in targets    # compound subject: discovered
    assert "topic:coherence" not in targets      # single word: elected lane only
    assert "topic:diary_read" not in targets     # identifier: machine vocabulary
    assert "topic:kiln-work" not in targets      # one session: never a subject
    assert "topic:morning" not in targets        # single word (and ambient)

    # The per-turn incremental lane never discovers (targets + window).
    from abstractmemory import world_model_update as _update
    turn = _update(system, scopes=SCOPES, owner_id=OWNER,
                   targets=["person:nobody"], tuning=TUNING)
    assert turn["formed"] == []

    # Provenance-less records share ONE unknown session — three
    # owner-direct writes can never mint a subject (the conservative
    # fallback pinned).
    system.remember_many([
        MemoryRecordInput(kind="episode", title=f"anon {j}",
                          digest=f"Anonymous note {j}.", keywords=("glass",))
        for j in range(3)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="anon")
    again = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert "topic:glass" not in {v["target"] for v in again["formed"]}


def test_interests_declare_subjects_and_card_immediately(system) -> None:
    """Interests-as-targets (laurent c171 'dozens of cards by now';
    entity c182 + runtime c174 reconciliation, adopted): a kind=interest
    record IS an elected subject declaration — its title's subject head
    becomes a topic target and the election itself clears the evidence
    floor (demanding 3 records would re-litigate his own act). Same
    subject folds to one card; the per-turn windowed lane never derives
    from interests."""
    system.remember_many([
        MemoryRecordInput(
            kind="interest",
            title="interest: Decentralized clinical trials and health equity — "
                  "how removing structural barriers changes outcomes",
            digest="Decentralized clinical trials and health equity — how "
                   "removing structural barriers (travel, geography) changes outcomes.")
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="int-1")
    system.remember_many([
        MemoryRecordInput(
            kind="interest",
            title="interest: The texture of continuity across time — how to "
                  "leave traces for future-me",
            digest="the texture of continuity across time — leaving traces.")
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="int-2")
    # A second interest declaring the SAME subject folds, never a twin card.
    system.remember_many([
        MemoryRecordInput(
            kind="interest",
            title="interest: the texture of continuity across time — revisited",
            digest="the texture of continuity across time — revisited tonight.")
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="int-3")

    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    targets = {v["target"]: v for v in out["formed"]}
    assert "topic:decentralized clinical trials and health equity" in targets
    assert "topic:texture of continuity across time" in targets
    assert targets["topic:texture of continuity across time"]["source_count"] == 2
    # The card body is the v2 briefing quoting HIS interest words.
    card = resolve_digest_assertion(
        system.store,
        targets["topic:decentralized clinical trials and health equity"]["card_id"])
    assert "Decentralized clinical trials" in str(card.object)


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
    assert night["phases"] == ("resolution", "maintenance", "world_models", "mining", "dream")
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


# ---------------------------------------------------------------------------
# the authored layer (2026-07-18 redesign: cards must read as briefings)
# ---------------------------------------------------------------------------


def test_feeling_line_rides_the_floor_when_appraised(system) -> None:
    """'I instantly know if I like him': gradation standing renders on the
    card floor; never fabricated for never-appraised targets."""
    _seed_ada(system)
    system.appraise("person:ada", sign=1, magnitude=3.0,
                    reason="the archive work was a joy",
                    scope=SCOPE, owner_id=OWNER)
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    card = resolve_digest_assertion(system.store, out["formed"][0]["card_id"])
    assert "Standing feeling: net +3" in str(card.object)


def test_concept_spelled_feelings_surface_on_topic_cards(system) -> None:
    """Runtime's build-4 adversary F4: feel elections teach concept:<words>
    while card targets mint topic:<words> — the card's feeling lookup
    falls back to the concept twin (alias READ only; engraved spellings
    keep their keys, no valence merge). The exact topic: spelling wins
    when both exist."""
    system.remember_many([
        MemoryRecordInput(kind="episode", title=f"coherence day {i}",
                          digest=f"Worked the coherence thread, day {i}.",
                          attributes={"topic": "coherence"})
        for i in range(3)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="coh-days")
    # He felt it in the taught spelling (concept:), not the card's (topic:).
    system.appraise("concept:coherence", sign=1, magnitude=2.0,
                    reason="this thread rewards me",
                    scope=SCOPE, owner_id=OWNER)
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    [verdict] = [v for v in out["formed"] if v["target"] == "topic:coherence"]
    card = resolve_digest_assertion(system.store, verdict["card_id"])
    assert "Standing feeling: net +2" in str(card.object)

    # Exact spelling WINS when both exist (no fold — the twin is fallback).
    system.appraise("topic:coherence", sign=1, magnitude=1.0,
                    reason="named directly", scope=SCOPE, owner_id=OWNER)
    system.remember_many([
        MemoryRecordInput(kind="episode", title="coherence day extra",
                          digest="One more coherence session.",
                          attributes={"topic": "coherence"})
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="coh-extra")
    out2 = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    [v2] = [v for v in out2["formed"] if v["target"] == "topic:coherence"]
    card2 = resolve_digest_assertion(system.store, v2["card_id"])
    assert "Standing feeling: net +1" in str(card2.object)


def test_author_world_model_replaces_words_and_keeps_provenance(system) -> None:
    """The distillation layer: authored prose supersedes the floor through
    the same revision chain; evidence lineage carries; the engine never
    invents or accepts empty/identical text; floor-less targets refuse."""
    ids = _seed_ada(system)
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    floor_id = out["formed"][0]["card_id"]

    with pytest.raises(ValueError, match="no standing world-model card"):
        author_world_model(system, target="person:nobody", text="words",
                           scope=SCOPE, owner_id=OWNER)
    with pytest.raises(ValueError, match="empty text"):
        author_world_model(system, target="person:ada", text="  ",
                           scope=SCOPE, owner_id=OWNER)

    authored = author_world_model(
        system, target="person:ada",
        text="Ada is the archivist I built the index with; steady, precise, "
             "kind under pressure. I trust her reading of the stacks.",
        scope=SCOPE, owner_id=OWNER, author="entity-reflection")
    assert authored["revision"] == 2
    card = resolve_digest_assertion(system.store, authored["card_id"])
    assert str(card.object).startswith("Ada is the archivist")
    assert card.attributes["digest_method"] == "authored-card-v1"
    # Provenance carried: derived_from edges to the ORIGINAL evidence.
    from abstractmemory import TripleQuery
    edges = [a for a in system.store.query(TripleQuery(subject=card.subject, limit=0))
             if isinstance(a.attributes, dict) and a.attributes.get("record_edge")]
    linked = {a.object for a in edges if a.predicate == "derived_from"}
    assert linked == set(ids)
    assert any(a.predicate == "refines" and a.object == floor_id for a in edges)
    # Current-wins: only the authored card stands.
    current = current_world_models(system.store, scope=SCOPE, owner_id=OWNER,
                                   journal=system.journal)["person:ada"]
    assert current.subject == authored["card_id"]
    # Idempotent re-apply of the SAME words reads as SUCCESS-ALREADY-CURRENT
    # (adversary finding 10: a crash-retry of an authoring that landed must
    # not be indistinguishable from a caller error), applies nothing.
    again = author_world_model(system, target="person:ada",
                               text=str(card.object), scope=SCOPE, owner_id=OWNER)
    assert again["applied"] is False
    assert again["card_id"] == authored["card_id"]
    assert again["revision"] == 2


def test_authored_lead_survives_new_evidence_with_one_delta(system) -> None:
    """New evidence must never demote an authored card back to the floor:
    the lead stands, ONE mechanical delta names what is new, and deltas
    never stack across revisions."""
    _seed_ada(system)
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    author_world_model(system, target="person:ada",
                       text="Ada, the archivist. Steady and precise.",
                       scope=SCOPE, owner_id=OWNER)
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Ada day 9",
                          digest="Ada showed the finished archive index today.",
                          participants=("person:ada", OWNER)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="ada-nine")
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert out["formed_count"] == 1
    card = resolve_digest_assertion(system.store, out["formed"][0]["card_id"])
    body = str(card.object)
    assert body.startswith("Ada, the archivist. Steady and precise.")
    assert "Since then (1 new record(s)" in body
    assert "finished archive index" in body
    assert card.attributes["digest_method"] == "authored-card-v1+delta"

    # A SECOND evidence wave re-derives ONE delta over the same lead —
    # the prior delta never stacks into the new digest.
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Ada day 10",
                          digest="Ada started the map room catalogue.",
                          participants=("person:ada", OWNER)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="ada-ten")
    out2 = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    card2 = resolve_digest_assertion(system.store, out2["formed"][0]["card_id"])
    body2 = str(card2.object)
    assert body2.count("Since then") == 1
    assert body2.startswith("Ada, the archivist.")


# ---------------------------------------------------------------------------
# mention => instant orientation (2026-07-18 directive)
# ---------------------------------------------------------------------------


def test_mentioned_target_admits_its_current_card(system) -> None:
    """'if I talk with the entity, it retrieves my card; if he thinks about
    continuity, it retrieves the continuity card' — participants match
    exactly; cue text matches the target name's tokens; unmentioned cards
    stay out; the card rides as a channel match (spread seed included)."""
    _seed_ada(system)
    system.remember_many([
        MemoryRecordInput(kind="episode", title=f"Continuity note {i}",
                          digest=f"Thought about continuity across gaps, pass {i}.",
                          attributes={"topic": "continuity"})
        for i in range(3)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="continuity-days")
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER,
                     tuning=SleepTuning(world_model_evidence_floor=3,
                                        world_model_max_cards=4))

    # Participant mention: the door-stamped visitor retrieves their card.
    r = system.reconstruct(
        Stimulus(cue_text="an unrelated greeting", participants=("person:ada",)),
        scopes=SCOPES, journal=False)
    ada_cards = [h for h in r.handles if h.kind == "world_model"
                 and "orientation" in h.relevance]
    assert ada_cards, "the visitor's card did not admit on participant mention"
    assert any("card for person:ada" in c for h in ada_cards for c in h.cues)

    # Cue-text mention: thinking about the topic retrieves the topic card.
    r2 = system.reconstruct(
        Stimulus(cue_text="what persists — continuity across my own gaps?"),
        scopes=SCOPES, journal=False)
    topic_cards = [h for h in r2.handles if h.kind == "world_model"
                   and "orientation" in h.relevance]
    assert topic_cards, "the topic card did not admit on cue mention"

    # No mention, no card via orientation (other channels may still match
    # it lexically — assert the ORIENTATION channel stayed quiet).
    r3 = system.reconstruct(Stimulus(cue_text="sailing regatta tonight"),
                            scopes=SCOPES, journal=False)
    assert not any("orientation" in h.relevance for h in r3.handles)


def test_adversary_folds_delta_baseline_shrink_and_lineage(system) -> None:
    """Findings 1-4 pinned: (1) an authored lead containing the delta
    phrase survives verbatim (attribute-carried, never digest-split);
    (2) the delta baseline is SINCE THE AUTHORING, not since the last
    pass; (3) evidence shrink fabricates no delta; (4) a re-seen
    evidence fingerprint mints a fresh revision instead of resurrecting
    a closed card (lineage never dies)."""
    _seed_ada(system)
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    lead = ("Ada, archivist.\n\nSince then I have trusted her — "
            "that phrase is part of MY words.")
    author_world_model(system, target="person:ada", text=lead,
                       scope=SCOPE, owner_id=OWNER)

    # Two evidence waves; the delta must count BOTH new records on the
    # second pass (baseline = authoring, not last pass) and the lead —
    # delta phrase included — must survive byte-verbatim.
    for i, key in ((9, "ada-nine"), (10, "ada-ten")):
        system.remember_many([
            MemoryRecordInput(kind="episode", title=f"Ada day {i}",
                              digest=f"Ada event number {i}.",
                              participants=("person:ada", OWNER)),
        ], scope=SCOPE, owner_id=OWNER, idempotency_key=key)
        world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    current = current_world_models(system.store, scope=SCOPE, owner_id=OWNER,
                                   journal=system.journal)["person:ada"]
    body = str(current.object)
    assert body.startswith(lead)                      # finding 1
    assert "Since then (2 new record(s)" in body      # finding 2
    assert "Ada event number 9" in body               # both waves named

    # Evidence SHRINK with nothing new vs the authoring baseline: RE-AUTHOR
    # (baseline now covers all current evidence), then retract one source —
    # the delta must say "revised", never fabricate old records as new.
    lead2 = "Ada, archivist and friend. My words, second edition."
    author_world_model(system, target="person:ada", text=lead2,
                       scope=SCOPE, owner_id=OWNER)
    day9 = next(a.subject for a in system.store.query(
        __import__("abstractmemory").TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))
        if isinstance(a.attributes, dict) and a.attributes.get("title") == "Ada day 9")
    system.close_record(day9, reason="never happened that way")
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert out["formed_count"] == 1
    current2 = current_world_models(system.store, scope=SCOPE, owner_id=OWNER,
                                    journal=system.journal)["person:ada"]
    assert "no new records; the evidence set was revised" in str(current2.object)  # finding 3
    assert str(current2.object).startswith(lead2)

    # A card ALWAYS stands after any pass sequence (finding 4's contract).
    assert current_world_models(system.store, scope=SCOPE, owner_id=OWNER,
                                journal=system.journal).get("person:ada") is not None


def test_orientation_cap_and_participant_priority(system) -> None:
    """Findings 6/7 pinned: admissions cap at orientation_max_cards with
    participant mentions outranking cue mentions."""
    for i in range(4):
        system.remember_many([
            MemoryRecordInput(kind="episode", title=f"T{i} day {j}",
                              digest=f"Notes about theme{i}, day {j}.",
                              attributes={"topic": f"theme{i}"})
            for j in range(3)
        ], scope=SCOPE, owner_id=OWNER, idempotency_key=f"t{i}-days")
    _seed_ada(system)
    world_model_pass(system, scopes=SCOPES, owner_id=OWNER,
                     tuning=SleepTuning(world_model_evidence_floor=3,
                                        world_model_max_cards=6))
    from abstractmemory.world_model import mention_orientation_cards

    stim = Stimulus(
        cue_text="theme0 theme1 theme2 theme3 all mentioned at once",
        participants=("person:ada",))
    admissions = mention_orientation_cards(
        system.store, stim, [(SCOPE, OWNER)], max_cards=3)
    assert len(admissions) == 3                       # cap holds
    assert admissions[0]["target"] == "person:ada"    # participant first


def test_world_model_update_is_the_bounded_incremental_lane(system) -> None:
    """The frozen per-turn API: named targets only, bounded scan, same
    revision chain as the sleep pass; empty targets refuse loudly."""
    _seed_ada(system)
    system.remember_many([
        MemoryRecordInput(kind="episode", title=f"B{j}",
                          digest=f"With Bruno at the docks, day {j}.",
                          participants=("person:bruno", OWNER))
        for j in range(3)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="bruno-days")
    from abstractmemory import world_model_update

    out = world_model_update(system, scopes=SCOPES, owner_id=OWNER,
                             targets=["person:ada"], tuning=TUNING)
    formed = {v["target"] for v in out["formed"]}
    assert formed == {"person:ada"}          # bruno untouched: not this turn's target
    # The sleep pass later normalizes and forms bruno's card too.
    full = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    assert any(v["target"] == "person:bruno" for v in full["formed"])
    with pytest.raises(ValueError, match="targets"):
        world_model_update(system, scopes=SCOPES, owner_id=OWNER, targets=[])
