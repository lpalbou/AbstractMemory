# A persistent queue of memory tasks in the home: what still needs understanding, leased and drained by the host

Status: Completed · Completed: 2026-11-10 · Shipped in: abstractmemory 0.5.0 (commit `5c6136b`; written as
not yet tagged, pushed or published, then published 2026-11-10: tag `v0.5.0` on `8624137`, PyPI) · Original path: `planned/knowledge_graph_convergence/0060_memory_task_queue.md`
(a one-line pointer since 2026-11-10; see the overview's planning note) · Item history: written with the code in
`5997b68` (2026-11-08), closed by the backlog commit that created this file.

Created: 2026-11-07 (understanding pass). Track: `knowledge_graph_convergence` · Priority: P1 · Type: feature ·
Status (as planned, 2026-11-08): Planned — engine half implemented on `main` (see Report), awaiting the maintainer's ship review; the drain
is runtime 0869.

## Summary
AbstractMemory keeps a durable queue of **memory tasks** in the home file (`memq_tasks`, `memq_log`,
`memq_windows` in `memory.sqlite3`). A task names one piece of understanding still owed: `digest.rewrite`,
`card.author`, `dream.narrate`, and the ripple's `ripple.reconsider` / `ripple.consolidate` (0061). Memory enqueues
the tasks itself where records form. The host leases them, runs the model and applies the result through the 0059
verbs. Which tasks a window runs is **activation-driven**: each task carries the strength of the incoming memory,
change or surprise; `select_for_window(budget_seconds, sensitivity)` gates it through ADR 0001's logistic and
returns the tasks above the floor, strongest first, until the budget or the hard cap, with everything else in
`left_out` with its reason.

## Why
Operator ruling 2026-11-07, rule 1: summaries and metadata are ALWAYS computed, in the background whenever
resources are free, with eventual consistency, driven by a PERSISTENT queue, preferably "a higher-level queue of
memory tasks inside AbstractMemory". Operator decision 3 (2026-11-08): no fixed `memories_rebuilt_per_turn`; the
strength of what came in sets an activation through the existing sigmoid-like activation function; the Mind setting
is the sensitivity of that function plus a hard safety cap, never a count. Operator ruling 2026-11-08 (generation
gate): the host-wide gate is a later design item; selection must not depend on it.

## Current code reality (audited 2026-11-07, before the change)
- No queue in AbstractMemory; `redigestion_candidates` rescanned the whole store per call and knew only episodes and
  summaries. AbstractNote's `store/queue.py` is prior art only (its ADR 0003 rules out a library dependency).
- The activation function: ADR 0001 decision 7 specifies the logistic gate `1 / (1 + e^-k(x - θ))`; no code in
  AbstractMemory implemented it (the shipped activations are `spreading.SpreadParams` and attention's clamped
  hyperbolic decay `attention._contribution`). AbstractNote's prototype (`recall/activation.py` `logistic`, branch
  `retro/integration`) carries the calibration (k 6, θ 0.5, floor 0.1, decay 0.5).
- Formation goes through `MemorySystem.remember_many`; mechanical writers label `digest_method` (consent set
  `MECHANICAL_DIGEST_METHODS`); cards form in `world_model_pass`, dreams in `dream_pass`; review offers
  (`maintenance_candidate`, `review_required`, `mechanical-dedup-v1`) are not understanding.
- `maintenance_due` counted new records and fragments only.

## Scope
In:
1. `activation_gate.py`: the gate and every threshold in one module, calibration quoted (ADR 0001 Enforcement).
2. `memory_tasks.py`: the schema (created on open; opening a home whose queue exists is a read), `MemoryTaskQueue`
   (`enqueue`, `select_for_window`, `claim`, `ack`, `release`, `left_out`, reads, `supersede_stale`), the enqueue
   sites, `understanding_debt`, `enqueue_debt` (dry-run by default; strength from lived use), `task_packet` (items
   whole within a token budget, the rest listed). No stored field carries a length cap (root ADR 0054).
3. The 0059 verbs settle a named task (`task_id=`) in their own transaction and supersede stale tasks; a SQLite home
   whose file holds the queue is settled even by a process that did not opt in.
4. `MemorySystem(task_queue=True)`; `maintenance_due(tasks=)`; the cold cut copies the queue.
5. Docs: `api.md` (the queue), `memory-system.md`, CHANGELOG.

Out: running a model, window timing and budgets, any generation gate (runtime); the ripple's propagation (0061).

## Dependencies
0059.

## Acceptance Criteria
- [x] Forming a mechanical episode in an opted-in home enqueues exactly one `digest.rewrite`; replaying the same
  formation enqueues nothing new.
- [x] A home without the opt-in enqueues nothing and creates no queue tables.
- [x] An expired lease returns its task to pending; three claims without settling fail it; three retries fail it with
  the last error; a defer never spends an attempt.
- [x] A summary task is not leased while one of its episodes has a pending rewrite.
- [x] A rewrite to version N+1 supersedes a pending task for basis N; an older basis is refused at enqueue.
- [x] `understanding_debt` matches a hand count; maintenance candidates, dedup groups and protected kinds are absent.
- [x] Opening a home whose queue tables exist takes no write lock.
- [x] Selection: highest activation first; the floor and the sensitivity decide; the budget and the hard cap bound
  it; every live task is selected or left out with a reason; selection writes nothing.

## Testing
- `python -m pytest tests/test_memory_task_queue.py -q`
- `python -m pytest tests -q -m "not integration and not lmstudio"`

## Report

Implemented 2026-11-08 on `main`.

- The queue shares the SQLite store's connection and lock (`memq_` tables; `memq_<table>_` for a custom table
  name), so `rewrite_digest` / `author_world_model` / `narrate_dream` with `task_id=` ack the task in the rewrite's
  `BEGIN IMMEDIATE` transaction: a failed apply rolls the ack back with it (tested by failing the row write).
- Strengths: formation 1.0 (`FORMATION_STRENGTH`); a +delta card revision the share of its evidence that is new
  (floor 0.1); a dream `salience / SleepTuning.salience_high` (capped at 1); the backfill
  `0.1 + 0.9 * ln(1 + n) / ln(1 + n_max)` over selected counts. Priority (10 turn, 20 ripple, 30 summary/card,
  40 dream, 90 backfill) is only the tie-break after activation.
- Cost hints: memory reports what it holds (`input_tokens` of the target and source digests, the verbatim reference);
  seconds are the median of the kind's completed tasks' `result.seconds`, else `DEFAULT_TASK_SECONDS`; the host
  overrides with `cost_of`.
- `maintenance_due` is due for pending ripple and night-only tasks (ADR 0001 decision 9); digest and card rewrites
  are reported, they run in any window.

Tests: `tests/test_memory_task_queue.py` (37 cases, both substrate pairs) and
`tests/test_doctoring.py::test_cold_cut_keeps_the_memory_task_queue`. Mutants Q1-Q12 (listed in the test module
docstring and the cold-cut test) each turned their test red; the files were restored byte-exact.

## Completion report (2026-11-10)

Outcome: done. Every acceptance criterion above was met by `5997b68` (2026-11-08) and holds at the release commit
`5c6136b` (abstractmemory 0.5.0, CHANGELOG `[0.5.0]` "Added: the memory task queue (0060) and ripple v1 (0061)").

Shipped in 0.5.0 on top of the item, all of it riding on the queue (no backlog item of their own; recorded here and
in the overview ledger):
- The pending contract (operator ruling 2026-11-09: "the title + summary must ALWAYS exist for any memory"):
  `c4ffc45` a missing title or summary is PENDING with its `title.author` / `digest.author` task
  (`PENDING_FIELDS`, `PENDING_TASK_KINDS`; supersedes `155bf8f`'s plain untitled records); `4f3a77e` memory's own
  passes form pending, never a mechanical title or summary; `c46b4cd` passes author a record's title and summary WITH
  it and form pending only after a recorded authoring failure (`formation_authoring`, `authoring = {authored,
  failures}`; Codex review 2 finding 10); `11687df` `declare_pending` for stored records never authored; `8ceb511`
  `rearm_pending` and `pending_records`; `71de051`, `8235daf` a public diary entry's summary authored or declared
  pending (owner-direct, hash-chained and private entries stay protected); `82178c9` `engram(author=)`: birth
  records authored, never `trait-N`. Tests: `tests/test_pending_formations.py`, `test_formation_authoring.py`,
  `test_declare_pending.py`, `test_rearm_pending.py`, `test_diary_summary_authored.py`, `test_untitled_records.py`,
  `test_engram.py`.
- Formation and its tasks in one commit: `39e479e` `memory_tasks.form_with_tasks` (Codex review 2 finding 11: a
  failure could leave pending records without tasks); `b403c0d` the in-memory store and its queue share one reentrant
  lock (Codex review 3 finding 4); `1cd854e` a failed formation undoes only its own rows, bindings and tasks (finding
  3); `3a5810c` the commit guard immediately before `form_with_tasks`' COMMITs (Stop fence F8).
- Sleep cadence on the queue's `memq_maintenance`: `645d94e`, `26503e3` `records_since_maintenance(system, *,
  scopes=None, after=None)` (the host's idle -> sleep threshold); `7ccc605`, `d1c1d9a` the `fragmented` share leaves
  out records no edge can ever place; `9dae0d7` `fragmented.count` counts each record once (share never above 1.0);
  `f310865` `sleep_pass(..., cancelled=None)`: a night stopped in its final stage records no completion. Test:
  `tests/test_records_since_maintenance.py`; the 9dae0d7 count mutants F5-F8 red
  (`abstractmemory/untracked/release-0.5.0/mut/mutants.txt`).

Validation:
- Release suite at `5c6136b`: `abstractmemory/untracked/release-0.5.0/pytest-full.log`, 2291 passed, 3 skipped,
  2 xfailed, exit 0. Re-run on 2026-11-10 at `5c6136b` of the 17 feature modules: 605 passed, 2 skipped.
- Mutants Q1-Q12 (the Report above) red; the pending-contract and cadence mutants as listed in their test modules.
- Reviews (framework root): `untracked/entity-phases-2026-11-08/review/CODEX-REVIEW-2.md` (findings 10, 11),
  `CODEX-REVIEW-3-runtime-memory.md` (findings 3, 4, 7), `FABLE-REVIEW-fence-runtime.md` (F8),
  `untracked/finish-plan-2026-11-09/graph-topics/REVIEW-memory-0.5.0.md` (GO for the tag; engram and
  `form_with_tasks` probed).

Docs: CHANGELOG `[0.5.0]` (Upgrading: `task_queue=True` homes, the `author` callable, the pending contract);
`docs/api.md` (the queue, the constructor), `docs/memory-system.md` (the title/summary contract, sleep cadence),
`docs/faq.md`, `docs/troubleshooting.md`.
ADR state: ADR 0001 decision 7 (the logistic gate, `activation_gate.py`) and decision 9 (night-only work). No new
ADR; the "titles and summaries are mandatory" rule is an operator ruling recorded in the CHANGELOG and root backlog
1146 (completed).

Behaviour changes for hosts: the passes listed in the CHANGELOG's Upgrading section refuse a home opened without
`task_queue=True` before writing anything; `MemoryRecordInput` raises `ValueError` for an empty title without
`pending=("title",)`; `world_model_pass` no longer queues `card.author` for new cards.

Residual risks and follow-ups:
- The queue's consumer is partial: the tracked runtime drain (`abstractruntime/identity/authoring.py`
  `drain_authoring`) leases only `title.author` / `digest.author`; `digest.rewrite`, `card.author`, `dream.narrate`
  and the ripple kinds wait for root backlog 1171 (planned, paused) and 1172 (proposed).
- Docs nit: `docs/api.md` line 226 lists the passes that refuse a queue-less home without `communities_pass` and
  `embed_missing` (the CHANGELOG has them): `proposed/0068_api_doc_queue_less_list_omits_communities.md`.

Backlog drift found: "the drain is runtime 0869" in the header is a draft number never filed in AbstractRuntime; the
drain is root 1171.
