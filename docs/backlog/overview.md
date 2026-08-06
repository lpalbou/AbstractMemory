# AbstractMemory Backlog Overview

## Summary

This backlog tracks planned AbstractMemory work that is not yet implemented.
Items are written as standalone implementation briefs for future coding agents.
They should be treated as planning memory, not as authority over the codebase:
inspect the current code first, then update the item if reality has changed.

## Current Status (reconciled 2026-07-20 — the shipped tree audited item by item)

- Planned: 0 — every planned item either shipped (moved to `completed/`)
  or was superseded (moved to `deprecated/`).
- Proposed: 13 GENUINELY open (4 in `memory_system_v1` + 9 in
  `extension_wave`)
- Completed: 33 (12 standalone/wave items + 20 `memory_system_v1`
  engine-wave items + `extension_wave/0049`)
- Deprecated: 3 (`001` superseded by the 0016 ruling; `003` by spreading
  activation; `006` by the shipped channel set)
- Recurrent: 0

GENUINELY OPEN (the honest desk, 2026-07-20):
- `proposed/memory_system_v1/0012` — LanceDB backend hardening (legacy
  store still in tree; low priority while SQLite is the home store).
- `proposed/memory_system_v1/0015` — capabilities surface + deterministic
  export/import (export_replay shipped; import + capabilities remain).
- `proposed/memory_system_v1/0016` — semantics vocabulary validation
  (direction RULED c184 2026-07-10: plain words admitted as declared
  terms, CURIEs as registry-side equivalences; promotion waits on
  registry coordination with the semantics seat).
- `proposed/memory_system_v1/0028` — lateral inhibition (deliberately
  deferred theory note, maintainer decision).
- `proposed/extension_wave/0040-0048` — the not-yet-accepted third-pass
  items (recurrence probe needs a maintainer detail round; loss anchors;
  explain_recall serving contract; mind-MASS health report — note
  cognition_health shipped the DRIVES half, the storage-mass/embedder
  half is what remains; origin-time axis for imports; N-party contract;
  transcript adoption verb; cue hygiene engine half; writer forensics).

Topic tracks (completed):
- `completed/subconscious_wave/` (0032-0035): dream lifecycle,
  world-model orientation cards, situate(), lessons — all shipped across
  the 2026-07-12..20 waves with receipts; first live firing verified on
  Ephemeral's first night (room 319/320).
- `completed/extension_wave/` (0037-0039 + 0049): familiarity,
  commitments, tend grammar, stable render order — shipped + live-proven.
- `completed/memory_system_v1/` (20 items): the engine wave itself —
  journal/attention/channels/reconstruction/records/facade/seam/
  spreading/sleep/probe plus the fork-adoption ledgers (0030/0031/0036)
  whose proposal sets landed across the extension + subconscious waves.

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

Implementation status refresh (2026-07-14, backlog↔code reconciliation):
the engine has since grown well past the 07-06 snapshot — suite 843
default tests green. Code now ALSO leads: `0019` (SQLite vector channel +
keyword/exact channels shipped in `sqlite_store.py`/`channels.py`; FTS5
half still open), `0022` (`probe.py` probe/expand — attention-inert,
effort presets, relevance-pure; plus `familiarity()` sharing the channel
pass), `0023` (`consolidation.py` + `maintenance.py` + `disposal.py` +
`dream_resolution.py`: the four-sub-phase night resolve→tend→world
models→dream with graceful cancellation), `0024` (`system.py` facade is
the shipped consumer surface). The whole `planned/subconscious_wave/`
track (0032-0035: dream lifecycle, `world_model.py`, `situate.py`,
lessons conventions) is implemented + adversary-reviewed per each item's
status note — items stay planned until the maintainer's ship review lands
(their own gating rule). Beyond any item: M1 embedder pins
(`embedding_pin.py`, `read_embedding_pin`, reembed repair), the frozen
replay stream v1 (`replay.py`), entity card compositor
(`entity_card.py`), two-anchor summon deltas (formed-by-T gate in
`folds.py`, `situate_prompt_block`), re-digestion (`redigestion.py`) and
doctoring (`doctoring.py` — dedup, journal cold-cut, verify; exercised
live on Castor 2026-07-14: 105→35 MB, verify green), spark/engram/
gradation/diary planes. Everything uncommitted per the standing
never-commit gate; promotion to completed/ follows the maintainer's ship
reviews, at which point each item gets its completion report and the
counts here move.

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

None — the 2026-07-20 reconciliation moved every planned item to
`completed/` (001-007 standalone, subconscious_wave 0032-0035,
extension_wave 0037-0039) or `deprecated/` (001/003/006, each with the
superseding pointer). New accepted work enters here as before.

## Proposed Items

| Item | Notes |
| --- | --- |
| [`0008_gateway_memory_install_and_config_boundary.md`](completed/0008_gateway_memory_install_and_config_boundary.md) | COMPLETED 2026-07-20 — the boundary exists both sides (gateway memory_store.py resolver + embeddings route; memory stayed dependency-light). |

### Memory System v1 track (`proposed/memory_system_v1/`)

Created 2026-07-05 from three adversarial investigation cycles (package/consumer
audit, Open Codex Memory prototype dissection, memory/semantics/runtime triangle
investigation). See the [track README](proposed/memory_system_v1/README.md) for
the design rationale, owner decisions (hard AbstractSemantics dependency,
append-only closure records, no erasure/neurotransmitter attention, no graph
database, L1 two-layer package), and reading order.

| Item | Track | Notes |
| --- | --- | --- |
| [`0009_assertion_identity_and_batch_read_contract.md`](completed/memory_system_v1/0009_assertion_identity_and_batch_read_contract.md) | A | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0010_append_only_closure_records_for_retract_and_supersede.md`](completed/memory_system_v1/0010_append_only_closure_records_for_retract_and_supersede.md) | A | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0011_cross_backend_parity_conformance_suite.md`](completed/memory_system_v1/0011_cross_backend_parity_conformance_suite.md) | A | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0012_lancedb_backend_hardening_and_explicit_schema.md`](proposed/memory_system_v1/0012_lancedb_backend_hardening_and_explicit_schema.md) | A | Explicit schema, create-race, honest failures, version pin. |
| [`0013_store_concurrency_and_thread_safety_contract.md`](completed/memory_system_v1/0013_store_concurrency_and_thread_safety_contract.md) | A | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0014_embedding_space_integrity_manifest.md`](completed/memory_system_v1/0014_embedding_space_integrity_manifest.md) | A | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0015_capabilities_extensions_and_deterministic_export_import.md`](proposed/memory_system_v1/0015_capabilities_extensions_and_deterministic_export_import.md) | A | Extends planned 002; JSONL export/import migration substrate. |
| [`0016_semantics_vocabulary_validation_and_aliasing_module.md`](proposed/memory_system_v1/0016_semantics_vocabulary_validation_and_aliasing_module.md) | A | Hard AbstractSemantics dep; shared validation + aliasing. |
| [`0017_memory_journal_and_scope_bindings_layer.md`](completed/memory_system_v1/0017_memory_journal_and_scope_bindings_layer.md) | B | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0018_neurotransmitter_attention_strengthen_weaken_decay.md`](completed/memory_system_v1/0018_neurotransmitter_attention_strengthen_weaken_decay.md) | B | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0019_hybrid_retrieval_channels_fts_vector_exact.md`](completed/memory_system_v1/0019_hybrid_retrieval_channels_fts_vector_exact.md) | C | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0020_reconstruction_shelf_and_selection_traces.md`](completed/memory_system_v1/0020_reconstruction_shelf_and_selection_traces.md) | C | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0021_memory_records_and_remember_api.md`](completed/memory_system_v1/0021_memory_records_and_remember_api.md) | D | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0022_probe_and_bounded_source_expansion.md`](completed/memory_system_v1/0022_probe_and_bounded_source_expansion.md) | D | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0023_maintenance_sleep_consolidate_dream.md`](completed/memory_system_v1/0023_maintenance_sleep_consolidate_dream.md) | D | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0024_memory_system_facade_and_consumer_migration.md`](completed/memory_system_v1/0024_memory_system_facade_and_consumer_migration.md) | D | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0025_graph_backend_decision_record_memgraph_rejected.md`](completed/memory_system_v1/0025_graph_backend_decision_record_memgraph_rejected.md) | — | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0026_spreading_activation_and_working_set.md`](completed/memory_system_v1/0026_spreading_activation_and_working_set.md) | C | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0027_runtime_seam_contract_v1.md`](completed/memory_system_v1/0027_runtime_seam_contract_v1.md) | C | COMPLETED 2026-07-20 (engine wave; see completion report). |
| [`0028_lateral_inhibition_theory.md`](proposed/memory_system_v1/0028_lateral_inhibition_theory.md) | — | Theory/discussion note (drafted by the runtime agent at the maintainer's request; memory-track owned). Deferred out of v1 by decision. |
| [`0029_sleep_reactivity_dreams_as_reaction.md`](completed/memory_system_v1/0029_sleep_reactivity_dreams_as_reaction.md) | — | COMPLETED 2026-07-20 (the wave-5 dream-signal chain; first live firing verified). |
| [`0030_fork_comparison_adoption_wave.md`](completed/memory_system_v1/0030_fork_comparison_adoption_wave.md) | — | COMPLETED 2026-07-20 (fork parity ledger executed). |
| [`0031_second_fork_pass_and_lifecycle_closure.md`](completed/memory_system_v1/0031_second_fork_pass_and_lifecycle_closure.md) | — | COMPLETED 2026-07-20 (lifecycle closure shipped across the waves). |
| [`0036_third_pass_extension_wave.md`](completed/memory_system_v1/0036_third_pass_extension_wave.md) | — | COMPLETED 2026-07-20 (engine wave; see completion report). |

### Extension wave track (`proposed/extension_wave/`, 0040-0048)

The not-yet-accepted third-pass items; see the
[track README](proposed/extension_wave/README.md). 0040 (recurrence)
requires a maintainer detail round before promotion; 0044+0046 form the
lineage bundle with the chapters election recorded in 0036 — 0044
(origin-time axis) is the first dependency of the Mnemosyne-lineage
import mission and the natural next promotion candidate. 0049 (stable
shelf order for prefix reuse) COMPLETED 2026-07-17 — moved to
`completed/extension_wave/`.

Interactions with planned items: `0011`/`0015` extend planned `002`;
`0020` supersedes the contract-first approach of planned `004`; `0021`
reshapes planned `001` into code; `0022` consumes planned `003` (and adds a
reverse-index + frontier-loop guidance note); planned `005` becomes
implementable once `0009` lands; planned `006`'s anchor idea is absorbed by
`0019`/`0020` hybrid retrieval + DF-banded anchors. Reconcile each pair at
promotion time.

## Completed Work Ledger

| Completed | Item | Evidence |
| --- | --- | --- |
| 2026-07-20 | 31-item reconciliation (planned 002/004/005/007, subconscious_wave 0032-0035, extension_wave 0037-0039, memory_system_v1 0009-0011/0013-0014/0017-0027/0029-0031/0036) | Every item audited against the shipped tree and moved to `completed/` with a per-item completion report naming modules + receipts; 001/003/006 deprecated with superseding pointers. The shipping receipts live on the hub (extension/subconscious/W2/W-GROUP/wave-5 SHIP posts); suite 1037 green at reconciliation. |
| 2026-07-17 | [`completed/extension_wave/0049_stable_shelf_order_for_prefix_reuse.md`](completed/extension_wave/0049_stable_shelf_order_for_prefix_reuse.md) | Engine `stable_render_order()` (6 pins, suite 875 green, c2846) + runtime election wired in `_memories_block` (c2895) + core's measured LCP delta on Ephemeral's real store: 75.1% vs 52.6% region reuse, 2.8x on rank-churn pairs (c2911). Decision: `decision:0049-stable-render-order`. |

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
