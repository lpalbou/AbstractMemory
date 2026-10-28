"""The connector conformance suite (ADR 0003 decision 3; backlog 0057): every connector behind `MemoryGraph`
(`abstractmemory.graph.backend`) keeps the same invariants, checked through the PUBLIC surface only. Parametrized
over every registered connector: SQLite (the default home), in-memory, LanceDB. A connector that cannot keep an
invariant marks that case `xfail(strict=True)` here with the reason; ADR 0003 and backlog 0057 list those cases
("what the LanceDB connector cannot promise").

Mutants: these cases restate, per connector, invariants whose mutants are listed in test_graph_revisions.py,
test_graph_provenance.py and test_graph_performance.py; the LanceDB-specific ones (applied by hand to
src/abstractmemory/graph/lancedb_backend.py; each turned the named case red):
- `transaction`: the staged plan flushed even when the block raised       -> test_a_failing_revision_leaves_nothing[lancedb-*]
- `_commit`: the log row written AFTER the projections                    -> test_lancedb_repair_finishes_a_half_projected_revision
- `_apply_plan`: plain `add` instead of the keyed merge-insert on repair -> test_lancedb_repair_finishes_a_half_projected_revision
- `revisions_page`: the `status = 'applied'` filter removed               -> test_lancedb_repair_finishes_a_half_projected_revision
- `_rows` / `_all`: `search().where(w).limit(n)` (LanceDB 0.30 applies the limit to scalar-index matches before a
  compound filter's residual part): NOT reproducible on a small table; verified by hand on the 20k bench's history
  table (10,848 rows): 233 (memory, event) lookups returned [] with the limit, 0 without. The read path after a
  compaction is exercised by test_keyed_reads_are_exact_after_compaction.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

from abstractmemory import TripleAssertion, TripleQuery
from abstractmemory.folds import closure_exclusions
from abstractmemory.graph import MemoryGraph, ProvenanceRequired, RevisionOp

from graph_support import BACKENDS, T, art, claim, close, mind_dump, narrow, open_home, prov, rev, step

LANCEDB_CROSS_PROCESS = pytest.mark.xfail(
    strict=True, reason="LanceDB: nothing serializes writers of one mind across processes (no cross-table "
                        "transaction, no shared lock): two processes allocate the same seq and the feed breaks")


@pytest.fixture(params=BACKENDS)
def home(request, tmp_path: Path):
    h = open_home(tmp_path, request.param)
    yield h
    h.close()


def _seed(home) -> None:
    home.graph.apply_revision(rev(
        "r-seed", claim("a-open", valid_from=T(1)), claim("b-open", o="ex:globex", valid_from=T(2)),
        claim("c-bounded", o="ex:initech", valid_from=T(1), valid_until=T(9)),
        provenance=prov(step("run-1", 1), art("note-1", "run-1"))))


class _Crash:
    """A transaction whose `where` operation dies (a crash in the middle of a revision)."""

    def __init__(self, tx, where: str) -> None:
        self._tx, self._where = tx, where

    def __getattr__(self, name):
        if name == self._where:
            def _die(*a, **k):
                raise RuntimeError(f"simulated crash in {name}")
            return _die
        return getattr(self._tx, name)


@pytest.mark.parametrize("where", ["insert_assertions", "end_row", "add_history", "add_source", "insert_revision"])
def test_a_failing_revision_leaves_nothing(home, where: str, monkeypatch) -> None:
    _seed(home)
    before = mind_dump(home)
    real = home.graph._b.transaction

    @contextmanager
    def crashing():
        with real() as tx:
            yield _Crash(tx, where)

    monkeypatch.setattr(home.graph._b, "transaction", crashing)
    with pytest.raises(RuntimeError, match="simulated crash"):
        home.graph.apply_revision(rev("r-x", claim("x-new", o="ex:new"),
                                      close("a-open", T(5), kind="supersede", replacement_ids=["x-new"])))
    monkeypatch.undo()
    assert mind_dump(home) == before
    # and the mind still works (its counters were given back): the same revision applies once
    assert home.graph.apply_revision(rev("r-x", claim("x-new", o="ex:new"))).seq == 2


def test_idempotent_on_revision_id(home) -> None:
    _seed(home)
    first = home.graph.apply_revision(rev("r-2", close("a-open", T(5)), claim("e-1", o="ex:e")))
    before = mind_dump(home)
    again = home.graph.apply_revision(rev("r-2", claim("other", o="ex:other")))
    assert (again.applied, again.seq, again.assertion_ids, again.closed) == (False, first.seq, ["e-1"], ["a-open"])
    assert mind_dump(home) == before


def test_provenance_rules(home) -> None:
    _seed(home)
    home.store.add([TripleAssertion(subject="ex:z", predicate="ex:p", object="ex:q", scope="global",
                                    owner_id="abstractnote", assertion_id="outside-1")])
    before = mind_dump(home)
    for bad in (rev("r-x", claim("x", provenance=prov())),                                   # neither
                rev("r-x", claim("x", provenance=prov(derived=["ghost"]))),                  # chain to nothing
                rev("r-x", claim("x", provenance=prov(derived=["x"]))),                      # self
                rev("r-x", claim("x", provenance=prov(derived=["a-open"])), owner_id="entity:other"),  # cross-owner
                rev("r-x", close("outside-1", T(4))),                                        # not adopted
                rev("r-x", close("a-open", T(3)), provenance=prov(derived=["a-open"]))):     # self-justified close
        with pytest.raises(ProvenanceRequired):
            home.graph.apply_revision(bad)
        assert mind_dump(home) == before


def test_close_narrow_and_active_at_agree(home) -> None:
    _seed(home)
    result = home.graph.apply_revision(rev(
        "r-2", claim("a-next", o="ex:umbrella", valid_from=T(6)),
        close("a-open", T(6), kind="supersede", replacement_ids=["a-next"]), narrow("c-bounded", T(4)),
        close("c-bounded", T(12), kind="retract"), cause="reinterpret"))
    assert result.closed == ["a-open", "c-bounded"] and result.narrowed == ["c-bounded"]
    at = {T(m): {a.assertion_id for a in home.store.query(TripleQuery(active_at=T(m), limit=0))} for m in (3, 5, 7)}
    assert at[T(3)] == {"a-open", "b-open", "c-bounded"}
    assert at[T(5)] == {"a-open", "b-open"} and at[T(7)] == {"a-next", "b-open"}
    closures = home.journal.closures(limit=0)
    assert {c.assertion_id for c in closures} == {"a-open", "c-bounded"}
    assert {"a-open", "c-bounded"} <= closure_exclusions(home.journal, max(c.seq for c in closures))
    with pytest.raises(ValueError, match="open window"):
        home.graph.apply_revision(rev("r-x", narrow("b-open", T(3))))


def test_re_observation_not_duplication(home) -> None:
    ops = lambda: (RevisionOp("assert", {"subject": "ex:alice", "predicate": "schema:knows", "object": "ex:bob"}),)
    first = home.graph.apply_revision(rev("run-1", *ops(), provenance=prov(step("run-1", 3))))
    second = home.graph.apply_revision(rev("run-2", *ops(), provenance=prov(step("run-2", 5))))
    assert second.re_observed == first.assertion_ids and second.assertion_ids == []
    assert len(home.store.query(TripleQuery(subject="ex:alice", limit=0))) == 1
    held = first.assertion_ids[0]
    assert [e["event"] for e in home.graph.history(held)] == ["asserted", "re-observed"]
    assert [d["ref"].key() for d in home.graph.sources_of(held, labelled=True)] == ["step:run-1#3", "step:run-2#5"]


def test_history_sources_lineage_and_owner_gate(home) -> None:
    _seed(home)
    home.graph.apply_revision(rev(
        "r-derive", claim("pattern", o="ex:pattern", provenance=prov(derived=["a-open"], actor="abstractmemory:sleep")),
        cause="maintenance", provenance=prov(step("run-sleep", 4), actor="abstractmemory:sleep")))
    home.graph.apply_revision(rev("r-close", close("a-open", T(5)), cause="person", provenance=prov(step("run-9", 1))))
    assert [(h["event"], h["revision_id"], h["cause"]) for h in home.graph.history("a-open")] == [
        ("asserted", "r-seed", "ingest"), ("closed", "r-close", "person")]
    labelled = home.graph.sources_of("pattern", transitive=False, labelled=True)
    assert [(d["ref"].key(), d["via"]) for d in labelled] == [("step:run-sleep#4", "revision")]
    assert [r.key() for r in home.graph.sources_of("pattern")] == ["step:run-sleep#4", "step:run-1#1",
                                                                    "artifact:note-1"]
    assert home.graph.derived_from_source(step("run-1", 1)) == ["a-open", "b-open", "c-bounded", "pattern"]
    assert home.graph.derived_from_source({"kind": "run", "run_id": "run-1"}, limit=2) == ["a-open", "b-open"]
    assert home.graph.names_ref(art("note-1"), ["abstractnote"]) is True
    assert home.graph.names_ref(art("note-1"), ["entity:x"]) is False
    assert home.graph.names_ref({"kind": "run", "run_id": "run-sleep"}, ["abstractnote"]) is True


def test_record_time_is_the_stores(home) -> None:
    result = home.graph.apply_revision(rev("r-back", claim("back"), recorded_at="2020-01-01T00:00:00+00:00"))
    assert result.recorded_at > "2026" and home.graph.revisions()[0][0].recorded_at == result.recorded_at


def test_change_feed_is_lossless_under_a_concurrent_writer(home, tmp_path: Path) -> None:
    if home.kind == "memory":
        writer = MemoryGraph(home.store, home.journal)
    else:
        writer = MemoryGraph(type(home.store)(home.store._path) if home.kind == "sqlite"
                             else type(home.store)(home.path), home.journal)
    total, written = 40, []

    def _write() -> None:
        for i in range(total):
            writer.apply_revision(rev(f"rev-{i:03d}", claim(f"m-{i}", o=f"ex:o{i}"), provenance=prov(step("w", i + 1))))
            written.append(f"rev-{i:03d}")

    thread = threading.Thread(target=_write)
    thread.start()
    seen, cursor, deadline = [], None, time.monotonic() + 60
    while time.monotonic() < deadline:
        page, cursor = home.graph.revisions(after=cursor, limit=7)
        seen.extend(r.revision_id for r in page)
        if not page and not thread.is_alive() and len(seen) >= len(written):
            break
    thread.join()
    assert seen == written == [f"rev-{i:03d}" for i in range(total)]


_CHILD = textwrap.dedent('''
    import sys, time, warnings
    warnings.simplefilter("ignore")
    sys.path[:0] = [{src!r}, {tests!r}]
    from graph_support import claim, prov, rev, step
    from abstractmemory import LanceDBTripleStore, SQLiteJournal, SQLiteTripleStore
    from abstractmemory.graph import MemoryGraph
    kind, path, flag, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    store = SQLiteTripleStore(path) if kind == "sqlite" else LanceDBTripleStore(path)
    graph = MemoryGraph(store, SQLiteJournal(path + ".child-journal"))
    graph.revisions(limit=1)
    if kind == "lancedb":
        graph._b.state.counter_values()
    open(flag + ".ready", "w").close()
    while not __import__("os").path.exists(flag):
        time.sleep(0.01)
    for i in range(n):
        graph.apply_revision(rev(f"child-{{i:03d}}", claim(f"child-{{i}}", o=f"ex:c{{i}}"), provenance=prov(step("c", i + 1))))
''')


@pytest.mark.parametrize("kind", ["sqlite", pytest.param("lancedb", marks=LANCEDB_CROSS_PROCESS)])
def test_two_processes_write_one_mind(tmp_path: Path, kind: str) -> None:
    """Writers in two processes: the log holds every revision once, in a seq order without gaps or repeats."""
    home = open_home(tmp_path, kind)
    path = str(home.store._path if kind == "sqlite" else home.path)
    here = Path(__file__).resolve().parent
    script = tmp_path / "child.py"
    script.write_text(_CHILD.format(src=str(here.parent / "src"), tests=str(here)))
    flag = str(tmp_path / "go")
    home.graph.revisions(limit=1)
    if kind == "lancedb":
        home.graph._b.state.counter_values()
    child = subprocess.Popen([sys.executable, str(script), kind, path, flag, "25"])
    while not os.path.exists(flag + ".ready"):
        time.sleep(0.01)
    open(flag, "w").close()
    for i in range(25):
        home.graph.apply_revision(rev(f"main-{i:03d}", claim(f"main-{i}", o=f"ex:m{i}"), provenance=prov(step("m", i + 1))))
    assert child.wait(timeout=120) == 0
    ids, cursor = [], None
    for _ in range(50):  # one revision per seq: a page of 1 holds exactly one revision
        page, cursor = home.graph.revisions(after=cursor, limit=1)
        assert len(page) == 1, [r.revision_id for r in page]
        ids.append(page[0].revision_id)
    assert len(set(ids)) == 50 and home.graph.revisions(after=cursor)[0] == []
    assert all(home.graph.history(f"{who}-{i}") for who in ("main", "child") for i in range(25))
    home.close()


def test_replay_into_an_empty_mind_equals_the_original(home, tmp_path: Path) -> None:
    _seed(home)
    home.graph.apply_revision(rev("r-2", claim("a2", o="ex:umbrella", valid_from=T(5)),
                                  close("a-open", T(5), kind="supersede", replacement_ids=["a2"]),
                                  narrow("c-bounded", T(4)), cause="reinterpret", provenance=prov(step("run-2", 4))))
    home.graph.apply_revision(rev("r-3", claim("insight", s="ex:dana", p="ex:pattern", o="ex:moves",
                                               provenance=prov(derived=["a2"], actor="abstractmemory:sleep")),
                                  cause="maintenance", provenance=prov(derived=["a2"], actor="abstractmemory:sleep")))
    home.graph.apply_revision(rev("r-4", claim("again", valid_from=T(2), o="ex:globex", s="ex:dana"),
                                  provenance=prov(step("run-3", 1))))  # re-observes b-open
    target = open_home(tmp_path, home.kind, name="replayed")
    assert home.graph.replay_into(target.graph) == 4
    assert mind_dump(target) == mind_dump(home)
    memory = open_home(tmp_path, "memory", name="as-memory")
    home.graph.replay_into(memory.graph)
    assert mind_dump(memory) == mind_dump(home)
    target.close()


def test_opening_a_mind_is_a_read(home, tmp_path: Path) -> None:
    _seed(home)
    if home.kind == "memory":
        before = mind_dump(home)
        MemoryGraph(home.store, home.journal)
        assert mind_dump(home) == before
        return
    root = Path(home.path)
    if home.kind == "sqlite":  # every row of every table (WAL readers touch the -shm file, never the data)
        from graph_support import file_state

        snapshot = lambda: file_state(root)
    else:  # LanceDB: any write adds a version / data file
        snapshot = lambda: sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    home.close()
    before = snapshot()
    if home.kind == "lancedb":
        from abstractmemory import LanceDBTripleStore
        from abstractmemory.graph import lancedb_backend

        lancedb_backend._STATES.clear()  # what another process sees: no shared state
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            graph = MemoryGraph(LanceDBTripleStore(root))
    else:
        from abstractmemory import SQLiteTripleStore

        graph = MemoryGraph(SQLiteTripleStore(root))
    assert graph.history("a-open")[0]["revision_id"] == "r-seed"
    assert snapshot() == before


def test_lancedb_repair_finishes_a_half_projected_revision(tmp_path: Path, monkeypatch) -> None:
    """LanceDB writes its log FIRST: a crash between the projections leaves a `pending` revision, which the next
    transaction (or MemoryGraph.repair) re-derives from the log; the result equals a clean apply."""
    home = open_home(tmp_path, "lancedb")
    _seed(home)
    backend = home.graph._b
    real = backend._apply_plan
    calls = {"n": 0}

    def crash_after_triples(plan, fresh=False):
        calls["n"] += 1
        if calls["n"] == 1:
            rows_only = dict(plan, updates={}, history=[], provenance=[], derivations=[])
            real(rows_only, fresh=fresh)
            raise RuntimeError("power cut after the triple rows")
        return real(plan, fresh=fresh)

    monkeypatch.setattr(backend, "_apply_plan", crash_after_triples)
    with pytest.raises(RuntimeError, match="power cut"):
        home.graph.apply_revision(rev("r-2", claim("x", o="ex:x"), close("a-open", T(5))))
    assert [r.revision_id for r in home.graph.revisions()[0]] == ["r-seed"]  # the feed shows applied ones only
    assert home.graph.repair() >= 1
    clean = open_home(tmp_path, "sqlite", name="clean")
    home.graph.replay_into(clean.graph)
    assert mind_dump(clean)["rows"] == mind_dump(home)["rows"]
    assert [r.revision_id for r in home.graph.revisions()[0]] == ["r-seed", "r-2"]
    assert home.graph.history("x")[0]["revision_id"] == "r-2"
    home.close()


@pytest.mark.xfail(strict=True, reason="LanceDB: no cross-table transaction: a crash during the projection leaves "
                                       "rows of an unapplied revision visible to readers until repair()")
def test_lancedb_a_crash_mid_projection_is_invisible_before_repair(tmp_path: Path, monkeypatch) -> None:
    home = open_home(tmp_path, "lancedb")
    _seed(home)
    before = home.store.query(TripleQuery(limit=0))
    backend = home.graph._b
    real = backend._apply_plan

    def crash(plan, fresh=False):
        real(dict(plan, updates={}, history=[], provenance=[], derivations=[]), fresh=fresh)
        raise RuntimeError("power cut")

    monkeypatch.setattr(backend, "_apply_plan", crash)
    with pytest.raises(RuntimeError):
        home.graph.apply_revision(rev("r-2", claim("x", o="ex:x")))
    assert len(home.store.query(TripleQuery(limit=0))) == len(before)


def test_keyed_reads_are_exact_after_compaction(home) -> None:
    """A memory with two history events, read by (memory, event) after the connector compacted and indexed its tables
    (found by the 20k bench: LanceDB 0.30 dropped the row when the first indexed match failed the residual filter)."""
    home.graph.apply_revision(rev("r-1", claim("m", valid_from=T(1), valid_until=T(9))))
    home.graph.apply_revision(rev("r-2", close("m", T(12), kind="retract")))
    if home.kind == "lancedb":
        home.graph._b.state.compact()
    assert home.graph.apply_revision(rev("r-3", narrow("m", T(4)))).narrowed == ["m"]  # needs memory_known("m")
    assert [e["event"] for e in home.graph.history("m")] == ["asserted", "closed", "narrowed"]
