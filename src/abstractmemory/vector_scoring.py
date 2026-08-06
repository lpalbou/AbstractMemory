"""Shared vector scoring for the triple stores (one definition, all stores).

Extracted from InMemoryTripleStore when SQLiteTripleStore gained native
vectors (a2a 0003, the entity-home pairing): both stores must resolve
cosine ranking IDENTICALLY — two copies of a scoring loop drift (same
lesson as canonical_spark_hash). The semantics here ARE the reference
semantics the InMemory store shipped with:

- cosine over the OVERLAPPING prefix (min length) — a dimension mismatch
  degrades to partial overlap rather than raising (defensive; embedder
  swaps mid-file are a store-hygiene problem the 0014 embedding manifest
  will make loud);
- empty/zero vectors score 0.0; scoring errors score 0.0;
- rows WITHOUT a vector are skipped silently here — the VECTOR CHANNEL
  owns the loud "#FALLBACK: ... vectorless rows" warning (channels.py), so
  the degradation is labeled once, where recall happens;
- min_score filters BEFORE ranking; results order by score desc.
"""

from __future__ import annotations

import math
from typing import Any, Callable, List, Optional, Sequence, Tuple

__all__ = ["cosine", "rank_by_cosine"]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    # Defensive: handle empty vectors.
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        ax = float(a[i])
        bx = float(b[i])
        dot += ax * bx
        na += ax * ax
        nb += bx * bx
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def rank_by_cosine(
    query_vector: Sequence[float],
    items: Sequence[Any],
    vector_of: Callable[[Any], Any],
    *,
    min_score: Optional[float] = None,
    limit: Optional[int] = None,
) -> List[Tuple[float, Any]]:
    """Score + rank candidates: skip items whose vector is not a list
    (vectorless rows — the channel labels the degradation), score errors →
    0.0, min_score filter, score-desc order, optional truncation."""
    ranked: List[Tuple[float, Any]] = []
    for item in items:
        v = vector_of(item)
        if not isinstance(v, list):
            continue
        try:
            score = cosine(query_vector, v)
        except Exception:
            score = 0.0
        if min_score is not None and score < float(min_score):
            continue
        ranked.append((score, item))
    ranked.sort(key=lambda t: t[0], reverse=True)
    return ranked if limit is None else ranked[:limit]
