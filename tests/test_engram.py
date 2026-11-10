"""The engram pass (keystone experiment, a2a 0003): spark → identity
records + prompt-active self bindings, idempotent and version-guarded.

BIRTH TITLES ARE AUTHORED (operator rule 2026-11-09/10; castor's two
"trait-0"): an item's `name` is its title as given; an unnamed item gets its
title from the host's `author(kind, body, context)` BEFORE it forms, else it
forms pending (`title.author` task + `pending.failure`), never a
`<stem>-<ordinal>` label. The summary is the spark statement (protected,
never asked for).

MUTATION LIST (scratch copy of src + this file, each mutant red, source
restored byte-exact): E1 the author is never called (every unnamed item
pending no_author_supplied); E2 the failure never reaches the marker
(pending_failure dropped); E3 the receipt is never filled; E4 the legacy
`<section stem>-<ordinal>` label comes back; E5 a named item is authored
too (its spark title replaced); E6 a replay authors again (no stored-row
check); E7 the summary is asked for too (the statement replaced); E8 a
replay ignores the stored title (input pending again, a spurious task).
"""

from __future__ import annotations

import copy
import warnings as warnings_module
from typing import Any, Dict, List

import pytest

from abstractmemory import RecallBudget, Stimulus, engram
from abstractmemory.records import resolve_digest_assertion
from abstractmemory.spark import DEFAULT_SPARK_TEMPLATE

SCOPE = "self"
OWNER = "entity-1"
MODEL = {"kind": "capability-model", "id": "summaries"}
READER = {"provider": "lmstudio", "model": "qwen/qwen3.8-27b", "thinking": False}
STEP = [{"kind": "artifact", "artifact_id": "authoring-call-1"}]
UNNAMED = ("purposes", "traits", "honesty")  # the default template names only its values
LEGACY_STEMS = ("value", "purpose", "trait", "limit")


class Author:
    """The host's authoring callable (formation_authoring contract): records each call; authors a title, raises,
    or returns `result` as told."""

    def __init__(self, *, fail: Exception = None, result: Any = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.fail, self.result = fail, result

    def __call__(self, kind: str, body: str, context: Dict[str, Any]) -> Any:
        self.calls.append({"kind": kind, "body": body, "context": dict(context)})
        if self.fail is not None:
            raise self.fail
        if self.result is not None:
            return self.result
        out: Dict[str, Any] = {"author": MODEL, "reader": READER, "sources": STEP}
        if "title" in context["fields"]:
            out["title"] = f"The {kind} I hold, {len(self.calls)}"
        if "summary" in context["fields"]:
            out["summary"] = f"A rewording of this {kind} ({len(self.calls)})."
        return out


def _is_legacy_birth_label(title: Any) -> bool:
    """docs/api.md's exact pattern: the whole title is `<stem>-<ASCII digits>`."""
    stem, sep, ordinal = str(title or "").partition("-")
    return bool(sep) and stem in LEGACY_STEMS and ordinal.isdigit() and ordinal.isascii()


def _row(system, gid: str):
    return resolve_digest_assertion(system.store, gid)


def _statements(spark: Dict[str, Any], section: str) -> List[str]:
    return [str(item["statement"]) for item in spark[section]]


def _title_tasks(system) -> List[str]:
    return sorted(t["target_id"] for t in system.tasks.tasks() if t["kind"] == "title.author")


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
    assert all("spark-engram" not in (h.title or "") for h in r.handles)

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
            journal=InMemoryJournal(), task_queue=True)
        with pytest.raises(ValueError, match="VECTORLESS under a pinned"):
            engram(pinned, spark=DEFAULT_SPARK_TEMPLATE,
                   scope="self", owner_id="entity:refused")

        # Pinless + no embedder: the legal vectorless mode is untouched.
        plain = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal(), task_queue=True)
        result = engram(plain, spark=DEFAULT_SPARK_TEMPLATE,
                        scope="self", owner_id="entity:plain")
        assert result.created is True


# --------------------------------------------------------------------------- birth titles: authored, never a label


def test_engram_author_titles_every_unnamed_item_with_provenance(system) -> None:
    spark = _spark()
    author = Author()
    result = engram(system, spark, owner_id=OWNER, author=author)

    # One call per UNNAMED item, the title only, from its statement, before it formed.
    assert [c["kind"] for c in author.calls] == ["purpose", "trait", "trait"]
    assert [c["body"] for c in author.calls] == [s for sec in UNNAMED for s in _statements(spark, sec)]
    for call in author.calls:
        ctx = call["context"]
        assert ctx["pass"] == "engram" and ctx["fields"] == ["title"] and ctx["title"] is None
        assert ctx["scope"] == SCOPE and ctx["owner_id"] == OWNER and ctx["source_ids"] == []
        assert ctx["attributes"]["spark_version"] == 1
    assert author.calls[2]["context"]["attributes"]["trait_class"] == "limit"  # the honesty item

    unnamed = [gid for sec in UNNAMED for gid in result.record_ids[sec]]
    for n, gid in enumerate(unnamed, start=1):
        attrs = _row(system, gid).attributes
        assert attrs["title"] == f"The {attrs['record_kind']} I hold, {n}" and "pending" not in attrs
        stamp = attrs["title_provenance"]
        assert stamp["author"] == MODEL and stamp["reader"]["model"] == READER["model"]
        assert stamp["sources"] == STEP and stamp["cause"] == {"cause": "formation"} and stamp["version"] == 0
        # The summary is the spark statement, the operator's words: never reworded, its reading the spark's.
        assert system.record_understanding(gid)["authored_by"] == {"kind": "operator", "id": "spark-v1"}
    assert [str(_row(system, g).object) for g in unnamed] == [s for sec in UNNAMED for s in _statements(spark, sec)]
    assert _title_tasks(system) == []
    assert result.authoring["failures"] == []
    assert [(a["record_id"], a["record_kind"], a["pass"], a["fields"]) for a in result.authoring["authored"]] == [
        (gid, _row(system, gid).attributes["record_kind"], "engram", ["title"]) for gid in unnamed]
    assert result.to_dict()["authoring"] == result.authoring


def test_engram_author_raising_forms_pending_with_the_failure(system) -> None:
    result = engram(system, _spark(), owner_id=OWNER, author=Author(fail=RuntimeError("model unloaded")))
    unnamed = [gid for sec in UNNAMED for gid in result.record_ids[sec]]
    for gid in unnamed:
        attrs = _row(system, gid).attributes
        assert attrs["title"] is None and "title_provenance" not in attrs
        marker = attrs["pending"]
        assert marker["title"] is True and marker["summary"] is False
        failure = marker["failure"]
        assert failure["reason"] == "author_raised" and failure["error_class"] == "RuntimeError"
        assert failure["message"] == "model unloaded" and failure["fields"] == ["title"] and failure["at"]
    assert _title_tasks(system) == sorted(unnamed)  # the night's repair writes each one
    assert result.authoring["authored"] == []
    assert [(f["record_id"], f["reason"], f["fields"]) for f in result.authoring["failures"]] == [
        (gid, "author_raised", ["title"]) for gid in unnamed]


def test_engram_without_author_forms_pending_no_author_supplied(system) -> None:
    result = engram(system, _spark(), owner_id=OWNER)
    unnamed = [gid for sec in UNNAMED for gid in result.record_ids[sec]]
    for gid in unnamed:
        attrs = _row(system, gid).attributes
        assert attrs["title"] is None
        failure = attrs["pending"]["failure"]
        assert failure["reason"] == "no_author_supplied" and failure["error_class"] is None
        assert "engram got no author callable" in failure["message"] and failure["fields"] == ["title"]
    assert _title_tasks(system) == sorted(unnamed)
    assert [f["reason"] for f in result.authoring["failures"]] == ["no_author_supplied"] * len(unnamed)


def test_engram_invalid_author_result_forms_pending(system) -> None:
    mechanical = {"title": "Asked first", "author": {"kind": "mechanical", "id": "x"}}
    result = engram(system, _spark(), owner_id=OWNER, author=Author(result=mechanical))
    [gid] = result.record_ids["traits"]
    failure = _row(system, gid).attributes["pending"]["failure"]
    assert failure["reason"] == "invalid_result" and "mechanical" in failure["message"]
    assert _row(system, gid).attributes["title"] is None


def test_engram_explicit_titles_are_kept_as_given(system) -> None:
    spark = _spark()
    for n, section in enumerate(UNNAMED):
        spark[section][0]["name"] = f"given_{section}_{n}"
    author = Author()
    result = engram(system, spark, owner_id=OWNER, author=author)
    assert author.calls == []  # nothing to author: every item is named
    assert result.authoring == {"authored": [], "failures": []}
    for section in ("values", *UNNAMED):
        for item, gid in zip(spark[section], result.record_ids[section]):
            attrs = _row(system, gid).attributes
            assert attrs["title"] == item["name"] and "pending" not in attrs and "title_provenance" not in attrs
            assert system.record_understanding(gid)["authored_by"] == {"kind": "operator", "id": "spark-v1"}
    assert _title_tasks(system) == []


@pytest.mark.parametrize("how", ["authored", "raised", "none"])
def test_engram_never_writes_a_birth_label(system, how) -> None:
    """Castor carries two "trait-0" (2026-07-07): no stored identity title is ever `<stem>-<ordinal>` again."""
    author = {"authored": Author(), "raised": Author(fail=OSError("down")), "none": None}[how]
    result = engram(system, _spark(), owner_id=OWNER, author=author)
    titles = [_row(system, gid).attributes["title"] for ids in result.record_ids.values() for gid in ids]
    assert len(titles) == 6 and not any(_is_legacy_birth_label(t) for t in titles)
    named = [t for t in titles if t is not None]
    assert len(named) == len(set(named))


def test_engram_replay_never_authors_again(system, stack) -> None:
    _, journal = stack
    first = engram(system, _spark(), owner_id=OWNER, author=Author())
    tasks_before = sorted(t["task_id"] for t in system.tasks.tasks())
    footprint = _journal_footprint(journal)

    again_author = Author()
    again = engram(system, _spark(), owner_id=OWNER, author=again_author)
    assert again.created is False and again.record_ids == first.record_ids
    assert again_author.calls == [] and again.authoring == {"authored": [], "failures": []}
    assert sorted(t["task_id"] for t in system.tasks.tasks()) == tasks_before  # no spurious title.author
    assert _journal_footprint(journal) == footprint
    gid = first.record_ids["traits"][0]
    assert _row(system, gid).attributes["title"] == "The trait I hold, 2"


def test_engram_replay_of_a_pending_birth_leaves_it_to_its_task(system) -> None:
    first = engram(system, _spark(), owner_id=OWNER)
    tasks_before = sorted(t["task_id"] for t in system.tasks.tasks())
    later = Author()
    again = engram(system, _spark(), owner_id=OWNER, author=later)
    assert later.calls == [] and again.authoring == {"authored": [], "failures": []}
    assert sorted(t["task_id"] for t in system.tasks.tasks()) == tasks_before
    assert _row(system, first.record_ids["purposes"][0]).attributes["title"] is None


def test_engram_on_a_home_without_a_task_queue() -> None:
    """A pending title needs the task that writes it: a queue-less home refuses an unauthored birth before anything
    is written, and takes an authored one."""
    from abstractmemory import InMemoryJournal, InMemoryTripleStore, MemorySystem, TripleQuery

    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore", RuntimeWarning)
        bare = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())
    with pytest.raises(ValueError, match="needs its authoring task"):
        engram(bare, _spark(), owner_id=OWNER)
    assert bare.store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0)) == []

    result = engram(bare, _spark(), owner_id=OWNER, author=Author())
    assert result.created is True and len(result.authoring["authored"]) == 3
