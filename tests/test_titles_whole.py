"""Titles are explicit, complete and stored whole (root ADR 0054; operator 2026-11-08, nerin's Interests panel:
"the title of any lesson, question, interest, world model must be explicit and easy to read / understand, both for a
human and for an agent. otherwise this screws up the discoverability").

Each test reads what was STORED:
- a world-model card formed from an interest keeps the interest's whole subject head as its target
  (`world_model._interest_subject_head` capped it at 8 words: nerin's card read "World model: first-person accounts
  as the bridge between aggregate crisis"); its title is pending its authored words (operator rulings 2026-11-09:
  the pass never writes a card's title);
- a lesson candidate's label carries the resolved question's words whole, both when the question's own title names
  it and when its title is boilerplate and the question's words label it (`candidate_miner` stored a 90-character
  head inside a 120-character title cut); the offer forms pending its authored title, its body quoting the words
  whole.

MUTATION LIST (each cut restored in the source turned its test red; the source was restored byte-exact):
- T1 `words = words[:8]` back in `_interest_subject_head` -> test_interest_card_keeps_the_whole_subject;
- T2 `bounded_label(f"Lesson candidate: {label}", 120)` back -> test_lesson_candidate_title_is_whole and
  test_lesson_candidate_label_from_the_question_words_is_whole;
- T3 the 90-character `bounded_label` head back -> test_lesson_candidate_label_from_the_question_words_is_whole.
"""

from __future__ import annotations

import pytest

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SleepTuning,
    mine_candidates_pass,
    world_model_pass,
)
from abstractmemory.records import resolve_digest_assertion
from abstractmemory.store import TripleQuery

pytestmark = pytest.mark.filterwarnings("ignore:.*InMemoryJournal is volatile.*")

SCOPE, OWNER = "life", "entity:test"
SCOPES = [(SCOPE, OWNER)]

SUBJECT = "First-person accounts as the bridge between aggregate crisis data and lived human experience"
PROBLEM = ("the connection pool keeps saturating under noon load whenever the nightly export overlaps the "
           "reporting writers and the retry storm from the mobile clients doubles the open sockets again")


def _system() -> MemorySystem:
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal(), task_queue=True)


def _stored_title(system: MemorySystem, gid: str) -> str:
    for row in system._store.query(TripleQuery(subject=gid, limit=0)):
        attrs = row.attributes if isinstance(row.attributes, dict) else {}
        if attrs.get("record_kind"):
            return str(attrs.get("title") or "")
    raise AssertionError(f"no record row for {gid}")


def test_interest_card_keeps_the_whole_subject() -> None:
    system = _system()
    system.remember_many([MemoryRecordInput(
        kind="interest",
        title=f"interest: {SUBJECT} — the dimension where displacement numbers become specific people",
        digest=f"{SUBJECT} — the dimension where displacement numbers become specific people.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="int-whole")
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER,
                           tuning=SleepTuning(world_model_evidence_floor=3))
    head = SUBJECT.lower()
    assert len(head.split()) == 13  # past the old 8-word cap
    formed = {v["target"]: v for v in out["formed"]}
    assert f"topic:{head}" in formed, sorted(formed)
    card = resolve_digest_assertion(system.store, formed[f"topic:{head}"]["card_id"])
    assert card.attributes["target"] == f"topic:{head}"
    assert card.attributes["title"] is None and card.attributes["pending"]["title"] is True


def _resolved_tension(system: MemorySystem, *, title: str, text: str) -> None:
    """A problem hit in one session, worked in two more, resolved by a later entry (the lesson-candidate
    precondition, as in test_candidate_miner)."""
    def diary(key: str, diary_type: str, t: str, words: str, session: str, **attrs: object) -> str:
        [gid] = system.remember_many(
            [MemoryRecordInput(kind="diary", title=t, digest=words,
                               attributes={"diary_type": diary_type, **attrs},
                               provenance={"source": "owner-direct", "session_id": session})],
            scope=SCOPE, owner_id=OWNER, idempotency_key=key)
        return gid

    def episode(key: str, t: str, session: str) -> None:
        system.remember_many(
            [MemoryRecordInput(kind="episode", title=t, digest=t, keywords=("connection", "pool"),
                               provenance={"session_id": session})],
            scope=SCOPE, owner_id=OWNER, idempotency_key=key)

    problem = diary("q", "problem", title, text, "s-alpha")
    episode("e1", "Debugged the connection pool saturating", "s-beta")
    episode("e2", "Connection pool fix verified", "s-gamma")
    diary("a", "note", "batching writers fixed the pool",
          "batching the noon writers fixed the connection pool for good", "s-gamma", resolves=problem)


def _lesson_candidate_title(system: MemorySystem) -> str:
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    lessons = [c for c in result["created"] if c["proposed_kind"] == "lesson"]
    assert lessons, "a resolved cross-session tension must offer a lesson"
    # The offer is stored pending its authored title; the report label and the provisional body keep the words whole.
    assert _stored_title(system, lessons[0]["candidate_id"]) == ""
    row = resolve_digest_assertion(system.store, lessons[0]["candidate_id"])
    assert row.attributes["pending"]["title"] is True
    label = lessons[0]["title"]
    assert label.split(": ", 1)[1] in str(row.object)
    return label


def test_lesson_candidate_title_is_whole() -> None:
    system = _system()
    assert len(PROBLEM) > 160
    _resolved_tension(system, title=PROBLEM, text=PROBLEM)
    assert _lesson_candidate_title(system) == f"Lesson candidate: {PROBLEM}"


def test_lesson_candidate_label_from_the_question_words_is_whole() -> None:
    # A title of no discriminative terms (digits only) is boilerplate: the question's words label the offer.
    system = _system()
    _resolved_tension(system, title="2026-07-17", text=PROBLEM)
    assert _lesson_candidate_title(system) == f"Lesson candidate: {PROBLEM}"
