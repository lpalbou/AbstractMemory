"""The union working set (maintainer's model, 2026-07-06 decisions).

"STM = the memories + edges with the highest temporal access counts.
Passive reconstruction = STM + memories retrieved by selection based on
stimulus." Locked: UNION admission; selected-use-only increments;
activity-relative decay — plus the presence ≠ use guard (a rendered STM
member must not saturate into un-evictability) and the C3 fill rule (STM
never displaces channel-matched candidates under scarcity).

Runs on the shared conftest `stack`/`system` fixtures (both backend pairs).
"""

from __future__ import annotations

from typing import Any, List

import pytest

from abstractmemory import (
    AttentionConfig,
    InMemoryJournal,
    InMemoryTripleStore,
    MemorySystem,
    RecallBudget,
    Stimulus,
    TripleAssertion,
)
from abstractmemory.canonical_text import canonical_text, handle_digest
from abstractmemory.records import MemoryRecordInput

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _ts(i: int) -> str:
    return f"2026-07-05T{10 + i // 60:02d}:{i % 60:02d}:00.000000+00:00"


def _assertion(aid: str, s: str, p: str, o: str, t: int, **attrs: Any) -> TripleAssertion:
    return TripleAssertion(subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
                           observed_at=_ts(t), attributes=dict(attrs), assertion_id=aid)


def _ids(result) -> List[str]:
    return [h.record_id for h in result.handles]


def _blank(system, **kw):
    return system.reconstruct(Stimulus(cue_text=""), scopes=SCOPES, journal=False, **kw)


# ---------------------------------------------------------------------------
# STM component basics
# ---------------------------------------------------------------------------


def test_stm_admits_trail_hot_records_stimulus_free(system) -> None:
    system.add([
        _assertion("hot-a", "alice", "wrote", "fusion report", 1),
        _assertion("hot-b", "bob", "filed", "tax form", 2),
        _assertion("cold-c", "carol", "likes", "tea", 3),
    ])
    system.commit_selection("t-warm-1", ["hot-a", "hot-b"])
    system.commit_selection("t-warm-2", ["hot-a"])  # hot-a hotter than hot-b

    r = _blank(system)  # blank cue: no channels — pure STM + recents
    by_id = {h.record_id: h for h in r.handles}
    # STM block leads the shelf, ranked by base_level desc.
    assert _ids(r)[:2] == ["hot-a", "hot-b"]
    assert by_id["hot-a"].admission == "stm" and by_id["hot-b"].admission == "stm"
    assert by_id["hot-a"].activation["base_level"] > by_id["hot-b"].activation["base_level"]
    # Cues stay honest: either the activation contributions explain the STM
    # presence, or the dedicated trail-hot cue does (never empty).
    assert any(c.startswith(("selected +", "stm: trail-hot")) for c in by_id["hot-a"].cues)
    # The cold recent is stimulus-component presence.
    assert by_id["cold-c"].admission == "stimulus"
    # budget_spent decomposes the union.
    assert r.budget_spent["stm_handles"] == 2
    assert r.budget_spent["stm_tokens_used"] > 0


def test_tokens_used_counts_stm_tokens_exactly_once(system) -> None:
    """a2a 0001/015 finding 1: tokens_used double-counted the STM component
    (added in the STM fill AND again after handle building), poisoning any
    ledger-side budget-integrity check. Exact arithmetic: tokens_used ==
    sum of the shelved handles' token_estimates; stm_tokens_used == the
    STM-labeled subset."""
    system.add([
        _assertion("hot-a", "alice", "wrote", "fusion report", 1),
        _assertion("hot-b", "bob", "filed", "tax form", 2),
        _assertion("cold-c", "carol", "likes", "tea", 3),
    ])
    system.commit_selection("t-warm-1", ["hot-a", "hot-b"])

    r = _blank(system)  # STM members + a stimulus recent on one shelf
    labels = {h.record_id: h.admission for h in r.handles}
    assert "stm" in labels.values() and "stimulus" in labels.values()  # both components present
    expected_total = sum(h.token_estimate for h in r.handles)
    expected_stm = sum(h.token_estimate for h in r.handles if h.admission == "stm")
    assert r.budget_spent["tokens_used"] == expected_total  # exactly once
    assert r.budget_spent["stm_tokens_used"] == expected_stm
    assert expected_stm > 0  # the regression is only meaningful with STM tokens on the shelf


def test_stm_fraction_zero_is_pure_stimulus_mode(system) -> None:
    system.add([_assertion("hot-a", "alice", "wrote", "fusion report", 1)])
    system.commit_selection("t-warm", ["hot-a"])
    r = _blank(system, budget=RecallBudget(stm_fraction=0.0))
    by_id = {h.record_id: h for h in r.handles}
    assert by_id["hot-a"].admission == "stimulus"  # recency presence only
    assert r.budget_spent["stm_handles"] == 0
    assert all(e.get("source") != "stm_trail" for e in r.edges)


def test_quiet_trail_means_empty_stm_no_special_case(system) -> None:
    system.add([_assertion("a-1", "alice", "wrote", "report", 1)])
    r = _blank(system)
    assert r.budget_spent["stm_handles"] == 0
    assert [h.admission for h in r.handles] == ["stimulus"]


def test_stm_floor_budget_override(system) -> None:
    system.add([_assertion("hot-a", "alice", "wrote", "report", 1)])
    system.commit_selection("t-warm", ["hot-a"])  # base_level 8.0
    assert _blank(system, budget=RecallBudget(stm_floor=9.0)).budget_spent["stm_handles"] == 0
    assert _blank(system, budget=RecallBudget(stm_floor=7.0)).budget_spent["stm_handles"] == 1


def test_overlap_is_counted_once_as_both(system) -> None:
    system.add([
        _assertion("hot-match", "alice", "wrote", "fusion report", 1),
        _assertion("cold-match", "bob", "drafted", "fusion appendix", 2),
    ])
    system.commit_selection("t-warm", ["hot-match"])

    r = system.reconstruct(Stimulus(cue_text="fusion"), scopes=SCOPES, journal=False)
    by_id = {h.record_id: h for h in r.handles}
    assert list(by_id) .count("hot-match") == 1  # never duplicated
    assert by_id["hot-match"].admission == "both"     # trail-hot AND matched
    assert by_id["cold-match"].admission == "stimulus"
    assert r.budget_spent["stm_handles"] == 0         # overlap frees the STM cap


# ---------------------------------------------------------------------------
# Hot trail edges surface in the working_set view
# ---------------------------------------------------------------------------


def test_hot_trail_pairs_surface_even_unwalked(system) -> None:
    system.add([
        _assertion("t-a", "alice", "wrote", "fusion report", 1),
        _assertion("t-b", "alice", "presented", "fusion talk", 2),
        _assertion("t-c", "carol", "likes", "tea", 3),
    ])
    # Shared term "alice" -> co_selected trail (t-a, t-b) deposited.
    system.commit_selection("t-warm", ["t-a", "t-b"])

    # Blank cue: nothing is channel-matched, so nothing seeds spreading —
    # the trail pair is UNWALKED this turn yet still surfaces as STM edge.
    r = _blank(system, view="working_set")
    stm_edges = [e for e in r.edges if e.get("source") == "stm_trail"]
    assert stm_edges and stm_edges[0]["pair"] == ["t-a", "t-b"]
    assert stm_edges[0]["trail_activation"] > 0
    # Walked edges (cued run) carry source="walked" and are not duplicated.
    cued = system.reconstruct(Stimulus(cue_text="fusion"), scopes=SCOPES,
                              view="working_set", journal=False)
    walked = [e for e in cued.edges if e.get("source") == "walked"]
    walked_pairs = {tuple(sorted((e["source_id"], e["target_id"]))) for e in walked}
    for e in cued.edges:
        if e.get("source") == "stm_trail":
            assert tuple(sorted(e["pair"])) not in walked_pairs


def test_shelf_view_has_no_trail_edges(system) -> None:
    system.add([_assertion("t-a", "alice", "wrote", "report", 1),
                _assertion("t-b", "alice", "filed", "copy", 2)])
    system.commit_selection("t-warm", ["t-a", "t-b"])
    assert _blank(system, view="shelf").edges == ()  # edges stay working_set-only


# ---------------------------------------------------------------------------
# Ablations empty STM by construction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("arm", ["recency_embedding", "recency"])
def test_ablations_produce_empty_stm(stack, arm: str) -> None:
    store, journal = stack
    full = MemorySystem(store=store, journal=journal)
    full.add([_assertion("hot-a", "alice", "wrote", "report", 1)])
    full.commit_selection("t-warm", ["hot-a"])

    ablated = MemorySystem(store=store, journal=journal, ablation=arm)
    r = ablated.reconstruct(Stimulus(cue_text=""), scopes=SCOPES,
                            view="working_set", journal=False)
    assert r.budget_spent["stm_handles"] == 0          # zeroed activation -> no STM
    assert all(h.admission == "stimulus" for h in r.handles)
    assert all(e.get("source") != "stm_trail" for e in r.edges)


# ---------------------------------------------------------------------------
# Presence ≠ use (the critic's decay requirement)
# ---------------------------------------------------------------------------


def test_stm_only_commits_deposit_no_usage_by_default(system, stack) -> None:
    _, journal = stack
    system.add([
        _assertion("hot-a", "alice", "wrote", "fusion report", 1),
        _assertion("m-b", "bob", "drafted", "storage plan", 2),
    ])
    system.commit_selection("t-warm", ["hot-a"])
    baseline_selected = len(journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected"], limit=0))

    # A journaled read whose shelf holds hot-a via STM and m-b via stimulus.
    r = system.reconstruct(Stimulus(cue_text="storage"), scopes=SCOPES, trace_id="t-read")
    by_id = {h.record_id: h for h in r.handles}
    assert by_id["hot-a"].admission == "stm"
    assert by_id["m-b"].admission in ("stimulus", "both")

    snap = system.commit_selection("t-read", ["hot-a", "m-b"])
    events = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected"], limit=0)
    new_ids = [e.record_id for e in events][: len(events) - baseline_selected]
    assert new_ids == ["m-b"]  # STM-only presence deposited NOTHING
    # The snapshot stays display-truthful: all used ids + admission labels.
    assert snap.used_record_ids == ("hot-a", "m-b")
    assert snap.provenance["admissions"] == {"hot-a": "stm", "m-b": by_id["m-b"].admission}


def test_rendered_stm_member_decays_out_while_stimulus_member_strengthens(stack) -> None:
    """The critic's regression math: an STM-only member rendered AND
    committed every turn must still DECAY (rehearsal_weight=0) and exit STM,
    while stimulus-matched members committed alongside it strengthen.
    decay_window=2 compresses the activity axis so ten turns of realistic
    deposit volume cross the floor (activity-relative decay is the mechanism
    under test; the window length is tuning)."""
    store, journal = stack
    system = MemorySystem(store=store, journal=journal,
                          attention_config=AttentionConfig(decay_window=2.0))
    system.add([
        _assertion("stm-only", "alice", "wrote", "fusion report", 1),
        _assertion("worker", "bob", "drafted", "storage plan", 2),
        _assertion("helper", "carol", "reviews", "storage checklist", 3),
    ])
    system.commit_selection("t-warm", ["stm-only"])  # make it hot once
    floor = 1.0  # config default
    assert {h.record_id: h.admission for h in _blank(system).handles}["stm-only"] == "stm"

    stm_turns = 0
    for turn in range(10):
        r = system.reconstruct(Stimulus(cue_text="storage"), scopes=SCOPES,
                               trace_id=f"t-turn-{turn}")
        by_id = {h.record_id: h for h in r.handles}
        assert "stm-only" in by_id  # rendered every single turn...
        stm_turns += by_id["stm-only"].admission == "stm"
        # ...and committed every turn it is an STM member (the premise: an
        # STM-ONLY member — no stimulus match ever claims it as used).
        used = [rid for rid in ("worker", "helper") if rid in by_id]
        if by_id["stm-only"].admission == "stm":
            used.insert(0, "stm-only")
        system.commit_selection(f"t-turn-{turn}", used)

    assert stm_turns >= 3  # it lived in STM for several rendered+committed turns
    act = system.activation(["stm-only", "worker"], scope=SCOPE, owner_id=OWNER)
    assert act["stm-only"]["base_level"] < floor      # ...yet decayed anyway
    assert act["worker"]["base_level"] > floor        # genuine use strengthens
    # The only usage event stm-only ever earned is the warm-up: 10 rendered
    # STM commits deposited NOTHING (presence is not use).
    _, journal = system._store, system._journal
    deposits = [e for e in journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected"], limit=0)
                if e.record_id == "stm-only"]
    assert [e.trace_id for e in deposits] == ["t-warm"]
    final = _blank(system)
    by_id = {h.record_id: h for h in final.handles}
    assert by_id["stm-only"].admission == "stimulus"  # out of STM (recency presence only)
    assert by_id["worker"].admission == "stm"         # genuine use keeps it in


def test_rehearsal_dial_deposits_weight_scaled_events(stack) -> None:
    store, journal = stack
    system = MemorySystem(store=store, journal=journal,
                          attention_config=AttentionConfig(stm_rehearsal_weight=2.0))
    system.add([_assertion("hot-a", "alice", "wrote", "fusion report", 1)])
    system.commit_selection("t-warm", ["hot-a"])

    r = system.reconstruct(Stimulus(cue_text=""), scopes=SCOPES, trace_id="t-read")
    assert {h.record_id: h.admission for h in r.handles}["hot-a"] == "stm"
    system.commit_selection("t-read", ["hot-a"])

    events = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected"], limit=0)
    rehearsal = [e for e in events if e.trace_id == "t-read"]
    assert len(rehearsal) == 1 and rehearsal[0].weight == 2.0  # scaled, not full 8.0
    assert journal.events(scope=SCOPE, owner_id=OWNER, kinds=["co_selected"], limit=0) == [] or all(
        e.trace_id != "t-read"
        for e in journal.events(scope=SCOPE, owner_id=OWNER, kinds=["co_selected"], limit=0)
    )  # rehearsal never deposits pair trails


# ---------------------------------------------------------------------------
# Realistic-fix regressions that belong with the union wave
# ---------------------------------------------------------------------------


def test_batch_internal_edge_refs(system, stack) -> None:
    store, _ = stack
    [gid_q, gid_a] = system.remember_many(
        [
            MemoryRecordInput(kind="question", title="Q", digest="Which pooler should we use?"),
            MemoryRecordInput(kind="answer", title="A", digest="Use pgbouncer.",
                              edges=(("answers", "local:0"),)),
        ],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-local",
    )
    from abstractmemory.store import TripleQuery
    [edge] = [a for a in store.query(TripleQuery(subject=gid_a, limit=0))
              if isinstance(a.attributes, dict) and a.attributes.get("record_edge")]
    assert edge.object == gid_q  # local:0 resolved to the sibling's graph id

    for bad_edges, match in (
        ((("answers", "local:9"),), "out of range"),
        ((("answers", "local:0"),), "itself"),
        ((("answers", "local:x"),), "invalid"),
    ):
        with pytest.raises(ValueError, match=match):
            system.remember_many(
                [MemoryRecordInput(kind="claim", title="C", digest="d", edges=bad_edges)],
                scope=SCOPE, owner_id=OWNER, idempotency_key="k-bad",
            )


def test_canonical_text_v2_record_digests_are_clean(system) -> None:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="lesson", title="Batch inserts", keywords=("ingest", "batching"),
                           digest="Batch sensor readings into one transaction.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-v2",
    )
    r = system.reconstruct(Stimulus(cue_text="batch sensor readings"), scopes=SCOPES, journal=False)
    h = next(x for x in r.handles if x.provenance.get("record_id") == gid)
    # handle.digest is the CLEAN literal (title travels separately).
    assert h.digest == "Batch sensor readings into one transaction."
    assert "dcterms:abstract" not in h.digest and "ex:" not in h.digest
    # canonical_text (embedding/keyword surface): title + digest + keywords.
    assert canonical_text(h and _fetch(system, gid)) == (
        "Batch inserts\nBatch sensor readings into one transaction.\nkeywords: ingest, batching"
    )
    assert system.payload(gid)["content"] == h.digest  # payload digest tier matches


def _fetch(system, gid):
    from abstractmemory.store import TripleQuery
    [a] = [x for x in system.query(TripleQuery(subject=gid, limit=0))
           if isinstance(x.attributes, dict) and x.attributes.get("record_kind")]
    return a


def test_handle_digest_helper_shapes() -> None:
    record = TripleAssertion(subject="ex:claim-1", predicate="dcterms:abstract",
                             object="The digest literal.", scope=SCOPE, owner_id=OWNER,
                             attributes={"literal": True, "record_kind": "claim", "title": "T"},
                             assertion_id="rec-1")
    plain = TripleAssertion(subject="alice", predicate="wrote", object="report",
                            scope=SCOPE, owner_id=OWNER, assertion_id="plain-1")
    assert handle_digest(record) == "The digest literal."
    assert handle_digest(plain) == canonical_text(plain)  # v1 shape for triples


class _CountingBaselineEmbedder:
    """Qwen-class behavior: unrelated pairs sit at a HIGH cosine baseline
    (~0.4) far above the absolute 0.05 floor; only the genuine hit rises
    clearly above it. Also counts embed calls (edge-skip check)."""

    def __init__(self) -> None:
        self.calls: List[List[str]] = []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        out = []
        for t in texts:
            if "fusion" in t.lower():
                out.append([1.0, 0.4, 0.0])       # genuine hit: cosine ~0.93
            else:
                out.append([0.4, 1.0, 0.0])       # unrelated baseline: ~0.4 vs query
        return out


def _quiet_system(store, emb) -> MemorySystem:
    import warnings as warnings_module
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore", RuntimeWarning)  # volatile-journal note
        return MemorySystem(store=store, journal=InMemoryJournal(), embedder=emb)


def test_relative_vector_floor_clips_the_unrelated_baseline() -> None:
    emb = _CountingBaselineEmbedder()
    store = InMemoryTripleStore(embedder=emb)
    system = _quiet_system(store, emb)
    system.add([_assertion("hit", "alice", "studies", "fusion energy", 1, literal=True)])
    system.add([
        _assertion(f"noise-{i}", "bob", "notes", f"unrelated topic {i}", 2 + i, literal=True)
        for i in range(6)  # >= 5 fetched cosines engage the median+margin floor
    ])
    r = system.reconstruct(Stimulus(cue_text="fusion research"), scopes=SCOPES, journal=False)
    by_id = {h.record_id: h for h in r.handles}
    assert "vector" in by_id["hit"].relevance          # the genuine hit survives
    assert all("vector" not in by_id[f"noise-{i}"].relevance
               for i in range(6) if f"noise-{i}" in by_id)  # baseline clipped


def test_edge_assertions_are_never_embedded() -> None:
    emb = _CountingBaselineEmbedder()
    store = InMemoryTripleStore(embedder=emb)
    system = _quiet_system(store, emb)
    system.remember_many(
        [
            MemoryRecordInput(kind="question", title="Q", digest="fusion target question"),
            MemoryRecordInput(kind="answer", title="A", digest="fusion answer",
                              edges=(("answers", "local:0"),)),
        ],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-edges",
    )
    embedded = [t for batch in emb.calls for t in batch]
    assert len(embedded) == 2                          # two digests, ZERO edge texts
    assert all("answers" != t for t in embedded)
    from abstractmemory.store import TripleQuery
    edge_rows = [row for row in store._rows
                 if isinstance(row["assertion"].attributes, dict)
                 and row["assertion"].attributes.get("record_edge")]
    assert edge_rows and all(row.get("vector") is None for row in edge_rows)
