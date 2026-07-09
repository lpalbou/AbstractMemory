"""Sleep/consolidation guards (backlog 0023 v1 — the fork port).

THESE TESTS ARE THE DELIVERABLE: each one ports a fork guard or pins a
named divergence. Sleep is deterministic; sleep proposes, waking evidence
disposes; maintenance deposits NOTHING; dreams never loop into their own
inputs, never enter identity, and never outrank lived memory.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from abstractmemory import (
    RecallBudget,
    Stimulus,
    dream_pass,
    structural_report,
    unresolved_dreams,
)
from abstractmemory.consolidation import COMPONENT_RELATIONS, CONTEXT_RELATIONS
from abstractmemory.records import KIND_RANKS, MemoryRecordInput

SCOPE = "life"
OWNER = "entity:test"
SCOPES = [(SCOPE, OWNER)]


def _remember(system, key: str, kind: str, title: str, digest: str, **kw: Any) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _two_island_world(system) -> Dict[str, str]:
    """Authored component (db-episode —edge— db-lesson) + garden records
    warmed by a co-use TRAIL (habit, NOT component-defining since the
    red-team guard: the garden pair is excluded from proposals as
    trail-associated, not merged) + one isolated note. Shared facets
    planted for bridge tests."""
    ids = {}
    ids["db-episode"] = _remember(system, "c-1", "episode", "Pool outage night",
                                  "The connection pool saturated at noon.",
                                  keywords=("pool", "saturation", "noon"))
    ids["db-lesson"] = _remember(system, "c-2", "lesson", "Batch the writers",
                                 "Batching the noon cron fixed the pool.",
                                 keywords=("pool", "batching"),
                                 edges=(("supports", ids["db-episode"]),))
    ids["garden-episode"] = _remember(system, "c-3", "episode", "Garden sensor day",
                                      "Planted the garden moisture sensors at noon.",
                                      keywords=("garden", "sensors", "noon"))
    ids["garden-plan"] = _remember(system, "c-4", "plan", "Water schedule",
                                   "Water the garden by sensor readings.",
                                   keywords=("garden", "watering"))
    ids["loose-note"] = _remember(system, "c-5", "memory", "Loose thought",
                                  "A stray idea about paint colors.",
                                  keywords=("paint",))
    # Warm a trail between the two garden records (co_selected adjacency).
    system.reconstruct(Stimulus(cue_text="garden"), scopes=SCOPES, trace_id="t-warm-garden")
    system.commit_selection("t-warm-garden", [ids["garden-episode"], ids["garden-plan"]])
    return ids


def _access_state(system, journal, ids: Dict[str, str]) -> Tuple[Dict, int]:
    counts = system.access_counts(record_ids=list(ids.values()))
    events = len(journal.events(scope=SCOPE, owner_id=OWNER,
                                kinds=["selected", "co_selected", "pinned", "silenced"],
                                limit=0))
    return counts, events


# ---------------------------------------------------------------------------
# GUARD: sleep deposits NOTHING (the D2 of sleep)
# ---------------------------------------------------------------------------


def test_guard_sleep_deposits_nothing(system, stack) -> None:
    _, journal = stack
    ids = _two_island_world(system)
    before_counts, before_events = _access_state(system, journal, ids)

    report = structural_report(system._store, journal, scopes=SCOPES)
    assert report["counts"]["records"] == 5
    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert result["dream_record_id"]  # a dream DID form (writes one record...)

    after_counts, after_events = _access_state(system, journal, ids)
    assert after_counts == before_counts        # ...but no access count moved
    assert after_events == before_events        # and no attention event landed


# ---------------------------------------------------------------------------
# GUARD: the loop-breaker (dreams never feed the next pass)
# ---------------------------------------------------------------------------


def test_guard_dream_excluded_from_next_pass_inputs(system, stack) -> None:
    _, journal = stack
    _two_island_world(system)
    first = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    dream_id = first["dream_record_id"]
    assert dream_id

    report = structural_report(system._store, journal, scopes=SCOPES)
    assert dream_id not in report["records"]
    assert all(dream_id not in component for component in report["components"])


# ---------------------------------------------------------------------------
# GUARD: one dream per pass; same graph state re-runs form nothing
# ---------------------------------------------------------------------------


def test_guard_one_dream_per_pass_and_fingerprint_idempotency(system, stack) -> None:
    store, _ = stack
    _two_island_world(system)
    first = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert first["created"] is True

    replay = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert replay["dream_record_id"] == first["dream_record_id"]
    assert replay["created"] is False           # fingerprint dedup via remember_many

    from abstractmemory.store import TripleQuery
    dreams = [a for a in store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))
              if isinstance(a.attributes, dict) and a.attributes.get("record_kind") == "dream"]
    assert len(dreams) == 1                     # exactly one dream record exists


# ---------------------------------------------------------------------------
# GUARD: a quiet night is a valid night
# ---------------------------------------------------------------------------


def test_guard_quiet_night_below_salience_forms_nothing(system) -> None:
    _remember(system, "q-1", "episode", "Only memory", "One lonely episode.",
              keywords=("lonely",))
    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert result["dream_record_id"] is None and result["created"] is False
    assert "quiet night" in result["skipped_reason"]

    # report_only never forms even when salience passes.
    _two_island_world(system)
    dry = dream_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    assert dry["dream_record_id"] is None and dry["skipped_reason"] == "report_only requested"


# ---------------------------------------------------------------------------
# GUARD: bridge correctness (proposal vs question vs excluded vs vector)
# ---------------------------------------------------------------------------


def test_guard_bridge_rules(system) -> None:
    ids = _two_island_world(system)
    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)

    pairs = {tuple(sorted(p["pair"])): p for p in result["proposals"]}
    # Cross-component, 2 shared lexical facets ("garden" never; db-episode +
    # garden-episode share {noon} only -> question; db-episode/garden share
    # nothing... construct: db-episode {pool,saturation,noon} vs
    # garden-episode {garden,sensors,noon} share {noon} -> QUESTION.
    q_pairs = {tuple(sorted(q["pair"])) for q in result["questions"]}
    assert tuple(sorted((ids["db-episode"], ids["garden-episode"]))) in q_pairs

    # Already-adjacent (same component) pairs never appear anywhere.
    same_component = tuple(sorted((ids["db-episode"], ids["db-lesson"])))
    assert same_component not in pairs and same_component not in q_pairs

    # Two shared facets across components -> PROPOSAL: add a record in the
    # db island sharing {garden, noon} with garden-episode... instead form a
    # fresh cross-island record sharing 2 facets with db-episode.
    bridge_id = _remember(system, "c-6", "episode", "Noon pool reading",
                          "Garden pond pool reading logged at noon.",
                          keywords=("pool", "noon", "pond"))
    fresh = dream_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    fresh_pairs = {tuple(sorted(p["pair"])) for p in fresh["proposals"]}
    assert tuple(sorted((ids["db-episode"], bridge_id))) in fresh_pairs  # {pool, noon}


def test_guard_vector_bridge_fires_without_lexical_facets(stack) -> None:
    """The named upgrade over the fork: unique digests with NO facet overlap
    still bridge when their stored embeddings agree (stub embedder)."""
    import warnings as warnings_module
    from abstractmemory import MemorySystem

    class TwinEmbedder:
        def embed_texts(self, texts):
            return [[1.0, 0.0] for _ in texts]  # everything maximally similar

    store, journal = stack
    if not hasattr(store, "stored_vector"):
        pytest.skip("store lacks stored_vector")
    # Rebuild the store WITH an embedder (conftest stacks build without one).
    store._embedder = TwinEmbedder()  # both shipped stores hold it in this attr
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore", RuntimeWarning)
        system = MemorySystem(store=store, journal=journal, embedder=TwinEmbedder())

    a = MemoryRecordInput(kind="episode", title="Ship day", digest="The freighter left port.")
    b = MemoryRecordInput(kind="episode", title="Kiln firing", digest="Ceramics glazed overnight.")
    [gid_a] = system.remember_many([a], scope=SCOPE, owner_id=OWNER, idempotency_key="v-1")
    [gid_b] = system.remember_many([b], scope=SCOPE, owner_id=OWNER, idempotency_key="v-2")

    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    proposal_pairs = {tuple(sorted(p["pair"])) for p in result["proposals"]}
    assert tuple(sorted((gid_a, gid_b))) in proposal_pairs
    [entry] = [p for p in result["proposals"] if tuple(sorted(p["pair"])) == tuple(sorted((gid_a, gid_b)))]
    assert entry["vector_score"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# GUARD: dream record shape + chaining
# ---------------------------------------------------------------------------


def test_guard_dream_record_shape_and_chaining(system, stack) -> None:
    store, journal = stack
    ids = _two_island_world(system)
    first = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    dream_id = first["dream_record_id"]

    from abstractmemory.store import TripleQuery
    rows = store.query(TripleQuery(subject=dream_id, limit=0))
    digest = next(a for a in rows if a.attributes.get("record_kind") == "dream")
    edges = [a for a in rows if a.attributes.get("record_edge")]

    assert KIND_RANKS["dream"] == KIND_RANKS["summary"] == 5  # derived-artifact rank
    assert digest.attributes["interpretation_required"] is True
    assert digest.attributes["salience"] == first["salience"]
    assert digest.attributes["continuation_state"] == "unresolved"  # questions remained
    assert digest.attributes["parent_dream_ids"] == []              # first night
    assert digest.title if hasattr(digest, "title") else True
    assert "islands" in digest.object                                # the fork's register
    assert edges and all(e.predicate == "mentions" for e in edges)
    edge_targets = {e.object for e in edges}
    assert edge_targets <= set(ids.values())                         # weak links to sources
    # Formed like every record: indexed+inactive binding, prompt-inactive.
    [binding] = [b for b in journal.bindings(scope=SCOPE, owner_id=OWNER, fold=True)
                 if b.record_id == dream_id]
    assert (binding.search_state, binding.prompt_state) == ("indexed", "inactive")

    # CHAINING: change the graph (new record resolves nothing, adds facets),
    # second pass links the first dream as parent (it stayed unresolved).
    _remember(system, "c-7", "episode", "Second night fuel",
              "Another noon pool anomaly in the garden pond.",
              keywords=("pool", "noon", "garden"))
    second = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert second["created"] is True and second["dream_record_id"] != dream_id
    second_digest = next(a for a in store.query(TripleQuery(subject=second["dream_record_id"], limit=0))
                         if a.attributes.get("record_kind") == "dream")
    assert dream_id in second_digest.attributes["parent_dream_ids"]

    # unresolved_dreams reads the chain (both stacks; folded when journal given).
    standing = unresolved_dreams(store, scope=SCOPE, owner_id=OWNER, journal=journal)
    assert [a.subject for a in standing][:1] == [dream_id]


# ---------------------------------------------------------------------------
# GUARD: dreams never enter identity; recall stays neutral
# ---------------------------------------------------------------------------


def test_guard_dream_never_in_identity_seats(system) -> None:
    _two_island_world(system)
    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    dream_id = result["dream_record_id"]
    # Even a (mis)bound prompt-active dream is kind-filtered out of the core.
    system.bind(dream_id, scope=SCOPE, owner_id=OWNER,
                search_state="indexed", prompt_state="active", source="operator")
    core = system.self_records(scope=SCOPE, owner_id=OWNER)
    assert all(a.attributes.get("record_kind") != "dream" for a in core)
    r = system.reconstruct(Stimulus(cue_text=""), scopes=SCOPES, journal=False,
                           budget=RecallBudget(self_fraction=0.5))
    assert all(h.kind != "dream" for h in r.handles if h.admission == "self")


def test_guard_recall_neutrality_matched_episode_outranks_unmatched_dream(system) -> None:
    _two_island_world(system)
    dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    r = system.reconstruct(Stimulus(cue_text="connection pool saturated"),
                           scopes=SCOPES, journal=False)
    kinds = [h.kind for h in r.handles]
    assert "episode" in kinds
    if "dream" in kinds:  # the dream may surface via NORMAL channels only
        assert kinds.index("episode") < kinds.index("dream")


# ---------------------------------------------------------------------------
# GUARD: component semantics (red-team 0007 URGENT — densification must not
# structurally kill the dream pass). Components = AUTHORED relations only;
# co_selected trails are habit, not structure — they exclude proposals for
# already-associated pairs but NEVER merge components.
# ---------------------------------------------------------------------------


def _authored_two_groups(system) -> Dict[str, str]:
    """Two authored components with planted cross-group facets:
    group A (a1 <-supports- a2), group B (b1 <-supports- b2)."""
    ids = {}
    ids["a1"] = _remember(system, "g-a1", "episode", "Reactor drill",
                          "Ran the reactor drill at dawn.",
                          keywords=("reactor", "drill", "dawn"))
    ids["a2"] = _remember(system, "g-a2", "lesson", "Drill pacing",
                          "Pace the reactor drill slower.",
                          keywords=("reactor", "pacing"),
                          edges=(("supports", ids["a1"]),))
    ids["b1"] = _remember(system, "g-b1", "episode", "Harbor watch",
                          "Watched the harbor tide at dawn.",
                          keywords=("harbor", "tide", "dawn", "drill"))
    ids["b2"] = _remember(system, "g-b2", "plan", "Tide charting",
                          "Chart the harbor tide weekly.",
                          keywords=("harbor", "charting"),
                          edges=(("supports", ids["b1"]),))
    return ids


def test_guard_trails_never_define_components(system, stack) -> None:
    """Heavy co-use ACROSS two semantically disjoint groups must not merge
    them: components stay 2, cross-group bridges stay proposable, salience
    stays > 0. (Pre-fix: the all-pairs trail bridged the groups into ONE
    component and no bridge could ever be proposed again.)"""
    _, journal = stack
    ids = _authored_two_groups(system)
    # Heavy co-use across the groups: a2+b2 serve three moments together.
    for t in range(3):
        system.commit_selection(f"t-cross-{t}", [ids["a2"], ids["b2"]])

    report = structural_report(system._store, journal, scopes=SCOPES)
    assert report["counts"]["components"] == 2  # trails did NOT merge
    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    # The trail-free cross pair (a1, b1) shares {dawn, drill} -> proposable.
    assert tuple(sorted((ids["a1"], ids["b1"]))) in {
        tuple(sorted(p["pair"])) for p in result["proposals"]}
    assert result["salience"] > 0


def test_guard_trail_warmed_pairs_not_proposed(system, stack) -> None:
    """A cross-component pair already associated BY USE (warm co_selected
    trail) is nothing to dream about: excluded from proposals AND questions,
    counted honestly as trail_associated — not silently dropped."""
    _, journal = stack
    ids = _authored_two_groups(system)
    system.commit_selection("t-warm-a1b1", [ids["a1"], ids["b1"]])  # warm the bridge pair

    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    warmed = tuple(sorted((ids["a1"], ids["b1"])))
    assert warmed not in {tuple(sorted(p["pair"])) for p in result["proposals"]}
    assert warmed not in {tuple(sorted(q["pair"])) for q in result["questions"]}
    assert result["trail_associated"] >= 1  # counted, not silent
    # The trail shows in the report as habit data, never as adjacency.
    assert list(warmed) in result["report"]["trail_pairs"]
    assert ids["b1"] not in result["report"]["adjacency"][ids["a1"]]


def test_guard_continues_chains_are_islands(system, stack) -> None:
    """DIVERGENCE (deliberate): `continues` IS component-defining — a
    chained session is one story/island. Two chains without cross edges =
    2 components; a cross-chain bridge stays proposable."""
    _, journal = stack
    ids = {}
    ids["e1"] = _remember(system, "ch-e1", "episode", "Morning start",
                          "Started the kiln logs at dawn.", keywords=("kiln", "logs"))
    ids["e2"] = _remember(system, "ch-e2", "episode", "Morning next",
                          "Continued the kiln logs.", keywords=("kiln",),
                          edges=(("continues", ids["e1"]),))
    ids["e3"] = _remember(system, "ch-e3", "episode", "Morning end",
                          "Closed the kiln logs at dusk.", keywords=("kiln", "dusk"),
                          edges=(("continues", ids["e2"]),))
    ids["f1"] = _remember(system, "ch-f1", "episode", "Evening start",
                          "Opened the dusk telescope at the dome.", keywords=("telescope", "dome"))
    ids["f2"] = _remember(system, "ch-f2", "episode", "Evening next",
                          "Tracked the telescope drift at dusk.",
                          keywords=("telescope", "dusk", "kiln"),
                          edges=(("continues", ids["f1"]),))

    report = structural_report(system._store, journal, scopes=SCOPES)
    assert report["counts"]["components"] == 2
    chain_of = report["component_of"]
    assert chain_of[ids["e1"]] == chain_of[ids["e2"]] == chain_of[ids["e3"]]
    assert chain_of[ids["f1"]] == chain_of[ids["f2"]]

    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    # e3 and f2 share {dusk, kiln} across the chains -> proposable bridge.
    assert tuple(sorted((ids["e3"], ids["f2"]))) in {
        tuple(sorted(p["pair"])) for p in result["proposals"]}


def test_guard_written_amid_never_defines_components(system, stack) -> None:
    """URGENT correction (a2a 0007, runtime's confirmation ask): the
    predicate policy is real CODE, not docstring prose. A diary projection
    carrying written_amid edges into records of two different authored
    components must NOT merge them (38+ diary nodes x ~6 anchors each
    would make diary entries super-connectors and fuse sessions into one
    island — the dream-death merger through the authored-edge door). The
    diary-linked pairs count as already-associated (context_associated,
    excluded from proposals AND questions); the dream still forms on the
    remaining semantic bridges."""
    _, journal = stack
    # Pin the policy itself: a future edit moving written_amid into the
    # component set fails HERE, loudly, before it merges anyone's diary.
    assert "written_amid" in CONTEXT_RELATIONS
    assert "written_amid" not in COMPONENT_RELATIONS
    assert not (COMPONENT_RELATIONS & CONTEXT_RELATIONS)

    ids = _authored_two_groups(system)
    # The projection shape the runtime ships (identity_support.py): kind
    # diary, act-frame digest, written_amid anchors = what the entity was
    # attending to at write time — here one record in EACH component.
    # Keywords planted so both diary pairs WOULD be proposals if the
    # exclusion ever regressed (>=2 shared facets with a1 and with b1).
    diary_id = _remember(
        system, "d-amid", "diary", "Diary entry (reflection) — 2026-07-07",
        "Wrote about the reactor drill and the harbor tide.",
        keywords=("reactor", "drill", "harbor", "tide"),
        attributes={"entry_id": "diary_0001", "diary_type": "reflection"},
        provenance={"source": "diary-projection", "entry_id": "diary_0001"},
        edges=(("written_amid", ids["a1"]), ("written_amid", ids["b1"])))

    report = structural_report(system._store, journal, scopes=SCOPES)
    # Still two authored components + the diary as its own island: the
    # written_amid edges routed to context, never adjacency.
    assert report["counts"]["components"] == 3
    assert report["component_of"][ids["a1"]] != report["component_of"][ids["b1"]]
    assert report["component_of"][diary_id] not in (
        report["component_of"][ids["a1"]], report["component_of"][ids["b1"]])
    assert diary_id in report["isolated"]  # no SEMANTIC relations
    assert ids["a1"] not in report["adjacency"][diary_id]
    assert sorted(map(tuple, report["context_pairs"])) == sorted([
        tuple(sorted((diary_id, ids["a1"]))), tuple(sorted((diary_id, ids["b1"])))])
    assert report["counts"]["context_edges"] == 2
    assert report["unknown_relations"] == []  # written_amid is DECLARED context

    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    proposal_pairs = {tuple(sorted(p["pair"])) for p in result["proposals"]}
    question_pairs = {tuple(sorted(q["pair"])) for q in result["questions"]}
    for anchored in (ids["a1"], ids["b1"]):
        pair = tuple(sorted((diary_id, anchored)))
        assert pair not in proposal_pairs and pair not in question_pairs
    assert result["context_associated"] == 2  # counted, not silent
    # The dream still has material: the a1/b1 semantic bridge ({dawn,
    # drill}) survives untouched, and forming works end to end.
    assert tuple(sorted((ids["a1"], ids["b1"]))) in proposal_pairs
    formed = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert formed["created"] is True and formed["dream_record_id"]


def test_guard_unknown_relation_defaults_to_context(system, stack) -> None:
    """A NOVEL predicate (no policy entry) must not silently merge
    components: unknowns route to context (conservative default) and are
    NAMED in the report — works-or-loud. Promoting a predicate to
    COMPONENT_RELATIONS is a deliberate edit, never an accident."""
    _, journal = stack
    r1 = _remember(system, "u-1", "episode", "Kiln reading",
                   "Logged the kiln sensor at noon.", keywords=("kiln", "sensor", "noon"))
    r2 = _remember(system, "u-2", "episode", "Dome reading",
                   "Logged the dome sensor at noon.", keywords=("dome", "sensor", "noon"),
                   edges=(("co_occurred_with", r1),))  # novel predicate

    report = structural_report(system._store, journal, scopes=SCOPES)
    assert report["counts"]["components"] == 2       # NOT merged (pre-fix: 1)
    assert report["component_of"][r1] != report["component_of"][r2]
    assert report["unknown_relations"] == ["co_occurred_with"]  # named, never silent
    assert report["counts"]["context_edges"] == 1
    assert [tuple(p) for p in report["context_pairs"]] == [tuple(sorted((r1, r2)))]

    # Context semantics apply: the pair is already-associated — excluded
    # from proposals/questions despite sharing {sensor, noon} — and counted.
    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    pair = tuple(sorted((r1, r2)))
    assert pair not in {tuple(sorted(p["pair"])) for p in result["proposals"]}
    assert pair not in {tuple(sorted(q["pair"])) for q in result["questions"]}
    assert result["context_associated"] == 1


def test_guard_dream_survives_dense_home(system, stack) -> None:
    """THE red-team fixture (0007 URGENT): a busy home — a dozen records,
    two continues-chained clusters, an all-pairs-trail hot clique spanning
    BOTH clusters — still yields a non-zero-salience pass and forms a
    dream. Pre-fix, the trail clique merged everything into one component:
    zero cross pairs, salience 0, dreams structurally dead."""
    _, journal = stack
    p, q = {}, {}
    for i in range(6):
        p[i] = _remember(
            system, f"dh-p{i}", "episode", f"Forge shift {i}",
            f"Forge shift number {i} ran hot.",
            keywords=("forge", f"shift{i}") + (("noon", "sensor") if i == 4 else ()),
            edges=(("continues", p[i - 1]),) if i else ())
    for i in range(6):
        q[i] = _remember(
            system, f"dh-q{i}", "episode", f"Orchard round {i}",
            f"Orchard round number {i} logged.",
            keywords=("orchard", f"round{i}") + (("noon", "sensor") if i == 4 else ()),
            edges=(("continues", q[i - 1]),) if i else ())
    # Hot clique: p0..p3 + q0..q3 serve three moments together (all-pairs
    # trails across the clusters: C(8,2)=28 pairs per commit).
    clique = [p[i] for i in range(4)] + [q[i] for i in range(4)]
    for t in range(3):
        system.commit_selection(f"t-dense-{t}", clique)

    report = structural_report(system._store, journal, scopes=SCOPES)
    assert report["counts"]["records"] == 12
    assert report["counts"]["components"] == 2  # chains, not trails, structure the home

    result = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert result["salience"] > 0
    # The trail-free cross pair (p4, q4) shares {noon, sensor} -> the bridge.
    assert tuple(sorted((p[4], q[4]))) in {
        tuple(sorted(pr["pair"])) for pr in result["proposals"]}
    assert result["created"] is True and result["dream_record_id"]