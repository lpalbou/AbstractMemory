"""`rearm_pending` / `pending_records`: a pending record whose authoring ran out is re-armed, never left pending forever
(operator rule 2026-11-09: "title + summary must ALWAYS exist for every memory").

The live failure: a bug in the host made every authoring attempt fail for a while, so records stayed marked pending
with every `title.author` / `digest.author` task terminal (failed after `max_attempts` claims, or skipped).
`declare_pending` answers such a record `already_pending` and queues nothing. `rearm_pending` queues formation's
task again for each pending field no live task owns, keeps the marker (its `rearmed` count) and journals the re-arm;
`pending_records` finds those records in one call. Every case runs on both substrate pairs.

MUTATION LIST (scratch copy, each mutant run against this file; all red, the source restored byte-exact):
M1 no task queued (the enqueue hook dropped); M2 the tasks at a non-formation priority; M3 the live_task
short-circuit removed (a live field re-armed beside its task); M4 the not_pending short-circuit removed; M5 the
`closed` refusal removed; M6 the `no_task_queue` refusal removed; M7 the marker's `rearmed` count not written; M8 the
marker's `attempts` not restarted; M9 no journal row (field `pending`) for the re-arm; M10 a terminal task's identity
reused (no fresh basis: the re-arm queues nothing); M11 `pending_records` keeps records whose fields all have a live
task under the default filter; M12 `pending_records` ignores `scopes`; M13 `pending_records` keeps closed records;
M14 a deferred task not counted live (re-armed beside it).
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
    apply_redigestion,
    pending_records,
    rearm_pending,
)
from abstractmemory.memory_tasks import task_id_for  # noqa: E402
from abstractmemory.records import resolve_digest_assertion  # noqa: E402
from abstractmemory.understanding import REARM_PENDING_METHOD  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "artifact", "artifact_id": "authoring-call-1"}]
REARMER = {"kind": "mechanical", "id": "rearm_pending"}
BODY = "We talked about the archive index and who rebuilds it."
LIVE = ("pending", "deferred", "leased")


class Embedder:
    """Deterministic unit vectors from the text hash; counts its calls."""

    model = "fake-hash-16"

    def __init__(self) -> None:
        self.calls = 0

    def embed_texts(self, texts):
        self.calls += 1
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(16)
            out.append((v / np.linalg.norm(v)).tolist())
        return out


def _open(kind: str, tmp_path, *, task_queue: bool = True) -> MemorySystem:
    emb = Embedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if kind == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        else:
            path = tmp_path / f"memory-{int(task_queue)}.sqlite3"
            store, journal = SQLiteTripleStore(path, embedder=emb), SQLiteJournal(path)
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=task_queue)
    system.emb = emb
    return system


@pytest.fixture(params=["memory", "sqlite"])
def home(request, tmp_path):
    system = _open(request.param, tmp_path)
    system.kind = request.param
    yield system
    system.journal.close()
    system.store.close()


def _form(system, key: str, *, kind: str = "episode", title: Any = None, digest: str = BODY,
          scope: str = SCOPE, **kw: Any) -> str:
    title = title if title is not None or kw.get("pending") else f"Exchange {key}"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many([MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)],
                                     scope=scope, owner_id=OWNER, idempotency_key=key)
    return gid


def _pending(system, key: str, fields=("title", "summary"), **kw: Any) -> str:
    return _form(system, key, pending=tuple(fields), **kw)


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


def _authoring(system, gid: str) -> List[Dict[str, Any]]:
    return system.tasks.tasks(kind=("title.author", "digest.author"), target_id=gid)


def _live(system, gid: str) -> Dict[str, Dict[str, Any]]:
    return {t["kind"]: t for t in _authoring(system, gid) if t["status"] in LIVE}


def _exhaust(system, gid: str, kinds=("title.author", "digest.author")) -> List[str]:
    """What the live bug did: every claim of every live authoring task failed until `max_attempts`."""
    out = []
    for t in [t for t in _authoring(system, gid) if t["status"] in LIVE and t["kind"] in kinds]:
        for n in range(int(t["max_attempts"])):
            assert system.tasks.claim([t["task_id"]], holder="rt")["claimed"]
            res = system.tasks.release(t["task_id"], holder="rt", outcome="retry", reason=f"authoring failed {n}")
        assert res["task"]["status"] == "failed"
        out.append(t["task_id"])
    return out


def _drain(system, gid: str, *, title: str = "", summary: str = "") -> Dict[str, Any]:
    """The runtime's drainer: per live task, read the packet, then retitle / rewrite_digest with its task id."""
    out: Dict[str, Any] = {}
    live = _live(system, gid)
    if summary:
        t = live["digest.author"]
        packet = system.task_packet(t["task_id"])
        out["summary"] = system.rewrite_digest(gid, text=summary, author=MODEL, reader=READER, sources=STEP,
                                               cause={"cause": "repair", "pending": "summary"},
                                               expected_version=int(packet["expected_version"]), task_id=t["task_id"])
    if title:
        t = live["title.author"]
        packet = system.task_packet(t["task_id"])
        out["title"] = system.retitle(gid, title=title, author=MODEL, reader=READER, sources=STEP,
                                      cause={"cause": "repair", "pending": "title"},
                                      expected_version=int(packet["expected_version"]), task_id=t["task_id"])
    return out


def _snapshot(system, gid: str):
    return (dict(_row(system, gid).attributes), [(t["task_id"], t["status"]) for t in system.tasks.tasks(target_id=gid)],
            [v["version_id"] for v in system.versions(gid)])


# --------------------------------------------------------------------------- the exhausted record


def test_an_exhausted_pending_record_is_rearmed_and_then_authored(home) -> None:
    gid = _pending(home, "exhausted")
    aid = str(_row(home, gid).assertion_id)
    since = _row(home, gid).attributes["pending"]["since"]
    failed = _exhaust(home, gid)
    assert len(failed) == 2 and _live(home, gid) == {}
    assert _row(home, gid).attributes["pending"]["attempts"] == 3
    # Before: nothing could take it out of pending (declare_pending: already_pending, nothing queued).
    assert home.declare_pending(gid)["reason"] == "already_pending" and _live(home, gid) == {}
    [found] = home.pending_records(scopes=SCOPES)
    assert found["record_id"] == gid and found["fields"] == ["title", "summary"]
    assert found["unowned"] == ["title", "summary"] and found["live"] == {"title": None, "summary": None}
    assert found["rearmed"] == 0 and found["record_kind"] == "episode"
    calls = home.emb.calls

    out = home.rearm_pending(gid, reason="authoring endpoint bug, fixed")
    assert out["applied"] is True and out["outcome"] == "rearmed" and out["reason"] is None
    assert out["record_id"] == gid and out["field"] == "pending" and out["rearmed"] == 1 and out["live"] == {}
    # Formation's task exactly, on the next free basis (the failed ones keep theirs).
    live = _live(home, gid)
    assert sorted(live) == ["digest.author", "title.author"]
    for fld, kind in (("title", "title.author"), ("summary", "digest.author")):
        t = live[kind]
        assert t["task_id"] == task_id_for(kind, gid, f"{aid}@pending-{fld}@2") == out["tasks"][fld]
        assert (t["status"], t["capability"], t["priority"], t["strength"], t["basis_version"], t["attempts"],
                t["max_attempts"], t["assertion_id"], t["scope"], t["owner_id"]) == (
            "pending", "summaries", 5, 1.0, 0, 0, 3, aid, SCOPE, OWNER)
        assert t["cause"] == {"cause": "repair", "pending": fld, "rearmed": 1,
                              "reason": "authoring endpoint bug, fixed"}
    assert sorted(out["enqueued"]) == sorted(out["tasks"].values())
    assert {t["task_id"]: t["status"] for t in _authoring(home, gid) if t["task_id"] in failed} == {
        tid: "failed" for tid in failed}
    # The marker stays; attempts restart for the fresh tasks; title still None, body untouched, no embedder call.
    row = _row(home, gid)
    marker = row.attributes["pending"]
    assert {k: marker[k] for k in ("title", "summary", "attempts", "rearmed", "since")} == {
        "title": True, "summary": True, "attempts": 0, "rearmed": 1, "since": since}
    assert marker["last_rearmed_at"] and out["pending"] == marker
    assert row.attributes["title"] is None and row.object == BODY and home.emb.calls == calls
    # The journal keeps the re-arm with its provenance.
    [rearm] = home.versions(gid, field="pending")
    assert rearm["version"] == 1 and rearm["text"] == "title, summary" and rearm["author"] == REARMER
    assert rearm["digest_method"] == REARM_PENDING_METHOD and rearm["version_id"] == out["version_id"]
    cause = rearm["cause"]
    assert (cause["cause"], cause["reason"], cause["rearmed"], cause["pending"], cause["tasks"],
            cause["attempts_before"]) == ("repair", "authoring endpoint bug, fixed", 1, ["title", "summary"],
                                          out["tasks"], 3)
    assert sorted(e["task_id"] for f in ("title", "summary") for e in cause["exhausted"][f]) == sorted(failed)
    assert {e["status"] for f in ("title", "summary") for e in cause["exhausted"][f]} == {"failed"}
    assert cause["exhausted"]["title"][0]["error"] == "authoring failed 2"
    revisions = [e["payload"] for e in home.export_replay(families=("revision",))
                 if e["payload"]["record_id"] == gid and e["payload"]["field"] == "pending"]
    assert [r["version_id"] for r in revisions] == [rearm["version_id"]]
    # Found no more (a live task owns each field), but still pending.
    assert home.pending_records(scopes=SCOPES) == []
    assert [r["record_id"] for r in home.pending_records(scopes=SCOPES, live_task=True)] == [gid]
    assert home.pending_records(scopes=SCOPES, live_task=None)[0]["live"] == out["tasks"]
    # Each claim of a fresh task is an attempt on the marker again.
    home.tasks.claim([out["tasks"]["title"]], holder="rt", lease_seconds=1)
    assert _row(home, gid).attributes["pending"]["attempts"] == 1
    home.tasks.release(out["tasks"]["title"], holder="rt", outcome="retry", reason="once more")

    done = _drain(home, gid, summary="Ada and I rebuilt the archive index.", title="Rebuilding the archive index")
    assert done["summary"]["applied"] is True and done["summary"]["pending_cleared"] == ["summary"]
    assert done["title"]["applied"] is True and done["title"]["pending_cleared"] == ["title"]
    row = _row(home, gid)
    assert row.attributes["title"] == "Rebuilding the archive index" and "pending" not in row.attributes
    assert row.object == "Ada and I rebuilt the archive index."
    assert {t["task_id"]: t["status"] for t in _authoring(home, gid)} == {
        **{tid: "failed" for tid in failed}, **{tid: "done" for tid in out["tasks"].values()}}
    assert home.pending_records(scopes=SCOPES, live_task=None) == []
    assert home.rearm_pending(gid)["reason"] == "not_pending"


def test_a_skipped_task_is_rearmed_alone_beside_a_live_one(home) -> None:
    gid = _pending(home, "skipped")
    live = _live(home, gid)
    title_task, summary_task = live["title.author"]["task_id"], live["digest.author"]["task_id"]
    home.tasks.claim([title_task], holder="rt")
    home.tasks.release(title_task, holder="rt", outcome="skip", reason="over_context", detail={"tokens": 90000})
    home.tasks.claim([summary_task], holder="rt")
    home.tasks.release(summary_task, holder="rt", outcome="retry", reason="model timeout")
    home.tasks.claim([summary_task], holder="rt", lease_seconds=600)       # leased: still live
    [found] = pending_records(home, scopes=SCOPES)
    assert found["unowned"] == ["title"] and found["live"] == {"title": None, "summary": summary_task}

    out = rearm_pending(home, gid)
    assert out["outcome"] == "rearmed" and list(out["tasks"]) == ["title"] and out["live"] == {"summary": summary_task}
    assert out["tasks"]["title"] == task_id_for("title.author", gid, f"{_row(home, gid).assertion_id}@pending-title@2")
    assert {t["kind"]: t["task_id"] for t in _live(home, gid).values()} == {
        "title.author": out["tasks"]["title"], "digest.author": summary_task}
    # attempts = the highest claim count of the live tasks (the leased summary task: 2).
    assert _row(home, gid).attributes["pending"]["attempts"] == 2
    [rearm] = home.versions(gid, field="pending")
    assert rearm["text"] == "title" and rearm["cause"]["live"] == {"summary": summary_task}
    assert [e["status"] for e in rearm["cause"]["exhausted"]["title"]] == ["skipped"]
    assert pending_records(home, scopes=SCOPES) == []


def test_a_second_exhaustion_is_rearmed_again_on_a_fresh_basis(home) -> None:
    gid = _pending(home, "twice", fields=("title",), digest="Ada told me where the index lives.")
    aid = str(_row(home, gid).assertion_id)
    _exhaust(home, gid)
    first = home.rearm_pending(gid)
    _exhaust(home, gid)
    assert [r["rearmed"] for r in home.pending_records(scopes=SCOPES)] == [1]
    second = home.rearm_pending(gid, cause="operator")
    assert second["outcome"] == "rearmed" and second["rearmed"] == 2
    assert second["tasks"] == {"title": task_id_for("title.author", gid, f"{aid}@pending-title@3")}
    assert first["tasks"]["title"] != second["tasks"]["title"]
    assert _row(home, gid).attributes["pending"]["rearmed"] == 2
    assert [v["cause"]["rearmed"] for v in home.versions(gid, field="pending")] == [1, 2]
    assert _live(home, gid)["title.author"]["cause"] == {"cause": "operator", "pending": "title", "rearmed": 2}
    assert _drain(home, gid, title="Where the index lives")["title"]["pending_cleared"] == ["title"]
    assert "pending" not in _row(home, gid).attributes


def test_a_declared_legacy_card_whose_tasks_ran_out_is_rearmed_and_authored(home) -> None:
    card = _form(home, "legacy-card", kind="world_model", title="World model: person:ada",
                 digest="What I know of person:ada: worked with Ada on the archive (3 records).",
                 participants=("person:ada",),
                 attributes={"world_model": True, "target": "person:ada", "revision": 1,
                             "evidence_fingerprint": "fp-old", "known_source_ids": ["ex:a", "ex:b", "ex:c"],
                             "digest_method": "mechanical-card-v2"})
    assert home.declare_pending(card)["applied"] is True
    _exhaust(home, card)
    out = home.rearm_pending(card)
    assert out["outcome"] == "rearmed" and sorted(out["tasks"]) == ["summary", "title"]
    assert [v["version"] for v in home.versions(card, field="pending")] == [1, 2]   # the declaration, the re-arm
    done = _drain(home, card, summary="Ada is the archivist I work beside.", title="Ada, the archivist")
    assert done["summary"]["field"] == "card" and done["title"]["pending_cleared"] == ["title"]
    row = _row(home, card)
    assert row.attributes["title"] == "Ada, the archivist" and "pending" not in row.attributes
    assert row.attributes["target"] == "person:ada"


# --------------------------------------------------------------------------- unchanged and refused


def test_a_live_task_leaves_the_record_unchanged(home) -> None:
    gid = _pending(home, "live")
    tasks = {t["kind"]: t["task_id"] for t in _authoring(home, gid)}
    snap = _snapshot(home, gid)
    out = home.rearm_pending(gid)
    assert out["applied"] is False and out["outcome"] == "unchanged" and out["reason"] == "live_task"
    assert out["tasks"] == {"title": tasks["title.author"], "summary": tasks["digest.author"]}
    assert _snapshot(home, gid) == snap
    # A deferred task (an unreachable endpoint) is live too.
    home.tasks.claim([tasks["title.author"]], holder="rt")
    home.tasks.release(tasks["title.author"], holder="rt", outcome="defer", reason="endpoint unreachable",
                       until="2099-01-01T00:00:00+00:00")
    assert home.tasks.task(tasks["title.author"])["status"] == "deferred"
    snap = _snapshot(home, gid)
    assert home.rearm_pending(gid)["reason"] == "live_task" and _snapshot(home, gid) == snap
    assert home.pending_records(scopes=SCOPES) == []


def test_a_record_not_pending_is_unchanged(home) -> None:
    gid = _form(home, "titled")
    snap = _snapshot(home, gid)
    out = home.rearm_pending(gid)
    assert (out["applied"], out["outcome"], out["reason"], out["tasks"], out["rearmed"]) == (
        False, "unchanged", "not_pending", {}, 0)
    assert _snapshot(home, gid) == snap
    assert home.pending_records(live_task=None) == []


def test_refusals_write_nothing(home) -> None:
    with pytest.raises(ValueError, match="cause"):
        home.rearm_pending("ex:none", cause="whim")
    assert home.rearm_pending("ex:none")["reason"] == "unknown_record"
    gid = _pending(home, "closed", fields=("title",), attributes={"digest_method": "mechanical-v2"})
    _exhaust(home, gid)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        replaced = apply_redigestion(home, [{"record_id": gid, "digest": "A replacement record's words."}],
                                     actor="operator")
    snap = _snapshot(home, gid)
    out = home.rearm_pending(gid)
    assert out["outcome"] == "refused" and out["reason"] == "closed"
    assert out["replaced_by"] == [replaced["outcomes"][0]["new_record_id"]]
    assert _snapshot(home, gid) == snap
    # A closed record is not listed (its replacement owes the metadata).
    assert gid not in [r["record_id"] for r in home.pending_records(live_task=None)]


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_a_home_without_a_task_queue_is_refused(kind, tmp_path) -> None:
    system = _open(kind, tmp_path, task_queue=False)
    try:
        gid = _form(system, "no-queue")
        before = dict(_row(system, gid).attributes)
        out = rearm_pending(system, gid)
        assert out["applied"] is False and out["reason"] == "no_task_queue"
        assert dict(_row(system, gid).attributes) == before and system.journal.versions(record_id=gid) == []
    finally:
        system.journal.close()
        system.store.close()


# --------------------------------------------------------------------------- the bulk read


def test_pending_records_reads_the_asked_scopes_oldest_first(home) -> None:
    a = _pending(home, "first", fields=("title",))
    b = _pending(home, "second", fields=("summary",), title="The second exchange")
    other = _pending(home, "elsewhere", fields=("title",), scope="work")
    _form(home, "authored")
    for gid in (a, b, other):
        _exhaust(home, gid)
    assert [r["record_id"] for r in home.pending_records(scopes=SCOPES)] == [a, b]
    assert [r["record_id"] for r in home.pending_records(scopes=[("work", OWNER)])] == [other]
    assert sorted(r["record_id"] for r in home.pending_records()) == sorted([a, b, other])
    [rb] = [r for r in home.pending_records(scopes=SCOPES) if r["record_id"] == b]
    assert rb["fields"] == ["summary"] and rb["unowned"] == ["summary"] and rb["scope"] == SCOPE
    assert rb["owner_id"] == OWNER and rb["pending"]["summary"] is True
    for r in home.pending_records(scopes=SCOPES):
        assert home.rearm_pending(r["record_id"])["outcome"] == "rearmed"
    assert home.pending_records(scopes=SCOPES) == [] and len(home.pending_records(scopes=SCOPES,
                                                                                    live_task=True)) == 2
    assert [r["record_id"] for r in home.pending_records()] == [other]
