"""At-least-once replay idempotency (a2a 0001/011 asks 2 + 3).

Runtime effects can crash between STARTED and COMPLETED and re-run. These
tests prove that replayed writes are TRUE no-ops at both layers:

- journal layer: caller-SUPPLIED record ids are idempotency keys — re-appends
  return the original stored records (original seqs), write nothing, and
  never advance the selected-use counter (both backends, same semantics);
- facade layer: commit_selection is idempotent by trace_id, with
  deterministic event/snapshot ids so even a crash BETWEEN the event appends
  and the snapshot append replays cleanly.
"""

from __future__ import annotations

import warnings
from typing import Any

import pytest

from abstractmemory import (
    InMemoryJournal,
    MemoryEvent,
    ReconstructionTrace,
    SQLiteJournal,
    ScopeBinding,
    ClosureRecord,
    ActiveMemorySnapshot,
    Stimulus,
    TripleAssertion,
)

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _ts(i: int) -> str:
    return f"2026-07-05T10:{i:02d}:00.000000+00:00"


def _assertion(aid: str, s: str, p: str, o: str, ts: int) -> TripleAssertion:
    return TripleAssertion(
        subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
        observed_at=_ts(ts), assertion_id=aid,
    )


def _event(kind: str = "selected", **kw: Any) -> MemoryEvent:
    defaults: dict[str, Any] = {"scope": SCOPE, "owner_id": OWNER, "record_id": "rec-a"}
    if kind == "co_selected":
        defaults["record_id"] = None
        defaults.setdefault("pair_ids", ("rec-a", "rec-b"))
    defaults.update(kw)
    return MemoryEvent(kind=kind, **defaults)


@pytest.fixture(params=["memory", "sqlite"])
def journal(request: pytest.FixtureRequest, tmp_path):
    if request.param == "memory":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            j = InMemoryJournal()
    else:
        j = SQLiteJournal(tmp_path / "journal.sqlite3")
    yield j
    j.close()


# ---------------------------------------------------------------------------
# journal layer: supplied-id dedup (0001/011 ask 3)
# ---------------------------------------------------------------------------


def test_replayed_event_batch_is_a_true_noop(journal) -> None:
    batch = [
        _event(event_id="ev-1", record_id="rec-a"),
        _event("co_selected", event_id="ev-2"),
        _event("listed", event_id="ev-3", record_id="rec-a"),
    ]
    first = journal.append_events(batch)
    assert [e.seq for e in first] == [1, 2, 3]
    assert journal.selected_count("rec-a") == 1
    seq_after_first = journal.current_seq()

    # The crash-replay: the exact same batch again (same supplied ids).
    replay = journal.append_events(batch)
    assert [e.seq for e in replay] == [1, 2, 3]              # original seqs returned
    assert [e.event_id for e in replay] == ["ev-1", "ev-2", "ev-3"]
    assert journal.current_seq() == seq_after_first          # no new records
    assert len(journal.events(scope=SCOPE, owner_id=OWNER, limit=0)) == 3
    assert journal.selected_count("rec-a") == 1              # counter untouched


def test_partial_replay_batch_handled_per_record(journal) -> None:
    journal.append_events([
        _event(event_id="ev-a", record_id="rec-a"),
        _event(event_id="ev-b", record_id="rec-b"),
    ])
    # A later batch mixing replayed and genuinely new records.
    out = journal.append_events([
        _event(event_id="ev-b", record_id="rec-b"),   # replay -> original seq 2
        _event(event_id="ev-new", record_id="rec-c"),  # new -> seq 3
        _event(event_id="ev-a", record_id="rec-a"),   # replay -> original seq 1
    ])
    assert [e.seq for e in out] == [2, 3, 1]
    assert journal.current_seq() == 3
    assert journal.selected_count("rec-b") == 1  # replays never double-count
    assert journal.selected_count("rec-c") == 1


def test_in_batch_duplicate_supplied_ids_resolve_to_first_occurrence(journal) -> None:
    out = journal.append_events([
        _event(event_id="ev-dup", record_id="rec-a"),
        _event(event_id="ev-dup", record_id="rec-a"),
    ])
    assert [e.seq for e in out] == [1, 1]
    assert len(journal.events(scope=SCOPE, owner_id=OWNER, limit=0)) == 1
    assert journal.selected_count("rec-a") == 1


def test_journal_assigned_ids_never_conflict(journal) -> None:
    # Identical payloads WITHOUT supplied ids are two genuine deposits.
    a = journal.append_events([_event()])[0]
    b = journal.append_events([_event()])[0]
    assert a.event_id != b.event_id and (a.seq, b.seq) == (1, 2)
    assert journal.selected_count("rec-a") == 2


def test_supplied_id_dedup_for_binding_closure_snapshot(journal) -> None:
    binding = ScopeBinding(record_id="rec-a", scope=SCOPE, owner_id=OWNER, binding_id="bind-1")
    closure = ClosureRecord(assertion_id="as-1", kind="retract", reason="wrong", closure_id="clo-1")
    snapshot = ActiveMemorySnapshot(snapshot_id="snap-1", trace_id="tr-1", used_record_ids=("rec-a",))

    b1, c1, s1 = journal.append_binding(binding), journal.append_closure(closure), journal.append_snapshot(snapshot)
    seq_after = journal.current_seq()

    # Replays return the ORIGINAL records — full equality including seq.
    assert journal.append_binding(binding) == b1
    assert journal.append_closure(closure) == c1
    assert journal.append_snapshot(snapshot) == s1
    assert journal.current_seq() == seq_after
    assert len(journal.bindings(fold=False)) == 1
    assert len(journal.closures(limit=0)) == 1
    assert len(journal.snapshots(limit=0)) == 1


def test_supplied_trace_id_dedup(journal) -> None:
    """Traces joined the supplied-id dedup (caller-supplied trace_id path):
    re-appending an existing trace_id returns the stored trace, no new seq."""
    trace = ReconstructionTrace(
        trace_id="tr-replay", trace_kind="reconstruct", query_fingerprint="fp-1",
        need={"cue_text": "x"}, searched_scopes=({"scope": SCOPE, "owner_id": OWNER},),
    )
    stored = journal.append_trace(trace)
    assert journal.append_trace(trace) == stored  # original record, original seq
    assert journal.current_seq() == stored.seq
    assert len(journal.traces(limit=0)) == 1
    # Distinct ids remain distinct deposits.
    other = journal.append_trace(
        ReconstructionTrace(
            trace_id="tr-other", trace_kind="reconstruct", query_fingerprint="fp-2",
            need={}, searched_scopes=(),
        )
    )
    assert other.seq == stored.seq + 1 and len(journal.traces(limit=0)) == 2


def test_sqlite_dedup_survives_reopen(tmp_path) -> None:
    """The real crash window: the process dies AFTER the append committed;
    the replay happens in a NEW process (new connection) — dedup must be
    durable, not an in-memory cache artifact."""
    path = tmp_path / "journal.sqlite3"
    j1 = SQLiteJournal(path)
    stored = j1.append_events([_event(event_id="ev-crash", record_id="rec-a")])[0]
    j1.close()

    j2 = SQLiteJournal(path)
    try:
        replay = j2.append_events([_event(event_id="ev-crash", record_id="rec-a")])[0]
        assert replay == stored  # original record, original seq
        assert j2.current_seq() == 1
        assert j2.selected_count("rec-a") == 1
        # Backstop exists: unique indexes on every deduped family.
        names = {
            r[0]
            for r in j2._conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        assert {
            "uq_memj_events_event_id",
            "uq_memj_bindings_binding_id",
            "uq_memj_closures_closure_id",
            "uq_memj_snapshots_snapshot_id",
        } <= names
    finally:
        j2.close()


# ---------------------------------------------------------------------------
# facade layer: commit_selection idempotent by trace_id (0001/011 ask 2)
# ---------------------------------------------------------------------------


def _seed(system) -> None:
    system.add([
        _assertion("m-old", "alice", "wrote", "report", 1),
        _assertion("m-new", "alice", "filed", "report copy", 2),
        _assertion("m-tea", "alice", "likes", "tea", 3),
    ])


def _trail(journal) -> dict:
    events = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected", "co_selected"], limit=0)
    return {
        "count": len(events),
        "ids": sorted(e.event_id for e in events),
        "selected_count": journal.selected_count("m-old"),
    }


def test_double_commit_same_trace_deposits_once(system, stack) -> None:
    _, journal = stack
    _seed(system)
    r = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)

    snap1 = system.commit_selection(r.trace_id, ["m-old", "m-tea"], prompt_token_estimate=42)
    trail_after_first = _trail(journal)
    assert trail_after_first["count"] == 3  # 2 selected + 1 co_selected (shared "alice")

    snap2 = system.commit_selection(r.trace_id, ["m-old", "m-tea"], prompt_token_estimate=42)
    assert snap2 == snap1                       # the SAME snapshot, unchanged
    assert _trail(journal) == trail_after_first  # no second deposit
    assert len(journal.snapshots(limit=0)) == 1


# ---------------------------------------------------------------------------
# facade layer: deliberate-act idempotency passthrough (0001/015 ask 1)
# ---------------------------------------------------------------------------


def test_replayed_reinforce_with_supplied_event_id_is_a_noop(system, stack) -> None:
    """Runtime effects replay at-least-once; reinforce is an additive
    salience write, so a naive replay double-boosts. A supplied event_id
    flows to the MemoryEvent and the journal's supplied-id dedup makes the
    replay a true no-op returning the ORIGINAL event."""
    _, journal = stack
    _seed(system)
    eid = system.reinforce(
        "m-old", reason="charter validated", scope=SCOPE, owner_id=OWNER,
        event_id="madjust-1", actor="runtime", provenance={"turn_id": "t-7"},
    )
    assert eid == "madjust-1"
    [pin] = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["pinned"], limit=0)
    first_seq, act_before = pin.seq, system.activation(["m-old"], scope=SCOPE, owner_id=OWNER)
    assert pin.actor == "runtime" and pin.provenance == {"turn_id": "t-7"}

    replay = system.reinforce(  # the crash-replay: identical call
        "m-old", reason="charter validated", scope=SCOPE, owner_id=OWNER,
        event_id="madjust-1", actor="runtime", provenance={"turn_id": "t-7"},
    )
    assert replay == "madjust-1"
    events = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["pinned"], limit=0)
    assert len(events) == 1 and events[0].seq == first_seq   # one event, same seq
    assert system.activation(["m-old"], scope=SCOPE, owner_id=OWNER) == act_before


def test_attenuate_and_refocus_accept_the_same_passthrough(system, stack) -> None:
    _, journal = stack
    _seed(system)
    assert system.attenuate("m-tea", reason="stale", scope=SCOPE, owner_id=OWNER,
                            event_id="madjust-2") == "madjust-2"
    assert system.attenuate("m-tea", reason="stale", scope=SCOPE, owner_id=OWNER,
                            event_id="madjust-2") == "madjust-2"
    assert len(journal.events(scope=SCOPE, owner_id=OWNER, kinds=["silenced"], limit=0)) == 1

    seq_after = journal.current_seq()
    assert system.refocus(reason="topic shift", scope=SCOPE, owner_id=OWNER,
                          event_id="madjust-3", actor="runtime") == "madjust-3"
    assert system.refocus(reason="topic shift", scope=SCOPE, owner_id=OWNER,
                          event_id="madjust-3", actor="runtime") == "madjust-3"
    assert journal.current_seq() == seq_after + 1            # exactly one refocus row
    # Default semantics unchanged: no event_id -> journal assigns fresh ids.
    fresh_a = system.refocus(reason="another shift", scope=SCOPE, owner_id=OWNER)
    fresh_b = system.refocus(reason="another shift", scope=SCOPE, owner_id=OWNER)
    assert fresh_a != fresh_b


def test_replayed_close_record_ignores_reason_drift(system, stack) -> None:
    """The closure idempotency key is (graph_id, kind, assertion_id) — the
    REASON never enters it, so a replay whose reason drifted (runtime
    re-derives prose) still dedupes to the original closures."""
    _, journal = stack
    from abstractmemory.records import MemoryRecordInput
    [gid_a] = system.remember_many([MemoryRecordInput(kind="claim", title="A", digest="alpha fact")],
                                   scope=SCOPE, owner_id=OWNER, idempotency_key="cr-1")
    [gid_b] = system.remember_many(
        [MemoryRecordInput(kind="claim", title="B", digest="beta fact",
                           edges=(("supports", gid_a),))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="cr-2")

    first = system.close_record(gid_b, reason="first reason")
    count_after = len(journal.closures(limit=0))
    assert len(first) == 2                                    # digest + edge, one act

    replay = system.close_record(gid_b, reason="second reason (drifted on replay)")
    assert replay == first                                    # same deterministic ids
    assert len(journal.closures(limit=0)) == count_after      # no new closures


def test_crash_between_events_and_snapshot_replays_clean(system, stack) -> None:
    """Simulated at-least-once crash: the trail is deposited, the process
    dies before the snapshot append, the effect re-runs. The replay must not
    double the trail (deterministic event ids -> journal dedup) and must
    create the snapshot with the SAME id the events already reference."""
    _, journal = stack
    _seed(system)
    r = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)

    def crash(snapshot):
        raise RuntimeError("simulated crash between event append and snapshot append")

    journal.append_snapshot = crash  # instance attribute shadows the method
    try:
        with pytest.raises(RuntimeError, match="simulated crash"):
            system.commit_selection(r.trace_id, ["m-old", "m-tea"])
    finally:
        del journal.append_snapshot  # restore the real method

    trail_after_crash = _trail(journal)
    assert trail_after_crash["count"] == 3      # the trail DID land pre-crash
    assert journal.snapshots(limit=0) == []     # ...but no snapshot yet

    snap = system.commit_selection(r.trace_id, ["m-old", "m-tea"])  # the replay
    assert _trail(journal) == trail_after_crash  # no duplicate events, count intact
    assert len(journal.snapshots(limit=0)) == 1
    # The events' context_ref matches the snapshot id (trace-derived, so the
    # replay re-derived the identical linkage the pre-crash events carry).
    events = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected"], limit=0)
    assert all(e.provenance.get("context_ref") == snap.snapshot_id for e in events)


def test_commit_replay_with_different_used_set_warns_and_keeps_original(system) -> None:
    _seed(system)
    r = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    snap1 = system.commit_selection(r.trace_id, ["m-old"])

    with pytest.warns(RuntimeWarning, match="#FALLBACK.*different.*used set"):
        snap2 = system.commit_selection(r.trace_id, ["m-new"])
    assert snap2 == snap1  # first commit is the truth; nothing was written


def test_distinct_traces_are_distinct_deposits(system, stack) -> None:
    """Idempotency keys on trace identity must NOT collapse genuinely
    different reads that used the same records."""
    _, journal = stack
    _seed(system)
    r1 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    system.commit_selection(r1.trace_id, ["m-old"])
    r2 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    system.commit_selection(r2.trace_id, ["m-old"])

    assert journal.selected_count("m-old") == 2  # two genuine uses
    assert len(journal.snapshots(limit=0)) == 2
