"""alive_drives() — the day-cue read: drives as DRIVERS of cognition
(laurent dm#82, room c224/c227; the adopted three-answer contract).

Pins:
- ranked handle-shaped items with born_at/origin/drive labels;
- aliveness = max(trail, recency): a trail-touched drive outranks an
  untouched one; a NEWBORN drive is alive by formation alone;
- dormant drives never return — an empty result IS the quiet desk
  (emergent, no threshold);
- pure read (deposits nothing — the cue must never breed tomorrow's
  list from this morning's);
- one shared interest fold with drive_pressure (never a copy);
- top-K cap; loud validation.
"""

from __future__ import annotations

import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    AttentionConfig,
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    alive_drives,
)

OWNER = "entity:hygieia"
SCOPES = [("self", OWNER), ("diary", OWNER), ("life", OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _question(system, title, digest, key):
    [gid] = system.remember_many([
        MemoryRecordInput(kind="diary", title=title, digest=digest,
                          attributes={"diary_type": "question"},
                          provenance={"source": "owner-direct"})],
        scope="diary", owner_id=OWNER, idempotency_key=key)
    return gid


def test_newborn_and_trail_alive_rank_over_each_other(system) -> None:
    q_old = _question(system, "Old Q", "An old standing question?", "aq-old")
    # Bury the old question's formation under enough binding traffic to
    # push it out of the recency window (small window via config below is
    # cleaner — here we just verify ordering semantics).
    q_new = _question(system, "New Q", "A newborn question?", "aq-new")

    out = alive_drives(system, scopes=SCOPES, k=5)
    by_id = {d["record_id"]: d for d in out}
    assert q_new in by_id and q_old in by_id
    # Newborn ranks above older-formed (recency rank distance).
    ids = [d["record_id"] for d in out]
    assert ids.index(q_new) < ids.index(q_old)
    assert by_id[q_new]["alive_via"] in ("recency", "both")
    assert by_id[q_new]["drive"] == "open question"
    assert by_id[q_new]["born_at"] is not None

    # TRAIL beats pure recency: the old question gets genuinely USED
    # (selected into a context) and becomes the strongest pull.
    r = system.reconstruct(
        __import__("abstractmemory").Stimulus(cue_text="old standing question"),
        scopes=SCOPES)
    system.commit_selection(r.trace_id, [q_old])
    out2 = alive_drives(system, scopes=SCOPES, k=5)
    ids2 = [d["record_id"] for d in out2]
    assert ids2.index(q_old) < ids2.index(q_new)
    assert {d["record_id"]: d for d in out2}[q_old]["alive_via"] in ("trail", "both")


def test_quiet_desk_is_emergent_and_read_is_pure(system) -> None:
    """Dormant drives fall out by the window (the BINDING-axis dial
    drive_window_limit), not a threshold: a question buried under later
    formations is dormant (empty desk) while a fresh one is alive."""
    small = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal(),
                         attention_config=AttentionConfig(drive_window_limit=4))
    q = _question(small, "Buried Q", "Will this go dormant?", "bq")
    # Bury it: five later records push its binding out of the window.
    for i in range(5):
        small.remember_many([
            MemoryRecordInput(kind="episode", title=f"noise {i}",
                              digest=f"Unrelated day noise {i}.")],
            scope="life", owner_id=OWNER, idempotency_key=f"n{i}")
    out = alive_drives(small, scopes=SCOPES, k=5)
    assert all(d["record_id"] != q for d in out)   # buried = dormant
    # And with NO standing drives at all the desk is simply empty.
    empty = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())
    assert alive_drives(empty, scopes=SCOPES, k=5) == []

    # Purity: the read deposits nothing.
    seq_before = small.current_seq()
    alive_drives(small, scopes=SCOPES, k=5)
    assert small.current_seq() == seq_before


def test_machine_bindings_never_occupy_the_recency_window(system) -> None:
    """Fable5 finding 2 pinned: machine formation bursts must not age his
    drives — maintenance-candidate/bookkeeping rows never occupy window
    slots (the occupancy twin of machine-rows-never-become-drives)."""
    small = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal(),
                         attention_config=AttentionConfig(drive_window_limit=4))
    q = _question(small, "His Q", "Still mine?", "mq")
    # A machine burst: six candidate rows land AFTER his question.
    for i in range(6):
        small.remember_many([
            MemoryRecordInput(kind="summary", title=f"cand {i}",
                              digest=f"Machine grouping {i}.",
                              edges=(("summarizes", q),),
                              attributes={"maintenance_candidate": True})],
            scope="life", owner_id=OWNER, idempotency_key=f"mc{i}")
    out = alive_drives(small, scopes=SCOPES, k=5)
    assert any(d["record_id"] == q for d in out), (
        "a machine burst aged his drive out of the window")


def test_top_k_cap_and_validation(system) -> None:
    for i in range(8):
        _question(system, f"Q{i}", f"Question {i}?", f"k-{i}")
    out = alive_drives(system, scopes=SCOPES, k=3)
    assert len(out) == 3
    with pytest.raises(ValueError, match="scope"):
        alive_drives(system, scopes=[], k=3)
