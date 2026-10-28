"""The matrix cache's footprint (architect review C2): a (re)build reserves exactly the table's vector rows and
allocates once; later appends grow by at most `VECTOR_MATRIX_GROWTH` (no doubling); a rebuild drops the old matrix
before the new one exists. Per-process footprint formula: `store_tuning.py`.

Measured (100k x 1024, tracemalloc, same code with the old policy emulated): held 424 MB vs 552 MB, build peak
460 MB vs 833 MB; a rebuild after a generation bump peaks at the build's figure in both (the old matrix was already
freed before the rebuild allocated: the 2.35 GB RSS reported by the architect is a high-water mark of doubling
growth copies, not two matrices held).

Mutants (applied by hand; each turned the named test red):
- `VectorMatrix._reserve`: growth `self._capacity * 2` (doubling)    -> test_appends_grow_by_at_most_ten_percent
- `SQLiteTripleStore._synced_vectors`: no `size_hint`               -> test_a_build_allocates_once_for_the_rows_it_holds
- `SQLiteTripleStore._synced_vectors`: the old matrix dropped AFTER the new one is constructed
                                                                    -> test_a_rebuild_never_holds_two_matrices
"""
from __future__ import annotations

import weakref
from pathlib import Path

import numpy as np
import pytest

import abstractmemory.sqlite_store as sqlite_store_module
from abstractmemory import SQLiteTripleStore, TripleAssertion, TripleQuery
from abstractmemory.store_tuning import SYNC_FETCH_ROWS, VECTOR_MATRIX_GROWTH

DIM = 4


class _Embedder:
    model = "unit-4"

    def embed_texts(self, texts):
        return [list(np.random.default_rng(abs(hash(t)) % (2 ** 32)).standard_normal(DIM)) for t in texts]


def _store(tmp_path: Path, n: int) -> SQLiteTripleStore:
    store = SQLiteTripleStore(tmp_path / "home.sqlite3", embedder=_Embedder(),
                              embedding_pin={"model_id": "unit-4", "dimension": DIM})
    store.add([TripleAssertion(subject="ex:s", predicate="ex:p", object=f"value {i}", scope="g")
               for i in range(n)])
    return store


def _query(store: SQLiteTripleStore) -> None:
    store.query(TripleQuery(scope="g", query_vector=[0.5] * DIM, limit=3))


def test_a_build_allocates_once_for_the_rows_it_holds(tmp_path: Path) -> None:
    n = SYNC_FETCH_ROWS + 904  # more than one fetch chunk: without a reservation the build regrows
    store = _store(tmp_path, n)
    _query(store)
    assert store._vectors.size == n and store._vectors._capacity == n
    assert store._vectors.allocations == 1
    store.close()


def test_appends_grow_by_at_most_ten_percent(tmp_path: Path) -> None:
    store = _store(tmp_path, 1500)
    _query(store)
    assert store._vectors._capacity == 1500
    store.add([TripleAssertion(subject="ex:s", predicate="ex:p", object="one more", scope="g")])
    _query(store)
    assert store._vectors._capacity == 1500 + int(1500 * VECTOR_MATRIX_GROWTH) == 1650
    store.close()


def test_a_rebuild_never_holds_two_matrices(tmp_path: Path, monkeypatch) -> None:
    store = _store(tmp_path, 50)
    _query(store)
    old = weakref.ref(store._vectors)
    seen = {}
    real = sqlite_store_module.VectorMatrix

    class Observed(real):
        def __init__(self, token):
            seen["old_alive_at_new"] = old() is not None
            super().__init__(token)

    monkeypatch.setattr(sqlite_store_module, "VectorMatrix", Observed)
    cur = store._conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    store._bump_vector_generation(cur)  # any whole-store vector rewrite (replace_vectors, the upgrade)
    cur.execute("COMMIT")
    _query(store)
    assert seen == {"old_alive_at_new": False}
    store.close()
