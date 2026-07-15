"""Active memory reconstruction: probe() and bounded expansion (0022; fork
090/091 shape adopted wholesale per the 2026-07-12 fork comparison).

PASSIVE reconstruction (reconstruct.py) is the shelf race: identity seats,
STM continuity, activation boosts — the working set that EMERGES from use.
The cue-dilution incident proved the gap: a mind that KNOWS it is looking
for something specific cannot escape that race; its dream lost the shelf to
episodes that matched the instruction text harder, and no deliberate reach
existed.

PROBE is that reach — the entity's own "go looking" surface:

- DELIBERATE: `reason` is MANDATORY (the fork's escalation-reason
  discipline; a probe with no stated need is refused loudly). The reason
  lands on the trace (`escalation_reason`) so every deep reach is auditable.
- EXEMPT FROM THE SHELF RACE: channels only (exact/keyword/vector/
  participants + concept co-occurrence) — no identity seats, no STM union,
  NO activation boost. Ranking is relevance-pure: a probe must be able to
  find the never-used record that passive recall structurally cannot
  surface (the unconscious stratum's first real read).
- EFFORT-SIZED, the Mnemosyne vocabulary: quick / standard / deep presets
  (PROBE_EFFORTS) size candidates, hits, and expansion room by how much
  time the mind has. Hosts may pass a custom ProbeBudget; the names are
  presets, never a closed set.
- PURE READ + AUDIT TRAIL: journal=True writes a trace
  (trace_kind="probe") and inert `listed` audit events — reading is not
  using (0018). Deposits happen only if the HOST commits displayed probe
  hits through the one strengthening path (commit_selection), exactly like
  passive recall.

EXPANSION (`probe_expand`) is the second disclosure step: bounded edge
traversal from chosen hits (both edge directions), depth- and
count-bounded, honoring closure/hidden folds. It answers "show me what is
CONNECTED to this" without a second query — the fork's expand, in seam
terms. Expansion traces ride trace_kind="expand" with the parent probe's
trace id in `need`.

FAMILIARITY (`familiarity`) is the pre-answer metamemory reflex (accepted
2026-07-13): one cheap pass answering "do I hold ANY trace near this
topic, and how much?" — match DENSITY, never content. It COUNTS the same
channel pass probe() RANKS (`_channel_pass`: the recents-window gather +
exact/vector/keyword/participants admission loop) and returns a
none/weak/strong strength plus per-channel/per-scope distinct counts,
with NO record ids, digests, or titles anywhere in the result — the read
cannot be mistaken for retrieval, which is the anti-fabrication property
(a visitor claims shared history; "none" gives the mind a mechanical
reason to say "I don't remember that" instead of inventing). Alongside
density it surfaces a compact feelings summary for stimulus-relevant
gradation targets (participants or cue-matched) — "I know about X, and I
hold feelings toward it" — read from the existing valence fold; feelings
are presentation only and NEVER gate density. familiarity is a REFLEX,
not a reach: no reason required, no journal writes, no trace, no audit
events, no deposits.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .canonical_text import handle_digest, token_estimate
from .channels import (
    run_exact_channel,
    run_keyword_channel,
    run_participants_channel,
    run_vector_channel,
)
from .concept_anchor import (
    DEFAULT_CONCEPT_TUNING,
    ConceptAnchorTuning,
    concept_terms,
    expand_by_concepts,
)
from .gradation import GradationConfig, compute_gradation
from .journal import MemoryEvent, ReconstructionTrace
from .models import TripleAssertion
from .records import ReconstructConfig
from .seam import RecallBudget, Stimulus
from .store import TripleQuery

__all__ = [
    "FAMILIARITY_MIN_KEYWORD_TOKENS",
    "FAMILIARITY_STRONG_THRESHOLD",
    "FAMILIARITY_VECTOR_MIN",
    "PROBE_EFFORTS",
    "ProbeBudget",
    "ProbeHit",
    "ProbeResult",
    "familiarity",
    "probe",
    "probe_expand",
]


@dataclass(frozen=True)
class ProbeBudget:
    """Bounds for one deliberate reach. All hard; efforts are presets."""

    max_candidates: int = 128     # per-channel fetch room (wider than shelf recall)
    max_hits: int = 12            # ranked hits returned
    token_budget: int = 2400      # digest tokens across returned hits
    concept_expansion: bool = True
    concept_tuning: ConceptAnchorTuning = DEFAULT_CONCEPT_TUNING
    # Expansion defaults consumed by probe_expand when the caller passes
    # this budget through (kept here so ONE object sizes the whole reach).
    expand_depth: int = 1
    expand_max_records: int = 12
    expand_token_budget: int = 1600

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["concept_tuning"] = asdict(self.concept_tuning)
        return d


# The Mnemosyne effort vocabulary (maintainer, 2026-07-12): quick, standard,
# deep — more or less time for active reconstruction. Presets, not a closed
# set: hosts may pass any ProbeBudget.
PROBE_EFFORTS: Mapping[str, ProbeBudget] = {
    "quick": ProbeBudget(max_candidates=48, max_hits=6, token_budget=1200,
                         concept_expansion=False, expand_depth=1,
                         expand_max_records=6, expand_token_budget=800),
    "standard": ProbeBudget(),
    "deep": ProbeBudget(max_candidates=256, max_hits=20, token_budget=4000,
                        expand_depth=2, expand_max_records=24,
                        expand_token_budget=3200),
}

# familiarity() strength ladder — deterministic and CONFIGURABLE (the
# `strong_threshold` parameter, K): distinct_records == 0 -> "none",
# 1..K -> "weak", > K -> "strong". K=3 default: a single trace (or a couple)
# is acquaintance, not command of a topic — more than three independent
# admitted records is enough density to answer from memory rather than
# hedge. A named module constant, never a literal buried in the fold.
FAMILIARITY_STRONG_THRESHOLD = 3

# Presentation bound for the familiarity feelings summary (compact by
# contract — a reflex must stay cheap to render). Callers widen/narrow via
# the `max_feelings` parameter.
FAMILIARITY_MAX_FEELINGS = 8

# DENSITY-HONEST admission floors (live A/B finding, 2026-07-13): probe's
# channel floors are RANKING-relative — the vector floor admits the top of
# ANY field (measured: gibberish cues admitted rows at cosine 0.31/0.27
# with a real qwen3 embedder), and one incidental keyword token ("office",
# "from") channel-matches — so "none" was unreachable on a lived home and
# the anti-fabrication signal could never fire. Familiarity therefore
# counts an admission toward DENSITY only above absolute confidence bars;
# probe()'s ranking behavior is untouched (these floors exist only in the
# counting fold). Exact anchors and door-stamped participants always count
# (identity-grade signals). Both bars are parameters; the defaults are
# calibrated against the measured gibberish baseline (~0.31) vs on-topic
# matches (>0.55) for qwen3-class embedders.
FAMILIARITY_VECTOR_MIN = 0.45
FAMILIARITY_MIN_KEYWORD_TOKENS = 2


@dataclass(frozen=True)
class ProbeHit:
    """One ranked probe hit — digest currency, provenance-honest.

    TWO ID NAMESPACES, both carried (the observer's join lesson):
    `record_id` is the digest ROW id (the trace/commit currency — matches
    reconstruct handles and commit_selection); `graph_id` is the record's
    graph subject (the edge/expansion currency)."""

    record_id: str
    graph_id: str
    title: str
    digest: str
    scope: str
    owner_id: str
    kind: str
    relevance: Dict[str, float] = field(default_factory=dict)
    cues: Tuple[str, ...] = ()
    token_estimate: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProbeResult:
    trace_id: str
    as_of_seq: int
    hits: Tuple[ProbeHit, ...]
    dropped: Tuple[Dict[str, Any], ...]
    channels: Tuple[str, ...]
    warnings: Tuple[str, ...]
    budget_spent: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "as_of_seq": self.as_of_seq,
            "hits": [h.to_dict() for h in self.hits],
            "dropped": list(self.dropped),
            "channels": list(self.channels),
            "warnings": list(self.warnings),
            "budget_spent": dict(self.budget_spent),
        }


def _require_reason(reason: Optional[str]) -> str:
    text = str(reason or "").strip()
    if not text:
        raise ValueError(
            "probe requires a non-empty reason — the deliberate reach is an "
            "audited act (fork 090 escalation discipline): say what you are "
            "looking for and why passive recall was not enough")
    return text


def _resolve_budget(effort: Any) -> ProbeBudget:
    if isinstance(effort, ProbeBudget):
        return effort
    name = str(effort or "standard").strip().lower()
    if name not in PROBE_EFFORTS:
        raise ValueError(
            f"unknown probe effort {name!r} (presets: {sorted(PROBE_EFFORTS)}; "
            "or pass a ProbeBudget for a custom reach)")
    return PROBE_EFFORTS[name]


def _kind_of(a: TripleAssertion, config: ReconstructConfig) -> str:
    return config.kind_of(a)


def _admit_candidate(
    universe: Dict[str, TripleAssertion],
    relevance: Dict[str, Dict[str, float]],
    cues: Dict[str, List[str]],
    excluded: Set[str],
    rid: str,
    a: TripleAssertion,
    channel: str,
    score: float,
    detail: str,
) -> None:
    """One admission into the candidate universe (shared by the channel
    pass and probe's concept expansion). Universe key = ASSERTION id (the
    trace/commit currency — same as the reconstruction pipeline);
    exclusion folds live in that namespace too."""
    if not (isinstance(rid, str) and rid) or rid in excluded:
        return
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    if attrs.get("record_edge") or attrs.get("bookkeeping"):
        return
    universe.setdefault(rid, a)
    rel = relevance.setdefault(rid, {})
    rel[channel] = max(rel.get(channel, 0.0), float(score))
    bucket = cues.setdefault(rid, [])
    line = detail if detail else channel
    if line not in bucket:
        bucket.append(line)


@dataclass
class _ChannelPass:
    """Everything one channel pass produced. probe() RANKS this; familiarity()
    COUNTS it — one pass, two readings."""

    universe: Dict[str, TripleAssertion]
    relevance: Dict[str, Dict[str, float]]
    cues: Dict[str, List[str]]
    channels_run: List[str]
    warnings: List[str]


def _channel_pass(
    store: Any,
    *,
    stimulus: Stimulus,
    scope_pairs: Sequence[Tuple[str, str]],
    max_candidates: int,
    excluded: Set[str],
    embedder: Any,
    config: ReconstructConfig,
) -> _ChannelPass:
    """The store-facing candidate pass probe() and familiarity() share: the
    recents-window gather + exact/vector/keyword/participants admission
    loop. Pure read; relevance only (no activation, no seats, no STM).
    Extracted verbatim from probe() — its behavior is pinned by the probe
    suite and must stay byte-identical for that caller."""
    warnings: List[str] = []
    # RecallBudget carries the per-channel fetch bound the channel runners
    # read (max_candidates); the rest of the shelf budget is irrelevant to
    # a probe and deliberately unused.
    channel_budget = RecallBudget(max_candidates=int(max_candidates))

    universe: Dict[str, TripleAssertion] = {}
    relevance: Dict[str, Dict[str, float]] = {}
    cues: Dict[str, List[str]] = {}
    channels_run: List[str] = []

    def _admit(rid: str, a: TripleAssertion, channel: str, score: float, detail: str) -> None:
        _admit_candidate(universe, relevance, cues, excluded, rid, a, channel, score, detail)

    # --- candidate gathering (recents per scope, the pipeline's baseline
    # source — keyword/participants scan a UNIVERSE, not the store) --------
    cap = int(max_candidates)
    gathered: Dict[str, TripleAssertion] = {}
    window_saturated: List[str] = []
    for scope, owner in scope_pairs:
        kept = 0
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=cap)):
            rid = a.assertion_id
            if not (isinstance(rid, str) and rid) or rid in excluded or rid in gathered:
                continue
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_edge") or attrs.get("bookkeeping"):
                continue
            gathered[rid] = a
            kept += 1
            if kept >= cap:
                window_saturated.append(scope)
                break
    if window_saturated:
        # Honest reach label (adversary F6): the keyword/participants/
        # concept scans cover the newest window only — an OLD vectorless
        # keyword-only record is beyond them at any effort. Exact anchors
        # and vector search still reach the whole store; FTS5 (0019) is
        # the standing fix for whole-store lexical reach.
        warnings.append(
            f"probe window saturated in scope(s) {sorted(set(window_saturated))}: "
            f"keyword/concept scans cover the newest {cap} records per scope — "
            "older records are reachable via exact anchors or vector search only "
            "(deep effort widens the window; FTS5/0019 lifts it)")

    # --- store-facing channels (relevance only; no activation, no seats) --
    exact_results, exact_found, exact_ran = run_exact_channel(
        store, stimulus, scope_pairs, channel_budget, excluded, warnings)
    if exact_ran:
        channels_run.append("exact")
    for r in exact_results:
        a = exact_found.get(r.record_id)
        if a is not None:
            _admit(r.record_id, a, "exact", r.score, r.detail)

    vec_results, vec_found, vec_ran = run_vector_channel(
        store, stimulus, scope_pairs, channel_budget, embedder, warnings,
        excluded_ids=excluded,
        vector_floor=config.vector_floor, vector_margin=config.vector_margin,
        confidence_span=config.confidence_span)
    if vec_ran:
        channels_run.append("vector")
    for r in vec_results:
        a = vec_found.get(r.record_id)
        if a is not None:
            _admit(r.record_id, a, "vector", r.score, r.detail)

    # --- universe-facing channels (recents + discoveries) ------------------
    scan_universe: Dict[str, TripleAssertion] = dict(gathered)
    scan_universe.update(universe)
    kw_results, kw_ran = run_keyword_channel(stimulus.cue_text, scan_universe, warnings)
    if kw_ran:
        channels_run.append("keyword")
    for r in kw_results:
        a = scan_universe.get(r.record_id)
        if a is not None:
            _admit(r.record_id, a, "keyword", r.score, r.detail)

    part_results, part_ran = run_participants_channel(stimulus, scan_universe, warnings)
    if part_ran:
        channels_run.append("participants")
    for r in part_results:
        a = scan_universe.get(r.record_id)
        if a is not None:
            _admit(r.record_id, a, "participants", r.score, r.detail)

    return _ChannelPass(universe=universe, relevance=relevance, cues=cues,
                        channels_run=channels_run, warnings=warnings)


def probe(
    store: Any,
    journal: Any,
    *,
    stimulus: Stimulus,
    scopes: Sequence[Tuple[str, str]],
    reason: str,
    effort: Any = "standard",
    embedder: Any = None,
    excluded_ids: Optional[Set[str]] = None,
    config: ReconstructConfig = ReconstructConfig(),
    as_of_seq: int = 0,
    trace_id: Optional[str] = None,
    write_journal: bool = True,
) -> ProbeResult:
    """One deliberate reach. Pure read over the store; journal writes are
    the trace + inert audit events (write_journal=False writes nothing).

    The caller (facade) owns fold assembly: `excluded_ids` must already
    carry closure/hidden exclusions and `as_of_seq` the replay anchor —
    the same division of labor as run_reconstruction."""
    reason_text = _require_reason(reason)
    budget = _resolve_budget(effort)
    excluded = set(excluded_ids or ())
    scope_pairs = [(str(s or "").strip().lower(), str(o or "").strip())
                   for s, o in (scopes or ()) if str(s or "").strip()]
    if not scope_pairs:
        raise ValueError("probe requires at least one (scope, owner_id) pair")
    tid = (trace_id.strip() if isinstance(trace_id, str) and trace_id.strip()
           else uuid.uuid4().hex)

    # The shared channel pass (also familiarity's counting substrate).
    cpass = _channel_pass(
        store, stimulus=stimulus, scope_pairs=scope_pairs,
        max_candidates=int(budget.max_candidates), excluded=excluded,
        embedder=embedder, config=config)
    universe = cpass.universe
    relevance = cpass.relevance
    cues = cpass.cues
    channels_run = cpass.channels_run
    warnings = cpass.warnings

    # --- concept co-occurrence expansion (probe default ON) ---------------
    if budget.concept_expansion and universe:
        seeds = dict(universe)
        admissions, notes = expand_by_concepts(
            store, seeds, scope_pairs, excluded_ids=excluded,
            tuning=budget.concept_tuning)
        if admissions:
            channels_run.append("concept")
        warnings.extend(notes)
        for adm in admissions:
            _admit_candidate(universe, relevance, cues, excluded,
                             adm["record_id"], adm["assertion"], "concept",
                             adm["score"],
                             "shared concepts: " + ", ".join(adm["concepts"][:6]))

    # --- relevance-pure ranking -------------------------------------------
    def fused(rid: str) -> float:
        return sum(relevance.get(rid, {}).values())

    ordered = sorted(universe.keys())
    ordered.sort(key=lambda rid: (universe[rid].observed_at or ""), reverse=True)
    ordered.sort(key=lambda rid: config.rank_of(_kind_of(universe[rid], config)))
    ordered.sort(key=fused, reverse=True)

    hits: List[ProbeHit] = []
    dropped: List[Dict[str, Any]] = []
    tokens_used = 0
    for rid in ordered:
        if len(hits) >= int(budget.max_hits):
            dropped.append({"record_id": rid, "score": fused(rid), "reason": "over_max_hits"})
            continue
        a = universe[rid]
        digest = handle_digest(a)
        cost = token_estimate(digest)
        if tokens_used + cost > int(budget.token_budget) and hits:
            dropped.append({"record_id": rid, "score": fused(rid), "reason": "token_budget"})
            continue
        tokens_used += cost
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        hits.append(ProbeHit(
            record_id=rid,
            graph_id=str(a.subject or ""),
            title=str(attrs.get("title") or ""),
            digest=digest,
            scope=a.scope,
            owner_id=a.owner_id or "",
            kind=_kind_of(a, config),
            relevance=dict(relevance.get(rid, {})),
            cues=tuple(cues.get(rid, ())),
            token_estimate=cost,
        ))

    budget_spent = {
        "candidates_considered": len(universe),
        "hits": len(hits),
        "tokens_used": tokens_used,
        "token_budget": int(budget.token_budget),
        "effort": effort if isinstance(effort, str) else "custom",
    }

    trace = ReconstructionTrace(
        trace_id=tid,
        trace_kind="probe",
        query_fingerprint="probe",
        need={**stimulus.to_dict(), "probe_reason": reason_text},
        searched_scopes=tuple({"scope": s, "owner_id": o} for s, o in scope_pairs),
        escalation_reason=reason_text,
        channels=tuple(channels_run),
        candidates=tuple(
            {"record_id": rid, "scores": dict(relevance.get(rid, {}))}
            for rid in ordered[:64]),
        selected=tuple(h.record_id for h in hits),
        dropped=tuple(dropped),
        cues=tuple(line for h in hits for line in h.cues),
        budgets=budget.to_dict(),
        budget_spent=dict(budget_spent),
        stop_reason="enough" if hits else "no_candidates",
        warnings=tuple(dict.fromkeys(warnings)),
        admissions={h.record_id: "stimulus" for h in hits},
    )
    if write_journal:
        journal.append_trace(trace)
        listed = [
            MemoryEvent(
                kind="listed", scope=h.scope, owner_id=h.owner_id,
                record_id=h.record_id, trace_id=tid, actor="system",
                provenance={"probe": True, **({"turn_id": stimulus.turn_id} if stimulus.turn_id else {})},
                # Replay-safe when the caller supplied the trace id
                # (adversary F8): a re-probe with a pinned trace_id
                # dedupes its audit events at the journal.
                event_id=(f"{tid}-listed-{h.record_id}" if trace_id else ""),
            )
            for h in hits
        ]
        if listed:
            journal.append_events(listed)

    return ProbeResult(
        trace_id=tid,
        as_of_seq=int(as_of_seq),
        hits=tuple(hits),
        dropped=tuple(dropped),
        channels=tuple(channels_run),
        warnings=tuple(dict.fromkeys(warnings)),
        budget_spent=budget_spent,
    )


# Warning texts the familiarity contract pins verbatim (tests assert these
# exact strings — honesty behaviors, not decoration).
_FAMILIARITY_NONE_WARNING = (
    "nothing within reach (newest-window scan; exact/vector reach whole store)")
_FAMILIARITY_VECTORLESS_WARNING = "#FALLBACK: keyword-only familiarity"

# Channel-detail formats are engine-pinned (channels.py writes them; channel
# tests assert them) — familiarity parses its OWN wire, never guesses.
_VECTOR_DETAIL_RE = re.compile(r"^vector: cosine ([0-9.]+)")
_KEYWORD_DETAIL_RE = re.compile(r"^keyword: matched .+ \((\d+)/\d+\)$")


def _familiarity_counts(
    cpass: "_ChannelPass",
    scope_pairs: Sequence[Tuple[str, str]],
    *,
    vector_min: float,
    min_keyword_tokens: int,
    warnings: List[str],
) -> Tuple[int, Dict[str, int], Dict[str, int]]:
    """The density fold with ABSOLUTE confidence bars (module constants'
    rationale above). Per admitted row, a channel admission COUNTS iff:
    exact/participants — always (identity-grade); vector — raw cosine
    (parsed from the channel's own pinned detail string) >= vector_min;
    keyword — matched-token count >= min_keyword_tokens. A detail string
    that fails to parse COUNTS (fail-open + label): of the two failure
    modes, over-counting reads "weak" where "none" was true, while
    silent strictness would fabricate "none" — and a false "I don't
    remember" is the exact harm this reflex exists to prevent.

    Returns (distinct, per_channel, by_scope) over COUNTING admissions;
    appends the weaker-echo honesty label when the bars dropped rows."""
    per_channel: Dict[str, int] = {ch: 0 for ch in cpass.channels_run}
    by_scope: Dict[str, int] = {scope: 0 for scope, _ in scope_pairs}
    vector_ran = "vector" in cpass.channels_run
    distinct = 0
    dropped = 0
    parse_failures = 0
    for rid, rel in cpass.relevance.items():
        details = cpass.cues.get(rid, ())
        counting: List[str] = []
        vector_counted = False
        # Vector decided FIRST: the keyword single-token rule below reads it.
        if "vector" in rel:
            m = next((_VECTOR_DETAIL_RE.match(d) for d in details
                      if d.startswith("vector:")), None)
            if m is None:
                parse_failures += 1
                vector_counted = True
            elif float(m.group(1)) >= float(vector_min):
                vector_counted = True
            if vector_counted:
                counting.append("vector")
        for ch in rel:
            if ch == "vector":
                continue  # decided above
            if ch in ("exact", "participants"):
                counting.append(ch)
                continue
            if ch == "keyword":
                m = next((_KEYWORD_DETAIL_RE.match(d) for d in details
                          if d.startswith("keyword:")), None)
                if m is None:
                    parse_failures += 1
                    counting.append(ch)
                    continue
                matched = int(m.group(1))
                if matched >= int(min_keyword_tokens):
                    counting.append(ch)
                elif matched >= 1 and (not vector_ran or vector_counted):
                    # CORROBORATION-OR-EXCLUSIVITY (live A/B calibration):
                    # a single-token lexical match is honest familiarity
                    # when keywords are the only channel a home HAS
                    # (vectorless — already labeled #FALLBACK), or when
                    # the semantic channel corroborates the row; but when
                    # the vector channel RAN and rejected this row, one
                    # incidental token ("office", "from") must not read
                    # as knowing the topic — that is exactly how "none"
                    # was unreachable on the lived home.
                    counting.append(ch)
                continue
            counting.append(ch)  # unknown future channel: fail-open
        if counting:
            distinct += 1
            a = cpass.universe.get(rid)
            if a is not None:
                by_scope[a.scope] = by_scope.get(a.scope, 0) + 1
            for ch in counting:
                per_channel[ch] = per_channel.get(ch, 0) + 1
        else:
            dropped += 1
    if dropped:
        warnings.append(
            f"familiarity counts high-confidence matches only (vector cosine >= "
            f"{float(vector_min):g}; >= {int(min_keyword_tokens)} matched keywords) — "
            f"{dropped} weaker echo(es) not counted; recall may still surface them")
    if parse_failures:
        warnings.append(
            f"#FALLBACK: {parse_failures} channel detail(s) unparseable — counted "
            "fail-open (a silent strict read could fabricate 'none')")
    return distinct, per_channel, by_scope


def _stimulus_feelings(
    store: Any,
    journal: Any,
    stimulus: Stimulus,
    scope_pairs: Sequence[Tuple[str, str]],
    *,
    gradation_config: GradationConfig,
    as_of_seq: Optional[int],
    max_feelings: int,
    warnings: List[str],
) -> List[Dict[str, Any]]:
    """Compact standing-feelings summary for STIMULUS-RELEVANT gradation
    targets (the maintainer's "complementary, wouldn't cost more" note):
    fold the searched pairs' valence streams once (the existing gradation
    fold — no new machinery) and keep targets that are either named
    participants or whose NAME part (after the "namespace:" prefix)
    shares a concept term with the cue text.

    Presentation info ONLY — never consulted by the density count (valence
    never gates, ruled). Targets that resolve to STORED RECORDS are skipped
    silently: a record id in the output would break the no-content property
    (record-targeted feelings belong to record-rendering surfaces, not to a
    density reflex). No journal -> empty, labeled."""
    if journal is None:
        warnings.append(
            "#FALLBACK: feelings skipped (no journal available; gradation "
            "reads the valence stream)")
        return []
    from .records import resolve_digest_assertion

    # One fold per searched pair, merged narrow-first (the caller passes
    # scopes narrow->broad; the narrowest scope's standing wins on
    # conflict — the same tie rule as the activation merge in folds.py).
    merged: Dict[str, Any] = {}
    for scope, owner in scope_pairs:
        events = journal.valence_events(
            scope=scope, owner_id=owner, until_seq=as_of_seq, limit=0)
        if not events:
            continue
        for target, score in compute_gradation(events, config=gradation_config).items():
            merged.setdefault(target, score)

    participants = set(stimulus.participants)
    cue_terms = set(concept_terms(stimulus.cue_text))
    out: List[Dict[str, Any]] = []
    for target in sorted(merged):
        if target in participants:
            matched = True
        else:
            # Gradation targets are "namespace:name" free strings (open
            # vocabulary); the namespace is a category label, not a topic
            # word — match the NAME part only, with the identifier-aware
            # concept tokenizer ("tool:web_search" matches "web search").
            name = target.split(":", 1)[1] if ":" in target else target
            matched = bool(set(concept_terms(name)) & cue_terms)
        if not matched:
            continue
        if resolve_digest_assertion(store, target) is not None:
            continue  # record-targeted feeling: never leak a record id
        score = merged[target]
        standing = ("scar+bond" if score.scarred and score.bonded
                    else "scar" if score.scarred
                    else "bond" if score.bonded
                    else "none")
        out.append({"target": target, "net": float(score.net), "standing": standing})
    # Strongest feelings first (|net| desc), deterministic tie-break.
    out.sort(key=lambda f: (-abs(f["net"]), f["target"]))
    return out[: max(0, int(max_feelings))]


def familiarity(
    store: Any,
    *,
    stimulus: Stimulus,
    scopes: Sequence[Tuple[str, str]],
    effort: Any = "quick",
    embedder: Any = None,
    excluded_ids: Optional[Set[str]] = None,
    config: ReconstructConfig = ReconstructConfig(),
    journal: Any = None,
    gradation_config: GradationConfig = GradationConfig(),
    as_of_seq: Optional[int] = None,
    strong_threshold: int = FAMILIARITY_STRONG_THRESHOLD,
    max_feelings: int = FAMILIARITY_MAX_FEELINGS,
    vector_min: float = FAMILIARITY_VECTOR_MIN,
    min_keyword_tokens: int = FAMILIARITY_MIN_KEYWORD_TOKENS,
) -> Dict[str, Any]:
    """Pre-answer metamemory: "do I hold ANY trace near this topic, and how
    much?" — match DENSITY, never content (module docstring: the
    anti-fabrication reflex).

    Runs the SAME channel pass probe() ranks (`_channel_pass`: recents
    gather + exact/vector/keyword/participants) and counts it. No concept
    expansion at any effort — expansion serves ranking, and a density
    reflex stays one pass. `effort` sizes only the candidate window
    (quick/standard/deep presets or a custom ProbeBudget).

    Returns a plain dict (no record ids, digests, or titles anywhere):
    - strength: "none" (0) | "weak" (1..strong_threshold) | "strong"
      (> strong_threshold; K is the documented, configurable parameter —
      default FAMILIARITY_STRONG_THRESHOLD = 3);
    - distinct_records: distinct admitted candidate rows across channels;
    - per_channel: {channel: distinct count} for every channel that RAN
      (0 means "ran, matched nothing"; absent means "did not run");
    - by_scope: {scope: distinct count} over admitted rows — every
      searched scope reported, zero included ("nothing in scope X" is a
      statement this reflex exists to make); counts fold across owners
      sharing a scope name (the ladder convention keeps scope names
      unique per call);
    - feelings: compact standing summary for stimulus-relevant gradation
      targets ({target, net, standing}) — presentation only, requires
      `journal` (skipped + labeled without one), NEVER gates density;
    - warnings: honesty labels. Pinned behaviors: strength "none" carries
      "nothing within reach (newest-window scan; exact/vector reach whole
      store)" (keyword/participant scans cover only the newest candidate
      window per scope); a semantic cue that could not vector-search
      (no embedder / store refuses vectors) carries
      "#FALLBACK: keyword-only familiarity".

    PURE READ, structurally: no trace, no audit events, no deposits — the
    only journal touch is the read-only valence fold for feelings. The
    caller (facade) owns fold assembly: `excluded_ids` carries closure/
    hidden exclusions, `as_of_seq` anchors the feelings read — the same
    division of labor as probe()."""
    if int(strong_threshold) < 1:
        raise ValueError(
            f"strong_threshold must be >= 1 (got {strong_threshold!r}) — with K=strong_threshold "
            "the ladder is none=0, weak=1..K, strong>K")
    budget = _resolve_budget(effort)
    excluded = set(excluded_ids or ())
    scope_pairs = [(str(s or "").strip().lower(), str(o or "").strip())
                   for s, o in (scopes or ()) if str(s or "").strip()]
    if not scope_pairs:
        raise ValueError("familiarity requires at least one (scope, owner_id) pair")

    cpass = _channel_pass(
        store, stimulus=stimulus, scope_pairs=scope_pairs,
        max_candidates=int(budget.max_candidates), excluded=excluded,
        embedder=embedder, config=config)
    warnings = list(cpass.warnings)

    # COUNT the pass (density, never content) — with the ABSOLUTE
    # confidence bars (FAMILIARITY_VECTOR_MIN / _MIN_KEYWORD_TOKENS
    # rationale above: ranking-relative floors made "none" unreachable on
    # a lived home). Every searched scope is REPORTED, zero included:
    # "nothing in scope X" is exactly the statement the anti-fabrication
    # reflex exists to make.
    distinct, per_channel, by_scope = _familiarity_counts(
        cpass, scope_pairs,
        vector_min=vector_min, min_keyword_tokens=min_keyword_tokens,
        warnings=warnings)

    if int(strong_threshold) < distinct:
        strength = "strong"
    elif distinct > 0:
        strength = "weak"
    else:
        strength = "none"

    # Honesty rules (contract text, verbatim strings pinned by tests).
    had_semantic_cue = bool(stimulus.cue_text) or stimulus.embedding is not None
    if had_semantic_cue and "vector" not in cpass.channels_run:
        warnings.append(_FAMILIARITY_VECTORLESS_WARNING)
    if strength == "none":
        warnings.append(_FAMILIARITY_NONE_WARNING)

    feelings = _stimulus_feelings(
        store, journal, stimulus, scope_pairs,
        gradation_config=gradation_config, as_of_seq=as_of_seq,
        max_feelings=max_feelings, warnings=warnings)

    return {
        "strength": strength,
        "distinct_records": distinct,
        "per_channel": per_channel,
        "by_scope": by_scope,
        "feelings": feelings,
        "warnings": list(dict.fromkeys(warnings)),
    }


def probe_expand(
    store: Any,
    journal: Any,
    *,
    record_ids: Sequence[str],
    reason: str,
    depth: int = 1,
    max_records: int = 12,
    token_budget: int = 1600,
    excluded_ids: Optional[Set[str]] = None,
    scope_pairs: Sequence[Tuple[str, str]] = (),
    parent_trace_id: Optional[str] = None,
    as_of_seq: int = 0,
    trace_id: Optional[str] = None,
    write_journal: bool = True,
    edge_limit_per_node: int = 64,
) -> ProbeResult:
    """Bounded source expansion from chosen records: BFS over record edges
    in BOTH directions (what this record points at; what points at it),
    depth/count/token bounded, closure/hidden folds honored via
    excluded_ids, scope-contained when scope_pairs are given. Root ids
    resolve through BOTH namespaces (row ids from probe hits AND graph ids
    from edges — the works-or-loud rule); unknown roots refuse loudly.
    Ranking: records reached by MORE distinct edges rank first (connection
    count), ties on graph id. Deposits nothing; the trace
    (trace_kind="expand") records the walk and the parent probe."""
    from .records import resolve_digest_assertion

    reason_text = _require_reason(reason)
    raw_roots = [str(r or "").strip() for r in (record_ids or ()) if str(r or "").strip()]
    if not raw_roots:
        raise ValueError("probe_expand requires at least one record id to expand from")
    if int(depth) < 1:
        raise ValueError(f"depth must be >= 1, got {depth}")
    excluded = set(excluded_ids or ())
    allowed_scopes = {(str(s).strip().lower(), str(o).strip())
                      for s, o in (scope_pairs or ())}
    tid = (trace_id.strip() if isinstance(trace_id, str) and trace_id.strip()
           else uuid.uuid4().hex)

    # ROOT RESOLUTION (works-or-loud, adversary F1): accept row ids AND
    # graph ids; an id that resolves to nothing is a loud error, never a
    # silent zero-hit walk.
    roots: List[str] = []
    for rid in raw_roots:
        digest = resolve_digest_assertion(store, rid)
        if digest is None:
            raise ValueError(
                f"probe_expand: {rid!r} resolves to no record in either id "
                "namespace (row id or graph id) — expansion roots must be "
                "formed records")
        gid = str(digest.subject or rid)
        if gid not in roots:
            roots.append(gid)

    # The walk is bounded THREE ways: depth, per-node edge budget, and a
    # discovery cap derived from the output bound (a hub node must not
    # trigger O(degree) unbounded scans — adversary F5).
    discovery_cap = max(int(max_records) * 4, int(max_records) + len(roots))
    per_node = max(1, int(edge_limit_per_node))
    seen: Set[str] = set(roots)
    frontier: List[str] = list(roots)
    found: Dict[str, TripleAssertion] = {}          # graph_id -> digest assertion
    connections: Dict[str, List[str]] = {}          # graph_id -> distinct edge cues
    edges_walked = 0

    def _note_connection(gid: str, cue: str) -> None:
        bucket = connections.setdefault(gid, [])
        if cue not in bucket:
            bucket.append(cue)

    for _level in range(int(depth)):
        next_frontier: List[str] = []
        for rid in sorted(frontier):
            for a in store.query(TripleQuery(subject=rid, limit=per_node)):
                attrs = a.attributes if isinstance(a.attributes, dict) else {}
                if not attrs.get("record_edge") or (a.assertion_id and a.assertion_id in excluded):
                    continue
                target = str(a.object or "")
                if not target:
                    continue
                edges_walked += 1
                _note_connection(target, f"via {a.predicate} from {rid}")
                if target not in seen and len(seen) < discovery_cap:
                    seen.add(target)
                    next_frontier.append(target)
            for a in store.query(TripleQuery(object=rid, limit=per_node)):
                attrs = a.attributes if isinstance(a.attributes, dict) else {}
                if not attrs.get("record_edge") or (a.assertion_id and a.assertion_id in excluded):
                    continue
                source = str(a.subject or "")
                if not source:
                    continue
                edges_walked += 1
                _note_connection(source, f"cited by {a.predicate} from {rid}")
                if source not in seen and len(seen) < discovery_cap:
                    seen.add(source)
                    next_frontier.append(source)
        if not next_frontier:
            break
        # Fetch digest rows for the new frontier; closed digests never
        # join, and scope containment applies when the caller named scopes
        # (adversary F4: cross-scope edges must not pull foreign digests).
        for target in next_frontier:
            if target in found or target in roots:
                continue
            rows = store.query(TripleQuery(
                subject=target, predicate="dcterms:abstract", limit=1))
            if not rows:
                continue
            row = rows[0]
            if row.assertion_id and row.assertion_id in excluded:
                continue
            if allowed_scopes and (row.scope, row.owner_id or "") not in allowed_scopes:
                continue
            found[target] = row
        frontier = next_frontier

    config = ReconstructConfig()
    # MORE connections rank FIRST (adversary F7: the old ascending-length
    # key ranked the least-connected strangers ahead of direct neighbors,
    # and single-append paths made every count 1).
    ordered = sorted(found.keys(),
                     key=lambda gid: (-len(connections.get(gid, ())), gid))
    hits: List[ProbeHit] = []
    dropped: List[Dict[str, Any]] = []
    tokens_used = 0
    for gid in ordered:
        a = found[gid]
        row_id = str(a.assertion_id or gid)
        score = float(len(connections.get(gid, ())))
        if len(hits) >= int(max_records):
            dropped.append({"record_id": row_id, "graph_id": gid,
                            "score": score, "reason": "over_max_records"})
            continue
        digest = handle_digest(a)
        cost = token_estimate(digest)
        if tokens_used + cost > int(token_budget) and hits:
            dropped.append({"record_id": row_id, "graph_id": gid,
                            "score": score, "reason": "token_budget"})
            continue
        tokens_used += cost
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        hits.append(ProbeHit(
            record_id=row_id,
            graph_id=gid,
            title=str(attrs.get("title") or ""),
            digest=digest,
            scope=a.scope,
            owner_id=a.owner_id or "",
            kind=config.kind_of(a),
            relevance={"connections": score},
            cues=tuple(connections.get(gid, ())),
            token_estimate=cost,
        ))

    budget_spent = {
        "roots": len(roots), "depth": int(depth),
        "edges_walked": edges_walked, "hits": len(hits),
        "tokens_used": tokens_used, "token_budget": int(token_budget),
    }
    trace = ReconstructionTrace(
        trace_id=tid,
        trace_kind="expand",
        query_fingerprint="expand",
        need={"expand_from": roots, "parent_trace_id": parent_trace_id,
              "probe_reason": reason_text},
        searched_scopes=tuple({"scope": s, "owner_id": o} for s, o in sorted(allowed_scopes)),
        escalation_reason=reason_text,
        channels=("expand",),
        # ROW ids in candidates (the trace currency — adversary F9b): drops
        # carry both namespaces in their own dicts.
        candidates=tuple(
            {"record_id": str(found[gid].assertion_id or gid), "scores": {}}
            for gid in ordered[:64]),
        selected=tuple(h.record_id for h in hits),
        dropped=tuple(dropped),
        cues=tuple(line for h in hits for line in h.cues),
        budgets={"depth": int(depth), "max_records": int(max_records),
                 "token_budget": int(token_budget),
                 "edge_limit_per_node": per_node, "discovery_cap": discovery_cap},
        budget_spent=dict(budget_spent),
        stop_reason="enough" if hits else "no_candidates",
        admissions={h.record_id: "stimulus" for h in hits},
    )
    if write_journal:
        journal.append_trace(trace)
        expanded = [
            MemoryEvent(
                kind="expanded", scope=h.scope, owner_id=h.owner_id,
                record_id=h.record_id, trace_id=tid, actor="system",
                provenance={"expand": True, "parent_trace_id": parent_trace_id or ""},
                # Replay-safe when the caller supplied the trace id
                # (adversary F8): derived event ids dedupe at the journal.
                event_id=(f"{tid}-expanded-{h.record_id}" if trace_id else ""),
            )
            for h in hits
        ]
        if expanded:
            journal.append_events(expanded)

    return ProbeResult(
        trace_id=tid, as_of_seq=int(as_of_seq), hits=tuple(hits),
        dropped=tuple(dropped), channels=("expand",),
        warnings=(), budget_spent=budget_spent,
    )
