"""engine_manifest() — the generated inventory (consensus substrate).

Pins the manifest's whole point: DERIVED sections are the live objects
(identity, not copies), every pass row resolves to a real callable whose
flags match the live signature, declared honesty claims cross-check
against behavioral pins where they exist, and the pass table cannot
silently miss a new engine pass (the drift test). JSON-safe throughout.
"""

from __future__ import annotations

import inspect
import json

from abstractmemory import (
    DIARY_TYPES,
    DRIVE_PRESSURE_BOUND,
    KIND_RANKS,
    MECHANICAL_DIGEST_METHODS,
    MEMORY_RECORD_KINDS,
    SELF_FRACTION_FLOOR,
    WARNING_WORDS,
    engine_manifest,
)
from abstractmemory.engine_manifest import _PASS_TABLE, _resolve


def test_manifest_is_json_safe_and_versioned() -> None:
    m = engine_manifest()
    assert m["manifest"] == "abstractmemory-engine"
    assert isinstance(m["manifest_version"], int)
    json.dumps(m)  # the whole payload must serialize


def test_vocabularies_are_the_live_sets_not_copies() -> None:
    m = engine_manifest()
    v = m["vocabularies"]
    assert v["record_kinds"] == sorted(MEMORY_RECORD_KINDS)
    assert v["diary_types"] == sorted(DIARY_TYPES)
    assert v["digest_methods"] == sorted(MECHANICAL_DIGEST_METHODS)
    assert v["warning_words"] == sorted(WARNING_WORDS)
    assert v["kind_ranks"] == {k: KIND_RANKS[k] for k in sorted(KIND_RANKS)}
    # The realization kind (this week's widening) rides through with zero
    # manifest edits — the derivation IS the sync.
    assert "realization" in v["record_kinds"]


def test_every_pass_row_resolves_and_flags_match_signatures() -> None:
    m = engine_manifest()
    by_name = {p["name"]: p for p in m["passes"]}
    assert len(by_name) == len(m["passes"]), "duplicate pass rows"
    for row in _PASS_TABLE:
        fn = _resolve(row["name"], row["module"])
        served = by_name[row["name"]]
        sig_defaults = {p.name for p in inspect.signature(fn).parameters.values()
                        if p.default is not inspect.Parameter.empty}
        assert set(served["flags"]) == sig_defaults, row["name"]


def test_declared_flags_carry_the_ruled_defaults() -> None:
    m = engine_manifest()
    sleep = next(p for p in m["passes"] if p["name"] == "sleep_pass")
    # The two cycle-window levers, straight off the live signature.
    assert sleep["flags"]["include_dream"] is True
    assert sleep["flags"]["include_identity"] is True
    identity = next(p for p in m["passes"] if p["name"] == "identity_review_pass")
    assert identity["cadence_class"] == "nightly-only"
    assert "registrar-never-authors" in identity["honesty"]


def test_constants_are_the_canonical_values() -> None:
    m = engine_manifest()
    assert m["constants"]["DRIVE_PRESSURE_BOUND"] == DRIVE_PRESSURE_BOUND
    assert m["constants"]["SELF_FRACTION_FLOOR"] == SELF_FRACTION_FLOOR


def test_tunables_reflect_dataclass_fields() -> None:
    from abstractmemory import RecallBudget
    from abstractmemory.sleep_policy import SleepTuning

    m = engine_manifest()
    budget = m["tunables"]["RecallBudget"]
    assert budget["shelf_size"] == RecallBudget().shelf_size
    assert budget["token_budget"] == RecallBudget().token_budget
    tuning = m["tunables"]["SleepTuning"]
    import dataclasses
    assert set(tuning) == {f.name for f in dataclasses.fields(SleepTuning)}


def test_pass_table_covers_the_exported_pass_surface() -> None:
    """The drift pin: a NEW exported pass/verb without a manifest row
    fails here — the manifest can never silently under-describe the
    engine (the whole point of generating it)."""
    import abstractmemory as pkg

    exported_passes = {n for n in pkg.__all__
                       if n.endswith("_pass") or n.endswith("_report")}
    manifest_names = {row["name"] for row in _PASS_TABLE}
    missing = exported_passes - manifest_names
    assert not missing, (
        f"exported passes missing a manifest row: {sorted(missing)} — "
        "add the row (name + cadence_class + honesty) in the same change")
