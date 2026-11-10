"""Understanding rewritten in place, every earlier reading kept as a version (backlog 0059).

THE RULING (operator, 2026-11-07, rule 2; DESIGN decisions 2026-11-08 §17.1): "Rewrites happen IN PLACE: the record
keeps its id, history and usage; the previous text is kept as a version with provenance; the verbatim is never
touched." It supersedes the redigestion module's "never edit-in-place" rule (`redigestion.py`, whose
`apply_redigestion` stays available, deprecated) and amends ADR 0003: a record's digest is THE ONE MUTABLE CELL of
the store, changed only through the verbs here.

WHAT A REWRITE DOES (one transaction on the SQLite home; the in-memory pair applies the same steps under the store's
lock):
1. reads the row and checks the compare-and-set (`expected_version` = the record's `digest_version`, 0 when it was
   never rewritten); a byte-identical text is an idempotent success (`applied=False`, nothing written);
2. on the FIRST rewrite, appends version 0 (the original text, its digest_method, its formation time) to the
   journal's `versions` family, then the new version N+1 with its provenance (author, reader, sources, cause);
3. replaces the row's `object`, its reserved attributes (`digest_method`, `digest_version`, `authored_by`,
   `understanding`, `title`, `keywords`), its canonical text, its keyword-index entry and its vector (embedded
   OUTSIDE the transaction with the store's pinned embedder; an unreachable embedder refuses the rewrite, it never
   writes a vectored row's words without their vector).
The graph id, the digest assertion id (usage keys on it), the edges, every journal event and every replay row stay
byte-identical; the only journal trace is the version row, which the replay stream shows in the opt-in family
`revision` only. Rewriting deposits nothing (formation is not use).

WHAT IS NEVER REWRITTEN HERE: the entity's own acts (`UNDERSTANDING_PROTECTED_KINDS`: diary, value, purpose, trait,
interest, realization); a dream's digest (a legacy dream's mechanical summary of the night stays; `narrate_dream` adds
a narration beside it); a world-model card outside `author_world_model` (which keeps the evidence rules); a closed
record (its replacement is the current one: `current_of`); a ripple's consolidation record (`summary_role:
re-understanding`) except by an operator. A dream or card formed with its summary PENDING (operator rulings
2026-11-09: the pass's bookkeeping text is only its provisional body) takes its authored summary through
`rewrite_digest` like any pending record; a card's goes through the card's own write (`author_card_in_place`). So
does a PUBLIC diary projection formed with its summary pending, or a legacy one `declare_pending` declared (operator
rule 2026-11-09: title + summary always exist, authored): its body is the book's entry (the runtime's hash-chained
ledger, `attributes.entry_id`), so the record's digest is only its summary and the write touches neither the body
nor a chain; a private, owner-direct or chained entry stays refused (`diary.diary_summary_refusal`). Its summary
versions are sealed in replay like its title versions.

A TITLE is changed alone by `retitle` (operator 2026-11-08, root ADR 0054: a title is an explicit, complete,
readable phrase, and stored text is never cut): for EVERY kind, the entity's own acts included, because a title the
runtime cut at formation is not the entity's words and the protected body is never touched. The title has its own
version history (field `title`, `title_version`, `title_provenance`); a digest or card reading that changes the
title (rewrite_digest's `title=`, a revert) writes its title version in the same transaction, so
`versions(record_id, field="title")` lists every title the record has held. The diary rule here concerns the body:
a diary entry's words are read through the book, its replay block is redacted, and the opt-in `revision` envelopes
of its title versions are sealed the same way (replay.py); a retitle reads nothing back. An entry carrying an
`entry_hash` (an owner-direct chained diary) refuses: its title is part of the attested hash. A record formed with
its title PENDING (`records.PENDING_FIELDS`, operator rulings 2026-11-09: a title and a summary are mandatory; a
missing one is stored None only beside its queued `title.author` / `digest.author` task and the `attributes.pending`
marker) is retitled like any other: its title version 0 is None, and the write completes the task and clears the
marker (`_clear_pending`; `rewrite_digest` likewise for a pending summary). A title is never removed: a revert to a
version that held none is refused. The one door back to pending is `declare_pending`, for a STORED record whose title
or summary was never authored (a legacy card or dream, a placeholder title): it sets the same marker and queues the
same tasks as formation in one transaction, a declared title is stored None (its old title kept as a version), and the
journal keeps the declaration as a version row (field `pending`); the drainer then completes it like any pending
record. A pending record whose authoring ran out (every task of a pending field failed after `max_attempts`, or was
skipped) is re-armed by `rearm_pending`: fresh formation tasks, the marker kept (its `rearmed` count), a `pending`
version row; `memory_tasks.pending_records` finds them.

A CARD'S KEY (`attributes.target`) is moved alone by `world_model_alias.rekey_world_model` through
`rekey_card_in_place` (operator 2026-11-08: an interest's card is keyed on its title's subject head, so a retitled
interest would otherwise form a second card beside the standing one): field `target`, `target_version`,
`target_provenance`; the old key joins `attributes.aliases`. The card's text, title, keywords and vector are
untouched (the key is not in the canonical text), so no embedder is called.

WHO WROTE THE WORDS is recorded, never inferred: `author` = {kind, id} with kind in `AUTHOR_KINDS`
("entity-mind": the entity's own model; "capability-model": a model the entity's cognition profile names for this
capability, writing as "a passive memory process, part of me" (operator decision 2); "operator"; "mechanical");
`reader` = {provider, model, thinking}; `sources` = ADR 0003 `SourceRef` dicts naming the ledger step of the call (a
model author must name one). This module never invents text and applies no rule to the words it is given.

A ROW NOBODY STAMPED (formed before formation recorded its reading, operator 2026-11-08) is read from what the row
itself says about its origin, never from its words: `reading_provenance` (its digest_method label, the spark mark,
an operator actor in its provenance, its kind; `_formation_author` has the order). `remember_many` records that
same reading at formation, so new rows carry it as a stamp.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .canonical_text import canonical_text, record_title
from .commit_guard import deferred_to_caller, guard_commit
from .journal import UnderstandingVersion, VERSION_FIELDS, utc_now_iso
from .records import PENDING_TASK_KINDS, resolve_digest_assertion

__all__ = [
    "AUTHOR_KINDS",
    "DECLARE_PENDING_METHOD",
    "DEFAULT_AUTHORED_METHOD",
    "ENTITY_WORDS_KINDS",
    "REARM_PENDING_METHOD",
    "REKEY_METHOD",
    "REWRITE_CAUSES",
    "RETITLE_METHOD",
    "SPARK_KINDS",
    "UNDERSTANDING_PROTECTED_KINDS",
    "current_of",
    "declare_pending",
    "formation_understanding",
    "narrate_dream",
    "reading_provenance",
    "rearm_pending",
    "record_understanding",
    "retitle",
    "revert_digest",
    "rewrite_digest",
    "understanding_fields",
    "version_id_for",
    "versions",
]

#: Who may author a reading (DESIGN §4). `unrecorded` is never accepted as input: it labels a reading nobody stamped
#: whose row names no origin (`_formation_author`: no mechanical label, not a kind only the entity writes, no spark
#: or operator mark) and a legacy author label.
AUTHOR_KINDS = frozenset({"mechanical", "entity-mind", "capability-model", "operator"})
MODEL_AUTHOR_KINDS = frozenset({"entity-mind", "capability-model"})
UNRECORDED = "unrecorded"

#: Why a reading was written (DESIGN §4). `repair` (operator 2026-11-08): a correction of what a process wrote wrong,
#: such as a title the runtime cut at formation or a card key derived from that cut title.
REWRITE_CAUSES = frozenset({"formation", "backfill", "ripple", "evidence", "operator", "revert", "repair"})

#: The entity's own acts: never rewritten by a background process (the redigestion rails, minus the born-digest
#: kinds that now have their own in-place verbs: dreams get a narration, cards get `author_world_model`).
UNDERSTANDING_PROTECTED_KINDS = frozenset({"diary", "value", "purpose", "trait", "interest", "realization"})

#: Kinds only the entity writes, in his own words (operator 2026-11-08): his elections at a visit close or mid-turn
#: (lesson, interest, realization, observation, question), his book (diary: every diary_type, so note, idea,
#: commitment, reflection, question, problem and lesson entries) and the identity he revises himself. A row of these
#: kinds nobody stamped reads `entity-mind` with the scope owner as id, unless its row names another origin
#: (`_formation_author`: a mechanical label, the spark, an operator import).
ENTITY_WORDS_KINDS = frozenset({"lesson", "interest", "realization", "observation", "question", "diary",
                                "value", "purpose", "trait"})

#: The identity kinds the engram pass forms from the spark (engram.py stamps `attributes.spark_version`): the
#: operator's (or the template's) words, never the entity's.
SPARK_KINDS = frozenset({"value", "purpose", "trait"})

#: The digest_method a rewrite stamps unless the caller names another.
DEFAULT_AUTHORED_METHOD = "authored-v1"

#: The method label of a title version written by `retitle`.
RETITLE_METHOD = "retitle-v1"

#: The method label of a card-key version written by `rekey_card_in_place` (version 0 of a key reads
#: `world-model-pass`: the pass derived it from the evidence).
REKEY_METHOD = "rekey-v1"

#: The method label of a pending declaration's version row (field `pending`) and of the title version it writes when
#: it takes a title back to pending (`declare_pending`).
DECLARE_PENDING_METHOD = "declare-pending-v1"

#: Who writes a declaration: the verb itself, a mechanical act (the caller's reason and identity ride the cause).
DECLARER: Mapping[str, str] = {"kind": "mechanical", "id": "declare_pending"}

#: The method label of a re-arm's version row (field `pending`, `rearm_pending`), and who writes it.
REARM_PENDING_METHOD = "rearm-pending-v1"
REARMER: Mapping[str, str] = {"kind": "mechanical", "id": "rearm_pending"}

#: The card floor's mechanical label (world_model.py): the cards the task queue owes authored words.
MECHANICAL_CARD_METHODS = frozenset({"mechanical-card-v2"})

#: A ripple's consolidation record (backlog 0061) is never batch-rewritten.
RE_UNDERSTANDING_ROLE = "re-understanding"

_JSON_SCALARS = (str, int, float, bool, type(None))


def version_id_for(record_id: str, field: str, version: int) -> str:
    """The deterministic id of one version row (a replayed append is a no-op)."""
    return hashlib.sha256(f"{record_id}|{field}|{int(version)}".encode("utf-8")).hexdigest()[:32]


# --------------------------------------------------------------------------- argument checks (loud: caller bugs)


def _json_safe(value: Any, where: str) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False, default=_refuse))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{where} must be JSON-safe: {exc}") from None


def _refuse(obj: Any) -> Any:
    raise TypeError(f"{type(obj).__name__} is not JSON-serializable")


def _author(author: Any) -> Dict[str, Any]:
    if not isinstance(author, Mapping):
        raise ValueError("author must be a mapping {kind, id} (kind in AUTHOR_KINDS)")
    kind = str(author.get("kind") or "").strip()
    if kind not in AUTHOR_KINDS:
        raise ValueError(f"author.kind must be one of {sorted(AUTHOR_KINDS)} (got {kind!r})")
    out = _json_safe(dict(author), "author")
    out["kind"] = kind
    out["id"] = str(author.get("id") or "").strip()
    return out


def _reader(reader: Any, author_kind: str) -> Dict[str, Any]:
    if reader is None:
        if author_kind in MODEL_AUTHOR_KINDS:
            raise ValueError(f"a {author_kind} author needs reader={{provider, model, thinking}} (which model wrote it)")
        return {}
    if not isinstance(reader, Mapping):
        raise ValueError("reader must be a mapping {provider, model, thinking}")
    provider = str(reader.get("provider") or "").strip()
    model = str(reader.get("model") or "").strip()
    if author_kind in MODEL_AUTHOR_KINDS and not (provider and model):
        raise ValueError("reader needs non-empty provider and model")
    thinking = reader.get("thinking")
    if not isinstance(thinking, _JSON_SCALARS):
        raise ValueError("reader.thinking must be a JSON scalar (bool, effort label or null)")
    out = _json_safe(dict(reader), "reader")
    out.update({"provider": provider, "model": model, "thinking": thinking})
    return out


def _sources(sources: Any, author_kind: str) -> Tuple[Dict[str, Any], ...]:
    from .graph.provenance import SourceRef  # lazy: the graph package imports the stores

    if isinstance(sources, (str, bytes, Mapping)):
        raise ValueError("sources is a list of SourceRef dicts (ADR 0003 decision 9)")
    refs = tuple(SourceRef.from_dict(s).to_dict() for s in (sources or ()))
    if author_kind in MODEL_AUTHOR_KINDS and not refs:
        raise ValueError(f"a {author_kind} author must name the ledger step of its call in sources (ADR 0003)")
    return refs


def _cause(cause: Any) -> Dict[str, Any]:
    raw = {"cause": cause} if isinstance(cause, str) else cause
    if not isinstance(raw, Mapping):
        raise ValueError(f"cause must be one of {sorted(REWRITE_CAUSES)} or a mapping with a 'cause' key")
    name = str(raw.get("cause") or "").strip()
    if name not in REWRITE_CAUSES:
        raise ValueError(f"cause must be one of {sorted(REWRITE_CAUSES)} (got {name!r})")
    out = _json_safe(dict(raw), "cause")
    out["cause"] = name
    return out


def _ids(values: Any, where: str) -> Tuple[str, ...]:
    if isinstance(values, (str, bytes, Mapping)):
        raise ValueError(f"{where} is a list of record ids")
    return tuple(str(v).strip() for v in (values or ()) if str(v or "").strip())


# --------------------------------------------------------------------------- reads shared by the verbs


def _attrs(assertion: Any) -> Dict[str, Any]:
    return dict(assertion.attributes) if isinstance(getattr(assertion, "attributes", None), dict) else {}


def _resolve(system: Any, record_id: str) -> Any:
    rid = str(record_id or "").strip()
    a = resolve_digest_assertion(system.store, rid) if rid else None
    if a is None or not _attrs(a).get("record_kind"):
        return None
    return a


def _field_of(kind: str) -> str:
    return "card" if kind == "world_model" else "digest"


def _version_attr(field: str) -> str:
    return {"narration": "narration_version", "title": "title_version",
            "target": "target_version", "pending": "pending_version"}.get(field, "digest_version")


def _title(attrs: Mapping[str, Any]) -> Optional[str]:
    """The record's title, None when it is untitled (operator ruling 2026-11-09: a failed title is stored NULL)."""
    return record_title(attrs)


def _clear_pending(out: Dict[str, Any], field: str) -> Dict[str, Any]:
    """The pending marker after a write (records.PENDING_FIELDS): a title is no longer pending once the row holds
    one; a summary is no longer pending once a digest reading (a card's: field `card`) is written. The marker goes
    when nothing is left."""
    marker = out.get("pending")
    if not isinstance(marker, Mapping):
        return out
    marker = dict(marker)
    if marker.get("title") and record_title(out) is not None:
        marker["title"] = False
    if marker.get("summary") and field in ("digest", "card"):
        marker["summary"] = False
    if marker.get("title") or marker.get("summary"):
        out["pending"] = marker
    else:
        out.pop("pending", None)
    return out


def _pending_cleared(before: Mapping[str, Any], after: Mapping[str, Any]) -> List[str]:
    """The pending fields a write fulfilled (they were pending before it and are not after it)."""
    m0 = before.get("pending") if isinstance(before.get("pending"), Mapping) else {}
    m1 = after.get("pending") if isinstance(after.get("pending"), Mapping) else {}
    return [f for f in ("title", "summary") if m0.get(f) and not m1.get(f)]


def _current_version(attrs: Mapping[str, Any], field: str) -> int:
    try:
        return max(0, int(attrs.get(_version_attr(field)) or 0))
    except (TypeError, ValueError):
        return 0


def _formation_author(attrs: Mapping[str, Any], provenance: Mapping[str, Any], owner_id: str) -> Dict[str, Any]:
    """Who wrote a formation reading nobody stamped, from what the row says about its origin (first match wins):
    a `mechanical*` digest_method; a legacy `authored_by` label (kind unknown: `unrecorded`, the label as id); a
    spark identity record (`attributes.spark_version`: the operator's spark, id `spark-v<N>`); a row whose
    provenance names the operator as actor (an archive import: id = provenance.source); a kind only the entity
    writes, in his own words (`ENTITY_WORDS_KINDS`: id = the scope owner); else `unrecorded`."""
    method = str(attrs.get("digest_method") or "").strip()
    if method.startswith("mechanical"):
        return {"kind": "mechanical", "id": method}
    label = attrs.get("authored_by")
    if isinstance(label, str) and label.strip():
        return {"kind": UNRECORDED, "id": label.strip()}
    kind = str(attrs.get("record_kind") or "").strip().lower()
    if kind in SPARK_KINDS and attrs.get("spark_version") is not None:
        return {"kind": "operator", "id": f"spark-v{attrs.get('spark_version')}"}
    if str(provenance.get("actor") or "").strip() == "operator":
        return {"kind": "operator", "id": str(provenance.get("source") or "").strip() or "operator"}
    owner = str(owner_id or "").strip()
    if kind in ENTITY_WORDS_KINDS and owner:
        return {"kind": "entity-mind", "id": owner}
    return {"kind": UNRECORDED, "id": method}


def _reading(attrs: Mapping[str, Any], provenance: Mapping[str, Any], owner_id: str,
             observed_at: str) -> Dict[str, Any]:
    und = attrs.get("understanding") if isinstance(attrs.get("understanding"), dict) else None
    if und:  # the writer's stamp always wins
        cause = und.get("cause") if isinstance(und.get("cause"), dict) else {}
        return {"author": dict(und.get("author") or {}), "reader": dict(und.get("reader") or {}),
                "understood_at": str(und.get("understood_at") or ""), "cause": str(cause.get("cause") or "")}
    return {"author": _formation_author(attrs, provenance, owner_id), "reader": {},
            "understood_at": str(observed_at or ""), "cause": "formation"}


def reading_provenance(assertion: Any) -> Dict[str, Any]:
    """THE derivation of who wrote a record's current reading, with which model, when and why (pure):
    {author {kind, id}, reader, understood_at, cause}. The row's own stamp (`attributes.understanding`, written by
    a rewrite, a ripple consolidation or formation) wins. A row nobody stamped is read as its formation reading:
    cause "formation", understood_at = observed_at, the author from `_formation_author`. `understanding_fields`
    (record_understanding, the replay display blocks), the version 0 a first rewrite captures, the card briefs and
    the formation stamp all go through here."""
    provenance = getattr(assertion, "provenance", None)
    return _reading(_attrs(assertion), provenance if isinstance(provenance, dict) else {},
                    str(getattr(assertion, "owner_id", "") or ""), str(getattr(assertion, "observed_at", "") or ""))


def formation_understanding(attrs: Mapping[str, Any], *, provenance: Mapping[str, Any], owner_id: str,
                            observed_at: str) -> Optional[Dict[str, Any]]:
    """The `understanding` stamp `remember_many` writes on a record its caller did not stamp (version 0, cause
    "formation", the same author `reading_provenance` derives), so a future read reads it recorded; None when the
    caller stamped one or the author is `unrecorded` (nothing known to record)."""
    if isinstance(attrs.get("understanding"), dict):
        return None
    reading = _reading(attrs, provenance, owner_id, observed_at)
    if reading["author"].get("kind") == UNRECORDED:
        return None
    return _understanding_attr(0, _field_of(str(attrs.get("record_kind") or "")), reading["author"], {},
                               {"cause": "formation"}, (), (), str(observed_at or ""))


def _closures(journal: Any, assertion_id: Optional[str]) -> List[Any]:
    if not assertion_id:
        return []
    return list(journal.closures(assertion_id=assertion_id, limit=0))


def _replaced_by(closures: Sequence[Any]) -> List[str]:
    for c in closures:  # newest first
        if c.kind in ("supersede", "merged") and c.replacement_ids:
            return list(c.replacement_ids)
    return []


def _refusal(reason: str, detail: str, **extra: Any) -> Dict[str, Any]:
    return {"applied": False, "outcome": "refused", "reason": reason, "detail": detail, **extra}


# --------------------------------------------------------------------------- the transaction (both backends)


def _same_file(a: Any, b: Any) -> bool:
    try:
        return os.path.samefile(str(a), str(b))
    except OSError:
        return False


def _backend(system: Any) -> str:
    from .in_memory_store import InMemoryTripleStore
    from .journal_sqlite import SQLiteJournal
    from .sqlite_store import SQLiteTripleStore

    store, journal = system.store, system.journal
    if isinstance(store, SQLiteTripleStore):
        if not (isinstance(journal, SQLiteJournal) and _same_file(store._path, journal._path)):
            raise ValueError(
                "rewrite_digest needs the SQLiteJournal in the store's own file (the entity-home deployment): "
                "the row, its keyword entry, its vector and the version row commit in ONE transaction")
        return "sqlite"
    if isinstance(store, InMemoryTripleStore):
        if not callable(getattr(journal, "append_version", None)):
            raise ValueError("rewrite_digest needs a journal with the versions family (append_version)")
        return "memory"
    refuse = getattr(store, "rewrite_digest_in_place", None)
    if callable(refuse):
        refuse()  # raises NotImplementedError naming the item
    raise NotImplementedError(f"rewrite_digest: {type(store).__name__} cannot rewrite a record in place (backlog 0059)")


def _queue_for(system: Any, kind_backend: str) -> Any:
    """The home's task queue: the system's own, or (SQLite) the file's when another process created it."""
    queue = getattr(system, "tasks", None)
    if queue is not None or kind_backend != "sqlite":
        return queue
    store = system.store
    prefix = "memq_" if store._table == "triples" else f"memq_{store._table}_"
    with store._lock:
        found = store._conn.cursor().execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (f"{prefix}tasks",)).fetchone()
    if found is None:
        return None
    from .memory_tasks import MemoryTaskQueue

    return MemoryTaskQueue(store)


def _embed(store: Any, text: str, had_vector: bool) -> Tuple[Optional[Dict[str, Any]], Optional[List[float]], bool]:
    """(refusal, vector, write_vector). The store's own embedder, outside any transaction (store.add parity)."""
    from .embedding_pin import check_add_dimension

    embedder = getattr(store, "_embedder", None)
    if embedder is None:
        if had_vector:
            return (_refusal(
                "embedder_unavailable",
                "the record is vectored and this store has no embedder: its vector would keep describing the old "
                "words (open the home with its pinned embedder)"), None, False)
        return None, None, False
    try:
        [vector] = embedder.embed_texts([text])
    except Exception as exc:  # transport / HTTP / model errors: refuse, never write vectorless
        return (_refusal("embedder_unavailable", f"the pinned embedder failed: {exc}"), None, False)
    vector = [float(x) for x in vector]
    check_add_dimension(store.embedding_pin(), [vector])  # wrong space: corruption, raises (never degradable)
    return None, vector, True


def _apply(
    system: Any, *, record_id: str, field: str, new_object: Optional[str], narration: Optional[str],
    reserved: Callable[[Dict[str, Any], int], Dict[str, Any]], version: Callable[[Any, int], UnderstandingVersion],
    expected_version: int, hooks: Sequence[Callable[[Any], None]] = (),
    after: Sequence[Callable[[Dict[str, Any]], None]] = (),
) -> Dict[str, Any]:
    """The shared write: CAS, version rows, row/keyword/vector replacement, in one transaction. `reserved(attrs, n)`
    returns the row's new attributes for version n; `version(assertion, n)` builds the version row n. `hooks` run on
    the open SQLite cursor (the task queue acks and supersedes there); `after` run once the write committed.

    A digest or card reading that changes the title also writes the title's version (field `title`: version 0 the
    title it replaces, then the new one with this reading's provenance), so the title history stays whole; so does
    a pending declaration (field `pending`, `declare_pending`) that takes the title back to pending (None). A
    declaration that leaves the title as it is changes no text: no embedder is called and the vector stands."""
    kind_backend = _backend(system)
    store, journal = system.store, system.journal
    a = _resolve(system, record_id)
    if a is None:
        return _refusal("unknown_record", f"no formed record {record_id!r} in this store")
    aid = str(a.assertion_id or "")
    attrs0 = _attrs(a)
    current = _current_version(attrs0, field)
    title_now = _current_version(attrs0, "title")
    target_new = current + 1
    reserved_verb = reserved

    def reserved(old: Dict[str, Any], n: int) -> Dict[str, Any]:  # noqa: F811 - the verb's attrs, pending settled
        return _clear_pending(reserved_verb(old, n), field)

    planned_attrs = reserved(attrs0, target_new)
    cleared = _pending_cleared(attrs0, planned_attrs)
    planned = replace(a, object=new_object if new_object is not None else a.object, attributes=planned_attrs)
    if field == "title":
        identical = _title(attrs0) == _title(planned_attrs)
    elif field == "target":
        identical = str(attrs0.get("target") or "") == str(planned_attrs.get("target") or "")
    elif narration is not None:
        identical = str(attrs0.get("narration") or "") == narration
    elif field == "pending":
        identical = attrs0.get("pending") == planned_attrs.get("pending") and _title(attrs0) == _title(planned_attrs)
    else:
        identical = str(a.object or "") == str(new_object or "")
    base = {"record_id": str(a.subject), "assertion_id": aid, "field": field}
    if identical and not cleared:
        return {"applied": False, "outcome": "unchanged", "reason": "identical",
                "detail": f"the {'title' if field == 'title' else 'text'} is already the current reading",
                "version": current, **base}
    # Identical words that settle a PENDING field are a write (Codex review 3 finding 7: `unchanged` left the marker
    # and the task, the drainer counted it authored, the lease expired and the re-arm queued it again, forever):
    # the authored reading's provenance is recorded as a version, the marker cleared and the task completed in one
    # transaction, like any authored write. The canonical text is unchanged, so its vector stands.
    settles_only = identical and canonical_text(planned) == canonical_text(a)
    if int(expected_version) != current:
        return _refusal("stale", f"expected version {int(expected_version)}, the record is at version {current}",
                        version=current, **base)
    vector: Optional[List[float]] = None
    write_vector = False
    distance: Optional[float] = None
    text = canonical_text(planned)
    # A card's key is not in its canonical text, nor is a pending marker: the vector stands (a declaration that takes
    # the title back to pending changes the canonical text, whose first line the title is).
    # A NON_EMBEDDED_KINDS record (a community) is never embedded: its authored words leave it vector-less.
    from .canonical_text import never_embedded

    if not settles_only and not never_embedded(planned) and (
            field not in ("narration", "target", "pending")
            or (field == "pending" and _title(planned_attrs) != _title(attrs0))):
        old_vector = store.stored_vector(aid)
        refusal, vector, write_vector = _embed(store, text, old_vector is not None)
        if refusal is not None:
            refusal.update(base)
            return refusal
        if old_vector is not None and vector is not None and len(old_vector) == len(vector):
            from .vector_scoring import cosine

            distance = round(1.0 - float(cosine(old_vector, vector)), 6)
    v_new = version(a, target_new)
    v_zero: Optional[UnderstandingVersion] = None
    if current == 0 and field == "title":
        v_zero = _title_version_zero(system, a)
    elif current == 0 and field == "target":
        v_zero = _target_version_zero(a)
    elif current == 0 and field not in ("narration", "pending"):  # a declaration has no original reading
        v_zero = _version_zero(a, field)
    title_rows: List[UnderstandingVersion] = []
    if field in ("digest", "card", "pending") and _title(planned_attrs) != _title(attrs0):
        # This reading (or declaration) changes the title too: the title's own history records it.
        if title_now == 0:
            title_rows.append(_title_version_zero(system, a))
        title_rows.append(_title_version_row(
            a, title_now + 1, title=_title(planned_attrs), author=v_new.author, reader=v_new.reader,
            sources=v_new.sources, cause=v_new.cause, task_id=v_new.task_id, at=v_new.understood_at,
            method=v_new.digest_method))
        stamp = _understanding_attr(title_now + 1, "title", v_new.author, v_new.reader, v_new.cause,
                                    tuple(v_new.sources), (), v_new.understood_at)
        reserved_reading = reserved

        def reserved(old: Dict[str, Any], n: int) -> Dict[str, Any]:  # noqa: F811 - the reading's attrs + title stamp
            out = reserved_reading(old, n)
            out.update({"title_version": title_now + 1, "title_provenance": stamp})
            return out

    def _title_moved(fresh_attrs: Mapping[str, Any]) -> bool:
        """A concurrent title write (a retitle, or a reading that changed it) makes this write stale: it would
        otherwise put back the title it read."""
        return field != "narration" and (_title(fresh_attrs) != _title(attrs0)
                                          or _current_version(fresh_attrs, "title") != title_now)

    written: List[UnderstandingVersion] = []
    queue = _queue_for(system, kind_backend)
    if queue is not None:
        # The task queue (0060) settles in the same transaction: the named task is acked, stale tasks superseded.
        def _settle(cur: Any) -> None:
            queue.on_rewrite(cur, record_id=str(a.subject), field=field, version=target_new,
                             task_id=v_new.task_id or None, completes=[PENDING_TASK_KINDS[f] for f in cleared],
                             result={"version": target_new, "version_id": v_new.version_id,
                                     "seq": written[-1].seq if written else None, "field": field,
                                     "author_kind": v_new.author.get("kind"),
                                     "model": v_new.reader.get("model"), "cosine_distance": distance})

        hooks = (*hooks, _settle)

    if kind_backend == "sqlite":
        with store._lock:
            cur = store._conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                row = store._row_for_rewrite(cur, aid)
                if row is None:
                    cur.execute("ROLLBACK")
                    return _refusal("unknown_record", f"record {record_id!r} vanished", **base)
                from .sqlite_store import SQLiteTripleStore as _S

                fresh = _S._row_to_assertion(row)
                fresh_attrs = _attrs(fresh)
                now_version = _current_version(fresh_attrs, field)
                if now_version != current or fresh.object != a.object or _title_moved(fresh_attrs) or (
                        field == "narration" and fresh_attrs.get("narration") != attrs0.get("narration")):
                    cur.execute("ROLLBACK")
                    return _refusal("stale", "the record changed while the rewrite was prepared",
                                    version=now_version, **base)
                rewritten = replace(fresh, attributes=reserved(fresh_attrs, target_new),
                                    object=new_object if new_object is not None else fresh.object)
                if field != "narration" and canonical_text(rewritten) != text:
                    cur.execute("ROLLBACK")
                    return _refusal("stale", "the record's title or keywords changed while the rewrite was prepared",
                                    version=now_version, **base)
                if v_zero is not None:
                    written.append(journal._append_version_on(cur, v_zero))
                written.append(journal._append_version_on(cur, v_new))
                for row_t in title_rows:
                    journal._append_version_on(cur, row_t)
                if write_vector and vector is not None and store.embedding_pin() is None:
                    _pin_first_write(store, vector, cur)
                store._rewrite_row_on(cur, row, rewritten, vector=vector, write_vector=write_vector)
                for hook in hooks:
                    hook(cur)
                guard_commit(store, f"understanding.{field}")
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
            if write_vector:
                store._vectors = None  # this handle rebuilds; others see the bumped vector_generation
    else:
        with store._lock:
            fresh = store._stored_row(aid)
            if fresh is None:
                return _refusal("unknown_record", f"record {record_id!r} vanished", **base)
            fresh_attrs = _attrs(fresh)
            now_version = _current_version(fresh_attrs, field)
            if now_version != current or fresh.object != a.object or _title_moved(fresh_attrs):
                return _refusal("stale", "the record changed while the rewrite was prepared",
                                version=now_version, **base)
            rewritten = replace(fresh, attributes=reserved(fresh_attrs, target_new),
                                object=new_object if new_object is not None else fresh.object)
            stored = replace(rewritten, assertion_id=aid)
            # No COMMIT here: the commit point is before the first write, and the writes below are its own.
            guard_commit(store, f"understanding.{field}")
            with deferred_to_caller(store):
                if v_zero is not None:
                    written.append(journal.append_version(v_zero))
                written.append(journal.append_version(v_new))
                for row_t in title_rows:
                    journal.append_version(row_t)
                if write_vector and store.embedding_pin() is None and vector is not None:
                    _pin_first_write(store, vector, None)
                store._rewrite_row(aid, stored, vector=vector, write_vector=write_vector)
                for hook in hooks:
                    hook(None)
    result = {"applied": True, "outcome": "applied", "reason": None, "version": target_new,
              "previous_version": current, "version_id": written[-1].version_id, "seq": written[-1].seq,
              "captured_original": v_zero is not None, "vector_rewritten": write_vector,
              "cosine_distance": distance, **base}
    if title_rows:
        result["title_version"] = title_now + 1
    if cleared:
        result["pending_cleared"] = cleared
    for fn in after:
        fn(result)
    return result


def _pin_first_write(store: Any, vector: List[float], cur: Any) -> None:
    """A pinless store's first embedded write pins the space (store.add parity, labelled)."""
    from .embedding_pin import build_pin, embedder_model_id, warn_first_write_pin

    pin = build_pin(embedder_model_id(store._embedder), len(vector), source="first-write",
                    claimed_by="embedder-attribute")
    warn_first_write_pin(pin)
    if cur is not None:
        store._write_pin(pin, cursor=cur)
    else:
        store._embedding_pin = pin


def _version_zero(a: Any, field: str) -> UnderstandingVersion:
    """The original reading, captured at the first rewrite (version 0): its provenance is `reading_provenance`'s."""
    attrs = _attrs(a)
    provenance = dict(a.provenance) if isinstance(a.provenance, dict) else {}
    reading = reading_provenance(a)
    return UnderstandingVersion(
        record_id=str(a.subject), assertion_id=str(a.assertion_id), version=0, field=field,
        text=str(a.object or ""), scope=str(a.scope), owner_id=str(a.owner_id or ""),
        title=record_title(attrs), keywords=tuple(attrs.get("keywords") or ()),
        digest_method=str(attrs.get("digest_method") or ""), author=reading["author"], reader=reading["reader"],
        cause={"cause": reading["cause"] or "formation", "formation_provenance": _json_safe(provenance, "provenance"),
               # The provisional digest of a record formed with its summary pending: never restored (a summary is
               # mandatory; revert_digest refuses it).
               **({"pending_summary": True} if field in ("digest", "card")
                  and isinstance(attrs.get("pending"), Mapping) and attrs["pending"].get("summary") else {})},
        understood_at=reading["understood_at"] or str(a.observed_at or ""),
        version_id=version_id_for(str(a.subject), field, 0),
    )


def _understanding_attr(n: int, field: str, author: Dict[str, Any], reader: Dict[str, Any], cause: Dict[str, Any],
                        sources: Tuple[Dict[str, Any], ...], derived_from: Tuple[str, ...], at: str) -> Dict[str, Any]:
    return {"version": n, "field": field, "author": author, "reader": reader, "cause": cause,
            "sources": list(sources), "derived_from": list(derived_from), "understood_at": at}


def _version_row(a: Any, n: int, *, field: str, text: Optional[str], title: Optional[str], keywords: Sequence[str],
                 digest_method: str,
                 author: Dict[str, Any], reader: Dict[str, Any], sources: Tuple[Dict[str, Any], ...],
                 derived_from: Tuple[str, ...], cause: Dict[str, Any], magnitude: Mapping[str, Any],
                 task_id: str, at: str) -> UnderstandingVersion:
    return UnderstandingVersion(
        record_id=str(a.subject), assertion_id=str(a.assertion_id), version=n, field=field, text=text,
        scope=str(a.scope), owner_id=str(a.owner_id or ""), title=title, keywords=tuple(keywords),
        digest_method=digest_method, author=author, reader=reader, sources=sources, derived_from=derived_from,
        cause=cause, magnitude=_json_safe(dict(magnitude or {}), "magnitude"), task_id=task_id,
        understood_at=at, version_id=version_id_for(str(a.subject), field, n),
    )


def _title_version_row(a: Any, n: int, *, title: Optional[str], author: Dict[str, Any], reader: Dict[str, Any],
                       sources: Sequence[Dict[str, Any]], cause: Dict[str, Any], task_id: str, at: str,
                       method: str) -> UnderstandingVersion:
    """One title version: the title is the row's `text` (and its `title`); keywords are the record's. An untitled
    record's title row holds None (version 0 of its first retitle, or a revert to that version)."""
    return _version_row(a, n, field="title", text=title, title=title, keywords=tuple(_attrs(a).get("keywords") or ()),
                        digest_method=method, author=dict(author), reader=dict(reader), sources=tuple(sources),
                        derived_from=(), cause=dict(cause), magnitude={}, task_id=task_id, at=at)


def _title_version_zero(system: Any, a: Any) -> UnderstandingVersion:
    """The title a record holds before its first title version (version 0), with the provenance of the reading that
    wrote it: the earliest digest/card version from which every later reading kept this title (a rewrite that passed
    it; version 0 of the digest = the formation reading), else `reading_provenance` (a record never rewritten)."""
    attrs = _attrs(a)
    current = _title(attrs)
    rows = list(system.journal.versions(record_id=str(a.subject), field=_field_of(str(attrs.get("record_kind") or ""))))
    if rows and rows[-1].title == current:
        k = len(rows) - 1
        while k > 0 and rows[k - 1].title == current:
            k -= 1
        src = rows[k]
        return _title_version_row(a, 0, title=current, author=src.author, reader=src.reader, sources=src.sources,
                                  cause={**src.cause, "title_from": {"field": src.field, "version": src.version}},
                                  task_id=src.task_id, at=src.understood_at, method=src.digest_method)
    reading = reading_provenance(a)
    provenance = dict(a.provenance) if isinstance(a.provenance, dict) else {}
    return _title_version_row(
        a, 0, title=current, author=reading["author"], reader=reading["reader"], sources=(),
        cause={"cause": reading["cause"] or "formation", "formation_provenance": _json_safe(provenance, "provenance")},
        task_id="", at=reading["understood_at"] or str(a.observed_at or ""),
        method=str(attrs.get("digest_method") or ""))


def _target_version_zero(a: Any) -> UnderstandingVersion:
    """The key a card holds before its first re-key (version 0): `world_model_pass` derived it from the evidence
    (author mechanical, cause formation), at the formation of the card row that holds it."""
    attrs = _attrs(a)
    provenance = dict(a.provenance) if isinstance(a.provenance, dict) else {}
    return _version_row(
        a, 0, field="target", text=str(attrs.get("target") or ""), title=_title(attrs),
        keywords=tuple(attrs.get("keywords") or ()), digest_method="world-model-pass",
        author={"kind": "mechanical", "id": "world_model_pass"}, reader={}, sources=(), derived_from=(),
        cause={"cause": "formation", "card_revision": attrs.get("revision"),
               "formation_provenance": _json_safe(provenance, "provenance")},
        magnitude={}, task_id="", at=str(a.observed_at or ""))


# --------------------------------------------------------------------------- the verbs


def rewrite_digest(
    system: Any, record_id: str, *,
    text: str,
    author: Mapping[str, Any],
    cause: Union[str, Mapping[str, Any]],
    expected_version: int,
    reader: Optional[Mapping[str, Any]] = None,
    sources: Sequence[Mapping[str, Any]] = (),
    derived_from: Sequence[str] = (),
    title: Optional[str] = None,
    keywords: Optional[Sequence[str]] = None,
    digest_method: str = DEFAULT_AUTHORED_METHOD,
    magnitude: Optional[Mapping[str, Any]] = None,
    task_id: Optional[str] = None,
    understood_at: Optional[str] = None,
    _hooks: Sequence[Callable[[Any], None]] = (),
    _after: Sequence[Callable[[Dict[str, Any]], None]] = (),
    _attributes: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Replace a record's digest (and optionally its title and keywords) IN PLACE, keeping every earlier reading.

    `record_id` is the graph id or the digest assertion id. `expected_version` is the compare-and-set: the record's
    current `digest_version` (0 for a never-rewritten record; `versions()` / `record_understanding()` read it).
    Returns {applied, outcome: applied|unchanged|refused, reason, detail?, record_id, assertion_id, field, version,
    previous_version?, version_id?, seq?, captured_original?, vector_rewritten?}. Refusal reasons (nothing written):
    `unknown_record`, `protected_kind`, `use_narrate_dream`, `use_author_world_model`, `closed`,
    `consolidation_record`, `empty_text`, `card_keywords`, `stale`, `embedder_unavailable`. Invalid arguments (an
    author kind outside `AUTHOR_KINDS`, a model author without reader or sources, a cause outside `REWRITE_CAUSES`)
    raise ValueError.

    A dream or a world-model card formed with its summary PENDING (`world_model_pass`, `dream_pass`: the night's or
    the evidence's bookkeeping text stands as the provisional body, operator rulings 2026-11-09) takes its authored
    summary here, so the `digest.author` task completes through the one verb every drainer calls: a dream's digest
    is replaced in place (its signals, proposals and narration untouched); a card's goes through the card's own
    reading (`author_card_in_place`: field `card`, the summary becomes its authored lead, evidence and key
    untouched). Outside a pending summary they keep their own doors (`use_narrate_dream`,
    `use_author_world_model`). A PUBLIC diary projection formed with its summary pending, or a legacy one whose summary
    `declare_pending` declared, is completed here too (its digest is only the summary: the body is the book's entry);
    every other diary write refuses `protected_kind` (a private, owner-direct or chained entry, or a summary not
    pending).
    """
    author_d = _author(author)
    reader_d = _reader(reader, author_d["kind"])
    sources_t = _sources(sources, author_d["kind"])
    cause_d = _cause(cause)
    derived = _ids(derived_from, "derived_from")
    words = str(text or "").strip()
    method = str(digest_method or "").strip()
    if not method:
        raise ValueError("rewrite_digest requires a non-empty digest_method label")
    a = _resolve(system, record_id)
    if a is None:
        return _refusal("unknown_record", f"no formed record {record_id!r} in this store", record_id=str(record_id))
    attrs = _attrs(a)
    kind = str(attrs.get("record_kind") or "").strip().lower()
    base = {"record_id": str(a.subject), "assertion_id": str(a.assertion_id or ""), "field": "digest"}
    summary_pending = bool(isinstance(attrs.get("pending"), Mapping) and attrs["pending"].get("summary"))
    if kind == "diary" and summary_pending:
        # A PUBLIC projection's pending summary (its body is the book's entry): authored here like any record's.
        from .diary import diary_summary_refusal

        provenance = a.provenance if isinstance(getattr(a, "provenance", None), Mapping) else {}
        refusal = diary_summary_refusal(attrs, provenance)
        if refusal is not None:
            return _refusal("protected_kind", f"{refusal[1]} ({refusal[0]})", **base)
    elif kind in UNDERSTANDING_PROTECTED_KINDS:
        return _refusal("protected_kind", f"kind {kind!r} is the entity's own act; it is never rewritten", **base)
    if kind == "dream" and not summary_pending:
        return _refusal("use_narrate_dream",
                        "a dream's digest is the night's mechanical summary; narrate_dream adds a narration", **base)
    if kind == "world_model" and not summary_pending:
        return _refusal("use_author_world_model", "cards are authored through author_world_model (evidence rules)",
                        **base)
    if attrs.get("summary_role") == RE_UNDERSTANDING_ROLE and cause_d["cause"] != "operator":
        return _refusal("consolidation_record", "a ripple's consolidation record is never batch-rewritten", **base)
    if not words:
        return _refusal("empty_text", "the engine never invents words: an empty rewrite would erase the reading",
                        **base)
    closures = _closures(system.journal, a.assertion_id)
    if closures:
        return _refusal("closed", f"the record is closed ({closures[0].kind}); rewrite its current replacement",
                        replaced_by=_replaced_by(closures), **base)
    if kind == "world_model":
        # A card's pending summary is its first authored reading: the card's own write (field `card`) keeps the
        # evidence rules (authored lead, the evidence it was read from) and completes the digest.author task.
        if keywords is not None:
            return _refusal("card_keywords", "a card's keywords are its evidence facets (world_model_pass)", **base)
        known = [str(s) for s in (attrs.get("known_source_ids") or attrs.get("source_ids") or ())]
        return author_card_in_place(
            system, a, text=words, author=author_d, reader=reader_d or None, sources=sources_t, cause=cause_d,
            expected_version=int(expected_version), authored_by=author_d["id"] or author_d["kind"], known_ids=known,
            task_id=task_id, title=title, _hooks=_hooks, _after=_after)
    new_title = str(title).strip() if title is not None and str(title).strip() else record_title(attrs)
    new_keywords = [str(k).strip() for k in keywords if str(k or "").strip()] if keywords is not None else list(
        attrs.get("keywords") or ())
    at = str(understood_at or "").strip() or utc_now_iso()
    tid = str(task_id or "").strip()
    # `_attributes`: a pass's own bookkeeping written with the reading, in its transaction (communities_pass: a topic
    # authored in place keeps its verdict and what its author saw).
    extra = _json_safe(dict(_attributes or {}), "_attributes")

    def reserved(old: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(old)
        out.update({
            "title": new_title, "digest_method": method, "digest_version": n,
            "authored_by": author_d["id"] or author_d["kind"],
            "understanding": _understanding_attr(n, "digest", author_d, reader_d, cause_d, sources_t, derived, at),
        })
        if new_keywords:
            out["keywords"] = list(new_keywords)
        else:
            out.pop("keywords", None)
        out.update(extra)
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _version_row(rec, n, field="digest", text=words, title=new_title, keywords=new_keywords,
                            digest_method=method, author=author_d, reader=reader_d, sources=sources_t,
                            derived_from=derived, cause=cause_d, magnitude=magnitude or {}, task_id=tid, at=at)

    return _apply(system, record_id=str(a.subject), field="digest", new_object=words, narration=None,
                  reserved=reserved, version=version, expected_version=int(expected_version),
                  hooks=_hooks, after=_after)


def retitle(
    system: Any, record_id: str, *,
    title: str,
    author: Mapping[str, Any],
    cause: Union[str, Mapping[str, Any]],
    expected_version: int,
    reader: Optional[Mapping[str, Any]] = None,
    sources: Sequence[Mapping[str, Any]] = (),
    task_id: Optional[str] = None,
    understood_at: Optional[str] = None,
    _hooks: Sequence[Callable[[Any], None]] = (),
    _after: Sequence[Callable[[Dict[str, Any]], None]] = (),
    _attributes: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Change ONLY a record's title, in place, keeping every earlier title as a version (field `title`).

    Every kind with a title (all formed records), the entity's own acts included (interest, lesson, realization,
    diary entries...): the body, the keywords, the digest's reading and its provenance stay byte-identical; the row's
    `title`, `title_version` and `title_provenance` change, and the canonical text (the title is its first line), the
    keyword-index entry and the vector are replaced in the same transaction, like `rewrite_digest`. The title is
    stored exactly as given (stripped), never cut. `expected_version` is the compare-and-set on `title_version` (0
    for a record never retitled). The first retitle captures version 0 (the title the record held, with the
    provenance of the reading that wrote it). A record whose title is PENDING (formed with `pending=("title",)`,
    operator rulings 2026-11-09) is retitled like any other: version 0 holds None (text and title), version 1 the
    authored title; the write completes its live `title.author` tasks, clears the marker (`pending_cleared`), and an
    interest's card keyed on its graph id moves to the title's head (`card_rekey`). Returns the `rewrite_digest` result
    shape with
    `field="title"`; `outcome="unchanged"` (no version) when the title is already the current one. Refusal reasons
    (nothing written): `unknown_record`, `empty_title`, `hash_chained` (an owner-direct diary entry whose
    `entry_hash` attests its title), `closed`, `stale`, `embedder_unavailable`. Invalid arguments raise ValueError, as
    in `rewrite_digest`.
    """
    author_d = _author(author)
    reader_d = _reader(reader, author_d["kind"])
    sources_t = _sources(sources, author_d["kind"])
    cause_d = _cause(cause)
    words = str(title or "").strip()
    a = _resolve(system, record_id)
    if a is None:
        return _refusal("unknown_record", f"no formed record {record_id!r} in this store", record_id=str(record_id))
    base = {"record_id": str(a.subject), "assertion_id": str(a.assertion_id or ""), "field": "title"}
    if not words:
        return _refusal("empty_title", "a title is an explicit, complete phrase: an empty one would erase it",
                        **base)
    if _attrs(a).get("entry_hash") is not None:
        return _refusal("hash_chained", "this diary entry's entry_hash attests its title (diary_entry_hash); a new "
                        "title would break verify_diary_chain", **base)
    closures = _closures(system.journal, a.assertion_id)
    if closures:
        return _refusal("closed", f"the record is closed ({closures[0].kind}); retitle its current replacement",
                        replaced_by=_replaced_by(closures), **base)
    was_untitled = _title(_attrs(a)) is None
    out = _retitle_apply(system, a, words, author_d, reader_d, sources_t, cause_d,
                         task_id=str(task_id or "").strip(), at=str(understood_at or "").strip() or utc_now_iso(),
                         expected=int(expected_version), method=RETITLE_METHOD, hooks=_hooks, after=_after,
                         extra=_json_safe(dict(_attributes or {}), "_attributes"))
    if out.get("applied") and was_untitled and _attrs(a).get("record_kind") == "interest":
        rekey = _rekey_untitled_interest_card(system, a, words, author_d, reader_d, sources_t, cause_d)
        if rekey is not None:
            out["card_rekey"] = rekey
    return out


def _rekey_untitled_interest_card(system: Any, a: Any, words: str, author_d: Dict[str, Any],
                                  reader_d: Dict[str, Any], sources_t: Sequence[Dict[str, Any]],
                                  cause_d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The title of an untitled interest landed: its standing card, keyed on the interest's graph id while it had
    no title (`world_model.interest_target`), moves to the new title's subject head through `rekey_world_model` (the
    id key stays an alias), so the next pass forms no second card. None when no card stands on the id key; a
    refusal (e.g. `target_taken`: a card already stands on the head) is returned as is, nothing written."""
    from .store import TripleQuery
    from .world_model import interest_target
    from .world_model_alias import rekey_world_model

    old_key = interest_target(str(a.subject), None)
    new_key = interest_target(str(a.subject), words)
    homes = sorted({(str(c.scope), str(c.owner_id or "")) for c in system.store.query(
        TripleQuery(owner_id=str(a.owner_id or "") or None, predicate="dcterms:abstract", limit=0))
        if isinstance(c.attributes, dict) and c.attributes.get("record_kind") == "world_model"
        and str(c.attributes.get("target") or "").strip() == old_key})
    if not homes:
        return None
    if not new_key:
        return {"applied": False, "outcome": "refused", "reason": "no_subject_head", "old_key": old_key,
                "detail": "the new title's subject head is too short to name a subject; the card keeps the id key"}
    results = [rekey_world_model(system, old_key, new_key, scope=scope, owner_id=owner, author=author_d,
                                 reader=reader_d or None, sources=sources_t,
                                 cause={**cause_d, "pending_title": str(a.subject)},
                                 reason="the interest's pending title landed")
               for scope, owner in homes]
    return results[0] if len(results) == 1 else {"results": results}


def _retitle_apply(system: Any, a: Any, words: str, author_d: Dict[str, Any], reader_d: Dict[str, Any],
                   sources_t: Sequence[Dict[str, Any]], cause_d: Dict[str, Any], *, task_id: str, at: str,
                   expected: int, method: str, hooks: Sequence[Callable[[Any], None]] = (),
                   after: Sequence[Callable[[Dict[str, Any]], None]] = (),
                   extra: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    def reserved(old: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(old)
        out.update({"title": words, "title_version": n,
                    "title_provenance": _understanding_attr(n, "title", author_d, reader_d, cause_d,
                                                            tuple(sources_t), (), at)})
        out.update(extra or {})
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _title_version_row(rec, n, title=words, author=author_d, reader=reader_d, sources=sources_t,
                                  cause=cause_d, task_id=task_id, at=at, method=method)

    return _apply(system, record_id=str(a.subject), field="title", new_object=None, narration=None,
                  reserved=reserved, version=version, expected_version=expected, hooks=hooks, after=after)


def declare_pending(
    system: Any, record_id: str, *,
    fields: Sequence[str] = ("title", "summary"),
    cause: Union[str, Mapping[str, Any]] = "repair",
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Declare that a STORED record's title and/or summary is still being written: the record gets the marker and the
    authoring tasks a record formed with `pending=fields` gets (operator rulings 2026-11-09: a title and a summary
    are mandatory metadata of every memory, authored, never cut, no fallback). For the records formed before that
    rule: a legacy world-model card ("World model: <subject>", mechanical-card-v2), a legacy dream ("Dream: ..."), a
    record stored with a placeholder or no title.

    Same state as formation, any kind: `attributes.pending = {title, summary, since, attempts}` (since = now, merged
    into a marker already there), and per newly declared field formation's task (`title.author` / `digest.author`,
    capability summaries, `FORMATION_PRIORITY` (a topic's `COMMUNITY_PRIORITY`), `FORMATION_STRENGTH`, basis
    `<assertion id>@pending-<field>`, basis_version 0; `memory_tasks.plan_declared`), queued in the same transaction
    (SQLite home). A declared TITLE is stored None, as a pending title is at formation: the title it held is kept as a
    title version (version 0 with the provenance of the reading that wrote it, then None with this declaration's), and
    the canonical text, keyword entry and vector are replaced (the title is the canonical text's first line); an
    interest's standing card moves to `topic:<its graph id>` (`card_rekey`), the key a pending interest elects. A
    declared SUMMARY keeps the body as the provisional digest it becomes (never restored by `revert_digest`) and
    supersedes the record's live body task (`digest.rewrite`, a card's `card.author`). The drainer then completes the
    tasks with `retitle` and `rewrite_digest` exactly as for a record formed pending (a card's summary through the
    card's own write, its target, evidence and revision untouched; a dream's in place, its signals untouched).

    The journal keeps the declaration as a version row (field `pending`, `pending_version` on the row): text = the
    fields declared, author `DECLARER`, cause = {cause, reason?, pending: [fields], tasks: {field: task id},
    provisional?: {field, version}, already_pending?: [fields], repaired?: [fields]}; the opt-in replay family
    `revision` shows it.

    Returns {applied, outcome: applied | unchanged | rearmed | refused, reason, detail?, record_id, assertion_id,
    field: "pending", version, declared, already_pending, repaired, pending (the marker), tasks {field: task id},
    enqueued, adopted, superseded, provisional?, title_version?, vector_rewritten?, seq?, version_id?, card_rekey?}.
    Idempotent for a healthy record: every asked field already pending WITH its live task -> outcome "unchanged",
    reason `already_pending`, `tasks` naming them, nothing written or queued. An already-pending field NO live task
    owns (its enqueue failed, or every task ran out) is repaired (Codex review 2026-11-09 finding 11): with nothing
    new to declare, through `rearm_pending` (outcome "rearmed", `repaired` the fields re-armed); beside a new field,
    its fresh task joins the declaration's transaction (`repaired`). Refusals (nothing written): `unknown_record`, `no_task_queue` (no title or summary is ever stored
    missing without the task that writes it), `closed` (with `replaced_by`: declare its current replacement),
    `protected_kind` (a summary of the entity's own act: his words are the body; a PUBLIC diary projection's summary
    is declared, its body being the book's entry, while a private, owner-direct or chained entry stays refused:
    `diary.diary_summary_refusal`), `consolidation_record` (a ripple's
    consolidation summary is never rewritten by a task), `hash_chained` (a title an owner-direct diary entry's
    `entry_hash` attests), `stale`, `embedder_unavailable`. `fields` outside `PENDING_FIELDS`, an empty `fields` or a
    cause outside `REWRITE_CAUSES` raise ValueError.
    """
    from .memory_tasks import enqueue_declared, live_pending_tasks, plan_declared
    from .records import PENDING_FIELDS

    if isinstance(fields, (str, bytes)):
        raise ValueError(f"fields is a sequence of pending fields ({sorted(PENDING_FIELDS)}), not a string")
    wanted = [f for f in ("title", "summary") if f in {str(x or "").strip().lower() for x in fields}]
    unknown = sorted({str(x or "").strip().lower() for x in fields} - PENDING_FIELDS)
    if unknown or not wanted:
        raise ValueError(f"declare_pending fields must be a non-empty subset of {sorted(PENDING_FIELDS)} "
                         f"(unknown: {unknown})")
    cause_d = _cause(cause)
    why = str(reason or "").strip()
    if why:
        cause_d["reason"] = why
    a = _resolve(system, record_id)
    if a is None:
        return _refusal("unknown_record", f"no formed record {record_id!r} in this store", record_id=str(record_id))
    attrs = _attrs(a)
    kind = str(attrs.get("record_kind") or "").strip().lower()
    base = {"record_id": str(a.subject), "assertion_id": str(a.assertion_id or ""), "field": "pending"}
    queue = _queue_for(system, _backend(system))
    if queue is None:
        return _refusal("no_task_queue", "a pending title or summary is stored only beside the task that writes it: "
                        "open the home with MemorySystem(task_queue=True)", **base)
    closures = _closures(system.journal, a.assertion_id)
    if closures:
        return _refusal("closed", f"the record is closed ({closures[0].kind}); declare its current replacement",
                        replaced_by=_replaced_by(closures), **base)
    marker = dict(attrs["pending"]) if isinstance(attrs.get("pending"), Mapping) else {}
    already = [f for f in wanted if marker.get(f)]
    new = [f for f in wanted if not marker.get(f)]
    live = live_pending_tasks(queue, str(a.subject), already)
    # An already-pending field no live task owns (its enqueue failed, or every task ran out) is REPAIRED, never
    # answered `already_pending` with no task (Codex review 2026-11-09 finding 11): a healthy record stays idempotent.
    repair = [f for f in already if live[f] is None]
    if not new:
        if repair:
            out = rearm_pending(system, str(a.subject), cause=cause, reason=reason)
            out.update({"declared": [], "already_pending": already, "repaired": sorted(out.get("tasks") or {})
                        if out.get("applied") else []})
            return out
        return {"applied": False, "outcome": "unchanged", "reason": "already_pending",
                "detail": f"{', '.join(already)} already pending, each with its live task: nothing declared, "
                          "nothing queued",
                "already_pending": already, "declared": [], "pending": marker, "tasks": dict(live), **base}
    if "summary" in new and kind == "diary":
        # A legacy PUBLIC projection (its first line standing in as the summary) is repaired like any record: its
        # body is the book's entry, so its digest is only the summary (formation's rule: diary_summary_refusal).
        from .diary import diary_summary_refusal

        provenance = a.provenance if isinstance(getattr(a, "provenance", None), Mapping) else {}
        refusal = diary_summary_refusal(attrs, provenance)
        if refusal is not None:
            return _refusal("protected_kind", f"{refusal[1]} ({refusal[0]})", **base)
    elif "summary" in new and kind in UNDERSTANDING_PROTECTED_KINDS:
        return _refusal("protected_kind", f"kind {kind!r} is the entity's own act: its body is his words, never "
                        "authored by a task, so its summary cannot be pending", **base)
    if "summary" in new and attrs.get("summary_role") == RE_UNDERSTANDING_ROLE:
        return _refusal("consolidation_record", "a ripple's consolidation record is never rewritten by a task",
                        **base)
    if "title" in new and attrs.get("entry_hash") is not None:
        return _refusal("hash_chained", "this diary entry's entry_hash attests its title (diary_entry_hash); taking "
                        "it back to pending would break verify_diary_chain", **base)
    plan = plan_declared(system, queue, a, [*new, *repair])
    body = _field_of(kind)
    at = utc_now_iso()
    row_cause: Dict[str, Any] = {**cause_d, "pending": list(new),
                                 "tasks": {f: str(plan[f]["task_id"]) for f in plan}}
    if repair:
        row_cause["repaired"] = list(repair)
    provisional = {"field": body, "version": _current_version(attrs, body)} if "summary" in new else None
    if provisional is not None:
        row_cause["provisional"] = provisional
    if already:
        row_cause["already_pending"] = list(already)
    old_title = _title(attrs)

    def reserved(old: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(old)
        held = dict(old["pending"]) if isinstance(old.get("pending"), Mapping) else {}
        out["pending"] = {**held, "title": bool(held.get("title")) or "title" in new,
                          "summary": bool(held.get("summary")) or "summary" in new,
                          "since": held.get("since") or at, "attempts": int(held.get("attempts") or 0)}
        out["pending_version"] = n
        if "title" in new:
            out["title"] = None
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _version_row(rec, n, field="pending", text=", ".join(new),
                            title=None if "title" in new else _title(_attrs(rec)),
                            keywords=tuple(_attrs(rec).get("keywords") or ()), digest_method=DECLARE_PENDING_METHOD,
                            author=dict(DECLARER), reader={}, sources=(), derived_from=(), cause=row_cause,
                            magnitude={}, task_id="", at=at)

    queued: Dict[str, List[str]] = {}

    def enqueue(cur: Any) -> None:
        queued.update(enqueue_declared(queue, a, plan, cause=cause_d, body_kind=kind, _cur=cur))

    out = _apply(system, record_id=str(a.subject), field="pending", new_object=None, narration=None,
                 reserved=reserved, version=version, expected_version=_current_version(attrs, "pending"),
                 hooks=(enqueue,))
    out.update(base)
    if not out.get("applied"):
        return out
    after = _resolve(system, str(a.subject))
    out.update({"declared": list(new), "already_pending": list(already), "repaired": list(repair),
                "pending": dict(_attrs(after).get("pending") or {}) if after is not None else {},
                "tasks": {f: str(plan[f]["task_id"]) for f in plan}, "enqueued": queued.get("enqueued", []),
                "adopted": queued.get("adopted", []), "superseded": queued.get("superseded", [])})
    if provisional is not None:
        out["provisional"] = provisional
    if "title" in new and kind == "interest" and old_title is not None:
        rekey = _rekey_declared_interest_card(system, a, old_title, cause_d)
        if rekey is not None:
            out["card_rekey"] = rekey
    return out


def _rekey_declared_interest_card(system: Any, a: Any, old_title: str,
                                  cause_d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """An interest whose title was declared pending elects `topic:<its graph id>` until the title lands
    (`world_model.interest_target`): its standing card, keyed on the old title's subject head, moves there through
    `rekey_world_model` (the head stays an alias), so the next pass forms no second card and `retitle` moves it on
    to the new title's head. None when no card stands on the old head. A card another active interest still elects
    (same-subject interests fold into one card) stays where it is: refusal-shaped `shared_card`, nothing written."""
    from .store import TripleQuery
    from .world_model import interest_target
    from .world_model_alias import rekey_world_model

    old_key = interest_target(str(a.subject), old_title)
    new_key = interest_target(str(a.subject), None)
    if not old_key or old_key == new_key:
        return None
    rows = list(system.store.query(TripleQuery(owner_id=str(a.owner_id or "") or None, predicate="dcterms:abstract",
                                               limit=0)))
    homes = sorted({(str(c.scope), str(c.owner_id or "")) for c in rows
                    if isinstance(c.attributes, dict) and c.attributes.get("record_kind") == "world_model"
                    and str(c.attributes.get("target") or "").strip() == old_key
                    and not _closures(system.journal, c.assertion_id)})
    if not homes:
        return None
    sharing = sorted(str(r.subject) for r in rows
                     if isinstance(r.attributes, dict) and r.attributes.get("record_kind") == "interest"
                     and str(r.subject) != str(a.subject)
                     and interest_target(str(r.subject), record_title(r.attributes)) == old_key
                     and not _closures(system.journal, r.assertion_id))
    if sharing:
        return {"applied": False, "outcome": "unchanged", "reason": "shared_card", "old_key": old_key,
                "new_key": new_key, "interests": sharing,
                "detail": "other active interests elect this card: it stays on its key"}
    results = [rekey_world_model(system, old_key, new_key, scope=scope, owner_id=owner, author=dict(DECLARER),
                                 cause={**cause_d, "pending_title": str(a.subject)},
                                 reason="the interest's title was declared pending")
               for scope, owner in homes]
    return results[0] if len(results) == 1 else {"results": results}


def rearm_pending(
    system: Any, record_id: str, *,
    cause: Union[str, Mapping[str, Any]] = "repair",
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Re-arm a pending record whose authoring ran out: a field its marker says is pending but that has NO live (pending
    / deferred / leased) `title.author` / `digest.author` task, because every task it had failed after `max_attempts`
    claims, was skipped or superseded, gets a fresh one (operator rule 2026-11-09: "title + summary must ALWAYS exist";
    a record pending with only terminal tasks would stay pending forever; a repeated `declare_pending` repairs it
    through here). Formation's task exactly (`plan_declared` / `enqueue_declared`: same kind, capability `summaries`,
    `FORMATION_PRIORITY` (a topic's `COMMUNITY_PRIORITY`), `FORMATION_STRENGTH`, basis_version 0, the next free basis
    `<assertion id>@pending-<field>@<k>`; cause {cause, reason?, pending: <field>, rearmed: n}), queued in the same
    transaction as the marker (SQLite home). A field that still has a live task keeps it (listed in `live`).

    The marker stays (the title stays None, the body provisional; no embedder call): `attempts` restarts at the
    highest claim count of its live tasks (0 for the fresh ones), `rearmed` counts the re-arms and
    `last_rearmed_at` is now; `since` is kept. The journal keeps the re-arm as a version row of field `pending`
    (text = the fields re-armed, author `REARMER`, method `REARM_PENDING_METHOD`, cause {cause, reason?, rearmed: n,
    pending: [fields], tasks: {field: task id}, attempts_before, exhausted: {field: [{task_id, status, attempts,
    max_attempts, error}]}, live?}); the opt-in replay family `revision` shows it. The drainer then completes the
    fresh tasks with `retitle` / `rewrite_digest` exactly as for a record formed pending.

    Returns {applied, outcome: rearmed | unchanged | refused, reason, detail?, record_id, assertion_id,
    field: "pending", tasks {field: task id}, rearmed (the marker's re-arm count), pending (the marker), live
    {field: task id}, enqueued, superseded, exhausted, version?, seq?, version_id?}. Unchanged (nothing written):
    `not_pending` (no pending marker), `live_task` (every pending field has a live task; `tasks` names them).
    Refusals (nothing written): `unknown_record`, `no_task_queue`, `closed` (with `replaced_by`), `stale`. A cause
    outside `REWRITE_CAUSES` raises ValueError."""
    from .memory_tasks import enqueue_declared, live_pending_tasks, plan_declared

    cause_d = _cause(cause)
    why = str(reason or "").strip()
    if why:
        cause_d["reason"] = why
    a = _resolve(system, record_id)
    if a is None:
        return _refusal("unknown_record", f"no formed record {record_id!r} in this store", record_id=str(record_id))
    attrs = _attrs(a)
    kind = str(attrs.get("record_kind") or "").strip().lower()
    base = {"record_id": str(a.subject), "assertion_id": str(a.assertion_id or ""), "field": "pending"}
    queue = _queue_for(system, _backend(system))
    if queue is None:
        return _refusal("no_task_queue", "a pending title or summary is re-armed only with the task that writes it: "
                        "open the home with MemorySystem(task_queue=True)", **base)
    closures = _closures(system.journal, a.assertion_id)
    if closures:
        return _refusal("closed", f"the record is closed ({closures[0].kind}); its current replacement owes the "
                        "metadata", replaced_by=_replaced_by(closures), **base)
    marker = dict(attrs["pending"]) if isinstance(attrs.get("pending"), Mapping) else {}
    fields = [f for f in ("title", "summary") if marker.get(f)]
    before = int(marker.get("rearmed") or 0)
    if not fields:
        return {"applied": False, "outcome": "unchanged", "reason": "not_pending",
                "detail": "the record carries no pending marker: nothing to re-arm", "tasks": {}, "live": {},
                "rearmed": before, "pending": marker, **base}
    live = live_pending_tasks(queue, str(a.subject), fields)
    owned = {f: str(t) for f, t in live.items() if t is not None}
    dead = [f for f in fields if live[f] is None]
    if not dead:
        return {"applied": False, "outcome": "unchanged", "reason": "live_task",
                "detail": f"{', '.join(fields)} still owned by a live task: nothing re-armed", "tasks": owned,
                "live": owned, "rearmed": before, "pending": marker, **base}
    plan = plan_declared(system, queue, a, dead)
    n = before + 1
    at = utc_now_iso()
    exhausted = {f: [{k: t[k] for k in ("task_id", "status", "attempts", "max_attempts", "error")}
                     for t in queue.tasks(kind=(PENDING_TASK_KINDS[f],), target_id=str(a.subject))] for f in dead}
    live_attempts = max([int(t["attempts"]) for f in owned for t in queue.tasks(
        status=("pending", "deferred", "leased"), kind=(PENDING_TASK_KINDS[f],), target_id=str(a.subject))],
                        default=0)
    tasks = {f: str(plan[f]["task_id"]) for f in dead}
    row_cause: Dict[str, Any] = {**cause_d, "rearmed": n, "pending": list(dead), "tasks": tasks,
                                 "attempts_before": int(marker.get("attempts") or 0), "exhausted": exhausted}
    if owned:
        row_cause["live"] = dict(owned)

    def reserved(old: Dict[str, Any], v: int) -> Dict[str, Any]:
        out = dict(old)
        held = dict(old["pending"]) if isinstance(old.get("pending"), Mapping) else {}
        out["pending"] = {**held, "attempts": live_attempts, "rearmed": n, "last_rearmed_at": at}
        out["pending_version"] = v
        return out

    def version(rec: Any, v: int) -> UnderstandingVersion:
        return _version_row(rec, v, field="pending", text=", ".join(dead), title=_title(_attrs(rec)),
                            keywords=tuple(_attrs(rec).get("keywords") or ()), digest_method=REARM_PENDING_METHOD,
                            author=dict(REARMER), reader={}, sources=(), derived_from=(), cause=row_cause,
                            magnitude={}, task_id="", at=at)

    queued: Dict[str, List[str]] = {}

    def enqueue(cur: Any) -> None:
        queued.update(enqueue_declared(queue, a, {f: plan[f] for f in dead}, cause=cause_d, body_kind=kind,
                                       _cur=cur, stamp={"rearmed": n}))

    out = _apply(system, record_id=str(a.subject), field="pending", new_object=None, narration=None,
                 reserved=reserved, version=version, expected_version=_current_version(attrs, "pending"),
                 hooks=(enqueue,))
    out.update(base)
    if not out.get("applied"):
        return out
    after = _resolve(system, str(a.subject))
    out.update({"outcome": "rearmed", "reason": None, "tasks": tasks, "rearmed": n, "live": owned,
                "pending": dict(_attrs(after).get("pending") or {}) if after is not None else {},
                "enqueued": queued.get("enqueued", []), "superseded": queued.get("superseded", []),
                "exhausted": exhausted})
    return out


def narrate_dream(
    system: Any, dream_id: str, *,
    text: str,
    author: Mapping[str, Any],
    expected_version: int = 0,
    reader: Optional[Mapping[str, Any]] = None,
    sources: Sequence[Mapping[str, Any]] = (),
    cause: Union[str, Mapping[str, Any]] = "formation",
    task_id: Optional[str] = None,
    understood_at: Optional[str] = None,
    _hooks: Sequence[Callable[[Any], None]] = (),
    _after: Sequence[Callable[[Dict[str, Any]], None]] = (),
) -> Dict[str, Any]:
    """Store a narration BESIDE a dream's mechanical summary (additive): `attributes.narration`,
    `narration_version`, `narration_provenance`. The digest, the signals, the keyword index and the vector are
    untouched (the narration is not recall currency). Versioned like a digest (field `narration`; the first
    narration is version 1, `expected_version` 0). Returns the `rewrite_digest` result shape; extra refusal
    `not_a_dream`."""
    author_d = _author(author)
    reader_d = _reader(reader, author_d["kind"])
    sources_t = _sources(sources, author_d["kind"])
    cause_d = _cause(cause)
    words = str(text or "").strip()
    a = _resolve(system, dream_id)
    if a is None:
        return _refusal("unknown_record", f"no formed record {dream_id!r} in this store", record_id=str(dream_id))
    base = {"record_id": str(a.subject), "assertion_id": str(a.assertion_id or ""), "field": "narration"}
    if _attrs(a).get("record_kind") != "dream":
        return _refusal("not_a_dream", "narrate_dream narrates dreams only", **base)
    if not words:
        return _refusal("empty_text", "the engine never invents words", **base)
    at = str(understood_at or "").strip() or utc_now_iso()
    tid = str(task_id or "").strip()

    def reserved(old: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(old)
        out.update({"narration": words, "narration_version": n,
                    "narration_provenance": _understanding_attr(n, "narration", author_d, reader_d, cause_d,
                                                                sources_t, (), at)})
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _version_row(rec, n, field="narration", text=words, title=record_title(_attrs(rec)),
                            keywords=(), digest_method="narration", author=author_d, reader=reader_d,
                            sources=sources_t, derived_from=(), cause=cause_d, magnitude={}, task_id=tid, at=at)

    return _apply(system, record_id=str(a.subject), field="narration", new_object=None, narration=words,
                  reserved=reserved, version=version, expected_version=int(expected_version),
                  hooks=_hooks, after=_after)


def revert_digest(
    system: Any, record_id: str, to_version: int, *,
    expected_version: int,
    by: Optional[Mapping[str, Any]] = None,
    reason: Optional[str] = None,
    field: Optional[str] = None,
) -> Dict[str, Any]:
    """Restore version `to_version` as a NEW version (cause `revert`; nothing is erased). The restored reading
    keeps the author and reader of the words it restores; `by` ({kind, id}, default the operator) is who reverted,
    recorded in the cause with `reverted_to` and `reason`. `field` defaults to the record's own (digest, card for a
    world-model card, narration or title when asked; a digest or card version restores its title too, recorded as
    a title version, unless the record was retitled since its current reading: that title stays). Extra refusals:
    `unknown_version`, `provisional_summary` (the provisional digest a record was formed with, or a reading
    `declare_pending` made provisional), `not_revertible` (field `pending`: a declaration is not a reading)."""
    a = _resolve(system, record_id)
    if a is None:
        return _refusal("unknown_record", f"no formed record {record_id!r} in this store", record_id=str(record_id))
    kind = str(_attrs(a).get("record_kind") or "")
    fld = str(field or _field_of(kind))
    if fld not in VERSION_FIELDS:
        raise ValueError(f"field must be one of {sorted(VERSION_FIELDS)}")
    who = _author(by or {"kind": "operator", "id": "operator"})
    if fld == "pending":
        return _refusal("not_revertible", "a pending declaration is not a reading: the marker clears when the authored "
                        "title or summary is written", record_id=str(a.subject),
                        assertion_id=str(a.assertion_id or ""), field=fld)
    rows = [v for v in system.journal.versions(record_id=str(a.subject), field=fld) if v.version == int(to_version)]
    if not rows:
        return _refusal("unknown_version", f"no version {int(to_version)} of {fld} for this record",
                        record_id=str(a.subject), assertion_id=str(a.assertion_id or ""), field=fld)
    if fld == "target":
        return _refusal("use_rekey_world_model",
                        "a card's key moves through rekey_world_model (the old key stays an alias); re-key it back",
                        record_id=str(a.subject), assertion_id=str(a.assertion_id or ""), field=fld)
    old = rows[0]
    cause = {"cause": "revert", "reverted_to": int(to_version), "by": who,
             "reason": str(reason or "").strip() or None}
    if fld == "narration":
        return _restore_narration(system, a, old, cause, int(expected_version))
    if fld == "title":
        if old.text is None:
            return _refusal("null_title", "a title is mandatory metadata of every memory (operator 2026-11-09): this "
                            "version held none, so it cannot be restored; retitle instead",
                            record_id=str(a.subject), assertion_id=str(a.assertion_id or ""), field=fld)
        return _retitle_apply(system, a, old.text, dict(old.author) or {"kind": UNRECORDED, "id": ""},
                              dict(old.reader), tuple(old.sources), cause, task_id="", at=utc_now_iso(),
                              expected=int(expected_version), method=old.digest_method or RETITLE_METHOD)
    if fld in ("digest", "card") and (old.cause.get("pending_summary")
                                      or _declared_provisional(system, a, fld, int(to_version))):
        return _refusal("provisional_summary", "this version is the provisional digest the record was formed with "
                        "while its summary was pending; a summary is mandatory (operator 2026-11-09)",
                        record_id=str(a.subject), assertion_id=str(a.assertion_id or ""), field=fld)
    if fld == "card":
        return _restore_card(system, a, old, cause, int(expected_version))
    restored_author = dict(old.author) if old.author else {"kind": UNRECORDED, "id": ""}
    return _restore(system, a, old, cause, int(expected_version), fld, restored_author)


def _declared_provisional(system: Any, a: Any, fld: str, version: int) -> bool:
    """A reading `declare_pending` made provisional (the record's summary declared pending while it held this
    reading): like the provisional digest a record was formed with, it is never restored."""
    want = {"field": fld, "version": int(version)}
    return any(isinstance(v.cause.get("provisional"), Mapping) and dict(v.cause["provisional"]) == want
               for v in system.journal.versions(record_id=str(a.subject), field="pending"))


def _restore(system: Any, a: Any, old: UnderstandingVersion, cause: Dict[str, Any], expected: int, fld: str,
             restored_author: Dict[str, Any],
             extra: Optional[Callable[[Dict[str, Any], Dict[str, Any]], None]] = None) -> Dict[str, Any]:
    at = utc_now_iso()
    # A revert restores a reading's title only when the title is still that reading's: a title retitled since
    # (it differs from the current reading's version row) stays, so undoing words never re-cuts a repaired title.
    held = _current_version(_attrs(a), fld)
    now_rows = [v for v in system.journal.versions(record_id=str(a.subject), field=fld) if v.version == held]
    keep_title = bool(now_rows) and now_rows[0].title != _title(_attrs(a))

    def reserved(prev: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(prev)
        restored_title = _title(prev) if keep_title else (old.title or _title(prev))
        out.update({"title": restored_title, "digest_method": old.digest_method,
                    "digest_version": n, "authored_by": restored_author.get("id") or restored_author.get("kind"),
                    "understanding": _understanding_attr(n, fld, restored_author, dict(old.reader), cause,
                                                         tuple(old.sources), tuple(old.derived_from), at)})
        if old.keywords:
            out["keywords"] = list(old.keywords)
        else:
            out.pop("keywords", None)
        if extra is not None:
            extra(out, prev)
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _version_row(rec, n, field=fld, text=old.text, title=old.title, keywords=old.keywords,
                            digest_method=old.digest_method, author=restored_author, reader=dict(old.reader),
                            sources=tuple(old.sources), derived_from=tuple(old.derived_from), cause=cause,
                            magnitude={}, task_id="", at=at)

    return _apply(system, record_id=str(a.subject), field=fld, new_object=old.text, narration=None,
                  reserved=reserved, version=version, expected_version=expected)


def _restore_card(system: Any, a: Any, old: UnderstandingVersion, cause: Dict[str, Any], expected: int) -> Dict:
    restored_author = dict(old.author) if old.author else {"kind": UNRECORDED, "id": ""}

    def extra(out: Dict[str, Any], prev: Dict[str, Any]) -> None:
        if old.digest_method.startswith("authored"):
            out["authored_lead"] = old.text
        else:
            out.pop("authored_lead", None)
            out.pop("authored_known_ids", None)

    return _restore(system, a, old, cause, expected, "card", restored_author, extra)


def _restore_narration(system: Any, a: Any, old: UnderstandingVersion, cause: Dict[str, Any], expected: int) -> Dict:
    at = utc_now_iso()
    restored_author = dict(old.author)

    def reserved(prev: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(prev)
        out.update({"narration": old.text, "narration_version": n,
                    "narration_provenance": _understanding_attr(n, "narration", restored_author, dict(old.reader),
                                                                cause, tuple(old.sources), (), at)})
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _version_row(rec, n, field="narration", text=old.text, title=old.title, keywords=(),
                            digest_method="narration", author=restored_author, reader=dict(old.reader),
                            sources=tuple(old.sources), derived_from=(), cause=cause, magnitude={}, task_id="",
                            at=at)

    return _apply(system, record_id=str(a.subject), field="narration", new_object=None, narration=old.text,
                  reserved=reserved, version=version, expected_version=expected)


def author_card_in_place(
    system: Any, card: Any, *, text: str, author: Mapping[str, Any], reader: Optional[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]], cause: Union[str, Mapping[str, Any]], expected_version: Optional[int],
    authored_by: str, known_ids: Sequence[str], task_id: Optional[str] = None, title: Optional[str] = None,
    _hooks: Sequence[Callable[[Any], None]] = (), _after: Sequence[Callable[[Dict[str, Any]], None]] = (),
) -> Dict[str, Any]:
    """`author_world_model`'s in-place path (world_model.py owns the evidence rules and calls this), and a pending
    card summary written through `rewrite_digest`: the card keeps its id, revision and evidence; its text becomes the
    authored lead (field `card`). A `title` given with the text is written with it (its own title version, as
    `rewrite_digest`'s `title=`); None keeps the card's title (or its pending state)."""
    author_d = dict(author)
    if author_d.get("kind") != UNRECORDED:
        author_d = _author(author_d)
    reader_d = _reader(reader, author_d["kind"])
    sources_t = _sources(sources, author_d["kind"])
    cause_d = _cause(cause)
    words = str(text or "").strip()
    attrs = _attrs(card)
    current = _current_version(attrs, "card")
    expected = current if expected_version is None else int(expected_version)
    at = utc_now_iso()
    tid = str(task_id or "").strip()
    known = sorted(str(k) for k in known_ids)
    new_title = str(title).strip() if title is not None and str(title).strip() else None

    def reserved(old: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(old)
        out.update({"digest_method": "authored-card-v1", "digest_version": n, "authored_by": authored_by,
                    "authored_lead": words, "authored_known_ids": known,
                    "understanding": _understanding_attr(n, "card", author_d, reader_d, cause_d, sources_t,
                                                         tuple(known), at)})
        if new_title is not None:
            out["title"] = new_title
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _version_row(rec, n, field="card", text=words,
                            title=new_title if new_title is not None else record_title(_attrs(rec)),
                            keywords=tuple(_attrs(rec).get("keywords") or ()), digest_method="authored-card-v1",
                            author=author_d, reader=reader_d, sources=sources_t, derived_from=tuple(known),
                            cause=cause_d, magnitude={}, task_id=tid, at=at)

    return _apply(system, record_id=str(card.subject), field="card", new_object=words, narration=None,
                  reserved=reserved, version=version, expected_version=expected, hooks=_hooks, after=_after)


def rekey_card_in_place(
    system: Any, card: Any, *, new_key: str, author: Mapping[str, Any], cause: Union[str, Mapping[str, Any]],
    reader: Optional[Mapping[str, Any]] = None, sources: Sequence[Mapping[str, Any]] = (),
    understood_at: Optional[str] = None,
) -> Dict[str, Any]:
    """`rekey_world_model`'s write (world_model_alias.py owns the refusals and calls this): the card's key
    (`attributes.target`) becomes `new_key` IN PLACE, and the key it held joins `attributes.aliases`, so evidence,
    mentions and participants under the old key still land on this card. Graph id, assertion id, revision, evidence
    fingerprint, sources, text, title, keywords, vector, edges and usage stay as they are. Field `target`: version 0
    is the key the pass derived, version N+1 this key with its provenance; `target_version` is the compare-and-set.
    A person card's `participants` follow the pass's rule (the key plus every non-topic alias)."""
    author_d = _author(author)
    reader_d = _reader(reader, author_d["kind"])
    sources_t = _sources(sources, author_d["kind"])
    cause_d = _cause(cause)
    key = str(new_key or "").strip()
    if not key:
        raise ValueError("rekey_card_in_place requires a non-empty new_key")
    at = str(understood_at or "").strip() or utc_now_iso()

    def reserved(old: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(old)
        held = str(old.get("target") or "").strip()
        names = {str(x).strip() for x in (old.get("aliases") or ()) if isinstance(x, str) and str(x).strip()}
        if held:
            names.add(held)
        names.discard(key)
        aliases = sorted(names)
        out.update({"target": key, "aliases": aliases, "target_version": n,
                    "target_provenance": _understanding_attr(n, "target", author_d, reader_d, cause_d, sources_t, (),
                                                             at)})
        if key.startswith("topic:"):
            out.pop("participants", None)
        else:
            out["participants"] = [key, *(x for x in aliases if not x.startswith("topic:"))]
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _version_row(rec, n, field="target", text=key, title=_title(_attrs(rec)),
                            keywords=tuple(_attrs(rec).get("keywords") or ()), digest_method=REKEY_METHOD,
                            author=author_d, reader=reader_d, sources=sources_t, derived_from=(), cause=cause_d,
                            magnitude={}, task_id="", at=at)

    return _apply(system, record_id=str(card.subject), field="target", new_object=None, narration=None,
                  reserved=reserved, version=version, expected_version=_current_version(_attrs(card), "target"))


# --------------------------------------------------------------------------- reads


def versions(system: Any, record_id: str, *, field: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every reading of a record, oldest first, as dicts (the version row plus `current`: True on the reading the
    record holds now). `field` defaults to the record's own (digest, or card for a world-model card); pass
    `field="narration"` for a dream's narrations, `field="title"` for its titles (version 0 = the title it held
    before its first title change). A never-rewritten record returns []."""
    a = _resolve(system, record_id)
    if a is None:
        raise ValueError(f"unknown record {record_id!r}: no formed record with that graph id or digest assertion id")
    attrs = _attrs(a)
    fld = str(field or _field_of(str(attrs.get("record_kind") or "")))
    if fld not in VERSION_FIELDS:
        raise ValueError(f"field must be one of {sorted(VERSION_FIELDS)}")
    current = _current_version(attrs, fld)
    out = []
    for v in system.journal.versions(record_id=str(a.subject), field=fld):
        d = v.to_dict()
        d["current"] = v.version == current
        out.append(d)
    return out


def current_of(system: Any, record_id: str, *, max_hops: int = 32) -> Dict[str, Any]:
    """Follow supersede (and merge) closures from a record to the live one: {record_id (as asked), graph_id,
    current_id, current_assertion_id, hops, chain, closed: None | "retract" | "reinterpreted" (the live end is
    itself closed without a replacement)}. A card revised N times answers with its newest revision."""
    a = _resolve(system, record_id)
    if a is None:
        raise ValueError(f"unknown record {record_id!r}: no formed record with that graph id or digest assertion id")
    chain = [str(a.subject)]
    current = a
    closed: Optional[str] = None
    for _ in range(max(1, int(max_hops))):
        closures = _closures(system.journal, current.assertion_id)
        nxt_ids = _replaced_by(closures)
        if not nxt_ids:
            ends = [c.kind for c in closures if c.kind in ("retract", "reinterpreted")]
            closed = ends[0] if ends else None
            break
        nxt = _resolve(system, nxt_ids[0])
        if nxt is None or str(nxt.subject) in chain:
            break  # dangling or cyclic replacement: stop at the last resolvable record
        chain.append(str(nxt.subject))
        current = nxt
    return {"record_id": str(record_id), "graph_id": str(a.subject), "current_id": chain[-1],
            "current_assertion_id": str(current.assertion_id or ""), "hops": len(chain) - 1, "chain": chain,
            "closed": closed}


def understanding_fields(
    assertion: Any, *, version_count: Optional[int] = None, replaced_by: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """The provenance of a record's current reading, from its row (pure): digest_method, digest_version,
    version_count, authored_by {kind, id}, reader, understood_at, cause; cards add target, target_type,
    card_revision, source_count; dreams add narrated, narration_version; replaced_by when closed by a supersede.
    authored_by, reader, understood_at and cause are `reading_provenance`'s (a row nobody stamped reads as its
    formation reading). digest_version is always present (0 = never rewritten); version_count counts the readings
    (1 for a never-rewritten record, whose journal holds no version rows; absent when the count is unknown: a
    rewritten record read without a versions journal). Other keys whose value is unknown are absent."""
    attrs = _attrs(assertion)
    out: Dict[str, Any] = {}
    method = str(attrs.get("digest_method") or "").strip()
    if method:
        out["digest_method"] = method
    out["digest_version"] = _current_version(attrs, "digest")
    if version_count is not None:
        out["version_count"] = max(1, int(version_count))
    elif out["digest_version"] == 0:
        out["version_count"] = 1
    reading = reading_provenance(assertion)
    out["authored_by"] = reading["author"]
    if reading["reader"]:
        out["reader"] = reading["reader"]
    out["understood_at"] = reading["understood_at"]
    if reading["cause"]:
        out["cause"] = reading["cause"]
    kind = str(attrs.get("record_kind") or "")
    if kind == "world_model":
        target = str(attrs.get("target") or "").strip()
        if target:
            out["target"] = target
            out["target_type"] = target.split(":", 1)[0] if ":" in target else "topic"
        if attrs.get("revision") is not None:
            try:
                out["card_revision"] = int(attrs.get("revision"))
            except (TypeError, ValueError):
                pass
        if attrs.get("source_count") is not None:
            try:
                out["source_count"] = int(attrs.get("source_count"))
            except (TypeError, ValueError):
                pass
    if kind == "dream":
        out["narrated"] = bool(str(attrs.get("narration") or "").strip())
        if out["narrated"]:
            out["narration_version"] = _current_version(attrs, "narration")
    if replaced_by:
        out["replaced_by"] = list(replaced_by)
    return out


def record_understanding(system: Any, record_id: str) -> Dict[str, Any]:
    """The record read the gateway serves (DESIGN §10): {record_id (as asked), graph_id, assertion_id, kind, title,
    digest, keywords, payload_ref, observed_at, closed, current_id} plus `understanding_fields` (digest_method,
    digest_version, version_count, authored_by, reader, understood_at, card target/type/revision, replaced_by) and,
    for dreams, the narration with its provenance. Diary records are refused here (the book is their door)."""
    a = _resolve(system, record_id)
    if a is None:
        raise ValueError(f"unknown record {record_id!r}: no formed record with that graph id or digest assertion id")
    attrs = _attrs(a)
    kind = str(attrs.get("record_kind") or "")
    if kind == "diary":
        raise ValueError("diary records are read through the book (DIARY_READ), not as an understanding")
    fld = _field_of(kind)
    count = len(system.journal.versions(record_id=str(a.subject), field=fld))
    closures = _closures(system.journal, a.assertion_id)
    replaced = _replaced_by(closures)
    out: Dict[str, Any] = {
        "record_id": str(record_id), "graph_id": str(a.subject), "assertion_id": str(a.assertion_id or ""),
        "kind": kind, "title": record_title(attrs), "digest": str(a.object or ""),
        "keywords": list(attrs.get("keywords") or ()), "payload_ref": attrs.get("payload_ref"),
        "observed_at": str(a.observed_at or ""), "closed": closures[0].kind if closures else None,
    }
    if isinstance(attrs.get("pending"), dict):
        out["pending"] = dict(attrs["pending"])  # a title / summary still being written (records.PENDING_FIELDS)
    out.update(understanding_fields(a, version_count=count, replaced_by=replaced))
    out["current_id"] = current_of(system, str(a.subject))["current_id"] if replaced else str(a.subject)
    if kind == "dream":
        if out.get("narrated"):
            out["narration"] = str(attrs.get("narration") or "")
            prov = attrs.get("narration_provenance") if isinstance(attrs.get("narration_provenance"), dict) else {}
            out["narration_by"] = dict(prov.get("author") or {})
            if prov.get("reader"):
                out["narration_reader"] = dict(prov["reader"])
            out["narrated_at"] = str(prov.get("understood_at") or "")
        if isinstance(attrs.get("signals"), list):
            out["signals"] = attrs["signals"]
    return out
