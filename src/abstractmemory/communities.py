"""Memory-owned communities: the topics of a home, formed while he sleeps (COMMUNITIES-DESIGN.md §1, 2026-11-10,
with the Fable review deltas D1, D2, D4 and D6).

One record kind, `community`, revised like a world-model card: every version is a NEW graph record
(`record_id_for("community", "community|<owner>|<key>|v<version_seq>", 0)`, `refines` -> the previous version, the
previous one closed `supersede`); the stable identity is `attributes.community_key` (`ex:community-<12 hex>`, minted
once from the first member set and carried across versions by the Jaccard match). A community is engine state, never
a memory (Fable D4): `attributes.bookkeeping` keeps it off every recall shelf, every keyword index and every memory
scan, and its digest is never embedded (`canonical_text.NON_EMBEDDED_KINDS`).

Attributes of a version (the read, `communities()`, serves them):

- `community_key`; `members`: [{id, via: detected | attached | provisional, since_seq}] in join order
  (since_seq, id); `size`; `kinds` {kind: n};
- `centroid` (base64 little-endian float32 unit mean of the vectored members), `centroid_dim`, `centroid_pin`
  (`vector_space_id`: the embedding model and dimension the vectors live in), `cohesion` (mean member cosine to the
  centroid);
- the title and the digest (= summary) under the standard authored contract (`formation_authoring.author_and_shape`):
  authored at formation from the BRIEFING (the provisional body: a stable kind-mixed member sample, the previous title,
  the sibling titles that must differ), else pending with `title.author` / `digest.author` tasks for the existing
  drainer, at `memory_tasks.COMMUNITY_PRIORITY` (ahead of every other pending record: a drainer with a small budget
  names the topics before a long repair tail); `verdict` = "no_common_subject" when the author said so (an authored
  terminal state, no task);
- `title_basis` {members (the membership the title was authored for), sample_ids (what the author saw),
  prompt_version, version_seq}: a title and summary carry to the next version while Jaccard(members, basis) >= 0.8
  and the prompt version is the same, else they are authored again from the fresh briefing;
- `layout` {xy, radius, seats {member id: [dx, dy]}} (data, computed here; the app draws it); `links` [{to: key,
  weight}] (summed cross weight);
- `basis` {version_seq, algorithm, params, membership_hash, previous_id, matched_jaccard, moved_in, moved_out,
  split_from?}. `version_seq` is the journal seq the pass READ the home at (the partition's snapshot); every record of
  one version carries the same one, and the records formed after it are exactly those a read folds in provisionally.

Verbs:

- `communities_pass(system, *, scopes, owner_id, author, cancelled, budget=None, seed_previous=True,
  detect_kinds=None) -> receipt`: read the graph (one SQL for the digests, one for the engraved edges, the vectors
  from the store's in-memory `VectorMatrix`) -> detect (deterministic Louvain warm-started from the previous version,
  over every VECTORED record; `written_amid` never drives detection) -> refine (giant split, connectivity, tiny
  communities merged whole) -> attach the vector-less records by their engraved neighbours -> match keys -> layout ->
  author the changed communities (`budget` = the most author calls, all of it for the topics: one call per new or
  changed topic writes its title AND its summary, where its queue tasks would take two; the rest form pending, their
  tasks ahead of every other pending record) -> `cancelled()` ONCE ->
  ONE commit-guarded transaction (new versions + their bindings + closures + tasks) -> receipt. An unchanged pass
  writes nothing.

  Detection is BOUNDED: at most `MAX_DETECTION_ROUNDS` (5) Louvain + refine rounds, each warm-started from the
  previous round's refined partition, in a fixed order. The rounds stop at the first of: a fixed point (the round
  gives the previous round's partition: kept); a repeated partition (the detection oscillates, e.g. a hub record and
  its pendant records flipping between two communities: the cycle's smallest partition in canonical order is kept,
  whichever round entered the cycle, so a rerun seeded from it lands on it again); the cap (the last round's partition is kept).
  The receipt reports the count as `timings_ms.rounds`.

  Receipt fields about the records no community holds: `unvectored` [ids] (every open formed record without a
  vector, placed or not); `unplaced` [ids] (the records no community holds tonight: no vector, no placed engraved
  neighbour, not kept provisionally in their previous community); `unplaced_closed` [ids], a subset of both: the
  unplaced vector-less records whose every live engraved relation (either direction, at least one) names a CLOSED
  record (every digest row closed), e.g. the summary of episodes consolidated away. Their neighbours are gone, so no edge places them; the fragmentation share
  (`sleep_cadence.records_since_maintenance(...)["fragmented"]`) can leave them out.
- `embed_missing(system, *, scopes, owner_id, record_ids=None, cancelled) -> {embedded, skipped, failed, ...}`: the
  vector-less records embedded with the store's own embedder, one small guarded commit per vector.

Pure Python + numpy (memory's `[fast]` extra; without numpy the pass is skipped with its reason). No networkx, no
compiled code, no keyword, no heuristic on text.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import time
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .canonical_text import record_title

__all__ = [
    "ALGORITHM",
    "COMMUNITY_KIND",
    "CommunityGraph",
    "CommunityPlanError",
    "Detection",
    "MEMBER_VIAS",
    "PROMPT_VERSION",
    "PreviousCommunity",
    "RELATION_WEIGHTS",
    "briefing_sample",
    "community_records",
    "communities_pass",
    "detect_communities",
    "embed_missing",
    "louvain",
    "read_community_graph",
    "validate_community_attributes",
    "vector_space_id",
]

COMMUNITY_KIND = "community"
ALGORITHM = "louvain-warm-v1"
#: Names the briefing's wording: a change re-authors every title on purpose (it rides `title_basis`).
PROMPT_VERSION = "community-briefing-v1"
#: The provisional body's label (the machine-composed briefing; an authored summary replaces it).
BRIEFING_METHOD = "mechanical-community-briefing-v1"
KEY_PREFIX = "ex:community-"
MEMBER_VIAS = frozenset({"detected", "attached", "provisional"})

#: Engraved relations, weighted by kind; each edge divides by sqrt(fan-out of its subject under that relation).
RELATION_WEIGHTS: Mapping[str, float] = MappingProxyType({
    "summarizes": 1.0, "continues": 1.0, "refines": 1.0, "derived_from": 1.0,
    "reflected_in": 0.8, "from_session": 0.6, "mentions": 0.5, "written_amid": 0.5,
})
#: Relations that never drive detection (context, not topic: a diary entry written amid episodes of several
#: subjects). They still place a vector-less record and count in `links`.
DETECTION_EXCLUDED_RELATIONS = frozenset({"written_amid"})

KNN_K = 6
KNN_MIN_COSINE = 0.45
KNN_WEIGHT = 0.5
KNN_BLOCK_ROWS = 1000
#: The most cosines one kNN block holds (block rows x n): the block's one float64 copy (rounded, masked and negated
#: in place), argpartition's working copy and its int64 indices stay ~26 bytes x this (~26 MB), whatever the home's
#: size (Fable review M1 #5: three full-size copies of a 1000-row block cost +433 MB at 10k records). Homes up to 1000
#: vectored records keep the one 1000-row block they always had.
KNN_BLOCK_CELLS = 1_000_000
RESOLUTION = 1.0
SPLIT_RESOLUTION = 1.5
SPLIT_SHARE = 0.25
SPLIT_MIN_SIZE = 40
MIN_COMPONENT_SIZE = 3
MIN_COMMUNITY_SIZE = 5
#: The warm-started detection is re-seeded from its own refined output until it no longer moves (a fixed point:
#: rerunning the pass on an unchanged graph moves nothing; castor settles in 2-4 rounds), HARD-capped at this many
#: Louvain + refine rounds (no hidden unbounded cost); a repeated partition stops it earlier (`_stabilise`).
MAX_DETECTION_ROUNDS = 5
KEY_MATCH_FLOOR = 0.5
TITLE_KEEP_JACCARD = 0.8
BRIEFING_HUBS = 3
#: Token estimate of the member lines one briefing carries (whole lines only: a line that does not fit is left out).
BRIEFING_TOKEN_BUDGET = 1500
#: Sibling titles named in one briefing (all of them up to this, else the most linked first); the collision check
#: covers every sibling regardless.
SIBLING_TITLES_MAX = 40
RADIUS_UNIT = 10.0
SEAT_FILL = 0.9
CIRCLE_GAP = 2.0
RELAX_MAX_ITERATIONS = 2000
GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))
NO_COMMON_SUBJECT = "no_common_subject"
PASS_NAME = "communities_pass"


class CommunityPlanError(RuntimeError):
    """The formation plan of a version names another record id than the one the pass derived for it
    (`record_id_for("community", ...)`): records.build_formation_plan and the pass disagree, nothing is written."""


def _np() -> Any:
    try:
        import numpy

        return numpy
    except ImportError:  # pragma: no cover - exercised where numpy is absent
        return None


# --------------------------------------------------------------------------- the record kind


def validate_community_attributes(attributes: Mapping[str, Any]) -> Dict[str, Any]:
    """The `community` kind's formation rule (records.MemoryRecordInput calls it): a stable key, a non-empty member
    list of {id, via, since_seq} with unique ids and a known `via`; the record is engine state (`bookkeeping`)."""
    attrs = dict(attributes or {})
    key = attrs.get("community_key")
    if not (isinstance(key, str) and key.startswith(KEY_PREFIX) and len(key) > len(KEY_PREFIX)):
        raise ValueError(f"kind='community' requires attributes.community_key '{KEY_PREFIX}<hex>' (got {key!r})")
    members = attrs.get("members")
    if not isinstance(members, (list, tuple)) or not members:
        raise ValueError("kind='community' requires attributes.members: a non-empty list of {id, via, since_seq}")
    seen: Set[str] = set()
    clean: List[Dict[str, Any]] = []
    for m in members:
        if not isinstance(m, Mapping):
            raise ValueError(f"kind='community' members are {{id, via, since_seq}} mappings (got {m!r})")
        mid = str(m.get("id") or "").strip()
        via = str(m.get("via") or "").strip()
        if not mid:
            raise ValueError("kind='community' every member names its record id")
        if mid in seen:
            raise ValueError(f"kind='community' member {mid!r} is listed twice")
        if via not in MEMBER_VIAS:
            raise ValueError(f"kind='community' member via must be one of {sorted(MEMBER_VIAS)} (got {via!r})")
        try:
            since = int(m.get("since_seq"))
        except (TypeError, ValueError):
            raise ValueError(f"kind='community' member {mid!r} needs an integer since_seq") from None
        seen.add(mid)
        clean.append({"id": mid, "via": via, "since_seq": since})
    attrs["members"] = clean
    attrs["bookkeeping"] = True
    return attrs


def vector_space_id(store: Any) -> Optional[str]:
    """The embedding space the stored vectors live in: '<model_id>@<dimension>' from the store's pin (a re-embed
    into another model or dimension changes it; rewriting one vector does not). None for a pinless store."""
    pin = store.embedding_pin() if hasattr(store, "embedding_pin") else None
    if not pin:
        return None
    return f"{pin.get('model_id') or 'unknown'}@{pin.get('dimension') or '?'}"


def _encode_centroid(vec: Any) -> str:
    np = _np()
    return base64.b64encode(np.asarray(vec, dtype="<f4").tobytes()).decode("ascii")


def _decode_centroid(text: Any, dim: Any) -> Any:
    np = _np()
    if not isinstance(text, str) or not text:
        return None
    try:
        raw = np.frombuffer(base64.b64decode(text.encode("ascii")), dtype="<f4").astype(np.float64)
    except (ValueError, TypeError):
        return None
    if dim is not None and raw.shape[0] != int(dim):
        return None
    norm = float(np.linalg.norm(raw))
    return raw / norm if norm > 0 else None


def _hex(text: str, n: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    return inter / float(len(a) + len(b) - inter) if inter else 0.0


# --------------------------------------------------------------------------- the graph read


@dataclass
class _Node:
    id: str
    assertion_id: str
    kind: str
    title: Optional[str]
    digest: str
    scope: str
    owner_id: str
    observed_at: str


@dataclass
class PreviousCommunity:
    """One current community version as the pass reads it (the previous version of tonight's)."""

    key: str
    record_id: str = ""
    assertion_id: str = ""
    members: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # id -> {id, via, since_seq}
    centroid: Any = None  # unit vector in the current space, or None (none stored / another space)
    attrs: Dict[str, Any] = field(default_factory=dict)
    title: Optional[str] = None
    digest: str = ""
    scope: str = ""


@dataclass
class CommunityGraph:
    """What the pass reads: the open formed records of the home (communities and bookkeeping rows excluded), their
    engraved relations, their unit vectors, and the current community versions."""

    nodes: Dict[str, _Node] = field(default_factory=dict)
    engraved: List[Tuple[str, str, str]] = field(default_factory=list)  # (subject, relation, object), deduped
    vec_ids: List[str] = field(default_factory=list)
    vectors: Any = None  # numpy (n, d) float32 unit rows, aligned with vec_ids
    space: Optional[str] = None
    seq: int = 0
    previous: List[PreviousCommunity] = field(default_factory=list)
    #: The records whose every open engraved relation (at least one) names a CLOSED record (their neighbours are
    #: gone: e.g. the summary of consolidated episodes). The receipt's `unplaced_closed` = the unplaced vector-less ones.
    closed_only: Set[str] = field(default_factory=set)
    _vindex: Any = field(default=None, init=False, repr=False, compare=False)

    @property
    def vindex(self) -> Dict[str, int]:
        """record id -> its row in `vectors` (rebuilt whenever `vec_ids` is replaced)."""
        held = self._vindex
        if held is None or held[0] is not self.vec_ids or held[1] != len(self.vec_ids):
            held = (self.vec_ids, len(self.vec_ids), {rid: i for i, rid in enumerate(self.vec_ids)})
            self._vindex = held
        return held[2]


def _pairs(scopes: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for pair in scopes or ():
        scope, owner = str(pair[0] or "").strip().lower(), str(pair[1] or "").strip()
        if scope and (scope, owner) not in out:
            out.append((scope, owner))
    if not out:
        raise ValueError("communities need at least one (scope, owner_id) pair with a non-empty scope")
    return out


def _pair_clause(pairs: Sequence[Tuple[str, str]]) -> Tuple[str, List[Any]]:
    parts, params = [], []
    for scope, owner in pairs:
        if owner:
            parts.append("(scope = ? AND owner_id = ?)")
            params.extend([scope, owner])
        else:
            parts.append("(scope = ?)")
            params.append(scope)
    return " OR ".join(parts), params


def _attrs_of(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _previous_of(aid: str, subject: str, scope: str, attrs: Dict[str, Any], digest: str,
                 space: Optional[str]) -> Optional[PreviousCommunity]:
    key = attrs.get("community_key")
    if not isinstance(key, str) or not key.startswith(KEY_PREFIX):
        return None
    members: Dict[str, Dict[str, Any]] = {}
    for m in attrs.get("members") or ():
        if isinstance(m, Mapping) and str(m.get("id") or ""):
            members[str(m["id"])] = {"id": str(m["id"]), "via": str(m.get("via") or "detected"),
                                     "since_seq": int(m.get("since_seq") or 0)}
    centroid = None
    if space is not None and attrs.get("centroid_pin") == space:
        centroid = _decode_centroid(attrs.get("centroid"), attrs.get("centroid_dim"))
    return PreviousCommunity(key=key, record_id=subject, assertion_id=aid, members=members, centroid=centroid,
                             attrs=attrs, title=record_title(attrs), digest=digest, scope=scope)


def read_community_graph(system: Any, *, scopes: Sequence[Tuple[str, str]], owner_id: str) -> CommunityGraph:
    """The pass's read (PURE READ). SQLite: one SQL for the digests, one for the engraved edges, the closures once,
    the vectors from the store's in-memory `VectorMatrix` (never a re-embed). In-memory store: the same from its
    rows. Requires numpy (the caller checks)."""
    from .in_memory_store import InMemoryTripleStore
    from .sqlite_store import SQLiteTripleStore

    np = _np()
    pairs = _pairs(scopes)
    store, journal = system.store, system.journal
    graph = CommunityGraph(space=vector_space_id(store), seq=int(journal.current_seq()))
    closed = {str(c.assertion_id) for c in journal.closures(limit=0)}
    relations = tuple(RELATION_WEIGHTS)
    digests: List[Tuple[str, str, str, str, str, str, Dict[str, Any]]] = []
    edge_rows: List[Tuple[str, str, str, str]] = []
    vector_of: Dict[str, Any] = {}
    if isinstance(store, SQLiteTripleStore):
        cond, params = _pair_clause(pairs)
        table = store._table
        with store._lock:
            cur = store._conn.cursor()
            for r in cur.execute(
                    f"SELECT assertion_id, subject, scope, owner_id, object, observed_at, attributes_json FROM {table} "
                    f"WHERE predicate = 'dcterms:abstract' AND ({cond}) ORDER BY observed_at DESC, assertion_id DESC",
                    params).fetchall():
                digests.append((r[0], r[1], r[2], r[3] or "", r[4] or "", r[5] or "", _attrs_of(r[6])))
            marks = ", ".join("?" for _ in relations)
            for r in cur.execute(
                    f"SELECT assertion_id, subject, predicate, object FROM {table} "
                    f"WHERE predicate IN ({marks}) AND ({cond})", (*relations, *params)).fetchall():
                edge_rows.append((r[0], r[1], r[2], r[3]))
            matrix = store._synced_vectors()
            if matrix is not None:
                wanted = [d[0] for d in digests if d[0] not in closed]
                for aid in wanted:
                    pos = matrix._position.get(aid)
                    if pos is None:
                        continue
                    wide = matrix._wide.get(pos) if matrix._wide else None
                    vec = (np.asarray(wide, dtype=np.float64) if wide is not None
                           else matrix._matrix[pos].astype(np.float64))
                    vector_of[aid] = vec
    elif isinstance(store, InMemoryTripleStore):
        from .store import TripleQuery

        seen: Set[str] = set()
        for scope, owner in pairs:
            for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
                if a.assertion_id in seen:
                    continue
                seen.add(a.assertion_id)
                attrs = a.attributes if isinstance(a.attributes, dict) else {}
                if a.predicate == "dcterms:abstract":
                    digests.append((a.assertion_id, a.subject, a.scope, a.owner_id or "", str(a.object or ""),
                                    str(a.observed_at or ""), attrs))
                elif a.predicate in RELATION_WEIGHTS:
                    edge_rows.append((a.assertion_id, a.subject, a.predicate, str(a.object or "")))
        with store._lock:
            for row in store._rows:
                v = row.get(store._vector_column)
                if isinstance(v, list) and v:
                    vector_of[str(row.get("assertion_id"))] = np.asarray(v, dtype=np.float64)
    else:
        raise TypeError(f"communities read a SQLiteTripleStore or an InMemoryTripleStore (got {type(store).__name__})")

    owner_n = str(owner_id or "").strip()
    previous: Dict[str, PreviousCommunity] = {}
    for aid, subject, scope, owner, obj, observed, attrs in digests:
        kind = attrs.get("record_kind")
        if not isinstance(kind, str) or not kind or attrs.get("record_edge"):
            continue
        if aid in closed or subject in closed:
            continue
        if kind == COMMUNITY_KIND:
            if owner == owner_n:
                prev = _previous_of(aid, subject, scope, attrs, obj, graph.space)
                if prev is not None:
                    held = previous.get(prev.key)
                    seq = int((prev.attrs.get("basis") or {}).get("version_seq") or 0)
                    if held is None or seq > int((held.attrs.get("basis") or {}).get("version_seq") or 0):
                        previous[prev.key] = prev
            continue
        if attrs.get("bookkeeping") or subject in graph.nodes:
            continue
        graph.nodes[subject] = _Node(id=subject, assertion_id=aid, kind=kind.strip().lower(),
                                     title=record_title(attrs), digest=obj, scope=scope, owner_id=owner,
                                     observed_at=observed)
    graph.previous = [previous[k] for k in sorted(previous)]
    # The closed records: every digest row of the subject closed (a subject with one open digest row is not closed).
    shut: Set[str] = set()
    alive: Set[str] = set()
    for aid, subject, _scope, _owner, _obj, _observed, attrs in digests:
        if isinstance(attrs.get("record_kind"), str) and attrs.get("record_kind") and not attrs.get("record_edge"):
            (shut if (aid in closed or subject in closed) else alive).add(subject)
    shut -= alive
    triples: Set[Tuple[str, str, str]] = set()
    to_closed: Dict[str, int] = {}
    to_other: Set[str] = set()
    for aid, s, p, o in edge_rows:
        if aid in closed or s == o:
            continue
        for end, other in ((s, o), (o, s)):
            if end in graph.nodes:
                if other in shut:
                    to_closed[end] = to_closed.get(end, 0) + 1
                else:
                    to_other.add(end)
        if s not in graph.nodes or o not in graph.nodes:
            continue
        triples.add((s, p, o))
    graph.engraved = sorted(triples)
    graph.closed_only = {rid for rid in to_closed if rid not in to_other}
    ids, rows = [], []
    for rid in sorted(graph.nodes):
        vec = vector_of.get(graph.nodes[rid].assertion_id)
        if vec is None or vec.ndim != 1 or not np.isfinite(vec).all():
            continue
        norm = float(np.linalg.norm(vec))
        if norm <= 0.0 or (rows and vec.shape[0] != rows[0].shape[0]):
            continue
        ids.append(rid)
        rows.append(vec / norm)
    graph.vec_ids = ids
    graph.vectors = (np.vstack(rows).astype(np.float32) if rows else np.zeros((0, 0), dtype=np.float32))
    return graph


# --------------------------------------------------------------------------- Louvain (deterministic, warm-startable)


def _compact(labels: Sequence[int]) -> List[int]:
    """Labels renumbered 0..k-1 in order of first appearance."""
    seen: Dict[int, int] = {}
    return [seen.setdefault(c, len(seen)) for c in labels]


def louvain(adj: Sequence[Mapping[int, float]], *, init: Optional[Sequence[int]] = None,
            resolution: float = RESOLUTION, max_levels: int = 32) -> List[int]:
    """Deterministic Louvain (the runtime's port, moved into memory: sorted iteration, no RNG, self-loops kept on
    aggregation) with a WARM START: `init` (one label per node) is the first level's starting partition, so the
    previous version's communities are where the local moves begin. Returns one compact label per node."""
    n = len(adj)
    if n == 0:
        return []
    level: List[Dict[int, float]] = [dict(row) for row in adj]
    member = list(range(n))
    start = _compact(list(init)) if init is not None else None
    if start is not None and len(start) != n:
        raise ValueError(f"louvain: init names {len(start)} labels for {n} nodes")
    for depth in range(max_levels):
        m = len(level)
        degree = [sum(row.values()) for row in level]
        m2 = sum(degree)
        if m2 <= 0.0:
            break
        community = list(start) if (depth == 0 and start is not None) else list(range(m))
        comm_degree: Dict[int, float] = {}
        for i, c in enumerate(community):
            comm_degree[c] = comm_degree.get(c, 0.0) + degree[i]
        moved = True
        while moved:
            moved = False
            for i in range(m):
                c_old = community[i]
                to: Dict[int, float] = {}
                for j, w in level[i].items():
                    if j != i:
                        cj = community[j]
                        to[cj] = to.get(cj, 0.0) + w
                comm_degree[c_old] -= degree[i]
                base = to.get(c_old, 0.0) - resolution * comm_degree[c_old] * degree[i] / m2
                best_c, best = c_old, 0.0
                for c in sorted(to):
                    if c == c_old:
                        continue
                    delta = to[c] - resolution * comm_degree.get(c, 0.0) * degree[i] / m2 - base
                    if delta > best + 1e-12:
                        best, best_c = delta, c
                comm_degree[best_c] = comm_degree.get(best_c, 0.0) + degree[i]
                if best_c != c_old:
                    community[i] = best_c
                    moved = True
        relabel = _compact(community)
        k = max(relabel) + 1
        member = [relabel[member[v]] for v in range(n)]
        if k == m:
            break
        aggregated: List[Dict[int, float]] = [{} for _ in range(k)]
        for i in range(m):
            row = aggregated[relabel[i]]
            for j, w in level[i].items():
                cj = relabel[j]
                row[cj] = row.get(cj, 0.0) + w
        level = aggregated
        if k == 1:
            break
    return _compact(member)


def _modularity(adj: Sequence[Mapping[int, float]], labels: Sequence[int], resolution: float = RESOLUTION) -> float:
    m2 = sum(sum(row.values()) for row in adj)
    if m2 <= 0:
        return 0.0
    inside: Dict[int, float] = {}
    degree: Dict[int, float] = {}
    for i, row in enumerate(adj):
        c = labels[i]
        degree[c] = degree.get(c, 0.0) + sum(row.values())
        inside[c] = inside.get(c, 0.0) + sum(w for j, w in row.items() if labels[j] == c)
    return sum(inside.get(c, 0.0) / m2 - resolution * (degree[c] / m2) ** 2 for c in degree)


# --------------------------------------------------------------------------- detection, refinement, attach


@dataclass
class Detection:
    """A partition of the home: `groups` (each {member id: via}, largest first), what could not be placed, and the
    numbers the receipt reports. Pure data: `detect_communities` returns it, the pass writes it."""

    groups: List[Dict[str, str]]
    split_from: Dict[int, Set[str]]  # group index -> the member set of the oversized group it was split from
    unvectored: List[str]
    unplaced: List[str]
    detection_nodes: int
    edges: int
    knn_edges: int
    modularity: float
    weights: Dict[str, Dict[str, float]]  # the full weighted graph (engraved incl. written_amid + kNN), symmetric
    knn_ms: float = 0.0
    louvain_ms: float = 0.0
    refine_ms: float = 0.0
    rounds: int = 0


def _engraved_weights(graph: CommunityGraph) -> List[Tuple[str, str, str, float]]:
    fanout: Dict[Tuple[str, str], int] = {}
    for s, p, _o in graph.engraved:
        fanout[(s, p)] = fanout.get((s, p), 0) + 1
    return [(s, o, p, RELATION_WEIGHTS[p] / math.sqrt(fanout[(s, p)])) for s, p, o in graph.engraved]


def _knn_pairs(vectors: Any, k: int, min_cos: float) -> Dict[Tuple[int, int], float]:
    """Cosine kNN over unit rows: {(i, j) i<j: cosine}, an edge when either end has the other in its k best at
    cosine >= min_cos. Cosines rounded to 1e-6 (determinism across BLAS orders). Blocked so the transient memory is
    bounded whatever n is: min(KNN_BLOCK_ROWS, KNN_BLOCK_CELLS // n) rows at a time, the float32 product cast ONCE to
    float64, then rounded, masked and negated IN PLACE (argpartition reads the negated copy: no `-block` copy)."""
    np = _np()
    n = int(vectors.shape[0]) if vectors is not None and vectors.size else 0
    k = min(int(k), n - 1)
    out: Dict[Tuple[int, int], float] = {}
    if k <= 0:
        return out
    step = max(1, min(KNN_BLOCK_ROWS, KNN_BLOCK_CELLS // n))
    for start in range(0, n, step):
        block = (vectors[start:start + step] @ vectors.T).astype(np.float64)
        np.round(block, 6, out=block)
        rows = np.arange(block.shape[0])
        block[rows, rows + start] = -np.inf
        np.negative(block, out=block)  # the k smallest = the k best cosines
        top = np.argpartition(block, k - 1, axis=1)[:, :k]
        for local in range(block.shape[0]):
            i = start + local
            for j in sorted(int(x) for x in top[local]):
                cos = -float(block[local, j])
                if cos >= min_cos:
                    key = (i, j) if i < j else (j, i)
                    if cos > out.get(key, -1.0):
                        out[key] = cos
    return out


def _components(members: Sequence[int], adj: Sequence[Mapping[int, float]]) -> List[List[int]]:
    inside = set(members)
    seen: Set[int] = set()
    out: List[List[int]] = []
    for s in sorted(members):
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            v = stack.pop()
            comp.append(v)
            for u in adj[v]:
                if u in inside and u not in seen:
                    seen.add(u)
                    stack.append(u)
        out.append(sorted(comp))
    return out


def _cross(group: Sequence[int], group_of: Mapping[int, int], adj: Sequence[Mapping[int, float]],
           own: int) -> Dict[int, float]:
    w: Dict[int, float] = {}
    for v in group:
        for u, x in adj[v].items():
            g = group_of.get(u)
            if g is not None and g != own:
                w[g] = w.get(g, 0.0) + x
    return w


def _refine(labels: Sequence[int], adj: Sequence[Mapping[int, float]]) -> Tuple[List[List[int]], List[int],
                                                                                  Dict[int, Set[int]]]:
    """Louvain's partition made safe: (1) a community over SPLIT_SHARE of the nodes (and at least SPLIT_MIN_SIZE)
    is re-run alone at SPLIT_RESOLUTION and split; (2) every community splits into its connected components and a
    component under MIN_COMPONENT_SIZE rejoins the community it is best connected to; (3) a community under
    MIN_COMMUNITY_SIZE moves WHOLE to the community it shares the most cross weight with (nothing is big: the
    partition is kept). Returns (groups of node indices, orphans: members of tiny communities with no neighbour,
    split_from: group index -> the oversized group's members)."""
    n = len(labels)
    by: Dict[int, List[int]] = {}
    for v, c in enumerate(labels):
        by.setdefault(c, []).append(v)
    groups = [sorted(g) for g in by.values()]
    groups.sort(key=lambda g: g[0])
    split_mark: Dict[int, int] = {}  # group position -> split id
    split_sets: Dict[int, Set[int]] = {}
    out: List[List[int]] = []
    for g in groups:
        if n and len(g) > SPLIT_SHARE * n and len(g) >= SPLIT_MIN_SIZE:
            local = {v: i for i, v in enumerate(g)}
            sub = [{local[u]: w for u, w in adj[v].items() if u in local} for v in g]
            parts_l = louvain(sub, resolution=SPLIT_RESOLUTION)
            parts: Dict[int, List[int]] = {}
            for i, c in enumerate(parts_l):
                parts.setdefault(c, []).append(g[i])
            if sum(1 for p in parts.values() if len(p) >= MIN_COMMUNITY_SIZE) >= 2:
                sid = len(split_sets)
                split_sets[sid] = set(g)
                for p in sorted(parts.values(), key=lambda p: p[0]):
                    split_mark[len(out)] = sid
                    out.append(sorted(p))
                continue
        out.append(g)
    # (2) connectivity
    comps: List[List[int]] = []
    comp_split: Dict[int, int] = {}
    for gi, g in enumerate(out):
        for comp in _components(g, adj):
            if gi in split_mark:
                comp_split[len(comps)] = split_mark[gi]
            comps.append(comp)
    group_of = {v: ci for ci, comp in enumerate(comps) for v in comp}
    alive = {ci: list(comp) for ci, comp in enumerate(comps)}
    for ci in sorted(alive, key=lambda c: (len(alive[c]), alive[c][0])):
        comp = alive.get(ci)
        if comp is None or len(comp) >= MIN_COMPONENT_SIZE:
            continue
        cross = _cross(comp, group_of, adj, ci)
        if not cross:
            continue
        target = sorted(cross, key=lambda g: (-cross[g], alive[g][0]))[0]
        alive[target] = sorted(alive[target] + comp)
        for v in comp:
            group_of[v] = target
        del alive[ci]
    # (3) tiny communities merge whole (nothing is big -> keep the partition)
    orphans: List[int] = []
    if any(len(g) >= MIN_COMMUNITY_SIZE for g in alive.values()):
        while True:
            tiny = sorted((c for c in alive if len(alive[c]) < MIN_COMMUNITY_SIZE),
                          key=lambda c: (len(alive[c]), alive[c][0]))
            merged = False
            for ci in tiny:
                cross = _cross(alive[ci], group_of, adj, ci)
                if not cross:
                    continue
                target = sorted(cross, key=lambda g: (-cross[g], alive[g][0]))[0]
                alive[target] = sorted(alive[target] + alive[ci])
                for v in alive[ci]:
                    group_of[v] = target
                if ci in comp_split and target not in comp_split:
                    comp_split[target] = comp_split[ci]
                del alive[ci]
                merged = True
                break
            if not merged:
                break
        for ci in [c for c in alive if len(alive[c]) < MIN_COMMUNITY_SIZE]:
            orphans.extend(alive.pop(ci))
    final = sorted(alive.items(), key=lambda kv: (-len(kv[1]), kv[1][0]))
    groups_out = [g for _, g in final]
    split_from = {gi: {v for v in split_sets[comp_split[ci]]} for gi, (ci, _) in enumerate(final) if ci in comp_split}
    return groups_out, sorted(orphans), split_from


def _unit_mean(np: Any, rows: Any) -> Any:
    if rows is None or len(rows) == 0:
        return None
    mean = np.asarray(rows, dtype=np.float64).mean(axis=0)
    norm = float(np.linalg.norm(mean))
    return mean / norm if norm > 0 else None


def _labels_of(n: int, groups: Sequence[Sequence[int]], orphans: Sequence[int]) -> List[int]:
    """One label per node: the group index, each orphan a label of its own after the groups."""
    out = [0] * n
    for gi, g in enumerate(groups):
        for v in g:
            out[v] = gi
    for k, v in enumerate(orphans):
        out[v] = len(groups) + k
    return out


def _stabilise(adj: Sequence[Mapping[int, float]], init: Optional[Sequence[int]]
               ) -> Tuple[List[List[int]], List[int], Dict[int, Set[int]], int]:
    """Louvain + refine re-seeded from its own refined output, at most MAX_DETECTION_ROUNDS rounds (PURE,
    deterministic: the same adjacency and seed give the same rounds and the same partition). Stops at the first of:
    a fixed point (the round gives the previous round's partition: kept); a repeated EARLIER partition (an
    oscillation: the cycle's smallest partition in canonical order is kept, so the result does not depend on the
    round that entered the cycle and a rerun seeded from it lands on it again); the cap (the last round's partition).
    Returns (groups, orphans, split_from, rounds)."""
    n = len(adj)
    history: List[Tuple[Tuple[int, ...], ...]] = []
    results: List[Tuple[List[List[int]], List[int], Dict[int, Set[int]]]] = []
    groups: List[List[int]] = []
    orphans: List[int] = []
    split: Dict[int, Set[int]] = {}
    rounds = 0
    while rounds < MAX_DETECTION_ROUNDS:
        rounds += 1
        groups, orphans, split = _refine(louvain(adj, init=init), adj)
        state = tuple(sorted(tuple(g) for g in groups)) + (tuple(orphans),)
        if state in history:
            at = history.index(state)
            if at < len(history) - 1:  # an oscillation: the cycle is history[at:]
                pick = min(range(at, len(history)), key=lambda i: history[i])
                groups, orphans, split = results[pick]
            break
        history.append(state)
        results.append((groups, orphans, split))
        init = _labels_of(n, groups, orphans)
    return groups, orphans, split, rounds


def detect_communities(graph: CommunityGraph, *, seed_previous: bool = True,
                       detect_kinds: Optional[Iterable[str]] = None) -> Detection:
    """The partition (PURE): detection over every VECTORED record (`detect_kinds` narrows it: the other kinds are
    attached by their nearest centroid), edges = engraved relations (kind weight / sqrt(fan-out), `written_amid` out)
    + cosine kNN (k = KNN_K, cosine >= KNN_MIN_COSINE, weight KNN_WEIGHT * cosine); Louvain warm-started from the
    previous version (`seed_previous`: a member starts in its previous community, a new vectored record at its
    nearest previous centroid); refinement; then the vector-less records attached by the summed weight of their
    engraved neighbours (rounds until nothing more places). Deterministic: the same graph gives the same groups."""
    np = _np()
    kinds = None if detect_kinds is None else {str(k).strip().lower() for k in detect_kinds}
    vindex = graph.vindex
    t0 = time.perf_counter()
    detect_ids = [rid for rid in graph.vec_ids if kinds is None or graph.nodes[rid].kind in kinds]
    di = {rid: i for i, rid in enumerate(detect_ids)}
    adj: List[Dict[int, float]] = [{} for _ in detect_ids]
    full: Dict[str, Dict[str, float]] = {rid: {} for rid in graph.nodes}

    def link(a: str, b: str, w: float) -> None:
        full[a][b] = full[a].get(b, 0.0) + w
        full[b][a] = full[b].get(a, 0.0) + w

    for a, b, rel, w in _engraved_weights(graph):
        link(a, b, w)
        if rel not in DETECTION_EXCLUDED_RELATIONS and a in di and b in di:
            i, j = di[a], di[b]
            adj[i][j] = adj[i].get(j, 0.0) + w
            adj[j][i] = adj[j].get(i, 0.0) + w
    knn_n = 0
    if detect_ids:
        rows = graph.vectors[[vindex[r] for r in detect_ids]]
        for (i, j), cos in sorted(_knn_pairs(rows, KNN_K, KNN_MIN_COSINE).items()):
            w = KNN_WEIGHT * cos
            adj[i][j] = adj[i].get(j, 0.0) + w
            adj[j][i] = adj[j].get(i, 0.0) + w
            link(detect_ids[i], detect_ids[j], w)
            knn_n += 1
    t1 = time.perf_counter()
    init: Optional[List[int]] = None
    if seed_previous and graph.previous and detect_ids:
        member_key = {mid: p.key for p in graph.previous for mid in p.members}
        keys = sorted({p.key for p in graph.previous})
        label = {k: i for i, k in enumerate(keys)}
        cents = [(p.key, p.centroid) for p in graph.previous if p.centroid is not None]
        cmat = np.vstack([c for _, c in cents]) if cents else None
        init = []
        fresh = len(keys)
        for rid in detect_ids:
            key = member_key.get(rid)
            if key is None and cmat is not None and cmat.shape[1] == graph.vectors.shape[1]:
                sims = cmat @ graph.vectors[vindex[rid]].astype(np.float64)
                key = cents[int(np.argmax(sims))][0]
            if key is None:
                init.append(fresh)
                fresh += 1
            else:
                init.append(label[key])
    groups_i: List[List[int]] = []
    orphans: List[int] = []
    split_i: Dict[int, Set[int]] = {}
    rounds = 0
    if detect_ids:
        groups_i, orphans, split_i, rounds = _stabilise(adj, init)
    final = _labels_of(len(detect_ids), groups_i, orphans)
    modularity = round(_modularity(adj, final), 6) if detect_ids else 0.0
    t2 = time.perf_counter()
    groups: List[Dict[str, str]] = [{detect_ids[v]: "detected" for v in g} for g in groups_i]
    # Attach by nearest centroid: the vectored records detection left out (other kinds, tiny orphan groups).
    centroids = [_unit_mean(np, graph.vectors[[vindex[m] for m in g]]) for g in groups]
    cmat = np.vstack(centroids) if groups else None
    to_attach = sorted([detect_ids[v] for v in orphans]
                       + [rid for rid in graph.vec_ids if rid not in di])
    unplaced: List[str] = []
    for rid in to_attach:
        if cmat is None:
            unplaced.append(rid)
            continue
        sims = cmat @ graph.vectors[vindex[rid]].astype(np.float64)
        groups[int(np.argmax(sims))][rid] = "attached"
    # Attach the vector-less records by their engraved neighbours (summed weight per community), in rounds.
    unvectored = sorted(rid for rid in graph.nodes if rid not in vindex)
    where = {m: gi for gi, g in enumerate(groups) for m in g}
    waiting = list(unvectored)
    while waiting:
        placed_now: List[Tuple[str, int]] = []
        for rid in waiting:
            score: Dict[int, float] = {}
            for nb, w in full[rid].items():
                gi = where.get(nb)
                if gi is not None:
                    score[gi] = score.get(gi, 0.0) + w
            if score:
                placed_now.append((rid, sorted(score, key=lambda g: (-score[g], g))[0]))
        if not placed_now:
            break
        for rid, gi in placed_now:
            groups[gi][rid] = "attached"
            where[rid] = gi
        done = {rid for rid, _ in placed_now}
        waiting = [rid for rid in waiting if rid not in done]
    unplaced.extend(waiting)
    split_from = {gi: {detect_ids[v] for v in members} for gi, members in split_i.items()}
    t3 = time.perf_counter()
    return Detection(groups=groups, split_from=split_from, unvectored=unvectored, unplaced=sorted(unplaced),
                     detection_nodes=len(detect_ids), edges=sum(len(r) for r in adj) // 2, knn_edges=knn_n,
                     modularity=modularity, weights=full, knn_ms=(t1 - t0) * 1000.0,
                     louvain_ms=(t2 - t1) * 1000.0, refine_ms=(t3 - t2) * 1000.0, rounds=rounds)


# --------------------------------------------------------------------------- keys: the Jaccard match


def mint_key(member_ids: Iterable[str], taken: Set[str]) -> str:
    """A fresh stable key from the first member set (sorted ids), salted only on a collision."""
    base = "\n".join(sorted(member_ids))
    salt = 0
    while True:
        key = KEY_PREFIX + _hex(base if salt == 0 else f"{base}|{salt}", 12)
        if key not in taken:
            return key
        salt += 1


def match_keys(groups: Sequence[Mapping[str, str]],
               previous: Sequence[PreviousCommunity]) -> List[Tuple[str, Optional[PreviousCommunity], float]]:
    """(key, the previous version it continues or None, Jaccard) per group: best Jaccard pairs first (ties: previous
    key, then the group's smallest member id), each previous community used once, floor KEY_MATCH_FLOOR; an
    unmatched group gets a fresh key."""
    owner_of: Dict[str, List[int]] = {}
    for pi, p in enumerate(previous):
        for m in p.members:
            owner_of.setdefault(m, []).append(pi)
    pairs: List[Tuple[float, str, str, int, int]] = []
    for gi, g in enumerate(groups):
        overlap: Dict[int, int] = {}
        for m in g:
            for pi in owner_of.get(m, ()):
                overlap[pi] = overlap.get(pi, 0) + 1
        for pi, inter in overlap.items():
            j = inter / float(len(g) + len(previous[pi].members) - inter)
            if j >= KEY_MATCH_FLOOR:
                pairs.append((-j, previous[pi].key, min(g), gi, pi))
    pairs.sort()
    used_g: Dict[int, Tuple[int, float]] = {}
    used_p: Set[int] = set()
    for negj, _key, _first, gi, pi in pairs:
        if gi in used_g or pi in used_p:
            continue
        used_g[gi] = (pi, -negj)
        used_p.add(pi)
    taken = {p.key for p in previous}
    out: List[Tuple[str, Optional[PreviousCommunity], float]] = []
    for gi, g in enumerate(groups):
        if gi in used_g:
            pi, j = used_g[gi]
            out.append((previous[pi].key, previous[pi], round(j, 6)))
        else:
            key = mint_key(g, taken)
            taken.add(key)
            out.append((key, None, 0.0))
    return out


# --------------------------------------------------------------------------- layout as data


def _sign_fixed(np: Any, vt: Any) -> Any:
    out = np.array(vt, dtype=np.float64)
    for r in range(out.shape[0]):
        if out[r, int(np.argmax(np.abs(out[r])))] < 0:
            out[r] = -out[r]
    return out


def _pca2(np: Any, rows: Any) -> Any:
    centered = np.asarray(rows, dtype=np.float64) - np.asarray(rows, dtype=np.float64).mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    axes = _sign_fixed(np, vt[:2])
    proj = centered @ axes.T
    if proj.shape[1] < 2:
        proj = np.hstack([proj, np.zeros((proj.shape[0], 2 - proj.shape[1]))])
    return proj


def _relax(np: Any, xy: Any, radius: Any, pinned: Any) -> Any:
    """Repel-only separation (no attraction, the ragnarok FA2 lesson): overlapping circles are pushed apart along the
    line between their centres (half each, all of it onto the free one beside a pinned circle), fixed iteration bound,
    deterministic (coincident centres split along an angle derived from their indices)."""
    pos = np.array(xy, dtype=np.float64)
    n = pos.shape[0]
    if n < 2:
        return pos
    r = np.asarray(radius, dtype=np.float64)
    free = ~np.asarray(pinned, dtype=bool)
    need = r[:, None] + r[None, :] + CIRCLE_GAP
    np.fill_diagonal(need, 0.0)
    idx = np.arange(n)
    angle = (idx[:, None] * 7919 + idx[None, :] * 104729) % 360 * (math.pi / 180.0)
    for _ in range(RELAX_MAX_ITERATIONS):
        diff = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((diff ** 2).sum(axis=2))
        over = need - dist
        np.fill_diagonal(over, 0.0)
        over[over <= 1e-9] = 0.0
        if not over.any():
            break
        with np.errstate(invalid="ignore", divide="ignore"):
            unit = np.where(dist[:, :, None] > 1e-12, diff / dist[:, :, None], 0.0)
        tie = (dist <= 1e-12) & (over > 0)
        if tie.any():
            sign = np.where(idx[:, None] < idx[None, :], 1.0, -1.0)
            unit[..., 0] = np.where(tie, np.cos(angle) * sign, unit[..., 0])
            unit[..., 1] = np.where(tie, np.sin(angle) * sign, unit[..., 1])
        share = np.where(free[:, None] & free[None, :], 0.5, np.where(free[:, None], 1.0, 0.0))
        push = (share * over)[:, :, None] * unit
        pos = pos + push.sum(axis=1) * 1.01
    return pos


def _layout(np: Any, items: List[Dict[str, Any]]) -> None:
    """xy and radius per community (in place). Unchanged communities are pinned where they were; a continued one
    starts at its previous place; a new one at its centroid's 2-D PCA position, Procrustes-aligned to the previous
    places (similarity fit) so the map does not spin between nights; below 3 centroids a fixed ring. Then the
    repel-only relaxation."""
    for it in items:
        if it.get("pinned") is None:
            it["radius"] = round(RADIUS_UNIT * math.sqrt(max(1, int(it["size"]))), 3)
    with_c = [it for it in items if it.get("centroid") is not None]
    target: Dict[str, Any] = {}
    if len(with_c) >= 3:
        proj = _pca2(np, np.vstack([it["centroid"] for it in with_c]))
        spread = 1.5 * math.sqrt(sum(float(it["radius"]) ** 2 for it in items))
        top = float(np.max(np.linalg.norm(proj, axis=1))) if len(proj) else 0.0
        if top > 0:
            proj = proj * (spread / top)
        anchors = [(i, np.asarray(it["prev_xy"], dtype=np.float64)) for i, it in enumerate(with_c)
                   if it.get("prev_xy") is not None]
        if len(anchors) >= 2:
            a = proj[[i for i, _ in anchors]]
            b = np.vstack([q for _, q in anchors])
            mu_a, mu_b = a.mean(axis=0), b.mean(axis=0)
            a0, b0 = a - mu_a, b - mu_b
            u, s, vt = np.linalg.svd(a0.T @ b0)
            rot = u @ vt
            denom = float((a0 ** 2).sum())
            scale = float(s.sum()) / denom if denom > 0 else 1.0
            proj = scale * (proj - mu_a) @ rot + mu_b
        elif len(anchors) == 1:
            i, q = anchors[0]
            proj = proj + (q - proj[i])
        for i, it in enumerate(with_c):
            target[it["key"]] = proj[i]
    else:
        free = [it for it in items if it.get("pinned") is None and it.get("prev_xy") is None]
        ring = sum(float(it["radius"]) for it in items) / math.pi if len(items) > 1 else 0.0
        for i, it in enumerate(free):
            ang = 2.0 * math.pi * i / max(1, len(free))
            target[it["key"]] = np.array([ring * math.cos(ang), ring * math.sin(ang)])
    xy, radius, pinned = [], [], []
    for it in items:
        if it.get("pinned") is not None:
            xy.append(np.asarray(it["pinned"]["xy"], dtype=np.float64))
            pinned.append(True)
        elif it.get("prev_xy") is not None:
            xy.append(np.asarray(it["prev_xy"], dtype=np.float64))
            pinned.append(False)
        else:
            xy.append(np.asarray(target.get(it["key"], np.zeros(2)), dtype=np.float64))
            pinned.append(False)
        radius.append(float(it["radius"]))
    out = _relax(np, np.vstack(xy) if xy else np.zeros((0, 2)), radius, pinned)
    for it, p in zip(items, out):
        it["xy"] = [round(float(p[0]), 3), round(float(p[1]), 3)]


def _seats(np: Any, members: Sequence[Dict[str, Any]], graph: CommunityGraph, radius: float) -> Dict[str, List[float]]:
    """Member seats relative to the circle's centre: the vectored members on the community's own 2-D PCA of their
    vectors scaled into SEAT_FILL of the circle; the vector-less ones on sunflower seats in join order (since_seq,
    id), seat k at SEAT_FILL * RADIUS_UNIT * sqrt(k + 0.5): independent of the count, so a newcomer appends at the rim
    and nobody moves (always inside: k < size)."""
    vindex = graph.vindex
    order = sorted(members, key=lambda m: (int(m["since_seq"]), m["id"]))
    vec = [m["id"] for m in order if m["id"] in vindex]
    seats: Dict[str, List[float]] = {}
    if len(vec) >= 2:
        proj = _pca2(np, graph.vectors[[vindex[r] for r in vec]])
        top = float(np.max(np.linalg.norm(proj, axis=1)))
        scale = (SEAT_FILL * radius / top) if top > 0 else 0.0
        for rid, p in zip(vec, proj):
            seats[rid] = [round(float(p[0] * scale), 3), round(float(p[1] * scale), 3)]
    elif vec:
        seats[vec[0]] = [0.0, 0.0]
    k = 0
    for m in order:
        if m["id"] in seats:
            continue
        rr = SEAT_FILL * RADIUS_UNIT * math.sqrt(k + 0.5)
        seats[m["id"]] = [round(rr * math.cos(k * GOLDEN_ANGLE), 3), round(rr * math.sin(k * GOLDEN_ANGLE), 3)]
        k += 1
    return seats


# --------------------------------------------------------------------------- the briefing (the provisional body)


def _sample_key(key: str, member_id: str) -> str:
    return hashlib.sha1(f"{key}:{member_id}".encode("utf-8")).hexdigest()


def _member_line(node: _Node) -> str:
    title = (node.title or "").strip()
    text = " ".join(str(node.digest or "").split())
    return f"- ({node.kind}) {title}: {text}" if title else f"- ({node.kind}) {text}"


def briefing_sample(key: str, member_ids: Sequence[str], graph: CommunityGraph,
                    weights: Mapping[str, Mapping[str, float]], *,
                    token_budget: int = BRIEFING_TOKEN_BUDGET) -> List[str]:
    """The stable kind-mixed sample the author reads: BRIEFING_HUBS hubs by internal weight, then a round-robin over
    the member kinds (most numerous first), each kind ordered by sha1('<key>:<member id>') - a bottom-k sample keyed
    on the STABLE key, so it drifts only as the membership does - until the token budget (whole lines only: a line
    that does not fit is left out, the first one too, so the sample stays within the budget; only when no single
    line fits is the shortest one, in that order, the whole sample - the author always reads at least one member)."""
    from .canonical_text import token_estimate

    inside = set(member_ids)
    internal = {m: sum(w for nb, w in weights.get(m, {}).items() if nb in inside) for m in member_ids}
    hubs = sorted(member_ids, key=lambda m: (-round(internal[m], 9), m))[:BRIEFING_HUBS]
    by_kind: Dict[str, List[str]] = {}
    for m in member_ids:
        if m not in hubs:
            by_kind.setdefault(graph.nodes[m].kind, []).append(m)
    for ids in by_kind.values():
        ids.sort(key=lambda m: _sample_key(key, m))
    kinds = sorted(by_kind, key=lambda k: (-len(by_kind[k]), k))
    order = list(hubs)
    depth = 0
    while True:
        added = False
        for k in kinds:
            if depth < len(by_kind[k]):
                order.append(by_kind[k][depth])
                added = True
        if not added:
            break
        depth += 1
    out: List[str] = []
    used = 0
    costs = {m: token_estimate(_member_line(graph.nodes[m])) for m in order}
    for m in order:
        if used + costs[m] > token_budget:
            continue
        out.append(m)
        used += costs[m]
    if not out and order:
        out = [min(order, key=lambda m: costs[m])]
    return out


def _briefing(size: int, kinds: Mapping[str, int], sample: Sequence[str], graph: CommunityGraph, *,
              previous_title: Optional[str], siblings: Sequence[str], feedback: Optional[str] = None) -> str:
    kinds_line = ", ".join(f"{n} {k}" for k, n in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0])))
    lines = [f"A topic of this memory: {size} memories that belong together ({kinds_line}).",
             "The title names the subject they share; the summary says in one to three sentences what these "
             "memories are about."]
    if previous_title:
        lines.append(f"The previous title of this topic was \"{previous_title}\": keep it if it still fits.")
    if siblings:
        lines.append("Other topics are already named, and this title must differ from each: "
                     + "; ".join(f"\"{s}\"" for s in siblings) + ".")
    lines.append("If these memories share no common subject, say so plainly.")
    if feedback:
        lines.append(feedback)
    lines.append("")
    lines.append(f"The memories (a sample of {len(sample)} of {size}):")
    lines.extend(_member_line(graph.nodes[m]) for m in sample)
    return "\n".join(lines)


def _norm_title(title: Optional[str]) -> str:
    return " ".join(str(title or "").casefold().split())


class _Capture:
    """The host's author, with the structured verdict it may return captured (`verdict`: None or
    "no_common_subject"; anything else is refused as invalid)."""

    def __init__(self, author: Any) -> None:
        self.author = author
        self.verdict: Optional[str] = None
        self.bad_verdict: Optional[str] = None

    def __call__(self, kind: str, body: str, context: Mapping[str, Any]) -> Any:
        self.verdict = self.bad_verdict = None
        result = self.author(kind, body, context)
        if isinstance(result, Mapping) and result.get("verdict") is not None:
            if result.get("verdict") == NO_COMMON_SUBJECT:
                self.verdict = NO_COMMON_SUBJECT
            else:
                self.bad_verdict = repr(result.get("verdict"))
        return result


# --------------------------------------------------------------------------- the one transaction


def _undo_in_memory_journal(journal: Any, binding_ids: Sequence[str], closure_ids: Sequence[str]) -> None:
    """Undo this attempt's bindings and closures on an InMemoryJournal (it has no transaction): the attempt held the
    journal's lock from its first append to here, so they are the newest records and the seq axis rewinds with them."""
    gone_b, gone_c = set(binding_ids), set(closure_ids)
    with journal._lock:
        seqs = [int(b.seq) for b in journal._bindings if b.binding_id in gone_b]
        seqs += [int(c.seq) for c in journal._closures if c.closure_id in gone_c]
        journal._bindings = [b for b in journal._bindings if b.binding_id not in gone_b]
        journal._closures = [c for c in journal._closures if c.closure_id not in gone_c]
        for bid in gone_b:
            journal._bindings_by_id.pop(bid, None)
        for cid in gone_c:
            journal._closures_by_id.pop(cid, None)
        if seqs and max(seqs) == journal._seq and len(seqs) == journal._seq - min(seqs) + 1:
            journal._seq = min(seqs) - 1


def _write_version(system: Any, plans: Sequence[Any], planned: Sequence[Mapping[str, Any]],
                   closures: Sequence[Any], superseded: Sequence[Tuple[str, str]]) -> None:
    """ONE transaction for a whole version: the new records (rows + bindings), the closures of the versions they
    replace and of the dissolved ones, the authoring tasks the new records owe and the supersession of the replaced
    versions' live tasks; the commit guard is called once, immediately before the COMMIT (the task queue's
    transaction on the store's own connection). An in-memory pair rolls this attempt back by hand."""
    from .commit_guard import deferred_to_caller
    from .in_memory_store import InMemoryTripleStore
    from .journal_memory import InMemoryJournal
    from .journal_sqlite import SQLiteJournal
    from .sqlite_store import SQLiteTripleStore
    from .store import TripleQuery
    from .understanding import _same_file

    queue = system.tasks
    store, journal = system.store, system.journal
    assertions = [a for plan in plans for a in plan.assertions]
    ids = tuple(a.assertion_id for a in assertions if a.assertion_id)
    existing = {a.assertion_id for a in store.query(TripleQuery(assertion_ids=ids, limit=0))} if ids else set()
    missing = [a for a in assertions if a.assertion_id not in existing]
    bindings = [b for plan in plans for b in plan.bindings]

    def tasks_on(cur: Any) -> None:
        for p in planned:
            args = dict(p)
            queue.enqueue(args.pop("kind"), args.pop("target_id"), _cur=cur, **args)
        for prior, reason in superseded:
            queue.supersede_target(prior, kinds=("title.author", "digest.author"), reason=reason, _cur=cur)

    if isinstance(store, SQLiteTripleStore):
        if not (queue.shares_store_transaction and isinstance(journal, SQLiteJournal)
                and _same_file(store._path, journal._path)):
            raise TypeError("communities_pass writes a version in ONE transaction: the home's journal must be a "
                            "SQLiteJournal in the store's own file (the entity home)")
        rows = store._prepare_add(missing)[1] if missing else []

        def write(cur: Any) -> None:
            if rows:
                store._insert_rows_on(cur, rows)
            for b in bindings:
                journal._append_binding_on(cur, b)
            for c in closures:
                journal._append_closure_on(cur, c)
            tasks_on(cur)

        queue._txn(None, write, where="communities.communities_pass")
        if rows:
            store._after_add_commit()
        return
    if not (isinstance(store, InMemoryTripleStore) and isinstance(journal, InMemoryJournal)):
        raise TypeError("communities_pass writes on a SQLite home (store + journal in one file) or an in-memory pair "
                        f"(got {type(store).__name__} + {type(journal).__name__})")
    prepared = store._prepare_add(missing) if missing else None
    added: List[str] = []
    bound: List[str] = []
    closed: List[str] = []
    with queue._lock, journal._lock:
        def write_mem(qcur: Any) -> None:
            tasks_on(qcur)
            with deferred_to_caller(store):
                if missing:
                    added.extend(store._insert_prepared(missing, prepared)[1])
                for b in bindings:
                    stored, new = journal._append_binding_tracked(b)
                    if new:
                        bound.append(str(stored.binding_id))
                for c in closures:
                    fresh = str(c.closure_id) not in journal._closures_by_id
                    stored_c = journal.append_closure(c)
                    if fresh:
                        closed.append(str(stored_c.closure_id))

        try:
            queue._txn(None, write_mem, where="communities.communities_pass")
        except BaseException:
            if added:
                store._discard_formed(added)
            _undo_in_memory_journal(journal, bound, closed)
            raise


# --------------------------------------------------------------------------- the pass


def _receipt() -> Dict[str, Any]:
    from .formation_authoring import new_receipt

    return {"pass_name": PASS_NAME, "version_seq": None, "communities": 0, "new": 0, "kept": 0, "renamed": 0,
            "dissolved": 0, "unchanged": 0, "written": 0, "moved_in": 0, "moved_out": 0, "detected": 0,
            "attached": 0, "provisional": 0, "unvectored": [], "unvectored_count": 0, "unplaced": [],
            "unplaced_count": 0, "unplaced_closed": [], "authored": 0, "pending": 0, "failed": 0, "titles_kept": 0,
            "budget": None, "budget_spent": 0,
            "ids": {"new": [], "kept": [], "renamed": [], "dissolved": [], "pending": [], "written": []},
            "authoring": new_receipt(), "cancelled": None, "skipped": None, "nodes": 0, "detection_nodes": 0,
            "edges": 0, "knn_edges": 0, "modularity": 0.0, "algorithm": ALGORITHM,
            "params": _params(), "elapsed_ms": 0.0, "timings_ms": {}}


def _params() -> Dict[str, Any]:
    return {"resolution": RESOLUTION, "knn_k": KNN_K, "knn_min_cosine": KNN_MIN_COSINE, "knn_weight": KNN_WEIGHT,
            "relation_weights": dict(RELATION_WEIGHTS), "detection_excluded": sorted(DETECTION_EXCLUDED_RELATIONS),
            "split": {"share": SPLIT_SHARE, "min_size": SPLIT_MIN_SIZE, "resolution": SPLIT_RESOLUTION},
            "min_component": MIN_COMPONENT_SIZE, "min_community": MIN_COMMUNITY_SIZE,
            "key_match_floor": KEY_MATCH_FLOOR, "title_keep_jaccard": TITLE_KEEP_JACCARD}


def _carried(prev: PreviousCommunity, members: Set[str]) -> bool:
    """The previous version's title and summary still name this membership: both authored (no pending marker),
    the basis prompt version is today's, and Jaccard(members, basis members) >= TITLE_KEEP_JACCARD."""
    attrs = prev.attrs
    marker = attrs.get("pending") if isinstance(attrs.get("pending"), dict) else {}
    if marker.get("title") or marker.get("summary") or prev.title is None:
        return False
    basis = attrs.get("title_basis") if isinstance(attrs.get("title_basis"), dict) else {}
    if basis.get("prompt_version") != PROMPT_VERSION:
        return False
    return _jaccard(members, {str(m) for m in basis.get("members") or ()}) >= TITLE_KEEP_JACCARD


def _needs_reform(system: Any, prev: PreviousCommunity) -> bool:
    """An unchanged community whose title still has to be written but has no live task to write it (every task
    failed out or was superseded), or whose basis names another prompt: it forms again."""
    from .memory_tasks import live_pending_tasks

    attrs = prev.attrs
    marker = attrs.get("pending") if isinstance(attrs.get("pending"), dict) else {}
    fields = [f for f in ("title", "summary") if marker.get(f)]
    if fields:
        live = live_pending_tasks(system.tasks, prev.record_id, fields)
        return any(v is None for v in live.values())
    basis = attrs.get("title_basis") if isinstance(attrs.get("title_basis"), dict) else {}
    return basis.get("prompt_version") != PROMPT_VERSION


def _links_gone(prev: PreviousCommunity, keys_now: Set[str]) -> bool:
    """The previous version's stored `links` name a community key that no current community carries tonight (a
    dissolved neighbour): the version forms again, so no stored link outlives the community it names."""
    return any(isinstance(link, Mapping) and str(link.get("to") or "") not in keys_now
               for link in prev.attrs.get("links") or ())


def communities_pass(system: Any, *, scopes: Sequence[Tuple[str, str]], owner_id: str, author: Any,
                     cancelled: Optional[Callable[[], bool]], budget: Optional[int] = None,
                     seed_previous: bool = True, detect_kinds: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """One night's communities (see the module docstring). `budget`: the most author calls this pass makes (None =
    no bound: every new or changed topic is authored). The budget goes to the topics FIRST and only to them, largest
    first: one call per new or changed topic (a carried title costs none) writes both its title and its summary, so the
    pass spends min(budget, n) of it, never more; the topics past it form pending (marker failure reason `budget_spent`)
    with their `title.author` / `digest.author` tasks at `COMMUNITY_PRIORITY`, ahead of every other pending record, so
    the next drain names them first. The version is still written. A host that shares one authoring budget between this
    pass and its drainer runs the pass first and gives the drainer `budget - budget_spent`.
    `cancelled`: the host's Stop check, called ONCE immediately before the write (True -> nothing is written, the
    receipt says `cancelled`); the commit guard inside the transaction is the truth for a Stop raised after it (its
    exception propagates). A home without a task queue is refused (a pending title always has its task). Returns the
    receipt: {version_seq | None, communities, new, kept, renamed, dissolved, unchanged, written, moved_in, moved_out,
    detected, attached, provisional, unvectored [ids], unvectored_count, unplaced [ids], unplaced_count,
    unplaced_closed [ids] (the module docstring), authored (the topics whose title and summary this pass wrote),
    pending (the topics written with a field still pending, their tasks queued), failed (`len(authoring.failures)`),
    titles_kept, budget (as given, None = unbounded), budget_spent (the author calls made, <= budget), ids {new, kept,
    renamed, dissolved, pending, written}, authoring {authored: [{record_id, record_kind, pass, fields}], failures}
    (the host's failure lines; a topic left pending by the budget is no failure line), cancelled, skipped, nodes,
    detection_nodes, edges, knn_edges, modularity, algorithm, params, elapsed_ms, timings_ms (per step in ms, and
    `rounds`: the detection rounds run, at most MAX_DETECTION_ROUNDS)}."""
    from .formation_authoring import author_and_shape, note
    from .memory_tasks import plan_formed, require_task_queue
    from .records import MemoryRecordInput, build_formation_plan, close_record_plan, record_id_for

    started = time.perf_counter()
    require_task_queue(system, PASS_NAME)
    out = _receipt()
    timings: Dict[str, float] = out["timings_ms"]
    np = _np()
    if np is None:
        out["skipped"] = "numpy is not importable (install abstractmemory[fast]): no vectors, no communities"
        out["elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
        return out
    if budget is not None and int(budget) < 0:
        raise ValueError(f"budget is the most author calls (>= 0) or None (got {budget!r})")
    out["budget"] = None if budget is None else int(budget)
    pairs = _pairs(scopes)
    owner = str(owner_id or "").strip()
    t = time.perf_counter()
    graph = read_community_graph(system, scopes=pairs, owner_id=owner)
    timings["read"] = round((time.perf_counter() - t) * 1000.0, 3)
    version_seq = graph.seq
    out["nodes"] = len(graph.nodes)
    det = detect_communities(graph, seed_previous=seed_previous, detect_kinds=detect_kinds)
    timings.update({"knn": round(det.knn_ms, 3), "louvain": round(det.louvain_ms, 3), "refine": round(det.refine_ms, 3),
                    "rounds": det.rounds})
    out.update({"detection_nodes": det.detection_nodes, "edges": det.edges, "knn_edges": det.knn_edges,
                "modularity": det.modularity, "unvectored": list(det.unvectored),
                "unvectored_count": len(det.unvectored)})
    t = time.perf_counter()
    matched = match_keys(det.groups, graph.previous)
    groups = [dict(g) for g in det.groups]
    # Provisional: a record nothing places now stays in the community it was in, while that community continues.
    key_group = {key: gi for gi, (key, _p, _j) in enumerate(matched)}
    keys_now = set(key_group)
    still: List[str] = []
    prev_key_of = {m: p.key for p in graph.previous for m in p.members}
    for rid in det.unplaced:
        gi = key_group.get(prev_key_of.get(rid, ""))
        if gi is None:
            still.append(rid)
        else:
            groups[gi][rid] = "provisional"
    out["unplaced"], out["unplaced_count"] = still, len(still)
    out["unplaced_closed"] = [rid for rid in still if rid in graph.closed_only and rid not in graph.vindex]
    # Members (join order kept), kinds, centroids, changes.
    current: List[Dict[str, Any]] = []
    for gi, (key, prev, jac) in enumerate(matched):
        g = groups[gi]
        prev_members = prev.members if prev is not None else {}
        members = [{"id": rid, "via": via,
                    "since_seq": int(prev_members[rid]["since_seq"]) if rid in prev_members else version_seq}
                   for rid, via in g.items()]
        members.sort(key=lambda m: (m["since_seq"], m["id"]))
        ids_set = {m["id"] for m in members}
        changed = prev is None or {(m["id"], m["via"]) for m in members} != {
            (mid, m["via"]) for mid, m in prev_members.items()}
        if not changed and _needs_reform(system, prev):
            changed = True
        if not changed and _links_gone(prev, keys_now):
            changed = True
        vec_rows = [graph.vindex[m] for m in sorted(ids_set) if m in graph.vindex]
        centroid = _unit_mean(np, graph.vectors[vec_rows]) if vec_rows else None
        kinds: Dict[str, int] = {}
        for m in members:
            k = graph.nodes[m["id"]].kind
            kinds[k] = kinds.get(k, 0) + 1
        current.append({"key": key, "prev": prev, "jaccard": jac, "members": members, "ids": ids_set,
                        "changed": changed, "centroid": centroid, "kinds": kinds, "size": len(members),
                        "split_from": det.split_from.get(gi),
                        "moved_in": len(ids_set - set(prev_members)), "moved_out": len(set(prev_members) - ids_set),
                        "vec_rows": vec_rows})
    matched_keys = {c["key"] for c in current if c["prev"] is not None}
    dissolved = [p for p in graph.previous if p.key not in matched_keys]
    out["communities"] = len(current)
    out["new"] = sum(1 for c in current if c["prev"] is None)
    out["kept"] = len(matched_keys)
    out["dissolved"] = len(dissolved)
    out["unchanged"] = sum(1 for c in current if not c["changed"])
    out["moved_in"] = sum(c["moved_in"] for c in current)
    out["moved_out"] = sum(c["moved_out"] for c in current) + sum(len(p.members) for p in dissolved)
    for c in current:
        for m in c["members"]:
            out[m["via"]] += 1
    out["ids"]["new"] = [c["key"] for c in current if c["prev"] is None]
    out["ids"]["kept"] = sorted(matched_keys)
    out["ids"]["dissolved"] = [p.key for p in dissolved]
    timings["match"] = round((time.perf_counter() - t) * 1000.0, 3)
    if not any(c["changed"] for c in current) and not dissolved:
        out["titles_kept"] = sum(1 for c in current if c["prev"] is not None and c["prev"].title is not None)
        if not graph.nodes:
            out["skipped"] = "empty: the home holds no formed record"
        elif not current:
            out["skipped"] = "no vectored record: nothing to detect over (embed_missing first)"
        else:
            out["skipped"] = "unchanged: every community stands as it is"
        out["elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
        return out
    # Layout (changed communities only; the unchanged stay where they are drawn) and links.
    t = time.perf_counter()
    where = {m["id"]: c["key"] for c in current for m in c["members"]}
    for c in current:
        cross: Dict[str, float] = {}
        for m in c["ids"]:
            for nb, w in det.weights.get(m, {}).items():
                k2 = where.get(nb)
                if k2 is not None and k2 != c["key"]:
                    cross[k2] = cross.get(k2, 0.0) + w
        c["links"] = [{"to": k2, "weight": round(w, 4)} for k2, w in sorted(cross.items()) if w > 0]
        c["link_total"] = cross
        prev = c["prev"]
        prev_layout = (prev.attrs.get("layout") if prev is not None and isinstance(prev.attrs.get("layout"), dict)
                       else None)
        c["pinned"] = prev_layout if (not c["changed"] and prev_layout and prev_layout.get("xy") is not None) else None
        if c["pinned"] is not None:
            c["radius"] = float(prev_layout.get("radius") or RADIUS_UNIT)
        c["prev_xy"] = prev_layout.get("xy") if prev_layout and prev_layout.get("xy") is not None else None
    _layout(np, current)
    for c in current:
        if c["changed"]:
            c["seats"] = _seats(np, c["members"], graph, float(c["radius"]))
    timings["layout"] = round((time.perf_counter() - t) * 1000.0, 3)
    # Authoring, in a fixed order (largest first), siblings' titles as they stand.
    t = time.perf_counter()
    titles: Dict[str, Optional[str]] = {c["key"]: (c["prev"].title if c["prev"] is not None
                                                   and not c["changed"] else None) for c in current}
    for c in current:
        if c["changed"] and c["prev"] is not None and _carried(c["prev"], c["ids"]):
            titles[c["key"]] = c["prev"].title
            c["carry"] = True
    scope0 = pairs[0][0]
    calls = 0
    records: List[Tuple[Dict[str, Any], Any, str]] = []
    for c in sorted(current, key=lambda c: (-c["size"], c["key"])):
        if not c["changed"]:
            continue
        prev = c["prev"]
        key = c["key"]
        rid = record_id_for(COMMUNITY_KIND, f"community|{owner}|{key}|v{version_seq}", 0)
        sample = briefing_sample(key, sorted(c["ids"]), graph, det.weights)
        others = [(k2, ttl) for k2, ttl in titles.items() if k2 != key and ttl]
        others.sort(key=lambda kv: (-c["link_total"].get(kv[0], 0.0), kv[0]))
        siblings = [ttl for _k2, ttl in others[:SIBLING_TITLES_MAX]]
        previous_title = prev.title if prev is not None else None
        body = _briefing(c["size"], c["kinds"], sample, graph, previous_title=previous_title, siblings=siblings)
        centroid = c["centroid"]
        cohesion = (round(float(np.mean(graph.vectors[c["vec_rows"]].astype(np.float64) @ centroid)), 6)
                    if centroid is not None else None)
        basis = {"version_seq": version_seq, "algorithm": ALGORITHM, "params": {"resolution": RESOLUTION,
                 "knn_k": KNN_K, "knn_min_cosine": KNN_MIN_COSINE},
                 "membership_hash": _hex("\n".join(sorted(c["ids"])), 16),
                 "previous_id": prev.record_id if prev is not None else None,
                 "matched_jaccard": c["jaccard"] if prev is not None else None,
                 "moved_in": c["moved_in"], "moved_out": c["moved_out"]}
        if c["split_from"]:
            origin = sorted(((len(set(p.members) & c["split_from"]), p.key) for p in graph.previous
                             if set(p.members) & c["split_from"]), key=lambda x: (-x[0], x[1]))
            basis["split_from"] = origin[0][1] if origin else None
        attrs: Dict[str, Any] = {
            "community_key": key, "members": c["members"], "size": c["size"], "kinds": c["kinds"],
            "centroid": _encode_centroid(centroid) if centroid is not None else None,
            "centroid_dim": int(centroid.shape[0]) if centroid is not None else None,
            "centroid_pin": graph.space, "cohesion": cohesion,
            "layout": {"xy": c["xy"], "radius": float(c["radius"]), "seats": c["seats"]},
            "links": c["links"], "basis": basis, "bookkeeping": True,
        }
        edges = (("refines", prev.record_id),) if prev is not None else ()
        if c.get("carry"):
            pa = prev.attrs
            for name in ("digest_method", "verdict", "title_basis"):
                if pa.get(name) is not None:
                    attrs[name] = pa[name]
            for name in ("understanding", "title_provenance"):  # the authored readings, carried (world-model rule)
                if isinstance(pa.get(name), dict):
                    attrs[name] = {**dict(pa[name]), "carried_from": prev.record_id}
            record = MemoryRecordInput(kind=COMMUNITY_KIND, title=prev.title, digest=prev.digest or body,
                                       edges=edges, attributes=attrs)
            records.append((c, record, rid))
            continue
        attrs["digest_method"] = BRIEFING_METHOD
        attrs["title_basis"] = {"members": sorted(c["ids"]), "sample_ids": sample, "prompt_version": PROMPT_VERSION,
                                "version_seq": version_seq}
        base = MemoryRecordInput(kind=COMMUNITY_KIND, title=None, digest=body, pending=("title", "summary"),
                                 edges=edges, attributes=attrs)
        if budget is not None and calls >= int(budget):
            from .journal import utc_now_iso

            at = utc_now_iso()
            record = replace(base, pending_failure={
                "reason": "budget_spent", "error_class": None, "at": at, "fields": ["title", "summary"],
                "message": f"the pass's authoring budget ({int(budget)} calls) was spent: the drainer authors it"})
            records.append((c, record, rid))
            continue
        calls += 1
        out["budget_spent"] += int(author is not None)
        capture = _Capture(author) if author is not None else None
        record, got = author_and_shape(capture, PASS_NAME, base, scope=scope0, owner_id=owner,
                                       fields=("title", "summary"), source_ids=sample)
        failure: Optional[Dict[str, Any]] = None
        if capture is not None and capture.bad_verdict is not None:
            failure = {"reason": "invalid_result", "error_class": "ValueError", "at": got.at,
                       "fields": ["title", "summary"],
                       "message": f"the author returned verdict {capture.bad_verdict} (known: {NO_COMMON_SUBJECT!r})"}
        elif record.title is not None:
            clash = [k2 for k2, ttl in titles.items() if k2 != key and _norm_title(ttl) == _norm_title(record.title)]
            if clash:
                failure = {"reason": "invalid_result", "error_class": "TitleCollision", "at": got.at,
                           "fields": ["title", "summary"],
                           "message": f"the title {record.title!r} is already another topic's title ({clash[0]})"}
        if failure is not None:
            feedback = (f"Another topic is already titled \"{record.title}\": this title must differ."
                        if failure["error_class"] == "TitleCollision" else None)
            body2 = _briefing(c["size"], c["kinds"], sample, graph, previous_title=previous_title,
                              siblings=siblings, feedback=feedback)
            record = replace(base, digest=body2, pending_failure=failure)
            out["authoring"]["failures"].append({"record_id": rid, "record_kind": COMMUNITY_KIND, "pass": PASS_NAME,
                                                 **failure})
        else:
            if capture is not None and capture.verdict is not None and record.title is not None:
                record = replace(record, attributes={**dict(record.attributes), "verdict": capture.verdict})
            note(out["authoring"], PASS_NAME, record, got, rid)
        if record.title is not None:
            titles[key] = record.title
        records.append((c, record, rid))
    timings["author"] = round((time.perf_counter() - t) * 1000.0, 3)
    # Plans, closures, the tasks they owe (pure reads), then cancelled() once, then the one transaction.
    t = time.perf_counter()
    plans, planned, closures, superseded = [], [], [], []
    for c, record, rid in records:
        key = c["key"]
        plan = build_formation_plan([record], scope=scope0, owner_id=owner,
                                    idempotency_key=f"community|{owner}|{key}|v{version_seq}")
        if tuple(plan.record_ids[:1]) != (rid,):
            raise CommunityPlanError(f"community {key}: the formation plan names {list(plan.record_ids)[:1]}, the pass "
                                     f"derived {rid!r} (version {version_seq})")
        plans.append(plan)
        planned.extend(plan_formed(system, plan, scope=scope0, owner_id=owner))
        prev = c["prev"]
        if prev is not None:
            closures.extend(close_record_plan(system.store, prev.record_id, kind="supersede", replacement_ids=[rid],
                                              reason=f"community {key}: version {version_seq}"))
            superseded.append((prev.record_id, f"community {key} revised to {rid}"))
    for p in dissolved:
        closures.extend(close_record_plan(system.store, p.record_id, kind="retract", replacement_ids=(),
                                          reason="dissolved"))
        superseded.append((p.record_id, f"community {p.key} dissolved"))
    timings["plan"] = round((time.perf_counter() - t) * 1000.0, 3)
    if cancelled is not None and bool(cancelled()):
        out["cancelled"] = "cancelled before the write: the host stopped the night (nothing written)"
        out["authoring"] = _receipt()["authoring"]
        out["elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
        return out
    t = time.perf_counter()
    _write_version(system, plans, planned, closures, superseded)
    timings["write"] = round((time.perf_counter() - t) * 1000.0, 3)
    out["version_seq"] = version_seq
    out["written"] = len(records)
    out["ids"]["written"] = [rid for _c, _r, rid in records]
    for c, record, _rid in records:
        if record.pending:
            out["pending"] += 1
            out["ids"]["pending"].append(c["key"])
        elif c.get("carry"):
            pass
        else:
            out["authored"] += 1
        if c["prev"] is not None and not c.get("carry"):
            out["renamed"] += 1
            out["ids"]["renamed"].append(c["key"])
    out["failed"] = len(out["authoring"]["failures"])
    out["titles_kept"] = (sum(1 for c in current if not c["changed"] and c["prev"] is not None
                              and c["prev"].title is not None) + sum(1 for c in current if c.get("carry")))
    out["elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    return out


# --------------------------------------------------------------------------- reads other verbs share


def community_records(system: Any, *, scopes: Sequence[Tuple[str, str]], owner_id: str) -> List[PreviousCommunity]:
    """The current (open) community versions of the home, one per key, by key (PURE READ; numpy needed only to
    decode centroids, which are None without it)."""
    if _np() is None:
        raise RuntimeError("community_records needs numpy (abstractmemory[fast])")
    return read_community_graph(system, scopes=scopes, owner_id=owner_id).previous


# --------------------------------------------------------------------------- embed_missing


def embed_missing(system: Any, *, scopes: Sequence[Tuple[str, str]], owner_id: str,
                  record_ids: Optional[Sequence[str]] = None,
                  cancelled: Optional[Callable[[], bool]]) -> Dict[str, Any]:
    """Embed the open formed records of these scopes that have no vector (`record_ids` None = every one of them; a
    list = those only), with the store's own embedder (formation's: its text = `canonical_text`, its pin checked),
    one small commit per vector under the commit guard (partial progress stands). No model call but the embedder's.
    `cancelled` is checked before each record: the rest are skipped, reason `cancelled`. The embedder failing is
    never raised: that record and the rest are skipped, reason `embedder_unavailable` (no embedder at all:
    `no_embedder`). A pinless store is pinned at its first vector, loudly, as formation pins it. A vector of the wrong
    dimension is `failed` (`dimension_mismatch`), never written. Community records are never embedded (D4). The commit guard's refusal propagates (the host's Stop).
    Returns {pass_name, embedded [ids], skipped [ids], failed [{id, reason}], reasons {id: reason}, cancelled}."""
    from .canonical_text import canonical_text, never_embedded
    from .embedding_pin import build_pin, check_add_dimension, embedder_model_id, warn_first_write_pin
    from .in_memory_store import InMemoryTripleStore
    from .memory_tasks import require_task_queue
    from .records import resolve_digest_assertion
    from .sqlite_store import SQLiteTripleStore
    from .vector_matrix import encode_vector

    require_task_queue(system, "embed_missing")
    store, journal = system.store, system.journal
    out: Dict[str, Any] = {"pass_name": "embed_missing", "embedded": [], "skipped": [], "failed": [], "reasons": {},
                           "cancelled": False}

    def skip(rid: str, reason: str) -> None:
        out["skipped"].append(rid)
        out["reasons"][rid] = reason

    pairs = _pairs(scopes)
    owner = str(owner_id or "").strip()
    closed = {str(c.assertion_id) for c in journal.closures(limit=0)}
    targets: List[Tuple[str, Any]] = []
    if record_ids is None:
        if _np() is None:
            raise RuntimeError("embed_missing(record_ids=None) reads the home with numpy (abstractmemory[fast])")
        graph = read_community_graph(system, scopes=pairs, owner_id=owner)
        for rid in sorted(set(graph.nodes) - set(graph.vec_ids)):
            a = resolve_digest_assertion(store, graph.nodes[rid].assertion_id)
            if a is not None and store.stored_vector(str(a.assertion_id)) is None:
                targets.append((rid, a))
    else:
        allowed = set(pairs)
        for raw in dict.fromkeys(str(r or "").strip() for r in record_ids):
            if not raw:
                continue
            a = resolve_digest_assertion(store, raw)
            attrs = a.attributes if a is not None and isinstance(a.attributes, dict) else {}
            if a is None or not attrs.get("record_kind"):
                out["failed"].append({"id": raw, "reason": "unknown_record"})
                continue
            if (str(a.scope), str(a.owner_id or "")) not in allowed and (str(a.scope), "") not in allowed:
                out["failed"].append({"id": raw, "reason": "out_of_scope"})
            elif str(a.assertion_id) in closed:
                skip(raw, "closed")
            elif never_embedded(a):
                skip(raw, "never_embedded")
            elif store.stored_vector(str(a.assertion_id)) is not None:
                skip(raw, "vectored")
            else:
                targets.append((raw, a))
    embedder = getattr(store, "_embedder", None)
    pin = store.embedding_pin() if hasattr(store, "embedding_pin") else None
    stop_reason: Optional[str] = None
    if embedder is None:
        stop_reason = "no_embedder"
    for rid, a in targets:
        if stop_reason is None and cancelled is not None and bool(cancelled()):
            out["cancelled"] = True
            stop_reason = "cancelled"
        if stop_reason is not None:
            skip(rid, stop_reason)
            continue
        try:
            [vector] = embedder.embed_texts([canonical_text(a)])
            vector = [float(x) for x in vector]
        except Exception as exc:  # the embedder failed: skipped, never raised (formation's degradation)
            stop_reason = "embedder_unavailable"
            skip(rid, f"embedder_unavailable: {type(exc).__name__}: {exc}")
            continue
        try:
            dim = check_add_dimension(pin, [vector])
        except ValueError:
            out["failed"].append({"id": rid, "reason": "dimension_mismatch"})
            continue
        if not pin or pin.get("dimension") is None:  # formation's first-write pin (sqlite_store._prepare_add)
            pin = (dict(pin, dimension=dim) if pin else
                   build_pin(embedder_model_id(embedder), dim, source="first-write", claimed_by="embedder-attribute"))
            if pin.get("source") == "first-write":
                warn_first_write_pin(pin)
            store._write_pin(pin)
        aid = str(a.assertion_id)
        if isinstance(store, SQLiteTripleStore):
            blob = encode_vector(vector)

            def write(cur: Any, aid: str = aid, blob: Any = blob) -> bool:
                cur.execute(f"UPDATE {store._table} SET embedding = ? WHERE assertion_id = ? AND embedding IS NULL",
                            (blob, aid))
                wrote = int(cur.rowcount or 0) > 0
                if wrote:
                    store._bump_vector_generation(cur)
                return wrote

            wrote = system.tasks._txn(None, write, where="communities.embed_missing")
        elif isinstance(store, InMemoryTripleStore):
            wrote = False
            with store._write("communities.embed_missing"):
                for row in store._rows:
                    if row.get("assertion_id") == aid:
                        if not isinstance(row.get(store._vector_column), list):
                            row[store._vector_column] = vector
                            wrote = True
                        break
        else:
            raise TypeError(f"embed_missing writes a SQLiteTripleStore or an InMemoryTripleStore "
                            f"(got {type(store).__name__})")
        if wrote:
            out["embedded"].append(rid)
        else:
            skip(rid, "vectored")
    return out
