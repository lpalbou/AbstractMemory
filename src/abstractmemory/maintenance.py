"""Sleep phase-1: data-quality tending + deterministic cadence (0023, fork parity).

The fork's sleep has TWO phases (memory_control.rs, request_memory_maintenance):
phase 1 "data_quality_tending" — metadata gaps, duplicate titles, near-duplicate
pairs, isolated-link candidates, edge-suppression candidates, and the creation
of INACTIVE review-gated consolidation candidates — then phase 2
"further_insight" — the dream (cross-component bridges). consolidation.py
ported phase 2; THIS module is phase 1 plus the fork-770 cadence predicate.
The maintainer's charge (2026-07-09): "the goal during the sleep phase is to
essentially do maintenance of the graph and help organize the memories of the
day, fix metadata issues, summaries, improve relationships".

HARD BOUNDARIES (identical to the dream pass, guard-tested):
- SLEEP PROPOSES; WAKING EVIDENCE DISPOSES. The only write in this module is
  the inactive consolidation candidate (kind="summary", review_required,
  formed via remember_many like every record). Everything else — metadata
  gaps, link candidates, edge suppressions, near-dup/shared-source proposals —
  is REPORT ONLY: fixing metadata is a waking/formation act (sleep never
  mutates a source record's attributes), new relationships need waking
  evidence, and edge suppression would be an append-only closure the waking
  entity/operator elects (the report names the closure candidates).
- THE D2 OF SLEEP: maintenance deposits NOTHING — no attention events, no
  access counts (remember_many deposits nothing by design: forming ≠ using).
- LOOP-BREAKER: maintenance candidates (attributes.maintenance_candidate) are
  EXCLUDED from maintenance-analysis inputs — tending never re-tends its own
  output (the dream-exclusion precedent). The DREAM pass still sees them:
  they are real summary nodes in the tended graph.

NAMED DIVERGENCES from the fork (our architecture rules where they clash):
- Near-duplicate pairs are SAME-KIND only: cross-kind textual similarity is
  derivation signal (an episode and its summary), not duplication; the fork's
  own shared_source group covers derived families. Duplicate-title groups are
  keyed (kind, normalized title) for the same reason.
- UPGRADE: near-dup evidence reads persisted VECTORS where homes have them
  (cosine >= vector floor 0.90 — deliberately far above the 0.35 dream-bridge
  floor: dedup claims near-identity, not mere relatedness). The fork is
  Jaccard-only and its proposals carry the false-positive caveat verbatim.
- Candidate formation goes through remember_many with a sorted-source-set
  idempotency key: re-running the pass on the same group is a no-op by
  construction (the fork scans for an existing candidate; we get dedup from
  deterministic identity AND keep the scan as the superset-coverage skip).
- Scheduling stays HOST policy (0023): maintenance_due answers "is there
  material" (enough new records / fragmentation, fork 770); late-local-time
  and the sleep window belong to the runtime's loop.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .consolidation import COMPONENT_RELATIONS, dream_pass, structural_report
from .records import MemoryRecordInput, record_id_for
# Cadence lives in sleep_cadence.py (600-line split: "is there material" is
# its own task); re-exported here so established import paths keep working.
from .sleep_cadence import last_maintenance_seq, maintenance_due  # noqa: F401
# Policy numbers live in sleep_policy (ONE source — this module and
# consolidation.py each carried a same-name _LIST_BOUND before); the
# NEAR_DUP_* re-exports keep established import paths working.
from .sleep_policy import (  # noqa: F401  (re-exported tunables)
    DEFAULT_SLEEP_TUNING,
    NEAR_DUP_JACCARD_FLOOR,
    NEAR_DUP_SCAN_LIMIT,
    NEAR_DUP_VECTOR_FLOOR,
    SleepTuning,
)
from .store import TripleQuery
# Tokenization lives in text_tokens (ONE home): token_set gains NFKD accent
# folding over the old local copy — accented FR near-duplicates were
# invisible to tending while keyword recall matched them (review find).
from .text_tokens import jaccard as _jaccard
from .text_tokens import title_key as _title_key
from .text_tokens import token_set as _tokens
from .vector_scoring import cosine

__all__ = [
    "SleepTuning",
    "consolidation_pass",
    "last_maintenance_seq",
    "maintenance_due",
    "maintenance_report",
    "sleep_pass",
]


def _scan(
    store: Any, scopes: Sequence[Tuple[str, str]]
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """One deterministic pure-read pass over the scopes.

    Returns (records, edges, candidates): analysis records (formed, minus
    dreams/bookkeeping/maintenance candidates), record_edge rows between any
    subjects, and the EXISTING maintenance candidates (for coverage skips).
    """
    records: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_edge"):
                edges.append({
                    "predicate": str(a.predicate or "").strip(), "subject": a.subject,
                    "object": a.object, "assertion_id": a.assertion_id,
                    "observed_at": a.observed_at or "",
                })
                continue
            kind = attrs.get("record_kind")
            if not kind or attrs.get("bookkeeping"):
                continue
            if attrs.get("maintenance_candidate"):
                sources = attrs.get("source_ids")
                candidates.append({
                    "record_id": a.subject,
                    "source_ids": [str(s) for s in sources] if isinstance(sources, (list, tuple)) else [],
                })
                continue
            if kind in ("dream", "world_model"):
                continue  # sleep-born derived artifacts never enter tending inputs
            records[a.subject] = {
                "record_id": a.subject,
                "assertion_id": a.assertion_id,
                "kind": str(kind),
                "title": str(attrs.get("title") or "").strip(),
                "digest": str(a.object or ""),
                "observed_at": a.observed_at or "",
                "keywords": list(attrs.get("keywords") or ()),
                "intents": list(attrs.get("intents") or ()),
                "outcomes": list(attrs.get("outcomes") or ()),
                # 0035: provenance signals for the unsourced-lesson check
                # (archive-imported / operator-taught lessons carry import
                # provenance instead of machine-readable source edges).
                # BOTH rests are read (adversary P1.1: archive_import writes
                # attributes.seeded_from + provenance.archive_path — the
                # attrs-only read flagged the importer's own lessons):
                # payload_ref counts as provenance BY RULING NEED — a
                # verbatim-backed lesson is traceable to its body; if that
                # proves over-wide, narrowing is a one-line change here.
                "has_import_provenance": bool(
                    attrs.get("import_provenance")
                    or attrs.get("seeded_from")
                    or attrs.get("origin_path")
                    or attrs.get("payload_ref")
                    or (isinstance(a.provenance, dict)
                        and (a.provenance.get("archive_path")
                             or a.provenance.get("source") == "archive-import"))),
            }
    candidates.sort(key=lambda c: c["record_id"])
    return records, edges, candidates


def _metadata_gaps(
    records: Dict[str, Dict[str, Any]], tuning: SleepTuning,
) -> List[Dict[str, Any]]:
    """Fork structural_metadata_gaps, REPORT-ONLY by our boundary: the fix is
    a waking act (formation-time keywords are the runtime's v1.1 lane; a
    re-digestion surface may consume this list) — sleep never mutates sources."""
    gaps: List[Dict[str, Any]] = []
    for rid in sorted(records):
        info = records[rid]
        missing = [f for f in ("keywords", "intents", "outcomes") if not info[f]]
        if missing:
            gaps.append({
                "record_id": rid, "missing_fields": missing, "risk": "low",
                "action": ("report-only: compute missing fields at a waking "
                           "re-digestion, never while asleep (no source mutation)"),
            })
    gaps.sort(key=lambda g: (-len(g["missing_fields"]), g["record_id"]))
    return gaps[: tuning.list_bound * tuning.metadata_gaps_factor]


def _unsourced_lessons(
    records: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]],
    tuning: SleepTuning,
) -> List[Dict[str, Any]]:
    """0035 sourcing discipline, by TENDING not refusal: a lesson/
    instruction with zero derivation edges and no import provenance is an
    opinion wearing wisdom's rank — named for a waking re-digestion (link
    the sources, or state where it came from), never refused (real
    teachings arrive without machine-readable sources).

    DIRECTIONS follow the semantics registry (semantics c1151 — the
    supports direction was backwards here before any row engraved it):
    a lesson is sourced when it is the SUBJECT of a derivation edge
    (derived_from/answers/from_session/summarizes/refines: the new/
    derived record is the subject) OR the OBJECT of a supports edge
    (cito:supports — subject=EVIDENCE, object=CLAIM: an episode
    supporting the lesson sources it; the lesson being the subject would
    mean the lesson is evidence for something else, which sources
    nothing about the lesson itself)."""
    subject_sourcing = {"derived_from", "answers", "from_session",
                        "summarizes", "refines"}
    sourced = {e["subject"] for e in edges if e["predicate"] in subject_sourcing}
    sourced |= {e["object"] for e in edges if e["predicate"] == "supports"}
    out: List[Dict[str, Any]] = []
    for rid in sorted(records):
        info = records[rid]
        if info["kind"] not in ("lesson", "instruction"):
            continue
        if rid in sourced or info.get("has_import_provenance"):
            continue
        out.append({
            "record_id": rid, "kind": info["kind"], "title": info["title"],
            "action": ("report-only: link the memories this distills "
                       "(lesson derived_from source) or record supporting "
                       "evidence (episode supports lesson) at a waking "
                       "re-digestion — distilled wisdom should reference "
                       "the experience it came from"),
        })
    return out[: tuning.list_bound]


def _duplicate_title_groups(
    records: Dict[str, Dict[str, Any]], tuning: SleepTuning,
) -> List[Dict[str, Any]]:
    by_key: Dict[Tuple[str, str], List[str]] = {}
    for rid in sorted(records):
        key = _title_key(records[rid]["title"])
        if key:
            by_key.setdefault((records[rid]["kind"], key), []).append(rid)
    groups = [
        {"kind": kind, "title_key": key, "record_ids": ids}
        for (kind, key), ids in sorted(by_key.items()) if len(ids) > 1
    ]
    groups.sort(key=lambda g: (-len(g["record_ids"]), g["record_ids"][0]))
    return groups[: tuning.list_bound]


def _near_duplicate_pairs(
    records: Dict[str, Dict[str, Any]], store: Any, scan_limit: int,
    tuning: SleepTuning,
) -> Tuple[List[Dict[str, Any]], int]:
    """Same-kind near-dup pairs: Jaccard >= floor over title+digest tokens,
    OR stored-vector cosine >= the tuned vector floor (both vectors present).
    Newest-first bounded scan (a resident home tends recent material first);
    vectorless below-Jaccard pairs are counted, never guessed."""
    ordered = sorted(records, key=lambda rid: (records[rid]["observed_at"], rid), reverse=True)
    scan = ordered[: max(0, int(scan_limit))]
    fingerprints = {rid: _tokens(f"{records[rid]['title']} {records[rid]['digest']}") for rid in scan}
    vector_reader = getattr(store, "stored_vector", None)
    pairs: List[Dict[str, Any]] = []
    vectorless = 0
    for i, left in enumerate(scan):
        for right in scan[i + 1:]:
            if records[left]["kind"] != records[right]["kind"]:
                continue
            entry: Dict[str, Any] = {"pair": sorted((left, right)), "kind": records[left]["kind"]}
            score = _jaccard(fingerprints[left], fingerprints[right])
            if score >= tuning.near_dup_jaccard_floor:
                entry["jaccard"] = round(score, 6)
                pairs.append(entry)
                continue
            if vector_reader is None:
                vectorless += 1
                continue
            va = vector_reader(records[left]["assertion_id"])
            vb = vector_reader(records[right]["assertion_id"])
            if isinstance(va, list) and isinstance(vb, list):
                vector_score = cosine(va, vb)
                if vector_score >= tuning.near_dup_vector_floor:
                    entry["vector_score"] = round(vector_score, 6)
                    pairs.append(entry)
            else:
                vectorless += 1
    pairs.sort(key=lambda p: (-(p.get("jaccard") or p.get("vector_score") or 0.0), p["pair"][0], p["pair"][1]))
    return pairs[: tuning.list_bound], vectorless


def _shared_source_groups(
    records: Dict[str, Dict[str, Any]], edges: Sequence[Dict[str, Any]],
    tuning: SleepTuning,
) -> List[Dict[str, Any]]:
    """Records whose summarizes/derived_from edges hit ONE shared target —
    possibly redundant derivations, possibly legitimate specializations
    (fork's own caveat; risk medium, report-only)."""
    by_source: Dict[str, List[str]] = {}
    for e in edges:
        if e["predicate"] in ("summarizes", "derived_from") and e["subject"] in records:
            by_source.setdefault(e["object"], []).append(e["subject"])
    groups = []
    for source_id in sorted(by_source):
        ids = sorted(set(by_source[source_id]))
        if len(ids) > 1:
            groups.append({"source_id": source_id, "record_ids": ids})
    groups.sort(key=lambda g: (-len(g["record_ids"]), g["source_id"]))
    return groups[: tuning.list_bound]


def _isolated_link_candidates(
    base: Dict[str, Any], records: Dict[str, Dict[str, Any]],
    tuning: SleepTuning,
) -> List[Dict[str, Any]]:
    """Fork structural_isolated_link_candidates: an isolated record sharing
    >= min_shared_facets facets with another record is a PROPOSAL for a
    waking-review link (mentions/supports after source expansion) — never
    written here."""
    base_records = base.get("records", {})
    facet_of = {
        rid: set(info.get("facets", ())) | set(info.get("participants", ()))
        for rid, info in base_records.items() if rid in records
    }
    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()
    for isolated_id in base.get("isolated", ()):
        left_facets = facet_of.get(isolated_id)
        if not left_facets:
            continue
        for rid in sorted(facet_of):
            if rid == isolated_id:
                continue
            shared = sorted(left_facets & facet_of[rid])[: tuning.shared_facets_shown]
            if len(shared) < tuning.min_shared_facets:
                continue
            pair = tuple(sorted((isolated_id, rid)))
            if pair in seen:
                continue
            seen.add(pair)
            out.append({
                "pair": list(pair), "shared_terms": shared, "risk": "medium",
                "suggested_kind": "mentions_or_supports_after_waking_review",
                "reason": (f"{pair[0]} and {pair[1]} share facets [{', '.join(shared)}] "
                           "while at least one is isolated"),
            })
    out.sort(key=lambda c: (-len(c["shared_terms"]), c["pair"][0], c["pair"][1]))
    return out[: tuning.list_bound]


def _edge_suppression_candidates(
    records: Dict[str, Dict[str, Any]], edges: Sequence[Dict[str, Any]],
    tuning: SleepTuning,
) -> List[Dict[str, Any]]:
    """Fork structural_edge_suppression_candidates, REPORT-ONLY here: the act
    it proposes is an append-only closure on the redundant EDGE assertion —
    a waking election, never a sleep write."""
    scoped = [e for e in edges if e["subject"] in records and e["object"] in records
              and e["assertion_id"]]
    out: List[Dict[str, Any]] = []

    # (a) exact duplicate logical edges across formation batches.
    by_exact: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for e in scoped:
        by_exact.setdefault((e["subject"], e["predicate"], e["object"]), []).append(e)
    for (subject, predicate, obj), group in sorted(by_exact.items()):
        if len(group) < 2:
            continue
        group.sort(key=lambda e: (e["observed_at"], e["assertion_id"]))
        out.append({
            "kind": "duplicate_edge", "pair": [subject, obj], "predicate": predicate,
            "keep_assertion_id": group[0]["assertion_id"],
            "redundant_assertion_ids": [e["assertion_id"] for e in group[1:]],
            "action": "waking close (append-only closure) of the redundant edge assertions",
            "reason": f"duplicate `{predicate}` edge recorded {len(group)} times; earliest kept as source",
            "risk": "low",
        })

    # (b) low-information mentions shadowed by a stronger authored relation.
    by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for e in scoped:
        by_pair.setdefault((e["subject"], e["object"]), []).append(e)
    for (subject, obj), group in sorted(by_pair.items()):
        mentions = sorted((e for e in group if e["predicate"] == "mentions"),
                          key=lambda e: e["assertion_id"])
        stronger = sorted((e for e in group if e["predicate"] in COMPONENT_RELATIONS),
                          key=lambda e: (e["predicate"], e["assertion_id"]))
        if mentions and stronger:
            out.append({
                "kind": "low_information_edge", "pair": [subject, obj], "predicate": "mentions",
                "keep_assertion_id": stronger[0]["assertion_id"],
                "redundant_assertion_ids": [e["assertion_id"] for e in mentions],
                "action": "waking close (append-only closure) of the mentions edges",
                "reason": (f"`mentions` is less informative than the existing "
                           f"`{stronger[0]['predicate']}` relation for the same pair"),
                "risk": "low",
            })
    out.sort(key=lambda c: (c["risk"], c["pair"][0], c["pair"][1], c["kind"]))
    return out[: tuning.list_bound * tuning.suppressions_factor]


def _consolidation_proposals(
    records: Dict[str, Dict[str, Any]],
    duplicate_groups: Sequence[Dict[str, Any]],
    near_dups: Sequence[Dict[str, Any]],
    shared_sources: Sequence[Dict[str, Any]],
    tuning: SleepTuning,
) -> List[Dict[str, Any]]:
    """Fork structural_consolidation_proposals order: duplicate_title (low)
    -> shared_source (medium) -> near_duplicate (medium); one proposal per
    distinct source set. Only duplicate_title/low ever becomes a candidate."""
    proposals: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    def _add(prefix: str, index: int, signal: str, ids: List[str], risk: str,
             review_action: str, caveat: str) -> None:
        key = "|".join(sorted(ids))
        if key in seen or len(ids) < 2:
            return
        seen.add(key)
        first = records.get(ids[0], {})
        preserved = [records[rid]["digest"] for rid in ids[: tuning.preserved_digests] if rid in records]
        proposals.append({
            "id": f"consolidate:{prefix}:{index}", "signal": signal,
            "source_ids": list(ids),
            "candidate_title": f"Consolidated: {first.get('title') or ids[0]}",
            "kind": first.get("kind", "memory"),
            "preserved_digests": preserved, "risk": risk,
            "review_action": review_action, "caveat": caveat,
        })

    for i, group in enumerate(duplicate_groups):
        _add("duplicate_title", i + 1, "duplicate_title", list(group["record_ids"]), "low",
             ("expand all sources, verify distinct facts/caveats, then review the "
              "inactive summary candidate carrying summarizes edges to every source"),
             "same normalized title within one kind; likely a repeated handle")
        if len(proposals) >= tuning.list_bound:
            return proposals
    for i, group in enumerate(shared_sources):
        _add("shared_source", i + 1, "shared_source", list(group["record_ids"]), "medium",
             ("review whether the shared source created redundant derived records; "
              "consolidate only if the newer handle preserves every source-specific fact"),
             "multiple records derive from one source; may be legitimate specializations")
        if len(proposals) >= tuning.list_bound:
            return proposals
    for i, pair in enumerate(near_dups):
        _add("near_duplicate", i + 1, "near_duplicate", list(pair["pair"]), "medium",
             "source-expand both records before any waking consolidation",
             "textual/vector similarity only; may be a false-positive topic overlap")
        if len(proposals) >= tuning.list_bound:
            return proposals
    return proposals


def maintenance_report(
    store: Any, journal: Any, *,
    scopes: Sequence[Tuple[str, str]], as_of: Optional[int] = None,
    scan_limit: Optional[int] = None,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
) -> Dict[str, Any]:
    """PURE READ phase-1 analysis (the fork's data-quality half of the
    maintenance ledger). Builds on structural_report (components/isolated —
    dream-pass semantics untouched) plus its own attribute-level scan.
    Deterministic ordering everywhere; deposits nothing; writes nothing.
    Every policy number rides `tuning`; an explicit scan_limit wins over
    the tuned default."""
    resolved_scan = tuning.resolve_scan_limit(scan_limit)
    base = structural_report(store, journal, scopes=scopes, as_of=as_of)
    records, edges, candidates = _scan(store, scopes)

    gaps = _metadata_gaps(records, tuning)
    unsourced = _unsourced_lessons(records, edges, tuning)
    duplicate_groups = _duplicate_title_groups(records, tuning)
    near_dups, vectorless_pairs = _near_duplicate_pairs(records, store, resolved_scan, tuning)
    shared_sources = _shared_source_groups(records, edges, tuning)
    link_candidates = _isolated_link_candidates(base, records, tuning)
    suppressions = _edge_suppression_candidates(records, edges, tuning)
    proposals = _consolidation_proposals(records, duplicate_groups, near_dups, shared_sources, tuning)

    operations: List[Dict[str, Any]] = []
    for gap in gaps:
        operations.append({
            "id": f"maintenance:metadata:{gap['record_id']}", "phase": "data_quality_tending",
            "kind": "metadata_gap", "status": "proposed", "node_ids": [gap["record_id"]],
            "summary": f"missing [{', '.join(gap['missing_fields'])}] — fill at a waking re-digestion",
            "risk": gap["risk"],
        })
    for link in link_candidates:
        operations.append({
            "id": f"maintenance:link:{link['pair'][0]}|{link['pair'][1]}",
            "phase": "data_quality_tending", "kind": "isolated_link_candidate",
            "status": "proposed", "node_ids": list(link["pair"]),
            "summary": link["reason"], "risk": link["risk"],
        })
    for sup in suppressions:
        operations.append({
            "id": f"maintenance:edge:{sup['pair'][0]}|{sup['pair'][1]}|{sup['predicate']}",
            "phase": "data_quality_tending", "kind": "edge_suppression_candidate",
            "status": "proposed", "node_ids": list(sup["pair"]),
            "summary": sup["reason"], "risk": sup["risk"],
        })
    for proposal in proposals:
        operations.append({
            "id": proposal["id"],
            "phase": ("data_quality_tending"
                      if proposal["signal"] in ("duplicate_title", "near_duplicate")
                      else "further_insight"),
            "kind": "consolidation_candidate", "status": "proposed",
            "node_ids": list(proposal["source_ids"]),
            "summary": f"{proposal['signal']} candidate `{proposal['candidate_title']}`",
            "risk": proposal["risk"],
        })
    operations.sort(key=lambda o: (o["phase"], o["kind"], o["risk"], o["id"]))
    bound = tuning.list_bound * tuning.operations_factor
    omitted = max(0, len(operations) - bound)

    return {
        "pass_name": "maintenance_report",
        "as_of_seq": base["as_of_seq"],
        "metadata_gaps": gaps,
        "unsourced_lessons": unsourced,
        "duplicate_title_groups": duplicate_groups,
        "near_duplicate_pairs": near_dups,
        "vectorless_pairs": vectorless_pairs,
        "shared_source_groups": shared_sources,
        "isolated_link_candidates": link_candidates,
        "edge_suppression_candidates": suppressions,
        "consolidation_proposals": proposals,
        "existing_candidates": candidates,
        "operations": operations[:bound],
        "operations_omitted": omitted,
        "isolated": [rid for rid in base.get("isolated", ()) if rid in records],
        "counts": {
            "records": len(records), "existing_candidates": len(candidates),
            "metadata_gaps": len(gaps), "unsourced_lessons": len(unsourced),
            "duplicate_title_groups": len(duplicate_groups),
            "near_duplicate_pairs": len(near_dups), "shared_source_groups": len(shared_sources),
            "isolated_link_candidates": len(link_candidates),
            "edge_suppression_candidates": len(suppressions),
            "consolidation_proposals": len(proposals),
        },
    }


def consolidation_pass(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
    max_candidates: int = 2, proposal_ids: Sequence[str] = (),
    report_only: bool = False, as_of: Optional[int] = None,
    scan_limit: Optional[int] = None,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
) -> Dict[str, Any]:
    """Phase-1's ONE write surface (fork create_consolidation_candidates):
    low-risk duplicate-title proposals become at most `max_candidates`
    (validated against SleepTuning.candidate_cap_band — out-of-band asks
    refuse loudly, never silently clamp) INACTIVE kind="summary" candidates
    via remember_many — summarizes edges to every source (true by
    construction: the candidate stands for exactly those records),
    review_required, sources byte-untouched. Idempotent by sorted source
    set; a group already covered by an existing candidate (equal or
    superset sources) is skipped. as_of anchors AUDIT reads only: writes
    under as_of are refused loudly."""
    if as_of is not None and not report_only:
        raise ValueError(
            "consolidation_pass: as_of anchors an audit read — writing candidates "
            "against a historical anchor would forge the timeline; pass report_only=True"
        )
    cap = tuning.validated_candidate_cap(max_candidates)
    store, journal = system.store, system.journal  # public substrate handles
    report = maintenance_report(
        store, journal, scopes=scopes, as_of=as_of, scan_limit=scan_limit, tuning=tuning)
    out: Dict[str, Any] = {
        "pass_name": "consolidation_pass",
        "report": report, "created": [], "skipped": [], "created_count": 0,
    }
    if report_only:
        out["skipped"].append({"reason": "report_only requested"})
        return out

    wanted = {str(p).strip() for p in (proposal_ids or ()) if str(p or "").strip()}
    selected = [p for p in report["consolidation_proposals"]
                if p["signal"] == "duplicate_title" and p["risk"] == "low"
                and (not wanted or p["id"] in wanted)]
    covered_sets = [set(c["source_ids"]) for c in report["existing_candidates"] if c["source_ids"]]

    for proposal in selected[:cap]:
        sources = list(proposal["source_ids"])
        if len(sources) < 2:
            out["skipped"].append({"proposal_id": proposal["id"], "reason": "fewer than two sources"})
            continue
        if any(set(sources) <= covered for covered in covered_sets):
            out["skipped"].append({
                "proposal_id": proposal["id"],
                "reason": "an existing inactive candidate already covers these sources",
            })
            continue
        digest = (
            f"Maintenance found {len(sources)} records carrying the same title "
            f"({proposal['kind']}). This candidate stands for the group pending waking "
            "review; every source remains intact and expandable — nothing was merged "
            "or removed while asleep."
        )
        fingerprint = hashlib.sha256("|".join(sorted(sources)).encode("utf-8")).hexdigest()
        key = f"maintenance-consolidation|{owner_id}|{fingerprint}"
        expected = record_id_for("summary", key, 0)
        existed = bool(store.query(TripleQuery(subject=expected, limit=1)))
        candidate = MemoryRecordInput(
            kind="summary",
            title=proposal["candidate_title"],
            digest=digest,
            edges=tuple(("summarizes", rid) for rid in sources),
            attributes={
                "maintenance_candidate": True,
                "review_required": True,
                "signal": proposal["signal"],
                "proposal_id": proposal["id"],
                "source_ids": sources,
                "source_count": len(sources),
                "no_source_mutation": True,
            },
        )
        [gid] = system.remember_many(
            [candidate], scope=scopes[0][0], owner_id=owner_id, idempotency_key=key)
        out["created"].append({
            "candidate_id": gid, "proposal_id": proposal["id"],
            "source_ids": sources, "created": not existed,
        })
    out["created_count"] = sum(1 for c in out["created"] if c["created"])
    return out


def sleep_pass(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
    max_candidates: int = 2, salience_floor: int = 2, max_sources: int = 8,
    embedder_similarity_floor: float = 0.35,
    report_only: bool = False, as_of: Optional[int] = None,
    scan_limit: Optional[int] = None,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
    should_continue: Optional[Any] = None,
    include_dream: bool = True,
) -> Dict[str, Any]:
    """One full sleep: RESOLVE first (the night reviews the day — standing
    dreams the day's lived experience already answered close softly,
    0032), then phase-1 tending, then the dream over the tended graph —
    the fork's canonical order extended by the maintainer's subconscious
    model, encoded engine-side so the host's on_sleep hook wires exactly
    one call. All phases idempotent; a quiet night in any phase is a valid
    night. The result names itself and its phases (self-describing shapes
    — review: three sleep verbs returned three near-miss dicts and a
    consumer confused two of them).

    Ordering rationale: resolution must PRECEDE tonight's dream so a
    settled tension never feeds continuation anchors again, and a
    continuation dream whose lineage closed resolves before it can re-arm
    salience.

    GRACEFUL CANCELLATION (the one-active-phase ruling, 2026-07-13: when
    the ENTITY's visit/personal/work phase activates, sleep's processes
    must END PROPERLY — the boundaries below are the NIGHT'S SUB-PHASES,
    not entity phases): `should_continue` is a zero-arg callable the HOST
    wires to its yield signal (loop mode flag, lease negotiation, door
    state). It is checked at SUB-PHASE BOUNDARIES only — including the
    start (a signal already raised at call time buys zero write phases) —
    complete-current-phase-then-stop is the grace contract: a mid-flight
    sub-phase is never torn by this mechanism; the one that already
    started finishes its writes, later ones are skipped with
    {"skipped_reason": "cancelled: ..."} and the night's result carries
    cancelled_after=<last completed sub-phase>. A skipped night is a
    VALID night (all sub-phases idempotent — the next sleep picks up
    exactly where this one stopped). HARD KILLS mid-phase degrade to
    crash semantics the engine already absorbs (idempotent formations,
    closure dedup, world-model crash-replay repair) — safe, but the
    boundary check is the graceful path hosts should prefer.

    include_dream=False is the MAINTENANCE-CYCLE composition (laurent
    dm#104 personal<->sleep cycle; v12 design adversary P1-6): the ~1h
    cycle window at every-2h cadence runs the graph-QUALITY passes
    (resolution / tending / world models / mining) while DREAM FORMATION
    keeps its own nightly-class cadence — naively reusing the whole
    night per cycle window would form a dream every ~3h (salience-50
    records piling into wake reasons, the bridge-attractor class). The
    dream phase then reports {"skipped_reason": "cycle window: dream
    formation keeps its nightly cadence budget"} — a valid night shape
    every consumer already handles. The host owns WHEN dreams run (a
    full sleep_pass nightly / at the day's last cycle window); the
    engine stays cadence-blind."""
    from .dream_resolution import resolve_dreams_pass
    from .world_model import world_model_pass

    if as_of is not None and not report_only:
        # One loud gate for the whole night (adversary P1-4): every write
        # phase refuses historical anchors individually; failing HERE
        # keeps an anchored mistake from producing a half-written night
        # (resolution closures landing before tending raises).
        raise ValueError(
            "sleep_pass: as_of anchors AUDIT reads only — pass "
            "report_only=True for anchored reads (a night written against "
            "a historical anchor would forge the timeline)")

    # Cancelled-phase shapes mirror the REAL empty pass shapes key-for-key
    # (phase-audit adversary finding 2: a phantom `formed` key resurrected
    # the documented formed-vs-created consumer bug class; near-miss dicts
    # are how the 2026-07-09 consolidator bug happened).
    def _cancelled(name: str, after: str, real_empty: Dict[str, Any]) -> Dict[str, Any]:
        return {"pass_name": name,
                "skipped_reason": f"cancelled: host ended sleep after {after} "
                                  "(one-active-phase transition)", **real_empty}

    def _cancelled_maintenance(after: str) -> Dict[str, Any]:
        return _cancelled("consolidation_pass", after,
                          {"report": {}, "created": [], "skipped": [], "created_count": 0})

    def _cancelled_world_models(after: str) -> Dict[str, Any]:
        return _cancelled("world_model_pass", after,
                          {"formed": [], "unchanged": [], "skipped": [], "repaired": [],
                           "targets_seen": 0, "eligible": [], "formed_count": 0,
                           "alias_proposals": []})

    def _cancelled_dream(after: str) -> Dict[str, Any]:
        return _cancelled("dream_pass", after,
                          {"report": {}, "proposals": [], "questions": [], "salience": 0,
                           "vectorless_pairs": 0, "trail_associated": [],
                           "context_associated": [],
                           "dream_record_id": None, "created": False})

    def _cancelled_mining(after: str) -> Dict[str, Any]:
        return _cancelled("mine_candidates_pass", after,
                          {"lesson_candidates": [], "interest_candidates": [],
                           "question_proposals": [], "drive_groups": [],
                           "created": [], "skipped": [],
                           "created_count": 0})

    def _go() -> bool:
        return should_continue is None or bool(should_continue())

    def _skipped_night(after: str, resolution_result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "pass_name": "sleep_pass",
            "phases": ("resolution", "maintenance", "world_models", "mining", "dream"),
            "cancelled_after": after,
            "resolution": resolution_result,
            "maintenance": _cancelled_maintenance(after),
            "world_models": _cancelled_world_models(after),
            "mining": _cancelled_mining(after),
            "dream": _cancelled_dream(after),
        }

    cancelled_after: Optional[str] = None
    # The start of the night is a boundary too (adversary finding 1): a
    # yield signal already raised when the verb is called must not buy a
    # whole write phase.
    if not _go():
        return _skipped_night(
            "start (no phase ran)",
            _cancelled("resolve_dreams_pass", "start (no phase ran)",
                       {"examined": 0, "resolved": [], "standing": [],
                        "as_of_seq": None, "resolved_count": 0}))
    resolution = resolve_dreams_pass(
        system, scopes=scopes, owner_id=owner_id,
        report_only=report_only, as_of=as_of, tuning=tuning)
    if not _go():
        return _skipped_night("resolution", resolution)
    maintenance = consolidation_pass(
        system, scopes=scopes, owner_id=owner_id, max_candidates=max_candidates,
        report_only=report_only, as_of=as_of, scan_limit=scan_limit, tuning=tuning)
    # Understanding refines after tending, before the dream (0033): cards
    # are report-excluded derived artifacts, so the dream never sees them —
    # the order just keeps the night's narrative honest (review the day,
    # tend the graph, refine understanding, then dream). Under an as_of
    # anchor the phase is SKIPPED honestly (it reads current state only;
    # a mixed-frame result would be worse than an absent one).
    if not _go():
        cancelled_after = "maintenance"
        world_models: Dict[str, Any] = _cancelled_world_models("maintenance")
    elif as_of is not None:
        world_models = {
            "pass_name": "world_model_pass",
            "skipped_reason": "as_of anchor: world models read current state "
                              "only — phase skipped to keep the night's "
                              "frames honest",
            "formed": [], "unchanged": [], "skipped": [], "repaired": [],
            "targets_seen": 0, "eligible": [], "formed_count": 0,
            "alias_proposals": [],
        }
    else:
        world_models = world_model_pass(
            system, scopes=scopes, owner_id=owner_id,
            report_only=report_only, tuning=tuning)
    # W2 MINING (wave-4 dispatch): lesson/interest candidates from repeated
    # session evidence + question-resolution proposals — after
    # understanding refines, before the dream (the dream metabolizes the
    # mining acts through its signal stream). Same as_of rule as world
    # models: the miner reads current diary/evidence state, so an anchored
    # night skips it honestly.
    if cancelled_after is None and not _go():
        cancelled_after = ("maintenance" if world_models.get("skipped_reason")
                          else "world_models")
    if cancelled_after is not None:
        mining: Dict[str, Any] = _cancelled_mining(cancelled_after)
    elif as_of is not None:
        mining = {
            "pass_name": "mine_candidates_pass",
            "skipped_reason": "as_of anchor: the miner reads current diary/"
                              "evidence state only — phase skipped to keep "
                              "the night's frames honest",
            "lesson_candidates": [], "interest_candidates": [],
            "question_proposals": [], "drive_groups": [],
            "created": [], "skipped": [],
            "created_count": 0,
        }
    else:
        from .candidate_miner import mine_candidates_pass
        mining = mine_candidates_pass(
            system, scopes=scopes, owner_id=owner_id,
            max_candidates=max_candidates, report_only=report_only,
            scan_limit=scan_limit or 0, tuning=tuning)
    # The dream metabolizes the night's work: the tending ledger's operation
    # count feeds dream salience (fork parity, capped in SleepTuning — a busy
    # tending night signals change worth dreaming about).
    if cancelled_after is None and not _go():
        # Honest label (adversary finding 6): under as_of the mining phase
        # was SKIPPED, not completed — cancelled_after names the last
        # phase that actually ran.
        cancelled_after = ("maintenance" if world_models.get("skipped_reason")
                          else ("world_models" if mining.get("skipped_reason")
                                else "mining"))
    if cancelled_after is not None:
        dream = _cancelled_dream(cancelled_after)
    elif not include_dream:
        # Maintenance-cycle window (v12 P1-6): quality passes ran; dream
        # formation keeps its nightly cadence budget. Same empty shape as
        # every other honest skip.
        dream = {
            "pass_name": "dream_pass",
            "skipped_reason": ("cycle window: dream formation keeps its "
                               "nightly cadence budget (include_dream=False)"),
            "report": {}, "proposals": [], "questions": [], "salience": 0,
            "vectorless_pairs": 0, "trail_associated": [],
            "context_associated": [],
            "dream_record_id": None, "created": False,
        }
    else:
        ops_count = len((maintenance.get("report") or {}).get("operations") or ())
        dream = dream_pass(
            system, scopes=scopes, owner_id=owner_id, salience_floor=salience_floor,
            max_sources=max_sources, embedder_similarity_floor=embedder_similarity_floor,
            report_only=report_only, as_of=as_of, maintenance_ops=ops_count,
            tuning=tuning,
            # The dream metabolizes the WHOLE night (Q1 ruling): earlier
            # phases' results become the signal stream on the dream record.
            phase_results={"resolution": resolution, "maintenance": maintenance,
                           "world_models": world_models, "mining": mining})
    result: Dict[str, Any] = {
        "pass_name": "sleep_pass",
        "phases": ("resolution", "maintenance", "world_models", "mining", "dream"),
        "resolution": resolution,
        "maintenance": maintenance,
        "world_models": world_models,
        "mining": mining,
        "dream": dream,
    }
    if cancelled_after is not None:
        result["cancelled_after"] = cancelled_after
    return result
