"""Retrieval channels for reconstruction (backlog 0019, v1 scope).

Three channels — exact (structured patterns + anchors), keyword (token scan
until FTS5 lands), vector (store/embedder cosine) — each returning scores
normalized 0..1 WITHIN the channel plus a human-readable detail ("why" cue).
Fusion/reserved-slot logic stays in reconstruct.py (0019 rule: fusion lives
in ONE module; backends/channels only provide primitives).

Split out of reconstruct.py to honor the <600-lines-per-file rule; this
module is internal to the reconstruction pipeline.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import AbstractSet, Any, Dict, List, Mapping, Optional, Sequence, Tuple

from . import text_tokens as _text_tokens
from .canonical_text import canonical_text
from .embedding_pin import pin_note
from .models import TripleAssertion
from .seam import RecallBudget, Stimulus
from .store import TripleQuery

# Fixed channel precedence: exact beats keyword beats vector beats
# participants wherever a fixed order is needed (cue ordering, trace channel
# sort). Encoded once. participants appended LAST deliberately: existing cue
# orders stay byte-stable, and shared-context is a co-presence signal, not a
# content match.
CHANNEL_ORDER: Tuple[str, ...] = (
    "exact", "keyword", "vector", "participants", "concept",
    # Orientation (world-model mention => instant card, 2026-07-18): a
    # named understanding admits its CURRENT card at direct-hit relevance.
    "orientation",
)

# Tokenization rules live in text_tokens.py (ONE home — the 2026-07-10
# review unified four drifting implementations); these aliases keep this
# module's established names. The 4-vs-3 floor rationale (0002 decay
# regression) is documented there.
_TOKEN_RE = _text_tokens.TOKEN_RE
_MIN_TOKEN_LEN = _text_tokens.RECALL_MIN_TOKEN_LEN
# Exclusion over-fetch headroom (audit f2): how many extra rows a bounded
# fetch may request so excluded/closed rows cannot shadow eligible ones.
# ONE policy constant — reconstruct.py and spreading.py import it (the
# review found four inline copies of the same 256).
EXCLUSION_OVERFETCH_CAP = 256
# Median baseline-estimation population floor (was an unnamed inline 5 whose
# docstring had drifted to claim 3 — the review's live example of what
# unnamed literals cost): below this many scored rows the median is the hits
# themselves, so only the absolute floor governs.
_MEDIAN_MIN_POPULATION = 5
# Keys a serialized exact pattern may carry into a TripleQuery. scope/owner_id
# come from the scope ladder (authoritative — a pattern must not escalate
# scope), query_text/query_vector belong to the vector channel, limit/order
# are budget-owned.
_EXACT_PATTERN_KEYS = frozenset({"subject", "predicate", "object", "assertion_ids", "since", "until", "active_at"})


@dataclass(frozen=True)
class ChannelResult:
    """One channel hit: score is normalized 0..1 WITHIN its channel."""

    record_id: str
    channel: str  # exact | keyword | vector
    score: float
    detail: str


def tokenize(text: str) -> List[str]:
    """Unique casefolded, accent-folded alnum tokens (len>=4 — the recall
    floor; rationale in text_tokens.py), first-seen order. Non-Latin scripts
    still produce zero tokens — the CALLER must label that degradation
    (run_keyword_channel does); FTS5 (0019) is the real fix."""
    return _text_tokens.tokenize(text, min_len=_MIN_TOKEN_LEN)


def _pattern_value_usable(value: Any) -> bool:
    """Reject values TripleQuery would normalize AWAY (empty/whitespace
    strings, empty id lists): a vanished constraint would silently turn the
    pattern into an unconstrained scope scan scored 1.0 — the exact-channel
    equivalent of `SELECT *`."""
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple)):
        return any(isinstance(x, str) and x.strip() for x in value)
    return value is not None


def _pattern_query_kwargs(pattern: Mapping[str, Any], warnings: List[str]) -> Optional[Dict[str, Any]]:
    """Sanitize one serialized pattern into TripleQuery kwargs.

    Patterns cross the seam from the runtime — boundary input. Unknown or
    ladder-owned keys are dropped loudly; an empty pattern is skipped because
    an exact cue with no constraint would mark the whole scope as an exact
    hit (score 1.0), which is not a cue.
    """
    kwargs: Dict[str, Any] = {}
    ignored: List[str] = []
    for key, value in pattern.items():
        if key in _EXACT_PATTERN_KEYS and _pattern_value_usable(value):
            kwargs[str(key)] = value
        else:
            ignored.append(str(key))
    if ignored:
        warnings.append(f"#FALLBACK: exact pattern keys ignored (scope ladder is authoritative): {sorted(ignored)}")
    if not kwargs:
        warnings.append("#FALLBACK: empty exact pattern skipped (a cue with no constraint is not a cue)")
        return None
    return kwargs


def run_exact_channel(
    store: Any,
    stimulus: Stimulus,
    scope_pairs: Sequence[Tuple[str, str]],
    budget: RecallBudget,
    excluded_ids: AbstractSet[str],
    warnings: List[str],
) -> Tuple[List[ChannelResult], Dict[str, TripleAssertion], bool]:
    """Exact channel: every stimulus pattern is a TripleQuery per scope, plus
    anchor_record_ids fetched by id. All hits score 1.0 (an exact match has
    no gradation). Returns (results, fetched assertions, channel_ran)."""
    results: List[ChannelResult] = []
    found: Dict[str, TripleAssertion] = {}
    ran = False
    limit = max(1, int(budget.max_candidates))
    # Exclusion-aware over-fetch (audit f2): closed/hidden rows consume the
    # fetch window and can fully shadow eligible rows just past it; fetch
    # extra headroom (bounded), filter, and keep at most `limit` survivors.
    fetch_limit = limit + min(len(excluded_ids), EXCLUSION_OVERFETCH_CAP)

    prepared: List[Tuple[Dict[str, Any], str]] = []
    for pattern in stimulus.patterns:
        kwargs = _pattern_query_kwargs(pattern, warnings)
        if kwargs:
            desc = ", ".join(f"{k}={kwargs[k]}" for k in sorted(kwargs))
            prepared.append((kwargs, desc))

    for kwargs, desc in prepared:
        ran = True
        for scope, owner in scope_pairs:
            try:
                rows = store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=fetch_limit, **kwargs))
            except (TypeError, ValueError) as e:
                warnings.append(f"#FALLBACK: exact pattern failed ({desc}): {e}")
                break  # a malformed pattern fails identically on every scope
            kept = 0
            for a in rows:
                if kept >= limit:
                    break
                if isinstance(a.assertion_id, str) and a.assertion_id and a.assertion_id not in excluded_ids:
                    kept += 1
                    found.setdefault(a.assertion_id, a)
                    results.append(ChannelResult(a.assertion_id, "exact", 1.0, f"exact: {desc}"))

    # Anchor record ids count as exact hits (explicit references from the
    # runtime). The scope ladder stays authoritative: anchors outside the
    # searched scopes are reported missing, never silently pulled in.
    anchors = list(stimulus.anchor_record_ids)
    max_anchors = max(0, int(budget.max_anchor_cues))
    if len(anchors) > max_anchors:
        warnings.append(f"#TRUNCATION: anchor_record_ids capped at max_anchor_cues={max_anchors} ({len(anchors)} given)")
        anchors = anchors[:max_anchors]
    usable_anchors: List[str] = []
    for rid in anchors:
        if rid in excluded_ids:
            warnings.append(f"anchor {rid} excluded by closure/visibility fold")
        else:
            usable_anchors.append(rid)
    if usable_anchors:
        ran = True
        seen_anchors: set = set()
        for scope, owner in scope_pairs:
            rows = store.query(
                TripleQuery(assertion_ids=tuple(usable_anchors), scope=scope, owner_id=owner or None, limit=len(usable_anchors))
            )
            for a in rows:
                rid = a.assertion_id
                if isinstance(rid, str) and rid and rid not in seen_anchors:
                    seen_anchors.add(rid)
                    found.setdefault(rid, a)
                    results.append(ChannelResult(rid, "exact", 1.0, f"anchor: {rid}"))
        missing = [rid for rid in usable_anchors if rid not in seen_anchors]
        if missing:
            warnings.append(f"#FALLBACK: anchor records not found in searched scopes: {missing}")

    return results, found, ran


def _store_pin_suffix(store: Any) -> str:
    """' [store pin: ...]' when the store declares an embedding pin, else
    ''. Best-effort by design: a diagnostics suffix must never turn a
    labeled degradation into a crash."""
    getter = getattr(store, "embedding_pin", None)
    if not callable(getter):
        return ""
    try:
        pin = getter()
    except Exception:
        return ""
    return f" [store pin: {pin_note(pin)}]" if pin else ""


def run_vector_channel(
    store: Any,
    stimulus: Stimulus,
    scope_pairs: Sequence[Tuple[str, str]],
    budget: RecallBudget,
    embedder: Any,
    warnings: List[str],
    *,
    excluded_ids: AbstractSet[str] = frozenset(),
    vector_floor: float = 0.05,
    vector_margin: float = 0.08,
    confidence_span: float = 0.25,
) -> Tuple[List[ChannelResult], Dict[str, TripleAssertion], bool]:
    """Vector channel. Query-vector source priority: stimulus.embedding
    (runtime precomputed) > injected embedder (pipeline embeds cue_text) >
    store-side query_text (store's own embedder). Degradations are labeled;
    an absent cue is a silent skip (nothing to search with is not a
    degradation). Excluded rows are filtered BEFORE normalization (they must
    not drive the scale) and the fetch over-provisions for them (audit f2).

    Floor (audit f3 + realistic-embedder fix): effective floor =
    max(vector_floor, median(fetched cosines) + vector_margin) when at least
    _MEDIAN_MIN_POPULATION rows scored (a median over fewer points estimates
    nothing — it is dominated by the hits themselves). Real
    embedders (qwen-class) put UNRELATED pairs at ~0.35-0.5 cosine, so an
    absolute floor alone never fires and everything channel-matches; the
    median estimates that unrelated baseline. Cosines below the effective
    floor are clipped BEFORE max-normalization; all-clipped is labeled.
    """
    query_kwargs: Dict[str, Any] = {}
    if stimulus.embedding is not None:
        query_kwargs["query_vector"] = [float(x) for x in stimulus.embedding]
    elif stimulus.cue_text and embedder is not None:
        try:
            query_kwargs["query_vector"] = [float(x) for x in embedder.embed_texts([stimulus.cue_text])[0]]
        except Exception as e:
            # ANY embed failure degrades the channel — it never kills the
            # recall. The vector channel is an enrichment (relevance admits;
            # absence is honest), and the embedder is a NETWORK CLIENT whose
            # provider stack raises its own exception types: the 2026-07-11
            # incident's `LMStudio API error (400)` subclassed neither
            # ValueError nor RuntimeError, escaped the old narrow catch, and
            # turned a misconfigured embedding route into a dead entity turn.
            # The engine cannot enumerate provider exception types (import
            # boundary forbids abstractcore), so the honest general contract
            # is: catch everything, label loudly, carry the store's pinned
            # identity (claimed-vs-served in one warning line).
            warnings.append(f"#FALLBACK: vector channel unavailable: {e}{_store_pin_suffix(store)}")
            return [], {}, False
    elif stimulus.cue_text:
        query_kwargs["query_text"] = stimulus.cue_text
    else:
        return [], {}, False

    limit = max(1, int(budget.max_candidates))
    fetch_limit = limit + min(len(excluded_ids), EXCLUSION_OVERFETCH_CAP)
    raw_scores: Dict[str, float] = {}
    found: Dict[str, TripleAssertion] = {}
    for scope, owner in scope_pairs:
        try:
            rows = store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=fetch_limit, **query_kwargs))
        except Exception as e:
            # Store cannot serve vector queries (no embedder configured, a
            # structured-only backend, or — the query_text arm — a provider
            # error from the store's OWN embedder, same network-client class
            # as above). The failure is identical for every scope: one
            # warning, channel reported as not-run, recall continues.
            warnings.append(f"#FALLBACK: vector channel unavailable: {e}{_store_pin_suffix(store)}")
            return [], {}, False
        kept = 0
        for a in rows:
            if kept >= limit:
                break
            rid = a.assertion_id
            if not (isinstance(rid, str) and rid) or rid in excluded_ids:
                continue
            retrieval = a.attributes.get("_retrieval") if isinstance(a.attributes, dict) else None
            score = retrieval.get("score") if isinstance(retrieval, dict) else None
            try:
                raw = float(score) if score is not None else None
            except (TypeError, ValueError):
                raw = None
            if raw is None:
                continue  # unscoreable row: cannot rank it honestly, skip
            kept += 1
            if rid not in raw_scores or raw > raw_scores[rid]:
                raw_scores[rid] = raw
                found[rid] = a

    # Effective floor (absolute + baseline-relative), then CONFIDENCE-SCALED
    # normalization (0002 regression fix): plain max-normalization crowned
    # the best of a WEAK field as 1.0 (empirical: a 2-row field with top
    # cosine 0.246 read relevance 1.0 and out-fused genuine matches). Vector
    # relevance must reflect ABSOLUTE confidence, not just relative rank:
    #   scale = clamp((cos_max − floor_eff) / confidence_span, 0, 1)
    #   rel_i = scale · (cos_i − floor_eff) / (cos_max − floor_eff)
    # A strong field (top well clear of the floor) still reads ≈1.0; a weak
    # field yields uniformly low vector relevance and cannot crown noise.
    floor = float(vector_floor)
    if len(raw_scores) >= _MEDIAN_MIN_POPULATION:
        # Baseline estimation needs a population: below the floor population
        # the median is dominated by the (likely relevant) hits themselves
        # and would clip legitimate recall; the absolute floor governs there.
        floor = max(floor, statistics.median(raw_scores.values()) + float(vector_margin))
    positive = {rid: s for rid, s in raw_scores.items() if s > 0.0 and s >= floor}
    results: List[ChannelResult] = []
    if positive:
        top = max(positive.values())
        span = max(float(confidence_span), 1e-9)
        scale = min(max((top - floor) / span, 0.0), 1.0)
        denominator = max(top - floor, 1e-9)
        for rid in sorted(positive):
            raw = positive[rid]
            rel = scale * (raw - floor) / denominator
            results.append(ChannelResult(rid, "vector", rel, f"vector: cosine {raw:.3f}"))
    elif raw_scores:
        warnings.append(
            f"#FALLBACK: vector channel: all {len(raw_scores)} cosines below floor {floor:.3g} "
            "— no semantic signal for this cue"
        )
    return results, found, True


def run_participants_channel(
    stimulus: Stimulus,
    candidates: Mapping[str, TripleAssertion],
    warnings: List[str],
) -> Tuple[List[ChannelResult], bool]:
    """Shared-context channel (maintainer round 5, "what do WE know / have
    lived together"): when the stimulus names participants, score candidates
    whose attributes.participants INTERSECT them —
    score = |intersection| / |stimulus.participants| (a memory shared with
    everyone present scores 1.0). Runs over the gathered UNIVERSE like the
    keyword scan (recents + channel discoveries) — v1 honesty note: records
    shared with the participants but outside the universe are not found;
    discovery-grade participant search needs an indexed attribute query
    (backlog note, same lift as keyword FTS5/0019). Doesn't run when the
    stimulus names nobody (a solo turn is not a degradation)."""
    wanted = {p for p in (stimulus.participants or ()) if str(p or "").strip()}
    if not wanted or not candidates:
        return [], False
    results: List[ChannelResult] = []
    for rid in sorted(candidates):
        attrs = candidates[rid].attributes if isinstance(candidates[rid].attributes, dict) else {}
        raw = attrs.get("participants")
        present = {str(p).strip() for p in raw if str(p or "").strip()} if isinstance(raw, (list, tuple)) else set()
        shared = wanted & present
        if not shared:
            continue
        score = len(shared) / len(wanted)
        detail = f"shared-with: {', '.join(sorted(shared))} ({len(shared)}/{len(wanted)})"
        results.append(ChannelResult(rid, "participants", score, detail))
    return results, True


def run_keyword_channel(
    cue_text: str,
    candidates: Mapping[str, TripleAssertion],
    warnings: List[str],
    *,
    store: Any = None,
    scope_pairs: Sequence[Tuple[str, str]] = (),
    discovery_limit: int = 0,
) -> Tuple[List[ChannelResult], Dict[str, TripleAssertion], bool]:
    """Keyword channel: token scan over canonical_text of the candidate
    UNIVERSE (recents + exact + vector discoveries), plus optional FTS5
    DISCOVERY (0019) — when the caller passes a store that supports keyword
    search and a positive discovery_limit, cue tokens are also searched
    against the store's index so matches OUTSIDE the gathered universe join
    as candidates (returned in the found map, exact/vector channel parity).
    Discovered rows are scored by the SAME token scan as everything else —
    one scoring rule regardless of how a candidate arrived. Discovery OFF
    (default) keeps the v1 universe re-score byte-identical, labeled.
    Runs LAST in the pipeline so channel-discovered candidates get keyword
    scores too (fairest fusion the scan offers)."""
    tokens = tokenize(cue_text)
    if not tokens:
        if str(cue_text or "").strip():
            # A non-empty cue that tokenizes to NOTHING (CJK/Cyrillic/…) is a
            # degradation, not a skip — label it (audit f6).
            warnings.append(
                "#FALLBACK: keyword channel: cue produced no indexable tokens "
                "(non-Latin scripts need FTS5/0019)"
            )
        return [], {}, False

    found: Dict[str, TripleAssertion] = {}
    discovery_ran = False
    if int(discovery_limit) > 0 and store is not None:
        if getattr(store, "supports_keyword_search", False):
            for scope, owner in scope_pairs:
                for a in store.query_keywords(
                    tokens, scope=scope, owner_id=owner or None,
                    limit=int(discovery_limit),
                ):
                    rid = a.assertion_id
                    if not rid or rid in candidates or rid in found:
                        continue
                    found[rid] = a
            discovery_ran = True
        else:
            warnings.append(
                "#FALLBACK: keyword discovery requested but the store has no "
                "FTS5 index — universe re-score only (token scan)"
            )

    scan: Dict[str, TripleAssertion] = dict(candidates)
    scan.update(found)
    if not scan:
        return [], {}, discovery_ran
    if not discovery_ran:
        warnings.append("#FALLBACK: keyword channel v1 = token scan (FTS5 lands with 0019)")
    total = len(tokens)
    results: List[ChannelResult] = []
    for rid in sorted(scan):
        cand_tokens = set(tokenize(canonical_text(scan[rid])))
        matched = [t for t in tokens if t in cand_tokens]
        if not matched:
            continue
        detail = f"keyword: matched {', '.join(matched)} ({len(matched)}/{total})"
        results.append(ChannelResult(rid, "keyword", len(matched) / total, detail))
    # Only discovered rows that actually SCORED join the found map handed to
    # admission (an FTS hit whose tokens fall below the recall floor after
    # our folding must not enter the universe unscored).
    scored = {r.record_id for r in results}
    found = {rid: a for rid, a in found.items() if rid in scored}
    return results, found, True
