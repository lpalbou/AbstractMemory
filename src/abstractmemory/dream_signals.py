"""Dream signals: the night as a SIGNAL STREAM from maintenance acts
(laurent's Q1 ruling, dm#67 + ratification dm#75; wave-5 synthesis,
twelve constraints binding).

"The dream ITSELF is the result of memory-graph maintenance — each act
emits a SHORT SIGNAL derived from the memories it touched ('if I was to
connect blue sky and happiness, I would possibly trigger a good feeling
about those 2; if I was connecting an open to a resolved question, I
would probably surface the resolution'); the stream may or may not be
interpretable — that is the nature of dreams."

Zero LLM, deterministic. Each maintenance act that DID something (the
per-pass novelty gates already decide that — resolutions resolve once,
candidates are fingerprint-idempotent, cards revise only on evidence
change) emits one signal:

    {kind, phase, act, fragment (<=200 chars, every word from the
     touched records), touched [record ids],
     felt: {tone, weight, scarred, bonded} — READ from accumulated
     valence, never written}

Ruled typology (decision:dream-signal-vocabulary):
- changed_understanding — a connection/consolidation/revision changed
  what stands (bridges proposed-confirmed, cards revised, duplicates
  grouped);
- unresolved_tension — a standing tension pressed (bridge proposals
  awaiting waking evidence; the day's resolver vocabulary, one language
  night and day);
- changed_navigation — the reachable paths changed (resolutions landing:
  an open question closing re-routes where waking attention goes).

THE FELT BLOCK reads ONE batched gradation fold per night (the ruling's
"connecting blue sky and happiness would possibly trigger a good feeling
about those 2" — the feeling is real and HIS, accumulated by his own
appraisals; the night merely echoes it). MAINTENANCE NEVER DEPOSITS
FEELINGS: the valence journal is byte-unchanged by the whole sleep pass
(pinned guard — at live sleep cadence even ±1 deposits would saturate
the never-decaying channels in ~2.5 days and drown his elected feelings
under machine noise).

Signals COMPOSE (bounded top-K by salience) into the EXISTING one
review-gated dream record as attributes.signals + the narration digest —
every dream guard survives: review-gated, interpretation_required,
waking evidence disposes, never feeds its own proof, novelty-gated,
fingerprint-idempotent. Structure decides which signals surface;
feelings COLOR content (ratified: "structure-decides/feelings-color");
if lived data later argues feelings should weigh selection, that returns
to laurent as a new fork.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .gradation import GradationConfig, compute_gradation
from .text_tokens import truncation_meta

__all__ = ["FRAGMENT_CAP", "SIGNAL_KINDS", "TOP_K_SIGNALS",
           "compose_signals", "night_feelings", "signal"]

SIGNAL_KINDS = frozenset(
    {"changed_understanding", "unresolved_tension", "changed_navigation"})

# Fork mapping, one comment (ruled c3536): the fork's operation-ledger
# typology changed_understanding / unresolved_signal / navigation_change
# maps 1:1 onto the ruled set — unresolved_signal became
# unresolved_tension (aligning the night's word with the day's resolver
# vocabulary) and navigation_change became changed_navigation (changed_*
# order-consistency inside the closed set).

_FRAGMENT_CAP = 200
_TOP_K_SIGNALS = 12  # bounded composition (C constraint 4; ~7KB ceiling)

# Public names for the params/observability surface (entity dm#112 M5:
# the blueprint's clickable cells resolve constants via WHITELISTED
# imports — public names only, never underscores).
TOP_K_SIGNALS = _TOP_K_SIGNALS
FRAGMENT_CAP = _FRAGMENT_CAP


def _bounded_fragment(fragment: Any) -> Tuple[str, Optional[Dict[str, Any]]]:
    """The signal's fragment bounded at FRAGMENT_CAP, with the cut counted.

    Framework ADR-0026 §1: signals ride the dream stream into reports and
    surfaces the entity reads, so an unmarked cut would read as the record's
    own whole words — the fragment keeps a bare "…". The COUNTS stay out of
    the string: `_FRAGMENT_CAP` is a documented bound that `replay` relies on
    to serve the stream verbatim, and `consolidation` splices fragments into
    the stored dream digest, where marker words would pollute the keyword and
    embedding surface. `touched` always names the records quoted from.
    #[WARNING:TRUNCATION] dream-signal fragment bounded at FRAGMENT_CAP
    """
    text = str(fragment or "").strip()
    if len(text) <= _FRAGMENT_CAP:
        return text, None
    return (text[:_FRAGMENT_CAP - 1] + "…",
            truncation_meta(_FRAGMENT_CAP - 1, len(text)))


def night_feelings(
    system: Any, *, scopes: Sequence[Tuple[str, str]],
    config: Optional[GradationConfig] = None,
) -> Dict[str, Any]:
    """ONE batched pure gradation fold for the whole night (read, never
    write): target -> GradationScore. Signal builders look their touched
    targets up here; an empty stream reads as no feelings, honestly.

    THE WHOLE LADDER folds, not the first pair (adversary P0-1, deployed-
    shape miss): production callers lead with ("self", entity) while the
    reflection lanes deposit RECORD-target feelings into the "life" scope
    (chat.py/visit_workflow.py: `"life" if target.startswith("ex:")`) —
    a first-pair read made felt coloring structurally unreachable for
    exactly the record-connection case laurent's ruling names. Events
    merge across pairs by seq (deterministic; per-target streams re-sort
    by seq inside compute_gradation anyway).

    Config resolves from the system's own threaded gradation config when
    present (adversary P2-4: a fresh default here would disagree with
    system.gradation() over the same events — the F2 unreachable-tuning
    class)."""
    journal = system.journal
    if journal is None:
        return {}
    merged: Dict[int, Any] = {}
    for scope, owner in scopes:
        for e in journal.valence_events(scope=scope, owner_id=owner, limit=0):
            merged[int(e.seq)] = e
    if not merged:
        return {}
    events = [merged[s] for s in sorted(merged)]
    cfg = (config or getattr(system, "_gradation_config", None)
           or GradationConfig())
    return compute_gradation(events, config=cfg)


def _felt(feelings: Dict[str, Any], targets: Sequence[str]) -> Optional[Dict[str, Any]]:
    """The felt block for one signal: fold the touched targets' standing
    (READ-only). None when nothing was ever felt toward any of them —
    a felt block is never fabricated neutrality.

    TONE AND WEIGHT READ THE CHANNELS, never the net (adversary P1-2):
    the dual-channel charter exists because the sum provably fails —
    +100/−10 reading "pure warm" deletes the −10, and a +8/−8
    ambivalence reading "neutral, weight 0" deletes BOTH. A target felt
    both ways is MIXED within itself; weight is the larger channel. A
    score whose channels are all zero with no standing flags (e.g. a
    lone revalued bookkeeping row) contributes nothing (P2-5: presence
    of a score object is not presence of a feeling)."""
    pos_total = neg_total = 0.0
    scarred = bonded = False
    felt_any = False
    for t in targets:
        score = feelings.get(str(t))
        if score is None:
            continue
        p, n = float(score.positive), float(score.negative)
        s, b = bool(score.scarred), bool(score.bonded)
        if p > 0 or n > 0 or s or b:
            felt_any = True
        pos_total = max(pos_total, p)
        neg_total = max(neg_total, n)
        scarred = scarred or s
        bonded = bonded or b
    if not felt_any:
        return None
    tone = ("mixed" if pos_total > 0 and neg_total > 0
            else "warm" if pos_total > 0
            else "sore" if neg_total > 0 else "neutral")
    return {
        "tone": tone,
        "weight": round(max(pos_total, neg_total), 2),
        "scarred": scarred,
        "bonded": bonded,
    }


def signal(
    kind: str, *, phase: str, act: str, fragment: str,
    touched: Sequence[str],
    feelings: Optional[Dict[str, Any]] = None,
    felt_targets: Sequence[str] = (),
) -> Dict[str, Any]:
    """One deterministic signal. fragment words must come from the
    touched records (caller's contract — every builder passes titles/
    verdicts verbatim); the cap keeps the stream stream-shaped."""
    k = str(kind or "").strip()
    if k not in SIGNAL_KINDS:
        raise ValueError(
            f"signal kind must be one of {sorted(SIGNAL_KINDS)} (got {kind!r})")
    text, fragment_truncation = _bounded_fragment(fragment)
    out: Dict[str, Any] = {
        "kind": k,
        "phase": str(phase or "").strip(),
        "act": str(act or "").strip(),
        "fragment": text,
        "touched": [str(t) for t in touched if str(t or "").strip()],
    }
    if fragment_truncation:
        out["fragment_truncation"] = fragment_truncation
    felt = _felt(feelings or {}, felt_targets)
    if felt is not None:
        out["felt"] = felt
    return out


def _title_of(report_records: Dict[str, Any], rid: str) -> str:
    row = report_records.get(rid) or {}
    return str(row.get("title") or "").strip() or rid


def compose_signals(
    *,
    resolution: Optional[Dict[str, Any]] = None,
    maintenance: Optional[Dict[str, Any]] = None,
    world_models: Optional[Dict[str, Any]] = None,
    mining: Optional[Dict[str, Any]] = None,
    proposals: Sequence[Dict[str, Any]] = (),
    questions: Sequence[Dict[str, Any]] = (),
    report_records: Optional[Dict[str, Any]] = None,
    feelings: Optional[Dict[str, Any]] = None,
    top_k: int = _TOP_K_SIGNALS,
    stats: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Fold the night's phase RESULTS into the bounded signal stream —
    the acts already passed their own novelty gates (a resolution
    resolves once; a card revises only on evidence change; candidates
    are fingerprint-idempotent), so emission is novelty-keyed by
    construction (C's P0: proposals that recompute every pass emit only
    when the DREAM mints, which the dream novelty gate decides).

    Ordering is STRUCTURAL (ratified: structure decides, feelings
    color): resolutions first (the day answered the night — the
    strongest thing a night can say), then card revisions, then
    tending/mining, then tensions.

    BOUNDED BY SECTION, not one flat slice (adversary P1-3): a flat
    [:top_k] let a churn-heavy night's twelve resolutions evict every
    one of the dream's OWN tension signals — the stream then described
    everything except the dream. Each section holds reserved seats
    (resolutions 4, cards 3, tending+mining 2, tensions 3 at the
    default top_k=12); unused seats backfill in structural order, so a
    quiet-section night still fills and a loud section never starves
    the others."""
    records = report_records or {}
    sec_resolution: List[Dict[str, Any]] = []
    sec_cards: List[Dict[str, Any]] = []
    sec_tending: List[Dict[str, Any]] = []
    sec_tensions: List[Dict[str, Any]] = []

    # 1. Resolutions surfaced (changed_navigation: an open loop closing
    # re-routes waking attention — the ruling's own example: "connecting
    # an open to a resolved question would surface the resolution").
    for r in ((resolution or {}).get("resolved") or ()):
        if not r.get("closed"):
            continue  # report-only verdicts are not acts
        dream_id = str(r.get("dream_id") or "")
        mechanisms = ", ".join(str(m) for m in (r.get("mechanisms") or ()))
        sec_resolution.append(signal(
            "changed_navigation", phase="resolution", act="dream_resolved",
            fragment=(f"a standing tension settled by the day"
                      f" ({int(r.get('settled') or 0)}/{int(r.get('tensions') or 0)}"
                      f" tensions{'; ' + mechanisms if mechanisms else ''})"),
            touched=[dream_id, *[str(e) for e in (r.get("evidence_ids") or ())][:4]],
            feelings=feelings, felt_targets=[dream_id]))

    # 2. Understanding refined (changed_understanding: cards formed or
    # revised — the night regrouped what it knows).
    for v in ((world_models or {}).get("formed") or ()):
        if not v.get("formed"):
            continue
        target = str(v.get("target") or "")
        sec_cards.append(signal(
            "changed_understanding", phase="world_models",
            act=("card_revised" if int(v.get("revision") or 1) > 1 else "card_formed"),
            fragment=(f"what I know of {target.split(':', 1)[-1]} "
                      f"{'deepened' if int(v.get('revision') or 1) > 1 else 'took shape'} "
                      f"({int(v.get('source_count') or 0)} lived record(s))"),
            touched=[str(v.get("card_id") or "")],
            feelings=feelings, felt_targets=[target]))

    # 3. Tending grouped (changed_understanding: consolidation candidates
    # = the night noticing sameness). Only genuinely NEW candidates emit
    # (the fingerprint-idempotent retry sets created=False). DELIBERATE
    # felt asymmetry (adversary P2-8): tending and mining signals carry NO
    # felt block — they touch MACHINE rows (candidates), and coloring a
    # bookkeeping act with his feelings would blur whose act it was; the
    # resolution/card/tension builders color because they touch HIS
    # records and targets.
    for c in ((maintenance or {}).get("created") or ()):
        if not c.get("created"):
            continue
        cid = str(c.get("candidate_id") or "")
        sources = [str(s) for s in (c.get("source_ids") or ())]
        first = _title_of(records, sources[0]) if sources else ""
        sec_tending.append(signal(
            "changed_understanding", phase="maintenance", act="grouped",
            fragment=(f"{len(sources)} moments read as one: {first!r}" if first
                      else "several moments read as one"),
            touched=[cid, *sources[:4]] if cid else sources[:4]))

    # 3b. Offers mined (changed_understanding: a candidate is the night
    # NOTICING a pattern worth his waking word — the offer forming is the
    # act; adoption stays his). Only genuinely new mints emit.
    for c in ((mining or {}).get("created") or ()):
        if not c.get("created"):
            continue
        title = str(c.get("title") or "").strip()
        sec_tending.append(signal(
            "changed_understanding", phase="mining", act="candidate_minted",
            fragment=title or "an offer formed for waking review",
            touched=[str(c.get("candidate_id") or ""),
                     *[str(s) for s in (c.get("source_ids") or ())][:3]]))

    # 4. Standing tensions pressed (unresolved_tension: tonight's bridge
    # proposals/questions — the fragment names BOTH records verbatim,
    # laurent's blue-sky-and-happiness shape).
    for entry in (*proposals, *questions):
        pair = entry.get("pair") if isinstance(entry, dict) else None
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
            continue
        left, right = str(pair[0]), str(pair[1])
        shared = ", ".join(sorted(entry.get("shared_facets") or ())[:4])
        via = (f" (shared: {shared})" if shared
               else " (kindred by meaning)" if entry.get("vector_score") else "")
        sec_tensions.append(signal(
            "unresolved_tension", phase="dream", act="bridge_proposed",
            fragment=(f"{_title_of(records, left)!r} beside "
                      f"{_title_of(records, right)!r}{via}"),
            touched=[left, right],
            feelings=feelings, felt_targets=[left, right]))

    # Reserved seats per section, proportional to top_k (4/3/2/3 at the
    # default 12), then structural-order backfill of unused seats.
    # `stats` (optional out-param) reports what the cap COST (observer's
    # first-night finding: both live dreams saturated exactly 12 — the
    # cap was doing silent selection work; the omitted count makes it
    # visible on the record).
    k = max(0, int(top_k))
    candidates_total = (len(sec_resolution) + len(sec_cards)
                        + len(sec_tending) + len(sec_tensions))
    if stats is not None:
        stats["candidates_total"] = candidates_total
        stats["omitted"] = max(0, candidates_total - min(candidates_total, k))
    if k == 0:
        return []
    sections = [sec_resolution, sec_cards, sec_tending, sec_tensions]
    quotas = [max(1, (k * w) // 12) for w in (4, 3, 2, 3)]
    # Keep quota sum <= k (integer floors can overshoot only when k < 4;
    # trim from the front which holds the largest quota).
    while sum(quotas) > k:
        quotas[quotas.index(max(quotas))] -= 1
    out: List[Dict[str, Any]] = []
    overflow: List[Dict[str, Any]] = []
    for sec, quota in zip(sections, quotas):
        out.extend(sec[:quota])
        overflow.extend(sec[quota:])
    for extra in overflow:
        if len(out) >= k:
            break
        out.append(extra)
    # Re-assert structural order over the final stream (backfill appends
    # out of order): resolutions, cards, tending/mining, tensions.
    order = {"resolution": 0, "world_models": 1, "maintenance": 2,
             "mining": 2, "dream": 3}
    out.sort(key=lambda s0: order.get(s0["phase"], 4))
    return out[:k]
