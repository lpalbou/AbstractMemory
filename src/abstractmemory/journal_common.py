"""Backend-agnostic journal semantics shared by BOTH journal backends.

One task: the append-boundary rules every backend must apply identically
(cross-backend parity, backlog 0011) — id assignment, observed_at
canonicalization, and the strict-JSON payload boundary (audit a5/s5).
`journal_memory` and `journal_sqlite` import from here; record shapes and
the protocol stay frozen in `journal.py`.
"""

from __future__ import annotations

import copy
import math
import uuid
import warnings
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, List, Sequence

from .journal import (
    ClosureRecord,
    MemoryEvent,
    ReconstructionTrace,
    ScopeBinding,
    ValenceEvent,
    utc_now_iso,
)
from .seam import ActiveMemorySnapshot

__all__ = [
    "canonical_observed_at",
    "new_id",
    "normalize_iso_ts",
    "sanitize_batch",
    "sanitize_json_payload",
]


def new_id() -> str:
    # uuid4, not ULID: the package carries no ULID dependency and `seq` already
    # provides total ordering, so ids only need uniqueness (same convention as
    # the triple stores).
    return str(uuid.uuid4())


def normalize_iso_ts(iso_ts: str) -> str:
    """Normalize an ISO-8601 timestamp to the journal's canonical text form
    (UTC, microsecond precision, '+00:00' offset — the `utc_now_iso()` shape).

    WHY: `seq_at()` compares timestamps lexicographically against stored
    `observed_at` values; that is only correct when both sides share one
    textual form. Handles 'Z' suffixes (Python 3.10 `fromisoformat` rejects
    them) and treats naive datetimes as UTC (the journal clock is UTC).
    """
    raw = str(iso_ts or "").strip()
    if not raw:
        raise ValueError("expected an ISO-8601 timestamp, got an empty value")
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"could not parse ISO-8601 timestamp {iso_ts!r}: {exc}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def canonical_observed_at(observed_at: Any) -> str:
    """Canonicalize a record's observed_at at append time.

    Empty values are filled with "now": an empty string sorts before every
    timestamp and would make the record match every `seq_at()` query.
    Parseable values are rewritten to the canonical UTC form (same instant,
    comparable text). Unparseable values RAISE (audit s2): a verbatim
    garbage timestamp silently corrupts the lexicographic `seq_at()` axis
    for every later query — a loud boundary error beats quiet corruption.
    """
    raw = str(observed_at or "").strip()
    if not raw:
        return utc_now_iso()
    return normalize_iso_ts(raw)  # ValueError on unparseable input


def sanitize_json_payload(value: Any) -> tuple[Any, bool]:
    """Normalize one JSON-bound payload for the strict-JSON boundary
    (audit a5/s5): seam `_jsonify` semantics (tuples→lists, datetimes and
    other objects → str) PLUS non-finite floats (NaN/±Inf) → None. Returns
    (clean, had_nonfinite). Shared by both journal backends and the
    formation encoder so every persisted payload survives
    `json.dumps(allow_nan=False)` and reads back identically everywhere.
    """
    if isinstance(value, dict):
        out_d: dict = {}
        dirty = False
        for k, v in value.items():
            clean, d = sanitize_json_payload(v)
            out_d[str(k)] = clean
            dirty = dirty or d
        return out_d, dirty
    if isinstance(value, (list, tuple)):
        out_l: list = []
        dirty = False
        for v in value:
            clean, d = sanitize_json_payload(v)
            out_l.append(clean)
            dirty = dirty or d
        return out_l, dirty
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value, False
    if isinstance(value, float):
        return (value, False) if math.isfinite(value) else (None, True)
    return str(value), False  # datetimes and arbitrary objects stringify (seam rule)


# JSON-bound payload fields per record family (everything that lands in a
# *_json column / seam to_dict). Scalar typed columns are validated at
# construction (e.g. MemoryEvent.weight must be finite).
_JSON_PAYLOAD_FIELDS: dict = {
    MemoryEvent: ("provenance",),
    ScopeBinding: ("provenance",),
    ClosureRecord: ("provenance",),
    ReconstructionTrace: ("need", "searched_scopes", "candidates", "dropped", "budgets", "budget_spent", "admissions"),
    ActiveMemorySnapshot: ("display", "provenance"),
    ValenceEvent: ("provenance",),
}


def sanitize_batch(records: Sequence[Any]) -> List[Any]:
    """Sanitize every record's JSON payload fields; ONE #FALLBACK warning per
    append batch when non-finite floats were normalized (audit contract)."""
    out: List[Any] = []
    dirty = False
    for r in records:
        updates: dict = {}
        for name in _JSON_PAYLOAD_FIELDS.get(type(r), ()):
            clean, d = sanitize_json_payload(getattr(r, name))
            updates[name] = clean
            dirty = dirty or d
        out.append(replace(r, **updates) if updates else r)
    if dirty:
        warnings.warn(
            "#FALLBACK: non-finite floats (NaN/Inf) in journal payloads were normalized "
            "to None (strict-JSON boundary)",
            RuntimeWarning,
            stacklevel=3,
        )
    return out


# --- enrichment -------------------------------------------------------------
#
# Append methods must return NEW frozen instances (never mutate inputs) with
# journal-assigned fields. The journal ALWAYS overwrites `seq` — it owns the
# axis, and trusting a caller-supplied seq could break monotonicity and
# corrupt `as_of` replay. Ids are honored when non-empty (deterministic
# import flows), assigned when empty. deepcopy isolates mutable dict fields
# (provenance etc.) from the caller's instance; `replace` re-runs
# __post_init__ validation on the way in.


def _enrich_event(event: MemoryEvent, seq: int) -> MemoryEvent:
    src = copy.deepcopy(event)
    return replace(
        src,
        event_id=(str(src.event_id or "").strip() or new_id()),
        seq=int(seq),
        observed_at=canonical_observed_at(src.observed_at),
    )


def _enrich_binding(binding: ScopeBinding, seq: int) -> ScopeBinding:
    src = copy.deepcopy(binding)
    return replace(
        src,
        binding_id=(str(src.binding_id or "").strip() or new_id()),
        seq=int(seq),
        observed_at=canonical_observed_at(src.observed_at),
    )


def _enrich_closure(closure: ClosureRecord, seq: int) -> ClosureRecord:
    src = copy.deepcopy(closure)
    return replace(
        src,
        closure_id=(str(src.closure_id or "").strip() or new_id()),
        seq=int(seq),
        observed_at=canonical_observed_at(src.observed_at),
    )


def _enrich_trace(trace: ReconstructionTrace, seq: int) -> ReconstructionTrace:
    # ReconstructionTrace has no __post_init__, so lists passed where tuples
    # are declared would otherwise be stored as-is in memory but come back as
    # tuples from SQLite — coerce here so both backends return one shape.
    src = copy.deepcopy(trace)
    return replace(
        src,
        trace_id=(str(src.trace_id or "").strip() or new_id()),
        seq=int(seq),
        observed_at=canonical_observed_at(src.observed_at),
        need=dict(src.need or {}),
        searched_scopes=tuple(dict(x) for x in (src.searched_scopes or ())),
        channels=tuple(str(x) for x in (src.channels or ())),
        candidates=tuple(dict(x) for x in (src.candidates or ())),
        selected=tuple(str(x) for x in (src.selected or ())),
        dropped=tuple(dict(x) for x in (src.dropped or ())),
        cues=tuple(str(x) for x in (src.cues or ())),
        budgets=dict(src.budgets or {}),
        budget_spent=dict(src.budget_spent or {}),
        warnings=tuple(str(x) for x in (src.warnings or ())),
        admissions={str(k): str(v) for k, v in (src.admissions or {}).items()},
    )


def _enrich_valence(event: ValenceEvent, seq: int) -> ValenceEvent:
    src = copy.deepcopy(event)
    return replace(
        src,
        event_id=(str(src.event_id or "").strip() or new_id()),
        seq=int(seq),
        observed_at=canonical_observed_at(src.observed_at),
    )


def _enrich_snapshot(snapshot: ActiveMemorySnapshot, seq: int) -> ActiveMemorySnapshot:
    # Same tuple-coercion rationale as traces (ActiveMemorySnapshot has no
    # __post_init__ either). seq is journal-assigned; callers leave the
    # seam dataclass's -1 sentinel default in place.
    src = copy.deepcopy(snapshot)
    return replace(
        src,
        snapshot_id=(str(src.snapshot_id or "").strip() or new_id()),
        seq=int(seq),
        used_record_ids=tuple(str(x) for x in (src.used_record_ids or ())),
        display=tuple(dict(x) for x in (src.display or ())),
        prompt_token_estimate=(
            int(src.prompt_token_estimate) if src.prompt_token_estimate is not None else None
        ),
        observed_at=canonical_observed_at(src.observed_at),
        provenance=dict(src.provenance or {}),
    )
