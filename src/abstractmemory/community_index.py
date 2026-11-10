"""Communities at formation and in reads: the community index, `place_record`, `communities`, `community_of`.

A community (a topic of the memory graph) is a formed record of kind ``community`` written by the sleep pass
(`communities.communities_pass`): one record per version of a community, a NEW graph id per version, the stable
``attributes.community_key`` carried across versions, ``attributes.basis.version_seq`` naming the version (every
record one pass writes carries the same one), ``attributes.members`` = ``[{id, via, since_seq}]`` (record graph ids;
``via`` detected | attached | provisional). This module never writes a community record. It owns:

- the COMMUNITY INDEX of a store, in memory: the current version's centroids (unit vectors, per owner) and the
  membership map (record graph id -> community key). Loaded from the current community records the first time a
  formation needs it, then caught up ONCE per formation, inside the formation's own transaction, by comparing the
  store's row high-water mark with the one the index was loaded at (SQLite: ``MAX(rowid)``; in-memory: the row list
  and its length). Only when it moved are the rows above it checked for a community record (one indexed range read),
  and only when one appeared does the index reload: the night's pass wrote a version, once a night. A process that
  keeps a home open for days (the gateway, the loop) therefore places against the version the store holds now.
- `place_record`: the provisional community of a record being formed, decided inside the formation transaction:
  the nearest current centroid (cosine) for a record with a vector; for a record without one (or when every centroid
  of its owner is stale: computed in another embedding space) the majority community of the records its formation
  edges name; neither: the record is left unplaced (`community_of` says so; the next sleep places it). The placement
  is ONE journal event ``placed`` (an audit kind: recorded, never scored) written on the formation's own transaction
  (``MemoryEvent.provenance`` = ``{community_key, community_id, how, score, provisional: true, version_seq}``). The
  community record is never rewritten at formation; no SQL read per record, no file I/O. The next sleep confirms the
  placement (the record becomes a member) or moves it.
- the reads `communities` (the payload the gateway serves, version 2) and `community_of`: pure reads of the current
  community records plus the ``placed`` events written after their version, folded in as provisional members, and
  each community's `facts` (formation span, recent use, most-used member, bridge members, most co-used member pairs,
  what its version changed), one query each over data memory already holds.
  Eventual consistency: a record formed after the last sleep is provisional until the next sleep; before a home's
  first sleep with communities there is no version and the read says ``first_sleep_pending: true``.

Community records are not embedded and never recalled (the pass forms them without a vector): nothing here reads a
community record's vector. A centroid is an attribute (base64 float32, ``centroid_dim``, ``centroid_pin`` = the
embedding space it was computed in, '<model_id>@<dimension>').
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
import threading
import warnings
import weakref
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .canonical_text import is_record_edge, record_title
from .journal import MemoryEvent
from .records import resolve_digest_assertion
from .vector_matrix import decode_vector, numpy_module

__all__ = [
    "COMMUNITIES_PAYLOAD_VERSION",
    "COMMUNITY_KIND",
    "CommunitySchemaError",
    "FACTS_PATHS_TOP",
    "FACTS_WINDOW_DAYS",
    "PLACED_EVENT_KIND",
    "PreparedPlacement",
    "communities",
    "community_of",
    "place_record",
]

COMMUNITY_KIND = "community"
PLACED_EVENT_KIND = "placed"
#: The version of the `communities` payload (the gateway's `/communities` body).
COMMUNITIES_PAYLOAD_VERSION = 2
_DIGEST_PREDICATE = "dcterms:abstract"
#: A community record's digest row (SQLite).
_COMMUNITY_SQL = (f"predicate = '{_DIGEST_PREDICATE}' "
                  "AND json_extract(COALESCE(attributes_json, '{}'), '$.record_kind') = 'community'")
#: The relations a community record's binding envelope may draw (its revision chain): never one per member.
_DISPLAY_RELATIONS = frozenset({"refines"})


class CommunitySchemaError(ValueError):
    """A community record lacks a field this module reads (the record kind's contract with the sleep pass)."""


@dataclass(frozen=True)
class PreparedPlacement:
    """One record of a formation, as `place_record` reads it: its graph id, digest assertion id, scope pair, the
    vector the formation prepared for it (None: vector-less) and the graph ids its formation edges name."""

    record_id: str
    assertion_id: str
    scope: str
    owner_id: str
    vector: Optional[Sequence[float]] = None
    neighbours: Tuple[str, ...] = ()


@dataclass(frozen=True)
class _Community:
    key: str
    record_id: str
    assertion_id: str
    scope: str
    owner_id: str
    version_seq: int
    observed_at: str
    assertion: Any

    @property
    def attrs(self) -> Dict[str, Any]:
        return self.assertion.attributes if isinstance(self.assertion.attributes, dict) else {}


def _space_id(store: Any) -> Optional[str]:
    """The embedding space a community's `centroid_pin` names, as the sleep pass stamps it
    (`communities.vector_space_id`: '<model_id>@<dimension>' of the store's pin; a re-embed into another model or
    dimension makes every earlier centroid stale)."""
    from .communities import vector_space_id

    return vector_space_id(store)


# --------------------------------------------------------------------------- reading community records


def _require(attrs: Mapping[str, Any], name: str, where: str) -> Any:
    if name not in attrs or attrs[name] is None:
        raise CommunitySchemaError(f"community record {where} carries no attributes.{name}")
    return attrs[name]


def _parse(a: Any) -> _Community:
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    where = str(a.subject)
    head = _checked(_head_of(a))
    members = _require(attrs, "members", where)
    if not isinstance(members, list) or any(not isinstance(m, Mapping) or not m.get("id") for m in members):
        raise CommunitySchemaError(f"community record {where}: attributes.members must be a list of {{id, via, ...}}")
    return _Community(key=head.key, record_id=where, assertion_id=head.assertion_id, scope=head.scope,
                      owner_id=head.owner_id, version_seq=int(head.version_seq), observed_at=head.observed_at,
                      assertion=a)


def _is_community_digest(a: Any) -> bool:
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    return str(a.predicate or "") == _DIGEST_PREDICATE and attrs.get("record_kind") == COMMUNITY_KIND


@dataclass(frozen=True)
class _Head:
    """What a version fold needs of one community record, read without parsing its attributes."""

    key: Any
    version_seq: Any
    observed_at: str
    assertion_id: str
    record_id: str
    scope: str
    owner_id: str


def _head_of(a: Any, assertion_id: Any = None) -> _Head:
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    basis = attrs.get("basis") if isinstance(attrs.get("basis"), Mapping) else {}
    return _Head(attrs.get("community_key"), basis.get("version_seq"), str(a.observed_at or ""),
                 str(assertion_id or a.assertion_id or ""), str(a.subject), str(a.scope or ""), str(a.owner_id or ""))


def _community_heads(store: Any, cur: Any = None) -> List[_Head]:
    """Every community record of the store (every version, closed ones included), as heads. SQLite: one query that
    extracts the two fields it needs (`cur`: the caller's open transaction, when given); in-memory: the rows;
    another store: its digest rows."""
    from .in_memory_store import InMemoryTripleStore
    from .sqlite_store import SQLiteTripleStore

    if isinstance(store, SQLiteTripleStore):
        sql = (f"SELECT assertion_id, subject, scope, owner_id, observed_at, "
               "json_extract(COALESCE(attributes_json, '{}'), '$.community_key'), "
               "json_extract(COALESCE(attributes_json, '{}'), '$.basis.version_seq') "
               f"FROM {store._table} WHERE {_COMMUNITY_SQL} ORDER BY rowid")
        if cur is not None:
            rows = cur.execute(sql).fetchall()
        else:
            with store._lock:
                rows = store._conn.cursor().execute(sql).fetchall()
        return [_Head(r[5], r[6], str(r[4] or ""), str(r[0] or ""), str(r[1] or ""), str(r[2] or ""),
                      str(r[3] or "")) for r in rows]
    if isinstance(store, InMemoryTripleStore):
        with store._lock:
            return [_head_of(r["assertion"], r.get("assertion_id")) for r in store._rows
                    if _is_community_digest(r["assertion"])]
    from .store import TripleQuery

    return [_head_of(a) for a in store.query(TripleQuery(predicate=_DIGEST_PREDICATE, limit=0))
            if _is_community_digest(a)]


def _load(store: Any, assertion_ids: Sequence[str], cur: Any = None) -> Dict[str, Any]:
    """assertion id -> the community record's digest assertion, fully read (attributes parsed)."""
    from .in_memory_store import InMemoryTripleStore, _result_copy
    from .sqlite_store import SQLiteTripleStore

    wanted = sorted({str(x) for x in assertion_ids if x})
    if not wanted:
        return {}
    if isinstance(store, SQLiteTripleStore):
        sql = f"SELECT * FROM {store._table} WHERE assertion_id IN ({', '.join('?' for _ in wanted)})"
        if cur is not None:
            rows = cur.execute(sql, wanted).fetchall()
        else:
            with store._lock:
                rows = store._conn.cursor().execute(sql, wanted).fetchall()
        return {str(r["assertion_id"]): store._row_to_assertion(r) for r in rows}
    if isinstance(store, InMemoryTripleStore):
        ids = set(wanted)
        with store._lock:
            return {str(r["assertion_id"]): _result_copy(r["assertion"], r.get("assertion_id"))
                    for r in store._rows if r.get("assertion_id") in ids}
    from .store import TripleQuery

    return {str(a.assertion_id): a for a in store.query(TripleQuery(assertion_ids=tuple(wanted), limit=0))}


def _closed_ids(journal: Any, heads: Sequence[_Head], *, until_seq: Optional[int],
                journal_cur: Any = None) -> Set[str]:
    """The assertion ids among these records that a closure (any kind, seq <= until_seq) names, by assertion id or
    graph id. `journal_cur`: the caller's open transaction on the journal's own file (no journal lock taken)."""
    if not heads:
        return set()
    if journal_cur is not None:
        names = sorted({h.assertion_id for h in heads} | {h.record_id for h in heads})
        sql = (f"SELECT assertion_id FROM {journal._t_closures} WHERE assertion_id IN "
               f"({', '.join('?' for _ in names)})") + (" AND seq <= ?" if until_seq is not None else "")
        hit = {str(r[0]) for r in journal_cur.execute(sql, [*names, *([until_seq] if until_seq is not None else [])])}
        return {h.assertion_id for h in heads if h.assertion_id in hit or h.record_id in hit}
    closed: Set[str] = set()
    for h in heads:
        for name in (h.assertion_id, h.record_id):
            if name and journal.closures(assertion_id=name, until_seq=until_seq, limit=1):
                closed.add(h.assertion_id)
                break
    return closed


def _checked(h: _Head) -> _Head:
    if not isinstance(h.key, str) or not h.key.strip():
        raise CommunitySchemaError(f"community record {h.record_id} carries no attributes.community_key")
    try:
        vs = int(h.version_seq)
    except (TypeError, ValueError):
        raise CommunitySchemaError(f"community record {h.record_id} carries no attributes.basis.version_seq") from None
    return _Head(h.key.strip(), vs, h.observed_at, h.assertion_id, h.record_id, h.scope, h.owner_id)


def _fold(store: Any, journal: Any, heads: Sequence[_Head], *, as_of: Optional[int] = None, cur: Any = None,
          journal_cur: Any = None) -> Tuple[List[_Community], Optional[int], Optional[int], Optional[_Community]]:
    """(the current communities, the version's seq, the seq bound of that version's view, the newest record read).

    The newest record of each key among the versions <= `as_of` (None: every version), unless a closure names it
    (a dissolved community, or a superseded one with no newer version) up to the bound: the seq before the next
    version (`as_of` given and a later version exists), else now (None). Only the current records (and the newest
    one) are read whole."""
    checked = [_checked(h) for h in heads]
    if not checked:
        return [], None, None, None
    ordered = sorted(checked, key=lambda h: (h.version_seq, h.observed_at, h.assertion_id))
    seen = [h for h in ordered if as_of is None or h.version_seq <= int(as_of)]
    if not seen:
        raise ValueError(f"no communities version at or before seq {as_of} (the first is {ordered[0].version_seq})")
    newest: Dict[str, _Head] = {}
    for h in seen:
        newest[h.key] = h
    version_seq = int(seen[-1].version_seq)
    later = [h.version_seq for h in ordered if h.version_seq > version_seq]
    bound = min(later) - 1 if later else None
    closed = _closed_ids(journal, list(newest.values()), until_seq=bound, journal_cur=journal_cur)
    heads_now = [h for h in newest.values() if h.assertion_id not in closed]
    rows = _load(store, [h.assertion_id for h in heads_now] + [seen[-1].assertion_id], cur)
    missing = [h.assertion_id for h in heads_now + [seen[-1]] if h.assertion_id not in rows]
    if missing:
        raise CommunitySchemaError(f"community records {missing} vanished between two reads of one fold")
    current = [_parse(rows[h.assertion_id]) for h in heads_now]
    return current, version_seq, bound, _parse(rows[seen[-1].assertion_id])


# --------------------------------------------------------------------------- the in-memory index


class _Centroids:
    """One owner's usable centroids as unit vectors, keys sorted (ties resolve to the first key)."""

    __slots__ = ("keys", "rows", "matrix", "dim")

    def __init__(self, keys: List[str], rows: List[List[float]], dim: int) -> None:
        self.keys, self.rows, self.dim = keys, rows, dim
        np = numpy_module()
        self.matrix = np.asarray(rows, dtype=np.float64) if np is not None else None

    def nearest(self, vector: Sequence[float]) -> Optional[Tuple[str, float]]:
        norm = math.sqrt(sum(float(x) * float(x) for x in vector))
        if not norm or not math.isfinite(norm):
            return None
        if self.matrix is not None:
            np = numpy_module()
            scores = self.matrix @ (np.asarray(vector, dtype=np.float64) / norm)
            best = int(np.argmax(scores))
            return self.keys[best], float(scores[best])
        unit = [float(x) / norm for x in vector]
        scores = [sum(a * b for a, b in zip(row, unit)) for row in self.rows]
        best = max(range(len(scores)), key=lambda i: (scores[i], -i))
        return self.keys[best], scores[best]


def _unit_centroid(attrs: Mapping[str, Any]) -> Optional[List[float]]:
    raw = attrs.get("centroid")
    if raw is None:
        return None
    try:
        values = decode_vector(base64.b64decode(str(raw), validate=True))
    except (binascii.Error, ValueError):
        return None
    if not values:
        return None
    norm = math.sqrt(sum(v * v for v in values))
    if not norm or not math.isfinite(norm):
        return None
    return [v / norm for v in values]


def _centroid_state(attrs: Mapping[str, Any], pin_id: Optional[str]) -> Tuple[Optional[List[float]], bool]:
    """(the usable unit centroid or None, stale): a centroid is stale when it was computed in another embedding
    space (`centroid_pin` is not the store's pin now) or its stored dimension disagrees with its bytes."""
    if attrs.get("centroid") is None:
        return None, False
    unit = _unit_centroid(attrs)
    dim = attrs.get("centroid_dim")
    if unit is None or (dim is not None and int(dim) != len(unit)) or attrs.get("centroid_pin") != pin_id:
        return None, True
    return unit, False


class _CommunityIndex:
    """A store's current communities as formation reads them. Touched only under the store's write lock (every
    formation holds it), so it carries no lock of its own."""

    def __init__(self) -> None:
        self.loaded = False
        self.mark: Any = None
        self.rows_ref: Any = None  # in-memory store: the row list the mark was taken on (keeps its id unique)
        self.version_seq: Optional[int] = None
        self.communities: Dict[str, _Community] = {}
        self.members: Dict[str, str] = {}
        self.provisional: Dict[str, str] = {}
        self.batch: Dict[str, str] = {}
        self.centroids: Dict[str, _Centroids] = {}
        self.disabled: Optional[str] = None

    def community_for(self, record_id: str) -> Optional[str]:
        return self.batch.get(record_id) or self.provisional.get(record_id) or self.members.get(record_id)

    def load(self, current: Sequence[_Community], version_seq: Optional[int], pin_id: Optional[str]) -> None:
        self.communities = {c.key: c for c in current}
        self.version_seq = version_seq
        self.members = {str(m["id"]): c.key for c in current for m in c.attrs["members"]}
        self.provisional = {r: k for r, k in self.provisional.items()
                            if r not in self.members and k in self.communities}
        by_owner: Dict[str, Dict[str, List[float]]] = {}
        for c in current:
            unit, _stale = _centroid_state(c.attrs, pin_id)
            if unit is not None:
                by_owner.setdefault(c.owner_id, {})[c.key] = unit
        self.centroids = {}
        for owner, units in by_owner.items():
            dims = {len(u) for u in units.values()}
            if len(dims) != 1:
                continue  # centroids of several dimensions in one home: none is comparable, neighbours only
            keys = sorted(units)
            self.centroids[owner] = _Centroids(keys, [units[k] for k in keys], dims.pop())
        self.disabled = None
        self.loaded = True


_INDEXES: "weakref.WeakKeyDictionary[Any, _CommunityIndex]" = weakref.WeakKeyDictionary()
_INDEXES_LOCK = threading.Lock()


def _index(store: Any) -> _CommunityIndex:
    with _INDEXES_LOCK:
        idx = _INDEXES.get(store)
        if idx is None:
            idx = _INDEXES[store] = _CommunityIndex()
        return idx


def _store_mark(store: Any, cur: Any) -> Tuple[Any, Any]:
    """The store's row high-water mark (and, in-memory, the row list it was read on)."""
    from .in_memory_store import InMemoryTripleStore
    from .sqlite_store import SQLiteTripleStore

    if isinstance(store, SQLiteTripleStore):
        c = cur if cur is not None else store._conn.cursor()
        return int(c.execute(f"SELECT COALESCE(MAX(rowid), 0) FROM {store._table}").fetchone()[0]), None
    if isinstance(store, InMemoryTripleStore):
        return (id(store._rows), len(store._rows)), store._rows
    raise TypeError(f"community placement reads a SQLiteTripleStore or an InMemoryTripleStore "
                    f"(got {type(store).__name__})")


def _community_rows_since(store: Any, cur: Any, old: Any, new: Any) -> bool:
    """True when a community row may have appeared between two marks (the rows above the old one are read)."""
    from .sqlite_store import SQLiteTripleStore

    if isinstance(store, SQLiteTripleStore):
        c = cur if cur is not None else store._conn.cursor()
        return c.execute(f"SELECT 1 FROM {store._table} WHERE rowid > ? AND rowid <= ? AND {_COMMUNITY_SQL} LIMIT 1",
                         (int(old), int(new))).fetchone() is not None
    (old_list, old_len), (new_list, new_len) = old, new
    if old_list != new_list or new_len < old_len:
        return True  # rows were removed (a failed formation undone): read everything again
    return any(_is_community_digest(r["assertion"]) for r in store._rows[old_len:new_len])


def _catch_up(system: Any, *, cur: Any = None, journal_cur: Any = None) -> _CommunityIndex:
    """The store's index, current with the store (see the module docstring). `cur`: the formation's open transaction
    on the store's connection (SQLite); `journal_cur`: the same when the journal shares that file. The caller holds
    the store's write lock."""
    store = system.store
    idx = _index(store)
    if cur is None:
        from .sqlite_store import SQLiteTripleStore

        if isinstance(store, SQLiteTripleStore):
            with store._lock:
                return _catch_up_on(system, idx, store._conn.cursor(), None)
    return _catch_up_on(system, idx, cur, journal_cur)


def _catch_up_on(system: Any, idx: _CommunityIndex, cur: Any, journal_cur: Any) -> _CommunityIndex:
    store = system.store
    mark, rows_ref = _store_mark(store, cur)
    if idx.loaded and mark == idx.mark:
        return idx  # the one compare: nothing was written since the index was current
    if idx.loaded and not _community_rows_since(store, cur, idx.mark, mark):
        idx.mark, idx.rows_ref = mark, rows_ref
        return idx
    try:
        current, version_seq, _bound, _newest = _fold(store, system.journal, _community_heads(store, cur), cur=cur,
                                                      journal_cur=journal_cur)
    except CommunitySchemaError as exc:
        # Formation never fails on a community version it cannot read: it forms unplaced, loudly, and the read
        # (`communities`) raises the same error.
        warnings.warn(f"#FALLBACK: formation places no record in a community: {exc}", RuntimeWarning, stacklevel=3)
        idx.load([], None, None)
        idx.disabled = str(exc)
    else:
        idx.load(current, version_seq, _space_id(store))
    idx.mark, idx.rows_ref = mark, rows_ref
    return idx


# --------------------------------------------------------------------------- placement at formation


def _placed_event_id(record_id: str, version_seq: int) -> str:
    return hashlib.sha256(f"{record_id}|placed|{int(version_seq)}".encode("utf-8")).hexdigest()[:32]


def _locate(idx: _CommunityIndex, p: PreparedPlacement) -> Optional[Dict[str, Any]]:
    if idx.disabled or not idx.communities or idx.community_for(p.record_id) is not None:
        return None
    owner = str(p.owner_id or "")
    cents = idx.centroids.get(owner)
    if p.vector is not None and cents is not None and len(p.vector) == cents.dim:
        hit = cents.nearest(p.vector)
        if hit is not None:
            return {"community_key": hit[0], "how": "centroid", "score": round(hit[1], 6)}
    votes: Counter = Counter()
    for n in p.neighbours:
        key = idx.community_for(n)
        if key is not None and key in idx.communities and idx.communities[key].owner_id == owner:
            votes[key] += 1
    if votes:
        key, n = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        return {"community_key": key, "how": "neighbour", "score": round(n / sum(votes.values()), 6)}
    return None


def place_record(system: Any, prepared: PreparedPlacement, *, cur: Any) -> Optional[Dict[str, Any]]:
    """Place one record being formed in its provisional community and write its ONE ``placed`` event.

    `cur`: the formation's open transaction on the journal's own file (SQLite), or None (an InMemoryJournal, under
    the formation's locks; a SQLite journal in another file, after the formation's COMMIT, like its bindings).
    `form_with_tasks` calls this for every non-community record it inserts, after catching the store's community
    index up once for the whole formation; then no SQL is read here. Returns ``{community_key, community_id, how
    ("centroid" | "neighbour"), score, version_seq, event_id, seq, stored}`` or None (no version yet, the record
    already placed or a member, no usable vector and no placed neighbour). Idempotent: the event id is derived from
    the record and the version, so a replay is a journal no-op."""
    from .journal_memory import InMemoryJournal

    idx = _index(system.store)
    if not idx.loaded:
        _catch_up(system)
    found = _locate(idx, prepared)
    if found is None:
        return None
    community = idx.communities[found["community_key"]]
    provenance = {"community_key": community.key, "community_id": community.record_id, "how": found["how"],
                  "score": found["score"], "provisional": True, "version_seq": idx.version_seq}
    event = MemoryEvent(kind=PLACED_EVENT_KIND, scope=prepared.scope, owner_id=prepared.owner_id,
                        record_id=prepared.record_id, weight=0.0, actor="system", provenance=provenance,
                        event_id=_placed_event_id(prepared.record_id, int(idx.version_seq or 0)))
    journal = system.journal
    if cur is not None:
        [stored] = journal._append_events_on(cur, [event])
        new = True  # the caller's rollback undoes it
    elif isinstance(journal, InMemoryJournal):
        [stored], new_ids = journal._append_events_tracked([event])
        new = bool(new_ids)
    else:
        [stored] = journal.append_events([event])
        new = True
    idx.batch[prepared.record_id] = community.key
    return {**provenance, "event_id": stored.event_id, "seq": int(stored.seq), "stored": new}


class FormationPlacement:
    """The placements of one `form_with_tasks` call: its records read before the transaction (pure), the index
    caught up and the events written inside it, kept by the index only after the COMMIT."""

    def __init__(self, system: Any, records: Sequence[PreparedPlacement]) -> None:
        self.system = system
        self.records = list(records)
        self.stored: List[str] = []

    @classmethod
    def for_plan(cls, system: Any, plan: Any, missing: Sequence[Any],
                 vectors: Mapping[int, Optional[Sequence[float]]]) -> "FormationPlacement":
        """`missing`: the plan's assertions this formation writes; `vectors`: position in `missing` -> vector."""
        edges: Dict[str, List[str]] = {}
        for a in plan.assertions:
            if is_record_edge(a):
                edges.setdefault(str(a.subject), []).append(str(a.object))
        records = []
        for i, a in enumerate(missing):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            kind = attrs.get("record_kind")
            if (not kind or kind == COMMUNITY_KIND or attrs.get("record_edge") or attrs.get("bookkeeping")
                    or str(a.predicate or "") != _DIGEST_PREDICATE):
                continue
            records.append(PreparedPlacement(
                record_id=str(a.subject), assertion_id=str(a.assertion_id or ""), scope=str(a.scope or ""),
                owner_id=str(a.owner_id or ""), vector=vectors.get(i),
                neighbours=tuple(sorted(set(edges.get(str(a.subject), ()))))))
        return cls(system, records)

    def catch_up(self, *, cur: Any = None, journal_cur: Any = None) -> None:
        if self.records:
            _catch_up(self.system, cur=cur, journal_cur=journal_cur)

    def place(self, *, cur: Any = None, inserted: Optional[Iterable[str]] = None) -> None:
        """Place every record (only those whose digest rows this attempt `inserted`, when named)."""
        only = None if inserted is None else {str(x) for x in inserted}
        for p in self.records:
            if only is not None and p.assertion_id not in only:
                continue
            res = place_record(self.system, p, cur=cur)
            if res is not None and res["stored"]:
                self.stored.append(res["event_id"])

    def committed(self) -> None:
        if self.records:
            idx = _index(self.system.store)
            idx.provisional.update(idx.batch)
            idx.batch.clear()

    def aborted(self) -> None:
        if self.records:
            _index(self.system.store).batch.clear()


# --------------------------------------------------------------------------- reads


def _pending_fields(attrs: Mapping[str, Any]) -> List[str]:
    marker = attrs.get("pending") if isinstance(attrs.get("pending"), Mapping) else {}
    return [f for f in ("title", "summary") if marker.get(f)]


def _served(c: _Community, provisional_ids: List[str], pin_id: Optional[str],
            facts: Mapping[str, Any]) -> Dict[str, Any]:
    attrs = c.attrs
    layout = _require(attrs, "layout", c.record_id)
    if not isinstance(layout, Mapping) or "xy" not in layout or "radius" not in layout:
        raise CommunitySchemaError(f"community record {c.record_id}: attributes.layout must carry xy and radius")
    pending = _pending_fields(attrs)
    _unit, stale = _centroid_state(attrs, pin_id)
    return {
        "id": c.record_id,
        "key": c.key,
        "title": record_title(attrs),
        "summary": None if "summary" in pending else str(c.assertion.object or ""),
        "pending": pending,
        "verdict": attrs.get("verdict"),
        "size": int(_require(attrs, "size", c.record_id)),
        "kinds": {str(k): int(v) for k, v in dict(_require(attrs, "kinds", c.record_id)).items()},
        "members": [{"id": str(m["id"]), "via": str(m.get("via") or "")} for m in attrs["members"]],
        "provisional_ids": provisional_ids,
        "cohesion": attrs.get("cohesion"),
        "layout": {"xy": list(layout["xy"]), "radius": layout["radius"], "seats": dict(layout.get("seats") or {})},
        "centroid_stale": stale,
        "facts": dict(facts),
    }


#: The window of `facts.activity` and `facts.paths` (days back from the system's clock).
FACTS_WINDOW_DAYS = 7
#: How many co-used member pairs `facts.paths` names.
FACTS_PATHS_TOP = 5


def _shared_journal(store: Any, journal: Any) -> bool:
    from .journal_sqlite import SQLiteJournal
    from .sqlite_store import SQLiteTripleStore
    from .understanding import _same_file

    return (isinstance(store, SQLiteTripleStore) and isinstance(journal, SQLiteJournal)
            and _same_file(store._path, journal._path))


def _pair_sql(pairs: Iterable[Tuple[str, str]], prefix: str = "") -> Tuple[str, List[Any]]:
    pairs = sorted(set(pairs))
    if not pairs:
        return "1 = 0", []
    return ("(" + " OR ".join(f"({prefix}scope = ? AND {prefix}owner_id = ?)" for _ in pairs) + ")",
            [v for pair in pairs for v in pair])


def _window_start(system: Any) -> str:
    from datetime import datetime, timedelta, timezone

    from .journal import utc_now_iso

    clock = getattr(system, "_clock", None) or utc_now_iso
    now = datetime.fromisoformat(str(clock()).replace("Z", "+00:00"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now.astimezone(timezone.utc) - timedelta(days=FACTS_WINDOW_DAYS)).isoformat(timespec="microseconds")


def _facts_inputs(system: Any, pairs: Set[Tuple[str, str]], since: str) -> Tuple[Dict[str, Tuple[str, str, int]],
                                                                                 List[Tuple[str, str]],
                                                                                 Counter, Counter]:
    """The data `facts` folds, one read each: (graph id -> (assertion id, formed at, uses ever)), the live engraved
    edges, the `selected` events per assertion id in the window, the `co_selected` events per pair in the window."""
    import json as _json

    from .in_memory_store import InMemoryTripleStore
    from .sqlite_store import SQLiteTripleStore

    store, journal = system.store, system.journal
    digests: Dict[str, Tuple[str, str, int]] = {}
    edges: List[Tuple[str, str]] = []
    used: Counter = Counter()
    co_used: Counter = Counter()
    shared = _shared_journal(store, journal)
    closed: Set[str] = set() if shared else {str(c.assertion_id) for c in journal.closures(limit=0)}
    if isinstance(store, SQLiteTripleStore):
        where, params = _pair_sql(pairs, "t.")
        uses = (f"COALESCE((SELECT n FROM {journal._t_counts} k WHERE k.record_id = t.assertion_id), 0)"
                if shared else "0")
        live = (f" AND t.assertion_id NOT IN (SELECT assertion_id FROM {journal._t_closures})" if shared else "")
        with store._lock:
            c = store._conn.cursor()
            rows = c.execute(f"SELECT t.subject, t.assertion_id, t.observed_at, {uses} FROM {store._table} t "
                             f"WHERE t.predicate = '{_DIGEST_PREDICATE}' AND {where}", params).fetchall()
            edge_rows = c.execute(
                f"SELECT t.subject, t.object, t.assertion_id FROM {store._table} t WHERE {where} AND "
                f"json_extract(COALESCE(t.attributes_json, '{{}}'), '$.record_edge') IS NOT NULL{live}",
                params).fetchall()
        for subject, aid, at, n in rows:
            prev = digests.get(str(subject))
            if prev is None or str(at or "") < prev[1]:
                digests[str(subject)] = (str(aid), str(at or ""), int(n or 0))
        edges = [(str(a), str(b)) for a, b, aid in edge_rows if str(aid) not in closed]
    elif isinstance(store, InMemoryTripleStore):
        with store._lock:
            rows = [(r["assertion"], str(r.get("assertion_id") or "")) for r in store._rows]
        for a, aid in rows:
            if (a.scope, a.owner_id or "") not in pairs:
                continue
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_edge"):
                if aid not in closed:
                    edges.append((str(a.subject), str(a.object)))
            elif str(a.predicate or "") == _DIGEST_PREDICATE and str(a.subject) not in digests:
                digests[str(a.subject)] = (aid, str(a.observed_at or ""), 0)
    else:
        raise TypeError(f"communities facts read a SQLiteTripleStore or an InMemoryTripleStore "
                        f"(got {type(store).__name__})")
    if not shared:
        digests = {g: (aid, at, int(journal.selected_count(aid))) for g, (aid, at, _n) in digests.items()}
    from .journal_sqlite import SQLiteJournal

    if isinstance(journal, SQLiteJournal):
        where, params = _pair_sql(pairs)
        with journal._lock:
            events = journal._conn.cursor().execute(
                f"SELECT kind, record_id, pair_ids_json FROM {journal._t_events} WHERE {where} "
                "AND kind IN ('selected', 'co_selected') AND observed_at >= ?", [*params, since]).fetchall()
        for kind, rid, pair_json in events:
            if kind == "selected" and rid:
                used[str(rid)] += 1
            elif kind == "co_selected" and pair_json:
                pair = _json.loads(pair_json)
                if isinstance(pair, list) and len(pair) == 2:
                    co_used[tuple(sorted(str(x) for x in pair))] += 1
    else:
        for scope, owner in sorted(pairs):
            for e in journal.events(scope=scope, owner_id=owner, kinds=["selected", "co_selected"], limit=0):
                if str(e.observed_at or "") < since:
                    continue
                if e.kind == "selected" and e.record_id:
                    used[str(e.record_id)] += 1
                elif e.kind == "co_selected" and e.pair_ids:
                    co_used[tuple(sorted(str(x) for x in e.pair_ids))] += 1
    return digests, edges, used, co_used


def _facts(system: Any, pairs: Set[Tuple[str, str]], current: Sequence[_Community],
           version_seq: int) -> Dict[str, Dict[str, Any]]:
    """community key -> {span: {first, last}, activity, hub, bridges, paths: [{from, to, count}],
    changed_since_last_sleep: {added, moved, split_from}} over the store and journal as they are now."""
    digests, edges, used, co_used = _facts_inputs(system, pairs, _window_start(system))
    member_of = {str(m["id"]): c.key for c in current for m in c.attrs["members"]}
    graph_of = {aid: g for g, (aid, _at, _n) in digests.items()}
    bridges: Dict[str, Set[str]] = {c.key: set() for c in current}
    for a, b in edges:
        ka, kb = member_of.get(a), member_of.get(b)
        if ka is not None and kb is not None and ka != kb:
            bridges[ka].add(a)
            bridges[kb].add(b)
    paths: Dict[str, Counter] = {c.key: Counter() for c in current}
    for (x, y), n in co_used.items():
        gx, gy = graph_of.get(x), graph_of.get(y)
        if gx is not None and gy is not None and gx != gy and member_of.get(gx) is not None \
                and member_of.get(gx) == member_of.get(gy):
            paths[member_of[gx]][tuple(sorted((gx, gy)))] += n
    out: Dict[str, Dict[str, Any]] = {}
    for c in current:
        ids = [str(m["id"]) for m in c.attrs["members"]]
        known = [digests[i] for i in ids if i in digests]
        times = sorted(at for _aid, at, _n in known if at)
        ever = sorted(((-digests[i][2], i) for i in ids if i in digests and digests[i][2] > 0))
        basis = c.attrs.get("basis") or {}
        changed = (c.version_seq == version_seq)
        out[c.key] = {
            "span": {"first": times[0] if times else None, "last": times[-1] if times else None},
            "activity": sum(used.get(aid, 0) for aid, _at, _n in known),
            "hub": ever[0][1] if ever else None,
            "bridges": sorted(bridges[c.key]),
            "paths": [{"from": a, "to": b, "count": n} for (a, b), n in
                      sorted(paths[c.key].items(), key=lambda kv: (-kv[1], kv[0]))[:FACTS_PATHS_TOP]],
            "changed_since_last_sleep": {
                "added": int(_require(basis, "moved_in", c.record_id)) if changed else 0,
                "moved": int(_require(basis, "moved_out", c.record_id)) if changed else 0,
                "split_from": basis.get("split_from") if changed else None,
            },
        }
    return out


def _empty_payload() -> Dict[str, Any]:
    return {"version": COMMUNITIES_PAYLOAD_VERSION, "version_seq": None, "first_sleep_pending": True,
            "algorithm": None, "communities": [], "links": []}


def _placed_since(journal: Any, pairs: Iterable[Tuple[str, str]], *, since_seq: int,
                  until_seq: Optional[int], record_id: Optional[str] = None) -> Dict[str, Tuple[int, MemoryEvent]]:
    """record graph id -> (seq, its newest `placed` event) written after a version, per scope pair."""
    out: Dict[str, Tuple[int, MemoryEvent]] = {}
    for scope, owner in sorted(set(pairs)):
        for e in journal.events(scope=scope, owner_id=owner, record_id=record_id, kinds=[PLACED_EVENT_KIND],
                                since_seq=since_seq, until_seq=until_seq, limit=0):
            prev = out.get(str(e.record_id))
            if prev is None or int(e.seq) > prev[0]:
                out[str(e.record_id)] = (int(e.seq), e)
    return out


def communities(system: Any, *, scopes: Sequence[Tuple[str, str]], owner_id: str,
                version: Optional[int] = None) -> Dict[str, Any]:
    """The home's communities, the payload the gateway serves (version 2). PURE READ: the current community records
    of these scope pairs and owner (or, with `version`, those of that version: the newest record of each community at
    or before that seq, viewed up to the next version), plus the ``placed`` events written after the version folded
    in as provisional members.

    Returns ``{version: 2, version_seq, first_sleep_pending, algorithm, communities: [{id (the version's record id),
    key (stable across versions), title, summary, pending, verdict, size, kinds, members: [{id, via}],
    provisional_ids, cohesion, layout: {xy, radius, seats}, centroid_stale, facts}], links: [{a, b, weight}]}`` with
    communities by size (largest first) then key, `links` keyed on community keys. `facts` (`_facts`, over the store
    and journal as they are now): {span: {first, last}, activity, hub, bridges, paths: [{from, to, count}],
    changed_since_last_sleep: {added, moved, split_from}}. No version yet: ``communities:
    []``, ``first_sleep_pending: true``. Raises `CommunitySchemaError` when a community record lacks a field it
    serves, ValueError for a `version` older than the first."""
    store, journal = system.store, system.journal
    pairs = {(str(s or "").strip().lower(), str(o or "").strip()) for s, o in scopes}
    owner = str(owner_id or "").strip()
    heads = [h for h in _community_heads(store) if (h.scope, h.owner_id) in pairs and h.owner_id == owner]
    current, version_seq, bound, newest = _fold(store, journal, heads, as_of=version)
    if version_seq is None:
        return _empty_payload()
    members = {str(m["id"]) for c in current for m in c.attrs["members"]}
    keys = {c.key for c in current}
    provisional: Dict[str, List[str]] = {k: [] for k in keys}
    placed = _placed_since(journal, pairs, since_seq=version_seq + 1, until_seq=bound)
    for rid, (_seq, e) in sorted(placed.items(), key=lambda kv: (kv[1][0], kv[0])):
        key = str(e.provenance["community_key"])
        if rid not in members and key in keys:
            provisional[key].append(rid)
    pin_id = _space_id(store)
    facts = _facts(system, pairs, current, version_seq)
    served = [_served(c, provisional[c.key], pin_id, facts[c.key]) for c in current]
    served.sort(key=lambda s: (-s["size"], s["key"]))
    links: Dict[Tuple[str, str], float] = {}
    for c in sorted(current, key=lambda c: (c.version_seq, c.key)):  # a newer version's weight wins
        for link in c.attrs.get("links") or ():
            other = str(link["to"])
            if other in keys and other != c.key:
                links[tuple(sorted((c.key, other)))] = float(link["weight"])
    basis = newest.attrs.get("basis") or {}
    return {
        "version": COMMUNITIES_PAYLOAD_VERSION,
        "version_seq": version_seq,
        "first_sleep_pending": False,
        "algorithm": _require(basis, "algorithm", newest.record_id),
        "communities": served,
        "links": [{"a": a, "b": b, "weight": w} for (a, b), w in sorted(links.items())],
    }


def community_of(system: Any, record_id: str) -> Dict[str, Any]:
    """The community a record is in now (PURE READ): ``{record_id (graph id), community_key, community_id (the current
    version's record id), provisional, via, how, score, version_seq, first_sleep_pending}``. A member of the current
    version: ``provisional: false``, ``via`` as the version names it. Placed at formation since the version:
    ``provisional: true``, ``via: "provisional"``, ``how`` / ``score`` of its ``placed`` event. In no community
    (unplaced: no usable vector and no placed neighbour, or formed before the version without a placement):
    ``community_key: null``. No version yet: ``first_sleep_pending: true``. Unknown record or a community record:
    ValueError."""
    store, journal = system.store, system.journal
    a = resolve_digest_assertion(store, str(record_id or "").strip())
    if a is None:
        raise ValueError(f"unknown record {record_id!r}: no formed record with that graph id or digest assertion id")
    if (a.attributes or {}).get("record_kind") == COMMUNITY_KIND:
        raise ValueError(f"{record_id!r} is a community record: read it with communities()")
    gid, owner = str(a.subject), str(a.owner_id or "")
    heads = [h for h in _community_heads(store) if h.owner_id == owner]
    current, version_seq, _bound, _newest = _fold(store, journal, heads)
    out: Dict[str, Any] = {"record_id": gid, "community_key": None, "community_id": None, "provisional": False,
                           "via": None, "how": None, "score": None, "version_seq": version_seq,
                           "first_sleep_pending": version_seq is None}
    if version_seq is None:
        return out
    for c in current:
        for m in c.attrs["members"]:
            if str(m["id"]) == gid:
                out.update(community_key=c.key, community_id=c.record_id, via=str(m.get("via") or ""))
                return out
    by_key = {c.key: c for c in current}
    placed = _placed_since(journal, [(str(a.scope), owner)], since_seq=version_seq + 1, until_seq=None,
                           record_id=gid)
    if gid in placed:
        e = placed[gid][1]
        key = str(e.provenance["community_key"])
        if key in by_key:
            out.update(community_key=key, community_id=by_key[key].record_id, provisional=True, via="provisional",
                       how=e.provenance.get("how"), score=e.provenance.get("score"))
    return out


def display_relations(kind: Any, edges: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """The formation edges a binding envelope draws for a record of `kind`: a community record's revision chain only,
    never an edge per member (replay)."""
    if kind != COMMUNITY_KIND or not edges:
        return edges
    kept = [e for e in edges if e.get("relation") in _DISPLAY_RELATIONS]
    return kept or None
