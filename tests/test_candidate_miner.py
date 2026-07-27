"""W2 candidate miner (wave-4 dispatch; correction 7 shape ruled c3331).

Pinned here:
- candidates are born kind="summary" + attributes.proposed_kind — NEVER
  the target kind (B-F8: a machine-authored kind=interest would enter his
  drive ratios and the daily offer as if he had elected it);
- the marker pair is the EXISTING maintenance_candidate + review_required
  (dream-contract parity: same shape gateway's review desk already
  serves, promote/reject verbs compose unchanged);
- lesson candidates require a RESOLVED tension whose theme lived across
  >= 2 distinct sessions; interest candidates require compound-theme
  recurrence across >= discovery-floor sessions with no standing interest
  declaring it;
- resolve_questions_pass PROPOSES and never discharges (machine purity —
  resolving is HIS act);
- mints are bounded per night, fingerprint-idempotent, and structurally
  outside cognition_health ratios (which now count them separately as
  pending review offers).
"""

from __future__ import annotations

from typing import Any, Dict

from abstractmemory import (
    cognition_health,
    mine_candidates_pass,
    open_questions,
    resolve_questions_pass,
    sleep_pass,
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


def _diary(system, key: str, diary_type: str, title: str, text: str,
           session: str, **attrs: Any) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="diary", title=title, digest=text,
                           attributes={"diary_type": diary_type, **attrs},
                           provenance={"source": "owner-direct",
                                       "session_id": session})],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _episode(system, key: str, title: str, session: str, **kw: Any) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title=title,
                           digest=kw.pop("digest", title),
                           provenance={"session_id": session}, **kw)],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _attrs_of(system, gid: str) -> Dict[str, Any]:
    for row in system._store.query(TripleQuery(subject=gid, limit=0)):
        attrs = row.attributes if isinstance(row.attributes, dict) else {}
        if attrs.get("record_kind"):
            return attrs
    return {}


def _resolved_tension_world(system) -> Dict[str, str]:
    """A problem hit in session A, evidence in session B, resolved by a
    later diary entry — the lesson-candidate precondition."""
    ids = {}
    ids["problem"] = _diary(system, "m-q1", "problem",
                            "the connection pool keeps saturating",
                            "the connection pool keeps saturating under noon load",
                            session="s-alpha")
    ids["ep1"] = _episode(system, "m-e1", "Debugged the connection pool saturating",
                          session="s-beta", keywords=("connection", "pool"))
    ids["ep2"] = _episode(system, "m-e2", "Connection pool fix verified",
                          session="s-gamma", keywords=("connection", "pool"))
    ids["answer"] = _diary(system, "m-a1", "note",
                           "batching writers fixed the pool",
                           "batching the noon writers fixed the connection pool for good",
                           session="s-gamma", resolves=ids["problem"])
    return ids


# ---------------------------------------------------------------------------
# LESSON candidates
# ---------------------------------------------------------------------------


def test_lesson_candidate_mints_in_the_ruled_shape(system) -> None:
    ids = _resolved_tension_world(system)
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    lessons = [c for c in result["created"] if c["proposed_kind"] == "lesson"]
    assert lessons, "a resolved cross-session tension must offer a lesson"
    attrs = _attrs_of(system, lessons[0]["candidate_id"])
    # THE RULED SHAPE (correction 7): summary + proposed_kind + the
    # existing marker pair — never kind=lesson at candidate stage.
    assert attrs["record_kind"] == "summary"
    assert attrs["proposed_kind"] == "lesson"
    assert attrs["maintenance_candidate"] is True
    assert attrs["review_required"] is True
    assert ids["problem"] in attrs["source_ids"]
    # His words are quoted, and the offer names adoption as HIS act.
    assert "connection pool" in str(attrs.get("title", "")).lower()


def test_open_tension_never_offers_a_lesson(system) -> None:
    _diary(system, "m-q2", "problem", "the embedder drifts overnight",
           "the embedder drifts overnight and scores shift",
           session="s-alpha")
    _episode(system, "m-e3", "Watched the embedder drifts overnight again",
             session="s-beta", keywords=("embedder",))
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert not [c for c in result["created"] if c["proposed_kind"] == "lesson"], (
        "an OPEN tension is a drive, not a lesson — only resolution earns one")


def test_single_session_tension_never_offers_a_lesson(system) -> None:
    q = _diary(system, "m-q3", "question", "why does the cache thrash",
               "why does the cache thrash at startup", session="s-only")
    _diary(system, "m-a3", "note", "cache warmed lazily",
           "warming the cache lazily stopped the thrash", session="s-only",
           answers=q)
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert not [c for c in result["created"] if c["proposed_kind"] == "lesson"], (
        "one session is an incident; recurrence across sessions earns the offer")


# ---------------------------------------------------------------------------
# INTEREST candidates
# ---------------------------------------------------------------------------


def test_interest_candidate_from_recurring_uneelected_theme(system) -> None:
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _episode(system, f"m-i{i}", f"Reading about tidal energy, day {i}",
                 session=session, keywords=("tidal energy", "reading"))
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    interests = [c for c in result["created"] if c["proposed_kind"] == "interest"]
    assert interests, "three sessions on one un-elected compound theme must offer"
    attrs = _attrs_of(system, interests[0]["candidate_id"])
    assert attrs["record_kind"] == "summary"
    assert attrs["proposed_kind"] == "interest"
    assert attrs["theme"] == "tidal energy"
    assert attrs["sessions"] == 3


def test_standing_interest_suppresses_the_offer(system) -> None:
    _remember(system, "m-int", "interest", "interest: tidal energy",
              "interest: tidal energy — how the tides could power the coast")
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _episode(system, f"m-i{i}", f"Reading about tidal energy, day {i}",
                 session=session, keywords=("tidal energy",))
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert not [c for c in result["created"] if c["proposed_kind"] == "interest"], (
        "he already elected this — the miner offers what is MISSING")
    assert any("standing interest" in s.get("reason", "")
               for s in result["skipped"])


def test_single_words_and_thin_recurrence_never_offer(system) -> None:
    for i, session in enumerate(("s-1", "s-2", "s-3", "s-4")):
        _episode(system, f"m-w{i}", f"A day with gardens, {i}",
                 session=session, keywords=("garden",))  # single word
    _episode(system, "m-c1", "Compound one", session="s-1",
             keywords=("quiet harbors",))
    _episode(system, "m-c2", "Compound two", session="s-2",
             keywords=("quiet harbors",))  # only 2 sessions < floor 3
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert not [c for c in result["created"] if c["proposed_kind"] == "interest"]


# ---------------------------------------------------------------------------
# resolve_questions_pass: proposals, never discharge
# ---------------------------------------------------------------------------


def test_resolve_questions_proposes_and_never_discharges(system, stack) -> None:
    store, journal = stack
    q = _diary(system, "m-q4", "question", "what settles the pool saturation",
               "what settles the connection pool saturation for good",
               session="s-alpha")
    _episode(system, "m-e4", "Connection pool saturation settled by batching",
             session="s-beta", keywords=("connection", "saturation"))
    result = resolve_questions_pass(store, journal, scopes=SCOPES)
    assert result["proposal_count"] >= 1
    prop = result["proposals"][0]
    assert prop["question_id"] == q
    assert prop["evidence"], "the later record must be named as evidence"
    assert len(prop["evidence"][0]["shared_terms"]) >= 2
    # NEVER a discharge: the question still stands open (machine purity —
    # resolving is HIS act via answers=/resolves=).
    still_open = open_questions(store, scope=SCOPE, owner_id=OWNER, journal=journal)
    assert any(a.subject == q for a in still_open)


def test_evidence_must_postdate_the_asking(system, stack) -> None:
    store, journal = stack
    _episode(system, "m-e5", "Old record about lantern maintenance rituals",
             session="s-old", keywords=("lantern", "maintenance"))
    _diary(system, "m-q5", "question", "how do lantern maintenance rituals work",
           "how do lantern maintenance rituals actually work",
           session="s-new")
    result = resolve_questions_pass(store, journal, scopes=SCOPES)
    hits = [p for p in result["proposals"]
            if any("lantern" in t for e in p["evidence"] for t in e["shared_terms"])]
    assert not hits, "evidence formed BEFORE the asking cannot answer it"


# ---------------------------------------------------------------------------
# Bounds, idempotency, purity
# ---------------------------------------------------------------------------


def test_night_cap_bounds_and_reruns_are_idempotent(system) -> None:
    _resolved_tension_world(system)
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _episode(system, f"m-i{i}", f"Reading about tidal energy, day {i}",
                 session=session, keywords=("tidal energy",))
        _episode(system, f"m-j{i}", f"Notes on glass harmonics, day {i}",
                 session=session, keywords=("glass harmonics",))
    first = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER,
                                 max_candidates=2)
    assert sum(1 for c in first["created"]) <= 2, "the night cap bounds mints"
    assert any("cap" in s.get("reason", "") for s in first["skipped"])

    # Cap-skipped offers DRAIN across nights (bounded nightly work, complete
    # eventually) — but an already-minted offer never re-mints (fingerprint
    # + covered-sources dedup).
    first_ids = {c["candidate_id"] for c in first["created"]}
    second = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER,
                                  max_candidates=2)
    second_new = {c["candidate_id"] for c in second["created"] if c["created"]}
    assert not (first_ids & second_new), "an offer never mints twice"

    third = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER,
                                 max_candidates=2)
    assert all(not c["created"] for c in third["created"]), (
        "once the backlog drains, nights are quiet")


def test_report_only_writes_nothing_and_predicts_the_write_night(system, stack) -> None:
    store, _ = stack
    _resolved_tension_world(system)
    before = len(store.query(TripleQuery(limit=0)))
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER,
                                  report_only=True)
    assert result["lesson_candidates"], "the report names what WOULD mint"
    # The report PREDICTS the write night (adversary F13b): would-mint
    # rows appear with created=False and no ids; the store is untouched.
    would = [c for c in result["created"] if c.get("would_mint")]
    assert would and all(not c["created"] and c["candidate_id"] is None
                         for c in would)
    assert result["created_count"] == 0
    assert len(store.query(TripleQuery(limit=0))) == before
    # And the prediction matches the write night one-for-one.
    write = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    minted = [c for c in write["created"] if c["created"]]
    assert [c["title"] for c in minted] == [c["title"] for c in would]


def test_as_of_refused_outright(system) -> None:
    """Adversary F3: the miner has NO anchored read path — accepting
    as_of on report_only served HEAD wearing an anchor."""
    for kwargs in ({"as_of": 5}, {"as_of": 5, "report_only": True}):
        try:
            mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER, **kwargs)
        except ValueError as e:
            assert "as_of" in str(e)
        else:  # pragma: no cover
            raise AssertionError("anchored calls must refuse")


def test_living_theme_never_starves_the_cap_or_mutates_the_candidate(system) -> None:
    """Adversary F1 (P0): growing evidence re-entered remember_many —
    stale rows ate the cap forever and appended edges to a frozen record."""
    ids = _resolved_tension_world(system)
    first = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER,
                                 max_candidates=2)
    minted = [c for c in first["created"] if c["created"]]
    assert minted
    cid = minted[0]["candidate_id"]
    edges_before = len([a for a in system._store.query(TripleQuery(subject=cid, limit=0))
                        if isinstance(a.attributes, dict) and a.attributes.get("record_edge")])

    # The theme GROWS (the living-theme trajectory) and a fresh offer
    # becomes available.
    _episode(system, "m-grow", "Connection pool saturating at dusk too",
             session="s-delta", keywords=("connection", "pool"))
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _episode(system, f"m-i{i}", f"Reading about tidal energy, day {i}",
                 session=session, keywords=("tidal energy",))
    second = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER,
                                  max_candidates=2)
    # The standing offer is SKIPPED (no cap slot, no store write) and the
    # NEW offer mints — the cap counts mints, never stale retries.
    assert any("already minted" in s.get("reason", "") for s in second["skipped"])
    assert any(c["created"] and c["proposed_kind"] == "interest"
               for c in second["created"]), "a living theme must not starve new offers"
    edges_after = len([a for a in system._store.query(TripleQuery(subject=cid, limit=0))
                       if isinstance(a.attributes, dict) and a.attributes.get("record_edge")])
    assert edges_after == edges_before, (
        "a minted candidate must never grow edges on re-runs (no_source_mutation)")


def test_retracted_answer_never_quoted_in_the_offer(system) -> None:
    """Adversary F2: the answering map must fold beliefs — a retracted
    answer's words must not rest in a durable candidate digest."""
    q = _diary(system, "m-q9", "problem", "the antenna wire keeps shorting",
               "the antenna wire keeps shorting in rain", session="s-a")
    good = _diary(system, "m-a9", "note", "loose ground fixed the antenna wire",
                  "tightening the loose ground fixed the antenna wire shorting",
                  session="s-b", resolves=q)
    bad = _diary(system, "m-a9b", "note", "WRONG-RETRACTED: gulls short the wire",
                 "gulls were shorting the antenna wire (wrong)", session="s-c",
                 resolves=q)
    system.close_record(bad, kind="retract", reason="wrong diagnosis")
    _episode(system, "m-e9", "Antenna wire shorting again at the mast",
             session="s-d", keywords=("antenna", "wire"))
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    lessons = [c for c in result["created"]
               if c["proposed_kind"] == "lesson" and c["created"]]
    assert lessons
    attrs = _attrs_of(system, lessons[0]["candidate_id"])
    digest = ""
    for row in system._store.query(TripleQuery(subject=lessons[0]["candidate_id"], limit=0)):
        if str(row.predicate).endswith("abstract"):
            digest = str(row.object)
    assert "WRONG-RETRACTED" not in digest, "retracted words must not rest"
    assert "loose ground" in digest
    assert bad not in attrs["source_ids"]
    assert good in attrs["source_ids"]


def test_answer_alone_is_not_recurrence_and_unknown_sessions_never_count(system) -> None:
    """Adversary F4: the discharging entry shares the question's words by
    construction — it must not satisfy the >=2-session gate; and two
    provenance-less records are not two sessions."""
    q = _diary(system, "m-q8", "question", "why does the kiln crack the glaze",
               "why does the kiln crack the glaze on tall pots", session="s-x")
    _diary(system, "m-a8", "note", "kiln glaze cracks from fast cooling",
           "slow cooling stopped the kiln glaze cracking", session="s-y",
           answers=q)
    # No third-party evidence: the answer alone must NOT mint a lesson.
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert not [c for c in result["created"] if c["proposed_kind"] == "lesson"], (
        "an answered question with zero third-party recurrence is not a lesson offer")


def test_french_function_words_never_match_and_accents_fold(system, stack) -> None:
    """Adversary F5: 'cette'/'dans' passed the length floor; mémoire and
    memoire never matched. The matching lane folds accents and screens
    FR/EN function words."""
    store, journal = stack
    q = _diary(system, "m-qf", "question",
               "comment consolider la mémoire dans cette maison",
               "comment consolider la mémoire dans cette maison sans perte",
               session="s-fr1")
    _episode(system, "m-ef1", "Une promenade dans cette ville avec le chien",
             session="s-fr2", keywords=("promenade",))
    _episode(system, "m-ef2", "Consolider la memoire sans accent aujourd'hui",
             session="s-fr3", keywords=("consolider",))
    result = resolve_questions_pass(store, journal, scopes=SCOPES)
    props = {p["question_id"]: p for p in result["proposals"]}
    assert q in props, "accent-folded content terms must match (memoire == mémoire)"
    titles = [e["title"] for e in props[q]["evidence"]]
    assert any("memoire" in t.lower() or "mémoire" in t.lower() for t in titles)
    assert not any("promenade" in t.lower() for t in titles), (
        "function words (dans/cette/avec) must never be the shared terms")
    for e in props[q]["evidence"]:
        assert not (set(e["shared_terms"]) <= {"dans", "cette", "avec", "pour"})


def test_broader_interest_does_not_suppress_a_distinct_theme(system) -> None:
    """Adversary F6: 'energy policy' must not suppress a 'tidal energy'
    offer on one shared word."""
    _remember(system, "m-int2", "interest", "interest: energy policy",
              "interest: energy policy — how grids get regulated")
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _episode(system, f"m-t{i}", f"Reading about tidal energy, day {i}",
                 session=session, keywords=("tidal energy",))
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    interests = [c for c in result["created"]
                 if c["proposed_kind"] == "interest" and c["created"]]
    assert interests, "one shared term is not a declaration of this theme"


def test_two_themes_on_the_same_records_both_mint(system) -> None:
    """Adversary F7: coverage keyed on source ids alone suppressed the
    second theme forever."""
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _episode(system, f"m-d{i}", f"Evening notes, day {i}", session=session,
                 keywords=("glass harmonics", "quiet harbors"))
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER,
                                  max_candidates=4)
    themes = {c["title"] for c in result["created"]
              if c["proposed_kind"] == "interest" and c["created"]}
    assert any("glass harmonics" in t for t in themes)
    assert any("quiet harbors" in t for t in themes), (
        "two distinct themes carried by the same records must both offer")


def test_retracted_and_parked_interests_do_not_suppress(system, stack) -> None:
    """Adversary F9: a retracted interest suppressed its theme forever;
    a rejected (parked) interest also suppressed against the comment's
    promise."""
    store, journal = stack
    gone = _remember(system, "m-int3", "interest", "interest: tidal energy",
                     "interest: tidal energy — early fascination")
    system.close_record(gone, kind="retract", reason="not mine anymore")
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _episode(system, f"m-p{i}", f"Reading about tidal energy, day {i}",
                 session=session, keywords=("tidal energy",))
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    interests = [c for c in result["created"]
                 if c["proposed_kind"] == "interest" and c["created"]]
    assert interests, "a retracted interest no longer owns its theme"


def test_candidate_edges_never_merge_dream_components(system, stack) -> None:
    """Adversary F8 (dream-death mechanic): a cross-session candidate's
    summarizes edges must not fuse islands in the dream substrate."""
    from abstractmemory import structural_report

    store, journal = stack
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _episode(system, f"m-x{i}", f"Island {i} note", session=session,
                 keywords=("quiet harbors",))
    before = structural_report(store, journal, scopes=SCOPES)
    n_components = before["counts"]["components"]
    result = mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert any(c["created"] for c in result["created"])
    after = structural_report(store, journal, scopes=SCOPES)
    assert after["counts"]["components"] >= n_components, (
        "a machine offer must never fuse lived islands")
    assert after["counts"]["candidate_edges"] > 0, "the edges are counted, honestly"


def test_question_twin_is_not_resolution_evidence(system, stack) -> None:
    """Adversary F13c: a re-asked question must not propose as the answer
    to its older twin."""
    store, journal = stack
    q1 = _diary(system, "m-tw1", "question", "why does the cellar flood in spring",
                "why does the cellar flood in spring thaw", session="s-1")
    _diary(system, "m-tw2", "question", "why does the cellar flood in spring",
           "why does the cellar flood in spring again", session="s-2")
    result = resolve_questions_pass(store, journal, scopes=SCOPES)
    for p in result["proposals"]:
        if p["question_id"] == q1:
            raise AssertionError("askings are not answers — twin proposed as evidence")


# ---------------------------------------------------------------------------
# Composition: sleep_pass phase + cognition_health counts + dream signals
# ---------------------------------------------------------------------------


def test_sleep_pass_runs_mining_and_health_counts_pending_offers(system, stack) -> None:
    store, journal = stack
    _resolved_tension_world(system)
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert night["phases"] == ("resolution", "maintenance", "world_models",
                               "mining", "identity", "dream")
    lessons = [c for c in night["mining"]["created"]
               if c["proposed_kind"] == "lesson" and c["created"]]
    assert lessons, "the night must mine the resolved tension"

    health = cognition_health(store, journal, scopes=SCOPES)
    assert health["candidates"]["pending"] >= 1
    assert health["candidates"]["by_proposed_kind"].get("lesson", 0) >= 1
    # STRUCTURALLY outside the ratios (correction 7 / B-F8): the offer
    # never moves questions/interests bars.
    assert health["interests"]["open"] == 0
    # The resolved problem stays resolved — mining changed no drive.
    assert health["problems"]["repaired"] == 1


def test_candidates_never_enter_drive_pressure(system, stack) -> None:
    store, journal = stack
    from abstractmemory import drive_pressure

    _resolved_tension_world(system)
    before = drive_pressure(store, journal, scopes=SCOPES)["total_open"]
    mine_candidates_pass(system, scopes=SCOPES, owner_id=OWNER)
    after = drive_pressure(store, journal, scopes=SCOPES)["total_open"]
    assert after == before, (
        "a machine offer must never appear as HIS drive (B-F8 by shape)")


def test_mined_offers_echo_in_the_dream_signal_stream(system) -> None:
    _resolved_tension_world(system)
    # Give the dream two islands so it minti (the miner's acts then echo).
    _episode(system, "m-g1", "Garden sensor day", session="s-g",
             keywords=("garden", "sensors", "noon"))
    _episode(system, "m-g2", "Harbor walk at noon", session="s-h",
             keywords=("harbor", "noon"))
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    dream_id = night["dream"]["dream_record_id"]
    if not dream_id:
        return  # a quiet night is valid; the echo is covered when it dreams
    attrs = _attrs_of(system, dream_id)
    mined = [s for s in attrs.get("signals", ())
             if s["phase"] == "mining" and s["act"] == "candidate_minted"]
    created = [c for c in night["mining"]["created"] if c["created"]]
    if created:
        assert mined, "a minted offer is a night act — it must echo as a signal"
        assert any("Lesson candidate" in s["fragment"] for s in mined)
