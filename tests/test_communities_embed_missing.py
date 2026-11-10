"""`embed_missing` (communities.py; framework seat's frozen verb, 2026-11-10): the vector-less records of a home
embedded with the store's own embedder before the night's communities pass, one guarded commit per vector.

Covered on both substrate pairs: every unvectored record in scope embedded (and then detected by the pass);
`record_ids` narrows it; the embedder unavailable -> skipped with its reason, never raised, nothing written; no
embedder -> skipped; cancelled mid-way -> the earlier vectors stand, the rest skipped `cancelled`; a wrong dimension
-> failed, never written; a community record is never embedded; each vector is its own commit (one guard call per
record) and a refused guard propagates with the earlier vectors kept.

MUTATION LIST (scratch copy untracked/communities/mut; all red, source restored): E1 embed every record (vectored
ones too); E2 raise when the embedder fails; E3 ignore `cancelled`; E4 write a wrong-dimension vector; E5 one commit
for the whole batch.
"""

from __future__ import annotations

import warnings
from typing import List

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import MemoryRecordInput  # noqa: E402
from abstractmemory import communities as C  # noqa: E402

from test_communities import (  # noqa: E402
    OWNER,
    SCOPES,
    Guard,
    _form,
    _open,
    _pass,
    _topic,
)


@pytest.fixture(params=["memory", "sqlite"])
def kind(request):
    return request.param


def _novec(system, n: int, key: str = "nv", topic: int = 2) -> List[str]:
    return _form(system, [MemoryRecordInput(kind="episode", title=f"N{i}", digest=f"novec topic-{topic} {i}")
                          for i in range(n)], key)


def _vector(system, rid: str):
    from abstractmemory.records import resolve_digest_assertion

    return system.store.stored_vector(resolve_digest_assertion(system.store, rid).assertion_id)


def _strip(system):
    """Texts with `novec` embed fine from now on: what failed at formation can be embedded later."""
    def embed(texts, _orig=system.emb.embed_texts):
        return _orig([t.replace("novec", "late") for t in texts])
    system.emb.embed_texts = embed


def _run(system, **kw):
    kw.setdefault("cancelled", lambda: False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return C.embed_missing(system, scopes=SCOPES, owner_id=OWNER, **kw)


def test_the_unvectored_records_are_embedded_and_then_detected(kind, tmp_path) -> None:
    system = _open(kind, tmp_path)
    topic = _topic(system, 2, 10)
    ids = _novec(system, 3)
    assert all(_vector(system, r) is None for r in ids)
    before = {r: _vector(system, r) for r in topic}
    _strip(system)
    out = _run(system)
    assert out["embedded"] == sorted(ids) and out["skipped"] == [] and out["failed"] == [] and not out["cancelled"]
    assert all(_vector(system, r) is not None for r in ids)
    assert {r: _vector(system, r) for r in topic} == before  # vectored records untouched
    r = _pass(system)
    assert r["unvectored"] == [] and r["communities"] == 1 and r["detected"] == 13


def test_record_ids_narrows_it(kind, tmp_path) -> None:
    system = _open(kind, tmp_path)
    vec = _topic(system, 2, 2)
    ids = _novec(system, 3)
    _strip(system)
    out = _run(system, record_ids=[ids[1], vec[0], "ex:episode-nope"])
    assert out["embedded"] == [ids[1]] and out["reasons"][vec[0]] == "vectored"
    assert out["failed"] == [{"id": "ex:episode-nope", "reason": "unknown_record"}]
    assert _vector(system, ids[0]) is None and _vector(system, ids[2]) is None


def test_an_unavailable_embedder_is_skipped_never_raised(kind, tmp_path) -> None:
    system = _open(kind, tmp_path)
    ids = _novec(system, 3)
    system.emb.down = True
    system.emb.calls = 0
    out = _run(system)
    assert out["embedded"] == [] and out["skipped"] == sorted(ids)
    assert out["reasons"][sorted(ids)[0]].startswith("embedder_unavailable: RuntimeError")
    assert all(out["reasons"][r] == "embedder_unavailable" for r in sorted(ids)[1:])  # no second call per record
    assert system.emb.calls == 1
    assert all(_vector(system, r) is None for r in ids)


def test_a_pinless_store_is_pinned_at_its_first_vector(kind, tmp_path) -> None:
    system = _open(kind, tmp_path)
    ids = _novec(system, 2)
    assert system.store.embedding_pin() is None
    _strip(system)
    out = _run(system)
    assert out["embedded"] == sorted(ids)
    pin = system.store.embedding_pin()
    assert pin["dimension"] == 32 and pin["source"] == "first-write"


def test_no_embedder_is_skipped(kind, tmp_path) -> None:
    system = _open(kind, tmp_path)
    ids = _novec(system, 2)
    _topic(system, 2, 1)
    system.store._embedder = None
    out = _run(system)
    assert out["skipped"] == sorted(ids) and {out["reasons"][r] for r in ids} == {"no_embedder"}


def test_cancelled_mid_way_keeps_the_earlier_vectors(kind, tmp_path) -> None:
    system = _open(kind, tmp_path)
    ids = sorted(_novec(system, 4))
    _strip(system)
    asked = []

    def cancelled() -> bool:
        asked.append(1)
        return len(asked) > 2

    out = _run(system, cancelled=cancelled)
    assert out["cancelled"] and out["embedded"] == ids[:2] and out["skipped"] == ids[2:]
    assert {out["reasons"][r] for r in ids[2:]} == {"cancelled"}
    assert _vector(system, ids[0]) is not None and _vector(system, ids[3]) is None


def test_a_wrong_dimension_fails_and_is_never_written(kind, tmp_path) -> None:
    system = _open(kind, tmp_path)
    _topic(system, 2, 1)  # pins the store at 32 dimensions
    ids = _novec(system, 1)
    system.emb.embed_texts = lambda texts: [[0.1] * 8 for _ in texts]
    out = _run(system)
    assert out["failed"] == [{"id": ids[0], "reason": "dimension_mismatch"}] and out["embedded"] == []
    assert _vector(system, ids[0]) is None


def test_a_community_record_is_never_embedded_by_it(kind, tmp_path) -> None:
    system = _open(kind, tmp_path)
    _topic(system, 2, 6)
    _pass(system)
    [c] = C.community_records(system, scopes=SCOPES, owner_id=OWNER)
    out = _run(system, record_ids=[c.record_id])
    assert out["reasons"] == {c.record_id: "never_embedded"} and out["embedded"] == []


def test_each_vector_is_its_own_guarded_commit(kind, tmp_path) -> None:
    guard = Guard()
    system = _open(kind, tmp_path, guard=guard)
    _topic(system, 2, 1)  # the store is pinned: only the vectors commit below
    ids = sorted(_novec(system, 3))
    _strip(system)
    del guard.calls[:]
    _run(system)
    assert guard.calls == ["communities.embed_missing"] * 3
    system.emb.down = True  # formed vector-less (the embedder down at formation)
    more = sorted(_form(system, [MemoryRecordInput(kind="episode", title=f"M{i}", digest=f"novec m {i}")
                                 for i in range(3)], "more"))
    system.emb.down = False
    calls = []

    def refuse_second(where: str) -> None:
        calls.append(where)
        if len(calls) == 2:
            raise RuntimeError("stopped by the operator")

    guard.refuse = None
    system.store._commit_guard = system.journal._commit_guard = refuse_second
    with pytest.raises(RuntimeError, match="stopped"):
        _run(system)
    assert _vector(system, more[0]) is not None and _vector(system, more[1]) is None
    assert ids
