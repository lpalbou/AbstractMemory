"""explain_recall() — the recall-explanation serving contract (backlog 0042).

Golden traces pinned: selected, budget-cut (dropped), candidate-only,
absent (with formed-after-trace timing + per-searched-scope diagnosis),
never-formed ids, no-traces journals, and the honesty rules — activation
always reads {"recorded": false}; a record outside the trace's bounded
candidate list reads relevance {"recorded": false} with the bound named
(old/synthetic traces carry the honest null, never a fresh number).
Pure read; explaining is not use.
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
    RecallBudget,
    ReconstructionTrace,
    Stimulus,
    explain_recall,
)

OWNER = "entity:explain-test"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def _form(system: MemorySystem, key: str, title: str, digest: str, **kw) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title=title, digest=digest, **kw)],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def test_selected_record_explains_with_shelf_position_and_recorded_relevance(system) -> None:
    _form(system, "e1", "Alpha", "The alpha event happened at the harbor.",
          keywords=("alpha",))
    _form(system, "e2", "Beta", "The beta event happened at the archive.",
          keywords=("beta",))
    r = system.reconstruct(Stimulus(cue_text="alpha event harbor"), scopes=SCOPES)
    top = r.handles[0]

    out = system.explain_recall(top.record_id)
    assert out["status"] == "selected"
    assert out["trace"]["trace_id"] == r.trace_id
    assert out["trace"]["searched_scopes"] == [{"scope": SCOPE, "owner_id": OWNER}]
    assert out["shelf"]["position"] == 1
    assert out["shelf"]["selected_count"] == len(r.handles)
    # Relevance parts come from the trace's own candidate record.
    assert out["relevance"]["recorded"] is True
    assert out["relevance"]["parts"]
    # HONESTY: activation was never journaled per candidate.
    assert out["activation"]["recorded"] is False
    assert "never" in out["activation"]["note"] or "not recorded" in out["activation"]["note"]
    # Origin is the formation identity.
    assert out["origin"]["formed"] is True
    assert out["origin"]["kind"] == "episode"
    # Budgets are served verbatim from the trace.
    assert out["budgets"]["shelf_size"] == 12
    assert "candidates_considered" in out["budget_spent"]


def test_budget_cut_record_explains_as_dropped_with_reason(system) -> None:
    for i in range(8):
        _form(system, f"h{i}", f"Harbor {i}",
              f"Harbor telling number {i}, tide and quay and mast.",
              keywords=("harbor",))
    r = system.reconstruct(
        Stimulus(cue_text="harbor tide quay"), scopes=SCOPES,
        budget=RecallBudget(shelf_size=2, token_budget=400))
    assert r.dropped, "the tight shelf must cut something"
    cut = dict(r.dropped[0])

    out = system.explain_recall(cut["record_id"], trace_id=r.trace_id)
    assert out["status"] == "dropped"
    assert out["reason"] == cut.get("reason")
    assert out["shelf"]["selected_count"] == len(r.handles)
    # A dropped candidate still carries its rank in the bounded list when
    # the trace retained it.
    if "candidate_rank" in out["shelf"]:
        assert out["shelf"]["candidate_rank"] >= 1
        assert "rank_note" in out["shelf"]


def test_absent_record_gets_timing_and_per_scope_diagnosis(system) -> None:
    _form(system, "e1", "Alpha", "The alpha event happened.", keywords=("alpha",))
    r = system.reconstruct(Stimulus(cue_text="alpha"), scopes=SCOPES)
    late = _form(system, "late", "Later record",
                 "Formed after the recall ran.", keywords=("later",))

    out = system.explain_recall(late, trace_id=r.trace_id)
    assert out["status"] == "absent"
    notes = " ".join(out["diagnosis"]["note"])
    assert "formed AFTER this recall" in notes
    # Adversary P1-2: a record that never raced must NOT get "it lost the
    # shelf race" — the structural diagnosis is skipped, and the note says
    # why, instead of serving a factually false explanation.
    assert out["diagnosis"]["by_scope"] == []
    assert "never raced" in notes

    # An absent record that EXISTED at recall time gets the full per-scope
    # structural diagnosis (the timing skip applies only to formed-after).
    # Deterministic absence: it lives in a scope the recall never searched.
    [elsewhere] = system.remember_many(
        [MemoryRecordInput(kind="interest", title="Elsewhere",
                           digest="Lives in self scope, unreachable here.")],
        scope="self", owner_id=OWNER, idempotency_key="elsewhere")
    r2 = system.reconstruct(Stimulus(cue_text="alpha"), scopes=SCOPES)
    out2 = system.explain_recall(elsewhere, trace_id=r2.trace_id)
    assert out2["status"] == "absent"
    by_scope = out2["diagnosis"]["by_scope"]
    assert [d["scope"] for d in by_scope] == [SCOPE]
    assert any("stored under scope" in reason for reason in by_scope[0]["reasons"])


def test_never_formed_id_is_an_honest_origin_answer(system) -> None:
    _form(system, "e1", "Alpha", "The alpha event happened.", keywords=("alpha",))
    system.reconstruct(Stimulus(cue_text="alpha"), scopes=SCOPES)

    out = system.explain_recall("ex:ghost-record")
    assert out["status"] == "absent"
    assert out["origin"]["formed"] is False
    ghost_reasons = " ".join(out["diagnosis"]["by_scope"][0]["reasons"])
    assert "never formed here" in ghost_reasons


def test_no_traces_and_unknown_trace_id(system) -> None:
    gid = _form(system, "e1", "Alpha", "The alpha event happened.")
    out = system.explain_recall(gid)
    assert out["status"] == "no_recall_recorded"
    assert out["origin"]["formed"] is True

    with pytest.raises(ValueError, match="no trace"):
        system.explain_recall(gid, trace_id="trace-that-never-ran")


def test_probe_traces_explain_too(system) -> None:
    gid = _form(system, "e1", "Alpha", "The alpha event happened.",
                keywords=("alpha",))
    p = system.probe(Stimulus(cue_text="alpha event"), scopes=SCOPES,
                     reason="explain check")
    assert p.hits
    out = system.explain_recall(p.hits[0].record_id, trace_id=p.trace_id)
    assert out["trace"]["trace_kind"] == "probe"
    assert out["status"] == "selected"
    assert gid  # formed above


def test_outside_the_bounded_candidate_list_reads_honest_null(system) -> None:
    """A synthetic trace shaped like a reserved-lane admission (selected,
    but not in the bounded candidate list — the self/STM shape, also the
    old-trace shape): relevance must read recorded=false naming the bound,
    never a recomputed number."""
    gid = _form(system, "e1", "Alpha", "The alpha event happened.")
    trace = ReconstructionTrace(
        trace_id="trace-synthetic-1",
        trace_kind="reconstruct",
        query_fingerprint="synthetic",
        need={},
        searched_scopes=({"scope": SCOPE, "owner_id": OWNER},),
        selected=(gid,),
        candidates=(),  # bounded list did not retain the record
    )
    system.journal.append_trace(trace)

    out = system.explain_recall(gid, trace_id="trace-synthetic-1")
    assert out["status"] == "selected"
    assert out["relevance"]["recorded"] is False
    assert "bounded candidate list" in out["relevance"]["note"]
    assert out["shelf"] == {"selected_count": 1, "position": 1}


def test_expand_trace_empty_parts_read_not_recorded(system) -> None:
    """Adversary P1-1: expand traces retain candidates with scores={} BY
    DESIGN — key presence must not claim per-channel parts were recorded."""
    root = _form(system, "e1", "Alpha root", "The alpha event happened.",
                 keywords=("alpha",))
    linked = _form(system, "e2", "Alpha detail",
                   "A detail hanging off the alpha event.",
                   keywords=("alpha",), edges=(("mentions", root),))
    p = system.probe(Stimulus(cue_text="alpha event"), scopes=SCOPES,
                     reason="expand check")
    assert p.hits
    ex = system.probe_expand([p.hits[0].record_id], scopes=SCOPES,
                             reason="follow the edge",
                             parent_trace_id=p.trace_id)
    assert ex.hits, "expand must find the linked record"
    out = system.explain_recall(ex.hits[0].record_id, trace_id=ex.trace_id)
    assert out["trace"]["trace_kind"] == "expand"
    assert out["relevance"]["recorded"] is False
    assert "no per-channel parts" in out["relevance"]["note"]
    assert linked  # formed above


def test_selected_record_never_leaks_scores_into_history_events(system) -> None:
    """Parity pin for the shared classifier refactor: a record BOTH selected
    and in the candidate list keeps recall_history's original event shape —
    scores itemize candidate_only events only."""
    _form(system, "e1", "Alpha", "The alpha event happened.", keywords=("alpha",))
    r = system.reconstruct(Stimulus(cue_text="alpha event"), scopes=SCOPES)
    top = r.handles[0].record_id
    hist = system.recall_history(top)
    selected_events = [e for e in hist["events"] if e["status"] == "selected"]
    assert selected_events
    for event in selected_events:
        assert "scores" not in event and "candidate_rank" not in event
    # explain_recall, by contrast, IS the deep per-trace view: it serves the
    # recorded parts for the same record.
    deep = system.explain_recall(top, trace_id=r.trace_id)
    assert deep["relevance"]["recorded"] is True


def test_explaining_is_not_use_and_writes_nothing(system) -> None:
    gid = _form(system, "e1", "Alpha", "The alpha event happened.",
                keywords=("alpha",))
    r = system.reconstruct(Stimulus(cue_text="alpha"), scopes=SCOPES)
    seq_before = system.journal.current_seq()
    count_before = system.journal.selected_count(gid)

    system.explain_recall(gid, trace_id=r.trace_id)
    system.explain_recall("ex:ghost-record")

    assert system.journal.current_seq() == seq_before
    assert system.journal.selected_count(gid) == count_before


def test_loud_validation(system) -> None:
    with pytest.raises(ValueError, match="requires a record id"):
        explain_recall(system.store, system.journal, "")
