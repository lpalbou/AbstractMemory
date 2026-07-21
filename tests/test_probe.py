"""probe() + probe_expand: the deliberate reach (0022, fork 090/091 shape).

Contracts pinned here:
- reason is MANDATORY and lands on the trace as escalation_reason;
- probe is EXEMPT from the shelf race: no identity seats, no STM, no
  activation boost — a never-used record beats a heavily-used one on
  relevance alone (the cue-dilution counter);
- efforts quick/standard/deep are presets over ProbeBudget (unknown names
  refuse loudly; custom budgets pass through);
- probing deposits NOTHING (audit events only — reading is not using);
- expansion walks edges BOTH directions, honors closure folds, and its
  trace records the parent probe.
"""

from __future__ import annotations

import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    PROBE_EFFORTS,
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    ProbeBudget,
    Stimulus,
)

OWNER = "entity:probe-test"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]


@pytest.fixture()
def system():
    store, journal = InMemoryTripleStore(), InMemoryJournal()
    return MemorySystem(store=store, journal=journal)


def _seed(system, n_noise: int = 0):
    records = [
        MemoryRecordInput(kind="episode", title="Voyager signal fades",
                          digest="The Voyager probe signal faded near the heliopause boundary.",
                          keywords=("voyager", "heliopause")),
        MemoryRecordInput(kind="episode", title="Garden pond at noon",
                          digest="Reflections in the garden pond at noon, quiet water.",
                          keywords=("garden", "pond")),
        MemoryRecordInput(kind="lesson", title="Persistence lesson",
                          digest="What persists when no one is reading: the voyager record endures.",
                          keywords=("persistence",)),
    ]
    for i in range(n_noise):
        records.append(MemoryRecordInput(
            kind="episode", title=f"Noise {i}",
            digest=f"Unrelated filler episode number {i} about weather patterns.",
            keywords=("weather",)))
    return system.remember_many(records, scope=SCOPE, owner_id=OWNER,
                                idempotency_key="probe-seed")


def test_probe_requires_a_reason(system) -> None:
    _seed(system)
    with pytest.raises(ValueError, match="reason"):
        system.probe(Stimulus(cue_text="voyager"), scopes=SCOPES, reason="")


def test_probe_reason_lands_as_escalation_on_the_trace(system) -> None:
    _seed(system)
    r = system.probe(Stimulus(cue_text="voyager"), scopes=SCOPES,
                     reason="looking for the voyager thread")
    [trace] = system.journal.traces(trace_id=r.trace_id)
    assert trace.trace_kind == "probe"
    assert trace.escalation_reason == "looking for the voyager thread"
    assert trace.selected == tuple(h.record_id for h in r.hits)


def test_probe_finds_never_used_records_on_relevance_alone(system) -> None:
    """The cue-dilution counter: a record with ZERO usage history must be
    findable by a deliberate reach — no activation, no seats, no race."""
    ids = _seed(system, n_noise=6)
    # Heavily use the noise records (the shelf race's rich-get-richer mass).
    rec = system.reconstruct(Stimulus(cue_text="weather patterns filler"),
                             scopes=SCOPES)
    if rec.handles:
        system.commit_selection(rec.trace_id, [h.record_id for h in rec.handles])
    r = system.probe(Stimulus(cue_text="voyager heliopause"), scopes=SCOPES,
                     reason="deliberate reach for the faded signal")
    assert r.hits, "probe found nothing"
    assert r.hits[0].graph_id == ids[0]  # the never-used record wins on relevance
    assert "keyword" in r.channels


def test_probe_efforts_are_presets_and_unknown_names_refuse(system) -> None:
    _seed(system)
    assert set(PROBE_EFFORTS) == {"quick", "standard", "deep"}
    quick = system.probe(Stimulus(cue_text="voyager"), scopes=SCOPES,
                         reason="quick check", effort="quick")
    assert quick.budget_spent["effort"] == "quick"
    with pytest.raises(ValueError, match="unknown probe effort"):
        system.probe(Stimulus(cue_text="voyager"), scopes=SCOPES,
                     reason="bad effort", effort="frantic")
    custom = system.probe(Stimulus(cue_text="voyager"), scopes=SCOPES,
                          reason="custom budget",
                          effort=ProbeBudget(max_hits=1, token_budget=200))
    assert len(custom.hits) <= 1
    assert custom.budget_spent["effort"] == "custom"


def test_probe_deposits_nothing(system) -> None:
    """Reading is not using: a probe (even journaled) must not move usage
    counters — only commit_selection strengthens."""
    ids = _seed(system)
    before = system.access_counts(record_ids=ids)
    system.probe(Stimulus(cue_text="voyager heliopause"), scopes=SCOPES,
                 reason="deposit check")
    after = system.access_counts(record_ids=ids)
    assert before == after, "a probe deposited usage"
    # And the audit trail exists (listed events with probe provenance).
    events = [e for e in system.journal.events(scope=SCOPE, owner_id=OWNER)
              if e.kind == "listed" and e.provenance.get("probe")]
    assert events, "probe wrote no audit events"


def test_probe_concept_channel_reaches_records_the_query_never_named(system) -> None:
    """Concept co-occurrence: the lesson shares the 'voyager' concept with
    the seed episode; a probe for the episode surfaces the lesson too even
    though the cue never said 'persistence'."""
    _seed(system)
    r = system.probe(Stimulus(cue_text="voyager heliopause"), scopes=SCOPES,
                     reason="associative reach", effort="standard")
    titles = [h.title for h in r.hits]
    assert "Persistence lesson" in titles
    lesson = next(h for h in r.hits if h.title == "Persistence lesson")
    assert "concept" in lesson.relevance or "keyword" in lesson.relevance


def test_concept_only_admissions_never_outrank_direct_hits(system) -> None:
    """The two-tier fusion rule (2026-07-17, live-reproduced on Ephemeral's
    home): concept scores are rarity-weighted and clamped at 1.0, so under
    a flat fused sum a concept-only ASSOCIATION outranked the direct hits
    that seeded it (top-8 all concept-only on a core-interest cue).
    Association admits; direct evidence ranks first — every hit the cue
    itself matched (vector/keyword/exact/participants) orders before every
    concept-only admission; concept corroboration ON a direct hit keeps
    its fused weight inside the direct tier."""
    system.remember_many([
        # Direct hits: share cue tokens, but weakly (low keyword fractions).
        MemoryRecordInput(
            kind="episode", title="Weak direct one",
            digest="The heliopause crossing came up in passing yesterday.",
            keywords=("heliopause",)),
        MemoryRecordInput(
            kind="episode", title="Weak direct two",
            digest="Another passing heliopause mention beside other things.",
            keywords=("heliopause",)),
        # Association bait: records sharing a rare concept with the direct
        # hits ('crossing'/'mention' overlap) but ZERO cue tokens — they
        # can only enter through the concept channel, clamped at 1.0.
        MemoryRecordInput(
            kind="episode", title="Association one",
            digest="A crossing mention in an unrelated thread of days."),
        MemoryRecordInput(
            kind="episode", title="Association two",
            digest="That crossing mention returned in another shape entirely."),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="fusion-tier-seed")

    r = system.probe(
        Stimulus(cue_text="heliopause probe telemetry archive"), scopes=SCOPES,
        reason="two-tier ordering pin", effort="standard", journal=False)
    assert r.hits, "fixture must produce hits"
    tiers = [0 if set(h.relevance) - {"concept"} else 1 for h in r.hits]
    assert tiers == sorted(tiers), (
        "a concept-only admission outranked a direct hit: "
        + "; ".join(f"{h.title}={sorted(h.relevance)}" for h in r.hits))
    # The associative reach itself is intact: concept-only hits still admit.
    direct_count = sum(1 for t in tiers if t == 0)
    assert direct_count >= 2 and len(r.hits) > direct_count, (
        "fixture lost its two-tier shape (need both direct and concept-only hits): "
        + "; ".join(f"{h.title}={sorted(h.relevance)}" for h in r.hits))


def test_expand_walks_both_directions_and_records_parent(system) -> None:
    ids = system.remember_many([
        MemoryRecordInput(kind="episode", title="Source episode",
                          digest="The thing that happened first."),
        MemoryRecordInput(kind="summary", title="Summary of it",
                          digest="A look back over the episode.",
                          edges=(("summarizes", "local:0"),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="expand-seed")
    probe_r = system.probe(Stimulus(cue_text="episode"), scopes=SCOPES,
                           reason="find the episode")
    x = system.probe_expand([ids[0]], reason="what connects to the episode",
                            parent_trace_id=probe_r.trace_id)
    assert [h.graph_id for h in x.hits] == [ids[1]]  # incoming summarizes edge
    assert any("summarizes" in c for h in x.hits for c in h.cues)
    [trace] = system.journal.traces(trace_id=x.trace_id)
    assert trace.trace_kind == "expand"
    assert trace.need["parent_trace_id"] == probe_r.trace_id


def test_expand_honors_closure_folds(system) -> None:
    ids = system.remember_many([
        MemoryRecordInput(kind="episode", title="Kept", digest="Still here."),
        MemoryRecordInput(kind="summary", title="Closed summary",
                          digest="Will be retracted.",
                          edges=(("summarizes", "local:0"),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="closure-seed")
    system.close_record(ids[1], reason="test: retract the summary")
    x = system.probe_expand([ids[0]], reason="expansion after closure")
    assert all(h.graph_id != ids[1] for h in x.hits), "expansion surfaced a closed record"


def test_expand_accepts_row_ids_and_refuses_unknown_roots(system) -> None:
    """The natural composition (adversary F1): probe hands hosts ROW ids;
    expanding from them must work identically to graph ids — and an id
    that resolves in NEITHER namespace refuses loudly, never returns an
    empty walk."""
    ids = system.remember_many([
        MemoryRecordInput(kind="episode", title="Root episode",
                          digest="The root thing happened.", keywords=("root",)),
        MemoryRecordInput(kind="summary", title="Its summary",
                          digest="Looking back at the root thing.",
                          edges=(("summarizes", "local:0"),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="rowid-seed")
    p = system.probe(Stimulus(cue_text="root"), scopes=SCOPES,
                     reason="get a row id")
    row_id = next(h.record_id for h in p.hits if h.graph_id == ids[0])
    assert row_id != ids[0]  # genuinely the other namespace
    x = system.probe_expand([row_id], reason="expand from a probe hit")
    assert [h.graph_id for h in x.hits] == [ids[1]]
    with pytest.raises(ValueError, match="neither id namespace|no record in either"):
        system.probe_expand(["ex:never-formed"], reason="unknown root")


def test_expand_default_scope_containment_and_hidden_fold(system) -> None:
    """A scopeless expand derives containment from the roots' own scopes
    (adversary F4): cross-scope edges pull no foreign digests, and hidden
    records stay folded."""
    [foreign] = system.remember_many([
        MemoryRecordInput(kind="episode", title="Foreign scope record",
                          digest="Lives in another scope entirely."),
    ], scope="work", owner_id="entity:someone-else", idempotency_key="foreign")
    ids = system.remember_many([
        MemoryRecordInput(kind="episode", title="Home root",
                          digest="The home-scope root.",
                          edges=(("relates_to", foreign),)),
        MemoryRecordInput(kind="summary", title="Home summary",
                          digest="Summary at home.", edges=(("summarizes", "local:0"),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="containment-seed")
    x = system.probe_expand([ids[0]], reason="containment check")
    got = {h.graph_id for h in x.hits}
    assert ids[1] in got
    assert foreign not in got, "scopeless expand pulled a foreign-scope digest"


def test_expand_ranks_by_connection_count(system) -> None:
    """More distinct edges into a node = stronger evidence = ranks first
    (adversary F7: the old key ranked least-connected strangers first)."""
    ids = system.remember_many([
        MemoryRecordInput(kind="episode", title="Hub target",
                          digest="Named by both roots."),
        MemoryRecordInput(kind="episode", title="Fringe target",
                          digest="Named by one root only."),
        MemoryRecordInput(kind="episode", title="Root A",
                          digest="First root.",
                          edges=(("relates_to", "local:0"), ("relates_to", "local:1"))),
        MemoryRecordInput(kind="episode", title="Root B",
                          digest="Second root.",
                          edges=(("mentions", "local:0"),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="rank-seed")
    x = system.probe_expand([ids[2], ids[3]], reason="rank check")
    got = [h.graph_id for h in x.hits]
    assert got.index(ids[0]) < got.index(ids[1]), "hub did not outrank fringe"
    hub = next(h for h in x.hits if h.graph_id == ids[0])
    assert hub.relevance.get("connections", 0) >= 2
