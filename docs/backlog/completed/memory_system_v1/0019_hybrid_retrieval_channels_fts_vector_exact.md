# Completed: Hybrid retrieval channels — exact + keyword (FTS5) + vector, with reserved slots

## Metadata

- Created: 2026-07-05
- Status: Completed (2026-07-20)
- Completed: 2026-07-20
- Priority: High
- Components: sqlite_store (FTS5), lancedb_store (FTS/BM25), retrieval fusion module, capabilities, tests

## ADR status

- Governing ADRs: AbstractFramework `0009-connected-memory-recall-and-provenance.md`,
  `memory-recall-levels.md`
- ADR impact: None

## Context

Retrieval today is exact-structured OR vector-only (LanceDB/in-memory with an
embedder); SQLite raises on `query_text` and the gateway returns 400 for any
`query_text` on the sqlite backend. There is no keyword search anywhere.

Evidence this matters:

- 2026 agent-memory table stakes are hybrid semantic + keyword + graph
  (mem0/Zep/Graphiti all converged there).
- The Open Codex Memory prototype's evals: exact lexical matching was its BEST
  precision channel; pure-lexical P@≤10 was 0.19–0.29 overall (why it needed
  an LLM selector); topic clustering failed as retrieval. Lesson encoded here:
  vectors must NOT displace exact-match channels for identifiers, paths, and
  error strings — reserve slots per channel.
- Planned item 002 lists FTS5 as an optional sub-bullet; the audits concluded
  it is the higher-value half and deserves its own item (this one).

## Current code reality

- `sqlite_store.py:134-135` rejects `query_text`/`query_vector` (documented).
- LanceDB path embeds `query_text` and runs ANN; no BM25/FTS use.
- No fusion, no channel abstraction, no reserved slots.
- Depends on: `0009` (ids in results), `0010` (closure fold excludes closed),
  `0011` (parity gate), `0014` (trustworthy embedding space).

## Problem or opportunity

Recall quality is the memory system's user-visible payoff. One retrieval
module with three channels and honest fusion turns every backend into a
first-class recall citizen and fixes the gateway's 400s.

## Proposed direction

1. SQLite keyword channel: FTS5 virtual table over canonical text (from
   `0014`'s shared module) + title-ish fields; external-content pattern with
   sync kept correct on insert (no manual drift — fork regret); FTS5
   availability probed, capability-reported (planned 002), and absence
   degrades to a documented substring fallback labeled `#FALLBACK`.
2. LanceDB keyword channel: native FTS/BM25 index where the pinned version
   supports it; otherwise the same labeled fallback.
3. Channel abstraction in ONE fusion module (never per-backend logic):
   - `exact`: structured SPO/pattern hits — score scale 1000;
   - `keyword`: FTS/BM25 normalized scores;
   - `vector`: cosine over digest embeddings (manifest-validated).
   Fusion: reciprocal-rank fusion (RRF) across available channels with
   RESERVED SLOTS per channel (defaults: exact 2, keyword 3, vector 3 of a
   12-slot shelf) so no channel monopolizes results; every result carries
   named per-channel contributions ("why" cues).
4. Query surface: explicit and unambiguous — `query_text` keeps meaning
   semantic/vector (unchanged contract); keyword search is a NEW explicit
   field (`keyword_text`) or a retrieval-request object consumed by the
   fusion module (decide at implementation; never a hidden fallback of
   `query_text`, per planned 002's rule).
5. Activation (`0018`) joins as a capped tie-breaker AFTER fusion; closure
   fold (`0010`) applies BEFORE ranking; visibility bindings (`0017`) shape
   the candidate universe when called through the facade.
6. Capabilities report per-channel availability; the gateway can finally
   describe sqlite-backend recall honestly instead of 400ing.

## Why it might matter

Directly serves the framework's recall ADRs, unblocks the gateway sqlite
path, and converts the fork's measured weakness (lexical-only) into this
package's structural advantage (three channels, reserved slots, explainable
fusion).

## Decision boundaries

- No LLM anywhere in this item (selector refinement is `0020`, injected).
- No heuristic pruning below the shelf: weak classifiers must not gate recall
  (fork lesson — shipped, then removed).
- Fusion lives in one module shared by all backends; backends only provide
  channel primitives.

## Promotion criteria

Promote after Track A + `0017`/`0018`; the FTS5 schema work should ride the
same migration wave as `0012`/`0014` where possible (one rebuild).

## Validation ideas

- Identifier/path/error-string queries: exact/keyword channels win reserved
  slots even when vector similarity is mediocre (the fork-informed regression
  scenario).
- Multilingual content: vector channel recalls what keyword misses (the
  fork's ASCII-bound weakness — this package's stack must not share it).
- FTS5-absent build: capability false, substring fallback labeled, results
  still returned.
- Fusion determinism: identical stores → identical ranked lists (stable
  tie-breaks).
- Parity: the conformance suite (`0011`) runs the channel/fusion scenarios on
  all backends.
- Baseline quality fixture: a small judged set (~50 queries) recording
  P@5/R@10 per channel and fused — the package's first measured retrieval
  baseline, kept as a tracked artifact for future tuning.

## Non-goals

- No reranker models, no learned fusion weights (measure first).
- No query expansion via LLM.
- No changes to `query_text` semantics.

## Guidance for future agents

Build the judged baseline fixture FIRST and keep it in the repo; every future
retrieval change must show its P@/R@ delta against it. Honest measurement is
the difference between tuning and superstition.


## Completion report (2026-07-20)

Shipped: channels.py exact/keyword/vector channels + FTS5 lexical reach + orientation channel; reserved slots; CHANNEL_ORDER; vectorless degradation labeled at the channel.
