"""InMemoryJournal — volatile reference backend for the MemoryJournal protocol.

Design sources: docs/backlog/proposed/memory_system_v1/0017 (journal + scope
bindings) and 0013 (concurrency contract). Record shapes and the protocol are
frozen in `journal.py`; this module only implements storage semantics.

Role: tests, dev loops, and hosts that want the memory-system layer without a
durable file. It doubles as the REFERENCE implementation: the enrichment/
filter helpers below define query semantics ONCE and are imported by
`journal_sqlite` so both backends resolve identically (cross-backend parity,
backlog 0011); the fully backend-agnostic boundary rules (ids, observed_at
canonicalization, strict-JSON sanitization) moved to `journal_common.py`
when the valence family landed (600-line rule).

Concurrency (0013 contract): one `threading.RLock` guards every read and
write. The seq counter and record lists mutate only under the lock, so `seq`
is a strict total order per journal instance across ALL record families
(events, bindings, closures, traces, snapshots — one axis, starting at 1).

Volatility: everything — including the seq axis the runtime persists for
`as_of` replay — dies with the process. Construction emits a `#FALLBACK`
warning so a host cannot mistake this for durable memory.
"""

from __future__ import annotations

import copy
import threading
import warnings
from dataclasses import replace
from typing import Any, List, Optional, Sequence

from .journal import (
    ALL_EVENT_KINDS,
    ClosureRecord,
    MemoryEvent,
    ReconstructionTrace,
    ScopeBinding,
    ValenceEvent,
    fold_bindings,
)
from .journal_common import (
    _enrich_binding,
    _enrich_closure,
    _enrich_event,
    _enrich_snapshot,
    _enrich_trace,
    _enrich_valence,
    canonical_observed_at as _canonical_observed_at,
    new_id as _new_id,
    normalize_iso_ts as _normalize_iso_ts,
    sanitize_batch as _sanitize_batch,
)
from .seam import ActiveMemorySnapshot

# ---------------------------------------------------------------------------
# Shared journal semantics (imported by journal_sqlite; keep backend-agnostic)
# ---------------------------------------------------------------------------


def _normalize_kinds_filter(kinds: Optional[Sequence[str]]) -> Optional[frozenset]:
    """Validate and normalize an events() kinds filter.

    Unknown kinds raise instead of silently matching nothing: the kind
    vocabulary is a frozen contract (journal.py / 0018) and no stored event
    can carry an unknown kind, so an unknown filter value is always a caller
    bug. An empty filter collapses to None = "no filter" (package convention,
    cf. TripleQuery.assertion_ids).
    """
    if kinds is None:
        return None
    if isinstance(kinds, str):
        # A bare string is iterable char-by-char; treat it as one kind instead
        # of producing a baffling "unknown kinds ['s','e',...]" error.
        kinds = (kinds,)
    requested = {str(k or "").strip().lower() for k in kinds}
    requested.discard("")
    if not requested:
        return None
    unknown = requested - ALL_EVENT_KINDS
    if unknown:
        raise ValueError(
            f"Unknown memory event kinds in filter: {sorted(unknown)} (known: {sorted(ALL_EVENT_KINDS)})"
        )
    return frozenset(requested)


def _require_scope(scope: Any) -> str:
    # events() makes scope a required kwarg; an empty scope can never match a
    # stored event (MemoryEvent enforces non-empty scope), so a silent [] here
    # would only hide caller bugs.
    normalized = str(scope or "").strip().lower()
    if not normalized:
        raise ValueError("events() requires a non-empty scope")
    return normalized


def _effective_limit(limit: Any, default: int) -> Optional[int]:
    """limit <= 0 means unlimited (package convention, cf. TripleQuery.limit)."""
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = int(default)
    return None if n <= 0 else n


def _require_instance(value: Any, expected: type, where: str) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{where} expects {expected.__name__} instances, got {type(value).__name__}")


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------


class InMemoryJournal:
    """Volatile, thread-safe MemoryJournal backend (lists + dicts + RLock).

    Reads and appends both pass through `copy.deepcopy` at the boundary so a
    caller mutating a returned record's `provenance` dict can never corrupt
    journal state (mirrors the triple stores' "never alias internals" rule).

    Write-side idempotency (a2a 0001/011 ask 3): caller-SUPPLIED ids are
    idempotency keys — re-appending an existing event/binding/closure/
    snapshot/trace id is a no-op returning the original stored record
    (original seq; selected-count untouched). Journal-assigned ids never
    conflict. Same observable semantics as SQLiteJournal's UNIQUE-indexed
    dedup.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._seq = 0  # last assigned seq; first record gets 1
        self._events: List[MemoryEvent] = []
        self._bindings: List[ScopeBinding] = []
        self._closures: List[ClosureRecord] = []
        self._traces: List[ReconstructionTrace] = []
        self._snapshots: List[ActiveMemorySnapshot] = []
        self._selected_counts: dict[str, int] = {}
        # Write-side idempotency indexes (a2a 0001/011 ask 3): id -> stored
        # record, one per family with supplied-id dedup (traces excluded —
        # see SQLiteJournal module docstring; the semantics mirror its UNIQUE
        # indexes). Every stored record is indexed (assigned ids too), so any
        # later append carrying an existing id is a no-op returning the
        # original — payloads are NOT compared, because replays legitimately
        # differ in wall-clock fields (observed_at); the id is the identity.
        self._events_by_id: dict[str, MemoryEvent] = {}
        self._bindings_by_id: dict[str, ScopeBinding] = {}
        self._closures_by_id: dict[str, ClosureRecord] = {}
        self._snapshots_by_id: dict[str, ActiveMemorySnapshot] = {}
        self._traces_by_id: dict[str, ReconstructionTrace] = {}
        self._valence: List[ValenceEvent] = []
        self._valence_by_id: dict[str, ValenceEvent] = {}
        # GLOBAL pair access counts (maintainer's access-count model): like
        # _selected_counts for records, cumulative co_selected count per
        # canonical pair — never decays, rebuildable from events.
        self._pair_counts: dict[tuple, int] = {}
        # Volatility must be loud: as_of replay anchors (seq) and the whole
        # attention substrate vanish on process exit. Display is deduped per
        # call site by the standard warnings filter ("once per process").
        warnings.warn(
            "#FALLBACK: InMemoryJournal is volatile — journal events, bindings, closures, "
            "traces, snapshots and the seq axis are lost on process exit (as_of replay will "
            "not survive a restart). Use SQLiteJournal for durable memory.",
            RuntimeWarning,
            stacklevel=2,
        )

    # -- events ---------------------------------------------------------

    def append_events(self, events: Sequence[MemoryEvent]) -> List[MemoryEvent]:
        items = list(events or ())
        for e in items:
            _require_instance(e, MemoryEvent, "append_events")
        if not items:
            return []
        items = _sanitize_batch(items)  # strict-JSON payload boundary (parity with SQLite)
        with self._lock:
            out: List[MemoryEvent] = []
            for e in items:
                supplied = str(e.event_id or "").strip()
                if supplied and supplied in self._events_by_id:
                    # Replay no-op (0001/011): return the ORIGINAL stored
                    # event with its original seq; no new record, and the
                    # selected-count increment is skipped with it. In-batch
                    # duplicate ids resolve to the first occurrence because
                    # the index is updated inside this same loop.
                    out.append(copy.deepcopy(self._events_by_id[supplied]))
                    continue
                self._seq += 1
                stored = _enrich_event(e, self._seq)
                self._events.append(stored)
                self._events_by_id[stored.event_id] = stored
                if stored.kind == "selected":
                    # Denormalized use counter (0017/0018): ONLY genuine
                    # selected-use advances it; audit kinds are inert.
                    self._selected_counts[stored.record_id] = (
                        self._selected_counts.get(stored.record_id, 0) + 1
                    )
                elif stored.kind == "co_selected" and stored.pair_ids:
                    self._pair_counts[tuple(stored.pair_ids)] = (
                        self._pair_counts.get(tuple(stored.pair_ids), 0) + 1
                    )
                out.append(copy.deepcopy(stored))
            return out

    def events(
        self,
        *,
        scope: str,
        owner_id: str,
        record_id: Optional[str] = None,
        kinds: Optional[Sequence[str]] = None,
        since_seq: Optional[int] = None,
        until_seq: Optional[int] = None,
        limit: int = 512,
    ) -> List[MemoryEvent]:
        scope_n = _require_scope(scope)
        owner_n = str(owner_id or "").strip()
        # Strict equality on record_id (matches the SQLite index contract):
        # co_selected pair events carry record_id=None and are read via
        # scope-level or kinds=["co_selected"] queries, not per-record ones.
        rid = record_id.strip() if isinstance(record_id, str) and record_id.strip() else None
        kind_filter = _normalize_kinds_filter(kinds)
        lo = int(since_seq) if since_seq is not None else None
        hi = int(until_seq) if until_seq is not None else None  # both bounds inclusive
        max_n = _effective_limit(limit, 512)
        with self._lock:
            out: List[MemoryEvent] = []
            for e in reversed(self._events):  # stored seq-ascending -> newest first
                if e.scope != scope_n or e.owner_id != owner_n:
                    continue
                if rid is not None and e.record_id != rid:
                    continue
                if kind_filter is not None and e.kind not in kind_filter:
                    continue
                if lo is not None and e.seq < lo:
                    continue
                if hi is not None and e.seq > hi:
                    continue
                out.append(copy.deepcopy(e))
                if max_n is not None and len(out) >= max_n:
                    break
            return out

    # -- bindings ---------------------------------------------------------

    def append_binding(self, binding: ScopeBinding) -> ScopeBinding:
        _require_instance(binding, ScopeBinding, "append_binding")
        [binding] = _sanitize_batch([binding])
        supplied = str(binding.binding_id or "").strip()
        with self._lock:
            if supplied and supplied in self._bindings_by_id:
                return copy.deepcopy(self._bindings_by_id[supplied])  # replay no-op
            self._seq += 1
            stored = _enrich_binding(binding, self._seq)
            self._bindings.append(stored)
            self._bindings_by_id[stored.binding_id] = stored
            return copy.deepcopy(stored)

    def bindings(
        self,
        *,
        record_id: Optional[str] = None,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
        fold: bool = True,
        until_seq: Optional[int] = None,
    ) -> List[ScopeBinding]:
        # None = no filter; explicit "" is a legitimate exact-match value
        # (ScopeBinding does not forbid empty owner_id).
        rid = str(record_id).strip() if record_id is not None else None
        scope_n = str(scope).strip().lower() if scope is not None else None
        owner_n = str(owner_id).strip() if owner_id is not None else None
        hi = int(until_seq) if until_seq is not None else None
        with self._lock:
            matches = [
                b
                for b in self._bindings  # seq-ascending: chronological audit order
                if (rid is None or b.record_id == rid)
                and (scope_n is None or b.scope == scope_n)
                and (owner_n is None or b.owner_id == owner_n)
                and (hi is None or b.seq <= hi)
            ]
            selected = fold_bindings(matches) if fold else matches
            return [copy.deepcopy(b) for b in selected]

    # -- closures ---------------------------------------------------------

    def append_closure(self, closure: ClosureRecord) -> ClosureRecord:
        _require_instance(closure, ClosureRecord, "append_closure")
        [closure] = _sanitize_batch([closure])
        supplied = str(closure.closure_id or "").strip()
        with self._lock:
            if supplied and supplied in self._closures_by_id:
                return copy.deepcopy(self._closures_by_id[supplied])  # replay no-op
            self._seq += 1
            stored = _enrich_closure(closure, self._seq)
            self._closures.append(stored)
            self._closures_by_id[stored.closure_id] = stored
            return copy.deepcopy(stored)

    def closures(
        self,
        *,
        assertion_id: Optional[str] = None,
        until_seq: Optional[int] = None,
        limit: int = 512,
    ) -> List[ClosureRecord]:
        aid = str(assertion_id).strip() if assertion_id is not None else None
        hi = int(until_seq) if until_seq is not None else None
        max_n = _effective_limit(limit, 512)
        with self._lock:
            out: List[ClosureRecord] = []
            for c in reversed(self._closures):  # newest first, like events
                if aid is not None and c.assertion_id != aid:
                    continue
                if hi is not None and c.seq > hi:
                    continue
                out.append(copy.deepcopy(c))
                if max_n is not None and len(out) >= max_n:
                    break
            return out

    # -- traces / snapshots ------------------------------------------------

    def append_trace(self, trace: ReconstructionTrace) -> ReconstructionTrace:
        _require_instance(trace, ReconstructionTrace, "append_trace")
        [trace] = _sanitize_batch([trace])
        supplied = str(trace.trace_id or "").strip()
        with self._lock:
            if supplied and supplied in self._traces_by_id:
                # Replay no-op (caller-supplied trace ids, a2a 0002 follow-up):
                # the FIRST journaled trace wins; re-calls never rewrite it.
                return copy.deepcopy(self._traces_by_id[supplied])
            self._seq += 1
            stored = _enrich_trace(trace, self._seq)
            self._traces.append(stored)
            self._traces_by_id[stored.trace_id] = stored
            return copy.deepcopy(stored)

    def traces(
        self, *, trace_id: Optional[str] = None, limit: int = 100,
        until_seq: Optional[int] = None,
    ) -> List[ReconstructionTrace]:
        # Mirrors snapshots(): newest first, optional exact trace_id filter,
        # optional until_seq anchor (situate() groundwork, seam v1.2).
        tid = str(trace_id).strip() if trace_id is not None else None
        max_n = _effective_limit(limit, 100)
        with self._lock:
            out: List[ReconstructionTrace] = []
            for t in reversed(self._traces):
                if tid is not None and t.trace_id != tid:
                    continue
                if until_seq is not None and t.seq > int(until_seq):
                    continue
                out.append(copy.deepcopy(t))
                if max_n is not None and len(out) >= max_n:
                    break
            return out

    def append_snapshot(self, snapshot: ActiveMemorySnapshot) -> ActiveMemorySnapshot:
        # The protocol types this Any (journal.py avoids the seam import), but
        # accepting arbitrary objects would break enrichment and reads —
        # enforce the documented concrete type.
        _require_instance(snapshot, ActiveMemorySnapshot, "append_snapshot")
        [snapshot] = _sanitize_batch([snapshot])
        supplied = str(snapshot.snapshot_id or "").strip()
        with self._lock:
            if supplied and supplied in self._snapshots_by_id:
                return copy.deepcopy(self._snapshots_by_id[supplied])  # replay no-op
            self._seq += 1
            stored = _enrich_snapshot(snapshot, self._seq)
            self._snapshots.append(stored)
            self._snapshots_by_id[stored.snapshot_id] = stored
            return copy.deepcopy(stored)

    def snapshots(
        self, *, trace_id: Optional[str] = None, limit: int = 100,
        until_seq: Optional[int] = None,
    ) -> List[ActiveMemorySnapshot]:
        tid = str(trace_id).strip() if trace_id is not None else None
        max_n = _effective_limit(limit, 100)
        with self._lock:
            out: List[ActiveMemorySnapshot] = []
            for s in reversed(self._snapshots):
                if tid is not None and s.trace_id != tid:
                    continue
                if until_seq is not None and s.seq > int(until_seq):
                    continue
                out.append(copy.deepcopy(s))
                if max_n is not None and len(out) >= max_n:
                    break
            return out

    # -- valence (identity wave; orthogonal to attention by contract) --------

    def append_valence(self, events: Sequence[ValenceEvent]) -> List[ValenceEvent]:
        items = list(events or ())
        for e in items:
            _require_instance(e, ValenceEvent, "append_valence")
        if not items:
            return []
        items = _sanitize_batch(items)
        with self._lock:
            out: List[ValenceEvent] = []
            for e in items:
                supplied = str(e.event_id or "").strip()
                if supplied and supplied in self._valence_by_id:
                    out.append(copy.deepcopy(self._valence_by_id[supplied]))  # replay no-op
                    continue
                self._seq += 1
                stored = _enrich_valence(e, self._seq)
                self._valence.append(stored)
                self._valence_by_id[stored.event_id] = stored
                out.append(copy.deepcopy(stored))
            return out

    def valence_events(
        self, *, scope: str, owner_id: str, target_id: Optional[str] = None,
        since_seq: Optional[int] = None, until_seq: Optional[int] = None,
        limit: int = 512,
    ) -> List[ValenceEvent]:
        scope_n = _require_scope(scope)
        owner_n = str(owner_id or "").strip()
        tid = target_id.strip() if isinstance(target_id, str) and target_id.strip() else None
        lo = int(since_seq) if since_seq is not None else None
        hi = int(until_seq) if until_seq is not None else None  # both bounds inclusive
        max_n = _effective_limit(limit, 512)
        with self._lock:
            out: List[ValenceEvent] = []
            for e in reversed(self._valence):  # newest first (parity with events())
                if e.scope != scope_n or e.owner_id != owner_n:
                    continue
                if tid is not None and e.target_id != tid:
                    continue
                if lo is not None and e.seq < lo:
                    continue
                if hi is not None and e.seq > hi:
                    continue
                out.append(copy.deepcopy(e))
                if max_n is not None and len(out) >= max_n:
                    break
            return out

    # -- replay stream (a2a 0005) --------------------------------------------

    def replay_records(self, *, since_seq: int = 0, until_seq: Optional[int] = None):
        """(family, record) across all six families in strict seq order.
        Materialized under the lock (collect + sort — journals are cheap to
        scan at current scale per the 0005 spec; a streaming k-way merge is
        a later optimization, not a semantic change), records deep-copied
        at the boundary like every other read."""
        lo = int(since_seq)
        with self._lock:
            hi = int(until_seq) if until_seq is not None else self._seq
            merged = [
                (r.seq, family, r)
                for family, records in (
                    ("event", self._events), ("binding", self._bindings),
                    ("closure", self._closures), ("trace", self._traces),
                    ("snapshot", self._snapshots), ("valence", self._valence),
                )
                for r in records
                if lo < r.seq <= hi
            ]
        merged.sort(key=lambda item: item[0])
        for _seq, family, record in merged:
            yield family, copy.deepcopy(record)

    # -- counters / axis ----------------------------------------------------

    def selected_count(self, record_id: str, *, until_seq: Optional[int] = None) -> int:
        """THE GLOBAL access count (maintainer's model): cumulative selected-
        use over the journal's whole life — never decays, only increases.
        The temporal counterpart is the activation fold (attention.py).
        until_seq anchors the count for as_of replay (fast path: the
        denormalized counter serves the unanchored read)."""
        rid = str(record_id or "").strip()
        with self._lock:
            if until_seq is None:
                return int(self._selected_counts.get(rid, 0))
            hi = int(until_seq)
            return sum(1 for e in self._events
                       if e.kind == "selected" and e.record_id == rid and e.seq <= hi)

    def pair_selected_count(self, pair: tuple, *, until_seq: Optional[int] = None) -> int:
        """GLOBAL access count for one EDGE (canonical pair): cumulative
        co_selected trail deposits — never decays. Order-insensitive."""
        a, b = (str(pair[0] or "").strip(), str(pair[1] or "").strip())
        key = tuple(sorted((a, b)))
        with self._lock:
            if until_seq is None:
                return int(self._pair_counts.get(key, 0))
            hi = int(until_seq)
            return sum(1 for e in self._events
                       if e.kind == "co_selected" and e.pair_ids == key and e.seq <= hi)

    def seq_at(self, iso_ts: str) -> int:
        ts = _normalize_iso_ts(iso_ts)
        best = 0
        with self._lock:
            # Snapshots are deliberately excluded: seq_at anchors scoring/fold
            # state (events/bindings/closures/traces); snapshots are pure
            # observability mirrors that never affect scores or folds.
            for records in (self._events, self._bindings, self._closures, self._traces):
                for r in records:
                    if r.observed_at <= ts and r.seq > best:
                        best = r.seq
        return best

    def current_seq(self) -> int:
        with self._lock:
            return int(self._seq)

    def close(self) -> None:
        # Nothing to release; data intentionally survives close() the same way
        # InMemoryTripleStore.close() behaves (volatile either way).
        return None
