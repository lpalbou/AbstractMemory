"""Sleep cadence: WHEN is a pass worth running (fork item 770).

Split from maintenance.py (600-line rule): the tending pass answers "what
needs tending", this module answers "is there material" — a deterministic
predicate over the journal's formation stream plus the standing
fragmentation signal. Scheduling itself (late-local-time, sleep windows)
stays HOST policy by the 0023 ruling: the host's clock decides WHEN to ask;
this only answers WHETHER the answer would be new.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .consolidation import structural_report
from .store import TripleQuery

__all__ = ["last_maintenance_seq", "maintenance_due"]


def last_maintenance_seq(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
) -> int:
    """Journal seq of the newest sleep artifact's formation (dream OR
    maintenance candidate) — the default "since when" anchor for the cadence
    predicate. 0 = this store has never had a sleep pass."""
    artifact_ids: List[str] = []
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_kind") == "dream" or attrs.get("maintenance_candidate"):
                artifact_ids.append(a.subject)
    high = 0
    for rid in sorted(set(artifact_ids)):
        for binding in journal.bindings(record_id=rid, fold=True):
            high = max(high, int(binding.seq))
    return high


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
    the pass would reproduce its own prior output byte-for-byte."""
    anchor = int(since_seq) if since_seq is not None else last_maintenance_seq(
        store, journal, scopes=scopes)
    new_formed = 0
    for scope, owner in scopes:
        for binding in journal.bindings(scope=scope, owner_id=owner, fold=False):
            if int(binding.seq) > anchor and binding.source == "remember":
                new_formed += 1
    base = structural_report(store, journal, scopes=scopes)
    duplicates = len(base.get("duplicates", {}))
    isolated = len(base.get("isolated", ()))
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
