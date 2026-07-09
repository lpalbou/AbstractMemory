"""Gradation: the derived reading of the valence axis (a2a 0003 §3 +
runtime Resolution-2 dual-channel reconciliation + maintainer correction A).

PURE functions only — no I/O, no journal handles. Gradation is how the
entity FEELS about a target (tool, record, person handle), derived from its
append-only ValenceEvent stream. It is ORTHOGONAL to attention by contract:
nothing here is imported by reconstruct/shelf, valence never touches
activation, and never gates candidates (enforcement test:
tests/test_valence_gradation.py asserts reconstruct output is bit-identical
with and without valence events).

DUAL CHANNELS (Resolution-2, reconciling the runtime's G⁺/G⁻ with the
chronological-walk finding — both survive because they solve different
failures): each target accumulates TWO channels chronologically
(oldest→newest), G⁺ from positive appraisals and G⁻ from negative ones,
each clamped 0..channel_clamp (100). The single running total provably
fails twice: cap-10 saturates (10 experiences indistinguishable from 300)
and cap-100 erases trauma (+100 then −10 reads "+90 ≈ fine" with the −10
arithmetically deleted). Dual channels preserve AMBIVALENCE: +100/−10 with
counts (300, 1) is "strongly positive, one severe incident" — the true
state; the trauma is never erased by the sum. The chronological order
still matters for the walk (contribution cues read in lived order) and for
marker timing (a bond only breaks on a LATER betrayal).

NO DECAY of any kind (CONCEDED to the runtime's Resolution-2, overturning
the earlier anti-spiral line): activation = retrieval strength (decays;
Bjork); valence = accumulated experience (persists). No calendar decay, no
window, no rank-distance falloff. Plasticity comes ONLY from new evidence
(appraisals move the channels), standing markers (scars/bonds), and their
append-only resolutions (healing/break). REVALUATION MARKER (design stub,
documented, NOT implemented): a future kind="revalued" — entity-reflection
only, `{target, factor, reason}` — will rescale a target's channels at fold
time for deliberate reappraisal ("agent N improved"); until it lands,
reappraisal = new appraisals + marker resolutions.

STANDING MARKERS (symmetric by maintainer correction A — signed PEAKS, not
"traumas"; a system that only builds durable structure from harm has a
built-in pessimistic trajectory):
- SCAR (−peak, sign=-1): an UNHEALED scar caps presentation at net ≤ 0 and
  sets scarred=True until a healing event names it in provenance["heals"].
- BOND (+peak, sign=+1): an UNBROKEN bond floors presentation at net ≥ 0
  and sets bonded=True. Bonds break via an explicit kind="break" event
  naming them in provenance["breaks"], OR by betrayal: any scar of
  magnitude ≥ break_magnitude (8) journaled AFTER the bond. Breaking is
  append-only and permanent — re-bonding is a NEW bond event later than
  the breaker.
- Both standing (scar and bond simultaneously unresolved): presentation
  clamps to exactly 0 with BOTH flags visible — honest ambivalence, not a
  hidden winner.
- Marker and resolution events contribute 0 to the channels: the paired
  appraisal already carries the magnitude; a marker is standing, not a
  second experience.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .journal import ValenceEvent

__all__ = [
    "GradationConfig",
    "GradationScore",
    "compute_gradation",
    "validate_amplitude_authority",
]

# Actors allowed to write amplitude > AMPLITUDE_TRIGGER_MAX appraisals
# (0003 §3 amplitude authority): deterministic triggers stay small; big
# swings need the entity's own reflection or the operator.
AMPLITUDE_TRIGGER_MAX = 3.0
_AMPLITUDE_ACTORS = frozenset({"entity-reflection", "operator"})

_MAX_CONTRIBUTION_REASONS = 5


@dataclass(frozen=True)
class GradationConfig:
    """Fold parameters (semantics live in the module doc). All retunable
    without migration — the journal stores raw events, never derived state."""

    channel_clamp: float = 100.0   # G+ / G- each accumulate within 0..this
    break_magnitude: float = 8.0   # a scar at/after this magnitude breaks earlier bonds


@dataclass(frozen=True)
class GradationScore:
    """Derived standing of one target on the valence axis (dual-channel).

    net = clamp(G+ − G−, ±channel_clamp), then presentation-clamped by
    standing markers: scarred → min(net, 0); bonded → max(net, 0); both →
    exactly 0 (ambivalence, both flags up). positive/negative + counts stay
    visible so the sum can never erase either side.
    """

    net: float
    positive: float
    negative: float
    positive_count: int
    negative_count: int
    scarred: bool
    bonded: bool
    contributions: Tuple[str, ...] = ()  # newest-first "why" strings (bounded)

    def to_dict(self) -> Dict[str, object]:
        return {
            "net": self.net, "positive": self.positive, "negative": self.negative,
            "positive_count": self.positive_count, "negative_count": self.negative_count,
            "scarred": self.scarred, "bonded": self.bonded,
            "contributions": list(self.contributions),
        }


NEUTRAL_GRADATION: Dict[str, object] = {
    "net": 0.0, "positive": 0.0, "negative": 0.0,
    "positive_count": 0, "negative_count": 0,
    "scarred": False, "bonded": False, "contributions": [],
}


def validate_amplitude_authority(
    magnitude: float, actor: str, provenance: Optional[Mapping[str, object]]
) -> None:
    """Amplitude authority (0003 §3): deterministic triggers write only
    ±1..3; a magnitude above that requires entity-reflection/operator
    actorship OR a catastrophic outcome code. Loud by design — a runaway
    trigger writing ±10s would fabricate trauma (or euphoria)."""
    if float(magnitude) <= AMPLITUDE_TRIGGER_MAX:
        return
    if str(actor or "").strip().lower() in _AMPLITUDE_ACTORS:
        return
    if str(dict(provenance or {}).get("outcome_class") or "").strip().lower() == "catastrophic":
        return
    raise ValueError(
        f"amplitude authority: magnitude {float(magnitude):g} > {AMPLITUDE_TRIGGER_MAX:g} requires "
        f"actor in {sorted(_AMPLITUDE_ACTORS)} or provenance['outcome_class']=='catastrophic' "
        f"(got actor={actor!r}) — deterministic triggers may only write ±1..3"
    )


def compute_gradation(
    events: Sequence[ValenceEvent],
    *,
    config: GradationConfig = GradationConfig(),
) -> Dict[str, GradationScore]:
    """Fold a valence stream into per-target dual-channel gradation.

    Pure function of (events, config); at_seq anchoring happens at the READ
    (the caller passes events <= at_seq), so identical inputs are identical
    outputs. Events must carry journal-assigned seqs (seq < 0 raises — same
    determinism guard as compute_activation)."""
    clamp = float(config.channel_clamp)
    if clamp <= 0.0:
        raise ValueError(f"GradationConfig.channel_clamp must be positive (got {clamp!r})")
    break_magnitude = float(config.break_magnitude)
    if break_magnitude <= 0.0:
        raise ValueError(f"GradationConfig.break_magnitude must be positive (got {break_magnitude!r})")

    by_target: Dict[str, List[ValenceEvent]] = {}
    healed: set = set()
    broken: set = set()
    for e in events:
        if e.seq < 0:
            raise ValueError(
                f"valence event {e.event_id or '<unassigned>'} has seq={e.seq}; gradation "
                "requires journal-assigned seqs (append first, score after)"
            )
        by_target.setdefault(e.target_id, []).append(e)
        if e.kind == "healing":
            ref = str(dict(e.provenance or {}).get("heals") or "").strip()
            if ref:
                healed.add(ref)
        elif e.kind == "break":
            ref = str(dict(e.provenance or {}).get("breaks") or "").strip()
            if ref:
                broken.add(ref)

    out: Dict[str, GradationScore] = {}
    for target, stream in by_target.items():
        stream.sort(key=lambda e: e.seq)  # CHRONOLOGICAL: lived order
        positive = negative = 0.0
        positive_count = negative_count = 0
        reasons: List[str] = []
        scarred = bonded = False
        betrayal_seqs = [e.seq for e in stream
                        if e.kind == "scar" and float(e.magnitude) >= break_magnitude]
        for e in stream:
            if e.kind == "scar":
                if e.event_id not in healed:
                    scarred = True
                continue
            if e.kind == "bond":
                explicitly_broken = e.event_id in broken
                betrayed = any(seq > e.seq for seq in betrayal_seqs)
                if not explicitly_broken and not betrayed:
                    bonded = True
                continue
            if e.kind in ("healing", "break"):
                continue  # resolutions are standing changes, not experiences
            magnitude = float(e.magnitude)
            if e.sign > 0:
                positive = min(positive + magnitude, clamp)
                positive_count += 1
            else:
                negative = min(negative + magnitude, clamp)
                negative_count += 1
            reasons.append(f"{'+' if e.sign > 0 else '-'}{magnitude:g} {e.reason}")

        net = min(max(positive - negative, -clamp), clamp)
        if scarred:
            net = min(net, 0.0)   # an unhealed wound never presents positive
        if bonded:
            net = max(net, 0.0)   # an unbroken bond never presents negative
        out[target] = GradationScore(
            net=net, positive=positive, negative=negative,
            positive_count=positive_count, negative_count=negative_count,
            scarred=scarred, bonded=bonded,
            contributions=tuple(reversed(reasons[-_MAX_CONTRIBUTION_REASONS:])),  # newest first
        )
    return out
