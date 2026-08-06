"""SQLiteJournal — durable MemoryJournal backend (stdlib sqlite3).

Design sources: docs/backlog/proposed/memory_system_v1/0017 (journal + scope
bindings) and 0013 (concurrency contract). Record shapes and the protocol are
frozen in `journal.py`; query/enrichment semantics are shared with the
`journal_memory` reference helpers so both backends resolve identically.

Storage model: one table per record family plus a single-row ``{prefix}seq``
counter — NOT per-table AUTOINCREMENT: `seq` is ONE monotonic axis across
ALL record families, incremented in the same transaction as each append
(crash-consistent; as_of replay anchors survive reopen).
``{prefix}selected_counts`` denormalizes per-record selected-use counts
(0018): maintained ONLY by kind='selected' events inside the append
transaction (audit kinds never touch it; rebuildable from events).
Filterable scalars are typed columns; dict/tuple fields are JSON TEXT.

Concurrency (0013): ``check_same_thread=False`` + one internal RLock around
ALL cursor use; WAL, ``busy_timeout=5000``, ``synchronous=NORMAL``; writes
use BEGIN IMMEDIATE (write lock up front — no deferred-upgrade deadlocks).
The in-database counter keeps one shared axis across instances/processes.
Coexistence: the default ``memj_`` prefix is disjoint from the triple
store's tables, so a journal may share a .sqlite3 file with a
`SQLiteTripleStore` (0017 sidecar; WAL-on-open sanctioned by 0013).

Write-side idempotency (a2a 0001/011 ask 3): CALLER-SUPPLIED record ids are
idempotency keys — appending an existing id is a no-op returning the
ORIGINAL stored record (original seq; selected-count untouched), so
at-least-once replays never double-write. Journal-assigned ids (empty →
uuid4) never conflict. UNIQUE indexes are the crash-proof backstop; the
check-then-insert inside BEGIN IMMEDIATE makes replays clean no-ops.
Payloads are NOT compared (replays legitimately differ in wall-clock
fields; the id is the identity; id reuse across different content is a
caller bug — first write wins). Traces dedup by caller-supplied trace_id
(reconstruct(trace_id=...) replays); the facade's uuid4-per-read never
collides.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from .journal import (
    ClosureRecord,
    MemoryEvent,
    ReconstructionTrace,
    ScopeBinding,
    ValenceEvent,
    fold_bindings,
)
from .journal_memory import (
    _effective_limit,
    _enrich_binding,
    _enrich_closure,
    _enrich_event,
    _enrich_snapshot,
    _enrich_trace,
    _enrich_valence,
    _normalize_iso_ts,
    _normalize_kinds_filter,
    _require_instance,
    _require_scope,
    _sanitize_batch,
)
from .journal_sqlite_rows import (
    ensure_schema,
    json_dump as _json_dump,
    row_to_binding,
    row_to_closure,
    row_to_event,
    row_to_snapshot,
    row_to_trace,
    row_to_valence,
)
from .seam import ActiveMemorySnapshot

# Table prefixes are interpolated into SQL text (sqlite3 cannot parameterize
# identifiers), so they must be strict identifiers — anything else is a SQL
# injection vector through configuration.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SQLiteJournal:
    """Durable, thread-safe MemoryJournal backend over one SQLite file."""

    def __init__(self, path: Path, *, table_prefix: str = "memj_") -> None:
        prefix = str(table_prefix or "memj_").strip() or "memj_"
        if not _IDENTIFIER_RE.match(prefix):
            raise ValueError(
                f"table_prefix must match [A-Za-z_][A-Za-z0-9_]* (got {table_prefix!r}); "
                "it is interpolated into SQL identifiers"
            )
        self._prefix = prefix
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._t_events, self._t_bindings = f"{prefix}events", f"{prefix}bindings"
        self._t_closures, self._t_traces = f"{prefix}closures", f"{prefix}traces"
        self._t_snapshots, self._t_valence = f"{prefix}snapshots", f"{prefix}valence"
        self._t_seq, self._t_counts = f"{prefix}seq", f"{prefix}selected_counts"

        self._lock = threading.RLock()
        # isolation_level=None -> autocommit + explicit BEGIN/COMMIT in _txn
        # (seq allocation + row inserts + counter updates are ONE atomic unit).
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._configure_pragmas()
        self._ensure_schema()

    # -- setup ----------------------------------------------------------------

    def _configure_pragmas(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            mode_row = cur.execute("PRAGMA journal_mode=WAL").fetchone()
            mode = str(mode_row[0] if mode_row else "").lower()
            if mode != "wal":
                # Some filesystems (network mounts) refuse WAL; the journal
                # still works, with worse reader/writer concurrency.
                warnings.warn(
                    f"#FALLBACK: SQLiteJournal could not enable WAL on {self._path} "
                    f"(journal_mode={mode!r}); concurrent access will be slower",
                    RuntimeWarning,
                    stacklevel=3,
                )
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA synchronous=NORMAL")

    def _ensure_schema(self) -> None:
        # Schema DDL lives with the row codecs (journal_sqlite_rows.ensure_schema):
        # table shapes and row mappings are one concern and drift together.
        with self._txn() as cur:
            ensure_schema(cur, prefix_tables={
                "events": self._t_events, "bindings": self._t_bindings,
                "closures": self._t_closures, "traces": self._t_traces,
                "snapshots": self._t_snapshots, "valence": self._t_valence,
                "seq": self._t_seq, "counts": self._t_counts,
            })

    # -- write plumbing ---------------------------------------------------------

    @contextmanager
    def _txn(self) -> Iterator[sqlite3.Cursor]:
        """One serialized write transaction (lock + BEGIN IMMEDIATE .. COMMIT)."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                yield cur
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise

    def _allocate_seqs(self, cur: sqlite3.Cursor, count: int) -> int:
        """Reserve `count` consecutive seqs; returns the FIRST. Must run
        inside an open transaction: allocation and row inserts commit or
        roll back together (the counter never drifts from the records)."""
        cur.execute(f"UPDATE {self._t_seq} SET value = value + ? WHERE id = 1", (int(count),))
        row = cur.execute(f"SELECT value FROM {self._t_seq} WHERE id = 1").fetchone()
        return int(row[0]) - int(count) + 1

    @staticmethod
    def _insert(cur: sqlite3.Cursor, table: str, row: Dict[str, Any]) -> None:
        cols = ", ".join(row.keys())
        marks = ", ".join("?" for _ in row)
        cur.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))

    def _select_rows(
        self, table: str, where: List[str], params: List[Any], *, order: str, limit: Optional[int]
    ) -> List[sqlite3.Row]:
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {' AND '.join(where)}"
        sql += f" ORDER BY seq {order}"
        if limit is not None:
            sql += " LIMIT ?"
            params = [*params, limit]
        with self._lock:
            return self._conn.cursor().execute(sql, params).fetchall()

    @staticmethod
    def _find_by_id(cur: sqlite3.Cursor, table: str, id_column: str, supplied_id: str) -> Optional[sqlite3.Row]:
        """Supplied-id dedup lookup INSIDE the open write transaction.

        BEGIN IMMEDIATE serializes writers across connections/processes, so
        check-then-insert is race-free (a concurrent replay blocks, then
        SEES the committed row); in-batch duplicate ids resolve to the
        first occurrence's row for the same reason."""
        return cur.execute(f"SELECT * FROM {table} WHERE {id_column} = ?", (supplied_id,)).fetchone()

    # -- events -------------------------------------------------------------------

    def append_events(self, events: Sequence[MemoryEvent]) -> List[MemoryEvent]:
        items = list(events or ())
        for e in items:
            _require_instance(e, MemoryEvent, "append_events")
        if not items:
            return []
        items = _sanitize_batch(items)  # strict-JSON payload boundary (shared with InMemory)
        with self._txn() as cur:
            out: List[MemoryEvent] = []
            for e in items:
                supplied = str(e.event_id or "").strip()
                if supplied:
                    row = self._find_by_id(cur, self._t_events, "event_id", supplied)
                    if row is not None:
                        # Replay no-op (0001/011): original row, original seq;
                        # skipping the insert also skips the selected-count
                        # increment (replays never double-count the trail).
                        out.append(row_to_event(row))
                        continue
                # Seqs allocated per INSERTED record only: gap-free axis.
                enriched = _enrich_event(e, self._allocate_seqs(cur, 1))
                self._insert(cur, self._t_events, {
                    "seq": enriched.seq, "event_id": enriched.event_id, "kind": enriched.kind,
                    "scope": enriched.scope, "owner_id": enriched.owner_id, "record_id": enriched.record_id,
                    "pair_ids_json": _json_dump(list(enriched.pair_ids)) if enriched.pair_ids is not None else None,
                    "weight": float(enriched.weight), "ttl_activity": enriched.ttl_activity,
                    "matched": 1 if enriched.matched else 0,
                    "query_fingerprint": enriched.query_fingerprint, "trace_id": enriched.trace_id,
                    "observed_at": enriched.observed_at, "actor": enriched.actor, "reason": enriched.reason,
                    "provenance_json": _json_dump(enriched.provenance),
                })
                # Denormalized selected-use counter (0018): only genuine
                # 'selected' events advance it — in the SAME transaction, so
                # counter and events can never disagree after a crash.
                if enriched.kind == "selected":
                    cur.execute(
                        f"INSERT INTO {self._t_counts} (record_id, n) VALUES (?, 1) "
                        "ON CONFLICT(record_id) DO UPDATE SET n = n + 1",
                        (enriched.record_id,),
                    )
                out.append(enriched)
        return out

    def events(
        self,
        *,
        scope: str,
        owner_id: str,
        record_id: Optional[str] = None,
        kinds: Optional[Sequence[str]] = None,
        since_seq: Optional[int] = None,
        until_seq: Optional[int] = None,
        limit: int = 512,
    ) -> List[MemoryEvent]:
        scope_n = _require_scope(scope)
        owner_n = str(owner_id or "").strip()
        rid = record_id.strip() if isinstance(record_id, str) and record_id.strip() else None
        kind_filter = _normalize_kinds_filter(kinds)
        max_n = _effective_limit(limit, 512)

        where = ["scope = ?", "owner_id = ?"]
        params: List[Any] = [scope_n, owner_n]
        if rid is not None:
            # Strict equality: co_selected rows (record_id NULL) never match a
            # per-record query — same semantics as the in-memory backend.
            where.append("record_id = ?")
            params.append(rid)
        if kind_filter is not None:
            where.append(f"kind IN ({', '.join('?' for _ in kind_filter)})")
            params.extend(sorted(kind_filter))
        if since_seq is not None:
            where.append("seq >= ?")
            params.append(int(since_seq))
        if until_seq is not None:
            where.append("seq <= ?")
            params.append(int(until_seq))

        rows = self._select_rows(self._t_events, where, params, order="DESC", limit=max_n)
        return [row_to_event(r) for r in rows]

    # -- bindings -------------------------------------------------------------------

    def append_binding(self, binding: ScopeBinding) -> ScopeBinding:
        _require_instance(binding, ScopeBinding, "append_binding")
        [binding] = _sanitize_batch([binding])
        supplied = str(binding.binding_id or "").strip()
        with self._txn() as cur:
            if supplied:
                row = self._find_by_id(cur, self._t_bindings, "binding_id", supplied)
                if row is not None:
                    return row_to_binding(row)  # replay no-op: original record, original seq
            enriched = _enrich_binding(binding, self._allocate_seqs(cur, 1))
            self._insert(cur, self._t_bindings, {
                "seq": enriched.seq, "binding_id": enriched.binding_id,
                "record_id": enriched.record_id, "scope": enriched.scope,
                "owner_id": enriched.owner_id, "search_state": enriched.search_state,
                "prompt_state": enriched.prompt_state, "lifecycle": enriched.lifecycle,
                "source": enriched.source, "reason": enriched.reason,
                "observed_at": enriched.observed_at,
                "provenance_json": _json_dump(enriched.provenance),
            })
        return enriched

    def bindings(
        self,
        *,
        record_id: Optional[str] = None,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
        fold: bool = True,
        until_seq: Optional[int] = None,
    ) -> List[ScopeBinding]:
        where: List[str] = []
        params: List[Any] = []
        if record_id is not None:
            where.append("record_id = ?")
            params.append(str(record_id).strip())
        if scope is not None:
            where.append("scope = ?")
            params.append(str(scope).strip().lower())
        if owner_id is not None:
            where.append("owner_id = ?")
            params.append(str(owner_id).strip())
        if until_seq is not None:
            where.append("seq <= ?")
            params.append(int(until_seq))

        # ASC = chronological audit order; NO limit by design (a fold must
        # see every matching binding). Shared fold module (0017 hard rule).
        rows = self._select_rows(self._t_bindings, where, params, order="ASC", limit=None)
        loaded = [row_to_binding(r) for r in rows]
        return fold_bindings(loaded) if fold else loaded

    # -- closures -------------------------------------------------------------------

    def append_closure(self, closure: ClosureRecord) -> ClosureRecord:
        _require_instance(closure, ClosureRecord, "append_closure")
        [closure] = _sanitize_batch([closure])
        supplied = str(closure.closure_id or "").strip()
        with self._txn() as cur:
            if supplied:
                row = self._find_by_id(cur, self._t_closures, "closure_id", supplied)
                if row is not None:
                    return row_to_closure(row)  # replay no-op: original record, original seq
            enriched = _enrich_closure(closure, self._allocate_seqs(cur, 1))
            self._insert(cur, self._t_closures, {
                "seq": enriched.seq, "closure_id": enriched.closure_id,
                "assertion_id": enriched.assertion_id, "kind": enriched.kind,
                "reason": enriched.reason,
                "replacement_ids_json": _json_dump(list(enriched.replacement_ids)),
                "observed_at": enriched.observed_at, "actor": enriched.actor,
                "provenance_json": _json_dump(enriched.provenance),
            })
        return enriched

    def closures(
        self,
        *,
        assertion_id: Optional[str] = None,
        until_seq: Optional[int] = None,
        limit: int = 512,
    ) -> List[ClosureRecord]:
        max_n = _effective_limit(limit, 512)
        where: List[str] = []
        params: List[Any] = []
        if assertion_id is not None:
            where.append("assertion_id = ?")
            params.append(str(assertion_id).strip())
        if until_seq is not None:
            where.append("seq <= ?")
            params.append(int(until_seq))
        # Newest first, like events.
        rows = self._select_rows(self._t_closures, where, params, order="DESC", limit=max_n)
        return [row_to_closure(r) for r in rows]

    # -- traces / snapshots ------------------------------------------------------------

    def append_trace(self, trace: ReconstructionTrace) -> ReconstructionTrace:
        _require_instance(trace, ReconstructionTrace, "append_trace")
        [trace] = _sanitize_batch([trace])
        supplied = str(trace.trace_id or "").strip()
        with self._txn() as cur:
            if supplied:
                row = self._find_by_id(cur, self._t_traces, "trace_id", supplied)
                if row is not None:
                    return row_to_trace(row)  # replay no-op: first trace wins
            enriched = _enrich_trace(trace, self._allocate_seqs(cur, 1))
            self._insert(cur, self._t_traces, {
                "seq": enriched.seq, "trace_id": enriched.trace_id,
                "trace_kind": enriched.trace_kind,
                "query_fingerprint": enriched.query_fingerprint,
                "need_json": _json_dump(enriched.need),
                "searched_scopes_json": _json_dump(list(enriched.searched_scopes)),
                "escalation_reason": enriched.escalation_reason,
                "channels_json": _json_dump(list(enriched.channels)),
                "candidates_json": _json_dump(list(enriched.candidates)),
                "selected_json": _json_dump(list(enriched.selected)),
                "dropped_json": _json_dump(list(enriched.dropped)),
                "cues_json": _json_dump(list(enriched.cues)),
                "budgets_json": _json_dump(enriched.budgets),
                "budget_spent_json": _json_dump(enriched.budget_spent),
                "selector_route": enriched.selector_route, "stop_reason": enriched.stop_reason,
                "warnings_json": _json_dump(list(enriched.warnings)),
                "admissions_json": _json_dump(dict(enriched.admissions)),
                "observed_at": enriched.observed_at,
            })
        return enriched

    def traces(
        self, *, trace_id: Optional[str] = None, limit: int = 100,
        until_seq: Optional[int] = None,
    ) -> List[ReconstructionTrace]:
        # Newest first; optional trace_id filter + until_seq anchor.
        max_n = _effective_limit(limit, 100)
        where: List[str] = []
        params: List[Any] = []
        if trace_id is not None:
            where.append("trace_id = ?")
            params.append(str(trace_id).strip())
        if until_seq is not None:
            where.append("seq <= ?")
            params.append(int(until_seq))
        rows = self._select_rows(self._t_traces, where, params, order="DESC", limit=max_n)
        return [row_to_trace(r) for r in rows]

    def append_snapshot(self, snapshot: ActiveMemorySnapshot) -> ActiveMemorySnapshot:
        # Protocol types this Any; storage needs the concrete seam type.
        _require_instance(snapshot, ActiveMemorySnapshot, "append_snapshot")
        [snapshot] = _sanitize_batch([snapshot])
        supplied = str(snapshot.snapshot_id or "").strip()
        with self._txn() as cur:
            if supplied:
                row = self._find_by_id(cur, self._t_snapshots, "snapshot_id", supplied)
                if row is not None:
                    return row_to_snapshot(row)  # replay no-op: original record, original seq
            enriched = _enrich_snapshot(snapshot, self._allocate_seqs(cur, 1))
            self._insert(cur, self._t_snapshots, {
                "seq": enriched.seq, "snapshot_id": enriched.snapshot_id,
                "trace_id": enriched.trace_id,
                "used_record_ids_json": _json_dump(list(enriched.used_record_ids)),
                "display_json": _json_dump(list(enriched.display)),
                "prompt_token_estimate": enriched.prompt_token_estimate,
                "observed_at": enriched.observed_at,
                "provenance_json": _json_dump(enriched.provenance),
            })
        return enriched

    def snapshots(
        self, *, trace_id: Optional[str] = None, limit: int = 100,
        until_seq: Optional[int] = None,
    ) -> List[ActiveMemorySnapshot]:
        max_n = _effective_limit(limit, 100)
        where: List[str] = []
        params: List[Any] = []
        if trace_id is not None:
            where.append("trace_id = ?")
            params.append(str(trace_id).strip())
        if until_seq is not None:
            where.append("seq <= ?")
            params.append(int(until_seq))
        rows = self._select_rows(self._t_snapshots, where, params, order="DESC", limit=max_n)
        return [row_to_snapshot(r) for r in rows]

    # -- valence (identity wave; orthogonal to attention by contract) ----------

    def append_valence(self, events: Sequence[ValenceEvent]) -> List[ValenceEvent]:
        items = list(events or ())
        for e in items:
            _require_instance(e, ValenceEvent, "append_valence")
        if not items:
            return []
        items = _sanitize_batch(items)
        out: List[ValenceEvent] = []
        with self._txn() as cur:
            for e in items:
                supplied = str(e.event_id or "").strip()
                if supplied:
                    row = self._find_by_id(cur, self._t_valence, "event_id", supplied)
                    if row is not None:
                        out.append(row_to_valence(row))  # replay no-op
                        continue
                enriched = _enrich_valence(e, self._allocate_seqs(cur, 1))
                self._insert(cur, self._t_valence, {
                    "seq": enriched.seq, "event_id": enriched.event_id,
                    "target_id": enriched.target_id, "sign": enriched.sign,
                    "magnitude": enriched.magnitude, "kind": enriched.kind,
                    "value_refs_json": _json_dump(list(enriched.value_refs)),
                    "scope": enriched.scope, "owner_id": enriched.owner_id,
                    "reason": enriched.reason, "actor": enriched.actor,
                    "trace_id": enriched.trace_id, "observed_at": enriched.observed_at,
                    "provenance_json": _json_dump(enriched.provenance),
                })
                out.append(enriched)
        return out

    def valence_events(
        self, *, scope: str, owner_id: str, target_id: Optional[str] = None,
        since_seq: Optional[int] = None, until_seq: Optional[int] = None,
        limit: int = 512,
    ) -> List[ValenceEvent]:
        where = ["scope = ?", "owner_id = ?"]
        params: List[Any] = [_require_scope(scope), str(owner_id or "").strip()]
        if target_id is not None and str(target_id).strip():
            where.append("target_id = ?")
            params.append(str(target_id).strip())
        if since_seq is not None:
            where.append("seq >= ?")
            params.append(int(since_seq))
        if until_seq is not None:
            where.append("seq <= ?")
            params.append(int(until_seq))
        rows = self._select_rows(self._t_valence, where, params, order="DESC",
                                 limit=_effective_limit(limit, 512))
        return [row_to_valence(r) for r in rows]

    # -- replay stream (a2a 0005) ------------------------------------------------

    def replay_records(self, *, since_seq: int = 0, until_seq: Optional[int] = None):
        """(family, record) across all six families in strict seq order —
        collect + sort over indexed range scans (cheap at current scale per
        0005; a streaming k-way merge is a later optimization)."""
        lo = int(since_seq)
        with self._lock:
            hi = int(until_seq) if until_seq is not None else self.current_seq()
            merged: List[Tuple[int, str, Any]] = []
            for family, table, codec in (
                ("event", self._t_events, row_to_event),
                ("binding", self._t_bindings, row_to_binding),
                ("closure", self._t_closures, row_to_closure),
                ("trace", self._t_traces, row_to_trace),
                ("snapshot", self._t_snapshots, row_to_snapshot),
                ("valence", self._t_valence, row_to_valence),
            ):
                rows = self._conn.cursor().execute(
                    f"SELECT * FROM {table} WHERE seq > ? AND seq <= ? ORDER BY seq ASC",
                    (lo, hi),
                ).fetchall()
                merged.extend((int(r["seq"]), family, codec(r)) for r in rows)
        merged.sort(key=lambda item: item[0])
        for _seq, family, record in merged:
            yield family, record

    # -- counters / axis ------------------------------------------------------------

    def selected_count(self, record_id: str, *, until_seq: Optional[int] = None) -> int:
        """THE GLOBAL access count (never decays; temporal counterpart =
        the activation fold). until_seq anchors for as_of replay (indexed
        event count; the counter table serves the unanchored read)."""
        rid = str(record_id or "").strip()
        with self._lock:
            if until_seq is None:
                row = self._conn.cursor().execute(
                    f"SELECT n FROM {self._t_counts} WHERE record_id = ?", (rid,)
                ).fetchone()
                return int(row["n"]) if row is not None else 0
            row = self._conn.cursor().execute(
                f"SELECT COUNT(*) AS n FROM {self._t_events} "
                "WHERE kind = 'selected' AND record_id = ? AND seq <= ?",
                (rid, int(until_seq)),
            ).fetchone()
        return int(row["n"]) if row is not None else 0

    def pair_selected_count(self, pair: tuple, *, until_seq: Optional[int] = None) -> int:
        """GLOBAL EDGE access count (cumulative co_selected; never decays;
        order-insensitive). Indexed COUNT over canonical pair_ids_json
        (partial index) — no second counter table: lifetime reads are rare,
        appends are hot."""
        a, b = (str(pair[0] or "").strip(), str(pair[1] or "").strip())
        key = _json_dump(list(sorted((a, b))))
        where = "kind = 'co_selected' AND pair_ids_json = ?"
        params: list = [key]
        if until_seq is not None:
            where += " AND seq <= ?"
            params.append(int(until_seq))
        with self._lock:
            row = self._conn.cursor().execute(
                f"SELECT COUNT(*) AS n FROM {self._t_events} WHERE {where}", params
            ).fetchone()
        return int(row["n"]) if row is not None else 0

    def seq_at(self, iso_ts: str) -> int:
        ts = _normalize_iso_ts(iso_ts)
        # Snapshots deliberately excluded: they mirror what entered a context and
        # never affect scoring or folds — not part of the as_of anchor (matches InMemoryJournal).
        families = (self._t_events, self._t_bindings, self._t_closures, self._t_traces)
        union = " UNION ALL ".join(f"SELECT MAX(seq) AS s FROM {t} WHERE observed_at <= ?" for t in families)
        with self._lock:
            row = self._conn.cursor().execute(f"SELECT MAX(s) AS m FROM ({union})", (ts,) * len(families)).fetchone()
        return int(row["m"]) if row is not None and row["m"] is not None else 0

    def current_seq(self) -> int:
        with self._lock:
            row = self._conn.cursor().execute(f"SELECT value FROM {self._t_seq} WHERE id = 1").fetchone()
        return int(row["value"]) if row is not None else 0

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass  # already closed / interpreter teardown: nothing to release
