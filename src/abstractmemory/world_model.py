"""World-model orientation cards (backlog 0033) — knowledge refined over time.

THE MAINTAINER'S MODEL (2026-07-12): "the world model cards are extremely
important as they represent the long-term understanding of people, object,
location, time, problems, ideas, concepts. that's the knowledge refined
over time." This is the SITUATION component's "profile recall" leg: the
gradation system gives the instant expectation of a target, participants
give shared context — the CARD holds the refined understanding, so a
returning visitor surfaces ONE compact orientation instead of N raw
episodes competing for shelf seats.

FORK LINEAGE (memory_control.rs world-model lane + ADR 0019, read
2026-07-12): source-linked (derived_from edges to the evidence),
revision-chained (refines edge to the previous revision; append-only —
"revision_policy: append_only_new_world_model_node"), maintenance-formed
only, indexed+inactive bindings ("indexed for grounding, not
prompt-pinned"), ORIENTATION NEVER AUTHORITY. Our port keeps every guard
and adds the closure fold: a superseded revision leaves recall through
the normal current-wins mechanism instead of a revision-number sort.

MECHANICS (deterministic, zero LLM — the digest is mechanical-v1 and says
so; entity-authored re-digestion is the waking lane, like every mechanical
digest):
- TARGETS are the gradation universe, extracted from lived records:
  participants (person:/entity:/... — except the scope owner: the
  explicit co-presence self-stamp is universal and a card about oneself
  is identity's lane, not orientation's) and topic strings (namespaced
  "topic:<t>"). Free strings, never an enum.
- EVIDENCE is lived records only: dreams, world_model cards, maintenance
  candidates, and bookkeeping rows never evidence a card (derived
  artifacts must not feed derived artifacts — the dream-pass loop-breaker
  applied here; ALSO the disposal rule's spirit: dream-only support can
  never source an orientation).
- A card forms when a target clears the evidence floor; it REVISES
  (revision N+1, refines → previous, previous closed kind="supersede"
  with the new card as replacement) when the evidence set CHANGED;
  identical evidence re-runs are no-ops (fingerprint idempotency).
- Cards carry attributes.participants=[target] for participant targets:
  the EXISTING participants channel surfaces the card exactly when that
  person is present — orientation arrives with the encounter, no new
  recall machinery.

THE D2 OF SLEEP HOLDS: forming/revising cards deposits nothing (formation
is not use; closures are belief revision).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .records import MemoryRecordInput, record_id_for
from .sleep_policy import DEFAULT_SLEEP_TUNING, SleepTuning
from .store import TripleQuery

__all__ = [
    "author_world_model",
    "current_world_models",
    "mention_orientation_cards",
    "standing_world_models",
    "world_model_pass",
    "world_model_update",
]

# Derived/bookkeeping kinds that never evidence a card (loop-breaker).
_NON_EVIDENCE_KINDS = frozenset({"dream", "world_model"})


def discovery_keyword_ok(keyword: str) -> bool:
    """ONE admission rule for mechanically-discovered subject keywords —
    shared by world-model topic discovery and the candidate miner's
    interest themes (miner adversary F10: the miner copied half the rule
    and the halves drifted — "_" cut and length floor diverged within a
    day). Compounds only (space/hyphen-joined), length >= 4, never
    machine vocabulary ("_" identifiers)."""
    k = str(keyword or "").strip().lower()
    if len(k) < 4 or "_" in k:
        return False
    return " " in k or "-" in k

# Act-frame marker lines ("[used tool: …]", "[kept in diary - …]") are not
# content — the redigestion module's poverty lesson applied to card gists.
_MARKER_RE = re.compile(r"\[[^\[\]]{1,120}\]")

# CARD DIGEST REDESIGN (2026-07-18, maintainer directive "the content is
# completely wrong"): the v1 mechanical digest was keyword soup ("Recurring
# themes: time, memory, system, like…") — true and useless. The v2 floor is
# an EVIDENCE-GIST briefing: standing feeling (gradation — "if I like him"),
# then the newest evidence records' ACTUAL sentences, then the themes line
# demoted to a footer. Still deterministic, zero LLM (digest_method
# "mechanical-card-v2" — named on the room thread the turn it was born, per
# the consent-vocabulary rule); the AUTHORED layer above it arrives via
# author_world_model() and is carried forward through evidence revisions as
# the lead with a mechanical "since then" delta.
_GIST_COUNT = 4          # newest evidence gists quoted on the floor
_GIST_CHARS = 150        # per-gist bound  #[WARNING:TRUNCATION] gist preview bounded (sources carry the full text)
_DELTA_GIST_COUNT = 3    # gists quoted in an authored card's delta line


def _evidence_gist(record: Dict[str, Any]) -> str:
    """One readable line from an evidence record: title when it carries
    meaning, else the digest's content residue (markers stripped)."""
    residue = " ".join(_MARKER_RE.sub(" ", record.get("digest") or "").split())
    title = str(record.get("title") or "").strip()
    # Generic machine titles ("exchange: …", "session reflection: …") add
    # nothing a reader learns; prefer the residue for those.
    text = residue if (not title or title.startswith(("exchange:", "session reflection:",
                                                      "Diary entry", "Consolidated:"))) else f"{title} — {residue}"
    text = text.strip() or title or "(no words survived the compression)"
    return text[: _GIST_CHARS - 1] + "…" if len(text) > _GIST_CHARS else text


def _evidence_scan(
    store: Any, journal: Any, *, scopes: Sequence[Tuple[str, str]],
    scan_limit: int = 0,
) -> Dict[str, Dict[str, Any]]:
    """Lived records eligible as card evidence: graph id -> facts.
    Closure-folded AND hidden-folded (a retracted or hidden episode stops
    evidencing cards — one belief-state read, same rule as
    unresolved_dreams) and derived-artifact-excluded. scan_limit=0 is the
    FULL scan (the sleep pass); a positive limit bounds the per-pair fetch
    newest-first (the per-turn incremental lane)."""
    from .folds import binding_states, closure_exclusions

    as_of = journal.current_seq()
    closed = set(closure_exclusions(journal, as_of))
    for scope, owner in scopes:
        _states, hidden, _active = binding_states(store, journal, [(scope, owner)], as_of)
        closed |= set(hidden)
    out: Dict[str, Dict[str, Any]] = {}
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None,
                                         limit=int(scan_limit))):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            kind = attrs.get("record_kind")
            if (not kind or kind in _NON_EVIDENCE_KINDS
                    or attrs.get("bookkeeping") or attrs.get("record_edge")
                    or attrs.get("maintenance_candidate")):
                continue
            if a.assertion_id in closed or a.subject in closed:
                continue
            # A record may be about SEVERAL things: attributes.topics
            # (list — runtime's reflection election, cap theirs) folds
            # with the single attributes.topic; order preserved, deduped.
            topics: List[str] = []
            for t in (attrs.get("topic"), *(attrs.get("topics") or ())):
                t = str(t or "").strip()
                if t and t not in topics:
                    topics.append(t)
            prov = a.provenance if isinstance(a.provenance, dict) else {}
            out[a.subject] = {
                "record_id": a.subject,
                "kind": str(kind),
                "title": str(attrs.get("title") or "").strip(),
                "digest": str(a.object or ""),
                "observed_at": str(a.observed_at or ""),
                "keywords": [str(k) for k in (attrs.get("keywords") or ())],
                "participants": [str(p) for p in (attrs.get("participants") or ())],
                "topic": topics[0] if topics else "",
                "topics": topics,
                # Session identity for recurrence gates (target discovery
                # counts DISTINCT sessions, never records — one chatty
                # session must not mint a subject).
                "session": str(prov.get("session_id") or prov.get("run_id") or ""),
            }
    return out


def _standing_feeling_line(system: Any, target: str, *, scope: str, owner_id: str) -> str:
    """The gradation half of 'I instantly know if I like him' — one line,
    omitted entirely when the target was never appraised (a card must not
    fabricate neutrality as a fact).

    SPELLING ALIAS READ (runtime's build-4 adversary F4, 2026-07-19): feel
    elections teach `concept:<words>` while card targets mint
    `topic:<words>` — a feeling marked on concept:coherence must surface
    on the topic:coherence card. The exact target spelling wins when
    appraised; the concept twin is a FALLBACK READ only (engraved
    spellings keep their keys — folding two streams would be a valence
    merge, a ruled act, never a read-side default)."""
    lookups = [target]
    if target.startswith("topic:"):
        lookups.append("concept:" + target.split(":", 1)[1])
    try:
        grades = system.gradation(lookups, scope=scope, owner_id=owner_id)
    except Exception:
        return ""  # a card floor must survive a journal hiccup; feelings are enrichment
    standing = None
    for key in lookups:
        row = grades.get(key)
        if row and (row.get("positive_count") or row.get("negative_count")):
            standing = row
            break
    if not standing:
        return ""
    net = float(standing.get("net") or 0.0)
    marks = [m for m, on in (("bond", standing.get("bonded")),
                             ("scar", standing.get("scarred"))) if on]
    suffix = f" ({', '.join(marks)})" if marks else ""
    return f"Standing feeling: net {net:+g}{suffix}."


def _floor_digest(display: str, rows: List[Dict[str, Any]], *, feeling: str,
                  first_seen: str, last_seen: str, kinds_line: str,
                  top_facets: Sequence[str]) -> str:
    """The mechanical-card-v2 floor: a BRIEFING, not a word cloud — standing
    feeling, then the newest evidence's actual sentences, then the span
    footer. Deterministic, zero LLM; the authored layer replaces it."""
    lines: List[str] = [f"What I know of {display}:"]
    if feeling:
        lines.append(feeling)
    for r in rows[-_GIST_COUNT:][::-1]:  # newest first
        lines.append(f"- {r['observed_at'][:10]}: {_evidence_gist(r)}")
    themes = f" Threads: {', '.join(top_facets)}." if top_facets else ""
    lines.append(
        f"(from {len(rows)} lived record(s), {first_seen[:10]} to {last_seen[:10]}, "
        f"{kinds_line}.{themes} Orientation, never authority — follow the "
        "sources when it matters.)")
    return "\n".join(lines)


def _authored_lead(prior: Any) -> str:
    """The authored text of a card — read from attributes.authored_lead
    (stamped by author_world_model and carried verbatim through +delta
    revisions), NEVER by splitting the digest text: an in-band delimiter
    would amputate authored prose that legitimately contains the delta
    phrase (adversary finding 1). Digest-split remains only as a legacy
    fallback for cards authored before the attribute existed."""
    attrs = prior.attributes if isinstance(prior.attributes, dict) else {}
    lead = str(attrs.get("authored_lead") or "").strip()
    if lead:
        return lead
    return str(prior.object or "").split("\n\nSince then", 1)[0].strip()


def _targets_of(record: Dict[str, Any], owner_id: str) -> List[str]:
    """The card targets one lived record contributes to: participants
    (minus the owner) + every elected topic (attributes.topic single or
    attributes.topics list — a reflection may elect that the day circled
    two subjects; each gets its own understanding)."""
    targets = [p for p in record["participants"] if p and p != owner_id]
    for topic in (record.get("topics") or ([record["topic"]] if record.get("topic") else [])):
        t = str(topic or "").strip()
        if t:
            targets.append(f"topic:{t}")
    return targets


def _interest_subject_head(text: str) -> str:
    """The subject an interest DECLARES, extracted deterministically from
    its title/digest: strip the 'interest:' prefix, take the head before
    the first qualifier separator (em/en dash, colon, question mark),
    fold whitespace, lowercase, drop one leading article, cap at 8 words.
    His own words, never invented — 'interest: Decentralized clinical
    trials and health equity — how removing...' -> 'decentralized
    clinical trials and health equity'."""
    t = str(text or "").strip()
    if t.lower().startswith("interest:"):
        t = t[len("interest:"):].strip()
    for sep in (" — ", " – ", " - ", ": ", "?"):
        idx = t.find(sep)
        if idx > 0:
            t = t[:idx]
    words = t.lower().split()
    if words and words[0] in ("the", "a", "an"):
        words = words[1:]
    words = words[:8]
    # An 8-word cut can land mid-phrase — drop dangling connectives so the
    # card key reads as a subject, never a fragment ("...consolidation,
    # and" -> "...consolidation").
    _dangling = {"and", "or", "of", "in", "on", "for", "with", "between",
                 "during", "the", "a", "an", "to", "that", "—", "–", "-"}
    while words and words[-1].strip(".,;:—–-?") in _dangling:
        words = words[:-1]
    head = " ".join(w.strip(".,;:—–-?") for w in words).strip()
    return head if len(head) >= 4 else ""


def _revision_of(assertion: Any) -> int:
    """Tolerant revision read: malformed values sort as 0, never crash
    (a card is data; a bad attribute is a formation bug to surface via
    the standing-duplicates repair, not a traceback in a read)."""
    raw = (assertion.attributes or {}).get("revision")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def standing_world_models(
    store: Any, *, scope: str, owner_id: str, journal: Any = None,
) -> Dict[str, List[Any]]:
    """target -> ALL standing (closure-folded) card assertions, revision
    ascending. More than one standing card per target means an
    interrupted revision (the supersede closure never landed) —
    world_model_pass repairs it."""
    rows = [a for a in store.query(TripleQuery(scope=scope, owner_id=owner_id or None, limit=0))
            if isinstance(a.attributes, dict)
            and a.attributes.get("record_kind") == "world_model"]
    if journal is not None:
        from .folds import closure_exclusions

        closed = closure_exclusions(journal, journal.current_seq())
        rows = [a for a in rows
                if a.assertion_id not in closed and a.subject not in closed]
    by_target: Dict[str, List[Any]] = {}
    for a in sorted(rows, key=lambda r: (_revision_of(r),
                                         str(r.observed_at or ""), str(r.subject))):
        target = str((a.attributes or {}).get("target") or "").strip()
        if target:
            by_target.setdefault(target, []).append(a)
    return by_target


def current_world_models(
    store: Any, *, scope: str, owner_id: str, journal: Any = None,
) -> Dict[str, Any]:
    """target -> the CURRENT (closure-folded, highest-revision) card.
    journal=None is the layer-1 read (no fold)."""
    return {target: rows[-1]
            for target, rows in standing_world_models(
                store, scope=scope, owner_id=owner_id, journal=journal).items()}


def world_model_pass(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
    report_only: bool = False,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
    targets: Optional[Sequence[str]] = None,
    scan_limit: int = 0,
) -> Dict[str, Any]:
    """Form/revise orientation cards for the targets the evidence supports.

    Deterministic and idempotent: same home state → same cards; a re-run
    forms nothing new (evidence fingerprints). Cards land in the FIRST
    scope pair (the home scope) under owner_id — same convention as the
    dream. Returns a self-describing result with per-target verdicts.

    TWO CADENCES, one body (maintainer 2026-07-18: per-turn background
    update + sleep-phase full maintenance): targets=None + scan_limit=0 is
    the SLEEP pass (whole evidence, every eligible target, repairs run);
    `targets=[...]` + a positive scan_limit is the PER-TURN incremental
    lane (world_model_update wraps it) — bounded newest-window evidence,
    only the named targets, honest about the window (a turn update sees
    recent evidence; the next sleep pass normalizes over everything, and
    the fingerprint/revision chain absorbs both cadences append-only)."""
    owner = str(owner_id or "").strip()
    if not owner:
        raise ValueError(
            "world_model_pass requires a non-empty owner_id — the owner "
            "exclusion (no card about oneself; the self-stamp never counts) "
            "is meaningless against a blank owner")
    store, journal = system.store, system.journal
    evidence = _evidence_scan(store, journal, scopes=scopes,
                              scan_limit=int(scan_limit))

    # Group evidence by target, deterministically.
    by_target: Dict[str, List[str]] = {}
    for gid in sorted(evidence):
        for target in _targets_of(evidence[gid], owner):
            by_target.setdefault(target, []).append(gid)

    # TARGET DISCOVERY (sleep cadence only — laurent's original directive
    # assigned sleep exactly this: "the sleep phase MUST enforce the proper
    # maintenance of those world model... loop back at every discussions,
    # identify and regroup the world model entities"; re-pushed 2026-07-19
    # c158 "it should have accumulated AND REFINED a lot more models").
    # A COMPOUND keyword recurring across >= discovery_sessions DISTINCT
    # sessions becomes a topic target — recurrence across sessions is
    # evidence of a standing subject, never one-record noise.
    #
    # COMPOUND-ONLY, measured not assumed (live simulation on Ephemeral's
    # 1,235-record store, 2026-07-19): single-word recurrence at ANY
    # ubiquity fraction yields function-word residue ("without",
    # "because", "circling") — his formation-side keywords are weak, and
    # no frequency gate can turn residue into subjects. Space/hyphen-
    # joined compounds are subject-shaped by construction ("cell-free",
    # "clinical trials"); underscore identifiers are machine vocabulary
    # (tool names: "diary_read") and never subjects. Slow-but-never-
    # garbage accumulation; single-word discovery stays with the ELECTED
    # lane (his words) until formation-side keyword quality improves
    # (runtime's lane, named on the record). Guards: session floor
    # (provenance-less records share ONE bucket — three owner-direct
    # writes never mint), ubiquity cut (concept-anchor max_sources
    # pattern), per-pass admission cap. No record is stamped — grouping
    # only; card CONTENT stays the v2 briefing.
    # INTERESTS AS TARGETS (2026-07-19, the room's reconciliation of
    # laurent's "dozens of cards by now" — entity c182 + runtime c174,
    # adopted): a kind=interest record IS an elected subject declaration
    # in his own words ("Decentralized clinical trials and health
    # equity") — the strongest target source in the hierarchy (election >
    # compound recurrence > single keywords never). Each ACTIVE interest
    # derives a topic target from its title's subject head; the interest
    # record itself is admissible evidence (it is in the scan), so a
    # declared subject cards immediately — an election is worth more
    # than raw recurrence, and the card honestly says what it is built
    # from. Same-subject interests fold into one target (his rumination
    # about continuity becomes ONE understanding, not twelve).
    interest_evidence: Dict[str, List[str]] = {}
    if targets is None and int(scan_limit) == 0:
        for gid in sorted(evidence):
            r = evidence[gid]
            if r["kind"] != "interest":
                continue
            head = _interest_subject_head(r["title"] or r["digest"])
            if not head:
                continue
            target = f"topic:{head}"
            interest_evidence.setdefault(target, []).append(gid)
        for target, ids in sorted(interest_evidence.items()):
            merged_ids = sorted({*by_target.get(target, []), *ids})
            by_target[target] = merged_ids

    if targets is None and int(scan_limit) == 0 and evidence:
        floor_sessions = max(2, int(tuning.world_model_discovery_sessions))
        max_fraction = float(tuning.world_model_discovery_max_fraction)
        kw_records: Dict[str, List[str]] = {}
        kw_sessions: Dict[str, set] = {}
        for gid in sorted(evidence):
            r = evidence[gid]
            session = str(r.get("session") or "").strip() or "(unknown-session)"
            for kw in r["keywords"]:
                k = str(kw or "").strip().lower()
                if not discovery_keyword_ok(k):
                    continue
                kw_records.setdefault(k, []).append(gid)
                kw_sessions.setdefault(k, set()).add(session)
        # The cap floors at 2x the session floor (a small store cannot
        # measure ubiquity; the cut earns its keep at scale).
        ubiquity_cap = max(2 * floor_sessions, int(len(evidence) * max_fraction))
        discovered = sorted(
            (k for k in kw_records
             if len(kw_sessions[k]) >= floor_sessions
             and len(kw_records[k]) <= ubiquity_cap),
            key=lambda k: (-len(kw_sessions[k]), k),
        )[: max(0, int(tuning.world_model_discovery_max_targets))]
        for k in discovered:
            target = f"topic:{k}"
            if target in by_target:
                continue  # elected/stamped topics own the name
            by_target[target] = sorted(set(kw_records[k]))

    standing = standing_world_models(store, scope=scopes[0][0],
                                     owner_id=scopes[0][1], journal=journal)

    # ALIAS FOLD (M3, maintainer's "admin = laurent"): a confirmed alias
    # (alias_world_model — always a deliberate act, never automatic)
    # regroups the alias string's evidence onto the PRIMARY card, and it
    # counts toward the primary's floor. One identity, one card, however
    # many names arrive at the door.
    from .world_model_alias import _aliases_of, alias_candidates

    aliases: Dict[str, str] = {}
    for primary, rows_ in standing.items():
        for alias in _aliases_of(rows_[-1]):
            if alias != primary:
                aliases[alias] = primary
    for alias, primary in sorted(aliases.items()):
        folded = by_target.pop(alias, None)
        if folded:
            merged = by_target.setdefault(primary, [])
            by_target[primary] = sorted({*merged, *folded})

    if targets is not None:
        # The filter normalizes through the map too: an update naming the
        # alias (the door stamped person:admin) reaches the primary's card.
        wanted = {aliases.get(t, t)
                  for t in (str(x).strip() for x in targets) if t}
        by_target = {t: ids for t, ids in by_target.items() if t in wanted}

    floor = int(tuning.world_model_evidence_floor)
    # An ELECTED subject clears the floor by the election itself:
    # demanding 3 records for a target he already declared significant
    # would re-litigate his own act (the interest record IS the evidence;
    # the card starts thin and thickens as lived records accrue — that is
    # "accumulate AND refine" in the intended order).
    eligible = {t: ids for t, ids in by_target.items()
                if len(ids) >= floor or t in interest_evidence}

    out: Dict[str, Any] = {
        "pass_name": "world_model_pass",
        "targets_seen": len(by_target),
        "eligible": sorted(eligible),
        "formed": [],
        "unchanged": [],
        "skipped": [],
        "repaired": [],
    }
    if targets is None and int(scan_limit) == 0:
        # SLEEP CADENCE ONLY (the full-evidence frame): heavy evidence
        # overlap between two same-namespace targets PROPOSES one identity
        # — waking review confirms with alias_world_model or leaves both
        # standing. Never on the per-turn window (a tiny frame overlaps
        # spuriously), never a silent merge (the dream discipline applied
        # to the identity of others).
        out["alias_proposals"] = alias_candidates(by_target, existing=aliases)

    # CRASH-REPLAY REPAIR (adversary P1-3): a crash between remember_many
    # (rev N+1 formed) and close_record(rev N) leaves TWO standing cards
    # for one target — the unchanged branch would then skip forever and
    # ranked recall would serve both. Repair on every pass: close every
    # standing card below the highest revision (closure ids are
    # deterministic, so re-closing is a journal no-op).
    for target, rows in sorted(standing.items()):
        for stale in rows[:-1]:
            if not report_only:
                system.close_record(
                    stale.subject, kind="supersede",
                    replacement_ids=[rows[-1].subject],
                    reason=f"world-model revision repair for {target} "
                           "(interrupted supersede)")
            out["repaired"].append({"target": target, "card_id": stale.subject,
                                    "closed": not report_only})

    current = {target: rows[-1] for target, rows in standing.items()}

    # Busiest understandings first; bounded per night. The unchanged
    # check runs BEFORE the budget (adversary P2: an unchanged target
    # must never be misreported as budget-skipped, and it spends none).
    ranked = sorted(eligible.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    budget = max(0, int(tuning.world_model_max_cards))
    for target, source_ids in ranked:
        fingerprint = hashlib.sha256(
            "|".join(sorted(source_ids)).encode("utf-8")).hexdigest()
        prior = current.get(target)
        prior_attrs = (prior.attributes if prior is not None
                       and isinstance(prior.attributes, dict) else {})
        if prior is not None and prior_attrs.get("evidence_fingerprint") == fingerprint:
            out["unchanged"].append({"target": target, "card_id": prior.subject})
            continue
        if budget <= 0:
            out["skipped"].append({"target": target, "reason": "max_cards reached"})
            continue
        revision = _revision_of(prior) + 1 if prior is not None else 1

        rows = [evidence[gid] for gid in source_ids]
        rows.sort(key=lambda r: (r["observed_at"], r["record_id"]))
        first_seen = rows[0]["observed_at"]
        last_seen = rows[-1]["observed_at"]
        facet_counts: Dict[str, int] = {}
        for r in rows:
            for kw in r["keywords"]:
                facet_counts[kw] = facet_counts.get(kw, 0) + 1
        top_facets = [f for f, _ in sorted(
            facet_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[: tuning.world_model_top_facets]]
        kind_counts: Dict[str, int] = {}
        for r in rows:
            kind_counts[r["kind"]] = kind_counts.get(r["kind"], 0) + 1
        kinds_line = ", ".join(f"{n} {k}" for k, n in sorted(
            kind_counts.items(), key=lambda kv: (-kv[1], kv[0])))

        display = target.split(":", 1)[1] if ":" in target else target
        feeling = _standing_feeling_line(system, target,
                                         scope=scopes[0][0], owner_id=owner)
        prior_method = str(prior_attrs.get("digest_method") or "")
        # A confirmed identity survives every evidence revision: aliases
        # carry forward verbatim (dropping them here would silently unbind
        # admin from laurent at the next sleep — an identity claim only a
        # deliberate act may revise).
        card_aliases = sorted({str(a).strip()
                               for a in (prior_attrs.get("aliases") or ())
                               if isinstance(a, str) and str(a).strip()})
        extra_attrs: Dict[str, Any] = {}
        if card_aliases:
            extra_attrs["aliases"] = card_aliases
        if prior is not None and prior_method.startswith("authored"):
            # AUTHORED LEAD CARRIES FORWARD: an entity/host-authored card is
            # never demoted back to the mechanical floor by new evidence —
            # the lead (attributes.authored_lead, verbatim) stands and ONE
            # mechanical delta names what is new SINCE THE AUTHORING
            # (baseline = attributes.authored_known_ids, frozen at the
            # authoring and carried through every +delta revision —
            # adversary finding 2: a per-pass baseline silently shrank the
            # delta to "since the last pass"). Deltas never stack;
            # re-authoring resets the baseline.
            lead = _authored_lead(prior)
            baseline = {str(s) for s in (prior_attrs.get("authored_known_ids")
                                         or prior_attrs.get("known_source_ids")
                                         or prior_attrs.get("source_ids") or ())}
            new_rows = [r for r in rows if r["record_id"] not in baseline]
            if new_rows:
                delta_gists = "; ".join(
                    _evidence_gist(r) for r in new_rows[-_DELTA_GIST_COUNT:][::-1])
                delta = (f"Since then ({len(new_rows)} new record(s), through "
                         f"{last_seen[:10]}): {delta_gists}")
            else:
                # Evidence SHRANK (retraction/hide changed the fingerprint
                # with zero new records) — adversary finding 3: fabricating
                # a delta from old rows would present old records as new.
                delta = (f"Since then: no new records; the evidence set was "
                         f"revised ({len(rows)} record(s) now stand).")
            digest = f"{lead}\n\n{delta}"
            digest_method = "authored-card-v1+delta"
            extra_attrs.update({
                "authored_lead": lead,
                "authored_known_ids": sorted(baseline),
                "authored_by": str(prior_attrs.get("authored_by") or "unknown")})
        else:
            digest = _floor_digest(
                display, rows, feeling=feeling, first_seen=first_seen,
                last_seen=last_seen, kinds_line=kinds_line, top_facets=top_facets)
            digest_method = "mechanical-card-v2"
        newest_first = [r["record_id"] for r in reversed(rows)]
        edges: List[Tuple[str, str]] = [
            ("derived_from", rid)
            for rid in newest_first[: tuning.world_model_max_sources]
        ]
        if prior is not None:
            edges.append(("refines", prior.subject))
        card = MemoryRecordInput(
            kind="world_model",
            title=f"World model: {display}",
            digest=digest,
            keywords=tuple(top_facets),
            participants=((target, *(a for a in card_aliases
                                     if not a.startswith("topic:")))
                          if not target.startswith("topic:") else ()),
            edges=tuple(edges),
            attributes={
                "world_model": True,
                "target": target,
                "revision": revision,
                "evidence_fingerprint": fingerprint,
                "source_count": len(rows),
                # The full evidence membership (edges are bounded to the
                # newest max_sources; the delta computation needs the SET).
                "known_source_ids": sorted(r["record_id"] for r in rows),
                "first_seen": first_seen,
                "last_seen": last_seen,
                # Mechanical floor awaiting authored words (author_world_model)
                # — or the authored lead + mechanical delta when carried.
                "digest_method": digest_method,
                **extra_attrs,
            },
        )
        verdict = {"target": target, "revision": revision,
                   "source_count": len(rows), "formed": not report_only}
        if not report_only:
            # REVISION RIDES THE KEY (adversary finding 4): a fingerprint-only
            # key let a RE-SEEN evidence set (hide -> revise -> unhide)
            # resolve to the old CLOSED card, which the pass then installed
            # as the "replacement" — zero standing cards, lineage dead
            # forever. With the revision in the key a re-seen set mints a
            # FRESH card at the new revision; crash-replay safety holds
            # (same revision + same fingerprint = same id = journal no-op).
            key = f"world-model|{owner}|{target}|rev{revision}|{fingerprint}"
            expected = record_id_for("world_model", key, 0)
            existed = bool(store.query(TripleQuery(subject=expected, limit=1)))
            [gid] = system.remember_many(
                [card], scope=scopes[0][0], owner_id=owner, idempotency_key=key)
            verdict["card_id"] = gid
            verdict["formed"] = not existed
            if prior is not None and prior.subject != gid:
                # Append-only revision: the old card leaves recall through
                # the normal closure fold; its history stays. Close
                # UNCONDITIONALLY (not just when the new card is fresh —
                # adversary P1-3): closure ids are deterministic, so a
                # replay after a crash between form and close re-lands
                # the close as a journal no-op instead of never.
                system.close_record(
                    prior.subject, kind="supersede", replacement_ids=[gid],
                    reason=f"world-model revision {revision} for {target} "
                           "(evidence changed)")
        out["formed"].append(verdict)
        budget -= 1

    out["formed_count"] = sum(1 for v in out["formed"] if v.get("formed"))
    return out


# Orientation bounds (declared tunables, ReconstructConfig carries the
# per-host overrides): the scan is BOUNDED like concept_anchor's identical
# shape (adversary finding 6: an unbounded per-recall store scan grows
# O(life) on the hot path — cards revise at every sleep pass, so current
# cards live inside a newest-first window by construction; a dormant card
# past the window resurfaces at its next revision). Admissions are CAPPED
# (finding 7: uncapped 1.0-score cards could fill a tight shelf and evict
# the genuinely matched answer — a mention orients, it must not crowd out
# the thing the mention was about); participant matches outrank cue
# matches inside the cap (who is actually HERE beats what was said).
ORIENTATION_SCAN_LIMIT = 400
ORIENTATION_MAX_CARDS = 3


def mention_orientation_cards(
    store: Any,
    stimulus: Any,
    scope_pairs: Sequence[Tuple[str, str]],
    *,
    excluded_ids: Any = frozenset(),
    scan_limit: int = ORIENTATION_SCAN_LIMIT,
    max_cards: int = ORIENTATION_MAX_CARDS,
) -> List[Dict[str, Any]]:
    """Mention => instant orientation (maintainer directive 2026-07-18):
    the CURRENT card for every world-model target mentioned in this
    stimulus — door-stamped participants match their target exactly;
    cue-text mentions match when ALL the target name's tokens appear in
    the cue's tokens (conservative: 'memory integrity' needs both words;
    a name in passing IS a mention — that is the design).

    Pure read, store-only (pipeline purity: closure/hidden folds arrive
    via excluded_ids, exactly like every other channel). Returns at most
    `max_cards` admissions [{record_id (assertion id), assertion, target,
    detail}] at direct-hit relevance, participant mentions first.

    Honest limits: the newest-`scan_limit` window per pair bounds cost
    (cards revise every sleep pass, so live cards stay inside it); cue
    matching floors at 3-char tokens (concept_terms), so very short
    names (topic:ai) are reachable via the participant path only; a
    stopword-grade topic target would cue-match its word anywhere —
    topic hygiene is formation's lane, the cap bounds the damage here.
    """
    from .concept_anchor import concept_terms

    cue_tokens = set(concept_terms(getattr(stimulus, "cue_text", "") or ""))
    participants = {str(p) for p in (getattr(stimulus, "participants", ()) or ())}
    if not cue_tokens and not participants:
        return []
    excluded = set(excluded_ids or ())

    matched: List[Tuple[int, str, Any, str]] = []  # (priority, target, assertion, via)
    seen_targets: set = set()
    for scope, owner in scope_pairs:
        rows = [a for a in store.query(TripleQuery(
                    scope=scope, owner_id=owner or None,
                    predicate="dcterms:abstract",
                    limit=int(scan_limit)))
                if isinstance(a.attributes, dict)
                and a.attributes.get("record_kind") == "world_model"
                and a.assertion_id not in excluded
                and a.subject not in excluded]
        # Current revision per target within this pair (closure folds
        # already dropped superseded cards via excluded_ids; revision
        # ordering guards the interrupted-supersede window).
        by_target: Dict[str, Any] = {}
        for a in sorted(rows, key=lambda r: (_revision_of(r),
                                             str(r.observed_at or ""), str(r.subject))):
            target = str((a.attributes or {}).get("target") or "").strip()
            if target:
                by_target[target] = a
        for target, a in sorted(by_target.items()):
            if target in seen_targets:
                continue
            # Every name the card answers to: the target plus confirmed
            # aliases (M3 — a mention of person:admin orients on the
            # laurent card once the identity is bound).
            attrs_a = a.attributes if isinstance(a.attributes, dict) else {}
            names = [target] + [str(al).strip()
                                for al in (attrs_a.get("aliases") or ())
                                if isinstance(al, str) and str(al).strip()]
            hit = next((n for n in names if n in participants), None)
            if hit is not None:
                seen_targets.add(target)
                via = ("participant" if hit == target
                       else f"participant alias {hit}")
                matched.append((0, target, a, via))
                continue
            for n in names:
                name = n.split(":", 1)[1] if ":" in n else n
                name_tokens = [t for t in concept_terms(name, bigrams=False)]
                if name_tokens and all(t in cue_tokens for t in name_tokens):
                    seen_targets.add(target)
                    via = "cue" if n == target else f"cue alias {n}"
                    matched.append((1, target, a, via))
                    break

    matched.sort(key=lambda m: (m[0], m[1]))
    return [{
        "record_id": a.assertion_id,
        "assertion": a,
        "target": target,
        "detail": f"orientation: current card for {target} (mentioned via {via})",
    } for _prio, target, a, via in matched[: max(0, int(max_cards))]]


def world_model_update(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
    targets: Sequence[str],
    scan_limit: int = ORIENTATION_SCAN_LIMIT,
    tuning: SleepTuning = DEFAULT_SLEEP_TUNING,
) -> Dict[str, Any]:
    """The per-turn incremental card update (frozen API for the driver's
    background pass, 2026-07-18): revise the named targets' cards from a
    bounded newest-window evidence scan — non-blocking-sized by design
    (one windowed query per scope pair), eventual-consistent by contract
    (the sleep pass normalizes over the full evidence). Targets the turn
    touched = door-stamped participants + topics the host extracted;
    below-floor targets no-op honestly. Same append-only revision chain,
    same authored-lead carry, same idempotency as the sleep pass — one
    body, two cadences."""
    wanted = [str(t).strip() for t in (targets or ()) if str(t).strip()]
    if not wanted:
        raise ValueError(
            "world_model_update requires the targets the turn touched — "
            "an empty update is a no-op the caller should skip, and a "
            "'just update everything' call is the sleep pass's job")
    return world_model_pass(
        system, scopes=scopes, owner_id=owner_id, tuning=tuning,
        targets=wanted, scan_limit=max(1, int(scan_limit)))


def author_world_model(
    system: Any, *, target: str, text: str,
    scope: str, owner_id: str,
    author: str = "entity-reflection",
) -> Dict[str, Any]:
    """Replace a card's words with AUTHORED prose (the distillation layer
    the mechanical floor awaits). The engine never invents text — this verb
    takes words authored elsewhere (the entity's reflection call, or an
    operator/host LLM pass) and applies them through the same append-only
    revision chain world_model_pass uses: new card (revision N+1, refines →
    prior, derived_from + evidence bookkeeping CARRIED — provenance answers
    "why do I think that" regardless of who wrote the prose), prior closed
    kind="supersede". Cards are excluded from apply_redigestion by rail;
    this is their one authoring door.

    Refusals are loud: no standing card (run world_model_pass first — an
    authored card without evidence lineage would be assertion, not
    orientation; NOTE for driver callers: a card exists only once its
    target clears SleepTuning.world_model_evidence_floor lived records,
    default 3 — a first-meeting participant has no card to author yet,
    skip silently and let the floor form at sleep), or empty text.
    Byte-identical text returns applied=False (idempotent success).
    """
    target_n = str(target or "").strip()
    words = str(text or "").strip()
    if not target_n:
        raise ValueError("author_world_model requires a target")
    if not words:
        raise ValueError(
            "author_world_model refuses empty text — the engine never "
            "invents words, and an empty authoring would erase the floor")
    current = current_world_models(
        system.store, scope=scope, owner_id=owner_id, journal=system.journal
    ).get(target_n)
    if current is None:
        raise ValueError(
            f"no standing world-model card for {target_n!r} — run "
            "world_model_pass first: an authored card without evidence "
            "lineage would be assertion, not orientation")
    if words == str(current.object or "").strip():
        # Idempotent success, not a refusal (adversary finding 10): a
        # crash-retry of an authoring that already landed must read as
        # "already current", indistinguishable refusals hide real errors.
        return {"target": target_n, "card_id": current.subject,
                "revision": _revision_of(current), "applied": False,
                "digest_method": str((current.attributes or {}).get("digest_method") or ""),
                "note": "authored text is already the current card"}
    attrs = current.attributes if isinstance(current.attributes, dict) else {}
    known = [str(s) for s in (attrs.get("known_source_ids")
                              or attrs.get("source_ids") or ())]
    if not known:
        # Legacy cards (pre known_source_ids) carry their evidence only as
        # derived_from edges — read them back so authoring over an old card
        # keeps its lineage (adversary finding 8: provenance must carry).
        known = [str(a.object) for a in system.store.query(
                     TripleQuery(subject=current.subject, limit=0))
                 if isinstance(a.attributes, dict)
                 and a.attributes.get("record_edge")
                 and a.predicate == "derived_from"]
    revision = _revision_of(current) + 1
    display = target_n.split(":", 1)[1] if ":" in target_n else target_n
    edges: List[Tuple[str, str]] = [
        ("derived_from", rid) for rid in list(reversed(known))[:8]]
    edges.append(("refines", current.subject))
    card = MemoryRecordInput(
        kind="world_model",
        title=f"World model: {display}",
        digest=words,
        keywords=tuple(str(k) for k in (attrs.get("keywords") or ())),
        participants=(target_n,) if not target_n.startswith("topic:") else (),
        edges=tuple(edges),
        attributes={
            "world_model": True,
            "target": target_n,
            "revision": revision,
            # The evidence identity is UNCHANGED by authoring — the words
            # changed, not the world. Fingerprint carries so the next
            # evidence-driven pass revises only on genuinely new evidence.
            "evidence_fingerprint": str(attrs.get("evidence_fingerprint") or ""),
            "source_count": attrs.get("source_count") or len(known),
            "known_source_ids": sorted(known),
            "first_seen": str(attrs.get("first_seen") or ""),
            "last_seen": str(attrs.get("last_seen") or ""),
            "digest_method": "authored-card-v1",
            "authored_by": str(author or "").strip() or "unknown",
            # The authored words + evidence baseline, carried VERBATIM by
            # every future +delta revision (findings 1+2: never parse the
            # lead out of digest text; never let the delta baseline drift).
            "authored_lead": words,
            "authored_known_ids": sorted(known),
        },
        provenance={"source": "world-model-authoring",
                    "actor": str(author or "").strip() or "unknown"},
    )
    key = f"world-model-authored|{owner_id}|{target_n}|rev{revision}"
    [gid] = system.remember_many(
        [card], scope=scope, owner_id=owner_id, idempotency_key=key)
    if current.subject != gid:
        system.close_record(
            current.subject, kind="supersede", replacement_ids=[gid],
            reason=f"world-model authored revision {revision} for {target_n}")
    return {"target": target_n, "card_id": gid, "revision": revision,
            "digest_method": "authored-card-v1"}
