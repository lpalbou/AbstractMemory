# Proposed: say where a dissolved community went (`merged_into`) in the community facts

## Metadata
- Created: 2026-11-10 (communities follow-up; framework root
  `untracked/release-2026-11-07/ROADMAP-2026-11-10-0900-DRAFT.md` "communities follow-ups ... merged_into")
- Status: Proposed
- Completed: N/A
- Priority: P3

## ADR status
- Governing ADRs: None (communities are a slice of planned
  [0053](../planned/knowledge_graph_convergence/0053_self_organisation_communities_consolidation_reflection.md))
- ADR impact: None

## Context
abstractmemory 0.5.0 forms communities (topics) during sleep (`communities_pass`, `3082695` .. `01ff4e2`) and serves
them through `community_index.communities()` (payload version 2), each with `facts`, including
`changed_since_last_sleep: {added, moved, split_from}`. A split names its origin; a merge does not.

## Current code reality (2026-11-10, `5c6136b`)
- `communities_pass` (`communities.py:1429-1442`) computes `dissolved = [previous versions whose key matched no
  current community]`, retracts each one's record with reason `dissolved` and lists the keys in the receipt's
  `ids.dissolved`; `moved_out` counts their members.
- `community_index._facts` (`community_index.py:727`) builds `changed_since_last_sleep` from each current record's
  `basis` (`moved_in`, `moved_out`, `split_from`). Nothing records which current community absorbed a dissolved
  one's members, and a dissolved key has no served row at all.
- The `grep merged_into` over `src/` and `tests/` returns nothing.

## Problem or opportunity
A reader (the entity's topics tool, AbstractEntity's Topics panel) can say "topic X split from Y" but, when a topic
disappears, cannot say "Y merged into X"; the change reads as a loss.

## Proposed direction
At write time in `communities_pass`, for each dissolved previous version, record on the current community that
received most of its members (ties by key) `basis.merged_from = [old keys]`, and serve it as
`changed_since_last_sleep.merged_from`; optionally a top-level `dissolved: [{key, merged_into}]` in the payload for
the keys that have no row. Payload version stays 2 if the field is additive (readers ignore unknown fields: check
AbstractEntity's `src/communities.ts` before deciding).

## Why it might matter
The topics view tells the story of a mind's reorganisation without the reader recomputing memberships.

## Promotion criteria
A consumer asks for it (AbstractEntity Topics panel or the entity's topics tool).

## Validation ideas
Fixture: two communities whose members join a third after a sleep -> the third's `merged_from` names both, the
payload's dissolved list names the third; a mutant that drops the field turns the test red.

## Non-goals
Changing detection, keys or the Jaccard matching.

## Guidance for future agents
Read COMMUNITIES-DESIGN (framework root `untracked/finish-plan-2026-11-09/graph-topics/COMMUNITIES-DESIGN.md`) §2 on
`basis` and the receipt before adding a field.
