# Proposed: Embedding-space integrity manifest and shared canonical text

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: High
- Components: embeddings, new canonical_text module, backends, manifest storage, tests

## ADR status

- Governing ADRs: AbstractFramework `0026-truncation-policy-and-contract.md`
- ADR impact: None

## Context

Embedding-space integrity is currently unmanaged:

- No embedding model id or dimension is persisted anywhere; swapping the
  gateway's embedding model silently mixes embedding spaces.
- `_cosine` silently truncates on dimension mismatch
  (`in_memory_store.py:42`, `n = min(len(a), len(b))`) — verified:
  `cosine([1,0,0,0],[1,0]) == 1.0`. Confident garbage with no error. LanceDB
  raises on the same input (parity divergence in failure mode; the silent one
  is the dangerous one).
- Rows added while the embedder was unavailable have no vector and are
  silently invisible to semantic search — no `#FALLBACK`. The gateway makes
  this likely: its embedder builder swallows every exception and returns None.
- `_canonical_text` (the embedding input) is TRIPLICATED across
  `in_memory_store.py:12-35`, `sqlite_store.py:13-36`, `lancedb_store.py:57-86`.
  Any uneven edit silently forks the embedding space between backends.

## Current code reality

See citations above; also `0011` divergence 5 (NaN handling) interacts with
this item — the cosine fix lands there, the manifest here.

## Problem or opportunity

Silent cross-space similarity is the least debuggable failure in the package:
a model swap produces plausible-looking wrong memories with no error anywhere.
Every retrieval item (`0019`, `0020`) builds on embeddings being trustworthy.

## Proposed direction

1. One shared `canonical_text.py` module with a versioned function
   (`CANONICAL_TEXT_VERSION = 1`), used by all backends; golden tests pin its
   output (it is a persisted embedding input — changes are migrations, not
   refactors).
2. `EmbeddingManifest` persisted per store (SQLite: a manifest table; LanceDB:
   a manifest table in the same db; in-memory: in-object):
   `{model_id, dimension, canonical_text_version, created_at}`. Written on
   first embedded add; validated on open and on every query with a vector:
   - dimension mismatch → error (never truncate);
   - model_id mismatch → error with remediation hint (re-embed or override);
   - callers can read the manifest via the capabilities/stats surface.
3. Embedder identity: extend the `TextEmbedder` protocol with an optional
   `describe() -> {model_id, dimension}` (defaulted via a probe embed when
   absent, `#FALLBACK`-labeled). The gateway's embedder adapter should
   populate it from its embeddings config.
4. Vectorless-row visibility: semantic queries report how many candidate rows
   were skipped for missing vectors (a warning on the result path /
   reconstruction trace once `0020` lands), labeled `#FALLBACK`. A
   `backfill_vectors(batch_size=...)` helper re-embeds rows missing vectors or
   carrying a stale `canonical_text_version` — bounded, resumable, explicit.
5. Batch discipline for the gateway HTTP embedder: chunk unbounded batch
   embeds (`embeddings.py:44-52` sends one unbounded POST today) with a
   configurable batch size.

## Why it might matter

The fork ran FTS-only and still hit retrieval-precision walls; embeddings are
this package's structural advantage — but only if the embedding space is a
managed invariant rather than an accident of gateway uptime and model config.

## Decision boundaries

- The manifest is per-store, not per-row (one embedding space per store).
  Multi-space stores are out of scope; a second space means a second store.
- Re-embedding is explicit (helper/host-invoked), never automatic on open.
- This item owns integrity; retrieval quality (fusion, thresholds) is `0019`.

## Promotion criteria

Promote with the wave; must land inside the `0012` schema wave (manifest
table + fixed-size vector column need the dimension) — one migration, not two.

## Validation ideas

- Manifest written on first embedded add; open with a different-dimension
  embedder fails with an actionable error on all backends.
- Dimension-mismatch query vector raises (no silent truncation) — regression
  test from `0011`.
- Vectorless rows: semantic query reports skip counts; backfill makes them
  retrievable; stale-version rows re-embedded by backfill.
- Golden canonical-text tests pass identically for all backends (single
  module).
- Gateway embedder chunking: large batch split into N requests, order
  preserved.

## Non-goals

- No multi-model/multi-space support.
- No automatic model migration on mismatch (explicit backfill only).
- No embedding cache layer (possible later optimization; measure first).

## Guidance for future agents

Treat `canonical_text` changes like schema changes: bump the version, keep the
old renderer callable for verification, and route re-embeds through the
backfill helper.

## Status addendum: CORE IMPLEMENTED (2026-07-10, consensus plan item 3 — M1/M1b)

The manifest shipped as the **embedding pin** (`embedding_pin.py` — shared
rules; per-store storage: SQLite `{table}_meta` sidecar / in-object), under
the 1-gateway-N-runtimes consensus plan: creation-time pinning (birth
choice, `embedding_pin=` store kwarg + `build_pin` export), first-write
pinning demoted to the labeled `#FALLBACK` for pre-existing homes,
model-mismatch refusal at open, dimension-mismatch refusal at write (zero
rows) and at read (the vector channel labels the degradation — the silent
min-prefix cosine this item documented is REMOVED). Re-embedding shipped as
`reembed_home` (M1b): all-or-nothing atomic swap (`replace_vectors`), pin
updated last, mid-pass-writer count guard, journaled bookkeeping act,
truth untouched, vectorless rows backfilled. Guards:
`tests/test_embedding_pin.py`. Deliberately NOT built from this item's
original sketch: `describe()` probe-embeds (the pin + measured dimensions
suffice), per-query skip-count reporting (the channel's vectorless
`#FALLBACK` already labels it), and LanceDB coverage (homes are SQLite;
LanceDB keeps its own raise-on-mismatch behavior).
