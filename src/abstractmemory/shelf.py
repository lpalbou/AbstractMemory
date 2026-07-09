"""Shelf assembly: candidate cells, membership, ordering, handle building.

One task (split out of reconstruct.py to honor the <600-lines-per-file rule
when the hostile-audit fix wave landed): everything between "a scored
candidate universe exists" and "an ordered shelf of handles exists".
reconstruct.py keeps pipeline orchestration (channels → spreading → views →
trace); this module owns the 0019/0020 selection semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple

from .canonical_text import display_title as _display_title
from .canonical_text import token_estimate as _token_estimate
from .channels import CHANNEL_ORDER
from .models import TripleAssertion
from .records import ReconstructConfig
from .seam import MemoryHandle

__all__ = ["Candidate", "build_handle", "order_members"]

_DEFAULT_BINDING = "indexed+inactive"


@dataclass
class Candidate:
    """Internal accumulation cell for one record across pipeline stages."""

    assertion: TripleAssertion
    record_id: str
    relevance: Dict[str, float] = field(default_factory=dict)
    details: Dict[str, List[str]] = field(default_factory=dict)
    sources: set = field(default_factory=set)  # recent|exact|keyword|vector|spread
    spread: float = 0.0

    @property
    def fused(self) -> float:
        # 0019 fusion v1: max-channel score. RRF is deferred until more than
        # one RANKED channel of comparable scale exists; with all channels
        # normalized 0..1, max is the honest parameter-free combiner.
        return max(self.relevance.values(), default=0.0)

    @property
    def channel_matched(self) -> bool:
        return bool(self.relevance)


def order_members(
    member_ids: Sequence[str],
    universe: Mapping[str, Candidate],
    base_of: Callable[[str], float],
    boost: Callable[[float], float],
    config: ReconstructConfig,
) -> List[str]:
    """0020 ordering, hardened by the hostile audit (f4/f5) and corrected by
    the realistic-data findings: CHANNEL-MATCHED candidates order before
    unmatched ones — PRIMARY key, any channel — so a zero-relevance record
    (however hot its activation or lofty its kind) can never outrank, and
    under a tight token budget never evict, a record the cue actually
    matched. Among matched peers: exact hits first, then fused + capped
    activation boost, then KIND RANK strictly as a tie-break (0020's "at
    equal relevance" — under realistic embedders everything channel-matches,
    and kind-above-fused let stale decisions outrank the direct answer),
    then observed_at desc, record_id asc. Spread deliberately does NOT
    reorder here — it is activation decomposition + working-set membership
    signal, not relevance. Stable sorts are applied lowest-priority first."""
    ids = sorted(member_ids)
    ids.sort(key=lambda rid: universe[rid].assertion.observed_at or "", reverse=True)
    ids.sort(key=lambda rid: config.rank_of(config.kind_of(universe[rid].assertion)))
    # Scale conversion: boost() returns fork-scale values (0..max_boost against a
    # 1000-point direct hit; 0018), while fused relevance here is normalized 0..1.
    # Dividing by 1000 preserves the fork's ratio, so activation reorders
    # near-ties among peers and never overturns relevance (a2a 004 contract 3).
    ids.sort(key=lambda rid: universe[rid].fused + float(boost(base_of(rid))) / 1000.0, reverse=True)
    ids.sort(key=lambda rid: 0 if "exact" in universe[rid].relevance else 1)
    ids.sort(key=lambda rid: 0 if universe[rid].channel_matched else 1)
    return ids


def build_handle(
    cand: Candidate,
    base_level: float,
    spread_cues: Sequence[str],
    contributions: Sequence[str],
    digest: str,
    binding: str,
    config: ReconstructConfig,
    global_count: int = 0,
    *,
    admission: str = "stimulus",
) -> MemoryHandle:
    a = cand.assertion
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    cues: List[str] = []
    for channel in CHANNEL_ORDER:
        cues.extend(cand.details.get(channel, ()))
    cues.extend(spread_cues)
    cues.extend(str(c) for c in contributions)
    if not cues:
        # Seam contract: cues never empty for selected handles. An STM
        # admission is its own honest reason; recency is the fallback.
        if admission == "stm":
            cues.append(f"stm: trail-hot (base_level {float(base_level):.1f})")
        else:
            cues.append(f"recent: scope {a.scope}/{a.owner_id or ''}")

    # v1 record enrichment (records.py): stored title beats the "s p o"
    # preview (same 120-char bound); payload_ref makes the raw tier reachable.
    stored_title = attrs.get("title")
    if isinstance(stored_title, str) and stored_title.strip():
        title = stored_title.strip()
        if len(title) > 120:
            title = title[:119] + "…"  #[WARNING:TRUNCATION] title preview bounded at 120 chars (digest carries the full text)
    else:
        title = _display_title(a)
    has_raw = isinstance(attrs.get("payload_ref"), str) and attrs["payload_ref"].strip()
    payload_tiers = ("digest", "raw") if has_raw else ("digest",)

    provenance: Dict[str, Any] = {"observed_at": a.observed_at}
    if a.confidence is not None:
        provenance["confidence"] = a.confidence
    if a.provenance:
        provenance["assertion_provenance"] = dict(a.provenance)
    if isinstance(attrs.get("record_kind"), str):
        # handle.record_id is the digest ASSERTION id (retrieval/commit key);
        # the subject is the GRAPH id remember_many returned (host correlation).
        provenance["record_id"] = a.subject
    # Topic surfacing (0002/001 q3): promote a string "topic" attribute for
    # the focus-coherence metric (no coercion).
    topic = attrs.get("topic")
    if isinstance(topic, str) and topic.strip():
        provenance["topic"] = topic.strip()
    # GLOBAL access count (maintainer's two-count model): lifetime selected
    # count, never decays — display truth beside the TEMPORAL activation
    # decomposition; never consulted by ordering or admission.
    provenance["global_count"] = int(global_count)
    # Diary progressive disclosure: the projection's pointer into the
    # runtime's hash-chained book, so a host can fetch the verbatim entry.
    entry_id = attrs.get("entry_id")
    if isinstance(entry_id, str) and entry_id.strip():
        provenance["entry_id"] = entry_id.strip()

    spread = float(cand.spread)
    return MemoryHandle(
        record_id=cand.record_id,
        kind=config.kind_of(a),  # attributes.record_kind for formed records; "memory" baseline
        title=title,
        digest=digest,
        token_estimate=_token_estimate(digest),
        relevance=dict(cand.relevance),
        activation={"base_level": float(base_level), "spread": spread, "total": float(base_level) + spread},
        cues=tuple(cues),
        binding=binding,  # facade-folded "{search_state}+{prompt_state}" (0017); default for unbound records
        scope=a.scope,
        owner_id=a.owner_id or "",
        provenance=provenance,
        payload_tiers=payload_tiers,
        admission=admission,
    )
