"""mind_mass_report() — the mind-health card's engine half (backlog 0043).

Pins: window-bounded curves (journal walk O(window), never O(life));
unit-labeled counts and {word, detail} warnings (the observer's two
consumer asks, adopted at commons c4132); duplicate counts UNBOUNDED
(maintenance_report's list_bound bounds its proposal list, a health
count must be exact); embedding integrity as claimed-vs-wired with the
vectorless sub-scan (the rogue-embedder signature); review depth lifted
from cognition_health's OWN fold (one truth, no cross-door drift);
loud validation; pure read.
"""

from __future__ import annotations

import json
import sqlite3
import warnings as _warnings
from types import SimpleNamespace

import pytest

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemorySystem,
    WARNING_WORDS,
    cognition_health,
    mind_mass_report,
)
from abstractmemory.records import MemoryRecordInput

OWNER = "entity:hygieia"
SCOPES = [("self", OWNER), ("diary", OWNER), ("life", OWNER)]


def _episode(system: MemorySystem, key: str, title: str, digest: str, **attrs) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title=title, digest=digest,
                           attributes=dict(attrs) if attrs else {})],
        scope="life", owner_id=OWNER, idempotency_key=key)
    return gid


def _words(report: dict) -> set:
    return {w["word"] for w in report["warnings"]}


def test_report_shape_units_and_sources(system) -> None:
    _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")
    _episode(system, "e2", "archive dig", "Read the old harbor ledgers.")
    [dream] = system.remember_many(
        [MemoryRecordInput(kind="dream", title="dream: bridges",
                           digest="Bridges between tide and ledger.")],
        scope="life", owner_id=OWNER, idempotency_key="d1")

    report = mind_mass_report(system.store, system.journal, scopes=SCOPES)

    assert report["report"] == "mind_mass_report"
    assert isinstance(report["as_of_seq"], int) and report["as_of_seq"] > 0
    assert report["window"]["days"] == 30 and report["window"]["bucket"] == "day"

    formation = report["formation"]
    assert formation["unit"] == "records"
    assert formation["total_by_kind"]["episode"] == 2
    assert formation["total_by_kind"]["dream"] == 1
    assert formation["records_total"] == 3
    today = formation["by_day"][-1]
    assert today["total"] == 3 and today["kinds"]["episode"] == 2

    by_pair = {(p["scope"], p["owner_id"]): p for p in report["pairs"]["by_pair"]}
    assert by_pair[("life", OWNER)]["records"] == 3
    assert by_pair[("life", OWNER)]["formed_in_window"] == 3
    assert by_pair[("self", OWNER)]["records"] == 0

    journal_section = report["journal"]
    assert journal_section["unit"] == "journal records"
    assert journal_section["walked"] >= 1  # formation bindings are journal mass
    assert journal_section["current_seq"] == report["as_of_seq"]
    assert isinstance(journal_section["compaction"]["available"], bool)

    dup = report["duplicates"]
    assert dup["units"]["title_clusters"] == "clusters"
    assert dup["units"]["wake_cue_members"] == "records"
    assert "title_clusters" in dup["sources"] and "wake_cue_clusters" in dup["sources"]

    review = report["review"]
    assert review["unit"] == "records"
    assert review["candidates"] == cognition_health(
        system.store, system.journal, scopes=SCOPES)["candidates"]

    # A dream row IS a sleep artifact: recency reads > 0, no never_slept.
    assert report["sleep"]["last_artifact_seq"] > 0
    assert report["sleep"]["dreams"] == {"unit": "records", "total": 1}
    assert dream  # formed above

    for warning in report["warnings"]:
        assert set(warning) == {"word", "detail"}
        assert warning["word"] in WARNING_WORDS
        assert warning["detail"].strip()
    # Fixture stacks carry no embedding pin: the unpinned FACT is stated.
    assert "unpinned" in _words(report)
    assert "never_slept" not in _words(report)


def test_window_bounds_both_curves(system) -> None:
    """Records formed today, report anchored 40 days later with a 30-day
    window: totals keep the mass, curves and window counts go empty, and
    the journal walk starts past everything (O(window), never O(life))."""
    _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")
    _episode(system, "e2", "archive dig", "Read the old harbor ledgers.")

    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(days=40)).isoformat()
    report = mind_mass_report(system.store, system.journal, scopes=SCOPES,
                              days=30, now=future)

    assert report["formation"]["records_total"] == 2      # totals are all-time
    assert report["formation"]["by_day"] == []            # curve is window-only
    by_pair = {(p["scope"], p["owner_id"]): p for p in report["pairs"]["by_pair"]}
    assert by_pair[("life", OWNER)] == {"scope": "life", "owner_id": OWNER,
                                        "records": 2, "formed_in_window": 0}
    assert report["journal"]["walked"] == 0
    assert report["journal"]["by_day"] == []


def test_embedding_claimed_vs_wired_and_vectorless(tmp_path) -> None:
    store = InMemoryTripleStore(embedding_pin={"model_id": "modelA", "dimension": 4})
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", RuntimeWarning)
        journal = InMemoryJournal()
    system = MemorySystem(store=store, journal=journal)
    for i in range(3):  # no embedder wired: rows land vectorless under a pin
        _episode(system, f"e{i}", f"walk {i}", f"Walked line {i} of the harbor.")

    mismatch = mind_mass_report(store, journal, scopes=SCOPES,
                                embedder=SimpleNamespace(model="modelB"))
    assert mismatch["embedding"]["match"] is False
    assert mismatch["embedding"]["wired_model"] == "modelB"
    assert {"embedder_mismatch", "vectorless_records"} <= _words(mismatch)
    assert "unpinned" not in _words(mismatch)
    scan = mismatch["embedding"]["vector_scan"]
    assert scan == {"unit": "records", "scanned": 3, "of": 3,
                    "vectorless": 3, "off_dimension": 0, "partial": False}

    match = mind_mass_report(store, journal, scopes=SCOPES,
                             embedder=SimpleNamespace(model="modelA"))
    assert match["embedding"]["match"] is True
    assert "embedder_mismatch" not in _words(match)

    unknown = mind_mass_report(store, journal, scopes=SCOPES)  # no embedder passed
    assert unknown["embedding"]["match"] is None


def test_dimension_is_the_fallback_identity_axis() -> None:
    """Adversary P1-1: identity-less embedders are enforced BY DIMENSION
    (embedding_pin contract) — a dimension-only pin must still surface a
    wired-dimension contradiction, and off-dimension vectors AT REST are
    the rogue-embedder signature itself."""
    store = InMemoryTripleStore(embedding_pin={"model_id": None, "dimension": 4})
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", RuntimeWarning)
        journal = InMemoryJournal()
    system = MemorySystem(store=store, journal=journal)
    _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")

    report = mind_mass_report(store, journal, scopes=SCOPES,
                              embedder=SimpleNamespace(dimension=8))
    assert "dimension_mismatch" in _words(report)
    assert report["embedding"]["match"] is False  # dimension contradiction decides

    # Off-dimension vectors AT REST (historical corruption, simulated by a
    # direct row poke — no write path can produce this state today).
    for row in store._rows:
        if not (row.get("attributes") or {}).get("record_edge"):
            row["vector"] = [0.1, 0.2]
    at_rest = mind_mass_report(store, journal, scopes=SCOPES)
    assert at_rest["embedding"]["vector_scan"]["off_dimension"] == 1
    assert "dimension_mismatch" in _words(at_rest)


def test_missing_stored_vector_capability_reaches_the_badge_path() -> None:
    """Adversary P1-2: a backend without stored_vector must say so in
    warnings (the badge path), not only in a field a tile never reads."""
    class NoVectorStore(InMemoryTripleStore):
        stored_vector = None  # capability absent

    store = NoVectorStore()
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", RuntimeWarning)
        journal = InMemoryJournal()
    system = MemorySystem(store=store, journal=journal)
    _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")

    report = mind_mass_report(store, journal, scopes=SCOPES)
    scan = report["embedding"]["vector_scan"]
    assert scan["scanned"] == 0 and scan["vectorless"] is None and scan["partial"]
    partials = [w for w in report["warnings"] if w["word"] == "vector_scan_partial"]
    assert partials and "no stored_vector" in partials[0]["detail"]


def test_non_utc_now_normalizes_the_window() -> None:
    store = InMemoryTripleStore()
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", RuntimeWarning)
        journal = InMemoryJournal()
    system = MemorySystem(store=store, journal=journal)
    _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")

    report = mind_mass_report(store, journal, scopes=SCOPES,
                              now="2030-01-01T05:00:00+05:00")
    assert report["window"]["until"].endswith("+00:00")
    assert report["window"]["until"].startswith("2030-01-01T00:00:00")
    assert report["window"]["since"].startswith("2029-12-02T00:00:00")


def test_vector_scan_bound_says_partial(system) -> None:
    for i in range(5):
        _episode(system, f"e{i}", f"walk {i}", f"Walked line {i} of the harbor.")
    report = mind_mass_report(system.store, system.journal, scopes=SCOPES,
                              vector_scan_limit=2)
    scan = report["embedding"]["vector_scan"]
    assert scan["scanned"] == 2 and scan["of"] == 5 and scan["partial"] is True
    assert "vector_scan_partial" in _words(report)


def test_duplicate_counts_are_unbounded_and_wake_cue_is_the_dry_run(system) -> None:
    # 14 distinct 2-member title clusters — beyond maintenance_report's
    # list_bound (12): the health COUNT must stay exact. Distinct content
    # words per pair (token folding drops digits, so numbered variants
    # would read near-identical to the wake-cue dry-run).
    nouns = ["anchor", "beacon", "compass", "davit", "ensign", "fathom",
             "galley", "hawser", "jetty", "keel", "lantern", "mooring",
             "porthole", "rudder"]
    for noun in nouns:
        _episode(system, f"a-{noun}", f"repeated {noun}",
                 f"First telling about the {noun}, seen from the quay.")
        _episode(system, f"b-{noun}", f"repeated {noun}",
                 f"Second telling about the {noun}, noted by the mast.")
    # One same-day near-identical 4-member group: the wake-cue signature
    # (dedup dry-run needs >= 3 members at jaccard >= 0.82).
    for i in range(4):
        _episode(system, f"w{i}", "wake cue",
                 "Woke at the same bell, checked the same empty inbox at dawn.")

    report = mind_mass_report(system.store, system.journal, scopes=SCOPES)
    dup = report["duplicates"]
    assert dup["title_clusters"] == 15            # 14 pairs + the wake-cue group
    assert dup["title_cluster_records"] == 32     # 28 + 4
    assert dup["wake_cue_clusters"] == 1          # only the 4-member group acts
    assert dup["wake_cue_members"] == 4

    skipped = mind_mass_report(system.store, system.journal, scopes=SCOPES,
                               wake_cue_kind=None)
    assert "wake_cue_clusters" not in skipped["duplicates"]


def test_duplicate_count_drops_after_repair(system) -> None:
    """Adversary P1-4: the store is append-only, so a closure-blind title
    fold could never decrease after the very repair this report motivates.
    Closing a duplicate member must drop the cluster from the count."""
    first = _episode(system, "a1", "repeated mooring",
                     "First telling about the mooring, seen from the quay.")
    _episode(system, "a2", "repeated mooring",
             "Second telling about the mooring, noted by the mast.")
    before = mind_mass_report(system.store, system.journal, scopes=SCOPES)
    assert before["duplicates"]["title_clusters"] == 1

    system.close_record(first, kind="retract",
                        reason="dedup repair: first telling superseded by hand")
    after = mind_mass_report(system.store, system.journal, scopes=SCOPES)
    assert after["duplicates"]["title_clusters"] == 0
    assert after["duplicates"]["title_cluster_records"] == 0


def test_overlapping_pairs_never_double_count_global_mass(system) -> None:
    """Adversary P1-3: ("Life", owner) vs ("life", owner) query identical
    rows (store grammar strips+lowers scope), and a wildcard-owner pair
    overlaps every named-owner pair — global counts fold DISTINCT
    assertions while the per-pair block keeps its per-pair views."""
    _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")
    _episode(system, "e2", "archive dig", "Read the old harbor ledgers.")

    shadowed = mind_mass_report(
        system.store, system.journal,
        scopes=[("life", OWNER), ("Life", OWNER), ("life", "")])
    assert shadowed["formation"]["records_total"] == 2
    assert shadowed["formation"]["total_by_kind"] == {"episode": 2}
    assert shadowed["formation"]["by_day"][-1]["total"] == 2
    scan = shadowed["embedding"]["vector_scan"]
    assert scan["of"] == 2  # the vector budget is never burned on copies
    # The per-pair block keeps overlapping views, case-folded and deduped.
    by_pair = {(p["scope"], p["owner_id"]): p for p in shadowed["pairs"]["by_pair"]}
    assert set(by_pair) == {("life", OWNER), ("life", "")}
    assert by_pair[("life", OWNER)]["records"] == 2
    assert by_pair[("life", "")]["records"] == 2


def test_review_composes_dreams_and_candidates(system) -> None:
    episode = _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")
    system.remember_many(
        [MemoryRecordInput(kind="dream", title="dream: tension",
                           digest="The same door, still closed.",
                           attributes={"continuation_state": "unresolved"})],
        scope="life", owner_id=OWNER, idempotency_key="d1")
    system.remember_many(
        [MemoryRecordInput(kind="summary", title="candidate: harbor lesson",
                           digest="Quays flood at spring tide.",
                           edges=(("summarizes", episode),),
                           attributes={"maintenance_candidate": True,
                                       "review_required": True,
                                       "proposed_kind": "lesson"})],
        scope="life", owner_id=OWNER, idempotency_key="c1")

    report = mind_mass_report(system.store, system.journal, scopes=SCOPES)
    assert report["review"]["unresolved_dreams"] == 1
    assert report["review"]["candidates"]["pending"] == 1
    assert report["review"]["candidates"]["by_proposed_kind"] == {"lesson": 1}


def test_never_slept_is_a_fact_not_a_threshold(system) -> None:
    _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")
    before = mind_mass_report(system.store, system.journal, scopes=SCOPES)
    assert "never_slept" in _words(before)
    assert before["sleep"]["last_artifact_seq"] == 0

    system.remember_many(
        [MemoryRecordInput(kind="dream", title="dream: first",
                           digest="A first quiet composition.")],
        scope="life", owner_id=OWNER, idempotency_key="d1")
    after = mind_mass_report(system.store, system.journal, scopes=SCOPES)
    assert "never_slept" not in _words(after)
    assert after["sleep"]["last_artifact_seq"] > 0


def test_compaction_meta_reads_the_doctoring_key(tmp_path) -> None:
    from abstractmemory import SQLiteJournal, SQLiteTripleStore

    path = tmp_path / "memory.sqlite3"
    store = SQLiteTripleStore(path)
    journal = SQLiteJournal(path)
    try:
        system = MemorySystem(store=store, journal=journal)
        _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")

        empty = mind_mass_report(store, journal, scopes=SCOPES)
        assert empty["journal"]["compaction"] == {
            "available": False,
            "detail": "no compaction recorded (absent or unreadable meta)"}

        # Simulate the doctoring wave's write: append-only history list
        # under the 'compaction' key (same file, store meta table).
        con = sqlite3.connect(str(path))
        try:
            con.execute(
                "INSERT OR REPLACE INTO triples_meta (key, value) VALUES (?, ?)",
                ("compaction", json.dumps([
                    {"at": "2026-07-01T00:00:00+00:00", "cut_seq": 3,
                     "archive_ref": "artifact:cut-1"},
                ])))
            con.commit()
        finally:
            con.close()

        report = mind_mass_report(store, journal, scopes=SCOPES)
        compaction = report["journal"]["compaction"]
        assert compaction["available"] is True
        assert compaction["archive_ref"] == "artifact:cut-1"
        assert compaction["cuts_total"] == 1
        assert compaction["seq_since_cut"] == report["as_of_seq"] - 3
    finally:
        journal.close()
        store.close()


def test_in_memory_backend_says_compaction_unavailable() -> None:
    store = InMemoryTripleStore()
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", RuntimeWarning)
        journal = InMemoryJournal()
    system = MemorySystem(store=store, journal=journal)
    _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")
    report = mind_mass_report(store, journal, scopes=SCOPES)
    assert report["journal"]["compaction"]["available"] is False
    assert "compaction meta" in report["journal"]["compaction"]["detail"]


def test_pure_read_deposits_and_writes_nothing(system) -> None:
    from abstractmemory import TripleQuery

    _episode(system, "e1", "harbor walk", "Walked the tide line at dawn.")
    seq_before = system.journal.current_seq()
    rows_before = len(system.store.query(TripleQuery(scope="life", owner_id=OWNER, limit=0)))

    mind_mass_report(system.store, system.journal, scopes=SCOPES)

    assert system.journal.current_seq() == seq_before
    assert len(system.store.query(TripleQuery(scope="life", owner_id=OWNER, limit=0))) == rows_before


def test_loud_validation(system) -> None:
    with pytest.raises(ValueError, match="bucket='day'"):
        mind_mass_report(system.store, system.journal, scopes=SCOPES, bucket="week")
    with pytest.raises(ValueError, match="days >= 1"):
        mind_mass_report(system.store, system.journal, scopes=SCOPES, days=0)
    with pytest.raises(ValueError, match="at least one"):
        mind_mass_report(system.store, system.journal, scopes=[])
