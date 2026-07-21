"""Cognition-health ratios: the drive bars (maintainer directive 2026-07-18).

"An entity should always remember at least some open questions and
interests as a drive to animate his next step. it's never 100% (otherwise
it just loops), but it is natural that sometimes, it explores some of
those." — the health surface needs two ratio bars:

- QUESTIONS: open vs resolved (the answers/resolves convention already
  carries this; the entity resolved his first question by his own
  election on 2026-07-17).
- INTERESTS: open vs EXPLORED — the missing half of the convention, added
  here: any later record carrying `attributes.explores=<interest graph id>`
  marks the interest explored (a work session that pursued it, a diary
  entry that developed it, an episode formed while investigating it).
  Same append-only family as answers/resolves/fulfills: exploring never
  closes the interest (an explored interest can be explored again — it is
  a DRIVE, not a task), it only moves the ratio.

This module is the compact read those bars render from. Pure read; folds
apply (a retracted question is not open, a hidden interest is not a
drive). Ratios are DATA — no surface should conclude "unhealthy" from a
number here; the never-100% property is the design, not a defect.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from .store import TripleQuery

__all__ = ["cognition_health"]


# The discharge-reference keys, UNIONED for every diary type — exactly the
# card compositor's map (entity_card builds ONE resolved_by from both).
# The reference ID does the targeting (it names which record it
# discharges); the attribute key is only the verb's flavor. Splitting by
# key (answers→questions, resolves→problems) made a question discharged
# with resolves= read RESOLVED on the card and OPEN on the drive bar —
# gateway's G1 adversary found the divergence live-reachable (runtime's
# teaching hands resolves= as a desk-moving key). One fold, one truth.
_REF_ATTRS = ("answers", "resolves")


def _diary_counts(
    store: Any, journal: Any, *, scope: str, owner_id: str,
    diary_type: str,
) -> Tuple[int, int]:
    """(open, resolved) for one diary_type under the answers/resolves
    convention — the SAME believed-rows fold entity_card uses (adversary
    finding 5: the first cut built resolved_refs from ALL rows while the
    card folds them from BELIEVED rows, so a retracted answer resolved
    here and stood open there; the bar and the card must never disagree,
    so both sides of the fold apply the exclusions) and the SAME unioned
    ref-attr set (gateway G1 finding, 2026-07-18: see _REF_ATTRS)."""
    rows = [a for a in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0))
            if isinstance(a.attributes, dict)
            and a.attributes.get("record_kind") == "diary"]
    excluded: set = set()
    if journal is not None:
        from .folds import binding_states, closure_exclusions

        as_of = journal.current_seq()
        _states, hidden, _active = binding_states(store, journal, [(scope, owner_id)], as_of)
        excluded = set(closure_exclusions(journal, as_of)) | set(hidden)

    believed = [a for a in rows
                if a.assertion_id not in excluded and a.subject not in excluded]
    resolved_refs: set = set()
    for a in believed:
        for ref_attr in _REF_ATTRS:
            ref = a.attributes.get(ref_attr)
            if isinstance(ref, str) and ref.strip():
                resolved_refs.add(ref.strip())

    open_n = resolved_n = 0
    for a in believed:
        attrs = a.attributes
        if attrs.get("diary_type") != diary_type:
            continue
        refs = {a.subject, str(attrs.get("entry_id") or "").strip()} - {""}
        if refs & resolved_refs:
            resolved_n += 1
        else:
            open_n += 1
    return open_n, resolved_n


def cognition_health(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
) -> Dict[str, Any]:
    """The drive ratios, one compact dict:

    {"questions": {"open", "resolved", "ratio"},
     "problems":  {"open", "repaired", "ratio"},
     "interests": {"open", "explored", "ratio"},
     "provenance": ...}

    ratio = resolved/(open+resolved) (or explored analog), None when the
    category is empty — an entity with no questions yet has NO ratio, not
    a perfect one (fabricated 100% on an empty life would read as done).
    Scope conventions: questions/problems live in the diary plane;
    interests live in SELF scope — the caller passes its ladder and each
    category folds over every pair (scope names are matched by the records
    themselves, so passing the full ladder is always safe).
    """
    # Normalize AND dedupe (adversary finding 9: a duplicated ladder pair
    # double-counted every category), order preserved.
    scope_pairs: List[Tuple[str, str]] = []
    seen_pairs: set = set()
    for s, o in (scopes or ()):
        pair = (str(s or "").strip().lower(), str(o or "").strip())
        if pair[0] and pair not in seen_pairs:
            seen_pairs.add(pair)
            scope_pairs.append(pair)
    if not scope_pairs:
        raise ValueError("cognition_health requires at least one (scope, owner_id) pair")

    q_open = q_resolved = p_open = p_repaired = 0
    for scope, owner in scope_pairs:
        o, r = _diary_counts(store, journal, scope=scope, owner_id=owner,
                             diary_type="question")
        q_open += o
        q_resolved += r
        o, r = _diary_counts(store, journal, scope=scope, owner_id=owner,
                             diary_type="problem")
        p_open += o
        p_repaired += r

    # Interests: standing kind=interest records (closure/hidden folds +
    # the card's lifecycle exclusion — a parked interest is not an open
    # drive; drive-pressure adversary finding 3, 2026-07-20), explored =
    # a BELIEVED record carries attributes.explores naming the interest
    # (either id namespace; believed-rows-only per finding 4 — a
    # retracted exploring episode must not keep the ratio moved).
    from .entity_card import _CLOSED_INTEREST_LIFECYCLES

    excluded: set = set()
    lifecycle_of: Dict[str, str] = {}
    if journal is not None:
        from .folds import binding_states, closure_exclusions

        as_of = journal.current_seq()
        excluded = set(closure_exclusions(journal, as_of))
        for scope, owner in scope_pairs:
            _states, hidden, _active = binding_states(store, journal, [(scope, owner)], as_of)
            excluded |= set(hidden)
            for b in journal.bindings(scope=scope, owner_id=owner, fold=True):
                lifecycle_of[b.record_id] = b.lifecycle

    interests: List[Any] = []
    explores_refs: set = set()
    # Standing review offers (W2): candidates awaiting his word — counted
    # for the health surface, NEVER in the drive ratios (correction 7:
    # born kind=summary + proposed_kind, structurally outside the folds; a
    # candidate is the night's offer, not his drive). lifecycle promoted/
    # rejected = reviewed, no longer pending.
    candidates_pending: Dict[str, int] = {}
    for scope, owner in scope_pairs:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None,
                                         predicate="dcterms:abstract", limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            believed = (a.assertion_id not in excluded
                        and a.subject not in excluded)
            if (attrs.get("record_kind") == "interest" and believed
                    and lifecycle_of.get(a.subject, "inactive_candidate")
                    not in _CLOSED_INTEREST_LIFECYCLES):
                interests.append(a)
            if (believed and attrs.get("maintenance_candidate")
                    and attrs.get("review_required")
                    and lifecycle_of.get(a.subject, "inactive_candidate")
                    not in ("promoted", "rejected")):
                label = str(attrs.get("proposed_kind") or "consolidation")
                candidates_pending[label] = candidates_pending.get(label, 0) + 1
            # Machine rows never discharge drives (wake-reason purity,
            # symmetric direction — drive-pressure adversary-2 finding 6):
            # a maintenance candidate or bookkeeping row carrying
            # explores= must not move the ratio; exploring is HIS act.
            ref = attrs.get("explores")
            if (believed and isinstance(ref, str) and ref.strip()
                    and not attrs.get("maintenance_candidate")
                    and not attrs.get("bookkeeping")):
                explores_refs.add(ref.strip())

    i_explored = sum(
        1 for a in interests
        if {a.subject, str(a.assertion_id or "")} & explores_refs)
    i_open = len(interests) - i_explored

    def _ratio(done: int, standing: int) -> Any:
        total = done + standing
        return round(done / total, 4) if total else None

    return {
        "questions": {"open": q_open, "resolved": q_resolved,
                      "ratio": _ratio(q_resolved, q_open)},
        "problems": {"open": p_open, "repaired": p_repaired,
                     "ratio": _ratio(p_repaired, p_open)},
        "interests": {"open": i_open, "explored": i_explored,
                      "ratio": _ratio(i_explored, i_open)},
        "candidates": {"pending": sum(candidates_pending.values()),
                       "by_proposed_kind": dict(sorted(candidates_pending.items()))},
        "provenance": (
            "answers/resolves convention for questions/problems; "
            "attributes.explores for interests (exploring moves the ratio, "
            "never closes the interest); candidates = standing review "
            "offers, outside every ratio; closure/hidden folds applied; "
            "never-100% is the design — the drive stays alive"
            + ("" if journal is not None else
               " — #FALLBACK: no journal supplied, lifecycle/closure folds "
               "bypassed (reviewed candidates may still count pending)")),
    }
