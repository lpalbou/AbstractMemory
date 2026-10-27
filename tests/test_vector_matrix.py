"""Binary vectors and the vector matrix cache of the SQLite store (backlog
0058; ADR 0003 decision 3). Real temporary stores, no mocks.

What is pinned:
- the matrix answers EXACTLY what the reference Python scan answers (same
  ids, same order, bit-identical scores) on random data with ties,
  near-ties, zero vectors, min_score / limit combinations and SQL-filtered
  candidates;
- a second handle sees rows another handle wrote by appending only those
  rows (no rescan), and rebuilds after `replace_vectors` from another
  handle (even with an identical pin: the `vector_generation` key);
- the in-place upgrade of a JSON-vector home: BLOBs after open, idempotent
  second open, resumable after a crash mid-upgrade, cursor respected;
- legacy JSON vectors (float64) are scored exactly by the matrix;
- the labelled `#FALLBACK` when numpy is absent or a vector is
  unrepresentable: warned once per handle, same results;
- `vector_engine`, `encode_vector` / `decode_vector`.

Mutants checked by hand (each turns this file red):
1. `_sequential_sum` -> `products.sum(axis=-1)` (pairwise) or a matmul:
   scores differ from the reference in the last bits.
2. `coarse_margin` -> 0.0: the near-tie rows at the limit boundary and at
   the min_score floor are dropped.
3. `np.argsort(-exact, kind="stable")` -> default kind: tie order is no
   longer rowid order.
4. `_synced_vectors` rebuilds from rowid 0 on every call (high-water
   ignored): `rows_read` grows by the whole store.
5. `replace_vectors` without `_bump_vector_generation`: the other handle
   keeps serving the old vectors (identical pin).
6. `_upgrade_vector_encoding` skipped / cursor ignored: JSON stays, or rows
   below the cursor are rewritten.
7. `_warn_python_path` without the once-flag: two warnings.
8. `encode_vector` without the range check: 1e39 is stored as inf.
9. forced rows not unioned into the candidates: the tiny/huge/legacy rows
   lose to the float32 pass.
10. `_rank_with_matrix` without the rebuild retry: the vanished-row case
    warns `#FALLBACK`.
"""

from __future__ import annotations

import json
import random
import sqlite3
import warnings
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pytest

from abstractmemory import SQLiteTripleStore, TripleAssertion, TripleQuery
from abstractmemory import sqlite_store as sqlite_store_module
from abstractmemory import vector_matrix
from abstractmemory.vector_matrix import (
    VECTOR_ENGINE_NUMPY,
    VECTOR_ENGINE_PYTHON,
    coarse_margin,
    decode_vector,
    encode_vector,
)
from abstractmemory.vector_scoring import rank_by_cosine

T0 = "2026-01-01T00:00:00.000000+00:00"


def _pin(dim: int) -> dict:
    return {"model_id": f"test-{dim}", "dimension": dim}


def _assertion(i: int, *, scope: str = "life", owner: Optional[str] = "entity:a",
               predicate: str = "ex:p", subject: Optional[str] = None,
               valid_until: Optional[str] = None) -> TripleAssertion:
    return TripleAssertion(
        subject=subject or f"ex:s{i % 13}", predicate=predicate, object=f"value {i}",
        scope=scope, owner_id=owner, observed_at=f"2026-01-01T00:{i // 60 % 60:02d}:{i % 60:02d}.000000+00:00",
        valid_until=valid_until, assertion_id=f"a-{i:05d}")


def _home(path: Path, vectors: List[Optional[List[float]]], dim: int, **row_kw) -> SQLiteTripleStore:
    """A store holding one row per vector (None = vectorless row), vectors
    written through the public `replace_vectors` (float32 BLOBs). Rows
    alternate between two scopes and three owners, every fifth predicate
    differs, so partition and SQL-filtered queries both have work."""
    store = SQLiteTripleStore(path, embedding_pin=_pin(dim))
    owners = ["entity:a", "entity:b", None]
    rows = [_assertion(i, scope="life" if i % 2 == 0 else "diary", owner=owners[i % 3],
                       predicate="ex:q" if i % 5 == 0 else "ex:p",
                       valid_until="2026-01-01T00:30:00+00:00" if i % 7 == 0 else None, **row_kw)
            for i in range(len(vectors))]
    store.add(rows)
    store.replace_vectors(
        {r.assertion_id: v for r, v in zip(rows, vectors) if v is not None}, _pin(dim),
        expected_row_count=len(rows))
    return store


def _reference(path: Path, query: List[float], q: TripleQuery, *, table: str = "triples"):
    """The reference answer, independent of the store's query code: the
    candidate rows in rowid order, `rank_by_cosine` over their decoded
    vectors."""
    where, params = [], []
    if q.scope:
        where.append("scope = ?"); params.append(q.scope)  # noqa: E702
    if q.owner_id:
        where.append("owner_id = ?"); params.append(q.owner_id)  # noqa: E702
    if q.predicate:
        where.append("predicate = ?"); params.append(q.predicate)  # noqa: E702
    if q.active_at:
        where.append("(valid_until IS NULL OR valid_until > ?)"); params.append(q.active_at)  # noqa: E702
    sql = f"SELECT assertion_id, embedding FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with sqlite3.connect(str(path)) as raw:
        rows = raw.execute(sql + " ORDER BY rowid", params).fetchall()
    limit = None if (q.limit or 0) <= 0 else q.limit
    ranked = rank_by_cosine(query, rows, lambda r: decode_vector(r[1]),
                            min_score=q.min_score, limit=limit)
    return [(r[0], s) for s, r in ranked]


def _answer(store: SQLiteTripleStore, q: TripleQuery):
    return [(a.assertion_id, a.attributes["_retrieval"]["score"]) for a in store.query(q)]


def _python_scan(store: SQLiteTripleStore, q: TripleQuery, monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(vector_matrix, "_np", None)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return _answer(store, q)


def _random_vectors(n: int, dim: int, seed: int) -> List[Optional[List[float]]]:
    rng = np.random.default_rng(seed)
    base = rng.standard_normal((n, dim)).astype(np.float32)
    vectors: List[Optional[List[float]]] = [list(map(float, v)) for v in base]
    pick = random.Random(seed)
    for i in range(n):
        roll = pick.random()
        earlier = vectors[pick.randrange(i)] if i > 0 else None
        if roll < 0.15 and earlier is not None:    # exact duplicate of an earlier row: a tie
            vectors[i] = list(earlier)
        elif roll < 0.25 and earlier is not None:  # near-tie: one ulp away in one component
            near = np.asarray(earlier, dtype=np.float32)
            k = pick.randrange(dim)
            near[k] = np.nextafter(near[k], np.float32(np.inf))
            vectors[i] = list(map(float, near))
        elif roll < 0.28:              # zero vector: scores 0.0
            vectors[i] = [0.0] * dim
        elif roll < 0.33:              # vectorless row: skipped by both
            vectors[i] = None
    return vectors


@pytest.mark.parametrize("n,dim", [(1, 3), (7, 3), (300, 16), (1200, 48)])
def test_matrix_ranking_equals_the_reference_scan(tmp_path: Path, n: int, dim: int, monkeypatch) -> None:
    path = tmp_path / "kg.sqlite3"
    vectors = _random_vectors(n, dim, seed=n)
    store = _home(path, vectors, dim)
    rng = np.random.default_rng(1000 + n)
    queries = [list(map(float, rng.standard_normal(dim))) for _ in range(2)]
    queries.append(next(v for v in vectors if v is not None))   # a stored vector: duplicates tie at the top
    queries.append([0.0] * dim)                                   # zero query: every row scores 0.0
    shapes = [
        dict(scope="life", owner_id="entity:a"),
        dict(scope="diary"),
        dict(),
        dict(scope="life", predicate="ex:q"),                     # SQL-filtered candidates
        dict(owner_id="entity:b", active_at="2026-01-01T00:40:00+00:00"),
    ]
    checked = 0
    for qv in queries:
        for shape in shapes:
            for limit in (1, 5, 50, 0):
                for min_score in (None, 0.0, 0.2):
                    q = TripleQuery(query_vector=qv, limit=limit, min_score=min_score, **shape)
                    expected = _reference(path, qv, q)
                    got = _answer(store, q)
                    assert got == expected, (shape, limit, min_score)
                    checked += len(got)
            # A floor EXACTLY at a row's score keeps that row (>=), whatever
            # float32 thinks of it.
            ref = _reference(path, qv, TripleQuery(query_vector=qv, limit=0, **shape))
            for _, floor in ref[:: max(1, len(ref) // 6)]:
                q = TripleQuery(query_vector=qv, limit=0, min_score=floor, **shape)
                assert _answer(store, q) == _reference(path, qv, q)
    assert store.vector_engine == VECTOR_ENGINE_NUMPY
    assert store._vectors is not None and store._vectors.size == sum(v is not None for v in vectors)  # noqa: SLF001
    if n > 1:
        assert checked > 0
    # And the store's own fallback path agrees with the matrix.
    q = TripleQuery(query_vector=queries[0], scope="life", limit=20)
    assert _python_scan(store, q, monkeypatch) == _answer(store, q)
    store.close()


def test_near_ties_at_the_limit_boundary_are_ranked_exactly(tmp_path: Path) -> None:
    """Hundreds of rows one float32 ulp apart from one another: the float32
    pass cannot order them, the exact pass must (mutant: margin 0)."""
    dim = 384
    rng = np.random.default_rng(5)
    base = rng.standard_normal(dim).astype(np.float32)
    vectors = []
    for i in range(400):
        v = base.copy()
        for k in random.Random(i).sample(range(dim), 3):
            v[k] = np.nextafter(v[k], np.float32(np.inf if i % 2 else -np.inf))
        vectors.append(list(map(float, v)))
    path = tmp_path / "kg.sqlite3"
    store = _home(path, vectors, dim)
    query = list(map(float, base.astype(np.float64) + rng.standard_normal(dim) * 1e-3))
    for limit in (1, 3, 10, 40):
        q = TripleQuery(query_vector=query, limit=limit)
        assert _answer(store, q) == _reference(path, query, q), limit
    ref = _reference(path, query, TripleQuery(query_vector=query, limit=0))
    for _, floor in ref[::20]:
        q = TripleQuery(query_vector=query, limit=0, min_score=floor)
        assert _answer(store, q) == _reference(path, query, q)
    store.close()


def test_coarse_margin_covers_the_float32_bound() -> None:
    assert coarse_margin(3) == vector_matrix.COARSE_MARGIN_FLOOR
    assert coarse_margin(384) == vector_matrix.COARSE_MARGIN_FLOOR
    # Wide embeddings outgrow the floor: twice gamma_(dim + 4) for float32.
    n = (65536 + 4) * 2.0 ** -24
    assert coarse_margin(65536) == pytest.approx(2 * n / (1 - n))
    assert coarse_margin(65536) > 2 * (65536 + 4) * 2.0 ** -24


def test_a_second_handle_appends_rows_another_handle_wrote(tmp_path: Path) -> None:
    dim = 8
    path = tmp_path / "kg.sqlite3"
    rng = np.random.default_rng(2)
    writer = _home(path, [list(map(float, rng.standard_normal(dim))) for _ in range(200)], dim)
    reader = SQLiteTripleStore(path)
    query = list(map(float, rng.standard_normal(dim)))
    q = TripleQuery(query_vector=query, limit=0)
    assert len(_answer(reader, q)) == 200
    matrix = reader._vectors  # noqa: SLF001 - observing the cache
    assert matrix is not None and matrix.rows_read == 200

    class Fixed:
        model = "test-8"

        def __init__(self) -> None:
            self.next: List[List[float]] = []

        def embed_texts(self, texts):
            return [self.next.pop(0) for _ in texts]

    emb = Fixed()
    writer._embedder = emb  # noqa: SLF001 - the writer embeds its new rows
    emb.next = [list(map(float, rng.standard_normal(dim))) for _ in range(5)]
    writer.add([_assertion(1000 + i) for i in range(5)])
    got = _answer(reader, q)
    assert len(got) == 205 and {f"a-{1000 + i:05d}" for i in range(5)} <= {a for a, _ in got}
    assert reader._vectors is matrix  # noqa: SLF001 - same cache, appended
    assert matrix.rows_read == 205, "only the 5 new rows were read"
    assert got == _reference(path, query, q)

    # The handle's own add appends too (no rebuild at the next query).
    reader._embedder = emb  # noqa: SLF001
    emb.next = [list(map(float, rng.standard_normal(dim))) for _ in range(3)]
    reader.add([_assertion(2000 + i) for i in range(3)])
    assert reader._vectors is matrix and matrix.rows_read == 208  # noqa: SLF001
    assert _answer(reader, q) == _reference(path, query, q)
    writer.close()
    reader.close()


def test_replace_vectors_from_another_handle_rebuilds_the_cache(tmp_path: Path) -> None:
    dim = 4
    path = tmp_path / "kg.sqlite3"
    old = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]
    writer = _home(path, old, dim)
    reader = SQLiteTripleStore(path)
    q = TripleQuery(query_vector=[1.0, 0.0, 0.0, 0.0], limit=1)
    assert [a for a, _ in _answer(reader, q)] == ["a-00000"]
    # Same pin, new vectors: only `vector_generation` says the space changed.
    writer.replace_vectors({"a-00000": [0.0, 0.0, 0.0, 1.0], "a-00001": [0.0, 1.0, 0.0, 0.0],
                            "a-00002": [1.0, 0.0, 0.0, 0.0]}, _pin(dim), expected_row_count=3)
    assert _answer(reader, q) == [("a-00002", 1.0)]
    assert _answer(reader, q) == _reference(path, [1.0, 0.0, 0.0, 0.0], q)
    # The writer's own cache follows its own swap.
    assert _answer(writer, q) == [("a-00002", 1.0)]
    writer.close()
    reader.close()


def test_rows_outside_the_float32_bound_are_forced_and_scored_exactly(tmp_path: Path) -> None:
    """A tiny norm, a huge norm and a legacy JSON value beyond float32 cannot
    go through the float32 pass: they are always candidates of the exact
    pass (no fallback), and win when the reference says so."""
    dim = 4
    path = tmp_path / "kg.sqlite3"
    store = _home(path, [[1.0, 0.0, 0.0, 0.0], [1e-30, 1e-30, 0.0, 0.0], [1e20, 1e20, 1.0, 0.0],
                         [0.0, 1.0, 0.0, 0.0], [0.6, 0.8, 0.0, 0.0]], dim)
    with sqlite3.connect(str(path)) as raw:
        raw.execute(
            "INSERT INTO triples (assertion_id, subject, predicate, object, scope, owner_id, "
            "observed_at, embedding) VALUES ('legacy-big', 'ex:x', 'ex:p', 'v', 'life', 'entity:a', ?, ?)",
            (T0, json.dumps([0.0, 0.0, 1e39, 1e39])))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for qv in ([1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0], [1.0, 0.0, 0.0, 0.0]):
            for limit in (1, 2, 0):
                q = TripleQuery(query_vector=qv, limit=limit)
                assert _answer(store, q) == _reference(path, qv, q), (qv, limit)
        top = _answer(store, TripleQuery(query_vector=[1.0, 1.0, 0.0, 0.0], limit=2))
        assert [a for a, _ in top] == ["a-00001", "a-00002"]
        assert _answer(store, TripleQuery(query_vector=[0.0, 0.0, 1.0, 1.0], limit=1))[0][0] == "legacy-big"
    assert store.vector_engine == VECTOR_ENGINE_NUMPY
    store.close()


def test_a_cache_naming_vanished_rows_is_rebuilt_not_served(tmp_path: Path) -> None:
    """The file changed under the handle without a generation bump (rows
    removed by hand): the matrix names ids the table lacks, so it is
    rebuilt once and the answer is the table's, with no fallback."""
    path = tmp_path / "kg.sqlite3"
    store = _home(path, [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 1.0, 0.0]], 3)
    q = TripleQuery(query_vector=[1.0, 0.0, 0.0], limit=2)
    assert [a for a, _ in _answer(store, q)] == ["a-00000", "a-00001"]
    before = store._vectors  # noqa: SLF001
    with sqlite3.connect(str(path)) as raw:
        raw.execute("DELETE FROM triples WHERE assertion_id = 'a-00000'")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert _answer(store, q) == _reference(path, [1.0, 0.0, 0.0], q)
    assert [a for a, _ in _answer(store, q)] == ["a-00001", "a-00002"]
    assert store._vectors is not before  # noqa: SLF001 - rebuilt
    store.close()


# -- in-place upgrade --------------------------------------------------------


def _to_json_encoding(path: Path, *, rewrite: Optional[Dict[str, str]] = None) -> None:
    """Rewrite a home's vectors the way AbstractMemory <= 0.3.2 stored them
    (JSON text, no upgrade cursor)."""
    with sqlite3.connect(str(path)) as raw:
        for rowid, blob in raw.execute(
                "SELECT rowid, embedding FROM triples WHERE embedding IS NOT NULL").fetchall():
            raw.execute("UPDATE triples SET embedding = ? WHERE rowid = ?",
                        (json.dumps(decode_vector(blob), separators=(",", ":")), rowid))
        for aid, text in (rewrite or {}).items():
            raw.execute("UPDATE triples SET embedding = ? WHERE assertion_id = ?", (text, aid))
        raw.execute("DELETE FROM triples_meta WHERE key IN ('vector_blob_high_water', 'vector_generation')")


def _encodings(path: Path) -> Dict[str, str]:
    with sqlite3.connect(str(path)) as raw:
        return dict(raw.execute("SELECT assertion_id, typeof(embedding) FROM triples ORDER BY rowid"))


def _meta(path: Path, key: str) -> Optional[str]:
    with sqlite3.connect(str(path)) as raw:
        row = raw.execute("SELECT value FROM triples_meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def test_a_json_vector_home_is_upgraded_in_place(tmp_path: Path, monkeypatch) -> None:
    dim = 6
    path = tmp_path / "kg.sqlite3"
    rng = np.random.default_rng(3)
    vectors = [list(map(float, rng.standard_normal(dim).astype(np.float32))) for _ in range(23)]
    vectors[4] = None
    _home(path, vectors, dim).close()
    _to_json_encoding(path, rewrite={
        "a-00005": '["x", "y", "z", "u", "v", "w"]',   # non-numeric: left as it is
        "a-00006": json.dumps([1e39] * dim),            # beyond float32: left as it is
    })
    query = list(map(float, rng.standard_normal(dim)))
    q = TripleQuery(query_vector=query, limit=0)
    before = _reference(path, query, q)
    assert set(_encodings(path).values()) == {"text", "null"}

    monkeypatch.setattr(sqlite_store_module, "VECTOR_UPGRADE_BATCH", 4)  # several transactions
    store = SQLiteTripleStore(path)
    kinds = _encodings(path)
    assert kinds["a-00004"] == "null"
    assert kinds["a-00005"] == kinds["a-00006"] == "text"
    assert {k for a, k in kinds.items() if a not in ("a-00004", "a-00005", "a-00006")} == {"blob"}
    assert _meta(path, "vector_blob_high_water") == "23"
    generation = _meta(path, "vector_generation")
    assert generation is not None
    # float32-exact JSON: the BLOB holds the very same values.
    with sqlite3.connect(str(path)) as raw:
        blob = raw.execute("SELECT embedding FROM triples WHERE assertion_id = 'a-00000'").fetchone()[0]
    assert decode_vector(blob) == vectors[0]
    # Same answer as before the upgrade; the leftover rows force the labelled scan.
    with pytest.warns(RuntimeWarning, match="#FALLBACK"):
        assert _answer(store, q) == before
    store.close()

    # Idempotent: a second open rewrites nothing (the generation is unchanged).
    snapshot = _encodings(path)
    SQLiteTripleStore(path).close()
    assert _encodings(path) == snapshot
    assert _meta(path, "vector_generation") == generation


def test_an_interrupted_upgrade_resumes_from_its_cursor(tmp_path: Path, monkeypatch) -> None:
    dim = 3
    path = tmp_path / "kg.sqlite3"
    vectors = [[float(i), 1.0, 0.5] for i in range(10)]
    _home(path, vectors, dim).close()
    _to_json_encoding(path)
    monkeypatch.setattr(sqlite_store_module, "VECTOR_UPGRADE_BATCH", 3)

    # Crash in the second batch: the first batch stays committed with its cursor.
    calls = {"n": 0}
    real = sqlite_store_module.encode_vector

    class Crash(BaseException):
        """A process dying mid-upgrade (not an error the upgrade may handle)."""

    def crashing(vector):
        calls["n"] += 1
        if calls["n"] > 4:
            raise Crash()
        return real(vector)

    monkeypatch.setattr(sqlite_store_module, "encode_vector", crashing)
    with pytest.raises(Crash):
        SQLiteTripleStore(path)
    assert _meta(path, "vector_blob_high_water") == "3"
    kinds = list(_encodings(path).values())
    assert kinds == ["blob"] * 3 + ["text"] * 7

    monkeypatch.setattr(sqlite_store_module, "encode_vector", real)
    store = SQLiteTripleStore(path)
    assert list(_encodings(path).values()) == ["blob"] * 10
    assert _meta(path, "vector_blob_high_water") == "10"
    q = TripleQuery(query_vector=[1.0, 0.0, 0.0], limit=3)
    assert _answer(store, q) == _reference(path, [1.0, 0.0, 0.0], q)
    store.close()


def test_the_upgrade_cursor_is_respected(tmp_path: Path) -> None:
    """Rows at or below `vector_blob_high_water` are never re-read: setting
    the cursor by hand leaves their (JSON) encoding alone, rows above it are
    upgraded."""
    path = tmp_path / "kg.sqlite3"
    _home(path, [[float(i), 1.0, 0.0] for i in range(6)], 3).close()
    _to_json_encoding(path)
    with sqlite3.connect(str(path)) as raw:
        raw.execute("INSERT INTO triples_meta (key, value) VALUES ('vector_blob_high_water', '4')")
    store = SQLiteTripleStore(path)
    assert list(_encodings(path).values()) == ["text"] * 4 + ["blob"] * 2
    # Legacy JSON below the cursor still serves (the matrix keeps its
    # float64 values exactly), together with the BLOB rows.
    q = TripleQuery(query_vector=[0.3, 1.0, 0.0], limit=0)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert _answer(store, q) == _reference(path, [0.3, 1.0, 0.0], q)
    assert store.vector_engine == VECTOR_ENGINE_NUMPY
    store.close()


def test_legacy_float64_json_rows_are_scored_exactly_by_the_matrix(tmp_path: Path) -> None:
    """Rows another writer stored as float64 JSON after this handle opened
    (an older process, or a graph insert path not yet on `encode_vector`)
    are scored with their float64 values: no fallback, reference scores."""
    dim = 32
    path = tmp_path / "kg.sqlite3"
    rng = np.random.default_rng(4)
    store = _home(path, [list(map(float, rng.standard_normal(dim))) for _ in range(50)], dim)
    query = list(map(float, rng.standard_normal(dim)))
    q = TripleQuery(query_vector=query, limit=0)
    _answer(store, q)  # matrix built
    with sqlite3.connect(str(path)) as raw:
        for i in range(10):
            vec = list(map(float, rng.standard_normal(dim)))  # float64, not float32-exact
            raw.execute(
                "INSERT INTO triples (assertion_id, subject, predicate, object, scope, owner_id, "
                "observed_at, embedding) VALUES (?, 'ex:x', 'ex:p', 'v', 'life', 'entity:a', ?, ?)",
                (f"legacy-{i}", T0, json.dumps(vec)))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        got = _answer(store, q)
    assert store.vector_engine == VECTOR_ENGINE_NUMPY
    assert got == _reference(path, query, q)
    assert sum(a.startswith("legacy-") for a, _ in got) == 10
    store.close()


# -- labelled fallback -------------------------------------------------------


def test_without_numpy_the_python_scan_answers_and_warns_once(tmp_path: Path, monkeypatch) -> None:
    dim = 5
    path = tmp_path / "kg.sqlite3"
    rng = np.random.default_rng(6)
    store = _home(path, [list(map(float, rng.standard_normal(dim))) for _ in range(40)], dim)
    query = list(map(float, rng.standard_normal(dim)))
    q = TripleQuery(query_vector=query, scope="life", limit=7)
    with_matrix = _answer(store, q)
    fresh = SQLiteTripleStore(path)
    monkeypatch.setattr(vector_matrix, "_np", None)
    assert fresh.vector_engine == VECTOR_ENGINE_PYTHON
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        first = _answer(fresh, q)
        second = _answer(fresh, q)
    fallback = [w for w in seen if "#FALLBACK" in str(w.message)]
    assert len(fallback) == 1, [str(w.message) for w in seen]
    assert "abstractmemory[fast]" in str(fallback[0].message)
    assert first == second == with_matrix == _reference(path, query, q)
    assert fresh._vectors is None  # noqa: SLF001 - no matrix without numpy
    fresh.close()
    store.close()


def test_an_unrepresentable_vector_falls_back_to_the_scan_with_a_label(tmp_path: Path) -> None:
    dim = 4
    path = tmp_path / "kg.sqlite3"
    store = _home(path, [[1.0, 0.0, 0.0, 0.0], [0.5, 0.5, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dim)
    with sqlite3.connect(str(path)) as raw:  # a 2-dim vector in a 4-dim home
        raw.execute("UPDATE triples SET embedding = ? WHERE assertion_id = 'a-00001'",
                    (encode_vector([0.9, 0.1]),))
    q = TripleQuery(query_vector=[1.0, 0.0, 0.0, 0.0], limit=0)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        got = _answer(store, q)
        assert _answer(store, q) == got
    labels = [str(w.message) for w in seen if "#FALLBACK" in str(w.message)]
    assert len(labels) == 1 and "dimensions" in labels[0], labels
    assert store.vector_engine == VECTOR_ENGINE_PYTHON
    # The reference semantics (cosine over the overlapping prefix) are kept.
    assert got == _reference(path, [1.0, 0.0, 0.0, 0.0], q)
    store.close()


# -- encoding ----------------------------------------------------------------


def test_encode_and_decode_vectors() -> None:
    values = [0.5, -1.25, 3.0, 0.0]
    blob = encode_vector(values)
    assert isinstance(blob, bytes) and len(blob) == 16
    assert decode_vector(blob) == values
    assert decode_vector(json.dumps(values)) == values      # legacy JSON text
    assert decode_vector(None) is None and decode_vector("") is None
    assert decode_vector(b"\x00\x00\x80") is None           # not a whole float32
    assert decode_vector('{"not": "a list"}') is None
    assert decode_vector(encode_vector([0.1]))[0] == float(np.float32(0.1))
    with pytest.raises(ValueError, match="float32 range"):
        encode_vector([1.0, 1e39])
    assert np.isnan(decode_vector(encode_vector([float("nan")]))[0])  # kept, not clipped


def test_new_rows_are_stored_as_float32_blobs(tmp_path: Path) -> None:
    path = tmp_path / "kg.sqlite3"
    store = _home(path, [[1.0, 2.0, 3.0]], 3)
    assert _encodings(path) == {"a-00000": "blob"}
    assert store.stored_vector("a-00000") == [1.0, 2.0, 3.0]
    store.close()


def test_the_fast_extra_the_fallback_names_exists() -> None:
    """The `#FALLBACK` warning tells the operator to install
    `abstractmemory[fast]`: the extra must exist and bring numpy."""
    tomllib = pytest.importorskip("tomllib")
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    extras = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["optional-dependencies"]
    assert any(dep.replace(" ", "").startswith("numpy") for dep in extras["fast"])
