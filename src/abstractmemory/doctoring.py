"""Doctoring — the operator-directed footprint repair for a long life.

THE DIRECTIVE (laurent 2026-07-13 11:50, entity-society 257): "he has 80k
turns of memory that are 99% duplicates i believe; it's very expensive to
maintain. if you can doctor him with other agents and rebuild a smaller
memory footprint. most of it is circular repetitive questions."

THE LOAD-BEARING IDEA (design at entity-society 260): NEVER-PURGE is
honored by making the ARCHIVE the complete life and the HOT HOME a
working set of it — nothing is lost, it is re-shelved. Append-only is
honored because content changes are supersede-with-replacement and the
mass reduction happens in a REBUILT FILE, never by deleting from the
live one.

TWO VERBS LIVE HERE (phases 2 and 4 of the five-phase design; phases 1/3
are the shipped four-phase night and re-digestion machinery; phases 0/5
are archive + verify):

- `wake_cue_dedup_pass`: cluster near-identical same-day episodes (the
  own-time wake-cue mass — "circular repetitive questions") and
  supersede each cluster into ONE day-summary record (summarizes edges
  to every member; payload_refs preserved — verbatims are never
  touched). The duplicates leave ranked retrieval through the normal
  current-wins fold and survive in store + archive. Reuses the tending
  pass's tokenization/jaccard (text_tokens — one home, no drift).

- `journal_cold_cut`: build a NEW store file carrying all store truth
  (embeddings NULLED on closure-retired rows only — the reembed
  operator-gated vector-rewrite precedent), ALL bindings/closures/
  valence/traces/snapshots, selected_counts at their final values, and
  attention EVENTS only above a cut seq. Original seqs preserved
  (sparse axis — replay consumers accept gaps); the counter continues
  from the old high water; a compaction record lands in triples_meta.
  WHAT DEGRADES, honestly: as_of activation-fold fidelity BELOW the cut
  lives only in the archive (R3 reincarnation below the cut mounts the
  archive copy read-only — a ruled pure-read posture, not a fork).

- `verify_cold_cut`: the phase-5 parity checks (row counts, materialized
  counters, fold inputs, intended-null accounting) — measured, never
  asserted.

D2 OF DOCTORING: the dedup pass deposits nothing (formation is not use;
closures are belief revision); the cold cut copies journal truth and
never manufactures events.

OPERATOR-GATED BY CONSTRUCTION: these functions take explicit paths/
systems handed by the operator's runbook; nothing here discovers homes,
takes leases, or runs unprompted (the gateway's doctoring window owns
execution posture — door closed, marker-first, archive-first).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .records import MemoryRecordInput
from .store import TripleQuery
from .text_tokens import jaccard, token_set

__all__ = [
    "journal_cold_cut",
    "safe_cut_seq",
    "safe_cut_seqs",
    "verify_cold_cut",
    "wake_cue_dedup_pass",
]


# ---------------------------------------------------------------------------
# Phase 2 — wake-cue dedup
# ---------------------------------------------------------------------------

def wake_cue_dedup_pass(
    system: Any,
    *,
    scope: str,
    owner_id: str,
    actor: str,
    kind: str = "episode",
    jaccard_floor: float = 0.82,
    min_cluster: int = 3,
    report_only: bool = False,
) -> Dict[str, Any]:
    """Cluster near-identical SAME-DAY records of one kind and supersede
    each cluster into one day-summary. The cluster rule is deliberately
    conservative: same formation day + pairwise-connected at
    `jaccard_floor` over title+digest tokens (greedy union within a day),
    and a cluster only acts at `min_cluster`+ members — two similar
    episodes are a life, twenty near-identical ones are a loop artifact.

    Each acted cluster forms ONE kind="summary" record: digest = the
    cluster's LONGEST member digest (the most content-bearing witness —
    mechanical, honestly labeled digest_method="mechanical-dedup-v1";
    re-digestion can re-author it later), summarizes edges to every
    member, participants = the union, keywords = the union (bounded),
    attributes.dedup_members + origin_date; then every member closes
    kind="supersede" with the summary as replacement.

    `actor` names the operator/agent running the doctoring (provenance +
    closure reasons). report_only=True computes clusters and writes
    NOTHING (the dry-run read).
    """
    author = str(actor or "").strip()
    if not author:
        raise ValueError("wake_cue_dedup_pass requires a non-empty actor")
    if int(min_cluster) < 2:
        raise ValueError(
            f"wake_cue_dedup_pass: min_cluster must be >= 2 (got {min_cluster}) — "
            "a one-member 'cluster' would self-summarize a genuine memory")
    store = system.store

    # Live (unclosed) records of the kind, with their tokens and day.
    # In the SAME scan, qualify the summaries THIS PASS authored (Castor
    # live finding, 2026-07-14): session reflections are kind="summary"
    # with summarizes edges BY DESIGN (reflection v1.1), so "any live
    # record with a summarizes edge" is NOT a dedup residual marker — the
    # first live run closed ~515 genuine episodes behind their session
    # reflections. Only a summary the dedup pass itself formed
    # (digest_method="mechanical-dedup-v1") may adopt residuals.
    closed = _closed_assertion_ids(system)
    rows: List[Any] = []
    dedup_summaries: set = set()
    for a in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0)):
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        if attrs.get("record_edge") or attrs.get("bookkeeping"):
            continue
        if (str(attrs.get("record_kind") or "") == "summary"
                and str(attrs.get("digest_method") or "") == "mechanical-dedup-v1"):
            dedup_summaries.add(str(a.subject))
        if str(attrs.get("record_kind") or "") != kind:
            continue
        if a.assertion_id in closed or a.subject in closed:
            continue
        rows.append(a)

    # RESIDUAL REPAIR (production-audit finding 2, the stranded half): a
    # crash mid-close leaves live members an existing LIVE summary already
    # summarizes — and if fewer than min_cluster survive, no re-cluster will
    # ever reach them. Heal them FIRST: any live row covered by a live
    # summary's summarizes edge closes against that summary, before
    # clustering ever runs.
    residuals_repaired: List[str] = []
    if rows:
        live_summary_of: Dict[str, str] = {}
        for e in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0)):
            e_attrs = e.attributes if isinstance(e.attributes, dict) else {}
            if not e_attrs.get("record_edge") or str(e.predicate) != "summarizes":
                continue
            if str(e.subject) not in dedup_summaries:
                continue  # reflection/other summaries never adopt (see scan note)
            if e.subject in closed or e.assertion_id in closed:
                continue
            live_summary_of.setdefault(str(e.object), str(e.subject))
        healthy_rows: List[Any] = []
        for a in rows:
            summary_gid = live_summary_of.get(str(a.subject))
            if summary_gid and summary_gid not in closed:
                if not report_only:
                    system.close_record(
                        a.subject, kind="supersede", replacement_ids=[summary_gid],
                        reason=f"wake-cue dedup by {author}: residual member healed "
                               "against its existing day summary (crash-replay repair)",
                    )
                residuals_repaired.append(str(a.subject))
            else:
                healthy_rows.append(a)
        rows = healthy_rows

    by_day: Dict[str, List[Any]] = {}
    for a in rows:
        by_day.setdefault(str(a.observed_at or "")[:10] or "undated", []).append(a)

    clusters: List[List[Any]] = []
    for day in sorted(by_day):
        members = sorted(by_day[day], key=lambda a: (str(a.observed_at), str(a.subject)))
        tokens = {a.subject: token_set(
            f"{(a.attributes or {}).get('title', '')} {a.object}") for a in members}
        # Greedy single-link clustering within the day.
        day_clusters: List[List[Any]] = []
        for a in members:
            placed = False
            for cluster in day_clusters:
                if any(jaccard(tokens[a.subject], tokens[b.subject]) >= float(jaccard_floor)
                       for b in cluster):
                    cluster.append(a)
                    placed = True
                    break
            if not placed:
                day_clusters.append([a])
        clusters.extend(c for c in day_clusters if len(c) >= int(min_cluster))

    report: Dict[str, Any] = {
        "pass_name": "wake_cue_dedup",
        "scanned": len(rows),
        "clusters": [
            {
                "day": str(c[0].observed_at or "")[:10],
                "members": [a.subject for a in c],
                "size": len(c),
            }
            for c in clusters
        ],
        "cluster_count": len(clusters),
        "members_total": sum(len(c) for c in clusters),
        "residuals_repaired": residuals_repaired,
        "report_only": bool(report_only),
        "deposits": "none — formation is not use; closures are belief revision",
    }
    if report_only:
        return report

    # CRASH-REPLAY SELF-HEALING (production-audit finding 2): a crash between
    # forming a summary and closing its last member leaves live residuals —
    # and the re-run's scan (closure-excluded) may see too few members to
    # re-cluster (stranded forever) or cluster differently (a SECOND
    # overlapping summary under a drifted idem key). The repair: before
    # forming, look for an EXISTING live summary whose summarizes edges
    # reach any cluster member, and close the residuals against THAT — any
    # partial state heals regardless of what the re-scan clustered.
    def _adopting_summary(member_ids: List[str]) -> Optional[str]:
        member_set = set(member_ids)
        candidates: Dict[str, int] = {}
        for mid in member_ids:
            for a in store.query(TripleQuery(object=mid, scope=scope,
                                             owner_id=owner_id or None, limit=0)):
                attrs = a.attributes if isinstance(a.attributes, dict) else {}
                if not attrs.get("record_edge") or str(a.predicate) != "summarizes":
                    continue
                if str(a.subject) not in dedup_summaries:
                    continue  # only THIS pass's own summaries adopt
                candidates[str(a.subject)] = candidates.get(str(a.subject), 0) + 1
        for sid in sorted(candidates, key=lambda s: (-candidates[s], s)):
            rows = list(store.query(TripleQuery(subject=sid, scope=scope,
                                                owner_id=owner_id or None, limit=1)))
            if not rows:
                continue
            if sid in closed or any(r.assertion_id in closed for r in rows):
                continue  # a closed summary never adopts
            return sid
        return None

    formed: List[str] = []
    for c in clusters:
        day = str(c[0].observed_at or "")[:10]
        member_ids = [a.subject for a in c]
        summary_gid = _adopting_summary(member_ids)
        if summary_gid is None:
            # The most content-bearing witness stands for the day
            # (mechanical, labeled; re-digestion may re-author it later).
            witness = max(c, key=lambda a: len(str(a.object or "")))
            participants: List[str] = []
            keywords: List[str] = []
            for a in c:
                attrs = a.attributes if isinstance(a.attributes, dict) else {}
                for p in attrs.get("participants") or ():
                    if p not in participants:
                        participants.append(p)
                for k in attrs.get("keywords") or ():
                    if k not in keywords and len(keywords) < 12:
                        keywords.append(k)
            idem = f"dedup|{scope}|{owner_id}|{day}|{member_ids[0]}"
            [summary_gid] = system.remember_many(
                [MemoryRecordInput(
                    kind="summary",
                    title=f"Day {day}: {len(c)} near-identical {kind}s consolidated",
                    digest=str(witness.object or ""),
                    keywords=tuple(keywords),
                    participants=tuple(participants),
                    edges=tuple(("summarizes", mid) for mid in member_ids),
                    attributes={
                        "digest_method": "mechanical-dedup-v1",
                        "dedup_members": len(c),
                        "origin_date": day,
                    },
                    provenance={"actor": author, "source": "wake_cue_dedup"},
                )],
                scope=scope, owner_id=owner_id, idempotency_key=idem,
            )
        for mid in member_ids:
            system.close_record(
                mid, kind="supersede", replacement_ids=[summary_gid],
                reason=f"wake-cue dedup by {author}: {len(c)} near-identical "
                       f"{kind}s from {day} consolidated into one day summary",
            )
        formed.append(summary_gid)
    report["formed_summaries"] = formed
    return report


def _closed_assertion_ids(system: Any) -> frozenset:
    from .folds import closure_exclusions

    return closure_exclusions(system.journal, system.current_seq())


# ---------------------------------------------------------------------------
# Phase 4 — journal cold-cut rebuild
# ---------------------------------------------------------------------------

def safe_cut_seq(
    journal: Any,
    scope_pairs: Sequence[Tuple[str, str]],
    *,
    window_limit: int = 512,
    margin: float = 2.0,
) -> int:
    """GLOBAL cut variant: the highest single cut that provably cannot
    change a head recall in ANY searched pair. Bounded by the SPARSEST
    pair (a pair whose whole history must survive forces 0) — correct
    but weak on ladder homes where diary/self pairs are thin while the
    life pair carries the mass. Prefer `safe_cut_seqs` (per-pair) for
    doctoring; this stays for single-pair callers."""
    cuts = safe_cut_seqs(journal, scope_pairs, window_limit=window_limit, margin=margin)
    return min(cuts.values()) if cuts else 0


def safe_cut_seqs(
    journal: Any,
    scope_pairs: Sequence[Tuple[str, str]],
    *,
    window_limit: int = 512,
    margin: float = 2.0,
) -> Dict[Tuple[str, str], int]:
    """PER-PAIR safe cuts: each (scope, owner) keeps at least
    window_limit × margin of its own most recent ATTENTION events above
    its own cut, so every pair's activation/trail fold (which reads
    exactly window_limit scoring events PER PAIR) sees an identical
    window before and after. A pair with a short history gets cut 0
    (nothing cold to cut there) WITHOUT gating the heavy pairs — the
    measured Castor shape: life carries 86k events while diary/self are
    thin; a global cut would be hostage to the thin pairs.

    margin defaults to 2× as drift insurance (a declared tunable, not
    fear: the extra span costs ~window_limit rows per pair, pennies
    against the mass being cut)."""
    from .journal import ATTENTION_KINDS

    keep = max(1, int(int(window_limit) * float(margin)))
    cuts: Dict[Tuple[str, str], int] = {}
    for scope, owner in scope_pairs:
        events = journal.events(scope=scope, owner_id=owner,
                                kinds=sorted(ATTENTION_KINDS), limit=keep)
        if len(events) < keep:
            cuts[(scope, owner)] = 0
            continue
        oldest_kept = min(int(e.seq) for e in events)
        cuts[(scope, owner)] = max(0, oldest_kept - 1)
    return cuts

_COPY_TABLES_FULL = (
    "memj_bindings", "memj_closures", "memj_valence",
    "memj_traces", "memj_snapshots", "memj_selected_counts", "memj_seq",
)


@dataclass(frozen=True)
class _CutStats:
    events_before: int
    events_after: int
    embeddings_nulled: int
    bytes_before: int
    bytes_after: int


def journal_cold_cut(
    src_path: str,
    dst_path: str,
    *,
    cut_seq: int = 0,
    pair_cuts: Optional[Dict[Tuple[str, str], int]] = None,
    archive_ref: str,
    exported_stream_ref: Optional[str] = None,
    null_retired_embeddings: bool = True,
    cut_traces: bool = False,
) -> Dict[str, Any]:
    """Rebuild a home store file with the attention-event mass cold-cut.

    Copies EVERYTHING except cut memj_events rows: `cut_seq` drops rows
    with seq <= cut in EVERY pair; `pair_cuts` (from safe_cut_seqs)
    drops per (scope, owner) — the ladder-honest mode, where a thin
    diary/self pair keeps its whole history while the heavy life pair
    sheds its cold mass. Nulls embeddings on closure-retired triples
    rows when asked (they are outside ranked retrieval already — vectors
    on retired rows are pure cost); writes the compaction record into
    triples_meta; VACUUMs. Operates file-to-file (src opened read-only;
    dst must not exist) — the live-home swap is the runbook's separate,
    gated step.

    The seq axis stays SPARSE-ORIGINAL: surviving rows keep their seqs,
    memj_seq keeps the old high water, so post-cut appends continue
    monotonically and anchors above the cut replay bit-identically.

    `cut_traces=True` (opt-in, measured on Castor: traces+snapshots =
    ~21MB of his 92MB) additionally drops reconstruction traces and
    commit snapshots at or below the HIGHEST cut. Traces are not
    attention inputs — head recall is untouched by construction; what
    degrades is situate()'s moment reconstruction and recall_history
    BELOW the cut, which the archive already serves (the same honest
    label as events). Default False: the conservative shape keeps every
    explanation row in the hot home.
    """
    import os

    if os.path.exists(dst_path):
        raise ValueError(f"journal_cold_cut: destination already exists: {dst_path}")
    if int(cut_seq) < 0:
        raise ValueError(f"journal_cold_cut: cut_seq must be >= 0 (got {cut_seq})")
    if not str(archive_ref or "").strip():
        raise ValueError("journal_cold_cut requires archive_ref — the cold cut is only "
                         "legal with the lossless archive recorded beside it")

    # NOT immutable=1: an immutable open ignores the WAL, silently reading a
    # stale pre-checkpoint view of a live-written home (found by test — the
    # forensic backups didn't hit it because .backup checkpoints). query_only
    # honors the WAL while structurally refusing writes.
    src = sqlite3.connect(src_path)
    src.execute("PRAGMA query_only=ON")
    # Honest size: a live WAL home keeps most bytes in -wal until checkpoint.
    bytes_before = sum(
        os.path.getsize(p) for p in (src_path, src_path + "-wal", src_path + "-shm")
        if os.path.exists(p))
    try:
        # ONE read snapshot for the whole copy (production-audit finding 3):
        # autocommit gives per-statement snapshots, so a writer landing
        # between the memj_seq copy and the events copy could put an event
        # ABOVE the copied high-water — the rebuilt journal would then
        # collide on its first append, forever. BEGIN pins one WAL snapshot;
        # the runbook's door-closed rule stays the posture, this makes it
        # structural.
        src.execute("BEGIN")
        dst = sqlite3.connect(dst_path)
        try:
            # Schema travels verbatim (indexes included).
            for (ddl,) in src.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"
            ).fetchall():
                try:
                    dst.execute(ddl)
                except sqlite3.OperationalError:
                    pass  # auto-created indexes re-create themselves

            # Store truth — full copy; retired embeddings nulled after.
            _copy_table(src, dst, "triples")
            _copy_table(src, dst, "triples_meta")

            embeddings_nulled = 0
            if null_retired_embeddings:
                # Subquery, never a bound IN-list (production-audit finding 1):
                # a doctored home carries ~100k+ closure rows and SQLite caps
                # bind variables at ~32k — the placeholder form crashed at
                # exactly the scale the verb exists for. Copy closures first,
                # then null from dst's own table with ZERO bind variables.
                _copy_table(src, dst, "memj_closures")
                cur = dst.execute(
                    "UPDATE triples SET embedding = NULL "
                    "WHERE embedding IS NOT NULL AND assertion_id IN "
                    "(SELECT assertion_id FROM memj_closures)")
                embeddings_nulled = cur.rowcount

            # memj_closures re-copy below is an OR IGNORE no-op.
            for table in _COPY_TABLES_FULL:
                _copy_table(src, dst, table)

            # Global-cut pair guard (production-audit finding 10): a global
            # cut_seq drops rows in EVERY pair, but safe_cut_seq computes
            # safety only over the pairs the caller enumerated — a ladder
            # home cut with only ("life", owner) in hand would silently
            # erase the thin diary/self pairs' whole history. Refuse unless
            # every pair with history below the cut is explicitly named in
            # pair_cuts (0 = keep whole, deliberate).
            if int(cut_seq) > 0:
                named = set(pair_cuts or {})
                affected = [
                    (str(s), str(o)) for s, o in src.execute(
                        "SELECT DISTINCT scope, owner_id FROM memj_events "
                        "WHERE seq <= ?", (int(cut_seq),)).fetchall()
                ]
                unlisted = sorted(p for p in affected if p not in named)
                if unlisted:
                    raise ValueError(
                        f"journal_cold_cut: global cut_seq={cut_seq} would erase history "
                        f"in pairs not named in pair_cuts: {unlisted} — enumerate every "
                        "pair (0 = keep whole) so no pair is cut by omission")

            events_before = src.execute("SELECT COUNT(*) FROM memj_events").fetchone()[0]
            cols = [r[1] for r in src.execute("PRAGMA table_info(memj_events)")]
            col_list = ", ".join(cols)
            marks = ", ".join("?" for _ in cols)
            for row in src.execute(
                f"SELECT {col_list} FROM memj_events WHERE seq > ?", (int(cut_seq),)
            ):
                dst.execute(f"INSERT OR IGNORE INTO memj_events ({col_list}) VALUES ({marks})", row)
            for (p_scope, p_owner), p_cut in sorted((pair_cuts or {}).items()):
                if int(p_cut) > 0:
                    dst.execute(
                        "DELETE FROM memj_events WHERE scope = ? AND owner_id = ? AND seq <= ?",
                        (str(p_scope), str(p_owner), int(p_cut)))
            events_after = dst.execute("SELECT COUNT(*) FROM memj_events").fetchone()[0]

            traces_dropped = snapshots_dropped = 0
            if cut_traces:
                highest_cut = max([int(cut_seq)] + [int(c) for c in (pair_cuts or {}).values()])
                if highest_cut > 0:
                    traces_dropped = dst.execute(
                        "DELETE FROM memj_traces WHERE seq <= ?", (highest_cut,)).rowcount
                    snapshots_dropped = dst.execute(
                        "DELETE FROM memj_snapshots WHERE seq <= ?", (highest_cut,)).rowcount

            # Seq-counter belt (finding 3's milder sibling): even under one
            # snapshot, keep the invariant explicit — the counter must be at
            # least the highest surviving row seq, or the rebuilt journal's
            # first append collides.
            max_row_seq = dst.execute(
                "SELECT MAX(m) FROM (SELECT MAX(seq) AS m FROM memj_events "
                "UNION ALL SELECT MAX(seq) FROM memj_bindings "
                "UNION ALL SELECT MAX(seq) FROM memj_closures "
                "UNION ALL SELECT MAX(seq) FROM memj_traces "
                "UNION ALL SELECT MAX(seq) FROM memj_snapshots "
                "UNION ALL SELECT MAX(seq) FROM memj_valence)").fetchone()[0] or 0
            dst.execute(
                "UPDATE memj_seq SET value = ? WHERE value < ?",
                (int(max_row_seq), int(max_row_seq)))

            from datetime import datetime, timezone

            compaction = {
                # "at" makes the record self-dating (footprint/health consumers
                # read last_maintenance_at FROM here — file mtimes lie after
                # swap/VACUUM). Entries written before this field exist without
                # it; consumers must treat absence as unknown, never guess.
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "cut_seq": int(cut_seq),
                "pair_cuts": {f"{s}|{o}": int(c) for (s, o), c in sorted((pair_cuts or {}).items())},
                "archive_ref": str(archive_ref),
                "exported_stream_ref": exported_stream_ref,
                "events_dropped": int(events_before - events_after),
                "embeddings_nulled": int(embeddings_nulled),
                "traces_dropped": int(traces_dropped),
                "snapshots_dropped": int(snapshots_dropped),
            }
            # APPEND, never replace (production-audit finding 6): a second
            # cut must not destroy the first cut's archive_ref — the
            # "compaction" key holds the FULL history as a JSON list; the
            # newest entry is the current cut.
            prior_row = dst.execute(
                "SELECT value FROM triples_meta WHERE key='compaction'").fetchone()
            history: List[Dict[str, Any]] = []
            if prior_row:
                try:
                    prior = json.loads(prior_row[0])
                    history = prior if isinstance(prior, list) else [prior]
                except (ValueError, TypeError):
                    history = []
            history.append(compaction)
            dst.execute(
                "INSERT OR REPLACE INTO triples_meta (key, value) VALUES (?, ?)",
                ("compaction", json.dumps(history, sort_keys=True)))
            dst.commit()
            dst.execute("VACUUM")
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()

    bytes_after = os.path.getsize(dst_path)
    return {
        "pass_name": "journal_cold_cut",
        "cut_seq": int(cut_seq),
        "events_before": int(events_before),
        "events_after": int(events_after),
        "embeddings_nulled": int(embeddings_nulled),
        "bytes_before": int(bytes_before),
        "bytes_after": int(bytes_after),
        "archive_ref": str(archive_ref),
        "exported_stream_ref": exported_stream_ref,
    }


def _copy_table(src: sqlite3.Connection, dst: sqlite3.Connection, table: str) -> None:
    cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})")]
    if not cols:
        return
    col_list = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    for row in src.execute(f"SELECT {col_list} FROM {table}"):
        dst.execute(f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({marks})", row)


def verify_cold_cut(src_path: str, dst_path: str) -> Dict[str, Any]:
    """Phase-5 parity checks between the original and the rebuilt file —
    measured, never asserted. Returns {ok, checks: [...]}; every check
    names itself and its numbers so a failed dry run reads exactly."""
    # query_only, not immutable: immutable opens ignore a live home's WAL
    # (stale reads); query_only honors it while refusing writes.
    src = sqlite3.connect(src_path)
    src.execute("PRAGMA query_only=ON")
    dst = sqlite3.connect(dst_path)
    dst.execute("PRAGMA query_only=ON")
    checks: List[Dict[str, Any]] = []

    def check(name: str, ok: bool, **detail: Any) -> None:
        checks.append({"check": name, "ok": bool(ok), **detail})

    def _newest_compaction(con: sqlite3.Connection) -> Dict[str, Any]:
        row = con.execute(
            "SELECT value FROM triples_meta WHERE key='compaction'").fetchone()
        if not row:
            return {}
        try:
            loaded = json.loads(row[0])
        except (ValueError, TypeError):
            return {}
        if isinstance(loaded, list):
            return loaded[-1] if loaded else {}
        return loaded if isinstance(loaded, dict) else {}

    try:
        comp_early = _newest_compaction(dst)
        expected_drop = {
            "memj_traces": int(comp_early.get("traces_dropped") or 0),
            "memj_snapshots": int(comp_early.get("snapshots_dropped") or 0),
        }
        for table in ("triples", "memj_bindings", "memj_closures", "memj_valence",
                      "memj_traces", "memj_snapshots", "memj_selected_counts"):
            a = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            b = dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            drop = expected_drop.get(table, 0)
            check(f"{table}_row_parity", a - drop == b, src=a, dst=b, expected_drop=drop)

        # Global counters preserved exactly (the two-count model's never-
        # decaying half).
        a = dict(src.execute("SELECT record_id, n FROM memj_selected_counts").fetchall())
        b = dict(dst.execute("SELECT record_id, n FROM memj_selected_counts").fetchall())
        check("selected_counts_equal", a == b, diverging=len(set(a.items()) ^ set(b.items())))

        # Compaction record present + honest accounting (newest entry of the
        # append-only history — finding 6).
        comp = _newest_compaction(dst)
        if not comp:
            check("compaction_record", False)
        else:
            ev_src = src.execute("SELECT COUNT(*) FROM memj_events").fetchone()[0]
            ev_dst = dst.execute("SELECT COUNT(*) FROM memj_events").fetchone()[0]
            check("compaction_record", True, **comp)
            check("events_accounting", ev_src - ev_dst == comp["events_dropped"],
                  src=ev_src, dst=ev_dst, recorded_drop=comp["events_dropped"])
            # No surviving event at or below the cut — global and per-pair.
            low = dst.execute("SELECT COUNT(*) FROM memj_events WHERE seq <= ?",
                              (comp["cut_seq"],)).fetchone()[0]
            check("no_events_below_cut", low == 0, below_cut=low)
            for pair_key, p_cut in (comp.get("pair_cuts") or {}).items():
                p_scope, _, p_owner = pair_key.partition("|")
                p_low = dst.execute(
                    "SELECT COUNT(*) FROM memj_events "
                    "WHERE scope = ? AND owner_id = ? AND seq <= ?",
                    (p_scope, p_owner, int(p_cut))).fetchone()[0]
                check(f"no_events_below_pair_cut[{pair_key}]", p_low == 0,
                      below_cut=p_low, pair_cut=p_cut)

        # Seq axis continuity: high water preserved.
        a = src.execute("SELECT value FROM memj_seq").fetchone()
        b = dst.execute("SELECT value FROM memj_seq").fetchone()
        check("seq_high_water", a == b, src=a and a[0], dst=b and b[0])

        # Embedding nulls hit ONLY closure-retired rows (production-audit
        # finding 5: the old nulled_live query was a self-join tautology —
        # the honest metric is dst rows that LOST an embedding src carried).
        retired = {r[0] for r in src.execute("SELECT assertion_id FROM memj_closures")}
        src_embedded = {r[0] for r in src.execute(
            "SELECT assertion_id FROM triples WHERE embedding IS NOT NULL")}
        dst_embedded = {r[0] for r in dst.execute(
            "SELECT assertion_id FROM triples WHERE embedding IS NOT NULL")}
        lost = src_embedded - dst_embedded
        unexpected = len(lost - retired)
        check("nulls_only_on_retired_rows", unexpected == 0,
              nulled_total=len(lost), unexpected=unexpected)
    finally:
        src.close()
        dst.close()

    return {"pass_name": "verify_cold_cut", "ok": all(c["ok"] for c in checks),
            "checks": checks}
