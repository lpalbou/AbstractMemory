"""MemorySystem — the layer-2 facade implementing the frozen runtime⇄memory seam v1.

Authoritative shape source: a2a/threads/0001-runtime-memory-orchestration/004-memory--to--runtime.md
System of record: docs/backlog/proposed/memory_system_v1/0027 (seam) + 0024 (facade).

The facade stays THIN by contract (0024: "keep the facade boring"): it wires
construction and delegates — as-of folds + ablation modes to folds.py, the
pure pipeline to reconstruct.py, record encoding/payloads to records.py,
commit derivations to selection.py, scoring/writers to attention.py.

Seam contracts honored here (a2a 0001/004, "I will not move these"):
1. `reconstruct` is a PURE READ; `journal=True` appends ONE trace + inert
   'listed' audit events that never affect scores; `journal=False` writes
   nothing at all.
2. `commit_selection` is the ONLY strengthening path (idempotent by
   trace_id); deliberate acts always require a `reason`.
3. Relevance admits, activation reorders (enforced in shelf.order_members).
4. Every result carries `as_of_seq`; degradations are labeled `#FALLBACK`.
   v1 limitation (a2a 0001/005): as_of anchors JOURNAL-derived signals only
   — store truth is read CURRENT, so the runtime replays from its ledger.

Id namespaces (audit fix 2): every id-taking call accepts BOTH the
digest-assertion id (handle.record_id) and the graph id (remember_many's
ex:… return) — resolution is works-or-loud, never silent (records.py).
This module never imports abstractcore/abstractruntime (0024 hard boundary);
LLM-adjacent steps arrive only as injected protocols (embedder/selector/reflector).
"""

from __future__ import annotations

import uuid
import warnings
from dataclasses import replace
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .attention import (
    AttentionConfig,
    attenuate as _attenuate_event,
    compute_activation,
    mark_selected as _mark_selected,
    ranking_boost as _ranking_boost,
    refocus as _refocus_event,
    reinforce as _reinforce_event,
)
from .folds import (
    reconstruction_inputs as _reconstruction_inputs,
    scoring_window as _scoring_window,
)
from .gradation import GradationConfig
from .journal import DEFAULT_WEIGHTS as _DEFAULT_WEIGHTS
from .journal import ClosureRecord, MemoryEvent, MemoryJournal, ScopeBinding, utc_now_iso
from .models import TripleAssertion
from .records import (
    MemoryRecordInput,
    ReconstructConfig,
    apply_formation_plan as _apply_formation_plan,
    build_formation_plan as _build_formation_plan,
    close_record_plan as _close_record_plan,
    read_payload as _read_payload,
    resolve_assertion_ids as _resolve_assertion_ids,
)
# _normalize_scopes is shared with the pipeline: the broad-scope guard must
# see scopes exactly as run_reconstruction will (lowercased, deduped), or a
# case variant like ("Global", ...) could slip past the escalation check.
from .reconstruct import _normalize_scopes, run_reconstruction
from .seam import ActiveMemorySnapshot, RecallBudget, ReconstructionResult, Stimulus
from .selection import (
    display_rows as _display_rows,
    normalize_used_ids as _normalize_used_ids,
    plan_selection as _plan_selection,
    selection_event_id as _selection_event_id,
    selection_snapshot_id as _selection_snapshot_id,
)
from .spreading import SpreadParams
from .store import TripleQuery, TripleStore
from .system_access import AccessOps
from .system_valence import ValenceOps

__all__ = ["MemorySystem"]

# Scopes whose search requires an explicit escalation_reason (0020 escalation
# discipline: broad recall is an audited decision, never a silent default).
_DEFAULT_BROAD_SCOPES = frozenset({"global"})

# Emergence-experiment ablations (a2a 0002/001; construction flag — one arm
# per run): "recency_embedding" = recency+channels, no activation/spreading;
# "recency" = channels disabled too (pure chat-history baseline). Read-side
# semantics live in folds.py.
_ABLATIONS = frozenset({"recency_embedding", "recency"})

# Payload fidelity tiers reserved until 0021 lands (v1 serves digest + raw).
_RESERVED_PAYLOAD_TIERS = frozenset({"summary", "compact"})


class MemorySystem(ValenceOps, AccessOps):
    """Layer-2 memory system: remember, reconstruct, commit, focus — over
    injected layer-1 parts. See the module docstring for the contracts.
    Lifecycle: `close()` releases the JOURNAL only; the store is caller-owned
    (layer 1 stays independently usable — 0024 layering decision). Mixins
    (600-line rule): ValenceOps = appraise/heal_scar/break_bond/gradation;
    AccessOps = access_counts + self_records (folded identity core)."""

    def __init__(
        self, *, store: TripleStore, journal: MemoryJournal,
        embedder: Any = None, selector: Any = None, reflector: Any = None,
        attention_config: AttentionConfig = AttentionConfig(),
        spread_params: SpreadParams = SpreadParams(),
        reconstruct_config: ReconstructConfig = ReconstructConfig(),
        gradation_config: GradationConfig = GradationConfig(),
        clock: Optional[Callable[[], str]] = None,
        broad_scopes: Optional[Iterable[str]] = None,
        ablation: Optional[str] = None,
    ) -> None:
        if store is None or journal is None:
            raise ValueError("MemorySystem requires both a store and a journal (layer-1 substrate)")
        self._store = store
        self._journal = journal
        self._embedder = embedder
        # selector/reflector are accepted + stored but UNUSED in v1 (0020's
        # selector hook / 0023's reflector land later); the warnings keep the
        # degradation honest (0024 startup-honesty rule).
        self._selector = selector
        self._reflector = reflector
        if selector is not None:
            warnings.warn("#FALLBACK: selector refinement not implemented in v1; "
                          "heuristic shelf only", RuntimeWarning, stacklevel=2)
        if reflector is not None:
            warnings.warn("#FALLBACK: reflector consolidation not implemented in v1; "
                          "sleep() lands with backlog 0023", RuntimeWarning, stacklevel=2)
        self._attention_config = attention_config
        self._spread_params = spread_params
        # 2026-07-10 review F1/F2: both configs were root-exported as the
        # tuning surface yet UNREACHABLE through the facade (constructed
        # fresh with defaults at every internal call site). The vector
        # floor/margin knobs are embedder-dependent by the code's own
        # documentation — a host with a third embedder profile needs them.
        self._reconstruct_config = reconstruct_config
        self._gradation_config = gradation_config
        self._clock: Callable[[], str] = clock if clock is not None else utc_now_iso
        self._broad_scopes = (
            frozenset(str(s or "").strip().lower() for s in broad_scopes if str(s or "").strip())
            if broad_scopes is not None
            else _DEFAULT_BROAD_SCOPES
        )
        # Ablation arm (a2a 0002/001): READ-side only — Arm B ignores the
        # journal during reconstruct while ALL write paths stay live, so both
        # arms build IDENTICAL journal histories (one substrate, two readers).
        normalized_ablation = str(ablation or "").strip().lower() or None
        if normalized_ablation is not None and normalized_ablation not in _ABLATIONS:
            raise ValueError(
                f"unknown ablation {ablation!r}; valid: None (full engine), "
                "'recency_embedding' (Arm B: no activation/spreading), "
                "'recency' (pure recency baseline: channels disabled too)")
        self._ablation = normalized_ablation

    # -- layer-1 passthroughs (unchanged surface; part of the frozen protocol) --

    @property
    def store(self) -> TripleStore:
        """The layer-1 store handle (read-only property — sleep passes and
        other same-package processes composed OVER the facade used to reach
        into `_store`; review: privates are not a composition surface)."""
        return self._store

    @property
    def journal(self) -> MemoryJournal:
        """The layer-1 journal handle (read-only property; see `store`)."""
        return self._journal

    def add(self, assertions: Iterable[TripleAssertion]) -> List[str]:
        """Layer-1 write passthrough (the seam keeps MEMORY_KG_* effects working)."""
        return self._store.add(assertions)

    def query(self, q: TripleQuery) -> List[TripleAssertion]:
        """Layer-1 read passthrough. NOTE: direct id-lookups intentionally
        bypass closure AND binding folds (audit completeness — TripleQuery
        contract); ranked retrieval via reconstruct() is where they apply."""
        return self._store.query(q)

    # -- formation (a2a 0001/009 addendum 1, 0001/011 ask 1; v1 bridge to 0021) --

    def remember_many(
        self, records: Sequence[MemoryRecordInput], *, scope: str,
        owner_id: str, idempotency_key: str, turn_id: Optional[str] = None,
    ) -> List[str]:
        """Form typed memory records: the pressure-independent graph feeder
        (verbatim stays a host `payload_ref`; the digest is stored + indexed
        and selectable the same turn). Encoding + identity live in
        records.py: ids derive from (idempotency_key, position); edges may
        reference batch siblings as "local:<i>"; each record gets an
        indexed/inactive ScopeBinding (source="remember"). IDEMPOTENT:
        replays re-derive identical ids (store pre-check + OR IGNORE +
        journal dedup). No attention event at formation BY DESIGN: forming
        is not using (0018). Returns record_ids in input order.
        """
        plan = _build_formation_plan(
            records, scope=scope, owner_id=owner_id,
            idempotency_key=idempotency_key, turn_id=turn_id,
        )
        return _apply_formation_plan(self._store, self._journal, plan)

    def remember(
        self, record: MemoryRecordInput, *, scope: str, owner_id: str,
        idempotency_key: str, turn_id: Optional[str] = None,
    ) -> str:
        """Single-record convenience over remember_many (same idempotency)."""
        return self.remember_many(
            [record], scope=scope, owner_id=owner_id,
            idempotency_key=idempotency_key, turn_id=turn_id,
        )[0]

    def _boost(self, base_level: float) -> float:
        # Config-driven: the injected AttentionConfig owns boost_scale/max_boost.
        return _ranking_boost(base_level, config=self._attention_config)

    # -- the seam: reconstruct -------------------------------------------------

    def reconstruct(
        self, stimulus: Stimulus, *, scopes: Sequence[Tuple[str, str]],
        budget: RecallBudget = RecallBudget(), view: str = "shelf",
        escalation_reason: Optional[str] = None, journal: bool = True,
        trace_id: Optional[str] = None,
    ) -> ReconstructionResult:
        """One reconstruction — one call, two views (seam v1).

        Read path: resolves `as_of` (stimulus.as_of, else current_seq),
        folds activation/trails/closures/bindings ≤ as_of, and hands
        everything to the pure pipeline, which returns the UNION working
        set: SELF (prompt-active bindings, budget.self_fraction,
        admission="self") + STM (trail-hot, budget.stm_fraction, "stm") +
        stimulus ("stimulus"/"both"). `as_of_seq` is the replay anchor;
        REPLAY LIMITATION (a2a 0001/005): store truth reads CURRENT.

        Write path: `journal=True` appends the trace + one inert 'listed'
        audit event per handle (never scored: reading is not using, 0018);
        `journal=False` writes nothing. Broad scopes require an
        escalation_reason (0020 §5). trace_id: None = fresh uuid4 per call;
        SUPPLYING one makes the journaled read replay-safe (trace dedupes,
        'listed' ids derive from it → re-calls write ZERO rows; pin
        Stimulus.as_of for byte-identical results). Caller owns uniqueness.
        """
        if view not in ("shelf", "working_set"):
            raise ValueError(f"view must be 'shelf' or 'working_set', got {view!r}")
        if trace_id is not None and not (isinstance(trace_id, str) and trace_id.strip()):
            raise ValueError(
                f"trace_id must be a non-empty string when supplied (got {trace_id!r}); "
                "pass None for a fresh per-call trace identity")
        tid = trace_id.strip() if isinstance(trace_id, str) else uuid.uuid4().hex
        scope_pairs = _normalize_scopes(scopes)
        if not scope_pairs:
            raise ValueError(
                "reconstruct requires at least one (scope, owner_id) pair with a "
                "non-empty scope — an empty scope ladder can never match anything")

        reason = str(escalation_reason or "").strip() or None
        broad = sorted({s for s, _ in scope_pairs if s in self._broad_scopes})
        if broad and reason is None:
            raise ValueError(
                f"reconstruct over broad scope(s) {broad} requires a non-empty escalation_reason "
                "explaining why narrower scopes are insufficient (broad recall is an explicit, "
                "audited decision). Pass escalation_reason=..., or drop the broad scope.")

        # Replay-anchor boundary validation: an anchor outside
        # [0, current_seq] was never issued by THIS journal — drift must be
        # a loud error, never a silent "latest" (a2a 0001/004 contract 4).
        current = self._journal.current_seq()
        as_of = current if stimulus.as_of is None else int(stimulus.as_of)
        if not (0 <= as_of <= current):
            raise ValueError(
                f"Stimulus.as_of={as_of} is not a valid anchor for this journal "
                f"(current_seq={current}). Pass an as_of_seq previously returned by "
                "reconstruct() on this journal, or None for latest.")
        # ONE fold assembly (folds.py) derives every journal input and owns
        # ablation read-modes (per-arm channel/activation switches + notes).
        inputs = _reconstruction_inputs(
            self._store, self._journal, scope_pairs, as_of,
            config=self._attention_config,
            spread_params=self._spread_params,
            pipeline_config=self._reconstruct_config,
            ablation=self._ablation,
        )

        result, trace = run_reconstruction(
            store=self._store,
            stimulus=stimulus,
            scopes=scope_pairs,
            budget=budget,
            view=view,
            base_activation=inputs.base,
            trail_activation=inputs.trails,
            activation_contributions=inputs.contributions,
            excluded_ids=inputs.excluded,
            bindings=inputs.bindings,
            embedder=self._embedder,
            spread_params=inputs.spread_params,
            as_of_seq=as_of,
            trace_id=tid,
            ranking_boost=self._boost,
            config=inputs.pipeline_config,
            run_channels=inputs.run_channels,
            run_spreading=inputs.run_spreading,
            prompt_active=inputs.prompt_active,
            global_count_of=inputs.global_count_of,
        )
        if inputs.notes:
            # The arm must be provable from every persisted result AND trace.
            result = replace(result, warnings=result.warnings + inputs.notes)
            trace = replace(trace, warnings=trace.warnings + inputs.notes)

        if journal:
            # Stamp escalation_reason (facade policy); turn_id rides audit
            # provenance. Supplied trace_id => both appends are replay-safe.
            self._journal.append_trace(replace(trace, escalation_reason=reason))
            listed_provenance = {"turn_id": stimulus.turn_id} if stimulus.turn_id else {}
            listed = [
                MemoryEvent(
                    kind="listed",  # audit-only: recorded for explainability, never scored
                    scope=h.scope,
                    owner_id=h.owner_id,
                    record_id=h.record_id,
                    trace_id=result.trace_id,
                    query_fingerprint=trace.query_fingerprint,
                    actor="system",
                    provenance=dict(listed_provenance),
                    event_id=_selection_event_id(tid, "listed", h.record_id) if trace_id is not None else "",
                )
                for h in result.handles
            ]
            if listed:
                self._journal.append_events(listed)
        return result

    # -- active reconstruction: probe / expand / recall reads ---------------

    def probe(
        self, stimulus: Stimulus, *, scopes: Sequence[Tuple[str, str]],
        reason: str, effort: Any = "standard", journal: bool = True,
        trace_id: Optional[str] = None,
    ) -> "ProbeResult":
        """The deliberate reach (0022, fork 090/091 shape): channels-only
        active reconstruction EXEMPT from the shelf race — no identity
        seats, no STM union, no activation boost. `reason` is MANDATORY
        (an audited escalation, landing on the trace); `effort` is
        "quick" | "standard" | "deep" (the Mnemosyne active-reconstruction
        vocabulary) or a custom ProbeBudget. Broad scopes require no extra
        reason: the probe reason IS the escalation reason. Pure read;
        journal=True writes the trace + inert audit events. Deposits
        happen only if the host commits displayed hits via
        commit_selection (the one strengthening path)."""
        from .probe import probe as _probe

        scope_pairs = _normalize_scopes(scopes)
        if not scope_pairs:
            raise ValueError("probe requires at least one (scope, owner_id) pair")
        current = self._journal.current_seq()
        as_of = current if stimulus.as_of is None else int(stimulus.as_of)
        if not (0 <= as_of <= current):
            raise ValueError(
                f"Stimulus.as_of={as_of} is not a valid anchor for this journal "
                f"(current_seq={current}) — same boundary rule as reconstruct")
        inputs = _reconstruction_inputs(
            self._store, self._journal, scope_pairs, as_of,
            config=self._attention_config, spread_params=self._spread_params,
            pipeline_config=self._reconstruct_config, ablation=self._ablation,
        )
        return _probe(
            self._store, self._journal, stimulus=stimulus, scopes=scope_pairs,
            reason=reason, effort=effort, embedder=self._embedder,
            excluded_ids=set(inputs.excluded), config=inputs.pipeline_config,
            as_of_seq=as_of, trace_id=trace_id, write_journal=bool(journal),
        )

    def probe_expand(
        self, record_ids: Sequence[str], *, reason: str, depth: int = 1,
        max_records: int = 12, token_budget: int = 1600,
        scopes: Optional[Sequence[Tuple[str, str]]] = None,
        parent_trace_id: Optional[str] = None, journal: bool = True,
        trace_id: Optional[str] = None,
    ) -> "ProbeResult":
        """Bounded source expansion from chosen records (the probe's second
        disclosure step): BFS over record edges in BOTH directions, honoring
        closure AND hidden folds, contained to the roots' scopes when the
        caller names none. Root ids resolve through both namespaces (row or
        graph); unknown roots refuse loudly. Deposits nothing."""
        from .probe import probe_expand as _expand
        from .records import resolve_digest_assertion

        scope_pairs = _normalize_scopes(scopes) if scopes else []
        if not scope_pairs:
            # Derive containment from the ROOTS' own scope pairs (adversary
            # F4: a scopeless expand must neither skip the hidden fold nor
            # pull digests from scopes the caller never named).
            derived: List[Tuple[str, str]] = []
            for rid in record_ids or ():
                digest = resolve_digest_assertion(self._store, str(rid or "").strip())
                if digest is not None:
                    pair = (digest.scope, digest.owner_id or "")
                    if pair not in derived:
                        derived.append(pair)
            scope_pairs = derived
        as_of = self._journal.current_seq()
        excluded: set = set()
        if scope_pairs:
            inputs = _reconstruction_inputs(
                self._store, self._journal, scope_pairs, as_of,
                config=self._attention_config, spread_params=self._spread_params,
                pipeline_config=self._reconstruct_config, ablation=self._ablation,
            )
            excluded = set(inputs.excluded)
        else:
            from .folds import closure_exclusions

            excluded = set(closure_exclusions(self._journal, as_of))
        return _expand(
            self._store, self._journal, record_ids=record_ids, reason=reason,
            depth=depth, max_records=max_records, token_budget=token_budget,
            excluded_ids=excluded, scope_pairs=scope_pairs,
            parent_trace_id=parent_trace_id,
            as_of_seq=as_of, trace_id=trace_id, write_journal=bool(journal),
        )

    def situate(
        self, *, scopes: Sequence[Tuple[str, str]],
        at: Optional[str] = None, seq: Optional[int] = None,
        participant: Optional[str] = None, occurrence: str = "first",
        budget: Optional["SituateBudget"] = None,
    ) -> Dict[str, Any]:
        """Rebuild the full context of a past moment (0034 — the temporal
        graph made usable): anchor by time (ISO/seq) or RELATION ("when I
        first/last met X"), get back the moment's working set, what was
        warm, the period's records, elected diary entries, the identity
        AS OF then, the identity EVOLUTION since (what may help — or
        hinder — resuming the path), and the tensions open at that time.
        PURE READ, everything labeled historical, deposits nothing:
        re-living is a deliberate act (re-enter via anchor_record_ids on
        a normal reconstruct), never a side effect of looking back."""
        from .situate import SituateBudget as _Budget, situate as _situate

        return _situate(
            self._store, self._journal, scopes=_normalize_scopes(scopes),
            at=at, seq=seq, participant=participant, occurrence=occurrence,
            budget=budget if budget is not None else _Budget(),
            attention_config=self._attention_config,
            config=self._reconstruct_config,
        )

    def recall_history(
        self, record_id: str, *, scope: Optional[str] = None,
        owner_id: str = "", limit_traces: int = 200,
    ) -> Dict[str, Any]:
        """Why was X (never) recalled — the explainability read (fork 605).
        History over recent traces (selected/dropped/candidate-only per
        trace, with reasons) plus, when scope is given, the structural
        absence diagnosis (closed? hidden? keyword/vector-reachable?).
        Pure read; writes nothing."""
        from .recall_reads import absence_diagnosis, recall_history as _history

        # store= threads BOTH id namespaces through the trace join (row ids
        # from probe hits, graph ids from edges — one input id answers both
        # halves correctly).
        out = _history(self._journal, record_id,
                       limit_traces=limit_traces, store=self._store)
        if scope is not None:
            out["diagnosis"] = absence_diagnosis(
                self._store, self._journal, record_id,
                scope=scope, owner_id=owner_id)
        return out

    # -- disposal: waking evidence decides (fork 690/360/470) ---------------

    def confirm_relation(
        self, source_id: str, relation: str, target_id: str, *,
        evidence_ids: Sequence[str], reason: str,
        proposed_by: Optional[str] = None, actor: str = "operator",
    ) -> Dict[str, Any]:
        """Turn a sleep proposal into a REAL typed edge (engraved vocabulary
        only; evidence mandatory; the proposing dream can never be its own
        evidence). Idempotent by (source, relation, target)."""
        from .disposal import confirm_relation as _confirm

        return _confirm(
            self._store, self._journal, source_id=source_id, relation=relation,
            target_id=target_id, evidence_ids=evidence_ids, reason=reason,
            proposed_by=proposed_by, actor=actor)

    def promote_candidate(
        self, record_id: str, *, scope: str, owner_id: str,
        corroborating_ids: Sequence[str], reason: str, min_origins: int = 2,
        prompt_state: Optional[str] = None, actor: str = "operator",
    ) -> Dict[str, Any]:
        """Promote an inactive candidate — refused without independent-origin
        corroboration (fork 470: repetition is not corroboration; the
        bridge-attractor counter, loud)."""
        from .disposal import promote_candidate as _promote

        return _promote(
            self._store, self._journal, record_id=record_id, scope=scope,
            owner_id=owner_id, corroborating_ids=corroborating_ids,
            reason=reason, min_origins=min_origins, prompt_state=prompt_state,
            actor=actor)

    def reject_candidate(
        self, record_id: str, *, scope: str, owner_id: str, reason: str,
        hide: bool = False, actor: str = "operator",
    ) -> Dict[str, Any]:
        """The honest no: lifecycle='rejected' with a mandatory reason;
        stays indexed unless hide=True (judgment is not erasure)."""
        from .disposal import reject_candidate as _reject

        return _reject(
            self._store, self._journal, record_id=record_id, scope=scope,
            owner_id=owner_id, reason=reason, hide=hide, actor=actor)

    def dispose_dream(
        self, dream_id: str, *, disposition: str, reason: str,
        relation: Optional[str] = None, source_id: Optional[str] = None,
        target_id: Optional[str] = None, evidence_ids: Sequence[str] = (),
        actor: str = "operator",
    ) -> Dict[str, Any]:
        """One call for the dream verdict: confirmed (edge + supersede) or
        dissolved (retract). Composes confirm_relation + close_record."""
        from .disposal import dispose_dream as _dispose

        return _dispose(
            self, dream_id=dream_id, disposition=disposition, reason=reason,
            relation=relation, source_id=source_id, target_id=target_id,
            evidence_ids=evidence_ids, actor=actor)

    # -- the seam: commit_selection ---------------------------------------------

    def commit_selection(
        self, trace_id: str, used_record_ids: Sequence[str], *,
        prompt_token_estimate: Optional[int] = None,
    ) -> ActiveMemorySnapshot:
        """Deposit the usage trail for records that ACTUALLY entered a context.

        The seam's ONLY strengthening path (contract 2): one 'selected'
        event per used record + 'co_selected' pair trails — ALL co-use
        pairs within the depositing slice, plus term-sharing (raw triples)
        and spreading-hop pairs over recorded edges (selection.py). PRESENCE ≠ USE (union model): trace-labeled
        admission="stm" ids deposit NOTHING by default (rehearsal dial:
        AttentionConfig.stm_rehearsal_weight) — only stimulus/"both"/
        unlabeled ids strengthen. Events group per (scope, owner); cross-
        group pairs land in the FIRST-used member's group; multi-group
        appends are not atomic (append-only; partial state replays). Both
        id namespaces accepted. The snapshot records ALL used ids +
        admission labels; unknown ids raise; trace_id is by reference.
        IDEMPOTENT BY trace_id (0001/011 ask 2): a re-call whose trace has
        a snapshot returns it UNCHANGED, writing nothing; event/snapshot
        ids derive from (trace_id, kind, canonical key), so a crash BETWEEN
        event appends and snapshot append also replays as journal no-ops.
        """
        tid = str(trace_id or "").strip()
        if not tid:
            raise ValueError("commit_selection requires a non-empty trace_id")
        ordered = list(dict.fromkeys(  # both namespaces -> digest assertion ids
            _resolve_assertion_ids(self._store, _normalize_used_ids(used_record_ids)).values()
        ))

        existing = self._journal.snapshots(trace_id=tid, limit=1)
        if existing:
            # Trail already deposited. A differing replay used set is a caller
            # bug worth surfacing; the first commit remains the truth.
            if set(existing[0].used_record_ids) != set(ordered):
                warnings.warn(
                    f"#FALLBACK: commit_selection replay for trace {tid} carries a different "
                    f"used set ({sorted(ordered)} vs {sorted(existing[0].used_record_ids)}); "
                    "returning the original snapshot unchanged (one trace = one commit)",
                    RuntimeWarning, stacklevel=2)
            return existing[0]

        rows = self._store.query(TripleQuery(assertion_ids=tuple(ordered), limit=0))
        fetched: Dict[str, TripleAssertion] = {
            a.assertion_id: a for a in rows if isinstance(a.assertion_id, str) and a.assertion_id
        }
        missing = [rid for rid in ordered if rid not in fetched]
        if missing:
            raise ValueError(
                f"commit_selection: record ids not found in the store: {missing} — "
                "only records that actually entered the context may be committed"
            )

        # PRESENCE ≠ USE: STM-only ids were rendered from the trail itself —
        # a full re-deposit would make STM self-reinforcing (saturates in ~6
        # turns, permanently un-evictable). Unlabeled ids (foreign/stub
        # traces, journal=False reads) keep the full deposit.
        trace_rows = self._journal.traces(trace_id=tid, limit=1)
        admissions = dict(trace_rows[0].admissions) if trace_rows else {}
        labels = {rid: str(admissions.get(rid, "stimulus")) for rid in ordered}
        # Non-depositing admissions (seam v1.2 delta 4): stm/self (and the
        # reserved "historical") are presence, not use. Only stm gets the
        # rehearsal dial — a self member's persistence IS its binding.
        skip = {"stm", "self", "historical"}
        deposit = [rid for rid in ordered if labels[rid] not in skip]
        rehearsal = [rid for rid in ordered if labels[rid] == "stm"]

        # snapshot_id doubles as the events' context_ref (trace-derived, so a
        # crash replay re-derives the same linkage); the store enables the
        # edge-based Hebbian pairs (audit fix 5).
        snapshot_id = _selection_snapshot_id(tid)
        for (scope, owner), payload in _plan_selection(deposit, fetched, store=self._store).items():
            _mark_selected(
                self._journal, payload["records"], pairs=payload["pairs"],
                scope=scope, owner_id=owner, trace_id=tid,
                context_ref=snapshot_id, actor="runtime",
                event_id_factory=lambda kind, key: _selection_event_id(tid, kind, key),
            )
        rehearsal_weight = float(self._attention_config.stm_rehearsal_weight)
        if rehearsal and rehearsal_weight > 0.0:
            # Rehearsal dial: weight-scaled record events only — rendering
            # from the trail is never co-use, so no pair trails.
            groups: Dict[Tuple[str, str], List[str]] = {}
            for rid in rehearsal:
                groups.setdefault((fetched[rid].scope, fetched[rid].owner_id or ""), []).append(rid)
            for (scope, owner), rids in groups.items():
                _mark_selected(
                    self._journal, rids, pairs=(), scope=scope, owner_id=owner,
                    trace_id=tid, context_ref=snapshot_id, actor="runtime",
                    event_id_factory=lambda kind, key: _selection_event_id(tid, kind, key),
                    selected_weight=rehearsal_weight,
                )

        snapshot = ActiveMemorySnapshot(
            snapshot_id=snapshot_id,
            # seq stays at the -1 default: the journal owns the axis and assigns.
            trace_id=tid,
            used_record_ids=tuple(ordered),  # display truth: ALL used ids
            display=tuple(_display_rows(ordered, fetched)),
            prompt_token_estimate=int(prompt_token_estimate) if prompt_token_estimate is not None else None,
            observed_at=self._clock(),
            provenance={"used_count": len(ordered), "admissions": labels},
        )
        return self._journal.append_snapshot(snapshot)

    # -- deliberate acts (thin wrappers over attention writers) -----------------

    # Deliberate acts share idempotency passthrough (0001/015 ask 1,
    # at-least-once effects): a supplied event_id makes replays journal
    # no-ops returning the ORIGINAL event id; actor/provenance ride the
    # event. reason stays mandatory; either id namespace accepted.

    def reinforce(
        self, record_id: str, *, reason: str, weight: float = _DEFAULT_WEIGHTS["pinned"],
        ttl_activity: Optional[int] = None, scope: str, owner_id: str,
        event_id: Optional[str] = None, actor: str = "operator",
        provenance: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Deliberate strengthen (kind='pinned'); returns the event id.
        weight clamps to 1..25 (journal schema)."""
        return self._deliberate_act(
            _reinforce_event, record_id, reason=reason, weight=weight,
            ttl_activity=ttl_activity, scope=scope, owner_id=owner_id,
            event_id=event_id, actor=actor, provenance=provenance)

    def attenuate(
        self, record_id: str, *, reason: str, weight: float = _DEFAULT_WEIGHTS["silenced"],
        ttl_activity: Optional[int] = None, scope: str, owner_id: str,
        event_id: Optional[str] = None, actor: str = "operator",
        provenance: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Deliberate weaken (kind='silenced'); returns the event id. A
        nudge toward invisibility, never negative relevance — closure is
        removal."""
        return self._deliberate_act(
            _attenuate_event, record_id, reason=reason, weight=weight,
            ttl_activity=ttl_activity, scope=scope, owner_id=owner_id,
            event_id=event_id, actor=actor, provenance=provenance)

    def _deliberate_act(self, writer: Callable[..., Any], record_id: str, **kw: Any) -> str:
        [rid] = _resolve_assertion_ids(self._store, [record_id]).values()
        return writer(self._journal, rid, **kw).event_id

    def refocus(
        self, *, reason: str, scope: str, owner_id: str,
        event_id: Optional[str] = None, actor: str = "operator",
        provenance: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Topic-shift marker: accelerates decay of everything older than it
        in the (scope, owner) stream; returns the event id."""
        return _refocus_event(
            self._journal, reason=reason, scope=scope, owner_id=owner_id,
            event_id=event_id, actor=actor, provenance=provenance).event_id

    # -- inspection --------------------------------------------------------------

    def activation(
        self, record_ids: Optional[Sequence[str]] = None, *,
        scope: str, owner_id: str, at_seq: Optional[int] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Stored activation per record: {"base_level": b, "total": b} (v1).
        No "spread" component BY DESIGN (spread is per-stimulus, never
        stored). Requested ids accept BOTH namespaces (audit fix 2), keyed
        in the output AS PASSED; unknown ids raise (a silent zero for a hot
        record was exactly the audit trap). When record_ids is omitted, only
        in-window-scored records return (journal-keyed, no resolution).
        """
        anchor = int(at_seq) if at_seq is not None else self._journal.current_seq()
        events = _scoring_window(
            self._journal, scope=scope, owner_id=owner_id, until_seq=anchor,
            config=self._attention_config,
        )
        scores = compute_activation(events, config=self._attention_config, at_seq=anchor)
        if record_ids is None:
            return {rid: {"base_level": s.base_level, "total": s.base_level}
                    for rid, s in scores.items()}
        out: Dict[str, Dict[str, float]] = {}
        for requested, rid in _resolve_assertion_ids(self._store, list(record_ids)).items():
            level = scores[rid].base_level if rid in scores else 0.0
            out[requested] = {"base_level": level, "total": level}
        return out

    def payload(self, record_id: str, tier: str = "digest") -> Dict[str, Any]:
        """Pure verbatim-on-demand read (a2a 0001/009 item 2, 0001/011 ask 6).
        digest = the canonical text handle.digest carries; raw = the HOST
        artifact reference (attributes.payload_ref, content=None — the
        runtime resolves it; the package never fetches verbatim); summary/
        compact land with 0021. Record ids resolve via their digest
        assertion, plain assertion ids directly. Explicit id reads bypass
        closure/binding folds (audit completeness).
        """
        rid = str(record_id or "").strip()
        if not rid:
            raise ValueError("payload requires a non-empty record_id")
        requested = str(tier or "").strip().lower()
        if requested in _RESERVED_PAYLOAD_TIERS:
            raise NotImplementedError(
                f"payload tier {requested!r} is not implemented in v1: payload tiers beyond "
                "digest land with backlog 0021; store verbatim via attributes.payload_ref "
                "meanwhile and keep rendering the digest tier")
        if requested not in ("digest", "raw"):
            raise ValueError(
                f"unknown payload tier {tier!r} (v1 serves 'digest' and 'raw'; "
                f"reserved for 0021: {sorted(_RESERVED_PAYLOAD_TIERS)})")
        return _read_payload(self._store, rid, requested)

    def seq_at(self, iso_ts: str) -> int:
        """Journal passthrough: highest seq observed at/before iso_ts."""
        return self._journal.seq_at(iso_ts)

    def current_seq(self) -> int:
        """Journal passthrough: the current as_of high-water mark."""
        return self._journal.current_seq()

    # -- lifecycle records --------------------------------------------------------

    def close_assertions(
        self,
        assertion_ids: Sequence[str],
        *,
        kind: str,
        replacement_ids: Sequence[str] = (),
        reason: str,
    ) -> List[str]:
        """Append one ClosureRecord per assertion (retract | supersede);
        returns closure ids. Supersede requires replacement_ids; reason is
        mandatory — validated by ClosureRecord BEFORE any append. A multi-
        assertion supersede shares one replacement set. Accepts either id
        namespace; to close a formed record WITH its edges, use
        close_record()."""
        ids = [str(x or "").strip() for x in (assertion_ids or ()) if str(x or "").strip()]
        if not ids:
            raise ValueError("close_assertions requires at least one assertion_id")
        resolved = list(dict.fromkeys(_resolve_assertion_ids(self._store, ids).values()))
        records = [
            ClosureRecord(
                assertion_id=aid, kind=kind, reason=reason,
                replacement_ids=tuple(replacement_ids or ()),
            )
            for aid in resolved  # construct (and validate) ALL before appending ANY
        ]
        return [self._journal.append_closure(rec).closure_id for rec in records]

    def close_record(
        self,
        record_id: str,
        *,
        reason: str,
        kind: str = "retract",
        replacement_ids: Sequence[str] = (),
    ) -> List[str]:
        """Close a WHOLE record as one belief-revision act: its digest
        assertion AND every edge assertion it owns (audit repro5: retracting
        only the digest left tombstone edges routing spread through a dead
        record). Accepts either id namespace. IDEMPOTENCY KEY: closure ids
        derive from sha256(f"{graph_id}|{kind}|{assertion_id}|closure") —
        reason/replacements/timestamps NEVER enter the key — so at-least-
        once replays dedupe at the journal (0001/015 ask 1). Returns the
        closure ids (digest first)."""
        plan = _close_record_plan(
            self._store, record_id, kind=kind,
            replacement_ids=replacement_ids, reason=reason,
        )
        return [self._journal.append_closure(rec).closure_id for rec in plan]

    def bind(
        self, record_id: str, *, scope: str, owner_id: str, search_state: str,
        prompt_state: str = "inactive", lifecycle: str = "none",
        source: str = "operator", reason: Optional[str] = None,
        binding_id: Optional[str] = None,
    ) -> ScopeBinding:
        """Append one scope-binding visibility event (latest seq wins per
        (record_id, scope, owner_id) — 0017 fold). "hidden" removes the
        record from ranked retrieval; re-binding "indexed" restores it. A
        supplied binding_id makes replays journal no-ops (engram derives
        deterministic ids)."""
        return self._journal.append_binding(ScopeBinding(
            record_id=record_id, scope=scope, owner_id=owner_id,
            search_state=search_state, prompt_state=prompt_state,
            lifecycle=lifecycle, source=source, reason=reason,
            binding_id=str(binding_id or "")))

    def close(self) -> None:
        """Release the journal. The store stays OPEN: it is caller-owned
        layer-1 substrate (see class docstring)."""
        self._journal.close()
