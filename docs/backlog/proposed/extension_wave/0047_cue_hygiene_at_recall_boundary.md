# Proposed: cue hygiene at the passive-recall boundary

## Metadata
- Created: 2026-07-13
- Status: Proposed
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None

## Context
Cue dilution is a trace-proven lived failure: a long operator message
used as the effective recall cue buried Castor's dream under lexical
mass — he interpreted the dream AS TOLD, never having had the record in
context. Deliberate-reach surfaces (probe, concept anchoring) attack
dilution on the ACTIVE side; passive recall still takes the whole message
as cue.

## Current code reality
`Stimulus.cue_text` is whatever the host passes (the runtime driver
passes the message); `cue_source` provenance exists (steer/diary_re_entry/
revisit); traces record cues verbatim. No dilution measurement exists.

## Problem or opportunity
Specific reaches lose the shelf race to long-message noise, and the trace
does not even show that it happened.

## Proposed direction
Mostly HOST lane: the driver distills a short cue (or passes the message
AND a distilled cue). Engine half (this item): accept the distilled cue
with `cue_source` provenance, and add a DILUTION HONESTY LABEL to traces —
cue token count vs channel saturation (how many candidates each channel
admitted at the cue's breadth) — so a buried reach is VISIBLE in
`recall_history`/`explain_recall` instead of silent.

## Why it might matter
Prevention for the class that cost a live dream; makes 0042's
explanations able to say "the cue was too wide" mechanically.

## Promotion criteria
Runtime seat adopting the distilled-cue driver change (coordinate on the
hub); or a second lived dilution incident.

## Validation ideas
Replay the dream-burial fixture: same records, message-cue vs distilled-
cue; assert the label quantifies the difference and the reach surfaces
under the short cue.

## Non-goals
The engine never distills text itself (no LLM in the engine); no
selection-side special-casing of short cues.

## Guidance for future agents
The label is the engine deliverable; the discipline is the driver's.
