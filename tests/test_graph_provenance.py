"""SourceRef and Provenance: the typed ledger provenance contract (ADR 0003 decisions 8-9; contract §1-§2).

Mutants (tried by hand in an isolated copy; each turned the named test red):
- `SourceRef.__post_init__`: the required-field loop removed            -> test_each_kind_refuses_its_missing_id
- `SourceRef.key()`: step key `step:<run>#<seq>` written `step:<run>:<seq>` -> test_key_formats
- `Provenance.from_legacy`: `payload_ref` dropped from the lifted keys    -> test_from_legacy_lifts_the_flat_keys
- `Provenance.from_dict`: unknown-key refusal removed                     -> test_from_dict_refuses_legacy_flat_keys
"""
from __future__ import annotations

import pytest

from abstractmemory import InvalidSourceRef, Provenance, ProvenanceRequired, SourceRef
from abstractmemory.graph import SOURCE_KINDS, RevisionOp

FULL = {
    "run": {"kind": "run", "run_id": "run-1"},
    "step": {"kind": "step", "run_id": "run-1", "seq": 7, "step_id": "st-9"},
    "artifact": {"kind": "artifact", "artifact_id": "art-1", "run_id": "run-1"},
    "message": {"kind": "message", "message_id": "msg-1", "run_id": "run-1"},
    "event": {"kind": "event", "event_id": "ev-1", "stream": "inbox"},
    "diary_entry": {"kind": "diary_entry", "entry_id": "de-1", "run_id": "diary:ent-1"},
}
REQUIRED = {
    "run": ["run_id"], "step": ["run_id", "seq"], "artifact": ["artifact_id"], "message": ["message_id"],
    "event": ["event_id"], "diary_entry": ["entry_id"],
}


def test_source_kinds_are_the_contract_set() -> None:
    assert SOURCE_KINDS == ("run", "step", "artifact", "message", "event", "diary_entry")
    assert set(FULL) == set(SOURCE_KINDS)


@pytest.mark.parametrize("kind,field", [(k, f) for k, fs in REQUIRED.items() for f in fs])
def test_each_kind_refuses_its_missing_id(kind: str, field: str) -> None:
    data = dict(FULL[kind])
    data.pop(field)
    with pytest.raises(InvalidSourceRef, match=field):
        SourceRef.from_dict(data)
    blank = dict(FULL[kind], **{field: "  " if field != "seq" else None})
    with pytest.raises(InvalidSourceRef):
        SourceRef.from_dict(blank)


@pytest.mark.parametrize("bad", [True, -1, "7", 7.0])
def test_step_seq_is_a_non_negative_int(bad) -> None:
    with pytest.raises(InvalidSourceRef, match="seq"):
        SourceRef(kind="step", run_id="run-1", seq=bad)
    assert SourceRef(kind="step", run_id="run-1", seq=1).key() == "step:run-1#1"
    with pytest.raises(InvalidSourceRef):  # ledger rows are 1-based (AbstractRuntime coerce_ledger_seq)
        SourceRef(kind="step", run_id="run-1", seq=0)


def test_unknown_kind_unknown_key_and_foreign_field_are_refused() -> None:
    with pytest.raises(InvalidSourceRef, match="kind"):
        SourceRef.from_dict({"kind": "turn", "run_id": "r"})
    with pytest.raises(InvalidSourceRef, match="unknown SourceRef keys"):
        SourceRef.from_dict({"kind": "run", "run_id": "r", "note_id": "n"})
    # A field another kind owns is refused, not silently carried.
    with pytest.raises(InvalidSourceRef, match="does not carry"):
        SourceRef.from_dict({"kind": "artifact", "artifact_id": "a", "seq": 3})
    with pytest.raises(InvalidSourceRef):
        SourceRef.from_dict("run:r")  # type: ignore[arg-type]


def test_key_formats() -> None:
    keys = {k: SourceRef.from_dict(v).key() for k, v in FULL.items()}
    assert keys == {
        "run": "run:run-1", "step": "step:run-1#7", "artifact": "artifact:art-1", "message": "message:msg-1",
        "event": "event:ev-1", "diary_entry": "diary_entry:de-1",
    }


@pytest.mark.parametrize("kind", list(FULL))
def test_round_trip_and_runtime_id_on_any_kind(kind: str) -> None:
    data = dict(FULL[kind], runtime_id="plane-rt")
    ref = SourceRef.from_dict(data)
    assert ref.to_dict() == data
    assert SourceRef.from_dict(ref.to_dict()) == ref
    assert ref.runtime_id == "plane-rt"


def test_provenance_requires_an_actor_and_reports_grounding() -> None:
    with pytest.raises(ProvenanceRequired, match="actor"):
        Provenance(sources=[FULL["run"]])
    sourced = Provenance(sources=[FULL["step"], FULL["artifact"]], actor="abstractnote")
    derived = Provenance(derived_from=["ex:episode-1"], actor="abstractmemory:sleep")
    neither = Provenance(actor="runtime")
    assert sourced.is_grounded() and derived.is_grounded()
    assert not neither.is_grounded()
    assert all(isinstance(s, SourceRef) for s in sourced.sources)


def test_provenance_dedupes_sources_by_key_and_round_trips() -> None:
    prov = Provenance(
        sources=[FULL["step"], dict(FULL["step"], step_id="other"), FULL["artifact"]],
        derived_from=["m1", "m1", "m2"], actor="entity:e1", reader="lmstudio/qwen", reason="formed",
        extra={"turn_id": "t1"},
    )
    assert [s.key() for s in prov.sources] == ["step:run-1#7", "artifact:art-1"]
    assert prov.derived_from == ("m1", "m2")
    assert Provenance.from_dict(prov.to_dict()) == prov
    assert prov.to_dict()["extra"] == {"turn_id": "t1"}


def test_from_dict_refuses_legacy_flat_keys() -> None:
    with pytest.raises(ProvenanceRequired, match="from_legacy"):
        Provenance.from_dict({"run_id": "r1", "turn_id": "t1", "actor": "runtime"})
    with pytest.raises(ProvenanceRequired, match="extra"):
        Provenance.from_dict({"actor": "runtime", "sources": [FULL["run"]], "note_id": "n1"})
    with pytest.raises(InvalidSourceRef):
        Provenance.from_dict({"actor": "runtime", "sources": [{"kind": "step", "run_id": "r1"}]})  # no seq


def test_from_legacy_lifts_the_flat_keys() -> None:
    prov = Provenance.from_legacy({
        "run_id": "run-1", "turn_id": "t-3", "writer_run_id": "run-0", "span_id": "art-span",
        "payload_ref": "artifact:art-payload", "entry_id": "de-9", "reason": "remembered",
    })
    assert [s.key() for s in prov.sources] == [
        "run:run-1", "artifact:art-span", "artifact:art-payload", "diary_entry:de-9",
    ]
    assert all(s.run_id == "run-1" for s in prov.sources if s.kind == "artifact")
    assert prov.actor == "runtime"
    assert prov.reason == "remembered"
    assert prov.extra == {"turn_id": "t-3", "writer_run_id": "run-0"}
    assert prov.is_grounded()


def test_from_legacy_never_fabricates() -> None:
    prov = Provenance.from_legacy({"turn_id": "t-1", "run_id": "  ", "span_id": ""}, actor="entity:e1")
    assert prov.sources == ()
    assert not prov.is_grounded()
    assert prov.actor == "entity:e1"
    # A diary pseudo-run is not a ledger run: it rides the diary_entry ref.
    diary = Provenance.from_legacy({"run_id": "diary:ent-1", "entry_id": "de-1"})
    assert [s.to_dict() for s in diary.sources] == [{"kind": "diary_entry", "entry_id": "de-1", "run_id": "diary:ent-1"}]
    lone = Provenance.from_legacy({"run_id": "diary:ent-1"})
    assert lone.sources == () and lone.extra == {"run_id": "diary:ent-1"}


def test_from_legacy_reads_a_graph_shaped_dict() -> None:
    prov = Provenance.from_legacy({"sources": [FULL["run"]], "extra": {"note_id": "n"}})
    assert prov.sources[0].key() == "run:run-1"
    assert prov.actor == "runtime"


# ---------------------------------------------------------------------------------------------------------------
# The graph enforces it (ADR 0003 decision 8 and "Enforcement"): MemoryGraph.apply_revision.
# Graph-level mutants (applied by hand to src/abstractmemory/graph/graph.py; each turned the named test red):
# - `_prepare`: the per-memory `is_grounded()` refusal removed                -> test_a_write_with_neither_sources_nor_lineage_is_refused[*]
# - `_prepare`: the revision-level `is_grounded()` refusal removed            -> test_a_revision_must_itself_be_grounded[*]
# - `_validate`: the close/narrow-only "cause outside its targets" rule removed -> test_a_revision_must_itself_be_grounded[*]
# - `_validate`: the fixpoint seeds every in-revision memory as grounded      -> test_a_derived_chain_that_never_reaches_a_source_is_refused[*]
# - `_validate._resolve`: an unknown id resolves to itself                    -> test_a_derived_chain_that_never_reaches_a_source_is_refused[*]
# - `_adopt`: the cause gate removed                                         -> test_a_store_row_written_outside_the_graph_must_be_adopted_first[*]
# - `_adopt`: the content comparison removed                                 -> test_a_store_row_written_outside_the_graph_must_be_adopted_first[*]
# - `apply_revision`: `tx.set_provenance` for adopted rows removed            -> test_a_store_row_written_outside_the_graph_must_be_adopted_first[*]
# - `apply_revision`: the close/narrow "not a memory of this graph" refusal removed
#                                                                             -> test_a_store_row_written_outside_the_graph_must_be_adopted_first[*]
# - `_SQLiteTx.write_pin` writes nothing and `_sqlite_rows` writes the pin itself (the 0.3 path, before the tx)
#                                                                             -> test_a_refused_write_leaves_no_embedding_pin
# - `_SQLiteBackend.with_ref`: a run ref matched on ref_key                   -> test_sources_of_and_derived_from_source[*]
# - `MemoryGraph.sources_of`: parents never enqueued                          -> test_sources_of_and_derived_from_source[*]
# ---------------------------------------------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

from abstractmemory import TripleAssertion, TripleQuery  # noqa: E402

from graph_support import (  # noqa: E402
    KINDS,
    FakeEmbedder,
    T,
    art,
    claim,
    close,
    file_state,
    home_state,
    narrow,
    open_home,
    prov,
    rev,
    step,
)


@pytest.fixture(params=KINDS)
def home(request, tmp_path: Path):
    h = open_home(tmp_path, request.param)
    h.graph.apply_revision(rev("r-base", claim("base", valid_from=T(1)), provenance=prov(step("run-1", 1))))
    yield h
    h.close()


def test_a_write_with_neither_sources_nor_lineage_is_refused(home) -> None:
    before = home_state(home)
    for bad in (prov(), {"sources": [], "derived_from": [], "actor": "runtime"}):
        with pytest.raises(ProvenanceRequired, match="never neither"):
            home.graph.apply_revision(rev("r-x", claim("x", provenance=bad)))
    # A payload provenance in the legacy flat shape is refused, pointing at from_legacy.
    with pytest.raises(ProvenanceRequired, match="from_legacy"):
        home.graph.apply_revision(rev("r-x", claim("x", provenance={"run_id": "run-1", "actor": "runtime"})))
    assert home_state(home) == before
    assert home.graph.revisions()[0][-1].revision_id == "r-base"


def test_a_revision_must_itself_be_grounded(home) -> None:
    before = home_state(home)
    with pytest.raises(ProvenanceRequired, match="cause of every change"):
        home.graph.apply_revision(rev("r-x", close("base", T(3)), provenance=prov(actor="abstractnote")))
    with pytest.raises(ProvenanceRequired, match="not a memory of this graph"):
        home.graph.apply_revision(rev("r-x", close("base", T(3)), provenance=prov(derived=["ghost"])))
    # Review M7: a close/narrow-only revision derived ONLY from the memory it closes names no cause at all.
    with pytest.raises(ProvenanceRequired, match="other than the ones it changes"):
        home.graph.apply_revision(rev("r-x", close("base", T(3)), provenance=prov(derived=["base"], actor="person")))
    assert home_state(home) == before
    home.graph.apply_revision(rev("r-why", claim("why", o="ex:why"), provenance=prov(step("run-1", 5))))
    ok = home.graph.apply_revision(rev("r-ok", close("base", T(3)), provenance=prov(derived=["why"], actor="person")))
    assert ok.closed == ["base"]


def test_a_derived_chain_that_never_reaches_a_source_is_refused(home) -> None:
    before = home_state(home)
    cases = {
        "unknown parent": [claim("d1", provenance=prov(derived=["ghost"]))],
        "self": [claim("d1", provenance=prov(derived=["d1"]))],
        "cycle": [claim("d1", provenance=prov(derived=["d2"])), claim("d2", o="ex:x", provenance=prov(derived=["d1"]))],
        "chain to nothing": [claim("d1", provenance=prov(derived=["d2"])),
                             claim("d2", o="ex:x", provenance=prov(derived=["d3"])),
                             claim("d3", o="ex:y", provenance=prov(derived=["d1"]))],
    }
    for name, ops in cases.items():
        with pytest.raises(ProvenanceRequired):
            home.graph.apply_revision(rev(f"r-{name}", *ops, provenance=prov(step("run-1", 2))))
        assert home_state(home) == before, name
    # Grounded chains are accepted: from a memory of the graph, and through a chain inside one revision.
    result = home.graph.apply_revision(rev(
        "r-ok",
        claim("d3", o="ex:z", provenance=prov(derived=["d2"], actor="abstractmemory:sleep")),
        claim("d2", o="ex:y", provenance=prov(derived=["d1"], actor="abstractmemory:sleep")),
        claim("d1", o="ex:x", provenance=prov(derived=["base"], actor="abstractmemory:sleep")),
        provenance=prov(derived=["base"], actor="abstractmemory:sleep")))
    assert result.assertion_ids == ["d3", "d2", "d1"]
    assert [s.key() for s in home.graph.sources_of("d3")] == ["step:run-1#1"]
    assert home.graph.sources_of("d3", transitive=False) == []


def test_derived_from_accepts_a_record_graph_id(home) -> None:
    home.graph.apply_revision(rev("r-note", claim("note-digest", s="ex:note-7", p="dcterms:abstract",
                                                  o="dana joined acme", attributes={"literal": True}),
                                  provenance=prov(art("note-7"))))
    home.graph.apply_revision(rev("r-derived", claim("lesson", s="ex:dana", p="ex:lesson", o="ex:x",
                                                     provenance=prov(derived=["ex:note-7"], actor="entity:e1")),
                                  provenance=prov(derived=["ex:note-7"], actor="entity:e1")))
    assert [s.key() for s in home.graph.sources_of("lesson")] == ["artifact:note-7"]
    assert home.graph.history("ex:note-7")[0]["revision_id"] == "r-note"  # a graph id reads its digest's history
    assert home.graph.derived_from_source(art("note-7")) == ["note-digest", "lesson"]


def test_a_store_row_written_outside_the_graph_must_be_adopted_first(home) -> None:
    legacy = TripleAssertion(subject="ex:dana", predicate="schema:worksFor", object="ex:oldco", scope="global",
                             owner_id="abstractnote", observed_at=T(1), valid_from=T(1), assertion_id="legacy-1",
                             provenance={"note_id": "nt_1", "run_id": "chat-1"}, attributes={"certainty": "stated"})
    home.store.add([legacy])
    before = home_state(home)
    # Not a memory of the graph: deriving from it, closing it, narrowing it, or re-asserting it as an ingest.
    for bad in (rev("r-x", claim("y", provenance=prov(derived=["legacy-1"]))),
                rev("r-x", close("legacy-1", T(4))),
                rev("r-x", narrow("legacy-1", T(4))),
                rev("r-x", RevisionOp("assert", dict(legacy.to_dict(), provenance=prov(art("note-1"))))),
                ):
        with pytest.raises(ProvenanceRequired, match="adopt"):
            home.graph.apply_revision(bad)
        assert home_state(home) == before
    # An import adopts it only as stored: a different claim under the same id is refused.
    with pytest.raises(ValueError, match="differs from the stored row"):
        home.graph.apply_revision(rev("r-import", RevisionOp("assert", dict(
            legacy.to_dict(), object="ex:newco", provenance=prov(art("note-1")))), cause="import"))
    assert home_state(home) == before
    graph_prov = Provenance.from_legacy(legacy.provenance, actor="abstractnote")
    graph_prov = Provenance(sources=[art("note-1")], actor="abstractnote", extra=graph_prov.extra)
    adopted = home.graph.apply_revision(rev("r-import", RevisionOp(
        "assert", dict(legacy.to_dict(), provenance=graph_prov.to_dict())), cause="import"))
    assert adopted.assertion_ids == ["legacy-1"]
    [row] = home.store.query(TripleQuery(assertion_ids=("legacy-1",)))
    assert row.provenance == graph_prov.to_dict()  # the row now carries the graph shape ...
    [event] = home.graph.history("legacy-1")
    assert event["detail"]["adopted"] is True
    assert event["detail"]["previous_provenance"] == {"note_id": "nt_1", "run_id": "chat-1"}  # ... nothing lost
    # Now it changes through the graph.
    assert home.graph.apply_revision(rev("r-close", close("legacy-1", T(4)))).closed == ["legacy-1"]


def test_a_refused_write_leaves_no_embedding_pin(tmp_path: Path) -> None:
    home = open_home(tmp_path, "sqlite", embedder=FakeEmbedder())
    before = file_state(home.path)
    assert home.store.embedding_pin() is None
    with pytest.raises(ProvenanceRequired):  # refused INSIDE the transaction (the chain check), after embedding
        home.graph.apply_revision(rev("r-x", claim("x", provenance=prov(derived=["ghost"]))))
    assert file_state(home.path) == before and home.store.embedding_pin() is None
    with pytest.warns(RuntimeWarning, match="FIRST WRITE"):
        home.graph.apply_revision(rev("r-ok", claim("x")))
    assert home.store.embedding_pin()["dimension"] == 64
    home.close()


def test_sources_of_and_derived_from_source(home) -> None:
    home.graph.apply_revision(rev(
        "r-1", claim("c1", o="ex:a"), claim("c2", o="ex:b"),
        provenance=prov(step("run-9", 3, "st-3"), art("art-9", "run-9"), {"kind": "message", "message_id": "m-1"})))
    home.graph.apply_revision(rev("r-2", claim("c3", o="ex:c"), provenance=prov(step("run-9", 4))))
    home.graph.apply_revision(rev(
        "r-3", claim("sum", o="ex:sum", provenance=prov(derived=["c1", "c3"], actor="abstractmemory:sleep")),
        cause="maintenance", provenance=prov(derived=["c1"], actor="abstractmemory:sleep")))
    assert [s.key() for s in home.graph.sources_of("sum")] == [
        "step:run-9#3", "artifact:art-9", "message:m-1", "step:run-9#4"]
    assert home.graph.sources_of("sum", transitive=False) == []
    assert home.graph.sources_of("sum", limit=2)[1].key() == "artifact:art-9"
    assert home.graph.derived_from_source(step("run-9", 3)) == ["c1", "c2", "sum"]
    assert home.graph.derived_from_source(step("run-9", 4)) == ["c3", "sum"]
    # A run ref matches every ref stamped with that run (steps and artifacts), once per memory.
    assert home.graph.derived_from_source({"kind": "run", "run_id": "run-9"}) == ["c1", "c2", "c3", "sum"]
    assert home.graph.derived_from_source({"kind": "message", "message_id": "m-1"}) == ["c1", "c2", "sum"]
    assert home.graph.derived_from_source({"kind": "run", "run_id": "run-unknown"}) == []
    assert home.graph.sources_of("unknown") == [] and home.graph.history("unknown") == []


def test_from_dict_refuses_a_string_where_a_list_is_expected():
    """Mutant: `tuple(data.get("derived_from") or ())` in Provenance.from_dict -> "m1" becomes ('m', '1') and is
    accepted as two memory ids (found by the runtime worker, 2026-10-27)."""
    import pytest
    from abstractmemory.graph import InvalidSourceRef, Provenance, ProvenanceRequired

    base = {"sources": [], "derived_from": [], "actor": "runtime", "reader": None, "reason": None, "extra": {}}
    with pytest.raises(ProvenanceRequired):
        Provenance.from_dict({**base, "derived_from": "m1"})
    with pytest.raises(InvalidSourceRef):
        Provenance.from_dict({**base, "sources": {"kind": "run", "run_id": "r1"}})
    with pytest.raises(InvalidSourceRef):
        Provenance.from_dict({**base, "sources": "run:r1"})
    ok = Provenance.from_dict({**base, "derived_from": ["m1"]})
    assert ok.derived_from == ("m1",)


# Synthetic run ids (review M5; ADR 0003 decision 11). Mutants (each turned the named test red):
# - `SourceRef.__post_init__`: the synthetic run/step refusal removed        -> test_a_synthetic_run_id_is_never_a_source
# - `Provenance.from_legacy`: `ledger_run` = any non-diary run id (pre-review) -> test_a_synthetic_run_id_is_never_a_source

from abstractmemory.graph import SYNTHETIC_RUN_ID_PREFIXES, is_synthetic_run_id  # noqa: E402


@pytest.mark.parametrize("run_id", ["chat-session-123", "global_memory", "session_memory_abc", "diary:ent-1"])
def test_a_synthetic_run_id_is_never_a_source(run_id: str) -> None:
    assert is_synthetic_run_id(run_id) and run_id.startswith(SYNTHETIC_RUN_ID_PREFIXES)
    for kind in ("run", "step"):
        with pytest.raises(InvalidSourceRef, match="synthetic"):
            SourceRef.from_dict({"kind": kind, "run_id": run_id, "seq": 1} if kind == "step"
                                else {"kind": kind, "run_id": run_id})
    lifted = Provenance.from_legacy({"run_id": run_id, "turn_id": "t1"})
    assert not lifted.is_grounded() and lifted.extra["run_id"] == run_id  # kept, never a ref
    # The artifact it carries is still the ground (with no run_id stamped on it).
    with_art = Provenance.from_legacy({"run_id": run_id, "span_id": "art-1"})
    assert [s.to_dict() for s in with_art.sources] == [{"kind": "artifact", "artifact_id": "art-1"}]
    # A real run id is untouched, and the diary pseudo-run still rides its diary_entry ref.
    assert not is_synthetic_run_id("run-7f3a") and Provenance.from_legacy({"run_id": "run-7f3a"}).is_grounded()
    assert SourceRef.from_dict({"kind": "diary_entry", "entry_id": "de-1", "run_id": "diary:ent-1"}).run_id


def test_from_legacy_reads_the_runtime_stamped_mixed_shape() -> None:
    """Runtime review R8: `MemoryFacade.stamp` (abstractruntime seam_handlers._handle_form) keeps the legacy flat keys
    for older readers and ADDS the `sources` it vouches for. from_legacy reads that shape: graph keys as they are,
    every flat key into extra, no ref lifted from a flat key (not even the payload_ref or a synthetic run id).
    from_dict stays strict. Mutant: the mixed branch handing the whole dict to from_dict (pre-review) -> red."""
    stamped = {
        "source": "turn", "run_id": "chat-sess-1", "turn_id": "t-3", "writer_run_id": "run-0",
        "payload_ref": "art-9", "span_id": "art-span",
        "sources": [{"kind": "step", "run_id": "run-abc", "seq": 4, "step_id": "st-4", "runtime_id": "rt-1"},
                    {"kind": "artifact", "artifact_id": "art-9", "run_id": "run-abc", "runtime_id": "rt-1"}],
    }
    prov = Provenance.from_legacy(stamped)
    assert [s.key() for s in prov.sources] == ["step:run-abc#4", "artifact:art-9"]
    assert prov.actor == "runtime"
    assert prov.extra == {"source": "turn", "run_id": "chat-sess-1", "turn_id": "t-3", "writer_run_id": "run-0",
                          "payload_ref": "art-9", "span_id": "art-span"}
    with_extra = Provenance.from_legacy({**stamped, "actor": "entity:e1", "reason": "formed",
                                         "extra": {"turn_id": "t-explicit", "note": 1}})
    assert with_extra.actor == "entity:e1" and with_extra.reason == "formed"
    assert with_extra.extra["turn_id"] == "t-explicit" and with_extra.extra["note"] == 1
    with pytest.raises(ProvenanceRequired, match="from_legacy"):
        Provenance.from_dict(stamped)  # strict: the flat keys are not the graph shape
    with pytest.raises(InvalidSourceRef):  # the stamped sources are validated
        Provenance.from_legacy({**stamped, "sources": [{"kind": "step", "run_id": "run-abc"}]})
