# Proposed: Append-only closure records for retract and supersede

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: High
- Components: models, store protocol, backends, query semantics, tests, docs

## ADR status

- Governing ADRs: AbstractFramework `0005-memory-architecture.md`,
  `0009-connected-memory-recall-and-provenance.md`
- ADR impact: Needs new ADR (belief lifecycle: closure semantics, no-erasure
  policy — durable cross-package rules; write it at promotion time)

## Context

AbstractMemory models validity (`valid_from`/`valid_until`) but nothing ever
ends it: there is no retract, supersede, or correction mechanism. Contradictory
facts accumulate with no machine-readable resolution. ai-space hand-rolled
`attributes.op` folding to compensate; the runtime has no way to express "this
was wrong" or "this replaced that".

Owner decision (2026-07-05): strict append-only closure records — a
retraction/supersession is itself a new record; queries resolve validity at
read time. No in-place `valid_until` updates. No physical erasure (see `0018`
for the forgetting model: decay + closure + silencing).

## Current code reality

- All three stores are append-only with no update path (correct).
- `TripleQuery.active_at` filters on `valid_from`/`valid_until` written at
  assert time only.
- Depends on `0009` (assertion ids at read) — closure targets an assertion id.
- The Open Codex Memory prototype's equivalent: correction is a successor node
  plus `replaces`/`disagrees_with`/`refines` edges; its ADR bans an
  `invalidated_by` edge; hidden bindings handle visibility. Two adaptations
  are made here because triples are finer-grained than fork nodes: closure
  targets a single assertion, and closure affects default retrieval directly.

## Problem or opportunity

Without closure, every consumer that needs "current truth" must implement its
own fold (ai-space proves this happens), and contradictory facts poison
retrieval quality forever.

## Proposed direction

1. `ClosureRecord` (frozen dataclass, stored by the journal from `0017`, or by
   a dedicated closure table when the journal has not landed — decide at
   implementation with the journal item):
   - `closure_id`, `assertion_id` (target), `kind: retract | supersede`,
     `replacement_ids: tuple[str, ...]` (supersede), `reason: str` (required),
     `observed_at`, `actor`, `provenance`.
2. Store surface: `close_assertions(assertion_ids, *, kind, replacement_ids=(),
   reason) -> list[str]`. Append-only; closing a closed assertion is a warned
   no-op; closing a missing id is an error.
3. Query semantics (the load-bearing part):
   - default queries exclude closed assertions ("open world of current
     belief");
   - `TripleQuery(include_closed=True)` returns everything with closure
     metadata attached (audit mode);
   - `TripleQuery(as_of=<ts>)` returns what was believed at a time: closure
     records after `as_of` are ignored (bi-temporal read);
   - exact id lookups (`assertion_ids=...`) always return the row regardless
     of closure — completeness for audit.
4. Supersede writes closure + expects the replacement to already exist
   (caller composes: `add()` replacement, then `close_assertions(kind=
   "supersede", replacement_ids=...)`). No attention transfer: the replacement
   starts cold (fork lesson: revisions re-earn attention).
5. No fake history: closure writes no attention events (`0018`).

## Why it might matter

This is the difference between a log of claims and a belief system. It is also
the 2026 table-stakes mechanic (temporal edge invalidation in Graphiti/Zep),
adapted to strict append-only per the framework's ledger philosophy — and
per SOTA evidence, mechanism only: no LLM write-time contradiction detection
(mem0 retired theirs; contradiction *candidates* surface read-only in `0023`).

## Decision boundaries

- Closure is per-assertion, not per-record-cluster; closing a typed memory
  record (`0021`) means closing its type assertion and is a facade concern.
- `reason` is mandatory (fork rule: every lifecycle action carries an
  evidence-based reason).
- Never mutate assertion rows to reflect closure; the fold happens at read.

## Promotion criteria

Promote with `0009` when the wave is scheduled; the closure-fold read path
must be in place before hybrid retrieval (`0019`) ranks anything.

## Validation ideas

- Retract → default query excludes; `include_closed` includes with metadata;
  `as_of` before retraction includes; id lookup always includes.
- Supersede → replacement returned by default queries, target excluded, chain
  traversable via `replacement_ids`.
- Double-close is a warned no-op; close-missing raises.
- Parity across all three backends (fold logic shared, not triplicated).
- Performance: fold cost bounded at 100k assertions / 1k closures.

## Non-goals

- No physical deletion or redaction (owner decision).
- No automatic contradiction detection at write time.
- No cascading closure of derived assertions (lineage-aware invalidation is a
  possible follow-up once planned `005` lands).

## Guidance for future agents

Resist the shortcut of writing `valid_until` onto the closed row. The whole
point is that truth rows never change; the fold is the contract. Keep the fold
implementation in one shared module used by all backends.
