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
from abstractmemory.graph import SOURCE_KINDS

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
    assert SourceRef(kind="step", run_id="run-1", seq=0).key() == "step:run-1#0"


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
