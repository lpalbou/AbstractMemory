"""LIVE PROOF script — memory's rows of the plan proof ledger (a2a 0014).

Runs the memory-lane behavior demos on a REAL fixture home and prints a
numbered proof transcript; artifacts (the home's .sqlite3, a JSON report)
are left on disk for inspection. Every step asserts — a broken invariant
exits nonzero. This is a DEMO of behavior, not a unit test: refusal texts
print verbatim, counts print before/after.

Rows covered (ledger a2a/threads/0014-plan-proofs):
- item 3 (M1): creation pin as birth choice; WRONG embedder refused at
  open; wrong-dimension write refused with ZERO rows; labeled vectorless
  read (recall answers on keyword with the #FALLBACK visible).
- item 3 (M1b): reembed repair — dimension change, pin swapped LAST,
  journaled claim record visible in the replay stream, vectorless rows
  backfilled.
- item 1 (M2): a visit-held home REFUSES a maintenance window naming the
  holder; the pass runs under one maintenance window and releases per-pass
  (flock probe). Skipped with a label when abstractruntime is absent.
- items 2+6 (M3): clean `entity:<name>` and legacy `entity:<name>@home-x`
  keys coexist in one store with zero cross-talk (recall/gradation/replay).

Usage:
    python examples/entity_home_maintenance_proof.py [--home DIR] [--live]

Default embedders are deterministic stubs (runs anywhere, offline).
--live uses LMStudio via OpenAICompatTextEmbedder: pin at birth with
text-embedding-qwen3-embedding-0.6b (1024d), repair onto
text-embedding-qwen3-embedding-4b (2560d) — the plan's named pair.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any, List, Sequence

# Monorepo bootstrap (same pattern as tests/conftest.py).
_ROOT = Path(__file__).resolve().parents[1]
for p in (str(_ROOT / "src"), str(_ROOT.parent / "abstractruntime" / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from abstractmemory import (  # noqa: E402
    DEFAULT_SPARK_TEMPLATE,
    MemorySystem,
    OpenAICompatTextEmbedder,
    SQLiteJournal,
    SQLiteTripleStore,
    Stimulus,
    engram,
    export_replay,
    reembed_store,
)
from abstractmemory.records import MemoryRecordInput  # noqa: E402
from abstractmemory.store import TripleQuery  # noqa: E402

CLEAN_OWNER = "entity:demo"
LEGACY_OWNER = "entity:demo@home-legacy1"
SCOPE = "life"

_step = 0
_report: List[dict] = []


def proof(title: str, detail: str) -> None:
    global _step
    _step += 1
    print(f"\nPROOF {_step}: {title}\n  {detail}")
    _report.append({"step": _step, "title": title, "detail": detail})


class StubEmbedder:
    """Deterministic offline embedder with a declared identity."""

    def __init__(self, model: str, dimension: int) -> None:
        self.model = model
        self._dim = int(dimension)

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        out = []
        for t in texts:
            seed = float((sum(ord(c) for c in str(t)) % 83) + 1)
            out.append([seed] + [1.0] * (self._dim - 1))
        return out


def build_embedders(live: bool):
    if not live:
        return StubEmbedder("stub-embed-a", 4), StubEmbedder("stub-embed-b", 8), \
            StubEmbedder("stub-embed-WRONG", 4)
    base = "http://127.0.0.1:1234/v1"
    return (
        OpenAICompatTextEmbedder(base, "text-embedding-qwen3-embedding-0.6b"),
        OpenAICompatTextEmbedder(base, "text-embedding-qwen3-embedding-4b"),
        OpenAICompatTextEmbedder(base, "text-embedding-nomic-embed-text-v1.5"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=None,
                        help="fixture home dir (default: a fresh temp dir, kept)")
    parser.add_argument("--live", action="store_true",
                        help="use LMStudio embedders (0.6b birth pin, 4b repair)")
    args = parser.parse_args()

    home = args.home or Path(tempfile.mkdtemp(prefix="memory-proof-home-"))
    home.mkdir(parents=True, exist_ok=True)
    for stale in home.glob("*.sqlite3*"):
        stale.unlink()
    db = home / "memory.sqlite3"
    born_embedder, repair_embedder, wrong_embedder = build_embedders(args.live)
    print(f"Fixture home: {home}  (artifacts stay on disk for inspection)")

    # ---- M1: the pin is a BIRTH choice -----------------------------------
    store = SQLiteTripleStore(db, embedder=born_embedder,
                              embedding_pin={"model_id": born_embedder.model})
    journal = SQLiteJournal(db)
    system = MemorySystem(store=store, journal=journal, embedder=born_embedder)
    engram(system, DEFAULT_SPARK_TEMPLATE, scope="self", owner_id=CLEAN_OWNER)
    [ep1] = system.remember_many(
        [MemoryRecordInput(kind="episode", title="Harbor walk",
                           digest="Walked the harbor at noon and watched the cranes.")],
        scope=SCOPE, owner_id=CLEAN_OWNER, idempotency_key="p-ep1")
    pin = store.embedding_pin()
    assert pin["model_id"] == born_embedder.model and pin["source"] == "creation"
    proof("M1 creation pin written at birth",
          f"pin={json.dumps(pin)} — model declared at creation; dimension "
          f"{pin['dimension']} locked by the first embedded write")

    # ---- M1: WRONG embedder refused at OPEN ------------------------------
    store.close(); journal.close()
    try:
        SQLiteTripleStore(db, embedder=wrong_embedder)
        raise AssertionError("wrong-model open was NOT refused")
    except ValueError as e:
        proof("M1 wrong embedder refused at open (loud, names both models)",
              f"refusal: {e}")

    # ---- M1: wrong-DIMENSION write refused with zero rows ----------------
    sneaky = StubEmbedder(born_embedder.model, 3) if not args.live else None
    if sneaky is not None:  # same declared model, wrong vectors — the hard case
        store = SQLiteTripleStore(db, embedder=sneaky)
        journal = SQLiteJournal(db)
        system = MemorySystem(store=store, journal=journal)
        before = len(store.query(TripleQuery(limit=0)))
        try:
            system.remember_many(
                [MemoryRecordInput(kind="episode", title="Should never land",
                                   digest="A wrong-space write.")],
                scope=SCOPE, owner_id=CLEAN_OWNER, idempotency_key="p-bad1")
            raise AssertionError("wrong-dimension write was NOT refused")
        except ValueError as e:
            after = len(store.query(TripleQuery(limit=0)))
            assert before == after
            proof("M1 wrong-dimension write refused, ZERO rows landed",
                  f"rows before={before} after={after}; refusal: {e}")
        store.close(); journal.close()
    else:
        proof("M1 wrong-dimension write (live mode)",
              "SKIPPED #FALLBACK: live servers cannot fake a wrong-dim batch "
              "under the same model id; the offline run covers this row")

    # ---- M1: labeled vectorless READ (no embedder; recall still answers) --
    store = SQLiteTripleStore(db)  # no embedder: read-only degradation path
    journal = SQLiteJournal(db)
    system = MemorySystem(store=store, journal=journal)
    result = system.reconstruct(Stimulus(cue_text="harbor cranes noon"),
                                scopes=[(SCOPE, CLEAN_OWNER)], trace_id="p-t1")
    fallback = [w for w in result.warnings if "#FALLBACK" in w and "vector" in w]
    assert fallback and any(h.title == "Harbor walk" for h in result.handles)
    proof("M1 labeled vectorless read — recall degrades LOUDLY, still answers",
          f"warning: {fallback[0]} | recalled: "
          f"{[h.title for h in result.handles][:3]}")
    store.close(); journal.close()

    # ---- M2 + M1b: lease windows around the reembed repair ---------------
    store = SQLiteTripleStore(db, embedder=born_embedder)
    journal = SQLiteJournal(db)
    system = MemorySystem(store=store, journal=journal, embedder=born_embedder)
    try:
        from abstractruntime.identity.lease import (
            HomeLeaseHeld, acquire_home_lease, read_home_lease)
    except ImportError:
        proof("M2 lease composition",
              "SKIPPED #FALLBACK: abstractruntime checkout not importable — "
              "the lease primitive lives there (plan seat split)")
        result_reembed = reembed_store(system, embedder=repair_embedder,
                                      owner_id=CLEAN_OWNER)
    else:
        visit = acquire_home_lease(home, holder="visit-host", session_id="chat-demo")
        try:
            acquire_home_lease(home, holder="maintenance")
            raise AssertionError("maintenance acquired while visit held the home")
        except HomeLeaseHeld as e:
            proof("M2 visit-held home REFUSES a maintenance window",
                  f"refusal names the holder: {e}")
        finally:
            visit.release()
        with acquire_home_lease(home, holder="maintenance", run_id="reembed-demo"):
            result_reembed = reembed_store(system, embedder=repair_embedder,
                                          owner_id=CLEAN_OWNER)
        state = read_home_lease(home)
        assert state is not None and state["held"] is False
        proof("M2 maintenance window released per-pass (flock probe)",
              f"lease state after the pass: held={state['held']} "
              f"(last holder: {state.get('holder')})")

    new_pin = store.embedding_pin()
    assert new_pin["model_id"] == repair_embedder.model and new_pin["source"] == "reembed"
    assert result_reembed["vectored"] >= 1
    proof("M1b reembed swapped the space atomically, pin LAST",
          f"old={json.dumps(result_reembed['old_pin'])} -> new={json.dumps(new_pin)}; "
          f"{result_reembed['vectored']} rows re-vectored, "
          f"{result_reembed['skipped_edges']} edge rows honestly vectorless")

    marker_id = result_reembed["marker_record_id"]
    stream_hit = [e for e in export_replay(store, journal, owner_id=CLEAN_OWNER)
                  if e["family"] == "binding" and e["payload"].get("record_id") == marker_id]
    assert stream_hit
    proof("M1b the act is JOURNALED — visible in the replay stream",
          f"claim record {marker_id} formation binding at stream seq "
          f"{stream_hit[0]['seq']} (old->new model ids ride its attributes)")

    # ---- M3: clean + legacy keys coexist, zero cross-talk ----------------
    engram(system, DEFAULT_SPARK_TEMPLATE, scope="self", owner_id=LEGACY_OWNER)
    system.remember_many(
        [MemoryRecordInput(kind="episode", title="Legacy harbor walk",
                           digest="The legacy life also walked the harbor at noon.")],
        scope=SCOPE, owner_id=LEGACY_OWNER, idempotency_key="p-ep2")
    clean_recall = system.reconstruct(Stimulus(cue_text="harbor walk noon"),
                                      scopes=[(SCOPE, CLEAN_OWNER)], trace_id="p-t2")
    assert clean_recall.handles
    assert all(h.owner_id == CLEAN_OWNER for h in clean_recall.handles)
    clean_core = {a.subject for a in system.self_records(scope="self", owner_id=CLEAN_OWNER)}
    legacy_core = {a.subject for a in system.self_records(scope="self", owner_id=LEGACY_OWNER)}
    assert clean_core and legacy_core and clean_core.isdisjoint(legacy_core)
    leaked = [e for e in export_replay(store, journal, owner_id=CLEAN_OWNER)
              if e.get("owner_id") not in (CLEAN_OWNER, "", None)]
    assert leaked == []
    proof("M3 clean and legacy owner keys coexist with ZERO cross-talk",
          f"'{CLEAN_OWNER}' and '{LEGACY_OWNER}' share a prefix; identity cores "
          f"disjoint ({len(clean_core)} vs {len(legacy_core)} records); recall and "
          "replay each serve exactly one owner (exact-string matching, never prefixes)")

    store.close(); journal.close()
    report_path = home / "proof_report.json"
    report_path.write_text(json.dumps(
        {"home": str(home), "live": bool(args.live), "proofs": _report}, indent=2),
        encoding="utf-8")
    print(f"\nALL {_step} PROOFS HELD. Report: {report_path}")
    return 0


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("default")
        sys.exit(main())
