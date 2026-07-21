# Completed: reconstruct() — anchor expansion, kind priority, budgeted shelf, selection traces

## Metadata

- Created: 2026-07-05
- Status: Completed (2026-07-20)
- Completed: 2026-07-20
- Priority: High
- Components: reconstruction module, anchor module, traces/snapshots (journal), optional SelectorProtocol, tests

## ADR status

- Governing ADRs: AbstractFramework `0007-active-context-and-memory-provenance.md`,
  `0009-connected-memory-recall-and-provenance.md`, `memory-recall-levels.md`,
  `0026-truncation-policy-and-contract.md`
- ADR impact: May revise existing ADR (recall-levels ADR should reference the
  shelf/trace contract once it exists); supersedes the approach of planned
  `004_recall_trace_and_access_events_contract.md` (contract-first) with a
  running implementation — reconcile at promotion.

## Context

`reconstruct()` is the heart of the high-level system: given a need, return a
budgeted SHELF of scored memory handles with full explanation — never a
prompt. Prompt assembly stays in hosts (runtime packetizer). This ports the
fork's passive-reconstruction stack with its measured bounds, upgraded by
embeddings.

## Current code reality

- Nothing exists beyond raw `query()`. The runtime's `memory_kg_query` +
  recall levels + packetization currently approximate this per-consumer.
- Depends on: `0019` (channels/fusion), `0018` (activation tie-break), `0017`
  (traces/snapshots storage, bindings fold), `0009` (ids).
- Fork spec available from the 2026-07-05 dissection (retrieval-stack spec +
  full API spec agent reports).

## Problem or opportunity

Every consumer that wants "relevant memory for this turn" currently invents
its own pipeline (runtime recall levels, SmartNote query wrapper, ai-space
scans). One implementation with traces makes recall explainable and portable.

## Proposed direction

1. Request/response shapes (journal-serializable dataclasses):
   - `RecallNeed`: `query_text`, optional exact `patterns`
     (tuple[TripleQuery]), `anchor_record_ids`, `kinds` filter;
   - `RecallBudget`: `max_candidates=64`, `shelf_size=12`,
     `token_budget=2400`, `reserved_slots` per channel, `max_anchor_cues=4`,
     optional `deadline_s`;
   - `MemoryShelf`: ordered `MemoryHandle`s (id, kind, title, digest,
     per-channel scores, cues, token_estimate, binding state, scope) +
     `dropped` (id, score, reason) + `selector_route` + `stop_reason` +
     `warnings` + `budget_spent`;
   - `ReconstructionTrace` (journal): fingerprint, need, searched scopes
     (explicit list — never a bare "global"), channels run/degraded,
     candidates with per-channel scores (bounded), selected/dropped with
     reasons, cues, budgets, selector route, stop reason, warnings.
2. Pipeline: bindings fold (`0017`) + closure fold (`0010`) build the
   candidate universe → channels + fusion (`0019`) with reserved slots →
   DF-banded anchor expansion (fork mechanic, ported: concept anchors from
   keywords/entity mentions/title tokens; an anchor is usable only when its
   document frequency across searched scopes is in a band (default 2..16) —
   too rare is noise, too common is a measured stopword (no stopword LISTS,
   fork ADR rule); expansion capped at `max_anchor_cues`; every used cue
   reported) → kind-priority ordering (`0021` kinds; distilled handles before
   raw memories: lesson > instruction > decision > episode > plan > summary >
   … > raw; configurable order, principle fixed) → activation tie-break
   (`0018`, capped) → greedy token-budgeted shelf fill → trace append.
3. Optional precision layer: `SelectorProtocol` (injected; typically
   LLM-backed by hosts):
   `refine(SelectorRequest{query, handles, token_budget, deadline_s}) ->
   SelectorDecision{selected_ids, reasons}`. Contracts: the selector may only
   drop or reorder within the candidate set (never add); on ANY failure
   (exception, timeout, malformed output, hallucinated ids) the heuristic
   shelf is returned unchanged with `selector_route="selector_failed_preserved"`
   (fork's preserve-on-failure rule); running without a selector is fully
   supported (heuristic floor).
4. `commit_selection(trace_id, used_record_ids, ...) -> ActiveMemorySnapshot`:
   the host calls this AFTER placing records into a context; it writes
   `selected`/`co_selected` events via `0018` and appends a snapshot (used
   ids + display metadata + token estimates; references, never payload
   copies). Reconstruction itself writes only inert `listed` audit events —
   searching is free; being used is what strengthens.
5. Scope ladder: callers pass ordered `(scope, owner_id)` pairs
   narrow→broad; broad scopes require an explicit `escalation_reason`
   (recorded in the trace) — the fork's broad-search guard.

## Why it might matter

Delivers the recall-levels ADR's intent with the explainability the framework
requires (every selected AND dropped candidate has a recorded reason), and
gives the runtime a single call to replace its bespoke recall pipeline.

## Decision boundaries

- `reconstruct()` NEVER assembles prompt text and never writes
  attention-feeding events; `commit_selection` is the only strengthening path.
- No deterministic pruning below the shelf; budgets bound output size, not a
  relevance classifier (fork lesson).
- Traces are bounded (candidate lists capped) — observability must not become
  its own storage problem.

## Promotion criteria

Promote after `0017`/`0018`/`0019`; the first consumer is the runtime's
`MEMORY_RECONSTRUCT` effect (tracked in `0024`).

## Validation ideas

- Anchor expansion: sibling records sharing vocabulary with a hit (but not the
  query) are recovered; DF band excludes 1-source and everywhere-concepts.
- Kind priority: at equal relevance, lesson outranks raw memory.
- Selector: malformed/hallucinating selector → heuristic shelf preserved +
  route recorded; healthy selector → refined shelf with reasons.
- Traces: selected + dropped reasons complete; searched scopes explicit;
  budget accounting adds up.
- `commit_selection`: writes events for exactly the used ids; snapshot
  references resolve; a second commit on the same trace is rejected.
- End-to-end judged fixture from `0019` re-run through `reconstruct()` (shelf
  quality ≥ raw fusion quality).

## Non-goals

- No prompt/packet rendering (runtime owns it).
- No auto-selection policy (which turns get memory is host policy).
- No cross-request caching of shelves (hosts may cache; package stays pure).

## Guidance for future agents

Port the fork's bounds and explanation discipline, not its lexical machinery.
Read planned `004` before implementing traces — its access-event vocabulary
merges into the journal taxonomy (`0017`/`0018`), and the trace shape here
supersedes its standalone contract.


## Completion report (2026-07-20)

Shipped: reconstruct.py shelf/working_set views, trace records with admissions, dropped accounting, budget_spent; stable_render_order (0049) for prefix reuse.
