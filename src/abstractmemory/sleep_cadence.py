"""Sleep cadence: WHEN is a pass worth running (fork item 770).

Split from maintenance.py (600-line rule): the tending pass answers "what
needs tending", this module answers "is there material" — a deterministic
predicate over the journal's formation stream plus the standing
fragmentation signal. Scheduling itself (late-local-time, sleep windows)
stays HOST policy by the 0023 ruling: the host's clock decides WHEN to ask;
this only answers WHETHER the answer would be new.

BOUNDED BY A CURSOR (backlog 0058). The predicate is meant to be asked
often; it used to re-read the whole scope twice (the anchor's artifact scan
and `structural_report`) on every call: 3.5 s at 20k records. Its answer is
now folded from the store's change feed (`assertions_after`, append-only
rows in rowid order) into a per-(store, journal, scopes) `_CadenceFold`
that keeps exactly the facts the answer needs: each record's effective
title, the maintenance candidates, the component edges and the sleep
artifacts. A check reads only the rows written since the previous one
(O(new rows)); the duplicate-title and isolated counts are recomputed in
memory only when such a row arrived. The journal's formation bindings are
re-read only when `journal.current_seq()` moved (the journal API has no
"after seq" read; see backlog 0058 Report, remaining hot spots). The answer
is the one the full scan gives — `_maintenance_due_scan` keeps that
reference, and a store without a change feed (LanceDB) still uses it.
"""

from __future__ import annotations

import threading
import weakref
from bisect import bisect_right
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .consolidation import COMPONENT_RELATIONS, structural_report
from .store import TripleQuery
from .store_tuning import CADENCE_FEED_PAGE
from .text_tokens import title_key

__all__ = ["last_maintenance_seq", "maintenance_due", "records_since_maintenance"]


# -- the reference (full scan) ----------------------------------------------


def _last_maintenance_seq_scan(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
) -> int:
    artifact_ids: List[str] = []
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_kind") == "dream" or attrs.get("maintenance_candidate"):
                artifact_ids.append(a.subject)
    return _anchor_of(journal, artifact_ids)


def _anchor_of(journal: Any, artifact_ids: Any) -> int:
    high = 0
    for rid in sorted(set(artifact_ids)):
        for binding in journal.bindings(record_id=rid, fold=True):
            high = max(high, int(binding.seq))
    return high


def _new_formed(seqs_per_pair: Sequence[Sequence[int]], anchor: int) -> int:
    return sum(len(seqs) - bisect_right(seqs, anchor) for seqs in seqs_per_pair)


def _remember_seqs(journal: Any, scopes: Sequence[Tuple[str, str]]) -> List[List[int]]:
    return [sorted(int(b.seq) for b in journal.bindings(scope=scope, owner_id=owner, fold=False)
                   if b.source == "remember")
            for scope, owner in scopes]


def _maintenance_due_scan(
    store: Any, journal: Any, *,
    scopes: Sequence[Tuple[str, str]], since_seq: Optional[int],
    min_new_records: int, min_signal: int,
) -> Dict[str, Any]:
    """The reference answer: full scope scans (the pre-0058 code path)."""
    anchor = int(since_seq) if since_seq is not None else _last_maintenance_seq_scan(
        store, journal, scopes=scopes)
    new_formed = _new_formed(_remember_seqs(journal, scopes), anchor)
    base = structural_report(store, journal, scopes=scopes)
    return _answer(anchor, new_formed, len(base.get("duplicates", {})),
                   len(base.get("isolated", ())), min_new_records, min_signal)


def _answer(anchor: int, new_formed: int, duplicates: int, isolated: int,
            min_new_records: int, min_signal: int) -> Dict[str, Any]:
    signal = duplicates + isolated
    reasons: List[str] = []
    if new_formed >= int(min_new_records):
        reasons.append(f"{new_formed} new records since seq {anchor} (floor {int(min_new_records)})")
    if new_formed > 0 and signal >= int(min_signal):
        reasons.append(
            f"{new_formed} new record(s) with fragmentation signal {signal} >= {int(min_signal)} "
            f"({duplicates} duplicate-title group(s) + {isolated} isolated)")
    return {
        "due": bool(reasons), "reasons": reasons, "since_seq": anchor,
        "new_records": new_formed, "signal": signal,
        "duplicate_groups": duplicates, "isolated": isolated,
    }


# -- the cursor-bounded fold --------------------------------------------------


def _scan_order(store: Any) -> Optional[str]:
    """How `store.query(limit=0)` orders rows of equal `observed_at` (the
    structural report's "last row of a subject wins" depends on it), or None
    for a store without a change feed: the fold must reproduce the scan
    exactly, so it only serves stores whose order it knows."""
    from .in_memory_store import InMemoryTripleStore
    from .sqlite_store import SQLiteTripleStore

    if isinstance(store, SQLiteTripleStore):
        return "assertion_id"   # ORDER BY observed_at DESC, assertion_id DESC
    if isinstance(store, InMemoryTripleStore):
        return "insertion"      # stable sort by observed_at, reverse
    return None


class _CadenceFold:
    """The facts `maintenance_due` needs, folded from the change feed.

    Reproduces `structural_report(store, journal, scopes)`'s duplicate-title
    and isolated counts and `last_maintenance_seq`'s artifact set exactly:
    the report walks the scopes in order, each newest-first, and the LAST
    row it sees for a subject sets the record's title — so a subject's
    effective row is, in the last scope listing it, its oldest row (ties by
    the store's own order, `_scan_order`)."""

    def __init__(self, journal: Any, scopes: Sequence[Tuple[str, str]], order: str) -> None:
        self.journal_ref = weakref.ref(journal)
        self.scopes = list(scopes)
        self.order = order
        self.lock = threading.Lock()
        self.cursors = [0] * len(self.scopes)
        # subject -> {scope index: (order key, title key)} (the oldest
        # eligible row of that subject in that scope).
        self.titles: Dict[str, Dict[int, Tuple[Tuple[Any, ...], str]]] = {}
        self.candidates: Set[str] = set()
        self.edges: Set[Tuple[str, str]] = set()
        self.artifacts: Set[str] = set()
        self.signal: Optional[Tuple[int, int]] = None   # (duplicates, isolated); None = stale
        self.journal_seq: Optional[int] = None
        self.remember_seqs: List[List[int]] = []
        self.anchor: Optional[int] = None               # derived anchor; None = stale
        self.rows_read = 0                              # change-feed rows folded (tests)

    def catch_up(self, store: Any) -> None:
        for index, (scope, owner) in enumerate(self.scopes):
            while True:
                rows, cursor = store.assertions_after(
                    self.cursors[index], scope=scope, owner_id=owner or None,
                    limit=CADENCE_FEED_PAGE)
                self.cursors[index] = cursor
                for position, a in rows:
                    self._fold(index, position, a)
                if len(rows) < CADENCE_FEED_PAGE:
                    break

    def _fold(self, index: int, position: int, a: Any) -> None:
        self.rows_read += 1
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        # last_maintenance_seq's artifact rule (any row of the scope).
        if attrs.get("record_kind") == "dream" or attrs.get("maintenance_candidate"):
            if a.subject not in self.artifacts:
                self.artifacts.add(a.subject)
                self.anchor = None
        # structural_report's rules, in its order.
        if attrs.get("record_edge"):
            predicate = str(a.predicate or "").strip()
            if predicate in COMPONENT_RELATIONS and a.subject != a.object:
                pair = (a.subject, a.object) if a.subject <= a.object else (a.object, a.subject)
                if pair not in self.edges:
                    self.edges.add(pair)
                    self.signal = None
            return
        kind = attrs.get("record_kind")
        if not kind or kind in ("dream", "world_model") or attrs.get("bookkeeping"):
            return
        if attrs.get("maintenance_candidate") and a.subject not in self.candidates:
            self.candidates.add(a.subject)
            self.signal = None
        tie = (a.assertion_id or "") if self.order == "assertion_id" else -int(position)
        key = (a.observed_at or "", tie)
        per_scope = self.titles.setdefault(a.subject, {})
        held = per_scope.get(index)
        if held is None or key < held[0]:
            per_scope[index] = (key, title_key(str(attrs.get("title") or "").strip()))
            self.signal = None

    def structural_counts(self) -> Tuple[int, int]:
        """(duplicate-title groups, isolated records) of structural_report."""
        if self.signal is None:
            groups: Counter = Counter()
            for per_scope in self.titles.values():
                normalized = per_scope[max(per_scope)][1]
                if normalized:
                    groups[normalized] += 1
            duplicates = sum(1 for count in groups.values() if count > 1)
            linked: Set[str] = set()
            for left, right in self.edges:
                if (left in self.titles and right in self.titles
                        and left not in self.candidates and right not in self.candidates):
                    linked.add(left)
                    linked.add(right)
            self.signal = (duplicates, len(self.titles) - len(linked))
        return self.signal

    def sync_journal(self, journal: Any) -> None:
        seq = int(journal.current_seq())
        if seq != self.journal_seq:
            # Read the seq FIRST: a binding appended meanwhile is either in
            # this read or makes the next check re-read (never lost).
            self.remember_seqs = _remember_seqs(journal, self.scopes)
            self.journal_seq = seq
            self.anchor = None

    def derived_anchor(self, journal: Any) -> int:
        if self.anchor is None:
            self.anchor = _anchor_of(journal, self.artifacts)
        return self.anchor


_FOLDS: "weakref.WeakKeyDictionary[Any, Dict[Any, _CadenceFold]]" = weakref.WeakKeyDictionary()
_FOLDS_LOCK = threading.Lock()


def _fold_for(store: Any, journal: Any, scopes: Sequence[Tuple[str, str]]) -> Optional[_CadenceFold]:
    order = _scan_order(store)
    if order is None or not hasattr(store, "assertions_after"):
        return None
    pairs = [(str(scope), owner) for scope, owner in scopes]
    key = (id(journal), tuple(pairs))
    with _FOLDS_LOCK:
        per_store = _FOLDS.setdefault(store, {})
        fold = per_store.get(key)
        if fold is None or fold.journal_ref() is not journal:
            fold = _CadenceFold(journal, pairs, order)
            per_store[key] = fold
    return fold


def last_maintenance_seq(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
) -> int:
    """Journal seq of the newest sleep artifact's formation (dream OR
    maintenance candidate) — the default "since when" anchor for the cadence
    predicate. 0 = this store has never had a sleep pass. Cursor-bounded
    (see the module docstring)."""
    fold = _fold_for(store, journal, scopes)
    if fold is None:
        return _last_maintenance_seq_scan(store, journal, scopes=scopes)
    with fold.lock:
        fold.catch_up(store)
        fold.sync_journal(journal)
        return fold.derived_anchor(journal)


def maintenance_due(
    store: Any, journal: Any, *,
    scopes: Sequence[Tuple[str, str]], since_seq: Optional[int] = None,
    min_new_records: int = 12, min_signal: int = 3,
    tasks: Any = None,
) -> Dict[str, Any]:
    """Deterministic cadence predicate (fork 770: "enough new nodes +
    fragmentation"; late-local-time stays the HOST's clock). Due when enough
    NEW records formed since the last pass, or when SOME new material exists
    and the standing fragmentation signal (duplicate-title groups + isolated
    records) clears its floor. A store with zero new formations is never due —
    the pass would reproduce its own prior output byte-for-byte.

    Bounded by a cursor (0058): a check reads the store rows written since
    the previous check of the same (store, journal, scopes), and re-reads the
    journal's formation bindings only when the journal moved. Same answer as
    the full scan.

    `tasks` (the home's `MemoryTaskQueue`, backlog 0060): pending memory
    tasks are reported (`pending_tasks` {kind: n}); pending ripple work and
    pending night-only work (dream narrations, ripple consolidations) make
    a sleep due (ADR 0001 decision 9: pending ripples are work due, never
    suppressed to keep a young system quiet). Digest and card rewrites run
    in any window and are reported without making a night due."""
    fold = _fold_for(store, journal, scopes)
    if fold is None:
        answer = _maintenance_due_scan(
            store, journal, scopes=scopes, since_seq=since_seq,
            min_new_records=min_new_records, min_signal=min_signal)
    else:
        with fold.lock:
            fold.catch_up(store)
            fold.sync_journal(journal)
            anchor = int(since_seq) if since_seq is not None else fold.derived_anchor(journal)
            duplicates, isolated = fold.structural_counts()
            new_formed = _new_formed(fold.remember_seqs, anchor)
        answer = _answer(anchor, new_formed, duplicates, isolated, min_new_records, min_signal)
    if tasks is not None:
        _with_tasks(answer, tasks, scopes)
    return answer


#: Task kinds whose pending work makes a sleep due (ADR 0001 decision 9 + night-only kinds).
_DUE_TASK_KINDS = ("ripple.reconsider", "ripple.consolidate", "dream.narrate")


def _with_tasks(answer: Dict[str, Any], tasks: Any, scopes: Sequence[Tuple[str, str]]) -> None:
    wanted = {(str(s).strip().lower(), str(o or "").strip()) for s, o in scopes}
    pending: Dict[str, int] = {}
    for t in tasks.tasks(status=("pending", "deferred", "leased")):
        if (t["scope"], t["owner_id"]) in wanted:
            pending[t["kind"]] = pending.get(t["kind"], 0) + 1
    answer["pending_tasks"] = pending
    due_work = {k: n for k, n in pending.items() if k in _DUE_TASK_KINDS}
    if due_work:
        answer["due"] = True
        answer["reasons"].append(
            "pending memory work only a sleep runs or ADR 0001 counts as due: "
            + ", ".join(f"{n} {k}" for k, n in sorted(due_work.items())))


# -- the host's idle -> sleep threshold ------------------------------------------------------------------------


def _maintenance_row(system: Any, scopes: Optional[Sequence[Tuple[str, str]]]) -> Optional[Dict[str, Any]]:
    """The newest completed NIGHT over these pairs, read without opening (or creating) anything: the home's own
    task queue, else (a SQLite home opened without one) the file's `memq_maintenance` table when it exists."""
    from .memory_tasks import _last_maintenance_rows
    from .sqlite_store import SQLiteTripleStore

    queue = getattr(system, "tasks", None)
    if queue is not None:
        return queue.last_maintenance(scopes, kind="night")
    store = system.store
    if not isinstance(store, SQLiteTripleStore):
        return None
    table = ("memq_" if store._table == "triples" else f"memq_{store._table}_") + "maintenance"

    def read(sql: str, params: Sequence[Any] = ()) -> List[Any]:
        with store._lock:
            cur = store._conn.cursor()
            if cur.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is None:
                return []
            return cur.execute(sql, tuple(params)).fetchall()

    return _last_maintenance_rows(read, table, scopes, "night")


#: A formed record's row: its digest assertion (edges and bookkeeping rows are not records).
_FORMED_SQL = ("predicate = 'dcterms:abstract' "
               "AND json_extract(COALESCE(attributes_json, '{}'), '$.record_kind') IS NOT NULL "
               "AND json_extract(COALESCE(attributes_json, '{}'), '$.record_edge') IS NULL "
               "AND json_extract(COALESCE(attributes_json, '{}'), '$.bookkeeping') IS NULL")


def _formed(a: Any) -> bool:
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    return (str(a.predicate or "") == "dcterms:abstract" and bool(attrs.get("record_kind"))
            and not attrs.get("record_edge") and not attrs.get("bookkeeping"))


def _count_formed(system: Any, pairs: Optional[List[Tuple[str, str]]],
                  after: Optional[str]) -> Tuple[int, Optional[str]]:
    """(records formed strictly after `after` (None = ever), the oldest one's observed_at). SQLite: per pair one
    COUNT and one MIN over the (scope, owner_id, observed_at) index range, O(rows in the range); any pair = the
    observed_at index. Other stores read their rows."""
    from .sqlite_store import SQLiteTripleStore

    store = system.store
    if isinstance(store, SQLiteTripleStore):
        count, oldest = 0, None
        targets: List[Tuple[str, List[Any]]] = (
            [("scope = ? AND owner_id = ?", [sc, ow]) for sc, ow in pairs] if pairs is not None else [("1 = 1", [])])
        with store._lock:
            cur = store._conn.cursor()
            for where, params in targets:
                clause = f"{where} AND {_FORMED_SQL}" + (" AND observed_at > ?" if after is not None else "")
                args = [*params, *([after] if after is not None else [])]
                n, low = cur.execute(f"SELECT COUNT(*), MIN(observed_at) FROM {store._table} WHERE {clause}",
                                     args).fetchone()
                count += int(n or 0)
                if low is not None and (oldest is None or str(low) < oldest):
                    oldest = str(low)
        return count, oldest
    rows: List[Any] = []
    for sc, ow in (pairs if pairs is not None else [(None, None)]):
        rows.extend(a for a in store.query(TripleQuery(scope=sc, owner_id=ow or None, predicate="dcterms:abstract",
                                                       since=after, limit=0))
                    if _formed(a) and (after is None or str(a.observed_at or "") > after))
    oldest_seen = min((str(a.observed_at or "") for a in rows), default=None)
    return len(rows), oldest_seen


def _normalized_instant(value: Any) -> Optional[str]:
    """`after` in memory's own timestamp format (UTC, microseconds, "+00:00": `journal.utc_now_iso`), so it orders
    exactly against stored `observed_at` / `completed_at` strings whatever offset style the host wrote ("Z",
    "+02:00", seconds only). A naive value is read as UTC. Unparseable -> ValueError."""
    from datetime import datetime, timezone

    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00") if text.endswith("Z") else text)
        except ValueError as exc:
            raise ValueError(f"records_since_maintenance: after={value!r} is not an ISO-8601 instant") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def records_since_maintenance(system: Any, *, scopes: Optional[Sequence[Tuple[str, str]]] = None,
                              after: Optional[str] = None) -> Dict[str, Any]:
    """How much the home lived since its last COMPLETED sleep (PURE READ; the host's idle -> sleep threshold,
    operator 2026-11-09: sleep after 24 h or 500 events). Returns {count, last_maintenance_at, since,
    boundary_source, fragmented}:

    - `last_maintenance_at`: when the newest completed night over these (scope, owner) pairs ended (`sleep_pass`
      records it when a whole night, `include_dream=True`, ran to its end: not cancelled, not report_only, not
      anchored with `as_of`; a cycle window is recorded apart and does not count), `None` when memory holds none;
      `scopes=None` = any pair.
    - `after`: the host's own knowledge of the last maintenance (the gateway's last `maintenance_done` from its
      state history, e.g. a night that ended before memory recorded completions): an ISO-8601 instant, any offset
      (naive = UTC), normalized to memory's format; unparseable -> ValueError.
    - the BOUNDARY is the later of `after` and `last_maintenance_at`; `boundary_source` names it: "memory" (memory's
      completion, also when both are equal), "after" (the host's, strictly later or memory has none), "birth"
      (neither: the home never slept).
    - `count`: the records FORMED in these scopes strictly after the boundary (a record = its digest row; edges and
      bookkeeping rows are not records; closed ones still count: they were formed), or since birth. The night's
      own formations precede its completion and never count.
    - `since`: the boundary actually used, or for "birth" the oldest formed record's time (`None` for an empty
      home, `count` 0).
    - `fragmented`: {count, share, provisional, unvectored, pending}, how much of the home a sleep would make whole
      (`_fragmented`): records placed in a community provisionally since the last completed night, live records
      without a vector, live records with a title or summary still being written; `share` = count / live formed
      records (0.0 for an empty home). The host sleeps early when it passes its threshold.

    Cheap: the completion is one primary-key read; on the SQLite home the count is one indexed COUNT per pair over
    the (scope, owner_id, observed_at) range after the boundary, so it reads only the records formed since.
    Nothing is written or created (a home whose queue tables predate this read answers `last_maintenance_at`
    None)."""
    pairs = (None if scopes is None
             else sorted({(str(sc).strip().lower(), str(ow or "").strip()) for sc, ow in scopes}))
    host = _normalized_instant(after)
    row = _maintenance_row(system, pairs)
    at = row["completed_at"] if row is not None else None
    if host is not None and (at is None or host > at):
        boundary, source = host, "after"
    elif at is not None:
        boundary, source = at, "memory"
    else:
        boundary, source = None, "birth"
    count, oldest = _count_formed(system, pairs, boundary)
    return {"count": count, "last_maintenance_at": at, "since": boundary if boundary is not None else oldest,
            "boundary_source": source,
            "fragmented": _fragmented(system, pairs, int(row["seq"]) if row is not None else 0)}


def _fragmented(system: Any, pairs: Optional[List[Tuple[str, str]]], night_seq: int) -> Optional[Dict[str, Any]]:
    """How much of the home a sleep would make whole (`records_since_maintenance(...)["fragmented"]`):
    {count, share, provisional, unvectored, pending}. `provisional` = the records placed in a community at formation
    since the last completed night (`placed` events above its journal seq: the next sleep confirms or moves them);
    `unvectored` = the live formed records without a vector; `pending` = the live formed records whose title or
    summary is still being written; `count` = their sum, `share` = count / the live formed records (0.0 for an empty
    home). Live = no closure names the record. A vector-less record whose every engraved relation names a CLOSED
    record (the sleep pass's `unplaced_closed`: e.g. the summary of episodes consolidated away; no edge can ever
    place it) is not fragmentation: it counts in neither `unvectored` nor `pending` (`_closed_only`). None on a store
    that cannot say which rows carry a vector (LanceDB). SQLite home: one COUNT over the pairs' (scope, owner_id)
    range (the closures read once, as a subquery), the vector-less rows of that range, the engraved edges of those
    rows by index, and one COUNT of `placed` events over the (scope, seq) range above the night."""
    from .in_memory_store import InMemoryTripleStore
    from .journal_sqlite import SQLiteJournal
    from .sqlite_store import SQLiteTripleStore
    from .understanding import _same_file

    store, journal = system.store, system.journal
    live = pending = 0
    vectorless: Dict[str, bool] = {}  # live vector-less record (graph id) -> its title or summary is pending
    if isinstance(store, SQLiteTripleStore):
        where, params = _pair_where(pairs)
        flags = ("embedding IS NULL AS nv, COALESCE(json_extract(attributes_json, '$.pending.title'), 0) "
                 "OR COALESCE(json_extract(attributes_json, '$.pending.summary'), 0) AS pe")
        if isinstance(journal, SQLiteJournal) and _same_file(store._path, journal._path):
            fold = (f"assertion_id NOT IN (SELECT assertion_id FROM {journal._t_closures}) "
                    f"AND subject NOT IN (SELECT assertion_id FROM {journal._t_closures})")
            with store._lock:
                cur = store._conn.cursor()
                n, pe = cur.execute(
                    f"SELECT COUNT(*), COALESCE(SUM(pe), 0) FROM (SELECT {flags} "
                    f"FROM {store._table} WHERE {where} AND {_FORMED_SQL} AND {fold})", params).fetchone()
                rows = cur.execute(
                    f"SELECT subject, {flags} FROM {store._table} WHERE {where} AND {_FORMED_SQL} AND {fold} "
                    "AND embedding IS NULL", params).fetchall()
            live, pending = int(n or 0), int(pe or 0)
            vectorless = {str(subject): bool(p) for subject, _nv, p in rows}
        else:  # the closures live in another file: read them once, fold here
            closed = {str(c.assertion_id) for c in journal.closures(limit=0)}
            with store._lock:
                rows = store._conn.cursor().execute(
                    f"SELECT assertion_id, subject, {flags} FROM {store._table} WHERE {where} AND {_FORMED_SQL}",
                    params).fetchall()
            for aid, subject, nv, pe in rows:
                if str(aid) not in closed and str(subject) not in closed:
                    live, pending = live + 1, pending + int(bool(pe))
                    if nv:
                        vectorless[str(subject)] = bool(pe)
    elif isinstance(store, InMemoryTripleStore):
        closed = {str(c.assertion_id) for c in journal.closures(limit=0)}
        wanted = None if pairs is None else set(pairs)
        with store._lock:
            rows = [(r["assertion"], r.get("assertion_id"), r.get(store._vector_column)) for r in store._rows]
        for a, aid, vector in rows:
            if wanted is not None and (a.scope, a.owner_id or "") not in wanted:
                continue
            if not _formed(a) or str(aid) in closed or str(a.subject) in closed:
                continue
            marker = a.attributes.get("pending") if isinstance(a.attributes.get("pending"), dict) else {}
            is_pending = bool(marker.get("title") or marker.get("summary"))
            live, pending = live + 1, pending + int(is_pending)
            if not vector:
                vectorless[str(a.subject)] = is_pending
    else:
        return None  # a store that cannot say which rows carry a vector (LanceDB): unknown, never a made-up 0
    gone = _closed_only(system, pairs, sorted(vectorless))
    unvectored = len(vectorless) - len(gone)
    pending -= sum(1 for rid in gone if vectorless[rid])
    provisional = _placed_count(journal, pairs, night_seq)
    count = provisional + unvectored + pending
    return {"count": count, "share": round(count / live, 6) if live else 0.0, "provisional": provisional,
            "unvectored": unvectored, "pending": pending}


def _closed_only(system: Any, pairs: Optional[List[Tuple[str, str]]], subjects: Sequence[str]) -> Set[str]:
    """The records among `subjects` whose every live engraved relation (at least one; the sleep pass's relation set,
    `communities.RELATION_WEIGHTS`, either direction, in these pairs) names a CLOSED record (every digest row of it
    closed): the predicate of the pass's `unplaced_closed` (`communities.read_community_graph`). Index reads only:
    the edges of these subjects, then the digest rows and closures of their neighbours."""
    from .communities import RELATION_WEIGHTS
    from .in_memory_store import InMemoryTripleStore

    if not subjects:
        return set()
    store, journal = system.store, system.journal
    wanted = set(subjects)
    rels = sorted(RELATION_WEIGHTS)
    edges: List[Tuple[str, str, str]] = []  # (subject, object, edge assertion id)
    digests: Dict[str, List[str]] = {}      # neighbour graph id -> its formed digest assertion ids
    if isinstance(store, InMemoryTripleStore):
        allowed = None if pairs is None else set(pairs)
        with store._lock:
            rows = [(r["assertion"], str(r.get("assertion_id") or "")) for r in store._rows]
        scoped = [(a, aid) for a, aid in rows if allowed is None or (a.scope, a.owner_id or "") in allowed]
        edges = [(str(a.subject), str(a.object), aid) for a, aid in scoped if str(a.predicate or "") in rels
                 and (str(a.subject) in wanted or str(a.object) in wanted)]
        others = {o if s in wanted else s for s, o, _aid in edges}
        for a, aid in scoped:
            if str(a.subject) in others and _formed_or_bookkeeping(a):
                digests.setdefault(str(a.subject), []).append(aid)
    else:
        where, params = _pair_where(pairs)
        marks = ", ".join("?" for _ in rels)
        with store._lock:
            cur = store._conn.cursor()
            for chunk in _chunks(sorted(wanted)):
                ids = ", ".join("?" for _ in chunk)
                edges += [(str(r[0]), str(r[1]), str(r[2])) for r in cur.execute(
                    f"SELECT subject, object, assertion_id FROM {store._table} WHERE predicate IN ({marks}) "
                    f"AND (subject IN ({ids}) OR object IN ({ids})) AND {where}",
                    [*rels, *chunk, *chunk, *params]).fetchall()]
            others = sorted({o if s in wanted else s for s, o, _aid in edges})
            for chunk in _chunks(others):
                ids = ", ".join("?" for _ in chunk)
                for subject, aid, attrs in cur.execute(
                        f"SELECT subject, assertion_id, attributes_json FROM {store._table} WHERE predicate = "
                        f"'dcterms:abstract' AND subject IN ({ids}) AND {where}", [*chunk, *params]).fetchall():
                    kind = _json_field(attrs, "record_kind")
                    if kind and not _json_field(attrs, "record_edge"):
                        digests.setdefault(str(subject), []).append(str(aid))
    names = {aid for _s, _o, aid in edges} | {aid for aids in digests.values() for aid in aids} | set(digests)
    closed = _closed_among(journal, names)
    shut = {g for g, aids in digests.items() if g in closed or all(aid in closed for aid in aids)}
    to_closed: Set[str] = set()
    to_other: Set[str] = set()
    for s, o, aid in edges:
        if aid in closed or s == o:
            continue
        for end, other in ((s, o), (o, s)):
            if end in wanted:
                (to_closed if other in shut else to_other).add(end)
    return to_closed - to_other


def _formed_or_bookkeeping(a: Any) -> bool:
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    return (str(a.predicate or "") == "dcterms:abstract" and bool(attrs.get("record_kind"))
            and not attrs.get("record_edge"))


def _json_field(raw: Any, name: str) -> Any:
    import json

    try:
        value = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return None
    return value.get(name) if isinstance(value, dict) else None


def _chunks(items: Sequence[str], size: int = 400) -> List[Sequence[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _closed_among(journal: Any, names: Set[str]) -> Set[str]:
    """The names (assertion ids or graph ids) some closure names. A SQLite journal: indexed lookups by assertion id."""
    from .journal_sqlite import SQLiteJournal

    if not names:
        return set()
    if isinstance(journal, SQLiteJournal):
        out: Set[str] = set()
        with journal._lock:
            cur = journal._conn.cursor()
            for chunk in _chunks(sorted(names)):
                out |= {str(r[0]) for r in cur.execute(
                    f"SELECT assertion_id FROM {journal._t_closures} WHERE assertion_id IN "
                    f"({', '.join('?' for _ in chunk)})", list(chunk)).fetchall()}
        return out
    return {str(c.assertion_id) for c in journal.closures(limit=0)} & names


def _pair_where(pairs: Optional[List[Tuple[str, str]]]) -> Tuple[str, List[Any]]:
    if pairs is None:
        return "1 = 1", []
    if not pairs:
        return "1 = 0", []
    return ("(" + " OR ".join("(scope = ? AND owner_id = ?)" for _ in pairs) + ")",
            [v for pair in pairs for v in pair])


def _placed_count(journal: Any, pairs: Optional[List[Tuple[str, str]]], night_seq: int) -> int:
    """The `placed` events above `night_seq` in these pairs (SQLite: one COUNT over the (scope, seq) index range)."""
    from .journal_sqlite import SQLiteJournal

    if isinstance(journal, SQLiteJournal):
        where, params = _pair_where(pairs)
        with journal._lock:
            row = journal._conn.cursor().execute(
                f"SELECT COUNT(*) FROM {journal._t_events} WHERE {where} AND seq > ? AND kind = 'placed'",
                [*params, int(night_seq)]).fetchone()
        return int(row[0] or 0)
    if pairs is None:
        pairs = sorted({(e.scope, e.owner_id) for e in getattr(journal, "_events", ()) if e.kind == "placed"})
    return sum(len(journal.events(scope=sc, owner_id=ow, kinds=["placed"], since_seq=int(night_seq) + 1, limit=0))
               for sc, ow in pairs)
