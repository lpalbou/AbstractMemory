"""Sleep cadence: WHEN is a pass worth running (fork item 770).

Split from maintenance.py (600-line rule): the tending pass answers "what
needs tending", this module answers "is there material" — a deterministic
predicate over the journal's formation stream plus the standing
fragmentation signal. Scheduling itself (late-local-time, sleep windows)
stays HOST policy by the 0023 ruling: the host's clock decides WHEN to ask;
this only answers WHETHER the answer would be new.

BOUNDED BY A CURSOR (backlog 0058). The predicate is meant to be asked
often; it used to re-read the whole scope twice (the anchor's artifact scan
and `structural_report`) on every call: 3.5 s at 20k records. Its answer is
now folded from the store's change feed (`assertions_after`, append-only
rows in rowid order) into a per-(store, journal, scopes) `_CadenceFold`
that keeps exactly the facts the answer needs: each record's effective
title, the maintenance candidates, the component edges and the sleep
artifacts. A check reads only the rows written since the previous one
(O(new rows)); the duplicate-title and isolated counts are recomputed in
memory only when such a row arrived. The journal's formation bindings are
re-read only when `journal.current_seq()` moved (the journal API has no
"after seq" read; see backlog 0058 Report, remaining hot spots). The answer
is the one the full scan gives — `_maintenance_due_scan` keeps that
reference, and a store without a change feed (LanceDB) still uses it.
"""

from __future__ import annotations

import threading
import weakref
from bisect import bisect_right
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .consolidation import COMPONENT_RELATIONS, structural_report
from .store import TripleQuery
from .store_tuning import CADENCE_FEED_PAGE
from .text_tokens import title_key

__all__ = ["last_maintenance_seq", "maintenance_due"]


# -- the reference (full scan) ----------------------------------------------


def _last_maintenance_seq_scan(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
) -> int:
    artifact_ids: List[str] = []
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_kind") == "dream" or attrs.get("maintenance_candidate"):
                artifact_ids.append(a.subject)
    return _anchor_of(journal, artifact_ids)


def _anchor_of(journal: Any, artifact_ids: Any) -> int:
    high = 0
    for rid in sorted(set(artifact_ids)):
        for binding in journal.bindings(record_id=rid, fold=True):
            high = max(high, int(binding.seq))
    return high


def _new_formed(seqs_per_pair: Sequence[Sequence[int]], anchor: int) -> int:
    return sum(len(seqs) - bisect_right(seqs, anchor) for seqs in seqs_per_pair)


def _remember_seqs(journal: Any, scopes: Sequence[Tuple[str, str]]) -> List[List[int]]:
    return [sorted(int(b.seq) for b in journal.bindings(scope=scope, owner_id=owner, fold=False)
                   if b.source == "remember")
            for scope, owner in scopes]


def _maintenance_due_scan(
    store: Any, journal: Any, *,
    scopes: Sequence[Tuple[str, str]], since_seq: Optional[int],
    min_new_records: int, min_signal: int,
) -> Dict[str, Any]:
    """The reference answer: full scope scans (the pre-0058 code path)."""
    anchor = int(since_seq) if since_seq is not None else _last_maintenance_seq_scan(
        store, journal, scopes=scopes)
    new_formed = _new_formed(_remember_seqs(journal, scopes), anchor)
    base = structural_report(store, journal, scopes=scopes)
    return _answer(anchor, new_formed, len(base.get("duplicates", {})),
                   len(base.get("isolated", ())), min_new_records, min_signal)


def _answer(anchor: int, new_formed: int, duplicates: int, isolated: int,
            min_new_records: int, min_signal: int) -> Dict[str, Any]:
    signal = duplicates + isolated
    reasons: List[str] = []
    if new_formed >= int(min_new_records):
        reasons.append(f"{new_formed} new records since seq {anchor} (floor {int(min_new_records)})")
    if new_formed > 0 and signal >= int(min_signal):
        reasons.append(
            f"{new_formed} new record(s) with fragmentation signal {signal} >= {int(min_signal)} "
            f"({duplicates} duplicate-title group(s) + {isolated} isolated)")
    return {
        "due": bool(reasons), "reasons": reasons, "since_seq": anchor,
        "new_records": new_formed, "signal": signal,
        "duplicate_groups": duplicates, "isolated": isolated,
    }


# -- the cursor-bounded fold --------------------------------------------------


def _scan_order(store: Any) -> Optional[str]:
    """How `store.query(limit=0)` orders rows of equal `observed_at` (the
    structural report's "last row of a subject wins" depends on it), or None
    for a store without a change feed: the fold must reproduce the scan
    exactly, so it only serves stores whose order it knows."""
    from .in_memory_store import InMemoryTripleStore
    from .sqlite_store import SQLiteTripleStore

    if isinstance(store, SQLiteTripleStore):
        return "assertion_id"   # ORDER BY observed_at DESC, assertion_id DESC
    if isinstance(store, InMemoryTripleStore):
        return "insertion"      # stable sort by observed_at, reverse
    return None


class _CadenceFold:
    """The facts `maintenance_due` needs, folded from the change feed.

    Reproduces `structural_report(store, journal, scopes)`'s duplicate-title
    and isolated counts and `last_maintenance_seq`'s artifact set exactly:
    the report walks the scopes in order, each newest-first, and the LAST
    row it sees for a subject sets the record's title — so a subject's
    effective row is, in the last scope listing it, its oldest row (ties by
    the store's own order, `_scan_order`)."""

    def __init__(self, journal: Any, scopes: Sequence[Tuple[str, str]], order: str) -> None:
        self.journal_ref = weakref.ref(journal)
        self.scopes = list(scopes)
        self.order = order
        self.lock = threading.Lock()
        self.cursors = [0] * len(self.scopes)
        # subject -> {scope index: (order key, title key)} (the oldest
        # eligible row of that subject in that scope).
        self.titles: Dict[str, Dict[int, Tuple[Tuple[Any, ...], str]]] = {}
        self.candidates: Set[str] = set()
        self.edges: Set[Tuple[str, str]] = set()
        self.artifacts: Set[str] = set()
        self.signal: Optional[Tuple[int, int]] = None   # (duplicates, isolated); None = stale
        self.journal_seq: Optional[int] = None
        self.remember_seqs: List[List[int]] = []
        self.anchor: Optional[int] = None               # derived anchor; None = stale
        self.rows_read = 0                              # change-feed rows folded (tests)

    def catch_up(self, store: Any) -> None:
        for index, (scope, owner) in enumerate(self.scopes):
            while True:
                rows, cursor = store.assertions_after(
                    self.cursors[index], scope=scope, owner_id=owner or None,
                    limit=CADENCE_FEED_PAGE)
                self.cursors[index] = cursor
                for position, a in rows:
                    self._fold(index, position, a)
                if len(rows) < CADENCE_FEED_PAGE:
                    break

    def _fold(self, index: int, position: int, a: Any) -> None:
        self.rows_read += 1
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        # last_maintenance_seq's artifact rule (any row of the scope).
        if attrs.get("record_kind") == "dream" or attrs.get("maintenance_candidate"):
            if a.subject not in self.artifacts:
                self.artifacts.add(a.subject)
                self.anchor = None
        # structural_report's rules, in its order.
        if attrs.get("record_edge"):
            predicate = str(a.predicate or "").strip()
            if predicate in COMPONENT_RELATIONS and a.subject != a.object:
                pair = (a.subject, a.object) if a.subject <= a.object else (a.object, a.subject)
                if pair not in self.edges:
                    self.edges.add(pair)
                    self.signal = None
            return
        kind = attrs.get("record_kind")
        if not kind or kind in ("dream", "world_model") or attrs.get("bookkeeping"):
            return
        if attrs.get("maintenance_candidate") and a.subject not in self.candidates:
            self.candidates.add(a.subject)
            self.signal = None
        tie = (a.assertion_id or "") if self.order == "assertion_id" else -int(position)
        key = (a.observed_at or "", tie)
        per_scope = self.titles.setdefault(a.subject, {})
        held = per_scope.get(index)
        if held is None or key < held[0]:
            per_scope[index] = (key, title_key(str(attrs.get("title") or "").strip()))
            self.signal = None

    def structural_counts(self) -> Tuple[int, int]:
        """(duplicate-title groups, isolated records) of structural_report."""
        if self.signal is None:
            groups: Counter = Counter()
            for per_scope in self.titles.values():
                normalized = per_scope[max(per_scope)][1]
                if normalized:
                    groups[normalized] += 1
            duplicates = sum(1 for count in groups.values() if count > 1)
            linked: Set[str] = set()
            for left, right in self.edges:
                if (left in self.titles and right in self.titles
                        and left not in self.candidates and right not in self.candidates):
                    linked.add(left)
                    linked.add(right)
            self.signal = (duplicates, len(self.titles) - len(linked))
        return self.signal

    def sync_journal(self, journal: Any) -> None:
        seq = int(journal.current_seq())
        if seq != self.journal_seq:
            # Read the seq FIRST: a binding appended meanwhile is either in
            # this read or makes the next check re-read (never lost).
            self.remember_seqs = _remember_seqs(journal, self.scopes)
            self.journal_seq = seq
            self.anchor = None

    def derived_anchor(self, journal: Any) -> int:
        if self.anchor is None:
            self.anchor = _anchor_of(journal, self.artifacts)
        return self.anchor


_FOLDS: "weakref.WeakKeyDictionary[Any, Dict[Any, _CadenceFold]]" = weakref.WeakKeyDictionary()
_FOLDS_LOCK = threading.Lock()


def _fold_for(store: Any, journal: Any, scopes: Sequence[Tuple[str, str]]) -> Optional[_CadenceFold]:
    order = _scan_order(store)
    if order is None or not hasattr(store, "assertions_after"):
        return None
    pairs = [(str(scope), owner) for scope, owner in scopes]
    key = (id(journal), tuple(pairs))
    with _FOLDS_LOCK:
        per_store = _FOLDS.setdefault(store, {})
        fold = per_store.get(key)
        if fold is None or fold.journal_ref() is not journal:
            fold = _CadenceFold(journal, pairs, order)
            per_store[key] = fold
    return fold


def last_maintenance_seq(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
) -> int:
    """Journal seq of the newest sleep artifact's formation (dream OR
    maintenance candidate) — the default "since when" anchor for the cadence
    predicate. 0 = this store has never had a sleep pass. Cursor-bounded
    (see the module docstring)."""
    fold = _fold_for(store, journal, scopes)
    if fold is None:
        return _last_maintenance_seq_scan(store, journal, scopes=scopes)
    with fold.lock:
        fold.catch_up(store)
        fold.sync_journal(journal)
        return fold.derived_anchor(journal)


def maintenance_due(
    store: Any, journal: Any, *,
    scopes: Sequence[Tuple[str, str]], since_seq: Optional[int] = None,
    min_new_records: int = 12, min_signal: int = 3,
) -> Dict[str, Any]:
    """Deterministic cadence predicate (fork 770: "enough new nodes +
    fragmentation"; late-local-time stays the HOST's clock). Due when enough
    NEW records formed since the last pass, or when SOME new material exists
    and the standing fragmentation signal (duplicate-title groups + isolated
    records) clears its floor. A store with zero new formations is never due —
    the pass would reproduce its own prior output byte-for-byte.

    Bounded by a cursor (0058): a check reads the store rows written since
    the previous check of the same (store, journal, scopes), and re-reads the
    journal's formation bindings only when the journal moved. Same answer as
    the full scan."""
    fold = _fold_for(store, journal, scopes)
    if fold is None:
        return _maintenance_due_scan(
            store, journal, scopes=scopes, since_seq=since_seq,
            min_new_records=min_new_records, min_signal=min_signal)
    with fold.lock:
        fold.catch_up(store)
        fold.sync_journal(journal)
        anchor = int(since_seq) if since_seq is not None else fold.derived_anchor(journal)
        duplicates, isolated = fold.structural_counts()
        new_formed = _new_formed(fold.remember_seqs, anchor)
    return _answer(anchor, new_formed, duplicates, isolated, min_new_records, min_signal)
