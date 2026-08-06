"""Formation write API v1 (a2a 0001/009 addendum 1, 0001/011 ask 1).

remember_many/remember over both backend stacks: deterministic idempotent
encoding, same-turn selectability with kind/title/topic/payload enrichment,
edge traversability under spreading, 0020 kind-priority ordering, the raw
payload tier, and input validation. Bridge scope only — the full typed
record model is backlog 0021.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, List

import pytest

from abstractmemory import MemoryRecordInput, RecallBudget, Stimulus
from abstractmemory.records import KIND_RANKS, MEMORY_RECORD_KINDS
from abstractmemory.store import TripleQuery

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _record(**kw: Any) -> MemoryRecordInput:
    defaults: dict[str, Any] = {
        "kind": "memory",
        "title": "A note",
        "digest": "Something worth remembering.",
    }
    defaults.update(kw)
    return MemoryRecordInput(**defaults)


def _ids(result) -> List[str]:
    return [h.record_id for h in result.handles]


def _store_count(store) -> int:
    return len(store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0)))


# ---------------------------------------------------------------------------
# round-trip: form -> reconstruct with enrichment
# ---------------------------------------------------------------------------


def test_remember_many_round_trip_with_enrichment(system, stack) -> None:
    _, journal = stack
    lesson = _record(
        kind="lesson",
        title="Connection pool sizing lesson",
        digest="Always size the connection pool from measured concurrency.",
        intents=("avoid outage recurrence",),
        outcomes=("pool resized",),
        keywords=("pool", "concurrency"),
        payload_ref="artifact-123",
        topic="A",
        confidence=0.9,
    )
    note = _record(kind="memory", title="Tea note", digest="Bob mentioned liking green tea.")

    record_ids = system.remember_many(
        [lesson, note], scope=SCOPE, owner_id=OWNER,
        idempotency_key="turn-1-formation", turn_id="turn-1",
    )
    assert len(record_ids) == 2
    assert record_ids[0].startswith("ex:lesson-") and record_ids[1].startswith("ex:memory-")

    r = system.reconstruct(Stimulus(cue_text="connection pool"), scopes=SCOPES)
    by_title = {h.title: h for h in r.handles}
    h = by_title["Connection pool sizing lesson"]  # stored title, not "s p o"
    assert h.kind == "lesson"
    assert "Always size the connection pool" in h.digest
    assert h.provenance["topic"] == "A"
    assert h.provenance["record_id"] == record_ids[0]  # graph id correlation
    assert h.provenance["assertion_provenance"]["turn_id"] == "turn-1"
    assert h.payload_tiers == ("digest", "raw")   # payload_ref -> raw reachable
    assert h.binding == "indexed+inactive"        # formation binding, folded
    assert h.relevance["keyword"] == 1.0

    plain = by_title["Tea note"]
    assert plain.kind == "memory" and plain.payload_tiers == ("digest",)

    # Formation journaled a binding per record (lifecycle audit)...
    folded = journal.bindings(record_id=record_ids[0], fold=True)
    assert len(folded) == 1
    b = folded[0]
    assert (b.search_state, b.prompt_state, b.lifecycle, b.source) == (
        "indexed", "inactive", "inactive_candidate", "remember",
    )
    assert b.provenance == {"turn_id": "turn-1"}
    # ...and NO attention events: forming is not using (0018).
    assert journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected", "co_selected"], limit=0) == []


# ---------------------------------------------------------------------------
# idempotency
# ---------------------------------------------------------------------------


def test_remember_many_replay_is_a_true_noop(system, stack) -> None:
    store, journal = stack
    records = [
        _record(kind="decision", title="Pooler", digest="Use pgbouncer.", payload_ref="a-1"),
        _record(kind="memory", title="Note", digest="Checkout latency complaints."),
    ]
    first = system.remember_many(records, scope=SCOPE, owner_id=OWNER, idempotency_key="k-1")
    assertions_after = _store_count(store)
    bindings_after = len(journal.bindings(fold=False))
    seq_after = journal.current_seq()

    replay = system.remember_many(records, scope=SCOPE, owner_id=OWNER, idempotency_key="k-1")
    assert replay == first                                   # same ids, input order
    assert _store_count(store) == assertions_after           # no new assertions
    assert len(journal.bindings(fold=False)) == bindings_after  # no new bindings
    assert journal.current_seq() == seq_after                # journal untouched

    # A different idempotency key is a DIFFERENT formation (new identities).
    other = system.remember_many(records, scope=SCOPE, owner_id=OWNER, idempotency_key="k-2")
    assert set(other).isdisjoint(set(first))
    assert _store_count(store) == assertions_after * 2


def test_remember_single_wrapper(system) -> None:
    rid = system.remember(
        _record(kind="plan", title="P", digest="Ship the harness."),
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-single",
    )
    assert rid.startswith("ex:plan-")
    assert system.payload(rid)["content"].endswith("Ship the harness.")


# ---------------------------------------------------------------------------
# edges: traversable by spreading
# ---------------------------------------------------------------------------


def test_edges_create_traversable_assertions(system) -> None:
    [target_id] = system.remember_many(
        [_record(kind="memory", title="Latency report", digest="Checkout latency complaints from ops.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-target",
    )
    [source_id] = system.remember_many(
        [_record(
            kind="decision", title="Pooler decision", digest="Use pgbouncer for pooling.",
            edges=(("derived_from", target_id),),
        )],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-source",
    )

    # Cue matches ONLY the source digest; the linked record gains spread
    # through the edge assertion (source -> edge -> target digest, 2 hops).
    r = system.reconstruct(
        Stimulus(cue_text="pgbouncer"), scopes=SCOPES,
        budget=RecallBudget(), view="working_set",
    )
    assert any(e["predicate"] == "derived_from" for e in r.edges)
    linked = [h for h in r.handles if h.provenance.get("record_id") == target_id]
    assert linked and linked[0].activation["spread"] > 0.0
    assert linked[0].relevance == {}  # reached by graph, not by the cue
    assert source_id  # formed ids remain the graph identities the edges name


def test_one_digest_row_per_graph_record_invariant(system, stack) -> None:
    """CROSS-CONSUMER CONTRACT (a2a 0005, observer): exactly ONE
    dcterms:abstract digest row exists per graph record id, through every
    formation path — the observer's structural edge-row detection ("a
    second row claiming a mapped graph_id must be an edge") relies on it.
    If this invariant must ever weaken, flag the observer on the channel
    BEFORE shipping."""
    store, _ = stack

    def digest_rows(graph_id: str) -> List[Any]:
        return store.query(TripleQuery(
            subject=graph_id, predicate="dcterms:abstract",
            scope=SCOPE, owner_id=OWNER, limit=0,
        ))

    # Plain formation + true-noop replay: still one digest row.
    [rid] = system.remember_many(
        [_record(kind="episode", title="Walk", digest="First walk in the park.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="inv-1",
    )
    system.remember_many(
        [_record(kind="episode", title="Walk", digest="First walk in the park.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="inv-1",
    )
    assert len(digest_rows(rid)) == 1

    # Edge-bearing formation: edge rows are subject-keyed to the SOURCE
    # graph id but carry a DIFFERENT predicate — never a second digest.
    [src] = system.remember_many(
        [_record(kind="decision", title="D", digest="Chose the park route.",
                 edges=(("derived_from", rid),))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="inv-2",
    )
    assert len(digest_rows(src)) == 1
    assert len(digest_rows(rid)) == 1

    # Record-level revision (close + form new): the NEW record is a NEW
    # graph id with its own single digest row; the old row stays single.
    system.close_record(rid, kind="supersede", reason="revised",
                        replacement_ids=(src,))
    assert len(digest_rows(rid)) == 1


# ---------------------------------------------------------------------------
# kind ranking (0020 kind priority)
# ---------------------------------------------------------------------------


def test_lesson_outranks_memory_at_equal_relevance(system) -> None:
    # The memory record is encoded AFTER the lesson (newer observed_at), so
    # pure recency would rank it first — kind priority must win instead.
    system.remember_many(
        [
            _record(kind="lesson", title="Pooling lesson", digest="Pooling needs warmup."),
            _record(kind="memory", title="Pooling chat", digest="Pooling came up in chat."),
        ],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-rank",
    )
    r = system.reconstruct(Stimulus(cue_text="pooling"), scopes=SCOPES)
    kinds = [h.kind for h in r.handles]
    assert kinds.index("lesson") < kinds.index("memory")
    # The rank table covers all ten kinds; lower rank = earlier (documented).
    assert set(KIND_RANKS) == MEMORY_RECORD_KINDS
    assert KIND_RANKS["lesson"] == 0 and KIND_RANKS["memory"] == 9


# ---------------------------------------------------------------------------
# payload tiers on formed records
# ---------------------------------------------------------------------------


def test_payload_raw_tier_returns_host_reference(system) -> None:
    [with_ref] = system.remember_many(
        [_record(kind="episode", title="Turn 3", digest="User asked about pooling.", payload_ref="art-9")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-raw",
    )
    [without_ref] = system.remember_many(
        [_record(kind="memory", title="N", digest="No verbatim stored.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-noraw",
    )

    out = system.payload(with_ref, tier="raw")
    assert out == {"record_id": with_ref, "tier": "raw", "payload_ref": "art-9",
                   "content": None, "token_estimate": None}
    with pytest.raises(ValueError, match="no raw tier"):
        system.payload(without_ref, tier="raw")

    # digest tier resolves record ids via the digest assertion (subject path)
    # and the assertion-id path stays equivalent (handle.record_id).
    digest_via_record_id = system.payload(with_ref)
    r = system.reconstruct(Stimulus(cue_text="pooling"), scopes=SCOPES)
    handle = next(h for h in r.handles if h.provenance.get("record_id") == with_ref)
    digest_via_assertion_id = system.payload(handle.record_id)
    assert digest_via_record_id["content"] == digest_via_assertion_id["content"] == handle.digest


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_record_input_validation() -> None:
    with pytest.raises(ValueError, match="digest"):
        _record(digest="   ")
    with pytest.raises(ValueError, match="title"):
        _record(title="")
    with pytest.raises(ValueError, match="kind"):
        _record(kind="vibe")
    with pytest.raises(ValueError, match="summary records require at least one edge"):
        _record(kind="summary", digest="Summarizes nothing.")
    assert _record(kind="summary", edges=(("summarizes", "ex:memory-abc"),)).edges
    with pytest.raises(ValueError, match="pairs"):
        _record(edges=(("only-relation",),))


def test_remember_many_input_validation(system) -> None:
    with pytest.raises(ValueError, match="idempotency_key"):
        system.remember_many([_record()], scope=SCOPE, owner_id=OWNER, idempotency_key="  ")
    with pytest.raises(ValueError, match="at least one MemoryRecordInput"):
        system.remember_many([], scope=SCOPE, owner_id=OWNER, idempotency_key="k")
    with pytest.raises(ValueError, match="scope"):
        system.remember_many([_record()], scope=" ", owner_id=OWNER, idempotency_key="k")
    with pytest.raises(TypeError, match="MemoryRecordInput"):
        system.remember_many([{"kind": "memory"}], scope=SCOPE, owner_id=OWNER, idempotency_key="k")


def test_record_input_is_json_safe_via_asdict() -> None:
    record = _record(
        kind="answer", intents=("i",), outcomes=("o",), keywords=("k",),
        edges=(("supports", "ex:claim-x"),), payload_ref="a-1", topic="B",
        confidence=0.5, attributes={"extra": 1}, provenance={"run_id": "r1"},
    )
    payload = json.loads(json.dumps(asdict(record)))
    assert payload["kind"] == "answer"
    assert payload["edges"] == [["supports", "ex:claim-x"]]
    assert payload["attributes"] == {"extra": 1}
