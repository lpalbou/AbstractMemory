"""The communities detection is BOUNDED (operator's performance rule: no hidden unbounded cost). `_stabilise` runs at
most MAX_DETECTION_ROUNDS (5) Louvain + refine rounds, each warm-started from the previous round's refined
partition. It stops at a fixed point, at a repeated partition (an oscillation: the cycle's smallest partition in
canonical order is kept), or at the cap. The receipt reports the count as `timings_ms.rounds`.

The adversarial oscillating graph (unit weights, no kNN edge): a path A (r00-r04) and a path B (r05-r09), a hub r10
tied to three records of each, and a pendant path r11-r12-r13 hanging off the hub. Each Louvain pass moves the hub
alone to the other side (the side it is on carries the pendant's degree). The pendant is then cut off from its
community, so refine moves it WHOLE after the hub (a community under MIN_COMMUNITY_SIZE merges into its best-linked
neighbour). Four records (the hub and the pendant) flip between the two communities every round, forever. Two
records alone cannot oscillate: every Louvain move raises modularity, and a block of one or two records follows the
hub inside Louvain itself.

Covered: the graph really oscillates (one raw round from each state gives the other, so the test cannot pass on a
graph that settled); the detection stops within the cap, deterministic, and keeps the same partition whichever
state seeds it (a rerun on the unchanged home lands on it again); a non-repeating adversary (refine returning a new
partition every round) is stopped by the cap at exactly MAX_DETECTION_ROUNDS rounds, on both substrate pairs through
the whole pass, with the count in `timings_ms.rounds`.

MUTATION LIST (each red, run against this file on a scratch copy): R1 the cap removed (`while True`); R2 the cap
raised to 12; R3 the oscillation not detected (only a fixed point stops the rounds); R4 the latest cycle state kept
instead of the canonical one; R5 `rounds` missing from timings_ms.
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Tuple

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import communities as C  # noqa: E402

from test_communities import SCOPE, OWNER, _pass, _three_topics, home, kind  # noqa: E402,F401

N = 14
A = list(range(0, 5))
B = list(range(5, 10))
HUB = 10
PENDANT = [11, 12, 13]
EDGES: List[Tuple[int, int]] = ([(0, 1), (1, 2), (2, 3), (3, 4)] + [(5, 6), (6, 7), (7, 8), (8, 9)]
                                + [(HUB, 0), (HUB, 1), (HUB, 2), (HUB, 5), (HUB, 6), (HUB, 7), (HUB, 11)]
                                + [(11, 12), (12, 13)])
#: The two states the detection flips between: the hub and its pendant with B, then with A.
WITH_B = ((0, 1, 2, 3, 4), (5, 6, 7, 8, 9, 10, 11, 12, 13), ())
WITH_A = ((0, 1, 2, 3, 4, 10, 11, 12, 13), (5, 6, 7, 8, 9), ())


def _adj() -> List[Dict[int, float]]:
    adj: List[Dict[int, float]] = [{} for _ in range(N)]
    for a, b in EDGES:
        adj[a][b] = adj[b][a] = 1.0
    return adj


def _state(groups, orphans) -> tuple:
    return tuple(sorted(tuple(g) for g in groups)) + (tuple(orphans),)


def _labels(state: tuple) -> List[int]:
    return C._labels_of(N, [list(g) for g in state[:-1]], list(state[-1]))


def _rid(i: int) -> str:
    return f"ex:episode-r{i:02d}"


def _graph(seed: tuple) -> C.CommunityGraph:
    """The oscillating graph as the pass reads it: engraved weight-1.0 relations (each (subject, relation) once, so
    no fan-out discount), one-hot vectors (cosine 0: no kNN edge), and a previous version per group of `seed`."""
    unit = [r for r, w in C.RELATION_WEIGHTS.items() if w == 1.0 and r not in C.DETECTION_EXCLUDED_RELATIONS]
    graph = C.CommunityGraph(space="fake@14", seq=7)
    for i in range(N):
        graph.nodes[_rid(i)] = C._Node(id=_rid(i), assertion_id=f"a{i:02d}", kind="episode", title=f"E{i}",
                                       digest=f"episode {i}", scope=SCOPE, owner_id=OWNER, observed_at="")
    used = set()
    for a, b in EDGES:
        s, o = (a, b) if a != HUB else (b, a)  # the hub is never the subject: its edges stay undiscounted
        rel = next(r for r in unit if (s, r) not in used)
        used.add((s, rel))
        graph.engraved.append((_rid(s), rel, _rid(o)))
    graph.engraved.sort()
    graph.vec_ids = [_rid(i) for i in range(N)]
    graph.vectors = np.eye(N, dtype=np.float32)
    graph.previous = [C.PreviousCommunity(key=f"{C.KEY_PREFIX}{gi:012x}",
                                          members={_rid(m): {"id": _rid(m), "via": "detected", "since_seq": 1}
                                                   for m in g})
                      for gi, g in enumerate(seed[:-1])]
    return graph


def _detected(det: C.Detection) -> tuple:
    index = {_rid(i): i for i in range(N)}
    return tuple(sorted(tuple(sorted(index[m] for m in g)) for g in det.groups)) + ((),)


def test_the_cap_is_five_rounds() -> None:
    assert C.MAX_DETECTION_ROUNDS == 5


def test_the_graph_really_oscillates() -> None:
    adj = _adj()
    for here, there in ((WITH_A, WITH_B), (WITH_B, WITH_A)):
        groups, orphans, _split = C._refine(C.louvain(adj, init=_labels(here)), adj)
        assert _state(groups, orphans) == there, "one raw round flips the hub and its pendant"


def test_an_oscillation_stops_within_the_cap_on_the_same_partition_whatever_seeds_it() -> None:
    adj = _adj()
    outcomes = []
    for seed in (WITH_A, WITH_B, WITH_A, WITH_B):
        groups, orphans, _split, rounds = C._stabilise(adj, _labels(seed))
        assert rounds == 3 <= C.MAX_DETECTION_ROUNDS  # A -> B -> A: the repeat stops it before the cap
        outcomes.append(_state(groups, orphans))
    # the cycle's smallest partition in canonical order, whichever state entered the cycle (a rerun lands on it)
    assert outcomes == [min(WITH_A, WITH_B)] * 4 == [WITH_B] * 4


def test_detection_on_the_oscillating_graph_is_bounded_and_deterministic() -> None:
    results = []
    for seed in (WITH_A, WITH_B, WITH_A):
        det = C.detect_communities(_graph(seed))
        assert det.rounds == 3 and det.unplaced == [] and det.knn_edges == 0 and det.edges == len(EDGES)
        results.append(_detected(det))
    assert results == [WITH_B] * 3


def test_a_partition_that_never_repeats_is_stopped_by_the_cap(home, monkeypatch) -> None:
    """The adversary: refine hands back a NEW partition every round (the border between two groups walks one record
    further each time), so neither a fixed point nor a repeat ever stops the rounds: only the cap does."""
    _three_topics(home)
    real_refine = C._refine
    calls: List[int] = []

    def walking_refine(labels, adj):
        calls.append(len(calls))
        if len(calls) > 50:
            raise AssertionError("the detection rounds are unbounded")
        n = len(labels)
        real_refine(labels, adj)  # the real cost of a round is still paid
        cut = 1 + (len(calls) - 1) % (n - 1)
        return [list(range(cut)), list(range(cut, n))], [], {}

    monkeypatch.setattr(C, "_refine", walking_refine)
    r = _pass(home)
    assert len(calls) == C.MAX_DETECTION_ROUNDS == r["timings_ms"]["rounds"] == 5
    assert r["communities"] == 2 and r["written"] == 2


def test_the_rounds_are_in_the_receipt(home) -> None:
    _three_topics(home)
    first = _pass(home)
    assert 1 <= first["timings_ms"]["rounds"] <= C.MAX_DETECTION_ROUNDS
    again = _pass(home)  # unchanged: round 1 reproduces the version, round 2 confirms the fixed point
    assert again["skipped"].startswith("unchanged") and again["timings_ms"]["rounds"] == 2
