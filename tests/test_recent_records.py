"""recent_records() — the breadcrumb read (Ephemeral's visit-1 ask).

Pins: time-window + newest-first ordering; closure/hidden folds applied;
machine rows (bookkeeping/maintenance candidates/record edges) excluded;
re-entry keys ride when present, never fabricated; kind filter; page bound
with honest truncated flag; PURE READ (no journal writes, no deposits);
validation is loud.
"""

from __future__ import annotations

import pytest

from abstractmemory import MemorySystem, recent_records
from abstractmemory.records import MemoryRecordInput

SCOPE = "life"
OWNER = "entity:test"
SCOPES = [(SCOPE, OWNER)]


def _seed(system: MemorySystem) -> list:
    return system.remember_many([
        MemoryRecordInput(kind="episode", title="monday walk",
                          digest="Walked the harbor on monday morning."),
        MemoryRecordInput(kind="episode", title="tuesday build",
                          digest="Built the simulation on tuesday.",
                          attributes={"phase": "personal"}),
        MemoryRecordInput(kind="diary", title="tuesday note",
                          digest="Kept a note about the build.",
                          attributes={"entry_id": "diary_ab12cd34ef56ab12cd34ef56",
                                      "diary_type": "note"},
                          provenance={"source": "owner-direct"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="bc-seed")


def test_window_orders_newest_first_with_keys_riding(system) -> None:
    _seed(system)
    out = system.recent_records(scopes=SCOPES, since="2000-01-01")
    assert [r["title"] for r in out["records"]] == [
        "tuesday note", "tuesday build", "monday walk"]  # formation order, newest first
    by_title = {r["title"]: r for r in out["records"]}
    diary = by_title["tuesday note"]
    assert diary["entry_id"] == "diary_ab12cd34ef56ab12cd34ef56"
    assert diary["diary_type"] == "note"
    assert "phase" not in diary                      # never fabricated
    assert by_title["tuesday build"]["phase"] == "personal"
    assert "entry_id" not in by_title["tuesday build"]
    assert out["counts"] == {"episode": 2, "diary": 1}
    assert out["truncated"] is False
    assert out["window"]["as_of_seq"] == system.current_seq()


def test_since_bounds_the_window_and_kinds_filter(system) -> None:
    _seed(system)
    all_rows = system.recent_records(scopes=SCOPES, since="2000-01-01")
    newest = all_rows["records"][0]["observed_at"]
    only_newest = system.recent_records(scopes=SCOPES, since=newest)
    assert [r["observed_at"] >= newest for r in only_newest["records"]] == \
        [True] * len(only_newest["records"])
    diaries = system.recent_records(scopes=SCOPES, since="2000-01-01", kinds=["diary"])
    assert [r["kind"] for r in diaries["records"]] == ["diary"]


def test_closed_records_leave_the_trail(system) -> None:
    ids = _seed(system)
    system.close_record(ids[0], reason="superseded by the tuesday build")
    out = system.recent_records(scopes=SCOPES, since="2000-01-01")
    assert "monday walk" not in [r["title"] for r in out["records"]]


def test_limit_pages_and_flags_truncation(system) -> None:
    _seed(system)
    out = system.recent_records(scopes=SCOPES, since="2000-01-01", limit=2)
    assert len(out["records"]) == 2
    assert out["truncated"] is True
    assert out["records"][0]["title"] == "tuesday note"  # newest survives paging


def test_pure_read_no_journal_writes_no_deposits(system) -> None:
    ids = _seed(system)
    seq = system.current_seq()
    counts = system.access_counts(record_ids=ids)
    for _ in range(3):
        system.recent_records(scopes=SCOPES, since="2000-01-01")
    assert system.current_seq() == seq, "the breadcrumb read wrote to the journal"
    assert system.access_counts(record_ids=ids) == counts, "the breadcrumb read deposited usage"


def test_validation_is_loud(system) -> None:
    with pytest.raises(ValueError, match="since"):
        system.recent_records(scopes=SCOPES, since="")
    with pytest.raises(ValueError, match="limit"):
        system.recent_records(scopes=SCOPES, since="2000-01-01", limit=0)
    with pytest.raises(ValueError, match="scope"):
        recent_records(system.store, system.journal, scopes=[], since="2000-01-01")
