"""Embedding-space pin + reembed guards (plan item 3: M1 + M1b).

The invariant under test: NO SILENT MIXING OF EMBEDDING SPACES. Pins are a
BIRTH choice (creation), first-write pinning survives only as the labeled
fallback for pre-existing homes, writes refuse wrong-space vectors with zero
rows landed, reads degrade loudly (the vector channel's #FALLBACK), and the
reembed repair is all-or-nothing with the pin updated last — truth (digests,
journal, counts) untouched.
"""

from __future__ import annotations

import warnings as warnings_module
from typing import Any, List, Sequence

import pytest

from abstractmemory import read_embedding_pin


def test_read_embedding_pin_is_a_pure_nonmutating_peek(tmp_path):
    """The resolution read of the entity-embedding-config contract
    (maintainer ruling 2026-07-11): doors read the declaration BEFORE
    constructing an embedder — without mutating the file. Tolerant of
    every absence; byte-identical file before/after is the point."""
    from abstractmemory import SQLiteTripleStore

    missing = tmp_path / "nope.sqlite3"
    assert read_embedding_pin(missing) is None
    assert not missing.exists()  # the peek can never create the file

    # A non-store sqlite file (no meta table) -> None, untouched.
    import sqlite3 as _sq
    other = tmp_path / "other.sqlite3"
    _sq.connect(other).execute("CREATE TABLE t (x)").connection.close()
    before = other.read_bytes()
    assert read_embedding_pin(other) is None
    assert other.read_bytes() == before  # non-mutating

    # A pinned store -> equals the open handle's own read.
    pinned = tmp_path / "pinned.sqlite3"
    store = SQLiteTripleStore(
        pinned, embedding_pin={"model_id": "text-embedding-qwen3-embedding-0.6b",
                               "dimension": 1024})
    expected = store.embedding_pin()
    store.close()
    peeked = read_embedding_pin(pinned)
    assert peeked == expected
    assert peeked["model_id"] == "text-embedding-qwen3-embedding-0.6b"

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
    Stimulus,
    build_pin,
    reembed_store,
)
from abstractmemory.records import MemoryRecordInput
from abstractmemory.store import TripleQuery

SCOPE = "life"
OWNER = "entity:test"
SCOPES = [(SCOPE, OWNER)]


class DimEmbedder:
    """Deterministic test embedder with a declared model id + dimension."""

    def __init__(self, model: str, dimension: int) -> None:
        self.model = model
        self._dimension = int(dimension)

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            seed = float((sum(ord(c) for c in str(t)) % 97) + 1)
            vector = [seed] + [1.0] * (self._dimension - 1)
            out.append(vector[: self._dimension])
        return out


def _stores(tmp_path, **kwargs) -> List[Any]:
    return [
        InMemoryTripleStore(**kwargs),
        SQLiteTripleStore(tmp_path / f"pin-{len(list(tmp_path.iterdir()))}.sqlite3", **kwargs),
    ]


def _system(store, tmp_path=None):
    if isinstance(store, SQLiteTripleStore):
        journal = SQLiteJournal(store._path)
    else:
        with warnings_module.catch_warnings():
            warnings_module.simplefilter("ignore", RuntimeWarning)
            journal = InMemoryJournal()
    return MemorySystem(store=store, journal=journal,
                        embedder=getattr(store, "_embedder", None))


def _remember(system, key: str, title: str, digest: str, **kw: Any) -> str:
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="episode", title=title, digest=digest, **kw)],
        scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


# ---------------------------------------------------------------------------
# M1: creation pin — birth choice, persisted, enforced
# ---------------------------------------------------------------------------


def test_creation_pin_persisted_and_survives_reopen(tmp_path) -> None:
    path = tmp_path / "home.sqlite3"
    pin = {"model_id": "test-embed-a", "dimension": 4}
    store = SQLiteTripleStore(path, embedding_pin=pin)
    stored = store.embedding_pin()
    assert stored["model_id"] == "test-embed-a" and stored["dimension"] == 4
    assert stored["source"] == "creation"
    store.close()

    reopened = SQLiteTripleStore(path)  # no embedder: vectorless reads OK
    again = reopened.embedding_pin()
    assert again["model_id"] == "test-embed-a" and again["dimension"] == 4
    reopened.close()


def test_conflicting_declared_pin_refused(tmp_path) -> None:
    path = tmp_path / "home.sqlite3"
    SQLiteTripleStore(path, embedding_pin={"model_id": "test-embed-a", "dimension": 4}).close()
    with pytest.raises(ValueError, match="no silent mixing"):
        SQLiteTripleStore(path, embedding_pin={"model_id": "test-embed-b", "dimension": 4})


def test_known_embedder_model_mismatch_refused_at_open(tmp_path) -> None:
    for store_kind in ("memory", "sqlite"):
        pin = {"model_id": "test-embed-a", "dimension": 4}
        wrong = DimEmbedder("test-embed-b", 4)
        with pytest.raises(ValueError, match="pinned to embedding model"):
            if store_kind == "memory":
                InMemoryTripleStore(embedder=wrong, embedding_pin=pin)
            else:
                SQLiteTripleStore(tmp_path / "open.sqlite3", embedder=wrong, embedding_pin=pin)


def test_wrong_dimension_write_refused_with_zero_rows(tmp_path) -> None:
    for store in _stores(tmp_path, embedder=DimEmbedder("test-embed-a", 3),
                         embedding_pin={"model_id": "test-embed-a", "dimension": 4}):
        system = _system(store)
        with pytest.raises(ValueError, match="pinned to dimension 4"):
            _remember(system, "w-1", "First", "A first memory.")
        assert store.query(TripleQuery(limit=0)) == []  # zero rows landed
        store.close()


def test_first_write_pin_is_the_labeled_fallback(tmp_path) -> None:
    for store in _stores(tmp_path, embedder=DimEmbedder("test-embed-a", 3)):
        system = _system(store)
        assert store.embedding_pin() is None  # legacy pinless store
        with pytest.warns(RuntimeWarning, match="#FALLBACK: embedding pin created at FIRST WRITE"):
            _remember(system, "f-1", "First", "A first memory.")
        pin = store.embedding_pin()
        assert pin["model_id"] == "test-embed-a" and pin["dimension"] == 3
        assert pin["source"] == "first-write"
        store.close()


def test_creation_pin_dimension_fills_on_first_write_silently(tmp_path) -> None:
    """A creation pin naming only the model gets its dimension locked by the
    first write — completing a birth choice, not a fallback."""
    for store in _stores(tmp_path, embedder=DimEmbedder("test-embed-a", 5),
                         embedding_pin={"model_id": "test-embed-a"}):
        system = _system(store)
        with warnings_module.catch_warnings():
            warnings_module.simplefilter("error", RuntimeWarning)  # no #FALLBACK expected
            _remember(system, "d-1", "First", "A first memory.")
        pin = store.embedding_pin()
        assert pin["dimension"] == 5 and pin["source"] == "creation"
        # The lock is real: a different-dimension embedder now refuses.
        store._embedder = DimEmbedder("test-embed-a", 7)
        with pytest.raises(ValueError, match="pinned to dimension 5"):
            _remember(system, "d-2", "Second", "A second memory.")
        store.close()


def test_wrong_space_query_degrades_loudly_never_mixes(tmp_path) -> None:
    """A wrong-dimension query vector refuses at the store, and RECALL
    converts it into the vector channel's labeled #FALLBACK — exact/keyword
    still serve (loud read degradation, never cross-space cosine)."""
    for store in _stores(tmp_path, embedder=DimEmbedder("test-embed-a", 4),
                         embedding_pin={"model_id": "test-embed-a", "dimension": 4}):
        system = _system(store)
        _remember(system, "q-1", "Harbor walk", "Walked the harbor at noon.")
        with pytest.raises(ValueError, match="query vector has dimension 2"):
            store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, query_vector=[1.0, 0.0]))

        result = system.reconstruct(
            Stimulus(cue_text="harbor", embedding=(1.0, 0.0)),  # wrong-space stimulus
            scopes=SCOPES, trace_id="t-wrong-space")
        assert any("#FALLBACK: vector channel unavailable" in w for w in result.warnings)
        assert any(h.title == "Harbor walk" for h in result.handles)  # keyword still found it
        store.close()


# ---------------------------------------------------------------------------
# M1b: the reembed repair — all-or-nothing, pin last, truth untouched
# ---------------------------------------------------------------------------


def test_reembed_swaps_space_and_journals_the_act(tmp_path) -> None:
    for store in _stores(tmp_path, embedder=DimEmbedder("test-embed-a", 3),
                         embedding_pin={"model_id": "test-embed-a", "dimension": 3}):
        system = _system(store)
        a = _remember(system, "r-1", "Harbor walk", "Walked the harbor at noon.")
        b = _remember(system, "r-2", "Kiln firing", "Ceramics glazed overnight.",
                      edges=(("continues", a),))
        digests_before = {
            row.assertion_id: (row.subject, row.object, dict(row.attributes))
            for row in store.query(TripleQuery(limit=0))
        }
        counts_before = system.access_counts(record_ids=[a, b])

        result = reembed_store(system, embedder=DimEmbedder("test-embed-b", 6),
                              owner_id=OWNER, marker_scope=SCOPE)

        pin = store.embedding_pin()
        assert pin["model_id"] == "test-embed-b" and pin["dimension"] == 6
        assert pin["source"] == "reembed"
        assert result["vectored"] == 2 and result["skipped_edges"] == 1
        assert result["old_pin"]["model_id"] == "test-embed-a"

        # Every pre-existing row byte-identical (vectors are DERIVED data).
        for row in store.query(TripleQuery(limit=0)):
            if row.assertion_id in digests_before:
                assert digests_before[row.assertion_id] == (
                    row.subject, row.object, dict(row.attributes))
        assert system.access_counts(record_ids=[a, b]) == counts_before

        # Vectors really live in the new space (6-dim), edges stay vectorless.
        for row in store.query(TripleQuery(limit=0)):
            vector = store.stored_vector(row.assertion_id)
            attrs = row.attributes if isinstance(row.attributes, dict) else {}
            if attrs.get("record_edge"):
                assert vector is None
            elif row.assertion_id in digests_before:
                assert isinstance(vector, list) and len(vector) == 6

        # The act is on the record: a bookkeeping claim naming old -> new.
        marker = next(r for r in store.query(TripleQuery(limit=0))
                      if r.subject == result["marker_record_id"])
        assert marker.attributes["maintenance"] == "reembed"
        assert marker.attributes["old_model_id"] == "test-embed-a"
        assert marker.attributes["new_model_id"] == "test-embed-b"
        assert marker.attributes["bookkeeping"] is True

        # New-space queries work end to end after the swap.
        rows = store.query(TripleQuery(scope=SCOPE, owner_id=OWNER,
                                       query_text="harbor", limit=4))
        assert rows  # embedded with the swapped-in embedder, same space
        store.close()


def test_reembed_backfills_vectorless_rows(tmp_path) -> None:
    """Rows formed while NO embedder was configured (vectorless) become
    retrievable after the repair — the pass re-derives the whole index."""
    path = tmp_path / "legacy.sqlite3"
    store = SQLiteTripleStore(path)  # no embedder, no pin: the legacy home
    system = _system(store)
    _remember(system, "l-1", "Harbor walk", "Walked the harbor at noon.")
    assert all(store.stored_vector(r.assertion_id) is None
               for r in store.query(TripleQuery(limit=0)))

    result = reembed_store(system, embedder=DimEmbedder("test-embed-a", 4), owner_id=OWNER)
    assert result["vectored"] == 1
    [row] = [r for r in store.query(TripleQuery(limit=0))
             if not r.attributes.get("record_edge") and not r.attributes.get("maintenance")]
    assert len(store.stored_vector(row.assertion_id)) == 4
    store.close()


def test_reembed_refuses_when_store_changes_mid_pass(tmp_path) -> None:
    """The lease-violation backstop: a row appearing between scan and swap
    aborts the swap with nothing written (works-or-loud)."""

    class IntrudingEmbedder(DimEmbedder):
        """Simulates a concurrent writer: sneaks a row in during embedding."""

        def __init__(self, store, system) -> None:
            super().__init__("test-embed-b", 4)
            self._store, self._system, self._fired = store, system, False

        def embed_texts(self, texts):
            if not self._fired:
                self._fired = True
                self._system.remember_many(
                    [MemoryRecordInput(kind="episode", title="Intruder",
                                       digest="A concurrent write during the pass.")],
                    scope=SCOPE, owner_id=OWNER, idempotency_key="intruder-1")
            return super().embed_texts(texts)

    for store in _stores(tmp_path, embedder=DimEmbedder("test-embed-a", 4),
                         embedding_pin={"model_id": "test-embed-a", "dimension": 4}):
        system = _system(store)
        _remember(system, "c-1", "Harbor walk", "Walked the harbor at noon.")
        old_pin = store.embedding_pin()

        with pytest.raises(RuntimeError, match="exclusive-writer guarantee"):
            reembed_store(system, embedder=IntrudingEmbedder(store, system), owner_id=OWNER)
        assert store.embedding_pin() == old_pin  # pin untouched: nothing swapped
        store.close()


# ---------------------------------------------------------------------------
# The 2026-07-11 incident shape (Mnemosyne home): a first-write pin recorded
# an embedder-attribute label the serving endpoint never recognized. The
# engine cannot verify a label against server truth — so it must (1) mark
# first-write labels as CLAIMS, (2) refuse the mismatch at open and stay
# repairable through the embedder-less repair posture, and (3) surface
# claimed-vs-served in the failure line when the server refuses at embed time.
# ---------------------------------------------------------------------------


class ServerRefusingEmbedder:
    """An embedder whose label the 'server' does not recognize — raises the
    incident's failure shape on every embed call (OpenAICompatTextEmbedder
    raises RuntimeError with the server body on HTTP 400)."""

    def __init__(self, model: str) -> None:
        self.model = model

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        raise RuntimeError(
            f'Embeddings server HTTP 400: Invalid model identifier "{self.model}". '
            "Please specify a valid downloaded model."
        )


def test_first_write_pin_marks_the_label_as_a_claim(tmp_path) -> None:
    """First-write pins record claimed_by="embedder-attribute": the label is
    read off the embedder object, never verified against the server —
    consumers must not treat it as an operator assertion. Creation and
    reembed pins carry no claim marker (the caller vouches for those)."""
    for store in _stores(tmp_path, embedder=DimEmbedder("test-embed-a", 3)):
        system = _system(store)
        with pytest.warns(RuntimeWarning, match="FIRST WRITE"):
            _remember(system, "cl-1", "First", "A first memory.")
        pin = store.embedding_pin()
        assert pin["claimed_by"] == "embedder-attribute"

        # The claim marker is provenance, not identity: reopening the SQLite
        # store with the same-labeled embedder still passes model compat.
        if isinstance(store, SQLiteTripleStore):
            store.close()
            reopened = SQLiteTripleStore(store._path, embedder=DimEmbedder("test-embed-a", 3))
            assert reopened.embedding_pin()["claimed_by"] == "embedder-attribute"
            reopened.close()
        else:
            store.close()

    # Creation pin: operator-vouched, no claim marker.
    created = SQLiteTripleStore(tmp_path / "born.sqlite3",
                                embedding_pin={"model_id": "test-embed-a", "dimension": 3})
    assert "claimed_by" not in created.embedding_pin()
    created.close()

    # Reembed pin: an operator-gated act, no claim marker.
    store = SQLiteTripleStore(tmp_path / "healed.sqlite3", embedder=DimEmbedder("test-embed-a", 3),
                              embedding_pin={"model_id": "test-embed-a", "dimension": 3})
    system = _system(store)
    _remember(system, "cl-2", "First", "A first memory.")
    reembed_store(system, embedder=DimEmbedder("test-embed-b", 4), owner_id=OWNER)
    pin = store.embedding_pin()
    assert pin["source"] == "reembed" and "claimed_by" not in pin
    store.close()


def test_incident_shape_open_refusal_repair_posture_and_heal(tmp_path) -> None:
    """The exact incident sequence on one persisted home:
    (1) a first-write pin binds a rogue label; (2) opening with the RIGHT
    model refuses loudly (pin != embedder); (3) opening WITHOUT an embedder
    is legal (labeled vectorless reads — the repair posture); (4)
    reembed_store through that open heals the pin; (5) the previously
    refused embedder now opens and serves recall."""
    path = tmp_path / "incident.sqlite3"

    # (1) Simulate the incident birth: an embedder claiming a label the
    # server would never serve, producing 1024-class vectors regardless.
    rogue = DimEmbedder("mlx-community/all-minilm-l6-v2", 8)
    store = SQLiteTripleStore(path, embedder=rogue)
    system = _system(store)
    with pytest.warns(RuntimeWarning, match="FIRST WRITE"):
        _remember(system, "i-1", "Harbor walk", "Walked the harbor at noon.")
    _remember(system, "i-2", "Kiln firing", "Ceramics glazed overnight.")
    pin = store.embedding_pin()
    assert pin["model_id"] == "mlx-community/all-minilm-l6-v2"
    assert pin["claimed_by"] == "embedder-attribute"
    store.close()

    # (2) The ruled default refuses at open — no silent mixing, and the
    # refusal text names the repair paths.
    target = DimEmbedder("text-embedding-qwen3-embedding-0.6b", 8)
    with pytest.raises(ValueError, match="reembed repair"):
        SQLiteTripleStore(path, embedder=target)

    # (3) The repair posture: open WITHOUT an embedder is always legal.
    repair = SQLiteTripleStore(path)
    repair_system = _system(repair)

    # (4) The heal: target embedder enters through reembed_store alone.
    result = reembed_store(
        repair_system, embedder=target, owner_id=OWNER,
        model_id="text-embedding-qwen3-embedding-0.6b",
        reason="incident repair: rogue first-write label")
    healed = repair.embedding_pin()
    assert healed["model_id"] == "text-embedding-qwen3-embedding-0.6b"
    assert healed["source"] == "reembed" and "claimed_by" not in healed
    assert result["old_pin"]["model_id"] == "mlx-community/all-minilm-l6-v2"
    assert result["vectored"] == 2
    repair.close()

    # (5) The previously refused embedder now opens and serves recall.
    served = SQLiteTripleStore(path, embedder=target)
    rows = served.query(TripleQuery(scope=SCOPE, owner_id=OWNER,
                                    query_text="harbor", limit=4))
    assert rows
    served.close()


def test_query_time_embed_failure_names_the_pin(tmp_path) -> None:
    """When the server refuses the embed call (the incident's LMStudio 400),
    the surfaced error must carry the store's pinned identity so the
    operator sees claimed-vs-served in one line — at the store query
    surface AND in the recall channel's labeled #FALLBACK."""
    good = DimEmbedder("mlx-community/all-minilm-l6-v2", 8)
    refusing = ServerRefusingEmbedder("mlx-community/all-minilm-l6-v2")
    for store in _stores(tmp_path, embedder=good):
        system = _system(store)
        with pytest.warns(RuntimeWarning, match="FIRST WRITE"):
            _remember(system, "e-1", "Harbor walk", "Walked the harbor at noon.")

        # Swap in the server-refusing embedder (same label: open-compat holds;
        # the incident fails at EMBED time, not at open).
        store._embedder = refusing
        with pytest.raises(RuntimeError) as excinfo:
            store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, query_text="harbor"))
        message = str(excinfo.value)
        assert 'Invalid model identifier "mlx-community/all-minilm-l6-v2"' in message
        assert "store pin: mlx-community/all-minilm-l6-v2@8d" in message
        assert "claimed by embedder-attribute" in message

        # Recall path: the injected-embedder failure degrades loudly AND
        # names the pin (exact/keyword still serve the cue).
        recall_system = MemorySystem(store=store, journal=system.journal, embedder=refusing)
        result = recall_system.reconstruct(
            Stimulus(cue_text="harbor"), scopes=SCOPES, trace_id="t-embed-400")
        fallback = [w for w in result.warnings if "vector channel unavailable" in w]
        assert fallback and "store pin: mlx-community/all-minilm-l6-v2@8d" in fallback[0]
        assert any(h.title == "Harbor walk" for h in result.handles)
        store.close()
