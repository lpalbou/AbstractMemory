from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso_seconds() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonicalize_term(value: str) -> str:
    """Canonicalize a KG term for stable matching.

    Policy (v0):
    - trim surrounding whitespace
    - lowercase (avoids missed matches due to casing drift)
    """
    return str(value or "").strip().lower()


def normalize_term(value: str) -> str:
    """Normalize a KG term for case-insensitive matching (query-time)."""
    # `canonicalize_term` already lowercases; keep this for clarity/compatibility.
    return canonicalize_term(value).lower()


@dataclass(frozen=True)
class TripleAssertion:
    """An append-only semantic assertion with temporal and provenance metadata."""

    subject: str
    predicate: str
    object: str
    scope: str = "run"  # run|session|global
    owner_id: Optional[str] = None  # scope owner identifier (e.g. run_id, session_memory_*, global_memory)
    observed_at: str = field(default_factory=utc_now_iso_seconds)

    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    confidence: Optional[float] = None

    provenance: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Canonicalize KG terms (trim + lower) for stable matching.
        object.__setattr__(self, "subject", canonicalize_term(self.subject))
        object.__setattr__(self, "predicate", canonicalize_term(self.predicate))
        object.__setattr__(self, "object", canonicalize_term(self.object))

        # Keep scope canonical (it is part of the partitioning key).
        object.__setattr__(self, "scope", str(self.scope or "").strip().lower() or "run")

        # Defensive trimming for timestamps/ids without altering semantics.
        if isinstance(self.owner_id, str):
            oid = self.owner_id.strip()
            object.__setattr__(self, "owner_id", oid if oid else None)
        object.__setattr__(self, "observed_at", str(self.observed_at or "").strip() or utc_now_iso_seconds())
        if isinstance(self.valid_from, str):
            vf = self.valid_from.strip()
            object.__setattr__(self, "valid_from", vf if vf else None)
        if isinstance(self.valid_until, str):
            vu = self.valid_until.strip()
            object.__setattr__(self, "valid_until", vu if vu else None)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "scope": self.scope,
            "owner_id": self.owner_id,
            "observed_at": self.observed_at,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "confidence": self.confidence,
            "provenance": dict(self.provenance),
            "attributes": dict(self.attributes),
        }
        # Keep JSON compact (omit nulls).
        return {k: v for k, v in out.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TripleAssertion":
        if not isinstance(data, dict):
            raise TypeError("TripleAssertion.from_dict expects a dict")

        subject = data.get("subject")
        predicate = data.get("predicate")
        obj = data.get("object")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("TripleAssertion.subject must be a non-empty string")
        if not isinstance(predicate, str) or not predicate.strip():
            raise ValueError("TripleAssertion.predicate must be a non-empty string")
        if not isinstance(obj, str) or not obj.strip():
            raise ValueError("TripleAssertion.object must be a non-empty string")

        scope = data.get("scope") if isinstance(data.get("scope"), str) else "run"
        owner_id = data.get("owner_id") if isinstance(data.get("owner_id"), str) else None
        observed_at = data.get("observed_at") if isinstance(data.get("observed_at"), str) else utc_now_iso_seconds()

        provenance = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
        attributes = data.get("attributes") if isinstance(data.get("attributes"), dict) else {}

        confidence_raw = data.get("confidence")
        confidence: Optional[float] = None
        if confidence_raw is not None:
            try:
                confidence = float(confidence_raw)
            except Exception:
                confidence = None

        return cls(
            subject=subject,
            predicate=predicate,
            object=obj,
            scope=scope,
            owner_id=owner_id.strip() if isinstance(owner_id, str) and owner_id.strip() else None,
            observed_at=observed_at.strip() or utc_now_iso_seconds(),
            valid_from=data.get("valid_from") if isinstance(data.get("valid_from"), str) else None,
            valid_until=data.get("valid_until") if isinstance(data.get("valid_until"), str) else None,
            confidence=confidence,
            provenance=dict(provenance),
            attributes=dict(attributes),
        )
