"""Pins for the 2026-07-10 adversarial-review wave (vocabulary / parameters /
process abstractions).

What the wave changed, each pinned here:
- text_tokens.py is the ONE tokenization home (four drifting implementations
  unified); near-dup evidence gained NFKD accent folding and duplicate-title
  identity converged on title_key everywhere.
- ReconstructConfig + GradationConfig thread through the MemorySystem facade
  (they were exported as the tuning surface but unreachable).
- SleepTuning carries every sleep-lane policy number; the silent 1..6
  candidate-cap clamp became a loud band refusal.
- SpreadParams.trail_divisor replaced an inlined 25.0 twin.
- Sleep pass results name themselves (pass_name).
- identity_card = entity_card (neutral alias).
- Public vocabulary mappings are read-only.
"""

from __future__ import annotations

import pytest

from abstractmemory import (
    DIARY_TYPES,
    KIND_RANKS,
    GradationConfig,
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    ReconstructConfig,
    SleepTuning,
    Stimulus,
    consolidation_pass,
    entity_card,
    identity_card,
    maintenance_report,
    sleep_pass,
)
from abstractmemory.journal import DEFAULT_WEIGHTS
from abstractmemory.seam import RecallBudget
from abstractmemory.spreading import SpreadParams
from abstractmemory.text_tokens import (
    facet_tokens,
    jaccard,
    title_key,
    token_set,
    tokenize,
)

OWNER = "entity:test-subject"
SCOPE = "life"
LADDER = [(SCOPE, OWNER)]


def _system(**kwargs) -> MemorySystem:
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal(), **kwargs)


def _form(system: MemorySystem, records, key: str):
    return system.remember_many(records, scope=SCOPE, owner_id=OWNER, idempotency_key=key)


# ---------------------------------------------------------------------------
# text_tokens: one home, declared variants
# ---------------------------------------------------------------------------

def test_tokenize_accent_folds_and_keeps_recall_floor():
    assert tokenize("Café société the and for") == ["cafe", "societe"]


def test_token_set_accent_folds_with_evidence_floor():
    # Evidence floor is 3: short content tokens stay for dedup fingerprints.
    assert token_set("Le café GPU") == {"cafe", "gpu"}


def test_title_key_is_punctuation_case_and_accent_stable():
    assert title_key("Café, Bridges!") == title_key("cafe   bridges") == "cafe bridges"
    assert title_key("...") == ""


def test_jaccard_empty_is_zero_never_error():
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard({"a", "b"}, {"a"}) == pytest.approx(0.5)


def test_facet_tokens_keep_non_latin_scripts():
    # The declared fork variant: CJK facet runs survive whole (the regex
    # tokenizer would produce nothing for them).
    assert "橋の記憶" in facet_tokens(["橋の記憶, bridge"])
    assert "bridge" in facet_tokens(["橋の記憶, bridge"])


def test_accented_near_duplicates_are_now_visible_to_tending():
    """The correctness gap the unification fixed: accented vs plain spellings
    of the same digest are near-duplicates (keyword recall already matched
    them; the tending pass could not see them before NFKD folding)."""
    system = _system()
    _form(system, [
        MemoryRecordInput(kind="episode", title="Café note",
                          digest="Le café de la société était très fréquenté ce matin."),
        MemoryRecordInput(kind="episode", title="Cafe note",
                          digest="Le cafe de la societe etait tres frequente ce matin."),
    ], "accents")
    report = maintenance_report(system.store, system.journal, scopes=LADDER)
    assert report["counts"]["near_duplicate_pairs"] >= 1
    # And the duplicate-title identity converged (accent/case variants group).
    assert report["counts"]["duplicate_title_groups"] == 1


# ---------------------------------------------------------------------------
# Facade config threading (review F1/F2)
# ---------------------------------------------------------------------------

def test_reconstruct_config_reaches_the_pipeline():
    """A threaded kind_rank override must change shelf ordering: with rank
    inverted so 'memory' outranks 'lesson', the tie-broken order flips —
    proof the facade config reaches the pipeline instead of a fresh
    default being constructed inside the folds."""
    inverted = {k: -v for k, v in KIND_RANKS.items()}
    stamp = "2026-07-10T00:00:00+00:00"
    results = {}
    for label, config in (("default", ReconstructConfig()),
                          ("inverted", ReconstructConfig(kind_rank=inverted))):
        system = _system(reconstruct_config=config, clock=lambda: stamp)
        _form(system, [
            MemoryRecordInput(kind="lesson", title="Bridge lesson",
                              digest="bridge inspection lesson alpha"),
            MemoryRecordInput(kind="memory", title="Bridge memory",
                              digest="bridge inspection memory alpha"),
        ], "rank-probe")
        result = system.reconstruct(
            Stimulus(cue_text="bridge inspection"), scopes=LADDER,
            budget=RecallBudget(shelf_size=2), journal=False)
        results[label] = [h.title for h in result.handles]
    assert results["default"].index("Bridge lesson") < results["default"].index("Bridge memory")
    assert results["inverted"].index("Bridge memory") < results["inverted"].index("Bridge lesson")


def test_gradation_config_reaches_appraise_gate_and_fold():
    """privileged_actors + channel_clamp threaded through the facade: a host
    channel name unknown to the defaults gains amplitude authority, and the
    clamp change shows in gradation()."""
    system = _system(gradation_config=GradationConfig(
        privileged_actors=frozenset({"host-reflection"}), channel_clamp=5.0))
    # The default-privileged actor is NOT in this host's set -> refused.
    with pytest.raises(ValueError, match="amplitude authority"):
        system.appraise("tool:saw", sign=1, magnitude=8.0, reason="big",
                        scope=SCOPE, owner_id=OWNER, actor="entity-reflection")
    # The host's own channel IS privileged.
    system.appraise("tool:saw", sign=1, magnitude=8.0, reason="big",
                    scope=SCOPE, owner_id=OWNER, actor="host-reflection")
    standing = system.gradation(["tool:saw"], scope=SCOPE, owner_id=OWNER)["tool:saw"]
    assert standing["positive"] == pytest.approx(5.0)  # clamped by the threaded config


def test_entity_card_key_moments_follow_threaded_break_magnitude():
    """The card's key-moment band IS GradationConfig.break_magnitude (the
    review found a second unlinked 8.0): lowering it to 2 makes a magnitude-3
    appraisal a key moment."""
    system = _system()
    system.appraise("idea:bridges", sign=1, magnitude=3.0, reason="steady interest",
                    scope=SCOPE, owner_id=OWNER, actor="runtime")
    default_card = system.entity_card(scope_pairs=LADDER, owner_id=OWNER)
    assert not [m for m in default_card["key_moments"]["moments"] if m.get("type") == "valence"]
    lowered = entity_card(system.store, system.journal, scope_pairs=LADDER,
                          owner_id=OWNER, gradation_config=GradationConfig(break_magnitude=2.0))
    assert [m for m in lowered["key_moments"]["moments"] if m.get("type") == "valence"]


def test_identity_card_is_the_same_function():
    assert identity_card is entity_card
    assert MemorySystem.identity_card is MemorySystem.entity_card  # facade mirror


# ---------------------------------------------------------------------------
# SleepTuning (loud band, threaded knobs, self-naming results)
# ---------------------------------------------------------------------------

def test_out_of_band_candidate_cap_refuses_loudly():
    """The old code silently clamped max_candidates into 1..6 — including
    inverting 0 into 1 (a works-or-loud violation). Out-of-band now refuses."""
    system = _system()
    for bad in (0, 7):
        with pytest.raises(ValueError, match="candidate_cap_band"):
            consolidation_pass(system, scopes=LADDER, owner_id=OWNER, max_candidates=bad)
    # Widening the band explicitly is the sanctioned path.
    tuning = SleepTuning(candidate_cap_band=(1, 12))
    out = consolidation_pass(system, scopes=LADDER, owner_id=OWNER,
                             max_candidates=9, tuning=tuning)
    assert out["pass_name"] == "consolidation_pass"


def test_sleep_results_name_themselves():
    system = _system()
    _form(system, [MemoryRecordInput(kind="episode", title="One night",
                                     digest="a single quiet episode")], "night")
    result = sleep_pass(system, scopes=LADDER, owner_id=OWNER, report_only=True)
    assert result["pass_name"] == "sleep_pass"
    assert result["phases"] == ("resolution", "maintenance", "world_models", "mining", "identity", "dream")
    assert result["resolution"]["pass_name"] == "resolve_dreams_pass"
    assert result["maintenance"]["pass_name"] == "consolidation_pass"
    assert result["maintenance"]["report"]["pass_name"] == "maintenance_report"
    assert result["world_models"]["pass_name"] == "world_model_pass"
    assert result["dream"]["pass_name"] == "dream_pass"


def test_sleep_tuning_bounds_report_lists():
    """list_bound threads into the report sections (was a baked module
    constant duplicated across two modules)."""
    system = _system()
    records = [MemoryRecordInput(kind="episode", title=f"Episode {i}", digest=f"digest {i}")
               for i in range(5)]
    _form(system, records, "gaps")
    tight = maintenance_report(system.store, system.journal, scopes=LADDER,
                               tuning=SleepTuning(list_bound=1, metadata_gaps_factor=2))
    assert len(tight["metadata_gaps"]) <= 2
    assert tight["counts"]["records"] == 5  # counts stay honest, only lists bound


# ---------------------------------------------------------------------------
# Twins killed
# ---------------------------------------------------------------------------

def test_trail_divisor_is_a_spread_param():
    assert SpreadParams().trail_divisor == pytest.approx(25.0)
    assert SpreadParams(trail_divisor=50.0).trail_divisor == pytest.approx(50.0)


def test_public_vocabulary_mappings_are_read_only():
    for mapping in (KIND_RANKS, DEFAULT_WEIGHTS):
        with pytest.raises(TypeError):
            mapping["memory"] = 0  # type: ignore[index]
    assert isinstance(DIARY_TYPES, frozenset)


# ---------------------------------------------------------------------------
# Sign-off renames (laurent c398): executed while the windows were open
# ---------------------------------------------------------------------------

def test_reembed_home_is_a_migration_shim():
    import abstractmemory
    from abstractmemory.reembed import reembed_home, reembed_store
    assert reembed_home is reembed_store
    assert abstractmemory.reembed_home is abstractmemory.reembed_store


def test_cue_source_rides_trace_need_but_never_the_fingerprint():
    """Steering wave: Stimulus.cue_source is pure provenance (like turn_id) —
    it flows into the journaled trace's need so the observer can label WHY a
    recall fired ("steer", "diary_re_entry"), but the query fingerprint keys
    on retrieval content only (same cue ± source = same query), and an
    absent field keeps traces byte-identical (additive seam rule)."""
    from abstractmemory.reconstruct import _query_fingerprint

    plain = Stimulus(cue_text="harbor cranes")
    steered = Stimulus(cue_text="harbor cranes", cue_source="steer")
    assert steered.cue_source == "steer"
    assert plain.cue_source is None
    assert _query_fingerprint(plain) == _query_fingerprint(steered)
    assert steered.to_dict()["cue_source"] == "steer"
    assert plain.to_dict()["cue_source"] is None  # field present, null when absent

    system = _system()
    _form(system, [MemoryRecordInput(kind="episode", title="Cranes",
                                     digest="harbor cranes at noon")], "cs")
    system.reconstruct(steered, scopes=LADDER, trace_id="t-steer-1")
    [trace] = system._journal.traces(trace_id="t-steer-1", limit=1)
    assert trace.need.get("cue_source") == "steer"


def test_diary_channel_owner_direct_and_legacy_canonicalization():
    """The engraved-class rename (entity-direct -> owner-direct), executed
    at zero engravings: the new spelling is canonical, and the OLD spelling
    is accepted but CANONICALIZED at the form-gate during the migration
    window — no 'entity-direct' can engrave from here on."""
    canonical = MemoryRecordInput(
        kind="diary", title="Direct entry", digest="written directly",
        provenance={"source": "owner-direct"})
    assert canonical.provenance["source"] == "owner-direct"
    legacy = MemoryRecordInput(
        kind="diary", title="Legacy spelling", digest="old channel name",
        provenance={"source": "entity-direct"})
    assert legacy.provenance["source"] == "owner-direct"  # canonicalized, never engraved
    with pytest.raises(ValueError, match="owner-direct"):
        MemoryRecordInput(kind="diary", title="No channel", digest="undeclared")
