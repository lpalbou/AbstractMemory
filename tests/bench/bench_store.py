"""Home store benchmark (backlog 0058; successor of the 2026-10-27 audit
baseline `untracked/memory-transition/audit/bench_abstractmemory_baseline.py`).

Not a test (pytest does not collect `bench_*.py`): run it by hand to measure
a change BEFORE and AFTER, by pointing PYTHONPATH at the code under test:

    PYTHONPATH=<checkout>/src python tests/bench/bench_store.py \
        --sizes 10000 50000 --backends sqlite
    PYTHONPATH=<checkout>/src python tests/bench/bench_store.py \
        --sizes --system 5000 20000

Every store lives in a TEMPORARY directory deleted afterwards; no network,
no model: vectors come from a deterministic fake 384-d embedder (numpy RNG
seeded by the text hash). One JSON line per run on stdout.

Store level (backend x size, vectors on every row unless --no-vectors):
  batch add (1000-row chunks), single add, subject+scope+owner query, object
  query, subject as-of, scope as-of, scope latest-100, scope full scan
  (limit=0), close_assertion, vector query (first = cache build, then warm),
  vector query after one more add (the append path), reopen + first vector
  query, the in-place JSON -> BLOB upgrade of the whole home (when the code
  under test has it), on-disk size.
System level (--system N ...): MemorySystem over SQLiteTripleStore +
  SQLiteJournal in one file: remember_many, reconstruct, probe,
  maintenance_due (first call, then repeated with no new material, then
  after one new record).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sqlite3
import statistics
import tempfile
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

warnings.simplefilter("ignore")

import abstractmemory  # noqa: E402
from abstractmemory import (  # noqa: E402
    SQLiteTripleStore,
    TripleAssertion,
    TripleQuery,
)

DIM = 384
N_SUBJECTS = 2000
PREDICATES = [f"ex:p{i}" for i in range(20)]
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeEmbedder:
    """Deterministic random unit vectors; no network, no model."""

    model = "fake-random-384"

    def __init__(self) -> None:
        self.calls = 0
        self.texts = 0

    def embed_texts(self, texts):
        self.calls += 1
        self.texts += len(texts)
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(DIM).astype(np.float32)
            v /= np.linalg.norm(v)
            out.append(v.tolist())
        return out


def ts(i: int) -> str:
    return (T0 + timedelta(seconds=i)).isoformat(timespec="microseconds")


def make_assertions(n: int, start: int = 0):
    rnd = random.Random(42 + start)
    rows = []
    for i in range(start, start + n):
        s = f"ex:s{rnd.randrange(N_SUBJECTS)}"
        p = PREDICATES[rnd.randrange(len(PREDICATES))]
        literal = rnd.random() < 0.5
        o = (f"Free text object number {i} about topic {rnd.randrange(300)}" if literal
             else f"ex:s{rnd.randrange(N_SUBJECTS)}")
        rows.append(TripleAssertion(
            subject=s, predicate=p, object=o, scope="session", owner_id="bench",
            observed_at=ts(i), valid_from=ts(i),
            confidence=0.9,
            provenance={"run_id": f"run-{i // 100}", "step_id": f"step-{i}", "source": "bench"},
            attributes={"literal": True} if literal else {},
        ))
    return rows


def timeit(fn, repeat: int):
    samples = []
    out = None
    for _ in range(repeat):
        t = time.perf_counter()
        out = fn()
        samples.append(time.perf_counter() - t)
    return samples, out


def ms(samples):
    return {
        "n": len(samples),
        "mean_ms": round(statistics.mean(samples) * 1000, 3),
        "p50_ms": round(statistics.median(samples) * 1000, 3),
        "max_ms": round(max(samples) * 1000, 3),
    }


def dir_size(path: Path) -> int:
    if path.is_file():
        total = path.stat().st_size
        for suffix in ("-wal", "-shm"):
            side = Path(str(path) + suffix)
            if side.exists():
                total += side.stat().st_size
        return total
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def open_store(backend: str, root: Path, embedder):
    if backend == "sqlite":
        path = root / "kg.sqlite3"
        return SQLiteTripleStore(path, embedder=embedder), path
    from abstractmemory import LanceDBTripleStore
    path = root / "kg"
    return LanceDBTripleStore(str(path), embedder=embedder), path


def _rewrite_vectors_as_json(path: Path) -> int:
    """Turn a home into the pre-0058 encoding (JSON text vectors, no upgrade
    cursor), the way an older AbstractMemory wrote it."""
    from abstractmemory.vector_matrix import decode_vector

    with sqlite3.connect(str(path)) as raw:
        rows = raw.execute(
            "SELECT rowid, embedding FROM triples WHERE typeof(embedding) = 'blob'").fetchall()
        raw.executemany(
            "UPDATE triples SET embedding = ? WHERE rowid = ?",
            [(json.dumps(decode_vector(e), separators=(",", ":")), r) for r, e in rows])
        raw.execute("DELETE FROM triples_meta WHERE key = 'vector_blob_high_water'")
    return len(rows)


def bench_store(backend: str, size: int, *, vectors: bool) -> dict:
    root = Path(tempfile.mkdtemp(prefix=f"am-bench-{backend}-"))
    res: dict = {"backend": backend, "size": size, "vectors": vectors}
    try:
        emb = FakeEmbedder() if vectors else None
        store, path = open_store(backend, root, emb)
        data = make_assertions(size)
        t = time.perf_counter()
        ids = []
        for k in range(0, size, 1000):
            ids.extend(store.add(data[k:k + 1000]))
        res["batch_add_total_s"] = round(time.perf_counter() - t, 3)
        res["batch_add_per_row_us"] = round(res["batch_add_total_s"] / size * 1e6, 1)
        extra = make_assertions(100, start=size)
        samples = []
        for a in extra:
            t = time.perf_counter()
            ids.append(store.add([a])[0])
            samples.append(time.perf_counter() - t)
        res["single_add"] = ms(samples)
        rnd = random.Random(7)
        subjects = [f"ex:s{rnd.randrange(N_SUBJECTS)}" for _ in range(100)]
        mid = ts(size // 2)

        def guard(name, fn, repeat, rows_key=None):
            try:
                s, out = timeit(fn, repeat)
                res[name] = ms(s)
                if rows_key:
                    res[rows_key] = len(out)
            except Exception as e:  # record, never hide
                res[name] = f"ERROR {type(e).__name__}: {str(e)[:160]}"

        it = iter(subjects * 10)
        guard("query_by_subject", lambda: store.query(TripleQuery(subject=next(it), scope="session", owner_id="bench", limit=100)), 50, "query_by_subject_rows_last")
        it_o = iter(subjects * 10)
        guard("query_by_object", lambda: store.query(TripleQuery(object=next(it_o), limit=100)), 50)
        it_a = iter(subjects * 10)
        guard("query_subject_as_of", lambda: store.query(TripleQuery(subject=next(it_a), active_at=mid, limit=100)), 50)
        guard("query_scope_as_of_limit100", lambda: store.query(TripleQuery(scope="session", owner_id="bench", active_at=mid, limit=100)), 5)
        guard("query_scope_recent_limit100", lambda: store.query(TripleQuery(scope="session", owner_id="bench", limit=100)), 5)
        guard("scope_full_scan_limit0", lambda: store.query(TripleQuery(scope="session", owner_id="bench", limit=0)), 2, "scope_full_scan_rows")
        if hasattr(store, "close_assertion"):
            it2 = iter(ids[:100])
            guard("close_assertion", lambda: store.close_assertion(next(it2), ts(size + 1000)), 100)
            guard("query_scope_as_of_after_close", lambda: store.query(TripleQuery(scope="session", owner_id="bench", active_at=ts(size + 2000), limit=100)), 5)
        else:
            res["close_assertion"] = "NOT IMPLEMENTED on this backend"
        if vectors:
            qv = FakeEmbedder().embed_texts(["query text"])[0]
            vq = TripleQuery(scope="session", owner_id="bench", query_vector=qv, limit=20)
            guard("vector_query_first", lambda: store.query(vq), 1)
            guard("vector_query_limit20", lambda: store.query(vq), 5, "vector_query_rows")
            res["vector_engine"] = getattr(store, "vector_engine", "n/a (pre-0058)")
            more = iter(make_assertions(5, start=size + 500))
            guard("vector_query_after_one_add", lambda: (store.add([next(more)]), store.query(vq)), 5)
        store.close()
        res["disk_bytes"] = dir_size(path)
        if vectors and backend == "sqlite":
            t = time.perf_counter()
            again = SQLiteTripleStore(path, embedder=emb)
            res["reopen_ms"] = round((time.perf_counter() - t) * 1000, 3)
            guard("vector_query_after_reopen_first", lambda: again.query(vq), 1)
            again.close()
            if hasattr(SQLiteTripleStore, "_upgrade_vector_encoding"):
                res["upgrade_rows_rewritten_as_json"] = _rewrite_vectors_as_json(path)
                t = time.perf_counter()
                upgraded = SQLiteTripleStore(path, embedder=emb)
                res["upgrade_open_s"] = round(time.perf_counter() - t, 3)
                t = time.perf_counter()
                upgraded.close()
                SQLiteTripleStore(path, embedder=emb).close()
                res["upgrade_second_open_ms"] = round((time.perf_counter() - t) * 1000, 3)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return res


def bench_system(n_records: int) -> dict:
    from abstractmemory import MemoryRecordInput, MemorySystem, SQLiteJournal, Stimulus
    from abstractmemory import maintenance_due

    root = Path(tempfile.mkdtemp(prefix="am-bench-system-"))
    res: dict = {"records": n_records}
    try:
        path = root / "memory.sqlite3"
        emb = FakeEmbedder()
        store = SQLiteTripleStore(path, embedder=emb)
        journal = SQLiteJournal(path)
        ms_ = MemorySystem(store=store, journal=journal, embedder=emb)
        rnd = random.Random(3)
        t = time.perf_counter()
        formed = []
        batch = 50

        def remember(k, n):
            recs = []
            for j in range(n):
                i = k + j
                edges = ()
                if formed and rnd.random() < 0.6:
                    edges = (("relates_to", formed[rnd.randrange(len(formed))]),)
                recs.append(MemoryRecordInput(
                    kind="episode", title=f"Episode {i} topic {rnd.randrange(200)}",
                    digest=f"Something happened with person {rnd.randrange(100)} about topic {rnd.randrange(200)} in turn {i}.",
                    keywords=(f"topic{rnd.randrange(200)}",), edges=edges,
                    provenance={"run_id": f"run-{k}", "source": "bench"}))
            formed.extend(ms_.remember_many(recs, scope="life", owner_id="bench", idempotency_key=f"bench-{k}"))

        for k in range(0, n_records, batch):
            remember(k, batch)
        res["remember_many_total_s"] = round(time.perf_counter() - t, 3)
        res["store_rows"] = len(store.query(TripleQuery(limit=0)))
        for rid in formed[:200]:
            ms_.close_record(rid, reason="bench retract")
        stim = Stimulus(cue_text="person 12 about topic 33")
        samples, out = timeit(lambda: ms_.reconstruct(stim, scopes=[("life", "bench")]), 3)
        res["reconstruct"] = ms(samples)
        res["reconstruct_handles"] = len(out.handles)
        samples, _ = timeit(lambda: ms_.probe(stim, scopes=[("life", "bench")], reason="bench"), 3)
        res["probe"] = ms(samples)
        scopes = [("life", "bench")]
        samples, due = timeit(lambda: maintenance_due(store, journal, scopes=scopes), 1)
        res["maintenance_due_first"] = ms(samples)
        res["maintenance_due_answer"] = {k: due[k] for k in ("due", "new_records", "signal", "since_seq")}
        samples, _ = timeit(lambda: maintenance_due(store, journal, scopes=scopes), 3)
        res["maintenance_due"] = ms(samples)
        remember(n_records, 1)
        samples, due = timeit(lambda: maintenance_due(store, journal, scopes=scopes), 1)
        res["maintenance_due_after_one_record"] = ms(samples)
        res["maintenance_due_answer_after"] = {k: due[k] for k in ("due", "new_records", "signal", "since_seq")}
        res["vector_engine"] = getattr(store, "vector_engine", "n/a (pre-0058)")
        res["embed_calls"] = emb.calls
        ms_.close()
        store.close()
        res["disk_bytes"] = dir_size(path)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="*", type=int, default=[10000, 50000])
    ap.add_argument("--backends", nargs="*", default=["sqlite"])
    ap.add_argument("--no-vectors", action="store_true")
    ap.add_argument("--system", nargs="*", type=int, default=[],
                    help="record counts for the MemorySystem bench (none = skip)")
    args = ap.parse_args()
    print(json.dumps({"abstractmemory": abstractmemory.__file__, "numpy": np.__version__}), flush=True)
    for backend in args.backends:
        if backend == "lancedb":
            try:
                import lancedb  # noqa: F401
            except Exception as e:
                print(json.dumps({"backend": "lancedb", "skipped": str(e)}))
                continue
        for size in args.sizes:
            t = time.perf_counter()
            r = bench_store(backend, size, vectors=not args.no_vectors)
            r["wall_s"] = round(time.perf_counter() - t, 2)
            print(json.dumps(r), flush=True)
    for n in args.system:
        t = time.perf_counter()
        r = bench_system(n)
        r["wall_s"] = round(time.perf_counter() - t, 2)
        print(json.dumps({"system": r}), flush=True)


if __name__ == "__main__":
    main()
