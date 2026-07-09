"""Co-use pair trails (maintainer-initiated, 2026-07-07 — "a lot of
isolated nodes... not enough relationships are created").

The rule: ALL unordered pairs within the DEPOSITING SLICE (admission
"stimulus"/"both" — exactly the ids that deposit 'selected') wire together
with 'co_selected' trails. Presence ≠ use extends to association: self/STM
members pair with NOTHING, so the hub-node failure cannot route through
identity by construction."""

from __future__ import annotations

from typing import Any

from abstractmemory import RecallBudget, Stimulus, TripleAssertion
from abstractmemory.records import MemoryRecordInput
from abstractmemory.spreading import SpreadParams, spread_activation

SCOPE = "life"
OWNER = "entity:test"
SCOPES = [(SCOPE, OWNER)]


def _remember(system, key: str, title: str, digest: str, **kw: Any) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title=title, digest=digest, **kw)],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def test_co_use_wires_edgeless_formed_records(system, stack) -> None:
    """Two formed records, NO formation edges, both channel-matched in one
    reconstruct → commit → ONE pair trail; same-trace re-commit stays 1
    (idempotent); a second distinct trace makes it 2."""
    _, journal = stack
    gid_a = _remember(system, "cu-1", "Pool outage", "The kelvin pool saturated at noon.")
    gid_b = _remember(system, "cu-2", "Pool fix", "Batching fixed the kelvin pool.")

    r = system.reconstruct(Stimulus(cue_text="kelvin pool"), scopes=SCOPES, trace_id="cu-t1")
    matched = [h.record_id for h in r.handles if h.relevance]
    assert len(matched) == 2
    system.commit_selection("cu-t1", matched)

    pair = system.access_counts(pairs=[(gid_a, gid_b)])["pairs"][(gid_a, gid_b)]
    assert pair == 1

    system.commit_selection("cu-t1", matched)  # replay: journal dedup, still 1
    assert system.access_counts(pairs=[(gid_a, gid_b)])["pairs"][(gid_a, gid_b)] == 1

    r2 = system.reconstruct(Stimulus(cue_text="kelvin pool"), scopes=SCOPES, trace_id="cu-t2")
    system.commit_selection("cu-t2", [h.record_id for h in r2.handles if h.relevance])
    assert system.access_counts(pairs=[(gid_a, gid_b)])["pairs"][(gid_a, gid_b)] == 2


def test_presence_never_pairs_self_and_stm_excluded(system, stack) -> None:
    """The D2 of association: self- and stm-admitted members in the same
    used set deposit ZERO pair events touching them — the depositing-slice
    rule is the hub guard."""
    _, journal = stack
    # Identity core (prompt-active) + a trail-hot record + two matched records.
    [value_gid] = system.remember_many(
        [MemoryRecordInput(kind="value", title="Honesty", digest="State things as they are.",
                           attributes={"value_class": "core"})],
        scope=SCOPE, owner_id=OWNER, idempotency_key="cu-val")
    system.bind(value_gid, scope=SCOPE, owner_id=OWNER,
                search_state="indexed", prompt_state="active", source="operator")
    hot_gid = _remember(system, "cu-hot", "Warm note", "An often used solo note.")
    for i in range(3):
        system.commit_selection(f"cu-warm-{i}", [hot_gid])
    gid_a = _remember(system, "cu-a", "Quartz episode", "The quartz sensor drifted at dawn.")
    gid_b = _remember(system, "cu-b", "Quartz fix", "Recalibrated the quartz sensor.")

    r = system.reconstruct(Stimulus(cue_text="quartz sensor"), scopes=SCOPES,
                           trace_id="cu-t3", budget=RecallBudget(self_fraction=0.3))
    labels = {h.record_id: h.admission for h in r.handles}
    used = [h.record_id for h in r.handles]  # commit-all-rendered pattern
    assert "self" in labels.values() and "stm" in labels.values()
    system.commit_selection("cu-t3", used)

    protected = {rid for rid, label in labels.items() if label in ("self", "stm")}
    pair_events = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["co_selected"], limit=0)
    for e in pair_events:
        assert not (set(e.pair_ids) & _assertion_ids(system, protected)), (
            f"identity/STM presence paired: {e.pair_ids}")
    # ...while the two matched records DID pair.
    assert system.access_counts(pairs=[(gid_a, gid_b)])["pairs"][(gid_a, gid_b)] >= 1


def _assertion_ids(system, graph_ids) -> set:
    from abstractmemory.records import resolve_assertion_ids
    return set(resolve_assertion_ids(system._store, list(graph_ids)).values())


def test_bounded_full_pairing_of_the_slice(system, stack) -> None:
    """A 4-record depositing slice deposits exactly C(4,2)=6 pair events."""
    _, journal = stack
    gids = [_remember(system, f"cu-n{i}", f"Zircon note {i}",
                      f"Zircon observation number {i}.") for i in range(4)]
    r = system.reconstruct(Stimulus(cue_text="zircon"), scopes=SCOPES, trace_id="cu-t4")
    matched = [h.record_id for h in r.handles if h.relevance]
    assert len(matched) == 4
    system.commit_selection("cu-t4", matched)

    pair_events = [e for e in journal.events(scope=SCOPE, owner_id=OWNER,
                                             kinds=["co_selected"], limit=0)
                   if e.trace_id == "cu-t4"]
    assert len(pair_events) == 6


def test_co_use_trail_feeds_spreading(system, stack) -> None:
    """The isolation actually heals: after co-use commits, spreading walks
    the pair trail between two edgeless records."""
    store, journal = stack
    gid_a = _remember(system, "cu-s1", "Falcon sighting", "Saw the falcon at the tower.")
    gid_b = _remember(system, "cu-s2", "Falcon nest", "The falcon nests on the ledge.")
    for t in range(3):
        r = system.reconstruct(Stimulus(cue_text="falcon"), scopes=SCOPES, trace_id=f"cu-s-t{t}")
        system.commit_selection(f"cu-s-t{t}", [h.record_id for h in r.handles if h.relevance])

    from abstractmemory.folds import activation_inputs
    from abstractmemory.attention import AttentionConfig
    _base, trails, _c = activation_inputs(journal, SCOPES, journal.current_seq(),
                                          config=AttentionConfig())
    aid_a, aid_b = sorted(_assertion_ids(system, [gid_a, gid_b]))
    assert trails.get((aid_a, aid_b), 0.0) > 0.0  # the trail exists...

    spread, edges = spread_activation(
        store, {aid_a: 1.0}, scope=SCOPE, owner_id=OWNER,
        params=SpreadParams(), trail_activation=trails)
    assert spread.get(aid_b, 0.0) > 0.0           # ...and spreading crosses it
    assert any({e["source_id"], e["target_id"]} == {aid_a, aid_b} for e in edges)