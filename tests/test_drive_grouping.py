"""Drive grouping (laurent room#277: "During the sleep, similar questions
should be grouped; same for problems; same for interests etc; the more
there are the higher the signal they get to be treated").

Pinned here:
- drive_groups() is pure, deterministic, family-blind (the callers keep
  families separate), and returns clusters >= 2 only;
- templated titles never cluster on scaffold (the per-corpus boilerplate
  screen — 84 questions titled 'Diary entry (question) — ...' must group
  on CONTENT or not at all);
- grouping NEVER discharges: members stay standing after a group offer;
- group offers mint in the ruled candidate shape with their OWN cap pool
  (theme offers cannot starve them);
- the day surface folds cluster members into ONE boosted entry — size is
  the signal.
"""

from __future__ import annotations

from typing import Any

from abstractmemory import (
    GROUP_OFFER_FLOOR,
    alive_drives,
    drive_groups,
    mine_candidates_pass,
    open_questions,
)
from abstractmemory.records import MemoryRecordInput
from abstractmemory.store import TripleQuery

SCOPE = "life"
OWNER = "entity:test"
SCOPES = [(SCOPE, OWNER)]


def _diary(system, key: str, diary_type: str, title: str, text: str,
           session: str = "s-1", **attrs: Any) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="diary", title=title, digest=text,
                           attributes={"diary_type": diary_type, **attrs},
                           provenance={"source": "owner-direct",
                                       "session_id": session})],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _attrs_of(system, gid: str):
    for row in system._store.query(TripleQuery(subject=gid, limit=0)):
        attrs = row.attributes if isinstance(row.attributes, dict) else {}
        if attrs.get("record_kind"):
            return attrs
    return {}


# ---------------------------------------------------------------------------
# The pure fold
# ---------------------------------------------------------------------------


def test_similar_drives_cluster_and_singletons_stay_out() -> None:
    items = [
        {"record_id": "q1", "title": "why does the connection pool saturate at noon"},
        {"record_id": "q2", "title": "what saturates the connection pool under load"},
        {"record_id": "q3", "title": "connection pool saturation keeps returning"},
        {"record_id": "q4", "title": "how do tidal turbines anchor in sand"},
    ]
    groups = drive_groups(items)
    assert len(groups) == 1
    g = groups[0]
    assert set(g["members"]) == {"q1", "q2", "q3"}
    assert g["size"] == 3
    assert g["exemplar"] == "q1"
    assert any(t in ("connection", "pool") for t in g["shared_terms"])

    assert drive_groups(items) == groups, "deterministic"
    assert drive_groups([items[3]]) == []


def test_templated_titles_never_cluster_on_scaffold() -> None:
    """The live-Ephemeral trap: 84 questions all titled 'Diary entry
    (question) — <date>' share every template word — the boilerplate
    screen must force clustering onto CONTENT."""
    items = []
    for i in range(30):
        items.append({"record_id": f"q{i}",
                      "title": f"Diary entry (question) — 2026-07-{i+1:02d}",
                      "text": f"unique subject number {i}: "
                              + ["harbor tides", "glass kilns", "moth wings",
                                 "peat bogs", "star charts", "clock springs",
                                 "ink recipes", "root grafts", "salt pans",
                                 "wind harps"][i % 10] + f" variant {i}"})
    groups = drive_groups(items)
    for g in groups:
        assert g["size"] <= 4, (
            "template scaffold must never fuse the whole desk into one group")


# ---------------------------------------------------------------------------
# Sleep half: group offers
# ---------------------------------------------------------------------------


def test_group_offer_mints_in_ruled_shape_and_never_discharges(system, stack) -> None:
    store, journal = stack
    ids = []
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        ids.append(_diary(system, f"g-q{i}", "question",
                          f"why does the kiln glaze crack, telling {i}",
                          f"the kiln glaze cracking question again {i}",
                          session=session))
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    groups = [g for g in result["drive_groups"] if g["family"] == "question"]
    assert groups and groups[0]["size"] == 3
    offers = [c for c in result["created"]
              if c["proposed_kind"] == "question_group" and c["created"]]
    assert offers, "a 3-cluster earns a desk offer"
    attrs = _attrs_of(system, offers[0]["candidate_id"])
    assert attrs["record_kind"] == "summary"
    assert attrs["maintenance_candidate"] is True
    assert attrs["review_required"] is True
    assert attrs["group_size"] == 3
    assert set(attrs["source_ids"]) == set(ids)
    # NEVER a discharge: all three questions still stand open.
    still_open = open_questions(store, scope=SCOPE, owner_id=OWNER, journal=journal)
    assert {a.subject for a in still_open} >= set(ids)


def test_pairs_report_but_stay_desk_quiet(system) -> None:
    for i in range(2):
        _diary(system, f"p-q{i}", "question",
               f"where do the moth wings overwinter, take {i}",
               f"moth wings overwintering question {i}", session=f"s-{i}")
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    pairs = [g for g in result["drive_groups"] if g["size"] == 2]
    assert pairs, "pairs report (the day surface boosts on them)"
    assert GROUP_OFFER_FLOOR == 3
    assert not [c for c in result["created"]
                if c["proposed_kind"] == "question_group"], (
        "a pair is desk-quiet — the offer floor is 3")


def test_group_offers_have_their_own_cap_pool(system) -> None:
    """Theme offers must not starve group offers (the ruling makes
    grouping the priority signal; groups mint last in order)."""
    # A resolved cross-session tension (mints a lesson, eats the theme pool)
    q = _diary(system, "cap-q", "problem", "the antenna wire keeps shorting",
               "antenna wire shorting in rain", session="s-a")
    _diary(system, "cap-a", "note", "ground fix for the antenna wire",
           "tightening the ground fixed the antenna wire", session="s-b",
           resolves=q)
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Antenna wire shorting at the mast",
                           digest="Antenna wire shorting at the mast",
                           keywords=("antenna", "wire"),
                           provenance={"session_id": "s-c"})],
        scope=SCOPE, owner_id=OWNER, idempotency_key="cap-e")
    # And a 3-cluster of open questions.
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _diary(system, f"cap-g{i}", "question",
               f"why does the kiln glaze crack, telling {i}",
               f"kiln glaze cracking question {i}", session=session)
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER,
                                  max_candidates=1)
    minted_kinds = {c["proposed_kind"] for c in result["created"] if c["created"]}
    assert "lesson" in minted_kinds
    assert "question_group" in minted_kinds, (
        "the group pool is separate — a lesson mint must not starve it")


def test_growing_cluster_keeps_one_standing_offer(system, stack) -> None:
    """Growth mints a FRESH offer with the honest size and SUPERSEDES the
    stale one (adversary F3: frozen digests stated stale sizes as fact) —
    exactly one STANDING offer per pressure at all times; an unchanged
    cluster re-mints nothing."""
    from abstractmemory import cognition_health

    store, journal = stack
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _diary(system, f"gr-q{i}", "question",
               f"why does the kiln glaze crack, telling {i}",
               f"kiln glaze cracking question {i}", session=session)
    first = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert any(c["proposed_kind"] == "question_group" and c["created"]
               for c in first["created"])

    # Unchanged cluster: nothing re-mints, the standing offer stands.
    stable = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert not [c for c in stable["created"]
                if c["proposed_kind"] == "question_group" and c["created"]]
    assert any("already minted" in s.get("reason", "") for s in stable["skipped"])

    # Growth: fresh honest offer, stale one superseded — one standing.
    _diary(system, "gr-q9", "question",
           "why does the kiln glaze crack, telling nine",
           "kiln glaze cracking question nine", session="s-9")
    grown = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    fresh = [c for c in grown["created"]
             if c["proposed_kind"] == "question_group" and c["created"]]
    assert fresh, "genuine growth mints the honest-size offer"
    assert _attrs_of(system, fresh[0]["candidate_id"])["group_size"] == 4
    health = cognition_health(store, journal, scopes=SCOPES)
    assert health["candidates"]["by_proposed_kind"].get("question_group", 0) == 1, (
        "the stale 3-offer is superseded — one standing offer per pressure")


# ---------------------------------------------------------------------------
# Day half: alive_drives folds groups
# ---------------------------------------------------------------------------


def test_small_templated_family_never_fuses_on_scaffold() -> None:
    """Adversary F1 (P0): five UNRELATED questions under the live title
    template fused into one desk entry on ['diary','entry','question'].
    The grouping screen must catch template scaffold at small n."""
    items = [
        {"record_id": f"q{i}",
         "title": f"Diary entry (question) — 2026-07-{i+1:02d}",
         "text": ["harbor tides shifting", "kiln glaze cracking",
                  "moth wings overwintering", "peat bog acidity",
                  "star chart drift"][i]}
        for i in range(5)
    ]
    assert drive_groups(items) == [], (
        "template scaffold must never fuse unrelated drives")


def test_dominant_theme_never_dissolves() -> None:
    """Adversary F2 (P0): the ruling's own target case — mass
    near-duplication — must group at EVERY size; the old df screen
    erased clusters larger than n//8 (11+ at n=84)."""
    import itertools

    items = []
    for i in range(30):  # 30 tellings of one pressure
        items.append({"record_id": f"k{i}",
                      "title": f"why does the kiln glaze crack, telling {i}",
                      "text": f"kiln glaze cracking again, night {i}"})
    # 54 GENUINELY distinct singletons -> n=84, the live board (each gets
    # unique word pairs — a fixture template here would itself cluster).
    vocab = ["harbor", "mothwing", "peatbog", "starchart", "clockwork",
             "inkstone", "rootgraft", "saltpan", "windharp", "lanterns",
             "brasscog", "fernseed"]
    pairs_iter = itertools.combinations(vocab, 2)
    for i in range(54):
        w1, w2 = next(pairs_iter)
        items.append({"record_id": f"s{i}", "title": f"about {w1}{i}",
                      "text": f"{w1}{i} beside {w2}{i}"})
    groups = drive_groups(items)
    kiln = [g for g in groups if set(g["members"]) & {f"k{i}" for i in range(30)}]
    assert kiln, "the 30-telling pressure must group — size IS the signal"
    assert set(kiln[0]["members"]) == {f"k{i}" for i in range(30)}


def test_merge_supersedes_stale_offers_one_per_pressure(system, stack) -> None:
    """Adversary F3: cluster merge left three frozen standing offers for
    one pressure — the new offer supersedes overlapping same-family
    offers (machine retiring machine rows, never his drives)."""
    from abstractmemory import cognition_health

    store, journal = stack
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _diary(system, f"m1-q{i}", "question",
               f"why does the kiln glaze crack, telling {i}",
               f"kiln glaze cracking question {i}", session=session)
    first = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert any(c["proposed_kind"] == "question_group" and c["created"]
               for c in first["created"])
    # A second distinct cluster forms, then a BRIDGE question merges them.
    for i, session in enumerate(("s-4", "s-5", "s-6")):
        _diary(system, f"m2-q{i}", "question",
               f"where does the glaze pigment fade, telling {i}",
               f"glaze pigment fading question {i}", session=session)
    mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    _diary(system, "m3-bridge", "question",
           "kiln glaze crack and glaze pigment fade — one firing problem?",
           "the kiln glaze cracking and the glaze pigment fading look like "
           "one firing problem", session="s-7")
    third = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER,
                                 max_candidates=4)
    merged = [c for c in third["created"]
              if c["proposed_kind"] == "question_group" and c["created"]]
    assert merged, "the merged cluster mints its offer"
    # Exactly ONE question-group offer stands pending afterwards.
    health = cognition_health(store, journal, scopes=SCOPES)
    assert health["candidates"]["by_proposed_kind"].get("question_group", 0) == 1, (
        "stale offers must be superseded — one standing offer per pressure")


def test_explored_interest_never_in_a_group(system) -> None:
    """Adversary F4: the inline interest fold dropped the explores=
    discharge — an EXPLORED interest became a group's exemplar."""
    ids = []
    for i in range(3):
        [gid] = system.remember_many(
            [MemoryRecordInput(kind="interest", title=f"interest: tidal energy {i}",
                               digest=f"interest: tidal energy fascination {i}")],
            scope=SCOPE, owner_id=OWNER, idempotency_key=f"int-{i}")
        ids.append(gid)
    # He EXPLORED the first one.
    system.remember_many(
        [MemoryRecordInput(kind="episode", title="Read about tidal energy all day",
                           digest="explored the tidal interest",
                           attributes={"explores": ids[0]})],
        scope=SCOPE, owner_id=OWNER, idempotency_key="int-exp")
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    for g in result["drive_groups"]:
        if g["family"] == "interest":
            assert ids[0] not in g["members"], (
                "an explored interest is not an open drive — fold agreement")


def test_exemplar_always_in_its_offers_sources(system) -> None:
    """Adversary F7: the newest-first source cap dropped the exemplar
    from its own offer on clusters >= 7."""
    for i in range(8):
        _diary(system, f"x-q{i}", "question",
               f"why does the kiln glaze crack, telling {i}",
               f"kiln glaze cracking question {i}", session=f"s-{i}")
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    offers = [c for c in result["created"]
              if c["proposed_kind"] == "question_group" and c["created"]]
    assert offers
    attrs = _attrs_of(system, offers[0]["candidate_id"])
    assert attrs["group_exemplar"] in attrs["source_ids"], (
        "the exemplar anchors the fingerprint — it must be in the sources")


def test_duplicate_inputs_never_mint_phantom_pairs() -> None:
    """Adversary F8: a doubled record_id minted a self-pair cluster."""
    item = {"record_id": "i1", "title": "interest: tidal energy",
            "text": "tidal energy fascination"}
    assert drive_groups([item, item]) == []


def test_dormant_offer_grade_cluster_still_surges(system, stack) -> None:
    """Runtime's 277 pathway ask 2: a fully-dormant 17-question cluster
    could never surge (no alive member, no entry) — mass itself presses:
    offer-grade clusters surface through their exemplar with
    size-derived aliveness even when every member is dormant."""
    _, journal = stack
    for i in range(5):
        _diary(system, f"dz-q{i}", "question",
               f"why does the kiln glaze crack, telling {i}",
               f"kiln glaze cracking question {i}", session=f"s-{i}")
    # Age every drive out of the recency window with machine-free churn:
    # form enough distinct his-records to push the cluster past the
    # binding window.
    window = int(getattr(system._attention_config, "drive_window_limit", 256))
    for i in range(window + 8):
        system.remember_many(
            [MemoryRecordInput(kind="episode", title=f"day noise {i}",
                               digest=f"unrelated moment {i}")],
            scope=SCOPE, owner_id=OWNER, idempotency_key=f"dz-n{i}")
    drives = alive_drives(system, scopes=SCOPES, k=10)
    grouped = [d for d in drives if d.get("group_size") == 5]
    assert grouped, "an offer-grade dormant cluster must still press by mass"
    assert grouped[0]["alive_via"] == "group_size"
    assert grouped[0]["group_alive_members"] == []
    # Pairs/singletons keep the emergent quiet-desk contract: no
    # size-derived entries below the offer floor.
    assert all(d.get("group_size") in (None, 5) for d in drives)


def test_drive_pressure_serves_the_group_structure(system, stack) -> None:
    """The gate/console fold key (gateway c290): drive_pressure gains
    "groups" — structure beside the counts, a VIEW never a new drive
    (counts stay exact and unchanged)."""
    from abstractmemory import drive_pressure

    store, journal = stack
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _diary(system, f"dp-q{i}", "question",
               f"why does the kiln glaze crack, telling {i}",
               f"kiln glaze cracking question {i}", session=session)
    pressure = drive_pressure(store, journal, scopes=SCOPES)
    assert pressure["open_questions"] == 3, "counts unchanged — a group is a view"
    groups = pressure["groups"]
    assert groups and groups[0]["family"] == "question"
    assert groups[0]["size"] == 3
    assert set(groups[0].keys()) >= {"family", "members", "size", "exemplar",
                                     "shared_terms"}


def test_alive_drives_folds_clusters_into_one_boosted_entry(system) -> None:
    ids = []
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        ids.append(_diary(system, f"ad-q{i}", "question",
                          f"why does the kiln glaze crack, telling {i}",
                          f"kiln glaze cracking question {i}", session=session))
    _diary(system, "ad-solo", "question", "how do tidal turbines anchor in sand",
           "tidal turbine anchoring question", session="s-4")
    drives = alive_drives(system, scopes=SCOPES, k=10)
    grouped = [d for d in drives if d.get("group_size")]
    assert grouped and grouped[0]["group_size"] == 3
    assert set(grouped[0]["group_members"]) == set(ids)
    kiln_entries = [d for d in drives if d["record_id"] in set(ids)]
    assert len(kiln_entries) == 1, (
        "N similar drives surface as ONE entry, never N diluting rows")
    solo = [d for d in drives if "tidal" in d["title"]]
    assert solo and "group_size" not in solo[0]
    # Size is the signal: the 3-cluster outranks the singleton born later.
    assert drives[0]["group_size"] == 3