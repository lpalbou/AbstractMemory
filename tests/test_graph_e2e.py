"""End to end on a temporary SQLite home, no mocks (ADR 0003 "Validation", second bullet; backlog 0056).

Two consumer-shaped clients write into ONE mind through `abstractmemory.graph`, each on its OWN connections to the
home file (as two processes would): a notebook client ("abstractnote": every claim names the applying tool step
`(run_id, seq)` and the note body's artifact) and an entity client ("entity:ex:person-x": a diary entry and its turn
step, then a reflection derived from memories with no sources of its own). The test reads what a host reads:
`history`, `sources_of(transitive)`, `derived_from_source(step)` and `(run)`, the change feed, the journal closures
and `TripleQuery(active_at=)`; and an ungrounded write is refused and leaves every table of the file as it was.

Mutants (applied by hand to src/abstractmemory/graph/graph.py; each turned this test red):
- `_SQLiteTx.add_source`: no-op                        -> derived_from_source / sources_of assertions
- `_SQLiteTx.add_derivation`: no-op                    -> the reflection's transitive sources
- `apply_revision`: the narrow branch's `add_history` removed -> the history sequence asserted -> closed -> narrowed
- `_prepare`: the per-memory `is_grounded` refusal AND `_validate`'s ungrounded refusal removed -> the third refused
  write (a grounded revision carrying a memory with an empty provenance) goes through
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from abstractmemory import SQLiteJournal, SQLiteTripleStore, TripleQuery
from abstractmemory.graph import MemoryGraph, ProvenanceRequired, Revision, RevisionOp

from graph_support import T, file_state, graph_tables


class NotebookClient:
    """AbstractNote-shaped: a note is captured by a run, its body is an artifact of that run, and a tool step
    extracts claims from it (contract §7: sources = [step ref, artifact ref], extra = {note_id, revision_id,
    evidence_quote}, actor = "abstractnote")."""

    actor = "abstractnote"

    def __init__(self, home: Path) -> None:
        self.store = SQLiteTripleStore(home)
        self.journal = SQLiteJournal(home)
        self.graph = MemoryGraph(self.store, self.journal)

    def _prov(self, run_id: str, seq: int, note_id: str, quote: str) -> Dict[str, Any]:
        return {"sources": [{"kind": "step", "run_id": run_id, "seq": seq, "step_id": f"extract-{seq}"},
                            {"kind": "artifact", "artifact_id": f"art-{note_id}", "run_id": run_id}],
                "actor": self.actor, "reader": "lmstudio/qwen3",
                "extra": {"note_id": note_id, "revision_id": f"nrev-{note_id}", "evidence_quote": quote}}

    def apply(self, rid: str, *ops: RevisionOp, run_id: str, seq: int, note_id: str, quote: str, cause: str,
              occurred_at: str) -> Any:
        return self.graph.apply_revision(Revision(
            revision_id=rid, scope="global", owner_id="abstractnote", cause=cause, occurred_at=occurred_at,
            ops=ops, provenance=self._prov(run_id, seq, note_id, quote), summary=f"note {note_id}"))

    def close(self) -> None:
        self.journal.close()
        self.store.close()


class EntityClient:
    """AbstractEntity-shaped: a diary entry of the entity's turn (diary_entry ref + the turn's step), and a
    reflection DERIVED from memories, with no ledger source of its own."""

    actor = "entity:ex:person-x"

    def __init__(self, home: Path) -> None:
        self.store = SQLiteTripleStore(home)
        self.journal = SQLiteJournal(home)
        self.graph = MemoryGraph(self.store, self.journal)

    def remember(self, rid: str, aid: str, s: str, p: str, o: str, *, run_id: str, seq: int, entry_id: str,
                 occurred_at: str) -> Any:
        prov = {"sources": [{"kind": "step", "run_id": run_id, "seq": seq},
                            {"kind": "diary_entry", "entry_id": entry_id, "run_id": "diary:ex:person-x"}],
                "actor": self.actor, "extra": {"turn_id": f"turn-{seq}"}}
        return self.graph.apply_revision(Revision(
            revision_id=rid, scope="global", owner_id="entity:ex:person-x", cause="ingest", occurred_at=occurred_at,
            ops=(RevisionOp("assert", {"assertion_id": aid, "subject": s, "predicate": p, "object": o}),),
            provenance=prov))

    def reflect(self, rid: str, aid: str, s: str, p: str, o: str, *, derived_from: List[str],
                provenance: Optional[Dict[str, Any]] = None) -> Any:
        prov = provenance or {"derived_from": derived_from, "actor": self.actor, "reason": "reflection"}
        return self.graph.apply_revision(Revision(
            revision_id=rid, scope="global", owner_id="entity:ex:person-x", cause="maintenance",
            occurred_at=T(10), ops=(RevisionOp("assert", {"assertion_id": aid, "subject": s, "predicate": p,
                                                          "object": o, "provenance": prov}),),
            provenance=prov))

    def close(self) -> None:
        self.journal.close()
        self.store.close()


def _counts(home: Path) -> Dict[str, int]:
    return {t: len(rows) for t, rows in graph_tables(home).items()}


def test_two_consumers_write_one_mind_and_read_it_back(tmp_path: Path) -> None:
    home = tmp_path / "plane" / "memory.sqlite3"
    note, entity = NotebookClient(home), EntityClient(home)
    try:
        # 1. A note (captured by run-cap, extracted at step 3) says Dana works at Acme.
        r1 = note.apply("nb-1", RevisionOp("assert", {
            "assertion_id": "c-acme", "subject": "ex:person-dana", "predicate": "schema:worksFor",
            "object": "ex:org-acme", "valid_from": T(1)}),
            run_id="run-cap-1", seq=3, note_id="n1", quote="Dana joined Acme in January", cause="ingest",
            occurred_at=T(1))
        assert r1.assertion_ids == ["c-acme"]
        # 2. The entity remembers meeting Dana (its own turn, its diary).
        entity.remember("en-1", "e-met", "ex:person-x", "ex:met", "ex:person-dana",
                        run_id="run-turn-7", seq=12, entry_id="de-7", occurred_at=T(2))
        # 3. A later note: Dana moved to Globex in June; the Acme claim is superseded by it.
        r3 = note.apply("nb-2",
                        RevisionOp("assert", {"assertion_id": "c-globex", "subject": "ex:person-dana",
                                              "predicate": "schema:worksFor", "object": "ex:org-globex",
                                              "valid_from": T(6)}),
                        RevisionOp("close", {"assertion_id": "c-acme", "valid_until": T(6), "kind": "supersede",
                                             "replacement_ids": ["c-globex"], "reason": "moved to Globex"}),
                        run_id="run-cap-2", seq=5, note_id="n2", quote="Dana started at Globex in June",
                        cause="ingest", occurred_at=T(6))
        assert r3.assertion_ids == ["c-globex"] and r3.closed == ["c-acme"]
        # 4. An EARLIER note, read again, dates the end of Acme in April: narrow the first claim.
        r4 = note.apply("nb-3", RevisionOp("narrow", {"assertion_id": "c-acme", "valid_until": T(4),
                                                      "reason": "the April note says Dana left Acme"}),
                        run_id="run-cap-3", seq=2, note_id="n0", quote="last day at Acme, April 1st",
                        cause="reinterpret", occurred_at=T(4))
        assert r4.narrowed == ["c-acme"]
        # 5. The entity reflects (no ledger source of its own), derived from ITS memory. Lineage never crosses
        #    owners (architect review B3): deriving from the notebook's claim is refused; what the entity learned
        #    from the notebook would enter as a source (the message or artifact it came through).
        with pytest.raises(ProvenanceRequired, match="lineage never crosses owners"):
            entity.reflect("en-x", "e-cross", "ex:person-dana", "ex:careerPattern", "ex:changes-jobs",
                           derived_from=["e-met", "c-globex"])
        r5 = entity.reflect("en-2", "e-insight", "ex:person-dana", "ex:careerPattern", "ex:changes-jobs",
                            derived_from=["e-met"])
        assert r5.assertion_ids == ["e-insight"]

        # --- reads, from either client (one mind) -------------------------------------------------------------
        for graph in (note.graph, entity.graph):
            history = graph.history("c-acme")
            assert [(h["event"], h["revision_id"], h["cause"]) for h in history] == [
                ("asserted", "nb-1", "ingest"), ("closed", "nb-2", "ingest"), ("narrowed", "nb-3", "reinterpret")]
            assert history[1]["detail"]["kind"] == "supersede"
            assert history[1]["detail"]["replacement_ids"] == ["c-globex"]
            assert history[2]["detail"] == {"valid_until": T(4), "previous_valid_until": T(6),
                                            "reason": "the April note says Dana left Acme"}
            assert [s.key() for s in graph.sources_of("e-insight")] == ["step:run-turn-7#12", "diary_entry:de-7"]
            assert graph.sources_of("e-insight", transitive=False) == []
            assert graph.derived_from_source({"kind": "step", "run_id": "run-cap-2", "seq": 5}) == ["c-globex"]
            assert graph.derived_from_source({"kind": "run", "run_id": "run-cap-1"}) == ["c-acme"]
            assert graph.derived_from_source({"kind": "run", "run_id": "run-turn-7"}) == ["e-met", "e-insight"]
            assert graph.derived_from_source({"kind": "diary_entry", "entry_id": "de-7"}) == ["e-met", "e-insight"]
            page, _ = graph.revisions()
            assert [(r.revision_id, r.provenance.actor) for r in page] == [
                ("nb-1", "abstractnote"), ("en-1", "entity:ex:person-x"), ("nb-2", "abstractnote"),
                ("nb-3", "abstractnote"), ("en-2", "entity:ex:person-x")]
            assert page[0].provenance.extra["evidence_quote"] == "Dana joined Acme in January"
        # The row's window and the journal agree.
        [acme] = note.store.query(TripleQuery(assertion_ids=("c-acme",)))
        assert acme.valid_until == T(4) and acme.provenance["actor"] == "abstractnote"
        # Event time: in May nothing says where Dana works (Acme ended in April, Globex starts in June); the
        # windowless reflection holds at any time.
        assert {a.assertion_id for a in note.store.query(
            TripleQuery(subject="ex:person-dana", active_at=T(5)))} == {"e-insight"}
        active_may = {a.assertion_id for a in note.store.query(
            TripleQuery(subject="ex:person-dana", predicate="schema:worksFor", active_at=T(5)))}
        active_mar = {a.assertion_id for a in note.store.query(
            TripleQuery(subject="ex:person-dana", predicate="schema:worksFor", active_at=T(3)))}
        assert active_may == set() and active_mar == {"c-acme"}
        [closure] = entity.journal.closures(assertion_id="c-acme", limit=0)
        assert (closure.kind, closure.replacement_ids, closure.provenance["revision_id"]) == (
            "supersede", ("c-globex",), "nb-2")

        # --- a write with neither sources nor derived_from: refused, nothing behind ---------------------------
        counts, state = _counts(home), file_state(home)
        assert set(counts) == {"triples", "memg_revisions", "memg_provenance", "memg_derivations", "memg_history"}
        assert counts["memg_revisions"] == 5 and counts["triples"] == 4
        with pytest.raises(ProvenanceRequired):
            entity.reflect("en-3", "e-bad", "ex:person-x", "ex:feels", "ex:unsure", derived_from=[],
                           provenance={"actor": entity.actor, "reason": "a thought from nowhere"})
        with pytest.raises(ProvenanceRequired):
            note.graph.apply_revision(Revision(
                revision_id="nb-bad", scope="global", owner_id="abstractnote", cause="ingest", occurred_at=T(7),
                ops=(RevisionOp("assert", {"assertion_id": "c-bad", "subject": "ex:person-dana",
                                           "predicate": "schema:livesIn", "object": "ex:paris"}),),
                provenance={"sources": [], "derived_from": [], "actor": "abstractnote"}))
        # A grounded revision does not ground a memory that names its own, empty, provenance.
        with pytest.raises(ProvenanceRequired):
            note.apply("nb-bad-2", RevisionOp("assert", {
                "assertion_id": "c-bad-2", "subject": "ex:person-dana", "predicate": "schema:livesIn",
                "object": "ex:lyon", "provenance": {"sources": [], "derived_from": [], "actor": "abstractnote"}}),
                run_id="run-cap-4", seq=1, note_id="n4", quote="?", cause="ingest", occurred_at=T(7))
        assert _counts(home) == counts
        assert file_state(home) == state
    finally:
        note.close()
        entity.close()
