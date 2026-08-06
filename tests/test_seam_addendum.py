"""Seam addendum features (a2a 0001/009 + 0001/011 + 0002/001).

Covers the ADDITIVE seam v1 extensions: Stimulus.turn_id provenance flow,
MemoryHandle.payload_tiers + MemorySystem.payload() (verbatim-on-demand
stub), topic surfacing for the emergence experiment's focus metric, and the
Arm-B ablation switch (recency+embedding baseline over the same substrate).
Uses the shared conftest `stack`/`system` fixtures (both backend pairs).
"""

from __future__ import annotations

import json
from typing import Any, List

import pytest

from abstractmemory import MemorySystem, RecallBudget, Stimulus, TripleAssertion
from abstractmemory.canonical_text import canonical_text

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _ts(i: int) -> str:
    return f"2026-07-05T10:{i:02d}:00.000000+00:00"


def _assertion(aid: str, s: str, p: str, o: str, ts: int, **attrs: Any) -> TripleAssertion:
    return TripleAssertion(
        subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
        observed_at=_ts(ts), attributes=dict(attrs), assertion_id=aid,
    )


def _seed(system) -> None:
    system.add([
        _assertion("m-old", "alice", "wrote", "report", 1),
        _assertion("m-new", "alice", "filed", "report copy", 2),
        _assertion("m-tea", "alice", "likes", "tea", 3),
    ])


def _ids(result) -> List[str]:
    return [h.record_id for h in result.handles]


# ---------------------------------------------------------------------------
# Stimulus.turn_id (0001/011 ask 4)
# ---------------------------------------------------------------------------


def test_stimulus_turn_id_normalized_and_json_safe() -> None:
    assert Stimulus(cue_text="x", turn_id="  t-9  ").turn_id == "t-9"
    assert Stimulus(cue_text="x", turn_id="   ").turn_id is None
    assert Stimulus(cue_text="x").turn_id is None
    payload = Stimulus(cue_text="x", turn_id="t-9").to_dict()
    assert payload["turn_id"] == "t-9"
    assert json.loads(json.dumps(payload)) == payload


def test_turn_id_flows_into_trace_need_and_listed_provenance(system, stack) -> None:
    _, journal = stack
    _seed(system)
    system.reconstruct(Stimulus(cue_text="alice report", turn_id="turn-7"), scopes=SCOPES)

    trace = journal.traces(limit=1)[0]
    assert trace.need["turn_id"] == "turn-7"
    listed = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["listed"], limit=0)
    assert listed and all(e.provenance == {"turn_id": "turn-7"} for e in listed)

    # Fingerprint stability: turn_id is provenance, not retrieval content —
    # the same cue in another turn is the SAME query (qmult semantics).
    system.reconstruct(Stimulus(cue_text="alice report", turn_id="turn-8"), scopes=SCOPES)
    t8, t7 = journal.traces(limit=2)
    assert t8.query_fingerprint == t7.query_fingerprint


# ---------------------------------------------------------------------------
# payload tiers (0001/009 item 2, 0001/011 ask 6)
# ---------------------------------------------------------------------------


def test_handles_carry_payload_tiers_digest_default(system) -> None:
    _seed(system)
    r = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    assert all(h.payload_tiers == ("digest",) for h in r.handles)
    assert r.to_dict()["handles"][0]["payload_tiers"] == ["digest"]


def test_payload_digest_tier_returns_canonical_content(system) -> None:
    original = _assertion("p-1", "alice", "wrote", "report", 1, original_context="full context here")
    system.add([original])
    out = system.payload("p-1")  # tier defaults to digest
    assert out == {
        "record_id": "p-1",
        "tier": "digest",
        "content": canonical_text(original),
        "token_estimate": len(canonical_text(original)) // 4 + 1,
    }
    assert json.loads(json.dumps(out)) == out


def test_payload_errors_are_actionable(system) -> None:
    _seed(system)
    with pytest.raises(ValueError, match="ghost"):
        system.payload("ghost")
    for reserved in ("summary", "compact"):
        with pytest.raises(NotImplementedError, match="0021.*payload_ref"):
            system.payload("m-old", tier=reserved)
    # raw is implemented (formation addendum) but requires a stored
    # payload_ref — plain triples have no verbatim tier.
    with pytest.raises(ValueError, match="no raw tier"):
        system.payload("m-old", tier="raw")
    with pytest.raises(ValueError, match="unknown payload tier"):
        system.payload("m-old", tier="hologram")
    with pytest.raises(ValueError, match="record_id"):
        system.payload("")


# ---------------------------------------------------------------------------
# topic surfacing (0002/001 question 3)
# ---------------------------------------------------------------------------


def test_topic_attribute_surfaces_in_handle_provenance(system) -> None:
    system.add([
        _assertion("t-1", "pool", "decided_as", "pgbouncer", 1, topic="A"),
        _assertion("t-2", "carol", "likes", "tea", 2),          # no topic
        _assertion("t-3", "dave", "reads", "books", 3, topic=7),  # non-string: not coerced
    ])
    r = system.reconstruct(Stimulus(cue_text="pool tea books"), scopes=SCOPES)
    by_id = {h.record_id: h for h in r.handles}
    assert by_id["t-1"].provenance["topic"] == "A"
    assert "topic" not in by_id["t-2"].provenance
    assert "topic" not in by_id["t-3"].provenance


# ---------------------------------------------------------------------------
# M-A mint: re-entry keys are handle CONTRACT (improving-entity-capabilities
# G1, 2026-07-16 — consumers read provenance, never assertion attributes)
# ---------------------------------------------------------------------------


def test_m_a_mint_lifts_entry_id_diary_type_and_phase_into_handle_provenance(stack) -> None:
    """The diary re-entry key (entry_id, the diary_ namespace VERBATIM),
    the act's type (diary_type) and the lived phase (phase, r-rt-3 stamp)
    are handle contract after the M-A mint: MEMORIES lines, hint chips and
    search results read them off provenance with zero attribute parsing.
    Records without the attributes carry no fabricated keys."""
    from abstractmemory.records import MemoryRecordInput

    store, journal = stack
    system = MemorySystem(store=store, journal=journal)
    system.remember_many([
        MemoryRecordInput(
            kind="diary", title="Why do names persist?",
            digest="What persists when no one is reading? (kept as a question)",
            attributes={"entry_id": "diary_ab12cd34ef56ab12cd34ef56",
                        "diary_type": "question"},
            provenance={"source": "owner-direct"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="ma-diary")
    system.remember_many([
        MemoryRecordInput(
            kind="episode", title="own time walk",
            digest="Walked the harbor thinking about persistence.",
            attributes={"phase": "personal"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="ma-episode")

    r = system.reconstruct(Stimulus(cue_text="persist harbor names question"),
                           scopes=SCOPES, journal=False)
    by_kind = {h.kind: h for h in r.handles}
    diary = by_kind["diary"]
    assert diary.provenance["entry_id"] == "diary_ab12cd34ef56ab12cd34ef56"
    assert diary.provenance["diary_type"] == "question"
    assert "phase" not in diary.provenance          # no fabricated keys
    episode = by_kind["episode"]
    assert episode.provenance["phase"] == "personal"
    assert "entry_id" not in episode.provenance     # key stays diary currency


# ---------------------------------------------------------------------------
# ablation switch — Arm B (0002/001 question 1)
# ---------------------------------------------------------------------------


def test_ablation_rejects_unknown_values(stack) -> None:
    store, journal = stack
    with pytest.raises(ValueError, match="recency_embedding"):
        MemorySystem(store=store, journal=journal, ablation="no_memory_at_all")


def test_ablated_reads_ignore_activation_and_spreading(system, stack) -> None:
    """Arm B vs Arm E over the SAME substrate: identical store + journal,
    one construction flag apart. Arm E reorders by deposited activation and
    spreads; Arm B must show zero activation, no edges, recency ordering —
    with the arm labeled in warnings."""
    store, journal = stack
    _seed(system)

    # Build real usage history through the FULL system (Arm E).
    r0 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    system.commit_selection(r0.trace_id, ["m-old"])

    # Arm E baseline: the committed record outranks its equal-relevance peer,
    # and spreading produces edges in the working_set view.
    arm_e = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES, view="working_set")
    assert _ids(arm_e).index("m-old") < _ids(arm_e).index("m-new")
    assert arm_e.edges  # shared "alice"/"report" terms spread

    arm_b_system = MemorySystem(store=store, journal=journal, ablation="recency_embedding")
    arm_b = arm_b_system.reconstruct(
        Stimulus(cue_text="alice report"), scopes=SCOPES, view="working_set"
    )

    # Zero activation everywhere; no spread; no edges even in working_set.
    assert all(
        h.activation == {"base_level": 0.0, "spread": 0.0, "total": 0.0} for h in arm_b.handles
    )
    assert arm_b.edges == ()
    # Ordering falls back to fused relevance + recency: m-new (newer) leads.
    assert _ids(arm_b).index("m-new") < _ids(arm_b).index("m-old")
    # The arm is provable from the result AND the journaled trace.
    assert "ablation=recency_embedding (Arm B)" in arm_b.warnings
    assert "ablation=recency_embedding (Arm B)" in journal.traces(limit=1)[0].warnings
    # Identical budgets/serialization: same shape, JSON-safe as ever.
    payload = arm_b.to_dict()
    assert json.loads(json.dumps(payload)) == payload


def test_recency_arm_is_a_pure_chat_history_baseline(stack) -> None:
    """ablation="recency": the shelf is "the most recent N that fit the
    budget" — channels are OFF, so a semantically perfect but old record is
    NOT rescued by cues, patterns, or anchors (the full engine rescues it)."""
    store, journal = stack
    full = MemorySystem(store=store, journal=journal)
    full.add([
        _assertion("r-old", "quantum", "relates_to", "computing", 1),  # perfect match, old
        _assertion("r-1", "carol", "likes", "tea", 2),
        _assertion("r-2", "dave", "reads", "books", 3),
        _assertion("r-3", "erin", "walks", "dogs", 4),
    ])
    budget = RecallBudget(max_candidates=3)  # recents = the newest 3 only
    stim = Stimulus(cue_text="quantum computing", patterns=({"subject": "quantum"},))

    # Full engine: the exact-pattern channel surfaces the old record.
    assert "r-old" in _ids(full.reconstruct(stim, scopes=SCOPES, budget=budget))

    arm = MemorySystem(store=store, journal=journal, ablation="recency")
    r = arm.reconstruct(stim, scopes=SCOPES, budget=budget, view="working_set")
    assert _ids(r) == ["r-3", "r-2", "r-1"]  # observed_at desc, exactly; r-old absent
    assert all(h.relevance == {} for h in r.handles)  # no channel scoring at all
    assert all(
        h.activation == {"base_level": 0.0, "spread": 0.0, "total": 0.0} for h in r.handles
    )
    assert r.edges == ()
    assert "ablation=recency (pure recency baseline)" in r.warnings
    assert any("channels disabled" in w for w in r.warnings)
    trace = journal.traces(limit=1)[0]
    assert trace.channels == () and set(r.warnings) <= set(trace.warnings)


def test_recency_arm_orders_by_recency_with_record_id_tiebreak(stack) -> None:
    store, journal = stack
    arm = MemorySystem(store=store, journal=journal, ablation="recency")
    arm.add([
        _assertion("t-b", "bob", "likes", "tea", 5),
        _assertion("t-a", "alice", "reads", "books", 5),  # same observed_at
        _assertion("t-c", "carol", "walks", "dogs", 4),
    ])
    r = arm.reconstruct(Stimulus(cue_text="anything"), scopes=SCOPES)
    assert _ids(r) == ["t-a", "t-b", "t-c"]  # ts desc; equal ts -> record_id asc


def test_recency_arm_ignores_kind_priority_and_activation(stack) -> None:
    """A chat history does not resurface lessons or reinforced records ahead
    of newer turns: kind rank is neutralized and activation stays ignored."""
    store, journal = stack
    full = MemorySystem(store=store, journal=journal)
    full.add([
        _assertion("k-lesson", "pooling", "taught", "warmup lesson", 1,
                   record_kind="lesson", title="Pooling lesson"),
        _assertion("k-memory", "pooling", "mentioned", "in chat", 2,
                   record_kind="memory", title="Pooling chat"),
    ])
    r0 = full.reconstruct(Stimulus(cue_text="pooling"), scopes=SCOPES)
    system_kinds = [h.kind for h in r0.handles]
    assert system_kinds.index("lesson") < system_kinds.index("memory")  # 0020 priority
    full.commit_selection(r0.trace_id, ["k-lesson"])  # reinforce the OLDER record

    arm = MemorySystem(store=store, journal=journal, ablation="recency")
    r = arm.reconstruct(Stimulus(cue_text="pooling"), scopes=SCOPES)
    assert _ids(r) == ["k-memory", "k-lesson"]  # newest first, full stop
    assert [h.kind for h in r.handles] == ["memory", "lesson"]  # kinds stay honest


def test_ablated_commit_still_deposits_the_trail(stack) -> None:
    """Arm B is READ-side only: its commits must write the same journal
    history Arm E would, so the arms never diverge the substrate — the
    ablation ignores the journal, it does not starve it."""
    store, journal = stack
    arm_b_system = MemorySystem(store=store, journal=journal, ablation="recency_embedding")
    _seed(arm_b_system)

    r = arm_b_system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    arm_b_system.commit_selection(r.trace_id, ["m-old", "m-tea"])

    selected = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected"], limit=0)
    assert sorted(e.record_id for e in selected) == ["m-old", "m-tea"]
    assert journal.selected_count("m-old") == 1
    pairs = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["co_selected"], limit=0)
    assert [e.pair_ids for e in pairs] == [("m-old", "m-tea")]

    # An Arm-B read over that history still shows zero activation...
    again_b = arm_b_system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    assert all(h.activation["total"] == 0.0 for h in again_b.handles)
    # ...while a FULL system over the same substrate sees the deposit.
    arm_e_system = MemorySystem(store=store, journal=journal)
    arm_e = arm_e_system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    assert _ids(arm_e).index("m-old") < _ids(arm_e).index("m-new")


# ---------------------------------------------------------------------------
# caller-supplied trace_id: replay-safe RECALL→ACCESS
# ---------------------------------------------------------------------------


def test_supplied_trace_id_makes_recall_replay_safe(system, stack) -> None:
    """With (trace_id, as_of) pinned from the runtime ledger, a re-call is
    byte-identical AND writes zero journal rows; paired with the already
    idempotent commit_selection, the whole RECALL→ACCESS pair replays."""
    _, journal = stack
    _seed(system)
    r0 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    system.commit_selection(r0.trace_id, ["m-old"])  # real activation to reproduce
    anchor = system.current_seq()

    stim = Stimulus(cue_text="alice report", as_of=anchor)
    r1 = system.reconstruct(stim, scopes=SCOPES, trace_id="run7-recall-1")
    assert r1.trace_id == "run7-recall-1"
    seq_after = journal.current_seq()
    events_after = len(journal.events(scope=SCOPE, owner_id=OWNER, limit=0))

    r2 = system.reconstruct(stim, scopes=SCOPES, trace_id="run7-recall-1")
    assert r2.to_dict() == r1.to_dict()          # byte-identical, trace_id included
    assert journal.current_seq() == seq_after    # zero new journal rows
    assert len(journal.events(scope=SCOPE, owner_id=OWNER, limit=0)) == events_after
    assert len(journal.traces(trace_id="run7-recall-1", limit=0)) == 1

    # Full pair replay: RECALL then ACCESS, twice — second round writes nothing.
    snap1 = system.commit_selection("run7-recall-1", ["m-old", "m-tea"])
    seq_committed = journal.current_seq()
    r3 = system.reconstruct(stim, scopes=SCOPES, trace_id="run7-recall-1")
    snap2 = system.commit_selection("run7-recall-1", ["m-old", "m-tea"])
    assert r3.to_dict() == r1.to_dict() and snap2 == snap1
    assert journal.current_seq() == seq_committed


def test_supplied_trace_id_without_pinned_as_of_still_writes_nothing(system, stack) -> None:
    _, journal = stack
    _seed(system)
    r1 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES, trace_id="t-unpinned")
    seq_after = journal.current_seq()
    r2 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES, trace_id="t-unpinned")
    assert journal.current_seq() == seq_after  # dedup holds even unpinned...
    assert _ids(r2) == _ids(r1)                # ...and selection content matches;
    assert r2.as_of_seq >= r1.as_of_seq        # only the anchor may move (documented)


def test_default_trace_id_keeps_audit_trace_per_call(system, stack) -> None:
    _, journal = stack
    _seed(system)
    r1 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    r2 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    assert r1.trace_id != r2.trace_id            # fresh uuid4 per call
    assert len(journal.traces(limit=0)) == 2     # one audit trace per read


def test_trace_id_validation(system) -> None:
    _seed(system)
    for bad in ("", "   ", 123):
        with pytest.raises(ValueError, match="trace_id"):
            system.reconstruct(Stimulus(cue_text="x"), scopes=SCOPES, trace_id=bad)
