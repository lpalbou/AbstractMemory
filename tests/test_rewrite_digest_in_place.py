"""In-place understanding rewrites with versions (backlog 0059; operator ruling 2026-11-07, rule 2).

Pinned here, on both substrate pairs (in-memory, and SQLite store + journal sharing one file):
- a rewrite keeps the record's graph id, digest assertion id, edges, usage (selected_count) and every journal record
  byte-identical, and the default replay stream gains no row;
- the journal's versions family holds version 0 (the original) and version 1 with author, reader, sources, cause;
- the keyword index finds the new words and no longer the old; the vector is the new text's;
- refusals (stale CAS, protected kind, empty text, unreachable embedder, closed record, dream/card redirects) write
  nothing; identical text is an idempotent success;
- revert restores an earlier reading as a NEW version; narrate_dream is additive; the opt-in replay family
  "revision" shows the rewrite; display blocks and record_understanding carry the provenance.

MUTATION LIST (each was applied to the source, the named test went red, the source was restored byte-exact):
- M1 skip the version append (`written.append(journal._append_version_on(cur, v_new))` / `append_version(v_new)`)
  -> test_versions_hold_the_original_and_the_rewrite_with_provenance;
- M2 skip the FTS delete in `SQLiteTripleStore._rewrite_row_on` -> test_keyword_index_follows_the_new_words;
- M3 never re-embed (`write_vector` forced False in `_embed`) -> test_vector_is_the_new_texts;
- M4 ignore the compare-and-set (`if int(expected_version) != current` disabled) -> test_stale_version_is_refused;
- M5 skip the closure check in rewrite_digest -> test_refusals_write_nothing (closed);
- M6 drop `"revision"` from the merge in export_replay -> test_revision_family_is_opt_in;
- M7 (test_dream_pass_signals.py) / M8 author_world_model's in-place branch disabled ->
  test_card_authoring_in_place_keeps_the_card_and_its_versions;
- M9 version 0 never captured -> test_revert_restores_an_earlier_reading_as_a_new_version.
"""

from __future__ import annotations

import hashlib
import warnings
from typing import Any, Dict, List

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import (  # noqa: E402
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    TripleQuery,
    apply_redigestion,
    author_world_model,
    world_model_pass,
)
from abstractmemory.canonical_text import canonical_text  # noqa: E402
from abstractmemory.records import resolve_digest_assertion  # noqa: E402
from abstractmemory.sleep_policy import SleepTuning  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
MIND = {"kind": "entity-mind", "id": "entity:nerin"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "step", "run_id": "run-understand-1", "seq": 3}]


class Embedder:
    """Deterministic unit vectors from the text hash; `dead` makes every call fail (an unreachable endpoint)."""

    model = "fake-hash-16"

    def __init__(self, dim: int = 16) -> None:
        self.dim, self.dead = dim, False

    def embed_texts(self, texts):
        if self.dead:
            raise RuntimeError("connection refused")
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(self.dim)
            out.append((v / np.linalg.norm(v)).tolist())
        return out


@pytest.fixture(params=["memory", "sqlite"])
def home(request, tmp_path):
    emb = Embedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if request.param == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        else:
            path = tmp_path / "memory.sqlite3"
            store, journal = SQLiteTripleStore(path, embedder=emb), SQLiteJournal(path)
        system = MemorySystem(store=store, journal=journal, embedder=emb)
    system.kind, system.emb, system.path = request.param, emb, tmp_path / "memory.sqlite3"
    yield system
    journal.close()
    store.close()


def _form(system, key: str, kind: str = "episode", digest: str = "User: hi. Nerin: [used tool: read_file] ok",
          title: str = "exchange: hi", **kw: Any) -> str:
    attrs = dict(kw.pop("attributes", {}) or {})
    attrs.setdefault("digest_method", "mechanical-v2")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many(
            [MemoryRecordInput(kind=kind, title=title, digest=digest, attributes=attrs, **kw)],
            scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _rewrite(system, gid: str, text: str, version: int = 0, **kw: Any) -> Dict[str, Any]:
    kw.setdefault("author", MIND)
    kw.setdefault("reader", READER)
    kw.setdefault("sources", STEP)
    kw.setdefault("cause", "formation")
    return system.rewrite_digest(gid, text=text, expected_version=version, **kw)


def _journal_records(system) -> List[Any]:
    return [(f, r.to_dict()) for f, r in system.journal.replay_records()]


def _edges(system, gid: str) -> List[Dict[str, Any]]:
    return sorted((a.to_dict() for a in system.store.query(TripleQuery(subject=gid, limit=0))
                   if (a.attributes or {}).get("record_edge")), key=lambda d: d["assertion_id"])


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


# --------------------------------------------------------------------------- identity, usage, journal untouched


def test_rewrite_keeps_identity_edges_usage_and_journal(home) -> None:
    ep = _form(home, "turn-1")
    summary = _form(home, "close-1", kind="summary", digest="Session: one exchange.",
                    title="session reflection: s1", edges=(("summarizes", ep),),
                    attributes={"digest_method": "mechanical-floor-v1"})
    before = _row(home, summary)
    home.commit_selection("t-use-1", [summary])
    home.commit_selection("t-use-2", [summary, ep])
    usage = home.journal.selected_count(before.assertion_id)
    assert usage == 2
    edges0, journal0 = _edges(home, summary), _journal_records(home)
    stream0 = [(e["seq"], e["family"], e["payload"]) for e in home.export_replay()]

    out = _rewrite(home, summary, "I opened the file the user asked about and we agreed it was fine.")
    assert out["applied"] is True and out["version"] == 1 and out["previous_version"] == 0

    after = _row(home, summary)
    assert after.subject == before.subject == summary
    assert after.assertion_id == before.assertion_id
    assert after.observed_at == before.observed_at and after.provenance == before.provenance
    assert after.object.startswith("I opened the file")
    assert after.attributes["digest_version"] == 1
    assert after.attributes["digest_method"] == "authored-v1"
    assert after.attributes["understanding"]["author"]["kind"] == "entity-mind"
    assert _edges(home, summary) == edges0
    assert home.journal.selected_count(after.assertion_id) == usage
    assert _journal_records(home) == journal0                      # the six families: byte-identical
    assert [(e["seq"], e["family"], e["payload"]) for e in home.export_replay()] == stream0
    # The episode the summary points at is untouched.
    assert _row(home, ep).object.startswith("User: hi.")


def test_versions_hold_the_original_and_the_rewrite_with_provenance(home) -> None:
    gid = _form(home, "turn-v")
    original = _row(home, gid)
    _rewrite(home, gid, "We talked briefly; I read a file for them.", task_id="task-1",
             magnitude={"change": "refined"})
    rows = home.versions(gid)
    assert [r["version"] for r in rows] == [0, 1]
    v0, v1 = rows
    assert v0["text"] == original.object and v0["digest_method"] == "mechanical-v2"
    assert v0["author"] == {"kind": "mechanical", "id": "mechanical-v2"}
    assert v0["cause"]["cause"] == "formation" and v0["understood_at"] == original.observed_at
    assert v0["current"] is False and v1["current"] is True
    assert v1["author"] == MIND and v1["reader"] == READER
    assert v1["sources"] == [{"kind": "step", "run_id": "run-understand-1", "seq": 3}]
    assert v1["cause"] == {"cause": "formation"} and v1["task_id"] == "task-1"
    assert v1["magnitude"] == {"change": "refined"}
    assert v0["seq"] < v1["seq"] <= home.current_seq()
    assert v0["assertion_id"] == v1["assertion_id"] == original.assertion_id
    # A second rewrite appends exactly one row (version 0 is captured once).
    _rewrite(home, gid, "A short visit; I opened a file and confirmed it.", version=1, cause="ripple")
    assert [r["version"] for r in home.versions(gid)] == [0, 1, 2]


# --------------------------------------------------------------------------- indexes follow the words


def test_keyword_index_follows_the_new_words(home) -> None:
    if home.kind != "sqlite":
        pytest.skip("the FTS5 keyword index is the SQLite store's")
    gid = _form(home, "turn-k", digest="User: zebracorn question. Nerin: answered.")
    store = home.store
    assert [a.subject for a in store.query_keywords(["zebracorn"], scope=SCOPE, owner_id=OWNER)] == [gid]
    _rewrite(home, gid, "We discussed the quillfeather archive together.")
    assert store.query_keywords(["zebracorn"], scope=SCOPE, owner_id=OWNER) == []
    assert [a.subject for a in store.query_keywords(["quillfeather"], scope=SCOPE, owner_id=OWNER)] == [gid]
    # The index is consistent with its content table (FTS5 integrity check).
    store._conn.execute(f"INSERT INTO {store._table}_fts({store._table}_fts) VALUES('integrity-check')")
    # A reopened handle sees the same index (no re-sync drift).
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        again = SQLiteTripleStore(home.path)
    try:
        assert [a.subject for a in again.query_keywords(["quillfeather"], scope=SCOPE, owner_id=OWNER)] == [gid]
    finally:
        again.close()


def test_vector_is_the_new_texts(home) -> None:
    gid = _form(home, "turn-e")
    _form(home, "turn-other", digest="An unrelated exchange about gardens.", title="exchange: gardens")
    old_vector = home.store.stored_vector(_row(home, gid).assertion_id)
    _rewrite(home, gid, "We discussed the archive index and its map room.")
    row = _row(home, gid)
    expected = home.emb.embed_texts([canonical_text(row)])[0]
    stored = home.store.stored_vector(row.assertion_id)
    assert stored is not None and old_vector is not None
    assert np.allclose(stored, expected, atol=1e-6) and not np.allclose(stored, old_vector, atol=1e-3)
    [top] = home.store.query(TripleQuery(query_vector=expected, scope=SCOPE, owner_id=OWNER, limit=1))
    assert top.subject == gid and top.attributes["_retrieval"]["score"] > 0.999


# --------------------------------------------------------------------------- refusals


def _snapshot(system, gid: str):
    row = _row(system, gid)
    return (row.object, dict(row.attributes), system.current_seq(),
            system.store.stored_vector(row.assertion_id), system.journal.versions(record_id=row.subject))


def test_stale_version_is_refused(home) -> None:
    gid = _form(home, "turn-s")
    assert _rewrite(home, gid, "First authored reading.")["applied"] is True
    snap = _snapshot(home, gid)
    out = _rewrite(home, gid, "A concurrent reading written against version 0.", version=0)
    assert out["outcome"] == "refused" and out["reason"] == "stale" and out["version"] == 1
    assert _snapshot(home, gid) == snap


def test_refusals_write_nothing(home) -> None:
    gid = _form(home, "turn-r")
    interest = _form(home, "interest-1", kind="interest", digest="Tide pools", title="Tide pools")
    dream = _form(home, "dream-1", kind="dream", digest="Two islands lit up.", title="Dream: a beside b")
    snap = _snapshot(home, gid)
    assert _rewrite(home, gid, "   ")["reason"] == "empty_text"
    assert _rewrite(home, interest, "rewritten interest")["reason"] == "protected_kind"
    assert _rewrite(home, dream, "a narrated dream")["reason"] == "use_narrate_dream"
    assert _rewrite(home, "ex:episode-nope", "words")["reason"] == "unknown_record"
    assert _snapshot(home, gid) == snap
    # A closed (superseded) record: its replacement is the current one.
    out = apply_redigestion(home, [{"record_id": gid, "digest": "A replacement record's words."}],
                            actor="operator")
    new_gid = out["outcomes"][0]["new_record_id"]
    closed = _rewrite(home, gid, "words for a closed record")
    assert closed["reason"] == "closed" and closed["replaced_by"] == [new_gid]
    assert home.journal.versions(record_id=gid) == []
    assert home.current_of(gid)["current_id"] == new_gid


def test_embedder_unavailable_refuses_and_writes_nothing(home, tmp_path) -> None:
    gid = _form(home, "turn-u")
    snap = _snapshot(home, gid)
    home.emb.dead = True
    out = _rewrite(home, gid, "Words the dead embedder cannot index.")
    assert out["reason"] == "embedder_unavailable"
    assert _snapshot(home, gid) == snap
    if home.kind == "sqlite":
        # A vectored home opened WITHOUT its embedder refuses too (the vector would keep the old words).
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            bare = MemorySystem(store=SQLiteTripleStore(home.path), journal=SQLiteJournal(home.path))
        try:
            assert _rewrite(bare, gid, "Words without an embedder.")["reason"] == "embedder_unavailable"
        finally:
            bare.journal.close()
            bare.store.close()


def test_identical_text_is_an_idempotent_success(home) -> None:
    gid = _form(home, "turn-i")
    first = _rewrite(home, gid, "The authored reading.")
    replay = _rewrite(home, gid, "The authored reading.", version=0)   # a crash-retry of the same call
    assert first["applied"] is True
    assert replay["applied"] is False and replay["outcome"] == "unchanged" and replay["version"] == 1
    assert len(home.versions(gid)) == 2


def test_arguments_are_checked_loudly(home) -> None:
    gid = _form(home, "turn-a")
    with pytest.raises(ValueError, match="author.kind"):
        _rewrite(home, gid, "x", author={"kind": "llm"})
    with pytest.raises(ValueError, match="reader"):
        _rewrite(home, gid, "x", reader=None)
    with pytest.raises(ValueError, match="ledger step"):
        _rewrite(home, gid, "x", sources=())
    with pytest.raises(ValueError, match="cause"):
        _rewrite(home, gid, "x", cause="whim")
    # An operator writes without a model or a ledger step.
    out = _rewrite(home, gid, "Operator words.", author={"kind": "operator", "id": "laurent"}, reader=None,
                   sources=(), cause="operator")
    assert out["applied"] is True


def test_sqlite_needs_the_journal_in_the_same_file(tmp_path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        system = MemorySystem(store=SQLiteTripleStore(tmp_path / "a.sqlite3"),
                              journal=SQLiteJournal(tmp_path / "b.sqlite3"))
        [gid] = system.remember_many([MemoryRecordInput(kind="episode", title="t", digest="d")],
                                     scope=SCOPE, owner_id=OWNER, idempotency_key="k")
    with pytest.raises(ValueError, match="same|own file"):
        _rewrite(system, gid, "words")


def test_lancedb_refuses_loudly(tmp_path) -> None:
    pytest.importorskip("lancedb")
    from abstractmemory import LanceDBTripleStore

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        system = MemorySystem(store=LanceDBTripleStore(tmp_path / "lance"), journal=InMemoryJournal())
        [gid] = system.remember_many([MemoryRecordInput(kind="episode", title="t", digest="d")],
                                     scope=SCOPE, owner_id=OWNER, idempotency_key="k")
    with pytest.raises(NotImplementedError, match="0059"):
        _rewrite(system, gid, "words")


# --------------------------------------------------------------------------- revert, narration, cards


def test_revert_restores_an_earlier_reading_as_a_new_version(home) -> None:
    gid = _form(home, "turn-rv")
    original = _row(home, gid).object
    _rewrite(home, gid, "A reading the operator will undo.")
    out = home.revert_digest(gid, 0, expected_version=1, reason="leaked reasoning")
    assert out["applied"] is True and out["version"] == 2
    row = _row(home, gid)
    assert row.object == original and row.attributes["digest_method"] == "mechanical-v2"
    rows = home.versions(gid)
    assert [r["version"] for r in rows] == [0, 1, 2]
    assert rows[2]["cause"]["cause"] == "revert" and rows[2]["cause"]["reverted_to"] == 0
    assert rows[2]["author"]["kind"] == "mechanical"            # the words are the mechanical writer's
    assert rows[2]["cause"]["by"] == {"kind": "operator", "id": "operator"}
    assert home.revert_digest(gid, 7, expected_version=2)["reason"] == "unknown_version"
    if home.kind == "sqlite":
        assert home.store.query_keywords(["undo"], scope=SCOPE, owner_id=OWNER) == []


def test_narrate_dream_is_additive(home) -> None:
    dream = _form(home, "dream-n", kind="dream", digest="Two islands lit up tonight.", title="Dream: a beside b",
                  attributes={"signals": [{"kind": "unresolved_tension", "fragment": "a beside b"}]})
    row0 = _row(home, dream)
    vec0 = home.store.stored_vector(row0.assertion_id)
    out = home.narrate_dream(dream, text="I dreamt the two islands were one shore.", author=MIND,
                             reader=READER, sources=STEP)
    assert out["applied"] is True and out["field"] == "narration" and out["version"] == 1
    row = _row(home, dream)
    assert row.object == row0.object
    assert row.attributes["signals"] == row0.attributes["signals"]
    assert row.attributes["narration"].startswith("I dreamt")
    assert row.attributes.get("digest_version", 0) == 0
    assert home.store.stored_vector(row.assertion_id) == vec0
    assert [v["version"] for v in home.versions(dream, field="narration")] == [1]
    assert home.versions(dream) == []                        # the digest was never rewritten
    assert home.narrate_dream(_form(home, "ep-n"), text="x", author=MIND, reader=READER,
                              sources=STEP)["reason"] == "not_a_dream"
    again = home.narrate_dream(dream, text="I dreamt it differently.", author=MIND, reader=READER, sources=STEP)
    assert again["reason"] == "stale"
    understood = home.record_understanding(dream)
    assert understood["narration"].startswith("I dreamt") and understood["narration_by"] == MIND
    assert understood["narrated"] is True and understood["narration_version"] == 1


def test_card_authoring_in_place_keeps_the_card_and_its_versions(home) -> None:
    for i in range(3):
        _form(home, f"ada-{i}", digest=f"Worked with Ada on the archive, day {i}.", title=f"Ada day {i}",
              participants=("person:ada", OWNER))
    tuning = SleepTuning(world_model_evidence_floor=3)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out = world_model_pass(home, scopes=[(SCOPE, OWNER)], owner_id=OWNER, tuning=tuning)
    card_id = out["formed"][0]["card_id"]
    assert _rewrite(home, card_id, "words")["reason"] == "use_author_world_model"
    authored = author_world_model(home, target="person:ada", text="Ada is the archivist I trust.",
                                  scope=SCOPE, owner_id=OWNER, author=MIND, reader=READER, sources=STEP)
    assert authored["card_id"] == card_id and authored["applied"] is True and authored["version"] == 1
    understood = home.record_understanding(card_id)
    assert understood["digest"] == "Ada is the archivist I trust."
    assert understood["authored_by"] == MIND and understood["reader"] == READER
    assert understood["target"] == "person:ada" and understood["target_type"] == "person"
    assert understood["card_revision"] == 1 and understood["version_count"] == 2
    assert [v["field"] for v in home.versions(card_id)] == ["card", "card"]
    reverted = home.revert_digest(card_id, 0, expected_version=1)
    assert reverted["applied"] is True and _row(home, card_id).attributes["digest_method"] == "mechanical-card-v2"


# --------------------------------------------------------------------------- serving


def test_revision_family_is_opt_in(home) -> None:
    gid = _form(home, "turn-f")
    _rewrite(home, gid, "The reading the app can show as provenance.")
    default = list(home.export_replay())
    assert all(e["family"] != "revision" for e in default)
    revisions = list(home.export_replay(families=("revision",)))
    assert [e["payload"]["version"] for e in revisions] == [0, 1]
    last = revisions[-1]
    assert last["run_id"] == "run-understand-1" and last["scope"] == SCOPE and last["owner_id"] == OWNER
    assert last["display"]["digest"].startswith("The reading the app")
    assert last["display"]["digest_version"] == 1 and last["display"]["version_count"] == 2
    both = list(home.export_replay(families=("binding", "revision")))
    assert [e["seq"] for e in both] == sorted(e["seq"] for e in both)
    assert {e["family"] for e in both} == {"binding", "revision"}
    # Cursored continuation: nothing repeats past the last seen seq.
    assert list(home.export_replay(families=("revision",), since_seq=last["seq"])) == []


def test_display_block_and_record_read_carry_the_provenance(home) -> None:
    gid = _form(home, "turn-d")
    plain = [e for e in home.export_replay(families=("binding",)) if e["payload"]["record_id"] == gid][0]
    assert plain["display"]["authored_by"] == {"kind": "mechanical", "id": "mechanical-v2"}
    assert plain["display"]["digest_version"] == 0 and plain["display"]["version_count"] == 1
    assert plain["display"]["cause"] == "formation"
    _rewrite(home, gid, "Understood in the entity's own words.")
    block = [e for e in home.export_replay(families=("binding",)) if e["payload"]["record_id"] == gid][0]["display"]
    assert block["digest"] == "Understood in the entity's own words."
    assert block["digest_method"] == "authored-v1" and block["digest_version"] == 1
    assert block["version_count"] == 2 and block["authored_by"] == MIND and block["reader"] == READER
    assert block["understood_at"] and block["cause"] == "formation"
    understood = home.record_understanding(gid)
    assert understood["digest"] == block["digest"] and understood["current_id"] == gid
    assert understood["closed"] is None and "replaced_by" not in understood
    # A superseded record names its replacement.
    out = apply_redigestion(home, [{"record_id": _form(home, "turn-d2"), "digest": "Replacement words."}],
                            actor="operator")
    old = out["outcomes"][0]["record_id"]
    assert home.record_understanding(old)["replaced_by"] == [out["outcomes"][0]["new_record_id"]]
