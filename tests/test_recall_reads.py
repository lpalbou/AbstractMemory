"""Recall-decision reads + concept anchoring (fork 605 + memory_anchor.rs).

Contracts pinned:
- recall_history classifies a record's part per trace (selected / dropped /
  candidate_only) and counts absences; probe traces join the history;
- absence_diagnosis names STRUCTURAL barriers in mechanism terms (closed,
  hidden, wrong scope, no keywords, no vector) and never guesses;
- concept_terms collapses variant spellings to one concept set;
- concept expansion in PASSIVE recall is opt-in (config), admits records
  the cue never named, and the golden default stays byte-stable (OFF).
"""

from __future__ import annotations

import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    ConceptAnchorTuning,
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    ReconstructConfig,
    Stimulus,
    concept_terms,
)

OWNER = "entity:reads-test"
SCOPE = "life"
SCOPES = [(SCOPE, OWNER)]


@pytest.fixture()
def system():
    return MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())


def test_concept_terms_collapse_variants() -> None:
    for text in ("auto memory", "auto-memory", "autoMemory", "auto_memory"):
        terms = concept_terms(text)
        assert "auto" in terms and "memory" in terms and "auto_memory" in terms, text
    # Identifier shapes split AND keep the joined bigram.
    assert "prompt_cache" in concept_terms("promptCache staging")


def test_recall_history_classifies_selected_and_dropped(system) -> None:
    ids = system.remember_many([
        MemoryRecordInput(kind="episode", title="Alpha", digest="The alpha event happened."),
        MemoryRecordInput(kind="episode", title="Beta", digest="The beta event happened."),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="h1")
    r = system.reconstruct(Stimulus(cue_text="alpha event"), scopes=SCOPES)
    # Row ids are the trace currency; map graph ids -> row ids via handles.
    selected_rows = list(r.handles)
    assert selected_rows
    hist = system.recall_history(selected_rows[0].record_id)
    assert hist["counts"]["selected"] >= 1
    assert any(e["status"] == "selected" for e in hist["events"])
    # Probe traces join the history.
    p = system.probe(Stimulus(cue_text="beta event"), scopes=SCOPES,
                     reason="history check")
    if p.hits:
        hist2 = system.recall_history(p.hits[0].record_id)
        assert any(e["trace_kind"] == "probe" for e in hist2["events"])


def test_absence_diagnosis_names_structural_barriers(system) -> None:
    [rid] = system.remember_many([
        MemoryRecordInput(kind="episode", title="Closed one", digest="Will be closed."),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="d1")
    system.close_record(rid, reason="test: retract")
    out = system.recall_history(rid, scope=SCOPE, owner_id=OWNER)
    reasons = " ".join(out["diagnosis"]["reasons"])
    assert "CLOSED" in reasons

    # Unknown id: honest namespace answer, never a crash.
    ghost = system.recall_history("ex:ghost-record", scope=SCOPE, owner_id=OWNER)
    assert "never formed here" in " ".join(ghost["diagnosis"]["reasons"])

    # Vectorless + keyword-less: both mechanisms named.
    [kw] = system.remember_many([
        MemoryRecordInput(kind="episode", title="你好", digest="全是中文"),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="d2")
    out2 = system.recall_history(kw, scope=SCOPE, owner_id=OWNER)
    text = " ".join(out2["diagnosis"]["reasons"])
    assert "keyword channel cannot match" in text
    assert "NO stored vector" in text


def test_history_and_diagnosis_answer_from_either_namespace(system) -> None:
    """One id, both halves correct (adversary F2/F3): a probe hit's ROW id
    and the record's GRAPH id give the same history AND the same diagnosis;
    a hidden record's diagnosis actually names the hidden fold."""
    [gid] = system.remember_many([
        MemoryRecordInput(kind="episode", title="Dual named",
                          digest="Reachable under two ids.", keywords=("dual",)),
    ], scope=SCOPE, owner_id=OWNER, idempotency_key="ns1")
    r = system.reconstruct(Stimulus(cue_text="dual"), scopes=SCOPES)
    row_id = next(h.record_id for h in r.handles if h and h.record_id)
    assert row_id != gid

    by_row = system.recall_history(row_id, scope=SCOPE, owner_id=OWNER)
    by_graph = system.recall_history(gid, scope=SCOPE, owner_id=OWNER)
    assert by_row["counts"]["selected"] >= 1
    assert by_graph["counts"]["selected"] == by_row["counts"]["selected"]
    assert "never formed here" not in " ".join(by_row["diagnosis"]["reasons"])
    assert "never formed here" not in " ".join(by_graph["diagnosis"]["reasons"])

    # Hidden fold names itself (F3: assertion-id fold vs graph-id check).
    system.bind(gid, scope=SCOPE, owner_id=OWNER, search_state="hidden")
    hidden_diag = system.recall_history(gid, scope=SCOPE, owner_id=OWNER)
    assert "HIDDEN" in " ".join(hidden_diag["diagnosis"]["reasons"])


def test_concept_expansion_is_opt_in_for_passive_recall() -> None:
    """Same store, two configs: default recall never runs the concept
    channel (byte-stability); opting in surfaces the record the cue never
    named."""
    store, journal = InMemoryTripleStore(), InMemoryJournal()
    base = MemorySystem(store=store, journal=journal)
    records = [
        MemoryRecordInput(kind="episode", title="Voyager signal",
                          digest="The voyager probe crossed the heliopause.",
                          keywords=("voyager",)),
        MemoryRecordInput(kind="lesson", title="Persistence rule",
                          digest="What persists: the voyager record endures unread.",
                          keywords=("persistence",)),
        MemoryRecordInput(kind="episode", title="Weather note",
                          digest="It rained on the datacenter roof.",
                          keywords=("weather",)),
    ]
    base.remember_many(records, scope=SCOPE, owner_id=OWNER, idempotency_key="c1")

    off = base.reconstruct(Stimulus(cue_text="heliopause crossing"), scopes=SCOPES)
    [trace_off] = base.journal.traces(trace_id=off.trace_id)
    assert "concept" not in trace_off.channels

    opted = MemorySystem(store=store, journal=journal,
                         reconstruct_config=ReconstructConfig(
                             concept_expansion=True,
                             concept_tuning=ConceptAnchorTuning(min_sources=2, max_sources=16)))
    on = opted.reconstruct(Stimulus(cue_text="heliopause crossing"), scopes=SCOPES)
    [trace_on] = opted.journal.traces(trace_id=on.trace_id)
    assert "concept" in trace_on.channels
    titles = {h.title for h in on.handles}
    assert "Persistence rule" in titles  # reached via the shared 'voyager' concept


def test_concept_tuning_validates_loudly() -> None:
    with pytest.raises(ValueError, match="min_sources"):
        ConceptAnchorTuning(min_sources=1)
    with pytest.raises(ValueError, match="max_sources"):
        ConceptAnchorTuning(min_sources=4, max_sources=3)
