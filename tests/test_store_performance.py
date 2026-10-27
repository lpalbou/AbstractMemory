"""Home store performance contracts (backlog 0058).

These pin the SHAPE of the reads, not wall-clock numbers (those live in
`tests/bench/bench_store.py`): partition reads walk the
(scope, owner_id, observed_at) index in query order, anchored reads use
their own index, the owner filter is an index-usable equality, and the
rewritten predicate returns exactly the rows the old COALESCE form did.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from abstractmemory import SQLiteTripleStore, TripleAssertion, TripleQuery


def _row(i: int, *, owner, subject: str = "ex:s", scope: str = "life") -> TripleAssertion:
    return TripleAssertion(
        subject=subject, predicate="ex:p", object=f"value {i}", scope=scope,
        owner_id=owner, observed_at=f"2026-01-01T00:00:{i:02d}.000000+00:00",
        assertion_id=f"a-{i}")


@pytest.mark.parametrize("table", ["triples", "kg_alt"])
def test_partition_reads_use_the_scope_owner_index_in_order(tmp_path: Path, table: str) -> None:
    store = SQLiteTripleStore(tmp_path / "kg.sqlite3", table_name=table)
    for q in (
        TripleQuery(scope="life", owner_id="entity:a", limit=100),               # latest N
        TripleQuery(scope="life", owner_id="entity:a", limit=100, order="asc"),
        TripleQuery(scope="life", owner_id="entity:a", limit=0),                 # full pair scan
        TripleQuery(scope="life", owner_id="entity:a", active_at="2026-01-01T00:00:00+00:00"),
        TripleQuery(scope="life", owner_id="entity:a", predicate="ex:p"),
    ):
        plan = " | ".join(store.query_plan(q))
        # Both key columns are bound: the old COALESCE(owner_id, '') = ?
        # form shows "(scope=?)" alone here and goes red.
        assert f"USING INDEX idx_{table}_scope_owner" in plan, plan
        assert "(scope=? AND owner_id=?)" in plan, plan
        # Rows come in index order: no sort of the whole partition.
        assert "TEMP B-TREE" not in plan, plan
    store.close()


def test_anchored_reads_use_their_own_index(tmp_path: Path) -> None:
    store = SQLiteTripleStore(tmp_path / "kg.sqlite3")
    by_subject = " | ".join(store.query_plan(
        TripleQuery(subject="ex:s1", scope="life", owner_id="entity:a")))
    assert "USING INDEX idx_triples_spo (subject=?)" in by_subject, by_subject
    by_object = " | ".join(store.query_plan(
        TripleQuery(object="ex:s1", scope="life", owner_id="entity:a")))
    assert "USING INDEX idx_triples_object (object=?)" in by_object, by_object
    by_id = " | ".join(store.query_plan(
        TripleQuery(assertion_ids=("a-1", "a-2"), scope="life", owner_id="entity:a")))
    assert "(assertion_id=?)" in by_id, by_id
    store.close()


def test_owner_equality_returns_the_rows_of_the_old_coalesce_form(tmp_path: Path) -> None:
    """NULL, '' and named owners side by side: every owner filter returns
    exactly what `COALESCE(owner_id, '') = ?` returned, and no filter
    returns them all."""
    path = tmp_path / "kg.sqlite3"
    store = SQLiteTripleStore(path)
    store.add([_row(1, owner=None), _row(2, owner="entity:a"), _row(3, owner="entity:b"),
               _row(4, owner="entity:a", subject="ex:t"), _row(5, owner="entity:a", scope="diary")])
    # A stored '' owner (TripleAssertion normalises '' to None, so write it raw).
    with sqlite3.connect(str(path)) as raw:
        raw.execute("UPDATE triples SET owner_id = '' WHERE assertion_id = 'a-3'")
        raw.execute("INSERT INTO triples (assertion_id, subject, predicate, object, scope, owner_id, observed_at) "
                    "VALUES ('a-6', 'ex:s', 'ex:p', 'v6', 'life', '', '2026-01-01T00:00:06.000000+00:00')")

    def old_form(scope, owner, subject=None):
        sql = "SELECT assertion_id FROM triples WHERE scope = ? AND COALESCE(owner_id, '') = ?"
        params = [scope, owner]
        if subject:
            sql += " AND subject = ?"
            params.append(subject)
        with sqlite3.connect(str(path)) as raw:
            return sorted(r[0] for r in raw.execute(sql, params))

    for owner in ("entity:a", "entity:b", "nobody"):
        got = sorted(a.assertion_id for a in store.query(TripleQuery(scope="life", owner_id=owner, limit=0)))
        assert got == old_form("life", owner)
        got_s = sorted(a.assertion_id for a in store.query(
            TripleQuery(subject="ex:s", scope="life", owner_id=owner, limit=0)))
        assert got_s == old_form("life", owner, "ex:s")
    everyone = sorted(a.assertion_id for a in store.query(TripleQuery(scope="life", owner_id="", limit=0)))
    assert everyone == ["a-1", "a-2", "a-3", "a-4", "a-6"]
    assert [a.owner_id for a in store.query(TripleQuery(assertion_ids=("a-1", "a-3"), limit=0))] == [None, None]
    store.close()


def test_existing_home_gains_the_partition_index_on_open(tmp_path: Path) -> None:
    """An existing home (created before the index) gains it at open; no row
    is rewritten."""
    path = tmp_path / "kg.sqlite3"
    store = SQLiteTripleStore(path)
    store.add([_row(i, owner="entity:a") for i in range(1, 6)])
    store.close()
    with sqlite3.connect(str(path)) as raw:
        raw.execute("DROP INDEX idx_triples_scope_owner_observed")
        before = raw.execute("SELECT rowid, * FROM triples ORDER BY rowid").fetchall()
    reopened = SQLiteTripleStore(path)
    assert "(scope=? AND owner_id=?)" in " | ".join(
        reopened.query_plan(TripleQuery(scope="life", owner_id="entity:a")))
    reopened.close()
    with sqlite3.connect(str(path)) as raw:
        assert raw.execute("SELECT rowid, * FROM triples ORDER BY rowid").fetchall() == before
