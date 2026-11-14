# Planned: the replay diary block carries the resolution keys (root backlog 1206)

## Metadata
- Created: 2026-11-11
- Status: Completed (in place; the 0.5.2 tag is cut by the release owner with the other residuals)
- Completed: 2026-11-11 (`b3d90c2`)
- Target: abstractmemory 0.5.2
- Priority: P1 (the Entity app cannot show a question as resolved from the stream)
- Owner: AbstractMemory (`src/abstractmemory/replay.py`, `src/abstractmemory/records.py`)

## ADR status
- Governing ADRs: None (the replay stream v1 rules: display blocks are additive, diary blocks carry act-frame
  keys and never words)
- ADR impact: None

## Context
A question is a diary record with `diary_type="question"`; a later entry resolves it through `attributes.resolves`
(graph id or book `entry_id`), the fold `diary._open_unresolved` and `entity_card` apply. The runtime (`4501552`,
0.19.5) confirms the claim at write time and reports, beside `resolves`, the book's verdict `resolves_status`
(for example `resolved_open_question`), `resolved_record_id` (the question's graph id) and `resolved_title`.
The replay diary block carried `diary_type`, `entry_id`, `graph_id` and the reading's act frame, none of these
keys, so the Entity app could not mark a question resolved from the stream (root backlog 1206, operator
2026-11-11 02:00: the answered question showed no badge).

## Current code reality (2026-11-11, after `b3d90c2`)
- `replay._display_block`: the diary block carries `resolves`, `resolves_status` and `resolved_record_id` when the
  record's attributes hold them (keys, never words, like `entry_id`); `resolved_title` rides only when the record
  is not private (`attributes.private` absent or False, the `diary.diary_summary_refusal` rule). A question entry
  itself carries nothing new.
- `records.MemoryRecordInput`: `resolves_status`, `resolved_record_id`, `resolved_title` are optional strings,
  non-empty when present, refused otherwise (the `resolves` validation style).
- Seam, the runtime's half: its projection (`integrations/abstractmemory/identity_support.py`) writes only
  `resolves` onto the record; the verdict keys live in its DIARY_WRITE result and the election meta. The stream
  carries them once the runtime writes them onto the resolving record's attributes, omitting a key it has no value
  for (a private target's `resolved_title` is `""` in its result: omit it, memory refuses an empty string).

## Validation
- `tests/test_replay.py`: a resolving entry exports the four keys; a private resolving entry exports the three
  keys and no title; a question entry exports none of them. `tests/test_records.py`: the three attributes are
  validated (empty, blank, non-string refused). Mutants run 2026-11-11: dropping the key loop (4 red), dropping
  the private rule (2 red), dropping the validation (1 red).
- Docs: `docs/api.md` (replay block field list, diary formation rules), `llms-full.txt` mirror, `CHANGELOG.md`
  `[0.5.2] - Unreleased`.

## Non-goals
Re-deriving a resolution in the stream from the `resolves` fold (the block carries what the record holds);
carrying `resolved_visibility`; changing the entity card or the open-question folds.
