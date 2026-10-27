"""The graph's reads are index reads (ADR 0003 "Validation": provenance lookups by ref key are index reads).

These pin the SHAPE of every keyed read `abstractmemory.graph` runs on SQLite (`_SQLiteBackend.sql`, the exact SQL
that executes), not wall-clock numbers: those come from `tests/bench/bench_graph.py` (50,000 assertions, numbers in
backlog 0056 "Report"). A read added to the graph without a plan expectation here fails
`test_every_graph_read_has_a_plan_expectation`.

Mutants (applied by hand to `_SQLiteBackend._ensure_graph_schema`; each turned the named test red):
- the `idx_<prov>_ref_key` index not created        -> test_every_graph_read_is_an_index_search[*] (with_ref_key: SCAN)
- the `idx_<prov>_run_id` index not created         -> test_every_graph_read_is_an_index_search[*] (with_run: SCAN)
- the `idx_<hist>_memory` index not created         -> test_every_graph_read_is_an_index_search[*] (history: SCAN)
- the `idx_<der>_from` index not created            -> test_every_graph_read_is_an_index_search[*] (children: SCAN)
- provenance PRIMARY KEY (ref_key, memory_id)       -> test_every_graph_read_is_an_index_search[*] (sources: SCAN)
- the `idx_<rev>_pending` partial index not created -> test_every_graph_read_is_an_index_search[*] (repair: SCAN)
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest

from abstractmemory import SQLiteTripleStore
from abstractmemory.graph import MemoryGraph

from graph_support import claim, close, prov, rev, step


def expected_plans(graph: MemoryGraph) -> Dict[str, List[str]]:
    """Per read: the plan fragments that must appear (the index and the bound key)."""
    b = graph._b
    rev_uq, prov_pk, der_pk = (f"sqlite_autoindex_{t}_1" for t in (b.t_rev, b.t_prov, b.t_der))
    hist_ix = f"idx_{b.t_hist}_memory (memory_id=?)"
    return {
        "revision_seq": [f"{rev_uq} (revision_id=?)"],
        "memory_known": [hist_ix],
        "closing_revision": [hist_ix],
        "history": [hist_ix, f"{rev_uq} (revision_id=?)"],
        "sources": [f"{prov_pk} (memory_id=?)"],
        "parents": [f"{der_pk} (memory_id=?)"],
        "children": [f"idx_{b.t_der}_from (from_id=?)"],
        "with_ref_key": [f"idx_{b.t_prov}_ref_key (ref_key=?)"],
        "with_run": [f"idx_{b.t_prov}_run_id (run_id=?)"],
        "revisions_page": ["INTEGER PRIMARY KEY (rowid>?)"],
        "pending_journal": [f"USING INDEX idx_{b.t_rev}_pending"],
        "closed_payload": [hist_ix],
    }


#: Reads that walk many rows in order: the index must deliver that order (no sort of the matches).
ORDERED_WALKS = ("history", "children", "with_ref_key", "with_run", "revisions_page", "pending_journal")


def plan_of(graph: MemoryGraph, name: str) -> str:
    sql = graph._b.sql[name]
    rows = graph.store._conn.execute("EXPLAIN QUERY PLAN " + sql, tuple(["x"] * sql.count("?"))).fetchall()
    return " | ".join(str(r[3]) for r in rows)


def assert_index_plans(graph: MemoryGraph) -> Dict[str, str]:
    """Every keyed read is an index search with its expected index; returns the plans (the bench prints them)."""
    plans = {}
    for name, fragments in expected_plans(graph).items():
        plan = plans[name] = plan_of(graph, name)
        for fragment in fragments:
            assert fragment in plan, f"{name}: expected {fragment!r} in plan {plan!r}"
        bare_scan = [p for p in plan.split(" | ") if p.startswith("SCAN") and "USING" not in p]
        assert not bare_scan, f"{name}: a table scan {bare_scan} in {plan!r}"
        if name in ORDERED_WALKS:
            assert "TEMP B-TREE" not in plan, f"{name}: sorts its matches: {plan!r}"
    return plans


@pytest.mark.parametrize("table", ["triples", "kg_alt"])
def test_every_graph_read_is_an_index_search(tmp_path: Path, table: str) -> None:
    graph = MemoryGraph(SQLiteTripleStore(tmp_path / "home.sqlite3", table_name=table))
    # Some data, so the plans are those of a live home (SQLite plans the same at any size without ANALYZE).
    graph.apply_revision(rev("r-1", claim("a"), claim("b", o="ex:b"), provenance=prov(step("run-1", 1))))
    graph.apply_revision(rev("r-2", claim("c", o="ex:c", provenance=prov(derived=["a"])), close("a", "2026-05-01")))
    assert_index_plans(graph)
    graph.store.close()


def test_every_graph_read_has_a_plan_expectation(tmp_path: Path) -> None:
    graph = MemoryGraph(SQLiteTripleStore(tmp_path / "home.sqlite3"))
    assert set(graph._b.sql) == set(expected_plans(graph))
    graph.store.close()
