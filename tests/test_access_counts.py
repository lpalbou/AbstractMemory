"""The maintainer's two-count access model (design authority, his fork):
GLOBAL access count — absolute selected-use, never decays, "at the end of
your life it could represent 'what matters'" — on records AND edges, plus
its surfacing on handles beside the TEMPORAL count (the activation fold).
"""

from __future__ import annotations

from typing import Any

from abstractmemory import RecallBudget, Stimulus, TripleAssertion
from abstractmemory.records import MemoryRecordInput

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _assertion(aid: str, s: str, p: str, o: str, t: int, **attrs: Any) -> TripleAssertion:
    return TripleAssertion(subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
                           observed_at=f"2026-07-05T10:{t:02d}:00.000000+00:00",
                           attributes=dict(attrs), assertion_id=aid)


_WARM_SEQ = iter(range(10_000))


def _warm(system, times: int, ids: list) -> None:
    # Unique trace ids across calls: commit_selection is idempotent by
    # trace_id, so reused ids would silently replay as no-ops.
    for _ in range(times):
        system.commit_selection(f"t-warm-{next(_WARM_SEQ)}", ids)


# ---------------------------------------------------------------------------
# Journal layer: record + pair global counts (both backends via stack)
# ---------------------------------------------------------------------------


def test_global_counts_records_and_pairs_never_decay(system, stack) -> None:
    _, journal = stack
    system.add([
        _assertion("m-a", "alice", "wrote", "fusion report", 1),
        _assertion("m-b", "alice", "filed", "fusion appendix", 2),  # shares "alice": pair trail
        _assertion("m-c", "carol", "likes", "tea", 3),
    ])
    _warm(system, 3, ["m-a", "m-b"])  # 3 selected each + 3 co_selected pair deposits

    assert journal.selected_count("m-a") == 3
    assert journal.selected_count("m-b") == 3
    assert journal.selected_count("m-c") == 0            # honest zero, no deposits
    # Pairs: canonical + order-insensitive.
    assert journal.pair_selected_count(("m-a", "m-b")) == 3
    assert journal.pair_selected_count(("m-b", "m-a")) == 3
    assert journal.pair_selected_count(("m-a", "m-c")) == 0

    # NEVER DECAYS: a refocus and a pile of other activity later, the global
    # count only grew — unlike activation, which the same history decays.
    system.refocus(reason="topic shift", scope=SCOPE, owner_id=OWNER)
    _warm(system, 5, ["m-c"])
    assert journal.selected_count("m-a") == 3            # unchanged by others' use
    assert journal.selected_count("m-c") == 5
    assert journal.pair_selected_count(("m-a", "m-b")) == 3


def test_global_counts_anchor_to_until_seq_for_replay(system, stack) -> None:
    _, journal = stack
    system.add([_assertion("m-a", "alice", "wrote", "report", 1),
                _assertion("m-b", "alice", "filed", "copy", 2)])
    _warm(system, 2, ["m-a", "m-b"])
    anchor = journal.current_seq()
    _warm(system, 3, ["m-a", "m-b"])

    assert journal.selected_count("m-a") == 5
    assert journal.selected_count("m-a", until_seq=anchor) == 2
    assert journal.pair_selected_count(("m-a", "m-b")) == 5
    assert journal.pair_selected_count(("m-a", "m-b"), until_seq=anchor) == 2
    assert journal.selected_count("m-a", until_seq=0) == 0


# ---------------------------------------------------------------------------
# Facade: access_counts (both namespaces, works-or-loud)
# ---------------------------------------------------------------------------


def test_access_counts_read_api(system) -> None:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="lesson", title="Batching", digest="batch the sensor writes")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="k-ac")
    system.add([_assertion("m-a", "alice", "wrote", "fusion report", 1)])
    _warm(system, 2, [gid, "m-a"])  # graph id accepted at commit too

    out = system.access_counts(record_ids=[gid, "m-a"], pairs=[(gid, "m-a")])
    assert out["records"] == {gid: 2, "m-a": 2}          # keys AS PASSED (graph id kept)
    # No shared term, no recorded edge — but the two records served the
    # same two moments together, and since the co-use rule (maintainer,
    # 2026-07-07) that is exactly what pair_selected_count counts.
    assert out["pairs"] == {(gid, "m-a"): 2}

    # Empty request halves are explicit, not "everything".
    assert system.access_counts() == {"records": {}, "pairs": {}}

    import pytest
    with pytest.raises(ValueError, match="ghost"):
        system.access_counts(record_ids=["ghost"])       # works-or-loud, like activation()
    with pytest.raises(ValueError, match="pairs entries"):
        system.access_counts(pairs=[("only-one",)])      # malformed pair shape


def test_access_counts_pair_read_matches_journal(system, stack) -> None:
    _, journal = stack
    system.add([_assertion("m-a", "alice", "wrote", "fusion report", 1),
                _assertion("m-b", "alice", "filed", "fusion appendix", 2)])
    _warm(system, 4, ["m-a", "m-b"])
    out = system.access_counts(pairs=[("m-b", "m-a")])   # reversed order accepted
    assert out["pairs"] == {("m-b", "m-a"): 4}
    assert journal.pair_selected_count(("m-a", "m-b")) == 4


# ---------------------------------------------------------------------------
# Surfacing: provenance["global_count"] beside the temporal count
# ---------------------------------------------------------------------------


def test_handles_carry_global_count_beside_temporal_activation(system) -> None:
    system.add([
        _assertion("m-hot", "alice", "wrote", "fusion report", 1),
        _assertion("m-cold", "bob", "drafted", "fusion appendix", 2),
    ])
    _warm(system, 3, ["m-hot"])

    r = system.reconstruct(Stimulus(cue_text="fusion"), scopes=SCOPES, journal=False)
    by_id = {h.record_id: h for h in r.handles}
    assert by_id["m-hot"].provenance["global_count"] == 3
    assert by_id["m-cold"].provenance["global_count"] == 0
    # The TEMPORAL count is the activation decomposition on the same handle.
    assert by_id["m-hot"].activation["base_level"] > by_id["m-cold"].activation["base_level"]

    # as_of replay sees the count AS OF the anchor (C4 discipline).
    anchor = system.current_seq()
    _warm(system, 2, ["m-hot"])
    replay = system.reconstruct(Stimulus(cue_text="fusion", as_of=anchor),
                                scopes=SCOPES, journal=False)
    assert {h.record_id: h.provenance["global_count"] for h in replay.handles}["m-hot"] == 3
    now = system.reconstruct(Stimulus(cue_text="fusion"), scopes=SCOPES, journal=False)
    assert {h.record_id: h.provenance["global_count"] for h in now.handles}["m-hot"] == 5
