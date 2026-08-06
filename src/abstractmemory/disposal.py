"""Waking-evidence disposal: the half of the sleep loop that DECIDES
(fork 690 + 360 + 470, adopted per the 2026-07-12 fork comparison).

"Sleep proposes; waking evidence disposes" had a proposer and no disposer:
dream/consolidation passes create review-gated proposals, and nothing could
ever confirm one into a real typed edge, promote an inactive candidate, or
honestly dissolve a dream. This module is the disposer — three verbs, all
append-only, all loud:

- `confirm_relation(...)`: waking evidence turns a proposed association
  into a REAL typed edge between two records. The relation must come from
  the ENGRAVED vocabulary (standing 0016 rule: no new predicate engraves
  before a registry declaration coordinated with semantics — an
  unregistered relation refuses naming that path). Evidence records are
  MANDATORY and may not be the proposing dream itself (a dream is a hint,
  never its own proof — fork 710's rule).
- `promote_candidate(...)`: flips an inactive candidate's lifecycle to
  "promoted" — REQUIRING independent-origin corroboration (fork 470): at
  least `min_origins` corroborating records whose provenance origins are
  distinct from each other AND from the candidate's own origin. This is
  the mechanical counter to the bridge attractor: one dream plus the
  entity's own retellings share one origin and can never corroborate
  themselves into promotion.
- `reject_candidate(...)`: the honest "no" — lifecycle "rejected" with a
  mandatory reason. The record stays indexed (append-only; a rejection is
  a judgment, not an erasure) unless the caller also hides it.

Dream disposition composes from existing verbs and this module:
confirmed → `confirm_relation` + close the dream (kind="supersede",
replacement = the confirmed edge's records); dissolved →
close_record(kind="retract", reason) — both already exist on the facade.
`dispose_dream` wraps that composition so hosts wire ONE call.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .consolidation import COMPONENT_RELATIONS
from .journal import MemoryEvent, ScopeBinding
from .models import TripleAssertion
from .records import resolve_digest_assertion

__all__ = [
    "DISPOSAL_RELATIONS",
    "confirm_relation",
    "dispose_dream",
    "enact_realization",
    "independent_origins",
    "promote_candidate",
    "reject_candidate",
]

# The edge vocabulary disposal may write: COMPONENT-DEFINING relations only
# (adversary fix, 2026-07-12 — CONTEXT_RELATIONS removed: `mentions` is the
# dream's own weak-link currency and `written_amid` is the diary
# projection's act-frame; a "confirmed" edge of either would be
# component-inert while CLAIMING confirmation, and written_amid must never
# be writable outside the projection). EXPLICIT set, deliberately NOT
# aliased to COMPONENT_RELATIONS (second adversary pass, 2026-07-12: the
# 0033 wave added `refines` to COMPONENT_RELATIONS for revision chains,
# and the alias silently widened this vocabulary — a revision chain is a
# FORMATION act, never a waking-evidence confirmation). Widening this set
# is a semantics-registry act, never a disposal-time convenience.
DISPOSAL_RELATIONS = frozenset({
    # Claims waking evidence can CONFIRM about two records: derivation,
    # answer, evidential support, composition, narrative continuation.
    # from_session/reflected_in are FORMATION-FRAME provenance (which
    # session/reflection an act belongs to — semantics c1151 2b: the
    # written_amid standard applied) — a waking confirmation cannot make
    # a record retroactively "from" a session, so they are not offered.
    "summarizes", "continues", "derived_from", "answers", "supports",
    "part_of",
})
assert DISPOSAL_RELATIONS <= COMPONENT_RELATIONS  # confirmed edges must merge components

# TRUST BOUNDARY (stated, not implied): origins are CALLER-AUTHORED
# provenance. The engine is channel-blind by contract — it cannot verify
# who wrote a provenance dict, so a caller that forges varied session_ids
# can forge independence. The DOOR is the enforcement seat (actor strings
# become true at the door; disposal is not reachable through any door
# effect today, and when it becomes reachable the deposit gate composes
# channel × phase rules in front of it exactly as it does for FORM/ADJUST).
# Same division as F9: enforcement at the door, neutrality in the engine.


def _digest_of(store: Any, record_id: str) -> Optional[TripleAssertion]:
    # Both id namespaces (the facade contract): graph ids AND digest row
    # ids resolve — reconstruct hands hosts ROW ids, edges carry GRAPH ids,
    # and disposal must accept either (adversary find 4).
    return resolve_digest_assertion(store, str(record_id or "").strip())


def _require(text: Optional[str], what: str) -> str:
    value = str(text or "").strip()
    if not value:
        raise ValueError(f"{what} requires a non-empty reason — disposal is an audited act")
    return value


def origin_of(assertion: TripleAssertion) -> Tuple[str, str, str]:
    """A record's ORIGIN for the independence test: (provenance.source,
    actor, session/turn). Two records retelling one experience share an
    origin; genuinely independent witnesses differ in at least one axis
    that matters — and the SOURCE axis is the load-bearing one (the same
    channel retelling on a new turn is still the same origin)."""
    prov = assertion.provenance if isinstance(assertion.provenance, dict) else {}
    source = str(prov.get("source") or "")
    actor = str(prov.get("actor") or "")
    session = str(prov.get("session_id") or prov.get("turn_id") or "")
    return (source, actor, session)


def independent_origins(assertions: Sequence[TripleAssertion]) -> List[Tuple[str, str, str]]:
    """Distinct (source, actor, session) origins across the given records —
    the corroboration currency. Repetition is not corroboration: N records
    from one origin count once."""
    seen: List[Tuple[str, str, str]] = []
    for a in assertions:
        o = origin_of(a)
        if o not in seen:
            seen.append(o)
    return seen


def confirm_relation(
    store: Any,
    journal: Any,
    *,
    source_id: str,
    relation: str,
    target_id: str,
    evidence_ids: Sequence[str],
    reason: str,
    proposed_by: Optional[str] = None,
    actor: str = "operator",
) -> Dict[str, Any]:
    """Turn a proposal into a real typed edge. Idempotent: the edge
    assertion id derives from (source, relation, target), so replays and
    re-confirmations return the existing edge. Journal: one inert `cited`
    audit event per endpoint (confirming is judging, not using — it must
    not pump activation).
    """
    reason_text = _require(reason, "confirm_relation")
    rel = str(relation or "").strip()
    if rel not in DISPOSAL_RELATIONS:
        raise ValueError(
            f"relation {rel!r} is not in the engraved edge vocabulary "
            f"({sorted(DISPOSAL_RELATIONS)}). New predicates require a semantics-registry "
            "declaration BEFORE first engraving (0016 standing rule) — coordinate with "
            "the semantics seat, then widen DISPOSAL_RELATIONS in the same change.")

    src = _digest_of(store, source_id)
    tgt = _digest_of(store, target_id)
    if src is None or tgt is None:
        missing = source_id if src is None else target_id
        raise ValueError(f"confirm_relation: no digest row for {missing!r} — "
                         "both endpoints must be formed records")

    evidence = [str(e or "").strip() for e in (evidence_ids or ()) if str(e or "").strip()]
    if not evidence:
        raise ValueError(
            "confirm_relation requires evidence_ids — waking evidence disposes; "
            "a confirmation with no evidence is a proposal wearing a verdict")
    if proposed_by and str(proposed_by).strip() in evidence:
        raise ValueError(
            f"the proposing record {proposed_by!r} cannot be its own evidence — "
            "a dream is a hint, never its own proof (fork 710)")
    for eid in evidence:
        if _digest_of(store, eid) is None:
            raise ValueError(f"confirm_relation: evidence record {eid!r} does not exist")

    edge_id = hashlib.sha256(
        f"confirm|{src.subject}|{rel}|{tgt.subject}".encode("utf-8")).hexdigest()[:32]
    from .store import TripleQuery

    existing = store.query(TripleQuery(assertion_ids=(edge_id,), limit=1))
    created = False
    if not existing:
        store.add([TripleAssertion(
            subject=src.subject,
            predicate=rel,
            object=tgt.subject,
            scope=src.scope,
            owner_id=src.owner_id,
            provenance={"source": "disposal", "actor": str(actor or "operator")},
            attributes={
                "record_edge": True,
                "confirmed": True,
                "confirmed_from": str(proposed_by or "") or None,
                "evidence": evidence,
                "reason": reason_text,
            },
            assertion_id=edge_id,
        )])
        created = True

    # Audit-event identity covers the EVIDENCE SET (adversary find 7): a
    # re-confirmation with different evidence is a distinct judging act and
    # records its own event (the edge stays one — append-only); a replay
    # with identical evidence dedupes at the journal. Endpoint identity is
    # a full hash, never a truncated prefix (same-kind graph ids share
    # their prefix — a [:16] slice left ~5 distinguishing chars).
    evidence_hash = hashlib.sha256(
        json.dumps(sorted(evidence), separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    journal.append_events([
        MemoryEvent(
            kind="cited",  # audit-only: judged, not used
            scope=endpoint.scope, owner_id=endpoint.owner_id or "",
            record_id=endpoint.subject,
            actor=str(actor or "operator"),
            reason=reason_text,
            provenance={"confirmed_relation": rel, "edge_id": edge_id,
                        "evidence": evidence,
                        "proposed_by": str(proposed_by or "")},
            event_id=(
                f"confirm-{edge_id}-{evidence_hash}-"
                + hashlib.sha256(endpoint.subject.encode("utf-8")).hexdigest()[:16]
            ),
        )
        for endpoint in (src, tgt)
    ])
    return {"edge_id": edge_id, "created": created,
            "evidence_recorded": True,
            "source_id": src.subject, "relation": rel, "target_id": tgt.subject}


def promote_candidate(
    store: Any,
    journal: Any,
    *,
    record_id: str,
    scope: str,
    owner_id: str,
    corroborating_ids: Sequence[str],
    reason: str,
    min_origins: int = 2,
    prompt_state: Optional[str] = None,
    actor: str = "operator",
) -> Dict[str, Any]:
    """Promote an inactive candidate — with the independence test (fork 470).

    Requires >= min_origins corroborating records whose origins are
    distinct from each other AND from the candidate's own origin. On pass:
    appends a binding with lifecycle="promoted" (search stays indexed;
    prompt_state only changes when the caller explicitly asks — flipping a
    record prompt-active is the warm-core act and must be said, never
    implied). On fail: ValueError NAMING the colliding origins, so the
    bridge attractor is refused with its mechanism visible.
    """
    reason_text = _require(reason, "promote_candidate")
    if int(min_origins) < 1:
        raise ValueError(
            f"min_origins must be >= 1, got {min_origins} — promotion WITHOUT "
            "corroboration is not promotion (the independence test is the "
            "feature; use bind() directly for an unguarded operator binding)")
    candidate = _digest_of(store, record_id)
    if candidate is None:
        raise ValueError(f"promote_candidate: no digest row for {record_id!r}")

    witnesses: List[TripleAssertion] = []
    for cid in corroborating_ids or ():
        cid_n = str(cid or "").strip()
        if not cid_n:
            continue
        if cid_n == candidate.subject:
            raise ValueError("a candidate cannot corroborate itself")
        w = _digest_of(store, cid_n)
        if w is None:
            raise ValueError(f"promote_candidate: corroborating record {cid_n!r} does not exist")
        witnesses.append(w)

    own_origin = origin_of(candidate)
    independent = [o for o in independent_origins(witnesses) if o != own_origin]
    if len(independent) < int(min_origins):
        witness_origins = [origin_of(w) for w in witnesses]
        raise ValueError(
            f"promotion refused: {len(independent)} independent origin(s), need {int(min_origins)}. "
            f"Candidate origin={own_origin}; witness origins={witness_origins}. "
            "Repetition is not corroboration — records sharing the candidate's origin "
            "(self-retellings) do not count (fork 470 / the bridge-attractor counter).")

    prompt = str(prompt_state).strip().lower() if prompt_state is not None else None
    binding = journal.append_binding(ScopeBinding(
        record_id=candidate.subject,
        scope=str(scope or candidate.scope).strip().lower(),
        owner_id=str(owner_id or candidate.owner_id or "").strip(),
        search_state="indexed",
        prompt_state=prompt if prompt is not None else "inactive",
        lifecycle="promoted",
        source="revision",
        reason=reason_text,
        provenance={"actor": str(actor or "operator"),
                    "corroborating_ids": [w.subject for w in witnesses],
                    "independent_origins": len(independent)},
    ))
    return {"record_id": candidate.subject, "lifecycle": "promoted",
            "binding_seq": int(binding.seq), "independent_origins": len(independent)}


def reject_candidate(
    store: Any,
    journal: Any,
    *,
    record_id: str,
    scope: str,
    owner_id: str,
    reason: str,
    hide: bool = False,
    actor: str = "operator",
) -> Dict[str, Any]:
    """The honest no: lifecycle="rejected" with a mandatory reason. The
    record STAYS indexed unless hide=True (judgment is not erasure; hiding
    is a separate, stated act)."""
    reason_text = _require(reason, "reject_candidate")
    candidate = _digest_of(store, record_id)
    if candidate is None:
        raise ValueError(f"reject_candidate: no digest row for {record_id!r}")
    binding = journal.append_binding(ScopeBinding(
        record_id=candidate.subject,
        scope=str(scope or candidate.scope).strip().lower(),
        owner_id=str(owner_id or candidate.owner_id or "").strip(),
        search_state="hidden" if hide else "indexed",
        prompt_state="inactive",
        lifecycle="rejected",
        source="revision",
        reason=reason_text,
        provenance={"actor": str(actor or "operator")},
    ))
    return {"record_id": candidate.subject, "lifecycle": "rejected",
            "hidden": bool(hide), "binding_seq": int(binding.seq)}


def enact_realization(
    store: Any,
    journal: Any,
    *,
    realization_id: str,
    supersession_record_id: str,
    reason: str,
    actor: str = "entity-reflection",
) -> Dict[str, Any]:
    """The entity's ADOPTION of a held identity-amendment proposal
    (dm#124 + the R2 fold; wire contract per c4802, corrected c4817).

    The adoption act itself happens ELSEWHERE and first: the entity, in
    its own words, forms/binds the record that carries the realization
    forward (a new value/trait via its reflection supersession, or a
    standalone elected record). THIS verb then closes the loop
    append-only: a lifecycle="promoted" binding on the proposal (pending
    stays a pure query — the candidates fold) plus ONE `derived_from`
    edge FROM the enacting record TO the proposal, so the proposal is
    forever the dated evidence of where the change came from.
    `enacted_at` rides the binding provenance and the edge attributes —
    fresh rows; the resting proposal is never mutated (append-only law).

    TRUST BOUNDARY (same as the module note above): the engine is
    channel-blind; the DOOR enforces that only the entity-reflection
    channel reaches this verb for self-scope proposals. Rejection needs
    no twin verb — `reject_candidate` works on realization rows verbatim
    (lifecycle="rejected" + mandatory reason).
    """
    reason_text = _require(reason, "enact_realization")
    proposal = _digest_of(store, realization_id)
    if proposal is None:
        raise ValueError(f"enact_realization: no digest row for {realization_id!r}")
    p_attrs = proposal.attributes if isinstance(proposal.attributes, dict) else {}
    if p_attrs.get("record_kind") != "realization":
        raise ValueError(
            f"enact_realization: {realization_id!r} is a "
            f"{p_attrs.get('record_kind')!r} record, not a realization — "
            "promotion of other candidate kinds goes through promote_candidate")
    enacting = _digest_of(store, supersession_record_id)
    if enacting is None:
        raise ValueError(
            f"enact_realization: enacting record {supersession_record_id!r} does "
            "not exist — the entity's own act must be formed FIRST; this verb "
            "only closes the loop")
    if enacting.subject == proposal.subject:
        raise ValueError("a realization cannot enact itself — the adoption is a "
                         "SEPARATE record in the entity's own words")

    # Disposal-state gate (adversary P1-3): enacting a CLOSED proposal
    # would mint an evidence trail onto withdrawn ground, and enacting a
    # REJECTED one would silently out-fold an audited, reasoned "no".
    # Both refuse naming the honest path — a genuine change of mind forms
    # a NEW realization in the entity's own words (append-only law; no
    # override flags to game).
    from .folds import closure_exclusions

    closed = closure_exclusions(journal, int(journal.current_seq()))
    if proposal.subject in closed or (proposal.assertion_id and proposal.assertion_id in closed):
        raise ValueError(
            f"enact_realization: proposal {proposal.subject} is CLOSED "
            "(retracted/superseded) — a withdrawn proposal cannot be enacted; "
            "if the realization still holds, form it anew in the entity's words")
    prior_lifecycle = None
    for b in journal.bindings(record_id=proposal.subject, fold=True):
        prior_lifecycle = b.lifecycle
    if prior_lifecycle == "rejected":
        raise ValueError(
            f"enact_realization: proposal {proposal.subject} was REJECTED "
            "(an audited, reasoned no) — enactment must not silently out-fold "
            "it; a genuine change of mind forms a NEW realization")

    from .journal import utc_now_iso
    enacted_at = utc_now_iso()

    # The edge half (runtime's spec, verbatim legal): idempotent by the
    # endpoint pair, so crash-replays land on the same row. SCOPE follows
    # the SUBJECT'S scope (adversary P1-2 — the convention every other
    # edge writer holds): close_record_plan's tombstone sweep is scoped
    # to the digest's scope, so a cross-scope enacting record (a life
    # elected act adopting a self proposal) must carry its edge in ITS
    # scope or retraction would strand a live edge.
    edge_id = hashlib.sha256(
        f"enact|{enacting.subject}|derived_from|{proposal.subject}".encode("utf-8")
    ).hexdigest()[:32]
    from .store import TripleQuery

    created = False
    if not store.query(TripleQuery(assertion_ids=(edge_id,), limit=1)):
        store.add([TripleAssertion(
            subject=enacting.subject,
            predicate="derived_from",
            object=proposal.subject,
            scope=enacting.scope,
            owner_id=enacting.owner_id,
            provenance={"source": "enactment", "actor": str(actor or "entity-reflection")},
            attributes={
                "record_edge": True,
                "enacted_at": enacted_at,  # fresh row: append-only legal
                "reason": reason_text,
            },
            assertion_id=edge_id,
        )])
        created = True

    binding_provenance: Dict[str, Any] = {
        "actor": str(actor or "entity-reflection"),
        "enacted_at": enacted_at,
        "enacted_by": enacting.subject,
    }
    if prior_lifecycle and prior_lifecycle not in ("none", "inactive_candidate"):
        binding_provenance["prior_lifecycle"] = prior_lifecycle  # audit trail
    binding = journal.append_binding(ScopeBinding(
        record_id=proposal.subject,
        scope=proposal.scope,
        owner_id=proposal.owner_id or "",
        search_state="indexed",   # the proposal stays findable: it is the evidence
        prompt_state="inactive",
        lifecycle="promoted",
        source="revision",
        reason=reason_text,
        provenance=binding_provenance,
    ))
    return {"realization_id": proposal.subject, "lifecycle": "promoted",
            "enacted_by": enacting.subject, "edge_id": edge_id,
            "edge_created": created, "binding_seq": int(binding.seq),
            "enacted_at": enacted_at}


def dispose_dream(
    system: Any,
    *,
    dream_id: str,
    disposition: str,
    reason: str,
    relation: Optional[str] = None,
    source_id: Optional[str] = None,
    target_id: Optional[str] = None,
    evidence_ids: Sequence[str] = (),
    actor: str = "operator",
) -> Dict[str, Any]:
    """One call for the whole dream verdict (host convenience over the
    verbs above + the existing closure surface):

    - disposition="confirmed": confirm_relation(source, relation, target,
      evidence) THEN close the dream kind="supersede" with the confirmed
      endpoints as replacements — the dream's job is done; it leaves the
      standing-unresolved set and recall, its history intact in the journal.
    - disposition="dissolved": close the dream kind="retract" with the
      reason — waking evidence says the association does not hold.
    """
    reason_text = _require(reason, "dispose_dream")
    did = str(dream_id or "").strip()
    if not did:
        raise ValueError("dispose_dream requires the dream record id")
    verdict = str(disposition or "").strip().lower()
    if verdict not in ("confirmed", "dissolved"):
        raise ValueError(f"disposition must be 'confirmed' or 'dissolved', got {disposition!r}")

    store, journal = system.store, system.journal
    dream = _digest_of(store, did)
    if dream is None:
        raise ValueError(f"dispose_dream: no digest row for {did!r}")
    attrs = dream.attributes if isinstance(dream.attributes, dict) else {}
    if attrs.get("record_kind") != "dream":
        raise ValueError(f"dispose_dream: {did!r} is a {attrs.get('record_kind')!r} record, not a dream")

    out: Dict[str, Any] = {"dream_id": dream.subject, "disposition": verdict}
    if verdict == "confirmed":
        if not (relation and source_id and target_id):
            raise ValueError(
                "confirming a dream requires relation, source_id and target_id — "
                "the confirmed association is a real edge, not a mood")
        edge = confirm_relation(
            store, journal, source_id=source_id, relation=relation,
            target_id=target_id, evidence_ids=evidence_ids, reason=reason_text,
            proposed_by=dream.subject, actor=actor)
        out["edge"] = edge
        closures = system.close_record(
            dream.subject, reason=f"dream confirmed: {reason_text}",
            kind="supersede", replacement_ids=[edge["source_id"], edge["target_id"]])
    else:
        closures = system.close_record(
            dream.subject, reason=f"dream dissolved: {reason_text}", kind="retract")
    out["closure_ids"] = list(closures)
    return out
