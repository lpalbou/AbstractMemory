# ADR 0001: An altered memory ripples through the memories connected to it

Status: Accepted (operator ruling, 2026-10-21; activation model confirmed with the operator the same day).
Amended 2026-10-27 (operator ruling): the ripple is AbstractMemory's process end to end, not a consumer's
(ADR 0002). Aspirational: AbstractMemory does not implement it yet; AbstractNote holds a prototype
(its ADR 0008 propagation lane) that is to be absorbed here, not kept as the implementation.

## Context

A memory system is not a filing cabinet. When one memory is altered, because new evidence arrived, because an
earlier record was found, because a causal root was identified, or because a reading was revised, what we
thought we knew about the memories connected to it is also in question. Sometimes the effect is subtle: an
incremental refinement of a neighbour's summary. Sometimes it is dramatic: a restructuring of a whole region of
the graph, as when a new causal root gives a deeper understanding of several things we thought we understood.
Dramatic changes are rare in a stable system that has learned enough; in the early days of a memory system
they happen often.

Today the stores treat an alteration as local: `close_assertion`, closure records (`retract`, `supersede`,
`reinterpreted`), reinforcement, attenuation and silencing change one record's standing or window, and the
sleep passes (`consolidation.py`: `sleep_pass`, `consolidation_pass`, `dream_pass`, `maintenance_report`)
tend the graph without re-evaluating the neighbours of a record whose meaning changed. Nothing in the library
asks "given that A changed this much, what must be reconsidered about B and E?".

## Decision

1. **A change in a memory is an event with a magnitude, not a silent update.** Any operation that alters what a
   memory means (its type or kind, its summary or content, its belief window, its relationships) MUST produce a
   change record that names the memory, what changed, and a measured magnitude. The magnitude combines the
   dimensions that matter for meaning: type change, distance between the old and new summary (an embedding
   distance, calibrated above the writer model's own rewrite noise), the share of statements replaced, and the
   share of relationships replaced. The thresholds live in one named place and are tuned by measurement, never
   hard-coded in several places.
2. **The ripple is evaluated hop by hop and decided by effect, not by distance alone.** When memory A changes,
   every memory connected to A is a candidate for reconsideration, weighted by how much it relied on A
   (the strength and recency of their relationship, the share of its own statements that involve A). Each
   candidate is reconsidered; if the effect on B is minor (below the magnitude threshold once measured), the
   ripple stops at B; if the effect on E is large, E's own change becomes a new event and the memories
   connected to E are candidates in turn, iteratively, until no candidate's measured change clears the
   threshold.
3. **Propagation carries decaying impact and never amplifies.** The impact handed from A to its neighbours is the
   measured magnitude scaled by reliance and by a decay factor; a reconsidered memory may hand on at most what it
   received or what it measured itself, whichever is smaller; a floor stops the spread. Cycles therefore die out
   by damping rather than by assuming the graph is a tree: the memory graph is not a DAG and the rule must not
   require one.
4. **Numbers choose, meaning is decided by the reader.** Magnitudes, reliance weights, decay and order select
   which memories are reconsidered, in which order, and under what budget. What a reconsidered memory now means
   is decided by the same reader that wrote it (a model, or the consumer's own interpretation step), never by
   string rules on content.
5. **Every ripple is bounded, visible and resumable.** Before a ripple runs, the system can say how many memories
   may be reconsidered and why (the sources and their magnitudes). A ripple runs under a budget; when the budget
   stops it, what was left is recorded and reported, never dropped silently (root framework ADR-0026). A second
   pass over the same change, with nothing new, costs no reader call: an unchanged reconsideration is settled by
   comparing structure, and is itself recorded.
6. **History is kept.** A reconsidered memory keeps its previous reading in the journal; the as-received view of
   the graph before the ripple stays answerable. Closures caused by a ripple carry their cause (the source memory
   and the hop count) so that a later reader, human or model, can see why a belief moved.
7. **The ripple is an activation with a threshold, not a distance rule.** Whether a connected memory is
   reconsidered is decided by an activation function over the impact it receives: each memory accumulates the
   reliance-weighted impacts of every changed neighbour within a pass (several small changes together can
   cross what none crosses alone), the accumulated potential passes through a smooth gate (a logistic
   `1 / (1 + e^-k(x - θ))` or an equivalent monotone function; the gate is a configuration, not a model), and
   the memory is reconsidered when the gated potential is above the floor. The potential's input is a weighted
   sum of standardised signals (type change, summary distance, statements replaced, relationships replaced),
   each standardised against the reader's own rewrite noise, and divided by the memory's **mass** (how much
   evidence already supports it): a thinly evidenced memory moves on little, a heavily evidenced one needs
   more, which is how a stable system comes to ripple rarely without anyone scheduling quiet. Onward
   propagation beyond one hop uses the **measured** change of the reconsidered memory, never the predicted
   impact alone. Termination is guaranteed by three rules together: a memory is reconsidered at most once per
   pass (a refractory period), impact never amplifies (loop gain `decay × max reliance × max gate slope < 1`),
   and the floor stops the tail. Every gate decision is recorded with its potential, so thresholds can be
   re-tuned from the record without re-running the ripple.
8. **Edges learn.** The reliance weight of an edge may be adjusted from history: an edge whose ripples
   repeatedly produced an unchanged reconsideration conducts less next time; an edge whose ripples produced
   real change conducts more. Adjustments are bounded, recorded, and never silence an edge entirely.
9. **Stable systems ripple rarely; young systems ripple often, and that is expected.** The cadence predicate of
   the sleep pass (`maintenance_due`) and any consumer's scheduler MUST treat pending ripples as work due,
   with priority given to the largest sources, and MUST NOT suppress ripples to keep a young system quiet.

## Consequences

### Positive
- The graph says what we know *now*, with the understanding the newest evidence allows, instead of what we
  happened to believe when each memory was first written.
- Deep changes (a new causal root, a re-dated archive, an entity that turns out to be a person as well as a
  project) reach the memories that leaned on them, in a bounded and explainable way.
- Every moved belief has a cause on record.

### Negative
- Reconsideration costs reader calls; a young system pays more. Budgets and the no-call settle rule bound it,
  and the operator sees the bound before the run.
- Thresholds are empirical; a wrong threshold either spreads noise (too low) or freezes understanding (too
  high). Calibration against the reader's own rewrite noise is mandatory before a threshold is trusted.
- The journal grows: one record per reconsideration and per change event.

### Neutral
- AbstractMemory owns the whole ripple: the primitives (change records, closure causes, additive windows,
  journal history), the propagation and activation, the budget and the reconsideration step. The reader that
  decides what a reconsidered memory now means (decision 4) is a model the host supplies to AbstractMemory
  (an injected reader), so the process lives here while the model choice stays with the host. Consumers
  (AbstractNote, AbstractEntity, gateway apps) trigger and display ripples; they do not implement them.

## Enforcement

- A pull request that adds or changes an operation altering a memory's meaning MUST either emit a change record
  with a magnitude or state in the ADR-linked backlog item why the operation cannot (and what the consumer must
  do instead).
- Closure records written because of a ripple MUST carry the cause (`source memory`, `hops`); a reviewer rejects
  a cause-less ripple closure.
- No code path may cap a ripple without recording what was left out (`left_out`) and warning; the marker
  `#[WARNING:TRUNCATION]` applies to any bounded preview of a ripple's members.
- Threshold constants live in one module with their calibration quoted; a second copy of a threshold is a
  review failure.
- Docs: `memory-system.md` "Sleep and dreams" MUST describe the ripple when the pass gains one; until then it
  states that the ripple is planned in AbstractMemory (backlog 0054) and points here.
- A consumer package MUST NOT add its own ripple, propagation or activation logic over memories; a gap in
  AbstractMemory is raised as an AbstractMemory backlog item (ADR 0002).

## Validation

- Unit: a deep change spreads one hop; a shallow change does not; two sub-threshold changes on the same neighbour
  together cross the gate; a heavily evidenced memory needs more impact than a thin one; the floor stops a hub;
  a cycle dies within a bounded number of hops with the loop gain below one; a second pass with nothing new makes
  no reader call; a budget stop records `left_out` equal to what is pending; every gate decision is on record with
  its potential. Each check MUST go red when its mechanism is removed (mutation list in the test file).
- Calibration: the summary-distance threshold is set from a measured distribution of same-memory rewrites by the
  reader in use, and the report that set it is linked from the constants module.
- Scenario: a dated archive that changes the type of one memory (project → person) must reconsider the memories
  connected to it and leave unrelated regions untouched; the as-received view before the ripple still answers.

## Backlog links

- Proposed: [ripple_wave/0001_change_records_and_ripple_primitives.md](../backlog/proposed/ripple_wave/0001_change_records_and_ripple_primitives.md)
  (the AbstractMemory primitives: change records with magnitude, closure causes, `maintenance_due` counting pending
  ripples, `narrow_assertion`).
- Planned: [knowledge_graph_convergence/0054_ripple_propagation_and_activation.md](../backlog/planned/knowledge_graph_convergence/0054_ripple_propagation_and_activation.md)
  (the propagation, activation and reconsideration process in AbstractMemory).
- Prototype to absorb, not to keep: AbstractNote ADR 0008 and its propagation lane (R6, 2026-10-20/21: calibrated
  thresholds, decay 0.5, floor 0.1, one hop per pass, budgeted stage, no-call settle), see
  `abstractnote/docs/adr/0008-interpretation-is-a-derived-view.md`, `abstractnote/untracked/briefs/R6-propagation-design.md`,
  and AbstractNote's unmerged branch `retro/integration` (`recall/propagation.py`, `recall/activation.py`).

## Related

- ADR 0002 (AbstractMemory owns the semantic temporal memory graph and all its processing).
- Root framework ADR-0026 (truncation policy: nothing silent).
- `memory-system.md` (attention, closures, sleep and dreams), `api.md` (closure records, `close_assertion`, consolidation).
- AbstractEntity's maintenance phases (the sleep phase where the graph is tended) as prior art for a scheduled, bounded night.
