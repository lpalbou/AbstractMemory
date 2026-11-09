"""Memory's own passes form their records PENDING their authored title and summary (operator rulings 2026-11-09:
"the title + summary must ALWAYS exist for any memory. those are mandatory metadata of all memories"; no fallback,
never a mechanical title or digest presented as the understanding).

Every formation site memory owns, and what it forms (each on both substrate pairs):
- `world_model_pass` (sleep and per-turn cadence): a card with `pending=("title", "summary")`, its evidence briefing
  (mechanical-card-v2, or the carried authored lead + "Since then") the provisional body only; an AUTHORED title
  (one with its `title_provenance`) carries to the next revision (`pending=("summary",)`), the legacy
  "World model: <subject>" label never does; the prior revision's live tasks are superseded. Its structured fields
  (target, fingerprint, sources, revision) are the pass's as before; the card key never depends on the title.
- `author_world_model` in place: the authored text completes a pending summary (`digest.author` done);
  `in_place=False`: an authored summary, the prior's authored title or a pending one.
- `alias_world_model`: carries what is authored, the rest forms pending.
- `dream_pass`: a dream with `pending=("title", "summary")`; its narration task stays.
- `mine_candidates_pass`, `consolidation_pass`, `wake_cue_dedup_pass`: their offers / day summary pending; the
  dedup pass still recognizes its own summary once its authored summary replaced the mechanical label.
- the drainer's seam: `rewrite_digest` completes a pending card (through the card's own write) or dream summary,
  `retitle` its title; a summary no longer pending keeps its own door; the provisional body is never restored.
- a home without a task queue is refused by each pass before it writes anything; report_only reads still run.

MUTATION LIST (scratch copy, each mutant run against this file; all red, the source restored byte-exact):
M1 the card title back to "World model: <subject>" with no pending; M2 a card's summary not pending; M3 the dream
title back to "Dream: …" with no pending; M4 rewrite_digest's card route removed; M5 rewrite_digest's dream route
removed; M6 `_clear_pending` blind to field "card"; M7 no title carried to the next revision; M8 a title carried
without its provenance (the legacy label carries); M9 the prior revision's tasks not superseded; M10 a pending card
still counted as card.author debt; M11 `require_task_queue` a no-op; M12 the miner's offer stores its label as
title; M13 the consolidation candidate stores "Consolidated: …"; M14 the dedup pass blind to its authored summary;
M15 a card reverted to its provisional body; M16 `author_world_model(in_place=False)` titles "World model: …";
M17 `alias_world_model` keeps the legacy title; M18 the provisional body accepted as an authored card text;
M19 apply_redigestion drops the pending title (the entry refused).
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
    alias_world_model,
    author_world_model,
    consolidation_pass,
    current_world_models,
    dream_pass,
    mine_candidates_pass,
    sleep_pass,
    wake_cue_dedup_pass,
    world_model_pass,
    world_model_update,
)
from abstractmemory.records import resolve_digest_assertion  # noqa: E402
from abstractmemory.sleep_policy import SleepTuning  # noqa: E402
from abstractmemory.store import TripleQuery  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
TUNING = SleepTuning(world_model_evidence_floor=3)
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "artifact", "artifact_id": "authoring-call-1"}]


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


def _open(kind: str, tmp_path, *, task_queue: bool = True) -> MemorySystem:
    emb = Embedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if kind == "memory":
            store, journal = InMemoryTripleStore(embedder=emb), InMemoryJournal()
        else:
            path = tmp_path / f"memory-{int(task_queue)}.sqlite3"
            store, journal = SQLiteTripleStore(path, embedder=emb), SQLiteJournal(path)
        return MemorySystem(store=store, journal=journal, embedder=emb, task_queue=task_queue)


@pytest.fixture(params=["memory", "sqlite"])
def home(request, tmp_path):
    system = _open(request.param, tmp_path)
    system.kind = request.param
    yield system
    system.journal.close()
    system.store.close()


def _form(system, key: str, kind: str = "episode", title: Any = None, digest: str = "", **kw: Any) -> str:
    title = title if title is not None else f"Exchange {key}"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many(
            [MemoryRecordInput(kind=kind, title=title, digest=digest or f"We talked about {key}.", **kw)],
            scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


def _tasks(system, gid: str, kinds=("title.author", "digest.author", "card.author")) -> Dict[str, Dict[str, Any]]:
    return {t["kind"]: t for t in system.tasks.tasks(kind=tuple(kinds), target_id=gid)}


def _display(system, gid: str) -> Dict[str, Any]:
    return {e["payload"]["record_id"]: e["display"] for e in system.export_replay(families=("binding",))}[gid]


def _ada(system, n: int = 3, start: int = 0) -> None:
    for i in range(start, start + n):
        _form(system, f"ada-{i}", title=f"Archive day {i} with Ada", digest=f"Worked with Ada on the archive, day {i}.",
              participants=("person:ada", OWNER))


def _card(system) -> str:
    out = world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    [verdict] = [v for v in out["formed"] if v["target"] == "person:ada"]
    return verdict["card_id"]


def _drain(system, gid: str, *, title: str = "", summary: str = "") -> Dict[str, Any]:
    """What the runtime's drainer does (abstractruntime identity/authoring.py): per task, read the packet, then
    `retitle` / `rewrite_digest` with the capability author, the packet's expected version and the task id."""
    out: Dict[str, Any] = {}
    tasks = _tasks(system, gid, ("title.author", "digest.author"))
    if summary:
        t = tasks["digest.author"]
        packet = system.task_packet(t["task_id"])
        out["summary"] = system.rewrite_digest(gid, text=summary, author=MODEL, reader=READER, sources=STEP,
                                               cause={"cause": "formation", "pending": "summary"},
                                               expected_version=int(packet["expected_version"]), task_id=t["task_id"])
    if title:
        t = tasks["title.author"]
        packet = system.task_packet(t["task_id"])
        out["title"] = system.retitle(gid, title=title, author=MODEL, reader=READER, sources=STEP,
                                      cause={"cause": "formation", "pending": "title"},
                                      expected_version=int(packet["expected_version"]), task_id=t["task_id"])
    return out


def _dream(system) -> str:
    _form(system, "s-1", digest="The connection pool saturated at noon.", keywords=("pool", "saturation", "noon"))
    _form(system, "s-3", digest="Planted the garden sensors at noon.", keywords=("garden", "sensors", "noon"))
    _form(system, "s-2", kind="lesson", title="Batching fixed the pool", digest="Batching the noon cron fixed it.",
          keywords=("pool", "batching"))
    night = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert night["dream_record_id"], night["skipped_reason"]
    return night["dream_record_id"]


def _record_count(system) -> int:
    return sum(1 for a in system.store.query(TripleQuery(limit=0)) if (a.attributes or {}).get("record_kind"))


# --------------------------------------------------------------------------- world_model_pass


def test_a_card_forms_pending_with_its_tasks_and_its_structure_intact(home) -> None:
    _ada(home)
    card = _card(home)
    row = _row(home, card)
    attrs = row.attributes
    assert attrs["title"] is None
    assert attrs["pending"]["title"] is True and attrs["pending"]["summary"] is True
    # The evidence briefing is the provisional body, labelled as what it is.
    assert str(row.object).startswith("What I know of ada:") and "Worked with Ada" in str(row.object)
    assert attrs["digest_method"] == "mechanical-card-v2"
    # The structure is the pass's, as before: key, revision, fingerprint, sources.
    assert attrs["target"] == "person:ada" and attrs["revision"] == 1
    assert attrs["evidence_fingerprint"] and len(attrs["known_source_ids"]) == 3
    assert list(current_world_models(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal)) == ["person:ada"]
    tasks = _tasks(home, card)
    assert sorted(tasks) == ["digest.author", "title.author"]                  # never a card.author beside them
    assert {t["priority"] for t in tasks.values()} == {5} and {t["status"] for t in tasks.values()} == {"pending"}
    # Read time: the app sees "being written…", never the briefing presented as the understanding.
    block = _display(home, card)
    assert block["title"] is None and block["pending"]["title"] is True and block["pending"]["summary"] is True
    understood = home.record_understanding(card)
    assert understood["pending"]["summary"] is True and understood["title"] is None
    # Debt: what the card owes is its title and summary, not a card.author rewrite.
    debt = home.understanding_debt(scopes=SCOPES)["debt"]
    assert debt["title.author"]["world_model"] == 1 and debt["digest.author"]["world_model"] == 1
    assert "card.author" not in debt
    assert home.enqueue_debt(scopes=SCOPES, dry_run=True)["would_enqueue"] == 0


def test_the_per_turn_lane_forms_pending_too(home) -> None:
    _ada(home)
    out = world_model_update(home, scopes=SCOPES, owner_id=OWNER, targets=["person:ada"], tuning=TUNING)
    [verdict] = out["formed"]
    assert verdict["pending"] == ["title", "summary"] and _row(home, verdict["card_id"]).attributes["title"] is None


def test_the_drainer_authors_a_pending_card_through_rewrite_digest_and_retitle(home) -> None:
    _ada(home)
    card = _card(home)
    target_before = _row(home, card).attributes["target"]
    out = _drain(home, card, summary="Ada is the archivist I work beside; we rebuilt the index together.")
    assert out["summary"]["applied"] is True and out["summary"]["field"] == "card"
    assert out["summary"]["pending_cleared"] == ["summary"]
    row = _row(home, card)
    assert row.object == "Ada is the archivist I work beside; we rebuilt the index together."
    assert row.attributes["digest_method"] == "authored-card-v1" and row.attributes["authored_lead"] == row.object
    assert row.attributes["pending"] == {**row.attributes["pending"], "title": True, "summary": False}
    assert row.attributes["target"] == target_before and row.attributes["revision"] == 1
    assert _tasks(home, card)["digest.author"]["status"] == "done"
    out = _drain(home, card, title="Ada, the archivist")
    assert out["title"]["applied"] is True and out["title"]["pending_cleared"] == ["title"]
    row = _row(home, card)
    assert row.attributes["title"] == "Ada, the archivist" and "pending" not in row.attributes
    assert {t["status"] for t in _tasks(home, card).values()} == {"done"}
    assert "pending" not in _display(home, card)
    # The summary is written: rewrite_digest is a card's door no more, and the briefing never comes back.
    again = home.rewrite_digest(card, text="Other words.", author=MODEL, reader=READER, sources=STEP,
                                cause="formation", expected_version=1)
    assert again["reason"] == "use_author_world_model"
    assert home.revert_digest(card, 0, expected_version=1)["reason"] == "provisional_summary"


def test_an_authored_title_carries_to_the_next_revision_and_the_prior_tasks_go(home) -> None:
    _ada(home)
    card = _card(home)
    _drain(home, card, title="Ada, the archivist")
    _form(home, "ada-9", title="Ada finished the index", digest="Ada finished the index.",
          participants=("person:ada", OWNER))
    card2 = _card(home)
    assert card2 != card
    attrs = _row(home, card2).attributes
    assert attrs["title"] == "Ada, the archivist" and attrs["revision"] == 2
    assert attrs["pending"]["title"] is False and attrs["pending"]["summary"] is True
    assert attrs["title_provenance"]["author"] == MODEL and attrs["title_provenance"]["carried_from"] == card
    assert sorted(_tasks(home, card2)) == ["digest.author"]
    # The prior revision's summary was never written: its live task is superseded, not left for a drainer.
    assert _tasks(home, card)["digest.author"]["status"] == "superseded"


def test_an_authored_lead_revises_as_a_pending_summary_over_lead_and_delta(home) -> None:
    _ada(home)
    card = _card(home)
    _drain(home, card, summary="Ada is the archivist I trust.", title="Ada, the archivist")
    _form(home, "ada-9", title="Ada finished the index", digest="Ada finished the index.",
          participants=("person:ada", OWNER))
    card2 = _card(home)
    row = _row(home, card2)
    assert str(row.object).startswith("Ada is the archivist I trust.\n\nSince then (1 new record(s)")
    assert row.attributes["pending"]["summary"] is True and row.attributes["title"] == "Ada, the archivist"
    assert row.attributes["authored_lead"] == "Ada is the archivist I trust."


def test_the_legacy_label_never_carries(home) -> None:
    # A card formed before 2026-11-09: the pass's own "World model: <subject>" label, no title provenance.
    _ada(home)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [legacy] = home.remember_many([MemoryRecordInput(
            kind="world_model", title="World model: person:ada", digest="What I know of person:ada: (legacy floor)",
            participants=("person:ada",),
            attributes={"world_model": True, "target": "person:ada", "revision": 1, "evidence_fingerprint": "old",
                        "known_source_ids": [], "digest_method": "mechanical-card-v2"})],
            scope=SCOPE, owner_id=OWNER, idempotency_key="legacy-card")
    card2 = _card(home)
    assert card2 != legacy
    attrs = _row(home, card2).attributes
    assert attrs["title"] is None and attrs["pending"]["title"] is True and "title_provenance" not in attrs


# --------------------------------------------------------------------------- the authored paths


def test_author_world_model_completes_the_pending_summary_and_keeps_the_title_pending(home) -> None:
    _ada(home)
    card = _card(home)
    provisional = str(_row(home, card).object)
    with pytest.raises(ValueError, match="provisional body"):
        author_world_model(home, target="person:ada", text=provisional, scope=SCOPE, owner_id=OWNER,
                           author=MODEL, reader=READER, sources=STEP)
    out = author_world_model(home, target="person:ada", text="Ada, whose archive I keep.", scope=SCOPE,
                             owner_id=OWNER, author=MODEL, reader=READER, sources=STEP)
    assert out["applied"] is True and out["card_id"] == card
    attrs = _row(home, card).attributes
    assert attrs["pending"]["summary"] is False and attrs["pending"]["title"] is True
    assert _tasks(home, card)["digest.author"]["status"] == "done"
    assert _tasks(home, card)["title.author"]["status"] == "pending"


def test_author_world_model_out_of_place_titles_from_an_authored_title_or_pending(home) -> None:
    _ada(home)
    card = _card(home)
    out = author_world_model(home, target="person:ada", text="Ada keeps the archive honest.", scope=SCOPE,
                             owner_id=OWNER, author="entity-reflection", in_place=False)
    assert out["pending"] == ["title"]
    attrs = _row(home, out["card_id"]).attributes
    assert attrs["title"] is None and attrs["pending"] == {**attrs["pending"], "title": True, "summary": False}
    assert attrs["digest_method"] == "authored-card-v1"
    assert _tasks(home, card)["digest.author"]["status"] == "superseded"
    _drain(home, out["card_id"], title="Ada, the archivist")
    out2 = author_world_model(home, target="person:ada", text="Ada, archivist and friend.", scope=SCOPE,
                              owner_id=OWNER, author="entity-reflection", in_place=False)
    attrs2 = _row(home, out2["card_id"]).attributes
    assert out2["pending"] == [] and attrs2["title"] == "Ada, the archivist" and "pending" not in attrs2


def test_alias_carries_what_is_authored_and_the_rest_forms_pending(home) -> None:
    _ada(home)
    card = _card(home)
    bound = alias_world_model(home, primary="person:ada", alias="person:admin", scope=SCOPE, owner_id=OWNER,
                              reason="the same person")
    attrs = _row(home, bound["card_id"]).attributes
    assert attrs["title"] is None and attrs["pending"]["title"] is True and attrs["pending"]["summary"] is True
    assert _tasks(home, card)["title.author"]["status"] == "superseded"
    _drain(home, bound["card_id"], summary="Ada, also signed in as admin.", title="Ada, the archivist")
    again = alias_world_model(home, primary="person:ada", alias="person:ada-old", scope=SCOPE, owner_id=OWNER,
                              reason="her old account")
    attrs = _row(home, again["card_id"]).attributes
    assert attrs["title"] == "Ada, the archivist" and "pending" not in attrs
    assert _row(home, again["card_id"]).object == "Ada, also signed in as admin."


# --------------------------------------------------------------------------- dream_pass


def test_a_dream_forms_pending_and_the_drainer_writes_its_summary_and_title(home) -> None:
    dream = _dream(home)
    row = _row(home, dream)
    assert row.attributes["title"] is None
    assert row.attributes["pending"]["title"] is True and row.attributes["pending"]["summary"] is True
    assert "memory islands lit up together" in str(row.object)           # the night's text: provisional body
    signals = row.attributes["signals"]
    tasks = _tasks(home, dream, ("title.author", "digest.author", "dream.narrate"))
    assert sorted(tasks) == ["digest.author", "dream.narrate", "title.author"]
    assert _display(home, dream)["pending"]["summary"] is True
    out = _drain(home, dream, summary="A night where the noon pool and the noon garden met.",
                 title="The noon pool beside the garden")
    assert out["summary"]["applied"] is True and out["summary"]["pending_cleared"] == ["summary"]
    assert out["title"]["pending_cleared"] == ["title"]
    row = _row(home, dream)
    assert row.object == "A night where the noon pool and the noon garden met."
    assert row.attributes["title"] == "The noon pool beside the garden" and "pending" not in row.attributes
    assert row.attributes["signals"] == signals                              # the structure stays
    assert tasks["dream.narrate"]["status"] == "pending"                     # the narration is still beside
    # Written: a dream's digest keeps its own door again; the night's text never comes back as its summary.
    again = home.rewrite_digest(dream, text="x", author=MODEL, reader=READER, sources=STEP, cause="formation",
                                expected_version=1)
    assert again["reason"] == "use_narrate_dream"
    assert home.revert_digest(dream, 0, expected_version=1)["reason"] == "provisional_summary"


# --------------------------------------------------------------------------- offers and the dedup summary


def test_miner_offers_form_pending_with_the_label_in_the_report_only(home) -> None:
    def diary(key: str, diary_type: str, title: str, words: str, session: str, **attrs: Any) -> str:
        return _form(home, key, kind="diary", title=title, digest=words,
                     attributes={"diary_type": diary_type, **attrs},
                     provenance={"source": "owner-direct", "session_id": session})

    problem = diary("q", "problem", "the connection pool keeps saturating",
                    "the connection pool keeps saturating under noon load", "s-alpha")
    _form(home, "e1", title="Debugged the connection pool saturating", keywords=("connection", "pool"),
          provenance={"session_id": "s-beta"})
    _form(home, "e2", title="Connection pool fix verified", keywords=("connection", "pool"),
          provenance={"session_id": "s-gamma"})
    diary("a", "note", "batching writers fixed the pool", "batching the noon writers fixed the connection pool",
          "s-gamma", resolves=problem)
    result = mine_candidates_pass(home, scopes=SCOPES, owner_id=OWNER)
    [offer] = [c for c in result["created"] if c["proposed_kind"] == "lesson"]
    assert offer["title"].startswith("Lesson candidate: ")                  # the report's label
    attrs = _row(home, offer["candidate_id"]).attributes
    assert attrs["title"] is None and attrs["pending"]["title"] is True and attrs["pending"]["summary"] is True
    assert sorted(_tasks(home, offer["candidate_id"])) == ["digest.author", "title.author"]


def test_consolidation_candidates_form_pending(home) -> None:
    for i in range(3):
        _form(home, f"b-{i}", kind="interest", title="The twelve bridges",
              digest=f"The twelve bridges keep returning to me, night {i}.")
    result = consolidation_pass(home, scopes=SCOPES, owner_id=OWNER)
    [created] = result["created"]
    attrs = _row(home, created["candidate_id"]).attributes
    assert attrs["title"] is None and attrs["pending"]["title"] is True and attrs["pending"]["summary"] is True
    assert attrs["maintenance_candidate"] is True
    assert sorted(_tasks(home, created["candidate_id"])) == ["digest.author", "title.author"]


def test_the_dedup_summary_forms_pending_and_still_adopts_once_authored(home) -> None:
    loop = [_form(home, f"loop-{i}", title=f"exchange: your own time continues #{i}",
                  digest=f"entity:nerin: your own time continues nerin: [used tool: read_file] tick {i}")
            for i in range(5)]
    report = wake_cue_dedup_pass(home, scope=SCOPE, owner_id=OWNER, actor="operator")
    [summary] = report["formed_summaries"]
    attrs = _row(home, summary).attributes
    assert attrs["title"] is None and attrs["pending"]["title"] is True and attrs["pending"]["summary"] is True
    _drain(home, summary, summary="A loop day of own-time ticks.", title="A loop day")
    assert _row(home, summary).attributes["digest_method"] == "authored-v1"

    # A crash between forming a day summary and closing its members (the dedup pass's own summary, authored since):
    # the re-run heals the residuals against it, never a second summary.
    others = [_form(home, f"loop2-{i}", title=f"exchange: own time again #{i}",
                    digest=f"entity:nerin: own time again nerin: [used tool: list_files] beat {i}")
              for i in range(4)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [crashed] = home.remember_many([MemoryRecordInput(
            kind="summary", title=None, pending=("title", "summary"), digest="entity:nerin: own time again …",
            edges=tuple(("summarizes", m) for m in others), attributes={"digest_method": "mechanical-dedup-v1"},
            provenance={"actor": "operator", "source": "wake_cue_dedup"})],
            scope=SCOPE, owner_id=OWNER, idempotency_key="crashed-day")
    _drain(home, crashed, summary="Another loop day.", title="Another loop day")
    home.close_record(others[0], kind="supersede", replacement_ids=[crashed], reason="dedup (interrupted)")
    again = wake_cue_dedup_pass(home, scope=SCOPE, owner_id=OWNER, actor="operator")
    assert sorted(again["residuals_repaired"] + [m for c in again["clusters"] for m in c["members"]]) == \
        sorted(others[1:])
    assert again.get("formed_summaries", []) in ([], [crashed])
    assert len(loop) == 5


def test_redigestion_hands_a_pending_title_on(home) -> None:
    from abstractmemory import apply_redigestion

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                 # the volatile journal; apply_redigestion is deprecated
        [gid] = home.remember_many([MemoryRecordInput(
            kind="episode", title=None, pending=("title",), digest="User: hi. Nerin: [used tool: read_file] ok",
            attributes={"digest_method": "mechanical-v2"})], scope=SCOPE, owner_id=OWNER, idempotency_key="redig")
        out = apply_redigestion(home, [{"record_id": gid, "digest": "Nerin read a file for the user."}],
                                actor="operator")
    new_gid = out["outcomes"][0]["new_record_id"]
    attrs = _row(home, new_gid).attributes
    assert attrs["title"] is None and attrs["pending"]["title"] is True and attrs["pending"]["summary"] is False
    assert sorted(_tasks(home, new_gid)) == ["title.author"]


# --------------------------------------------------------------------------- the queue is required


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_every_pass_refuses_a_home_without_a_queue_before_writing(kind, tmp_path) -> None:
    bare = _open(kind, tmp_path, task_queue=False)
    _ada(bare)
    for i in range(3):
        _form(bare, f"b-{i}", kind="interest", title="The twelve bridges",
              digest=f"The twelve bridges keep returning to me, night {i}.")
    before = _record_count(bare)
    seq = bare.journal.current_seq()
    calls = {
        "world_model_pass": lambda: world_model_pass(bare, scopes=SCOPES, owner_id=OWNER, tuning=TUNING),
        "dream_pass": lambda: dream_pass(bare, scopes=SCOPES, owner_id=OWNER),
        "mine_candidates_pass": lambda: mine_candidates_pass(bare, scopes=SCOPES, owner_id=OWNER),
        "consolidation_pass": lambda: consolidation_pass(bare, scopes=SCOPES, owner_id=OWNER),
        "wake_cue_dedup_pass": lambda: wake_cue_dedup_pass(bare, scope=SCOPE, owner_id=OWNER, actor="operator"),
        "sleep_pass": lambda: sleep_pass(bare, scopes=SCOPES, owner_id=OWNER, tuning=TUNING),
    }
    for verb, call in calls.items():
        with pytest.raises(ValueError, match=f"{verb} forms its records pending.*task_queue=True"):
            call()
    assert _record_count(bare) == before and bare.journal.current_seq() == seq
    # An empty home is refused too (the gate is the verb's, not a formation's accident).
    (tmp_path / "empty").mkdir()
    empty = _open(kind, tmp_path / "empty", task_queue=False)
    for verb, call in (("world_model_pass", lambda: world_model_pass(empty, scopes=SCOPES, owner_id=OWNER)),
                       ("sleep_pass", lambda: sleep_pass(empty, scopes=SCOPES, owner_id=OWNER))):
        with pytest.raises(ValueError, match=f"{verb} forms its records pending"):
            call()
    empty.journal.close()
    empty.store.close()
    # Reads still run.
    assert world_model_pass(bare, scopes=SCOPES, owner_id=OWNER, tuning=TUNING, report_only=True)["eligible"]
    assert sleep_pass(bare, scopes=SCOPES, owner_id=OWNER, tuning=TUNING, report_only=True)["pass_name"] == \
        "sleep_pass"
    assert _record_count(bare) == before
    bare.journal.close()
    bare.store.close()


def _labels(system) -> List[str]:
    return [str((a.attributes or {}).get("title")) for a in system.store.query(TripleQuery(limit=0))
            if (a.attributes or {}).get("record_kind") in ("world_model", "dream")]


def test_a_full_night_stores_no_mechanical_title(home) -> None:
    _ada(home)
    _dream(home)
    sleep_pass(home, scopes=SCOPES, owner_id=OWNER, tuning=TUNING)
    labels = _labels(home)
    assert labels and all(t == "None" for t in labels), labels
