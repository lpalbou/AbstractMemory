"""Origin-diversity fold over a rendered shelf (M-F, improving-entity-capabilities).

The rumination counterweight: when many shelf seats hold the entity's OWN
retellings of one thing, repetition reads as corroboration ("nine bridge
records" = one dream plus his own retellings — the bridge-attractor
mechanic). Per-line origin labels shipped runtime-side; what readers still
re-derived by hand every time was the AGGREGATE — "9 of these 15 memories
come from one voice". This module computes that fold as DATA the host can
render. Presentation, never selection (the observer's line): nothing here
touches ordering, admission, budgets, or any engine state — a pure read
over already-built handles, same consumption shape as agent's
`circling_streak` (returns data or None; attaches ZERO policy).

Axis, deliberately coarser than disposal's witness-origin: a VOICE is
(provenance.source, actor). disposal.origin_of adds the session axis
because its question is promotion independence ("distinct witnesses");
this fold's question is "how many independent voices are on this shelf" —
nine own-reflection retellings across nine days are nine sessions but ONE
voice, and folding them apart would hide exactly the pattern M-F exists to
surface. Session diversity within the dominant voice is still counted, as
display data ("across 6 sessions").

Exclusions and fallbacks, each honest:
- `admission == "self"` handles are EXCLUDED from the fold: identity
  records are present by right (posture, not match) and share one origin
  by construction — counting them would make the label fire on every
  entity shelf, and a label that always fires teaches habituation.
- Records without a provenance source fall back to a kind-keyed voice
  (`kind:dream`, ...) instead of merging into one unlabeled mega-voice —
  dreams and engram-era records are not one shared origin.

Vocabulary boundary: entity-facing channel words ("your own reflection")
are the HOST's vocabulary (runtime already owns SOURCE_LABELS; a third
copy here would be the clamp-drift class). Hosts inject their label map;
absent labels fall back to the raw engraved source string — honest, never
invented. The composed note reuses the established house phrase
("repetition is not corroboration") so every surface speaks one language.

Declared tunables (not folklore): MIN_COUNTED — below it the fold abstains
(a two-seat shelf cannot be "mostly" anything; the A1 all-short-buffers
precedent); DOMINANCE_FLOOR — the share at which the note switches from
the diverse phrasing to the one-voice phrasing. Both overridable per call.

Return shape (frozen contract; evolution is ADDITIVE keys, never renames —
the A1 return-dict discipline):

    {
      "counted": 12,          # handles measured (non-self)
      "excluded_self": 6,     # identity-presence handles left out
      "voices": 3,            # distinct (source, actor) voices
      "dominant": {
        "source": "entity-chat-reflection-v1",  # raw engraved string
        "actor": "",                              # raw; "" when absent
        "label": "your own reflection",           # injected or raw fallback
        "count": 9,
        "share": 0.75,
        "sessions": 6,        # distinct sessions inside the dominant voice
      },
      "note": "9 of these 12 memories come from one voice (your own
               reflection, across 6 sessions) - repetition is not
               corroboration.",
    }
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

__all__ = ["ORIGIN_DOMINANCE_FLOOR", "ORIGIN_MIN_COUNTED", "origin_diversity"]

# Below this many counted (non-self) handles the fold abstains: a tiny
# shelf cannot be "mostly" anything, and a label over 2 records is noise.
ORIGIN_MIN_COUNTED = 3

# At or above this dominant-voice share the note uses the one-voice
# phrasing; below it the diverse phrasing. Display wording only — the
# numbers are always returned and hosts may apply their own bar.
# CALIBRATED on Ephemeral's live store (2026-07-17 A/B, read-only copy):
# at 0.5 a balanced 3-of-6 three-voice shelf fired the one-voice phrasing
# on every probe cue — a label that always fires teaches habituation.
# 0.6 keeps the motivating case (9 of 15) firing while balanced shelves
# read as diverse.
ORIGIN_DOMINANCE_FLOOR = 0.6


def _field(handle: Any, name: str) -> Any:
    """Handles arrive as MemoryHandle objects or as their to_dict() dicts
    (the runtime renders from dicts); read either without coercion."""
    if isinstance(handle, Mapping):
        return handle.get(name)
    return getattr(handle, name, None)


def _voice_of(handle: Any) -> Tuple[str, str, str]:
    """(source, actor, session) for one handle, from the assertion
    provenance the shelf lifts into handle.provenance.assertion_provenance.
    Empty source falls back to a kind-keyed voice (see module docstring).
    Session prefers session_id, then run_id, then turn_id — run_id is the
    honest session proxy for chat-formed records (one run per session);
    turn ids alone would overcount."""
    prov = _field(handle, "provenance")
    prov = prov if isinstance(prov, Mapping) else {}
    ap = prov.get("assertion_provenance")
    ap = ap if isinstance(ap, Mapping) else {}
    source = str(ap.get("source") or "").strip()
    actor = str(ap.get("actor") or "").strip()
    if not source:
        kind = str(_field(handle, "kind") or "").strip() or "memory"
        source = f"kind:{kind}"
    session = str(ap.get("session_id") or ap.get("run_id") or ap.get("turn_id") or "").strip()
    return source, actor, session


def _label_for(source: str, actor: str, labels: Optional[Mapping[str, str]]) -> str:
    """Host-injected label, else the raw engraved string — never invented.
    Lookup order: "source|actor" (finest), then source alone. kind:-voices
    fall back to the bare kind word ("dream"), which is entity register
    already (the kind vocabulary is a closed set the entity meets in its
    own recall surfaces)."""
    if labels:
        for key in (f"{source}|{actor}", source):
            label = labels.get(key)
            if isinstance(label, str) and label.strip():
                return label.strip()
    if source.startswith("kind:"):
        return source[len("kind:"):] or "memory"
    return source or "unlabeled origin"


def origin_diversity(
    handles: Sequence[Any],
    *,
    labels: Optional[Mapping[str, str]] = None,
    min_counted: int = ORIGIN_MIN_COUNTED,
    dominance_floor: float = ORIGIN_DOMINANCE_FLOOR,
) -> Optional[Dict[str, Any]]:
    """Fold a rendered shelf into its voice diversity; None = abstain.

    Pure read over the given handles (dicts or MemoryHandle objects) — no
    store, no journal, no mutation. See the module docstring for the axis,
    the exclusions, and the frozen return shape.
    """
    if int(min_counted) < 1:
        raise ValueError(f"min_counted must be >= 1, got {min_counted!r}")
    floor = float(dominance_floor)
    if not (0.0 < floor <= 1.0):
        raise ValueError(f"dominance_floor must be within (0, 1], got {dominance_floor!r}")

    excluded_self = 0
    # voice -> [count, {sessions}] in first-seen order (deterministic ties:
    # the shelf order is the host's chosen presentation order).
    folds: Dict[Tuple[str, str], List[Any]] = {}
    for handle in handles or ():
        if str(_field(handle, "admission") or "") == "self":
            excluded_self += 1
            continue
        source, actor, session = _voice_of(handle)
        cell = folds.setdefault((source, actor), [0, set()])
        cell[0] += 1
        if session:
            cell[1].add(session)

    counted = sum(cell[0] for cell in folds.values())
    if counted < int(min_counted):
        return None

    # Dominant voice: highest count; ties go to the FIRST-SEEN voice (dict
    # order = shelf order = the host's chosen presentation priority).
    dom_source, dom_actor = next(iter(folds))
    for (source, actor), cell in folds.items():
        if cell[0] > folds[(dom_source, dom_actor)][0]:
            dom_source, dom_actor = source, actor
    dom_cell = folds[(dom_source, dom_actor)]
    dom_count = int(dom_cell[0])
    dom_sessions = len(dom_cell[1])
    share = dom_count / counted
    label = _label_for(dom_source, dom_actor, labels)
    voices = len(folds)

    if share >= floor and voices > 1:
        across = f", across {dom_sessions} sessions" if dom_sessions > 1 else ""
        note = (
            f"{dom_count} of these {counted} memories come from one voice "
            f"({label}{across}) - repetition is not corroboration."
        )
    elif voices == 1:
        across = f" across {dom_sessions} sessions" if dom_sessions > 1 else ""
        note = (
            f"all {counted} of these memories come from one voice "
            f"({label}){across} - one origin retold, not {counted} witnesses."
        )
    else:
        note = f"{counted} memories from {voices} distinct voices - no single origin dominates."

    return {
        "counted": counted,
        "excluded_self": excluded_self,
        "voices": voices,
        "dominant": {
            "source": dom_source,
            "actor": dom_actor,
            "label": label,
            "count": dom_count,
            "share": round(share, 4),
            "sessions": dom_sessions,
        },
        "note": note,
    }
