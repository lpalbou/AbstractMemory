"""Ripple v1 over the memory task queue (backlog 0061; ADR 0001's validation list, v1 slice).

Pinned, on both substrate pairs:
- a deep change spreads one hop, a shallow one does not; two sub-threshold changes on one neighbour together cross;
- the floor stops the tail; a cycle dies (refractory: nothing is reconsidered twice in one ripple);
- the onward impact is min(received, measured) and never amplifies;
- a budget stop records left_out with a warning; protected kinds are never enqueued and appear in left_out;
- every gate decision is stored with its potential; an `unchanged` reconsideration writes no version;
- `ripple.consolidate` is never leased outside a night window and its record links every changed memory;
- surprise is words only (no feeling is written); a ripple is revertible; a dry run writes nothing.

MUTATION LIST (each applied to the source, the named test went red, the source restored byte-exact):
- R1 the floor check removed in _propagate -> test_a_deep_change_spreads_one_hop_a_shallow_one_does_not;
- R2 the refractory check removed -> test_the_floor_stops_the_tail_and_a_cycle_dies;
- R3 the budget check removed -> test_a_budget_stop_records_left_out_and_warns;
- R4 the protected check removed -> test_protected_kinds_are_never_reconsidered;
- R5 the gate-row insert removed -> test_every_gate_decision_is_stored_with_its_potential;
- R6 consolidation's night-only window removed -> test_consolidation_runs_only_at_night_and_links_every_change;
- R7 onward = received (no min) -> test_onward_impact_is_the_smaller_of_received_and_measured;
- R8 potentials not accumulated -> test_two_sub_threshold_changes_together_cross_the_gate.
"""

from __future__ import annotations

import warnings
from typing import Any

import pytest

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    TripleQuery,
)
from abstractmemory.activation_gate import GATE_FLOOR, logistic, loop_gain, measured_change

SCOPE, OWNER = "life", "entity:nerin"
MIND = {"kind": "entity-mind", "id": OWNER}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "step", "run_id": "run-r", "seq": 1}]
T0 = "2026-11-08T03:00:00+00:00"


@pytest.fixture(params=["memory", "sqlite"])
def home(request, tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if request.param == "memory":
            store, journal = InMemoryTripleStore(), InMemoryJournal()
        else:
            path = tmp_path / "memory.sqlite3"
            store, journal = SQLiteTripleStore(path), SQLiteJournal(path)
        system = MemorySystem(store=store, journal=journal, task_queue=True)
    system.kind = request.param
    yield system
    journal.close()
    store.close()


def _form(system, key: str, kind: str = "episode", edges=(), owner: str = OWNER, **kw: Any) -> str:
    kw.setdefault("title", f"record {key}")
    kw.setdefault("digest", f"What I hold about {key}.")
    attrs = dict(kw.pop("attributes", {}) or {})
    attrs.setdefault("digest_method", "authored-v1")
    [gid] = system.remember_many([MemoryRecordInput(kind=kind, edges=tuple(edges), attributes=attrs, **kw)],
                                 scope=SCOPE, owner_id=owner, idempotency_key=key)
    return gid


def _reconsider_targets(system, rid: str):
    return sorted(t["target_id"] for t in system.tasks.tasks(ripple_id=rid, kind=("ripple.reconsider",)))


def _rewrite_and_settle(system, task, change: str):
    system.tasks.claim([task["task_id"]], holder="rt", now=T0)
    system.rewrite_digest(task["target_id"], text=f"Revised after the ripple ({change}): {task['target_id']}",
                          author=MIND, reader=READER, sources=STEP,
                          cause={"cause": "ripple", "ripple_id": task["ripple_id"], "hops": task["hop"]},
                          expected_version=system.record_understanding(task["target_id"])["digest_version"],
                          task_id=task["task_id"])
    return system.settle_reconsideration(task["task_id"], holder="rt", outcome="rewritten", change=change, now=T0)


def _task_for(system, rid: str, target: str):
    [t] = [t for t in system.tasks.tasks(ripple_id=rid, kind=("ripple.reconsider",)) if t["target_id"] == target]
    return t


def test_the_gate_constants_hold_their_invariants() -> None:
    assert loop_gain() < 1.0
    assert logistic(0.5) == pytest.approx(0.5)
    assert measured_change("overturned") == 1.0 and measured_change("unchanged") == 0.0
    # The vectors can halve a reader's claim when the words barely moved; they never raise it.
    assert measured_change("revised", 0.05) == pytest.approx(0.3)
    assert measured_change("revised", 0.9) == pytest.approx(0.6)
    with pytest.raises(ValueError):
        measured_change("shocked")


def test_a_deep_change_spreads_one_hop_a_shallow_one_does_not(home) -> None:
    seed = _form(home, "seed")
    summary = _form(home, "sum", kind="summary", edges=(("summarizes", seed),))
    shallow = home.seed_ripple(seed, change="refined", cause="formation", now=T0)
    assert _reconsider_targets(home, shallow["ripple_id"]) == []
    [d] = shallow["decisions"]
    assert d["decision"] == "below_floor" and d["activation"] < GATE_FLOOR
    deep = home.seed_ripple(seed, change="overturned", cause={"cause": "formation", "note": "deep"}, now=T0)
    assert _reconsider_targets(home, deep["ripple_id"]) == [summary]
    [d] = deep["decisions"]
    assert d["decision"] == "reconsider" and d["potential"] == pytest.approx(0.5) and d["via"] == "edge:summarizes<-"


def test_an_election_rereads_the_seed_first_and_its_neighbours_wait(home) -> None:
    seed = _form(home, "seed")
    summary = _form(home, "sum", kind="summary", edges=(("summarizes", seed),))
    out = home.seed_ripple(seed, change="overturned", surprise="I had this backwards.",
                           cause={"cause": "evidence", "election": "revise #seed", "evidence": ["ex:visit-1"]},
                           now=T0)
    assert _reconsider_targets(home, out["ripple_id"]) == sorted([seed, summary])
    seed_task, sum_task = _task_for(home, out["ripple_id"], seed), _task_for(home, out["ripple_id"], summary)
    assert seed_task["hop"] == 0 and sum_task["depends_on"] == [seed_task["task_id"]]
    sel = home.tasks.select_for_window(10_000, window="turn", now=T0)
    assert {o["task_id"]: o["reason"] for o in sel["left_out"]}[sum_task["task_id"]] == "blocked"
    packet = home.task_packet(seed_task["task_id"])
    assert packet["ripple"]["surprise"] == "I had this backwards." and packet["ripple"]["cause"]["cause"] == "evidence"
    # Words only: no feeling was written.
    assert [f for f, _ in home.journal.replay_records() if f == "valence"] == []
    # Idempotent: the same election is one ripple.
    again = home.seed_ripple(seed, change="overturned", surprise="I had this backwards.",
                             cause={"cause": "evidence", "election": "revise #seed", "evidence": ["ex:visit-1"]})
    assert again["opened"] is False and again["ripple_id"] == out["ripple_id"]


def test_the_floor_stops_the_tail_and_a_cycle_dies(home) -> None:
    a = _form(home, "a")
    b = _form(home, "b", kind="summary", edges=(("summarizes", a),))
    c = _form(home, "c", kind="summary", edges=(("summarizes", b), ("refines", a)))     # a cycle a - b - c - a
    d = _form(home, "d", kind="summary", edges=(("summarizes", c),))
    e = _form(home, "e", kind="summary", edges=(("summarizes", d),))
    rid = home.seed_ripple(a, change="overturned", cause="formation", now=T0)["ripple_id"]
    assert _reconsider_targets(home, rid) == sorted([b, c])                               # both touch a: hop 1
    via_b = {x["candidate_id"]: x["decision"] for x in
             _rewrite_and_settle(home, _task_for(home, rid, b), "overturned")["decisions"]}
    assert via_b == {a: "refractory", c: "refractory"}                                    # once per ripple
    via_c = {x["candidate_id"]: x for x in
             _rewrite_and_settle(home, _task_for(home, rid, c), "overturned")["decisions"]}
    assert via_c[d]["decision"] == "reconsider" and via_c[d]["hop"] == 2
    assert via_c[d]["potential"] == pytest.approx(0.25)
    assert via_c[a]["decision"] == via_c[b]["decision"] == "refractory"
    tail = {x["candidate_id"]: x for x in
            _rewrite_and_settle(home, _task_for(home, rid, d), "overturned")["decisions"]}
    assert tail[e]["decision"] == "below_floor" and tail[e]["hop"] == 3
    assert tail[e]["potential"] == pytest.approx(0.125)                                   # the floor stops the tail
    assert tail[c]["decision"] == "refractory"
    assert _reconsider_targets(home, rid) == sorted([b, c, d])
    assert home.ripple(rid)["status"] == "consolidating"                                  # three changed


def test_onward_impact_is_the_smaller_of_received_and_measured(home) -> None:
    a = _form(home, "a")
    b = _form(home, "b", kind="summary", edges=(("summarizes", a),))
    _form(home, "c", kind="summary", edges=(("summarizes", b),))
    rid = home.seed_ripple(a, change="overturned", cause="formation", now=T0)["ripple_id"]
    refined = _rewrite_and_settle(home, _task_for(home, rid, b), "refined")
    assert refined["onward"] == pytest.approx(0.25)                    # measured 0.25 < received 0.5
    rid2 = home.seed_ripple(a, change="revised", cause={"cause": "formation", "n": 2}, now=T0)["ripple_id"]
    overturned = _rewrite_and_settle(home, _task_for(home, rid2, b), "overturned")
    assert overturned["onward"] == pytest.approx(0.3)                  # received 0.6 * 1 * 0.5 < measured 1.0


def test_two_sub_threshold_changes_together_cross_the_gate(home) -> None:
    s = _form(home, "s")
    b1 = _form(home, "b1", kind="summary", edges=(("summarizes", s),))
    b2 = _form(home, "b2", kind="summary", edges=(("summarizes", s),))
    c = _form(home, "c", kind="summary", edges=(("summarizes", b1), ("summarizes", b2)))
    rid = home.seed_ripple(s, change="overturned", cause="formation", now=T0)["ripple_id"]
    first = {x["candidate_id"]: x for x in _rewrite_and_settle(home, _task_for(home, rid, b1), "refined")["decisions"]}
    assert first[c]["decision"] == "below_floor" and first[c]["potential"] == pytest.approx(0.125)
    second = {x["candidate_id"]: x for x in _rewrite_and_settle(home, _task_for(home, rid, b2), "refined")["decisions"]}
    assert second[c]["decision"] == "reconsider" and second[c]["potential"] == pytest.approx(0.25)


def test_a_budget_stop_records_left_out_and_warns(home) -> None:
    hub = _form(home, "hub")
    spokes = [_form(home, f"s{i}", kind="summary", edges=(("summarizes", hub),)) for i in range(5)]
    with pytest.warns(RuntimeWarning, match="WARNING:TRUNCATION"):
        out = home.seed_ripple(hub, change="overturned", cause="formation", budget=2, now=T0)
    assert len(_reconsider_targets(home, out["ripple_id"])) == 2
    budget = [x for x in out["left_out"] if x["reason"] == "budget"]
    assert len(budget) == 3 and {x["record_id"] for x in budget} | set(_reconsider_targets(home, out["ripple_id"])) \
        == set(spokes)
    assert all(x["potential"] == pytest.approx(0.5) for x in budget)


def test_protected_kinds_are_never_reconsidered(home) -> None:
    seed = _form(home, "seed")
    interest = _form(home, "interest", kind="interest", edges=(("derived_from", seed),))
    lesson = _form(home, "lesson", kind="lesson", edges=(("derived_from", seed),))
    out = home.seed_ripple(seed, change="overturned", cause="formation", now=T0)
    assert _reconsider_targets(home, out["ripple_id"]) == [lesson]
    [left] = out["left_out"]
    assert left["record_id"] == interest and left["reason"] == "protected: the entity's own act"


def test_every_gate_decision_is_stored_with_its_potential(home) -> None:
    seed = _form(home, "seed")
    near = _form(home, "near", kind="summary", edges=(("summarizes", seed),))
    far = _form(home, "far", edges=(("mentions", seed),))
    out = home.seed_ripple(seed, change="revised", cause="formation", now=T0)
    gates = {g["candidate_id"]: g for g in home.ripple(out["ripple_id"])["gates"]}
    assert set(gates) == {near, far}
    assert gates[near]["potential"] == pytest.approx(0.3) and gates[near]["decision"] == "reconsider"
    assert gates[far]["potential"] == pytest.approx(0.075) and gates[far]["decision"] == "below_floor"
    assert gates[near]["activation"] == pytest.approx(logistic(0.3))


def test_an_unchanged_reconsideration_writes_no_version(home) -> None:
    seed = _form(home, "seed")
    summary = _form(home, "sum", kind="summary", edges=(("summarizes", seed),))
    rid = home.seed_ripple(seed, change="overturned", cause="formation", now=T0)["ripple_id"]
    task = _task_for(home, rid, summary)
    home.tasks.claim([task["task_id"]], holder="rt", now=T0)
    out = home.settle_reconsideration(task["task_id"], holder="rt", outcome="unchanged", now=T0)
    assert out["outcome"] == "unchanged" and out["status"] == "settled"
    assert home.versions(summary) == [] and home.tasks.task(task["task_id"])["status"] == "done"
    assert home.ripple(rid)["gates"][-1]["decision"] == "settled"


def test_consolidation_runs_only_at_night_and_links_every_change(home) -> None:
    seed = _form(home, "seed")
    b1 = _form(home, "b1", kind="summary", edges=(("summarizes", seed),))
    b2 = _form(home, "b2", kind="summary", edges=(("summarizes", seed),))
    rid = home.seed_ripple(seed, change="overturned", cause="formation", now=T0)["ripple_id"]
    for target in (b1, b2):
        _rewrite_and_settle(home, _task_for(home, rid, target), "revised")
    [cons] = home.tasks.tasks(ripple_id=rid, kind=("ripple.consolidate",))
    assert cons["windows"] == ["night"]
    for window in ("turn", "visit", "nap", "cycle", "idle"):
        sel = home.tasks.select_for_window(10_000, window=window, now=T0)
        assert cons["task_id"] not in {t["task_id"] for t in sel["tasks"]}
    assert home.tasks.claim([cons["task_id"]], holder="rt", window="nap", now=T0)["refused"][0]["reason"] == "window"
    night = home.tasks.select_for_window(10_000, window="night", now=T0)
    assert cons["task_id"] in {t["task_id"] for t in night["tasks"]}
    packet = home.task_packet(cons["task_id"])
    assert {c["record_id"] for c in packet["ripple"]["changed"]} == {b1, b2}
    assert all(c["before"] and c["now"] for c in packet["ripple"]["changed"])
    home.tasks.claim(night, holder="rt", now=T0)
    formed = home.form_consolidation(cons["task_id"], holder="rt", title="What the seed changes",
                                     text="I now read both sessions differently.", author=MIND, reader=READER,
                                     sources=STEP)
    record = home.record_understanding(formed["record_id"])
    edges = {(e.predicate, e.object) for e in home.store.query(TripleQuery(subject=formed["record_id"], limit=0))
             if (e.attributes or {}).get("record_edge")}
    assert edges == {("summarizes", b1), ("summarizes", b2), ("derived_from", seed)}
    assert record["kind"] == "summary" and record["authored_by"] == MIND
    assert home.tasks.tasks(target_id=formed["record_id"]) == []                 # never batch-rewritten
    assert home.rewrite_digest(formed["record_id"], text="x", author=MIND, reader=READER, sources=STEP,
                               cause="ripple", expected_version=0)["reason"] == "consolidation_record"
    assert home.ripple(rid)["status"] == "consolidated"
    # The ripple is revertible: each changed memory gets back the reading it held before.
    before = {c["record_id"]: c["before"] for c in packet["ripple"]["changed"]}
    for res in home.revert_ripple(rid, reason="operator check"):
        assert res["applied"] is True
    assert {r: home.record_understanding(r)["digest"] for r in (b1, b2)} == before


def test_a_dry_run_writes_nothing_and_says_the_bound(home) -> None:
    seed = _form(home, "seed")
    summary = _form(home, "sum", kind="summary", edges=(("summarizes", seed),))
    out = home.seed_ripple(seed, change="overturned", cause="formation", dry_run=True, now=T0)
    assert out["dry_run"] is True and [d["candidate_id"] for d in out["decisions"]] == [summary]
    assert home.ripples() == [] and home.tasks.tasks(kind=("ripple.reconsider",)) == []


def test_another_owners_memory_is_never_reconsidered(home) -> None:
    seed = _form(home, "seed")
    _form(home, "theirs", kind="summary", edges=(("summarizes", seed),), owner="entity:castor")
    out = home.seed_ripple(seed, change="overturned", cause="formation", now=T0)
    assert out["decisions"] == [] and _reconsider_targets(home, out["ripple_id"]) == []


def test_refresh_closes_a_ripple_whose_last_task_was_skipped(home) -> None:
    seed = _form(home, "seed")
    summary = _form(home, "sum", kind="summary", edges=(("summarizes", seed),))
    rid = home.seed_ripple(seed, change="overturned", cause="formation", now=T0)["ripple_id"]
    task = _task_for(home, rid, summary)
    home.tasks.claim([task["task_id"]], holder="rt", now=T0)
    home.tasks.release(task["task_id"], holder="rt", outcome="skip", reason="over_context", now=T0)
    assert home.ripple(rid)["status"] == "open"
    assert home.refresh_ripples(now=T0) == [{"ripple_id": rid, "status": "settled"}]
    assert home.ripples(status=("settled",))[0]["ripple_id"] == rid


class _TwinEmbedder:
    """Test fake: one shared unit vector for texts about the harbor, orthogonal ones for anything else."""

    model = "fake-twin-4"

    def embed_texts(self, texts):
        out = []
        for t in texts:
            if "harbor" in str(t):
                out.append([1.0, 0.0, 0.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0, 0.0] if "garden" in str(t) else [0.0, 0.0, 0.0, 1.0])
        return out


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_similarity_reaches_an_unlinked_memory(kind, tmp_path) -> None:
    emb = _TwinEmbedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if kind == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        else:
            store, journal = SQLiteTripleStore(tmp_path / "m.sqlite3", embedder=emb), SQLiteJournal(tmp_path / "m.sqlite3")
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=True)
        seed = _form(system, "seed", digest="The harbor wall survey.")
        twin = _form(system, "twin", digest="Three cracks in the harbor wall.")
        other = _form(system, "other", digest="Planting the garden.")
    out = system.seed_ripple(seed, change="overturned", cause="formation", now=T0)
    by = {d["candidate_id"]: d for d in out["decisions"]}
    assert by[twin]["via"] == "similarity" and by[twin]["decision"] == "reconsider"
    assert other not in by                                   # another idea carries no reliance
    journal.close()
    store.close()
