"""A record whose title failed at formation is stored UNTITLED: its title is NULL, never "" and never a stand-in.

Operator ruling 2026-11-09 (root backlog 1146): "we shouldn't need a fallback; if the title fails, add information to
a temporary error file in untracked/ so we know what's failing and fix it at the source". The runtime forms the
record with title None and logs the failure; memory accepts it for the kinds the runtime forms from the entity's own
election blocks (`TITLE_OPTIONAL_KINDS`: interest, lesson, realization, observation, every diary entry kind). Every
other kind still requires a title.

Pinned here, on both substrate pairs (in-memory, and SQLite store + journal sharing one file):
- formation: None, "" and whitespace store `attributes.title = None` for every optional kind; other kinds refuse;
- `short_title(None)` is None; a recall handle, a replay display block, `record_understanding`, `recent_records`,
  `explain_recall`'s origin and the identity card's briefs serve None, never an "s p o" preview or the body;
- the canonical text (FTS / keyword index / vector input) is the body alone: no "None" token;
- the world-model key of an untitled interest is `topic:<its graph id>` (`interest_target`), never a head cut from its
  body; the candidate miner lets an untitled interest own no theme;
- `retitle` of an untitled record: version 0 = None (text and title), version 1 the authored title; revert to 0 makes
  it untitled again (the SQLite NOT NULL columns round-trip it);
- an owner-direct chained diary entry formed untitled verifies; the dedup pass adds no "None" token.

MUTATION LIST (each applied to a scratch COPY of src/, this file run against it with PYTHONPATH, red confirmed):
- U1 the kind gate dropped (every kind may be untitled) -> test_other_kinds_still_require_a_title;
- U2 "" stored instead of None (`title or None` -> `title`) -> test_title_optional_kinds_form_untitled;
- U3 short_title(None) returns "" -> test_short_title_of_no_title_is_none;
- U4 the shelf handle falls back to the "s p o" preview -> test_recall_serves_no_title_and_indexes_the_body_alone;
- U5 canonical_text renders str(None) -> test_recall_serves_no_title_and_indexes_the_body_alone;
- U6 the replay block falls back to "subject predicate" -> test_read_surfaces_serve_none;
- U7 record_understanding serves "" -> test_read_surfaces_serve_none;
- U8 the world-model key reads the digest when the title is empty -> test_untitled_interest_keys_its_card_on_its_id;
- U9 the miner's interest head reads the body -> test_untitled_interest_owns_no_theme;
- U10 the SQLite version row writes None into a NOT NULL column -> test_retitle_an_untitled_record;
- U11 entity_card briefs serve "" -> test_identity_card_briefs_serve_none;
- U12 the dedup pass tokenizes str(None) -> test_dedup_adds_no_none_token.
"""

from __future__ import annotations

import hashlib
import warnings
from typing import Any

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import (  # noqa: E402
    MEMORY_RECORD_KINDS,
    TITLE_OPTIONAL_KINDS,
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    Stimulus,
    mine_candidates_pass,
    verify_diary_chain,
    wake_cue_dedup_pass,
    world_model_pass,
)
from abstractmemory.canonical_text import canonical_text, short_title  # noqa: E402
from abstractmemory.diary import diary_entry_hash  # noqa: E402
from abstractmemory.records import DIARY_TYPES, resolve_digest_assertion  # noqa: E402
from abstractmemory.sleep_policy import SleepTuning  # noqa: E402
from abstractmemory.world_model import interest_target  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
MODEL = {"kind": "capability-model", "id": "understanding"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "step", "run_id": "run-untitled-1", "seq": 3}]
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
        system = MemorySystem(store=store, journal=journal, embedder=emb)
    system.kind, system.emb = request.param, emb
    yield system
    journal.close()
    store.close()


def _form(system, key: str, kind: str, title: Any, digest: str, **kw: Any) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many([MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)],
                                     scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _untitled(system, key: str, kind: str, title: Any = None, digest: str = BODY, **kw: Any) -> str:
    if kind.startswith("diary:"):
        kw.setdefault("attributes", {"diary_type": kind[6:], "entry_id": f"book-{key}"})
        kw.setdefault("provenance", {"source": "diary-projection"})
        kind = "diary"
    return _form(system, key, kind, title, digest, **kw)


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


OPTIONAL = ["interest", "lesson", "realization", "observation"] + [f"diary:{t}" for t in sorted(DIARY_TYPES)]


# --------------------------------------------------------------------------- formation


def test_the_optional_kinds_are_the_election_kinds() -> None:
    assert TITLE_OPTIONAL_KINDS == {"interest", "lesson", "realization", "observation", "diary"}


@pytest.mark.parametrize("given", [None, "", "  \n\t "])
@pytest.mark.parametrize("kind", OPTIONAL)
def test_title_optional_kinds_form_untitled(home, kind, given) -> None:
    gid = _untitled(home, f"u-{kind}-{given!r}", kind, title=given)
    row = _row(home, gid)
    assert "title" in row.attributes and row.attributes["title"] is None   # NULL, never "" and never a label
    assert row.object == BODY
    assert MemoryRecordInput(kind="lesson", title="  A lesson  ", digest="x").title == "A lesson"


@pytest.mark.parametrize("kind", sorted(MEMORY_RECORD_KINDS - TITLE_OPTIONAL_KINDS))
def test_other_kinds_still_require_a_title(kind) -> None:
    for given in (None, "", "   "):
        with pytest.raises(ValueError, match="title must be a non-empty string"):
            MemoryRecordInput(kind=kind, title=given, digest="Some words.")


def test_short_title_of_no_title_is_none() -> None:
    assert short_title(None) is None
    assert short_title("") is None and short_title("   ") is None
    assert short_title("A title") == "A title"


# --------------------------------------------------------------------------- read surfaces


def test_recall_serves_no_title_and_indexes_the_body_alone(home) -> None:
    gid = _untitled(home, "u-recall", "lesson", keywords=("trials",))
    _form(home, "other", "episode", "exchange: gardens", "An unrelated exchange about gardens.")
    row = _row(home, gid)
    assert canonical_text(row) == f"{BODY}\nkeywords: trials"          # no title line, no "None"
    if home.kind == "sqlite":
        store = home.store
        assert [a.subject for a in store.query_keywords(["quorvanth"], scope=SCOPE, owner_id=OWNER)] == [gid]
        assert store.query_keywords(["none"], scope=SCOPE, owner_id=OWNER) == []
    recall = home.reconstruct(Stimulus(cue_text="quorvanth registry"), scopes=[(SCOPE, OWNER)], journal=False)
    [handle] = [h for h in recall.handles if h.record_id in {gid, row.assertion_id}] or [None]
    assert handle is not None
    assert handle.title is None and handle.digest == BODY                # never the "s p o" preview of the body
    assert handle.to_dict()["title"] is None


def test_read_surfaces_serve_none(home) -> None:
    gid = _untitled(home, "u-read", "interest")
    understood = home.record_understanding(gid)
    assert understood["title"] is None and understood["digest"] == BODY
    [binding] = [e for e in home.export_replay(families=("binding",)) if e["payload"]["record_id"] == gid]
    assert binding["display"]["title"] is None                           # never "<graph id> dcterms:abstract"
    recent = home.recent_records(scopes=[(SCOPE, OWNER)], since="2000-01-01T00:00:00Z")
    [r] = [r for r in recent["records"] if r["graph_id"] == gid]
    assert r["title"] is None
    assert home.explain_recall(gid)["origin"]["title"] is None


def test_identity_card_briefs_serve_none(home) -> None:
    interest = _untitled(home, "u-card-i", "interest")
    lesson = _untitled(home, "u-card-l", "lesson", digest="Check a country's indicators before citing them.")
    card = home.entity_card(scope_pairs=[(SCOPE, OWNER)], owner_id=OWNER)
    [i] = [b for b in card["discoveries"]["interests"] if b["record_id"] == interest]
    [lb] = [b for b in card["lessons"]["lessons"] if b["record_id"] == lesson]
    assert i["title"] is None and i["statement"] == BODY
    assert lb["title"] is None
    firsts = {m["what"]: m for m in card["key_moments"]["moments"] if m["type"] == "first"}
    assert firsts["first_interest"]["title"] is None


# --------------------------------------------------------------------------- world-model key


def test_interest_target_keys() -> None:
    assert interest_target("ex:interest-abc", None) == "topic:ex:interest-abc"
    assert interest_target("ex:interest-abc", "  ") == "topic:ex:interest-abc"
    assert interest_target("ex:interest-abc", "interest: Tidal energy — the coast") == "topic:tidal energy"
    assert interest_target("ex:interest-abc", "Ab") == ""                # a head too short to name a subject


def test_untitled_interest_keys_its_card_on_its_id(home) -> None:
    gid = _untitled(home, "u-wm", "interest")
    titled = _form(home, "t-wm", "interest", "interest: Tidal energy — how the tides could power the coast",
                   "How the tides could power the coast.")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out = world_model_pass(home, scopes=[(SCOPE, OWNER)], owner_id=OWNER, tuning=SleepTuning())
    targets = {f["target"] for f in out["formed"]}
    assert f"topic:{gid}" in targets                                     # the stable structured key
    assert "topic:decentralized clinical trials and health equity" not in targets   # never cut from the body
    assert "topic:tidal energy" in targets                               # a titled interest: its head
    [card] = [f for f in out["formed"] if f["target"] == f"topic:{gid}"]
    attrs = _row(home, card["card_id"]).attributes
    assert attrs["target"] == f"topic:{gid}" and attrs["title"] == f"World model: {gid}"
    assert titled != gid


# --------------------------------------------------------------------------- candidate miner


def test_untitled_interest_owns_no_theme(home) -> None:
    _untitled(home, "u-miner", "interest", digest="tidal energy — how the tides could power the coast")
    for i, session in enumerate(("s-1", "s-2", "s-3")):
        _form(home, f"m-i{i}", "episode", f"Reading about tidal energy, day {i}", f"Tidal energy, day {i}.",
              keywords=("tidal energy",), provenance={"session_id": session})
    result = mine_candidates_pass(home, scopes=[(SCOPE, OWNER)], owner_id=OWNER)
    offers = [c for c in result["created"] if c["proposed_kind"] == "interest"]
    assert [c["title"] for c in offers] == ["Interest candidate: tidal energy"]   # his body declared nothing
    assert not any("standing interest" in s.get("reason", "") for s in result["skipped"])


# --------------------------------------------------------------------------- retitle


def test_retitle_an_untitled_record(home) -> None:
    gid = _untitled(home, "u-retitle", "realization")
    new = "Realization: numbers become people when the account is first-person"
    out = home.retitle(gid, title=new, author=MODEL, reader=READER, sources=STEP, cause="backfill",
                       expected_version=0)
    assert out["applied"] is True and out["version"] == 1 and out["captured_original"] is True
    row = _row(home, gid)
    assert row.attributes["title"] == new and row.object == BODY
    assert canonical_text(row).splitlines()[0] == new
    rows = home.versions(gid, field="title")
    assert [(r["version"], r["text"], r["title"], r["current"]) for r in rows] == \
        [(0, None, None, False), (1, new, new, True)]
    assert rows[0]["cause"]["cause"] == "formation"
    assert home.record_understanding(gid)["title"] == new
    if home.kind == "sqlite":
        assert [a.subject for a in home.store.query_keywords(["first-person"], scope=SCOPE, owner_id=OWNER)] \
            == [gid]

    back = home.revert_digest(gid, 0, field="title", expected_version=1)
    assert back["applied"] is True and back["version"] == 2
    row = _row(home, gid)
    assert row.attributes["title"] is None and canonical_text(row) == BODY
    assert [(r["version"], r["text"]) for r in home.versions(gid, field="title")] == \
        [(0, None), (1, new), (2, None)]
    assert home.record_understanding(gid)["title"] is None


def test_retitle_of_an_untitled_record_refuses_an_empty_title(home) -> None:
    gid = _untitled(home, "u-empty", "observation")
    out = home.retitle(gid, title="  ", author=MODEL, reader=READER, sources=STEP, cause="backfill",
                       expected_version=0)
    assert out["reason"] == "empty_title" and home.versions(gid, field="title") == []


# --------------------------------------------------------------------------- diary chain, dedup


def test_an_untitled_chained_diary_entry_verifies(home) -> None:
    first = _form(home, "chain-1", "diary", None, "Owner-direct words, attested.",
                  attributes={"diary_type": "note", "prev_entry_hash": ""}, provenance={"source": "owner-direct"})
    attrs = _row(home, first).attributes
    assert attrs["title"] is None
    assert attrs["entry_hash"] == diary_entry_hash("", "Owner-direct words, attested.", _row(home, first).observed_at)
    assert verify_diary_chain(home.store, scope=SCOPE, owner_id=OWNER)["intact"] is True


def test_dedup_adds_no_none_token(home) -> None:
    # Pairwise Jaccard 4/6 = 0.67 under a 0.70 floor: no cluster. A "None" token in every member would make it
    # 5/7 = 0.71 and merge three distinct observations.
    for i, tail in enumerate(("foxtrot", "golfing", "hotelier")):
        _untitled(home, f"dd-{i}", "observation", digest=f"alpha bravo charlie delta {tail}")
    report = wake_cue_dedup_pass(home, scope=SCOPE, owner_id=OWNER, actor="operator", kind="observation",
                                 jaccard_floor=0.70, min_cluster=3, report_only=True)
    assert report["cluster_count"] == 0
