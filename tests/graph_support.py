"""Shared builders for the graph suites (tests/test_graph_*.py). Real stores on tmp_path, real journals, no mocks.

`open_home(tmp_path, kind)` opens one mind in one of three deployments:
- "sqlite":         SQLiteTripleStore + SQLiteJournal in the SAME file (the entity/plane home: one transaction),
- "sqlite-offfile": SQLiteTripleStore + SQLiteJournal in another file (closures appended after commit, repairable),
- "memory":         InMemoryTripleStore + InMemoryJournal (undo-log atomicity).
`home_state(home)` is everything the home holds (every SQLite table's rows, or the in-memory store, graph state and
journal), so "nothing behind" and "replay equals the original" are exact comparisons, not counts of one table.
"""
from __future__ import annotations

import hashlib
import sqlite3
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    SQLiteJournal,
    SQLiteTripleStore,
    TripleQuery,
)
from abstractmemory.graph import MemoryGraph, Revision, RevisionOp

KINDS = ("sqlite", "sqlite-offfile", "memory")
#: Every connector of abstractmemory.graph.backend (the conformance suite runs on each).
BACKENDS = ("sqlite", "memory", "lancedb")


def T(month: int, day: int = 1) -> str:
    """A day of 2026 in the graph's canonical timestamp form (UTC, microseconds, '+00:00'): what a revision stores
    after normalizing whatever ISO-8601 form it was given."""
    return f"2026-{month:02d}-{day:02d}T00:00:00.000000+00:00"


def step(run_id: str, seq: int, step_id: Optional[str] = None) -> Dict[str, Any]:
    ref: Dict[str, Any] = {"kind": "step", "run_id": run_id, "seq": seq}
    if step_id:
        ref["step_id"] = step_id
    return ref


def art(artifact_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    ref: Dict[str, Any] = {"kind": "artifact", "artifact_id": artifact_id}
    if run_id:
        ref["run_id"] = run_id
    return ref


def prov(*sources: Dict[str, Any], derived=(), actor: str = "abstractnote", **extra: Any) -> Dict[str, Any]:
    return {"sources": list(sources), "derived_from": list(derived), "actor": actor, "extra": dict(extra)}


def claim(aid: str, s: str = "ex:dana", p: str = "schema:worksFor", o: str = "ex:acme", **kw: Any) -> RevisionOp:
    return RevisionOp("assert", {"assertion_id": aid, "subject": s, "predicate": p, "object": o, **kw})


def close(aid: str, until: str, kind: str = "retract", replacement_ids=(), reason: str = "no longer held",
          **kw: Any) -> RevisionOp:
    return RevisionOp("close", {"assertion_id": aid, "valid_until": until, "kind": kind,
                                "replacement_ids": list(replacement_ids), "reason": reason, **kw})


def narrow(aid: str, until: str, reason: str = "an earlier note dates it") -> RevisionOp:
    return RevisionOp("narrow", {"assertion_id": aid, "valid_until": until, "reason": reason})


DEFAULT_PROV = prov(step("run-1", 1))


def rev(rid: str, *ops: RevisionOp, cause: str = "ingest", provenance: Optional[Dict[str, Any]] = None,
        occurred_at: str = T(1), recorded_at: Optional[str] = None, scope: str = "global",
        owner_id: str = "abstractnote", summary: Optional[str] = None) -> Revision:
    kw: Dict[str, Any] = {}
    if recorded_at:
        kw["recorded_at"] = recorded_at
    return Revision(revision_id=rid, scope=scope, owner_id=owner_id, cause=cause, occurred_at=occurred_at,
                    ops=tuple(ops), provenance=provenance or DEFAULT_PROV, summary=summary, **kw)


class FakeEmbedder:
    """Deterministic unit vectors seeded by the text hash (the audit bench's pattern); no model, no network."""

    model = "fake-random-64"

    def __init__(self, dim: int = 64) -> None:
        self.dim, self.calls = dim, 0

    def embed_texts(self, texts):
        self.calls += 1
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(self.dim).astype(np.float32)
            out.append((v / np.linalg.norm(v)).tolist())
        return out


@dataclass
class Home:
    kind: str
    store: Any
    journal: Any
    graph: MemoryGraph
    path: Optional[Path] = None
    journal_path: Optional[Path] = None

    def close(self) -> None:
        self.journal.close() if hasattr(self.journal, "close") else None
        self.store.close()


def open_home(tmp_path: Path, kind: str, name: str = "home", embedder: Any = None) -> Home:
    if kind == "lancedb":
        from abstractmemory import LanceDBTripleStore

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # no embedding pin on LanceDB (its #FALLBACK)
            store = LanceDBTripleStore(tmp_path / f"{name}-lance", embedder=embedder)
        journal_path = tmp_path / f"{name}-journal.sqlite3"  # a LanceDB mind keeps its journal elsewhere
        journal = SQLiteJournal(journal_path)
        return Home(kind, store, journal, MemoryGraph(store, journal), tmp_path / f"{name}-lance", journal_path)
    if kind == "memory":
        store = InMemoryTripleStore(embedder=embedder)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # the in-memory journal's volatility #FALLBACK
            journal = InMemoryJournal()
        return Home(kind, store, journal, MemoryGraph(store, journal))
    path = tmp_path / f"{name}.sqlite3"
    journal_path = path if kind == "sqlite" else tmp_path / f"{name}-journal.sqlite3"
    store = SQLiteTripleStore(path, embedder=embedder)
    journal = SQLiteJournal(journal_path)
    return Home(kind, store, journal, MemoryGraph(store, journal), path, journal_path)


def file_state(path: Path) -> Dict[str, List[tuple]]:
    """Every row of every real table of a SQLite file (FTS shadow tables included), sorted: an exact snapshot."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND sql NOT LIKE 'CREATE VIRTUAL%' "
            "ORDER BY name")]
        return {t: sorted(conn.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr) for t in tables}
    finally:
        conn.close()


def store_dump(store: Any) -> List[Dict[str, Any]]:
    """The full TripleQuery dump (every row, every field), sorted by id."""
    rows = store.query(TripleQuery(limit=0, order="asc"))
    return sorted((a.to_dict() for a in rows), key=lambda d: str(d.get("assertion_id")))


def home_state(home: Home) -> Any:
    if home.kind == "memory":
        from abstractmemory.graph.graph import _memory_backend

        b = _memory_backend(home.store)
        return {
            "rows": [(r["assertion_id"], r["assertion"].to_dict(), r.get("vector")) for r in home.store._rows],
            "pin": home.store.embedding_pin(),
            "revisions": [(e["seq"], e["revision"].to_dict(), e["journal_applied"]) for e in b.revisions],
            "hist": [dict(h) for h in b.hist],
            "provenance": [(m, k, r.to_dict(), rid, via, o) for m, k, r, rid, via, o in b.provenance],
            "derivations": list(b.derivations),
            "known": sorted(b.known),
            "closures": [c.to_dict() for c in home.journal.closures(limit=0)],
        }
    state = {"file": file_state(home.path)}
    if home.journal_path != home.path:
        state["journal"] = file_state(home.journal_path)
    return state


def graph_tables(path: Path) -> Dict[str, List[tuple]]:
    """The four memg_* tables and the triple table of a home file."""
    return {t: rows for t, rows in file_state(path).items() if t.startswith("memg_") or t == "triples"}


def mind_dump(home: Home) -> Dict[str, Any]:
    """Everything a mind holds, read through the PUBLIC surface only (works on every connector): every triple, the
    whole revision log, each memory's history and labelled sources, and the journal's closures."""
    rows = store_dump(home.store)
    revisions, cursor = [], None
    while True:
        page, cursor = home.graph.revisions(after=cursor, limit=1000)
        if not page:
            break
        revisions.extend(r.to_dict() for r in page)
    ids = [r["assertion_id"] for r in rows]
    return {
        "rows": rows,
        "revisions": revisions,
        "history": {i: home.graph.history(i) for i in ids},
        "sources": {i: [{**d, "ref": d["ref"].to_dict()} for d in home.graph.sources_of(i, labelled=True)]
                    for i in ids},
        "closures": sorted((c.closure_id, c.assertion_id, c.kind) for c in home.journal.closures(limit=0)),
    }
