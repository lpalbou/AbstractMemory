"""A record's title is changed alone, in place, every earlier title kept as a version (`retitle`).

Operator rule (2026-11-08, root ADR 0054): a title is an explicit, complete, readable phrase; stored text is never
cut. The runtime cut 170 interest, 38 lesson, 222 diary, 35 card and 51 episode titles at formation, and the
protected kinds (interest, diary, realization...) refuse `rewrite_digest`, so a repair could not re-title them.
`retitle` changes the title only: the body stays byte-equal, version 0 keeps the cut title.

Pinned here, on both substrate pairs (in-memory, and SQLite store + journal sharing one file):
- every kind with a title (episode, summary, world-model card, dream, interest, lesson, realization, observation,
  question/problem/commitment/idea diary entries) is retitled; body, keywords and the digest's reading untouched;
- `versions(field="title")` = [0: the cut title, 1: the new one with its provenance]; the display block's title is
  the new one; the keyword index and the vector follow the new title; `short_title` derives from it;
- refusals (empty/whitespace, stale, unknown, closed, hash-chained diary, dead embedder) write nothing; an unchanged
  title is `unchanged` with no version;
- a digest reading that changes the title writes its title version too; `revert_digest(field="title")` restores;
  reverting the words keeps a title retitled since;
- a diary entry's revision envelopes are sealed like its display block.

MUTATION LIST (each applied to a scratch COPY of src/, this file run against it with PYTHONPATH, red confirmed):
- R1 drop the title version write (`written.append(...v_new)` skipped for field "title" in `_apply`) ->
  test_every_kind_is_retitled_alone and test_versions_and_revert_of_the_title;
- R2 version 0 never captured for a title (`_title_version_zero` not appended) -> test_every_kind_is_retitled_alone;
- R3 reserved() keeps the old title (`"title": words` dropped) -> test_every_kind_is_retitled_alone;
- R4 the diary revision seal skipped -> test_diary_title_versions_are_sealed_in_the_revision_stream;
- R5 the companion title rows of a digest reading dropped -> test_a_digest_reading_that_changes_the_title_versions_it;
- R6 a revert always restores the reading's title (`keep_title` forced False) ->
  test_reverting_the_words_keeps_a_title_retitled_since;
- R7 title version 0 always from `reading_provenance` (the walk over digest versions skipped) ->
  test_title_version_zero_names_the_reading_that_wrote_the_title.
"""

from __future__ import annotations

import hashlib
import warnings
from typing import Any, Dict

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import (  # noqa: E402
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    Stimulus,
    apply_redigestion,
    retitle,
    world_model_pass,
)
from abstractmemory.canonical_text import canonical_text, short_title  # noqa: E402
from abstractmemory.records import resolve_digest_assertion  # noqa: E402
from abstractmemory.sleep_policy import SleepTuning  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
MODEL = {"kind": "capability-model", "id": "understanding"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "step", "run_id": "run-retitle-1", "seq": 7}]
OPERATOR = {"kind": "operator", "id": "laurent"}
TITLE_KEYS = {"title", "title_version", "title_provenance"}


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
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=True)
    system.kind, system.emb = request.param, emb
    yield system
    journal.close()
    store.close()


def _form(system, key: str, kind: str, title: str, digest: str, **kw: Any) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many([MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)],
                                     scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


def _retitle(system, gid: str, title: str, version: int = 0, **kw: Any) -> Dict[str, Any]:
    kw.setdefault("author", MODEL)
    kw.setdefault("reader", READER)
    kw.setdefault("sources", STEP)
    kw.setdefault("cause", "backfill")
    return system.retitle(gid, title=title, expected_version=version, **kw)


def _diary(system, key: str, diary_type: str) -> str:
    body = (f"Why do the displacement numbers hide the people behind them, and what would it take for me to see "
            f"them as specific lives ({diary_type})?")
    return _form(system, key, "diary", f"Diary entry ({diary_type}) — 2026-11-07: Why do the displacement numbers…",
                 body, attributes={"diary_type": diary_type, "entry_id": f"book-{key}"},
                 provenance={"source": "diary-projection"})


def _card(system) -> str:
    for i in range(3):
        _form(system, f"ada-{i}", "episode", f"Ada day {i}", f"Worked with Ada on the archive, day {i}.",
              participants=("person:ada", OWNER))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out = world_model_pass(system, scopes=[(SCOPE, OWNER)], owner_id=OWNER,
                               tuning=SleepTuning(world_model_evidence_floor=3))
    return out["formed"][0]["card_id"]


CUT = "First-person accounts as the bridge between aggregate crisis"
BODY = ("First-person accounts as the bridge between aggregate crisis data and lived human experience: the dimension "
        "where displacement numbers become specific people.")


def _make(system, kind: str) -> str:
    """One record of `kind` carrying a cut title (the runtime's formation cut)."""
    if kind == "summary":
        ep = _form(system, "ep-s", "episode", "exchange: hi", "User: hi. Nerin: hello.")
        return _form(system, "sum", "summary", "session reflection: owntime-20261108T12", "We spoke of crisis data.",
                     edges=(("summarizes", ep),), attributes={"digest_method": "mechanical-floor-v1"})
    if kind == "world_model":
        return _card(system)
    if kind == "dream":
        return _form(system, "dream", "dream", "Dream: aggregate crisis beside lived", "Two islands lit up.",
                     attributes={"signals": [{"kind": "unresolved_tension", "fragment": "crisis beside lived"}]})
    if kind.startswith("diary:"):
        return _diary(system, f"d-{kind[6:]}", kind[6:])
    if kind == "episode":
        return _form(system, "ep", "episode", "exchange: User asked about the crisis numbers and I answered with "
                     "the…", "User: what do the crisis numbers mean? Nerin: they are people.",
                     attributes={"digest_method": "mechanical-v2"})
    return _form(system, kind, kind, f"{kind}: {CUT}", BODY, keywords=("crisis", "testimony"))


KINDS = ["episode", "summary", "world_model", "dream", "interest", "lesson", "realization", "observation",
         "diary:question", "diary:problem", "diary:commitment", "diary:idea"]


# --------------------------------------------------------------------------- every kind: the title alone changes


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_is_retitled_alone(home, kind) -> None:
    gid = _make(home, kind)
    before = _row(home, gid)
    cut = before.attributes["title"]
    vec0 = home.store.stored_vector(before.assertion_id)
    new = f"Zephyrine: why aggregate crisis numbers need first-person testimony ({kind})"

    out = _retitle(home, gid, new, task_id="")
    assert out["applied"] is True and out["outcome"] == "applied" and out["field"] == "title"
    assert out["version"] == 1 and out["previous_version"] == 0 and out["captured_original"] is True

    after = _row(home, gid)
    assert after.subject == before.subject and after.assertion_id == before.assertion_id
    assert after.object == before.object                                      # the body: byte-equal
    assert after.attributes["title"] == new                                   # stored whole, as given
    keys = TITLE_KEYS | {"pending"}
    assert {k: v for k, v in after.attributes.items() if k not in keys} == \
        {k: v for k, v in before.attributes.items() if k not in keys}  # keywords, reading, kind: untouched
    if isinstance(before.attributes.get("pending"), dict):  # a card forms pending its authored title (2026-11-09)
        assert before.attributes["pending"]["title"] is True and cut is None
        assert after.attributes["pending"] == {**before.attributes["pending"], "title": False}
    else:
        assert "pending" not in after.attributes
    assert after.attributes["title_version"] == 1
    assert after.attributes["title_provenance"]["author"] == MODEL
    assert after.observed_at == before.observed_at and after.provenance == before.provenance

    rows = home.versions(gid, field="title")
    assert [(r["version"], r["text"], r["current"]) for r in rows] == [(0, cut, False), (1, new, True)]
    v0, v1 = rows
    assert v0["field"] == v1["field"] == "title" and v0["title"] == cut and v0["cause"]["cause"] == "formation"
    assert v1["author"] == MODEL and v1["reader"] == READER and v1["cause"] == {"cause": "backfill"}
    assert v1["sources"] == [{"kind": "step", "run_id": "run-retitle-1", "seq": 7}]
    assert v1["digest_method"] == "retitle-v1"
    assert home.versions(gid) == []                                           # the digest/card never rewritten

    # The vector is the new canonical text's (the title is its first line).
    vec1 = home.store.stored_vector(after.assertion_id)
    if vec0 is not None:
        assert np.allclose(vec1, home.emb.embed_texts([canonical_text(after)])[0], atol=1e-6)
        assert not np.allclose(vec1, vec0, atol=1e-3)

    # The display block's title is the current one (a diary block is redacted: no title, no words).
    [binding] = [e for e in home.export_replay(families=("binding",)) if e["payload"]["record_id"] == gid]
    if kind.startswith("diary:"):
        assert binding["display"]["redacted"] == "diary" and "title" not in binding["display"]
    else:
        assert binding["display"]["title"] == new
        assert home.record_understanding(gid)["title"] == new
        assert home.record_understanding(gid)["digest"] == before.object

    if home.kind == "sqlite":
        found = home.store.query_keywords(["zephyrine"], scope=SCOPE, owner_id=OWNER)
        assert [a.subject for a in found] == [gid]


def test_module_function_and_the_task_queue(home) -> None:
    gid = _make(home, "lesson")
    body_task = home.tasks.enqueue("digest.rewrite", gid, scope=SCOPE, owner_id=OWNER, basis=f"{gid}@v0",
                                   strength=0.5, cause={"cause": "backfill"})["task_id"]
    title_task = home.tasks.enqueue("digest.rewrite", gid, scope=SCOPE, owner_id=OWNER, basis=f"{gid}@title",
                                    strength=0.5, cause={"cause": "backfill"})["task_id"]
    out = retitle(home, gid, title="lesson: Check a country's indicators before citing them", author=OPERATOR,
                  cause="operator", expected_version=0, task_id=title_task)
    assert out["applied"] is True and _row(home, gid).attributes["title"].startswith("lesson: Check")
    assert home.tasks.task(title_task)["status"] == "done"      # the task the writer named is acked
    assert home.tasks.task(body_task)["status"] == "pending"    # a body task stays: the words are unchanged


# --------------------------------------------------------------------------- recall finds the new title


def test_recall_finds_the_record_by_its_new_title_and_short_title_derives_from_it(home) -> None:
    gid = _form(home, "ep-q", "episode", "exchange: quillmoss", "User: hello there. Nerin: hello.")
    _form(home, "ep-other", "episode", "exchange: gardens", "An unrelated exchange about gardens.")
    if home.kind == "sqlite":
        assert [a.subject for a in home.store.query_keywords(["quillmoss"], scope=SCOPE, owner_id=OWNER)] == [gid]
    new = ("Resuming the deep search on self-evolving archival systems with Ada, and why the marrowind index "
           "finally made the old notes readable again for both of us")
    assert len(new) > 120
    _retitle(home, gid, new)
    if home.kind == "sqlite":
        store = home.store
        assert store.query_keywords(["quillmoss"], scope=SCOPE, owner_id=OWNER) == []   # the old title is gone
        assert [a.subject for a in store.query_keywords(["marrowind"], scope=SCOPE, owner_id=OWNER)] == [gid]
        store._conn.execute(f"INSERT INTO {store._table}_fts({store._table}_fts) VALUES('integrity-check')")
    recall = home.reconstruct(Stimulus(cue_text="marrowind index"), scopes=[(SCOPE, OWNER)], journal=False)
    ids = {gid, _row(home, gid).assertion_id}
    [handle] = [h for h in recall.handles if h.record_id in ids] or [None]
    assert handle is not None and handle.title == short_title(new)
    assert handle.title.endswith("…") and _row(home, gid).attributes["title"] == new        # stored whole


# --------------------------------------------------------------------------- refusals


def _snapshot(system, gid: str):
    row = _row(system, gid)
    return (row.object, dict(row.attributes), system.current_seq(),
            system.store.stored_vector(row.assertion_id), system.journal.versions(record_id=row.subject))


def test_refusals_write_nothing(home) -> None:
    gid = _make(home, "interest")
    snap = _snapshot(home, gid)
    assert _retitle(home, gid, "")["reason"] == "empty_title"
    assert _retitle(home, gid, "   \n\t ")["reason"] == "empty_title"
    assert _retitle(home, "ex:interest-nope", "A title")["reason"] == "unknown_record"
    same = _retitle(home, gid, f"  interest: {CUT}  ")                       # unchanged: no version
    assert same["applied"] is False and same["outcome"] == "unchanged" and same["version"] == 0
    assert _snapshot(home, gid) == snap
    home.emb.dead = True
    assert _retitle(home, gid, "interest: A title the dead embedder cannot index")["reason"] == \
        "embedder_unavailable"
    home.emb.dead = False
    assert _snapshot(home, gid) == snap

    # Stale: a second writer against version 0 after the first retitle.
    assert _retitle(home, gid, "interest: Personal stories behind crisis statistics")["applied"] is True
    snap1 = _snapshot(home, gid)
    stale = _retitle(home, gid, "interest: A concurrent title", version=0)
    assert stale["reason"] == "stale" and stale["version"] == 1
    assert _snapshot(home, gid) == snap1
    replay = _retitle(home, gid, "interest: Personal stories behind crisis statistics", version=0)
    assert replay["outcome"] == "unchanged" and replay["version"] == 1      # a crash-retry is idempotent

    # A closed record: its replacement is the current one.
    ep = _make(home, "episode")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        out = apply_redigestion(home, [{"record_id": ep, "digest": "A replacement record's words."}],
                                actor="operator")
    closed = _retitle(home, ep, "exchange: what the crisis numbers mean")
    assert closed["reason"] == "closed" and closed["replaced_by"] == [out["outcomes"][0]["new_record_id"]]
    assert home.journal.versions(record_id=ep) == []


def test_hash_chained_diary_entry_refuses(home) -> None:
    gid = _form(home, "chained", "diary", "A chained entry", "Owner-direct words, attested.",
                attributes={"diary_type": "note", "entry_hash": "0" * 64}, provenance={"source": "owner-direct"})
    snap = _snapshot(home, gid)
    assert _retitle(home, gid, "A better title")["reason"] == "hash_chained"
    assert _snapshot(home, gid) == snap


def test_arguments_are_checked_loudly(home) -> None:
    gid = _make(home, "interest")
    with pytest.raises(ValueError, match="author.kind"):
        _retitle(home, gid, "x", author={"kind": "llm"})
    with pytest.raises(ValueError, match="reader"):
        _retitle(home, gid, "x", reader=None)
    with pytest.raises(ValueError, match="ledger step"):
        _retitle(home, gid, "x", sources=())
    with pytest.raises(ValueError, match="cause"):
        _retitle(home, gid, "x", cause="whim")
    assert home.versions(gid, field="title") == []


# --------------------------------------------------------------------------- history across verbs


def test_versions_and_revert_of_the_title(home) -> None:
    gid = _make(home, "interest")
    _retitle(home, gid, "interest: Personal stories behind crisis statistics")
    _retitle(home, gid, "interest: Testimony that turns crisis statistics into people", version=1,
             author=OPERATOR, reader=None, sources=(), cause="operator")
    out = home.revert_digest(gid, 0, expected_version=2, field="title", reason="keep his first words")
    assert out["applied"] is True and out["version"] == 3 and out["field"] == "title"
    assert _row(home, gid).attributes["title"] == f"interest: {CUT}"
    rows = home.versions(gid, field="title")
    assert [r["version"] for r in rows] == [0, 1, 2, 3] and rows[3]["current"] is True
    assert rows[3]["cause"]["cause"] == "revert" and rows[3]["cause"]["reverted_to"] == 0
    assert rows[3]["author"] == rows[0]["author"]                          # the words are the formation writer's
    assert home.revert_digest(gid, 9, expected_version=3, field="title")["reason"] == "unknown_version"
    assert _row(home, gid).object == BODY


def test_a_digest_reading_that_changes_the_title_versions_it(home) -> None:
    gid = _make(home, "episode")
    cut = _row(home, gid).attributes["title"]
    mind = {"kind": "entity-mind", "id": OWNER}
    out = home.rewrite_digest(gid, text="We talked about what crisis numbers hide.", title="What crisis numbers hide",
                              author=mind, reader=READER, sources=STEP, cause="backfill", expected_version=0)
    assert out["applied"] is True and out["title_version"] == 1
    rows = home.versions(gid, field="title")
    assert [(r["version"], r["text"]) for r in rows] == [(0, cut), (1, "What crisis numbers hide")]
    assert rows[1]["author"] == mind and rows[1]["digest_method"] == "authored-v1"
    # A retitle on top, then a digest reading that keeps the title: no title version, the title stays.
    _retitle(home, gid, "Why crisis numbers hide the people", version=1)
    again = home.rewrite_digest(gid, text="A second reading of the same talk.", author=mind, reader=READER,
                                sources=STEP, cause="ripple", expected_version=1)
    assert again["applied"] is True and "title_version" not in again
    assert _row(home, gid).attributes["title"] == "Why crisis numbers hide the people"
    assert [r["version"] for r in home.versions(gid, field="title")] == [0, 1, 2]


def test_title_version_zero_names_the_reading_that_wrote_the_title(home, monkeypatch) -> None:
    """Records rewritten before titles had versions (the 1181 backfill set episode titles through rewrite_digest):
    title version 0 names the digest reading that introduced the title, not the newest reading."""
    from abstractmemory import understanding

    mind = {"kind": "entity-mind", "id": OWNER}
    titled = _form(home, "ep-t", "episode", "exchange: x", "User: x. Nerin: y.",
                   attributes={"digest_method": "mechanical-v2"})
    kept = _form(home, "ep-k", "episode", "exchange: z", "User: z. Nerin: w.",
                 attributes={"digest_method": "mechanical-v2"})
    with monkeypatch.context() as m:        # the state before this change: no title rows beside a digest rewrite
        m.setattr(understanding, "_title", lambda attrs: "")
        home.rewrite_digest(titled, text="We spoke briefly.", title="A brief talk", author=mind, reader=READER,
                            sources=STEP, cause="backfill", expected_version=0)
        home.rewrite_digest(kept, text="We spoke again.", author=mind, reader=READER, sources=STEP,
                            cause="backfill", expected_version=0)
    assert home.versions(titled, field="title") == [] and _row(home, titled).attributes["title"] == "A brief talk"
    home.rewrite_digest(titled, text="We spoke, briefly.", author=OPERATOR, cause="operator", expected_version=1)
    _retitle(home, titled, "A brief talk about x and y")
    _retitle(home, kept, "Talking about z")
    v0 = home.versions(titled, field="title")[0]
    assert v0["text"] == "A brief talk" and v0["author"] == mind              # the rewrite that set it, not v2's
    assert v0["cause"]["title_from"] == {"field": "digest", "version": 1}
    k0 = home.versions(kept, field="title")[0]
    assert k0["text"] == "exchange: z" and k0["author"] == {"kind": "mechanical", "id": "mechanical-v2"}
    assert k0["cause"]["title_from"] == {"field": "digest", "version": 0}


def test_reverting_the_words_keeps_a_title_retitled_since(home) -> None:
    gid = _make(home, "episode")
    mind = {"kind": "entity-mind", "id": OWNER}
    original = _row(home, gid).object
    home.rewrite_digest(gid, text="We talked about what crisis numbers hide.", author=mind, reader=READER,
                        sources=STEP, cause="backfill", expected_version=0)
    _retitle(home, gid, "What the crisis numbers hide")
    out = home.revert_digest(gid, 0, expected_version=1, reason="the words were wrong")
    assert out["applied"] is True and "title_version" not in out
    row = _row(home, gid)
    assert row.object == original and row.attributes["title"] == "What the crisis numbers hide"
    assert [r["version"] for r in home.versions(gid, field="title")] == [0, 1]


def test_diary_title_versions_are_sealed_in_the_revision_stream(home) -> None:
    gid = _make(home, "diary:question")
    new = "Diary entry (question) — 2026-11-07: Why do the displacement numbers hide the people behind them?"
    _retitle(home, gid, new)
    revisions = [e for e in home.export_replay(families=("revision",)) if e["payload"]["record_id"] == gid]
    assert [e["payload"]["version"] for e in revisions] == [0, 1]
    for e in revisions:
        assert e["payload"]["redacted"] == "diary" and e["payload"]["field"] == "title"
        assert e["payload"]["text"] == "" and e["payload"]["title"] == "" and e["payload"]["keywords"] == []
        assert e["display"]["redacted"] == "diary" and "digest" not in e["display"]
    # The journal keeps the version whole (the book's door reads it; the stream is sealed).
    assert [v.text for v in home.journal.versions(record_id=gid, field="title")][1] == new
    # A non-diary record's revision envelope carries its title verbatim.
    lesson = _make(home, "lesson")
    _retitle(home, lesson, "lesson: Check the indicators before citing them")
    [last] = [e for e in home.export_replay(families=("revision",))
              if e["payload"]["record_id"] == lesson and e["payload"]["version"] == 1]
    assert last["payload"]["text"] == "lesson: Check the indicators before citing them"
    assert last["display"]["title"] == "lesson: Check the indicators before citing them"
