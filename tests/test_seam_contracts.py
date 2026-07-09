"""Regression tests for the five frozen seam v1 stability contracts.

One test per contract, quoting a2a
`0001-runtime-memory-orchestration/004-memory--to--runtime.md` ("Contracts you
can rely on (I will not move these)"). The runtime builds against these
promises; breaking any of them is a cross-package incident (backlog 0027).

C4 note: cross-process byte-identity is impractical in one test, so this file
asserts the in-process equivalent — identical inputs + as_of produce
byte-identical serialized results on repeated calls, with journal state
deliberately shifted in between (and, at the pipeline level, byte-identity
INCLUDING a pinned trace_id). Store truth is held constant across replays,
matching the documented v1 caveat (as_of anchors journal signals only).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from abstractmemory import (
    AttentionConfig,
    MemorySystem,
    RecallBudget,
    Stimulus,
    TripleAssertion,
)
from abstractmemory.attention import ranking_boost
from abstractmemory.reconstruct import run_reconstruction

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


def _seed(system: MemorySystem) -> None:
    system.add([
        _assertion("m-old", "alice", "wrote", "report", 1),
        _assertion("m-new", "alice", "filed", "report copy", 2),
        _assertion("m-tea", "alice", "likes", "tea", 3),
    ])


def _ids(result) -> List[str]:
    return [h.record_id for h in result.handles]


def _journal_dump(journal) -> Dict[str, Any]:
    """Full observable journal state (every record family + the seq axis)."""
    return {
        "seq": journal.current_seq(),
        "events": [e.to_dict() for e in journal.events(scope=SCOPE, owner_id=OWNER, limit=0)],
        "bindings": [b.to_dict() for b in journal.bindings(fold=False)],
        "closures": [c.to_dict() for c in journal.closures(limit=0)],
        "traces": [t.to_dict() for t in journal.traces(limit=0)],
        "snapshots": [s.to_dict() for s in journal.snapshots(limit=0)],
    }


# ---------------------------------------------------------------------------
# C1 — "reconstruct is a PURE READ … journal=True appends a trace + inert
# audit events that NEVER affect scores; journal=False writes nothing at all."
# ---------------------------------------------------------------------------


def test_c1_journal_false_writes_nothing_and_audit_events_never_change_scores(system, stack) -> None:
    _, journal = stack
    _seed(system)
    r0 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    system.commit_selection(r0.trace_id, ["m-old"])  # give scores something to lose

    # journal=False: the ENTIRE journal state is byte-identical afterwards.
    before = _journal_dump(journal)
    result = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES, journal=False)
    assert result.handles  # a real read happened
    assert _journal_dump(journal) == before

    # journal=True: traces + 'listed' audit events ARE appended, and scores
    # and ordering still never move (audit kinds are structurally inert).
    scores_before = system.activation(scope=SCOPE, owner_id=OWNER)
    order_before = _ids(system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES))
    seq_before = journal.current_seq()
    for _ in range(5):
        system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES, journal=True)
    assert journal.current_seq() > seq_before  # the reads were journaled...
    assert system.activation(scope=SCOPE, owner_id=OWNER) == scores_before
    assert _ids(system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)) == order_before


# ---------------------------------------------------------------------------
# C2 — "commit_selection is the ONLY strengthening path."
# ---------------------------------------------------------------------------


def test_c2_commit_selection_is_the_only_strengthening_path(system) -> None:
    _seed(system)

    # Reconstruct alone — journaled or not — never raises activation.
    for journaled in (True, False, True, True):
        system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES, journal=journaled)
    assert system.activation(scope=SCOPE, owner_id=OWNER) == {}
    zeros = system.activation(["m-old", "m-new"], scope=SCOPE, owner_id=OWNER)
    assert all(v == {"base_level": 0.0, "total": 0.0} for v in zeros.values())

    # One commit deposits the trail; activation rises for exactly the used set.
    r = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    system.commit_selection(r.trace_id, ["m-old"])
    after = system.activation(["m-old", "m-new"], scope=SCOPE, owner_id=OWNER)
    assert after["m-old"]["base_level"] > 0.0
    assert after["m-new"]["base_level"] == 0.0


# ---------------------------------------------------------------------------
# C3 — "Relevance admits, activation reorders. min_activation only filters
# working-set membership; a channel-matched candidate is never suppressed."
# ---------------------------------------------------------------------------


def test_c3_relevance_admits_activation_reorders(system) -> None:
    system.add([
        _assertion("c-match", "quantum", "relates_to", "computing", 1),  # cue-matched, never used
        _assertion("c-noise", "carol", "likes", "tea", 2),               # unmatched, never used
        _assertion("c-hot", "dave", "reads", "books", 3),                # unmatched, heavily used
    ])
    for _ in range(3):  # only commits may strengthen (C2); trace_id is by-reference
        system.commit_selection("t-warmup", ["c-hot"])

    budget = RecallBudget(min_activation=0.5)
    r = system.reconstruct(
        Stimulus(cue_text="quantum computing"), scopes=SCOPES, budget=budget, view="working_set"
    )
    by_id = {h.record_id: h for h in r.handles}

    # Channel-matched c-match survives min_activation DESPITE zero activation.
    assert "c-match" in by_id and by_id["c-match"].relevance
    assert by_id["c-match"].activation["total"] < 0.5
    # Unmatched records live or die by the threshold alone.
    assert "c-hot" in by_id and not by_id["c-hot"].relevance  # admitted as recent, above threshold
    assert "c-noise" not in by_id
    assert {"record_id": "c-noise", "score": 0.0, "reason": "below_min_activation"} in [
        dict(d) for d in r.dropped
    ]

    # At a shelf of ONE, the zero-activation channel match still wins the
    # slot over the trail-hot non-match: under the union, STM admits by
    # activation alone but NEVER displaces channel-matched candidates under
    # scarcity (the C3 fill guarantee).
    tight = system.reconstruct(
        Stimulus(cue_text="quantum computing"), scopes=SCOPES,
        budget=RecallBudget(shelf_size=1, min_activation=0.5), view="working_set",
    )
    assert _ids(tight) == ["c-match"]
    assert tight.handles[0].admission in ("stimulus", "both")

    # With a LARGER budget the union works as designed: the trail-hot record
    # IS admitted stimulus-free, labeled admission="stm".
    roomy = system.reconstruct(
        Stimulus(cue_text="quantum computing"), scopes=SCOPES,
        budget=RecallBudget(shelf_size=6, min_activation=0.5), view="working_set",
    )
    by_id = {h.record_id: h for h in roomy.handles}
    assert "c-match" in by_id and by_id["c-match"].admission in ("stimulus", "both")
    assert "c-hot" in by_id and by_id["c-hot"].admission == "stm"

    # Boost cap: ranking influence is min(boost_scale·activation, max_boost) —
    # capped, so runaway activation can only reorder by a bounded amount.
    assert ranking_boost(1e9) == AttentionConfig().max_boost == 120.0
    assert ranking_boost(1e9, config=AttentionConfig(boost_scale=10.0, max_boost=50.0)) == 50.0


def test_c3_phase0_cheap_unmatched_fills_cannot_starve_the_top_match(system) -> None:
    """a2a 0001/015 violation path (a): at tiny budgets, cheap unmatched
    fills used to consume the headroom the post-fill guard needed — the top
    match fit the TOTAL budget but no longer fit by the time the guard
    fired. Phase-0 placement seats the best channel match FIRST; STM and
    fills compete for the remainder."""
    # Top match: exact pattern hit whose digest (~190 chars -> ~48 tokens)
    # exceeds the stimulus SHARE (60 - 15 STM reservation = 45) but fits the
    # total budget of 60 on its own.
    system.add([
        _assertion("big-match", "proj", "spec", "x" * 181, 1),
        # Cheap unmatched recents (~10 tokens each): pre-fix these filled the
        # 45-token share first and starved the guard (30 + 48 > 60).
        _assertion("cheap-1", "u1", "note", "y" * 30, 2),
        _assertion("cheap-2", "u2", "note", "y" * 30, 3),
        _assertion("cheap-3", "u3", "note", "y" * 30, 4),
        _assertion("hot-1", "h1", "did", "z" * 10, 5),
    ])
    system.commit_selection("t-warm-15a", ["hot-1"])  # STM hot -> reservation active

    r = system.reconstruct(
        Stimulus(cue_text="", patterns=({"subject": "proj"},)), scopes=SCOPES,
        budget=RecallBudget(token_budget=60, shelf_size=4, stm_fraction=0.25),
        journal=False,
    )
    by_id = {h.record_id: h for h in r.handles}
    assert "big-match" in by_id, f"top match evicted: {list(by_id)}"
    assert by_id["big-match"].relevance.get("exact") == 1.0
    # Budget integrity (0001/015 finding 1): tokens_used counts every shelved
    # handle exactly once — STM tokens are never double-added.
    assert r.budget_spent["tokens_used"] == sum(h.token_estimate for h in r.handles)
    assert r.budget_spent["tokens_used"] <= 60


def test_c3_phase0_lesser_match_cannot_satisfy_guard_while_top_match_evicted(system) -> None:
    """a2a 0001/015 violation path (b): a small lesser channel match used to
    satisfy the any-match guard inside the stimulus share while the TOP
    match (too big for the share, fits the total) was evicted. Phase-0
    seats the single BEST match (exact-first, then fused) before anything."""
    system.add([
        _assertion("top-match", "proj", "spec", "x" * 181, 1),      # exact hit, ~48 tokens
        TripleAssertion(subject="note", predicate="mentions", object="minor kumquat detail",
                        scope=SCOPE, owner_id=OWNER, observed_at=_ts(2),
                        attributes={"literal": True}, assertion_id="lesser-match"),
        _assertion("hot-1", "h1", "did", "z" * 10, 3),
    ])
    system.commit_selection("t-warm-15b", ["hot-1"])

    r = system.reconstruct(
        Stimulus(cue_text="kumquat", patterns=({"subject": "proj"},)), scopes=SCOPES,
        budget=RecallBudget(token_budget=60, shelf_size=4, stm_fraction=0.25),
        journal=False,
    )
    ids = [h.record_id for h in r.handles]
    assert "top-match" in ids, f"top match evicted by a lesser match: {ids}"
    # The lesser keyword match may also fit later — but never INSTEAD of the
    # top match, and never ahead of it (exact-first ordering).
    if "lesser-match" in ids:
        assert ids.index("top-match") < ids.index("lesser-match")
    assert r.budget_spent["tokens_used"] == sum(h.token_estimate for h in r.handles)


def test_c3_channel_matched_records_are_never_outranked_or_evicted(system) -> None:
    """Hostile-audit hardening of C3 (f4/f5): channel-matched orders before
    unmatched — a boost-maxed or lesson-kind record with ZERO relevance can
    neither outrank nor budget-evict ANY record the cue matched."""
    # Audit f5: 11 distinct cue tokens; a-match matches exactly one (fused
    # 1/11 ≈ 0.09); b-hot is unmatched but boost-maxed by heavy recent use.
    cue = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo"
    system.add([
        TripleAssertion(subject="doc", predicate="mentions", object="alpha topic notes",
                        scope=SCOPE, owner_id=OWNER, observed_at=_ts(1),
                        attributes={"literal": True}, assertion_id="a-match"),
        TripleAssertion(subject="doc", predicate="covers", object="unrelated subject matter",
                        scope=SCOPE, owner_id=OWNER, observed_at=_ts(2),
                        attributes={"literal": True}, assertion_id="b-hot"),
    ])
    for _ in range(4):  # base_level clamps at 25 = max boost — ordinary heavy use
        system.commit_selection(f"t-{system.current_seq()}", ["b-hot"])

    r = system.reconstruct(Stimulus(cue_text=cue), scopes=SCOPES, journal=False)
    ids = [h.record_id for h in r.handles]
    assert ids.index("a-match") < ids.index("b-hot")

    # Budget-for-one: the matched record wins the only slot (no eviction).
    tight = system.reconstruct(Stimulus(cue_text=cue), scopes=SCOPES,
                               budget=RecallBudget(token_budget=12), journal=False)
    assert [h.record_id for h in tight.handles] == ["a-match"]

    # Audit f4: an irrelevant lesson (kind rank 0, fused 0.0) must not outrank
    # or evict the only keyword-matched memory (kind rank 9, fused 1.0).
    system.add([
        TripleAssertion(subject="ex:lesson-gc", predicate="dcterms:abstract",
                        object="tune gc pauses using zgc flags", scope=SCOPE, owner_id=OWNER,
                        observed_at=_ts(3), attributes={"literal": True, "record_kind": "lesson"},
                        assertion_id="l-gc"),
        TripleAssertion(subject="ex:memory-pool", predicate="dcterms:abstract",
                        object="database connection pool decision", scope=SCOPE, owner_id=OWNER,
                        observed_at=_ts(4), attributes={"literal": True, "record_kind": "memory"},
                        assertion_id="m-pool"),
    ])
    pool = system.reconstruct(Stimulus(cue_text="database connection pool decision"),
                              scopes=SCOPES, journal=False)
    pool_ids = [h.record_id for h in pool.handles]
    assert pool_ids.index("m-pool") < pool_ids.index("l-gc")
    pool_tight = system.reconstruct(Stimulus(cue_text="database connection pool decision"),
                                    scopes=SCOPES, budget=RecallBudget(token_budget=20), journal=False)
    assert "m-pool" in [h.record_id for h in pool_tight.handles]
    assert "l-gc" not in [h.record_id for h in pool_tight.handles]


# ---------------------------------------------------------------------------
# C4 — "Every result carries as_of_seq … replay with Stimulus(as_of=that_seq)
# is bit-exact." (In-process equivalent; see module docstring.)
# ---------------------------------------------------------------------------


def test_c4_as_of_replay_is_byte_identical_on_repeated_calls(system, stack) -> None:
    store, _ = stack
    _seed(system)
    r0 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    system.commit_selection(r0.trace_id, ["m-old", "m-tea"])
    anchor = system.current_seq()

    def replay_bytes() -> str:
        r = system.reconstruct(
            Stimulus(cue_text="alice report", as_of=anchor), scopes=SCOPES, view="working_set"
        )
        assert r.as_of_seq == anchor  # every result carries its anchor
        payload = r.to_dict()
        # trace_id is a FRESH identity per read (uuid4) by design; the
        # replay contract covers result CONTENT. Everything else must match.
        payload.pop("trace_id")
        return json.dumps(payload, sort_keys=True)

    first = replay_bytes()
    # Shift journal state between replays: new commits + journaled reads.
    for _ in range(2):
        r = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
        system.commit_selection(r.trace_id, ["m-new"])
    assert replay_bytes() == first
    assert replay_bytes() == first  # and again: repeated calls, same bytes

    # Pipeline level: with a pinned trace_id, byte-identity holds for the
    # FULL to_dict() JSON (no exclusions) across repeated identical calls.
    def pipeline_bytes() -> str:
        result, _trace = run_reconstruction(
            store=store,
            stimulus=Stimulus(cue_text="alice report"),
            scopes=SCOPES,
            budget=RecallBudget(),
            view="working_set",
            base_activation={"m-old": 8.0},
            trail_activation={},
            as_of_seq=anchor,
            trace_id="pinned-trace",
        )
        return json.dumps(result.to_dict(), sort_keys=True)

    assert pipeline_bytes() == pipeline_bytes()


# ---------------------------------------------------------------------------
# C5 — "Errors are actionable, degradations are labeled #FALLBACK in warnings."
# ---------------------------------------------------------------------------


def test_c5_degraded_channels_emit_fallback_labeled_warnings(system, stack) -> None:
    _, journal = stack
    _seed(system)
    r = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)

    # No embedder anywhere -> the vector channel degradation is labeled.
    assert any(w.startswith("#FALLBACK") and "vector channel unavailable" in w for w in r.warnings)
    # Keyword v1 token scan (FTS5 not landed) is labeled too.
    assert any(w.startswith("#FALLBACK") and "keyword channel v1" in w for w in r.warnings)
    # The journaled trace carries the same labeled warnings (auditability).
    assert set(r.warnings) <= set(journal.traces(limit=1)[0].warnings)
