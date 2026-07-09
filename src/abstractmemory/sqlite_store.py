from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Iterable, List, Optional

from .embeddings import TextEmbedder
from .models import TripleAssertion
from .store import TripleQuery
from .vector_scoring import rank_by_cosine


# Single source of truth for the stored/embedded text (canonical_text.py v2:
# clean record digests); the aliases keep this module's established names and
# the golden parity tests meaningful.
from .canonical_text import canonical_text as _canonical_text  # noqa: E402
from .canonical_text import is_record_edge as _is_record_edge  # noqa: E402


class SQLiteTripleStore:
    """SQLite-backed append-only triple store with native vector support.

    Notes:
    - Uses stdlib `sqlite3` (portable; no daemon).
    - Append-only: there is no update/delete API (see AbstractMemory FAQ).
    - VECTORS (a2a 0003, the entity-home pairing): pass `embedder=` and each
      added assertion's canonical text is embedded and persisted in the SAME
      .sqlite3 file (JSON-encoded `embedding` column; in-place ALTER TABLE
      upgrade for pre-vector homes — old rows stay NULL/vectorless and the
      VECTOR CHANNEL labels that degradation at recall). Mirrors the
      InMemory reference semantics exactly: edge assertions are never
      embedded; `query_text` requires the embedder (no keyword fallback);
      `query_vector` is accepted directly; cosine ranking happens in Python
      over the SQL-filtered candidates (honest v1: linear scan —
      comfortable at entity-home scale; ANN lifts are backlog 0019).

    Concurrency (0013 contract, hardened after the persistence audit):
    ``check_same_thread=False`` + one internal RLock around ALL cursor use, so
    a store constructed on one thread is safe from gateway worker threads.
    WAL + busy_timeout=5000 + synchronous=NORMAL match the journal backend.
    add() is ONE explicit transaction (BEGIN IMMEDIATE .. COMMIT) using
    INSERT OR IGNORE: existing assertion_id rows are skipped — store-level id
    idempotency — and a failing batch rolls back atomically, so partial rows
    can never leak into a later unrelated commit (audit s4_leak_commit).
    Embedding happens BEFORE the transaction (InMemory parity): an embedder
    failure aborts the add with ZERO rows written — it never corrupts or
    half-writes the batch.
    """

    def __init__(
        self, path: Path, *, table_name: str = "triples",
        embedder: Optional[TextEmbedder] = None,
    ) -> None:
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._table = str(table_name or "triples").strip() or "triples"
        self._embedder = embedder

        self._lock = threading.RLock()
        # isolation_level=None -> autocommit + explicit BEGIN/COMMIT in add():
        # Python's implicit-transaction mode is what allowed failed batches to
        # leave uncommitted rows that a LATER unrelated commit() flushed.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._configure_pragmas()
        self._ensure_schema()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def _configure_pragmas(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA synchronous=NORMAL")

    def _ensure_schema(self) -> None:
        with self._lock:
            self._create_schema()

    def _create_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
              assertion_id TEXT PRIMARY KEY,
              subject TEXT NOT NULL,
              predicate TEXT NOT NULL,
              object TEXT NOT NULL,
              scope TEXT NOT NULL,
              owner_id TEXT,
              observed_at TEXT NOT NULL,
              valid_from TEXT,
              valid_until TEXT,
              confidence REAL,
              provenance_json TEXT,
              attributes_json TEXT,
              text TEXT
            )
            """
        )
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self._table}_spo ON {self._table}(subject, predicate, object)")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self._table}_scope_owner ON {self._table}(scope, owner_id)")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self._table}_observed ON {self._table}(observed_at)")
        # IN-PLACE UPGRADE (a2a 0003: the one-file home stands): pre-vector
        # homes gain the embedding column on open; their existing rows stay
        # NULL (vectorless) — the vector channel labels that at recall.
        columns = {r[1] for r in cur.execute(f"PRAGMA table_info({self._table})").fetchall()}
        if "embedding" not in columns:
            cur.execute(f"ALTER TABLE {self._table} ADD COLUMN embedding TEXT")

    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]:
        pending: List[TripleAssertion] = [a for a in assertions]
        if not pending:
            return []

        # Embed BEFORE the transaction (InMemory parity): edge assertions are
        # graph structure, never embedded; an embedder failure aborts the add
        # with zero rows written (never a half-embedded committed batch).
        vectors: Optional[dict[int, List[float]]] = None
        if self._embedder is not None:
            embeddable = [(i, _canonical_text(a)) for i, a in enumerate(pending) if not _is_record_edge(a)]
            if embeddable:
                embedded = self._embedder.embed_texts([t for _, t in embeddable])
                vectors = {i: v for (i, _), v in zip(embeddable, embedded)}

        ids: List[str] = []
        rows: List[tuple] = []

        for i, a in enumerate(pending):
            # Honor caller-supplied ids (deterministic/import flows); default uuid4.
            assertion_id = a.assertion_id or str(uuid.uuid4())
            ids.append(assertion_id)
            vector = vectors.get(i) if vectors is not None else None
            rows.append(
                (
                    assertion_id,
                    a.subject,
                    a.predicate,
                    a.object,
                    a.scope,
                    a.owner_id,
                    a.observed_at,
                    a.valid_from,
                    a.valid_until,
                    a.confidence,
                    json.dumps(a.provenance, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(a.attributes, ensure_ascii=False, separators=(",", ":")),
                    _canonical_text(a),
                    json.dumps([float(x) for x in vector], separators=(",", ":")) if vector is not None else None,
                )
            )

        # ONE atomic batch (audit s4_leak_commit): BEGIN IMMEDIATE takes the
        # write lock up front; a failure rolls back EVERY row of this batch,
        # so nothing can linger uncommitted and flush at a later unrelated
        # commit. INSERT OR IGNORE skips rows whose assertion_id already
        # exists (store-level id idempotency — same supplied-id-wins rule as
        # the journal); ids are returned for ALL requested rows as before.
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.executemany(
                    f"""
                    INSERT OR IGNORE INTO {self._table} (
                      assertion_id, subject, predicate, object, scope, owner_id,
                      observed_at, valid_from, valid_until, confidence,
                      provenance_json, attributes_json, text, embedding
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
        return ids

    def query(self, q: TripleQuery) -> List[TripleAssertion]:
        # Vector-query resolution mirrors InMemory exactly: precomputed
        # query_vector wins; query_text embeds via the configured embedder
        # (no keyword fallback, same error text).
        query_vector: Optional[List[float]] = None
        if q.query_vector:
            query_vector = [float(x) for x in q.query_vector]
        elif q.query_text:
            if self._embedder is None:
                raise ValueError("query_text requires a configured embedder (vector search); keyword fallback is disabled")
            query_vector = [float(x) for x in self._embedder.embed_texts([q.query_text])[0]]

        raw_limit = int(q.limit) if isinstance(q.limit, int) else 100
        limit: Optional[int]
        if raw_limit <= 0:
            limit = None
        else:
            limit = max(1, raw_limit)

        parts: List[str] = []
        params: List[Any] = []

        if q.assertion_ids:
            placeholders = ", ".join("?" for _ in q.assertion_ids)
            parts.append(f"assertion_id IN ({placeholders})")
            params.extend(q.assertion_ids)
        if q.subject:
            parts.append("subject = ?")
            params.append(q.subject)
        if q.predicate:
            parts.append("predicate = ?")
            params.append(q.predicate)
        if q.object:
            parts.append("object = ?")
            params.append(q.object)
        if q.scope:
            parts.append("scope = ?")
            params.append(q.scope)
        if q.owner_id:
            parts.append("COALESCE(owner_id, '') = ?")
            params.append(q.owner_id)
        if q.since:
            parts.append("observed_at >= ?")
            params.append(q.since)
        if q.until:
            parts.append("observed_at <= ?")
            params.append(q.until)
        if q.active_at:
            # valid_until is exclusive: valid_until > active_at
            parts.append("(valid_from IS NULL OR valid_from <= ?)")
            params.append(q.active_at)
            parts.append("(valid_until IS NULL OR valid_until > ?)")
            params.append(q.active_at)

        where = " AND ".join(parts)
        sql = f"SELECT * FROM {self._table}"
        if where:
            sql += f" WHERE {where}"

        if query_vector is not None:
            # Cosine ranking in Python over ALL SQL-filtered candidates
            # (InMemory parity: score first, THEN limit — honest v1 linear
            # scan; ANN lifts are backlog 0019).
            with self._lock:
                rows = self._conn.cursor().execute(sql, params).fetchall()
            ranked = rank_by_cosine(
                query_vector, rows, lambda r: self._row_vector(r),
                min_score=q.min_score, limit=limit,
            )
            out: List[TripleAssertion] = []
            for score, r in ranked:
                a = self._row_to_assertion(r)
                attrs = dict(a.attributes) if isinstance(a.attributes, dict) else {}
                retrieval = attrs.get("_retrieval") if isinstance(attrs.get("_retrieval"), dict) else {}
                retrieval2 = dict(retrieval)
                retrieval2["score"] = float(score)
                retrieval2.setdefault("metric", "cosine")
                attrs["_retrieval"] = retrieval2
                a.attributes.clear()
                a.attributes.update(attrs)
                out.append(a)
            return out

        order_sql = "ASC" if str(q.order or "").strip().lower() == "asc" else "DESC"
        # Deterministic tie-breaker on assertion_id.
        sql += f" ORDER BY observed_at {order_sql}, assertion_id {order_sql}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))

        with self._lock:
            rows = self._conn.cursor().execute(sql, params).fetchall()
        return [self._row_to_assertion(r) for r in rows]

    def stored_vector(self, assertion_id: str) -> Optional[List[float]]:
        """The persisted embedding for one row, or None (vectorless /
        unknown). Read surface for consolidation's vector bridge signal —
        never used by recall itself (the vector channel queries by cosine)."""
        rid = str(assertion_id or "").strip()
        if not rid:
            return None
        with self._lock:
            row = self._conn.cursor().execute(
                f"SELECT embedding FROM {self._table} WHERE assertion_id = ?", (rid,)
            ).fetchone()
        return self._row_vector(row) if row is not None else None

    @staticmethod
    def _row_vector(r: sqlite3.Row) -> Any:
        raw = r["embedding"]
        if not raw:
            return None  # vectorless row: skipped by ranking; channel labels it
        try:
            vector = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return vector if isinstance(vector, list) else None

    @staticmethod
    def _row_to_assertion(r: sqlite3.Row) -> TripleAssertion:
        try:
            prov = json.loads(r["provenance_json"]) if r["provenance_json"] else {}
        except Exception:
            prov = {}
        try:
            attrs = json.loads(r["attributes_json"]) if r["attributes_json"] else {}
        except Exception:
            attrs = {}
        return TripleAssertion(
            subject=str(r["subject"] or ""),
            predicate=str(r["predicate"] or ""),
            object=str(r["object"] or ""),
            scope=str(r["scope"] or "run"),
            owner_id=str(r["owner_id"] or "").strip() or None,
            observed_at=str(r["observed_at"] or ""),
            valid_from=str(r["valid_from"] or "").strip() or None,
            valid_until=str(r["valid_until"] or "").strip() or None,
            confidence=float(r["confidence"]) if r["confidence"] is not None else None,
            provenance=dict(prov) if isinstance(prov, dict) else {},
            attributes=dict(attrs) if isinstance(attrs, dict) else {},
            assertion_id=str(r["assertion_id"] or "").strip() or None,
        )
