"""Prospective memory: open_commitments + triggered_commitments.

A commitment is the ENTITY'S OWN remembered promise elected into its diary
("next time I talk to Ada, ask about her paper"). Nothing executes it — it
SURFACES at the right moment (person appears, topic matches, date passes)
so the entity can keep its word or consciously let it go. The lived failure
this repairs: visit commitments died at the next generic wake cue.

Fixtures honor the D4 form-gate (diary records declare their write channel:
"owner-direct" / "diary-projection"+entry_id) and run on BOTH layer-1
stacks via the shared `stack`/`system` conftest fixtures.
"""

from __future__ import annotations

import pytest

from abstractmemory import Stimulus
from abstractmemory.diary import open_commitments, open_questions, triggered_commitments
from abstractmemory.records import MemoryRecordInput
from abstractmemory.store import TripleQuery

DIRECT = {"source": "owner-direct"}


def _elect_commitment(system, *, key: str, title: str, gist: str,
                      trigger=None, scope: str = "session", owner_id: str = "s1",
                      provenance=None, extra_attrs=None) -> str:
    """One commitment election as the diary lane writes it (graph plane)."""
    attributes = {"diary_type": "commitment"}
    if trigger is not None:
        attributes["trigger"] = trigger
    if extra_attrs:
        attributes.update(extra_attrs)
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="diary", title=title, digest=gist,
                           attributes=attributes,
                           provenance=dict(provenance or DIRECT))],
        scope=scope, owner_id=owner_id, idempotency_key=key)
    return gid


def _fulfill(system, *, key: str, ref: str, scope: str = "session",
             owner_id: str = "s1") -> str:
    """Append-only fulfillment: a later diary entry references the
    commitment via attributes.fulfills (graph id OR book entry_id)."""
    [gid] = system.remember_many(
        [MemoryRecordInput(kind="diary", title="Kept my word",
                           digest="I did what I promised.",
                           attributes={"diary_type": "reflection", "fulfills": ref},
                           provenance=DIRECT)],
        scope=scope, owner_id=owner_id, idempotency_key=key)
    return gid


# --- open_commitments: sibling semantics (the _open_unresolved fold) --------


def test_open_commitments_lifecycle(system, stack) -> None:
    """Mirrors open_questions/open_problems: unresolved only, oldest first;
    fulfillment is append-only via attributes.fulfills referencing EITHER
    the graph record id or the book entry_id; fulfilled commitments stay
    retrievable ("I promised, then I kept my word")."""
    store, journal = stack
    c1 = _elect_commitment(system, key="c-1", title="Ask Ada about her paper",
                           gist="Next time I talk to Ada, ask about her paper.")
    # A projection commitment (book plane): D4 requires entry_id.
    c2 = _elect_commitment(
        system, key="c-2", title="Send Bram the dataset",
        gist="I promised Bram the cleaned dataset.",
        provenance={"source": "diary-projection"},
        extra_attrs={"entry_id": "diary_c2"})

    listed = open_commitments(store, scope="session", owner_id="s1")
    assert [a.subject for a in listed] == [c1, c2]  # oldest first, both open

    # Fulfill c1 by GRAPH id, c2 by BOOK entry_id — both namespaces are
    # honest references (the sibling convention).
    _fulfill(system, key="c-1-done", ref=c1)
    assert [a.subject for a in open_commitments(store, scope="session", owner_id="s1")] == [c2]
    _fulfill(system, key="c-2-done", ref="diary_c2")
    assert open_commitments(store, scope="session", owner_id="s1") == []

    # Fulfilled commitments remain retrievable as ordinary records.
    assert store.query(TripleQuery(subject=c1, limit=0))
    assert store.query(TripleQuery(subject=c2, limit=0))

    # Distinct types: a commitment never lists as a question (and the
    # question lane is untouched by fulfillment traffic).
    assert open_questions(store, scope="session", owner_id="s1") == []


def test_open_commitments_folded_read_excludes_closed(system, stack) -> None:
    """Sibling fold semantics: with the journal, a CLOSED commitment is not
    open; the layer-1 read (no journal) honestly still lists it."""
    store, journal = stack
    c1 = _elect_commitment(system, key="cf-1", title="Water the plants",
                           gist="I said I would water the plants.")
    system.close_record(c1, reason="let it go consciously")
    assert open_commitments(store, scope="session", owner_id="s1", journal=journal) == []
    assert [a.subject for a in open_commitments(store, scope="session", owner_id="s1")] == [c1]


def test_fulfills_formation_validation_mirrors_siblings() -> None:
    """attributes.fulfills must be a non-empty string when present — the
    same loud formation gate answers/resolves already have."""
    with pytest.raises(ValueError, match="fulfills"):
        MemoryRecordInput(kind="diary", title="t", digest="d",
                          attributes={"fulfills": "  "}, provenance=DIRECT)


# --- triggered_commitments: the annotation read ------------------------------


def test_ada_scenario_end_to_end(system, stack) -> None:
    """The motivating case: elect "ask Ada about her paper" with a
    participant trigger; N unrelated events later, Ada appears in a
    stimulus — the line surfaces with the matched participant AND the
    election date (dated handles are a visit-honesty requirement)."""
    store, journal = stack
    gid = _elect_commitment(
        system, key="ada-1", title="Ask Ada about her paper",
        gist="Next time I talk to Ada, ask about her paper.",
        trigger={"participants": ["person:ada"], "keywords": ["paper"]})

    # Life goes on: unrelated episodes between election and encounter.
    for i in range(4):
        system.remember_many(
            [MemoryRecordInput(kind="episode", title=f"Routine turn {i}",
                               digest=f"An ordinary exchange number {i}.")],
            scope="session", owner_id="s1", idempotency_key=f"ep-{i}")

    # A generic wake cue names nobody: the commitment stays silent
    # (exactly the failure mode this feature repairs — it must fire on
    # the RIGHT moment, not on every wake).
    quiet = triggered_commitments(
        store, journal, stimulus=Stimulus(cue_text="morning wake cue"),
        scope="session", owner_id="s1")
    assert quiet == []

    # Ada appears.
    hits = triggered_commitments(
        store, journal,
        stimulus=Stimulus(cue_text="hello again", participants=("person:ada",)),
        scope="session", owner_id="s1")
    assert len(hits) == 1
    hit = hits[0]
    assert hit["entry"].subject == gid
    assert hit["matched"] == ["participant:person:ada"]
    elected_date = str(hit["entry"].observed_at)[:10]
    assert hit["line"] == (
        f"standing intention (elected {elected_date}): "
        "Next time I talk to Ada, ask about her paper. [matched: person:ada]")


def test_keyword_trigger_case_and_accent_insensitive(system, stack) -> None:
    """Keyword matching is a folded word match against the cue text: case
    and accents fold (text_tokens.fold_text), multi-word keywords need all
    their words present, and elected short terms (below the recall floor)
    still match — the entity chose them deliberately."""
    store, journal = stack
    gid = _elect_commitment(
        system, key="kw-1", title="Follow up on the article",
        gist="Ask about the article when the topic comes up.",
        trigger={"keywords": ["café", "her paper", "gpu"]})

    # Accent + case fold: "café" matches "CAFE".
    hits = triggered_commitments(
        store, journal, stimulus=Stimulus(cue_text="Shall we meet at the CAFE?"),
        scope="session", owner_id="s1")
    assert [h["matched"] for h in hits] == [["keyword:café"]]
    assert "[matched: keyword:café]" in hits[0]["line"]

    # Multi-word keyword: every word must appear (word match, not substring).
    hits = triggered_commitments(
        store, journal,
        stimulus=Stimulus(cue_text="Ada published her new paper yesterday"),
        scope="session", owner_id="s1")
    assert hits[0]["matched"] == ["keyword:her paper"]
    # One word alone is not the elected phrase.
    assert triggered_commitments(
        store, journal, stimulus=Stimulus(cue_text="I need more paper for the printer... her?"),
        scope="session", owner_id="s1")[0]["matched"] == ["keyword:her paper"]

    # Short elected term (3 chars, below the recall floor of 4) still fires.
    hits = triggered_commitments(
        store, journal, stimulus=Stimulus(cue_text="the GPU fans are loud"),
        scope="session", owner_id="s1")
    assert hits[0]["matched"] == ["keyword:gpu"]

    # An unrelated cue matches nothing.
    assert triggered_commitments(
        store, journal, stimulus=Stimulus(cue_text="completely unrelated topic"),
        scope="session", owner_id="s1") == []
    assert gid  # formed and stayed open throughout (annotation deposits nothing)


def test_due_trigger_honors_caller_supplied_now(system, stack) -> None:
    """due_at fires on due_at <= now with BOTH sides normalized to the
    canonical UTC form (the WAIT_UNTIL lexicographic invariant — a +02:00
    deadline must not fire late). now=None disables due matching entirely:
    the engine never reads the clock."""
    store, journal = stack
    _elect_commitment(
        system, key="due-1", title="Send the report",
        gist="I promised the report by July 10.",
        trigger={"due_at": "2026-07-10T02:00:00+02:00"})  # == 2026-07-10T00:00 UTC
    stim = Stimulus(cue_text="anything at all")

    # No now: silent (never a clock read inside the engine).
    assert triggered_commitments(store, journal, stimulus=stim,
                                 scope="session", owner_id="s1") == []
    # Before the due moment: silent.
    assert triggered_commitments(store, journal, stimulus=stim,
                                 scope="session", owner_id="s1",
                                 now="2026-07-09T23:59:59+00:00") == []
    # RAW-string lexicographic compare would wrongly stay silent here
    # ("...T02:00" > "...T01:00"); normalization makes it fire.
    hits = triggered_commitments(store, journal, stimulus=stim,
                                 scope="session", owner_id="s1",
                                 now="2026-07-10T01:00:00+00:00")
    assert [h["matched"] for h in hits] == [["due:2026-07-10T00:00:00.000000+00:00"]]
    assert "[matched: due:2026-07-10]" in hits[0]["line"]
    # Exactly-at-the-moment counts as passed; Z-suffix now is accepted.
    assert triggered_commitments(store, journal, stimulus=stim,
                                 scope="session", owner_id="s1",
                                 now="2026-07-10T00:00:00Z")[0]["matched"] == \
        ["due:2026-07-10T00:00:00.000000+00:00"]

    # Garbage caller now refuses loudly (boundary input).
    with pytest.raises(ValueError, match="ISO-8601"):
        triggered_commitments(store, journal, stimulus=stim,
                              scope="session", owner_id="s1", now="not-a-time")


def test_unparseable_stored_due_at_degrades_that_channel_only(system, stack) -> None:
    """Aged/foreign data must not kill the read: a garbage stored due_at
    skips the due channel with ONE labeled #FALLBACK warning; the other
    trigger channels still run for the same commitment."""
    store, journal = stack
    gid = _elect_commitment(
        system, key="bad-due", title="Ping Ada",
        gist="Ping Ada about the meetup.",
        trigger={"participants": ["person:ada"], "due_at": "next tuesday-ish"})
    with pytest.warns(RuntimeWarning, match="#FALLBACK"):
        hits = triggered_commitments(
            store, journal,
            stimulus=Stimulus(cue_text="", participants=("person:ada",)),
            scope="session", owner_id="s1", now="2026-07-13T00:00:00+00:00")
    assert [h["entry"].subject for h in hits] == [gid]
    assert hits[0]["matched"] == ["participant:person:ada"]  # due skipped, not fired


def test_empty_or_absent_trigger_never_annotates(system, stack) -> None:
    """A commitment without a trigger (or with an empty/contentless one) is
    listed by open_commitments only — it NEVER annotates, whatever the
    stimulus."""
    store, journal = stack
    c_none = _elect_commitment(system, key="e-1", title="Untethered promise",
                               gist="A promise with no trigger.")
    c_empty = _elect_commitment(system, key="e-2", title="Empty trigger",
                                gist="Trigger dict is empty.", trigger={})
    c_blank = _elect_commitment(system, key="e-3", title="Contentless trigger",
                                gist="Lists are empty.",
                                trigger={"participants": [], "keywords": []})

    everything = Stimulus(
        cue_text="promise trigger empty lists untethered contentless dict",
        participants=("person:ada", "person:bram"))
    assert triggered_commitments(store, journal, stimulus=everything,
                                 scope="session", owner_id="s1",
                                 now="2099-01-01T00:00:00+00:00") == []
    # ...while all three remain in the open set.
    assert [a.subject for a in open_commitments(store, scope="session", owner_id="s1")] == \
        [c_none, c_empty, c_blank]


def test_fulfilled_and_closed_commitments_never_trigger(system, stack) -> None:
    """triggered_commitments reads the OPEN set: fulfillment (by reference)
    and closure (journal fold) both silence the trigger."""
    store, journal = stack
    trig = {"participants": ["person:ada"]}
    c1 = _elect_commitment(system, key="ft-1", title="Ask Ada A",
                           gist="Ask Ada about A.", trigger=trig)
    c2 = _elect_commitment(system, key="ft-2", title="Ask Ada B",
                           gist="Ask Ada about B.", trigger=trig)
    _fulfill(system, key="ft-1-done", ref=c1)
    system.close_record(c2, reason="no longer relevant")

    stim = Stimulus(cue_text="", participants=("person:ada",))
    assert triggered_commitments(store, journal, stimulus=stim,
                                 scope="session", owner_id="s1") == []
    # Layer-1 read (journal=None): the closure fold is bypassed, so the
    # CLOSED one honestly still annotates; the FULFILLED one never does
    # (resolution is store truth, not a fold).
    layer1 = triggered_commitments(store, None, stimulus=stim,
                                   scope="session", owner_id="s1")
    assert [h["entry"].subject for h in layer1] == [c2]


def test_cap_and_suppressed_summary_line(system, stack) -> None:
    """Over-fire containment: oldest-first, capped at max_lines, ONE final
    summary element naming how many matched commitments were suppressed."""
    store, journal = stack
    gids = [
        _elect_commitment(system, key=f"cap-{i}", title=f"Promise {i}",
                          gist=f"Promise number {i}.",
                          trigger={"participants": ["person:ada"]})
        for i in range(5)
    ]
    stim = Stimulus(cue_text="", participants=("person:ada",))
    out = triggered_commitments(store, journal, stimulus=stim,
                                scope="session", owner_id="s1", max_lines=3)
    assert len(out) == 4  # 3 annotated + 1 summary
    assert [h["entry"].subject for h in out[:3]] == gids[:3]  # oldest first
    assert out[3] == {"entry": None, "matched": [],
                      "line": "2 more open commitments suppressed"}

    # max_lines=0: summary-only (everything matched, everything suppressed).
    only_summary = triggered_commitments(store, journal, stimulus=stim,
                                         scope="session", owner_id="s1", max_lines=0)
    assert only_summary == [{"entry": None, "matched": [],
                             "line": "5 more open commitments suppressed"}]
    # Under the cap: no summary element at all.
    assert len(triggered_commitments(store, journal, stimulus=stim,
                                     scope="session", owner_id="s1",
                                     max_lines=10)) == 5
    with pytest.raises(ValueError, match="max_lines"):
        triggered_commitments(store, journal, stimulus=stim,
                              scope="session", owner_id="s1", max_lines=-1)


def test_combined_trigger_reports_every_matched_channel(system, stack) -> None:
    """One commitment matching on several channels reports them all in one
    entry (participant, keyword, due — the spec's token order)."""
    store, journal = stack
    _elect_commitment(
        system, key="multi-1", title="Ask Ada about her paper before the deadline",
        gist="Ask Ada about her paper before July 10.",
        trigger={"participants": ["person:ada"], "keywords": ["paper"],
                 "due_at": "2026-07-10T00:00:00Z"})
    hits = triggered_commitments(
        store, journal,
        stimulus=Stimulus(cue_text="did you finish the paper?",
                          participants=("person:ada",)),
        scope="session", owner_id="s1", now="2026-07-12T00:00:00+00:00")
    assert hits[0]["matched"] == [
        "participant:person:ada", "keyword:paper",
        "due:2026-07-10T00:00:00.000000+00:00"]
    assert hits[0]["line"].endswith(
        "[matched: person:ada, keyword:paper, due:2026-07-10]")


def test_pure_read_invariants(system, stack) -> None:
    """Presentation-only: neither open_commitments nor triggered_commitments
    writes to the journal or deposits usage (access counts unchanged)."""
    store, journal = stack
    gid = _elect_commitment(
        system, key="pure-1", title="Ask Ada about her paper",
        gist="Next time I talk to Ada, ask about her paper.",
        trigger={"participants": ["person:ada"]})
    seq_before = journal.current_seq()
    counts_before = system.access_counts(record_ids=[gid])

    open_commitments(store, scope="session", owner_id="s1", journal=journal)
    hits = triggered_commitments(
        store, journal,
        stimulus=Stimulus(cue_text="hi", participants=("person:ada",)),
        scope="session", owner_id="s1", now="2026-07-13T00:00:00+00:00")
    assert len(hits) == 1  # the read worked...

    assert journal.current_seq() == seq_before, "pure read wrote to the journal"
    assert system.access_counts(record_ids=[gid]) == counts_before, \
        "annotation deposited usage — surfacing is not use"


def test_situate_tensions_fold_fulfills(system, stack) -> None:
    """Consistency across presentation reads: a FULFILLED commitment is not
    an open tension at a later anchor (situate folds attributes.fulfills
    exactly like answers/resolves)."""
    store, journal = stack
    c_open = _elect_commitment(system, key="st-1", title="Still standing",
                               gist="A promise not yet kept.")
    c_done = _elect_commitment(system, key="st-2", title="Kept already",
                               gist="A promise already kept.")
    _fulfill(system, key="st-2-done", ref=c_done)
    situation = system.situate(scopes=[("session", "s1")], seq=journal.current_seq())
    tension_ids = {t["graph_id"] for t in situation["tensions_then"]}
    assert c_open in tension_ids
    assert c_done not in tension_ids
