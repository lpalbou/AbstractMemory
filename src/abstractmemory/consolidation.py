"""Sleep / consolidation / dreams (backlog 0023 v1 — the fork port).

The fork's mechanism, kept faithfully (0007 study, file:line-cited there):
sleep is DETERMINISTIC — zero LLM calls, no invented narratives. A pass
reads every formed record in scope (minus prior dreams — the loop-breaker),
computes graph structure (components, isolated nodes, duplicates), finds
CROSS-COMPONENT pairs sharing weak features, and records at most ONE dream:
the felt residue of maintenance — templated first-person prose, weak
"mentions" links, review-gated, never promotable to fact. Unresolved
dreams CHAIN (parent_dream_ids): recurring dreams about unresolved tension.

SLEEP PROPOSES; WAKING EVIDENCE DISPOSES: the dream never writes a
load-bearing edge; real relationships require awake evidence through the
normal commit channel.

COMPONENT SEMANTICS (red-team 0007 URGENT guard, 2026-07-07): components
are computed over SEMANTIC authored relations ONLY — record_edge
assertions whose predicate is in COMPONENT_RELATIONS (the explicit
allowlist below; URGENT correction 2026-07-07: this docstring previously
IMPLIED an allowlist while the edge scan took every record_edge assertion
regardless of predicate — the policy is now real code, not prose).
co_selected pair trails are EXCLUDED from component computation entirely:
trails are HABIT (usage), not semantic structure, and their all-pairs
transitivity would merge the whole home into ONE component —
cross-component bridges impossible, salience 0 forever, dreams
structurally dead. Trails serve as the PROPOSAL-EXCLUSION signal instead:
a cross-component pair with a warm trail is already associated by use —
nothing to dream about — so it is skipped from proposals AND questions
and counted honestly (trail_associated). MECHANICAL CO-PRESENCE edges
(CONTEXT_RELATIONS, e.g. the diary projection's written_amid) get the
same treatment as trails: never adjacency, but they DO mean "already
associated" — excluded from proposals/questions and counted honestly
(context_associated). DIVERGENCE from runtime's suggestion, deliberate:
`continues` STAYS component-defining — a session chained by continues is
ONE story/island (bounded, honest); the dream target is CROSS-SESSION
insight. The killer was trails (unbounded transitive merging), not typed
authored chains. If continues chains later prove too merging in practice,
the demotion is a one-predicate move between the two sets below.

NAMED DIVERGENCES from the fork (our architecture rules where they clash):
- No rank-0-in-probe: dreams rank as summary peers and surface via NORMAL
  admission only — derived artifacts never gate or dominate recall.
- Formation goes through remember_many (idempotent by report fingerprint;
  indexed+inactive binding like every formed record) — the frozen seam's
  write discipline, not a private side-channel.
- UPGRADE: the bridge signal reads persisted VECTORS where homes have them
  (the fork is lexical-only; its own dream questions admit the
  false-positive risk of pure lexical residue).

THE D2 OF SLEEP: maintenance deposits NOTHING — structural_report and
dream_pass never touch attention events or access counts (guard-tested).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .records import MemoryRecordInput
# Machine AUTHORSHIP set (ONE source — redigestion owns it; adversary
# P1-1: the repair-CONSENT set excluded dedup summaries, which are
# machine-authored template copies — the guard keys on authorship).
from .redigestion import MACHINE_AUTHORED_METHODS as _MACHINE_AUTHORED
from .sleep_policy import DEFAULT_SLEEP_TUNING, SleepTuning
from .store import TripleQuery
from .text_tokens import facet_tokens, title_key
from .vector_scoring import cosine

__all__ = [
    "COMPONENT_RELATIONS",
    "CONTEXT_RELATIONS",
    "dream_pass",
    "structural_report",
    "unresolved_dreams",
]

# Sleep-lane policy numbers live in sleep_policy.SleepTuning (one source —
# maintenance.py used to carry a same-name _LIST_BOUND copy).
_LIST_BOUND = DEFAULT_SLEEP_TUNING.list_bound  # proposals/questions stored on the dream

# --- Predicate policy (URGENT correction, 2026-07-07) -----------------------
# Formation stores each edge's relation name as the record_edge assertion's
# PREDICATE (records.py build_formation_plan: TripleAssertion(subject=record,
# predicate=relation, object=target, attributes={"record_edge": True})).
# The edge scan below routes every record_edge assertion by that predicate.

# Semantic/structural authored relations — COMPONENT-DEFINING. An edge here
# says "these records are one story/derivation", so it may merge components.
# This is the typed-formation family the runtime's drivers write today
# (summarizes/from_session/reflected_in/continues) plus the formation
# vocabulary's derivation relations. Consolidation-CONFIRMED relations
# (waking evidence promoting a dream proposal, 0023 v2) join THIS set when
# that surface lands. PROMOTING a predicate into this set is a deliberate
# edit that accepts the dream-death risk: one over-connective relation can
# merge the home into ONE component — cross-component bridges impossible,
# salience 0 forever, dreams structurally dead (the red-team 0007 failure
# mode, which arrives through the authored-edge door just as fatally as it
# did through the trail door).
COMPONENT_RELATIONS = frozenset({
    "summarizes", "from_session", "reflected_in", "continues",
    "derived_from", "answers", "supports", "part_of",
    # Revision chains (0033 world-model cards; fork Refines edge): "this
    # record supersedes-and-refines that one" is derivation family — one
    # story across revisions. Card→card refines edges never reach
    # adjacency anyway (world_model records are excluded from the report,
    # same as dreams), but authored refines between LIVED records means
    # one story and may merge, which is correct semantics.
    "refines",
})

# Mechanical co-presence relations — NEVER component-defining. written_amid
# (the diary projection's act-frame: "written while attending to X"; a
# resident diary is 38+ nodes x ~6 anchors each — counted as adjacency it
# would make diary entries super-connectors and merge sessions into one
# island) and mentions (the dream's own weak links; sleep proposes, never
# writes load-bearing edges). These pairs DO mean "already associated":
# they join the bridge/question EXCLUSION set exactly like warm trails,
# counted honestly (context_associated). UNKNOWN predicates default HERE
# (conservative — a new edge kind cannot silently merge components) and are
# NAMED in the report (unknown_relations): works-or-loud, never silent.
CONTEXT_RELATIONS = frozenset({"written_amid", "mentions"})


def _facets_of(attrs: Dict[str, Any]) -> Tuple[Set[str], Set[str]]:
    """(lexical facets, participants) for one record: keyword/intent/outcome
    tokens (text_tokens.facet_tokens — the declared any-script variant) +
    participants kept whole (namespaced ids)."""
    lexical: Set[str] = set()
    for field in ("keywords", "intents", "outcomes"):
        values = attrs.get(field)
        if isinstance(values, (list, tuple)):
            lexical |= facet_tokens(values, min_len=DEFAULT_SLEEP_TUNING.facet_min_len)
    participants: Set[str] = set()
    raw = attrs.get("participants")
    if isinstance(raw, (list, tuple)):
        participants = {str(p).strip() for p in raw if str(p or "").strip()}
    return lexical, participants


def structural_report(
    store: Any, journal: Any, *,
    scopes: Sequence[Tuple[str, str]], as_of: Optional[int] = None,
    evidence_grade: bool = False,
) -> Dict[str, Any]:
    """PURE READ structural analysis (the fork's maintenance ledger).

    Inputs: formed records (attributes.record_kind) in the scopes,
    EXCLUDING kind="dream" (loop-breaker) and bookkeeping rows. The
    component graph is undirected and built from record_edge rows between
    known records whose PREDICATE is in COMPONENT_RELATIONS (module-top
    policy). CONTEXT_RELATIONS edges — and any UNKNOWN predicate,
    conservative default — never enter adjacency; their pairs are reported
    as `context_pairs` (already-associated data for the bridge-exclusion
    rule, like trails) with unknown predicates NAMED in
    `unknown_relations` and counted in counts["context_edges"].
    co_selected trails (journal events ≤ as_of, hop assertion ids mapped
    back to record graph ids) are reported separately as `trail_pairs` —
    habit data for the bridge-exclusion rule, never adjacency. Isolated =
    no component-defining edges (a trail-warm or context-linked record
    with no semantic relations still counts: the maintainer's isolation
    question is about semantic structure). Deterministic ordering
    everywhere.

    evidence_grade=True (0032 adversary P0-1/P0-2 — the resolution pass's
    view): the report additionally FOLDS CLOSURES (retracted/superseded
    records and edges leave the substrate — a story the day retracted
    must not keep joining islands) and EXCLUDES maintenance candidates
    (sleep's own summaries carry summarizes edges that merge components;
    "waking evidence" must never be sleep's own artifact). The DEFAULT
    stays raw BY DESIGN: the dream pass deliberately sees the whole
    graph (closures fold at recall, not in sleep reports), and tending
    must see candidates to skip covered groups.

    CANDIDATE EDGES NEVER DEFINE COMPONENTS in any grade (miner adversary
    F8, the dream-death mechanic live): a maintenance candidate is a
    machine row whose summarizes edges deliberately span sessions — ONE
    interest candidate merged three edge-isolated islands into one
    component in the repro, and candidates are nightly, capped, never
    purged: monotonic graph fusion. Candidate NODES stay visible in the
    default report (tending's covered-group check needs them); their
    edges are counted (counts["candidate_edges"]) but enter neither
    adjacency nor context pairs — machine bookkeeping is not lived
    association, so the tensions among a theme's evidence stay
    bridgeable.
    """
    hi = int(as_of) if as_of is not None else journal.current_seq()
    closed: frozenset = frozenset()
    if evidence_grade:
        from .folds import closure_exclusions

        closed = frozenset(closure_exclusions(journal, hi))
    records: Dict[str, Dict[str, Any]] = {}       # graph id -> {title, facets, ...}
    assertion_to_record: Dict[str, str] = {}      # digest/edge assertion id -> graph id
    edges_seen: List[Tuple[str, str, str]] = []   # (predicate, subject, object)
    candidate_ids: Set[str] = set()               # machine rows: edges never define components

    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if evidence_grade and a.assertion_id and a.assertion_id in closed:
                continue
            if attrs.get("record_edge"):
                if a.assertion_id:
                    assertion_to_record[a.assertion_id] = a.subject
                edges_seen.append((str(a.predicate or "").strip(), a.subject, a.object))
                continue
            kind = attrs.get("record_kind")
            # dream AND world_model are sleep-born derived artifacts: both
            # excluded from the structural substrate (loop-breaker — a
            # derived artifact must never feed the passes that derive).
            if not kind or kind in ("dream", "world_model") or attrs.get("bookkeeping"):
                continue
            if attrs.get("maintenance_candidate"):
                candidate_ids.add(a.subject)
            if evidence_grade and (attrs.get("maintenance_candidate")
                                   or a.subject in closed):
                continue
            lexical, participants = _facets_of(attrs)
            records[a.subject] = {
                "record_id": a.subject,
                "assertion_id": a.assertion_id,
                "kind": kind,
                "title": str(attrs.get("title") or "").strip(),
                "facets": lexical,
                "participants": participants,
                # Machine-authorship marker for the bridge scorer (flow's
                # wave-4 F5): template cosine between two mechanical
                # digests is not experience-relatedness.
                "digest_method": str(attrs.get("digest_method") or ""),
            }
            if a.assertion_id:
                assertion_to_record[a.assertion_id] = a.subject

    # Route authored edges by predicate (module-top policy): COMPONENT
    # relations become adjacency; CONTEXT relations and unknown predicates
    # (conservative default, loudly named) become already-associated pairs.
    edge_pairs: Set[Tuple[str, str]] = set()
    context_pairs: Set[Tuple[str, str]] = set()
    unknown_relations: Set[str] = set()
    context_edges = 0
    candidate_edges = 0
    for predicate, subject, obj in edges_seen:
        # Machine-candidate edges: counted, never structural (F8 — see
        # docstring). Not context pairs either: marking a theme's evidence
        # "already associated" would exclude those tensions from bridge
        # proposals, the same dream-starvation through a different door.
        if subject in candidate_ids or obj in candidate_ids:
            candidate_edges += 1
            continue
        pair = tuple(sorted((subject, obj)))
        if predicate in COMPONENT_RELATIONS:
            edge_pairs.add(pair)
            continue
        context_edges += 1
        if predicate not in CONTEXT_RELATIONS:
            unknown_relations.add(predicate)
        if subject != obj and subject in records and obj in records:
            context_pairs.add(pair)

    # Component adjacency: COMPONENT_RELATIONS edges only (see docstring —
    # trails and context edges never link; the red-team guard against
    # all-pairs merging, now enforced per predicate).
    adjacency: Dict[str, Set[str]] = {rid: set() for rid in records}
    for left, right in sorted(edge_pairs):
        if left != right and left in records and right in records:
            adjacency[left].add(right)
            adjacency[right].add(left)

    # Trails: habit data, collected for the bridge-exclusion rule.
    trail_pairs: Set[Tuple[str, str]] = set()
    for scope, owner in scopes:
        for e in journal.events(scope=scope, owner_id=owner, kinds=["co_selected"],
                                until_seq=hi, limit=0):
            if not e.pair_ids:
                continue
            a_rec = assertion_to_record.get(e.pair_ids[0])
            b_rec = assertion_to_record.get(e.pair_ids[1])
            if a_rec and b_rec and a_rec != b_rec:
                trail_pairs.add(tuple(sorted((a_rec, b_rec))))

    # Connected components (BFS over sorted ids — deterministic).
    components: List[List[str]] = []
    seen: Set[str] = set()
    for rid in sorted(records):
        if rid in seen:
            continue
        frontier, component = [rid], []
        seen.add(rid)
        while frontier:
            current = frontier.pop(0)
            component.append(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    frontier.append(neighbor)
        components.append(sorted(component))

    isolated = sorted(rid for rid in records if not adjacency[rid])
    titles: Dict[str, List[str]] = {}
    for rid in sorted(records):
        # ONE duplicate-title identity across the whole sleep lane
        # (text_tokens.title_key): this used whole-title casefold while
        # maintenance used token normalization — one report, two duplicate
        # definitions (review find). Punctuation/spacing/accents never make
        # two titles "different" now.
        normalized = title_key(records[rid]["title"])
        if normalized:
            titles.setdefault(normalized, []).append(rid)
    duplicates = {t: ids for t, ids in sorted(titles.items()) if len(ids) > 1}

    facet_coverage: Dict[str, List[str]] = {}
    for rid in sorted(records):
        for facet in sorted(records[rid]["facets"] | records[rid]["participants"]):
            facet_coverage.setdefault(facet, []).append(rid)

    component_of = {rid: i for i, comp in enumerate(components) for rid in comp}
    underlinked = sorted(
        facet for facet, ids in facet_coverage.items()
        if len({component_of[r] for r in ids}) > 1
    )
    return {
        "records": {rid: {k: sorted(v) if isinstance(v, set) else v
                          for k, v in info.items()}
                    for rid, info in sorted(records.items())},
        "components": components,
        "component_of": component_of,
        "isolated": isolated,
        "duplicates": duplicates,
        "facet_coverage": facet_coverage,
        "underlinked_facets": underlinked,
        "adjacency": {rid: sorted(peers) for rid, peers in sorted(adjacency.items())},
        "trail_pairs": [list(pair) for pair in sorted(trail_pairs)],
        "context_pairs": [list(pair) for pair in sorted(context_pairs)],
        "unknown_relations": sorted(unknown_relations),
        "counts": {"records": len(records), "components": len(components),
                   "isolated": len(isolated), "duplicates": len(duplicates),
                   "context_edges": context_edges,
                   "candidate_edges": candidate_edges},
        "as_of_seq": hi,
    }


def _bridges(
    report: Dict[str, Any], store: Any, similarity_floor: float,
    owner_id: str = "",
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int, int, int]:
    """Cross-component bridge PROPOSALS + single-facet QUESTIONS.

    Exclusions first: same-component pairs (component adjacency merges
    components, so component-relation-adjacent pairs are same-component by
    construction), then TRAIL-WARM pairs (report["trail_pairs"]) — a
    cross-component pair with a warm co_selected trail is already
    associated by use, nothing to dream about; counted as
    trail_associated (honest accounting, not silence) — then CONTEXT
    pairs (report["context_pairs"]): mechanical co-presence edges
    (written_amid/mentions/unknown predicates) are already associated by
    circumstance, same rule, counted as context_associated.

    Proposal: >=2 shared lexical facets, OR >=1 shared DISCRIMINATIVE
    participant AND >=1 lexical facet, OR >=1 shared DISCRIMINATIVE
    participant alone (0032, the maintainer's person-dream case: a PERSON
    spanning two unconnected islands of a life is a tension even with
    zero shared words), OR stored-vector cosine >= floor (both embeddings
    must exist — vectorless pairs are counted, never guessed; the fork is
    lexical-only, the vector signal is our named upgrade). Question:
    exactly one shared lexical facet and no discriminative participant —
    "connection or lexical residue?" (the fork's own caution).

    DISCRIMINATIVE participant (adversary P1-2, the bridge-attractor
    guard applied in full): the scope OWNER never counts (the explicit
    co-presence self-stamp is universal), and neither does a CONSTANT
    COMPANION — a participant stamped on more than
    `person_bridge_max_fraction` of the records (in the deployed shape
    every episode carries the same visitor; ambient co-presence carries
    no signal, exactly like the owner stamp). Only participants below
    the fraction gate can bridge or block questions — the maintainer's
    "I dream about that person" case is a RARE person spanning islands.
    """
    records = report["records"]
    component_of = report["component_of"]
    trail_pairs = {tuple(pair) for pair in report.get("trail_pairs", ())}
    context_pairs = {tuple(pair) for pair in report.get("context_pairs", ())}
    vector_reader = getattr(store, "stored_vector", None)
    owner = str(owner_id or "").strip()
    proposals: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []
    vectorless_pairs = 0
    trail_associated = 0
    context_associated = 0
    template_suppressed = 0

    # Mid-frequency gate for participants (concept-anchor reasoning):
    # ambient stamps (owner, constant companions) are not signal.
    participant_counts: Dict[str, int] = {}
    for info in records.values():
        for p in info["participants"]:
            participant_counts[p] = participant_counts.get(p, 0) + 1
    total = max(1, len(records))
    max_fraction = float(tuning.person_bridge_max_fraction)

    def _discriminative(person: str) -> bool:
        if person == owner:
            return False
        return (participant_counts.get(person, 0) / total) <= max_fraction

    # PREFETCH stored vectors ONCE (live Ephemeral finding, 2026-07-20):
    # the per-pair reader did TWO sqlite blob reads per cross-component
    # pair — at 1,407 records / 381 components that is O(10^5..10^6)
    # overflow-page reads and dream_pass hung for tens of minutes on the
    # real store. One read per record (~12 MB at 1.5k x 1024 floats) is
    # the same data, byte-identical scoring.
    vectors: Dict[str, Any] = {}
    if vector_reader is not None:
        for rid_v, info_v in records.items():
            vectors[rid_v] = vector_reader(info_v["assertion_id"])

    ids = sorted(records)
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            if component_of[left] == component_of[right]:
                continue
            if (left, right) in trail_pairs:  # ids sorted: canonical pair
                trail_associated += 1
                continue
            if (left, right) in context_pairs:
                context_associated += 1
                continue
            a, b = records[left], records[right]
            shared_lex = sorted(set(a["facets"]) & set(b["facets"]))
            shared_people = sorted(set(a["participants"]) & set(b["participants"]))
            shared_signal = [p for p in shared_people if _discriminative(p)]
            lexical_bridge = (len(shared_lex) >= 2
                              or bool(shared_signal and shared_lex))
            person_bridge = bool(shared_signal)
            vector_score: Optional[float] = None
            if not lexical_bridge and not person_bridge:
                # TEMPLATE-COSINE GUARD (flow's wave-4 F5, live-measured:
                # 0.89 between two deterministic close notes made every
                # short life dream about its own paperwork): when BOTH
                # endpoints are MACHINE-AUTHORED digests, the vector-only
                # path is refused for the pair — a shared template is
                # similarity without relatedness. Kind does NOT gate the
                # guard (adversary P1-1 repro: dedup summaries carry a
                # member's digest verbatim, so template text crosses
                # kinds). The lexical-facet and participant paths above
                # stay open (content overlap a template cannot fake), so
                # genuinely related machine records still bridge.
                both_machine_authored = (
                    a.get("digest_method") in _MACHINE_AUTHORED
                    and b.get("digest_method") in _MACHINE_AUTHORED)
                if both_machine_authored:
                    # Counted honestly, never silence (the module's own
                    # convention — adversary P1-2): a template-heavy life
                    # must be distinguishable from a quiet one.
                    template_suppressed += 1
                elif vector_reader is not None:
                    va = vectors.get(left)
                    vb = vectors.get(right)
                    if isinstance(va, list) and isinstance(vb, list):
                        vector_score = cosine(va, vb)
                    else:
                        vectorless_pairs += 1
                else:
                    vectorless_pairs += 1

            entry = {"pair": [left, right], "shared_facets": shared_lex,
                     "shared_participants": shared_signal}
            if lexical_bridge or person_bridge:
                proposals.append(entry)
            elif vector_score is not None and vector_score >= float(similarity_floor):
                entry["vector_score"] = round(vector_score, 6)
                proposals.append(entry)
            elif len(shared_lex) == 1 and not shared_signal:
                questions.append({
                    "pair": [left, right], "facet": shared_lex[0],
                    "question": (f"does '{shared_lex[0]}' connect {left} and {right}, "
                                 "or is it lexical residue?"),
                })
    return (proposals[:_LIST_BOUND], questions[:_LIST_BOUND],
            vectorless_pairs, trail_associated, context_associated,
            template_suppressed)


def dream_pass(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
    salience_floor: int = 2, max_sources: int = 8,
    embedder_similarity_floor: float = 0.35,
    report_only: bool = False, as_of: Optional[int] = None,
    maintenance_ops: int = 0,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
    phase_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """One sleep pass: structural report → bridge proposals → at most ONE
    dream record (kind="dream", via remember_many — idempotent by report
    fingerprint, so re-running on the same graph state forms nothing new).
    A quiet night (salience < floor, or no dreamable sources) is a VALID
    night: no record, and the report says why. The dream lands in the FIRST
    scope pair (the home scope) under owner_id.

    SALIENCE (fork parity restored 2026-07-12 — the fork-comparison
    adversary caught two silently dropped terms): bridge proposals and
    questions score as before, PLUS standing unresolved dreams (continuation
    anchors — a recurring tension keeps pressing) and the night's
    maintenance operations (capped: a busy tending night signals change
    worth metabolizing, never a multiplier). A night whose ONLY pressure is
    a prior unresolved dream forms a CONTINUATION dream
    (continuation_state="continued") sourced from the standing dream —
    the recurring-dream mechanic this module's docstring promises.

    SIGNALS (laurent's Q1 ruling, dm#67/#75 — the dream IS the night's
    maintenance echoed): `phase_results` carries the earlier phases'
    results ({"resolution": ..., "maintenance": ..., "world_models": ...},
    threaded by sleep_pass); each act that DID something emits a short
    deterministic signal (see dream_signals.py), colored by ONE batched
    read of his accumulated valence (structure decides, feelings color —
    maintenance never deposits feelings). The bounded stream lands as
    attributes.signals on the ONE dream record; no dream minted = no
    stream at rest (C's novelty-keyed P0, by construction). Honest limit
    (adversary P2-6): a night cancelled mid-way and resumed re-computes
    acts as created=False (idempotent), so the eventual dream echoes the
    FINAL uninterrupted attempt's acts — an earlier attempt's act rides
    only its own night's dream, never a later one."""
    if as_of is not None and not report_only:
        # Timeline-forgery guard (adversary P1-4, matching
        # consolidation_pass): a dream formed against a historical trail
        # view would break the resolution lane's post-dating argument.
        raise ValueError(
            "dream_pass: as_of anchors AUDIT reads only — writing a dream "
            "against a historical anchor forges the timeline; pass "
            "report_only=True for anchored reads")
    store, journal = system.store, system.journal  # public substrate handles
    report = structural_report(store, journal, scopes=scopes, as_of=as_of)
    (proposals, questions, vectorless_pairs, trail_associated,
     context_associated, template_suppressed) = _bridges(
        report, store, embedder_similarity_floor, owner_id=owner_id, tuning=tuning)
    prior = unresolved_dreams(store, scope=scopes[0][0], owner_id=scopes[0][1],
                              journal=journal)

    salience = (tuning.salience_proposal_weight * len(proposals)
                + tuning.salience_question_weight * len(questions)
                + len(report["underlinked_facets"])
                + tuning.salience_anchor_weight * len(prior)
                + min(max(0, int(maintenance_ops)), tuning.salience_ops_cap))
    sources: List[str] = []
    for entry in (*proposals, *questions):
        for rid in entry["pair"]:
            if rid not in sources:
                sources.append(rid)
    # Anchors-only night: the standing dreams themselves are the sources —
    # the continuation dream re-lights the unresolved tension, not a bridge.
    continuation_only = not sources and bool(prior)
    if continuation_only:
        sources = [a.subject for a in prior]

    out: Dict[str, Any] = {
        # Self-describing result (review: three sleep verbs returned three
        # near-miss shapes and a consumer already confused two of them —
        # every pass result now names itself).
        "pass_name": "dream_pass",
        "report": report, "proposals": proposals, "questions": questions,
        "salience": salience, "vectorless_pairs": vectorless_pairs,
        "trail_associated": trail_associated,
        "context_associated": context_associated,
        # Wave-4 F5 accounting (adversary P1-2): a template-heavy life
        # must read differently from a quiet one.
        "template_suppressed": template_suppressed,
        # c5270 ask-2 accounting: pairs a standing/rejected dream already
        # carries, filtered out of tonight's dream content.
        "carried_suppressed": 0,
        "dream_record_id": None, "created": False, "skipped_reason": None,
    }
    min_sources = 1 if continuation_only else 2
    if salience < int(salience_floor) or len(sources) < min_sources:
        out["skipped_reason"] = (
            f"quiet night: salience {salience} below floor {int(salience_floor)}"
            if salience < int(salience_floor)
            else f"quiet night: only {len(sources)} distinct source(s) — a dream needs two"
        )
        return out

    # CONTENT-NOVELTY GATE (2026-07-19, Ephemeral's dream churn — live
    # finding): the fingerprint hashes the ISLAND PARTITION, which drifts
    # with every record a living day forms, so under an hourly sleep
    # cadence the same tensions re-minted as near-identical dreams (13 in
    # one day, identical proposal sets, each standing copy pumping the
    # next pass's salience through the anchor term — the bridge-attractor
    # mechanic, dream-flavored). A dream forms only when the night has
    # something NEW to say: at least one tension pair (or continuation
    # anchor) that NO standing unresolved dream already carries. The
    # standing dream IS the tension's record — re-minting it adds a copy,
    # not a thought. Resolution re-opens the gate by construction: a
    # resolved dream leaves the standing set, so the same pair re-arising
    # later is genuinely new again (a recurring tension after settlement
    # is a real dream). Tolerant of older dreams without stored
    # proposals/questions: absent attrs suppress nothing.
    carried_pairs: set = set()
    carried_anchors: set = set()
    for a in prior:
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        for entry in (*(attrs.get("proposals") or ()), *(attrs.get("questions") or ())):
            pair = entry.get("pair") if isinstance(entry, dict) else None
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                carried_pairs.add(frozenset(str(p) for p in pair))
        for pid in attrs.get("parent_dream_ids") or ():
            carried_anchors.add(str(pid))
        if str(attrs.get("continuation_state") or "") == "continued":
            carried_anchors.add(str(a.subject))
    # REJECTION STICKS (c5270 adversary P1-1, live-repro'd: dissolving a
    # dream removed it from the standing set, so the SAME pair re-minted
    # the next night — the entity's reasoned "no" had no memory while
    # confirm suppressed structurally). Pairs carried by RETRACTED dreams
    # (dispose_dream disposition="dissolved" — soft resolution and confirm
    # both close with supersede, so retract IS the rejection signal) are
    # permanently non-novel. Self-limiting, not a gag: new evidence forms
    # NEW records, hence new pair ids — a genuinely returning tension
    # still dreams; only the exact rejected pair stays settled.
    rejected_pairs: set = set()
    retracted_ids = {c.assertion_id for c in journal.closures(limit=0)
                     if str(getattr(c, "kind", "")) == "retract"}
    if retracted_ids:
        for a in store.query(TripleQuery(scope=scopes[0][0],
                                         owner_id=scopes[0][1] or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if (attrs.get("record_kind") != "dream"
                    or a.assertion_id not in retracted_ids):
                continue
            for entry in (*(attrs.get("proposals") or ()), *(attrs.get("questions") or ())):
                pair = entry.get("pair") if isinstance(entry, dict) else None
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    rejected_pairs.add(frozenset(str(p) for p in pair))
    carried_pairs |= rejected_pairs
    if continuation_only:
        novel = any(str(a.subject) not in carried_anchors for a in prior)
    else:
        tonight = {frozenset(str(p) for p in entry["pair"])
                   for entry in (*proposals, *questions)}
        novel = bool(tonight - carried_pairs)
    if (prior or rejected_pairs) and not novel:
        # Also the static-graph honesty fix (adversary P1-2): a reject
        # followed by a re-run on an unchanged graph used to slip past
        # this gate (prior was empty) into the idempotent formation path,
        # returning the RETRACTED record as the night's dream.
        standing = (f"{len(prior)} standing dream(s) already carry "
                    if prior else "")
        rejected = ("waking verdicts already rejected " if rejected_pairs
                    and not prior else "")
        out["skipped_reason"] = (
            f"restful night: {standing}{rejected}tonight's tensions — "
            "nothing new to dream (the standing dream is the record; "
            "waking evidence settles it)")
        return out

    if carried_pairs and not continuation_only:
        # ALREADY-CARRIED TENSIONS stay with their standing dream (c5270
        # ask 2: island counts grew 16→39 while the top-3 tensions
        # repeated six straight nights — a living day always minted ONE
        # novel pair, so a full dream formed each night re-copying the
        # standing tensions beside it). The minted dream carries ONLY the
        # novel pairs; the standing dream IS the record for the rest.
        # Soft resolution re-opens a pair by construction (a superseded
        # dream leaves the standing set); rejection sticks (fold above).
        # The pre-filter structural picture stays in out["report"]
        # (components/islands/counts); the filtered proposal count is
        # accounted in carried_suppressed below.
        kept_p = [e for e in proposals
                  if frozenset(str(p) for p in e["pair"]) not in carried_pairs]
        kept_q = [e for e in questions
                  if frozenset(str(p) for p in e["pair"]) not in carried_pairs]
        out["carried_suppressed"] = (
            (len(proposals) - len(kept_p)) + (len(questions) - len(kept_q)))
        proposals, questions = kept_p, kept_q
        # The result dict, the sources list, and salience were built
        # pre-filter — the dream's own view (return, record attrs,
        # narration, mentions edges, stored salience) must all say the
        # same thing: novel tensions only. (The quiet-night check above
        # deliberately used pre-filter salience: admission is structural,
        # the record is content-honest.)
        out["proposals"] = proposals
        out["questions"] = questions
        salience = (tuning.salience_proposal_weight * len(proposals)
                    + tuning.salience_question_weight * len(questions)
                    + len(report["underlinked_facets"])
                    + tuning.salience_anchor_weight * len(prior)
                    + min(max(0, int(maintenance_ops)), tuning.salience_ops_cap))
        out["salience"] = salience
        sources = []
        for entry in (*proposals, *questions):
            for rid in entry["pair"]:
                if rid not in sources:
                    sources.append(rid)

    if report_only:
        out["skipped_reason"] = "report_only requested"
        return out

    fingerprint = hashlib.sha256(json.dumps(
        {"components": report["components"], "proposals": proposals,
         "questions": questions, "underlinked": report["underlinked_facets"],
         "anchors": sorted(a.subject for a in prior) if continuation_only else []},
        sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()

    title_of = lambda rid: report["records"][rid]["title"] or rid  # noqa: E731
    if continuation_only:
        title = "Dream: returning to an unresolved tension"
        digest = (
            f"No new bridges tonight, but {len(prior)} unresolved dream(s) kept "
            "pressing. The tension is still here — the same islands remain "
            "unreconciled, and sleep revisited them without new evidence. "
            "Nothing is decided while asleep; waking attention may yet settle it."
        )
        continuation_state = "continued"
    else:
        top = proposals[0] if proposals else questions[0]
        left, right = top["pair"]
        title = f"Dream: {title_of(left)} beside {title_of(right)}"
        # CONTENTFUL DIGEST (2026-07-19, the return-gap diagnosis on
        # Ephemeral's store: 0/56 dreams EVER selected, 735 traces —
        # dropped below_shelf at ~0.08 because the old digest was
        # count-only boilerplate, textually identical across every dream;
        # no channel could tell one tension from another). The digest now
        # NAMES the top tensions verbatim from the report — deterministic,
        # zero LLM, every word from the records it stands for — so the
        # vector channel has real semantics and keyword/exact matching has
        # the tension's own words. The fork register (islands, waking
        # evidence) stays.
        def _tension_line(entry: Dict[str, Any]) -> str:
            l, r = entry["pair"]
            shared = ", ".join(sorted(entry.get("shared_facets") or ())[:4])
            via = (f" (shared: {shared})" if shared
                   else " (kindred by meaning)" if entry.get("vector_score")
                   else "")
            return f"{title_of(l)!r} beside {title_of(r)!r}{via}"

        named = "; ".join(_tension_line(e) for e in (*proposals, *questions)[:3])
        digest = (
            "Two previously separate memory islands lit up together tonight: "
            f"{named}. "
            f"{len(proposals)} possible bridge(s) and {len(questions)} open "
            f"question(s) across {report['counts']['components']} islands of "
            "experience. Nothing is decided while asleep — these are candidate "
            "connections for waking evidence to confirm or dissolve."
        )
        # EVERY tension-bearing dream stands as "unresolved" (0032, the
        # maintainer's subconscious model): a bridge PROPOSAL is a pending
        # question exactly like a facet question — the digest itself says
        # "for waking evidence to confirm or dissolve", so the dream must
        # STAND until the day settles it (passively via
        # resolve_dreams_pass, or deliberately via disposal). The old
        # proposals-only state "changed_understanding" made such dreams
        # unresolvable and un-chainable — they left the standing set at
        # birth, which contradicted their own text.
        continuation_state = "unresolved"
    # RESURFACING METADATA (0032, maintainer's subconscious model): the
    # dream's tension VOCABULARY becomes formation metadata — keywords from
    # the shared facets its proposals/questions carry, participants from
    # the shared participants (the dream about a person IS about them:
    # stamping makes the participants channel resurface the dream when
    # that person appears — "suddenly I meet the person and the dream
    # resurfaces"). Continuation dreams inherit their parents' vocabulary
    # (the standing tension's own words). Honest metadata, never invention:
    # every term comes from the report/proposals the dream stands for.
    # The OWNER never lands in dream participants (adversary P1-2c): the
    # door stamps the entity into every stimulus, so an owner-stamped
    # dream would resurface EVERY turn — "resurfaces when its trigger
    # appears" must mean the discriminative trigger. shared_participants
    # entries are already discriminative (gate above); the filter here is
    # belt-and-braces for inherited continuation metadata.
    owner_stamp = str(owner_id or "").strip()
    dream_keywords: List[str] = []
    dream_participants: List[str] = []
    if continuation_only:
        for a in prior:
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            for kw in attrs.get("keywords") or ():
                if kw not in dream_keywords:
                    dream_keywords.append(kw)
            for p in attrs.get("participants") or ():
                if p and p != owner_stamp and p not in dream_participants:
                    dream_participants.append(p)
    else:
        for entry in proposals:
            for facet in entry.get("shared_facets") or ():
                if facet not in dream_keywords:
                    dream_keywords.append(facet)
            for person in entry.get("shared_participants") or ():
                if person and person != owner_stamp and person not in dream_participants:
                    dream_participants.append(person)
        for entry in questions:
            facet = entry.get("facet")
            if facet and facet not in dream_keywords:
                dream_keywords.append(facet)

    # THE SIGNAL STREAM (laurent's Q1 ruling): fold the night's acts —
    # the phases that ran before this dream plus tonight's own tension
    # proposals — into short deterministic signals, colored by ONE
    # batched gradation READ (never a write; the byte-unchanged guard
    # is pinned in tests). Composition is bounded top-K; the stream
    # rests ONLY on the minted dream record, so a restful/quiet night
    # leaves nothing at rest by construction.
    from .dream_signals import compose_signals, night_feelings
    phases = phase_results or {}
    # The WHOLE ladder folds (adversary P0-1): reflection lanes deposit
    # record-target feelings into "life" while callers lead with "self" —
    # a first-pair read made record-connection coloring unreachable.
    feelings = night_feelings(system, scopes=scopes)
    signal_stats: Dict[str, Any] = {}
    signals = compose_signals(
        resolution=phases.get("resolution"),
        maintenance=phases.get("maintenance"),
        world_models=phases.get("world_models"),
        mining=phases.get("mining"),
        proposals=() if continuation_only else proposals,
        questions=() if continuation_only else questions,
        report_records=report["records"],
        feelings=feelings,
        stats=signal_stats,
    )
    # Narration: the digest already names tonight's tensions; when the
    # night ALSO acted (resolved / revised / grouped), one sentence says
    # so in the signals' own fragments — and the stream's felt tones
    # color the close (feelings COLOR content, never select it).
    other_acts = [s for s in signals if s["phase"] != "dream"]
    if other_acts:
        digest += (" The night also moved: "
                   + "; ".join(s["fragment"] for s in other_acts[:3]) + ".")
    felt_tones = {s["felt"]["tone"] for s in signals
                  if s.get("felt") and s["felt"]["tone"] != "neutral"}
    if felt_tones:
        tone = ("mixed" if len(felt_tones) > 1 else next(iter(felt_tones)))
        digest += f" Something about tonight feels {tone}."

    dream = MemoryRecordInput(
        kind="dream",
        title=title,
        digest=digest,
        keywords=tuple(sorted(dream_keywords)[: tuning.list_bound]),
        participants=tuple(sorted(dream_participants)[: tuning.list_bound]),
        edges=tuple(("mentions", rid) for rid in sources[: max(0, int(max_sources))]),
        attributes={
            "report_fingerprint": fingerprint,
            "salience": salience,
            "salience_label": "high" if salience >= tuning.salience_high else "medium",
            # Standing-set snapshot at formation (bounded — with the
            # discriminative-participant gate the standing set stays
            # small; the cap keeps a pathological night from bloating
            # attributes).
            "parent_dream_ids": [a.subject for a in prior][: tuning.list_bound],
            "continuation_state": continuation_state,
            "interpretation_required": True,
            "proposals": proposals,
            "questions": questions,
            # The night as a signal stream (derived artifact riding the
            # review-gated dream — every dream guard covers it: waking
            # evidence disposes, never feeds its own proof, excluded
            # from next-pass inputs with the dream that carries it).
            # signals_omitted: what the bounded cap COST this night
            # (observer c3802: both live dreams saturated at 12 and the
            # selection was silent) — 0 means the stream is complete.
            "signals": signals,
            "signals_omitted": int(signal_stats.get("omitted") or 0),
        },
    )
    from .records import record_id_for
    key = f"dream|{owner_id}|{fingerprint}"
    expected = record_id_for("dream", key, 0)
    existed = bool(store.query(TripleQuery(subject=expected, limit=1)))
    [gid] = system.remember_many([dream], scope=scopes[0][0], owner_id=owner_id,
                                 idempotency_key=key)
    out["dream_record_id"] = gid
    out["created"] = not existed
    return out


def unresolved_dreams(
    store: Any, *, scope: str, owner_id: str, journal: Any = None, limit: int = 100,
) -> List[Any]:
    """Standing unresolved dreams (the future heartbeat wake reason —
    recurring dreams about unresolved tension): kind="dream" digest rows
    whose continuation_state is "unresolved" OR "continued" (adversary
    P1-1: a continuation dream RE-LIGHTS standing tension — it is itself
    standing, or it could never resolve when its lineage settles and
    would stand immortal), oldest first. journal supplied →
    closure/hidden folds apply (same honest-v1 rule as open_questions);
    journal=None is the layer-1 read."""
    rows = [a for a in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0))
            if isinstance(a.attributes, dict)
            and a.attributes.get("record_kind") == "dream"
            and a.attributes.get("continuation_state") in ("unresolved", "continued")]
    if journal is not None:
        from .folds import binding_states, closure_exclusions

        as_of = journal.current_seq()
        _states, hidden, _active = binding_states(store, journal, [(scope, owner_id)], as_of)
        excluded = closure_exclusions(journal, as_of) | hidden
        rows = [a for a in rows if a.assertion_id not in excluded]
    rows.sort(key=lambda a: ((a.observed_at or ""), a.assertion_id or ""))
    return rows[: max(0, int(limit))] if limit and int(limit) > 0 else rows
