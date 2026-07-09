"""Tests for the pure reconstruction pipeline (backlog 0019/0020/0026 v1).

Uses InMemoryTripleStore only. The fake embedder maps texts to fixed topic
vectors by marker word so cosine outcomes are exact and deterministic.
"""

from __future__ import annotations

import json
from typing import List, Sequence

import pytest

from abstractmemory import InMemoryTripleStore, TripleAssertion
from abstractmemory.canonical_text import CANONICAL_TEXT_VERSION, canonical_text
from abstractmemory.in_memory_store import _canonical_text as in_memory_canonical_text
from abstractmemory.lancedb_store import _canonical_text as lancedb_canonical_text
from abstractmemory.reconstruct import run_reconstruction
from abstractmemory.seam import RecallBudget, Stimulus
from abstractmemory.sqlite_store import _canonical_text as sqlite_canonical_text

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _ts(i: int) -> str:
    return f"2026-07-05T10:{i:02d}:00.000000+00:00"


def _assertion(aid: str, s: str, p: str, o: str, ts: int, **attrs) -> TripleAssertion:
    return TripleAssertion(
        subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
        observed_at=_ts(ts), attributes=dict(attrs), assertion_id=aid,
    )


class TopicEmbedder:
    """Marker-word embedder: exact, deterministic cosine outcomes.

    "museum" and "gallery" land in the same semantic region without sharing a
    token — the classic vector-recalls-what-keyword-misses scenario.
    """

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            low = str(t).lower()
            if "museum" in low:
                out.append([1.0, 0.0, 0.0])
            elif "gallery" in low:
                out.append([1.0, 1.0, 0.0])  # cosine 0.7071 vs museum topic
            else:
                out.append([0.0, 0.0, 1.0])
        return out


def _run(store, stimulus, *, budget=None, view="shelf", base=None, trail=None, **kw):
    return run_reconstruction(
        store=store,
        stimulus=stimulus,
        scopes=SCOPES,
        budget=budget or RecallBudget(),
        view=view,
        base_activation=base or {},
        trail_activation=trail or {},
        **kw,
    )


# --- canonical_text golden parity -----------------------------------------

def test_canonical_text_matches_all_three_stores_byte_identical() -> None:
    # v2: clean record digests (title\ndigest\nkeywords); the stores now
    # IMPORT the shared function (aliases), so parity holds by construction —
    # the battery still guards against anyone re-introducing a private copy.
    assert CANONICAL_TEXT_VERSION == 2
    battery = [
        _assertion("g-1", "alice", "works_at", "acme", 1),
        _assertion("g-2", "alice", "authored", "Report Q3", 2, literal=True),
        _assertion(
            "g-3", "bob", "visited", "paris", 3,
            subject_type="person", object_type="city",
            evidence_quote="Bob said he visited Paris.",
            original_context="short context",
        ),
        _assertion("g-4", "carol", "noted", "detail", 4, original_context="x" * 401),
        _assertion("g-5", "dave", "flagged", "issue", 5, subject_type="  ", evidence_quote=""),
    ]
    for a in battery:
        expected = canonical_text(a)
        assert in_memory_canonical_text(a) == expected
        assert sqlite_canonical_text(a) == expected
        assert lancedb_canonical_text(a) == expected
    # Truncation shape pinned: 400 chars + ellipsis, labeled behavior.
    assert canonical_text(battery[3]).endswith("x" * 10 + "…")


# --- channels ---------------------------------------------------------------

def test_exact_channel_pattern_and_anchor() -> None:
    store = InMemoryTripleStore()
    store.add([_assertion("e-1", "alice", "works_at", "acme", 1), _assertion("e-2", "bob", "likes", "tea", 2)])
    stim = Stimulus(cue_text="", patterns=({"subject": "alice"},), anchor_record_ids=("e-2",))
    result, trace = _run(store, stim)
    by_id = {h.record_id: h for h in result.handles}
    assert by_id["e-1"].relevance == {"exact": 1.0}
    assert "exact: subject=alice" in by_id["e-1"].cues
    assert by_id["e-2"].relevance == {"exact": 1.0}
    assert "anchor: e-2" in by_id["e-2"].cues
    assert trace.channels == ("exact",)
    # Exact hits order before non-exact and each other deterministically.
    assert [h.record_id for h in result.handles][:2] in (["e-1", "e-2"], ["e-2", "e-1"])


def test_exact_pattern_cannot_escalate_scope_and_empty_pattern_skipped() -> None:
    store = InMemoryTripleStore()
    store.add([_assertion("e-1", "alice", "works_at", "acme", 1)])
    stim = Stimulus(cue_text="", patterns=({"subject": "alice", "scope": "global"}, {}))
    result, _ = _run(store, stim)
    assert any("scope ladder is authoritative" in w for w in result.warnings)
    assert any("empty exact pattern skipped" in w for w in result.warnings)
    assert {h.record_id for h in result.handles} == {"e-1"}


def test_missing_anchor_warns() -> None:
    store = InMemoryTripleStore()
    store.add([_assertion("e-1", "alice", "works_at", "acme", 1)])
    result, _ = _run(store, Stimulus(cue_text="", anchor_record_ids=("ghost",)))
    assert any("anchor records not found" in w and "ghost" in w for w in result.warnings)


def test_keyword_channel_scores_and_details() -> None:
    store = InMemoryTripleStore()
    store.add([
        _assertion("k-1", "alice", "wrote", "report", 1),
        _assertion("k-2", "alice", "likes", "tea", 2),
        _assertion("k-3", "bob", "reads", "books", 3),
    ])
    result, trace = _run(store, Stimulus(cue_text="alice report"))
    by_id = {h.record_id: h for h in result.handles}
    assert by_id["k-1"].relevance["keyword"] == 1.0  # 2/2 tokens
    assert by_id["k-2"].relevance["keyword"] == 0.5  # 1/2 tokens
    assert "keyword" not in by_id["k-3"].relevance
    assert "keyword: matched alice, report (2/2)" in by_id["k-1"].cues
    assert any(w.startswith("#FALLBACK: keyword channel v1 = token scan") for w in result.warnings)
    assert "keyword" in trace.channels
    # Ranked by fused score: k-1 (1.0) before k-2 (0.5).
    ids = [h.record_id for h in result.handles]
    assert ids.index("k-1") < ids.index("k-2")


def test_vector_channel_unavailable_falls_back_labeled() -> None:
    store = InMemoryTripleStore(embedder=None)
    store.add([_assertion("v-1", "alice", "wrote", "report", 1)])
    result, trace = _run(store, Stimulus(cue_text="report"))
    assert any(w.startswith("#FALLBACK: vector channel unavailable:") for w in result.warnings)
    assert "vector" not in trace.channels
    # Degraded vector channel never blocks the others.
    assert {h.record_id for h in result.handles} == {"v-1"}


def test_vector_channel_with_embedder_normalized_scores() -> None:
    emb = TopicEmbedder()
    store = InMemoryTripleStore(embedder=emb)
    store.add([
        _assertion("v-1", "bob", "toured", "museum", 1),
        _assertion("v-2", "dave", "visited", "gallery", 2),
        _assertion("v-3", "alice", "wrote", "report", 3),
    ])
    result, trace = _run(store, Stimulus(cue_text="museum"), budget=RecallBudget())
    by_id = {h.record_id: h for h in result.handles}
    # Confidence-scaled normalization (0002 decay-regression fix): a STRONG
    # field (top 1.0, far above floor+span) keeps its top at 1.0; mid-field
    # scores are floor-relative — (0.7071−0.05)/(1.0−0.05) — instead of the
    # old raw ratio 0.7071 (the floor is the zero of the relevance axis).
    assert by_id["v-1"].relevance["vector"] == 1.0
    assert abs(by_id["v-2"].relevance["vector"] - (0.7071 - 0.05) / 0.95) < 1e-3
    assert "vector" not in by_id["v-3"].relevance  # cosine 0: clipped, not admitted as noise
    assert "vector" in trace.channels
    assert any(c.startswith("vector: cosine") for c in by_id["v-2"].cues)


def test_vector_channel_uses_precomputed_stimulus_embedding() -> None:
    store = InMemoryTripleStore(embedder=TopicEmbedder())
    store.add([_assertion("v-1", "bob", "toured", "museum", 1)])
    # No cue_text at all: only the precomputed turn embedding drives recall.
    result, _ = _run(store, Stimulus(cue_text="", embedding=(1.0, 0.0, 0.0)))
    assert result.handles[0].relevance["vector"] == 1.0


def test_vector_channel_uses_injected_embedder_when_store_lacks_one() -> None:
    store = InMemoryTripleStore(embedder=TopicEmbedder())
    store.add([_assertion("v-1", "bob", "toured", "museum", 1)])
    # Simulate the LanceDB scenario: vectors exist in storage but the store
    # instance has no query-time embedder (query_text would raise). The
    # injected pipeline embedder pre-embeds the cue into query_vector.
    store._embedder = None
    result, _ = _run(store, Stimulus(cue_text="museum"), embedder=TopicEmbedder())
    assert result.handles[0].relevance["vector"] == 1.0
    assert not any("vector channel unavailable" in w for w in result.warnings)


# --- fusion: reserved slots REMOVED (maintainer decision 2026-07-06) --------

def test_reserved_slots_mechanism_is_gone() -> None:
    """Removal regression: RecallBudget no longer accepts reserved_slots and
    membership is one ordering + greedy fill — the old quota rescue (a
    weaker keyword hit displacing a stronger fused candidate) must NOT
    happen, and the lost_reserved_slot_race dropped-reason is extinct."""
    with pytest.raises(TypeError, match="reserved_slots"):
        RecallBudget(reserved_slots={"keyword": 1})

    emb = TopicEmbedder()
    store = InMemoryTripleStore(embedder=emb)
    store.add([
        _assertion("r-v1", "bob", "toured", "museum", 1),      # vector 1.0 (+ keyword 1/3)
        _assertion("r-v2", "dave", "visited", "gallery", 2),   # vector 0.7071
        _assertion("r-k1", "alice", "arranged", "visit plans", 3, literal=True),  # keyword 2/3
    ])
    result, _ = _run(store, Stimulus(cue_text="museum visit plans"),
                     budget=RecallBudget(shelf_size=2, token_budget=2400))
    # Pure ordering wins: fused top-2, no quota-forced substitution.
    assert {h.record_id for h in result.handles} == {"r-v1", "r-v2"}
    dropped = {d["record_id"]: d["reason"] for d in result.dropped}
    assert dropped["r-k1"] == "below_shelf"
    assert "lost_reserved_slot_race" not in set(dropped.values())


# --- exclusions and ordering -------------------------------------------------

def test_excluded_ids_respected_everywhere() -> None:
    store = InMemoryTripleStore()
    store.add([
        _assertion("x-1", "alice", "wrote", "report", 1),
        _assertion("x-2", "alice", "reviews", "report drafts", 2),
    ])
    stim = Stimulus(cue_text="alice report", patterns=({"subject": "alice"},), anchor_record_ids=("x-2",))
    result, trace = _run(store, stim, excluded_ids=frozenset({"x-2"}))
    assert {h.record_id for h in result.handles} == {"x-1"}
    assert all(d["record_id"] != "x-2" for d in result.dropped)
    assert all(c["record_id"] != "x-2" for c in trace.candidates)
    assert any("anchor x-2 excluded" in w for w in result.warnings)


def test_ranking_boost_reorders_but_never_admits() -> None:
    store = InMemoryTripleStore()
    store.add([
        _assertion("b-1", "alice", "wrote", "report", 1),
        _assertion("b-2", "alice", "filed", "report copy", 2),
    ])
    # Equal keyword relevance (2/2 each): recency tie-break puts b-2 first...
    result_no_base, _ = _run(store, Stimulus(cue_text="alice report"))
    assert [h.record_id for h in result_no_base.handles] == ["b-2", "b-1"]
    # ...but base activation on the OLDER record flips the order (4a boost).
    result, _ = _run(store, Stimulus(cue_text="alice report"), base={"b-1": 5.0})
    assert [h.record_id for h in result.handles] == ["b-1", "b-2"]
    b1 = {h.record_id: h for h in result.handles}["b-1"]
    assert b1.activation == {"base_level": 5.0, "spread": 0.0, "total": 5.0}
    # b-2 receives spread from b-1 (shared entity "alice") — and the no-base
    # run above proves spread contributes to DECOMPOSITION, not to ordering.
    b2 = {h.record_id: h for h in result.handles}["b-2"]
    assert b2.activation == {"base_level": 0.0, "spread": 0.5, "total": 0.5}


def test_exact_hits_order_first() -> None:
    store = InMemoryTripleStore()
    store.add([
        _assertion("f-1", "alice", "wrote", "report", 1),
        _assertion("f-2", "bob", "likes", "tea", 2),
    ])
    stim = Stimulus(cue_text="alice wrote report", patterns=({"subject": "bob"},))
    # f-1 has keyword 3/3 = 1.0; f-2 is the exact hit and still leads.
    result, _ = _run(store, stim)
    assert [h.record_id for h in result.handles][0] == "f-2"


# --- budgets, stop reasons, views ---------------------------------------------

def test_token_budget_exhaustion_drops_with_reason() -> None:
    store = InMemoryTripleStore()
    store.add([
        _assertion("t-1", "alice", "wrote", "report", 1),
        _assertion("t-2", "alice", "filed", "report copy", 2),
    ])
    # canonical_text("alice wrote report") = 18 chars → 5 tokens; budget fits one.
    result, _ = _run(store, Stimulus(cue_text="alice report"), budget=RecallBudget(token_budget=6))
    assert len(result.handles) == 1
    assert result.stop_reason == "budget_exhausted"
    assert any(d["reason"] == "budget_exhausted" for d in result.dropped)
    assert result.budget_spent["tokens_used"] <= 6


def test_no_candidates_stop_reason() -> None:
    result, trace = _run(InMemoryTripleStore(), Stimulus(cue_text="anything"))
    assert result.stop_reason == "no_candidates"
    assert result.handles == ()
    assert trace.stop_reason == "no_candidates"


def test_below_shelf_dropped_with_reason() -> None:
    store = InMemoryTripleStore()
    store.add([_assertion(f"s-{i}", "alice", "did", f"thing{i}", i, literal=True) for i in range(1, 5)])
    result, _ = _run(store, Stimulus(cue_text="alice"), budget=RecallBudget(shelf_size=2))
    assert len(result.handles) == 2
    reasons = {d["reason"] for d in result.dropped}
    assert reasons == {"below_shelf"}


def _spread_fixture():
    """S (channel-matched) — N (1 hop) — M (2 hops); N/M outside recents."""
    store = InMemoryTripleStore()
    store.add([
        _assertion("w-m", "acme", "located_in", "paris", 1),
        _assertion("w-n", "bob", "works_at", "acme", 2),
        _assertion("w-f", "carol", "likes", "tea", 3),
        _assertion("w-s", "alice", "knows", "bob", 4),
    ])
    # max_candidates=2 → recents = {w-s, w-f}; w-n/w-m only reachable by spreading.
    budget = RecallBudget(max_candidates=2, min_activation=None)
    return store, budget


def test_working_set_includes_edges_and_decomposition_sums() -> None:
    store, budget = _spread_fixture()
    result, trace = _run(store, Stimulus(cue_text="alice"), budget=budget, view="working_set",
                         base={"w-n": 0.1})
    by_id = {h.record_id: h for h in result.handles}
    # Spread-only members joined the working set with attributable activation.
    assert by_id["w-n"].activation == {"base_level": 0.1, "spread": 0.5, "total": 0.6}
    assert by_id["w-m"].activation == {"base_level": 0.0, "spread": 0.25, "total": 0.25}
    assert "spread: via works_at from w-s" in by_id["w-n"].cues
    edges = [(e["source_id"], e["target_id"]) for e in result.edges]
    assert ("w-s", "w-n") in edges and ("w-n", "w-m") in edges
    for e in result.edges:
        assert e["strength_label"] == "recorded"
    for h in result.handles:
        assert abs(h.activation["total"] - (h.activation["base_level"] + h.activation["spread"])) < 1e-12
    assert trace.budget_spent["edges_visited"] == len(result.edges)


def test_shelf_view_has_no_edges_and_no_spread_members() -> None:
    store, budget = _spread_fixture()
    result, _ = _run(store, Stimulus(cue_text="alice"), budget=budget, view="shelf")
    assert result.edges == ()
    ids = {h.record_id for h in result.handles}
    assert "w-n" not in ids and "w-m" not in ids  # spread members are working_set-only


def test_min_activation_filters_spread_only_members_never_channel_matches() -> None:
    store, budget_base = _spread_fixture()
    budget = RecallBudget(max_candidates=2, min_activation=0.3)
    result, _ = _run(store, Stimulus(cue_text="alice"), budget=budget, view="working_set")
    ids = {h.record_id for h in result.handles}
    # w-n total = 0.5 passes; w-m total = 0.25 filtered; channel match w-s
    # stays even though its OWN total activation is 0.0 (< threshold).
    assert "w-s" in ids and "w-n" in ids
    assert "w-m" not in ids
    dropped = {d["record_id"]: d["reason"] for d in result.dropped}
    assert dropped["w-m"] == "below_min_activation"
    # Recent-but-unmatched member with zero activation is membership-filtered too.
    assert dropped.get("w-f") == "below_min_activation"


def test_min_activation_ignored_in_shelf_view() -> None:
    store, _ = _spread_fixture()
    budget = RecallBudget(max_candidates=2, min_activation=99.0)
    result, _ = _run(store, Stimulus(cue_text="alice"), budget=budget, view="shelf")
    assert {h.record_id for h in result.handles} == {"w-s", "w-f"}


# --- traces, serialization, determinism ---------------------------------------

def test_trace_is_complete_and_faithful() -> None:
    store = InMemoryTripleStore()
    store.add([
        _assertion("c-1", "alice", "wrote", "report", 1),
        _assertion("c-2", "bob", "likes", "tea", 2),
    ])
    budget = RecallBudget(shelf_size=1)
    stim = Stimulus(cue_text="alice report", patterns=({"subject": "alice"},))
    result, trace = _run(store, stim, budget=budget, as_of_seq=7, trace_id="tr-1")
    assert trace.trace_id == result.trace_id == "tr-1"
    assert result.as_of_seq == 7
    assert trace.trace_kind == "reconstruct"
    assert len(trace.query_fingerprint) == 16 and int(trace.query_fingerprint, 16) >= 0
    assert trace.searched_scopes == ({"scope": SCOPE, "owner_id": OWNER},)
    assert trace.channels == ("exact", "keyword")
    assert trace.selected == tuple(h.record_id for h in result.handles)
    assert set(trace.selected) | {d["record_id"] for d in trace.dropped} == {"c-1", "c-2"}
    assert {c["record_id"] for c in trace.candidates} == {"c-1", "c-2"}
    for c in trace.candidates:
        assert set(c["scores"]).issubset({"exact", "keyword", "vector"})
    assert trace.budgets == budget.to_dict()
    assert trace.budget_spent == result.budget_spent
    assert trace.selector_route == "heuristic"
    assert all(cue in trace.cues for h in result.handles for cue in h.cues)
    # Same stimulus → same fingerprint; different → different.
    _, trace2 = _run(store, stim, budget=budget)
    assert trace2.query_fingerprint == trace.query_fingerprint
    _, trace3 = _run(store, Stimulus(cue_text="other cue"), budget=budget)
    assert trace3.query_fingerprint != trace.query_fingerprint


def test_trace_candidates_bounded_to_64() -> None:
    store = InMemoryTripleStore()
    store.add([_assertion(f"m-{i:03d}", "alice", "did", f"thing{i}", i % 60, literal=True) for i in range(100)])
    result, trace = _run(store, Stimulus(cue_text="alice"), budget=RecallBudget(max_candidates=100))
    assert len(trace.candidates) == 64
    assert result.budget_spent["candidates_considered"] == 100


def test_result_and_trace_json_round_trip() -> None:
    store = InMemoryTripleStore(embedder=TopicEmbedder())
    store.add([
        _assertion("j-1", "bob", "toured", "museum", 1),
        _assertion("j-2", "bob", "works_at", "acme", 2),
    ])
    stim = Stimulus(cue_text="museum", embedding=(1.0, 0.0, 0.0), anchor_record_ids=("j-2",))
    result, trace = _run(store, stim, view="working_set", trail={("j-1", "j-2"): 4.0})
    for payload in (result.to_dict(), trace.to_dict()):
        round_tripped = json.loads(json.dumps(payload))
        assert round_tripped == payload
    assert result.to_dict()["view"] == "working_set"
    assert isinstance(result.to_dict()["handles"], list)


def test_deterministic_end_to_end() -> None:
    store = InMemoryTripleStore(embedder=TopicEmbedder())
    store.add([
        _assertion("d-1", "bob", "toured", "museum", 1),
        _assertion("d-2", "dave", "visited", "gallery", 2),
        _assertion("d-3", "alice", "wrote", "museum report", 3, literal=True),
    ])
    stim = Stimulus(cue_text="museum report", patterns=({"subject": "bob"},))
    a_result, a_trace = _run(store, stim, view="working_set", trace_id="fixed")
    b_result, b_trace = _run(store, stim, view="working_set", trace_id="fixed")
    assert a_result.to_dict() == b_result.to_dict()
    ta, tb = a_trace.to_dict(), b_trace.to_dict()
    ta.pop("observed_at"), tb.pop("observed_at")  # journal timestamp is wall-clock by design
    assert ta == tb


def test_handles_shape_and_kind_hook() -> None:
    store = InMemoryTripleStore()
    long_object = "very " * 40 + "long object"
    original = _assertion("h-1", "alice", "described", long_object, 1, literal=True)
    store.add([original])
    result, _ = _run(store, Stimulus(cue_text="alice"))
    h = result.handles[0]
    assert h.kind == "memory"
    assert len(h.title) <= 120 and h.title.endswith("…")
    assert h.digest == canonical_text(original)
    assert h.token_estimate == len(h.digest) // 4 + 1
    assert h.binding == "indexed+inactive"
    assert h.scope == SCOPE and h.owner_id == OWNER
    assert h.cues  # never empty for selected handles


def test_activation_contributions_appended_as_cues() -> None:
    store = InMemoryTripleStore()
    store.add([_assertion("a-1", "alice", "wrote", "report", 1)])
    result, _ = _run(
        store, Stimulus(cue_text="alice"),
        activation_contributions={"a-1": ("selected x3 (recent)",)},
    )
    assert "selected x3 (recent)" in result.handles[0].cues


def test_invalid_view_rejected() -> None:
    store = InMemoryTripleStore()
    with pytest.raises(ValueError, match="view"):
        _run(store, Stimulus(cue_text="x"), view="prompt")
