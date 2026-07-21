# Completed: MemorySystem facade + consumer migration map

## Metadata

- Created: 2026-07-05
- Status: Completed (2026-07-20)
- Completed: 2026-07-20
- Priority: High (the integrating item)
- Components: system facade module, config, docs; cross-repo migration items (runtime/gateway/smartnote/ai-space)

## ADR status

- Governing ADRs: AbstractFramework `0001-layered-architecture.md`,
  `0005-memory-architecture.md`
- ADR impact: Needs new ADR (the two-layer package architecture and the
  injected-protocol boundary are durable policy).

## Context

Owner decision (layering L1): ONE package, two layers. Layer 1 = the existing
low-level substrate (stores, structured queries — reusable by AbstractRuntime
or anything else). Layer 2 = the high-level functioning memory system with
methods to actually remember, reconstruct, focus. LLM-adjacent steps are
injected via exactly three protocols so AbstractMemory never imports
AbstractCore/AbstractRuntime: `TextEmbedder` (exists), `SelectorProtocol`
(`0020`), `ReflectorProtocol` (`0023`).

The triangle investigation (2026-07-05) confirmed everything fits under this
boundary and categorized what stays OUT (runtime-owned): scope→owner
resolution (run/session/global ladder), turn boundaries and the
completed-turn formation recipe, prompt packing/packetization, effect/tool
exposure, approval and recall-level policy.

## Current code reality

- Facade target shape (from the full API spec, 2026-07-05):

  ```python
  MemorySystem(
      store: TripleStore, journal: MemoryJournal,
      embedder: TextEmbedder | None = None,
      selector: SelectorProtocol | None = None,
      reflector: ReflectorProtocol | None = None,
      semantics: Vocabulary | None = None,   # defaults to registry-backed
      config: MemoryConfig = MemoryConfig(), clock=utc_now_iso_seconds,
  )
  ```

  Methods delegate to the wave's modules: `remember/remember_many` (`0021`),
  `reconstruct/commit_selection` (`0020`), `focus/refocus/reinforce/attenuate/
  activation/activation_report` (`0018`), `probe/expand` (`0022`),
  `sleep` (`0023`), `bind/close_assertions` (`0017`/`0010`), plus journal
  read passthroughs (`traces/snapshots/events`).
- `MemoryConfig` centralizes every tunable (attention constants, budgets,
  kind-priority order, DF band, thresholds, payload cap, broad_scopes) —
  strategy/config over hardcoding.
- Consumer reality being replaced (verified 2026-07-05): the runtime's
  946-line integration (aliasing→`0016`, dedupe→`0009`, recall
  plumbing→`0020`); gateway's class-name capability dicts→`0015`; SmartNote's
  diverged validation→`0016` and write-only KG→`0021`+`0020`; ai-space's
  op-folding→`0010` and private BFS→`0022`/planned 003.

## Problem or opportunity

The facade is where the wave becomes usable by one import; the migration map
is where the duplication pathology actually dies (absorbing mechanics without
migrating consumers would leave the divergent copies alive).

## Proposed direction

1. Implement the facade (thin: construction wiring + delegation + config;
   modules do the work; files stay <600 lines).
2. Startup honesty: constructing without a journal-capable backend fails with
   an actionable error; missing embedder/selector/reflector degrade the
   documented surfaces with explicit warnings (channel degradation cues,
   dream-mode error) — `#FALLBACK` conventions throughout.
3. Consumer migration map (file items in each consumer's backlog at promotion
   time; this item tracks the map):
   - abstractruntime: `MEMORY_REMEMBER`/`MEMORY_RECONSTRUCT`/`MEMORY_FOCUS`/
     `MEMORY_MAINTAIN` effects wrapping the facade; existing `memory_kg_*`
     effects re-implemented over layer 1 + `0016` (aliasing deleted from the
     runtime); the completed-turn formation recipe (Question/Answer/Episode
     ledger with idempotency keys) as a runtime module over `remember_many`;
     recall-levels mapped onto `RecallBudget`; agent tools for
     `probe`/`expand`/`focus` (reason mandatory in tool schemas).
   - abstractgateway: store/journal construction via its config resolver;
     capability dicts replaced by `0015` descriptors; KG routes extended with
     reconstruct/probe/activation_report endpoints (observer data source);
     scheduled `sleep(report)` as host policy.
   - smartnote: private validation replaced by `0016`; cards/fragments as
     typed records (`0021`); retrieval via `reconstruct` — its KG stops being
     write-only.
   - ai-space: op-folding replaced by closure records (`0010`); reachability
     via traversal/`expand`.
4. Version/release discipline: the wave lands behind minor versions with the
   parity suite green; consumers migrate one at a time; no flag-day.

## Why it might matter

This item is the difference between "a better library nobody switched to" and
the framework actually having ONE memory system. The consumer migrations are
where SmartNote's silent data loss, the runtime's N+1s, and ai-space's private
semantics actually get deleted.

## Decision boundaries

- The facade never imports abstractcore/abstractruntime (enforced by an
  import-linter test).
- Layer 1 remains fully usable without the facade (no forced adoption).
- Prompt text assembly never enters the package.

## Promotion criteria

Promote when Tracks A–C are implemented (this is the capstone). The
consumer-migration sub-items are filed in consumer backlogs at that moment,
not before (avoid cross-repo backlog drift).

## Validation ideas

- Import-boundary test: `abstractmemory` imports neither abstractcore nor
  abstractruntime anywhere (CI-enforced).
- Facade construction matrix: with/without embedder/selector/reflector —
  documented degradations, no silent behavior changes.
- End-to-end scenario test (package-level): remember records → reconstruct →
  commit_selection → activation shifts → probe/expand → sleep report — one
  integration test tells the whole story on SQLite and LanceDB.
- Runtime pilot: one gateway workflow using `MEMORY_RECONSTRUCT` +
  `commit_selection` demonstrates recall improving across turns (the
  user-visible proof point).

## Non-goals

- No orchestration/scheduling inside the package.
- No consumer migration before Tracks A–C land (map only).
- No backwards-compat shims for the runtime's private helpers (they migrate
  or stay; the package does not mirror them).

## Guidance for future agents

Keep the facade boring. If a method grows logic, it belongs in a module. When
filing the consumer items, copy the relevant verified file:line findings from
this track's items so consumer agents do not re-audit from scratch.


## Completion report (2026-07-20)

Shipped: system.py MemorySystem facade (reconstruct/remember_many/commit_selection/probe/appraise/situate/...) — the one consumer surface; runtime + gateway consume it exclusively.
