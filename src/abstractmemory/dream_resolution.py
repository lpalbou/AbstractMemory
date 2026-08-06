"""Passive dream resolution — the day answers the night (backlog 0032).

THE MAINTAINER'S MODEL (2026-07-12, verbatim intent): a dream is a PENDING
QUESTION the entity does not consciously know it holds. "During the live
experience of the entity, it may come across clues, information, anything
that might suddenly answer that pending question" — I dream I don't know
how to finish the project; during the day I finish it (a SOFT resolution).
Or the dream RESURFACES when its trigger appears (I meet the person). It
is MOSTLY A PASSIVE PROCESS; deliberate review (disposal.py) stays the
rare, explicit path.

THIS PASS runs at the sleep boundary — the night reviews the day — and
closes standing dreams whose tension the day's lived experience already
answered. It is STRUCTURAL, deterministic, and evidence-post-dating: it
never guesses semantics, never calls an LLM, and never mutates sources.
"When in doubt, leave the dream standing — a false resolution erases a
real tension silently" (the 0032 guidance line).

THE EVIDENCE IS EVIDENCE-GRADE (adversary P0-1/P0-2): the pass reads the
structural report with `evidence_grade=True` — closures FOLDED (a story
the day retracted must not keep joining islands; a closed endpoint means
the tension STANDS) and maintenance candidates EXCLUDED (sleep's own
summaries carry summarizes edges that merge components; "waking evidence
disposes" can never mean sleep's own artifact). The dream pass keeps its
deliberately RAW view; only resolution needs belief-state truth.

RESOLUTION MECHANISMS (each names itself in the result):
- bridge proposals resolve when the proposed pair is NO LONGER separate:
  same component under authored LIVED relations (someone wrote the story
  that joins the islands), or a STRONG co_selected trail now joins it —
  co-use across at least `resolution_trail_min_traces` DISTINCT traces
  (one co-display in one prompt is co-appearance, not lived association;
  the dream's own resurfacing keywords co-surface its endpoints, so a
  single-event trail would let the dream resolve itself — adversary
  P1-5). Both signals are inherently post-dream: at dream time the pair
  was cross-component and trail-cold by construction.
- facet questions ("does 'X' connect these, or is it lexical residue?")
  resolve when a NEW record — formed AFTER the dream — carries the
  questioned facet AND touches an endpoint (shared participant, authored
  edge, or mechanical co-presence). The question found its subject in
  lived experience.
- continuation dreams (re-lights of standing tension) resolve when every
  parent dream they re-light has left the standing set.

A dream resolves when AT LEAST the tuned fraction of its tensions
(proposals + questions) resolved individually — default 1.0: ALL of them
(conservative by the 0032 guidance). Soft resolution writes ONE
append-only act: close_record(kind="supersede") with the resolving
records as replacements and a reason naming the mechanism — the dream was
not wrong, life absorbed it; its history stays in the journal.

AS_OF ANCHORS AUDIT READS ONLY (adversary P1-4, the consolidation_pass
rule): writing closures against a historical anchor would mix time
frames; report_only=True is required with as_of.

THE D2 OF SLEEP HOLDS: this pass deposits nothing (closures are belief
revision, not usage; access counts never move — guard-tested).

RESURFACING needs no machinery here: dreams now form with keywords/
participants drawn from their own tension vocabulary (consolidation.py),
so normal recall channels surface a dream exactly when its trigger
appears. Influence = admission, never a push.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .consolidation import structural_report
from .sleep_policy import DEFAULT_SLEEP_TUNING, SleepTuning
from .store import TripleQuery

__all__ = ["resolve_dreams_pass"]


def _formation_seq(journal: Any, graph_id: str) -> Optional[int]:
    """The journal seq at which a record was FORMED (its earliest
    source="remember" binding). None when the journal never saw it —
    works-or-loud at the caller (an unformed dream cannot be resolved)."""
    rows = [b for b in journal.bindings(record_id=graph_id, fold=False)
            if b.source == "remember"]
    if not rows:
        return None
    return min(int(b.seq) for b in rows)


def _new_records_since(
    journal: Any, *, scopes: Sequence[Tuple[str, str]], after_seq: int,
    known: Set[str],
) -> Set[str]:
    """Graph ids of records FORMED after a seq (the lived day), restricted
    to records the structural report knows (dreams and bookkeeping rows
    are excluded there — a dream can never evidence another dream)."""
    fresh: Set[str] = set()
    for scope, owner in scopes:
        for b in journal.bindings(scope=scope, owner_id=owner, fold=False):
            if (b.source == "remember" and int(b.seq) > int(after_seq)
                    and b.record_id in known):
                fresh.add(b.record_id)
    return fresh


def _endpoint_touch(
    new_id: str, endpoint: str, *, records: Dict[str, Dict[str, Any]],
    adjacency: Dict[str, List[str]], context_pairs: Set[Tuple[str, str]],
) -> bool:
    """Does a new record TOUCH a dream endpoint? Shared participant,
    authored (component) edge, or mechanical co-presence — the structural
    reads of 'the question found its subject'."""
    a, b = records.get(new_id), records.get(endpoint)
    if a is None or b is None:
        return False
    if set(a.get("participants") or ()) & set(b.get("participants") or ()):
        return True
    if endpoint in (adjacency.get(new_id) or ()):
        return True
    return tuple(sorted((new_id, endpoint))) in context_pairs


def resolve_dreams_pass(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
    report_only: bool = False, as_of: Optional[int] = None,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
) -> Dict[str, Any]:
    """Examine every standing unresolved dream against the day's lived
    experience; softly close the ones life already answered.

    Pure read + append-only closures (report_only=True writes nothing).
    Deterministic: same home state → same verdicts. Returns a
    self-describing result: per-dream verdicts with the mechanism and
    evidence ids, so the operator (and the entity's future explainability
    reads) can see WHY a tension closed."""
    from .consolidation import unresolved_dreams

    if as_of is not None and not report_only:
        raise ValueError(
            "resolve_dreams_pass: as_of anchors AUDIT reads only — closures "
            "against a historical anchor mix time frames; pass "
            "report_only=True for anchored reads")
    store, journal = system.store, system.journal
    report = structural_report(store, journal, scopes=scopes, as_of=as_of,
                               evidence_grade=True)
    records: Dict[str, Dict[str, Any]] = report["records"]
    component_of: Dict[str, int] = report["component_of"]
    adjacency: Dict[str, List[str]] = report["adjacency"]
    context_pairs: Set[Tuple[str, str]] = {tuple(p) for p in report.get("context_pairs", ())}

    # STRONG trails only (P1-5): the report's trail_pairs admits any single
    # co_selected event ever; lived association needs co-use across
    # distinct traces. Count distinct trace ids per canonical pair.
    hi = int(as_of) if as_of is not None else journal.current_seq()
    assertion_to_record: Dict[str, str] = {}
    for gid, info in records.items():
        if info.get("assertion_id"):
            assertion_to_record[info["assertion_id"]] = gid
    pair_traces: Dict[Tuple[str, str], Set[str]] = {}
    for scope, owner in scopes:
        for e in journal.events(scope=scope, owner_id=owner,
                                kinds=["co_selected"], until_seq=hi, limit=0):
            if not e.pair_ids or len(e.pair_ids) != 2:
                continue
            a_rec = assertion_to_record.get(e.pair_ids[0])
            b_rec = assertion_to_record.get(e.pair_ids[1])
            if a_rec and b_rec and a_rec != b_rec:
                key = tuple(sorted((a_rec, b_rec)))
                pair_traces.setdefault(key, set()).add(str(e.trace_id or e.event_id))
    floor = max(1, int(tuning.resolution_trail_min_traces))
    trail_pairs: Set[Tuple[str, str]] = {
        pair for pair, traces in pair_traces.items() if len(traces) >= floor}

    standing = unresolved_dreams(
        store, scope=scopes[0][0], owner_id=scopes[0][1], journal=journal)
    standing_ids = {a.subject for a in standing}

    out: Dict[str, Any] = {
        "pass_name": "resolve_dreams_pass",
        "examined": len(standing),
        "resolved": [],
        "standing": [],
        "as_of_seq": report["as_of_seq"],
    }

    # Oldest first (unresolved_dreams orders so): a continuation dream's
    # parents are examined before it, so chain resolution settles in ONE
    # pass when the whole lineage closed.
    resolved_this_pass: Set[str] = set()
    for dream in standing:
        gid = dream.subject
        attrs = dream.attributes if isinstance(dream.attributes, dict) else {}
        proposals = [e for e in (attrs.get("proposals") or ()) if isinstance(e, dict)]
        questions = [e for e in (attrs.get("questions") or ()) if isinstance(e, dict)]
        parents = [str(p) for p in (attrs.get("parent_dream_ids") or ()) if str(p or "").strip()]
        born_at = _formation_seq(journal, gid)
        if born_at is None:
            out["standing"].append({"dream_id": gid, "reason": "no formation seq in journal"})
            continue
        fresh = _new_records_since(
            journal, scopes=scopes, after_seq=born_at, known=set(records))

        tensions = 0
        settled = 0
        evidence: List[str] = []
        mechanisms: List[str] = []

        for entry in proposals:
            pair = entry.get("pair") or ()
            if len(pair) != 2:
                continue
            left, right = str(pair[0]), str(pair[1])
            tensions += 1
            if left not in component_of or right not in component_of:
                # An endpoint left the EVIDENCE-GRADE substrate (closed/
                # hidden since the dream) — the tension stands: absence
                # of a party is not evidence about the connection. Real
                # now that the report folds closures (P0-2).
                continue
            canonical = tuple(sorted((left, right)))
            if component_of[left] == component_of[right]:
                settled += 1
                mechanisms.append("joined_by_authored_story")
                evidence.extend([left, right])
            elif canonical in trail_pairs:
                settled += 1
                mechanisms.append("associated_by_lived_use")
                evidence.extend([left, right])

        for entry in questions:
            pair = entry.get("pair") or ()
            facet = str(entry.get("facet") or "").strip()
            if len(pair) != 2 or not facet:
                continue
            left, right = str(pair[0]), str(pair[1])
            tensions += 1
            canonical = tuple(sorted((left, right)))
            if (left in component_of and right in component_of
                    and (component_of[left] == component_of[right]
                         or canonical in trail_pairs)):
                settled += 1
                mechanisms.append("questioned_pair_now_associated")
                evidence.extend([left, right])
                continue
            answered_by = next(
                (nid for nid in sorted(fresh)
                 if facet in set(records[nid].get("facets") or ())
                 and (_endpoint_touch(nid, left, records=records,
                                      adjacency=adjacency, context_pairs=context_pairs)
                      or _endpoint_touch(nid, right, records=records,
                                         adjacency=adjacency, context_pairs=context_pairs))),
                None,
            )
            if answered_by is not None:
                settled += 1
                mechanisms.append("facet_found_its_subject_in_experience")
                evidence.append(answered_by)

        # Continuation dreams re-light their parents' tension: with no own
        # tensions, they resolve when the whole re-lit lineage has left the
        # standing set (closed earlier, or resolved THIS pass).
        if tensions == 0 and parents:
            tensions = len(parents)
            settled = sum(
                1 for p in parents
                if p not in standing_ids or p in resolved_this_pass)
            if settled == tensions:
                mechanisms.append("relit_tension_settled")
                evidence.extend(parents)

        if tensions == 0:
            out["standing"].append({"dream_id": gid, "reason": "no examinable tensions"})
            continue
        fraction = settled / tensions
        if fraction < float(tuning.resolution_fraction):
            out["standing"].append({
                "dream_id": gid,
                "reason": f"{settled}/{tensions} tensions settled "
                          f"(< {tuning.resolution_fraction:g} required)",
            })
            continue

        # Soft resolution: ONE append-only act; the dream leaves the
        # standing set through the normal closure fold, history intact.
        ordered_evidence = list(dict.fromkeys(evidence))[: tuning.resolution_evidence_bound]
        verdict = {
            "dream_id": gid,
            "mechanisms": sorted(set(mechanisms)),
            "evidence_ids": ordered_evidence,
            "settled": settled,
            "tensions": tensions,
        }
        if not report_only:
            system.close_record(
                gid, kind="supersede", replacement_ids=ordered_evidence,
                reason=("resolved_by_experience: " + ", ".join(sorted(set(mechanisms)))
                        + f" ({settled}/{tensions} tensions settled by the day)"),
            )
            resolved_this_pass.add(gid)
        verdict["closed"] = not report_only
        out["resolved"].append(verdict)

    out["resolved_count"] = sum(1 for v in out["resolved"] if v["closed"])
    return out
