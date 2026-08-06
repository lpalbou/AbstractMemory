# Completed: probe() + expand() — agent-initiated bounded memory exploration

## Metadata

- Created: 2026-07-05
- Status: Completed (2026-07-20)
- Completed: 2026-07-20
- Priority: Medium
- Components: probe/expand module, probe traces (journal), traversal integration, tests

## ADR status

- Governing ADRs: AbstractFramework `0009-connected-memory-recall-and-provenance.md`,
  `0026-truncation-policy-and-contract.md`
- ADR impact: None (implements planned `003`'s traversal as its consumer;
  complements `0020`)

## Context

Two deliberate exploration surfaces, distinct from per-turn reconstruction:

- `probe(query)` — "what do I know about X?": explicit search across scopes
  with an append-only probe trace, kind ordering biased to transferable
  handles, and NO attention side effects (probing must not light up the
  graph — fork's anti-noise rule).
- `expand(record_id)` — "show me the evidence behind this": read-only bounded
  BFS over typed record links with budgets and stop reasons (fork:
  depth≤3, nodes≤12, token-budgeted, zero writes).

These are the tool-facing memory verbs for agents (the fork exposes them as
`query_memory_graph` and `expand_memory_sources` tools) and the operator verbs
for UIs.

## Current code reality

- Nothing exists; ai-space hand-rolls reachability BFS; the runtime resolve
  handler does N+1 label loops.
- Planned `003_bounded_graph_traversal_over_triples.md` specifies the
  traversal primitive (GraphWalk) this item consumes — 003 stays the
  low-level item; this item is its high-level consumer.
- Depends on: `0009` (ids), `0017` (traces), `0020` (shared retrieval
  internals), `0021` (record kinds for follow-groups), planned 003
  (traversal). New input for 003 from the graph-backend investigation: add an
  `(object, predicate, subject)`-shaped index for reverse traversal (SQLite),
  and prefer the Python frontier loop over recursive CTEs (benchmarked
  20–100x faster at this scale).

## Problem or opportunity

Agents need a safe way to interrogate memory mid-task without corrupting
attention or over-pulling context; operators need the same for trust
("what exactly is behind this claim?").

## Proposed direction

1. `probe(query, *, scopes, reason, budget=RecallBudget(shelf_size=8),
   reuse_trace_id=None, reset=False, escalation_reason=None) -> ProbeResult`:
   - runs the `0020` pipeline in exploration mode: heuristic-only (no
     selector), kind ordering preferring transferable handles for broad
     scopes (lesson, instruction, episode, probe_report, summary before raw);
   - trace-scoped: repeating the same query/scope reuses the open probe trace
     (append-only continuation) instead of resetting; `reset=True` starts a
     fresh trace;
   - broad scopes require `escalation_reason` (recorded);
   - writes ONLY inert `listed` audit events.
2. `expand(record_id, *, scopes, follow=("sources","outcomes","lessons",
   "predecessors","relationships"), max_depth=2 (cap 3), max_nodes=6 (cap 12),
   max_tokens=2400 (cap 6000), trace_id=None, report=False, reason=None)
   -> ExpansionResult`:
   - follow-groups map to record links: sources → summarizes/derived_from;
     outcomes → answers/results; lessons → supports/derived_from into
     lesson/instruction records; predecessors → precedes/replaces/refines;
     relationships → all, labeled with the strength vocabulary
     (recorded/supported/temporal/co-selected/inferred — computed labels, not
     stored data);
   - built on planned 003's GraphWalk with per-hop scope/validity filters;
     budgets enforced per hop; explicit `stop_reason`
     (depth_cap|node_cap|token_cap|exhausted) + skipped-path notes;
   - DEFAULT: writes nothing (strictly read-only — the property that makes it
     safe to expose as an agent tool);
   - `report=True`: materializes a `probe_report` record via `remember`
     internals (derived_from links to every expanded source, indexed +
     inactive binding, `cited` audit events) — the operator "keep this
     investigation" path.
3. Result payloads include digest-level content only; bodies/payload refs are
   returned as references with token estimates (hosts decide what to fetch;
   `#TRUNCATION` labels where excerpts are cut).

## Why it might matter

Gives agents and operators safe, budgeted, explainable memory interrogation —
the fork's most-used surfaces in practice — and replaces two consumer
hand-rolls (ai-space BFS, runtime resolve loops) with package calls.

## Decision boundaries

- Expansion never mutates anything by default; the report path is the only
  write, and it is explicit.
- Budgets and caps are enforced in the package, not left to callers.
- Probe results are advisory evidence for agents, never instructions (hosts
  phrase tool outputs accordingly).

## Promotion criteria

Promote after `0020` and planned 003; a natural first consumer is the runtime
exposing both as agent tools (`0024`).

## Validation ideas

- Probe trace reuse: same query/scope continues the trace; reset starts anew;
  broad scope without escalation_reason is rejected.
- Probe writes zero attention-feeding events (regression vs `0018`).
- Expand: budgets/stop reasons exact; cycles terminate; scope/validity filters
  apply at every hop; default path writes nothing (journal diff empty).
- Report path: probe_report record with correct links; second identical
  report is deduped via idempotency key.
- ai-space reachability fixture reproduced via expand/traversal (parity with
  its private BFS).

## Non-goals

- No semantic ranking inside expansion (it follows recorded links only).
- No LLM summarization of expansion output (hosts may; package returns
  structured evidence).
- No unbounded traversal mode.

## Guidance for future agents

Read planned 003 first; implement the traversal primitive there (with the
reverse index + frontier-loop guidance above), then this item's surfaces on
top. Keep expand's zero-write default sacred — it is what makes the tool safe.


## Completion report (2026-07-20)

Shipped: probe.py (deliberate reach, two-tier ranking fusion, familiarity) + probe_expand/expand_by_concepts bounded expansion.
