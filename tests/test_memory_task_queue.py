"""The persistent queue of memory tasks (backlog 0060; operator rulings 2026-11-07 rule 1 and 2026-11-08 decision 3).

Pinned here, on both substrate pairs where the behaviour is shared:
- formation in an opted-in home enqueues exactly one `digest.rewrite` per labelled-mechanical record; a replay
  enqueues nothing; a home without the opt-in, authored words, protected kinds and review offers enqueue nothing;
- ACTIVATION-DRIVEN selection: highest gated activation first, the gate floor and the host's sensitivity decide,
  the wall-time budget and the hard cap bound it, never a fixed count; every live task is either selected or left
  out with a named reason; selection is a pure read;
- leases expire back to pending, max_attempts make a task fail, a defer spends no attempt, a summary waits for its
  episodes, a rewrite acks its task inside its own transaction and supersedes stale tasks;
- `understanding_debt` matches a hand count; `enqueue_debt` is dry-run by default and ranks by lived use;
- `maintenance_due` counts pending night-only and ripple work as due; opening a home whose queue exists is a read.

MUTATION LIST (each applied to the source, the named test went red, the source restored byte-exact):
- Q1 dependencies ignored in select_for_window -> test_a_summary_waits_for_its_episodes;
- Q2 a leased task never expires in claim -> test_an_expired_lease_returns_the_task;
- Q3 a defer spends its attempt -> test_defer_spends_no_attempt_and_retries_fail_at_max;
- Q4 candidates ordered by age only -> test_highest_activation_first_and_sensitivity_moves_the_gate;
- Q5 the gate floor check removed -> test_highest_activation_first_and_sensitivity_moves_the_gate;
- Q6 the budget check removed -> test_budget_and_hard_cap_bound_the_window_never_a_count;
- Q7 on_rewrite supersedes nothing -> test_a_rewrite_supersedes_stale_tasks;
- Q8 the consent-set check removed in enqueue_formed -> test_formation_enqueues_one_task_per_mechanical_record;
- Q9 the rewrite's queue hook removed -> test_a_rewrite_acks_its_task_in_the_same_transaction;
- Q10 maintenance_due's task clause removed -> test_maintenance_due_counts_night_and_ripple_work;
- Q11 review offers not excluded (_protected) -> test_understanding_debt_matches_a_hand_count.
"""

from __future__ import annotations

import sqlite3
import time
import warnings
from pathlib import Path
from typing import Any

import pytest

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    author_world_model,
    dream_pass,
    maintenance_due,
    world_model_pass,
)
from abstractmemory.activation_gate import GATE_FLOOR, activation, threshold
from abstractmemory.memory_tasks import MemoryTaskQueue
from abstractmemory.sleep_policy import SleepTuning

SCOPE, OWNER = "life", "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
MIND = {"kind": "entity-mind", "id": OWNER}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "step", "run_id": "run-q", "seq": 1}]
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
    system.kind, system.path = request.param, tmp_path / "memory.sqlite3"
    yield system
    journal.close()
    store.close()


def _form(system, key: str, kind: str = "episode", method: str = "mechanical-v2", **kw: Any) -> str:
    attrs = dict(kw.pop("attributes", {}) or {})
    if method:
        attrs["digest_method"] = method
    kw.setdefault("title", f"exchange {key}")
    kw.setdefault("digest", f"User: about {key}. Nerin: noted.")
    [gid] = system.remember_many([MemoryRecordInput(kind=kind, attributes=attrs, **kw)],
                                 scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _task(system, gid: str, kind: str = "digest.rewrite"):
    [t] = system.tasks.tasks(kind=(kind,), target_id=gid)
    return t


def _live_ids(system):
    return {t["task_id"] for t in system.tasks.tasks(status=("pending", "deferred", "leased"))}


# --------------------------------------------------------------------------- enqueue at formation


def test_formation_enqueues_one_task_per_mechanical_record(home) -> None:
    ep = _form(home, "turn-1")
    authored = _form(home, "turn-2", method="entity-authored")
    unlabeled = _form(home, "turn-3", method="")
    interest = _form(home, "interest-1", kind="interest", method="mechanical-v2")
    offer = _form(home, "offer-1", kind="summary", edges=(("summarizes", ep),),
                  attributes={"maintenance_candidate": True, "review_required": True})
    tasks = home.tasks.tasks()
    assert [(t["kind"], t["target_id"]) for t in tasks] == [("digest.rewrite", ep)]
    t = tasks[0]
    assert t["status"] == "pending" and t["strength"] == 1.0 and t["capability"] == "summaries"
    assert t["basis_version"] == 0 and t["cause"] == {"cause": "formation"} and t["priority"] == 10
    assert t["cost_hint"]["input_tokens"] > 0
    _form(home, "turn-1")                      # an at-least-once replay of the same formation
    assert len(home.tasks.tasks()) == 1
    for gid in (authored, unlabeled, interest, offer):
        assert home.tasks.tasks(target_id=gid) == []


def test_a_home_without_the_opt_in_enqueues_nothing(tmp_path) -> None:
    path = tmp_path / "plain.sqlite3"
    system = MemorySystem(store=SQLiteTripleStore(path), journal=SQLiteJournal(path))
    assert system.tasks is None
    _form(system, "turn-1")
    with sqlite3.connect(str(path)) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'memq_%'").fetchall() == []
    system.close()
    system.store.close()


def test_opening_a_home_whose_queue_exists_takes_no_write_lock(tmp_path) -> None:
    path = tmp_path / "home.sqlite3"
    first = SQLiteTripleStore(path)
    MemoryTaskQueue(first)
    first.close()
    writer = sqlite3.connect(str(path), isolation_level=None, timeout=0.1)
    writer.execute("BEGIN IMMEDIATE")          # another process holds the write lock
    try:
        started = time.monotonic()
        store = SQLiteTripleStore(path)
        MemoryTaskQueue(store)
        assert time.monotonic() - started < 2.0
        store.close()
    finally:
        writer.execute("ROLLBACK")
        writer.close()


# --------------------------------------------------------------------------- activation-driven selection


def _enqueue(system, target: str, strength: float, kind: str = "digest.rewrite", **kw: Any) -> str:
    return system.tasks.enqueue(kind, target, scope=SCOPE, owner_id=OWNER, basis=f"{target}@b",
                                strength=strength, cause={"cause": "backfill"}, now=T0, **kw)["task_id"]


def test_highest_activation_first_and_sensitivity_moves_the_gate(home) -> None:
    weak = _enqueue(home, "ex:a", 0.3)
    strong = _enqueue(home, "ex:b", 1.0)
    middle = _enqueue(home, "ex:c", 0.6)
    faint = _enqueue(home, "ex:d", 0.05)
    sel = home.tasks.select_for_window(10_000, 1.0, window="idle", now=T0)
    assert [t["task_id"] for t in sel["tasks"]] == [strong, middle, weak]
    acts = [t["activation"] for t in sel["tasks"]]
    assert acts == sorted(acts, reverse=True) and all(a >= GATE_FLOOR for a in acts)
    assert acts[0] == pytest.approx(activation(1.0))
    assert [(o["task_id"], o["reason"]) for o in sel["left_out"]] == [(faint, "below_gate")]
    assert threshold() == pytest.approx(0.1338, abs=1e-3)
    # A more sensitive mind lets the faint signal through; a less sensitive one keeps only the strong.
    assert faint in {t["task_id"] for t in home.tasks.select_for_window(10_000, 5.0, window="idle", now=T0)["tasks"]}
    dull = home.tasks.select_for_window(10_000, 0.2, window="idle", now=T0)
    assert [t["task_id"] for t in dull["tasks"]] == [strong]
    with pytest.raises(ValueError):
        home.tasks.select_for_window(10, 0.0)


def test_budget_and_hard_cap_bound_the_window_never_a_count(home) -> None:
    ids = [_enqueue(home, f"ex:t{i}", 1.0 - i * 0.1) for i in range(4)]
    sel = home.tasks.select_for_window(130, window="idle", now=T0)    # default 60 s per task
    assert [t["task_id"] for t in sel["tasks"]] == ids[:2] and sel["planned_seconds"] == 120
    assert {o["task_id"]: o["reason"] for o in sel["left_out"]} == {ids[2]: "over_budget", ids[3]: "over_budget"}
    assert home.tasks.select_for_window(0, window="idle", now=T0)["tasks"] == []
    assert len(home.tasks.select_for_window(10_000, window="idle", now=T0)["tasks"]) == 4
    capped = home.tasks.select_for_window(10_000, window="idle", hard_cap=1, now=T0)
    assert len(capped["tasks"]) == 1 and capped["left_out_counts"] == {"hard_cap": 3}
    cheap = home.tasks.select_for_window(130, window="idle", cost_of=lambda t: 30.0, now=T0)
    assert len(cheap["tasks"]) == 4
    # Measured times replace the default: a completed task that reports 10 s makes four fit in 45 s.
    [c] = home.tasks.claim([ids[0]], holder="rt", now=T0)["claimed"]
    home.tasks.ack(c["task_id"], holder="rt", result={"outcome": "unchanged", "seconds": 10.0}, now=T0)
    measured = home.tasks.select_for_window(45, window="idle", now=T0)
    assert len(measured["tasks"]) == 3 and measured["tasks"][0]["cost"]["basis"] == "measured"


def test_selection_is_a_pure_read_that_accounts_for_every_live_task(home) -> None:
    ep = _form(home, "turn-1")
    _form(home, "close-1", kind="summary", method="mechanical-floor-v1", edges=(("summarizes", ep),))
    _enqueue(home, "ex:dream", 1.0, kind="dream.narrate")
    _enqueue(home, "ex:cold", 0.01)
    before = [(t["task_id"], t["status"], t["updated_at"]) for t in home.tasks.tasks()]
    sel = home.tasks.select_for_window(10_000, window="turn", now=T0)
    assert [(t["task_id"], t["status"], t["updated_at"]) for t in home.tasks.tasks()] == before
    seen = [t["task_id"] for t in sel["tasks"]] + [o["task_id"] for o in sel["left_out"]]
    assert sorted(seen) == sorted(_live_ids(home)) and len(seen) == len(set(seen))
    reasons = {o["reason"] for o in sel["left_out"]}
    assert {"window", "blocked", "below_gate"} <= reasons      # dream at turn; summary blocked; cold below gate
    night = home.tasks.select_for_window(10_000, window="night", now=T0)
    assert any(t["kind"] == "dream.narrate" for t in night["tasks"])


# --------------------------------------------------------------------------- leases, retries, dependencies


def test_an_expired_lease_returns_the_task(home) -> None:
    tid = _enqueue(home, "ex:a", 1.0)
    [t] = home.tasks.claim([tid], holder="loop", lease_seconds=60, now=T0)["claimed"]
    assert t["status"] == "leased" and t["attempts"] == 1 and t["lease_holder"] == "loop"
    assert home.tasks.claim([tid], holder="gw", now="2026-11-08T03:00:30+00:00")["refused"] == [
        {"task_id": tid, "reason": "leased"}]
    assert home.tasks.select_for_window(1000, window="idle", now="2026-11-08T03:00:30+00:00")["left_out"][0][
        "reason"] == "leased"
    later = "2026-11-08T03:02:00+00:00"
    assert [x["task_id"] for x in home.tasks.select_for_window(1000, window="idle", now=later)["tasks"]] == [tid]
    [again] = home.tasks.claim([tid], holder="gw", now=later)["claimed"]
    assert again["lease_holder"] == "gw" and again["attempts"] == 2
    assert [e["event"] for e in home.tasks.log(tid)] == ["enqueued", "claimed", "lease_expired", "claimed"]
    assert home.tasks.ack(tid, holder="loop", result={})["reason"] == "not_held"


def test_defer_spends_no_attempt_and_retries_fail_at_max(home) -> None:
    tid = _enqueue(home, "ex:a", 1.0)
    home.tasks.claim([tid], holder="rt", now=T0)
    out = home.tasks.release(tid, holder="rt", outcome="defer", reason="endpoint unreachable",
                             until="2026-11-08T04:00:00+00:00", now=T0)
    assert out["task"]["status"] == "deferred" and out["task"]["attempts"] == 0
    assert home.tasks.select_for_window(1000, window="idle", now=T0)["left_out"][0]["reason"] == "not_before"
    later = "2026-11-08T04:00:01+00:00"
    for n in range(1, 4):
        [t] = home.tasks.claim([tid], holder="rt", now=later)["claimed"]
        assert t["attempts"] == n
        res = home.tasks.release(tid, holder="rt", outcome="retry", reason=f"bad schema {n}", now=later)
    assert res["task"]["status"] == "failed" and res["task"]["error"] == "bad schema 3"
    assert home.tasks.claim([tid], holder="rt", now=later)["refused"] == [{"task_id": tid, "reason": "failed"}]


def test_three_expired_leases_fail_the_task(home) -> None:
    tid = _enqueue(home, "ex:crashy", 1.0, max_attempts=3)
    times = ["2026-11-08T03:00:00+00:00", "2026-11-08T03:20:00+00:00", "2026-11-08T03:40:00+00:00"]
    for at in times:
        assert home.tasks.claim([tid], holder="rt", lease_seconds=60, now=at)["claimed"]
    assert home.tasks.claim([tid], holder="rt", now="2026-11-08T04:00:00+00:00")["refused"][0]["reason"] == "failed"
    assert home.tasks.task(tid)["status"] == "failed"


def test_skip_is_terminal_with_its_measurement(home) -> None:
    tid = _enqueue(home, "ex:huge", 1.0)
    home.tasks.claim([tid], holder="rt", now=T0)
    out = home.tasks.release(tid, holder="rt", outcome="skip", reason="over_context",
                             detail={"tokens": 71_374, "cap": 56_000}, now=T0)
    assert out["task"]["status"] == "skipped" and out["task"]["result"] == {"tokens": 71_374, "cap": 56_000}
    assert tid not in _live_ids(home)


def test_a_summary_waits_for_its_episodes(home) -> None:
    ep = _form(home, "turn-1")
    summary = _form(home, "close-1", kind="summary", method="mechanical-floor-v1", edges=(("summarizes", ep),))
    s_task, e_task = _task(home, summary), _task(home, ep)
    assert s_task["depends_on"] == [e_task["task_id"]] and s_task["priority"] == 30
    sel = home.tasks.select_for_window(10_000, window="turn", now=T0)
    assert [t["task_id"] for t in sel["tasks"]] == [e_task["task_id"]]
    assert {o["task_id"]: o["reason"] for o in sel["left_out"]}[s_task["task_id"]] == "blocked"
    assert home.tasks.claim([s_task["task_id"]], holder="rt", now=T0)["refused"][0]["reason"] == "blocked"
    home.tasks.claim([e_task["task_id"]], holder="rt", now=T0)
    home.rewrite_digest(ep, text="We talked about turn one.", author=MIND, reader=READER, sources=STEP,
                        cause="formation", expected_version=0, task_id=e_task["task_id"])
    assert home.tasks.task(e_task["task_id"])["status"] == "done"
    assert [t["task_id"] for t in home.tasks.select_for_window(10_000, window="turn")["tasks"]] == [
        s_task["task_id"]]


# --------------------------------------------------------------------------- settled by the 0059 verbs


def test_a_rewrite_acks_its_task_in_the_same_transaction(home) -> None:
    ep = _form(home, "turn-1")
    t = _task(home, ep)
    home.tasks.claim([t["task_id"]], holder="rt", now=T0)
    out = home.rewrite_digest(ep, text="Understood words.", author=MIND, reader=READER, sources=STEP,
                              cause="formation", expected_version=0, task_id=t["task_id"])
    done = home.tasks.task(t["task_id"])
    assert done["status"] == "done" and done["result"]["version"] == 1
    assert done["result"]["version_id"] == out["version_id"] and done["result"]["model"] == READER["model"]
    assert home.tasks.ack(t["task_id"], holder="rt", result={})["reason"] == "already_done"


def test_a_failed_apply_rolls_back_the_ack_too(home, monkeypatch) -> None:
    if home.kind != "sqlite":
        pytest.skip("one transaction is the SQLite home's guarantee")
    ep = _form(home, "turn-1")
    t = _task(home, ep)
    home.tasks.claim([t["task_id"]], holder="rt", now=T0)

    def crash(*a, **k):
        raise RuntimeError("power cut mid-apply")

    monkeypatch.setattr(home.store, "_rewrite_row_on", crash)
    with pytest.raises(RuntimeError):
        home.rewrite_digest(ep, text="Words that never land.", author=MIND, reader=READER, sources=STEP,
                            cause="formation", expected_version=0, task_id=t["task_id"])
    assert home.tasks.task(t["task_id"])["status"] == "leased"
    assert home.journal.versions(record_id=ep) == []
    assert "never land" not in home.record_understanding(ep)["digest"]


def test_a_rewrite_supersedes_stale_tasks(home) -> None:
    ep = _form(home, "turn-1")
    t = _task(home, ep)
    home.rewrite_digest(ep, text="An operator's reading.", author={"kind": "operator", "id": "laurent"},
                        cause="operator", expected_version=0)
    assert home.tasks.task(t["task_id"])["status"] == "superseded"
    # An older basis can no longer be enqueued for that record.
    again = home.tasks.enqueue("digest.rewrite", ep, scope=SCOPE, owner_id=OWNER, basis="x@v0",
                               basis_version=0, strength=1.0, cause={"cause": "backfill"})
    assert again["enqueued"] is False and again["reason"] == "stale_basis"


def test_supersede_stale_catches_a_rewrite_the_queue_did_not_see(tmp_path) -> None:
    store, journal = InMemoryTripleStore(), InMemoryJournal()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        a = MemorySystem(store=store, journal=journal, task_queue=True)
        b = MemorySystem(store=store, journal=journal)              # same home, no queue
    ep = _form(a, "turn-1")
    b.rewrite_digest(ep, text="Words written elsewhere.", author={"kind": "operator", "id": "op"},
                     cause="operator", expected_version=0)
    assert _task(a, ep)["status"] == "pending"
    assert a.tasks.supersede_stale(a) == [_task(a, ep)["task_id"]]
    assert _task(a, ep)["status"] == "superseded"


def test_cards_and_dreams_enqueue_and_their_verbs_ack(home) -> None:
    for i in range(3):
        _form(home, f"ada-{i}", digest=f"Worked with Ada, day {i}.", participants=("person:ada", OWNER))
    out = world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=SleepTuning(world_model_evidence_floor=3))
    card = out["formed"][0]["card_id"]
    ct = _task(home, card, "card.author")
    assert ct["capability"] == "summaries" and ct["strength"] == 1.0
    home.tasks.claim([ct["task_id"]], holder="rt", now=T0)
    author_world_model(home, target="person:ada", text="Ada, the archivist I trust.", scope=SCOPE, owner_id=OWNER,
                       author=MIND, reader=READER, sources=STEP, task_id=ct["task_id"])
    assert home.tasks.task(ct["task_id"])["status"] == "done"
    # New evidence revises the card: a new authoring task, the old card's live task superseded.
    _form(home, "ada-9", digest="Ada finished the index.", participants=("person:ada", OWNER))
    out2 = world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=SleepTuning(world_model_evidence_floor=3))
    card2 = out2["formed"][0]["card_id"]
    ct2 = _task(home, card2, "card.author")
    assert ct2["cause"]["cause"] == "evidence" and ct2["strength"] < 1.0      # a +delta: the share that is new

    _form(home, "s-1", digest="The connection pool saturated at noon.", keywords=("pool", "saturation", "noon"))
    _form(home, "s-3", digest="Planted the garden sensors at noon.", keywords=("garden", "sensors", "noon"))
    _form(home, "s-2", kind="lesson", method="", digest="Batching the noon cron fixed the pool.",
          keywords=("pool", "batching"))
    night = dream_pass(home, scopes=SCOPES, owner_id=OWNER)
    assert night["dream_record_id"], night["skipped_reason"]
    dt = _task(home, night["dream_record_id"], "dream.narrate")
    assert dt["windows"] == ["night", "nap"]
    assert home.tasks.claim([dt["task_id"]], holder="rt", window="turn", now=T0)["refused"][0]["reason"] == "window"
    home.tasks.claim([dt["task_id"]], holder="rt", window="night", now=T0)
    home.narrate_dream(night["dream_record_id"], text="I dreamt of a pool in a garden.", author=MIND,
                       reader=READER, sources=STEP, task_id=dt["task_id"])
    assert home.tasks.task(dt["task_id"])["status"] == "done"


def test_claim_records_the_window_and_what_it_left_out(home) -> None:
    a, b = _enqueue(home, "ex:a", 1.0), _enqueue(home, "ex:b", 0.9)
    sel = home.tasks.select_for_window(70, window="turn", now=T0)
    out = home.tasks.claim(sel, holder="loop", now=T0)
    assert [t["task_id"] for t in out["claimed"]] == [a]
    [record] = home.tasks.left_out(holder="loop")
    assert record["window"] == "turn" and record["claimed"] == [a]
    assert record["left_out"] == [{"task_id": b, "kind": "digest.rewrite", "target_id": "ex:b",
                                   "reason": "over_budget", "activation": round(activation(0.9), 6),
                                   "cost_seconds": 60.0}]
    home.tasks.claim(home.tasks.select_for_window(0, window="turn", now=T0), holder="loop", now=T0)
    assert len(home.tasks.left_out(holder="loop")) == 1     # one row per (holder, window), replaced
    with pytest.raises(ValueError):
        home.tasks.claim([a], holder="")


# --------------------------------------------------------------------------- debt, backfill, packet, cadence


def test_understanding_debt_matches_a_hand_count(home) -> None:
    eps = [_form(home, f"turn-{i}") for i in range(3)]
    _form(home, "close-1", kind="summary", method="mechanical-floor-v1", edges=(("summarizes", eps[0]),))
    _form(home, "authored", method="entity-authored")
    _form(home, "offer", kind="summary", edges=(("summarizes", eps[1]),),
          attributes={"maintenance_candidate": True, "review_required": True})
    _form(home, "dedup", kind="summary", method="mechanical-dedup-v1", edges=(("summarizes", eps[2]),))
    _form(home, "interest", kind="interest", method="mechanical-v2")
    _form(home, "dream-1", kind="dream", method="", digest="Two islands lit up.")
    debt = home.understanding_debt(scopes=SCOPES)
    assert debt["debt"] == {"digest.rewrite": {"episode": 3, "summary": 1}, "dream.narrate": {"dream": 1}}
    assert debt["total"] == 5 and debt["unqueued"] == 1           # the dream was formed outside dream_pass
    assert debt["queue"]["digest.rewrite"]["pending"] == 4
    assert debt["by_capability"] == {"summaries": 4}
    assert debt["oldest_pending"]["kind"] == "digest.rewrite"
    # Widening the consent set counts the earlier manual pass's label too (operator decision 6).
    wide = home.understanding_debt(scopes=SCOPES, methods=("mechanical-v2", "mechanical-floor-v1", "entity-authored"))
    assert wide["debt"]["digest.rewrite"]["episode"] == 4


def test_enqueue_debt_is_dry_run_by_default_and_ranks_by_lived_use(tmp_path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        plain = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())
    hot, cold = _form(plain, "hot"), _form(plain, "cold")
    for i in range(5):
        plain.commit_selection(f"t-{i}", [hot])
    system = MemorySystem(store=plain.store, journal=plain.journal, task_queue=True)
    dry = system.enqueue_debt(scopes=SCOPES)
    assert dry["dry_run"] is True and dry["would_enqueue"] == 2 and system.tasks.tasks() == []
    strengths = {t["target_id"]: t["strength"] for t in dry["tasks"]}
    assert strengths[hot] == pytest.approx(1.0) and strengths[cold] == pytest.approx(0.1)
    real = system.enqueue_debt(scopes=SCOPES, dry_run=False)
    assert real["enqueued"] == 2 and all(t["priority"] == 90 for t in system.tasks.tasks())
    assert system.enqueue_debt(scopes=SCOPES, dry_run=False)["enqueued"] == 0
    assert system.understanding_debt(scopes=SCOPES)["unqueued"] == 0


def test_task_packet_keeps_every_item_whole(home) -> None:
    long_text = "word " * 400
    eps = [_form(home, f"turn-{i}", digest=f"{i} {long_text}") for i in range(3)]
    summary = _form(home, "close-1", kind="summary", method="mechanical-floor-v1",
                    edges=tuple(("summarizes", e) for e in eps))
    t = _task(home, summary)
    full = home.task_packet(t["task_id"])
    assert len(full["sources"]) == 3 and full["left_out"] == []
    assert {s["digest"] for s in full["sources"]} == {home.record_understanding(e)["digest"] for e in eps}
    assert full["expected_version"] == 0 and full["target_state"] == "live"
    tight = home.task_packet(t["task_id"], token_budget=800)
    kept = {s["record_id"] for s in tight["sources"]}
    assert len(kept) == 1 and len(tight["left_out"]) == 2
    assert all(s["digest"] == home.record_understanding(s["record_id"])["digest"] for s in tight["sources"])
    assert {x["reason"] for x in tight["left_out"]} == {"token_budget"}


def test_maintenance_due_counts_night_and_ripple_work(home) -> None:
    _form(home, "turn-1")
    base = maintenance_due(home.store, home.journal, scopes=SCOPES, tasks=home.tasks)
    assert base["pending_tasks"] == {"digest.rewrite": 1} and base["due"] is False
    _enqueue(home, "ex:dream", 1.0, kind="dream.narrate")
    due = maintenance_due(home.store, home.journal, scopes=SCOPES, tasks=home.tasks)
    assert due["due"] is True and any("dream.narrate" in r for r in due["reasons"])
    assert "pending_tasks" not in maintenance_due(home.store, home.journal, scopes=SCOPES)
