"""A formed record and the tasks it owes commit together, and a pending field no live task owns is repaired (Codex
review 2026-11-09 finding 11).

The finding: `remember_many` stored the records BEFORE it queued their tasks, so an enqueue that failed left a pending
record (title None, `attributes.pending`) with an empty queue, and `declare_pending` then answered it `already_pending`
with a null task id: pending forever, against the operator rule "title + summary must ALWAYS exist". Now
(`memory_tasks.form_with_tasks`) the rows, their bindings and the tasks commit in ONE transaction on the SQLite home
(the queue rides the store's connection), and on the in-memory pair the queue transaction opens first and commits
last around the store and journal writes, a failure removing the rows the batch added. `declare_pending` on a field
already pending with no live task re-arms it; on a healthy record it stays idempotent. Every case runs on both
substrate pairs.

MUTATION LIST (scratch copy, each mutant run against this file and the queue/pending suites; all red, the source
restored byte-exact):
F1 the SQLite path queues its tasks after the commit; F2 the SQLite path appends a shared journal's bindings after the
commit; F3 the in-memory path keeps the batch's rows on failure; F4 the in-memory path commits its queue transaction
on failure; F5 remember_many back to store-then-enqueue; F6 declare_pending's repair removed (already_pending with no
task); F7 a healthy record re-armed on every declaration; F8 a summary no longer depends on its batch siblings'
rewrites; F9 `ack` keeps a failed attempt's error on the done task; F10 a write naming the task keeps it; F11 a write completing it unnamed keeps it.
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
)
from abstractmemory.memory_tasks import MemoryTaskQueue, task_id_for  # noqa: E402
from abstractmemory.records import apply_formation_plan, build_formation_plan, resolve_digest_assertion  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
LIVE = ("pending", "deferred", "leased")


class Embedder:
    model = "fake-hash-16"

    def embed_texts(self, texts):
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(16)
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
    system.kind = request.param
    yield system
    system.journal.close()
    system.store.close()


def _inputs(key: str) -> List[MemoryRecordInput]:
    return [MemoryRecordInput(kind="episode", title=None, digest=f"We talked about {key}.", pending=("title", "summary"))]


def _remember(system, key: str, records=None) -> List[str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return system.remember_many(records or _inputs(key), scope=SCOPE, owner_id=OWNER, idempotency_key=key)


def _planned_ids(key: str, records=None) -> List[str]:
    return list(build_formation_plan(records or _inputs(key), scope=SCOPE, owner_id=OWNER,
                                     idempotency_key=key).record_ids)


def _nothing_of(system, gids: List[str]) -> None:
    for gid in gids:
        assert resolve_digest_assertion(system.store, gid) is None
        assert system.journal.bindings(record_id=gid, fold=False) == []
        assert system.tasks.tasks(target_id=gid) == []


def _live(system, gid: str) -> Dict[str, str]:
    return {t["kind"]: t["task_id"] for t in system.tasks.tasks(target_id=gid) if t["status"] in LIVE}


def test_a_failed_enqueue_persists_nothing_and_a_retry_forms_whole(home, monkeypatch) -> None:
    gids = _planned_ids("enq-fail")
    real = MemoryTaskQueue.enqueue
    calls = {"n": 0}

    def flaky(self, kind, *a, **kw):
        calls["n"] += 1
        if kind == "digest.author":     # the record's second task: the first was already written
            raise RuntimeError("injected enqueue failure")
        return real(self, kind, *a, **kw)

    monkeypatch.setattr(MemoryTaskQueue, "enqueue", flaky)
    with pytest.raises(RuntimeError, match="injected enqueue failure"):
        _remember(home, "enq-fail")
    assert calls["n"] == 2
    _nothing_of(home, gids)
    monkeypatch.setattr(MemoryTaskQueue, "enqueue", real)
    assert _remember(home, "enq-fail") == gids
    [gid] = gids
    assert sorted(_live(home, gid)) == ["digest.author", "title.author"]
    assert resolve_digest_assertion(home.store, gid).attributes["pending"]["title"] is True
    assert len(home.journal.bindings(record_id=gid, fold=False)) == 1


def test_a_failed_binding_persists_neither_the_record_nor_its_tasks(home, monkeypatch) -> None:
    gids = _planned_ids("bind-fail")

    def boom(*_a, **_kw):
        raise RuntimeError("injected binding failure")

    if home.kind == "sqlite":
        monkeypatch.setattr(home.journal, "_append_binding_on", boom)
    else:
        monkeypatch.setattr(home.journal, "append_binding", boom)
    with pytest.raises(RuntimeError, match="injected binding failure"):
        _remember(home, "bind-fail")
    monkeypatch.undo()
    _nothing_of(home, gids)
    assert _remember(home, "bind-fail") == gids and len(_live(home, gids[0])) == 2


def test_a_failed_store_write_queues_nothing(home, monkeypatch) -> None:
    gids = _planned_ids("store-fail")

    def boom(*_a, **_kw):
        raise RuntimeError("injected store failure")

    monkeypatch.setattr(home.store, "_insert_rows_on" if home.kind == "sqlite" else "_insert_prepared", boom)
    with pytest.raises(RuntimeError, match="injected store failure"):
        _remember(home, "store-fail")
    monkeypatch.undo()
    _nothing_of(home, gids)


def test_a_replayed_formation_writes_nothing_twice(home) -> None:
    gids = _remember(home, "replay")
    tasks = home.tasks.tasks(target_id=gids[0])
    bindings = home.journal.bindings(record_id=gids[0], fold=False)
    assert _remember(home, "replay") == gids
    assert home.tasks.tasks(target_id=gids[0]) == tasks
    assert home.journal.bindings(record_id=gids[0], fold=False) == bindings
    assert len(home.store.query(__import__("abstractmemory").TripleQuery(subject=gids[0], limit=0))) == 1


def test_a_summary_depends_on_its_batch_siblings_rewrites(home) -> None:
    records = [
        MemoryRecordInput(kind="episode", title="First exchange", digest="We met at the archive.",
                          attributes={"digest_method": "mechanical-v2"}),
        MemoryRecordInput(kind="summary", title="The week", digest="A week at the archive.",
                          attributes={"digest_method": "mechanical-v2"}, edges=(("summarizes", "local:0"),)),
    ]
    ep, summary = _remember(home, "siblings", records)
    [rewrite] = [t for t in home.tasks.tasks(target_id=ep) if t["kind"] == "digest.rewrite"]
    [srewrite] = [t for t in home.tasks.tasks(target_id=summary) if t["kind"] == "digest.rewrite"]
    assert srewrite["depends_on"] == [rewrite["task_id"]]
    assert srewrite["cost_hint"]["input_tokens"] > rewrite["cost_hint"]["input_tokens"]


# --------------------------------------------------------------------------- declare_pending repairs


def _stored_without_tasks(system, key: str, fields=("title", "summary")) -> str:
    """The finding's state exactly: a pending record stored, its tasks never queued."""
    plan = build_formation_plan(
        [MemoryRecordInput(kind="episode", title=None if "title" in fields else f"Exchange {key}",
                           digest=f"We talked about {key}.", pending=tuple(fields))],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = apply_formation_plan(system.store, system.journal, plan)
    assert system.tasks.tasks(target_id=gid) == []
    return gid


def test_a_repeated_declaration_repairs_a_pending_record_with_no_task(home) -> None:
    gid = _stored_without_tasks(home, "orphan")
    aid = str(resolve_digest_assertion(home.store, gid).assertion_id)
    out = home.declare_pending(gid)
    assert out["applied"] is True and out["outcome"] == "rearmed" and out["declared"] == []
    assert out["already_pending"] == ["title", "summary"] and out["repaired"] == ["summary", "title"]
    assert all(out["tasks"].values())
    live = _live(home, gid)
    assert live == {"title.author": out["tasks"]["title"], "digest.author": out["tasks"]["summary"]}
    # The formation identity was free (never queued): the repair takes it.
    assert live["title.author"] == task_id_for("title.author", gid, f"{aid}@pending-title")
    # Healthy now: a further declaration is idempotent, nothing written or queued.
    snap = (home.tasks.tasks(target_id=gid), home.versions(gid, field="pending"))
    again = home.declare_pending(gid)
    assert again["outcome"] == "unchanged" and again["reason"] == "already_pending"
    assert again["tasks"] == {"title": live["title.author"], "summary": live["digest.author"]}
    assert (home.tasks.tasks(target_id=gid), home.versions(gid, field="pending")) == snap


def test_a_declaration_beside_an_orphan_field_repairs_it_in_the_same_write(home) -> None:
    gid = _stored_without_tasks(home, "half", fields=("title",))
    out = home.declare_pending(gid, fields=("title", "summary"))
    assert out["outcome"] == "applied" and out["declared"] == ["summary"] and out["repaired"] == ["title"]
    assert sorted(out["tasks"]) == ["summary", "title"] and all(out["tasks"].values())
    assert sorted(_live(home, gid)) == ["digest.author", "title.author"]
    [decl] = home.versions(gid, field="pending")
    assert decl["cause"]["repaired"] == ["title"] and decl["cause"]["tasks"] == out["tasks"]


# --------------------------------------------------------------------------- a done task carries no stale error


def test_a_completed_task_carries_no_earlier_failure_but_its_log_does(home) -> None:
    gid, other = _remember(home, "err-ack")[0], _remember(home, "err-rewrite")[0]
    for target in (gid, other):
        tid = _live(home, target)["title.author"]
        home.tasks.claim([tid], holder="rt")
        home.tasks.release(tid, holder="rt", outcome="retry", reason="TypeError: bad schema")
        assert home.tasks.task(tid)["error"] == "TypeError: bad schema"
        home.tasks.claim([tid], holder="rt")
    # Settled by the host's ack.
    tid = _live(home, gid)["title.author"]
    assert home.tasks.ack(tid, holder="rt", result={"outcome": "written"})["acked"] is True
    assert home.tasks.task(tid)["status"] == "done" and home.tasks.task(tid)["error"] is None
    retry = [e for e in home.tasks.log(tid) if e["event"] == "retry"]
    assert [e["detail"]["reason"] for e in retry] == ["TypeError: bad schema"]
    # Settled by the write that names it (retitle with task_id).
    tid = _live(home, other)["title.author"]
    out = home.retitle(other, title="An exchange about errors", author={"kind": "capability-model", "id": "summaries"},
                       reader={"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False},
                       sources=[{"kind": "artifact", "artifact_id": "authoring-call-1"}], cause="formation",
                       expected_version=0, task_id=tid)
    assert out["applied"] is True
    assert home.tasks.task(tid)["status"] == "done" and home.tasks.task(tid)["error"] is None
    assert [e["detail"]["reason"] for e in home.tasks.log(tid) if e["event"] == "retry"] == ["TypeError: bad schema"]
    # Completed by a write that does not name it (the pending summary written; its live task is done).
    tid = _live(home, other)["digest.author"]
    home.tasks.claim([tid], holder="rt")
    home.tasks.release(tid, holder="rt", outcome="retry", reason="TimeoutError: model")
    out = home.rewrite_digest(other, text="We talked about errors and how they read.",
                              author={"kind": "capability-model", "id": "summaries"},
                              reader={"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False},
                              sources=[{"kind": "artifact", "artifact_id": "authoring-call-2"}], cause="formation",
                              expected_version=0)
    assert out["applied"] is True and out["pending_cleared"] == ["summary"]
    assert home.tasks.task(tid)["status"] == "done" and home.tasks.task(tid)["error"] is None
    assert [e["detail"]["reason"] for e in home.tasks.log(tid) if e["event"] == "retry"] == ["TimeoutError: model"]
