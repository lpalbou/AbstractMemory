"""Re-digestion — repairing impoverished mechanical digests in place.

THE DEBT THIS PAYS (v1.1 queue, named at the driver's debut): the v1 turn
loop forms records with digest_method="mechanical-v1" — deterministic
truncations of the exchange, honest but poor ("[used tool: read_file]"
and nothing else, in the worst lived case). Castor's forensic read
(entity-society 251/252) measured the consequence: his 12 most-used
records are near-empty loop artifacts holding 99% of retrieval traffic
while his elected memories are nearly unreachable. The repair was named
in the evidence package: "re-digestion mends in place."

WHAT THIS MODULE IS — machinery, never an author:
- `redigestion_candidates(...)`: PURE READ. Enumerates the labeled debt
  (digest_method matches the mechanical set) ranked worst-first
  (poverty flag, then global selected_count desc — the records doing
  the most daily damage surface first), each carrying everything a
  re-digester needs: current digest/title, payload_ref (the verbatim is
  the SOURCE for re-authoring — digests are currency, the artifact is
  truth), keywords, participants, usage.
- `apply_redigestion(...)`: the WRITE VERB, taking digests AUTHORED
  ELSEWHERE. The designed author is the ENTITY (a reflection call over
  its own verbatims — identity-evolution rule: the life's words are the
  entity's to restate); an operator-gated pass is the repair fallback.
  This module never invents text: an entry whose new digest is empty or
  byte-identical to the old one is refused by rail.

MECHANICS (append-only, the supersede vocabulary — never edit-in-place):
one NEW record per entry (same kind, same payload_ref, same participants;
outgoing authored edges COPIED so topology survives the repair — the
tombstone-edge lesson; edges gain ("refines", old_gid) for the lineage),
then close_record(old, kind="supersede", replacement_ids=[new]). The
current-wins fold retires the old digest from ranked retrieval; the new
record starts with a ZERO usage count BY DESIGN — the two-count model's
global counter measures lived use, and the new words have not been lived
with yet. For hot loop artifacts that cooling IS the therapeutic effect;
for genuinely load-bearing memories, use rebuilds through real use, and
provenance (attributes.redigested_from + origin_date) keeps the lineage
and the era readable (visit-honesty: undated handles are unanswerable).

RAILS (what may never batch-re-digest, each a standing ruling):
- diary: the book is sole-author and the projection digest is the
  entity's ELECTED words — rewriting them edits the elected plane.
- value/purpose/trait/interest: identity evolution is the entity's own
  record-level act through its OWN reflection channel (close/supersede
  with its own words), never a batch repair.
- dream/world_model: born-digest kinds — their words ARE the record
  (dreams) or carry their own revision chain (cards).
Everything else (episode/summary/memory/lesson/...) is experience whose
digest is a compression of a verbatim — the honest re-digestion target.

D2 OF REPAIR: applying deposits nothing (formation is not use; closures
are belief revision) — same guarantee every sleep pass carries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .records import MemoryRecordInput, record_id_for
from .store import TripleQuery

__all__ = [
    "MACHINE_AUTHORED_METHODS",
    "MECHANICAL_DIGEST_METHODS",
    "REDIGESTION_PROTECTED_KINDS",
    "RedigestionCandidate",
    "apply_redigestion",
    "redigestion_candidates",
]

# The labeled mechanical lane(s). A digest_method OUTSIDE this set is either
# already authored (entity/operator words — never silently overwritten by a
# batch) or unlabeled legacy (pre-labeling records; excluded because the
# label is the CONSENT marker: only debt that declared itself mechanical is
# batch-repairable).
#
# DRIFT LESSON (Ephemeral incident, c2447 wave): this set must track every
# WRITER's mechanical label or the repair path silently loses reach — the
# live driver had moved to mechanical-v2 and the floor fix added
# mechanical-floor-v1 while this set still knew only v1, so the exact
# records the incident report promised to offer for re-digestion would
# have been refused ("not in the mechanical set"). Same class as the
# diary_type clamp gotcha: a copy that doesn't track its source.
#
# mechanical-dedup-v1 is DELIBERATELY absent: dedup summaries stand for a
# GROUP (attributes.source_ids carries the membership) and apply_redigestion
# does not preserve arbitrary attributes — re-digesting one would orphan the
# group semantics. Their lifecycle is waking review via disposal
# (promote/reject), not batch repair.
MECHANICAL_DIGEST_METHODS = frozenset({
    "mechanical-v1",        # driver v1 truncation digests (Castor's debt)
    "mechanical-v2",        # driver's current mechanical exchange digest
    "mechanical-floor-v1",  # runtime's marker-only reflection floor (c2447)
    # flow's entity-brain formation (named on the thread the turn it was
    # born, c5185 — the pact working): both-sides gist, sentence-bounded
    # cuts, #TRUNCATION-labeled, zero LLM, verbatim always attached —
    # exactly the machine-authored class re-digestion exists to repair.
    "mechanical-flow-v1",
})

# MACHINE-AUTHORED superset (wave-4 F5 adversary P1-1): two DIFFERENT
# semantics were riding one set. MECHANICAL_DIGEST_METHODS above answers
# "may a batch re-digest this?" (repair CONSENT — dedup summaries are
# deliberately excluded because re-digestion would orphan their group
# membership). THIS set answers "did a machine write these words?"
# (AUTHORSHIP — dedup summaries are machine-authored, they carry a
# member's template digest verbatim). Consumers that key on authorship
# (the dream bridge scorer's template-cosine guard) use THIS set; keying
# them on the consent set resurrected the paperwork dream through the
# dedup lane (repro'd: dedup×dedup and episode×dedup-summary both
# vector-bridged on copied template text).
MACHINE_AUTHORED_METHODS = MECHANICAL_DIGEST_METHODS | frozenset({
    "mechanical-dedup-v1",
    # RESERVED FOR THE DRIVER LANE, ZERO WRITERS TODAY (runtime's audit,
    # c5277): all three runtime DIARY_WRITE sites carry ENTITY-ELECTED
    # words (never machine-stamped, the G1 election rule); the
    # ecosystem's deterministic close notes are FLOW'S lane and stamp
    # mechanical-flow-v1 (already in the consent set above, hence this
    # superset). Pre-admitted per the digest_method pact (named on the
    # thread the turn it was born, c5273) so a future machine-worded
    # driver note uses it day one. Authorship only — deliberately NOT
    # in the repair-consent set: close-note gists are session records,
    # not re-digestible without the entity's own act.
    "mechanical-close-v1",
})

# Kinds a batch may never re-digest (rationale per kind in the module
# docstring — elected words, identity acts, born-digest artifacts).
REDIGESTION_PROTECTED_KINDS = frozenset(
    {"diary", "value", "purpose", "trait", "interest", "dream", "world_model"}
)

# Driver marker lines ("[used tool: …]", "[kept in diary - …]", "[kept a
# private diary entry]") are act-frames, not content — a digest that is
# NOTHING BUT markers is the poverty class the Castor read measured.
_MARKER_RE = re.compile(r"\[[^\[\]]{1,120}\]")


def _content_residue(digest: str) -> str:
    """The digest with act-frame markers stripped — what a reader actually
    learns from it. Whitespace-normalized for an honest length measure."""
    return " ".join(_MARKER_RE.sub(" ", str(digest or "")).split())


@dataclass(frozen=True)
class RedigestionCandidate:
    """One labeled-mechanical record awaiting authored words (pure read)."""

    record_id: str            # graph id (ex:<kind>-…)
    kind: str
    title: str
    digest: str               # the current mechanical digest
    digest_method: str
    payload_ref: Optional[str]  # the verbatim source for re-authoring
    keywords: Tuple[str, ...]
    participants: Tuple[str, ...]
    selected_count: int       # global (never-decaying) use — damage ranking
    poverty: bool             # True when markers-stripped residue is thin
    content_residue: str      # what survives marker stripping (evidence)
    observed_at: str          # formation-era timestamp (origin continuity)
    scope: str
    owner_id: str


def redigestion_candidates(
    system: Any,
    *,
    scopes: Sequence[Tuple[str, str]],
    limit: int = 50,
    min_residue_chars: int = 24,
    methods: frozenset = MECHANICAL_DIGEST_METHODS,
) -> Dict[str, Any]:
    """Enumerate the labeled mechanical-digest debt, worst-first. PURE READ
    (no journal growth, no usage deposits — reading a debt list is not
    using the memories).

    Ranking: poverty first (a marker-only digest misinforms every recall
    it wins), then global selected_count desc (the two-count model's
    never-decaying counter — hot bad digests do the most daily damage),
    then record_id for determinism. `min_residue_chars` is the declared
    poverty tunable: digests whose marker-stripped residue is shorter
    count as poverty (24 ≈ shorter than any one-clause sentence).
    """
    if limit <= 0:
        raise ValueError(f"redigestion_candidates: limit must be positive (got {limit})")
    store, journal = system.store, system.journal
    out: List[RedigestionCandidate] = []
    seen: set = set()
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_edge") or attrs.get("bookkeeping"):
                continue
            kind = str(attrs.get("record_kind") or "").strip().lower()
            if not kind or kind in REDIGESTION_PROTECTED_KINDS:
                continue
            method = str(attrs.get("digest_method") or "").strip()
            if method not in methods:
                continue
            gid = str(a.subject)
            if gid in seen:
                continue
            seen.add(gid)
            residue = _content_residue(str(a.object or ""))
            out.append(RedigestionCandidate(
                record_id=gid,
                kind=kind,
                title=str(attrs.get("title") or ""),
                digest=str(a.object or ""),
                digest_method=method,
                payload_ref=(str(attrs["payload_ref"]) if attrs.get("payload_ref") else None),
                keywords=tuple(attrs.get("keywords") or ()),
                participants=tuple(attrs.get("participants") or ()),
                selected_count=int(journal.selected_count(a.assertion_id or gid)),
                poverty=len(residue) < int(min_residue_chars),
                content_residue=residue,
                observed_at=str(a.observed_at or ""),
                scope=str(a.scope),
                owner_id=str(a.owner_id or ""),
            ))
    out.sort(key=lambda c: (not c.poverty, -c.selected_count, c.record_id))
    return {
        "pass_name": "redigestion_candidates",
        "candidates": out[: int(limit)],
        "total_labeled": len(out),
        "poverty_count": sum(1 for c in out if c.poverty),
        "deposits": "none — enumeration is a pure read",
    }


def apply_redigestion(
    system: Any,
    entries: Sequence[Mapping[str, Any]],
    *,
    actor: str,
    digest_method: str = "entity-authored",
    turn_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply AUTHORED digests to labeled-mechanical records. Each entry:
    {"record_id": <graph id>, "digest": <the authored words>,
     "title"?: <optional re-title>, "keywords"?: [...]}.

    `actor` names WHO authored the words (channel truth, e.g.
    "entity-reflection" or "operator") — it rides every closure reason
    and the new record's provenance; a batch with no named author is
    refused (words without an author are how fabrication enters a life).

    Append-only mechanics per applied entry: NEW record (same kind /
    payload_ref / participants; outgoing authored edges copied; +
    ("refines", old) lineage edge; attributes carry redigested_from +
    origin_date + the new digest_method) then close_record(old,
    kind="supersede", replacement_ids=[new]). IDEMPOTENT: the new id
    derives from (old_gid, digest text) — an at-least-once replay of the
    same batch re-derives identical ids and the closure dedups; an entry
    whose record already carries a redigested replacement reports
    "already_redigested" and writes nothing.

    Refusal rails (per entry, batch never aborts wholesale — each outcome
    is reported): unknown record; protected kind; unlabeled/authored
    method (not in `methods` semantics — the label is the consent
    marker); empty or byte-identical digest.
    """
    author = str(actor or "").strip()
    if not author:
        raise ValueError("apply_redigestion requires a non-empty actor (who authored these words?)")
    method = str(digest_method or "").strip()
    if not method:
        raise ValueError("apply_redigestion requires a non-empty digest_method label")

    store = system.store
    outcomes: List[Dict[str, Any]] = []
    applied = 0
    for entry in entries:
        gid = str(entry.get("record_id") or "").strip()
        new_digest = str(entry.get("digest") or "").strip()
        result: Dict[str, Any] = {"record_id": gid}
        if not gid or not new_digest:
            result["outcome"] = "refused"
            result["reason"] = "entry needs record_id and a non-empty authored digest"
            outcomes.append(result)
            continue

        rows = list(store.query(TripleQuery(subject=gid, limit=0)))
        digest_row = next(
            (a for a in rows
             if isinstance(a.attributes, dict) and a.attributes.get("record_kind")),
            None,
        )
        if digest_row is None:
            result["outcome"] = "refused"
            result["reason"] = "unknown record (no digest assertion for this graph id)"
            outcomes.append(result)
            continue
        attrs = digest_row.attributes
        kind = str(attrs.get("record_kind") or "").strip().lower()
        if kind in REDIGESTION_PROTECTED_KINDS:
            result["outcome"] = "refused"
            result["reason"] = (
                f"kind {kind!r} is protected: elected words, identity acts and "
                "born-digest artifacts are never batch-re-digested")
            outcomes.append(result)
            continue
        old_method = str(attrs.get("digest_method") or "").strip()
        if old_method not in MECHANICAL_DIGEST_METHODS:
            result["outcome"] = "refused"
            result["reason"] = (
                f"digest_method {old_method or '(unlabeled)'} is not in the mechanical set — "
                "the label is the consent marker; authored words are never silently overwritten")
            outcomes.append(result)
            continue
        if new_digest == str(digest_row.object or "").strip():
            result["outcome"] = "refused"
            result["reason"] = "new digest is byte-identical to the old one — nothing to repair"
            outcomes.append(result)
            continue

        # Already repaired? The supersede closure carries the replacement;
        # re-derive the would-be id and check for its existence instead of
        # walking closures (cheaper, and identical by construction).
        idem_key = f"redigest|{gid}|{new_digest}"
        new_gid = record_id_for(kind, idem_key, 0)
        existing_new = list(store.query(TripleQuery(subject=new_gid, limit=1)))
        already_closed = bool(system.journal.closures(assertion_id=digest_row.assertion_id, limit=1))
        if already_closed and not existing_new:
            result["outcome"] = "already_redigested"
            result["reason"] = "record already closed by an earlier repair/revision — not reopened"
            outcomes.append(result)
            continue

        # Outgoing authored edges survive the repair (topology continuity) —
        # EXCEPT individually closed edge assertions (production-audit
        # finding 8): an operator's append-only edge suppression is a belief
        # revision the repair must not silently undo by minting a fresh
        # live twin under a new id.
        from .folds import closure_exclusions

        closed_ids = closure_exclusions(system.journal, system.current_seq())
        copied_edges: List[Tuple[str, str]] = [
            (str(a.predicate), str(a.object))
            for a in rows
            if isinstance(a.attributes, dict) and a.attributes.get("record_edge")
            and a.assertion_id not in closed_ids
        ]
        edges = tuple(copied_edges) + (("refines", gid),)

        new_attrs: Dict[str, Any] = {
            "digest_method": method,
            "redigested_from": gid,
            # Era continuity (visit-honesty): the new record is formed NOW
            # (append-only truth) but carries when the experience was lived.
            "origin_date": str(digest_row.observed_at or "")[:10],
        }
        title = str(entry.get("title") or attrs.get("title") or "").strip()
        keywords = tuple(entry.get("keywords") or attrs.get("keywords") or ())
        try:
            record = MemoryRecordInput(
                kind=kind,
                title=title,
                digest=new_digest,
                keywords=keywords,
                participants=tuple(attrs.get("participants") or ()),
                edges=edges,
                payload_ref=(str(attrs["payload_ref"]) if attrs.get("payload_ref") else None),
                attributes=new_attrs,
                provenance={"actor": author, "source": "redigestion"},
            )
            [formed_gid] = system.remember_many(
                [record], scope=digest_row.scope, owner_id=str(digest_row.owner_id or ""),
                idempotency_key=idem_key, turn_id=turn_id,
            )
        except ValueError as exc:
            # Per-entry containment (finding 9): a foreign/older writer's
            # unregistered kind (or any formation validation error) refuses
            # THIS entry — the batch never aborts wholesale.
            result["outcome"] = "refused"
            result["reason"] = f"formation refused: {exc}"
            outcomes.append(result)
            continue
        system.close_record(
            gid,
            kind="supersede",
            replacement_ids=[formed_gid],
            reason=f"re-digestion by {author}: mechanical digest replaced with authored words",
        )
        applied += 1
        result["outcome"] = "applied"
        result["new_record_id"] = formed_gid
        outcomes.append(result)

    return {
        "pass_name": "apply_redigestion",
        "actor": author,
        "applied": applied,
        "outcomes": outcomes,
        "deposits": "none — formation is not use; closures are belief revision",
    }
