"""Opening a home is a READ (architect review C1): a process that opens an up-to-date home (the store, the journal
and the graph over one file) takes no write lock, so it never waits behind a writer: the gateway opens a mind per
request while an entity's loop or a workflow holds the write lock. The backfills that DO write on open (keyword
index, JSON->BLOB vectors, missing schema) run only when there is work, and every write path keeps their cursors
current, so a home written by this version opens without work.

Mutants (applied by hand; each turned the named test red):
- `SQLiteTripleStore._create_schema`: the FTS sync guarded by nothing (BEGIN IMMEDIATE on every open)
                                                                   -> test_opening_an_up_to_date_home_never_waits
- `SQLiteTripleStore._upgrade_vector_encoding`: the read-first probe removed
                                                                   -> test_rows_a_0_3_writer_added_do_not_make_an_open_write
- `SQLiteTripleStore._after_insert`: the vector cursor not advanced -> test_opening_an_up_to_date_home_never_waits
- `SQLiteJournal._ensure_schema`: the deferred first attempt removed -> test_opening_an_up_to_date_home_never_waits
- `journal_sqlite_rows.ensure_schema`: the counter row INSERT made unconditional again
                                                                   -> test_opening_an_up_to_date_home_never_waits
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from abstractmemory import SQLiteJournal, SQLiteTripleStore, TripleAssertion
from abstractmemory.graph import MemoryGraph

from graph_support import FakeEmbedder, claim, file_state, prov, rev, step


def _open_all(path: Path):
    embedder = FakeEmbedder()
    store = SQLiteTripleStore(path, embedder=embedder, embedding_pin={"model_id": embedder.model, "dimension": 64})
    journal = SQLiteJournal(path)
    return store, journal, MemoryGraph(store, journal)


def test_opening_an_up_to_date_home_never_waits(tmp_path: Path) -> None:
    path = tmp_path / "home.sqlite3"
    store, journal, graph = _open_all(path)
    # every write path: store.add, a graph revision (with a close: the journal), a second add after the graph
    store.add([TripleAssertion(subject="ex:a", predicate="ex:p", object="text a", scope="global")])
    graph.apply_revision(rev("r-1", claim("g-1", s="ex:g", o="ex:x"), provenance=prov(step("run-1", 1))))
    graph.apply_revision(rev("r-2", claim("g-2", s="ex:h", o="ex:y"), provenance=prov(step("run-1", 2))))
    store.add([TripleAssertion(subject="ex:b", predicate="ex:p", object="text b", scope="global")])
    journal.close()
    store.close()
    with sqlite3.connect(str(path)) as conn:  # every write path left the cursors at the head: nothing to do on open
        cursors = dict(conn.execute("SELECT key, value FROM triples_meta WHERE key LIKE '%high_water'").fetchall())
        top = conn.execute("SELECT MAX(rowid) FROM triples").fetchone()[0]
    assert cursors == {"fts_high_water": str(top), "vector_blob_high_water": str(top)}
    before = file_state(path)
    writer = sqlite3.connect(str(path), isolation_level=None, timeout=0.1)
    writer.execute("BEGIN IMMEDIATE")  # another process holds the home's write lock
    try:
        started = time.monotonic()
        store, journal, graph = _open_all(path)
        assert graph.history("g-1")[0]["revision_id"] == "r-1"
        elapsed = time.monotonic() - started
    finally:
        writer.execute("ROLLBACK")
        writer.close()
    journal.close()
    store.close()
    assert elapsed < 0.5, f"opening waited {elapsed:.2f}s behind a writer"
    assert file_state(path) == before  # and wrote nothing


def test_rows_a_0_3_writer_added_do_not_make_an_open_write(tmp_path: Path) -> None:
    """A 0.3.x process sharing the home adds vectorless rows (it keeps the keyword index but knows nothing of the
    vector cursor): the vector cursor is behind, yet there is no JSON vector to rewrite, so opening still writes
    nothing and does not wait."""
    path = tmp_path / "home.sqlite3"
    store = SQLiteTripleStore(path)
    store.add([TripleAssertion(subject="ex:a", predicate="ex:p", object="a")])
    store.close()
    with sqlite3.connect(str(path)) as conn:
        conn.execute("INSERT INTO triples (assertion_id, subject, predicate, object, scope, observed_at, text) "
                     "VALUES ('old-1', 'ex:b', 'ex:p', 'b', 'global', '2026-01-01T00:00:00+00:00', 'ex:b ex:p b')")
        top = conn.execute("SELECT MAX(rowid) FROM triples").fetchone()[0]
        conn.execute("INSERT INTO triples_fts (rowid, text) VALUES (?, 'ex:b ex:p b')", (top,))
        conn.execute("UPDATE triples_meta SET value = ? WHERE key = 'fts_high_water'", (str(top),))
    before = file_state(path)
    writer = sqlite3.connect(str(path), isolation_level=None, timeout=0.1)
    writer.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        SQLiteTripleStore(path).close()
        elapsed = time.monotonic() - started
    finally:
        writer.execute("ROLLBACK")
        writer.close()
    assert elapsed < 0.5 and file_state(path) == before
