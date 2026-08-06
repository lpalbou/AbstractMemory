"""M3 — clean internal keys (plan items 2 + 6, memory half).

THE RULED SPELLINGS (maintainer, commons c2513): an entity's internal id is
`entity:<name>`, and the only @-suffixed shape that exists anywhere is the
NETWORK HANDLE `<entity_name>@ip` (addressing, never storage). The
@home_id-suffixed owner string was a MISTAKE — retired, never minted again,
and never to be taught as a format.

Why this test still constructs one: existing homes were engraved with the
mistake before it was retired, and the journal is append-only — the bad
string cannot be renamed out of those lives. The ENGINE guarantee pinned
here is what makes that tolerable: owner strings are OPAQUE — never parsed,
never normalized across forms, never merged. A clean-id home and a
mistake-engraved home each round-trip identically through engram ->
formation -> recall -> commit -> gradation -> replay, and two owners whose
strings share a prefix ("entity:castor" vs "entity:castor@home-abc") are
fully distinct identities in one store. New minting is the door's job and
mints ONLY `entity:<name>`.
"""

from __future__ import annotations

from typing import Any

import pytest

from abstractmemory import DEFAULT_SPARK_TEMPLATE, Stimulus, engram, export_replay
from abstractmemory.records import MemoryRecordInput

SCOPE = "life"

CLEAN = "entity:castor"                 # the item-6 form for NEW homes
LEGACY = "entity:castor@home-ab12cd34"  # the pre-plan engraving (kept for life)


def _live_a_little(system, owner: str, key_prefix: str) -> str:
    """One tiny life: engram + an episode + a used recall + a feeling."""
    result = engram(system, DEFAULT_SPARK_TEMPLATE, scope="self", owner_id=owner)
    assert result.record_ids["values"]  # the core planted under this owner
    [episode] = system.remember_many(
        [MemoryRecordInput(kind="episode", title=f"Harbor walk ({owner})",
                           digest=f"Walked the harbor at noon with {owner}.")],
        scope=SCOPE, owner_id=owner, idempotency_key=f"{key_prefix}-ep-1")
    recall = system.reconstruct(
        Stimulus(cue_text="harbor walk noon"),
        scopes=[("self", owner), (SCOPE, owner)], trace_id=f"{key_prefix}-t1",
        journal=True)
    assert any(h.title.startswith("Harbor walk") for h in recall.handles)
    system.commit_selection(f"{key_prefix}-t1", [episode])
    system.appraise(target_id="person:laurent", sign=1, magnitude=2,
                    scope="self", owner_id=owner, reason="he stayed while I searched",
                    actor="entity-reflection", trace_id=f"{key_prefix}-t1")
    return episode


@pytest.mark.parametrize("owner", [CLEAN, LEGACY], ids=["clean-key", "legacy-key"])
def test_owner_form_round_trips_end_to_end(system, owner: str) -> None:
    """Both engravings live identical lives: the engine never parses the
    owner string, so the item-6 mint change is a pure door decision."""
    episode = _live_a_little(system, owner, key_prefix="rt")

    # Identity reads back under the exact owner key.
    core = system.self_records(scope="self", owner_id=owner)
    assert core and all(a.owner_id == owner for a in core)
    # Usage landed under the exact owner key (presence != use held for self).
    counts = system.access_counts(record_ids=[episode])
    assert counts["records"][episode] >= 1
    # Gradation folds under the exact owner key.
    standing = system.gradation(scope="self", owner_id=owner)
    assert standing["person:laurent"]["positive"] > 0
    # The replay stream carries the owner VERBATIM on every scoped envelope.
    owners = {e["owner_id"] for e in export_replay(system._store, system._journal,
                                                   owner_id=owner)
              if e.get("owner_id")}
    assert owners == {owner}


def test_prefix_sharing_owners_never_merge(system) -> None:
    """The dangerous drift the opaque-string rule forbids: a clean key and
    a legacy key sharing the name prefix are DISTINCT identities — no read
    surface may fold one into the other (the door maps handle -> home; the
    engine must never 'helpfully' normalize)."""
    _live_a_little(system, CLEAN, key_prefix="a")
    _live_a_little(system, LEGACY, key_prefix="b")

    # Identity cores are disjoint record sets.
    clean_ids = {a.subject for a in system.self_records(scope="self", owner_id=CLEAN)}
    legacy_ids = {a.subject for a in system.self_records(scope="self", owner_id=LEGACY)}
    assert clean_ids and legacy_ids and clean_ids.isdisjoint(legacy_ids)

    # Recall under one owner never surfaces the other's records.
    recall = system.reconstruct(Stimulus(cue_text="harbor walk noon"),
                                scopes=[(SCOPE, CLEAN)], trace_id="iso-t1")
    assert recall.handles and all(h.owner_id == CLEAN for h in recall.handles)

    # Gradation is per-owner: each life felt its own +2, not a merged +4.
    for owner in (CLEAN, LEGACY):
        standing = system.gradation(scope="self", owner_id=owner)
        assert standing["person:laurent"]["positive"] == pytest.approx(2.0)

    # Replay filtered to one owner never leaks the other's envelopes — the
    # filter matches the string EXACTLY (never a prefix).
    leaked = [e for e in export_replay(system._store, system._journal, owner_id=CLEAN)
              if e.get("owner_id") not in (CLEAN, "", None)]
    assert leaked == []


def test_owner_strings_reach_participant_stamps_unparsed(system) -> None:
    """Co-presence stamps carry whatever identity string the door minted —
    the participants channel matches them by EXACT string (the engine's
    opacity contract at the one place identity strings compare)."""
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Shared moment",
                           digest="A visit both parties will remember.",
                           participants=(CLEAN, "person:laurent"))],
        scope=SCOPE, owner_id=CLEAN, idempotency_key="ps-1")
    hit = system.reconstruct(
        Stimulus(cue_text="completely unrelated cue words",
                 participants=(CLEAN,)),
        scopes=[(SCOPE, CLEAN)], trace_id="ps-t1")
    [handle] = [h for h in hit.handles if h.record_id]
    assert handle.title == "Shared moment"
    assert any("shared-with" in c for c in handle.cues)
    # The near-miss form does NOT match: exact strings, never prefixes.
    miss = system.reconstruct(
        Stimulus(cue_text="completely unrelated cue words",
                 participants=(LEGACY,)),
        scopes=[(SCOPE, CLEAN)], trace_id="ps-t2")
    assert all("shared-with" not in c for h in miss.handles for c in h.cues)
