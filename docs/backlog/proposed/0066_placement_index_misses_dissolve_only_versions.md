# Proposed: the placement index misses a dissolve-only community version (formation places into a dead key)

## Metadata
- Created: 2026-11-10 (Fable pre-tag review of 0.5.0, should-fix 1)
- Status: Proposed
- Completed: N/A
- Target: the next abstractmemory patch (0.5.1 shipped without it)
- Priority: P2 (no data loss; self-heals at the next sleep)

## ADR status
- Governing ADRs: None (communities are a slice of planned
  [0053](../planned/knowledge_graph_convergence/0053_self_organisation_communities_consolidation_reflection.md))
- ADR impact: None

## Context
On a `task_queue=True` home, `remember_many` places every record it forms in its provisional community inside the
formation's transaction (`d550551`, `community_index.place_record`). The placement index is reloaded only when its
catch-up mark says a new community version was written. Fable's review of 0.5.0 (framework root
`untracked/finish-plan-2026-11-09/graph-topics/REVIEW-memory-0.5.0.md`, should-fix 1; probe p2 under
`abstractmemory/untracked/review-050/`) found that the mark misses one kind of version.

## Current code reality (2026-11-10, `5c6136b`)
- `community_index.py:436-456`: the catch-up compares the STORE rowid high-water only.
- A version that only dissolves a community writes closures and no new row (`communities.py:1444-1600` with
  `plans=[]`), so the rowid does not move and the index is never reloaded.
- Repro p2 (SQLite and in-memory): formation places a record into the dead key; `communities()` drops it,
  `community_of` answers None, and `records_since_maintenance(...)["fragmented"]["provisional"]` counts it.
- It self-heals: the next `communities_pass` writes a new version (new rows) and the index reloads.
- Refresh (2026-11-10, `f5fdee0`, after 0.5.1): unchanged. `_store_mark` (`community_index.py:416-427`) is still
  the store rowid high-water (SQLite `MAX(rowid)`, in-memory the row count) and `_catch_up_on` (`459-479`) reloads
  only when a community row appeared above the old mark. 0.5.1's membership reads `community_memberships_of` /
  `community_keys_of` (`944-1007`) share this catch-up, so after a dissolve-only version they keep answering the
  dissolved community's key for its former members until the next version (their docstring names this item).

## Problem or opportunity
Between a dissolve-only night and the next one, every record formed is placed into a community that no longer exists.

## Proposed direction
Make the mark a pair: (store rowid high-water, closures high-water: `SELECT MAX(seq) FROM memj_closures` on SQLite,
`len(closures)` on the in-memory journal). One more integer compare on the hot path; reload when either moved. The one catch-up serves placement and the
membership reads, so the fix covers both.

## Why it might matter
Placement at formation is what keeps a lived home's topics current between sleeps.

## Promotion criteria
The next memory patch (0.5.1 shipped without it).

## Validation ideas
Red test from p2 on both substrates: a dissolve-only version, then a formation; assert the record is placed in a live
community (or unplaced), never the dissolved key; and through `community_keys_of`, a dissolved community's former
member answers None. Mutant: compare the rowid only -> red.

## Non-goals
Changing detection or what a dissolve writes.

## Guidance for future agents
Keep the hot path at zero store reads per record (review I6: the journal idempotency lookup is the only read).
