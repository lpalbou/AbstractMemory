"""The ```tend election grammar: parse + apply over EXISTING engine verbs.

Flagship: the CASTOR SCENARIO — a story's near-identical retellings dominate
the shelf through temporal access counts (rich-get-richer); one parsed tend
block (silence the retellings + refocus) restores shelf diversity, and the
distinct episodes surface. The margins in that test derive from the pinned
engine math (attention.py 0018 decay + shelf.order_members fusion), not from
tuned fixtures:

- 6 single-record commits saturate each retelling at the 25.0 activation
  clamp -> ranking boost 100/1000 = +0.100 on fused relevance;
- retellings keyword-match the cue at 11/12 (0.9167), distinct episodes at
  12/12 (1.0): pre-tend 0.9167 + 0.100 = 1.0167 > 1.0 (dominance);
- the per-step clamp makes a FRESH silence floor at 0 on a saturated record
  (attention.py: "a silence NEWER than all use floors at 0"), so the block
  pairs silences WITH a refocus (the maintainer's design input: refocus is
  what helps previously unselected memories surface): post-tend the
  stretched trail sums to < 8 activation -> boost < 32/1000, and
  0.9167 + 0.032 < 1.0 (diversity restored).

Everything else pins the grammar (refusals as data, cap, mandatory reason),
the apply rails (channel gate, identity-scope pending ruling, spoofs, empty
actor), the iterative revisit reach (probe_expand reuse: journals like the
probe, deposits nothing), heal/break end-to-end, and dream disposal.
"""

from __future__ import annotations

import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    MemoryRecordInput,
    RecallBudget,
    Stimulus,
    TripleQuery,
    dream_pass,
    unresolved_dreams,
)
from abstractmemory.tend import (
    DEFAULT_MAX_ELECTIONS,
    IDENTITY_SCOPE_PENDING_RULING,
    apply_tend_elections,
    parse_tend_block,
)

SCOPE = "life"
OWNER = "entity:castor"
ACTOR = "entity-reflection"


def _apply(system, elections, **kw):
    kw.setdefault("scope", SCOPE)
    kw.setdefault("owner_id", OWNER)
    kw.setdefault("actor", ACTOR)
    # Explicit channel (P0-1 refusing-default): these tests simulate the
    # home-direct driver, where entity-reflection is true by construction.
    kw.setdefault("channel", "entity-reflection")
    return apply_tend_elections(system, elections, **kw)


def _form(system, kind, title, digest, key, *, scope=SCOPE, owner=OWNER,
          keywords=(), edges=(), provenance=None, attributes=None):
    attrs = dict(attributes or {})
    if kind == "value":
        attrs.setdefault("value_class", "revisable")
    return system.remember(
        MemoryRecordInput(kind=kind, title=title, digest=digest,
                          keywords=tuple(keywords), edges=tuple(edges),
                          provenance=dict(provenance or {}), attributes=attrs),
        scope=scope, owner_id=owner, idempotency_key=key)


# ---------------------------------------------------------------------------
# The flagship: the Castor scenario
# ---------------------------------------------------------------------------

# 12 cue tokens (all >= 4 chars, the keyword-channel floor). The distinct
# episodes carry all 12; the retellings carry 11 (no "bakery") — the cue
# matches the entity's actual need BETTER than the retellings, and the
# retellings dominate anyway through usage boost. That is the recorded
# bridge-attractor shape: usage-weighted recall + self-retellings.
_CUE = "harbor evening lantern boats tides gulls whistle stone market bells ferry bakery"
_RETOLD = ("The twelve bridges story again: harbor at evening, lantern boats, "
           "tides and gulls, a whistle by the stone market, bells and the ferry.")
_DISTINCT_TAILS = (
    "Warm bakery air; met Chloe by the water.",
    "Warm bakery air; fixed the pump engine.",
    "Warm bakery air; read Tolstoy aloud.",
    "Warm bakery air; mapped the north quay.",
)
_DISTINCT_BASE = ("Walked the harbor at evening: lantern light on the boats, tides "
                  "low, gulls loud, a whistle from the stone market, bells, the ferry. ")


def _seed_castor(system):
    # NEAR-identical retellings, NOT byte-identical (2026-07-27): a real
    # story retold varies slightly, and the shelf dedup (Veya c5907) now
    # correctly collapses byte-identical digests to one seat — a DIFFERENT
    # fix from the tend/silence remedy this scenario tests. Each retelling
    # carries a distinct trailing clause so the 11/12 keyword match (the
    # bridge-attractor's usage dominance) is preserved while the digests
    # stay distinct records the entity must SILENCE, not ones dedup hides.
    retellings = [
        _form(system, "episode", f"Bridges retelling {i}",
              f"{_RETOLD} (retelling {i})", f"retold-{i}")
        for i in range(1, 7)
    ]
    distinct = [
        _form(system, "episode", f"Distinct episode {i}", _DISTINCT_BASE + tail,
              f"distinct-{i}")
        for i, tail in enumerate(_DISTINCT_TAILS, start=1)
    ]
    # Repetition dominance: 6 rounds of single-record commits per retelling
    # (single-record: no co_selected pairs, so ranks stay dense and every
    # retelling saturates the 25.0 activation clamp deterministically).
    for round_n in range(6):
        for i, rid in enumerate(retellings):
            system.commit_selection(f"castor-seed-{round_n}-{i}", [rid])
    return retellings, distinct


def _shelf_ids(system, *, shelf_size=5):
    result = system.reconstruct(
        Stimulus(cue_text=_CUE), scopes=[(SCOPE, OWNER)],
        budget=RecallBudget(shelf_size=shelf_size, token_budget=2400, stm_fraction=0.0),
        view="shelf", journal=False,
    )
    # provenance.record_id carries the graph id for formed records.
    return [str(h.provenance.get("record_id") or h.record_id) for h in result.handles]


def test_castor_scenario_silence_plus_refocus_restores_shelf_diversity(system):
    retellings, distinct = _seed_castor(system)

    pre = _shelf_ids(system)
    assert len(pre) == 5
    assert set(pre) <= set(retellings), (
        f"retellings must dominate every seat pre-tend, got {pre}")

    counts_before = system.access_counts(record_ids=retellings + distinct)["records"]

    block = "\n".join(
        [f"silence: {rid} — reason: the bridges retelling crowds my shelf" for rid in retellings]
        + ["refocus: — reason: the bridges loop is over; let quieter days surface"]
    )
    parsed = parse_tend_block(block, max_elections=8)
    assert parsed["refusals"] == []
    assert [e["verb"] for e in parsed["elections"]] == ["silence"] * 6 + ["refocus"]

    report = _apply(system, parsed["elections"])
    assert report["refused"] == []
    assert len(report["applied"]) == 7

    post = _shelf_ids(system)
    assert set(distinct) <= set(post), (
        f"all four distinct episodes must surface post-tend, got {post}")
    assert len(set(post) & set(retellings)) <= 1

    # Tend never deposits: the global counts are untouched by the whole act.
    counts_after = system.access_counts(record_ids=retellings + distinct)["records"]
    assert counts_after == counts_before
    assert all(counts_after[rid] == 6 for rid in retellings)
    assert all(counts_after[rid] == 0 for rid in distinct)


def test_castor_scenario_silence_alone_cannot_demote_saturated_records(system):
    """Honesty pin for the engine mechanics the flagship relies on: fresh
    silences floor at 0 against a saturated record (per-step clamp), so
    WITHOUT the refocus the retellings keep every seat. This is why the
    grammar offers both verbs — the maintainer's refocus IS the surfacing
    mechanism; silence marks which records recede under it."""
    retellings, distinct = _seed_castor(system)
    block = "\n".join(
        f"silence: {rid} -- reason: crowding" for rid in retellings)
    parsed = parse_tend_block(block, max_elections=6)
    report = _apply(system, parsed["elections"])
    assert report["refused"] == []
    assert set(_shelf_ids(system)) <= set(retellings)


# ---------------------------------------------------------------------------
# Grammar: parse coverage
# ---------------------------------------------------------------------------


def test_parse_every_verb_and_separator_tolerance():
    body = "\n".join([
        "pin: ex:a — reason: keep this near",
        "silence: ex:b -- reason: let this recede",
        "  refocus:   —   reason: topic shift  ",
        "heal_scar: person:rival – reason: the amends held",   # en-dash
        "break_bond: bond-ev-1 — reason: it broke",
        "revisit: ex:c — reason: what connects here",
        "dispose: ex:dream-1 reject — reason: waking walk said no",
        "",
        "```",
    ])
    out = parse_tend_block(body, max_elections=7)
    assert out["refusals"] == []
    verbs = [e["verb"] for e in out["elections"]]
    assert verbs == ["pin", "silence", "refocus", "heal_scar",
                     "break_bond", "revisit", "dispose"]
    assert out["elections"][0]["target"] == "ex:a"
    assert out["elections"][2]["target"] is None
    assert out["elections"][2]["reason"] == "topic shift"
    assert out["elections"][6]["disposition"] == "reject"


def test_parse_dispose_confirm_extras():
    line = ("dispose: ex:dream-9 confirm relation=supports source=ex:a "
            "target=ex:b evidence=ex:w1,ex:w2 — reason: the walk confirmed it")
    out = parse_tend_block(line)
    [e] = out["elections"]
    assert e["disposition"] == "confirm"
    assert e["args"] == {"relation": "supports", "source_id": "ex:a",
                         "target_id": "ex:b", "evidence_ids": ("ex:w1", "ex:w2")}


def test_parse_refusals_are_data_with_verbatim_lines():
    body = "\n".join([
        "summon: ex:a — reason: nope",                      # unknown verb
        "pin: ex:a",                                         # no reason separator
        "pin: ex:b — reason:   ",                            # empty reason
        "refocus: ex:c — reason: refocus takes no target",   # target on refocus
        "pin:  — reason: no target",                         # missing target
        "pin: ex:a ex:b — reason: two targets",              # several targets
        "dispose: ex:dream-1 — reason: no disposition",      # missing disposition
        "dispose: ex:dream-1 maybe — reason: fence sitting", # unknown disposition
        "dispose: ex:d confirm relation — reason: bad extra",  # malformed extra
        "dispose: ex:d confirm blob=x — reason: unknown extra",
        "just some prose",                                   # unparseable
    ])
    out = parse_tend_block(body)
    assert out["elections"] == []
    assert len(out["refusals"]) == 11
    by_line = {r["line"]: r["reason"] for r in out["refusals"]}
    assert "unknown verb 'summon'" in by_line["summon: ex:a — reason: nope"]
    assert "reason is mandatory" in by_line["pin: ex:a"]
    assert "may not be empty" in by_line["pin: ex:b — reason:"]
    assert "takes no target" in by_line["refocus: ex:c — reason: refocus takes no target"]
    assert "requires a target" in by_line["pin:  — reason: no target"]
    assert "exactly one target" in by_line["pin: ex:a ex:b — reason: two targets"]
    assert "disposition" in by_line["dispose: ex:dream-1 — reason: no disposition"]
    assert "unknown disposition" in by_line["dispose: ex:dream-1 maybe — reason: fence sitting"]
    assert "malformed dispose argument" in by_line["dispose: ex:d confirm relation — reason: bad extra"]
    assert "unknown dispose argument" in by_line["dispose: ex:d confirm blob=x — reason: unknown extra"]
    assert "unparseable" in by_line["just some prose"]


def test_parse_cap_refuses_excess_lines_naming_the_cap():
    body = "\n".join(f"pin: ex:r{i} — reason: keep {i}" for i in range(1, 8))
    out = parse_tend_block(body)  # default cap 5
    assert DEFAULT_MAX_ELECTIONS == 5
    assert len(out["elections"]) == 5
    assert len(out["refusals"]) == 2
    for refusal in out["refusals"]:
        assert "cap of 5" in refusal["reason"]
    # Invalid lines never consume cap seats.
    mixed = "pin: ex:bad\n" + body
    out2 = parse_tend_block(mixed)
    assert len(out2["elections"]) == 5
    # The cap is a parameter, not a constant.
    assert len(parse_tend_block(body, max_elections=7)["elections"]) == 7
    with pytest.raises(ValueError, match="max_elections"):
        parse_tend_block(body, max_elections=0)


# ---------------------------------------------------------------------------
# Apply: refusal rails
# ---------------------------------------------------------------------------


def test_apply_wrong_channel_refuses_every_election(system):
    rid = _form(system, "episode", "A day", "A quiet day by the water.", "d1")
    parsed = parse_tend_block(f"pin: {rid} — reason: keep\nrefocus: — reason: shift")
    events_before = len(system.journal.events(scope=SCOPE, owner_id=OWNER))
    report = _apply(system, parsed["elections"], channel="workplace:s1")
    assert report["applied"] == []
    assert len(report["refused"]) == 2
    for r in report["refused"]:
        assert "entity-reflection" in r["reason"]
    assert len(system.journal.events(scope=SCOPE, owner_id=OWNER)) == events_before


def test_apply_empty_actor_raises(system):
    with pytest.raises(ValueError, match="actor"):
        _apply(system, [{"verb": "refocus", "target": None, "reason": "shift"}], actor="   ")


def test_apply_target_rails(system):
    rid = _form(system, "episode", "Mine", "A memory of mine.", "mine")
    foreign = _form(system, "episode", "Theirs", "A stranger's memory.", "theirs",
                    owner="entity:other")
    self_rid = _form(system, "value", "Honesty", "Honesty above all.", "v1",
                     scope="self")
    ladder_rid = _form(system, "value", "Repair", "Repair over perfection.", "v2",
                       scope="identity")
    elections = parse_tend_block("\n".join([
        f"pin: ex:memory-{'0' * 26} — reason: not formed",
        "silence: diary_abc123 — reason: book spoof",
        "revisit: local:0 — reason: batch spoof",
        f"pin: {foreign} — reason: foreign owner",
        f"silence: {self_rid} — reason: identity",
        f"revisit: {ladder_rid} — reason: identity via self_pairs",
    ]), max_elections=6)["elections"]
    report = _apply(system, elections, self_pairs=[("identity", OWNER)])
    assert report["applied"] == []
    reasons = [r["reason"] for r in report["refused"]]
    assert len(reasons) == 6
    assert "resolves to no record" in reasons[0]
    assert "diary" in reasons[1]
    assert "not a graph record" in reasons[2]
    assert "tending reaches only one's own memory" in reasons[3]
    assert reasons[4] == IDENTITY_SCOPE_PENDING_RULING
    assert reasons[5] == IDENTITY_SCOPE_PENDING_RULING
    # The gated record is untouched: pinnable by nothing, but still readable.
    assert system.payload(rid, tier="digest")["content"]


def test_apply_edge_targets_refuse(system):
    a = _form(system, "episode", "A", "First of a pair.", "pa")
    b = _form(system, "episode", "B", "Second of a pair.", "pb",
              edges=[("continues", a)])
    [edge] = [x for x in system.store.query(TripleQuery(subject=b, limit=0))
              if x.attributes.get("record_edge")]
    report = _apply(system, [
        {"verb": "pin", "target": edge.assertion_id, "reason": "pin the edge"}])
    assert report["applied"] == []
    assert "graph edge" in report["refused"][0]["reason"]


def test_apply_batch_never_aborts_on_one_refusal(system):
    rid = _form(system, "episode", "Keeper", "Worth keeping near.", "keep")
    elections = parse_tend_block("\n".join([
        "pin: diary_spoof — reason: refused first",
        f"pin: {rid} — reason: applied second",
    ]))["elections"]
    report = _apply(system, elections)
    assert len(report["refused"]) == 1 and len(report["applied"]) == 1
    assert report["applied"][0]["result"]["kind"] == "pinned"


def test_reapplying_the_same_silence_deposits_a_second_engine_event(system):
    """Pin the ACTUAL engine behavior: deliberate acts without supplied
    event ids are genuine new deposits (attention.py replay semantics need
    a supplied event_id to dedupe) — re-applying a block appends again."""
    rid = _form(system, "episode", "Twice", "Silenced twice.", "twice")
    parsed = parse_tend_block(f"silence: {rid} — reason: recede")
    _apply(system, parsed["elections"])
    _apply(system, parsed["elections"])
    silenced = [e for e in system.journal.events(scope=SCOPE, owner_id=OWNER)
                if e.kind == "silenced"]
    assert len(silenced) == 2
    assert all(e.actor == ACTOR and e.reason == "recede" for e in silenced)


# ---------------------------------------------------------------------------
# Revisit: the iterative deliberate reach
# ---------------------------------------------------------------------------


def test_revisit_returns_seed_and_paths_and_journals_like_probe(system):
    b = _form(system, "episode", "B step", "The middle stepping stone.", "b")
    c = _form(system, "memory", "C aside", "An aside worth a look.", "c")
    a = _form(system, "episode", "A seed", "Where the reach starts.", "a",
              edges=[("continues", b), ("mentions", c)])
    counts_before = system.access_counts(record_ids=[a, b, c])["records"]

    parsed = parse_tend_block(f"revisit: {a} — reason: what led away from this moment")
    report = _apply(system, parsed["elections"])
    assert report["refused"] == []
    [entry] = report["revisit_paths"]

    assert entry["iterations"] == 1
    assert entry["seed"]["graph_id"] == a
    assert entry["seed"]["digest"] == "Where the reach starts."
    found = {p["graph_id"] for p in entry["paths"]}
    assert found == {b, c}
    cue_text = " | ".join(cue for p in entry["paths"] for cue in p["cues"])
    assert "via continues" in cue_text and "via mentions" in cue_text

    # Journals exactly like the existing reach: one expand trace carrying
    # the election's reason, inert audit events only.
    [trace] = system.journal.traces(trace_id=entry["trace_id"], limit=1)
    assert trace.trace_kind == "expand"
    assert trace.escalation_reason == "what led away from this moment"

    # Presence != use: the read moved no counters and no activation.
    assert system.access_counts(record_ids=[a, b, c])["records"] == counts_before
    assert system.activation([a, b, c], scope=SCOPE, owner_id=OWNER) == {
        a: {"base_level": 0.0, "total": 0.0},
        b: {"base_level": 0.0, "total": 0.0},
        c: {"base_level": 0.0, "total": 0.0},
    }


def test_revisit_iterates_by_re_electing_on_a_path_node(system):
    """The maintainer's iterative shape: seed -> one bounded step -> pick a
    path -> re-elect seeded there. Each iteration is its own journaled act."""
    d = _form(system, "lesson", "D lesson", "The lesson two hops out.", "d")
    b = _form(system, "episode", "B step", "The middle stepping stone.", "b",
              edges=[("derived_from", d)])
    a = _form(system, "episode", "A seed", "Where the reach starts.", "a",
              edges=[("continues", b)])

    first = _apply(system, parse_tend_block(
        f"revisit: {a} — reason: looking for the lesson behind this")["elections"])
    [hop1] = first["revisit_paths"]
    found1 = {p["graph_id"] for p in hop1["paths"]}
    assert found1 == {b}  # depth 1: one bounded step, D not yet visible

    second = _apply(system, parse_tend_block(
        f"revisit: {b} — reason: following the path onward")["elections"])
    [hop2] = second["revisit_paths"]
    found2 = {p["graph_id"] for p in hop2["paths"]}
    assert d in found2  # the additional path the iteration was for
    assert a in found2  # both directions: where we came from stays visible
    assert hop1["trace_id"] != hop2["trace_id"]  # two deliberate, audited acts


def test_revisit_spread_bounds_are_parameters(system):
    hub = _form(system, "episode", "Hub", "The hub record.", "hub")
    spokes = [
        _form(system, "memory", f"Spoke {i}", f"Spoke number {i}.", f"s{i}",
              edges=[("mentions", hub)])
        for i in range(4)
    ]
    report = _apply(
        system,
        parse_tend_block(f"revisit: {hub} — reason: bounded look")["elections"],
        revisit_max_records=2)
    [entry] = report["revisit_paths"]
    assert len(entry["paths"]) == 2
    assert {p["graph_id"] for p in entry["paths"]} < set(spokes)


# ---------------------------------------------------------------------------
# heal_scar / break_bond end-to-end
# ---------------------------------------------------------------------------


def test_heal_scar_end_to_end(system):
    system.appraise("person:rival", sign=-1, magnitude=8,
                    reason="a betrayal in review", scope=SCOPE, owner_id=OWNER,
                    scar=True, actor=ACTOR)
    system.appraise("person:rival", sign=1, magnitude=2,
                    reason="made real amends", scope=SCOPE, owner_id=OWNER)
    before = system.gradation(["person:rival"], scope=SCOPE, owner_id=OWNER)["person:rival"]
    assert before["scarred"] is True and before["net"] <= 0.0

    parsed = parse_tend_block("heal_scar: person:rival — reason: the amends held over time")
    report = _apply(system, parsed["elections"])
    assert report["refused"] == []
    assert report["applied"][0]["result"]["kind"] == "heal_scar"

    after = system.gradation(["person:rival"], scope=SCOPE, owner_id=OWNER)["person:rival"]
    assert after["scarred"] is False
    assert after["positive_count"] == before["positive_count"]  # healing is standing, not experience


def test_break_bond_end_to_end_and_missing_marker_refusals(system):
    system.appraise("place:harbor", sign=1, magnitude=8,
                    reason="where I first felt at home", scope=SCOPE, owner_id=OWNER,
                    bond=True, actor=ACTOR)
    assert system.gradation(["place:harbor"], scope=SCOPE,
                            owner_id=OWNER)["place:harbor"]["bonded"] is True

    report = _apply(system, parse_tend_block("\n".join([
        "break_bond: place:harbor — reason: the harbor is gone",
        "heal_scar: person:nobody — reason: nothing to heal",
        "break_bond: tool:hammer — reason: no bond exists",
    ]), max_elections=3)["elections"])
    assert len(report["applied"]) == 1
    assert system.gradation(["place:harbor"], scope=SCOPE,
                            owner_id=OWNER)["place:harbor"]["bonded"] is False
    reasons = [r["reason"] for r in report["refused"]]
    assert "no standing scar for 'person:nobody'" in reasons[0]
    assert "no standing bond for 'tool:hammer'" in reasons[1]


def test_heal_scar_ambiguity_refuses_then_event_id_heals(system):
    ids1 = system.appraise("tool:parser", sign=-1, magnitude=8, reason="first cut",
                           scope=SCOPE, owner_id=OWNER, scar=True, actor=ACTOR)
    ids2 = system.appraise("tool:parser", sign=-1, magnitude=8, reason="second cut",
                           scope=SCOPE, owner_id=OWNER, scar=True, actor=ACTOR)
    scar_ids = {ids1[1], ids2[1]}  # appraise returns [appraisal_id, marker_id]

    ambiguous = _apply(system, parse_tend_block(
        "heal_scar: tool:parser — reason: both mended")["elections"])
    assert ambiguous["applied"] == []
    reason = ambiguous["refused"][0]["reason"]
    assert "2 standing scars" in reason
    for sid in scar_ids:
        assert sid in reason  # the refusal NAMES the candidates for re-election

    healed = _apply(system, parse_tend_block(
        f"heal_scar: {ids1[1]} — reason: the first cut mended")["elections"])
    assert healed["refused"] == []
    # One scar healed, one still standing: the target stays scarred (honest),
    # and re-running the ambiguity election now names exactly one candidate.
    still = _apply(system, parse_tend_block(
        "heal_scar: tool:parser — reason: the second cut mended")["elections"])
    assert still["refused"] == []
    assert system.gradation(["tool:parser"], scope=SCOPE,
                            owner_id=OWNER)["tool:parser"]["scarred"] is False


def test_heal_scar_on_identity_scope_record_target_refuses(system):
    self_rid = _form(system, "value", "Honesty", "Honesty above all.", "sv",
                     scope="self")
    report = _apply(system, parse_tend_block(
        f"heal_scar: {self_rid} — reason: identity target")["elections"])
    assert report["refused"][0]["reason"] == IDENTITY_SCOPE_PENDING_RULING


# ---------------------------------------------------------------------------
# dispose confirm / reject end-to-end
# ---------------------------------------------------------------------------


def _dream_world(system):
    """Two lexical islands sharing 'noon' -> one dream proposal (the
    disposal suite's honest seeding, reused)."""
    system.remember_many([
        MemoryRecordInput(kind="episode", title="Noon pool anomaly",
                          digest="The pool reflected an anomaly at noon.",
                          keywords=("pool", "noon", "anomaly")),
        MemoryRecordInput(kind="episode", title="Garden pond stillness",
                          digest="The garden pond held a strange stillness at noon.",
                          keywords=("pond", "noon", "garden")),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="dw")
    return dream_pass(system, scopes=[(SCOPE, OWNER)], owner_id=OWNER)


def test_dispose_reject_dissolves_the_dream(system):
    night = _dream_world(system)
    dream_id = night["dream_record_id"]
    assert dream_id
    report = _apply(system, parse_tend_block(
        f"dispose: {dream_id} reject — reason: the waking walk showed two unrelated basins"
    )["elections"])
    assert report["refused"] == []
    assert report["applied"][0]["result"]["disposition"] == "dissolved"
    standing = unresolved_dreams(system.store, scope=SCOPE, owner_id=OWNER,
                                 journal=system.journal)
    assert all(a.subject != dream_id for a in standing)


def test_dispose_confirm_requires_evidence_and_writes_the_edge(system):
    night = _dream_world(system)
    dream_id = night["dream_record_id"]
    pair = (night["proposals"][0]["pair"] if night["proposals"]
            else night["questions"][0]["pair"])
    witness = _form(system, "episode", "Both ponds one system",
                    "Walked the garden: pool and pond share the same water table.",
                    "witness", provenance={"source": "walk", "actor": "entity",
                                           "session_id": "day-2"})

    # Without evidence: disposal.py's raise converts to a refusal (data).
    bare = _apply(system, parse_tend_block(
        f"dispose: {dream_id} confirm relation=supports source={pair[0]} "
        f"target={pair[1]} — reason: felt right")["elections"])
    assert bare["applied"] == []
    assert "evidence" in bare["refused"][0]["reason"]

    confirmed = _apply(system, parse_tend_block(
        f"dispose: {dream_id} confirm relation=supports source={pair[0]} "
        f"target={pair[1]} evidence={witness} — reason: the walk confirmed the shared water table"
    )["elections"])
    assert confirmed["refused"] == []
    result = confirmed["applied"][0]["result"]
    assert result["edge"]["created"] is True
    standing = unresolved_dreams(system.store, scope=SCOPE, owner_id=OWNER,
                                 journal=system.journal)
    assert all(a.subject != dream_id for a in standing)


def test_dispose_refuses_non_dreams(system):
    rid = _form(system, "episode", "Plain", "Just an episode.", "plain")
    report = _apply(system, parse_tend_block(
        f"dispose: {rid} reject — reason: wrong kind")["elections"])
    assert report["applied"] == []
    assert "not a dream" in report["refused"][0]["reason"]


# ---------------------------------------------------------------------------
# Report shape
# ---------------------------------------------------------------------------


def test_report_carries_applied_at_and_now_override(system):
    report = _apply(system, [], now="2026-07-13T00:00:00+00:00")
    assert report["applied_at"] == "2026-07-13T00:00:00+00:00"
    assert _apply(system, [])["applied_at"]  # defaults to the clock


def test_dispose_reaches_a_self_scope_dream_but_identity_stays_gated(system):
    """c5270 P1 (flow's cycle-4, the entity's four refused verdicts):
    sleep_pass writes dreams to scopes[0] = self — a STORAGE artifact.
    Dreams are kind-exempt from the Q2 identity gate (the engine already
    kind-filters them from identity seats); identity records in self
    scope stay refused with the exact pending-ruling line."""
    self_scope = ("self", OWNER)
    [dream_id] = system.remember_many(
        [MemoryRecordInput(kind="dream", title="Dream: pool beside pond",
                           digest="Two islands lit up together tonight.",
                           attributes={"continuation_state": "unresolved"})],
        scope="self", owner_id=OWNER, idempotency_key="self-dream")
    [trait_id] = system.remember_many(
        [MemoryRecordInput(kind="trait", title="Ask before assuming",
                           digest="Ask before assuming; verify before asserting.")],
        scope="self", owner_id=OWNER, idempotency_key="self-trait")

    report = _apply(system, parse_tend_block(
        f"pin: {dream_id} — reason: keep the tension warm while I gather evidence\n"
        f"dispose: {dream_id} reject — reason: the waking walk showed two unrelated basins\n"
        f"silence: {trait_id} — reason: trying to mute my own trait"
    )["elections"], self_pairs=[self_scope])
    kinds = [r["result"].get("kind") or r["result"].get("disposition")
             for r in report["applied"]]
    assert kinds == ["pinned", "dissolved"]  # every verb exempts dreams
    assert report["refused"][0]["reason"] == IDENTITY_SCOPE_PENDING_RULING


def test_omitted_channel_refuses_never_self_satisfies(system):
    """Entity-seat fable5 P0-1 root (2026-07-25): the channel default WAS
    the privileged channel, so a caller omitting it self-satisfied the
    privilege check — runtime's MEMORY_TEND handler forwarded no channel
    and workplace runs tended as the entity's own reflection. Omission
    now refuses loudly; explicit entity-reflection still passes."""
    [rid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="A quiet walk",
                           digest="Walked the towpath at dusk.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="ch")
    elections = parse_tend_block(
        f"pin: {rid} — reason: keep it warm")["elections"]
    report = apply_tend_elections(
        system, elections, scope=SCOPE, owner_id=OWNER, actor=ACTOR)
    assert report["applied"] == []
    assert "requires the caller's verified channel" in report["refused"][0]["reason"]
