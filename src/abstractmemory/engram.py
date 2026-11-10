"""The engram pass: spark → identity records + prompt-active self bindings.

One task (the keystone experiment's missing piece, a2a 0003): turn a linted
spark into the entity's always-warm identity core — value/purpose/trait
records formed via remember_many, each bound prompt-active so the SELF
admission component (self_fraction) surfaces them on every reconstruction.

V1 IS FOR LIFE (maintainer correction, 2026-07-07): the spark is engrammed
ONCE and kept — "if you were born as v1, you should keep v1... it's part of
your identity." Identity evolution is EXPERIENTIAL and entity-owned
(revisable-value revision through the entity's own reflection, interests,
traits, lessons) — never spark rewrites. Re-engramming a new version is an
EXCEPTIONAL REPAIR reserved for a defective/harmful core; the guards below
keep that rare repair orderly (no dual cores mid-repair), they are not an
amendment lifecycle.

HOW LIVING IDENTITY EVOLVES (record-level, maintainer round 4): the entity
revises a value by CLOSING the old record (append-only revision) + forming
the new one + binding it into the reserved seats. Current reads
(self_records, the self component) render only the newest — closure folds
guarantee it — and NOTHING is lost: the journal's time axis IS the
versioning ("what did I believe/feel at time T" = as-of reads;
reconstruct(Stimulus(as_of=...)) folds closures/bindings to that anchor).
The spark stays the birth certificate.

IDEMPOTENT + GUARDED: the whole pass derives from a canonical spark hash.
Re-running the SAME spark is a complete no-op (remember_many + binding
dedup re-derive identical ids); a MODIFIED spark under the SAME version is
REFUSED via a marker record — identity does not silently drift; a HIGHER
version is refused while the born core remains prompt-active.

NO diary entry is written here BY DESIGN: the birth reflection is
entity-authored (first-person, through the home diary channel, host-side) —
the engram is the operator planting the seed, not the entity's first word.

TITLES ARE AUTHORED, NEVER A LABEL (operator rule 2026-11-09/10: every
memory's title and summary is authored; castor carries two "trait-0" from
2026-07-07). A spark item's `name` is its explicit title, kept as given (the
operator's words: the row reads operator `spark-v<N>`). An item without one
gets its title authored BEFORE formation by the host's `author(kind, body,
context)` callable (formation_authoring, the passes' contract; `body` = the
item's statement, `context["pass"]` = "engram"); a failure, or no `author`,
forms the record PENDING (title None, its `title.author` task, the failure
in `attributes.pending.failure`) and the night's repair writes it. The
summary is never asked for: an identity record's summary IS the spark
statement, the operator's words, a protected body (never rewritten, never
pending). This version never writes the legacy labels `value-N` /
`purpose-N` / `trait-N` / `limit-N`; homes born earlier carry them and the
host's sleep repair treats them as placeholders (docs/api.md names the
exact pattern).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .formation_authoring import AuthorFn, author_and_shape, new_receipt, note
from .records import MemoryRecordInput, record_id_for, resolve_digest_assertion
from .spark import canonical_spark_hash, lint_spark
from .store import TripleQuery

__all__ = ["EngramResult", "engram"]


@dataclass(frozen=True)
class EngramResult:
    """What one engram pass produced (or found already present)."""

    record_ids: Dict[str, Tuple[str, ...]] = field(default_factory=dict)  # section -> graph ids
    binding_ids: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    created: bool = True  # False = the same spark was already engrammed (no-op)
    # The titles this pass authored and the ones it left pending, with why (formation_authoring's receipt shape:
    # {authored: [{record_id, record_kind, pass, fields}], failures: [{record_id, record_kind, pass, fields, reason,
    # error_class, message, at}]}); the host writes its authoring-failures line from `failures`. Empty on a replay.
    authoring: Dict[str, Any] = field(default_factory=new_receipt)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_ids": {k: list(v) for k, v in self.record_ids.items()},
            "binding_ids": list(self.binding_ids),
            "warnings": list(self.warnings),
            "created": self.created,
            "authoring": {"authored": [dict(x) for x in self.authoring.get("authored") or ()],
                          "failures": [dict(x) for x in self.authoring.get("failures") or ()]},
        }


def _items(spark: Mapping[str, Any], section: str) -> List[Mapping[str, Any]]:
    return [x for x in (spark.get(section) or ()) if isinstance(x, Mapping)]


def engram(
    system: Any,  # MemorySystem (typed Any to avoid a circular import)
    spark: Mapping[str, Any],
    *,
    scope: str = "self",
    owner_id: str,
    spark_artifact_ref: Optional[str] = None,
    author: Optional[AuthorFn] = None,
) -> EngramResult:
    """Engram one spark into (scope, owner_id). Lint ERRORS abort; lint
    warnings ride the result. Records per section: values → kind="value"
    (attributes.value_class from the item's class), purposes →
    kind="purpose", traits → kind="trait", honesty → kind="trait" with
    attributes.trait_class="limit". Each carries precedence (ordinal),
    spark_version, and payload_ref=spark_artifact_ref (the attested spark
    document, when the host stored one). NO edges at engram time —
    relationships come from experience, not from the seed.

    TITLES: an item's `name` is its title, as given. An item without one has
    its title authored by `author(kind, body, context)` before it forms
    (`formation_authoring`: kind = the record kind, body = the statement,
    context = {pass: "engram", record_kind, scope, owner_id, fields:
    ["title"], title: None, source_ids: [], attributes}); a failure or no
    `author` forms it pending (`title.author` task, `pending.failure`
    reason `author_raised` / `invalid_result` / `no_author_supplied`), so
    such a spark needs a home opened with `task_queue=True` unless every
    title is authored. A record already formed (a replay) is never authored
    again. `EngramResult.authoring` is the receipt.
    """
    issues = lint_spark(spark)
    errors = [i for i in issues if i.startswith("ERROR")]
    if errors:
        raise ValueError("engram aborted — spark lint errors:\n" + "\n".join(errors))
    warnings = tuple(i for i in issues if not i.startswith("ERROR"))

    version = int(spark.get("spark", 1) or 1)
    spark_hash = canonical_spark_hash(spark)
    key = f"engram|{owner_id}|spark-v{version}|{spark_hash[:16]}"

    # THE VERSION GUARDS: one marker claim per (owner, version). Same
    # version + same hash → replay (proceed; everything downstream no-ops).
    # Same version + different hash → a modified spark — refuse loudly.
    # G8 (v1-for-life): a HIGHER version is refused while the born core
    # remains prompt-active — re-engram is an exceptional REPAIR for a
    # defective core, and even a repair must never leave BOTH cores in the
    # working set (the self admission does not version-filter).
    marker_title = f"spark-engram v{version}"
    existing_marker = None
    prior_versions: List[int] = []
    for a in system.query(TripleQuery(scope=scope, owner_id=owner_id, limit=0)):
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        if attrs.get("record_kind") != "claim":
            continue
        title = str(attrs.get("title") or "")
        if title == marker_title:
            existing_marker = a
        elif title.startswith("spark-engram v"):
            try:
                prior_versions.append(int(attrs.get("spark_version")))
            except (TypeError, ValueError):
                continue
    if existing_marker is not None:
        prior_hash = str(existing_marker.attributes.get("spark_hash") or "")
        if prior_hash != spark_hash:
            raise ValueError(
                f"spark v{version} already engrammed for owner {owner_id!r} with DIFFERENT "
                "content — a spark is kept for life and identity does not silently "
                "drift; identity evolves experientially (the entity's own revision of "
                "revisable values), never by spark rewrite"
            )
    for prior in sorted(v for v in prior_versions if v < version):
        if system.self_records(scope=scope, owner_id=owner_id, spark_version=prior):
            raise ValueError(
                f"spark v{prior} is engrammed and prompt-active; a spark is kept for "
                "life — re-engramming is an exceptional repair for a defective core "
                f"(retire the v{prior} records first: close + rebind inactive)"
            )

    sections: List[Tuple[str, str, List[Mapping[str, Any]]]] = [
        ("values", "value", _items(spark, "values")),
        ("purposes", "purpose", _items(spark, "purposes")),
        ("traits", "trait", _items(spark, "traits")),
        ("honesty", "trait", _items(spark, "honesty")),
    ]
    inputs: List[MemoryRecordInput] = [MemoryRecordInput(
        kind="claim",
        title=marker_title,
        digest=f"Spark v{version} engrammed for {owner_id} (hash {spark_hash[:16]}).",
        # bookkeeping=True keeps the marker OFF working-set shelves (it is
        # engine bookkeeping, not a memory — surfacing it as fill was
        # cosmetic noise); it stays fully queryable via layer-1 query(),
        # which is exactly how the version guards above scan for it.
        attributes={"spark_hash": spark_hash, "spark_version": version, "bookkeeping": True},
        payload_ref=spark_artifact_ref,
    )]
    plan: List[Tuple[str, int]] = [("marker", 0)]  # section, ordinal (marker rides position 0)
    # An item without a `name` has its title AUTHORED before it forms (operator rule: a title is authored, never a
    # placeholder; the `<section>-<ordinal>` labels this pass minted until 2026-11-10 are gone). `got` per input
    # position: what the author gave (or the recorded failure), None for a named item and for a replayed record.
    authored: Dict[int, Any] = {}
    for section, kind, items in sections:
        for ordinal, item in enumerate(items):
            attributes: Dict[str, Any] = {"precedence": ordinal, "spark_version": version}
            if section == "values":
                attributes["value_class"] = str(item.get("class") or "")
            if section == "honesty":
                attributes["trait_class"] = "limit"
            digest = str(item.get("statement") or "")
            title = str(item.get("name") or "").strip()
            position = len(inputs)
            if title:  # the spark's own title, as given
                record = MemoryRecordInput(kind=kind, title=title, digest=digest, attributes=attributes,
                                           payload_ref=spark_artifact_ref)
            else:
                record = MemoryRecordInput(kind=kind, title=None, digest=digest, attributes=attributes,
                                           payload_ref=spark_artifact_ref, pending=("title",))
                stored = resolve_digest_assertion(system.store, record_id_for(kind, key, position))
                if stored is not None:
                    # A REPLAY: the record stands and is never authored again. Its input repeats what is stored
                    # (its title, or still pending), so the formation re-derives no task it does not already have.
                    stored_title = str((stored.attributes or {}).get("title") or "").strip()
                    if stored_title:
                        record = MemoryRecordInput(kind=kind, title=stored_title, digest=digest,
                                                   attributes=attributes, payload_ref=spark_artifact_ref)
                else:
                    record, authored[position] = author_and_shape(
                        author, "engram", record, scope=scope, owner_id=owner_id, fields=("title",))
            inputs.append(record)
            plan.append((section, ordinal))

    all_ids = system.remember_many(inputs, scope=scope, owner_id=owner_id, idempotency_key=key)
    receipt = new_receipt()
    for position, got in sorted(authored.items()):
        note(receipt, "engram", inputs[position], got, all_ids[position])

    # BIRTH STRICTNESS (wave-4b adversary P1-1, live-repro'd): formation
    # now DEGRADES to vectorless on a dead embedder (the mid-life amnesia
    # fix) — but a birth is not a mid-life turn. A vectorless identity
    # core under a PINNED embedding space is a failed birth locked in by
    # idempotency (the re-run is a designed no-op), so the engram REFUSES
    # here, loudly, with both repair paths named. Pinless stores pass:
    # vectorless homes are a legal, deliberate mode — the pin is the
    # declaration that vectors were expected.
    store = system.store
    if callable(getattr(store, "embedding_pin", None)) and store.embedding_pin() is not None:
        probe_id = next((gid for (section, _o), gid in zip(plan, all_ids)
                         if section != "marker"), None)
        if probe_id is not None:
            digest_row = resolve_digest_assertion(store, probe_id)
            reader = getattr(store, "stored_vector", None)
            if (digest_row is not None and callable(reader)
                    and reader(digest_row.assertion_id) is None):
                raise ValueError(
                    "engram refused: the identity core is VECTORLESS under a "
                    "pinned embedding space — the embedder failed during this "
                    "birth (or a previous one; re-runs are idempotent no-ops "
                    "and cannot re-vector). A summoned entity's core must be "
                    "vectored at creation: repair with the operator-gated "
                    "reembed, or recreate the home with a live embedder.")

    record_ids: Dict[str, List[str]] = {"values": [], "purposes": [], "traits": [], "honesty": []}
    binding_ids: List[str] = []
    for (section, _ordinal), gid, position in zip(plan, all_ids, range(len(all_ids))):
        if section == "marker":
            continue
        record_ids[section].append(gid)
        # Prompt-active binding = membership in the always-warm self core
        # (values, purposes, limit-traits AND voice traits alike). Ids are
        # key-derived so at-least-once re-runs are journal no-ops.
        binding = system.bind(
            gid, scope=scope, owner_id=owner_id,
            search_state="indexed", prompt_state="active",
            lifecycle="promoted", source="operator",
            reason=f"engram spark v{version}",
            binding_id=hashlib.sha256(f"{key}|{position}|self-binding".encode()).hexdigest()[:32],
        )
        binding_ids.append(binding.binding_id)

    return EngramResult(
        record_ids={k: tuple(v) for k, v in record_ids.items()},
        binding_ids=tuple(binding_ids),
        warnings=warnings,
        created=existing_marker is None,
        authoring=receipt,
    )
