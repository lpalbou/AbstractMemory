"""Entity identity card guards (a2a 0009 — "something to know our summoned
entity").

The card is ABOUT the entity, from its data, never claiming to BE it: every
section derives from a named source (per-field provenance) and composing it
is a PURE READ — being described must not strengthen anyone (the D2
discipline extended to description). Both stacks via conftest fixtures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from abstractmemory import Stimulus, engram, entity_card
from abstractmemory.diary import open_questions
from abstractmemory.consolidation import unresolved_dreams
from abstractmemory.records import MemoryRecordInput
from abstractmemory.spark import DEFAULT_SPARK_TEMPLATE

EID = "entity:card-test"
SCOPES = [("self", EID), ("diary", EID), ("life", EID)]

CARD_SECTIONS = ("identity", "age_and_context", "current_state",
                 "likes_dislikes", "questions", "key_moments", "discoveries")


def _remember(system, key: str, kind: str, title: str, digest: str,
              scope: str = "life", **kw: Any) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)],
        scope=scope, owner_id=EID, idempotency_key=key)
    return gid


def _seeded_home(system) -> Dict[str, str]:
    """A small but complete life: engram + episodes (one committed selection
    so global counts are non-zero) + valence incl. free-string, record, and
    ambivalent targets + a scar-marked peak + diary questions (one resolved)
    + a dream + an interest."""
    ids: Dict[str, str] = {}
    engram(system, DEFAULT_SPARK_TEMPLATE, owner_id=EID)

    ids["ep1"] = _remember(system, "e-1", "episode", "Pool outage night",
                           "The connection pool saturated at noon.",
                           keywords=("pool", "noon"))
    ids["ep2"] = _remember(system, "e-2", "episode", "Harbor watch",
                           "Watched the harbor tide at dawn.",
                           keywords=("harbor", "dawn"))
    system.commit_selection("t-card-seed", [ids["ep1"], ids["ep2"]])  # real usage

    # Valence: free-string target, ambivalent tool, a record target (title
    # resolution), and one high-magnitude scar-marked peak (a key moment).
    system.appraise("person:laurent", sign=1, magnitude=3,
                    reason="trusted me to search for myself",
                    scope="self", owner_id=EID, actor="entity-reflection")
    system.appraise("tool:web_search", sign=1, magnitude=2, reason="found the source",
                    scope="life", owner_id=EID)
    system.appraise("tool:web_search", sign=-1, magnitude=1, reason="one dead link",
                    scope="life", owner_id=EID)
    system.appraise(ids["ep1"], sign=1, magnitude=2, reason="proud of the diagnosis",
                    scope="life", owner_id=EID)
    system.appraise("tool:rm_rf", sign=-1, magnitude=9, reason="wiped a workspace",
                    scope="life", owner_id=EID, actor="operator", scar=True)

    # Diary: one open question, one question resolved by a later note.
    ids["q-open"] = _remember(system, "d-1", "diary", "Why do names persist?",
                              "What persists when no one is reading?", scope="diary",
                              attributes={"diary_type": "question"},
                              provenance={"source": "owner-direct"})
    ids["q-done"] = _remember(system, "d-2", "diary", "Which model runs me?",
                              "Which substrate is powering me tonight?", scope="diary",
                              attributes={"diary_type": "question"},
                              provenance={"source": "owner-direct"})
    ids["answer"] = _remember(system, "d-3", "diary", "Learned my substrate",
                              "The episode stamps carry mind_substrate now.", scope="diary",
                              attributes={"answers": ids["q-done"]},
                              provenance={"source": "owner-direct"})

    ids["dream"] = _remember(system, "dr-1", "dream", "Dream: pool beside harbor",
                             "Two islands lit up together tonight.",
                             attributes={"continuation_state": "unresolved",
                                         "interpretation_required": True})
    ids["interest"] = _remember(system, "i-1", "interest", "What persists",
                                "What persists when no one is reading.", scope="self")
    return ids


# ---------------------------------------------------------------------------
# The full card over a seeded home (shape + semantics, both stacks)
# ---------------------------------------------------------------------------


def test_full_card_over_seeded_home(system) -> None:
    ids = _seeded_home(system)
    card = system.entity_card(scope_pairs=SCOPES, owner_id=EID)

    assert card["owner_id"] == EID
    assert card["as_of_seq"] == system.current_seq()
    for section in CARD_SECTIONS:
        assert isinstance(card[section], dict)
        provenance = card[section]["provenance"]
        assert isinstance(provenance, str) and provenance.strip()  # source named per field

    # identity: the folded self core, spark version, engine-truth name.
    identity = card["identity"]
    assert identity["name"] == EID
    assert identity["spark_version"] == 1
    value_titles = {v["title"] for v in identity["values"]}
    assert "shared_vulnerability" in value_titles
    assert any(v.get("value_class") == "core" for v in identity["values"])
    assert identity["purposes"] and identity["traits"]
    assert any(t.get("trait_class") == "limit" for t in identity["traits"])  # honesty section

    # age_and_context: counts by kind per scope; timestamps, never now().
    ctx = card["age_and_context"]
    assert ctx["journal_seq"] == card["as_of_seq"]
    assert ctx["record_counts"]["life"]["episode"] == 2
    assert ctx["record_counts"]["life"]["dream"] == 1
    assert ctx["record_counts"]["diary"]["diary"] == 3
    assert ctx["record_counts"]["self"]["value"] == 3
    assert ctx["diary_entries"] == 3
    assert ctx["first_observed_at"] and ctx["last_observed_at"]
    assert ctx["first_observed_at"] <= ctx["last_observed_at"]

    # current_state: window over APPRAISALS only (the scar marker is
    # standing, not an experience); top reasons led by the biggest swing.
    state = card["current_state"]
    assert state["event_count"] == 5
    assert (state["positive"], state["negative"], state["net"]) == (7.0, 10.0, -3.0)
    assert state["top_reasons"][0] == "-9 wiped a workspace"
    assert len(state["top_reasons"]) <= 5
    assert "window, not a point" in state["provenance"]

    # likes_dislikes: channels separate; ambivalent target in BOTH lists;
    # record-backed target carries its resolved title; scar flag visible.
    likes = {e["target"]: e for e in card["likes_dislikes"]["likes"]}
    dislikes = {e["target"]: e for e in card["likes_dislikes"]["dislikes"]}
    assert "person:laurent" in likes and likes["person:laurent"]["positive"] == 3.0
    assert "tool:web_search" in likes and "tool:web_search" in dislikes  # ambivalence
    assert likes[ids["ep1"]]["title"] == "Pool outage night"  # record target resolved
    assert "title" not in likes["person:laurent"]             # free string passes through
    assert dislikes["tool:rm_rf"]["scarred"] is True
    assert dislikes["tool:rm_rf"]["negative"] == 9.0
    assert card["likes_dislikes"]["targets_total"] == 4

    # questions: open vs resolved split via the answers/resolves convention.
    open_ids = {q["record_id"] for q in card["questions"]["open"]}
    resolved = {q["record_id"]: q for q in card["questions"]["resolved"]}
    assert open_ids == {ids["q-open"]}
    assert set(resolved) == {ids["q-done"]}
    assert resolved[ids["q-done"]]["resolved_by"] == [ids["answer"]]
    # Parity with the shipped diary fold helper (same convention, same folds).
    helper_open = {a.subject for a in open_questions(
        system._store, scope="diary", owner_id=EID, journal=system._journal)}
    assert open_ids == helper_open

    # key_moments: chronological; the scar pair (appraisal + marker) at
    # magnitude 9 + first dream + first interest; never ranked.
    moments = card["key_moments"]["moments"]
    assert card["key_moments"]["total"] == 4
    stamps = [str(m["observed_at"]) for m in moments]
    assert stamps == sorted(stamps)
    valence_moments = [m for m in moments if m["type"] == "valence"]
    assert {m["kind"] for m in valence_moments} == {"appraisal", "scar"}
    assert all(m["magnitude"] == 9.0 for m in valence_moments)
    firsts = {m["what"]: m for m in moments if m["type"] == "first"}
    assert firsts["first_dream"]["record_id"] == ids["dream"]
    assert firsts["first_interest"]["record_id"] == ids["interest"]

    # discoveries: open interests + unresolved dream count (helper parity).
    disc = card["discoveries"]
    assert [i["record_id"] for i in disc["interests"]] == [ids["interest"]]
    assert disc["unresolved_dreams"] == 1
    assert disc["unresolved_dreams"] == len(unresolved_dreams(
        system._store, scope="life", owner_id=EID, journal=system._journal))


def test_first_supersession_is_a_key_moment(system) -> None:
    ids = _seeded_home(system)
    replacement = _remember(system, "e-3", "episode", "Pool outage, revised",
                            "The saturation was the batch cron, not the pool.")
    system.close_record(ids["ep1"], kind="supersede", reason="better diagnosis",
                        replacement_ids=[replacement])
    card = system.entity_card(scope_pairs=SCOPES, owner_id=EID)
    firsts = {m["what"] for m in card["key_moments"]["moments"] if m["type"] == "first"}
    assert "first_supersession" in firsts
    # History never shrinks: the superseded episode still counts.
    assert card["age_and_context"]["record_counts"]["life"]["episode"] == 3


# ---------------------------------------------------------------------------
# PURITY: being described deposits nothing (the D2 of description)
# ---------------------------------------------------------------------------


def test_guard_card_is_a_pure_read(system, stack) -> None:
    _, journal = stack
    ids = _seeded_home(system)
    seq_before = journal.current_seq()
    counts_before = system.access_counts(record_ids=[ids["ep1"], ids["ep2"]])
    events_before = {
        (scope, owner): len(journal.events(scope=scope, owner_id=owner, limit=0))
        for scope, owner in SCOPES
    }
    valence_before = {
        (scope, owner): len(journal.valence_events(scope=scope, owner_id=owner, limit=0))
        for scope, owner in SCOPES
    }

    system.entity_card(scope_pairs=SCOPES, owner_id=EID)
    system.entity_card(scope_pairs=SCOPES, owner_id=EID, as_of=seq_before, top_n=2)

    assert journal.current_seq() == seq_before  # NOTHING appended, any family
    assert system.access_counts(record_ids=[ids["ep1"], ids["ep2"]]) == counts_before
    for scope, owner in SCOPES:
        assert len(journal.events(scope=scope, owner_id=owner, limit=0)) == events_before[(scope, owner)]
        assert len(journal.valence_events(scope=scope, owner_id=owner, limit=0)) == valence_before[(scope, owner)]


# ---------------------------------------------------------------------------
# as_of anchoring: the card at seq T describes the entity AT T
# ---------------------------------------------------------------------------


def test_as_of_anchors_records_and_valence(system) -> None:
    engram(system, DEFAULT_SPARK_TEMPLATE, owner_id=EID)
    _remember(system, "p1-e", "episode", "First day", "The first episode.")
    system.appraise("tool:alpha", sign=1, magnitude=2, reason="phase one",
                    scope="life", owner_id=EID)
    anchor = system.current_seq()

    # Phase 2: later records + a high-magnitude feeling must NOT leak back.
    _remember(system, "p2-d", "dream", "Dream: later", "A later dream.",
              attributes={"continuation_state": "unresolved"})
    _remember(system, "p2-i", "interest", "Later interest", "Grew later.", scope="self")
    _remember(system, "p2-q", "diary", "Later question", "Asked later.", scope="diary",
              attributes={"diary_type": "question"},
              provenance={"source": "owner-direct"})
    system.appraise("tool:beta", sign=-1, magnitude=9, reason="phase two loss",
                    scope="life", owner_id=EID, actor="operator")

    then = system.entity_card(scope_pairs=SCOPES, owner_id=EID, as_of=anchor)
    assert then["as_of_seq"] == anchor
    assert then["age_and_context"]["records_total"] == 7   # 6 engrammed + 1 episode
    assert then["current_state"]["event_count"] == 1
    assert then["current_state"]["net"] == 2.0
    assert [e["target"] for e in then["likes_dislikes"]["likes"]] == ["tool:alpha"]
    assert then["likes_dislikes"]["dislikes"] == []
    assert then["key_moments"]["moments"] == []            # the -9 came later
    assert then["questions"]["open"] == []
    assert then["discoveries"]["interests"] == []
    assert then["discoveries"]["unresolved_dreams"] == 0

    now = system.entity_card(scope_pairs=SCOPES, owner_id=EID)
    assert now["age_and_context"]["records_total"] == 10
    assert now["current_state"]["event_count"] == 2
    assert {e["target"] for e in now["likes_dislikes"]["dislikes"]} == {"tool:beta"}
    assert {m["what"] for m in now["key_moments"]["moments"] if m["type"] == "first"} \
        == {"first_dream", "first_interest"}
    assert len(now["questions"]["open"]) == 1

    # At seq 0 nothing existed — identity included (the engram came later).
    birthless = system.entity_card(scope_pairs=SCOPES, owner_id=EID, as_of=0)
    assert birthless["identity"]["values"] == []
    assert birthless["identity"]["spark_version"] is None
    assert birthless["age_and_context"]["records_total"] == 0

    with pytest.raises(ValueError, match="not a valid anchor"):
        system.entity_card(scope_pairs=SCOPES, owner_id=EID,
                           as_of=system.current_seq() + 10)


def test_question_resolved_after_anchor_reads_open_at_anchor(system) -> None:
    """Belief-at-T: a question answered AFTER the anchor was still open AT
    the anchor — the resolution must not leak backward."""
    q = _remember(system, "aq-1", "diary", "Standing question", "Still wondering.",
                  scope="diary", attributes={"diary_type": "question"},
                  provenance={"source": "owner-direct"})
    anchor = system.current_seq()
    _remember(system, "aq-2", "diary", "Answered", "Learned it.", scope="diary",
              attributes={"answers": q}, provenance={"source": "owner-direct"})

    then = system.entity_card(scope_pairs=SCOPES, owner_id=EID, as_of=anchor)
    assert [x["record_id"] for x in then["questions"]["open"]] == [q]
    assert then["questions"]["resolved"] == []
    now = system.entity_card(scope_pairs=SCOPES, owner_id=EID)
    assert now["questions"]["open"] == []
    assert [x["record_id"] for x in now["questions"]["resolved"]] == [q]


# ---------------------------------------------------------------------------
# The empty home: honest emptiness, never fabricated
# ---------------------------------------------------------------------------


def test_empty_home_card_is_honest(system) -> None:
    card = system.entity_card(scope_pairs=SCOPES, owner_id=EID)
    assert card["as_of_seq"] == 0
    identity = card["identity"]
    assert identity["name"] == EID and identity["spark_version"] is None
    assert identity["values"] == identity["purposes"] == identity["traits"] == []
    assert "no prompt-active identity records" in identity["provenance"]
    ctx = card["age_and_context"]
    assert ctx["records_total"] == 0 and ctx["record_counts"] == {}
    assert ctx["first_observed_at"] is None and ctx["last_observed_at"] is None
    assert "no formed records" in ctx["provenance"]
    state = card["current_state"]
    assert state["event_count"] == 0 and state["net"] == 0.0
    assert "no appraisal events" in state["provenance"]
    assert card["likes_dislikes"]["likes"] == [] and card["likes_dislikes"]["dislikes"] == []
    assert "no valence events" in card["likes_dislikes"]["provenance"]
    assert card["questions"]["open"] == [] and card["questions"]["resolved"] == []
    assert card["key_moments"]["moments"] == [] and card["key_moments"]["total"] == 0
    assert card["discoveries"]["interests"] == []
    assert card["discoveries"]["unresolved_dreams"] == 0


def test_card_input_validation(system) -> None:
    with pytest.raises(ValueError, match="scope"):
        system.entity_card(scope_pairs=[], owner_id=EID)
    with pytest.raises(ValueError, match="owner_id"):
        system.entity_card(scope_pairs=SCOPES, owner_id="  ")
    with pytest.raises(ValueError, match="current_window_events"):
        system.entity_card(scope_pairs=SCOPES, owner_id=EID, current_window_events=0)
    with pytest.raises(ValueError, match="top_n"):
        system.entity_card(scope_pairs=SCOPES, owner_id=EID, top_n=-1)


def test_current_window_is_a_window_not_a_point(system) -> None:
    """The declared tunable bites: a window of 2 sees only the newest two
    appraisals; older experience stays in gradation (standing) but leaves
    'current' — current is a window, not a lifetime."""
    for i, (sign, magnitude) in enumerate([(1, 3), (1, 3), (-1, 2), (-1, 1)]):
        system.appraise("tool:x", sign=sign, magnitude=magnitude,
                        reason=f"event {i}", scope="life", owner_id=EID)
    card = system.entity_card(scope_pairs=SCOPES, owner_id=EID,
                              current_window_events=2)
    state = card["current_state"]
    assert state["event_count"] == 2
    assert (state["positive"], state["negative"], state["net"]) == (0.0, 3.0, -3.0)
    # Standing (likes_dislikes) still folds the WHOLE life: ambivalent.
    [like] = card["likes_dislikes"]["likes"]
    assert like["target"] == "tool:x" and like["positive"] == 6.0
