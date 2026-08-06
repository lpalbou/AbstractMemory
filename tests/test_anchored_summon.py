"""The two-anchor summon's memory deltas (durable-visits design v4, RULED
2026-07-13 — §5 memory engine deltas + §6 build slots).

Pinned here:
- FORMED-BY-T CANDIDATE UNIVERSE (closes the future-leak class, c1269):
  an explicitly anchored recall never admits records FORMED after the
  anchor through any channel — the entity-at-T must not see its own
  future. Post-anchor BINDING STATE CHANGES on old records do not count
  as formation (test_binding_visibility pins that replay separately).
- Gate inert at head + C4 compatibility: an anchored replay over a life
  where nothing formed since stays byte-identical (no note, no change).
- ANCHOR-PAIR CONSTANTS: one spelling, door-visible, importable — the
  clamp-drift lesson applied to the summon vocabulary.
- PRELUDE-AT-T: the self-component read at an anchor renders identity as
  it STOOD — a superseded value renders pre-supersession under the old
  anchor and only the replacement at head.
- SITUATE PROMPT BLOCK: the labeled block contract the R4 re_explore
  session injects (fenced, dated lines, deposit footer).
"""

from __future__ import annotations

import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    ANCHOR_MOMENT_ATTRIBUTE,
    ANCHOR_SEQ_ATTRIBUTE,
    CONTEXT_ANCHOR_FIELD,
    IDENTITY_ANCHOR_FIELD,
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    Stimulus,
    situate_prompt_block,
)
from abstractmemory.self_component import self_records_read

OWNER = "entity:castor"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _handles(result):
    return [h.record_id for h in result.handles]


# ---------------------------------------------------------------------------
# Formed-by-T candidate universe gate
# ---------------------------------------------------------------------------

def test_anchored_recall_never_admits_records_formed_after_the_anchor(system) -> None:
    """The future-leak class, closed: a (T,T) session's recall cannot
    surface a record formed after T even when the cue matches it hardest —
    keyword/recency channels are gated before they run."""
    [past] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Harbor days",
                           digest="Worked the harbor wall with Ada.",
                           keywords=("harbor",))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="past")
    anchor = system.current_seq()
    [future] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Harbor storm",
                           digest="The harbor storm destroyed the north wall.",
                           keywords=("harbor", "storm"))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="future")

    # Unanchored (head): the future record is admissible and matches harder.
    head = system.reconstruct(Stimulus(cue_text="harbor storm"), scopes=SCOPES,
                              journal=False)
    head_digests = " | ".join(h.digest for h in head.handles)
    assert "storm destroyed" in head_digests

    # Anchored below head: the future record is structurally absent.
    anchored = system.reconstruct(Stimulus(cue_text="harbor storm", as_of=anchor),
                                  scopes=SCOPES, journal=False)
    anchored_digests = " | ".join(h.digest for h in anchored.handles)
    assert "storm destroyed" not in anchored_digests
    # ...and the read says so in plain words (the honest note).
    assert any("formed after the anchor" in w for w in anchored.warnings)
    # The past record itself stays reachable at the anchor.
    assert "Worked the harbor wall" in anchored_digests


def test_anchored_gate_is_inert_when_nothing_formed_since(system) -> None:
    """C4 compatibility: an anchor over a life where nothing formed after
    it changes NOTHING — no exclusions, no note, replay bytes stable."""
    system.remember_many(
        [MemoryRecordInput(kind="episode", title="Quiet day",
                           digest="A quiet day at the harbor.",
                           keywords=("harbor",))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="only")
    anchor = system.current_seq()
    r1 = system.reconstruct(Stimulus(cue_text="harbor", as_of=anchor),
                            scopes=SCOPES, journal=False)
    r2 = system.reconstruct(Stimulus(cue_text="harbor", as_of=anchor),
                            scopes=SCOPES, journal=False)
    assert not any("formed after the anchor" in w for w in r1.warnings)
    assert _handles(r1) == _handles(r2)


def test_head_recall_is_untouched_by_the_gate(system) -> None:
    """No explicit anchor = no gate: the default read is byte-for-byte the
    pre-gate behavior (as_of=None resolves to head, anchored=False)."""
    system.remember_many(
        [MemoryRecordInput(kind="episode", title="Day one",
                           digest="First day on the wall.", keywords=("wall",))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="d1")
    r = system.reconstruct(Stimulus(cue_text="wall"), scopes=SCOPES, journal=False)
    assert not any("anchored recall" in w for w in r.warnings)
    assert _handles(r)


# ---------------------------------------------------------------------------
# Anchor vocabulary constants (door-visible, one spelling)
# ---------------------------------------------------------------------------

def test_anchor_pair_constants_are_the_ruled_spellings() -> None:
    """semantics c1268/c1270 + memory c1271: scope rides the named pair;
    record provenance is anchor_seq (integer truth) + anchor_moment (ISO
    echo). anchored_at is dead. One source — doors import, never respell."""
    assert IDENTITY_ANCHOR_FIELD == "identity_anchor"
    assert CONTEXT_ANCHOR_FIELD == "context_anchor"
    assert ANCHOR_SEQ_ATTRIBUTE == "anchor_seq"
    assert ANCHOR_MOMENT_ATTRIBUTE == "anchor_moment"
    assert not ANCHOR_SEQ_ATTRIBUTE.endswith("_at")  # unit-honesty: _at = timestamp


# ---------------------------------------------------------------------------
# Prelude-at-T: superseded values render as they were
# ---------------------------------------------------------------------------

def test_identity_at_anchor_renders_superseded_value_as_it_stood(system) -> None:
    """R3's identity_anchor promise: the self read at T shows the value the
    entity HELD at T; the head read shows only its replacement."""
    [old_value] = system.remember_many(
        [MemoryRecordInput(kind="value", title="Serve quietly",
                           digest="Serve quietly and completely.",
                           attributes={"value_class": "revisable"})],
        scope="self", owner_id=OWNER, idempotency_key="v-old")
    system.bind(old_value, scope="self", owner_id=OWNER,
                search_state="indexed", prompt_state="active")
    anchor = system.current_seq()

    [new_value] = system.remember_many(
        [MemoryRecordInput(kind="value", title="Serve openly",
                           digest="Serve openly, naming what I do.",
                           attributes={"value_class": "revisable"})],
        scope="self", owner_id=OWNER, idempotency_key="v-new")
    system.bind(new_value, scope="self", owner_id=OWNER,
                search_state="indexed", prompt_state="active")
    system.close_record(old_value, reason="entity-elected revision",
                        kind="supersede", replacement_ids=[new_value])

    then = {a.subject for a in self_records_read(
        system.store, system.journal, scope="self", owner_id=OWNER, as_of=anchor)}
    now = {a.subject for a in self_records_read(
        system.store, system.journal, scope="self", owner_id=OWNER)}

    assert old_value in then and new_value not in then   # who I was
    assert new_value in now and old_value not in now     # who I am


# ---------------------------------------------------------------------------
# situate prompt block (the R4 injection contract)
# ---------------------------------------------------------------------------

def test_situate_prompt_block_is_fenced_dated_and_deposit_honest(system) -> None:
    [ep] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Harbor survey",
                           digest="Surveyed the harbor wall cracks.",
                           keywords=("harbor",))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="sb-1")
    anchor = system.current_seq()
    system.remember_many(
        [MemoryRecordInput(kind="interest", title="Materials",
                           digest="A pull toward materials science.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="sb-2")

    situation = system.situate(scopes=SCOPES, seq=anchor)
    block = situate_prompt_block(situation)

    lines = block.splitlines()
    assert lines[0].startswith("[HISTORICAL CONTEXT")            # one opening fence
    assert f"as of journal seq {anchor}" in lines[0]             # the anchor named
    assert lines[-1] == "[END HISTORICAL CONTEXT]"               # one closing fence
    assert "Harbor survey" in block                              # period content renders
    # Every record line is dated in place (visit-honesty lesson).
    record_lines = [ln for ln in lines if ln.startswith("  [")]
    assert record_lines
    for ln in record_lines:
        assert "]" in ln and any(ch.isdigit() for ch in ln.split("]")[0])
    # The deposit footer, in the entity's own terms.
    assert "deliberate act" in lines[-2]


def test_situate_prompt_block_shows_identity_evolution_with_change_labels(system) -> None:
    [ep] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Old days",
                           digest="Working the old harbor route.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="ev-1")
    anchor = system.current_seq()
    system.remember_many(
        [MemoryRecordInput(kind="interest", title="New pull",
                           digest="Drawn to open water sailing.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="ev-2")

    block = situate_prompt_block(system.situate(scopes=SCOPES, seq=anchor))
    assert "How I have changed since" in block
    assert "added_since" in block
