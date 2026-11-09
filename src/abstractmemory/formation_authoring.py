"""A memory's title and summary are authored WITH it (operator ruling 2026-11-09; Codex review 2026-11-09 finding 10).

THE RULE: "the title + summary must ALWAYS exist for any memory" and they are authored, never cut, no fallback; a
record forms PENDING (`attributes.pending`, with its `title.author` / `digest.author` tasks) only after a RECORDED
authoring failure. Memory has no model access, so the passes that form records from their own bookkeeping
(`world_model_pass` / `world_model_update`, `dream_pass`, `mine_candidates_pass`, `consolidation_pass`,
`wake_cue_dedup_pass`, and `sleep_pass`, which runs the first four) take an optional host-supplied `author` callable:

    author(kind: str, body: str, context: Mapping[str, Any]) -> Mapping[str, Any]   (or raises)

- `kind`: the record kind about to form (`world_model`, `dream`, `summary`);
- `body`: the pass's provisional body, the text the metadata is authored FROM (a card's evidence briefing, the
  night's composition, an offer's or a candidate's composed text, a dedup witness's words);
- `context`: {pass, record_kind, scope, owner_id, fields (the fields wanted: "title" and/or "summary"), title (a
  title already authored, e.g. carried by a card's next revision, else None), source_ids (the records it stands on),
  attributes (the record's attributes as formed)};
- returns {title: str (when "title" is wanted), summary: str (when "summary" is wanted), author: {kind, id} (kind
  in `understanding.AUTHOR_KINDS`, never "mechanical"), reader: {provider, model, thinking} (required for
  "capability-model" / "entity-mind"), sources: [SourceRef dicts] (the ledger step of the call; required for those
  kinds, ADR 0003)}.

A wanted field returned non-empty is stored authored: the title with `title_provenance` (version 0, cause
formation), the summary as the record's digest with its `understanding` stamp and an authored method
(`authored-v1`; a card `authored-card-v1` with `authored_lead` / `authored_known_ids` / `authored_by`). Anything else
forms the record pending for the fields not authored, the failure recorded IN the marker
(`attributes.pending.failure = {reason, error_class, message, at, fields}`) and returned in the pass's receipt
(`authoring`), so the host can write its authoring-failures line:

- `no_author_supplied`: the pass got no callable (explicit, never silent);
- `author_raised`: the callable raised (`error_class` / `message` are the exception's);
- `invalid_result`: it returned something that is not authored metadata (not a mapping, a wanted field missing or
  empty, an author/reader/sources the provenance rules refuse).

A record that already exists (an idempotent replay) is never authored again: the pass checks before it calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

__all__ = [
    "AUTHORING_FAILURE_REASONS",
    "AuthorFn",
    "Authored",
    "author_and_shape",
    "author_formation",
    "authored_record",
    "merge_receipts",
    "new_receipt",
    "note",
]

AuthorFn = Callable[[str, str, Mapping[str, Any]], Mapping[str, Any]]

AUTHORING_FAILURE_REASONS = frozenset({"no_author_supplied", "author_raised", "invalid_result"})


@dataclass(frozen=True)
class Authored:
    """What `author_formation` got: the authored fields, the fields left pending and the failure that left them."""

    title: Optional[str] = None
    summary: Optional[str] = None
    pending: Tuple[str, ...] = ()
    failure: Optional[Dict[str, Any]] = None
    author: Dict[str, Any] = field(default_factory=dict)
    reader: Dict[str, Any] = field(default_factory=dict)
    sources: Tuple[Dict[str, Any], ...] = ()
    at: str = ""


def _failure(reason: str, fields: Sequence[str], at: str, message: str,
             error_class: Optional[str] = None) -> Dict[str, Any]:
    return {"reason": reason, "error_class": error_class, "message": message, "at": at, "fields": list(fields)}


def author_formation(author: Optional[AuthorFn], *, kind: str, body: str, context: Mapping[str, Any],
                     fields: Sequence[str]) -> Authored:
    """Ask the host's `author` for the wanted fields of a record about to form; never raises for the host's
    failure (it becomes the recorded failure the record forms pending with)."""
    from .journal import utc_now_iso
    from .understanding import _author, _reader, _sources

    wanted = tuple(f for f in ("title", "summary") if f in set(fields))
    at = utc_now_iso()
    if not wanted:
        return Authored(at=at)
    pass_name = str(context.get("pass") or "this pass")
    if author is None:
        return Authored(pending=wanted, at=at, failure=_failure(
            "no_author_supplied", wanted, at,
            f"{pass_name} got no author callable: the record forms pending and its authoring tasks write "
            f"{' and '.join(wanted)}"))
    try:
        result = author(str(kind), str(body or ""), {**dict(context), "fields": list(wanted)})
    except Exception as exc:  # the host's failure, recorded: never a fallback, never silent
        return Authored(pending=wanted, at=at, failure=_failure(
            "author_raised", wanted, at, str(exc) or repr(exc), type(exc).__name__))
    if not isinstance(result, Mapping):
        return Authored(pending=wanted, at=at, failure=_failure(
            "invalid_result", wanted, at, f"the author returned {type(result).__name__}, not a mapping "
            "{title, summary, author, reader, sources}", "TypeError"))
    words = {f: str(result.get(f) or "").strip() for f in wanted}
    authored = [f for f in wanted if words[f]]
    missing = [f for f in wanted if not words[f]]
    if not authored:
        return Authored(pending=wanted, at=at, failure=_failure(
            "invalid_result", wanted, at, f"the author returned no {' and no '.join(wanted)}", "ValueError"))
    try:
        author_d = _author(result.get("author"))
        if author_d["kind"] == "mechanical":
            raise ValueError("a mechanical author is not authorship: name who wrote the words")
        reader_d = _reader(result.get("reader"), author_d["kind"])
        sources_t = _sources(result.get("sources") or (), author_d["kind"])
    except ValueError as exc:
        return Authored(pending=wanted, at=at, failure=_failure("invalid_result", wanted, at, str(exc), "ValueError"))
    return Authored(
        title=words["title"] if "title" in authored else None,
        summary=words["summary"] if "summary" in authored else None,
        pending=tuple(missing), at=at, author=author_d, reader=reader_d, sources=sources_t,
        failure=_failure("invalid_result", missing, at, f"the author returned no {' and no '.join(missing)}",
                         "ValueError") if missing else None)


def authored_record(record: Any, got: Authored, *, known_ids: Sequence[str] = ()) -> Any:
    """The `MemoryRecordInput` to form: the authored title and summary in place, the rest pending with the
    recorded failure. A card's authored summary is labelled as `author_card_in_place` labels one
    (`authored-card-v1`, `authored_lead`, `authored_known_ids` = `known_ids`, `authored_by`)."""
    from .understanding import DEFAULT_AUTHORED_METHOD, _field_of, _understanding_attr

    attrs = dict(record.attributes or {})
    cause = {"cause": "formation"}
    title = record.title
    digest = record.digest
    if got.title is not None:
        title = got.title
        attrs["title_provenance"] = _understanding_attr(0, "title", got.author, got.reader, cause, got.sources, (),
                                                        got.at)
    if got.summary is not None:
        digest = got.summary
        body_field = _field_of(record.kind)
        attrs["understanding"] = _understanding_attr(0, body_field, got.author, got.reader, cause, got.sources,
                                                     tuple(str(k) for k in known_ids), got.at)
        if record.kind == "world_model":
            attrs.update({"digest_method": "authored-card-v1", "authored_lead": got.summary,
                          "authored_known_ids": sorted(str(k) for k in known_ids),
                          "authored_by": got.author.get("id") or got.author.get("kind")})
        else:
            attrs["digest_method"] = DEFAULT_AUTHORED_METHOD
    return replace(record, title=title, digest=digest, attributes=attrs, pending=tuple(got.pending),
                   pending_failure=dict(got.failure) if got.pending and got.failure else None)


def new_receipt() -> Dict[str, Any]:
    """An empty `authoring` receipt: {authored: [{record_id, record_kind, pass, fields}], failures: [{record_id,
    record_kind, pass, fields, reason, error_class, message, at}]}. The host writes its authoring-failures line from
    `failures`."""
    return {"authored": [], "failures": []}


def note(receipt: Dict[str, Any], pass_name: str, record: Any, got: Authored, record_id: Optional[str]) -> None:
    """Add one formed record to its pass's receipt (in place)."""
    authored = [f for f, v in (("title", got.title), ("summary", got.summary)) if v is not None]
    if authored:
        receipt["authored"].append({"record_id": record_id, "record_kind": record.kind, "pass": pass_name,
                                    "fields": authored})
    if got.pending and got.failure:
        receipt["failures"].append({"record_id": record_id, "record_kind": record.kind, "pass": pass_name,
                                    **dict(got.failure), "fields": list(got.pending)})


def merge_receipts(receipts: Sequence[Optional[Mapping[str, Any]]]) -> Dict[str, Any]:
    """Several passes' `authoring` receipts as one (sleep_pass's top-level receipt)."""
    out = new_receipt()
    for r in receipts:
        if isinstance(r, Mapping):
            out["authored"].extend(r.get("authored") or ())
            out["failures"].extend(r.get("failures") or ())
    return out


def context_for(pass_name: str, record: Any, *, scope: str, owner_id: str, fields: Sequence[str],
                source_ids: Sequence[str] = ()) -> Dict[str, Any]:
    """The `context` a pass hands its author."""
    return {"pass": pass_name, "record_kind": record.kind, "scope": str(scope), "owner_id": str(owner_id or ""),
            "fields": list(fields), "title": record.title, "source_ids": [str(s) for s in source_ids],
            "attributes": dict(record.attributes or {})}


def author_and_shape(author: Optional[AuthorFn], pass_name: str, record: Any, *, scope: str, owner_id: str,
                     fields: Sequence[str], source_ids: Sequence[str] = (),
                     known_ids: Sequence[str] = ()) -> Tuple[Any, Authored]:
    """Author a record about to form and return (the record to form, what was got)."""
    got = author_formation(author, kind=record.kind, body=record.digest, fields=fields,
                           context=context_for(pass_name, record, scope=scope, owner_id=owner_id, fields=fields,
                                               source_ids=source_ids))
    return authored_record(record, got, known_ids=known_ids), got

