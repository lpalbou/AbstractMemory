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

Finding 3: on the in-memory pair formation read which rows were missing BEFORE it took its lock and, when a later
write failed, removed every one of them, even those this attempt never inserted: a writer that lost the race to
another writer of the same record and then failed deleted the winner's record (its tasks and binding stayed). A failing
second binding of a two-record batch left the first binding behind. Now the rows this attempt inserted are decided
inside the lock (`InMemoryTripleStore._insert_prepared`), the bindings it stored are tracked
(`InMemoryJournal._append_binding_tracked`; a SQLite journal appends the batch's bindings in one transaction), and a
failure undoes exactly those, its tasks rolled back with the queue transaction; the in-memory seq axis stays gap-free.

MUTATION LIST (scratch copy, each mutant run against this file; all red, the source restored byte-exact):
L1 the in-memory queue back on its own private RLock; R1 the rollback removes every row read missing before the lock;
R2 the batch's own bindings never undone; R3 a replayed (another writer's) binding undone too; R4 the seq axis not
rewound; R5 a SQLite journal's bindings appended one transaction each.
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
from abstractmemory.records import build_formation_plan, resolve_digest_assertion  # noqa: E402

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


@pytest.fixture(params=["memory", "sqlite", "mixed"])
def home(request, tmp_path):
    """The two substrate pairs, plus an in-memory store over a SQLite journal (formation's in-memory branch with a
    journal that has transactions)."""
    emb = Embedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if request.param == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        elif request.param == "mixed":
            store, journal = InMemoryTripleStore(embedder=emb), SQLiteJournal(tmp_path / "journal.sqlite3")
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



def _plan(key: str, records=None):
    return build_formation_plan(records or _inputs(key), scope=SCOPE, owner_id=OWNER, idempotency_key=key)


def _state(system, gids: List[str]) -> Dict[str, Dict[str, Any]]:
    return {g: {"record": resolve_digest_assertion(system.store, g) is not None,
                "bindings": len(system.journal.bindings(record_id=g, fold=False)),
                "tasks": sorted(t["kind"] for t in system.tasks.tasks(target_id=g))} for g in gids}


WHOLE = {"record": True, "bindings": 1, "tasks": ["digest.author", "title.author"]}
NOTHING = {"record": False, "bindings": 0, "tasks": []}


def _fail_bindings(system, monkeypatch, failing) -> None:
    """Make the binding append raise when `failing()` says so, on whichever path the pair takes."""
    if system.kind == "memory":
        real = system.journal.append_binding

        def append_binding(b, *a, **kw):
            if failing():
                raise RuntimeError("injected binding failure")
            return real(b, *a, **kw)

        monkeypatch.setattr(system.journal, "append_binding", append_binding)
    else:
        real_on = system.journal._append_binding_on

        def append_binding_on(cur, b, *a, **kw):
            if failing():
                raise RuntimeError("injected binding failure")
            return real_on(cur, b, *a, **kw)

        monkeypatch.setattr(system.journal, "_append_binding_on", append_binding_on)


def _pause_after_existence_read(system, monkeypatch, key: str, who: str, gate: threading.Event,
                                arrived: threading.Barrier, records=None) -> None:
    """The writer named `who` reads which rows are missing, then waits for `gate` before it takes its lock."""
    wanted = set(_plan(key, records).assertion_ids)
    real = system.store.query

    def query(q):
        out = real(q)
        if threading.current_thread().name == who and q.assertion_ids and set(q.assertion_ids) == wanted:
            arrived.wait(timeout=JOIN_SECONDS)
            gate.wait(timeout=JOIN_SECONDS)
        return out

    monkeypatch.setattr(system.store, "query", query)


def test_a_losing_writer_that_fails_never_removes_the_winners_records(home, monkeypatch) -> None:
    """Two writers of one two-record batch: the loser reads every row missing, the winner forms the whole batch, then
    the loser runs: its rows are all stored already, its first binding is the winner's (a replay) and its second
    binding fails. It must undo nothing of the winner's: rows, bindings and tasks stay whole."""
    records = _inputs("same", 2)
    gids = list(_plan("same", records).record_ids)
    winner_done = threading.Event()
    arrived = threading.Barrier(2)
    _pause_after_existence_read(home, monkeypatch, "same", "loser", winner_done, arrived, records)
    loser_binds = {"n": 0}

    def losers_second_binding() -> bool:
        if threading.current_thread().name != "loser":
            return False
        loser_binds["n"] += 1
        return loser_binds["n"] == 2

    _fail_bindings(home, monkeypatch, losers_second_binding)
    out: Dict[str, Any] = {}

    def lose() -> None:
        try:
            out["loser"] = _remember(home, "same", records)
        except RuntimeError as exc:
            out["loser"] = exc

    def win() -> None:
        arrived.wait(timeout=JOIN_SECONDS)   # the loser has read every row missing
        try:
            out["winner"] = _remember(home, "same", records)
        finally:
            winner_done.set()

    loser = threading.Thread(target=lose, name="loser", daemon=True)
    winner = threading.Thread(target=win, name="winner", daemon=True)
    loser.start()
    winner.start()
    for t in (winner, loser):
        t.join(JOIN_SECONDS)
    assert not loser.is_alive() and not winner.is_alive()
    assert out["winner"] == gids
    assert isinstance(out["loser"], RuntimeError) and "injected binding failure" in str(out["loser"])
    assert loser_binds["n"] == 2
    assert _state(home, gids) == {g: WHOLE for g in gids}


def test_two_writers_of_one_record_form_it_once(home, monkeypatch) -> None:
    gids = list(_plan("twice").record_ids)
    both = threading.Barrier(2)
    real = home.store.query
    wanted = set(_plan("twice").assertion_ids)

    def query(q):
        out = real(q)
        if q.assertion_ids and set(q.assertion_ids) == wanted:
            try:
                both.wait(timeout=2.0)   # both writers read every row missing before either takes its lock
            except threading.BrokenBarrierError:
                pass
        return out

    monkeypatch.setattr(home.store, "query", query)
    out: Dict[str, Any] = {}
    threads = _run(lambda: out.__setitem__("a", _remember(home, "twice")),
                   lambda: out.__setitem__("b", _remember(home, "twice")))
    assert not any(t.is_alive() for t in threads)
    assert out["a"] == out["b"] == gids
    assert _state(home, gids) == {gids[0]: WHOLE}
    assert len(home.tasks.tasks()) == 2


def test_a_batch_whose_second_binding_fails_persists_nothing(home, monkeypatch) -> None:
    records = _inputs("batch", 2)
    gids = list(_plan("batch", records).record_ids)
    seq0 = home.journal.current_seq()
    n = {"i": 0}

    def second() -> bool:
        n["i"] += 1
        return n["i"] == 2

    _fail_bindings(home, monkeypatch, second)
    with pytest.raises(RuntimeError, match="injected binding failure"):
        _remember(home, "batch", records)
    assert n["i"] == 2
    assert _state(home, gids) == {g: NOTHING for g in gids}
    assert home.journal.current_seq() == seq0   # no hole in the seq axis
    monkeypatch.undo()
    assert _remember(home, "batch", records) == gids
    assert _state(home, gids) == {g: WHOLE for g in gids}
    assert home.journal.current_seq() == seq0 + 2
