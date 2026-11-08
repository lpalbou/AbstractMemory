"""A standing card moves to a new key in place, the old key kept as an alias (`rekey_world_model`).

The problem (title repair, operator 2026-11-08, root ADR 0054): an interest's card is keyed on the subject head of
the interest's TITLE (world_model._interest_subject_head). Retitling a cut interest title moves the key the next
`world_model_pass` computes, so that pass forms a SECOND card on the new key while the old card stands: the subject
splits (63 standing cards in ephemeral and nerin). `alias_world_model` cannot repair it (it needs a card on the
primary, and it revises into a new record). `rekey_world_model` changes the card's key in place.

Pinned here, on both substrate pairs (in-memory, and SQLite store + journal sharing one file):
- the control: without the re-key, a pass after the retitle forms a second card;
- after the re-key (before or after the interest's retitle), the pass forms NO card, revises nothing, and
  `current_world_models` holds one card, under the new key;
- the card keeps its record id, assertion id, revision, evidence fingerprint, sources, text, title, keywords,
  vector, edges, card versions and usage; field `target` versions = [0: the old key (mechanical, formation), 1: the
  new key with author, cause `repair`, reason and the move];
- the old key resolves to the card (alias_map, mention, world_model_update), and evidence stamped with the old key
  revises the SAME lineage under the new key;
- refusals write nothing: `unknown_card`, `target_taken` (merging is not this verb), `alias_bound_elsewhere`; a
  replay is `unchanged`; bad arguments raise; `revert_digest(field="target")` refuses; a pending card.author task
  survives; no embedder is called;
- `repair` is a cause of the understanding vocabulary.

MUTATION LIST (each applied to a scratch COPY of src/, this file run against it with PYTHONPATH, red confirmed):
- K1 reserved() keeps the old target (`"target": key` dropped in rekey_card_in_place) ->
  test_after_the_rekey_the_pass_forms_no_new_card and test_the_card_moves_in_place;
- K2 the old key not kept as an alias (`names.add(held)` dropped) -> test_after_the_rekey_the_pass_forms_no_new_card,
  test_the_old_key_still_resolves_to_the_card;
- K3 the elected-interest fold through aliases dropped (world_model_pass) ->
  test_the_rekey_before_the_retitle_also_holds_the_subject;
- K4 version 0 of the key never captured (`_target_version_zero` not appended) -> test_the_card_moves_in_place;
- K5 the target_taken refusal skipped -> test_refusals_write_nothing;
- K6 the key move embeds like a title (`field not in ("narration", "target")` back to `field != "narration"`) ->
  test_no_embedder_is_called_and_a_pending_authoring_survives;
- K7 the task queue has no `target` entry (on_rewrite map) ->
  test_no_embedder_is_called_and_a_pending_authoring_survives;
- K8 `repair` removed from REWRITE_CAUSES -> test_repair_is_an_understanding_cause and the rekey tests.
"""

from __future__ import annotations

import hashlib
import warnings
from typing import Any, Dict, List

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import (  # noqa: E402
    REWRITE_CAUSES,
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    Stimulus,
    alias_map,
    alias_world_model,
    current_world_models,
    rekey_world_model,
    standing_world_models,
    world_model_pass,
    world_model_update,
)
from abstractmemory.records import resolve_digest_assertion  # noqa: E402
from abstractmemory.sleep_policy import SleepTuning  # noqa: E402
from abstractmemory.store import TripleQuery  # noqa: E402
from abstractmemory.world_model import mention_orientation_cards  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
SCOPES = [(SCOPE, OWNER)]
TUNING = SleepTuning(world_model_evidence_floor=3)
REPAIRER = {"kind": "operator", "id": "laurent"}
REASON = "the interest was retitled from its formation cut (title repair 2026-11-08)"

CUT = "First-person accounts as the bridge between aggregate crisis"
OLD_HEAD = "first-person accounts as the bridge between aggregate crisis"
NEW_TITLE = "First-person accounts bridging aggregate crisis data and lived human experience"
OLD, NEW = f"topic:{OLD_HEAD}", f"topic:{NEW_TITLE.lower()}"
BODY = ("First-person accounts as the bridge between aggregate crisis data and lived human experience: the dimension "
        "where displacement numbers become specific people.")
KEY_ATTRS = {"target", "aliases", "target_version", "target_provenance"}


class Embedder:
    """Deterministic unit vectors from the text hash; `dead` makes every call fail (an unreachable endpoint)."""

    model = "fake-hash-16"

    def __init__(self, dim: int = 16) -> None:
        self.dim, self.dead = dim, False

    def embed_texts(self, texts):
        if self.dead:
            raise RuntimeError("connection refused")
        out = []
        for t in texts:
            seed = int(hashlib.sha256(str(t).encode()).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).standard_normal(self.dim)
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
    system.emb = emb
    yield system
    journal.close()
    store.close()


def _form(system, key: str, kind: str, title: str, digest: str, **kw: Any) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many([MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)],
                                     scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _pass(system, **kw: Any) -> Dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return world_model_pass(system, scopes=SCOPES, owner_id=OWNER, tuning=TUNING, **kw)


def _cards(system) -> Dict[str, Any]:
    return current_world_models(system.store, scope=SCOPE, owner_id=OWNER, journal=system.journal)


def _standing_count(system) -> int:
    return sum(len(v) for v in standing_world_models(
        system.store, scope=SCOPE, owner_id=OWNER, journal=system.journal).values())


def _subject(system) -> Dict[str, str]:
    """nerin's case: an interest whose title the runtime cut, plus an episode stamped with the cut subject; the pass
    forms ONE card on the cut key from both."""
    interest = _form(system, "int", "interest", f"interest: {CUT}", BODY, keywords=("crisis", "testimony"))
    episode = _form(system, "ep", "episode", "The crisis numbers are people",
                    "User: what do the crisis numbers mean? Nerin: they are specific people.", topic=OLD_HEAD)
    out = _pass(system)
    [verdict] = [v for v in out["formed"] if v["target"] == OLD]
    return {"interest": interest, "episode": episode, "card": verdict["card_id"]}


def _retitle_interest(system, gid: str) -> None:
    out = system.retitle(gid, title=NEW_TITLE, author=REPAIRER, cause="repair", expected_version=0)
    assert out["applied"] is True


def _rekey(system, old: str = OLD, new: str = NEW, **kw: Any) -> Dict[str, Any]:
    kw.setdefault("author", REPAIRER)
    kw.setdefault("cause", "repair")
    kw.setdefault("reason", REASON)
    return system.rekey_world_model(old, new, scope=SCOPE, owner_id=OWNER, **kw)


def _edges(system, gid: str) -> List[tuple]:
    return sorted((e.predicate, e.object) for e in system.store.query(TripleQuery(subject=gid, limit=0))
                  if isinstance(e.attributes, dict) and e.attributes.get("record_edge"))


# --------------------------------------------------------------------------- the split, and its repair


def test_without_the_rekey_a_retitled_interest_splits_its_subject(home) -> None:
    """The control: the fixture reproduces the reported split (a second card on the new key)."""
    ids = _subject(home)
    _retitle_interest(home, ids["interest"])
    out = _pass(home, report_only=True)
    assert NEW in {v["target"] for v in out["formed"]}
    assert OLD in _cards(home)


@pytest.mark.parametrize("order", ["retitle-first", "rekey-first"])
def test_after_the_rekey_the_pass_forms_no_new_card(home, order) -> None:
    ids = _subject(home)
    if order == "retitle-first":
        _retitle_interest(home, ids["interest"])
        assert _rekey(home)["applied"] is True
    else:
        assert _rekey(home)["applied"] is True
        _retitle_interest(home, ids["interest"])
    for _ in range(2):  # a second sleep stays a no-op
        out = _pass(home)
        assert out["formed"] == [] and out["formed_count"] == 0 and out["repaired"] == []
        assert out["unchanged"] == [{"target": NEW, "card_id": ids["card"]}]
    assert list(_cards(home)) == [NEW] and _standing_count(home) == 1
    assert _cards(home)[NEW].subject == ids["card"]


def test_the_rekey_before_the_retitle_also_holds_the_subject(home) -> None:
    """An interest still titled with the cut words heads to the old key: the alias carries its election."""
    ids = _subject(home)
    assert _rekey(home)["applied"] is True
    out = _pass(home)
    assert out["formed"] == [] and out["unchanged"] == [{"target": NEW, "card_id": ids["card"]}]
    assert list(_cards(home)) == [NEW]


def test_the_card_moves_in_place(home) -> None:
    ids = _subject(home)
    gid = ids["card"]
    home.reinforce(gid, reason="read it during a visit", scope=SCOPE, owner_id=OWNER)
    before = resolve_digest_assertion(home.store, gid)
    vec0 = home.store.stored_vector(before.assertion_id)
    counts0 = home.access_counts([gid])
    activation0 = home.activation([gid], scope=SCOPE, owner_id=OWNER)
    edges0 = _edges(home, gid)
    _retitle_interest(home, ids["interest"])

    out = _rekey(home)
    assert out["applied"] is True and out["outcome"] == "applied" and out["field"] == "target"
    assert out["version"] == 1 and out["previous_version"] == 0 and out["captured_original"] is True
    assert out["vector_rewritten"] is False
    assert (out["card_id"], out["old_key"], out["new_key"], out["aliases"]) == (gid, OLD, NEW, [OLD])
    assert out["revision"] == before.attributes["revision"] == 1

    after = resolve_digest_assertion(home.store, gid)
    assert after.subject == before.subject and after.assertion_id == before.assertion_id
    assert after.object == before.object and after.observed_at == before.observed_at
    assert after.provenance == before.provenance
    assert after.attributes["target"] == NEW and after.attributes["aliases"] == [OLD]
    assert after.attributes["target_version"] == 1
    assert after.attributes["target_provenance"]["author"] == REPAIRER
    # Everything else is byte-equal: revision, fingerprint, sources, span, digest_method, title, keywords, reading.
    assert {k: v for k, v in after.attributes.items() if k not in KEY_ATTRS} == \
        {k: v for k, v in before.attributes.items() if k not in KEY_ATTRS}
    assert home.store.stored_vector(after.assertion_id) == vec0
    assert _edges(home, gid) == edges0
    assert home.access_counts([gid]) == counts0
    assert home.activation([gid], scope=SCOPE, owner_id=OWNER) == activation0
    assert home.versions(gid) == []                                   # the card's text never rewritten

    rows = home.versions(gid, field="target")
    assert [(r["version"], r["text"], r["current"]) for r in rows] == [(0, OLD, False), (1, NEW, True)]
    v0, v1 = rows
    assert v0["author"] == {"kind": "mechanical", "id": "world_model_pass"}
    assert v0["cause"]["cause"] == "formation" and v0["digest_method"] == "world-model-pass"
    assert v1["author"] == REPAIRER and v1["digest_method"] == "rekey-v1"
    assert v1["cause"] == {"cause": "repair", "reason": REASON, "rekey": {"from": OLD, "to": NEW}}
    # The move is in the journal's revision stream, with its provenance.
    moves = [e["payload"] for e in home.export_replay(families=("revision",))
             if e["payload"]["record_id"] == gid and e["payload"]["field"] == "target"]
    assert [(m["version"], m["text"]) for m in moves] == [(0, OLD), (1, NEW)]
    assert moves[1]["author"] == REPAIRER and moves[1]["cause"]["cause"] == "repair"


def test_the_old_key_still_resolves_to_the_card(home) -> None:
    ids = _subject(home)
    _retitle_interest(home, ids["interest"])
    _rekey(home)
    assert alias_map(home.store, scope=SCOPE, owner_id=OWNER, journal=home.journal) == {OLD: NEW}
    [hit] = mention_orientation_cards(
        home.store, Stimulus(cue_text="first-person accounts as the bridge between aggregate crisis"), SCOPES)
    assert hit["target"] == NEW and hit["assertion"].subject == ids["card"] and "alias" in hit["detail"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        upd = world_model_update(home, scopes=SCOPES, owner_id=OWNER, targets=[OLD], tuning=TUNING)
    assert upd["formed"] == [] and upd["targets_seen"] == 1


def test_evidence_under_the_old_key_revises_the_same_lineage(home) -> None:
    ids = _subject(home)
    _retitle_interest(home, ids["interest"])
    _rekey(home)
    _form(home, "ep2", "episode", "Testimony again", "Nerin: each number is a person who told me their day.",
          topic=OLD_HEAD)                                       # a later record still stamped with the cut subject
    out = _pass(home)
    [verdict] = out["formed"]
    assert verdict["target"] == NEW and verdict["revision"] == 2 and verdict["source_count"] == 3
    card = _cards(home)[NEW]
    assert list(_cards(home)) == [NEW] and _standing_count(home) == 1
    assert card.subject != ids["card"] and card.attributes["aliases"] == [OLD]
    assert ("refines", ids["card"]) in _edges(home, card.subject)


# --------------------------------------------------------------------------- refusals and guards


def test_refusals_write_nothing(home) -> None:
    ids = _subject(home)
    before = resolve_digest_assertion(home.store, ids["card"])

    # target_taken: another standing card already holds the new key (merging is out of scope).
    _form(home, "int-new", "interest", NEW_TITLE, "A second interest on the whole subject.")
    _pass(home)
    other = _cards(home)[NEW]
    taken = _rekey(home)
    assert (taken["applied"], taken["outcome"], taken["reason"]) == (False, "refused", "target_taken")
    assert taken["standing_card_id"] == other.subject and taken["card_id"] == ids["card"]

    assert _rekey(home, old="topic:never formed")["reason"] == "unknown_card"

    # alias_bound_elsewhere: the new key is an alias of a third card.
    for i in range(3):
        _form(home, f"ada-{i}", "episode", f"Ada day {i}", f"Archive work with Ada, day {i}.",
              participants=("person:ada", OWNER))
    _pass(home)
    alias_world_model(home, primary="person:ada", alias="person:ada-lovelace", scope=SCOPE, owner_id=OWNER,
                      reason="one archivist, two names")
    bound = _rekey(home, new="person:ada-lovelace")
    assert bound["reason"] == "alias_bound_elsewhere" and bound["primary"] == "person:ada"

    after = resolve_digest_assertion(home.store, ids["card"])
    assert after.attributes == before.attributes
    assert home.versions(ids["card"], field="target") == []

    for bad in ({"old": OLD, "new": OLD}, {"old": "", "new": NEW}, {"old": OLD, "new": " "}):
        with pytest.raises(ValueError):
            _rekey(home, old=bad["old"], new=bad["new"])
    with pytest.raises(ValueError):
        _rekey(home, cause="repaired")
    with pytest.raises(ValueError):
        _rekey(home, author={"kind": "capability-model", "id": "understanding"})  # a model author names its reader


def test_a_replay_is_unchanged_and_a_revert_refuses(home) -> None:
    ids = _subject(home)
    assert _rekey(home)["applied"] is True
    again = _rekey(home)
    assert (again["applied"], again["outcome"], again["card_id"], again["version"]) == \
        (False, "unchanged", ids["card"], 1)
    assert len(home.versions(ids["card"], field="target")) == 2
    rev = home.revert_digest(ids["card"], 0, expected_version=1, field="target")
    assert rev["reason"] == "use_rekey_world_model"
    # Re-keying back is the way: the card answers to both keys, under the old one again.
    back = _rekey(home, old=NEW, new=OLD)
    assert back["applied"] is True and back["version"] == 2 and back["aliases"] == [NEW]
    assert list(_cards(home)) == [OLD]


def test_no_embedder_is_called_and_a_pending_authoring_survives(home) -> None:
    ids = _subject(home)
    [task] = home.tasks.tasks(kind=("card.author",), target_id=ids["card"])
    assert task["status"] == "pending"
    home.emb.dead = True                     # the key is not in the canonical text: no embedder needed
    out = rekey_world_model(home, OLD, NEW, scope=SCOPE, owner_id=OWNER, author=REPAIRER, cause="repair")
    assert out["applied"] is True and out["vector_rewritten"] is False
    assert home.tasks.task(task["task_id"])["status"] == "pending"


# --------------------------------------------------------------------------- the cause vocabulary


def test_repair_is_an_understanding_cause(home) -> None:
    assert "repair" in REWRITE_CAUSES
    gid = _form(home, "les", "lesson", f"lesson: {CUT}", BODY)
    out = home.retitle(gid, title=NEW_TITLE, author=REPAIRER, cause={"cause": "repair", "ruling": "ADR 0054"},
                       expected_version=0)
    assert out["applied"] is True
    row = resolve_digest_assertion(home.store, gid)
    assert row.attributes["title_provenance"]["cause"] == {"cause": "repair", "ruling": "ADR 0054"}
    with pytest.raises(ValueError):
        home.retitle(gid, title="Another title", author=REPAIRER, cause="repaired", expected_version=1)
