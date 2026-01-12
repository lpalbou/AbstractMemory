from __future__ import annotations

from datetime import datetime, timedelta, timezone

from abstractmemory import SQLiteTripleStore, TripleAssertion, TripleQuery


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def test_add_and_query_roundtrip(tmp_path):
    store = SQLiteTripleStore(tmp_path / "kg.sqlite3")
    try:
        t0 = datetime.now(timezone.utc) - timedelta(hours=1)
        a = TripleAssertion(
            subject="e:openai",
            predicate="creates",
            object="e:gpt4",
            scope="global",
            observed_at=_iso(t0),
            confidence=0.9,
            provenance={"span_id": "art_123"},
            attributes={"kind": "extracted"},
        )
        store.add([a])

        rows = store.query(TripleQuery(subject="e:openai", predicate="creates", scope="global"))
        assert len(rows) == 1
        assert rows[0].subject == "e:openai"
        assert rows[0].predicate == "creates"
        assert rows[0].object == "e:gpt4"
        assert rows[0].scope == "global"
        assert rows[0].confidence == 0.9
        assert rows[0].provenance.get("span_id") == "art_123"
        assert rows[0].attributes.get("kind") == "extracted"
    finally:
        store.close()


def test_time_filters_and_active_at(tmp_path):
    store = SQLiteTripleStore(tmp_path / "kg.sqlite3")
    try:
        now = datetime.now(timezone.utc)
        a1 = TripleAssertion(
            subject="e:alice",
            predicate="lives_in",
            object="e:paris",
            scope="session",
            observed_at=_iso(now - timedelta(days=2)),
            valid_from=_iso(now - timedelta(days=10)),
            valid_until=_iso(now - timedelta(days=1)),
        )
        a2 = TripleAssertion(
            subject="e:alice",
            predicate="lives_in",
            object="e:london",
            scope="session",
            observed_at=_iso(now - timedelta(hours=12)),
            valid_from=_iso(now - timedelta(days=1)),
            valid_until=None,
        )
        store.add([a1, a2])

        # observed_at window: only the recent assertion
        recent = store.query(TripleQuery(subject="e:alice", since=_iso(now - timedelta(days=1))))
        assert len(recent) == 1
        assert recent[0].object == "e:london"

        # active_at view (validity window) at 36h ago -> a1 should be active
        active_old = store.query(
            TripleQuery(subject="e:alice", active_at=_iso(now - timedelta(hours=36)), order="asc")
        )
        assert len(active_old) == 1
        assert active_old[0].object == "e:paris"

        # active_at now -> a2 should be active
        active_now = store.query(TripleQuery(subject="e:alice", active_at=_iso(now)))
        assert len(active_now) == 1
        assert active_now[0].object == "e:london"
    finally:
        store.close()

