"""The shared-context channel (maintainer round 5, "with whom" part (c)):
memories carry WHO lived them (attributes.participants); a stimulus naming
participants matches the memories shared with them — "what do WE know /
have lived together". Previously Stimulus.participants was normalized in
the seam and used NOWHERE (inert); this suite pins the channel end-to-end.
"""

from __future__ import annotations

import pytest

from abstractmemory import RecallBudget, Stimulus
from abstractmemory.records import MemoryRecordInput

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _remember(system, key: str, title: str, digest: str, participants=()) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title=title, digest=digest,
                           participants=tuple(participants))],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def test_participants_flow_into_record_attributes(system, stack) -> None:
    store, _ = stack
    gid = _remember(system, "p-0", "Kitchen plan", "Planned the kitchen sensors together.",
                    ["person:albou", "entity:castor"])
    from abstractmemory.store import TripleQuery
    [row] = [a for a in store.query(TripleQuery(subject=gid, limit=0))
             if a.attributes.get("record_kind")]
    assert row.attributes["participants"] == ["person:albou", "entity:castor"]


def test_shared_context_recall_scores_and_cues(system) -> None:
    shared_both = _remember(system, "p-1", "Outage night",
                            "Walked the outage together at 2am.",
                            ["person:albou", "entity:castor"])
    shared_one = _remember(system, "p-2", "Recital chat",
                           "Talked about the recital in the hallway.",
                           ["person:albou"])
    solo = _remember(system, "p-3", "Solo maintenance",
                     "Vacuumed the vector index alone.", [])

    r = system.reconstruct(
        Stimulus(cue_text="", participants=("person:albou", "entity:castor")),
        scopes=SCOPES, journal=False)
    by_id = {h.provenance.get("record_id"): h for h in r.handles}

    # Full co-presence scores 1.0; partial scores |shared|/|stimulus|.
    assert by_id[shared_both].relevance["participants"] == 1.0
    assert by_id[shared_one].relevance["participants"] == 0.5
    assert "participants" not in by_id[solo].relevance
    assert any(c.startswith("shared-with: entity:castor, person:albou (2/2)")
               for c in by_id[shared_both].cues)

    # Channel-matched semantics are inherited: shared memories order ahead
    # of the unshared recent under the fill contract.
    ids = [h.provenance.get("record_id") for h in r.handles]
    assert ids.index(shared_both) < ids.index(solo)
    assert by_id[shared_both].admission in ("stimulus", "both")
    assert "participants" in r.to_dict()["handles"][0]["relevance"]  # JSON-safe


def test_solo_stimulus_never_runs_the_channel(system) -> None:
    _remember(system, "p-1", "Outage night", "Walked the outage together.",
              ["person:albou"])
    r = system.reconstruct(Stimulus(cue_text="outage"), scopes=SCOPES, journal=False)
    assert all("participants" not in h.relevance for h in r.handles)

    # And a participants-only stimulus with no shared records matches nothing
    # via the channel (no crash, no phantom relevance).
    r2 = system.reconstruct(Stimulus(cue_text="", participants=("person:stranger",)),
                            scopes=SCOPES, journal=False)
    assert all("participants" not in h.relevance for h in r2.handles)


def test_participants_channel_respects_tight_budget_priority(system) -> None:
    """A shared memory is a channel match: under scarcity it takes the
    phase-0 seat over unmatched trail-hot records (C3 inherited)."""
    shared = _remember(system, "p-1", "Shared decision",
                       "Decided the backup policy together.", ["person:albou"])
    hot = _remember(system, "p-2", "Hot solo note", "A solo note used a lot.", [])
    for i in range(3):
        system.commit_selection(f"t-warm-{i}", [hot])

    tight = system.reconstruct(
        Stimulus(cue_text="", participants=("person:albou",)),
        scopes=SCOPES, journal=False,
        budget=RecallBudget(shelf_size=1, token_budget=30, stm_fraction=0.25))
    assert [h.provenance.get("record_id") for h in tight.handles] == [shared]
