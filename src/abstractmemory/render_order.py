"""Stable render order for shelf handles (0049 — prefix-cache reuse).

The MEMORIES region is rendered in RANK order today, so rank churn between
consecutive turns breaks the longest-common-prefix and the provider's
prefix/delta cache re-prefills the whole region even when the record SET
barely moved (core's bloc-seam adversary §6, research/cache-composability
v2). This module is the engine half of the fix: a PURE presentation
helper the driver may elect — render the shelf in a STABLE identity order
with rank carried as an annotation instead of as position.

THE KEY IS FORMATION ORDER (observed_at, record_id), deliberately not the
id-alphabetical order the backlog item sketched: alphabetical identity
order lets a NEW record sort into the MIDDLE of the region (its id lands
between two existing ids), breaking the byte prefix at the insertion
point. Under formation order, records that persist across turns hold
their relative positions FOREVER and new records — newer by definition —
append at the TAIL, which is exactly the longest-common-prefix-maximizing
behavior, with zero cross-turn state.

RENDER CONTRACT ("stable order, rank annotated") — an OPTION the driver
elects, never engine policy:
- the driver renders lines in the returned order;
- each line carries its RANK annotation (e.g. "[r3]") so the model still
  sees importance — the annotation is MANDATORY under this contract
  (hiding rank would trade model judgment for cache bytes; refused);
- selection is untouched: same handles in, same handles out, reordered.
  Presentation may diversify; selection never changes (the ruled lane).

Prefix honesty: when a leading record DROPS off the shelf, the prefix
breaks at that point regardless of ordering — the set changed there.
Stable order maximizes reuse among the records that survive; it cannot
(and must not) pretend the shelf did not change.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Tuple

__all__ = ["stable_render_order"]


def _field(handle: Any, name: str) -> Any:
    """Handles arrive as MemoryHandle objects or their to_dict() dicts —
    the same duck-typed read as origin_diversity."""
    if isinstance(handle, Mapping):
        return handle.get(name)
    return getattr(handle, name, None)


def _formation_key(handle: Any) -> Tuple[str, str]:
    """(observed_at, record_id) — both immutable at formation. A handle
    without observed_at (foreign dict shapes) sorts by record_id alone,
    ahead of dated peers only through the empty string — deterministic,
    and honest about what is known."""
    prov = _field(handle, "provenance")
    prov = prov if isinstance(prov, Mapping) else {}
    observed_at = str(prov.get("observed_at") or "")
    record_id = str(_field(handle, "record_id") or "")
    return (observed_at, record_id)


def stable_render_order(handles: Any) -> List[Tuple[Any, int]]:
    """Reorder ranked shelf handles into the stable render order.

    Input: handles in RANK order (the shelf's selection output — position
    IS rank, as reconstruct() returns them). Output: (handle, rank) pairs
    in formation order, rank being the 1-based position in the INPUT —
    the annotation the driver must render so importance stays visible.

    Pure read: no mutation, no engine state, no selection change — the
    returned handles are the given objects, every one of them, exactly
    once. Deterministic for identical inputs.
    """
    ranked = [(handle, rank) for rank, handle in enumerate(handles or (), start=1)]
    ranked.sort(key=lambda pair: _formation_key(pair[0]))
    return ranked
