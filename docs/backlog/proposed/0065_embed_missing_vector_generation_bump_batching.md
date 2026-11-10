# Proposed: batch `embed_missing`'s per-vector `vector_generation` bump (deliberately skipped in 0.5.0)

## Metadata
- Created: 2026-11-10 (Fable review nit, recorded as "not done" in `01ff4e2`)
- Status: Proposed
- Completed: N/A
- Priority: P3 (performance; no correctness gap)

## ADR status
- Governing ADRs: None
- ADR impact: None

## Context
`communities.embed_missing` (`3082695`, abstractmemory 0.5.0) embeds the formed records that have no vector, one
small guarded commit per vector so partial progress stands. The Fable review of memory M1 (framework root
`untracked/finish-plan-2026-11-09/graph-topics/REVIEW-memory-m1.md`, nits) noted: "per-vector `vector_generation`
bump forces one full matrix rebuild after `embed_missing`".

## Why it was skipped (the reason recorded in `01ff4e2`, kept here verbatim in substance)
Each vector is its own guarded commit. A bump deferred to the end of the pass would leave the vectors already
committed invisible to other handles' vector matrices when the night is stopped mid-way (the host's Stop refuses
every later commit, including a final bump). The in-process rebuild count is one either way: the matrix is rebuilt
lazily at the next semantic query, not once per bump.

## Current code reality (2026-11-10, `5c6136b`)
- `communities.py:1736-1745`: on SQLite each vector is `UPDATE ... SET embedding = ? WHERE assertion_id = ? AND
  embedding IS NULL` plus `store._bump_vector_generation(cur)` in one `system.tasks._txn(..., where=
  "communities.embed_missing")`, guarded by the commit guard.
- `vector_generation` is a uuid in `{table}_meta` (`sqlite_store.py:356`); every process compares it before its next
  semantic query and rebuilds its matrix when it moved.
- The cost: every OTHER process that queries during a long `embed_missing` may rebuild its matrix once per observed
  bump instead of once per pass.

## Problem or opportunity
Only worth doing if a measurement shows other processes rebuilding repeatedly during one pass (a large backfill on a
home that other processes query at the same time).

## Proposed direction
If measured worthwhile: bump once per chunk of N vectors committed together (still guarded; a Stop loses at most the
uncommitted chunk, never a committed vector's visibility), or bump in the same transaction as the chunk's last
vector. Never defer the bump past a commit that wrote vectors.

## Why it might matter
Fewer full matrix rebuilds in concurrent readers during a big `embed_missing` backfill.

## Promotion criteria
A measured repeated rebuild in another process during one `embed_missing` pass on a real (copied) home.

## Validation ideas
A test that a Stop mid-pass leaves every committed vector visible to a second handle's vector query (the invariant
that made the batching unsafe); a rebuild counter on a second handle before and after.

## Non-goals
Changing `rewrite_digest`'s bump (one per rewrite, measured cheap, 0059).

## Guidance for future agents
Keep the invariant first: a committed vector is visible to every handle after its commit, Stop or not.
