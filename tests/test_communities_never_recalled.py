"""A community is engine state, never a memory (Fable review D4, 2026-11-10): formed WITHOUT a vector, kept
vector-less through its authored words and a re-embed, and never returned by recall, a probe, a vector query or the
keyword index. Both substrate pairs.

Why it matters: the briefing (member titles and summaries) is a near-perfect attractor for any query on its topic; an
embedded, recallable community would carry a whole topic packet into prompts uninvited.

MUTATION LIST (scratch copy untracked/communities/mut; all red, source restored): N1 the SQLite and in-memory stores
embed every non-edge (no kind rule); N2 an authored summary re-embeds a community; N3 reembed embeds every non-edge;
N4 a community record is not bookkeeping (it reaches recall shelves and the keyword index).
"""

from __future__ import annotations

import warnings

import pytest

np = pytest.importorskip("numpy")

from abstractmemory import ReconstructConfig, Stimulus  # noqa: E402
from abstractmemory import communities as C  # noqa: E402
from abstractmemory.reembed import reembed_store  # noqa: E402
from abstractmemory.store import TripleQuery  # noqa: E402
from abstractmemory.understanding import retitle, rewrite_digest  # noqa: E402

from test_communities import MODEL, OWNER, READER, SCOPE, SCOPES, Embedder, _open, _pass, _topic  # noqa: E402

LIVE = ("pending", "deferred", "leased")


@pytest.fixture(params=["memory", "sqlite"])
def kind(request):
    return request.param


def _home(kind, tmp_path, **kw):
    system = _open(kind, tmp_path, **kw)
    for t in (1, 2):
        _topic(system, t, 10)
    return system


def _communities(system):
    return C.community_records(system, scopes=SCOPES, owner_id=OWNER)


def _is_community(system, record_id: str) -> bool:
    from abstractmemory.records import resolve_digest_assertion

    a = resolve_digest_assertion(system.store, record_id)
    return a is not None and (a.attributes or {}).get("record_kind") == "community"


def test_a_community_is_formed_without_a_vector(kind, tmp_path) -> None:
    system = _home(kind, tmp_path)
    calls = system.emb.calls
    r = _pass(system)
    assert r["written"] == 2 and system.emb.calls == calls  # no embed call for the communities
    for c in _communities(system):
        assert system.store.stored_vector(c.assertion_id) is None
        assert c.attrs["bookkeeping"] is True


def test_its_authored_words_leave_it_vectorless(kind, tmp_path) -> None:
    system = _home(kind, tmp_path)
    _pass(system, author=None)  # pending: the drainer writes its title and summary later
    c = _communities(system)[0]
    tasks = {t["kind"]: t["task_id"] for t in system.tasks.tasks(target_id=c.record_id) if t["status"] in LIVE}
    sources = [{"kind": "artifact", "artifact_id": "drain-1"}]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out = rewrite_digest(system, c.record_id, text="Memories about one subject.", author=MODEL, reader=READER,
                             sources=sources, cause="formation", expected_version=0, task_id=tasks["digest.author"])
        assert out["applied"], out
        out = retitle(system, c.record_id, title="One subject", author=MODEL, reader=READER, sources=sources,
                      cause="formation", expected_version=0, task_id=tasks["title.author"])
        assert out["applied"], out
    [again] = [x for x in _communities(system) if x.key == c.key]
    assert again.title == "One subject" and system.store.stored_vector(again.assertion_id) is None


def test_a_reembed_leaves_it_vectorless(kind, tmp_path) -> None:
    system = _home(kind, tmp_path)
    _pass(system)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        reembed_store(system, embedder=Embedder(), owner_id=OWNER, model_id="fake-topic-32")
    for c in _communities(system):
        assert system.store.stored_vector(c.assertion_id) is None
        assert all(system.store.stored_vector(a.assertion_id) is not None
                   for a in system.store.query(TripleQuery(predicate="dcterms:abstract", limit=0))
                   if (a.attributes or {}).get("record_kind") == "episode")


def test_recall_never_returns_a_community(kind, tmp_path) -> None:
    system = _home(kind, tmp_path, task_queue=True)
    _pass(system)
    for c in _communities(system):
        for cue in (c.title, c.digest, "topic-1 topic-2 again"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                res = system.reconstruct(Stimulus(cue_text=cue), scopes=SCOPES, journal=False)
                probe = system.probe(Stimulus(cue_text=cue), scopes=SCOPES, reason="test: topics stay out",
                                     journal=False)
            assert res.handles, "recall found nothing at all: the check would be vacuous"
            assert not [h for h in res.handles if _is_community(system, h.record_id)]
            assert not [h for h in probe.hits if _is_community(system, getattr(h, "record_id", ""))]


def test_keyword_discovery_never_returns_a_community(tmp_path) -> None:
    from abstractmemory import MemorySystem

    system = _home("sqlite", tmp_path)
    _pass(system, author=None)
    c = _communities(system)[0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        # "belong"/"together" are only in the communities' briefing; "again" is in every episode
        hits = system.store.query_keywords(["belong", "together"], scope=SCOPE, owner_id=OWNER, limit=100)
        control = system.store.query_keywords(["again"], scope=SCOPE, owner_id=OWNER, limit=100)
        found = MemorySystem(store=system.store, journal=system.journal, task_queue=True,
                             reconstruct_config=ReconstructConfig(keyword_discovery=True)).reconstruct(
            Stimulus(cue_text="A topic of this memory belong together"), scopes=SCOPES, journal=False)
    assert c.digest.startswith("A topic of this memory") and "belong together" in c.digest
    assert len(control) == 20 and hits == []
    assert not [h for h in found.handles if _is_community(system, h.record_id)]


def test_a_vector_query_never_returns_a_community(kind, tmp_path) -> None:
    system = _home(kind, tmp_path)
    _pass(system)
    for c in _communities(system):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            rows = system.store.query(TripleQuery(query_text=c.title, scope=SCOPE, owner_id=OWNER, limit=50))
        assert rows and not [a for a in rows if (a.attributes or {}).get("record_kind") == "community"]
