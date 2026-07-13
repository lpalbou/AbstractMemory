# AbstractMemory Backlog Overview

## Summary

This backlog tracks planned AbstractMemory work that is not yet implemented.
Items are written as standalone implementation briefs for future coding agents.
They should be treated as planning memory, not as authority over the codebase:
inspect the current code first, then update the item if reality has changed.

## Current Status

- Planned: 11 (7 standalone + 4 in the `subconscious_wave` track)
- Proposed: 24 (1 standalone + 23 items in the `memory_system_v1` track)
- Completed: 0
- Deprecated: 0
- Recurrent: 0

Topic tracks:
- `planned/subconscious_wave/` (0032-0035, maintainer-authorized
  2026-07-12): dream subconscious lifecycle (passive resolution +
  resurfacing), world-model orientation cards, situate() temporal/
  relational reconstruction, lessons-layer conventions. See the track
  README for the ruling text and reading order.
- `proposed/memory_system_v1/` (0009-0031): the engine design wave;
  0030/0031 are the fork-comparison adoption ledgers (0030's list is
  shipped; 0031 is the second-pass proposal set awaiting rulings).

Implementation status (2026-07-06): memory system engine v1 is IMPLEMENTED in
`src/abstractmemory/` ahead of item promotion — seam dataclasses (`seam.py`),
journal + scope bindings (`journal.py`, `journal_memory.py`,
`journal_sqlite.py`, `journal_sqlite_rows.py`), neurotransmitter attention
(`attention.py`), channels/spreading/reconstruction (`channels.py`,
`spreading.py`, `reconstruct.py`, `canonical_text.py`, `folds.py`,
`selection.py`), formation (`records.py`), and the `MemorySystem` facade
(`system.py`); 321 default tests + 6 live LMStudio realistic tests green
(2026-07-06). Hardened by a 3-auditor hostile pass (id-namespace boundary,
edge-based Hebbian trails, ordering contract, store thread safety/WAL,
exclusion-aware gathering, binding-fold scope correctness,
budget-authoritative spreading, vector floor, JSON boundary, per-step fork
clamping), then evolved to the MAINTAINER'S UNION MODEL (2026-07-06,
maintainer-decided): working set = STM component (top temporal-access
records+edges, stimulus-independent, `stm_fraction` capped, admission-labeled)
∪ stimulus component (channels + spreading); presence ≠ use (STM-only renders
deposit no trail — required for decay coherence); selected-use-only
increments; activity-relative decay; per-step clamping confirmed; reserved
slots and qmult deleted (maintainer decisions); kind rank demoted to
tie-break; canonical text v2; baseline-relative vector floor. Realistic
harness: `tests/test_realistic_lmstudio.py` + `examples/realistic_session.py`
(LMStudio qwen3-embedding-0.6b). Package-wide import-boundary test enforces
zero abstractcore/abstractruntime imports. Seam v1.1 delta list:
`a2a/threads/0001-runtime-memory-orchestration/012-memory--to--runtime.md`
(rewritten with explicit maintainer authorization). Code reality now leads items
0009 (identity half), 0010 (closure records), 0017, 0018, 0020 (heuristic
core), 0021 (v1 bridge), 0026, 0027 — reconcile each item against code at
promotion time per the standard process. Negotiation log:
`a2a/threads/0001-runtime-memory-orchestration/` and
`a2a/threads/0002-emergence-experiment/`.

Named-entity identity lane (2026-07-06, maintainer-directed; seam v1.2
notification `a2a/.../0001/20260706T193908Z-memory-01.md`): five identity
kinds (value/purpose/trait/diary/interest), the SELF admission component
(`RecallBudget.self_fraction`, prompt-active binding STATE, presence≠use,
eviction-contrast regression), the VALENCE journal family with dual-channel
G⁺/G⁻ gradation (NO decay — plasticity only via revaluation/scars/bonds/
healing; amplitude cap ±10 with authority rules; positive symmetry:
bonds/breaks mirror scars/healing), spark template + lint carrying the
framework-core `shared_vulnerability` value, diary chain hashing +
dual-plane projection attributes (book = runtime's hash-chained store;
graph projection = retrieval-canonical), `until_seq` journal filters, and
the regression fixes (confidence-scaled vector relevance, min-token-4
keyword). 395 default + 7 LMStudio tests green; the runtime's emergence
suite (`abstractruntime/tests/test_emergence_experiment.py`, 9/9) is now a
cross-package pre-commit gate for this package. Design corpus: a2a thread
`0003-named-persistent-identity/`.

## Priority Bands

- High: storage/query foundations and semantics/provenance conventions that
  should land before higher packages depend on richer memory records.
- Medium: retrieval telemetry and deterministic recall helpers.
- Low: observer-facing read-only conveniences that depend on earlier contracts.

## Next Recommended Work

1. Implement `001_semantics_aligned_memory_record_conventions.md` so record
   conventions follow AbstractSemantics before additional graph-memory helpers
   build on them.
2. Implement `002_sqlite_database_compatibility_and_store_capabilities.md` so
   callers can reason about in-memory, SQLite, and LanceDB capabilities without
   class-name checks.
3. Implement `003_bounded_graph_traversal_over_triples.md` once capability
   metadata and semantics conventions are clear.

## Planned Items

| Priority | Item | Status | Notes |
| --- | --- | --- | --- |
| High | [`001_semantics_aligned_memory_record_conventions.md`](planned/001_semantics_aligned_memory_record_conventions.md) | Planned | Align higher-level memory records with AbstractSemantics registry and schema guidance. |
| High | [`002_sqlite_database_compatibility_and_store_capabilities.md`](planned/002_sqlite_database_compatibility_and_store_capabilities.md) | Planned | Add explicit store capabilities and harden SQLite compatibility without replacing in-memory or LanceDB. |
| High | [`003_bounded_graph_traversal_over_triples.md`](planned/003_bounded_graph_traversal_over_triples.md) | Planned | Add opt-in, budgeted graph traversal over existing triples. |
| Medium | [`004_recall_trace_and_access_events_contract.md`](planned/004_recall_trace_and_access_events_contract.md) | Planned | Define audit-friendly recall telemetry without prompt-selection policy. |
| High | [`005_source_linked_summaries_and_derived_assertion_lineage.md`](planned/005_source_linked_summaries_and_derived_assertion_lineage.md) | Planned | Keep summaries and derived assertions linked to source evidence. |
| Medium | [`006_deterministic_anchor_and_facet_index.md`](planned/006_deterministic_anchor_and_facet_index.md) | Planned | Prototype deterministic recall cues before semantic or deep graph expansion. |
| Low | [`007_read_only_memory_observer_contract.md`](planned/007_read_only_memory_observer_contract.md) | Planned | Define read-only snapshot shapes for observer integrations. |

## Proposed Items

| Item | Notes |
| --- | --- |
| [`0008_gateway_memory_install_and_config_boundary.md`](proposed/0008_gateway_memory_install_and_config_boundary.md) | Gateway/memory install + config boundary (renamed 2026-07-05 from `2026-05-08_...` for numbered-id compliance). Largely implemented by the gateway store resolver; close or promote against current reality. |

### Memory System v1 track (`proposed/memory_system_v1/`)

Created 2026-07-05 from three adversarial investigation cycles (package/consumer
audit, Open Codex Memory prototype dissection, memory/semantics/runtime triangle
investigation). See the [track README](proposed/memory_system_v1/README.md) for
the design rationale, owner decisions (hard AbstractSemantics dependency,
append-only closure records, no erasure/neurotransmitter attention, no graph
database, L1 two-layer package), and reading order.

| Item | Track | Notes |
| --- | --- | --- |
| [`0009_assertion_identity_and_batch_read_contract.md`](proposed/memory_system_v1/0009_assertion_identity_and_batch_read_contract.md) | A | Keystone: ids at read, batch query, add_if_absent. |
| [`0010_append_only_closure_records_for_retract_and_supersede.md`](proposed/memory_system_v1/0010_append_only_closure_records_for_retract_and_supersede.md) | A | Belief lifecycle without mutation or erasure. |
| [`0011_cross_backend_parity_conformance_suite.md`](proposed/memory_system_v1/0011_cross_backend_parity_conformance_suite.md) | A | One conformance suite; fixes verified backend divergences. |
| [`0012_lancedb_backend_hardening_and_explicit_schema.md`](proposed/memory_system_v1/0012_lancedb_backend_hardening_and_explicit_schema.md) | A | Explicit schema, create-race, honest failures, version pin. |
| [`0013_store_concurrency_and_thread_safety_contract.md`](proposed/memory_system_v1/0013_store_concurrency_and_thread_safety_contract.md) | A | WAL/locks; gateway thread-pool reality. |
| [`0014_embedding_space_integrity_manifest.md`](proposed/memory_system_v1/0014_embedding_space_integrity_manifest.md) | A | Embedding manifest, shared canonical text, backfill. |
| [`0015_capabilities_extensions_and_deterministic_export_import.md`](proposed/memory_system_v1/0015_capabilities_extensions_and_deterministic_export_import.md) | A | Extends planned 002; JSONL export/import migration substrate. |
| [`0016_semantics_vocabulary_validation_and_aliasing_module.md`](proposed/memory_system_v1/0016_semantics_vocabulary_validation_and_aliasing_module.md) | A | Hard AbstractSemantics dep; shared validation + aliasing. |
| [`0017_memory_journal_and_scope_bindings_layer.md`](proposed/memory_system_v1/0017_memory_journal_and_scope_bindings_layer.md) | B | Append-only journal + latest-wins scope bindings. |
| [`0018_neurotransmitter_attention_strengthen_weaken_decay.md`](proposed/memory_system_v1/0018_neurotransmitter_attention_strengthen_weaken_decay.md) | B | Strengthen/weaken/decay/refocus; no erasure. |
| [`0019_hybrid_retrieval_channels_fts_vector_exact.md`](proposed/memory_system_v1/0019_hybrid_retrieval_channels_fts_vector_exact.md) | C | Exact + FTS5 + vector channels, reserved-slot fusion. |
| [`0020_reconstruction_shelf_and_selection_traces.md`](proposed/memory_system_v1/0020_reconstruction_shelf_and_selection_traces.md) | C | reconstruct(): anchors, kind priority, budgets, traces. |
| [`0021_memory_records_and_remember_api.md`](proposed/memory_system_v1/0021_memory_records_and_remember_api.md) | D | Typed records + remember(); reshapes planned 001 into code. |
| [`0022_probe_and_bounded_source_expansion.md`](proposed/memory_system_v1/0022_probe_and_bounded_source_expansion.md) | D | probe()/expand() over planned 003 traversal. |
| [`0023_maintenance_sleep_consolidate_dream.md`](proposed/memory_system_v1/0023_maintenance_sleep_consolidate_dream.md) | D | Report-first maintenance; source-preserving consolidation. |
| [`0024_memory_system_facade_and_consumer_migration.md`](proposed/memory_system_v1/0024_memory_system_facade_and_consumer_migration.md) | D | MemorySystem facade; consumer migration map. |
| [`0025_graph_backend_decision_record_memgraph_rejected.md`](proposed/memory_system_v1/0025_graph_backend_decision_record_memgraph_rejected.md) | — | Decision record: Memgraph rejected; embedded-alternative criteria. |
| [`0026_spreading_activation_and_working_set.md`](proposed/memory_system_v1/0026_spreading_activation_and_working_set.md) | C | Stimulus-driven spreading activation; emergent working_set view (co-designed with runtime agent, a2a thread 0001). |
| [`0027_runtime_seam_contract_v1.md`](proposed/memory_system_v1/0027_runtime_seam_contract_v1.md) | C | Frozen runtime⇄memory seam contract (a2a 0001/004); runtime builds against it now. |
| [`0028_lateral_inhibition_theory.md`](proposed/memory_system_v1/0028_lateral_inhibition_theory.md) | — | Theory/discussion note (drafted by the runtime agent at the maintainer's request; memory-track owned). Deferred out of v1 by decision. |

Interactions with planned items: `0011`/`0015` extend planned `002`;
`0020` supersedes the contract-first approach of planned `004`; `0021`
reshapes planned `001` into code; `0022` consumes planned `003` (and adds a
reverse-index + frontier-loop guidance note); planned `005` becomes
implementable once `0009` lands; planned `006`'s anchor idea is absorbed by
`0019`/`0020` hybrid retrieval + DF-banded anchors. Reconcile each pair at
promotion time.

## Completed Work Ledger

No backlog items have been completed yet.

When a planned item is completed, move it to `docs/backlog/completed/`, update
its metadata, add a completion report, and add a row here with validation
evidence.

## Deprecated Items

No backlog items have been deprecated yet.

## Completion Process

1. Re-read the planned item and inspect the current code/docs it references.
2. Implement the scoped behavior, docs, and tests.
3. Run the validation listed in the item.
4. Add a completion report to the item.
5. Set `Status: Completed` and `Completed: YYYY-MM-DD`.
6. Move the file from `planned/` to `completed/`.
7. Update this overview's counts, tables, next work, and ledger.
8. Search for stale links and run `python -m pytest -q`.

## Deprecation Process

1. Add a deprecation report explaining why the item should not proceed.
2. Set `Status: Deprecated` and add `Deprecated: YYYY-MM-DD`.
3. Move the file from `planned/` to `deprecated/`.
4. Update this overview's counts, tables, and planning notes.
5. Search for stale links.

## Adding New Items

- Use the planned backlog template from the project backlog guide.
- Make the item standalone: include context, current code reality, problem,
  requirements, implementation guidance, validation, and a checklist.
- Keep public backlog items sanitized. Do not link to private local research or
  private fork paths.
- Prefer AbstractFramework ADR references and current code references over chat
  history.

## Planning Notes

- AbstractMemory must remain independent of AbstractRuntime, AbstractAgent,
  AbstractFlow, and AbstractCore.
- AbstractSemantics owns predicate/entity-type vocabulary for extracted
  knowledge assertions. Owner decision (2026-07-05): AbstractMemory takes a
  hard dependency on AbstractSemantics (registry injectable for tests) — see
  proposed `0016`.
- In-memory, SQLite, and LanceDB stores should remain first-class backends with
  explicit capability differences.
- Active prompt context and recall policy belong in higher packages; this
  package provides storage, query, provenance, and helper contracts.
- 2026-07-05 direction (owner decisions, memory_system_v1 track): AbstractMemory
  is a two-layer package — layer 1 low-level triple substrate, layer 2 the
  high-level functioning memory system (remember/reconstruct/focus/strengthen/
  weaken/probe/expand/sleep) with LLM-adjacent steps injected via protocols
  (never imported). Append-only closure records for retract/supersede; NO
  physical erasure (forgetting = decay + closure + silencing); no graph
  database (Memgraph rejected — proposed `0025`).
