"""Communities at formation and in reads (community_index.py): `place_record` inside `form_with_tasks`, the `placed`
event, the `communities` / `community_of` reads (payload v2) and the replay projection of a community record.

Most community records here are a FIXTURE version written by the test (`_write_version`: digest rows of kind
`community` with the attributes the sleep pass writes: community_key, members, size, kinds, centroid + dim + pin,
cohesion, layout, links, basis.version_seq/algorithm/moved_in/moved_out/split_from), so each case controls its
version exactly; those cases run on the in-memory pair, the SQLite home (store and journal in one file) and an
in-memory store beside a SQLite journal. `test_the_real_pass_...` runs the sleep pass itself
(`communities.communities_pass`) twice on both pairs it writes on: read, placement, replay and confirmation. Also
`records_since_maintenance(...)["fragmented"]`.

MUTATION LIST (scratch copy under untracked/communities-m2/, each mutant run against this file; all red, the source
restored byte-exact):
P1 the SQLite home writes the placed event in its own journal transaction after the formation's COMMIT;
P2 the in-memory pair keeps the placed event of a failed formation (no discard);
P3 the index notes a placement before the COMMIT (a refused formation leaves the record "already placed");
P4 the formation never catches the index up (a version written after the first formation is never seen);
P5 the placed event says provisional false;
P6 the placed event id is random (a formation that lost the race to another process writes a second event);
P7 the read folds no placed event (provisional_ids always empty);
P8 a pending summary is served as the briefing text;
P9 a community record's binding envelope draws every edge (per-member edges come back);
P10 a stale centroid still places by cosine;
P11 a record without a vector is never placed through its neighbours;
F1 `fragmented.provisional` counts placements from before the last night; F2 closed records count as live;
FA1 `facts.paths` counts pairs across two communities; FA2 `facts.activity` ignores its 7-day window;
FA3 every version reads as changed since the last sleep; FA4 no bridge member is found.
"""

from __future__ import annotations

import base64
import hashlib
import math
import time
import warnings
from array import array
from typing import Any, Dict, List, Optional, Sequence

import pytest

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    TripleAssertion,
)
from abstractmemory import community_index as ci
from abstractmemory.community_index import (
    CommunitySchemaError,
    PreparedPlacement,
    communities,
    community_of,
    place_record,
)
from abstractmemory.replay import export_replay

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [("self", OWNER), ("diary", OWNER), ("life", OWNER)]
DIM = 8
AXES = {"alpha": 0, "beta": 1, "gamma": 2}


class TopicEmbedder:
    """Unit vectors on one axis per topic word (alpha, beta, gamma) plus a small deterministic tilt; a text naming
    `novector` makes the embed call fail (the batch forms vector-less, a labelled fallback)."""

    model = "topic-axes-8"

    def embed_texts(self, texts):
        out = []
        for t in texts:
            if "novector" in str(t):
                raise RuntimeError("embedder down")
            v = [0.0] * DIM
            for word, axis in AXES.items():
                if word in str(t):
                    v[axis] = 1.0
            h = hashlib.sha256(str(t).encode()).digest()
            for i in range(3, DIM):
                v[i] = (h[i] / 255.0) * 0.2
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


class Guard:
    def __init__(self) -> None:
        self.refuse: Optional[str] = None

    def __call__(self, where: str) -> None:
        if self.refuse is not None and (self.refuse == "*" or where == self.refuse):
            raise RuntimeError(f"stopped at {where}")


def _open(kind: str, tmp_path, guard: Guard) -> MemorySystem:
    emb = TopicEmbedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if kind == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        elif kind == "sqlite":
            path = tmp_path / "memory.sqlite3"
            store, journal = SQLiteTripleStore(path, embedder=emb), SQLiteJournal(path)
        else:
            store, journal = InMemoryTripleStore(embedder=emb), SQLiteJournal(tmp_path / "journal.sqlite3")
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=True, commit_guard=guard)
    system.kind = kind
    return system


@pytest.fixture(params=["memory", "sqlite", "memory+sqlite-journal"])
def home(request, tmp_path):
    guard = Guard()
    system = _open(request.param, tmp_path, guard)
    system.guard = guard
    yield system
    system.journal.close()
    system.store.close()


def _remember(system, key: str, digest: str, *, kind: str = "episode", edges=()) -> str:
    rec = MemoryRecordInput(kind=kind, title=f"About {key}", digest=digest, edges=tuple(edges))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return system.remember_many([rec], scope=SCOPE, owner_id=OWNER, idempotency_key=key)[0]


def _vector(system, graph_id: str) -> List[float]:
    from abstractmemory.records import resolve_digest_assertion

    a = resolve_digest_assertion(system.store, graph_id)
    return list(system.store.stored_vector(a.assertion_id))


def _b64(values: Sequence[float]) -> str:
    return base64.b64encode(array("f", [float(v) for v in values]).tobytes()).decode("ascii")


def _write_version(system, groups: Dict[str, Sequence[str]], *, previous: Optional[Dict[str, str]] = None,
                   pending: Sequence[str] = (), pin_id: Any = "store", links=(), dissolve: Sequence[str] = (),
                   extra_edges: Sequence[tuple] = (), split_from: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """A fixture communities version: one record per key, a new graph id per version, the previous versions closed
    (supersede; `dissolve` keys retracted). Returns {version_seq, ids: key -> record graph id, aids}."""
    store, journal = system.store, system.journal
    split_from = dict(split_from or {})
    vs = journal.current_seq() + 1
    pin = ci._space_id(store) if pin_id == "store" else pin_id
    assertions, ids, aids = [], {}, {}
    for n, (key, members) in enumerate(sorted(groups.items())):
        vecs = [v for v in (store.stored_vector(_aid(system, m)) for m in members) if v]
        attrs: Dict[str, Any] = {
            "literal": True, "record_kind": "community", "community_key": key,
            "title": None if "title" in pending else f"Topic {key}",
            "members": [{"id": m, "via": "detected", "since_seq": vs} for m in members],
            "size": len(members), "kinds": {"episode": len(members)},
            "cohesion": 0.5, "verdict": None,
            "layout": {"xy": [float(n), 0.0], "radius": 1.0 + n, "seats": {m: [0.1 * i, 0.0] for i, m in enumerate(members)}},
            "links": [{"to": other, "weight": w} for (a, other, w) in links if a == key],
            "basis": {"version_seq": vs, "algorithm": "louvain-warm-v1",
                      "moved_in": len(set(members) - set(getattr(system, "prev_members", {}).get(key, ()))),
                      "moved_out": len(set(getattr(system, "prev_members", {}).get(key, ())) - set(members))},
            "bookkeeping": True,
        }
        if split_from.get(key):
            attrs["basis"]["split_from"] = split_from[key]
        if vecs:
            mean = [sum(col) / len(vecs) for col in zip(*vecs)]
            attrs.update(centroid=_b64(mean), centroid_dim=len(mean), centroid_pin=pin)
        if pending:
            attrs["pending"] = {"title": "title" in pending, "summary": "summary" in pending, "since": "x", "attempts": 0}
        gid = f"ex:community-{hashlib.sha256(f'{key}|{vs}'.encode()).hexdigest()[:26]}"
        aid = hashlib.sha256(f"{gid}|digest".encode()).hexdigest()[:32]
        ids[key], aids[key] = gid, aid
        assertions.append(TripleAssertion(subject=gid, predicate="dcterms:abstract",
                                          object=f"Briefing of {key}" if "summary" in pending else f"Summary of {key}",
                                          scope=SCOPE, owner_id=OWNER, attributes=attrs, assertion_id=aid))
        if previous and key in previous:
            assertions.append(TripleAssertion(subject=gid, predicate="refines", object=previous[key], scope=SCOPE,
                                              owner_id=OWNER, attributes={"record_edge": True}))
        for rel, target in extra_edges:
            assertions.append(TripleAssertion(subject=gid, predicate=rel, object=target, scope=SCOPE,
                                              owner_id=OWNER, attributes={"record_edge": True}))
    store.add(assertions)
    from abstractmemory.journal import ScopeBinding

    for gid in ids.values():
        journal.append_binding(ScopeBinding(record_id=gid, scope=SCOPE, owner_id=OWNER, source="maintenance"))
    for key, old_aid in (system.prev_aids if hasattr(system, "prev_aids") else {}).items():
        if key in dissolve:
            system.close_assertions([old_aid], kind="retract", reason="dissolved")
        elif key in aids:
            system.close_assertions([old_aid], kind="supersede", replacement_ids=[aids[key]], reason="new version")
    system.prev_aids = {**{k: v for k, v in getattr(system, "prev_aids", {}).items() if k not in dissolve}, **aids}
    system.prev_members = {**getattr(system, "prev_members", {}), **{k: list(m) for k, m in groups.items()}}
    return {"version_seq": vs, "ids": ids, "aids": aids}


def _aid(system, graph_id: str) -> str:
    from abstractmemory.records import resolve_digest_assertion

    return resolve_digest_assertion(system.store, graph_id).assertion_id


def _placed(system, record_id: Optional[str] = None) -> List[Any]:
    out = []
    for scope, owner in SCOPES:
        out += system.journal.events(scope=scope, owner_id=owner, record_id=record_id, kinds=["placed"], limit=0)
    return sorted(out, key=lambda e: e.seq)


def _two_topics(system) -> Dict[str, Any]:
    a = [_remember(system, f"a{i}", f"Notes on alpha number {i}.") for i in range(3)]
    b = [_remember(system, f"b{i}", f"Notes on beta number {i}.") for i in range(3)]
    v = _write_version(system, {"k-alpha": a, "k-beta": b}, links=[("k-alpha", "k-beta", 1.5)])
    v.update(alpha=a, beta=b)
    return v


# --------------------------------------------------------------------------- no version


def test_no_version_no_placement_and_first_sleep_pending(home):
    rid = _remember(home, "x", "Notes on alpha.")
    assert _placed(home) == []
    assert communities(home, scopes=SCOPES, owner_id=OWNER) == {
        "version": 2, "version_seq": None, "first_sleep_pending": True, "algorithm": None,
        "communities": [], "links": []}
    got = community_of(home, rid)
    assert got["first_sleep_pending"] is True and got["community_key"] is None and got["version_seq"] is None


# --------------------------------------------------------------------------- placement


def test_nearest_centroid_placement_is_provisional_and_one_event(home):
    v = _two_topics(home)
    seq_before = home.journal.current_seq()
    rid = _remember(home, "new-a", "Fresh thoughts about alpha.")
    events = _placed(home, rid)
    assert len(events) == 1
    e = events[0]
    assert e.kind == "placed" and e.record_id == rid and e.weight == 0.0
    assert e.provenance["community_key"] == "k-alpha"
    assert e.provenance["community_id"] == v["ids"]["k-alpha"]
    assert e.provenance["provisional"] is True and e.provenance["how"] == "centroid"
    assert e.provenance["version_seq"] == v["version_seq"] and e.provenance["score"] > 0.9
    assert e.seq > seq_before
    # The community record is not rewritten at formation.
    assert [h.assertion_id for h in ci._community_heads(home.store)] == list(v["aids"].values())
    got = community_of(home, rid)
    assert (got["community_key"], got["provisional"], got["via"], got["how"]) == ("k-alpha", True, "provisional",
                                                                                 "centroid")
    served = {c["key"]: c for c in communities(home, scopes=SCOPES, owner_id=OWNER)["communities"]}
    assert served["k-alpha"]["provisional_ids"] == [rid]
    assert served["k-beta"]["provisional_ids"] == []
    member = community_of(home, v["alpha"][0])
    assert (member["community_key"], member["provisional"], member["via"]) == ("k-alpha", False, "detected")


def test_community_records_are_never_placed(home):
    _two_topics(home)
    before = len(_placed(home))
    _write_version(home, {"k-alpha": [], "k-beta": []})
    assert len(_placed(home)) == before


def test_replayed_formation_writes_no_second_event(home):
    _two_topics(home)
    rid = _remember(home, "same", "Fresh thoughts about beta.")
    again = _remember(home, "same", "Fresh thoughts about beta.")
    assert again == rid
    assert len(_placed(home, rid)) == 1


def test_a_formation_that_lost_the_race_writes_no_second_event(tmp_path, monkeypatch):
    """Two processes form the same record: the loser read it missing before the winner committed, so its rows are
    INSERT OR IGNORE no-ops and its own index never saw the winner's placement; the derived event id makes its
    placed event a journal no-op."""
    first = _open("sqlite", tmp_path, Guard())
    second = _open("sqlite", tmp_path, Guard())
    try:
        _two_topics(first)
        rid = _remember(first, "race", "Fresh thoughts about alpha.")
        real = second.store.query
        monkeypatch.setattr(second.store, "query", lambda q: [] if q.assertion_ids else real(q))
        assert _remember(second, "race", "Fresh thoughts about alpha.") == rid
        assert len(_placed(first, rid)) == 1
    finally:
        for system in (second, first):
            system.journal.close()
            system.store.close()


def test_vectorless_record_placed_through_its_neighbours_else_unplaced(home):
    v = _two_topics(home)
    linked = _remember(home, "nv1", "novector text", edges=[("mentions", v["beta"][0]), ("mentions", v["beta"][1])])
    [e] = _placed(home, linked)
    assert (e.provenance["community_key"], e.provenance["how"], e.provenance["score"]) == ("k-beta", "neighbour", 1.0)
    alone = _remember(home, "nv2", "novector alone")
    assert _placed(home, alone) == []
    got = community_of(home, alone)
    assert got["community_key"] is None and got["first_sleep_pending"] is False
    assert all(alone not in c["provisional_ids"] for c in communities(home, scopes=SCOPES, owner_id=OWNER)["communities"])


def test_stale_centroids_place_by_neighbours_only(home):
    a = [_remember(home, f"a{i}", f"Notes on alpha {i}.") for i in range(2)]
    b = [_remember(home, f"b{i}", f"Notes on beta {i}.") for i in range(2)]
    _write_version(home, {"k-alpha": a, "k-beta": b}, pin_id="another-model@8")
    served = communities(home, scopes=SCOPES, owner_id=OWNER)["communities"]
    assert all(c["centroid_stale"] for c in served)
    by_cosine = _remember(home, "s1", "More about alpha.")
    assert _placed(home, by_cosine) == []
    by_edge = _remember(home, "s2", "More about alpha.", edges=[("mentions", b[0])])
    [e] = _placed(home, by_edge)
    assert (e.provenance["community_key"], e.provenance["how"]) == ("k-beta", "neighbour")


# --------------------------------------------------------------------------- the formation transaction


def test_a_refused_formation_lands_no_record_and_no_placed_event(home):
    _two_topics(home)
    seq = home.journal.current_seq()
    home.guard.refuse = "tasks.form_with_tasks"
    with pytest.raises(RuntimeError, match="stopped"):
        _remember(home, "stop", "Fresh thoughts about alpha.")
    home.guard.refuse = None
    planned = MemoryRecordInput(kind="episode", title="About stop", digest="Fresh thoughts about alpha.")
    from abstractmemory.records import build_formation_plan, resolve_digest_assertion

    rid = build_formation_plan([planned], scope=SCOPE, owner_id=OWNER, idempotency_key="stop").record_ids[0]
    assert resolve_digest_assertion(home.store, rid) is None
    assert _placed(home) == []
    assert home.journal.current_seq() == seq
    # Nothing of the refused attempt stays in the index: the same formation, allowed now, places its record.
    assert _remember(home, "stop", "Fresh thoughts about alpha.") == rid
    [e] = _placed(home, rid)
    assert e.provenance["community_key"] == "k-alpha"


def test_the_placed_event_commits_with_the_record(home):
    """A journal write of its own would be a second commit point: refusing exactly that point must not matter."""
    _two_topics(home)
    home.guard.refuse = "journal"
    rid = _remember(home, "together", "Fresh thoughts about beta.")
    home.guard.refuse = None
    [e] = _placed(home, rid)
    assert e.provenance["community_key"] == "k-beta"


def test_a_version_written_after_the_first_formation_is_caught_up(home):
    v1 = _two_topics(home)
    first = _remember(home, "f1", "Fresh thoughts about alpha.")
    assert _placed(home, first)[0].provenance["version_seq"] == v1["version_seq"]
    # The night's pass writes a version (a gamma topic) the way another process would: rows above the mark.
    g = [_remember(home, f"g{i}", f"Notes on gamma {i}.") for i in range(2)]
    v2 = _write_version(home, {"k-alpha": v1["alpha"] + [first], "k-beta": v1["beta"], "k-gamma": g},
                        previous=v1["ids"])
    later = _remember(home, "f2", "Fresh thoughts about gamma.")
    [e] = _placed(home, later)
    assert (e.provenance["community_key"], e.provenance["version_seq"]) == ("k-gamma", v2["version_seq"])
    assert e.provenance["community_id"] == v2["ids"]["k-gamma"]


def test_unrelated_rows_never_reload_the_index(home, monkeypatch):
    _two_topics(home)
    _remember(home, "warm", "Fresh thoughts about alpha.")
    reloads = []
    real = ci._fold
    monkeypatch.setattr(ci, "_fold", lambda *a, **k: reloads.append(1) or real(*a, **k))
    for i in range(4):
        _remember(home, f"more{i}", f"Fresh thoughts about beta {i}.")
    assert reloads == []
    assert len(_placed(home)) == 5


def test_place_record_reads_no_store_row(tmp_path):
    system = _open("sqlite", tmp_path, Guard())
    try:
        v = _two_topics(system)
        ci._catch_up(system)
        vec = _vector(system, v["alpha"][0])
        statements: List[str] = []
        system.store._conn.set_trace_callback(statements.append)
        started = time.perf_counter()
        with system.store._lock:
            cur = system.store._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            for i in range(50):
                p = PreparedPlacement(record_id=f"ex:episode-probe{i}", assertion_id=f"probe{i}", scope=SCOPE,
                                      owner_id=OWNER, vector=vec)
                assert place_record(system, p, cur=cur)["community_key"] == "k-alpha"
            cur.execute("ROLLBACK")
        per_record = (time.perf_counter() - started) / 50
        system.store._conn.set_trace_callback(None)
        reads = [s for s in statements if "triples" in s and not s.startswith(("BEGIN", "ROLLBACK"))
                 and "memj_" not in s]
        assert reads == []
        assert per_record < 0.005
    finally:
        system.journal.close()
        system.store.close()


def test_an_unreadable_version_never_blocks_formation(home):
    a = [_remember(home, f"a{i}", f"Notes on alpha {i}.") for i in range(2)]
    v = _write_version(home, {"k-alpha": a})
    broken = {k: val for k, val in home.store.query(
        __import__("abstractmemory").TripleQuery(assertion_ids=(v["aids"]["k-alpha"],), limit=1))[0].attributes.items()
        if k != "community_key"}
    home.store.add([TripleAssertion(subject="ex:community-broken", predicate="dcterms:abstract", object="x",
                                    scope=SCOPE, owner_id=OWNER, attributes=broken)])
    rec = MemoryRecordInput(kind="episode", title="About still", digest="Fresh thoughts about alpha.")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        [rid] = home.remember_many([rec], scope=SCOPE, owner_id=OWNER, idempotency_key="still")
    assert any("#FALLBACK: formation places no record" in str(w.message) and "community_key" in str(w.message)
               for w in caught)
    assert rid and _placed(home, rid) == []
    with pytest.raises(CommunitySchemaError, match="community_key"):
        communities(home, scopes=SCOPES, owner_id=OWNER)


# --------------------------------------------------------------------------- the read shape (payload v2)


def _use(system, graph_id: str, n: int = 1, *, days_ago: int = 0) -> None:
    from datetime import datetime, timedelta, timezone

    from abstractmemory.journal import MemoryEvent

    at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="microseconds")
    system.journal.append_events([MemoryEvent(kind="selected", scope=SCOPE, owner_id=OWNER,
                                              record_id=_aid(system, graph_id), observed_at=at) for _ in range(n)])


def _co_use(system, a: str, b: str, n: int = 1) -> None:
    from abstractmemory.journal import MemoryEvent

    system.journal.append_events([MemoryEvent(kind="co_selected", scope=SCOPE, owner_id=OWNER,
                                              pair_ids=(_aid(system, a), _aid(system, b))) for _ in range(n)])


def _formed_at(system, graph_id: str) -> str:
    from abstractmemory.records import resolve_digest_assertion

    return resolve_digest_assertion(system.store, graph_id).observed_at


def test_read_shape_golden(home):
    b = [_remember(home, f"b{i}", f"Notes on beta number {i}.") for i in range(3)]
    a = [_remember(home, f"a{i}", f"Notes on alpha number {i}.") for i in range(2)]
    a.append(_remember(home, "a2", "Notes on alpha number 2.", edges=[("mentions", b[0])]))
    v = _write_version(home, {"k-alpha": a, "k-beta": b}, links=[("k-alpha", "k-beta", 1.5)])
    rid = _remember(home, "p", "Fresh thoughts about beta.")
    _use(home, a[1], 2)
    _use(home, a[0], 1)
    _use(home, a[2], 5, days_ago=30)          # used often, but long ago: the hub, never this week's activity
    _co_use(home, a[0], a[1], 3)
    _co_use(home, a[0], a[2], 1)
    _co_use(home, a[0], b[1], 4)              # across two communities: no community's path
    payload = communities(home, scopes=SCOPES, owner_id=OWNER)
    assert payload == {
        "version": 2,
        "version_seq": v["version_seq"],
        "first_sleep_pending": False,
        "algorithm": "louvain-warm-v1",
        "communities": [
            {"id": v["ids"]["k-alpha"], "key": "k-alpha", "title": "Topic k-alpha", "summary": "Summary of k-alpha",
             "pending": [], "verdict": None, "size": 3, "kinds": {"episode": 3},
             "members": [{"id": m, "via": "detected"} for m in a], "provisional_ids": [], "cohesion": 0.5,
             "layout": {"xy": [0.0, 0.0], "radius": 1.0, "seats": {m: [0.1 * i, 0.0] for i, m in enumerate(a)}},
             "centroid_stale": False,
             "facts": {"span": {"first": _formed_at(home, a[0]), "last": _formed_at(home, a[2])},
                       "activity": 3, "hub": a[2], "bridges": [a[2]],
                       "paths": [{"from": min(a[0], a[1]), "to": max(a[0], a[1]), "count": 3},
                                 {"from": min(a[0], a[2]), "to": max(a[0], a[2]), "count": 1}],
                       "changed_since_last_sleep": {"added": 3, "moved": 0, "split_from": None}}},
            {"id": v["ids"]["k-beta"], "key": "k-beta", "title": "Topic k-beta", "summary": "Summary of k-beta",
             "pending": [], "verdict": None, "size": 3, "kinds": {"episode": 3},
             "members": [{"id": m, "via": "detected"} for m in b], "provisional_ids": [rid], "cohesion": 0.5,
             "layout": {"xy": [1.0, 0.0], "radius": 2.0, "seats": {m: [0.1 * i, 0.0] for i, m in enumerate(b)}},
             "centroid_stale": False,
             "facts": {"span": {"first": _formed_at(home, b[0]), "last": _formed_at(home, b[2])},
                       "activity": 0, "hub": None, "bridges": [b[0]], "paths": [],
                       "changed_since_last_sleep": {"added": 3, "moved": 0, "split_from": None}}},
        ],
        "links": [{"a": "k-alpha", "b": "k-beta", "weight": 1.5}],
    }


def test_facts_name_only_the_last_version_as_changed(home):
    v1 = _two_topics(home)
    g = [_remember(home, f"g{i}", f"Notes on gamma {i}.") for i in range(2)]
    _write_version(home, {"k-alpha": v1["alpha"][:2], "k-gamma": g + v1["alpha"][2:]}, previous=v1["ids"],
                   split_from={"k-gamma": "k-alpha"})
    facts = {c["key"]: c["facts"]["changed_since_last_sleep"]
             for c in communities(home, scopes=SCOPES, owner_id=OWNER)["communities"]}
    assert facts == {"k-alpha": {"added": 0, "moved": 1, "split_from": None},
                     "k-beta": {"added": 0, "moved": 0, "split_from": None},
                     "k-gamma": {"added": 3, "moved": 0, "split_from": "k-alpha"}}


def test_pending_title_and_summary_are_served_as_none(home):
    a = [_remember(home, f"a{i}", f"Notes on alpha {i}.") for i in range(2)]
    _write_version(home, {"k-alpha": a}, pending=("title", "summary"))
    [c] = communities(home, scopes=SCOPES, owner_id=OWNER)["communities"]
    assert (c["title"], c["summary"], c["pending"]) == (None, None, ["title", "summary"])


def test_versions_dissolution_and_as_of(home):
    v1 = _two_topics(home)
    g = [_remember(home, f"g{i}", f"Notes on gamma {i}.") for i in range(2)]
    v2 = _write_version(home, {"k-alpha": v1["alpha"] + v1["beta"], "k-gamma": g}, previous=v1["ids"],
                        dissolve=("k-beta",))
    now = communities(home, scopes=SCOPES, owner_id=OWNER)
    assert now["version_seq"] == v2["version_seq"]
    assert [(c["key"], c["id"]) for c in now["communities"]] == [("k-alpha", v2["ids"]["k-alpha"]),
                                                                 ("k-gamma", v2["ids"]["k-gamma"])]
    then = communities(home, scopes=SCOPES, owner_id=OWNER, version=v1["version_seq"])
    assert then["version_seq"] == v1["version_seq"]
    assert [(c["key"], c["id"]) for c in then["communities"]] == [("k-alpha", v1["ids"]["k-alpha"]),
                                                                  ("k-beta", v1["ids"]["k-beta"])]
    with pytest.raises(ValueError, match="no communities version"):
        communities(home, scopes=SCOPES, owner_id=OWNER, version=v1["version_seq"] - 1)
    # A placement made under v1 and never confirmed is not provisional under v2.
    assert all(c["provisional_ids"] == [] for c in now["communities"])


def test_a_placement_confirmed_by_the_next_version_is_a_member(home):
    v1 = _two_topics(home)
    rid = _remember(home, "conf", "Fresh thoughts about alpha.")
    _write_version(home, {"k-alpha": v1["alpha"] + [rid], "k-beta": v1["beta"]}, previous=v1["ids"])
    got = community_of(home, rid)
    assert (got["community_key"], got["provisional"], got["via"]) == ("k-alpha", False, "detected")
    served = {c["key"]: c for c in communities(home, scopes=SCOPES, owner_id=OWNER)["communities"]}
    assert served["k-alpha"]["provisional_ids"] == [] and {"id": rid, "via": "detected"} in served["k-alpha"]["members"]


def test_community_of_refuses_unknown_and_community_records(home):
    v = _two_topics(home)
    with pytest.raises(ValueError, match="unknown record"):
        community_of(home, "ex:episode-nope")
    with pytest.raises(ValueError, match="community record"):
        community_of(home, v["ids"]["k-alpha"])


# --------------------------------------------------------------------------- replay


def test_replay_projects_a_community_record_like_any_record(home):
    v1 = _two_topics(home)
    v2 = _write_version(home, {"k-alpha": v1["alpha"], "k-beta": v1["beta"]}, previous=v1["ids"],
                        extra_edges=[("has_member", v1["alpha"][0])])
    rid = _remember(home, "r", "Fresh thoughts about alpha.")
    envelopes = list(export_replay(home.store, home.journal, scope=SCOPE, owner_id=OWNER))
    bindings = {e["display"]["graph_id"]: e for e in envelopes
                if e["family"] == "binding" and e.get("display", {}).get("kind") == "community"}
    new = bindings[v2["ids"]["k-alpha"]]["display"]
    assert new["kind"] == "community" and new["title"] == "Topic k-alpha" and new["digest"] == "Summary of k-alpha"
    assert (new["community_key"], new["version_seq"], new["size"]) == ("k-alpha", v2["version_seq"], 3)
    assert new["edges"] == [{"relation": "refines", "target_graph_id": v1["ids"]["k-alpha"]}]
    assert new["version_count"] == 1 and "authored_by" in new
    old = bindings[v1["ids"]["k-alpha"]]["display"]
    assert old["replaced_by"] == [v2["aids"]["k-alpha"]] and "edges" not in old
    [placed] = [e for e in envelopes if e["family"] == "event" and e["payload"]["kind"] == "placed"]
    assert placed["payload"]["record_id"] == rid
    assert placed["payload"]["provenance"]["community_key"] == "k-alpha"
    assert placed["display"]["graph_id"] == rid


def test_replay_carries_a_pending_community_record(home):
    a = [_remember(home, f"a{i}", f"Notes on alpha {i}.") for i in range(2)]
    v = _write_version(home, {"k-alpha": a}, pending=("title", "summary"))
    [env] = [e for e in export_replay(home.store, home.journal, scope=SCOPE, owner_id=OWNER)
             if e["family"] == "binding" and e["payload"]["record_id"] == v["ids"]["k-alpha"]]
    assert env["display"]["title"] is None and env["display"]["pending"]["title"] is True


def test_placed_is_an_inert_audit_kind():
    from abstractmemory.engine_manifest import engine_manifest
    from abstractmemory.journal import ATTENTION_KINDS, AUDIT_KINDS

    assert "placed" in AUDIT_KINDS and "placed" not in ATTENTION_KINDS
    assert "placed" in engine_manifest()["vocabularies"]["event_kinds"]


# --------------------------------------------------------------------------- records_since_maintenance: fragmented


def _fragmented(system) -> Dict[str, Any]:
    from abstractmemory import records_since_maintenance

    return records_since_maintenance(system, scopes=SCOPES)["fragmented"]


def test_fragmented_share_of_an_empty_home_is_zero(home):
    assert _fragmented(home) == {"count": 0, "share": 0.0, "provisional": 0, "unvectored": 0, "pending": 0}


def test_fragmented_counts_provisional_unvectored_and_pending_over_live_records(home):
    v = _two_topics(home)                                            # 6 live records, community rows not counted
    _remember(home, "pl", "Fresh thoughts about alpha.")             # placed: provisional
    _remember(home, "nv", "novector alone")                          # no vector, unplaced
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        home.remember_many([MemoryRecordInput(kind="episode", title=None, digest="Fresh thoughts about beta.",
                                              pending=("title",))],
                           scope=SCOPE, owner_id=OWNER, idempotency_key="pe")   # pending, and placed
    home.close_record(v["alpha"][0], reason="wrong")                 # closed: no longer live
    assert _fragmented(home) == {"count": 4, "share": round(4 / 8, 6), "provisional": 2, "unvectored": 1,
                                 "pending": 1}


def test_fragmented_provisional_counts_only_placements_since_the_last_night(home):
    _two_topics(home)
    _remember(home, "before", "Fresh thoughts about alpha.")
    home.tasks.record_maintenance(SCOPES, kind="night", completed_at="2999-01-01T00:00:00.000000+00:00",
                                  seq=home.journal.current_seq())
    _remember(home, "after", "Fresh thoughts about beta.")
    got = _fragmented(home)
    assert (got["provisional"], got["count"], got["share"]) == (1, 1, round(1 / 8, 6))


# --------------------------------------------------------------------------- against the real sleep pass


TOPIC_DIM = 32


class _PassEmbedder:
    """A text naming `topic-<n>` lies near topic n's direction; `novector` fails the batch (vector-less)."""

    model = "pass-topics-32"

    def embed_texts(self, texts):
        import numpy as np

        out = []
        for text in texts:
            if "novector" in text:
                raise RuntimeError("embedder down")
            topic = next((int(w[6:].strip(".,")) for w in text.split() if w.startswith("topic-")
                          and w[6:].strip(".,").isdigit()), 99)
            center = np.random.default_rng(1000 + topic).standard_normal(TOPIC_DIM)
            noise = np.random.default_rng(int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)).standard_normal(
                TOPIC_DIM)
            v = center / np.linalg.norm(center) + 0.08 * noise
            out.append((v / np.linalg.norm(v)).tolist())
        return out


def _pass_author(kind, body, context):
    h = hashlib.sha1(body.encode("utf-8")).hexdigest()[:8]
    return {"title": f"Topic {h}", "summary": f"Memories about subject {h}.",
            "author": {"kind": "capability-model", "id": "summaries"},
            "reader": {"provider": "lmstudio", "model": "test-model", "thinking": False},
            "sources": [{"kind": "artifact", "artifact_id": f"call-{h}"}]}


@pytest.fixture(params=["memory", "sqlite"])
def lived(request, tmp_path):
    pytest.importorskip("numpy")
    emb = _PassEmbedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if request.param == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        else:
            path = tmp_path / "memory.sqlite3"
            store, journal = SQLiteTripleStore(path, embedder=emb), SQLiteJournal(path)
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=True)
    topics = {}
    for t in (1, 2, 3):
        recs = [MemoryRecordInput(kind="episode", title=f"Episode {t}.{i}", digest=f"We talked about topic-{t}, item {i}.",
                                  edges=(("continues", f"local:{i - 1}"),) if i else ())
                for i in range(10)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            topics[t] = system.remember_many(recs, scope=SCOPE, owner_id=OWNER, idempotency_key=f"t{t}")
    system.topics = topics
    yield system
    system.journal.close()
    system.store.close()


def _sleep(system):
    from abstractmemory.communities import communities_pass

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return communities_pass(system, scopes=[(SCOPE, OWNER)], owner_id=OWNER, author=_pass_author,
                                cancelled=lambda: False)


def test_the_real_pass_serves_through_the_read_and_places_at_formation(lived):
    from abstractmemory.communities import vector_space_id

    assert communities(lived, scopes=SCOPES, owner_id=OWNER)["first_sleep_pending"] is True
    receipt = _sleep(lived)
    assert receipt["version_seq"] is not None and receipt["communities"] == 3
    payload = communities(lived, scopes=SCOPES, owner_id=OWNER)
    assert set(payload) == {"version", "version_seq", "first_sleep_pending", "algorithm", "communities", "links"}
    assert (payload["version"], payload["version_seq"], payload["first_sleep_pending"], payload["algorithm"]) == (
        2, receipt["version_seq"], False, "louvain-warm-v1")
    shape = {"id", "key", "title", "summary", "pending", "verdict", "size", "kinds", "members", "provisional_ids",
             "cohesion", "layout", "centroid_stale", "facts"}
    by_topic = {}
    for c in payload["communities"]:
        assert set(c) == shape and set(c["layout"]) == {"xy", "radius", "seats"}
        assert set(c["facts"]) == {"span", "activity", "hub", "bridges", "paths", "changed_since_last_sleep"}
        assert c["key"].startswith("ex:community-") and c["id"] != c["key"] and c["title"] and c["summary"]
        assert c["centroid_stale"] is False and c["pending"] == [] and c["provisional_ids"] == []
        ids = {m["id"] for m in c["members"]}
        [t] = [t for t, rids in lived.topics.items() if set(rids) == ids]
        by_topic[t] = c
    assert ci._space_id(lived.store) == vector_space_id(lived.store)
    # A record formed after the sleep: provisional in topic 2's community, by its centroid.
    rid = _remember(lived, "later", "Again about topic-2, a new thought.")
    got = community_of(lived, rid)
    assert (got["community_key"], got["community_id"], got["provisional"], got["how"]) == (
        by_topic[2]["key"], by_topic[2]["id"], True, "centroid")
    lone = _remember(lived, "lone", "novector, linked", edges=[("mentions", lived.topics[3][0])])
    assert community_of(lived, lone)["community_key"] == by_topic[3]["key"]
    served = {c["key"]: c for c in communities(lived, scopes=SCOPES, owner_id=OWNER)["communities"]}
    assert served[by_topic[2]["key"]]["provisional_ids"] == [rid]
    assert served[by_topic[3]["key"]]["provisional_ids"] == [lone]
    # Replay: the version records project like any record, with no edge per member.
    bindings = [e["display"] for e in export_replay(lived.store, lived.journal, scope=SCOPE, owner_id=OWNER)
                if e["family"] == "binding" and e.get("display", {}).get("kind") == "community"]
    assert sorted(d["community_key"] for d in bindings) == sorted(served)
    assert all(d["version_seq"] == receipt["version_seq"] and "edges" not in d for d in bindings)
    # The next sleep confirms both placements: members now, nothing provisional.
    second = _sleep(lived)
    assert second["version_seq"] > receipt["version_seq"]
    confirmed = community_of(lived, rid)
    assert (confirmed["community_key"], confirmed["provisional"]) == (by_topic[2]["key"], False)
    after = {c["key"]: c for c in communities(lived, scopes=SCOPES, owner_id=OWNER)["communities"]}
    assert all(c["provisional_ids"] == [] for c in after.values())
    assert after[by_topic[2]["key"]]["facts"]["changed_since_last_sleep"]["added"] == 1
    assert after[by_topic[2]["key"]]["id"] != by_topic[2]["id"]
