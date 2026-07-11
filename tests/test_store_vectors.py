"""Native vector support parity: SQLiteTripleStore mirrors the InMemory
reference semantics exactly (a2a 0003 — the entity-home pairing). One test
suite, both stores, same expectations; plus the SQLite-only durability and
in-place-upgrade paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

import pytest

from abstractmemory import InMemoryTripleStore, SQLiteTripleStore, TripleAssertion, TripleQuery

SCOPE = "session"
OWNER = "s1"


class TopicEmbedder:
    """Deterministic 3-dim stub: axis by topic keyword; counts calls."""

    def __init__(self) -> None:
        self.calls: List[List[str]] = []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        out = []
        for t in texts:
            low = str(t).lower()
            if "museum" in low:
                out.append([1.0, 0.0, 0.0])
            elif "gallery" in low:
                out.append([0.5, 0.5, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out


def _assertion(aid: str, s: str, p: str, o: str, t: int, **attrs: Any) -> TripleAssertion:
    return TripleAssertion(subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
                           observed_at=f"2026-07-05T10:{t:02d}:00.000000+00:00",
                           attributes=dict(attrs), assertion_id=aid)


@pytest.fixture(params=["memory", "sqlite"])
def store_factory(request: pytest.FixtureRequest, tmp_path: Path):
    """Factory so tests control the embedder per construction (and reopen)."""
    if request.param == "memory":
        instances = {}

        def make(embedder=None):
            # In-memory "reopen" = same instance (no persistence claim).
            if "store" not in instances or embedder is not None:
                instances.setdefault("store", InMemoryTripleStore(embedder=embedder))
                instances["store"]._embedder = embedder
            return instances["store"]

        make.durable = False
        return make

    def make(embedder=None):
        return SQLiteTripleStore(tmp_path / "kg.sqlite3", embedder=embedder)

    make.durable = True
    return make


def test_embed_on_add_and_query_text_end_to_end(store_factory) -> None:
    emb = TopicEmbedder()
    store = store_factory(embedder=emb)
    store.add([
        _assertion("v-1", "bob", "toured", "museum", 1),
        _assertion("v-2", "dave", "visited", "gallery", 2),
        _assertion("v-3", "alice", "wrote", "report", 3),
    ])
    hits = store.query(TripleQuery(query_text="museum", scope=SCOPE, limit=2))
    assert [h.assertion_id for h in hits] == ["v-1", "v-2"]  # score desc, limit honored
    assert hits[0].attributes["_retrieval"]["score"] == pytest.approx(1.0)
    assert hits[0].attributes["_retrieval"]["metric"] == "cosine"
    assert hits[1].attributes["_retrieval"]["score"] == pytest.approx(0.7071, abs=1e-3)

    # query_vector accepted directly (no embedder call needed at query time).
    calls_before = len(emb.calls)
    direct = store.query(TripleQuery(query_vector=(1.0, 0.0, 0.0), scope=SCOPE, limit=1))
    assert [h.assertion_id for h in direct] == ["v-1"]
    assert len(emb.calls) == calls_before

    # min_score filters before ranking.
    strict = store.query(TripleQuery(query_text="museum", scope=SCOPE, min_score=0.9, limit=10))
    assert [h.assertion_id for h in strict] == ["v-1"]
    store.close()


def test_edge_assertions_never_embedded(store_factory) -> None:
    emb = TopicEmbedder()
    store = store_factory(embedder=emb)
    store.add([
        _assertion("d-1", "ex:a", "dcterms:abstract", "museum digest", 1,
                   literal=True, record_kind="episode", title="A"),
        _assertion("e-1", "ex:a", "supports", "ex:b", 2, record_edge=True),
    ])
    embedded_texts = [t for batch in emb.calls for t in batch]
    assert len(embedded_texts) == 1  # the digest only; the edge is structure
    hits = store.query(TripleQuery(query_vector=(1.0, 0.0, 0.0), scope=SCOPE, limit=10))
    assert [h.assertion_id for h in hits] == ["d-1"]  # edge row has no vector
    store.close()


def test_vectorless_rows_skipped_not_scored(store_factory) -> None:
    """Rows added while NO embedder was configured stay vectorless: vector
    queries skip them (the vector channel labels that degradation at
    recall — store semantics mirror InMemory: silent skip here)."""
    plain = store_factory(embedder=None)
    plain.add([_assertion("old-1", "bob", "toured", "museum", 1)])
    if store_factory.durable:
        plain.close()
    emb = TopicEmbedder()
    store = store_factory(embedder=emb)
    store.add([_assertion("new-1", "carol", "loves", "museum tours", 2)])

    hits = store.query(TripleQuery(query_text="museum", scope=SCOPE, limit=10))
    assert [h.assertion_id for h in hits] == ["new-1"]  # old row honestly absent
    # Both rows still exist structurally (the upgrade lost nothing).
    assert {a.assertion_id for a in store.query(TripleQuery(scope=SCOPE, limit=10))} == {"old-1", "new-1"}
    store.close()


def test_sqlite_vectors_survive_reopen(tmp_path: Path) -> None:
    """Persistence: vectors are stored (JSON column), not cached — a fresh
    process scores rows written by the previous one."""
    path = tmp_path / "kg.sqlite3"
    first = SQLiteTripleStore(path, embedder=TopicEmbedder())
    first.add([_assertion("v-1", "bob", "toured", "museum", 1),
               _assertion("v-3", "alice", "wrote", "report", 3)])
    first.close()

    reopened = SQLiteTripleStore(path, embedder=TopicEmbedder())
    hits = reopened.query(TripleQuery(query_text="museum", scope=SCOPE, min_score=0.9, limit=10))
    assert [h.assertion_id for h in hits] == ["v-1"]
    # query_vector works even without an embedder on the reopened handle.
    vectorless_handle = SQLiteTripleStore(path)
    direct = vectorless_handle.query(TripleQuery(query_vector=(1.0, 0.0, 0.0),
                                                 scope=SCOPE, min_score=0.9, limit=10))
    assert [h.assertion_id for h in direct] == ["v-1"]
    reopened.close()
    vectorless_handle.close()


def test_sqlite_in_place_upgrade_of_pre_vector_home(tmp_path: Path) -> None:
    """A home created BEFORE native vectors (no embedding column) upgrades
    in place on open — same memory.sqlite3, zero migration story: old rows
    stay vectorless, new rows score."""
    import sqlite3 as _sqlite3
    path = tmp_path / "memory.sqlite3"
    # Old-schema fixture: the pre-vector table shape, one legacy row.
    conn = _sqlite3.connect(str(path))
    conn.execute(
        """CREATE TABLE triples (
          assertion_id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL,
          object TEXT NOT NULL, scope TEXT NOT NULL, owner_id TEXT, observed_at TEXT NOT NULL,
          valid_from TEXT, valid_until TEXT, confidence REAL,
          provenance_json TEXT, attributes_json TEXT, text TEXT)"""
    )
    conn.execute(
        "INSERT INTO triples VALUES ('legacy-1','bob','toured','museum','session','s1',"
        "'2026-07-05T10:01:00.000000+00:00',NULL,NULL,NULL,'{}','{}','bob toured museum')"
    )
    conn.commit()
    conn.close()

    store = SQLiteTripleStore(path, embedder=TopicEmbedder())  # ALTER TABLE on open
    store.add([_assertion("fresh-1", "carol", "loves", "museum tours", 2)])
    hits = store.query(TripleQuery(query_text="museum", scope=SCOPE, limit=10))
    assert [h.assertion_id for h in hits] == ["fresh-1"]     # legacy row vectorless
    structural = store.query(TripleQuery(scope=SCOPE, limit=10))
    assert {a.assertion_id for a in structural} == {"legacy-1", "fresh-1"}
    store.close()


def test_scoring_parity_between_stores(tmp_path: Path) -> None:
    """The two stores rank identical data identically (shared
    vector_scoring module) — and REFUSE identically: a dimension-mismatched
    query vector raises on both (M1 pin guard; the pre-pin behavior was the
    silent min-prefix overlap 0014 documented as confident garbage)."""
    import pytest

    emb_a, emb_b = TopicEmbedder(), TopicEmbedder()
    mem = InMemoryTripleStore(embedder=emb_a)
    lite = SQLiteTripleStore(tmp_path / "kg.sqlite3", embedder=emb_b)
    data = [
        _assertion("v-1", "bob", "toured", "museum", 1),
        _assertion("v-2", "dave", "visited", "gallery", 2),
        _assertion("v-3", "alice", "wrote", "report", 3),
    ]
    mem.add(list(data))
    lite.add(list(data))
    for q in (
        TripleQuery(query_text="museum", scope=SCOPE, limit=10),
        TripleQuery(query_vector=(0.5, 0.5, 0.0), scope=SCOPE, limit=10),  # pinned dim (3)
        TripleQuery(query_text="museum", scope=SCOPE, min_score=0.5, limit=10),
    ):
        mem_hits = [(h.assertion_id, round(h.attributes["_retrieval"]["score"], 9))
                    for h in mem.query(q)]
        lite_hits = [(h.assertion_id, round(h.attributes["_retrieval"]["score"], 9))
                     for h in lite.query(q)]
        assert mem_hits == lite_hits
    # Dimension-mismatch parity: both stores refuse loudly, same contract.
    mismatched = TripleQuery(query_vector=(0.5, 0.5, 0.0, 0.9), scope=SCOPE, limit=10)
    for store in (mem, lite):
        with pytest.raises(ValueError, match="no silent mixing"):
            store.query(mismatched)
    lite.close()