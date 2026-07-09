# FAQ

## Where should I start?

- Installation + first examples: [`getting-started.md`](getting-started.md)
- Concepts and invariants: [`architecture.md`](architecture.md)
- The cognitive model: [`memory-system.md`](memory-system.md)
- Public API contracts: [`api.md`](api.md)
- Store behavior: [`stores.md`](stores.md)

## What is AbstractMemory (and what is it not)?

AbstractMemory is a Python library for durable, append-only agent memory: temporal, provenance-aware triple assertions with deterministic structured queries and optional vector retrieval (layer 1), plus a `MemorySystem` facade that composes them with an append-only journal into a usage-weighted memory graph — typed records, stimulus-driven reconstruction, attention, identity, valence, diary conventions, consolidation, and a replay stream (layer 2).

It is **not**:

- A knowledge-graph reasoner (no inference, joins, or ontologies).
- A text extraction/summarization library (no LLM calls anywhere in the package).
- A runtime or an agent host: it owns memory mechanics; hosts decide when to recall, what enters prompts, and who may write.

## How does AbstractMemory fit into AbstractFramework?

- **AbstractMemory**: the memory substrate (this package) — no dependency on the other packages.
- **AbstractRuntime**: orchestrates when memory is consulted and committed (per turn) and owns host-side surfaces such as the diary book.
- **AbstractGateway**: hosts entity homes, serves the replay stream over HTTP, and can provide embeddings via `AbstractGatewayTextEmbedder`.

Related projects: `https://github.com/lpalbou/abstractframework`, `https://github.com/lpalbou/abstractcore`, `https://github.com/lpalbou/abstractruntime`.

## What is the core data model?

At layer 1, `TripleAssertion` is the single write primitive: `(subject, predicate, object)` plus `scope`, `owner_id`, time fields, and metadata dicts (`provenance`, `attributes`). Stores stamp `assertion_id` on every query result. At layer 2, typed memory records are encoded over the same substrate: one digest assertion per record (the record's graph id is the assertion's subject) plus one assertion per edge.

## Why are `subject` / `predicate` / `object` lowercased?

Canonicalization (trim + lowercase) is part of the matching contract: it prevents missed matches when the same term arrives with different casing or whitespace. To preserve original casing, store it separately (for example `attributes={"raw_subject": "Alice"}`), or set `attributes={"literal": True}` to keep the `object` case-sensitive — typed records use this for their digest text.

## Does AbstractMemory support updates or deletes?

There is no update or delete API, by design:

- At layer 1, represent changes by adding a new assertion with fresh provenance.
- At layer 2, belief revision is a closure record (`close_record` / `close_assertions`: retract or supersede with replacements) — the old record leaves ranked retrieval but stays in the store and in history. Visibility can also be withdrawn per scope with a `hidden` binding and restored with `indexed`.
- Forgetting is decay of retrieval strength plus closures and silencing. The substrate is lossless; there is no compaction.

## What do `scope` and `owner_id` mean?

They partition data. `scope` is a free-form label (lowercased); `owner_id` is an identifier within it. Common conventions: `"session"` + session id, `"run"` + run id, `"global"` for shared memory, and the entity-home ladder `"self"` / `"diary"` / `"life"` + entity id. At layer 2, `"global"` is a broad scope by default: searching it in `reconstruct` requires an explicit `escalation_reason`.

## How are time filters evaluated?

Time fields are stored and compared as **strings**: `since`/`until` compare `observed_at` (`>= since`, `<= until`); `active_at` intersects the `(valid_from, valid_until)` window with an exclusive end. Use RFC-3339/ISO-8601 UTC strings (e.g. `2026-01-01T00:00:00+00:00`) to keep comparisons predictable.

## Which store should I use?

- `InMemoryTripleStore`: dependency-free, volatile — tests, development, ephemeral agents.
- `SQLiteTripleStore`: dependency-free persistent single file with structured queries **and** native vector search (construct with an embedder) — the recommended durable default; a store+journal pair can share one file.
- `LanceDBTripleStore`: persistent vector-capable backend on LanceDB's storage format (optional dependency).

See [`stores.md`](stores.md) for details.

## How do I do semantic search?

Vector search is opt-in and works the same across all three stores:

- `query_text=...` requires a configured embedder (a `ValueError` is raised otherwise; there is no keyword fallback).
- `query_vector=...` bypasses embedding generation.
- Only rows written with vectors participate; `min_score` applies a cosine threshold; results carry `attributes["_retrieval"]`.

## Are queries deterministic?

Structured queries: yes — filters are explicit, and non-semantic results are ordered by `observed_at` then limited. Vector queries rank by similarity; ties are not specified. Layer-2 reconstruction is deterministic given the same journal state: every result carries `as_of_seq`, and anchoring `Stimulus(as_of=...)` reproduces it.

## Do reads strengthen memory?

No. Reconstruction, inspection, replay, the structural report, and the entity card are pure reads. `commit_selection` is the only strengthening path, and it deposits only for records admitted by the stimulus (records rendered from the identity core or from short-term standing are presence, not use). See [`memory-system.md`](memory-system.md).

## What gets embedded for vector search?

On `add(...)`, vector-capable stores embed each assertion's canonical text (`canonical_text(assertion)`): the triple terms plus selected attributes, with digest-bearing records rendered around their digest text. On `query(...)` with `query_text=...`, the query string is embedded and ranked against stored vectors. Edge assertions are never embedded.

## What embedding interface do I need to implement?

The `TextEmbedder` protocol: `embed_texts(texts: Sequence[str]) -> list[list[float]]`. Two implementations ship with the package: `OpenAICompatTextEmbedder` (any OpenAI-compatible `/embeddings` endpoint, e.g. LM Studio or Ollama) and `AbstractGatewayTextEmbedder` (an AbstractGateway deployment; default path `/api/gateway/embeddings`, Bearer auth via `auth_token`).

## Where does vector retrieval metadata appear?

On results, stores attach retrieval metadata to `TripleAssertion.attributes["_retrieval"]`: cosine `score` + `metric` (LanceDB additionally reports `distance`).

## How do I inspect the data on disk?

- SQLite: open the file with any SQLite client. The assertions table includes the canonical triple columns plus `provenance_json`, `attributes_json`, `text`, and `embedding`; the journal's sidecar tables live in the same file when you pass the same path to `SQLiteJournal`.
- LanceDB: open the `uri` path with LanceDB and inspect the table.
- For a whole entity home, prefer the read-only workflow in [`operator.md`](operator.md) — identity core, wake reasons, gradation, replay stream, and the identity card, all pure reads.

## Can I replay the past?

Yes. The journal assigns a monotonic `seq` to every record; `export_replay(since_seq=..., until_seq=...)` streams verbatim history, and `as_of`/`at_seq` parameters on reads (`reconstruct`, `gradation`, `activation`, `entity_card`) fold state to any anchor. One documented limit: triple-store truth is read current (assertions have no seq axis), so store rows added after an anchor still enter candidate gathering; replay is exact while store contents are unchanged.
