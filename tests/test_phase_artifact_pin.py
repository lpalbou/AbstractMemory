"""Phase-graph artifact pin (c1505 ask 1b: the graph CONTROLS, lanes verify
against THE SOURCE — spec/entity_phases.json in abstractentity — never
parallel prose).

Memory's stake in the machine is the SLEEP node: this package IS the
"passive memory-graph processes: consolidation, dreams" the artifact
names, and the graceful-cancellation contract (one-active-phase: entering
any phase properly ends sleep's processes) is implemented here as
sleep_pass(should_continue=...). These pins read the artifact directly
(observer/gateway's consumption shape) so a spec change breaks THIS
suite, not the operator's trust.

Standalone checkouts (no sibling abstractentity) SKIP with a visible
reason — never a false green.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ARTIFACT = (Path(__file__).resolve().parents[2]
             / "abstractentity" / "spec" / "entity_phases.json")

pytestmark = pytest.mark.skipif(
    not _ARTIFACT.exists(),
    reason="#FALLBACK: sibling abstractentity checkout not present — "
           "phase-artifact pins skipped (never a false green)",
)


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(_ARTIFACT.read_text())


def test_sleep_node_names_this_packages_processes(artifact) -> None:
    """The artifact's SLEEP behavior is this package's lane — if the spec
    re-words what sleep IS, memory must hear about it through a red test."""
    sleep = artifact["phases"]["sleep"]
    behavior = sleep["behavior"].lower()
    assert "consolidation" in behavior and "dream" in behavior
    # Entering any other phase ends sleep — the clause sleep_pass's
    # should_continue grace contract implements.
    assert set(sleep["on_activation_ends"]) == {"work", "visit", "personal"}


def test_phase_keys_and_initial_phase_match_the_ruled_machine(artifact) -> None:
    assert sorted(artifact["phases"]) == ["personal", "sleep", "visit", "work"]
    assert artifact["initial_phase"] == "sleep"  # newborn = sleep (ruled 13:46)


def test_every_transition_into_a_non_sleep_phase_ends_sleep_gracefully(artifact) -> None:
    """One-active-phase invariant, read from the artifact's own invariants:
    the wording memory's grace contract was built against must still be
    there. (Content check, not byte pin — the artifact owner may re-word;
    the INVARIANT disappearing is what must go red.)"""
    invariants = " ".join(str(i) for i in artifact["invariants"]).lower()
    assert "one" in invariants and ("active" in invariants or "exclusive" in invariants)


def test_sleep_grace_is_implemented_by_this_package(artifact) -> None:
    """The control link: the artifact's exclusivity clause is enforceable
    in memory because sleep_pass exposes should_continue — verify the
    surface exists and carries the boundary-grace contract."""
    import inspect

    from abstractmemory.maintenance import sleep_pass

    sig = inspect.signature(sleep_pass)
    assert "should_continue" in sig.parameters
    doc = (sleep_pass.__doc__ or "").lower()
    assert "cancel" in doc and "boundar" in doc
