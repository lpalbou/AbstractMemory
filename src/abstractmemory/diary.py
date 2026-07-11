"""Diary conventions: the hash chain, chain verification, open questions.

One task (split from records.py under the 600-line rule — this module is
the definition home; records.py re-exports the chain helpers for
compatibility): everything the engine owns about kind="diary" records
beyond formation validation. The dual-plane split (a2a 0003) stands: the
runtime's BOOK is the attested original; these records are the MEMORY of
the book (or owner-direct entries where no book exists).

QUESTIONS AS AUTONOMY DRIVERS (maintainer round 4): "all the unanswered
questions... and also the resolved questions; those are also drivers for
autonomy." diary_type="question" is first-class; resolution is append-only
and mirrors heal/break — an ANSWERING entry references the question via
attributes.answers (the question's graph record id or its book entry_id).
Resolved questions stay retrievable: "I wondered, then I learned."
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from .store import TripleQuery

__all__ = ["diary_entry_hash", "open_ideas", "open_problems", "open_questions", "verify_diary_chain"]

# Binding lifecycles that mean "still incubating" for an idea entry (the
# formation default is inactive_candidate; reviewed = seen, undecided).
_INCUBATING_LIFECYCLES = frozenset({"inactive_candidate", "reviewed"})


def diary_entry_hash(title: str, digest: str, observed_at: str) -> str:
    """Content hash for one diary entry (identity wave §7): sha256 over the
    entry's own title + digest + stored observed_at. The chain property is
    conventional: each entry's attributes.prev_entry_hash names the previous
    entry's entry_hash (the runtime owns write discipline; the engine owns
    the convention + verification)."""
    payload = f"{str(title or '')}\n{str(digest or '')}\n{str(observed_at or '')}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_diary_chain(store: Any, *, scope: str, owner_id: str) -> Dict[str, Any]:
    """Audit the (scope, owner) diary chain: recompute every entry's content
    hash and check each prev_entry_hash pointer against its predecessor.
    Returns {"intact": bool, "break_at": Optional[record_id], "entries": n}.
    break_at names the FIRST entry whose own hash or back-pointer fails
    (chain order: observed_at, then record_id — the formation clock is the
    chain axis).

    SCOPE OF THE CONVENTION (dual-plane split, a2a 0003): the
    entry_hash/prev_entry_hash chain applies ONLY when the WRITER supplies
    prev_entry_hash — i.e. owner-direct writes where no book exists.
    Book PROJECTIONS deliberately do NOT chain here: their attestation
    plane is the runtime's HashChainedLedgerStore, referenced via
    attributes.entry_id (a second, weaker chain over gists would invite
    confusion). "Nothing claimed, nothing broken": entries without
    prev_entry_hash make no chain claim and fail nothing; a fully
    unchained (all-projection) diary reports intact."""
    rows = [a for a in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0))
            if isinstance(a.attributes, dict) and a.attributes.get("record_kind") == "diary"]
    rows.sort(key=lambda a: ((a.observed_at or ""), a.assertion_id or ""))
    prev_hash: Optional[str] = None
    for a in rows:
        attrs = a.attributes
        claimed = attrs.get("entry_hash")
        if claimed is not None:
            recomputed = diary_entry_hash(str(attrs.get("title") or ""), str(a.object or ""),
                                          str(a.observed_at or ""))
            if recomputed != str(claimed):
                return {"intact": False, "break_at": a.subject, "entries": len(rows)}
        pointer = attrs.get("prev_entry_hash")
        if pointer is not None and str(pointer or "") != (prev_hash or ""):
            return {"intact": False, "break_at": a.subject, "entries": len(rows)}
        prev_hash = str(claimed) if claimed is not None else prev_hash
    return {"intact": True, "break_at": None, "entries": len(rows)}


def open_ideas(
    store: Any, *, scope: str, owner_id: str, limit: int = 100,
    journal: Any = None,
) -> List["Any"]:
    """The entity's incubating ideas (wake reason for the heartbeat, like
    open_questions): diary records with diary_type="idea" that are still
    INCUBATING. With a `journal`, incubation is read from the folded binding
    lifecycle — inactive_candidate/reviewed count as incubating; parked
    (rejected) and matured (promoted) are excluded, as are closed/hidden
    entries. journal=None → ALL idea entries, folds bypassed (layer-1 store
    truth; documented v1 read). Parked and matured ideas stay retrievable
    as ordinary records regardless — this helper only computes the open
    set. Oldest first, bounded by `limit` after folding."""
    rows = [a for a in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0))
            if isinstance(a.attributes, dict)
            and a.attributes.get("record_kind") == "diary"
            and a.attributes.get("diary_type") == "idea"]

    if journal is not None:
        from .folds import binding_states, closure_exclusions  # local: folds stay optional

        as_of = journal.current_seq()
        _states, hidden, _active = binding_states(store, journal, [(scope, owner_id)], as_of)
        excluded = closure_exclusions(journal, as_of) | hidden
        lifecycle_of = {b.record_id: b.lifecycle
                        for b in journal.bindings(scope=scope, owner_id=owner_id,
                                                  fold=True, until_seq=as_of)}
        rows = [a for a in rows
                if a.assertion_id not in excluded
                and lifecycle_of.get(a.subject, "inactive_candidate") in _INCUBATING_LIFECYCLES]

    rows.sort(key=lambda a: ((a.observed_at or ""), a.assertion_id or ""))
    return rows[: max(0, int(limit))] if limit and int(limit) > 0 else rows


def _open_unresolved(
    store: Any, *, scope: str, owner_id: str, diary_type: str, ref_attr: str,
    limit: int, journal: Any,
) -> List["Any"]:
    """Shared fold for the unresolved wake-reason reads (questions/problems):
    diary entries of `diary_type` that no other diary entry references via
    `ref_attr` (the entry's graph record id OR its book entry_id — both
    namespaces are honest references). Oldest first (the longest-standing
    one leads), bounded by `limit` after folding.

    FOLDING (honest v1): when a `journal` is supplied, closure and hidden-
    binding folds apply — a retracted or hidden entry is not "open".
    Without a journal this is a LAYER-1 read (store truth only, folds
    bypassed); pass the journal when belief-state matters. Resolved entries
    stay retrievable as ordinary diary records — this computes the OPEN
    set only."""
    rows = [a for a in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0))
            if isinstance(a.attributes, dict) and a.attributes.get("record_kind") == "diary"]

    excluded: frozenset = frozenset()
    if journal is not None:
        from .folds import binding_states, closure_exclusions  # local: folds imports stay optional

        as_of = journal.current_seq()
        _states, hidden, _active = binding_states(store, journal, [(scope, owner_id)], as_of)
        excluded = closure_exclusions(journal, as_of) | hidden

    resolved_refs: set = set()
    for a in rows:
        ref = a.attributes.get(ref_attr)
        if isinstance(ref, str) and ref.strip():
            resolved_refs.add(ref.strip())

    out = []
    for a in rows:
        attrs = a.attributes
        if attrs.get("diary_type") != diary_type:
            continue
        if a.assertion_id in excluded:
            continue
        refs = {a.subject, str(attrs.get("entry_id") or "").strip()}
        refs.discard("")
        if refs & resolved_refs:
            continue
        out.append(a)
    out.sort(key=lambda a: ((a.observed_at or ""), a.assertion_id or ""))
    return out[: max(0, int(limit))] if limit and int(limit) > 0 else out


def open_questions(
    store: Any, *, scope: str, owner_id: str, limit: int = 100,
    journal: Any = None,
) -> List["Any"]:
    """The entity's standing CURIOSITY: diary_type="question" entries that
    no other diary entry answers (attributes.answers). Resolved questions
    stay retrievable ("I wondered, then I learned"). Fold semantics:
    _open_unresolved."""
    return _open_unresolved(store, scope=scope, owner_id=owner_id,
                            diary_type="question", ref_attr="answers",
                            limit=limit, journal=journal)


def open_problems(
    store: Any, *, scope: str, owner_id: str, limit: int = 100,
    journal: Any = None,
) -> List["Any"]:
    """The entity's standing ISSUES (maintainer round 6): something WRONG
    needing a fix — distinct from a question's curiosity, likely a
    different emotional weight and wake priority. diary_type="problem"
    entries that no other diary entry resolves (attributes.resolves).
    Resolved problems stay retrievable ("I hit it, then I fixed it").
    Fold semantics: _open_unresolved."""
    return _open_unresolved(store, scope=scope, owner_id=owner_id,
                            diary_type="problem", ref_attr="resolves",
                            limit=limit, journal=journal)
