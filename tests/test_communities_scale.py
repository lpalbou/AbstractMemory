"""Communities at real and large sizes (COMMUNITIES-DESIGN.md §5 envelope; Fable deltas D1, D6, F9): measured and
printed (run with -s to read the numbers).

- the castor copy (graph-topics/castor-copy, a read-only copy of a lived home, copied into tmp_path; skipped where the
  operator's copy is absent): one cold pass and one warm pass, timings per step, the partition (sizes, modularity,
  diary-dominated communities: reported, not asserted - Fable F5 / delta D1 detects over every vectored record),
  `unvectored` and `unplaced`; warm pass <= 2 s (the design says ~1 s);
- the warm start measured (delta D6): the newest 5 % of castor held out, a version formed without them, then the
  whole life detected SEEDED from that version vs FRESH; keys and node memberships kept, printed; seeded keeps
  >= 60 % of the keys and >= 95 % of the memberships, and more than fresh (RED: the warm start disabled);
- a 10 000-record synthetic home (200 subjects): the whole pass under a generous ceiling (120 s), timings printed.

MUTATION LIST (scratch copy untracked/communities/mut, runner untracked/communities/mutate.py; all red, source
restored): M11 the warm start disabled; M12 the detection not iterated to its fixed point (a rerun on the unchanged
castor writes again).
"""

from __future__ import annotations

import hashlib
import shutil
import time
import warnings
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import MemoryRecordInput, MemorySystem, SQLiteJournal, SQLiteTripleStore  # noqa: E402
from abstractmemory import communities as C  # noqa: E402

from test_communities import author_fn  # noqa: E402

CASTOR = Path(__file__).resolve().parents[2] / "untracked/finish-plan-2026-11-09/graph-topics/castor-copy/memory.sqlite3"
CASTOR_OWNER = "entity:castor@home-fd023c86"
CASTOR_SCOPES = [("life", CASTOR_OWNER), ("self", CASTOR_OWNER), ("diary", CASTOR_OWNER)]

needs_castor = pytest.mark.skipif(not CASTOR.exists(), reason=f"the operator's castor copy is not here ({CASTOR})")


def _castor(tmp_path):
    path = tmp_path / "castor.sqlite3"
    shutil.copyfile(CASTOR, path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return MemorySystem(store=SQLiteTripleStore(path), journal=SQLiteJournal(path), task_queue=True)


def _pass(system, scopes, owner, **kw):
    kw.setdefault("cancelled", lambda: False)
    kw.setdefault("author", author_fn())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return C.communities_pass(system, scopes=scopes, owner_id=owner, **kw)


def _line(r) -> str:
    keys = ("communities", "new", "kept", "dissolved", "unchanged", "written", "moved_in", "moved_out", "detected",
            "attached", "provisional", "unvectored_count", "unplaced_count", "authored", "pending", "modularity",
            "elapsed_ms")
    return " ".join(f"{k}={r[k]}" for k in keys) + f"\n    timings_ms={r['timings_ms']}"


@needs_castor
def test_castor_cold_and_warm(tmp_path) -> None:
    system = _castor(tmp_path)
    g = C.read_community_graph(system, scopes=CASTOR_SCOPES, owner_id=CASTOR_OWNER)
    det = C.detect_communities(g)
    sizes = [len(x) for x in det.groups]
    diary = [round(sum(1 for m in grp if g.nodes[m].kind == "diary") / len(grp), 2) for grp in det.groups]
    print(f"\ncastor: {len(g.nodes)} open records, {len(g.vec_ids)} vectored, {len(g.engraved)} engraved relations, "
          f"{det.knn_edges} kNN edges, detection over {det.detection_nodes}, {det.rounds} rounds")
    print(f"  {len(sizes)} communities, Q {det.modularity}, sizes {sizes}")
    print(f"  diary share {diary}: {sum(1 for d in diary if d > 0.6)} communities > 60 % diary")
    cold = _pass(system, CASTOR_SCOPES, CASTOR_OWNER)
    print("  cold:", _line(cold))
    warm = _pass(system, CASTOR_SCOPES, CASTOR_OWNER)
    print("  warm:", _line(warm))
    assert cold["communities"] == len(sizes) and cold["written"] == len(sizes)
    assert cold["unvectored_count"] == len(g.nodes) - len(g.vec_ids) > 0  # I12
    assert warm["written"] == 0 and warm["version_seq"] is None
    assert warm["elapsed_ms"] < 2000.0
    members = [m for c in C.community_records(system, scopes=CASTOR_SCOPES, owner_id=CASTOR_OWNER) for m in c.members]
    assert len(members) == len(set(members)) == len(g.nodes) - cold["unplaced_count"]


def _without(g: "C.CommunityGraph", drop: set) -> "C.CommunityGraph":
    keep = [i for i, r in enumerate(g.vec_ids) if r not in drop]
    return C.CommunityGraph(
        nodes={k: v for k, v in g.nodes.items() if k not in drop},
        engraved=[e for e in g.engraved if e[0] not in drop and e[2] not in drop],
        vec_ids=[g.vec_ids[i] for i in keep], vectors=g.vectors[keep], space=g.space, seq=g.seq, previous=[])


def _as_previous(g, groups):
    out = []
    for (key, _p, _j), grp in zip(C.match_keys(groups, []), groups):
        rows = [g.vindex[m] for m in grp if m in g.vindex]
        out.append(C.PreviousCommunity(key=key, members={m: {"id": m, "via": v, "since_seq": 0}
                                                         for m, v in grp.items()},
                                       centroid=C._unit_mean(np, g.vectors[rows]) if rows else None))
    return out


def _kept(prev, groups):
    matched = C.match_keys(groups, prev)
    old = {m: p.key for p in prev for m in p.members}
    new = {m: key for (key, _p, _j), grp in zip(matched, groups) for m in grp}
    keys = sum(1 for _k, p, _j in matched if p is not None) / max(1, len(prev))
    nodes = sum(1 for m, k in old.items() if new.get(m) == k) / max(1, len(old))
    return keys, nodes


@needs_castor
def test_castor_warm_start_vs_fresh_under_five_percent_growth(tmp_path) -> None:
    system = _castor(tmp_path)
    g = C.read_community_graph(system, scopes=CASTOR_SCOPES, owner_id=CASTOR_OWNER)
    newest = sorted(g.nodes.values(), key=lambda n: (n.observed_at, n.id))[-max(1, len(g.nodes) // 20):]
    before = _without(g, {n.id for n in newest})
    prev = _as_previous(before, C.detect_communities(before, seed_previous=False).groups)
    g.previous = prev
    t = time.perf_counter()
    seeded = C.detect_communities(g, seed_previous=True)
    t_seeded = (time.perf_counter() - t) * 1000.0
    t = time.perf_counter()
    fresh = C.detect_communities(g, seed_previous=False)
    t_fresh = (time.perf_counter() - t) * 1000.0
    ks, ns = _kept(prev, seeded.groups)
    kf, nf = _kept(prev, fresh.groups)
    print(f"\ncastor + 5 % ({len(newest)} records) after a version of {len(prev)} communities:")
    print(f"  seeded: {len(seeded.groups)} communities, keys kept {ks:.0%}, memberships kept {ns:.0%}, "
          f"{seeded.rounds} rounds, detect {t_seeded:.0f} ms")
    print(f"  fresh:  {len(fresh.groups)} communities, keys kept {kf:.0%}, memberships kept {nf:.0%}, "
          f"{fresh.rounds} rounds, detect {t_fresh:.0f} ms")
    assert ks >= 0.6 and ns >= 0.95  # measured 2026-11-10: seeded 100 % / 99 %, fresh 93 % / 93 %
    assert ks >= kf and ns > nf


def _synthetic(tmp_path, topics: int, per: int, dim: int = 64):
    centers = np.random.default_rng(7).standard_normal((topics, dim))
    centers /= np.linalg.norm(centers, axis=1, keepdims=True)

    class Emb:
        model = f"synthetic-{dim}"

        def embed_texts(self, texts):
            out = []
            for text in texts:
                t = int(text.split("subject-", 1)[1].split()[0])
                seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
                v = centers[t] + 0.06 * np.random.default_rng(seed).standard_normal(dim)
                out.append((v / np.linalg.norm(v)).tolist())
            return out

    path = tmp_path / "big.sqlite3"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        system = MemorySystem(store=SQLiteTripleStore(path, embedder=Emb()), journal=SQLiteJournal(path),
                              task_queue=True)
        for t in range(topics):
            recs = [MemoryRecordInput(kind="episode", title=f"Item {t}.{i}", digest=f"About subject-{t} number {i}.",
                                      edges=(("continues", f"local:{i - 1}"),) if i else ()) for i in range(per)]
            system.remember_many(recs, scope="life", owner_id="entity:big", idempotency_key=f"s{t}")
    return system


def test_ten_thousand_records(tmp_path) -> None:
    t = time.perf_counter()
    system = _synthetic(tmp_path, 200, 50)
    built = (time.perf_counter() - t)
    r = _pass(system, [("life", "entity:big")], "entity:big")
    print(f"\n10k synthetic (built in {built:.1f} s): " + _line(r))
    assert r["nodes"] == 10_000 and r["unplaced_count"] == 0
    assert 150 <= r["communities"] <= 250
    assert r["elapsed_ms"] < 120_000.0
