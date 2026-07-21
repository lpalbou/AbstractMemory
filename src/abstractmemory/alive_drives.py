"""Alive drives: the day-cue read — drives as DRIVERS of cognition
(laurent dm#82 via room c224, 2026-07-20).

"It's not that existing questions, interests or problems or commitments
forbid idle; it's that they are the DRIVERS of cognition and existence...
this must be fluid and organic, unprompted, happening naturally because
of the evolving memory states."

drive_pressure() answers "how much stands?" (counts, the gate's
currency). THIS read answers "what is ALIVE right now?" (ranked items,
the cue's currency): the standing drive sets joined with the engine's
own aliveness signals —

- TRAIL-ALIVE: the drive carries stored activation (it was selected,
  co-selected, or spread-reached recently — he has been circling it).
- RECENCY-ALIVE: the drive's formation/last-belief event falls inside
  the CURRENT attention window (formation is itself an evolving-memory
  event — a question elected yesterday counts before any trail forms).

Aliveness = max(activation-derived, recency-derived), both resolved
against the attention machinery's EXISTING declared dials
(AttentionConfig window/decay — one physics, no second set). A drive
that is neither is DORMANT and never returns: an empty result IS the
quiet desk, emergently ("thirty dormant questions do not make a day"),
and quiet desk -> sleep needs no new threshold.

CONTRACT: pure read, deposits nothing — and the cue composed from it
must never deposit either (presence != use; the driver excludes cue
handles from commit_selection exactly as self/stm admissions are
excluded — a depositing cue would breed tomorrow's list from this
morning's, the bridge-attractor twin). Machine rows never become OR
discharge drives (the drive_pressure folds carry that law here).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .consolidation import unresolved_dreams
from .diary import open_commitments, open_ideas, open_problems, open_questions
from .store import TripleQuery

__all__ = ["alive_drives"]

# The drive families the read serves, in stable presentation order.
_DRIVE_LABELS = {
    "question": "open question",
    "problem": "open problem",
    "commitment": "open commitment",
    "idea": "incubating idea",
    "interest": "unexplored interest",
    "dream": "unresolved tension",
}


def _origin_of(assertion: Any) -> str:
    prov = assertion.provenance if isinstance(assertion.provenance, dict) else {}
    return str(prov.get("source") or "").strip()


def alive_drives(
    system: Any, *, scopes: Sequence[Tuple[str, str]], k: int = 5,
) -> List[Dict[str, Any]]:
    """Top-k alive drives as handle-shaped items, strongest first:

        {record_id, kind, drive ("open question"|...), title, digest,
         born_at, origin, aliveness, alive_via ("trail"|"recency"|"both")}

    k is the cue-dilution cap (the room's 3-5 band; the caller renders
    the [kind #tag date - origin] line — tag rendering is the HOST's,
    per the recent_records convention). Deterministic; pure read.
    """
    store, journal = system.store, system.journal
    pairs: List[Tuple[str, str]] = []
    seen = set()
    for s, o in (scopes or ()):
        pair = (str(s or "").strip().lower(), str(o or "").strip())
        if pair[0] and pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    if not pairs:
        raise ValueError("alive_drives requires at least one (scope, owner_id) pair")

    # 1. The standing drive sets — the SAME post-adversary folds
    # drive_pressure uses (believed rows both sides, parked interests
    # excluded, machine rows inert). Each entry: (assertion, drive label).
    standing: List[Tuple[Any, str]] = []
    for scope, owner in pairs:
        for a in open_questions(store, scope=scope, owner_id=owner, journal=journal, limit=0):
            standing.append((a, _DRIVE_LABELS["question"]))
        for a in open_problems(store, scope=scope, owner_id=owner, journal=journal, limit=0):
            standing.append((a, _DRIVE_LABELS["problem"]))
        for a in open_commitments(store, scope=scope, owner_id=owner, journal=journal, limit=0):
            standing.append((a, _DRIVE_LABELS["commitment"]))
        for a in open_ideas(store, scope=scope, owner_id=owner, journal=journal, limit=0):
            standing.append((a, _DRIVE_LABELS["idea"]))
        for a in unresolved_dreams(store, scope=scope, owner_id=owner, journal=journal, limit=0):
            standing.append((a, _DRIVE_LABELS["dream"]))

    # Unexplored interests via the ONE shared fold (drive_pressure's) —
    # the gate's count and the cue's items can never diverge on what
    # counts as an open interest.
    from .drive_pressure import unexplored_interests

    for a in unexplored_interests(store, journal, pairs):
        standing.append((a, _DRIVE_LABELS["interest"]))

    if not standing:
        return []

    # 2. TRAIL aliveness: stored activation per drive record, per pair
    # (the facade read; every id was just resolved from the store, so the
    # unknown-id raise path is unreachable — NO exception guard here by
    # the silent-fallback law: a broken journal must raise loudly, never
    # read as a quiet desk; fable5 finding 1). Normalization is per-call:
    # `aliveness` is WITHIN-READ ordering currency only (finding 6) — a
    # host must never render it as a cross-day meter.
    activation: Dict[str, float] = {}
    by_pair: Dict[Tuple[str, str], List[str]] = {}
    for a, _label in standing:
        by_pair.setdefault((a.scope, str(a.owner_id or "")), []).append(a.subject)
    for (scope, owner), ids in by_pair.items():
        scores = system.activation(ids, scope=scope, owner_id=owner)
        for rid, s in scores.items():
            activation[rid] = max(activation.get(rid, 0.0), float(s.get("total") or 0.0))
    max_act = max(activation.values(), default=0.0)

    # 3. RECENCY aliveness on the BINDING axis: formation and every
    # belief change write bindings (a newborn drive has a binding before
    # any usage event exists — "formation is itself an evolving-memory
    # event"). A drive whose NEWEST binding falls within the newest
    # window_limit bindings of its pair is recency-alive, scored with the
    # same 1/(1+d/decay) shape activation uses over rank distance —
    # activity-relative (busy periods age drives faster), no wall clock,
    # no second physics: window and decay are AttentionConfig's dials.
    config = getattr(system, "_attention_config", None)
    window_limit = int(getattr(config, "drive_window_limit", 256) or 256)
    decay = float(getattr(config, "decay_window", 20.0) or 20.0)
    # ONE axis across the whole ladder (the journal's seq is global): a
    # drive formed in a quiet scope while the life roared elsewhere IS
    # dormant — per-pair windows would keep a lone diary question alive
    # forever against a busy life, which is the opposite of
    # activity-relative. The window is the BINDING-axis dial
    # (drive_window_limit — bindings run ~20-100x sparser than events;
    # fable5 finding 3), and it counts DISTINCT HIS-RECORDS: dedup runs
    # BEFORE the slice and machine rows (maintenance candidates,
    # bookkeeping) never occupy slots (finding 2 — machine formation
    # bursts must not age his drives; the occupancy twin of "machine
    # rows never become or discharge drives").
    machine_subjects: set = set()
    for scope, owner in pairs:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None,
                                         predicate="dcterms:abstract", limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("maintenance_candidate") or attrs.get("bookkeeping"):
                machine_subjects.add(a.subject)
    merged: List[Any] = []
    for scope, owner in pairs:
        merged.extend(journal.bindings(scope=scope, owner_id=owner, fold=False))
    merged.sort(key=lambda b: -int(b.seq))
    recency: Dict[str, float] = {}
    seen_rid: set = set()
    rank = 0
    for b in merged:  # newest binding per DISTINCT his-record ranks it
        rid = str(b.record_id or "")
        if not rid or rid in seen_rid or rid in machine_subjects:
            continue
        seen_rid.add(rid)
        if rank >= window_limit:
            break
        recency[rid] = 1.0 / (1.0 + rank / decay)
        rank += 1

    out: List[Dict[str, Any]] = []
    for a, label in standing:
        trail = (activation.get(a.subject, 0.0) / max_act) if max_act > 0 else 0.0
        recent = recency.get(a.subject, 0.0)
        aliveness = max(trail, recent)
        if aliveness <= 0.0:
            continue  # dormant: an empty result IS the quiet desk
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        out.append({
            "record_id": a.subject,
            "kind": str(attrs.get("record_kind") or ""),
            "drive": label,
            "title": str(attrs.get("title") or "").strip(),
            "digest": str(a.object or "")[:280],
            "born_at": str(a.observed_at or "")[:10] or None,
            "origin": _origin_of(a),
            "aliveness": round(aliveness, 4),
            "alive_via": ("both" if trail > 0 and recent > 0
                          else "trail" if trail > 0 else "recency"),
        })

    # GROUP FOLD (laurent room#277: "the more there are the higher the
    # signal they get to be treated"): the ONE partition over the FULL
    # open families (grouping adversary F1/F5 — grouping the small alive
    # subset let the scaffold screen go inert and FUSED five unrelated
    # templated questions into one fake entry, and standing dreams always
    # fused on the engine's own digest template). Only the three RULED
    # families group (question/problem/interest); dreams, commitments and
    # ideas surface ungrouped. Alive members of a cluster fold into ONE
    # entry — the strongest carries, boosted by the FULL open-cluster
    # size (the ruling counts tellings, not this morning's alive subset;
    # alive_members annotates the difference honestly — adversary F7).
    # Grouping never discharges (members stay standing; the entry NAMES
    # them).
    from .drive_grouping import GROUP_BOOST_STEP, open_drive_partition

    partition = open_drive_partition(store, journal, scopes=pairs)
    member_to_group: Dict[str, Dict[str, Any]] = {}
    group_family_of: Dict[str, str] = {}
    for family, groups in partition.items():
        for g in groups:
            for rid in g["members"]:
                member_to_group[rid] = g
                group_family_of[rid] = family

    folded: List[Dict[str, Any]] = []
    emitted_groups: set = set()
    for d in out:
        g = member_to_group.get(d["record_id"])
        if g is None:
            folded.append(d)
            continue
        gid = g["exemplar"]
        if gid in emitted_groups:
            continue  # the cluster already surfaced through its strongest member
        emitted_groups.add(gid)
        alive_members = [x for x in out if x["record_id"] in set(g["members"])]
        carrier = max(alive_members, key=lambda x: (x["aliveness"], x["record_id"]))
        # Uncapped (aliveness is WITHIN-READ ordering currency only, never
        # a meter — finding 6): capping at 1.0 made a fresh singleton TIE
        # a boosted 3-cluster, inverting the ruling.
        boosted = carrier["aliveness"] + GROUP_BOOST_STEP * (g["size"] - 1)
        entry = dict(carrier)
        entry["aliveness"] = round(boosted, 4)
        entry["group_size"] = g["size"]
        entry["group_members"] = g["members"]
        entry["group_alive_members"] = [x["record_id"] for x in alive_members]
        entry["group_shared_terms"] = g["shared_terms"]
        folded.append(entry)

    # SIZE IS ITSELF AN ALIVENESS SOURCE for offer-grade clusters
    # (runtime's 277 pathway ask 2: a fully-DORMANT 17-question cluster
    # could never surge — no alive member, no entry — capping "the more
    # there are the higher the signal" exactly where it matters most:
    # the oldest, most-neglected pressures the ratios indict). A cluster
    # >= GROUP_OFFER_FLOOR whose members are all dormant surfaces through
    # its exemplar with size-derived aliveness (the boost term alone).
    # This AMENDS the dormant-never-returns contract for grouped drives
    # BY the ruling: mass itself presses. Singletons and pairs keep the
    # emergent quiet-desk behavior unchanged.
    from .drive_grouping import GROUP_OFFER_FLOOR

    standing_by_id = {a.subject: (a, label) for a, label in standing}
    for family, groups in partition.items():
        for g in groups:
            if g["exemplar"] in emitted_groups or g["size"] < GROUP_OFFER_FLOOR:
                continue
            emitted_groups.add(g["exemplar"])
            anchor = standing_by_id.get(g["exemplar"])
            if anchor is None:
                continue
            a, label = anchor
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            folded.append({
                "record_id": a.subject,
                "kind": str(attrs.get("record_kind") or ""),
                "drive": label,
                "title": str(attrs.get("title") or "").strip(),
                "digest": str(a.object or "")[:280],
                "born_at": str(a.observed_at or "")[:10] or None,
                "origin": _origin_of(a),
                "aliveness": round(GROUP_BOOST_STEP * (g["size"] - 1), 4),
                "alive_via": "group_size",
                "group_size": g["size"],
                "group_members": g["members"],
                "group_alive_members": [],
                "group_shared_terms": g["shared_terms"],
            })
    folded.sort(key=lambda d: (-d["aliveness"], d["record_id"]))
    return folded[: max(0, int(k))]
