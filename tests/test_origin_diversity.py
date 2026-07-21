"""M-F origin-diversity fold (improving-entity-capabilities WAVE 2).

Pins the frozen return contract {counted, excluded_self, voices, dominant
{source, actor, label, count, share, sessions}, note} and the honesty
rules: pure read (data or None, zero policy), self-admission handles
excluded (present by right — counting them would fire the label on every
entity shelf), kind-fallback voices for source-less records (dreams must
not merge into one unlabeled mega-voice), host-injected labels (raw
engraved string when absent — never invented), abstention below the
counted floor (a two-seat shelf cannot be "mostly" anything).
"""

from __future__ import annotations

import pytest

from abstractmemory import (
    MemorySystem,
    ORIGIN_DOMINANCE_FLOOR,
    ORIGIN_MIN_COUNTED,
    Stimulus,
    origin_diversity,
)
from abstractmemory.records import MemoryRecordInput

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]

# The runtime's entity-facing channel words, injected as a host would
# (the map is HOST vocabulary — this test uses a copy as an injection
# EXAMPLE, not as a second source of truth).
LABELS = {
    "entity-chat-v1": "lived conversation",
    "entity-chat-reflection-v1": "your own reflection",
}


def _handle(source: str = "", actor: str = "", session: str = "",
            kind: str = "episode", admission: str = "stimulus") -> dict:
    """A handle dict shaped exactly like MemoryHandle.to_dict() output —
    the form the runtime renders from."""
    ap = {}
    if source:
        ap["source"] = source
    if actor:
        ap["actor"] = actor
    if session:
        ap["run_id"] = session
    return {
        "record_id": f"row-{source}-{session}-{id(object())}",
        "kind": kind,
        "admission": admission,
        "provenance": {"assertion_provenance": ap} if ap else {},
    }


# ---------------------------------------------------------------------------
# the fold itself
# ---------------------------------------------------------------------------


def test_dominant_voice_note_with_injected_labels() -> None:
    """The motivating shape: most seats one voice — the note carries the
    numbers, the host's label, the session spread, and the house phrase."""
    handles = (
        [_handle("entity-chat-reflection-v1", session=f"chat-owntime-{i}") for i in range(4)]
        + [_handle("entity-chat-v1", session="chat-visit-1"),
           _handle("entity-chat-v1", session="chat-visit-2")]
    )
    out = origin_diversity(handles, labels=LABELS)
    assert out is not None
    assert out["counted"] == 6
    assert out["excluded_self"] == 0
    assert out["voices"] == 2
    dom = out["dominant"]
    assert dom["source"] == "entity-chat-reflection-v1"
    assert dom["label"] == "your own reflection"
    assert dom["count"] == 4
    assert dom["share"] == pytest.approx(4 / 6, abs=1e-4)
    assert dom["sessions"] == 4
    assert out["note"] == (
        "4 of these 6 memories come from one voice (your own reflection, "
        "across 4 sessions) - repetition is not corroboration."
    )


def test_diverse_shelf_gets_the_diverse_note() -> None:
    handles = [
        _handle("entity-chat-v1", session="a"),
        _handle("entity-chat-reflection-v1", session="b"),
        _handle("diary-projection", session="c"),
    ]
    out = origin_diversity(handles, labels=LABELS)
    assert out is not None
    assert out["voices"] == 3
    assert out["dominant"]["share"] == pytest.approx(1 / 3, abs=1e-4)
    assert out["note"] == "3 memories from 3 distinct voices - no single origin dominates."


def test_single_voice_shelf_names_the_retelling() -> None:
    handles = [_handle("entity-chat-reflection-v1", session=f"day-{i}") for i in range(3)]
    out = origin_diversity(handles, labels=LABELS)
    assert out is not None
    assert out["voices"] == 1
    assert out["note"] == (
        "all 3 of these memories come from one voice (your own reflection) "
        "across 3 sessions - one origin retold, not 3 witnesses."
    )


# ---------------------------------------------------------------------------
# exclusions, fallbacks, abstention
# ---------------------------------------------------------------------------


def test_self_admission_handles_are_excluded_from_the_fold() -> None:
    """Identity presence is posture, not match — identity records share one
    origin by construction, and counting them would fire the label on
    every entity shelf (habituation)."""
    handles = (
        [_handle(kind="value", admission="self") for _ in range(6)]
        + [_handle("entity-chat-v1", session="a"),
           _handle("entity-chat-reflection-v1", session="b"),
           _handle("diary-projection", session="c")]
    )
    out = origin_diversity(handles, labels=LABELS)
    assert out is not None
    assert out["excluded_self"] == 6
    assert out["counted"] == 3
    assert out["voices"] == 3


def test_sourceless_records_fold_by_kind_never_one_mega_voice() -> None:
    """Dreams and engram-era records carry no provenance source; folding
    them into ONE unlabeled voice would fake dominance. kind-keyed voices
    keep them apart, and the kind word is the honest fallback label."""
    handles = (
        [_handle(kind="dream"), _handle(kind="dream")]
        + [_handle(kind="episode"), _handle("entity-chat-v1", session="a")]
    )
    out = origin_diversity(handles)  # no labels injected
    assert out is not None
    assert out["voices"] == 3  # kind:dream, kind:episode, entity-chat-v1
    assert out["dominant"]["source"] == "kind:dream"
    assert out["dominant"]["label"] == "dream"


def test_raw_source_is_the_label_fallback_never_invented() -> None:
    handles = [_handle("entity-visit-run-v0", session=f"v-{i}") for i in range(3)]
    out = origin_diversity(handles)  # host injected nothing for this source
    assert out is not None
    assert out["dominant"]["label"] == "entity-visit-run-v0"


def test_abstains_below_the_counted_floor() -> None:
    handles = [_handle("entity-chat-v1"), _handle("entity-chat-v1")]
    assert origin_diversity(handles) is None            # 2 < ORIGIN_MIN_COUNTED
    assert origin_diversity([]) is None
    assert origin_diversity([_handle(kind="value", admission="self")] * 9) is None
    assert ORIGIN_MIN_COUNTED == 3                      # declared tunable, pinned
    assert ORIGIN_DOMINANCE_FLOOR == 0.6                # live-calibrated (module docstring)


def test_tunable_validation_is_loud() -> None:
    handles = [_handle("entity-chat-v1") for _ in range(3)]
    with pytest.raises(ValueError, match="min_counted"):
        origin_diversity(handles, min_counted=0)
    with pytest.raises(ValueError, match="dominance_floor"):
        origin_diversity(handles, dominance_floor=0.0)
    with pytest.raises(ValueError, match="dominance_floor"):
        origin_diversity(handles, dominance_floor=1.5)


def test_count_ties_go_to_first_seen_shelf_order() -> None:
    handles = [
        _handle("entity-chat-v1", session="a"),
        _handle("entity-chat-reflection-v1", session="b"),
        _handle("entity-chat-v1", session="c"),
        _handle("entity-chat-reflection-v1", session="d"),
    ]
    out = origin_diversity(handles, labels=LABELS)
    assert out is not None
    assert out["dominant"]["source"] == "entity-chat-v1"  # first seen wins the tie


def test_pure_read_never_mutates_handles() -> None:
    handles = [_handle("entity-chat-v1", session="a") for _ in range(3)]
    import copy
    before = copy.deepcopy(handles)
    origin_diversity(handles, labels=LABELS)
    assert handles == before


# ---------------------------------------------------------------------------
# real pipeline: MemoryHandle OBJECTS from reconstruct(), not synthetic dicts
# ---------------------------------------------------------------------------


def test_fold_over_real_reconstruction_handles(stack) -> None:
    """End to end over the real shelf: records formed with distinct
    provenance voices, reconstructed, folded — the object path (getattr)
    and the to_dict path must agree."""
    store, journal = stack
    system = MemorySystem(store=store, journal=journal)
    inputs = []
    for i in range(4):
        inputs.append(MemoryRecordInput(
            kind="episode", title=f"harbor thought {i}",
            digest=f"Circled the harbor idea again, retelling {i}.",
            provenance={"source": "entity-chat-reflection-v1",
                        "run_id": f"chat-owntime-{i}"}))
    inputs.append(MemoryRecordInput(
        kind="episode", title="harbor visit",
        digest="Talked about the harbor with a visitor.",
        provenance={"source": "entity-chat-v1", "run_id": "chat-visit-9"}))
    system.remember_many(inputs, scope=SCOPE, owner_id=OWNER, idempotency_key="mf-real")

    r = system.reconstruct(Stimulus(cue_text="harbor retelling idea"),
                           scopes=SCOPES, journal=False)
    assert len(r.handles) == 5

    out_objects = origin_diversity(r.handles, labels=LABELS)
    out_dicts = origin_diversity([h.to_dict() for h in r.handles], labels=LABELS)
    assert out_objects == out_dicts
    assert out_objects is not None
    assert out_objects["counted"] == 5
    assert out_objects["voices"] == 2
    dom = out_objects["dominant"]
    assert dom["source"] == "entity-chat-reflection-v1"
    assert dom["count"] == 4 and dom["sessions"] == 4
    assert "repetition is not corroboration" in out_objects["note"]
