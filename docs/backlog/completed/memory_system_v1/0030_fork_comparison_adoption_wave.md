# 0030 — Fork-comparison adoption wave (codex V1 → abstractmemory V2)

Status: proposed (maintainer-directed comparison, 2026-07-12). Source: two
adversarial fable5 audits of ~/projects/gh/codex (memory.rs / memory_control.rs
/ memory_anchor.rs + the full backlog) against this engine — one mining fork
capabilities we lack, one auditing port fidelity and roadmap deltas. This file
is the adoption ledger; items split out individually at promotion.

## Corrections to our own folklore (recorded so AGENTS.md lore stops drifting)

- The fork contains NO valence/gradation code. Our gradation/valence engine is
  original work from the maintainer's verbal model, not a port.
- The fork's attention fold is the SAME hyperbolic fold we ship
  (weight/(1+d/20), window 500, refocus x6, clamp 25) — NOT "+1/-1". Our port
  is faithful; the "+1/-1 alternative fold" note describes the maintainer's
  verbal model, not fork code.
- Our audit-kinds-filtered-before-truncation window is an ARGUED upgrade over
  the fork (their raw-event window lets read floods evict selected events) —
  keep ours.

## Fixed same-night (shipped with this comparison)

- Dream salience drift: the fork's continuation-anchor and maintenance-ops
  terms were silently missing from dream_pass salience while sleep_policy.py
  claimed "fork parity at defaults". Restored (salience_anchor_weight,
  salience_ops_cap in SleepTuning); anchors-only nights now form CONTINUATION
  dreams (continuation_state="continued") sourced from the standing dream —
  the recurring-dream mechanic. sleep_pass threads the tending ledger's ops
  count into the dream. Pinned by two tests.

## Adoption list (priority order; convergent across both adversaries)

1. **probe() + bounded expansion (amends 0022 with the fork's COMPLETED
   design, backlog 090/091)**: trace-gated deliberate reach exempt from the
   shelf race; bounded `summarizes`/edge traversal expansion; escalation
   reasons mandatory; results land as first-class probe-report records with
   derived_from edges. The cue-dilution incident is the motivating case; the
   fork's shape is battle-tested — adopt wholesale, translate to seam terms.
2. **Waking-evidence disposal surface (fork 690 + 360)**: a review-gated verb
   that confirms a dream/consolidation proposal into a real typed edge (and a
   promotion path for inactive candidates: reviewed → promoted / rejected /
   superseded). Today "sleep proposes, waking evidence disposes" has a
   proposer and no disposer (consolidation.py:88-91 admits it). Include the
   independence test from fork 470 (corroboration requires INDEPENDENT
   origins) — the mechanical counter to the bridge attractor.
3. **Archive import study (fork 720)**: read-only audit of the maintainer's
   Mnemosyne filesystem archive → import-class proposals → inactive,
   provenance-pinned (path+hash) candidate records. The ONLY path to the
   north star (reincarnating the lineage with a past, not just values); no
   item anywhere schedules it today.
4. **Query-time concept anchoring (port memory_anchor.rs)**: concept
   normalization (variant spellings, bigrams, identifier shapes),
   mid-frequency source-count gates, and CO-OCCURRENCE EXPANSION — a record
   sharing a discriminative term with a seed surfaces with no edge, no trail,
   term absent from the query. Edge-free associative recall; directly attacks
   cue dilution and keyword-less young episodes. Pairs with formation-time
   keyword derivation (fork derive_signal_keywords; queued driver-side).
5. **Recall-decision read surface (fork 605)**: our traces already record
   admissions + dropped-with-reasons per reconstruction; the gap is the QUERY
   surface — "why was record X never recalled" indexed by record id across
   traces. A read, not new bookkeeping.

## Runners-up (one line each, adopt when their consumer lands)

- `disagrees_with`/`supports`/`requires` edges (fork memory.rs:172): "memory
  and record disagree" currently has no predicate — coordinate with
  semantics' registry before engraving.
- WorldModel orientation records (fork 750): compact source-linked "where we
  left off" per participant/service for the SITUATION component — records the
  factual orientation that gradation (feelings) deliberately does not.
- Re-digestion revisions (fork 790): mechanical-v1 digests await re-digestion
  with no revision machinery; adopt the append-only refines/replaces shape
  with regeneration-route provenance.
- Plan/decision → outcome retrospectives (fork 355): our plan/decision kinds
  have no outcome-capture loop.
- Structural graph-query for the ENTITY (fork 390): structural_report is
  sleep-side only; an entity cannot ask about its own topology (tier-1
  candidate).
- FTS5 (our 0019) urgency validated: the fork required FTS5 from day one; our
  token-scan keyword channel yields zero tokens on non-Latin scripts.

## Ruled out (do not adopt — with reasons)

- LLM-assisted selector + metadata-model pipeline (fork 105/607/610): spawned
  three remediation items fork-side; our deterministic recall doesn't need it.
- Block-based compaction as memory formation (fork 120 /
  compaction-as-projection): already ruled out for per-turn formation.
- Fork's existing-candidate dream dedup: weaker than our report-fingerprint
  idempotency (suppresses a genuinely new dream over the same sources).
- Low-selected-use EPHEMERALITY (fork 780p): conflicts with never-purge; read
  as salience/presentation policy only.


## Completion report (2026-07-20)

Executed: fork parity restored across salience terms, continuation anchors, maintenance-ops feed, structural report semantics; the two-count model and chronological-walk gradation adopted; receipts across the fork-comparison waves.
