"""The LanceDB connector of a mind (ADR 0003 decision 3; backlog 0057): `MemoryGraph` over a `LanceDBTripleStore`.

LanceDB has no transaction across tables, so this connector keeps the graph's atomicity with a STAGED transaction
and a LOG-FIRST commit:

1. Inside `transaction()` every write is staged in memory and every read of the transaction overlays the staged
   writes on the stored tables; an exception discards the stage, so a refused or failing revision writes nothing.
2. Commit (the graph's work done): the revision row is written FIRST with `status = 'pending'` and the whole staged
   projection (`plan_json`: triples, window/provenance updates, history, provenance and derivation rows, each keyed
   so a re-application is a no-op); then each projection is written (merge-insert on its key / an update to a
   value); then the revision row becomes `status = 'applied'`.
3. A crash between 2's steps leaves a `pending` log row: `repair_projections()` (run at the start of every
   transaction, and by `MemoryGraph.repair()`) re-applies its plan, so the log is the truth and the projections are
   re-derived from it. Until then, the half-written projection is VISIBLE to readers (no cross-table transaction).

Within ONE process every connector over the same LanceDB directory shares one lock, one set of table handles
(strongly consistent reads) and the seq counters, so writers are serialized and the change feed is lossless.
Across processes nothing serializes LanceDB writers: two processes writing one mind can allocate the same seq.
The conformance suite (`tests/test_graph_conformance.py`) marks those cases `xfail(strict=True)`; ADR 0003 decision
3 and backlog 0057 list them ("what the LanceDB connector cannot promise").

The journal of a LanceDB mind lives elsewhere (a `SQLiteJournal` file, an `InMemoryJournal`): closures are appended
after the commit and `repair()` re-appends any a crash left unwritten.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from ..canonical_text import canonical_text as _canonical_text
from ..canonical_text import is_record_edge as _is_record_edge
from ..journal import ClosureRecord
from ..journal_common import normalize_iso_ts as _instant
from ..lancedb_store import LanceDBTripleStore, _escape_sql_string, _import_lancedb, _list_lancedb_tables, _loads_json
from ..models import TripleAssertion, canonicalize_term
from .backend import GraphBackend, GraphTx, register_backend
from .graph import (
    DIGEST_PREDICATE,
    MAX_READ_LIMIT,
    VIA_MEMORY,
    _EVENT_ASSERTED,
    _EVENT_CLOSED,
    _dump,
    _identity,
    _row_revision_dict,
)
from .provenance import SourceRef
from .revisions import Revision

#: Ids per `assertion_id IN (...)` filter (keeps a filter string bounded).
IN_CHUNK = 500
#: Every this many commits a mind's tables are compacted (`optimize()`) and their scalar indexes brought up to date:
#: each LanceDB commit adds a fragment, and keyed reads over un-indexed fragments are scans (measured with
#: tests/bench/bench_graph.py --backend lancedb: see backlog 0057).
COMPACT_EVERY = 50
#: The keyed columns of each table (BTREE scalar indexes, created at the first compaction with rows).
INDEXED_COLUMNS = {
    "revisions": ("revision_id", "seq", "status"),
    "history": ("memory_id", "revision_id"),
    "provenance": ("pk", "memory_id", "ref_key", "run_id"),
    "derivations": ("pk", "memory_id", "from_id"),
    "triples": ("assertion_id", "subject"),
}
_TRIPLE_TEXT = ("assertion_id", "subject", "predicate", "object", "scope", "owner_id", "observed_at", "valid_from",
                "valid_until", "provenance_json", "attributes_json", "text")


def _q(value: Any) -> str:
    return "'" + _escape_sql_string(str(value)) + "'"


def _schemas(pa: Any) -> Dict[str, Any]:
    s, i = pa.string(), pa.int64()
    return {
        "revisions": pa.schema([("seq", i), ("revision_id", s), ("scope", s), ("owner_id", s), ("cause", s),
                                ("occurred_at", s), ("recorded_at", s), ("ops_json", s), ("provenance_json", s),
                                ("summary", s), ("journal_applied", i), ("status", s), ("plan_json", s)]),
        "provenance": pa.schema([("pk", s), ("pseq", i), ("memory_id", s), ("ref_key", s), ("ref_kind", s),
                                 ("run_id", s), ("revision_id", s), ("ref_json", s), ("via", s), ("owner_id", s)]),
        "derivations": pa.schema([("pk", s), ("dseq", i), ("memory_id", s), ("from_id", s), ("revision_id", s)]),
        "history": pa.schema([("hseq", i), ("memory_id", s), ("event", s), ("at", s), ("revision_id", s),
                              ("detail_json", s)]),
    }


def _triples_schema(pa: Any, vector_column: str, dim: Optional[int]) -> Any:
    fields = [(name, pa.string()) for name in _TRIPLE_TEXT[:9]] + [("confidence", pa.float64())]
    fields += [(name, pa.string()) for name in _TRIPLE_TEXT[9:]]
    if dim:
        fields.append((vector_column, pa.list_(pa.float32(), int(dim))))
    return pa.schema(fields)


class _State:
    """Per-process state of one LanceDB mind (directory + triple table): the lock, the table handles and the
    counters, shared by every connector over it so in-process writers are serialized."""

    def __init__(self, uri: str, table: str, vector_column: str) -> None:
        self.lock = threading.RLock()
        self.pa = __import__("pyarrow")
        self.db = _import_lancedb().connect(uri, read_consistency_interval=timedelta(0))
        self.table_name, self.vector_column = table, vector_column
        prefix = "memg_" if table == "triple_assertions" else f"memg_{table}_"
        self.names = {k: f"{prefix}{k}" for k in ("revisions", "provenance", "derivations", "history")}
        self.tables: Dict[str, Any] = {}
        self.triples: Any = None
        self.counters: Optional[Dict[str, int]] = None
        self.commits = 0
        self.pending_possible = True  # checked once at open, then only after a commit of this process failed

    def open(self) -> None:
        """Open the graph tables, creating only those that are absent (opening an existing mind writes nothing)."""
        existing = _list_lancedb_tables(self.db)
        for key, schema in _schemas(self.pa).items():
            name = self.names[key]
            self.tables[key] = (self.db.open_table(name) if name in existing
                                else self.db.create_table(name, schema=schema))
        self.triple_handle()

    def triple_handle(self) -> Any:
        """The triple table, opened when it exists (a `LanceDBTripleStore.add` outside the graph may have created
        it since this state opened), else None."""
        if self.triples is None and self.table_name in _list_lancedb_tables(self.db):
            self.triples = self.db.open_table(self.table_name)
            self._add_missing_triple_columns()
        return self.triples

    def _add_missing_triple_columns(self) -> None:
        """A triple table created by `LanceDBTripleStore.add` has the schema of its first batch (no `valid_until`
        when the first rows had none): add the missing nullable columns once."""
        have = set(self.triples.schema.names)
        missing = {name: "CAST(NULL AS STRING)" for name in _TRIPLE_TEXT if name not in have}
        if "confidence" not in have:
            missing["confidence"] = "CAST(NULL AS DOUBLE)"
        if missing:
            self.triples.add_columns(missing)

    def ensure_triples(self, dim: Optional[int]) -> Any:
        if self.triple_handle() is None:
            self.triples = self.db.create_table(
                self.table_name, schema=_triples_schema(self.pa, self.vector_column, dim))
        return self.triples

    def compact(self) -> None:
        """Compact every table and bring its scalar indexes up to date (COMPACT_EVERY)."""
        handles = dict(self.tables, triples=self.triples) if self.triples is not None else dict(self.tables)
        for key, table in handles.items():
            if table.count_rows() == 0:
                continue
            have = {c for idx in table.list_indices() for c in getattr(idx, "columns", [])}
            for column in INDEXED_COLUMNS[key]:
                if column not in have:
                    table.create_scalar_index(column)
            table.optimize()

    def counter_values(self) -> Dict[str, int]:
        if self.counters is None:
            def top(key: str, col: str) -> int:
                values = self.tables[key].search().select([col]).to_arrow().column(col).to_pylist()
                return max([int(v) for v in values if v is not None] or [0])
            self.counters = {"seq": top("revisions", "seq"), "hseq": top("history", "hseq"),
                             "pseq": top("provenance", "pseq"), "dseq": top("derivations", "dseq")}
        return self.counters

    def take(self, name: str) -> int:
        values = self.counter_values()
        values[name] += 1
        return values[name]


_STATES: Dict[Tuple[str, str], _State] = {}
_STATES_LOCK = threading.Lock()


def _state_for(store: LanceDBTripleStore) -> _State:
    uri = str(Path(str(store._db.uri)).expanduser().resolve()) if "://" not in str(store._db.uri) else str(store._db.uri)
    key = (uri, store._table_name)
    with _STATES_LOCK:
        state = _STATES.get(key)
        if state is None:
            state = _State(uri, store._table_name, store._vector_column)
            state.open()
            _STATES[key] = state
    return state


def _rows(table: Any, where: str, columns: Optional[List[str]] = None, *, limit: int) -> List[dict]:
    q = table.search().where(where).limit(int(limit))
    if columns:
        q = q.select(columns)
    return q.to_list()


def _all(table: Any, where: str, columns: Optional[List[str]] = None) -> List[dict]:
    """Every matching row (LanceDB's default query limit is 10: lift it). The caller bounds the filter."""
    count = table.count_rows(where)
    if count == 0:
        return []
    q = table.search().where(where).limit(int(count))
    if columns:
        q = q.select(columns)
    return q.to_list()


def _to_assertion(row: Dict[str, Any]) -> TripleAssertion:
    conf = row.get("confidence")
    return TripleAssertion(
        subject=str(row.get("subject") or ""), predicate=str(row.get("predicate") or ""),
        object=str(row.get("object") or ""), scope=str(row.get("scope") or "run"),
        owner_id=row.get("owner_id") or None, observed_at=str(row.get("observed_at") or ""),
        valid_from=row.get("valid_from") or None, valid_until=row.get("valid_until") or None,
        confidence=float(conf) if isinstance(conf, (int, float)) else None,
        provenance=_loads_json(row.get("provenance_json")), attributes=_loads_json(row.get("attributes_json")),
        assertion_id=row.get("assertion_id") or None)


class _LanceTx(GraphTx):
    """One revision, staged: writes are buffered, reads overlay them on the stored tables."""

    def __init__(self, backend: "LanceDBBackend") -> None:
        self.b, self.s = backend, backend.state
        self.new_rows: Dict[str, Dict[str, Any]] = {}
        self.updates: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self.provenance: Dict[str, Dict[str, Any]] = {}
        self.derivations: Dict[str, Dict[str, Any]] = {}
        self.revision: Optional[Dict[str, Any]] = None

    # -- reads (staged writes first) --------------------------------------------------------------------------------
    def _stored_row(self, aid: str) -> Optional[Dict[str, Any]]:
        if aid in self.new_rows:
            row = dict(self.new_rows[aid])
        else:
            if self.s.triple_handle() is None:
                return None
            found = _rows(self.s.triples, f"assertion_id = {_q(aid)}", limit=1)
            if not found:
                return None
            row = dict(found[0])
        row.update(self.updates.get(aid, {}))
        return row

    def revision_seq(self, rid: str) -> Optional[int]:
        found = _rows(self.s.tables["revisions"], f"revision_id = {_q(rid)}", ["seq"], limit=1)
        return int(found[0]["seq"]) if found else None

    def memory_known(self, mid: str) -> bool:
        if any(h["memory_id"] == mid and h["event"] == _EVENT_ASSERTED for h in self.history):
            return True
        return bool(_rows(self.s.tables["history"], f"memory_id = {_q(mid)} AND event = {_q(_EVENT_ASSERTED)}",
                          ["hseq"], limit=1))

    def closing_revision(self, mid: str) -> Optional[str]:
        stored = _all(self.s.tables["history"], f"memory_id = {_q(mid)} AND event = {_q(_EVENT_CLOSED)}",
                      ["hseq", "revision_id"])
        if stored:
            return str(min(stored, key=lambda r: r["hseq"])["revision_id"])
        for h in self.history:
            if h["memory_id"] == mid and h["event"] == _EVENT_CLOSED:
                return str(h["revision_id"])
        return None

    def open_same_claim(self, a: TripleAssertion) -> Optional[str]:
        if self.s.triple_handle() is None:
            return None
        rows = _rows(self.s.triples, f"subject = {_q(a.subject)} AND predicate = {_q(a.predicate)} AND "
                                     f"object = {_q(a.object)} AND valid_until IS NULL", limit=MAX_READ_LIMIT)
        for row in sorted(rows, key=lambda r: str(r.get("assertion_id"))):
            row = dict(row, **self.updates.get(str(row["assertion_id"]), {}))
            held = _to_assertion(row)
            if held.valid_until is None and _identity(held) == _identity(a) and self.memory_known(str(row["assertion_id"])):
                return str(row["assertion_id"])
        return None

    def digest_assertion_for(self, graph_id: str) -> Optional[str]:
        subject = canonicalize_term(graph_id)
        rows = list(self.new_rows.values())
        if self.s.triple_handle() is not None:
            rows += _rows(self.s.triples, f"subject = {_q(subject)} AND predicate = {_q(DIGEST_PREDICATE)}",
                          ["assertion_id", "observed_at", "subject", "predicate"], limit=MAX_READ_LIMIT)
        rows = [r for r in rows if r.get("subject") == subject and r.get("predicate") == DIGEST_PREDICATE]
        if not rows:
            return None
        return str(max(rows, key=lambda r: (str(r.get("observed_at") or ""), str(r["assertion_id"])))["assertion_id"])

    def existing_ids(self, ids: Sequence[str]) -> set:
        found = {i for i in ids if i in self.new_rows}
        if self.s.triple_handle() is not None:
            for start in range(0, len(ids), IN_CHUNK):
                chunk = list(ids[start:start + IN_CHUNK])
                where = f"assertion_id IN ({', '.join(_q(i) for i in chunk)})"
                found.update(r["assertion_id"] for r in _rows(self.s.triples, where, ["assertion_id"], limit=len(chunk)))
        return found

    def stored(self, aid: str) -> TripleAssertion:
        return _to_assertion(self._stored_row(aid))  # type: ignore[arg-type]

    def window(self, aid: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
        row = self._stored_row(aid)
        return (row.get("valid_from") or None, row.get("valid_until") or None) if row else None

    # -- writes (staged) --------------------------------------------------------------------------------------------
    def write_pin(self, pin: Optional[Dict[str, Any]]) -> None:
        return None  # LanceDBTripleStore keeps no embedding pin (its #FALLBACK warning says so)

    def insert_assertions(self, rows: List[Dict[str, Any]]) -> None:
        held = self.existing_ids([r["assertion_id"] for r in rows])
        for row in rows:
            if row["assertion_id"] not in held:
                self.new_rows[row["assertion_id"]] = dict(row)

    def _update(self, aid: str, **values: Any) -> None:
        self.updates.setdefault(aid, {}).update(values)

    def set_provenance(self, aid: str, provenance: Dict[str, Any]) -> None:
        self._update(aid, provenance_json=json.dumps(provenance, ensure_ascii=False, separators=(",", ":")))

    def end_row(self, aid: str, until: str) -> bool:
        self._update(aid, valid_until=until)
        return True

    def narrow_row(self, aid: str, until: str) -> bool:
        window = self.window(aid)
        if window is None:
            return False
        if window[1] is None:
            raise ValueError(
                f"narrow_assertion cannot widen or close an open window ({aid!r} has no valid_until); "
                "close it with close_assertion (the `close` op of a revision)")
        if _instant(window[1]) <= _instant(until):
            return False
        self._update(aid, valid_until=until)
        return True

    def write_closure(self, closure: ClosureRecord) -> bool:
        return False  # the journal is never in a LanceDB mind: appended after the commit

    def add_history(self, mid: str, event: str, at: str, rid: str, detail: Dict[str, Any]) -> None:
        self.history.append({"hseq": self.s.take("hseq"), "memory_id": mid, "event": event, "at": at,
                             "revision_id": rid, "detail_json": _dump(detail)})

    def add_source(self, mid: str, ref: SourceRef, rid: str, owner: Optional[str], via: str = VIA_MEMORY) -> None:
        pk = f"{mid}\x1f{ref.key()}"
        if pk in self.provenance or (mid not in self.new_rows and  # a memory new in this revision has no stored row
                                     _rows(self.s.tables["provenance"], f"pk = {_q(pk)}", ["pk"], limit=1)):
            return
        self.provenance[pk] = {"pk": pk, "pseq": self.s.take("pseq"), "memory_id": mid, "ref_key": ref.key(),
                               "ref_kind": ref.kind, "run_id": ref.run_id, "revision_id": rid,
                               "ref_json": _dump(ref.to_dict()), "via": via, "owner_id": owner or ""}

    def add_derivation(self, mid: str, from_id: str, rid: str) -> None:
        pk = f"{mid}\x1f{from_id}"
        if pk in self.derivations or (mid not in self.new_rows and
                                      _rows(self.s.tables["derivations"], f"pk = {_q(pk)}", ["pk"], limit=1)):
            return
        self.derivations[pk] = {"pk": pk, "dseq": self.s.take("dseq"), "memory_id": mid, "from_id": from_id,
                                "revision_id": rid}

    def insert_revision(self, rev: Revision, journal_applied: bool) -> int:
        seq = self.s.counter_values()["seq"] + 1
        self.revision = {
            "seq": seq, "revision_id": rev.revision_id, "scope": rev.scope, "owner_id": rev.owner_id,
            "cause": rev.cause, "occurred_at": rev.occurred_at, "recorded_at": rev.recorded_at,
            "ops_json": _dump([o.to_dict() for o in rev.ops]), "provenance_json": _dump(rev.provenance.to_dict()),
            "summary": rev.summary, "journal_applied": 1 if journal_applied else 0}
        return seq

    def plan(self) -> Dict[str, Any]:
        return {"rows": list(self.new_rows.values()), "updates": self.updates, "history": self.history,
                "provenance": list(self.provenance.values()), "derivations": list(self.derivations.values())}


class LanceDBBackend(GraphBackend):
    """`GraphBackend` over a `LanceDBTripleStore` (see the module docstring for what it can and cannot promise)."""

    def __init__(self, store: LanceDBTripleStore, journal: Any) -> None:
        self.store, self.journal = store, journal
        self.state = _state_for(store)
        if self.state.triple_handle() is not None:
            store._table = self.state.triples  # one strongly consistent handle for the store's reads too

    # -- writes -----------------------------------------------------------------------------------------------------
    def prepare_rows(self, assertions: List[TripleAssertion]) -> Tuple[List[Dict[str, Any]], None, bool]:
        texts = [_canonical_text(a) for a in assertions]
        vectors: Dict[int, List[float]] = {}
        embedder = self.store._embedder
        if embedder is not None:
            embeddable = [i for i, a in enumerate(assertions) if not _is_record_edge(a)]
            if embeddable:
                vectors = dict(zip(embeddable, embedder.embed_texts([texts[i] for i in embeddable])))
        rows = []
        for i, a in enumerate(assertions):
            rows.append({
                "assertion_id": a.assertion_id, "subject": a.subject, "predicate": a.predicate, "object": a.object,
                "scope": a.scope, "owner_id": a.owner_id, "observed_at": a.observed_at, "valid_from": a.valid_from,
                "valid_until": a.valid_until, "confidence": a.confidence,
                "provenance_json": json.dumps(a.provenance, ensure_ascii=False, separators=(",", ":")),
                "attributes_json": json.dumps(a.attributes, ensure_ascii=False, separators=(",", ":")),
                "text": texts[i],
                self.state.vector_column: [float(x) for x in vectors[i]] if i in vectors else None,
            })
        return rows, None, False

    @contextmanager
    def transaction(self) -> Iterator[_LanceTx]:
        state = self.state
        with state.lock:
            if state.pending_possible:
                self._repair_locked()
                state.pending_possible = False
            saved = dict(state.counter_values())
            tx = _LanceTx(self)
            try:
                yield tx
            except BaseException:
                state.counters = saved  # nothing was written: give the staged sequence numbers back
                raise
            if tx.revision is not None:
                try:
                    self._commit(tx)
                except BaseException:
                    state.pending_possible = True  # the log row may be written: the next transaction repairs it
                    raise
                state.commits += 1
                if state.commits % COMPACT_EVERY == 0:
                    state.compact()

    def _commit(self, tx: _LanceTx) -> None:
        state = self.state
        plan = tx.plan()
        row = dict(tx.revision, status="pending", plan_json=json.dumps(plan, ensure_ascii=False))  # type: ignore
        state.tables["revisions"].add(state.pa.Table.from_pylist([row], schema=state.tables["revisions"].schema))
        state.counter_values()["seq"] = row["seq"]  # the log row is written: its seq is taken
        self._apply_plan(plan, fresh=True)
        state.tables["revisions"].update(where=f"revision_id = {_q(row['revision_id'])}",
                                         values={"status": "applied", "plan_json": ""})

    def _apply_plan(self, plan: Dict[str, Any], fresh: bool = False) -> None:
        """Write a revision's projections. `fresh` (the commit that staged them): every key is new (the stage
        checked), so rows are appended. Otherwise (repair, re-applying a plan a crash interrupted) every write is
        keyed and idempotent: merge-insert of the keys not yet stored; updates set a value."""
        state, pa = self.state, self.state.pa
        rows = plan["rows"]
        if rows:
            dims = [len(r[state.vector_column]) for r in rows if r.get(state.vector_column)]
            triples = state.ensure_triples(dims[0] if dims else None)
            self.store._table = triples
            names = triples.schema.names
            batch = pa.Table.from_pylist([{k: r.get(k) for k in names} for r in rows], schema=triples.schema)
            if fresh:
                triples.add(batch)
            else:
                triples.merge_insert("assertion_id").when_not_matched_insert_all().execute(batch)
        for aid, values in plan["updates"].items():
            state.triples.update(where=f"assertion_id = {_q(aid)}", values=values)
        for key, table_key, col in (("history", "history", "hseq"), ("provenance", "provenance", "pk"),
                                    ("derivations", "derivations", "pk")):
            if plan[key]:
                table = state.tables[table_key]
                batch = pa.Table.from_pylist(plan[key], schema=table.schema)
                if fresh:
                    table.add(batch)
                else:
                    table.merge_insert(col).when_not_matched_insert_all().execute(batch)

    def _repair_locked(self) -> int:
        pending = _all(self.state.tables["revisions"], "status = 'pending'", ["seq", "revision_id", "plan_json"])
        for row in sorted(pending, key=lambda r: r["seq"]):
            self._apply_plan(json.loads(row["plan_json"]))
            self.state.tables["revisions"].update(where=f"revision_id = {_q(row['revision_id'])}",
                                                  values={"status": "applied", "plan_json": ""})
        return len(pending)

    def repair_projections(self) -> int:
        with self.state.lock:
            return self._repair_locked()

    # -- reads (under the mind's lock: never a half-written revision of THIS process) -----------------------------
    def _t(self, key: str) -> Any:
        return self.state.tables[key]

    def applied_seq(self, rid: str) -> Optional[int]:
        with self.state.lock:
            found = _rows(self._t("revisions"), f"revision_id = {_q(rid)} AND status = 'applied'", ["seq"], limit=1)
            return int(found[0]["seq"]) if found else None

    def resolve(self, mid: str) -> Optional[str]:
        with self.state.lock:
            tx = _LanceTx(self)
            if tx.memory_known(mid):
                return mid
            aid = tx.digest_assertion_for(mid)
            return aid if aid and tx.memory_known(aid) else None

    def history(self, mid: str, limit: int) -> List[Dict[str, Any]]:
        with self.state.lock:
            rows = sorted(_all(self._t("history"), f"memory_id = {_q(mid)}"), key=lambda r: r["hseq"])[:limit]
            rids = sorted({r["revision_id"] for r in rows})
            causes = {r["revision_id"]: r["cause"] for r in _all(
                self._t("revisions"), f"revision_id IN ({', '.join(_q(x) for x in rids)})",
                ["revision_id", "cause"])} if rids else {}
        return [{"event": r["event"], "at": r["at"], "revision_id": r["revision_id"], "cause": causes[r["revision_id"]],
                 "detail": json.loads(r["detail_json"])} for r in rows]

    def sources(self, mid: str, limit: int) -> List[Tuple[SourceRef, str, str]]:
        with self.state.lock:
            rows = sorted(_all(self._t("provenance"), f"memory_id = {_q(mid)}"), key=lambda r: r["pseq"])[:limit]
        return [(SourceRef.from_dict(json.loads(r["ref_json"])), r["via"], r["revision_id"]) for r in rows]

    def parents(self, mid: str, limit: int) -> List[str]:
        with self.state.lock:
            rows = _all(self._t("derivations"), f"memory_id = {_q(mid)}", ["dseq", "from_id"])
        return [r["from_id"] for r in sorted(rows, key=lambda r: r["dseq"])][:limit]

    def children(self, fid: str, limit: int) -> List[str]:
        with self.state.lock:
            rows = _all(self._t("derivations"), f"from_id = {_q(fid)}", ["dseq", "memory_id"])
        return [r["memory_id"] for r in sorted(rows, key=lambda r: r["dseq"])][:limit]

    def with_ref(self, ref: SourceRef, limit: int) -> List[str]:
        where = f"run_id = {_q(ref.run_id)}" if ref.kind == "run" else f"ref_key = {_q(ref.key())}"
        with self.state.lock:
            rows = sorted(_all(self._t("provenance"), where, ["pseq", "memory_id"]), key=lambda r: r["pseq"])
        out: List[str] = []
        for r in rows:
            if r["memory_id"] not in out:
                out.append(r["memory_id"])
                if len(out) >= limit:
                    break
        return out

    def names_ref(self, ref: SourceRef, owners: List[str]) -> bool:
        key = f"run_id = {_q(ref.run_id)}" if ref.kind == "run" else f"ref_key = {_q(ref.key())}"
        where = f"{key} AND owner_id IN ({', '.join(_q(o) for o in owners)})"
        with self.state.lock:
            return bool(_rows(self._t("provenance"), where, ["pk"], limit=1))

    def revisions_page(self, after: int, limit: int) -> List[Tuple[int, Revision]]:
        # seqs are contiguous (allocated head + 1 under the lock; a pending row is repaired before the next write)
        with self.state.lock:
            rows = _all(self._t("revisions"), f"seq > {int(after)} AND seq <= {int(after) + int(limit)} AND "
                                              "status = 'applied'")
        return [(int(r["seq"]), Revision.from_dict(_row_revision_dict(r))) for r in sorted(rows, key=lambda r: r["seq"])]

    def log_head(self) -> int:
        with self.state.lock:
            return int(self.state.counter_values()["seq"])

    def logged_outcome(self, rid: str) -> Tuple[Optional[str], List[Tuple[str, str]]]:
        with self.state.lock:
            rev = _rows(self._t("revisions"), f"revision_id = {_q(rid)}", ["recorded_at"], limit=1)
            events = sorted(_all(self._t("history"), f"revision_id = {_q(rid)}", ["hseq", "memory_id", "event"]),
                            key=lambda r: r["hseq"])
        return (rev[0]["recorded_at"] if rev else None), [(e["memory_id"], e["event"]) for e in events]

    def pending_journal(self, limit: int) -> List[Revision]:
        with self.state.lock:
            rows = _all(self._t("revisions"), "journal_applied = 0 AND status = 'applied'")
        return [Revision.from_dict(_row_revision_dict(r)) for r in sorted(rows, key=lambda r: r["seq"])[:limit]]

    def closed_payload(self, aid: str, rid: str) -> Optional[Dict[str, Any]]:
        with self.state.lock:
            rows = _rows(self._t("history"), f"memory_id = {_q(aid)} AND revision_id = {_q(rid)} AND "
                                             f"event = {_q(_EVENT_CLOSED)}", ["detail_json"], limit=1)
        return json.loads(rows[0]["detail_json"]) if rows else None

    def mark_journal_applied(self, rid: str) -> None:
        with self.state.lock:
            self._t("revisions").update(where=f"revision_id = {_q(rid)}", values={"journal_applied": 1})


register_backend(LanceDBTripleStore, LanceDBBackend)
