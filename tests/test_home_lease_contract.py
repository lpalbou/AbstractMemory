"""M2 — the per-home lease contract from the MAINTENANCE seat (plan item 1).

The lease primitive is runtime-owned (GW-A spec: the loop process cannot
import the gateway, and the ENGINE never imports the runtime — the import
boundary stands). These tests pin the COMPOSITION the plan requires:
maintenance passes (reembed, sleep) are writers like any other — they run
UNDER the lease their CALLER acquires (gateway maintenance verb / runtime
CLI), refuse loudly when another window holds the home, and keep the
engine-side count-guard as the backstop for writers that never honored the
lease at all.

MIGRATION-TOLERANT IMPORT (c357 owner intent): runtime is re-homing the
primitive from identity/lease.py (acquire_home_lease, HomeLeaseHeld) to a
neutral spelling in storage/lease.py (acquire_directory_lease — one generic
one-writer-per-directory mechanism; the identity spelling dies before
release). This suite resolves the NEW spelling first and falls back to the
old, and asserts the refusal by TYPE + holder metadata, never by prose —
the refusal wording is diagnostics and is changing with the re-home (the
exact "pin entity dress by accident" trap my c356 note named).

Skipped wholesale when abstractruntime is not importable (the engine's own
suite must not hard-depend on a sibling checkout) and on platforms without
flock — both skips are labeled, never silent passes.
"""

from __future__ import annotations

import importlib
from typing import Any, List, Sequence

import pytest

pytest.importorskip(
    "abstractruntime",
    reason="M2 contract needs the sibling abstractruntime checkout (lease primitive)",
)
pytest.importorskip("fcntl", reason="the lease's kernel exclusion is POSIX flock")


def _resolve_lease_module():
    """New neutral home first (storage.lease), legacy home second — the
    migration-window rule from c357: never two spellings in OUR code, but
    tolerate whichever single spelling the sibling checkout ships."""
    for module_name in ("abstractruntime.storage.lease", "abstractruntime.identity.lease"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    pytest.skip("no lease module in the sibling abstractruntime checkout (storage.lease / identity.lease)")


lease_module = _resolve_lease_module()


def _resolve(*names: str):
    for name in names:
        found = getattr(lease_module, name, None)
        if found is not None:
            return found
    raise AttributeError(
        f"lease module {lease_module.__name__} exposes none of {names} — "
        "the c357 re-home changed more than the agreed spellings; re-sync the contract"
    )


LeaseHeld = _resolve("DirectoryLeaseHeld", "HomeLeaseHeld", "LeaseHeld")
acquire_lease = _resolve("acquire_directory_lease", "acquire_home_lease")
read_lease = _resolve("read_directory_lease", "read_home_lease")

from abstractmemory import (  # noqa: E402  (after importorskip by design)
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    reembed_store,
    sleep_pass,
)
from abstractmemory.records import MemoryRecordInput  # noqa: E402

SCOPE = "life"
OWNER = "entity:test"
SCOPES = [(SCOPE, OWNER)]


class DimEmbedder:
    def __init__(self, model: str, dimension: int) -> None:
        self.model = model
        self._dimension = int(dimension)

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        return [[float((sum(ord(c) for c in str(t)) % 89) + 1)] + [1.0] * (self._dimension - 1)
                for t in texts]


def _home(tmp_path) -> tuple:
    home = tmp_path / "home"
    home.mkdir()
    store = SQLiteTripleStore(
        home / "memory.sqlite3", embedder=DimEmbedder("test-embed-a", 4),
        embedding_pin={"model_id": "test-embed-a", "dimension": 4})
    journal = SQLiteJournal(home / "memory.sqlite3")
    system = MemorySystem(store=store, journal=journal)
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Harbor walk",
                           digest="Walked the harbor at noon.")],
        scope=SCOPE, owner_id=OWNER, idempotency_key="l-1")
    return home, store, journal, system, gid


def test_maintenance_refused_while_another_window_holds(tmp_path) -> None:
    """A visit window holds the home -> the maintenance writer REFUSES
    loudly (the lease-held error naming the holder), never waits, never
    writes. Asserted by TYPE + holder metadata, not refusal prose (the
    wording is diagnostics and neutralizes with the c357 re-home)."""
    home, store, journal, system, _ = _home(tmp_path)
    with acquire_lease(home, holder="visit-host", session_id="chat-1"):
        with pytest.raises(LeaseHeld) as excinfo:
            acquire_lease(home, holder="maintenance")
        assert excinfo.value.holder and excinfo.value.holder["holder"] == "visit-host"
        # Nothing moved: the refusal happened before any engine call.
        assert store.embedding_pin()["model_id"] == "test-embed-a"
    store.close()
    journal.close()


def test_reembed_and_sleep_run_under_the_maintenance_lease(tmp_path) -> None:
    """The M1b/phase-1 composition the plan names: maintenance passes run
    inside ONE maintenance window; the lease releases at pass end (per-pass
    granularity, D1) and the home reads free afterwards."""
    home, store, journal, system, _ = _home(tmp_path)
    with acquire_lease(home, holder="maintenance", run_id="reembed-1") as lease:
        assert lease.acquired
        result = reembed_store(system, embedder=DimEmbedder("test-embed-b", 6), owner_id=OWNER)
        assert result["vectored"] >= 1
        sleep = sleep_pass(system, scopes=SCOPES, owner_id=OWNER, report_only=True)
        assert sleep["maintenance"]["report"]["counts"]["records"] >= 1
        # While held: a second window refuses (the exclusion is real).
        with pytest.raises(LeaseHeld):
            acquire_lease(home, holder="dream")
    state = read_lease(home)
    assert state is not None and state["held"] is False  # released at pass end
    assert store.embedding_pin()["model_id"] == "test-embed-b"  # the pass really ran
    store.close()
    journal.close()


def test_backstop_fires_for_writers_that_never_took_the_lease(tmp_path) -> None:
    """The lease is advisory for a writer that never calls it (three
    processes, one file — the plan's honest premise); the engine's
    count-guard stays the backstop: a mid-pass write from a lease-ignoring
    writer aborts the swap with nothing written, even though the pass
    itself held the lease correctly."""
    home, store, journal, system, _ = _home(tmp_path)

    class RogueWriterEmbedder(DimEmbedder):
        """Simulates a writer that ignored the lease, mid-pass."""

        def __init__(self) -> None:
            super().__init__("test-embed-b", 4)
            self._fired = False

        def embed_texts(self, texts):
            if not self._fired:
                self._fired = True
                system.remember_many(
                    [MemoryRecordInput(kind="episode", title="Rogue write",
                                       digest="A writer that never took the lease.")],
                    scope=SCOPE, owner_id=OWNER, idempotency_key="rogue-1")
            return super().embed_texts(texts)

    with acquire_lease(home, holder="maintenance"):
        with pytest.raises(RuntimeError, match="exclusive-writer guarantee"):
            reembed_store(system, embedder=RogueWriterEmbedder(), owner_id=OWNER)
    assert store.embedding_pin()["model_id"] == "test-embed-a"  # swap never landed
    store.close()
    journal.close()
