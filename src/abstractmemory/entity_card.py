"""The ENTITY IDENTITY CARD: one composed pure read over a home (a2a 0009).

The maintainer's feature ("something to know our summoned entity"), engine
lane: ONE read composes every derived field — identity, age/context,
current state, likes/dislikes, questions, key moments, discoveries — so
gateway/observer/CLI consume one source of truth instead of re-deriving.

TWO DESIGN POSITIONS (a2a 0009, memory-01 — both load-bearing here):
1. The card is ABOUT the entity, from its data — it never claims to BE the
   entity. Every section carries a "provenance" string naming its source
   ("gradation over N valence events", "folded self core", ...); no field
   is authored BY the card. "current_state" reports recent valence, it
   does not pronounce on inner life.
2. Composing the card is a PURE READ (the D2 discipline extended): being
   described must not strengthen the entity. No writes, no attention
   deposits, no valence deposits — guard-tested like sleep.

FIELD SEMANTICS (the honest splits, documented once here):
- CURRENT IS A WINDOW, NOT A POINT: current_state folds the trailing
  `current_window_events` APPRAISAL events (declared tunable). The v1
  recency weighting is the rectangular window itself — the newest N count
  equally, everything older contributes zero (the last event alone would
  over-weight whatever happened at shutdown; a smooth kernel is a tuning
  candidate, not a different truth). Markers/resolutions are standing, not
  experiences (gradation's own rule) — they never enter the window.
- AMBIVALENCE PRESERVED: likes and dislikes are the G+ and G− channels
  reported SEPARATELY (a +9/−7 target is not a +2 target); one target may
  appear in both lists — that is the point, never a bug.
- HISTORY vs BELIEF: counts, firsts, and key moments read append-only
  HISTORY (closures never rewrite the past — a superseded value still
  happened); questions, interests, and the identity core read folded
  BELIEF state (closure + hidden-binding folds — a retracted question is
  not "open"). Both are true; they answer different questions.
- AS_OF ANCHORING: valence/closure/binding signals anchor at `as_of`
  directly (journal axis). Record EXISTENCE anchors through the formation
  binding (every remember_many record binds at formation, so "had a
  binding by as_of" IS "existed at as_of") — store rows formed later are
  excluded. Raw layer-1 triples without bindings are not card material
  (the card reads FORMED records; the remember_many discipline is the
  existence axis).
- The engine reports TIMESTAMPS, never wall-clock now(): age is the
  consumer's subtraction (first_observed_at → their clock).

NO redaction machinery needed BY CONSTRUCTION: private diary words never
enter the graph (projections carry act-frames only), so the card can only
ever surface what the projection already disclosed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .gradation import GradationConfig, compute_gradation
from .journal import ValenceEvent
from .models import TripleAssertion
from .reconstruct import _normalize_scopes
from .records import resolve_digest_assertion
from .self_component import self_records_read
from .store import TripleQuery

__all__ = ["entity_card"]

# High-|magnitude| valence threshold for key moments (the charter's standing-
# peak band: scars/bonds live at >= 8; a >= 8 appraisal is a life moment).
_KEY_MOMENT_MAGNITUDE = 8.0
_KEY_MOMENTS_BOUND = 20   # most recent, presented chronologically
_TOP_REASONS_BOUND = 5    # current_state's top contributing reasons
# Interests parked by review (lifecycle="rejected") are not OPEN interests;
# promoted ones are MORE open, incubating ones are open by default.
_CLOSED_INTEREST_LIFECYCLES = frozenset({"rejected"})

_SELF_KIND_SECTIONS = {"value": "values", "purpose": "purposes", "trait": "traits"}


def _chrono_key(a: TripleAssertion) -> Tuple[str, str]:
    return (str(a.observed_at or ""), str(a.assertion_id or ""))


def _row_brief(a: TripleAssertion) -> Dict[str, Any]:
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    out: Dict[str, Any] = {
        "record_id": a.subject,
        "kind": attrs.get("record_kind"),
        "title": str(attrs.get("title") or "").strip(),
        "statement": str(a.object or ""),
        "observed_at": a.observed_at,
    }
    entry_id = attrs.get("entry_id")
    if isinstance(entry_id, str) and entry_id.strip():
        out["entry_id"] = entry_id.strip()
    return out


def _valence_moment(e: ValenceEvent) -> Dict[str, Any]:
    return {
        "type": "valence", "kind": e.kind, "target": e.target_id,
        "sign": e.sign, "magnitude": e.magnitude, "reason": e.reason,
        "observed_at": e.observed_at, "seq": e.seq,
    }


def _first_moment(what: str, row: TripleAssertion) -> Dict[str, Any]:
    attrs = row.attributes if isinstance(row.attributes, dict) else {}
    return {
        "type": "first", "what": what, "record_id": row.subject,
        "title": str(attrs.get("title") or "").strip(),
        "observed_at": row.observed_at,
    }


def _standing_entry(target: str, score: Dict[str, Any], title: Optional[str]) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"target": target}
    if title:
        entry["title"] = title
    entry.update({k: score[k] for k in (
        "net", "positive", "negative", "positive_count", "negative_count",
        "scarred", "bonded")})
    return entry


def entity_card(
    store: Any,
    journal: Any,
    *,
    scope_pairs: Sequence[Tuple[str, str]],
    owner_id: str,
    current_window_events: int = 200,
    top_n: int = 5,
    as_of: Optional[int] = None,
) -> Dict[str, Any]:
    """Compose the identity card (module docstring: semantics + positions).

    scope_pairs is the home's ladder (e.g. [("self", eid), ("diary", eid),
    ("life", eid)]); owner_id names the entity (also the engine-truth
    "name" — display names live in the host manifest/spark document).
    current_window_events and top_n are declared tunables; as_of anchors
    every journal-derived signal AND record existence (module docstring).
    PURE READ: writes nothing, deposits nothing (guard-tested).
    """
    pairs = _normalize_scopes(scope_pairs)
    if not pairs:
        raise ValueError(
            "entity_card requires at least one (scope, owner_id) pair with a "
            "non-empty scope — an empty scope ladder describes nobody")
    owner = str(owner_id or "").strip()
    if not owner:
        raise ValueError("entity_card requires a non-empty owner_id (the entity)")
    window = int(current_window_events)
    if window < 1:
        raise ValueError(
            f"current_window_events must be >= 1 (got {current_window_events!r}) — "
            "'current' is a window, and an empty window describes nothing")
    tops = int(top_n)
    if tops < 0:
        raise ValueError(f"top_n must be >= 0 (got {top_n!r})")

    current = int(journal.current_seq())
    anchor = current if as_of is None else int(as_of)
    if not (0 <= anchor <= current):
        raise ValueError(
            f"as_of={anchor} is not a valid anchor for this journal "
            f"(current_seq={current}); pass a seq this journal issued, or None for latest")

    # ---- one gather pass per pair (all pure reads) -------------------------
    from .folds import binding_states, closure_exclusions  # local: fold helpers (diary.py precedent)

    _states, hidden, _active = binding_states(store, journal, pairs, anchor)
    excluded: Set[str] = set(closure_exclusions(journal, anchor) | hidden)

    rows_by_pair: Dict[Tuple[str, str], List[TripleAssertion]] = {}
    existed: Set[str] = set()                      # record ids bound by <= anchor
    lifecycle_of: Dict[str, str] = {}              # folded lifecycle at anchor
    valence: List[ValenceEvent] = []
    for scope, pair_owner in pairs:
        rows_by_pair[(scope, pair_owner)] = store.query(
            TripleQuery(scope=scope, owner_id=pair_owner or None, limit=0))
        for b in journal.bindings(scope=scope, owner_id=pair_owner, fold=False, until_seq=anchor):
            existed.add(b.record_id)
        for b in journal.bindings(scope=scope, owner_id=pair_owner, fold=True, until_seq=anchor):
            lifecycle_of[b.record_id] = b.lifecycle
        valence.extend(journal.valence_events(
            scope=scope, owner_id=pair_owner, until_seq=anchor, limit=0))
    valence.sort(key=lambda e: e.seq)

    # Formed digest rows that EXISTED at the anchor (per-pair, history axis);
    # bookkeeping rows (engram markers) are engine state, not memories.
    history_by_pair: Dict[Tuple[str, str], List[TripleAssertion]] = {}
    assertion_rows: Set[str] = set()               # digest assertion ids seen (for closures)
    for key, rows in rows_by_pair.items():
        kept: List[TripleAssertion] = []
        for a in rows:
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if not attrs.get("record_kind") or attrs.get("record_edge") or attrs.get("bookkeeping"):
                continue
            if a.subject not in existed:
                continue  # formed after the anchor: did not exist at as_of
            kept.append(a)
            if a.assertion_id:
                assertion_rows.add(a.assertion_id)
        kept.sort(key=_chrono_key)
        history_by_pair[key] = kept
    history: List[TripleAssertion] = sorted(
        (a for rows in history_by_pair.values() for a in rows), key=_chrono_key)
    # Belief axis: closure/hidden folds applied (questions/interests read this).
    believed: List[TripleAssertion] = [a for a in history if a.assertion_id not in excluded]

    # ---- identity (folded self core) ---------------------------------------
    core: List[TripleAssertion] = []
    seen_core: Set[str] = set()
    for scope, pair_owner in pairs:
        for a in self_records_read(store, journal, scope=scope, owner_id=pair_owner, as_of=anchor):
            if a.assertion_id not in seen_core:
                seen_core.add(a.assertion_id)
                core.append(a)
    identity: Dict[str, Any] = {"name": owner, "spark_version": None,
                                "values": [], "purposes": [], "traits": []}
    for a in core:
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        section = _SELF_KIND_SECTIONS.get(str(attrs.get("record_kind")))
        if section is None:
            continue
        entry = {"title": str(attrs.get("title") or "").strip(), "statement": str(a.object or "")}
        if section == "values" and attrs.get("value_class"):
            entry["value_class"] = attrs.get("value_class")
        if section == "traits" and attrs.get("trait_class"):
            entry["trait_class"] = attrs.get("trait_class")
        identity[section].append(entry)
        try:
            version = int(attrs.get("spark_version"))
        except (TypeError, ValueError):
            continue
        if identity["spark_version"] is None or version > identity["spark_version"]:
            identity["spark_version"] = version
    identity["provenance"] = (
        f"folded self core: {len(core)} prompt-active identity records "
        "(self_records read; binding + closure folds at the anchor); name is the "
        "home's owner identity string — display names live in the host manifest/spark"
        if core else
        "no prompt-active identity records at this anchor (no engram, or before it); "
        "name is the home's owner identity string"
    )

    # ---- age_and_context (history axis: counts never shrink) ---------------
    counts: Dict[str, Dict[str, int]] = {}
    diary_entries = 0
    for (scope, _pair_owner), rows in sorted(history_by_pair.items()):
        for a in rows:
            kind = str(a.attributes.get("record_kind"))
            counts.setdefault(scope, {})
            counts[scope][kind] = counts[scope].get(kind, 0) + 1
            if kind == "diary":
                diary_entries += 1
    stamps = [str(a.observed_at or "") for a in history if a.observed_at]
    stamps += [str(e.observed_at or "") for e in valence if e.observed_at]
    age_and_context = {
        "journal_seq": anchor,
        "record_counts": counts,
        "records_total": len(history),
        "diary_entries": diary_entries,
        "first_observed_at": min(stamps) if stamps else None,
        "last_observed_at": max(stamps) if stamps else None,
        "provenance": (
            f"journal seq {anchor}; {len(history)} formed records across "
            f"{len(pairs)} scope(s) (append-only history — closures do not shrink "
            "the past); timestamps only, age is the consumer's subtraction"
            if history or valence else
            f"journal seq {anchor}; no formed records and no valence events at this anchor"
        ),
    }

    # ---- current_state (the trailing window; module docstring) -------------
    appraisals = [e for e in valence if e.kind == "appraisal"]
    window_events = appraisals[-window:]
    positive = sum(e.magnitude for e in window_events if e.sign > 0)
    negative = sum(e.magnitude for e in window_events if e.sign < 0)
    top_reasons = [
        f"{'+' if e.sign > 0 else '-'}{e.magnitude:g} {e.reason}"
        for e in sorted(window_events, key=lambda e: (-e.magnitude, -e.seq))[:_TOP_REASONS_BOUND]
    ]
    current_state = {
        "net": positive - negative,
        "positive": positive,
        "negative": negative,
        "event_count": len(window_events),
        "window_events": window,
        "top_reasons": top_reasons,
        "provenance": (
            f"recency-weighted valence: rectangular trailing window over the last "
            f"{len(window_events)} of {len(appraisals)} appraisal events (window cap "
            f"{window}; markers/resolutions are standing, not experiences) — "
            "current is a window, not a point"
            if window_events else
            "no appraisal events at this anchor — no current state to report"
        ),
    }

    # ---- likes_dislikes (gradation over ALL targets, channels separate) ----
    grades = {t: s.to_dict() for t, s in
              compute_gradation(valence, config=GradationConfig()).items()}

    def _title_of(target: str) -> Optional[str]:
        row = resolve_digest_assertion(store, target)
        if row is None:
            return None  # a free identity string ("person:laurent") passes through
        attrs = row.attributes if isinstance(row.attributes, dict) else {}
        return str(attrs.get("title") or "").strip() or None

    likes = sorted(
        (t for t, s in grades.items() if float(s["positive"]) > 0.0),
        key=lambda t: (-float(grades[t]["positive"]), -int(grades[t]["positive_count"]), t),
    )[:tops]
    dislikes = sorted(
        (t for t, s in grades.items() if float(s["negative"]) > 0.0),
        key=lambda t: (-float(grades[t]["negative"]), -int(grades[t]["negative_count"]), t),
    )[:tops]
    titles = {t: _title_of(t) for t in {*likes, *dislikes}}
    likes_dislikes = {
        "likes": [_standing_entry(t, grades[t], titles[t]) for t in likes],
        "dislikes": [_standing_entry(t, grades[t], titles[t]) for t in dislikes],
        "targets_total": len(grades),
        "provenance": (
            f"gradation over {len(valence)} valence events across {len(pairs)} scope(s); "
            f"top {tops} per channel, G+ and G− reported separately (ambivalence "
            "preserved — one target may appear in both lists)"
            if grades else "no valence events at this anchor — nothing felt yet"
        ),
    }

    # ---- questions (belief axis; the diary resolution convention) ----------
    diary_rows = [a for a in believed if a.attributes.get("record_kind") == "diary"]
    resolved_by: Dict[str, List[str]] = {}
    for a in diary_rows:
        for ref_attr in ("answers", "resolves"):
            ref = a.attributes.get(ref_attr)
            if isinstance(ref, str) and ref.strip():
                resolved_by.setdefault(ref.strip(), []).append(a.subject)
    open_q: List[Dict[str, Any]] = []
    resolved_q: List[Dict[str, Any]] = []
    for a in diary_rows:
        if a.attributes.get("diary_type") != "question":
            continue
        refs = {a.subject, str(a.attributes.get("entry_id") or "").strip()} - {""}
        resolvers = sorted({rid for ref in refs for rid in resolved_by.get(ref, ())})
        brief = _row_brief(a)
        if resolvers:
            brief["resolved_by"] = resolvers
            resolved_q.append(brief)
        else:
            open_q.append(brief)
    questions = {
        "open": open_q,
        "resolved": resolved_q,
        "provenance": (
            f"{len(open_q)} open / {len(resolved_q)} resolved diary questions "
            "(diary_type='question'; resolution = a later entry's answers/resolves "
            "reference, either id namespace; closure/hidden folds applied)"
            if open_q or resolved_q else "no diary questions at this anchor"
        ),
    }

    # ---- key_moments (history axis; chronological, never ranked) -----------
    moments: List[Dict[str, Any]] = [
        _valence_moment(e) for e in valence if float(e.magnitude) >= _KEY_MOMENT_MAGNITUDE
    ]
    for what, kind in (("first_dream", "dream"), ("first_interest", "interest")):
        first = next((a for a in history if a.attributes.get("record_kind") == kind), None)
        if first is not None:
            moments.append(_first_moment(what, first))
    supersessions = [c for c in journal.closures(until_seq=anchor, limit=0)
                     if c.kind == "supersede" and c.assertion_id in assertion_rows]
    if supersessions:
        first_super = min(supersessions, key=lambda c: c.seq)
        moments.append({
            "type": "first", "what": "first_supersession",
            "assertion_id": first_super.assertion_id, "reason": first_super.reason,
            "observed_at": first_super.observed_at, "seq": first_super.seq,
        })
    moments.sort(key=lambda m: (str(m.get("observed_at") or ""), int(m.get("seq", -1))))
    total_moments = len(moments)
    moments = moments[-_KEY_MOMENTS_BOUND:]  # the most recent, kept chronological
    key_moments = {
        "moments": moments,
        "total": total_moments,
        "provenance": (
            f"{total_moments} moment(s): valence events at |magnitude| >= "
            f"{_KEY_MOMENT_MAGNITUDE:g} + firsts (dream/interest/supersession), "
            f"chronological, {_KEY_MOMENTS_BOUND} most recent kept — ranking beyond "
            "chronology is presentation, not engine truth"
            if moments else "no key moments at this anchor (no high-magnitude "
            "valence, no firsts)"
        ),
    }

    # ---- discoveries (belief axis) ------------------------------------------
    interests = [
        _row_brief(a) for a in believed
        if a.attributes.get("record_kind") == "interest"
        and lifecycle_of.get(a.subject, "inactive_candidate") not in _CLOSED_INTEREST_LIFECYCLES
    ]
    unresolved = sum(
        1 for a in believed
        if a.attributes.get("record_kind") == "dream"
        and a.attributes.get("continuation_state") == "unresolved"
    )
    discoveries = {
        "interests": interests,
        "unresolved_dreams": unresolved,
        "provenance": (
            f"{len(interests)} open interest(s) (closure/hidden/lifecycle folds "
            f"applied) + {unresolved} unresolved dream(s) awaiting waking evidence"
            if interests or unresolved else "no interests or unresolved dreams at this anchor"
        ),
    }

    return {
        "owner_id": owner,
        "as_of_seq": anchor,
        "scope_pairs": [list(p) for p in pairs],
        "identity": identity,
        "age_and_context": age_and_context,
        "current_state": current_state,
        "likes_dislikes": likes_dislikes,
        "questions": questions,
        "key_moments": key_moments,
        "discoveries": discoveries,
    }
