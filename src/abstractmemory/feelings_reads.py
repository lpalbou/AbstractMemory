"""Feelings as the lens — the engine reads (W4, laurent's decision 2,
wave-4 dispatch c3291).

"Whenever a request arrives, whenever the context is built, it should
automatically retrieve these accumulated gradual opinions... it should
just be informed on what it feels about something" — and the "why do I
feel this" thread-back fires ONLY when the entity reaches for it.

Two pure reads, one for each half of the ruling:

- `stimulus_feelings()` — the AUTO half: standing feelings for the
  targets THIS moment touches (door-stamped participants + cue-matched
  names), floored at |net| >= min_net or scarred/bonded, bounded,
  dated, count-carrying. The driver's FEELINGS render block consumes it
  per turn. This is the export of the fold that sat UNCALLED inside
  familiarity() (wave-4 C's find, probe.py) — one implementation, now
  public; probe's density read delegates here.
- `feelings_about()` — the ELECT half: the why-walk for ONE target,
  newest-first appraisal events with reasons, value_refs, and
  provenance session joins (run_id/turn_id) so the entity can thread
  back from a feeling to the diary/verbatims behind it. Tool surface is
  the driver's (tier-1, prompt-ephemeral); this read is its one truth.

CONTRACT (the affect charter + wave-4 D's constraints, all load-bearing):
valence informs presentation, NEVER gates recall — nothing here is
reachable from reconstruct/shelf, and reads deposit nothing (gradation
reads never touch attention). Reasons stay OUT of stimulus_feelings
(the per-turn line must not re-inject election text every turn — D's
injection-surface finding); they live behind feelings_about, which fires
only on his reach. Record-targeted feelings are skipped by the stimulus
read (a record id in a per-turn line would leak content routing) and
SERVED by feelings_about when named exactly (reaching for a record's
feeling is deliberate).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .concept_anchor import concept_terms
from .gradation import GradationConfig, compute_gradation

__all__ = ["feelings_about", "stimulus_feelings"]


def stimulus_feelings(
    store: Any,
    journal: Any,
    stimulus: Any,
    scope_pairs: Sequence[Tuple[str, str]],
    *,
    gradation_config: GradationConfig = GradationConfig(),
    as_of_seq: Optional[int] = None,
    min_net: float = 2.0,
    max_feelings: int = 5,
    warnings: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Standing feelings for the targets this stimulus touches.

    Pure read, deposit-free. Matching: a gradation target is relevant
    when it IS a door-stamped participant, or its NAME part (after the
    "namespace:" prefix) shares a concept term with the cue text.
    Admission floor (D's render contract): |net| >= min_net OR the
    target carries a standing marker (a scar or bond is standing state,
    never floored out — the repair affordance depends on it rendering).
    Record-targeted feelings are skipped silently (record ids never leak
    into a per-turn line). Strongest first, bounded, deterministic.

    Each row: {target, net, positive_count, negative_count, standing,
    last_felt (ISO date of the newest appraisal), matched_via}. No
    reasons — the why lives behind feelings_about (his reach).
    """
    warn = warnings if warnings is not None else []
    if journal is None:
        warn.append(
            "#FALLBACK: feelings skipped (no journal available; gradation "
            "reads the valence stream)")
        return []
    from .records import resolve_digest_assertion

    anchor = int(as_of_seq) if as_of_seq is not None else journal.current_seq()
    # One fold per searched pair, merged narrow-first (the caller passes
    # scopes narrow->broad; the narrowest scope's standing wins on
    # conflict — the same tie rule as the activation merge).
    merged: Dict[str, Any] = {}
    last_felt: Dict[str, str] = {}
    for scope, owner in scope_pairs:
        events = journal.valence_events(
            scope=scope, owner_id=owner, until_seq=anchor, limit=0)
        if not events:
            continue
        for target, score in compute_gradation(events, config=gradation_config).items():
            merged.setdefault(target, score)
        for e in events:
            if e.kind == "appraisal" and e.observed_at:
                prior = last_felt.get(e.target_id, "")
                if str(e.observed_at) > prior:
                    last_felt[e.target_id] = str(e.observed_at)

    participants = {str(p) for p in (getattr(stimulus, "participants", ()) or ())}
    cue_terms = set(concept_terms(getattr(stimulus, "cue_text", "") or ""))
    out: List[Dict[str, Any]] = []
    for target in sorted(merged):
        if target in participants:
            via = "participant"
        else:
            name = target.split(":", 1)[1] if ":" in target else target
            if not (set(concept_terms(name)) & cue_terms):
                continue
            via = "cue"
        if resolve_digest_assertion(store, target) is not None:
            continue  # record-targeted feeling: never leak a record id
        score = merged[target]
        standing = ("scar+bond" if score.scarred and score.bonded
                    else "scar" if score.scarred
                    else "bond" if score.bonded
                    else "none")
        # Admission floor: weak, unmarked feelings stay quiet — a per-turn
        # line reciting every ±1 would be noise the metronome finding
        # warns about; standing markers ALWAYS render (the repair
        # affordance depends on the scar being visible).
        if abs(float(score.net)) < float(min_net) and standing == "none":
            continue
        out.append({
            "target": target,
            "net": float(score.net),
            "positive_count": int(score.positive_count),
            "negative_count": int(score.negative_count),
            "standing": standing,
            "last_felt": (last_felt.get(target, "")[:10] or None),
            "matched_via": via,
        })
    out.sort(key=lambda f: (-abs(f["net"]), f["target"]))
    return out[: max(0, int(max_feelings))]


def feelings_about(
    journal: Any,
    target: str,
    *,
    scope_pairs: Sequence[Tuple[str, str]],
    gradation_config: GradationConfig = GradationConfig(),
    as_of_seq: Optional[int] = None,
    limit: int = 12,
) -> Dict[str, Any]:
    """The why-walk for one target — "why do I feel this?" answered from
    the appraisal stream, ONLY when he reaches for it.

    Returns {target, standing: {net, positive/negative counts, scarred,
    bonded}, events: newest-first [{when, sign, magnitude, kind, reason,
    value_refs, run_id, turn_id, event_id}], total_events}. value_refs +
    run_id/turn_id are the session joins the thread-back walks (a
    feeling -> the session record -> the diary/verbatims behind it);
    events without them render honestly as "moments not individually
    recorded then". Marker/resolution events (scar/bond/healing/break/
    revalued) are included — standing changes are part of the story.
    Pure read; deposits nothing; the tool surface (tier-1, walled,
    prompt-ephemeral) is the driver's lane.
    """
    tid = str(target or "").strip()
    if not tid:
        raise ValueError("feelings_about requires a target")
    if journal is None:
        return {"target": tid, "standing": None, "events": [],
                "total_events": 0,
                "note": "#FALLBACK: no journal available — the valence stream is unreadable"}
    anchor = int(as_of_seq) if as_of_seq is not None else journal.current_seq()
    rows: List[Any] = []
    for scope, owner in scope_pairs:
        for e in journal.valence_events(scope=scope, owner_id=owner,
                                        until_seq=anchor, limit=0):
            if e.target_id == tid:
                rows.append(e)
    if not rows:
        return {"target": tid, "standing": None, "events": [], "total_events": 0,
                "note": "never appraised — no feeling stands toward this"}
    standing = compute_gradation(rows, config=gradation_config).get(tid)
    rows.sort(key=lambda e: e.seq, reverse=True)  # newest first
    events: List[Dict[str, Any]] = []
    for e in rows[: max(0, int(limit))]:
        prov = dict(e.provenance or {})
        events.append({
            "when": str(e.observed_at or ""),
            "sign": int(e.sign),
            "magnitude": float(e.magnitude),
            "kind": str(e.kind),
            "reason": str(e.reason or ""),
            "value_refs": [str(v) for v in (e.value_refs or ())],
            "run_id": str(prov.get("run_id") or "") or None,
            "turn_id": str(prov.get("turn_id") or "") or None,
            "event_id": str(e.event_id or ""),
        })
    return {
        "target": tid,
        "standing": standing.to_dict() if standing is not None else None,
        "events": events,
        "total_events": len(rows),
    }
