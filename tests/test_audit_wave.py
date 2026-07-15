"""Regression tests derived from the hostile-audit repros (2026-07-06 wave).

Each test cluster maps to one numbered fix and reproduces the audit scenario
it was derived from (/tmp/memaudit_{algo,persist,contract}/): thread safety +
atomic add, the id-namespace boundary, binding-fold correctness, edge-based
Hebbian trails, exclusion-aware gathering, budget-authoritative spreading,
edges-conduct-never-member, the vector floor, the strict-JSON boundary, and
the sharp edges (ttl, observed_at, tokenizer, seq guard).
"""

from __future__ import annotations

import json
import threading
import warnings as warnings_module
from datetime import datetime
from typing import Any, List

import pytest

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryEvent,
    MemorySystem,
    RecallBudget,
    SQLiteJournal,
    SQLiteTripleStore,
    Stimulus,
    TripleAssertion,
    TripleQuery,
)
from abstractmemory.attention import compute_activation, reinforce as reinforce_writer
from abstractmemory.channels import run_keyword_channel, tokenize
from abstractmemory.records import MemoryRecordInput

SCOPE = "session"
OWNER = "s1"
SCOPES = [(SCOPE, OWNER)]


def _ts(i: int) -> str:
    return f"2026-07-05T{10 + i // 60:02d}:{i % 60:02d}:00.000000+00:00"


def _assertion(aid: str, s: str, p: str, o: str, t: int, **attrs: Any) -> TripleAssertion:
    return TripleAssertion(subject=s, predicate=p, object=o, scope=SCOPE, owner_id=OWNER,
                           observed_at=_ts(t), attributes=dict(attrs), assertion_id=aid)


def _ids(result) -> List[str]:
    return [h.record_id for h in result.handles]


def _record(**kw: Any) -> MemoryRecordInput:
    defaults: dict[str, Any] = {"kind": "claim", "title": "T", "digest": "digest text"}
    defaults.update(kw)
    return MemoryRecordInput(**defaults)


# ---------------------------------------------------------------------------
# Fix 1 — store thread safety + atomic add (audit a1/s4)
# ---------------------------------------------------------------------------


def _run_in_thread(fn) -> None:
    errors: List[BaseException] = []

    def wrapper() -> None:
        try:
            fn()
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    t = threading.Thread(target=wrapper)
    t.start()
    t.join()
    assert errors == [], f"cross-thread use failed: {errors!r}"


def test_sqlite_store_usable_from_other_threads(tmp_path) -> None:
    """Audit a1: the store used to be constructed on the gateway main thread
    and CRASH from worker threads (check_same_thread)."""
    store = SQLiteTripleStore(tmp_path / "s.sqlite3")

    def work() -> None:
        store.add([_assertion("t-1", "alice", "wrote", "report", 1)])
        assert [a.assertion_id for a in store.query(TripleQuery(subject="alice"))] == ["t-1"]

    _run_in_thread(work)
    store.close()


def test_memory_system_seam_calls_from_worker_thread_over_sqlite(tmp_path) -> None:
    path = tmp_path / "m.sqlite3"
    system = MemorySystem(store=SQLiteTripleStore(path), journal=SQLiteJournal(path))

    def work() -> None:
        [gid] = system.remember_many([_record(digest="tokamak plasma containment")],
                                     scope=SCOPE, owner_id=OWNER, idempotency_key="t1")
        r = system.reconstruct(Stimulus(cue_text="tokamak plasma"), scopes=SCOPES)
        assert r.handles
        snap = system.commit_selection(r.trace_id, [gid])
        assert snap.used_record_ids

    _run_in_thread(work)
    system.close()


def test_partial_conflict_batch_never_leaks_into_later_commit(tmp_path) -> None:
    """Audit s4_leak_commit: a conflicting batch used to leave pre-conflict
    rows in an open transaction that a LATER unrelated add() flushed. add()
    is now one atomic transaction with INSERT OR IGNORE: the whole batch
    lands (duplicate ids skipped), nothing lingers, later adds are clean."""
    dbpath = tmp_path / "leak.sqlite3"
    store = SQLiteTripleStore(dbpath)
    store.add([_assertion("Y", "y", "p", "o", 1)])

    ids = store.add([
        _assertion("X", "x", "p", "o", 2),
        _assertion("Y", "y", "p", "duplicate", 3),  # id conflict: skipped, not fatal
        _assertion("Z", "z", "p", "o", 4),
    ])
    assert ids == ["X", "Y", "Z"]  # ids returned as before, conflicts included

    reader = SQLiteTripleStore(dbpath)  # separate connection = disk truth
    on_disk = sorted(a.assertion_id for a in reader.query(TripleQuery(scope=SCOPE, limit=0)))
    assert on_disk == ["X", "Y", "Z"]
    # The FIRST write of Y won (store-level id idempotency, OR IGNORE).
    [y] = reader.query(TripleQuery(assertion_ids=("Y",)))
    assert y.object == "o"

    store.add([_assertion("W", "w", "p", "o", 5)])  # unrelated later add
    reader2 = SQLiteTripleStore(dbpath)
    after = sorted(a.assertion_id for a in reader2.query(TripleQuery(scope=SCOPE, limit=0)))
    assert after == ["W", "X", "Y", "Z"]  # exactly one new row — no resurrections
    for s in (store, reader, reader2):
        s.close()


# ---------------------------------------------------------------------------
# Fix 2 — id-namespace boundary (audit repro2) + close_record (repro5)
# ---------------------------------------------------------------------------


def test_id_matrix_every_entry_point_accepts_both_namespaces(system, stack) -> None:
    _, journal = stack
    [gid] = system.remember_many([_record(digest="tokamak plasma containment")],
                                 scope=SCOPE, owner_id=OWNER, idempotency_key="t1")
    r = system.reconstruct(Stimulus(cue_text="tokamak plasma"), scopes=SCOPES, journal=False)
    aid = r.handles[0].record_id
    assert aid != gid  # the two namespaces really are distinct

    # reinforce(graph id) must boost the handle the ranking actually reads.
    system.reinforce(gid, reason="pin by graph id", weight=25, scope=SCOPE, owner_id=OWNER)
    act = system.activation([aid, gid], scope=SCOPE, owner_id=OWNER)
    assert act[aid]["base_level"] == 25.0   # landed on the digest assertion id
    assert act[gid]["base_level"] == 25.0   # graph key resolves to the same score

    # attenuate(graph id) journals under the same resolved id.
    system.attenuate(gid, reason="mute", scope=SCOPE, owner_id=OWNER)
    assert journal.events(scope=SCOPE, owner_id=OWNER, kinds=["silenced"], limit=0)[0].record_id == aid

    # commit_selection(graph id): the trail lands on the retrieval key.
    snap = system.commit_selection("t-commit", [gid])
    assert snap.used_record_ids == (aid,)
    assert journal.selected_count(aid) == 1

    # Unknown ids are LOUD everywhere (never a silent zero / no-op).
    for call in (
        lambda: system.activation(["ghost"], scope=SCOPE, owner_id=OWNER),
        lambda: system.reinforce("ghost", reason="x", scope=SCOPE, owner_id=OWNER),
        lambda: system.commit_selection("t-x", ["ghost"]),
        lambda: system.close_assertions(["ghost"], kind="retract", reason="x"),
    ):
        with pytest.raises(ValueError, match="ghost"):
            call()

    # close_assertions(graph id) resolves and actually removes from recall.
    system.close_assertions([gid], kind="retract", reason="done with it")
    after = system.reconstruct(Stimulus(cue_text="tokamak plasma"), scopes=SCOPES, journal=False)
    assert aid not in _ids(after)


def test_close_record_closes_digest_and_edges_as_one_act(system) -> None:
    """Audit repro5: retracting only the digest left tombstone EDGES routing
    spread through the dead record (and C stayed reachable through B)."""
    [gid_a] = system.remember_many([_record(title="A", digest="zeta protocol handshake details")],
                                   scope=SCOPE, owner_id=OWNER, idempotency_key="t1")
    [gid_b] = system.remember_many(
        [_record(title="B", digest="unrelated middle fact", edges=(("supports", gid_a),))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="t2")
    [gid_c] = system.remember_many(
        [_record(title="C", digest="distant conclusion text", edges=(("refines", gid_b),))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="t3")

    def run():
        return system.reconstruct(Stimulus(cue_text="zeta protocol handshake"), scopes=SCOPES,
                                  budget=RecallBudget(max_hops=3), view="working_set", journal=False)

    # Sanity: the chain conducts before closure — A is cued; C receives spread.
    # (Edges point B->A and C->B; spreading is undirected over shared terms.)
    before = {h.title: h for h in run().handles}
    assert before["C"].activation["spread"] > 0

    closure_ids = system.close_record(gid_b, reason="B was wrong")
    assert len(closure_ids) == 2  # digest + its one edge assertion, one act

    after = run()
    titles = [h.title for h in after.handles]
    assert "B" not in titles
    # B's edge no longer conducts: C is unreachable from the A cue.
    c_handle = next((h for h in after.handles if h.title == "C"), None)
    assert c_handle is None or c_handle.activation["spread"] == 0.0
    # Replaying close_record is a journal no-op (deterministic closure ids).
    assert system.close_record(gid_b, reason="B was wrong") == closure_ids


# ---------------------------------------------------------------------------
# Fix 3 — binding fold: record-level enforcement + per-pair scoping
# ---------------------------------------------------------------------------


def test_hidden_binding_on_graph_id_finally_enforces(system) -> None:
    """Audit repro1: bind(graph_id, hidden) was accepted and silently ignored."""
    [gid] = system.remember_many([_record(digest="tokamak plasma containment")],
                                 scope=SCOPE, owner_id=OWNER, idempotency_key="t1")
    r = system.reconstruct(Stimulus(cue_text="tokamak plasma"), scopes=SCOPES, journal=False)
    assert r.handles

    system.bind(gid, scope=SCOPE, owner_id=OWNER, search_state="hidden", reason="quarantine")
    hidden = system.reconstruct(Stimulus(cue_text="tokamak plasma"), scopes=SCOPES, journal=False)
    assert hidden.handles == ()  # digest AND edge assertions leave retrieval

    system.bind(gid, scope=SCOPE, owner_id=OWNER, search_state="indexed", prompt_state="active",
                reason="restored")
    restored = system.reconstruct(Stimulus(cue_text="tokamak plasma"), scopes=SCOPES, journal=False)
    # The graph-level binding surfaces on the digest handle (subject-first).
    assert restored.handles[0].binding == "indexed+active"


def test_hidden_in_one_pair_never_vetoes_another_pair(system) -> None:
    """Audit repro4 exact scenario: hidden in (private, alice) must not block
    the record's home pair (team, bob) in a ladder search."""
    system.add([TripleAssertion(subject="shared doc", predicate="covers", object="quarterly metrics",
                                scope="team", owner_id="bob", observed_at=_ts(1), assertion_id="doc-1")])
    system.bind("doc-1", scope="team", owner_id="bob", search_state="indexed", reason="home binding")
    system.bind("doc-1", scope="private", owner_id="alice", search_state="hidden",
                reason="alice hides in her view")

    ladder = [("private", "alice"), ("team", "bob")]
    r = system.reconstruct(Stimulus(cue_text="quarterly metrics"), scopes=ladder, journal=False)
    assert "doc-1" in _ids(r)  # the home pair still serves it

    # And hiding it in its OWN pair removes it, ladder or not.
    system.bind("doc-1", scope="team", owner_id="bob", search_state="hidden", reason="team hides")
    r2 = system.reconstruct(Stimulus(cue_text="quarterly metrics"), scopes=ladder, journal=False)
    assert "doc-1" not in _ids(r2)


# ---------------------------------------------------------------------------
# Fix 5 — edge-based Hebbian trails (audit repro9)
# ---------------------------------------------------------------------------


def test_trails_form_and_feed_spreading_for_formed_records(system, stack) -> None:
    _, journal = stack
    [gid_a] = system.remember_many([_record(title="A", digest="tokamak plasma containment")],
                                   scope=SCOPE, owner_id=OWNER, idempotency_key="t1")
    [gid_b] = system.remember_many(
        [_record(title="B", digest="magnet coil design", edges=(("supports", gid_a),))],
        scope=SCOPE, owner_id=OWNER, idempotency_key="t2")

    r = system.reconstruct(Stimulus(cue_text="tokamak magnet"), scopes=SCOPES)
    digest_ids = [h.record_id for h in r.handles]
    assert len(digest_ids) == 2  # both digests matched; edge is not a member
    system.commit_selection(r.trace_id, digest_ids)

    # The commit deposited hop-keyed co_selected trails over the recorded
    # edge PLUS the direct co-use pair (maintainer-initiated 2026-07-07:
    # all depositing-slice pairs wire; the hop pairs stay for spreading).
    pairs = [e.pair_ids for e in journal.events(scope=SCOPE, owner_id=OWNER,
                                                kinds=["co_selected"], limit=0)]
    assert len(pairs) == 3  # (digest_src, edge) + (edge, digest_dst) + (digest, digest)

    # End-to-end (the audit's bar): the NEXT reconstruction's spreading walks
    # those exact hops with trail_activation > 0.
    r2 = system.reconstruct(Stimulus(cue_text="tokamak magnet"), scopes=SCOPES,
                            view="working_set", journal=False)
    walked = [e for e in r2.edges if e["trail_activation"] > 0]
    assert walked, f"no trail-strengthened hop in {r2.edges}"


# ---------------------------------------------------------------------------
# Fix 6 — exclusion-aware gathering (audit f2)
# ---------------------------------------------------------------------------


def test_closed_rows_no_longer_starve_the_recents_window(system) -> None:
    system.add([_assertion(f"ok-{i}", "alice", "did", f"database thing{i}", i, literal=True)
                for i in range(1, 6)])
    system.add([_assertion(f"x-{i:03d}", "noise", "said", f"junk {i}", 100 + i, literal=True)
                for i in range(64)])
    system.close_assertions([f"x-{i:03d}" for i in range(64)], kind="retract", reason="noise purge")

    r = system.reconstruct(Stimulus(cue_text="alice database"), scopes=SCOPES,
                           budget=RecallBudget(max_candidates=64), journal=False)
    assert sorted(_ids(r)) == [f"ok-{i}" for i in range(1, 6)]  # all 5 eligible found
    assert r.stop_reason == "enough"


def test_spreading_reaches_through_newer_closed_neighbors(system) -> None:
    """Audit f2 part 2: 13 newer closed rows sharing the hub term used to
    burn the whole fan-out window and block the eligible older target."""
    system.add([_assertion("s-1", "alice", "knows", "acme", 50)])
    system.add([_assertion("ok-1", "acme", "located_in", "paris", 1)])  # eligible, OLDEST
    system.add([_assertion(f"x-{i:02d}", "acme", "noted", f"junk{i}", 100 + i, literal=True)
                for i in range(13)])
    system.close_assertions([f"x-{i:02d}" for i in range(13)], kind="retract", reason="junk")

    r = system.reconstruct(Stimulus(cue_text="alice"), scopes=SCOPES, view="working_set", journal=False)
    by_id = {h.record_id: h for h in r.handles}
    assert "ok-1" in by_id and by_id["ok-1"].activation["spread"] > 0


# ---------------------------------------------------------------------------
# Fix 7 — budget-authoritative spreading (a2a 008)
# ---------------------------------------------------------------------------


def test_budget_hops_override_spread_params_default(system) -> None:
    system.add([
        _assertion("h-1", "alice", "knows", "bob", 1),
        _assertion("h-2", "bob", "knows", "carol", 2),
        _assertion("h-3", "carol", "knows", "dave", 3),
        _assertion("h-4", "dave", "located_in", "paris", 4),  # 3 hops from h-1
    ])
    # Default SpreadParams.max_hops=2 used to silently clamp min(2, 5)=2.
    r = system.reconstruct(Stimulus(cue_text="alice"), scopes=SCOPES,
                           budget=RecallBudget(max_hops=5), view="working_set", journal=False)
    by_id = {h.record_id: h for h in r.handles}
    assert "h-4" in by_id and by_id["h-4"].activation["spread"] > 0  # hop 3 reached


# ---------------------------------------------------------------------------
# Fix 8 — edge assertions conduct, never member
# ---------------------------------------------------------------------------


def test_edge_assertions_walkable_but_never_handles(system, stack) -> None:
    _, journal = stack
    [gid_a] = system.remember_many([_record(title="A", digest="tokamak plasma containment")],
                                   scope=SCOPE, owner_id=OWNER, idempotency_key="t1")
    system.remember_many([_record(title="B", digest="magnet coil design",
                                  edges=(("supports", gid_a),))],
                         scope=SCOPE, owner_id=OWNER, idempotency_key="t2")

    r = system.reconstruct(Stimulus(cue_text="tokamak magnet"), scopes=SCOPES, view="working_set")
    assert {h.title for h in r.handles} == {"A", "B"}   # no tombstone-edge handles
    assert any(e["predicate"] == "supports" for e in r.edges)  # still conducts
    # 'listed' audits mirror handles only — never edge assertion ids.
    listed = {e.record_id for e in journal.events(scope=SCOPE, owner_id=OWNER,
                                                  kinds=["listed"], limit=0)}
    assert listed == set(_ids(r))


# ---------------------------------------------------------------------------
# Fix 9 — vector floor (audit f3 banana case)
# ---------------------------------------------------------------------------


class _BananaEmbedder:
    def embed_texts(self, texts):
        out = []
        for t in texts:
            low = str(t).lower()
            if "banana" in low:
                out.append([0.02, 1.0, 0.0])   # cosine ~0.02 vs the cue
            elif "finance" in low or "quarterly" in low:
                out.append([0.0, 0.0, 1.0] if "filed" in low else [1.0, 0.0, 0.0])
            else:
                out.append([0.0, 1.0, 0.0])
        return out


def test_vector_floor_stops_weak_cosine_from_crowning_1_0() -> None:
    store = InMemoryTripleStore(embedder=_BananaEmbedder())
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore", RuntimeWarning)
        system = MemorySystem(store=store, journal=InMemoryJournal())
    system.add([
        _assertion("a-banana", "carol", "ate", "banana split", 1, literal=True),
        _assertion("b-finance", "bob", "filed", "finance report", 2, literal=True),
    ])
    r = system.reconstruct(Stimulus(cue_text="quarterly finance report"), scopes=SCOPES, journal=False)
    by_id = {h.record_id: h for h in r.handles}
    assert "vector" not in by_id["a-banana"].relevance      # 0.02 clipped by the floor
    assert by_id["b-finance"].relevance["keyword"] > 0.6    # the genuine match
    assert _ids(r)[0] == "b-finance"
    # All cosines below the floor is labeled loudly and distinctly.
    assert any("below floor 0.05" in w and "no semantic signal" in w for w in r.warnings)


# ---------------------------------------------------------------------------
# Fix 10 — strict-JSON boundary (audit a5/s5)
# ---------------------------------------------------------------------------


@pytest.fixture(params=["memory", "sqlite"])
def journal(request: pytest.FixtureRequest, tmp_path):
    if request.param == "memory":
        with warnings_module.catch_warnings():
            warnings_module.simplefilter("ignore", RuntimeWarning)
            j = InMemoryJournal()
    else:
        j = SQLiteJournal(tmp_path / "journal.sqlite3")
    yield j
    j.close()


def test_nan_weight_rejected_at_construction() -> None:
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite"):
            MemoryEvent(kind="listed", scope=SCOPE, owner_id=OWNER, record_id="r", weight=bad)


def test_nonfinite_provenance_normalizes_with_one_warning(journal) -> None:
    ev = MemoryEvent(kind="listed", scope=SCOPE, owner_id=OWNER, record_id="r",
                     provenance={"score": float("nan"), "ratio": float("inf"), "ok": 1.5})
    with pytest.warns(RuntimeWarning, match="non-finite"):
        stored = journal.append_events([ev])[0]
    assert stored.provenance == {"score": None, "ratio": None, "ok": 1.5}
    back = journal.events(scope=SCOPE, owner_id=OWNER, limit=1)[0]
    assert back.provenance == {"score": None, "ratio": None, "ok": 1.5}
    # Strict JSON survives the whole path.
    json.dumps(back.to_dict(), allow_nan=False)


def test_datetime_provenance_survives_identically_on_both_backends(journal) -> None:
    ev = MemoryEvent(kind="listed", scope=SCOPE, owner_id=OWNER, record_id="r",
                     provenance={"when": datetime(2026, 1, 1, 12, 30)})
    journal.append_events([ev])
    back = journal.events(scope=SCOPE, owner_id=OWNER, limit=1)[0]
    assert back.provenance == {"when": "2026-01-01 12:30:00"}  # seam _jsonify stringification


def test_sqlite_ledger_cells_are_strict_json(tmp_path) -> None:
    j = SQLiteJournal(tmp_path / "j.sqlite3")
    with pytest.warns(RuntimeWarning, match="non-finite"):
        j.append_events([MemoryEvent(kind="listed", scope=SCOPE, owner_id=OWNER, record_id="r",
                                     provenance={"score": float("nan")})])
    [cell] = j._conn.execute("SELECT provenance_json FROM memj_events").fetchone()
    parsed = json.loads(cell)
    assert parsed == {"score": None}
    json.dumps(parsed, allow_nan=False)  # no bare NaN token on disk
    j.close()


# ---------------------------------------------------------------------------
# Fixes 11 + 12 — sharp edges
# ---------------------------------------------------------------------------


def test_ttl_zero_or_negative_rejected() -> None:
    """Audit f8: ttl<=0 silently inverted "expire asap" into "permanent"."""
    for bad in (0, -5):
        with pytest.raises(ValueError, match="ttl_activity"):
            MemoryEvent(kind="pinned", scope=SCOPE, owner_id=OWNER, record_id="r",
                        reason="keep", ttl_activity=bad)
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore", RuntimeWarning)
        j = InMemoryJournal()
    with pytest.raises(ValueError, match="ttl_activity"):
        reinforce_writer(j, "r", reason="x", ttl_activity=0, scope=SCOPE, owner_id=OWNER)


def test_unparseable_observed_at_rejected_at_append(journal) -> None:
    """Audit s2: garbage timestamps used to be stored verbatim, silently
    corrupting the lexicographic seq_at() axis forever."""
    with pytest.raises(ValueError, match="ISO-8601"):
        journal.append_events([MemoryEvent(kind="listed", scope=SCOPE, owner_id=OWNER,
                                           record_id="r", observed_at="not-a-timestamp")])
    # Empty still means "now" (unchanged convention).
    stored = journal.append_events([MemoryEvent(kind="listed", scope=SCOPE, owner_id=OWNER,
                                                record_id="r", observed_at="")])[0]
    assert stored.observed_at


def test_tokenizer_accent_folds_and_labels_non_latin_cues() -> None:
    """Audit f6: 'café' and 'cafe' never matched; CJK cues died silently."""
    assert tokenize("café über élan") == tokenize("cafe uber elan") == ["cafe", "uber", "elan"]
    fr = _assertion("fr-1", "ex:m", "dcterms:abstract", "le café préféré du député", 1, literal=True)
    hits, _found, _ = run_keyword_channel("cafe prefere", {"fr-1": fr}, [])
    assert hits and hits[0].score == 1.0  # unaccented cue matches accented text

    warnings_list: List[str] = []
    results, _found, ran = run_keyword_channel("数据库连接池决定", {"fr-1": fr}, warnings_list)
    assert results == [] and ran is False
    assert any("no indexable tokens" in w and "FTS5" in w for w in warnings_list)


def test_compute_activation_rejects_unassigned_seq() -> None:
    """Audit f12: seq=-1 events made scores depend on caller list ORDER."""
    unenriched = MemoryEvent(kind="selected", scope=SCOPE, owner_id=OWNER, record_id="r")
    with pytest.raises(ValueError, match="seq"):
        compute_activation([unenriched])


def test_trace_id_indexes_exist(tmp_path) -> None:
    j = SQLiteJournal(tmp_path / "j.sqlite3")
    names = {r[0] for r in j._conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
    assert {"idx_memj_snapshots_trace", "idx_memj_events_trace"} <= names
    j.close()
