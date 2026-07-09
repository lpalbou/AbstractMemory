# Proposed: sleep() — report-first maintenance, source-preserving consolidation, dream traces

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: Medium
- Components: maintenance module, ReflectorProtocol, tests, docs

## ADR status

- Governing ADRs: AbstractFramework `0005-memory-architecture.md`,
  `0026-truncation-policy-and-contract.md`
- ADR impact: Needs new ADR at promotion (maintenance boundaries are durable
  policy: what maintenance may never touch).

## Context

Memory that only accumulates degrades: duplicates pile up, contradictions
persist unresolved, structure fragments. The fork's answer — validated in
production — is a REPORT-FIRST maintenance pass with deterministic analysis
and only low-risk, source-preserving writes, plus an optional "dream" trace
(at most one metacognitive record per pass). Its hard boundaries are the
transferable core: maintenance must never mutate source records, attention,
prompt state, or closure records.

This package upgrades the fork's analysis with embeddings (its near-dup
detection was token-set Jaccard; ours is vector cosine) and with
closure-aware contradiction candidates (a channel the fork lacked).

## Current code reality

- Nothing exists. Depends on: `0021` (records; consolidation writes Summary
  records), `0019` (embeddings for near-dups), `0017` (journal stats,
  bindings), `0010` (closure records for contradiction candidates), `0018`
  (attention boundaries).

## Problem or opportunity

Without maintenance, the no-erasure design (`0018`) eventually buries recall
under redundancy — the fork's own graph "accumulates never-selected memories"
with only a diagnostic planned. Designing maintenance WITH the memory system
(not after it) avoids inheriting that pile-up.

## Proposed direction

1. `ReflectorProtocol` (injected; the second and last LLM-adjacent protocol):
   `reflect(ReflectionRequest{purpose: "dream"|"record_metadata", context,
   deadline_s}) -> ReflectionResult{fields}` — used by `sleep(mode="dream")`
   here and available to hosts for `remember` metadata drafting (`0021`).
2. `sleep(*, scopes, mode="report"|"consolidate"|"dream", reason (required),
   max_candidates=2, near_dup_threshold=0.83, proposal_ids=(),
   reflector=None) -> MaintenanceReport`:
   - `report` (read-only, deterministic): duplicate titles (canonical key);
     near-duplicates via digest-vector cosine ≥ threshold (no embedder →
     token-set Jaccard fallback labeled `#FALLBACK`); isolated records (no
     links); contradiction candidates (recorded disagrees_with pairs + live
     records still supporting closure-retracted assertions); facet bridges
     (records sharing ≥2 DF-banded anchors with no recorded link — proposal
     only); journal pressure stats (event counts, fold-window); bounded
     `consolidation_proposals` + `maintenance_questions` with source ids,
     risk labels, caveats. All salience from structured metadata + measured
     scores — no hardcoded lexical filters (fork ADR rule).
   - `consolidate` (low-risk writes only): from duplicate-title/near-dup
     proposals (optionally restricted via `proposal_ids`), create ≤
     `max_candidates` Summary records with summarizes links to EVERY source,
     deterministic template text (no model), indexed + prompt-inactive,
     `source="maintenance"` bindings, deduped by sorted source-set key.
     Broad scopes rejected for writes.
   - `dream` (requires reflector; absent → actionable error, no silent
     fallback — a deterministic "dream" would be fake metacognition): at most
     ONE `dream` record per pass, only when the pass has a salient signal
     (a proposal, an open question, an under-linked facet, a prior unresolved
     dream anchor); weak mentions links to touched sources; provenance keeps
     the bounded operation ledger + debug ref; indexed + inactive. Dream
     records are experiential traces, never promotable as facts.
3. HARD BOUNDARIES (enforced, tested, stated in every report): never mutates
   source records; never writes/deletes attention events; never changes
   prompt_state; never touches closure records; never searches or writes
   broad scopes for candidates. Reports propose; only remember/bind/close
   surfaces dispose.

## Why it might matter

Keeps the no-erasure memory healthy (dedup pressure, contradiction surfacing,
structure repair proposals) while structurally guaranteeing maintenance can
never corrupt truth, attention, or prompts — the property that made the
fork's sleep passes shippable.

## Decision boundaries

- Edge-creation split (agreed with the runtime agent, a2a 0001
  20260706T170635Z-memory-01): FORMATION-time edges are structural only —
  true by construction at write time (`precedes` between consecutive turns,
  `derived_from` reply→user record, deterministic `mentions`, fan-out capped)
  and are the RUNTIME's formation policy; CONSOLIDATION-time edges are
  semantic — anything requiring judgment (near-duplicate links,
  supports/disagrees_with, facet bridges) and belong HERE, report-first,
  bounded, source-preserving. Rule of thumb: if a human could dispute the
  edge, it waits for consolidation; mechanical bookkeeping forms immediately.
- Consolidation text is deterministic template output in v1 (model-written
  summaries are a possible later upgrade gated on the reflector, never a
  requirement).
- `dream` is the only LLM-touching mode and it is optional, bounded to one
  record, and quality-gated by salience.
- Scheduling is host policy (gateway cron, operator command); the package
  only exposes the pass.

## Promotion criteria

Promote last in Track D with `0024`; requires `0021`+`0019`+`0017`+`0010`.

## Validation ideas

- Report determinism: identical stores → identical reports (modulo
  timestamps).
- Near-dup: embedded fixture pairs above/below threshold classified
  correctly; Jaccard fallback labeled when no embedder.
- Contradiction candidates: closure-retracted assertion + live supporter
  surfaces as a candidate.
- Consolidate: sources untouched (byte-identical rows), Summary correct,
  cap respected, re-run dedupes, broad scope rejected.
- Dream: no reflector → actionable error; with stub reflector → ≤1 record,
  salience gate respected (empty pass creates nothing).
- Boundary regression: journal diff after report mode is empty; attention
  scores before/after any mode are identical.

## Non-goals

- No automatic write-time contradiction resolution (mechanism-only supersede
  stays `0010`; SOTA evidence: mem0 retired LLM write-time conflict
  resolution).
- No memory deletion or archival of truth (journal archival is host policy).
- No scheduler in the package.

## Guidance for future agents

Enforce the boundaries in code (assertions/tests), not in prose. If tempted
to let maintenance "fix" records in place, stop — that is what closure records
and revision composition are for.

## Status: IMPLEMENTED v1 (2026-07-07, fork-faithful port with named divergences)

Shipped in `src/abstractmemory/consolidation.py` after the codex-fork study
(a2a 0007/20260707T062609Z): `structural_report` (pure read — components
over COMPONENT_RELATIONS edges only, a real predicate allowlist since the
2026-07-07 URGENT correction: CONTEXT_RELATIONS (written_amid/mentions)
and unknown predicates route to already-associated context pairs, never
adjacency; co_selected trails likewise; isolated/duplicates/facets),
`dream_pass` (cross-component bridge proposals; single-facet pairs become
questions; salience floor; at most ONE `kind="dream"` record per pass via
remember_many, idempotent by report fingerprint; parent_dream_ids chaining;
quiet nights are valid nights), `unresolved_dreams` (heartbeat wake reason).
Guards enforced in tests (tests/test_consolidation.py), not prose:
maintenance deposits NOTHING; dreams never feed the next pass; never enter
identity seats; never outrank lived memory.

Named divergences from the fork (our architecture ruled):
- No rank-0-in-probe: dreams rank as summary peers (derived artifacts never
  gate or dominate recall); normal admission only.
- Formation via remember_many (frozen-seam write discipline + free
  idempotency), not a private side-channel.
- UPGRADE: vector bridge signal from persisted store embeddings where homes
  have them (the fork is lexical-only; its own dream questions admit the
  lexical-residue false-positive risk).

## Status addendum: PHASE 1 IMPLEMENTED (2026-07-09, maintainer-approved)

The fork's FIRST sleep phase ("data_quality_tending") and the deterministic
cadence (fork 770) shipped in `src/abstractmemory/maintenance.py` under the
maintainer's explicit go ("the goal during the sleep phase is to essentially
do maintenance of the graph and help organize the memories of the day, fix
metadata issues, summaries, improve relationships"):
`maintenance_report` (pure read: metadata gaps report-only, same-kind
duplicate-title groups, near-dup pairs — Jaccard ≥ 0.65 OR stored-vector
cosine ≥ 0.90 upgrade —, shared-source groups, isolated-link proposals,
edge-suppression closure candidates, operations ledger),
`consolidation_pass` (≤ N inactive review-gated `kind="summary"` candidates,
sorted-source-set idempotency, sources byte-untouched, as_of writes refused),
`maintenance_due`/`last_maintenance_seq` (material-half cadence; the clock
stays host policy), `sleep_pass` (tend → dream, one call for the runtime's
on_sleep hook). Loop-breaker: candidates never re-enter tending inputs.
Guards in `tests/test_maintenance.py` (26 checks, both stacks; suite 568).
The 0023 `ReflectorProtocol` dream mode remains deliberately NOT built —
the shipped deterministic dream (fork-faithful) superseded it.
