"""Frozen runtime⇄memory seam dataclasses (seam v1).

Authoritative shape source: a2a/threads/0001-runtime-memory-orchestration/004-memory--to--runtime.md
System of record: docs/backlog/proposed/memory_system_v1/0027_runtime_seam_contract_v1.md

Contract: every type here is JSON-safe (str/int/float/bool/list/dict/None;
tuples serialize as lists). The runtime persists these in its ledger and
replays runs from them — shape changes go through the a2a channel FIRST.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple


def _jsonify(value: Any) -> Any:
    """Recursively convert to plain JSON types (tuples -> lists)."""
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class Stimulus:
    """An incoming cue that triggers reconstruction (the runtime owns WHEN)."""

    cue_text: str
    patterns: Tuple[Dict[str, Any], ...] = ()  # serialized TripleQuery filters (exact cues)
    anchor_record_ids: Tuple[str, ...] = ()
    participants: Tuple[str, ...] = ()
    embedding: Optional[Tuple[float, ...]] = None  # precomputed turn embedding (optional)
    as_of: Optional[int] = None  # journal seq; None = latest. See MemorySystem.seq_at().
    # Additive (a2a 0001/011 ask 4): the runtime's turn identity. Pure
    # provenance — it closes false-dedup/lost-deposit under at-least-once
    # replay and flows into the trace `need` + 'listed' event provenance.
    # NOT part of the query fingerprint: the same cue in a different turn is
    # still the same query (qmult semantics key on retrieval content only).
    turn_id: Optional[str] = None
    # Additive (steering wave, 2026-07-11 — pays the 0005 promise the room
    # believed already shipped): names the CHANNEL the cue came through
    # ("steer" for an operator mid-turn interjection, "diary_re_entry" for
    # a re-read of one's own entry, absent for an ordinary turn cue). Pure
    # provenance like turn_id: flows into trace `need` via to_dict so the
    # observer can label WHY a recall fired; NOT part of the query
    # fingerprint (same cue through a different channel = same query).
    # Free string — host vocabulary, never an enum.
    cue_source: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cue_text", str(self.cue_text or "").strip())
        object.__setattr__(self, "patterns", tuple(dict(p) for p in (self.patterns or ()) if isinstance(p, Mapping)))
        object.__setattr__(
            self, "anchor_record_ids", tuple(s.strip() for s in (self.anchor_record_ids or ()) if isinstance(s, str) and s.strip())
        )
        object.__setattr__(
            self, "participants", tuple(s.strip() for s in (self.participants or ()) if isinstance(s, str) and s.strip())
        )
        if self.embedding is not None:
            object.__setattr__(self, "embedding", tuple(float(x) for x in self.embedding))
        if self.as_of is not None:
            object.__setattr__(self, "as_of", int(self.as_of))
        if self.turn_id is not None:
            tid = str(self.turn_id).strip()
            object.__setattr__(self, "turn_id", tid if tid else None)
        if self.cue_source is not None:
            src = str(self.cue_source).strip()
            object.__setattr__(self, "cue_source", src if src else None)

    def to_dict(self) -> Dict[str, Any]:
        return _jsonify(asdict(self))


# THE IDENTITY FLOOR (maintainer round 7, single source of truth): summoned
# entities must run with self_fraction >= this floor — "stripping an entity
# from its identity could lead it to do things it wouldn't do otherwise."
# The GATEWAY enforces the channel policy (who must summon with the floor);
# the engine stays policy-free — RecallBudget validation deliberately keeps
# accepting 0.0..0.9 because non-entity callers legitimately run at 0 —
# but the constant lives HERE so both sides read one number (two copies
# drift: same-night precedent, the diary_type clamp vs validation split).
# fill_shelf's first-seat guarantee makes the floor MEAN presence: at least
# one identity record renders whenever a prompt-active core and any budget
# remain.
SELF_FRACTION_FLOOR = 0.05

# THE ENTITY CONTEXT FLOOR (maintainer ruling, round 8): entity sessions
# require at least this many context tokens — "never less". The gateway
# refuses smaller summons; entity_recall_budget refuses to even produce a
# profile for them (works-or-loud; no silent clamping). One constant, both
# sides import it — same clamp-drift lesson as SELF_FRACTION_FLOOR.
ENTITY_CONTEXT_FLOOR = 20_000


def entity_recall_budget(
    context_window: int, *, shelf_size: int = 12, token_fraction: float = 0.12,
) -> "RecallBudget":
    """The entity-session default recall-budget profile (single source of
    truth; the gateway injects it with the posture at summon). Every
    constant's basis, per the round-9 width-over-fear ruling ("width first,
    tune later" — no fear-derived ceilings):

    - Context floor 20k (ENTITY_CONTEXT_FLOOR): maintainer ruling round 8 —
      a MINIMUM, never a target.
    - token_budget = max(2400, round(token_fraction × context_window)) —
      NO upper cap (round 9: the earlier 4800 cap was partly bloat-fear
      and is removed; the fraction itself is the bound — 88% of context
      stays for history + generation at the default). The 2400 floor is a
      STARVATION guard (floors are not fear): the 60-token starvation
      repro is impossible at >= 2400 by construction.
    - token_fraction 0.12: a soft approximation, declared tunable
      (12% of the 20k floor = 2400, the seam default grounded). Bounded at
      0.5 — a recall payload beyond half the context starves generation;
      that is an ARITHMETIC bound, not a fear one.
    - shelf_size 12 default: the limited-attention model (seats ≈ what a
      mind holds at once — a cognitive basis, not fear) — DECLARED TUNABLE:
      callers/entities may widen it (entity-elected widening composes with
      the round-7 hyperfocus agency rules).
    - max_candidates = max(64, shelf_size × 8): the candidate pool scales
      with the shelf (width-first and cheap; default 96 at shelf 12).

    BUDGET MATH, honest (runtime's rich-digest arithmetic, 0007): at the
    20k floor (token_budget 2400), 12 shelf seats × ~200-token rich
    digests fill the budget EXACTLY — tokens bind first and seats may go
    unfilled. From ~3900+ token budgets (≈33k contexts at the default
    fraction), seats bind before tokens and the full shelf fits; wider
    contexts buy the headroom (the round-9 width note applies).

    POSTURE-INDEPENDENT by design: self_fraction stays 0.0 here — the
    summon POSTURE injects self_fraction (0.5) at the gate; the profile
    only sizes attention. Contexts below ENTITY_CONTEXT_FLOOR raise.
    """
    window = int(context_window)
    if window < ENTITY_CONTEXT_FLOOR:
        raise ValueError(
            f"entity sessions require a context window of at least "
            f"{ENTITY_CONTEXT_FLOOR:,} tokens — maintainer ruling, round 8 "
            f"(got {window:,}; see ENTITY_CONTEXT_FLOOR)"
        )
    seats = int(shelf_size)
    if seats < 1:
        raise ValueError(f"shelf_size must be >= 1 (got {shelf_size!r})")
    fraction = float(token_fraction)
    if not (0.0 < fraction <= 0.5):
        raise ValueError(
            f"token_fraction must be within (0, 0.5] (got {fraction!r}) — a recall "
            "payload beyond half the context starves generation (an arithmetic "
            "bound, not a fear one)"
        )
    token_budget = max(2400, round(fraction * window))
    return RecallBudget(token_budget=int(token_budget), shelf_size=seats,
                        max_candidates=max(64, seats * 8))


@dataclass(frozen=True)
class RecallBudget:
    """Bounds for one reconstruction. All bounds are hard; stop reasons name
    them. (reserved_slots was REMOVED — maintainer decision 2026-07-06: the
    per-channel quota mechanism is gone; membership is one ordering + greedy
    fill with channel-matched priority.)"""

    max_candidates: int = 64
    shelf_size: int = 12
    token_budget: int = 2400
    max_anchor_cues: int = 4
    max_hops: int = 2       # spreading phase
    max_edges: int = 100    # spreading phase
    min_activation: Optional[float] = None  # working_set MEMBERSHIP only; never gates channel matches
    deadline_s: Optional[float] = None
    # Additive (maintainer's union model): the stimulus-independent STM
    # component. stm_fraction caps STM's share of tokens/slots (0 disables —
    # the diagnostic pure-stimulus mode); stm_floor is the base-activation
    # eligibility bar (None → ReconstructConfig.stm_floor, default 1.0) —
    # separate from min_activation, which keeps its working-set-membership
    # meaning and ALSO gates STM members in that view.
    stm_fraction: float = 0.25
    stm_floor: Optional[float] = None
    # Additive (identity wave, a2a 0003 / seam v1.2 delta 1): the SELF
    # admission component — identity core from prompt-active bindings
    # (state, not trail). 0.0 = off (default; behavior byte-identical to
    # pre-wave). Hosts set it on entity summons.
    self_fraction: float = 0.0

    def __post_init__(self) -> None:
        fraction = float(self.self_fraction)
        if not (0.0 <= fraction <= 0.9):
            raise ValueError(
                f"RecallBudget.self_fraction must be within 0.0..0.9 (got {fraction!r}) — "
                "the self component may never consume the whole budget"
            )

    def to_dict(self) -> Dict[str, Any]:
        return _jsonify(asdict(self))


@dataclass(frozen=True)
class MemoryHandle:
    """One scored memory in a reconstruction result. digest is serialize-ready."""

    record_id: str
    kind: str
    title: str
    digest: str
    token_estimate: int
    relevance: Dict[str, float]   # {"exact": x, "keyword": y, "vector": z} (present channels only)
    activation: Dict[str, float]  # {"base_level": b, "spread": s, "total": t}
    cues: Tuple[str, ...]         # human-readable "why"; never empty for selected handles
    binding: str                  # e.g. "indexed+inactive"
    scope: str
    owner_id: str
    provenance: Dict[str, Any] = field(default_factory=dict)
    # Additive (a2a 0001/009 item 2, 0001/011 ask 6): payload fidelity levels
    # reachable via MemorySystem.payload(record_id, tier). v1 records carry
    # only their digest; richer tiers (raw/summary/compact) land with 0021.
    payload_tiers: Tuple[str, ...] = ("digest",)
    # Additive (union model + identity wave): how this handle entered the
    # working set — "stm" (trail-hot, stimulus-independent), "stimulus"
    # (channel/recency), "both" (trail-hot AND channel-matched), or "self"
    # (prompt-active binding: identity state, not trail — seam v1.2 delta 2;
    # "self" wins over "both"/"stm" because the binding admitted the record
    # regardless of any match). Reserved, not yet emitted: "historical"
    # (future situate() surface). Presence ≠ use: only stimulus/both
    # admissions deposit full usage events at commit; stm/self (and later
    # historical) deposit nothing.
    admission: str = "stimulus"

    def to_dict(self) -> Dict[str, Any]:
        return _jsonify(asdict(self))


@dataclass(frozen=True)
class ReconstructionResult:
    """Output of MemorySystem.reconstruct() — one call, two views."""

    trace_id: str
    view: str                                # "shelf" | "working_set"
    as_of_seq: int                           # journal high-water mark; persist for replay
    handles: Tuple[MemoryHandle, ...]
    edges: Tuple[Dict[str, Any], ...] = ()   # working_set view only:
    #   {source_id, predicate, target_id, strength_label, trail_activation}
    dropped: Tuple[Dict[str, Any], ...] = ()  # {record_id, score, reason}
    selector_route: str = "heuristic"        # heuristic | selector | selector_failed_preserved
    stop_reason: str = "enough"
    warnings: Tuple[str, ...] = ()           # #FALLBACK notes (degraded channels etc.)
    budget_spent: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = _jsonify(asdict(self))
        out["handles"] = [h.to_dict() for h in self.handles]
        return out


@dataclass(frozen=True)
class ActiveMemorySnapshot:
    """What actually entered a context (references + display metadata; never payload copies)."""

    snapshot_id: str
    # seq is journal-assigned (-1 = "not yet appended", matching every journal
    # record). kw_only keeps the frozen seam FIELD ORDER (and thus the JSON
    # shape) intact while allowing a default ahead of required fields.
    seq: int = field(default=-1, kw_only=True)
    trace_id: str
    used_record_ids: Tuple[str, ...]
    display: Tuple[Dict[str, Any], ...] = ()  # {record_id, title, digest, token_estimate}
    prompt_token_estimate: Optional[int] = None
    observed_at: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return _jsonify(asdict(self))
