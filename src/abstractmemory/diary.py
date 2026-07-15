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

PROSPECTIVE MEMORY (maintainer acceptance 2026-07-13, "it completes the
system for pending questions and the need to resolve them but goes beyond
— it's a larger set"): diary_type="commitment" is the entity's OWN
remembered promise ("next time I talk to Ada, ask about her paper").
Nothing executes it — open_commitments lists the standing set (fulfillment
is append-only via attributes.fulfills, mirroring answers/resolves) and
triggered_commitments SURFACES the ones whose elected trigger matches the
current stimulus (person appears, topic matches, date passes) so the
entity can keep its word or consciously let it go. The lived failure this
repairs: visit commitments died at the next generic wake cue.
"""

from __future__ import annotations

import hashlib
import warnings as _warnings
from typing import Any, Dict, List, Optional

from .journal_common import normalize_iso_ts
from .store import TripleQuery
from .text_tokens import TOKEN_RE, fold_text

__all__ = [
    "diary_entry_hash",
    "open_commitments",
    "open_ideas",
    "open_problems",
    "open_questions",
    "triggered_commitments",
    "verify_diary_chain",
]

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


def open_commitments(
    store: Any, *, scope: str, owner_id: str, limit: int = 100,
    journal: Any = None,
) -> List["Any"]:
    """The entity's standing PROMISES (prospective memory): diary_type=
    "commitment" entries that no other diary entry fulfills
    (attributes.fulfills — the commitment's graph record id or its book
    entry_id, mirroring answers/resolves). Fulfilled commitments stay
    retrievable ("I promised, then I kept my word"). Like the question/
    problem reads, this is a wake-reason surface: "do I have open
    commitments?" is a reason to wake. Fold semantics: _open_unresolved."""
    return _open_unresolved(store, scope=scope, owner_id=owner_id,
                            diary_type="commitment", ref_attr="fulfills",
                            limit=limit, journal=journal)


def _trigger_matches(
    trigger: Dict[str, Any], *,
    stimulus_participants: frozenset,
    cue_tokens: frozenset,
    now_norm: Optional[str],
    due_warnings: List[str],
    record_id: str,
) -> List[str]:
    """Match ONE commitment's elected trigger against the current stimulus.
    Returns kind-prefixed matched tokens ("participant:person:ada",
    "keyword:paper", "due:<canonical-iso>") — empty when nothing matches.

    - participants: exact stripped-string intersection with the stimulus
      (the run_participants_channel convention — identity strings are
      opaque, never tokenized).
    - keywords: every folded word of the elected keyword must appear in
      the folded cue-text tokens (case/accent-insensitive word match via
      text_tokens.fold_text; NO length floor — the recall floor is a
      stopword surrogate for free text, wrong for the entity's own
      deliberately elected trigger terms like "gpu").
    - due_at: canonical-ISO lexicographic compare (the WAIT_UNTIL
      invariant) against the CALLER-supplied now; now=None means due
      triggers never fire (the engine never reads the clock). An
      unparseable stored due_at degrades that channel only (collected
      into due_warnings — aged data must not kill the read).
    Shapes follow the participants channel's strictness: list/tuple
    values only; anything else contributes nothing.
    """
    matched: List[str] = []

    raw_participants = trigger.get("participants")
    if isinstance(raw_participants, (list, tuple)):
        wanted = {str(p).strip() for p in raw_participants if str(p or "").strip()}
        for p in sorted(wanted & stimulus_participants):
            matched.append(f"participant:{p}")

    raw_keywords = trigger.get("keywords")
    if isinstance(raw_keywords, (list, tuple)) and cue_tokens:
        for kw in raw_keywords:
            kw_text = str(kw or "").strip()
            if not kw_text:
                continue
            kw_tokens = TOKEN_RE.findall(fold_text(kw_text))
            if kw_tokens and all(t in cue_tokens for t in kw_tokens):
                matched.append(f"keyword:{kw_text}")

    raw_due = trigger.get("due_at")
    if now_norm is not None and isinstance(raw_due, str) and raw_due.strip():
        try:
            due_norm = normalize_iso_ts(raw_due)
        except ValueError:
            due_warnings.append(f"{record_id} due_at={raw_due!r}")
        else:
            if due_norm <= now_norm:
                matched.append(f"due:{due_norm}")

    return matched


def _render_commitment_line(entry: Any, matched: List[str]) -> str:
    """One presentation line for a triggered commitment. Dated handles are
    a visit-honesty requirement (undated handles make "when did I promise
    this?" unanswerable), so the line leads with the election date. In the
    [matched: ...] tail, participant tokens show their bare identity value
    (already self-namespaced — "person:ada"); keyword tokens keep their
    kind prefix (a bare word would be ambiguous); due tokens show the
    date part (the full canonical ISO stays in the machine-readable
    matched list)."""
    elected = str(entry.observed_at or "")[:10] or "undated"
    gist = str(entry.object or "").strip()
    display: List[str] = []
    for token in matched:
        if token.startswith("participant:"):
            display.append(token[len("participant:"):])
        elif token.startswith("due:"):
            display.append("due:" + token[len("due:"):][:10])
        else:
            display.append(token)
    return f"standing intention (elected {elected}): {gist} [matched: {', '.join(display)}]"


def triggered_commitments(
    store: Any, journal: Any, *, stimulus: Any, scope: str, owner_id: str,
    max_lines: int = 3, now: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Prospective-memory annotation — a PURE READ the host calls beside
    reconstruct: which OPEN commitments does the current stimulus trigger?
    Nothing executes a commitment; this SURFACES it at the right moment
    (person appears, topic matches, date passes) so the entity can keep
    its word or consciously let it go.

    Returns a list of {"entry": <the open-commitment row open_commitments
    returns>, "matched": [kind-prefixed tokens], "line": <one rendered
    presentation line>}, oldest-first (the longest-standing promise
    leads), capped at `max_lines`; when more commitments matched than the
    cap allows, ONE final summary element {"entry": None, "matched": [],
    "line": "N more open commitments suppressed"} names the overflow (the
    over-fire containment — a stimulus matching everything must not flood
    the prompt).

    Trigger shape (dict written into attributes.trigger at election time):
    {"participants": [...], "keywords": [...], "due_at": iso-optional}.
    An empty or absent trigger NEVER annotates (such commitments are
    listed by open_commitments only). Matching semantics: _trigger_matches.

    `now` is caller-supplied (the engine never reads the clock); None
    disables due matching. `journal` folds closures/hidden bindings out of
    the open set (None = layer-1 read, sibling semantics). This is
    presentation-only: NOT an admission channel — no shelf change, no
    deposit, no journal write.
    """
    if int(max_lines) < 0:
        raise ValueError("triggered_commitments max_lines must be >= 0 "
                         "(0 = summary-only; negative bounds are refused, never wrapped)")
    now_norm = normalize_iso_ts(now) if now is not None else None  # loud on garbage: boundary input

    stimulus_participants = frozenset(
        str(p).strip() for p in (getattr(stimulus, "participants", None) or ())
        if str(p or "").strip())
    cue_tokens = frozenset(TOKEN_RE.findall(fold_text(
        str(getattr(stimulus, "cue_text", "") or ""))))

    due_warnings: List[str] = []
    annotated: List[Dict[str, Any]] = []
    suppressed = 0
    for entry in open_commitments(store, scope=scope, owner_id=owner_id,
                                  limit=0, journal=journal):
        trigger = entry.attributes.get("trigger")
        if not isinstance(trigger, dict) or not trigger:
            continue  # empty/absent trigger never annotates (listed-only commitment)
        matched = _trigger_matches(
            trigger, stimulus_participants=stimulus_participants,
            cue_tokens=cue_tokens, now_norm=now_norm,
            due_warnings=due_warnings, record_id=str(entry.subject))
        if not matched:
            continue
        if len(annotated) < int(max_lines):
            annotated.append({"entry": entry, "matched": matched,
                              "line": _render_commitment_line(entry, matched)})
        else:
            suppressed += 1

    if due_warnings:
        _warnings.warn(
            "#FALLBACK: triggered_commitments skipped unparseable trigger.due_at on "
            f"{len(due_warnings)} record(s) ({'; '.join(due_warnings)}) — the due "
            "channel needs a canonical ISO timestamp; other trigger channels still ran",
            RuntimeWarning,
            stacklevel=2,
        )
    if suppressed:
        annotated.append({"entry": None, "matched": [],
                          "line": f"{suppressed} more open commitments suppressed"})
    return annotated
