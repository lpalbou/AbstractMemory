# Proposed: close the write barrier's three residual windows (`_write_pin`, `mark_journal_applied`, LanceDB)

## Metadata
- Created: 2026-11-10 (residual of the 0.5.0 Stop fence hooks)
- Status: Proposed
- Completed: N/A
- Target: the next abstractmemory patch (the two SQLite points; 0.5.1 shipped without them); the LanceDB window
  needs a decision first
- Priority: P2

## ADR status
- Governing ADRs: [ADR 0003](../../adr/0003-one-graph-ledger-provenance-and-revisions.md) (the SQLite home is the
  one home store; LanceDB a connector)
- ADR impact: None expected for the SQLite half; refusing or accepting the LanceDB window may deserve an ADR 0003
  note

## Context
0.5.0 ships the memory half of the host's Stop fence: `MemorySystem(commit_guard=)` calls the host's guard inside
every write transaction immediately before its COMMIT (`4074406`, `3a5810c`), and `write_barrier()` lets the host
bump what the guard compares while every in-flight COMMIT finishes and every new one waits (`85ecf75`; Codex review 4
finding 2, framework root `untracked/entity-phases-2026-11-08/review/CODEX-REVIEW-4-fence.md`). The CHANGELOG's
Upgrading section and the `write_barrier.py` docstring name three windows the barrier does not cover.

## Current code reality (2026-11-10, `5c6136b`)
- `SQLiteTripleStore._write_pin(pin, cursor=None)` (`sqlite_store.py:463`): without a cursor it is an AUTOCOMMIT
  write; it calls `guard_commit(self, "store.write_pin")` under the store's in-process lock, then executes one
  `INSERT OR REPLACE` that takes the file's write lock only when it runs. Reached by a pinless store's first embedded
  write (for example `communities.embed_missing`, `communities.py:1734`).
- `MemoryGraph`'s SQLite backend `mark_journal_applied` (`graph/graph.py:548`): the same shape, one autocommit
  `UPDATE ... SET journal_applied = 1` after the guard; reached on the off-file graph (graph tables not in the
  journal's file).
- Both are covered by a barrier on the SAME handle (it holds the store's lock across guard and statement), not by a
  barrier taken through another connection or process: there, one write whose guard passed may land after the bump.
- LanceDB: `LanceDBTripleStore.add` and the LanceDB graph backend take no write lock (LanceDB has no transaction and
  no file lock), so nothing can make their write wait; `BarrierHold.uncovered` names the store and a `#FALLBACK`
  RuntimeWarning is emitted. At most one write per concurrent writer lands after the bump; its next write is refused.
- Production exposure today is low: the runtime opens one SQLite file per home (`abstractruntime/identity/chat.py`),
  live homes are pinned, and the entity homes are SQLite (ADR 0003 decision 3).
- Refresh (2026-11-10, `f5fdee0`, after 0.5.1): unchanged; 0.5.1 touched none of `write_barrier.py`,
  `sqlite_store.py` or `graph/` (its source changes are `communities.py`, `community_index.py`, `memory_tasks.py`,
  `understanding.py`).

## Problem or opportunity
A Stop that must mean "nothing after this lands" has three documented exceptions. Each is at most one write per
concurrent writer, but each is a hole the fence's tests have to describe rather than refuse.

## Proposed direction
1. SQLite points: run each as `BEGIN IMMEDIATE` -> guard -> statement -> `COMMIT` on the store's connection, so the
   guard runs after the file's write lock is held (exactly like every other write transaction). A barrier on another
   connection then makes the write wait, and its guard sees the bump.
2. LanceDB: decide between (a) refusing `commit_guard=` on a LanceDB store or graph (`TypeError`, like an unguarded
   store type), (b) a process-shared lock file beside the LanceDB directory taken by every LanceDB write and by the
   barrier, or (c) keeping the documented window. Record the decision.
3. Remove the corresponding sentences from the CHANGELOG Upgrading section, `write_barrier.py` and `docs/api.md` once
   a window is closed.

## Why it might matter
The runtime fence's guarantee ("after Stop, no memory write lands") becomes unconditional for the SQLite home; the
LanceDB case stops being a silent-but-warned exception.

## Promotion criteria
Promote with the next memory patch (0.5.1 shipped without it) for the SQLite half; the LanceDB half when a host fences a LanceDB home.

## Validation ideas
- In `tests/test_write_barrier.py`: a pinless store's first embedded write and an off-file `mark_journal_applied`,
  paused after the guard in another process; a barrier from a third connection waits, bumps, and the paused write is
  refused (red today, green after).
- A mutant that drops the `BEGIN IMMEDIATE` turns both red.
- LanceDB: whichever option is chosen gets its own red test (refusal raised, or the lock file waited on).

## Non-goals
Changing the hot path of ordinary transactions; any runtime-side fence change.

## Guidance for future agents
Read `write_barrier.py`'s module docstring and `commit_guard.py` first; keep the barrier writing nothing and the
fixed lock order (store lock, queue lock, graph tables lock, journal lock, then the files).
