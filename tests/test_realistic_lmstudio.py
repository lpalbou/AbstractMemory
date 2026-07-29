"""Realistic integration tests against a LOCAL LMStudio server (real
embeddings, realistic prose — no toy three-word fixtures).

Scenario: tests/realistic_fixtures.py — a 12-turn assistant session about a
developer building "Hearth" (a local-first home-automation hub), with
personal facts (Chloé's piano recital Thursday), engineering decisions
(PostgreSQL over SQLite because of concurrent writers; Zigbee vs WiFi), a
mid-session tax detour, and a return to the project.

What is asserted (seam behavior on real embeddings):
  (a) semantic recall WITHOUT keyword overlap — vector channel only;
  (b) cross-turn continuity: a fact formed 9 turns earlier, with the tax
      detour in between, is still reachable via a related cue;
  (c) decay is behavioral: the tax-detour records exit the emergent working
      set (membership, not score) after the host returns to the project;
  (d) reactivation: an indirect "Thursday evening" cue re-lifts the piano
      fact, with channel attribution visible in cues;
  (e) determinism: pinned as_of + same stimulus -> byte-identical results.

Gating: marker `lmstudio` + module-level skip when the server or an
embedding model is unreachable (2s probe). The optional `lmstudio_llm` test
additionally uses the chat model as a JUDGE and skips on timeout. The
default suite therefore stays green with or without LMStudio.
"""

from __future__ import annotations

import json
import re
import time
import warnings
from dataclasses import dataclass
from typing import List

import pytest

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemorySystem,
    OpenAICompatTextEmbedder,
    Stimulus,
)
from abstractmemory.canonical_text import canonical_text
from abstractmemory.channels import tokenize

from realistic_fixtures import (
    FORMED_AT_TURN,
    MEMBERSHIP_BUDGET,
    OWNER,
    SCOPE,
    TURN_BUDGET,
    TURNS,
    SessionRunner,
    chat_completion,
    probe_lmstudio,
    strip_think_block,
)

# (f) needs Stimulus for a journaled read the union commit can label.

_PROBE = probe_lmstudio(timeout_s=2.0)

pytestmark = [
    pytest.mark.lmstudio,
    pytest.mark.skipif(
        not _PROBE.available,
        reason=(
            f"LMStudio unavailable at {_PROBE.base_url}: "
            f"{_PROBE.error or 'no embedding model served'}"
        ),
    ),
]


@dataclass
class SessionState:
    runner: SessionRunner
    embedder: OpenAICompatTextEmbedder
    working_set_after_detour: List[str]   # blank-cue membership right after turn 9
    working_set_at_end: List[str]         # blank-cue membership after full session
    turn_seconds: float


@pytest.fixture(scope="module")
def session() -> SessionState:
    """Run the full host loop ONCE per module (embedding calls are
    real network work); tests then assert with pure journal=False probes."""
    embedder = OpenAICompatTextEmbedder(_PROBE.base_url, _PROBE.embed_model, timeout_s=60.0)
    store = InMemoryTripleStore(embedder=embedder)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # volatility #FALLBACK, asserted elsewhere
        journal = InMemoryJournal()
    system = MemorySystem(store=store, journal=journal, embedder=embedder)
    runner = SessionRunner(system)

    started = time.monotonic()
    runner.run_turns(TURNS[:9])                       # ...through the tax detour
    after_detour = runner.blank_working_set_labels()  # (c) first membership probe
    runner.run_turns(TURNS[9:])                       # return to the project
    elapsed = time.monotonic() - started
    at_end = runner.blank_working_set_labels()        # (c) second membership probe

    return SessionState(
        runner=runner,
        embedder=embedder,
        working_set_after_detour=after_detour,
        working_set_at_end=at_end,
        turn_seconds=elapsed,
    )


# ---------------------------------------------------------------------------
# (a) semantic recall without keyword overlap
# ---------------------------------------------------------------------------


def test_semantic_recall_without_keyword_overlap(session: SessionState) -> None:
    """'what did we decide about data storage?' shares NO indexable token
    with the Postgres decision's canonical text, yet the decision is
    retrieved — real-embedding semantic recall through the vector channel."""
    cue = "what did we decide about data storage?"
    result = session.runner.probe(cue, budget=TURN_BUDGET, trace_id="probe-a")

    handle = session.runner.handle_for(result, "postgres-decision")
    assert handle is not None, (
        f"Postgres decision not retrieved; got {[h.title for h in result.handles]}"
    )
    # handle.digest is the CANONICAL text ("<graph-id> dcterms:abstract <prose>"),
    # so the prose is asserted by containment, not prefix.
    assert "Chose PostgreSQL over SQLite for the hub" in handle.digest

    # Prove the retrieval could not have come from token overlap: the cue and
    # the record's canonical text (what the keyword channel scans and the
    # store embedded) share zero tokens, and the keyword channel scored it 0.
    overlap = set(tokenize(cue)) & set(tokenize(handle.digest))
    assert overlap == set(), f"fixture rot: cue/digest share tokens {overlap}"
    assert "keyword" not in handle.relevance
    assert "vector" in handle.relevance and handle.relevance["vector"] > 0.0
    assert any(c.startswith("vector: cosine") for c in handle.cues)


# ---------------------------------------------------------------------------
# (b) cross-turn continuity across the detour
# ---------------------------------------------------------------------------


def test_cross_turn_continuity_across_detour(session: SessionState) -> None:
    """The Pi-5 hardware constraint was formed and committed at turn 3; the
    probe runs after the full session — many turns later, with the storage
    debate, the radio debate, and the tax detour in between — and a related cue still
    reaches it."""
    assert FORMED_AT_TURN["pi-constraint"] == 3
    assert len(TURNS) - FORMED_AT_TURN["pi-constraint"] >= 8  # 8+ intervening turns

    cue = "remind me what hardware the hub is supposed to run on"
    result = session.runner.probe(cue, budget=TURN_BUDGET, trace_id="probe-b")

    handle = session.runner.handle_for(result, "pi-constraint")
    assert handle is not None, (
        f"Pi constraint not retrieved; got {[h.title for h in result.handles]}"
    )
    assert "Target hardware is a Raspberry Pi 5" in handle.digest
    assert "vector" in handle.relevance


# ---------------------------------------------------------------------------
# (c) decay is behavioral: the tax detour leaves the working set
# ---------------------------------------------------------------------------


def test_tax_detour_decays_out_of_working_memory(session: SessionState) -> None:
    """Membership, not score — and under the union, the blank-cue probe IS
    the STM view. Right after the tax turns the tax records sit in working
    memory (fresh usage trail). After enough post-detour project turns the
    tax records fall below the membership floor — decay under presence ≠ use
    (STM renders deposit nothing,
    so standing falls by pure activity displacement) — while storage never
    lost them: a tax cue still retrieves the tax answer via channels."""
    after, end = session.working_set_after_detour, session.working_set_at_end
    assert "tax-answer" in after, f"tax answer missing right after the detour: {after}"
    assert "homeoffice-answer" in after, f"home-office answer missing right after the detour: {after}"

    assert "tax-answer" not in end, f"tax answer still in working memory at end: {end}"
    assert "homeoffice-answer" not in end, f"home-office answer still in working memory at end: {end}"
    # The probe still sees a live working set (it did not just go empty):
    assert "locking-lesson" in end, f"end-of-session working set looks wrong: {end}"

    # Union-native reading (maintainer's model): the end-of-session STM
    # component holds project records, never the detour's tax records.
    stm_probe = session.runner.probe("", budget=MEMBERSHIP_BUDGET, trace_id="probe-c-stm")
    stm_labels = [
        session.runner.label_of(h) for h in stm_probe.handles if h.admission == "stm"
    ]
    assert stm_labels, "end-of-session STM component is empty"
    assert "tax-answer" not in stm_labels and "homeoffice-answer" not in stm_labels

    # Storage never decays: only retrieval standing does.
    recall = session.runner.probe(
        "what was that safe-harbor rule for my estimated taxes?",
        budget=TURN_BUDGET, trace_id="probe-c-recall",
    )
    tax = session.runner.handle_for(recall, "tax-answer")
    assert tax is not None
    assert "Increase the Q3 estimated payment" in tax.digest


# ---------------------------------------------------------------------------
# (d) reactivation by an indirect cue
# ---------------------------------------------------------------------------


def test_indirect_cue_reactivates_piano_fact(session: SessionState) -> None:
    """Ten turns after it was formed, an indirect scheduling question — no
    mention of Chloé, piano, or recital — re-lifts the piano fact, with
    channel attribution visible in the handle's cues."""
    cue = "what's happening Thursday evening — can I schedule the firmware flash then?"
    result = session.runner.probe(cue, budget=TURN_BUDGET, trace_id="probe-d")

    handle = session.runner.handle_for(result, "piano")
    assert handle is not None, (
        f"piano fact not reactivated; got {[h.title for h in result.handles]}"
    )
    assert "Sam's daughter Chloé has her piano recital" in handle.digest
    # The lift is explainable — the cues name the channel that carried it.
    # (canonical-text v2 + the baseline-relative vector floor: qwen puts this
    # cue/record pair AT its unrelated baseline, so the honest attribution is
    # the keyword channel — thursday/evening — and/or spread, not a
    # sub-baseline cosine that the floor now rightly clips.)
    assert (
        handle.activation["spread"] > 0.0
        or any(c.startswith(("vector: cosine", "keyword: matched")) for c in handle.cues)
    ), f"no channel/spread attribution in cues: {handle.cues}"
    # The recorded edge graph conducts: the working_set view surfaces the
    # prepares_for edge between the leave-early plan and the recital.
    # (.get: STM trail edges use the {"source": "stm_trail", "pair": …} shape.)
    assert any(e.get("predicate") == "prepares_for" for e in result.edges), (
        f"prepares_for edge not walked; edges={result.edges}"
    )


# ---------------------------------------------------------------------------
# (e) determinism under a pinned anchor
# ---------------------------------------------------------------------------


def test_pinned_as_of_same_cue_is_byte_identical(session: SessionState) -> None:
    """Pinned as_of + identical stimulus + same trace_id -> the two results
    serialize byte-identically (the engine's purity/replay contract; the cue
    embedding is computed once so the assertion tests the ENGINE, not the
    embedding server — whose bit-stability is reported, not assumed)."""
    cue = "what did we decide about data storage?"
    embedding = session.embedder.embed_texts([cue])[0]
    anchor = session.runner.system.current_seq()

    def run() -> dict:
        return session.runner.probe(
            cue, budget=TURN_BUDGET, embedding=embedding, as_of=anchor,
            trace_id="probe-e",
        ).to_dict()

    first, second = run(), run()
    assert first["as_of_seq"] == anchor
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["handles"], "determinism probe returned an empty working set"


# ---------------------------------------------------------------------------
# (f) the union working set, live (maintainer's model end-to-end)
# ---------------------------------------------------------------------------


def test_union_stm_component_live(session: SessionState) -> None:
    """After the full session: a blank-cue reconstruct returns a NON-EMPTY
    STM component (admission="stm") holding the most-committed project
    records; and once the piano fact is genuinely used again, a piano cue
    shows it as admission="both" (trail-hot AND stimulus-matched).
    NOTE: this test commits (mutates the shared session journal) — it is
    deliberately LAST in the module."""
    r = session.runner.probe("", budget=MEMBERSHIP_BUDGET, trace_id="probe-union")
    stm_labels = [
        session.runner.label_of(h) for h in r.handles if h.admission == "stm"
    ]
    assert stm_labels, "blank-cue STM component is empty after the full session"
    # The storage track dominated the commits — STM must reflect that use.
    assert set(stm_labels) & {
        "storage-question", "storage-answer", "postgres-decision",
        "storage-recap", "schema-plan", "ingest-lesson", "locking-lesson",
    }, f"STM holds none of the most-committed project records: {stm_labels}"
    assert "tax-answer" not in stm_labels  # the detour decayed out (test c)

    # Genuine re-use flips the piano fact to "both" on the next piano cue.
    cue = "when is Chloé's piano recital again?"
    system = session.runner.system
    first = system.reconstruct(
        Stimulus(cue_text=cue), scopes=[(SCOPE, OWNER)], budget=TURN_BUDGET,
        view="working_set", trace_id="union-piano-read",
    )
    piano = session.runner.handle_for(first, "piano")
    assert piano is not None, f"piano fact not retrieved by direct cue: {[h.title for h in first.handles]}"
    # Under burst-axis decay the piano fact may still sit above stm_floor (1.0)
    # from its turn-2 commit — channel match then yields "both" even before
    # this probe's commit. The deposit step must still lift standing.
    base_before = float(piano.activation["base_level"])
    assert piano.admission in ("stimulus", "both"), (
        f"unexpected admission {piano.admission!r} (base={base_before})"
    )
    system.commit_selection("union-piano-read", [piano.record_id])

    second = session.runner.probe(cue, budget=TURN_BUDGET, trace_id="probe-union-2")
    piano2 = session.runner.handle_for(second, "piano")
    assert piano2 is not None
    assert piano2.admission == "both", (
        f"expected both (trail-hot + matched), got {piano2.admission!r} "
        f"(base={piano2.activation['base_level']})"
    )
    assert float(piano2.activation["base_level"]) >= base_before


# ---------------------------------------------------------------------------
# optional: the chat model as a judge (skips on timeout/unavailability)
# ---------------------------------------------------------------------------


@pytest.mark.lmstudio_llm
def test_llm_judge_confirms_postgres_decision(session: SessionState) -> None:
    """Hand the (a)-probe working set to the local chat model and ask it —
    yes/no — whether the digests contain the Postgres decision. Exercises the
    full loop a host would run: reconstruct -> render digests -> LLM reads
    its working memory."""
    if not _PROBE.chat_model:
        pytest.skip(f"no ornith chat model among {len(_PROBE.model_ids)} served models")

    result = session.runner.probe(
        "what did we decide about data storage?", budget=TURN_BUDGET,
        trace_id="probe-judge",
    )
    digests = "\n".join(f"- {h.digest}" for h in result.handles)
    try:
        reply = chat_completion(
            _PROBE.base_url,
            _PROBE.chat_model,
            [
                {
                    "role": "system",
                    "content": (
                        "You are a strict verifier. Answer with exactly one word: "
                        "yes or no."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Here is the working-memory digest set an assistant "
                        "reconstructed for the question 'what did we decide about "
                        f"data storage?':\n{digests}\n\n"
                        "Does this set contain a decision to use PostgreSQL for "
                        "the hub? Answer yes or no."
                    ),
                },
            ],
            timeout_s=60.0,
        )
    except RuntimeError as e:
        pytest.skip(f"chat judge unavailable within 60s: {e}")

    verdict = strip_think_block(reply)
    words = [w for w in re.split(r"[^a-zA-Z]+", verdict.lower()) if w]
    if not words:
        pytest.skip(f"chat judge returned no parsable verdict: {reply!r}")
    assert words[0] == "yes", f"judge said {verdict!r} over digests:\n{digests}"
