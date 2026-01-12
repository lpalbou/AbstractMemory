from __future__ import annotations

import pytest

from abstractmemory import InMemoryTripleStore, TripleAssertion, TripleQuery


def test_in_memory_query_text_requires_embedder_without_fallback() -> None:
    store = InMemoryTripleStore(embedder=None)
    store.add(
        [
            TripleAssertion(subject="Scrooge", predicate="related_to", object="Christmas", scope="session", owner_id="s1"),
            TripleAssertion(subject="Marley", predicate="participates_in", object="Death of Marley", scope="session", owner_id="s1"),
            TripleAssertion(subject="Alice", predicate="creates", object="Report", scope="session", owner_id="s2"),
        ]
    )

    with pytest.raises(ValueError) as e:
        store.query(TripleQuery(query_text="christmas", scope="session", owner_id="s1", limit=10))
    assert "query_text" in str(e.value).lower()
