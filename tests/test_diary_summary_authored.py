"""A PUBLIC diary entry's summary is authored like any record's; its body and the chain stay untouched.

Operator rule 2026-11-09: "the title + summary must ALWAYS exist for any memory — mandatory metadata, authored, never
a slug or cut, no fallback." Memory refused any pending or authored summary on a diary record (the entity's own act:
`UNDERSTANDING_PROTECTED_KINDS`), so the runtime stood his first line in as the summary (runtime 7dd32e1, Codex review
2 finding 10). A PUBLIC book projection's body is the book's entry (the runtime's hash-chained ledger, named by
`attributes.entry_id` and the provenance's `diary_entry` source with the chain's record hash); the record's digest is
only its summary. So it now takes (a) an authored summary at formation (`attributes.understanding` with author, reader
and ledger sources), (b) `pending=("summary",)` with its `digest.author` task, and (c) `rewrite_digest` completing it.
A private entry (`attributes.private`, act-only and content-free), an owner-direct one (no book: the digest IS his
words) and a chained one (`entry_hash` attests the digest) are refused as before (`diary.diary_summary_refusal`).

Pinned here, on both substrate pairs (in-memory, and SQLite store + journal sharing one file):
- formation: every diary type forms with an authored summary (its provenance checked) or pending with its task;
- completion: `rewrite_digest` writes the summary, completes the task, clears the marker; the provisional words stay
  whole as version 0 and are never restored; a summary not pending stays `protected_kind`;
- the body and the chain: the book reference (entry id, the chain's record hash) byte-equal, an owner-direct chained
  entry beside it byte-equal and `verify_diary_chain` intact;
- refusals: private (fail-closed on any non-False flag), owner-direct and chained entries, at formation and in
  `rewrite_digest` (a forged pending marker on a private row);
- visibility: the summary versions are sealed in the replay `revision` stream like the title versions, and the task
  packet serves the diary redacted.

MUTATION LIST (each applied to a scratch COPY of src/, this file run against it with PYTHONPATH, red confirmed):
- D1 MemoryRecordInput refuses a pending summary on every diary again ->
  test_a_public_entry_forms_with_its_summary_pending;
- D2 the private check dropped -> test_a_private_entry_is_still_refused;
- D3 the private check reads only `is True` -> test_a_private_entry_is_still_refused;
- D4 the owner-direct check dropped -> test_owner_direct_and_chained_entries_are_refused;
- D5 the hash-chained check dropped -> test_owner_direct_and_chained_entries_are_refused;
- D6 rewrite_digest refuses every diary again -> test_a_pending_summary_is_completed_by_rewrite_digest;
- D7 rewrite_digest skips the diary refusal -> test_a_private_entry_is_still_refused;
- D8 rewrite_digest opens a diary whose summary is not pending -> test_a_summary_not_pending_stays_protected;
- D9 the authored stamp not checked -> test_an_authored_summary_carries_its_provenance;
- D10 a mechanical author accepted -> test_an_authored_summary_carries_its_provenance;
- D11 the diary revision seal skipped -> test_summary_versions_are_sealed_like_the_title.
"""

from __future__ import annotations

import hashlib
import warnings
from typing import Any, Dict

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import (  # noqa: E402
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    TripleAssertion,
    verify_diary_chain,
)
from abstractmemory.diary import diary_entry_hash, diary_summary_refusal  # noqa: E402
from abstractmemory.memory_tasks import FORMATION_PRIORITY  # noqa: E402
from abstractmemory.records import DIARY_TYPES, resolve_digest_assertion  # noqa: E402

SCOPE = "diary"
OWNER = "entity:nerin"
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "step", "run_id": "run-diary-1", "seq": 4}]
FIRST_LINE = "I walked to the quorvanth registry and counted the rural sites twice."
AUTHORED = "A walk to the registry to recount its rural sites, and what the second count changed."
BOOK_HASH = "b" * 64


class Embedder:
    """Deterministic unit vectors from the text hash."""

    model = "fake-hash-16"

    def embed_texts(self, texts):
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(16)
            out.append((v / np.linalg.norm(v)).tolist())
        return out


@pytest.fixture(params=["memory", "sqlite"])
def home(request, tmp_path):
    emb = Embedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if request.param == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        else:
            path = tmp_path / "memory.sqlite3"
            store, journal = SQLiteTripleStore(path, embedder=emb), SQLiteJournal(path)
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=True)
    yield system
    system.journal.close()
    system.store.close()


def _stamp(**over: Any) -> Dict[str, Any]:
    """The authored summary's reading, the shape `formation_authoring.authored_record` writes."""
    return {"version": 0, "field": "digest", "author": dict(MODEL), "reader": dict(READER),
            "cause": {"cause": "formation"}, "sources": list(STEP), "derived_from": [],
            "understood_at": "2026-11-09T18:00:00.000000Z", **over}


def _attrs(key: str, diary_type: str = "note", **extra: Any) -> Dict[str, Any]:
    return {"entry_id": f"book-{key}", "diary_type": diary_type, "diary_kind": diary_type,
            "written_at": "2026-11-09T17:59:00Z", **extra}


def _provenance(key: str, source: str = "diary-projection") -> Dict[str, Any]:
    return {"source": source, "entry_id": f"book-{key}",
            "sources": [{"kind": "diary_entry", "entry_id": f"book-{key}", "run_id": "diary:entity:nerin",
                         "digest": BOOK_HASH}]}


def _input(key: str, *, digest: str = FIRST_LINE, title: Any = "The registry recount", diary_type: str = "note",
           attributes: Any = None, provenance: Any = None, **kw: Any) -> MemoryRecordInput:
    return MemoryRecordInput(kind="diary", title=title, digest=digest,
                             attributes=_attrs(key, diary_type) if attributes is None else attributes,
                             provenance=_provenance(key) if provenance is None else provenance, **kw)


def _form(system, key: str, **kw: Any) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many([_input(key, **kw)], scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


def _tasks(system, gid: str, kind: str = "digest.author"):
    return system.tasks.tasks(kind=(kind,), target_id=gid)


def _author(system, gid: str, *, task_id: Any = None, expected: int = 0) -> Dict[str, Any]:
    return system.rewrite_digest(gid, text=AUTHORED, author=MODEL, reader=READER, sources=STEP, cause="formation",
                                 expected_version=expected, task_id=task_id)


# --------------------------------------------------------------------------- formation


@pytest.mark.parametrize("diary_type", sorted(DIARY_TYPES))
def test_a_public_entry_forms_with_an_authored_summary(home, diary_type) -> None:
    gid = _form(home, f"a-{diary_type}", digest=AUTHORED, diary_type=diary_type,
                attributes=_attrs(f"a-{diary_type}", diary_type, understanding=_stamp(), digest_method="authored-v1"))
    row = _row(home, gid)
    assert row.object == AUTHORED and "pending" not in row.attributes
    assert row.attributes["understanding"]["author"] == MODEL
    assert row.attributes["understanding"]["reader"] == READER and row.attributes["understanding"]["sources"] == STEP
    assert row.attributes["digest_method"] == "authored-v1" and row.attributes["diary_type"] == diary_type
    assert _tasks(home, gid) == [] and _tasks(home, gid, "digest.rewrite") == []      # authored: no task owed


def test_an_authored_summary_carries_its_provenance() -> None:
    for bad, match in ((_stamp(sources=[]), "ledger step"), (_stamp(reader=None), "reader"),
                       (_stamp(author={"kind": "mechanical", "id": "first-line"}), "never mechanical"),
                       (_stamp(author={"kind": "someone"}), "author.kind"), (_stamp(field="card"), "'digest'"),
                       ("an authored summary", "authored summary's reading")):
        with pytest.raises(ValueError, match=match):
            _input("bad", digest=AUTHORED, attributes=_attrs("bad", understanding=bad))
    # The operator, and the entity's own model with its reader and step, author too.
    assert _input("op", digest=AUTHORED, attributes=_attrs("op", understanding=_stamp(
        author={"kind": "operator", "id": "laurent"}, reader={}, sources=[])))
    assert _input("em", digest=AUTHORED, attributes=_attrs("em", understanding=_stamp(
        author={"kind": "entity-mind", "id": OWNER})))


@pytest.mark.parametrize("diary_type", sorted(DIARY_TYPES))
def test_a_public_entry_forms_with_its_summary_pending(home, diary_type) -> None:
    gid = _form(home, f"p-{diary_type}", diary_type=diary_type, pending=("summary",))
    row = _row(home, gid)
    assert row.object == FIRST_LINE                                            # the provisional words, as given
    assert row.attributes["pending"] == {"title": False, "summary": True, "since": row.observed_at, "attempts": 0}
    [task] = _tasks(home, gid)
    assert task["status"] == "pending" and task["capability"] == "summaries"
    assert task["priority"] == FORMATION_PRIORITY and task["cause"] == {"cause": "formation", "pending": "summary"}


# --------------------------------------------------------------------------- completion, body, chain


def test_a_pending_summary_is_completed_by_rewrite_digest(home) -> None:
    # Beside it, an owner-direct CHAINED entry: the chain the engine verifies covers its digest (his words).
    chained = _form(home, "chain-1", title="A chained entry", digest="Owner-direct words, attested.",
                    attributes={"diary_type": "note", "prev_entry_hash": ""}, provenance={"source": "owner-direct"})
    before_chained = _row(home, chained)
    assert before_chained.attributes["entry_hash"] == diary_entry_hash(
        "A chained entry", "Owner-direct words, attested.", before_chained.observed_at)

    gid = _form(home, "p-1", title=None, pending=("title", "summary"))
    before = _row(home, gid)
    [task] = _tasks(home, gid)
    out = _author(home, gid, task_id=task["task_id"])
    assert out["applied"] is True and out["pending_cleared"] == ["summary"]
    assert home.tasks.task(task["task_id"])["status"] == "done"
    row = _row(home, gid)
    assert row.object == AUTHORED and row.attributes["pending"]["title"] is True    # the title still owed
    assert row.attributes["understanding"]["author"] == MODEL and row.attributes["digest_method"] == "authored-v1"
    assert home.retitle(gid, title="The registry recount", author=MODEL, reader=READER, sources=STEP,
                        cause="formation", expected_version=0)["pending_cleared"] == ["title"]
    assert "pending" not in _row(home, gid).attributes

    # The body is the book's entry: memory's reference to it stays byte-equal (the chain's record hash included).
    after = _row(home, gid)
    assert after.provenance == before.provenance and after.provenance["sources"][0]["digest"] == BOOK_HASH
    assert after.subject == before.subject and after.assertion_id == before.assertion_id
    assert after.observed_at == before.observed_at
    for key in ("entry_id", "diary_type", "diary_kind", "written_at"):
        assert after.attributes[key] == before.attributes[key]
    assert "entry_hash" not in after.attributes and "prev_entry_hash" not in after.attributes
    # The provisional words stay whole as version 0, never restored.
    v0 = home.versions(gid)[0]
    assert v0["version"] == 0 and v0["text"] == FIRST_LINE and v0["cause"]["pending_summary"] is True
    back = home.revert_digest(gid, 0, expected_version=1)
    assert back["applied"] is False and back["reason"] == "provisional_summary"
    # The chain: the chained entry untouched byte for byte, and it verifies.
    now_chained = _row(home, chained)
    assert (now_chained.object, now_chained.attributes, now_chained.observed_at) == (
        before_chained.object, before_chained.attributes, before_chained.observed_at)
    assert verify_diary_chain(home.store, scope=SCOPE, owner_id=OWNER) == {"intact": True, "break_at": None,
                                                                           "entries": 2}


def test_a_summary_not_pending_stays_protected(home) -> None:
    authored = _form(home, "a-1", digest=AUTHORED,
                     attributes=_attrs("a-1", understanding=_stamp(), digest_method="authored-v1"))
    plain = _form(home, "plain-1")                       # a legacy public projection: his first line, nothing owed
    for gid in (authored, plain):
        out = home.rewrite_digest(gid, text="Another reading.", author=MODEL, reader=READER, sources=STEP,
                                  cause="repair", expected_version=0)
        assert out["applied"] is False and out["reason"] == "protected_kind"
    assert _row(home, authored).object == AUTHORED and _row(home, plain).object == FIRST_LINE
    # Completed once, the summary is his entry's again: no second background rewrite.
    gid = _form(home, "p-2", pending=("summary",))
    assert _author(home, gid)["applied"] is True
    again = home.rewrite_digest(gid, text="Yet another reading.", author=MODEL, reader=READER, sources=STEP,
                                cause="repair", expected_version=1)
    assert again["reason"] == "protected_kind" and _row(home, gid).object == AUTHORED


# --------------------------------------------------------------------------- refusals


def test_a_private_entry_is_still_refused(home) -> None:
    private = {"entry_id": "book-priv", "written_at": "2026-11-09T17:59:00Z", "private": True}
    for flag in (True, "yes", 1):
        attrs = {**private, "private": flag}
        with pytest.raises(ValueError, match="private_entry"):
            _input("priv", title="Diary entry (private) — 2026-11-09 [k-priv]", digest="Wrote a private diary entry.",
                   attributes=attrs, pending=("summary",))
        with pytest.raises(ValueError, match="private_entry"):
            _input("priv", digest=AUTHORED, attributes={**attrs, "understanding": _stamp()})
    # private=False is a public entry.
    assert _input("pub", attributes={**private, "private": False}, pending=("summary",)).pending == ("summary",)
    # A stored private entry stays as formed: no summary write.
    gid = _form(home, "priv-1", title="Diary entry (private) — 2026-11-09 [riv-1]",
                digest="Wrote a private diary entry.", attributes=dict(private))
    assert home.rewrite_digest(gid, text=AUTHORED, author=MODEL, reader=READER, sources=STEP, cause="formation",
                               expected_version=0)["reason"] == "protected_kind"
    # Even a forged pending marker on a private row is refused, and nothing is written.
    forged = TripleAssertion(
        subject="ex:diary-forged0000000000000000000", predicate="dcterms:abstract",
        object="Wrote a private diary entry.", scope=SCOPE, owner_id=OWNER,
        attributes={"literal": True, "record_kind": "diary", "title": "Diary entry (private) — 2026-11-09 [forged]",
                    "diary_type": "note", "entry_id": "book-forged", "private": True,
                    "pending": {"title": False, "summary": True, "since": "2026-11-09T18:00:00Z", "attempts": 0}},
        provenance={"source": "diary-projection", "entry_id": "book-forged"},
        assertion_id="f" * 32)
    home.store.add([forged])
    out = home.rewrite_digest(forged.subject, text=AUTHORED, author=MODEL, reader=READER, sources=STEP,
                              cause="formation", expected_version=0)
    assert out["applied"] is False and out["reason"] == "protected_kind" and "private_entry" in out["detail"]
    assert _row(home, forged.subject).object == "Wrote a private diary entry."
    assert home.versions(forged.subject) == []


def test_owner_direct_and_chained_entries_are_refused() -> None:
    with pytest.raises(ValueError, match="owner_direct"):
        _input("od", attributes={"diary_type": "note"}, provenance={"source": "owner-direct"}, pending=("summary",))
    with pytest.raises(ValueError, match="owner_direct"):
        _input("od", digest=AUTHORED, attributes={"diary_type": "note", "understanding": _stamp()},
               provenance={"source": "entity-direct"})                          # canonicalized to owner-direct
    with pytest.raises(ValueError, match="hash_chained"):
        _input("ch", attributes=_attrs("ch", prev_entry_hash=""), pending=("summary",))
    with pytest.raises(ValueError, match="hash_chained"):
        _input("ch", attributes=_attrs("ch", entry_hash="0" * 64), pending=("summary",))
    # The rule itself: None only for a public projection.
    assert diary_summary_refusal(_attrs("ok"), _provenance("ok")) is None
    assert diary_summary_refusal({**_attrs("p"), "private": True}, _provenance("p"))[0] == "private_entry"
    assert diary_summary_refusal(_attrs("o"), {"source": "owner-direct"})[0] == "owner_direct"
    assert diary_summary_refusal(_attrs("o"), None)[0] == "owner_direct"
    assert diary_summary_refusal(_attrs("c", prev_entry_hash=""), _provenance("c"))[0] == "hash_chained"
    # The other protected kinds keep their rule.
    with pytest.raises(ValueError, match="never authored by a task"):
        MemoryRecordInput(kind="realization", title="A realization", digest="x", pending=("summary",))


# --------------------------------------------------------------------------- visibility


def test_summary_versions_are_sealed_like_the_title(home) -> None:
    gid = _form(home, "seal-1", pending=("summary",))
    [task] = _tasks(home, gid)
    packet = home.task_packet(task["task_id"])
    assert packet["record"]["redacted"] == "diary" and packet["record"]["digest"] == ""
    assert packet["record"]["entry_id"] == "book-seal-1" and packet["expected_version"] == 0
    assert _author(home, gid, task_id=task["task_id"])["applied"] is True
    revisions = [e for e in home.export_replay(families=("revision",)) if e["payload"]["record_id"] == gid]
    assert [e["payload"]["version"] for e in revisions] == [0, 1]
    for e in revisions:
        assert e["payload"]["field"] == "digest" and e["payload"]["redacted"] == "diary"
        assert e["payload"]["text"] == "" and e["payload"]["title"] == "" and e["payload"]["keywords"] == []
        assert e["display"]["redacted"] == "diary" and "digest" not in e["display"]
    for e in home.export_replay(families=("binding",)):
        if e["payload"]["record_id"] == gid:
            assert e["display"]["redacted"] == "diary" and "digest" not in e["display"]
            assert "title" not in e["display"]
    with pytest.raises(ValueError, match="book"):
        home.record_understanding(gid)
