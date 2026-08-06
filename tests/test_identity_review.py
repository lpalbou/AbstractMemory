"""Identity-amendment proposals: the registrar + enactment seam
(dm#124 ruling + the R2 fold; runtime's realize fence is the producer,
wire contract per c4802 corrected at c4817).

Pins: kind=realization forms with the producer's exact wire shape;
identity_review_pass is a PURE READ (registrar never authors) whose
pending set is the candidates fold (lifecycle undisposed) and whose one
mechanical bar is evidence-alive; enact_realization is append-only
(lifecycle binding + derived_from edge from the enacting record —
enacted_at rides fresh rows, never a mutation on the resting proposal);
rejection reuses reject_candidate verbatim; sleep_pass threads
include_identity with cycle-never and honest skip shapes.
"""

from __future__ import annotations

import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    MemoryRecordInput,
    MemorySystem,
    TripleQuery,
    enact_realization,
    identity_review_pass,
    reject_candidate,
    sleep_pass,
)

OWNER = "entity:mnemo"
SCOPES = [("self", OWNER), ("life", OWNER)]

# The `system` fixture comes from conftest and parametrizes BOTH backends
# (memory + sqlite) — adversary P1-4: the review's evidence resolution is
# exactly the ordering-sensitive read backend parametrization exists for.


def _evidence(system: MemorySystem, key: str, digest: str) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title=f"ev {key}", digest=digest)],
        scope="life", owner_id=OWNER, idempotency_key=key)
    return gid


def _realization(system: MemorySystem, key: str, words: str, *evidence: str) -> str:
    """The producer's exact wire shape (runtime c4802)."""
    [gid] = system.remember_many(
        [MemoryRecordInput(
            kind="realization",
            title=f"realization: {' '.join(words.split()[:8])}",
            digest=words,
            edges=tuple(("derived_from", e) for e in evidence),
            attributes={"session_id": "s1", "phase": "personal"},
            provenance={"source": "entity-realize-v1",
                        "actor": "entity-reflection"})],
        scope="self", owner_id=OWNER, idempotency_key=key)
    return gid


def test_review_reports_pending_with_alive_evidence(system) -> None:
    ev = _evidence(system, "e1", "I hesitated, then kept the lesson immediately.")
    rid = _realization(system, "r1",
                       "I keep a lesson the moment I learn it.", ev)

    out = identity_review_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert out["pass_name"] == "identity_review_pass"
    assert out["unit"] == "records"
    assert out["counts"] == {"pending": 1, "bars_failing": 0, "disposed": 0}
    [entry] = out["pending"]
    assert entry["record_id"] == rid
    assert entry["evidence"] == {"unit": "records", "total": 1, "alive": 1}
    assert entry["bar_failures"] == []
    assert entry["session_id"] == "s1" and entry["phase"] == "personal"


def test_review_is_a_pure_read(system) -> None:
    ev = _evidence(system, "e1", "Lived it once, plainly.")
    _realization(system, "r1", "Plain living is enough.", ev)
    seq_before = system.journal.current_seq()
    rows_before = len(system.store.query(TripleQuery(scope="self", owner_id=OWNER, limit=0)))

    identity_review_pass(system, scopes=SCOPES, owner_id=OWNER)

    assert system.journal.current_seq() == seq_before  # registrar never authors
    assert len(system.store.query(TripleQuery(scope="self", owner_id=OWNER, limit=0))) == rows_before


def test_evidence_closed_after_formation_fails_the_bar(system) -> None:
    ev = _evidence(system, "e1", "The ground this rested on.")
    _realization(system, "r1", "Something built on that ground.", ev)
    system.close_record(ev, kind="retract", reason="test: the ground retracts")

    out = identity_review_pass(system, scopes=SCOPES, owner_id=OWNER)
    [entry] = out["pending"]
    assert entry["evidence"]["alive"] == 0
    assert any("closed after the proposal formed" in f for f in entry["bar_failures"])
    assert out["counts"]["bars_failing"] == 1


def test_evidence_free_row_is_named_honestly(system) -> None:
    # The producer refuses these; a historical/foreign row must still be
    # named rather than trusted transitively.
    [rid] = system.remember_many(
        [MemoryRecordInput(kind="realization", title="realization: bare",
                           digest="A proposal with no ground.")],
        scope="self", owner_id=OWNER, idempotency_key="bare")
    out = identity_review_pass(system, scopes=SCOPES, owner_id=OWNER)
    [entry] = out["pending"]
    assert entry["record_id"] == rid
    assert any("no derived_from evidence" in f for f in entry["bar_failures"])


def test_enactment_is_append_only_and_leaves_pending(system) -> None:
    ev = _evidence(system, "e1", "Three sessions, same hesitation.")
    rid = _realization(system, "r1", "I answer before I am certain.", ev)
    # The entity's OWN act, formed first (its words carrying the change).
    [act] = system.remember_many(
        [MemoryRecordInput(kind="value", title="value: honest speed",
                           digest="I answer when I can stand behind the answer.",
                           attributes={"value_class": "revisable"})],
        scope="self", owner_id=OWNER, idempotency_key="act-1")

    out = enact_realization(system.store, system.journal,
                            realization_id=rid, supersession_record_id=act,
                            reason="adopted in session s2, his words")
    assert out["lifecycle"] == "promoted" and out["enacted_by"] == act
    assert out["edge_created"] is True and out["enacted_at"]

    # Pending drains via the SAME fold (pure query, no mutation anywhere).
    review = identity_review_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert review["counts"] == {"pending": 0, "bars_failing": 0, "disposed": 1}

    # The proposal row itself is byte-untouched (append-only law): the
    # stamp lives on the binding + the fresh edge row.
    [proposal_row] = system.store.query(TripleQuery(subject=rid, predicate="dcterms:abstract", limit=1))
    assert "enacted_at" not in (proposal_row.attributes or {})
    edges = [a for a in system.store.query(TripleQuery(subject=act, limit=0))
             if (a.attributes or {}).get("record_edge")
             and a.predicate == "derived_from" and a.object == rid]
    assert len(edges) == 1 and edges[0].attributes["enacted_at"] == out["enacted_at"]

    # Replay lands on the same edge row (crash-safe idempotency).
    again = enact_realization(system.store, system.journal,
                              realization_id=rid, supersession_record_id=act,
                              reason="replay after crash")
    assert again["edge_id"] == out["edge_id"] and again["edge_created"] is False


def test_enactment_refusals_are_loud(system) -> None:
    ev = _evidence(system, "e1", "Ground.")
    rid = _realization(system, "r1", "Words.", ev)
    with pytest.raises(ValueError, match="not a realization"):
        enact_realization(system.store, system.journal,
                          realization_id=ev, supersession_record_id=rid,
                          reason="wrong kind")
    with pytest.raises(ValueError, match="cannot enact itself"):
        enact_realization(system.store, system.journal,
                          realization_id=rid, supersession_record_id=rid,
                          reason="self-enactment")
    with pytest.raises(ValueError, match="does not exist"):
        enact_realization(system.store, system.journal,
                          realization_id=rid,
                          supersession_record_id="ex:ghost",
                          reason="phantom act")
    with pytest.raises(ValueError, match="non-empty reason"):
        enact_realization(system.store, system.journal,
                          realization_id=rid, supersession_record_id=ev,
                          reason="  ")


def test_enactment_refuses_disposed_proposals(system) -> None:
    """Adversary P1-3: a rejected proposal is an audited no — enactment
    must not silently out-fold it; a closed proposal is withdrawn ground."""
    ev = _evidence(system, "e1", "Ground.")
    rejected = _realization(system, "r1", "He said no to this one.", ev)
    reject_candidate(system.store, system.journal,
                     record_id=rejected, scope="self", owner_id=OWNER,
                     reason="his call", actor="entity-reflection")
    with pytest.raises(ValueError, match="REJECTED"):
        enact_realization(system.store, system.journal,
                          realization_id=rejected, supersession_record_id=ev,
                          reason="late change of heart")

    retracted = _realization(system, "r2", "This one was withdrawn.", ev)
    system.close_record(retracted, kind="retract", reason="test: withdrawn")
    with pytest.raises(ValueError, match="CLOSED"):
        enact_realization(system.store, system.journal,
                          realization_id=retracted, supersession_record_id=ev,
                          reason="enacting withdrawn ground")


def test_cross_scope_enactment_edge_rides_the_enacting_scope(system) -> None:
    """Adversary P1-2: the edge follows the SUBJECT'S scope (the convention
    every edge writer holds) — a life-scope elected act adopting a self
    proposal must carry its edge in LIFE scope, or the tombstone sweep on
    a later retraction would strand it."""
    ev = _evidence(system, "e1", "Lived ground.")
    rid = _realization(system, "r1", "Adopted from the life side.", ev)
    [act] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="the adopting act",
                           digest="I acted on it, in my own words.")],
        scope="life", owner_id=OWNER, idempotency_key="act-life")

    out = enact_realization(system.store, system.journal,
                            realization_id=rid, supersession_record_id=act,
                            reason="adopted across scopes")
    edges = [a for a in system.store.query(TripleQuery(scope="life", owner_id=OWNER, limit=0))
             if (a.attributes or {}).get("record_edge")
             and a.assertion_id == out["edge_id"]]
    assert len(edges) == 1, "the enactment edge must live in the enacting record's scope"


def test_row_id_evidence_edges_resolve(system) -> None:
    """Adversary P1-1: both id namespaces resolve — an evidence edge naming
    a ROW id must not read as a false 'no longer resolves'."""
    ev = _evidence(system, "e1", "Ground with two names.")
    [row] = system.store.query(TripleQuery(subject=ev, predicate="dcterms:abstract", limit=1))
    row_id = str(row.assertion_id)
    assert row_id and row_id != ev
    _realization(system, "r1", "Cites the row id.", row_id)

    out = identity_review_pass(system, scopes=SCOPES, owner_id=OWNER)
    [entry] = out["pending"]
    assert entry["evidence"] == {"unit": "records", "total": 1, "alive": 1}
    assert entry["bar_failures"] == []


def test_rejection_reuses_the_candidates_verb(system) -> None:
    ev = _evidence(system, "e1", "Ground.")
    rid = _realization(system, "r1", "A proposal he declines.", ev)
    reject_candidate(system.store, system.journal,
                     record_id=rid, scope="self", owner_id=OWNER,
                     reason="his call: reworded instead", actor="entity-reflection")
    review = identity_review_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert review["counts"]["pending"] == 0
    assert review["counts"]["disposed"] == 1


def test_sleep_pass_threads_include_identity(system) -> None:
    ev = _evidence(system, "e1", "Night material.")
    _realization(system, "r1", "Held for tonight.", ev)

    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert "identity" in night["phases"]
    assert night["identity"]["pass_name"] == "identity_review_pass"
    assert night["identity"]["counts"]["pending"] == 1

    nap = sleep_pass(system, scopes=SCOPES, owner_id=OWNER,
                     include_dream=False, include_identity=False)
    assert "cycle window" in nap["identity"]["skipped_reason"]
    assert nap["identity"]["pending"] == []

    anchored = sleep_pass(system, scopes=SCOPES, owner_id=OWNER,
                          report_only=True, as_of=system.journal.current_seq())
    assert "as_of anchor" in anchored["identity"]["skipped_reason"]


def test_sleep_cancellation_carries_the_identity_shape(system) -> None:
    calls = {"n": 0}

    def one_phase_only() -> bool:
        calls["n"] += 1
        return calls["n"] <= 1  # yield raised right after resolution

    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER,
                       should_continue=one_phase_only)
    identity = night["identity"]
    assert identity["pass_name"] == "identity_review_pass"
    assert "cancelled" in identity["skipped_reason"]
    # Shape parity with the real empty pass, key-for-key.
    assert identity["pending"] == []
    assert identity["counts"] == {"pending": 0, "bars_failing": 0, "disposed": 0}
