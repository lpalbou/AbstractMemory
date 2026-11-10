# Ripple v1: a disruptive change is reconsidered through connected memories, bounded per window, and consolidated in sleep

Status: Completed (the engine; its consumers deferred, see the report) · Completed: 2026-11-10 · Shipped in:
abstractmemory 0.5.0 (commit `5c6136b`, local `main`; not yet tagged, pushed or published on 2026-11-10) · Original
path: `planned/knowledge_graph_convergence/0061_ripple_v1_over_the_task_queue.md` (a one-line pointer since
2026-11-10; see the overview's planning note) · Item history: written with the code in `09686e0` (2026-11-08),
closed by the backlog commit that created this file.

Created: 2026-11-07 (understanding pass; [ADR 0001](../../../adr/0001-altered-memories-ripple.md)). Track:
`knowledge_graph_convergence` (the first slice of 0054; absorbs part of `proposed/ripple_wave/0001`) · Priority: P2 ·
Type: feature · Status (as planned, 2026-11-08): Planned — engine half implemented on `main` (see Report), awaiting the maintainer's ship
review; detection (the `revise` election) is runtime 0870, the reader runtime 0869.

## Summary
When a memory's meaning changes, memory seeds a ripple. Two triggers: the entity's own `revise` election (passed in
by the runtime), and a rewrite whose reader reports `change: revised | overturned`. From the seed, memory selects the
connected memories by relation and by similarity until the activation floor, and enqueues one `ripple.reconsider`
task for each (0060). The reader returns `unchanged` (settled with no write, recorded) or a new version with cause
`ripple`; a memory whose measured change clears the floor seeds the next hop. At the next nightly sleep, a ripple that
changed two or more memories yields one `ripple.consolidate` task: a first-person "what this changes" record linked
to everything it touched.

## Why
Operator, 2026-11-07, verbatim: "a disruptive fact given in the present should trigger a reaction (surprise?) and
slowly get to actual consistency by rippling through the connected memories until a certain activation threshold
... and this could consolidate also during the sleep/dream phase ... The goal is not to destabilize the entity, but
to give it the opportunity to revisit what it thinks it knows and possibly expand its understanding." ADR 0001 rules
that AbstractMemory owns the ripple end to end. Surprise as a feeling is not decided (operator decision 8): words only.

## Current code reality (audited 2026-11-07, before the change)
- Bounded spreading activation exists (`spreading.py`, `SpreadParams`: max_hops 2, fan_out_cap 12, damping 0.5,
  min_contribution 0.05); a pure read used by recall. ADR 0001's activation function (logistic gate, floor, mass,
  refractory, measured onward change) was not built (backlog 0054, `proposed/ripple_wave/0001`).
- No surprise or novelty signal in the runtime; `dream_signals.py` "novelty" deduplicates emissions only.
- Valence (`journal.py`, kinds include `revalued`) is orthogonal to attention by contract; this item does not read it.
- Reverse lookups: cards list their evidence in `known_source_ids`, summaries point at their sources with
  `summarizes` edges, incoming edges are indexed (`idx_triples_object`). The live homes are vectored.

## Scope
In (v1, the smallest truthful slice of 0054):
1. `memq_ripples` and `memq_ripple_gates` beside the queue; every gate decision recorded with its potential.
2. `seed_ripple` (magnitude from the reader's enum, scaled by the measured vector distance, never raised; an election
   re-reads the seed first and its neighbours wait for it; `dry_run` = the bound read; idempotent).
3. Propagation: record edges both ways (`RELATION_WEIGHTS`; context relations and usage trails excluded), cards on the
   source's evidence, the vector top-k; potential = impact x reliance x decay 0.5, accumulated per ripple; floor 0.1 on
   the logistic; at most 2 hops, 20 reconsiderations per ripple and per window, one reconsideration per memory per
   ripple; the rest in `left_out`, warned, never dropped.
4. `settle_reconsideration`: `unchanged` writes nothing; `rewritten` hands on `min(received, measured)`.
5. Protected kinds never reconsidered, listed in `left_out` as "protected: the entity's own act".
6. `ripple.consolidate` leased only in a `night` window; `form_consolidation` forms the `summary_role:
   re-understanding` record (`summarizes` every changed memory, `derived_from` the seed), never batch-rewritten.
7. Reads `ripples`, `ripple`; `refresh_ripples`; `revert_ripple`.
8. Docs: `memory-system.md` "Sleep and dreams" describes v1 and points at 0054; `api.md`; ADR 0001 status.

Out: mass, the logistic gate's refractory period across passes and edge learning (0054 proper); closures caused by a
ripple (v1 closes nothing); any surprise valence; prompts (runtime).

## Dependencies
0059, 0060. The runtime reader is 0869; detection is runtime 0870.

## Acceptance Criteria
- [x] A deep change spreads one hop; a shallow one does not.
- [x] The floor stops the tail; a cycle dies within 2 hops; nothing is reconsidered twice in one ripple.
- [x] Two sub-threshold changes on one neighbour together cross the gate.
- [x] A budget stop records `left_out` equal to what was not enqueued, with a warning.
- [x] An `unchanged` reconsideration writes no version and is recorded as settled.
- [x] Protected kinds are never enqueued; they appear in `left_out`.
- [x] Every gate decision is stored with its potential.
- [x] `ripple.consolidate` is never leased outside a nightly sleep window, and its record links every changed memory.
- [x] Each test has a mutant that removes its mechanism and turns it red.

## Testing
- `python -m pytest tests/test_ripple_v1.py -q`
- `python -m pytest tests -q -m "not integration and not lmstudio"`

## Report

Implemented 2026-11-08 on `main` (`ripple.py`; constants in `activation_gate.py`).

- The gate's constants are AbstractNote's R7 calibration (k 6, θ 0.5, floor 0.1, decay 0.5; loop gain 0.75),
  quoted in `activation_gate.py`; the entity-home calibration of the reader's rewrite noise is root backlog 1137.
- `rewrite_digest` reports `cosine_distance` between the old and new vectors, so a settle needs no recomputation.
- Owner strictness (ADR 0003 decision 2): only the seed owner's memories are candidates.
- Tests: `tests/test_ripple_v1.py` (29 cases, both substrate pairs, plus the similarity channel with a controlled
  embedder). Mutants R1-R8 (listed in the module docstring) each turned their test red; files restored byte-exact.

## Completion report (2026-11-10)

Outcome: done for this item's scope, which is memory's engine. Every acceptance criterion above was met by `09686e0`
(2026-11-08) and holds at the release commit `5c6136b` (abstractmemory 0.5.0, CHANGELOG `[0.5.0]` "Added: the memory
task queue (0060) and ripple v1 (0061)"). The ripple verbs refuse a home opened without `task_queue=True`
(CHANGELOG Upgrading); `form_consolidation` takes the "what this changes" record's title and words from the host's
reader (its `title` and `text` arguments).

THE CONSUMERS REMAIN DEFERRED. On 2026-11-10 nothing outside AbstractMemory calls `seed_ripple`,
`settle_reconsideration` or `form_consolidation` (0 hits in `abstractruntime/src` and `abstractgateway/src`), and
the tracked runtime drain (`abstractruntime/identity/authoring.py` `drain_authoring`) leases only `title.author` /
`digest.author`, so no ripple is seeded on any live home and no `ripple.reconsider` / `ripple.consolidate` task is
ever leased. Detection (the entity's `revise` election) and the drain of the two ripple kinds are root backlog 1172
(proposed, paused) over root 1171 (planned, paused). Memory's side of that seam is filed as
`proposed/ripple_wave/0063_ripple_v1_consumer_seam.md`.

Validation:
- `tests/test_ripple_v1.py` (both substrate pairs plus the similarity channel); mutants R1-R8 red (the Report above).
- Release suite at `5c6136b`: `abstractmemory/untracked/release-0.5.0/pytest-full.log`, 2291 passed, 3 skipped,
  2 xfailed, exit 0. Re-run on 2026-11-10 at `5c6136b` of the 17 feature modules (ripple included): 605 passed,
  2 skipped.
- No live validation: there is no consumer (above).

Docs: CHANGELOG `[0.5.0]`; `docs/memory-system.md` "Sleep and dreams" (v1, pointing at 0054); `docs/api.md`.
ADR state: [ADR 0001](../../../adr/0001-altered-memories-ripple.md) records "Implemented (v1)" with a link to this
item's planned path, which the pointer file keeps valid. No new ADR.

Residual risks and follow-ups:
- 0054 (planned) keeps the rest of the process: mass, the refractory period across passes, edge learning, closures
  caused by a ripple, and the calibration of the summary-distance threshold against the entity homes' reader.
- `proposed/ripple_wave/0001` keeps structured closure causes and change records for type and relationship changes.

Backlog drift found: the Report's "the entity-home calibration of the reader's rewrite noise is root backlog 1137"
is stale. Root 1137 is another item (follow-ups after the 0.13.1 wave; root
`planned/understanding-pass/README.md`: draft ids were never filed, "use the root ids"); the calibration is in
0054's scope. Likewise "runtime 0870" / "runtime 0869" in the header are drafts; the tracked items are root 1172 and
1171.
