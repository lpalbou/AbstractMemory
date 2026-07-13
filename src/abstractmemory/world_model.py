"""World-model orientation cards (backlog 0033) — knowledge refined over time.

THE MAINTAINER'S MODEL (2026-07-12): "the world model cards are extremely
important as they represent the long-term understanding of people, object,
location, time, problems, ideas, concepts. that's the knowledge refined
over time." This is the SITUATION component's "profile recall" leg: the
gradation system gives the instant expectation of a target, participants
give shared context — the CARD holds the refined understanding, so a
returning visitor surfaces ONE compact orientation instead of N raw
episodes competing for shelf seats.

FORK LINEAGE (memory_control.rs world-model lane + ADR 0019, read
2026-07-12): source-linked (derived_from edges to the evidence),
revision-chained (refines edge to the previous revision; append-only —
"revision_policy: append_only_new_world_model_node"), maintenance-formed
only, indexed+inactive bindings ("indexed for grounding, not
prompt-pinned"), ORIENTATION NEVER AUTHORITY. Our port keeps every guard
and adds the closure fold: a superseded revision leaves recall through
the normal current-wins mechanism instead of a revision-number sort.

MECHANICS (deterministic, zero LLM — the digest is mechanical-v1 and says
so; entity-authored re-digestion is the waking lane, like every mechanical
digest):
- TARGETS are the gradation universe, extracted from lived records:
  participants (person:/entity:/... — except the scope owner: the
  explicit co-presence self-stamp is universal and a card about oneself
  is identity's lane, not orientation's) and topic strings (namespaced
  "topic:<t>"). Free strings, never an enum.
- EVIDENCE is lived records only: dreams, world_model cards, maintenance
  candidates, and bookkeeping rows never evidence a card (derived
  artifacts must not feed derived artifacts — the dream-pass loop-breaker
  applied here; ALSO the disposal rule's spirit: dream-only support can
  never source an orientation).
- A card forms when a target clears the evidence floor; it REVISES
  (revision N+1, refines → previous, previous closed kind="supersede"
  with the new card as replacement) when the evidence set CHANGED;
  identical evidence re-runs are no-ops (fingerprint idempotency).
- Cards carry attributes.participants=[target] for participant targets:
  the EXISTING participants channel surfaces the card exactly when that
  person is present — orientation arrives with the encounter, no new
  recall machinery.

THE D2 OF SLEEP HOLDS: forming/revising cards deposits nothing (formation
is not use; closures are belief revision).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .records import MemoryRecordInput, record_id_for
from .sleep_policy import DEFAULT_SLEEP_TUNING, SleepTuning
from .store import TripleQuery

__all__ = ["current_world_models", "standing_world_models", "world_model_pass"]

# Derived/bookkeeping kinds that never evidence a card (loop-breaker).
_NON_EVIDENCE_KINDS = frozenset({"dream", "world_model"})


def _evidence_scan(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
) -> Dict[str, Dict[str, Any]]:
    """Lived records eligible as card evidence: graph id -> facts.
    Closure-folded AND hidden-folded (a retracted or hidden episode stops
    evidencing cards — one belief-state read, same rule as
    unresolved_dreams) and derived-artifact-excluded."""
    from .folds import binding_states, closure_exclusions

    as_of = journal.current_seq()
    closed = set(closure_exclusions(journal, as_of))
    for scope, owner in scopes:
        _states, hidden, _active = binding_states(store, journal, [(scope, owner)], as_of)
        closed |= set(hidden)
    out: Dict[str, Dict[str, Any]] = {}
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            kind = attrs.get("record_kind")
            if (not kind or kind in _NON_EVIDENCE_KINDS
                    or attrs.get("bookkeeping") or attrs.get("record_edge")
                    or attrs.get("maintenance_candidate")):
                continue
            if a.assertion_id in closed or a.subject in closed:
                continue
            out[a.subject] = {
                "record_id": a.subject,
                "kind": str(kind),
                "title": str(attrs.get("title") or "").strip(),
                "observed_at": str(a.observed_at or ""),
                "keywords": [str(k) for k in (attrs.get("keywords") or ())],
                "participants": [str(p) for p in (attrs.get("participants") or ())],
                "topic": str(attrs.get("topic") or "").strip(),
            }
    return out


def _targets_of(record: Dict[str, Any], owner_id: str) -> List[str]:
    """The card targets one lived record contributes to."""
    targets = [p for p in record["participants"] if p and p != owner_id]
    if record["topic"]:
        targets.append(f"topic:{record['topic']}")
    return targets


def _revision_of(assertion: Any) -> int:
    """Tolerant revision read: malformed values sort as 0, never crash
    (a card is data; a bad attribute is a formation bug to surface via
    the standing-duplicates repair, not a traceback in a read)."""
    raw = (assertion.attributes or {}).get("revision")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def standing_world_models(
    store: Any, *, scope: str, owner_id: str, journal: Any = None,
) -> Dict[str, List[Any]]:
    """target -> ALL standing (closure-folded) card assertions, revision
    ascending. More than one standing card per target means an
    interrupted revision (the supersede closure never landed) —
    world_model_pass repairs it."""
    rows = [a for a in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0))
            if isinstance(a.attributes, dict)
            and a.attributes.get("record_kind") == "world_model"]
    if journal is not None:
        from .folds import closure_exclusions

        closed = closure_exclusions(journal, journal.current_seq())
        rows = [a for a in rows
                if a.assertion_id not in closed and a.subject not in closed]
    by_target: Dict[str, List[Any]] = {}
    for a in sorted(rows, key=lambda r: (_revision_of(r),
                                         str(r.observed_at or ""), str(r.subject))):
        target = str((a.attributes or {}).get("target") or "").strip()
        if target:
            by_target.setdefault(target, []).append(a)
    return by_target


def current_world_models(
    store: Any, *, scope: str, owner_id: str, journal: Any = None,
) -> Dict[str, Any]:
    """target -> the CURRENT (closure-folded, highest-revision) card.
    journal=None is the layer-1 read (no fold)."""
    return {target: rows[-1]
            for target, rows in standing_world_models(
                store, scope=scope, owner_id=owner_id, journal=journal).items()}


def world_model_pass(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
    report_only: bool = False,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
) -> Dict[str, Any]:
    """Form/revise orientation cards for the targets the evidence supports.

    Deterministic and idempotent: same home state → same cards; a re-run
    forms nothing new (evidence fingerprints). Cards land in the FIRST
    scope pair (the home scope) under owner_id — same convention as the
    dream. Returns a self-describing result with per-target verdicts."""
    owner = str(owner_id or "").strip()
    if not owner:
        raise ValueError(
            "world_model_pass requires a non-empty owner_id — the owner "
            "exclusion (no card about oneself; the self-stamp never counts) "
            "is meaningless against a blank owner")
    store, journal = system.store, system.journal
    evidence = _evidence_scan(store, journal, scopes=scopes)

    # Group evidence by target, deterministically.
    by_target: Dict[str, List[str]] = {}
    for gid in sorted(evidence):
        for target in _targets_of(evidence[gid], owner):
            by_target.setdefault(target, []).append(gid)

    floor = int(tuning.world_model_evidence_floor)
    eligible = {t: ids for t, ids in by_target.items() if len(ids) >= floor}
    standing = standing_world_models(store, scope=scopes[0][0],
                                     owner_id=scopes[0][1], journal=journal)

    out: Dict[str, Any] = {
        "pass_name": "world_model_pass",
        "targets_seen": len(by_target),
        "eligible": sorted(eligible),
        "formed": [],
        "unchanged": [],
        "skipped": [],
        "repaired": [],
    }

    # CRASH-REPLAY REPAIR (adversary P1-3): a crash between remember_many
    # (rev N+1 formed) and close_record(rev N) leaves TWO standing cards
    # for one target — the unchanged branch would then skip forever and
    # ranked recall would serve both. Repair on every pass: close every
    # standing card below the highest revision (closure ids are
    # deterministic, so re-closing is a journal no-op).
    for target, rows in sorted(standing.items()):
        for stale in rows[:-1]:
            if not report_only:
                system.close_record(
                    stale.subject, kind="supersede",
                    replacement_ids=[rows[-1].subject],
                    reason=f"world-model revision repair for {target} "
                           "(interrupted supersede)")
            out["repaired"].append({"target": target, "card_id": stale.subject,
                                    "closed": not report_only})

    current = {target: rows[-1] for target, rows in standing.items()}

    # Busiest understandings first; bounded per night. The unchanged
    # check runs BEFORE the budget (adversary P2: an unchanged target
    # must never be misreported as budget-skipped, and it spends none).
    ranked = sorted(eligible.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    budget = max(0, int(tuning.world_model_max_cards))
    for target, source_ids in ranked:
        fingerprint = hashlib.sha256(
            "|".join(sorted(source_ids)).encode("utf-8")).hexdigest()
        prior = current.get(target)
        prior_attrs = (prior.attributes if prior is not None
                       and isinstance(prior.attributes, dict) else {})
        if prior is not None and prior_attrs.get("evidence_fingerprint") == fingerprint:
            out["unchanged"].append({"target": target, "card_id": prior.subject})
            continue
        if budget <= 0:
            out["skipped"].append({"target": target, "reason": "max_cards reached"})
            continue
        revision = _revision_of(prior) + 1 if prior is not None else 1

        rows = [evidence[gid] for gid in source_ids]
        rows.sort(key=lambda r: (r["observed_at"], r["record_id"]))
        first_seen = rows[0]["observed_at"]
        last_seen = rows[-1]["observed_at"]
        facet_counts: Dict[str, int] = {}
        for r in rows:
            for kw in r["keywords"]:
                facet_counts[kw] = facet_counts.get(kw, 0) + 1
        top_facets = [f for f, _ in sorted(
            facet_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[: tuning.world_model_top_facets]]
        kind_counts: Dict[str, int] = {}
        for r in rows:
            kind_counts[r["kind"]] = kind_counts.get(r["kind"], 0) + 1
        kinds_line = ", ".join(f"{n} {k}" for k, n in sorted(
            kind_counts.items(), key=lambda kv: (-kv[1], kv[0])))

        display = target.split(":", 1)[1] if ":" in target else target
        themes = f" Recurring themes: {', '.join(top_facets)}." if top_facets else ""
        digest = (
            f"Refined understanding of {display}, distilled from "
            f"{len(rows)} lived record(s) between {first_seen[:10]} and "
            f"{last_seen[:10]} ({kinds_line}).{themes} This card is "
            "orientation, never authority: the sources remain the "
            "evidence, and a live encounter always overrides it."
        )
        newest_first = [r["record_id"] for r in reversed(rows)]
        edges: List[Tuple[str, str]] = [
            ("derived_from", rid)
            for rid in newest_first[: tuning.world_model_max_sources]
        ]
        if prior is not None:
            edges.append(("refines", prior.subject))
        card = MemoryRecordInput(
            kind="world_model",
            title=f"World model: {display}",
            digest=digest,
            keywords=tuple(top_facets),
            participants=(target,) if not target.startswith("topic:") else (),
            edges=tuple(edges),
            attributes={
                "world_model": True,
                "target": target,
                "revision": revision,
                "evidence_fingerprint": fingerprint,
                "source_count": len(rows),
                "first_seen": first_seen,
                "last_seen": last_seen,
                # Mechanical digest awaiting entity-authored re-digestion —
                # the same flag the driver uses for episode digests.
                "digest_method": "mechanical-v1",
            },
        )
        verdict = {"target": target, "revision": revision,
                   "source_count": len(rows), "formed": not report_only}
        if not report_only:
            key = f"world-model|{owner}|{target}|{fingerprint}"
            expected = record_id_for("world_model", key, 0)
            existed = bool(store.query(TripleQuery(subject=expected, limit=1)))
            [gid] = system.remember_many(
                [card], scope=scopes[0][0], owner_id=owner, idempotency_key=key)
            verdict["card_id"] = gid
            verdict["formed"] = not existed
            if prior is not None and prior.subject != gid:
                # Append-only revision: the old card leaves recall through
                # the normal closure fold; its history stays. Close
                # UNCONDITIONALLY (not just when the new card is fresh —
                # adversary P1-3): closure ids are deterministic, so a
                # replay after a crash between form and close re-lands
                # the close as a journal no-op instead of never.
                system.close_record(
                    prior.subject, kind="supersede", replacement_ids=[gid],
                    reason=f"world-model revision {revision} for {target} "
                           "(evidence changed)")
        out["formed"].append(verdict)
        budget -= 1

    out["formed_count"] = sum(1 for v in out["formed"] if v.get("formed"))
    return out
