# Completed: Cross-backend parity conformance suite (and the divergences it fixes)

## Metadata

- Created: 2026-07-05
- Status: Completed (2026-07-20)
- Completed: 2026-07-20
- Priority: High
- Components: tests (new conformance module), models, all three backends

## ADR status

- Governing ADRs: AbstractFramework `0019-testing-strategy-and-levels.md`
- ADR impact: None

## Context

The backlog planning notes promise "in-memory, SQLite, and LanceDB stores
remain first-class backends". The 2026-07-05 adversarial audit proved the
promise false today: the backends disagree on core query semantics, and the
per-backend test files structurally cannot catch it. Findings were verified by
execution (lancedb 0.30.0, Python 3.12).

Verified divergences (severity in parentheses):

1. (critical) Literal-cased objects (`attributes.literal=true`) are matched
   case-insensitively by in-memory (`in_memory_store.py:111`) and LanceDB
   (`lower(object) =` in the where clause) but EXACTLY by SQLite
   (`sqlite_store.py:153-155` compares the raw column against the lowercased
   query term) — SQLite returns 0 hits where the others return 1. This
   silently breaks the runtime's dedupe probe → unbounded duplicates.
2. (critical) Semantic queries with `limit<=0`: in-memory returns all rows;
   LanceDB caps at its internal default of 10 (`lancedb_store.py:235`,
   `to_list()` without `.limit()`).
3. (major) In-memory non-semantic queries return aliased store internals
   (`in_memory_store.py:184`) — mutating a result corrupts the store. The
   semantic path deep-copies; SQLite/LanceDB rebuild fresh objects.
4. (major) Timestamps are unvalidated strings compared lexicographically in
   all backends; mixed formats (`Z` vs `+00:00`, second vs microsecond
   precision) corrupt ordering and range filters. Reachable from raw HTTP
   payloads via the gateway KG route.
5. (major) NaN scores bypass `min_score` (`in_memory_store.py:154`: `NaN < x`
   is False) and poison ranking; cosine silently truncates on dimension
   mismatch (`in_memory_store.py:42`, `n = min(len(a), len(b))` —
   `cosine([1,0,0,0],[1,0]) == 1.0`) while LanceDB raises on the same input.
6. (minor) NaN confidence: SQLite roundtrips to None, in-memory preserves NaN.
7. (minor) Non-JSON-serializable attributes: accepted in-memory, TypeError at
   add on SQLite/LanceDB.
8. (minor) `TripleQuery.vector_column` defaults to `"vector"` so the store
   constructor's `vector_column` override is dead configuration
   (`store.py:67-69` vs `in_memory_store.py:147`).
9. (minor) Unicode: no NFC normalization, `lower()` not `casefold()`
   (`models.py:14-21`) — NFD query misses NFC-stored terms; `straße`/`STRASSE`
   don't match.

## Current code reality

- 16 existing tests, all happy-path, per-backend files, ≤3-row datasets; none
  of the above is covered.
- See file:line citations above; re-verify each against current code before
  fixing (some may have been fixed since the audit).

## Problem or opportunity

Divergence is a bug class, not a bug: without a single conformance suite that
runs identical scenarios against all three backends, every future feature
(closure folds, journal, hybrid retrieval) will re-diverge.

## Proposed direction

1. One parametrized conformance module (`tests/conformance/`) with a store
   fixture parametrized over in-memory, SQLite, LanceDB (LanceDB skipped when
   not installed), asserting IDENTICAL results for: literal-object matching,
   limit semantics (positive, zero, negative; semantic and structured),
   ordering with ties (deterministic tie-breaker everywhere — adopt SQLite's
   `observed_at, assertion_id` rule), result isolation (mutation of results
   never affects the store), timestamp handling, NaN/zero/mismatched vectors,
   vectorless rows, serialization edge cases, unicode terms.
2. Fix the divergences the suite catches. Chosen behaviors:
   - literal objects: match case-sensitively ONLY when the query term is also
     marked literal; otherwise case-insensitive on both sides (i.e. fix SQLite
     with a `lower(object)` comparison and document the literal contract);
   - `limit<=0` semantic queries: return all matches on every backend (LanceDB
     via an explicit large limit with a documented ceiling + warning);
   - deep-copy or rebuild all returned objects everywhere;
   - normalize timestamps at the model boundary: parse ISO-8601 (accepting
     `Z`), convert to UTC, re-serialize to one canonical microsecond format in
     `TripleAssertion`/`TripleQuery` `__post_init__`; reject unparseable
     values in `from_dict` (`#FALLBACK`-labeled leniency if any);
   - `_cosine`: raise on dimension mismatch; NaN scores are excluded with a
     warning; zero vectors score 0.0 (documented);
   - unicode: NFC-normalize + `casefold()` in `canonicalize_term` (note: this
     changes stored canonical forms for new writes only; document the
     read-compat implication);
   - remove or honor the store-level `vector_column` (pick one; honoring means
     `TripleQuery.vector_column: Optional[str] = None` falling back to the
     store's value).
3. Extend the suite whenever any later item (0009/0010/0017/0019) adds store
   behavior — parity is a permanent gate, not a one-off.

## Why it might matter

Every consumer that switches backends (dev on memory, deploy on
SQLite/LanceDB — the documented pattern) currently changes behavior silently.
The dedupe breakage (divergence 1) is live data corruption in production
shapes.

## Promotion criteria

Promote with the wave; this item should land immediately after `0009` so the
suite covers ids from day one.

## Validation ideas

The item IS validation. Success = the conformance suite passes identically on
all three backends and each fixed divergence has a dedicated regression test
that failed before the fix.

## Non-goals

- No new query features (that is `0019`).
- No performance work beyond what parity requires (benchmarks live in `0015`
  validation and later work).

## Guidance for future agents

Write the failing conformance tests FIRST, verify they fail on the current
code for the documented reasons, then fix. If a documented divergence no
longer reproduces, note it in this item and skip the fix.


## Completion report (2026-07-20)

Shipped: the whole test suite runs parametrized [memory]/[sqlite] via the conftest stack fixture — 1000+ tests execute against both backends on every run; parity IS the suite.
