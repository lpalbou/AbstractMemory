# Memory System v1 backlog track

## Status

Proposed

## Purpose

This track turns AbstractMemory into what it was always intended to be: the
framework's functioning memory system. It keeps the existing low-level triple
substrate (stores, structured queries) as layer 1 and adds a high-level
`MemorySystem` layer (remember / reconstruct / focus / strengthen / weaken /
probe / expand / sleep) as layer 2 — in ONE package, with any LLM-dependent
step injected via protocols so AbstractMemory never imports AbstractCore or
AbstractRuntime.

The design was derived from three adversarial investigation cycles (2026-07-05):

1. a package/consumer audit that found the memory semantics duplicated and
   diverging across AbstractRuntime (946-line integration), AbstractGateway,
   SmartNote (silent predicate drops), and ai-space (private traversal and
   op-folding);
2. a full dissection of the private Open Codex Memory prototype (Rust/SQLite),
   whose battle-tested mechanics (append-only bindings, selected-use-only
   attention, formation ledgers, report-first maintenance) and documented
   failures (attention noise, heuristic pruning removed after one day,
   CHECK-constraint migration scars) directly shape these items;
3. an abstractmemory/abstractsemantics/abstractruntime triangle investigation
   that resolved layering: everything fits in AbstractMemory with three
   injected protocols (`TextEmbedder` exists; `SelectorProtocol`,
   `ReflectorProtocol` are new).

Owner decisions encoded in this track:

- hard dependency on AbstractSemantics (registry stays the vocabulary
  authority; registry additions are tracked as an explicit prerequisite);
- append-only closure records for retract/supersede;
- NO physical erasure: forgetting = decay + closure + silencing
  ("neurotransmitters" that strengthen or weaken access);
- no graph database (Memgraph rejected; see `0025`); bounded traversal over
  existing backends;
- prompt assembly and recall policy stay in higher packages.

## Items

Track A — substrate foundations (fix the contract before building on it):

- `0009_assertion_identity_and_batch_read_contract.md`: expose assertion ids at
  read; batch query; `add_if_absent`.
- `0010_append_only_closure_records_for_retract_and_supersede.md`: belief
  lifecycle without mutation or erasure.
- `0011_cross_backend_parity_conformance_suite.md`: one parametrized suite over
  all three backends; fixes the verified divergences.
- `0012_lancedb_backend_hardening_and_explicit_schema.md`: explicit schema,
  create-race, open-failure reporting, version pin.
- `0013_store_concurrency_and_thread_safety_contract.md`: WAL/locks; the
  gateway thread-pool reality.
- `0014_embedding_space_integrity_manifest.md`: embedding model/dim manifest;
  shared canonical text.
- `0015_capabilities_extensions_and_deterministic_export_import.md`: extends
  planned 002; JSONL export/import as the migration substrate.
- `0016_semantics_vocabulary_validation_and_aliasing_module.md`: registry-backed
  validation + aliasing in the package (fixes SmartNote drops).

Track B — journal and neurotransmitters:

- `0017_memory_journal_and_scope_bindings_layer.md`: append-only journal
  (events/bindings/traces/snapshots) + latest-wins scope bindings.
- `0018_neurotransmitter_attention_strengthen_weaken_decay.md`: selected-use
  attention, decay, refocus, strengthen/weaken; no erasure.

Track C — retrieval:

- `0019_hybrid_retrieval_channels_fts_vector_exact.md`: exact + FTS5 + vector
  channels with reserved slots and fusion.
- `0020_reconstruction_shelf_and_selection_traces.md`: `reconstruct()` —
  anchors, kind priority, budgets, traces, optional selector.

Track D — high-level memory system:

- `0021_memory_records_and_remember_api.md`: typed memory records and
  `remember()`.
- `0022_probe_and_bounded_source_expansion.md`: `probe()` / `expand()`.
- `0023_maintenance_sleep_consolidate_dream.md`: `sleep()` report /
  consolidate / dream.
- `0024_memory_system_facade_and_consumer_migration.md`: the `MemorySystem`
  facade and the consumer migration map.

Decision record:

- `0025_graph_backend_decision_record_memgraph_rejected.md`: Memgraph verdict
  and promotion criteria for any future embedded graph backend.

Track C additions (2026-07-05, from the runtime⇄memory a2a coordination):

- `0026_spreading_activation_and_working_set.md`: stimulus-driven spreading
  activation (ACT-R-shaped, over trail-strengthened edges) and the emergent
  `working_set` view of `reconstruct()`. Co-designed with the runtime agent
  via `a2a/threads/0001-runtime-memory-orchestration/`; several constants
  await maintainer answers recorded there.
- `0027_runtime_seam_contract_v1.md`: the FROZEN runtime⇄memory seam
  (dataclasses, protocol, stability contracts) confirmed in a2a 0001/004.
  The runtime is building its effects/stub/harness against it; implement
  from the a2a message, raise shape changes on the channel first.
- `0028_lateral_inhibition_theory.md`: theory/discussion note on lateral
  inhibition (fan effect, redundancy decorrelation) — deliberately deferred
  out of v1; drafted by the runtime agent, owned by this track.

## Implementation status (2026-07-06)

Engine v1 is IMPLEMENTED (see `src/abstractmemory/` and the overview's
implementation-status note): identity exposure, closure records, journal +
bindings, attention, channels + spreading + reconstruction (shelf +
working_set views, Arm-B ablation switch), formation (`remember_many`),
idempotent replay semantics, and the `MemorySystem` facade — 240 tests green.
Items 0009/0010/0017/0018/0020/0021/0026/0027 are partially or largely
realized in code; the remaining unbuilt surface is: FTS5 keyword channel +
manifest (0014/0019), parity conformance vs LanceDB semantics (0011/0012),
remaining concurrency hardening (0013 — store WAL/locks landed 2026-07-06),
vocabulary module (0016), capabilities/export (0015), probe/expand (0022),
maintenance (0023), consumer migration (0024). Reconcile each item against
code before implementing further.

2026-07-06 union-model update (maintainer-decided; supersedes parts of
0018/0020/0026/0027 text): working set = STM ∪ stimulus with admission
labels, presence ≠ use commit semantics, reserved slots + qmult deleted,
kind rank demoted to tie-break, canonical text v2, baseline-relative vector
floor. Authoritative delta: a2a 0001/012 (rewritten with maintainer
authorization). Known gap to schedule: seed-to-seed spreading — two
channel-matched seeds never receive spread from each other (both already
expanded when their connecting edge fires), so `activation.spread` reads 0 on
seed pairs although the edge is walked; fix belongs in 0026's frontier
semantics.

## Reading order

0009 → 0010 → 0011 → 0012 → 0013 → 0014 → 0015 → 0016 (Track A, roughly in
order; 0011 lands with fixes from 0009/0010 available), then 0017 → 0018,
then 0019 → 0020, then 0021 → 0022 → 0023 → 0024. 0025 can be read anytime.

## Governing ADRs

- AbstractFramework: `docs/adr/0005-memory-architecture.md`,
  `0007-active-context-and-memory-provenance.md`,
  `0009-connected-memory-recall-and-provenance.md`,
  `0025-kg-entity-normalization-and-dedup.md`,
  `0026-truncation-policy-and-contract.md`, `memory-recall-levels.md`.
- Several items in this track establish durable policy (closure semantics,
  attention contracts, no-erasure) and are flagged `Needs new ADR` — create
  the ADRs at promotion time.

## Scope

Design-complete proposed items for the memory system v1 wave, standalone
enough for future implementing agents.

## Non-goals

- No LLM calls inside AbstractMemory (injection only).
- No prompt assembly or recall policy in this package.
- No graph database dependency.
- No physical erasure API.
- No rewrite of planned items 001–007; where this track supersedes an
  approach (001's doc-only form, 002's FTS sub-bullet), the item says so and
  reconciliation happens at promotion time.

## Notes for future agents

Inspect current code before implementing anything here; several items fix
defects that may have been fixed already. The private Open Codex Memory
prototype is cited as design evidence ("fork lesson") without paths — treat
those lessons as constraints validated by production failure, not as
suggestions.
