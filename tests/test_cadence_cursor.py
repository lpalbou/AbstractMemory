"""`maintenance_due` bounded by a cursor (backlog 0058): the fold over the
store's change feed answers exactly what the full scan answers, and a check
reads only the rows written since the previous one. Both layer-1 stacks
(InMemory pair, SQLite pair in one file), no mocks.

Mutants checked by hand (each turns this file red):
1. `_CadenceFold._fold`: the tie key ignores the store order (always
   assertion_id, or always insertion): the effective title of a subject
   with equal `observed_at` rows differs from the scan.
2. `structural_counts` keeps edges touching a maintenance candidate.
3. `structural_counts` reads a subject's FIRST scope instead of its last.
4. `catch_up` restarts every pair from cursor 0 (rows_read grows by the
   whole store on every check).
5. `sync_journal` never re-reads (the journal_seq check inverted): new
   formations are not counted.
6. `_fold` forgets to reset `anchor` when a new artifact arrives.
7. `SQLiteTripleStore.assertions_after` returns the next cursor as the last
   rowid of a short page instead of the snapshot top (rows of other
   partitions re-read: rows_read grows).
"""

from __future__ import annotations

import random
import warnings
from typing import Any, List, Tuple

import pytest

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    ScopeBinding,
    SQLiteJournal,
    SQLiteTripleStore,
    TripleAssertion,
    TripleQuery,
    consolidation_pass,
    last_maintenance_seq,
    maintenance_due,
)
from abstractmemory import sleep_cadence
from abstractmemory.sleep_cadence import _last_maintenance_seq_scan, _maintenance_due_scan


@pytest.fixture(params=["memory", "sqlite"])
def pair(request: pytest.FixtureRequest, tmp_path) -> Tuple[Any, Any]:
    if request.param == "memory":
        store = InMemoryTripleStore()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            journal = InMemoryJournal()
    else:
        path = tmp_path / "memory.sqlite3"
        store = SQLiteTripleStore(path)
        journal = SQLiteJournal(path)
    yield store, journal
    journal.close()
    store.close()


def _both(store, journal, scopes, **kw) -> dict:
    """The fold's answer, asserted equal to the full scan's."""
    folded = maintenance_due(store, journal, scopes=scopes, **kw)
    scanned = _maintenance_due_scan(
        store, journal, scopes=scopes, since_seq=kw.get("since_seq"),
        min_new_records=kw.get("min_new_records", 12), min_signal=kw.get("min_signal", 3))
    assert folded == scanned
    assert last_maintenance_seq(store, journal, scopes=scopes) == _last_maintenance_seq_scan(
        store, journal, scopes=scopes)
    return folded


TITLES = ["Morning walk", "morning, walk!", "Evening call", "Garden", "", "Garden"]
KINDS = ["episode", "episode", "episode", "summary", "dream", "world_model"]
PREDICATES = ["summarizes", "continues", "mentions", "written_amid", "relates_to", "part_of"]
SUBJECTS = [f"rec:{i}" for i in range(40)]
STAMPS = [f"2026-01-0{d}T00:00:00+00:00" for d in range(1, 6)]   # few values: many ties


def _random_rows(rnd: random.Random, n: int, start: int) -> List[TripleAssertion]:
    rows = []
    for i in range(start, start + n):
        scope = rnd.choice(["life", "life", "diary"])
        owner = rnd.choice(["entity:a", "entity:a", "entity:b"])
        subject = rnd.choice(SUBJECTS)
        roll = rnd.random()
        if roll < 0.4:
            attrs = {"record_edge": True}
            predicate = rnd.choice(PREDICATES)
            obj = rnd.choice(SUBJECTS + ["rec:unknown"])
        else:
            attrs = {"record_kind": rnd.choice(KINDS), "title": rnd.choice(TITLES)}
            if rnd.random() < 0.1:
                attrs["maintenance_candidate"] = True
            if rnd.random() < 0.05:
                attrs["bookkeeping"] = True
            if rnd.random() < 0.05:
                attrs.pop("record_kind")
            predicate, obj = "dcterms:abstract", f"digest {i}"
        rows.append(TripleAssertion(
            subject=subject, predicate=predicate, object=obj, scope=scope, owner_id=owner,
            observed_at=rnd.choice(STAMPS), attributes=attrs,
            assertion_id=f"{rnd.randrange(10 ** 6):06d}-{i}"))
    return rows


@pytest.mark.parametrize("scopes", [
    [("life", "entity:a")],
    [("life", "entity:a"), ("diary", "entity:a")],
    [("diary", "entity:b"), ("life", "")],                       # '' owner = no owner filter
    [("life", "entity:a"), ("LIFE", "entity:a"), ("life", "entity:b")],  # a scope listed twice
])
def test_the_fold_answers_what_the_full_scan_answers(pair, scopes) -> None:
    store, journal = pair
    rnd = random.Random(len(scopes))
    for step in range(8):
        rows = _random_rows(rnd, 30, start=step * 30)
        store.add(rows)
        for a in rows:
            if rnd.random() < 0.7:
                journal.append_binding(ScopeBinding(
                    record_id=a.subject, scope=a.scope, owner_id=a.owner_id or "",
                    source=rnd.choice(["remember", "remember", "maintenance", "election"])))
        for kw in ({}, {"min_new_records": 1, "min_signal": 1}, {"since_seq": step * 10},
                   {"min_new_records": 10 ** 6, "min_signal": 2}):
            _both(store, journal, scopes, **kw)
    # Answers repeat identically with nothing new (the cached path).
    assert maintenance_due(store, journal, scopes=scopes) == maintenance_due(store, journal, scopes=scopes)


def test_fixture_flow_matches_the_scan(pair) -> None:
    """The maintenance fixture's flow (duplicate pile, a consolidation pass
    forming a candidate, new material) through MemorySystem."""
    store, journal = pair
    system = MemorySystem(store=store, journal=journal)
    scopes = [("life", "entity:test")]

    def remember(key, title, digest, **kw):
        return system.remember_many(
            [MemoryRecordInput(kind="episode", title=title, digest=digest, **kw)],
            scope="life", owner_id="entity:test", idempotency_key=key)[0]

    assert _both(store, journal, scopes)["due"] is False
    first = remember("m-1", "Castor's interest", "Castor likes astronomy.", keywords=("astronomy",))
    remember("m-2", "Castor's interest", "Castor likes astronomy a lot.", keywords=("astronomy",))
    remember("m-3", "Castor interest", "Castor talks about stars.", keywords=("astronomy",),
             edges=(("summarizes", first),))
    remember("m-4", "Weather", "It rained.")
    due = _both(store, journal, scopes, min_new_records=3)
    assert due["due"] is True and due["new_records"] == 4
    consolidation_pass(system, scopes=scopes, owner_id="entity:test")
    assert last_maintenance_seq(store, journal, scopes=scopes) > 0
    assert _both(store, journal, scopes, min_new_records=1)["due"] is False
    remember("m-5", "Fresh evening", "Something new happened.")
    again = _both(store, journal, scopes, min_new_records=50, min_signal=1)
    assert again["due"] is True and again["new_records"] == 1


def test_a_check_reads_only_rows_written_since_the_previous_one(pair) -> None:
    store, journal = pair
    scopes = [("life", "entity:a")]
    rnd = random.Random(9)
    rows = _random_rows(rnd, 300, start=0)
    store.add(rows)
    maintenance_due(store, journal, scopes=scopes)
    fold = sleep_cadence._FOLDS[store][(id(journal), (("life", "entity:a"),))]  # noqa: SLF001
    in_pair = sum(1 for a in rows if a.scope == "life" and a.owner_id == "entity:a")
    assert fold.rows_read == in_pair
    for _ in range(3):
        maintenance_due(store, journal, scopes=scopes)
    assert fold.rows_read == in_pair, "no new rows: nothing re-read"
    more = [TripleAssertion(subject="rec:new", predicate="dcterms:abstract", object="d", scope="life",
                            owner_id="entity:a", observed_at=STAMPS[0],
                            attributes={"record_kind": "episode", "title": "New"}, assertion_id="new-1"),
            TripleAssertion(subject="rec:other", predicate="dcterms:abstract", object="d", scope="diary",
                            owner_id="entity:b", observed_at=STAMPS[0],
                            attributes={"record_kind": "episode", "title": "Other"}, assertion_id="new-2")]
    store.add(more)
    _both(store, journal, scopes)
    assert fold.rows_read == in_pair + 1, "only the one new row of the pair"


def test_a_second_store_handle_sees_rows_another_handle_wrote(tmp_path) -> None:
    path = tmp_path / "memory.sqlite3"
    reader, writer = SQLiteTripleStore(path), SQLiteTripleStore(path)
    journal = SQLiteJournal(path)
    scopes = [("life", "entity:a")]
    writer.add(_random_rows(random.Random(1), 50, start=0))
    _both(reader, journal, scopes)
    writer.add(_random_rows(random.Random(2), 50, start=50))
    _both(reader, journal, scopes, min_signal=1)
    for handle in (reader, writer):
        handle.close()
    journal.close()


def test_the_sqlite_change_feed_walks_rowids_not_the_partition(tmp_path) -> None:
    store = SQLiteTripleStore(tmp_path / "kg.sqlite3")
    store.add([TripleAssertion(subject="s", predicate="p", object=str(i),
                               scope="life" if i % 2 else "diary", owner_id="o",
                               observed_at=STAMPS[i % 5], assertion_id=f"a{i}") for i in range(1, 11)])
    rows, cursor = store.assertions_after(0, scope="LIFE", owner_id="o", limit=3)
    assert [r for r, _ in rows] == [1, 3, 5] and cursor == 5
    rows, cursor = store.assertions_after(cursor, scope="life", owner_id="o", limit=3)
    assert [r for r, _ in rows] == [7, 9] and cursor == 10, "a short page resumes at the top"
    assert store.assertions_after(cursor, scope="life", limit=3) == ([], 10)
    assert [a.object for _, a in store.assertions_after(0, limit=100)[0]] == [str(i) for i in range(1, 11)]
    plan = store._conn.execute(  # noqa: SLF001 - the access path the feed relies on
        "EXPLAIN QUERY PLAN SELECT rowid FROM triples WHERE rowid > ? AND rowid <= ? "
        "AND +scope = ? AND +owner_id = ? ORDER BY rowid LIMIT 3", (0, 10, "life", "o")).fetchall()
    assert "INTEGER PRIMARY KEY (rowid>? AND rowid<?)" in " | ".join(str(r[3]) for r in plan)
    store.close()


def test_the_in_memory_change_feed_matches_query_filters() -> None:
    store = InMemoryTripleStore()
    store.add([TripleAssertion(subject="s", predicate="p", object=str(i), scope="life",
                               owner_id="o" if i % 2 else None, observed_at=STAMPS[0],
                               assertion_id=f"a{i}") for i in range(6)])
    rows, cursor = store.assertions_after(0, scope="life", owner_id="o", limit=2)
    assert [(p, a.object) for p, a in rows] == [(2, "1"), (4, "3")] and cursor == 4
    rows, cursor = store.assertions_after(cursor, scope="life", owner_id="o", limit=2)
    assert [(p, a.object) for p, a in rows] == [(6, "5")] and cursor == 6
    everyone = [a.assertion_id for _, a in store.assertions_after(0, scope="life")[0]]
    assert sorted(everyone) == sorted(a.assertion_id for a in store.query(TripleQuery(scope="life", limit=0)))


def test_a_store_without_a_change_feed_keeps_the_full_scan(pair) -> None:
    """Stores the fold does not know (LanceDB) answer through the scan."""
    store, journal = pair

    class Plain:
        def __init__(self, inner):
            self.inner = inner

        def query(self, q):
            return self.inner.query(q)

    store.add(_random_rows(random.Random(4), 40, start=0))
    plain = Plain(store)
    scopes = [("life", "entity:a")]
    assert maintenance_due(plain, journal, scopes=scopes) == maintenance_due(store, journal, scopes=scopes)
    assert plain not in sleep_cadence._FOLDS  # noqa: SLF001
