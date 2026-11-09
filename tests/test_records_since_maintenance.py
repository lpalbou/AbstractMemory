"""`records_since_maintenance`: how much the home lived since its last COMPLETED sleep (the host's idle -> sleep
threshold; operator 2026-11-09: sleep after 24 h or 500 events).

`sleep_pass` records when a whole night ran to its end (`{prefix}maintenance`, one row per scope pair and kind); a
cancelled, report-only or anchored night records nothing, and a cycle window (include_dream=False) is recorded apart
and does not reset the count. The read counts the records formed after that moment (digest rows only), or since birth
for a home that never slept; it writes nothing and, on the SQLite home, reads through the (scope, owner_id,
observed_at) index. Every case runs on both substrate pairs.

MUTATION LIST (scratch copy, each mutant run against this file; all red, the source restored byte-exact):
R1 sleep_pass records no completion; R2 a cancelled night recorded; R3 a report-only night recorded; R4 a cycle
window resets the count; R5 the record filter dropped (edge rows counted); R6 the scope filter dropped; R7 a never-slept home's
`since` None; R8 the count ignores the completion (counts since birth); R9 the SQLite count off the index (a full
scan); R10 bookkeeping rows counted.
"""

from __future__ import annotations

import hashlib
import time
import warnings
from typing import Any, List

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import (  # noqa: E402
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    records_since_maintenance,
    sleep_pass,
)
from abstractmemory.records import resolve_digest_assertion  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]


class Embedder:
    model = "fake-hash-16"

    def embed_texts(self, texts):
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
    system.kind = kind
    return system


@pytest.fixture(params=["memory", "sqlite"])
def home(request, tmp_path):
    system = _open(request.param, tmp_path)
    yield system
    system.journal.close()
    system.store.close()


def _form(system, key: str, *, scope: str = SCOPE, edges=(), **kw: Any) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many(
            [MemoryRecordInput(kind="episode", title=f"Exchange {key}", digest=f"We talked about {key}.",
                               edges=tuple(edges), **kw)], scope=scope, owner_id=OWNER, idempotency_key=key)
    return gid


def _many(system, prefix: str, n: int, **kw: Any) -> List[str]:
    return [_form(system, f"{prefix}-{i}", **kw) for i in range(n)]


def _sleep(system, **kw: Any):
    time.sleep(0.002)  # the completion and the next formation never share a timestamp
    out = sleep_pass(system, scopes=SCOPES, owner_id=OWNER, **kw)
    time.sleep(0.002)
    return out


def test_a_home_that_never_slept_counts_since_birth(home) -> None:
    assert records_since_maintenance(home, scopes=SCOPES) == {"count": 0, "last_maintenance_at": None, "since": None}
    first = _form(home, "first")
    _form(home, "second", edges=(("supports", first),))                  # an edge row is not a record
    out = records_since_maintenance(home, scopes=SCOPES)
    assert out["count"] == 2 and out["last_maintenance_at"] is None
    assert out["since"] == resolve_digest_assertion(home.store, first).observed_at


def test_a_completed_night_resets_the_count_and_its_own_formations_never_count(home) -> None:
    _many(home, "day", 4)
    night = _sleep(home)
    assert "cancelled_after" not in night
    out = records_since_maintenance(home, scopes=SCOPES)
    assert out["last_maintenance_at"] is not None and out["since"] == out["last_maintenance_at"]
    assert out["count"] == 0                                                  # the night's dream/cards precede it
    _many(home, "after", 3)
    assert records_since_maintenance(home, scopes=SCOPES)["count"] == 3
    assert records_since_maintenance(home)["count"] == 3                      # any pair
    row = home.tasks.last_maintenance(SCOPES)
    assert row["kind"] == "night" and row["completed_at"] == out["last_maintenance_at"]
    assert row["seq"] <= home.journal.current_seq()


def test_cancelled_report_only_and_cycle_nights_complete_nothing(home) -> None:
    _many(home, "day", 3)
    assert _sleep(home, should_continue=lambda: False)["cancelled_after"]
    budget = iter([True, True])                                               # ends after maintenance: mid-night
    assert _sleep(home, should_continue=lambda: next(budget, False))["cancelled_after"] == "maintenance"
    assert _sleep(home, report_only=True) is not None
    assert records_since_maintenance(home, scopes=SCOPES)["last_maintenance_at"] is None
    _sleep(home, include_dream=False)                                         # a maintenance nap
    assert home.tasks.last_maintenance(SCOPES, kind="cycle") is not None
    out = records_since_maintenance(home, scopes=SCOPES)
    assert out["last_maintenance_at"] is None and out["count"] >= 3


def test_the_count_reads_only_the_asked_scopes(home) -> None:
    _sleep(home)
    _many(home, "here", 2)
    _many(home, "there", 5, scope="work")
    assert records_since_maintenance(home, scopes=SCOPES)["count"] == 2
    work = records_since_maintenance(home, scopes=[("work", OWNER)])
    assert work["count"] == 5 and work["last_maintenance_at"] is None       # "work" never slept
    assert records_since_maintenance(home)["count"] == 5 + 2                 # any pair: since the newest night


def test_bookkeeping_rows_are_not_records(home) -> None:
    _sleep(home)
    _form(home, "booked", attributes={"bookkeeping": True})
    _form(home, "lived")
    assert records_since_maintenance(home, scopes=SCOPES)["count"] == 1


def test_the_read_writes_nothing(home) -> None:
    _many(home, "day", 2)
    _sleep(home)
    _many(home, "after", 2)
    seq = home.journal.current_seq()
    if home.kind == "sqlite":
        changes = home.store._conn.total_changes
    out = records_since_maintenance(home, scopes=SCOPES)
    assert out["count"] == 2 and home.journal.current_seq() == seq
    if home.kind == "sqlite":
        assert home.store._conn.total_changes == changes


def test_the_sqlite_count_walks_the_index(tmp_path) -> None:
    system = _open("sqlite", tmp_path)
    try:
        _many(system, "day", 3)
        _sleep(system)
        _many(system, "after", 2)
        seen: List[str] = []
        system.store._conn.set_trace_callback(seen.append)
        try:
            assert records_since_maintenance(system, scopes=SCOPES)["count"] == 2
        finally:
            system.store._conn.set_trace_callback(None)
        counts = [s for s in seen if s.lstrip().upper().startswith("SELECT COUNT(*)")]
        assert counts
        for sql in counts:
            plan = " ".join(str(r[-1]) for r in system.store._conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall())
            assert "SEARCH" in plan and "scope_owner_observed" in plan, plan
    finally:
        system.journal.close()
        system.store.close()


def test_a_sqlite_home_without_a_queue_reads_without_creating_anything(tmp_path) -> None:
    system = _open("sqlite", tmp_path, task_queue=False)
    try:
        _many(system, "day", 2)
        tables = {r[0] for r in system.store._conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        out = records_since_maintenance(system, scopes=SCOPES)
        assert out["count"] == 2 and out["last_maintenance_at"] is None
        assert {r[0] for r in system.store._conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")} == \
            tables
    finally:
        system.journal.close()
        system.store.close()
