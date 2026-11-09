"""The activation gate and its constants, in ONE module (ADR 0001 decision 7 and its Enforcement rule: "threshold
constants live in one module with their calibration quoted"). Used by the memory task queue's window selection
(backlog 0060) and by the ripple (backlog 0061).

WHERE THE FUNCTION COMES FROM. ADR 0001 decision 7 (accepted 2026-10-21) specifies the gate: "the accumulated
potential passes through a smooth gate (a logistic `1 / (1 + e^-k(x - θ))` or an equivalent monotone function)", and
the memory is reconsidered "when the gated potential is above the floor". Before this module no code in AbstractMemory
implemented it: the package's activation functions were the bounded spreading walk (`spreading.SpreadParams`:
damping 0.5, min_contribution 0.05, max_hops 2, fan_out_cap 12) and attention's per-step clamped hyperbolic decay
(`attention._contribution`, `weight / (1 + d / decay_window)` clamped to [0, max_activation]). The logistic gate was
prototyped and calibrated in AbstractNote (`recall/activation.py` `logistic`, `recall/propagation.py`
`PropagationTuning`, unmerged branch `retro/integration`, runs R6/R7 2026-10-20/21); ADR 0001 rules that the
prototype is absorbed here. The values below are that calibration.

OPERATOR DECISION 3 (2026-11-08): there is no fixed number of memories rebuilt per turn. The strength of the
incoming memory, change or surprise sets an activation through this gate; the host's Mind setting is the gate's
SENSITIVITY (a multiplier on the potential) plus a hard safety cap, never a count.

CALIBRATION QUOTED (AbstractNote PropagationTuning, R7 2026-10-21, notebook-1000 + the Mnemosyne replay, embedder
qwen3-embedding-0.6b, the embedder the live entity homes are pinned to):
- GATE_K 6, GATE_THETA 0.5, FLOOR 0.1: marked at potential >= 0.134 ("about an eighth of a note's statements resting
  on an idea that fully changed"); the loop gain DECAY x max reliance (1) x k/4 = 0.75 < 1 bounds every cycle.
- DECAY 0.5 / FLOOR 0.1: at these values a random entity reached p50 1 / p90 4 proximal ideas; without a floor the
  whole notebook was reached in two hops.
- SUMMARY_NOISE 0.10 (cosine distance of a paraphrase, noise-proxy p25 0.111) and SUMMARY_DIFFERENT 0.61 (median
  distance between different ideas, 0.609): a summary distance standardises between them.
Not yet calibrated on entity homes: the backfill dry run (root backlog 1137) measures the reader's own rewrite noise
on theforge-nvidia `qwen/qwen3.8-27b`; these constants move only from that measurement, in this module.

The numbers choose which memories are reconsidered and in which order; what a memory means is decided by the reader
(ADR 0001 decision 4). Nothing here reads text.
"""

from __future__ import annotations

import math
from typing import Dict, Mapping, Optional

__all__ = [
    "BACKFILL_FLOOR_STRENGTH",
    "CHANGE_MAGNITUDE",
    "DECAY",
    "DEFAULT_HARD_CAP",
    "DEFAULT_TASK_SECONDS",
    "FORMATION_STRENGTH",
    "GATE_FLOOR",
    "GATE_K",
    "GATE_THETA",
    "MAX_HOPS",
    "RELATION_WEIGHTS",
    "RIPPLE_BUDGET",
    "RIPPLE_WINDOW_CAP",
    "SIMILARITY_CEIL",
    "SIMILARITY_FLOOR",
    "SUMMARY_DIFFERENT",
    "SUMMARY_NOISE",
    "VECTOR_TOP_K",
    "activation",
    "distance_signal",
    "logistic",
    "loop_gain",
    "measured_change",
    "similarity_weight",
    "threshold",
]

# --- the gate (ADR 0001 decision 7; AbstractNote R7 calibration)
GATE_K: float = 6.0            # logistic slope k (loop gain DECAY * 1 * k / 4 = 0.75 < 1)
GATE_THETA: float = 0.5        # logistic centre θ
GATE_FLOOR: float = 0.1        # a gated activation at or above it is selected / reconsidered (potential >= 0.134)
DECAY: float = 0.5             # impact kept per hop (= spreading.SpreadParams.damping)

# --- the ripple's bounds (backlog 0061; the understanding-pass design §8)
MAX_HOPS: int = 2              # = spreading.SpreadParams.max_hops
RIPPLE_BUDGET: int = 20        # reconsiderations one ripple may enqueue; the rest is recorded as left_out
RIPPLE_WINDOW_CAP: int = 20    # ripple reconsiderations one window may select
VECTOR_TOP_K: int = 8          # nearest digests a ripple considers by similarity

# --- what a reader's change means as a magnitude (the reader's own enum; 0061)
CHANGE_MAGNITUDE: Mapping[str, float] = {"unchanged": 0.0, "refined": 0.25, "revised": 0.6, "overturned": 1.0}

# --- summary distance standardisation (AbstractNote H0: same embedder)
SUMMARY_NOISE: float = 0.10
SUMMARY_DIFFERENT: float = 0.61
SIMILARITY_FLOOR: float = 1.0 - SUMMARY_DIFFERENT   # cosine at or below: another idea (weight 0)
SIMILARITY_CEIL: float = 1.0 - SUMMARY_NOISE        # cosine at or above: a paraphrase (weight 1)

# How much a memory relies on the one it is connected to, by relation (reliance, ADR 0001 decision 2). Context
# relations (`written_amid`) and usage trails are not reliance and are absent: they never carry a ripple.
RELATION_WEIGHTS: Mapping[str, float] = {
    "summarizes": 1.0, "derived_from": 1.0, "refines": 1.0, "answers": 0.75, "supports": 0.75, "part_of": 0.75,
    "continues": 0.5, "from_session": 0.5, "reflected_in": 0.5, "mentions": 0.25,
}

# --- the strength of an incoming memory (backlog 0060)
FORMATION_STRENGTH: float = 1.0       # a memory just formed is wholly un-understood: a full change from nothing
BACKFILL_FLOOR_STRENGTH: float = 0.1  # an old, never-used mechanical memory (below the gate at sensitivity 1)

# --- the window (operator decision 3: a safety cap, never a count to fill)
DEFAULT_HARD_CAP: int = 64
# Seconds one task is expected to take when no completed task of its kind has reported its time yet (a host
# overrides with `cost_of`; measured times replace these as tasks complete). Order of magnitude for a 27B local
# model at 30-45 tokens/s decode with thinking off (DESIGN §9: 2-6k tokens in, ~250 out).
DEFAULT_TASK_SECONDS: Mapping[str, float] = {
    "title.author": 20.0, "digest.author": 60.0,  # a pending record's title (~20 tokens out) or summary
    "digest.rewrite": 60.0, "card.author": 60.0, "dream.narrate": 45.0,
    "ripple.reconsider": 60.0, "ripple.consolidate": 90.0,
}


def logistic(x: float, *, k: float = GATE_K, theta: float = GATE_THETA) -> float:
    """The gate `1 / (1 + e^-k(x - θ))` (ADR 0001 decision 7)."""
    z = -k * (float(x) - theta)
    if z > 60.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(z))


def threshold(*, k: float = GATE_K, theta: float = GATE_THETA, floor: float = GATE_FLOOR) -> float:
    """The potential at which the gate reaches the floor."""
    return theta - math.log((1.0 - floor) / floor) / k


def loop_gain(*, decay: float = DECAY, k: float = GATE_K) -> float:
    """What one hop can hand on per unit received: decay x max reliance (1) x max gate slope (k/4); must be < 1."""
    return decay * 1.0 * k / 4.0


def _finite(value: float, where: str) -> float:
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"{where} must be finite (got {value!r})")
    return v


def activation(strength: float, sensitivity: float = 1.0) -> float:
    """The gated activation of an incoming strength in [0, 1]: `logistic(sensitivity * strength)`. Sensitivity is
    the host's Mind setting (> 0): above 1 the gate opens for weaker signals, below 1 only strong ones pass."""
    s = _finite(sensitivity, "sensitivity")
    if s <= 0.0:
        raise ValueError(f"sensitivity must be positive (got {sensitivity!r})")
    x = min(1.0, max(0.0, _finite(strength, "strength")))
    return logistic(s * x)


def distance_signal(cosine_distance: float) -> float:
    """A summary distance standardised between the reader's paraphrase noise (0) and another idea (1)."""
    d = _finite(cosine_distance, "cosine_distance")
    return min(1.0, max(0.0, (d - SUMMARY_NOISE) / (SUMMARY_DIFFERENT - SUMMARY_NOISE)))


def similarity_weight(cosine: float) -> float:
    """A candidate's reliance through similarity alone: cosine standardised between another idea and a paraphrase."""
    c = _finite(cosine, "cosine")
    return min(1.0, max(0.0, (c - SIMILARITY_FLOOR) / (SIMILARITY_CEIL - SIMILARITY_FLOOR)))


def measured_change(change: str, cosine_distance: Optional[float] = None) -> float:
    """The magnitude of a reading's change: the reader's own enum (`CHANGE_MAGNITUDE`), scaled by how far the text
    actually moved when both vectors exist (`* (0.5 + 0.5 * distance_signal)`). The vectors can halve the reader's
    claim when the words barely moved; they never raise it above what the reader said."""
    name = str(change or "").strip()
    if name not in CHANGE_MAGNITUDE:
        raise ValueError(f"change must be one of {sorted(CHANGE_MAGNITUDE)} (got {change!r})")
    base = float(CHANGE_MAGNITUDE[name])
    if cosine_distance is None:
        return base
    return base * (0.5 + 0.5 * distance_signal(cosine_distance))


def gate_description() -> Dict[str, float]:
    """The gate's constants (JSON-safe), for results that must say how they decided."""
    return {"k": GATE_K, "theta": GATE_THETA, "floor": GATE_FLOOR, "threshold": round(threshold(), 6),
            "decay": DECAY, "loop_gain": loop_gain()}
