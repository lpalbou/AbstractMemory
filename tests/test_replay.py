"""The replay/observability stream (a2a 0005 schema v1): one envelope shape
for history scrub AND live tail — verbatim journal records, strict seq
order, deterministic, resumable by cursor, enrichment marked-not-fabricated,
diary content redacted for audience enforcement."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from abstractmemory import Stimulus, TripleAssertion, export_replay
from abstractmemory.records import MemoryRecordInput
from abstractmemory.replay import REPLAY_FAMILIES

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _assertion(aid: str, s: str, p: str, o: str, t: int) -> TripleAssertion:
    return TripleAssertion(subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
                           observed_at=f"2026-07-05T10:{t:02d}:00.000000+00:00",
                           assertion_id=aid)


def _busy_session(system) -> Dict[str, str]:
    """Every family exercised: formation (bindings), recall (trace +
    listed events), commit (selected/co_selected + snapshot), a closure,
    an appraisal, and a diary projection."""
    [lesson] = system.remember_many(
        [MemoryRecordInput(kind="lesson", title="Batching", digest="batch the sensor writes",
                           keywords=("batch",))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="rp-lesson")
    [diary] = system.remember_many(
        [MemoryRecordInput(kind="diary", title="Quiet morning",
                           digest="Wrote about the quiet morning.",
                           attributes={"entry_id": "entry-7"},
                           provenance={"source": "diary-projection"})],
        scope=SCOPE, owner_id=OWNER, idempotency_key="rp-diary")
    system.add([_assertion("m-a", "alice", "wrote", "fusion report", 1),
                _assertion("m-b", "alice", "filed", "fusion appendix", 2)])
    system.reconstruct(Stimulus(cue_text="fusion"), scopes=SCOPES, trace_id="rp-read")
    system.commit_selection("rp-read", ["m-a", "m-b"])
    system.close_record(lesson, reason="superseded by practice")
    system.appraise("tool:batcher", sign=1, magnitude=2, reason="worked",
                    scope=SCOPE, owner_id=OWNER)
    return {"lesson": lesson, "diary": diary}


def test_all_families_in_strict_seq_order_verbatim(system, stack) -> None:
    _, journal = stack
    _busy_session(system)
    items = list(system.export_replay())

    seqs = [i["seq"] for i in items]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)  # strict total order
    assert {i["family"] for i in items} == set(REPLAY_FAMILIES)  # all six present
    for i in items:
        assert i["stream"] == "abstractmemory.replay" and i["stream_version"] == 1
        assert isinstance(i["observed_at"], str) and i["observed_at"]
        # Correlation keys (v1 freeze, delta 1): always present, null OK.
        assert {"trace_id", "turn_id", "run_id"} <= set(i)

    # Verbatim payloads: for each family, the payload equals the stored
    # record's to_dict() (spot-checked via the journal readers).
    by_family: Dict[str, List[Dict[str, Any]]] = {}
    for i in items:
        by_family.setdefault(i["family"], []).append(i)
    [closure] = journal.closures(limit=0)[:1]
    assert any(i["payload"] == closure.to_dict() for i in by_family["closure"])
    [valence] = journal.valence_events(scope=SCOPE, owner_id=OWNER, limit=1)
    assert any(i["payload"] == valence.to_dict() for i in by_family["valence"])
    trace = journal.traces(trace_id="rp-read", limit=1)[0]
    assert any(i["payload"] == trace.to_dict() for i in by_family["trace"])


def test_family_scope_and_window_filters(system, stack) -> None:
    _, journal = stack
    _busy_session(system)
    # families subset
    only_events = list(system.export_replay(families=["event"]))
    assert only_events and all(i["family"] == "event" for i in only_events)
    with pytest.raises(ValueError, match="unknown replay families"):
        list(system.export_replay(families=["event", "ghost"]))
    # Reserved family "host" (v1 freeze, delta 2): accepted, yields nothing
    # from memory — the gateway interleaves its markers transport-side.
    assert list(system.export_replay(families=["host"])) == []
    with pytest.raises(ValueError, match="bogus"):
        list(system.export_replay(families=["bogus"]))

    # scope filter matches lifted scopes (incl. traces via searched set and
    # snapshots via their trace).
    scoped = list(system.export_replay(scope=SCOPE, owner_id=OWNER))
    assert {i["family"] for i in scoped} == set(REPLAY_FAMILIES)
    assert all(i["scope"] == SCOPE and i["owner_id"] == OWNER for i in scoped)
    assert list(system.export_replay(scope="elsewhere")) == []

    # since (exclusive) / until (inclusive) windows partition the stream.
    everything = list(system.export_replay())
    mid = everything[len(everything) // 2]["seq"]
    head = list(system.export_replay(until_seq=mid))
    tail = list(system.export_replay(since_seq=mid))
    assert [i["seq"] for i in head] + [i["seq"] for i in tail] == [i["seq"] for i in everything]
    assert head[-1]["seq"] == mid          # until inclusive
    assert tail[0]["seq"] > mid            # since exclusive


def test_resumption_no_gap_no_repeat(system) -> None:
    _busy_session(system)
    everything = list(system.export_replay())
    cursor = 0
    resumed: List[Dict[str, Any]] = []
    while True:
        batch = list(system.export_replay(since_seq=cursor, until_seq=cursor + 3))
        resumed.extend(batch)
        cursor += 3
        if cursor >= everything[-1]["seq"]:
            break
    assert [i["seq"] for i in resumed] == [i["seq"] for i in everything]


def test_determinism_two_calls_identical(system) -> None:
    _busy_session(system)
    first = list(system.export_replay())
    second = list(system.export_replay())
    assert first == second


def test_enrichment_shape_pairs_and_absence(system) -> None:
    ids = _busy_session(system)
    items = list(system.export_replay())

    # A selected event over a PLAIN triple (m-a/m-b) enriches without a
    # graph_id — plain subjects are not formed-record graph ids (no
    # fabrication; this is the observer-delta omission path).
    selected = [i for i in items if i["family"] == "event"
                and i["payload"].get("kind") == "selected"]
    assert selected and all("display" in i for i in selected)
    block = selected[0]["display"]
    assert set(block) == {"record_id", "kind", "title", "token_estimate"}
    assert block["record_id"] == selected[0]["payload"]["record_id"]

    # co_selected enriches BOTH pair members (plain triples here: no graph_id).
    pairs = [i for i in items if i["family"] == "event"
             and i["payload"].get("kind") == "co_selected"]
    assert pairs and all(set(i["display"]) == {"pair"} for i in pairs)
    assert len(pairs[0]["display"]["pair"]) == 2

    # The lesson's formation binding enriches via the graph id; after the
    # engram-style close its closure enriches too (records are immutable —
    # closure is journal state, the store row remains resolvable). FORMED
    # records carry graph_id — the namespace join key (observer delta):
    # binding record_id == graph id; the block also surfaces it explicitly,
    # and the two namespaces differ.
    lesson_bindings = [i for i in items if i["family"] == "binding"
                       and i["payload"]["record_id"] == ids["lesson"]]
    assert lesson_bindings and lesson_bindings[0]["display"]["kind"] == "lesson"
    lesson_block = lesson_bindings[0]["display"]
    assert set(lesson_block) == {"record_id", "kind", "title", "token_estimate", "graph_id"}
    assert lesson_block["graph_id"] == ids["lesson"]

    # The lesson's closure enriches keyed by the ASSERTION id namespace —
    # graph_id joins it back to the binding's graph-id namespace.
    lesson_closures = [i for i in items if i["family"] == "closure"
                       and i["display"].get("graph_id") == ids["lesson"]]
    assert lesson_closures
    closure_block = lesson_closures[0]["display"]
    assert closure_block["record_id"] != closure_block["graph_id"]  # two namespaces, joined

    # A valence event over a free-string target: unresolvable → NO display,
    # never fabricated.
    valence = [i for i in items if i["family"] == "valence"]
    assert valence and all("display" not in i for i in valence)

    # enrich=False gives the pure ledger stream.
    assert all("display" not in i for i in system.export_replay(enrich=False))


def test_correlation_keys_lift_per_family(system) -> None:
    """v1-freeze delta 1: trace_id/turn_id/run_id are pure liftings for the
    viewer's beat grouping — always present, null when the record carries
    no correlation info."""
    _busy_session(system)
    system.appraise("tool:batcher", sign=1, magnitude=1, reason="beat-tagged",
                    scope=SCOPE, owner_id=OWNER, trace_id="rp-beat",
                    provenance={"turn_id": "t7", "run_id": "run-42"})
    items = list(system.export_replay())

    # Traces and snapshots carry their own trace_id.
    trace = next(i for i in items if i["family"] == "trace")
    assert trace["trace_id"] == "rp-read" and trace["turn_id"] is None
    snapshot = next(i for i in items if i["family"] == "snapshot")
    assert snapshot["trace_id"] == "rp-read"

    # A valence event lifts its trace_id field + provenance turn/run.
    tagged = next(i for i in items if i["family"] == "valence"
                  and i["payload"]["reason"] == "beat-tagged")
    assert (tagged["trace_id"], tagged["turn_id"], tagged["run_id"]) == (
        "rp-beat", "t7", "run-42")

    # Formation events carry turn provenance (remember_many turn_id rides
    # provenance); a record with no correlation info has all three = None.
    listed = [i for i in items if i["family"] == "event"
              and i["payload"]["kind"] == "listed"]
    assert listed and listed[0]["trace_id"] == "rp-read"
    closure = next(i for i in items if i["family"] == "closure")
    assert (closure["trace_id"], closure["turn_id"], closure["run_id"]) == (None, None, None)


def test_diary_display_is_redacted(system) -> None:
    ids = _busy_session(system)
    items = list(system.export_replay(families=["binding"]))
    diary_bindings = [i for i in items if i["payload"]["record_id"] == ids["diary"]]
    assert diary_bindings
    for i in diary_bindings:
        # Topology = existence + IDENTITY + connections (observer delta):
        # the opaque graph_id joins the diary lane; content stays sealed.
        assert i["display"] == {"redacted": "diary", "graph_id": ids["diary"]}
        assert "Quiet morning" not in str(i["display"])


def test_formed_pair_members_carry_graph_id(system) -> None:
    """co_selected enrichment over FORMED records: each pair member carries
    graph_id (the observer's namespace join), distinct from the assertion
    row id the trail events key on."""
    from abstractmemory import Stimulus as _Stimulus
    gids = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Outage A", digest="alpha outage handled"),
         MemoryRecordInput(kind="episode", title="Outage B", digest="alpha outage documented",
                           edges=(("follows", "local:0"),))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="rp-pair")
    r = system.reconstruct(_Stimulus(cue_text="alpha outage"), scopes=SCOPES,
                           trace_id="rp-pair-read")
    system.commit_selection("rp-pair-read", gids)

    pairs = [i for i in system.export_replay(families=["event"])
             if i["payload"].get("kind") == "co_selected" and "display" in i]
    assert pairs
    members = pairs[0]["display"]["pair"]
    assert len(members) == 2
    for m in members:
        assert m["graph_id"] in gids
        assert m["record_id"] != m["graph_id"]  # assertion id vs graph id, joined


def test_binding_display_carries_formation_edges(system) -> None:
    """Ask 2 (0007, display-only additive): an edge-bearing formed record's
    binding envelope carries display.edges so the view draws "known" links
    distinct from lit usage trails; edgeless records carry NO edges key;
    diary blocks carry edges TOO but never content (observer e-s 253 gap:
    the maintainer's diary-connectivity ruling made written_amid ACT-FRAME
    — "the edge is act-frame, the words stay in the book" — so sealing
    edges made diary connectivity invisible in pixels while present at
    rest; an edge is relation + opaque target graph id, node identity by
    the same justification as the block's own graph_id)."""
    gids = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Storm watch", digest="watched the storm roll in"),
         MemoryRecordInput(kind="episode", title="Storm log", digest="logged the storm damage",
                           edges=(("follows", "local:0"),))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="rp-edges")
    [diary] = system.remember_many(
        [MemoryRecordInput(kind="diary", title="Storm feelings",
                           digest="Wrote privately about the storm.",
                           attributes={"entry_id": "entry-9"},
                           provenance={"source": "diary-projection"},
                           edges=(("written_amid", gids[0]),))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="rp-edges-diary")

    bindings = {i["payload"]["record_id"]: i["display"]
                for i in system.export_replay(families=["binding"])}
    assert bindings[gids[1]]["edges"] == [
        {"relation": "follows", "target_graph_id": gids[0]}]
    assert "edges" not in bindings[gids[0]]              # edgeless: no key, no fabrication
    sealed = bindings[diary]
    assert sealed["redacted"] == "diary"                  # content marker stands
    assert sealed["graph_id"] == diary
    assert sealed["edges"] == [                           # act-frame topology visible
        {"relation": "written_amid", "target_graph_id": gids[0]}]
    # Redaction semantics: no content fields ever (title/digest/kind/tokens).
    assert not {"title", "kind", "token_estimate", "record_id"} & set(sealed)
    assert "Storm feelings" not in str(sealed) and "privately" not in str(sealed)