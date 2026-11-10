# Planned: the runtime's recall stamps use `community_keys_of` instead of the full topics read

## Metadata
- Created: 2026-11-10
- Status: Planned
- Completed: N/A
- Target: abstractmemory 0.5.1 (the read: published 2026-11-10, tag `v0.5.1`, `f66ef28`) + the next AbstractRuntime release
  (the switch)
- Priority: P1 (a hidden per-recall cost that grows with the home)
- Owner: AbstractRuntime (`abstractruntime/src/abstractruntime/integrations/abstractmemory/seam_handlers.py`)

## ADR status
- Governing ADRs: None (communities are a slice of planned
  [0053](knowledge_graph_convergence/0053_self_organisation_communities_consolidation_reflection.md))
- ADR impact: None

## Context
AbstractRuntime `1afbf68` stamps every recalled handle of a visit with its topic (`result.handles[i].topic`, the
community key, read by the Entity app's live activity panel, root backlog 1196).
`seam_handlers._stamp_recall_topics` reads memory's whole `communities()` payload once per recall
(`identity.topics.entity_communities`) and looks each handle up by `provenance.record_id`. That payload computes
every topic's `facts`, so the read is linear in the home: 19 ms at 2,000 records and 190 ms at 20,000 on the
runtime's synthetic home (54 topics, 44 handles), on the passive recall of every turn.

## Current code reality (2026-11-10)
- Memory now serves the membership-only read: `community_index.community_keys_of(system, record_ids, *, scopes,
  owner_id) -> {record_id: key | None}` (and `community_memberships_of`, with `provisional`), the same answer as
  `communities()` for those records, from the in-memory community index. Measured for 50 ids, 54 topics, SQLite
  home: 20 µs per call at 2,000 records, 22 µs at 20,000 (`tests/test_community_keys_of.py`, run with `-s`).
- The runtime still calls `entity_communities` in `_stamp_recall_topics`.
- Refresh (2026-11-10, after the 0.5.1 tag): the runtime's committed `HEAD` (`1afbf68`) still calls
  `entity_communities`. The switch is drafted, uncommitted, in the runtime's working tree: `_stamp_recall_topics`
  calls `memory_facade.community_keys_of` once per recall, `memory_facade` maps `community_keys_of` to
  `abstractmemory.community_index`, and `pyproject.toml` raises the floor to `AbstractMemory>=0.5.1` (version
  0.19.2). Committing and releasing it is the runtime's; this item closes when that release is published.

## Problem or opportunity
The stamp costs up to a fifth of a second per recall on a 20k home, for a key a dict lookup can give.

## Proposed direction
In `_stamp_recall_topics`, collect the handles' graph ids (`provenance.record_id`) and call
`community_keys_of(memory_system, ids, scopes=scopes, owner_id=owner_id)` once; `handle["topic"] =
keys.get(graph_id)`. Raise the runtime's `abstractmemory` floor to the release that ships it (0.5.1). Keep the
existing failure path (a read that raises leaves the recall whole, without `topic`, with its `#FALLBACK` line).

## Promotion criteria
abstractmemory 0.5.1 published with `community_keys_of`: MET 2026-11-10 (tag `v0.5.1` on `f5fdee0`, PyPI 16:51 UTC).

## Validation ideas
The runtime's existing stamp tests unchanged in outcome; its synthetic-home measurement repeated (expect the stamp
under 1 ms at 20,000 records); a counter test that the stamp no longer calls `communities()`.

## Non-goals
Changing what `topic` means or the prompt.

## Guidance for future agents
Pass graph ids, not digest assertion ids: the read does no store lookup per id, so an assertion id answers None.
