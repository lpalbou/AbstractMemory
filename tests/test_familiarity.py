"""familiarity(): the pre-answer metamemory reflex (accepted 2026-07-13).

Contracts pinned here:
- one cheap pass answering "do I hold ANY trace near this topic, and how
  much?" — match DENSITY, never content: NO record id, graph id, digest
  text or title anywhere in the result (the anti-fabrication property: the
  read cannot be mistaken for retrieval);
- strength ladder is deterministic and configurable: none=0,
  weak=1..K, strong>K (K = strong_threshold, default 3);
- PURE READ: journal seq unchanged, access counts unchanged, store rows
  unchanged after N calls — a reflex, not a reach (no trace, no deposits);
- correlation kill-test: familiarity "strong" predicts probe() hits for
  the same stimulus; familiarity "none" predicts an empty probe;
- feelings composition: stimulus-relevant gradation targets (participants
  or cue-matched) surface with correct net + standing; absent journal is
  labeled; record-id targets never leak; feelings NEVER gate density;
- honesty warnings, verbatim: strength "none" carries "nothing within
  reach (newest-window scan; exact/vector reach whole store)"; a semantic
  cue on a vectorless stack carries "#FALLBACK: keyword-only familiarity".

Fixture: a compact realistic life (real-shaped digests — the Hearth-style
session vocabulary, not "abc") for entity:iris across "life" and "work"
scopes, with person:sam stamped on the shared family episodes.
"""

from __future__ import annotations

import json
import warnings as _w
from typing import Iterator, List, Sequence

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    Stimulus,
    TripleQuery,
)
from abstractmemory.probe import (
    FAMILIARITY_STRONG_THRESHOLD,
    familiarity as familiarity_fn,
)

OWNER = "entity:iris"
LIFE = "life"
WORK = "work"
SCOPES = [(LIFE, OWNER), (WORK, OWNER)]

# --- the realistic fixture life ---------------------------------------------

# (kind, title, digest, keywords, participants) — family thread: TWO records
# (the weak band), stamped with the visitor who lived them.
FAMILY_RECORDS = (
    ("episode", "Chloé's piano recital (Thursday)",
     "Sam's daughter Chloé has her piano recital on Thursday evening at 18:00 "
     "in the school auditorium; Sam plans to head out by 17:00.",
     ("chloé", "recital", "thursday"), ("person:sam", "entity:iris")),
    ("plan", "Leave early on Thursday",
     "Wrap up work early on Thursday: out the door by 17:00 to reach the "
     "auditorium before the recital starts.",
     ("thursday", "recital"), ("person:sam", "entity:iris")),
)

# Storage thread: FIVE records (the strong band), four in "life" + one in
# "work" so by_scope has two honest buckets.
STORAGE_LIFE_RECORDS = (
    ("question", "SQLite or PostgreSQL for the hub?",
     "Open question: SQLite or PostgreSQL for the hub's state and event "
     "history, given the concurrent write patterns we expect.",
     ("sqlite", "postgresql"), ()),
    ("answer", "Prototype hit SQLite's writer lock",
     "SQLite's single-writer lock stalled the prototype whenever sensor "
     "ingest and the rule engine wrote at the same moment.",
     ("sqlite", "lock"), ()),
    ("decision", "PostgreSQL over SQLite for the hub",
     "Chose PostgreSQL over SQLite for the hub's state store because sensor "
     "ingest, the rule engine, and mobile app sync write concurrently.",
     ("postgresql",), ()),
    ("plan", "Hub database schema draft",
     "Draft schema: a devices table, device_state keyed by device id, and an "
     "append-only events table partitioned by month in PostgreSQL.",
     ("schema", "postgresql"), ()),
)
STORAGE_WORK_RECORDS = (
    ("lesson", "Batch sensor inserts",
     "Batch sensor readings into one PostgreSQL transaction every two "
     "seconds; per-reading inserts saturated the SD card on the hub.",
     ("ingest", "postgresql"), ()),
)

STRONG_CUE = "postgresql storage writer lock"        # matches all 5 storage records
WEAK_CUE = "piano recital thursday"                  # matches the 2 family records
NONE_CUE = "sailing regatta off the brittany coast"  # matches nothing


def _remember(system: MemorySystem, specs, *, scope: str, key: str) -> List[str]:
    records = [
        MemoryRecordInput(kind=kind, title=title, digest=digest,
                          keywords=keywords, participants=participants)
        for kind, title, digest, keywords, participants in specs
    ]
    return system.remember_many(records, scope=scope, owner_id=OWNER,
                                idempotency_key=key)


def _seed_life(system: MemorySystem) -> List[str]:
    ids = _remember(system, FAMILY_RECORDS, scope=LIFE, key="fam-family")
    ids += _remember(system, STORAGE_LIFE_RECORDS, scope=LIFE, key="fam-storage-life")
    ids += _remember(system, STORAGE_WORK_RECORDS, scope=WORK, key="fam-storage-work")
    return ids


def _all_rows(system: MemorySystem):
    rows = []
    for scope, owner in SCOPES:
        rows.extend(system.store.query(TripleQuery(scope=scope, owner_id=owner, limit=0)))
    return rows


def _walk_strings(obj) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            yield from _walk_strings(v)


# --- strength ladder ---------------------------------------------------------


def test_strength_transitions_none_weak_strong(system) -> None:
    """The ladder: 0 -> none; 1..K -> weak; >K -> strong (K default 3)."""
    empty = system.familiarity(Stimulus(cue_text=STRONG_CUE), scopes=SCOPES)
    assert empty["strength"] == "none"
    assert empty["distinct_records"] == 0

    _seed_life(system)

    weak = system.familiarity(Stimulus(cue_text=WEAK_CUE), scopes=SCOPES)
    assert weak["strength"] == "weak"
    assert 1 <= weak["distinct_records"] <= FAMILIARITY_STRONG_THRESHOLD

    strong = system.familiarity(Stimulus(cue_text=STRONG_CUE), scopes=SCOPES)
    assert strong["strength"] == "strong"
    assert strong["distinct_records"] > FAMILIARITY_STRONG_THRESHOLD

    none = system.familiarity(Stimulus(cue_text=NONE_CUE), scopes=SCOPES)
    assert none["strength"] == "none"
    assert none["distinct_records"] == 0


def test_strength_threshold_is_configurable_and_validated(system) -> None:
    """K is a documented parameter, never a buried constant: the same 2-match
    cue reads weak at K=3 and strong at K=1; a K below 1 refuses loudly."""
    _seed_life(system)
    default = system.familiarity(Stimulus(cue_text=WEAK_CUE), scopes=SCOPES)
    assert default["strength"] == "weak"
    lowered = system.familiarity(Stimulus(cue_text=WEAK_CUE), scopes=SCOPES,
                                 strong_threshold=1)
    assert lowered["strength"] == "strong"
    assert lowered["distinct_records"] == default["distinct_records"]
    with pytest.raises(ValueError, match="strong_threshold"):
        system.familiarity(Stimulus(cue_text=WEAK_CUE), scopes=SCOPES,
                           strong_threshold=0)


def test_per_channel_and_by_scope_counts(system) -> None:
    """per_channel carries every channel that RAN (0 = ran, matched nothing;
    absent = did not run); by_scope counts distinct admitted rows per scope."""
    _seed_life(system)
    r = system.familiarity(Stimulus(cue_text=STRONG_CUE), scopes=SCOPES)
    assert r["per_channel"].get("keyword", 0) == r["distinct_records"] == 5
    # No patterns/anchors -> exact never ran; no participants named -> the
    # participants channel never ran: both ABSENT, not zero.
    assert "exact" not in r["per_channel"]
    assert "participants" not in r["per_channel"]
    assert r["by_scope"] == {LIFE: 4, WORK: 1}

    # Every searched scope is reported, zero included: "nothing in scope X"
    # is exactly the statement the reflex exists to make.
    none = system.familiarity(Stimulus(cue_text=NONE_CUE), scopes=SCOPES)
    assert none["by_scope"] == {LIFE: 0, WORK: 0}

    # Naming participants runs the shared-context channel: density from
    # co-presence alone, no topical cue needed.
    p = system.familiarity(Stimulus(cue_text="", participants=("person:sam",)),
                           scopes=SCOPES)
    assert p["per_channel"].get("participants") == 2
    assert p["distinct_records"] == 2
    assert p["strength"] == "weak"
    assert p["by_scope"] == {LIFE: 2, WORK: 0}


# --- density-honest floors (live A/B calibration, 2026-07-13) ----------------


class _FixedEmbedder:
    """Stub placing every GARDEN-flavored text at a controlled ~0.30 cosine
    to the cue axis [1,0,0] (the measured gibberish-baseline class)."""

    def embed_texts(self, texts):
        out = []
        for t in texts:
            if "garden" in str(t).lower():
                out.append([0.30, 0.9539392, 0.0])   # unit length; cos=0.30 to cue
            else:
                out.append([1.0, 0.0, 0.0])
        return out


def test_low_cosine_vector_matches_do_not_count_toward_density() -> None:
    """The live A/B failure class pinned: probe's ranking-relative vector
    floor admits the TOP of ANY field (gibberish admitted rows at cosine
    0.31 on the lived home), so without an absolute bar "none" was
    unreachable and the anti-fabrication line could never fire. A vector
    admission below FAMILIARITY_VECTOR_MIN must not count toward density
    — and the drop is labeled (weaker echoes exist, recall may surface
    them)."""
    cue_vec = [1.0, 0.0, 0.0]
    store = InMemoryTripleStore(embedder=_FixedEmbedder())
    system = MemorySystem(store=store, journal=InMemoryJournal())
    system.remember_many(
        [MemoryRecordInput(
            kind="episode", title="Garden bed reframed",
            digest="The hub garden bed was reframed with cedar planks yesterday.")],
        scope=LIFE, owner_id=OWNER, idempotency_key="veclow")

    stim = Stimulus(cue_text="sailing regatta brittany", embedding=cue_vec)
    r = familiarity_fn(store, stimulus=stim, scopes=[(LIFE, OWNER)])
    assert r["strength"] == "none", r
    assert r["distinct_records"] == 0
    assert any("weaker echo" in w for w in r["warnings"]), r["warnings"]
    # The same admission COUNTS when the caller lowers the bar (parameter,
    # not policy): the floor is calibration, never a hidden gate.
    lowered = familiarity_fn(store, stimulus=stim, scopes=[(LIFE, OWNER)],
                             vector_min=0.2)
    assert lowered["strength"] == "weak"


class _MidBandEmbedder:
    """Stub placing every GARDEN-flavored text at a controlled ~0.50 cosine
    to the cue axis [1,0,0] — the NONSENSE-ADJACENT band measured live on
    Ephemeral's production home (2026-07-17: gibberish cues admitted rows
    at 0.475-0.542 in the qwen3-0.6b space and read STRONG at the old
    0.45 bar)."""

    def embed_texts(self, texts):
        out = []
        for t in texts:
            if "garden" in str(t).lower():
                out.append([0.50, 0.8660254, 0.0])   # unit length; cos=0.50 to cue
            else:
                out.append([1.0, 0.0, 0.0])
        return out


def test_mid_band_cosines_do_not_count_at_the_recalibrated_bar() -> None:
    """The 2026-07-17 recalibration pinned: the 0.45→0.55 move exists
    because the nonsense band of a real embedder space sits at ~0.48-0.54
    on a lived store — a 0.50-cosine admission must NOT count at the
    default bar (fabricated familiarity), while the old 0.45 bar remains
    reachable as an explicit parameter (calibration, never a hidden
    gate)."""
    cue_vec = [1.0, 0.0, 0.0]
    store = InMemoryTripleStore(embedder=_MidBandEmbedder())
    system = MemorySystem(store=store, journal=InMemoryJournal())
    system.remember_many(
        [MemoryRecordInput(
            kind="episode", title="Garden shed inventory",
            digest="Counted the garden shed tools and ordered replacement gloves.")],
        scope=LIFE, owner_id=OWNER, idempotency_key="vecmid")

    stim = Stimulus(cue_text="zorblat quixotic fenwick turbine", embedding=cue_vec)
    r = familiarity_fn(store, stimulus=stim, scopes=[(LIFE, OWNER)])
    assert r["strength"] == "none", r
    assert any("weaker echo" in w for w in r["warnings"])
    old_bar = familiarity_fn(store, stimulus=stim, scopes=[(LIFE, OWNER)],
                             vector_min=0.45)
    assert old_bar["strength"] == "weak"


def test_single_incidental_keyword_counts_only_without_vector_rejection(system) -> None:
    """Corroboration-or-exclusivity: one matched token is honest
    familiarity on a VECTORLESS home (keywords are the only reach — the
    #FALLBACK label already says so), but must not read as knowing the
    topic when the semantic channel ran and rejected the row (the
    incidental-token class: "office", "from")."""
    _seed_life(system)
    # One token ("thursday") matches the family records; vectorless stack
    # => exclusivity arm: counts.
    r = system.familiarity(Stimulus(cue_text="thursday regatta"), scopes=SCOPES)
    assert r["per_channel"].get("keyword", 0) >= 1
    assert r["strength"] != "none"


def test_multi_token_keyword_matches_count_at_the_default_bar(system) -> None:
    """2+ matched tokens meet FAMILIARITY_MIN_KEYWORD_TOKENS on their own —
    no corroboration needed (the default bar's intended pass case)."""
    _seed_life(system)
    two = system.familiarity(Stimulus(cue_text="piano recital"), scopes=SCOPES)
    assert two["strength"] != "none"
    assert two["per_channel"].get("keyword", 0) >= 1


# --- the anti-fabrication property -------------------------------------------


def test_no_content_leaks_recursively(system) -> None:
    """Density, never content: no record id (either namespace), digest text,
    or title appears anywhere in the result dict — recursively, keys
    included. The result must also stay plain-JSON (a reflex's output is
    prompt/wire currency)."""
    graph_ids = _seed_life(system)
    forbidden: List[str] = list(graph_ids)
    for a in _all_rows(system):
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        forbidden.extend(x for x in (
            a.assertion_id, a.subject, a.object, str(attrs.get("title") or ""),
        ) if isinstance(x, str) and x)

    for cue in (STRONG_CUE, WEAK_CUE, NONE_CUE):
        result = system.familiarity(
            Stimulus(cue_text=cue, participants=("person:sam",)), scopes=SCOPES)
        json.dumps(result)  # plain dict, JSON-safe
        for s in _walk_strings(result):
            for f in forbidden:
                assert f not in s, (
                    f"familiarity leaked content: {f!r} inside {s!r}")


# --- pure read ---------------------------------------------------------------


def test_pure_read_journals_nothing_and_deposits_nothing(system) -> None:
    """A reflex, not a reach: after N calls the journal seq is unchanged
    (no trace, no audit events), access counts are unchanged (no deposits),
    and the store carries the same rows (no writes)."""
    ids = _seed_life(system)
    # Valence on a participant so the feelings path genuinely executes.
    system.appraise("person:sam", sign=1, magnitude=2.0,
                    reason="shared the recital plan", scope=LIFE, owner_id=OWNER)

    seq_before = system.current_seq()
    counts_before = system.access_counts(record_ids=ids)
    rows_before = {a.assertion_id for a in _all_rows(system)}

    for _ in range(3):
        system.familiarity(
            Stimulus(cue_text=STRONG_CUE, participants=("person:sam",)),
            scopes=SCOPES)
        system.familiarity(Stimulus(cue_text=NONE_CUE), scopes=SCOPES)

    assert system.current_seq() == seq_before, "familiarity wrote to the journal"
    assert system.access_counts(record_ids=ids) == counts_before, (
        "familiarity deposited usage")
    assert {a.assertion_id for a in _all_rows(system)} == rows_before, (
        "familiarity mutated the store")


# --- the correlation kill-test ------------------------------------------------


def test_familiarity_predicts_probe_at_fixture_scale(system) -> None:
    """familiarity counts the SAME pass probe ranks: "strong" must predict
    probe hits for the same stimulus, "none" an empty probe (journal=False:
    the prediction check itself must not perturb the fixture)."""
    _seed_life(system)

    strong = system.familiarity(Stimulus(cue_text=STRONG_CUE), scopes=SCOPES)
    assert strong["strength"] == "strong"
    reach = system.probe(Stimulus(cue_text=STRONG_CUE), scopes=SCOPES,
                         reason="correlation kill-test: verify the density reading",
                         journal=False)
    assert reach.hits, "familiarity said strong; probe found nothing"

    none = system.familiarity(Stimulus(cue_text=NONE_CUE), scopes=SCOPES)
    assert none["strength"] == "none"
    empty = system.probe(Stimulus(cue_text=NONE_CUE), scopes=SCOPES,
                         reason="correlation kill-test: verify the none reading",
                         journal=False)
    assert not empty.hits, "familiarity said none; probe found hits"


# --- feelings (the gradation composition) -------------------------------------


def test_feelings_surface_for_participants_with_correct_net(system) -> None:
    _seed_life(system)
    system.appraise("person:sam", sign=1, magnitude=2.0,
                    reason="shared the recital plan openly",
                    scope=LIFE, owner_id=OWNER)
    system.appraise("person:sam", sign=1, magnitude=2.0,
                    reason="took the storage pushback well",
                    scope=LIFE, owner_id=OWNER)
    r = system.familiarity(
        Stimulus(cue_text=WEAK_CUE, participants=("person:sam",)), scopes=SCOPES)
    [feeling] = [f for f in r["feelings"] if f["target"] == "person:sam"]
    assert feeling["net"] == 4.0
    assert feeling["standing"] == "none"


def test_feelings_surface_for_cue_matched_targets_with_standing(system) -> None:
    """Keyword-matched gradation targets ride the cue ("tool:web_search"
    matches "web search"), and standing markers surface: an unhealed scar
    caps presentation at net <= 0 and reads standing="scar"."""
    _seed_life(system)
    system.appraise("tool:web_search", sign=-1, magnitude=2.0, scar=True,
                    reason="fabricated results burned a visit",
                    scope=LIFE, owner_id=OWNER)
    r = system.familiarity(
        Stimulus(cue_text="web search results for the hub docs"), scopes=SCOPES)
    [feeling] = [f for f in r["feelings"] if f["target"] == "tool:web_search"]
    assert feeling["standing"] == "scar"
    assert feeling["net"] <= 0.0
    # Unrelated standing targets stay out: relevance to THIS stimulus only.
    system.appraise("place:atelier", sign=1, magnitude=1.0,
                    reason="quiet mornings", scope=LIFE, owner_id=OWNER)
    again = system.familiarity(
        Stimulus(cue_text="web search results for the hub docs"), scopes=SCOPES)
    assert all(f["target"] != "place:atelier" for f in again["feelings"])


def test_feelings_never_gate_density(system) -> None:
    """Valence never gates (ruled): density is bit-identical with and
    without feelings in the stream — presentation info only."""
    _seed_life(system)
    before = system.familiarity(Stimulus(cue_text=STRONG_CUE), scopes=SCOPES)
    system.appraise("topic:postgresql", sign=-1, magnitude=3.0,
                    reason="the migration weekend hurt", scope=LIFE, owner_id=OWNER)
    after = system.familiarity(Stimulus(cue_text=STRONG_CUE), scopes=SCOPES)
    assert after["distinct_records"] == before["distinct_records"]
    assert after["per_channel"] == before["per_channel"]
    assert after["by_scope"] == before["by_scope"]
    assert after["strength"] == before["strength"]


def test_feelings_skip_record_id_targets(system) -> None:
    """Record-targeted feelings (valence targets may be record ids) must
    never surface here: a record id in the output would break the
    no-content property. The word-shaped target still surfaces."""
    graph_ids = _seed_life(system)
    system.appraise(graph_ids[0], sign=1, magnitude=2.0,
                    reason="that recital evening mattered",
                    scope=LIFE, owner_id=OWNER)
    system.appraise("moment:recital", sign=1, magnitude=1.0,
                    reason="the recital evening", scope=LIFE, owner_id=OWNER)
    r = system.familiarity(Stimulus(cue_text=WEAK_CUE), scopes=SCOPES)
    targets = [f["target"] for f in r["feelings"]]
    assert graph_ids[0] not in targets
    assert "moment:recital" in targets


def test_feelings_without_journal_are_empty_and_labeled(system) -> None:
    """The module-level function skips feelings without a journal, loudly —
    gradation reads the valence stream, so absence is a labeled degradation,
    never a silent empty."""
    _seed_life(system)
    r = familiarity_fn(system.store, stimulus=Stimulus(cue_text=WEAK_CUE),
                       scopes=SCOPES, journal=None)
    assert r["feelings"] == []
    assert any("#FALLBACK" in w and "feelings" in w for w in r["warnings"])
    # Density still works journal-less (the count needs only the store).
    assert r["strength"] == "weak"


# --- honesty warnings ----------------------------------------------------------


def test_none_carries_the_window_honesty_warning(system) -> None:
    """"none" is a statement about REACH, not about the whole store: the
    keyword/participant scans cover only the newest candidate window per
    scope, and the warning says so verbatim."""
    _seed_life(system)
    r = system.familiarity(Stimulus(cue_text=NONE_CUE), scopes=SCOPES)
    assert r["strength"] == "none"
    assert ("nothing within reach (newest-window scan; exact/vector reach "
            "whole store)") in r["warnings"]
    # A non-none read does NOT carry it.
    strong = system.familiarity(Stimulus(cue_text=STRONG_CUE), scopes=SCOPES)
    assert all("nothing within reach" not in w for w in strong["warnings"])


def test_vectorless_stack_carries_keyword_only_fallback(system) -> None:
    """The conftest stacks have no embedder anywhere: a semantic cue that
    cannot vector-search is a labeled degradation, verbatim."""
    _seed_life(system)
    r = system.familiarity(Stimulus(cue_text=STRONG_CUE), scopes=SCOPES)
    assert "#FALLBACK: keyword-only familiarity" in r["warnings"]


def test_vector_capable_stack_counts_vector_and_drops_the_fallback() -> None:
    """With a real vector path the fallback disappears and the vector
    channel contributes density keyword cannot see ("gallery" finds the
    museum record without sharing a token)."""

    class MarkerEmbedder:
        def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
            out: List[List[float]] = []
            for t in texts:
                low = str(t).lower()
                if "museum" in low:
                    out.append([1.0, 0.0, 0.0])
                elif "gallery" in low:
                    out.append([1.0, 1.0, 0.0])  # cosine ~0.707 vs museum
                else:
                    out.append([0.0, 0.0, 1.0])
            return out

    store = InMemoryTripleStore(embedder=MarkerEmbedder())
    with _w.catch_warnings():
        _w.simplefilter("ignore", RuntimeWarning)
        journal = InMemoryJournal()
    vec_system = MemorySystem(store=store, journal=journal,
                              embedder=MarkerEmbedder())
    vec_system.remember_many([
        MemoryRecordInput(
            kind="episode", title="Afternoon in the museum",
            digest="We spent the afternoon in the museum's impressionist "
                   "wing, sketching from the Caillebotte room.",
            keywords=("museum",)),
        MemoryRecordInput(
            kind="episode", title="Batch cooking Sunday",
            digest="Sunday afternoon went to batch cooking soups for the "
                   "week and labeling the freezer boxes.",
            keywords=("cooking",)),
    ], scope=LIFE, owner_id=OWNER, idempotency_key="fam-vector-seed")

    r = vec_system.familiarity(Stimulus(cue_text="gallery paintings"),
                               scopes=[(LIFE, OWNER)])
    assert r["per_channel"].get("vector") == 1
    assert r["distinct_records"] == 1
    assert r["strength"] == "weak"
    assert "#FALLBACK: keyword-only familiarity" not in r["warnings"]
