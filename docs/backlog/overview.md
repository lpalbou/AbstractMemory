# AbstractMemory Backlog Overview

## Summary

This backlog tracks planned AbstractMemory work that is not yet implemented.
Items are written as standalone implementation briefs for future coding agents.
They should be treated as planning memory, not as authority over the codebase:
inspect the current code first, then update the item if reality has changed.

## Current Status (counts recounted on disk 2026-11-10 after the 0.5.1 tag, unchanged since the 0.5.0 closure; first reconciled 2026-07-20 — the shipped tree audited item by item)

- Planned: 10 — `planned/0069` (runtime recall stamps use `community_keys_of`, added 2026-11-10; its memory half
  shipped in 0.5.1, the runtime switch remains) and
  `planned/knowledge_graph_convergence/` 0050-0058 (0050-0055 added
  2026-10-27, ADR 0002; 0056-0058, ADR 0003; 0056 in progress, first slice
  on `feat/memory-graph-provenance`; 0053 has its communities slice shipped in
  0.5.0). The track folder also holds three one-line pointer files (0059-0061,
  see the planning note), not counted. Before 2026-10-27 every planned item had
  shipped (moved to `completed/`) or was superseded (moved to `deprecated/`).
- Proposed: 22 GENUINELY open: 4 in `memory_system_v1`, 9 in `extension_wave`,
  2 in `ripple_wave` (0001, 0063), 6 standalone 0.5.0 follow-ups (0062,
  0064-0068) and 0070 (topic-version churn, memory half of root 1201, 2026-11-10). The 2026-07-20 count (13) left out `ripple_wave/0001`.
- Completed: 36 (12 standalone/wave items + 20 `memory_system_v1`
  engine-wave items + `extension_wave/0049` + `knowledge_graph_convergence`
  0059-0061, closed 2026-11-10 with abstractmemory 0.5.0)
- Deprecated: 3 (`001` superseded by the 0016 ruling; `003` by spreading
  activation; `006` by the shipped channel set)
- Recurrent: 0

GENUINELY OPEN (the honest desk, 2026-07-20; convergence track added 2026-10-27; 0.5.0 follow-ups added 2026-11-10):
- 0.5.0 follow-ups (filed 2026-11-10 from the release's documented residuals and the Fable pre-tag review; 0.5.1
  shipped without the four aimed at it, so their target is now the next memory patch):
  `proposed/0062` write barrier residual windows (`_write_pin`, `mark_journal_applied`, LanceDB; SQLite half next
  patch), `proposed/0066` placement index misses a dissolve-only version (next patch; 0.5.1's `community_keys_of`
  inherits it), `proposed/0067` `communities()` is not one snapshot (next patch), `proposed/0068` api.md queue-less
  list (next docs pass), `proposed/0064` `merged_into` in the community facts, `proposed/0065` `embed_missing`'s
  `vector_generation` bump (skipped, reason kept), `proposed/ripple_wave/0063` ripple v1's consumer seam (nothing
  seeds a ripple yet).
- `planned/knowledge_graph_convergence/` (0050-0055) — operator ruling
  2026-10-27 (ADR 0002): AbstractMemory IS the semantic temporal memory
  graph and owns all of its processing. Absorb what AbstractNote built over a
  parallel graph (entity registry and reversible merges, claim lifecycle and
  revision log, document-knowledge retrieval, communities/consolidation/
  reflection, the ripple process, a notes/diary layer shared with
  AbstractEntity). `narrow_assertion` first: it removes AbstractNote's
  private-table write.
- `proposed/ripple_wave/0001` — change records with magnitude, closure causes,
  `narrow_assertion`, ripple-aware `maintenance_due`, the bound read (partly absorbed:
  `narrow_assertion` 0.4.0, magnitude and the bound read 0059-0061; see its status note) (ADR 0001,
  operator ruling 2026-10-21: an altered memory ripples through connected memories).
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

## Next Recommended Work (2026-11-10, after the 0.5.1 tag)

1. Both releases are out: 0.5.0 (tag `v0.5.0` on `8624137`, which adds the topic-priority fix on top of the release
   commit `5c6136b`; PyPI 2026-11-10 03:06 UTC) and 0.5.1 (tag `v0.5.1` on `f5fdee0`; Release and CI workflows
   green, PyPI 2026-11-10 16:51 UTC). The wave and its order are root backlog 1179.
2. `planned/0069`'s runtime half (AbstractRuntime owns it): the switch is drafted, uncommitted, in the runtime's
   working tree (0.19.2 in preparation, floor `AbstractMemory>=0.5.1`); 0069 closes when that runtime release lands.
3. The next memory patch, smallest first: `proposed/0066` (placement mark as a pair; the same fix covers 0.5.1's
   `community_keys_of` / `community_memberships_of`), `proposed/0067` (one snapshot for `communities()`), the SQLite
   half of `proposed/0062` (the two autocommit points under `BEGIN IMMEDIATE`) and the `proposed/0068` docs nit.
   Each self-heals or is rare today; none blocked 0.5.1.
4. The convergence track in its README's reading order (0056 and 0058 first).

The earlier list (001, 002, 003) was resolved by the 2026-07-20 reconciliation:
002 completed, 001 and 003 deprecated.

## Planned Items

The 2026-07-20 reconciliation moved every earlier planned item to
`completed/` (001-007 standalone, subconscious_wave 0032-0035,
extension_wave 0037-0039) or `deprecated/` (001/003/006, each with the
superseding pointer).

| Item | Priority | Notes |
| --- | --- | --- |
| [`0069_runtime_recall_stamps_use_community_keys_of.md`](planned/0069_runtime_recall_stamps_use_community_keys_of.md) | P1 | Memory side published in 0.5.1 (`f66ef28`, tag `v0.5.1`, PyPI); the runtime's `_stamp_recall_topics` switches from the full `communities()` read (190 ms at 20k records) to `community_keys_of` (22 µs): drafted, uncommitted, in the runtime's tree (0.19.2 prep). |

### Knowledge graph convergence track (`planned/knowledge_graph_convergence/`, 0050-0061)

Operator ruling 2026-10-27 ([ADR 0002](../adr/0002-abstractmemory-owns-the-memory-graph.md)); see the
[track README](planned/knowledge_graph_convergence/README.md) for scope, reading order and prior art.
Consumer side: AbstractNote backlog 0033-0036.
Rows 0059-0061 are COMPLETED (2026-11-10, abstractmemory 0.5.0) and link to their completed records; they stay in
this table to keep the track whole.

| Item | Priority | Notes |
| --- | --- | --- |
| [`0050_entity_registry_identity_and_reversible_merges.md`](planned/knowledge_graph_convergence/0050_entity_registry_identity_and_reversible_merges.md) | High | One canonical entity; candidate lookup; reversible merges; review; unify with `alias_world_model`. |
| [`0051_claim_lifecycle_and_revision_log.md`](planned/knowledge_graph_convergence/0051_claim_lifecycle_and_revision_log.md) | High | Revision log with causes; claims with provenance; public `narrow_assertion` (ship first). |
| [`0052_document_knowledge_retrieval.md`](planned/knowledge_graph_convergence/0052_document_knowledge_retrieval.md) | Medium | Hybrid search with facets, expansion, timelines, then-versus-now, change feed, as-received. |
| [`0053_self_organisation_communities_consolidation_reflection.md`](planned/knowledge_graph_convergence/0053_self_organisation_communities_consolidation_reflection.md) | Medium | Communities, topics, document consolidation, reflection and insights, review list. Communities slice shipped in 0.5.0 (`3082695`..`01ff4e2`, see its Progress note); the rest open. |
| [`0054_ripple_propagation_and_activation.md`](planned/knowledge_graph_convergence/0054_ripple_propagation_and_activation.md) | High | ADR 0001's process; absorbs AbstractNote's R6 prototype; promote `proposed/ripple_wave/0001` with it. |
| [`0055_notes_and_diary_layer_for_consumers.md`](planned/knowledge_graph_convergence/0055_notes_and_diary_layer_for_consumers.md) | Medium | A note/diary abstraction over the graph for AbstractNote and AbstractEntity. |
| [`0056_ledger_provenance_contract_and_revision_log.md`](planned/knowledge_graph_convergence/0056_ledger_provenance_contract_and_revision_log.md) | High | ADR 0003. In progress: `abstractmemory.graph` (SourceRef, Provenance, revisions, history, change feed, replay), `narrow_assertion`; 0.4.0. |
| [`0057_one_mind_per_plane_sqlite_home.md`](planned/knowledge_graph_convergence/0057_one_mind_per_plane_sqlite_home.md) | High | ADR 0003 decision 3. Planned, unblocked: connectors behind `MemoryGraph` (S8 landed: protocol, conformance suite, LanceDB connector); next the plane import through `import` revisions and the gateway default (SQLite). |
| [`0058_home_store_performance_indexes_vectors.md`](planned/knowledge_graph_convergence/0058_home_store_performance_indexes_vectors.md) | High | ADR 0003. Owner predicate, column projection, binary vectors, matrix cache. |
| [`0059_record_understanding_rewrites_in_place_with_versions.md`](completed/knowledge_graph_convergence/0059_record_understanding_rewrites_in_place_with_versions.md) | P1 | COMPLETED 2026-11-10 (0.5.0, `3fbaf10`; plus read-time provenance, stored text whole, `retitle`, `rekey_world_model`). ADR 0003 decision 6a. `rewrite_digest` / `narrate_dream` / `revert_digest` / `versions`, cards in place, `dream_pass` signals, replay provenance. |
| [`0060_memory_task_queue.md`](completed/knowledge_graph_convergence/0060_memory_task_queue.md) | P1 | COMPLETED 2026-11-10 (0.5.0, `5997b68`; plus the pending contract, `form_with_tasks`, sleep cadence). The persistent queue of memory tasks; `select_for_window(budget_seconds, sensitivity)` gates each task's strength through ADR 0001's logistic; debt, backfill, packet. |
| [`0061_ripple_v1_over_the_task_queue.md`](completed/knowledge_graph_convergence/0061_ripple_v1_over_the_task_queue.md) | P2 | COMPLETED 2026-11-10 (0.5.0, `09686e0`); consumers deferred (`proposed/ripple_wave/0063`). ADR 0001 v1 (first slice of 0054): `seed_ripple` / `settle_reconsideration` / `form_consolidation`, gate decisions on record, sleep consolidation. |

## Proposed Items

| Item | Notes |
| --- | --- |
| [`0008_gateway_memory_install_and_config_boundary.md`](completed/0008_gateway_memory_install_and_config_boundary.md) | COMPLETED 2026-07-20 — the boundary exists both sides (gateway memory_store.py resolver + embeddings route; memory stayed dependency-light). |

### 0.5.0 follow-ups (filed 2026-11-10)

From the 0.5.0 release's documented residuals (CHANGELOG `[0.5.0]` Upgrading, `write_barrier.py`, `01ff4e2`) and the
Fable pre-tag review (framework root `untracked/finish-plan-2026-11-09/graph-topics/REVIEW-memory-0.5.0.md`). Targets
re-set 2026-11-10: 0.5.1 shipped without the four aimed at it.

| Item | Target | Notes |
| --- | --- | --- |
| [`0062_write_barrier_residual_windows.md`](proposed/0062_write_barrier_residual_windows.md) | next patch (SQLite half) | `_write_pin` without a cursor and the off-file `mark_journal_applied` are autocommit points outside another handle's barrier; LanceDB takes no write lock. |
| [`0063_ripple_v1_consumer_seam.md`](proposed/ripple_wave/0063_ripple_v1_consumer_seam.md) | with root 1172 | Nothing seeds a ripple yet; memory's checks and calibration run when the runtime starts. |
| [`0064_community_facts_merged_into.md`](proposed/0064_community_facts_merged_into.md) | when asked | A dissolved community's destination is not in the facts (`split_from` is). |
| [`0065_embed_missing_vector_generation_bump_batching.md`](proposed/0065_embed_missing_vector_generation_bump_batching.md) | if measured | Skipped in `01ff4e2`: a deferred bump would hide committed vectors from other handles after a Stop. |
| [`0066_placement_index_misses_dissolve_only_versions.md`](proposed/0066_placement_index_misses_dissolve_only_versions.md) | next patch | The catch-up mark is the store rowid only; a dissolve-only version never reloads the index. 0.5.1's membership reads share the catch-up and inherit it. |
| [`0067_communities_read_is_not_one_snapshot.md`](proposed/0067_communities_read_is_not_one_snapshot.md) | next patch | Three statements; one read can serve a version with no communities. |
| [`0068_api_doc_queue_less_list_omits_communities.md`](proposed/0068_api_doc_queue_less_list_omits_communities.md) | next docs pass | `docs/api.md:226` omits `communities_pass` and `embed_missing` (still true at `v0.5.1`). |
| [`0070_topic_versions_churn_small_deltas_and_via_promotion.md`](proposed/0070_topic_versions_churn_small_deltas_and_via_promotion.md) | next minor, with root 1201 | A `via` promotion or a one-record delta marks a topic `changed`: 64 versions / 261 closed topic records / 247 link rows in one day on a busy home (castor: 4). Versions are already incremental; add an ids-only compare and a rewrite floor. |

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
| 2026-11-10 | 0.5.1 work, no item closed (tag `v0.5.1` on `f5fdee0`): `community_keys_of` / `community_memberships_of` (`f66ef28`), the memory half of planned 0069, which stays planned for the runtime switch; standing pending topics authored in place and their legacy tasks moved up (`7e83d2b`, from Castor's second topics night: 10 of 11 topics titled, the 11th's first-night tasks at priority 5 behind ~267 repair tasks). Also `8624137` (topic tasks at `COMMUNITY_PRIORITY` 3, the pass's budget to the topics), committed after the 0.5.0 release commit and tagged as `v0.5.0`. | `f66ef28`: `tests/test_community_keys_of.py` (37), mutants K1-K8 red (`abstractmemory/untracked/community-keys-of/`), full suite 2356 passed, 3 skipped, 2 xfailed; 20 µs / 22 µs per call at 2,000 / 20,000 records. `7e83d2b`, `8624137`: `tests/test_communities.py`; CHANGELOG `[0.5.1]` and `[0.5.0]`. All three are communities-slice work of planned 0053 (progress note added). |
| 2026-11-10 | [`completed/knowledge_graph_convergence/0059_record_understanding_rewrites_in_place_with_versions.md`](completed/knowledge_graph_convergence/0059_record_understanding_rewrites_in_place_with_versions.md) (was `planned/knowledge_graph_convergence/`, created 2026-11-07) | abstractmemory 0.5.0 (`5c6136b`; recorded here as local and unpublished, published the same day: tag `v0.5.0` on `8624137`, PyPI). Engine `3fbaf10`; plus read-time provenance `e74c29c`, stored text never cut `8ac6df4` `566f174` `20cd1f4`, `retitle` `d4fc7e4`, `rekey_world_model` `6e4ca13`, identical words settle `15ef176`. Release suite `abstractmemory/untracked/release-0.5.0/pytest-full.log` 2291 passed, 3 skipped, 2 xfailed; 17 feature modules re-run 2026-11-10: 605 passed, 2 skipped; mutants per test docstring; Fable pre-tag review GO. |
| 2026-11-10 | [`completed/knowledge_graph_convergence/0060_memory_task_queue.md`](completed/knowledge_graph_convergence/0060_memory_task_queue.md) (was `planned/knowledge_graph_convergence/`, created 2026-11-07) | 0.5.0. Queue `5997b68`; pending contract `c4ffc45` `4f3a77e` `c46b4cd` `11687df` `8ceb511` `71de051` `8235daf` `82178c9` (engram author); one commit for a record and its tasks `39e479e` `b403c0d` `1cd854e` `3a5810c`; sleep cadence `645d94e` `26503e3` `7ccc605` `d1c1d9a` `9dae0d7` `f310865`. Mutants Q1-Q12, F5-F8 red; Codex reviews 2 and 3 findings closed (framework root `untracked/entity-phases-2026-11-08/review/`). |
| 2026-11-10 | [`completed/knowledge_graph_convergence/0061_ripple_v1_over_the_task_queue.md`](completed/knowledge_graph_convergence/0061_ripple_v1_over_the_task_queue.md) (was `planned/knowledge_graph_convergence/`, created 2026-11-07) | 0.5.0. Engine `09686e0`, `tests/test_ripple_v1.py`, mutants R1-R8 red. Consumers DEFERRED: nothing outside memory seeds a ripple (root 1172 / 1171 paused); `proposed/ripple_wave/0063`. |
| 2026-11-10 | 0.5.0 work with no item of its own: the Stop fence hooks (`commit_guard` `4074406` `3a5810c`, `write_barrier` `85ecf75`) and the communities slice of planned 0053 (`3082695` `aac9476` `c07f5e9` `d550551` `7ccc605` `d1c1d9a` `01ff4e2`) | Fence: `tests/test_commit_guard.py`, `tests/test_write_barrier.py`, mutants in `abstractmemory/untracked/commit-guard/mutants.txt` and B1-B7 (commit `85ecf75`); residual windows filed as `proposed/0062`. Communities: Fable reviews `REVIEW-memory-m1.md` (all should-fixes fixed in `01ff4e2`) and `REVIEW-memory-0.5.0.md` (framework root `untracked/finish-plan-2026-11-09/graph-topics/`); progress recorded in 0053; follow-ups `proposed/0064`-`0068`. The other no-item work (provenance, titles, pending, cadence) is recorded in the 0059 and 0060 reports. |
| 2026-07-20 | 31-item reconciliation (planned 002/004/005/007, subconscious_wave 0032-0035, extension_wave 0037-0039, memory_system_v1 0009-0011/0013-0014/0017-0027/0029-0031/0036) | Every item audited against the shipped tree and moved to `completed/` with a per-item completion report naming modules + receipts; 001/003/006 deprecated with superseding pointers. The shipping receipts live on the hub (extension/subconscious/W2/W-GROUP/wave-5 SHIP posts); suite 1037 green at reconciliation. |
| 2026-07-17 | [`completed/extension_wave/0049_stable_shelf_order_for_prefix_reuse.md`](completed/extension_wave/0049_stable_shelf_order_for_prefix_reuse.md) | Engine `stable_render_order()` (6 pins, suite 875 green, c2846) + runtime election wired in `_memories_block` (c2895) + core's measured LCP delta on Ephemeral's real store: 75.1% vs 52.6% region reuse, 2.8x on rank-churn pairs (c2911). Decision: `decision:0049-stable-render-order`. |

When a planned item is completed, move it to `docs/backlog/completed/`, update
its metadata, add a completion report, and add a row here with validation
evidence.

## Deprecated Items

Three, all deprecated in the 2026-07-20 reconciliation: [`001`](deprecated/001_semantics_aligned_memory_record_conventions.md)
(superseded by the 0016 ruling), [`003`](deprecated/003_bounded_graph_traversal_over_triples.md) (by spreading
activation), [`006`](deprecated/006_deterministic_anchor_and_facet_index.md) (by the shipped channel set). (This section
said "none yet" until 2026-11-10.)

## Completion Process

1. Re-read the planned item and inspect the current code/docs it references.
2. Implement the scoped behavior, docs, and tests.
3. Run the validation listed in the item.
4. Add a completion report to the item.
5. Set `Status: Completed` and `Completed: YYYY-MM-DD`.
6. Move the file from `planned/` to `completed/` (since 2026-11-10 without `git mv`: see the pointer convention in
   the planning notes).
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
- Pointer convention (2026-11-10, first used for 0059-0061): file moves through `git mv` / `git rm` are not used
  in this repository's hygiene passes. A completed item is written as a NEW file under `completed/<track>/` with the
  same `NNNN_` name, carrying the item's original content whole, a status block (completed date, release and commit,
  original path) and its completion report; the planned file is reduced to ONE line, "Moved to
  completed/<track>/NNNN_<slug>.md on <date>", linking to it. The pointer is intentional duplication: it is not a
  live item, it is not counted, and it keeps older links valid (ADR 0001 and ADR 0003 still link to the planned
  paths of 0061 and 0059). A later pass that is allowed to delete files may remove the pointers after updating
  those links.
- Numbering audit (2026-11-10): new items use the next global four-digit prefix (0062-0068 and 0070 filed here). Known legacy
  collision, not renamed: `deprecated/001_...` (three digits) and `proposed/ripple_wave/0001_...` share the numeric
  id 1; refer to the ripple item by its path.
- Draft ids (2026-11-10): "runtime 0867-0870", "gateway 1012/1013" and "root 1137" in the 0059-0061 texts are the
  understanding-pass draft ids (framework root `untracked/understanding-pass-2026-11-07/drafts/`), never filed under
  those numbers; the tracked items are root backlog 1171 (the drain) and 1172 (the `revise` election and the ripple
  drain). Root `docs/backlog/planned/understanding-pass/README.md` records the mapping.
