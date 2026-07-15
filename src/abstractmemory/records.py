"""Typed memory records v1: input model, storage encoding, kind policy, payload.

The MINIMAL formation bridge to backlog 0021 (a2a 0001/009 addendum 1,
0001/011 ask 1): the runtime forms per-turn `verbatim ⇄ digest` records via
`MemorySystem.remember_many`, and this module owns everything derivable from
the inputs — validation (`MemoryRecordInput`), the deterministic v1 storage
encoding (ONE digest assertion per record + one assertion per edge), the
kind-priority policy (`ReconstructConfig`, consumed by reconstruct.py's 0020
ordering), and payload-tier resolution. Pure derivations + store READS only;
all writes stay in the facade.

v1 encoding decisions (replaced wholesale by 0021's registry-typed records):
- record_id = "ex:{kind}-{sha256(idempotency_key|position)[:26]}" — the "ex:"
  namespace marks pre-registry ids; deterministic so at-least-once replays
  re-derive identical ids (the runtime's idempotency_key + input position IS
  the identity).
- The digest is the assertion OBJECT (literal; case preserved) under
  "dcterms:abstract" — same predicate the seam already names for digests —
  so keyword/vector retrieval indexes the digest text with zero new store
  machinery. Title/intents/outcomes/keywords/payload_ref/topic ride
  `attributes` (host `attributes` merge UNDER them: reserved keys win).
- Edges are plain assertions record_id --relation--> target_record_id
  (attributes {"record_edge": True}). Relations are NOT vocabulary-validated
  in v1 (0016 owns validation); spreading walks them as-is because both
  terms are entity-like record ids.
- Full verbatim stays a HOST artifact reference (`payload_ref`): the package
  never fetches it — that is what keeps "no compaction" honest without
  bloating the triple store.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .canonical_text import handle_digest, token_estimate
# Diary conventions live in diary.py (definition home); re-exported here
# for compatibility (formation also derives the chain hash at encode time).
from .diary import diary_entry_hash, verify_diary_chain
from .journal import ClosureRecord, ScopeBinding, utc_now_iso
from .models import TripleAssertion
from .store import TripleQuery

__all__ = [
    "DIARY_TYPES",
    "FormationPlan",
    "INSTRUCTION_CATEGORIES",
    "KIND_RANKS",
    "LESSON_EVIDENCE_CLASSES",
    "MEMORY_RECORD_KINDS",
    "MemoryRecordInput",
    "ReconstructConfig",
    "VALUE_CLASSES",
    "apply_formation_plan",
    "build_formation_plan",
    "close_record_plan",
    "diary_entry_hash",
    "read_payload",
    "resolve_assertion_ids",
    "verify_diary_chain",
]

MEMORY_RECORD_KINDS = frozenset(
    {"memory", "episode", "lesson", "instruction", "decision", "claim",
     "summary", "question", "answer", "plan",
     # Identity kinds (a2a 0003, named-persistent-identity wave): who the
     # entity IS, distinct from what it has learned.
     "value", "purpose", "trait", "diary", "interest",
     # Sleep artifact (0023): the felt residue of consolidation — one per
     # pass, review-gated, never promotable to fact (consolidation.py).
     "dream",
     # Long-term orientation (0033, maintainer 2026-07-12): the refined
     # understanding of ONE target (person/object/location/time/problem/
     # idea/concept) across time — sleep-formed, source-linked,
     # revision-chained, ORIENTATION never authority (world_model.py).
     "world_model"}
)

# 0020 kind priority (lower rank orders earlier): identity kinds (value <
# purpose < trait, negative) outrank learned kinds — ONLY among
# channel-matched peers (kind is a TIE-BREAK behind relevance in the fill
# contract, so an unmatched value never evicts a matched episode). Among
# learned kinds distilled knowledge leads raw material; diary = episode
# peer, interest = summary peer; questions/claims trail; "memory" (and any
# plain untyped triple) is the raw baseline.
# Read-only mapping (review nit: a mutable public vocabulary dict invites
# in-place edits that no consumer can see; per-call tuning goes through
# ReconstructConfig.kind_rank, which copies this).
KIND_RANKS: Mapping[str, int] = MappingProxyType({
    "value": -3, "purpose": -2, "trait": -1,
    "lesson": 0, "instruction": 1, "decision": 2, "episode": 3, "diary": 3,
    # dream = summary peer (derived artifact; deliberately NOT the fork's
    # rank-0-loud — derived artifacts never gate or dominate recall here).
    # world_model = same derived-artifact band: orientation competes as a
    # summary peer, never outranking lessons or lived episodes (0033).
    "plan": 4, "summary": 5, "interest": 5, "dream": 5, "world_model": 5,
    "answer": 6, "question": 7, "claim": 8, "memory": 9,
})

# Identity-kind attribute conventions (validated at formation). "question"
# (curiosity, round 4), "problem" (something WRONG needing a fix, round
# 6 — distinct priority and emotional weight) and "commitment" (the
# entity's own remembered promise — prospective memory, accepted
# 2026-07-13) are first-class autonomy drivers: the heartbeat's "do I have
# open questions/problems/commitments?" is a wake reason, and resolved
# ones stay part of the story (diary.open_questions / open_problems /
# open_commitments).
VALUE_CLASSES = frozenset({"core", "revisable"})
DIARY_TYPES = frozenset({"note", "idea", "commitment", "reflection", "question", "problem"})

# Lesson-layer conventions (0035, maintainer 2026-07-12: lessons are
# "something actionable that can reference actual memories and serve as
# both distilled knowledge and wisdom — critical for the long term
# evolution of the entity"; fork 095 lineage). All OPTIONAL-but-validated:
# absence is honest, presence is checked. The evidence ladder is JUDGMENT
# data (presentation, disposal corroboration) — it never gates recall.
LESSON_EVIDENCE_CLASSES = frozenset(
    {"proposed", "single_source", "corroborated", "validated", "disputed"})
# Fork 490: a taught procedure is not a world lesson — rule (constraint),
# instruction (how-to), process (multi-step discipline).
INSTRUCTION_CATEGORIES = frozenset({"rule", "instruction", "process"})


def _str_tuple(values: Any) -> Tuple[str, ...]:
    return tuple(str(v).strip() for v in (values or ()) if str(v or "").strip())


@dataclass(frozen=True)
class MemoryRecordInput:
    """One record the runtime asks the package to remember (formation
    input). JSON-safe via dataclasses.asdict (tuples serialize as lists).
    The digest is the 1-3 sentence orientation text that gets embedded/
    indexed; intents/outcomes/keywords are the fork's selection metadata;
    edges link to EXISTING record ids ((relation, target_record_id))."""

    kind: str
    title: str
    digest: str
    intents: Tuple[str, ...] = ()
    outcomes: Tuple[str, ...] = ()
    keywords: Tuple[str, ...] = ()
    # WHO lived this memory (shared-context recall, maintainer round 5):
    # identity strings like "person:albou", "entity:castor" — the
    # participants channel matches them against Stimulus.participants.
    # CONVENTION (a2a 0007, ruled during Castor's first steps): co-presence
    # is EXPLICIT — the owning entity stamps ITSELF into its own records
    # (hosts/doors write entity:<id> alongside the other parties). The
    # engine never implies the owner: what a record SAYS is its full
    # co-presence, so records stay honest when they travel across scopes.
    participants: Tuple[str, ...] = ()
    edges: Tuple[Tuple[str, str], ...] = ()
    payload_ref: Optional[str] = None
    topic: Optional[str] = None
    confidence: Optional[float] = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        kind = str(self.kind or "").strip().lower()
        if kind not in MEMORY_RECORD_KINDS:
            raise ValueError(f"Unknown record kind {self.kind!r} (known: {sorted(MEMORY_RECORD_KINDS)})")
        object.__setattr__(self, "kind", kind)
        for name in ("title", "digest"):
            value = str(getattr(self, name) or "").strip()
            if not value:
                raise ValueError(f"MemoryRecordInput.{name} must be a non-empty string ({kind!r} record)")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "intents", _str_tuple(self.intents))
        object.__setattr__(self, "outcomes", _str_tuple(self.outcomes))
        object.__setattr__(self, "keywords", _str_tuple(self.keywords))
        object.__setattr__(self, "participants", _str_tuple(self.participants))

        edges: List[Tuple[str, str]] = []
        for e in self.edges or ():
            if not (isinstance(e, (tuple, list)) and len(e) == 2):
                raise ValueError(f"edges must be (relation, target_record_id) pairs, got {e!r}")
            relation, target = str(e[0] or "").strip(), str(e[1] or "").strip()
            if not relation or not target:
                raise ValueError(f"edges must be (relation, target_record_id) pairs, got {e!r}")
            edges.append((relation, target))
        object.__setattr__(self, "edges", tuple(edges))
        if kind == "summary" and not edges:
            raise ValueError(
                "summary records require at least one edge naming what they summarize "
                "(e.g. (\"summarizes\", <record_id>)) — a summary detached from its "
                "sources is unverifiable"
            )

        attributes = dict(self.attributes or {})
        if kind == "value":
            # Explicit by design: whether a value is core (identity-defining,
            # revision = identity event) or revisable is a DECISION the
            # author must make, never a silent default.
            value_class = str(attributes.get("value_class") or "").strip().lower()
            if value_class not in VALUE_CLASSES:
                raise ValueError(
                    "kind='value' requires attributes.value_class to be one of "
                    f"{sorted(VALUE_CLASSES)} (got {attributes.get('value_class')!r}) — "
                    "declare explicitly whether this value is core or revisable"
                )
            attributes["value_class"] = value_class
        if kind == "diary":
            # D4 FORM-gate (one-writer guarantee, memory-side half): diary
            # records must DECLARE their write channel — "diary-projection"
            # (the runtime book's memory-of-the-act) or "owner-direct"
            # (the scope OWNER's direct home writes, no book). WHO may use
            # each channel is the gateway deposit gate's job; the engine
            # enforces THAT a channel is declared.
            # NAMING (sign-off, laurent c398): "owner-direct" replaced
            # "entity-direct" while ZERO rows carried it (scan-verified —
            # engraved-class strings rename only inside that window); the
            # sole author of a diary is the SCOPE OWNER, the engine's own
            # noun. "entity-direct" is accepted AND CANONICALIZED to
            # "owner-direct" during the migration window (runtime's one
            # test site moves same-day, c395) so no old spelling ever
            # engraves from here on; the acceptance dies with the shims.
            source = str(dict(self.provenance or {}).get("source") or "").strip()
            if source == "entity-direct":
                source = "owner-direct"
                provenance = dict(self.provenance or {})
                provenance["source"] = source
                object.__setattr__(self, "provenance", provenance)
            if source not in ("diary-projection", "owner-direct"):
                raise ValueError(
                    "kind='diary' requires provenance.source to be 'diary-projection' "
                    "(runtime book projection) or 'owner-direct' (the scope owner's "
                    f"direct write) — got {source or None!r}. The diary has ONE writer "
                    "per plane; undeclared channels are refused (D4 form-gate)."
                )
            # Diary entries NEVER require edges (the first entry has none).
            # diary_type: ABSENT -> "note"; present-but-unknown -> LOUD (a
            # silent re-default would eat direct writers' typos).
            raw_type = attributes.get("diary_type")
            diary_type = "note" if raw_type is None else str(raw_type or "").strip().lower()
            if diary_type not in DIARY_TYPES:
                raise ValueError(
                    f"kind='diary' attributes.diary_type must be one of {sorted(DIARY_TYPES)} "
                    f"(got {raw_type!r}); omit the key entirely for the default 'note'"
                )
            attributes["diary_type"] = diary_type
            # Dual-plane projection attributes (the runtime's BOOK is the
            # attested original; these records are the MEMORY of the book):
            # entry_id names the book's chain entry — light validation
            # (non-empty when present; REQUIRED for projections so the
            # graph can verify against the book).
            entry_id = attributes.get("entry_id")
            if entry_id is not None and not (isinstance(entry_id, str) and entry_id.strip()):
                raise ValueError(
                    f"kind='diary' attributes.entry_id must be a non-empty string when present "
                    f"(got {entry_id!r}) — it names the book's chain entry"
                )
            # Question/problem/commitment resolution mirrors heal/break
            # (append-only): an entry ANSWERING a question references it via
            # attributes.answers; one RESOLVING a problem via
            # attributes.resolves; one FULFILLING a commitment via
            # attributes.fulfills (graph record id or book entry_id).
            for ref_attr, target_kind in (("answers", "question"), ("resolves", "problem"),
                                          ("fulfills", "commitment")):
                ref = attributes.get(ref_attr)
                if ref is not None and not (isinstance(ref, str) and ref.strip()):
                    raise ValueError(
                        f"kind='diary' attributes.{ref_attr} must be a non-empty string when "
                        f"present (got {ref!r}) — it references the {target_kind} record id "
                        "or entry_id it resolves"
                    )
            if str(dict(self.provenance or {}).get("source") or "") == "diary-projection" and entry_id is None:
                raise ValueError(
                    "diary projections (provenance.source='diary-projection') must carry "
                    "attributes.entry_id — the graph record must be verifiable against the book"
                )

        if kind in ("lesson", "instruction"):
            # 0035 conventions — optional-but-validated (absence is honest;
            # presence is checked; nothing here ever gates recall):
            # applies_when/caveats normalize to string tuples and
            # applies_when tokens JOIN the keywords (findability: a lesson
            # about "sqlite migrations" surfaces when migrations come up —
            # plumbing tokenization, never cognition filtering).
            for field_name in ("applies_when", "caveats"):
                raw = attributes.get(field_name)
                if raw is None:
                    continue
                values = (raw,) if isinstance(raw, str) else raw
                if not isinstance(values, (list, tuple)) or not all(
                        isinstance(v, str) and v.strip() for v in values):
                    raise ValueError(
                        f"kind={kind!r} attributes.{field_name} must be a non-empty "
                        f"string or a list of non-empty strings (got {raw!r})"
                    )
                attributes[field_name] = [str(v).strip() for v in values]
            if attributes.get("applies_when"):
                from .text_tokens import tokenize

                applicability_tokens = tokenize(" ".join(attributes["applies_when"]))
                if not applicability_tokens:
                    # tokenize()'s own contract: zero tokens for non-Latin
                    # text must be LABELED by the caller — a lesson whose
                    # applicability adds no findability should say so
                    # rather than silently no-op (adversary P2).
                    import warnings as _warnings

                    _warnings.warn(
                        "#FALLBACK: applies_when yielded no recall tokens "
                        f"(non-Latin or too short: {attributes['applies_when']!r}) "
                        "— the lesson gains no applicability findability",
                        RuntimeWarning, stacklevel=2)
                merged = list(self.keywords)
                for token in sorted(applicability_tokens):
                    if token not in merged:
                        merged.append(token)
                object.__setattr__(self, "keywords", tuple(merged))
            evidence_class = attributes.get("evidence_class")
            if evidence_class is not None:
                normalized = str(evidence_class or "").strip().lower()
                if normalized not in LESSON_EVIDENCE_CLASSES:
                    raise ValueError(
                        f"attributes.evidence_class must be one of "
                        f"{sorted(LESSON_EVIDENCE_CLASSES)} (got {evidence_class!r}); "
                        "omit the key for an unlabeled lesson"
                    )
                attributes["evidence_class"] = normalized
        if kind == "instruction":
            category = attributes.get("category")
            if category is not None:
                normalized = str(category or "").strip().lower()
                if normalized not in INSTRUCTION_CATEGORIES:
                    raise ValueError(
                        f"kind='instruction' attributes.category must be one of "
                        f"{sorted(INSTRUCTION_CATEGORIES)} (got {category!r}); "
                        "omit the key for an uncategorized instruction"
                    )
                attributes["category"] = normalized
        object.__setattr__(self, "attributes", attributes)

        if self.payload_ref is not None:
            ref = str(self.payload_ref).strip()
            object.__setattr__(self, "payload_ref", ref if ref else None)
        if self.topic is not None:
            topic = str(self.topic).strip()
            object.__setattr__(self, "topic", topic if topic else None)
        if self.confidence is not None:
            object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "attributes", dict(self.attributes or {}))
        object.__setattr__(self, "provenance", dict(self.provenance or {}))


def _derived_hex(payload: str, length: int) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def record_id_for(kind: str, idempotency_key: str, position: int) -> str:
    return f"ex:{kind}-{_derived_hex(f'{idempotency_key}|{position}', 26)}"


@dataclass(frozen=True)
class FormationPlan:
    """Everything remember_many writes, fully derived before any I/O."""

    record_ids: Tuple[str, ...]
    assertions: Tuple[TripleAssertion, ...]      # digest + edge assertions, input order
    bindings: Tuple[ScopeBinding, ...]           # one per record, deterministic ids
    assertion_ids: Tuple[str, ...]               # for the idempotency pre-check


def build_formation_plan(
    records: Sequence[MemoryRecordInput],
    *,
    scope: str,
    owner_id: str,
    idempotency_key: str,
    turn_id: Optional[str] = None,
) -> FormationPlan:
    """Encode records into deterministic assertions + bindings (no I/O).

    Identity: every assertion_id/binding_id derives from (idempotency_key,
    position, role) — replays re-derive byte-identical ids so the store
    pre-check and the journal's supplied-id dedup turn them into no-ops.
    turn_id (0001/011 ask 4) rides provenance on every derived row.
    """
    key = str(idempotency_key or "").strip()
    if not key:
        raise ValueError(
            "remember_many requires a non-empty idempotency_key — it is the batch identity "
            "that makes at-least-once replays no-ops (empty keys would collide across turns)"
        )
    scope_n = str(scope or "").strip().lower()
    if not scope_n:
        raise ValueError("remember_many requires a non-empty scope")
    items = list(records or ())
    if not items:
        raise ValueError("remember_many requires at least one MemoryRecordInput (skip the call instead)")
    for r in items:
        if not isinstance(r, MemoryRecordInput):
            raise TypeError(f"remember_many expects MemoryRecordInput instances, got {type(r).__name__}")

    # All ids first: batch-internal edge refs ("local:<i>") need every
    # position's graph id before any edge resolves (realistic fix — without
    # this, same-batch links forced hosts into sequential remember() calls).
    record_ids: List[str] = [record_id_for(r.kind, key, i) for i, r in enumerate(items)]

    def _edge_target(target: str, position: int) -> str:
        if not target.startswith("local:"):
            return target
        try:
            index = int(target[len("local:"):])
        except ValueError:
            raise ValueError(f"invalid batch-internal edge target {target!r} (expected 'local:<index>')")
        if not (0 <= index < len(items)):
            raise ValueError(
                f"batch-internal edge target {target!r} is out of range (batch has {len(items)} records)")
        if index == position:
            raise ValueError(f"record at position {position} cannot edge-reference itself ({target!r})")
        return record_ids[index]

    assertions: List[TripleAssertion] = []
    bindings: List[ScopeBinding] = []
    for position, r in enumerate(items):
        rid = record_ids[position]
        observed_at = utc_now_iso()  # fixed here: the diary hash must cover the stored value

        # Host attributes merge UNDER the reserved keys (reserved win): the
        # enrichment path (reconstruct/payload) must be able to trust them.
        attrs: Dict[str, Any] = dict(r.attributes)
        attrs.update({"literal": True, "record_kind": r.kind, "title": r.title})
        for name, values in (("intents", r.intents), ("outcomes", r.outcomes),
                             ("keywords", r.keywords), ("participants", r.participants)):
            if values:
                attrs[name] = list(values)
        if r.payload_ref is not None:
            attrs["payload_ref"] = r.payload_ref
        if r.topic is not None:
            attrs["topic"] = r.topic

        provenance: Dict[str, Any] = dict(r.provenance)
        if turn_id:
            provenance["turn_id"] = str(turn_id).strip()

        # Diary hash chain (identity wave §7): when the caller supplies
        # prev_entry_hash (entity-direct writes), the entry's content hash
        # is derived over encoding-time observed_at and stored;
        # verify_diary_chain() audits it later.
        if r.kind == "diary" and "prev_entry_hash" in attrs:
            attrs["entry_hash"] = diary_entry_hash(r.title, r.digest, observed_at)

        assertions.append(
            TripleAssertion(
                subject=rid,
                predicate="dcterms:abstract",
                object=r.digest,
                scope=scope_n,
                owner_id=owner_id,
                observed_at=observed_at,
                confidence=r.confidence,
                provenance=provenance,
                attributes=attrs,
                assertion_id=_derived_hex(f"{key}|{position}|digest", 32),
            )
        )
        for relation, raw_target in r.edges:
            target = _edge_target(raw_target, position)
            assertions.append(
                TripleAssertion(
                    subject=rid,
                    predicate=relation,  # NOT vocabulary-validated in v1 (0016)
                    object=target,
                    scope=scope_n,
                    owner_id=owner_id,
                    provenance=dict(provenance),
                    attributes={"record_edge": True},
                    # Identity derives from the RESOLVED target so a replay
                    # via "local:<i>" and a replay via the concrete graph id
                    # dedupe to the same assertion.
                    assertion_id=_derived_hex(f"{key}|{position}|edge|{relation}|{target}", 32),
                )
            )
        bindings.append(
            ScopeBinding(
                record_id=rid,
                scope=scope_n,
                owner_id=owner_id,
                search_state="indexed",
                prompt_state="inactive",
                lifecycle="inactive_candidate",  # formed, awaiting review/election (0017 lifecycle)
                source="remember",
                reason=None,
                provenance=dict(provenance),
                binding_id=_derived_hex(f"{key}|{position}|binding", 32),
            )
        )
    return FormationPlan(
        record_ids=tuple(record_ids),
        assertions=tuple(assertions),
        bindings=tuple(bindings),
        assertion_ids=tuple(a.assertion_id for a in assertions if a.assertion_id),
    )


def resolve_digest_assertion(store: Any, record_id: str) -> Optional[TripleAssertion]:
    """Resolve a record's DIGEST assertion from either id namespace.

    Formed record_ids ("ex:kind-…") are assertion SUBJECTS, not assertion
    ids — resolve via (subject=record_id, predicate="dcterms:abstract").
    Plain triples (v1 degenerate records: record_id == assertion_id) resolve
    by assertion id. Try the direct id first (cheap, exact), then the
    subject path; newest wins if a host wrote several digest assertions.
    """
    rid = str(record_id or "").strip()
    if not rid:
        return None
    for row in store.query(TripleQuery(assertion_ids=(rid,), limit=1)):
        if row.assertion_id == rid:
            return row
    rows = store.query(TripleQuery(subject=rid, predicate="dcterms:abstract", limit=1))
    return rows[0] if rows else None


def resolve_assertion_ids(store: Any, ids: Sequence[str]) -> Dict[str, str]:
    """Map caller-supplied ids — digest-ASSERTION ids or GRAPH record ids
    (ex:… subjects) — to the assertion ids the journal/retrieval key on.

    The two-namespace boundary is load-bearing (a2a 0001/008; hostile-audit
    repro2): a graph id sent to an id-taking seam call used to deposit
    events under a key no handle ever carries — a silent no-op. Every
    id-taking facade call now resolves through here: known assertion ids map
    to themselves, graph ids map to their digest assertion id, anything else
    raises naming the id and BOTH namespaces (works-or-loud, never silent).
    Returns {original_id: resolved_assertion_id} preserving caller keys.
    """
    wanted = [str(i or "").strip() for i in (ids or ()) if str(i or "").strip()]
    if not wanted:
        return {}
    rows = store.query(TripleQuery(assertion_ids=tuple(dict.fromkeys(wanted)), limit=0))
    known = {a.assertion_id for a in rows if isinstance(a.assertion_id, str) and a.assertion_id}
    resolved: Dict[str, str] = {}
    for rid in wanted:
        if rid in known:
            resolved[rid] = rid
            continue
        digest = resolve_digest_assertion(store, rid)
        if digest is not None and digest.assertion_id:
            resolved[rid] = digest.assertion_id
            continue
        raise ValueError(
            f"unknown record id {rid!r}: neither a store assertion id nor a graph record id "
            "(a subject with a dcterms:abstract digest assertion). Pass handle.record_id "
            "(assertion id) or the id remember_many returned (graph id)."
        )
    return resolved




def apply_formation_plan(store: Any, journal: Any, plan: "FormationPlan") -> List[str]:
    """Idempotent formation writes (facade delegate): store pre-check +
    OR IGNORE skip existing assertions; bindings replay as journal no-ops
    via supplied ids. No attention event: forming is not using (0018)."""
    existing = {
        a.assertion_id for a in store.query(TripleQuery(assertion_ids=plan.assertion_ids, limit=0))
    }
    missing = [a for a in plan.assertions if a.assertion_id not in existing]
    if missing:
        store.add(missing)
    for binding in plan.bindings:
        journal.append_binding(binding)
    return list(plan.record_ids)


def close_record_plan(
    store: Any, record_id: str, *, kind: str, replacement_ids: Sequence[str], reason: str
) -> List[ClosureRecord]:
    """ONE belief-revision act for a whole record: closure records for its
    digest assertion AND every edge assertion it owns (subject == graph id,
    attributes.record_edge). Without this, retracting a record's digest left
    its edges alive — tombstone edges kept routing spreading activation
    through a dead record (hostile-audit repro5). IDEMPOTENCY KEY (0001/015):
    closure_id = sha256(f"{graph_id}|{kind}|{assertion_id}|closure")[:32] —
    reason, replacement_ids, and timestamps NEVER enter the key, so
    at-least-once replays (even with a drifted reason) dedupe at the journal
    and return the original closures.
    Accepts either id namespace; plain triples close as a single assertion.
    """
    rid = str(record_id or "").strip()
    digest = resolve_digest_assertion(store, rid) if rid else None
    if digest is None or not digest.assertion_id:
        raise ValueError(
            f"close_record: unknown record id {rid!r} (neither an assertion id nor a "
            "graph record id with a digest assertion)"
        )
    graph_id = digest.subject
    targets = [digest.assertion_id]
    for a in store.query(TripleQuery(subject=graph_id, scope=digest.scope,
                                     owner_id=digest.owner_id or None, limit=0)):
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        if attrs.get("record_edge") and a.assertion_id and a.assertion_id not in targets:
            targets.append(a.assertion_id)
    return [
        ClosureRecord(
            assertion_id=aid, kind=kind, reason=reason,
            replacement_ids=tuple(replacement_ids or ()),
            closure_id=_derived_hex(f"{graph_id}|{kind}|{aid}|closure", 32),
        )
        for aid in targets
    ]


def read_payload(store: Any, record_id: str, tier: str) -> Dict[str, Any]:
    """Pure payload read at a fidelity tier (facade delegates here).

    digest -> the canonical text (exactly what handle.digest carries).
    raw    -> the HOST artifact reference from attributes.payload_ref with
              content=None: the package never fetches verbatim payloads —
              the runtime resolves the ref against its ArtifactStore.
    Diary projections additionally carry "entry_id" (the runtime book's
    chain entry) in BOTH tiers — progressive disclosure: recall surfaces
    the projection, entry_id points into the book, the host fetches the
    verbatim entry via the runtime's diary_read.
    """
    a = resolve_digest_assertion(store, record_id)
    if a is None:
        raise ValueError(f"payload: record id not found in the store: {record_id}")
    attrs = a.attributes if isinstance(a.attributes, dict) else {}
    out: Dict[str, Any]
    if tier == "digest":
        content = handle_digest(a)  # clean literal for formed records (v2)
        out = {"record_id": record_id, "tier": "digest", "content": content,
               "token_estimate": token_estimate(content)}
    else:  # tier == "raw" (the facade routes summary/compact/unknown before us)
        ref = str(attrs.get("payload_ref") or "").strip()
        if not ref:
            raise ValueError(
                f"payload: record {record_id} has no raw tier (no attributes.payload_ref); "
                "only its digest is stored — form records with payload_ref to keep verbatim reachable"
            )
        out = {"record_id": record_id, "tier": "raw", "payload_ref": ref,
               "content": None, "token_estimate": None}
    entry_id = attrs.get("entry_id")
    if isinstance(entry_id, str) and entry_id.strip():
        out["entry_id"] = entry_id.strip()
    return out


@dataclass(frozen=True)
class ReconstructConfig:
    """Kind policy for reconstruction ordering (0020 kind priority).

    kind_of reads the v1 record encoding (attributes.record_kind); plain
    untyped triples fall back to "memory" — the raw baseline. rank_of maps
    kinds to KIND_RANKS (lower orders earlier; unknown kinds get
    default_kind_rank so future kinds degrade to baseline, never crash).
    Lives with the record model so kind semantics have ONE home; re-exported
    by reconstruct.py for compatibility.
    """

    default_kind: str = "memory"
    kind_rank: Mapping[str, int] = field(default_factory=lambda: dict(KIND_RANKS))
    default_kind_rank: int = 100
    # Vector-channel absolute floor (audit f3): cosines below this are
    # clipped BEFORE max-normalization, so the "best of nothing" can never
    # be crowned score 1.0.
    vector_floor: float = 0.05
    # Relative floor margin (realistic-embedder fix): effective floor =
    # max(vector_floor, median(fetched cosines) + vector_margin). Real
    # embedders (qwen-class) put UNRELATED pairs at ~0.35-0.5 cosine, so the
    # absolute floor alone never fires; the median estimates that baseline.
    vector_margin: float = 0.08
    # Confidence span (0002 decay-regression fix): vector relevance is
    # confidence-scaled — scale = clamp((cos_max - floor_eff)/span, 0, 1) —
    # so the best of a WEAK field no longer normalizes to 1.0. 0.25 tuned
    # empirically on BOTH embedders: genuinely-strong matches still read 1.0
    # (harness bag-of-tokens tops 0.38-0.83 vs floor 0.05 → scale clamps at
    # 1; qwen tops sit 0.10-0.24 above the median+margin floor → strong
    # cues ~0.8-1.0), while the regression's weak field (top cosine 0.246,
    # floor 0.05) reads 0.78 instead of a crowned 1.0 and genuinely weak
    # qwen fields (top barely over the relative floor) fall to ~0.1-0.4.
    confidence_span: float = 0.25
    # STM eligibility bar (union model): default base-activation floor when
    # RecallBudget.stm_floor is None. 1.0 ≈ "used at least once recently on
    # the activity axis" after decay.
    stm_floor: float = 1.0
    # Concept anchoring (fork memory_anchor.rs port, 2026-07-12): edge-free
    # associative expansion from channel-matched seeds. OFF by default —
    # passive recall keeps its golden byte-stability; hosts opt in here,
    # and probe() runs the pass with expansion ON by its own default.
    # concept_tuning is typed Any to keep the records module import-light
    # (the real type is concept_anchor.ConceptAnchorTuning; None = defaults).
    concept_expansion: bool = False
    concept_tuning: Any = None
    # Keyword DISCOVERY (0019's FTS5 half): when True and the store carries
    # the FTS5 index, the keyword channel also SEARCHES the store (per scope
    # pair, budget-bounded) instead of only re-scoring the gathered
    # universe. OFF by default for the same golden byte-stability reason as
    # concept_expansion; probe() turns it on by its own default (the
    # deliberate reach is where discovery earns its tokens).
    keyword_discovery: bool = False

    def kind_of(self, assertion: TripleAssertion) -> str:
        attrs = assertion.attributes if isinstance(assertion.attributes, dict) else {}
        kind = attrs.get("record_kind")
        if isinstance(kind, str) and kind.strip():
            return kind.strip().lower()
        return self.default_kind

    def rank_of(self, kind: str) -> int:
        try:
            return int(self.kind_rank.get(kind, self.default_kind_rank))
        except (TypeError, ValueError):
            return self.default_kind_rank
