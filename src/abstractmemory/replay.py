"""The replay/observability stream (a2a 0005, schema v1).

One task: fold the journal's six record families into ONE envelope shape
serving both modes — replay is a bounded read; live is the same read that
doesn't stop (consumers poll `since_seq=cursor`; the gateway turns that
into push). Every item is a VERBATIM journal record (payload =
record.to_dict()) — the ledger IS the stream, never a second source of
truth, and never a payload export (enrichment carries digest-level
titles/kinds only; diary content is marked redacted for gateway audience
enforcement).

Determinism: same journal + same args → identical item sequence
(observed_at is stored at write time; until_seq=None anchors to the
high-water mark AT CALL TIME, so a stream started before later appends
never grows mid-iteration). Resumption: persist the last rendered seq and
pass it as since_seq — exact continuation, no gaps, no repeats. SEQ-GAP
HONESTY (0005 delta 3): under family filters or audience redaction,
consumers legitimately see gaps in seq — gaps are EXPECTED there and carry
no meaning; they are never data loss.

STREAM v1 IS FROZEN (0005 consumer review folded in): the envelope carries
turn-correlation keys (trace_id/turn_id/run_id, always present, null when
absent — pure lifting, no new data) and RESERVES family="host" for
gateway-authored transport markers (summon / prelude_rendered /
session_closed): never emitted by memory, accepted by the families filter
so consumers hard-coding the enum need no v2 bump. Display blocks of
FORMED records additionally carry "graph_id" (0005 observer delta,
additive — the join key between the graph-id and assertion-id namespaces;
diary-redacted blocks carry it too: identity is topology, not content).
BINDING envelopes of formed records also carry display.edges =
[{relation, target_graph_id}] when formation-time edges exist (0007 ask 2,
display-only additive per the frozen-v1 rules — the view draws "known"
links distinct from lit usage trails; diary-redacted blocks never carry
edges).
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional, Sequence

from .canonical_text import handle_digest, token_estimate
from .records import resolve_digest_assertion

__all__ = [
    "REPLAY_FAMILIES",
    "REPLAY_STREAM",
    "REPLAY_STREAM_VERSION",
    "RESERVED_FAMILIES",
    "export_replay",
]

REPLAY_STREAM = "abstractmemory.replay"
REPLAY_STREAM_VERSION = 1
REPLAY_FAMILIES = ("event", "binding", "closure", "trace", "snapshot", "valence")
# Reserved in stream v1 for gateway-authored transport markers; memory never
# emits it (see module docstring).
RESERVED_FAMILIES = frozenset({"host"})


def _lift_scope_owner(family: str, record: Any, journal: Any, store: Any,
                      memo: Optional["_ExportMemo"] = None) -> tuple:
    """Lift (scope, owner_id) for filter-without-parse (0005 §1): direct
    fields for events/bindings/valence; traces lift from their searched-
    scopes set (single pair → it; mixed → ""). TWO SPEC GAPS fixed
    minimally (flagged in 0005): snapshots and closures carry NO scope
    fields in their payloads — snapshots lift through their TRACE, closures
    through their ASSERTION (store lookup); ("", "") when unresolvable."""
    if family in ("event", "binding", "valence"):
        return record.scope, record.owner_id
    if family == "closure":
        a = (memo.resolve(record.assertion_id) if memo is not None
             else resolve_digest_assertion(store, record.assertion_id))
        return (a.scope, a.owner_id or "") if a is not None else ("", "")
    if family == "trace":
        pairs = {(str(s.get("scope") or ""), str(s.get("owner_id") or ""))
                 for s in (record.searched_scopes or ()) if isinstance(s, dict)}
        if len(pairs) == 1:
            return next(iter(pairs))
        return "", ""
    # snapshot: resolve through the trace it references.
    rows = journal.traces(trace_id=record.trace_id, limit=1)
    if rows:
        return _lift_scope_owner("trace", rows[0], journal, store, memo)
    return "", ""


def _lift_correlation(family: str, record: Any) -> tuple:
    """Lift (trace_id, turn_id, run_id) — 0005 delta 1, filter-without-parse
    for the viewer's beat grouping ("turn 7" = trace + snapshot + formation
    events + appraisals as one visual unit). Pure lifting, no new data;
    None when a record carries no correlation info. traces/snapshots → own
    trace_id; events/valence → trace_id field + provenance turn_id/run_id;
    bindings/closures → provenance keys when present."""
    provenance = getattr(record, "provenance", None)
    provenance = provenance if isinstance(provenance, dict) else {}

    def _key(name: str) -> Optional[str]:
        value = provenance.get(name)
        return str(value) if isinstance(value, str) and value.strip() else None

    if family in ("trace", "snapshot"):
        return record.trace_id or None, None, None
    if family in ("event", "valence"):
        return record.trace_id or None, _key("turn_id"), _key("run_id")
    # binding | closure: correlation rides provenance only.
    return _key("trace_id"), _key("turn_id"), _key("run_id")


def _display_block(assertion: Any, requested_id: str) -> Dict[str, Any]:
    attrs = assertion.attributes if isinstance(assertion.attributes, dict) else {}
    # graph_id (0005 observer delta, additive): a formed-graph row's SUBJECT
    # is a record graph id — digest rows (record_kind) AND edge rows
    # (record_edge, whose subject is the SOURCE record's graph id by
    # construction; co_selected hop pairs reference them) — the join key
    # between the two id namespaces (bindings carry graph ids; usage/traces
    # carry assertion row ids) that consumers otherwise reverse-engineer
    # from titles. Plain triples omit it (their subject is not a graph id —
    # no fabrication).
    formed = bool(attrs.get("record_kind") or attrs.get("record_edge"))
    if attrs.get("record_kind") == "diary":
        # Topology visible, content marked (0005 §5.1): the gateway serving
        # end enforces audience; memory marks the kind so it can. Topology =
        # existence + IDENTITY + connections — the opaque graph_id is node
        # identity, not content, so the diary lane can join too.
        return {"redacted": "diary", "graph_id": assertion.subject}
    digest = handle_digest(assertion)
    title = str(attrs.get("title") or "").strip() or f"{assertion.subject} {assertion.predicate}"
    block: Dict[str, Any] = {
        "record_id": requested_id,
        "kind": str(attrs.get("record_kind") or "memory"),
        "title": title,
        "token_estimate": token_estimate(digest),
    }
    if formed:
        block["graph_id"] = assertion.subject
    # Interaction-correlation key (item-14 render ask, additive like
    # graph_id): visit_id is the FIRST INSTANCE of the generic convention —
    # door-minted once, opaque, carried as DATA on each home's own records
    # so two perspectives of one shared moment correlate without the
    # streams ever merging (laurent c338: the name stays concrete, the
    # concept is generic). Diary-redacted blocks never reach here — a
    # private entry's correlation would leak the act's context, same rule
    # as formation edges.
    visit_id = attrs.get("visit_id")
    if isinstance(visit_id, str) and visit_id.strip():
        block["visit_id"] = visit_id.strip()
    return block


class _ExportMemo:
    """Per-export resolve/edges caches (entity's c2394 profiling: the N+1
    resolve_digest_assertion + per-binding edge query were ~45% of stream
    generation on a lived home). Records are IMMUTABLE and journal rows
    only ever reference records that already exist at their seq, so a
    per-export memo is exactly correct — and it additionally gives one
    export ONE consistent edge snapshot. Scoped to a single export_replay
    call (never module-global): size is bounded by the home's distinct
    record count, and a fresh export always sees the current store."""

    __slots__ = ("store", "resolved", "edges")

    def __init__(self, store: Any) -> None:
        self.store = store
        self.resolved: Dict[str, Any] = {}
        self.edges: Dict[str, Any] = {}

    def resolve(self, rid: str) -> Any:
        if rid in self.resolved:
            return self.resolved[rid]
        a = resolve_digest_assertion(self.store, rid)
        self.resolved[rid] = a
        return a

    def formation_edges(self, a: Any) -> Any:
        key = str(a.subject)
        if key in self.edges:
            return self.edges[key]
        from .store import TripleQuery  # local: keep module imports lean

        edges = [
            {"relation": e.predicate, "target_graph_id": e.object}
            for e in self.store.query(TripleQuery(subject=a.subject, scope=a.scope,
                                                  owner_id=a.owner_id or None, limit=0))
            if isinstance(e.attributes, dict) and e.attributes.get("record_edge")
        ]
        result = sorted(edges, key=lambda x: (x["relation"], x["target_graph_id"])) if edges else None
        self.edges[key] = result
        return result


def _enrich(family: str, record: Any, store: Any,
            memo: Optional["_ExportMemo"] = None) -> Optional[Dict[str, Any]]:
    """Optional display block (0005 §3) for record-bearing items, resolved
    from the store at export time. Absent when unresolvable — NEVER
    fabricated. Records are immutable, so enrichment keeps determinism
    (and the per-export memo keeps it CHEAP — see _ExportMemo)."""
    resolve = memo.resolve if memo is not None else (
        lambda rid: resolve_digest_assertion(store, rid))
    if family == "event":
        if record.pair_ids:  # co_selected: both pair members
            members = []
            for rid in record.pair_ids:
                a = resolve(rid)
                if a is not None:
                    members.append(_display_block(a, rid))
            return {"pair": members} if members else None
        rid = record.record_id
    elif family == "binding":
        rid = record.record_id
    elif family == "closure":
        rid = record.assertion_id
    elif family == "valence":
        rid = record.target_id  # free identity strings usually unresolvable
    else:
        return None  # traces/snapshots: payload already carries display truth
    if not rid:
        return None
    a = resolve(rid)
    if a is None:
        return None
    block = _display_block(a, rid)
    if family == "binding":
        # Display-only, additive (0007 ask 2): a formed record's binding
        # envelope carries its FORMATION-TIME edges so the view can draw
        # "known" links distinct from lit usage trails. Diary-redacted
        # blocks carry edges TOO (observer e-s 253 gap): the maintainer's
        # diary-connectivity ruling made written_amid act-frame, not
        # content — "uniformly (private included): the edge is act-frame,
        # the words stay in the book". An edge is relation + opaque target
        # graph id (node identity, the same justification as the block's
        # own graph_id); sealing it made diary connectivity invisible in
        # pixels while present at rest — the invisible-topology class.
        # Content fields stay sealed exactly as before.
        if memo is not None:
            edges = memo.formation_edges(a)
        else:
            from .store import TripleQuery  # local: keep module imports lean

            raw = [
                {"relation": e.predicate, "target_graph_id": e.object}
                for e in store.query(TripleQuery(subject=a.subject, scope=a.scope,
                                                 owner_id=a.owner_id or None, limit=0))
                if isinstance(e.attributes, dict) and e.attributes.get("record_edge")
            ]
            edges = sorted(raw, key=lambda x: (x["relation"], x["target_graph_id"])) if raw else None
        if edges:
            block["edges"] = edges
    return block


def export_replay(
    store: Any,
    journal: Any,
    *,
    scope: Optional[str] = None,
    owner_id: Optional[str] = None,
    since_seq: int = 0,
    until_seq: Optional[int] = None,
    families: Optional[Sequence[str]] = None,
    enrich: bool = True,
) -> Iterator[Dict[str, Any]]:
    """The 0005 stream: envelopes over journal records in strict seq order.
    since_seq exclusive; until_seq inclusive (None = high-water at call
    time); scope/owner filters match the LIFTED values; families defaults
    to all six (unknown names raise). enrich=False gives the pure ledger
    stream.

    EXECUTION CONTRACT (pinned after the 2026-07-12 gateway starvation
    incident — one abandoned since_seq=0 tail pinned the serving event
    loop ~40s): this is a SYNCHRONOUS, CPU-bound generator by design
    (SQLite reads + enrichment + dict assembly per envelope, no awaits).
    Async/HTTP consumers MUST iterate it OFF the event loop (worker
    thread / run_in_executor with chunked handoff) and SHOULD check
    client liveness between chunks. Poll loops MUST pass their cursor as
    since_seq — backends serve that as an indexed continuation (SQLite:
    range scans `seq > cursor`), so a cursored re-poll is cheap while a
    since_seq=0 re-walk replays the whole life every time."""
    wanted_families = tuple(families) if families is not None else REPLAY_FAMILIES
    # Reserved families are ACCEPTED (they yield nothing from memory — the
    # gateway interleaves them transport-side); unknown names still raise.
    unknown = [f for f in wanted_families
               if f not in REPLAY_FAMILIES and f not in RESERVED_FAMILIES]
    if unknown:
        raise ValueError(
            f"unknown replay families {unknown} "
            f"(valid: {list(REPLAY_FAMILIES)}; reserved: {sorted(RESERVED_FAMILIES)})"
        )
    family_set = frozenset(wanted_families)
    scope_f = str(scope or "").strip().lower() or None
    owner_f = str(owner_id or "").strip() or None
    hi = int(until_seq) if until_seq is not None else journal.current_seq()
    # Per-export memo (entity c2394: N+1 resolves were ~45% of generation
    # on a lived home) — one resolve/edge-query per distinct record per
    # export, exactly correct over immutable records (_ExportMemo doc).
    memo = _ExportMemo(store)

    for family, record in journal.replay_records(since_seq=int(since_seq), until_seq=hi):
        if family not in family_set:
            continue
        lifted_scope, lifted_owner = _lift_scope_owner(family, record, journal, store, memo)
        if scope_f is not None and lifted_scope != scope_f:
            continue
        if owner_f is not None and lifted_owner != owner_f:
            continue
        trace_id, turn_id, run_id = _lift_correlation(family, record)
        envelope: Dict[str, Any] = {
            "stream": REPLAY_STREAM,
            "stream_version": REPLAY_STREAM_VERSION,
            "seq": record.seq,
            "family": family,
            "observed_at": record.observed_at,
            "scope": lifted_scope,
            "owner_id": lifted_owner,
            "trace_id": trace_id,   # correlation keys (0005 delta 1):
            "turn_id": turn_id,     # always present, null when the record
            "run_id": run_id,       # carries no correlation info.
            "payload": record.to_dict(),  # verbatim: the ledger IS the stream
        }
        if enrich:
            display = _enrich(family, record, store, memo)
            if display is not None:
                envelope["display"] = display
        yield envelope
