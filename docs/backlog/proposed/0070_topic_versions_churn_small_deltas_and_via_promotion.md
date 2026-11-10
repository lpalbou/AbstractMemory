# Proposed: a topic is "changed" by a `via` promotion or a one-record delta, so every short rest rewrites it

## Metadata
- Created: 2026-11-10 (memory half of framework root backlog 1201; counts from the Entity seat's Q3 report,
  framework root `untracked/finish-plan-2026-11-09/round3/Q3-aletheia-counts.md`, counts only)
- Status: Proposed
- Completed: N/A
- Target: the next abstractmemory minor, with the runtime's threshold (root 1201 scope 1); not this wave
- Priority: P2 (memory growth and graph noise on a busy entity; no data loss, no wrong placement)

## ADR status
- Governing ADRs: None (communities are a slice of planned
  [0053](../planned/knowledge_graph_convergence/0053_self_organisation_communities_consolidation_reflection.md))
- ADR impact: None (a version row still advances; records stay immutable; `refines` chains stay)

## Context
A one-day-old live home (a private entity, counted read-only, no content read) holds 1,179 records: 681 open
memories, 229 closed memories, 1 engine record and **268 topic records (7 current, 261 closed)** plus **247 closed
`refines` link rows** between topic versions: **64 topic versions in 8 h 43 min** (castor, same day: 4 versions,
17 link rows). Each version closed ~4 of the 7 topics and wrote 4 new records and ~4 link rows. The Entity app had to
learn to hide those rows (abstractentity backlog 0021). Root 1201 records the runtime half: the full night (topics
stage) runs at every self-elected rest, 156 sleeps in that day.

## Current code reality (2026-11-10, `20c3086`, published 0.5.1)
- `communities.py:1562-1660`: versions are ALREADY incremental — only a `changed` community gets a new record (the
  previous closed `supersede`, one `refines` edge); the unchanged ones keep their record, layout and title
  (`if not c["changed"]: continue`). Root 1201's "every topic record re-created" is not what the code does; the 261
  closed topic records are 64 versions × ~4 changed topics.
- `communities.py:1508-1513`: a community is `changed` when its set of `(id, via)` pairs differs from the previous
  version's, or `_needs_reform`, or `_links_gone`. Two consequences:
  1. a **`via` promotion** alone (a record placed `provisional` by `place_record` during the day, then found by the
     night's detection in the SAME community, `via` → `detected`) flips the community: same members, new record,
     closed previous, new link row;
  2. **one new record** (an episode formed since the last version, detected into its provisional community) flips
     the community the same way.
- `communities_pass` writes nothing only when no community is `changed` and no pending title waits
  (`_unchanged_skip`, `:1350`). A rest that follows 8–12 new memories therefore writes a version with ~4 rewritten
  topics (the Q3 home: ~4.1 per version).

## Problem or opportunity
A topic record is rewritten (new record + closure + link row, new `membership_hash`, carried or re-authored title)
for membership deltas that do not change what the topic IS. On a busy entity that is ~4 rewrites per rest, ~250
closed topic records and ~250 link rows a day, growing `community_keys_of`'s index reload, the replay, and the
graph's hidden set, and (root 1198 #2) re-authoring wording that had nothing new to say.

## Proposed direction
1. **`via` promotion is not a change.** Compare the membership by ids only (`{m["id"]}`), and record the promotion in
   place on the standing record's `members[].via` through the placement index (the record's content is otherwise
   untouched; `since_seq` stays). A community whose ids are identical keeps its record.
2. **Small deltas stand as provisional.** A community whose delta since its record is below a floor (e.g. fewer than
   `COMMUNITY_REWRITE_MIN` = 3 new ids AND no id moved out AND the `matched_jaccard` ≥ 0.9) keeps its record; the new
   ids stay `provisional` in the placement index (as they are during the day) and are counted in the receipt
   (`deferred_members`). A delta at or above the floor, any move-out, a split/merge, `_needs_reform` or `_links_gone`
   rewrites as today. The version row still advances with the pass receipt (so `version_seq` / `communities_changed`
   stay truthful), and `communities()` serves the standing records with their provisional members.
3. Receipt and night line: `rewritten`, `deferred_members`, `promoted` counts, so the runtime's own-time line can say
   "topics: 7 stand, 9 memories placed, 0 rewritten".
4. Measured on the Q3 home's copy (counts only) and on castor's: versions, topic records and link rows per day
   before/after, with the runtime's threshold (root 1201 scope 1) on and off.

## Validation
- A night that only promotes provisional members: no topic record written, no closure, no link row; `communities()`
  shows the members as `detected`.
- A night with 2 new records in one topic and nothing moved: the topic stands, the receipt says `deferred_members: 2`;
  a night with 3 new records or one move-out rewrites it.
- `tests/test_communities.py` mutants: a version that drops the floor (rewrites every changed topic) turns the
  deferred test red; a version that never rewrites turns the move-out test red.
- The Entity app's "closed memories" toggle count stops growing with short rests (abstractentity 0021).

## Non-goals
The runtime's trigger threshold (root 1201 scope 1, AbstractRuntime `identity/topics.py`); the app's hiding of link
rows (abstractentity 0021, done this wave); any change to the detection algorithm or the authored titles' rules.
