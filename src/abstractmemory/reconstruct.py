"""Pure reconstruction pipeline: fusion + spreading + ordering + views.

Implements the v1 scope of backlog 0019 (fusion/reserved slots — channel
primitives live in channels.py), 0020 (budgeted shelf + selection traces)
and 0026 (spreading + working_set) as ONE pure function over an injected
store and injected activation inputs.

Purity contract (0026 §5): `run_reconstruction` only READS the store; it
never writes journal records, never computes attention (base/trail
activation are inputs), and never calls selectors — those hooks land in the
facade (system.py, backlog 0024). Determinism: identical (store contents,
stimulus, params, activation inputs) → identical outputs; every internal
ordering has explicit tie-breaks.

Hard contract (fork lesson, 0019/0020 decision boundaries): low activation
NEVER excludes a channel-matched candidate, and there is no heuristic
pruning below the shelf — budgets bound output size, not relevance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import AbstractSet, Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .canonical_text import handle_digest
from .canonical_text import token_estimate as _token_estimate
from .attention import AttentionConfig, ranking_boost
from .channels import (
    CHANNEL_ORDER,
    EXCLUSION_OVERFETCH_CAP,
    ChannelResult,
    run_exact_channel,
    run_keyword_channel,
    run_participants_channel,
    run_vector_channel,
)
from .journal import ReconstructionTrace
from .models import TripleAssertion
# ReconstructConfig lives in records.py (kind policy); re-exported here.
from .records import ReconstructConfig
from .seam import ENTITY_RECALL_CANDIDATE_CAP, RecallBudget, ReconstructionResult, Stimulus
# Shelf assembly (ordering/handles) lives in shelf.py; the union fill and
# candidate registration live in self_component.py (identity wave split —
# this module orchestrates the pipeline, those own their tasks).
from .self_component import add_candidate as _add_candidate
from .self_component import fetch_by_ids as _fetch_by_ids
from .self_component import fill_shelf, select_self_members
from .shelf import Candidate as _Candidate
from .shelf import _DEFAULT_BINDING, build_handle, order_members
from .spreading import SpreadParams, spread_activation
from .store import TripleQuery

__all__ = ["ChannelResult", "ReconstructConfig", "default_ranking_boost", "run_reconstruction"]

# Trace candidate lists are bounded independently of budgets (0020: traces
# must not become their own storage problem). ALIGNED with the seam's pool
# cap (operator 2026-08-01 "at most a 100" ruling): the old private 64 here
# was a DISPLAY ARTIFACT — the UI counted this list while the engine's pool
# ran wider, so the operator's "N considered" read the trace bound, not the
# truth. One constant, both bounds: a full entity-profile pool now fits the
# trace whole, and budget_spent.candidates_considered stays the authoritative
# count when the universe outgrows the list (spreading can add past the
# gather pool).
_TRACE_CANDIDATE_CAP = ENTITY_RECALL_CANDIDATE_CAP
_EMPTY_CONTRIBUTIONS: Mapping[str, Sequence[str]] = MappingProxyType({})
# bindings: (record_id, scope, owner_id) -> "{search_state}+{prompt_state}"
# display string from the facade's 0017 fold. Unbound records keep the
# documented default (shelf._DEFAULT_BINDING).
_EMPTY_BINDINGS: Mapping[Tuple[str, str, str], str] = MappingProxyType({})


def default_ranking_boost(base_level: float) -> float:
    """Fork-derived activation boost for DIRECT `run_reconstruction` callers
    (the facade injects its own config-driven boost — system.py). Delegates
    to attention.ranking_boost with default config so the formula has ONE
    owner: min(boost_scale·a, max_boost) = min(4a, 120) at defaults. Negative
    base (silenced) attenuates. Relevance admits, activation reorders (0018).
    Invariant worth naming: max_boost/1000 (shelf.py's relevance scale) is
    the "activation boost ≤ 12% of a direct hit" seam contract — tune
    AttentionConfig.max_boost with that ratio in view."""
    return ranking_boost(float(base_level), config=AttentionConfig())


def _query_fingerprint(stimulus: Stimulus) -> str:
    """sha256 over cue_text + canonical-JSON patterns, first 16 hex (0020)."""
    payload = json.dumps(
        {"cue_text": stimulus.cue_text, "patterns": [dict(p) for p in stimulus.patterns]},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _normalize_scopes(scopes: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Normalize + dedupe (order preserved: callers pass narrow→broad)."""
    out: List[Tuple[str, str]] = []
    seen: set = set()
    for pair in scopes or ():
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            continue
        norm = (str(pair[0] or "").strip().lower(), str(pair[1] or "").strip())
        if not norm[0] or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def _apply_channel_results(
    universe: Dict[str, _Candidate],
    results: Sequence[ChannelResult],
    assertions: Mapping[str, TripleAssertion],
    excluded_ids: AbstractSet[str],
) -> Dict[str, float]:
    """Fold channel hits into the universe; returns record_id -> channel score
    (max over duplicate hits, e.g. two patterns matching the same record)."""
    folded: Dict[str, float] = {}
    for r in results:
        assertion = assertions.get(r.record_id) or (universe[r.record_id].assertion if r.record_id in universe else None)
        if assertion is None:
            continue
        cand = _add_candidate(universe, assertion, r.channel, excluded_ids)
        if cand is None:
            continue
        cand.relevance[r.channel] = max(cand.relevance.get(r.channel, 0.0), float(r.score))
        bucket = cand.details.setdefault(r.channel, [])
        if r.detail not in bucket:
            bucket.append(r.detail)
        folded[r.record_id] = max(folded.get(r.record_id, 0.0), float(r.score))
    return folded


def run_reconstruction(
    *,
    store: Any,
    stimulus: Stimulus,
    scopes: Sequence[Tuple[str, str]],
    budget: RecallBudget,
    view: str,
    base_activation: Mapping[str, float],
    trail_activation: Mapping[Tuple[str, str], float],
    activation_contributions: Mapping[str, Sequence[str]] = _EMPTY_CONTRIBUTIONS,
    excluded_ids: AbstractSet[str] = frozenset(),
    bindings: Mapping[Tuple[str, str, str], str] = _EMPTY_BINDINGS,
    embedder: Any = None,
    spread_params: SpreadParams = SpreadParams(),
    as_of_seq: int = 0,
    trace_id: str = "",
    ranking_boost: Optional[Callable[[float], float]] = None,
    config: ReconstructConfig = ReconstructConfig(),
    run_channels: bool = True,
    run_spreading: bool = True,
    prompt_active: Sequence[Tuple[str, str, str]] = (),
    global_count_of: Optional[Callable[[str], int]] = None,
) -> Tuple[ReconstructionResult, ReconstructionTrace]:
    """One reconstruction: candidates → channels → fusion → spreading →
    membership → ordering → budgeted shelf → (result, trace). See module
    docstring for the purity/no-gating contracts. `as_of_seq`/`trace_id` are
    caller-owned bookkeeping (an empty trace_id gets a deterministic
    fingerprint-derived fallback so the pipeline stays uuid-free).

    `bindings` maps (record_id, scope, owner_id) to the folded 0017 display
    string for the handle's `binding` field; unbound records get the
    "indexed+inactive" default. HIDDEN enforcement is NOT re-derived here:
    the facade passes hidden ids inside `excluded_ids` (one exclusion set,
    one code path — same treatment as closure folds)."""
    if view not in ("shelf", "working_set"):
        raise ValueError(f"view must be 'shelf' or 'working_set', got {view!r}")

    warnings: List[str] = []
    scope_pairs = _normalize_scopes(scopes)
    boost = ranking_boost if ranking_boost is not None else default_ranking_boost

    def base_of(rid: str) -> float:
        try:
            return float(base_activation.get(rid, 0.0))
        except (TypeError, ValueError):
            return 0.0

    if budget.deadline_s is not None:
        warnings.append("#FALLBACK: deadline_s is not enforced by the v1 pure pipeline (no clock injection)")

    universe: Dict[str, _Candidate] = {}
    channels_run: List[str] = []

    # All RecallBudget bounds are hard; max_candidates <= 0 means NOTHING may
    # be fetched (the stores treat limit<=0 as UNLIMITED — never forward it).
    gather = int(budget.max_candidates) > 0
    if not gather:
        warnings.append("#FALLBACK: max_candidates <= 0 disables candidate gathering")

    if gather:
        # CANDIDATES: recent assertions per (scope, owner). Recency is the
        # baseline candidate source; channels add targeted hits on top.
        # Exclusion-aware over-fetch (audit f2): closed/hidden rows would
        # otherwise burn the whole window and shadow eligible older rows.
        cap = int(budget.max_candidates)
        fetch_limit = cap + min(len(excluded_ids), EXCLUSION_OVERFETCH_CAP)
        for scope, owner in scope_pairs:
            kept = 0
            for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=fetch_limit)):
                if kept >= cap:
                    break
                if _add_candidate(universe, a, "recent", excluded_ids) is not None:
                    kept += 1

    # run_channels=False (ablation="recency"): recents-only universe — no
    # channel scoring, so relevance stays empty, reserved slots never
    # engage, and stimulus cues/patterns/anchors are ignored.
    if gather and run_channels:
        exact_results, exact_found, exact_ran = run_exact_channel(
            store, stimulus, scope_pairs, budget, excluded_ids, warnings
        )
        if exact_ran:
            channels_run.append("exact")
            _apply_channel_results(universe, exact_results, exact_found, excluded_ids)

        vector_results, vector_found, vector_ran = run_vector_channel(
            store, stimulus, scope_pairs, budget, embedder, warnings,
            excluded_ids=excluded_ids, vector_floor=config.vector_floor,
            vector_margin=config.vector_margin, confidence_span=config.confidence_span,
        )
        if vector_ran:
            channels_run.append("vector")
            _apply_channel_results(universe, vector_results, vector_found, excluded_ids)
            if not vector_results and universe and not any("below floor" in w for w in warnings):
                # 0014 gap made visible: rows written without vectors are
                # silently invisible to semantic search (a store built without
                # an embedder + a system-level embedder query hits this). Zero
                # vector hits over a non-empty universe is the cheapest honest
                # tell — warn instead of letting the channel look alive. (When
                # cosines EXISTED but all fell below the floor, the channel
                # already said so — this store-side alarm would be false.)
                warnings.append(
                    f"#FALLBACK: vector channel ran but scored 0 of {len(universe)} candidates — "
                    "verify store-side vectors exist (vectorless rows are invisible to semantic "
                    "search; manifest/backfill lands with backlog 0014)"
                )

        # Keyword + participants run last, over the full universe (recents +
        # exact + vector discoveries), so no channel-found candidate misses
        # their scores. Keyword gains store DISCOVERY when the host opts in
        # (config.keyword_discovery + an FTS5-capable store, 0019);
        # participants stays a universe re-score.
        keyword_results, keyword_found, keyword_ran = run_keyword_channel(
            stimulus.cue_text, {rid: c.assertion for rid, c in universe.items()}, warnings,
            store=store if config.keyword_discovery else None,
            scope_pairs=scope_pairs,
            discovery_limit=int(budget.max_candidates) if config.keyword_discovery else 0,
        )
        if keyword_ran:
            channels_run.append("keyword")
            _apply_channel_results(universe, keyword_results, keyword_found, excluded_ids)

        participant_results, participants_ran = run_participants_channel(
            stimulus, {rid: c.assertion for rid, c in universe.items()}, warnings
        )
        if participants_ran:
            channels_run.append("participants")
            _apply_channel_results(universe, participant_results, {}, excluded_ids)

        # ORIENTATION ADMISSION (world-model mention => instant card,
        # 2026-07-18 maintainer directive): a mentioned target's CURRENT
        # card admits at direct-hit relevance — orientation arrives WITH
        # the mention, before any similarity race. ON by default; homes
        # without cards are byte-unchanged (nothing to admit), which is
        # how the golden fixture stays byte-identical.
        if config.orientation_admission:
            from .world_model import mention_orientation_cards

            oriented = mention_orientation_cards(
                store, stimulus, scope_pairs, excluded_ids=excluded_ids,
                scan_limit=int(config.orientation_scan_limit),
                max_cards=int(config.orientation_max_cards))
            if oriented:
                channels_run.append("orientation")
            orientation_results = [
                ChannelResult(record_id=adm["record_id"], channel="orientation",
                              score=1.0, detail=adm["detail"])
                for adm in oriented
            ]
            found_o = {adm["record_id"]: adm["assertion"] for adm in oriented}
            _apply_channel_results(universe, orientation_results, found_o, excluded_ids)

        # CONCEPT ANCHORING (fork memory_anchor.rs port, 2026-07-12):
        # edge-free associative expansion — records sharing a DISCRIMINATIVE
        # concept with a channel-matched seed surface as candidates even
        # when the query never contained the term. OFF by default
        # (golden byte-stability; hosts opt in via ReconstructConfig);
        # probe() runs its own copy of this pass with expansion ON.
        if config.concept_expansion:
            seeds = {rid: c.assertion for rid, c in universe.items() if c.channel_matched}
            if seeds:
                from .concept_anchor import DEFAULT_CONCEPT_TUNING, expand_by_concepts

                admissions_c, notes_c = expand_by_concepts(
                    store, seeds, scope_pairs, excluded_ids=excluded_ids,
                    tuning=config.concept_tuning or DEFAULT_CONCEPT_TUNING)
                warnings.extend(notes_c)
                if admissions_c:
                    channels_run.append("concept")
                concept_results = [
                    ChannelResult(record_id=adm["record_id"], channel="concept",
                                  score=float(adm["score"]),
                                  detail="shared concepts: " + ", ".join(adm["concepts"][:6]))
                    for adm in admissions_c
                ]
                found_c = {adm["record_id"]: adm["assertion"] for adm in admissions_c}
                _apply_channel_results(universe, concept_results, found_c, excluded_ids)

    channels_run.sort(key=CHANNEL_ORDER.index)

    # SPREADING (0026): seeds = channel-matched records with fused scores
    # (ACT-R W_j). Runs per (scope, owner) pair — activation must not leak
    # across scope partitions — under a SHARED total edge budget consumed
    # narrow→broad. The RecallBudget is AUTHORITATIVE for hops/edges (a2a
    # 008; the old min() silently clamped a budget of 5 hops down to
    # SpreadParams' 2): SpreadParams keeps the walk-shape knobs
    # (weights/damping/fan_out_cap/min_contribution) only.
    eff_params = replace(
        spread_params,
        max_hops=int(budget.max_hops),
        max_edges=int(budget.max_edges),
    )
    all_edges: List[Dict[str, Any]] = []
    # EVERY pair walks, and each keeps its OWN seeds. A pair must never claim a
    # seed another pair would then be unable to reach: that made the result
    # non-monotonic in ladder coverage, because records reachable only from the
    # claimed seeds silently lost their spread. Dropping the narrower pair
    # instead is equally wrong — `fan_out_cap` then lets a crowded owner win
    # the shared walk and starve the narrow owner's records to zero.
    #
    # Contributions COMBINE BY MAX, not by sum, so a record that two
    # overlapping pairs both reach is counted once, and adding a pair can only
    # ever RAISE a record's spread. For a ladder of disjoint scopes — every
    # ladder the package ships — exactly one pair can reach any given record,
    # so max and sum agree and this changes nothing.
    for scope, owner in (scope_pairs if run_spreading else ()):
        remaining = eff_params.max_edges - len(all_edges)
        if remaining <= 0:
            break
        pair_seeds: Dict[str, float] = {}
        for rid, cand in universe.items():
            if not cand.channel_matched:
                continue
            a = cand.assertion
            if a.scope == scope and (not owner or (a.owner_id or "") == owner):
                pair_seeds[rid] = cand.fused
        if not pair_seeds:
            continue
        spread_scores, edges = spread_activation(
            store,
            pair_seeds,
            scope=scope,
            owner_id=owner,
            params=replace(eff_params, max_edges=remaining),
            trail_activation=trail_activation,
            excluded_ids=excluded_ids,
        )
        all_edges.extend(edges)
        if view == "working_set":
            # The emergent neighborhood: spread targets join the candidate
            # universe as members-in-waiting. working_set view ONLY — the
            # shelf view stays spec-literal (recents + channel hits), with
            # spread contributing activation decomposition on those.
            new_ids = [rid for rid in spread_scores if rid not in universe]
            for rid, a in _fetch_by_ids(store, new_ids, scope, owner).items():
                _add_candidate(universe, a, "spread", excluded_ids)
        for rid, value in spread_scores.items():
            if rid in universe:
                universe[rid].spread = max(universe[rid].spread, float(value))

    spread_cue_map: Dict[str, List[str]] = {}
    for edge in all_edges:
        cue = f"spread: via {edge['predicate']} from {edge['source_id']}"
        bucket = spread_cue_map.setdefault(str(edge["target_id"]), [])
        if cue not in bucket:
            bucket.append(cue)

    # SELF MEMBERS (identity wave): prompt-active bindings admit by STATE.
    # Selected BEFORE the min_activation filter, which never gates them
    # (identity presence is not an activation question — same exemption as
    # channel matches).
    self_members: List[str] = []
    if float(budget.self_fraction) > 0.0 and prompt_active:
        self_members = select_self_members(store, universe, prompt_active, excluded_ids, config)
    self_member_set = set(self_members)

    # working_set MEMBERSHIP threshold on TOTAL activation (base + spread),
    # applied BEFORE slot selection so filtered members never consume shelf
    # slots. HARD CONTRACT: never filters a channel-matched or self member.
    had_candidates = bool(universe)
    pre_dropped: List[Dict[str, Any]] = []
    if view == "working_set" and budget.min_activation is not None:
        threshold = float(budget.min_activation)
        for rid in sorted(universe.keys()):
            cand = universe[rid]
            if cand.channel_matched or rid in self_member_set:
                continue
            if base_of(rid) + cand.spread < threshold:
                del universe[rid]
                pre_dropped.append({"record_id": rid, "score": cand.fused, "reason": "below_min_activation"})

    # ORDERING over the whole universe: channel-matched first, exact-first,
    # fused + boost, kind tie-break, recency — then the union fill
    # (self_component.fill_shelf) assembles the shelf per C3 v1.2:
    # phase-0 top match → SELF → stimulus share → STM → stimulus remainder.
    ordered = order_members(list(universe.keys()), universe, base_of, boost, config)

    # STM eligibility = the activation fold's base map (STM horizon == the
    # attention window; never a store scan); floor from budget.stm_floor
    # (default config.stm_floor).
    stm_hot: List[str] = []
    if gather and float(budget.stm_fraction) > 0.0 and base_activation:
        stm_floor = float(budget.stm_floor) if budget.stm_floor is not None else float(config.stm_floor)
        stm_hot = sorted(
            (rid for rid, b in base_activation.items()
             if float(b) >= stm_floor and rid not in excluded_ids),
            key=lambda rid: (-float(base_activation[rid]), rid),
        )

    fill = fill_shelf(
        store=store, universe=universe, ordered=ordered, self_members=self_members,
        stm_hot=stm_hot, base_activation=base_activation, base_of=base_of,
        budget=budget, view=view, scope_pairs=scope_pairs, excluded_ids=excluded_ids,
        newest_seats=int(getattr(config, "newest_seat_guarantee", 0)),
        dedup_identical_digests=bool(getattr(config, "shelf_dedup_identical_digests", True)),
    )
    dropped: List[Dict[str, Any]] = [*pre_dropped, *fill.dropped]
    admissions, digests = fill.admissions, fill.digests
    stm_placed, placed, stm_slots = fill.stm_placed, fill.placed, fill.stm_slots
    tokens_used, token_exhausted = fill.tokens_used, fill.token_exhausted

    def _binding_of(rid: str) -> str:
        # Subject-level (record/graph-id) binding first — the 0017-canonical
        # key remember_many/bind() write — then assertion-level, then default.
        a = universe[rid].assertion
        key = (a.subject, a.scope, a.owner_id or "")
        return bindings.get(key, bindings.get((rid, a.scope, a.owner_id or ""), _DEFAULT_BINDING))

    counts = global_count_of if global_count_of is not None else (lambda rid: 0)
    handles = tuple(
        build_handle(
            universe[rid], base_of(rid), spread_cue_map.get(rid, ()),
            activation_contributions.get(rid, ()), digests[rid], _binding_of(rid), config,
            admission=admissions[rid], global_count=int(counts(rid)),
        )
        for rid in fill.handle_order
    )

    if not had_candidates and not fill.handle_order:
        stop_reason = "no_candidates"
    elif token_exhausted:
        stop_reason = "budget_exhausted"
    else:
        stop_reason = "enough"

    warnings = list(dict.fromkeys(warnings))  # dedupe, order preserved
    fingerprint = _query_fingerprint(stimulus)
    if not trace_id:
        trace_id = f"trace-{fingerprint}-{int(as_of_seq)}"

    # Component accounting counts by admission LABEL, not fill path: a
    # trail-hot record the recency pull happened to gather is still STM
    # presence (and deposits nothing at commit), wherever it was placed.
    stm_member_ids = [rid for rid, label in admissions.items() if label == "stm"]
    budget_spent: Dict[str, Any] = {
        "tokens_used": tokens_used,
        "token_budget": int(budget.token_budget),
        "candidates_considered": len(universe) + len(pre_dropped),
        "handles": len(fill.handle_order),
        "stm_handles": len(stm_member_ids),
        "stm_tokens_used": sum(_token_estimate(digests[rid]) for rid in stm_member_ids),
        "shelf_size": int(budget.shelf_size),
        "edges_visited": len(all_edges),
        "max_edges": int(eff_params.max_edges),
    }
    if float(budget.self_fraction) > 0.0:
        # Keys are CONDITIONAL by design: self_fraction=0.0 must keep the
        # result JSON byte-identical to pre-identity-wave output (seam v1.2).
        self_ids = [rid for rid, label in admissions.items() if label == "self"]
        budget_spent["self_handles"] = len(self_ids)
        budget_spent["self_tokens_used"] = sum(_token_estimate(digests[rid]) for rid in self_ids)

    # Hot STM trail pairs surface in the working_set view even when unwalked
    # this turn ("the edges with the highest temporal access counts" are part
    # of STM); walked hops already carry their trail_activation, so only
    # unwalked pairs are added. Render-side observability only, never handles.
    edges_out: List[Dict[str, Any]] = list(all_edges) if view == "working_set" else []
    if view == "working_set" and float(budget.stm_fraction) > 0.0 and trail_activation:
        walked_pairs = {tuple(sorted((str(e["source_id"]), str(e["target_id"])))) for e in all_edges}
        ranked_pairs = sorted(trail_activation.items(), key=lambda kv: (-float(kv[1]), kv[0]))
        for pair, value in ranked_pairs[: max(2, stm_slots)]:
            if float(value) > 0.0 and tuple(sorted(pair)) not in walked_pairs:
                edges_out.append(
                    {"source": "stm_trail", "pair": [pair[0], pair[1]], "trail_activation": float(value)}
                )

    result = ReconstructionResult(
        trace_id=trace_id,
        view=view,
        as_of_seq=int(as_of_seq),
        handles=handles,
        edges=tuple(edges_out),
        dropped=tuple(dropped),
        selector_route="heuristic",  # the pure pipeline never calls selectors (hook lands in system.py)
        stop_reason=stop_reason,
        warnings=tuple(warnings),
        budget_spent=budget_spent,
    )

    # Bounded trace candidates: strongest fused first, deterministic ties.
    trace_ids = sorted(universe.keys())
    trace_ids.sort(key=lambda rid: universe[rid].assertion.observed_at or "", reverse=True)
    trace_ids.sort(key=lambda rid: universe[rid].fused, reverse=True)
    trace_candidates = tuple(
        {"record_id": rid, "scores": dict(universe[rid].relevance)} for rid in trace_ids[:_TRACE_CANDIDATE_CAP]
    )

    need = stimulus.to_dict()
    if need.get("embedding") is not None:
        # Traces are bounded observability records; a full float vector adds
        # bulk without explanatory value. Dimensionality is enough to audit.
        need["embedding"] = f"<{len(stimulus.embedding or ())} floats omitted>"
    need["view"] = view

    cue_lines: List[str] = []
    for h in handles:
        for cue in h.cues:
            if cue not in cue_lines:
                cue_lines.append(cue)

    trace = ReconstructionTrace(
        trace_id=trace_id,
        trace_kind="reconstruct",
        query_fingerprint=fingerprint,
        need=need,
        searched_scopes=tuple({"scope": s, "owner_id": o} for s, o in scope_pairs),
        escalation_reason=None,  # the broad-scope guard is facade policy (0020 §5)
        channels=tuple(channels_run),
        candidates=trace_candidates,
        selected=tuple(h.record_id for h in handles),
        dropped=tuple(dropped),
        cues=tuple(cue_lines),
        budgets=budget.to_dict(),
        budget_spent=dict(budget_spent),
        selector_route="heuristic",
        stop_reason=stop_reason,
        warnings=tuple(warnings),
        admissions=dict(admissions),  # presence ≠ use: commit consults this
    )
    return result, trace
