"""The passes author a record's title and summary WITH it; pending only after a RECORDED authoring failure (operator
ruling 2026-11-09: "metadata is authored WITH the memory"; Codex review 2026-11-09 finding 10).

Memory has no model access: `world_model_pass` / `world_model_update`, `dream_pass`, `mine_candidates_pass`,
`consolidation_pass`, `wake_cue_dedup_pass` and `sleep_pass` take the host's `author(kind, body, context)` callable
(formation_authoring). Supplied and successful: the record forms with its authored title and summary (provenance
stamped, authored method, no authoring task). Raising, or returning what is not authored metadata: the record forms
pending with `attributes.pending.failure = {reason, error_class, message, at, fields}`, also in the pass's
`authoring` receipt. Not supplied: pending with reason `no_author_supplied`, explicit. A replay never calls it again.
Every case runs on both substrate pairs.

MUTATION LIST (scratch copy, each mutant run against this file; all red, the source restored byte-exact):
A1 the passes ignore `author` (never called); A2 the failure never reaches the marker; A3 the receipt drops the
failures; A4 the author's exception escapes the pass; A5 a capability-model author without its ledger step accepted;
A6 a mechanical author accepted; A7 an authored card summary labelled mechanical (card.author debt); A8 the authored card
revision left pending; A9 sleep_pass does not hand `author` to its phases; A10 a partial result discards the
authored title; A11 the dedup day summary never authored.
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
    consolidation_pass,
    current_world_models,
    dream_pass,
    mine_candidates_pass,
    sleep_pass,
    wake_cue_dedup_pass,
    world_model_pass,
    world_model_update,
)
from abstractmemory.records import resolve_digest_assertion  # noqa: E402
from abstractmemory.sleep_policy import SleepTuning  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
TUNING = SleepTuning(world_model_evidence_floor=3)
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "artifact", "artifact_id": "authoring-call-1"}]


class Embedder:
    model = "fake-hash-16"

    def embed_texts(self, texts):
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(16)
            out.append((v / np.linalg.norm(v)).tolist())
        return out


class Author:
    """The host's authoring callable: records each call; authors, raises, or returns `result` as told."""

    def __init__(self, *, fail: Exception = None, result: Any = None, provenance: Dict[str, Any] = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.fail, self.result = fail, result
        self.provenance = {"author": MODEL, "reader": READER, "sources": STEP} if provenance is None else provenance

    def __call__(self, kind: str, body: str, context: Dict[str, Any]) -> Any:
        self.calls.append({"kind": kind, "body": body, "context": dict(context)})
        if self.fail is not None:
            raise self.fail
        if self.result is not None:
            return self.result
        out = dict(self.provenance)
        if "title" in context["fields"]:
            out["title"] = f"The {kind} I name, {len(self.calls)}"
        if "summary" in context["fields"]:
            out["summary"] = f"What this {kind} holds, in my words ({len(self.calls)})."
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
    yield system
    system.journal.close()
    system.store.close()


def _form(system, key: str, kind: str = "episode", title: Any = None, digest: str = "", **kw: Any) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many(
            [MemoryRecordInput(kind=kind, title=title or f"Exchange {key}", digest=digest or f"We talked about {key}.",
                               **kw)], scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


def _authoring_tasks(system, gid: str) -> List[str]:
    return sorted(t["kind"] for t in system.tasks.tasks(target_id=gid)
                  if t["kind"] in ("title.author", "digest.author", "card.author"))


def _ada(system, n: int = 3) -> None:
    for i in range(n):
        _form(system, f"ada-{i}", title=f"Archive day {i} with Ada", digest=f"Worked with Ada on the archive, day {i}.",
              participants=("person:ada", OWNER))


def _card(out: Dict[str, Any]) -> str:
    [verdict] = [v for v in out["formed"] if v["target"] == "person:ada"]
    return verdict["card_id"]


def _night(system) -> None:
    _form(system, "s-1", digest="The connection pool saturated at noon.", keywords=("pool", "saturation", "noon"))
    _form(system, "s-3", digest="Planted the garden sensors at noon.", keywords=("garden", "sensors", "noon"))
    _form(system, "s-2", kind="lesson", title="Batching fixed the pool", digest="Batching the noon cron fixed it.",
          keywords=("pool", "batching"))


def _assert_authored(system, gid: str, kind: str, method: str) -> Dict[str, Any]:
    row = _row(system, gid)
    attrs = row.attributes
    assert "pending" not in attrs and attrs["title"].startswith(f"The {kind} I name")
    assert str(row.object).startswith(f"What this {kind} holds")
    assert attrs["digest_method"] == method
    for stamp in (attrs["title_provenance"], attrs["understanding"]):
        assert stamp["author"]["kind"] == "capability-model" and stamp["author"]["id"] == "summaries"
        assert stamp["reader"]["model"] == READER["model"] and stamp["sources"] == STEP
        assert stamp["cause"] == {"cause": "formation"} and stamp["version"] == 0
    assert _authoring_tasks(system, gid) == []
    assert system.record_understanding(gid)["authored_by"]["kind"] == "capability-model"
    return attrs


# --------------------------------------------------------------------------- authored with the record


def test_a_card_is_authored_with_its_formation(home) -> None:
    _ada(home)
    author = Author()
    out = world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING, author=author)
    card = _card(out)
    attrs = _assert_authored(home, card, "world_model", "authored-card-v1")
    assert attrs["authored_lead"] == str(_row(home, card).object)
    assert attrs["authored_known_ids"] == attrs["known_source_ids"] and attrs["authored_by"] == "summaries"
    assert attrs["target"] == "person:ada" and attrs["revision"] == 1
    [call] = author.calls
    assert call["kind"] == "world_model" and "Archive day 2 with Ada" in call["body"]   # authored FROM the briefing
    ctx = call["context"]
    assert ctx["pass"] == "world_model_pass" and ctx["fields"] == ["title", "summary"] and ctx["title"] is None
    assert ctx["attributes"]["target"] == "person:ada" and len(ctx["source_ids"]) == 3
    assert out["authoring"] == {"authored": [{"record_id": card, "record_kind": "world_model",
                                              "pass": "world_model_pass", "fields": ["title", "summary"]}],
                                "failures": []}
    assert [v["pending"] for v in out["formed"] if v.get("card_id") == card] == [[]]
    debt = home.understanding_debt(scopes=SCOPES)["debt"]
    assert "card.author" not in debt and "title.author" not in debt
    # The next revision carries the authored title and asks only for the summary.
    _form(home, "ada-3", title="Archive day 3 with Ada", digest="Ada found the lost index.",
          participants=("person:ada", OWNER))
    out2 = world_model_update(home, scopes=SCOPES, owner_id=OWNER, targets=["person:ada"], tuning=TUNING,
                              author=author)
    card2 = _card(out2)
    assert author.calls[-1]["context"]["fields"] == ["summary"]
    assert author.calls[-1]["context"]["title"] == attrs["title"]
    assert _row(home, card2).attributes["title"] == attrs["title"] and "pending" not in _row(home, card2).attributes


def test_a_dream_is_authored_and_never_twice(home) -> None:
    _night(home)
    author = Author()
    night = dream_pass(home, scopes=SCOPES, owner_id=OWNER, author=author)
    dream = night["dream_record_id"]
    attrs = _assert_authored(home, dream, "dream", "authored-v1")
    assert attrs["signals"] == night["signals"]
    assert [t["kind"] for t in home.tasks.tasks(target_id=dream)] == ["dream.narrate"]   # the narration stays owed
    assert night["authoring"]["authored"][0]["record_id"] == dream and night["authoring"]["failures"] == []
    assert "memory islands" in author.calls[0]["body"]
    again = dream_pass(home, scopes=SCOPES, owner_id=OWNER, author=author)
    assert again["created"] is False and len(author.calls) == 1
    assert again["authoring"] == {"authored": [], "failures": []}


def test_a_crash_replay_never_authors_the_standing_record_again(home, monkeypatch) -> None:
    _ada(home)
    author = Author()
    world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING, author=author)
    _form(home, "ada-3", title="Archive day 3 with Ada", digest="Ada found the lost index.",
          participants=("person:ada", OWNER))

    def crash(*_a, **_kw):
        raise RuntimeError("crashed between forming the revision and closing the prior")

    monkeypatch.setattr(home, "close_record", crash)
    with pytest.raises(RuntimeError, match="crashed"):
        world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING, author=author)
    assert len(author.calls) == 2
    monkeypatch.undo()
    out = world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING, author=author)
    assert len(author.calls) == 2 and out["authoring"] == {"authored": [], "failures": []}
    standing = current_world_models(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal)["person:ada"]
    assert standing.attributes["revision"] == 2 and "pending" not in standing.attributes
    assert standing.attributes["digest_method"] == "authored-card-v1"


def test_offers_candidates_and_the_dedup_day_summary_are_authored(home) -> None:
    def diary(key: str, diary_type: str, title: str, words: str, session: str, **attrs: Any) -> str:
        return _form(home, key, kind="diary", title=title, digest=words,
                     attributes={"diary_type": diary_type, **attrs},
                     provenance={"source": "owner-direct", "session_id": session})

    problem = diary("q", "problem", "the connection pool keeps saturating",
                    "the connection pool keeps saturating under noon load", "s-alpha")
    _form(home, "e1", title="Debugged the connection pool saturating", keywords=("connection", "pool"),
          provenance={"session_id": "s-beta"})
    _form(home, "e2", title="Connection pool fix verified", keywords=("connection", "pool"),
          provenance={"session_id": "s-gamma"})
    diary("a", "note", "batching writers fixed the pool", "batching the noon writers fixed the connection pool",
          "s-gamma", resolves=problem)
    author = Author()
    mined = mine_candidates_pass(home, scopes=SCOPES, owner_id=OWNER, author=author)
    [offer] = [c for c in mined["created"] if c["proposed_kind"] == "lesson"]
    attrs = _assert_authored(home, offer["candidate_id"], "summary", "authored-v1")
    assert attrs["maintenance_candidate"] is True and attrs["review_required"] is True
    assert offer["candidate_id"] in [a["record_id"] for a in mined["authoring"]["authored"]]

    for i in range(3):
        _form(home, f"b-{i}", kind="interest", title="The twelve bridges",
              digest=f"The twelve bridges keep returning to me, night {i}.")
    calls = len(author.calls)
    tended = consolidation_pass(home, scopes=SCOPES, owner_id=OWNER, author=author)
    [created] = tended["created"]
    _assert_authored(home, created["candidate_id"], "summary", "authored-v1")
    assert tended["authoring"]["authored"][0]["pass"] == "consolidation_pass"
    assert consolidation_pass(home, scopes=SCOPES, owner_id=OWNER, author=author)["authoring"]["authored"] == []
    assert len(author.calls) == calls + 1                                     # the replay never authors again

    for i in range(5):
        _form(home, f"loop-{i}", title=f"exchange: your own time continues #{i}",
              digest=f"entity:nerin: your own time continues nerin: [used tool: read_file] tick {i}")
    report = wake_cue_dedup_pass(home, scope=SCOPE, owner_id=OWNER, actor="operator", author=author)
    [summary] = report["formed_summaries"]
    attrs = _assert_authored(home, summary, "summary", "authored-v1")
    assert _row(home, summary).provenance["source"] == "wake_cue_dedup"
    assert report["authoring"]["authored"] == [{"record_id": summary, "record_kind": "summary",
                                                "pass": "wake_cue_dedup_pass", "fields": ["title", "summary"]}]


def test_a_night_hands_its_author_to_every_phase_and_sums_the_receipts(home) -> None:
    _ada(home)
    _night(home)
    author = Author()
    night = sleep_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING, author=author)
    passes = {a["pass"] for a in night["authoring"]["authored"]}
    assert {"world_model_pass", "dream_pass"} <= passes and night["authoring"]["failures"] == []
    assert night["authoring"]["authored"] == [e for phase in ("maintenance", "world_models", "mining", "dream")
                                              for e in night[phase]["authoring"]["authored"]]
    assert len(author.calls) == len(night["authoring"]["authored"])
    for entry in night["authoring"]["authored"]:
        assert "pending" not in _row(home, entry["record_id"]).attributes


# --------------------------------------------------------------------------- pending only after a recorded failure


def test_an_author_that_raises_forms_pending_with_the_failure_recorded(home) -> None:
    _ada(home)
    out = world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING,
                           author=Author(fail=ConnectionError("authoring endpoint returned 500")))
    card = _card(out)
    attrs = _row(home, card).attributes
    assert attrs["title"] is None and attrs["pending"]["title"] is True and attrs["pending"]["summary"] is True
    failure = attrs["pending"]["failure"]
    assert (failure["reason"], failure["error_class"], failure["message"], failure["fields"]) == (
        "author_raised", "ConnectionError", "authoring endpoint returned 500", ["title", "summary"])
    assert failure["at"]
    assert attrs["digest_method"] == "mechanical-card-v2"                     # the briefing: provisional body only
    assert _authoring_tasks(home, card) == ["digest.author", "title.author"]
    assert out["authoring"]["authored"] == []
    assert out["authoring"]["failures"] == [{"record_id": card, "record_kind": "world_model",
                                             "pass": "world_model_pass", **failure}]
    # The marker keeps the failure through the queue's life (a claim's attempt mirror, a re-arm).
    tid = home.tasks.tasks(kind=("title.author",), target_id=card)[0]["task_id"]
    home.tasks.claim([tid], holder="rt")
    assert _row(home, card).attributes["pending"]["failure"] == failure


def test_no_author_supplied_is_recorded_never_silent(home) -> None:
    _night(home)
    night = dream_pass(home, scopes=SCOPES, owner_id=OWNER)
    dream = night["dream_record_id"]
    marker = _row(home, dream).attributes["pending"]
    assert marker["title"] is True and marker["summary"] is True
    assert marker["failure"]["reason"] == "no_author_supplied" and marker["failure"]["error_class"] is None
    assert "dream_pass" in marker["failure"]["message"]
    assert night["authoring"]["failures"][0]["reason"] == "no_author_supplied"
    assert night["authoring"]["failures"][0]["record_id"] == dream


@pytest.mark.parametrize("case", ["title_only", "no_sources", "mechanical", "not_a_mapping", "empty"])
def test_what_is_not_authored_metadata_forms_pending_as_invalid(home, case) -> None:
    _ada(home)
    author = {
        "title_only": Author(result={"title": "Ada, the archivist", "author": MODEL, "reader": READER,
                                     "sources": STEP}),
        "no_sources": Author(provenance={"author": MODEL, "reader": READER}),
        "mechanical": Author(provenance={"author": {"kind": "mechanical", "id": "x"}}),
        "not_a_mapping": Author(result=["Ada", "the archivist"]),
        "empty": Author(result={"title": " ", "summary": "", "author": MODEL, "reader": READER, "sources": STEP}),
    }[case]
    out = world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING, author=author)
    card = _card(out)
    attrs = _row(home, card).attributes
    failure = attrs["pending"]["failure"]
    assert failure["reason"] == "invalid_result"
    if case == "title_only":
        assert attrs["title"] == "Ada, the archivist" and attrs["title_provenance"]["author"] == MODEL
        assert attrs["pending"]["title"] is False and attrs["pending"]["summary"] is True
        assert failure["fields"] == ["summary"] and _authoring_tasks(home, card) == ["digest.author"]
        assert out["authoring"]["authored"][0]["fields"] == ["title"]
    else:
        assert attrs["title"] is None and failure["fields"] == ["title", "summary"]
        assert _authoring_tasks(home, card) == ["digest.author", "title.author"]
        assert out["authoring"]["authored"] == []
    assert out["authoring"]["failures"][0]["reason"] == "invalid_result"
