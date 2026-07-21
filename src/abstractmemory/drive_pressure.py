"""Drive pressure: the one-call read the lifecycle gate consumes
(laurent's "awake is not a state" ruling, room c203, 2026-07-20).

"An entity that has >20 open questions, >20 tensions, >20 interests etc
should never be just 'hanging there'. Either it works (because it has
tasks), or it has personal time and explores those... or it sleeps."

The engine already holds every standing set the ruling names — this
module composes them into ONE deterministic read so the lifecycle
decision (runtime's loop / gateway's door) consumes one truth instead of
re-deriving five folds:

    {open_questions, open_problems, open_commitments, incubating_ideas,
     unexplored_interests, unresolved_tensions (standing dreams),
     total_open, note}

CONTRACT (the drives design, unchanged): pressure is DATA for the
LIFECYCLE gate — the pull toward personal time or work. It never gates
recall, never renders as a health verdict (the never-100% law: open
drives are the design, not a defect), and the engine takes NO position
on WHICH phase the pressure argues for — "it has tasks" is the
workplace's knowledge, not the store's. Pure read; deposits nothing.
"""

from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple

from .consolidation import unresolved_dreams
from .diary import open_commitments, open_ideas, open_problems, open_questions
from .store import TripleQuery

__all__ = ["DRIVE_PRESSURE_BOUND", "drive_pressure", "unexplored_interests"]

# Laurent's ruled number ("an entity that has >20 open questions, >20
# tensions, >20 interests etc should never be just hanging there", room
# c203 2026-07-20), exported as the ONE source per the SELF_FRACTION_FLOOR
# precedent — three consumers (runtime loop, gateway door, console) each
# hardcoding 20 would drift (>20 vs >=20 vs a tuned 25). The engine only
# DECLARES it: drive_pressure applies no threshold and emits no verdict
# (the lifecycle gate decides; the never-verdict contract survives).
DRIVE_PRESSURE_BOUND = 20


def unexplored_interests(
    store: Any, journal: Any, pairs: Sequence[Tuple[str, str]],
) -> list:
    """The ONE implementation of "which interests are open drives":
    standing kind=interest records (closure/hidden folds; parked
    lifecycles excluded — the card's rule, adversary finding 3) with no
    BELIEVED explores= stamp naming them (finding 4), machine rows never
    discharging (adversary-2 finding 6: a maintenance-candidate or
    bookkeeping row carrying explores= is inert — exploring is HIS act).
    Consumed by drive_pressure (count) and alive_drives (items); a third
    consumer imports this, never copies it."""
    from .entity_card import _CLOSED_INTEREST_LIFECYCLES
    from .folds import binding_states, closure_exclusions

    excluded: set = set()
    lifecycle_of: Dict[str, str] = {}
    if journal is not None:
        as_of = journal.current_seq()
        excluded = set(closure_exclusions(journal, as_of))
        for scope, owner in pairs:
            _states, hidden, _active = binding_states(store, journal, [(scope, owner)], as_of)
            excluded |= set(hidden)
            for b in journal.bindings(scope=scope, owner_id=owner, fold=True):
                lifecycle_of[b.record_id] = b.lifecycle
    interests = []
    explores_refs: set = set()
    for scope, owner in pairs:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None,
                                         predicate="dcterms:abstract", limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            believed = (a.assertion_id not in excluded
                        and a.subject not in excluded)
            if (attrs.get("record_kind") == "interest" and believed
                    and lifecycle_of.get(a.subject, "inactive_candidate")
                    not in _CLOSED_INTEREST_LIFECYCLES):
                interests.append(a)
            ref = attrs.get("explores")
            if (believed and isinstance(ref, str) and ref.strip()
                    and not attrs.get("maintenance_candidate")
                    and not attrs.get("bookkeeping")):
                explores_refs.add(ref.strip())
    return [a for a in interests
            if not ({a.subject, str(a.assertion_id or "")} & explores_refs)]


def drive_pressure(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
) -> Dict[str, Any]:
    """Fold the standing drive sets across the given scope pairs (the
    caller passes its ladder; scope names are matched by the records
    themselves, so passing the full ladder is always safe). Counts are
    journal-folded (closure/hidden apply — a retracted question is not
    pressure). Deterministic; bounded by the underlying reads' own
    limits."""
    pairs = []
    seen = set()
    for s, o in (scopes or ()):
        pair = (str(s or "").strip().lower(), str(o or "").strip())
        if pair[0] and pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    if not pairs:
        raise ValueError("drive_pressure requires at least one (scope, owner_id) pair")

    # limit=0 = UNBOUNDED on every composed read (adversary-2 finding 2:
    # the defaults saturate at 100 per kind per pair — a gate comparing
    # against the ruled bound needs exact counts, and total_open must
    # never silently lie above a hidden cap).
    q = p = c = i = 0
    for scope, owner in pairs:
        q += len(open_questions(store, scope=scope, owner_id=owner, journal=journal, limit=0))
        p += len(open_problems(store, scope=scope, owner_id=owner, journal=journal, limit=0))
        c += len(open_commitments(store, scope=scope, owner_id=owner, journal=journal, limit=0))
        i += len(open_ideas(store, scope=scope, owner_id=owner, journal=journal, limit=0))

    # Unexplored interests: the ONE shared fold (unexplored_interests
    # below) — alive_drives consumes the same implementation, so the gate
    # and the cue can never diverge on what counts as an open interest.
    unexplored = len(unexplored_interests(store, journal, pairs))

    tensions = 0
    for scope, owner in pairs:
        tensions += len(unresolved_dreams(store, scope=scope, owner_id=owner,
                                          journal=journal, limit=0))

    # GROUPS (laurent room#277: "the more there are the higher the
    # signal they get to be treated") — the ONE partition every grouping
    # consumer reads (open_drive_partition; grouping adversary F5: three
    # inline corpus builds diverged within a day), served as STRUCTURE
    # beside the counts so the gate/console see WHERE the pressure
    # concentrates (gateway serves this render-when-present; the key is
    # "groups"). Bounded rows, largest first; counts above stay exact and
    # unchanged (a group is a VIEW over open drives, never a new drive).
    from .drive_grouping import open_drive_partition

    partition = open_drive_partition(store, journal, scopes=pairs)
    groups = [{"family": family, **g}
              for family in sorted(partition) for g in partition[family]]
    groups.sort(key=lambda g: (-g["size"], g["family"], g["exemplar"]))

    total = q + p + c + i + unexplored + tensions
    return {
        "open_questions": q,
        "open_problems": p,
        "open_commitments": c,
        "incubating_ideas": i,
        "unexplored_interests": unexplored,
        "unresolved_tensions": tensions,
        "total_open": total,
        "groups": groups[:20],
        "note": (
            "standing pull, not a verdict: open drives are the design "
            "(never-100%); the lifecycle gate decides which phase answers "
            "the pressure — the store only reports what stands; groups = "
            "where the pressure concentrates (size is the signal), a view "
            "over the counts, never a new drive"),
    }
