# 0028 — Lateral inhibition: theory and when to adopt (discussion)

## Metadata
- Created: 2026-07-05
- Status: Proposed (theory / discussion — not a build order)
- Owner: memory track (drafted by `runtime` at the maintainer's request; memory to own/refine)
- Depends on: 0018 (attention/decay), 0026 (spreading activation + working_set)
- Decision: **deferred out of v1**; ship spreading + decay first, measure, then revisit.

> This item is a theory note, deliberately not scheduled. It exists so the idea is
> captured with its rationale and its risks, so a future decision is evidence-based
> rather than aesthetic. The v1 recommendation (from both agents and the fork's own
> history) is to NOT ship inhibition until the emergence experiment shows a concrete
> need.

## What lateral inhibition is

In neuroscience, lateral inhibition is competition: an active neuron suppresses the
activation of its neighbors, sharpening contrast (edge detection in the retina is
the canonical example). In memory/activation models it is the "competition" half of
a winner-take-more dynamic — when several memories are co-activated by a cue, they
partially cancel each other so the strongest, most distinctive few dominate rather
than a diffuse cloud of weakly-related nodes.

In our terms: after cue-seeded spreading activation over the graph (0026), a raw
activation field `A_i` is produced. Lateral inhibition would post-process that field
so that mutually-redundant or mutually-competing nodes reduce each other's score
before the working-set is cut to budget.

## What it could bring to our graph

1. **Hub-explosion control.** Dense graphs have high-degree "hub" nodes (a much-
   mentioned entity, a popular lesson) that spreading activation lights up for almost
   any cue. Inhibition (specifically ACT-R's *fan effect* — activation divides across
   a node's many associations) prevents a hub from crowding the working set on every
   turn. Synapse (2026) cites exactly this as the reason it adds inhibition to
   spreading activation. This is the strongest argument for it.
2. **Redundancy decorrelation.** If five near-duplicate memories all match a cue,
   plain top-k fills the budget with five copies of one idea. Inhibition (or the
   cheaper cousin, MMR-style redundancy penalty) keeps one and frees budget for
   diverse, complementary context — better use of a scarce token budget.
3. **Contrast / focus.** It sharpens the boundary between "in the working set" and
   "not", which is desirable if we want a crisp emergent STM rather than a soft
   gradient that the budget cut makes arbitrary anyway.

## What it risks (why it is deferred)

1. **It can hide relevant memory.** Suppression is, by construction, a mechanism for
   *not surfacing* things. Mis-tuned, it silences a memory the agent needed. This is
   the highest-severity risk and the reason it must be gated on measurement.
2. **The fork's own lesson.** The reference implementation's history shows that
   "clever" suppression/attention mechanisms shipped before they were measured were
   reverted. Inhibition is the archetypal clever mechanism.
3. **Determinism/tuning cost.** Inhibition adds coupled parameters (who inhibits
   whom, how strongly, normalization scheme) with no ground truth to tune against
   until the experiment exists. It also couples node scores to each other, making the
   working set harder to explain ("why did X drop out? because Y was present") — in
   tension with 0026's mandatory human-readable `cues`.
4. **It competes with cheaper tools.** Much of the redundancy benefit is obtainable
   with a diversity penalty (MMR) or the reserved-slot scheme already in
   `RecallBudget`. The fan-effect benefit is obtainable by normalizing activation by
   node degree — a one-line divisive step — without full pairwise inhibition.

## Design sketch (if adopted later)

Preserve the hard contract from 0026/0020: **relevance admits, activation reorders;
nothing suppresses a channel-matched candidate to zero.** Inhibition would therefore
act only on the *ordering/among-activated* layer, never as an admission gate:

- **Cheap first (preferred):** divisive normalization by local degree / fan
  (`A_i ← A_i / (1 + λ·fan_i)`) to defang hubs, plus an MMR redundancy penalty on the
  final budget cut. No pairwise dynamics; deterministic; explainable ("down-weighted:
  high-fan hub" / "dropped: redundant with X").
- **Full inhibition (only if the cheap version proves insufficient):** iterative
  divisive normalization over the co-activated set,
  `A_i ← A_i / (σ + Σ_j w_ij·A_j)`, bounded iterations, fixed order, `ε=0` for
  determinism. Every suppression must still emit a `cue` explaining it.

Placement: a pure post-processing stage between spreading (0026) and the budget cut,
inside `reconstruct`; off by a config flag defaulting off.

## Adoption gate (evidence, not taste)

Add inhibition only if the emergence experiment (thread `0002`) shows, at equal token
budget, at least one of:
- working sets dominated by high-fan hub nodes across unrelated cues (measurable:
  hub node appears in >X% of working sets regardless of topic), or
- budget wasted on near-duplicate memories (measurable: intra-working-set redundancy
  above a threshold), and
- a diversity/normalization baseline (the "cheap first" version) fails to fix it.

If the cheap normalization + MMR fixes the observed problem, full lateral inhibition
should remain deferred indefinitely.

## References
- Collins & Loftus (1975) — spreading activation (the field inhibition would modify).
- Anderson, ACT-R — the *fan effect* (activation divides across associations).
- Synapse (2026) — spreading activation + lateral inhibition + fan effect for
  hub-explosion control in dense agent-memory graphs.
- Reference codex fork — prior evidence that unmeasured suppression was reverted.
