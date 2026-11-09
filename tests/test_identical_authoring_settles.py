"""An authored text identical to a pending field's provisional one settles it (Codex review 3, 2026-11-09, finding 7).

The finding: `understanding._apply` answered `unchanged` for identical words BEFORE it cleared the pending marker or
completed the task. The runtime's drainer takes `unchanged` as success (`authored: 1`), so the summary stayed pending
and its `digest.author` task stayed leased; the lease expired, the task was claimed again (or, exhausted, re-armed by
the repair) and the same words came back: a loop with no end. Now clearing a pending marker counts as a change: the
authored reading is recorded as a version (its provenance: the model author, reader and sources), the marker is
cleared and the task completed in the same transaction, `outcome="applied"` with `pending_cleared`. The canonical text
is unchanged, so no embedder call is made and the vector stands. Identical words on a record with nothing pending are
still `unchanged` (nothing written). Every case runs on both substrate pairs.

MUTATION LIST (scratch copy, each mutant run against this file; all red, the source restored byte-exact):
I1 identical words answer `unchanged` even when they settle a pending field; I2 the settling write embeds again;
I3 the settling write completes no unnamed pending task.
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
)
from abstractmemory.records import resolve_digest_assertion  # noqa: E402

SCOPE = "life"
OWNER = "entity:nerin"
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "artifact", "artifact_id": "authoring-call-1"}]
LIVE = ("pending", "deferred", "leased")
WORDS = "We talked about the archive."


class Embedder:
    model = "fake-hash-16"

    def __init__(self) -> None:
        self.calls = 0

    def embed_texts(self, texts):
        self.calls += 1
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
    system.kind = request.param
    system.emb = emb
    yield system
    system.journal.close()
    system.store.close()


def _form(system, key: str, *, pending=("summary",)) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        [gid] = system.remember_many(
            [MemoryRecordInput(kind="episode", title="A talk at the archive", digest=WORDS, pending=pending)],
            scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _task(system, gid: str, kind: str = "digest.author") -> Dict[str, Any]:
    [t] = [t for t in system.tasks.tasks(target_id=gid) if t["kind"] == kind]
    return t


def _write(system, gid: str, *, task_id=None, text: str = WORDS) -> Dict[str, Any]:
    return system.rewrite_digest(gid, text=text, author=MODEL, reader=READER, sources=STEP,
                                 cause={"cause": "formation", "pending": "summary"}, expected_version=0,
                                 task_id=task_id)


def _attrs(system, gid: str) -> Dict[str, Any]:
    return dict(resolve_digest_assertion(system.store, gid).attributes)


def test_identical_authored_words_settle_a_pending_summary(home) -> None:
    gid = _form(home, "same-words")
    t = _task(home, gid)
    assert home.tasks.claim([t["task_id"]], holder="rt")["claimed"]
    out = _write(home, gid, task_id=t["task_id"])
    assert out["applied"] is True and out["outcome"] == "applied"
    assert out["pending_cleared"] == ["summary"] and out["version"] == 1
    attrs = _attrs(home, gid)
    assert "pending" not in attrs
    assert attrs["digest_version"] == 1 and attrs["authored_by"] == "summaries"
    assert attrs["understanding"]["author"] == MODEL and attrs["understanding"]["reader"]["model"] == READER["model"]
    assert home.tasks.task(t["task_id"])["status"] == "done"
    rows = home.versions(gid, field="digest")
    assert [r["version"] for r in rows] == [0, 1]
    assert rows[0]["cause"].get("pending_summary") is True       # the provisional words, never restored
    assert rows[1]["author"] == MODEL and rows[1]["text"] == WORDS


def test_the_settled_record_never_comes_back(home) -> None:
    """The loop the finding describes: lease expiry and re-arm find nothing left to do."""
    gid = _form(home, "no-loop")
    t = _task(home, gid)
    home.tasks.claim([t["task_id"]], holder="rt", lease_seconds=1)
    _write(home, gid, task_id=t["task_id"])
    later = "2999-01-01T00:00:00+00:00"   # every lease long expired
    assert home.tasks.claim([t["task_id"]], holder="rt2", now=later)["claimed"] == []
    assert [x for x in home.tasks.tasks(target_id=gid) if x["status"] in LIVE] == []
    assert home.pending_records(scopes=[(SCOPE, OWNER)], live_task=None) == []
    again = home.rearm_pending(gid)
    assert again["applied"] is False and again["reason"] == "not_pending"


def test_an_unnamed_settling_write_completes_the_pending_task(home) -> None:
    gid = _form(home, "unnamed")
    t = _task(home, gid)
    out = _write(home, gid)
    assert out["applied"] is True and out["pending_cleared"] == ["summary"]
    assert home.tasks.task(t["task_id"])["status"] == "done"


def test_the_settling_write_keeps_the_vector_and_calls_no_embedder(home) -> None:
    gid = _form(home, "vector")
    aid = str(resolve_digest_assertion(home.store, gid).assertion_id)
    before, calls = home.store.stored_vector(aid), home.emb.calls
    assert before is not None
    out = _write(home, gid)
    assert out["applied"] is True and out["vector_rewritten"] is False
    assert home.emb.calls == calls
    assert home.store.stored_vector(aid) == before


def test_identical_words_on_a_record_with_nothing_pending_stay_unchanged(home) -> None:
    gid = _form(home, "authored", pending=())
    out = _write(home, gid)
    assert out["applied"] is False and out["outcome"] == "unchanged" and out["reason"] == "identical"
    assert home.versions(gid, field="digest") == []
    assert int(_attrs(home, gid).get("digest_version") or 0) == 0


def test_different_words_still_write_as_before(home) -> None:
    gid = _form(home, "different")
    out = _write(home, gid, text="We talked about the archive and its catalogue.")
    assert out["applied"] is True and out["pending_cleared"] == ["summary"] and out["vector_rewritten"] is True
