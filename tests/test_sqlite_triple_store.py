from __future__ import annotations

from pathlib import Path

import pytest

from abstractmemory import SQLiteTripleStore, TripleAssertion, TripleQuery


def test_sqlite_triple_store_persists_and_queries(tmp_path: Path) -> None:
    db = tmp_path / "kg.sqlite"

    store = SQLiteTripleStore(db)
    store.add(
        [
            TripleAssertion(
                subject="sb:test",
                predicate="dcterms:hasPart",
                object="bloc:abc",
                scope="session",
                owner_id="sess-1",
            )
        ]
    )
    store.close()

    store2 = SQLiteTripleStore(db)
    hits = store2.query(TripleQuery(subject="sb:test", scope="session", owner_id="sess-1"))
    assert len(hits) == 1
    assert hits[0].predicate == "dcterms:haspart"
    assert hits[0].object == "bloc:abc"
    store2.close()


def test_sqlite_triple_store_order_and_limit(tmp_path: Path) -> None:
    store = SQLiteTripleStore(tmp_path / "kg.sqlite")
    store.add(
        [
            TripleAssertion(subject="a", predicate="p", object="1", observed_at="2026-01-01T00:00:01+00:00"),
            TripleAssertion(subject="a", predicate="p", object="2", observed_at="2026-01-01T00:00:03+00:00"),
            TripleAssertion(subject="a", predicate="p", object="3", observed_at="2026-01-01T00:00:02+00:00"),
        ]
    )
    hits = store.query(TripleQuery(subject="a", predicate="p", limit=2, order="desc"))
    assert [h.object for h in hits] == ["2", "3"]
    hits2 = store.query(TripleQuery(subject="a", predicate="p", limit=2, order="asc"))
    assert [h.object for h in hits2] == ["1", "3"]
    store.close()


def test_sqlite_triple_store_active_at_window(tmp_path: Path) -> None:
    store = SQLiteTripleStore(tmp_path / "kg.sqlite")
    store.add(
        [
            TripleAssertion(
                subject="x",
                predicate="p",
                object="a",
                valid_from="2026-01-01T00:00:00+00:00",
                valid_until="2026-01-02T00:00:00+00:00",
            ),
            TripleAssertion(
                subject="x",
                predicate="p",
                object="b",
                valid_from="2026-01-02T00:00:00+00:00",
            ),
        ]
    )
    inside = store.query(TripleQuery(subject="x", predicate="p", active_at="2026-01-01T12:00:00+00:00"))
    assert [h.object for h in inside] == ["a"]
    boundary = store.query(TripleQuery(subject="x", predicate="p", active_at="2026-01-02T00:00:00+00:00"))
    assert [h.object for h in boundary] == ["b"]
    store.close()


def test_sqlite_triple_store_rejects_semantic_queries(tmp_path: Path) -> None:
    store = SQLiteTripleStore(tmp_path / "kg.sqlite")
    with pytest.raises(ValueError):
        _ = store.query(TripleQuery(query_text="hello", scope="global"))
    store.close()

