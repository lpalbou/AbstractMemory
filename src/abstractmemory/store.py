from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol

from .models import TripleAssertion


@dataclass(frozen=True)
class TripleQuery:
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None
    scope: Optional[str] = None  # run|session|global
    owner_id: Optional[str] = None  # owner identifier within the selected scope

    since: Optional[str] = None  # observed_at >= since
    until: Optional[str] = None  # observed_at <= until
    active_at: Optional[str] = None  # valid_from/valid_until window intersection

    # Optional semantic search:
    # - query_text requires a store-configured embedder
    # - query_vector bypasses embedding generation
    query_text: Optional[str] = None
    query_vector: Optional[List[float]] = None
    vector_column: str = "vector"

    limit: int = 100
    order: str = "desc"  # asc|desc by observed_at


class TripleStore(Protocol):
    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]: ...

    def query(self, q: TripleQuery) -> List[TripleAssertion]: ...

    def close(self) -> None: ...
