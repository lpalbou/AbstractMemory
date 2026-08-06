"""W2 candidate miner: lesson/interest candidates from repeated session
evidence + question-resolution proposals (the room's wave-4 dispatch;
laurent's ITERATION 2 mechanism questions Q1/Q3 — "how do questions get
resolved, how do they translate into lessons").

THE SHAPE IS RULED (framework correction 7, adopted c3331 before this
build set): candidates are born kind="summary" +
attributes.proposed_kind="lesson"|"interest" — NEVER the target kind. A
candidate born kind=interest would enter his drive ratios and the daily
offer as if he had elected it (the machine-authored-drives class B-F8
forbids); born kind=summary + proposed_kind they are structurally outside
every kind-keyed fold. The ONE marker is the EXISTING
attributes.maintenance_candidate (input-exclusion rails already key on
it) + review_required. ADOPTION mints the real kind=lesson/interest in
HIS OWN WORDS (the promote path / an entity election) — the candidate is
an offer, never the thing itself.

Three reads/acts here:

- LESSON candidates: a RESOLVED question/problem whose theme lived across
  >= 2 distinct KNOWN sessions is worth keeping as a lesson ("you hit
  this, you settled it, and it recurred — your words would make it a
  lesson"). The discharging entries themselves never count as recurrence
  (adversary F4: the answer shares the question's words by construction),
  and provenance-less records never fake a session.
- INTEREST candidates: a compound theme recurring across >= N distinct
  sessions (ONE admission rule with world-model discovery —
  `discovery_keyword_ok` + the same ubiquity cap) with NO standing
  interest already declaring it.
- resolve_questions_pass: OPEN questions/problems matched against LATER
  evidence sharing their discriminative terms — PROPOSALS ONLY, never a
  discharge (machine purity, B-F8: resolving is HIS act; the proposal is
  the day desk's offer, "this may already be answered — look").

All candidates are fingerprint-idempotent (the existed check SKIPS the
store call entirely on re-runs — adversary F1: a re-mint through
remember_many would append grown summarizes edges to a frozen record),
bounded per night by MINTS (never by stale retries), and carry
summarizes edges naming their evidence (the engine's summary guard).
Machine rows never count as evidence or sessions. Term matching folds
through text_tokens (NFKD accents — mémoire matches memoire) with an
EN+FR function-word screen for the MATCHING lane (adversary F5: length
alone admits French function words; this list is proposal-matching
precision, not recall vocabulary — the recall tokenizer keeps the fork
ADR's no-language-lists rule).

Pure-read except the bounded candidate mints; report_only=True writes
nothing and applies the same cap accounting so the report PREDICTS the
write night (adversary F13b). as_of is refused outright: the miner reads
current diary/evidence state only (adversary F3 — an "anchored" read
that silently serves HEAD wears a costume).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .records import MemoryRecordInput, record_id_for
from .sleep_policy import DEFAULT_SLEEP_TUNING, SleepTuning
from .store import TripleQuery
from .text_tokens import bounded_label, token_set
from .world_model import _evidence_scan, _interest_subject_head, discovery_keyword_ok

__all__ = ["mine_candidates_pass", "resolve_questions_pass"]

_UNKNOWN_SESSION = "(unknown-session)"

# Function-word screen for the MATCHING lane only (proposal/theme term
# overlap — never recall tokenization, which keeps the fork ADR's
# no-language-lists rule with length as the proxy). English + French
# because Ephemeral lives FR/EN (adversary F5: 'cette'/'dans' passed the
# length floor and matched an unrelated walk to a question). Stored in
# NFKD-folded form because _terms folds before screening.
_STOPWORDS = frozenset({
    # EN
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "with", "to",
    "that", "this", "those", "these", "is", "are", "was", "were", "be",
    "been", "it", "its", "his", "her", "their", "our", "your", "my", "i",
    "about", "into", "from", "what", "when", "where", "how", "why", "who",
    "does", "did", "will", "would", "could", "should", "can", "cannot",
    "not", "no", "yes", "but", "as", "at", "by", "if", "then", "than",
    "there", "here", "have", "has", "had", "do", "am", "we", "they",
    "some", "same", "each", "also", "just", "very", "more", "most",
    # FR (folded: être->etre, très->tres, après->apres, même->meme)
    "dans", "cette", "ces", "avec", "pour", "sans", "leur", "leurs",
    "nous", "vous", "mais", "donc", "alors", "etre", "tout", "tous",
    "toute", "toutes", "comme", "plus", "moins", "tres", "bien", "encore",
    "aussi", "autre", "autres", "entre", "vers", "chez", "sous", "apres",
    "avant", "depuis", "quand", "comment", "pourquoi", "parce", "elle",
    "elles", "sont", "etait", "sera", "fait", "faire", "peut", "peuvent",
    "cela", "ceci", "celui", "celle", "ainsi", "meme", "sur", "une", "les",
    "des", "aux", "est", "sont", "ont", "par", "pas", "que", "qui", "quoi",
})


def _terms(text: str) -> Set[str]:
    """Discriminative terms for the matching lane: NFKD-folded tokens
    (text_tokens — the ONE folding home; mémoire == memoire, U+2019
    apostrophes stripped) minus the EN/FR function-word screen."""
    # Digit-dominated tokens are never discriminative (live finding:
    # timestamp fragments like '17t22' from projection texts matched 42
    # same-sitting entries as a "shared term").
    return {t for t in token_set(str(text or ""), min_len=4)
            if t not in _STOPWORDS
            and sum(c.isdigit() for c in t) * 2 < len(t)}


def _corpus_boilerplate(term_sets: Sequence[Set[str]]) -> Set[str]:
    """Per-corpus ubiquity screen for the MATCHING lane (live Ephemeral
    finding, 2026-07-20): his diary titles are templated ("Diary entry
    (question) — 2026-07-17"), so 'diary'/'entry'/'question' pass every
    static screen yet discriminate NOTHING — two such terms satisfied
    min_shared_terms and a lesson offer claimed "lived across 200
    sessions". A term present in more than an EIGHTH of the corpus
    documents (floor 8 — tiny stores cannot measure ubiquity) is
    boilerplate for MATCHING purposes; content stays content."""
    df: Dict[str, int] = {}
    for ts in term_sets:
        for t in ts:
            df[t] = df.get(t, 0) + 1
    if not df:
        return set()
    # 12.5% cap, floor 8 (measured on Ephemeral's live copy: the diary
    # template's scaffold sits at 16-36% document frequency — 'diary' 36%,
    # 'entry' 22%, 'question' 16% — while real content themes sit under
    # 10% — 'coherence' 6%, 'identity' 2%; a quarter cap kept the
    # scaffold and the templated matches with it).
    cap = max(8, len(term_sets) // 8)
    return {t for t, n in df.items() if n > cap}


def _diary_entries(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
) -> Tuple[List[Dict[str, Any]], Set[str], Dict[str, Dict[str, Any]]]:
    """Believed diary rows (as dicts), the unioned discharge-reference
    set, AND the reverse answering map (discharged ref -> the answering
    believed entry) — ONE fold, the SAME believed-rows semantics as
    cognition_health._diary_counts / diary._open_unresolved (a bar and a
    miner must never disagree on what stands open).

    The answering map is built HERE from believed rows only (adversary
    F2: a separate unfolded scan let a RETRACTED answer be quoted
    verbatim in a durable candidate digest). Deterministic pick on
    collisions: the OLDEST believed answering entry by
    (observed_at, record_id) — the entry that actually settled it first,
    identical across store backends (F2 sub-point: newest-first store
    order tie-broke differently between backends).

    resolved_refs union per SCOPE PAIR (adversary F13d: cross-pair
    unioning made a discharge read resolved here and open on the bar —
    fold agreement wins over generosity)."""
    from .cognition_health import _REF_ATTRS
    from .folds import binding_states, closure_exclusions

    excluded: Set[str] = set()
    if journal is not None:
        as_of = journal.current_seq()
        excluded = set(closure_exclusions(journal, as_of))
        for scope, owner in scopes:
            _states, hidden, _active = binding_states(store, journal, [(scope, owner)], as_of)
            excluded |= set(hidden)

    entries: List[Dict[str, Any]] = []
    per_pair_refs: Dict[Tuple[str, str], Set[str]] = {}
    answering_of: Dict[str, Dict[str, Any]] = {}
    seen: Set[str] = set()
    for scope, owner in scopes:
        pair = (scope, owner)
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_kind") != "diary":
                continue
            if a.assertion_id in excluded or a.subject in excluded:
                continue
            if a.subject in seen:
                continue
            seen.add(a.subject)
            prov = a.provenance if isinstance(a.provenance, dict) else {}
            entry = {
                "record_id": a.subject,
                "entry_id": str(attrs.get("entry_id") or "").strip(),
                "diary_type": str(attrs.get("diary_type") or ""),
                "title": str(attrs.get("title") or "").strip(),
                "text": str(a.object or ""),
                "observed_at": str(a.observed_at or ""),
                "scope_pair": pair,
                "session": str(prov.get("session_id") or prov.get("run_id") or ""),
            }
            entries.append(entry)
            for ref_attr in _REF_ATTRS:
                ref = attrs.get(ref_attr)
                if isinstance(ref, str) and ref.strip():
                    ref_n = ref.strip()
                    per_pair_refs.setdefault(pair, set()).add(ref_n)
                    prior = answering_of.get(ref_n)
                    if (prior is None
                            or (entry["observed_at"], entry["record_id"])
                            < (prior["observed_at"], prior["record_id"])):
                        answering_of[ref_n] = entry
    for e in entries:
        e["resolved_refs"] = per_pair_refs.get(e["scope_pair"], set())
    return entries, set().union(*per_pair_refs.values()) if per_pair_refs else set(), answering_of


def _discharged(entry: Dict[str, Any]) -> bool:
    refs = {entry["record_id"], entry["entry_id"]} - {""}
    return bool(refs & entry.get("resolved_refs", set()))


def resolve_questions_pass(
    store: Any, journal: Any, *,
    scopes: Sequence[Tuple[str, str]],
    scan_limit: int = 0,
    min_shared_terms: int = 2,
    max_evidence: int = 3,
    limit: int = 20,
    _entries: Optional[List[Dict[str, Any]]] = None,
    _evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """OPEN questions/problems matched against LATER evidence — PROPOSALS
    ONLY (report shape, zero writes): resolving is HIS act; a machine
    record must never discharge a drive (B-F8). A proposal says "these
    later records share your question's own words — it may already be
    answered; look". The day desk / wake cue offers it; a believed diary
    entry with answers=/resolves= is the only discharge.

    Match rule: >= min_shared_terms discriminative terms shared between
    the question's title/text and an evidence record's title+keywords,
    evidence formed strictly AFTER the question (ISO observed_at order —
    the day answering must postdate the asking). Question/problem diary
    rows never count as evidence (adversary F13c: a re-asked question is
    not an answer to its older twin — same words by construction).

    _entries/_evidence are the miner's precomputed folds (adversary F11:
    the pass used to re-scan what the caller had just scanned)."""
    if _entries is None or _evidence is None:
        _entries, _refs, _ans = _diary_entries(store, journal, scopes=scopes)
        _evidence = _evidence_scan(store, journal, scopes=scopes, scan_limit=scan_limit)
    entries, evidence = _entries, _evidence

    # Diary question/problem records never serve as resolution evidence
    # (they ARE askings, not answers) — keyed by record id.
    asking_ids = {e["record_id"] for e in entries
                  if e["diary_type"] in ("question", "problem")}

    # Pre-tokenize evidence once (F11: O(questions x evidence)
    # re-tokenization measured at seconds on a 5k store).
    ev_terms: Dict[str, Set[str]] = {}
    for rid in sorted(evidence):
        r = evidence[rid]
        ev_terms[rid] = (_terms(r["title"])
                         | {t for k in r["keywords"] for t in _terms(str(k))})
    # Per-corpus boilerplate screen (live Ephemeral finding): templated
    # titles make their scaffold words ubiquitous — ubiquitous terms
    # discriminate nothing and never count as shared.
    boilerplate = _corpus_boilerplate(list(ev_terms.values()))
    for rid in ev_terms:
        ev_terms[rid] -= boilerplate

    proposals: List[Dict[str, Any]] = []
    open_entries = [e for e in entries
                    if e["diary_type"] in ("question", "problem")
                    and not _discharged(e)]
    open_entries.sort(key=lambda e: (e["observed_at"], e["record_id"]))
    for q in open_entries:
        q_terms = (_terms(q["title"]) | _terms(q["text"])) - boilerplate
        if not q_terms:
            continue
        matched: List[Dict[str, Any]] = []
        for rid in sorted(evidence):
            if rid in asking_ids or rid == q["record_id"]:
                continue
            r = evidence[rid]
            if r["observed_at"] <= q["observed_at"]:
                continue  # the answer must postdate the asking
            shared = sorted(q_terms & ev_terms[rid])
            if len(shared) >= int(min_shared_terms):
                matched.append({"record_id": rid, "title": r["title"],
                                "shared_terms": shared,
                                "observed_at": r["observed_at"]})
        if matched:
            matched.sort(key=lambda m: (-len(m["shared_terms"]), m["observed_at"]))
            proposals.append({
                "question_id": q["record_id"],
                "diary_type": q["diary_type"],
                "title": q["title"],
                "asked_at": q["observed_at"],
                "evidence": matched[: max(1, int(max_evidence))],
                "note": ("later records share this question's own words — "
                         "it may already be answered; resolving is yours "
                         "(a diary entry with answers=/resolves=)"),
            })
    return {
        "pass_name": "resolve_questions_pass",
        "examined": len(open_entries),
        "proposals": proposals[: max(0, int(limit))],
        "proposal_count": len(proposals),
    }


def mine_candidates_pass(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
    max_candidates: int = 2,
    report_only: bool = False, as_of: Optional[int] = None,
    scan_limit: int = 0,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
) -> Dict[str, Any]:
    """One mining pass: lesson candidates (resolved tensions that lived
    across sessions), interest candidates (recurring un-elected themes),
    and the question-resolution proposals — bounded, idempotent, ruled
    shape (kind=summary + proposed_kind; adoption mints HIS record).

    Candidates land in the FIRST scope pair (the home scope), like every
    sleep formation. The night cap counts MINTS only (adversary F1:
    counting stale retries let two living themes starve every future
    offer forever) and applies in report_only too, so the report predicts
    the write night (F13b)."""
    if as_of is not None:
        # The miner reads CURRENT diary/evidence state only — there is no
        # anchored read path, so accepting as_of would serve HEAD wearing
        # an anchor (adversary F3). sleep_pass skips this phase under
        # as_of for the same reason.
        raise ValueError(
            "mine_candidates_pass: the miner reads current state only — "
            "anchored audits are not supported (as_of must be None); "
            "sleep_pass skips the mining phase under an anchor")
    store, journal = system.store, system.journal
    cap = max(0, int(max_candidates))

    entries, resolved_refs, answering_of = _diary_entries(store, journal, scopes=scopes)
    evidence = _evidence_scan(store, journal, scopes=scopes, scan_limit=scan_limit)
    questions = resolve_questions_pass(
        store, journal, scopes=scopes, scan_limit=scan_limit,
        _entries=entries, _evidence=evidence)

    out: Dict[str, Any] = {
        "pass_name": "mine_candidates_pass",
        "lesson_candidates": [], "interest_candidates": [],
        "question_proposals": questions["proposals"],
        "drive_groups": [],
        "created": [], "skipped": [], "created_count": 0,
    }

    # --- Standing exclusions (believed rows + lifecycle; adversary F9:
    # a RETRACTED interest suppressed its theme forever, and rejected
    # interests suppressed while the comment promised otherwise) --------------
    excluded: Set[str] = set()
    lifecycle_of: Dict[str, str] = {}
    if journal is not None:
        from .folds import binding_states, closure_exclusions

        seq_now = journal.current_seq()
        excluded = set(closure_exclusions(journal, seq_now))
        for scope, owner in scopes:
            _states, hidden, _active = binding_states(store, journal, [(scope, owner)], seq_now)
            excluded |= set(hidden)
            for b in journal.bindings(scope=scope, owner_id=owner, fold=True):
                lifecycle_of[b.record_id] = b.lifecycle

    from .entity_card import _CLOSED_INTEREST_LIFECYCLES

    standing_interest_heads: Set[str] = set()
    standing_lesson_terms: List[Set[str]] = []
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None,
                                         predicate="dcterms:abstract", limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if a.assertion_id in excluded or a.subject in excluded:
                continue
            kind = attrs.get("record_kind")
            if kind == "interest":
                if lifecycle_of.get(a.subject, "") in _CLOSED_INTEREST_LIFECYCLES:
                    continue  # a parked interest does not own its theme
                head = _interest_subject_head(str(attrs.get("title") or a.object or ""))
                if head:
                    standing_interest_heads.add(head)
            elif kind == "lesson":
                standing_lesson_terms.append(_terms(str(attrs.get("title") or "")))

    # Two cap POOLS, same numeric bound: theme offers (lesson/interest)
    # and GROUP offers — the ruling makes grouping the priority signal,
    # and groups run last in mint order; one shared pool would let two
    # lesson mints starve every group offer on exactly the 84-question
    # store the ruling describes (the F1 starvation lesson at design
    # time, pool-shaped).
    minted_by_pool: Dict[str, int] = {"offers": 0, "groups": 0}

    def _mint(kind_proposed: str, *, key_seed: str, title: str, digest: str,
              source_ids: Sequence[str], extra: Dict[str, Any],
              pool: str = "offers") -> Optional[str]:
        sources = [s for s in dict.fromkeys(source_ids) if s][:6]
        if not sources:
            return None
        fingerprint = hashlib.sha256(key_seed.encode("utf-8")).hexdigest()
        key = f"candidate-miner|{kind_proposed}|{owner_id}|{fingerprint}"
        expected = record_id_for("summary", key, 0)
        # EXISTED CHECK BEFORE ANY WRITE (adversary F1 P0): re-entering
        # remember_many with a grown source list appended new summarizes
        # edges onto the frozen candidate and ate a cap slot forever.
        # An already-minted offer is SKIPPED — no store write, no cap
        # slot, no signal — but its id RETURNS so group retirement can
        # still supersede stale siblings onto the standing offer
        # (grouping adversary F3: a merge whose exemplar kept the old
        # fingerprint left the swallowed cluster's offer frozen forever).
        if store.query(TripleQuery(subject=expected, limit=1)):
            out["skipped"].append({"proposed_kind": kind_proposed, "title": title,
                                   "reason": "already minted (standing offer)"})
            return expected
        if minted_by_pool[pool] >= cap:
            out["skipped"].append({"proposed_kind": kind_proposed, "title": title,
                                   "reason": f"night cap {cap} reached"})
            return None
        minted_by_pool[pool] += 1
        if report_only:
            out["created"].append({"candidate_id": None, "proposed_kind": kind_proposed,
                                   "title": title, "source_ids": sources,
                                   "created": False, "would_mint": True})
            return None
        candidate = MemoryRecordInput(
            kind="summary",
            title=title,
            digest=digest,
            edges=tuple(("summarizes", rid) for rid in sources),
            attributes={
                # THE RULED SHAPE (correction 7): summary + proposed_kind,
                # the existing marker pair — structurally outside drive
                # ratios, daily offers, and every kind-keyed fold until
                # HE adopts it.
                "maintenance_candidate": True,
                "review_required": True,
                "proposed_kind": kind_proposed,
                "source_ids": sources,
                "source_count": len(sources),
                "no_source_mutation": True,
                **extra,
            },
        )
        [gid] = system.remember_many(
            [candidate], scope=scopes[0][0], owner_id=owner_id, idempotency_key=key)
        out["created"].append({"candidate_id": gid, "proposed_kind": kind_proposed,
                               "title": title, "source_ids": sources, "created": True})
        return gid

    # --- LESSON candidates ---------------------------------------------------
    # A resolved question/problem whose theme lived across >= 2 distinct
    # KNOWN sessions. The discharging entries never count as recurrence
    # (adversary F4a: the answer shares the question's words by
    # construction) and the unknown-session bucket never counts toward
    # the floor (F4b: two provenance-less records are not two sessions —
    # the digest was fabricating "lived across 2 sessions").
    discharger_ids: Set[str] = {e["record_id"] for e in answering_of.values()}

    # Pre-tokenized evidence with the per-corpus boilerplate screen
    # (live Ephemeral finding: templated diary titles made
    # 'diary'/'entry'/'question' ubiquitous — a lesson offer claimed a
    # theme "lived across 200 sessions" on pure scaffold words).
    lesson_ev_terms: Dict[str, Set[str]] = {}
    for rid in sorted(evidence):
        r = evidence[rid]
        lesson_ev_terms[rid] = (_terms(r["title"])
                                | {t for k in r["keywords"] for t in _terms(str(k))})
    boilerplate = _corpus_boilerplate(list(lesson_ev_terms.values()))
    for rid in lesson_ev_terms:
        lesson_ev_terms[rid] -= boilerplate

    lesson_rows: List[Dict[str, Any]] = []
    for q in entries:
        if q["diary_type"] not in ("question", "problem"):
            continue
        if not _discharged(q):
            continue
        q_terms = (_terms(q["title"]) | _terms(q["text"])) - boilerplate
        if not q_terms:
            continue
        # A lesson already standing on this theme means his act happened.
        if any(len(q_terms & lt) >= 2 for lt in standing_lesson_terms if lt):
            continue
        sessions: Set[str] = set()
        q_session = q["session"] or _UNKNOWN_SESSION
        if q_session != _UNKNOWN_SESSION:
            sessions.add(q_session)
        theme_evidence: List[str] = []
        for rid in sorted(evidence):
            if rid in discharger_ids or rid == q["record_id"]:
                continue
            if len(q_terms & lesson_ev_terms[rid]) >= 2:
                session = evidence[rid]["session"] or _UNKNOWN_SESSION
                if session != _UNKNOWN_SESSION:
                    sessions.add(session)
                theme_evidence.append(rid)
        if len(sessions) < 2:
            continue
        answer = (answering_of.get(q["record_id"])
                  or answering_of.get(q["entry_id"]) or {})
        lesson_rows.append({
            "question": q, "answer": answer, "evidence": theme_evidence,
            "sessions": len(sessions)})

    # Oldest tension first (the longest-standing resolution earned its
    # lesson first) — deterministic under the cap.
    lesson_rows.sort(key=lambda r: (r["question"]["observed_at"],
                                    r["question"]["record_id"]))
    for row in lesson_rows:
        q, answer = row["question"], row["answer"]
        # Name the offer by words that CARRIED the match (live Ephemeral
        # polish: his diary titles are templated — "Diary entry
        # (question) — 2026-07-17" names nothing; when the title is all
        # boilerplate, the question's own text head is the honest label).
        label = q["title"]
        if not (_terms(q["title"]) - boilerplate):
            # `question_id` below carries the record these words came from.
            head = bounded_label(" ".join(str(q["text"] or "").split()), 90).strip()
            label = head or q["title"]
        entry = {
            "proposed_kind": "lesson", "question_id": q["record_id"],
            "title": bounded_label(f"Lesson candidate: {label}", 120),
            "sessions": row["sessions"],
        }
        out["lesson_candidates"].append(entry)
        settled_line = (f" You settled it: {answer['title']!r}." if answer.get("title")
                        else " You settled it in your own diary.")
        digest = (
            f"You {'asked' if q['diary_type'] == 'question' else 'hit'} this and "
            f"resolved it: {label!r}.{settled_line} The theme lived across "
            f"{row['sessions']} sessions — worth keeping as a lesson IN YOUR OWN "
            "WORDS. This candidate stands for review; adopting it mints the "
            "lesson as your act, rejecting it is an honest no.")
        _mint("lesson",
              key_seed=f"lesson|{q['record_id']}",
              title=entry["title"],
              digest=digest,
              source_ids=[q["record_id"],
                          *([answer["record_id"]] if answer.get("record_id") else []),
                          *row["evidence"]],
              extra={"question_id": q["record_id"], "sessions": row["sessions"]})

    # --- INTEREST candidates -------------------------------------------------
    # ONE admission vocabulary with world-model discovery (adversary F10:
    # the copied half drifted within a day): discovery_keyword_ok +
    # the discovery ubiquity cap. Known sessions only (F4b symmetry).
    floor_sessions = max(2, int(tuning.world_model_discovery_sessions))
    max_fraction = float(tuning.world_model_discovery_max_fraction)
    theme_sessions: Dict[str, Set[str]] = {}
    theme_records: Dict[str, List[str]] = {}
    for rid in sorted(evidence):
        r = evidence[rid]
        session = r["session"] or _UNKNOWN_SESSION
        if session == _UNKNOWN_SESSION:
            continue
        for kw in r["keywords"]:
            kw_n = str(kw or "").strip().lower()
            if not discovery_keyword_ok(kw_n):
                continue
            theme_sessions.setdefault(kw_n, set()).add(session)
            theme_records.setdefault(kw_n, []).append(rid)
    ubiquity_cap = max(2 * floor_sessions, int(len(evidence) * max_fraction))

    interest_rows: List[Tuple[str, int, List[str]]] = []
    for theme in sorted(theme_sessions):
        n_sessions = len(theme_sessions[theme])
        if n_sessions < floor_sessions:
            continue
        if len(theme_records[theme]) > ubiquity_cap:
            continue  # stamped-on-everything vocabulary is not a subject
        theme_t = _terms(theme)
        # Suppression requires the standing interest to genuinely declare
        # the theme: full term containment either way, or a substring
        # match on the heads (adversary F6: a one-shared-term relaxation
        # let "energy policy" suppress "tidal energy").
        covered = any(
            head and (head in theme or theme in head
                      or (theme_t and _terms(head) and
                          (theme_t <= _terms(head) or _terms(head) <= theme_t)))
            for head in standing_interest_heads)
        if covered:
            out["skipped"].append({"proposed_kind": "interest", "title": theme,
                                   "reason": "a standing interest already declares this theme"})
            continue
        interest_rows.append((theme, n_sessions, theme_records[theme]))

    interest_rows.sort(key=lambda r: (-r[1], r[0]))  # most-recurrent first
    for theme, n_sessions, rids in interest_rows:
        entry = {"proposed_kind": "interest", "theme": theme,
                 "title": bounded_label(f"Interest candidate: {theme}", 120),
                 "sessions": n_sessions}
        out["interest_candidates"].append(entry)
        example = evidence[rids[0]]["title"] if rids else ""
        digest = (
            f"You returned to {theme!r} across {n_sessions} distinct sessions "
            f"(e.g. {example!r}) without electing it as an interest. This "
            "candidate stands for review: adopting it mints the interest in "
            "your own words; rejecting it is an honest no.")
        _mint("interest",
              key_seed=f"interest|{theme}",
              title=entry["title"],
              digest=digest,
              source_ids=list(dict.fromkeys(rids)),
              extra={"theme": theme, "sessions": n_sessions})

    # --- DRIVE GROUPS (laurent room#277: "During the sleep, similar
    # questions should be grouped; same for problems; same for interests
    # etc; the more there are the higher the signal") ---------------------
    # ONE partition over the full open families (open_drive_partition —
    # grouping adversary F1/F4/F5: the inline family builds dropped the
    # explores= discharge and diverged from the day lane's corpus); every
    # cluster >= 2 reports in drive_groups; clusters >= GROUP_OFFER_FLOOR
    # mint ONE group offer in the ruled shape. Grouping NEVER discharges a
    # drive — the offer is an invitation ("these N read as one"); one
    # answering entry from HIM discharges the members he confirms.
    # Fingerprint = the cluster's EXEMPLAR (oldest member), so a growing
    # cluster keeps its one standing offer; when clusters MERGE or SPLIT
    # (new exemplar), the stale standing offers are SUPERSEDED by the new
    # one (adversary F3: three frozen offers described one merged
    # pressure — machine retiring machine rows, the resolve_dreams
    # precedent, never a B-F8 discharge of HIS drives).
    from .drive_grouping import GROUP_OFFER_FLOOR, open_drive_partition

    # Standing group offers (believed rows) for the retirement scan.
    standing_offers: List[Any] = []
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None,
                                         predicate="dcterms:abstract", limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if (attrs.get("maintenance_candidate")
                    and str(attrs.get("proposed_kind") or "").endswith("_group")
                    and a.assertion_id not in excluded and a.subject not in excluded):
                standing_offers.append(a)

    partition = open_drive_partition(store, journal, scopes=scopes, _entries=entries)
    for family in sorted(partition):
        for g in partition[family]:
            row = {"family": family, **g}
            out["drive_groups"].append(row)
            if g["size"] < GROUP_OFFER_FLOOR:
                continue
            shared = ", ".join(g["shared_terms"][:4]) or "(shared vocabulary)"
            digest = (
                f"{g['size']} of your open {family}s read as one — shared words: "
                f"{shared}. The night grouped them; nothing was closed. If they ARE "
                "one, a single answering entry settles the ones you confirm; if "
                "they are distinct, rejecting this offer is an honest no.")
            # Exemplar FIRST in sources (adversary F7: the newest-first cap
            # dropped the exemplar from its own offer on clusters >= 7).
            ordered_members = [g["exemplar"],
                               *[m for m in g["members"] if m != g["exemplar"]]]
            # Fingerprint = exemplar + MEMBER SET (adversary F3's frozen-size
            # half): a stable cluster keeps its one offer night after night;
            # genuine change (growth/merge/split) mints a fresh offer with
            # the honest size and retirement supersedes the stale one —
            # exactly one standing offer per pressure, always current.
            members_hash = hashlib.sha256(
                "|".join(sorted(g["members"])).encode("utf-8")).hexdigest()[:16]
            new_gid = _mint(
                f"{family}_group",
                key_seed=f"group|{family}|{g['exemplar']}|{members_hash}",
                title=bounded_label(
                    f"Group offer: {g['size']} {family}s around "
                    f"{(g['shared_terms'][0] if g['shared_terms'] else g['exemplar'])}", 120),
                digest=digest,
                source_ids=ordered_members,
                extra={"group_size": g["size"], "group_family": family,
                       "group_shared_terms": g["shared_terms"],
                       "group_exemplar": g["exemplar"]},
                pool="groups")
            if new_gid is None:
                continue
            # RETIREMENT (F3): a standing same-family group offer sharing
            # any member with this cluster describes the SAME pressure
            # lineage (partitions are disjoint) — supersede it so exactly
            # one offer stands per pressure and health counts stay honest.
            member_set = set(g["members"])
            for old in standing_offers:
                old_attrs = old.attributes
                if old_attrs.get("proposed_kind") != f"{family}_group":
                    continue
                if old.subject == new_gid:
                    continue
                old_members = {str(s) for s in (old_attrs.get("source_ids") or ())}
                old_members.add(str(old_attrs.get("group_exemplar") or ""))
                if old_members & member_set:
                    system.close_record(
                        old.subject, kind="supersede", replacement_ids=[new_gid],
                        reason=(f"group offer superseded: the {family} cluster "
                                f"changed shape (now {g['size']} members) — one "
                                "standing offer per pressure"))

    out["created_count"] = sum(1 for c in out["created"] if c["created"])
    return out
