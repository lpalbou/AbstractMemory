"""Formation racing other writers on one home (Codex review 3, 2026-11-09).

Finding 4: on the in-memory pair the store and its task queue had TWO locks taken in opposite orders: formation
(`memory_tasks.form_with_tasks`) held the queue's lock and then took the store's (`store.add`), a rewrite
(`understanding._apply`) held the store's and its task hook (`on_rewrite`) took the queue's. A formation racing a
rewrite deadlocked. The queue over an `InMemoryTripleStore` now takes the store's own reentrant lock: one
transaction lock for store and queue on both substrate pairs (the SQLite home's queue always rode the store's).

The race is forced, not hoped for: each side waits at a barrier at the exact point where it holds its first lock and
is about to take the second. With two locks both arrive and deadlock; with one lock the second side cannot reach the
barrier until the first is done (the barrier then times out and both finish). A deadlock fails the test through a
join timeout on daemon threads, never hangs the run. Every case runs on both substrate pairs.

MUTATION LIST (scratch copy, each mutant run against this file; all red, the source restored byte-exact):
L1 the in-memory queue back on its own private RLock.
"""

from __future__ import annotations

import hashlib
import threading
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
from abstractmemory import memory_tasks  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "artifact", "artifact_id": "authoring-call-1"}]
JOIN_SECONDS = 10.0


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


def _inputs(text: str, n: int = 1) -> List[MemoryRecordInput]:
    return [MemoryRecordInput(kind="episode", title=None, digest=f"{text} {i}.", pending=("title", "summary"))
            for i in range(n)]


def _remember(system, key: str, records=None) -> List[str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return system.remember_many(records or _inputs(key), scope=SCOPE, owner_id=OWNER, idempotency_key=key)


def _run(*targets) -> List[threading.Thread]:
    threads = [threading.Thread(target=t, daemon=True) for t in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join(JOIN_SECONDS)
    return threads


def test_the_store_and_its_queue_share_one_transaction_lock(home) -> None:
    assert home.tasks._lock is home.store._lock


def test_a_formation_racing_a_rewrite_completes(home, monkeypatch) -> None:
    [gid] = _remember(home, "first")
    barrier = threading.Barrier(2)

    def meet() -> None:
        try:
            barrier.wait(timeout=1.0)
        except threading.BrokenBarrierError:
            pass

    real_enqueue, real_on_rewrite = memory_tasks._enqueue_planned, home.tasks.on_rewrite

    def enqueue_planned(*a, **kw):  # formation holds its first lock here; the store's rows come next
        meet()
        return real_enqueue(*a, **kw)

    def on_rewrite(*a, **kw):  # the rewrite holds the store's lock here; the queue's write comes next
        meet()
        return real_on_rewrite(*a, **kw)

    monkeypatch.setattr(memory_tasks, "_enqueue_planned", enqueue_planned)
    monkeypatch.setattr(home.tasks, "on_rewrite", on_rewrite)
    out: Dict[str, Any] = {}

    def form() -> None:
        out["form"] = _remember(home, "second", _inputs("Another talk"))

    def rewrite() -> None:
        out["rewrite"] = home.rewrite_digest(gid, text="We talked about the archive.", author=MODEL, reader=READER,
                                             sources=STEP, cause="formation", expected_version=0)

    threads = _run(form, rewrite)
    assert not any(t.is_alive() for t in threads), "formation and rewrite deadlocked"
    assert out["rewrite"]["applied"] is True and out["rewrite"]["pending_cleared"] == ["summary"]
    [other] = out["form"]
    assert sorted(t["kind"] for t in home.tasks.tasks(target_id=other)) == ["digest.author", "title.author"]

