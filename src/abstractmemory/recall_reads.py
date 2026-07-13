"""Recall-decision reads: "why was X (never) recalled?" as a query (fork 605).

The traces already record everything — admissions, bounded candidate lists,
dropped-with-reasons — per reconstruction. What was missing (the
fork-comparison audit, 2026-07-12) is the READ indexed by RECORD id across
traces: when an entity (or its operator) feels an absence ("I know I lived
this — why does it never come back?"), the answer today is a forensic
session over raw traces. The fork made it a first-class read; this module
is that read in seam terms.

Two surfaces, both pure reads:

- `recall_history(journal, record_id, ...)`: walk traces newest-first and
  classify the record's part in each — selected (with admission label),
  dropped (with the recorded reason), candidate-only (scored but never
  placed), or absent. Probe/expand traces are included and labeled by
  trace_kind: a deliberate reach that found the record IS part of its
  recall history.
- `absence_diagnosis(store, journal, record_id, scope, owner_id)`: when the
  history says "mostly absent", diagnose WHY in structural terms — closed?
  hidden by binding? no keywords (keyword channel can only match its
  title/digest tokens)? no stored vector (the vector channel cannot rank
  it)? never bound to the searched scope? Each diagnosis is a plain
  sentence naming the mechanism, never a guess.

The facade composes both as `MemorySystem.recall_history(...)` — history +
diagnosis in one answer. Nothing here writes: explaining recall is not
using (0018's audit-inertness rule applies to the explanation itself).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .folds import binding_states, closure_exclusions
from .store import TripleQuery

__all__ = ["absence_diagnosis", "recall_history"]

# Bounded trace walk: enough nights/turns to answer "recently, why not X"
# without turning the explainability read into its own storage scan.
# Declared tunable via the limit_traces parameter.
DEFAULT_TRACE_WALK = 200


def _identity_set(store: Any, record_id: str) -> Set[str]:
    """BOTH ids for one record (the works-or-loud namespace rule): traces
    speak ROW ids, edges speak GRAPH ids, and a caller may hold either.
    Unknown ids return just themselves — history over an unformed id is an
    honest all-absent read, and the diagnosis surface names the namespace
    problem explicitly."""
    rid = str(record_id or "").strip()
    ids = {rid}
    try:
        from .records import resolve_digest_assertion

        digest = resolve_digest_assertion(store, rid)
        if digest is not None:
            ids.add(str(digest.subject or rid))
            if digest.assertion_id:
                ids.add(str(digest.assertion_id))
    except Exception:
        pass  # a diagnosis read must never crash on a store hiccup
    return ids


def recall_history(
    journal: Any,
    record_id: str,
    *,
    limit_traces: int = DEFAULT_TRACE_WALK,
    until_seq: Optional[int] = None,
    store: Any = None,
) -> Dict[str, Any]:
    """The record's part in recent reconstructions, newest first.

    Returns {record_id, events, counts, traces_walked}: each event is
    {trace_id, seq, observed_at, trace_kind, status, admission?, reason?,
    scores?} with status ∈ selected | dropped | candidate_only. Traces the
    record never appeared in are counted (absent) but not itemized — the
    absences are the diagnosis surface's job. When a store is supplied the
    input id matches through BOTH namespaces (row and graph — adversary
    F2: probe hits hand hosts row ids, edges hand graph ids, and the
    history join must work from either).
    """
    rid = str(record_id or "").strip()
    if not rid:
        raise ValueError("recall_history requires a record id")
    ids = _identity_set(store, rid) if store is not None else {rid}

    traces = journal.traces(limit=int(limit_traces), until_seq=until_seq)
    events: List[Dict[str, Any]] = []
    counts = {"selected": 0, "dropped": 0, "candidate_only": 0, "absent": 0}

    for trace in traces:
        status: Optional[str] = None
        entry: Dict[str, Any] = {
            "trace_id": trace.trace_id,
            "seq": int(trace.seq),
            "observed_at": trace.observed_at,
            "trace_kind": trace.trace_kind,
        }
        selected_hit = next((s for s in (trace.selected or ()) if s in ids), None)
        if selected_hit is not None:
            status = "selected"
            admission = (trace.admissions or {}).get(selected_hit)
            if admission:
                entry["admission"] = admission
        else:
            for d in trace.dropped or ():
                if isinstance(d, dict) and (d.get("record_id") in ids
                                            or d.get("graph_id") in ids):
                    status = "dropped"
                    entry["reason"] = str(d.get("reason") or "")
                    if d.get("score") is not None:
                        entry["score"] = d.get("score")
                    break
            if status is None:
                for c in trace.candidates or ():
                    if isinstance(c, dict) and c.get("record_id") in ids:
                        status = "candidate_only"
                        entry["scores"] = dict(c.get("scores") or {})
                        break
        if status is None:
            counts["absent"] += 1
            continue
        entry["status"] = status
        counts[status] += 1
        events.append(entry)

    return {
        "record_id": rid,
        "events": events,
        "counts": counts,
        "traces_walked": len(traces),
    }


def absence_diagnosis(
    store: Any,
    journal: Any,
    record_id: str,
    *,
    scope: str,
    owner_id: str,
) -> Dict[str, Any]:
    """Structural reasons the record may be unreachable, in plain sentences.

    Checks, in mechanism order: existence → closure → binding visibility →
    keyword reachability → vector reachability. `channels_reachable` names
    which recall channels can currently surface the record at all.
    """
    rid = str(record_id or "").strip()
    scope_n = str(scope or "").strip().lower()
    owner = str(owner_id or "").strip()
    if not rid or not scope_n:
        raise ValueError("absence_diagnosis requires record_id and scope")

    reasons: List[str] = []
    channels: List[str] = []

    # BOTH namespaces resolve (adversary F2): a probe hit's row id and an
    # edge's graph id both name the record.
    from .records import resolve_digest_assertion

    a = resolve_digest_assertion(store, rid)
    if a is None:
        return {
            "record_id": rid,
            "reasons": [f"no digest row exists for {rid!r} in the store — it was never formed here, "
                        "or the id belongs to another namespace (row ids vs graph ids)"],
            "channels_reachable": [],
        }
    graph_id = str(a.subject or rid)
    attrs = a.attributes if isinstance(a.attributes, dict) else {}

    as_of = int(journal.current_seq())
    closed = closure_exclusions(journal, as_of)
    if graph_id in closed or (a.assertion_id and a.assertion_id in closed):
        reasons.append("the record is CLOSED (retracted/superseded) — closure folds exclude it from recall")

    # The hidden fold materializes ASSERTION ids (adversary F3: checking
    # the graph id against it could never fire).
    states, hidden, _active = binding_states(store, journal, [(scope_n, owner)], as_of)
    if (a.assertion_id and a.assertion_id in hidden) or graph_id in hidden:
        reasons.append("its binding is HIDDEN for this scope — re-bind search_state='indexed' to restore")
    binding = states.get((graph_id, scope_n, owner))
    if binding is None and a.scope != scope_n:
        reasons.append(
            f"it is stored under scope {a.scope!r}, not {scope_n!r} — a ladder that "
            "never includes its scope pair cannot reach it")

    # Exact channel: reachable by id/pattern always (when not closed/hidden).
    if not reasons:
        channels.append("exact (by anchor id or matching pattern)")

    keywords = attrs.get("keywords")
    from .text_tokens import tokenize
    digest_tokens = tokenize(f"{attrs.get('title') or ''} {a.object or ''}")
    # Reach caveat (adversary F6): keyword/concept scans cover the newest
    # candidate window per scope, not the whole store — "reachable" here
    # means "matchable IF scanned", and an old record may sit past the
    # window at any effort.
    window_note = "; note: keyword/concept scans cover the newest candidate window per scope — an old record may sit past it (probe deep widens; FTS5/0019 lifts)"
    if isinstance(keywords, (list, tuple)) and keywords:
        channels.append("keyword (formation keywords present" + window_note + ")")
    elif digest_tokens:
        channels.append("keyword (title/digest tokens only — no formation keywords" + window_note + ")")
    else:
        reasons.append(
            "it has NO formation keywords and its title/digest yield no recall tokens "
            "(short or non-Latin text) — the keyword channel cannot match it (FTS5/0019 "
            "is the standing fix; concept anchoring may still reach it via facets)")

    embedding = getattr(a, "embedding", None)
    if embedding:
        channels.append("vector (stored embedding present)")
    else:
        reasons.append(
            "it carries NO stored vector — the vector channel cannot rank it "
            "(formed before the embedder was wired, or the store is vectorless; "
            "reembed_store backfills)")

    participants = attrs.get("participants")
    if isinstance(participants, (list, tuple)) and participants:
        channels.append("participants (shared-context overlap)")

    if not reasons:
        reasons.append(
            "no structural barrier found — absence in recent traces means it lost "
            "the shelf race on relevance/budget (see recall_history for the drop "
            "reasons; probe() is the deliberate reach)")

    return {"record_id": rid, "reasons": reasons, "channels_reachable": channels}
