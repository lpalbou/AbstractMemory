"""The membership reads (community_index.py): `community_keys_of` / `community_memberships_of`, what a host stamps on
every recalled record (the runtime's recall handles, backlog 0069).

- correctness: the same answer as `communities()` for every id (member, provisional, none), on the four substrate
  pairs, before and after a new version, across two handles on one SQLite file (another process), for another
  owner and for a scope subset; unknown ids, community record ids, an empty home, an unreadable version;
- the hot path: one `MAX(rowid)` statement on the store's connection per call and nothing on the journal's when no
  row was written; the journal read once per pair after a formation; no `_fold` unless a community row appeared;
  no file opened, stat'ed or locked from Python (counted over 200 calls, formations in between);
- the cost on synthetic SQLite homes of 2 000 and 20 000 records (54 topics, 50 ids per call): measured and printed
  (run with -s), median under 1 ms; `communities()` on the same homes printed beside it.

MUTATION LIST (scratch copy untracked/community-keys-of/mut, each mutant run against this file; all red, the source
restored byte-exact):
K1 the read never catches the index up once it is loaded (a later version is never seen);
K2 the placed events are read once per version and never again (a record formed after the first read is never
   provisional);
K3 the provisional flag is always false;
K4 the scope pairs and owner are ignored (another owner's topics answer);
K5 the version floor is ignored (a placement from before the current version still answers);
K6 the journal is read on every call;
K7 the read checks whether the journal shares the store's file on every call (`os.stat`);
K8 `FormationPlacement.committed` leaves the placed reads as they are (a read between a SQLite store's COMMIT and
   the off-file journal's events never sees them).
"""

from __future__ import annotations

import builtins
import io
import os
import statistics
import time
import warnings
from typing import Any, Dict, List, Optional, Sequence

import pytest

from abstractmemory import MemoryEvent, MemorySystem, SQLiteJournal, SQLiteTripleStore, TripleAssertion
from abstractmemory import community_index as ci
from abstractmemory.community_index import (
    CommunitySchemaError,
    communities,
    community_keys_of,
    community_memberships_of,
)

from test_community_placement import (  # noqa: E402  (shared fixtures of the placement suite)
    OWNER,
    SCOPE,
    SCOPES,
    Guard,
    _open,
    _open_two_sqlite_files,
    _remember,
    _two_topics,
    _write_version,
)

OTHER = "entity:other"


@pytest.fixture(params=["memory", "sqlite", "memory+sqlite-journal", "sqlite+sqlite-journal"])
def any_home(request, tmp_path):
    guard = Guard()
    system = (_open_two_sqlite_files(tmp_path, guard) if request.param == "sqlite+sqlite-journal"
              else _open(request.param, tmp_path, guard))
    system.guard = guard
    yield system
    system.journal.close()
    system.store.close()


def _expected(system, ids: Sequence[str], *, scopes=SCOPES, owner: str = OWNER) -> Dict[str, Optional[Dict[str, Any]]]:
    """What `communities()` says of each id: member, provisional, or none."""
    out: Dict[str, Optional[Dict[str, Any]]] = {rid: None for rid in ids}
    for c in communities(system, scopes=scopes, owner_id=owner)["communities"]:
        for m in c["members"]:
            if m["id"] in out:
                out[m["id"]] = {"key": c["key"], "provisional": False}
        for rid in c["provisional_ids"]:
            if rid in out and out[rid] is None:
                out[rid] = {"key": c["key"], "provisional": True}
    return out


def _agrees(system, ids: Sequence[str], *, scopes=SCOPES, owner: str = OWNER) -> Dict[str, Optional[Dict[str, Any]]]:
    got = community_memberships_of(system, ids, scopes=scopes, owner_id=owner)
    assert got == _expected(system, ids, scopes=scopes, owner=owner)
    assert community_keys_of(system, ids, scopes=scopes, owner_id=owner) == {
        rid: (m["key"] if m else None) for rid, m in got.items()}
    return got


def _mixed(system) -> Dict[str, Any]:
    """Two topics, three records placed since the version (centroid, centroid, neighbour), one unplaced."""
    v = _two_topics(system)
    v["new_a"] = _remember(system, "new-a", "Fresh thoughts about alpha.")
    v["new_b"] = _remember(system, "new-b", "Fresh thoughts about beta.")
    v["linked"] = _remember(system, "nv1", "novector text", edges=[("mentions", v["beta"][0])])
    v["alone"] = _remember(system, "nv2", "novector alone")
    return v


def _ids(v: Dict[str, Any]) -> List[str]:
    return [*v["alpha"], *v["beta"], v["new_a"], v["new_b"], v["linked"], v["alone"], "ex:episode-unknown",
            v["ids"]["k-alpha"]]


# --------------------------------------------------------------------------- correctness


def test_memberships_match_communities_on_every_substrate(any_home):
    v = _mixed(any_home)
    got = _agrees(any_home, _ids(v))
    assert got[v["alpha"][0]] == {"key": "k-alpha", "provisional": False}
    assert got[v["new_a"]] == {"key": "k-alpha", "provisional": True}
    assert got[v["new_b"]] == {"key": "k-beta", "provisional": True}
    assert got[v["linked"]] == {"key": "k-beta", "provisional": True}
    assert got[v["alone"]] is None and got["ex:episode-unknown"] is None
    assert got[v["ids"]["k-alpha"]] is None  # a community record is no member of a community
    keys = community_keys_of(any_home, [v["new_a"], "ex:episode-unknown"], scopes=SCOPES, owner_id=OWNER)
    assert keys == {v["new_a"]: "k-alpha", "ex:episode-unknown": None}


def test_a_record_formed_after_the_first_read_is_provisional(any_home):
    v = _two_topics(any_home)
    assert _agrees(any_home, v["alpha"])[v["alpha"][0]]["provisional"] is False
    later = _remember(any_home, "later", "Fresh thoughts about alpha.")
    assert _agrees(any_home, [later])[later] == {"key": "k-alpha", "provisional": True}


def test_a_new_version_is_caught_up(any_home):
    v1 = _mixed(any_home)
    _agrees(any_home, _ids(v1))  # the index is loaded on version 1
    g = [_remember(any_home, f"g{i}", f"Notes on gamma {i}.") for i in range(2)]
    v2 = _write_version(any_home, {"k-alpha": v1["alpha"] + [v1["new_a"]], "k-gamma": g}, previous=v1["ids"],
                        dissolve=["k-beta"])
    ids = _ids(v1) + g
    got = _agrees(any_home, ids)
    assert got[v1["new_a"]] == {"key": "k-alpha", "provisional": False}  # confirmed by the version
    assert all(got[b] is None for b in v1["beta"])  # dissolved: never the dead key
    assert got[v1["new_b"]] is None and got[v1["linked"]] is None  # placed in the dead key before the version
    assert got[g[0]] == {"key": "k-gamma", "provisional": False}
    after = _remember(any_home, "after", "Fresh thoughts about gamma.")
    assert _agrees(any_home, [after])[after] == {"key": "k-gamma", "provisional": True}
    assert v2["version_seq"] > v1["version_seq"]


def test_a_placement_from_before_the_current_version_no_longer_answers(any_home):
    v1 = _two_topics(any_home)
    drifted = _remember(any_home, "drifted", "Fresh thoughts about alpha.")
    assert _agrees(any_home, [drifted])[drifted]["provisional"] is True
    # The next version keeps k-alpha alive but leaves the record out: its placed event is older than the version.
    _write_version(any_home, {"k-alpha": v1["alpha"], "k-beta": v1["beta"]}, previous=v1["ids"])
    assert _agrees(any_home, [drifted])[drifted] is None


def test_another_owner_and_a_scope_subset(any_home):
    v = _mixed(any_home)
    ids = _ids(v)
    other_scopes = [("life", OTHER)]
    assert _agrees(any_home, ids, scopes=other_scopes, owner=OTHER) == {rid: None for rid in ids}
    # Pairs of another owner in the list are not this owner's: only (life, OWNER) holds the topics.
    assert _agrees(any_home, ids, scopes=[("diary", OWNER), ("life", OTHER)]) == {rid: None for rid in ids}
    assert _agrees(any_home, ids, scopes=[("LIFE ", OWNER)])[v["alpha"][0]]["key"] == "k-alpha"
    # Another owner's topic in the same home answers for that owner only.
    rec = _remember_as(any_home, OTHER, "o1", "Notes on alpha for another.")
    _write_version_as(any_home, OTHER, "k-other", [rec])
    both = ids + [rec]
    assert _agrees(any_home, both)[rec] is None
    theirs = _agrees(any_home, both, scopes=other_scopes, owner=OTHER)
    assert theirs[rec] == {"key": "k-other", "provisional": False}
    assert all(theirs[rid] is None for rid in ids)
    assert _agrees(any_home, both)[v["alpha"][0]] == {"key": "k-alpha", "provisional": False}


def _remember_as(system, owner: str, key: str, digest: str) -> str:
    from abstractmemory import MemoryRecordInput

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return system.remember_many([MemoryRecordInput(kind="episode", title=f"About {key}", digest=digest)],
                                    scope=SCOPE, owner_id=owner, idempotency_key=key)[0]


def _write_version_as(system, owner: str, key: str, members: Sequence[str]) -> None:
    vs = system.journal.current_seq() + 1
    attrs = {"literal": True, "record_kind": "community", "community_key": key,
             "members": [{"id": m, "via": "detected", "since_seq": vs} for m in members], "size": len(members),
             "kinds": {"episode": len(members)}, "cohesion": 0.5, "verdict": None, "title": f"Topic {key}",
             "layout": {"xy": [0.0, 0.0], "radius": 1.0, "seats": {}}, "links": [],
             "basis": {"version_seq": vs, "algorithm": "louvain-warm-v1", "moved_in": len(members), "moved_out": 0},
             "bookkeeping": True}
    system.store.add([TripleAssertion(subject=f"ex:community-{key}-{vs}", predicate="dcterms:abstract",
                                      object=f"Summary of {key}", scope=SCOPE, owner_id=owner, attributes=attrs)])


def test_an_empty_home_and_no_ids(any_home):
    rid = _remember(any_home, "x", "Notes on alpha.")
    assert _agrees(any_home, [rid, "ex:episode-unknown"]) == {rid: None, "ex:episode-unknown": None}
    assert community_keys_of(any_home, [], scopes=SCOPES, owner_id=OWNER) == {}
    _two_topics(any_home)
    assert community_memberships_of(any_home, [], scopes=SCOPES, owner_id=OWNER) == {}


def test_an_unreadable_version_raises_like_communities(any_home):
    a = [_remember(any_home, f"a{i}", f"Notes on alpha {i}.") for i in range(2)]
    v = _write_version(any_home, {"k-alpha": a})
    assert community_keys_of(any_home, a, scopes=SCOPES, owner_id=OWNER) == {a[0]: "k-alpha", a[1]: "k-alpha"}
    from abstractmemory import TripleQuery

    good = any_home.store.query(TripleQuery(assertion_ids=(v["aids"]["k-alpha"],), limit=1))[0].attributes
    any_home.store.add([TripleAssertion(subject="ex:community-broken", predicate="dcterms:abstract", object="x",
                                        scope=SCOPE, owner_id=OWNER,
                                        attributes={k: val for k, val in good.items() if k != "community_key"})])
    with pytest.raises(CommunitySchemaError, match="community_key"):
        communities(any_home, scopes=SCOPES, owner_id=OWNER)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # the index's own #FALLBACK line at its reload
        with pytest.raises(CommunitySchemaError, match="community_key"):
            community_keys_of(any_home, a, scopes=SCOPES, owner_id=OWNER)


def test_another_handle_on_the_same_file_is_caught_up(tmp_path):
    """Two handles on one SQLite home (two processes): the reader's index follows the writer's version and
    placements."""
    reader, writer = _open("sqlite", tmp_path, Guard()), _open("sqlite", tmp_path, Guard())
    try:
        v1 = _two_topics(writer)
        _agrees(reader, v1["alpha"])
        placed = _remember(writer, "w1", "Fresh thoughts about beta.")
        assert _agrees(reader, [placed])[placed] == {"key": "k-beta", "provisional": True}
        g = [_remember(writer, f"g{i}", f"Notes on gamma {i}.") for i in range(2)]
        _write_version(writer, {"k-gamma": g, "k-beta": v1["beta"] + [placed]}, previous=v1["ids"],
                       dissolve=["k-alpha"])
        got = _agrees(reader, [*v1["alpha"], placed, *g])
        assert got[placed] == {"key": "k-beta", "provisional": False}
        assert all(got[a] is None for a in v1["alpha"]) and got[g[1]]["key"] == "k-gamma"
    finally:
        for system in (writer, reader):
            system.journal.close()
            system.store.close()


def test_a_read_between_the_store_commit_and_the_off_file_events_sees_them_next(tmp_path, monkeypatch):
    """A SQLite store with its journal in another file gets the placed events after the store's COMMIT; a read in
    that window sees the new rows and no event yet, and the next read must not miss them."""
    system = _open_two_sqlite_files(tmp_path, Guard())
    try:
        _two_topics(system)
        community_keys_of(system, [], scopes=SCOPES, owner_id=OWNER)
        real = ci.FormationPlacement.place
        early: List[Dict[str, Any]] = []

        def place(self, *, cur=None, inserted=None):
            if cur is None:  # after the store's COMMIT, before the events
                early.append(community_memberships_of(system, [p.record_id for p in self.records], scopes=SCOPES,
                                                      owner_id=OWNER))
            return real(self, cur=cur, inserted=inserted)

        monkeypatch.setattr(ci.FormationPlacement, "place", place)
        rid = _remember(system, "window", "Fresh thoughts about alpha.")
        assert early == [{rid: None}]
        assert _agrees(system, [rid])[rid] == {"key": "k-alpha", "provisional": True}
    finally:
        system.journal.close()
        system.store.close()


# --------------------------------------------------------------------------- the hot path


def test_the_hot_path_is_one_store_statement_and_no_journal_read(tmp_path, monkeypatch):
    system = _open("sqlite", tmp_path, Guard())
    try:
        v = _mixed(system)
        ids = _ids(v)
        community_keys_of(system, ids, scopes=SCOPES, owner_id=OWNER)  # warm: loaded, placements read
        folds: List[int] = []
        real_fold = ci._fold
        monkeypatch.setattr(ci, "_fold", lambda *a, **k: folds.append(1) or real_fold(*a, **k))
        store_sql: List[str] = []
        journal_sql: List[str] = []
        system.store._conn.set_trace_callback(store_sql.append)
        system.journal._conn.set_trace_callback(journal_sql.append)
        for _ in range(10):
            community_keys_of(system, ids, scopes=SCOPES, owner_id=OWNER)
        assert store_sql == [f"SELECT COALESCE(MAX(rowid), 0) FROM {system.store._table}"] * 10
        assert journal_sql == [] and folds == []
        # A formation moves the mark: the next read fetches the placed events once (per pair), the one after none.
        system.store._conn.set_trace_callback(None)
        system.journal._conn.set_trace_callback(None)
        later = _remember(system, "later", "Fresh thoughts about beta.")
        system.store._conn.set_trace_callback(store_sql.append)
        system.journal._conn.set_trace_callback(journal_sql.append)
        journal_sql.clear()
        assert community_keys_of(system, [later], scopes=SCOPES, owner_id=OWNER) == {later: "k-beta"}
        assert len(journal_sql) == 2 * len(SCOPES)  # current_seq + the pair's placed events, per pair
        journal_sql.clear()
        community_keys_of(system, [later], scopes=SCOPES, owner_id=OWNER)
        assert journal_sql == [] and folds == []
    finally:
        system.store._conn.set_trace_callback(None)
        system.journal._conn.set_trace_callback(None)
        system.journal.close()
        system.store.close()


@pytest.fixture(params=["memory", "sqlite", "memory+sqlite-journal", "sqlite+sqlite-journal"])
def counted_home(request, tmp_path):
    guard = Guard()
    system = (_open_two_sqlite_files(tmp_path, guard) if request.param == "sqlite+sqlite-journal"
              else _open(request.param, tmp_path, guard))
    yield system
    system.journal.close()
    system.store.close()


def test_two_hundred_reads_open_stat_and_lock_no_file(counted_home, monkeypatch):
    """The operator's rule (no hidden per-call cost): the read opens, stats and locks no file from Python, on the hot
    path and on the catch-up after a formation (formations run between reads, uncounted)."""
    import fcntl

    v = _mixed(counted_home)
    ids = _ids(v)
    calls: List[str] = []
    counting = [False]

    def counted(name, real):
        def wrapper(*a, **k):
            if counting[0]:
                calls.append(name)
            return real(*a, **k)
        return wrapper

    for module, name in ((builtins, "open"), (io, "open"), (os, "open"), (os, "stat"), (os, "lstat"),
                         (os, "fstat"), (fcntl, "flock"), (fcntl, "lockf"), (fcntl, "fcntl")):
        monkeypatch.setattr(module, name, counted(f"{module.__name__}.{name}", getattr(module, name)))
    for i in range(200):
        if i % 50 == 25:
            _remember(counted_home, f"between{i}", f"Fresh thoughts about alpha {i}.")
        counting[0] = True
        try:
            community_memberships_of(counted_home, ids, scopes=SCOPES, owner_id=OWNER)
        finally:
            counting[0] = False
    assert calls == []
    # The check is live: the same patch counts a stat from this process.
    counting[0] = True
    os.stat(str(os.getcwd()))
    counting[0] = False
    assert calls == ["os.stat"]


# --------------------------------------------------------------------------- measured cost (synthetic SQLite homes)


TOPICS = 54
PER_CALL = 50


def _synthetic(tmp_path, records: int):
    """A SQLite home (store and journal in one file) of `records` digest rows: 54 topics over all but the last 500
    records, those 500 placed since the version."""
    path = tmp_path / f"home-{records}.sqlite3"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        store, journal = SQLiteTripleStore(path), SQLiteJournal(path)
        system = MemorySystem(store=store, journal=journal, task_queue=True)
    gids = [f"ex:episode-{i:06d}" for i in range(records)]
    store.add([TripleAssertion(subject=g, predicate="dcterms:abstract", object=f"Note {i}.", scope=SCOPE,
                               owner_id=OWNER, attributes={"record_kind": "episode", "title": f"Note {i}"})
               for i, g in enumerate(gids)])
    placed, members = gids[-500:], gids[:-500]
    vs = journal.current_seq()
    groups = {f"ex:community-{t:012x}": members[t::TOPICS] for t in range(TOPICS)}
    store.add([TripleAssertion(
        subject=f"ex:community-rec-{t}", predicate="dcterms:abstract", object=f"Summary {t}", scope=SCOPE,
        owner_id=OWNER, attributes={
            "literal": True, "record_kind": "community", "community_key": key, "title": f"Topic {t}",
            "members": [{"id": m, "via": "detected", "since_seq": vs} for m in group], "size": len(group),
            "kinds": {"episode": len(group)}, "cohesion": 0.5, "verdict": None, "links": [],
            "layout": {"xy": [float(t), 0.0], "radius": 1.0, "seats": {}},
            "basis": {"version_seq": vs, "algorithm": "louvain-warm-v1", "moved_in": len(group), "moved_out": 0},
            "bookkeeping": True})
        for t, (key, group) in enumerate(sorted(groups.items()))])
    keys = sorted(groups)
    journal.append_events([MemoryEvent(kind="placed", scope=SCOPE, owner_id=OWNER, record_id=g, weight=0.0,
                                       actor="system", provenance={"community_key": keys[i % TOPICS],
                                                                   "how": "centroid", "provisional": True})
                           for i, g in enumerate(placed)])
    step = max(1, len(members) // 40)
    ids = members[::step][:40] + placed[:5] + [f"ex:episode-unknown-{i}" for i in range(5)]
    assert len(ids) == PER_CALL
    return system, ids


def _median_ms(fn, n: int = 200) -> float:
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return statistics.median(times) * 1000.0


@pytest.mark.parametrize("records", [2_000, 20_000])
def test_measured_cost_for_fifty_ids(tmp_path, records):
    system, ids = _synthetic(tmp_path, records)
    try:
        t0 = time.perf_counter()
        got = community_memberships_of(system, ids, scopes=SCOPES, owner_id=OWNER)
        cold_ms = (time.perf_counter() - t0) * 1000.0
        assert sum(1 for m in got.values() if m and not m["provisional"]) == 40
        assert sum(1 for m in got.values() if m and m["provisional"]) == 5
        assert got == _expected(system, ids)
        hot_ms = _median_ms(lambda: community_keys_of(system, ids, scopes=SCOPES, owner_id=OWNER))
        topics_ms = _median_ms(lambda: communities(system, scopes=SCOPES, owner_id=OWNER), n=5)
        print(f"\n[community_keys_of] {records} records, {TOPICS} topics, {PER_CALL} ids: hot median "
              f"{hot_ms * 1000.0:.1f} us per call; first call (index load) {cold_ms:.1f} ms; communities() "
              f"{topics_ms:.1f} ms")
        assert hot_ms < 1.0  # the target; measured ~0.03-0.05 ms on an M-series laptop
    finally:
        system.journal.close()
        system.store.close()
