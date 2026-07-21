# Completed: Neurotransmitter attention — strengthen/weaken, decay, refocus (no erasure)

## Metadata

- Created: 2026-07-05
- Status: Completed (2026-07-20)
- Completed: 2026-07-20
- Priority: High
- Components: attention module (scoring), journal event writers, facade methods, tests, docs

## ADR status

- Governing ADRs: AbstractFramework `0007-active-context-and-memory-provenance.md`
- ADR impact: Needs new ADR (the attention contract and the no-erasure
  forgetting model are durable policy; write at promotion)

## Context

Owner decision (2026-07-05): AbstractMemory gets NO physical erasure. Instead,
"the equivalents of neurotransmitters that strengthen or weaken relationships
and therefore access to memory". The Open Codex Memory prototype implements
exactly this and its production history supplies the two hard lessons this
item encodes as contracts:

1. Attention-noise failure (fixed by design there): if scans, listings, and
   observer reads all feed one signal, last-used becomes whole-graph noise.
   Fix: ONLY selected use strengthens. Reading is not using.
2. Pruning failure: a heuristic relevance filter shipped and was removed the
   next day (judged F1≈0.5 — too weak to gate recall). Fix: attention can
   REORDER, never ADMIT or EXCLUDE.

## Current code reality

- Nothing exists. Depends on `0017` (journal stores the events), `0009` (ids
  to reference), `0010` (closure interaction).
- Full translation spec exists from the 2026-07-05 fork dissection (agent
  report "Attention Translation Spec"); this item encodes its decisions.

## Problem or opportunity

This is the owner's chosen forgetting model and the mechanism that makes
recall improve with use: memory that is used together strengthens together;
memory that stops being used fades — without ever mutating or deleting truth.

## Proposed direction

1. Event taxonomy (journal `MemoryEvent.kind`), with attention semantics:

   | kind | feeds activation | default weight | written by |
   |---|---|---|---|
   | `selected` | yes | 8 | `mark_selected` (host committed records into a context) |
   | `co_selected` (pair trail) | yes | 4 | `mark_selected` — for each selected pair sharing a term |
   | `pinned` | yes | +8 (clamp 1..25) | `reinforce()` |
   | `silenced` | yes (negative) | −8 | `attenuate()` |
   | `refocus` | modifies decay | 0 | `refocus()` |
   | `listed` / `shown` / `expanded` / `cited` | NO — audit only | 0 | retrieval/probe/expansion paths |

   Trails: when a selection set commits, every pair of co-selected assertions
   that shares at least one term (equal subject or object, either side) gets a
   `co_selected` event on the canonical sorted pair — the triple-store analog
   of the fork's edge trails ("green links"), recorded (not derived) so
   togetherness earns its own decay curve.

2. Activation scoring (pure function over journal events; derived at read,
   NEVER stored as truth):

   ```text
   eligible = {selected, co_selected, pinned, silenced}
   distance(e) = rank position of e among recency-ordered eligible∪refocus
                 events in the window (activity-relative, NOT wall-clock)
   if e older than latest refocus: distance ×= refocus_multiplier (6)
   contribution = sign(e) · weight(e) / (1 + distance / decay_window (20))
   activation(item) = clamp(Σ contributions, 0, max_activation (25))
   ranking influence = min(4 · activation, 120)   # vs 1000 direct-hit scale
   cumulative prior = min(ln(selected_count+1)·0.05, 1.0)  # inspection paths only
   ```

   Constants configurable in `AttentionConfig` (window 512, decay 20,
   refocus 6, clamp 25, boost 4/120, per-kind weights). The following are
   FIXED CONTRACTS, not configuration: (a) audit events never feed activation
   nor advance `selected_count`; (b) activation floor 0 (silence demotes,
   never negative relevance); (c) rank-distance semantics; (d) influence is
   additive after admission, capped ≤12% of a direct match — never gates
   candidate admission; (e) the prior applies only to interactive inspection
   ranking, never auto-recall.

3. API (facade + journal writers):
   - `mark_selected(assertion_ids, *, context_ref, scope, owner_id)` — the
     ONLY writer of `selected` + `co_selected`; called by hosts AFTER records
     actually entered a context (`0020`'s `commit_selection` wraps it);
   - `reinforce(id, *, reason, weight=8, ttl_activity=None)` /
     `attenuate(id, *, reason, weight=8, ttl_activity=None)` — deliberate
     strengthen/weaken; `reason` mandatory; TTL in activity units (an event
     expires once its rank distance exceeds `ttl_activity`), consistent with
     rank-distance decay;
   - `refocus(*, reason, scope, owner_id)` — topic shift; accelerates decay of
     older events; deletes and rewrites nothing;
   - `activation(ids=None, *, scope, owner_id, at_seq=None, include_trails=False)`
     — derived scores; `at_seq` gives time-anchored replay ("what was hot
     before X");
   - `activation_report(...)` — normalized scores + per-item contribution
     reasons + trail scores, the observer's data source (pure package
     function; gateway wraps it in an endpoint later).
4. Closure interaction (`0010`): closing writes NO attention events (no fake
   history); closed assertions leave default retrieval via the validity fold,
   so residual activation is historical fact, not live influence; replacements
   start cold (re-earn attention).
5. Forgetting = three auditable dials, zero erasure: natural decay (do
   nothing), closure (explicit validity end), silencing (explicit negative
   attention). Structured/exact queries ALWAYS stay complete — activation
   affects only ranked/semantic ordering.

## Why it might matter

It is the owner's explicit design direction, it is validated by the fork's
production usage (including the failure modes it prevents), and it gives the
framework human-plausible memory dynamics — use strengthens, disuse fades,
correction closes — with full auditability.

## Decision boundaries

- The anti-noise rule and the no-gating rule are contracts; changing them
  requires an ADR revision, not a config flip.
- Silence is a nudge, closure is the removal tool: −25 activation × 4 = −100
  against a 1000-point exact hit by construction (documented, intended).
- No wall-clock decay in v1 (activity-relative only); revisit only with
  evidence.

## Promotion criteria

Promote immediately after `0017`; `0019`/`0020` consume activation as a
tie-breaker.

## Validation ideas

- Audit events (listed/shown/expanded/cited) provably never change activation
  or ordering (regression test — the fork's documented failure mode).
- Decay: activation decreases monotonically with intervening eligible events;
  refocus accelerates older-event decay only.
- Silence never buries a direct exact match; strengthen never admits a
  non-matching candidate.
- TTL: pinned/silenced events stop contributing past their activity horizon.
- Trails: co-selected term-sharing pairs accumulate pair activation; pairs
  without shared terms do not.
- `at_seq` replay matches a recomputation over the truncated event stream.
- Determinism: identical journals produce identical scores (pure function).

## Non-goals

- No physical erasure or redaction (owner decision).
- No LLM involvement anywhere in attention.
- No automatic strengthening from retrieval alone (reading is not using).
- No cross-scope activation bleed (scores are per scope/owner).

## Guidance for future agents

Implement scoring as a pure function over an event slice so tests and the
observer share one implementation. Resist adding new attention-feeding event
kinds without revisiting the noise failure that shaped this design.


## Completion report (2026-07-20)

Shipped: attention.py — selected-use-only activation, rank-distance decay, refocus, clamps, AttentionConfig declared dials (window/decay/drive_window_limit); commit_selection as the one strengthening path.
