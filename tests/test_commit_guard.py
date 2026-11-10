"""The commit guard (the memory half of the host's Stop fence): `MemorySystem(..., commit_guard=guard)`.

The runtime passes its lifecycle fence's `check`; an operator's Stop moves the generation and every later memory
commit must be refused with nothing landing (STOP-LANE-DESIGN, invariant I1: no persistence after Stop; I6: no
unfenced writer). Memory knows no entity and no Stop: the guard is a callable taking the commit point's name, called
inside every write transaction immediately before its COMMIT. Pinned here:

- T4 (`test_*_rolls_back`): a guard that raises refuses formation with its tasks (`remember_many` on a queued home),
  formation without a queue, `rewrite_digest`, `retitle`, `declare_pending`, `record_maintenance`, a night's
  completion marker, every journal family, the store's own writes (close, narrow, the vector swap, the first-write
  pin), a graph revision (SQLite same-file and off-file, in-memory, LanceDB), the graph's journal mark and a LanceDB
  store write: every table row-identical before and after, the guard's own exception surfaced (the same object),
  nothing recorded about the refusal; a guard that passes commits normally;
- one guard call per OUTERMOST write (a nested queue/journal write on its caller's transaction, or inside a composed
  in-memory write, does not call it again);
- the check is INSIDE the transaction: a generation moved by the transaction's own body is seen at its COMMIT;
- installation: all or none, a foreign store refused, a second different guard refused;
- the hot path: 200 guarded commits make exactly the file opens / stats / flocks / subprocesses that 200 unguarded
  ones make (the guard adds none), the dispatch costs well under its ceiling;
- I6, the closed set: every function that calls the guard is listed, every write transaction in the package is a
  listed commit point or an exemption with its reason, and every method of the in-memory and LanceDB doubles is
  classified (a new transaction helper or write method without the guard fails here).

LanceDB: tested locally (lancedb is a test extra); skipped where it is not installed.

MUTATION LIST (each applied to a scratch COPY of src/, this file run against it, all red; G1-G21 also red
test_the_commit_points_are_a_closed_set; G22-G26 change no call site, so only their behavioural cases go red):
- G1 SQLiteJournal._txn without its guard        -> test_journal_appends_roll_back[sqlite-*] (7),
                                                    ..._inside_the_transaction_is_seen[journal], graph journal mark
- G2 InMemoryJournal._write                      -> test_journal_appends_roll_back[memory-*] (7)
- G3 SQLiteTripleStore.add                       -> test_formation_without_a_queue_rolls_back[sqlite]
- G4 SQLiteTripleStore.close_assertion           -> test_store_writes_roll_back[sqlite-close_assertion]
- G5 SQLiteTripleStore.narrow_assertion          -> test_store_writes_roll_back[sqlite-narrow_assertion]
- G6 SQLiteTripleStore.replace_vectors           -> test_store_writes_roll_back[sqlite-replace_vectors]
- G7 SQLiteTripleStore._write_pin (autocommit)   -> test_the_first_write_pin_rolls_back[sqlite]
- G8 InMemoryTripleStore._write                  -> test_store_writes_roll_back[memory-*] (3), formation w/o queue
- G9 InMemoryTripleStore._write_pin              -> test_the_first_write_pin_rolls_back[memory]
- G10 LanceDBTripleStore.add                     -> test_a_lancedb_store_write_rolls_back
- G11 _SQLiteBackend.transaction                 -> test_a_graph_revision_rolls_back[sqlite, sqlite-offfile],
                                                    ..._inside_the_transaction_is_seen[graph]
- G12 _SQLiteBackend.mark_journal_applied        -> test_the_graph_journal_mark_rolls_back[sqlite-offfile]
- G13 _MemoryBackend.transaction                 -> test_a_graph_revision_rolls_back[memory],
                                                    ..._inside_the_transaction_is_seen[graph-memory]
- G14 _MemoryBackend.mark_journal_applied        -> test_the_graph_journal_mark_rolls_back[memory]
- G15 LanceDBBackend.transaction                 -> test_a_graph_revision_rolls_back[lancedb]
- G16 LanceDBBackend.mark_journal_applied        -> test_the_graph_journal_mark_rolls_back[lancedb]
- G17 MemoryTaskQueue._txn                       -> test_record_maintenance_rolls_back[*],
                                                    test_a_stopped_night_records_no_completion[*]
- G18 form_with_tasks, SQLite branch             -> test_formation_with_tasks_rolls_back[sqlite],
                                                    ..._inside_the_transaction_is_seen[formation], the hot path
- G19 form_with_tasks, in-memory branch          -> test_formation_with_tasks_rolls_back[memory]
- G20 understanding._apply, SQLite branch        -> test_understanding_writes_roll_back[sqlite-*] (3),
                                                    ..._inside_the_transaction_is_seen[rewrite]
- G21 understanding._apply, in-memory branch     -> test_understanding_writes_roll_back[memory-*] (3)
- G22 MemorySystem installs no guard             -> 54 cases (every refusal)
- G23 the journal's guard after its COMMIT       -> test_journal_appends_roll_back[sqlite-*],
                                                    ..._inside_the_transaction_is_seen[journal]
- G24 deferred_to_caller defers nothing          -> test_one_guard_call_per_outermost_write[memory], the in-memory
                                                    formation, rewrite and graph counts
- G25 form_with_tasks, in-memory branch, guard   -> test_a_stop_after_the_first_formed_row_refuses_the_in_memory_
      back before its first row (Stop fence F8)     formation[memory, sqlite]
- G26 form_with_tasks commits a SQLite journal's -> test_a_stop_after_the_first_formed_row_refuses_the_in_memory_
      bindings before its guard                     formation[sqlite]
"""

from __future__ import annotations

import ast
import builtins
import collections
import copy
import fcntl
import hashlib
import io
import os
import re
import subprocess
import time
import warnings
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

np = pytest.importorskip("numpy")

import abstractmemory  # noqa: E402
from abstractmemory import (  # noqa: E402
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    TripleAssertion,
    TripleQuery,
    records_since_maintenance,
    sleep_pass,
)
from abstractmemory.commit_guard import guard_commit  # noqa: E402
from abstractmemory.journal import (  # noqa: E402
    ClosureRecord,
    MemoryEvent,
    ReconstructionTrace,
    ScopeBinding,
    UnderstandingVersion,
    ValenceEvent,
)
from abstractmemory.records import resolve_digest_assertion  # noqa: E402
from abstractmemory.seam import ActiveMemorySnapshot  # noqa: E402

from graph_support import T, claim, close, file_state, home_state, open_home, rev  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
DIM = 16
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "artifact", "artifact_id": "authoring-call-1"}]


class Refused(Exception):
    """Stands for the host's StoppedByOperator: whatever the guard raises must reach the caller unchanged."""


class Guard:
    """Records every commit point it is asked about; `refuse` = None (pass), "*" (every commit) or a set of names."""

    def __init__(self) -> None:
        self.calls: list = []
        self.refuse: Any = None
        self.error = Refused("stopped by the operator")

    def __call__(self, where: str) -> None:
        self.calls.append(where)
        if self.refuse == "*" or (self.refuse and where in self.refuse):
            raise self.error


class Fence:
    """The runtime's shape: an int captured at admission, compared with the current one (no I/O)."""

    def __init__(self) -> None:
        self.generation = self.admitted = 7
        self.calls = 0

    def check(self, where: str) -> None:
        self.calls += 1
        if self.generation != self.admitted:
            raise Refused(f"stopped by the operator ({where})")

    def bump(self) -> None:
        self.generation += 1


class Embedder:
    model = "fake-hash-16"

    def embed_texts(self, texts):
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(DIM)
            out.append((v / np.linalg.norm(v)).tolist())
        return out


class Home:
    def __init__(self, kind: str, system: MemorySystem, guard: Any, path: Optional[Path]) -> None:
        self.kind, self.system, self.guard, self.path = kind, system, guard, path


def _open(kind: str, tmp_path: Path, *, task_queue: bool = True, pinned: bool = True, guard: Any = None,
          name: str = "home", guarded: bool = True) -> Home:
    """An entity-home-shaped pair (embedder, pin declared at birth) guarded by `guard` (a fresh Guard by default;
    `guarded=False`: no commit_guard at all)."""
    guard = Guard() if guard is None else guard
    emb = Embedder()
    pin = {"model_id": Embedder.model, "dimension": DIM} if pinned else None
    path = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if kind == "memory":
            store, journal = InMemoryTripleStore(embedder=emb, embedding_pin=pin), InMemoryJournal()
        else:
            path = tmp_path / f"{name}.sqlite3"
            store, journal = SQLiteTripleStore(path, embedder=emb, embedding_pin=pin), SQLiteJournal(path)
        commit_guard = (guard.check if isinstance(guard, Fence) else guard) if guarded else None
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=task_queue,
                              commit_guard=commit_guard)
    return Home(kind, system, guard, path)


@pytest.fixture(params=["memory", "sqlite"])
def home(request, tmp_path):
    h = _open(request.param, tmp_path)
    yield h
    h.system.journal.close()
    h.system.store.close()


def _public(obj: Any) -> Dict[str, Any]:
    """An in-memory object's data (its lock, guard, embedder and back-reference are not state)."""
    skip = ("_lock", "_commit_guard", "_embedder", "store")
    return {k: copy.deepcopy(v) for k, v in vars(obj).items() if k not in skip}


def state(home: Home) -> Any:
    """Everything the home holds: every row of every SQLite table of its file, or the in-memory store, journal, task
    queue database and graph tables."""
    if home.kind == "sqlite":
        return file_state(home.path)
    store, journal, queue = home.system.store, home.system.journal, home.system.tasks
    from abstractmemory.graph.graph import _MEMORY_BACKENDS

    out = {"store": _public(store), "journal": _public(journal)}
    if queue is not None:
        out["queue"] = list(queue._conn.iterdump())
    backend = _MEMORY_BACKENDS.get(store)
    if backend is not None:
        out["graph"] = _public(backend)
    return out


def _form(system: MemorySystem, key: str, *, pending=(), title: Optional[str] = "A talk at the archive") -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many(
            [MemoryRecordInput(kind="episode", title=title, digest="We talked about the archive.", pending=pending)],
            scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _refused(home: Home, fn, *, where) -> None:
    """`fn()` under a guard refusing every commit: the guard's exception, nothing changed, one call at `where`."""
    before = state(home)
    home.guard.calls.clear()
    home.guard.refuse = "*"
    with pytest.raises(Refused) as caught:
        fn()
    home.guard.refuse = None
    assert caught.value is home.guard.error            # propagated unchanged, never wrapped or recorded
    assert home.guard.calls == [where]                 # one call, at the outermost commit point
    assert state(home) == before                       # nothing of the refused write landed
    home.guard.calls.clear()                           # the admitted retry's calls are checked by the caller


# ----------------------------------------------------------------------------------------------- T4: refused writes


def test_formation_with_tasks_rolls_back(home) -> None:
    """remember_many on a queued home (form_with_tasks): the pending record, its binding and its digest.author task
    form together or not at all."""
    _refused(home, lambda: _form(home.system, "refused", pending=("summary",)), where="tasks.form_with_tasks")
    gid = _form(home.system, "refused", pending=("summary",))           # the same call, admitted
    assert home.guard.calls == ["tasks.form_with_tasks"]
    assert [t["kind"] for t in home.system.tasks.tasks(target_id=gid)] == ["digest.author"]


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_formation_without_a_queue_rolls_back(kind, tmp_path) -> None:
    h = _open(kind, tmp_path, task_queue=False)
    _refused(h, lambda: _form(h.system, "plain"), where="store.add")
    gid = _form(h.system, "plain")
    assert h.guard.calls == ["store.add", "journal"]                    # rows, then the binding (two transactions)
    assert resolve_digest_assertion(h.system.store, gid) is not None


def _rewrite(system, gid):
    return system.rewrite_digest(gid, text="We talked about the archive and its catalogue.", author=MODEL,
                                 reader=READER, sources=STEP, cause={"cause": "formation", "pending": "summary"},
                                 expected_version=0)


def _retitle(system, gid):
    return system.retitle(gid, title="A long talk at the archive", author=MODEL, reader=READER, sources=STEP,
                          cause="backfill", expected_version=0)


def _declare(system, gid):
    return system.declare_pending(gid, fields=("title",), cause="repair", reason="the title is mechanical")


@pytest.mark.parametrize("verb,field", [(_rewrite, "digest"), (_retitle, "title"), (_declare, "pending")],
                         ids=["rewrite_digest", "retitle", "declare_pending"])
def test_understanding_writes_roll_back(home, verb, field) -> None:
    gid = _form(home.system, "understood", pending=("summary",) if field == "digest" else ())
    _refused(home, lambda: verb(home.system, gid), where=f"understanding.{field}")
    out = verb(home.system, gid)                                        # admitted: the same write applies
    assert out["applied"] is True and out["outcome"] == "applied"
    assert home.guard.calls == [f"understanding.{field}"]


def test_record_maintenance_rolls_back(home) -> None:
    def mark():
        home.system.tasks.record_maintenance(SCOPES, kind="night", completed_at="2026-11-09T03:00:00+00:00", seq=1)

    _refused(home, mark, where="tasks.record_maintenance")
    mark()
    assert home.system.tasks.last_maintenance(SCOPES)["completed_at"] == "2026-11-09T03:00:00+00:00"


def test_a_stopped_night_records_no_completion(home) -> None:
    """Classes C/H of the design: a night whose host never passed `cancelled=` still cannot record a completed night
    once its commits are refused; the boundary of records_since_maintenance stays where it was."""
    for i in range(3):
        _form(home.system, f"day-{i}")
    home.guard.refuse = {"tasks.record_maintenance"}                     # the Stop lands as the night ends
    with pytest.raises(Refused) as caught:
        sleep_pass(home.system, scopes=SCOPES, owner_id=OWNER)
    assert caught.value is home.guard.error and home.guard.calls[-1] == "tasks.record_maintenance"
    assert home.system.tasks.last_maintenance(SCOPES) is None
    assert records_since_maintenance(home.system, scopes=SCOPES)["boundary_source"] == "birth"


def _journal_record(family: str):
    return {
        "events": lambda j: j.append_events([MemoryEvent(kind="selected", scope=SCOPE, owner_id=OWNER,
                                                         record_id="ex:r1")]),
        "binding": lambda j: j.append_binding(ScopeBinding(record_id="ex:r1", scope=SCOPE, owner_id=OWNER)),
        "closure": lambda j: j.append_closure(ClosureRecord(assertion_id="a1", kind="retract", reason="no longer")),
        "trace": lambda j: j.append_trace(ReconstructionTrace(
            trace_id="t1", trace_kind="reconstruct", query_fingerprint="f", need={"q": 1},
            searched_scopes=[{"scope": SCOPE, "owner_id": OWNER}])),
        "snapshot": lambda j: j.append_snapshot(ActiveMemorySnapshot(snapshot_id="s1", trace_id="t1",
                                                                     used_record_ids=("ex:r1",))),
        "valence": lambda j: j.append_valence([ValenceEvent(target_id="ex:r1", sign=1, magnitude=2, reason="it helped",
                                                            scope=SCOPE, owner_id=OWNER)]),
        "version": lambda j: j.append_version(UnderstandingVersion(
            record_id="ex:r1", assertion_id="a1", version=1, field="digest", text="t", scope=SCOPE, owner_id=OWNER,
            version_id="v-ex:r1-digest-1")),
    }[family]


@pytest.mark.parametrize("family", ["events", "binding", "closure", "trace", "snapshot", "valence", "version"])
def test_journal_appends_roll_back(home, family) -> None:
    write = _journal_record(family)
    _refused(home, lambda: write(home.system.journal), where="journal")
    write(home.system.journal)
    assert home.system.journal.current_seq() >= 1


def _one_assertion(home: Home) -> str:
    [aid] = home.system.add([TripleAssertion(subject="ex:dana", predicate="schema:worksFor", object="ex:acme",
                                             scope=SCOPE, owner_id=OWNER, observed_at="2026-01-01T00:00:00+00:00")])
    return aid


@pytest.mark.parametrize("op", ["close_assertion", "narrow_assertion", "replace_vectors"])
def test_store_writes_roll_back(home, op) -> None:
    store = home.system.store
    aid = _one_assertion(home)
    if op == "close_assertion":
        fn = lambda: store.close_assertion(aid, "2026-06-01T00:00:00+00:00")  # noqa: E731
    elif op == "narrow_assertion":
        store.close_assertion(aid, "2026-06-01T00:00:00+00:00")
        fn = lambda: store.narrow_assertion(aid, "2026-03-01T00:00:00+00:00")  # noqa: E731
    else:
        [vector] = Embedder().embed_texts(["another space"])
        rows = len(store.query(TripleQuery(limit=0)))
        fn = lambda: store.replace_vectors({aid: vector}, store.embedding_pin(), expected_row_count=rows)  # noqa: E731
    _refused(home, fn, where=f"store.{op}")
    fn()
    assert home.guard.calls == [f"store.{op}"]


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_the_first_write_pin_rolls_back(kind, tmp_path) -> None:
    """A pinless store's first embedded write pins the space BEFORE the rows' transaction (an autocommit write on
    SQLite): it is its own commit point, so a refused formation leaves no pin behind."""
    h = _open(kind, tmp_path, task_queue=False, pinned=False)
    assert h.system.store.embedding_pin() is None
    _refused(h, lambda: _form(h.system, "first"), where="store.write_pin")
    _form(h.system, "first")
    assert h.system.store.embedding_pin()["dimension"] == DIM


def _lance_state(path: Path) -> Dict[str, Any]:
    from abstractmemory.lancedb_store import _import_lancedb, _list_lancedb_tables

    db = _import_lancedb().connect(str(path))
    out: Dict[str, Any] = {}
    for name in sorted(_list_lancedb_tables(db)):
        table = db.open_table(name)
        out[name] = (table.version, sorted(repr(r) for r in table.to_arrow().to_pylist()))
    return out


def _graph_state(h) -> Any:
    if h.kind == "lancedb":
        return {"lance": _lance_state(h.path), "journal": file_state(h.journal_path)}
    return home_state(h)


@pytest.fixture(params=["sqlite", "sqlite-offfile", "memory", "lancedb"])
def mind(request, tmp_path):
    if request.param == "lancedb":
        pytest.importorskip("lancedb")
    h = open_home(tmp_path, request.param)
    h.guard = Guard()
    MemorySystem(store=h.store, journal=h.journal, commit_guard=h.guard)  # the host's facade installs the guard
    yield h
    h.close()


def test_a_graph_revision_rolls_back(mind) -> None:
    mind.graph.apply_revision(rev("r1", claim("ex:a1")))                 # the mind exists (its tables too)
    before = _graph_state(mind)
    mind.guard.calls.clear()
    mind.guard.refuse = "*"
    with pytest.raises(Refused) as caught:
        mind.graph.apply_revision(rev("r2", claim("ex:a2", s="ex:eli")))
    mind.guard.refuse = None
    assert caught.value is mind.guard.error and mind.guard.calls == ["graph"]
    assert _graph_state(mind) == before
    assert mind.graph.apply_revision(rev("r2", claim("ex:a2", s="ex:eli"))).applied is True


@pytest.fixture(params=["sqlite-offfile", "memory", "lancedb"])
def offfile_mind(request, tmp_path):
    if request.param == "lancedb":
        pytest.importorskip("lancedb")
    h = open_home(tmp_path, request.param)
    h.guard = Guard()
    MemorySystem(store=h.store, journal=h.journal, commit_guard=h.guard)
    yield h
    h.close()


def test_the_graph_journal_mark_rolls_back(offfile_mind) -> None:
    """A mind whose journal is elsewhere commits a close in three transactions (revision, closures, mark). Refused at
    the mark, the revision stays awaiting its mark (journal_applied 0), exactly what a crash there leaves, and
    repair() completes it once commits are admitted again."""
    h = offfile_mind
    h.graph.apply_revision(rev("r1", claim("ex:a1")))
    h.guard.calls.clear()
    h.guard.refuse = {"graph.mark_journal_applied"}
    with pytest.raises(Refused) as caught:
        h.graph.apply_revision(rev("r2", close("ex:a1", T(2)), cause="reinterpret"))
    h.guard.refuse = None
    assert caught.value is h.guard.error
    assert h.guard.calls == ["graph", "journal", "graph.mark_journal_applied"]
    assert [r.revision_id for r in h.graph._b.pending_journal(10)] == ["r2"]
    assert h.graph.repair() == 1 and h.graph._b.pending_journal(10) == []


def test_a_lancedb_store_write_rolls_back(tmp_path) -> None:
    pytest.importorskip("lancedb")
    from abstractmemory import LanceDBTripleStore

    guard = Guard()
    store = LanceDBTripleStore(tmp_path / "lance")
    MemorySystem(store=store, journal=SQLiteJournal(tmp_path / "journal.sqlite3"), commit_guard=guard)
    row = TripleAssertion(subject="ex:dana", predicate="schema:worksFor", object="ex:acme", scope=SCOPE,
                          owner_id=OWNER, observed_at="2026-01-01T00:00:00+00:00", assertion_id="a1")
    before = _lance_state(tmp_path / "lance")
    guard.refuse = "*"
    with pytest.raises(Refused) as caught:
        store.add([row])
    guard.refuse = None
    assert caught.value is guard.error and guard.calls == ["store.add"]
    assert _lance_state(tmp_path / "lance") == before
    assert store.add([row]) == ["a1"] and len(store.query(TripleQuery(limit=0))) == 1


# ------------------------------------------------------------------------------------- the passing guard, the counts


def test_a_passing_guard_commits_like_no_guard(tmp_path) -> None:
    """The same life on a guarded home and on an unguarded twin: the same records, readings, tasks and marker."""
    lives = []
    for name in ("guarded", "bare"):
        h = _open("sqlite", tmp_path, name=name, guarded=name == "guarded")
        gid = _form(h.system, "life-1", pending=("summary",))
        out = _rewrite(h.system, gid)
        h.system.tasks.record_maintenance(SCOPES, kind="night", completed_at="2026-11-09T03:00:00+00:00", seq=1)
        a = resolve_digest_assertion(h.system.store, gid)
        lives.append((gid, out["applied"], out["version"], a.object, sorted(a.attributes),
                      [(t["kind"], t["status"]) for t in h.system.tasks.tasks(target_id=gid)],
                      h.system.tasks.last_maintenance(SCOPES) is not None))
        if name == "guarded":
            assert h.guard.calls == ["tasks.form_with_tasks", "understanding.digest", "tasks.record_maintenance"]
        else:
            assert h.guard.calls == [] and h.system.store._commit_guard is None
    assert lives[0] == lives[1]


def test_one_guard_call_per_outermost_write(home) -> None:
    """A write nested in its caller's transaction does not call the guard again: the queue's task writes on a
    rewrite's cursor (or, in memory, inside the rewrite's composed write), the journal's version rows, the in-memory
    graph's store rows."""
    gid = _form(home.system, "nested")
    home.guard.calls.clear()
    _declare(home.system, gid)            # marker + version row + task enqueue: one transaction
    assert home.guard.calls == ["understanding.pending"]
    from abstractmemory.graph import MemoryGraph

    home.guard.calls.clear()
    MemoryGraph(home.system.store, home.system.journal).apply_revision(rev("g1", claim("ex:g1")))
    assert home.guard.calls == ["graph"]


@pytest.mark.parametrize("site", ["formation", "rewrite", "journal", "graph", "graph-memory"])
def test_a_generation_moved_inside_the_transaction_is_seen(site, tmp_path, monkeypatch) -> None:
    """Design §6.2: the check must not drift out of the transaction. The move lands from INSIDE the transaction's
    own body (after BEGIN, before COMMIT); a guard checked before BEGIN would pass it, the commit-point guard refuses
    it and nothing lands."""
    from abstractmemory.graph import MemoryGraph
    from abstractmemory.graph import graph as graph_mod

    fence = Fence()
    h = _open("memory" if site == "graph-memory" else "sqlite", tmp_path, guard=fence)
    gid = _form(h.system, "before") if site == "rewrite" else None

    def moving(cls, name):
        original = getattr(cls, name)

        def inner(*a, **k):
            out = original(*a, **k)
            fence.bump()                                   # the operator's Stop, mid-transaction
            return out

        monkeypatch.setattr(cls, name, inner)

    if site == "formation":
        moving(SQLiteTripleStore, "_insert_rows_on")
        fn = lambda: _form(h.system, "moved")  # noqa: E731
    elif site == "rewrite":
        moving(SQLiteTripleStore, "_rewrite_row_on")
        fn = lambda: _retitle(h.system, gid)  # noqa: E731
    elif site == "journal":
        moving(SQLiteJournal, "_append_binding_on")
        fn = lambda: h.system.journal.append_binding(ScopeBinding(record_id="ex:r1", scope=SCOPE, owner_id=OWNER))  # noqa: E731,E501
    else:
        graph = MemoryGraph(h.system.store, h.system.journal)  # opened first: its schema is an opening write
        moving(graph_mod._SQLiteTx if site == "graph" else graph_mod._MemoryTx, "insert_revision")
        fn = lambda: graph.apply_revision(rev("m1", claim("ex:m1")))  # noqa: E731
    before = state(h)
    with pytest.raises(Refused):
        fn()
    assert state(h) == before


@pytest.mark.parametrize("journal_kind", ["memory", "sqlite"])
def test_a_stop_after_the_first_formed_row_refuses_the_in_memory_formation(journal_kind, tmp_path,
                                                                           monkeypatch) -> None:
    """Stop fence F8: form_with_tasks's in-memory branch (in-memory store, in-memory or SQLite journal) checks the
    guard immediately before its COMMITs, after its rows, bindings and tasks. The fence still admits the formation
    when it starts and is bumped right after the first row is inserted: a guard checked before that row would pass
    and the formation would land; the commit-point guard refuses it and no row, binding or task remains. The same
    call, admitted again, forms the record with its binding and task (the absence check is not vacuous)."""
    fence = Fence()
    emb = Embedder()
    jpath = tmp_path / "journal.sqlite3"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        store = InMemoryTripleStore(embedder=emb, embedding_pin={"model_id": Embedder.model, "dimension": DIM})
        journal = InMemoryJournal() if journal_kind == "memory" else SQLiteJournal(jpath)
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=True, commit_guard=fence.check)
    original = InMemoryTripleStore._insert_prepared

    def first_row_then_stop(self, *a, **k):
        out = original(self, *a, **k)
        fence.bump()                                       # the operator's Stop, after the first formed row
        return out

    def snapshot() -> Any:
        jstate = _public(journal) if journal_kind == "memory" else file_state(jpath)
        return {"store": _public(store), "journal": jstate, "queue": list(system.tasks._conn.iterdump())}

    try:
        before = snapshot()
        monkeypatch.setattr(InMemoryTripleStore, "_insert_prepared", first_row_then_stop)
        with pytest.raises(Refused):
            _form(system, "stopped", pending=("summary",))
        assert fence.calls == 1                            # one check, at the commit point, after the bump
        assert snapshot() == before
        assert store.query(TripleQuery(limit=0)) == []     # no row
        assert journal.bindings() == []                    # no binding
        assert system.tasks.tasks() == []                  # no task
        monkeypatch.setattr(InMemoryTripleStore, "_insert_prepared", original)
        fence.admitted = fence.generation                  # admitted again (a new generation's run)
        gid = _form(system, "stopped", pending=("summary",))
        assert [a.assertion_id for a in store.query(TripleQuery(limit=0))]
        assert [b.record_id for b in journal.bindings()] == [gid]
        assert [t["kind"] for t in system.tasks.tasks(target_id=gid)] == ["digest.author"]
    finally:
        journal.close()
        store.close()


# --------------------------------------------------------------------------------------------------- installation


def test_installation_is_all_or_none_and_one_guard_per_store(tmp_path) -> None:
    guard, other = Guard(), Guard()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        store, journal = InMemoryTripleStore(), InMemoryJournal()

    class ForeignJournal:  # a journal whose writes call no guard
        pass

    with pytest.raises(TypeError, match="cannot honour a commit guard"):
        MemorySystem(store=store, journal=ForeignJournal(), commit_guard=guard)
    assert store._commit_guard is None                                  # nothing installed on the store either
    with pytest.raises(TypeError, match="must be callable"):
        MemorySystem(store=store, journal=journal, commit_guard="fence")
    fence = Fence()
    MemorySystem(store=store, journal=journal, commit_guard=fence.check)
    MemorySystem(store=store, journal=journal, commit_guard=fence.check)  # the same guard (a fresh bound method)
    MemorySystem(store=store, journal=journal)                           # no guard: the installed one stays
    assert store._commit_guard == fence.check and journal._commit_guard == fence.check
    with pytest.raises(ValueError, match="already guarded"):
        MemorySystem(store=store, journal=journal, commit_guard=other)
    assert store._commit_guard == fence.check


# ------------------------------------------------------------------------------------------------- the hot path


_IO = [(builtins, "open"), (io, "open"), (os, "open"), (os, "stat"), (os, "lstat"), (os, "fstat"),
       (fcntl, "flock"), (fcntl, "lockf"), (subprocess, "Popen"), (subprocess, "run"), (os, "system")]


def _counting(monkeypatch, counts: collections.Counter) -> None:
    for mod, name in _IO:
        original = getattr(mod, name)
        key = f"{mod.__name__}.{name}"

        def counted(*a, _original=original, _key=key, **k):
            counts[_key] += 1
            return _original(*a, **k)

        monkeypatch.setattr(mod, name, counted)


def test_the_guard_adds_no_io_on_the_hot_path(tmp_path, monkeypatch) -> None:
    """Design §7: the guard is the host's int compare; memory adds an attribute read and one call. 200 guarded
    formations make exactly the opens/stats/flocks/subprocesses 200 unguarded ones make (delta 0 for every counter),
    and the dispatch stays far under a ceiling generous enough for a loaded CI box."""
    n = 200
    fence = Fence()
    bare = _open("sqlite", tmp_path, name="bare", guarded=False)
    guarded = _open("sqlite", tmp_path, guard=fence, name="guarded")
    for h in (bare, guarded):
        for i in range(3):  # warm: lazy imports and statement caches outside the count
            _form(h.system, f"warm-{i}")
    fence.calls = 0
    measured = {}
    for label, h in (("bare", bare), ("guarded", guarded)):
        counts: collections.Counter = collections.Counter()
        with monkeypatch.context() as m:
            _counting(m, counts)
            t0 = time.perf_counter_ns()
            for i in range(n):
                _form(h.system, f"hot-{i}")
            elapsed = time.perf_counter_ns() - t0
        measured[label] = (counts, elapsed / n)
    assert fence.calls == n                                             # one guard call per formation
    assert measured["guarded"][0] == measured["bare"][0]               # the guard contributed no I/O at all
    for mod, name in _IO:
        assert measured["guarded"][0][f"{mod.__name__}.{name}"] == measured["bare"][0][f"{mod.__name__}.{name}"]
    # The dispatch alone (attribute read + deferral check + the fence's compare), with every I/O counter armed.
    store = guarded.system.store
    calls = 20_000
    counts = collections.Counter()
    with monkeypatch.context() as m:
        _counting(m, counts)
        t0 = time.perf_counter_ns()
        for _ in range(calls):
            guard_commit(store, "store.add")
        per_call = (time.perf_counter_ns() - t0) / calls
    assert sum(counts.values()) == 0
    assert per_call < 50_000, f"guard dispatch {per_call:.0f} ns per commit (ceiling 50 us)"
    assert measured["guarded"][1] < 50_000_000                          # 50 ms per formation: never the guard's
    print(f"\ncommit_guard hot path: dispatch {per_call:.0f} ns/call over {calls}; {n} formations "
          f"bare {measured['bare'][1] / 1000:.0f} us, guarded {measured['guarded'][1] / 1000:.0f} us per commit; "
          f"I/O counters equal: {dict(measured['guarded'][0]) or 'all zero'}")


# ------------------------------------------------------------------------------------------- I6: the closed set


SRC = Path(abstractmemory.__file__).resolve().parent

#: Every function that calls `guard_commit`, with its number of calls (one per branch). A new commit point is added
#: here on purpose; a missing one fails.
COMMIT_POINTS = {
    "journal_sqlite.py:SQLiteJournal._txn": 1,
    "journal_memory.py:InMemoryJournal._write": 1,
    "sqlite_store.py:SQLiteTripleStore.add": 1,
    "sqlite_store.py:SQLiteTripleStore.close_assertion": 1,
    "sqlite_store.py:SQLiteTripleStore.narrow_assertion": 1,
    "sqlite_store.py:SQLiteTripleStore.replace_vectors": 1,
    "sqlite_store.py:SQLiteTripleStore._write_pin": 1,
    "in_memory_store.py:InMemoryTripleStore._write": 1,
    "in_memory_store.py:InMemoryTripleStore._write_pin": 1,
    "lancedb_store.py:LanceDBTripleStore.add": 1,
    "graph/graph.py:_SQLiteBackend.transaction": 1,
    "graph/graph.py:_SQLiteBackend.mark_journal_applied": 1,
    "graph/graph.py:_MemoryBackend.transaction": 1,
    "graph/graph.py:_MemoryBackend.mark_journal_applied": 1,
    "graph/lancedb_backend.py:LanceDBBackend.transaction": 1,
    "graph/lancedb_backend.py:LanceDBBackend.mark_journal_applied": 1,
    "memory_tasks.py:MemoryTaskQueue._txn": 1,
    "memory_tasks.py:form_with_tasks": 2,
    "understanding.py:_apply": 2,
}

#: Transactions that call no guard, each with its reason.
EXEMPT = {
    "journal_sqlite.py:SQLiteJournal._ensure_schema": "opening a home (schema), before any guard is installed",
    "sqlite_store.py:SQLiteTripleStore._create_schema": "opening: keyword backfill of rows already committed",
    "sqlite_store.py:SQLiteTripleStore._upgrade_vector_encoding": "opening: in-place vector encoding upgrade",
    "sqlite_store.py:SQLiteTripleStore._rank_with_matrix": "a READ snapshot (BEGIN .. COMMIT around reads)",
    "sqlite_store.py:SQLiteTripleStore.assertions_after": "a READ snapshot",
    "graph/graph.py:_SQLiteBackend._ensure_graph_schema": "opening: the graph's schema",
    "memory_tasks.py:MemoryTaskQueue._ensure_schema": "opening: the queue's schema",
    "doctoring.py:journal_cold_cut": "offline operator tool writing a NEW file, door closed",
    "doctoring.py:_copy_table": "journal_cold_cut's copy into its new file",
}

#: Calls that route a write through a guarded section (a commit point above).
_ROUTES = {"_txn", "transaction", "_write", "_write_pin", "_insert_prepared"}
_CURSOR_ARGS = {"cur", "cursor", "c", "qcur", "jcur"}


def _functions():
    """(key, node, class name) for every function of the package; key = 'path:Class.func' / 'path:outer.inner'."""
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def walk(node, prefix, cls):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    yield from walk(child, f"{prefix}{child.name}.", child.name)
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{rel}:{prefix}{child.name}", child, cls
                    yield from walk(child, f"{prefix}{child.name}.", cls)
                else:
                    yield from walk(child, prefix, cls)

        yield from walk(tree, "", None)


def _own_nodes(fn):
    """The nodes of `fn`'s own body (nested functions excluded)."""
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _required_args(fn) -> set:
    """Positional parameters without a default (an optional cursor means the function may commit on its own)."""
    args = fn.args.args
    return {a.arg for a in args[:len(args) - len(fn.args.defaults)]}


def _call_name(node) -> Optional[str]:
    if isinstance(node, ast.Call):
        f = node.func
        return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
    return None


def _strings(fn):
    docs = set()
    body = getattr(fn, "body", [])
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        docs.add(id(body[0].value))
    for node in _own_nodes(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            yield node.value
        elif isinstance(node, ast.JoinedStr):
            yield "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))


#: A write statement in the SQL text a function holds (f-string text parts joined: "UPDATE {t} SET" reads
#: "UPDATE  SET").
_WRITE_SQL = re.compile(r"\b(INSERT\s+(OR\s+[A-Z]+\s+)?INTO|UPDATE\s+(\S+\s+)?SET|DELETE\s+FROM)\b")


def test_the_commit_points_are_a_closed_set() -> None:
    """Every function calling the guard is a listed commit point (both ways); every function that runs a COMMIT, or
    is a transaction helper (`_txn`, `transaction`), calls the guard or is exempt with its reason; every function
    holding a write statement is a commit point, writes on a caller's cursor, routes through a guarded helper, is the
    graph transaction's own cursor object (`_SQLiteTx`) or is exempt."""
    functions = list(_functions())
    guarded: Dict[str, int] = collections.Counter()
    problems = []
    for key, fn, cls in functions:
        if all(isinstance(b, ast.Pass) or (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))
               for b in fn.body):
            continue  # a protocol declaration (docstring / `...` / pass): no transaction runs there
        calls = [_call_name(n) for n in _own_nodes(fn)]
        guarded_here = calls.count("guard_commit")
        if guarded_here:
            guarded[key] = guarded_here
        texts = list(_strings(fn))
        commits = "COMMIT" in texts or "commit" in calls
        name = key.rsplit(".", 1)[-1].split(":")[-1]
        if (commits or name in ("_txn", "transaction")) and not guarded_here and key not in EXEMPT:
            problems.append(f"{key}: a write transaction without the guard (add guard_commit before its COMMIT)")
        writes = any(_WRITE_SQL.search(t) for t in texts)
        if writes and not (guarded_here or key in EXEMPT or cls == "_SQLiteTx"
                           or _required_args(fn) & _CURSOR_ARGS or set(calls) & _ROUTES):
            problems.append(f"{key}: writes SQL outside a guarded transaction (no cursor, no commit point)")
    assert dict(guarded) == COMMIT_POINTS, "the guarded commit points changed: update COMMIT_POINTS on purpose"
    assert not problems, "\n".join(problems)
    keys = {k for k, _, _ in functions}
    assert not set(EXEMPT) - keys, f"stale exemptions {sorted(set(EXEMPT) - keys)}"


#: Every method of the doubles without SQL, classified. A new method must be classified on purpose.
DOUBLES = {
    ("in_memory_store.py", "InMemoryTripleStore"): {
        "commit point": {"_write", "_write_pin"},
        "guarded": {"add", "replace_vectors", "close_assertion", "narrow_assertion", "_prepare_add",
                    "_insert_prepared"},
        "inside its caller's guarded write": {"_rewrite_row"},  # understanding._apply; a claim's attempt mirror
        "undo of a refused formation": {"_discard_formed"},
        "read or lifecycle": {"__init__", "embedding_pin", "_stored_row", "close", "assertions_after",
                              "stored_vector", "query"},
    },
    ("journal_memory.py", "InMemoryJournal"): {
        "commit point": {"_write"},
        "guarded": {"append_events", "_append_events_tracked", "append_binding", "_append_binding_tracked",
                    "append_closure", "append_trace", "append_snapshot", "append_valence", "append_version"},
        "undo of a refused formation": {"_discard_formed_bindings", "_discard_formed_events"},
        "read or lifecycle": {"__init__", "events", "bindings", "closures", "traces", "snapshots", "valence_events",
                              "versions", "revision_records", "replay_records", "selected_count",
                              "pair_selected_count", "seq_at", "current_seq", "close"},
    },
    ("lancedb_store.py", "LanceDBTripleStore"): {
        "commit point": {"add"},
        "refuses (NotImplementedError)": {"narrow_assertion", "rewrite_digest_in_place"},
        "read or lifecycle": {"__init__", "close", "query"},
    },
}


@pytest.mark.parametrize("where", sorted(DOUBLES), ids=lambda w: w[1])
def test_every_method_of_the_doubles_is_classified(where) -> None:
    path, cls_name = where
    tree = ast.parse((SRC / path).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    classes = DOUBLES[where]
    listed = set().union(*classes.values())
    assert set(methods) == listed, f"{cls_name}: classify {sorted(set(methods) - listed)} / drop {sorted(listed - set(methods))}"
    for name in classes["commit point"]:
        assert "guard_commit" in [_call_name(n) for n in _own_nodes(methods[name])], f"{cls_name}.{name}"
    for name in classes.get("guarded", ()):
        calls = {_call_name(n) for n in _own_nodes(methods[name])}
        assert calls & (_ROUTES | {"append_binding", "append_events"}), f"{cls_name}.{name} writes outside its guarded section"
