"""A community is engine state, never a memory (Fable review D4, 2026-11-10): formed WITHOUT a vector, kept
vector-less through its authored words and a re-embed, and never returned by recall, a probe, a vector query or the
keyword index. Both substrate pairs.

Why it matters: the briefing (member titles and summaries) is a near-perfect attractor for any query on its topic; an
embedded, recallable community would carry a whole topic packet into prompts uninvited.

THE CLOSED SET (Fable review M1 #1): every embed call site in `src/abstractmemory` (a call to an embedder's
`embed_texts`, or to a function that embeds what it is handed: `embedding_pin.embed_texts_degradable`,
`understanding._embed`) sits in a function that asks `canonical_text.never_embedded`, unless it embeds the reader's
query (`[<x>.query_text]` / `[<x>.cue_text]`). A new site without it fails `test_every_embed_site_asks_never_embedded`
by name; the scanner's own red cases are `test_the_closed_set_check_goes_red_on_an_unguarded_site`.

MUTATION LIST (scratch copy untracked/communities/mut; all red, source restored): N1 the SQLite and in-memory stores
embed every non-edge (no kind rule); N2 an authored summary re-embeds a community; N3 reembed embeds every non-edge;
N4 a community record is not bookkeeping (it reaches recall shelves and the keyword index). Fable review M1 (scratch
copy untracked/review-m1-wip/tree): D4a graph._sqlite_rows back on `is_record_edge`, D4b
lancedb_backend.prepare_rows back on `is_record_edge` (the closed set and the revision test both red).
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path

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


# ----------------------------------------------------------------------------------------------- the closed set

SRC = Path(C.__file__).resolve().parent
#: Functions that embed the texts they are handed: a call to one is an embed site (None: any module; else the module
#: the helper is local to). Their own bodies are not sites (their callers are).
WRAPPERS = {"embed_texts_degradable": None, "_embed": "understanding.py"}
QUERY_ATTRS = frozenset({"query_text", "cue_text"})


def _called(call: ast.Call) -> str:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""


def _is_wrapper(name: str, module: str) -> bool:
    return name in WRAPPERS and WRAPPERS[name] in (None, module)


def _names_never_embedded(fn: ast.AST) -> bool:
    return any((isinstance(n, ast.Name) and n.id.endswith("never_embedded"))
               or (isinstance(n, ast.Attribute) and n.attr.endswith("never_embedded")) for n in ast.walk(fn))


def _is_query(call: ast.Call) -> bool:
    return bool(call.args) and all(
        isinstance(a, ast.List) and len(a.elts) == 1 and isinstance(a.elts[0], ast.Attribute)
        and a.elts[0].attr in QUERY_ATTRS for a in call.args)


def embed_sites(source: str, module: str):
    """[(function, line, verdict)] for every embed call of one module: 'query' (the reader's query or cue text),
    'own' (inside an embedder's `embed_texts` or a wrapper's own body), 'guarded' (a function on the stack names
    never_embedded), 'unguarded' (the leak this file exists to catch)."""
    out = []

    def visit(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, stack + [child])
                continue
            if isinstance(child, ast.Call):
                name = _called(child)
                if (name == "embed_texts" and isinstance(child.func, ast.Attribute)) or _is_wrapper(name, module):
                    fn = stack[-1].name if stack else "<module>"
                    if stack and (fn == "embed_texts" or _is_wrapper(fn, module)):
                        verdict = "own"
                    elif _is_query(child):
                        verdict = "query"
                    elif any(_names_never_embedded(f) for f in stack):
                        verdict = "guarded"
                    else:
                        verdict = "unguarded"
                    out.append((fn, child.lineno, verdict))
            visit(child, stack)

    visit(ast.parse(source), [])
    return out


def _all_sites():
    out = []
    for path in sorted(SRC.rglob("*.py")):
        module = path.relative_to(SRC).as_posix()
        out.extend((module, fn, line, verdict) for fn, line, verdict in embed_sites(path.read_text("utf-8"), module))
    return out


def test_every_embed_site_asks_never_embedded() -> None:
    sites = _all_sites()
    unguarded = [f"{m}:{line} in {fn}()" for m, fn, line, verdict in sites if verdict == "unguarded"]
    assert unguarded == [], ("these embed sites never ask canonical_text.never_embedded (a community they write "
                             f"would embed): {unguarded}")
    guarded = {(m, fn) for m, fn, _line, verdict in sites if verdict == "guarded"}
    assert guarded >= {  # the scan is not vacuous: every known write path is found, and found guarded
        ("sqlite_store.py", "_prepare_add"), ("in_memory_store.py", "_prepare_add"), ("graph/graph.py", "_sqlite_rows"),
        ("lancedb_store.py", "add"), ("graph/lancedb_backend.py", "prepare_rows"), ("reembed.py", "reembed_store"),
        ("communities.py", "embed_missing"), ("understanding.py", "_apply")}, sorted(guarded)
    assert sum(1 for *_x, verdict in sites if verdict == "query") >= 4


def test_the_closed_set_check_goes_red_on_an_unguarded_site() -> None:
    bad = "class S:\n    def add(self, rows):\n        return self._embedder.embed_texts([r.text for r in rows])\n"
    wrapped = "def rows(store, xs):\n    return embed_texts_degradable(store._embedder, xs, None)\n"
    good = ("def rows(store, xs):\n    keep = [x for x in xs if not _never_embedded(x)]\n"
            "    return embed_texts_degradable(store._embedder, keep, None)\n")
    query = "def query(self, q):\n    return self._embedder.embed_texts([q.query_text])[0]\n"
    helper = ("def _embed(store, text):\n    return store._embedder.embed_texts([text])\n"
              "def go(s):\n    _embed(s, 't')\n")
    assert embed_sites(bad, "x.py") == [("add", 3, "unguarded")]
    assert embed_sites(wrapped, "x.py") == [("rows", 2, "unguarded")]
    assert embed_sites(good, "x.py") == [("rows", 3, "guarded")]
    assert embed_sites(query, "x.py") == [("query", 2, "query")]
    assert embed_sites(helper, "understanding.py") == [("_embed", 2, "own"), ("go", 4, "unguarded")]


class _Recording:
    model = "fake-recording-64"

    def __init__(self) -> None:
        from graph_support import FakeEmbedder

        self.inner, self.texts = FakeEmbedder(), []

    def embed_texts(self, texts):
        self.texts.extend(texts)
        return self.inner.embed_texts(texts)


@pytest.mark.parametrize("backend", ["sqlite", "memory", "lancedb"])
def test_a_community_asserted_through_a_revision_is_never_embedded(backend, tmp_path) -> None:
    """MemoryGraph.apply_revision validates no record kind and is reachable from the runtime facade and the gateway's
    memory route: a `community` digest it asserts gets no vector on any connector; the ordinary claim beside it does
    (the check is not vacuous)."""
    from graph_support import claim, open_home, rev

    if backend == "lancedb":
        pytest.importorskip("lancedb")
    emb = _Recording()
    home = open_home(tmp_path, backend, embedder=emb)
    try:
        attrs = {"record_kind": "community", "community_key": "ex:community-0123456789ab", "bookkeeping": True,
                 "members": [{"id": "ex:a", "via": "detected", "since_seq": 1}]}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            home.graph.apply_revision(rev("r-community", claim(
                "a-community", s="ex:community-0123456789ab", p="dcterms:abstract",
                o="A topic of this memory: briefing words", attributes=attrs), claim("a-claim")))
        assert any("ex:dana" in t for t in emb.texts), emb.texts
        assert not [t for t in emb.texts if "briefing words" in t], emb.texts
        if hasattr(home.store, "stored_vector"):
            assert home.store.stored_vector("a-community") is None
            assert home.store.stored_vector("a-claim") is not None
    finally:
        home.close()
