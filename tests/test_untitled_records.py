"""A title and a summary are mandatory; the one exception is an explicit, transient PENDING state with its task.

Operator rulings 2026-11-09 (root backlog 1146): "the title + summary must ALWAYS exist for any memory. those are
mandatory metadata of all memories", and "no fallback; log the failure to untracked/ and fix it at the source". A
record whose title (or summary) failed at formation is formed with `pending=("title",)` (and/or "summary"): its
title is stored None, `attributes.pending = {title, summary, since, attempts}`, and the same `remember_many` call
queues the authoring task (`title.author` / `digest.author`, capability `summaries`, formation priority). Without a
task queue, or without the declaration, a missing title is refused. `retitle` / `rewrite_digest` complete the task
and clear the marker.

Pinned here, on both substrate pairs (in-memory, and SQLite store + journal sharing one file):
- formation: the marker and the task, for any kind and every diary type; refusals (undeclared null title, no task
  queue, a title given while declared pending, an unknown field, a pending summary on a protected kind, a forged
  host marker);
- reads serve title None (never "", an "s p o" preview or the body) and the marker: recall handles, replay display
  blocks (diary too), `record_understanding`, `recent_records`, `explain_recall`, identity-card briefs; the canonical
  text (FTS, keyword index, vector) is the body alone; `short_title(None)` is None;
- the queue: formation priority ahead of `digest.rewrite`, debt counted and covered, each claim mirrored into the
  marker's `attempts`, the packet (a diary target redacted);
- completion: `retitle` (named task or not) and `rewrite_digest` complete the tasks and clear the marker; a revert to
  a null title or to the provisional digest is refused;
- the world-model key of an untitled interest is `topic:<its graph id>`, re-keyed to the title's head when it lands;
  the miner lets an untitled interest own no theme; a chained diary entry verifies; the dedup pass adds no token.

MUTATION LIST (each applied to a scratch COPY of src/, this file run against it with PYTHONPATH, red confirmed):
- P1 the undeclared-null-title check dropped -> test_a_null_title_must_be_declared_pending;
- P2 remember_many forms pending records without a task queue -> test_pending_needs_a_task_queue;
- P3 the formation task not enqueued -> test_pending_title_forms_with_its_task;
- P4 FORMATION_PRIORITY 30 (behind digest.rewrite) -> test_pending_tasks_run_first;
- P5 the marker not cleared by a write -> test_retitle_completes_the_task_and_clears_the_marker;
- P6 on_rewrite ignores `completes` -> test_retitle_completes_the_task_and_clears_the_marker;
- P7 claims not mirrored into `attempts` -> test_each_claim_is_an_attempt_on_the_marker;
- P8 the display block drops the marker -> test_read_surfaces_serve_none_and_the_marker;
- P9 the shelf handle falls back to the "s p o" preview -> test_recall_serves_no_title_and_indexes_the_body_alone;
- P10 the world-model key reads the digest -> test_untitled_interest_keys_its_card_on_its_id_until_its_title_lands;
- P11 no re-key when the title lands -> test_untitled_interest_keys_its_card_on_its_id_until_its_title_lands;
- P12 a revert to a null title allowed -> test_a_revert_never_removes_a_title;
- P13 debt ignores the pending kinds -> test_debt_counts_the_pending_kinds;
- P14 the dedup pass tokenizes str(None) -> test_dedup_adds_no_none_token;
- P15 a revert to the provisional digest allowed -> test_a_pending_summary_is_completed_by_rewrite_digest.
"""

from __future__ import annotations

import hashlib
import warnings
from typing import Any

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import (  # noqa: E402
    PENDING_FIELDS,
    PENDING_TASK_KINDS,
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    Stimulus,
    current_world_models,
    mine_candidates_pass,
    verify_diary_chain,
    wake_cue_dedup_pass,
    world_model_pass,
)
from abstractmemory.canonical_text import canonical_text, short_title  # noqa: E402
from abstractmemory.diary import diary_entry_hash  # noqa: E402
from abstractmemory.memory_tasks import FORMATION_PRIORITY  # noqa: E402
from abstractmemory.records import DIARY_TYPES, resolve_digest_assertion  # noqa: E402
from abstractmemory.sleep_policy import SleepTuning  # noqa: E402
from abstractmemory.store import TripleQuery  # noqa: E402
from abstractmemory.world_model import interest_target  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "step", "run_id": "run-pending-1", "seq": 3}]
BODY = ("Decentralized clinical trials and health equity — how removing the site visit could reach the patients "
        "the trials keep missing, and what the quorvanth registry shows about it.")


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


def _open(kind: str, tmp_path, *, task_queue: bool = True):
    emb = Embedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if kind == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        else:
            path = tmp_path / "memory.sqlite3"
            store, journal = SQLiteTripleStore(path, embedder=emb), SQLiteJournal(path)
        system = MemorySystem(store=store, journal=journal, embedder=emb, task_queue=task_queue)
    system.kind = kind
    return system


@pytest.fixture(params=["memory", "sqlite"])
def home(request, tmp_path):
    system = _open(request.param, tmp_path)
    yield system
    system.journal.close()
    system.store.close()


def _form(system, key: str, kind: str, title: Any, digest: str = BODY, **kw: Any) -> str:
    if kind.startswith("diary:"):
        kw.setdefault("attributes", {"diary_type": kind[6:], "entry_id": f"book-{key}"})
        kw.setdefault("provenance", {"source": "diary-projection"})
        kind = "diary"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many([MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)],
                                     scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _pending(system, key: str, kind: str, **kw: Any) -> str:
    kw.setdefault("pending", ("title",))
    return _form(system, key, kind, kw.pop("title", None), **kw)


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


def _tasks(system, gid: str, kind: str = "title.author", status=None):
    return system.tasks.tasks(kind=(kind,), target_id=gid, status=status)


KINDS = ["interest", "lesson", "realization", "observation", "episode", "claim"] + \
    [f"diary:{t}" for t in sorted(DIARY_TYPES)]


# --------------------------------------------------------------------------- formation


def test_the_contract_constants() -> None:
    assert PENDING_FIELDS == {"title", "summary"}
    assert dict(PENDING_TASK_KINDS) == {"title": "title.author", "summary": "digest.author"}


@pytest.mark.parametrize("given", [None, "", "  \n "])
@pytest.mark.parametrize("kind", KINDS)
def test_pending_title_forms_with_its_task(home, kind, given) -> None:
    gid = _pending(home, f"p-{kind}-{given!r}", kind, title=given)
    row = _row(home, gid)
    assert "title" in row.attributes and row.attributes["title"] is None
    assert row.attributes["pending"] == {"title": True, "summary": False, "since": row.observed_at, "attempts": 0}
    [task] = _tasks(home, gid)
    assert task["status"] == "pending" and task["capability"] == "summaries"
    assert task["priority"] == FORMATION_PRIORITY and task["strength"] == 1.0
    assert task["cause"] == {"cause": "formation", "pending": "title"}
    assert _tasks(home, gid, "digest.author") == []


@pytest.mark.parametrize("kind", ["interest", "episode", "diary:note"])
def test_a_null_title_must_be_declared_pending(kind) -> None:
    for given in (None, "", "   "):
        with pytest.raises(ValueError, match="title must be a non-empty string"):
            MemoryRecordInput(kind=kind.split(":")[0], title=given, digest="Some words.",
                              attributes={"diary_type": "note"} if kind.startswith("diary") else {})


def test_pending_declaration_is_checked() -> None:
    with pytest.raises(ValueError, match="but a title was given"):
        MemoryRecordInput(kind="lesson", title="A lesson", digest="x", pending=("title",))
    with pytest.raises(ValueError, match="unknown fields"):
        MemoryRecordInput(kind="lesson", title=None, digest="x", pending=("title", "keywords"))
    with pytest.raises(ValueError, match="never authored by a task"):
        MemoryRecordInput(kind="interest", title="An interest", digest="x", pending=("summary",))
    assert MemoryRecordInput(kind="lesson", title=" ", digest="x", pending=("Title", "title")).pending == ("title",)


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_pending_needs_a_task_queue(tmp_path, backend) -> None:
    system = _open(backend, tmp_path, task_queue=False)
    try:
        with pytest.raises(ValueError, match="needs its authoring task"):
            _pending(system, "no-queue", "lesson")
        assert system.store.query(TripleQuery(limit=0)) == []                  # nothing written
        assert _form(system, "titled", "lesson", "A titled lesson")            # a titled record still forms
    finally:
        system.journal.close()
        system.store.close()


def test_a_host_cannot_forge_the_marker(home) -> None:
    gid = _form(home, "forged", "lesson", "A titled lesson",
                attributes={"pending": {"title": True, "summary": False, "since": "x", "attempts": 0}})
    assert "pending" not in _row(home, gid).attributes and _tasks(home, gid) == []


def test_short_title_of_no_title_is_none() -> None:
    assert short_title(None) is None and short_title("") is None and short_title("  ") is None
    assert short_title("A title") == "A title"


# --------------------------------------------------------------------------- reads


def test_recall_serves_no_title_and_indexes_the_body_alone(home) -> None:
    gid = _pending(home, "p-recall", "lesson", keywords=("trials",))
    _form(home, "other", "episode", "exchange: gardens", "An unrelated exchange about gardens.")
    row = _row(home, gid)
    assert canonical_text(row) == f"{BODY}\nkeywords: trials"
    if home.kind == "sqlite":
        assert [a.subject for a in home.store.query_keywords(["quorvanth"], scope=SCOPE, owner_id=OWNER)] == [gid]
        assert home.store.query_keywords(["none"], scope=SCOPE, owner_id=OWNER) == []
    recall = home.reconstruct(Stimulus(cue_text="quorvanth registry"), scopes=[(SCOPE, OWNER)], journal=False)
    [handle] = [h for h in recall.handles if h.record_id in {gid, row.assertion_id}] or [None]
    assert handle is not None and handle.title is None and handle.digest == BODY


def test_read_surfaces_serve_none_and_the_marker(home) -> None:
    gid = _pending(home, "p-read", "interest")
    marker = _row(home, gid).attributes["pending"]
    understood = home.record_understanding(gid)
    assert understood["title"] is None and understood["pending"] == marker and understood["digest"] == BODY
    blocks = {e["payload"]["record_id"]: e["display"] for e in home.export_replay(families=("binding",))}
    assert blocks[gid]["title"] is None and blocks[gid]["pending"] == marker
    diary = _pending(home, "p-diary", "diary:question")
    assert blocks.get(diary) is None
    dblock = {e["payload"]["record_id"]: e["display"] for e in home.export_replay(families=("binding",))}[diary]
    assert dblock["redacted"] == "diary" and dblock["pending"]["title"] is True and "title" not in dblock
    [r] = [r for r in home.recent_records(scopes=[(SCOPE, OWNER)], since="2000-01-01T00:00:00Z")["records"]
           if r["graph_id"] == gid]
    assert r["title"] is None
    assert home.explain_recall(gid)["origin"]["title"] is None


def test_identity_card_briefs_serve_none(home) -> None:
    interest = _pending(home, "p-card-i", "interest")
    lesson = _pending(home, "p-card-l", "lesson", digest="Check a country's indicators before citing them.")
    card = home.entity_card(scope_pairs=[(SCOPE, OWNER)], owner_id=OWNER)
    [i] = [b for b in card["discoveries"]["interests"] if b["record_id"] == interest]
    [lb] = [b for b in card["lessons"]["lessons"] if b["record_id"] == lesson]
    assert i["title"] is None and i["statement"] == BODY and lb["title"] is None
    firsts = {m["what"]: m for m in card["key_moments"]["moments"] if m["type"] == "first"}
    assert firsts["first_interest"]["title"] is None


# --------------------------------------------------------------------------- the queue


def test_pending_tasks_run_first(home) -> None:
    mech = _form(home, "mech", "episode", "exchange: x", "User: x. Nerin: y.",
                 attributes={"digest_method": "mechanical-v2"})
    gid = _pending(home, "p-first", "observation")
    window = home.tasks.select_for_window(10_000.0, window="turn")
    order = [(t["kind"], t["target_id"]) for t in window["tasks"]]
    assert order.index(("title.author", gid)) < order.index(("digest.rewrite", mech))


def test_debt_counts_the_pending_kinds(home) -> None:
    gid = _pending(home, "p-debt", "interest")
    both = _form(home, "p-both", "episode", None, "User: what? Nerin: this.", pending=("title", "summary"),
                 attributes={"digest_method": "mechanical-v2"})
    debt = home.understanding_debt(scopes=[(SCOPE, OWNER)])
    assert debt["debt"]["title.author"] == {"interest": 1, "episode": 1}
    assert debt["debt"]["digest.author"] == {"episode": 1}
    assert "digest.rewrite" not in debt["debt"]               # the pending summary's task owns the body
    assert debt["unqueued"] == 0 and debt["by_capability"]["summaries"] == 3
    assert home.enqueue_debt(scopes=[(SCOPE, OWNER)], dry_run=True)["would_enqueue"] == 0
    assert _tasks(home, both, "digest.rewrite") == [] and len(_tasks(home, gid)) == 1


def test_each_claim_is_an_attempt_on_the_marker(home) -> None:
    gid = _pending(home, "p-claim", "lesson")
    [task] = _tasks(home, gid)
    home.tasks.claim([task["task_id"]], holder="reader-1", lease_seconds=1)
    assert _row(home, gid).attributes["pending"]["attempts"] == 1
    home.tasks.release(task["task_id"], holder="reader-1", outcome="retry", reason="model timeout")
    home.tasks.claim([task["task_id"]], holder="reader-1")
    marker = _row(home, gid).attributes["pending"]
    assert marker["attempts"] == 2 and marker["title"] is True
    assert _row(home, gid).object == BODY and canonical_text(_row(home, gid)) == BODY


def test_the_packet_of_a_pending_title(home) -> None:
    gid = _pending(home, "p-packet", "interest")
    [task] = _tasks(home, gid)
    packet = home.task_packet(task["task_id"])
    assert packet["expected_version"] == 0 and packet["record"]["pending"]["title"] is True
    assert packet["record"]["title"] is None and packet["record"]["digest"] == BODY
    diary = _pending(home, "p-packet-d", "diary:note")
    [dtask] = _tasks(home, diary)
    dpacket = home.task_packet(dtask["task_id"])
    assert dpacket["record"]["redacted"] == "diary" and dpacket["record"]["digest"] == ""
    assert dpacket["record"]["entry_id"] == "book-p-packet-d" and dpacket["record"]["pending"]["title"] is True


# --------------------------------------------------------------------------- completion


def test_retitle_completes_the_task_and_clears_the_marker(home) -> None:
    gid = _pending(home, "p-retitle", "realization")
    [task] = _tasks(home, gid)
    new = "Realization: numbers become people when the account is first-person"
    out = home.retitle(gid, title=new, author=MODEL, reader=READER, sources=STEP, cause="formation",
                       expected_version=0, task_id=task["task_id"])
    assert out["applied"] is True and out["pending_cleared"] == ["title"]
    row = _row(home, gid)
    assert row.attributes["title"] == new and "pending" not in row.attributes and row.object == BODY
    assert canonical_text(row).splitlines()[0] == new
    assert home.tasks.task(task["task_id"])["status"] == "done"
    rows = home.versions(gid, field="title")
    assert [(r["version"], r["text"], r["title"]) for r in rows] == [(0, None, None), (1, new, new)]
    assert "pending" not in home.record_understanding(gid)

    # A retitle that names no task (the operator's) completes the live task all the same.
    other = _pending(home, "p-retitle-2", "lesson")
    out2 = home.retitle(other, title="Lesson: cite indicators only after checking them", author={"kind": "operator",
                        "id": "laurent"}, cause="operator", expected_version=0)
    assert out2["pending_cleared"] == ["title"]
    assert [t["status"] for t in _tasks(home, other)] == ["done"]


def test_a_pending_summary_is_completed_by_rewrite_digest(home) -> None:
    gid = _form(home, "p-sum", "episode", None, "User: what? Nerin: this, verbatim.", pending=("title", "summary"),
                attributes={"digest_method": "mechanical-v2"})
    [st] = _tasks(home, gid, "digest.author")
    assert home.retitle(gid, title="exchange: what this was", author=MODEL, reader=READER, sources=STEP,
                        cause="formation", expected_version=0)["pending_cleared"] == ["title"]
    assert _row(home, gid).attributes["pending"]["summary"] is True
    assert _row(home, gid).attributes["pending"]["title"] is False
    out = home.rewrite_digest(gid, text="We spoke about what this was.", author=MODEL, reader=READER, sources=STEP,
                              cause="formation", expected_version=0, task_id=st["task_id"])
    assert out["applied"] is True and out["pending_cleared"] == ["summary"]
    assert "pending" not in _row(home, gid).attributes
    assert home.tasks.task(st["task_id"])["status"] == "done"
    assert home.versions(gid)[0]["cause"]["pending_summary"] is True
    back = home.revert_digest(gid, 0, expected_version=1)       # the provisional words are never restored
    assert back["applied"] is False and back["reason"] == "provisional_summary"
    assert _row(home, gid).object == "We spoke about what this was."


def test_a_revert_never_removes_a_title(home) -> None:
    gid = _pending(home, "p-revert", "observation")
    home.retitle(gid, title="Observation: the registry undercounts rural sites", author=MODEL, reader=READER,
                 sources=STEP, cause="formation", expected_version=0)
    out = home.revert_digest(gid, 0, field="title", expected_version=1)
    assert out["applied"] is False and out["reason"] == "null_title"
    assert _row(home, gid).attributes["title"] == "Observation: the registry undercounts rural sites"


# --------------------------------------------------------------------------- world model, miner


def test_interest_target_keys() -> None:
    assert interest_target("ex:interest-abc", None) == "topic:ex:interest-abc"
    assert interest_target("ex:interest-abc", "  ") == "topic:ex:interest-abc"
    assert interest_target("ex:interest-abc", "interest: Tidal energy — the coast") == "topic:tidal energy"
    assert interest_target("ex:interest-abc", "Ab") == ""


def test_untitled_interest_keys_its_card_on_its_id_until_its_title_lands(home) -> None:
    gid = _pending(home, "p-wm", "interest")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out = world_model_pass(home, scopes=[(SCOPE, OWNER)], owner_id=OWNER, tuning=SleepTuning())
    targets = {f["target"]: f["card_id"] for f in out["formed"]}
    assert set(targets) == {f"topic:{gid}"}                     # never "topic:decentralized clinical trials..."
    card_id = targets[f"topic:{gid}"]
    landed = home.retitle(gid, title="interest: Tidal energy — how the tides could power the coast", author=MODEL,
                          reader=READER, sources=STEP, cause="formation", expected_version=0)
    assert landed["card_rekey"]["applied"] is True
    assert landed["card_rekey"]["old_key"] == f"topic:{gid}" and landed["card_rekey"]["new_key"] == "topic:tidal energy"
    cards = current_world_models(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal)
    assert set(cards) == {"topic:tidal energy"} and cards["topic:tidal energy"].subject == card_id
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        again = world_model_pass(home, scopes=[(SCOPE, OWNER)], owner_id=OWNER, tuning=SleepTuning())
    assert again["formed"] == []                                # no second card


def test_untitled_interest_owns_no_theme(home) -> None:
    _pending(home, "p-miner", "interest", digest="tidal energy — how the tides could power the coast")
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _form(home, f"m-i{i}", "episode", f"Reading about tidal energy, day {i}", f"Tidal energy, day {i}.",
              keywords=("tidal energy",), provenance={"session_id": session})
    result = mine_candidates_pass(home, scopes=[(SCOPE, OWNER)], owner_id=OWNER)
    offers = [c for c in result["created"] if c["proposed_kind"] == "interest"]
    assert [c["title"] for c in offers] == ["Interest candidate: tidal energy"]
    assert not any("standing interest" in s.get("reason", "") for s in result["skipped"])


# --------------------------------------------------------------------------- diary chain, dedup


def test_a_pending_chained_diary_entry_verifies(home) -> None:
    gid = _form(home, "chain-1", "diary", None, "Owner-direct words, attested.", pending=("title",),
                attributes={"diary_type": "note", "prev_entry_hash": ""}, provenance={"source": "owner-direct"})
    row = _row(home, gid)
    assert row.attributes["title"] is None
    assert row.attributes["entry_hash"] == diary_entry_hash("", "Owner-direct words, attested.", row.observed_at)
    assert verify_diary_chain(home.store, scope=SCOPE, owner_id=OWNER)["intact"] is True


def test_dedup_adds_no_none_token(home) -> None:
    # Pairwise Jaccard 4/6 = 0.67 under a 0.70 floor: no cluster. A "None" token in every member would make it
    # 5/7 = 0.71 and merge three distinct observations.
    for i, tail in enumerate(("foxtrot", "golfing", "hotelier")):
        _pending(home, f"dd-{i}", "observation", digest=f"alpha bravo charlie delta {tail}")
    report = wake_cue_dedup_pass(home, scope=SCOPE, owner_id=OWNER, actor="operator", kind="observation",
                                 jaccard_floor=0.70, min_cluster=3, report_only=True)
    assert report["cluster_count"] == 0
