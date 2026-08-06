"""FTS5 keyword discovery (backlog 0019's open half).

Pinned:
- the SQLite store builds/maintains the FTS index append-only (edges and
  bookkeeping rows excluded — embedding parity) and backfills pre-FTS
  homes at open (in-place-upgrade precedent);
- query_keywords is a pure scoped read, best-match first;
- the keyword channel DISCOVERS beyond the gathered universe only when
  the host opts in (ReconstructConfig.keyword_discovery) on a capable
  store; default recall stays byte-identical (golden stability, the
  concept-expansion precedent);
- capability honesty: discovery requested on an incapable store degrades
  to the labeled v1 scan.
"""

from __future__ import annotations

import sqlite3
import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    MemoryRecordInput,
    MemorySystem,
    ReconstructConfig,
    SQLiteJournal,
    SQLiteTripleStore,
    Stimulus,
)
from abstractmemory.in_memory_store import InMemoryTripleStore
from abstractmemory.journal_memory import InMemoryJournal
from abstractmemory.seam import RecallBudget

OWNER = "entity:test"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]

_FTS_AVAILABLE = True
try:
    _c = sqlite3.connect(":memory:")
    _c.execute("CREATE VIRTUAL TABLE _probe USING fts5(x)")
    _c.close()
except sqlite3.OperationalError:  # pragma: no cover - build-dependent
    _FTS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _FTS_AVAILABLE, reason="sqlite build lacks FTS5 (capability-detected path)"
)


def _sqlite_system(tmp_path):
    db = str(tmp_path / "memory.sqlite3")
    return MemorySystem(store=SQLiteTripleStore(db), journal=SQLiteJournal(db)), db


def _seed_target_beyond_window(system) -> str:
    """One keyword-rich OLD record, then enough filler that the recency
    window (max_candidates) never reaches it."""
    [target] = system.remember_many([
        MemoryRecordInput(
            kind="episode", title="The lighthouse ledger",
            digest="I catalogued the lighthouse ledger with Ada near the breakwater.",
            keywords=("lighthouse", "ledger"), participants=("person:ada", OWNER)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="target")
    fillers = [
        MemoryRecordInput(
            kind="episode", title=f"routine tick {i}",
            digest=f"Routine maintenance tick number {i} passed without incident.",
        )
        for i in range(24)
    ]
    system.remember_many(fillers, scope=SCOPE, owner_id=OWNER, idempotency_key="fill")
    return target


def test_store_indexes_prose_and_skips_edges(tmp_path) -> None:
    system, db = _sqlite_system(tmp_path)
    [a] = system.remember_many([
        MemoryRecordInput(
            kind="episode", title="Harbor survey",
            digest="Ada walked me through the harbor wall survey.",
            edges=(("mentions", "ex:somewhere"),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="one")
    store = system.store
    assert store.supports_keyword_search
    hits = store.query_keywords(["harbor"], scope=SCOPE, owner_id=OWNER)
    assert hits and all(
        not (h.attributes or {}).get("record_edge") for h in hits
    ), "edge rows must never be keyword-indexed (embedding parity)"
    # Edge exclusion proven by MATCH semantics (a plain full scan of an
    # external-content FTS table enumerates the CONTENT table, so COUNT(*)
    # cannot distinguish indexed from unindexed rows — MATCH can): the edge
    # row's own tokens find nothing.
    con = sqlite3.connect(db)
    con.execute("PRAGMA query_only=ON")
    edge_hits = con.execute(
        "SELECT COUNT(*) FROM triples_fts WHERE triples_fts MATCH 'mentions'"
    ).fetchone()[0]
    prose_hits = con.execute(
        "SELECT COUNT(*) FROM triples_fts WHERE triples_fts MATCH 'harbor'"
    ).fetchone()[0]
    con.close()
    assert edge_hits == 0 and prose_hits >= 1
    system.close()
    assert a


def test_backfill_indexes_a_pre_fts_home(tmp_path) -> None:
    """A home written before the FTS index existed gains it at open —
    the in-place-upgrade precedent (embedding column)."""
    system, db = _sqlite_system(tmp_path)
    _seed_target_beyond_window(system)
    system.close()
    # Simulate the pre-FTS home: drop the index + its cursor.
    con = sqlite3.connect(db)
    con.execute("DROP TABLE IF EXISTS triples_fts")
    con.execute("DELETE FROM triples_meta WHERE key = 'fts_high_water'")
    con.commit()
    con.close()
    reopened = SQLiteTripleStore(db)
    assert reopened.supports_keyword_search
    hits = reopened.query_keywords(["lighthouse"], scope=SCOPE, owner_id=OWNER)
    assert any("lighthouse" in (h.object or "") for h in hits)
    reopened.close()


def test_discovery_finds_beyond_the_recency_window_when_opted_in(tmp_path) -> None:
    db = str(tmp_path / "memory.sqlite3")
    system = MemorySystem(
        store=SQLiteTripleStore(db), journal=SQLiteJournal(db),
        reconstruct_config=ReconstructConfig(keyword_discovery=True),
    )
    target = _seed_target_beyond_window(system)
    budget = RecallBudget(max_candidates=8, shelf_size=6)
    r = system.reconstruct(
        Stimulus(cue_text="lighthouse ledger"),
        scopes=SCOPES, budget=budget, journal=False)
    assert any(h.record_id == target or "lighthouse" in h.digest for h in r.handles), \
        "FTS discovery must surface the keyword match outside the recency window"
    # The fulfilled promise drops the v1 scan label on this path.
    assert not any("FTS5 lands with 0019" in w for w in r.warnings)
    system.close()


def test_default_recall_stays_scan_only_and_labeled(tmp_path) -> None:
    """Golden stability: without the opt-in, the same home misses the
    beyond-window match and carries the honest v1 label."""
    system, _db = _sqlite_system(tmp_path)
    target = _seed_target_beyond_window(system)
    budget = RecallBudget(max_candidates=8, shelf_size=6)
    r = system.reconstruct(
        Stimulus(cue_text="lighthouse ledger"),
        scopes=SCOPES, budget=budget, journal=False)
    assert not any(h.record_id == target for h in r.handles)
    assert any("FTS5 lands with 0019" in w for w in r.warnings)
    system.close()


def test_incapable_store_degrades_loudly_when_discovery_requested() -> None:
    system = MemorySystem(
        store=InMemoryTripleStore(), journal=InMemoryJournal(),
        reconstruct_config=ReconstructConfig(keyword_discovery=True),
    )
    system.remember_many([
        MemoryRecordInput(kind="episode", title="t", digest="the harbor wall"),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="x")
    r = system.reconstruct(
        Stimulus(cue_text="harbor"), scopes=SCOPES, journal=False)
    assert any("no FTS5 index" in w for w in r.warnings)
    system.close()


def test_probe_discovery_reaches_beyond_the_window_by_default(tmp_path) -> None:
    """probe() is the deliberate reach: ProbeBudget.keyword_discovery
    defaults ON, so an old keyword-only record beyond the recents window is
    found on an FTS5-capable store — and the F6 saturation label speaks the
    discovery-live variant (lexical reach is store-wide)."""
    from abstractmemory import probe

    system, _db = _sqlite_system(tmp_path)
    target = _seed_target_beyond_window(system)
    r = probe(
        system.store, system.journal,
        stimulus=Stimulus(cue_text="lighthouse ledger"),
        scopes=SCOPES, reason="test reach", effort="quick",
        write_journal=False)
    # Hits carry digest ROW ids, not graph ids (the two-namespace rule) —
    # match on the digest text like the recall pin does.
    assert any("lighthouse" in (h.digest or "") for h in r.hits), \
        [h.digest for h in r.hits]
    assert not any("FTS5/0019 lifts it" in w for w in r.warnings)
    system.close()
    assert target  # graph id exists; namespace note above


def test_probe_discovery_off_keeps_the_original_labels(tmp_path) -> None:
    from abstractmemory import probe
    from abstractmemory.probe import ProbeBudget

    system, _db = _sqlite_system(tmp_path)
    target = _seed_target_beyond_window(system)
    r = probe(
        system.store, system.journal,
        stimulus=Stimulus(cue_text="lighthouse ledger"),
        scopes=SCOPES, reason="test reach",
        effort=ProbeBudget(max_candidates=8, max_hits=6,
                           keyword_discovery=False, concept_expansion=False),
        write_journal=False)
    assert not any("lighthouse" in (h.digest or "") for h in r.hits)
    assert any("FTS5/0019 lifts it" in w for w in r.warnings)
    system.close()
    assert target


def test_duplicate_adds_never_double_index(tmp_path) -> None:
    system, db = _sqlite_system(tmp_path)
    record = MemoryRecordInput(
        kind="episode", title="once", digest="a singular moment by the sea")
    system.remember_many([record], scope=SCOPE, owner_id=OWNER, idempotency_key="dup")
    system.remember_many([record], scope=SCOPE, owner_id=OWNER, idempotency_key="dup")
    # A MATCH returns the record once: OR IGNORE duplicates sit below the
    # high-water cursor and are never re-indexed.
    con = sqlite3.connect(db)
    con.execute("PRAGMA query_only=ON")
    match_hits = con.execute(
        "SELECT COUNT(*) FROM triples_fts WHERE triples_fts MATCH 'singular'"
    ).fetchone()[0]
    con.close()
    assert match_hits == 1
    hits = system.store.query_keywords(["singular"], scope=SCOPE, owner_id=OWNER)
    assert len(hits) == 1
    system.close()
