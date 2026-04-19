from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable, List, Optional

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
            ctx2 = ctx2[:400] + "…"  #[WARNING:TRUNCATION] bounded canonical-text context preview (full context remains in attributes)
        parts.append(f"context: {ctx2}")

    return "\n".join(parts)


class SQLiteTripleStore:
    """SQLite-backed append-only triple store (structured queries only).

    Notes:
    - Uses stdlib `sqlite3` (portable; no daemon).
    - Append-only: there is no update/delete API (see AbstractMemory FAQ).
    - Semantic/vector queries are intentionally unsupported in v0 for this backend.
    """

    def __init__(self, path: Path, *, table_name: str = "triples") -> None:
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._table = str(table_name or "triples").strip() or "triples"

        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def _ensure_schema(self) -> None:
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
        self._conn.commit()

    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]:
        pending: List[TripleAssertion] = [a for a in assertions]
        if not pending:
            return []

        ids: List[str] = []
        rows: List[tuple] = []

        for a in pending:
            assertion_id = str(uuid.uuid4())
            ids.append(assertion_id)
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
                )
            )

        cur = self._conn.cursor()
        cur.executemany(
            f"""
            INSERT INTO {self._table} (
              assertion_id, subject, predicate, object, scope, owner_id,
              observed_at, valid_from, valid_until, confidence,
              provenance_json, attributes_json, text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return ids

    def query(self, q: TripleQuery) -> List[TripleAssertion]:
        if q.query_text or q.query_vector:
            raise ValueError("SQLiteTripleStore does not support semantic/vector queries (no keyword fallback)")

        raw_limit = int(q.limit) if isinstance(q.limit, int) else 100
        limit: Optional[int]
        if raw_limit <= 0:
            limit = None
        else:
            limit = max(1, raw_limit)

        parts: List[str] = []
        params: List[Any] = []

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
        order = "asc" if str(q.order or "").strip().lower() == "asc" else "desc"
        order_sql = "ASC" if order == "asc" else "DESC"

        sql = f"SELECT * FROM {self._table}"
        if where:
            sql += f" WHERE {where}"
        # Deterministic tie-breaker on assertion_id.
        sql += f" ORDER BY observed_at {order_sql}, assertion_id {order_sql}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))

        cur = self._conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

        out: List[TripleAssertion] = []
        for r in rows:
            try:
                prov = json.loads(r["provenance_json"]) if r["provenance_json"] else {}
            except Exception:
                prov = {}
            try:
                attrs = json.loads(r["attributes_json"]) if r["attributes_json"] else {}
            except Exception:
                attrs = {}
            out.append(
                TripleAssertion(
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
                )
            )
        return out
