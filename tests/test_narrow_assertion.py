"""narrow_assertion: move an already-closed validity window EARLIER (ADR 0003 decision 7, contract §4).

Mutants (tried by hand in an isolated copy, each turned the named test red):
- SQLite `_narrow_on`: open-row branch replaced by `if False:`        -> test_narrow_refuses_an_open_window[sqlite]
- SQLite `_narrow_on`: `<=` -> `<` for "already at or before"         -> test_narrow_is_a_no_op_when_already_at_or_before[sqlite]
  (the equal-value replay then reports True)
- InMemory: the `valid_until <= until` guard removed                  -> test_narrow_is_a_no_op_when_already_at_or_before[memory]
  (the window widens back to the later value)
- SQLite: unknown id returns True                                     -> test_narrow_unknown_id_is_false[sqlite]
Guard (not a mutant): test_narrow_never_touches_the_journal pins that the store never writes a closure; the revision
that carries a `narrow` op records it (abstractmemory.graph).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from abstractmemory import (
    InMemoryTripleStore,
    LanceDBTripleStore,
    SQLiteJournal,
    SQLiteTripleStore,
    TripleAssertion,
    TripleQuery,
)

T_JAN = "2026-01-01T00:00:00+00:00"
T_MAR = "2026-03-01T00:00:00+00:00"
T_APR = "2026-04-01T00:00:00+00:00"
T_JUN = "2026-06-01T00:00:00+00:00"
T_SEP = "2026-09-01T00:00:00+00:00"


def _store(tmp_path: Path, which: str):
    if which == "memory":
        return InMemoryTripleStore()
    return SQLiteTripleStore(tmp_path / "kg.sqlite3")


def _fact(aid: str, *, valid_until=None) -> TripleAssertion:
    return TripleAssertion(
        subject="ex:person-dana", predicate="schema:worksFor", object="ex:org-acme", scope="global",
        owner_id="abstractnote", observed_at=T_JAN, valid_from=T_JAN, valid_until=valid_until,
        assertion_id=aid, provenance={"note_id": "nt_x"}, attributes={"certainty": "stated"},
    )


def _row(store, aid: str) -> TripleAssertion:
    [row] = store.query(TripleQuery(assertion_ids=(aid,)))
    return row


@pytest.mark.parametrize("which", ["memory", "sqlite"])
def test_narrow_moves_a_closed_window_earlier_only(tmp_path: Path, which: str) -> None:
    store = _store(tmp_path, which)
    store.add([_fact("n1", valid_until=T_JUN)])
    assert store.narrow_assertion("n1", T_MAR) is True
    row = _row(store, "n1")
    assert row.valid_until == T_MAR
    # Only the window moved.
    assert (row.object, row.provenance, row.attributes.get("certainty"), row.valid_from) == (
        "ex:org-acme", {"note_id": "nt_x"}, "stated", T_JAN)
    # active_at agrees with the narrowed window.
    owner = TripleQuery(active_at=T_APR, owner_id="abstractnote")
    assert store.query(owner) == []
    assert [a.assertion_id for a in store.query(TripleQuery(active_at="2026-02-01T00:00:00+00:00"))] == ["n1"]
    store.close()


@pytest.mark.parametrize("which", ["memory", "sqlite"])
def test_narrow_refuses_an_open_window(tmp_path: Path, which: str) -> None:
    store = _store(tmp_path, which)
    store.add([_fact("open_1")])
    with pytest.raises(ValueError, match="narrow_assertion cannot widen"):
        store.narrow_assertion("open_1", T_MAR)
    assert _row(store, "open_1").valid_until is None
    store.close()


@pytest.mark.parametrize("which", ["memory", "sqlite"])
def test_narrow_is_a_no_op_when_already_at_or_before(tmp_path: Path, which: str) -> None:
    store = _store(tmp_path, which)
    store.add([_fact("n2", valid_until=T_MAR)])
    # Same value: an idempotent replay.
    assert store.narrow_assertion("n2", T_MAR) is False
    # Later value: the window is already earlier; it never widens back.
    assert store.narrow_assertion("n2", T_SEP) is False
    assert _row(store, "n2").valid_until == T_MAR
    store.close()


@pytest.mark.parametrize("which", ["memory", "sqlite"])
def test_narrow_unknown_id_is_false(tmp_path: Path, which: str) -> None:
    store = _store(tmp_path, which)
    store.add([_fact("n3", valid_until=T_JUN)])
    assert store.narrow_assertion("missing", T_MAR) is False
    assert _row(store, "n3").valid_until == T_JUN
    with pytest.raises(ValueError):
        store.narrow_assertion("", T_MAR)
    with pytest.raises(ValueError):
        store.narrow_assertion("n3", "  ")
    store.close()


def test_narrow_persists_and_keeps_vectors_and_fts(tmp_path: Path) -> None:
    class Emb:
        model_id = "unit-test"

        def embed_texts(self, texts):
            return [[1.0, float(len(t) % 7), 0.5] for t in texts]

    db = tmp_path / "kg.sqlite3"
    store = SQLiteTripleStore(db, embedder=Emb())
    store.add([_fact("n4", valid_until=T_JUN)])
    vec = store.stored_vector("n4")
    assert store.narrow_assertion("n4", T_MAR)
    assert store.stored_vector("n4") == vec
    assert [h.assertion_id for h in store.query_keywords(["acme"], scope="global", owner_id="abstractnote")] == ["n4"]
    store.close()
    reopened = SQLiteTripleStore(db, embedder=Emb())
    assert _row(reopened, "n4").valid_until == T_MAR
    reopened.close()


def test_narrow_never_touches_the_journal(tmp_path: Path) -> None:
    db = tmp_path / "home.sqlite3"
    store = SQLiteTripleStore(db)
    journal = SQLiteJournal(db)
    store.add([_fact("n5", valid_until=T_JUN)])
    before = journal.current_seq()
    assert store.narrow_assertion("n5", T_MAR) is True
    assert journal.current_seq() == before
    assert journal.closures(assertion_id="n5") == []
    journal.close()
    store.close()


def test_lancedb_narrow_is_not_implemented() -> None:
    store = object.__new__(LanceDBTripleStore)  # no lancedb needed: the method refuses before any I/O
    with pytest.raises(NotImplementedError, match="backlog 0057"):
        store.narrow_assertion("x", T_MAR)
