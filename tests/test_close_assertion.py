"""close_assertion: the one in-place change both triple stores allow.

It closes an open validity window and nothing else, so TripleQuery(active_at=...)
agrees with a writer that superseded a fact (AbstractNote supersession)."""
from __future__ import annotations

from pathlib import Path

import pytest

from abstractmemory import InMemoryTripleStore, SQLiteTripleStore, TripleAssertion, TripleQuery


def _stores(tmp_path: Path):
    return [InMemoryTripleStore(), SQLiteTripleStore(tmp_path / "kg.sqlite3")]


def _fact(aid: str, obj: str, valid_from: str, **kw) -> TripleAssertion:
    return TripleAssertion(
        subject="ex:person-dana", predicate="schema:worksFor", object=obj, scope="global",
        owner_id="abstractnote", observed_at=valid_from, valid_from=valid_from,
        assertion_id=aid, provenance={"note_id": "nt_x"}, attributes={"certainty": "stated"}, **kw,
    )


@pytest.mark.parametrize("which", [0, 1])
def test_close_assertion_closes_open_window_only(tmp_path: Path, which: int) -> None:
    store = _stores(tmp_path)[which]
    store.add([_fact("cl_1", "ex:org-acme", "2026-01-01T00:00:00+00:00"),
               _fact("cl_2", "ex:org-beta", "2026-06-01T00:00:00+00:00")])

    before = store.query(TripleQuery(active_at="2026-07-01T00:00:00+00:00", owner_id="abstractnote"))
    assert {a.assertion_id for a in before} == {"cl_1", "cl_2"}

    assert store.close_assertion("cl_1", "2026-06-01T00:00:00+00:00") is True
    # Already closed: no change, the first window stands.
    assert store.close_assertion("cl_1", "2027-01-01T00:00:00+00:00") is False
    assert store.close_assertion("cl_missing", "2027-01-01T00:00:00+00:00") is False

    after = store.query(TripleQuery(active_at="2026-07-01T00:00:00+00:00", owner_id="abstractnote"))
    assert {a.assertion_id for a in after} == {"cl_2"}
    earlier = store.query(TripleQuery(active_at="2026-03-01T00:00:00+00:00", owner_id="abstractnote"))
    assert {a.assertion_id for a in earlier} == {"cl_1"}

    [closed] = store.query(TripleQuery(assertion_ids=("cl_1",)))
    assert closed.valid_until == "2026-06-01T00:00:00+00:00"
    # Everything else is untouched.
    assert closed.object == "ex:org-acme"
    assert closed.provenance == {"note_id": "nt_x"}
    assert closed.attributes.get("certainty") == "stated"
    assert closed.valid_from == "2026-01-01T00:00:00+00:00"
    store.close()


def test_close_assertion_persists_and_keeps_vectors_and_fts(tmp_path: Path) -> None:
    class Emb:
        model_id = "unit-test"

        def embed_texts(self, texts):
            return [[1.0, float(len(t) % 7), 0.5] for t in texts]

    db = tmp_path / "kg.sqlite3"
    store = SQLiteTripleStore(db, embedder=Emb())
    store.add([TripleAssertion(
        subject="ex:person-dana", predicate="schema:worksFor", object="ex:org-acme", scope="global",
        owner_id="abstractnote", observed_at="2026-01-01T00:00:00+00:00",
        valid_from="2026-01-01T00:00:00+00:00", assertion_id="cl_1",
        attributes={"evidence_quote": "Dana joined Acme"})])
    vec_before = store.stored_vector("cl_1")
    assert store.close_assertion("cl_1", "2026-02-01T00:00:00+00:00")
    assert store.stored_vector("cl_1") == vec_before
    hits = store.query_keywords(["acme"], scope="global", owner_id="abstractnote")
    assert [h.assertion_id for h in hits] == ["cl_1"]
    store.close()

    reopened = SQLiteTripleStore(db, embedder=Emb())
    [row] = reopened.query(TripleQuery(assertion_ids=("cl_1",)))
    assert row.valid_until == "2026-02-01T00:00:00+00:00"
    reopened.close()


@pytest.mark.parametrize("which", [0, 1])
def test_close_assertion_rejects_empty_arguments(tmp_path: Path, which: int) -> None:
    store = _stores(tmp_path)[which]
    with pytest.raises(ValueError):
        store.close_assertion("", "2026-01-01T00:00:00+00:00")
    with pytest.raises(ValueError):
        store.close_assertion("cl_1", "")
