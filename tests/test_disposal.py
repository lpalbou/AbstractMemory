"""Disposal: waking evidence decides (fork 690/360/470 adoption).

Contracts pinned:
- confirm_relation refuses unregistered predicates (0016: registry first),
  demands evidence, and refuses the proposing dream as its own evidence;
- the confirmed edge is idempotent and CONDUCTS (spreading/expansion see
  it) without pumping activation (cited = audit-only);
- promote_candidate enforces INDEPENDENT-ORIGIN corroboration — the
  bridge-attractor counter: self-retellings share an origin and never
  corroborate; the refusal names the mechanism;
- reject_candidate records the honest no without erasure;
- dispose_dream composes the verdict: confirmed → edge + supersede (the
  dream leaves the standing-unresolved set); dissolved → retract.
"""

from __future__ import annotations

import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    Stimulus,
    TripleQuery,
    dream_pass,
    unresolved_dreams,
)

OWNER = "entity:disposal-test"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _seed(system):
    """Two islands + distinct-origin witnesses."""
    a = system.remember_many([
        MemoryRecordInput(kind="episode", title="Bridge design talk",
                          digest="We discussed the twelve bridges design at noon.",
                          keywords=("bridges", "design"),
                          provenance={"source": "chat-v1", "actor": "workplace:s1", "session_id": "s1"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="w1")[0]
    b = system.remember_many([
        MemoryRecordInput(kind="episode", title="Bridge dream retold",
                          digest="I retold the bridges idea in my own words again.",
                          keywords=("bridges", "retold"),
                          provenance={"source": "chat-v1", "actor": "workplace:s1", "session_id": "s1"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="w2")[0]
    c = system.remember_many([
        MemoryRecordInput(kind="episode", title="Operator confirms bridges",
                          digest="The operator confirmed the bridges plan in review.",
                          keywords=("bridges", "review"),
                          provenance={"source": "operator-review", "actor": "operator", "session_id": "op-1"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="w3")[0]
    return a, b, c


def test_confirm_relation_refuses_unregistered_predicates(system) -> None:
    a, b, _ = _seed(system)
    with pytest.raises(ValueError, match="engraved edge vocabulary"):
        system.confirm_relation(a, "resonates_with", b,
                                evidence_ids=[b], reason="feels right")


def test_confirm_relation_demands_evidence_and_refuses_self_proof(system) -> None:
    a, b, _ = _seed(system)
    with pytest.raises(ValueError, match="evidence"):
        system.confirm_relation(a, "supports", b, evidence_ids=[], reason="no proof")
    with pytest.raises(ValueError, match="own evidence"):
        system.confirm_relation(a, "supports", b, evidence_ids=["ex:dream-x"],
                                reason="dream as proof", proposed_by="ex:dream-x")


def test_confirmed_edge_is_idempotent_and_audit_only(system) -> None:
    a, b, c = _seed(system)
    counts_before = system.access_counts(record_ids=[a, b])
    first = system.confirm_relation(a, "supports", b, evidence_ids=[c],
                                    reason="the review corroborates the talk")
    again = system.confirm_relation(a, "supports", b, evidence_ids=[c],
                                    reason="replay")
    assert first["edge_id"] == again["edge_id"]
    assert first["created"] is True and again["created"] is False
    # The edge exists as a record edge with disposal provenance.
    [edge] = system.store.query(TripleQuery(assertion_ids=(first["edge_id"],), limit=1))
    assert edge.predicate == "supports" and edge.attributes["confirmed"] is True
    # Audit-only: no usage deposited on either endpoint.
    assert system.access_counts(record_ids=[a, b]) == counts_before


def test_promotion_requires_independent_origins(system) -> None:
    a, b, c = _seed(system)
    # a + b share ONE origin (same source/actor/session) — the self-retelling
    # shape. Promotion on {b} or {b, b-like} must refuse loudly.
    with pytest.raises(ValueError, match="Repetition is not corroboration"):
        system.promote_candidate(a, scope=SCOPE, owner_id=OWNER,
                                 corroborating_ids=[b], reason="one witness, same origin")
    # b (same origin as a) + c (operator origin) = only ONE independent
    # origin distinct from a's own — still short of 2.
    with pytest.raises(ValueError, match="independent origin"):
        system.promote_candidate(a, scope=SCOPE, owner_id=OWNER,
                                 corroborating_ids=[b, c], reason="one real witness")
    # Add a third, second independent origin — promotion passes.
    d = system.remember_many([
        MemoryRecordInput(kind="lesson", title="Sleep pass found it too",
                          digest="The consolidation pass independently proposed the bridge.",
                          provenance={"source": "sleep-pass", "actor": "system", "session_id": "night-1"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="w4")[0]
    out = system.promote_candidate(a, scope=SCOPE, owner_id=OWNER,
                                   corroborating_ids=[c, d],
                                   reason="two independent witnesses")
    assert out["lifecycle"] == "promoted" and out["independent_origins"] == 2
    # The binding fold reflects the promotion.
    [binding] = [x for x in system.journal.bindings(scope=SCOPE, owner_id=OWNER, fold=True)
                 if x.record_id == a]
    assert binding.lifecycle == "promoted"


def test_promotion_never_flips_prompt_state_implicitly(system) -> None:
    a, _, c = _seed(system)
    d = system.remember_many([
        MemoryRecordInput(kind="lesson", title="Independent again",
                          digest="Another independent sighting.",
                          provenance={"source": "web-search", "actor": "tool", "session_id": "t-9"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="w5")[0]
    system.promote_candidate(a, scope=SCOPE, owner_id=OWNER,
                             corroborating_ids=[c, d], reason="promote quietly")
    [binding] = [x for x in system.journal.bindings(scope=SCOPE, owner_id=OWNER, fold=True)
                 if x.record_id == a]
    assert binding.prompt_state == "inactive"  # warm-core flips must be said, never implied


def test_min_origins_floor_and_row_id_namespace(system) -> None:
    """Adversary finds 3+4: min_origins<1 refuses (a zero-corroboration
    promotion is not promotion); disposal accepts BOTH id namespaces (row
    ids are the currency reconstruct hands hosts)."""
    a, b, c = _seed(system)
    with pytest.raises(ValueError, match="min_origins must be >= 1"):
        system.promote_candidate(a, scope=SCOPE, owner_id=OWNER,
                                 corroborating_ids=[], reason="no bar", min_origins=0)
    # Resolve a's digest ROW id and confirm through it.
    row = next(x for x in system.store.query(TripleQuery(subject=a, limit=0))
               if x.attributes.get("record_kind"))
    out = system.confirm_relation(row.assertion_id, "supports", c,
                                  evidence_ids=[b], reason="row-id namespace works")
    assert out["source_id"] == a  # resolved back to the graph subject


def test_context_relations_are_not_confirmable(system) -> None:
    """Adversary find 6: `mentions` is the dream's own weak-link currency
    and `written_amid` is projection-only — neither may carry a
    'confirmed' claim."""
    a, b, _ = _seed(system)
    for rel in ("mentions", "written_amid"):
        with pytest.raises(ValueError, match="engraved edge vocabulary"):
            system.confirm_relation(a, rel, b, evidence_ids=[b], reason="inert claim")


def test_reconfirmation_with_new_evidence_records_its_own_audit_event(system) -> None:
    """Adversary find 7: the edge stays ONE, but each distinct evidence set
    is a distinct judging act with its own cited events."""
    a, b, c = _seed(system)
    system.confirm_relation(a, "supports", b, evidence_ids=[c], reason="first evidence")
    d = system.remember_many([
        MemoryRecordInput(kind="episode", title="Fresh witness",
                          digest="A later independent sighting.",
                          provenance={"source": "walk", "actor": "entity", "session_id": "s9"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="w9")[0]
    out = system.confirm_relation(a, "supports", b, evidence_ids=[d], reason="new evidence")
    assert out["created"] is False and out["evidence_recorded"] is True
    cited = [e for e in system.journal.events(scope=SCOPE, owner_id=OWNER)
             if e.kind == "cited" and e.record_id == a]
    assert len(cited) == 2  # one per distinct evidence set
    evidence_sets = {tuple(e.provenance.get("evidence") or ()) for e in cited}
    assert len(evidence_sets) == 2


def test_reject_candidate_records_the_no_without_erasure(system) -> None:
    a, _, _ = _seed(system)
    out = system.reject_candidate(a, scope=SCOPE, owner_id=OWNER,
                                  reason="waking evidence says otherwise")
    assert out["lifecycle"] == "rejected" and out["hidden"] is False
    [binding] = [x for x in system.journal.bindings(scope=SCOPE, owner_id=OWNER, fold=True)
                 if x.record_id == a]
    assert binding.lifecycle == "rejected"
    assert binding.search_state == "indexed"  # judgment is not erasure


def _dream_world(system):
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Noon pool anomaly",
                          digest="The pool reflected an anomaly at noon.",
                          keywords=("pool", "noon", "anomaly")),
        MemoryRecordInput(kind="episode", title="Garden pond stillness",
                          digest="The garden pond held a strange stillness at noon.",
                          keywords=("pond", "noon", "garden")),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="dw")
    return dream_pass(system, scopes=SCOPES, owner_id=OWNER)


def test_dispose_dream_confirmed_writes_edge_and_supersedes(system) -> None:
    night = _dream_world(system)
    dream_id = night["dream_record_id"]
    assert dream_id
    pair = night["proposals"][0]["pair"] if night["proposals"] else night["questions"][0]["pair"]
    witness = system.remember_many([
        MemoryRecordInput(kind="episode", title="Both ponds one system",
                          digest="Walked the garden: pool and pond share the same water table.",
                          provenance={"source": "walk", "actor": "entity", "session_id": "day-2"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="witness")[0]

    out = system.dispose_dream(dream_id, disposition="confirmed",
                               reason="the walk confirmed the shared water table",
                               relation="supports", source_id=pair[0],
                               target_id=pair[1], evidence_ids=[witness])
    assert out["edge"]["created"] is True
    # The dream leaves the standing-unresolved set (supersede closure).
    standing = unresolved_dreams(system.store, scope=SCOPE, owner_id=OWNER,
                                 journal=system.journal)
    assert all(a.subject != dream_id for a in standing)


def test_dispose_dream_dissolved_retracts(system) -> None:
    night = _dream_world(system)
    dream_id = night["dream_record_id"]
    out = system.dispose_dream(dream_id, disposition="dissolved",
                               reason="waking walk showed two unrelated basins")
    assert out["closure_ids"]
    standing = unresolved_dreams(system.store, scope=SCOPE, owner_id=OWNER,
                                 journal=system.journal)
    assert all(a.subject != dream_id for a in standing)


def test_dispose_dream_refuses_non_dreams_and_bad_dispositions(system) -> None:
    a, _, _ = _seed(system)
    with pytest.raises(ValueError, match="not a dream"):
        system.dispose_dream(a, disposition="confirmed", reason="wrong kind",
                             relation="supports", source_id=a, target_id=a)
    night = _dream_world(system)
    with pytest.raises(ValueError, match="disposition"):
        system.dispose_dream(night["dream_record_id"], disposition="maybe",
                             reason="fence sitting")
