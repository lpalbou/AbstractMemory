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
    """
    hi = int(as_of) if as_of is not None else journal.current_seq()
    records: Dict[str, Dict[str, Any]] = {}       # graph id -> {title, facets, ...}
    assertion_to_record: Dict[str, str] = {}      # digest/edge assertion id -> graph id
    edges_seen: List[Tuple[str, str, str]] = []   # (predicate, subject, object)

    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_edge"):
                if a.assertion_id:
                    assertion_to_record[a.assertion_id] = a.subject
                edges_seen.append((str(a.predicate or "").strip(), a.subject, a.object))
                continue
            kind = attrs.get("record_kind")
            if not kind or kind == "dream" or attrs.get("bookkeeping"):
                continue
            lexical, participants = _facets_of(attrs)
            records[a.subject] = {
                "record_id": a.subject,
                "assertion_id": a.assertion_id,
                "kind": kind,
                "title": str(attrs.get("title") or "").strip(),
                "facets": lexical,
                "participants": participants,
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
    for predicate, subject, obj in edges_seen:
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
                   "context_edges": context_edges},
        "as_of_seq": hi,
    }


def _bridges(
    report: Dict[str, Any], store: Any, similarity_floor: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int, int]:
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

    Proposal: >=2 shared lexical facets, OR >=1 shared participant AND >=1
    lexical facet, OR stored-vector cosine >= floor (both embeddings must
    exist — vectorless pairs are counted, never guessed; the fork is
    lexical-only, the vector signal is our named upgrade). Question: exactly
    one shared lexical facet and nothing else — "connection or lexical
    residue?" (the fork's own caution).
    """
    records = report["records"]
    component_of = report["component_of"]
    trail_pairs = {tuple(pair) for pair in report.get("trail_pairs", ())}
    context_pairs = {tuple(pair) for pair in report.get("context_pairs", ())}
    vector_reader = getattr(store, "stored_vector", None)
    proposals: List[Dict[str, Any]] = []
    questions: List[Dict[str, Any]] = []
    vectorless_pairs = 0
    trail_associated = 0
    context_associated = 0

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
            vector_score: Optional[float] = None
            if len(shared_lex) < 2 and not (shared_people and shared_lex):
                if vector_reader is not None:
                    va = vector_reader(a["assertion_id"])
                    vb = vector_reader(b["assertion_id"])
                    if isinstance(va, list) and isinstance(vb, list):
                        vector_score = cosine(va, vb)
                    else:
                        vectorless_pairs += 1
                else:
                    vectorless_pairs += 1

            entry = {"pair": [left, right], "shared_facets": shared_lex,
                     "shared_participants": shared_people}
            if len(shared_lex) >= 2 or (shared_people and shared_lex):
                proposals.append(entry)
            elif vector_score is not None and vector_score >= float(similarity_floor):
                entry["vector_score"] = round(vector_score, 6)
                proposals.append(entry)
            elif len(shared_lex) == 1 and not shared_people:
                questions.append({
                    "pair": [left, right], "facet": shared_lex[0],
                    "question": (f"does '{shared_lex[0]}' connect {left} and {right}, "
                                 "or is it lexical residue?"),
                })
    return (proposals[:_LIST_BOUND], questions[:_LIST_BOUND],
            vectorless_pairs, trail_associated, context_associated)


def dream_pass(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
    salience_floor: int = 2, max_sources: int = 8,
    embedder_similarity_floor: float = 0.35,
    report_only: bool = False, as_of: Optional[int] = None,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
) -> Dict[str, Any]:
    """One sleep pass: structural report → bridge proposals → at most ONE
    dream record (kind="dream", via remember_many — idempotent by report
    fingerprint, so re-running on the same graph state forms nothing new).
    A quiet night (salience < floor, or fewer than 2 distinct sources) is a
    VALID night: no record, and the report says why. The dream lands in the
    FIRST scope pair (the home scope) under owner_id. Salience weights, the
    floor, and the one-per-pass shape are declared tunables (SleepTuning;
    fork parity at defaults — the fork inlines the same weights)."""
    store, journal = system.store, system.journal  # public substrate handles
    report = structural_report(store, journal, scopes=scopes, as_of=as_of)
    proposals, questions, vectorless_pairs, trail_associated, context_associated = _bridges(
        report, store, embedder_similarity_floor)

    salience = (tuning.salience_proposal_weight * len(proposals)
                + tuning.salience_question_weight * len(questions)
                + len(report["underlinked_facets"]))
    sources: List[str] = []
    for entry in (*proposals, *questions):
        for rid in entry["pair"]:
            if rid not in sources:
                sources.append(rid)

    out: Dict[str, Any] = {
        # Self-describing result (review: three sleep verbs returned three
        # near-miss shapes and a consumer already confused two of them —
        # every pass result now names itself).
        "pass_name": "dream_pass",
        "report": report, "proposals": proposals, "questions": questions,
        "salience": salience, "vectorless_pairs": vectorless_pairs,
        "trail_associated": trail_associated,
        "context_associated": context_associated,
        "dream_record_id": None, "created": False, "skipped_reason": None,
    }
    if salience < int(salience_floor) or len(sources) < 2:
        out["skipped_reason"] = (
            f"quiet night: salience {salience} below floor {int(salience_floor)}"
            if salience < int(salience_floor)
            else f"quiet night: only {len(sources)} distinct source(s) — a dream needs two"
        )
        return out
    if report_only:
        out["skipped_reason"] = "report_only requested"
        return out

    fingerprint = hashlib.sha256(json.dumps(
        {"components": report["components"], "proposals": proposals,
         "questions": questions, "underlinked": report["underlinked_facets"]},
        sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()

    top = proposals[0] if proposals else questions[0]
    left, right = top["pair"]
    title_of = lambda rid: report["records"][rid]["title"] or rid  # noqa: E731
    prior = unresolved_dreams(store, scope=scopes[0][0], owner_id=scopes[0][1],
                              journal=journal)
    dream = MemoryRecordInput(
        kind="dream",
        title=f"Dream: {title_of(left)} beside {title_of(right)}",
        digest=(
            "Two previously separate memory islands lit up together tonight. "
            f"I noticed {len(proposals)} possible bridge(s) and "
            f"{len(questions)} open question(s) across {report['counts']['components']} "
            "islands of experience. Nothing is decided while asleep — these are "
            "candidate connections for waking evidence to confirm or dissolve."
        ),
        edges=tuple(("mentions", rid) for rid in sources[: max(0, int(max_sources))]),
        attributes={
            "report_fingerprint": fingerprint,
            "salience": salience,
            "salience_label": "high" if salience >= tuning.salience_high else "medium",
            "parent_dream_ids": [a.subject for a in prior],
            "continuation_state": "unresolved" if questions else "changed_understanding",
            "interpretation_required": True,
            "proposals": proposals,
            "questions": questions,
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
    with continuation_state=="unresolved", oldest first. journal supplied →
    closure/hidden folds apply (same honest-v1 rule as open_questions);
    journal=None is the layer-1 read."""
    rows = [a for a in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0))
            if isinstance(a.attributes, dict)
            and a.attributes.get("record_kind") == "dream"
            and a.attributes.get("continuation_state") == "unresolved"]
    if journal is not None:
        from .folds import binding_states, closure_exclusions

        as_of = journal.current_seq()
        _states, hidden, _active = binding_states(store, journal, [(scope, owner_id)], as_of)
        excluded = closure_exclusions(journal, as_of) | hidden
        rows = [a for a in rows if a.assertion_id not in excluded]
    rows.sort(key=lambda a: ((a.observed_at or ""), a.assertion_id or ""))
    return rows[: max(0, int(limit))] if limit and int(limit) > 0 else rows
