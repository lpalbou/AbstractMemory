"""The revision: the unit of change of the graph (ADR 0003 decision 6; contract §3).

Every change is one append-only revision `{revision_id, scope, owner_id, cause, occurred_at, recorded_at, ops,
provenance, summary}` whose ops apply together and atomically (`MemoryGraph.apply_revision`). A revision is
idempotent on its id, and replaying the log into an empty store yields the same graph. Ops in this slice:

- ``assert``: payload = `TripleAssertion.to_dict()` (assertion_id may be given; the graph assigns a deterministic
  one otherwise, so the logged revision replays byte-identically).
- ``close``: payload = {assertion_id, valid_until, kind, replacement_ids, reason, ripple_source, ripple_hops}; sets
  the row's window (when it is still open; a bounded window is kept) AND writes the journal closure (cause fields on
  its provenance) in the same op. A memory is closed once; a second close is skipped.
- ``narrow``: payload = {assertion_id, valid_until, reason}; moves an already-closed window earlier only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..journal_common import normalize_iso_ts
from ..models import TripleAssertion, utc_now_iso_seconds
from .provenance import Provenance

#: Why a revision happened (ADR 0003 decision 6).
REVISION_CAUSES: Tuple[str, ...] = (
    "ingest", "reinterpret", "merge", "unmerge", "ripple", "person", "maintenance", "import", "migration",
)
#: The ops of this slice (entity and alias ops arrive with backlog 0050).
REVISION_OPS: Tuple[str, ...] = ("assert", "close", "narrow")
#: The kinds a `close` op may carry (ADR 0003 decision 7; `narrowed` is the `narrow` op, not a close kind).
CLOSE_KINDS: Tuple[str, ...] = ("retract", "supersede", "reinterpreted", "merged")

_CLOSE_KEYS = frozenset({"assertion_id", "valid_until", "kind", "replacement_ids", "reason", "ripple_source",
                         "ripple_hops"})
_NARROW_KEYS = frozenset({"assertion_id", "valid_until", "reason"})


#: The timestamp fields of an `assert` payload, normalized like every other time of a revision.
_ASSERT_TIMES = ("observed_at", "valid_from", "valid_until")


def normalize_timestamp(value: Any, what: str) -> str:
    """One timestamp of the graph: parsed as ISO-8601 and rewritten to the package's canonical UTC text form
    (microseconds, '+00:00': `journal_common.normalize_iso_ts`, the shape of `utc_now_iso_seconds`). Stores and
    queries compare these as strings; that is only correct when every value shares one form ('2026-05-31T23:00-02:00'
    sorts before '2026-06-01T00:00Z' but is the later instant). Raises ValueError for anything that is not a
    timestamp ("next tuesday")."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty ISO-8601 timestamp (got {value!r})")
    try:
        return normalize_iso_ts(value)
    except ValueError as exc:
        raise ValueError(f"{what} must be an ISO-8601 timestamp (got {value!r}): {exc}") from None


def _req_str(payload: Mapping[str, Any], key: str, op: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"a {op!r} op requires a non-empty string {key!r} (got {value!r})")
    return value.strip()


def _normalize_close(payload: Mapping[str, Any]) -> Dict[str, Any]:
    unknown = sorted(set(payload) - _CLOSE_KEYS)
    if unknown:
        raise ValueError(f"unknown 'close' op keys {unknown} (known: {sorted(_CLOSE_KEYS)})")
    kind = _req_str(payload, "kind", "close").lower()
    if kind not in CLOSE_KINDS:
        raise ValueError(f"a 'close' op kind must be one of {list(CLOSE_KINDS)} (got {kind!r})")
    raw_ids = payload.get("replacement_ids") or ()
    if isinstance(raw_ids, (str, bytes)) or not all(isinstance(x, str) and x.strip() for x in raw_ids):
        raise ValueError(f"'close' replacement_ids is a list of non-empty id strings (got {raw_ids!r})")
    replacement_ids = list(dict.fromkeys(x.strip() for x in raw_ids))
    if kind in ("supersede", "merged") and not replacement_ids:
        raise ValueError(f"a {kind!r} close requires replacement_ids (what it was {kind} by/into)")
    ripple_source = payload.get("ripple_source")
    if ripple_source is not None and (not isinstance(ripple_source, str) or not ripple_source.strip()):
        raise ValueError(f"'close' ripple_source is a memory id or None (got {ripple_source!r})")
    ripple_hops = payload.get("ripple_hops")
    if ripple_hops is not None and (isinstance(ripple_hops, bool) or not isinstance(ripple_hops, int)
                                    or ripple_hops < 0):
        raise ValueError(f"'close' ripple_hops is a non-negative int or None (got {ripple_hops!r})")
    return {
        "assertion_id": _req_str(payload, "assertion_id", "close"),
        "valid_until": normalize_timestamp(payload.get("valid_until"), "a 'close' op's valid_until"),
        "kind": kind,
        "replacement_ids": replacement_ids,
        "reason": _req_str(payload, "reason", "close"),
        "ripple_source": ripple_source.strip() if isinstance(ripple_source, str) else None,
        "ripple_hops": ripple_hops,
    }


def _normalize_narrow(payload: Mapping[str, Any]) -> Dict[str, Any]:
    unknown = sorted(set(payload) - _NARROW_KEYS)
    if unknown:
        raise ValueError(f"unknown 'narrow' op keys {unknown} (known: {sorted(_NARROW_KEYS)})")
    return {
        "assertion_id": _req_str(payload, "assertion_id", "narrow"),
        "valid_until": normalize_timestamp(payload.get("valid_until"), "a 'narrow' op's valid_until"),
        "reason": _req_str(payload, "reason", "narrow"),
    }


@dataclass(frozen=True)
class RevisionOp:
    """One operation of a revision. The payload is validated and normalized at construction."""

    op: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        op = str(self.op or "").strip().lower()
        if op not in REVISION_OPS:
            raise ValueError(f"RevisionOp.op must be one of {list(REVISION_OPS)} (got {self.op!r})")
        object.__setattr__(self, "op", op)
        if not isinstance(self.payload, Mapping):
            raise ValueError(f"RevisionOp.payload is a dict (got {type(self.payload).__name__})")
        if op == "assert":
            payload = dict(self.payload)
            for key in _ASSERT_TIMES:  # absent/None stays absent (the graph fills observed_at from the revision)
                if payload.get(key) is not None:
                    payload[key] = normalize_timestamp(payload[key], f"an 'assert' op's {key}")
            TripleAssertion.from_dict(payload)  # validates terms; raises on a malformed claim
        elif op == "close":
            payload = _normalize_close(self.payload)
        else:
            payload = _normalize_narrow(self.payload)
        object.__setattr__(self, "payload", payload)

    def to_dict(self) -> Dict[str, Any]:
        return {"op": self.op, "payload": dict(self.payload)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RevisionOp":
        if isinstance(data, RevisionOp):
            return data
        if not isinstance(data, Mapping):
            raise ValueError(f"a RevisionOp is a dict (got {type(data).__name__})")
        return cls(op=str(data.get("op") or ""), payload=dict(data.get("payload") or {}))


@dataclass(frozen=True, kw_only=True)
class Revision:
    """One append-only change of the graph (contract §3). Keyword-only."""

    revision_id: str
    scope: str
    owner_id: str
    cause: str
    occurred_at: str  # observation time: when the source said it (ISO UTC)
    ops: Tuple[RevisionOp, ...]
    provenance: Provenance
    recorded_at: str = field(default_factory=utc_now_iso_seconds)  # record time: when this mind learned it
    summary: Optional[str] = None

    def __post_init__(self) -> None:
        rid = self.revision_id.strip() if isinstance(self.revision_id, str) else ""
        if not rid:
            raise ValueError("Revision.revision_id is required (it is the idempotency key)")
        object.__setattr__(self, "revision_id", rid)
        scope = self.scope.strip().lower() if isinstance(self.scope, str) else ""
        if not scope:
            raise ValueError("Revision.scope is required")
        object.__setattr__(self, "scope", scope)
        if self.owner_id is not None and not isinstance(self.owner_id, str):
            raise ValueError(f"Revision.owner_id is a string (got {self.owner_id!r})")
        object.__setattr__(self, "owner_id", (self.owner_id or "").strip())
        cause = self.cause.strip().lower() if isinstance(self.cause, str) else ""
        if cause not in REVISION_CAUSES:
            raise ValueError(f"Revision.cause must be one of {list(REVISION_CAUSES)} (got {self.cause!r})")
        object.__setattr__(self, "cause", cause)
        for name in ("occurred_at", "recorded_at"):
            object.__setattr__(self, name, normalize_timestamp(getattr(self, name), f"Revision.{name}"))
        if isinstance(self.ops, (str, bytes, Mapping)):
            raise ValueError("Revision.ops is a sequence of RevisionOp")
        ops = tuple(RevisionOp.from_dict(o) for o in (self.ops or ()))
        if not ops:
            raise ValueError("Revision.ops must hold at least one op (a revision that changes nothing is not one)")
        object.__setattr__(self, "ops", ops)
        object.__setattr__(self, "provenance", Provenance.from_dict(self.provenance))
        if self.summary is not None and not isinstance(self.summary, str):
            raise ValueError(f"Revision.summary is a string or None (got {self.summary!r})")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "scope": self.scope,
            "owner_id": self.owner_id,
            "cause": self.cause,
            "occurred_at": self.occurred_at,
            "recorded_at": self.recorded_at,
            "ops": [o.to_dict() for o in self.ops],
            "provenance": self.provenance.to_dict(),
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Revision":
        if not isinstance(data, Mapping):
            raise ValueError(f"a Revision is a dict (got {type(data).__name__})")
        kwargs: Dict[str, Any] = {
            "revision_id": data.get("revision_id"),
            "scope": data.get("scope"),
            "owner_id": data.get("owner_id") or "",
            "cause": data.get("cause"),
            "occurred_at": data.get("occurred_at"),
            "ops": tuple(data.get("ops") or ()),
            "provenance": data.get("provenance") or {},
            "summary": data.get("summary"),
        }
        if data.get("recorded_at"):
            kwargs["recorded_at"] = data["recorded_at"]
        return cls(**kwargs)


@dataclass(frozen=True)
class RevisionResult:
    """What `apply_revision` did. `applied` is False when the revision id was already in the log (nothing changed).
    `skipped` lists ops that changed nothing (`{"op", "index", "assertion_id", "why"}`): an assert of an id the
    graph already holds, a close of a memory the graph already closed, a narrow of a window already at or before
    the date."""

    revision_id: str
    applied: bool
    assertion_ids: List[str] = field(default_factory=list)
    closed: List[str] = field(default_factory=list)
    narrowed: List[str] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    seq: Optional[int] = None  # the revision's position in the log (its change-feed cursor), None when not applied
