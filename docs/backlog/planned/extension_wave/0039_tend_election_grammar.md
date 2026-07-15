# Planned: the ```tend election grammar (attention + repair agency)

## Metadata
- Created: 2026-07-13
- Status: Planned (implementation in flight, maintainer-accepted)
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None (identity-scope question escalated to the maintainer
  as ruling Q2 — recorded in 0036)

## Context
The engine has deliberate verbs for attention (reinforce/attenuate/
refocus — attention.py events pinned/silenced/refocus), emotional repair
(heal_scar/break_bond — system_valence.py), re-entry (payload/deliberate
reach) and dream disposal (disposal.py) — and NO entity can call any of
them. Castor noticed nine of his thirty shelf seats were one story retold
and could only complain (the bridge attractor); with the mechanical
origin-penalty forbidden by ruling ("don't"), entity-elected tending is
the only compliant counter. Maintainer acceptance (2026-07-13): "sort of a
more controlled way for the entity to manage its emotions, attention and
focus. I agree in principle, it depends on the implementation… I suggest
an ITERATIVE process here, because ideas can lead to others: selecting
first the closest nodes to our need, then letting it spread a bit, trying
to find additional paths."

## Current code reality
All target verbs exist and are tested engine-side; the ```diary and
```feel fenced-block precedents are parsed runtime-side (identity/
reflection.py). No tend grammar exists anywhere. Verified 2026-07-13.

## Problem
Agency over one's own attention and repair exists as code surface only;
every scar is permanent and every self-amplifying thread unquietable by
the entity's own act — by accident, not design.

## What we want to do
`src/abstractmemory/tend.py`:
- `parse_tend_block(text)` — one verb per line
  (`verb: <target> — reason: …`): pin / silence / refocus / heal_scar /
  break_bond / revisit / dispose(confirm|reject). Mandatory reason;
  per-block verb cap; refusals returned as data (shown verbatim to the
  entity), never exceptions.
- `apply_tend_elections(system, elections, *, scope, owner_id, actor,
  channel, self_pairs=...)` — maps each election to the EXISTING engine
  verb (zero new mutation paths); per-election refusals (wrong channel,
  unknown target, identity-scope pending Q2, missing scar/bond); batch
  never aborts.
- REVISIT is the iterative reach (maintainer input): seed from the named
  record, one bounded spreading step over trail-strengthened edges
  (reusing probe_expand/spreading), return seed + labeled neighbor paths;
  iterate by re-electing on a path node. Journals like probe (a traced
  deliberate read with the election's reason as cue provenance).

## Why
The entity's own counter to the bridge attractor; closes the healing loop
the trauma model requires (healing = entity reflection); one grammar
family instead of three separate election surfaces.

## Requirements
- Engine gains zero new mutation paths (grep-honest).
- Reason mandatory on every line; refusals are data.
- Channel contract visible engine-side (entity-reflection), door-gated
  again at the gateway.
- Identity-scope targets refuse with the pending-Q2 text until ruled.
- Valence never gates; tend never deposits (commit stays the only
  strengthening path; revisit's read follows probe's trace semantics).

## Scope
Engine parser + applier + tests. Driver fence extraction and offering the
block in reflection prompts is runtime's lane (coordinated on the hub).

## Non-goals
- No auto-tending: every act is the entity's explicit election.
- No workplace-channel acceptance.
- No new verbs beyond the seven; no selection-side changes.

## Dependencies and related tasks
0036 (wave ledger; Q2 ruling pending); memory_system_v1 0031-2/-14
(disposal + healing surfaces this grammar unifies); attention.py verbs.

## Expected outcomes
The Castor scenario passes: a shelf dominated by retellings is restored
to diversity by the entity's own silence: elections; a seeded scar with
positive evidence since is healable through the block; revisit surfaces
additional paths iteratively.

## Validation
- `tests/test_tend.py`: flagship Castor-scenario test (domination →
  silence → diversity); full grammar + refusal rails; revisit paths +
  trace semantics + presence≠use; heal/dispose end-to-end; wrong-channel
  refusal. Full suite green.
- Live experiment: a realistic reflection turn where a real model's
  emitted block parses and applies, and the next recall demonstrably
  changes.

## Progress checklist
- [x] Contract (concretizer round, 2026-07-13)
- [x] Implementation (builder agent: `tend.py` — parse_tend_block +
      apply_tend_elections over EXISTING verbs only
      (reinforce/attenuate/refocus/heal_scar/break_bond/revisit/dispose);
      reasons mandatory; revisit = iterative probe_expand reach per the
      maintainer's acceptance note; identity-scope elections refused
      pending ruling — IDENTITY_SCOPE_PENDING_RULING)
- [x] Integration + full suite (exports + changelog; suite 843 green
      2026-07-13; test_tend.py incl. the flagship Castor
      shelf-domination→silence→diversity scenario)
- [x] Live experiment (2026-07-13, LMStudio qwen3-4b: 9/9 trials PASS —
      model-authored ```tend blocks parsed, applied, and the shelf
      diversified; report on commons c1680)
- [ ] Q2 ruling folded when it lands
- [ ] Maintainer validation
- [ ] Driver-lane wiring (runtime): offer the block in reflection —
      flagged to skill c1714 as the teaching trigger when it lands

## Guidance for the implementing agent
Read the ```feel precedent for grammar tolerance; call only existing
public verbs; keep every refusal text exact and tested.
