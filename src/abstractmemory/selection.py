"""Commit-selection derivations: Hebbian pairs, scope grouping, replay identity.

One task (split out of system.py to honor the <600-lines-per-file rule when
the idempotency addendum landed): everything `MemorySystem.commit_selection`
derives from a used-record set before touching the journal — normalized used
ids, per-(scope, owner) event grouping with co-use pairs (maintainer rule,
2026-07-07: ALL pairs within the depositing slice) plus the earlier
term-sharing (0018) and recorded-edge hop routes, snapshot display rows, and
the DETERMINISTIC ids that make at-least-once replays no-ops (a2a 0001/011
ask 2). Pure functions; no store access beyond the optional edge scan.

Replay identity: runtime effects execute at-least-once (crash between
STARTED and COMPLETED → replay re-runs commit_selection). Every journal
record a commit writes therefore carries an id derived purely from
(trace_id, kind, canonical key), so the journal's supplied-id dedup turns
the replayed writes into no-ops. trace_id is the commit's identity anchor:
one trace = one selection = one trail deposit.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .canonical_text import display_title, handle_digest, token_estimate
from .models import TripleAssertion
from .store import TripleQuery

__all__ = [
    "display_rows",
    "normalize_used_ids",
    "plan_selection",
    "selection_event_id",
    "selection_snapshot_id",
]

# 32 hex chars (128 bits of sha256): collision-safe at any realistic scale
# while matching the length of the uuid4().hex ids used elsewhere.
_ID_HEX_LEN = 32


def _derived_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:_ID_HEX_LEN]


def selection_event_id(trace_id: str, kind: str, key: str) -> str:
    """Deterministic event id for one commit deposit.

    key = record_id for 'selected', "a+b" (canonical sorted pair) for
    'co_selected'. Two different traces committing the same record produce
    DIFFERENT ids (both deposits are genuine uses); replaying one trace's
    commit reproduces the SAME ids (journal dedup makes it a no-op).
    """
    return _derived_id(str(trace_id), str(kind), str(key))


def selection_snapshot_id(trace_id: str) -> str:
    """Deterministic snapshot id for a trace's commit. Also used as the
    events' context_ref, so a crash-replayed commit re-derives the same
    snapshot identity and the events↔snapshot linkage stays consistent."""
    return _derived_id(str(trace_id), "snapshot")


def normalize_used_ids(used_record_ids: Sequence[str]) -> List[str]:
    """Strip + order-preserving dedupe; empty result is a caller error
    (one commit = one use; duplicates deposit once)."""
    ordered: List[str] = []
    seen: set = set()
    for raw in used_record_ids or ():
        rid = str(raw or "").strip()
        if rid and rid not in seen:
            seen.add(rid)
            ordered.append(rid)
    if not ordered:
        raise ValueError(
            "commit_selection requires at least one used_record_id (an empty commit "
            "would deposit no trail; skip the call instead)"
        )
    return ordered


def plan_selection(
    ordered: Sequence[str], fetched: Dict[str, TripleAssertion], store: Optional[Any] = None
) -> Dict[Tuple[str, str], Dict[str, list]]:
    """Group the used set per (scope, owner_id) and derive Hebbian pairs.

    CO-USE RULE (maintainer-initiated, 2026-07-07 — "not enough
    relationships are created"): ALL unordered pairs within `ordered` wire
    together. `ordered` is the DEPOSITING SLICE — commit_selection passes
    only admission="stimulus"/"both" ids here (exactly the ids that deposit
    'selected'), so presence ≠ use extends to association: self/STM/
    (future historical) members pair with NOTHING, and the classic
    hub-node failure cannot route through identity BY CONSTRUCTION — the
    depositing-slice rule is the hub guard now. Bounded by the shelf
    (worst case C(12,2)=66 pairs); the fork's canonical model expects
    exactly this ("pair count = how often did these two memories serve one
    moment together").

    Term rule (0018, kept): shared subject/object terms also wire — this
    was the RAW-TRIPLE-ERA mechanism (never a guard against co-use
    pairing); predicates stay excluded ("works_at" hubs). Now subsumed by
    the co-use rule within one commit but kept for its documented
    semantics and any caller composing plans directly.

    Edge rule (audit repro9, kept): recorded edge assertions BETWEEN used
    subjects deposit trails keyed as the SPREADING HOP PAIRS —
    (source_digest_id, edge_id) and (edge_id, target_digest_id) — because
    those are the pairs spread_activation looks up during traversal; a
    (digestA, digestB) co-use pair additionally lets spreading walk
    DIRECTLY between co-used records.

    Grouping: activation streams are scope-partitioned, so events land in
    each record's own (scope, owner) stream. A cross-group pair is hosted by
    the group of whichever pair member appears FIRST in the used order
    (deterministic; a pair must live in exactly one stream, and the
    first-used record's stream is the reading context that co-activated
    both). Groups are insertion-ordered by first use; pairs are deduped
    per group (a pair earned by two routes deposits once per commit).
    """

    def _group_of(rid: str) -> Tuple[str, str]:
        a = fetched[rid]
        return (a.scope, a.owner_id or "")

    groups: Dict[Tuple[str, str], Dict[str, list]] = {}
    for rid in ordered:
        groups.setdefault(_group_of(rid), {"records": [], "pairs": []})["records"].append(rid)

    def _add_pair(host_rid: str, pair: Tuple[str, str]) -> None:
        pairs = groups[_group_of(host_rid)]["pairs"]
        if pair not in pairs:
            pairs.append(pair)

    # CO-USE: every unordered pair in the depositing slice (see docstring).
    for i, rid_a in enumerate(ordered):
        for rid_b in ordered[i + 1 :]:
            _add_pair(rid_a, tuple(sorted((rid_a, rid_b))))

    # Term rule (raw-triple era; see docstring — subsumed within one commit
    # by the co-use rule, kept for direct plan composition).
    for i, rid_a in enumerate(ordered):
        terms_a = {t for t in (fetched[rid_a].subject, fetched[rid_a].object) if t}
        for rid_b in ordered[i + 1 :]:
            terms_b = {t for t in (fetched[rid_b].subject, fetched[rid_b].object) if t}
            if terms_a & terms_b:
                _add_pair(rid_a, tuple(sorted((rid_a, rid_b))))

    if store is not None:
        # First-used wins when two used assertions share a subject (defensive;
        # normally one digest per subject is used at a time).
        subject_to_rid: Dict[str, str] = {}
        for rid in ordered:
            subject_to_rid.setdefault(fetched[rid].subject, rid)
        # Bounded by the shelf: the used set is at most one shelf, and a
        # subject rarely owns more than a handful of edges — 4x headroom.
        scan_limit = max(16, 4 * len(ordered))
        for subject, source_rid in subject_to_rid.items():
            src = fetched[source_rid]
            rows = store.query(TripleQuery(subject=subject, scope=src.scope,
                                           owner_id=src.owner_id or None, limit=scan_limit))
            for edge in rows:
                attrs = edge.attributes if isinstance(edge.attributes, dict) else {}
                if not attrs.get("record_edge") or not edge.assertion_id:
                    continue
                target_rid = subject_to_rid.get(edge.object)
                if target_rid is None or target_rid == source_rid:
                    continue  # edge leaves the used set: no co-use to deposit
                _add_pair(source_rid, tuple(sorted((source_rid, edge.assertion_id))))
                _add_pair(source_rid, tuple(sorted((edge.assertion_id, target_rid))))
    return groups


def display_rows(ordered: Sequence[str], fetched: Dict[str, TripleAssertion]) -> List[Dict[str, Any]]:
    """Snapshot display metadata: references + previews, never payload copies."""
    rows: List[Dict[str, Any]] = []
    for rid in ordered:
        digest = handle_digest(fetched[rid])  # clean literal for formed records (v2)
        rows.append(
            {
                "record_id": rid,
                "title": display_title(fetched[rid]),
                "digest": digest,
                "token_estimate": token_estimate(digest),
            }
        )
    return rows
