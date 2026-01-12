from __future__ import annotations

import pytest

from abstractmemory import LanceDBTripleStore, TripleQuery


def test_lancedb_missing_dependency_raises_helpful_error(tmp_path):
    # Our CI/dev environments may not have LanceDB installed by default.
    # The contract is that the package still imports, but instantiation raises a clear error.
    with pytest.raises(ImportError) as e:
        LanceDBTripleStore(tmp_path / "kg")
    assert "lancedb" in str(e.value).lower()


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
    assert "subject = 'e:alice'" in where
    assert "predicate = 'says'" in where
    assert "object = 'bob''s car'" in where  # escaped
    assert "scope = 'session'" in where
    assert "observed_at >= '2026-01-01T00:00:00+00:00'" in where
    assert "observed_at <= '2026-02-01T00:00:00+00:00'" in where
    assert "valid_from" in where and "valid_until" in where

