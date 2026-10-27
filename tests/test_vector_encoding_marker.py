"""A 0.4.0 home declares its vector encoding (review M4): opening it rewrites JSON vectors as float32 BLOBs, a ONE-WAY
migration a 0.3.x reader cannot follow (it decodes JSON only and silently finds no vectors), so the meta table says
`vector_encoding = float32-blob` for any later reader to check.

Mutants (applied by hand to SQLiteTripleStore): the marker write removed from `_after_insert` -> the first test red;
removed from the upgrade transaction -> the second test red.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from abstractmemory import SQLiteTripleStore
from abstractmemory.vector_matrix import VECTOR_ENCODING_FLOAT32_BLOB, VECTOR_ENCODING_KEY


def _meta(path: Path, key: str):
    with sqlite3.connect(str(path)) as conn:
        row = conn.execute("SELECT value FROM triples_meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def test_a_new_home_declares_float32_blob_at_its_first_write(tmp_path: Path) -> None:
    """Opening writes nothing (architect C1: opening a home is a read); the first write declares the encoding."""
    from abstractmemory import TripleAssertion

    path = tmp_path / "home.sqlite3"
    SQLiteTripleStore(path).close()
    assert _meta(path, VECTOR_ENCODING_KEY) is None
    store = SQLiteTripleStore(path)
    store.add([TripleAssertion(subject="ex:a", predicate="ex:p", object="ex:b")])
    store.close()
    assert _meta(path, VECTOR_ENCODING_KEY) == VECTOR_ENCODING_FLOAT32_BLOB == "float32-blob"


def test_an_upgraded_0_3_home_declares_it_after_rewriting_its_vectors(tmp_path: Path) -> None:
    path = tmp_path / "home.sqlite3"
    SQLiteTripleStore(path).close()
    with sqlite3.connect(str(path)) as conn:  # what a 0.3.x writer left: a JSON vector, no marker
        conn.execute("DELETE FROM triples_meta WHERE key IN (?, 'vector_blob_high_water')", (VECTOR_ENCODING_KEY,))
        conn.execute("INSERT INTO triples (assertion_id, subject, predicate, object, scope, observed_at, embedding) "
                     "VALUES ('old-1', 'ex:a', 'ex:p', 'ex:b', 'global', '2026-01-01T00:00:00+00:00', ?)",
                     (json.dumps([0.25, 0.5, 0.75]),))
    assert _meta(path, VECTOR_ENCODING_KEY) is None
    store = SQLiteTripleStore(path)
    assert store.stored_vector("old-1") == [0.25, 0.5, 0.75]
    store.close()
    with sqlite3.connect(str(path)) as conn:
        assert conn.execute("SELECT typeof(embedding) FROM triples WHERE assertion_id = 'old-1'").fetchone()[0] == "blob"
    assert _meta(path, VECTOR_ENCODING_KEY) == "float32-blob"
