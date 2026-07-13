"""situate() — the temporal graph made usable (backlog 0034).

Contracts pinned:
- anchors: seq, ISO time, and RELATIONAL ("when I first/last met X") —
  exactly one, loud on ambiguity/absence/unknown participants;
- the composed read returns the moment's working set, warm activity,
  period records, elected diary act-frames, identity AS OF the anchor,
  the identity EVOLUTION since, and tensions open at that time;
- everything record-shaped is labeled admission="historical";
- PURE READ: no journal growth, no usage deposits (the anti
  trapped-in-the-past rule);
- boundary validation mirrors reconstruct's as_of rule.
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
    SituateBudget,
    Stimulus,
)

OWNER = "entity:traveler"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _seed_life(system):
    """A small life in three chapters: early work, a meeting, later work.
    Returns (early_ids, meeting_id, late_ids, anchor_seq_after_meeting)."""
    early = system.remember_many([
        MemoryRecordInput(kind="episode", title="Harbor survey",
                          digest="Surveyed the harbor wall cracks.",
                          keywords=("harbor",)),
        MemoryRecordInput(kind="question", title="Wall question",
                          digest="Why does the north wall crack faster?",
                          keywords=("wall",)),
        MemoryRecordInput(kind="value", title="Care",
                          digest="Care for what is entrusted to me.",
                          attributes={"value_class": "core"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="early")
    # The identity core is PROMPT-ACTIVE in a real home (the engram does
    # this); formation alone leaves bindings inactive.
    system.bind(early[2], scope=SCOPE, owner_id=OWNER,
                search_state="indexed", prompt_state="active")
    [meeting] = system.remember_many([
        MemoryRecordInput(kind="episode", title="Met Ada",
                          digest="First conversation with Ada about the harbor.",
                          keywords=("harbor",), participants=("person:ada", OWNER)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="meeting")
    anchor = system.journal.current_seq()
    # Recall + commit at the anchor moment: the working set of "then".
    r = system.reconstruct(Stimulus(cue_text="harbor wall"), scopes=SCOPES)
    system.commit_selection(r.trace_id, [h.record_id for h in r.handles])
    late = system.remember_many([
        MemoryRecordInput(kind="episode", title="New instruments",
                          digest="Installed the new strain instruments.",
                          keywords=("instruments",)),
        MemoryRecordInput(kind="interest", title="Materials science",
                          digest="A growing pull toward materials science."),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="late")
    return early, meeting, late, anchor


def test_exactly_one_anchor_required(system) -> None:
    _seed_life(system)
    with pytest.raises(ValueError, match="exactly ONE anchor"):
        system.situate(scopes=SCOPES)
    with pytest.raises(ValueError, match="exactly ONE anchor"):
        system.situate(scopes=SCOPES, seq=1, participant="person:ada")
    with pytest.raises(ValueError, match="outside this journal"):
        system.situate(scopes=SCOPES, seq=10_000)


def test_relational_anchor_when_i_met_x(system) -> None:
    early, meeting, late, _ = _seed_life(system)
    out = system.situate(scopes=SCOPES, participant="person:ada", occurrence="first")
    assert out["anchor_kind"] == "participant"
    assert out["encounter_record_id"] == meeting
    period_gids = {h["graph_id"] for h in out["period"]}
    assert meeting in period_gids, "the encounter itself is part of the period"
    with pytest.raises(ValueError, match="no record .* stamped"):
        system.situate(scopes=SCOPES, participant="person:nobody")


def test_composed_read_moment_activity_and_labels(system) -> None:
    early, meeting, late, anchor = _seed_life(system)
    # Anchor AFTER the commit so the moment's trace is visible.
    out = system.situate(scopes=SCOPES, seq=system.journal.seq_at("9999-12-31T00:00:00Z"))
    assert out["pass_name"] == "situate"
    # every record-shaped entry is historical
    for section in ("period", "elected", "then_identity",
                    "identity_evolution", "tensions_then"):
        assert all(h["admission"] == "historical" for h in out[section]), section
    assert all(a["admission"] == "historical" for a in out["activity"])
    # the moment carries the committed working set
    assert out["moment"]["trace_id"] is not None
    assert out["moment"]["held_record_ids"], "the moment lost its working set"


def test_then_identity_and_evolution(system) -> None:
    early, meeting, late, anchor = _seed_life(system)
    out = system.situate(scopes=SCOPES, seq=anchor)
    # Then-identity: the core value existed at the anchor.
    then_titles = {h["title"] for h in out["then_identity"]}
    assert "Care" in then_titles
    # Evolution: the interest formed AFTER the anchor shows as added_since.
    evolution = {h["title"]: h["change"] for h in out["identity_evolution"]}
    assert evolution.get("Materials science") == "added_since"


def test_tensions_open_at_the_anchor(system) -> None:
    early, meeting, late, anchor = _seed_life(system)
    out = system.situate(scopes=SCOPES, seq=anchor)
    tension_titles = {h["title"] for h in out["tensions_then"]}
    assert "Wall question" in tension_titles
    # Close the question NOW; situating at the same past anchor still
    # shows it OPEN (closures fold as-of the anchor, not as-of today).
    question_gid = early[1]
    system.close_record(question_gid, reason="answered later")
    again = system.situate(scopes=SCOPES, seq=anchor)
    assert "Wall question" in {h["title"] for h in again["tensions_then"]}, (
        "a later closure leaked into the past moment")


def test_situate_is_a_pure_read(system) -> None:
    early, meeting, late, anchor = _seed_life(system)
    all_ids = list(early) + [meeting] + list(late)
    seq_before = system.journal.current_seq()
    counts_before = system.access_counts(record_ids=all_ids)
    system.situate(scopes=SCOPES, seq=anchor)
    system.situate(scopes=SCOPES, participant="person:ada")
    assert system.journal.current_seq() == seq_before, "situate wrote to the journal"
    assert system.access_counts(record_ids=all_ids) == counts_before, (
        "situate deposited usage")


def test_budget_bounds_the_window(system) -> None:
    _seed_life(system)
    tight = SituateBudget(window_records=2, activity_top_k=1, tensions=1)
    out = system.situate(scopes=SCOPES, participant="person:ada", budget=tight)
    assert len(out["period"]) <= 2
    assert len(out["activity"]) <= 1
    assert len(out["tensions_then"]) <= 1
    assert out["budget"]["window_records"] == 2


def test_zero_bounds_mean_nothing_and_negatives_refuse(system) -> None:
    """Adversary P1.4: bounds of 0 serve NOTHING (never 'unlimited'
    through slice arithmetic); negatives refuse loudly."""
    _seed_life(system)
    zeroed = SituateBudget(window_records=0, activity_top_k=0,
                           tensions=0, identity_delta=0, diary_entries=0)
    out = system.situate(scopes=SCOPES, participant="person:ada", budget=zeroed)
    assert out["period"] == []
    assert out["activity"] == []
    assert out["tensions_then"] == []
    assert out["identity_evolution"] == []
    assert out["elected"] == []
    with pytest.raises(ValueError, match="must be >= 0"):
        SituateBudget(window_records=-1)


def test_resolved_questions_are_not_tensions_of_that_moment(system) -> None:
    """Adversary P1.2 (the lane's most important fix): the diary lane
    settles questions by REFERENCE, deliberately without closures — a
    question answered BEFORE the anchor was not an open tension then."""
    [q] = system.remember_many([
        MemoryRecordInput(kind="diary", title="Why does the wall crack?",
                          digest="Standing question about the north wall.",
                          attributes={"diary_type": "question"},
                          provenance={"source": "owner-direct"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="q")
    system.remember_many([
        MemoryRecordInput(kind="diary", title="The wall answer",
                          digest="Frost heave — answered at the site visit.",
                          attributes={"diary_type": "note", "answers": q},
                          provenance={"source": "owner-direct"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="a")
    anchor = system.journal.current_seq()
    out = system.situate(scopes=SCOPES, seq=anchor)
    titles = {h["title"] for h in out["tensions_then"]}
    assert "Why does the wall crack?" not in titles, (
        "an already-answered question presented as an open tension")

    # And the graph twin: an authored answers EDGE settles it too.
    [q2] = system.remember_many([
        MemoryRecordInput(kind="question", title="Second question",
                          digest="What loosens the east gate hinge?"),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="q2")
    system.remember_many([
        MemoryRecordInput(kind="answer", title="Hinge answer",
                          digest="Salt air corrosion.",
                          edges=(("answers", q2),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="a2")
    out2 = system.situate(scopes=SCOPES, seq=system.journal.current_seq())
    assert "Second question" not in {h["title"] for h in out2["tensions_then"]}


def test_at_anchor_and_occurrence_last(system) -> None:
    """The at= branch and occurrence='last' were unpinned (adversary)."""
    _seed_life(system)
    out = system.situate(scopes=SCOPES, at="9999-01-01T00:00:00Z")
    assert out["anchor_kind"] == "time"
    assert out["anchor_seq"] == system.journal.seq_at("9999-01-01T00:00:00Z")
    last = system.situate(scopes=SCOPES, participant="person:ada",
                          occurrence="last")
    assert last["occurrence"] == "last"
    with pytest.raises(ValueError, match="occurrence"):
        system.situate(scopes=SCOPES, participant="person:ada",
                       occurrence="middle")
    with pytest.raises(ValueError, match="had not started"):
        system.situate(scopes=SCOPES, at="1970-01-01T00:00:00Z")


def test_purity_and_anchors_hold_on_sqlite(tmp_path) -> None:
    """Purity was pinned on InMemory only (adversary): the SQLite journal
    and store are separate implementations — pin the same contract."""
    from abstractmemory import SQLiteJournal, SQLiteTripleStore

    system = MemorySystem(
        store=SQLiteTripleStore(tmp_path / "store.sqlite3"),
        journal=SQLiteJournal(tmp_path / "journal.sqlite3"))
    ids = system.remember_many([
        MemoryRecordInput(kind="episode", title="Met Ada",
                          digest="First talk with Ada.",
                          participants=("person:ada",)),
        MemoryRecordInput(kind="question", title="Open one",
                          digest="Why does the tide sing?"),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="sqlite-life")
    seq_before = system.journal.current_seq()
    counts_before = system.access_counts(record_ids=ids)
    out = system.situate(scopes=SCOPES, participant="person:ada")
    assert out["encounter_record_id"] == ids[0]
    # The question formed AFTER the first encounter — a tension of NOW,
    # not of then (post-dating honesty); anchor at now to see it.
    now = system.situate(scopes=SCOPES, seq=seq_before)
    assert any(h["title"] == "Open one" for h in now["tensions_then"])
    assert system.journal.current_seq() == seq_before, "situate wrote (sqlite)"
    assert system.access_counts(record_ids=ids) == counts_before
