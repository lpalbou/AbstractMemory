"""Re-digestion machinery (dispatch c1340 ask 5 — built substrate-side,
touching no home; ready the day laurent rules on Castor).

Contracts pinned:
- candidates: PURE READ over the labeled mechanical debt, worst-first
  (poverty = marker-only digests, then global use desc); protected kinds
  and unlabeled/authored digests never enumerate.
- apply: authored-words-only write verb — new record (same kind/
  payload_ref/participants, edges copied + refines lineage, origin_date
  era continuity) + supersede closure; current-wins retires the old
  digest from ranked retrieval.
- rails: protected kinds, unlabeled methods, empty/identical digests,
  unknown records all refuse PER ENTRY (batch never aborts); a missing
  actor raises (words without an author are refused).
- idempotency: replaying the same batch re-derives identical ids and
  writes nothing new.
- D2 of repair: applying deposits nothing.
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
    Stimulus,
    apply_redigestion,
    redigestion_candidates,
)

OWNER = "entity:castor"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _seed(system):
    """Three mechanical episodes (one marker-only), one authored episode,
    one diary projection, one interest — the Castor shape in miniature."""
    marker_only, rich, mid = system.remember_many([
        MemoryRecordInput(
            kind="episode", title="own time",
            digest="[used tool: read_file]",
            participants=("person:ada", OWNER),
            payload_ref="artifact-1",
            attributes={"digest_method": "mechanical-v1"}),
        MemoryRecordInput(
            kind="episode", title="harbor talk",
            digest="User: how goes the harbor? castor: The wall survey found three cracks worth watching.",
            keywords=("harbor",),
            payload_ref="artifact-2",
            edges=(("continues", "local:0"),),
            attributes={"digest_method": "mechanical-v1"}),
        MemoryRecordInput(
            kind="episode", title="short note",
            digest="[kept in diary - note] A gull.",
            payload_ref="artifact-3",
            attributes={"digest_method": "mechanical-v1"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="mech")
    [authored] = system.remember_many([
        MemoryRecordInput(kind="episode", title="authored one",
                          digest="I wrote these words myself, deliberately.",
                          attributes={"digest_method": "entity-authored"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="auth")
    [diary] = system.remember_many([
        MemoryRecordInput(kind="diary", title="Elected words",
                          digest="What I chose to keep.",
                          attributes={"entry_id": "e-1",
                                      "digest_method": "mechanical-v1"},
                          provenance={"source": "diary-projection"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="diary")
    [interest] = system.remember_many([
        MemoryRecordInput(kind="interest", title="Bridges",
                          digest="Drawn to the twelve bridges.",
                          attributes={"digest_method": "mechanical-v1"}),
    ], scope="self", owner_id=OWNER, idempotency_key="int")
    return {"marker_only": marker_only, "rich": rich, "mid": mid,
            "authored": authored, "diary": diary, "interest": interest}


def _burn(system, gid, times=3):
    """Deposit real selected-use on a record (usage ranking input)."""
    for i in range(times):
        r = system.reconstruct(Stimulus(cue_text="harbor wall gull tool"),
                               scopes=SCOPES, trace_id=f"burn-{gid}-{i}")
        if any(h.record_id for h in r.handles):
            # commit only the target if admitted; else commit whole shelf
            ids = [h.record_id for h in r.handles]
            system.commit_selection(f"burn-{gid}-{i}", ids)


# ---------------------------------------------------------------------------
# candidates
# ---------------------------------------------------------------------------

def test_candidates_enumerate_only_labeled_mechanical_and_rank_poverty_first(system) -> None:
    ids = _seed(system)
    report = redigestion_candidates(system, scopes=SCOPES + [("self", OWNER)])
    got = {c.record_id: c for c in report["candidates"]}

    assert ids["marker_only"] in got and ids["rich"] in got and ids["mid"] in got
    assert ids["authored"] not in got        # authored words never batch-enumerate
    assert ids["diary"] not in got           # protected kind (elected plane)
    assert ids["interest"] not in got        # protected kind (identity act)

    # Poverty first: the marker-only digest outranks the rich mechanical one.
    order = [c.record_id for c in report["candidates"]]
    assert order.index(ids["marker_only"]) < order.index(ids["rich"])
    assert got[ids["marker_only"]].poverty is True
    assert got[ids["marker_only"]].content_residue == ""
    assert got[ids["rich"]].poverty is False
    # The verbatim source rides along for the re-author.
    assert got[ids["rich"]].payload_ref == "artifact-2"
    assert report["poverty_count"] >= 1


def test_candidates_are_a_pure_read(system) -> None:
    _seed(system)
    before = system.current_seq()
    redigestion_candidates(system, scopes=SCOPES)
    assert system.current_seq() == before  # no journal growth: reading debt is not use


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def test_apply_supersedes_with_authored_words_and_keeps_topology(system) -> None:
    ids = _seed(system)
    result = apply_redigestion(system, [
        {"record_id": ids["rich"],
         "digest": "Ada asked about the harbor; I reported three watchable cracks in the wall survey.",
         "keywords": ["harbor", "cracks"]},
    ], actor="entity-reflection")
    [outcome] = [o for o in result["outcomes"] if o["record_id"] == ids["rich"]]
    assert outcome["outcome"] == "applied"
    new_gid = outcome["new_record_id"]

    # Current-wins: recall surfaces the authored digest, never the old one.
    r = system.reconstruct(Stimulus(cue_text="harbor cracks"), scopes=SCOPES, journal=False)
    digests = " | ".join(h.digest for h in r.handles)
    assert "three watchable cracks" in digests
    assert "User: how goes the harbor?" not in digests

    # Topology + provenance on the new record.
    from abstractmemory import TripleQuery
    rows = list(system.store.query(TripleQuery(subject=new_gid, limit=0)))
    digest_row = next(a for a in rows if a.attributes.get("record_kind"))
    assert digest_row.attributes["redigested_from"] == ids["rich"]
    assert digest_row.attributes["digest_method"] == "entity-authored"
    assert digest_row.attributes["payload_ref"] == "artifact-2"   # verbatim untouched
    assert digest_row.attributes["origin_date"]                    # era continuity
    edge_pairs = {(a.predicate, a.object) for a in rows if a.attributes.get("record_edge")}
    assert ("refines", ids["rich"]) in edge_pairs                  # lineage
    assert any(p == "continues" for p, _t in edge_pairs)           # copied edge


def test_apply_is_idempotent_on_replay(system) -> None:
    ids = _seed(system)
    batch = [{"record_id": ids["marker_only"],
              "digest": "Ada and I read the harbor file together that morning."}]
    first = apply_redigestion(system, batch, actor="operator")
    new_gid = first["outcomes"][0]["new_record_id"]
    rows_before = len(list(system.store.query(
        __import__("abstractmemory").TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))))
    replay = apply_redigestion(system, batch, actor="operator")
    assert replay["outcomes"][0]["new_record_id"] == new_gid       # same derived id
    rows_after = len(list(system.store.query(
        __import__("abstractmemory").TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))))
    assert rows_after == rows_before                               # nothing new written


def test_apply_rails_refuse_per_entry_without_aborting_the_batch(system) -> None:
    ids = _seed(system)
    result = apply_redigestion(system, [
        {"record_id": ids["diary"], "digest": "rewritten elected words"},      # protected
        {"record_id": ids["authored"], "digest": "silently replaced"},         # not mechanical
        {"record_id": ids["rich"], "digest": "User: how goes the harbor? castor: The wall survey found three cracks worth watching."},  # identical
        {"record_id": "ex:episode-doesnotexist000000000000", "digest": "x"},   # unknown
        {"record_id": ids["mid"], "digest": "A gull crossed the harbor while I kept a small note."},  # valid
    ], actor="entity-reflection")
    by_id = {o["record_id"]: o for o in result["outcomes"]}
    assert by_id[ids["diary"]]["outcome"] == "refused" and "protected" in by_id[ids["diary"]]["reason"]
    assert by_id[ids["authored"]]["outcome"] == "refused" and "consent" in by_id[ids["authored"]]["reason"]
    assert by_id[ids["rich"]]["outcome"] == "refused" and "identical" in by_id[ids["rich"]]["reason"]
    assert by_id["ex:episode-doesnotexist000000000000"]["outcome"] == "refused"
    assert by_id[ids["mid"]]["outcome"] == "applied"               # the batch survived
    assert result["applied"] == 1


def test_apply_contains_formation_refusal_per_entry(system) -> None:
    """Production-audit finding 9: a row whose kind this engine version
    does not register (foreign/newer writer) must refuse ITS entry, never
    abort the batch — an operator's 500-entry Castor batch dying at entry
    250 with half the closures already committed is the incident shape."""
    from abstractmemory.models import TripleAssertion

    ids = _seed(system)
    # A foreign-kind mechanical row, written directly (no formation gate —
    # exactly what a newer engine version's home looks like to this one).
    system.store.add([TripleAssertion(
        subject="ex:futurekind-aaaaaaaaaaaaaaaaaaaaaaaa",
        predicate="dcterms:abstract",
        object="[used tool: read_file]",
        scope=SCOPE, owner_id=OWNER,
        attributes={"record_kind": "futurekind", "digest_method": "mechanical-v1"},
    )])
    result = apply_redigestion(system, [
        {"record_id": "ex:futurekind-aaaaaaaaaaaaaaaaaaaaaaaa",
         "digest": "Words this engine cannot form under an unknown kind."},
        {"record_id": ids["mid"], "digest": "A gull crossed the harbor while I kept a small note."},
    ], actor="entity-reflection")
    by_id = {o["record_id"]: o for o in result["outcomes"]}
    foreign = by_id["ex:futurekind-aaaaaaaaaaaaaaaaaaaaaaaa"]
    assert foreign["outcome"] == "refused" and "formation refused" in foreign["reason"]
    assert by_id[ids["mid"]]["outcome"] == "applied"   # batch survived
    assert result["applied"] == 1


def test_apply_requires_a_named_author(system) -> None:
    ids = _seed(system)
    with pytest.raises(ValueError, match="actor"):
        apply_redigestion(system, [{"record_id": ids["rich"], "digest": "x y z"}], actor="")


def test_apply_deposits_nothing(system) -> None:
    ids = _seed(system)
    apply_redigestion(system, [
        {"record_id": ids["marker_only"], "digest": "We read the harbor file; nothing else happened."},
    ], actor="entity-reflection")
    counts = system.access_counts([ids["marker_only"]])["records"]
    assert counts[ids["marker_only"]] == 0  # repair is not use (D2 of repair)


# ---------------------------------------------------------------------------
# mechanical-set drift (Ephemeral incident, c2447 wave)
# ---------------------------------------------------------------------------

def test_mechanical_set_tracks_live_writer_labels(system) -> None:
    """The consent set must cover every writer's mechanical label — the live
    driver forms mechanical-v2 and the c2447 floor fix forms
    mechanical-floor-v1; a set knowing only v1 silently refuses the exact
    records the incident repair path (r-mem-3) exists for. Dedup summaries
    stay excluded: they stand for a group and are disposal's lane."""
    from abstractmemory import MECHANICAL_DIGEST_METHODS

    assert {"mechanical-v1", "mechanical-v2", "mechanical-floor-v1"} <= MECHANICAL_DIGEST_METHODS
    assert "mechanical-dedup-v1" not in MECHANICAL_DIGEST_METHODS

    [v2] = system.remember_many([
        MemoryRecordInput(
            kind="episode", title="v2 contaminated",
            digest="person:admin: hello. me: The loop indicator is still there (iteration 3 of 20).",
            payload_ref="artifact-v2",
            attributes={"digest_method": "mechanical-v2"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="drift-v2")
    [floored] = system.remember_many([
        MemoryRecordInput(
            kind="summary", title="floored reflection",
            digest="[marked 2 feelings] [kept an interest] - Look-back over 1 moment(s): quiet session.",
            edges=(("summarizes", v2),),  # engine guard: a summary names its sources
            attributes={"digest_method": "mechanical-floor-v1"}),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="drift-floor")

    report = redigestion_candidates(system, scopes=SCOPES)
    got = {c.record_id for c in report["candidates"]}
    assert v2 in got and floored in got  # both current labels enumerate

    result = apply_redigestion(system, [
        {"record_id": v2,
         "digest": "The visitor greeted me; I mentioned a loop indicator I kept noticing."},
    ], actor="entity-reflection")
    assert result["outcomes"][0]["outcome"] == "applied"  # v2 is repairable
