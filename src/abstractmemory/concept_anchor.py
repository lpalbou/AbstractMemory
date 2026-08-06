"""Concept anchoring: edge-free associative recall (fork memory_anchor.rs port).

The fork's memory anchor layer solved a failure our recall still has (the
fork-comparison audit, 2026-07-12): a record can be UNREACHABLE even though
it shares a discriminative concept with what the mind is already holding —
the keyword channel needs the query to contain the token, and spreading
needs edges or trails. Young keyword-less episodes and cue-diluted reaches
(the Castor incident) both die on that gap.

Concept anchoring closes it in three moves, all deterministic:

1. CONCEPT NORMALIZATION (`concept_terms`): variant spellings collapse to
   one concept — ``auto memory`` / ``auto-memory`` / ``autoMemory`` /
   ``auto_memory`` all yield the token pair ("auto", "memory") plus the
   joined bigram "auto_memory". Identifier shapes (camelCase, snake_case,
   kebab-case) split into their words AND keep the joined form, so code
   identifiers anchor both ways.
2. MID-FREQUENCY GATE: a concept is DISCRIMINATIVE only when it appears in
   [min_sources, max_sources] records of the scanned field. Below the floor
   it is noise (one record = no association); above the cap it is a
   stop-concept (everything mentions it — anchoring on it would re-create
   the cue-dilution failure this layer exists to fix).
3. CO-OCCURRENCE EXPANSION (`expand_by_concepts`): records sharing a
   discriminative concept with a SEED surface as candidates — no edge, no
   trail, and the term may be absent from the query. Scores are
   rarity-weighted and capped; the pass ADMITS (relevance semantics), it
   never reorders existing members.

Tunables are declared (`ConceptAnchorTuning`), never fear ceilings. The
pass is OFF by default in passive reconstruction (golden byte-stability;
hosts opt in via ReconstructConfig.concept_expansion) and ON by default in
probe() — the deliberate reach is exactly where associative reach earns
its tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

from .models import TripleAssertion
from .store import TripleQuery
from .text_tokens import fold_text

__all__ = [
    "ConceptAnchorTuning",
    "DEFAULT_CONCEPT_TUNING",
    "concept_terms",
    "expand_by_concepts",
    "record_concepts",
]

# Words inside identifiers: split camelCase boundaries before folding.
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
# A concept word: folded alnum run. 3 is deliberate (vs recall's 4): concept
# anchoring gates by FREQUENCY, not length — "gpu", "tax", "aws" are exactly
# the discriminative short tokens the length floor was protecting recall
# from losing (text_tokens.py documents them as the keyword channel's known
# limit; the mid-frequency gate is the honest stopword surrogate here).
_WORD_RE = re.compile(r"[a-z0-9]+")
_MIN_WORD_LEN = 3


@dataclass(frozen=True)
class ConceptAnchorTuning:
    """Declared tunables for the anchoring pass (one frozen object, the
    SleepTuning/AttentionConfig pattern). Defaults are the fork's shape
    scaled to entity-home sizes."""

    min_sources: int = 2         # below: a concept anchors nothing (noise)
    max_sources: int = 16        # above: stop-concept (anchoring = dilution)
    scan_limit: int = 400        # newest-first rows scanned per scope pair
    max_admissions: int = 12     # expansion admits at most this many records
    max_seed_concepts: int = 24  # discriminative concepts taken per pass
    bigrams: bool = True         # adjacent-word bigrams join as concepts

    def __post_init__(self) -> None:
        if int(self.min_sources) < 2:
            raise ValueError(
                f"min_sources must be >= 2 (a concept in {self.min_sources} record(s) "
                "associates nothing — the pass admits records BESIDE the seed)")
        if int(self.max_sources) < int(self.min_sources):
            raise ValueError(
                f"max_sources ({self.max_sources}) must be >= min_sources ({self.min_sources})")


DEFAULT_CONCEPT_TUNING = ConceptAnchorTuning()


def concept_terms(text: str, *, bigrams: bool = True) -> List[str]:
    """Normalized concept tokens for one text: identifier-aware words plus
    (optionally) adjacent-word bigrams joined with '_'. Unique, first-seen
    order, deterministic. Variants collapse: 'auto-memory', 'auto memory',
    'autoMemory' and 'auto_memory' all produce ['auto', 'memory',
    'auto_memory']."""
    # Split camelCase BEFORE folding (folding lowercases, losing the
    # boundary), then fold accents/case once.
    pre = _CAMEL_RE.sub(" ", str(text or ""))
    folded = fold_text(pre)
    words = [w for w in _WORD_RE.findall(folded) if len(w) >= _MIN_WORD_LEN]
    out: List[str] = list(dict.fromkeys(words))
    if bigrams:
        for left, right in zip(words, words[1:]):
            joined = f"{left}_{right}"
            if joined not in out:
                out.append(joined)
    return out


def record_concepts(assertion: TripleAssertion, *, bigrams: bool = True) -> Set[str]:
    """Concept set for one record row: title + digest text + the lexical
    facet lists (keywords/intents/outcomes). Participants deliberately
    excluded — they anchor through the participants channel, which scores
    WHO-overlap with its own semantics."""
    attrs = assertion.attributes if isinstance(assertion.attributes, dict) else {}
    parts: List[str] = [str(attrs.get("title") or ""), str(assertion.object or "")]
    for facet in ("keywords", "intents", "outcomes"):
        values = attrs.get(facet)
        if isinstance(values, (list, tuple)):
            parts.extend(str(v) for v in values)
    out: Set[str] = set()
    for part in parts:
        out.update(concept_terms(part, bigrams=bigrams))
    return out


def _digest_rows(
    store: Any, scope_pairs: Sequence[Tuple[str, str]], *, scan_limit: int,
    excluded_ids: Iterable[str],
) -> Dict[str, TripleAssertion]:
    """Newest-first bounded scan of digest rows per scope pair (the same
    bounded-window discipline as the sleep lane's near-dup scan). Keyed by
    ASSERTION id — the candidate/trace/commit currency (the same key the
    reconstruction universe uses), never the graph subject."""
    excluded = set(excluded_ids or ())
    rows: Dict[str, TripleAssertion] = {}
    for scope, owner in scope_pairs:
        kept = 0
        for a in store.query(TripleQuery(
                scope=scope, owner_id=owner or None,
                predicate="dcterms:abstract", limit=int(scan_limit))):
            rid = a.assertion_id
            if not (isinstance(rid, str) and rid) or rid in excluded or rid in rows:
                continue
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if not attrs.get("record_kind"):
                continue  # concept anchoring serves records, not raw triples
            rows[rid] = a
            kept += 1
            if kept >= int(scan_limit):
                break
    return rows


def expand_by_concepts(
    store: Any,
    seeds: Mapping[str, TripleAssertion],
    scope_pairs: Sequence[Tuple[str, str]],
    *,
    excluded_ids: Iterable[str] = (),
    tuning: ConceptAnchorTuning = DEFAULT_CONCEPT_TUNING,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Co-occurrence expansion: records sharing a DISCRIMINATIVE concept
    with a seed surface as admissions.

    Returns (admissions, notes) where each admission is
    {record_id, assertion, score, concepts} — score in (0, 1], rarity
    weighted: rarer shared concepts score higher; multiple shared concepts
    sum then clamp at 1.0. Deterministic: ties break on record id.

    The pass is a pure read. It admits only records NOT already in seeds
    (expansion, not reordering), and never more than max_admissions.
    """
    notes: List[str] = []
    if not seeds:
        return [], notes

    field = _digest_rows(store, scope_pairs, scan_limit=tuning.scan_limit,
                         excluded_ids=excluded_ids)
    # Seeds ride the field too (their concepts index identically) — make
    # sure they are present even when older than the scan window.
    for rid, a in seeds.items():
        field.setdefault(rid, a)

    concepts_of: Dict[str, Set[str]] = {
        rid: record_concepts(a, bigrams=tuning.bigrams) for rid, a in field.items()
    }
    # Concept -> source records (the anchor index).
    sources: Dict[str, Set[str]] = {}
    for rid, concepts in concepts_of.items():
        for c in concepts:
            sources.setdefault(c, set()).add(rid)

    lo, hi = int(tuning.min_sources), int(tuning.max_sources)

    # Discriminative concepts present in ANY seed, rarest first (the most
    # discriminative association wins the bounded seed-concept budget).
    seed_concepts: List[str] = []
    for rid in sorted(seeds.keys()):
        for c in sorted(concepts_of.get(rid, ())):
            n = len(sources.get(c, ()))
            if lo <= n <= hi and c not in seed_concepts:
                seed_concepts.append(c)
    seed_concepts.sort(key=lambda c: (len(sources[c]), c))
    if len(seed_concepts) > int(tuning.max_seed_concepts):
        notes.append(
            f"concept expansion: {len(seed_concepts)} discriminative concepts, "
            f"taking the {int(tuning.max_seed_concepts)} rarest")
        seed_concepts = seed_concepts[: int(tuning.max_seed_concepts)]

    # Rarity weight: a concept shared by exactly min_sources records scores
    # 1.0; at max_sources it approaches the floor. Linear, explainable.
    def rarity(c: str) -> float:
        n = len(sources[c])
        if hi == lo:
            return 1.0
        return max(0.0, min(1.0, (hi - n + 1) / (hi - lo + 1)))

    scored: Dict[str, Dict[str, Any]] = {}
    for c in seed_concepts:
        for rid in sources[c]:
            if rid in seeds:
                continue
            entry = scored.setdefault(rid, {"score": 0.0, "concepts": []})
            entry["score"] = min(1.0, float(entry["score"]) + rarity(c))
            entry["concepts"].append(c)

    ranked = sorted(scored.items(), key=lambda kv: (-float(kv[1]["score"]), kv[0]))
    admissions: List[Dict[str, Any]] = []
    for rid, entry in ranked[: int(tuning.max_admissions)]:
        admissions.append({
            "record_id": rid,
            "assertion": field[rid],
            "score": float(entry["score"]),
            "concepts": sorted(entry["concepts"]),
        })
    if len(ranked) > int(tuning.max_admissions):
        notes.append(
            f"concept expansion: {len(ranked)} associated records, admitting "
            f"the strongest {int(tuning.max_admissions)}")
    return admissions, notes
