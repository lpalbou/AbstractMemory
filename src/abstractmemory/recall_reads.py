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

`explain_recall(...)` (backlog 0042) is the third surface: ONE serving
dict answering "why did/didn't record X surface in THIS recall?" — the
question every cue-dilution and bridge-attractor diagnosis answered with
a hand-written forensic script. It COMPOSES the two reads above against
one trace (named by trace_id, or the newest): status + admission label +
the per-channel relevance parts the trace recorded + shelf position vs
cut + budgets + origin, and the structural absence diagnosis when the
record never appeared. HONESTY RULE (0042): the explanation reports only
what the trace RECORDED at recall time — activation was never journaled
per-candidate, so it reads {"recorded": false} with a plain note, NEVER
a fresh number presented as the past decision. Consumers version by
FIELD PRESENCE, never schema forks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .folds import binding_states, closure_exclusions
from .store import TripleQuery

__all__ = ["absence_diagnosis", "explain_recall", "recall_history"]

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
    from .records import resolve_digest_assertion

    rid = str(record_id or "").strip()
    ids = {rid}
    # No exception guard, by the silent-fallback law (the same rule
    # `alive_drives` states): an unformed id already resolves to None and
    # reads as honestly absent, so the only thing a guard here could catch is
    # a genuinely broken store — which must raise loudly, never read as a
    # quiet desk with nothing recalled.
    digest = resolve_digest_assertion(store, rid)
    if digest is not None:
        ids.add(str(digest.subject or rid))
        if digest.assertion_id:
            ids.add(str(digest.assertion_id))
    return ids


def _trace_status(trace: Any, ids: Set[str]) -> Optional[Dict[str, Any]]:
    """The record's recorded part in ONE trace, or None (absent). One
    classifier for recall_history AND explain_recall — two surfaces
    reading the same trace must never disagree on what it says.
    Returns {status, admission?, reason?, score?, scores?, candidate_rank?}:
    candidate_rank is the 1-based position in the trace's bounded
    strongest-first candidate list, when the record appears in it."""
    out: Dict[str, Any] = {}
    selected_hit = next((s for s in (trace.selected or ()) if s in ids), None)
    if selected_hit is not None:
        out["status"] = "selected"
        admission = (trace.admissions or {}).get(selected_hit)
        if admission:
            out["admission"] = admission
    else:
        for d in trace.dropped or ():
            if isinstance(d, dict) and (d.get("record_id") in ids
                                        or d.get("graph_id") in ids):
                out["status"] = "dropped"
                out["reason"] = str(d.get("reason") or "")
                if d.get("score") is not None:
                    out["score"] = d.get("score")
                break
    for rank, c in enumerate(trace.candidates or (), start=1):
        if isinstance(c, dict) and c.get("record_id") in ids:
            out["candidate_rank"] = rank
            out["scores"] = dict(c.get("scores") or {})
            if "status" not in out:
                out["status"] = "candidate_only"
            break
    return out if "status" in out else None


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
        part = _trace_status(trace, ids)
        if part is None:
            counts["absent"] += 1
            continue
        entry: Dict[str, Any] = {
            "trace_id": trace.trace_id,
            "seq": int(trace.seq),
            "observed_at": trace.observed_at,
            "trace_kind": trace.trace_kind,
            "status": part["status"],
        }
        # Field parity with the established event shape: scores itemize
        # candidate_only events only (selected/dropped keep their original
        # compact entries; explain_recall is the per-trace deep view).
        if part["status"] == "selected" and "admission" in part:
            entry["admission"] = part["admission"]
        if part["status"] == "dropped":
            entry["reason"] = part.get("reason", "")
            if "score" in part:
                entry["score"] = part["score"]
        if part["status"] == "candidate_only":
            entry["scores"] = part.get("scores", {})
        counts[part["status"]] += 1
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


def _record_origin(store: Any, ids: Set[str]) -> Dict[str, Any]:
    """The record's formation identity (kind, formed_at, provenance voice) —
    origin_diversity's voice fields, served per record. Provenance is
    immutable at formation, so store truth IS recall-time truth here."""
    from .records import resolve_digest_assertion

    digest = None
    for rid in sorted(ids):
        digest = resolve_digest_assertion(store, rid)
        if digest is not None:
            break
    if digest is None:
        return {"formed": False,
                "note": "no digest row exists for this id in the store"}
    attrs = digest.attributes if isinstance(digest.attributes, dict) else {}
    prov = digest.provenance if isinstance(digest.provenance, dict) else {}
    return {
        "formed": True,
        "graph_id": str(digest.subject or ""),
        "kind": str(attrs.get("record_kind") or "memory"),
        "title": str(attrs.get("title") or ""),
        "formed_at": str(digest.observed_at or ""),
        "source": str(prov.get("source") or ""),
        "actor": str(prov.get("actor") or ""),
        "session_id": str(prov.get("session_id") or prov.get("run_id")
                          or prov.get("turn_id") or ""),
    }


def explain_recall(
    store: Any,
    journal: Any,
    record_id: str,
    *,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """"Why did/didn't record X surface in THIS recall?" as ONE serving
    dict (backlog 0042) — the composition of the two reads above against
    one trace, so the diagnosis method that worked live ("felt absence
    decomposed measurably") is a surface anyone can render.

    Trace selection: `trace_id` names the recall to explain; None = the
    newest trace (the "that last recall" question). A named trace that
    does not exist raises loudly — explaining a phantom recall would be
    fabrication. No traces at all returns status="no_recall_recorded".

    Status vocabulary: selected | dropped | candidate_only | absent |
    no_recall_recorded. The scopes come FROM THE TRACE (searched_scopes) —
    "why not in this recall" can only mean the scopes this recall
    searched; the absent branch runs the structural diagnosis per pair.

    HONESTY RULES (0042, non-negotiable):
    - the explanation reports what the trace RECORDED at recall time.
      Per-candidate activation was never journaled, so `activation` reads
      {"recorded": false} with a plain note — never a fresh number
      presented as the past decision.
    - relevance parts come from the trace's BOUNDED candidate list; a
      record outside it reads {"recorded": false} with the bound named.
    - shelf rank is labeled what it is: the strongest-fused position in
      the bounded candidate list at trace time, not a replay of the fill.
    Consumers version by FIELD PRESENCE, never schema forks. Pure read.
    """
    rid = str(record_id or "").strip()
    if not rid:
        raise ValueError("explain_recall requires a record id")
    ids = _identity_set(store, rid)

    trace = None
    if trace_id is not None:
        wanted = str(trace_id).strip()
        found = journal.traces(trace_id=wanted, limit=1)
        if not found:
            raise ValueError(
                f"explain_recall: no trace {wanted!r} exists in this journal — "
                "explaining a recall that never ran would be fabrication")
        trace = found[0]
    else:
        newest = journal.traces(limit=1)
        trace = newest[0] if newest else None

    origin = _record_origin(store, ids)
    out: Dict[str, Any] = {"record_id": rid, "origin": origin}
    if trace is None:
        out["status"] = "no_recall_recorded"
        out["note"] = ("this journal holds no reconstruction/probe traces — "
                       "no recall has run to explain")
        return out

    searched: List[Tuple[str, str]] = [
        (str(s.get("scope") or ""), str(s.get("owner_id") or ""))
        for s in (trace.searched_scopes or ())
        if isinstance(s, dict) and str(s.get("scope") or "").strip()
    ]
    out["trace"] = {
        "trace_id": trace.trace_id,
        "seq": int(trace.seq),
        "observed_at": trace.observed_at,
        "trace_kind": trace.trace_kind,
        "channels": list(trace.channels or ()),
        "searched_scopes": [{"scope": s, "owner_id": o} for s, o in searched],
        "stop_reason": trace.stop_reason,
        "warnings": list(trace.warnings or ()),
    }
    out["budgets"] = dict(trace.budgets or {})
    out["budget_spent"] = dict(trace.budget_spent or {})
    out["activation"] = {
        "recorded": False,
        "note": ("not recorded in this trace — traces carry per-channel "
                 "relevance and drop reasons; activation influenced ordering "
                 "at recall time but was never journaled per candidate"),
    }

    part = _trace_status(trace, ids)
    if part is None:
        out["status"] = "absent"
        reasons: List[str] = []
        # Timing first: a record formed AFTER the trace could never have
        # surfaced in it — the cheapest true explanation there is.
        formed_after = False
        formed_at = str(origin.get("formed_at") or "")
        if origin.get("formed") and formed_at and str(trace.observed_at or ""):
            if formed_at > str(trace.observed_at):
                formed_after = True
                reasons.append(
                    "the record was formed AFTER this recall ran "
                    f"(formed {formed_at}, recall {trace.observed_at}) — "
                    "no recall can surface a memory that did not exist yet; "
                    "structural diagnosis skipped (a record that never raced "
                    "cannot have lost the race)")
        if not searched:
            reasons.append(
                "this trace records no searched scopes — the structural "
                "diagnosis has nothing to run against")
        out["diagnosis"] = {
            "note": reasons,
            # Adversary P1-2: a formed-after record never raced this recall —
            # running the structural diagnosis anyway would answer "it lost
            # the shelf race", which is factually false for it.
            "by_scope": [] if formed_after else [
                {"scope": scope, "owner_id": owner,
                 **{k: v for k, v in absence_diagnosis(
                     store, journal, rid, scope=scope, owner_id=owner,
                 ).items() if k != "record_id"}}
                for scope, owner in searched
            ],
        }
        return out

    out["status"] = part["status"]
    if "admission" in part:
        out["admission"] = part["admission"]  # self | stm | stimulus | both
    if part["status"] == "dropped":
        out["reason"] = part.get("reason", "")
        if "score" in part:
            out["score"] = part["score"]

    # Adversary P1-1: expand traces retain candidates with scores={} BY
    # DESIGN (they record no per-channel parts) — key presence alone would
    # claim recorded parts that never existed. Recorded means NON-EMPTY.
    parts = dict(part.get("scores") or {})
    if parts:
        out["relevance"] = {"recorded": True, "parts": parts}
    elif "scores" in part:
        out["relevance"] = {
            "recorded": False,
            "note": ("the trace retained this record in its candidate list "
                     "but recorded no per-channel parts (expand traces record "
                     "none) — there is nothing honest to serve"),
        }
    else:
        cap = len(trace.candidates or ())
        out["relevance"] = {
            "recorded": False,
            "note": (f"not in the trace's bounded candidate list ({cap} "
                     "strongest retained) — per-channel parts were not kept "
                     "for this record; presence came from a reserved lane "
                     "(self/STM) or the record ranked below the bound"),
        }

    shelf: Dict[str, Any] = {"selected_count": len(trace.selected or ())}
    selected_ids = list(trace.selected or ())
    hit = next((s for s in selected_ids if s in ids), None)
    if hit is not None:
        shelf["position"] = selected_ids.index(hit) + 1  # shelf render order
    if "candidate_rank" in part:
        shelf["candidate_rank"] = part["candidate_rank"]
        shelf["candidate_cap"] = len(trace.candidates or ())
        shelf["rank_note"] = ("strongest-fused position in the trace's bounded "
                              "candidate list at recall time — not a replay of "
                              "the shelf fill (reserved self/STM lanes fill by "
                              "state, not rank)")
    out["shelf"] = shelf
    return out
