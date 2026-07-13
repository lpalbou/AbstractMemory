"""Dream subconscious lifecycle (backlog 0032): the day answers the night.

Contracts pinned:
- dreams FORM with resurfacing metadata (keywords/participants drawn from
  their own tension vocabulary) so normal recall channels surface a dream
  exactly when its trigger appears — influence, never a push;
- a bridge-proposal dream resolves SOFTLY when the day joins the pair
  (authored story or lived co-use); the closure names the mechanism and
  carries the evidence; the dream leaves the standing set append-only;
- a facet-question dream resolves when a NEW post-dream record carries the
  questioned facet and touches an endpoint;
- resolution is conservative (all tensions must settle at default tuning),
  post-dating (yesterday's records cannot resolve tomorrow's dream), and
  deposits NOTHING (the D2 of sleep);
- continuation dreams resolve when their re-lit lineage settles;
- sleep_pass runs resolution FIRST (a settled tension never re-arms
  continuation salience).
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
    SleepTuning,
    Stimulus,
    TripleQuery,
    dream_pass,
    resolve_dreams_pass,
    sleep_pass,
    unresolved_dreams,
)
from abstractmemory.records import resolve_digest_assertion

OWNER = "entity:dreamer"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _row_id(system, graph_id: str) -> str:
    digest = resolve_digest_assertion(system.store, graph_id)
    assert digest is not None, f"no digest for {graph_id}"
    return str(digest.assertion_id)


def _dream_attrs(system, graph_id: str) -> dict:
    digest = resolve_digest_assertion(system.store, graph_id)
    assert digest is not None and isinstance(digest.attributes, dict)
    return digest.attributes


def _seed_two_islands(system):
    """Two components sharing >= 2 facets — the bridge-PROPOSAL substrate
    (one shared facet would make a question instead)."""
    return system.remember_many([
        MemoryRecordInput(kind="episode", title="Project stall",
                          digest="The migration project stalled at the schema step.",
                          keywords=("migration", "schema"),
                          participants=("person:ada",)),
        MemoryRecordInput(kind="episode", title="Library visit",
                          digest="Reading about schema migration patterns at the library.",
                          keywords=("migration", "schema", "patterns"),
                          participants=("person:grace",)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="islands")


def _dream(system, **kwargs):
    return dream_pass(system, scopes=SCOPES, owner_id=OWNER,
                      salience_floor=1, **kwargs)


def _standing(system):
    return [a.subject for a in unresolved_dreams(
        system.store, scope=SCOPE, owner_id=OWNER, journal=system.journal)]


def test_dreams_form_with_resurfacing_metadata(system) -> None:
    _seed_two_islands(system)
    out = _dream(system)
    assert out["created"], out.get("skipped_reason")
    gid = out["dream_record_id"]
    attrs = _dream_attrs(system, gid)
    assert attrs.get("keywords"), "dream formed without tension keywords"
    r = system.reconstruct(Stimulus(cue_text="migration"), scopes=SCOPES)
    assert _row_id(system, gid) in {h.record_id for h in r.handles}, (
        "the dream did not resurface on its own tension keyword")


def test_dream_resurfaces_when_its_person_appears(system) -> None:
    """The maintainer's case: 'I dream about that person… I meet the
    person and the dream resurfaces.' A RARE person spanning two islands
    (the discriminative gate: an ambient companion never bridges) becomes
    dream participants; the participants channel matches on encounter."""
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Harbor walk",
                          digest="Walking the harbor and talking for an hour.",
                          keywords=("harbor",), participants=("person:ada",)),
        MemoryRecordInput(kind="episode", title="Old letter",
                          digest="An old letter resurfaced from the archive box.",
                          keywords=("letter",), participants=("person:ada",)),
        # The rest of the life: ada is RARE (2/6 records), hence signal.
        *[MemoryRecordInput(kind="episode", title=f"Ordinary day {i}",
                            digest=f"An ordinary unrelated moment {i}.",
                            keywords=(f"ordinary{i}",))
          for i in range(4)],
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="person-islands")
    out = _dream(system)
    assert out["created"], out.get("skipped_reason")
    gid = out["dream_record_id"]
    assert "person:ada" in (_dream_attrs(system, gid).get("participants") or ()), (
        "shared participant did not land on the dream")
    # Meeting the person: participants-only stimulus, no lexical overlap.
    r = system.reconstruct(
        Stimulus(cue_text="zzz unrelated words", participants=("person:ada",)),
        scopes=SCOPES)
    assert _row_id(system, gid) in {h.record_id for h in r.handles}, (
        "meeting the person did not resurface the dream about them")


def _co_use(system, ids, cue: str) -> None:
    """One lived co-use: recall + commit BOTH islands in one trace."""
    r = system.reconstruct(Stimulus(cue_text=cue), scopes=SCOPES)
    rows = {_row_id(system, i) for i in ids}
    used = [h.record_id for h in r.handles if h.record_id in rows]
    assert len(used) == 2, "seed episodes did not co-surface"
    system.commit_selection(r.trace_id, used)


def test_day_resolves_bridge_dream_via_lived_co_use(system) -> None:
    ids = _seed_two_islands(system)
    out = _dream(system)
    assert out["created"]
    gid = out["dream_record_id"]
    assert gid in _standing(system)

    # ONE co-display is co-appearance, not lived association (P1-5 floor:
    # default resolution_trail_min_traces=2) — the dream stands.
    _co_use(system, ids, "migration schema patterns")
    early = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert early["resolved_count"] == 0, "a single co-display resolved the dream"

    # A SECOND distinct trace of co-use: now it is lived association.
    _co_use(system, ids, "schema migration again")
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert res["resolved_count"] == 1
    verdict = res["resolved"][0]
    assert verdict["dream_id"] == gid
    assert "associated_by_lived_use" in verdict["mechanisms"]
    assert set(verdict["evidence_ids"]) == set(ids)
    # The dream left the standing set (closure fold), append-only.
    assert _standing(system) == []
    # Idempotent re-run: nothing left to resolve, nothing re-closed.
    again = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert again["examined"] == 0 and again["resolved_count"] == 0


def test_day_resolves_bridge_dream_via_authored_story(system) -> None:
    ids = _seed_two_islands(system)
    out = _dream(system)
    gid = out["dream_record_id"]
    # The day: a summary WRITES the story that joins the islands.
    system.remember_many([
        MemoryRecordInput(kind="summary", title="How the stall broke",
                          digest="The library patterns unlocked the stalled migration.",
                          edges=(("summarizes", ids[0]), ("summarizes", ids[1]))),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="joining-story")
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert res["resolved_count"] == 1
    assert res["resolved"][0]["dream_id"] == gid
    assert "joined_by_authored_story" in res["resolved"][0]["mechanisms"]


def test_unresolved_tension_stands(system) -> None:
    _seed_two_islands(system)
    out = _dream(system)
    gid = out["dream_record_id"]
    # No day activity: nothing settles; the dream stands, named.
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert res["resolved_count"] == 0
    assert any(s["dream_id"] == gid for s in res["standing"])
    assert gid in _standing(system)


def test_report_only_never_closes(system) -> None:
    ids = _seed_two_islands(system)
    out = _dream(system)
    gid = out["dream_record_id"]
    _co_use(system, ids, "migration schema patterns")
    _co_use(system, ids, "schema migration again")
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
    assert res["resolved"] and res["resolved"][0]["dream_id"] == gid
    assert res["resolved"][0]["closed"] is False
    assert res["resolved_count"] == 0
    assert gid in _standing(system), "report_only closed a dream"


def test_resolution_deposits_nothing(system) -> None:
    """The D2 of sleep extends to resolution: closures are belief revision,
    never usage."""
    ids = _seed_two_islands(system)
    _dream(system)
    _co_use(system, ids, "migration schema patterns")
    _co_use(system, ids, "schema migration again")
    before = system.access_counts(record_ids=ids)
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert res["resolved_count"] == 1
    after = system.access_counts(record_ids=ids)
    assert before == after, "passive resolution deposited usage"


def test_facet_question_resolved_by_new_experience(system) -> None:
    """A question dream ('does X connect these?') resolves when a NEW
    record carries the facet and touches an endpoint."""
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Garden note",
                          digest="Pruning roses in the north garden bed.",
                          keywords=("roses",), participants=("person:ada",)),
        MemoryRecordInput(kind="episode", title="Market trip",
                          digest="Bought roses and bread at the market.",
                          keywords=("roses", "market"), participants=("person:grace",)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="question-islands")
    out = _dream(system)
    assert out["created"], out.get("skipped_reason")
    gid = out["dream_record_id"]
    assert _dream_attrs(system, gid).get("questions"), "expected a facet question dream"

    # The day: a new episode about roses WITH ada (touches endpoint 1).
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Rose show",
                          digest="Ada and I visited the rose show downtown.",
                          keywords=("roses", "show"), participants=("person:ada",)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="rose-day")
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert res["resolved_count"] == 1
    assert res["resolved"][0]["dream_id"] == gid
    assert "facet_found_its_subject_in_experience" in res["resolved"][0]["mechanisms"]


def test_pre_dream_records_cannot_resolve_a_question(system) -> None:
    """Post-dating rule: only records formed AFTER the dream count as the
    day's answer. Seeded so the pre-dated record WOULD settle one of two
    question tensions if the seq filter were deleted (fraction 0.5 makes
    that flip the verdict — a vacuous version of this pin was the first
    adversary's P1-6)."""
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Garden note",
                          digest="Pruning roses in the north garden bed.",
                          keywords=("roses",)),
        MemoryRecordInput(kind="episode", title="Market trip",
                          digest="Bought roses and bread at the market.",
                          keywords=("roses", "market")),
        # Pre-dated: carries the questioned facet AND touches the Garden
        # endpoint (authored edge) — it would settle the Garden↔Market
        # question if post-dating were broken.
        MemoryRecordInput(kind="episode", title="Rose show",
                          digest="Visited the rose show downtown.",
                          keywords=("roses", "show"),
                          edges=(("continues", "local:0"),)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="pre-dated")
    out = _dream(system)
    assert out["created"], out.get("skipped_reason")
    tuned = SleepTuning(resolution_fraction=0.5)
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=tuned)
    assert res["resolved_count"] == 0, (
        "a pre-dream record resolved a dream question (post-dating broken)")


def test_continuation_dream_resolves_with_its_lineage(system) -> None:
    """A continuation dream re-lights standing tension; when the whole
    lineage settles, it follows. Seeded directly (a dream-pass night on an
    unchanged graph is idempotent BY DESIGN — same fingerprint, no second
    record — so the continuation record is formed as the engine forms it,
    with continuation_state='continued')."""
    ids = _seed_two_islands(system)
    first = _dream(system)
    gid1 = first["dream_record_id"]
    [gid2] = system.remember_many([
        MemoryRecordInput(
            kind="dream", title="Dream: returning to an unresolved tension",
            digest="The same tension pressed again tonight.",
            attributes={"continuation_state": "continued",
                        "parent_dream_ids": [gid1],
                        "interpretation_required": True,
                        "proposals": [], "questions": []}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="continuation")
    assert set(_standing(system)) == {gid1, gid2}, (
        "a continuation dream must STAND (or it could never resolve)")
    # The day settles the original tension by lived use (two traces).
    _co_use(system, ids, "migration schema patterns")
    _co_use(system, ids, "schema migration again")
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    resolved = {v["dream_id"] for v in res["resolved"]}
    assert gid1 in resolved, "the parent dream did not resolve"
    assert gid2 in resolved, "the continuation dream did not follow its lineage"
    assert any("relit_tension_settled" in v["mechanisms"]
               for v in res["resolved"] if v["dream_id"] == gid2)
    assert _standing(system) == []


def test_sleeps_own_artifacts_never_resolve_a_dream(system) -> None:
    """Adversary P0-1: a consolidation candidate (sleep's own summary,
    summarizes edges) must NOT count as the authored story that joins the
    islands — waking evidence is never sleep's artifact."""
    ids = _seed_two_islands(system)
    out = _dream(system)
    gid = out["dream_record_id"]
    # Simulate the tending write: a maintenance candidate summarizing
    # BOTH islands (exactly what consolidation_pass forms).
    system.remember_many([
        MemoryRecordInput(kind="summary", title="Maintenance candidate",
                          digest="Stands for the group pending waking review.",
                          edges=(("summarizes", ids[0]), ("summarizes", ids[1])),
                          attributes={"maintenance_candidate": True,
                                      "review_required": True}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="sleep-artifact")
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert res["resolved_count"] == 0, (
        "sleep's own candidate resolved the dream (P0-1 regression)")
    assert gid in _standing(system)


def test_retracted_stories_do_not_resolve_and_closed_endpoints_stand(system) -> None:
    """Adversary P0-2: resolution evidence is closure-folded — a story the
    day retracted stops joining islands, and a closed endpoint means the
    tension STANDS (absence of a party is not evidence)."""
    ids = _seed_two_islands(system)
    out = _dream(system)
    gid = out["dream_record_id"]
    # An authored story joins the islands… then the day retracts it.
    [story] = system.remember_many([
        MemoryRecordInput(kind="summary", title="How the stall broke",
                          digest="The library patterns unlocked the migration.",
                          edges=(("summarizes", ids[0]), ("summarizes", ids[1]))),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="retractable-story")
    system.close_record(story, reason="the story was wrong")
    res = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert res["resolved_count"] == 0, "a retracted story resolved the dream"
    assert gid in _standing(system)

    # And a closed ENDPOINT leaves the tension standing, never "settled".
    system.close_record(ids[1], reason="endpoint retracted")
    res2 = resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert res2["resolved_count"] == 0
    assert gid in _standing(system)


def test_writes_under_as_of_refuse_loudly(system) -> None:
    """Adversary P1-4: as_of anchors audit reads only — every sleep-lane
    write phase refuses a historical anchor."""
    _seed_two_islands(system)
    with pytest.raises(ValueError, match="as_of"):
        resolve_dreams_pass(system, scopes=SCOPES, owner_id=OWNER, as_of=1)
    with pytest.raises(ValueError, match="as_of"):
        dream_pass(system, scopes=SCOPES, owner_id=OWNER, as_of=1)
    with pytest.raises(ValueError, match="as_of"):
        sleep_pass(system, scopes=SCOPES, owner_id=OWNER, as_of=1)
    # report_only anchored reads stay legal.
    out = sleep_pass(system, scopes=SCOPES, owner_id=OWNER, as_of=1,
                     report_only=True)
    assert out["world_models"]["skipped_reason"], (
        "anchored night must skip the current-state world-model phase")


def test_ambient_companions_do_not_flood_proposals(system) -> None:
    """Adversary P1-2: the deployed shape — every record stamped with the
    same visitor — must not turn every cross-island pair into a proposal,
    and the dream's participants metadata never carries ambient stamps."""
    system.remember_many([
        MemoryRecordInput(kind="episode", title=f"Island {i}",
                          digest=f"Unrelated moment number {i}.",
                          keywords=(f"unique{i}",),
                          participants=("person:laurent", OWNER))
        for i in range(6)
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="ambient")
    out = _dream(system)
    # person:laurent is on 6/6 records (> max fraction): no person-bridges.
    assert out["proposals"] == [], (
        f"ambient companion flooded {len(out['proposals'])} proposals")
    if out["created"]:
        attrs = _dream_attrs(system, out["dream_record_id"])
        assert "person:laurent" not in (attrs.get("participants") or ())
        assert OWNER not in (attrs.get("participants") or ())


def test_sleep_pass_resolves_before_dreaming(system) -> None:
    ids = _seed_two_islands(system)
    first = _dream(system)
    gid1 = first["dream_record_id"]
    _co_use(system, ids, "migration schema patterns")
    _co_use(system, ids, "schema migration again")

    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER, salience_floor=1)
    assert night["phases"] == ("resolution", "maintenance", "world_models", "dream")
    assert night["resolution"]["resolved_count"] == 1
    assert night["resolution"]["resolved"][0]["dream_id"] == gid1
    # Tonight's dream (if any) must not chain the settled tension.
    if night["dream"]["created"]:
        attrs = _dream_attrs(system, night["dream"]["dream_record_id"])
        assert gid1 not in (attrs.get("parent_dream_ids") or ()), (
            "a resolved dream re-armed continuation anchors")


def test_resolution_tunables_exist(system) -> None:
    tuned = SleepTuning(resolution_fraction=0.5, resolution_evidence_bound=2)
    assert tuned.resolution_fraction == 0.5
    assert tuned.resolution_evidence_bound == 2
