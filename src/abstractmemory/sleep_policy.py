"""Sleep-lane tuning (ONE home for phase-1/phase-2 policy numbers).

The 2026-07-10 parameter review found the sleep lane had reproduced the
fork's baked-constant disease: floors, list bounds, and salience weights
inlined across maintenance.py and consolidation.py — including a same-name
`_LIST_BOUND = 12` in BOTH modules with no shared source (the diary_type
copy-drift class). This module is the single source; both import from here,
and every knob rides `SleepTuning` so a host can tune the sleep window
without editing engine source.

Declared tunables, never fear-derived ceilings (round-9 rule): the scan cap
bounds one sleep window's O(n^2) near-dup scan — raise it for bigger
windows; the floors state what the evidence must show, not how much a mind
may hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

__all__ = [
    "DEFAULT_SLEEP_TUNING",
    "NEAR_DUP_JACCARD_FLOOR",
    "NEAR_DUP_SCAN_LIMIT",
    "NEAR_DUP_VECTOR_FLOOR",
    "SleepTuning",
]

# Fork parity note: the fork's STRUCTURAL_NEAR_DUPLICATE_SCAN_LIMIT is 250;
# ours is 200 — parity is MECHANISM-level (bounded newest-first O(n^2) scan),
# not value-level (the review caught the comment overclaiming).
NEAR_DUP_SCAN_LIMIT = 200
NEAR_DUP_JACCARD_FLOOR = 0.65
# Our vector upgrade: near-IDENTITY, deliberately far above the 0.35
# dream-bridge relatedness floor (dedup claims sameness, not relatedness).
NEAR_DUP_VECTOR_FLOOR = 0.90


@dataclass(frozen=True)
class SleepTuning:
    """Every sleep-lane policy number, one frozen object (mirrors
    AttentionConfig's role for the attention lane). Defaults ARE today's
    behavior — constructing `SleepTuning()` changes nothing."""

    # -- phase 1: tending evidence floors --------------------------------
    near_dup_scan_limit: int = NEAR_DUP_SCAN_LIMIT
    near_dup_jaccard_floor: float = NEAR_DUP_JACCARD_FLOOR
    near_dup_vector_floor: float = NEAR_DUP_VECTOR_FLOOR
    # -- report list bounds (fork's limit discipline) ---------------------
    list_bound: int = 12
    # Section-specific multiples of list_bound: metadata gaps are the
    # highest-volume, lowest-risk section (4x); edge suppressions carry two
    # sublists per pair (2x); the flat operations ledger aggregates every
    # section (6x). These were unexplained inline multipliers before.
    metadata_gaps_factor: int = 4
    suppressions_factor: int = 2
    operations_factor: int = 6
    # -- consolidation candidates -----------------------------------------
    # Per-pass candidate cap band (fork parity band). Out-of-band asks are
    # REFUSED loudly — the previous silent clamp inverted a caller's 0 into
    # 1 (works-or-loud violation, review find F4).
    candidate_cap_band: Tuple[int, int] = (1, 6)
    preserved_digests: int = 4   # source digests carried on a proposal
    # -- link candidates ---------------------------------------------------
    min_shared_facets: int = 2   # fork rule: ">= 2 shared facets" proposes a link
    shared_facets_shown: int = 6  # display bound on the shared-term list
    # -- phase 2: dream salience ------------------------------------------
    facet_min_len: int = 3
    salience_proposal_weight: int = 3
    salience_question_weight: int = 2
    salience_high: int = 6       # label floor: >= high -> "high", else "medium"

    def resolve_scan_limit(self, scan_limit: "int | None") -> int:
        """Explicit kwarg wins; None falls to the tuned default."""
        return int(self.near_dup_scan_limit if scan_limit is None else scan_limit)

    def validated_candidate_cap(self, max_candidates: int) -> int:
        """Loud band validation (works-or-loud): a cap outside the band is a
        caller error, never a silent rewrite."""
        low, high = self.candidate_cap_band
        cap = int(max_candidates)
        if not (int(low) <= cap <= int(high)):
            raise ValueError(
                f"max_candidates={cap} outside the per-pass band [{low}, {high}] "
                "(SleepTuning.candidate_cap_band) — widen the band explicitly "
                "instead of relying on a silent clamp"
            )
        return cap


DEFAULT_SLEEP_TUNING = SleepTuning()
