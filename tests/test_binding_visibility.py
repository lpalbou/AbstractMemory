"""Scope-binding visibility enforcement in ranked retrieval (backlog 0017).

The facade folds ScopeBinding events ≤ as_of per searched (scope, owner):
hidden records leave ranked retrieval (id-lookups bypass the fold — audit
completeness), re-binding indexed restores them, and handles report the
honest folded binding string. Runs on the shared conftest `stack`/`system`
fixtures (both layer-1 stacks, 0011 parity).
"""

from __future__ import annotations

from typing import List

from abstractmemory import MemorySystem, Stimulus, TripleAssertion, TripleQuery

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _ts(i: int) -> str:
    return f"2026-07-05T10:{i:02d}:00.000000+00:00"


def _seed(system: MemorySystem) -> None:
    system.add([
        TripleAssertion(
            subject="alice", predicate="wrote", object="report", scope=SCOPE,
            owner_id=OWNER, observed_at=_ts(1), assertion_id="m-old",
        ),
        TripleAssertion(
            subject="alice", predicate="filed", object="report copy", scope=SCOPE,
            owner_id=OWNER, observed_at=_ts(2), assertion_id="m-new",
        ),
    ])


def _ids(result) -> List[str]:
    return [h.record_id for h in result.handles]


def test_hidden_binding_excluded_from_ranked_retrieval_but_not_id_lookup(system, stack) -> None:
    """A record whose latest binding is search_state="hidden" leaves ranked
    retrieval, while direct id-lookup keeps bypassing the fold BY DESIGN
    (audit completeness — same rule as closures)."""
    store, _ = stack
    _seed(system)
    assert "m-old" in _ids(system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES))
    anchor_before = system.current_seq()

    system.bind(
        "m-old", scope=SCOPE, owner_id=OWNER, search_state="hidden", reason="operator quarantine",
    )

    after = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    assert "m-old" not in _ids(after)
    # Direct id-lookup still returns the record (audit completeness).
    rows = store.query(TripleQuery(assertion_ids=("m-old",)))
    assert [a.assertion_id for a in rows] == ["m-old"]

    # A replay anchored BEFORE the binding still sees the record: the
    # bindings fold is ≤ as_of like every other journal-derived signal.
    replayed = system.reconstruct(
        Stimulus(cue_text="alice report", as_of=anchor_before), scopes=SCOPES
    )
    assert "m-old" in _ids(replayed)


def test_rebinding_indexed_restores_ranked_retrieval(system) -> None:
    """Latest-wins fold: hidden -> indexed re-binding restores visibility."""
    _seed(system)
    system.bind("m-old", scope=SCOPE, owner_id=OWNER, search_state="hidden", reason="quarantine")
    assert "m-old" not in _ids(system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES))

    system.bind("m-old", scope=SCOPE, owner_id=OWNER, search_state="indexed", reason="quarantine lifted")
    assert "m-old" in _ids(system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES))


def test_binding_string_surfaces_on_handles(system) -> None:
    """MemoryHandle.binding is the honest folded "{search_state}+{prompt_state}"
    for bound records; unbound records keep the documented default."""
    _seed(system)
    system.bind(
        "m-old", scope=SCOPE, owner_id=OWNER,
        search_state="indexed", prompt_state="active", reason="promoted to prompt",
    )

    r = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    by_id = {h.record_id: h for h in r.handles}
    assert by_id["m-old"].binding == "indexed+active"
    assert by_id["m-new"].binding == "indexed+inactive"  # unbound default
