"""Ripple v1: a change in a memory is reconsidered through the memories connected to it (backlog 0061; ADR 0001).

THE RULING (operator, 2026-11-07): "a disruptive fact given in the present should trigger a reaction (surprise?)
and slowly get to actual consistency by rippling through the connected memories until a certain activation
threshold ... and this could consolidate also during the sleep/dream phase ... The goal is not to destabilize the
entity, but to give it the opportunity to revisit what it thinks it knows and possibly expand its understanding."

THE PROCESS (memory owns it end to end, ADR 0001 / 0002; the host runs the reader):
1. `seed_ripple(system, seed_id, change=..., cause=...)`: the seed is the entity's own election ("this changes what
   I held about #tag", cause `evidence`, passed in by the host) or a rewrite whose reader reported `revised` /
   `overturned`. Its magnitude is the reader's enum (`activation_gate.CHANGE_MAGNITUDE`), scaled by how far the text
   moved when both vectors exist. An election also re-reads the seed itself (hop 0).
2. Propagation (hop 1 from the seed, hop 2 from a reconsidered memory that changed): the candidates are the record
   edges in both directions (`activation_gate.RELATION_WEIGHTS`; context relations and usage trails carry nothing),
   the cards whose evidence holds the source, and the source's nearest digests by vector (`similarity_weight`).
   Each candidate's potential = received impact x reliance x DECAY, accumulated over every source of the same
   ripple; it is reconsidered when `logistic(potential)` reaches the floor. EVERY gate decision is stored with its
   potential (`memq_ripple_gates`), so thresholds can be re-tuned from the record.
3. Reconsideration = a `ripple.reconsider` task (0060), run by the host's reader: `unchanged` settles with no write;
   a rewrite (cause `ripple`, "revised after X") makes a version and its measured change, at most what it
   received, is handed on one hop further.
4. A ripple that changed two or more memories yields one `ripple.consolidate` task, leased only in a nightly sleep
   window: a first-person "what this changes" record (kind summary, `summary_role: re-understanding`, `summarizes`
   edges to every changed memory, `derived_from` the seed), never batch-rewritten afterwards.

SAFEGUARDS: at most `MAX_HOPS` hops and `RIPPLE_BUDGET` reconsiderations per ripple (the rest is recorded in
`left_out` with its potential and warned, never dropped); each memory at most once per ripple (refractory); the
protected kinds, diaries and consolidation records are never reconsidered (listed in `left_out` as protected); a
ripple closes nothing; every ripple rewrite is a version (`revert_ripple` restores what the ripple changed).
SURPRISE is recorded in words only (`surprise`, the entity's own words): no feeling kind is written (the operator has
not decided one). Numbers choose; the reader decides what a memory now means; nothing here reads text.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from . import activation_gate as gate
from .memory_tasks import MemoryTaskQueue, _dump, _iso, _load, _utc

__all__ = [
    "RIPPLE_PROTECTED_KINDS",
    "form_consolidation",
    "refresh_ripples",
    "revert_ripple",
    "ripple",
    "ripple_context",
    "ripples",
    "seed_ripple",
    "settle_reconsideration",
]

#: Never reconsidered by a ripple: the entity's own acts, its book, and the ripple's own consolidation records.
RIPPLE_PROTECTED_KINDS = frozenset({"diary", "value", "purpose", "trait", "interest", "realization"})
SEED_CAUSES = frozenset({"evidence", "formation", "backfill", "ripple", "operator"})
CONSOLIDATION_METHOD = "authored-consolidation-v1"


def _queue(system: Any) -> MemoryTaskQueue:
    queue = getattr(system, "tasks", None)
    if queue is None:
        raise ValueError("the ripple runs over the memory task queue: open the home with MemorySystem(task_queue=True)")
    return queue


def _ripple_row(queue: MemoryTaskQueue, ripple_id: str) -> Optional[Dict[str, Any]]:
    rows = queue._read(f"SELECT * FROM {queue.t_ripples} WHERE ripple_id = ?", (str(ripple_id),))
    if not rows:
        return None
    r = rows[0]
    return {"ripple_id": r["ripple_id"], "seed_id": r["seed_id"], "scope": r["scope"], "owner_id": r["owner_id"],
            "cause": _load(r["cause_json"], {}), "magnitude": float(r["magnitude"]), "surprise": r["surprise"],
            "status": r["status"], "hops_max": int(r["hops_max"]), "budget": int(r["budget"]),
            "reconsidered": int(r["reconsidered"]), "changed": _load(r["changed_json"], []),
            "left_out": _load(r["left_out_json"], []), "opened_at": r["opened_at"], "settled_at": r["settled_at"]}


def _resolve(system: Any, rid: str) -> Any:
    from .understanding import _resolve as resolve

    return resolve(system, rid)


def _kind(a: Any) -> str:
    return str((a.attributes or {}).get("record_kind") or "")


def _excluded(a: Any) -> Optional[str]:
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    if _kind(a) in RIPPLE_PROTECTED_KINDS:
        return "protected: the entity's own act"
    if attrs.get("summary_role") == "re-understanding":
        return "protected: a ripple's consolidation record"
    if attrs.get("maintenance_candidate") or attrs.get("review_required"):
        return "protected: a review offer"
    return None


# --------------------------------------------------------------------------- candidates (pure read)


def _candidates(system: Any, source: Any) -> Dict[str, Tuple[float, str]]:
    """{graph id: (reliance in [0, 1], via)} for one source record: edges both ways, cards on its evidence, nearest
    digests. One connection per candidate per source: the strongest channel."""
    from .store import TripleQuery
    from .world_model import current_world_models

    store = system.store
    gid = str(source.subject)
    owner = str(source.owner_id or "")
    found: Dict[str, Tuple[float, str]] = {}

    def offer(rid: str, weight: float, via: str) -> None:
        if rid and rid != gid and weight > 0.0 and weight > found.get(rid, (0.0, ""))[0]:
            found[rid] = (float(weight), via)

    for e in store.query(TripleQuery(subject=gid, limit=0)):
        if (e.attributes or {}).get("record_edge") and e.predicate in gate.RELATION_WEIGHTS:
            offer(str(e.object), gate.RELATION_WEIGHTS[e.predicate], f"edge:{e.predicate}")
    for e in store.query(TripleQuery(object=gid, limit=0)):
        if (e.attributes or {}).get("record_edge") and e.predicate in gate.RELATION_WEIGHTS:
            offer(str(e.subject), gate.RELATION_WEIGHTS[e.predicate], f"edge:{e.predicate}<-")
    for card in current_world_models(store, scope=source.scope, owner_id=owner, journal=system.journal).values():
        if gid in {str(s) for s in ((card.attributes or {}).get("known_source_ids") or ())}:
            offer(str(card.subject), gate.RELATION_WEIGHTS["derived_from"], "card:evidence")
    vector = store.stored_vector(str(source.assertion_id or ""))
    if vector is not None:
        try:
            near = store.query(TripleQuery(query_vector=vector, scope=source.scope, owner_id=owner or None,
                                           limit=gate.VECTOR_TOP_K + 1))
        except ValueError:
            near = []
        for n in near:
            attrs = n.attributes if isinstance(n.attributes, dict) else {}
            if attrs.get("record_kind") and not attrs.get("record_edge"):
                score = float((attrs.get("_retrieval") or {}).get("score") or 0.0)
                offer(str(n.subject), gate.similarity_weight(score), "similarity")
    return found


def _propagate(system: Any, queue: MemoryTaskQueue, rip: Dict[str, Any], source: Any, *, hop: int,
               received: float, depends_on: Sequence[str] = (), dry_run: bool = False,
               now: Optional[str] = None) -> List[Dict[str, Any]]:
    """Gate every candidate of `source` at `hop` and record the decision (or, dry_run, only report it)."""
    from .folds import closure_exclusions

    at = _iso(_utc(now))
    closed = closure_exclusions(system.journal, system.journal.current_seq())
    decisions: List[Dict[str, Any]] = []
    rid = rip["ripple_id"]
    members = {t["target_id"] for t in queue.tasks(ripple_id=rid, kind=("ripple.reconsider",))}
    members.add(rip["seed_id"])
    for cand_id, (weight, via) in sorted(_candidates(system, source).items()):
        cand = _resolve(system, cand_id)
        if cand is None or str(cand.owner_id or "") != rip["owner_id"]:
            continue  # another owner's memory is never this mind's to reconsider (ADR 0003 decision 2)
        cand_id = str(cand.subject)
        prior = queue._read(
            f"SELECT COALESCE(SUM(potential), 0) FROM {queue.t_gates} WHERE ripple_id = ? AND candidate_id = ? "
            "AND decision = 'below_floor'", (rid, cand_id))[0][0] if not dry_run else 0.0
        potential = float(prior) + float(received) * weight * gate.DECAY
        act = gate.logistic(potential)
        reason = ""
        if cand_id in members:
            decision, reason = "refractory", "already reconsidered in this ripple"
        elif cand.assertion_id in closed or cand.subject in closed:
            decision, reason = "closed", "the memory is closed; its replacement carries its meaning"
        elif _excluded(cand):
            decision, reason = "protected", _excluded(cand)
        elif act < gate.GATE_FLOOR:
            decision, reason = "below_floor", f"activation {act:.4f} < floor {gate.GATE_FLOOR}"
        elif hop > gate.MAX_HOPS:
            decision, reason = "max_hops", f"hop {hop} > {gate.MAX_HOPS}"
        elif rip["reconsidered"] >= rip["budget"]:
            decision, reason = "budget", f"{rip['budget']} reconsiderations already enqueued"
        else:
            decision = "reconsider"
        d = {"candidate_id": cand_id, "hop": hop, "via": via, "potential": round(potential, 6),
             "activation": round(act, 6), "decision": decision, "reason": reason}
        decisions.append(d)
        if dry_run:
            if decision == "reconsider":
                rip["reconsidered"] += 1
                members.add(cand_id)
            continue
        if decision == "reconsider":
            res = queue.enqueue(
                "ripple.reconsider", cand_id, scope=cand.scope, owner_id=rip["owner_id"],
                assertion_id=str(cand.assertion_id or ""), basis=rid, strength=min(1.0, potential),
                cause={"cause": "ripple", "ripple_id": rid, "seed_id": rip["seed_id"], "hops": hop,
                       "from": str(source.subject), "via": via},
                depends_on=depends_on, ripple_id=rid, hop=hop, now=now)
            if res["enqueued"]:
                rip["reconsidered"] += 1
                members.add(cand_id)
        if decision in ("protected", "max_hops", "budget"):
            rip["left_out"].append({"record_id": cand_id, "hop": hop, "reason": decision if decision != "protected"
                                    else reason, "potential": round(potential, 6)})

        def write(cur: Any, d: Dict[str, Any] = d) -> None:
            cur.execute(f"INSERT INTO {queue.t_gates} (ripple_id, candidate_id, hop, via, potential, activation, "
                        "decision, reason, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (rid, d["candidate_id"], d["hop"], d["via"], d["potential"], d["activation"], d["decision"],
                         d["reason"], at))

        queue._txn(None, write)
    if not dry_run:
        _save(queue, rip)
        if any(x["reason"] == "budget" for x in rip["left_out"]):
            warnings.warn(
                f"#[WARNING:TRUNCATION] ripple {rid}: budget {rip['budget']} reached; "
                f"{sum(1 for x in rip['left_out'] if x['reason'] == 'budget')} memories recorded in left_out",
                RuntimeWarning, stacklevel=3)
    return decisions


def _save(queue: MemoryTaskQueue, rip: Mapping[str, Any]) -> None:
    def write(cur: Any) -> None:
        cur.execute(f"UPDATE {queue.t_ripples} SET status = ?, reconsidered = ?, changed_json = ?, left_out_json = ?, "
                    "settled_at = ? WHERE ripple_id = ?",
                    (rip["status"], int(rip["reconsidered"]), _dump(list(rip["changed"])),
                     _dump(list(rip["left_out"])), rip.get("settled_at"), rip["ripple_id"]))

    queue._txn(None, write)


# --------------------------------------------------------------------------- the verbs


def seed_ripple(
    system: Any, seed_id: str, *,
    cause: Union[str, Mapping[str, Any]],
    change: str = "revised",
    magnitude: Optional[float] = None,
    cosine_distance: Optional[float] = None,
    surprise: Optional[str] = None,
    reconsider_seed: Optional[bool] = None,
    budget: int = gate.RIPPLE_BUDGET,
    dry_run: bool = False,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """Open a ripple from `seed_id`. `cause` = `evidence` for the entity's own `revise` election (pass its
    election and evidence in the mapping), or the cause of the rewrite whose reader reported `change`. Magnitude:
    `magnitude` when given, else `activation_gate.measured_change(change, cosine_distance)`. `reconsider_seed`
    (default: True for an election, False for a rewrite) re-reads the seed itself first; its neighbours then wait
    for it. `surprise` is the entity's own words, stored as words. `dry_run=True` writes nothing and returns the
    hop-1 decisions (the bound ADR 0001 decision 5 asks for). Idempotent: the same seed, cause and seed version is
    one ripple. Returns {ripple_id, opened, magnitude, decisions, reconsider_task_ids, left_out}."""
    from .understanding import _attrs, _cause, _current_version, _field_of

    queue = _queue(system)
    seed = _resolve(system, seed_id)
    if seed is None:
        raise ValueError(f"unknown record {seed_id!r}: no formed record with that id")
    cause_d = {"cause": cause} if isinstance(cause, str) else dict(cause)
    if str(cause_d.get("cause") or "") not in SEED_CAUSES:
        raise ValueError(f"a ripple's cause must be one of {sorted(SEED_CAUSES)}")
    cause_d = _cause(cause_d)
    mag = float(magnitude) if magnitude is not None else gate.measured_change(change, cosine_distance)
    if not (0.0 <= mag <= 1.0):
        raise ValueError(f"magnitude must be within [0, 1] (got {mag!r})")
    if int(budget) < 0:
        raise ValueError("budget must be non-negative")
    attrs = _attrs(seed)
    version = _current_version(attrs, _field_of(_kind(seed)))
    rid = "rpl-" + hashlib.sha256(
        f"{seed.subject}|{json.dumps(cause_d, sort_keys=True)}|{version}".encode("utf-8")).hexdigest()[:24]
    existing = _ripple_row(queue, rid)
    if existing is not None and not dry_run:
        return {"ripple_id": rid, "opened": False, "magnitude": existing["magnitude"], "decisions": [],
                "reconsider_task_ids": [t["task_id"] for t in queue.tasks(ripple_id=rid)],
                "left_out": existing["left_out"]}
    at = _iso(_utc(now))
    rip = {"ripple_id": rid, "seed_id": str(seed.subject), "scope": seed.scope, "owner_id": str(seed.owner_id or ""),
           "cause": cause_d, "magnitude": mag, "surprise": surprise, "status": "open", "hops_max": gate.MAX_HOPS,
           "budget": int(budget), "reconsidered": 0, "changed": [], "left_out": [], "opened_at": at,
           "settled_at": None}
    elect = cause_d["cause"] == "evidence" if reconsider_seed is None else bool(reconsider_seed)
    if dry_run:
        decisions = _propagate(system, queue, rip, seed, hop=1, received=mag, dry_run=True, now=now)
        return {"ripple_id": rid, "opened": False, "dry_run": True, "magnitude": mag, "decisions": decisions,
                "reconsider_task_ids": [], "left_out": []}

    def write(cur: Any) -> None:
        cur.execute(
            f"INSERT INTO {queue.t_ripples} (ripple_id, seed_id, scope, owner_id, cause_json, magnitude, surprise, "
            "status, hops_max, budget, reconsidered, changed_json, left_out_json, opened_at, settled_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '[]', '[]', ?, NULL)",
            (rid, rip["seed_id"], rip["scope"], rip["owner_id"], _dump(cause_d), mag, surprise, "open",
             gate.MAX_HOPS, int(budget), at))

    queue._txn(None, write)
    depends: List[str] = []
    if elect:
        excluded = _excluded(seed)
        if excluded:
            rip["left_out"].append({"record_id": rip["seed_id"], "hop": 0, "reason": excluded, "potential": mag})
        else:
            res = queue.enqueue(
                "ripple.reconsider", rip["seed_id"], scope=seed.scope, owner_id=rip["owner_id"],
                assertion_id=str(seed.assertion_id or ""), basis=rid, strength=mag,
                cause={"cause": "ripple", "ripple_id": rid, "seed_id": rip["seed_id"], "hops": 0, "via": "seed"},
                ripple_id=rid, hop=0, now=now)
            rip["reconsidered"] += 1
            depends = [res["task_id"]]
        _save(queue, rip)
    decisions = _propagate(system, queue, rip, seed, hop=1, received=mag, depends_on=depends, now=now)
    _refresh(system, queue, rid, now=now)
    final = _ripple_row(queue, rid) or rip
    return {"ripple_id": rid, "opened": True, "magnitude": mag, "decisions": decisions,
            "reconsider_task_ids": [t["task_id"] for t in queue.tasks(ripple_id=rid, kind=("ripple.reconsider",))],
            "left_out": final["left_out"]}


def settle_reconsideration(
    system: Any, task_id: str, *,
    holder: str,
    outcome: str,
    change: Optional[str] = None,
    cosine_distance: Optional[float] = None,
    result: Optional[Mapping[str, Any]] = None,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """Settle one `ripple.reconsider` task. `outcome="unchanged"`: the reader kept the reading; the task is acked,
    nothing is written, the ripple stops there. `outcome="rewritten"`: the host already applied
    `rewrite_digest(..., cause={"cause": "ripple", ...}, task_id=task_id)` (which acked the task); `change` is the
    reader's enum and `cosine_distance` (default: the one the rewrite measured) scales it. The memory's onward
    impact, `min(received, measured)`, is handed one hop further. Returns {ripple_id, outcome, onward, decisions,
    status}."""
    queue = _queue(system)
    t = queue.task(task_id)
    if t is None or t["kind"] != "ripple.reconsider":
        raise ValueError(f"{task_id!r} is not a ripple.reconsider task")
    rid = str(t["ripple_id"])
    rip = _ripple_row(queue, rid)
    if rip is None:
        raise ValueError(f"unknown ripple {rid!r}")
    if outcome == "unchanged":
        acked = queue.ack(task_id, holder=holder, result={"outcome": "unchanged", **dict(result or {})}, now=now)
        if not acked["acked"] and acked.get("reason") != "already_done":
            return {"ripple_id": rid, "outcome": "refused", "reason": acked.get("reason"), "decisions": []}
        _gate_note(queue, rid, t, "settled", "unchanged: the reader kept its reading", now)
        status = _refresh(system, queue, rid, now=now)
        return {"ripple_id": rid, "outcome": "unchanged", "onward": 0.0, "decisions": [], "status": status}
    if outcome != "rewritten":
        raise ValueError("outcome must be 'unchanged' or 'rewritten'")
    current = queue.task(task_id)
    if current["status"] != "done":
        raise ValueError("a 'rewritten' settle follows the rewrite: pass task_id to rewrite_digest first")
    distance = cosine_distance
    if distance is None:
        distance = (current.get("result") or {}).get("cosine_distance")
    measured = gate.measured_change(str(change or "revised"), distance)
    onward = min(float(t["strength"]), measured)
    rip["changed"].append({"record_id": t["target_id"], "hop": t["hop"], "change": change or "revised",
                           "measured": round(measured, 6), "onward": round(onward, 6)})
    _save(queue, rip)
    _gate_note(queue, rid, t, "settled", f"rewritten ({change or 'revised'}), onward {onward:.4f}", now)
    decisions: List[Dict[str, Any]] = []
    source = _resolve(system, t["target_id"])
    if source is not None and onward > 0.0:
        decisions = _propagate(system, queue, rip, source, hop=int(t["hop"]) + 1, received=onward, now=now)
    status = _refresh(system, queue, rid, now=now)
    return {"ripple_id": rid, "outcome": "rewritten", "onward": onward, "decisions": decisions, "status": status}


def _gate_note(queue: MemoryTaskQueue, rid: str, t: Mapping[str, Any], decision: str, reason: str,
               now: Optional[str]) -> None:
    at = _iso(_utc(now))

    def write(cur: Any) -> None:
        cur.execute(f"INSERT INTO {queue.t_gates} (ripple_id, candidate_id, hop, via, potential, activation, decision, "
                    "reason, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (rid, t["target_id"], int(t["hop"] or 0), "settle", float(t["strength"]),
                     gate.logistic(float(t["strength"])), decision, reason, at))

    queue._txn(None, write)


def _refresh(system: Any, queue: MemoryTaskQueue, rid: str, *, now: Optional[str] = None) -> str:
    """Close the propagation when no reconsideration is live; enqueue the consolidation when two or more memories
    changed."""
    rip = _ripple_row(queue, rid)
    if rip is None or rip["status"] not in ("open",):
        return rip["status"] if rip else "unknown"
    live = queue.tasks(ripple_id=rid, kind=("ripple.reconsider",), status=("pending", "deferred", "leased"))
    if live:
        return "open"
    rip["settled_at"] = _iso(_utc(now))
    if len(rip["changed"]) >= 2:
        seed = _resolve(system, rip["seed_id"])
        queue.enqueue("ripple.consolidate", rip["seed_id"], scope=rip["scope"], owner_id=rip["owner_id"],
                      assertion_id=str(seed.assertion_id or "") if seed is not None else "", basis=rid,
                      strength=min(1.0, sum(float(c["measured"]) for c in rip["changed"])),
                      cause={"cause": "ripple", "ripple_id": rid, "seed_id": rip["seed_id"]},
                      ripple_id=rid, hop=None, now=now)
        rip["status"] = "consolidating"
    else:
        rip["status"] = "settled"
    _save(queue, rip)
    return rip["status"]


def refresh_ripples(system: Any, *, now: Optional[str] = None) -> List[Dict[str, str]]:
    """Close every open ripple whose reconsiderations are all settled, skipped, failed or superseded (and enqueue
    its consolidation when two or more memories changed). A host calls it when a window ends. Returns
    [{ripple_id, status}] for the ripples whose status moved."""
    queue = _queue(system)
    moved = []
    for (rid,) in queue._read(f"SELECT ripple_id FROM {queue.t_ripples} WHERE status = 'open' ORDER BY opened_at"):
        status = _refresh(system, queue, rid, now=now)
        if status != "open":
            moved.append({"ripple_id": rid, "status": status})
    return moved


def form_consolidation(
    system: Any, task_id: str, *,
    holder: str,
    text: str,
    title: str,
    author: Mapping[str, Any],
    reader: Optional[Mapping[str, Any]] = None,
    sources: Sequence[Mapping[str, Any]] = (),
    keywords: Sequence[str] = (),
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply a `ripple.consolidate` task: form the first-person "what this changes" record (kind summary,
    `summary_role: re-understanding`, `summarizes` edges to every changed memory, `derived_from` the seed; never
    batch-rewritten) and ack the task. The task must be leased by `holder` (consolidation tasks lease only in a
    `night` window). Returns {ripple_id, record_id, status}."""
    from .records import MemoryRecordInput
    from .understanding import _author, _reader, _sources, _understanding_attr, utc_now_iso

    queue = _queue(system)
    t = queue.task(task_id)
    if t is None or t["kind"] != "ripple.consolidate":
        raise ValueError(f"{task_id!r} is not a ripple.consolidate task")
    if t["status"] != "leased" or t["lease_holder"] != str(holder):
        raise ValueError("form_consolidation needs the task leased by its holder (a night window)")
    words, name = str(text or "").strip(), str(title or "").strip()
    if not words or not name:
        raise ValueError("a consolidation needs non-empty text and title (the engine never invents words)")
    author_d = _author(author)
    reader_d = _reader(reader, author_d["kind"])
    sources_t = _sources(sources, author_d["kind"])
    rid = str(t["ripple_id"])
    rip = _ripple_row(queue, rid)
    changed = [c["record_id"] for c in rip["changed"]]
    edges = tuple(("summarizes", c) for c in changed) + (("derived_from", rip["seed_id"]),)
    at = utc_now_iso()
    cause = {"cause": "ripple", "ripple_id": rid, "seed_id": rip["seed_id"]}
    record = MemoryRecordInput(
        kind="summary", title=name, digest=words, keywords=tuple(keywords), edges=edges,
        attributes={"summary_role": "re-understanding", "ripple_id": rid, "digest_method": CONSOLIDATION_METHOD,
                    "authored_by": author_d["id"] or author_d["kind"],
                    "understanding": _understanding_attr(0, "digest", author_d, reader_d, cause, sources_t,
                                                         (rip["seed_id"], *changed), at)},
        provenance={"source": "ripple-consolidation", "ripple_id": rid,
                    "actor": author_d["id"] or author_d["kind"]})
    [gid] = system.remember_many([record], scope=rip["scope"], owner_id=rip["owner_id"],
                                 idempotency_key=f"ripple-consolidation|{rid}")
    queue.ack(task_id, holder=holder, result={"outcome": "consolidated", "record_id": gid}, now=now)
    rip["status"] = "consolidated"
    rip["settled_at"] = rip.get("settled_at") or _iso(_utc(now))
    _save(queue, rip)
    return {"ripple_id": rid, "record_id": gid, "status": "consolidated"}


def revert_ripple(system: Any, ripple_id: str, *, by: Optional[Mapping[str, Any]] = None,
                  reason: Optional[str] = None) -> List[Dict[str, Any]]:
    """Restore, as new versions, the readings each changed memory held before this ripple rewrote it (only where
    the ripple's version is still the current one). Returns one revert result per changed memory."""
    from .understanding import revert_digest, versions

    queue = _queue(system)
    rip = _ripple_row(queue, ripple_id)
    if rip is None:
        raise ValueError(f"unknown ripple {ripple_id!r}")
    out = []
    for c in rip["changed"]:
        rows = versions(system, c["record_id"])
        current = next((v for v in rows if v["current"]), None)
        if current is None or (current.get("cause") or {}).get("ripple_id") != ripple_id:
            out.append({"record_id": c["record_id"], "outcome": "refused", "reason": "not_the_ripple_version"})
            continue
        out.append(revert_digest(system, c["record_id"], int(current["version"]) - 1,
                                 expected_version=int(current["version"]), by=by,
                                 reason=reason or f"revert ripple {ripple_id}"))
    return out


# --------------------------------------------------------------------------- reads


def ripples(system: Any, *, scope: Optional[str] = None, owner_id: Optional[str] = None,
            status: Optional[Sequence[str]] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Ripples, newest first: [{ripple_id, seed_id, scope, owner_id, cause, magnitude, surprise, status, budget,
    reconsidered, changed, left_out, opened_at, settled_at}]."""
    queue = _queue(system)
    where, params = [], []
    if scope is not None:
        where.append("scope = ?")
        params.append(str(scope).strip().lower())
    if owner_id is not None:
        where.append("owner_id = ?")
        params.append(str(owner_id))
    if status:
        vals = [status] if isinstance(status, str) else list(status)
        where.append(f"status IN ({', '.join('?' for _ in vals)})")
        params.extend(vals)
    sql = f"SELECT ripple_id FROM {queue.t_ripples}" + (f" WHERE {' AND '.join(where)}" if where else "")
    sql += " ORDER BY opened_at DESC, ripple_id"
    if int(limit) > 0:
        sql += f" LIMIT {int(limit)}"
    return [_ripple_row(queue, r[0]) for r in queue._read(sql, params)]


def ripple(system: Any, ripple_id: str) -> Dict[str, Any]:
    """One ripple with its members (tasks) and every gate decision, oldest first."""
    queue = _queue(system)
    row = _ripple_row(queue, ripple_id)
    if row is None:
        raise ValueError(f"unknown ripple {ripple_id!r}")
    row["members"] = queue.tasks(ripple_id=ripple_id)
    row["gates"] = [{"candidate_id": g["candidate_id"], "hop": int(g["hop"]), "via": g["via"],
                     "potential": float(g["potential"]), "activation": float(g["activation"]),
                     "decision": g["decision"], "reason": g["reason"], "at": g["at"]}
                    for g in queue._read(f"SELECT * FROM {queue.t_gates} WHERE ripple_id = ? ORDER BY seq",
                                         (ripple_id,))]
    return row


def ripple_context(system: Any, task: Mapping[str, Any]) -> Dict[str, Any]:
    """What a reader needs to reconsider one memory in a ripple (task_packet's `ripple`): the ripple's cause and
    surprise words, the seed's current reading and the reading it replaced, how this memory was reached (from, via,
    hop, the impact it received) and, for a consolidation, every change with its before and after."""
    from .understanding import record_understanding, versions

    queue = _queue(system)
    rip = _ripple_row(queue, str(task["ripple_id"]))
    if rip is None:
        return {"ripple_id": task["ripple_id"], "state": "unknown"}

    def before_after(rid: str) -> Dict[str, Any]:
        rows = versions(system, rid)
        current = next((v for v in rows if v["current"]), None)
        prior = next((v for v in reversed(rows) if current and v["version"] == current["version"] - 1), None)
        return {"record_id": rid, "now": record_understanding(system, rid)["digest"],
                "before": prior["text"] if prior else None}

    out = {"ripple_id": rip["ripple_id"], "cause": rip["cause"], "surprise": rip["surprise"],
           "magnitude": rip["magnitude"], "seed": before_after(rip["seed_id"]),
           "reached": {k: (task.get("cause") or {}).get(k) for k in ("from", "via", "hops")},
           "received": float(task.get("strength") or 0.0)}
    if task.get("kind") == "ripple.consolidate":
        out["changed"] = [dict(c, **before_after(c["record_id"])) for c in rip["changed"]]
    return out
