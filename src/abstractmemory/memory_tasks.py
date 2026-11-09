"""A persistent queue of memory tasks in the home: what still needs understanding (backlog 0060).

THE RULING (operator 2026-11-07, rule 1; decision 3 of 2026-11-08): summaries and metadata are always computed, in the
background whenever resources are free, with eventual consistency, driven by a persistent queue inside AbstractMemory.
Which tasks a window runs is ACTIVATION-DRIVEN: each task carries the strength of the incoming memory, change or
surprise that caused it; `select_for_window(budget_seconds, sensitivity)` gates every strength through the ADR 0001
logistic (`activation_gate.activation`) and returns the tasks above the floor, highest activation first, until the
host's wall-time budget or the hard safety cap stops it, and says what it left out and why. Never a fixed count.

WHAT MEMORY OWNS: the tasks (`memq_tasks`), their log (`memq_log`) and the last window each host claimed
(`memq_windows`), all in the home's one file (`memory.sqlite3`, on the store's connection; the in-memory store gets a
private in-memory database with the same schema). Memory enqueues where records form (`MemorySystem(task_queue=True)`
+ `remember_many`, `world_model_pass`, `dream_pass`, the ripple, the backfill). WHAT THE HOST OWNS: when a window
opens, its budget, the model call, any generation gate. The host leases tasks (`claim`), reads `task_packet`, runs
its reader, and applies through the 0059 verbs with `task_id=` (the verb acks the task in the same transaction on a
SQLite home) or settles with `ack` / `release`.

TASK KINDS (capability = the cognition-profile capability that runs them):
- `title.author`, `digest.author` (summaries): a record formed PENDING (operator rulings 2026-11-09: a title and a
  summary are mandatory metadata of every memory; when one failed at formation the record carries the marker
  `attributes.pending = {title, summary, since, attempts}` and these tasks write what is missing; a STORED record
  whose title or summary is still not authored, e.g. a legacy card or dream, is declared pending the same way by
  `understanding.declare_pending`). FORMATION priority, ahead of every rewrite; `retitle` / `rewrite_digest`
  complete them and clear the marker; each claim mirrors the attempt into the marker;
- `digest.rewrite` (summaries): an episode, session summary or observation still in mechanical words;
- `card.author` (summaries): a LEGACY world-model card still in mechanical words (or carrying a mechanical delta),
  formed before cards formed pending; `world_model_pass` forms every card with its title and summary pending (the
  evidence briefing is only its provisional body), so a new card owes `title.author` / `digest.author` instead;
- `dream.narrate` (understanding): a dream without a narration (night and nap windows only);
- `ripple.reconsider`, `ripple.consolidate` (understanding): the ripple (backlog 0061); consolidation runs only in a
  nightly sleep window.
Maintenance candidates and dedup groups are review offers, never tasks. The protected kinds are never tasks.

STATUS: pending -> leased (lease_seconds, then it returns) -> done | failed (max_attempts claims) | skipped (the host's
reason, e.g. over_context) | superseded (a newer reading made the basis stale). `deferred` = pending with a
`not_before` (an unreachable endpoint or embedder; no attempt spent). Idempotent: task_id = hash(kind | target |
basis), enqueue is INSERT OR IGNORE. Nothing stored is cut: every text and list is kept whole (root ADR 0054).
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from . import activation_gate as gate
from .canonical_text import record_title, token_estimate

__all__ = [
    "FORMATION_PRIORITY",
    "MemoryTaskQueue",
    "PENDING_KINDS",
    "TASK_CAPABILITIES",
    "TASK_KINDS",
    "TASK_STATUSES",
    "WINDOWS",
    "enqueue_debt",
    "task_id_for",
    "task_packet",
    "understanding_debt",
]

TASK_CAPABILITIES: Mapping[str, str] = {
    "title.author": "summaries", "digest.author": "summaries",
    "digest.rewrite": "summaries", "card.author": "summaries", "dream.narrate": "understanding",
    "ripple.reconsider": "understanding", "ripple.consolidate": "understanding",
}
#: The tasks that write a pending record's mandatory metadata (records.PENDING_TASK_KINDS, by pending field).
PENDING_KINDS = frozenset({"title.author", "digest.author"})
TASK_KINDS = frozenset(TASK_CAPABILITIES)
TASK_STATUSES = frozenset({"pending", "deferred", "leased", "done", "failed", "skipped", "superseded"})
TERMINAL = frozenset({"done", "failed", "skipped", "superseded"})
LIVE = frozenset({"pending", "deferred", "leased"})
#: The host's window names (DESIGN §6). A task names the windows it may run in; none = any.
WINDOWS = frozenset({"turn", "visit", "nap", "cycle", "night", "idle"})
KIND_WINDOWS: Mapping[str, Tuple[str, ...]] = {"dream.narrate": ("night", "nap"), "ripple.consolidate": ("night",)}
#: Tie-break after activation (DESIGN §5): 5 formation (a pending title or summary: mandatory metadata still being
#: written), 10 this turn, 20 ripple, 30 summary/card, 40 dream, 90 backfill.
FORMATION_PRIORITY = 5
PRIORITY: Mapping[str, int] = {"title.author": FORMATION_PRIORITY, "digest.author": FORMATION_PRIORITY,
                               "digest.rewrite": 30, "card.author": 30, "dream.narrate": 40,
                               "ripple.reconsider": 20, "ripple.consolidate": 40}
TURN_PRIORITY = 10
BACKFILL_PRIORITY = 90
DEFAULT_LEASE_SECONDS = 600
DEFAULT_MAX_ATTEMPTS = 3
RELEASE_OUTCOMES = frozenset({"retry", "defer", "skip"})
#: Selection reasons a task is left out of a window (each named in the result).
LEFT_OUT_REASONS = frozenset({"below_gate", "over_budget", "hard_cap", "window", "blocked", "not_before", "leased",
                              "ripple_window_cap", "scope", "filtered"})


def task_id_for(kind: str, target_id: str, basis: str) -> str:
    """The idempotent id of a task."""
    return hashlib.sha256(f"{kind}|{target_id}|{basis}".encode("utf-8")).hexdigest()[:32]


def _utc(value: Optional[Union[str, datetime]] = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"times must carry an offset (got {value!r})")
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False, sort_keys=True)


def _load(raw: Any, default: Any) -> Any:
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _strength(value: float) -> float:
    v = float(value)
    if not math.isfinite(v) or v < 0.0 or v > 1.0:
        raise ValueError(f"strength must be within [0, 1] (got {value!r})")
    return v


class MemoryTaskQueue:
    """The queue over one home. SQLite store: the store's own file, connection and lock (a rewrite acks its task in
    its own transaction). Any other store: a private in-memory database with the same schema (volatile, like the
    store). Construct through `MemorySystem(task_queue=True)` (then `system.tasks`) or directly over a store."""

    def __init__(self, store: Any) -> None:
        from .sqlite_store import SQLiteTripleStore

        self.store = store
        if isinstance(store, SQLiteTripleStore):
            self._conn, self._lock = store._conn, store._lock
            table = store._table
            self.prefix = "memq_" if table == "triples" else f"memq_{table}_"
            self.shares_store_transaction = True
        else:
            if type(store).__name__ == "LanceDBTripleStore":
                raise NotImplementedError("the memory task queue lives in a SQLite home (backlog 0060); "
                                          "a LanceDB store has no transactional file for it")
            self._conn = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._lock = threading.RLock()
            self.prefix = "memq_"
            self.shares_store_transaction = False
        self.t_tasks, self.t_log, self.t_windows = (f"{self.prefix}tasks", f"{self.prefix}log",
                                                    f"{self.prefix}windows")
        self.t_ripples, self.t_gates = f"{self.prefix}ripples", f"{self.prefix}ripple_gates"
        self._ensure_schema()

    # ----------------------------------------------------------------- schema (opening is a read when complete)

    _INDEXES = ("idx_{t}_status", "idx_{t}_target", "idx_{t}_ripple")

    def _expected_objects(self) -> Tuple[str, ...]:
        t = self.t_tasks
        return (self.t_tasks, self.t_log, self.t_windows, self.t_ripples, self.t_gates,
                *(i.format(t=t) for i in self._INDEXES), f"idx_{self.t_gates}_ripple", f"idx_{self.t_log}_task")

    def _ensure_schema(self) -> None:
        expected = self._expected_objects()
        with self._lock:
            cur = self._conn.cursor()
            marks = ", ".join("?" for _ in expected)
            [(present,)] = cur.execute(
                f"SELECT COUNT(*) FROM sqlite_master WHERE name IN ({marks})", expected).fetchall()
            if int(present) == len(expected):
                return
            cur.execute("BEGIN IMMEDIATE")
            try:
                self._create(cur)
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise

    def _create(self, cur: sqlite3.Cursor) -> None:
        t = self.t_tasks
        cur.execute(
            f"""CREATE TABLE IF NOT EXISTS {t} (
              task_id TEXT PRIMARY KEY, kind TEXT NOT NULL, capability TEXT NOT NULL, target_id TEXT NOT NULL,
              assertion_id TEXT NOT NULL, scope TEXT NOT NULL, owner_id TEXT NOT NULL, basis TEXT NOT NULL,
              basis_version INTEGER NOT NULL, strength REAL NOT NULL, priority INTEGER NOT NULL,
              depends_on_json TEXT NOT NULL, windows_json TEXT NOT NULL, not_before TEXT, status TEXT NOT NULL,
              attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL, lease_holder TEXT, lease_until TEXT,
              cause_json TEXT NOT NULL, cost_json TEXT NOT NULL, result_json TEXT, error TEXT,
              ripple_id TEXT, hop INTEGER, enqueued_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_status ON {t}(status, kind)")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_target ON {t}(target_id, kind, status)")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_ripple ON {t}(ripple_id)")
        cur.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.t_log} (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, event TEXT NOT NULL, at TEXT NOT NULL,
              detail_json TEXT NOT NULL)""")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.t_log}_task ON {self.t_log}(task_id, seq)")
        cur.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.t_windows} (
              holder TEXT NOT NULL, window TEXT NOT NULL, at TEXT NOT NULL, budget_seconds REAL NOT NULL,
              sensitivity REAL NOT NULL, hard_cap INTEGER NOT NULL, selected_json TEXT NOT NULL,
              left_out_json TEXT NOT NULL, left_out_counts_json TEXT NOT NULL, PRIMARY KEY (holder, window))""")
        # The ripple's tables (backlog 0061) live beside the queue that carries its reconsiderations.
        cur.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.t_ripples} (
              ripple_id TEXT PRIMARY KEY, seed_id TEXT NOT NULL, scope TEXT NOT NULL, owner_id TEXT NOT NULL,
              cause_json TEXT NOT NULL, magnitude REAL NOT NULL, surprise TEXT, status TEXT NOT NULL,
              hops_max INTEGER NOT NULL, budget INTEGER NOT NULL, reconsidered INTEGER NOT NULL,
              changed_json TEXT NOT NULL, left_out_json TEXT NOT NULL, opened_at TEXT NOT NULL, settled_at TEXT)""")
        cur.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.t_gates} (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, ripple_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
              hop INTEGER NOT NULL, via TEXT NOT NULL, potential REAL NOT NULL, activation REAL NOT NULL,
              decision TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL)""")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.t_gates}_ripple ON {self.t_gates}(ripple_id, seq)")

    # ----------------------------------------------------------------- plumbing

    def _txn(self, cur: Optional[sqlite3.Cursor], fn: Callable[[sqlite3.Cursor], Any]) -> Any:
        """Run `fn` on the caller's open transaction (a rewrite's) or in a new one."""
        if cur is not None:
            return fn(cur)
        with self._lock:
            c = self._conn.cursor()
            c.execute("BEGIN IMMEDIATE")
            try:
                out = fn(c)
                c.execute("COMMIT")
                return out
            except BaseException:
                c.execute("ROLLBACK")
                raise

    def _log(self, cur: sqlite3.Cursor, task_id: str, event: str, at: str, detail: Mapping[str, Any]) -> None:
        cur.execute(f"INSERT INTO {self.t_log} (task_id, event, at, detail_json) VALUES (?, ?, ?, ?)",
                    (task_id, event, at, _dump(dict(detail))))

    def _read(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._conn.cursor().execute(sql, tuple(params)).fetchall()

    @staticmethod
    def _task(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "task_id": row["task_id"], "kind": row["kind"], "capability": row["capability"],
            "target_id": row["target_id"], "assertion_id": row["assertion_id"], "scope": row["scope"],
            "owner_id": row["owner_id"], "basis": row["basis"], "basis_version": int(row["basis_version"]),
            "strength": float(row["strength"]), "priority": int(row["priority"]),
            "depends_on": list(_load(row["depends_on_json"], [])), "windows": list(_load(row["windows_json"], [])),
            "not_before": row["not_before"], "status": row["status"], "attempts": int(row["attempts"]),
            "max_attempts": int(row["max_attempts"]), "lease_holder": row["lease_holder"],
            "lease_until": row["lease_until"], "cause": dict(_load(row["cause_json"], {})),
            "cost_hint": dict(_load(row["cost_json"], {})), "result": _load(row["result_json"], None),
            "error": row["error"], "ripple_id": row["ripple_id"],
            "hop": int(row["hop"]) if row["hop"] is not None else None,
            "enqueued_at": row["enqueued_at"], "updated_at": row["updated_at"],
        }

    # ----------------------------------------------------------------- enqueue

    def enqueue(
        self, kind: str, target_id: str, *, scope: str, owner_id: str, basis: str, strength: float,
        cause: Mapping[str, Any], assertion_id: str = "", basis_version: int = 0,
        priority: Optional[int] = None, depends_on: Sequence[str] = (), not_before: Optional[str] = None,
        windows: Optional[Sequence[str]] = None, cost_hint: Optional[Mapping[str, Any]] = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS, ripple_id: Optional[str] = None, hop: Optional[int] = None,
        now: Optional[str] = None, _cur: Optional[sqlite3.Cursor] = None,
    ) -> Dict[str, Any]:
        """Add one task (idempotent: the same kind, target and basis is one task). `strength` in [0, 1] is the
        incoming signal the gate reads; `basis` names what the task was computed against (a digest assertion id +
        version, a card's evidence fingerprint, a ripple id). A pending task for the same target and kind on an
        OLDER basis_version is superseded. Returns {task_id, enqueued, superseded: [...]}."""
        if kind not in TASK_KINDS:
            raise ValueError(f"kind must be one of {sorted(TASK_KINDS)} (got {kind!r})")
        target = str(target_id or "").strip()
        if not target or not str(basis or "").strip() or not str(scope or "").strip():
            raise ValueError("enqueue needs a target_id, a basis and a scope")
        wins = tuple(KIND_WINDOWS.get(kind, ())) if windows is None else tuple(windows)
        unknown = sorted(set(wins) - WINDOWS)
        if unknown:
            raise ValueError(f"unknown windows {unknown} (known: {sorted(WINDOWS)})")
        if int(max_attempts) < 1:
            raise ValueError("max_attempts must be at least 1")
        tid = task_id_for(kind, target, str(basis))
        at = _iso(_utc(now))
        if ripple_id is None and kind in ("digest.rewrite", "card.author") and self._record_version(target) > int(
                basis_version):
            return {"task_id": tid, "enqueued": False, "superseded": [], "reason": "stale_basis"}
        row = {
            "task_id": tid, "kind": kind, "capability": TASK_CAPABILITIES[kind], "target_id": target,
            "assertion_id": str(assertion_id or ""), "scope": str(scope).strip().lower(),
            "owner_id": str(owner_id or "").strip(), "basis": str(basis), "basis_version": int(basis_version),
            "strength": _strength(strength), "priority": int(PRIORITY[kind] if priority is None else priority),
            "depends_on_json": _dump([str(d) for d in depends_on if str(d or "").strip()]),
            "windows_json": _dump(list(wins)), "not_before": _iso(_utc(not_before)) if not_before else None,
            "status": "pending", "attempts": 0, "max_attempts": int(max_attempts),
            "cause_json": _dump(dict(cause or {})), "cost_json": _dump(dict(cost_hint or {})),
            "ripple_id": ripple_id, "hop": hop, "enqueued_at": at, "updated_at": at,
        }

        def write(cur: sqlite3.Cursor) -> Dict[str, Any]:
            newer = cur.execute(
                f"SELECT 1 FROM {self.t_tasks} WHERE target_id = ? AND kind = ? AND basis_version > ? "
                "AND ripple_id IS NULL LIMIT 1", (target, kind, int(basis_version))).fetchone() \
                if ripple_id is None and kind in ("digest.rewrite", "card.author") else None
            if newer is not None:
                return {"task_id": tid, "enqueued": False, "superseded": [], "reason": "stale_basis"}
            cols = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            cur.execute(f"INSERT OR IGNORE INTO {self.t_tasks} ({cols}) VALUES ({marks})", tuple(row.values()))
            created = int(cur.rowcount or 0) > 0
            superseded: List[str] = []
            if created:
                self._log(cur, tid, "enqueued", at, {"cause": dict(cause or {}), "strength": row["strength"]})
                if ripple_id is None and kind in ("digest.rewrite", "card.author"):
                    superseded = self._supersede_on(cur, target, kind, int(basis_version), at, keep=tid)
            return {"task_id": tid, "enqueued": created, "superseded": superseded}

        return self._txn(_cur, write)

    def _record_version(self, target: str) -> int:
        """The record's current reading version (0 when never rewritten or unknown)."""
        from .records import resolve_digest_assertion
        from .understanding import _current_version, _field_of

        a = resolve_digest_assertion(self.store, target)
        if a is None or not isinstance(a.attributes, dict):
            return 0
        return _current_version(a.attributes, _field_of(str(a.attributes.get("record_kind") or "")))

    def _supersede_on(self, cur: sqlite3.Cursor, target: str, kind: str, version: int, at: str,
                      keep: Optional[str] = None) -> List[str]:
        rows = cur.execute(
            f"SELECT task_id FROM {self.t_tasks} WHERE target_id = ? AND kind = ? AND basis_version < ? "
            "AND status IN ('pending', 'deferred') AND ripple_id IS NULL", (target, kind, version)).fetchall()
        ids = [r[0] for r in rows if r[0] != keep]
        for tid in ids:
            cur.execute(f"UPDATE {self.t_tasks} SET status = 'superseded', updated_at = ? WHERE task_id = ?",
                        (at, tid))
            self._log(cur, tid, "superseded", at, {"by_version": version})
        return ids

    def supersede_target(self, target_id: str, *, kinds: Sequence[str] = ("digest.rewrite", "card.author"),
                         reason: str, now: Optional[str] = None, _cur: Optional[sqlite3.Cursor] = None) -> List[str]:
        """Close the live tasks of a record that no longer needs them (it was closed or replaced)."""
        at = _iso(_utc(now))

        def write(cur: sqlite3.Cursor) -> List[str]:
            marks = ", ".join("?" for _ in kinds)
            rows = cur.execute(
                f"SELECT task_id FROM {self.t_tasks} WHERE target_id = ? AND kind IN ({marks}) "
                "AND status IN ('pending', 'deferred')", (str(target_id), *kinds)).fetchall()
            for (tid,) in rows:
                cur.execute(f"UPDATE {self.t_tasks} SET status = 'superseded', error = ?, updated_at = ? "
                            "WHERE task_id = ?", (reason, at, tid))
                self._log(cur, tid, "superseded", at, {"reason": reason})
            return [r[0] for r in rows]

        return self._txn(_cur, write)

    def on_rewrite(self, cur: Optional[sqlite3.Cursor], *, record_id: str, field: str, version: int,
                   result: Mapping[str, Any], task_id: Optional[str], completes: Sequence[str] = ()) -> None:
        """Called by the 0059 verbs inside their transaction (SQLite) or right after (in-memory): ack the task the
        writer named, and supersede the live tasks the new reading made stale. A retitle (field `title`) and a card
        re-key (field `target`) ack the task they name and supersede nothing: the body a pending task would
        understand is unchanged. `completes` names the pending kinds (`title.author`, `digest.author`) this write
        fulfilled (it cleared the record's pending marker): every live task of those kinds on the record is done,
        whoever wrote the words."""
        at = _iso(_utc())
        kind = {"digest": "digest.rewrite", "card": "card.author", "narration": "dream.narrate", "title": None,
                "target": None, "pending": None}[field]

        def write(c: sqlite3.Cursor) -> None:
            if task_id:
                row = c.execute(f"SELECT status FROM {self.t_tasks} WHERE task_id = ?", (task_id,)).fetchone()
                if row is not None and row[0] not in TERMINAL:
                    c.execute(f"UPDATE {self.t_tasks} SET status = 'done', result_json = ?, lease_holder = NULL, "
                              "lease_until = NULL, updated_at = ? WHERE task_id = ?",
                              (_dump(dict(result)), at, task_id))
                    self._log(c, task_id, "done", at, {"by": "rewrite", "version": version})
            if kind is not None and field != "narration":
                self._supersede_on(c, record_id, kind, version, at, keep=task_id)
            kinds = [k for k in completes if k in PENDING_KINDS]
            if kinds:
                marks = ", ".join("?" for _ in kinds)
                rows = c.execute(f"SELECT task_id FROM {self.t_tasks} WHERE target_id = ? AND kind IN ({marks}) "
                                 "AND status IN ('pending', 'deferred', 'leased')", (record_id, *kinds)).fetchall()
                for (tid,) in rows:
                    c.execute(f"UPDATE {self.t_tasks} SET status = 'done', result_json = ?, lease_holder = NULL, "
                              "lease_until = NULL, updated_at = ? WHERE task_id = ?",
                              (_dump({"outcome": "written", "field": field, "version": version}), at, tid))
                    self._log(c, tid, "done", at, {"by": "rewrite", "field": field, "version": version})

        self._txn(cur, write)

    # ----------------------------------------------------------------- reads

    def task(self, task_id: str) -> Optional[Dict[str, Any]]:
        rows = self._read(f"SELECT * FROM {self.t_tasks} WHERE task_id = ?", (str(task_id),))
        return self._task(rows[0]) if rows else None

    def tasks(self, *, status: Optional[Sequence[str]] = None, kind: Optional[Sequence[str]] = None,
              target_id: Optional[str] = None, ripple_id: Optional[str] = None,
              limit: int = 0) -> List[Dict[str, Any]]:
        """Tasks, oldest first (`limit` <= 0 = all)."""
        where, params = [], []
        for col, values in (("status", status), ("kind", kind)):
            if values:
                vals = [values] if isinstance(values, str) else list(values)
                where.append(f"{col} IN ({', '.join('?' for _ in vals)})")
                params.extend(vals)
        if target_id is not None:
            where.append("target_id = ?")
            params.append(str(target_id))
        if ripple_id is not None:
            where.append("ripple_id = ?")
            params.append(str(ripple_id))
        sql = f"SELECT * FROM {self.t_tasks}" + (f" WHERE {' AND '.join(where)}" if where else "")
        sql += " ORDER BY enqueued_at, task_id"
        if int(limit) > 0:
            sql += f" LIMIT {int(limit)}"
        return [self._task(r) for r in self._read(sql, params)]

    def log(self, task_id: str) -> List[Dict[str, Any]]:
        return [{"seq": int(r["seq"]), "event": r["event"], "at": r["at"], "detail": _load(r["detail_json"], {})}
                for r in self._read(f"SELECT * FROM {self.t_log} WHERE task_id = ? ORDER BY seq", (str(task_id),))]

    def counts(self) -> Dict[str, Dict[str, int]]:
        """{kind: {status: n}} over the whole queue."""
        out: Dict[str, Dict[str, int]] = {}
        for r in self._read(f"SELECT kind, status, COUNT(*) AS n FROM {self.t_tasks} GROUP BY kind, status"):
            out.setdefault(r["kind"], {})[r["status"]] = int(r["n"])
        return out

    def measured_seconds(self, kind: str, *, recent: int = 20) -> Optional[float]:
        """Median seconds of the kind's most recent completed tasks that reported `result.seconds`."""
        rows = self._read(f"SELECT result_json FROM {self.t_tasks} WHERE kind = ? AND status = 'done' "
                          "ORDER BY updated_at DESC LIMIT ?", (kind, int(recent)))
        values = sorted(float(s) for s in (
            (_load(r["result_json"], {}) or {}).get("seconds") for r in rows)
            if isinstance(s, (int, float)) and math.isfinite(float(s)) and float(s) >= 0)
        if not values:
            return None
        mid = len(values) // 2
        return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2.0

    def cost_of(self, task: Mapping[str, Any]) -> Dict[str, Any]:
        """The task's cost hint: {seconds, basis: measured | default, input_tokens, verbatim}."""
        return self._hint(task, self.measured_seconds(str(task["kind"])))

    @staticmethod
    def _hint(task: Mapping[str, Any], measured: Optional[float]) -> Dict[str, Any]:
        hint = dict(task.get("cost_hint") or {})
        hint["seconds"] = measured if measured is not None else float(gate.DEFAULT_TASK_SECONDS[str(task["kind"])])
        hint["basis"] = "measured" if measured is not None else "default"
        return hint

    # ----------------------------------------------------------------- the window

    def select_for_window(
        self, budget_seconds: float, sensitivity: float = 1.0, *, window: str = "turn",
        scopes: Optional[Sequence[Tuple[str, str]]] = None, kinds: Optional[Sequence[str]] = None,
        capabilities: Optional[Sequence[str]] = None, hard_cap: int = gate.DEFAULT_HARD_CAP,
        cost_of: Optional[Callable[[Mapping[str, Any]], float]] = None, now: Optional[str] = None,
    ) -> Dict[str, Any]:
        """The tasks this window should run, highest activation first, never a fixed count (PURE READ).

        Every live task's activation = `activation_gate.activation(strength, sensitivity)`; a task is a candidate
        when it is at or above the gate floor, allowed in `window`, not blocked by a pending dependency, past its
        `not_before`, and not leased by anyone. Candidates are taken in order (activation, then priority, then age)
        while their cost fits the remaining `budget_seconds` (a task that does not fit is left out and the next is
        tried), up to `hard_cap` tasks, and at most `RIPPLE_WINDOW_CAP` ripple reconsiderations. `cost_of(task) ->
        seconds` overrides the queue's estimate (measured median of completed tasks of the kind, else the declared
        default). Returns {window, budget_seconds, sensitivity, hard_cap, gate, tasks: [task + activation + cost],
        planned_seconds, left_out: [{task_id, kind, target_id, reason, activation, cost_seconds}], left_out_counts}.
        Every live task is either selected or listed in left_out with its reason."""
        if window not in WINDOWS:
            raise ValueError(f"window must be one of {sorted(WINDOWS)} (got {window!r})")
        budget = float(budget_seconds)
        if not math.isfinite(budget) or budget < 0:
            raise ValueError("budget_seconds must be a finite non-negative number")
        if int(hard_cap) < 0:
            raise ValueError("hard_cap must be non-negative")
        gate.activation(0.0, sensitivity)  # validates sensitivity
        at = _iso(_utc(now))
        live = [self._task(r) for r in self._read(
            f"SELECT * FROM {self.t_tasks} WHERE status IN ('pending', 'deferred', 'leased')")]
        status_of: Dict[str, str] = {}
        deps = {d for t in live for d in t["depends_on"]}
        if deps:
            marks = ", ".join("?" for _ in deps)
            for r in self._read(f"SELECT task_id, status FROM {self.t_tasks} WHERE task_id IN ({marks})", list(deps)):
                status_of[r["task_id"]] = r["status"]
        wanted_scopes = {(str(s).strip().lower(), str(o or "").strip()) for s, o in scopes} if scopes else None
        left_out: List[Dict[str, Any]] = []
        candidates: List[Tuple[float, int, str, str, Dict[str, Any]]] = []

        def leave(t: Mapping[str, Any], reason: str, act: float, cost: Optional[float] = None) -> None:
            left_out.append({"task_id": t["task_id"], "kind": t["kind"], "target_id": t["target_id"],
                             "reason": reason, "activation": round(act, 6), "cost_seconds": cost})

        for t in live:
            act = gate.activation(t["strength"], sensitivity)
            t["activation"] = act
            if wanted_scopes is not None and (t["scope"], t["owner_id"]) not in wanted_scopes:
                leave(t, "scope", act)
            elif (kinds and t["kind"] not in kinds) or (capabilities and t["capability"] not in capabilities):
                leave(t, "filtered", act)
            elif t["status"] == "leased" and t["lease_until"] and t["lease_until"] > at:
                leave(t, "leased", act)
            elif t["windows"] and window not in t["windows"]:
                leave(t, "window", act)
            elif t["not_before"] and t["not_before"] > at:
                leave(t, "not_before", act)
            elif any(status_of.get(d, "done") not in TERMINAL for d in t["depends_on"]):
                leave(t, "blocked", act)
            elif act < gate.GATE_FLOOR:
                leave(t, "below_gate", act)
            else:
                candidates.append((-act, t["priority"], t["enqueued_at"], t["task_id"], t))
        candidates.sort(key=lambda c: c[:4])
        selected: List[Dict[str, Any]] = []
        spent = 0.0
        ripples = 0
        measured: Dict[str, Optional[float]] = {}
        for _a, _p, _e, _i, t in candidates:
            if t["kind"] not in measured:
                measured[t["kind"]] = self.measured_seconds(t["kind"])
            hint = self._hint(t, measured[t["kind"]])
            seconds = float(cost_of(t)) if cost_of is not None else float(hint["seconds"])
            t["cost"] = dict(hint, seconds=seconds)
            if len(selected) >= int(hard_cap):
                leave(t, "hard_cap", t["activation"], seconds)
            elif t["kind"] == "ripple.reconsider" and ripples >= gate.RIPPLE_WINDOW_CAP:
                leave(t, "ripple_window_cap", t["activation"], seconds)
            elif spent + seconds > budget:
                leave(t, "over_budget", t["activation"], seconds)
            else:
                selected.append(t)
                spent += seconds
                ripples += t["kind"] == "ripple.reconsider"
        counts: Dict[str, int] = {}
        for item in left_out:
            counts[item["reason"]] = counts.get(item["reason"], 0) + 1
        return {"window": window, "budget_seconds": budget, "sensitivity": float(sensitivity),
                "hard_cap": int(hard_cap), "gate": gate.gate_description(), "at": at, "tasks": selected,
                "planned_seconds": spent, "left_out": left_out, "left_out_counts": counts}

    # ----------------------------------------------------------------- leasing

    def claim(
        self, tasks: Union[Mapping[str, Any], Sequence[str]], *, holder: str,
        lease_seconds: float = DEFAULT_LEASE_SECONDS, window: Optional[str] = None, now: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lease tasks for `holder`: a `select_for_window` result (its tasks, its window; the window's choice and
        its left_out are recorded for `left_out()`), or a list of task ids (`window` then checks each task's
        allowed windows). One transaction: a task is leased only while it is pending (or its lease expired), its
        dependencies are settled, its `not_before` passed and the window allows it. Each claim spends one attempt;
        a task re-claimed after `max_attempts` expired leases fails instead. Returns {claimed: [task], refused:
        [{task_id, reason}]}."""
        who = str(holder or "").strip()
        if not who:
            raise ValueError("claim needs a holder (who runs the task)")
        selection = tasks if isinstance(tasks, Mapping) else None
        ids = [str(t["task_id"]) for t in selection["tasks"]] if selection is not None else [str(t) for t in tasks]
        win = str(selection["window"]) if selection is not None else (str(window) if window else None)
        if win is not None and win not in WINDOWS:
            raise ValueError(f"window must be one of {sorted(WINDOWS)} (got {win!r})")
        start = _utc(now)
        at, until = _iso(start), _iso(start + timedelta(seconds=float(lease_seconds)))

        def write(cur: sqlite3.Cursor) -> Dict[str, Any]:
            claimed, refused = [], []
            for tid in ids:
                row = cur.execute(f"SELECT * FROM {self.t_tasks} WHERE task_id = ?", (tid,)).fetchone()
                if row is None:
                    refused.append({"task_id": tid, "reason": "unknown"})
                    continue
                t = self._task(row)
                expired = t["status"] == "leased" and (not t["lease_until"] or t["lease_until"] <= at)
                if t["status"] in TERMINAL:
                    refused.append({"task_id": tid, "reason": t["status"]})
                    continue
                if t["status"] == "leased" and not expired:
                    refused.append({"task_id": tid, "reason": "leased"})
                    continue
                if win is not None and t["windows"] and win not in t["windows"]:
                    refused.append({"task_id": tid, "reason": "window"})
                    continue
                if t["not_before"] and t["not_before"] > at:
                    refused.append({"task_id": tid, "reason": "not_before"})
                    continue
                if t["depends_on"]:
                    marks = ", ".join("?" for _ in t["depends_on"])
                    open_deps = cur.execute(
                        f"SELECT COUNT(*) FROM {self.t_tasks} WHERE task_id IN ({marks}) "
                        "AND status NOT IN ('done', 'failed', 'skipped', 'superseded')", t["depends_on"]).fetchone()[0]
                    if int(open_deps):
                        refused.append({"task_id": tid, "reason": "blocked"})
                        continue
                if expired:
                    self._log(cur, tid, "lease_expired", at, {"holder": t["lease_holder"]})
                if t["attempts"] >= t["max_attempts"]:
                    cur.execute(f"UPDATE {self.t_tasks} SET status = 'failed', lease_holder = NULL, "
                                "lease_until = NULL, error = COALESCE(error, ?), updated_at = ? WHERE task_id = ?",
                                ("max_attempts reached (leases expired)", at, tid))
                    self._log(cur, tid, "failed", at, {"reason": "max_attempts"})
                    refused.append({"task_id": tid, "reason": "failed"})
                    continue
                cur.execute(f"UPDATE {self.t_tasks} SET status = 'leased', lease_holder = ?, lease_until = ?, "
                            "attempts = attempts + 1, updated_at = ? WHERE task_id = ?", (who, until, at, tid))
                self._log(cur, tid, "claimed", at, {"holder": who, "lease_until": until, "window": win})
                claimed.append(self._task(cur.execute(
                    f"SELECT * FROM {self.t_tasks} WHERE task_id = ?", (tid,)).fetchone()))
                if claimed[-1]["kind"] in PENDING_KINDS and self.shares_store_transaction:
                    self._mirror_attempts(cur, claimed[-1])
            if selection is not None:
                cur.execute(
                    f"INSERT OR REPLACE INTO {self.t_windows} (holder, window, at, budget_seconds, sensitivity, "
                    "hard_cap, selected_json, left_out_json, left_out_counts_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (who, win, at, float(selection["budget_seconds"]), float(selection["sensitivity"]),
                     int(selection["hard_cap"]), _dump([t["task_id"] for t in claimed]),
                     _dump(list(selection["left_out"])), _dump(dict(selection["left_out_counts"]))))
            return {"claimed": claimed, "refused": refused}

        out = self._txn(None, write)
        if not self.shares_store_transaction:
            for t in out["claimed"]:
                if t["kind"] in PENDING_KINDS:
                    self._mirror_attempts(None, t)
        return out

    def _mirror_attempts(self, cur: Optional[sqlite3.Cursor], task: Mapping[str, Any]) -> None:
        """A pending record's marker says how many authoring attempts its tasks have had (`attempts`, the highest
        claim count of its live pending tasks): written into the record's attributes on the claim's own transaction
        (SQLite home) or under the store's lock right after (in-memory). The body, title and canonical text are
        untouched; a record whose marker is gone (written meanwhile) is left alone."""
        from dataclasses import replace as _replace

        aid, attempts = str(task.get("assertion_id") or ""), int(task["attempts"])
        if not aid:
            return

        def bumped(fresh: Any) -> Optional[Any]:
            attrs = dict(fresh.attributes or {}) if fresh is not None else {}
            marker = attrs.get("pending")
            if not isinstance(marker, dict) or int(marker.get("attempts") or 0) >= attempts:
                return None
            attrs["pending"] = {**marker, "attempts": attempts}
            return _replace(fresh, attributes=attrs)

        if cur is not None:
            from .sqlite_store import SQLiteTripleStore

            row = self.store._row_for_rewrite(cur, aid)
            new = bumped(SQLiteTripleStore._row_to_assertion(row)) if row is not None else None
            if new is not None:
                self.store._rewrite_row_on(cur, row, new, vector=None, write_vector=False)
        else:
            with self.store._lock:  # read and write under one hold: a concurrent retitle is never clobbered
                new = bumped(self.store._stored_row(aid))
                if new is not None:
                    self.store._rewrite_row(aid, new, vector=None, write_vector=False)

    def ack(self, task_id: str, *, holder: str, result: Mapping[str, Any], now: Optional[str] = None) -> Dict:
        """Settle a leased task as done with the host's result (e.g. {outcome: "unchanged", seconds, tokens,
        run_id, model}). The holder must still hold it. A task a rewrite already acked returns
        {acked: False, reason: "already_done"}."""
        at = _iso(_utc(now))

        def write(cur: sqlite3.Cursor) -> Dict[str, Any]:
            row = cur.execute(f"SELECT * FROM {self.t_tasks} WHERE task_id = ?", (str(task_id),)).fetchone()
            if row is None:
                return {"acked": False, "reason": "unknown"}
            t = self._task(row)
            if t["status"] == "done":
                return {"acked": False, "reason": "already_done", "task": t}
            if t["status"] != "leased" or t["lease_holder"] != str(holder):
                return {"acked": False, "reason": "not_held", "task": t}
            cur.execute(f"UPDATE {self.t_tasks} SET status = 'done', result_json = ?, lease_holder = NULL, "
                        "lease_until = NULL, updated_at = ? WHERE task_id = ?", (_dump(dict(result)), at, t["task_id"]))
            self._log(cur, t["task_id"], "done", at, {"by": str(holder)})
            return {"acked": True, "task": self._task(cur.execute(
                f"SELECT * FROM {self.t_tasks} WHERE task_id = ?", (t["task_id"],)).fetchone())}

        return self._txn(None, write)

    def release(
        self, task_id: str, *, holder: str, outcome: str, reason: str, until: Optional[str] = None,
        detail: Optional[Mapping[str, Any]] = None, now: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Give a leased task back. `outcome`: `retry` (the attempt is spent; failed once `max_attempts` is
        reached), `defer` (an unreachable endpoint or embedder: no attempt spent, not before `until`), `skip`
        (terminal, e.g. reason "over_context" with the measured tokens in `detail`)."""
        if outcome not in RELEASE_OUTCOMES:
            raise ValueError(f"outcome must be one of {sorted(RELEASE_OUTCOMES)} (got {outcome!r})")
        why = str(reason or "").strip()
        if not why:
            raise ValueError("release needs a reason")
        if outcome == "defer" and not until:
            raise ValueError("a defer needs `until` (when to try again)")
        at = _iso(_utc(now))

        def write(cur: sqlite3.Cursor) -> Dict[str, Any]:
            row = cur.execute(f"SELECT * FROM {self.t_tasks} WHERE task_id = ?", (str(task_id),)).fetchone()
            if row is None:
                return {"released": False, "reason": "unknown"}
            t = self._task(row)
            if t["status"] != "leased" or t["lease_holder"] != str(holder):
                return {"released": False, "reason": "not_held", "task": t}
            if outcome == "defer":
                cur.execute(f"UPDATE {self.t_tasks} SET status = 'deferred', not_before = ?, lease_holder = NULL, "
                            "lease_until = NULL, attempts = MAX(0, attempts - 1), error = ?, updated_at = ? "
                            "WHERE task_id = ?", (_iso(_utc(until)), why, at, t["task_id"]))
            elif outcome == "skip":
                cur.execute(f"UPDATE {self.t_tasks} SET status = 'skipped', lease_holder = NULL, lease_until = NULL, "
                            "error = ?, result_json = ?, updated_at = ? WHERE task_id = ?",
                            (why, _dump(dict(detail or {})), at, t["task_id"]))
            else:
                status = "failed" if t["attempts"] >= t["max_attempts"] else "pending"
                cur.execute(f"UPDATE {self.t_tasks} SET status = ?, lease_holder = NULL, lease_until = NULL, "
                            "error = ?, updated_at = ? WHERE task_id = ?", (status, why, at, t["task_id"]))
            self._log(cur, t["task_id"], outcome, at, {"reason": why, **dict(detail or {})})
            return {"released": True, "task": self._task(cur.execute(
                f"SELECT * FROM {self.t_tasks} WHERE task_id = ?", (t["task_id"],)).fetchone())}

        return self._txn(None, write)

    def left_out(self, *, holder: Optional[str] = None, window: Optional[str] = None) -> List[Dict[str, Any]]:
        """What the last claimed window of each (holder, window) left out, and why (root ADR-0026: bounded work
        says what it left out). One row per (holder, window), replaced at each claim: [{holder, window, at,
        budget_seconds, sensitivity, hard_cap, claimed, left_out, left_out_counts}]."""
        where, params = [], []
        if holder is not None:
            where.append("holder = ?")
            params.append(str(holder))
        if window is not None:
            where.append("window = ?")
            params.append(str(window))
        sql = f"SELECT * FROM {self.t_windows}" + (f" WHERE {' AND '.join(where)}" if where else "")
        return [{"holder": r["holder"], "window": r["window"], "at": r["at"],
                 "budget_seconds": float(r["budget_seconds"]), "sensitivity": float(r["sensitivity"]),
                 "hard_cap": int(r["hard_cap"]), "claimed": _load(r["selected_json"], []),
                 "left_out": _load(r["left_out_json"], []), "left_out_counts": _load(r["left_out_counts_json"], {})}
                for r in self._read(sql + " ORDER BY at", params)]

    def supersede_stale(self, system: Any, *, now: Optional[str] = None) -> List[str]:
        """Close live digest/card tasks whose basis version is older than the record's current version (a reading
        written without a task id, or by another process)."""
        from .understanding import _attrs, _current_version, _field_of, _resolve

        at = _iso(_utc(now))
        closed: List[str] = []
        for t in self.tasks(status=("pending", "deferred"), kind=("digest.rewrite", "card.author")):
            if t["ripple_id"]:
                continue
            a = _resolve(system, t["target_id"])
            if a is None:
                continue
            attrs = _attrs(a)
            current = _current_version(attrs, _field_of(str(attrs.get("record_kind") or "")))
            if current > t["basis_version"]:
                closed.extend(self._txn(None, lambda cur, t=t, current=current: self._supersede_on(
                    cur, t["target_id"], t["kind"], current, at)))
        return sorted(set(closed))


# --------------------------------------------------------------------------- formation-side enqueue (memory owns it)


def _protected(attrs: Mapping[str, Any]) -> bool:
    from .understanding import UNDERSTANDING_PROTECTED_KINDS

    kind = str(attrs.get("record_kind") or "").strip().lower()
    return (kind in UNDERSTANDING_PROTECTED_KINDS or bool(attrs.get("maintenance_candidate"))
            or bool(attrs.get("review_required")) or attrs.get("summary_role") == "re-understanding")


def _pending_marker(attrs: Mapping[str, Any]) -> Dict[str, Any]:
    marker = attrs.get("pending")
    return dict(marker) if isinstance(marker, Mapping) else {}


def require_task_queue(system: Any, verb: str) -> None:
    """A pass that forms records PENDING their authored title and summary (world_model_pass, dream_pass, the
    candidate miner, consolidation candidates, the dedup day summary) refuses a home without a task queue before it
    writes anything: no title or summary is ever stored missing without the task that writes it (operator rulings
    2026-11-09; `remember_many` refuses the record itself, this keeps a night from stopping half-written)."""
    if getattr(system, "tasks", None) is None:
        raise ValueError(
            f"{verb} forms its records pending their authored title and summary (the pass's bookkeeping text is "
            "only their provisional body): open the home with MemorySystem(task_queue=True)")


def pending_task_kinds(attrs: Mapping[str, Any]) -> List[str]:
    """The authoring tasks a record's pending marker owes (`title.author`, `digest.author`), from its marker only."""
    from .records import PENDING_TASK_KINDS

    marker = _pending_marker(attrs)
    return [kind for fld, kind in PENDING_TASK_KINDS.items() if marker.get(fld)]


def enqueue_formed(system: Any, plan: Any, *, scope: str, owner_id: str) -> List[str]:
    """`remember_many`'s enqueue (opted-in homes only): a `title.author` / `digest.author` task per pending field
    of a record formed pending (formation priority, strength FORMATION_STRENGTH), and one `digest.rewrite` per
    formed record whose digest_method is in the repair-consent set (`MECHANICAL_DIGEST_METHODS`; never beside a
    pending summary, whose `digest.author` task owns the body). A summary depends on the pending rewrites of the
    records it summarizes. Returns the task ids enqueued."""
    from .redigestion import MECHANICAL_DIGEST_METHODS

    queue: Optional[MemoryTaskQueue] = getattr(system, "tasks", None)
    if queue is None:
        return []
    digests = [a for a in plan.assertions if (a.attributes or {}).get("record_kind")]
    out: List[str] = []
    for a in digests:
        attrs = dict(a.attributes or {})
        for task_kind in pending_task_kinds(attrs):
            fld = "title" if task_kind == "title.author" else "summary"
            res = queue.enqueue(
                task_kind, a.subject, scope=scope, owner_id=owner_id, assertion_id=str(a.assertion_id or ""),
                basis=f"{a.assertion_id}@pending-{fld}", basis_version=0, strength=gate.FORMATION_STRENGTH,
                cause={"cause": "formation", "pending": fld}, priority=FORMATION_PRIORITY,
                cost_hint=_cost_hint(system, a))
            if res["enqueued"]:
                out.append(res["task_id"])
        if _pending_marker(attrs).get("summary"):
            continue
        if str(attrs.get("digest_method") or "") not in MECHANICAL_DIGEST_METHODS or _protected(attrs):
            continue
        kind = str(attrs.get("record_kind"))
        sources = [e.object for e in plan.assertions
                   if e.subject == a.subject and (e.attributes or {}).get("record_edge") and e.predicate == "summarizes"]
        depends = [t["task_id"] for s in sources
                   for t in queue.tasks(status=tuple(LIVE), kind=("digest.rewrite",), target_id=s)]
        res = queue.enqueue(
            "digest.rewrite", a.subject, scope=scope, owner_id=owner_id, assertion_id=str(a.assertion_id or ""),
            basis=f"{a.assertion_id}@v0", basis_version=0, strength=gate.FORMATION_STRENGTH,
            cause={"cause": "formation"}, priority=TURN_PRIORITY if kind != "summary" else PRIORITY["digest.rewrite"],
            depends_on=depends, cost_hint=_cost_hint(system, a, sources))
        if res["enqueued"]:
            out.append(res["task_id"])
    return out


def plan_declared(system: Any, queue: "MemoryTaskQueue", a: Any, fields: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """The authoring task each field `understanding.declare_pending` declares gets (PURE READ, before its
    transaction): formation's own task (`title.author` / `digest.author`, basis `<assertion id>@pending-<field>`,
    basis_version 0), so a declared record owes exactly what a record formed pending owes. A LIVE task with that
    identity (queued earlier without the marker) is adopted, never duplicated; one that already ran to an end on this
    record (a title authored once, declared again) leaves the identity to the first free `...@pending-<field>@<k>`.
    Returns {field: {kind, task_id, basis, live, cost_hint}}."""
    from .records import PENDING_TASK_KINDS

    out: Dict[str, Dict[str, Any]] = {}
    for fld in fields:
        kind = PENDING_TASK_KINDS[fld]
        base = f"{a.assertion_id}@pending-{fld}"
        basis, k = base, 1
        while True:
            t = queue.task(task_id_for(kind, str(a.subject), basis))
            if t is None or t["status"] in LIVE:
                break
            k += 1
            basis = f"{base}@{k}"
        out[fld] = {"kind": kind, "task_id": task_id_for(kind, str(a.subject), basis), "basis": basis,
                    "live": t is not None, "cost_hint": _cost_hint(system, a)}
    return out


def enqueue_declared(queue: "MemoryTaskQueue", a: Any, plan: Mapping[str, Mapping[str, Any]], *,
                     cause: Mapping[str, Any], body_kind: str, _cur: Optional[sqlite3.Cursor] = None,
                     ) -> Dict[str, List[str]]:
    """`declare_pending`'s enqueue, on its transaction (SQLite) or right after its write (in-memory): per declared
    field the task `plan_declared` named, with formation's parameters (`FORMATION_PRIORITY`, `FORMATION_STRENGTH`,
    capability summaries); its cause is the declaration's ({cause, pending: <field>, declared: true, reason?}). A
    declared summary supersedes the record's live body task (`digest.rewrite`, a card's `card.author`): a pending
    summary's `digest.author` task owns the body, as at formation. Returns {enqueued, adopted, superseded}."""
    out: Dict[str, List[str]] = {"enqueued": [], "adopted": [], "superseded": []}
    for fld, p in plan.items():
        if p["live"]:
            out["adopted"].append(str(p["task_id"]))
            continue
        res = queue.enqueue(
            str(p["kind"]), str(a.subject), scope=str(a.scope), owner_id=str(a.owner_id or ""),
            assertion_id=str(a.assertion_id or ""), basis=str(p["basis"]), basis_version=0,
            strength=gate.FORMATION_STRENGTH, cause={**dict(cause), "pending": fld, "declared": True},
            priority=FORMATION_PRIORITY, cost_hint=p["cost_hint"], _cur=_cur)
        out["enqueued" if res["enqueued"] else "adopted"].append(str(res["task_id"]))
    if "summary" in plan:
        out["superseded"] = queue.supersede_target(
            str(a.subject), kinds=("card.author",) if body_kind == "world_model" else ("digest.rewrite",),
            reason="summary declared pending: its digest.author task owns the body", _cur=_cur)
    return out


def _cost_hint(system: Any, a: Any, source_ids: Sequence[str] = ()) -> Dict[str, Any]:
    """What memory knows of a task's input size: the target's digest plus its source digests (token estimates);
    the verbatim is a host artifact, named but not read."""
    from .records import resolve_digest_assertion

    tokens = token_estimate(str(a.object or ""))
    for sid in source_ids:
        s = resolve_digest_assertion(system.store, sid)
        if s is not None:
            tokens += token_estimate(str(s.object or ""))
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    return {"input_tokens": tokens, "verbatim": attrs.get("payload_ref")}


def supersede_revised_card(system: Any, prior_id: str, card_id: str) -> List[str]:
    """`world_model_pass`'s revision: the prior card's live authoring tasks (`title.author`, `digest.author`, a
    legacy `card.author`) are superseded; the new revision, formed pending, carries its own (queued by
    `remember_many`)."""
    queue: Optional[MemoryTaskQueue] = getattr(system, "tasks", None)
    if queue is None or not prior_id or prior_id == card_id:
        return []
    return queue.supersede_target(prior_id, kinds=("title.author", "digest.author", "card.author"),
                                  reason=f"card revised to {card_id}")


def enqueue_dream(system: Any, dream_id: str, *, scope: str, owner_id: str, salience: float,
                  salience_high: float) -> Optional[str]:
    """`dream_pass`'s enqueue: a `dream.narrate` task for a formed dream (night and nap windows)."""
    queue: Optional[MemoryTaskQueue] = getattr(system, "tasks", None)
    if queue is None:
        return None
    from .records import resolve_digest_assertion

    a = resolve_digest_assertion(system.store, dream_id)
    if a is None:
        return None
    strength = min(1.0, max(0.0, float(salience) / max(1.0, float(salience_high))))
    res = queue.enqueue("dream.narrate", dream_id, scope=scope, owner_id=owner_id, assertion_id=str(a.assertion_id),
                        basis=f"{a.assertion_id}@narration", basis_version=0, strength=strength,
                        cause={"cause": "formation", "salience": salience}, cost_hint=_cost_hint(system, a))
    return res["task_id"] if res["enqueued"] else None


# --------------------------------------------------------------------------- debt and backfill


def _formed_rows(system: Any, scopes: Sequence[Tuple[str, str]]) -> List[Any]:
    from .folds import closure_exclusions
    from .store import TripleQuery

    closed = closure_exclusions(system.journal, system.journal.current_seq())
    rows = []
    seen = set()
    for scope, owner in scopes:
        for a in system.store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if not attrs.get("record_kind") or attrs.get("record_edge") or attrs.get("bookkeeping"):
                continue
            if a.assertion_id in closed or a.subject in closed or a.subject in seen:
                continue
            seen.add(a.subject)
            rows.append(a)
    return rows


def _debt_kind(attrs: Mapping[str, Any], methods: frozenset) -> Optional[str]:
    """Which task a record's current reading still owes, from its labels only."""
    from .understanding import MECHANICAL_CARD_METHODS

    kind = str(attrs.get("record_kind") or "")
    method = str(attrs.get("digest_method") or "")
    if _protected(attrs):
        return None
    if kind != "dream" and _pending_marker(attrs).get("summary"):
        return None  # the digest.author task owns the body (a dream's narration is beside it, still owed)
    if kind == "world_model":
        return "card.author" if method in MECHANICAL_CARD_METHODS or method.endswith("+delta") else None
    if kind == "dream":
        return None if str(attrs.get("narration") or "").strip() else "dream.narrate"
    return "digest.rewrite" if method in methods else None


def _covered(queue: Optional[MemoryTaskQueue], kind: str, target: str, version: int) -> bool:
    """A live task, or a done one at the record's current version, already owns this debt."""
    if queue is None:
        return False
    return any(t["status"] in LIVE or (t["status"] == "done" and t["basis_version"] >= version)
               for t in queue.tasks(kind=(kind,), target_id=target))


def understanding_debt(system: Any, *, scopes: Sequence[Tuple[str, str]],
                       methods: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """What is still in mechanical words or still being written (PURE READ): {debt: {task kind: {record kind: n}},
    total, unqueued (debt with no live or done task at the record's current version), queue: {kind: {status: n}},
    by_capability: {capability: live n}, oldest_pending: {task_id, kind, enqueued_at} | None}. A record formed
    pending owes `title.author` / `digest.author` (its marker; any kind). Closed records, review offers
    (maintenance candidates, dedup groups) and the protected kinds are never rewrite debt."""
    from .redigestion import MECHANICAL_DIGEST_METHODS
    from .understanding import _current_version, _field_of

    consent = frozenset(methods) if methods is not None else MECHANICAL_DIGEST_METHODS
    queue: Optional[MemoryTaskQueue] = getattr(system, "tasks", None)
    debt: Dict[str, Dict[str, int]] = {}
    unqueued = 0
    for a in _formed_rows(system, scopes):
        attrs = dict(a.attributes)
        rk = str(attrs.get("record_kind"))
        # A pending record owes its mandatory metadata first (formation debt; the protected kinds included: a
        # title is never his body).
        for pk in pending_task_kinds(attrs):
            debt.setdefault(pk, {})[rk] = debt.setdefault(pk, {}).get(rk, 0) + 1
            if not _covered(queue, pk, str(a.subject), 0):
                unqueued += 1
        task_kind = _debt_kind(attrs, consent)
        if task_kind is None or (task_kind == "digest.rewrite" and _pending_marker(attrs).get("summary")):
            continue
        debt.setdefault(task_kind, {})[rk] = debt.setdefault(task_kind, {}).get(rk, 0) + 1
        version = _current_version(attrs, _field_of(rk))
        if not _covered(queue, task_kind, str(a.subject), version):
            unqueued += 1
    out: Dict[str, Any] = {"debt": debt, "total": sum(sum(v.values()) for v in debt.values()), "unqueued": unqueued,
                           "queue": {}, "by_capability": {}, "oldest_pending": None, "methods": sorted(consent)}
    if queue is not None:
        out["queue"] = queue.counts()
        for kind, statuses in out["queue"].items():
            live = sum(n for s, n in statuses.items() if s in LIVE)
            cap = TASK_CAPABILITIES[kind]
            out["by_capability"][cap] = out["by_capability"].get(cap, 0) + live
        oldest = queue.tasks(status=("pending", "deferred"), limit=1)
        if oldest:
            out["oldest_pending"] = {k: oldest[0][k] for k in ("task_id", "kind", "target_id", "enqueued_at")}
    return out


def enqueue_debt(system: Any, *, scopes: Sequence[Tuple[str, str]], cause: str = "backfill",
                 priority: int = BACKFILL_PRIORITY, dry_run: bool = True,
                 methods: Optional[Iterable[str]] = None, kinds: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """The backfill: enqueue a task for every debt record with no task yet. Strength from lived use (the records
    doing the most daily damage first): `BACKFILL_FLOOR_STRENGTH + (1 - floor) * ln(1 + n) / ln(1 + n_max)` over the
    home's selected counts. `dry_run=True` (the default) writes nothing and returns what it would enqueue.
    `methods` widens the consent set (e.g. a home whose earlier manual pass labelled `entity-authored`). Returns
    {dry_run, would_enqueue | enqueued, by_kind, tasks: [{task_id, kind, target_id, strength}]}."""
    from .redigestion import MECHANICAL_DIGEST_METHODS
    from .understanding import _current_version, _field_of

    queue: Optional[MemoryTaskQueue] = getattr(system, "tasks", None)
    if queue is None and not dry_run:
        raise ValueError("enqueue_debt needs a home opened with MemorySystem(task_queue=True)")
    consent = frozenset(methods) if methods is not None else MECHANICAL_DIGEST_METHODS
    rows = []
    for a in _formed_rows(system, scopes):
        attrs = dict(a.attributes)
        for pk in pending_task_kinds(attrs):
            if not kinds or pk in kinds:
                rows.append((pk, a))
        task_kind = _debt_kind(attrs, consent)
        if task_kind is None or (kinds and task_kind not in kinds) or (
                task_kind == "digest.rewrite" and _pending_marker(attrs).get("summary")):
            continue
        rows.append((task_kind, a))
    counts = {str(a.assertion_id): int(system.journal.selected_count(str(a.assertion_id))) for _k, a in rows}
    top = max(counts.values(), default=0)
    planned = []
    for task_kind, a in rows:
        attrs = dict(a.attributes)
        n = counts[str(a.assertion_id)]
        use = math.log1p(n) / math.log1p(top) if top > 0 else 0.0
        strength = gate.BACKFILL_FLOOR_STRENGTH + (1.0 - gate.BACKFILL_FLOOR_STRENGTH) * use
        version = (0 if task_kind in PENDING_KINDS
                   else _current_version(attrs, _field_of(str(attrs.get("record_kind")))))
        if _covered(queue, task_kind, str(a.subject), version):
            continue
        suffix = f"@v{version}" if version else ""
        if task_kind in PENDING_KINDS:
            # The formation task's own identity: a backfill never duplicates a live or settled authoring task.
            basis = f"{a.assertion_id}@pending-{'title' if task_kind == 'title.author' else 'summary'}"
            strength = gate.FORMATION_STRENGTH
        elif task_kind == "card.author":
            basis = f"{attrs.get('evidence_fingerprint') or ''}@rev{attrs.get('revision') or 0}{suffix}"
        elif task_kind == "dream.narrate":
            basis = f"{a.assertion_id}@narration"
        else:
            basis = f"{a.assertion_id}@v{version}"
        tid = task_id_for(task_kind, str(a.subject), basis)
        if queue is not None and queue.task(tid) is not None:
            continue
        planned.append({"task_id": tid, "kind": task_kind, "target_id": str(a.subject), "strength": strength,
                        "basis": basis, "basis_version": version if task_kind != "dream.narrate" else 0,
                        "assertion_id": str(a.assertion_id), "scope": a.scope, "owner_id": str(a.owner_id or "")})
    by_kind: Dict[str, int] = {}
    for p in planned:
        by_kind[p["kind"]] = by_kind.get(p["kind"], 0) + 1
    if not dry_run:
        for p in planned:
            queue.enqueue(p["kind"], p["target_id"], scope=p["scope"], owner_id=p["owner_id"],
                          assertion_id=p["assertion_id"], basis=p["basis"], basis_version=p["basis_version"],
                          strength=p["strength"], cause={"cause": cause},
                          priority=FORMATION_PRIORITY if p["kind"] in PENDING_KINDS else int(priority))
    key = "would_enqueue" if dry_run else "enqueued"
    return {"dry_run": bool(dry_run), key: len(planned), "by_kind": by_kind,
            "tasks": [{k: p[k] for k in ("task_id", "kind", "target_id", "strength")} for p in planned]}


# --------------------------------------------------------------------------- the packet (pure read)


def task_packet(system: Any, task_id: str, *, token_budget: int = 56_000) -> Dict[str, Any]:
    """Everything a reader needs for one task (PURE READ; the host fetches the verbatim from `verbatim`):
    {task, record (`record_understanding` of the target, with its `pending` marker; a diary target is redacted:
    its words come through the book by `entry_id`), expected_version (a `title.author` task: the title version;
    a `digest.author` task: the digest version), verbatim, sources | evidence | mentions
    (each item WHOLE: {record_id, kind, title, digest, digest_method, observed_at, token_estimate}, newest first),
    ripple (0061 tasks), token_estimate, token_budget, left_out: [{record_id, token_estimate, reason}]}. Items that
    do not fit the budget are left out WHOLE and listed; no text is ever cut. A target that is closed or gone says
    so (`target_state`) so the host can settle the task without a model call."""
    from .records import resolve_digest_assertion
    from .store import TripleQuery
    from .understanding import _current_version, _field_of, record_understanding

    queue: Optional[MemoryTaskQueue] = getattr(system, "tasks", None)
    if queue is None:
        raise ValueError("task_packet needs a home opened with MemorySystem(task_queue=True)")
    t = queue.task(task_id)
    if t is None:
        raise ValueError(f"unknown task {task_id!r}")
    budget = int(token_budget)
    if budget <= 0:
        raise ValueError("token_budget must be positive")
    a = resolve_digest_assertion(system.store, t["target_id"])
    if a is None:
        return {"task": t, "target_state": "gone"}
    attrs_t = a.attributes if isinstance(a.attributes, dict) else {}
    if attrs_t.get("record_kind") == "diary":
        # A pending diary title: the entry's words are read through the book (entry_id), never served here.
        from .understanding import _closures

        closures = _closures(system.journal, a.assertion_id)
        record = {"record_id": t["target_id"], "graph_id": str(a.subject), "assertion_id": str(a.assertion_id or ""),
                  "kind": "diary", "redacted": "diary", "entry_id": attrs_t.get("entry_id"),
                  "title": record_title(attrs_t), "digest": "", "closed": closures[0].kind if closures else None}
        if isinstance(attrs_t.get("pending"), dict):
            record["pending"] = dict(attrs_t["pending"])
    else:
        record = record_understanding(system, t["target_id"])
    field = {"dream.narrate": "narration", "title.author": "title", "digest.author": "digest"}.get(
        t["kind"], _field_of(record["kind"]))
    out: Dict[str, Any] = {"task": t, "record": record, "target_state": "closed" if record["closed"] else "live",
                           "expected_version": _current_version(a.attributes or {}, field),
                           "verbatim": (a.attributes or {}).get("payload_ref"), "token_budget": budget}
    used = token_estimate(record["digest"])
    left_out: List[Dict[str, Any]] = []

    def item(rid: str) -> Optional[Dict[str, Any]]:
        s = resolve_digest_assertion(system.store, rid)
        if s is None:
            return None
        attrs = s.attributes if isinstance(s.attributes, dict) else {}
        if attrs.get("record_kind") == "diary":
            return {"record_id": str(s.subject), "kind": "diary", "redacted": True, "observed_at": s.observed_at,
                    "token_estimate": 0}
        return {"record_id": str(s.subject), "kind": str(attrs.get("record_kind") or ""),
                "title": record_title(attrs), "digest": str(s.object or ""),
                "digest_method": str(attrs.get("digest_method") or ""), "observed_at": str(s.observed_at or ""),
                "token_estimate": token_estimate(str(s.object or ""))}

    def fill(name: str, ids: Sequence[str]) -> None:
        nonlocal used
        items = [x for x in (item(i) for i in ids) if x is not None]
        items.sort(key=lambda x: (x["observed_at"], x["record_id"]), reverse=True)
        kept = []
        for x in items:
            if used + x["token_estimate"] > budget:
                left_out.append({"record_id": x["record_id"], "token_estimate": x["token_estimate"],
                                 "reason": "token_budget"})
                continue
            used += x["token_estimate"]
            kept.append(x)
        out[name] = kept

    edges = [e for e in system.store.query(TripleQuery(subject=a.subject, limit=0))
             if (e.attributes or {}).get("record_edge")]
    if t["kind"] in ("digest.rewrite", "digest.author"):
        fill("sources", [e.object for e in edges if e.predicate == "summarizes"])
    elif t["kind"] == "card.author":
        fill("evidence", [str(s) for s in ((a.attributes or {}).get("known_source_ids") or ())])
    elif t["kind"] == "dream.narrate":
        fill("mentions", [e.object for e in edges if e.predicate == "mentions"])
    elif t["kind"] in ("ripple.reconsider", "ripple.consolidate"):
        from .ripple import ripple_context

        out["ripple"] = ripple_context(system, t)
        if t["kind"] == "ripple.consolidate":
            fill("changed", [c["record_id"] for c in out["ripple"].get("changed", [])])
    out["token_estimate"] = used
    out["left_out"] = left_out
    return out
