"""The write barrier (the bumper's half of the Stop fence): `MemorySystem.write_barrier()` / `write_barrier(system)`.

The commit guard runs INSIDE every write transaction; the runtime bumps its lifecycle generation under its own home
lock. Without the barrier "guard passes -> another process bumps -> COMMIT lands" is a real interleaving (Codex review
4, finding 2). The runtime wraps its bump: home_state_lock -> write_barrier() -> write the generation -> release.
Pinned here:

- a writer whose guard PASSED and that pauses before its COMMIT makes the barrier WAIT until that COMMIT, whether the
  barrier is taken by another thread of the same handle, another handle of this process (SQLite file lock), or
  another PROCESS on the same SQLite file (both directions); the block then sees the commit, and after the bump the
  next guard check refuses: the formation, a journal append, a store add, a task-queue write, a graph revision, on the
  in-memory pair, the SQLite one-file home and the SQLite off-file journal;
- the fixed order: the barrier follows the writers' nesting (store/queue lock, then the journal's), so it never
  deadlocks with a real in-memory formation; racing barriers on two handles of one file, mixed with writers, never
  deadlock and never overlap;
- re-entrant within one thread (same handle, and another handle over a file the thread already holds); refused
  inside a memory write transaction of its own thread (it would wait for itself);
- the timeout: `WriteBarrierTimeout` names the lock a writer still holds (in-process lock, cross-process file lock),
  and everything acquired is released (locks free, no open transaction, busy_timeout restored);
- zero effect on the hot path: the guard's counters are unchanged by any number of barriers, the barrier leaves no
  attribute behind, and no module of the package but `system.py` (the method) references it;
- LanceDB is not coverable: named in `BarrierHold.uncovered` with a `#FALLBACK` warning, and its documented window
  pinned (a LanceDB write paused after its guard does not hold the barrier and lands after the bump; the next one is
  refused).

MUTATION LIST (in-process: a scratch pytest plugin monkeypatches `abstractmemory.write_barrier` for one run; no
tracked file copied or edited; the subprocess children run the real barrier), each red (2026-11-10):
- B1 the barrier takes no lock at all (`_plan` -> nothing)       -> 28 red: every waits case, the other-handle and
                                                                   writer-in-another-process cases, the lock order,
                                                                   racing, nested, own-thread, timeout, LanceDB
- B2 in-process locks only, no BEGIN IMMEDIATE                     -> 9 red: other-handle (2), writer in another
                                                                   process, racing (2 SQLite), nested (2), own-thread,
                                                                   LanceDB
- B3 the lock order reversed (journal before store)                -> 17 red: test_the_barrier_follows_the_writers_lock_
                                                                   order, racing[memory] (deadlock), the hold order (15)
- B4 no per-thread re-entry (every barrier BEGINs)                 -> 2 red: test_a_nested_barrier_reenters[sqlite*]
- B5 the deadline ignored on the file lock                         -> 3 red: writer in another process, nested (2)
- B6 the deadline ignored on the in-process locks                  -> 2 red: test_the_timeout_names_the_lock_and_
                                                                   releases[*]
- B7 no ROLLBACK on exit (the in-process locks released)           -> 19 red: every SQLite case
"""

from __future__ import annotations

import ast
import os
import queue as queue_mod
import subprocess
import sys
import threading
import time
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pytest

import abstractmemory
from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryGraph,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    TripleAssertion,
    WriteBarrierTimeout,
    write_barrier,
)

from graph_support import claim, file_state, rev

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
SRC = Path(abstractmemory.__file__).resolve().parent
WAIT = 0.4  # how long a waiting barrier must stay out of its block


class Refused(Exception):
    """Stands for the host's StoppedByOperator."""


class Fence:
    """The runtime's shape: an int captured at admission, compared with the current one."""

    def __init__(self) -> None:
        self.generation = self.admitted = 7
        self.calls = 0

    def current(self) -> int:
        return self.generation

    def check(self, where: str) -> None:
        self.calls += 1
        if self.current() != self.admitted:
            raise Refused(f"stopped by the operator ({where})")

    def bump(self) -> None:
        self.generation += 1


class FileFence(Fence):
    """A non-bumper process's fence: the generation another process writes to a file (the runtime's stat refresh)."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        path.write_text("7")

    def current(self) -> int:
        return int(self.path.read_text())


#: Every pause of the running test: released at teardown, so a failing case never leaves a writer parked on a lock.
_PAUSES: list = []


def _release_pauses() -> None:
    for pause in _PAUSES:
        pause.armed = None
        pause.go.set()
    _PAUSES.clear()


@pytest.fixture(autouse=True)
def _no_parked_writer():
    yield
    _release_pauses()


class Pause:
    """The commit guard: the fence's check, then, once armed for a commit point, a pause BEFORE returning, i.e.
    after the guard passed and before the COMMIT."""

    def __init__(self, fence: Fence) -> None:
        self.fence = fence
        self.armed: Optional[str] = None
        self.passed, self.go = threading.Event(), threading.Event()
        _PAUSES.append(self)

    def arm(self, where: str) -> None:
        self.armed = where
        self.passed.clear()
        self.go.clear()

    def __call__(self, where: str) -> None:
        self.fence.check(where)
        if self.armed is not None and where == self.armed:
            self.armed = None
            self.passed.set()
            assert self.go.wait(20), "the paused writer was never released"


class Worker(threading.Thread):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__(daemon=True)
        self.fn, self.error, self.result = fn, None, None

    def run(self) -> None:
        try:
            self.result = self.fn()
        except BaseException as exc:  # noqa: BLE001 - inspected by the test
            self.error = exc


class Home:
    def __init__(self, kind: str, system: MemorySystem, fence: Fence, pause: Pause,
                 path: Optional[Path], journal_path: Optional[Path]) -> None:
        self.kind, self.system, self.fence, self.pause = kind, system, fence, pause
        self.path, self.journal_path = path, journal_path


def _open(kind: str, tmp_path: Path, *, fence: Optional[Fence] = None, name: str = "home") -> Home:
    fence = fence or Fence()
    pause = Pause(fence)
    path = journal_path = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if kind == "memory":
            store, journal = InMemoryTripleStore(), InMemoryJournal()
        else:
            path = tmp_path / f"{name}.sqlite3"
            journal_path = path if kind == "sqlite" else tmp_path / f"{name}-journal.sqlite3"
            store, journal = SQLiteTripleStore(path), SQLiteJournal(journal_path)
        system = MemorySystem(store=store, journal=journal, task_queue=True, commit_guard=pause)
    return Home(kind, system, fence, pause, path, journal_path)


def _handle(h: Home) -> MemorySystem:
    """A second handle on the same files (the gateway's other open of one home): its own locks and connections."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return MemorySystem(store=SQLiteTripleStore(h.path), journal=SQLiteJournal(h.journal_path), task_queue=True)


@pytest.fixture(params=["memory", "sqlite", "sqlite-offfile"])
def home(request, tmp_path):
    h = _open(request.param, tmp_path)
    yield h
    _release_pauses()
    h.system.journal.close()
    h.system.store.close()


def snapshot(h: Home) -> Any:
    """What the home has COMMITTED: every row of its SQLite files read through a fresh connection, or the in-memory
    store rows, journal sequence, queue database and graph revisions."""
    if h.kind == "memory":
        from abstractmemory.graph.graph import _MEMORY_BACKENDS

        s, j, q = h.system.store, h.system.journal, h.system.tasks
        backend = _MEMORY_BACKENDS.get(s)
        return (len(s._rows), j._seq, tuple(q._conn.iterdump()), len(backend.revisions) if backend else 0)
    out = {"file": file_state(h.path)}
    if h.journal_path != h.path:
        out["journal"] = file_state(h.journal_path)
    return out


def _quiet(fn: Callable[[], Any]) -> Any:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return fn()


def _form(system: MemorySystem, key: str) -> Any:
    return _quiet(lambda: system.remember_many(
        [MemoryRecordInput(kind="episode", title="A talk at the archive", digest="We talked about the archive.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key))


def _row(key: str) -> TripleAssertion:
    return TripleAssertion(subject=f"ex:{key}", predicate="schema:worksFor", object="ex:acme", scope=SCOPE,
                           owner_id=OWNER, observed_at="2026-11-10T00:00:00+00:00", assertion_id=f"a-{key}")


#: writer -> (write(system, key), the commit point its guard is called at)
WRITERS: Dict[str, Any] = {
    "formation": (_form, "tasks.form_with_tasks"),
    "journal": (lambda s, k: s.bind(f"rec-{k}", scope=SCOPE, owner_id=OWNER, search_state="hidden"), "journal"),
    "store": (lambda s, k: s.add([_row(k)]), "store.add"),
    "tasks": (lambda s, k: s.tasks.record_maintenance(SCOPES, kind=f"night-{k}", completed_at="2026-11-10T03:00:00Z",
                                                      seq=1), "tasks.record_maintenance"),
    "graph": (lambda s, k: MemoryGraph(s.store, s.journal).apply_revision(rev(f"r-{k}", claim(f"ex:g-{k}"))), "graph"),
}


def _released(h: Home) -> None:
    """Nothing of a barrier left behind: no open transaction, the connections' busy_timeout back to 5000 ms, every
    lock free for another thread."""
    s, j = h.system.store, h.system.journal
    for part in (s, j):
        conn = getattr(part, "_conn", None)
        if conn is not None:
            assert not conn.in_transaction
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    for lock in (s._lock, j._lock, h.system.tasks._lock):
        got = []
        t = threading.Thread(target=lambda lk=lock: got.append(lk.acquire(timeout=2) and (lk.release() or True)))
        t.start()
        t.join(5)
        assert got == [True], "a lock is still held after the barrier"


# ------------------------------------------------------------------- the barrier waits for a guard that passed


@pytest.mark.parametrize("writer", sorted(WRITERS))
def test_the_barrier_waits_for_the_commit_whose_guard_passed(home, writer) -> None:
    write, where = WRITERS[writer]
    if writer == "graph":
        MemoryGraph(home.system.store, home.system.journal)  # the graph tables exist before the measured write
    before = snapshot(home)
    home.pause.arm(where)
    w = Worker(lambda: write(home.system, "w1"))
    w.start()
    assert home.pause.passed.wait(10), "the writer never reached its guard"
    entered, seen = threading.Event(), {}

    def bump() -> None:
        with home.system.write_barrier() as hold:
            entered.set()
            seen["inside"], seen["hold"] = snapshot(home), hold
            home.fence.bump()

    b = Worker(bump)
    b.start()
    assert not entered.wait(WAIT), "the barrier ran while a COMMIT whose guard passed was pending"
    home.pause.go.set()
    w.join(10)
    b.join(10)
    assert not b.is_alive() and b.error is None, b.error
    assert not w.is_alive()
    # The paused COMMIT landed. Off-file only: formation's bindings are a later transaction of their own, which
    # waited behind the barrier and was refused by the bump (its records committed first).
    assert w.error is None or (home.kind == "sqlite-offfile" and writer == "formation" and isinstance(w.error, Refused))
    assert seen["inside"] != before, "the block ran before the paused COMMIT landed"
    assert seen["hold"].locks[:1] == ("store",) and seen["hold"].locks[-1] == "journal"
    _released(home)
    after = snapshot(home)
    with pytest.raises(Refused):  # the bump happened under the barrier: the next guard check refuses
        write(home.system, "w2")
    assert snapshot(home) == after


@pytest.mark.parametrize("kind", ["sqlite", "sqlite-offfile"])
def test_a_barrier_on_another_handle_waits_through_the_file_lock(kind, tmp_path) -> None:
    """The gateway may hold two handles of one home: the barrier on the second one shares no Python lock with the
    writer, only the SQLite write lock (BEGIN IMMEDIATE)."""
    h = _open(kind, tmp_path)
    other = _handle(h)
    for writer in ("store", "journal"):
        write, where = WRITERS[writer]
        before = snapshot(h)
        h.pause.arm(where)
        w = Worker(lambda: write(h.system, f"{writer}-1"))
        w.start()
        assert h.pause.passed.wait(10)
        entered, seen = threading.Event(), {}

        def bump() -> None:
            with write_barrier(other) as hold:  # the module-level form
                entered.set()
                seen["inside"], seen["hold"] = snapshot(h), hold

        b = Worker(bump)
        b.start()
        assert not entered.wait(WAIT), f"{writer}: the other handle's barrier ignored the file's write lock"
        h.pause.go.set()
        w.join(10)
        b.join(10)
        assert w.error is None and b.error is None, (w.error, b.error)
        assert seen["inside"] != before
        assert len(seen["hold"].files) == (1 if kind == "sqlite" else 2)
    h.fence.bump()
    with pytest.raises(Refused):
        WRITERS["store"][0](h.system, "after")


_CHILD_BARRIER = r"""
import sqlite3, sys, warnings
warnings.simplefilter("ignore")
from abstractmemory import MemorySystem, SQLiteJournal, SQLiteTripleStore
path, gen_file = sys.argv[1], sys.argv[2]
system = MemorySystem(store=SQLiteTripleStore(path), journal=SQLiteJournal(path))
print("ready", flush=True)
sys.stdin.readline()
with system.write_barrier(timeout=30):
    seen = sqlite3.connect(f"file:{path}?mode=ro", uri=True).execute("SELECT COUNT(*) FROM triples").fetchone()[0]
    print(f"acquired {seen}", flush=True)
    with open(gen_file, "w") as f:
        f.write("8")
print("released", flush=True)
"""

_CHILD_WRITER = r"""
import sys, warnings
warnings.simplefilter("ignore")
from abstractmemory import MemorySystem, SQLiteJournal, SQLiteTripleStore, TripleAssertion
path = sys.argv[1]

def guard(where):
    print(f"passed {where}", flush=True)
    sys.stdin.readline()

system = MemorySystem(store=SQLiteTripleStore(path), journal=SQLiteJournal(path), commit_guard=guard)
print("ready", flush=True)
system.add([TripleAssertion(subject="ex:child", predicate="schema:worksFor", object="ex:acme", scope="life",
                            owner_id="entity:nerin", observed_at="2026-11-10T00:00:00+00:00", assertion_id="a-child")])
print("committed", flush=True)
"""


def _child(code: str, *args: str) -> Any:
    env = dict(os.environ, PYTHONPATH=str(SRC.parent))
    proc = subprocess.Popen([sys.executable, "-c", code, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env)
    lines: "queue_mod.Queue[str]" = queue_mod.Queue()
    threading.Thread(target=lambda: [lines.put(line.strip()) for line in proc.stdout], daemon=True).start()
    return proc, lines


def _next(lines: Any, timeout: float = 20.0) -> Optional[str]:
    try:
        return lines.get(timeout=timeout)
    except queue_mod.Empty:
        return None


def _say(proc: Any, text: str = "go") -> None:
    proc.stdin.write(text + "\n")
    proc.stdin.flush()


def test_a_barrier_in_another_process_waits_for_the_commit(tmp_path) -> None:
    """The writer here passed its guard and pauses before COMMIT; the barrier is taken by another process on the same
    file: it waits for that COMMIT, sees it, bumps (the generation file), and the next write here is refused."""
    gen_file = tmp_path / "lifecycle_generation"
    h = _open("sqlite", tmp_path, fence=FileFence(gen_file))
    proc, lines = _child(_CHILD_BARRIER, str(h.path), str(gen_file))
    try:
        assert _next(lines) == "ready", proc.stderr.read() if proc.poll() is not None else "child silent"
        h.pause.arm("store.add")
        w = Worker(lambda: h.system.add([_row("parent")]))
        w.start()
        assert h.pause.passed.wait(10)
        _say(proc)  # the child takes the barrier now
        assert _next(lines, WAIT + 0.4) is None, "the other process's barrier did not wait for the pending COMMIT"
        h.pause.go.set()
        w.join(10)
        assert w.error is None
        assert _next(lines) == "acquired 1"  # the block saw the COMMIT
        assert _next(lines) == "released"
        assert proc.wait(20) == 0, proc.stderr.read()
    finally:
        h.pause.go.set()
        if proc.poll() is None:
            proc.kill()
    with pytest.raises(Refused):
        h.system.add([_row("after")])
    assert [r[0] for r in file_state(h.path)["triples"]] == ["a-parent"]


def test_a_writer_in_another_process_holds_the_barrier_and_the_timeout_names_it(tmp_path) -> None:
    """The writer is another process, paused after its guard: the barrier here times out with a typed error naming
    the file, releases everything, and once the writer commits, the barrier is taken and sees the row."""
    h = _open("sqlite", tmp_path)
    proc, lines = _child(_CHILD_WRITER, str(h.path))
    try:
        assert _next(lines) == "ready", proc.stderr.read() if proc.poll() is not None else "child silent"
        assert _next(lines) == "passed store.add"
        b = Worker(lambda: h.system.write_barrier(timeout=0.5).__enter__())
        t0 = time.monotonic()
        b.start()
        b.join(8)
        elapsed = time.monotonic() - t0
        assert not b.is_alive(), "the barrier's timeout was not honoured on the file lock"
        assert isinstance(b.error, WriteBarrierTimeout), b.error
        assert str(h.path.resolve()) in b.error.waiting_for and b.error.timeout == 0.5
        assert 0.45 <= elapsed < 5
        _released(h)
        _say(proc)
        with h.system.write_barrier(timeout=20):
            rows = file_state(h.path)["triples"]
        assert [r[0] for r in rows] == ["a-child"]
        assert _next(lines) == "committed"
        assert proc.wait(20) == 0, proc.stderr.read()
    finally:
        if proc.poll() is None:
            proc.kill()
    _released(h)


# ------------------------------------------------------------------------------------------------ the fixed order


class GatedLock:
    """The journal's lock, gated once: when the writer thread asks for it while holding the store's lock (the
    formation's `with queue._lock, journal._lock`), the barrier is let in first."""

    def __init__(self, inner: Any, store_lock: Any, writer: threading.Thread, barrier_started: threading.Event):
        self.inner, self.store_lock, self.writer, self.barrier_started = inner, store_lock, writer, barrier_started
        self.holding_store = threading.Event()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        if (threading.current_thread() is self.writer and not self.holding_store.is_set()
                and self.store_lock._is_owned()):
            self.holding_store.set()
            assert self.barrier_started.wait(10)
            time.sleep(0.3)  # the barrier is asking for its first lock now
        return self.inner.acquire(blocking, timeout)

    def release(self) -> None:
        self.inner.release()

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *exc: Any) -> None:
        self.release()


def test_the_barrier_follows_the_writers_lock_order(tmp_path) -> None:
    """A real in-memory formation holds the store's (queue's) lock and then asks for the journal's: a barrier taking
    the journal's lock first would deadlock with it (here: time out). The fixed order is the writers' own."""
    h = _open("memory", tmp_path)
    journal = h.system.journal
    before = snapshot(h)
    barrier_started, seen = threading.Event(), {}
    w = Worker(lambda: _form(h.system, "ordered"))
    journal._lock = GatedLock(journal._lock, h.system.store._lock, w, barrier_started)
    try:
        w.start()
        assert journal._lock.holding_store.wait(10), "the formation never held the store's lock"

        def bump() -> None:
            barrier_started.set()
            with h.system.write_barrier(timeout=3):
                seen["inside"] = snapshot(h)

        b = Worker(bump)
        b.start()
        b.join(10)
        w.join(10)
        assert b.error is None, f"the barrier deadlocked with the formation: {b.error!r}"
        assert w.error is None
        assert seen["inside"] != before  # the formation committed first
    finally:
        journal._lock = journal._lock.inner


@pytest.mark.parametrize("kind", ["memory", "sqlite", "sqlite-offfile"])
def test_racing_barriers_and_writers_never_deadlock_or_overlap(kind, tmp_path) -> None:
    h = _open(kind, tmp_path)
    handles = [h.system] + ([_handle(h)] if kind != "memory" else [])
    inside, worst, count = [0], [0], threading.Lock()

    def barriers(i: int) -> None:
        for n in range(10):
            with handles[(i + n) % len(handles)].write_barrier(timeout=30):
                with count:
                    inside[0] += 1
                    worst[0] = max(worst[0], inside[0])
                time.sleep(0.001)
                with count:
                    inside[0] -= 1

    def writes(i: int) -> None:
        for n in range(8):
            _form(handles[(i + n) % len(handles)], f"race-{i}-{n}")

    workers = [Worker(lambda i=i: barriers(i)) for i in range(3)] + [Worker(lambda i=i: writes(i)) for i in range(2)]
    for t in workers:
        t.start()
    for t in workers:
        t.join(60)
    assert not any(t.is_alive() for t in workers), "a barrier or a writer deadlocked"
    assert [t.error for t in workers] == [None] * len(workers)
    assert worst[0] == 1, "two barriers over one home held at once"
    _released(h)


# --------------------------------------------------------------------------------------------- re-entrancy, misuse


@pytest.mark.parametrize("kind", ["memory", "sqlite", "sqlite-offfile"])
def test_a_nested_barrier_reenters(kind, tmp_path) -> None:
    h = _open(kind, tmp_path)
    other = _handle(h) if kind != "memory" else None
    with h.system.write_barrier(timeout=2) as outer:
        with h.system.write_barrier(timeout=2) as inner:
            assert inner.files == outer.files
        if other is not None:
            with other.write_barrier(timeout=2):  # another handle over a file this thread holds: not locked again
                pass
            if kind == "sqlite":
                assert h.system.store._conn.in_transaction  # the inner exits left the outer's lock in place
            probe = Worker(lambda: other.write_barrier(timeout=0.3).__enter__())
            probe.start()
            probe.join(5)
            assert isinstance(probe.error, WriteBarrierTimeout), "the outer barrier no longer holds the file"
    _released(h)
    if other is not None:
        with other.write_barrier(timeout=2):
            pass


def test_a_barrier_inside_a_write_of_its_own_thread_is_refused(tmp_path) -> None:
    h = _open("sqlite", tmp_path)
    calls = []

    def guard(where: str) -> None:
        calls.append(where)
        with h.system.write_barrier(timeout=1):
            pass

    h.pause.fence.check = guard  # the guard runs inside the store's transaction
    with pytest.raises(RuntimeError, match="inside a memory write transaction"):
        h.system.add([_row("self")])
    assert calls == ["store.add"]
    assert file_state(h.path)["triples"] == []
    _released(h)


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_the_timeout_names_the_lock_and_releases(kind, tmp_path) -> None:
    """A writer of this process paused inside its journal append holds the journal's lock: the barrier (store lock
    taken, journal lock awaited) times out, names the lock and gives the store's lock back."""
    h = _open(kind, tmp_path)
    h.pause.arm("journal")
    w = Worker(lambda: WRITERS["journal"][0](h.system, "held"))
    w.start()
    assert h.pause.passed.wait(10)
    try:
        b = Worker(lambda: h.system.write_barrier(timeout=0.3).__enter__())
        t0 = time.monotonic()
        b.start()
        b.join(5)
        assert not b.is_alive(), "the timeout was not honoured on an in-process lock"
        assert isinstance(b.error, WriteBarrierTimeout), b.error
        assert "journal lock" in b.error.waiting_for and b.error.timeout == 0.3
        assert 0.25 <= time.monotonic() - t0 < 4
        got = []
        t = threading.Thread(target=lambda: got.append(
            h.system.store._lock.acquire(timeout=2) and (h.system.store._lock.release() or True)))
        t.start()
        t.join(5)
        assert got == [True], "the store's lock stayed held after the timeout"
    finally:
        h.pause.go.set()
        w.join(10)
    assert w.error is None
    _released(h)
    with pytest.raises(ValueError):
        with h.system.write_barrier(timeout=-1):
            pass


# ------------------------------------------------------------------------------------------------- the hot path


def test_the_barrier_adds_nothing_to_the_hot_path(tmp_path) -> None:
    """Only the bumper pays: the guard is called once per write whatever the barriers did, a barrier calls no
    guard, leaves no attribute behind, and no writer module references the barrier."""
    for kind in ("memory", "sqlite"):
        h = _open(kind, tmp_path, name=kind)
        store, journal = h.system.store, h.system.journal
        attrs = (sorted(vars(store)), sorted(vars(journal)), sorted(vars(h.system.tasks)))
        guard_before = (store._commit_guard, journal._commit_guard)
        for i in range(20):
            _form(h.system, f"hot-{i}")
        assert h.fence.calls == 20
        for _ in range(25):
            with h.system.write_barrier():
                pass
        assert h.fence.calls == 20  # the barrier calls no guard and adds no call to a write
        for i in range(20):
            _form(h.system, f"hot-after-{i}")
        assert h.fence.calls == 40
        assert (sorted(vars(store)), sorted(vars(journal)), sorted(vars(h.system.tasks))) == attrs
        assert (store._commit_guard, journal._commit_guard) == guard_before
        _released(h)
    referencing = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel in ("write_barrier.py", "__init__.py"):
            continue
        names = {n.id for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Name)}
        names |= {n.module or "" for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.ImportFrom)}
        if {"write_barrier", "_write_barrier"} & names or any(m.endswith("write_barrier") for m in names):
            referencing.append(rel)
    assert referencing == ["system.py"], f"a writer references the barrier: {referencing}"


# -------------------------------------------------------------------------------------------- LanceDB: the window


def test_a_lancedb_store_is_uncovered_and_its_window_is_one_write(tmp_path) -> None:
    pytest.importorskip("lancedb")
    from abstractmemory import LanceDBTripleStore

    fence = Fence()
    pause = Pause(fence)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        store = LanceDBTripleStore(tmp_path / "lance")
    journal_path = tmp_path / "journal.sqlite3"
    system = MemorySystem(store=store, journal=SQLiteJournal(journal_path), commit_guard=pause)
    with pytest.warns(RuntimeWarning, match="#FALLBACK: write_barrier cannot hold store: LanceDBTripleStore"):
        with system.write_barrier(timeout=2) as hold:
            pass
    assert hold.locks == ("journal",) and hold.files == (str(journal_path.resolve()),)
    assert hold.uncovered and "one write per concurrent writer" in hold.uncovered[0]
    # The documented window: a LanceDB write whose guard passed does not hold the barrier and lands after the bump.
    pause.arm("store.add")
    w = Worker(lambda: store.add([_row("lance-1")]))
    w.start()
    assert pause.passed.wait(10)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with system.write_barrier(timeout=2):
            fence.bump()
    pause.go.set()
    w.join(20)
    assert w.error is None
    assert [a.assertion_id for a in store.query(abstractmemory.TripleQuery(limit=0))] == ["a-lance-1"]
    with pytest.raises(Refused):  # the writer's next write is refused: one write, never more
        store.add([_row("lance-2")])
