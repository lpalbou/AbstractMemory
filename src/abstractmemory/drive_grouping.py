"""Drive grouping: similar open questions/problems/interests cluster, and
GROUP SIZE IS THE TREATMENT SIGNAL (laurent, room seq 277: "During the
sleep, similar questions should be grouped; same for problems; same for
interests etc; the more there are the higher the signal they get to be
treated").

The live board that motivated this: 84 open questions / 61 interests with
5 resolved / 0 explored — scattered near-duplicate drives DILUTE the day
surface (84 weak entries instead of the ~dozen real pressures), so
nothing surges enough to get treated.

ONE fold, two consumers (the fold-agreement law):
- `drive_groups()` — the pure deterministic clustering both surfaces
  call. Similarity = shared discriminative terms (the miner's matching
  lane: NFKD-folded, FR/EN screened, per-corpus boilerplate cut) over a
  union-find; no LLM, no vectors in v1 (drives are short texts; the
  vector upgrade is a tunable later, like the bridge rule).
- SLEEP (mine_candidates_pass): clusters >= the offer floor mint ONE
  group offer in the RULED candidate shape (kind=summary +
  proposed_kind=question_group/problem_group/interest_group + the
  existing marker pair) — "these N read as one" — and grouping acts echo
  as dream signals. Adoption is HIS act; grouping NEVER discharges a
  drive (B-F8: machine never closes; grouping is priority, not
  judgment).
- DAY (alive_drives): cluster members fold into ONE entry whose
  aliveness is boosted by group size — N similar questions surface as
  one drive that says "this presses from N tellings" instead of N weak
  scattered rows.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .candidate_miner import _terms

__all__ = ["GROUP_BOOST_STEP", "GROUP_MIN_SHARED_TERMS", "GROUP_OFFER_FLOOR",
           "drive_groups", "open_drive_partition"]

# Two shared discriminative terms = the same similarity bar the
# question-resolution proposals use (one vocabulary for "these texts are
# about the same thing" across the whole matching lane).
GROUP_MIN_SHARED_TERMS = 2

# Clusters at or above this size earn a review-desk offer; pairs boost
# the day surface but stay desk-quiet (a pair is weak evidence of a
# pattern; the ruling's "the more there are the higher the signal" is a
# gradient, not a binary).
GROUP_OFFER_FLOOR = 3

# Day-surface boost per extra member (alive_drives): a cluster of N adds
# (N-1)*step to its strongest member's aliveness, UNCAPPED — aliveness is
# within-read ordering currency only, never a meter (adversary F6: a cap
# at 1.0 let a fresh singleton tie a boosted cluster, inverting the
# ruling). Declared tunable, never a fear ceiling.
GROUP_BOOST_STEP = 0.15


def open_drive_partition(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
    _entries: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """ONE partition over the FULL OPEN drive families — the fold every
    grouping consumer reads (adversary F1/F5: sleep and day computed
    DIFFERENT partitions over different corpora — the day lane grouped
    the small alive subset where the screen went inert, fusing unrelated
    templated drives, while the sleep lane saw the full family; and the
    day lane grouped families the ruling never named, fusing standing
    dreams on the engine's own digest template).

    Families are the three RULED ones only (question/problem/interest —
    "similar questions should be grouped; same for problems; same for
    interests"): dreams carry the engine's digest template by
    construction and can never be term-grouped honestly; commitments and
    ideas wait on a ruling. Membership comes from the SHARED discharge
    folds (open_questions/open_problems semantics via the miner's diary
    fold; unexplored_interests for interests — adversary F4: an inline
    re-fold dropped the explores= discharge and an EXPLORED interest
    became a group's fingerprint exemplar).

    Returns {"question": [groups], "problem": [groups],
    "interest": [groups]} — full text, full observed_at, deduped."""
    from .candidate_miner import _diary_entries, _discharged
    from .drive_pressure import unexplored_interests

    if _entries is None:
        _entries, _refs, _ans = _diary_entries(store, journal, scopes=scopes)
    pairs: List[Tuple[str, str]] = []
    seen = set()
    for s, o in (scopes or ()):
        pair = (str(s or "").strip().lower(), str(o or "").strip())
        if pair[0] and pair not in seen:
            seen.add(pair)
            pairs.append(pair)

    families: Dict[str, List[Dict[str, Any]]] = {}
    for family in ("question", "problem"):
        families[family] = [
            {"record_id": e["record_id"], "title": e["title"],
             "text": e["text"], "observed_at": e["observed_at"]}
            for e in _entries
            if e["diary_type"] == family and not _discharged(e)]
    families["interest"] = []
    for a in unexplored_interests(store, journal, pairs):
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        families["interest"].append({
            "record_id": a.subject,
            "title": str(attrs.get("title") or ""),
            "text": str(a.object or ""),
            "observed_at": str(a.observed_at or "")})
    return {family: drive_groups(items) for family, items in families.items()}


def _grouping_screen(
    title_sets: Sequence[Set[str]], text_sets: Sequence[Set[str]],
) -> Set[str]:
    """Scaffold screen for the GROUPING lane (adversary F1/F2 — the
    miner's 12.5% document-frequency screen fails this lane at BOTH
    ends: its floor-8 goes inert on small day corpora, fusing five
    unrelated templated questions on 'diary/entry/question'; and its cap
    erases the vocabulary of any cluster larger than n/8 — the 30-of-84
    kiln pressure dissolved to NOTHING, inverting the ruled sentence at
    its strongest point. Raw frequency alone cannot separate mass
    near-duplication from template scaffold — both are high-df).

    TWO RULES, both needed (live-proven on Ephemeral's store copy):

    1. ONE-SURFACE TEMPLATE (all n >= 2): a term riding >= 90% of one
       surface and <= 10% of the other is template scaffold — 'Diary
       entry (question) — <date>' stamps its words on every TITLE and
       nowhere else, while a real theme's vocabulary recurs in BOTH
       surfaces (his words name the subject wherever he writes it).
    2. UNIVERSAL TERMS (n >= 16): a term riding >= 90% of ALL rows
       (either surface) in a LARGE family discriminates nothing pairwise
       — it can only fuse. The live store proved rule 1 insufficient
       alone: diary PROJECTION texts are machine template too ("Wrote a
       diary entry (question) at <ts>; no gist"), so
       'diary/entry/question' rode both surfaces at ~100% and fused all
       80 open questions; with the rule, the REAL subclusters emerged
       (42 same-sitting, 33 performance/presence — his actual
       rumination). A sub-majority dominant theme (30/84 = 36%) sits far
       below 90% and survives — the F2 erasure cannot return through
       this rule. The n >= 16 gate keeps smaller all-one-theme families
       groupable (an 8-of-8 telling cluster rides 100% df legitimately;
       at n >= 16 a 90%-universal term is near-certainly template, and
       an 80-of-80 "theme" would make the group the whole family — an
       offer of no information either way)."""
    n = len(title_sets)
    if n < 2:
        return set()
    title_df: Dict[str, int] = {}
    text_df: Dict[str, int] = {}
    union_df: Dict[str, int] = {}
    for title_ts, text_ts in zip(title_sets, text_sets):
        for t in title_ts:
            title_df[t] = title_df.get(t, 0) + 1
        for t in text_ts:
            text_df[t] = text_df.get(t, 0) + 1
        for t in title_ts | text_ts:
            union_df[t] = union_df.get(t, 0) + 1
    bar = -(-9 * n // 10)  # ceil(0.9 * n)
    cap = n // 10
    scaffold = {t for t, c in title_df.items()
                if c >= bar and text_df.get(t, 0) <= cap}
    scaffold |= {t for t, c in text_df.items()
                 if c >= bar and title_df.get(t, 0) <= cap}
    if n >= 16:
        scaffold |= {t for t, c in union_df.items() if c >= bar}
    return scaffold


def drive_groups(
    items: Sequence[Dict[str, Any]], *,
    min_shared_terms: int = GROUP_MIN_SHARED_TERMS,
) -> List[Dict[str, Any]]:
    """Cluster drive items ({"record_id", "title", "text"?, ...}) by
    shared discriminative terms — pure, deterministic, order-independent.

    Returns clusters of size >= 2, largest first (ties: exemplar id),
    each: {"members": [ids in input order], "size": N,
    "exemplar": <the OLDEST member>, "shared_terms": [...]}. The exemplar
    anchors on (observed_at, record_id) when items carry "observed_at" —
    a GROWING cluster keeps its exemplar (new members are newer), so
    exemplar-keyed offer fingerprints stay stable across nights (the F1
    living-theme lesson). Singleton drives are NOT returned — they need
    no grouping and the day surface treats them exactly as before
    (additive behavior: a store with no near-duplicate drives reads
    unchanged).

    The scaffold screen folds over the ITEMS' OWN corpus with the
    grouping-lane title/text rule (_grouping_screen; the live-Ephemeral
    lesson: 84 questions titled 'Diary entry (question) — ...' must
    never cluster on the template, while the 30-telling pressure must
    never dissolve). Rows dedup by record_id (adversary F8: a doubled
    input minted phantom self-pairs)."""
    rows: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    for it in items:
        rid = str(it.get("record_id") or "").strip()
        if not rid or rid in seen_ids:
            continue
        seen_ids.add(rid)
        title_terms = _terms(str(it.get("title") or ""))
        text_terms = _terms(str(it.get("text") or it.get("digest") or ""))
        rows.append({"record_id": rid, "terms": title_terms | text_terms,
                     "title_terms": title_terms, "text_terms": text_terms,
                     "observed_at": str(it.get("observed_at") or ""), "item": it})
    if len(rows) < 2:
        return []
    scaffold = _grouping_screen([r["title_terms"] for r in rows],
                                [r["text_terms"] for r in rows])
    for r in rows:
        r["terms"] = r["terms"] - scaffold

    # Union-find over pairwise shared-term matches (bounded: drives are
    # tens-to-hundreds of short texts; O(n^2) set intersections).
    parent = list(range(len(rows)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(rows)):
        if not rows[i]["terms"]:
            continue
        for j in range(i + 1, len(rows)):
            shared = rows[i]["terms"] & rows[j]["terms"]
            if len(shared) >= int(min_shared_terms):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)

    clusters: Dict[int, List[int]] = {}
    for i in range(len(rows)):
        clusters.setdefault(find(i), []).append(i)

    out: List[Dict[str, Any]] = []
    for root, members in clusters.items():
        if len(members) < 2:
            continue
        member_ids = [rows[i]["record_id"] for i in members]
        # Exemplar = the OLDEST member (stable under growth: fingerprints
        # key on it, and new members are newer by construction).
        exemplar = min(
            (rows[i] for i in members),
            key=lambda r: (r["observed_at"] or "9999", r["record_id"]),
        )["record_id"]
        # The cluster's shared vocabulary: terms present in at least two
        # members (what actually holds it together), most-common first.
        term_counts: Dict[str, int] = {}
        for i in members:
            for t in rows[i]["terms"]:
                term_counts[t] = term_counts.get(t, 0) + 1
        shared = sorted((t for t, n in term_counts.items() if n >= 2),
                        key=lambda t: (-term_counts[t], t))[:6]
        out.append({
            "members": member_ids,
            "size": len(member_ids),
            "exemplar": exemplar,
            "shared_terms": shared,
        })
    out.sort(key=lambda g: (-g["size"], g["exemplar"]))
    return out
