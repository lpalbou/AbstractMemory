# Proposed: Stimulus-driven spreading activation + emergent working_set view

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: High
- Components: spreading module, reconstruct view flag, seam dataclasses, tests; co-designed with the runtime agent (a2a thread 0001)

## ADR status

- Governing ADRs: AbstractFramework `0007-active-context-and-memory-provenance.md`,
  `memory-recall-levels.md`
- ADR impact: Needs new ADR (the emergent working-memory model — two-factor
  activation — is durable cross-package policy; write at promotion).

## Context

The maintainer's memory model (relayed via the runtime agent, a2a thread
`0001-runtime-memory-orchestration`, and grounded in the codex-fork reference
implementation): memory is ONE durable, usage-weighted graph. Working/short-term
memory is NOT a separate store — it is the high-activation subgraph that
EMERGES from two factors:

1. recency + frequency of use — the decaying trail left by selection
   (item `0018`: base-level activation);
2. stimulus — every incoming message is a cue; activation SPREADS from cue
   matches through the graph and gives the agent focus.

Established mapping (shared vocabulary with the runtime agent): Cowan/Oberauer
(WM = activated LTM region), ACT-R `A_i = B_i + Σ W_j·S_ji`, Bjork (storage
never decays; retrieval strength does), Hebb (co-activation strengthens
links), stigmergy/ACO (pheromone = activation, deposit = access trail,
evaporation = decay). Adjacent 2025-26 work: HippoRAG 2 (PPR over KG),
Synapse (ACT-R spreading + fan effect), CLS-M, MRAgent.

Item `0020`'s DF-banded anchor expansion approximates factor 2 lexically;
this item adds true edge-propagated spreading and the `working_set` view.

## Current code reality

- Nothing exists. Depends on: `0017` (journal), `0018` (base-level
  activation + co_selected pair trails), `0019` (channels — cue matching),
  `0020` (reconstruct pipeline + traces), planned `003` (bounded traversal).
- Seam contract agreed with the runtime agent (a2a 0001/002-memory, 0001/003):
  JSON-serializable frozen dataclasses; pure reads with seq-based `as_of`;
  ONE call — `reconstruct(stimulus, ..., view="shelf" | "working_set")`;
  runtime owns all triggers and deposits the trail via `commit_selection`.

## Problem or opportunity

Without spreading, recall is flat channel-matching: a cue only retrieves what
it lexically/semantically matches. With spreading over trail-strengthened
edges, a cue re-lights the neighborhood the agent actually used together —
focus, priming, and topic coherence emerge from the same substrate that
records use. This is the load-bearing half of the maintainer's "emergent STM".

## Proposed direction

1. ACT-R-shaped activation, mapped onto existing mechanics:
   - `B_i` (base level) = `0018` activation (rank-distance decay over
     selected/pinned events);
   - `W_j` (cue weights) = per-channel match scores of stimulus-hit records
     (`0019`: exact/keyword/vector), normalized;
   - `S_ji` (associative strength) = f(recorded typed edges between records,
     `co_selected` pair-trail activation from `0018`) — Hebbian: edges the
     agent used together carry more spread;
   - `total_i = B_i + spread_i`, both reported separately (decomposition is
     mandatory for the emergence experiment's attribution).
2. Spreading computation (pure function; bounded): seed = cue-matched records
   with `W_j`; propagate over typed edges via the planned-003 frontier walk
   with `SpreadParams{max_hops=2, per_edge_kind_weights, damping, fan_out_cap,
   min_contribution}`; fan-out capping guards high-degree hubs (fan effect);
   cycles terminate by visited-set; every spread contribution is reported as
   a cue (`"spread: via supports from ex:lesson-…"`).
3. `Stimulus` dataclass (seam, agreed): `cue_text`, `patterns`
   (tuple[TripleQuery]), `anchor_record_ids`, `participants`,
   `embedding: list[float] | None` (runtime may pass a precomputed turn
   embedding; else the store's embedder runs), `as_of: int | None` (journal
   seq; `seq_at(iso_ts)` helper for conversion).
4. `view="working_set"` on `reconstruct()`: same pipeline as the shelf view,
   additionally returning the activated subgraph — included edges with
   strength labels, per-item activation decomposition
   `{base_level, spread, total}`, per-channel relevance, cues, stop_reason.
   `min_activation` acts ONLY as a working-set membership threshold — it
   never gates channel-matched candidates (hard contract from `0018`:
   relevance admits, activation reorders).
5. Purity + replay: results are pure functions of (store truth ≤ as_of,
   journal ≤ as_of, stimulus, params); results carry the seq high-water mark
   for the runtime ledger; `journal=False` gives zero-write reads.
6. Open decisions PENDING maintainer input via the runtime agent (a2a 0001
   asks; do not implement until answered):
   - decay math: activity-relative rank distance (`0018`, fork-validated) vs
     ACT-R wall-time power law `B_i = ln(Σ t_k^-d)`;
   - spreading params: per-edge-kind weight differentials, hop philosophy;
   - working-set sizing: token budget vs item count vs activation threshold;
   - lateral inhibition (Synapse-style): recommendation OUT for v1 — ship
     spread + decay, measure, then decide (fork lesson: unmeasured
     suppression mechanisms get reverted).

## Why it might matter

This is the item that makes the memory system cognitively real rather than a
ranked search index — and it is the memory half of the falsifiable emergence
experiment co-owned with the runtime agent.

## Decision boundaries

- Spreading is a pure read; it never writes events (deposit happens only via
  `commit_selection`).
- One call, two views; no separately-maintained working-memory state
  anywhere.
- All constants in `SpreadParams`/`MemoryConfig`; contracts (no gating, no
  audit-event feedback) fixed.

## Promotion criteria

Promote after `0018`/`0020` and the maintainer's answers to the open
decisions; implement together with the runtime's `MEMORY_RECALL` /
`MEMORY_ACCESS` effects (a2a-coordinated, stub-first on the runtime side).

## Validation ideas

- Determinism: identical (store, journal, stimulus, as_of) → identical
  working sets, bit-exact across processes.
- Spreading: a fact stated once, connected by used edges, is re-lit by a
  related cue that does NOT lexically match it (the priming scenario).
- Fan effect: a hub with 100 edges does not flood the working set
  (fan-out cap respected).
- Decomposition: base_level vs spread attribution sums to total; ablation
  (spread off) reproduces `0020` shelf ordering.
- The joint emergence experiment (a2a thread 0002 when opened): scripted
  multi-topic session; probe for a once-stated fact many turns later vs a
  recency+embedding baseline at equal token budget; pass = emergence + focus
  + decay + reactivation. Memory side: working_set + ablation baseline
  (same store, spreading+activation disabled).

## Non-goals

- No lateral inhibition in v1 (pending measurement).
- No PageRank/global graph algorithms (bounded local spread only).
- No trigger logic (runtime owns when; this package owns what).
- No separately-stored working-memory state.

## Guidance for future agents

Read a2a thread `0001-runtime-memory-orchestration` in full before
implementing — the seam dataclasses and the open decisions live there. Keep
the decomposition honest: if you cannot attribute an item's presence to
base-level, spread, or channel relevance with a human-readable cue, the
implementation is wrong.
