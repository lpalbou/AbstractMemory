"""0049 stable render order — the prefix-reuse presentation contract.

Pins: formation-order key (persisting records hold relative position;
new records append at the TAIL — the LCP-maximizing property alphabetical
identity order lacks); rank annotations preserve the input's 1-based rank;
pure read (same objects, all of them, once; input untouched); determinism;
both handle shapes (objects and dicts).
"""

from __future__ import annotations

import pytest

from abstractmemory import MemorySystem, Stimulus, stable_render_order
from abstractmemory.records import MemoryRecordInput

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _handle(rid: str, observed_at: str) -> dict:
    return {"record_id": rid, "provenance": {"observed_at": observed_at}}


def test_persisting_records_hold_position_and_new_records_append() -> None:
    """The LCP property: turn 2 reranks the shared records and adds one
    NEW record — under formation order the shared PREFIX is byte-stable
    and the newcomer lands at the tail, whatever its rank."""
    a = _handle("row-a", "2026-07-10T08:00:00")
    b = _handle("row-b", "2026-07-12T09:00:00")
    c = _handle("row-c", "2026-07-14T10:00:00")
    new = _handle("row-0-alphabetically-first", "2026-07-17T11:00:00")

    turn1 = stable_render_order([b, c, a])          # ranks: b=1, c=2, a=3
    turn2 = stable_render_order([new, c, b, a])     # newcomer ranked FIRST

    assert [h["record_id"] for h, _ in turn1] == ["row-a", "row-b", "row-c"]
    assert [h["record_id"] for h, _ in turn2] == [
        "row-a", "row-b", "row-c", "row-0-alphabetically-first"]
    # The shared three are a byte-stable leading prefix; the new record —
    # alphabetically FIRST, rank 1 — still appends at the tail (formation
    # order beats both id order and rank order for prefix reuse).
    assert [h["record_id"] for h, _ in turn2[:3]] == [h["record_id"] for h, _ in turn1]


def test_rank_annotations_carry_the_input_rank() -> None:
    a, b, c = (_handle("row-a", "2026-07-10"), _handle("row-b", "2026-07-12"),
               _handle("row-c", "2026-07-14"))
    out = stable_render_order([c, a, b])  # ranks: c=1, a=2, b=3
    assert [(h["record_id"], r) for h, r in out] == [
        ("row-a", 2), ("row-b", 3), ("row-c", 1)]


def test_pure_read_same_objects_once_input_untouched() -> None:
    handles = [_handle("row-b", "2026-07-12"), _handle("row-a", "2026-07-10")]
    snapshot = [dict(h) for h in handles]
    out = stable_render_order(handles)
    assert [id(h) for h, _ in sorted(out, key=lambda p: p[1])] == [id(h) for h in handles]
    assert handles == snapshot
    assert stable_render_order(handles) == out  # deterministic
    assert stable_render_order([]) == []


def test_ties_and_missing_dates_are_deterministic() -> None:
    same_time = [_handle("row-z", "2026-07-10"), _handle("row-a", "2026-07-10")]
    out = stable_render_order(same_time)
    assert [h["record_id"] for h, _ in out] == ["row-a", "row-z"]  # id tie-break
    undated = [_handle("row-n", ""), _handle("row-m", "2026-07-10")]
    out2 = stable_render_order(undated)
    assert [h["record_id"] for h, _ in out2] == ["row-n", "row-m"]  # empty sorts first, stated


def test_real_reconstruction_handles_order_by_formation(stack) -> None:
    """Object path over real MemoryHandles: whatever the rank order,
    the render order is formation order and every handle survives."""
    store, journal = stack
    system = MemorySystem(store=store, journal=journal)
    system.remember_many([
        MemoryRecordInput(kind="episode", title=f"harbor day {i}",
                          digest=f"Harbor walk number {i} with the tide out.")
        for i in range(4)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="render-order-seed")
    r = system.reconstruct(Stimulus(cue_text="harbor tide walk"),
                           scopes=SCOPES, journal=False)
    assert len(r.handles) == 4
    out = stable_render_order(r.handles)
    dates = [str((_h.provenance or {}).get("observed_at") or "") for _h, _ in out]
    assert dates == sorted(dates)
    assert {h.record_id for h, _ in out} == {h.record_id for h in r.handles}
    assert sorted(r for _, r in out) == [1, 2, 3, 4]
