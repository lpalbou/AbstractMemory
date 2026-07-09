from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol, Tuple

from .models import TripleAssertion, canonicalize_term


@dataclass(frozen=True)
class TripleQuery:
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None
    scope: Optional[str] = None  # run|session|global
    owner_id: Optional[str] = None  # owner identifier within the selected scope

    # Exact id lookup (backlog 0009). When set, only assertions whose
    # assertion_id is in this tuple are returned; other term filters still apply.
    # Id lookups intentionally bypass closure/visibility folds (audit completeness).
    assertion_ids: Optional[Tuple[str, ...]] = None

    since: Optional[str] = None  # observed_at >= since
    until: Optional[str] = None  # observed_at <= until
    active_at: Optional[str] = None  # valid_from/valid_until window intersection

    # Optional semantic search:
    # - query_text requires a store-configured embedder
    # - query_vector bypasses embedding generation
    query_text: Optional[str] = None
    query_vector: Optional[List[float]] = None
    vector_column: str = "vector"
    min_score: Optional[float] = None  # cosine similarity threshold (semantic queries)

    limit: int = 100
    order: str = "desc"  # asc|desc by observed_at

    def __post_init__(self) -> None:
        # Normalize id filter: drop empties, keep stable order, tuple-ify.
        if self.assertion_ids is not None:
            ids = tuple(
                s.strip()
                for s in (self.assertion_ids or ())
                if isinstance(s, str) and s.strip()
            )
            object.__setattr__(self, "assertion_ids", ids if ids else None)

        # Canonicalize KG terms once (trim + lower; stable exact match).
        if isinstance(self.subject, str):
            s = canonicalize_term(self.subject)
            object.__setattr__(self, "subject", s if s else None)
        if isinstance(self.predicate, str):
            p = canonicalize_term(self.predicate)
            object.__setattr__(self, "predicate", p if p else None)
        if isinstance(self.object, str):
            o = canonicalize_term(self.object)
            object.__setattr__(self, "object", o if o else None)

        if isinstance(self.scope, str):
            sc = str(self.scope or "").strip().lower()
            object.__setattr__(self, "scope", sc if sc else None)

        # Keep metadata trimmed without changing semantics.
        if isinstance(self.owner_id, str):
            oid = self.owner_id.strip()
            object.__setattr__(self, "owner_id", oid if oid else None)
        if isinstance(self.since, str):
            s = self.since.strip()
            object.__setattr__(self, "since", s if s else None)
        if isinstance(self.until, str):
            u = self.until.strip()
            object.__setattr__(self, "until", u if u else None)
        if isinstance(self.active_at, str):
            a = self.active_at.strip()
            object.__setattr__(self, "active_at", a if a else None)

        # For semantic retrieval, normalize text input once.
        if isinstance(self.query_text, str):
            qt = str(self.query_text or "").strip()
            object.__setattr__(self, "query_text", qt if qt else None)

        if isinstance(self.vector_column, str):
            vc = self.vector_column.strip() or "vector"
            object.__setattr__(self, "vector_column", vc)

        if self.min_score is not None:
            try:
                ms = float(self.min_score)
            except Exception:
                ms = None
            if ms is None or not (ms == ms):  # NaN
                object.__setattr__(self, "min_score", None)
            else:
                object.__setattr__(self, "min_score", ms)

        if isinstance(self.order, str):
            object.__setattr__(self, "order", self.order.strip().lower() or "desc")


class TripleStore(Protocol):
    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]: ...

    def query(self, q: TripleQuery) -> List[TripleAssertion]: ...

    def close(self) -> None: ...
