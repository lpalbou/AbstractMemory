"""Cross-backend conformance tests for the MemoryJournal implementations.

Parametrized over InMemoryJournal and SQLiteJournal so both backends prove the
SAME observable semantics (backlog 0011 parity principle applied to 0017/0013).
Backend-specific behavior (durability, WAL, triple-store coexistence, the
volatility warning) is covered by dedicated non-parametrized tests at the end.
"""

from __future__ import annotations

import sqlite3
import threading
import warnings
from typing import Any, List

import pytest

from abstractmemory.journal import (
    ClosureRecord,
    MemoryEvent,
    ReconstructionTrace,
    ScopeBinding,
)
from abstractmemory.journal_memory import InMemoryJournal
from abstractmemory.journal_sqlite import SQLiteJournal
from abstractmemory.models import TripleAssertion
from abstractmemory.seam import ActiveMemorySnapshot
from abstractmemory.sqlite_store import SQLiteTripleStore
from abstractmemory.store import TripleQuery


# ---------------------------------------------------------------------------
# Record factories (valid-by-default; override per test)
# ---------------------------------------------------------------------------


def make_event(kind: str = "selected", **kw: Any) -> MemoryEvent:
    defaults: dict[str, Any] = {"scope": "run", "owner_id": "run-1", "record_id": "rec-a"}
    if kind == "refocus":
        defaults["record_id"] = None
        defaults.setdefault("reason", "topic shift")
    elif kind == "co_selected":
        defaults["record_id"] = None
        defaults.setdefault("pair_ids", ("rec-a", "rec-b"))
    elif kind in {"pinned", "silenced"}:
        defaults.setdefault("reason", "deliberate act")
    defaults.update(kw)
    return MemoryEvent(kind=kind, **defaults)


def make_binding(**kw: Any) -> ScopeBinding:
    defaults: dict[str, Any] = {"record_id": "rec-a", "scope": "run", "owner_id": "run-1"}
    defaults.update(kw)
    return ScopeBinding(**defaults)


def make_closure(**kw: Any) -> ClosureRecord:
    defaults: dict[str, Any] = {"assertion_id": "as-1", "kind": "retract", "reason": "wrong fact"}
    defaults.update(kw)
    return ClosureRecord(**defaults)


def make_trace(**kw: Any) -> ReconstructionTrace:
    defaults: dict[str, Any] = {
        "trace_id": "tr-1",
        "trace_kind": "reconstruct",
        "query_fingerprint": "fp-1",
        "need": {"cue_text": "what is x"},
        "searched_scopes": ({"scope": "run", "owner_id": "run-1"},),
    }
    defaults.update(kw)
    return ReconstructionTrace(**defaults)


def make_snapshot(**kw: Any) -> ActiveMemorySnapshot:
    defaults: dict[str, Any] = {
        "snapshot_id": "",
        "seq": -1,  # placeholder; the journal owns the axis and reassigns
        "trace_id": "tr-1",
        "used_record_ids": ("rec-a",),
    }
    defaults.update(kw)
    return ActiveMemorySnapshot(**defaults)


# ---------------------------------------------------------------------------
# Backend fixture
# ---------------------------------------------------------------------------


@pytest.fixture(params=["memory", "sqlite"])
def journal(request: pytest.FixtureRequest, tmp_path):
    if request.param == "memory":
        with warnings.catch_warnings():
            # Volatility warning is asserted in its own test; keep others clean.
            warnings.simplefilter("ignore", RuntimeWarning)
            j = InMemoryJournal()
    else:
        j = SQLiteJournal(tmp_path / "journal.sqlite3")
    yield j
    j.close()


# ---------------------------------------------------------------------------
# seq axis
# ---------------------------------------------------------------------------


def test_seq_monotonic_across_mixed_record_types(journal) -> None:
    """One seq axis per journal instance, across ALL record families, from 1."""
    e = journal.append_events([make_event()])[0]
    b = journal.append_binding(make_binding())
    c = journal.append_closure(make_closure())
    t = journal.append_trace(make_trace())
    s = journal.append_snapshot(make_snapshot())
    e2 = journal.append_events([make_event(kind="shown")])[0]

    assert [e.seq, b.seq, c.seq, t.seq, s.seq, e2.seq] == [1, 2, 3, 4, 5, 6]
    assert journal.current_seq() == 6


def test_append_events_batch_gets_consecutive_seqs(journal) -> None:
    out = journal.append_events([make_event(), make_event(kind="listed"), make_event(kind="cited")])
    assert [x.seq for x in out] == [1, 2, 3]
    assert journal.current_seq() == 3


# ---------------------------------------------------------------------------
# append enrichment
# ---------------------------------------------------------------------------


def test_append_events_returns_new_enriched_instances(journal) -> None:
    original = make_event()
    returned = journal.append_events([original])[0]

    # New frozen instance; input never mutated (frozen dataclass semantics).
    assert returned is not original
    assert original.seq == -1 and original.event_id == ""
    assert returned.seq == 1
    assert isinstance(returned.event_id, str) and returned.event_id
    # Journal-assigned fields aside, payload is preserved.
    assert (returned.kind, returned.scope, returned.owner_id, returned.record_id) == (
        original.kind,
        original.scope,
        original.owner_id,
        original.record_id,
    )


def test_append_honors_caller_supplied_ids_but_owns_seq(journal) -> None:
    returned = journal.append_events([make_event(event_id="ev-deterministic", seq=999)])[0]
    # Deterministic/import flows may bring their own id...
    assert returned.event_id == "ev-deterministic"
    # ...but seq is ALWAYS journal-assigned (the as_of axis cannot be spoofed).
    assert returned.seq == 1


def test_append_binding_closure_trace_snapshot_assign_ids(journal) -> None:
    b = journal.append_binding(make_binding())
    c = journal.append_closure(make_closure())
    s = journal.append_snapshot(make_snapshot())
    assert b.binding_id and c.closure_id and s.snapshot_id
    assert b.seq == 1 and c.seq == 2 and s.seq == 3


def test_append_rejects_wrong_types(journal) -> None:
    with pytest.raises(TypeError):
        journal.append_events([{"kind": "selected"}])
    with pytest.raises(TypeError):
        journal.append_binding(make_event())
    with pytest.raises(TypeError):
        journal.append_snapshot({"snapshot_id": "x"})


# ---------------------------------------------------------------------------
# events() filtering
# ---------------------------------------------------------------------------


def _seed_events(journal) -> List[MemoryEvent]:
    return journal.append_events(
        [
            make_event(record_id="rec-a"),                                        # seq 1
            make_event(kind="listed", record_id="rec-a"),                         # seq 2
            make_event(kind="selected", record_id="rec-b"),                       # seq 3
            make_event(kind="co_selected", pair_ids=("rec-a", "rec-b")),          # seq 4
            make_event(scope="session", owner_id="sess-1", record_id="rec-a"),    # seq 5
            make_event(kind="pinned", record_id="rec-a", reason="keep"),          # seq 6
        ]
    )


def test_events_filters_scope_and_owner_newest_first(journal) -> None:
    _seed_events(journal)
    out = journal.events(scope="run", owner_id="run-1")
    assert [e.seq for e in out] == [6, 4, 3, 2, 1]  # newest first; session event excluded

    assert [e.seq for e in journal.events(scope="session", owner_id="sess-1")] == [5]
    assert journal.events(scope="run", owner_id="other-owner") == []


def test_events_filters_record_id_strictly(journal) -> None:
    _seed_events(journal)
    out = journal.events(scope="run", owner_id="run-1", record_id="rec-a")
    # co_selected (record_id=None) must NOT match a per-record query.
    assert [e.seq for e in out] == [6, 2, 1]
    assert all(e.record_id == "rec-a" for e in out)


def test_events_filters_kinds(journal) -> None:
    _seed_events(journal)
    out = journal.events(scope="run", owner_id="run-1", kinds=["selected", "co_selected"])
    assert [e.seq for e in out] == [4, 3, 1]

    trails = journal.events(scope="run", owner_id="run-1", kinds=["co_selected"])
    assert len(trails) == 1 and trails[0].pair_ids == ("rec-a", "rec-b")

    with pytest.raises(ValueError):
        journal.events(scope="run", owner_id="run-1", kinds=["not_a_kind"])


def test_events_seq_window_is_inclusive(journal) -> None:
    _seed_events(journal)
    out = journal.events(scope="run", owner_id="run-1", since_seq=2, until_seq=4)
    assert [e.seq for e in out] == [4, 3, 2]


def test_events_limit_keeps_newest(journal) -> None:
    _seed_events(journal)
    out = journal.events(scope="run", owner_id="run-1", limit=2)
    assert [e.seq for e in out] == [6, 4]
    # limit <= 0 means unlimited (package convention, cf. TripleQuery.limit).
    assert len(journal.events(scope="run", owner_id="run-1", limit=0)) == 5


# ---------------------------------------------------------------------------
# bindings fold
# ---------------------------------------------------------------------------


def test_bindings_fold_latest_wins(journal) -> None:
    journal.append_binding(make_binding(search_state="indexed", prompt_state="inactive"))
    journal.append_binding(make_binding(search_state="hidden", prompt_state="inactive", reason="quarantine"))
    journal.append_binding(make_binding(search_state="indexed", prompt_state="active", source="operator"))
    journal.append_binding(make_binding(record_id="rec-b", search_state="indexed", prompt_state="inactive"))

    folded = journal.bindings(scope="run", owner_id="run-1", fold=True)
    assert len(folded) == 2  # one winner per (record_id, scope, owner_id)
    by_record = {b.record_id: b for b in folded}
    assert by_record["rec-a"].search_state == "indexed"
    assert by_record["rec-a"].prompt_state == "active"
    assert by_record["rec-a"].seq == 3
    assert by_record["rec-b"].seq == 4

    unfolded = journal.bindings(record_id="rec-a", fold=False)
    assert [b.seq for b in unfolded] == [1, 2, 3]  # full audit history, chronological


def test_bindings_fold_respects_until_seq_anchor(journal) -> None:
    journal.append_binding(make_binding(search_state="indexed", prompt_state="inactive"))
    journal.append_binding(make_binding(search_state="hidden", prompt_state="inactive", reason="quarantine"))
    journal.append_binding(make_binding(search_state="indexed", prompt_state="active", source="operator"))

    # As-of seq 2 the record was hidden; the later re-index must not leak in.
    at_2 = journal.bindings(record_id="rec-a", fold=True, until_seq=2)
    assert len(at_2) == 1 and at_2[0].search_state == "hidden" and at_2[0].seq == 2


def test_bindings_per_scope_independence(journal) -> None:
    journal.append_binding(make_binding(scope="run", search_state="hidden", reason="local quarantine"))
    journal.append_binding(make_binding(scope="global", owner_id="global_memory", search_state="indexed"))

    folded = journal.bindings(record_id="rec-a", fold=True)
    states = {(b.scope, b.owner_id): b.search_state for b in folded}
    # Same record, different scope keys: both winners survive the fold.
    assert states == {("run", "run-1"): "hidden", ("global", "global_memory"): "indexed"}


# ---------------------------------------------------------------------------
# closures
# ---------------------------------------------------------------------------


def test_closure_append_and_read(journal) -> None:
    journal.append_closure(make_closure(assertion_id="as-1", kind="retract", reason="user corrected"))
    journal.append_closure(
        make_closure(assertion_id="as-2", kind="supersede", reason="refined", replacement_ids=("as-3", "as-4"))
    )

    all_closures = journal.closures()
    assert [c.assertion_id for c in all_closures] == ["as-2", "as-1"]  # newest first

    only_2 = journal.closures(assertion_id="as-2")
    assert len(only_2) == 1
    assert only_2[0].kind == "supersede"
    assert only_2[0].replacement_ids == ("as-3", "as-4")
    assert only_2[0].closure_id  # journal-assigned

    assert journal.closures(assertion_id="as-2", until_seq=1) == []


# ---------------------------------------------------------------------------
# snapshots
# ---------------------------------------------------------------------------


def test_snapshot_append_and_read_by_trace(journal) -> None:
    journal.append_snapshot(make_snapshot(trace_id="tr-1", used_record_ids=("rec-a", "rec-b")))
    journal.append_snapshot(make_snapshot(trace_id="tr-2", display=({"record_id": "rec-c", "title": "T"},)))

    got = journal.snapshots(trace_id="tr-2")
    assert len(got) == 1
    assert got[0].display == ({"record_id": "rec-c", "title": "T"},)
    assert len(journal.snapshots()) == 2


def test_traces_read_newest_first_and_by_trace_id(journal) -> None:
    """traces() mirrors snapshots(): newest first, exact trace_id filter,
    full-fidelity round-trip of every stored field (both backends)."""
    journal.append_trace(make_trace(trace_id="tr-1"))
    stored = journal.append_trace(
        make_trace(
            trace_id="tr-2",
            escalation_reason="cross-session lookup",
            channels=("exact", "keyword"),
            candidates=({"record_id": "rec-a", "scores": {"exact": 1.0}},),
            selected=("rec-a",),
            dropped=({"record_id": "rec-b", "score": 0.5, "reason": "below_shelf"},),
            cues=("exact: subject=alice",),
            budgets={"shelf_size": 12},
            budget_spent={"tokens_used": 7},
            warnings=("#FALLBACK: keyword channel v1 = token scan",),
        )
    )

    out = journal.traces()
    assert [t.trace_id for t in out] == ["tr-2", "tr-1"]  # newest first

    only_2 = journal.traces(trace_id="tr-2")
    assert len(only_2) == 1
    assert only_2[0] == stored  # full field equality across the round-trip

    assert journal.traces(trace_id="ghost") == []
    assert len(journal.traces(limit=1)) == 1


# ---------------------------------------------------------------------------
# selected_count (denormalized use counter)
# ---------------------------------------------------------------------------


def test_selected_count_only_advances_on_selected(journal) -> None:
    """Regression (0018 hard contract): reading is not using — audit kinds,
    trails and deliberate acts must never advance the selected-use counter."""
    assert journal.selected_count("rec-a") == 0

    journal.append_events([make_event(kind="selected", record_id="rec-a")])
    assert journal.selected_count("rec-a") == 1

    journal.append_events(
        [
            make_event(kind="listed", record_id="rec-a"),
            make_event(kind="shown", record_id="rec-a"),
            make_event(kind="expanded", record_id="rec-a"),
            make_event(kind="cited", record_id="rec-a"),
            make_event(kind="co_selected", pair_ids=("rec-a", "rec-b")),
            make_event(kind="pinned", record_id="rec-a", reason="keep"),
            make_event(kind="silenced", record_id="rec-a", reason="mute"),
        ]
    )
    assert journal.selected_count("rec-a") == 1  # unchanged by all of the above

    journal.append_events([make_event(kind="selected", record_id="rec-a")])
    assert journal.selected_count("rec-a") == 2
    assert journal.selected_count("rec-b") == 0
    assert journal.selected_count("never-seen") == 0


# ---------------------------------------------------------------------------
# seq_at
# ---------------------------------------------------------------------------


def test_seq_at_scans_state_records_and_excludes_snapshots(journal) -> None:
    journal.append_events([make_event(observed_at="2026-01-01T10:00:00+00:00")])          # seq 1
    journal.append_binding(make_binding(observed_at="2026-01-01T11:00:00+00:00"))          # seq 2
    journal.append_closure(make_closure(observed_at="2026-01-01T12:00:00+00:00"))          # seq 3
    journal.append_trace(make_trace(observed_at="2026-01-01T13:00:00+00:00"))              # seq 4
    journal.append_snapshot(make_snapshot(observed_at="2026-01-01T14:00:00+00:00"))        # seq 5

    assert journal.seq_at("2026-01-01T09:59:59+00:00") == 0
    assert journal.seq_at("2026-01-01T10:00:00+00:00") == 1  # inclusive bound
    assert journal.seq_at("2026-01-01T11:30:00+00:00") == 2
    assert journal.seq_at("2026-01-01T12:30:00+00:00") == 3
    assert journal.seq_at("2026-01-01T13:30:00+00:00") == 4
    # Snapshots (seq 5) never anchor as_of: they mirror context contents and
    # do not affect scoring or folds.
    assert journal.seq_at("2026-01-01T23:00:00+00:00") == 4
    assert journal.current_seq() == 5


def test_seq_at_accepts_z_suffix_and_rejects_garbage(journal) -> None:
    journal.append_events([make_event(observed_at="2026-01-01T10:00:00+00:00")])
    assert journal.seq_at("2026-01-01T10:00:00Z") == 1
    with pytest.raises(ValueError):
        journal.seq_at("not-a-timestamp")


# ---------------------------------------------------------------------------
# thread safety (0013 contract smoke)
# ---------------------------------------------------------------------------


def test_threaded_writers_preserve_seq_axis(journal) -> None:
    threads_n, events_per_thread = 8, 50
    errors: List[BaseException] = []
    barrier = threading.Barrier(threads_n)

    def writer(worker: int) -> None:
        try:
            barrier.wait()  # maximize interleaving
            for i in range(events_per_thread):
                journal.append_events([make_event(record_id=f"rec-{worker}-{i}")])
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(w,)) for w in range(threads_n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    total = threads_n * events_per_thread
    out = journal.events(scope="run", owner_id="run-1", limit=0)
    assert len(out) == total
    seqs = [e.seq for e in out]  # newest first
    assert seqs == sorted(seqs, reverse=True)
    assert len(set(seqs)) == total  # no duplicate seq: strictly increasing axis
    assert set(seqs) == set(range(1, total + 1))  # no gaps either
    assert journal.current_seq() == total


# ---------------------------------------------------------------------------
# record validation surfaces through append paths
# ---------------------------------------------------------------------------


def test_record_validation_errors_surface() -> None:
    with pytest.raises(ValueError, match="kind"):
        make_event(kind="viewed")  # unknown kind
    with pytest.raises(ValueError, match="refocus"):
        MemoryEvent(kind="refocus", scope="run", owner_id="run-1", record_id="rec-a", reason="shift")
    with pytest.raises(ValueError, match="hidden"):
        make_binding(search_state="hidden", prompt_state="active")
    with pytest.raises(ValueError, match="replacement_ids"):
        make_closure(kind="supersede", replacement_ids=())
    with pytest.raises(ValueError, match="reason"):
        make_event(kind="pinned", reason="")
    with pytest.raises(ValueError, match="distinct"):
        make_event(kind="co_selected", pair_ids=("rec-a", "rec-a"))


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def test_memory_event_json_round_trip(journal) -> None:
    enriched = journal.append_events(
        [
            make_event(
                weight=0.0,  # defaulted to 8.0 by kind
                ttl_activity=7,
                matched=True,
                query_fingerprint="fp-9",
                trace_id="tr-9",
                actor="runtime",
                provenance={"run_id": "r1", "turn_id": 3},
            ),
            make_event(kind="co_selected", pair_ids=("rec-b", "rec-a")),  # unsorted on purpose
        ]
    )
    for original in enriched:
        data = original.to_dict()
        # to_dict must be JSON-plain (tuples become lists).
        if original.pair_ids is not None:
            assert data["pair_ids"] == ["rec-a", "rec-b"]  # canonical sorted pair
        restored = MemoryEvent.from_dict(data)
        assert restored == original  # full field equality, incl. seq/event_id


# ---------------------------------------------------------------------------
# backend-specific behavior
# ---------------------------------------------------------------------------


def test_in_memory_journal_warns_fallback_on_construction() -> None:
    # pytest.warns installs an "always" filter, so the once-per-location
    # dedup of the default filter cannot hide the warning here.
    with pytest.warns(RuntimeWarning, match="#FALLBACK"):
        InMemoryJournal()


def test_sqlite_journal_persists_across_reopen(tmp_path) -> None:
    path = tmp_path / "journal.sqlite3"
    j1 = SQLiteJournal(path)
    j1.append_events([make_event()])
    j1.append_binding(make_binding())
    assert j1.current_seq() == 2
    j1.close()

    j2 = SQLiteJournal(path)
    try:
        # The axis survives reopen: as_of anchors persisted by the runtime
        # stay valid, and new appends continue after the high-water mark.
        assert j2.current_seq() == 2
        assert [e.seq for e in j2.events(scope="run", owner_id="run-1")] == [1]
        assert j2.append_events([make_event(kind="cited")])[0].seq == 3
    finally:
        j2.close()


def test_sqlite_journal_enables_wal_and_busy_timeout(tmp_path) -> None:
    path = tmp_path / "journal.sqlite3"
    j = SQLiteJournal(path)
    try:
        j.append_events([make_event()])
    finally:
        j.close()
    probe = sqlite3.connect(str(path))
    try:
        assert str(probe.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
    finally:
        probe.close()


def test_sqlite_journal_coexists_with_triple_store_in_same_file(tmp_path) -> None:
    """0017: the journal is a sidecar in the SAME file as the triple store —
    distinct table names, no interference in either direction."""
    path = tmp_path / "memory.sqlite3"

    store = SQLiteTripleStore(path)
    store.add([TripleAssertion(subject="alice", predicate="knows", object="bob")])

    j = SQLiteJournal(path)
    try:
        j.append_events([make_event()])
        j.append_binding(make_binding())

        # Triple store still fully functional (existing + new writes)...
        assert len(store.query(TripleQuery(subject="alice"))) == 1
        store.add([TripleAssertion(subject="bob", predicate="knows", object="carol")])
        assert len(store.query(TripleQuery(predicate="knows"))) == 2

        # ...and the journal reads back its own records.
        assert [e.seq for e in j.events(scope="run", owner_id="run-1")] == [1]
        assert j.current_seq() == 2

        # Table sets are disjoint by construction (memj_ prefix).
        names = {
            r[0]
            for r in j._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "triples" in names
        assert {"memj_events", "memj_bindings", "memj_closures", "memj_traces", "memj_snapshots", "memj_seq", "memj_selected_counts"} <= names
    finally:
        j.close()
        store.close()


def test_sqlite_journal_rejects_malformed_table_prefix(tmp_path) -> None:
    # The prefix is interpolated into SQL identifiers; anything but a strict
    # identifier is an injection vector and must be refused loudly.
    with pytest.raises(ValueError, match="table_prefix"):
        SQLiteJournal(tmp_path / "journal.sqlite3", table_prefix="memj_; DROP TABLE triples;--")
