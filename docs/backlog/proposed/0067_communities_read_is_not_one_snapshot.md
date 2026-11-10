# Proposed: `communities()` reads heads, closures and rows in three statements (one read can serve an empty version)

## Metadata
- Created: 2026-11-10 (Fable pre-tag review of 0.5.0, should-fix 2)
- Status: Proposed
- Completed: N/A
- Target: abstractmemory 0.5.1
- Priority: P2 (no data loss; one wrong read, self-heals at the next read)

## ADR status
- Governing ADRs: None (communities are a slice of planned
  [0053](../planned/knowledge_graph_convergence/0053_self_organisation_communities_consolidation_reflection.md))
- ADR impact: None

## Context
`community_index.communities()` is the payload the gateway serves (version 2) and the entity's topics tool reads.
Fable's review of 0.5.0 (framework root `untracked/finish-plan-2026-11-09/graph-topics/REVIEW-memory-0.5.0.md`,
should-fix 2; probe p3 under `abstractmemory/untracked/review-050/`) found a torn read.

## Current code reality (2026-11-10, `5c6136b`)
- `community_index.py:806-807` and `253-281`: the heads, the closures and the rows are read in three statements with
  no shared snapshot.
- A version committed between them (p3, both substrates) serves `version_seq` v1 with `communities: []` and
  `first_sleep_pending: false` for one read; the entity's topics tool then says "no topics".
- The next read is correct.

## Problem or opportunity
A reader can be told the home has no topics during the seconds a sleep commits its new version.

## Proposed direction
Either (a) when every head of the newest version is closed, re-read the heads once; or (b) wrap the fold in one
deferred read transaction on the shared SQLite file (`BEGIN` ... `COMMIT`, a snapshot under WAL) and hold
`store._lock` on the in-memory pair. (b) is the general fix; (a) is the minimal one.

## Why it might matter
The served payload must never contradict itself (a version with no communities and no first-sleep flag).

## Promotion criteria
The 0.5.1 memory patch.

## Validation ideas
Red test from p3 on both substrates: commit a version between the heads read and the rows read (a hook or a paused
writer) and assert the payload is either the old version whole or the new one whole. Mutant: drop the snapshot / the
re-read -> red.

## Non-goals
Changing the payload shape.

## Guidance for future agents
A read transaction must not take the write lock (no `BEGIN IMMEDIATE`): opening a home whose tables exist is a read.
