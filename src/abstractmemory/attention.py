"""Neurotransmitter attention engine: pure activation scoring + journal writers.

Algorithm source (exact port): docs/backlog/proposed/memory_system_v1/
0018_neurotransmitter_attention_strengthen_weaken_decay.md. Consumers:
0020 (ranking tie-break via ranking_boost), 0026 (spreading reads
compute_trail_activation as associative strength), and the runtime seam
(a2a 0001/004): compute_activation fills the `base_level` slot of the
{base_level, spread, total} decomposition.

Hard contracts from 0018 (changing any of these requires an ADR revision,
not a config flip):

- ONLY kinds in ATTENTION_KINDS feed activation. Audit kinds (listed/shown/
  expanded/cited) are structurally inert: never in the rank index, never
  scored. Reading is not using — this is the fork's attention-noise failure,
  fixed by construction here.
- Activation floor is 0: silencing demotes toward invisibility in ranked
  paths; it never becomes negative relevance.
- Clamping is PER STEP, newest→oldest (fork parity, memory_control.rs:13615:
  `score = (score + contribution).clamp(0.0, MAX)` per event) — NOT one final
  clamp of the raw sum. Semantics this fixes (hostile-audit f1): excess
  negative can no longer accumulate into a "silence hole" that swallows an
  older pin, and pin overflow can no longer build invisible headroom that
  makes later silences unobservable (the silence-deadband). A silence now
  visibly demotes from the ceiling; the floor discards per-step excess.
- Distance is activity-relative rank position within the event window, NOT
  wall-clock time (no wall-clock decay in v1).
- Attention REORDERS, it never admits or excludes: ranking_boost is additive
  after admission and capped at max_boost (~12% of a 1000-point direct hit).

Purity contract: compute_activation / compute_trail_activation / ranking_boost
perform no I/O and never mutate their inputs — tests, the facade, and the
observer share this one implementation (0018 guidance). The mark_selected /
reinforce / attenuate / refocus writers are the only journal-touching code
here, and they only append (journal is append-only, 0017).

Scope note: events are pre-filtered per (scope, owner_id) stream by the
caller; there is no cross-scope activation bleed (0018 non-goal) and this
module does not re-filter by scope.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Optional, Sequence

# THE TWO-COUNT CONTRACT (maintainer's access-count model, his fork):
# every memory (and edge) carries a GLOBAL access count — absolute
# selected-use, never decays, "what matters over a lifetime" — and a
# TEMPORAL access count with decay for soft refocus. The GLOBAL count is
# the journal's selected_count / pair_selected_count. The TEMPORAL count
# is THIS MODULE's activation fold: the maintainer's "+1 on use / decay
# otherwise" shape is implemented as the rank-distance decay walk below
# (weight/(1+d/decay_window) over the activity axis). His simple +1/-1
# per-turn fold is an ALTERNATIVE FOLD SHAPE over the same journaled
# events — a tuning question (his words: "soft approximations that we may
# need to tune later"), switchable via AttentionConfig without touching
# stored data. The STRUCTURE — two counts, global never-decays + temporal
# decays — is the contract; the decay curve is not.

from .journal import (
    ATTENTION_KINDS,
    DECAY_MARKER_KINDS,
    DEFAULT_WEIGHTS,
    MemoryEvent,
    MemoryJournal,
)

__all__ = [
    "ActivationScore",
    "AttentionConfig",
    "attenuate",
    "compute_activation",
    "compute_trail_activation",
    "mark_selected",
    "ranking_boost",
    "refocus",
    "reinforce",
]

# TTL-by-activity applies to deliberate acts only (0018: "pinned/silenced with
# ttl_activity=n contribute 0 when rank_index > n"). Organic selected /
# co_selected events decay naturally and never expire outright.
_TTL_KINDS = frozenset({"pinned", "silenced"})

# Explainability cap: at most 6 per-event reason strings per record (0018
# activation_report contract). Most recent first; older detail is derivable
# from the journal itself, so truncating the *explanation* loses nothing.
_MAX_CONTRIBUTION_REASONS = 6


@dataclass(frozen=True)
class AttentionConfig:
    """Tunable constants from the 0018 math block.

    These are configuration; the surrounding semantics (rank-distance decay,
    audit inertness, floor 0, reorder-never-gate) are fixed contracts.
    Per-kind base weights deliberately live on the EVENTS (DEFAULT_WEIGHTS at
    write time, operator override via reinforce/attenuate weight), not here:
    scoring must reproduce what was journaled, not what today's config says.

    WINDOW_LIMIT — DECLARED TUNABLE (0007 saturation ruling, 2026-07-07).
    Basis: a READ-BOUND on the activity axis. The hyperbolic decay curve
    (weight/(1 + d/decay_window)) is the semantics; the window is the
    fold's WORKING SET, not a recency horizon. At the window edge (d≈500)
    an event still contributes ~4% of its weight — the window is a CLIFF,
    not a decayed-to-zero tail: a resident's record heavily used yesterday
    can read temporal-ZERO today if its events fall past the edge. The
    default 512 is SESSION-SCALE (fork parity: the fork's horizon was 500
    events, but those spanned WEEKS of sessions; resident cadence is ~1k
    events/day, so 512 ≈ half a day — the difference is event density,
    not mechanism). RESIDENT RECOMMENDATION: 24/7 homes should size
    window_limit to ~a week of MEASURED cadence (≈8192 at ~1k events/day)
    via the AttentionConfig the host passes —
    MemorySystem(attention_config=AttentionConfig(window_limit=8192)).
    The GLOBAL count never windows: the two-count model's global half
    (selected_count / pair_selected_count) is untouched by this entirely.
    DEFERRED, on record (not a rediscovery): the deeper fix is a
    count-compressed tail beyond the window (the fold sums a compressed
    per-record residual at the horizon so nothing ever cliff-drops); it
    changes fold outputs and is gated on an emergence experiment re-run —
    the maintainer's call.
    """

    window_limit: int = 512          # read-bound working set (see docstring: declared tunable)
    decay_window: float = 20.0       # rank-distance half-ish life: 1/(1+d/20)
    refocus_multiplier: float = 6.0  # distance stretch for pre-refocus events
    max_activation: float = 25.0     # per-record/per-pair clamp ceiling
    boost_scale: float = 4.0         # ranking influence = 4·activation …
    max_boost: float = 120.0         # … capped vs the 1000-point direct-hit scale
    prior_scale: float = 0.05        # cumulative prior: ln(count+1)·0.05 …
    prior_cap: float = 1.0           # … capped at 1.0 (inspection paths only)
    reason_threshold: float = 0.5    # min |contribution| to surface as a reason
    # Presence ≠ use (union model): STM-only handles committed to a context
    # deposit NO selected event by default (rendering from the trail is not
    # new evidence of use — otherwise a rendered STM member saturates and
    # becomes un-evictable). > 0 = tuning dial: STM-only commits deposit a
    # selected event with THIS weight (rehearsal), still no pair trails.
    stm_rehearsal_weight: float = 0.0


@dataclass(frozen=True)
class ActivationScore:
    """Derived (never stored) activation for one record at one point in time."""

    record_id: str
    base_level: float                # clamped [0, max_activation]
    contributions: tuple[str, ...]   # "kind +x.y" strings, most recent first


def _attention_window(
    events: Sequence[MemoryEvent],
    *,
    config: AttentionConfig,
    at_seq: Optional[int],
) -> tuple[list[MemoryEvent], Optional[int]]:
    """Build the rank window: eligible∪refocus, seq ≤ at_seq, DESC, truncated.

    Ordering of operations is load-bearing: audit kinds are dropped BEFORE
    truncation so a flood of listed/shown/expanded/cited events can never push
    eligible events out of the window (that would let reads perturb scores —
    exactly the noise failure 0018 forbids). Returns the window plus the seq
    of the LATEST in-window refocus: only that one stretches distances, and a
    refocus that already fell out of the window has no effect.
    """
    considered = [
        e
        for e in events
        if (e.kind in ATTENTION_KINDS or e.kind in DECAY_MARKER_KINDS)
        and (at_seq is None or e.seq <= at_seq)
    ]
    for e in considered:
        if e.seq < 0:
            # Determinism guard (audit f12): seq IS the rank axis. Unenriched
            # events (seq=-1) tie everywhere, making scores depend on caller
            # list ORDER — the journal always assigns seq, so this is a bug.
            raise ValueError(
                "compute_activation received an event with journal-unassigned seq "
                f"({e.kind!r}, seq={e.seq}); append events to a journal (which assigns "
                "the monotonic seq axis) before scoring them"
            )
    # seq is the journal's single monotonic as_of axis; DESC = most recent first.
    considered.sort(key=lambda e: e.seq, reverse=True)
    window = considered[: config.window_limit]

    latest_refocus_seq: Optional[int] = None
    for event in window:
        if event.kind in DECAY_MARKER_KINDS:
            latest_refocus_seq = event.seq  # first hit in DESC order = latest
            break
    return window, latest_refocus_seq


def _contribution(
    event: MemoryEvent,
    rank_index: int,
    latest_refocus_seq: Optional[int],
    *,
    config: AttentionConfig,
) -> float:
    """Signed contribution of one in-window attention event (0018 math block).

    contribution = sign · weight / (1 + distance / decay_window)

    - TTL expiry compares the RAW rank index (activity distance), not the
      refocus-stretched distance: refocus accelerates decay, it does not
      retroactively shorten a deliberate act's promised lifetime.
    - The refocus multiplier applies exactly ONCE, to events strictly older
      than the latest in-window refocus (single stretch — not compounded per
      refocus event; matches the fork).
    - qmult was REMOVED (maintainer decision, 2026-07-06): scoring treats all
      events equally regardless of query fingerprints. MemoryEvent keeps the
      query_fingerprint FIELD as pure provenance ("which query listed this").
    """
    if (
        event.kind in _TTL_KINDS
        and event.ttl_activity is not None
        and rank_index > event.ttl_activity
    ):
        return 0.0  # expired by activity distance; the record stays visible at 0

    distance = float(rank_index)
    if latest_refocus_seq is not None and event.seq < latest_refocus_seq:
        distance *= config.refocus_multiplier

    sign = -1.0 if event.kind == "silenced" else 1.0
    return sign * event.weight / (1.0 + distance / config.decay_window)


def compute_activation(
    events: Sequence[MemoryEvent],
    *,
    config: AttentionConfig = AttentionConfig(),
    at_seq: int | None = None,
    include_prior: bool = False,
    selected_counts: Mapping[str, int] | None = None,
) -> dict[str, ActivationScore]:
    """Per-record base-level activation over one scope's event stream.

    Pure function of (events, config, at_seq, prior inputs): identical
    inputs yield identical outputs, and passing at_seq=k is exactly
    equivalent to scoring the stream truncated to seq ≤ k — that
    equivalence is the deterministic-replay contract (0018 validation).

    co_selected events occupy rank slots (they are real activity on the
    shared axis) but credit NO record here: the schema gives them
    record_id=None, and their weight belongs to the pair trail
    (compute_trail_activation) that 0026's spreading consumes as associative
    strength. Crediting both the pair AND its members would double-count the
    same usage once spread is added on top of base_level.

    include_prior adds min(ln(count+1)·prior_scale, prior_cap) from
    selected_counts as ONE MORE clamped step after the event walk, so the
    base_level invariant [0, max_activation] holds unconditionally. The
    prior is for interactive inspection ranking only — never auto-recall
    (0018 fixed contract e). Records with a positive count but NO in-window
    events still get a prior-only entry: the cumulative prior exists
    precisely to keep long-used memories rankable after their events decay
    past the window. The prior is not an event, so it never appears in
    contributions.

    Events must carry journal-assigned seqs; seq<0 raises (determinism
    guard — see _attention_window).
    """
    window, latest_refocus_seq = _attention_window(events, config=config, at_seq=at_seq)

    totals: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}
    for rank_index, event in enumerate(window):
        if event.kind not in ATTENTION_KINDS:
            continue  # refocus markers hold a rank slot but carry no weight
        if event.record_id is None:
            continue  # co_selected: pair-trail credit only (see docstring)
        contribution = _contribution(event, rank_index, latest_refocus_seq, config=config)
        # PER-STEP clamp, newest→oldest (fork parity; see module docstring):
        # floor 0 discards per-step negative excess, ceiling binds per step.
        totals[event.record_id] = min(
            max(totals.get(event.record_id, 0.0) + contribution, 0.0), config.max_activation
        )

        bucket = reasons.setdefault(event.record_id, [])
        # Reasons surface per-event contributions ≥ threshold in MAGNITUDE
        # (silenced contributions are negative and must still show up as
        # "why"), most recent first because the window iterates in DESC order.
        if (
            contribution != 0.0
            and abs(contribution) >= config.reason_threshold
            and len(bucket) < _MAX_CONTRIBUTION_REASONS
        ):
            bucket.append(f"{event.kind} {contribution:+.1f}")

    def _prior(record_id: str) -> float:
        count = (selected_counts or {}).get(record_id, 0)
        return min(math.log(count + 1) * config.prior_scale, config.prior_cap)

    scores: dict[str, ActivationScore] = {}
    for record_id, total in totals.items():
        if include_prior:
            # The prior is one more clamped step on top of the event walk.
            total = min(max(total + _prior(record_id), 0.0), config.max_activation)
        scores[record_id] = ActivationScore(
            record_id=record_id,
            base_level=total,
            contributions=tuple(reasons.get(record_id, ())),
        )

    if include_prior and selected_counts:
        for record_id, count in selected_counts.items():
            if record_id in scores or count <= 0:
                continue  # count 0 == prior 0 == absence; skip the noise
            prior = min(max(_prior(record_id), 0.0), config.max_activation)
            scores[record_id] = ActivationScore(
                record_id=record_id, base_level=prior, contributions=()
            )
    return scores


def compute_trail_activation(
    events: Sequence[MemoryEvent],
    *,
    config: AttentionConfig = AttentionConfig(),
    at_seq: int | None = None,
) -> dict[tuple[str, str], float]:
    """Pair-trail activation over co_selected events ("green links").

    Same window, same rank axis, same decay/refocus math as
    compute_activation — only the aggregation key differs (canonical sorted
    pair_ids instead of record_id), so togetherness earns its own decay curve
    on the SHARED activity axis (0018 trails). No query multiplier here:
    trails feed spreading (0026), which is an auto-recall path.
    """
    window, latest_refocus_seq = _attention_window(events, config=config, at_seq=at_seq)

    totals: dict[tuple[str, str], float] = {}
    for rank_index, event in enumerate(window):
        if event.kind != "co_selected" or event.pair_ids is None:
            continue
        contribution = _contribution(event, rank_index, latest_refocus_seq, config=config)
        # PER-STEP clamp — same discipline as compute_activation ("same
        # math"), so a future negative trail kind cannot accumulate a hole.
        totals[event.pair_ids] = min(
            max(totals.get(event.pair_ids, 0.0) + contribution, 0.0), config.max_activation
        )
    return dict(totals)


def ranking_boost(base_level: float, *, config: AttentionConfig = AttentionConfig()) -> float:
    """Additive ranking influence: min(boost_scale·activation, max_boost).

    By construction ≤120 against a 1000-point exact hit (0018 decision
    boundary: silence is a nudge, closure is the removal tool). This value
    reorders admitted candidates only — it must never gate admission.
    """
    return min(config.boost_scale * base_level, config.max_boost)


# ---------------------------------------------------------------------------
# Journal-facing writers (the ONLY code here that touches a journal; append-only)
# ---------------------------------------------------------------------------


def mark_selected(
    journal: MemoryJournal,
    used_record_ids: Sequence[str],
    *,
    pairs: Sequence[tuple[str, str]],
    scope: str,
    owner_id: str,
    trace_id: str | None,
    context_ref: str | None,
    actor: str = "runtime",
    event_id_factory: Callable[[str, str], str] | None = None,
    selected_weight: float | None = None,
) -> list[MemoryEvent]:
    """Deposit the usage trail: one 'selected' per used record, one
    'co_selected' per co-use pair.

    This is the ONLY writer of selected/co_selected (0018): hosts call it
    AFTER records actually entered a context (0020 commit_selection wraps
    it). Pairs arrive precomputed by the caller (selection.plan_selection):
    since 2026-07-07 (maintainer-initiated) that means ALL pairs within the
    DEPOSITING slice — the 0018-era term-sharing restriction was the
    raw-triple mechanism, not a guard against co-use pairing; the hub guard
    is the depositing-slice rule (self/STM presence never pairs).

    trace_id lands on the event's first-class trace_id field (that is what
    the schema field exists for); context_ref travels in provenance
    {"context_ref": ...} per the seam agreement. Duplicate record ids and
    duplicate pairs (after canonical sorting) are deposited once: a record
    either entered this context or it did not — one commit is one use, and
    double-depositing would inflate the trail.

    event_id_factory(kind, key) -> event_id (a2a 0001/011 ask 2): lets the
    caller derive DETERMINISTIC event ids so at-least-once replays dedupe in
    the journal (supplied-id no-op semantics). key is the canonical identity
    of the deposit: the record_id for 'selected', "a+b" (sorted pair) for
    'co_selected' — derived AFTER schema canonicalization so caller-order
    variations of the same pair map to one id. None keeps journal-assigned
    ids (each append is a genuine new deposit).

    selected_weight overrides the 'selected' event weight (union model: STM
    rehearsal deposits are weight-scaled); None keeps the 0018 default. Pair
    trails always keep their default weight.
    """
    provenance = {"context_ref": context_ref} if context_ref is not None else {}

    def _with_identity(event: MemoryEvent, key: str) -> MemoryEvent:
        if event_id_factory is None:
            return event
        # replace() re-runs __post_init__ validation on the way in.
        return replace(event, event_id=str(event_id_factory(event.kind, key)))

    batch: list[MemoryEvent] = []
    seen_records: set[str] = set()
    for record_id in used_record_ids:
        if record_id in seen_records:
            continue
        seen_records.add(record_id)
        event = MemoryEvent(
            kind="selected",
            scope=scope,
            owner_id=owner_id,
            record_id=record_id,
            weight=DEFAULT_WEIGHTS["selected"] if selected_weight is None else float(selected_weight),
            trace_id=trace_id,
            actor=actor,
            provenance=dict(provenance),
        )
        batch.append(_with_identity(event, event.record_id or ""))

    seen_pairs: set[tuple[str, str]] = set()
    for pair in pairs:
        event = MemoryEvent(
            kind="co_selected",
            scope=scope,
            owner_id=owner_id,
            pair_ids=tuple(pair),  # schema canonicalizes (sorted, distinct)
            weight=DEFAULT_WEIGHTS["co_selected"],
            trace_id=trace_id,
            actor=actor,
            provenance=dict(provenance),
        )
        if event.pair_ids in seen_pairs:
            continue  # (a,b) and (b,a) are the same trail deposit
        seen_pairs.add(event.pair_ids)  # type: ignore[arg-type]
        batch.append(_with_identity(event, "+".join(event.pair_ids or ())))

    if not batch:
        return []
    return journal.append_events(batch)


def reinforce(
    journal: MemoryJournal,
    record_id: str,
    *,
    reason: str,
    weight: float = 8.0,
    ttl_activity: int | None = None,
    scope: str,
    owner_id: str,
    actor: str = "operator",
    event_id: str | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> MemoryEvent:
    """Deliberate strengthen (kind='pinned'). reason is mandatory — the
    journal schema rejects empty reasons and clamps weight to 1..25 (0018:
    deliberate-act strength bounds), so validation happens BEFORE any append.
    ttl_activity bounds the pin's lifetime in activity units (rank distance).
    A supplied event_id makes replays journal no-ops returning the ORIGINAL
    event (a2a 0001/015 ask 1 — at-least-once runtime effects); provenance
    rides the event untouched.
    """
    event = MemoryEvent(
        kind="pinned",
        scope=scope,
        owner_id=owner_id,
        record_id=record_id,
        weight=weight,
        ttl_activity=ttl_activity,
        reason=reason,
        actor=actor,
        event_id=str(event_id or ""),
        provenance=dict(provenance or {}),
    )
    return journal.append_events([event])[0]


def attenuate(
    journal: MemoryJournal,
    record_id: str,
    *,
    reason: str,
    weight: float = 8.0,
    ttl_activity: int | None = None,
    scope: str,
    owner_id: str,
    actor: str = "operator",
    event_id: str | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> MemoryEvent:
    """Deliberate weaken (kind='silenced'). The weight is stored positive and
    the negative sign is applied at scoring time (journal DEFAULT_WEIGHTS
    note) — silencing is a nudge toward invisibility, never negative
    relevance, and closure (0010) remains the actual removal tool.
    Supplied event_id => replay no-op returning the original (0001/015).
    """
    event = MemoryEvent(
        kind="silenced",
        scope=scope,
        owner_id=owner_id,
        record_id=record_id,
        weight=weight,
        ttl_activity=ttl_activity,
        reason=reason,
        actor=actor,
        event_id=str(event_id or ""),
        provenance=dict(provenance or {}),
    )
    return journal.append_events([event])[0]


def refocus(
    journal: MemoryJournal,
    *,
    reason: str,
    scope: str,
    owner_id: str,
    actor: str = "operator",
    event_id: str | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> MemoryEvent:
    """Topic-shift marker (kind='refocus'): accelerates decay of everything
    older than itself (distance × refocus_multiplier, applied once) while
    deleting and rewriting nothing. Carries no record_id and no weight; it
    only occupies a slot on the activity axis.
    Supplied event_id => replay no-op returning the original (0001/015).
    """
    event = MemoryEvent(
        kind="refocus",
        scope=scope,
        owner_id=owner_id,
        reason=reason,
        actor=actor,
        weight=0.0,
        event_id=str(event_id or ""),
        provenance=dict(provenance or {}),
    )
    return journal.append_events([event])[0]
