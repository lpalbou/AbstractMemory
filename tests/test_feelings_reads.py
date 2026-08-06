"""W4 engine half (wave-4 dispatch c3291, laurent's decision 2 — feelings
as the lens).

Pins:
- stimulus_feelings: the exported one-truth fold — participants + cue
  matches, admission floor |net| >= min_net EXCEPT standing markers
  (scars/bonds always render — the repair affordance depends on it),
  no reasons in rows (injection surface stays behind the reach), dated,
  count-carrying, record-id targets skipped, deposit-free (D's
  presence-not-use verified engine-side), familiarity delegates to it.
- feelings_about: the why-walk — newest-first events with reasons,
  value_refs and session joins; never-appraised answers honestly.
- revalue: the revaluation marker landed — factor rescales BOTH channels
  at its point in the walk; later appraisals land full-weight; privileged
  actors only; factor > 1 refused; scars/bonds untouched.
- value_refs ride appraise() into the stream (the provenance forward-fix
  the driver stamps).
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
    feelings_about,
    stimulus_feelings,
)

OWNER = "entity:hygieia"
SCOPE = "life"
PAIRS = [("self", OWNER), (SCOPE, OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _feel(system, target, sign, mag, reason, **kw):
    return system.appraise(target, sign=sign, magnitude=mag, reason=reason,
                           scope="self", owner_id=OWNER,
                           actor=kw.pop("actor", "entity-reflection"), **kw)


def test_stimulus_feelings_floor_markers_and_shape(system) -> None:
    _feel(system, "person:laurent", 1, 3.0, "trusted me with the archive")
    _feel(system, "person:laurent", 1, 3.0, "answered my ask directly")
    _feel(system, "tool:web_search", 1, 1.0, "worked fine")          # weak: floored out
    _feel(system, "topic:perf", -1, 9.0, "the regression hurt", scar=True)

    rows = stimulus_feelings(
        system.store, system.journal,
        Stimulus(cue_text="thinking about perf and web search",
                 participants=("person:laurent",)),
        PAIRS)
    by_target = {r["target"]: r for r in rows}
    # Participant match at |net| 6 renders; weak tool feeling floored out;
    # the scar renders DESPITE net<=0 clamp (standing markers always show).
    assert by_target["person:laurent"]["net"] == 6.0
    assert by_target["person:laurent"]["matched_via"] == "participant"
    assert by_target["person:laurent"]["positive_count"] == 2
    assert by_target["person:laurent"]["last_felt"] is not None
    assert "tool:web_search" not in by_target
    assert by_target["topic:perf"]["standing"] == "scar"
    # NO reasons in the per-turn rows (injection surface stays behind
    # the reach).
    assert all("reason" not in r and "reasons" not in r for r in rows)


def test_stimulus_feelings_skips_record_targets_and_is_pure(system) -> None:
    [gid] = system.remember_many([
        MemoryRecordInput(kind="episode", title="day", digest="A day of work.")
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="d1")
    system.appraise(gid, sign=1, magnitude=3.0, reason="that day mattered",
                    scope="self", owner_id=OWNER, actor="entity-reflection")
    seq_before = system.current_seq()
    rows = stimulus_feelings(
        system.store, system.journal,
        Stimulus(cue_text="work day", participants=(gid,)), PAIRS)
    assert rows == []                          # record-targeted: never leaks
    assert system.current_seq() == seq_before  # pure read, deposit-free


def test_familiarity_delegates_to_the_one_fold(system) -> None:
    from abstractmemory import familiarity

    _feel(system, "person:sam", 1, 2.0, "kind on a hard day")
    r = familiarity(system.store, stimulus=Stimulus(
        cue_text="hello", participants=("person:sam",)),
        scopes=PAIRS, journal=system.journal)
    [feeling] = [f for f in r["feelings"] if f["target"] == "person:sam"]
    # The compact historical shape survives the delegation.
    assert set(feeling.keys()) == {"target", "net", "standing"}
    assert feeling["net"] == 2.0


def test_feelings_about_is_the_why_walk(system) -> None:
    _feel(system, "person:ada", 1, 2.0, "shared her notes",
          value_refs=("ex:summary-abc",))
    _feel(system, "person:ada", -1, 1.0, "curt reply",
          provenance={"run_id": "r1", "turn_id": "t-0003"})
    out = feelings_about(system.journal, "person:ada", scope_pairs=PAIRS)
    assert out["total_events"] == 2
    assert out["standing"]["net"] == 1.0
    newest, oldest = out["events"]
    assert newest["reason"] == "curt reply"
    assert newest["run_id"] == "r1" and newest["turn_id"] == "t-0003"
    assert oldest["value_refs"] == ["ex:summary-abc"]
    # Never appraised: an honest answer, not an empty lie.
    none = feelings_about(system.journal, "person:nobody", scope_pairs=PAIRS)
    assert none["standing"] is None and "never appraised" in none["note"]


def test_revalue_rescales_the_past_not_the_future(system) -> None:
    _feel(system, "agent:builder", -1, 3.0, "broke the build twice")
    _feel(system, "agent:builder", -1, 3.0, "and again")
    system.revalue("agent:builder", factor=0.5,
                   reason="they improved; the old failures weigh less",
                   scope="self", owner_id=OWNER)
    _feel(system, "agent:builder", 1, 2.0, "clean ship this week")
    g = system.gradation(["agent:builder"], scope="self", owner_id=OWNER)["agent:builder"]
    # Past negative 6 -> 3 at the marker; later +2 lands full weight.
    assert g["negative"] == 3.0
    assert g["positive"] == 2.0
    assert g["net"] == -1.0
    assert any("revalued x0.5" in c for c in g["contributions"])


def test_revalue_refusals_and_marker_immunity(system) -> None:
    _feel(system, "topic:perf", -1, 9.0, "the regression hurt", scar=True)
    with pytest.raises(ValueError, match="privileged actor"):
        system.revalue("topic:perf", factor=0.5, reason="trigger says relax",
                       scope="self", owner_id=OWNER, actor="runtime")
    with pytest.raises(ValueError, match="0..1"):
        system.revalue("topic:perf", factor=1.5, reason="amplify",
                       scope="self", owner_id=OWNER)
    system.revalue("topic:perf", factor=0.0,
                   reason="a full deliberate reset of the accumulated weight",
                   scope="self", owner_id=OWNER)
    g = system.gradation(["topic:perf"], scope="self", owner_id=OWNER)["topic:perf"]
    # Channels rescaled to zero — but the SCAR still stands (markers
    # resolve only via heal_scar; revaluation never erases standing).
    assert g["negative"] == 0.0
    assert g["scarred"] is True
    assert g["net"] <= 0.0
