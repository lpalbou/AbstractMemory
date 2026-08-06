"""Recent-work read: "what have I been working on recently?" (the breadcrumb).

Born from Ephemeral's own gap, named in visit 1 (2026-07-17, mission c2914):
"if I'm alone and wondering where did I leave my own thinking, there's no
breadcrumb trail" — his proposed surface verbatim: "a way to ask 'what have
I been working on recently' without already knowing the answer." That is a
RECENCY/AGENDA query, not a similarity query: search_memory needs words to
match, diary_list covers only the book, and the recall shelf serves the
moment's cue. NOTHING covered "my last N formed records by time window" —
this module is that read.

Contract (the division runtime's visit report named): the ENGINE offers the
time-window read; the host (runtime) wires the tool surface, the #tag
render, and the teaching line. Pure read — no trace, no deposits, no
journal writes (asking "where did I leave off" must not reorder what you
left; the audit-inertness rule that governs recall_history applies).

Honesty rules:
- Closure/hidden folds APPLY (one exclusion path — folds.py): a superseded
  or hidden record is not "what you have been working on".
- Machine records stay out: bookkeeping/maintenance-candidate rows and
  record_edge rows never surface (a consolidation candidate is the
  engine's desk, not his).
- Digests are the payload (prompt currency, same as probe hits); private
  diary projections already carry act-only digests at formation, so this
  read leaks nothing search_memory would not.
- Both id namespaces ride every row (record_id = digest row id, the
  trace/commit currency; graph_id = the edge/expansion currency) plus the
  re-entry keys the M-A mint made contract (entry_id/diary_type/phase).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .canonical_text import handle_digest
from .folds import binding_states, closure_exclusions
from .store import TripleQuery

__all__ = ["RECENT_RECORDS_DEFAULT_LIMIT", "recent_records"]

# Enough for "where did I leave off" without becoming a store dump; the
# caller widens explicitly. A breadcrumb trail is a page, not an archive.
RECENT_RECORDS_DEFAULT_LIMIT = 24


def recent_records(
    store: Any,
    journal: Any,
    *,
    scopes: Sequence[Tuple[str, str]],
    since: str,
    until: Optional[str] = None,
    kinds: Optional[Sequence[str]] = None,
    limit: int = RECENT_RECORDS_DEFAULT_LIMIT,
    as_of: Optional[int] = None,
) -> Dict[str, Any]:
    """Formed records across the given scope pairs with observed_at >= since
    (and <= until when given), newest first, folds applied.

    Returns {"records": [...], "counts": {kind: n}, "window": {...},
    "truncated": bool}. Each record row: {record_id, graph_id, kind, title,
    digest, observed_at, scope, owner_id} plus entry_id/diary_type/phase
    when the attributes carry them (keys only — words stay in the book).
    `as_of` anchors the closure/hidden folds (None = journal head), the
    same replay semantics as every other read.
    """
    window_since = str(since or "").strip()
    if not window_since:
        raise ValueError(
            "recent_records requires `since` (ISO timestamp) — the breadcrumb "
            "is a time-window read; an unbounded 'everything ever' read is a "
            "store dump, not a trail"
        )
    bound = int(limit)
    if bound < 1:
        raise ValueError(f"limit must be >= 1 (got {limit!r})")
    scope_pairs = [(str(s or "").strip().lower(), str(o or "").strip())
                   for s, o in (scopes or ()) if str(s or "").strip()]
    if not scope_pairs:
        raise ValueError("recent_records requires at least one (scope, owner_id) pair")
    kind_filter = {str(k).strip().lower() for k in (kinds or ()) if str(k).strip()}

    seq = int(as_of) if as_of is not None else int(journal.current_seq())
    excluded = set(closure_exclusions(journal, seq))
    _states, hidden, _active = binding_states(store, journal, scope_pairs, seq)
    excluded |= set(hidden)

    rows: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    truncated = False
    for scope, owner in scope_pairs:
        # Over-fetch per pair by the exclusion mass so folded-out rows
        # cannot starve the window (the reconstruction gather's f2 lesson),
        # +1 lookahead so the truncated flag can observe that more work
        # exists past the page (a fetch of exactly `bound` rows could
        # never distinguish a full page from a truncated one).
        fetch = bound + min(len(excluded), 200) + 1
        for a in store.query(TripleQuery(
                scope=scope, owner_id=owner or None,
                predicate="dcterms:abstract",
                since=window_since, until=until, limit=fetch)):
            rid = a.assertion_id
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            kind = str(attrs.get("record_kind") or "").strip().lower()
            if not (isinstance(rid, str) and rid) or not kind:
                continue  # raw triples are not lived records
            if rid in excluded or str(a.subject or "") in excluded:
                continue
            if attrs.get("bookkeeping") or attrs.get("record_edge") or attrs.get("maintenance_candidate"):
                continue
            if kind_filter and kind not in kind_filter:
                continue
            row: Dict[str, Any] = {
                "record_id": rid,
                "graph_id": str(a.subject or ""),
                "kind": kind,
                "title": str(attrs.get("title") or "").strip(),
                "digest": handle_digest(a),
                "observed_at": str(a.observed_at or ""),
                "scope": a.scope,
                "owner_id": a.owner_id or "",
            }
            # The M-A key contract, mirrored: re-entry keys ride when the
            # record carries them; no fabricated keys otherwise.
            for key in ("entry_id", "diary_type", "phase"):
                value = attrs.get(key)
                if isinstance(value, str) and value.strip():
                    row[key] = value.strip()
            rows.append(row)

    # Newest first across all pairs; deterministic tie-break on record id.
    rows.sort(key=lambda r: (r["observed_at"], r["record_id"]), reverse=True)
    if len(rows) > bound:
        rows = rows[:bound]
        truncated = True  # more work exists in the window than the page shows

    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1

    return {
        "records": rows,
        "counts": counts,
        "window": {"since": window_since, "until": until, "as_of_seq": seq,
                   "scopes": [list(p) for p in scope_pairs]},
        "truncated": truncated,
    }
