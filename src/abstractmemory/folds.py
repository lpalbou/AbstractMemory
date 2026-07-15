"""As-of folds over journal state: the read-side inputs of reconstruction.

One task (split out of system.py to honor the <600-lines-per-file rule):
derive everything `MemorySystem.reconstruct` injects into the pure pipeline
from journal records ≤ as_of — activation inputs (0018), closure exclusions
(0010), and scope-binding visibility (0017) — assembled by
`reconstruction_inputs`, which also owns the READ-side ablation mode for the
emergence experiment (a2a 0002/001). Pure READS only (journal always; the
store solely to materialize binding visibility into assertion ids); no
writes, no facade policy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .attention import AttentionConfig, compute_activation, compute_trail_activation
from .journal import ATTENTION_KINDS, DECAY_MARKER_KINDS, MemoryEvent, MemoryJournal
from .records import ReconstructConfig
from .spreading import SpreadParams
from .store import TripleQuery

__all__ = [
    "ReconstructionInputs",
    "activation_inputs",
    "binding_states",
    "closure_exclusions",
    "reconstruction_inputs",
    "scoring_window",
]

# The scoring window reads ONLY kinds that can move scores (attention events +
# refocus decay markers). Audit kinds are excluded at the QUERY so a flood of
# 'listed'/'shown' records can never displace eligible events from the window
# (same rationale as attention._attention_window, applied one layer earlier).
_SCORING_KINDS: Tuple[str, ...] = tuple(sorted(ATTENTION_KINDS | DECAY_MARKER_KINDS))


def scoring_window(
    journal: MemoryJournal, *, scope: str, owner_id: str, until_seq: int, config: AttentionConfig
) -> List[MemoryEvent]:
    """One (scope, owner) stream, newest-first, ≤ until_seq, pre-filtered to
    scoring kinds, truncated to the attention window. Pulling exactly
    window_limit kinds-filtered events reproduces attention.py's window."""
    return journal.events(
        scope=scope,
        owner_id=owner_id,
        kinds=_SCORING_KINDS,
        until_seq=until_seq,
        limit=config.window_limit,
    )


def activation_inputs(
    journal: MemoryJournal,
    scope_pairs: Sequence[Tuple[str, str]],
    as_of: int,
    *,
    config: AttentionConfig,
) -> Tuple[Dict[str, float], Dict[Tuple[str, str], float], Dict[str, Tuple[str, ...]]]:
    """base_activation + trail_activation + contribution cues per record.

    Streams are scored independently per (scope, owner) — attention.py
    forbids cross-scope bleed — then merged by MAX: a record's standing is
    its strongest anywhere on the searched ladder (sum would double-count
    one usage if a record were journaled in two searched scopes). Strict
    `>` keeps the FIRST (narrowest) scope's score on ties (narrow→broad).
    """
    base: Dict[str, float] = {}
    contributions: Dict[str, Tuple[str, ...]] = {}
    trails: Dict[Tuple[str, str], float] = {}
    for scope, owner in scope_pairs:
        events = scoring_window(journal, scope=scope, owner_id=owner, until_seq=as_of, config=config)
        if not events:
            continue
        scores = compute_activation(events, config=config, at_seq=as_of)
        for rid, score in scores.items():
            if rid not in base or score.base_level > base[rid]:
                base[rid] = score.base_level
                contributions[rid] = score.contributions
        for pair, value in compute_trail_activation(events, config=config, at_seq=as_of).items():
            if pair not in trails or value > trails[pair]:
                trails[pair] = value
    return base, trails, contributions


def closure_exclusions(journal: MemoryJournal, as_of: int) -> frozenset:
    """Closure fold ≤ as_of: retracted AND superseded assertion_ids leave
    ranked retrieval (both closure kinds mean "no longer believed as-is").
    Id-lookups via store.query(assertion_ids=...) bypass this by design
    (audit completeness); reconstruct is ranked retrieval, so it applies.
    """
    return frozenset(c.assertion_id for c in journal.closures(until_seq=as_of, limit=0))


def binding_states(
    store: Any, journal: MemoryJournal, scope_pairs: Sequence[Tuple[str, str]], as_of: int
) -> Tuple[Dict[Tuple[str, str, str], str], frozenset, Tuple[Tuple[str, str, str], ...]]:
    """Bindings fold ≤ as_of per searched (scope, owner) — 0017 enforcement.

    Returns (states, hidden, prompt_active):
    - states: (record_id, scope, owner_id) -> "{search_state}+{prompt_state}"
      display string for the handle `binding` field (honest fold, latest seq
      wins per key). The pipeline consults the SUBJECT-level key first, then
      the assertion-level key, then the default — so record-level bindings
      from remember_many surface on their digest handles.
    - hidden: ASSERTION ids excluded from ranked retrieval, materialized
      against the store (hostile-audit repro1/repro4): a latest-hidden
      binding in pair P excludes exactly the assertions whose OWN
      (scope, owner) is P and whose assertion_id OR subject equals the
      bound record id. Record-level bindings (graph ids) therefore finally
      enforce, and hidden in one pair never vetoes another searched pair
      (fork precedent: per-scope positive checks, not a global veto).
      Direct store.query id-lookups keep bypassing the fold by design
      (audit completeness, same rule as closures).
    - prompt_active: (record_id, scope, owner_id) triples whose FOLDED
      binding is search_state="indexed" AND prompt_state="active" — the
      identity-wave SELF admission source (the fork's <active_memory>
      semantics: binding STATE, not trail; a2a 0003). Deterministic order
      (searched-pair order, then fold order).
    """
    states: Dict[Tuple[str, str, str], str] = {}
    hidden: set = set()
    prompt_active: List[Tuple[str, str, str]] = []
    for scope, owner in scope_pairs:
        for b in journal.bindings(scope=scope, owner_id=owner, fold=True, until_seq=as_of):
            states[(b.record_id, b.scope, b.owner_id)] = f"{b.search_state}+{b.prompt_state}"
            if b.search_state == "indexed" and b.prompt_state == "active":
                prompt_active.append((b.record_id, b.scope, b.owner_id))
            if b.search_state != "hidden":
                continue
            owner_q = b.owner_id or None
            # Assertion-level binding: the bound id itself, IF it lives in
            # the binding's own pair (per-pair enforcement).
            for a in store.query(TripleQuery(assertion_ids=(b.record_id,), scope=b.scope,
                                             owner_id=owner_q, limit=1)):
                if a.assertion_id:
                    hidden.add(a.assertion_id)
            # Record-level binding: every assertion whose SUBJECT is the
            # bound id in that pair (digest + edges of a formed record).
            for a in store.query(TripleQuery(subject=b.record_id, scope=b.scope,
                                             owner_id=owner_q, limit=0)):
                if a.assertion_id:
                    hidden.add(a.assertion_id)
    return states, frozenset(hidden), tuple(prompt_active)


def anchored_universe_exclusions(
    store: Any, journal: MemoryJournal, scope_pairs: Sequence[Tuple[str, str]], as_of: int
) -> Tuple[frozenset, int]:
    """FORMED-BY-T candidate universe gate (durable-visits design §5,
    commons c1269 — closes the future-leak class): store truth has no seq
    axis, so relevance channels (keyword/vector/recents) can admit records
    formed AFTER the anchor into an anchored recall — the entity-at-T
    seeing its own future. The journal DOES know every formation: a formed
    record's first binding seq is its formation position. This gate
    excludes, per searched pair, every record whose binding fold exists at
    head but NOT at ≤ as_of (formed after T), materialized to assertion
    ids exactly like hidden bindings (digest + edge rows by subject).

    Returns (excluded_assertion_ids, post_anchor_record_count).

    HONEST LIMIT (the promise wording in the design doc): rows written
    without journal bindings (raw store.add) carry no formation
    provenance and pass ungated — the anchored promise is "the
    journal-derived view at T over records that existed at T", never
    "the entity exactly as it was"."""
    excluded: set = set()
    post_anchor_records: set = set()
    for scope, owner in scope_pairs:
        # Formation position = the record's FIRST source="remember" binding
        # (the marker situate/dream_resolution/sleep_cadence already key on).
        # Raw rows (fold=False): a folded view collapses to the LATEST
        # binding, which loses the formation row under later state changes
        # (promotion, quarantine) — a record bound hidden after T was not
        # FORMED after T (test_binding_visibility pins that replay).
        first_formed: Dict[Tuple[str, str, str], int] = {}
        for b in journal.bindings(scope=scope, owner_id=owner, fold=False, until_seq=None):
            if b.source != "remember":
                continue
            key = (b.record_id, b.scope, b.owner_id)
            if key not in first_formed or int(b.seq) < first_formed[key]:
                first_formed[key] = int(b.seq)
        pair_post_anchor: set = set()
        for (rid, _b_scope, _b_owner), formed_seq in first_formed.items():
            if formed_seq > int(as_of):
                pair_post_anchor.add(rid)
        post_anchor_records |= pair_post_anchor
        if not pair_post_anchor:
            continue
        # ONE pair scan, not two queries per record (production-audit
        # finding 4): a deep anchor over a real life would otherwise issue
        # thousands of store queries per recall — R3/R4 sessions run this
        # gate EVERY turn. Membership matching does the per-record work.
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            if not a.assertion_id:
                continue
            if a.assertion_id in pair_post_anchor or a.subject in pair_post_anchor:
                excluded.add(a.assertion_id)
    return frozenset(excluded), len(post_anchor_records)


@dataclass(frozen=True)
class ReconstructionInputs:
    """Journal-derived inputs + read-mode for one reconstruction call."""

    base: Dict[str, float]
    trails: Dict[Tuple[str, str], float]
    contributions: Dict[str, Tuple[str, ...]]
    bindings: Dict[Tuple[str, str, str], str]
    excluded: frozenset
    spread_params: SpreadParams
    run_channels: bool                  # False only under ablation="recency"
    run_spreading: bool                 # False under BOTH ablations
    pipeline_config: ReconstructConfig  # kind policy (neutralized under "recency")
    notes: Tuple[str, ...]              # ablation labels for result/trace warnings
    # Identity wave: prompt-active binding triples (self admission source).
    # Deliberately NOT zeroed by ablations — the arms test recall MECHANICS
    # (activation/trails/channels), not identity presence: an ablated entity
    # is still itself, and self admission is binding STATE, orthogonal to
    # the ablated trail machinery.
    prompt_active: Tuple[Tuple[str, str, str], ...] = ()
    # GLOBAL access counts (maintainer's two-count model): read-only lookup
    # into the journal's never-decaying selected counter, surfaced on every
    # handle as provenance["global_count"]. NOT zeroed by ablations (like
    # prompt_active: lifetime importance is not the recall mechanic under
    # test) and NEVER used for ordering/admission — display truth only.
    global_count_of: Callable[[str], int] = lambda rid: 0


def reconstruction_inputs(
    store: Any,
    journal: MemoryJournal,
    scope_pairs: Sequence[Tuple[str, str]],
    as_of: int,
    *,
    config: AttentionConfig,
    spread_params: SpreadParams,
    pipeline_config: Optional[ReconstructConfig] = None,
    ablation: Optional[str] = None,
    anchored: bool = False,
) -> ReconstructionInputs:
    """Assemble every journal-derived input one reconstruction needs, plus
    the ablation read-mode (a2a 0002/001 experiment arms).

    No cumulative prior here: auto-recall scoring must reproduce the
    journaled trail only (0018 fixed contract e — the prior is for
    interactive inspection ranking, never reconstruction).

    Ablations are READ-side only and both zero activation/trails and disable
    spreading (run_spreading=False — the pipeline never starts the walk;
    edges stay empty in both views). The closure/binding folds are
    deliberately KEPT in every arm: ablations disable activation, not belief
    lifecycle, so retracted/hidden records leave ALL arms.

    - "recency_embedding" (Arm B): channels still run — pure recency+channel
      retrieval, activation ignored.
    - "recency" (pure recency baseline): channels DISABLED too — the shelf
      is "the most recent N that fit the budget" (a chat-history baseline);
      stimulus cues, patterns and anchors are ignored, relevance stays
      empty, reserved slots never engage. Kind priority is neutralized
      (empty kind_rank → constant rank), because a chat history does not
      resurface lessons ahead of newer turns: ordering is observed_at desc
      with record_id tie-break, exactly.

    The exclusion folds merge into ONE set (0010 closures + 0017 hidden
    bindings): both mean "not in ranked retrieval", and one set keeps the
    pipeline's exclusion path single.
    """
    ablated = ablation in ("recency_embedding", "recency")
    if ablated:
        base: Dict[str, float] = {}
        trails: Dict[Tuple[str, str], float] = {}
        contributions: Dict[str, Tuple[str, ...]] = {}
    else:
        base, trails, contributions = activation_inputs(journal, scope_pairs, as_of, config=config)
    states, hidden, prompt_active = binding_states(store, journal, scope_pairs, as_of)
    excluded = closure_exclusions(journal, as_of) | hidden
    anchor_notes: Tuple[str, ...] = ()
    if anchored:
        # Explicitly-anchored recall (as_of below head): close the
        # future-leak class before any channel runs. Inert at head by
        # construction (no binding's first seq exceeds current_seq).
        future_ids, future_records = anchored_universe_exclusions(
            store, journal, scope_pairs, as_of)
        excluded = excluded | future_ids
        if future_records:
            # Note only when the gate actually excluded something: an inert
            # anchor (nothing formed since T) stays byte-identical to the
            # original read — the C4 replay contract and this gate are the
            # same promise ("the view at T over records that existed at T"),
            # and a zero-effect note would break replay bytes for nothing.
            anchor_notes = (
                f"anchored recall (as_of={as_of}): {future_records} record(s) formed after the "
                "anchor excluded from the candidate universe; rows without formation bindings "
                "are ungated (store truth has no seq axis)",
            )

    # The facade-threaded config is the base (review F1: ReconstructConfig
    # used to be constructed fresh here, making the exported tuning surface
    # unreachable); a missing config keeps the defaults.
    threaded = pipeline_config if pipeline_config is not None else ReconstructConfig()
    if ablation == "recency":
        run_channels = False
        # Kind priority neutralized (empty kind_rank -> constant rank), the
        # OTHER threaded knobs kept: the arm removes kind resurfacing, not
        # the host's vector-floor calibration.
        pipeline_config = replace(threaded, kind_rank={})
        notes: Tuple[str, ...] = (
            "ablation=recency (pure recency baseline)",
            "ablation=recency: channels disabled — stimulus cues, patterns and anchors are ignored",
        )
    elif ablation == "recency_embedding":
        run_channels = True
        pipeline_config = threaded
        notes = ("ablation=recency_embedding (Arm B)",)
    else:
        run_channels = True
        pipeline_config = threaded
        notes = ()
    # Global counts are anchored to as_of like every other journal-derived
    # input: a C4 replay must see the counts AS OF the anchor, or repeated
    # calls after new commits would produce different handle provenance.
    def _global_count_of(rid: str, _j: MemoryJournal = journal, _hi: int = as_of) -> int:
        return int(_j.selected_count(rid, until_seq=_hi))

    return ReconstructionInputs(
        base=base, trails=trails, contributions=contributions, bindings=states,
        excluded=excluded, spread_params=spread_params, run_channels=run_channels,
        run_spreading=not ablated, pipeline_config=pipeline_config, notes=notes + anchor_notes,
        prompt_active=prompt_active, global_count_of=_global_count_of,
    )
