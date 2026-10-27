"""Typed ledger provenance (ADR 0003 decisions 8-11; contract §1-§2).

A memory is either SOURCED (it names at least one ledger source: a run, a step, an artifact, a message, an event or
a diary entry) or DERIVED (it names the memories it was derived from, whose own provenance reaches a source).
Never neither. This module only VALIDATES and SHAPES references: it never reads a ledger (reconstruction is the
runtime facade's job, ADR 0003 decision 10), and it has no framework import (a `SourceRef` is a plain dict on the
wire).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

#: The ledger source kinds (contract §1).
SOURCE_KINDS: Tuple[str, ...] = ("run", "step", "artifact", "message", "event", "diary_entry")

# kind -> (required id fields, optional fields). `runtime_id` is optional on every kind.
_KIND_FIELDS: Mapping[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {
    "run": (("run_id",), ()),
    "step": (("run_id", "seq"), ("step_id",)),
    "artifact": (("artifact_id",), ("run_id",)),
    "message": (("message_id",), ("run_id",)),
    "event": (("event_id",), ("stream",)),
    "diary_entry": (("entry_id",), ("run_id",)),
}
_STR_FIELDS = ("run_id", "step_id", "artifact_id", "message_id", "event_id", "stream", "entry_id", "runtime_id")
_ALL_FIELDS = frozenset(_STR_FIELDS) | {"seq", "kind"}

#: Run ids that NO ledger can load (ADR 0003 decision 11: "a synthetic run id that no store can load is not a
#: source"): a chat session's id (`chat-<sid>`), the memory-scope owner ids hosts used as run ids
#: (`session_memory_<...>`, `global_memory`), and an entity's diary pseudo-run (`diary:<entity_id>`, which rides a
#: `diary_entry` ref as its optional run_id). Matched as prefixes. A `run` or `step` ref naming one is refused;
#: `Provenance.from_legacy` never lifts one into a ref. The runtime's run check reuses this constant.
SYNTHETIC_RUN_ID_PREFIXES: Tuple[str, ...] = ("chat-", "diary:", "session_memory_", "global_memory")


def is_synthetic_run_id(run_id: Any) -> bool:
    """True for a run id no ledger can load (`SYNTHETIC_RUN_ID_PREFIXES`)."""
    return isinstance(run_id, str) and run_id.strip().startswith(SYNTHETIC_RUN_ID_PREFIXES)


#: The keys of a provenance dict in the graph shape (contract §2).
PROVENANCE_KEYS = frozenset({"sources", "derived_from", "actor", "reader", "reason", "extra"})

#: Flat keys hosts wrote before the graph shape; `Provenance.from_legacy` lifts them.
LEGACY_KEYS = frozenset({"run_id", "turn_id", "writer_run_id", "span_id", "payload_ref", "entry_id"})


class InvalidSourceRef(ValueError):
    """A SourceRef whose kind is unknown, lacks its required id, or carries a field its kind does not have."""


class ProvenanceRequired(ValueError):
    """A write whose provenance names neither a ledger source nor a grounded memory it was derived from, or whose
    provenance is not in the graph shape (legacy flat keys must go through `Provenance.from_legacy`)."""


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidSourceRef(f"SourceRef id fields are strings (got {type(value).__name__}: {value!r})")
    out = value.strip()
    return out or None


@dataclass(frozen=True)
class SourceRef:
    """A typed pointer into the ledger. One canonical `key()` per ref; indexed both ways by the graph."""

    kind: str
    run_id: Optional[str] = None
    seq: Optional[int] = None
    step_id: Optional[str] = None
    artifact_id: Optional[str] = None
    message_id: Optional[str] = None
    event_id: Optional[str] = None
    stream: Optional[str] = None
    entry_id: Optional[str] = None
    runtime_id: Optional[str] = None

    def __post_init__(self) -> None:
        kind = str(self.kind or "").strip().lower()
        if kind not in _KIND_FIELDS:
            raise InvalidSourceRef(f"SourceRef.kind must be one of {list(SOURCE_KINDS)} (got {self.kind!r})")
        object.__setattr__(self, "kind", kind)
        for name in _STR_FIELDS:
            object.__setattr__(self, name, _clean_str(getattr(self, name)))
        seq = self.seq
        if seq is not None:
            # bool is an int subclass; a ledger row address is never True/False.
            if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
                raise InvalidSourceRef(f"SourceRef.seq is the ledger row address, a non-negative int (got {seq!r})")
        required, optional = _KIND_FIELDS[kind]
        for name in required:
            if getattr(self, name) is None:
                raise InvalidSourceRef(f"a {kind!r} SourceRef requires {name!r} (required: {list(required)})")
        if kind in ("run", "step") and is_synthetic_run_id(self.run_id):
            raise InvalidSourceRef(
                f"a {kind!r} SourceRef names the synthetic run id {self.run_id!r}, which no ledger can load "
                f"(SYNTHETIC_RUN_ID_PREFIXES = {list(SYNTHETIC_RUN_ID_PREFIXES)}); name the artifact or diary entry "
                "it belongs to instead"
            )
        allowed = set(required) | set(optional) | {"runtime_id"}
        foreign = [n for n in (*_STR_FIELDS, "seq") if n not in allowed and getattr(self, n) is not None]
        if foreign:
            raise InvalidSourceRef(
                f"a {kind!r} SourceRef does not carry {foreign} (allowed: {sorted(allowed)}); "
                "name a second ref of the right kind instead"
            )

    def key(self) -> str:
        """Canonical key: run:<run_id> | step:<run_id>#<seq> | artifact:<id> | message:<id> | event:<id> |
        diary_entry:<id>."""
        if self.kind == "run":
            return f"run:{self.run_id}"
        if self.kind == "step":
            return f"step:{self.run_id}#{self.seq}"
        if self.kind == "artifact":
            return f"artifact:{self.artifact_id}"
        if self.kind == "message":
            return f"message:{self.message_id}"
        if self.kind == "event":
            return f"event:{self.event_id}"
        return f"diary_entry:{self.entry_id}"

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"kind": self.kind}
        for name in ("run_id", "seq", "step_id", "artifact_id", "message_id", "event_id", "stream", "entry_id",
                     "runtime_id"):
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceRef":
        if isinstance(data, SourceRef):
            return data
        if not isinstance(data, Mapping):
            raise InvalidSourceRef(f"a SourceRef is a dict (got {type(data).__name__})")
        unknown = sorted(set(data) - _ALL_FIELDS)
        if unknown:
            raise InvalidSourceRef(f"unknown SourceRef keys {unknown} (known: {sorted(_ALL_FIELDS)})")
        return cls(**{k: v for k, v in data.items()})


def _coerce_sources(sources: Iterable[Any]) -> Tuple[SourceRef, ...]:
    if isinstance(sources, (str, bytes, Mapping)):
        raise InvalidSourceRef("Provenance.sources is a list of SourceRef dicts")
    out: Dict[str, SourceRef] = {}
    for item in sources or ():
        ref = SourceRef.from_dict(item)
        out.setdefault(ref.key(), ref)  # duplicates collapse on the canonical key, first wins
    return tuple(out.values())


def _coerce_ids(ids: Iterable[Any]) -> Tuple[str, ...]:
    if isinstance(ids, (str, bytes, Mapping)):
        raise ProvenanceRequired("Provenance.derived_from is a list of memory ids")
    out: List[str] = []
    for item in ids or ():
        if not isinstance(item, str) or not item.strip():
            raise ProvenanceRequired(f"Provenance.derived_from holds non-empty memory id strings (got {item!r})")
        if item.strip() not in out:
            out.append(item.strip())
    return tuple(out)


@dataclass(frozen=True)
class Provenance:
    """Where a memory, or a change of one, came from (contract §2). `actor` is required."""

    sources: Tuple[SourceRef, ...] = ()
    derived_from: Tuple[str, ...] = ()
    actor: str = ""
    reader: Optional[str] = None
    reason: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", _coerce_sources(self.sources))
        object.__setattr__(self, "derived_from", _coerce_ids(self.derived_from))
        actor = self.actor.strip() if isinstance(self.actor, str) else ""
        if not actor:
            raise ProvenanceRequired(
                "Provenance.actor is required ('abstractnote' | 'entity:<id>' | 'runtime' | 'abstractmemory:<pass>')"
            )
        object.__setattr__(self, "actor", actor)
        for name in ("reader", "reason"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ProvenanceRequired(f"Provenance.{name} is a string or None (got {value!r})")
            object.__setattr__(self, name, value.strip() or None if isinstance(value, str) else None)
        if not isinstance(self.extra, Mapping):
            raise ProvenanceRequired("Provenance.extra is a dict")
        object.__setattr__(self, "extra", dict(self.extra))

    def is_grounded(self) -> bool:
        """True when this provenance names a ledger source or a memory it was derived from. Whether a derived_from
        chain REACHES a source is the graph's check (`MemoryGraph.apply_revision`), not this object's."""
        return bool(self.sources or self.derived_from)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sources": [s.to_dict() for s in self.sources],
            "derived_from": list(self.derived_from),
            "actor": self.actor,
            "reader": self.reader,
            "reason": self.reason,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Provenance":
        """Strict: only the graph-shape keys. A flat legacy dict (`run_id`, `span_id`, ...) is refused with a
        pointer to `from_legacy` rather than silently dropped."""
        if isinstance(data, Provenance):
            return data
        if not isinstance(data, Mapping):
            raise ProvenanceRequired(f"provenance is a dict in the graph shape (got {type(data).__name__})")
        unknown = sorted(set(data) - PROVENANCE_KEYS)
        if unknown:
            legacy = sorted(set(unknown) & LEGACY_KEYS)
            hint = f" (legacy flat keys {legacy}: convert with Provenance.from_legacy)" if legacy else ""
            raise ProvenanceRequired(
                f"provenance carries keys outside the graph shape {unknown}{hint}; "
                f"known keys: {sorted(PROVENANCE_KEYS)}; anything else belongs in 'extra'"
            )
        # Raw values go to the coercers: `tuple("m1")` would split a string into characters and pass validation.
        return cls(
            sources=data.get("sources") or (),
            derived_from=data.get("derived_from") or (),
            actor=data.get("actor") if isinstance(data.get("actor"), str) else "",
            reader=data.get("reader"),
            reason=data.get("reason"),
            extra=dict(data.get("extra") or {}),
        )

    @classmethod
    def from_legacy(cls, flat: Mapping[str, Any], *, actor: Optional[str] = None) -> "Provenance":
        """Lift a flat legacy provenance dict into the graph shape (contract §2), in ONE place for the runtime.

        - `run_id` -> a `run` ref, unless it is synthetic (`SYNTHETIC_RUN_ID_PREFIXES`: no ledger can load it).
          A diary pseudo-run id (`diary:<entity_id>`) rides the `diary_entry` ref as its optional `run_id` when
          `entry_id` is present; any other synthetic run id stays in `extra` (never a ref).
        - `span_id` and `payload_ref` -> `artifact` refs (span_id = artifact_id, root ADR 0009; a leading
          `artifact:` prefix on payload_ref is stripped), carrying `run_id` when known.
        - `entry_id` -> a `diary_entry` ref.
        - `actor`, `reader`, `reason` are kept; every other key (`turn_id`, `writer_run_id`, `note_id`, ...) goes to
          `extra`.
        - A dict that already carries `sources` or `derived_from` (the graph shape, or the MIXED shape the runtime
          stamps: the legacy flat keys kept for older readers PLUS the `sources` it vouches for) takes its graph
          keys as they are (`sources` validated) and lifts every other key into `extra`; no ref is lifted from a
          flat key then (the stamped `sources` are what is real; a synthetic run id never becomes a ref). An
          explicit `extra` wins over a flat key of the same name.
        - `actor` defaults to the flat dict's own `actor`, else "runtime" (this is the runtime's conversion).
        Nothing is fabricated: no ref is produced for a key that is absent or empty.
        """
        if not isinstance(flat, Mapping):
            raise ProvenanceRequired(f"from_legacy expects a dict (got {type(flat).__name__})")
        chosen_actor = actor or (flat.get("actor") if isinstance(flat.get("actor"), str) else None) or "runtime"
        if "sources" in flat or "derived_from" in flat:
            given_extra = flat.get("extra")
            if given_extra is not None and not isinstance(given_extra, Mapping):
                raise ProvenanceRequired("Provenance.extra is a dict")
            others = {k: v for k, v in flat.items() if k not in PROVENANCE_KEYS}
            graph_keys = {k: v for k, v in flat.items() if k in PROVENANCE_KEYS and k != "extra"}
            return cls.from_dict({**graph_keys, "actor": chosen_actor,
                                  "extra": {**others, **dict(given_extra or {})}})

        def _s(key: str) -> Optional[str]:
            value = flat.get(key)
            return value.strip() or None if isinstance(value, str) else None

        run_id = _s("run_id")
        entry_id = _s("entry_id")
        diary_run = run_id if run_id and run_id.startswith("diary:") else None
        ledger_run = run_id if run_id and not is_synthetic_run_id(run_id) else None
        sources: List[Dict[str, Any]] = []
        if ledger_run:
            sources.append({"kind": "run", "run_id": ledger_run})
        for key in ("span_id", "payload_ref"):
            art = _s(key)
            if art and key == "payload_ref" and art.startswith("artifact:"):
                art = art[len("artifact:"):].strip() or None
            if art:
                ref: Dict[str, Any] = {"kind": "artifact", "artifact_id": art}
                if ledger_run:
                    ref["run_id"] = ledger_run
                sources.append(ref)
        if entry_id:
            ref = {"kind": "diary_entry", "entry_id": entry_id}
            if diary_run:
                ref["run_id"] = diary_run
            sources.append(ref)
        consumed = {"actor", "reader", "reason", "span_id", "payload_ref", "entry_id"}
        if ledger_run or (diary_run and entry_id):
            consumed.add("run_id")
        extra = {k: v for k, v in flat.items() if k not in consumed}
        return cls(
            sources=tuple(sources),
            actor=chosen_actor,
            reader=flat.get("reader") if isinstance(flat.get("reader"), str) else None,
            reason=flat.get("reason") if isinstance(flat.get("reason"), str) else None,
            extra=extra,
        )
