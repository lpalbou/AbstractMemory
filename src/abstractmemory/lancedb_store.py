from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .embeddings import TextEmbedder
from .models import TripleAssertion
from .store import TripleQuery


def _import_lancedb():
    try:
        import lancedb  # type: ignore

        return lancedb
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "LanceDB support requires `lancedb` (and its dependencies). "
            "Install it in your environment (offline/local install is fine), e.g. `pip install lancedb`."
        ) from e


def _escape_sql_string(value: str) -> str:
    # LanceDB uses SQL-like filter strings; escape single quotes.
    return str(value).replace("'", "''")


def _build_where_clause(q: TripleQuery) -> str:
    parts: list[str] = []

    if q.subject:
        parts.append(f"subject = '{_escape_sql_string(q.subject)}'")
    if q.predicate:
        parts.append(f"predicate = '{_escape_sql_string(q.predicate)}'")
    if q.object:
        parts.append(f"object = '{_escape_sql_string(q.object)}'")
    if q.scope:
        parts.append(f"scope = '{_escape_sql_string(q.scope)}'")
    if q.owner_id:
        parts.append(f"owner_id = '{_escape_sql_string(q.owner_id)}'")

    if q.since:
        parts.append(f"observed_at >= '{_escape_sql_string(q.since)}'")
    if q.until:
        parts.append(f"observed_at <= '{_escape_sql_string(q.until)}'")

    if q.active_at:
        at = _escape_sql_string(q.active_at)
        parts.append(f"(valid_from IS NULL OR valid_from <= '{at}')")
        parts.append(f"(valid_until IS NULL OR valid_until > '{at}')")

    return " AND ".join(parts)


def _canonical_text(a: TripleAssertion) -> str:
    # Stable, information-rich representation for embedding retrieval.
    #
    # Why include more than "s p o":
    # - semantic queries often refer to details that aren't present in the triple surface form
    # - extractor-provided evidence/context improves retrieval selectivity without requiring
    #   a separate episodic document store in v0
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


def _loads_json(raw: object) -> dict:
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


class LanceDBTripleStore:
    """LanceDB-backed append-only triple store with optional vector search.

    Notes:
    - Append-only: updates are represented as new assertions.
    - Vector search is optional and requires `embedder` (for query_text) or query_vector.
    """

    def __init__(
        self,
        uri: str | Path,
        *,
        table_name: str = "triple_assertions",
        embedder: Optional[TextEmbedder] = None,
        vector_column: str = "vector",
    ):
        self._lancedb = _import_lancedb()
        self._db = self._lancedb.connect(str(uri))
        self._table_name = str(table_name)
        self._vector_column = str(vector_column or "vector")
        self._embedder = embedder

        self._table = None
        try:
            # `table_names()` is deprecated upstream but is stable and sufficient for local stores.
            if self._table_name in set(self._db.table_names()):
                self._table = self._db.open_table(self._table_name)
        except Exception:
            self._table = None

    def close(self) -> None:
        # LanceDB tables/connections are managed by the library; nothing required here.
        return None

    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]:
        rows: list[dict[str, Any]] = []
        ids: List[str] = []
        pending: List[TripleAssertion] = []

        for a in assertions:
            pending.append(a)

        if not pending:
            return []

        # Always store a canonical text column (useful for debugging and future indexing).
        texts: List[str] = [_canonical_text(a) for a in pending]
        vectors: Optional[List[List[float]]] = None
        if self._embedder is not None:
            vectors = self._embedder.embed_texts(texts)

        for idx, a in enumerate(pending):
            assertion_id = str(uuid.uuid4())
            ids.append(assertion_id)
            row: Dict[str, Any] = {
                "assertion_id": assertion_id,
                "subject": a.subject,
                "predicate": a.predicate,
                "object": a.object,
                "scope": a.scope,
                "owner_id": a.owner_id,
                "observed_at": a.observed_at,
                "valid_from": a.valid_from,
                "valid_until": a.valid_until,
                "confidence": a.confidence,
                "provenance_json": json.dumps(a.provenance, ensure_ascii=False, separators=(",", ":")),
                "attributes_json": json.dumps(a.attributes, ensure_ascii=False, separators=(",", ":")),
                "text": texts[idx],
            }

            if vectors is not None and idx < len(vectors):
                row[self._vector_column] = vectors[idx]

            # Keep JSON compact (omit nulls).
            row = {k: v for k, v in row.items() if v is not None}
            rows.append(row)

        if self._table is None:
            # Create on first insert so we can infer vector dimensionality from real data.
            self._table = self._db.create_table(self._table_name, data=rows, mode="create")
        else:
            self._table.add(rows)
        return ids

    def query(self, q: TripleQuery) -> List[TripleAssertion]:
        if self._table is None:
            return []

        limit = int(q.limit) if isinstance(q.limit, int) else 100
        limit = max(1, min(limit, 10_000))

        where = _build_where_clause(q)

        query_vector: Optional[Sequence[float]] = None
        if q.query_vector:
            query_vector = q.query_vector
        elif q.query_text:
            if self._embedder is None:
                raise ValueError("query_text requires a configured embedder (vector search); keyword fallback is disabled")
            query_vector = self._embedder.embed_texts([q.query_text])[0]

        qb = None
        if query_vector is not None:
            # Use cosine metric so `min_score` can be expressed as cosine similarity.
            qb = self._table.search(query_vector, vector_column_name=q.vector_column or self._vector_column).metric("cosine")
        if qb is None:
            qb = self._table.search()

        if where:
            qb = qb.where(where)

        rows = qb.limit(limit).to_list()

        out: List[TripleAssertion] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            provenance = _loads_json(r.get("provenance_json"))
            attributes = _loads_json(r.get("attributes_json"))

            # Attach retrieval metadata for semantic queries.
            # LanceDB returns `_distance` for vector searches; with metric=cosine, similarity = 1 - distance.
            if query_vector is not None:
                dist_raw = r.get("_distance")
                dist: Optional[float] = None
                try:
                    dist = float(dist_raw) if dist_raw is not None else None
                except Exception:
                    dist = None
                score: Optional[float] = None
                if dist is not None:
                    score = 1.0 - dist

                if q.min_score is not None and score is not None and score < float(q.min_score):
                    continue

                retrieval = attributes.get("_retrieval") if isinstance(attributes.get("_retrieval"), dict) else {}
                retrieval2 = dict(retrieval)
                if score is not None:
                    retrieval2["score"] = score
                if dist is not None:
                    retrieval2["distance"] = dist
                retrieval2.setdefault("metric", "cosine")
                attributes = dict(attributes)
                attributes["_retrieval"] = retrieval2
            out.append(
                TripleAssertion(
                    subject=str(r.get("subject") or ""),
                    predicate=str(r.get("predicate") or ""),
                    object=str(r.get("object") or ""),
                    scope=str(r.get("scope") or "run"),
                    owner_id=str(r.get("owner_id")) if r.get("owner_id") is not None else None,
                    observed_at=str(r.get("observed_at") or ""),
                    valid_from=str(r.get("valid_from")) if r.get("valid_from") is not None else None,
                    valid_until=str(r.get("valid_until")) if r.get("valid_until") is not None else None,
                    confidence=r.get("confidence") if isinstance(r.get("confidence"), (int, float)) else None,
                    provenance=provenance,
                    attributes=attributes,
                )
            )

        # For non-semantic queries, keep compatibility with SQLite semantics: order by observed_at.
        # For semantic queries, LanceDB already returns similarity-ranked results.
        if query_vector is None:
            out.sort(key=lambda a: a.observed_at or "", reverse=(str(q.order).lower() != "asc"))
        return out[:limit]
