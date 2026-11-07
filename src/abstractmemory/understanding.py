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
interest, realization); a dream's digest (the mechanical summary of the night stays; `narrate_dream` adds a narration
beside it); a world-model card outside `author_world_model` (which keeps the evidence rules); a closed record (its
replacement is the current one: `current_of`); a ripple's consolidation record (`summary_role: re-understanding`)
except by an operator.

WHO WROTE THE WORDS is recorded, never inferred: `author` = {kind, id} with kind in `AUTHOR_KINDS`
("entity-mind": the entity's own model; "capability-model": a model the entity's cognition profile names for this
capability, writing as "a passive memory process, part of me" (operator decision 2); "operator"; "mechanical");
`reader` = {provider, model, thinking}; `sources` = ADR 0003 `SourceRef` dicts naming the ledger step of the call (a
model author must name one). This module never invents text and applies no rule to the words it is given.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .canonical_text import canonical_text
from .journal import UnderstandingVersion, VERSION_FIELDS, utc_now_iso
from .records import resolve_digest_assertion
from .redigestion import MACHINE_AUTHORED_METHODS

__all__ = [
    "AUTHOR_KINDS",
    "DEFAULT_AUTHORED_METHOD",
    "REWRITE_CAUSES",
    "UNDERSTANDING_PROTECTED_KINDS",
    "current_of",
    "narrate_dream",
    "record_understanding",
    "revert_digest",
    "rewrite_digest",
    "understanding_fields",
    "version_id_for",
    "versions",
]

#: Who may author a reading (DESIGN §4). `unrecorded` is never accepted as input: it labels readings this package
#: did not see written (version 0 of a record whose digest_method names no mechanical writer, a legacy author label).
AUTHOR_KINDS = frozenset({"mechanical", "entity-mind", "capability-model", "operator"})
MODEL_AUTHOR_KINDS = frozenset({"entity-mind", "capability-model"})
UNRECORDED = "unrecorded"

#: Why a reading was written (DESIGN §4).
REWRITE_CAUSES = frozenset({"formation", "backfill", "ripple", "evidence", "operator", "revert"})

#: The entity's own acts: never rewritten by a background process (the redigestion rails, minus the born-digest
#: kinds that now have their own in-place verbs: dreams get a narration, cards get `author_world_model`).
UNDERSTANDING_PROTECTED_KINDS = frozenset({"diary", "value", "purpose", "trait", "interest", "realization"})

#: The digest_method a rewrite stamps unless the caller names another.
DEFAULT_AUTHORED_METHOD = "authored-v1"

#: The card floor's mechanical label (world_model.py); with MACHINE_AUTHORED_METHODS, the labels whose words a
#: machine wrote.
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
    return "narration_version" if field == "narration" else "digest_version"


def _current_version(attrs: Mapping[str, Any], field: str) -> int:
    try:
        return max(0, int(attrs.get(_version_attr(field)) or 0))
    except (TypeError, ValueError):
        return 0


def original_author(attrs: Mapping[str, Any]) -> Dict[str, Any]:
    """Who wrote a reading this package did not see written (version 0), from its digest_method label only."""
    method = str(attrs.get("digest_method") or "").strip()
    if method in MACHINE_AUTHORED_METHODS or method in MECHANICAL_CARD_METHODS:
        return {"kind": "mechanical", "id": method}
    label = attrs.get("authored_by")
    return {"kind": UNRECORDED, "id": str(label if isinstance(label, str) else "") or method}


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
    the open SQLite cursor (the task queue acks and supersedes there); `after` run once the write committed."""
    kind_backend = _backend(system)
    store, journal = system.store, system.journal
    a = _resolve(system, record_id)
    if a is None:
        return _refusal("unknown_record", f"no formed record {record_id!r} in this store")
    aid = str(a.assertion_id or "")
    attrs0 = _attrs(a)
    current = _current_version(attrs0, field)
    target_new = current + 1
    planned_attrs = reserved(attrs0, target_new)
    planned = replace(a, object=new_object if new_object is not None else a.object, attributes=planned_attrs)
    identical = (narration is not None and str(attrs0.get("narration") or "") == narration) or (
        narration is None and str(a.object or "") == str(new_object or ""))
    base = {"record_id": str(a.subject), "assertion_id": aid, "field": field}
    if identical:
        return {"applied": False, "outcome": "unchanged", "reason": "identical",
                "detail": "the text is already the current reading", "version": current, **base}
    if int(expected_version) != current:
        return _refusal("stale", f"expected version {int(expected_version)}, the record is at version {current}",
                        version=current, **base)
    vector: Optional[List[float]] = None
    write_vector = False
    text = canonical_text(planned)
    if field != "narration":
        had_vector = store.stored_vector(aid) is not None
        refusal, vector, write_vector = _embed(store, text, had_vector)
        if refusal is not None:
            refusal.update(base)
            return refusal
    v_new = version(a, target_new)
    v_zero = _version_zero(a, field) if current == 0 and field != "narration" else None
    written: List[UnderstandingVersion] = []
    queue = _queue_for(system, kind_backend)
    if queue is not None:
        # The task queue (0060) settles in the same transaction: the named task is acked, stale tasks superseded.
        def _settle(cur: Any) -> None:
            queue.on_rewrite(cur, record_id=str(a.subject), field=field, version=target_new,
                             task_id=v_new.task_id or None,
                             result={"version": target_new, "version_id": v_new.version_id,
                                     "seq": written[-1].seq if written else None, "field": field,
                                     "author_kind": v_new.author.get("kind"),
                                     "model": v_new.reader.get("model")})

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
                if now_version != current or fresh.object != a.object or (
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
                if write_vector and vector is not None and store.embedding_pin() is None:
                    _pin_first_write(store, vector, cur)
                store._rewrite_row_on(cur, row, rewritten, vector=vector, write_vector=write_vector)
                for hook in hooks:
                    hook(cur)
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
            if now_version != current or fresh.object != a.object:
                return _refusal("stale", "the record changed while the rewrite was prepared",
                                version=now_version, **base)
            rewritten = replace(fresh, attributes=reserved(fresh_attrs, target_new),
                                object=new_object if new_object is not None else fresh.object)
            stored = replace(rewritten, assertion_id=aid)
            if v_zero is not None:
                written.append(journal.append_version(v_zero))
            written.append(journal.append_version(v_new))
            if write_vector and store.embedding_pin() is None and vector is not None:
                _pin_first_write(store, vector, None)
            store._rewrite_row(aid, stored, vector=vector, write_vector=write_vector)
            for hook in hooks:
                hook(None)
    result = {"applied": True, "outcome": "applied", "reason": None, "version": target_new,
              "previous_version": current, "version_id": written[-1].version_id, "seq": written[-1].seq,
              "captured_original": v_zero is not None, "vector_rewritten": write_vector, **base}
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
    """The original reading, captured at the first rewrite (version 0)."""
    attrs = _attrs(a)
    provenance = dict(a.provenance) if isinstance(a.provenance, dict) else {}
    return UnderstandingVersion(
        record_id=str(a.subject), assertion_id=str(a.assertion_id), version=0, field=field,
        text=str(a.object or ""), scope=str(a.scope), owner_id=str(a.owner_id or ""),
        title=str(attrs.get("title") or ""), keywords=tuple(attrs.get("keywords") or ()),
        digest_method=str(attrs.get("digest_method") or ""), author=original_author(attrs),
        cause={"cause": "formation", "formation_provenance": _json_safe(provenance, "provenance")},
        understood_at=str(a.observed_at or ""), version_id=version_id_for(str(a.subject), field, 0),
    )


def _understanding_attr(n: int, field: str, author: Dict[str, Any], reader: Dict[str, Any], cause: Dict[str, Any],
                        sources: Tuple[Dict[str, Any], ...], derived_from: Tuple[str, ...], at: str) -> Dict[str, Any]:
    return {"version": n, "field": field, "author": author, "reader": reader, "cause": cause,
            "sources": list(sources), "derived_from": list(derived_from), "understood_at": at}


def _version_row(a: Any, n: int, *, field: str, text: str, title: str, keywords: Sequence[str], digest_method: str,
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
) -> Dict[str, Any]:
    """Replace a record's digest (and optionally its title and keywords) IN PLACE, keeping every earlier reading.

    `record_id` is the graph id or the digest assertion id. `expected_version` is the compare-and-set: the record's
    current `digest_version` (0 for a never-rewritten record; `versions()` / `record_understanding()` read it).
    Returns {applied, outcome: applied|unchanged|refused, reason, detail?, record_id, assertion_id, field, version,
    previous_version?, version_id?, seq?, captured_original?, vector_rewritten?}. Refusal reasons (nothing written):
    `unknown_record`, `protected_kind`, `use_narrate_dream`, `use_author_world_model`, `closed`,
    `consolidation_record`, `empty_text`, `stale`, `embedder_unavailable`. Invalid arguments (an author kind outside
    `AUTHOR_KINDS`, a model author without reader or sources, a cause outside `REWRITE_CAUSES`) raise ValueError.
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
    if kind in UNDERSTANDING_PROTECTED_KINDS:
        return _refusal("protected_kind", f"kind {kind!r} is the entity's own act; it is never rewritten", **base)
    if kind == "dream":
        return _refusal("use_narrate_dream",
                        "a dream's digest is the night's mechanical summary; narrate_dream adds a narration", **base)
    if kind == "world_model":
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
    new_title = str(title).strip() if title is not None and str(title).strip() else str(attrs.get("title") or "")
    new_keywords = [str(k).strip() for k in keywords if str(k or "").strip()] if keywords is not None else list(
        attrs.get("keywords") or ())
    at = str(understood_at or "").strip() or utc_now_iso()
    tid = str(task_id or "").strip()

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
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _version_row(rec, n, field="digest", text=words, title=new_title, keywords=new_keywords,
                            digest_method=method, author=author_d, reader=reader_d, sources=sources_t,
                            derived_from=derived, cause=cause_d, magnitude=magnitude or {}, task_id=tid, at=at)

    return _apply(system, record_id=str(a.subject), field="digest", new_object=words, narration=None,
                  reserved=reserved, version=version, expected_version=int(expected_version),
                  hooks=_hooks, after=_after)


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
        return _version_row(rec, n, field="narration", text=words, title=str(_attrs(rec).get("title") or ""),
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
    world-model card, narration when asked). Extra refusal: `unknown_version`."""
    a = _resolve(system, record_id)
    if a is None:
        return _refusal("unknown_record", f"no formed record {record_id!r} in this store", record_id=str(record_id))
    kind = str(_attrs(a).get("record_kind") or "")
    fld = str(field or _field_of(kind))
    if fld not in VERSION_FIELDS:
        raise ValueError(f"field must be one of {sorted(VERSION_FIELDS)}")
    who = _author(by or {"kind": "operator", "id": "operator"})
    rows = [v for v in system.journal.versions(record_id=str(a.subject), field=fld) if v.version == int(to_version)]
    if not rows:
        return _refusal("unknown_version", f"no version {int(to_version)} of {fld} for this record",
                        record_id=str(a.subject), assertion_id=str(a.assertion_id or ""), field=fld)
    old = rows[0]
    cause = {"cause": "revert", "reverted_to": int(to_version), "by": who,
             "reason": str(reason or "").strip() or None}
    if fld == "narration":
        return _restore_narration(system, a, old, cause, int(expected_version))
    if fld == "card":
        return _restore_card(system, a, old, cause, int(expected_version))
    restored_author = dict(old.author) if old.author else {"kind": UNRECORDED, "id": ""}
    return _restore(system, a, old, cause, int(expected_version), fld, restored_author)


def _restore(system: Any, a: Any, old: UnderstandingVersion, cause: Dict[str, Any], expected: int, fld: str,
             restored_author: Dict[str, Any],
             extra: Optional[Callable[[Dict[str, Any], Dict[str, Any]], None]] = None) -> Dict[str, Any]:
    at = utc_now_iso()

    def reserved(prev: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(prev)
        out.update({"title": old.title or str(prev.get("title") or ""), "digest_method": old.digest_method,
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
    authored_by: str, known_ids: Sequence[str], task_id: Optional[str] = None,
    _hooks: Sequence[Callable[[Any], None]] = (), _after: Sequence[Callable[[Dict[str, Any]], None]] = (),
) -> Dict[str, Any]:
    """`author_world_model`'s in-place path (world_model.py owns the evidence rules and calls this): the card keeps
    its id, revision and evidence; its text becomes the authored lead (field `card`)."""
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

    def reserved(old: Dict[str, Any], n: int) -> Dict[str, Any]:
        out = dict(old)
        out.update({"digest_method": "authored-card-v1", "digest_version": n, "authored_by": authored_by,
                    "authored_lead": words, "authored_known_ids": known,
                    "understanding": _understanding_attr(n, "card", author_d, reader_d, cause_d, sources_t,
                                                         tuple(known), at)})
        return out

    def version(rec: Any, n: int) -> UnderstandingVersion:
        return _version_row(rec, n, field="card", text=words, title=str(_attrs(rec).get("title") or ""),
                            keywords=tuple(_attrs(rec).get("keywords") or ()), digest_method="authored-card-v1",
                            author=author_d, reader=reader_d, sources=sources_t, derived_from=tuple(known),
                            cause=cause_d, magnitude={}, task_id=tid, at=at)

    return _apply(system, record_id=str(card.subject), field="card", new_object=words, narration=None,
                  reserved=reserved, version=version, expected_version=expected, hooks=_hooks, after=_after)


# --------------------------------------------------------------------------- reads


def versions(system: Any, record_id: str, *, field: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every reading of a record, oldest first, as dicts (the version row plus `current`: True on the reading the
    record holds now). `field` defaults to the record's own (digest, or card for a world-model card); pass
    `field="narration"` for a dream's narrations. A never-rewritten record returns []."""
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
    Keys whose value is unknown are absent (never fabricated); digest_version is always present (0 = never
    rewritten)."""
    attrs = _attrs(assertion)
    out: Dict[str, Any] = {}
    method = str(attrs.get("digest_method") or "").strip()
    if method:
        out["digest_method"] = method
    out["digest_version"] = _current_version(attrs, "digest")
    if version_count is not None:
        out["version_count"] = int(version_count)
    und = attrs.get("understanding") if isinstance(attrs.get("understanding"), dict) else None
    if und:
        out["authored_by"] = dict(und.get("author") or {})
        if und.get("reader"):
            out["reader"] = dict(und["reader"])
        out["understood_at"] = str(und.get("understood_at") or "")
        cause = und.get("cause") if isinstance(und.get("cause"), dict) else {}
        if cause.get("cause"):
            out["cause"] = str(cause["cause"])
    else:
        out["authored_by"] = original_author(attrs)
        out["understood_at"] = str(getattr(assertion, "observed_at", "") or "")
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
        "kind": kind, "title": str(attrs.get("title") or ""), "digest": str(a.object or ""),
        "keywords": list(attrs.get("keywords") or ()), "payload_ref": attrs.get("payload_ref"),
        "observed_at": str(a.observed_at or ""), "closed": closures[0].kind if closures else None,
    }
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
