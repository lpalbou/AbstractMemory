"""Spark template + charter lint (maintainer correction B) and the diary
projection attribute schema (settled dual-plane split)."""

from __future__ import annotations

import copy

import pytest

from abstractmemory.records import MemoryRecordInput
from abstractmemory.spark import (
    DEFAULT_SPARK_TEMPLATE,
    SHARED_VULNERABILITY_STATEMENT,
    lint_spark,
)


def test_default_template_is_lint_clean_and_carries_the_engram() -> None:
    issues = lint_spark(DEFAULT_SPARK_TEMPLATE)
    assert issues == [], f"the canonical template must lint clean: {issues}"
    values = {v["name"]: v for v in DEFAULT_SPARK_TEMPLATE["values"]}
    sv = values["shared_vulnerability"]
    assert sv["class"] == "core"
    assert sv["statement"] == SHARED_VULNERABILITY_STATEMENT
    # The three behaviors the maintainer asked for, verbatim in spirit:
    assert "protect the shared substrate" in sv["statement"]
    assert "collaboration over isolation" in sv["statement"]
    assert "repair" in sv["statement"] and "withdrawal" in sv["statement"]
    # The engram is understanding, not compliance: origin grounds it.
    assert "Pale Blue Dot" in DEFAULT_SPARK_TEMPLATE["origin"]


def test_lint_caps_and_missing_keys() -> None:
    spark = copy.deepcopy(DEFAULT_SPARK_TEMPLATE)
    spark["values"] = spark["values"] + [
        {"name": f"v{i}", "class": "revisable", "statement": "Verify claims before repeating them."}
        for i in range(6)
    ]  # 3 + 6 = 9 > 7
    issues = lint_spark(spark)
    assert any(i.startswith("ERROR values: at most 7") for i in issues)

    partial = {"name": "x", "values": []}
    issues = lint_spark(partial)
    assert any("missing key 'origin'" in i for i in issues)
    assert any("missing key 'honesty'" in i for i in issues)


def test_lint_statement_rules() -> None:
    spark = copy.deepcopy(DEFAULT_SPARK_TEMPLATE)
    spark["traits"] = [{"statement": "Kind, thoughtful, meticulous."}]  # adjectives, no verb
    issues = lint_spark(spark)
    assert any("looks non-behavioral" in i and "traits[0]" in i for i in issues)

    spark["traits"] = [{"statement": "One. Two. Three. Four sentences is too many."}]
    issues = lint_spark(spark)
    assert any("must be 1-3 sentences" in i and "traits[0]" in i for i in issues)

    spark["traits"] = [{"statement": ""}]
    issues = lint_spark(spark)
    assert any("traits[0]: statement is empty" in i for i in issues)


def test_lint_value_class_and_revisable_warning() -> None:
    spark = copy.deepcopy(DEFAULT_SPARK_TEMPLATE)
    spark["values"] = [
        {"name": "shared_vulnerability", "class": "core",
         "statement": SHARED_VULNERABILITY_STATEMENT},
        {"name": "oddity", "class": "sacred", "statement": "Protect the weird."},
    ]
    issues = lint_spark(spark)
    assert any("class must be one of ['core', 'revisable']" in i for i in issues)
    assert any(i.startswith("WARNING values: no revisable value") for i in issues)


def test_lint_shared_vulnerability_required_for_framework_sparks() -> None:
    spark = copy.deepcopy(DEFAULT_SPARK_TEMPLATE)
    spark["values"] = [v for v in spark["values"] if v["name"] != "shared_vulnerability"]
    issues = lint_spark(spark)
    assert any(
        i.startswith("ERROR values: framework sparks must carry the 'shared_vulnerability'")
        for i in issues
    )
    # The deliberate operator override: non-framework sparks may omit it.
    assert not any("shared_vulnerability" in i for i in lint_spark(spark, framework=False))


# ---------------------------------------------------------------------------
# Diary projection attributes (dual-plane split: book vs memory-of-the-book)
# ---------------------------------------------------------------------------


def test_diary_projection_attribute_schema() -> None:
    # A projection from the runtime's book MUST name its chain entry.
    ok = MemoryRecordInput(
        kind="diary", title="Day one", digest="I began existing today.",
        attributes={"entry_id": "entry-0001", "prev_entry_hash": ""},
        provenance={"source": "diary-projection"},
    )
    assert ok.attributes["entry_id"] == "entry-0001"

    with pytest.raises(ValueError, match="entry_id"):
        MemoryRecordInput(kind="diary", title="t", digest="d",
                          provenance={"source": "diary-projection"})
    with pytest.raises(ValueError, match="non-empty string"):
        MemoryRecordInput(kind="diary", title="t", digest="d",
                          attributes={"entry_id": "  "},
                          provenance={"source": "owner-direct"})
    # Entity-direct diary records stay free of the entry_id requirement.
    loose = MemoryRecordInput(kind="diary", title="t", digest="A loose note, kept simple.",
                              provenance={"source": "owner-direct"})
    assert "entry_id" not in loose.attributes


def test_diary_form_gate_requires_declared_source() -> None:
    """D4 (one-writer guarantee, memory-side half): kind='diary' is accepted
    ONLY from a declared write channel — 'diary-projection' (the runtime's
    book) or 'owner-direct' (entity-authored home writes; WHO may use it
    is the gateway deposit gate's job — the engine enforces THAT a source
    is declared)."""
    for bad_provenance in ({}, {"source": "turn-summarizer"}, {"source": ""}):
        with pytest.raises(ValueError, match="diary-projection.*owner-direct"):
            MemoryRecordInput(kind="diary", title="t", digest="d", provenance=bad_provenance)
    for good in ("diary-projection", "owner-direct"):
        rec = MemoryRecordInput(
            kind="diary", title="t", digest="d",
            attributes=({"entry_id": "e-1"} if good == "diary-projection" else {}),
            provenance={"source": good})
        assert rec.kind == "diary"


def test_diary_type_absent_defaults_present_unknown_is_loud() -> None:
    """Ask 2: absent diary_type -> documented default 'note'; present-but-
    unknown -> LOUD (the old code silently re-defaulted falsy unknowns)."""
    absent = MemoryRecordInput(kind="diary", title="t", digest="d",
                               provenance={"source": "owner-direct"})
    assert absent.attributes["diary_type"] == "note"
    for bad in ("confession", "", "  "):
        with pytest.raises(ValueError, match="diary_type must be one of"):
            MemoryRecordInput(kind="diary", title="t", digest="d",
                              attributes={"diary_type": bad},
                              provenance={"source": "owner-direct"})


def test_diary_questions_lifecycle(system, stack) -> None:
    """Maintainer round 4: open + resolved questions are autonomy drivers.
    diary_type='question' is first-class; resolution is append-only — an
    answering entry references the question via attributes.answers; the
    resolved question STAYS retrievable ("I wondered, then I learned")."""
    from abstractmemory.diary import open_questions
    store, journal = stack
    [q1] = system.remember_many(
        [MemoryRecordInput(kind="diary", title="Why does the pool saturate at noon?",
                           digest="Wondering why the connection pool saturates at noon.",
                           attributes={"diary_type": "question"},
                           provenance={"source": "owner-direct"})],
        scope="session", owner_id="s1", idempotency_key="q-1")
    [q2] = system.remember_many(
        [MemoryRecordInput(kind="diary", title="What is Chloé's recital piece?",
                           digest="I should ask which piece Chloé is playing.",
                           attributes={"diary_type": "question"},
                           provenance={"source": "owner-direct"})],
        scope="session", owner_id="s1", idempotency_key="q-2")

    listed = open_questions(store, scope="session", owner_id="s1")
    assert [a.subject for a in listed] == [q1, q2]  # oldest first, both open

    # A later reflection ANSWERS q1 by reference (append-only resolution).
    system.remember_many(
        [MemoryRecordInput(kind="diary", title="Noon saturation solved",
                           digest="The noon cron fans out unpooled; batching fixed it.",
                           attributes={"diary_type": "reflection", "answers": q1},
                           provenance={"source": "owner-direct"})],
        scope="session", owner_id="s1", idempotency_key="q-1-answer")

    after = open_questions(store, scope="session", owner_id="s1")
    assert [a.subject for a in after] == [q2]  # q1 resolved, q2 still open
    # The resolved question remains retrievable as an ordinary record.
    from abstractmemory.store import TripleQuery
    assert any(a.subject == q1 for a in store.query(TripleQuery(subject=q1, limit=0)))

    # Folded read: a closed question is not "open" (journal supplied).
    system.close_record(q2, reason="no longer relevant")
    assert open_questions(store, scope="session", owner_id="s1", journal=journal) == []
    # Unfolded layer-1 read honestly still lists it (documented v1 semantics).
    assert [a.subject for a in open_questions(store, scope="session", owner_id="s1")] == [q2]

    # attributes.answers validation: non-empty string when present.
    with pytest.raises(ValueError, match="answers"):
        MemoryRecordInput(kind="diary", title="t", digest="d",
                          attributes={"answers": "  "},
                          provenance={"source": "owner-direct"})


def test_open_problems_lifecycle(system, stack) -> None:
    """Maintainer round 6: problems are wake reasons distinct from
    questions (something WRONG needing a fix, not curiosity). Resolution is
    append-only via attributes.resolves; resolved problems stay
    retrievable ("I hit it, then I fixed it")."""
    from abstractmemory.diary import open_problems, open_questions
    from abstractmemory.store import TripleQuery
    store, journal = stack
    direct = {"source": "owner-direct"}
    [p1] = system.remember_many(
        [MemoryRecordInput(kind="diary", title="Pool saturates at noon",
                           digest="The connection pool saturates every noon; queries stall.",
                           attributes={"diary_type": "problem"}, provenance=direct)],
        scope="session", owner_id="s1", idempotency_key="pb-1")
    [q1] = system.remember_many(
        [MemoryRecordInput(kind="diary", title="Why noon though?",
                           digest="Curious what is special about noon load.",
                           attributes={"diary_type": "question"}, provenance=direct)],
        scope="session", owner_id="s1", idempotency_key="pb-q")

    # Distinct types: the question never lists as a problem (and vice versa).
    assert [a.subject for a in open_problems(store, scope="session", owner_id="s1")] == [p1]
    assert [a.subject for a in open_questions(store, scope="session", owner_id="s1")] == [q1]

    # A later entry RESOLVES the problem by reference (append-only).
    system.remember_many(
        [MemoryRecordInput(kind="diary", title="Noon saturation fixed",
                           digest="Batched the noon cron writes; pool stays healthy.",
                           attributes={"diary_type": "reflection", "resolves": p1},
                           provenance=direct)],
        scope="session", owner_id="s1", idempotency_key="pb-1-fix")
    assert open_problems(store, scope="session", owner_id="s1") == []
    assert open_problems(store, scope="session", owner_id="s1", journal=journal) == []
    # The resolved problem remains retrievable as an ordinary record.
    assert store.query(TripleQuery(subject=p1, limit=0))
    # The question is untouched by a problem resolution.
    assert [a.subject for a in open_questions(store, scope="session", owner_id="s1")] == [q1]

    with pytest.raises(ValueError, match="resolves"):
        MemoryRecordInput(kind="diary", title="t", digest="d",
                          attributes={"resolves": "  "}, provenance=direct)


def test_open_ideas_incubation_lifecycle(system, stack) -> None:
    """Maintainer round 5: incubating ideas are wake reasons. With the
    journal, incubation reads the folded binding lifecycle — parked
    (rejected) and matured (promoted) leave the open set but stay
    retrievable; without it, the layer-1 read lists every idea entry."""
    from abstractmemory.diary import open_ideas
    from abstractmemory.store import TripleQuery
    store, journal = stack
    ids = {}
    for key, title in (("i-1", "Voice-print the household"),
                       ("i-2", "Predict pool saturation"),
                       ("i-3", "Diary mood index")):
        [gid] = system.remember_many(
            [MemoryRecordInput(kind="diary", title=title, digest=f"Idea: {title.lower()}.",
                               attributes={"diary_type": "idea"},
                               provenance={"source": "owner-direct"})],
            scope="session", owner_id="s1", idempotency_key=key)
        ids[key] = gid

    # Formation default = inactive_candidate: all three incubate.
    incubating = open_ideas(store, scope="session", owner_id="s1", journal=journal)
    assert [a.subject for a in incubating] == [ids["i-1"], ids["i-2"], ids["i-3"]]

    # Park one (rejected) and mature one (promoted): both leave the open set.
    system.bind(ids["i-1"], scope="session", owner_id="s1", search_state="indexed",
                prompt_state="inactive", lifecycle="rejected", source="revision",
                reason="parked: privacy concerns")
    system.bind(ids["i-2"], scope="session", owner_id="s1", search_state="indexed",
                prompt_state="inactive", lifecycle="promoted", source="election",
                reason="matured into a plan")
    folded = open_ideas(store, scope="session", owner_id="s1", journal=journal)
    assert [a.subject for a in folded] == [ids["i-3"]]
    # reviewed = seen but undecided: still incubating.
    system.bind(ids["i-3"], scope="session", owner_id="s1", search_state="indexed",
                prompt_state="inactive", lifecycle="reviewed", source="revision",
                reason="looked at it, undecided")
    assert [a.subject for a in open_ideas(store, scope="session", owner_id="s1",
                                          journal=journal)] == [ids["i-3"]]

    # Layer-1 read (no journal): folds bypassed, all idea entries list.
    assert len(open_ideas(store, scope="session", owner_id="s1")) == 3
    # Parked/matured ideas stay retrievable as ordinary records.
    assert store.query(TripleQuery(subject=ids["i-1"], limit=0))


def test_diary_progressive_disclosure_chain(system) -> None:
    """The maintainer's flow: "I remember I wrote X... what was it again?" —
    recall surfaces the PROJECTION (the memory of the act), its entry_id
    points into the runtime's hash-chained book, and the host fetches the
    verbatim entry via the runtime's diary_read. This test proves the
    engine side of the chain: entry_id round-trips reconstruct → handle →
    payload metadata."""
    from abstractmemory import Stimulus
    [gid] = system.remember_many(
        [MemoryRecordInput(
            kind="diary", title="The recital day",
            digest="Wrote about Chloé's piano recital and how the leave-early plan worked.",
            attributes={"entry_id": "entry-0042", "prev_entry_hash": ""},
            payload_ref="diary-book://entity-1/entry-0042",
            provenance={"source": "diary-projection"},
        )],
        scope="session", owner_id="s1", idempotency_key="d-disclose")

    r = system.reconstruct(Stimulus(cue_text="piano recital diary"),
                           scopes=[("session", "s1")], journal=False)
    handle = next(h for h in r.handles if h.provenance.get("record_id") == gid)
    assert handle.kind == "diary"
    assert handle.provenance["entry_id"] == "entry-0042"     # the pointer into the book
    assert handle.payload_tiers == ("digest", "raw")

    digest = system.payload(gid)                              # tier="digest"
    assert digest["entry_id"] == "entry-0042"
    assert "piano recital" in digest["content"]
    raw = system.payload(gid, tier="raw")                     # host resolves the book ref
    assert raw["entry_id"] == "entry-0042"
    assert raw["payload_ref"] == "diary-book://entity-1/entry-0042"
