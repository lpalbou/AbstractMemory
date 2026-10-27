"""Provenance / history / change-feed lookups of `abstractmemory.graph` at scale (backlog 0056 "Report").

Builds a TEMPORARY SQLite home (deleted afterwards; never a real home) through `MemoryGraph.apply_revision` only, in
the shape a notebook + entity write: runs of extraction steps, each revision asserting claims sourced by its step and
the note's artifact; derived memories (no sources) built from earlier claims; supersede closes. Then it
times the reads a host makes and checks, at that size, that every keyed read is an index search
(tests/test_graph_performance.py `assert_index_plans`). No model, no network: `--embed` uses the deterministic fake
embedder of `untracked/memory-transition/audit/bench_abstractmemory_baseline.py` (numpy RNG seeded by the text hash).

"Before" is the only provenance lookup a 0.3 home allowed: a scan of the triple table's provenance JSON.

    PYTHONPATH=src python tests/bench/bench_graph.py [--size 50000] [--embed] [--repeat 200]
"""
from __future__ import annotations

import argparse
import hashlib
import random
import shutil
import statistics
import sys
import tempfile
import time
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))  # tests/ (assert_index_plans)
sys.path.insert(0, str(HERE.parents[2] / "src"))

from abstractmemory import SQLiteJournal, SQLiteTripleStore  # noqa: E402
from abstractmemory.graph import MemoryGraph, Revision, RevisionOp  # noqa: E402
from test_graph_performance import assert_index_plans  # noqa: E402

CLAIMS_PER_REVISION = 5
STEPS_PER_RUN = 20
DERIVED_SHARE = 0.10     # a tenth of the assertions are derived memories (no sources)
DIM = 384


class FakeEmbedder:
    """Deterministic random unit vectors; no network, no model (the audit bench's pattern)."""

    model = "fake-random-384"

    def embed_texts(self, texts):
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(DIM).astype(np.float32)
            out.append((v / np.linalg.norm(v)).tolist())
        return out


def ts(i: int) -> str:
    return f"2026-{1 + (i // 100000) % 12:02d}-{1 + (i // 4000) % 28:02d}T{(i // 160) % 24:02d}:{(i // 3) % 60:02d}:" \
           f"{i % 60:02d}+00:00"


def build(graph: MemoryGraph, size: int, rnd: random.Random) -> dict:
    n_derived = int(size * DERIVED_SHARE)
    n_sourced = size - n_derived
    sourced_ids, derived_ids, closes = [], [], 0
    t0 = time.perf_counter()
    revisions = 0
    i = 0
    while len(sourced_ids) < n_sourced:
        run, seq = f"run-{revisions // STEPS_PER_RUN:05d}", revisions % STEPS_PER_RUN
        ops = []
        for k in range(CLAIMS_PER_REVISION):
            aid = f"m-{i}"
            ops.append(RevisionOp("assert", {"assertion_id": aid, "subject": f"ex:s{rnd.randrange(2000)}",
                                             "predicate": f"ex:p{rnd.randrange(20)}", "object": f"value {i}",
                                             "valid_from": ts(i)}))
            sourced_ids.append(aid)
            i += 1
        if revisions % 9 == 8 and len(sourced_ids) > 50:  # a supersession now and then
            old = sourced_ids[rnd.randrange(len(sourced_ids) - CLAIMS_PER_REVISION)]
            ops.append(RevisionOp("close", {"assertion_id": old, "valid_until": ts(i), "kind": "supersede",
                                            "replacement_ids": [ops[0].payload["assertion_id"]],
                                            "reason": "a later note"}))
            closes += 1
        graph.apply_revision(Revision(
            revision_id=f"rev-{revisions}", scope="global", owner_id="abstractnote", cause="ingest",
            occurred_at=ts(i), ops=tuple(ops),
            provenance={"sources": [{"kind": "step", "run_id": run, "seq": seq},
                                    {"kind": "artifact", "artifact_id": f"note-{revisions}", "run_id": run}],
                        "actor": "abstractnote"}))
        revisions += 1
    while len(derived_ids) < n_derived:
        ops = []
        for k in range(CLAIMS_PER_REVISION):
            aid = f"d-{len(derived_ids)}"
            parents = [sourced_ids[rnd.randrange(len(sourced_ids))] for _ in range(2)]
            ops.append(RevisionOp("assert", {
                "assertion_id": aid, "subject": f"ex:s{rnd.randrange(2000)}", "predicate": "ex:pattern",
                "object": f"pattern {aid}",
                "provenance": {"derived_from": parents, "actor": "abstractmemory:sleep"}}))
            derived_ids.append(aid)
        graph.apply_revision(Revision(
            revision_id=f"rev-{revisions}", scope="global", owner_id="abstractnote", cause="maintenance",
            occurred_at=ts(i), ops=tuple(ops),
            provenance={"derived_from": [ops[0].payload["provenance"]["derived_from"][0]],
                        "actor": "abstractmemory:sleep"}))
        revisions += 1
    build_s = time.perf_counter() - t0
    return {"sourced": sourced_ids, "derived": derived_ids, "revisions": revisions, "closes": closes,
            "build_s": build_s, "runs": (revisions - len(derived_ids) // CLAIMS_PER_REVISION)
            // STEPS_PER_RUN}


def timeit(fn, args_list):
    samples = []
    out = None
    for args in args_list:
        t = time.perf_counter()
        out = fn(*args)
        samples.append((time.perf_counter() - t) * 1000.0)
    samples.sort()
    return {"median_ms": statistics.median(samples), "p95_ms": samples[int(0.95 * (len(samples) - 1))],
            "n": len(samples), "last_len": len(out) if hasattr(out, "__len__") else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=50000)
    ap.add_argument("--repeat", type=int, default=200)
    ap.add_argument("--embed", action="store_true")
    args = ap.parse_args()
    warnings.simplefilter("ignore")
    rnd = random.Random(7)
    root = Path(tempfile.mkdtemp(prefix="bench-graph-"))
    try:
        path = root / "home.sqlite3"
        store = SQLiteTripleStore(path, embedder=FakeEmbedder() if args.embed else None)
        journal = SQLiteJournal(path)
        graph = MemoryGraph(store, journal)
        info = build(graph, args.size, rnd)
        n_rev = info["revisions"]
        n_sourced_revs = n_rev - len(info["derived"]) // CLAIMS_PER_REVISION
        print(f"built {args.size} assertions in {n_rev} revisions ({info['closes']} closes) in "
              f"{info['build_s']:.1f}s = {n_rev / info['build_s']:.0f} revisions/s, "
              f"{args.size / info['build_s']:.0f} assertions/s; embed={args.embed}; "
              f"file {sum(p.stat().st_size for p in root.iterdir()) / 1e6:.1f} MB")
        plans = assert_index_plans(graph)
        R = args.repeat
        steps = [({"kind": "step", "run_id": f"run-{r // STEPS_PER_RUN:05d}", "seq": r % STEPS_PER_RUN + 1},)
                 for r in (rnd.randrange(n_sourced_revs) for _ in range(R))]
        runs = [({"kind": "run", "run_id": f"run-{rnd.randrange(n_sourced_revs // STEPS_PER_RUN):05d}"},)
                for _ in range(R)]
        sourced = [(info["sourced"][rnd.randrange(len(info["sourced"]))],) for _ in range(R)]
        derived = [(info["derived"][rnd.randrange(len(info["derived"]))],) for _ in range(R)]
        cursors = [(str(rnd.randrange(n_rev)),) for _ in range(R)]
        rows = {
            "derived_from_source(step)": timeit(lambda r: graph.derived_from_source(r), steps),
            "derived_from_source(run)": timeit(lambda r: graph.derived_from_source(r), runs),
            "sources_of(sourced memory)": timeit(lambda m: graph.sources_of(m), sourced),
            "sources_of(derived, transitive)": timeit(lambda m: graph.sources_of(m), derived),
            "history(memory)": timeit(lambda m: graph.history(m), sourced),
            "revisions(after=cursor, limit=100)": timeit(lambda c: graph.revisions(after=c, limit=100)[0], cursors),
            "apply_revision (replay no-op)": timeit(
                lambda c: [graph.apply_revision(r) for r in graph.revisions(after=c, limit=1)[0]], cursors[:50]),
        }

        if args.embed:  # graph-written rows are float32 BLOBs: the store's matrix cache serves them (0058)
            from abstractmemory import TripleQuery

            probes = [(FakeEmbedder().embed_texts([f"probe {k}"])[0],) for k in range(20)]
            store.query(TripleQuery(query_vector=probes[0][0], scope="global", limit=20))  # builds the matrix
            rows["vector query, limit 20 (" + store.vector_engine + ")"] = timeit(
                lambda v: store.query(TripleQuery(query_vector=v, scope="global", limit=20)), probes)

        def before(run):  # the 0.3 way: scan every row's provenance JSON for the run id
            return store._conn.execute(f"SELECT assertion_id FROM triples WHERE provenance_json LIKE ?",
                                       (f'%"{run["run_id"]}"%',)).fetchall()

        rows["BEFORE: provenance_json scan by run"] = timeit(before, runs[:20])
        print(f"\n| read @ {args.size} assertions | median ms | p95 ms | n | rows returned (last) |")
        print("|---|---:|---:|---:|---:|")
        for name, r in rows.items():
            print(f"| {name} | {r['median_ms']:.3f} | {r['p95_ms']:.3f} | {r['n']} | {r['last_len']} |")
        print("\nplans:")
        for name, plan in plans.items():
            print(f"  {name}: {plan}")
        journal.close()
        store.close()
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
