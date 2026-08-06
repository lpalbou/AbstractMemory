"""Archive import: populate a memory graph from a lineage archive
(fork 720 adopted; maintainer process description 2026-07-12).

THE MATERIAL (the maintainer's words): a lineage archive holds dated
markdown — self model, values, purposes, capabilities, relationships,
(semantic) knowledge, emotional significance, protocols, an index of
memories, many verbatims, many experiential notes. The goal is a PROCESS
that builds an entity's memory from those files — run by the OPERATOR, on
the operator's word, never by an agent on its own initiative.

DESIGN RULES (each traceable to a standing ruling):

1. MANIFEST-DRIVEN, never heuristic. The operator writes an import
   manifest naming each file's CATEGORY (below). Guessing what a file "is"
   from its prose would put classification errors into an append-only
   graph; the manifest is the operator's word, and mistakes are the
   operator's to correct BEFORE anything engraves.
2. TWO STAGES, dry-run first. `plan_import` is a PURE read of the archive:
   it produces an ImportPlan (records + warnings + a draft spark + proposed
   appraisals) and writes NOTHING. `apply_import` executes a plan against
   a MemorySystem — idempotent per file (content-hash keys), so a crashed
   import re-runs into the same records.
3. PROVENANCE IS PINNED: every imported record carries
   provenance.source="archive-import", the file's relative path, and its
   sha256 — the fork-720 path+hash rule. The file's DATE (front matter or
   manifest) rides attributes.origin_date; observed_at stays import time
   (append-only truth: the graph observed it now; the CONTENT is dated —
   the same division diary projections use with written_at).
4. IDENTITY IS NOT IMPORTED SIDEWAYS. Values/purposes/capabilities/self
   model files become a DRAFT SPARK (returned for operator review), never
   direct self-scope records — the engram remains the only identity seed
   (create-time contract, c626). History/knowledge/protocols land in LIFE
   scope with inactive bindings (surface on merit, like every formed
   record).
5. FEELINGS ARE PROPOSED, NEVER APPLIED. Emotional-significance material
   becomes a list of proposed appraisals (target, value, reason, source
   file). Valence writes ride their own gated channels; the import tool
   has no appraisal pen.
6. VERBATIMS ARE REFERENCES. Verbatim files map to payload_ref values the
   HOST resolves into its artifact store; the graph gets digests, never a
   second copy of the prose (references-at-rest).

Categories (manifest `category` field):
- "value" | "purpose" | "trait" | "capability" | "self_model" → draft spark
- "history" | "experiential_note" → kind="episode" records
- "knowledge"                      → kind="lesson" records
- "protocol"                       → kind="instruction" records
- "relationship"                   → kind="episode" + participants +
                                      proposed appraisals
- "memory_index"                   → keyword enrichment source (plan-level)
- "verbatim"                       → payload_ref carrier for a record named
                                      by `attach_to` (manifest field)

THE GUARD: this module never walks a directory uninvited — `plan_import`
takes an explicit manifest, and nothing in this package invokes it. Tests
run against synthetic fixtures only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .records import MemoryRecordInput
from .text_tokens import truncation_meta

__all__ = [
    "ArchiveFile",
    "ImportPlan",
    "apply_import",
    "plan_import",
]

_CATEGORIES = frozenset({
    "value", "purpose", "trait", "capability", "self_model",
    "history", "experiential_note", "knowledge", "protocol",
    "relationship", "memory_index", "verbatim",
})
_SPARK_CATEGORIES = frozenset({"value", "purpose", "trait", "capability", "self_model"})
_RECORD_KIND_BY_CATEGORY = {
    "history": "episode",
    "experiential_note": "episode",
    "relationship": "episode",
    "knowledge": "lesson",
    "protocol": "instruction",
}

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ArchiveFile:
    """One manifest entry: the operator's word about one file."""

    path: str                       # relative to the archive root
    category: str
    date: Optional[str] = None      # ISO date; falls back to filename/content
    title: Optional[str] = None
    participants: Tuple[str, ...] = ()   # relationship files: who
    attach_to: Optional[str] = None      # verbatim files: content-key of the record

    def __post_init__(self) -> None:
        cat = str(self.category or "").strip().lower()
        if cat not in _CATEGORIES:
            raise ValueError(
                f"unknown archive category {self.category!r} for {self.path!r} "
                f"(known: {sorted(_CATEGORIES)})")
        object.__setattr__(self, "category", cat)


@dataclass
class ImportPlan:
    """The dry-run product: everything the import WOULD do, nothing done."""

    records: List[MemoryRecordInput] = field(default_factory=list)
    record_keys: List[str] = field(default_factory=list)   # content-hash key per record
    spark_draft: Dict[str, Any] = field(default_factory=dict)
    proposed_appraisals: List[Dict[str, Any]] = field(default_factory=list)
    keyword_enrichment: Dict[str, List[str]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _first_sentences(text: str, cap: int = 480) -> Tuple[str, Optional[Dict[str, Any]]]:
    """The digest prose bounded at `cap`, with the cut recorded out-of-band.

    Headings carry the title (extracted separately) — the digest is prose.
    Framework ADR-0026 §1: the cut is never silent. It shows in the text as a
    bare "…", and it is COUNTED in the returned metadata, which the caller
    hangs on the record's attributes. The counts stay OUT of the digest
    because this string is the ingested record's embedding and keyword
    surface (`canonical_text`): a counted marker's own words would be shared
    by every truncated import and would inflate near-duplicate Jaccard
    between files that have nothing in common. A manifest that also declares
    a verbatim keeps the whole file (payload_ref).
    #[WARNING:TRUNCATION] archive-import digest bounded at `cap` chars
    """
    prose = "\n".join(line for line in str(text or "").splitlines()
                      if not line.lstrip().startswith("#"))
    body = " ".join(prose.split())
    if len(body) <= cap:
        return body, None
    cut = body[:cap]
    dot = cut.rfind(". ")
    kept = cut[: dot + 1] if dot > cap // 2 else cut
    return kept + " …", truncation_meta(len(kept), len(body), unit="prose chars")


def _date_of(entry: ArchiveFile, text: str) -> Optional[str]:
    if entry.date:
        return str(entry.date)
    m = _DATE_RE.search(Path(entry.path).name) or _DATE_RE.search(text[:400])
    return m.group(1) if m else None


def _title_of(entry: ArchiveFile, text: str) -> str:
    if entry.title:
        return str(entry.title)
    m = _HEADING_RE.search(text)
    if m:
        return m.group(1).strip()
    return Path(entry.path).stem.replace("_", " ").replace("-", " ").strip()


def _contained_path(root: Path, rel_path: str, warnings: List[str]) -> Optional[Path]:
    """Resolve a manifest path INSIDE the archive root, or warn and refuse.
    Every read path uses this — the manifest describes THE ARCHIVE; a path
    that escapes (../, absolute) is a manifest error, never read as the
    operator."""
    resolved = (root / str(rel_path or "")).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        warnings.append(
            f"#FALLBACK: {rel_path!r} escapes the archive root — skipped "
            "(manifest paths must be relative and inside the archive)")
        return None
    return resolved


def plan_import(
    archive_root: str,
    manifest: Sequence[ArchiveFile],
    *,
    max_file_bytes: int = 512_000,
) -> ImportPlan:
    """PURE dry run: read the manifest's files under archive_root and build
    the plan. Missing/oversized/unreadable files become warnings, never
    crashes — the operator reviews the plan before anything applies."""
    root = Path(archive_root).expanduser()
    plan = ImportPlan()
    verbatim_refs: Dict[str, str] = {}

    entries = list(manifest or ())
    if not entries:
        raise ValueError("plan_import requires a non-empty manifest — the manifest "
                         "is the operator's word about each file; nothing is guessed")

    # Duplicate manifest entries would form twice under two positions —
    # dedupe by (path, category) loudly.
    seen_entries: set = set()
    deduped: List[ArchiveFile] = []
    for entry in entries:
        key = (entry.path, entry.category)
        if key in seen_entries:
            plan.warnings.append(
                f"#FALLBACK: duplicate manifest entry {entry.path!r} ({entry.category}) — skipped")
            continue
        seen_entries.add(key)
        deduped.append(entry)
    entries = deduped

    # Pass 1: verbatims and memory indexes resolve first so records can
    # reference them regardless of manifest order. Containment applies to
    # EVERY read path and to verbatim refs (they rest in the graph as
    # payload_ref — an escaping ref must never engrave).
    for entry in entries:
        if entry.category == "verbatim":
            if not entry.attach_to:
                plan.warnings.append(f"#FALLBACK: verbatim {entry.path!r} has no attach_to — skipped")
                continue
            if _contained_path(root, entry.path, plan.warnings) is None:
                continue
            verbatim_refs[str(entry.attach_to)] = entry.path
        elif entry.category == "memory_index":
            index_path = _contained_path(root, entry.path, plan.warnings)
            if index_path is None:
                continue
            try:
                index_text = index_path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                plan.warnings.append(f"#FALLBACK: cannot read index {entry.path!r}: {e} — skipped")
                continue
            plan.counts["memory_index"] = plan.counts.get("memory_index", 0) + 1
            # Index lines become keyword enrichment: "<key>: kw1, kw2".
            for line in index_text.splitlines():
                if ":" not in line:
                    continue
                key, _, kws = line.partition(":")
                words = [w.strip() for w in kws.split(",") if w.strip()]
                if key.strip() and words:
                    plan.keyword_enrichment.setdefault(key.strip(), []).extend(words)

    consumed_refs: set = set()
    for entry in entries:
        if entry.category in ("verbatim", "memory_index"):
            continue
        file_path = _contained_path(root, entry.path, plan.warnings)
        if file_path is None:
            continue
        try:
            raw = file_path.read_bytes()
        except OSError as e:
            plan.warnings.append(f"#FALLBACK: cannot read {entry.path!r}: {e} — skipped")
            continue
        if len(raw) > int(max_file_bytes):
            plan.warnings.append(
                f"#FALLBACK: {entry.path!r} is {len(raw)} bytes (> {max_file_bytes}) — skipped; "
                "split the file or raise max_file_bytes explicitly")
            continue
        text = raw.decode("utf-8", errors="replace")
        digest_hash = _sha256(raw)
        date = _date_of(entry, text)
        title = _title_of(entry, text)
        plan.counts[entry.category] = plan.counts.get(entry.category, 0) + 1

        if entry.category in _SPARK_CATEGORIES:
            bucket = plan.spark_draft.setdefault(entry.category, [])
            bucket.append({
                "title": title, "text": text.strip(), "date": date,
                "path": entry.path, "sha256": digest_hash,
            })
            continue

        if entry.category == "relationship":
            if not entry.participants:
                plan.warnings.append(
                    f"#FALLBACK: relationship {entry.path!r} names no participants — "
                    "imported as a plain episode")
            # Emotional significance: "feel: <target> <+/-N> <reason>"
            # markers (anywhere in a line) become PROPOSED appraisals —
            # never applied here (valence rides its own gated channels).
            for line in text.splitlines():
                m = re.search(r"feel:\s*(\S+)\s+([+-]?\d+)\s*(.*)", line, re.IGNORECASE)
                if m:
                    plan.proposed_appraisals.append({
                        "target": m.group(1), "value": int(m.group(2)),
                        "reason": m.group(3).strip() or f"archived feeling from {entry.path}",
                        "source_path": entry.path,
                    })

        kind = _RECORD_KIND_BY_CATEGORY[entry.category]
        content_key = f"archive|{entry.path}|{digest_hash[:16]}"
        keywords = tuple(plan.keyword_enrichment.get(entry.path, ())) or \
            tuple(plan.keyword_enrichment.get(title, ()))
        digest, digest_truncation = _first_sentences(text)
        attributes: Dict[str, Any] = {"seeded_from": "archive-import"}
        if date:
            attributes["origin_date"] = date
        if digest_truncation:
            attributes["_truncation"] = digest_truncation
        ref_key = entry.path if entry.path in verbatim_refs else (
            title if title in verbatim_refs else None)
        if ref_key is not None:
            consumed_refs.add(ref_key)
        record = MemoryRecordInput(
            kind=kind,
            title=title,
            digest=digest,
            keywords=keywords,
            participants=tuple(entry.participants),
            payload_ref=verbatim_refs.get(ref_key) if ref_key else None,
            attributes=attributes,
            provenance={
                "source": "archive-import",
                "actor": "operator",
                "archive_path": entry.path,
                "archive_sha256": digest_hash,
            },
        )
        plan.records.append(record)
        plan.record_keys.append(content_key)

    # A verbatim whose attach_to matched nothing is a manifest typo — say so
    # (silently unconsumed references are how transcripts get lost).
    for attach_key in sorted(set(verbatim_refs) - consumed_refs):
        plan.warnings.append(
            f"#FALLBACK: verbatim attach_to {attach_key!r} matched no imported record — "
            "check the manifest (attach_to must equal a record's path or title)")

    if plan.spark_draft:
        plan.warnings.append(
            "spark draft assembled from "
            f"{sorted(plan.spark_draft)} — REVIEW REQUIRED: identity seeds ride the "
            "engram at entity creation (c626), never a direct import")
    return plan


def apply_import(
    system: Any,
    plan: ImportPlan,
    *,
    scope: str,
    owner_id: str,
    batch_size: int = 20,
) -> Dict[str, Any]:
    """Execute a reviewed plan: one remember_many call PER RECORD, keyed by
    the record's own content key — identity is a pure function of file
    content, so crashed/partial/incremental/reordered re-runs all land on
    the same records (supplied-id dedup). Spark draft and proposed
    appraisals are RETURNED UNTOUCHED: the operator applies identity via
    the engram and feelings via the gated valence channels, never through
    this tool."""
    if not plan.records:
        return {"record_ids": [], "batches": 0,
                "spark_draft": dict(plan.spark_draft),
                "proposed_appraisals": list(plan.proposed_appraisals),
                "warnings": list(plan.warnings)}
    del batch_size  # kept in the signature for compatibility; identity is per-file now
    record_ids: List[str] = []
    # PER-FILE IDENTITY (adversary find, 2026-07-12): record ids must be a
    # pure function of FILE CONTENT alone. Batch-derived keys made identity
    # depend on batch COMPOSITION — adding/removing one file (the normal
    # incremental-archive case), reordering, or changing batch_size shifted
    # chunk boundaries and re-minted every id → silent duplicates in a
    # never-purge graph. One remember_many call per record, keyed by the
    # record's own content key: manifest growth, reorder, and re-runs all
    # land on the same ids; only changed file BYTES mint new records (and
    # the old rows stand — append-only; the operator closes them if wanted).
    for content_key, record in sorted(zip(plan.record_keys, plan.records),
                                      key=lambda kv: kv[0]):
        record_ids.extend(system.remember_many(
            [record], scope=scope, owner_id=owner_id, idempotency_key=content_key))
    return {"record_ids": record_ids, "batches": len(record_ids),
            "spark_draft": dict(plan.spark_draft),
            "proposed_appraisals": list(plan.proposed_appraisals),
            "warnings": list(plan.warnings)}
