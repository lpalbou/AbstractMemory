"""Item 14 — the two-sided visit, MEMORY-LAYER contract (plan phase 3).

The plan's item-14 memory layer (c159, folded v13+): a cross-runtime visit
is ONE EVENT, TWO PERSPECTIVES, TWO APPEND-ONLY JOURNALS — each entity
forms its OWN record of the shared moment in its OWN home, co-presence
stamped explicitly (participants = both door-verified identities), joined
by a door-stamped visit id carried as DATA. NEVER one run written into two
stores; never shared rows. What A diaries about the visit never lands in
B's home.

These tests pin that contract on the ENGINE alone, before the transport
exists (the M3 pattern: the seam agreed and pinned before the build) —
this is the "correspondence correct-outcome test" from the 0011 verdict
that the seam spec's A/B gate names (criterion 1 extension). The relay
(gateway GW-C/GW-G) and the durable runs (runtime R2) will make these
writes happen for real; the invariants they must land on are pinned here.

NAMING (laurent c338 + agency c341 option (b)): `visit_id` is the FIRST
INSTANCE of the generic interaction-correlation convention — a key minted
ONCE at the door for one shared interaction, opaque, carried as DATA on
each participant's own records, kind-free. The name stays concrete where
it was born; the next interaction kind (a meet, a broadcast, a co-work
session) REUSES this key convention instead of minting a second spelling.
The engine never parses it — correlation is the consumer's join.
"""

from __future__ import annotations

import warnings
from typing import Any, Tuple

import pytest

from abstractmemory import (
    DEFAULT_SPARK_TEMPLATE,
    InMemoryJournal,
    InMemoryTripleStore,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    Stimulus,
    engram,
    export_replay,
)
from abstractmemory.records import MemoryRecordInput
from abstractmemory.store import TripleQuery

ANNA = "entity:anna"    # the visitor (outbound leg forms in HER home)
BRUNO = "entity:bruno"  # the receiver (inbound leg forms in HIS home)
VISIT_ID = "visit-3f2a9c"  # door-stamped correlation key (carried as DATA)
PRIVATE_WORDS = "petrichor-lantern-quiet"  # A's private diary sentinel


def _home(kind: str, tmp_path, name: str) -> Tuple[Any, Any, MemorySystem]:
    if kind == "sqlite":
        path = tmp_path / f"{name}.sqlite3"
        store, journal = SQLiteTripleStore(path), SQLiteJournal(path)
    else:
        store = InMemoryTripleStore()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            journal = InMemoryJournal()
    return store, journal, MemorySystem(store=store, journal=journal)


@pytest.fixture(params=["memory", "sqlite"])
def two_homes(request, tmp_path):
    a_store, a_journal, anna = _home(request.param, tmp_path, "anna")
    b_store, b_journal, bruno = _home(request.param, tmp_path, "bruno")
    engram(anna, DEFAULT_SPARK_TEMPLATE, scope="self", owner_id=ANNA)
    engram(bruno, DEFAULT_SPARK_TEMPLATE, scope="self", owner_id=BRUNO)
    yield (anna, a_store, a_journal), (bruno, b_store, b_journal)
    for closable in (a_journal, a_store, b_journal, b_store):
        closable.close()


def _exchange(anna: MemorySystem, bruno: MemorySystem) -> Tuple[str, str]:
    """One shared moment, formed twice — each home its OWN perspective,
    its OWN turn identity, the shared visit id as an attribute."""
    [a_episode] = anna.remember_many(
        [MemoryRecordInput(
            kind="episode", title="Visiting Bruno",
            digest="I visited Bruno and we talked about the harbor cranes.",
            participants=(ANNA, BRUNO),
            attributes={"visit_id": VISIT_ID})],
        scope="life", owner_id=ANNA, idempotency_key=f"{VISIT_ID}|outbound|t1")
    [b_episode] = bruno.remember_many(
        [MemoryRecordInput(
            kind="episode", title="Anna visited",
            digest="Anna visited me and we talked about the harbor cranes.",
            participants=(ANNA, BRUNO),
            attributes={"visit_id": VISIT_ID})],
        scope="life", owner_id=BRUNO, idempotency_key=f"{VISIT_ID}|inbound|t1")
    return a_episode, b_episode


def test_one_event_two_perspectives_never_shared_rows(two_homes) -> None:
    (anna, a_store, _), (bruno, b_store, _) = two_homes
    a_episode, b_episode = _exchange(anna, bruno)

    # Correlation is by the door-stamped visit id AS DATA — the record ids
    # differ (each home derived its own from its own turn identity).
    assert a_episode != b_episode
    for store, episode, owner in ((a_store, a_episode, ANNA), (b_store, b_episode, BRUNO)):
        [row] = [a for a in store.query(TripleQuery(subject=episode, limit=0))
                 if not a.attributes.get("record_edge")]
        assert row.attributes["visit_id"] == VISIT_ID
        assert row.owner_id == owner
        assert sorted(row.attributes["participants"]) == sorted([ANNA, BRUNO])

    # Mirrored perspectives, never shared rows: neither store contains the
    # OTHER home's record id anywhere (subject or object).
    assert a_store.query(TripleQuery(subject=b_episode, limit=1)) == []
    assert b_store.query(TripleQuery(subject=a_episode, limit=1)) == []


def test_identity_never_contaminated_and_counters_stay_zero(two_homes) -> None:
    """The 0011 correct-outcome pin (A/B criterion-1 extension): after the
    exchange, neither identity entered the other's home, and a recall+commit
    cycle over the visit content leaves BOTH identity cores at access 0
    (presence != use holds through correspondence)."""
    (anna, a_store, _), (bruno, b_store, _) = two_homes
    a_episode, b_episode = _exchange(anna, bruno)

    # B's identity records are entirely absent from A's store (and inversely).
    a_core = {r.subject for r in anna.self_records(scope="self", owner_id=ANNA)}
    b_core = {r.subject for r in bruno.self_records(scope="self", owner_id=BRUNO)}
    assert a_core and b_core
    for rid in b_core:
        assert a_store.query(TripleQuery(subject=rid, limit=1)) == []
    for rid in a_core:
        assert b_store.query(TripleQuery(subject=rid, limit=1)) == []

    # Each side recalls the shared moment (posture: identity present by
    # right) and commits ITS OWN episode — identity counters stay 0.
    for system, owner, episode, core in (
        (anna, ANNA, a_episode, a_core), (bruno, BRUNO, b_episode, b_core),
    ):
        from abstractmemory import RecallBudget
        result = system.reconstruct(
            Stimulus(cue_text="harbor cranes visit", participants=(ANNA, BRUNO)),
            scopes=[("self", owner), ("life", owner)],
            budget=RecallBudget(self_fraction=0.5),
            trace_id=f"{VISIT_ID}|{owner}|recall")
        assert any(h.record_id and h.admission in ("stimulus", "both")
                   and h.owner_id == owner for h in result.handles)
        system.commit_selection(f"{VISIT_ID}|{owner}|recall", [episode])
        counts = system.access_counts(record_ids=sorted(core))
        assert all(n == 0 for n in counts["records"].values()), \
            "identity presence deposited usage through a correspondence turn"


def test_what_a_diaries_about_the_visit_never_lands_in_b(two_homes) -> None:
    (anna, a_store, _), (bruno, b_store, _) = two_homes
    _exchange(anna, bruno)

    # A elects a PRIVATE diary entry about the visit — in HER home only.
    anna.remember_many(
        [MemoryRecordInput(
            kind="diary", title="After the visit",
            digest=f"Privately: {PRIVATE_WORDS}.",
            attributes={"diary_type": "reflection", "private": True,
                        "entry_id": "diary_a1b2c3", "visit_id": VISIT_ID},
            provenance={"source": "diary-projection"})],
        scope="diary", owner_id=ANNA, idempotency_key=f"{VISIT_ID}|a-diary|1")

    # B's home: zero diary rows, zero rows carrying the private words —
    # checked over EVERY row (subject/object/attributes), the 0007 predicate.
    b_rows = b_store.query(TripleQuery(limit=0))
    assert all((r.attributes or {}).get("record_kind") != "diary" for r in b_rows)
    for row in b_rows:
        blob = f"{row.subject} {row.predicate} {row.object} {row.attributes}"
        assert PRIVATE_WORDS not in blob

    # And B's replay stream never carries it either (the served surface).
    for envelope in export_replay(b_store, bruno._journal, owner_id=BRUNO):
        assert PRIVATE_WORDS not in str(envelope)


def test_replay_display_surfaces_visit_id_but_never_on_diary(two_homes) -> None:
    """Observer's render ask (c344, graph_id precedent): the ALREADY-ENGRAVED
    attributes.visit_id surfaces in replay display blocks of digest rows that
    carry it — episodes correlate across the two streams as data. Diary
    blocks stay sealed: a private entry's correlation key would leak the
    act's context (same rule as formation edges)."""
    (anna, a_store, a_journal), (bruno, b_store, b_journal) = two_homes
    _exchange(anna, bruno)
    anna.remember_many(
        [MemoryRecordInput(
            kind="diary", title="After the visit",
            digest=f"Privately: {PRIVATE_WORDS}.",
            attributes={"diary_type": "reflection", "private": True,
                        "entry_id": "diary_d4e5f6", "visit_id": VISIT_ID},
            provenance={"source": "diary-projection"})],
        scope="diary", owner_id=ANNA, idempotency_key=f"{VISIT_ID}|a-diary|2")

    def _display_blocks(store, journal, owner):
        return [e["display"] for e in export_replay(store, journal, owner_id=owner)
                if isinstance(e.get("display"), dict)]

    for store, journal, owner in ((a_store, a_journal, ANNA), (b_store, b_journal, BRUNO)):
        episode_blocks = [b for b in _display_blocks(store, journal, owner)
                          if b.get("kind") == "episode"]
        assert any(b.get("visit_id") == VISIT_ID for b in episode_blocks), \
            f"{owner}: episode display should carry the correlation key"
    diary_blocks = [b for b in _display_blocks(a_store, a_journal, ANNA)
                    if b.get("redacted") == "diary"]
    assert diary_blocks and all("visit_id" not in b for b in diary_blocks), \
        "a redacted diary block must never carry the correlation key"


def test_receiving_side_recalls_the_shared_moment_by_participant(two_homes) -> None:
    """WITH-WHOM works on the receiving side: a later stimulus naming the
    visitor surfaces B's OWN record of the shared moment (shared-context
    channel over the stamped participants), never anything of A's."""
    (anna, _, _), (bruno, _, _) = two_homes
    _, b_episode = _exchange(anna, bruno)

    result = bruno.reconstruct(
        Stimulus(cue_text="something else entirely today",
                 participants=(ANNA,)),
        scopes=[("life", BRUNO)], trace_id=f"{VISIT_ID}|b-later")
    # handle.record_id is the digest ASSERTION id; the graph id remember_many
    # returned rides provenance["record_id"] (the two-namespace contract).
    [hit] = [h for h in result.handles
             if h.provenance.get("record_id") == b_episode]
    assert any("shared-with" in c for c in hit.cues)
    assert all(h.owner_id == BRUNO for h in result.handles)
