"""MemoryGraph: the revision log, the provenance index and their reads (ADR 0003; contract §3).

`MemoryGraph(store, journal=None).apply_revision(rev)` is the write path. In order:

1. PURE checks (nothing read, nothing embedded): the ops normalize (deterministic ids, scope/owner/observed_at
   filled, so the logged revision replays byte-identically), and every asserted memory AND the revision itself name
   sources or derived_from (`ProvenanceRequired` otherwise).
2. Idempotency pre-check: a revision id already in the log returns `applied=False` before any embedding.
3. Embedding (outside any transaction, like `SQLiteTripleStore.add`); the pin a first embedded write sets is written
   INSIDE the transaction, so a refused revision leaves no pin behind.
4. ONE transaction: the derived_from chains are resolved and must reach a ledger source (cycles and chains to
   nothing refused); a store row written outside the graph may only be ADOPTED by an `import`/`migration` revision
   that carries it as stored (only its provenance changes, to the graph shape; the old one stays in the history
   detail); a `close`/`narrow` may only name a memory of this graph (asserted through a revision, or in this one by
   an EARLIER op); then triples (+ FTS rows), window changes, closures, history, provenance and derivation rows and
   the revision row are written; any failure (a `narrow` that would widen, an unknown id) rolls all of it back.

ATOMICITY (SQLite). The graph tables live in the store's file and are written on the STORE'S connection, under the
store's lock, in ONE `BEGIN IMMEDIATE .. COMMIT`. The journal closure joins that same transaction when the journal
is a `SQLiteJournal` on the SAME file (the entity-home and plane-home deployment): `SQLiteJournal` and
`SQLiteTripleStore` hold separate connections, but the journal's seq counter is in-database and its closure insert
runs on any cursor of that file (`SQLiteJournal._append_closure_on`), so one transaction covers both, and
`TripleQuery(active_at=)` and ranked recall (which folds journal closures) can never disagree. When the journal
lives elsewhere (another file, `InMemoryJournal`) no transaction can span both: the closures are appended AFTER the
store transaction commits, the revision row records `journal_applied = 0` until they are, and `repair()` re-appends
the closures of any revision a crash left at 0 (closure ids are deterministic, so the journal's supplied-id dedup
makes the repair idempotent).

InMemoryTripleStore: same semantics, applied under the store's lock with an undo log (a failing op rolls back what
the revision already did, the embedding pin included); the graph state is shared by every MemoryGraph over the same
store object; closures always go to the journal after the apply (`journal_applied` as above).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import weakref
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple, Union

from ..canonical_text import canonical_text as _canonical_text
from ..canonical_text import is_record_edge as _is_record_edge
from ..embedding_pin import (
    build_pin,
    check_add_dimension,
    embed_texts_degradable,
    embedder_model_id,
    warn_first_write_pin,
)
from ..in_memory_store import InMemoryTripleStore
from ..journal import ClosureRecord
from ..journal_common import normalize_iso_ts as _instant
from ..journal_sqlite import SQLiteJournal
from ..models import TripleAssertion, canonicalize_term, utc_now_iso_seconds
from ..sqlite_store import SQLiteTripleStore
from ..vector_matrix import encode_vector
from .provenance import Provenance, ProvenanceRequired, SourceRef
from .revisions import Revision, RevisionOp, RevisionResult

# -- named constants (ADR 0003 enforcement: page sizes and bounds live in one place) --------------------------------
# Measured 2026-10-27 on a temporary SQLite home with 50,000 graph-asserted memories (tests/bench/bench_graph.py; the
# full table is in backlog 0056 "Report"; the plans are pinned by tests/test_graph_performance.py). Every read below
# is an index read whose cost is linear in what it returns: history 0.02 ms, sources_of 0.04 ms (transitive over a
# derived memory 0.10 ms), derived_from_source(step) 0.05 ms, a run walk returning 128 memories 0.8 ms, a change-feed
# page of 100 revisions 4 ms (decoding dominates). So the bounds are set by what a caller can use in one call, not
# by cost: a full 1000-memory lineage walk stays in single-digit milliseconds.
#: Default change-feed page (`revisions(limit=)`).
DEFAULT_REVISION_PAGE = 100
#: The largest page any one graph read returns; a larger `limit` is clamped to it.
MAX_READ_LIMIT = 1000
#: Default bound of `sources_of` / `derived_from_source` / `history`.
DEFAULT_READ_LIMIT = 200
#: The most memories one lineage walk (`sources_of(transitive=True)`, `derived_from_source`) visits.
MAX_LINEAGE_VISITS = 1000
#: The predicate of a record's digest assertion: its SUBJECT is the record's graph id (records.py v1 encoding),
#: accepted wherever a memory id is (resolved to the digest's assertion id, the one namespace of the index).
DIGEST_PREDICATE = "dcterms:abstract"
#: The causes whose revisions may adopt a store row written outside the graph (ADR 0003 consequences: existing
#: stores are imported / projected once).
ADOPTING_CAUSES = ("import", "migration")

_EVENT_ASSERTED, _EVENT_CLOSED, _EVENT_NARROWED = "asserted", "closed", "narrowed"
_EVENT_REOBSERVED = "re-observed"  # an assert of a claim the graph already holds open: new sources, no new row
#: How a provenance-index row reached a memory: the memory's own provenance, or the revision that wrote it (a memory
#: whose own provenance is lineage only is still found from the step that produced it).
VIA_MEMORY, VIA_REVISION = "memory", "revision"
#: Columns added to the provenance index after it first shipped: (name, DDL). Migrated in place when a graph opens.
_PROV_ADDED_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("via", "TEXT NOT NULL DEFAULT 'memory'"),
    # the memory's owner, denormalized (a memory's owner never changes: adoption keeps it, M6 refuses a different
    # claim under a held id) so the owner gate `names_ref` is ONE index probe; '' for no owner
    ("owner_id", "TEXT NOT NULL DEFAULT ''"),
)

# The triple store's column set this module's insert path writes. Checked when a graph opens: a store schema change
# (backlog 0058's binary vectors, say) must update `_sqlite_rows` too, so it fails loudly here instead of writing a
# stale row shape.
_STORE_COLUMNS = (
    "assertion_id", "subject", "predicate", "object", "scope", "owner_id", "observed_at", "valid_from",
    "valid_until", "confidence", "provenance_json", "attributes_json", "text", "embedding",
)


def _det_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _check_limit(limit: int, name: str = "limit") -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"{name} must be a positive int (every graph read is bounded; got {limit!r})")
    return min(int(limit), MAX_READ_LIMIT)


def _content(a: TripleAssertion) -> Tuple[Any, ...]:
    """Everything a stored claim IS, except its provenance (what adoption may change) and its id."""
    return (a.subject, a.predicate, a.object, a.scope, a.owner_id, a.observed_at, a.valid_from, a.valid_until,
            a.confidence, _dump(a.attributes))


def _identity(a: TripleAssertion) -> Tuple[Any, ...]:
    """What makes a re-assert of a memory the graph holds the SAME claim: its terms, partition and start. (The end,
    observation time and provenance may legitimately differ on a replayed or re-sent assert: the graph may have
    closed it since, and a re-sent op fills observed_at from its own revision.)"""
    return (a.subject, a.predicate, a.object, a.scope, a.owner_id,
            _instant(a.valid_from) if a.valid_from else None)


def _closure_record(rev: Revision, payload: Mapping[str, Any]) -> ClosureRecord:
    """The journal closure of one `close` op: kind, reason and successor from the op; the cause, the revision and
    the ripple fields on its provenance. `observed_at` is the revision's observation time (ADR 0003 decision 5),
    the record time rides the provenance and the journal seq."""
    return ClosureRecord(
        assertion_id=payload["assertion_id"],
        kind=payload["kind"],
        reason=payload["reason"],
        replacement_ids=tuple(payload.get("replacement_ids") or ()),
        observed_at=rev.occurred_at,
        actor=rev.provenance.actor,
        provenance={
            "revision_id": rev.revision_id,
            "cause": rev.cause,
            "recorded_at": rev.recorded_at,
            "ripple_source": payload.get("ripple_source"),
            "ripple_hops": payload.get("ripple_hops"),
            "valid_until": payload["valid_until"],
        },
        closure_id=_det_id(rev.revision_id, "close", payload["assertion_id"]),
    )


@dataclass
class _Prepared:
    revision: Revision                      # ops normalized: ids, scope/owner, observed_at filled
    assertions: List[TripleAssertion]       # assert ops in order (provenance = the effective graph-shape dict)
    effective: Dict[str, Provenance]        # assertion_id -> effective provenance
    aliases: Dict[str, str]                 # digest subject (graph id) -> assertion_id, in this revision


def _prepare(rev: Revision) -> _Prepared:
    """Pure: normalize the revision so its logged form replays byte-identically, resolve each asserted memory's
    provenance (its own when the payload carries one, else the revision's), and refuse an ungrounded shape (a memory
    or a revision naming neither sources nor derived_from) before anything is read or embedded."""
    ops: List[RevisionOp] = []
    assertions: List[TripleAssertion] = []
    effective: Dict[str, Provenance] = {}
    aliases: Dict[str, str] = {}
    for index, op in enumerate(rev.ops):
        if op.op != "assert":
            ops.append(op)
            continue
        payload = dict(op.payload)
        if not (isinstance(payload.get("scope"), str) and payload["scope"].strip()):
            payload["scope"] = rev.scope
        if not (isinstance(payload.get("owner_id"), str) and payload["owner_id"].strip()) and rev.owner_id:
            payload["owner_id"] = rev.owner_id
        if not (isinstance(payload.get("observed_at"), str) and payload["observed_at"].strip()):
            payload["observed_at"] = rev.occurred_at  # observation time of the claim = the revision's
        if not (isinstance(payload.get("assertion_id"), str) and payload["assertion_id"].strip()):
            payload["assertion_id"] = _det_id(rev.revision_id, "assert", str(index))
        raw = payload.get("provenance")
        prov = Provenance.from_dict(raw) if raw else rev.provenance
        assertion = TripleAssertion.from_dict({**payload, "provenance": prov.to_dict()})
        aid = str(assertion.assertion_id)
        if aid in effective:
            raise ValueError(f"revision {rev.revision_id!r} asserts {aid!r} twice")
        if payload.get("adoption") is not None and rev.cause not in ADOPTING_CAUSES:
            raise ValueError(f"revision {rev.revision_id!r} ({rev.cause!r}) carries an adoption note on {aid!r}; "
                             f"only {list(ADOPTING_CAUSES)} revisions adopt store rows")
        if not prov.is_grounded():
            raise ProvenanceRequired(
                f"revision {rev.revision_id!r}: memory {aid!r} names neither ledger sources nor derived_from "
                "(every memory is sourced or derived; never neither)"
            )
        effective[aid] = prov
        assertions.append(assertion)
        if assertion.predicate == DIGEST_PREDICATE:
            aliases.setdefault(assertion.subject, aid)
        ops.append(RevisionOp("assert", payload))
    if not rev.provenance.is_grounded():
        raise ProvenanceRequired(
            f"revision {rev.revision_id!r}: its provenance names neither ledger sources nor derived_from "
            "(the cause of every change must be traceable)"
        )
    return _Prepared(replace(rev, ops=tuple(ops)), assertions, effective, aliases)


# ---------------------------------------------------------------------------------------------------------------
# Backends: one transaction surface (`_Tx`) and the reads, per store kind.
# ---------------------------------------------------------------------------------------------------------------


class _SQLiteTx:
    def __init__(self, backend: "_SQLiteBackend", cur: sqlite3.Cursor) -> None:
        self.b, self.cur = backend, cur

    def revision_seq(self, rid: str) -> Optional[int]:
        row = self.cur.execute(self.b.sql["revision_seq"], (rid,)).fetchone()
        return int(row[0]) if row else None

    def memory_known(self, mid: str) -> bool:
        return self.cur.execute(self.b.sql["memory_known"], (mid, _EVENT_ASSERTED)).fetchone() is not None

    def open_same_claim(self, a: TripleAssertion) -> Optional[str]:
        """The first (rowid order) OPEN memory of this graph holding the same claim as `a` (`_identity`)."""
        for row in self.cur.execute(
            f"SELECT assertion_id, subject, predicate, object, scope, owner_id, observed_at, valid_from, valid_until, "
            f"confidence, provenance_json, attributes_json FROM {self.b.table} WHERE subject = ? AND predicate = ? "
            "AND object = ? AND valid_until IS NULL ORDER BY rowid LIMIT ?",
            (a.subject, a.predicate, a.object, MAX_READ_LIMIT)).fetchall():
            held = SQLiteTripleStore._row_to_assertion(row)
            if _identity(held) == _identity(a) and self.memory_known(str(held.assertion_id)):
                return str(held.assertion_id)
        return None

    def closing_revision(self, mid: str) -> Optional[str]:
        row = self.cur.execute(self.b.sql["closing_revision"], (mid, _EVENT_CLOSED)).fetchone()
        return str(row[0]) if row else None

    def digest_assertion_for(self, graph_id: str) -> Optional[str]:
        row = self.cur.execute(
            f"SELECT assertion_id FROM {self.b.table} WHERE subject = ? AND predicate = ? "
            "ORDER BY observed_at DESC, assertion_id DESC LIMIT 1",
            (canonicalize_term(graph_id), DIGEST_PREDICATE),
        ).fetchone()
        return str(row[0]) if row else None

    def existing_ids(self, ids: Sequence[str]) -> set:
        found: set = set()
        for start in range(0, len(ids), 500):
            chunk = list(ids[start:start + 500])
            marks = ", ".join("?" for _ in chunk)
            found.update(r[0] for r in self.cur.execute(
                f"SELECT assertion_id FROM {self.b.table} WHERE assertion_id IN ({marks})", chunk).fetchall())
        return found

    def stored(self, aid: str) -> TripleAssertion:
        row = self.cur.execute(
            "SELECT assertion_id, subject, predicate, object, scope, owner_id, observed_at, valid_from, valid_until, "
            f"confidence, provenance_json, attributes_json FROM {self.b.table} WHERE assertion_id = ?", (aid,)
        ).fetchone()
        return SQLiteTripleStore._row_to_assertion(row)

    def set_provenance(self, aid: str, provenance: Dict[str, Any]) -> None:
        self.cur.execute(f"UPDATE {self.b.table} SET provenance_json = ? WHERE assertion_id = ?",
                         (json.dumps(provenance, ensure_ascii=False, separators=(",", ":")), aid))

    def write_pin(self, pin: Optional[Dict[str, Any]]) -> None:
        if pin is not None:
            self.b.store._write_pin(pin, cursor=self.cur)

    def insert_assertions(self, rows: List[tuple]) -> None:
        if not rows:
            return
        cols = ", ".join(_STORE_COLUMNS)
        marks = ", ".join("?" for _ in _STORE_COLUMNS)
        self.cur.executemany(f"INSERT OR IGNORE INTO {self.b.table} ({cols}) VALUES ({marks})", rows)
        self.b.store._sync_fts_index(self.cur)  # keyword index rides the same transaction (store.add parity)

    def window(self, aid: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
        row = self.cur.execute(
            f"SELECT valid_from, valid_until FROM {self.b.table} WHERE assertion_id = ?", (aid,)).fetchone()
        return (row[0], row[1]) if row else None

    def end_row(self, aid: str, until: str) -> bool:
        """Set the row's end (the caller decided it moves: open, or later than `until`)."""
        self.cur.execute(f"UPDATE {self.b.table} SET valid_until = ? WHERE assertion_id = ?", (until, aid))
        return int(self.cur.rowcount or 0) > 0

    def narrow_row(self, aid: str, until: str) -> bool:
        return SQLiteTripleStore._narrow_on(self.cur, self.b.table, aid, until)

    def write_closure(self, closure: ClosureRecord) -> bool:
        """True when written in this transaction; False when the caller must append it after commit."""
        if not self.b.same_file_journal:
            return False
        self.b.journal._append_closure_on(self.cur, closure)
        return True

    def add_history(self, mid: str, event: str, at: str, rid: str, detail: Dict[str, Any]) -> None:
        self.cur.execute(
            f"INSERT INTO {self.b.t_hist} (memory_id, event, at, revision_id, detail_json) VALUES (?, ?, ?, ?, ?)",
            (mid, event, at, rid, _dump(detail)))

    def add_source(self, mid: str, ref: SourceRef, rid: str, owner: Optional[str], via: str = VIA_MEMORY) -> None:
        """First row per (memory, ref key) wins: write the memory's own refs before the revision's."""
        self.cur.execute(
            f"INSERT OR IGNORE INTO {self.b.t_prov} (memory_id, ref_key, ref_kind, run_id, revision_id, ref_json, "
            "via, owner_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, ref.key(), ref.kind, ref.run_id, rid, _dump(ref.to_dict()), via, owner or ""))

    def add_derivation(self, mid: str, from_id: str, rid: str) -> None:
        self.cur.execute(
            f"INSERT OR IGNORE INTO {self.b.t_der} (memory_id, from_id, revision_id) VALUES (?, ?, ?)",
            (mid, from_id, rid))

    def insert_revision(self, rev: Revision, journal_applied: bool) -> int:
        self.cur.execute(
            f"INSERT INTO {self.b.t_rev} (revision_id, scope, owner_id, cause, occurred_at, recorded_at, ops_json, "
            "provenance_json, summary, journal_applied) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rev.revision_id, rev.scope, rev.owner_id, rev.cause, rev.occurred_at, rev.recorded_at,
             _dump([o.to_dict() for o in rev.ops]), _dump(rev.provenance.to_dict()), rev.summary,
             1 if journal_applied else 0))
        return int(self.cur.lastrowid)


def _same_file(a: Any, b: Any) -> bool:
    try:
        return os.path.samefile(str(a), str(b))
    except OSError:
        return False


class _SQLiteBackend:
    def __init__(self, store: SQLiteTripleStore, journal: Any) -> None:
        self.store, self.journal = store, journal
        self.table = store._table
        # One graph per store table: the default table keeps the contract's names; a custom table name prefixes
        # them so two stores sharing a file never share a revision log.
        prefix = "memg_" if self.table == "triples" else f"memg_{self.table}_"
        self.t_rev, self.t_prov = f"{prefix}revisions", f"{prefix}provenance"
        self.t_der, self.t_hist = f"{prefix}derivations", f"{prefix}history"
        self.same_file_journal = isinstance(journal, SQLiteJournal) and _same_file(store._path, journal._path)
        h, p, d, r = self.t_hist, self.t_prov, self.t_der, self.t_rev
        # Every keyed read of the graph, in one place, so tests/test_graph_performance.py EXPLAINs the exact SQL
        # that runs (each must be an index search; a dropped index turns its plan into a SCAN).
        self.sql: Dict[str, str] = {
            "revision_seq": f"SELECT seq FROM {r} WHERE revision_id = ?",
            "memory_known": f"SELECT 1 FROM {h} WHERE memory_id = ? AND event = ? LIMIT 1",
            "closing_revision": f"SELECT revision_id FROM {h} WHERE memory_id = ? AND event = ? ORDER BY seq LIMIT 1",
            "history": (f"SELECT h.event, h.at, h.revision_id, h.detail_json, r.cause FROM {h} h "
                        f"JOIN {r} r ON r.revision_id = h.revision_id WHERE h.memory_id = ? ORDER BY h.seq LIMIT ?"),
            "sources": f"SELECT ref_json, via, revision_id FROM {p} WHERE memory_id = ? ORDER BY rowid LIMIT ?",
            "parents": f"SELECT from_id FROM {d} WHERE memory_id = ? ORDER BY rowid LIMIT ?",
            "children": f"SELECT memory_id FROM {d} WHERE from_id = ? ORDER BY rowid LIMIT ?",
            "with_ref_key": f"SELECT memory_id FROM {p} WHERE ref_key = ? ORDER BY rowid LIMIT ?",
            "with_run": f"SELECT memory_id FROM {p} WHERE run_id = ? ORDER BY rowid",
            # the owner gate: does any memory of these owners name this ref? ({marks}: one ? per owner)
            "names_ref_key": f"SELECT 1 FROM {p} WHERE ref_key = ? AND owner_id IN ({{marks}}) LIMIT 1",
            "names_ref_run": f"SELECT 1 FROM {p} WHERE run_id = ? AND owner_id IN ({{marks}}) LIMIT 1",
            "revisions_page": f"SELECT * FROM {r} WHERE seq > ? ORDER BY seq LIMIT ?",
            "log_head": f"SELECT MAX(seq) FROM {r}",
            "pending_journal": f"SELECT * FROM {r} WHERE journal_applied = 0 ORDER BY seq LIMIT ?",
            "closed_payload": (f"SELECT detail_json FROM {h} WHERE memory_id = ? AND revision_id = ? AND event = ? "
                               "LIMIT 1"),
        }
        self._ensure_graph_schema()

    def _ensure_graph_schema(self) -> None:
        with self.store._lock:
            cur = self.store._conn.cursor()
            columns = tuple(r[1] for r in cur.execute(f"PRAGMA table_info({self.table})").fetchall())
            if set(columns) != set(_STORE_COLUMNS):
                raise RuntimeError(
                    f"abstractmemory.graph: the triple table {self.table!r} has columns {sorted(columns)}, the graph's "
                    f"insert path writes {sorted(_STORE_COLUMNS)}; update graph._sqlite_rows with the store schema"
                )
            # Opening a graph on an existing home is a READ: when every table and index is there, no DDL
            # transaction runs (a reader needs no write lock and never waits behind a writer).
            expected = (self.t_rev, self.t_prov, self.t_der, self.t_hist, f"idx_{self.t_prov}_ref_key",
                        f"idx_{self.t_prov}_run_id", f"idx_{self.t_der}_from", f"idx_{self.t_hist}_memory",
                        f"idx_{self.t_rev}_pending", f"idx_{self.t_prov}_ref_owner", f"idx_{self.t_prov}_run_owner")
            marks = ", ".join("?" for _ in expected)
            present = cur.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE name IN ({marks})", expected).fetchone()
            prov_cols = {r[1] for r in cur.execute(f"PRAGMA table_info({self.t_prov})").fetchall()}
            if int(present[0]) == len(expected) and all(c in prov_cols for c, _ in _PROV_ADDED_COLUMNS):
                return
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {self.t_rev} ("
                    "seq INTEGER PRIMARY KEY AUTOINCREMENT, revision_id TEXT NOT NULL UNIQUE, scope TEXT NOT NULL, "
                    "owner_id TEXT NOT NULL, cause TEXT NOT NULL, occurred_at TEXT NOT NULL, "
                    "recorded_at TEXT NOT NULL, ops_json TEXT NOT NULL, provenance_json TEXT NOT NULL, "
                    "summary TEXT, journal_applied INTEGER NOT NULL DEFAULT 1)")
                # Partial: holds only the revisions awaiting their off-file journal closures (normally none), so
                # repair() is an index read however long the log is.
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.t_rev}_pending ON {self.t_rev}(seq) "
                            "WHERE journal_applied = 0")
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {self.t_prov} ("
                    "memory_id TEXT NOT NULL, ref_key TEXT NOT NULL, ref_kind TEXT NOT NULL, run_id TEXT, "
                    "revision_id TEXT NOT NULL, ref_json TEXT NOT NULL, PRIMARY KEY (memory_id, ref_key))")
                have = {r[1] for r in cur.execute(f"PRAGMA table_info({self.t_prov})").fetchall()}
                for name, ddl in _PROV_ADDED_COLUMNS:  # in-place upgrade of a home written before the column
                    if name not in have:
                        cur.execute(f"ALTER TABLE {self.t_prov} ADD COLUMN {name} {ddl}")
                        if name == "owner_id":  # backfill from the memory's row
                            cur.execute(f"UPDATE {self.t_prov} SET owner_id = COALESCE((SELECT t.owner_id FROM "
                                        f"{self.table} t WHERE t.assertion_id = {self.t_prov}.memory_id), '')")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.t_prov}_ref_owner ON {self.t_prov}(ref_key, owner_id)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.t_prov}_run_owner ON {self.t_prov}(run_id, owner_id)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.t_prov}_ref_key ON {self.t_prov}(ref_key)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.t_prov}_run_id ON {self.t_prov}(run_id)")
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {self.t_der} ("
                    "memory_id TEXT NOT NULL, from_id TEXT NOT NULL, revision_id TEXT NOT NULL, "
                    "PRIMARY KEY (memory_id, from_id))")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.t_der}_from ON {self.t_der}(from_id)")
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {self.t_hist} ("
                    "seq INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT NOT NULL, event TEXT NOT NULL, "
                    "at TEXT NOT NULL, revision_id TEXT NOT NULL, detail_json TEXT NOT NULL)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.t_hist}_memory ON {self.t_hist}(memory_id, seq)")
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise

    def prepare_rows(self, assertions: List[TripleAssertion]) -> Tuple[List[tuple], Optional[Dict[str, Any]], bool]:
        return _sqlite_rows(self.store, assertions)

    @contextmanager
    def transaction(self) -> Iterator[_SQLiteTx]:
        with self.store._lock:
            cur = self.store._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                yield _SQLiteTx(self, cur)
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise

    def _read(self, sql: str, params: Sequence[Any]) -> List[sqlite3.Row]:
        with self.store._lock:
            return self.store._conn.cursor().execute(sql, tuple(params)).fetchall()

    # reads
    def applied_seq(self, rid: str) -> Optional[int]:
        with self.store._lock:
            return _SQLiteTx(self, self.store._conn.cursor()).revision_seq(rid)

    def resolve(self, mid: str) -> Optional[str]:
        with self.store._lock:
            tx = _SQLiteTx(self, self.store._conn.cursor())
            if tx.memory_known(mid):
                return mid
            aid = tx.digest_assertion_for(mid)
            return aid if aid and tx.memory_known(aid) else None

    def history(self, mid: str, limit: int) -> List[Dict[str, Any]]:
        rows = self._read(self.sql["history"], (mid, limit))
        return [{"event": r["event"], "at": r["at"], "revision_id": r["revision_id"], "cause": r["cause"],
                 "detail": json.loads(r["detail_json"])} for r in rows]

    def sources(self, mid: str, limit: int) -> List[Tuple[SourceRef, str, str]]:
        rows = self._read(self.sql["sources"], (mid, limit))
        return [(SourceRef.from_dict(json.loads(r[0])), r[1], r[2]) for r in rows]

    def parents(self, mid: str, limit: int) -> List[str]:
        return [r[0] for r in self._read(self.sql["parents"], (mid, limit))]

    def children(self, fid: str, limit: int) -> List[str]:
        return [r[0] for r in self._read(self.sql["children"], (fid, limit))]

    def names_ref(self, ref: SourceRef, owners: List[str]) -> bool:
        name, key = ("names_ref_run", ref.run_id) if ref.kind == "run" else ("names_ref_key", ref.key())
        sql = self.sql[name].format(marks=", ".join("?" for _ in owners))
        return bool(self._read(sql, (key, *owners)))

    def with_ref(self, ref: SourceRef, limit: int) -> List[str]:
        if ref.kind != "run":  # one row per (memory, key): the key index answers in insertion (rowid) order
            return [r[0] for r in self._read(self.sql["with_ref_key"], (ref.key(), limit))]
        # A run ref matches everything stamped with the run (its run ref and its steps/artifacts/messages/diary
        # entries): one memory may hold several such refs, so the run_id index is stepped lazily (rowid order, no
        # sort) and deduplicated until `limit` distinct memories, never reading past what it returns.
        out: List[str] = []
        seen: set = set()
        with self.store._lock:
            cur = self.store._conn.cursor().execute(self.sql["with_run"], (ref.run_id,))
            try:
                while len(out) < limit:
                    batch = cur.fetchmany(limit)
                    if not batch:
                        break
                    for (mid,) in batch:
                        if mid not in seen:
                            seen.add(mid)
                            out.append(mid)
                            if len(out) >= limit:
                                break
            finally:
                cur.close()
        return out

    def revisions_page(self, after: int, limit: int) -> List[Tuple[int, Revision]]:
        rows = self._read(self.sql["revisions_page"], (after, limit))
        return [(int(r["seq"]), _row_revision(r)) for r in rows]

    def log_head(self) -> int:
        row = self._read(self.sql["log_head"], ())[0]
        return int(row[0] or 0)

    def pending_journal(self, limit: int) -> List[Revision]:
        rows = self._read(self.sql["pending_journal"], (limit,))
        return [_row_revision(r) for r in rows]

    def closed_payload(self, aid: str, rid: str) -> Optional[Dict[str, Any]]:
        rows = self._read(self.sql["closed_payload"], (aid, rid, _EVENT_CLOSED))
        return json.loads(rows[0][0]) if rows else None

    def mark_journal_applied(self, rid: str) -> None:
        with self.store._lock:
            self.store._conn.cursor().execute(
                f"UPDATE {self.t_rev} SET journal_applied = 1 WHERE revision_id = ?", (rid,))


def _row_revision(r: sqlite3.Row) -> Revision:
    return Revision.from_dict({
        "revision_id": r["revision_id"], "scope": r["scope"], "owner_id": r["owner_id"], "cause": r["cause"],
        "occurred_at": r["occurred_at"], "recorded_at": r["recorded_at"], "ops": json.loads(r["ops_json"]),
        "provenance": json.loads(r["provenance_json"]), "summary": r["summary"],
    })


def _sqlite_rows(store: SQLiteTripleStore,
                 assertions: List[TripleAssertion]) -> Tuple[List[tuple], Optional[Dict[str, Any]], bool]:
    """Row tuples for `_STORE_COLUMNS`, embedded BEFORE the transaction exactly as `SQLiteTripleStore.add` does
    (edges never embedded; a dead embedder degrades to vectorless rows with its #FALLBACK; a wrong-dimension vector
    aborts; vectors stored as float32 BLOBs via `vector_matrix.encode_vector`, so the store's matrix cache picks the
    graph's rows up at its next sync by rowid, exactly as it does `add`'s). Returns the rows, the pin the transaction must write (a pinless store pins at its first embedded
    write; a dimensionless pin gains its dimension) or None, and whether that is a first-write pin (warned, loudly,
    once the transaction commits)."""
    vectors: Optional[Dict[int, List[float]]] = None
    pin_update: Optional[Dict[str, Any]] = None
    first_write = False
    embedder = store._embedder
    if embedder is not None and assertions:
        embeddable = [(i, _canonical_text(a)) for i, a in enumerate(assertions) if not _is_record_edge(a)]
        embedded = (embed_texts_degradable(embedder, [t for _, t in embeddable], store.embedding_pin())
                    if embeddable else None)
        if embeddable and embedded is not None:
            vectors = {i: v for (i, _), v in zip(embeddable, embedded)}
            pin = store.embedding_pin()
            dim = check_add_dimension(pin, vectors.values())
            if dim is not None:
                if pin is None:
                    pin_update = build_pin(embedder_model_id(embedder), dim, source="first-write",
                                           claimed_by="embedder-attribute")
                    first_write = True
                elif pin.get("dimension") is None:
                    pin_update = dict(pin, dimension=dim)
    rows: List[tuple] = []
    for i, a in enumerate(assertions):
        vector = vectors.get(i) if vectors is not None else None
        rows.append((
            a.assertion_id, a.subject, a.predicate, a.object, a.scope, a.owner_id, a.observed_at, a.valid_from,
            a.valid_until, a.confidence,
            json.dumps(a.provenance, ensure_ascii=False, separators=(",", ":")),
            json.dumps(a.attributes, ensure_ascii=False, separators=(",", ":")),
            _canonical_text(a),
            encode_vector(vector) if vector is not None else None,  # float32 BLOB, as SQLiteTripleStore.add (0058)
        ))
    return rows, pin_update, first_write


class _MemoryTx:
    """InMemory transaction: every mutation registers its undo; a failure replays them in reverse."""

    def __init__(self, backend: "_MemoryBackend") -> None:
        self.b = backend
        self.undo: List[Callable[[], None]] = []

    def rollback(self) -> None:
        for fn in reversed(self.undo):
            fn()

    def _row(self, aid: str) -> Optional[dict]:
        for row in self.b.store._rows:
            if row.get("assertion_id") == aid:
                return row
        return None

    def revision_seq(self, rid: str) -> Optional[int]:
        entry = self.b.rev_by_id.get(rid)
        return entry["seq"] if entry else None

    def memory_known(self, mid: str) -> bool:
        return mid in self.b.known

    def open_same_claim(self, a: TripleAssertion) -> Optional[str]:
        for row in self.b.store._rows:
            held = row.get("assertion")
            if (isinstance(held, TripleAssertion) and held.valid_until is None and _identity(held) == _identity(a)
                    and str(row.get("assertion_id")) in self.b.known):
                return str(row.get("assertion_id"))
        return None

    def closing_revision(self, mid: str) -> Optional[str]:
        for h in self.b.hist:
            if h["memory_id"] == mid and h["event"] == _EVENT_CLOSED:
                return str(h["revision_id"])
        return None

    def digest_assertion_for(self, graph_id: str) -> Optional[str]:
        subject = canonicalize_term(graph_id)
        best: Optional[Tuple[str, str]] = None
        for row in self.b.store._rows:
            a = row.get("assertion")
            if isinstance(a, TripleAssertion) and a.subject == subject and a.predicate == DIGEST_PREDICATE:
                key = (a.observed_at or "", str(row.get("assertion_id")))
                best = key if best is None or key > best else best
        return best[1] if best else None

    def existing_ids(self, ids: Sequence[str]) -> set:
        return {i for i in ids if i in self.b.store._ids}

    def stored(self, aid: str) -> TripleAssertion:
        row = self._row(aid)
        return row["assertion"] if row is not None else None  # type: ignore[return-value]

    def set_provenance(self, aid: str, provenance: Dict[str, Any]) -> None:
        row = self._row(aid)
        before = row["assertion"]
        row["assertion"] = replace(before, provenance=dict(provenance))
        self.undo.append(lambda: row.__setitem__("assertion", before))

    def write_pin(self, pin: Optional[Dict[str, Any]]) -> None:
        return None  # InMemoryTripleStore.add pins inside the apply; insert_assertions' undo restores it

    def insert_assertions(self, assertions: List[TripleAssertion]) -> None:
        store = self.b.store
        new = [a for a in assertions if a.assertion_id not in store._ids]
        if not new:
            return
        ids = {str(a.assertion_id) for a in new}
        pin_before = store._embedding_pin

        def _undo() -> None:
            store._rows[:] = [r for r in store._rows if r.get("assertion_id") not in ids]
            store._ids.difference_update(ids)
            store._embedding_pin = pin_before

        self.undo.append(_undo)
        store.add(new)

    def window(self, aid: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
        row = self._row(aid)
        a = row.get("assertion") if row else None
        return (a.valid_from, a.valid_until) if isinstance(a, TripleAssertion) else None

    def _mutate(self, aid: str, fn: Callable[[], bool]) -> bool:
        row = self._row(aid)
        before = row.get("assertion") if row else None
        changed = fn()
        if changed and row is not None:
            self.undo.append(lambda: row.__setitem__("assertion", before))
        return changed

    def end_row(self, aid: str, until: str) -> bool:
        row = self._row(aid)
        if row is None or not isinstance(row.get("assertion"), TripleAssertion):
            return False
        before = row["assertion"]
        row["assertion"] = replace(before, valid_until=until)
        self.undo.append(lambda: row.__setitem__("assertion", before))
        return True

    def narrow_row(self, aid: str, until: str) -> bool:
        return self._mutate(aid, lambda: self.b.store.narrow_assertion(aid, until))

    def write_closure(self, closure: ClosureRecord) -> bool:
        return False  # no shared transaction with any journal: appended after the apply

    def add_history(self, mid: str, event: str, at: str, rid: str, detail: Dict[str, Any]) -> None:
        b = self.b
        b.hist.append({"memory_id": mid, "event": event, "at": at, "revision_id": rid,
                       "detail": json.loads(_dump(detail))})
        newly_known = event == _EVENT_ASSERTED and mid not in b.known
        if newly_known:
            b.known.add(mid)

        def _undo() -> None:
            b.hist.pop()
            if newly_known:
                b.known.discard(mid)

        self.undo.append(_undo)

    def add_source(self, mid: str, ref: SourceRef, rid: str, owner: Optional[str], via: str = VIA_MEMORY) -> None:
        b, key = self.b, ref.key()
        if (mid, key) in b.prov_keys:
            return
        b.provenance.append((mid, key, ref, rid, via, owner or ""))
        b.prov_keys.add((mid, key))

        def _undo() -> None:
            b.provenance.pop()
            b.prov_keys.discard((mid, key))

        self.undo.append(_undo)

    def add_derivation(self, mid: str, from_id: str, rid: str) -> None:
        b = self.b
        if (mid, from_id) in b.der_keys:
            return
        b.derivations.append((mid, from_id, rid))
        b.der_keys.add((mid, from_id))

        def _undo() -> None:
            b.derivations.pop()
            b.der_keys.discard((mid, from_id))

        self.undo.append(_undo)

    def insert_revision(self, rev: Revision, journal_applied: bool) -> int:
        b = self.b
        entry = {"seq": len(b.revisions) + 1, "revision": rev, "journal_applied": bool(journal_applied)}
        b.revisions.append(entry)
        b.rev_by_id[rev.revision_id] = entry

        def _undo() -> None:
            b.revisions.pop()
            b.rev_by_id.pop(rev.revision_id, None)

        self.undo.append(_undo)
        return int(entry["seq"])


class _MemoryBackend:
    """The graph tables of one InMemoryTripleStore. Shared by every MemoryGraph over the same store object (the
    SQLite tables are shared through the file; this is the in-process equivalent)."""

    def __init__(self, store: InMemoryTripleStore) -> None:
        self.store = store
        self._lock = threading.RLock()
        self.revisions: List[Dict[str, Any]] = []
        self.rev_by_id: Dict[str, Dict[str, Any]] = {}
        self.hist: List[Dict[str, Any]] = []
        self.provenance: List[Tuple[str, str, SourceRef, str, str, str]] = []  # memory, key, ref, revision, via, owner
        self.prov_keys: set = set()
        self.derivations: List[Tuple[str, str, str]] = []
        self.der_keys: set = set()
        self.known: set = set()

    def prepare_rows(self, assertions: List[TripleAssertion]) -> Tuple[List[TripleAssertion], None, bool]:
        return list(assertions), None, False  # the store embeds (and pins) inside add()

    @contextmanager
    def transaction(self) -> Iterator[_MemoryTx]:
        with self.store._lock, self._lock:
            tx = _MemoryTx(self)
            try:
                yield tx
            except BaseException:
                tx.rollback()
                raise

    def applied_seq(self, rid: str) -> Optional[int]:
        with self._lock:
            return _MemoryTx(self).revision_seq(rid)

    def resolve(self, mid: str) -> Optional[str]:
        with self.store._lock, self._lock:
            if mid in self.known:
                return mid
            aid = _MemoryTx(self).digest_assertion_for(mid)
            return aid if aid and aid in self.known else None

    def history(self, mid: str, limit: int) -> List[Dict[str, Any]]:
        with self._lock:
            out = []
            for h in self.hist:
                if h["memory_id"] != mid:
                    continue
                cause = self.rev_by_id[h["revision_id"]]["revision"].cause
                out.append({"event": h["event"], "at": h["at"], "revision_id": h["revision_id"], "cause": cause,
                            "detail": json.loads(_dump(h["detail"]))})
                if len(out) >= limit:
                    break
            return out

    def sources(self, mid: str, limit: int) -> List[Tuple[SourceRef, str, str]]:
        with self._lock:
            return [(ref, via, rid) for m, _, ref, rid, via, _ in self.provenance if m == mid][:limit]

    def parents(self, mid: str, limit: int) -> List[str]:
        with self._lock:
            return [f for m, f, _ in self.derivations if m == mid][:limit]

    def children(self, fid: str, limit: int) -> List[str]:
        with self._lock:
            return [m for m, f, _ in self.derivations if f == fid][:limit]

    def names_ref(self, ref: SourceRef, owners: List[str]) -> bool:
        wanted = set(owners)
        with self._lock:
            for _, key, r, _, _, owner in self.provenance:
                hit = (r.run_id == ref.run_id) if ref.kind == "run" else (key == ref.key())
                if hit and owner in wanted:
                    return True
        return False

    def with_ref(self, ref: SourceRef, limit: int) -> List[str]:
        with self._lock:
            out: List[str] = []
            for m, key, r, _, _, _ in self.provenance:
                hit = (r.run_id == ref.run_id) if ref.kind == "run" else (key == ref.key())
                if hit and m not in out:
                    out.append(m)
                    if len(out) >= limit:
                        break
            return out

    def revisions_page(self, after: int, limit: int) -> List[Tuple[int, Revision]]:
        with self._lock:
            return [(e["seq"], e["revision"]) for e in self.revisions if e["seq"] > after][:limit]

    def log_head(self) -> int:
        with self._lock:
            return len(self.revisions)

    def pending_journal(self, limit: int) -> List[Revision]:
        with self._lock:
            return [e["revision"] for e in self.revisions if not e["journal_applied"]][:limit]

    def closed_payload(self, aid: str, rid: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for h in self.hist:
                if h["memory_id"] == aid and h["revision_id"] == rid and h["event"] == _EVENT_CLOSED:
                    return json.loads(_dump(h["detail"]))
            return None

    def mark_journal_applied(self, rid: str) -> None:
        with self._lock:
            self.rev_by_id[rid]["journal_applied"] = True


_MEMORY_BACKENDS: "weakref.WeakKeyDictionary[InMemoryTripleStore, _MemoryBackend]" = weakref.WeakKeyDictionary()
_MEMORY_BACKENDS_LOCK = threading.Lock()


def _memory_backend(store: InMemoryTripleStore) -> _MemoryBackend:
    with _MEMORY_BACKENDS_LOCK:
        backend = _MEMORY_BACKENDS.get(store)
        if backend is None:
            backend = _MemoryBackend(store)
            _MEMORY_BACKENDS[store] = backend
        return backend


# ---------------------------------------------------------------------------------------------------------------


class MemoryGraph:
    """The graph's write path and its provenance / history / change-feed reads over one store (a mind).

    `store`: a `SQLiteTripleStore` (the home store; graph tables in the same file) or an `InMemoryTripleStore`
    (tests, dev). Any other store raises NotImplementedError (LanceDB: backlog 0057).
    `journal`: where `close` ops write their `ClosureRecord` (ranked retrieval folds closures). None writes no
    closure record; the history row and the revision still carry the close and its cause.
    """

    def __init__(self, store: Any, journal: Any = None) -> None:
        self._store, self._journal = store, journal
        if isinstance(store, SQLiteTripleStore):
            self._b: Any = _SQLiteBackend(store, journal)
        elif isinstance(store, InMemoryTripleStore):
            self._b = _memory_backend(store)
        else:
            raise NotImplementedError(
                f"MemoryGraph: {type(store).__name__} is not a graph home; use SQLiteTripleStore (InMemoryTripleStore "
                "for tests). LanceDB: see backlog 0057"
            )

    @property
    def store(self) -> Any:
        return self._store

    @property
    def journal(self) -> Any:
        return self._journal

    # -- write ---------------------------------------------------------------------------------------------------

    def apply_revision(self, revision: Revision, *, replay: bool = False) -> RevisionResult:
        """Validate and apply one revision atomically; idempotent on `revision_id` (a second apply returns
        `applied=False` and changes nothing).

        Record time is the STORE's: a fresh apply stamps `recorded_at` with this process's UTC clock inside the
        write transaction and ignores the value on the `Revision` (a caller cannot backdate what this mind learned;
        the log's `seq` is the record ORDER, `recorded_at` its wall-clock reading). `replay=True` keeps the logged
        `recorded_at`: a replay re-applies a record that already exists elsewhere, it is not a new one
        (`replay_into` passes it; a host surface must not expose it to callers). Raises `ProvenanceRequired` for an ungrounded write (or one that
        touches a store row the graph never adopted) and ValueError for an op that names an unknown assertion,
        names one before the op that asserts it, or tries to narrow an open window; either leaves nothing behind."""
        if not isinstance(revision, Revision):
            raise TypeError(f"apply_revision expects a Revision (got {type(revision).__name__})")
        prep = _prepare(revision)  # pure checks first: an ungrounded write is refused before any read or embed
        rev = prep.revision
        seq = self._b.applied_seq(rev.revision_id)
        if seq is not None:  # a replay: nothing to embed, nothing to write
            return RevisionResult(revision_id=rev.revision_id, applied=False, seq=seq)
        rows, pin_update, first_write_pin = self._b.prepare_rows(prep.assertions)  # embedding, outside the tx
        pending: List[ClosureRecord] = []
        result = RevisionResult(revision_id=rev.revision_id, applied=True)
        with self._b.transaction() as tx:
            seq = tx.revision_seq(rev.revision_id)
            if seq is not None:  # a concurrent apply of the same id won the race
                return RevisionResult(revision_id=rev.revision_id, applied=False, seq=seq)
            if not replay:  # the store's clock, read under the write lock: record time follows the log order
                rev = replace(rev, recorded_at=utc_now_iso_seconds())
            derived = self._validate(tx, prep)
            by_id = {str(a.assertion_id): a for a in prep.assertions}
            in_store = tx.existing_ids(list(by_id))
            known = {aid for aid in in_store if tx.memory_known(aid)}
            for aid in sorted(known):  # a different claim under a held id is refused, never silently "skipped"
                if _identity(tx.stored(aid)) != _identity(by_id[aid]):
                    raise ValueError(
                        f"revision {rev.revision_id!r} asserts {aid!r}, which this graph already holds as a different "
                        "claim (terms, scope, owner or valid_from differ); a changed claim gets a new id (and a close "
                        "of the old one)")
            previous = self._adopt(tx, rev, by_id, in_store - known)
            # RE-OBSERVATION, not duplication (architect E1): an open assert of a claim this graph already holds OPEN
            # (same `_identity`, hence the same owner) records the new sources on that memory instead of a second
            # row; so does a later duplicate inside this revision. A held id re-asserted while closed is a skip.
            reobserved: Dict[str, str] = {}
            fresh: Dict[Tuple[Any, ...], str] = {}
            for a in prep.assertions:
                aid = str(a.assertion_id)
                if a.valid_until is not None or aid in previous:
                    continue
                if aid in known:
                    if tx.window(aid)[1] is None:
                        reobserved[aid] = aid
                    continue
                key = _identity(a)
                target = fresh.get(key) or tx.open_same_claim(a)
                if target is not None:
                    reobserved[aid] = target
                else:
                    fresh[key] = aid
            tx.write_pin(pin_update)
            tx.insert_assertions([r for r, a in zip(rows, prep.assertions) if str(a.assertion_id) not in reobserved])
            for aid in previous:
                tx.set_provenance(aid, by_id[aid].provenance)
            at, rid = rev.recorded_at, rev.revision_id
            asserted: set = set()
            logged_ops: List[RevisionOp] = []  # the ops as logged: an adoption carries its previous provenance
            for index, op in enumerate(rev.ops):
                payload = op.payload
                logged_ops.append(op)
                if op.op == "assert":
                    aid = str(payload["assertion_id"])
                    asserted.add(aid)
                    if aid in reobserved:
                        target, prov = reobserved[aid], prep.effective[aid]
                        result.re_observed.append(target)
                        result.skipped.append({"op": "assert", "index": index, "assertion_id": target,
                                               "why": "re-observed"})
                        tx.add_history(target, _EVENT_REOBSERVED, at, rid, {
                            "asserted_as": aid, "observed_at": by_id[aid].observed_at,
                            "sources": [s.key() for s in prov.sources],
                            "derived_from": [reobserved.get(d, d) for d in derived[aid]]})
                        for ref in prov.sources:
                            tx.add_source(target, ref, rid, by_id[aid].owner_id)
                        for ref in rev.provenance.sources:
                            tx.add_source(target, ref, rid, by_id[aid].owner_id, VIA_REVISION)
                        for parent in derived[aid]:
                            if reobserved.get(parent, parent) != target:
                                tx.add_derivation(target, reobserved.get(parent, parent), rid)
                        continue
                    if aid in known:
                        result.skipped.append({"op": "assert", "index": index, "assertion_id": aid,
                                               "why": "already asserted in this graph"})
                        continue
                    a, prov = by_id[aid], prep.effective[aid]
                    result.assertion_ids.append(aid)
                    noted = (payload.get("adoption") or {}).get("previous_provenance")
                    if aid in previous:  # a live adoption: the stored provenance is the truth; log it with the op
                        if noted is not None and dict(noted) != previous[aid]:
                            raise ValueError(
                                f"revision {rid!r}: the adoption note of {aid!r} names a previous provenance that "
                                "differs from the stored row's")
                        logged_ops[-1] = RevisionOp("assert", {**payload, "adoption": {
                            "previous_provenance": previous[aid]}})
                        noted = previous[aid]
                    # (a replayed adoption inserts the row afresh and reads its previous provenance from the note)
                    detail: Dict[str, Any] = {
                        "subject": a.subject, "predicate": a.predicate, "object": a.object,
                        "valid_from": a.valid_from, "valid_until": a.valid_until, "observed_at": a.observed_at,
                        "sources": [s.key() for s in prov.sources], "derived_from": derived[aid],
                        "adopted": noted is not None,  # a store row written before the graph knew it: indexed now
                    }
                    if noted is not None:
                        detail["previous_provenance"] = dict(noted)
                    tx.add_history(aid, _EVENT_ASSERTED, at, rid, detail)
                    for ref in prov.sources:
                        tx.add_source(aid, ref, rid, a.owner_id)
                    for ref in rev.provenance.sources:  # the revision that wrote it (A7): found from its step too
                        tx.add_source(aid, ref, rid, a.owner_id, VIA_REVISION)
                    for parent in derived[aid]:
                        tx.add_derivation(aid, reobserved.get(parent, parent), rid)
                    continue
                aid = payload["assertion_id"]
                if aid in by_id and aid not in asserted:
                    raise ValueError(f"revision {rid!r}: op {index} ({op.op!r}) names {aid!r} before the op that "
                                     "asserts it (ops apply in order)")
                aid = reobserved.get(aid, aid)  # an id this revision re-observed names the memory that holds it
                window = tx.window(aid)
                if window is None:
                    raise ValueError(f"revision {rid!r}: a {op.op!r} op names an unknown assertion {aid!r}")
                if not tx.memory_known(aid):
                    raise ProvenanceRequired(
                        f"revision {rid!r}: a {op.op!r} op names {aid!r}, a store row written outside the graph; "
                        "adopt it with an 'import' or 'migration' revision first (its window then changes through "
                        "the graph, with a cause)")
                # A window never inverts: the end may equal the start (an empty window) but never precede it.
                if window[0] and _instant(payload["valid_until"]) < _instant(window[0]):
                    raise ValueError(
                        f"revision {rid!r}: a {op.op!r} op ends {aid!r} at {payload['valid_until']}, before its "
                        f"valid_from {window[0]} (the window would invert)")
                if op.op == "close":
                    # A memory is closed ONCE through the graph. The row's end becomes min(current end, the op's
                    # valid_until), compared as instants: an open window closes at valid_until; a window that would
                    # still run past the close ("valid until December", retracted in March) ends at the close, so
                    # TripleQuery(active_at=) and ranked recall (the closure) agree after it (ADR 0003 decision 7);
                    # an end already at or before the close is kept. The closure is written in every case. The
                    # history detail records the previous end, the end now on the row and whether it moved.
                    earlier = tx.closing_revision(aid)
                    if earlier is not None:
                        result.skipped.append({"op": "close", "index": index, "assertion_id": aid,
                                               "why": f"already closed by revision {earlier!r}"})
                        continue
                    current_end = window[1]
                    window_closed = (current_end is None
                                     or _instant(current_end) > _instant(payload["valid_until"]))
                    if window_closed:
                        tx.end_row(aid, payload["valid_until"])
                    closure = _closure_record(rev, payload)
                    if self._journal is not None and not tx.write_closure(closure):
                        pending.append(closure)
                    result.closed.append(aid)
                    tx.add_history(aid, _EVENT_CLOSED, at, rid, {
                        **payload, "closure_id": closure.closure_id if self._journal is not None else None,
                        "window_closed": window_closed, "previous_valid_until": current_end,
                        "row_valid_until": payload["valid_until"] if window_closed else current_end})
                else:  # narrow (raises ValueError on an open window: the whole revision rolls back)
                    if not tx.narrow_row(aid, payload["valid_until"]):
                        result.skipped.append({"op": "narrow", "index": index, "assertion_id": aid,
                                               "why": f"window already at or before (valid_until={window[1]})"})
                        continue
                    result.narrowed.append(aid)
                    tx.add_history(aid, _EVENT_NARROWED, at, rid, {
                        "valid_until": payload["valid_until"], "previous_valid_until": window[1],
                        "reason": payload["reason"]})
            seq = tx.insert_revision(replace(rev, ops=tuple(logged_ops)), journal_applied=not pending)
            result = replace(result, recorded_at=rev.recorded_at)
        if first_write_pin and pin_update is not None:
            warn_first_write_pin(pin_update)  # loud, and only once the pin is actually written
        if pending:  # the journal lives outside the store's transaction (see the module docstring)
            for closure in pending:
                self._journal.append_closure(closure)
            self._b.mark_journal_applied(rev.revision_id)
        return replace(result, seq=seq)

    @staticmethod
    def _adopt(tx: Any, rev: Revision, by_id: Mapping[str, TripleAssertion],
               unknown_rows: set) -> Dict[str, Dict[str, Any]]:
        """Asserted ids already in the store but never asserted through the graph: only an import/migration
        revision may adopt them, and only as stored (everything but provenance equal). Returns {id: the stored
        provenance it replaces}."""
        if not unknown_rows:
            return {}
        if rev.cause not in ADOPTING_CAUSES:
            raise ProvenanceRequired(
                f"revision {rev.revision_id!r} ({rev.cause!r}) asserts {sorted(unknown_rows)[:5]}, store rows "
                f"written outside the graph; only a revision whose cause is one of {list(ADOPTING_CAUSES)} adopts "
                "them (a store row written outside the graph must be adopted by an import or migration revision first)"
            )
        previous: Dict[str, Dict[str, Any]] = {}
        for aid in sorted(unknown_rows):
            stored = tx.stored(aid)
            if _content(stored) != _content(by_id[aid]):
                raise ValueError(
                    f"revision {rev.revision_id!r} adopts {aid!r} with content that differs from the stored row; "
                    "an adoption carries the row as stored (TripleQuery(...).to_dict()), only its provenance in the "
                    "graph shape"
                )
            previous[aid] = dict(stored.provenance)
        return previous

    def _validate(self, tx: Any, prep: _Prepared) -> Dict[str, List[str]]:
        """Provenance check (ADR 0003 decision 8), inside the transaction. Returns each asserted memory's
        derived_from ids resolved to the index namespace (assertion ids). A memory is grounded when it names
        sources, or when at least one memory it is derived from is grounded: a memory already in the graph is
        grounded by induction (the graph only ever accepted grounded writes); a memory of this revision is grounded
        by the same rule, to a fixpoint (so a cycle or a chain to nothing is refused). Every memory and the revision
        already passed the shape check (`_prepare`)."""
        rev = prep.revision

        def _resolve(mid: str, owner: str) -> str:
            if mid in prep.effective:
                return mid
            if mid in prep.aliases:
                return prep.aliases[mid]
            if tx.memory_known(mid):
                return mid
            aid = tx.digest_assertion_for(mid)
            if aid and (tx.memory_known(aid) or aid in prep.effective):
                return aid
            raise ProvenanceRequired(
                f"revision {rev.revision_id!r}: {owner} is derived_from {mid!r}, which is not a memory of this graph "
                "(neither asserted through a revision nor asserted in this one; a store row written outside the "
                "graph must be adopted by an 'import' or 'migration' revision first)"
            )

        derived: Dict[str, List[str]] = {
            aid: [_resolve(d, f"memory {aid!r}") for d in prov.derived_from] for aid, prov in prep.effective.items()
        }
        # Lineage never crosses owners (ADR 0003 decision 2, amended: strict ownership): knowledge from another
        # owner enters as a SOURCE (the message or artifact it reached this owner through), never as derived_from.
        own = {str(a.assertion_id): (a.owner_id or "") for a in prep.assertions}

        def _owner(mid: str) -> str:
            return own[mid] if mid in own else (tx.stored(mid).owner_id or "")

        def _same_owner(child_owner: str, parents: List[str], who: str) -> None:
            foreign = sorted({p for p in parents if _owner(p) != child_owner})
            if foreign:
                raise ProvenanceRequired(
                    f"revision {rev.revision_id!r}: {who} (owner {child_owner!r}) is derived_from {foreign} owned by "
                    f"{sorted({_owner(p) for p in foreign})}; lineage never crosses owners: name the message or "
                    "artifact the knowledge came through as a source instead")

        for aid, parents in derived.items():
            _same_owner(own[aid], parents, f"memory {aid!r}")
        grounded = {aid for aid, prov in prep.effective.items() if prov.sources}
        changed = True
        while changed:
            changed = False
            for aid, parents in derived.items():
                if aid not in grounded and any(p in grounded or p not in prep.effective for p in parents):
                    grounded.add(aid)
                    changed = True
        ungrounded = [aid for aid in prep.effective if aid not in grounded]
        if ungrounded:
            raise ProvenanceRequired(
                f"revision {rev.revision_id!r}: {ungrounded} derive only from memories that never reach a ledger "
                "source (a cycle, or a chain of derived memories with no sources)"
            )
        prov = rev.provenance
        parents = [_resolve(d, "the revision") for d in prov.derived_from]
        _same_owner(rev.owner_id or "", parents, "the revision")
        if not prov.sources and not any(p in grounded or p not in prep.effective for p in parents):
            raise ProvenanceRequired(f"revision {rev.revision_id!r}: its derived_from never reaches a ledger source")
        # A revision that only closes / narrows needs a cause OUTSIDE the memories it changes: citing the closed
        # memory as the reason for closing it names no ledger cause at all.
        if not prov.sources and all(op.op in ("close", "narrow") for op in rev.ops):
            targets = {op.payload["assertion_id"] for op in rev.ops}
            if not [p for p in parents if p not in targets]:
                raise ProvenanceRequired(
                    f"revision {rev.revision_id!r} only closes/narrows {sorted(targets)} and is derived only from "
                    "them: name a ledger source, or a memory other than the ones it changes, as its cause")
        return derived

    def repair(self, *, limit: int = MAX_READ_LIMIT) -> int:
        """Append the journal closures of revisions a crash left with `journal_applied = 0` (only possible when the
        journal is not in the store's file), oldest first, at most `limit` revisions per call. Idempotent
        (deterministic closure ids). Returns how many revisions were repaired (call again while it returns
        `limit`)."""
        pending = self._b.pending_journal(_check_limit(limit))
        if pending and self._journal is None:
            raise RuntimeError("MemoryGraph.repair: revisions await their journal closures but no journal is attached")
        for rev in pending:
            # The closures to append are the revision's close ops that closed something (a skipped close wrote no
            # history row and owes no closure), read back by (memory id, revision id) on the history index.
            for op in rev.ops:
                if op.op != "close" or self._b.closed_payload(op.payload["assertion_id"], rev.revision_id) is None:
                    continue
                self._journal.append_closure(_closure_record(rev, op.payload))
            self._b.mark_journal_applied(rev.revision_id)
        return len(pending)

    # -- reads -----------------------------------------------------------------------------------------------------

    def _resolve_read(self, memory_id: str) -> Optional[str]:
        mid = str(memory_id or "").strip()
        if not mid:
            raise ValueError("a memory id is required")
        return self._b.resolve(mid)

    def history(self, memory_id: str, *, limit: int = DEFAULT_READ_LIMIT) -> List[Dict[str, Any]]:
        """The memory's lifecycle in record order: `{event: asserted|closed|narrowed, at (record time), revision_id,
        cause, detail}`. Accepts an assertion id or a record's graph id. Unknown id: []."""
        n = _check_limit(limit)
        mid = self._resolve_read(memory_id)
        if mid is None:
            return []
        return self._b.history(mid, n)

    def sources_of(self, memory_id: str, *, transitive: bool = True, limit: int = DEFAULT_READ_LIMIT,
                   labelled: bool = False) -> List[Any]:
        """The ledger sources of a memory: the refs of its own provenance AND those of the revision that wrote it
        (a memory whose own provenance is lineage only still names the step that produced it); with `transitive`,
        also those of the memories it was derived from (breadth-first, deduplicated by key, at most `limit` refs and
        `MAX_LINEAGE_VISITS` memories visited). Unknown id: [].

        `labelled=True` returns `{"ref": SourceRef, "via": "memory" | "revision", "memory_id", "revision_id"}`
        dicts instead (which memory's row it is, and how the ref reached it)."""
        n = _check_limit(limit)
        start = self._resolve_read(memory_id)
        if start is None:
            return []
        out: Dict[str, Dict[str, Any]] = {}
        seen, queue = {start}, deque([start])
        while queue and len(out) < n:
            mid = queue.popleft()
            for ref, via, rid in self._b.sources(mid, n):
                out.setdefault(ref.key(), {"ref": ref, "via": via, "memory_id": mid, "revision_id": rid})
                if len(out) >= n:
                    break
            if transitive:
                for parent in self._b.parents(mid, MAX_LINEAGE_VISITS):
                    if parent not in seen and len(seen) < MAX_LINEAGE_VISITS:
                        seen.add(parent)
                        queue.append(parent)
        return list(out.values()) if labelled else [row["ref"] for row in out.values()]

    def derived_from_source(self, ref: Union[SourceRef, Mapping[str, Any]], *,
                            limit: int = DEFAULT_READ_LIMIT) -> List[str]:
        """Memory ids grounded in this ledger source: those that name it, then (breadth-first) every memory derived
        from them. A `run` ref matches everything stamped with that run (its steps, artifacts, messages). Bounded
        by `limit` (and `MAX_LINEAGE_VISITS`)."""
        n = _check_limit(limit)
        source = SourceRef.from_dict(ref)
        out: List[str] = []
        seen: set = set()
        queue: deque = deque()
        for mid in self._b.with_ref(source, n):
            if mid not in seen:
                seen.add(mid)
                out.append(mid)
                queue.append(mid)
        visits = 0
        while queue and len(out) < n and visits < MAX_LINEAGE_VISITS:
            visits += 1
            for child in self._b.children(queue.popleft(), n - len(out)):
                if child not in seen:
                    seen.add(child)
                    out.append(child)
                    queue.append(child)
        return out[:n]

    def names_ref(self, ref: Union[SourceRef, Mapping[str, Any]], owner_ids: Iterable[Optional[str]]) -> bool:
        """The owner gate in ONE index probe: does any memory owned by one of `owner_ids` name this ledger source
        (its own provenance or the revision that wrote it)? A `run` ref matches everything stamped with that run.
        `None` / '' is the no-owner partition. No owners: False. At most `MAX_READ_LIMIT` owners per call (a
        principal's owners plus the entities it owns); more raises ValueError."""
        source = SourceRef.from_dict(ref)
        owners = sorted({str(o or "").strip() for o in owner_ids})
        if not owners:
            return False
        if len(owners) > MAX_READ_LIMIT:
            raise ValueError(f"names_ref takes at most {MAX_READ_LIMIT} owner ids (got {len(owners)})")
        return self._b.names_ref(source, owners)

    def revisions(self, after: Optional[str] = None, limit: int = DEFAULT_REVISION_PAGE) -> Tuple[List[Revision], str]:
        """The change feed: revisions in log order strictly after the cursor, and the next cursor (`str(seq)` of the
        last one returned; unchanged when nothing is new). Lossless: no revision is skipped or repeated across
        calls, including while writers append (a revision's seq is allocated inside its write transaction, and
        write transactions are serialized, so commit order is seq order). A cursor beyond the log's head (from
        another graph, or invented) raises ValueError: it would silently skip every revision below it."""
        n = _check_limit(limit)
        if after is None or after == "":
            position = 0
        elif isinstance(after, str) and after.isdigit():
            position = int(after)
        else:
            raise ValueError(f"revisions(after=) takes a cursor returned by a previous call (got {after!r})")
        if position:
            head = self._b.log_head()
            if position > head:  # never handed out by this log (another graph's, or invented): later revisions
                raise ValueError(  # below it would never be delivered
                    f"revisions(after={after!r}): beyond this log's head ({head}); a cursor comes from a previous "
                    "call on the same graph")
        page = self._b.revisions_page(position, n)
        cursor = str(page[-1][0]) if page else str(position)
        return [rev for _, rev in page], cursor

    def replay_into(self, target: "MemoryGraph") -> int:
        """Re-apply every revision of this graph, in log order, to `target`; returns how many it applied (already
        present revision ids are no-ops, so a replay is resumable)."""
        if not isinstance(target, MemoryGraph):
            raise TypeError("replay_into expects a MemoryGraph")
        applied, cursor = 0, None
        while True:
            page, cursor = self.revisions(after=cursor, limit=DEFAULT_REVISION_PAGE)
            if not page:
                return applied
            for rev in page:
                if target.apply_revision(rev, replay=True).applied:
                    applied += 1
