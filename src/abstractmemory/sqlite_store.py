from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Iterable, List, Optional

from .models import TripleAssertion
from .store import TripleQuery


SCHEMA_VERSION = 1


class SQLiteTripleStore:
    """SQLite-backed append-only triple store.

    Notes:
    - This is intentionally simple (MVP) and uses only stdlib `sqlite3`.
    - Assertions are append-only. Higher-level policies (retractions, “current truth”)
      are built on top by adding new assertions with timestamps/validity windows.
    """

    def __init__(self, path: str | Path):
        self._path = str(path)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Writes
    # ---------------------------------------------------------------------
    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]:
        rows = []
        ids: List[str] = []
        for a in assertions:
            assertion_id = str(uuid.uuid4())
            ids.append(assertion_id)
            rows.append(
                (
                    assertion_id,
                    a.subject,
                    a.predicate,
                    a.object,
                    a.scope,
                    a.observed_at,
                    a.valid_from,
                    a.valid_until,
                    a.confidence,
                    json.dumps(a.provenance, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(a.attributes, ensure_ascii=False, separators=(",", ":")),
                )
            )

        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO triple_assertions (
                    assertion_id,
                    subject,
                    predicate,
                    object,
                    scope,
                    observed_at,
                    valid_from,
                    valid_until,
                    confidence,
                    provenance_json,
                    attributes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

        return ids

    # ---------------------------------------------------------------------
    # Reads
    # ---------------------------------------------------------------------
    def query(self, q: TripleQuery) -> List[TripleAssertion]:
        where = []
        params: List[object] = []

        if q.subject:
            where.append("subject = ?")
            params.append(q.subject)
        if q.predicate:
            where.append("predicate = ?")
            params.append(q.predicate)
        if q.object:
            where.append("object = ?")
            params.append(q.object)
        if q.scope:
            where.append("scope = ?")
            params.append(q.scope)

        if q.since:
            where.append("observed_at >= ?")
            params.append(q.since)
        if q.until:
            where.append("observed_at <= ?")
            params.append(q.until)

        if q.active_at:
            where.append("(valid_from IS NULL OR valid_from <= ?)")
            where.append("(valid_until IS NULL OR valid_until > ?)")
            params.extend([q.active_at, q.active_at])

        limit = int(q.limit) if isinstance(q.limit, int) else 100
        limit = max(1, min(limit, 10_000))
        order = "ASC" if str(q.order).lower() == "asc" else "DESC"

        sql = "SELECT * FROM triple_assertions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY observed_at {order} LIMIT ?"
        params.append(limit)

        cur = self._conn.execute(sql, params)
        rows = cur.fetchall()
        out: List[TripleAssertion] = []
        for r in rows:
            provenance = _loads_json(r["provenance_json"])
            attributes = _loads_json(r["attributes_json"])
            out.append(
                TripleAssertion(
                    subject=r["subject"],
                    predicate=r["predicate"],
                    object=r["object"],
                    scope=r["scope"],
                    observed_at=r["observed_at"],
                    valid_from=r["valid_from"],
                    valid_until=r["valid_until"],
                    confidence=r["confidence"],
                    provenance=provenance,
                    attributes=attributes,
                )
            )
        return out

    # ---------------------------------------------------------------------
    # Schema
    # ---------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS triple_assertions (
                    assertion_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    valid_from TEXT,
                    valid_until TEXT,
                    confidence REAL,
                    provenance_json TEXT NOT NULL,
                    attributes_json TEXT NOT NULL
                )
                """
            )

            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_subject ON triple_assertions(subject)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_predicate ON triple_assertions(predicate)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_object ON triple_assertions(object)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_scope_time ON triple_assertions(scope, observed_at)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_sp ON triple_assertions(subject, predicate)"
            )

            existing = self._meta_get("schema_version")
            if existing is None:
                self._meta_set("schema_version", str(SCHEMA_VERSION))

    def _meta_get(self, key: str) -> Optional[str]:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def _meta_set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def _loads_json(raw: object) -> dict:
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}

