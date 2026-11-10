"""Memory-owned communities (COMMUNITIES-DESIGN.md §1 + Fable deltas D1/D2/D6): the pass's invariants on both
substrate pairs.

Covered: I1 every placeable record in exactly one current community (vector-less records attached by their engraved
neighbours, the rest reported `unplaced`; those whose every relation names a closed record also `unplaced_closed`); `written_amid` never drives detection; `detect_kinds` attaches the other
kinds by nearest centroid; stable keys across a rerun with 5 % growth; an unchanged pass writes nothing; a new
version is a NEW record id with the same `community_key`, `refines` -> previous, previous closed `supersede`, its
live tasks superseded, a dissolved community closed `retract`; ONE transaction per version (one guard call; a refused
guard leaves no row, binding, closure or task); `cancelled()` -> nothing written; I3 determinism; I5 no title
without an author (author None -> pending + live tasks; no task queue -> refused); I10 seats inside circles, circles
apart; I13 budget -> the rest pending, the version still written; the stable briefing sample; sibling-title collision
-> pending with one feedback line; the `no_common_subject` verdict; the title carried while Jaccard >= 0.8; small
homes (empty, 1, 2 records, no vector at all).

MUTATION LIST (scratch copy untracked/communities/mut, runner untracked/communities/mutate.py, each mutant run
against this file; all red, source restored byte-exact):
M1 drop the vector-less attach step; M2 let written_amid drive detection; M3 mint a fresh key for every group
(matching off); M4 ignore `cancelled`; M5 one transaction per community; M6 sample ordered by member id only (not
keyed on the community key); M7 store a title cut from the first member title when the author fails; M8 no
relaxation (circles overlap); M9 no collision check; M10 budget ignored; M13 `unplaced_closed` = every unplaced
vector-less record (the closed-only rule dropped); M14 a relation to an open record does not count against it.
Fable review M1 (2026-11-10, scratch copy untracked/review-m1-wip/tree): m2 the connectivity refinement removed (a
disconnected community stays whole: I2); m4 KEY_MATCH_FLOOR = 0 (any overlap continues a key); L1 an unchanged
community keeps its stored links to a dissolved key. All red.
"""

from __future__ import annotations

import hashlib
import warnings
from typing import Any, Dict, List, Optional

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import (  # noqa: E402
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
)
from abstractmemory import communities as C  # noqa: E402
from abstractmemory.store import TripleQuery  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
DIM = 32
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
LIVE = ("pending", "deferred", "leased")


def _center(t: int) -> Any:
    v = np.random.default_rng(1000 + t).standard_normal(DIM)
    return v / np.linalg.norm(v)


class Embedder:
    """Vectors by topic: a text naming `topic-<n>` lies near topic n's direction (cosine ~0.85 inside a topic,
    ~0 across); a text naming `novec` fails the batch (the store degrades it to vector-less)."""

    model = "fake-topic-32"

    def __init__(self) -> None:
        self.calls = 0
        self.down = False

    def embed_texts(self, texts):
        self.calls += 1
        out = []
        for text in texts:
            if self.down or "novec" in text:
                raise RuntimeError("embedder unreachable")
            topic = next((int(w.split("-", 1)[1].strip(".,:")) for w in text.split()
                          if w.startswith("topic-") and w.split("-", 1)[1].strip(".,:").isdigit()), 99)
            noise = np.random.default_rng(int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)).standard_normal(DIM)
            v = _center(topic) + 0.08 * noise
            out.append((v / np.linalg.norm(v)).tolist())
        return out


class Guard:
    def __init__(self, refuse: Optional[str] = None) -> None:
        self.calls: List[str] = []
        self.refuse = refuse

    def __call__(self, where: str) -> None:
        self.calls.append(where)
        if self.refuse is not None and where == self.refuse:
            raise RuntimeError(f"stopped by the operator ({where})")


def _open(kind: str, tmp_path, *, guard=None, task_queue: bool = True, name: str = "memory.sqlite3"):
    emb = Embedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if kind == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        else:
            path = tmp_path / name
            store, journal = SQLiteTripleStore(path, embedder=emb), SQLiteJournal(path)
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=task_queue,
                              commit_guard=guard)
    system.kind = kind
    system.emb = emb
    return system


@pytest.fixture(params=["memory", "sqlite"])
def kind(request):
    return request.param


@pytest.fixture
def home(kind, tmp_path):
    system = _open(kind, tmp_path)
    yield system
    system.journal.close()
    system.store.close()


def _form(system, records: List[MemoryRecordInput], key: str) -> List[str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return system.remember_many(records, scope=SCOPE, owner_id=OWNER, idempotency_key=key)


def _topic(system, t: int, n: int, *, start: int = 0, tag: str = "") -> List[str]:
    """n episodes about topic t, chained by `continues`."""
    recs = []
    for i in range(start, start + n):
        edges = (("continues", f"local:{i - start - 1}"),) if i > start else ()
        recs.append(MemoryRecordInput(kind="episode", title=f"Episode {t}.{i}{tag}",
                                      digest=f"We talked about topic-{t} again, item {i}{tag}.", edges=edges))
    return _form(system, recs, f"topic-{t}-{start}-{n}{tag}")


def author_fn(log: Optional[List[str]] = None, *, verdict: Optional[str] = None, title: Optional[str] = None):
    def author(kind: str, body: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if log is not None:
            log.append(body)
        h = hashlib.sha1(body.encode("utf-8")).hexdigest()[:8]
        out = {"title": title or f"Topic {h}", "summary": f"Memories about subject {h}.", "author": MODEL,
               "reader": READER, "sources": [{"kind": "artifact", "artifact_id": f"call-{h}"}]}
        if verdict is not None:
            out["verdict"] = verdict
        return out
    return author


_DEFAULT = object()


def _pass(system, author: Any = _DEFAULT, **kw) -> Dict[str, Any]:
    kw.setdefault("cancelled", lambda: False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return C.communities_pass(system, scopes=SCOPES, owner_id=OWNER,
                                  author=author_fn() if author is _DEFAULT else author, **kw)


def _current(system) -> List[C.PreviousCommunity]:
    return C.community_records(system, scopes=SCOPES, owner_id=OWNER)


def _membership(system) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for c in _current(system):
        for m in c.members:
            assert m not in out, f"{m} is in two current communities"
            out[m] = c.key
    return out


def _all_rows(system):
    return system.store.query(TripleQuery(limit=0))


def _community_rows(system):
    return [a for a in _all_rows(system) if (a.attributes or {}).get("record_kind") == "community"]


def _three_topics(system, n: int = 12) -> Dict[int, List[str]]:
    return {t: _topic(system, t, n) for t in (1, 2, 3)}


# ----------------------------------------------------------------------------------------------- I1 + detection


def test_every_record_is_in_exactly_one_community(home) -> None:
    topics = _three_topics(home)
    # vector-less records: a summary over topic 2 (placed by its edges), one with no edge at all (unplaced)
    [s] = _form(home, [MemoryRecordInput(kind="summary", title="A novec summary", digest="novec summary of two",
                                         edges=tuple(("summarizes", r) for r in topics[2][:4]))], "s-novec")
    [lone] = _form(home, [MemoryRecordInput(kind="episode", title="Lonely novec", digest="novec alone")], "lone")
    r = _pass(home)
    assert r["version_seq"] is not None and r["communities"] == 3 and r["written"] == 3
    member = _membership(home)
    for ids in topics.values():
        assert len({member[i] for i in ids}) == 1, "a topic is one community"
    assert len({member[ids[0]] for ids in topics.values()}) == 3
    assert member[s] == member[topics[2][0]]
    [c2] = [c for c in _current(home) if s in c.members]
    assert c2.members[s]["via"] == "attached"
    assert lone not in member and r["unplaced"] == [lone] and r["unplaced_count"] == 1
    assert sorted(r["unvectored"]) == sorted([s, lone]) and r["unvectored_count"] == 2  # I12: never silently 0
    assert r["attached"] == 1 and r["detected"] == 36


def test_unplaced_summaries_of_closed_records_are_reported_apart(home) -> None:
    """The summary of episodes consolidated away has no vector and only closed neighbours: no edge can place it.
    It stays in `unplaced` and `unvectored` and is named in `unplaced_closed` (the fragmentation share leaves it
    out). An unplaced record with any relation to an open record is not."""
    _three_topics(home)
    old = _topic(home, 1, 3, start=100, tag="-old")
    [lone] = _form(home, [MemoryRecordInput(kind="episode", title="Lonely novec", digest="novec alone")], "lone")
    [s] = _form(home, [MemoryRecordInput(kind="summary", title="Old days", digest="novec summary of the old days",
                                         edges=tuple(("summarizes", r) for r in old))], "s-closed")
    [u] = _form(home, [MemoryRecordInput(kind="summary", title="Mixed", digest="novec summary, one live source",
                                         edges=(("summarizes", old[0]), ("summarizes", lone)))], "s-mixed")
    for rid in old:
        home.close_record(rid, reason="test: consolidated away")
    r = _pass(home)
    assert r["unplaced"] == sorted([s, lone, u]) and r["unplaced_count"] == 3
    assert r["unplaced_closed"] == [s]
    assert set(r["unplaced_closed"]) <= set(r["unvectored"]) and r["unvectored_count"] == 3
    assert s not in _membership(home)
    again = _pass(home)
    assert again["skipped"].startswith("unchanged") and again["unplaced_closed"] == [s]


def test_written_amid_never_drives_detection(home) -> None:
    topics = _three_topics(home)
    # a small separate subject (5 records), every one of them `written_amid` five records of topic 1
    small = _form(home, [MemoryRecordInput(kind="diary", title=f"Entry {i}", digest=f"On topic-7, note {i}.",
                                           provenance={"source": "owner-direct"},
                                           edges=tuple(("written_amid", x) for x in topics[1][i:i + 5]))
                         for i in range(5)], "diary-amid")
    r = _pass(home)
    member = _membership(home)
    assert len({member[x] for x in small}) == 1
    assert member[small[0]] != member[topics[1][0]], "written_amid pulled the entries into topic 1"
    assert {c.members[small[0]]["via"] for c in _current(home) if small[0] in c.members} == {"detected"}
    assert r["communities"] == 4


def test_detect_kinds_attaches_the_other_kinds_by_centroid(home) -> None:
    topics = _three_topics(home)
    diary = _form(home, [MemoryRecordInput(kind="diary", title=f"Entry {i}", digest=f"About topic-3 today {i}.",
                                           provenance={"source": "owner-direct"}) for i in range(3)], "d3")
    _pass(home, detect_kinds=("episode",))
    member = _membership(home)
    [c3] = [c for c in _current(home) if topics[3][0] in c.members]
    for d in diary:
        assert member[d] == c3.key and c3.members[d]["via"] == "attached"


# ----------------------------------------------------------------------------------------------- versions, keys


def test_an_unchanged_pass_writes_nothing(home) -> None:
    _three_topics(home)
    _pass(home)
    seq = home.journal.current_seq()
    rows = len(_all_rows(home))
    r = _pass(home)
    assert r["version_seq"] is None and r["written"] == 0 and r["unchanged"] == 3
    assert r["skipped"].startswith("unchanged")
    assert home.journal.current_seq() == seq and len(_all_rows(home)) == rows


def test_a_new_version_is_a_new_record_with_the_same_key(home) -> None:
    topics = _three_topics(home)
    _pass(home)
    before = {c.key: c for c in _current(home)}
    key1 = next(c.key for c in before.values() if topics[1][0] in c.members)
    old = before[key1]
    _topic(home, 1, 4, start=12)  # topic 1 grows by a third: its title goes stale too
    r = _pass(home)
    after = {c.key: c for c in _current(home)}
    assert set(after) == set(before) and r["kept"] == 3 and r["new"] == 0 and r["written"] == 1
    new = after[key1]
    assert new.record_id != old.record_id and new.record_id.startswith("ex:community-")
    assert new.attrs["basis"]["previous_id"] == old.record_id
    refines = home.store.query(TripleQuery(subject=new.record_id, predicate="refines", limit=0))
    assert [e.object for e in refines] == [old.record_id]
    closed = {c.assertion_id: c for c in home.journal.closures(limit=0)}
    assert closed[old.assertion_id].kind == "supersede"
    assert closed[old.assertion_id].replacement_ids == (new.record_id,)
    since = {m: v["since_seq"] for m, v in new.members.items()}
    assert since[topics[1][0]] == old.members[topics[1][0]]["since_seq"]  # carried join order
    assert min(since[m] for m in new.members if m not in old.members) == new.attrs["basis"]["version_seq"]


def test_stable_keys_across_five_percent_growth(home) -> None:
    for t in range(1, 7):
        _topic(home, t, 10)
    _pass(home)
    before = _membership(home)
    keys = set(before.values())
    _topic(home, 2, 2, start=10)
    _topic(home, 5, 1, start=10)
    _pass(home)
    after = _membership(home)
    kept = len(keys & set(after.values())) / len(keys)
    same = sum(1 for m, k in before.items() if after.get(m) == k) / len(before)
    print(f"\n5% growth: keys kept {kept:.0%}, memberships kept {same:.0%}")
    assert kept >= 0.6 and same >= 0.8


def test_a_dissolved_community_is_retracted(home) -> None:
    topics = _three_topics(home)
    _pass(home)
    key3 = _membership(home)[topics[3][0]]
    [old3] = [c for c in _current(home) if c.key == key3]
    for rid in topics[3]:
        home.close_record(rid, reason="test: forget topic 3")
    r = _pass(home)
    assert r["dissolved"] == 1 and r["ids"]["dissolved"] == [key3]
    assert key3 not in {c.key for c in _current(home)}
    assert {c.kind for c in home.journal.closures(limit=0) if c.assertion_id == old3.assertion_id} == {"retract"}


def test_a_disconnected_community_is_split_into_its_components(home) -> None:
    """I2 (Fable review M1 #2): last night's version held two topics as ONE community (the bridge that joined them is
    gone). The warm start seeds both halves with one label and no local move leaves it (every neighbour of every node
    is inside), so only the connectivity refinement splits it: one community per connected component."""
    t1, t2 = _topic(home, 1, 10), _topic(home, 2, 10)
    g = C.read_community_graph(home, scopes=SCOPES, owner_id=OWNER)
    both = t1 + t2
    g.previous = [C.PreviousCommunity(key="ex:community-bridged",
                                      members={m: {"id": m, "via": "detected", "since_seq": 0} for m in both},
                                      centroid=C._unit_mean(np, g.vectors[[g.vindex[m] for m in both]]))]
    det = C.detect_communities(g)
    assert sorted(sorted(grp) for grp in det.groups) == sorted([sorted(t1), sorted(t2)])
    assert all(set(grp.values()) == {"detected"} for grp in det.groups) and det.unplaced == []


def test_refine_splits_a_community_into_its_connected_components() -> None:
    """I2 on the refinement alone: two 6-cliques labelled as one community come back as two groups."""
    adj = [{} for _ in range(12)]
    for base in (0, 6):
        for i in range(base, base + 6):
            for j in range(base, base + 6):
                if i != j:
                    adj[i][j] = 1.0
    groups, orphans, _split = C._refine([0] * 12, adj)
    assert groups == [list(range(6)), list(range(6, 12))] and orphans == []


def test_the_jaccard_floor_is_where_a_key_stops_continuing() -> None:
    """KEY_MATCH_FLOOR (Fable review M1 #3): a group overlapping the previous version at Jaccard 0.5 continues its
    key; at 1/3 it gets a fresh key and the previous one is left unmatched (dissolved)."""
    old = C.PreviousCommunity(key="ex:community-old",
                              members={f"m{i}": {"id": f"m{i}", "via": "detected", "since_seq": 0} for i in range(6)})
    at_floor = {**{f"m{i}": "detected" for i in range(4)}, "n0": "detected", "n1": "detected"}  # 4 / 8
    below = {**{f"m{i}": "detected" for i in range(3)}, "n0": "detected", "n1": "detected", "n2": "detected"}  # 3 / 9
    [(key, prev, j)] = C.match_keys([at_floor], [old])
    assert key == old.key and prev is old and j == 0.5 == C.KEY_MATCH_FLOOR
    [(key, prev, j)] = C.match_keys([below], [old])
    assert prev is None and j == 0.0 and key.startswith(C.KEY_PREFIX) and key != old.key


def test_a_group_under_the_jaccard_floor_gets_a_fresh_key_and_the_old_one_dissolves(home) -> None:
    """The floor on the pass: 9 of topic 3's 12 records forgotten and 12 new ones formed; tonight's topic-3 group
    (3 old + 12 new) overlaps the old version at Jaccard 3/24 < 0.5: a fresh key, the old version retracted, the
    other two keys kept."""
    topics = _three_topics(home)
    _pass(home)
    before = _membership(home)
    key3 = before[topics[3][0]]
    for rid in topics[3][3:]:
        home.close_record(rid, reason="test: most of topic 3 forgotten")
    fresh3 = _topic(home, 3, 12, start=12)
    r = _pass(home)
    after = _membership(home)
    [new3] = {after[m] for m in fresh3 + topics[3][:3]}
    assert 3 / (15 + 12 - 3) < C.KEY_MATCH_FLOOR
    assert new3 != key3 and r["ids"]["new"] == [new3]
    assert r["dissolved"] == 1 and r["ids"]["dissolved"] == [key3]
    assert after[topics[1][0]] == before[topics[1][0]] and after[topics[2][0]] == before[topics[2][0]]
    [old3] = [a for a in _community_rows(home) if (a.attributes or {}).get("community_key") == key3]
    assert {c.kind for c in home.journal.closures(limit=0) if c.assertion_id == old3.assertion_id} == {"retract"}


def test_a_dissolved_neighbour_leaves_no_stored_link(home) -> None:
    """An unchanged community linked to one that dissolves forms again (its title carried, no author call), so no
    stored `links` entry outlives the key it names; the pass after writes nothing."""
    topics = _three_topics(home)
    [note] = _form(home, [MemoryRecordInput(kind="observation", title="A note",
                                            digest="Still on topic-1, and a nod aside.",
                                            edges=(("mentions", topics[3][0]),))], "note")
    _pass(home)
    member = _membership(home)
    key1, key3 = member[topics[1][0]], member[topics[3][0]]
    assert member[note] == key1
    [c1] = [c for c in _current(home) if c.key == key1]
    assert [link["to"] for link in c1.attrs["links"]] == [key3]
    for rid in topics[3]:
        home.close_record(rid, reason="test: forget topic 3")
    log: List[str] = []
    r = _pass(home, author=author_fn(log))
    assert r["ids"]["dissolved"] == [key3]
    [c1b] = [c for c in _current(home) if c.key == key1]
    assert c1b.record_id != c1.record_id and c1b.attrs["links"] == []
    assert set(c1b.members) == set(c1.members) and c1b.title == c1.title and log == []  # carried, no author call
    assert _pass(home)["written"] == 0


# ----------------------------------------------------------------------------------------------- one transaction


def test_one_version_is_one_guarded_transaction(kind, tmp_path) -> None:
    guard = Guard()
    system = _open(kind, tmp_path, guard=guard)
    topics = _three_topics(system)
    del guard.calls[:]
    _pass(system)
    assert guard.calls == ["communities.communities_pass"]
    # a second version (one community revised, its predecessor closed): still ONE commit point
    _topic(system, 1, 6, start=12)
    del guard.calls[:]
    r = _pass(system)
    assert r["written"] >= 1 and guard.calls == ["communities.communities_pass"]
    assert topics


def test_a_refused_version_leaves_nothing(kind, tmp_path) -> None:
    guard = Guard()
    system = _open(kind, tmp_path, guard=guard)
    _three_topics(system)
    _pass(system, author=author_fn())
    _topic(system, 1, 6, start=12)
    _form(system, [MemoryRecordInput(kind="episode", title="x", digest="novec x")], "x")  # no-op for the version
    before_rows = sorted(a.assertion_id for a in _all_rows(system))
    before_bind = len(system.journal.bindings(fold=False))
    before_close = len(system.journal.closures(limit=0))
    before_tasks = sorted(t["task_id"] + t["status"] for t in system.tasks.tasks())
    seq = system.journal.current_seq()
    current = {c.record_id for c in _current(system)}
    guard.refuse = "communities.communities_pass"
    with pytest.raises(RuntimeError, match="stopped by the operator"):
        _pass(system, author=None)  # pending: tasks would be queued in the same transaction
    assert sorted(a.assertion_id for a in _all_rows(system)) == before_rows
    assert len(system.journal.bindings(fold=False)) == before_bind
    assert len(system.journal.closures(limit=0)) == before_close
    assert sorted(t["task_id"] + t["status"] for t in system.tasks.tasks()) == before_tasks
    assert system.journal.current_seq() == seq
    assert {c.record_id for c in _current(system)} == current  # the previous version is still served


def test_a_cancelled_pass_writes_nothing(home) -> None:
    _three_topics(home)
    seq = home.journal.current_seq()
    rows = len(_all_rows(home))
    r = _pass(home, cancelled=lambda: True)
    assert r["cancelled"] and r["version_seq"] is None and r["written"] == 0
    assert r["authoring"] == {"authored": [], "failures": []}
    assert home.journal.current_seq() == seq and len(_all_rows(home)) == rows
    assert not _community_rows(home) and not home.tasks.tasks()


def test_cancelled_is_asked_once_immediately_before_the_write(home) -> None:
    _three_topics(home)
    asked: List[int] = []

    def cancelled() -> bool:
        asked.append(len(_community_rows(home)))
        return False

    _pass(home, cancelled=cancelled)
    assert asked == [0] and len(_community_rows(home)) == 3


# ----------------------------------------------------------------------------------------------- determinism, layout


def test_the_same_home_gives_the_same_communities(kind, tmp_path) -> None:
    def build(name):
        s = _open(kind, tmp_path, name=name)
        for t in range(1, 5):
            _topic(s, t, 9)
        _pass(s)
        return s

    a, b = build("a.sqlite3"), build("b.sqlite3")
    strip = ("understanding", "title_provenance")

    def view(s):
        return sorted((c.key, sorted(c.members.items()), {k: v for k, v in c.attrs.items() if k not in strip})
                      for c in _current(s))

    assert view(a) == view(b)


def test_seats_sit_inside_their_circle_and_circles_never_overlap(home) -> None:
    for t in range(1, 7):
        _topic(home, t, 4 + 2 * t)
    _form(home, [MemoryRecordInput(kind="summary", title=f"S{i}", digest=f"novec summary {i}",
                                   edges=(("summarizes", _topic(home, 1, 1, start=40 + i)[0]),)) for i in range(2)],
          "seat-novec")
    _pass(home)
    cur = _current(home)
    for c in cur:
        lay = c.attrs["layout"]
        assert set(lay["seats"]) == set(c.members)
        for seat in lay["seats"].values():
            assert math_hypot(seat) <= lay["radius"] + 1e-6
    for i, a in enumerate(cur):
        for b in cur[i + 1:]:
            d = math_hypot([a.attrs["layout"]["xy"][0] - b.attrs["layout"]["xy"][0],
                            a.attrs["layout"]["xy"][1] - b.attrs["layout"]["xy"][1]])
            assert d >= a.attrs["layout"]["radius"] + b.attrs["layout"]["radius"] - 1e-6


def math_hypot(v) -> float:
    return float((v[0] ** 2 + v[1] ** 2) ** 0.5)


# ----------------------------------------------------------------------------------------------- authoring


def test_no_title_without_an_author(home) -> None:
    _three_topics(home)
    r = _pass(home, author=None)
    assert r["pending"] == 3 and r["authored"] == 0 and r["failed"] == 3
    assert {f["reason"] for f in r["authoring"]["failures"]} == {"no_author_supplied"}
    for c in _current(home):
        assert c.title is None and c.attrs["pending"]["title"] and c.attrs["pending"]["summary"]
        assert c.attrs["digest_method"] == C.BRIEFING_METHOD
        live = {t["kind"] for t in home.tasks.tasks(target_id=c.record_id) if t["status"] in LIVE}
        assert live == {"title.author", "digest.author"}
        assert c.digest.startswith("A topic of this memory")  # the briefing, never a member's title


def test_a_home_without_a_task_queue_is_refused(kind, tmp_path) -> None:
    system = _open(kind, tmp_path, task_queue=False)
    _three_topics(system)
    with pytest.raises(ValueError, match="task_queue=True"):
        _pass(system)


def test_authored_titles_and_the_title_basis(home) -> None:
    log: List[str] = []
    _three_topics(home)
    r = _pass(home, author=author_fn(log))
    assert r["authored"] == 3 and r["pending"] == 0 and len(log) == 3
    titles = {c.title for c in _current(home)}
    assert len(titles) == 3
    for c in _current(home):
        assert c.attrs["title_provenance"]["author"] == MODEL
        assert c.attrs["understanding"]["field"] == "digest"
        basis = c.attrs["title_basis"]
        assert basis["prompt_version"] == C.PROMPT_VERSION and set(basis["members"]) == set(c.members)
        assert set(basis["sample_ids"]) <= set(c.members)
        assert not home.tasks.tasks(target_id=c.record_id)
    # the briefing names the siblings already titled (the later ones see the earlier ones)
    assert "must differ" not in log[0] and "must differ" in log[2]


def test_a_title_carries_while_the_membership_barely_moves(home) -> None:
    log: List[str] = []
    topics = {t: _topic(home, t, 20) for t in (1, 2)}
    _pass(home, author=author_fn(log))
    title1 = next(c.title for c in _current(home) if topics[1][0] in c.members)
    _topic(home, 1, 1, start=20)  # 1 of 21: Jaccard 0.95
    log.clear()
    r = _pass(home, author=author_fn(log))
    assert r["written"] == 1 and log == [] and r["titles_kept"] == 2 and r["renamed"] == 0
    [c1] = [c for c in _current(home) if topics[1][0] in c.members]
    assert c1.title == title1 and c1.attrs["title_provenance"]["carried_from"] == c1.attrs["basis"]["previous_id"]
    _topic(home, 1, 6, start=21)  # Jaccard to the basis < 0.8: authored again, the previous title in the briefing
    r = _pass(home, author=author_fn(log))
    assert r["renamed"] == 1 and len(log) == 1 and f'"{title1}"' in log[0]


def test_budget_bounds_the_author_calls_and_the_version_is_still_written(home) -> None:
    _three_topics(home)
    log: List[str] = []
    r = _pass(home, author=author_fn(log), budget=1)
    assert len(log) == 1 and r["authored"] == 1 and r["pending"] == 2 and r["written"] == 3
    pend = [c for c in _current(home) if c.title is None]
    assert len(pend) == 2 and {c.attrs["pending"]["failure"]["reason"] for c in pend} == {"budget_spent"}
    for c in pend:
        assert {t["kind"] for t in home.tasks.tasks(target_id=c.record_id) if t["status"] in LIVE} == {
            "title.author", "digest.author"}


def test_a_sibling_title_collision_forms_pending_with_one_feedback_line(home) -> None:
    _three_topics(home)
    r = _pass(home, author=author_fn(title="Same words"))
    assert r["authored"] == 1 and r["pending"] == 2
    assert {f["error_class"] for f in r["authoring"]["failures"]} == {"TitleCollision"}
    pend = [c for c in _current(home) if c.title is None]
    for c in pend:
        assert 'Another topic is already titled "Same words": this title must differ.' in c.digest


def test_the_no_common_subject_verdict_is_an_authored_terminal_state(home) -> None:
    _three_topics(home)
    r = _pass(home, author=author_fn(verdict=C.NO_COMMON_SUBJECT))
    assert r["authored"] == 3
    for c in _current(home):
        assert c.attrs["verdict"] == C.NO_COMMON_SUBJECT and c.title
        assert not [t for t in home.tasks.tasks(target_id=c.record_id) if t["status"] in LIVE]


def test_an_unknown_verdict_is_an_invalid_result(home) -> None:
    _three_topics(home)
    r = _pass(home, author=author_fn(verdict="maybe"))
    assert r["pending"] == 3 and {f["reason"] for f in r["authoring"]["failures"]} == {"invalid_result"}


def test_the_briefing_sample_is_stable_for_a_stable_key(home) -> None:
    topics = {1: _topic(home, 1, 60)}
    g = C.read_community_graph(home, scopes=SCOPES, owner_id=OWNER)
    det = C.detect_communities(g)
    members = sorted(topics[1])
    small = C.briefing_sample("ex:community-aaaaaaaaaaaa", members, g, det.weights, token_budget=120)
    again = C.briefing_sample("ex:community-aaaaaaaaaaaa", members, g, det.weights, token_budget=120)
    other = C.briefing_sample("ex:community-bbbbbbbbbbbb", members, g, det.weights, token_budget=120)
    assert small == again and 3 < len(small) < len(members)
    hubs = small[:C.BRIEFING_HUBS]
    assert other[:C.BRIEFING_HUBS] == hubs and other[C.BRIEFING_HUBS:] != small[C.BRIEFING_HUBS:]
    # 5 % more members: the keyed sample keeps most of its choice (bottom-k by hash)
    extra = _topic(home, 1, 3, start=60)
    g2 = C.read_community_graph(home, scopes=SCOPES, owner_id=OWNER)
    det2 = C.detect_communities(g2)
    s2 = C.briefing_sample("ex:community-aaaaaaaaaaaa", sorted(members + extra), g2, det2.weights, token_budget=120)
    tail1, tail2 = set(small[C.BRIEFING_HUBS:]), set(s2[C.BRIEFING_HUBS:])
    assert len(tail1 & tail2) >= 0.6 * len(tail1)


# ----------------------------------------------------------------------------------------------- small homes


def test_an_empty_home(home) -> None:
    r = _pass(home)
    assert r["version_seq"] is None and r["communities"] == 0 and r["skipped"].startswith("empty")


def test_one_and_two_records(home) -> None:
    [a] = _topic(home, 1, 1)
    r = _pass(home)
    assert r["communities"] == 1 and _membership(home) == {a: _current(home)[0].key}
    assert _current(home)[0].attrs["layout"]["xy"] == [0.0, 0.0]
    [b] = _topic(home, 1, 1, start=1)
    r = _pass(home)
    assert r["communities"] == 1 and set(_membership(home)) == {a, b}


def test_a_home_with_no_vector_at_all(home) -> None:
    ids = _form(home, [MemoryRecordInput(kind="episode", title=f"N{i}", digest=f"novec {i}",
                                         edges=(("continues", "local:0"),) if i else ()) for i in range(4)], "nv")
    r = _pass(home)
    assert r["communities"] == 0 and r["version_seq"] is None
    assert r["unvectored"] == sorted(ids) and r["unplaced"] == sorted(ids) and r["unplaced_count"] == 4
    assert r["skipped"].startswith("no vectored record")


def test_the_receipt_has_what_the_runtime_logs(home) -> None:
    _three_topics(home)
    r = _pass(home)
    for key in ("version_seq", "communities", "new", "kept", "renamed", "dissolved", "moved_in", "moved_out",
                "attached", "unvectored", "unplaced", "unplaced_closed", "authored", "pending", "failed",
                "cancelled", "skipped", "elapsed_ms", "timings_ms", "authoring", "titles_kept"):
        assert key in r
    assert set(r["timings_ms"]) >= {"read", "knn", "louvain", "refine", "rounds", "match", "layout", "author",
                                    "write"}
