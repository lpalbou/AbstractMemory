# Proposed: `docs/api.md` omits `communities_pass` and `embed_missing` from the passes that refuse a queue-less home

## Metadata
- Created: 2026-11-10 (Fable pre-tag review of 0.5.0, nit)
- Status: Proposed
- Completed: N/A
- Target: abstractmemory 0.5.1 docs pass
- Priority: P3 (docs)

## ADR status
- Governing ADRs: None
- ADR impact: None

## Context
abstractmemory 0.5.0 makes every pass that can form a record with a pending title or summary refuse a home opened
without `task_queue=True`, before writing anything. The CHANGELOG `[0.5.0]` Upgrading section lists them, including
`communities_pass` and `embed_missing` (both call `require_task_queue`, `communities.py`). Fable's review (framework
root `untracked/finish-plan-2026-11-09/graph-topics/REVIEW-memory-0.5.0.md`, nits) found the api page's list short.

## Current code reality (2026-11-10, `5c6136b`)
`docs/api.md` line 226 (the `task_queue=True` bullet under the `MemorySystem` constructor) lists `world_model_pass`,
`dream_pass`, `mine_candidates_pass`, `consolidation_pass`, `wake_cue_dedup_pass`, `sleep_pass`, `declare_pending` /
`rearm_pending`, the ripple verbs and `engram`; `communities_pass` and `embed_missing` are missing.

## Proposed direction
Add both to that bullet, then regenerate `llms-full.txt` (coredoc pass) so the mirror matches.

## Why it might matter
The api page is the reference a host reads before opening a home.

## Promotion criteria
The next memory docs pass (0.5.1).

## Validation ideas
`grep -n "communities_pass" docs/api.md` finds the bullet; `llms-full.txt` regenerated identically on a rerun.

## Non-goals
Rewording the rest of the page.

## Guidance for future agents
Apply the coredoc skill; claims checked against `require_task_queue` call sites in `src/`.
