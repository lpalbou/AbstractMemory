"""The revision log (ADR 0003 decisions 6-7, "Validation"; contract §3): ops, idempotency, atomic rollback, history,
window/closure agreement, the lossless change feed, replay, repair. Every test runs on real stores (tmp_path).

Mutants (each applied by hand to src/abstractmemory/graph/graph.py, the named test watched go red, then reverted):
- `_SQLiteBackend.transaction`: ROLLBACK replaced by COMMIT                     -> test_a_failing_op_rolls_back_the_whole_revision[sqlite*]
- `_MemoryBackend.transaction`: `tx.rollback()` removed                         -> test_a_failing_op_rolls_back_the_whole_revision[memory]
- `_SQLiteTx.write_closure`: `self.b.journal.append_closure(closure)` (the journal's own transaction) instead of
  `_append_closure_on(self.cur, ...)`                                         -> test_a_failing_op_rolls_back_the_whole_revision[sqlite]
- `apply_revision`: the in-transaction `revision_seq` idempotency check AND the pre-check removed
                                                                               -> test_a_revision_is_idempotent_on_its_id[*]
- `apply_revision`: the `close` branch's `tx.write_closure`/pending append removed -> test_close_writes_the_window_and_the_closure_together[*]
- `_SQLiteTx.close_row`: UPDATE removed (returns True)                         -> test_close_writes_the_window_and_the_closure_together[sqlite*]
- `apply_revision`: `closing_revision` skip removed (a second close writes a second closure)
                                                                               -> test_a_memory_is_closed_once_and_a_bounded_window_is_kept[*]
- `_SQLiteBackend.revisions_page`: `seq > ?` -> `seq >= ?`                     -> test_change_feed_is_lossless_under_a_concurrent_writer[sqlite]
- `MemoryGraph.revisions`: next cursor = `str(position + n)`                   -> test_change_feed_is_lossless_under_a_concurrent_writer[*]
- `replay_into`: returns after the first page                                  -> test_replay_into_an_empty_store_equals_the_original
- `_SQLiteTx.insert_revision`: `recorded_at` stored as now                     -> test_replay_into_an_empty_store_equals_the_original
- `repair`: `mark_journal_applied` removed                                    -> test_repair_appends_what_a_crash_left_behind[*]
- `_closure_record`: `closure_id` = uuid4 (non-deterministic)                  -> test_repair_appends_what_a_crash_left_behind[*]
- `apply_revision`: the "named before the op that asserts it" check removed   -> test_ops_apply_in_order
"""
from __future__ import annotations

import threading
import time
import warnings
from pathlib import Path

import pytest

from abstractmemory import InMemoryJournal, SQLiteJournal, TripleQuery
from abstractmemory.folds import closure_exclusions
from abstractmemory.graph import MAX_READ_LIMIT, MemoryGraph, ProvenanceRequired, Revision

from graph_support import (
    KINDS,
    T,
    art,
    claim,
    close,
    home_state,
    file_state,
    narrow,
    open_home,
    prov,
    rev,
    step,
    store_dump,
)


@pytest.fixture(params=KINDS)
def home(request, tmp_path: Path):
    h = open_home(tmp_path, request.param)
    yield h
    h.close()


def _row(store, aid: str):
    [row] = store.query(TripleQuery(assertion_ids=(aid,)))
    return row


def _seed(home) -> None:
    """Two open claims and one asserted with a bounded window."""
    home.graph.apply_revision(rev(
        "r-seed",
        claim("a-open", valid_from=T(1)),
        claim("b-open", o="ex:globex", valid_from=T(2)),
        claim("c-bounded", o="ex:initech", valid_from=T(1), valid_until=T(9)),
        provenance=prov(step("run-1", 1), art("note-1", "run-1")),
    ))


def test_ops_apply_and_report(home) -> None:
    _seed(home)
    result = home.graph.apply_revision(rev(
        "r-2",
        claim("d-new", o="ex:umbrella", valid_from=T(6)),
        close("a-open", T(6), kind="supersede", replacement_ids=["d-new"], reason="moved to Umbrella"),
        narrow("c-bounded", T(4)),
        cause="reinterpret", occurred_at=T(6),
    ))
    assert result.applied and result.seq == 2
    assert result.assertion_ids == ["d-new"] and result.closed == ["a-open"] and result.narrowed == ["c-bounded"]
    assert result.skipped == []
    assert _row(home.store, "a-open").valid_until == T(6)
    assert _row(home.store, "c-bounded").valid_until == T(4)
    assert _row(home.store, "d-new").observed_at == T(6)  # the claim's observation time is the revision's
    # Skips are reported, not silent: a re-assert, a second close, a narrow that would not move the window earlier.
    again = home.graph.apply_revision(rev(
        "r-3", claim("d-new", o="ex:umbrella", valid_from=T(6)), close("a-open", T(7)), narrow("c-bounded", T(5)),
        cause="person"))
    assert again.applied and again.assertion_ids == [] and again.closed == [] and again.narrowed == []
    assert [s["op"] for s in again.skipped] == ["assert", "close", "narrow"]
    assert _row(home.store, "c-bounded").valid_until == T(4)  # never widened


def test_ops_apply_in_order(home) -> None:
    _seed(home)
    before = home_state(home)
    with pytest.raises(ValueError, match="before the op that asserts it"):
        home.graph.apply_revision(rev("r-bad", close("x-1", T(3)), claim("x-1", valid_from=T(2))))
    assert home_state(home) == before
    ok = home.graph.apply_revision(rev("r-ok", claim("x-1", valid_from=T(2)), close("x-1", T(3))))
    assert ok.closed == ["x-1"] and _row(home.store, "x-1").valid_until == T(3)


def test_a_revision_is_idempotent_on_its_id(home) -> None:
    _seed(home)
    first = home.graph.apply_revision(rev("r-2", close("a-open", T(5)), claim("e-1", o="ex:e")))
    before = home_state(home)
    again = home.graph.apply_revision(rev("r-2", close("a-open", T(5)), claim("e-1", o="ex:e")))
    assert (again.applied, again.seq) == (False, first.seq)
    assert again.assertion_ids == [] and again.closed == []
    # Same id, different content: the first write wins (the id is the identity), nothing changes.
    other = home.graph.apply_revision(rev("r-2", claim("e-2", o="ex:other")))
    assert other.applied is False
    assert home_state(home) == before
    # A second graph over the same store sees the same log (the SQLite tables or the shared in-memory state).
    assert MemoryGraph(home.store, home.journal).apply_revision(rev("r-2", claim("e-3"))).applied is False


def test_a_failing_op_rolls_back_the_whole_revision(home) -> None:
    _seed(home)
    before = home_state(home)
    n_closures = len(home.journal.closures(limit=0))
    # assert + close (window + same-file journal closure) + history ... then a narrow of an OPEN window refuses.
    with pytest.raises(ValueError, match="cannot widen or close an open window"):
        home.graph.apply_revision(rev(
            "r-fail",
            claim("f-new", o="ex:new"),
            close("a-open", T(5), kind="supersede", replacement_ids=["f-new"]),
            narrow("b-open", T(3)),
        ))
    assert home_state(home) == before
    assert len(home.journal.closures(limit=0)) == n_closures
    assert _row(home.store, "a-open").valid_until is None
    assert home.graph.history("f-new") == [] and home.graph.revisions()[0][-1].revision_id == "r-seed"
    # An op naming an unknown assertion rolls back the same way.
    with pytest.raises(ValueError, match="unknown assertion"):
        home.graph.apply_revision(rev("r-fail-2", claim("g-new"), close("nope", T(5))))
    assert home_state(home) == before
    # The failed ids stay free: the same revision id applies once fixed.
    assert home.graph.apply_revision(rev("r-fail", claim("f-new", o="ex:new"))).applied


def test_history_shows_assert_narrow_close_with_revision_ids_and_causes(home) -> None:
    _seed(home)
    home.graph.apply_revision(rev("r-narrow", narrow("c-bounded", T(4)), cause="reinterpret", occurred_at=T(10)))
    home.graph.apply_revision(rev("r-close", close("c-bounded", T(11), kind="retract", reason="never true"),
                                  cause="person", occurred_at=T(11)))
    history = home.graph.history("c-bounded")
    assert [(h["event"], h["revision_id"], h["cause"]) for h in history] == [
        ("asserted", "r-seed", "ingest"), ("narrowed", "r-narrow", "reinterpret"), ("closed", "r-close", "person"),
    ]
    assert history[0]["detail"]["sources"] == ["step:run-1#1", "artifact:note-1"]
    assert history[1]["detail"]["previous_valid_until"] == T(9) and history[1]["detail"]["valid_until"] == T(4)
    assert history[2]["detail"]["kind"] == "retract" and history[2]["detail"]["window_closed"] is False
    assert history[2]["detail"]["row_valid_until"] == T(4)
    assert [h["at"] for h in history] == sorted(h["at"] for h in history)  # record time order
    assert home.graph.history("c-bounded", limit=1) == history[:1]
    assert home.graph.history("never-written") == []


def test_close_writes_the_window_and_the_closure_together(home) -> None:
    _seed(home)
    result = home.graph.apply_revision(rev(
        "r-sup", claim("a-next", o="ex:umbrella", valid_from=T(6)),
        close("a-open", T(6), kind="supersede", replacement_ids=["a-next"], reason="moved"),
        cause="reinterpret", occurred_at=T(6)))
    # Event time: TripleQuery(active_at=) sees the window.
    active_after = {a.assertion_id for a in home.store.query(TripleQuery(active_at=T(7), limit=0))}
    active_before = {a.assertion_id for a in home.store.query(TripleQuery(active_at=T(5), limit=0))}
    assert "a-open" not in active_after and "a-open" in active_before and "a-next" in active_after
    # Ranked recall folds the journal: the closure is there, with its cause and successor.
    [closure] = home.journal.closures(assertion_id="a-open", limit=0)
    assert closure.kind == "supersede" and closure.replacement_ids == ("a-next",)
    assert closure.provenance["revision_id"] == "r-sup" and closure.provenance["cause"] == "reinterpret"
    assert closure.actor == "abstractnote"
    seq_now = max(c.seq for c in home.journal.closures(limit=0))
    assert "a-open" in closure_exclusions(home.journal, seq_now)
    # Agreement over the whole store: a memory the graph closed has a closed window AND a closure, and vice versa.
    closed_ids = {c.assertion_id for c in home.journal.closures(limit=0)}
    windows = {a.assertion_id: a.valid_until for a in home.store.query(TripleQuery(limit=0))}
    assert closed_ids == {"a-open"} and windows["a-open"] == T(6) and windows["b-open"] is None
    assert result.closed == ["a-open"]
    if home.kind == "sqlite":  # one file, one transaction: nothing awaits repair
        assert home.graph.repair() == 0


def test_a_memory_is_closed_once_and_a_bounded_window_is_kept(home) -> None:
    _seed(home)
    first = home.graph.apply_revision(rev("r-c1", close("c-bounded", T(12), kind="retract")))
    assert first.closed == ["c-bounded"]
    assert _row(home.store, "c-bounded").valid_until == T(9)  # the claim's own bound is kept
    second = home.graph.apply_revision(rev("r-c2", close("c-bounded", T(3), kind="supersede",
                                                          replacement_ids=["a-open"])))
    assert second.closed == [] and "r-c1" in second.skipped[0]["why"]
    assert len(home.journal.closures(assertion_id="c-bounded", limit=0)) == 1


@pytest.mark.parametrize("kind", ["sqlite", "memory"])
def test_change_feed_is_lossless_under_a_concurrent_writer(tmp_path: Path, kind: str) -> None:
    reader = open_home(tmp_path, kind)
    # The second writer: its own store/connection on the same file (SQLite), or the same store object (memory).
    if kind == "sqlite":
        from abstractmemory import SQLiteTripleStore

        writer_store = SQLiteTripleStore(reader.path)
        writer = MemoryGraph(writer_store, SQLiteJournal(reader.path))
    else:
        writer_store, writer = reader.store, MemoryGraph(reader.store, reader.journal)
    total = 120
    written: list = []

    def _write() -> None:
        for i in range(total):
            rid = f"rev-{i:04d}"
            writer.apply_revision(rev(rid, claim(f"m-{i}", o=f"ex:o{i}"),
                                      provenance=prov(step("run-w", i))))
            written.append(rid)
            if i % 10 == 0:
                time.sleep(0.001)

    thread = threading.Thread(target=_write)
    thread.start()
    seen: list = []
    cursor = None
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        page, cursor = reader.graph.revisions(after=cursor, limit=7)
        seen.extend(r.revision_id for r in page)
        if not page and not thread.is_alive() and len(seen) >= len(written):
            break
    thread.join()
    page, cursor = reader.graph.revisions(after=cursor, limit=7)
    seen.extend(r.revision_id for r in page)
    assert seen == written == [f"rev-{i:04d}" for i in range(total)]
    assert reader.graph.revisions(after=cursor) == ([], cursor)  # an idle cursor stays put
    with pytest.raises(ValueError):
        reader.graph.revisions(after="not-a-cursor")
    if kind == "sqlite":
        writer_store.close()
    reader.close()


def _rich_log(graph: MemoryGraph, n_bulk: int) -> None:
    """A log with every op, derived memories, a digest record, and more revisions than one replay page."""
    graph.apply_revision(rev(
        "r-0", claim("a", valid_from=T(1)), claim("b", o="ex:globex", valid_from=T(1), valid_until=T(9)),
        claim("note-digest", s="ex:note-1", p="dcterms:abstract", o="dana joined acme", attributes={"literal": True}),
        provenance=prov(step("run-1", 1, "st-1"), art("note-1", "run-1")), summary="first note"))
    graph.apply_revision(rev(
        "r-1", claim("a2", o="ex:umbrella", valid_from=T(5)),
        close("a", T(5), kind="supersede", replacement_ids=["a2"], ripple_source="note-digest", ripple_hops=1),
        narrow("b", T(4)), cause="reinterpret", occurred_at=T(5), provenance=prov(step("run-2", 4))))
    graph.apply_revision(rev(
        "r-2", claim("insight", s="ex:dana", p="ex:careerPattern", o="ex:moves-often",
                     provenance=prov(derived=["a", "a2", "ex:note-1"], actor="abstractmemory:sleep")),
        cause="maintenance", provenance=prov(derived=["a2"], actor="abstractmemory:sleep")))
    for i in range(n_bulk):
        graph.apply_revision(rev(f"bulk-{i:04d}", claim(f"bulk-{i}", s=f"ex:s{i % 7}", o=f"ex:o{i}"),
                                 provenance=prov(step("run-bulk", i)), occurred_at=T(2, 1 + i % 27)))


def _graph_dump(graph: MemoryGraph, ids) -> dict:
    revs, cursor = [], None
    while True:
        page, cursor = graph.revisions(after=cursor, limit=MAX_READ_LIMIT)
        if not page:
            break
        revs.extend(r.to_dict() for r in page)
    return {
        "rows": store_dump(graph.store),
        "revisions": revs,
        "history": {i: graph.history(i) for i in ids},
        "sources": {i: [s.to_dict() for s in graph.sources_of(i)] for i in ids},
        "direct": {i: [s.to_dict() for s in graph.sources_of(i, transitive=False)] for i in ids},
        "derived": [graph.derived_from_source(k) for k in (
            {"kind": "run", "run_id": "run-1"}, {"kind": "run", "run_id": "run-2"}, step("run-1", 1),
            art("note-1"), {"kind": "run", "run_id": "run-bulk"})],
    }


def test_replay_into_an_empty_store_equals_the_original(tmp_path: Path) -> None:
    original = open_home(tmp_path, "sqlite", "original")
    _rich_log(original.graph, n_bulk=130)  # 133 revisions: more than one replay page (100)
    target = open_home(tmp_path, "sqlite", "replayed")
    assert original.graph.replay_into(target.graph) == 133
    # The whole file: triples, FTS shadow tables, the four memg_* tables, the journal's closures and seq counter.
    assert file_state(target.path) == file_state(original.path)
    ids = ["a", "a2", "b", "note-digest", "insight", "ex:note-1", "bulk-0", "bulk-129"]
    dump = _graph_dump(original.graph, ids)
    assert _graph_dump(target.graph, ids) == dump
    assert original.graph.replay_into(target.graph) == 0  # resumable: already-present ids are no-ops
    # Across backends: the in-memory replay reads the same.
    mem = open_home(tmp_path, "memory")
    assert original.graph.replay_into(mem.graph) == 133
    assert _graph_dump(mem.graph, ids) == dump
    assert original.graph.replay_into(MemoryGraph(original.store)) == 0  # into itself: every id already there
    for h in (original, target, mem):
        h.close()


def _crash_first_append(base):
    """A real journal class whose first closure append dies (the process crash between the store commit and the
    off-file journal append, ADR 0003 atomicity note)."""

    class _Crashing(base):
        crashes = 1

        def append_closure(self, closure):
            if self.crashes:
                self.crashes -= 1
                raise RuntimeError("simulated crash before the journal append")
            return super().append_closure(closure)

    return _Crashing


_CrashingJournal = _crash_first_append(SQLiteJournal)


@pytest.mark.parametrize("kind", ["sqlite-offfile", "memory"])
def test_repair_appends_what_a_crash_left_behind(tmp_path: Path, kind: str) -> None:
    home = open_home(tmp_path, kind)
    _seed(home)
    if kind == "memory":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            journal = _crash_first_append(InMemoryJournal)()
    else:
        journal = _CrashingJournal(home.journal_path)
    graph = MemoryGraph(home.store, journal)
    with pytest.raises(RuntimeError, match="simulated crash"):
        graph.apply_revision(rev("r-close", close("a-open", T(5)), close("b-open", T(5), kind="supersede",
                                                                      replacement_ids=["a-open"])))
    # The store transaction committed: windows closed, revision logged; the journal never heard of it.
    assert _row(home.store, "a-open").valid_until == T(5)
    assert [r.revision_id for r in graph.revisions()[0]] == ["r-seed", "r-close"]
    assert journal.closures(limit=0) == []
    assert graph.repair() == 1
    closures = sorted(journal.closures(limit=0), key=lambda c: c.assertion_id)
    assert [(c.assertion_id, c.kind) for c in closures] == [("a-open", "retract"), ("b-open", "supersede")]
    assert closures[0].provenance["revision_id"] == "r-close"
    assert graph.repair() == 0  # marked applied
    # Idempotent even if the mark were lost: re-appending the same deterministic closure ids is a no-op.
    from abstractmemory.graph.graph import _closure_record

    replayed = graph.revisions()[0][1]
    for op in replayed.ops:
        journal.append_closure(_closure_record(replayed, op.payload))
    assert len(journal.closures(limit=0)) == 2
    journal.close()
    home.close()


def test_repair_without_a_journal_is_loud(tmp_path: Path) -> None:
    home = open_home(tmp_path, "sqlite-offfile")
    _seed(home)
    journal = _CrashingJournal(home.journal_path)
    with pytest.raises(RuntimeError):
        MemoryGraph(home.store, journal).apply_revision(rev("r-x", close("a-open", T(5))))
    with pytest.raises(RuntimeError, match="no journal is attached"):
        MemoryGraph(home.store).repair()
    journal.close()
    home.close()


@pytest.mark.parametrize("bad", [0, -1, True, 2.5, None])
def test_every_read_is_bounded(home, bad) -> None:
    _seed(home)
    for read in (lambda: home.graph.history("a-open", limit=bad),
                 lambda: home.graph.sources_of("a-open", limit=bad),
                 lambda: home.graph.derived_from_source(step("run-1", 1), limit=bad),
                 lambda: home.graph.revisions(limit=bad),
                 lambda: home.graph.repair(limit=bad)):
        with pytest.raises(ValueError, match="bounded"):
            read()


def test_reads_honour_their_limit(home) -> None:
    home.graph.apply_revision(rev("r-many", *[claim(f"m{i}", o=f"ex:o{i}") for i in range(12)],
                                  provenance=prov(step("run-1", 1), step("run-1", 2), art("x", "run-1"))))
    assert len(home.graph.derived_from_source(step("run-1", 1), limit=5)) == 5
    assert home.graph.derived_from_source({"kind": "run", "run_id": "run-1"}, limit=5) == [f"m{i}" for i in range(5)]
    assert len(home.graph.sources_of("m0", limit=2)) == 2
    page, cursor = home.graph.revisions(limit=MAX_READ_LIMIT + 50)
    assert len(page) == 1 and cursor == "1"
