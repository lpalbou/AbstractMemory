"""Stored text is never cut (root ADR 0054, operator ruling 2026-11-08): a 2,000-character input reaches storage whole.

One test per lifted bound; each reads what was STORED, not what a function returned:
- a world-model card's evidence gists (the card digest, `world_model._evidence_gist`; was 150 chars);
- a dream signal's fragment (the dream record's `attributes.signals` and digest; was 200 chars);
- an assertion's `original_context` in the canonical text (the SQLite `text` column, keyword index and vector input;
  was 400 chars).

MUTATION LIST (each cap restored in the source turned its test red; the source was restored byte-exact):
- W1 `_evidence_gist` cut at 150 again -> test_card_gists_are_stored_whole;
- W2 `signal()` cuts the fragment at 200 again -> test_dream_signal_fragments_are_stored_whole;
- W3 `canonical_text` cuts the context at 400 again -> test_canonical_context_is_stored_whole.
"""

from __future__ import annotations

import sqlite3
import warnings

from abstractmemory import (
    MemoryRecordInput,
    SQLiteTripleStore,
    TripleAssertion,
    TripleQuery,
    dream_pass,
    world_model_pass,
)
from abstractmemory.records import resolve_digest_assertion
from abstractmemory.sleep_policy import SleepTuning

SCOPE, OWNER = "life", "entity:test"
SCOPES = [(SCOPE, OWNER)]
LONG = " ".join(f"word{i:05d}" for i in range(200)) + "x"   # exactly 2,000 characters, no marker brackets


def test_card_gists_are_stored_whole(system) -> None:
    assert len(LONG) == 2000
    system.remember_many([
        MemoryRecordInput(kind="episode", title=f"Ada day {i}", participants=("person:ada", OWNER),
                          digest=(LONG if i == 2 else f"Worked with Ada, day {i}."))
        for i in range(3)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="ada")
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=SleepTuning(world_model_evidence_floor=3))
    card = resolve_digest_assertion(system.store, out["formed"][0]["card_id"])
    assert LONG in str(card.object)


def test_dream_signal_fragments_are_stored_whole(system) -> None:
    long_title = "Pool outage " + LONG[: 2000 - len("Pool outage ")]
    assert len(long_title) == 2000
    ids = []
    for key, kind, title, digest, keywords in (
            ("s-1", "episode", long_title, "The connection pool saturated at noon.", ("pool", "saturation", "noon")),
            ("s-3", "episode", "Garden sensor day", "Planted the garden moisture sensors at noon.",
             ("garden", "sensors", "noon"))):
        [gid] = system.remember_many([MemoryRecordInput(kind=kind, title=title, digest=digest, keywords=keywords)],
                                     scope=SCOPE, owner_id=OWNER, idempotency_key=key)
        ids.append(gid)
    system.remember_many([MemoryRecordInput(kind="lesson", title="Batch the writers",
                                            digest="Batching the noon cron fixed the pool.",
                                            keywords=("pool", "batching"), edges=(("supports", ids[0]),))],
                         scope=SCOPE, owner_id=OWNER, idempotency_key="s-2")
    night = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert night["dream_record_id"], night["skipped_reason"]
    stored = resolve_digest_assertion(system.store, night["dream_record_id"]).attributes
    fragments = [s["fragment"] for s in stored["signals"]]
    assert any(long_title in f for f in fragments)
    assert all("fragment_truncation" not in s for s in stored["signals"])


def test_canonical_context_is_stored_whole(tmp_path) -> None:
    path = tmp_path / "home.sqlite3"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        store = SQLiteTripleStore(path)
    store.add([TripleAssertion(subject="carol", predicate="noted", object="detail", scope=SCOPE,
                               attributes={"original_context": LONG}, assertion_id="ctx-1")])
    store.close()
    with sqlite3.connect(str(path)) as conn:
        [(text,)] = conn.execute("SELECT text FROM triples WHERE assertion_id = 'ctx-1'").fetchall()
    assert text.endswith("context: " + LONG)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        again = SQLiteTripleStore(path)
    try:
        # The keyword index holds the context's last word, past any former cut.
        assert [a.assertion_id for a in again.query_keywords([LONG.split()[-1]], scope=SCOPE)] == ["ctx-1"]
        assert again.query(TripleQuery(assertion_ids=("ctx-1",)))[0].attributes["original_context"] == LONG
    finally:
        again.close()
