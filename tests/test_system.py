"""End-to-end tests for the MemorySystem facade (seam v1, backlog 0024/0027).

Runs on the shared `stack`/`system` fixtures from conftest.py: both layer-1
stacks — (InMemoryTripleStore + InMemoryJournal) and (SQLiteTripleStore +
SQLiteJournal sharing one file, the 0017 sidecar deployment) — so the facade
proves identical seam behavior on the volatile reference pair and the durable
pair (0011 parity principle).

Timestamps and assertion ids are explicit throughout: ordering assertions
must never depend on wall-clock races.
"""

from __future__ import annotations

import json
import warnings
from typing import Any, Dict, List

import pytest

# Package-root imports on purpose: the runtime consumes this surface, so the
# suite exercises the __init__ re-exports rather than the module paths.
from abstractmemory import (
    MemorySystem,
    RecallBudget,
    Stimulus,
    TripleAssertion,
    TripleQuery,
)

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _ts(i: int) -> str:
    return f"2026-07-05T10:{i:02d}:00.000000+00:00"


def _assertion(aid: str, s: str, p: str, o: str, ts: int, **attrs: Any) -> TripleAssertion:
    return TripleAssertion(
        subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
        observed_at=_ts(ts), attributes=dict(attrs), assertion_id=aid,
    )


def _seed_report_world(system: MemorySystem) -> None:
    """Two equal-relevance report records (activation tie-break substrate)
    plus a subject-sharing record and an unrelated one."""
    system.add([
        _assertion("m-old", "alice", "wrote", "report", 1),
        _assertion("m-new", "alice", "filed", "report copy", 2),
        _assertion("m-tea", "alice", "likes", "tea", 3),
        _assertion("m-bob", "bob", "reads", "books", 4),
    ])


def _ids(result) -> List[str]:
    return [h.record_id for h in result.handles]


# ---------------------------------------------------------------------------
# End-to-end: reconstruct -> commit_selection -> strengthened reconstruct
# ---------------------------------------------------------------------------


def test_end_to_end_commit_strengthens_ranking(system, stack) -> None:
    _, journal = stack
    _seed_report_world(system)

    r1 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    assert {"m-old", "m-new", "m-tea", "m-bob"} <= set(_ids(r1))
    for h in r1.handles:
        assert h.record_id and h.cues  # cues never empty for selected handles
    # Equal keyword relevance (2/2 each): recency tie-break puts m-new first.
    assert _ids(r1).index("m-new") < _ids(r1).index("m-old")
    assert r1.selector_route == "heuristic"
    assert r1.as_of_seq == 0  # nothing journaled before the first read

    snap = system.commit_selection(r1.trace_id, ["m-old", "m-tea"], prompt_token_estimate=99)

    # Snapshot: journal-assigned seq, reference display (never payload copies).
    assert snap.seq > 0 and snap.snapshot_id
    assert snap.trace_id == r1.trace_id
    assert snap.used_record_ids == ("m-old", "m-tea")
    assert snap.prompt_token_estimate == 99
    # Union model: the snapshot records every used id's admission label.
    assert snap.provenance == {
        "used_count": 2,
        "admissions": {"m-old": "stimulus", "m-tea": "stimulus"},
    }
    by_rid = {d["record_id"]: d for d in snap.display}
    assert by_rid["m-old"]["title"] == "alice wrote report"
    assert by_rid["m-old"]["digest"] == "alice wrote report"
    assert by_rid["m-old"]["token_estimate"] == len("alice wrote report") // 4 + 1
    assert journal.snapshots(trace_id=r1.trace_id)[0].snapshot_id == snap.snapshot_id

    # The trail: one selected per used record + the term-sharing pair
    # (m-old and m-tea share subject "alice"); m-bob was not used -> nothing.
    selected = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected"], limit=0)
    assert sorted(e.record_id for e in selected) == ["m-old", "m-tea"]
    assert all(e.trace_id == r1.trace_id and e.actor == "runtime" for e in selected)
    pairs = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["co_selected"], limit=0)
    assert [e.pair_ids for e in pairs] == [("m-old", "m-tea")]  # canonical sorted pair
    assert pairs[0].provenance == {"context_ref": snap.snapshot_id}

    # Strengthened re-read: the committed record now outranks the equally
    # relevant uncommitted one (activation reorders; relevance admitted both).
    r2 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    assert _ids(r2).index("m-old") < _ids(r2).index("m-new")
    h_old = {h.record_id: h for h in r2.handles}["m-old"]
    assert h_old.activation["base_level"] > 0.0
    assert h_old.activation["total"] == pytest.approx(
        h_old.activation["base_level"] + h_old.activation["spread"]
    )
    assert any(c.startswith("selected +") for c in h_old.cues)  # contribution cue surfaced


def test_commit_selection_co_use_pairs_the_depositing_slice(system, stack) -> None:
    """CO-USE RULE (maintainer-initiated 2026-07-07): ALL unordered pairs
    in the depositing slice wire together — records that serve one moment
    together leave a trail even without shared terms or formation edges
    (the old term-only expectation was the raw-triple-era mechanism; p-3
    sharing nothing no longer means wiring nothing)."""
    _, journal = stack
    system.add([
        _assertion("p-1", "alice", "knows", "bob", 1),
        _assertion("p-2", "bob", "reads", "books", 2),    # subject == p-1 object
        _assertion("p-3", "carol", "likes", "tea", 3),    # shares nothing — still co-used
    ])
    r = system.reconstruct(Stimulus(cue_text="alice bob carol"), scopes=SCOPES)
    system.commit_selection(r.trace_id, ["p-1", "p-2", "p-3"])

    pairs = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["co_selected"], limit=0)
    assert sorted(e.pair_ids for e in pairs) == [
        ("p-1", "p-2"), ("p-1", "p-3"), ("p-2", "p-3")]  # C(3,2), deduped


def test_commit_selection_groups_events_per_scope_and_owner(system, stack) -> None:
    """Mixed-scope commits: selected events land in each record's own
    (scope, owner) stream; a cross-group pair lands in the group of the
    pair member that appears FIRST in used_record_ids (documented choice)."""
    _, journal = stack
    system.add([
        _assertion("g-sess", "alice", "wrote", "report", 1),
        TripleAssertion(
            subject="alice", predicate="drafted", object="summary", scope="run",
            owner_id="r1", observed_at=_ts(2), assertion_id="g-run",
        ),
    ])
    r = system.reconstruct(Stimulus(cue_text="alice"), scopes=[(SCOPE, OWNER), ("run", "r1")])
    system.commit_selection(r.trace_id, ["g-sess", "g-run"])

    sess_selected = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["selected"], limit=0)
    run_selected = journal.events(scope="run", owner_id="r1", kinds=["selected"], limit=0)
    assert [e.record_id for e in sess_selected] == ["g-sess"]
    assert [e.record_id for e in run_selected] == ["g-run"]

    # Shared subject "alice" -> one pair, hosted by g-sess's stream (first used).
    sess_pairs = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["co_selected"], limit=0)
    run_pairs = journal.events(scope="run", owner_id="r1", kinds=["co_selected"], limit=0)
    assert [e.pair_ids for e in sess_pairs] == [("g-run", "g-sess")]
    assert run_pairs == []


def test_commit_selection_rejects_empty_and_unknown_ids(system) -> None:
    _seed_report_world(system)
    r = system.reconstruct(Stimulus(cue_text="alice"), scopes=SCOPES)
    with pytest.raises(ValueError, match="at least one used_record_id"):
        system.commit_selection(r.trace_id, [])
    with pytest.raises(ValueError, match="ghost"):
        system.commit_selection(r.trace_id, ["m-old", "ghost"])
    with pytest.raises(ValueError, match="trace_id"):
        system.commit_selection("", ["m-old"])


# ---------------------------------------------------------------------------
# working_set view
# ---------------------------------------------------------------------------


def test_working_set_view_returns_edges_and_decomposition(system) -> None:
    # S (channel-matched) -- N (1 hop, shared "bob") -- M (2 hops, shared
    # "acme"); max_candidates=2 keeps N/M out of recents so only spreading
    # can bring them in.
    system.add([
        _assertion("w-m", "acme", "located_in", "paris", 1),
        _assertion("w-n", "bob", "works_at", "acme", 2),
        _assertion("w-f", "carol", "likes", "tea", 3),
        _assertion("w-s", "alice", "knows", "bob", 4),
    ])
    budget = RecallBudget(max_candidates=2)
    r = system.reconstruct(Stimulus(cue_text="alice"), scopes=SCOPES, budget=budget, view="working_set")

    assert r.view == "working_set"
    edge_pairs = [(e["source_id"], e["target_id"]) for e in r.edges]
    assert ("w-s", "w-n") in edge_pairs and ("w-n", "w-m") in edge_pairs
    for e in r.edges:
        if e.get("source") == "stm_trail":
            assert set(e) == {"source", "pair", "trail_activation"}
            continue
        assert set(e) == {"source_id", "predicate", "target_id", "strength_label", "trail_activation", "source"}
    by_id = {h.record_id: h for h in r.handles}
    assert by_id["w-n"].activation["spread"] > 0.0
    for h in r.handles:
        assert h.activation["total"] == pytest.approx(
            h.activation["base_level"] + h.activation["spread"]
        )

    # Shelf view of the same world: no edges, no spread-only members.
    r_shelf = system.reconstruct(Stimulus(cue_text="alice"), scopes=SCOPES, budget=budget, view="shelf")
    assert r_shelf.edges == ()
    assert "w-n" not in _ids(r_shelf) and "w-m" not in _ids(r_shelf)


# ---------------------------------------------------------------------------
# as_of replay
# ---------------------------------------------------------------------------


def test_as_of_replay_reproduces_activation_ordering(system) -> None:
    _seed_report_world(system)
    stim = Stimulus(cue_text="alice report")

    r0 = system.reconstruct(stim, scopes=SCOPES)
    system.commit_selection(r0.trace_id, ["m-old", "m-tea"])

    r_a = system.reconstruct(stim, scopes=SCOPES)
    captured = r_a.as_of_seq
    order_a = _ids(r_a)
    activation_a = {h.record_id: dict(h.activation) for h in r_a.handles}
    assert order_a.index("m-old") < order_a.index("m-new")

    # Shift the attention state AFTER the anchor: m-new gets committed twice.
    for _ in range(2):
        r_x = system.reconstruct(stim, scopes=SCOPES)
        system.commit_selection(r_x.trace_id, ["m-new"])

    # Latest-state read now ranks m-new first (proves the state truly moved).
    r_latest = system.reconstruct(stim, scopes=SCOPES)
    assert _ids(r_latest).index("m-new") < _ids(r_latest).index("m-old")

    # Anchored replay: identical order AND identical activation decomposition.
    r_b = system.reconstruct(Stimulus(cue_text="alice report", as_of=captured), scopes=SCOPES)
    assert r_b.as_of_seq == captured
    assert _ids(r_b) == order_a
    assert {h.record_id: dict(h.activation) for h in r_b.handles} == activation_a
    # Everything except the fresh trace_id is bit-identical.
    dict_a, dict_b = r_a.to_dict(), r_b.to_dict()
    dict_a.pop("trace_id"), dict_b.pop("trace_id")
    assert dict_a == dict_b


def test_as_of_outside_journal_axis_is_a_loud_error(system) -> None:
    """Contract 4 (a2a 0001/004): replay drift is a loud error, never silent.
    An anchor this journal never issued cannot quietly mean "latest"."""
    _seed_report_world(system)
    with pytest.raises(ValueError, match="as_of"):
        system.reconstruct(Stimulus(cue_text="alice", as_of=10_000), scopes=SCOPES)
    with pytest.raises(ValueError, match="as_of"):
        system.reconstruct(Stimulus(cue_text="alice", as_of=-1), scopes=SCOPES)


# ---------------------------------------------------------------------------
# audit inertness + journal=False purity
# ---------------------------------------------------------------------------


def test_repeated_journaled_reads_never_change_scores(system, stack) -> None:
    """0018 end-to-end: reading is not using. Ten journaled reconstructions
    append traces + 'listed' events, yet no activation score moves."""
    _, journal = stack
    _seed_report_world(system)
    r0 = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    system.commit_selection(r0.trace_id, ["m-old"])

    before_scores = system.activation(scope=SCOPE, owner_id=OWNER)
    before_order = _ids(system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES))
    seq_before = journal.current_seq()

    for _ in range(10):
        system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES, journal=True)

    assert journal.current_seq() > seq_before  # reads WERE journaled...
    listed = journal.events(scope=SCOPE, owner_id=OWNER, kinds=["listed"], limit=0)
    assert len(listed) >= 10 and all(e.actor == "system" for e in listed)
    # ...and yet: scores and ordering are untouched (audit kinds are inert).
    assert system.activation(scope=SCOPE, owner_id=OWNER) == before_scores
    assert _ids(system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)) == before_order


def test_journal_false_writes_nothing_at_all(system, stack) -> None:
    _, journal = stack
    _seed_report_world(system)
    seq_before = journal.current_seq()
    events_before = len(journal.events(scope=SCOPE, owner_id=OWNER, limit=0))

    result = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES, journal=False)

    assert result.handles  # a real read happened...
    # ...with zero journal effect: no seq movement, no records of any family.
    assert journal.current_seq() == seq_before
    assert len(journal.events(scope=SCOPE, owner_id=OWNER, limit=0)) == events_before
    assert journal.traces(limit=0) == []
    assert journal.snapshots(limit=0) == []


# ---------------------------------------------------------------------------
# closures
# ---------------------------------------------------------------------------


def test_closed_assertions_leave_ranked_retrieval_but_not_id_lookup(system, stack) -> None:
    store, _ = stack
    _seed_report_world(system)
    assert "m-old" in _ids(system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES))

    closure_ids = system.close_assertions(["m-old"], kind="retract", reason="user corrected the fact")
    assert len(closure_ids) == 1 and all(closure_ids)

    # Ranked retrieval honors the closure fold...
    after = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES)
    assert "m-old" not in _ids(after)
    assert all(d["record_id"] != "m-old" for d in after.dropped)
    # ...while direct id-lookup bypasses it BY DESIGN (audit completeness).
    rows = store.query(TripleQuery(assertion_ids=("m-old",)))
    assert [a.assertion_id for a in rows] == ["m-old"]

    # A replay anchored BEFORE the closure still sees the record (closure
    # fold is ≤ as_of like every other journal-derived signal).
    replayed = system.reconstruct(Stimulus(cue_text="alice report", as_of=0), scopes=SCOPES)
    assert "m-old" in _ids(replayed)


def test_close_assertions_validation(system) -> None:
    # Ids resolve against the store now (audit fix 2), so validation cases
    # must reference real records — and unknown ids are their own loud error.
    _seed_report_world(system)
    with pytest.raises(ValueError, match="at least one assertion_id"):
        system.close_assertions([], kind="retract", reason="nothing")
    with pytest.raises(ValueError, match="replacement_ids"):
        system.close_assertions(["m-old"], kind="supersede", reason="refined")
    with pytest.raises(ValueError, match="retract"):
        system.close_assertions(["m-old"], kind="delete", reason="wrong kind")
    with pytest.raises(ValueError, match="ghost"):
        system.close_assertions(["ghost"], kind="retract", reason="unknown id")


# ---------------------------------------------------------------------------
# binding visibility enforcement (0017): see tests/test_binding_visibility.py
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# broad-scope guard
# ---------------------------------------------------------------------------


def test_broad_scope_requires_escalation_reason(system, stack) -> None:
    _, journal = stack
    _seed_report_world(system)

    with pytest.raises(ValueError, match="escalation_reason"):
        system.reconstruct(Stimulus(cue_text="alice"), scopes=[("global", "global_memory")])
    # Mixed ladders trigger too, and case variants cannot sneak past.
    with pytest.raises(ValueError, match="escalation_reason"):
        system.reconstruct(Stimulus(cue_text="alice"), scopes=[(SCOPE, OWNER), ("Global", "g")])
    with pytest.raises(ValueError, match="escalation_reason"):
        system.reconstruct(
            Stimulus(cue_text="alice"), scopes=[("global", "g")], escalation_reason="   "
        )

    ok = system.reconstruct(
        Stimulus(cue_text="alice"),
        scopes=[(SCOPE, OWNER), ("global", "global_memory")],
        escalation_reason="session scope lacked the answer",
    )
    assert ok.handles  # session-scope records still found
    # The reason lands on the journaled trace (audited escalation).
    assert journal.traces(limit=1)[0].escalation_reason == "session scope lacked the answer"


def test_broad_scope_set_is_configurable(stack) -> None:
    store, journal = stack
    system = MemorySystem(store=store, journal=journal, broad_scopes={"session"})
    with pytest.raises(ValueError, match="escalation_reason"):
        system.reconstruct(Stimulus(cue_text="x"), scopes=SCOPES)
    system.reconstruct(Stimulus(cue_text="x"), scopes=SCOPES, escalation_reason="audit test")


def test_reconstruct_input_validation(system) -> None:
    with pytest.raises(ValueError, match="view"):
        system.reconstruct(Stimulus(cue_text="x"), scopes=SCOPES, view="prompt")
    with pytest.raises(ValueError, match="scope"):
        system.reconstruct(Stimulus(cue_text="x"), scopes=[])


# ---------------------------------------------------------------------------
# seam JSON safety
# ---------------------------------------------------------------------------


def test_seam_payloads_survive_json_round_trip(system) -> None:
    _seed_report_world(system)
    result = system.reconstruct(Stimulus(cue_text="alice report"), scopes=SCOPES, view="working_set")
    snap = system.commit_selection(result.trace_id, ["m-old", "m-tea"])

    for payload in (result.to_dict(), snap.to_dict()):
        assert json.loads(json.dumps(payload)) == payload
    assert result.to_dict()["as_of_seq"] == result.as_of_seq
    assert snap.to_dict()["used_record_ids"] == ["m-old", "m-tea"]


# ---------------------------------------------------------------------------
# selector / reflector v1 degradation
# ---------------------------------------------------------------------------


def test_selector_emits_single_fallback_and_stays_heuristic(stack) -> None:
    store, journal = stack
    store.add([_assertion("s-1", "alice", "wrote", "report", 1)])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        system = MemorySystem(store=store, journal=journal, selector=object())
    matching = [w for w in caught if "selector refinement not implemented in v1" in str(w.message)]
    assert len(matching) == 1
    assert all("#FALLBACK" in str(w.message) for w in matching)

    result = system.reconstruct(Stimulus(cue_text="alice"), scopes=SCOPES)
    assert result.selector_route == "heuristic"  # heuristic result, not an error
    assert result.handles


def test_reflector_emits_fallback_warning(stack) -> None:
    store, journal = stack
    with pytest.warns(RuntimeWarning, match="#FALLBACK: reflector"):
        MemorySystem(store=store, journal=journal, reflector=object())


# ---------------------------------------------------------------------------
# deliberate acts, activation inspection, bindings, passthroughs
# ---------------------------------------------------------------------------


def test_deliberate_act_wrappers_and_activation_inspection(system) -> None:
    _seed_report_world(system)

    eid = system.reinforce("m-old", reason="keep this fact", scope=SCOPE, owner_id=OWNER)
    assert isinstance(eid, str) and eid
    act = system.activation(["m-old"], scope=SCOPE, owner_id=OWNER)
    assert act["m-old"] == {"base_level": 8.0, "total": 8.0}  # pinned weight, rank 0
    # Audit fix 2 (works-or-loud): unknown ids raise instead of returning a
    # silent zero — the old "explicit zeros" reading hid mis-namespaced ids.
    with pytest.raises(ValueError, match="ghost"):
        system.activation(["m-old", "ghost"], scope=SCOPE, owner_id=OWNER)

    at_pin = system.current_seq()
    system.attenuate("m-old", reason="mute for now", weight=25, scope=SCOPE, owner_id=OWNER)
    act2 = system.activation(["m-old"], scope=SCOPE, owner_id=OWNER)
    # Per-step clamp (audit f1, fork parity): the silence is the NEWEST event
    # so it floors at 0 with nothing accumulated above it; the older pin then
    # contributes from rank 1. Demotion now acts on accumulated-newer use.
    assert act2["m-old"]["base_level"] == pytest.approx(8.0 * 20 / 21)
    # at_seq anchoring: the pre-attenuation state is still inspectable.
    act_before = system.activation(["m-old"], scope=SCOPE, owner_id=OWNER, at_seq=at_pin)
    assert act_before["m-old"]["base_level"] == 8.0

    rid = system.refocus(reason="topic shift", scope=SCOPE, owner_id=OWNER)
    assert isinstance(rid, str) and rid

    # Unfiltered inspection lists only records with journaled attention.
    full = system.activation(scope=SCOPE, owner_id=OWNER)
    assert set(full) == {"m-old"}

    with pytest.raises(ValueError, match="reason"):
        system.reinforce("m-old", reason="", scope=SCOPE, owner_id=OWNER)


def test_bind_and_seq_passthroughs(system, stack) -> None:
    _, journal = stack
    _seed_report_world(system)

    binding = system.bind(
        "m-old", scope=SCOPE, owner_id=OWNER, search_state="hidden", reason="quarantine",
    )
    assert binding.seq > 0 and binding.binding_id
    folded = journal.bindings(record_id="m-old", fold=True)
    assert len(folded) == 1 and folded[0].search_state == "hidden"
    with pytest.raises(ValueError, match="hidden"):
        system.bind("m-old", scope=SCOPE, owner_id=OWNER, search_state="hidden", prompt_state="active")

    assert system.current_seq() == journal.current_seq()
    assert system.seq_at("2000-01-01T00:00:00+00:00") == 0


def test_layer1_passthroughs_and_close_leaves_store_open(stack) -> None:
    store, journal = stack
    system = MemorySystem(store=store, journal=journal)
    ids = system.add([_assertion("l-1", "alice", "wrote", "report", 1)])
    assert ids == ["l-1"]
    assert [a.assertion_id for a in system.query(TripleQuery(subject="alice"))] == ["l-1"]

    system.close()
    # Store lifecycle is caller-owned: layer 1 keeps working after close().
    assert len(store.query(TripleQuery(subject="alice"))) == 1


def test_package_has_no_runtime_or_core_imports() -> None:
    """0024 hard boundary, package-wide: NO module in abstractmemory imports
    abstractcore or abstractruntime (LLM-adjacent steps arrive only as
    injected protocols; the gateway embedder speaks HTTP). Checked on the
    AST of every module file (docstrings may legitimately mention the
    package names when documenting this very boundary)."""
    import ast
    from pathlib import Path

    import abstractmemory

    package_root = Path(abstractmemory.__file__).resolve().parent
    module_files = sorted(p for p in package_root.rglob("*.py") if "__pycache__" not in p.parts)
    assert len(module_files) >= 17, f"package scan looks wrong: {module_files}"

    offenders: Dict[str, List[str]] = {}
    for path in module_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        forbidden = [m for m in imported if m.startswith(("abstractcore", "abstractruntime"))]
        if forbidden:
            offenders[str(path.relative_to(package_root))] = forbidden
    assert offenders == {}


def test_package_root_exports_complete_and_sorted() -> None:
    """__init__ exports the seam surface (a2a 0001/006 hand-off): every name
    in __all__ resolves, __all__ is sorted, and the layer-2 surface the
    runtime consumes is present."""
    import abstractmemory

    assert abstractmemory.__all__ == sorted(abstractmemory.__all__)
    missing = [n for n in abstractmemory.__all__ if not hasattr(abstractmemory, n)]
    assert missing == []
    required = {
        # seam dataclasses + facade
        "MemorySystem", "Stimulus", "RecallBudget", "MemoryHandle",
        "ReconstructionResult", "ActiveMemorySnapshot",
        # journal substrate
        "MemoryEvent", "ScopeBinding", "ClosureRecord", "ReconstructionTrace",
        "MemoryJournal", "fold_bindings", "InMemoryJournal", "SQLiteJournal",
        # tuning + shared rendering
        "AttentionConfig", "SpreadParams", "canonical_text", "CANONICAL_TEXT_VERSION",
    }
    assert required <= set(abstractmemory.__all__)
