"""Tests for bounded spreading activation (backlog 0026, v1 record semantics).

Graph fixture vocabulary: assertions ARE the records; two assertions are
neighbors when they share an entity term (subject or object).
"""

from __future__ import annotations

from abstractmemory import InMemoryTripleStore, TripleAssertion
from abstractmemory.spreading import SpreadParams, spread_activation

SCOPE = "session"
OWNER = "s1"


def _ts(i: int) -> str:
    return f"2026-07-05T10:{i:02d}:00.000000+00:00"


def _add(store, aid: str, s: str, p: str, o: str, ts: int, **attrs) -> str:
    store.add(
        [
            TripleAssertion(
                subject=s,
                predicate=p,
                object=o,
                scope=SCOPE,
                owner_id=OWNER,
                observed_at=_ts(ts),
                attributes=dict(attrs),
                assertion_id=aid,
            )
        ]
    )
    return aid


def _chain_store() -> InMemoryTripleStore:
    """e1 -(bob)- e2 -(acme)- e3: a 2-hop chain from e1."""
    store = InMemoryTripleStore()
    _add(store, "e-1", "alice", "knows", "bob", 1)
    _add(store, "e-2", "bob", "works_at", "acme", 2)
    _add(store, "e-3", "acme", "located_in", "paris", 3)
    return store


def test_two_hop_chain_reached() -> None:
    store = _chain_store()
    spread, edges = spread_activation(
        store, {"e-1": 1.0}, scope=SCOPE, owner_id=OWNER, params=SpreadParams(), trail_activation={}
    )
    # hop1: e-2 = 1.0 * 0.5; hop2: e-3 = 0.5 * 0.5
    assert spread == {"e-2": 0.5, "e-3": 0.25}
    assert [(e["source_id"], e["target_id"]) for e in edges] == [("e-1", "e-2"), ("e-2", "e-3")]
    for e in edges:
        assert set(e.keys()) == {"source_id", "predicate", "target_id", "strength_label", "trail_activation", "source"}
        assert e["source"] == "walked"  # vs render-side "stm_trail" entries
        assert e["strength_label"] == "recorded"
        assert e["trail_activation"] == 0.0
    assert edges[0]["predicate"] == "works_at"
    assert edges[1]["predicate"] == "located_in"


def test_max_hops_limits_reach() -> None:
    store = _chain_store()
    spread, _ = spread_activation(
        store, {"e-1": 1.0}, scope=SCOPE, owner_id=OWNER, params=SpreadParams(max_hops=1), trail_activation={}
    )
    assert spread == {"e-2": 0.5}


def test_fan_out_capped_deterministically() -> None:
    store = InMemoryTripleStore()
    _add(store, "e-seed", "hub", "is_a", "node", 1)
    for i in range(1, 6):
        _add(store, f"e-n{i}", "hub", "links_to", f"leaf{i}", 1 + i)
    spread, edges = spread_activation(
        store,
        {"e-seed": 1.0},
        scope=SCOPE,
        owner_id=OWNER,
        params=SpreadParams(max_hops=1, fan_out_cap=2),
        trail_activation={},
    )
    # Audit f10 fix: the cap keeps the most RECENT neighbors (observed_at
    # desc, id desc tie-break) — the docstring's recency preference is now
    # real, not a per-query accident of the id sort.
    assert sorted(spread.keys()) == ["e-n4", "e-n5"]
    assert len(edges) == 2


def test_cycle_terminates_with_convergent_accumulation() -> None:
    store = InMemoryTripleStore()
    _add(store, "e-1", "a", "knows", "b", 1)
    _add(store, "e-2", "b", "knows", "c", 2)
    _add(store, "e-3", "c", "knows", "a", 3)
    spread, edges = spread_activation(
        store,
        {"e-1": 1.0},
        scope=SCOPE,
        owner_id=OWNER,
        params=SpreadParams(max_hops=5, damping=0.9, min_contribution=0.01),
        trail_activation={},
    )
    # hop1 from e-1: e-2 and e-3 each get 0.9; hop2: e-2 → e-3 adds 0.81.
    # No echo back into expanded nodes; the walk terminates despite the cycle.
    assert spread == {"e-2": 0.9, "e-3": 0.9 + 0.81}
    assert len(edges) == 3


def test_excluded_ids_never_receive_nor_relay() -> None:
    store = _chain_store()
    spread, edges = spread_activation(
        store,
        {"e-1": 1.0},
        scope=SCOPE,
        owner_id=OWNER,
        params=SpreadParams(),
        trail_activation={},
        excluded_ids=frozenset({"e-2"}),
    )
    # e-2 is the only path to e-3: excluding it blocks the whole walk.
    assert spread == {}
    assert edges == []


def test_excluded_seed_is_dropped() -> None:
    store = _chain_store()
    spread, edges = spread_activation(
        store,
        {"e-1": 1.0},
        scope=SCOPE,
        owner_id=OWNER,
        params=SpreadParams(),
        trail_activation={},
        excluded_ids=frozenset({"e-1"}),
    )
    assert spread == {}
    assert edges == []


def test_deterministic_outputs() -> None:
    store = InMemoryTripleStore()
    _add(store, "e-1", "alice", "knows", "bob", 1)
    _add(store, "e-2", "bob", "works_at", "acme", 2)
    _add(store, "e-3", "bob", "lives_in", "paris", 3)
    _add(store, "e-4", "acme", "located_in", "paris", 4)
    runs = [
        spread_activation(
            store,
            {"e-1": 1.0},
            scope=SCOPE,
            owner_id=OWNER,
            params=SpreadParams(),
            trail_activation={},
        )
        for _ in range(2)
    ]
    assert runs[0] == runs[1]
    # Neighbor iteration is recency-ordered (audit f10): e-3 (newer) first;
    # the order is still fully deterministic across runs.
    assert [e["target_id"] for e in runs[0][1]][:2] == ["e-3", "e-2"]


def test_trail_activation_boosts_contribution() -> None:
    store = _chain_store()
    spread, edges = spread_activation(
        store,
        {"e-1": 1.0},
        scope=SCOPE,
        owner_id=OWNER,
        params=SpreadParams(max_hops=1),
        trail_activation={("e-1", "e-2"): 25.0},  # canonical sorted pair (journal contract)
    )
    # 1.0 * 0.5 * (1 + 25/25) = 1.0 — a maxed trail doubles the contribution.
    assert spread == {"e-2": 1.0}
    assert edges[0]["trail_activation"] == 25.0


def test_edge_kind_weights_scale_contribution() -> None:
    store = _chain_store()
    spread, _ = spread_activation(
        store,
        {"e-1": 1.0},
        scope=SCOPE,
        owner_id=OWNER,
        params=SpreadParams(max_hops=1, edge_kind_weights={"works_at": 2.0}),
        trail_activation={},
    )
    assert spread == {"e-2": 1.0}


def test_min_contribution_floor_stops_propagation() -> None:
    store = _chain_store()
    spread, _ = spread_activation(
        store,
        {"e-1": 1.0},
        scope=SCOPE,
        owner_id=OWNER,
        params=SpreadParams(damping=0.1, min_contribution=0.05),
        trail_activation={},
    )
    # hop1 = 0.1 passes the floor; hop2 = 0.01 does not (no accumulation, no edge).
    assert spread == {"e-2": 0.1}


def test_max_edges_budget_is_hard() -> None:
    store = InMemoryTripleStore()
    _add(store, "e-1", "alice", "knows", "bob", 1)
    _add(store, "e-2", "bob", "works_at", "acme", 2)
    _add(store, "e-3", "bob", "lives_in", "paris", 3)
    spread, edges = spread_activation(
        store,
        {"e-1": 1.0},
        scope=SCOPE,
        owner_id=OWNER,
        params=SpreadParams(max_edges=1),
        trail_activation={},
    )
    assert len(edges) == 1
    assert len(spread) == 1


def test_literal_neighbor_receives_but_does_not_relay() -> None:
    store = InMemoryTripleStore()
    _add(store, "e-1", "alice", "knows", "bob", 1)
    # Literal fact about bob: reachable (a cue about bob should light it up),
    # but its object is a value, not an entity — no onward traversal from it.
    _add(store, "e-2", "bob", "age", "42", 2, literal=True)
    _add(store, "e-3", "42", "meaning", "everything", 3)  # only reachable THROUGH the literal
    spread, edges = spread_activation(
        store, {"e-1": 1.0}, scope=SCOPE, owner_id=OWNER, params=SpreadParams(max_hops=3), trail_activation={}
    )
    assert spread == {"e-2": 0.5}
    assert len(edges) == 1


def test_empty_and_unknown_seeds() -> None:
    store = _chain_store()
    assert spread_activation(
        store, {}, scope=SCOPE, owner_id=OWNER, params=SpreadParams(), trail_activation={}
    ) == ({}, [])
    assert spread_activation(
        store, {"nope": 1.0}, scope=SCOPE, owner_id=OWNER, params=SpreadParams(), trail_activation={}
    ) == ({}, [])
    assert spread_activation(
        store, {"e-1": 0.0}, scope=SCOPE, owner_id=OWNER, params=SpreadParams(), trail_activation={}
    ) == ({}, [])


def test_scope_partition_respected() -> None:
    store = _chain_store()
    # Same entity term in ANOTHER owner's scope must never receive spread.
    store.add(
        [
            TripleAssertion(
                subject="bob",
                predicate="works_at",
                object="globex",
                scope=SCOPE,
                owner_id="OTHER",
                observed_at=_ts(9),
                assertion_id="e-other",
            )
        ]
    )
    spread, _ = spread_activation(
        store, {"e-1": 1.0}, scope=SCOPE, owner_id=OWNER, params=SpreadParams(), trail_activation={}
    )
    assert "e-other" not in spread
