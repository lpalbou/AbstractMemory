"""Tests for the neurotransmitter attention engine (backlog 0018).

These tests are examples of the 0018 contracts — the engine must hold them
for arbitrary event streams, not just these fixtures. Expected numbers are
hand-derived from the spec math: contribution = sign·w·qmult/(1 + d/20).

NOTE: `abstractmemory.journal_memory` (InMemoryJournal, backlog 0017) did not
exist when this file was written (parallel agent). Per coordination notes we
use a minimal private _StubJournal implementing just append_events/events.
Once InMemoryJournal lands, the writer tests can switch to it — the writers
only rely on the MemoryJournal protocol surface.
"""

from __future__ import annotations

import dataclasses
import math
from typing import List, Optional, Sequence

import pytest

from abstractmemory.attention import (
    ActivationScore,
    AttentionConfig,
    attenuate,
    compute_activation,
    compute_trail_activation,
    mark_selected,
    ranking_boost,
    refocus,
    reinforce,
)
from abstractmemory.journal import MemoryEvent

SCOPE = "proj"
OWNER = "alice"


def _ev(
    kind: str,
    seq: int,
    record_id: Optional[str] = None,
    *,
    pair_ids: Optional[tuple] = None,
    weight: float = 0.0,
    ttl_activity: Optional[int] = None,
    query_fingerprint: Optional[str] = None,
    reason: Optional[str] = None,
) -> MemoryEvent:
    """Build a valid journal event with an explicit seq (as a journal would assign)."""
    if reason is None and kind in {"pinned", "silenced", "refocus"}:
        reason = f"test {kind}"
    return MemoryEvent(
        kind=kind,
        scope=SCOPE,
        owner_id=OWNER,
        record_id=record_id,
        pair_ids=pair_ids,
        weight=weight,
        ttl_activity=ttl_activity,
        query_fingerprint=query_fingerprint,
        reason=reason,
        seq=seq,
    )


class _StubJournal:
    """Minimal append-only journal (append_events/events only) for writer tests."""

    def __init__(self) -> None:
        self._events: List[MemoryEvent] = []
        self._seq = 0

    def append_events(self, events: Sequence[MemoryEvent]) -> List[MemoryEvent]:
        out: List[MemoryEvent] = []
        for event in events:
            self._seq += 1
            enriched = dataclasses.replace(
                event, seq=self._seq, event_id=f"evt-{self._seq}"
            )
            self._events.append(enriched)
            out.append(enriched)
        return out

    def events(self, *, scope: str, owner_id: str, **_: object) -> List[MemoryEvent]:
        return [e for e in self._events if e.scope == scope and e.owner_id == owner_id]


# ---------------------------------------------------------------------------
# Decay / rank-distance semantics
# ---------------------------------------------------------------------------


def test_monotone_decay_older_events_contribute_less():
    events = [
        _ev("selected", 1, "r1"),
        _ev("selected", 2, "r2"),
        _ev("selected", 3, "r3"),
    ]
    scores = compute_activation(events)

    # rank 0/1/2 -> 8/(1+d/20)
    assert scores["r3"].base_level == pytest.approx(8.0)
    assert scores["r2"].base_level == pytest.approx(8.0 * 20 / 21)
    assert scores["r1"].base_level == pytest.approx(8.0 * 20 / 22)
    assert scores["r3"].base_level > scores["r2"].base_level > scores["r1"].base_level
    assert scores["r3"].contributions == ("selected +8.0",)


def test_refocus_multiplier_applies_exactly_to_pre_refocus_events():
    events = [
        _ev("selected", 1, "old"),
        _ev("refocus", 2),
        _ev("selected", 3, "new"),
    ]
    scores = compute_activation(events)

    # "new" (seq 3 > refocus seq 2) is unaffected: rank 0 -> 8.0.
    assert scores["new"].base_level == pytest.approx(8.0)
    # "old" holds rank 2 (refocus occupies rank 1 but contributes nothing);
    # distance stretched once: 2*6=12 -> 8/(1+12/20) = 5.0 exactly.
    assert scores["old"].base_level == pytest.approx(5.0)
    # The refocus marker itself never scores a record.
    assert set(scores) == {"old", "new"}


def test_refocus_multiplier_applies_once_not_per_refocus_event():
    events = [
        _ev("selected", 1, "old"),
        _ev("refocus", 2),
        _ev("refocus", 3),
        _ev("selected", 4, "new"),
    ]
    scores = compute_activation(events)
    # "old" at rank 3; single stretch by the LATEST refocus: 3*6=18 ->
    # 8/(1+18/20). Compounding per refocus (3*6*6=108) would give ~1.25.
    assert scores["old"].base_level == pytest.approx(8.0 / 1.9)


def test_refocus_outside_window_has_no_effect():
    config = AttentionConfig(window_limit=2)
    events = [
        _ev("refocus", 1),
        _ev("selected", 2, "a"),
        _ev("selected", 3, "b"),
    ]
    scores = compute_activation(events, config=config)
    # Window (DESC, limit 2) = [b, a]; the refocus fell out -> no stretching.
    assert scores["b"].base_level == pytest.approx(8.0)
    assert scores["a"].base_level == pytest.approx(8.0 * 20 / 21)


# ---------------------------------------------------------------------------
# THE regression test: audit events are structurally inert (reading != using)
# ---------------------------------------------------------------------------


def test_audit_events_change_nothing():
    eligible = [
        _ev("selected", 10, "r1", query_fingerprint="qX"),
        _ev("co_selected", 20, pair_ids=("r1", "r2")),
        _ev("pinned", 30, "r2", weight=10.0),
        _ev("refocus", 40),
        _ev("silenced", 50, "r3"),
        _ev("selected", 60, "r3"),
    ]
    # A pile of audit reads truly INTERLEAVED on the seq axis (before,
    # between, and after every eligible event — not just appended at the end).
    pile = []
    for anchor in (5, 15, 25, 35, 45, 55, 65):
        for offset, kind in enumerate(("listed", "shown", "expanded", "cited")):
            pile.append(_ev(kind, anchor + offset, f"r{offset % 3 + 1}"))
    noisy = sorted(eligible + pile, key=lambda e: e.seq)

    clean_scores = compute_activation(eligible)
    noisy_scores = compute_activation(noisy)
    assert clean_scores == noisy_scores  # identical dicts, bit-exact

    assert compute_trail_activation(eligible) == compute_trail_activation(noisy)


def test_audit_flood_cannot_push_eligible_events_out_of_the_window():
    # If audit kinds ever entered the rank window, a flood of reads would
    # evict eligible events past window_limit — the fork's noise failure.
    config = AttentionConfig(window_limit=3)
    eligible = [
        _ev("selected", 1, "r1"),
        _ev("selected", 2, "r2"),
        _ev("selected", 3, "r3"),
    ]
    flood = [_ev("shown", 100 + i, "r1") for i in range(50)]
    assert compute_activation(eligible, config=config) == compute_activation(
        eligible + flood, config=config
    )


# ---------------------------------------------------------------------------
# Silencing, TTL, clamping
# ---------------------------------------------------------------------------


def test_silenced_reduces_but_never_below_zero():
    """Per-step clamp semantics (audit f1, fork parity): each event applies
    against the accumulated score of everything NEWER than it, clamped
    [0, max] at every step. A silence NEWER than all use floors at 0 (it
    starts biting only as new activity accumulates above it) but still
    demotes via rank displacement; a silence OLDER than the use demotes it
    visibly; the floor holds at every step, never just at the end."""
    events = [
        _ev("selected", 1, "r"),
        _ev("selected", 2, "r"),
        _ev("silenced", 3, "r"),
    ]
    silenced_score = compute_activation(events)["r"].base_level
    baseline = compute_activation(events[:2])["r"].base_level
    assert 0.0 < silenced_score < baseline
    # Walk newest→oldest: silenced(rank 0) -8 floors at 0; the selects then
    # add from ranks 1 and 2 (one slot deeper than in the baseline).
    assert silenced_score == pytest.approx(8.0 * 20 / 21 + 8.0 * 20 / 22)
    assert "silenced -8.0" in compute_activation(events)["r"].contributions

    # A silence OLDER than the use demotes it from the accumulated score
    # (the fork's S3 case): 8 + 8/1.05 accumulated, then -8/1.1 applied.
    older_silence = [_ev("silenced", 1, "r"), _ev("selected", 2, "r"), _ev("selected", 3, "r")]
    demoted = compute_activation(older_silence)["r"].base_level
    assert demoted == pytest.approx(8.0 + 8.0 * 20 / 21 - 8.0 * 20 / 22)

    # Floor at EVERY step: silences alone can never produce a negative score.
    only_silences = [_ev("silenced", i, "r") for i in range(1, 4)]
    assert compute_activation(only_silences)["r"].base_level == 0.0


def test_ttl_expiry_by_rank_distance():
    def stream(ttl: int) -> list:
        return [
            _ev("pinned", 1, "pin", ttl_activity=ttl),
            _ev("selected", 2, "a"),
            _ev("selected", 3, "b"),
            _ev("selected", 4, "c"),
        ]

    # The pin sits at rank 3. ttl=3 -> still alive (3 <= 3): 8/(1+3/20).
    alive = compute_activation(stream(3))
    assert alive["pin"].base_level == pytest.approx(8.0 * 20 / 23)
    # ttl=2 -> rank 3 > 2: contributes 0; the record stays visible at 0.
    expired = compute_activation(stream(2))
    assert expired["pin"].base_level == 0.0
    assert expired["pin"].contributions == ()

    # Silence expires the same way: old expired silence stops demoting.
    events = [
        _ev("selected", 1, "r"),
        _ev("silenced", 2, "r", ttl_activity=1),
        _ev("selected", 3, "x"),
        _ev("selected", 4, "y"),
    ]
    scores = compute_activation(events)
    assert scores["r"].base_level == pytest.approx(8.0 / 1.15)  # selection survives


def test_ttl_compares_raw_rank_index_not_refocus_stretched_distance():
    events = [
        _ev("pinned", 1, "pin", ttl_activity=5),
        _ev("refocus", 2),
        _ev("selected", 3, "x"),
    ]
    scores = compute_activation(events)
    # Raw rank 2 <= ttl 5 -> alive, even though stretched distance (12) > 5.
    # Decay still uses the stretched distance: 8/(1+12/20) = 5.0.
    assert scores["pin"].base_level == pytest.approx(5.0)


def test_activation_clamped_at_max_activation():
    events = [_ev("selected", i, "hot") for i in range(1, 11)]
    assert compute_activation(events)["hot"].base_level == 25.0

    tight = AttentionConfig(max_activation=10.0)
    assert compute_activation(events, config=tight)["hot"].base_level == 10.0


# ---------------------------------------------------------------------------
# qmult REMOVAL regression (maintainer decision, 2026-07-06)
# ---------------------------------------------------------------------------


def test_query_fingerprints_are_provenance_only_never_scored():
    """The query-fingerprint multiplier was REMOVED from scoring: events
    carrying fingerprints score exactly like unfingerprinted ones (the field
    survives as pure provenance), and compute_activation no longer accepts a
    query_fingerprint argument at all."""
    events = [
        _ev("selected", 1, "match", query_fingerprint="q1"),
        _ev("selected", 2, "other", query_fingerprint="q2"),
        _ev("selected", 3, "plain"),  # no fingerprint on the event
    ]
    scores = compute_activation(events)
    assert scores["plain"].base_level == pytest.approx(8.0)
    assert scores["other"].base_level == pytest.approx(8.0 * 20 / 21)
    assert scores["match"].base_level == pytest.approx(8.0 * 20 / 22)
    # The field is preserved on the event (provenance), not consumed by math.
    assert events[0].query_fingerprint == "q1"
    with pytest.raises(TypeError):
        compute_activation(events, query_fingerprint="q1")  # parameter deleted


# ---------------------------------------------------------------------------
# at_seq replay, trails, boost, determinism
# ---------------------------------------------------------------------------


def _mixed_stream() -> list:
    return [
        _ev("selected", 1, "r1", query_fingerprint="qA"),
        _ev("co_selected", 2, pair_ids=("r1", "r2")),
        _ev("pinned", 3, "r2", weight=12.0),
        _ev("shown", 4, "r1"),  # audit: inert
        _ev("refocus", 5),
        _ev("silenced", 6, "r1", ttl_activity=4),
        _ev("selected", 7, "r3"),
        _ev("co_selected", 8, pair_ids=("r3", "r2")),
        _ev("listed", 9, "r3"),  # audit: inert
        _ev("selected", 10, "r2", query_fingerprint="qB"),
    ]


def test_at_seq_replay_equals_recomputation_over_truncated_stream():
    events = _mixed_stream()
    for cut in (2, 5, 6, 8, 10, 999):
        truncated = [e for e in events if e.seq <= cut]
        assert compute_activation(events, at_seq=cut) == compute_activation(truncated)
        assert compute_trail_activation(events, at_seq=cut) == (
            compute_trail_activation(truncated)
        )


def test_trail_scores_over_co_selected_pairs():
    events = [
        _ev("co_selected", 1, pair_ids=("b", "a")),  # canonicalized to (a, b)
        _ev("co_selected", 2, pair_ids=("a", "c")),
        _ev("selected", 3, "x"),  # occupies rank 0 on the shared activity axis
    ]
    trails = compute_trail_activation(events)
    assert set(trails) == {("a", "b"), ("a", "c")}
    assert trails[("a", "c")] == pytest.approx(4.0 * 20 / 21)  # rank 1
    assert trails[("a", "b")] == pytest.approx(4.0 * 20 / 22)  # rank 2

    # Pair trails never leak into per-record activation (record_id is None).
    record_scores = compute_activation(events)
    assert set(record_scores) == {"x"}

    # Repeated togetherness accumulates on the same canonical key.
    repeated = events + [_ev("co_selected", 4, pair_ids=("b", "a"))]
    assert compute_trail_activation(repeated)[("a", "b")] > trails[("a", "b")]


def test_ranking_boost_scales_and_caps():
    assert ranking_boost(0.0) == 0.0
    assert ranking_boost(5.0) == pytest.approx(20.0)
    assert ranking_boost(25.0) == pytest.approx(100.0)
    assert ranking_boost(40.0) == 120.0  # capped vs the 1000-point direct-hit scale
    custom = AttentionConfig(boost_scale=2.0, max_boost=30.0)
    assert ranking_boost(20.0, config=custom) == 30.0


def test_determinism_identical_events_identical_output():
    events = _mixed_stream()
    first = compute_activation(events, include_prior=True,
                               selected_counts={"r1": 3, "cold": 7})
    second = compute_activation(events, include_prior=True,
                                selected_counts={"r1": 3, "cold": 7})
    assert first == second
    # Input order must not matter: seq is the only ordering axis.
    assert compute_activation(list(reversed(events))) == compute_activation(events)
    assert compute_trail_activation(events) == compute_trail_activation(events)


def test_include_prior_inspection_only_and_silence_wins():
    events = [_ev("selected", 1, "r1")]
    counts = {"r1": 10, "cold": 100, "zero": 0}

    plain = compute_activation(events, selected_counts=counts)  # include_prior=False
    assert set(plain) == {"r1"}
    assert plain["r1"].base_level == pytest.approx(8.0)

    with_prior = compute_activation(events, include_prior=True, selected_counts=counts)
    assert with_prior["r1"].base_level == pytest.approx(8.0 + math.log(11) * 0.05)
    # Long-used record whose events decayed out of the window stays rankable…
    assert with_prior["cold"].base_level == pytest.approx(math.log(101) * 0.05)
    assert with_prior["cold"].contributions == ()  # the prior is not an event
    # …but count 0 adds nothing and creates no entry.
    assert "zero" not in with_prior

    # Prior is capped and joins as ONE MORE clamped step (per-step clamp,
    # audit f1): a silenced-to-zero record shows at most the prior_cap (1.0)
    # — a bounded inspection-only nudge that cannot outrank real activation,
    # not the old bury-the-prior semantics (the deadband fix's flip side).
    buried = [_ev("silenced", i, "r1") for i in range(1, 4)]
    silenced = compute_activation(buried, include_prior=True,
                                  selected_counts={"r1": 10 ** 12})
    assert silenced["r1"].base_level == pytest.approx(1.0)  # prior_cap


def test_contribution_reasons_threshold_and_cap():
    events = [_ev("selected", i, "hot") for i in range(1, 11)]
    reasons = compute_activation(events)["hot"].contributions
    assert len(reasons) == 6  # capped at 6, most recent first
    assert reasons[0] == "selected +8.0"

    # Raising the threshold filters small contributions out of the "why".
    strict = AttentionConfig(reason_threshold=7.9)
    assert compute_activation(events, config=strict)["hot"].contributions == (
        "selected +8.0",
    )


# ---------------------------------------------------------------------------
# Journal-facing writers
# ---------------------------------------------------------------------------


def test_mark_selected_appends_selected_and_co_selected_events():
    journal = _StubJournal()
    written = mark_selected(
        journal,
        ["r1", "r2", "r1"],  # duplicate use in one commit deposits once
        pairs=[("b", "a"), ("a", "b")],  # same trail both ways: deposits once
        scope=SCOPE,
        owner_id=OWNER,
        trace_id="tr-1",
        context_ref="ctx-9",
    )
    assert [e.kind for e in written] == ["selected", "selected", "co_selected"]
    assert [e.record_id for e in written] == ["r1", "r2", None]
    assert written[2].pair_ids == ("a", "b")
    assert [e.weight for e in written] == [8.0, 8.0, 4.0]
    for event in written:
        assert event.trace_id == "tr-1"
        assert event.provenance == {"context_ref": "ctx-9"}
        assert event.actor == "runtime"
        assert (event.scope, event.owner_id) == (SCOPE, OWNER)
        assert event.seq > 0 and event.event_id  # enriched by the journal
    assert [e.seq for e in written] == [1, 2, 3]
    assert journal.events(scope=SCOPE, owner_id=OWNER) == written

    assert mark_selected(
        journal, [], pairs=[], scope=SCOPE, owner_id=OWNER,
        trace_id=None, context_ref=None,
    ) == []
    assert len(journal.events(scope=SCOPE, owner_id=OWNER)) == 3


def test_reinforce_attenuate_refocus_write_correct_events():
    journal = _StubJournal()

    pin = reinforce(journal, "r1", reason="user starred this",
                    ttl_activity=3, scope=SCOPE, owner_id=OWNER)
    assert (pin.kind, pin.record_id, pin.weight) == ("pinned", "r1", 8.0)
    assert pin.ttl_activity == 3
    assert pin.reason == "user starred this"
    assert pin.actor == "operator"

    # Deliberate-act strength is clamped 1..25 by the journal schema.
    assert reinforce(journal, "r1", reason="max", weight=99.0,
                     scope=SCOPE, owner_id=OWNER).weight == 25.0
    assert reinforce(journal, "r1", reason="min", weight=0.1,
                     scope=SCOPE, owner_id=OWNER).weight == 1.0

    hush = attenuate(journal, "r2", reason="off topic", scope=SCOPE, owner_id=OWNER)
    assert (hush.kind, hush.record_id, hush.weight) == ("silenced", "r2", 8.0)

    marker = refocus(journal, reason="topic shift", scope=SCOPE, owner_id=OWNER)
    assert (marker.kind, marker.record_id, marker.weight) == ("refocus", None, 0.0)
    assert marker.reason == "topic shift"

    assert [e.seq for e in journal.events(scope=SCOPE, owner_id=OWNER)] == [1, 2, 3, 4, 5]


def test_writers_reject_empty_reason_via_journal_validation():
    journal = _StubJournal()
    with pytest.raises(ValueError):
        reinforce(journal, "r1", reason="", scope=SCOPE, owner_id=OWNER)
    with pytest.raises(ValueError):
        attenuate(journal, "r1", reason="   ", scope=SCOPE, owner_id=OWNER)
    with pytest.raises(ValueError):
        refocus(journal, reason="", scope=SCOPE, owner_id=OWNER)
    # Validation fires at event construction: nothing was appended.
    assert journal.events(scope=SCOPE, owner_id=OWNER) == []


def test_activation_score_shape_matches_frozen_interface():
    score = ActivationScore(record_id="r", base_level=1.0, contributions=("selected +8.0",))
    assert dataclasses.is_dataclass(score) and isinstance(score.contributions, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        score.base_level = 2.0  # type: ignore[misc]


def test_window_limit_tunable_honored_end_to_end():
    """The 0007 saturation ruling: window_limit is a DECLARED TUNABLE and a
    host-supplied AttentionConfig must reach the fold. One substrate, two
    readers (the ablation pattern): identical journaled history, a resident-
    sized window vs the session default's shape at miniature scale. The old
    record's events fall OUTSIDE the small window (temporal-zero — the
    cliff) but INSIDE the large one (alive, per the decay curve). Same
    injected config drives reconstruct via _reconstruction_inputs; the
    GLOBAL count never windows (asserted — the two-count model's other
    half)."""
    import warnings as warnings_module
    from abstractmemory import InMemoryJournal, InMemoryTripleStore, MemorySystem, TripleAssertion

    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore", RuntimeWarning)  # volatile-journal note
        store, journal = InMemoryTripleStore(), InMemoryJournal()
        small = MemorySystem(store=store, journal=journal,
                             attention_config=AttentionConfig(window_limit=8))
        wide = MemorySystem(store=store, journal=journal,
                            attention_config=AttentionConfig(window_limit=8192))
    store.add([
        TripleAssertion(subject="m-old", predicate="wrote", object="yesterday's hot report",
                        scope=SCOPE, owner_id=OWNER, assertion_id="m-old"),
        TripleAssertion(subject="m-busy", predicate="filed", object="today's busy form",
                        scope=SCOPE, owner_id=OWNER, assertion_id="m-busy"),
    ])
    small.commit_selection("t-old", ["m-old"])          # 1 selected event, then...
    for turn in range(10):                              # ...10 busy events push it out
        small.commit_selection(f"t-busy-{turn}", ["m-busy"])

    assert small.activation(["m-old"], scope=SCOPE, owner_id=OWNER)["m-old"]["base_level"] == 0.0
    assert wide.activation(["m-old"], scope=SCOPE, owner_id=OWNER)["m-old"]["base_level"] > 0.0
    # The global half never windows: both readers report the same lifetime count.
    assert small.access_counts(record_ids=["m-old"])["records"]["m-old"] == 1
    assert wide.access_counts(record_ids=["m-old"])["records"]["m-old"] == 1


def test_burst_axis_survives_quadratic_pair_deposits_the_c5439_wash() -> None:
    """laurent's c5439 (operator-watched): at ruled shelves (22-36 seats)
    one commit deposits C(n,2) co_selected pairs, and the old per-event
    rank axis pushed the commit's OWN selections hundreds of ranks deep —
    top base_level 0.966 < stm_floor 1.0 on a live home with deposits
    perfectly healthy (zero STM, no green). The burst axis makes one
    committed turn ONE decay step regardless of shelf size."""
    import warnings as _w

    from abstractmemory import InMemoryJournal, InMemoryTripleStore, MemorySystem
    from abstractmemory.attention import compute_activation
    from abstractmemory.models import TripleAssertion

    with _w.catch_warnings():
        _w.simplefilter("ignore", RuntimeWarning)
        system = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())
    owner = "entity:wash"
    ids = [f"r-{i}" for i in range(22)]
    system.add([TripleAssertion(subject=f"ex:{rid}", predicate="dcterms:abstract",
                                object=f"Record {rid} lived a distinct moment {rid}.",
                                scope="life", owner_id=owner, assertion_id=rid,
                                attributes={"record_kind": "episode", "title": rid})
                for rid in ids])
    # One shelf-22 commit: 22 selected + C(22,2)=231 pairs in one burst.
    system.commit_selection("t-big", ids)
    act = system.activation(ids, scope="life", owner_id=owner)
    top = max(v["base_level"] for v in act.values())
    assert top >= 1.0, f"just-committed records must clear the STM floor (top={top})"

    # A second, different commit decays the first by ONE step, not 253.
    system.add([TripleAssertion(subject="ex:next", predicate="dcterms:abstract",
                                object="A new moment arrives the next turn.",
                                scope="life", owner_id=owner, assertion_id="next",
                                attributes={"record_kind": "episode", "title": "next"})])
    system.commit_selection("t-next", ["next"])
    act2 = system.activation(ids[:1], scope="life", owner_id=owner)
    events = system.journal.events(scope="life", owner_id=owner, limit=0)
    one_step = compute_activation(events)
    # distance 1 burst: contribution = w/(1 + 1/20) — far above the floor,
    # nothing like the pre-fix wash (0.966 after ONE commit).
    assert act2[ids[0]]["base_level"] >= 1.0
