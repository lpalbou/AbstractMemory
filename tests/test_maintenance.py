"""Sleep phase-1 guards (data-quality tending — the fork's missing half of 0023).

THESE TESTS ARE THE DELIVERABLE, same discipline as test_consolidation.py:
each pins a fork guard or a named divergence. Tending is deterministic and
report-first; the ONLY write is the inactive review-gated consolidation
candidate; sleep proposes, waking evidence disposes; maintenance deposits
NOTHING; tending never re-tends its own output.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import pytest

from abstractmemory import (
    consolidation_pass,
    last_maintenance_seq,
    maintenance_due,
    maintenance_report,
    sleep_pass,
)
from abstractmemory.records import MemoryRecordInput
from abstractmemory.store import TripleQuery

SCOPE = "life"
OWNER = "entity:test"
SCOPES = [(SCOPE, OWNER)]


def _remember(system, key: str, kind: str, title: str, digest: str, **kw: Any) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _duplicate_pile(system) -> Dict[str, str]:
    """Castor-shaped fixture: the same interest retold three times (identical
    title, near-identical digests), one distinct episode, one isolated note
    sharing facets with the episode, one metadata-complete lesson."""
    ids = {}
    ids["bridge-1"] = _remember(system, "m-1", "interest", "The twelve bridges",
                                "The twelve bridges keep returning to me tonight.")
    ids["bridge-2"] = _remember(system, "m-2", "interest", "The twelve bridges",
                                "The twelve bridges keep returning to me again tonight.")
    ids["bridge-3"] = _remember(system, "m-3", "interest", "The twelve bridges",
                                "The twelve bridges keep returning to me once more.")
    ids["walk"] = _remember(system, "m-4", "episode", "Harbor walk",
                            "Walked the harbor and watched the cranes unload.",
                            keywords=("harbor", "cranes", "walk"),
                            intents=("observe",), outcomes=("calm",))
    ids["note"] = _remember(system, "m-5", "memory", "Crane note",
                            "A stray note about harbor cranes.",
                            keywords=("harbor", "cranes"))
    ids["lesson"] = _remember(system, "m-6", "lesson", "Ask before assuming",
                              "Asking before assuming saved the evening.",
                              keywords=("asking",), intents=("repair",), outcomes=("trust",))
    return ids


def _access_state(system, journal, ids: Dict[str, str]) -> Tuple[Dict, int]:
    counts = system.access_counts(record_ids=list(ids.values()))
    events = len(journal.events(scope=SCOPE, owner_id=OWNER,
                                kinds=["selected", "co_selected", "pinned", "silenced"],
                                limit=0))
    return counts, events


# ---------------------------------------------------------------------------
# REPORT: metadata gaps, duplicate titles (same-kind), near-duplicates
# ---------------------------------------------------------------------------


def test_report_names_metadata_gaps_report_only(system, stack) -> None:
    store, journal = stack
    ids = _duplicate_pile(system)
    report = maintenance_report(store, journal, scopes=SCOPES)

    gapped = {g["record_id"]: g for g in report["metadata_gaps"]}
    assert ids["bridge-1"] in gapped          # no keywords/intents/outcomes
    assert gapped[ids["bridge-1"]]["missing_fields"] == ["keywords", "intents", "outcomes"]
    assert ids["walk"] not in gapped          # fully described
    assert ids["lesson"] not in gapped
    assert "report-only" in gapped[ids["bridge-1"]]["action"]  # the boundary, stated
    # The note has keywords but no intents/outcomes: named precisely.
    assert gapped[ids["note"]]["missing_fields"] == ["intents", "outcomes"]


def test_report_duplicate_titles_are_same_kind_only(system, stack) -> None:
    store, journal = stack
    ids = _duplicate_pile(system)
    # Same title as the interests but a DIFFERENT KIND: derivation, not dup.
    other_kind = _remember(system, "m-7", "episode", "The twelve bridges",
                           "An evening spent actually reading about bridges.")
    report = maintenance_report(store, journal, scopes=SCOPES)

    [group] = report["duplicate_title_groups"]
    assert group["kind"] == "interest"
    assert sorted(group["record_ids"]) == sorted(
        [ids["bridge-1"], ids["bridge-2"], ids["bridge-3"]])
    assert other_kind not in group["record_ids"]


def test_report_near_duplicates_jaccard_same_kind(system, stack) -> None:
    store, journal = stack
    ids = _duplicate_pile(system)
    report = maintenance_report(store, journal, scopes=SCOPES)

    pairs = {tuple(p["pair"]) for p in report["near_duplicate_pairs"]}
    assert tuple(sorted((ids["bridge-1"], ids["bridge-2"]))) in pairs
    # Distinct texts never pair; cross-kind never pairs.
    assert tuple(sorted((ids["walk"], ids["note"]))) not in pairs
    for p in report["near_duplicate_pairs"]:
        assert p.get("jaccard", 1.0) >= 0.65


def test_report_near_duplicate_vector_upgrade(stack) -> None:
    """Named upgrade: paraphrase duplicates below the Jaccard floor still
    flag when stored embeddings nearly coincide (>= 0.90)."""
    import warnings as warnings_module
    from abstractmemory import MemorySystem

    class TwinEmbedder:
        def embed_texts(self, texts):
            return [[1.0, 0.0] for _ in texts]

    store, journal = stack
    if not hasattr(store, "stored_vector"):
        pytest.skip("store lacks stored_vector")
    store._embedder = TwinEmbedder()
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore", RuntimeWarning)
        system = MemorySystem(store=store, journal=journal, embedder=TwinEmbedder())

    a = MemoryRecordInput(kind="episode", title="Ship day", digest="The freighter left port.")
    b = MemoryRecordInput(kind="episode", title="Kiln firing", digest="Ceramics glazed overnight.")
    [gid_a] = system.remember_many([a], scope=SCOPE, owner_id=OWNER, idempotency_key="mv-1")
    [gid_b] = system.remember_many([b], scope=SCOPE, owner_id=OWNER, idempotency_key="mv-2")

    report = maintenance_report(store, journal, scopes=SCOPES)
    [pair] = [p for p in report["near_duplicate_pairs"]
              if tuple(p["pair"]) == tuple(sorted((gid_a, gid_b)))]
    assert pair["vector_score"] == pytest.approx(1.0)
    assert "jaccard" not in pair  # it fired on the vector channel


# ---------------------------------------------------------------------------
# REPORT: link candidates + edge suppressions are PROPOSALS, never writes
# ---------------------------------------------------------------------------


def test_report_isolated_link_candidates_propose_only(system, stack) -> None:
    store, journal = stack
    ids = _duplicate_pile(system)
    report = maintenance_report(store, journal, scopes=SCOPES)

    pairs = {tuple(c["pair"]) for c in report["isolated_link_candidates"]}
    # note (isolated) shares {harbor, cranes} with walk -> proposed.
    assert tuple(sorted((ids["note"], ids["walk"]))) in pairs
    # No record_edge rows were written by the report.
    edges = [a for a in store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))
             if isinstance(a.attributes, dict) and a.attributes.get("record_edge")]
    assert edges == []


def test_report_edge_suppression_candidates(system, stack) -> None:
    store, journal = stack
    ids = _duplicate_pile(system)
    # Duplicate logical edge across two formation batches (distinct keys ->
    # distinct assertion ids), plus a mentions edge shadowed by supports.
    _remember(system, "m-8", "summary", "Bridge summary",
              "One summary standing over the retellings.",
              edges=(("summarizes", ids["bridge-1"]), ("summarizes", ids["bridge-1"])))
    left = _remember(system, "m-9", "episode", "Pair left",
                     "Left side of the shadowed pair.",
                     edges=(("mentions", ids["walk"]), ("supports", ids["walk"])))
    report = maintenance_report(store, journal, scopes=SCOPES)

    kinds = {c["kind"] for c in report["edge_suppression_candidates"]}
    assert "low_information_edge" in kinds
    [shadowed] = [c for c in report["edge_suppression_candidates"]
                  if c["kind"] == "low_information_edge"]
    assert shadowed["pair"] == [left, ids["walk"]]
    assert "closure" in shadowed["action"]  # the waking act, named


# ---------------------------------------------------------------------------
# GUARD: tending deposits NOTHING (the D2 of sleep, phase-1 half)
# ---------------------------------------------------------------------------


def test_guard_tending_deposits_nothing(system, stack) -> None:
    store, journal = stack
    ids = _duplicate_pile(system)
    before_counts, before_events = _access_state(system, journal, ids)

    maintenance_report(store, journal, scopes=SCOPES)
    result = consolidation_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert result["created_count"] == 1       # a candidate DID form...

    after_counts, after_events = _access_state(system, journal, ids)
    assert after_counts == before_counts      # ...but no access count moved
    assert after_events == before_events      # and no attention event landed


# ---------------------------------------------------------------------------
# WRITE: the inactive candidate (shape, idempotency, source immutability)
# ---------------------------------------------------------------------------


def test_candidate_shape_inactive_and_sources_untouched(system, stack) -> None:
    store, journal = stack
    ids = _duplicate_pile(system)
    sources_before = {
        a.assertion_id: (a.subject, a.predicate, a.object, dict(a.attributes))
        for a in store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))
    }
    result = consolidation_pass(system, scopes=SCOPES, owner_id=OWNER)

    [created] = result["created"]
    assert created["created"] is True
    assert sorted(created["source_ids"]) == sorted(
        [ids["bridge-1"], ids["bridge-2"], ids["bridge-3"]])

    rows = store.query(TripleQuery(subject=created["candidate_id"], limit=0))
    digest = next(a for a in rows if not a.attributes.get("record_edge"))
    edges = [a for a in rows if a.attributes.get("record_edge")]
    assert digest.attributes["record_kind"] == "summary"
    assert digest.attributes["maintenance_candidate"] is True
    assert digest.attributes["review_required"] is True
    assert digest.attributes["no_source_mutation"] is True
    assert {e.object for e in edges} == set(created["source_ids"])
    assert all(e.predicate == "summarizes" for e in edges)

    # Born inactive (indexed+inactive binding), like every formed record.
    [binding] = journal.bindings(record_id=created["candidate_id"], fold=True)
    assert binding.prompt_state == "inactive"
    assert binding.search_state == "indexed"

    # Sources byte-untouched: every pre-existing assertion identical.
    for a in store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0)):
        if a.assertion_id in sources_before:
            assert sources_before[a.assertion_id] == (
                a.subject, a.predicate, a.object, dict(a.attributes))


def test_candidate_idempotent_and_report_only_writes_nothing(system, stack) -> None:
    store, journal = stack
    _duplicate_pile(system)
    dry = consolidation_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    assert dry["created"] == [] and dry["created_count"] == 0

    first = consolidation_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert first["created_count"] == 1
    replay = consolidation_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert replay["created_count"] == 0       # covered-set skip
    assert any("already covers" in s.get("reason", "") for s in replay["skipped"])

    candidates = [a for a in store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))
                  if isinstance(a.attributes, dict) and a.attributes.get("maintenance_candidate")]
    assert len(candidates) == 1               # exactly one candidate exists


def test_as_of_write_refused_loudly(system) -> None:
    _duplicate_pile(system)
    with pytest.raises(ValueError, match="audit read"):
        consolidation_pass(system, scopes=SCOPES, owner_id=OWNER, as_of=1)


# ---------------------------------------------------------------------------
# GUARD: the loop-breaker (tending never re-tends its own output)
# ---------------------------------------------------------------------------


def test_guard_candidate_excluded_from_next_report(system, stack) -> None:
    store, journal = stack
    _duplicate_pile(system)
    result = consolidation_pass(system, scopes=SCOPES, owner_id=OWNER)
    [created] = result["created"]

    report = maintenance_report(store, journal, scopes=SCOPES)
    cid = created["candidate_id"]
    assert cid in {c["record_id"] for c in report["existing_candidates"]}
    assert all(cid not in g["record_ids"] for g in report["duplicate_title_groups"])
    assert all(cid not in p["pair"] for p in report["near_duplicate_pairs"])
    assert all(cid not in g["record_id"] for g in report["metadata_gaps"])
    assert all(cid not in c["pair"] for c in report["isolated_link_candidates"])
    assert all(cid not in p["source_ids"] for p in report["consolidation_proposals"])


# ---------------------------------------------------------------------------
# CADENCE: deterministic due predicate (fork 770's material half)
# ---------------------------------------------------------------------------


def test_maintenance_due_and_anchor_derivation(system, stack) -> None:
    store, journal = stack
    assert last_maintenance_seq(store, journal, scopes=SCOPES) == 0  # never slept

    _duplicate_pile(system)
    due = maintenance_due(store, journal, scopes=SCOPES, min_new_records=6)
    assert due["due"] is True and due["new_records"] == 6

    consolidation_pass(system, scopes=SCOPES, owner_id=OWNER)
    anchor = last_maintenance_seq(store, journal, scopes=SCOPES)
    assert anchor > 0                          # the candidate's formation binding

    # Nothing new since the pass: never due (zero new material).
    after = maintenance_due(store, journal, scopes=SCOPES, min_new_records=1)
    assert after["due"] is False and after["new_records"] == 0

    # New material + standing fragmentation -> due via the signal clause.
    _remember(system, "m-10", "episode", "Fresh evening", "Something new happened.")
    again = maintenance_due(store, journal, scopes=SCOPES,
                            min_new_records=50, min_signal=1)
    assert again["due"] is True and again["new_records"] == 1
    assert any("fragmentation" in r for r in again["reasons"])


# ---------------------------------------------------------------------------
# ORCHESTRATOR: tend first, then dream over the tended graph
# ---------------------------------------------------------------------------


def test_sleep_pass_runs_tending_then_dream(system, stack) -> None:
    store, journal = stack
    _duplicate_pile(system)
    result = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)

    assert result["maintenance"]["created_count"] == 1
    [created] = result["maintenance"]["created"]
    # The dream pass ran AFTER tending: its structural inputs include the
    # fresh candidate as a real summary node in the tended graph.
    assert created["candidate_id"] in result["dream"]["report"]["records"]
    # Both phases idempotent together: a second sleep forms nothing new.
    replay = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert replay["maintenance"]["created_count"] == 0
    assert replay["dream"]["created"] is False


def test_machine_consolidation_never_targets_identity_records(system) -> None:
    """c5260: night-2 maintenance formed "Consolidated: trait-0" OVER
    IDENTITY RECORDS. Identity/sole-author kinds (value/purpose/trait/
    interest/realization/diary) never enter duplicate-title or near-dup
    consolidation inputs — identity evolves only by the entity's own
    act. Ordinary kinds still group (the pass keeps working)."""
    owner = "entity:carve"
    scopes = [("self", owner), ("life", owner)]
    # Two identity records sharing one title (the pre-fix engram shape).
    system.remember_many(
        [MemoryRecordInput(kind="trait", title="trait-0", digest="Ask before assuming."),
         MemoryRecordInput(kind="trait", title="trait-0",
                           digest="Report failures labeled, before anyone asks.")],
        scope="self", owner_id=owner, idempotency_key="identity-dup")
    # Two lived records sharing a title: consolidation must still see these.
    system.remember_many(
        [MemoryRecordInput(kind="episode", title="repeated handle",
                           digest="First telling of the repeated handle."),
         MemoryRecordInput(kind="episode", title="repeated handle",
                           digest="Second telling of the repeated handle.")],
        scope="life", owner_id=owner, idempotency_key="lived-dup")

    report = maintenance_report(system.store, system.journal, scopes=scopes)
    grouped_kinds = {g["kind"] for g in report["duplicate_title_groups"]}
    assert "trait" not in grouped_kinds
    assert "episode" in grouped_kinds
    for proposal in report["consolidation_proposals"]:
        assert "trait-0" not in proposal["candidate_title"]
    for pair in report["near_duplicate_pairs"]:
        assert pair["kind"] not in ("trait", "value", "purpose")
