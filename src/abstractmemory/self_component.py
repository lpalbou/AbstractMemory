"""Union shelf fill: the SELF / STM / stimulus admission components.

One task (split out of reconstruct.py to honor the <600-line rule): given the
ordered candidate universe, assemble the budgeted shelf. Three admission
sources compose here (a2a 0003 identity wave + the maintainer's union model):

- SELF   — identity core admitted by BINDING STATE (folded
           search_state="indexed" AND prompt_state="active"): the fork's
           <active_memory> semantics. State, not trail: members are ordered
           by kind rank (value < purpose < trait < ...) then record_id —
           deterministic, never activation-ordered — and survive regardless
           of usage (the eviction contrast: a max-weight pin dies under
           window eviction; a prompt-active member persists).
- STM    — trail-hot records from the activation fold (temporal-access
           standing), capped by stm_fraction.
- STIMULUS — channel/recency retrieval, phase-0 top-match guarantee.

FILL ORDER (C3 v1.2, seam notification 0001/20260706T193908Z): phase-0 top
channel match → SELF (self_fraction cap; never displaces the top match;
FIRST seat guaranteed against the full remaining budget — the identity
floor means at least one identity record is PRESENT whenever the entity
has a prompt-active core and any budget remains, because a reserved seat
that renders nothing is identity-absent, which the floor forbids) →
stimulus share → STM (stm_fraction cap) → stimulus remainder.

ADMISSION LABELS key on WHY a record is present, with precedence
self > both > stm > stimulus: a prompt-active record labels "self" even when
channel-matched or trail-hot (the binding admitted it — it was coming
regardless), because presence ≠ use depends on the label: self/stm members
deposit NOTHING at commit. min_activation NEVER gates self members (it is an
activation gate; self admission is state — an identity with zero activation
is still present, exactly like channel matches are never activation-gated).

CROSS-PACKAGE CONTRACT (a2a 0003, round 7 floor): the seat derivation
`max(1, round(fraction × shelf))` — at least one seat for ANY fraction > 0 —
is mirrored by the gateway's entity-gate floor check. If this derivation
ever changes, flag the gateway on the channel BEFORE shipping (its refusal
math must follow, or the gate refuses combos the engine seats fine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    AbstractSet,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from .canonical_text import handle_digest, token_estimate as _token_estimate
from .models import TripleAssertion
from .records import KIND_RANKS, ReconstructConfig
from .seam import RecallBudget
from .shelf import Candidate
from .store import TripleQuery

__all__ = [
    "FillResult",
    "add_candidate",
    "fetch_by_ids",
    "fill_shelf",
    "select_self_members",
    "self_records_read",
]

# The identity kinds the self core is made of (value < purpose < trait —
# canonical KIND_RANKS order; diary/interest are identity-ADJACENT but not
# core, so self_records excludes them).
_SELF_CORE_KINDS = frozenset({"value", "purpose", "trait"})


def add_candidate(
    universe: Dict[str, Candidate],
    assertion: TripleAssertion,
    source: str,
    excluded_ids: AbstractSet[str],
) -> Optional[Candidate]:
    """Register one assertion as a shelf candidate (or return None).

    Records without read-side identity cannot become handles or be traced
    (backlog 0009). Edge assertions CONDUCT, they are never MEMBERS (audit
    fix 8): walkable in spreading, visible in result.edges, but never
    handles. BOOKKEEPING records (attributes.bookkeeping, e.g. the engram
    marker) are engine state, not memories — same membership exclusion,
    still fully reachable via layer-1 query()/id lookups. Excluded ids
    (closures + hidden bindings) never enter.
    """
    rid = assertion.assertion_id
    if not (isinstance(rid, str) and rid) or rid in excluded_ids:
        return None
    attrs = assertion.attributes if isinstance(assertion.attributes, dict) else {}
    if attrs.get("record_edge") or attrs.get("bookkeeping"):
        return None
    cand = universe.get(rid)
    if cand is None:
        cand = Candidate(assertion=assertion, record_id=rid)
        universe[rid] = cand
    cand.sources.add(source)
    return cand


def fetch_by_ids(store: Any, ids: Sequence[str], scope: str, owner: str) -> Dict[str, TripleAssertion]:
    """Guarded id fetch: TripleQuery normalizes an EMPTY assertion_ids tuple
    to None (whole-scope scan) — the empty case must short-circuit."""
    wanted = tuple(sorted({i for i in ids if isinstance(i, str) and i}))
    if not wanted:
        return {}
    rows = store.query(TripleQuery(assertion_ids=wanted, scope=scope, owner_id=owner or None, limit=len(wanted)))
    return {a.assertion_id: a for a in rows if isinstance(a.assertion_id, str) and a.assertion_id}


def select_self_members(
    store: Any,
    universe: Dict[str, Candidate],
    prompt_active: Sequence[Tuple[str, str, str]],
    excluded_ids: AbstractSet[str],
    config: ReconstructConfig,
) -> List[str]:
    """Resolve prompt-active binding triples to ordered member ids.

    Bindings carry RECORD ids (graph id or plain assertion id, 0017); the
    shelf needs digest-assertion ids. Resolution per (record_id, scope,
    owner): assertion-id lookup in the pair first, then subject lookup for
    formed records (the digest row carries attributes.record_kind). Closed/
    hidden ids never resurface (excluded_ids applies — a stale active
    binding cannot resurrect a retracted record). Ordering: kind rank
    (identity kinds lead: value < purpose < trait), then record_id —
    deterministic; identity is STATE, so activation plays no part.
    """
    members: List[str] = []
    seen: set = set()
    for record_id, scope, owner in prompt_active:
        assertion: Optional[TripleAssertion] = None
        cand = universe.get(record_id)
        if cand is not None:
            assertion = cand.assertion
        if assertion is None:
            assertion = fetch_by_ids(store, [record_id], scope, owner).get(record_id)
        if assertion is None:
            # Record-level binding: find the digest assertion by subject.
            for a in store.query(TripleQuery(subject=record_id, scope=scope,
                                             owner_id=owner or None, limit=0)):
                attrs = a.attributes if isinstance(a.attributes, dict) else {}
                if attrs.get("record_kind") and a.assertion_id:
                    assertion = a
                    break
        if assertion is None:
            continue  # not resolvable in its own pair: nothing to admit
        attrs = assertion.attributes if isinstance(assertion.attributes, dict) else {}
        if attrs.get("record_kind") == "dream":
            # Derived sleep artifacts never occupy identity's reserved seats
            # (0023 guard) — even a mis-bound prompt-active dream is not who
            # the entity IS; it surfaces via normal admission only.
            continue
        placed = add_candidate(universe, assertion, "self", excluded_ids)
        if placed is None or placed.record_id in seen:
            continue
        seen.add(placed.record_id)
        members.append(placed.record_id)
    # Ordering uses the CANONICAL kind ranks, not config.kind_rank: the
    # recency ablation neutralizes shelf kind priority (recall mechanics),
    # but the self block's internal order is an identity convention
    # (value < purpose < trait) that holds in every arm.
    members.sort(key=lambda rid: (
        KIND_RANKS.get(config.kind_of(universe[rid].assertion), 100), rid))
    return members


def self_records_read(
    store: Any,
    journal: Any,
    *,
    scope: str,
    owner_id: str,
    spark_version: Optional[int] = None,
    as_of: Optional[int] = None,
) -> List[TripleAssertion]:
    """The FOLDED identity read (a2a 0003 ask 3): the digest assertions of
    the entity's prompt-active identity core — binding-folded (latest per
    (record_id, scope, owner) wins; only indexed+active admit),
    CLOSURE-folded (retracted/superseded records never render — the layer-1
    query() passthrough the prelude used could resurrect them), identity
    kinds only (value/purpose/trait), optionally filtered to
    attributes.spark_version. Ordering: canonical kind rank
    (value < purpose < trait), then attributes.precedence, then record id —
    the prelude's render order. as_of=None reads CURRENT state (the
    summon-time read); an explicit as_of anchors the binding/closure folds
    for replay surfaces (the entity card's identity-at-T)."""
    from .folds import binding_states, closure_exclusions  # local: avoids a module cycle

    as_of = int(as_of) if as_of is not None else journal.current_seq()
    _states, hidden, prompt_active = binding_states(store, journal, [(scope, owner_id)], as_of)
    excluded = closure_exclusions(journal, as_of) | hidden

    out: List[TripleAssertion] = []
    seen: set = set()
    for record_id, pair_scope, pair_owner in prompt_active:
        assertion: Optional[TripleAssertion] = None
        fetched = fetch_by_ids(store, [record_id], pair_scope, pair_owner)
        assertion = fetched.get(record_id)
        if assertion is None:
            for a in store.query(TripleQuery(subject=record_id, scope=pair_scope,
                                             owner_id=pair_owner or None, limit=0)):
                attrs = a.attributes if isinstance(a.attributes, dict) else {}
                if attrs.get("record_kind") and a.assertion_id:
                    assertion = a
                    break
        if assertion is None or not assertion.assertion_id:
            continue
        if assertion.assertion_id in excluded or assertion.assertion_id in seen:
            continue
        attrs = assertion.attributes if isinstance(assertion.attributes, dict) else {}
        if attrs.get("record_kind") not in _SELF_CORE_KINDS:
            continue
        if spark_version is not None:
            try:
                if int(attrs.get("spark_version")) != int(spark_version):
                    continue
            except (TypeError, ValueError):
                continue  # unversioned records never match a version filter
        seen.add(assertion.assertion_id)
        out.append(assertion)

    def _precedence(a: TripleAssertion) -> int:
        try:
            return int((a.attributes or {}).get("precedence"))
        except (TypeError, ValueError):
            return 1_000_000  # unordered items trail their section

    out.sort(key=lambda a: (KIND_RANKS.get(str((a.attributes or {}).get("record_kind")), 100),
                            _precedence(a), a.subject, a.assertion_id))
    return out


@dataclass
class FillResult:
    """Everything the pipeline needs back from the union fill."""

    handle_order: Tuple[str, ...] = ()       # self block, STM block, stimulus block
    admissions: Dict[str, str] = field(default_factory=dict)
    dropped: List[Dict[str, Any]] = field(default_factory=list)
    digests: Dict[str, str] = field(default_factory=dict)
    tokens_used: int = 0
    token_exhausted: bool = False
    self_placed: Tuple[str, ...] = ()
    stm_placed: Tuple[str, ...] = ()
    placed: Tuple[str, ...] = ()
    stm_slots: int = 0


def fill_shelf(
    *,
    store: Any,
    universe: Dict[str, Candidate],
    ordered: Sequence[str],
    self_members: Sequence[str],
    stm_hot: Sequence[str],
    base_activation: Mapping[str, float],
    base_of: Callable[[str], float],
    budget: RecallBudget,
    view: str,
    scope_pairs: Sequence[Tuple[str, str]],
    excluded_ids: AbstractSet[str],
) -> FillResult:
    """The C3 v1.2 union fill (order + guarantees in the module docstring)."""
    shelf_cap = max(0, int(budget.shelf_size))
    total_tokens = int(budget.token_budget)
    stm_fraction = max(0.0, float(budget.stm_fraction))
    self_fraction = max(0.0, float(budget.self_fraction))
    stm_slots = min(shelf_cap, max(1, round(stm_fraction * shelf_cap))) if stm_fraction > 0.0 else 0
    self_slots = min(shelf_cap, max(1, round(self_fraction * shelf_cap))) if self_fraction > 0.0 else 0
    self_tokens_cap = int(self_fraction * total_tokens)
    stm_hot_set = set(stm_hot)
    self_set = set(self_members) if self_slots > 0 else set()

    r = FillResult(stm_slots=stm_slots)
    digests = r.digests
    for rid in ordered:
        digests[rid] = handle_digest(universe[rid].assertion)
    placed: List[str] = []
    self_placed: List[str] = []
    stm_placed: List[str] = []
    placed_set: set = set()

    def _shelf_full() -> bool:
        return len(placed) + len(self_placed) + len(stm_placed) >= shelf_cap

    # Phase 0: the single best channel-matched candidate takes a seat
    # against the FULL budget before any reservation (0001/015 hardening).
    top_matched = next((rid for rid in ordered if universe[rid].channel_matched), None)
    if top_matched is not None and shelf_cap >= 1:
        estimate = _token_estimate(digests[top_matched])
        if estimate <= total_tokens:
            placed.append(top_matched)
            placed_set.add(top_matched)
            r.tokens_used += estimate
        else:
            r.token_exhausted = True

    # SELF component: binding-state admission under its own caps. Never
    # displaces the phase-0 top match (it fills AFTER, from the remainder).
    # FIRST-SEAT GUARANTEE (identity floor, maintainer round 7 — mirror of
    # the phase-0 hardening): the FIRST placed self member seats against
    # the full REMAINING budget, not the fraction cap — at small budgets
    # int(self_fraction * total_tokens) can be smaller than ANY identity
    # digest, and a reserved seat that renders nothing is identity-absent,
    # which the floor forbids. Subsequent members respect the fraction cap.
    self_tokens_used = 0
    for rid in self_members if self_slots > 0 else ():
        if len(self_placed) >= self_slots or _shelf_full():
            break
        if rid in placed_set:
            continue  # phase-0 seated it; the label still says "self"
        digests.setdefault(rid, handle_digest(universe[rid].assertion))
        estimate = _token_estimate(digests[rid])
        if not self_placed:
            if r.tokens_used + estimate > total_tokens:
                # Even the whole remaining budget cannot fit it: honest drop;
                # the NEXT (possibly smaller) member may still claim the seat.
                r.token_exhausted = True
                r.dropped.append({"record_id": rid, "score": 0.0, "reason": "self_capped"})
                continue
        elif self_tokens_used + estimate > min(self_tokens_cap, total_tokens - r.tokens_used):
            r.dropped.append({"record_id": rid, "score": 0.0, "reason": "self_capped"})
            continue
        self_placed.append(rid)
        placed_set.add(rid)
        self_tokens_used += estimate
    r.tokens_used += self_tokens_used

    stm_reserved_slots = min(stm_slots, len(stm_hot))
    stm_reserved_tokens = int(stm_fraction * total_tokens) if stm_hot else 0

    def _fill_stimulus(slot_cap: int, token_cap: int) -> None:
        for rid in ordered:
            if rid in placed_set:
                continue
            if len(placed) >= slot_cap:
                break
            estimate = _token_estimate(digests[rid])  # crude 4-chars/token estimate (labeled)
            if r.tokens_used + estimate > token_cap:
                r.token_exhausted = True
                continue  # keep scanning: smaller items may still fit
            placed.append(rid)
            placed_set.add(rid)
            r.tokens_used += estimate

    _fill_stimulus(max(len(placed), shelf_cap - stm_reserved_slots - len(self_placed)),
                   total_tokens - stm_reserved_tokens)

    # STM component (unchanged mechanics; self members never eat STM cap).
    stm_tokens_used = 0
    if stm_hot:
        stm_token_cap = min(stm_reserved_tokens, total_tokens - r.tokens_used)
        missing = [rid for rid in stm_hot if rid not in universe]
        fetched_hot: Dict[str, TripleAssertion] = {}
        for scope, owner in scope_pairs:
            still = [rid for rid in missing if rid not in fetched_hot]
            if not still:
                break
            fetched_hot.update(fetch_by_ids(store, still, scope, owner))
        for rid in stm_hot:
            if len(stm_placed) >= stm_slots or _shelf_full():
                break
            if rid in placed_set:
                continue  # overlap: rode an earlier fill; label decides meaning
            cand = universe.get(rid)
            if cand is None:
                a = fetched_hot.get(rid)
                if a is None:
                    continue  # hot id not resolvable in the searched scopes
                cand = add_candidate(universe, a, "stm", excluded_ids)
                if cand is None:
                    continue  # edge assertion or excluded: conducts, never a member
                digests[rid] = handle_digest(cand.assertion)
            # min_activation keeps its working-set-membership meaning and
            # gates STM members too (total activation, matched or not).
            if view == "working_set" and budget.min_activation is not None:
                if base_of(rid) + cand.spread < float(budget.min_activation):
                    continue
            estimate = _token_estimate(digests.setdefault(rid, handle_digest(cand.assertion)))
            if stm_tokens_used + estimate > stm_token_cap:
                r.dropped.append({"record_id": rid, "score": float(base_activation.get(rid, 0.0)),
                                  "reason": "stm_capped"})
                continue
            stm_placed.append(rid)
            placed_set.add(rid)
            stm_tokens_used += estimate
    r.tokens_used += stm_tokens_used

    # Stimulus remainder: unused reservations return to the stimulus order.
    _fill_stimulus(shelf_cap - len(stm_placed) - len(self_placed), total_tokens)
    for rid in ordered:
        if rid not in placed_set:
            reason = "budget_exhausted" if r.token_exhausted else "below_shelf"
            r.dropped.append({"record_id": rid, "score": universe[rid].fused, "reason": reason})

    # Admission labels (precedence self > both > stm > stimulus; rationale
    # in the module docstring — presence ≠ use keys off these). An STM-FILL
    # placement is ALWAYS "stm", even when weakly channel-matched: a match
    # that lost the stimulus fill did not earn admission — the trail caused
    # the presence, and labeling it "both" would full-deposit every render
    # (live-proven: a trail-hot record with stopword-grade keyword overlap
    # re-deposited each turn and never decayed). "both" is reserved for
    # records the STIMULUS fill seated while trail-hot AND matched.
    for rid in stm_placed:
        r.admissions[rid] = "self" if rid in self_set else "stm"
    for rid in self_placed:
        r.admissions[rid] = "self"
    for rid in placed:
        if rid in self_set:
            r.admissions[rid] = "self"
        elif rid in stm_hot_set:
            r.admissions[rid] = "both" if universe[rid].channel_matched else "stm"
        else:
            r.admissions[rid] = "stimulus"

    r.handle_order = (*self_placed, *stm_placed, *placed)
    r.self_placed = tuple(self_placed)
    r.stm_placed = tuple(stm_placed)
    r.placed = tuple(placed)
    return r
