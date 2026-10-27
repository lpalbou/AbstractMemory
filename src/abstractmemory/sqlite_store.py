from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
import warnings
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

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
from .models import TripleAssertion
from .store import TripleQuery
from .vector_matrix import (
    ID_FETCH_CHUNK,
    SYNC_FETCH_ROWS,
    VECTOR_ENGINE_NUMPY,
    VECTOR_ENGINE_PYTHON,
    VECTOR_UPGRADE_BATCH,
    VectorMatrix,
    _Unrepresentable,
    decode_vector,
    encode_vector,
    numpy_module,
)
from .vector_scoring import rank_by_cosine


# Single source of truth for the stored/embedded text (canonical_text.py v2:
# clean record digests); the aliases keep this module's established names and
# the golden parity tests meaningful.
from .canonical_text import canonical_text as _canonical_text  # noqa: E402
from .canonical_text import is_record_edge as _is_record_edge  # noqa: E402

# The table name is interpolated into SQL identifiers, which cannot be bound
# as parameters — so it is validated at the door, exactly as SQLiteJournal
# validates its table_prefix. Same rule, same reason, both backends.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _checked_table(table_name: Optional[str]) -> str:
    table = str(table_name or "triples").strip() or "triples"
    if not _IDENTIFIER_RE.match(table):
        raise ValueError(
            f"table_name must match [A-Za-z_][A-Za-z0-9_]* (got {table_name!r}); "
            "it is interpolated into SQL identifiers"
        )
    return table


# COLUMN PROJECTION (backlog 0058): the columns `_row_to_assertion` reads.
# Structured reads never fetch `embedding` (the stored vector: several KB per
# row, the bulk of every scan when it rode along with `SELECT *`) nor `text`
# (the canonical text, which only the FTS index and the embedder consume).
# Vectors are read only by semantic queries and the explicit vector reads
# (`stored_vector`, the vector matrix cache).
# Sentinel of `_rank_in_snapshot`: the matrix named a row the table lacks.
_STALE = object()

_ASSERTION_COLUMNS = (
    "assertion_id", "subject", "predicate", "object", "scope", "owner_id",
    "observed_at", "valid_from", "valid_until", "confidence",
    "provenance_json", "attributes_json",
)


class SQLiteTripleStore:
    """SQLite-backed append-only triple store with native vector support.

    Notes:
    - Uses stdlib `sqlite3` (portable; no daemon).
    - Append-only: there is no update/delete API (see AbstractMemory FAQ),
      except `close_assertion`, which only closes an open validity window.
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
        embedding_pin: Optional[dict] = None,
    ) -> None:
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._table = _checked_table(table_name)
        self._embedder = embedder

        self._lock = threading.RLock()
        # Vector matrix cache (0058): built at the first semantic query,
        # appended from new rows, dropped when the vectors are rewritten.
        self._vectors: Optional[VectorMatrix] = None
        self._vector_fallback_warned = False
        # isolation_level=None -> autocommit + explicit BEGIN/COMMIT in add():
        # Python's implicit-transaction mode is what allowed failed batches to
        # leave uncommitted rows that a LATER unrelated commit() flushed.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._configure_pragmas()
        self._ensure_schema()
        # EMBEDDING PIN (M1, one store = one embedding space): a supplied
        # creation pin is persisted on a pinless store and must AGREE with an
        # existing one; a known embedder identity must agree with the pin.
        # Both mismatches refuse loudly — no silent mixing of spaces.
        stored = self.embedding_pin()
        if embedding_pin is not None:
            declared = build_pin(
                embedding_pin.get("model_id"), embedding_pin.get("dimension"),
                source=str(embedding_pin.get("source") or "creation"),
                claimed_by=embedding_pin.get("claimed_by"))
            if stored is None:
                self._write_pin(declared)
                stored = declared
            else:
                for field in ("model_id", "dimension"):
                    a, b = stored.get(field), declared.get(field)
                    if a is not None and b is not None and a != b:
                        raise ValueError(
                            f"embedding-space mismatch: store is pinned to "
                            f"{field}={a!r} but the declared pin says {b!r} — "
                            "no silent mixing of embedding spaces (reembed is "
                            "the sanctioned migration)"
                        )
        check_model_compat(stored, self._embedder)

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
        # INCOMING-EDGE WALKS (diary---verbatims item E, 2026-07-19): the
        # trail reads (read_memory connections, DIARY_READ born-from,
        # gateway's door trail) query by OBJECT — the spo index cannot
        # serve an object-only filter, so every walk was a full table
        # scan (measured 4.6ms at 12k rows on the live home; O(life) —
        # a multi-year store pays seconds). One covering index; created
        # on open, so existing homes gain it at their next process start.
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self._table}_object ON {self._table}(object, predicate)")
        # PARTITION READS IN ORDER (backlog 0058): "latest N in (scope,
        # owner)", the as-of window and the per-pair full scans read one
        # partition newest-first. (scope, owner_id) alone forced a temp
        # B-tree sort of the WHOLE partition (588 ms for latest-100 at 50k
        # rows); with observed_at + the assertion_id tie-breaker in the key
        # the partition is walked in query order and LIMIT stops the walk.
        # Created on open: existing homes gain it at their next process
        # start (no row is rewritten).
        cur.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self._table}_scope_owner_observed "
            f"ON {self._table}(scope, owner_id, observed_at, assertion_id)")
        # IN-PLACE UPGRADE (a2a 0003: the one-file home stands): pre-vector
        # homes gain the embedding column on open; their existing rows stay
        # NULL (vectorless) — the vector channel labels that at recall.
        columns = {r[1] for r in cur.execute(f"PRAGMA table_info({self._table})").fetchall()}
        if "embedding" not in columns:
            # Declared BLOB since 0058 (float32 little-endian); homes that
            # gained the column earlier declare TEXT, which stores a BLOB
            # unchanged (SQLite affinity only converts numbers).
            cur.execute(f"ALTER TABLE {self._table} ADD COLUMN embedding BLOB")
        # Store metadata sidecar (M1): the embedding pin lives IN the same
        # file — the one-file home invariant covers the space identity too.
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table}_meta "
            "(key TEXT PRIMARY KEY, value TEXT)"
        )
        # KEYWORD INDEX (0019's FTS5 half): an external-content FTS5 table
        # over the canonical `text` column, maintained append-only via a
        # high-water rowid cursor (`fts_high_water` in the meta sidecar).
        # Capability-DETECTED: a Python/sqlite build without FTS5 leaves the
        # store fully functional — the keyword channel keeps its labeled v1
        # scan (same posture as vectorless rows). Backfill runs at open for
        # pre-FTS homes (in-place-upgrade precedent, same as the embedding
        # column above); the cursor makes it idempotent and O(new rows).
        try:
            cur.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {self._table}_fts "
                f"USING fts5(text, content={self._table}, content_rowid=rowid)"
            )
            self._fts_supported = True
        except sqlite3.OperationalError:
            self._fts_supported = False
        if self._fts_supported:
            cur.execute("BEGIN IMMEDIATE")
            try:
                self._sync_fts_index(cur)
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise
        self._upgrade_vector_encoding(cur)

    def _upgrade_vector_encoding(self, cur: sqlite3.Cursor) -> None:
        """IN-PLACE UPGRADE (0058): rewrite JSON-text vectors as float32
        BLOBs, above the `vector_blob_high_water` rowid cursor of the meta
        sidecar (the FTS backfill pattern): idempotent, resumable, O(rows
        written since the last open), `VECTOR_UPGRADE_BATCH` rows per
        transaction. Unreadable or non-numeric JSON, and values float32
        cannot hold, stay as they are (the reference scan reads them as
        before). A batch that rewrote rows bumps `vector_generation` in the
        same transaction, so a matrix another handle built from the JSON
        values rebuilds. The file does not shrink until a VACUUM; new rows
        are written as BLOBs by `add`."""
        row = cur.execute(
            f"SELECT value FROM {self._table}_meta WHERE key = 'vector_blob_high_water'"
        ).fetchone()
        high_water = int(row[0]) if row and str(row[0]).lstrip("-").isdigit() else 0
        top = cur.execute(f"SELECT MAX(rowid) FROM {self._table}").fetchone()[0]
        if top is None or int(top) <= high_water:
            return
        top = int(top)
        size = int(VECTOR_UPGRADE_BATCH)
        while high_water < top:
            cur.execute("BEGIN IMMEDIATE")
            try:
                batch = cur.execute(
                    f"SELECT rowid, embedding FROM {self._table} "
                    "WHERE rowid > ? AND rowid <= ? AND typeof(embedding) = 'text' "
                    "ORDER BY rowid LIMIT ?", (high_water, top, size),
                ).fetchall()
                updates = []
                for rowid, raw in batch:
                    vector = decode_vector(raw)
                    if vector is None:
                        continue
                    try:
                        updates.append((encode_vector(vector), rowid))
                    except (TypeError, ValueError, OverflowError):
                        continue  # non-numeric / beyond float32: left untouched
                if updates:
                    cur.executemany(
                        f"UPDATE {self._table} SET embedding = ? WHERE rowid = ?", updates)
                    self._bump_vector_generation(cur)
                high_water = int(batch[-1][0]) if len(batch) == size else top
                cur.execute(
                    f"INSERT OR REPLACE INTO {self._table}_meta (key, value) "
                    "VALUES ('vector_blob_high_water', ?)", (str(high_water),))
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise

    def _bump_vector_generation(self, cur: sqlite3.Cursor) -> None:
        """Mark every stored vector as rewritten (caller owns the
        transaction): each handle's matrix sees a new token and rebuilds."""
        cur.execute(
            f"INSERT OR REPLACE INTO {self._table}_meta (key, value) "
            "VALUES ('vector_generation', ?)", (str(uuid.uuid4()),))

    def _sync_fts_index(self, cur: sqlite3.Cursor) -> None:
        """Index rows above the high-water rowid (caller owns the
        transaction). Append-only makes this exact: new rows always carry a
        higher rowid, and INSERT OR IGNORE duplicates never re-insert, so
        the cursor can never skip or double-index a row. Edge/bookkeeping
        assertions are excluded — parity with the embedding rule (graph
        structure is not prose)."""
        if not getattr(self, "_fts_supported", False):
            return
        row = cur.execute(
            f"SELECT value FROM {self._table}_meta WHERE key = 'fts_high_water'"
        ).fetchone()
        high_water = int(row[0]) if row and str(row[0]).lstrip("-").isdigit() else 0
        cur.execute(
            f"INSERT INTO {self._table}_fts (rowid, text) "
            f"SELECT rowid, COALESCE(text, '') FROM {self._table} "
            "WHERE rowid > ? "
            "AND json_extract(COALESCE(attributes_json, '{}'), '$.record_edge') IS NULL "
            "AND json_extract(COALESCE(attributes_json, '{}'), '$.bookkeeping') IS NULL",
            (high_water,),
        )
        new_high = cur.execute(
            f"SELECT COALESCE(MAX(rowid), ?) FROM {self._table}", (high_water,)
        ).fetchone()[0]
        cur.execute(
            f"INSERT OR REPLACE INTO {self._table}_meta (key, value) "
            "VALUES ('fts_high_water', ?)", (str(int(new_high)),))

    @property
    def supports_keyword_search(self) -> bool:
        """True when the FTS5 keyword index is available on this store —
        the keyword channel's discovery capability check (0019)."""
        return bool(getattr(self, "_fts_supported", False))

    def query_keywords(
        self, tokens: Sequence[str], *, scope: str,
        owner_id: Optional[str] = None, limit: int = 32,
    ) -> List[TripleAssertion]:
        """Keyword DISCOVERY over the FTS5 index: rows in (scope, owner)
        matching ANY of the tokens, best-match first (BM25). Pure read.
        Tokens are matched as quoted terms (the caller tokenizes — one
        tokenizer for scan and discovery keeps scoring consistent). Raises
        if the store lacks FTS5 — callers gate on supports_keyword_search."""
        if not self.supports_keyword_search:
            raise ValueError(
                "SQLiteTripleStore: FTS5 keyword index unavailable on this "
                "build — gate on supports_keyword_search before calling"
            )
        terms = [str(t).strip().replace('"', "") for t in tokens]
        terms = [t for t in terms if t]
        if not terms or int(limit) <= 0:
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        owner_clause = "AND t.owner_id = ?" if owner_id is not None else "AND t.owner_id IS NULL"
        params: List[Any] = [match, str(scope)]
        if owner_id is not None:
            params.append(str(owner_id))
        params.append(int(limit))
        with self._lock:
            rows = self._conn.cursor().execute(
                f"SELECT {', '.join('t.' + c for c in _ASSERTION_COLUMNS)} FROM {self._table}_fts f "
                f"JOIN {self._table} t ON t.rowid = f.rowid "
                f"WHERE {self._table}_fts MATCH ? AND t.scope = ? {owner_clause} "
                f"ORDER BY bm25({self._table}_fts), t.rowid DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_assertion(r) for r in rows]

    def embedding_pin(self) -> Optional[dict]:
        """The store's embedding-space pin `{model_id, dimension, source,
        pinned_at}`, or None (legacy pinless store — first embedded write
        pins with a labeled #FALLBACK)."""
        with self._lock:
            row = self._conn.cursor().execute(
                f"SELECT value FROM {self._table}_meta WHERE key = 'embedding_pin'"
            ).fetchone()
        if row is None:
            return None
        try:
            pin = json.loads(row["value"])
        except (TypeError, ValueError):
            return None
        return pin if isinstance(pin, dict) else None

    def meta_json(self, key: str) -> Optional[Any]:
        """JSON value of one `<table>_meta` key, or None (absent/corrupt).
        The generic read behind operator health surfaces (mind_mass_report
        reads the doctoring wave's 'compaction' history through it) — the
        embedding pin keeps its dedicated, validating accessor above."""
        with self._lock:
            row = self._conn.cursor().execute(
                f"SELECT value FROM {self._table}_meta WHERE key = ?", (str(key),)
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["value"])
        except (TypeError, ValueError):
            return None

    def _write_pin(self, pin: dict, cursor: Optional[sqlite3.Cursor] = None) -> None:
        payload = json.dumps(pin, ensure_ascii=False, separators=(",", ":"))
        if cursor is not None:  # caller owns the transaction (atomic swaps)
            cursor.execute(
                f"INSERT OR REPLACE INTO {self._table}_meta (key, value) "
                "VALUES ('embedding_pin', ?)", (payload,))
            return
        with self._lock:
            self._conn.cursor().execute(
                f"INSERT OR REPLACE INTO {self._table}_meta (key, value) "
                "VALUES ('embedding_pin', ?)", (payload,))

    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]:
        pending: List[TripleAssertion] = [a for a in assertions]
        if not pending:
            return []

        # Embed BEFORE the transaction (InMemory parity): edge assertions are
        # graph structure, never embedded. A DEAD embedder degrades the batch
        # to VECTORLESS with one loud #FALLBACK (wave-4b ask 3 — formation
        # amnesia on an embedder outage was worse than the vectorless row);
        # wrong-space vectors still abort HARD below (corruption, never
        # degradable).
        vectors: Optional[dict[int, List[float]]] = None
        if self._embedder is not None:
            embeddable = [(i, _canonical_text(a)) for i, a in enumerate(pending) if not _is_record_edge(a)]
            if embeddable:
                embedded = embed_texts_degradable(
                    self._embedder, [t for _, t in embeddable], self.embedding_pin())
            else:
                embedded = None
            if embeddable and embedded is not None:
                vectors = {i: v for (i, _), v in zip(embeddable, embedded)}
                # M1 write guard: dimension must agree with the pin (abort =
                # zero rows). Pinless legacy stores pin here, loudly; a
                # creation pin missing only its dimension gets it filled.
                pin = self.embedding_pin()
                dim = check_add_dimension(pin, vectors.values())
                if dim is not None:
                    if pin is None:
                        # claimed_by: the label is read off the embedder
                        # object, never verified against the serving
                        # endpoint — consumers must treat it as a CLAIM
                        # (2026-07-11: a first-write pin recorded a label
                        # the server never recognized).
                        pin = build_pin(embedder_model_id(self._embedder), dim,
                                        source="first-write",
                                        claimed_by="embedder-attribute")
                        warn_first_write_pin(pin)
                        self._write_pin(pin)
                    elif pin.get("dimension") is None:
                        pin = dict(pin, dimension=dim)
                        self._write_pin(pin)

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
                    encode_vector(vector) if vector is not None else None,
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
                # Keyword index rides the SAME transaction: a rolled-back
                # batch indexes nothing; the high-water cursor makes the
                # sync exact under OR IGNORE dedup (skipped rows sit below
                # the cursor already).
                self._sync_fts_index(cur)
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
            if self._vectors is not None:
                # Append the committed rows to the matrix (O(new rows)). A
                # failure here must not report the committed add as failed:
                # the cache is dropped and the next semantic query rebuilds.
                try:
                    self._synced_vectors()
                except Exception:
                    self._vectors = None
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
            try:
                query_vector = [float(x) for x in self._embedder.embed_texts([q.query_text])[0]]
            except (ValueError, RuntimeError) as e:
                # Surface claimed-vs-served in ONE line (2026-07-11): the
                # server error names the REQUESTED model; append the store's
                # pinned identity so the operator sees the mismatch here.
                annotated = annotate_embed_failure(e, self.embedding_pin())
                if annotated is None:
                    raise
                raise annotated from e
        # M1 read guard: a wrong-space query vector refuses loudly here; the
        # vector CHANNEL converts this into its labeled #FALLBACK, so recall
        # degrades to exact/keyword instead of serving cross-space cosine.
        check_query_dimension(self.embedding_pin(), query_vector)

        raw_limit = int(q.limit) if isinstance(q.limit, int) else 100
        limit: Optional[int]
        if raw_limit <= 0:
            limit = None
        else:
            limit = max(1, raw_limit)

        if query_vector is not None:
            # Cosine over ALL filtered candidates, THEN limit (InMemory
            # parity). Served by the vector matrix when numpy is importable
            # (0058); otherwise, or when the matrix cannot represent the
            # stored vectors exactly, by the reference Python scan (labelled
            # once with a #FALLBACK warning). Same results either way.
            with self._lock:
                ranked = self._rank_with_matrix(q, query_vector, limit)
            if ranked is None:
                where, params = self._where_clause(q)
                sql = f"SELECT {', '.join(_ASSERTION_COLUMNS)}, embedding FROM {self._table}"
                if where:
                    sql += f" WHERE {where}"
                sql += " ORDER BY rowid"  # ties keep rowid order, like the matrix
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

        sql, params = self._structured_sql(q, limit)
        with self._lock:
            rows = self._conn.cursor().execute(sql, params).fetchall()
        return [self._row_to_assertion(r) for r in rows]

    def _where_clause(self, q: TripleQuery) -> Tuple[str, List[Any]]:
        """The WHERE of a query (filters only; no ordering, no limit)."""
        parts: List[str] = []
        params: List[Any] = []
        # INDEX CHOICE (backlog 0058). An id / subject / object filter is the
        # selective anchor: its own index (pk, spo, object) finds a handful
        # of rows and scope/owner are checked per row — the unary `+` keeps
        # the planner from preferring the (scope, owner) index, which a
        # one-partition home matches entirely (34 ms per subject read at
        # 50k rows). Without an anchor, scope/owner ARE the index key.
        anchored = bool(q.assertion_ids or q.subject or q.object)
        col = "+" if anchored else ""

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
            parts.append(f"{col}scope = ?")
            params.append(q.scope)
        if q.owner_id:
            # Plain equality, never COALESCE(owner_id, '') = ?: a function of
            # the column cannot use any index on owner_id. Same rows: the
            # filter only applies to a NON-EMPTY owner (TripleQuery maps ''
            # to None = no owner filter), and a NULL or '' stored owner never
            # equals a non-empty one under either form.
            parts.append(f"{col}owner_id = ?")
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
        return " AND ".join(parts), params

    def _structured_sql(self, q: TripleQuery, limit: Optional[int]) -> Tuple[str, List[Any]]:
        """The non-semantic read: filters, observed_at order with the
        assertion_id tie-breaker, optional LIMIT."""
        where, params = self._where_clause(q)
        sql = f"SELECT {', '.join(_ASSERTION_COLUMNS)} FROM {self._table}"
        if where:
            sql += f" WHERE {where}"
        order_sql = "ASC" if str(q.order or "").strip().lower() == "asc" else "DESC"
        # Deterministic tie-breaker on assertion_id.
        sql += f" ORDER BY observed_at {order_sql}, assertion_id {order_sql}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return sql, params

    @property
    def vector_engine(self) -> str:
        """Which path serves semantic queries: `"numpy-matrix-cache"`, or the
        labelled `"python-linear-scan"` (numpy not importable, or the stored
        vectors include one the matrix cannot score exactly). Before the
        first semantic query of a handle the matrix is not built yet and the
        answer is `"numpy-matrix-cache"` whenever numpy is importable; the
        build itself may still find an unrepresentable vector (it then warns
        with `#FALLBACK` and this property turns to the scan)."""
        if numpy_module() is None:
            return VECTOR_ENGINE_PYTHON
        matrix = self._vectors
        return VECTOR_ENGINE_NUMPY if matrix is None or matrix.exact else VECTOR_ENGINE_PYTHON

    def _warn_python_path(self, reason: str) -> None:
        """The labelled fallback: once per store handle (the scan answers
        every later query the same way, only slower)."""
        if self._vector_fallback_warned:
            return
        self._vector_fallback_warned = True
        warnings.warn(
            f"#FALLBACK: SQLite vector search uses the Python linear scan: {reason}",
            RuntimeWarning, stacklevel=4)

    def _vector_token(self, cur: sqlite3.Cursor) -> Tuple[Any, ...]:
        """Identity of the stored vector space: the embedding pin plus the
        `vector_generation` that every whole-store rewrite bumps."""
        return tuple(
            (str(k), str(v)) for k, v in cur.execute(
                f"SELECT key, value FROM {self._table}_meta "
                "WHERE key IN ('embedding_pin', 'vector_generation') ORDER BY key"
            ).fetchall())

    def _synced_vectors(self) -> Optional[VectorMatrix]:
        """The vector matrix brought up to date (caller holds the lock and,
        for a consistent snapshot, a read transaction), or None when the
        Python scan must serve. Rebuilt from a scan only when absent or when
        the vector space changed (`vector_generation` or the embedding pin,
        written by `replace_vectors` and the in-place upgrade in any
        process); otherwise only the rows above its rowid high-water are
        read."""
        if numpy_module() is None:
            self._warn_python_path(
                "numpy is not importable (install abstractmemory[fast] for the matrix cache)")
            return None
        cur = self._conn.cursor()
        token = self._vector_token(cur)
        matrix = self._vectors
        if matrix is None or matrix.token != token:
            matrix = VectorMatrix(token)
            self._vectors = matrix
        top = cur.execute(f"SELECT MAX(rowid) FROM {self._table}").fetchone()[0]
        if top is not None and int(top) > matrix.high_water:
            rows = cur.execute(
                f"SELECT rowid, assertion_id, scope, owner_id, embedding FROM {self._table} "
                "WHERE rowid > ? AND rowid <= ? AND embedding IS NOT NULL ORDER BY rowid",
                (matrix.high_water, int(top)))
            while True:
                chunk = rows.fetchmany(SYNC_FETCH_ROWS)
                if not chunk:
                    break
                matrix.append(tuple(r) for r in chunk)
            matrix.high_water = max(matrix.high_water, int(top))
        if not matrix.exact:
            self._warn_python_path(
                f"the store holds a vector the float32 matrix cannot score exactly ({matrix.inexact_reason})")
            return None
        return matrix

    def _rank_with_matrix(
        self, q: TripleQuery, query_vector: List[float], limit: Optional[int],
    ) -> Optional[List[Tuple[float, sqlite3.Row]]]:
        """`(score, row)` best first from the matrix (caller holds the lock),
        or None when the Python scan must answer. Sync, candidate filter,
        ranking and the row read share ONE read transaction (one snapshot:
        a concurrent writer cannot slip rows or a new vector space in
        between)."""
        for attempt in (0, 1):
            cur = self._conn.cursor()
            cur.execute("BEGIN")
            try:
                ranked = self._rank_in_snapshot(cur, q, query_vector, limit)
            finally:
                cur.execute("COMMIT")
            if ranked is not _STALE:
                return ranked
            # The matrix names a row the table no longer has (the file was
            # rewritten under this handle): rebuild once from the table.
            self._vectors = None
        self._warn_python_path("the vector matrix disagrees with the table after a rebuild")
        return None

    def _rank_in_snapshot(
        self, cur: sqlite3.Cursor, q: TripleQuery, query_vector: List[float], limit: Optional[int],
    ) -> Any:
        matrix = self._synced_vectors()
        if matrix is None:
            return None
        partition_only = not (q.assertion_ids or q.subject or q.predicate or q.object
                              or q.since or q.until or q.active_at)
        if partition_only:
            # The vector channel's shape: (scope, owner) is a mask, no SQL.
            positions = matrix.partition(q.scope or None, q.owner_id or None)
        else:
            where, params = self._where_clause(q)
            ids = [r[0] for r in cur.execute(
                f"SELECT assertion_id FROM {self._table} WHERE {where} AND embedding IS NOT NULL",
                params).fetchall()]
            positions = matrix.positions_of(ids)
        try:
            scored = matrix.rank(query_vector, positions, min_score=q.min_score, limit=limit)
        except _Unrepresentable as e:
            self._warn_python_path(str(e))
            return None
        ids = [aid for _, aid in scored]
        rows: dict = {}
        for k in range(0, len(ids), ID_FETCH_CHUNK):
            chunk = ids[k:k + ID_FETCH_CHUNK]
            marks = ", ".join("?" for _ in chunk)
            for r in cur.execute(
                f"SELECT {', '.join(_ASSERTION_COLUMNS)} FROM {self._table} "
                f"WHERE assertion_id IN ({marks})", chunk,
            ).fetchall():
                rows[r["assertion_id"]] = r
        if len(rows) != len(set(ids)):
            return _STALE
        return [(score, rows[aid]) for score, aid in scored]

    def query_plan(self, q: TripleQuery) -> List[str]:
        """SQLite's `EXPLAIN QUERY PLAN` detail lines for the structured
        read `query(q)` would run (filters, order, limit; a semantic query's
        candidate filter is the same WHERE). A measurement surface: tests pin
        that partition and anchored reads stay on their indexes (0058)."""
        raw_limit = int(q.limit) if isinstance(q.limit, int) else 100
        sql, params = self._structured_sql(q, None if raw_limit <= 0 else max(1, raw_limit))
        with self._lock:
            rows = self._conn.cursor().execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
        return [str(r[3]) for r in rows]

    def close_assertion(self, assertion_id: str, valid_until: str) -> bool:
        """Close one assertion's validity window IN PLACE (additive, backlog:
        abstractnote supersession). Sets `valid_until` only while it is still
        open (NULL); every other column — terms, provenance, attributes, the
        FTS row, the vector — is untouched, so the store stays append-only
        for content. Returns True when a row changed, False when the id is
        unknown or the window was already closed (idempotent replays).

        Why: a later fact superseding an earlier one must make
        `TripleQuery(active_at=...)` agree with the writer's belief window;
        journal closures alone only reach ranked retrieval, never `query`."""
        rid = str(assertion_id or "").strip()
        until = str(valid_until or "").strip()
        if not rid:
            raise ValueError("close_assertion requires an assertion_id")
        if not until:
            raise ValueError("close_assertion requires a valid_until timestamp")
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute(
                    f"UPDATE {self._table} SET valid_until = ? "
                    "WHERE assertion_id = ? AND valid_until IS NULL",
                    (until, rid),
                )
                changed = int(cur.rowcount or 0) > 0
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
        return changed

    def replace_vectors(
        self, vectors: dict, pin: dict, *,
        expected_row_count: int, embedder: Optional[TextEmbedder] = None,
    ) -> int:
        """ATOMIC embedding-space swap (M1b reembed): in ONE transaction,
        verify the store did not change under the pass (expected_row_count —
        the lease-violation guard), rewrite EVERY row's vector (rows absent
        from `vectors` become NULL — edge rows and unembeddable rows), and
        write the new pin LAST inside the same transaction. Readers serve
        the OLD space consistently until the commit — never a mixed space.
        The live embedder swaps with the pin so subsequent adds embed into
        the new space. Returns the number of vectored rows."""
        payload = {str(k): encode_vector(v) for k, v in vectors.items() if v is not None}
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                [(count,)] = cur.execute(f"SELECT COUNT(*) FROM {self._table}").fetchall()
                if int(count) != int(expected_row_count):
                    raise RuntimeError(
                        f"reembed swap refused: store changed mid-pass "
                        f"({count} rows now, {expected_row_count} at scan) — "
                        "the caller's exclusive-writer guarantee did not hold (another writer touched the store); nothing was written"
                    )
                cur.execute(f"UPDATE {self._table} SET embedding = NULL")
                cur.executemany(
                    f"UPDATE {self._table} SET embedding = ? WHERE assertion_id = ?",
                    [(vec, rid) for rid, vec in sorted(payload.items())],
                )
                # Every vector changed: other handles' matrices must rebuild.
                self._bump_vector_generation(cur)
                self._write_pin(pin, cursor=cur)
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
            self._vectors = None  # this handle rebuilds at its next semantic query
            if embedder is not None:
                self._embedder = embedder
        return len(payload)

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
        # float32 BLOB or legacy JSON text; None = vectorless row (skipped
        # by ranking; the channel labels it).
        return decode_vector(r["embedding"])

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


def read_embedding_pin(path: Any, *, table_name: str = "triples") -> Optional[dict]:
    """PURE PEEK at a store file's embedding pin — the resolution read of the
    entity-embedding-config contract (maintainer ruling 2026-07-11: the home's
    declaration overrides every ambient default).

    Doors must decide WHICH embedder to construct FROM the store's own
    declaration BEFORE opening the store with it — but opening a store just
    to read the pin MUTATES the file (schema ensure + WAL flip), and a
    "read the declaration" step must be a pure read. This helper is that
    read: read-only sqlite connection (mode=ro URI), tolerant of everything
    (missing file / missing meta table / missing row / malformed JSON ->
    None, exactly matching embedding_pin()'s tolerance), and guaranteed
    non-mutating — it can never create the file or the table.

    None means "no declaration" — for entity homes the DOOR turns that into
    a loud refusal (legacy home: run the reembed migration once); the engine
    stays entity-blind (non-entity stores keep the labeled first-write
    fallback). InMemoryTripleStore needs no twin: an object in hand already
    answers embedding_pin() — this is a path-vs-object difference, not a
    parity gap.
    """
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        return None
    table = _checked_table(table_name)
    try:
        conn = sqlite3.connect(f"file:{file_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute(
            f"SELECT value FROM {table}_meta WHERE key = 'embedding_pin'"
        ).fetchone()
    except sqlite3.Error:
        return None  # no meta table (pre-M1 store) or not a store file
    finally:
        conn.close()
    if row is None:
        return None
    try:
        pin = json.loads(row[0])
    except (TypeError, ValueError):
        return None
    return pin if isinstance(pin, dict) else None
