"""SQLite row/table shapes for SQLiteJournal (one task: the storage mapping).

Split out of `journal_sqlite.py` to honor the <600-lines-per-file rule. This
module owns the faithful translation between `sqlite3.Row` and the frozen
record dataclasses (journal.py / seam.py), the JSON column helpers, AND the
schema DDL (`ensure_schema` — table shapes and row mappings are one concern
and drift together). No transactions, no locking: `journal_sqlite.py` owns
storage semantics and calls in with an open cursor.
"""

from __future__ import annotations

import json
import sqlite3
import warnings
from typing import Any, Dict, Mapping, Tuple

from .journal import ClosureRecord, MemoryEvent, ReconstructionTrace, ScopeBinding, ValenceEvent
from .seam import ActiveMemorySnapshot, _jsonify

__all__ = [
    "ensure_schema",
    "json_dump",
    "row_to_binding",
    "row_to_closure",
    "row_to_event",
    "row_to_snapshot",
    "row_to_trace",
    "row_to_valence",
]


def ensure_schema(cur: sqlite3.Cursor, *, prefix_tables: Mapping[str, str]) -> None:
    """Create/migrate every journal table (idempotent; runs inside the
    caller's transaction). seq is PRIMARY KEY in every family table: the
    global counter guarantees cross-family uniqueness, so within a family it
    is trivially unique and doubles as the rowid."""
    t = dict(prefix_tables)
    ev, bi, cl, tr, sn, va = t["events"], t["bindings"], t["closures"], t["traces"], t["snapshots"], t["valence"]
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS {ev} (
          seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL, kind TEXT NOT NULL,
          scope TEXT NOT NULL, owner_id TEXT NOT NULL, record_id TEXT,
          pair_ids_json TEXT, weight REAL NOT NULL, ttl_activity INTEGER,
          matched INTEGER NOT NULL DEFAULT 0, query_fingerprint TEXT, trace_id TEXT,
          observed_at TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT,
          provenance_json TEXT)"""
    )
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{ev}_scope_seq ON {ev}(scope, seq DESC)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{ev}_record_seq ON {ev}(record_id, seq)")
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS {bi} (
          seq INTEGER PRIMARY KEY, binding_id TEXT NOT NULL, record_id TEXT NOT NULL,
          scope TEXT NOT NULL, owner_id TEXT NOT NULL, search_state TEXT NOT NULL,
          prompt_state TEXT NOT NULL, lifecycle TEXT NOT NULL, source TEXT NOT NULL,
          reason TEXT, observed_at TEXT NOT NULL, provenance_json TEXT)"""
    )
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{bi}_fold ON {bi}(record_id, scope, owner_id, seq)")
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS {cl} (
          seq INTEGER PRIMARY KEY, closure_id TEXT NOT NULL, assertion_id TEXT NOT NULL,
          kind TEXT NOT NULL, reason TEXT NOT NULL, replacement_ids_json TEXT NOT NULL,
          observed_at TEXT NOT NULL, actor TEXT NOT NULL, provenance_json TEXT)"""
    )
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{cl}_assertion ON {cl}(assertion_id)")
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS {tr} (
          seq INTEGER PRIMARY KEY, trace_id TEXT NOT NULL, trace_kind TEXT NOT NULL,
          query_fingerprint TEXT NOT NULL, need_json TEXT NOT NULL,
          searched_scopes_json TEXT NOT NULL, escalation_reason TEXT,
          channels_json TEXT NOT NULL, candidates_json TEXT NOT NULL,
          selected_json TEXT NOT NULL, dropped_json TEXT NOT NULL, cues_json TEXT NOT NULL,
          budgets_json TEXT NOT NULL, budget_spent_json TEXT NOT NULL,
          selector_route TEXT NOT NULL, stop_reason TEXT NOT NULL,
          warnings_json TEXT NOT NULL, observed_at TEXT NOT NULL)"""
    )
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS {sn} (
          seq INTEGER PRIMARY KEY, snapshot_id TEXT NOT NULL, trace_id TEXT NOT NULL,
          used_record_ids_json TEXT NOT NULL, display_json TEXT NOT NULL,
          prompt_token_estimate INTEGER, observed_at TEXT NOT NULL, provenance_json TEXT)"""
    )
    # Single-row global counter (id constrained to 1); seeded once.
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS {t["seq"]} (
          id INTEGER PRIMARY KEY CHECK (id = 1), value INTEGER NOT NULL)"""
    )
    cur.execute(f'INSERT OR IGNORE INTO {t["seq"]} (id, value) VALUES (1, 0)')
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS {t["counts"]} (
          record_id TEXT PRIMARY KEY, n INTEGER NOT NULL)"""
    )
    # Valence family (identity wave slice 2): signed appraisals, orthogonal
    # to attention by contract — reconstruct never reads this table. No JSONL
    # export inclusion: the 0015 export surface is not built yet (nothing to
    # extend; noted for when it lands).
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS {va} (
          seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL, target_id TEXT NOT NULL,
          sign INTEGER NOT NULL, magnitude REAL NOT NULL, kind TEXT NOT NULL,
          value_refs_json TEXT NOT NULL, scope TEXT NOT NULL, owner_id TEXT NOT NULL,
          reason TEXT NOT NULL, actor TEXT NOT NULL, trace_id TEXT,
          observed_at TEXT NOT NULL, provenance_json TEXT)"""
    )
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{va}_target ON {va}(target_id, seq DESC)")
    # Idempotency backstop (0001/011 ask 3): record ids are unique per
    # family. Migration-safe (IF NOT EXISTS; pre-existing rows carry uuid4
    # ids). The append paths dedup via check-then-insert under BEGIN
    # IMMEDIATE, so these indexes should never fire — if one does, an
    # identity invariant broke and a loud IntegrityError is correct.
    for table, id_col in ((ev, "event_id"), (bi, "binding_id"), (cl, "closure_id"),
                          (sn, "snapshot_id"), (tr, "trace_id"), (va, "event_id")):
        cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS uq_{table}_{id_col} ON {table}({id_col})")
    # Additive column migration (union model): admissions_json landed after
    # the traces table shipped; CREATE TABLE IF NOT EXISTS cannot add
    # columns, so probe and ALTER (nullable -> {} on read).
    trace_cols = {r[1] for r in cur.execute(f"PRAGMA table_info({tr})").fetchall()}
    if "admissions_json" not in trace_cols:
        cur.execute(f"ALTER TABLE {tr} ADD COLUMN admissions_json TEXT")
    # trace_id lookups are hot paths (commit_selection idempotency pre-check
    # scans snapshots per commit; listed-audit correlation reads events per
    # trace) — index them (audit a6/s6).
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{sn}_trace ON {sn}(trace_id)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{ev}_trace ON {ev}(trace_id)")
    # Global pair access counts (maintainer's access-count model): partial
    # index makes pair_selected_count an indexed COUNT over co_selected rows.
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{ev}_pair ON {ev}(pair_ids_json) "
        "WHERE kind = 'co_selected'"
    )


def json_dump(value: Any) -> str:
    # ensure_ascii=False keeps multilingual reasons/digests readable in the
    # file (same convention as SQLiteTripleStore provenance columns).
    # Strict-JSON boundary (audit a5): the seam _jsonify pass stringifies
    # datetimes/objects, and allow_nan=False guarantees no bare NaN/Infinity
    # token ever lands on disk — non-finite floats are normalized to None at
    # append (journal_memory._sanitize_batch), so a ValueError here means a
    # sanitization gap, which must be loud.
    return json.dumps(_jsonify(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _json_load(raw: Any, default: Any) -> Any:
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        # A corrupt JSON cell must not make the whole family unreadable;
        # degrade loudly per framework convention instead of raising.
        warnings.warn(
            f"#FALLBACK: SQLiteJournal could not decode a JSON column ({raw!r}); using default",
            RuntimeWarning,
        )
        return default


def _dict_tuple(raw: Any) -> Tuple[Dict[str, Any], ...]:
    loaded = _json_load(raw, [])
    return tuple(dict(x) for x in loaded if isinstance(x, dict))


def _str_tuple(raw: Any) -> Tuple[str, ...]:
    return tuple(str(x) for x in _json_load(raw, []))


def row_to_event(r: sqlite3.Row) -> MemoryEvent:
    pair = _json_load(r["pair_ids_json"], None)
    return MemoryEvent(
        kind=str(r["kind"]),
        scope=str(r["scope"]),
        owner_id=str(r["owner_id"]),
        record_id=str(r["record_id"]) if r["record_id"] is not None else None,
        pair_ids=tuple(pair) if isinstance(pair, list) and len(pair) == 2 else None,
        weight=float(r["weight"]),
        ttl_activity=int(r["ttl_activity"]) if r["ttl_activity"] is not None else None,
        matched=bool(r["matched"]),
        query_fingerprint=r["query_fingerprint"],
        trace_id=r["trace_id"],
        observed_at=str(r["observed_at"]),
        actor=str(r["actor"]),
        reason=r["reason"],
        provenance=dict(_json_load(r["provenance_json"], {})),
        event_id=str(r["event_id"]),
        seq=int(r["seq"]),
    )


def row_to_binding(r: sqlite3.Row) -> ScopeBinding:
    return ScopeBinding(
        record_id=str(r["record_id"]),
        scope=str(r["scope"]),
        owner_id=str(r["owner_id"]),
        search_state=str(r["search_state"]),
        prompt_state=str(r["prompt_state"]),
        lifecycle=str(r["lifecycle"]),
        source=str(r["source"]),
        reason=r["reason"],
        observed_at=str(r["observed_at"]),
        provenance=dict(_json_load(r["provenance_json"], {})),
        binding_id=str(r["binding_id"]),
        seq=int(r["seq"]),
    )


def row_to_closure(r: sqlite3.Row) -> ClosureRecord:
    return ClosureRecord(
        assertion_id=str(r["assertion_id"]),
        kind=str(r["kind"]),
        reason=str(r["reason"]),
        replacement_ids=_str_tuple(r["replacement_ids_json"]),
        observed_at=str(r["observed_at"]),
        actor=str(r["actor"]),
        provenance=dict(_json_load(r["provenance_json"], {})),
        closure_id=str(r["closure_id"]),
        seq=int(r["seq"]),
    )


def row_to_trace(r: sqlite3.Row) -> ReconstructionTrace:
    return ReconstructionTrace(
        trace_id=str(r["trace_id"]),
        trace_kind=str(r["trace_kind"]),
        query_fingerprint=str(r["query_fingerprint"]),
        need=dict(_json_load(r["need_json"], {})),
        searched_scopes=_dict_tuple(r["searched_scopes_json"]),
        escalation_reason=r["escalation_reason"],
        channels=_str_tuple(r["channels_json"]),
        candidates=_dict_tuple(r["candidates_json"]),
        selected=_str_tuple(r["selected_json"]),
        dropped=_dict_tuple(r["dropped_json"]),
        cues=_str_tuple(r["cues_json"]),
        budgets=dict(_json_load(r["budgets_json"], {})),
        budget_spent=dict(_json_load(r["budget_spent_json"], {})),
        selector_route=str(r["selector_route"]),
        stop_reason=str(r["stop_reason"]),
        warnings=_str_tuple(r["warnings_json"]),
        admissions=dict(_json_load(r["admissions_json"], {})),
        observed_at=str(r["observed_at"]),
        seq=int(r["seq"]),
    )


def row_to_valence(r: sqlite3.Row) -> ValenceEvent:
    return ValenceEvent(
        target_id=str(r["target_id"]),
        sign=int(r["sign"]),
        magnitude=float(r["magnitude"]),
        kind=str(r["kind"]),
        value_refs=_str_tuple(r["value_refs_json"]),
        scope=str(r["scope"]),
        owner_id=str(r["owner_id"]),
        reason=r["reason"],
        actor=str(r["actor"]),
        trace_id=r["trace_id"],
        observed_at=str(r["observed_at"]),
        provenance=dict(_json_load(r["provenance_json"], {})),
        event_id=str(r["event_id"]),
        seq=int(r["seq"]),
    )


def row_to_snapshot(r: sqlite3.Row) -> ActiveMemorySnapshot:
    return ActiveMemorySnapshot(
        snapshot_id=str(r["snapshot_id"]),
        seq=int(r["seq"]),
        trace_id=str(r["trace_id"]),
        used_record_ids=_str_tuple(r["used_record_ids_json"]),
        display=_dict_tuple(r["display_json"]),
        prompt_token_estimate=(
            int(r["prompt_token_estimate"]) if r["prompt_token_estimate"] is not None else None
        ),
        observed_at=str(r["observed_at"]),
        provenance=dict(_json_load(r["provenance_json"], {})),
    )
