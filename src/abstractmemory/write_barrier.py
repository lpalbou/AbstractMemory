"""The write barrier: the bumper's half of the Stop fence (the commit guard is the writers' half).

The commit guard (`commit_guard.py`) runs INSIDE every write transaction, immediately before its COMMIT. A host that
moves what the guard compares (the runtime's lifecycle generation, at an operator's Stop) under a lock of its own
leaves one interleaving open: a writer's guard passes, the host bumps, the writer's COMMIT lands after the Stop
(Codex review 4, finding 2). `write_barrier()` closes it: the bumper holds memory's write locks around its bump, so
every transaction whose guard has passed reaches its COMMIT before the bump, and every transaction after the bump
calls its guard after it.

    with home_state_lock(home):                 # the host's lock first; memory never takes it
        with system.write_barrier(timeout=10):  # waits for every in-flight COMMIT, holds off every new one
            write_generation(home, g + 1)
    # released: the next COMMIT, in any process, calls its guard and sees g + 1

What it holds, acquired in this FIXED order and released in reverse:

1. The in-process locks of the home's writers, in the writers' own nesting order: the store's lock (the SQLite task
   queue and graph write on the store's connection under it; over an `InMemoryTripleStore` the queue and the graph's
   transaction take it too), a task queue's own lock when it has one, the in-memory graph tables' lock, then the
   journal's lock. Formation, the communities pass and the in-memory rewrites hold the store's (queue's) lock and
   then the journal's, so a barrier never deadlocks with a writer of this process.
2. The database write lock of each distinct SQLite file, the store's and then the journal's when it is another file:
   BEGIN IMMEDIATE on the system's own connection. It waits for every other connection's open write transaction
   (other processes, other handles of this process) to COMMIT or ROLLBACK, and holds off every new one. A file the
   store and the journal share is locked once. The barrier writes nothing: it ends with ROLLBACK.

The hot path is unchanged: no writer checks a flag, counts or calls anything for the barrier. Only the bumper pays.

Re-entrant within one thread: a nested barrier (the same system, or another one over a file this thread's barrier
already holds) re-enters the in-process locks and does not lock a held file again; only the outermost releases. A
barrier must not be taken INSIDE a memory write transaction of its own thread (it would wait for itself): over SQLite
this is refused (`RuntimeError`); in memory it cannot be detected. A memory write INSIDE the barrier's block on its
own thread is not supported either: SQLite refuses its BEGIN on the barrier's connection, and on another connection
to the same file it waits that connection's busy_timeout and fails "database is locked". The block is for the host's
own write. Keep it short: a writer of another process waits at most its busy_timeout (5 s for this package's stores
and journals) and then fails with "database is locked". The host must never take its own lock inside a memory
transaction (the guard runs there): the order is host lock, then barrier, never the reverse.

`timeout` (seconds; None = wait as long as it takes) bounds the whole acquisition. When it elapses, everything
acquired so far is released and `WriteBarrierTimeout` names what was still held by a writer, so a hung writer is
visible instead of a silent hang.

NOT COVERABLE: LanceDB. A `LanceDBTripleStore` takes no lock around its writes (LanceDB has no transaction and no
file write lock; the LanceDB graph's lock serializes one process only), so nothing can make a LanceDB write wait.
The window: a LanceDB write whose guard passed before the bump (`LanceDBTripleStore.add` between its guard call and
its table write; a LanceDB graph revision between its guard call and its log row and table writes) may land after
the bump. That is at most ONE write per concurrent writer, in any process; the writer's next write calls its guard
and is refused. The barrier still holds the home's journal. The uncovered store is named in `BarrierHold.uncovered`
and a `#FALLBACK` RuntimeWarning is emitted; so is any other store or journal type that has none of the known locks.

Also outside a barrier taken by ANOTHER handle or process: the two SQLite AUTOCOMMIT commit points,
`SQLiteTripleStore._write_pin` without a cursor (a pinless store's first embedded write) and the off-file graph's
`mark_journal_applied`. They call the guard before their one statement takes the file's write lock, so one such write
whose guard passed may land after a bump made through another connection. A barrier on the SAME handle covers them
(both hold the store's lock across the guard and the statement).
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional, Set, Tuple

__all__ = ["BarrierHold", "WriteBarrierTimeout", "write_barrier"]

# Per thread: the database files this thread's barriers hold (a nested barrier does not BEGIN on them again).
_local = threading.local()

# One busy wait inside SQLite before the barrier looks at its deadline again (milliseconds).
_SLICE_MS = 1000


class WriteBarrierTimeout(TimeoutError):
    """The barrier could not take a write lock within its `timeout`: a writer still holds it (its transaction has
    not committed). Everything the barrier had acquired is released before this is raised."""

    def __init__(self, waiting_for: str, timeout: float) -> None:
        self.waiting_for = waiting_for
        self.timeout = timeout
        super().__init__(f"write_barrier: still waiting for {waiting_for} after {timeout:g} s "
                         "(a writer holds it and has not committed)")


@dataclass(frozen=True)
class BarrierHold:
    """What a barrier holds for its block: the in-process locks (`store`, `tasks`, `graph`, `journal`), the SQLite
    files whose write lock it took (outermost barrier of this thread) or re-entered, and what it cannot cover."""

    locks: Tuple[str, ...]
    files: Tuple[str, ...]
    uncovered: Tuple[str, ...]


def _file_key(path: Any) -> str:
    return os.path.realpath(os.fspath(path))


def _plan(system: Any) -> Tuple[List[Tuple[str, Any]], List[Tuple[str, sqlite3.Connection]], List[str]]:
    """(locks in acquisition order, one (file, connection) per distinct SQLite file in order, uncovered parts)."""
    from .graph.graph import _MEMORY_BACKENDS
    from .in_memory_store import InMemoryTripleStore
    from .journal_memory import InMemoryJournal
    from .journal_sqlite import SQLiteJournal
    from .sqlite_store import SQLiteTripleStore

    store, journal, queue = system.store, system.journal, system.tasks
    locks: List[Tuple[str, Any]] = []
    conns: List[Tuple[str, sqlite3.Connection]] = []
    uncovered: List[str] = []

    def lock(name: str, obj: Any) -> None:
        if not any(held is obj for _, held in locks):
            locks.append((name, obj))

    def conn(path: Any, connection: sqlite3.Connection) -> None:
        key = _file_key(path)
        if all(key != held for held, _ in conns):
            conns.append((key, connection))

    if isinstance(store, SQLiteTripleStore):
        lock("store", store._lock)
        conn(store._path, store._conn)
    elif isinstance(store, InMemoryTripleStore):
        lock("store", store._lock)
    elif type(store).__name__ == "LanceDBTripleStore":
        uncovered.append("store: LanceDBTripleStore (no write lock: one write per concurrent writer may land "
                         "after the bump)")
    else:
        uncovered.append(f"store: {type(store).__name__} (no known write lock)")
    if queue is not None:
        lock("tasks", queue._lock)  # the store's own lock on both backends; a queue over another store has its own
    if isinstance(store, InMemoryTripleStore):
        backend = _MEMORY_BACKENDS.get(store)
        if backend is not None:
            lock("graph", backend._lock)  # its journal mark writes under this lock alone
    if isinstance(journal, SQLiteJournal):
        lock("journal", journal._lock)
        conn(journal._path, journal._conn)
    elif isinstance(journal, InMemoryJournal):
        lock("journal", journal._lock)
    else:
        uncovered.append(f"journal: {type(journal).__name__} (no known write lock)")
    return locks, conns, uncovered


def _left(deadline: Optional[float]) -> Optional[float]:
    return None if deadline is None else max(0.0, deadline - time.monotonic())


def _busy(exc: sqlite3.OperationalError) -> bool:
    code = getattr(exc, "sqlite_errorcode", None)  # Python >= 3.11
    if code is not None:
        return code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    text = str(exc).lower()
    return "database is locked" in text or "database is busy" in text or "database table is locked" in text


def _begin_immediate(connection: sqlite3.Connection, key: str, deadline: Optional[float],
                     timeout: Optional[float]) -> None:
    """BEGIN IMMEDIATE on `connection` (its lock is held), waiting in slices of the connection's busy handler until
    the deadline; the connection's own busy_timeout is restored whatever happens."""
    cur = connection.cursor()
    original = int(cur.execute("PRAGMA busy_timeout").fetchone()[0])
    try:
        while True:
            left = _left(deadline)
            wait_ms = _SLICE_MS if left is None else min(_SLICE_MS, int(left * 1000))
            cur.execute(f"PRAGMA busy_timeout = {int(wait_ms)}")
            try:
                cur.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as exc:
                if not _busy(exc):
                    raise
            left = _left(deadline)
            if left is not None and left <= 0:
                raise WriteBarrierTimeout(f"the write lock of {key}", float(timeout or 0.0))
    finally:
        cur.execute(f"PRAGMA busy_timeout = {original}")


def _release(begun: List[Tuple[str, sqlite3.Connection]], acquired: List[Any], mine: Set[str]) -> None:
    """ROLLBACK every file this barrier locked (newest first), then release its locks (newest first); a failed
    ROLLBACK is raised after every lock is released."""
    failure: Optional[BaseException] = None
    for key, connection in reversed(begun):
        mine.discard(key)
        try:
            if connection.in_transaction:  # a write on this thread inside the block may have ended it already
                connection.cursor().execute("ROLLBACK")
        except BaseException as exc:  # noqa: BLE001 - re-raised below, after the locks are released
            failure = failure or exc
    for held in reversed(acquired):
        held.release()
    if failure is not None:
        raise failure


@contextmanager
def write_barrier(system: Any, *, timeout: Optional[float] = None) -> Iterator[BarrierHold]:
    """Hold the write locks of `system`'s store, task queue, graph tables and journal for the caller's block: every
    write transaction whose commit guard has passed commits before the block runs, and none commits until it ends.
    See the module docstring for the order, re-entrancy, the timeout (`WriteBarrierTimeout`) and the LanceDB window."""
    if timeout is not None:
        timeout = float(timeout)
        if timeout < 0:
            raise ValueError(f"write_barrier timeout must be None or >= 0 seconds (got {timeout!r})")
    deadline = None if timeout is None else time.monotonic() + timeout
    locks, conns, uncovered = _plan(system)
    if uncovered:
        warnings.warn("#FALLBACK: write_barrier cannot hold " + "; ".join(uncovered), RuntimeWarning, stacklevel=3)
    mine: Set[str] = _local.__dict__.setdefault("files", set())
    acquired: List[Any] = []
    begun: List[Tuple[str, sqlite3.Connection]] = []
    try:
        for name, held in locks:
            left = _left(deadline)
            ok = held.acquire() if left is None else (held.acquire(True, left) if left > 0 else held.acquire(False))
            if not ok:
                raise WriteBarrierTimeout(f"the {name} lock (a writer of this process is inside a transaction)",
                                          float(timeout or 0.0))
            acquired.append(held)
        for key, connection in conns:
            if key not in mine and connection.in_transaction:
                # Its lock is held by this thread, so the open transaction is this thread's own write.
                raise RuntimeError(f"write_barrier inside a memory write transaction on {key} on this thread: the "
                                   "barrier would wait for its own COMMIT (take it outside every memory write)")
        for key, connection in conns:
            if key in mine:
                continue  # this thread's outer barrier holds the file
            _begin_immediate(connection, key, deadline, timeout)
            begun.append((key, connection))
            mine.add(key)
    except BaseException:
        _release(begun, acquired, mine)
        raise
    try:
        yield BarrierHold(locks=tuple(name for name, _ in locks), files=tuple(key for key, _ in conns),
                          uncovered=tuple(uncovered))
    finally:
        _release(begun, acquired, mine)
