"""`declare_pending`: a STORED record whose title or summary was never authored is declared pending, the same state a
record formed pending is in (operator rule 2026-11-09: "title + summary must ALWAYS exist for every memory; authored,
never cut, no fallback"; the runtime owner's option, one rule).

The legacy records the runtime's sleep repair finds (abstractruntime 7d2419e): a card titled "World model: <subject>"
in mechanical-card-v2 words and a dream titled "Dream: ...". Before this verb their summaries were refused
(`use_author_world_model` / `use_narrate_dream`) and nothing could make a stored record pending. Every case runs on both
substrate pairs.

MUTATION LIST (scratch copy, each mutant run against this file; all red, the source restored byte-exact):
M1 a declared title keeps the legacy label (not stored None); M2 no marker written; M3 no task queued (the enqueue
hook dropped); M4 the tasks at a non-formation priority; M5 the already_pending short-circuit removed; M6 the
`closed` refusal removed; M7 the `no_task_queue` refusal removed; M8 a protected kind's summary accepted; M9 the
`hash_chained` refusal removed; M10 `revert_digest` restores a reading the declaration made provisional; M11 a
declaration reverted as a reading (`not_revertible` removed); M12 an interest's card left on its old head; M13 a card
other interests share moved anyway; M14 the record's live body task left beside the pending summary; M15 a settled
task's identity reused (no fresh basis: the title owes no live task); M16 no title version written for the title the
declaration takes back; M17 the embedder called for a marker-only declaration; M18 a version 0 row captured for the
`pending` field.
"""

from __future__ import annotations

import hashlib
import warnings
from typing import Any, Dict, List

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import (  # noqa: E402
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    apply_redigestion,
    current_world_models,
    declare_pending,
    world_model_pass,
)
from abstractmemory.memory_tasks import enqueue_dream, task_id_for  # noqa: E402
from abstractmemory.records import resolve_digest_assertion  # noqa: E402
from abstractmemory.sleep_policy import SleepTuning  # noqa: E402
from abstractmemory.understanding import DECLARE_PENDING_METHOD  # noqa: E402
from abstractmemory.world_model import interest_target  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
TUNING = SleepTuning(world_model_evidence_floor=3)
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "artifact", "artifact_id": "authoring-call-1"}]
DECLARER = {"kind": "mechanical", "id": "declare_pending"}


class Embedder:
    """Deterministic unit vectors from the text hash; counts its calls."""

    model = "fake-hash-16"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def embed_texts(self, texts):
        self.calls += 1
        if self.fail:
            raise ConnectionError("embedder endpoint unreachable")
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(16)
            out.append((v / np.linalg.norm(v)).tolist())
        return out


def _open(kind: str, tmp_path, *, task_queue: bool = True) -> MemorySystem:
    emb = Embedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if kind == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        else:
            path = tmp_path / f"memory-{int(task_queue)}.sqlite3"
            store, journal = SQLiteTripleStore(path, embedder=emb), SQLiteJournal(path)
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=task_queue)
    system.emb = emb
    return system


@pytest.fixture(params=["memory", "sqlite"])
def home(request, tmp_path):
    system = _open(request.param, tmp_path)
    system.kind = request.param
    yield system
    system.journal.close()
    system.store.close()


def _form(system, key: str, kind: str = "episode", title: Any = None, digest: str = "", **kw: Any) -> str:
    title = title if title is not None or kw.get("pending") else f"Exchange {key}"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many(
            [MemoryRecordInput(kind=kind, title=title, digest=digest or f"We talked about {key}.", **kw)],
            scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


def _tasks(system, gid: str, kinds=("title.author", "digest.author")) -> Dict[str, Dict[str, Any]]:
    return {t["kind"]: t for t in system.tasks.tasks(kind=tuple(kinds), target_id=gid)}


def _all_tasks(system, gid: str) -> List[Dict[str, Any]]:
    return system.tasks.tasks(target_id=gid)


def _display(system, gid: str) -> Dict[str, Any]:
    return {e["payload"]["record_id"]: e["display"] for e in system.export_replay(families=("binding",))}[gid]


def _drain(system, gid: str, *, title: str = "", summary: str = "") -> Dict[str, Any]:
    """What the runtime's drainer does (abstractruntime identity/authoring.py): per live task, read the packet, then
    `retitle` / `rewrite_digest` with the capability author, the packet's expected version and the task id."""
    out: Dict[str, Any] = {}
    live = {t["kind"]: t for t in system.tasks.tasks(kind=("title.author", "digest.author"), target_id=gid)
            if t["status"] in ("pending", "deferred", "leased")}
    if summary:
        t = live["digest.author"]
        packet = system.task_packet(t["task_id"])
        out["summary"] = system.rewrite_digest(gid, text=summary, author=MODEL, reader=READER, sources=STEP,
                                               cause={"cause": "repair", "pending": "summary"},
                                               expected_version=int(packet["expected_version"]), task_id=t["task_id"])
    if title:
        t = live["title.author"]
        packet = system.task_packet(t["task_id"])
        out["title"] = system.retitle(gid, title=title, author=MODEL, reader=READER, sources=STEP,
                                      cause={"cause": "repair", "pending": "title"},
                                      expected_version=int(packet["expected_version"]), task_id=t["task_id"])
    return out


def _legacy_card(system) -> str:
    """A card formed before 2026-11-09: the pass's "World model: <subject>" label, its mechanical briefing as body."""
    return _form(system, "legacy-card", kind="world_model", title="World model: person:ada",
                 digest="What I know of person:ada: worked with Ada on the archive (3 records).",
                 participants=("person:ada",),
                 attributes={"world_model": True, "target": "person:ada", "revision": 1,
                             "evidence_fingerprint": "fp-old", "known_source_ids": ["ex:a", "ex:b", "ex:c"],
                             "digest_method": "mechanical-card-v2"})


def _legacy_dream(system) -> str:
    return _form(system, "legacy-dream", kind="dream", title="Dream: the noon pool met the garden",
                 digest="Two memory islands lit up together: the noon pool and the garden sensors.",
                 attributes={"signals": [{"kind": "bridge", "fragment": "noon pool / garden sensors"}],
                             "digest_method": "mechanical-dream-v1"})


def _structure(system, gid: str) -> Dict[str, Any]:
    attrs = _row(system, gid).attributes
    return {k: attrs.get(k) for k in ("target", "revision", "evidence_fingerprint", "known_source_ids", "signals",
                                      "participants", "record_kind")}


# --------------------------------------------------------------------------- the legacy card


def test_a_legacy_card_declared_pending_is_authored_through_rewrite_digest_and_retitle(home) -> None:
    card = _legacy_card(home)
    aid = str(_row(home, card).assertion_id)
    structure = _structure(home, card)
    # Before: the summary has no door (the refusal the runtime's drainer logged as memory_refused).
    assert home.rewrite_digest(card, text="x", author=MODEL, reader=READER, sources=STEP, cause="repair",
                               expected_version=0)["reason"] == "use_author_world_model"
    # The legacy card still owes its mechanical words (card.author); the pending summary takes the body over.
    home.enqueue_debt(scopes=SCOPES, dry_run=False)
    [legacy_task] = [t for t in _all_tasks(home, card) if t["kind"] == "card.author"]

    out = home.declare_pending(card, cause="repair", reason="legacy card: World model label, mechanical body")
    assert out["applied"] is True and out["outcome"] == "applied" and out["field"] == "pending"
    assert out["declared"] == ["title", "summary"] and out["already_pending"] == []
    assert out["provisional"] == {"field": "card", "version": 0}
    assert out["superseded"] == [legacy_task["task_id"]] and out["adopted"] == []
    row = _row(home, card)
    attrs = row.attributes
    # The same state as a card formed pending: no title, the marker, the briefing only the provisional body.
    assert attrs["title"] is None
    assert {k: attrs["pending"][k] for k in ("title", "summary", "attempts")} == {
        "title": True, "summary": True, "attempts": 0}
    assert attrs["pending"]["since"] and out["pending"] == attrs["pending"]
    assert row.object == "What I know of person:ada: worked with Ada on the archive (3 records)."
    assert attrs["digest_method"] == "mechanical-card-v2"
    assert _structure(home, card) == structure
    # The same tasks as formation: kind, capability, priority, strength, basis, basis_version.
    tasks = _tasks(home, card)
    assert sorted(tasks) == ["digest.author", "title.author"]
    for fld, kind in (("title", "title.author"), ("summary", "digest.author")):
        t = tasks[kind]
        assert t["task_id"] == task_id_for(kind, card, f"{aid}@pending-{fld}") == out["tasks"][fld]
        assert (t["status"], t["capability"], t["priority"], t["strength"], t["basis_version"]) == (
            "pending", "summaries", 5, 1.0, 0)
        assert t["cause"] == {"cause": "repair", "pending": fld, "declared": True,
                              "reason": "legacy card: World model label, mechanical body"}
    assert sorted(out["enqueued"]) == sorted(t["task_id"] for t in tasks.values())
    assert {t["task_id"]: t["status"] for t in _all_tasks(home, card)}[legacy_task["task_id"]] == "superseded"
    # The title history is whole: version 0 the legacy label (mechanical), version 1 pending (None, the declarer).
    titles = home.versions(card, field="title")
    assert [(v["version"], v["text"]) for v in titles] == [(0, "World model: person:ada"), (1, None)]
    assert titles[0]["author"]["kind"] == "mechanical" and titles[1]["author"] == DECLARER
    assert titles[1]["digest_method"] == DECLARE_PENDING_METHOD and out["title_version"] == 1
    # The declaration is a journal revision event with its provenance.
    [decl] = home.versions(card, field="pending")
    assert decl["version"] == 1 and decl["text"] == "title, summary" and decl["author"] == DECLARER
    assert decl["cause"]["cause"] == "repair" and decl["cause"]["pending"] == ["title", "summary"]
    assert decl["cause"]["tasks"] == out["tasks"] and decl["cause"]["provisional"] == {"field": "card", "version": 0}
    assert decl["cause"]["reason"] == "legacy card: World model label, mechanical body"
    revisions = [e["payload"] for e in home.export_replay(families=("revision",))
                 if e["payload"]["record_id"] == card and e["payload"]["field"] == "pending"]
    assert [r["version_id"] for r in revisions] == [decl["version_id"]]
    # Read time: "being written", never the label.
    assert _display(home, card)["title"] is None and _display(home, card)["pending"]["summary"] is True
    assert home.record_understanding(card)["pending"]["title"] is True
    debt = home.understanding_debt(scopes=SCOPES)["debt"]
    assert debt["title.author"]["world_model"] == 1 and "card.author" not in debt

    # The drainer: summary through the card's own write, then the title; both tasks done, the marker gone.
    done = _drain(home, card, summary="Ada is the archivist I work beside; we rebuilt the index together.")
    assert done["summary"]["applied"] is True and done["summary"]["field"] == "card"
    assert done["summary"]["pending_cleared"] == ["summary"]
    row = _row(home, card)
    assert row.object == "Ada is the archivist I work beside; we rebuilt the index together."
    assert row.attributes["digest_method"] == "authored-card-v1" and row.attributes["pending"]["title"] is True
    done = _drain(home, card, title="Ada, the archivist")
    assert done["title"]["applied"] is True and done["title"]["pending_cleared"] == ["title"]
    row = _row(home, card)
    assert row.attributes["title"] == "Ada, the archivist" and "pending" not in row.attributes
    assert {t["status"] for t in _tasks(home, card).values()} == {"done"}
    assert _structure(home, card) == structure                         # target, revision, evidence untouched
    assert [(v["version"], v["text"]) for v in home.versions(card, field="title")][-1] == (2, "Ada, the archivist")
    # Written: the card keeps its own door again, the briefing never comes back, a declaration is not a reading.
    assert home.rewrite_digest(card, text="Other.", author=MODEL, reader=READER, sources=STEP, cause="repair",
                               expected_version=1)["reason"] == "use_author_world_model"
    assert home.revert_digest(card, 0, expected_version=1)["reason"] == "provisional_summary"
    assert home.revert_digest(card, 1, expected_version=1, field="pending")["reason"] == "not_revertible"
    assert list(current_world_models(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal)) == ["person:ada"]


# --------------------------------------------------------------------------- the legacy dream


def test_a_legacy_dream_declared_pending_is_authored_and_keeps_its_night(home) -> None:
    dream = _legacy_dream(home)
    signals = _row(home, dream).attributes["signals"]
    narrate = enqueue_dream(home, dream, scope=SCOPE, owner_id=OWNER, salience=1.0, salience_high=1.0)
    assert home.rewrite_digest(dream, text="x", author=MODEL, reader=READER, sources=STEP, cause="repair",
                               expected_version=0)["reason"] == "use_narrate_dream"
    out = declare_pending(home, dream, reason="legacy dream")
    assert out["applied"] is True and out["provisional"] == {"field": "digest", "version": 0}
    assert out["superseded"] == []                                      # the narration stays beside
    attrs = _row(home, dream).attributes
    assert attrs["title"] is None and attrs["pending"]["title"] is True and attrs["pending"]["summary"] is True
    assert sorted(_tasks(home, dream)) == ["digest.author", "title.author"]
    done = _drain(home, dream, summary="A night where the noon pool and the garden met.",
                  title="The noon pool beside the garden")
    assert done["summary"]["pending_cleared"] == ["summary"] and done["title"]["pending_cleared"] == ["title"]
    row = _row(home, dream)
    assert row.object == "A night where the noon pool and the garden met."
    assert row.attributes["title"] == "The noon pool beside the garden" and "pending" not in row.attributes
    assert row.attributes["signals"] == signals
    assert {t["status"] for t in _tasks(home, dream).values()} == {"done"}
    assert home.tasks.task(narrate)["status"] == "pending"
    assert home.rewrite_digest(dream, text="x", author=MODEL, reader=READER, sources=STEP, cause="repair",
                               expected_version=1)["reason"] == "use_narrate_dream"
    assert home.revert_digest(dream, 0, expected_version=1)["reason"] == "provisional_summary"


# --------------------------------------------------------------------------- idempotence and identities


def test_a_second_declaration_is_already_pending_and_writes_nothing(home) -> None:
    card = _legacy_card(home)
    first = home.declare_pending(card)
    snap = (dict(_row(home, card).attributes), [t["task_id"] for t in _all_tasks(home, card)],
            len(home.versions(card, field="pending")), len(home.versions(card, field="title")))
    again = home.declare_pending(card)
    assert again["applied"] is False and again["outcome"] == "unchanged" and again["reason"] == "already_pending"
    assert again["already_pending"] == ["title", "summary"] and again["tasks"] == first["tasks"]
    assert (dict(_row(home, card).attributes), [t["task_id"] for t in _all_tasks(home, card)],
            len(home.versions(card, field="pending")), len(home.versions(card, field="title"))) == snap
    # A partial overlap declares only what is new, and the marker keeps when it started.
    ep = _form(home, "ep-partial", attributes={"digest_method": "mechanical-v2"})
    one = home.declare_pending(ep, fields=("summary",))
    since = _row(home, ep).attributes["pending"]["since"]
    two = home.declare_pending(ep, fields=["title", "summary"])
    assert two["declared"] == ["title"] and two["already_pending"] == ["summary"]
    assert sorted(two["tasks"]) == ["title"] and one["tasks"]["summary"] == _tasks(home, ep)["digest.author"]["task_id"]
    marker = _row(home, ep).attributes["pending"]
    assert marker["title"] is True and marker["summary"] is True and marker["since"] == since
    assert [v["text"] for v in home.versions(ep, field="pending")] == ["summary", "title"]


def test_a_live_task_queued_without_the_marker_is_adopted(home) -> None:
    # What the runtime's sleep scan queued before this verb existed (7d2419e): formation's basis, no marker.
    card = _legacy_card(home)
    aid = str(_row(home, card).assertion_id)
    queued = home.tasks.enqueue("digest.author", card, scope=SCOPE, owner_id=OWNER, assertion_id=aid,
                                basis=f"{aid}@pending-summary", basis_version=0, strength=1.0,
                                cause={"cause": "legacy_missing", "pending": "summary"}, priority=5)
    out = home.declare_pending(card)
    assert out["adopted"] == [queued["task_id"]] and out["tasks"]["summary"] == queued["task_id"]
    assert len([t for t in _all_tasks(home, card) if t["kind"] == "digest.author"]) == 1
    assert _row(home, card).attributes["pending"]["summary"] is True


def test_a_title_authored_once_and_declared_again_owes_a_fresh_task(home) -> None:
    gid = _form(home, "pending-once", title=None, pending=("title",))
    aid = str(_row(home, gid).assertion_id)
    _drain(home, gid, title="A first authored title")
    assert _tasks(home, gid)["title.author"]["status"] == "done"
    out = home.declare_pending(gid, fields=("title",), reason="the title was cut")
    assert out["applied"] is True
    fresh = out["tasks"]["title"]
    assert fresh == task_id_for("title.author", gid, f"{aid}@pending-title@2") and out["enqueued"] == [fresh]
    assert home.tasks.task(fresh)["status"] == "pending" and _row(home, gid).attributes["title"] is None
    assert [v["text"] for v in home.versions(gid, field="title")] == [None, "A first authored title", None]
    done = _drain(home, gid, title="A complete authored title")
    assert done["title"]["pending_cleared"] == ["title"] and home.tasks.task(fresh)["status"] == "done"
    assert "pending" not in _row(home, gid).attributes


def test_a_declared_summary_never_restores_the_reading_it_made_provisional(home) -> None:
    ep = _form(home, "ep-rewritten", digest="Mechanical words of the exchange.",
               attributes={"digest_method": "mechanical-v2"})
    assert [t["kind"] for t in _all_tasks(home, ep)] == ["digest.rewrite"]
    home.rewrite_digest(ep, text="Second mechanical words.", author={"kind": "mechanical", "id": "floor"},
                        cause="backfill", expected_version=0, digest_method="mechanical-v2")
    out = home.declare_pending(ep, fields=("summary",))
    assert out["provisional"] == {"field": "digest", "version": 1} and "title_version" not in out
    assert {t["kind"]: t["status"] for t in _all_tasks(home, ep)}["digest.rewrite"] == "superseded"
    assert _row(home, ep).attributes["title"] == "Exchange ep-rewritten"            # the title was not declared
    _drain(home, ep, summary="We worked out what the crisis numbers mean.")
    assert home.revert_digest(ep, 1, expected_version=2)["reason"] == "provisional_summary"
    assert home.versions(ep, field="pending")[0]["version"] == 1                     # no version 0 for a declaration
    assert len(home.versions(ep, field="pending")) == 1


# --------------------------------------------------------------------------- the vector


def test_only_a_declared_title_moves_the_vector_and_a_failed_embedder_writes_nothing(home) -> None:
    ep = _form(home, "ep-vector", attributes={"digest_method": "mechanical-v2"})
    vec = home.store.stored_vector(str(_row(home, ep).assertion_id))
    home.emb.fail = True
    calls = home.emb.calls
    refused = home.declare_pending(ep, fields=("title", "summary"))
    assert refused["reason"] == "embedder_unavailable"
    assert "pending" not in _row(home, ep).attributes and _tasks(home, ep) == {}
    assert home.versions(ep, field="pending") == [] and home.versions(ep, field="title") == []
    # A summary-only declaration changes no text: no embedder call, the vector stands.
    calls = home.emb.calls
    out = home.declare_pending(ep, fields=("summary",))
    assert out["applied"] is True and out["vector_rewritten"] is False and home.emb.calls == calls
    assert home.store.stored_vector(str(_row(home, ep).assertion_id)) == vec
    home.emb.fail = False
    out = home.declare_pending(ep, fields=("title",))
    assert out["applied"] is True and out["vector_rewritten"] is True
    assert home.store.stored_vector(str(_row(home, ep).assertion_id)) != vec


# --------------------------------------------------------------------------- refusals


def test_refusals_write_nothing(home, tmp_path) -> None:
    with pytest.raises(ValueError, match="subset"):
        home.declare_pending("ex:none", fields=("body",))
    with pytest.raises(ValueError, match="subset"):
        home.declare_pending("ex:none", fields=())
    with pytest.raises(ValueError, match="not a string"):
        home.declare_pending("ex:none", fields="title")
    with pytest.raises(ValueError, match="cause"):
        home.declare_pending("ex:none", cause="whim")
    assert home.declare_pending("ex:none")["reason"] == "unknown_record"

    # The entity's own act: his words are the body, so its summary is never pending; its title may be.
    lesson = _form(home, "a-realization", kind="realization", title="untitled realization [a1b2c3]",
                   digest="I keep my word when it costs me.")
    refused = home.declare_pending(lesson)
    assert refused["reason"] == "protected_kind" and "pending" not in _row(home, lesson).attributes
    assert _tasks(home, lesson) == {}
    assert home.declare_pending(lesson, fields=("title",))["applied"] is True

    # An owner-direct diary entry: its entry_hash attests the title.
    chained = _form(home, "chained", kind="diary", title="A chained entry", digest="Owner-direct words.",
                    attributes={"diary_type": "note", "entry_hash": "0" * 64}, provenance={"source": "owner-direct"})
    assert home.declare_pending(chained, fields=("title",))["reason"] == "hash_chained"
    assert _row(home, chained).attributes["title"] == "A chained entry" and _tasks(home, chained) == {}

    # A closed record: its replacement is the current one.
    ep = _form(home, "ep-closed", attributes={"digest_method": "mechanical-v2"})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        replaced = apply_redigestion(home, [{"record_id": ep, "digest": "A replacement record's words."}],
                                     actor="operator")
    closed = home.declare_pending(ep)
    assert closed["reason"] == "closed" and closed["replaced_by"] == [replaced["outcomes"][0]["new_record_id"]]
    assert "pending" not in _row(home, ep).attributes and _tasks(home, ep) == {}


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_a_home_without_a_task_queue_is_refused(kind, tmp_path) -> None:
    system = _open(kind, tmp_path, task_queue=False)
    try:
        card = _legacy_card(system)
        before = dict(_row(system, card).attributes)
        out = declare_pending(system, card)
        assert out["applied"] is False and out["reason"] == "no_task_queue"
        assert dict(_row(system, card).attributes) == before
        assert system.journal.versions(record_id=card) == []
    finally:
        system.journal.close()
        system.store.close()


# --------------------------------------------------------------------------- an interest's card


def _interest(system, key: str, title: str) -> str:
    return _form(system, key, kind="interest", title=title, digest=f"I keep coming back to {key}.")


def test_an_interest_declared_pending_takes_its_card_to_its_id_key_and_back(home) -> None:
    gid = _interest(home, "pool", "untitled interest [0f3a9c]")
    world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    head = interest_target(gid, "untitled interest [0f3a9c]")
    [card] = [c for k, c in current_world_models(home.store, scope=SCOPE, owner_id=OWNER,
                                                 journal=home.journal).items() if k == head]
    out = home.declare_pending(gid, fields=("title",), reason="placeholder title")
    assert out["card_rekey"]["applied"] is True and out["card_rekey"]["new_key"] == f"topic:{gid}"
    cards = current_world_models(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal)
    assert list(cards) == [f"topic:{gid}"] and cards[f"topic:{gid}"].subject == card.subject
    world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)              # no second card forms
    assert list(current_world_models(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal)) == [
        f"topic:{gid}"]
    done = _drain(home, gid, title="Why the connection pool saturates at noon")
    assert done["title"]["card_rekey"]["applied"] is True
    cards = current_world_models(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal)
    assert list(cards) == [interest_target(gid, "Why the connection pool saturates at noon")]
    assert next(iter(cards.values())).subject == card.subject


def test_a_card_other_interests_share_stays_on_its_key(home) -> None:
    one = _interest(home, "pool-a", "The connection pool — why it saturates")
    _interest(home, "pool-b", "The connection pool — what batching changed")
    world_model_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    head = interest_target(one, "The connection pool — why it saturates")
    assert head in current_world_models(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal)
    out = home.declare_pending(one, fields=("title",))
    assert out["applied"] is True and out["card_rekey"]["reason"] == "shared_card"
    assert head in current_world_models(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal)
