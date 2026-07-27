from __future__ import annotations

import threading
import uuid
from typing import Any, Iterable, List, Optional, Sequence

from .embedding_pin import (
    annotate_embed_failure,
    embed_texts_degradable,
    build_pin,
    check_add_dimension,
    check_model_compat,
    check_query_dimension,
    embedder_model_id,
    warn_first_write_pin,
)
from .embeddings import TextEmbedder
from .models import TripleAssertion, normalize_term
from .store import TripleQuery
# Shared scoring (one definition for all stores — see vector_scoring.py);
# the _cosine alias keeps this module's established internal name.
from .vector_scoring import cosine as _cosine, rank_by_cosine


# Single source of truth for the embedding/keyword text (canonical_text.py
# v2: clean record digests); the alias keeps this module's established name
# and the golden parity tests meaningful.
from .canonical_text import canonical_text as _canonical_text  # noqa: E402
from .canonical_text import is_record_edge as _is_record_edge  # noqa: E402


def _result_copy(a: TripleAssertion, assertion_id: Any, *, attributes: dict[str, Any] | None = None) -> TripleAssertion:
    """Rebuild an assertion for query results: fresh dicts + read-side identity."""
    return TripleAssertion(
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
        attributes=attributes if attributes is not None else dict(a.attributes),
        assertion_id=str(assertion_id) if isinstance(assertion_id, str) and assertion_id else None,
    )


class InMemoryTripleStore:
    """A dependency-free triple store (best-effort).

    Notes:
    - Intended for tests/dev and hosts without LanceDB installed.
    - Append-only: updates are represented as new assertions.
    - Vector search is optional and stores vectors in-memory only.
    - Thread-safe (0013): one RLock guards add/query, and add() skips rows
      whose assertion_id already exists (store-level id idempotency —
      matches SQLiteTripleStore's INSERT OR IGNORE semantics).
    """

    def __init__(
        self,
        *,
        embedder: Optional[TextEmbedder] = None,
        vector_column: str = "vector",
        embedding_pin: Optional[dict] = None,
    ) -> None:
        self._embedder = embedder
        self._vector_column = str(vector_column or "vector")
        self._rows: list[dict[str, Any]] = []
        self._ids: set[str] = set()
        self._lock = threading.RLock()
        # EMBEDDING PIN (M1) — SQLite parity, in-object storage.
        self._embedding_pin: Optional[dict] = None
        if embedding_pin is not None:
            self._embedding_pin = build_pin(
                embedding_pin.get("model_id"), embedding_pin.get("dimension"),
                source=str(embedding_pin.get("source") or "creation"),
                claimed_by=embedding_pin.get("claimed_by"))
        check_model_compat(self._embedding_pin, self._embedder)

    def embedding_pin(self) -> Optional[dict]:
        """The store's embedding-space pin, or None (pinless — first
        embedded write pins with a labeled #FALLBACK). SQLite parity."""
        with self._lock:
            return dict(self._embedding_pin) if self._embedding_pin else None

    def replace_vectors(
        self, vectors: dict, pin: dict, *,
        expected_row_count: int, embedder: Optional[TextEmbedder] = None,
    ) -> int:
        """ATOMIC embedding-space swap (M1b reembed) — SQLite parity: count
        guard (lease violation refuses, nothing changes), every row's vector
        rewritten (absent = vectorless), pin last, live embedder swapped."""
        clean = {str(k): [float(x) for x in v] for k, v in vectors.items() if v is not None}
        with self._lock:
            if len(self._rows) != int(expected_row_count):
                raise RuntimeError(
                    f"reembed swap refused: store changed mid-pass "
                    f"({len(self._rows)} rows now, {expected_row_count} at scan) — "
                    "the caller's exclusive-writer guarantee did not hold (another writer touched the store); nothing was written"
                )
            for row in self._rows:
                vector = clean.get(str(row.get("assertion_id")))
                if vector is None:
                    row.pop(self._vector_column, None)
                else:
                    row[self._vector_column] = vector
            self._embedding_pin = dict(pin)
            if embedder is not None:
                self._embedder = embedder
        return len(clean)

    def close(self) -> None:
        return None

    def stored_vector(self, assertion_id: str) -> Optional[List[float]]:
        """The persisted embedding for one row, or None (vectorless /
        unknown). Read surface for consolidation's vector bridge signal —
        never used by recall itself (the vector channel queries by cosine)."""
        rid = str(assertion_id or "").strip()
        with self._lock:
            for r in self._rows:
                if r.get("assertion_id") == rid:
                    v = r.get(self._vector_column)
                    return list(v) if isinstance(v, list) else None
        return None

    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]:
        pending: list[TripleAssertion] = [a for a in assertions]
        if not pending:
            return []

        vectors: Optional[dict[int, List[float]]] = None
        if self._embedder is not None:
            # Edge assertions are graph structure, never embedded (realistic
            # fix): embedding "ex:a supports ex:b" wastes embed calls and let
            # edges consume vector fetch slots before rejection.
            embeddable = [(i, _canonical_text(a)) for i, a in enumerate(pending) if not _is_record_edge(a)]
            # Dead embedder degrades to VECTORLESS, labeled (SQLite parity —
            # wave-4b ask 3); wrong-space still aborts hard below.
            embedded = (embed_texts_degradable(
                self._embedder, [t for _, t in embeddable], self.embedding_pin())
                if embeddable else None)
            if embeddable and embedded is not None:
                vectors = {i: v for (i, _), v in zip(embeddable, embedded)}
                # M1 write guard (SQLite parity): dimension must agree with
                # the pin; pinless stores pin here, loudly.
                with self._lock:
                    dim = check_add_dimension(self._embedding_pin, vectors.values())
                    if dim is not None:
                        if self._embedding_pin is None:
                            # claimed_by: unverified embedder-attribute
                            # label (SQLite parity — see sqlite_store.add).
                            pin = build_pin(embedder_model_id(self._embedder), dim,
                                            source="first-write",
                                            claimed_by="embedder-attribute")
                            warn_first_write_pin(pin)
                            self._embedding_pin = pin
                        elif self._embedding_pin.get("dimension") is None:
                            self._embedding_pin = dict(self._embedding_pin, dimension=dim)

        ids: list[str] = []
        with self._lock:
            for i, a in enumerate(pending):
                # Honor caller-supplied ids (deterministic/import flows); default uuid4.
                assertion_id = a.assertion_id or str(uuid.uuid4())
                ids.append(assertion_id)
                if assertion_id in self._ids:
                    continue  # store-level id idempotency (parity with OR IGNORE)
                self._ids.add(assertion_id)
                row: dict[str, Any] = {"assertion_id": assertion_id, "assertion": a}
                if vectors is not None and i in vectors:
                    row[self._vector_column] = vectors[i]
                self._rows.append(row)
        return ids

    def query(self, q: TripleQuery) -> List[TripleAssertion]:
        raw_limit = int(q.limit) if isinstance(q.limit, int) else 100
        limit: Optional[int]
        if raw_limit <= 0:
            limit = None
        else:
            limit = max(1, raw_limit)

        def _match(a: TripleAssertion) -> bool:
            if q.subject and normalize_term(a.subject) != normalize_term(q.subject):
                return False
            if q.predicate and normalize_term(a.predicate) != normalize_term(q.predicate):
                return False
            if q.object and normalize_term(a.object) != normalize_term(q.object):
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

        with self._lock:  # snapshot under the lock; scoring below is lock-free
            rows = [r for r in self._rows if isinstance(r, dict) and isinstance(r.get("assertion"), TripleAssertion)]
        filtered: list[dict[str, Any]] = []
        id_filter = set(q.assertion_ids) if q.assertion_ids else None
        for r in rows:
            a = r["assertion"]
            if id_filter is not None and r.get("assertion_id") not in id_filter:
                continue
            if _match(a):
                filtered.append(r)

        query_vector: Optional[Sequence[float]] = None
        if q.query_vector:
            query_vector = q.query_vector
        elif q.query_text:
            if self._embedder is None:
                raise ValueError("query_text requires a configured embedder (vector search); keyword fallback is disabled")
            try:
                query_vector = self._embedder.embed_texts([q.query_text])[0]
            except (ValueError, RuntimeError) as e:
                # Claimed-vs-served in one line (SQLite parity — see
                # sqlite_store.query).
                annotated = annotate_embed_failure(e, self.embedding_pin())
                if annotated is None:
                    raise
                raise annotated from e
        # M1 read guard (SQLite parity): wrong-space query vectors refuse
        # loudly; the vector channel labels the degradation.
        check_query_dimension(self.embedding_pin(), query_vector)

        if query_vector is not None:
            column = q.vector_column or self._vector_column
            ranked = rank_by_cosine(query_vector, filtered, lambda r: r.get(column),
                                    min_score=q.min_score, limit=limit)

            out: list[TripleAssertion] = []
            for score, r in ranked:
                a = r["assertion"]
                attrs = dict(a.attributes) if isinstance(a.attributes, dict) else {}
                retrieval = attrs.get("_retrieval") if isinstance(attrs.get("_retrieval"), dict) else {}
                retrieval2 = dict(retrieval)
                retrieval2["score"] = float(score)
                retrieval2.setdefault("metric", "cosine")
                attrs["_retrieval"] = retrieval2
                out.append(_result_copy(a, r.get("assertion_id"), attributes=attrs))
            return out

        ordered = sorted(filtered, key=lambda r: r["assertion"].observed_at or "", reverse=(str(q.order).lower() != "asc"))
        sliced = ordered if limit is None else ordered[:limit]
        # Rebuild results (never alias store internals) and attach read-side identity.
        return [_result_copy(r["assertion"], r.get("assertion_id")) for r in sliced]
