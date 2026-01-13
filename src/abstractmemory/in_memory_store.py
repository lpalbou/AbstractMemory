from __future__ import annotations

import math
import uuid
from typing import Any, Iterable, List, Optional, Sequence

from .embeddings import TextEmbedder
from .models import TripleAssertion
from .store import TripleQuery


def _canonical_text(a: TripleAssertion) -> str:
    base = f"{a.subject} {a.predicate} {a.object}".strip()
    attrs = a.attributes if isinstance(a.attributes, dict) else {}

    parts: list[str] = [base]
    st = attrs.get("subject_type")
    ot = attrs.get("object_type")
    if isinstance(st, str) and st.strip():
        parts.append(f"subject_type: {st.strip()}")
    if isinstance(ot, str) and ot.strip():
        parts.append(f"object_type: {ot.strip()}")

    eq = attrs.get("evidence_quote")
    if isinstance(eq, str) and eq.strip():
        parts.append(f"evidence: {eq.strip()}")

    ctx = attrs.get("original_context")
    if isinstance(ctx, str) and ctx.strip():
        ctx2 = ctx.strip()
        if len(ctx2) > 400:
            ctx2 = ctx2[:400] + "…"
        parts.append(f"context: {ctx2}")

    return "\n".join(parts)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    # Defensive: handle empty vectors.
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        ax = float(a[i])
        bx = float(b[i])
        dot += ax * bx
        na += ax * ax
        nb += bx * bx
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class InMemoryTripleStore:
    """A dependency-free triple store (best-effort).

    Notes:
    - Intended for tests/dev and hosts without LanceDB installed.
    - Append-only: updates are represented as new assertions.
    - Vector search is optional and stores vectors in-memory only.
    """

    def __init__(
        self,
        *,
        embedder: Optional[TextEmbedder] = None,
        vector_column: str = "vector",
    ) -> None:
        self._embedder = embedder
        self._vector_column = str(vector_column or "vector")
        self._rows: list[dict[str, Any]] = []

    def close(self) -> None:
        return None

    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]:
        pending: list[TripleAssertion] = [a for a in assertions]
        if not pending:
            return []

        vectors: Optional[List[List[float]]] = None
        if self._embedder is not None:
            vectors = self._embedder.embed_texts([_canonical_text(a) for a in pending])

        ids: list[str] = []
        for i, a in enumerate(pending):
            assertion_id = str(uuid.uuid4())
            ids.append(assertion_id)
            row: dict[str, Any] = {"assertion_id": assertion_id, "assertion": a}
            if vectors is not None and i < len(vectors):
                row[self._vector_column] = vectors[i]
            self._rows.append(row)
        return ids

    def query(self, q: TripleQuery) -> List[TripleAssertion]:
        limit = int(q.limit) if isinstance(q.limit, int) else 100
        limit = max(1, min(limit, 10_000))

        def _match(a: TripleAssertion) -> bool:
            if q.subject and a.subject != q.subject:
                return False
            if q.predicate and a.predicate != q.predicate:
                return False
            if q.object and a.object != q.object:
                return False
            if q.scope and a.scope != q.scope:
                return False
            if q.owner_id and (a.owner_id or "") != q.owner_id:
                return False
            if q.since and (a.observed_at or "") < q.since:
                return False
            if q.until and (a.observed_at or "") > q.until:
                return False
            if q.active_at:
                at = q.active_at
                if a.valid_from and a.valid_from > at:
                    return False
                if a.valid_until and a.valid_until <= at:
                    return False
            return True

        rows = [r for r in self._rows if isinstance(r, dict) and isinstance(r.get("assertion"), TripleAssertion)]
        filtered: list[dict[str, Any]] = []
        for r in rows:
            a = r["assertion"]
            if _match(a):
                filtered.append(r)

        query_vector: Optional[Sequence[float]] = None
        if q.query_vector:
            query_vector = q.query_vector
        elif q.query_text:
            if self._embedder is None:
                raise ValueError("query_text requires a configured embedder (vector search); keyword fallback is disabled")
            query_vector = self._embedder.embed_texts([q.query_text])[0]

        if query_vector is not None:
            ranked: list[tuple[float, TripleAssertion]] = []
            for r in filtered:
                v = r.get(q.vector_column or self._vector_column)
                if not isinstance(v, list):
                    continue
                try:
                    score = _cosine(query_vector, v)
                except Exception:
                    score = 0.0
                if q.min_score is not None and score < float(q.min_score):
                    continue
                ranked.append((score, r["assertion"]))
            ranked.sort(key=lambda t: t[0], reverse=True)

            out: list[TripleAssertion] = []
            for score, a in ranked[:limit]:
                attrs = dict(a.attributes) if isinstance(a.attributes, dict) else {}
                retrieval = attrs.get("_retrieval") if isinstance(attrs.get("_retrieval"), dict) else {}
                retrieval2 = dict(retrieval)
                retrieval2["score"] = float(score)
                retrieval2.setdefault("metric", "cosine")
                attrs["_retrieval"] = retrieval2
                out.append(
                    TripleAssertion(
                        subject=a.subject,
                        predicate=a.predicate,
                        object=a.object,
                        scope=a.scope,
                        owner_id=a.owner_id,
                        observed_at=a.observed_at,
                        valid_from=a.valid_from,
                        valid_until=a.valid_until,
                        confidence=a.confidence,
                        provenance=dict(a.provenance),
                        attributes=attrs,
                    )
                )
            return out

        out: list[TripleAssertion] = [r["assertion"] for r in filtered]
        out.sort(key=lambda a: a.observed_at or "", reverse=(str(q.order).lower() != "asc"))
        return out[:limit]
