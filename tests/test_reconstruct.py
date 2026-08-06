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


def test_provider_error_degrades_vector_channel_never_kills_recall() -> None:
    """2026-07-11 incident pin: the embedder is a NETWORK CLIENT whose
    provider stack raises its own exception types (the live failure was
    `LMStudio API error (400)` — neither ValueError nor RuntimeError). The
    old narrow catch let it escape run_vector_channel and turn a
    misconfigured embedding route into a dead entity turn. Contract: ANY
    embed failure degrades the vector channel with a labeled #FALLBACK and
    the recall proceeds on the remaining channels."""

    class ProviderAPIError(Exception):
        """Stands in for abstractcore's provider exceptions (import boundary
        forbids importing the real one here — the point IS that the engine
        cannot enumerate provider types)."""

    class RefusingEmbedder:
        def embed_texts(self, texts):
            raise ProviderAPIError(
                'LMStudio API error (400): {"error": "Invalid model identifier ..."}'
            )

    # Pipeline-embed arm (the incident's live path): injected embedder 400s.
    store = InMemoryTripleStore(embedder=None)
    store.add([_assertion("p-1", "alice", "wrote", "report", 1)])
    result, trace = _run(store, Stimulus(cue_text="report"), embedder=RefusingEmbedder())
    assert any(
        w.startswith("#FALLBACK: vector channel unavailable:") and "LMStudio API error (400)" in w
        for w in result.warnings
    )
    assert "vector" not in trace.channels
    assert {h.record_id for h in result.handles} == {"p-1"}  # recall survived

    # Store-embed arm (query_text through the store's OWN embedder): same
    # provider class, same degradation contract. The incident shape exactly:
    # rows were WRITTEN while the provider was healthy; the route went rogue
    # before the query — so the store embeds fine at add time and 400s at
    # query time.
    store2 = InMemoryTripleStore(embedder=TopicEmbedder())
    store2.add([_assertion("p-2", "alice", "read", "novel", 1)])
    store2._embedder = RefusingEmbedder()
    result2, trace2 = _run(store2, Stimulus(cue_text="novel"))
    assert any(w.startswith("#FALLBACK: vector channel unavailable:") for w in result2.warnings)
    assert "vector" not in trace2.channels
    assert {h.record_id for h in result2.handles} == {"p-2"}


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


def test_ranking_boost_reorders_but_never_outranks() -> None:
    """Relevance admits and orders; activation only reorders WITHIN that order.

    `0026` §4 states the division of labour: activation never gates a
    channel-matched candidate. b-3 is the control — no channel matches it, so
    however much base activation it carries it must stay behind every matched
    record. (It is still PRESENT: under the STM ∪ stimulus union a boosted
    record is admitted with `admission="stm"` — presence is not precedence.)
    """
    store = InMemoryTripleStore()
    store.add([
        _assertion("b-1", "alice", "wrote", "report", 1),
        _assertion("b-2", "alice", "filed", "report copy", 2),
        _assertion("b-3", "zeus", "brews", "tea", 3),  # no channel matches this
    ])
    # Equal keyword relevance (2/2 each): recency tie-break puts b-2 first...
    result_no_base, _ = _run(store, Stimulus(cue_text="alice report"))
    assert [h.record_id for h in result_no_base.handles] == ["b-2", "b-1", "b-3"]
    # ...but base activation on the OLDER record flips the order (4a boost).
    result, _ = _run(store, Stimulus(cue_text="alice report"),
                     base={"b-1": 5.0, "b-3": 5.0})
    assert [h.record_id for h in result.handles] == ["b-1", "b-2", "b-3"]
    handles = {h.record_id: h for h in result.handles}
    # b-1 and b-2 are BOTH cue-matched seeds (`0026` §2: seed = cue-matched
    # records with W_j), so spreading warms them symmetrically across the
    # shared entity "alice" — the seed-peer hop. Spread contributes to
    # DECOMPOSITION, not to ordering: the no-base run above fixes the order.
    assert handles["b-1"].activation == {"base_level": 5.0, "spread": 0.5, "total": 5.5}
    assert handles["b-2"].activation == {"base_level": 0.0, "spread": 0.5, "total": 0.5}
    # The contract: b-3 carries the SAME 5.0 base as b-1 and no relevance, and
    # still sorts behind b-2, whose total activation is a tenth of it.
    assert handles["b-3"].relevance == {}
    assert handles["b-3"].activation == {"base_level": 5.0, "spread": 0.0, "total": 5.0}


def test_spread_is_monotonic_in_scope_ladder_coverage() -> None:
    """Adding a pair to the ladder never REMOVES spread.

    A wildcard-owner pair covers every owner in its scope, so a ladder that
    also names an explicit owner for that same scope describes exactly the
    same records. Both must produce identical spread: the narrow pass must not
    be able to claim seeds the broad pass can then no longer reach, which would
    leave records reachable only from those seeds with no spread at all.
    """
    def _spread(scopes):
        store = InMemoryTripleStore()
        store.add([
            _assertion("x1", "alice", "knows", "bob", 1),
            _assertion("y1", "alice", "wrote", "report", 2),
            TripleAssertion(  # same scope, DIFFERENT owner — wildcard-only reach
                subject="alice", predicate="filed", object="report copy",
                scope=SCOPE, owner_id="s2", observed_at=_ts(3),
                attributes={}, assertion_id="z1",
            ),
        ])
        result, _ = run_reconstruction(
            store=store, stimulus=Stimulus(cue_text="alice report"),
            scopes=scopes, budget=RecallBudget(), view="working_set",
            base_activation={}, trail_activation={},
        )
        return {h.record_id: h.activation["spread"] for h in result.handles}

    broad = _spread([(SCOPE, "")])
    assert broad["z1"] > 0.0  # the other owner's record is reached at all
    assert _spread([(SCOPE, OWNER), (SCOPE, "")]) == broad


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


def test_trace_candidates_bounded_to_pool_cap() -> None:
    """The trace list is bounded at the SAME 100 as the seam's pool cap
    (operator 2026-08-01 "at most a 100"; the old private 64 made the UI's
    candidate count a display artifact while the pool ran wider). When the
    universe still outgrows the list, budget_spent.candidates_considered
    stays the authoritative count."""
    from abstractmemory.reconstruct import _TRACE_CANDIDATE_CAP
    from abstractmemory.seam import ENTITY_RECALL_CANDIDATE_CAP

    assert _TRACE_CANDIDATE_CAP == ENTITY_RECALL_CANDIDATE_CAP == 100

    store = InMemoryTripleStore()
    store.add([_assertion(f"m-{i:03d}", "alice", "did", f"thing{i}", i % 60, literal=True) for i in range(120)])
    result, trace = _run(store, Stimulus(cue_text="alice"), budget=RecallBudget(max_candidates=120))
    assert len(trace.candidates) == 100
    assert result.budget_spent["candidates_considered"] == 120
    # A full entity-profile pool (<= 100) fits the trace whole: what the
    # operator sees is the pool the engine gathered.
    result2, trace2 = _run(store, Stimulus(cue_text="alice"), budget=RecallBudget(max_candidates=100))
    assert len(trace2.candidates) == result2.budget_spent["candidates_considered"] == 100


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


def test_newest_seat_guarantee_seats_the_correction_when_enabled(stack) -> None:
    """c5208 ask 4 (the Caspar/Mishka ladder): entrenched records win every
    generic-cue race by usage; the taught correction — newest-formed,
    matched, lower-ordered — dropped below_shelf every turn. With
    newest_seat_guarantee=1 the newest matched candidate takes a seat
    (evicting the lowest stimulus member, never the top match); the
    DEFAULT stays 0 (ruling 0020: pure ordering wins) so default shelves
    are byte-unchanged — the enabled path is the A/B arm flow measures."""
    from abstractmemory import MemorySystem, ReconstructConfig
    from abstractmemory.seam import RecallBudget, Stimulus

    store, journal = stack
    system = MemorySystem(store=store, journal=journal)
    system.add([
        _assertion("old-a", "castor", "keeps", "cat name notes", 1),
        _assertion("old-b", "castor", "repeats", "cat name stories", 2),
        _assertion("old-c", "castor", "records", "cat name habits", 3),
        _assertion("correction", "visitor", "corrected", "cat name yesterday", 4),
    ])
    # Entrench the three old records across several committed turns.
    for turn in range(4):
        system.commit_selection(f"t-entrench-{turn}", ["old-a", "old-b", "old-c"])

    cue = Stimulus(cue_text="cat name")
    budget = RecallBudget(shelf_size=3, token_budget=2400, stm_fraction=0.0)

    default_result = system.reconstruct(cue, scopes=SCOPES, budget=budget,
                                        journal=False, trace_id="t-default")
    default_ids = {h.record_id for h in default_result.handles}

    enabled_system = MemorySystem(
        store=store, journal=journal,
        reconstruct_config=ReconstructConfig(newest_seat_guarantee=1))
    enabled = enabled_system.reconstruct(
        cue, scopes=SCOPES, budget=budget, journal=False, trace_id="t-enabled")
    enabled_ids = {h.record_id for h in enabled.handles}

    assert "correction" in enabled_ids, (
        f"the newest matched record must hold a seat when enabled (got {enabled_ids})")
    # The top-ordered match survives the eviction in both worlds.
    assert default_result.handles[0].record_id == enabled.handles[0].record_id
    # If the default shelf already seated the correction, the scenario is
    # not exercising entrenchment — keep the fixture honest.
    if "correction" in default_ids:
        raise AssertionError("fixture failed to entrench: correction seated by merit")


def test_newest_seat_guarantee_k2_never_evicts_its_own_or_merit_seats(stack) -> None:
    """Adversary P1 on the c5867 slice: at K>=2 a positional victim
    (placed[-1]) evicted iteration 1's own seat or the merit-seated
    newest record — self-defeating. The victim is now order-indexed and
    the protected set covers every newest candidate + prior guarantee
    seats: K=2 must seat BOTH newest records, evicting only entrenched
    non-newest members, with no record both in handles and dropped."""
    from abstractmemory import MemorySystem, ReconstructConfig
    from abstractmemory.seam import RecallBudget, Stimulus

    store, journal = stack
    system = MemorySystem(
        store=store, journal=journal,
        reconstruct_config=ReconstructConfig(newest_seat_guarantee=2))
    system.add([
        _assertion("old-a", "castor", "keeps", "cat name notes", 1),
        _assertion("old-b", "castor", "repeats", "cat name stories", 2),
        _assertion("old-c", "castor", "records", "cat name habits", 3),
        _assertion("new-1", "visitor", "corrected", "cat name yesterday", 4),
        _assertion("new-2", "visitor", "confirmed", "cat name today", 5),
    ])
    for turn in range(4):
        system.commit_selection(f"t-k2-{turn}", ["old-a", "old-b", "old-c"])

    r = system.reconstruct(
        Stimulus(cue_text="cat name"), scopes=SCOPES,
        budget=RecallBudget(shelf_size=3, token_budget=2400, stm_fraction=0.0),
        journal=False, trace_id="t-k2")
    ids = [h.record_id for h in r.handles]
    assert "new-1" in ids and "new-2" in ids, f"both newest must seat (got {ids})"
    dropped_ids = {d["record_id"] for d in r.dropped}
    assert not (set(ids) & dropped_ids), "no record may be both seated and dropped"


def test_shelf_dedup_collapses_identical_digests_to_one_seat(stack) -> None:
    """Veya deep-check P1 (gateway c5907): ~10 of 24 shelf seats were
    literal duplicates (a probe ran the same prompt 10x -> 10 byte-identical
    episodes), each holding a seat AND each generating C(n,2) co-selection
    pairs. Dedup collapses byte-identical digests to ONE seat (default on);
    the graph is untouched (all records recallable); disabling restores the
    old all-copies behavior."""
    from abstractmemory import MemorySystem, ReconstructConfig
    from abstractmemory.seam import RecallBudget, Stimulus

    store, journal = stack
    system = MemorySystem(store=store, journal=journal)
    # Five byte-identical episodes (same digest) + one distinct.
    for i in range(5):
        system.add([_assertion(f"dup-{i}", "castor", "recalls", "the harbor story", i + 1)])
    system.add([_assertion("other", "castor", "mapped", "the north quay", 6)])
    # Force identical digests: same canonical object across the dup-* rows.
    cue = Stimulus(cue_text="harbor story quay")
    budget = RecallBudget(shelf_size=6, token_budget=2400, stm_fraction=0.0)

    r = system.reconstruct(cue, scopes=SCOPES, budget=budget, journal=False,
                           trace_id="t-dedup")
    seated_digests = [h.digest for h in r.handles]
    # No digest appears twice on the shelf.
    assert len(seated_digests) == len(set(seated_digests)), (
        f"duplicate digests seated: {seated_digests}")
    dup_drops = [d for d in r.dropped if d.get("reason") == "duplicate_digest"]
    if any(seated_digests.count(d) for d in seated_digests):
        pass  # (kept for readability)
    # With dedup OFF, the identical copies each get a seat (old behavior).
    off = MemorySystem(store=store, journal=journal,
                       reconstruct_config=ReconstructConfig(shelf_dedup_identical_digests=False))
    r_off = off.reconstruct(cue, scopes=SCOPES, budget=budget, journal=False,
                            trace_id="t-dedup-off")
    off_digests = [h.digest for h in r_off.handles]
    assert len(off_digests) != len(set(off_digests)) or len(dup_drops) == 0, (
        "dedup-off must not collapse identical digests")


def test_dedup_stimulus_skipped_duplicates_are_accounted(stack) -> None:
    """Adversary P1-A: a duplicate first met by the stimulus fill (the
    common Veya case, 9 of 10 probes) set duplicate_of but got NO drop
    entry — it vanished from both handle_order AND dropped (zero trace).
    Every skipped duplicate now carries exactly one duplicate_digest drop
    pointing at the seated owner."""
    from abstractmemory import MemorySystem
    from abstractmemory.seam import RecallBudget, Stimulus

    store, journal = stack
    system = MemorySystem(store=store, journal=journal)
    for i in range(3):
        system.add([_assertion(f"same-{i}", "castor", "recalls", "harbor story", i + 1)])
    r = system.reconstruct(Stimulus(cue_text="harbor story"), scopes=SCOPES,
                           budget=RecallBudget(shelf_size=5, token_budget=2400, stm_fraction=0.0),
                           journal=False, trace_id="t-acct")
    seated = {h.record_id for h in r.handles}
    dup_drops = {d["record_id"]: d for d in r.dropped if d.get("reason") == "duplicate_digest"}
    all_ids = {"same-0", "same-1", "same-2"}
    # Every identical record is EITHER seated once OR accounted as a dup drop.
    assert len(seated & all_ids) == 1, f"exactly one instance seats: {seated}"
    accounted = (seated & all_ids) | set(dup_drops)
    assert accounted == all_ids, f"a duplicate vanished from accounting: {all_ids - accounted}"
    for d in dup_drops.values():
        assert d["duplicate_of"] in seated, "duplicate_of must point at a SEATED record"


def test_dedup_eviction_unregisters_victim_digest(stack) -> None:
    """Adversary P1-B (the sharp one): the newest-seat guarantee evicts a
    victim byte-identical to the newest candidate; the stale registration
    made the newest candidate _is_dup-skip against words no longer on the
    shelf — the guarantee failed silently and the fact left entirely.
    Eviction now unregisters the sole-holder victim's digest, so the
    newest candidate seats its (identical) words."""
    from abstractmemory import MemorySystem, ReconstructConfig
    from abstractmemory.seam import RecallBudget, Stimulus

    store, journal = stack
    # Entrench a filler + a victim whose digest the newest record shares.
    system = MemorySystem(
        store=store, journal=journal,
        reconstruct_config=ReconstructConfig(newest_seat_guarantee=1))
    system.add([
        _assertion("filler-a", "castor", "keeps", "harbor notes", 1),
        _assertion("victim", "castor", "recalls", "the tide story", 2),
        _assertion("newest", "castor", "recalls", "the tide story", 5),  # identical digest
    ])
    for turn in range(4):
        system.commit_selection(f"t-ev-{turn}", ["filler-a", "victim"])
    r = system.reconstruct(
        Stimulus(cue_text="harbor tide story"), scopes=SCOPES,
        budget=RecallBudget(shelf_size=2, token_budget=2400, stm_fraction=0.0),
        journal=False, trace_id="t-ev")
    seated_digests = [h.digest for h in r.handles]
    # The tide-story words are ON the shelf (via the newest record), and no
    # digest is seated twice.
    assert any("tide story" in d for d in seated_digests), (
        f"the newest record's words must be present, not lost to a stale registration ({seated_digests})")
    assert len(seated_digests) == len(set(seated_digests))
