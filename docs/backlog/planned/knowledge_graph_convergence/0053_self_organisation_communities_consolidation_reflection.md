# Self-organisation: communities, topics, consolidation, reflection, review

Created: 2026-10-27 (operator ruling, [ADR 0002](../../../adr/0002-abstractmemory-owns-the-memory-graph.md)).
Track: `knowledge_graph_convergence` · Priority: Medium · Status: Planned

## Summary
The passes that let a graph structure itself: community detection (deterministic, seeded) and their naming
through an injected reader; topic normalisation (one spelling per topic); consolidation stages for document
knowledge (merge duplicates, recompute communities, label, refresh stale summaries); deterministic reflection
candidates with provenance and the insight records they produce; the review list of disagreements and uncertain
matches.

## Why
Self-organisation is what makes AbstractMemory a memory rather than a store. Its sleep passes tend agent memory;
AbstractNote built the document-knowledge equivalent. One set of passes should serve both, scheduled by the host.

## Current code reality
- AbstractMemory: `consolidation.py` (`sleep_pass`, `consolidation_pass`, `dream_pass`: deterministic, zero model
  calls, components, duplicates), `maintenance.py`, `sleep_cadence.py`, `sleep_policy.py`, `dream_resolution.py`,
  `redigestion.py`, `doctoring.py` (dedup, verify), `candidate_miner.py`, `tend.py`. No communities, no topic
  records, no summary refresh, no insight records with provenance.
- AbstractNote (prior art): `recall/communities.py` (Louvain via `networkx`, fixed seed, weights from statements
  and co-mentions), `store/topics.py`, `recall/consolidation.py` (staged `note-consolidate`), `recall/reflect.py`
  (rules with explicit thresholds and repeat guards), `recall/insights.py`, `recall/review.py`.

## Scope
In: the passes as AbstractMemory functions with budgets and recorded results, reader injected where judgement is
needed, wired into the existing maintenance cadence (`maintenance_due`). Out: scheduling (the host's runtime),
prompt wording. Decide in this item whether `networkx` becomes an optional extra (AbstractMemory is
dependency-light).

## Dependencies
0050, 0051, 0052. Ripples triggered by consolidation go through 0054.

## Validation
Seeded community detection is stable across runs; a consolidation pass over a fixture graph produces recorded
stages and respects its budget (nothing dropped silently, root ADR-0026); reflection candidates carry their rule
and provenance; mutation tests per rule.

## Progress (2026-11-10): the communities slice shipped in abstractmemory 0.5.0

Built and released in 0.5.0 (release commit `5c6136b`; written as not yet published, published the same day: tag
`v0.5.0` on `8624137`, PyPI), from COMMUNITIES-DESIGN
(framework root `untracked/finish-plan-2026-11-09/graph-topics/COMMUNITIES-DESIGN.md`, with the Fable deltas of
`FABLE-REVIEW-communities-design.md`):
- `3082695` the `community` record kind (one record per version, a stable `attributes.community_key`),
  `communities_pass` (deterministic warm-started Louvain over the vectored records, vector-less records attached by
  their engraved relations, layout, authored titles, one guarded transaction) and `embed_missing`; `aac9476` and
  `01ff4e2` a community is never embedded or recalled (`canonical_text.never_embedded`, an AST closed-set test over
  every embed site); `c07f5e9` at most 5 stabilisation rounds, `unplaced_closed` in the receipt; `d550551`
  placement at formation inside `form_with_tasks` and the reads `communities()` (payload version 2 with `facts`) /
  `community_of()` (`community_index.py`); `7ccc605`, `d1c1d9a` the sleep cadence's `fragmented` share leaves out
  records no edge can place.
- The dependency decision this item asked for: no `networkx`; pure Python plus numpy (the `[fast]` extra; without
  numpy the pass is skipped with its reason).
- Evidence: Fable review of M1 `untracked/finish-plan-2026-11-09/graph-topics/REVIEW-memory-m1.md` (APPROVE WITH
  SHOULD-FIXES, all five fixed in `01ff4e2`; probes under `abstractmemory/untracked/review-m1/`), Fable pre-tag
  review `REVIEW-memory-0.5.0.md` (GO; probes under `abstractmemory/untracked/review-050/`); tests
  `tests/test_communities*.py`, `tests/test_community_placement.py`; release suite
  `abstractmemory/untracked/release-0.5.0/pytest-full.log` (2291 passed, 3 skipped, 2 xfailed).

Filed from that work: `proposed/0064` (`merged_into` in the facts), `proposed/0065` (`embed_missing`'s
`vector_generation` bump, skipped with its reason), `proposed/0066` (placement index misses a dissolve-only version,
0.5.1), `proposed/0067` (`communities()` is not one snapshot, 0.5.1), `proposed/0068` (api.md nit). Review
observations not filed: the 10k layout step is the slowest (1.9 s), the γ 1.5 split fragments a merged block (never
armed on castor), the neighbour vote's owner check has no red test (mutant m2 survived), and an off-file journal
costs one `selected_count` query per digest row in `communities()` (the runtime opens one file).

## Progress (2026-11-10): topics after the 0.5.0 release commit (the `v0.5.0` tag and 0.5.1)

- `8624137` (committed after the release commit, tagged as `v0.5.0`): a topic's `title.author` / `digest.author`
  tasks are queued at `COMMUNITY_PRIORITY` (3, ahead of `FORMATION_PRIORITY` 5); `communities_pass`'s `budget` goes
  to the topics, largest first, one call per topic; the receipt carries `budget` / `budget_spent`.
- `7e83d2b` (0.5.1): what the budget leaves goes to the STANDING topics still pending, written in place on their
  current record (`rewrite_digest` / `retitle`); every standing topic's live authoring task waiting behind
  `COMMUNITY_PRIORITY` moves up (`MemoryTaskQueue.prioritize`); the receipt's `pending` is read back. Found on
  Castor's second topics night: 10 of 11 topics titled, the 11th's first-night tasks at priority 5 behind ~267
  repair tasks.
- `f66ef28` (0.5.1): `community_keys_of` / `community_memberships_of`, the membership-only read the runtime's recall
  stamps switch to (planned 0069): 20 µs / 22 µs per call at 2,000 / 20,000 records. It shares placement's
  catch-up, so it inherits `proposed/0066`.
- 0.5.1 shipped without `proposed/0066`, `0067`, `0068` and the SQLite half of `0062`; their target is now the next
  memory patch.
- Evidence: `tests/test_communities.py`; `tests/test_community_keys_of.py` (37; mutants K1-K8 red,
  `abstractmemory/untracked/community-keys-of/`); full suite at `f66ef28` 2356 passed, 3 skipped, 2 xfailed.

Still open in this item: topic normalisation (one spelling per topic), the consolidation stages for document
knowledge, deterministic reflection candidates and their insight records, the review list. The item stays planned.
