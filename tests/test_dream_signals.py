"""Dream signals (laurent's Q1 ruling, dm#67 + ratification dm#75): the
night as a SIGNAL STREAM from maintenance acts, composed onto the ONE
review-gated dream record.

Guards pinned here:
- the stream derives from acts that DID something and every fragment word
  comes from the touched records (zero LLM, deterministic);
- felt blocks READ accumulated valence; the valence journal is
  BYTE-UNCHANGED through the whole sleep pass (at live cadence even ±1
  machine deposits would saturate the never-decaying channels in days);
- no dream minted = no signal stream at rest (novelty-keyed emission by
  construction — signals live only on the minted record);
- composition is bounded and deterministic.
"""

from __future__ import annotations

from typing import Any, Dict

from abstractmemory import MemorySystem, Stimulus, dream_pass, sleep_pass
from abstractmemory.dream_signals import (
    SIGNAL_KINDS,
    compose_signals,
    night_feelings,
    signal,
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


def _two_island_world(system) -> Dict[str, str]:
    """Two components sharing facets (bridge tension) — the standard
    dreamable world from the consolidation suite."""
    ids = {}
    ids["db-episode"] = _remember(system, "s-1", "episode", "Pool outage night",
                                  "The connection pool saturated at noon.",
                                  keywords=("pool", "saturation", "noon"))
    ids["db-lesson"] = _remember(system, "s-2", "lesson", "Batch the writers",
                                 "Batching the noon cron fixed the pool.",
                                 keywords=("pool", "batching"),
                                 edges=(("supports", ids["db-episode"]),))
    ids["garden-episode"] = _remember(system, "s-3", "episode", "Garden sensor day",
                                      "Planted the garden moisture sensors at noon.",
                                      keywords=("garden", "sensors", "noon"))
    return ids


def _dream_attributes(system, dream_id: str) -> Dict[str, Any]:
    rows = system._store.query(TripleQuery(subject=dream_id, limit=0))
    for row in rows:
        attrs = row.attributes if isinstance(row.attributes, dict) else {}
        if attrs.get("record_kind") == "dream" or "signals" in attrs:
            return attrs
    # Fold all rows' attributes (digest row carries record attrs).
    merged: Dict[str, Any] = {}
    for row in rows:
        if isinstance(row.attributes, dict):
            merged.update(row.attributes)
    return merged


# ---------------------------------------------------------------------------
# The stream rides the dream record
# ---------------------------------------------------------------------------


def test_dream_carries_the_nights_signal_stream(system) -> None:
    ids = _two_island_world(system)
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    dream_id = night["dream"]["dream_record_id"]
    assert dream_id, "the two-island world must dream"

    attrs = _dream_attributes(system, dream_id)
    signals = attrs.get("signals")
    assert isinstance(signals, list) and signals, "signals must rest on the dream"
    for s in signals:
        assert s["kind"] in SIGNAL_KINDS
        assert s["phase"] and s["act"]
        assert len(s["fragment"]) <= 200
        assert isinstance(s["touched"], list)
    # Tonight's tension signal names BOTH records verbatim (the ruling's
    # blue-sky-and-happiness shape: words from the touched records).
    tension = [s for s in signals if s["kind"] == "unresolved_tension"]
    assert tension, "a bridge-proposal night emits tension signals"
    assert any("Pool outage night" in s["fragment"]
               or "Garden sensor day" in s["fragment"] for s in tension)
    assert any(ids["db-episode"] in s["touched"] or ids["garden-episode"] in s["touched"]
               for s in tension)


def test_no_dream_means_no_signal_stream_at_rest(system, stack) -> None:
    """Restful/quiet nights leave NOTHING at rest (C's novelty-keyed P0):
    signals exist only on a minted dream record."""
    store, _ = stack
    _two_island_world(system)
    first = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert first["dream"]["dream_record_id"]
    rows_after_first = len(store.query(TripleQuery(limit=0)))

    second = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert second["dream"]["dream_record_id"] is None, (
        "the novelty gate must read the same tensions as already carried")
    assert "night" in (second["dream"]["skipped_reason"] or "")
    assert len(store.query(TripleQuery(limit=0))) == rows_after_first, (
        "a skipped night must write no rows — no orphan signal stream")


# ---------------------------------------------------------------------------
# Feelings: read-only coloring, never deposits
# ---------------------------------------------------------------------------


def test_valence_journal_byte_unchanged_through_sleep(system, stack) -> None:
    _, journal = stack
    ids = _two_island_world(system)
    # He felt something toward the outage episode before sleeping.
    system.appraise(ids["db-episode"], sign=1, magnitude=2.0,
                    reason="the fix held", scope=SCOPE, owner_id=OWNER,
                    actor="entity-reflection")
    before = [(e.event_id, e.kind, e.target_id, e.sign, e.magnitude)
              for e in journal.valence_events(scope=SCOPE, owner_id=OWNER, limit=0)]
    assert before, "fixture must hold at least one feeling"

    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert night["dream"]["dream_record_id"]

    after = [(e.event_id, e.kind, e.target_id, e.sign, e.magnitude)
             for e in journal.valence_events(scope=SCOPE, owner_id=OWNER, limit=0)]
    assert after == before, (
        "sleep must never deposit feelings — the felt blocks are READS")


def test_felt_blocks_read_his_accumulated_valence(system) -> None:
    ids = _two_island_world(system)
    system.appraise(ids["db-episode"], sign=1, magnitude=2.0,
                    reason="proud of that repair", scope=SCOPE, owner_id=OWNER,
                    actor="entity-reflection")
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    attrs = _dream_attributes(system, night["dream"]["dream_record_id"])
    felt = [s.get("felt") for s in attrs["signals"]
            if s.get("felt") and ids["db-episode"] in s.get("touched", ())]
    assert felt, "a felt-toward record touched by a signal must carry a felt block"
    assert felt[0]["tone"] == "warm"
    assert felt[0]["weight"] > 0
    # Records he never felt anything toward carry NO felt block (no
    # fabricated neutrality).
    unfelt = [s for s in attrs["signals"]
              if ids["garden-episode"] in s.get("touched", ())
              and ids["db-episode"] not in s.get("touched", ())]
    for s in unfelt:
        assert "felt" not in s


def test_night_feelings_is_one_pure_batched_read(system, stack) -> None:
    _, journal = stack
    ids = _two_island_world(system)
    system.appraise(ids["db-episode"], sign=-1, magnitude=1.0, reason="it stung",
                    scope=SCOPE, owner_id=OWNER, actor="entity-reflection")
    events_before = len(journal.valence_events(scope=SCOPE, owner_id=OWNER, limit=0))
    folded = night_feelings(system, scopes=SCOPES)
    assert ids["db-episode"] in folded
    assert folded[ids["db-episode"]].net < 0
    assert len(journal.valence_events(scope=SCOPE, owner_id=OWNER, limit=0)) == events_before


def test_deployed_ladder_shape_colors_record_feelings(system) -> None:
    """Adversary P0-1 regression (the deployed-shape miss): production
    callers lead the ladder with ("self", entity) while reflection lanes
    deposit RECORD-target feelings into "life" — the fold must read the
    WHOLE ladder or record-connection coloring (laurent's motivating
    case) never fires."""
    ids = _two_island_world(system)
    # Deposit exactly as chat.py does for record targets: scope="life".
    system.appraise(ids["db-episode"], sign=1, magnitude=2.0,
                    reason="that repair mattered", scope="life", owner_id=OWNER,
                    actor="entity-reflection")
    ladder = [("self", OWNER), ("diary", OWNER), ("life", OWNER)]
    folded = night_feelings(system, scopes=ladder)
    assert ids["db-episode"] in folded, (
        "a life-scope record feeling must survive the self-led ladder fold")
    night = sleep_pass(system, scopes=[("life", OWNER)], owner_id=OWNER)
    dream_id = night["dream"]["dream_record_id"]
    assert dream_id
    attrs = _dream_attributes(system, dream_id)
    felt = [s for s in attrs["signals"]
            if s.get("felt") and ids["db-episode"] in s.get("touched", ())]
    assert felt, "the tension touching the felt record must carry its color"


def test_felt_reads_channels_never_the_net(system) -> None:
    """Adversary P1-2: +8/-8 ambivalence is MIXED with real weight, never
    'neutral, weight 0' — the dual-channel charter applied to the night."""
    ids = _two_island_world(system)
    system.appraise(ids["db-episode"], sign=1, magnitude=3.0, reason="it shone",
                    scope=SCOPE, owner_id=OWNER, actor="entity-reflection")
    system.appraise(ids["db-episode"], sign=-1, magnitude=3.0, reason="it burned",
                    scope=SCOPE, owner_id=OWNER, actor="entity-reflection")
    from abstractmemory.dream_signals import _felt

    folded = night_feelings(system, scopes=SCOPES)
    block = _felt(folded, [ids["db-episode"]])
    assert block is not None
    assert block["tone"] == "mixed"
    assert block["weight"] >= 3.0


def test_section_caps_never_starve_the_dreams_own_tensions() -> None:
    """Adversary P1-3: twelve resolutions must not evict the tension
    signals — each section holds reserved seats."""
    resolution = {"resolved": [
        {"dream_id": f"ex:dream-{i}", "closed": True, "settled": 2,
         "tensions": 2, "mechanisms": ["bridge_confirmed"], "evidence_ids": []}
        for i in range(12)]}
    proposals = [{"pair": ["ex:a", "ex:b"], "shared_facets": ["noon"]}]
    records = {"ex:a": {"title": "Left"}, "ex:b": {"title": "Right"}}
    stream = compose_signals(resolution=resolution, proposals=proposals,
                             report_records=records)
    kinds = [s["kind"] for s in stream]
    assert "unresolved_tension" in kinds, (
        "the dream's own tension must survive a resolution-heavy night")
    assert len(stream) <= 12
    # Structural order holds across the backfilled stream.
    phases = [s["phase"] for s in stream]
    assert phases == sorted(phases, key=lambda p: {"resolution": 0, "dream": 3}.get(p, 2))


# ---------------------------------------------------------------------------
# Composition: deterministic, bounded, act-derived
# ---------------------------------------------------------------------------


def test_compose_signals_deterministic_bounded_and_act_gated() -> None:
    resolution = {"resolved": [
        {"dream_id": "ex:dream-1", "closed": True, "settled": 3, "tensions": 4,
         "mechanisms": ["bridge_confirmed"], "evidence_ids": ["ex:ep-1"]},
        {"dream_id": "ex:dream-2", "closed": False},  # report-only: no act
    ]}
    maintenance = {"created": [
        {"candidate_id": "ex:cand-1", "source_ids": ["ex:a", "ex:b"], "created": True},
        {"candidate_id": "ex:cand-2", "source_ids": ["ex:c"], "created": False},  # retry
    ]}
    world_models = {"formed": [
        {"formed": True, "target": "person:laurent", "card_id": "ex:card-1",
         "revision": 2, "source_count": 5},
        {"formed": False, "target": "topic:x", "card_id": None},  # unchanged: no act
    ]}
    proposals = [{"pair": ["ex:a", "ex:b"], "shared_facets": ["noon"]}]
    records = {"ex:a": {"title": "Left thing"}, "ex:b": {"title": "Right thing"},
               "ex:ep-1": {"title": "Evidence day"}}

    one = compose_signals(resolution=resolution, maintenance=maintenance,
                          world_models=world_models, proposals=proposals,
                          report_records=records)
    two = compose_signals(resolution=resolution, maintenance=maintenance,
                          world_models=world_models, proposals=proposals,
                          report_records=records)
    assert one == two, "same night, same stream — deterministic"

    acts = [(s["phase"], s["act"]) for s in one]
    assert ("resolution", "dream_resolved") in acts
    assert ("world_models", "card_revised") in acts
    assert ("maintenance", "grouped") in acts
    assert ("dream", "bridge_proposed") in acts
    # Non-acts never emit: the report-only verdict, the idempotent retry,
    # the unchanged card.
    assert len([a for a in acts if a[1] == "dream_resolved"]) == 1
    assert len([a for a in acts if a[1] == "grouped"]) == 1
    assert not any(s["act"] == "card_formed" for s in one)
    # Fragment words come from the touched records.
    bridge = next(s for s in one if s["act"] == "bridge_proposed")
    assert "Left thing" in bridge["fragment"] and "Right thing" in bridge["fragment"]
    # Structural order: resolutions first (the day answered the night).
    assert acts[0] == ("resolution", "dream_resolved")

    capped = compose_signals(resolution=resolution, maintenance=maintenance,
                             world_models=world_models, proposals=proposals,
                             report_records=records, top_k=2)
    assert len(capped) == 2


def test_dream_display_block_carries_the_signal_stream(system, stack) -> None:
    """The serving lane (entity c3711): consumers fold from replay
    display blocks — the dream's block carries the bounded stream
    verbatim, so no consumer needs a second attribute door."""
    from abstractmemory import export_replay

    store, journal = stack
    _two_island_world(system)
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    dream_id = night["dream"]["dream_record_id"]
    assert dream_id
    blocks = [env.get("display") for env in export_replay(store, journal)
              if isinstance(env.get("display"), dict)
              and env["display"].get("graph_id") == dream_id]
    assert blocks, "the dream must appear in the replay stream"
    signals = blocks[0].get("signals")
    assert isinstance(signals, list) and signals
    assert signals == _dream_attributes(system, dream_id)["signals"]


def test_brief_unit_is_signals_and_cap_cost_is_visible(system, stack) -> None:
    """Observer c3802 (first live night, two-lane verification): the
    brief's count counts SIGNALS not dreams — a render read '24 dreams'
    for hours because prose was the only contract. The unit field pins
    it; `dreams` carries the other number; and the dream records the cap
    cost (signals_omitted) so bounded selection is never silent."""
    from abstractmemory import entity_card

    store, journal = stack
    _two_island_world(system)
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    dream_id = night["dream"]["dream_record_id"]
    assert dream_id
    card = entity_card(store, journal, scope_pairs=SCOPES, owner_id=OWNER)
    brief = card["discoveries"]["dreams_signals_brief"]
    assert brief["unit"] == "signals"
    assert brief["dreams"] == 1
    assert brief["count"] == len(_dream_attributes(system, dream_id)["signals"])
    attrs = _dream_attributes(system, dream_id)
    assert attrs["signals_omitted"] == 0, "an uncapped night reads complete"

    stream = compose_signals(
        resolution={"resolved": [
            {"dream_id": f"ex:d{i}", "closed": True, "settled": 1, "tensions": 1,
             "mechanisms": [], "evidence_ids": []} for i in range(20)]},
        stats=(stats := {}))
    assert len(stream) <= 12
    assert stats["candidates_total"] == 20
    assert stats["omitted"] == 8, "the cap's selection cost is on the record"


def test_card_carries_the_dreams_signals_brief(system, stack) -> None:
    """The card half of the three-seat convergence (c3721/c3722): a
    BOUNDED brief (count + kinds + felt tones) on the entity card —
    never fragments; depth stays on the record/display block."""
    from abstractmemory import entity_card

    store, journal = stack
    ids = _two_island_world(system)
    system.appraise(ids["db-episode"], sign=1, magnitude=2.0, reason="held",
                    scope=SCOPE, owner_id=OWNER, actor="entity-reflection")
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert night["dream"]["dream_record_id"]
    card = entity_card(store, journal, scope_pairs=SCOPES, owner_id=OWNER)
    brief = card["discoveries"].get("dreams_signals_brief")
    assert brief and brief["count"] >= 1
    assert set(brief["kinds"]) <= {"changed_understanding", "unresolved_tension",
                                   "changed_navigation"}
    assert "warm" in brief["felt_tones"]
    assert "fragments" not in brief and "touched" not in brief


def test_cycle_window_runs_quality_passes_without_the_dream(system, stack) -> None:
    """The maintenance-cycle composition (dm#104 cycle; v12 P1-6): a ~1h
    cycle window at every-2h cadence runs resolution/tending/world-models/
    mining but NEVER mints a dream — dream formation keeps its nightly
    cadence budget, or a standing grant would form salience-50 dreams
    every ~3h (the bridge-attractor class)."""
    store, _ = stack
    _two_island_world(system)
    cycle = sleep_pass(system, scopes=SCOPES, owner_id=OWNER, include_dream=False)
    assert cycle["phases"] == ("resolution", "maintenance", "world_models",
                               "mining", "dream")
    assert cycle["dream"]["dream_record_id"] is None
    assert "nightly cadence budget" in cycle["dream"]["skipped_reason"]
    dream_rows = [a for a in store.query(TripleQuery(limit=0))
                  if isinstance(a.attributes, dict)
                  and a.attributes.get("record_kind") == "dream"]
    assert not dream_rows, "a cycle window must write NO dream record"

    # The nightly pass over the same state still dreams — the budget is
    # the host's composition, never a lost capability.
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert night["dream"]["dream_record_id"]


def test_signal_kind_is_a_closed_set() -> None:
    try:
        signal("wishful_thinking", phase="dream", act="x", fragment="y", touched=())
    except ValueError as e:
        assert "wishful_thinking" in str(e)
    else:  # pragma: no cover
        raise AssertionError("unknown signal kinds must refuse loudly")


def test_narration_names_the_nights_acts_and_feelings_color(system) -> None:
    """The digest gains one 'night also moved' sentence when non-dream
    acts happened, and a felt-tone close when the stream carries
    feelings — structure decides, feelings color."""
    ids = _two_island_world(system)
    system.appraise(ids["db-episode"], sign=1, magnitude=2.0, reason="good repair",
                    scope=SCOPE, owner_id=OWNER, actor="entity-reflection")
    # A prior standing dream the day resolved would need a full lineage;
    # the cheap non-dream act is a consolidation candidate — force one by
    # duplicating titles.
    _remember(system, "s-dup-1", "episode", "Same day twice",
              "First telling of the same day.", keywords=("pool",))
    _remember(system, "s-dup-2", "episode", "Same day twice",
              "Second telling of the same day.", keywords=("pool",))
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    dream_id = night["dream"]["dream_record_id"]
    assert dream_id
    rows = system._store.query(TripleQuery(subject=dream_id, limit=0))
    digest = ""
    for row in rows:
        if row.predicate.endswith("abstract"):
            digest = str(row.object)
    assert digest
    # The fixture MUST produce a tending act (adversary P2-7a: an
    # `if created:` guard here silently stopped testing when the fixture
    # drifted) — assert the precondition, then the narration.
    created = [c for c in night["maintenance"]["created"] if c.get("created")]
    assert created, "fixture drift: the duplicate titles must mint a candidate"
    assert "The night also moved:" in digest
    assert "feels warm" in digest or "feels mixed" in digest
