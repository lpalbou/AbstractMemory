# A persistent queue of memory tasks in the home: what still needs understanding, leased and drained by the host

Created: 2026-11-07 (understanding pass). Track: `knowledge_graph_convergence` · Priority: P1 · Type: feature ·
Status: Planned — engine half implemented on `main` (see Report), awaiting the maintainer's ship review; the drain
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
