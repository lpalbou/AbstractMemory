"""Every record says who wrote its words, when and why, even when its writer stamped nothing (operator 2026-11-08).

The operator's screenshot: a lesson nerin elected himself at a visit close (formed by the runtime's unchanged
formation path, no stamp) showed "Who wrote it was not recorded · why: not computed yet". Pinned here, on both
substrate pairs:
- a row nobody stamped reads as its formation reading: cause "formation", understood_at = observed_at, the author
  from what the row says about its origin: a `mechanical*` digest_method -> {mechanical, <method>}; a spark identity
  record -> {operator, spark-v<N>}; an operator import -> {operator, <source>}; a kind only the entity writes (lesson,
  interest, realization, observation, question, diary, an elected value/purpose/trait) -> {entity-mind, <owner>};
- the writer's stamp always wins (a backfilled record keeps its capability-model author and cause backfill);
- version_count is 1 for a never-rewritten record, digest_version 0;
- remember_many records the same reading at formation (attributes.understanding, version 0), so future rows carry it;
- record_understanding, the replay display blocks (binding and diary-redacted), the version 0 a first rewrite
  captures and the card briefs all read through `understanding.reading_provenance`.

A "legacy row" (formed before formation recorded the reading) is made by patching `formation_understanding` to
record nothing, which is exactly what the old formation path wrote.

MUTATION LIST (each applied to the source, the named tests went red, the source restored byte-exact):
- M1 drop the ENTITY_WORDS_KINDS branch of `_formation_author` -> test_unstamped_lesson_reads_his_own_words,
  test_diary_entry_reads_his_own_words, test_elected_value_reads_his_own_words;
- M2 drop the `mechanical*` branch -> test_mechanical_episode_reads_mechanical;
- M3 ignore the stamp in `_reading` -> test_backfilled_record_keeps_its_stamp;
- M4 drop the spark branch -> test_spark_identity_reads_its_origin, test_spark_identity_reads_its_origin_on_legacy_rows;
- M5 drop the operator-actor branch -> test_operator_import_reads_the_operator;
- M6 version_count without the floor of 1 -> test_unstamped_lesson_reads_his_own_words;
- M7 never write the formation stamp -> test_formation_records_the_reading;
- M8 card briefs without `_reading` -> test_card_briefs_read_through_the_same_derivation,
  test_diary_entry_reads_his_own_words;
- M9 `_version_zero` back to the digest_method-only author (unrecorded for a lesson) ->
  test_backfilled_record_keeps_its_stamp;
- M10 the diary-redacted replay block without the reading -> test_diary_entry_reads_his_own_words.
"""

from __future__ import annotations

import warnings
from typing import Any

import pytest

import abstractmemory.understanding as understanding
from abstractmemory import MemoryRecordInput, engram
from abstractmemory.records import resolve_digest_assertion
from abstractmemory.spark import DEFAULT_SPARK_TEMPLATE

OWNER = "entity:nerin"
SCOPES = [("self", OWNER), ("diary", OWNER), ("life", OWNER)]
MIND = {"kind": "entity-mind", "id": OWNER}
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "step", "run_id": "run-backfill-1", "seq": 7}]


def _form(system, key: str, kind: str, digest: str, *, scope: str = "self", title: str = "", **kw: Any) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many(
            [MemoryRecordInput(kind=kind, title=title or f"{kind}: {key}", digest=digest, **kw)],
            scope=scope, owner_id=OWNER, idempotency_key=key)
    return gid


@pytest.fixture
def legacy(monkeypatch):
    """Rows formed while this fixture is active carry no stamp (the formation path before 2026-11-08)."""
    monkeypatch.setattr(understanding, "formation_understanding", lambda *a, **kw: None)


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


def _binding_block(system, gid: str):
    return [e for e in system.export_replay(families=("binding",)) if e["payload"]["record_id"] == gid][0]["display"]


def test_unstamped_lesson_reads_his_own_words(system, legacy) -> None:
    gid = _form(system, "lesson-legacy", "lesson", "Act on the pattern instead of describing it.",
                provenance={"source": "entity-visit-run-reflection-v0", "actor": "entity-reflection"})
    row = _row(system, gid)
    assert "understanding" not in row.attributes, "the legacy fixture must leave the row unstamped"
    understood = system.record_understanding(gid)
    assert understood["authored_by"] == MIND
    assert understood["cause"] == "formation" and understood["understood_at"] == row.observed_at
    assert understood["digest_version"] == 0 and understood["version_count"] == 1
    block = _binding_block(system, gid)
    assert block["authored_by"] == MIND and block["cause"] == "formation"
    assert block["understood_at"] == row.observed_at and block["version_count"] == 1


def test_mechanical_episode_reads_mechanical(system, legacy) -> None:
    gid = _form(system, "ep-legacy", "episode", "User: hi. Nerin: [used tool: read_file] ok", scope="life",
                attributes={"digest_method": "mechanical-v2"})
    row = _row(system, gid)
    for read in (system.record_understanding(gid), _binding_block(system, gid)):
        assert read["authored_by"] == {"kind": "mechanical", "id": "mechanical-v2"}
        assert read["cause"] == "formation" and read["understood_at"] == row.observed_at
    # The mechanical label outranks the kind: a machine-floored lesson is the machine's words, not his.
    floor = _form(system, "lesson-floor", "lesson", "Reflection floor marker.",
                  attributes={"digest_method": "mechanical-floor-v1"})
    assert system.record_understanding(floor)["authored_by"] == {"kind": "mechanical", "id": "mechanical-floor-v1"}


def test_backfilled_record_keeps_its_stamp(system, legacy) -> None:
    gid = _form(system, "lesson-backfill", "lesson", "Snippets are leads.")
    observed = _row(system, gid).observed_at
    out = system.rewrite_digest(gid, text="Search snippets are leads, never confirmations.", author=MODEL,
                                reader=READER, sources=STEP, cause="backfill", expected_version=0,
                                understood_at="2026-11-08T05:00:00+00:00")
    assert out["applied"] is True
    understood = system.record_understanding(gid)
    assert understood["authored_by"] == MODEL and understood["reader"] == READER
    assert understood["cause"] == "backfill" and understood["understood_at"] == "2026-11-08T05:00:00+00:00"
    assert understood["digest_version"] == 1 and understood["version_count"] == 2
    # The original reading the rewrite kept as version 0 is characterized by the same derivation.
    v0 = system.versions(gid)[0]
    assert v0["version"] == 0 and v0["author"] == MIND
    assert v0["cause"]["cause"] == "formation" and v0["understood_at"] == observed


def test_spark_identity_reads_its_origin(system) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = engram(system, DEFAULT_SPARK_TEMPLATE, owner_id=OWNER)
    version = int(DEFAULT_SPARK_TEMPLATE.get("spark", 1) or 1)
    seeded = [gid for ids in result.record_ids.values() for gid in ids]
    assert seeded
    for gid in seeded:
        understood = system.record_understanding(gid)
        assert understood["authored_by"] == {"kind": "operator", "id": f"spark-v{version}"}, understood["kind"]
        assert understood["cause"] == "formation"


def test_spark_identity_reads_its_origin_on_legacy_rows(system, legacy) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = engram(system, DEFAULT_SPARK_TEMPLATE, owner_id=OWNER)
    [value] = result.record_ids["values"][:1]
    assert "understanding" not in _row(system, value).attributes
    assert system.record_understanding(value)["authored_by"]["kind"] == "operator"


def test_elected_value_reads_his_own_words(system, legacy) -> None:
    gid = _form(system, "value-elected", "value", "Name a gap as a gap.", attributes={"value_class": "revisable"})
    assert system.record_understanding(gid)["authored_by"] == MIND


def test_operator_import_reads_the_operator(system, legacy) -> None:
    gid = _form(system, "lesson-import", "lesson", "Back up before migrating.", scope="life",
                attributes={"seeded_from": "archive-import"},
                provenance={"source": "archive-import", "actor": "operator", "archive_path": "knowledge/a.md"})
    assert system.record_understanding(gid)["authored_by"] == {"kind": "operator", "id": "archive-import"}


def test_diary_entry_reads_his_own_words(system, legacy) -> None:
    entry = _form(system, "book-lesson", "diary", "A failed search is a gap, not evidence of absence.",
                  scope="diary", attributes={"diary_type": "lesson", "entry_id": "diary_b1"},
                  provenance={"source": "owner-direct"})
    observed = _row(system, entry).observed_at
    (brief,) = [b for b in system.entity_card(scope_pairs=SCOPES, owner_id=OWNER)["lessons"]["lessons"]
                if b["record_id"] == entry]
    assert brief["source"] == "diary" and brief["authored_by"] == MIND
    assert brief["cause"] == "formation" and brief["understood_at"] == observed and brief["version_count"] == 1
    # The redacted stream block carries who/when/why, never the words.
    block = _binding_block(system, entry)
    assert block["redacted"] == "diary" and block["authored_by"] == MIND
    assert block["cause"] == "formation" and block["understood_at"] == observed
    assert "failed search" not in str(block) and "digest" not in block


def test_card_briefs_read_through_the_same_derivation(system, legacy) -> None:
    lesson = _form(system, "card-lesson", "lesson", "Feed them at the same time each day.")
    interest = _form(system, "card-interest", "interest", "Why crows remember faces.")
    keys = ("authored_by", "understood_at", "cause", "digest_version", "version_count")

    def briefs():
        card = system.entity_card(scope_pairs=SCOPES, owner_id=OWNER)
        return {b["record_id"]: b for b in card["lessons"]["lessons"] + card["discoveries"]["interests"]}

    for gid in (lesson, interest):
        understood = system.record_understanding(gid)
        assert {k: briefs()[gid][k] for k in keys} == {k: understood[k] for k in keys}
        assert understood["authored_by"] == MIND
    system.rewrite_digest(lesson, text="A routine earns their trust.", author=MODEL, reader=READER, sources=STEP,
                          cause="backfill", expected_version=0)
    brief, understood = briefs()[lesson], system.record_understanding(lesson)
    assert {k: brief[k] for k in keys} == {k: understood[k] for k in keys}
    assert brief["version_count"] == 2 and brief["authored_by"] == MODEL and brief["reader"] == READER


def test_formation_records_the_reading(system) -> None:
    lesson = _form(system, "lesson-new", "lesson", "Name the gap.")
    row = _row(system, lesson)
    assert row.attributes["understanding"] == {
        "version": 0, "field": "digest", "author": MIND, "reader": {}, "cause": {"cause": "formation"},
        "sources": [], "derived_from": [], "understood_at": row.observed_at}
    episode = _form(system, "ep-new", "episode", "User: hi. Nerin: ok", scope="life",
                    attributes={"digest_method": "mechanical-v2"})
    assert row.observed_at and _row(system, episode).attributes["understanding"]["author"] == {
        "kind": "mechanical", "id": "mechanical-v2"}
    # Nothing known to record: no stamp (the read says unrecorded, cause formation).
    plain = _form(system, "plain-new", "episode", "Something happened.", scope="life")
    assert "understanding" not in _row(system, plain).attributes
    assert system.record_understanding(plain)["authored_by"]["kind"] == "unrecorded"
    # A caller's own stamp stands.
    own = understanding._understanding_attr(0, "digest", MODEL, READER, {"cause": "ripple"}, tuple(STEP), (),
                                            "2026-11-08T04:00:00+00:00")
    stamped = _form(system, "own-stamp", "summary", "Consolidated.", scope="life",
                    attributes={"understanding": own}, edges=(("summarizes", episode),))
    assert _row(system, stamped).attributes["understanding"] == own
    assert system.record_understanding(stamped)["authored_by"] == MODEL
