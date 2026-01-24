from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.basic


def test_in_memory_triple_store_limit_zero_is_unbounded() -> None:
    from abstractmemory import InMemoryTripleStore, TripleAssertion, TripleQuery

    store = InMemoryTripleStore()
    try:
        store.add(
            [
                TripleAssertion(subject="ex:a", predicate="rdf:type", object="schema:thing", scope="session", owner_id="o1"),
                TripleAssertion(subject="ex:b", predicate="rdf:type", object="schema:thing", scope="session", owner_id="o1"),
                TripleAssertion(subject="ex:c", predicate="rdf:type", object="schema:thing", scope="session", owner_id="o1"),
            ]
        )

        assert len(store.query(TripleQuery(scope="session", owner_id="o1", limit=1))) == 1
        assert len(store.query(TripleQuery(scope="session", owner_id="o1", limit=0))) == 3
        assert len(store.query(TripleQuery(scope="session", owner_id="o1", limit=-1))) == 3
    finally:
        store.close()


def test_lancedb_triple_store_limit_zero_is_unbounded(tmp_path: Path) -> None:
    try:
        import lancedb  # type: ignore  # noqa: F401
    except Exception:
        pytest.skip("lancedb is not installed")

    from abstractmemory import LanceDBTripleStore, TripleAssertion, TripleQuery

    store = LanceDBTripleStore(tmp_path / "kg")
    try:
        store.add(
            [
                TripleAssertion(subject="ex:a", predicate="rdf:type", object="schema:thing", scope="session", owner_id="o1"),
                TripleAssertion(subject="ex:b", predicate="rdf:type", object="schema:thing", scope="session", owner_id="o1"),
                TripleAssertion(subject="ex:c", predicate="rdf:type", object="schema:thing", scope="session", owner_id="o1"),
            ]
        )

        assert len(store.query(TripleQuery(scope="session", owner_id="o1", limit=1))) == 1
        assert len(store.query(TripleQuery(scope="session", owner_id="o1", limit=0))) == 3
        assert len(store.query(TripleQuery(scope="session", owner_id="o1", limit=-1))) == 3
    finally:
        store.close()

