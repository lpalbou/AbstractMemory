"""mind_mass_report() — the mind-health card's engine half (backlog 0043).

The operator's glance question is "is this mind healthy?". Two live
incidents defined the card: the rogue-embedder incident (recall failure
from a misconfigured embedding model — invisible until a forensic script
joined the store's pin with the serving endpoint's refusal) and the 92MB
wake-cue duplicate mass (invisible until a hand census). Both facts were
ALREADY in the engine; nothing composed them. This module is that
composition: ONE pure read over reads that each shipped separately.

COMPOSE, DON'T REIMPLEMENT (the 0042 rule, applied here): duplicate
clusters reuse maintenance's `_scan` input discipline + `title_key`
fold (with the closure fold applied — a repaired duplicate must stop
counting, adversary P1-4); the wake-cue sub-count IS
`wake_cue_dedup_pass(report_only=True)`; review depth lifts
`cognition_health`'s candidates block VERBATIM (one fold, one truth — a
second fold here could disagree with the /cognition door, the cross-key
discharge lesson); dreams ride `consolidation.unresolved_dreams`; sleep
recency rides `sleep_cadence.last_maintenance_seq`.

CONSUMER CONTRACT (observer's two shape asks, adopted on the record —
commons c4113/c4132):
- every count says what it counts: sections carry `unit` (uniform) or
  `units` (per-field) labels; counts that are not plain record counts
  are named for what they are (`current_seq`, `walked`).
- warnings are `{word, detail}` pairs — `word` is badge-stable
  vocabulary (WARNING_WORDS), `detail` is the tooltip sentence. Warnings
  state STRUCTURAL FACTS (identity mismatch, pinless store, partial or
  unavailable scan, never-slept) — never threshold judgments; thresholds
  that alert on their own are a non-goal (0043): presentation belongs to
  the panel.

WINDOW-BOUNDED MANDATORY: 24/7 residents produce ~5k journal records a
day, so the journal walk starts at `seq_at(window start)` — the walk is
O(window), never O(life). Store scans are O(records) by nature (records
grow orders slower than journal mass); the vector sub-scan is
additionally bounded by `vector_scan_limit` and says so when partial.

CADENCE HONESTY (adversary P1-5): one call runs several full store
scans (formation, tending, per-pair wake-cue dry-runs, cognition_health,
unresolved_dreams) plus their closure/binding folds — this is a DAILY /
on-demand glance read, not a per-second polling target. A board tile
should cache it at glance cadence.

PURE READ: deposits nothing, writes nothing, no thresholds fire.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .cognition_health import cognition_health
from .consolidation import unresolved_dreams
from .doctoring import wake_cue_dedup_pass
from .embedding_pin import embedder_model_id, pin_note
from .folds import closure_exclusions
from .maintenance import _scan as _tending_scan
from .sleep_cadence import last_maintenance_seq
from .store import TripleQuery
from .text_tokens import title_key

__all__ = [
    "VECTOR_SCAN_LIMIT",
    "WARNING_WORDS",
    "mind_mass_report",
]

# Newest-first bound on the per-row stored_vector sub-scan. Each read is
# one indexed lookup; the bound keeps a long life's glance read cheap and
# the report SAYS when it was partial (vector_scan.partial + a warning).
VECTOR_SCAN_LIMIT = 4000

# The badge-stable warning vocabulary (observer ask 2: a tile badges the
# word and tooltips the detail — prose blobs cannot be badged). Adding a
# word here is an interface change for panel consumers: additive only.
WARNING_WORDS = frozenset({
    "embedder_mismatch",   # pinned model != wired embedder model
    "dimension_mismatch",  # stored/claimed dimension != pinned dimension
    "unpinned",            # no embedding pin at all (pre-M1 home)
    "vectorless_records",  # pinned space, yet N digest rows carry no vector
    "vector_scan_partial", # the vectorless count saw a bounded sample, or none
    "never_slept",         # no sleep artifact has ever formed
})


def _utc_now(now: Optional[str]) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(str(now).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    # Normalize to UTC (adversary P2): record observed_at strings are UTC,
    # and the window fold compares ISO strings lexicographically — a +05:00
    # boundary string would shift the window by the offset.
    return parsed.astimezone(timezone.utc)


def _when(record: Any) -> str:
    """Tolerant timestamp of one journal-family record ("" = undated).
    Every current family carries observed_at (adversary confirmed); the
    alternates keep future families from silently bucketing undated."""
    for attr in ("observed_at", "created_at", "closed_at", "at"):
        value = getattr(record, attr, None)
        if value is None and isinstance(record, dict):
            value = record.get(attr)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _warning(word: str, detail: str) -> Dict[str, str]:
    if word not in WARNING_WORDS:  # keep the vocabulary closed and testable
        raise ValueError(f"unknown mind-mass warning word: {word!r}")
    return {"word": word, "detail": detail}


def _normalized_pairs(scopes: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Store-grammar normalization + dedupe (adversary P1-3): TripleQuery
    strip+lowers scope and strips owner, so ("Life", o) and ("life", o)
    query IDENTICAL rows — exact-tuple dedupe alone double-counts mass.
    Subset overlaps (a ("life", "") wildcard beside ("life", owner)) are
    deeper than pair identity; the formation fold guards those by
    counting DISTINCT assertions, never summing pair queries."""
    pairs: List[Tuple[str, str]] = []
    for scope, owner in scopes:
        pair = (str(scope).strip().lower(), str(owner).strip())
        if pair not in pairs:
            pairs.append(pair)
    if not pairs:
        raise ValueError("mind_mass_report requires at least one (scope, owner) pair")
    return pairs


def _formation_scan(
    store: Any, pairs: Sequence[Tuple[str, str]], since_iso: str,
) -> Dict[str, Any]:
    """One digest-row pass: all-time totals by kind, window curve by day,
    per-pair growth, machine mass, dream recency inputs, vector-scan rows.
    Global counts fold DISTINCT assertions (seen-set): overlapping pairs
    (wildcard owner beside a named owner) must not double-count; the
    per-pair block deliberately keeps the overlapping per-pair view."""
    total_by_kind: Dict[str, int] = {}
    by_day: Dict[str, Dict[str, int]] = {}
    pair_rows: Dict[Tuple[str, str], Dict[str, int]] = {
        pair: {"records": 0, "formed_in_window": 0} for pair in pairs}
    machine = 0
    dreams_total = 0
    newest_dream_at: Optional[str] = None
    scan_rows: List[Any] = []  # distinct digest rows, for the vector sub-scan
    seen: Set[str] = set()

    for pair in pairs:
        scope, owner = pair
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None,
                                         predicate="dcterms:abstract", limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            kind = str(attrs.get("record_kind") or "memory")
            when = str(a.observed_at or "")
            in_window = when >= since_iso

            pair_rows[pair]["records"] += 1
            if in_window:
                pair_rows[pair]["formed_in_window"] += 1

            row_id = str(a.assertion_id or f"{a.subject}|{scope}|{owner}")
            if row_id in seen:
                continue  # global counts are distinct-assertion counts
            seen.add(row_id)

            scan_rows.append(a)
            total_by_kind[kind] = total_by_kind.get(kind, 0) + 1
            if attrs.get("maintenance_candidate") or attrs.get("bookkeeping"):
                machine += 1
            if kind == "dream":
                dreams_total += 1
                if when and (newest_dream_at is None or when > newest_dream_at):
                    newest_dream_at = when
            if in_window and when:
                day = when[:10]
                by_day.setdefault(day, {})[kind] = by_day.get(day, {}).get(kind, 0) + 1

    return {
        "total_by_kind": dict(sorted(total_by_kind.items())),
        "by_day": [
            {"day": day, "kinds": dict(sorted(kinds.items())),
             "total": sum(kinds.values())}
            for day, kinds in sorted(by_day.items())
        ],
        "records_total": sum(total_by_kind.values()),
        "machine_records": machine,
        "pairs": [
            {"scope": scope, "owner_id": owner, **counts}
            for (scope, owner), counts in pair_rows.items()
        ],
        "dreams_total": dreams_total,
        "newest_dream_at": newest_dream_at,
        "scan_rows": scan_rows,
    }


def _journal_curve(journal: Any, since_iso: str) -> Dict[str, Any]:
    """Window-bounded family/day curve over the replay stream. seq_at
    anchors the walk at the window start, so the cost is O(window)."""
    since_seq = int(journal.seq_at(since_iso))
    by_day: Dict[str, Dict[str, int]] = {}
    walked = 0
    for family, record in journal.replay_records(since_seq=since_seq):
        walked += 1
        day = _when(record)[:10] or "undated"
        by_day.setdefault(day, {})[family] = by_day.get(day, {}).get(family, 0) + 1
    return {
        "unit": "journal records",
        "since_seq": since_seq,
        "walked": walked,
        "by_day": [
            {"day": day, "families": dict(sorted(families.items())),
             "total": sum(families.values())}
            for day, families in sorted(by_day.items())
        ],
    }


def _compaction(store: Any, current_seq: int) -> Dict[str, Any]:
    """Newest compaction cut from the store-file meta (doctoring writes the
    'compaction' key as an append-only history list; homes keep store and
    journal in one file, so the store's meta table is the right door).
    Absence of the capability or the key reads as available=False —
    an entry without 'at' reads as unknown, never a guess (doctoring's
    own consumer note)."""
    reader = getattr(store, "meta_json", None)
    if not callable(reader):
        return {"available": False,
                "detail": "store backend exposes no compaction meta"}
    history = reader("compaction")
    if not history:
        return {"available": False,
                "detail": "no compaction recorded (absent or unreadable meta)"}
    entries = history if isinstance(history, list) else [history]
    newest = entries[-1] if isinstance(entries[-1], dict) else {}
    cut_seq = newest.get("cut_seq")
    return {
        "available": True,
        "at": newest.get("at"),  # may be absent on pre-field cuts: unknown
        "cut_seq": cut_seq,
        "archive_ref": newest.get("archive_ref"),
        "cuts_total": len(entries),
        "seq_since_cut": (int(current_seq) - int(cut_seq)
                          if isinstance(cut_seq, (int, float)) else None),
    }


def _duplicate_mass(
    store: Any, journal: Any, pairs: Sequence[Tuple[str, str]],
    wake_cue_kind: Optional[str], excluded: frozenset,
) -> Dict[str, Any]:
    """Duplicate clusters, two labeled sources. Title clusters reuse the
    tending scan's input discipline (same exclusions as maintenance_report:
    dreams/world_model/bookkeeping/candidates never count) PLUS the closure
    fold (adversary P1-4: the store is append-only, so without it the count
    could never drop after the very repair this report motivates), folded
    UNBOUNDED — maintenance_report's list_bound bounds its proposal LIST; a
    health count must be exact. The wake-cue sub-count is the doctoring
    dry-run itself, never a re-derivation; clusters dedupe by member set
    so overlapping pairs cannot double-count one cluster."""
    records, _edges, _candidates = _tending_scan(store, pairs)
    by_key: Dict[Tuple[str, str], int] = {}
    for rid, rec in records.items():
        if rid in excluded or str(rec.get("assertion_id") or "") in excluded:
            continue  # repaired/retracted duplicates stopped counting
        key = title_key(rec["title"])
        if key:
            pair = (rec["kind"], key)
            by_key[pair] = by_key.get(pair, 0) + 1
    clusters = {pair: n for pair, n in by_key.items() if n > 1}

    out: Dict[str, Any] = {
        "units": {"title_clusters": "clusters", "title_cluster_records": "records"},
        "title_clusters": len(clusters),
        "title_cluster_records": sum(clusters.values()),
        "sources": {
            "title_clusters": "maintenance duplicate-title fold (unbounded count, "
                              "closure fold applied, same input discipline as "
                              "maintenance_report)",
        },
    }
    if wake_cue_kind:
        # wake_cue_dedup_pass takes the system facade; report_only touches
        # only store/journal/current_seq, which this view carries — any
        # future attribute reach fails LOUD (AttributeError), never silent.
        view = SimpleNamespace(store=store, journal=journal,
                               current_seq=journal.current_seq)
        cluster_sets: Set[frozenset] = set()
        for scope, owner in pairs:
            report = wake_cue_dedup_pass(
                view, scope=scope, owner_id=owner, actor="mind-mass-report",
                kind=str(wake_cue_kind), report_only=True)
            for cluster in report.get("clusters") or ():
                members = frozenset(cluster.get("members") or ())
                if members:
                    cluster_sets.add(members)
        out["units"].update(wake_cue_clusters="clusters", wake_cue_members="records")
        out["wake_cue_clusters"] = len(cluster_sets)
        out["wake_cue_members"] = sum(len(m) for m in cluster_sets)
        out["sources"]["wake_cue_clusters"] = (
            f"wake_cue_dedup_pass(report_only=True, kind={wake_cue_kind!r})")
    return out


def _wired_dimension(embedder: Any) -> Optional[int]:
    """Declared output dimension of a wired embedder, when it exposes one
    (attribute conventions; None = unknown — enforcement then rests on the
    stored vectors themselves, measured in the sub-scan below)."""
    if embedder is None:
        return None
    for attr in ("dimension", "embedding_dimension", "dim"):
        value = getattr(embedder, attr, None)
        if isinstance(value, int) and value > 0:
            return value
    return None


def _embedding_health(
    store: Any, embedder: Any, scan_rows: Sequence[Any],
    vector_scan_limit: int, warnings: List[Dict[str, str]],
) -> Dict[str, Any]:
    pin = store.embedding_pin() if callable(getattr(store, "embedding_pin", None)) else None
    wired = embedder_model_id(embedder) if embedder is not None else None
    pinned_model = (pin or {}).get("model_id")
    pinned_dim = (pin or {}).get("dimension")
    match: Optional[bool] = None
    if pinned_model and wired:
        match = (pinned_model == wired)
        if not match:
            warnings.append(_warning(
                "embedder_mismatch",
                f"store is pinned to {pinned_model!r} but the wired embedder "
                f"claims {wired!r} — recall's vector channel degrades to "
                "labeled vectorless until they agree (or reembed runs)"))
    # Dimension is the fallback identity axis (embedding_pin contract:
    # identity-less embedders are enforced BY DIMENSION) — adversary P1-1:
    # without this check, dimension-only pins had no mismatch surface.
    wired_dim = _wired_dimension(embedder)
    if isinstance(pinned_dim, int) and wired_dim and wired_dim != pinned_dim:
        if match is None:
            match = False
        warnings.append(_warning(
            "dimension_mismatch",
            f"store is pinned to dimension {pinned_dim} but the wired "
            f"embedder declares {wired_dim} — wrong-space vectors would be "
            "refused at write; reembed is the sanctioned migration"))
    if pin is None:
        warnings.append(_warning(
            "unpinned",
            "no embedding pin — this store predates creation-time pinning "
            "(M1); dimension enforcement only starts at the first embedded "
            "write"))

    out: Dict[str, Any] = {
        "pin": dict(pin) if pin else None,
        "pin_note": pin_note(pin),
        "wired_model": wired,
        "match": match,
    }

    # Bounded vectorless sub-scan (newest first: fresh formation failing to
    # embed is the live signal; ancient pre-vector rows are known history).
    # The same walk measures stored dimensions against the pin — wrong-space
    # vectors AT REST are the rogue-embedder signature itself.
    reader = getattr(store, "stored_vector", None)
    if callable(reader):
        rows = sorted(scan_rows, key=lambda a: str(a.observed_at or ""), reverse=True)
        bound = max(0, int(vector_scan_limit))
        sample = rows[:bound] if bound else rows
        vectorless = 0
        off_dimension = 0
        for a in sample:
            vector = reader(a.assertion_id)
            if vector is None:
                vectorless += 1
            elif isinstance(pinned_dim, int) and len(vector) != pinned_dim:
                off_dimension += 1
        partial = len(rows) > len(sample)
        out["vector_scan"] = {
            "unit": "records", "scanned": len(sample), "of": len(rows),
            "vectorless": vectorless, "off_dimension": off_dimension,
            "partial": partial,
        }
        if partial:
            warnings.append(_warning(
                "vector_scan_partial",
                f"vectorless count saw the newest {len(sample)} of {len(rows)} "
                "records — raise vector_scan_limit for an exhaustive pass"))
        if vectorless and pin is not None:
            warnings.append(_warning(
                "vectorless_records",
                f"{vectorless} of {len(sample)} scanned records carry no "
                "stored vector despite a pinned embedding space — they are "
                "invisible to vector recall (the rogue-embedder signature; "
                "reembed repairs)"))
        if off_dimension:
            warnings.append(_warning(
                "dimension_mismatch",
                f"{off_dimension} of {len(sample)} scanned records store a "
                "vector whose dimension contradicts the pin — mixed embedding "
                "spaces at rest; reembed is the sanctioned repair"))
    else:
        # Adversary P1-2: capability absence must reach the badge path,
        # not just a field a tile never reads.
        out["vector_scan"] = {"unit": "records", "scanned": 0, "of": len(scan_rows),
                              "vectorless": None, "off_dimension": None,
                              "partial": True}
        warnings.append(_warning(
            "vector_scan_partial",
            "store backend exposes no stored_vector read — the vectorless "
            "count is unavailable on this backend"))
    return out


def mind_mass_report(
    store: Any,
    journal: Any,
    *,
    scopes: Sequence[Tuple[str, str]],
    days: int = 30,
    bucket: str = "day",
    embedder: Any = None,
    now: Optional[str] = None,
    vector_scan_limit: int = VECTOR_SCAN_LIMIT,
    wake_cue_kind: Optional[str] = "episode",
) -> Dict[str, Any]:
    """The mind-health card's engine half: formation cadence, journal mass,
    duplicate mass, embedding-space integrity, review backlog, and sleep
    recency — one window-bounded pure read (module docstring carries the
    composition map, the consumer contract, and the cadence note).

    `embedder` is the WIRED embedder (optional): passing it turns the pin
    comparison from "what the store claims" into claimed-vs-wired. `now`
    exists for deterministic tests (normalized to UTC). `wake_cue_kind=None`
    skips the doctoring dry-run sub-count. `bucket` is validated ("day" is
    v1's only resolution) so the shape can widen without a signature break.
    """
    if str(bucket) != "day":
        raise ValueError(f"mind_mass_report supports bucket='day' only (got {bucket!r})")
    if int(days) < 1:
        raise ValueError(f"mind_mass_report requires days >= 1 (got {days!r})")
    pairs = _normalized_pairs(scopes)

    now_dt = _utc_now(now)
    since_iso = (now_dt - timedelta(days=int(days))).isoformat()
    warnings: List[Dict[str, str]] = []

    formation = _formation_scan(store, pairs, since_iso)
    scan_rows = formation.pop("scan_rows")
    dreams_total = formation.pop("dreams_total")
    newest_dream_at = formation.pop("newest_dream_at")
    pair_growth = formation.pop("pairs")

    journal_section = _journal_curve(journal, since_iso)
    current_seq = int(journal.current_seq())
    journal_section["current_seq"] = current_seq
    journal_section["compaction"] = _compaction(store, current_seq)

    embedding = _embedding_health(store, embedder, scan_rows,
                                  vector_scan_limit, warnings)

    # ONE closure fold for the reads this module folds itself (the
    # composed callees keep their own folds — one truth per callee).
    excluded = closure_exclusions(journal, current_seq)

    unresolved_ids: Set[str] = set()
    for scope, owner in pairs:
        for row in unresolved_dreams(store, scope=scope, owner_id=owner,
                                     journal=journal, limit=0):
            unresolved_ids.add(str(row.assertion_id or row.subject))
    health = cognition_health(store, journal, scopes=pairs)
    review = {
        "unit": "records",
        "unresolved_dreams": len(unresolved_ids),
        "candidates": health["candidates"],
        "sources": {
            "unresolved_dreams": "consolidation.unresolved_dreams (closure/hidden "
                                 "folds; distinct rows across pairs)",
            "candidates": "cognition_health.candidates — the SAME fold the "
                          "/cognition door serves (one truth, no drift)",
        },
    }

    artifact_seq = int(last_maintenance_seq(store, journal, scopes=pairs))
    if artifact_seq == 0:
        warnings.append(_warning(
            "never_slept",
            "no sleep artifact (dream or maintenance candidate) has ever "
            "formed in these scopes — consolidation has never run"))
    sleep = {
        "last_artifact_seq": artifact_seq,  # 0 = never; a journal seq, not a count
        "newest_dream_at": newest_dream_at,
        "dreams": {"unit": "records", "total": dreams_total},
    }

    return {
        "report": "mind_mass_report",
        "as_of_seq": current_seq,
        "window": {"days": int(days), "bucket": "day",
                   "since": since_iso, "until": now_dt.isoformat()},
        "formation": {"unit": "records", **formation},
        "pairs": {"unit": "records", "by_pair": pair_growth},
        "journal": journal_section,
        "duplicates": _duplicate_mass(store, journal, pairs, wake_cue_kind, excluded),
        "embedding": embedding,
        "review": review,
        "sleep": sleep,
        "warnings": warnings,
        "provenance": (
            "pure read — deposits nothing, writes nothing; counts label "
            "their unit; warnings are structural facts as {word, detail} "
            "pairs (WARNING_WORDS vocabulary), never threshold judgments; "
            "glance-cadence read (several full store scans per call), "
            "cache at the panel, do not poll"),
    }
