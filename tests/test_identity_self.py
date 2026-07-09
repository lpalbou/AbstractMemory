"""Identity wave slice 1 (a2a 0003 + seam v1.2 deltas 1-5, 7).

Identity kinds (value/purpose/trait/diary/interest), the SELF admission
component (prompt-active bindings: state, not trail), presence ≠ use for
self members, until_seq journal filters, and the two load-bearing proofs:

- EVICTION CONTRAST: a max-weight pin's influence dies under busy commits
  (attention is a WINDOW over the activity axis — usage standing, not
  identity), while a prompt-active self member survives arbitrarily many
  commits because binding STATE is not subject to the window.
- SEAM COMPAT: self_fraction=0.0 keeps ReconstructionResult JSON
  byte-identical to the pre-wave golden.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

import pytest

from abstractmemory import (
    AttentionConfig,
    InMemoryJournal,
    InMemoryTripleStore,
    MemorySystem,
    RecallBudget,
    Stimulus,
    TripleAssertion,
)
from abstractmemory.records import KIND_RANKS, MEMORY_RECORD_KINDS, MemoryRecordInput

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]
GOLDEN = Path(__file__).parent / "golden" / "pre_identity_wave_result.json"


def _ts(i: int) -> str:
    return f"2026-07-05T{10 + i // 60:02d}:{i % 60:02d}:00.000000+00:00"


def _assertion(aid: str, s: str, p: str, o: str, t: int, **attrs: Any) -> TripleAssertion:
    return TripleAssertion(subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
                           observed_at=_ts(t), attributes=dict(attrs), assertion_id=aid)


def _record(kind: str, title: str, digest: str, **kw: Any) -> MemoryRecordInput:
    return MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)


def _blank(system, **kw):
    return system.reconstruct(Stimulus(cue_text=""), scopes=SCOPES, journal=False, **kw)


# ---------------------------------------------------------------------------
# Identity kinds: registration, ranks, validation
# ---------------------------------------------------------------------------


def test_identity_kinds_registered_with_ranks() -> None:
    assert {"value", "purpose", "trait", "diary", "interest"} <= MEMORY_RECORD_KINDS
    assert (KIND_RANKS["value"], KIND_RANKS["purpose"], KIND_RANKS["trait"]) == (-3, -2, -1)
    assert KIND_RANKS["diary"] == KIND_RANKS["episode"] == 3   # lived raw material peers
    assert KIND_RANKS["interest"] == KIND_RANKS["summary"] == 5


def test_value_kind_requires_explicit_value_class() -> None:
    with pytest.raises(ValueError, match="value_class"):
        _record("value", "Honesty", "Intellectual honesty above all.")
    with pytest.raises(ValueError, match="value_class"):
        _record("value", "Honesty", "d", attributes={"value_class": "sacred"})
    core = _record("value", "Honesty", "d", attributes={"value_class": "CORE"})
    assert core.attributes["value_class"] == "core"  # normalized
    revisable = _record("value", "Tidy code", "d", attributes={"value_class": "revisable"})
    assert revisable.attributes["value_class"] == "revisable"


def test_diary_kind_defaults_type_and_never_requires_edges() -> None:
    # Diary formation requires a declared write channel (D4 form-gate);
    # these are entity-direct writes semantically.
    direct = {"source": "entity-direct"}
    first = _record("diary", "Day one", "I began existing today.", provenance=direct)
    assert first.attributes["diary_type"] == "note" and first.edges == ()
    for dt in ("note", "idea", "commitment", "reflection"):
        assert _record("diary", "t", "d", attributes={"diary_type": dt},
                       provenance=direct).attributes["diary_type"] == dt
    with pytest.raises(ValueError, match="diary_type"):
        _record("diary", "t", "d", attributes={"diary_type": "confession"}, provenance=direct)
    # Summary edge rule unchanged by the wave.
    with pytest.raises(ValueError, match="summary records require"):
        _record("summary", "t", "d")


def test_identity_kinds_outrank_learned_kinds_only_among_matched_peers(system) -> None:
    system.remember_many(
        [_record("value", "Care", "quantum care principle", attributes={"value_class": "core"}),
         _record("lesson", "Batching", "quantum batching lesson")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-rank")
    system.add([_assertion("plain-match", "doc", "notes", "quantum notes text", 9, literal=True)])

    r = system.reconstruct(Stimulus(cue_text="quantum"), scopes=SCOPES, journal=False)
    kinds = [h.kind for h in r.handles]
    # All three are keyword-matched: identity kind leads, lesson next.
    assert kinds.index("value") < kinds.index("lesson") < kinds.index("memory")

    # But an UNMATCHED value never outranks a matched record (kind stays a
    # tie-break behind relevance — the fill contract).
    r2 = system.reconstruct(Stimulus(cue_text="batching"), scopes=SCOPES, journal=False)
    ids2 = [h.record_id for h in r2.handles]
    lesson_pos = next(i for i, h in enumerate(r2.handles) if h.kind == "lesson")
    value_pos = next((i for i, h in enumerate(r2.handles) if h.kind == "value"), None)
    assert value_pos is None or lesson_pos < value_pos


# ---------------------------------------------------------------------------
# SELF admission component
# ---------------------------------------------------------------------------


def _seed_identity(system) -> List[str]:
    """Three identity records + two plain memories; identity bound
    prompt-active (the entity's always-warm core)."""
    gids = system.remember_many(
        [
            _record("trait", "Curious", "I ask before I assume.", keywords=("curiosity",)),
            _record("value", "Honesty", "Intellectual honesty above everything.",
                    attributes={"value_class": "core"}),
            _record("purpose", "Steward", "Help this home run itself.",
                    keywords=("stewardship",)),
        ],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-self",
    )
    system.add([
        _assertion("m-recent", "alice", "wrote", "storage report", 8),
        _assertion("m-old", "bob", "filed", "old form", 1),
    ])
    for gid in gids:
        system.bind(gid, scope=SCOPE, owner_id=OWNER,
                    search_state="indexed", prompt_state="active", source="operator")
    return gids  # [trait, value, purpose]


def test_self_component_admits_by_binding_state(system) -> None:
    _seed_identity(system)
    r = _blank(system, budget=RecallBudget(self_fraction=0.4))
    by_kind = {h.kind: h for h in r.handles}
    assert {"trait", "value", "purpose"} <= set(by_kind)
    for kind in ("trait", "value", "purpose"):
        assert by_kind[kind].admission == "self"
        assert by_kind[kind].binding == "indexed+active"  # the real folded state
    # Deterministic order: kind rank (value < purpose < trait), never activation.
    self_kinds = [h.kind for h in r.handles if h.admission == "self"]
    assert self_kinds == ["value", "purpose", "trait"]
    assert r.budget_spent["self_handles"] == 3
    assert r.budget_spent["self_tokens_used"] > 0
    assert r.budget_spent["tokens_used"] == sum(h.token_estimate for h in r.handles)


def test_self_fraction_zero_emits_no_self_component(system) -> None:
    _seed_identity(system)
    r = _blank(system)  # default self_fraction=0.0
    assert all(h.admission != "self" for h in r.handles)
    assert "self_handles" not in r.budget_spent  # byte-compat: keys absent at 0.0


def test_self_fraction_validation() -> None:
    with pytest.raises(ValueError, match="self_fraction"):
        RecallBudget(self_fraction=0.95)
    with pytest.raises(ValueError, match="self_fraction"):
        RecallBudget(self_fraction=-0.1)


def test_self_never_displaces_phase0_top_match(system) -> None:
    _seed_identity(system)
    system.add([_assertion("m-match", "proj", "spec", "zeta protocol details", 9, literal=True)])
    # Budget fits ~one handle: the channel match keeps its phase-0 seat.
    tight = system.reconstruct(
        Stimulus(cue_text="zeta protocol"), scopes=SCOPES, journal=False,
        budget=RecallBudget(shelf_size=1, token_budget=12, self_fraction=0.5),
    )
    assert [h.record_id for h in tight.handles] == ["m-match"]
    assert tight.handles[0].admission in ("stimulus", "both")


def test_self_label_wins_over_matched_and_trail_hot(system) -> None:
    """Precedence decision (documented in self_component.py): a prompt-active
    record labels "self" even when channel-matched or trail-hot — the
    binding admitted it; it was coming regardless."""
    [gid_trait, *_] = _seed_identity(system)
    system.commit_selection("t-warm-self", [gid_trait])  # also make it trail-hot
    r = system.reconstruct(Stimulus(cue_text="curiosity"), scopes=SCOPES, journal=False,
                           budget=RecallBudget(self_fraction=0.4))
    trait = next(h for h in r.handles if h.kind == "trait")
    assert trait.relevance  # channel-matched...
    assert trait.admission == "self"  # ...and still labeled self


def test_min_activation_never_gates_self_members(system) -> None:
    _seed_identity(system)  # identity records: zero activation (never committed)
    r = _blank(system, view="working_set",
               budget=RecallBudget(self_fraction=0.4, min_activation=5.0))
    self_kinds = {h.kind for h in r.handles if h.admission == "self"}
    assert {"trait", "value", "purpose"} <= self_kinds  # present despite 0 < 5.0


def test_stale_active_binding_cannot_resurrect_closed_record(system) -> None:
    [gid_trait, *_] = _seed_identity(system)
    system.close_record(gid_trait, reason="identity revision: trait retired")
    r = _blank(system, budget=RecallBudget(self_fraction=0.4))
    assert all(h.kind != "trait" for h in r.handles)  # closure fold wins over binding


def test_self_members_never_deposit_at_commit(system, stack) -> None:
    _, journal = stack
    _seed_identity(system)
    r = system.reconstruct(Stimulus(cue_text=""), scopes=SCOPES, trace_id="t-self-read",
                           budget=RecallBudget(self_fraction=0.4))
    used = [h.record_id for h in r.handles]  # commit-all-rendered pattern
    snap = system.commit_selection("t-self-read", used)
    deposited = [e.record_id for e in journal.events(scope=SCOPE, owner_id=OWNER,
                                                     kinds=["selected"], limit=0)]
    for h in r.handles:
        if h.admission == "self":
            assert h.record_id not in deposited  # presence is not use
        else:
            assert h.record_id in deposited
    assert set(snap.used_record_ids) == set(used)  # display truth keeps ALL


@pytest.mark.parametrize("arm", ["recency_embedding", "recency"])
def test_ablations_keep_the_self_component(stack, arm: str) -> None:
    """DECISION (documented in folds.py): ablations zero the TRAIL machinery
    (activation/spreading/channels) they are designed to test — self
    admission is binding STATE, orthogonal to recall mechanics. An ablated
    entity is still itself."""
    store, journal = stack
    full = MemorySystem(store=store, journal=journal)
    _seed_identity(full)
    ablated = MemorySystem(store=store, journal=journal, ablation=arm)
    r = ablated.reconstruct(Stimulus(cue_text=""), scopes=SCOPES, journal=False,
                            budget=RecallBudget(self_fraction=0.4))
    self_kinds = [h.kind for h in r.handles if h.admission == "self"]
    assert self_kinds == ["value", "purpose", "trait"]


def test_identity_floor_first_seat_survives_tiny_token_budget(system) -> None:
    """Maintainer round 7 (identity floor): at self_fraction=0.05 the
    fraction cap (int(0.05 × 60) = 3 tokens) is smaller than ANY identity
    digest — before the first-seat guarantee, the reserved slot rendered
    NOTHING and the entity summoned identity-absent. Now the FIRST self
    member seats against the full remaining budget."""
    _seed_identity(system)
    r = _blank(system, budget=RecallBudget(shelf_size=12, token_budget=60,
                                           self_fraction=0.05))
    self_handles = [h for h in r.handles if h.admission == "self"]
    assert self_handles, "the identity floor forbids an identity-absent summon"
    assert self_handles[0].kind == "value"  # kind-rank order: the core leads
    assert r.budget_spent["tokens_used"] <= 60
    assert r.budget_spent["tokens_used"] == sum(h.token_estimate for h in r.handles)


def test_identity_floor_fraction_cap_still_binds_beyond_first_seat(system) -> None:
    """The guarantee covers ONE seat: with two reserved slots
    (0.15 × 12 → 2) and a 9-token fraction cap, the second member exceeds
    the cap in the SELF fill and is dropped self_capped (honest) — the
    fraction stays authoritative beyond the guaranteed seat."""
    _seed_identity(system)
    r = _blank(system, budget=RecallBudget(shelf_size=12, token_budget=60,
                                           self_fraction=0.15))
    self_block = [h for h in r.handles if h.admission == "self"]
    assert self_block and self_block[0].kind == "value"
    capped = [d for d in r.dropped if d["reason"] == "self_capped"]
    assert capped, "the fraction cap must bind for the second reserved seat"
    assert r.budget_spent["tokens_used"] == sum(h.token_estimate for h in r.handles)


def test_identity_floor_composes_with_phase0_top_match(system) -> None:
    """Phase-0 interaction: the top channel match seats FIRST (full budget),
    THEN the first self member gets the full-remaining-budget guarantee —
    both present at a budget that fits exactly the two."""
    _seed_identity(system)
    system.add([_assertion("m-match", "proj", "spec", "zeta protocol details", 9, literal=True)])
    # Sizes: m-match canonical ~"proj spec zeta protocol details" (~8 tokens);
    # the smallest identity digest ~10 tokens. Budget 22 fits exactly the two;
    # the remaining self members drop under the fraction cap.
    r = system.reconstruct(
        Stimulus(cue_text="zeta protocol"), scopes=SCOPES, journal=False,
        budget=RecallBudget(shelf_size=12, token_budget=22, self_fraction=0.05,
                            stm_fraction=0.0),
    )
    by_admission = {}
    for h in r.handles:
        by_admission.setdefault(h.admission, []).append(h)
    assert [h.record_id for h in by_admission.get("stimulus", []) or by_admission.get("both", [])][:1] == ["m-match"]
    assert len(by_admission.get("self", [])) == 1  # the guaranteed first seat
    assert r.budget_spent["tokens_used"] <= 22


def test_entity_recall_budget_profile() -> None:
    """Rounds 8+9: the entity-session budget profile, single source of
    truth — width over fear. 12% of context above a 2400 starvation floor,
    NO upper cap (the removed 4800 cap was partly bloat-fear); shelf 12 is
    the limited-attention DEFAULT, a declared tunable; posture-independent
    (the gate injects self_fraction)."""
    import abstractmemory
    from abstractmemory import ENTITY_CONTEXT_FLOOR, entity_recall_budget

    assert ENTITY_CONTEXT_FLOOR == 20_000
    assert abstractmemory.ENTITY_CONTEXT_FLOOR == 20_000

    at_floor = entity_recall_budget(20_000)
    assert isinstance(at_floor, RecallBudget)  # passed __post_init__
    assert (at_floor.token_budget, at_floor.shelf_size) == (2400, 12)
    assert at_floor.max_candidates == 96       # max(64, 12 x 8): pool scales
    assert at_floor.self_fraction == 0.0       # posture-independent by design

    assert entity_recall_budget(25_000).token_budget == 3000
    assert entity_recall_budget(40_000).token_budget == 4800   # scaling, not a cap
    huge = entity_recall_budget(1_000_000)
    assert (huge.token_budget, huge.shelf_size) == (120_000, 12)  # width; shelf default holds

    # Declared tunables: entity-elected widening honored, pool scales.
    wide = entity_recall_budget(20_000, shelf_size=24)
    assert (wide.shelf_size, wide.max_candidates) == (24, 192)
    # The 2400 floor is a starvation guard: a small fraction cannot dip under.
    assert entity_recall_budget(20_000, token_fraction=0.05).token_budget == 2400

    with pytest.raises(ValueError, match=r"at least 20,000 tokens.*round 8"):
        entity_recall_budget(19_999)
    with pytest.raises(ValueError, match=r"arithmetic bound, not a fear one"):
        entity_recall_budget(20_000, token_fraction=0.6)
    with pytest.raises(ValueError, match="shelf_size"):
        entity_recall_budget(20_000, shelf_size=0)


def test_self_fraction_floor_constant_exported() -> None:
    import abstractmemory
    assert abstractmemory.SELF_FRACTION_FLOOR == 0.05
    from abstractmemory.seam import SELF_FRACTION_FLOOR
    assert SELF_FRACTION_FLOOR == 0.05
    # The engine stays policy-free: budgets below the floor remain valid
    # (non-entity callers legitimately run at 0; the gateway owns policy).
    assert RecallBudget(self_fraction=0.0).self_fraction == 0.0
    assert RecallBudget(self_fraction=0.01).self_fraction == 0.01


# ---------------------------------------------------------------------------
# until_seq journal filters (seam v1.2 delta 7)
# ---------------------------------------------------------------------------


def test_snapshots_and_traces_until_seq_filters(system, stack) -> None:
    _, journal = stack
    system.add([_assertion("m-a", "alice", "wrote", "report", 1)])
    system.reconstruct(Stimulus(cue_text="report"), scopes=SCOPES, trace_id="t-early")
    system.commit_selection("t-early", ["m-a"])
    anchor = journal.current_seq()
    system.reconstruct(Stimulus(cue_text="report"), scopes=SCOPES, trace_id="t-late")
    system.commit_selection("t-late", ["m-a"])

    assert {t.trace_id for t in journal.traces(limit=0)} == {"t-early", "t-late"}
    assert {t.trace_id for t in journal.traces(limit=0, until_seq=anchor)} == {"t-early"}
    assert {s.trace_id for s in journal.snapshots(limit=0)} == {"t-early", "t-late"}
    assert {s.trace_id for s in journal.snapshots(limit=0, until_seq=anchor)} == {"t-early"}
    assert journal.traces(limit=0, until_seq=0) == []


# ---------------------------------------------------------------------------
# THE load-bearing regression: eviction contrast + golden byte-compat
# ---------------------------------------------------------------------------


def test_eviction_contrast_pin_dies_self_survives(stack) -> None:
    """WHY the self component exists: attention is a WINDOW over the
    activity axis — even a MAX-WEIGHT pin's influence dies once enough busy
    commits push it past window_limit (usage standing, not identity). A
    prompt-active self member is binding STATE: it survives arbitrarily
    many commits, still surfaces with admission="self", and never deposits.
    (window_limit=120 compresses the axis; the mechanism, not the length,
    is under test — ~120+ busy events evict regardless of weight.)"""
    store, journal = stack
    system = MemorySystem(store=store, journal=journal,
                          attention_config=AttentionConfig(window_limit=120))
    [gid_value] = system.remember_many(
        [_record("value", "Honesty", "Intellectual honesty above everything.",
                 attributes={"value_class": "core"})],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-evict")
    system.bind(gid_value, scope=SCOPE, owner_id=OWNER,
                search_state="indexed", prompt_state="active", source="operator")
    system.add([_assertion("m-pinned", "alice", "wrote", "pinned report", 1),
                _assertion("m-busy-a", "bob", "filed", "busy form", 2),
                _assertion("m-busy-b", "carol", "sent", "busy mail", 3)])
    system.reinforce("m-pinned", reason="operator pin", weight=25,  # max weight
                     scope=SCOPE, owner_id=OWNER)
    assert system.activation(["m-pinned"], scope=SCOPE, owner_id=OWNER)["m-pinned"]["base_level"] > 0

    for turn in range(70):  # 70 commits x 2 selected events = 140 > window
        system.commit_selection(f"t-busy-{turn}", ["m-busy-a", "m-busy-b"])

    # (a) the pin's influence is GONE — window eviction, weight irrelevant.
    assert system.activation(["m-pinned"], scope=SCOPE, owner_id=OWNER)["m-pinned"]["base_level"] == 0.0
    # (b) the self member still surfaces, by state, and never deposited.
    r = system.reconstruct(Stimulus(cue_text=""), scopes=SCOPES, trace_id="t-evict-read",
                           budget=RecallBudget(self_fraction=0.4))
    value = next(h for h in r.handles if h.kind == "value")
    assert value.admission == "self"
    system.commit_selection("t-evict-read", [value.record_id])
    deposits = [e for e in journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected"], limit=0)
                if e.record_id and "value-" in e.record_id]
    assert deposits == []  # arbitrarily many renders: still zero usage events


def test_golden_byte_identity_with_self_fraction_zero() -> None:
    """Seam-compat proof: the exact pre-identity-wave scenario replays
    byte-identical with self_fraction=0.0. GOLDEN HISTORY: captured before
    the identity wave (proved the SELF component off = byte-identical);
    REGENERATED for the access-count wave (2026-07-06, additive
    "global_count" in handle provenance) and for the co-use trail wave
    (2026-07-07, maintainer-initiated: the warm-up commit now deposits a
    (g-hot, g-report) co_selected pair, shifting the seq axis by one).
    The golden pins the CURRENT serialization against accidental drift."""
    import warnings as warnings_module
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore", RuntimeWarning)  # volatile-journal note
        system = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal(),
                              clock=lambda: "2026-07-06T00:00:00.000000+00:00")
    system.add([
        _assertion("g-report", "alice", "wrote", "fusion energy report", 1),
        _assertion("g-tea", "carol", "likes", "green tea", 2),
        _assertion("g-plan", "bob", "drafted", "fusion reactor plan", 3, literal=True),
        _assertion("g-hot", "dave", "reads", "old books", 4),
    ])
    system.commit_selection("t-golden-warm", ["g-hot", "g-report"])
    r = system.reconstruct(
        Stimulus(cue_text="fusion energy report", as_of=system.current_seq()),
        scopes=SCOPES,
        budget=RecallBudget(shelf_size=3, token_budget=200, stm_fraction=0.25),
        view="working_set", journal=False, trace_id="t-golden-read",
    )
    assert json.dumps(r.to_dict(), sort_keys=True, indent=1) + "\n" == GOLDEN.read_text()
