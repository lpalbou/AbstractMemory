"""Memory journal: append-only sidecar records + the MemoryJournal protocol.

Design source: docs/backlog/proposed/memory_system_v1/0017 (journal + bindings)
and 0018 (attention events). Event schema negotiated with the runtime agent in
a2a thread 0001 (message 002 §3) — field names are part of the seam; do not
rename without going through the channel.

Journal records are deliberately NOT triples: they have the opposite lifecycle
of assertions (no valid-time, never superseded, write-heavy, read by "recent N
per scope") and must never pollute FTS/vector indexes or SPO queries.

Attention semantics (hard contracts, see 0018):
- ONLY kinds in ATTENTION_KINDS feed activation. Audit kinds are structurally
  inert: recorded for explainability, never scored. Reading is not using.
- `seq` is assigned by the journal, monotonic per journal instance; it is the
  `as_of` axis for deterministic replay.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Protocol, Sequence, Tuple


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


# Event kinds that FEED activation (0018 fixed contract).
ATTENTION_KINDS = frozenset({"selected", "co_selected", "pinned", "silenced"})
# refocus modifies decay but contributes no weight itself.
DECAY_MARKER_KINDS = frozenset({"refocus"})
# Audit-only kinds: recorded, structurally inert for scoring.
AUDIT_KINDS = frozenset({"listed", "shown", "expanded", "cited"})
ALL_EVENT_KINDS = ATTENTION_KINDS | DECAY_MARKER_KINDS | AUDIT_KINDS

# Default weights per kind (config can override pin strength only).
DEFAULT_WEIGHTS: Dict[str, float] = {
    "selected": 8.0,
    "co_selected": 4.0,
    "pinned": 8.0,
    "silenced": 8.0,  # applied with negative sign at scoring time
}


def _jsonify(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class MemoryEvent:
    """One append-only access/attention event (a2a 0001/002 §3 schema)."""

    kind: str
    scope: str
    owner_id: str
    record_id: Optional[str] = None          # None only for refocus
    pair_ids: Optional[Tuple[str, str]] = None  # co_selected trails (canonical sorted pair)
    weight: float = 0.0
    ttl_activity: Optional[int] = None       # pins/silences: expiry by rank distance
    matched: bool = False
    query_fingerprint: Optional[str] = None
    trace_id: Optional[str] = None
    observed_at: str = field(default_factory=utc_now_iso)
    actor: str = "system"                    # runtime | operator | system
    reason: Optional[str] = None             # REQUIRED for pinned/silenced/refocus
    provenance: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""                       # journal-assigned when empty
    seq: int = -1                            # journal-assigned

    def __post_init__(self) -> None:
        kind = str(self.kind or "").strip().lower()
        if kind not in ALL_EVENT_KINDS:
            raise ValueError(f"Unknown memory event kind: {kind!r} (known: {sorted(ALL_EVENT_KINDS)})")
        object.__setattr__(self, "kind", kind)

        if kind in {"pinned", "silenced", "refocus"} and not (isinstance(self.reason, str) and self.reason.strip()):
            raise ValueError(f"Memory event kind {kind!r} requires a non-empty reason")

        if kind == "refocus":
            if self.record_id is not None:
                raise ValueError("refocus events carry no record_id (scope-level marker)")
        elif kind == "co_selected":
            pair = self.pair_ids
            if not (isinstance(pair, tuple) and len(pair) == 2 and all(isinstance(p, str) and p.strip() for p in pair)):
                raise ValueError("co_selected events require pair_ids=(id_a, id_b)")
            a, b = sorted((pair[0].strip(), pair[1].strip()))
            if a == b:
                raise ValueError("co_selected pair must reference two distinct records")
            object.__setattr__(self, "pair_ids", (a, b))
            object.__setattr__(self, "record_id", None)
        else:
            if not (isinstance(self.record_id, str) and self.record_id.strip()):
                raise ValueError(f"Memory event kind {kind!r} requires record_id")
            object.__setattr__(self, "record_id", self.record_id.strip())

        if not (isinstance(self.scope, str) and self.scope.strip()):
            raise ValueError("Memory events require a scope")
        object.__setattr__(self, "scope", self.scope.strip().lower())
        object.__setattr__(self, "owner_id", str(self.owner_id or "").strip())

        w = float(self.weight)
        if not math.isfinite(w):
            # NaN/Inf would poison scoring sums AND break strict JSON ledgers
            # (json.dumps(allow_nan=False)) — reject at the boundary.
            raise ValueError(f"Memory event weight must be finite, got {self.weight!r}")
        if kind in {"pinned", "silenced"}:
            # Clamp deliberate-act strength (0018): 1..25.
            w = max(1.0, min(25.0, abs(w) if w else DEFAULT_WEIGHTS[kind]))
        elif kind in DEFAULT_WEIGHTS and w == 0.0:
            w = DEFAULT_WEIGHTS[kind]
        object.__setattr__(self, "weight", w)

        if self.ttl_activity is not None:
            ttl = int(self.ttl_activity)
            if ttl <= 0:
                # Coercing ttl<=0 to None silently INVERTED "expire asap"
                # into "never expires" (audit f8) — refuse instead.
                raise ValueError(
                    f"ttl_activity must be a positive activity distance, got {self.ttl_activity!r} "
                    "(omit it, or pass None, for a non-expiring act)"
                )
            object.__setattr__(self, "ttl_activity", ttl)

    @property
    def feeds_attention(self) -> bool:
        return self.kind in ATTENTION_KINDS

    def to_dict(self) -> Dict[str, Any]:
        return _jsonify(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEvent":
        if not isinstance(data, dict):
            raise TypeError("MemoryEvent.from_dict expects a dict")
        pair = data.get("pair_ids")
        return cls(
            kind=str(data.get("kind") or ""),
            scope=str(data.get("scope") or ""),
            owner_id=str(data.get("owner_id") or ""),
            record_id=data.get("record_id") if isinstance(data.get("record_id"), str) else None,
            pair_ids=tuple(pair) if isinstance(pair, (list, tuple)) and len(pair) == 2 else None,
            weight=float(data.get("weight") or 0.0),
            ttl_activity=int(data["ttl_activity"]) if data.get("ttl_activity") is not None else None,
            matched=bool(data.get("matched", False)),
            query_fingerprint=data.get("query_fingerprint") if isinstance(data.get("query_fingerprint"), str) else None,
            trace_id=data.get("trace_id") if isinstance(data.get("trace_id"), str) else None,
            observed_at=str(data.get("observed_at") or "") or utc_now_iso(),
            actor=str(data.get("actor") or "system"),
            reason=data.get("reason") if isinstance(data.get("reason"), str) else None,
            provenance=dict(data.get("provenance") or {}),
            event_id=str(data.get("event_id") or ""),
            seq=int(data.get("seq", -1)),
        )


@dataclass(frozen=True)
class ScopeBinding:
    """Append-only visibility event; latest seq wins per (record_id, scope, owner_id)."""

    record_id: str
    scope: str
    owner_id: str
    search_state: str = "indexed"    # indexed | hidden
    prompt_state: str = "inactive"   # active | inactive; hidden => inactive (enforced)
    lifecycle: str = "none"          # none | inactive_candidate | reviewed | promoted | rejected | superseded
    source: str = "operator"         # remember | election | operator | maintenance | revision
    reason: Optional[str] = None
    observed_at: str = field(default_factory=utc_now_iso)
    provenance: Dict[str, Any] = field(default_factory=dict)
    binding_id: str = ""             # journal-assigned when empty
    seq: int = -1                    # journal-assigned

    _SEARCH = frozenset({"indexed", "hidden"})
    _PROMPT = frozenset({"active", "inactive"})
    _LIFECYCLE = frozenset({"none", "inactive_candidate", "reviewed", "promoted", "rejected", "superseded"})
    _SOURCE = frozenset({"remember", "election", "operator", "maintenance", "revision"})

    def __post_init__(self) -> None:
        if not (isinstance(self.record_id, str) and self.record_id.strip()):
            raise ValueError("ScopeBinding requires record_id")
        object.__setattr__(self, "record_id", self.record_id.strip())
        object.__setattr__(self, "scope", str(self.scope or "").strip().lower())
        object.__setattr__(self, "owner_id", str(self.owner_id or "").strip())

        search = str(self.search_state or "").strip().lower()
        prompt = str(self.prompt_state or "").strip().lower()
        if search not in self._SEARCH:
            raise ValueError(f"search_state must be one of {sorted(self._SEARCH)}")
        if prompt not in self._PROMPT:
            raise ValueError(f"prompt_state must be one of {sorted(self._PROMPT)}")
        if search == "hidden" and prompt == "active":
            raise ValueError("hidden implies inactive (a hidden record cannot be prompt-active)")
        object.__setattr__(self, "search_state", search)
        object.__setattr__(self, "prompt_state", prompt)

        lifecycle = str(self.lifecycle or "none").strip().lower()
        if lifecycle not in self._LIFECYCLE:
            raise ValueError(f"lifecycle must be one of {sorted(self._LIFECYCLE)}")
        object.__setattr__(self, "lifecycle", lifecycle)

        source = str(self.source or "operator").strip().lower()
        if source not in self._SOURCE:
            raise ValueError(f"source must be one of {sorted(self._SOURCE)}")
        object.__setattr__(self, "source", source)

    def to_dict(self) -> Dict[str, Any]:
        return _jsonify(asdict(self))


@dataclass(frozen=True)
class ClosureRecord:
    """Append-only belief-lifecycle record (backlog 0010): retract or supersede."""

    assertion_id: str
    kind: str                        # retract | supersede
    reason: str
    replacement_ids: Tuple[str, ...] = ()
    observed_at: str = field(default_factory=utc_now_iso)
    actor: str = "system"
    provenance: Dict[str, Any] = field(default_factory=dict)
    closure_id: str = ""             # journal-assigned when empty
    seq: int = -1                    # journal-assigned

    def __post_init__(self) -> None:
        if not (isinstance(self.assertion_id, str) and self.assertion_id.strip()):
            raise ValueError("ClosureRecord requires assertion_id")
        object.__setattr__(self, "assertion_id", self.assertion_id.strip())
        kind = str(self.kind or "").strip().lower()
        if kind not in {"retract", "supersede"}:
            raise ValueError("ClosureRecord.kind must be 'retract' or 'supersede'")
        object.__setattr__(self, "kind", kind)
        if not (isinstance(self.reason, str) and self.reason.strip()):
            raise ValueError("ClosureRecord requires a non-empty reason")
        if kind == "supersede" and not self.replacement_ids:
            raise ValueError("supersede closures require replacement_ids")
        object.__setattr__(
            self, "replacement_ids", tuple(s.strip() for s in (self.replacement_ids or ()) if isinstance(s, str) and s.strip())
        )

    def to_dict(self) -> Dict[str, Any]:
        return _jsonify(asdict(self))


@dataclass(frozen=True)
class ReconstructionTrace:
    """Append-only record of one reconstruct()/probe() call (backlog 0020)."""

    trace_id: str
    trace_kind: str                              # reconstruct | probe
    query_fingerprint: str
    need: Dict[str, Any]
    searched_scopes: Tuple[Dict[str, Any], ...]  # explicit list; never a bare "global"
    escalation_reason: Optional[str] = None
    channels: Tuple[str, ...] = ()
    candidates: Tuple[Dict[str, Any], ...] = ()  # bounded: {record_id, scores}
    selected: Tuple[str, ...] = ()
    dropped: Tuple[Dict[str, Any], ...] = ()     # {record_id, score, reason}
    cues: Tuple[str, ...] = ()
    budgets: Dict[str, Any] = field(default_factory=dict)
    budget_spent: Dict[str, Any] = field(default_factory=dict)
    selector_route: str = "heuristic"
    stop_reason: str = "enough"
    warnings: Tuple[str, ...] = ()
    # Additive (union model, presence ≠ use): record_id -> admission label
    # ("stm" | "stimulus" | "both") for every PLACED handle. commit_selection
    # consults this to decide which used ids deposit full usage events.
    admissions: Dict[str, str] = field(default_factory=dict)
    observed_at: str = field(default_factory=utc_now_iso)
    seq: int = -1                                # journal-assigned

    def to_dict(self) -> Dict[str, Any]:
        return _jsonify(asdict(self))


VALENCE_KINDS = frozenset({"appraisal", "scar", "healing", "bond", "break"})


@dataclass(frozen=True)
class ValenceEvent:
    """Signed appraisal on the valence axis (identity wave, a2a 0003 §3).

    ORTHOGONAL to attention by contract: valence events never touch
    activation, never gate candidates, and reconstruct/shelf never read
    them — the derived surface is `gradation.compute_gradation` only.

    target_id may be a record id OR a free identity string (e.g.
    "tool:web_search") — appraisal targets are NOT required to be records.
    value_refs name the value records the appraisal is grounded in (may be
    empty for deterministic triggers).

    Standing markers are EXPLICIT and SYMMETRIC (maintainer correction A —
    signed PEAKS, not "traumas"): a magnitude>=8 appraisal does NOT
    auto-create a marker; the caller writes kind="scar" (sign=-1, caps the
    target's presentation at <=0) or kind="bond" (sign=+1, floors it at
    >=0) alongside when the peak is standing. Resolutions are append-only
    and mirror each other: kind="healing" resolves a scar by naming its
    event_id in provenance["heals"]; kind="break" dissolves a bond via
    provenance["breaks"] (a betrayal-scale scar, magnitude>=8 AFTER the
    bond, also breaks it — see gradation.py). Marker rows are never
    rewritten.
    """

    target_id: str
    sign: int                        # +1 | -1
    magnitude: float                 # 1..10; 10 IS the trauma-to-ordinary ratio
    kind: str = "appraisal"          # appraisal | scar | healing
    value_refs: Tuple[str, ...] = ()
    scope: str = ""
    owner_id: str = ""
    reason: Optional[str] = None     # REQUIRED (validated) — appraisals must be explainable
    actor: str = "runtime"
    trace_id: Optional[str] = None
    observed_at: str = field(default_factory=utc_now_iso)
    provenance: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""               # journal-assigned when empty
    seq: int = -1                    # journal-assigned

    def __post_init__(self) -> None:
        if not (isinstance(self.target_id, str) and self.target_id.strip()):
            raise ValueError("ValenceEvent requires a non-empty target_id")
        object.__setattr__(self, "target_id", self.target_id.strip())
        if self.sign not in (1, -1):
            raise ValueError(f"ValenceEvent.sign must be +1 or -1 (got {self.sign!r})")
        magnitude = float(self.magnitude)
        if not math.isfinite(magnitude) or not (1.0 <= magnitude <= 10.0):
            raise ValueError(
                f"ValenceEvent.magnitude must be within 1..10 (got {self.magnitude!r}) — "
                "±10 is the cap; trauma is 10x an ordinary experience, not unbounded"
            )
        object.__setattr__(self, "magnitude", magnitude)
        kind = str(self.kind or "").strip().lower()
        if kind not in VALENCE_KINDS:
            raise ValueError(f"ValenceEvent.kind must be one of {sorted(VALENCE_KINDS)}")
        object.__setattr__(self, "kind", kind)
        scope = str(self.scope or "").strip().lower()
        if not scope:
            raise ValueError("ValenceEvent requires a non-empty scope")
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "owner_id", str(self.owner_id or "").strip())
        if not (isinstance(self.reason, str) and self.reason.strip()):
            raise ValueError("ValenceEvent requires a non-empty reason (appraisals must be explainable)")
        object.__setattr__(self, "value_refs",
                           tuple(str(v).strip() for v in (self.value_refs or ()) if str(v or "").strip()))
        if kind == "healing" and not str(dict(self.provenance or {}).get("heals") or "").strip():
            raise ValueError(
                "healing events must reference the scar they resolve via provenance['heals'] "
                "(the scar's event_id) — healing without a wound is not a resolution"
            )
        if kind == "break" and not str(dict(self.provenance or {}).get("breaks") or "").strip():
            raise ValueError(
                "break events must reference the bond they dissolve via provenance['breaks'] "
                "(the bond's event_id) — a break without a bond is not a revaluation"
            )
        if kind == "scar" and self.sign != -1:
            raise ValueError("scar events are negative by definition (sign must be -1)")
        if kind == "bond" and self.sign != 1:
            raise ValueError("bond events are positive by definition (sign must be +1)")

    def to_dict(self) -> Dict[str, Any]:
        return _jsonify(asdict(self))


class MemoryJournal(Protocol):
    """Append-only journal protocol (0017). Implementations must assign
    monotonically increasing `seq` (per journal instance, across ALL record
    types — seq is the single as_of axis) and be thread-safe (0013 contract).

    Write-side idempotency (a2a 0001/011 ask 3, all backends): a
    caller-SUPPLIED record id is an idempotency key — appending an existing
    event_id/binding_id/closure_id/snapshot_id/trace_id is a no-op returning
    the ORIGINAL stored record (original seq; selected-count untouched), so
    at-least-once effect replays never double-write. Empty ids get
    journal-assigned uuid4s and never conflict. Payloads are never compared
    (replays legitimately differ in wall-clock fields); reusing an id for
    DIFFERENT content is a caller bug — the first write wins.
    """

    def append_events(self, events: Sequence[MemoryEvent]) -> List[MemoryEvent]: ...

    def events(
        self,
        *,
        scope: str,
        owner_id: str,
        record_id: Optional[str] = None,
        kinds: Optional[Sequence[str]] = None,
        since_seq: Optional[int] = None,
        until_seq: Optional[int] = None,
        limit: int = 512,
    ) -> List[MemoryEvent]: ...

    def append_binding(self, binding: ScopeBinding) -> ScopeBinding: ...

    def bindings(
        self,
        *,
        record_id: Optional[str] = None,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
        fold: bool = True,
        until_seq: Optional[int] = None,
    ) -> List[ScopeBinding]: ...

    def append_closure(self, closure: ClosureRecord) -> ClosureRecord: ...

    def closures(
        self,
        *,
        assertion_id: Optional[str] = None,
        until_seq: Optional[int] = None,
        limit: int = 512,
    ) -> List[ClosureRecord]: ...

    def append_trace(self, trace: ReconstructionTrace) -> ReconstructionTrace: ...

    def traces(
        self, *, trace_id: Optional[str] = None, limit: int = 100,
        until_seq: Optional[int] = None,
    ) -> List[ReconstructionTrace]: ...  # until_seq: situate() groundwork (seam v1.2 delta 7)

    def append_snapshot(self, snapshot: Any) -> Any: ...  # seam.ActiveMemorySnapshot

    def snapshots(
        self, *, trace_id: Optional[str] = None, limit: int = 100,
        until_seq: Optional[int] = None,
    ) -> List[Any]: ...

    def append_valence(self, events: Sequence[ValenceEvent]) -> List[ValenceEvent]: ...

    def valence_events(
        self, *, scope: str, owner_id: str, target_id: Optional[str] = None,
        since_seq: Optional[int] = None, until_seq: Optional[int] = None,
        limit: int = 512,
    ) -> List[ValenceEvent]: ...

    def replay_records(
        self, *, since_seq: int = 0, until_seq: Optional[int] = None,
    ) -> Iterator[Tuple[str, Any]]: ...
    # ^ (family, record) across ALL SIX families in strict seq order —
    #   family ∈ {event, binding, closure, trace, snapshot, valence}.
    #   since_seq exclusive, until_seq inclusive (None = high-water).
    #   The replay/observability stream's substrate (a2a 0005).

    def selected_count(self, record_id: str, *, until_seq: Optional[int] = None) -> int: ...
    # ^ THE GLOBAL access count (maintainer's model): never decays.
    #   until_seq anchors it for as_of replay (C4: counts are journal
    #   history, so replays must see the count AS OF the anchor).

    def pair_selected_count(self, pair: Tuple[str, str], *, until_seq: Optional[int] = None) -> int: ...
    # ^ Global EDGE access count: cumulative co_selected per canonical pair.

    def seq_at(self, iso_ts: str) -> int: ...

    def current_seq(self) -> int: ...

    def close(self) -> None: ...


def fold_bindings(bindings: Sequence[ScopeBinding]) -> List[ScopeBinding]:
    """Latest-wins fold per (record_id, scope, owner_id). Shared by all backends."""
    latest: Dict[Tuple[str, str, str], ScopeBinding] = {}
    for b in bindings:
        key = (b.record_id, b.scope, b.owner_id)
        cur = latest.get(key)
        if cur is None or b.seq > cur.seq:
            latest[key] = b
    return sorted(latest.values(), key=lambda b: b.seq)
