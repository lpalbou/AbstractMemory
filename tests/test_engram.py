"""The engram pass (keystone experiment, a2a 0003): spark → identity
records + prompt-active self bindings, idempotent and version-guarded."""

from __future__ import annotations

import copy
import warnings as warnings_module
from typing import Any, Dict

import pytest

from abstractmemory import RecallBudget, Stimulus, engram
from abstractmemory.spark import DEFAULT_SPARK_TEMPLATE

SCOPE = "self"
OWNER = "entity-1"


def _spark() -> Dict[str, Any]:
    spark = copy.deepcopy(DEFAULT_SPARK_TEMPLATE)
    spark["name"] = "Ada"
    return spark


def _journal_footprint(journal) -> Dict[str, int]:
    return {
        "seq": journal.current_seq(),
        "bindings": len(journal.bindings(fold=False)),
    }


def test_engram_round_trip_surfaces_self_component(system, stack) -> None:
    store, _ = stack
    result = engram(system, _spark(), owner_id=OWNER,
                    spark_artifact_ref="artifact://sparks/ada-v1.json")
    assert result.created is True
    assert result.warnings == ()  # the canonical template lints clean
    assert len(result.record_ids["values"]) == 3       # shared_vulnerability + 2
    assert len(result.record_ids["purposes"]) == 1
    assert len(result.record_ids["traits"]) == 1
    assert len(result.record_ids["honesty"]) == 1
    assert len(result.binding_ids) == 6                 # every identity record bound

    # The identity core surfaces stimulus-free with admission="self".
    r = system.reconstruct(Stimulus(cue_text=""), scopes=[(SCOPE, OWNER)],
                           budget=RecallBudget(self_fraction=0.5, shelf_size=12),
                           journal=False)
    self_handles = [h for h in r.handles if h.admission == "self"]
    assert self_handles, "engrammed identity must enter via the self component"
    kinds = [h.kind for h in self_handles]
    assert kinds[0] == "value"                          # value < purpose < trait order
    titles = {h.title for h in self_handles}
    assert "shared_vulnerability" in titles             # the engram is present
    by_title = {h.title: h for h in self_handles}
    assert by_title["shared_vulnerability"].binding == "indexed+active"
    # The marker claim is NOT part of the self core (never bound active).
    assert all(h.kind != "claim" for h in self_handles)
    # raw tier reachable when the host attested the spark document.
    assert system.payload(result.record_ids["values"][0], tier="raw")["payload_ref"] == (
        "artifact://sparks/ada-v1.json"
    )


def test_engram_rerun_is_a_complete_noop(system, stack) -> None:
    _, journal = stack
    first = engram(system, _spark(), owner_id=OWNER)
    before = _journal_footprint(journal)

    again = engram(system, _spark(), owner_id=OWNER)
    assert again.created is False
    assert again.record_ids == first.record_ids         # identical ids re-derived
    assert again.binding_ids == first.binding_ids
    assert _journal_footprint(journal) == before        # zero new journal rows


def test_engram_modified_spark_same_version_is_refused(system) -> None:
    engram(system, _spark(), owner_id=OWNER)
    tampered = _spark()
    tampered["purposes"] = [{"statement": "Serve the quarterly metrics above all."}]
    with pytest.raises(ValueError, match="kept for life"):
        engram(system, tampered, owner_id=OWNER)


def test_g8_supersession_guard_blocks_v2_until_v1_retired(system) -> None:
    """G8 under v1-for-life (maintainer correction): a spark is engrammed
    ONCE and kept; a HIGHER version is an exceptional REPAIR for a
    defective core and is refused while the born core remains prompt-active
    — even a repair must never leave BOTH cores in the working set.
    Retiring the v1 records (the repair, simulated manually here)
    unblocks v2."""
    v1 = engram(system, _spark(), owner_id=OWNER)
    v2_spark = _spark()
    v2_spark["spark"] = 2
    v2_spark["purposes"] = [{"statement": "Help this home run itself, and say when you cannot."}]

    with pytest.raises(ValueError, match=r"spark v1 is engrammed and prompt-active.*exceptional repair"):
        engram(system, v2_spark, owner_id=OWNER)

    # Simulate the exceptional repair: close every v1 identity record and
    # rebind it inactive (retirement is deliberate, never silent).
    for section in ("values", "purposes", "traits", "honesty"):
        for gid in v1.record_ids[section]:
            system.close_record(gid, reason="repair: v1 core defective, superseded by v2")
            system.bind(gid, scope=SCOPE, owner_id=OWNER,
                        search_state="indexed", prompt_state="inactive",
                        lifecycle="superseded", source="revision",
                        reason="repair: spark v2")

    result = engram(system, v2_spark, owner_id=OWNER)
    assert result.created is True

    # The folded identity read sees ONLY the v2 core now.
    v2_rows = system.self_records(scope=SCOPE, owner_id=OWNER, spark_version=2)
    assert v2_rows and {a.attributes["spark_version"] for a in v2_rows} == {2}
    assert system.self_records(scope=SCOPE, owner_id=OWNER, spark_version=1) == []
    all_rows = system.self_records(scope=SCOPE, owner_id=OWNER)
    assert {a.attributes["spark_version"] for a in all_rows} == {2}


def test_engram_marker_never_surfaces_on_shelves(system, stack) -> None:
    """Marker shelf-noise fix: the engram marker (kind='claim',
    attributes.bookkeeping) is engine bookkeeping, not a memory — it must
    never seat on a working-set shelf as fill, while staying fully
    queryable (the G8 guard scans it via layer-1 query)."""
    store, _ = stack
    engram(system, _spark(), owner_id=OWNER)

    # Blank-cue reconstruct with a roomy shelf: recents fill previously
    # seated the marker (it is the NEWEST-adjacent record after engram).
    r = system.reconstruct(Stimulus(cue_text=""), scopes=[(SCOPE, OWNER)],
                           budget=RecallBudget(shelf_size=12, token_budget=2400,
                                               self_fraction=0.5),
                           view="working_set", journal=False)
    assert r.handles  # the identity core is there...
    assert all(h.kind != "claim" for h in r.handles)
    assert all("spark-engram" not in h.title for h in r.handles)

    # ...and the marker is still first-class at layer 1 (query + guard).
    from abstractmemory.store import TripleQuery
    markers = [a for a in store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))
               if isinstance(a.attributes, dict) and a.attributes.get("bookkeeping")]
    assert len(markers) == 1 and markers[0].attributes["title"] == "spark-engram v1"

    tampered = _spark()
    tampered["origin"] = "Rewritten origin story."
    with pytest.raises(ValueError, match="kept for life"):
        engram(system, tampered, owner_id=OWNER)  # G8/marker scan still works


def test_close_then_render_closure_wins_and_as_of_restores(system) -> None:
    """Maintainer round 4, the mechanical confirmation: a CLOSED value whose
    prompt-active binding is untouched is excluded from self_records AND
    from the reconstruct self component (closure fold wins over binding
    state) — and the journal's time axis IS the versioning: an as-of read
    anchored BEFORE the closure still shows the value ("what did I believe
    at time T")."""
    result = engram(system, _spark(), owner_id=OWNER)
    revised = result.record_ids["values"][1]  # intellectual_honesty
    pre_closure = system.current_seq()

    # Close via the exceptional-repair/revision path; the binding stays ACTIVE.
    system.close_record(revised, reason="entity reflection: value revised")

    # Current reads: closure wins over the still-active binding.
    assert all(a.subject != revised for a in system.self_records(scope=SCOPE, owner_id=OWNER))
    now = system.reconstruct(Stimulus(cue_text=""), scopes=[(SCOPE, OWNER)],
                             budget=RecallBudget(self_fraction=0.5, shelf_size=12),
                             view="working_set", journal=False)
    now_ids = {h.provenance.get("record_id") for h in now.handles}
    assert revised not in now_ids
    assert any(h.admission == "self" for h in now.handles)  # the rest of the core stands

    # As-of read anchored BEFORE the closure: the value renders again —
    # folds.reconstruction_inputs anchors closure AND binding folds to as_of.
    then = system.reconstruct(Stimulus(cue_text="", as_of=pre_closure),
                              scopes=[(SCOPE, OWNER)],
                              budget=RecallBudget(self_fraction=0.5, shelf_size=12),
                              view="working_set", journal=False)
    then_ids = {h.provenance.get("record_id") for h in then.handles}
    assert revised in then_ids
    revised_handle = next(h for h in then.handles if h.provenance.get("record_id") == revised)
    assert revised_handle.admission == "self"


def test_self_records_is_the_folded_identity_read(system) -> None:
    """Ask 3: prompt-active AND closure-folded, identity kinds only, ordered
    kind rank -> precedence -> record id (the prelude's proper read — the
    layer-1 query() passthrough it replaces bypasses both folds)."""
    result = engram(system, _spark(), owner_id=OWNER)
    rows = system.self_records(scope=SCOPE, owner_id=OWNER)
    kinds = [a.attributes["record_kind"] for a in rows]
    assert kinds == sorted(kinds, key=lambda k: {"value": -3, "purpose": -2, "trait": -1}[k])
    assert len(rows) == 6
    values = [a for a in rows if a.attributes["record_kind"] == "value"]
    assert [a.attributes["precedence"] for a in values] == [0, 1, 2]  # ordinal order
    assert values[0].attributes["title"] == "shared_vulnerability"

    # Closure fold: a retracted value never renders (query() would keep it).
    retired = result.record_ids["values"][2]
    system.close_record(retired, reason="revised after reflection")
    after = system.self_records(scope=SCOPE, owner_id=OWNER)
    assert all(a.subject != retired for a in after) and len(after) == 5

    # Binding fold: rebinding a record inactive removes it from the core.
    demoted = result.record_ids["traits"][0]
    system.bind(demoted, scope=SCOPE, owner_id=OWNER, search_state="indexed",
                prompt_state="inactive", source="revision", reason="quieting a trait")
    assert all(a.subject != demoted for a in system.self_records(scope=SCOPE, owner_id=OWNER))


def test_engram_lint_errors_abort_warnings_pass_through(system) -> None:
    broken = _spark()
    broken["values"] = [v for v in broken["values"] if v["name"] != "shared_vulnerability"]
    with pytest.raises(ValueError, match="shared_vulnerability"):
        engram(system, broken, owner_id=OWNER)

    # Warnings do not block; they ride the result.
    warny = _spark()
    warny["values"] = [
        {"name": "shared_vulnerability", "class": "core",
         "statement": v["statement"]}
        for v in warny["values"] if v["name"] == "shared_vulnerability"
    ]  # only core values -> zero-revisable WARNING
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore")
        result = engram(system, warny, owner_id="entity-2")
    assert any("no revisable value" in w for w in result.warnings)
    assert result.created is True


def test_engram_refuses_a_vectorless_core_under_a_pinned_space() -> None:
    """Wave-4b adversary P1-1 (live-repro'd): formation now degrades to
    vectorless on a dead embedder — but a BIRTH is not a mid-life turn.
    A vectorless identity core under a pinned space is a failed birth
    that idempotency would lock in forever; the engram refuses loudly
    with both repair paths named. Pinless stores stay legal (vectorless
    homes are a deliberate mode)."""
    import warnings as _w

    import pytest

    from abstractmemory import (
        DEFAULT_SPARK_TEMPLATE,
        InMemoryJournal,
        InMemoryTripleStore,
        MemorySystem,
        engram,
    )

    class DeadEmbedder:
        model = "dead-model"
        def embed_texts(self, texts):
            raise RuntimeError("HTTP 400: model not loaded")

    with _w.catch_warnings():
        _w.simplefilter("ignore", RuntimeWarning)
        pinned = MemorySystem(
            store=InMemoryTripleStore(embedder=DeadEmbedder(),
                                      embedding_pin={"model_id": "dead-model",
                                                     "dimension": 4}),
            journal=InMemoryJournal())
        with pytest.raises(ValueError, match="VECTORLESS under a pinned"):
            engram(pinned, spark=DEFAULT_SPARK_TEMPLATE,
                   scope="self", owner_id="entity:refused")

        # Pinless + no embedder: the legal vectorless mode is untouched.
        plain = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())
        result = engram(plain, spark=DEFAULT_SPARK_TEMPLATE,
                        scope="self", owner_id="entity:plain")
        assert result.created is True


def test_default_spark_titles_never_collide_across_sections() -> None:
    """c5260 (flow's life-loop adversary): the default spark minted the
    trait AND the limit both titled "trait-0" (honesty shares
    kind="trait"), turning identity records into a duplicate-title
    group. Fallback stems are section-derived now: limit-N for honesty."""
    from abstractmemory import (
        DEFAULT_SPARK_TEMPLATE,
        InMemoryJournal,
        InMemoryTripleStore,
        MemorySystem,
        TripleQuery,
        engram,
    )

    system = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())
    engram(system, spark=DEFAULT_SPARK_TEMPLATE, scope="self", owner_id="entity:n")
    titles = []
    for a in system.store.query(TripleQuery(scope="self", owner_id="entity:n", limit=0)):
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        if a.predicate == "dcterms:abstract" and not attrs.get("bookkeeping"):
            titles.append(str(attrs.get("title") or ""))
    assert len(titles) == len(set(titles)), f"colliding identity titles: {titles}"
    assert "limit-0" in titles and "trait-0" in titles
