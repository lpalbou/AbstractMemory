from __future__ import annotations

import builtins

import pytest

from abstractmemory import LanceDBTripleStore, TripleAssertion, TripleQuery


def test_lancedb_missing_dependency_raises_helpful_error(tmp_path, monkeypatch):
    # Even if LanceDB is installed in the current environment, we want to keep a
    # stable contract test that the error message is actionable when it isn't.
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "lancedb":
            raise ModuleNotFoundError("No module named 'lancedb'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(ImportError) as e:
        LanceDBTripleStore(tmp_path / "kg")
    assert "lancedb" in str(e.value).lower()


def test_lancedb_persists_across_reopen(tmp_path):
    try:
        import lancedb  # noqa: F401
    except Exception:
        pytest.skip("lancedb not installed")

    store_path = tmp_path / "kg"

    store = LanceDBTripleStore(store_path)
    store.add(
        [
            TripleAssertion(
                subject="e:scrooge",
                predicate="is_a",
                object="Person",
                scope="session",
                owner_id="sess-1",
                observed_at="2026-01-01T00:00:00+00:00",
                attributes={"evidence_quote": "Scrooge"},
            )
        ]
    )
    store.close()

    store2 = LanceDBTripleStore(store_path)
    out = store2.query(TripleQuery(subject="e:scrooge", scope="session", owner_id="sess-1", limit=10))
    assert len(out) == 1
    assert out[0].predicate == "is_a"


def test_lancedb_query_text_requires_embedder_without_fallback(tmp_path):
    try:
        import lancedb  # noqa: F401
    except Exception:
        pytest.skip("lancedb not installed")

    store = LanceDBTripleStore(tmp_path / "kg")
    store.add(
        [
            TripleAssertion(
                subject="e:marley",
                predicate="died",
                object="1836-12",
                scope="global",
                owner_id=None,
                observed_at="2026-01-01T00:00:00+00:00",
                attributes={"original_context": "Mr. Marley has been dead these seven years"},
            )
        ]
    )
    with pytest.raises(ValueError) as e:
        store.query(TripleQuery(query_text="seven years", scope="global", limit=10))
    assert "embedder" in str(e.value).lower()


def test_lancedb_query_text_vector_search_with_embedder(tmp_path):
    try:
        import lancedb  # noqa: F401
    except Exception:
        pytest.skip("lancedb not installed")

    class _DummyEmbedder:
        def embed_texts(self, texts):
            # Deterministic, cheap vectors (no external calls).
            # Encode one salient concept to make nearest-neighbor assertions stable.
            out = []
            for t in texts:
                t2 = (t or "").lower()
                if "marley" in t2:
                    out.append([1.0, 0.0, 0.0])
                elif "scrooge" in t2:
                    out.append([0.0, 1.0, 0.0])
                else:
                    out.append([0.0, 0.0, 1.0])
            return out

    store = LanceDBTripleStore(tmp_path / "kg", embedder=_DummyEmbedder())
    store.add(
        [
            TripleAssertion(
                subject="e:scrooge",
                predicate="is_a",
                object="person",
                scope="global",
                observed_at="2026-01-01T00:00:00+00:00",
            ),
            TripleAssertion(
                subject="e:marley",
                predicate="is_a",
                object="person",
                scope="global",
                observed_at="2026-01-02T00:00:00+00:00",
            ),
        ]
    )

    out = store.query(TripleQuery(query_text="marley", scope="global", limit=5))
    assert len(out) >= 1
    assert out[0].subject == "e:marley"

def test_lancedb_query_text_min_score_filters_results(tmp_path):
    try:
        import lancedb  # noqa: F401
    except Exception:
        pytest.skip("lancedb not installed")

    class _DummyEmbedder:
        def embed_texts(self, texts):
            out = []
            for t in texts:
                t2 = (t or "").lower()
                if "marley" in t2:
                    out.append([1.0, 0.0])
                elif "scrooge" in t2:
                    out.append([0.0, 1.0])
                else:
                    out.append([0.0, 0.0])
            return out

    store = LanceDBTripleStore(tmp_path / "kg", embedder=_DummyEmbedder())
    store.add(
        [
            TripleAssertion(subject="e:scrooge", predicate="is_a", object="person", scope="global", attributes={"evidence_quote": "scrooge"}),
            TripleAssertion(subject="e:marley", predicate="is_a", object="person", scope="global", attributes={"evidence_quote": "marley"}),
        ]
    )

    out = store.query(TripleQuery(query_text="marley", scope="global", limit=10, min_score=0.5))
    assert len(out) == 1
    assert out[0].subject == "e:marley"
    attrs = out[0].attributes
    assert isinstance(attrs, dict)
    ret = attrs.get("_retrieval")
    assert isinstance(ret, dict)
    assert ret.get("metric") == "cosine"
    assert ret.get("score") is not None


def test_where_clause_builder_escapes_and_compares():
    from abstractmemory.lancedb_store import _build_where_clause

    q = TripleQuery(
        subject="e:alice",
        predicate="says",
        object="bob's car",
        scope="session",
        since="2026-01-01T00:00:00+00:00",
        until="2026-02-01T00:00:00+00:00",
        active_at="2026-01-15T00:00:00+00:00",
    )
    where = _build_where_clause(q)
    assert "lower(subject) = 'e:alice'" in where
    assert "lower(predicate) = 'says'" in where
    assert "lower(object) = 'bob''s car'" in where  # escaped
    assert "scope = 'session'" in where
    assert "observed_at >= '2026-01-01T00:00:00+00:00'" in where
    assert "observed_at <= '2026-02-01T00:00:00+00:00'" in where
    assert "valid_from" in where and "valid_until" in where
