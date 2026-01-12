from __future__ import annotations

from abstractmemory import InMemoryTripleStore, TripleAssertion, TripleQuery


def test_terms_are_canonicalized_on_write_and_query() -> None:
    store = InMemoryTripleStore(embedder=None)
    store.add(
        [
            TripleAssertion(
                subject="  Scrooge  ",
                predicate="  Related_To  ",
                object="  Christmas  ",
                scope="  SESSION  ",
                owner_id="s1",
                observed_at="2026-01-01T00:00:00+00:00",
            )
        ]
    )

    out = store.query(
        TripleQuery(
            subject="scrooge",
            predicate="related_to",
            object="CHRISTMAS",
            scope="session",
            owner_id="s1",
            limit=10,
        )
    )
    assert len(out) == 1
    assert out[0].subject == "scrooge"
    assert out[0].predicate == "related_to"
    assert out[0].object == "christmas"

