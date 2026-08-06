"""Bounded spreading activation over the assertion graph (backlog 0026).

v1 record semantics: plain assertions ARE the records (record_id ==
assertion_id). There is no separate node/edge storage yet — an assertion
whose subject AND object both look like entity terms is treated as an edge
of the entity graph, and activation spreads assertion→assertion through
shared entity terms (store.query(subject=term) / store.query(object=term)).

Hard properties (0026 decision boundaries):
- pure READ: only store.query() calls, never a write;
- bounded: max_hops / fan_out_cap (fan effect) / max_edges / min_contribution;
- deterministic: every frontier and neighbor set is sorted by assertion_id;
- cycles terminate via an expanded-nodes visited set;
- excluded_ids (closure/visibility fold, computed by the caller) never
  receive activation AND are never traversed — spreading through a retracted
  assertion would leak its influence back into recall.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AbstractSet, Any, Dict, List, Mapping, Tuple

from .channels import EXCLUSION_OVERFETCH_CAP
from .models import TripleAssertion
from .store import TripleQuery

# Terms longer than this are extracted sentences/free text, not entity names;
# traversing through them would connect unrelated facts via prose overlap.
_ENTITY_TERM_MAX_CHARS = 120


@dataclass(frozen=True)
class SpreadParams:
    """Tuning knobs for one spreading walk (all bounds hard, 0026)."""

    max_hops: int = 2
    fan_out_cap: int = 12      # neighbors accepted per node per hop (fan effect guard)
    damping: float = 0.5       # per-hop multiplier
    max_edges: int = 100       # total accepted-edge budget for the whole walk
    min_contribution: float = 0.05  # noise floor: weaker contributions do not propagate
    # Trail normalization divisor: a maximally reinforced pair (trail at the
    # attention ceiling) DOUBLES its edge contribution (1 + trail/divisor).
    # Must track AttentionConfig.max_activation — the review found the 25.0
    # inlined here while max_activation was a declared tunable, so raising
    # the ceiling silently doubled the intended max trail bonus.
    trail_divisor: float = 25.0
    # predicate -> multiplier; missing predicate = 1.0 (uniform by default,
    # per-edge-kind differentials are a maintainer-pending tuning decision).
    edge_kind_weights: Mapping[str, float] = field(default_factory=dict)


def _is_entity_term(term: str) -> bool:
    """Heuristic: does this term look like an entity name (not free text)?"""
    t = str(term or "").strip()
    if not t or len(t) > _ENTITY_TERM_MAX_CHARS:
        return False
    # Require at least one alphanumeric char so punctuation-only terms
    # (e.g. "---") never become graph hubs.
    return any(ch.isalnum() for ch in t)


def _is_graph_edge(a: TripleAssertion) -> bool:
    """v1 edge rule: subject AND object are entity-like and the object is not
    a literal value (models.py marks literal objects via attributes["literal"])."""
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    if bool(attrs.get("literal")):
        return False
    return _is_entity_term(a.subject) and _is_entity_term(a.object)


def _expansion_terms(a: TripleAssertion) -> List[str]:
    """Terms of `a` worth querying for neighbors.

    The subject is queried when entity-like; the object only when entity-like
    AND not literal-flagged (querying store.query(subject=<free text>) is
    useless and querying literals would traverse through values, not entities).
    """
    terms: List[str] = []
    if _is_entity_term(a.subject):
        terms.append(a.subject)
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    if not bool(attrs.get("literal")) and _is_entity_term(a.object) and a.object not in terms:
        terms.append(a.object)
    return terms


def _fetch_assertions_by_ids(
    store: Any, ids: Tuple[str, ...], *, scope: str, owner_id: str
) -> Dict[str, TripleAssertion]:
    """Guarded id fetch. CRITICAL: TripleQuery normalizes an empty
    assertion_ids tuple to None, which would return the ENTIRE scope — so an
    empty id set must short-circuit before building the query."""
    if not ids:
        return {}
    wanted = tuple(sorted(ids))
    q = TripleQuery(assertion_ids=wanted, scope=scope, owner_id=owner_id or None, limit=len(wanted))
    out: Dict[str, TripleAssertion] = {}
    for a in store.query(q):
        if isinstance(a.assertion_id, str) and a.assertion_id:
            out[a.assertion_id] = a
    return out


def _neighbors(
    store: Any,
    source: TripleAssertion,
    *,
    scope: str,
    owner_id: str,
    fan_out_cap: int,
    excluded_ids: AbstractSet[str] = frozenset(),
) -> List[TripleAssertion]:
    """Neighboring assertions of `source`: any assertion sharing one of its
    entity terms in subject OR object position. Bounded per query, deduped,
    self and EXCLUDED rows dropped BEFORE the cap (audit f2: closed/hidden
    rows must not burn fan-out slots), then the cap keeps the most RECENT
    neighbors (observed_at desc, assertion_id desc tie-break) — the recency
    preference the docstring always promised (audit f10: the old id-sorted
    truncation kept the lexicographically smallest ids instead).
    """
    source_id = source.assertion_id or ""
    found: Dict[str, TripleAssertion] = {}
    # +1 leaves room for the source itself showing up in its own term queries;
    # over-fetch bounded headroom so excluded rows cannot shadow eligible ones.
    per_query_limit = max(1, int(fan_out_cap)) + 1 + min(len(excluded_ids), EXCLUSION_OVERFETCH_CAP)
    for term in _expansion_terms(source):
        for q in (
            TripleQuery(subject=term, scope=scope, owner_id=owner_id, limit=per_query_limit),
            TripleQuery(object=term, scope=scope, owner_id=owner_id, limit=per_query_limit),
        ):
            for a in store.query(q):
                aid = a.assertion_id
                if not (isinstance(aid, str) and aid) or aid == source_id or aid in excluded_ids:
                    continue
                found.setdefault(aid, a)
    ordered = sorted(
        found.values(),
        key=lambda a: (a.observed_at or "", a.assertion_id or ""),
        reverse=True,
    )
    return ordered[: max(0, int(fan_out_cap))]


def spread_activation(
    store: Any,
    seeds: Mapping[str, float],
    *,
    scope: str,
    owner_id: str,
    params: SpreadParams,
    trail_activation: Mapping[Tuple[str, str], float],
    excluded_ids: AbstractSet[str] = frozenset(),
) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    """Spread activation from cue-matched seed records through the graph.

    seeds: record_id -> cue weight (ACT-R W_j; typically the fused channel
    score from reconstruction). Returns (spread_scores, edges_visited):
    - spread_scores: record_id -> accumulated spread contribution (targets
      only; a record may accumulate from several sources — convergence);
    - edges_visited: traversal trace, one dict per accepted edge with the
      seam-fixed keys {source_id, predicate, target_id, strength_label,
      trail_activation}. "recorded" label: v1 has no inferred edges.

    Contribution at hop h along a path is
      seed_weight * damping^h * Π edge_kind_weight(predicate) * Π (1 + trail/25)
    implemented as a per-hop recurrence (strength carried on the frontier).
    The /25 divisor anchors the trail boost to the journal's deliberate-act
    weight ceiling (journal.py clamps pin/silence weights to 1..25): a
    maximally reinforced pair trail doubles the contribution.

    TRAIL EDGES (co-use trails, maintainer-initiated 2026-07-07): warm
    co_selected pairs are TRAVERSABLE connections, not just boosts — a
    node's trail partners (pairs in trail_activation containing it, trail
    > 0) are walked like neighbors, labeled strength_label="trail" with
    predicate="co_used". This is what heals the isolation the maintainer
    observed: two edgeless formed records that repeatedly served one
    moment together become mutually reachable through their own usage
    history. Trail partners respect fan_out_cap (strongest trails first),
    the shared edge budget, and the same exclusion/cycle rules.
    """
    max_hops = int(params.max_hops)
    max_edges = int(params.max_edges)
    if max_hops <= 0 or max_edges <= 0 or not seeds:
        return {}, []

    # Sanitize seeds: positive finite weights only, exclusions honored.
    clean_seeds: Dict[str, float] = {}
    for rid, w in seeds.items():
        if not (isinstance(rid, str) and rid.strip()) or rid in excluded_ids:
            continue
        try:
            weight = float(w)
        except (TypeError, ValueError):
            continue
        if weight > 0.0 and weight == weight and weight != float("inf"):
            clean_seeds[rid.strip()] = weight
    if not clean_seeds:
        return {}, []

    seed_assertions = _fetch_assertions_by_ids(
        store, tuple(clean_seeds.keys()), scope=scope, owner_id=owner_id
    )

    spread: Dict[str, float] = {}
    edges: List[Dict[str, Any]] = []
    expanded: set[str] = set()  # cycle terminator: a node spreads at most once

    # Trail-partner index (co-use edges): node -> [(partner, trail)] with
    # trail > 0, strongest first — deterministic (trail desc, partner asc).
    trail_partners: Dict[str, List[Tuple[str, float]]] = {}
    for pair, raw in (trail_activation or {}).items():
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0.0 or not (isinstance(pair, tuple) and len(pair) == 2):
            continue
        a, b = pair
        trail_partners.setdefault(a, []).append((b, value))
        trail_partners.setdefault(b, []).append((a, value))
    for node in trail_partners:
        trail_partners[node].sort(key=lambda t: (-t[1], t[0]))

    # frontier: assertion_id -> (assertion, propagation strength). Hop 0 = seeds.
    seed_ids = set(seed_assertions.keys())
    frontier: Dict[str, Tuple[TripleAssertion, float]] = {
        rid: (seed_assertions[rid], clean_seeds[rid]) for rid in sorted(seed_assertions.keys())
    }

    budget_exhausted = False
    for _hop in range(1, max_hops + 1):
        if not frontier or budget_exhausted:
            break
        next_frontier: Dict[str, Tuple[TripleAssertion, float]] = {}

        for source_id in sorted(frontier.keys()):
            if budget_exhausted:
                break
            if source_id in expanded:
                continue
            expanded.add(source_id)
            source, strength = frontier[source_id]

            reached_from_source: set = set()
            for neighbor in _neighbors(
                store, source, scope=scope, owner_id=owner_id,
                fan_out_cap=params.fan_out_cap, excluded_ids=excluded_ids,
            ):
                target_id = neighbor.assertion_id or ""
                if not target_id:  # excluded rows already filtered pre-cap
                    continue
                # A node that already spread in an EARLIER hop does not
                # re-receive: the echo (seed -> neighbor -> seed) would burn
                # edge budget on self-reinforcement without adding working-set
                # structure. ONE deliberate exception: the original cue-matched
                # seeds may still warm each other on hop 1, fixing the
                # seed-to-seed gap called out in 0026 without changing later
                # same-hop frontier behavior.
                allow_seed_peer = (
                    source_id in seed_ids
                    and target_id in seed_ids
                    and target_id in frontier
                    and source_id != target_id
                )
                if target_id in expanded and not allow_seed_peer:
                    continue

                pair = tuple(sorted((source_id, target_id)))
                try:
                    trail = float(trail_activation.get(pair, 0.0))  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    trail = 0.0
                kind_weight = float(params.edge_kind_weights.get(neighbor.predicate, 1.0))
                contribution = strength * float(params.damping) * kind_weight * (1.0 + trail / float(params.trail_divisor))
                if contribution < float(params.min_contribution):
                    continue  # below the noise floor: no accumulation, no edge, no propagation

                if len(edges) >= max_edges:
                    budget_exhausted = True
                    break
                # The edge label is the TARGET assertion's predicate: in v1
                # the neighbor assertion IS the edge being brought in, and its
                # predicate names the relation that carried the spread.
                edges.append(
                    {
                        "source_id": source_id,
                        "predicate": neighbor.predicate,
                        "target_id": target_id,
                        "strength_label": "recorded",
                        "trail_activation": trail,
                        "source": "walked",  # vs "stm_trail" entries added render-side
                    }
                )
                spread[target_id] = spread.get(target_id, 0.0) + contribution
                reached_from_source.add(target_id)

                # Propagation continues only through graph EDGES (both terms
                # entity-like): leaves (literal facts) receive activation but
                # do not re-walk their subject's neighborhood.
                if _is_graph_edge(neighbor):
                    prev = next_frontier.get(target_id)
                    # Strongest incoming path drives onward propagation
                    # (sum would inflate through dense cliques).
                    if prev is None or contribution > prev[1]:
                        next_frontier[target_id] = (neighbor, contribution)

            if budget_exhausted:
                break
            # CO-USE TRAIL EDGES (see docstring): partners this source has
            # NOT already reached via the graph this hop — one physical
            # connection contributes once (graph-adjacent warm pairs keep
            # the (1 + trail/25) boost instead of a second edge).
            cap = max(0, int(params.fan_out_cap))
            partner_entries = [
                (pid, trail) for pid, trail in trail_partners.get(source_id, [])
                if pid not in expanded and pid not in excluded_ids
                and pid not in reached_from_source
            ][:cap]
            partner_rows = _fetch_assertions_by_ids(
                store, tuple(pid for pid, _ in partner_entries),
                scope=scope, owner_id=owner_id)
            for partner_id, trail in partner_entries:
                partner = partner_rows.get(partner_id)
                if partner is None:
                    continue  # not resolvable in this (scope, owner): skip
                contribution = strength * float(params.damping) * (1.0 + trail / float(params.trail_divisor))
                if contribution < float(params.min_contribution):
                    continue
                if len(edges) >= max_edges:
                    budget_exhausted = True
                    break
                edges.append({
                    "source_id": source_id, "predicate": "co_used",
                    "target_id": partner_id, "strength_label": "trail",
                    "trail_activation": trail, "source": "walked",
                })
                spread[partner_id] = spread.get(partner_id, 0.0) + contribution
                prev = next_frontier.get(partner_id)
                if prev is None or contribution > prev[1]:
                    next_frontier[partner_id] = (partner, contribution)

        frontier = next_frontier

    return dict(sorted(spread.items())), edges
