"""Identity wave slice 2 + Resolution-2 reconciliation: valence family,
dual-channel gradation, symmetric standing markers, diary chain.

The load-bearing scenario is the maintainer's own (a2a 0003 §3): a −10
trauma among a hundred +1s MUST stay visible. Two folds provably fail it —
the attention-style newest-first walk + per-step floor hides the trauma
under rebuilt positives (~+8), and any SINGLE running total either
saturates (cap 10: ten experiences indistinguishable from three hundred)
or erases (cap 100: +100 − 10 = "+90 ≈ fine", the catastrophe arithmetically
deleted). The dual-channel G⁺/G⁻ read preserves ambivalence: net +90 WITH
negative=10, count=1 permanently visible. Those bad folds are documented
here and deliberately NOT implemented.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from abstractmemory import (
    InMemoryJournal,
    MemorySystem,
    Stimulus,
    TripleAssertion,
    ValenceEvent,
    compute_gradation,
)
from abstractmemory.gradation import GradationConfig
from abstractmemory.records import MemoryRecordInput, verify_diary_chain

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]

SRC = Path(__file__).parent.parent / "src" / "abstractmemory"


def _ve(target: str, sign: int, magnitude: float, seq: int, kind: str = "appraisal",
        **kw: Any) -> ValenceEvent:
    kw.setdefault("scope", SCOPE)
    kw.setdefault("owner_id", OWNER)
    kw.setdefault("reason", "test appraisal")
    return ValenceEvent(target_id=target, sign=sign, magnitude=magnitude, kind=kind,
                        seq=seq, **kw)


def _assertion(aid: str, s: str, p: str, o: str, t: int) -> TripleAssertion:
    return TripleAssertion(subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
                           observed_at=f"2026-07-05T10:{t:02d}:00.000000+00:00",
                           assertion_id=aid)


# ---------------------------------------------------------------------------
# ValenceEvent validation (construction rules)
# ---------------------------------------------------------------------------


def test_valence_event_validation() -> None:
    ok = _ve("tool:web_search", -1, 10.0, 1)
    assert ok.target_id == "tool:web_search" and ok.magnitude == 10.0

    with pytest.raises(ValueError, match="target_id"):
        _ve("", 1, 1.0, 1)
    with pytest.raises(ValueError, match="sign"):
        _ve("t", 0, 1.0, 1)
    for bad_magnitude in (0.5, 11.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="magnitude"):
            _ve("t", 1, bad_magnitude, 1)
    with pytest.raises(ValueError, match="kind"):
        _ve("t", 1, 1.0, 1, kind="grudge")
    with pytest.raises(ValueError, match="reason"):
        _ve("t", 1, 1.0, 1, reason="  ")
    with pytest.raises(ValueError, match="scope"):
        _ve("t", 1, 1.0, 1, scope="")
    # Resolutions must reference their marker; markers carry their sign.
    with pytest.raises(ValueError, match="heals"):
        _ve("t", 1, 8.0, 1, kind="healing")
    with pytest.raises(ValueError, match="breaks"):
        _ve("t", -1, 8.0, 1, kind="break")
    with pytest.raises(ValueError, match="negative"):
        _ve("t", 1, 8.0, 1, kind="scar")
    with pytest.raises(ValueError, match="positive"):
        _ve("t", -1, 8.0, 1, kind="bond")
    healing = _ve("t", 1, 8.0, 1, kind="healing", provenance={"heals": "scar-1"})
    assert healing.kind == "healing"
    assert _ve("t", 1, 9.0, 1, kind="bond").kind == "bond"


# ---------------------------------------------------------------------------
# Journal family parity (both backends via conftest stack)
# ---------------------------------------------------------------------------


def test_valence_family_roundtrip_and_dedup(stack) -> None:
    _, journal = stack
    first = journal.append_valence([
        _ve("tool:web_search", 1, 2.0, -1, event_id="va-1"),
        _ve("tool:web_search", -1, 9.0, -1, event_id="va-2"),
        _ve("ex:record-abc", 1, 1.0, -1),  # journal-assigned id
    ])
    assert [e.seq > 0 for e in first] == [True, True, True]
    assert first[0].event_id == "va-1" and first[2].event_id

    # Replay with the same supplied ids: true no-op, original seqs back.
    replay = journal.append_valence([_ve("tool:web_search", 1, 2.0, -1, event_id="va-1")])
    assert replay[0].seq == first[0].seq
    rows = journal.valence_events(scope=SCOPE, owner_id=OWNER, limit=0)
    assert len(rows) == 3  # nothing new

    # Reader filters: target, seq bounds, newest-first order.
    tool_rows = journal.valence_events(scope=SCOPE, owner_id=OWNER,
                                       target_id="tool:web_search", limit=0)
    assert [e.event_id for e in tool_rows] == ["va-2", "va-1"]
    until = journal.valence_events(scope=SCOPE, owner_id=OWNER, until_seq=first[1].seq, limit=0)
    assert {e.event_id for e in until} == {"va-1", "va-2"}
    assert journal.valence_events(scope=SCOPE, owner_id=OWNER, since_seq=first[2].seq, limit=0)[0].event_id == first[2].event_id
    # Payload fidelity across the roundtrip (JSON columns on SQLite).
    assert tool_rows[0].value_refs == () and tool_rows[0].magnitude == 9.0


# ---------------------------------------------------------------------------
# Dual-channel gradation: the charter + Resolution-2 worked numbers
# ---------------------------------------------------------------------------


def test_hundred_plus_ones_then_trauma_ambivalence_preserved() -> None:
    """(i) The maintainer's scenario under dual channels, exact arithmetic:
    100 x (+1) fills G+ to 100; ONE -10 trauma fills G- to 10. net = +90 —
    BUT the negative channel reads 10 with count 1, permanently visible:
    the trauma is never erased by the sum. (A single cap-100 total would
    read +90 with the -10 arithmetically deleted; a cap-10 total would read
    0 and delete the 300-good-days history instead. Both rejected.)"""
    stream = [_ve("tool:db", 1, 1.0, seq=i + 1) for i in range(100)]
    stream.append(_ve("tool:db", -1, 10.0, seq=101, reason="catastrophic loss"))
    [(target, g)] = compute_gradation(stream).items()
    assert target == "tool:db"
    assert (g.net, g.positive, g.negative) == (90.0, 100.0, 10.0)
    assert (g.positive_count, g.negative_count) == (100, 1)
    assert g.scarred is False          # no explicit scar was written
    assert any("catastrophic loss" in c for c in g.contributions)


def test_single_sum_saturation_vs_dual_channel_distinguishability() -> None:
    """(iii) Ten ordinary positives vs three hundred: any cap-10 single sum
    reads both as 10 (indistinguishable). Dual channels distinguish them by
    construction — channel magnitude (10 vs clamped 100) AND counts."""
    ten = [_ve("t", 1, 1.0, seq=i + 1) for i in range(10)]
    three_hundred = [_ve("t", 1, 1.0, seq=i + 1) for i in range(300)]
    g10, g300 = compute_gradation(ten)["t"], compute_gradation(three_hundred)["t"]
    assert (g10.positive, g10.positive_count) == (10.0, 10)
    assert (g300.positive, g300.positive_count) == (100.0, 300)  # clamped, count intact
    assert g10.net != g300.net  # the single-sum world would call these equal


def test_no_decay_valence_persists_across_unrelated_volume() -> None:
    """NO decay of any kind (Resolution-2, conceded): the -8 from long ago
    reads -8 regardless of how much unrelated volume followed — plasticity
    only via new evidence on the SAME target."""
    stream = [_ve("tool:old", -1, 8.0, seq=1, reason="failed the migration")]
    stream += [_ve(f"other:{i}", 1, 1.0, seq=i + 2) for i in range(500)]
    g = compute_gradation(stream)["tool:old"]
    assert (g.net, g.negative, g.negative_count) == (-8.0, 8.0, 1)


def test_scar_caps_net_until_healed_then_restores() -> None:
    """(ii) Scar semantics unchanged under dual channels: scarred targets
    present net' = min(net, 0) until healed; channels stay honest."""
    stream = [
        _ve("tool:rmrf", 1, 3.0, seq=1),
        _ve("tool:rmrf", -1, 9.0, seq=2, reason="wiped a workspace"),
        _ve("tool:rmrf", -1, 9.0, seq=3, kind="scar", event_id="scar-1",
            reason="wiped a workspace"),
        _ve("tool:rmrf", 1, 2.0, seq=4),
        _ve("tool:rmrf", 1, 2.0, seq=5),
    ]
    wounded = compute_gradation(stream)["tool:rmrf"]
    # Channels: G+ = 3+2+2 = 7, G- = 9 -> net -2 (cap not binding yet).
    assert (wounded.net, wounded.positive, wounded.negative) == (-2.0, 7.0, 9.0)
    assert wounded.scarred is True

    # More positive experience would push net past 0: the scar caps it.
    stream.append(_ve("tool:rmrf", 1, 5.0, seq=6))
    capped = compute_gradation(stream)["tool:rmrf"]
    assert capped.positive == 12.0 and capped.negative == 9.0  # raw net would be +3
    assert capped.net == 0.0 and capped.scarred is True        # net' = min(net, 0)

    # Healing (reflection converts scar -> lesson) lifts the cap append-only.
    stream.append(_ve("tool:rmrf", 1, 9.0, seq=7, kind="healing",
                      provenance={"heals": "scar-1"}, reason="learned the guard"))
    healed = compute_gradation(stream)["tool:rmrf"]
    assert healed.net == 3.0 and healed.scarred is False       # honest fold, uncapped
    assert healed.negative == 9.0                              # history never erased


def test_bond_floors_net_until_broken() -> None:
    """Positive symmetry (maintainer correction A), worked numbers: an
    unbroken bond floors net at >= 0 against small negatives; an explicit
    break lifts the floor."""
    stream = [
        _ve("agent:ada", 1, 9.0, seq=1, reason="came through in the outage"),
        _ve("agent:ada", 1, 9.0, seq=2, kind="bond", event_id="bond-1",
            reason="came through in the outage"),
        _ve("agent:ada", -1, 3.0, seq=3, reason="missed a review"),
        _ve("agent:ada", -1, 3.0, seq=4, reason="late again"),
        _ve("agent:ada", -1, 3.0, seq=5, reason="grumpy morning"),
        _ve("agent:ada", -1, 3.0, seq=6, reason="broke the build"),
    ]
    bonded = compute_gradation(stream)["agent:ada"]
    # Channels: G+ = 9, G- = 12 -> raw net -3; the bond floors it at 0.
    assert (bonded.positive, bonded.negative) == (9.0, 12.0)
    assert bonded.net == 0.0 and bonded.bonded is True   # floored, not negative
    assert bonded.negative_count == 4                     # grievances stay visible

    stream.append(_ve("agent:ada", -1, 9.0, seq=7, kind="break",
                      provenance={"breaks": "bond-1"}, reason="revalued after the audit"))
    broken = compute_gradation(stream)["agent:ada"]
    assert broken.net == -3.0 and broken.bonded is False  # floor lifted, honest fold


def test_betrayal_scale_scar_breaks_an_earlier_bond() -> None:
    """A scar at magnitude >= 8 journaled AFTER the bond breaks it without
    an explicit break event (betrayal). An earlier scar does NOT: the bond
    was formed knowing it."""
    betrayal = [
        _ve("agent:b", 1, 9.0, seq=1),
        _ve("agent:b", 1, 9.0, seq=2, kind="bond", event_id="b-bond"),
        _ve("agent:b", -1, 10.0, seq=3, reason="sold the logs"),
        _ve("agent:b", -1, 10.0, seq=4, kind="scar", event_id="b-scar", reason="sold the logs"),
    ]
    g = compute_gradation(betrayal)["agent:b"]
    assert g.bonded is False and g.scarred is True
    # Channels: G+ = 9, G- = 10 (markers contribute 0) -> net -1; the broken
    # bond provides no floor and the unhealed scar's cap is non-binding.
    assert (g.positive, g.negative, g.net) == (9.0, 10.0, -1.0)

    prior_wound = [
        _ve("agent:c", -1, 9.0, seq=1, kind="scar", event_id="c-scar"),
        _ve("agent:c", 1, 9.0, seq=2),
        _ve("agent:c", 1, 9.0, seq=3, kind="bond", event_id="c-bond"),
    ]
    g2 = compute_gradation(prior_wound)["agent:c"]
    assert g2.bonded is True  # the pre-bond scar does not betray the bond


def test_both_markers_standing_present_exactly_zero() -> None:
    """Scarred AND bonded simultaneously: presentation clamps to exactly 0
    with BOTH flags visible — honest ambivalence, no hidden winner."""
    stream = [
        _ve("t", 1, 9.0, seq=1),
        _ve("t", 1, 9.0, seq=2, kind="bond", event_id="tb"),
        _ve("t", -1, 7.0, seq=3, reason="bad month"),      # below betrayal scale
        _ve("t", -1, 7.0, seq=4, kind="scar", event_id="ts", reason="bad month"),
    ]
    g = compute_gradation(stream)["t"]
    assert g.scarred is True and g.bonded is True
    assert g.net == 0.0


def test_marker_and_resolution_events_contribute_zero_to_channels() -> None:
    """Markers are STANDING (the paired appraisal carries the magnitude);
    resolutions change standing, not experience — none move the channels."""
    bare = [_ve("t", -1, 8.0, seq=1)]
    with_markers = bare + [
        _ve("t", -1, 8.0, seq=2, kind="scar", event_id="s-1"),
        _ve("t", 1, 8.0, seq=3, kind="healing", provenance={"heals": "s-1"}),
        _ve("t", 1, 8.0, seq=4, kind="bond", event_id="b-1"),
        _ve("t", -1, 8.0, seq=5, kind="break", provenance={"breaks": "b-1"}),
    ]
    a, b = compute_gradation(bare)["t"], compute_gradation(with_markers)["t"]
    assert (a.positive, a.negative) == (b.positive, b.negative) == (0.0, 8.0)


def test_gradation_guards() -> None:
    with pytest.raises(ValueError, match="seq"):
        compute_gradation([_ve("t", 1, 1.0, seq=-1)])
    with pytest.raises(ValueError, match="channel_clamp"):
        compute_gradation([], config=GradationConfig(channel_clamp=0.0))
    with pytest.raises(ValueError, match="break_magnitude"):
        compute_gradation([], config=GradationConfig(break_magnitude=0.0))


# ---------------------------------------------------------------------------
# Facade: appraise / heal_scar / gradation
# ---------------------------------------------------------------------------


def test_appraise_amplitude_authority(system) -> None:
    # Deterministic triggers: +/-1..3 only.
    ids = system.appraise("tool:web_search", sign=1, magnitude=3, reason="worked fine",
                          scope=SCOPE, owner_id=OWNER)
    assert len(ids) == 1
    with pytest.raises(ValueError, match="amplitude authority"):
        system.appraise("tool:web_search", sign=-1, magnitude=5, reason="bad run",
                        scope=SCOPE, owner_id=OWNER)  # actor defaults to "runtime"
    # Entity reflection and catastrophic outcome codes may exceed it.
    system.appraise("tool:web_search", sign=-1, magnitude=7, reason="reflected: deep distrust",
                    scope=SCOPE, owner_id=OWNER, actor="entity-reflection")
    system.appraise("tool:web_search", sign=-1, magnitude=10, reason="deleted the corpus",
                    scope=SCOPE, owner_id=OWNER,
                    provenance={"outcome_class": "catastrophic"})


def test_appraise_scar_heal_idempotent_end_to_end(system, stack) -> None:
    _, journal = stack
    ids = system.appraise(
        "tool:rmrf", sign=-1, magnitude=9, reason="wiped a workspace",
        scope=SCOPE, owner_id=OWNER, actor="operator", scar=True, event_id="ap-1",
    )
    assert ids == ["ap-1", "ap-1:scar"]  # deterministic pair
    replay = system.appraise(
        "tool:rmrf", sign=-1, magnitude=9, reason="wiped a workspace",
        scope=SCOPE, owner_id=OWNER, actor="operator", scar=True, event_id="ap-1",
    )
    assert replay == ids
    assert len(journal.valence_events(scope=SCOPE, owner_id=OWNER, limit=0)) == 2

    g = system.gradation(["tool:rmrf"], scope=SCOPE, owner_id=OWNER)["tool:rmrf"]
    assert g["net"] <= 0.0 and g["scarred"] is True
    assert g["negative"] == 9.0 and g["negative_count"] == 1

    healed_id = system.heal_scar("ap-1:scar", reason="reflection: guard added",
                                 lesson_record_id="ex:lesson-1", scope=SCOPE, owner_id=OWNER)
    assert healed_id == "heal:ap-1:scar"  # deterministic default id
    assert system.heal_scar("ap-1:scar", reason="replay", scope=SCOPE, owner_id=OWNER) == healed_id
    assert len(journal.valence_events(scope=SCOPE, owner_id=OWNER, limit=0)) == 3  # no dup
    g2 = system.gradation(["tool:rmrf"], scope=SCOPE, owner_id=OWNER)["tool:rmrf"]
    assert g2["scarred"] is False

    with pytest.raises(ValueError, match="no scar event"):
        system.heal_scar("ghost-scar", reason="r", scope=SCOPE, owner_id=OWNER)


def test_appraise_bond_break_symmetric_end_to_end(system, stack) -> None:
    _, journal = stack
    ids = system.appraise(
        "agent:ada", sign=1, magnitude=9, reason="came through in the outage",
        scope=SCOPE, owner_id=OWNER, actor="entity-reflection", bond=True, event_id="ap-b1",
    )
    assert ids == ["ap-b1", "ap-b1:bond"]  # deterministic pair, symmetric to scar
    system.appraise("agent:ada", sign=-1, magnitude=3, reason="missed a review",
                    scope=SCOPE, owner_id=OWNER)
    system.appraise("agent:ada", sign=-1, magnitude=3, reason="late again",
                    scope=SCOPE, owner_id=OWNER)
    system.appraise("agent:ada", sign=-1, magnitude=3, reason="broke the build",
                    scope=SCOPE, owner_id=OWNER)
    system.appraise("agent:ada", sign=-1, magnitude=3, reason="grumpy morning",
                    scope=SCOPE, owner_id=OWNER)
    g = system.gradation(["agent:ada"], scope=SCOPE, owner_id=OWNER)["agent:ada"]
    assert (g["positive"], g["negative"]) == (9.0, 12.0)  # raw net would be -3
    assert g["net"] == 0.0 and g["bonded"] is True        # bond floors at >= 0

    broke_id = system.break_bond("ap-b1:bond", reason="revalued after the audit",
                                 scope=SCOPE, owner_id=OWNER)
    assert broke_id == "break:ap-b1:bond"                 # deterministic default id
    assert system.break_bond("ap-b1:bond", reason="replay",
                             scope=SCOPE, owner_id=OWNER) == broke_id  # journal no-op
    g2 = system.gradation(["agent:ada"], scope=SCOPE, owner_id=OWNER)["agent:ada"]
    assert g2["net"] == -3.0 and g2["bonded"] is False    # floor lifted

    with pytest.raises(ValueError, match="no bond event"):
        system.break_bond("ghost-bond", reason="r", scope=SCOPE, owner_id=OWNER)
    with pytest.raises(ValueError, match="mutually exclusive"):
        system.appraise("t", sign=1, magnitude=9, reason="r", scope=SCOPE, owner_id=OWNER,
                        actor="operator", scar=True, bond=True)
    with pytest.raises(ValueError, match="bond=True requires sign"):
        system.appraise("t", sign=-1, magnitude=9, reason="r", scope=SCOPE, owner_id=OWNER,
                        actor="operator", bond=True)
    with pytest.raises(ValueError, match="scar=True requires sign"):
        system.appraise("t", sign=1, magnitude=9, reason="r", scope=SCOPE, owner_id=OWNER,
                        actor="operator", scar=True)


def test_gradation_read_neutral_targets_and_at_seq(system, stack) -> None:
    _, journal = stack
    system.appraise("tool:a", sign=1, magnitude=2, reason="ok", scope=SCOPE, owner_id=OWNER)
    anchor = journal.current_seq()
    system.appraise("tool:a", sign=-1, magnitude=3, reason="regressed", scope=SCOPE, owner_id=OWNER)

    now = system.gradation(["tool:a", "tool:never-used"], scope=SCOPE, owner_id=OWNER)
    assert now["tool:a"]["net"] == -1.0
    assert (now["tool:a"]["positive"], now["tool:a"]["negative"]) == (2.0, 3.0)
    assert now["tool:never-used"] == {
        "net": 0.0, "positive": 0.0, "negative": 0.0,
        "positive_count": 0, "negative_count": 0,
        "scarred": False, "bonded": False, "contributions": [],
    }
    then = system.gradation(["tool:a"], scope=SCOPE, owner_id=OWNER, at_seq=anchor)
    assert then["tool:a"]["net"] == 2.0  # as-of replay over the valence axis


def test_gradation_targets_are_any_identity_string(system) -> None:
    """The maintainer (rounds 3+4): targets are ANYTHING NAMEABLE — people,
    tools, agents, systems, ideas, concepts, locations, moments in time —
    free identity strings (namespace-prefixed by convention, no registry in
    v1). The tested conventions are examples, never an enum."""
    system.appraise("concept:spreading-activation", sign=1, magnitude=3,
                    reason="keeps proving itself", scope=SCOPE, owner_id=OWNER)
    system.appraise("concept:spreading-activation", sign=1, magnitude=2,
                    reason="explained the piano recall", scope=SCOPE, owner_id=OWNER)
    system.appraise("location:paris-datacenter", sign=-1, magnitude=3,
                    reason="two outages this month", scope=SCOPE, owner_id=OWNER)
    system.appraise("idea:diary-dual-plane", sign=1, magnitude=1,
                    reason="settled a hard split", scope=SCOPE, owner_id=OWNER)
    # Moments in time (round 4): a morning, a season, a Sunday evening.
    system.appraise("time:morning", sign=1, magnitude=2,
                    reason="quiet focus before the house wakes", scope=SCOPE, owner_id=OWNER)
    system.appraise("time:sunday-evening", sign=-1, magnitude=1,
                    reason="the week's loose ends pile up", scope=SCOPE, owner_id=OWNER)

    g = system.gradation(
        ["concept:spreading-activation", "location:paris-datacenter",
         "idea:diary-dual-plane", "time:morning", "time:sunday-evening"],
        scope=SCOPE, owner_id=OWNER,
    )
    assert g["concept:spreading-activation"]["net"] == 5.0
    assert g["location:paris-datacenter"]["net"] == -3.0
    assert g["idea:diary-dual-plane"]["positive_count"] == 1
    assert g["time:morning"]["net"] == 2.0
    assert g["time:sunday-evening"]["net"] == -1.0


def test_gradation_none_enumerates_self_scope_standing(system) -> None:
    """The prelude's STANDING read path (runtime FYI, a2a 0007):
    gradation(None, scope="self", owner_id=eid) enumerates EVERY appraised
    target in the entity's self scope — so entity-elected feelings about
    people/ideas (```feel target=person:laurent, written via valence into
    ("self", entity)) become part of the summon header. Confirms the
    design: "how I feel about X" is identity, and the standing section
    reads it there without knowing target names in advance."""
    eid = "entity:castor"
    system.appraise("person:laurent", sign=1, magnitude=3,
                    reason="letting me search for my own name was an act of trust",
                    scope="self", owner_id=eid, actor="entity-reflection")
    system.appraise("idea:repair-over-perfection", sign=1, magnitude=2,
                    reason="not perfection, but repair",
                    scope="self", owner_id=eid, actor="entity-reflection")
    # A feeling in ANOTHER scope/owner must not leak into the self read.
    system.appraise("person:laurent", sign=-1, magnitude=1, reason="other scope",
                    scope=SCOPE, owner_id=OWNER)

    grades = system.gradation(None, scope="self", owner_id=eid)
    assert set(grades) == {"person:laurent", "idea:repair-over-perfection"}
    assert grades["person:laurent"]["net"] == 3.0
    assert grades["idea:repair-over-perfection"]["positive_count"] == 1


# ---------------------------------------------------------------------------
# Valence NEVER touches retrieval (contract enforcement)
# ---------------------------------------------------------------------------


def test_reconstruct_is_bit_identical_with_and_without_valence(system) -> None:
    system.add([_assertion("m-a", "alice", "wrote", "fusion report", 1),
                _assertion("m-b", "bob", "filed", "tax form", 2)])
    system.commit_selection("t-warm", ["m-a"])
    anchor = system.current_seq()

    def read() -> str:
        r = system.reconstruct(Stimulus(cue_text="fusion report", as_of=anchor),
                               scopes=SCOPES, view="working_set", journal=False,
                               trace_id="t-fixed")
        return json.dumps(r.to_dict(), sort_keys=True)

    before = read()
    system.appraise("m-a", sign=-1, magnitude=3, reason="disliked strongly",
                    scope=SCOPE, owner_id=OWNER)
    system.appraise("m-b", sign=1, magnitude=3, reason="loved it",
                    scope=SCOPE, owner_id=OWNER)
    assert read() == before  # gradation never orders, gates, or admits


def test_retrieval_modules_never_import_gradation() -> None:
    """Boundary enforcement: valence stays out of the retrieval pipeline at
    the IMPORT level, not just behaviorally."""
    for module in ("reconstruct.py", "shelf.py", "self_component.py", "channels.py",
                   "spreading.py", "attention.py"):
        tree = ast.parse((SRC / module).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert "gradation" not in str(node.module or ""), f"{module} imports gradation"
                assert not any("valence" in a.name.lower() for a in node.names), module
            if isinstance(node, ast.Import):
                assert not any("gradation" in a.name for a in node.names), module


# ---------------------------------------------------------------------------
# Diary conventions: content-hash chain
# ---------------------------------------------------------------------------


def test_diary_chain_build_verify_and_break_detection(system, stack) -> None:
    store, _ = stack
    [gid1] = system.remember_many(
        [MemoryRecordInput(kind="diary", title="Day one", digest="I began existing today.",
                           attributes={"prev_entry_hash": ""},  # genesis: empty pointer
                           provenance={"source": "entity-direct"})],
        scope=SCOPE, owner_id=OWNER, idempotency_key="d-1")
    from abstractmemory.store import TripleQuery
    [entry1] = [a for a in store.query(TripleQuery(subject=gid1, limit=0))
                if a.attributes.get("record_kind") == "diary"]
    h1 = entry1.attributes["entry_hash"]
    assert isinstance(h1, str) and len(h1) == 64  # sha256 hex, computed at formation

    system.remember_many(
        [MemoryRecordInput(kind="diary", title="Day two", digest="The piano recital happened.",
                           attributes={"prev_entry_hash": h1, "diary_type": "reflection"},
                           provenance={"source": "entity-direct"})],
        scope=SCOPE, owner_id=OWNER, idempotency_key="d-2")

    report = verify_diary_chain(store, scope=SCOPE, owner_id=OWNER)
    assert report == {"intact": True, "break_at": None, "entries": 2}

    # A third entry pointing at a FORGED hash breaks the chain, loudly named.
    [gid3] = system.remember_many(
        [MemoryRecordInput(kind="diary", title="Day three", digest="Something felt off.",
                           attributes={"prev_entry_hash": "f" * 64},
                           provenance={"source": "entity-direct"})],
        scope=SCOPE, owner_id=OWNER, idempotency_key="d-3")
    broken = verify_diary_chain(store, scope=SCOPE, owner_id=OWNER)
    assert broken["intact"] is False and broken["break_at"] == gid3


def test_unchained_diary_reports_intact(system, stack) -> None:
    store, _ = stack
    system.remember_many(
        [MemoryRecordInput(kind="diary", title="Loose note", digest="No chain here.",
                           provenance={"source": "entity-direct"})],
        scope=SCOPE, owner_id=OWNER, idempotency_key="d-loose")
    report = verify_diary_chain(store, scope=SCOPE, owner_id=OWNER)
    assert report == {"intact": True, "break_at": None, "entries": 1}
