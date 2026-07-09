# Proposed: Gateway Memory Install And Configuration Boundary

## Metadata
- Created: 2026-05-08
- Status: Proposed
- Completed: N/A

## Context

AbstractMemory owns append-only, temporal, provenance-aware triple stores and query contracts.
Gateway-hosted agents can use it for persistent KG memory, but Memory should not own LLM provider
selection or Gateway deployment configuration.

## Current Code Reality

- Memory base install is dependency-light.
- `AbstractMemory[lancedb]` is optional.
- `AbstractMemory[apple]` and `AbstractMemory[gpu]` are no-op compatibility aliases.
- `AbstractMemory[all-apple]` and `AbstractMemory[all-gpu]` install the current Memory-owned
  vector-capable optional backend, LanceDB.
- Memory provides an `AbstractGatewayTextEmbedder` that calls Gateway embeddings over HTTP.
- Memory has multiple store modes:
  - `InMemoryTripleStore`: dependency-free and volatile;
  - `SQLiteTripleStore`: dependency-free, persistent, structured-query only;
  - `LanceDBTripleStore`: optional dependency, persistent, vector-capable.
- Runtime's `memory_kg_*` handlers require a store with `add(...)` and `query(...)`; they do not
  intrinsically require LanceDB.
- Current Gateway KG workflow setup hardcodes `LanceDBTripleStore` for bundles that use
  `memory_kg_*` effects.
- Current Gateway `/kg/query` also hardcodes `LanceDBTripleStore`.
- Gateway owns embedding provider/model configuration through its own env/config and
  `/api/gateway/embeddings`.

## Problem

The design question is not "does memory require LanceDB?" The answer is no at the AbstractMemory and
Runtime contract level. Memory is a triple/query library, and Runtime can execute memory effects
against any store that satisfies the store contract.

The current implementation question is different: Gateway currently chooses LanceDB directly. That
means plain `abstractmemory` is not sufficient for today's Gateway KG bundle path or current Gateway
`/kg/query` route, because those paths import and construct `LanceDBTripleStore`.

There is also a recall-mode risk. LanceDB is the current durable vector-capable backend, while SQLite
is durable but structured-query only. Semantic `query_text` recall should fail clearly when vector
recall is not configured; it should not silently become keyword search.

Future image memory adds another distinction:

- storing images should not require LanceDB; image/audio/media bytes should live in Runtime/Gateway
  artifact storage, with Memory triples pointing to artifact ids, hashes, captions, detected
  entities, and provenance;
- querying images semantically may require vectors, but LanceDB is only one possible vector backend;
- current AbstractMemory only implements durable vector retrieval through LanceDB, so it is the
  practical v0 choice for persistent text/image embedding search unless another vector backend is
  added.

## Proposed Direction

Keep Memory package profiles:

- `AbstractMemory`: lightweight store/model contracts.
- `AbstractMemory[lancedb]`: vector-capable LanceDB store.
- `AbstractMemory[all]`: Memory-owned optional storage backends, currently LanceDB.
- `AbstractMemory[apple]` / `AbstractMemory[gpu]`: no-op compatibility aliases because Memory has
  no hardware engine.
- `AbstractMemory[all-apple]` / `AbstractMemory[all-gpu]`: install Memory-owned optional storage
  backends relevant to full native Gateway deployments, currently LanceDB.

Add Gateway-side profiles:

- `abstractgateway[memory]`: persistent Gateway memory profile. It may depend on
  `abstractmemory[lancedb]` for the current v0 implementation, but it should be described as
  "Gateway persistent/vector memory" rather than "Memory requires LanceDB."
- consider including `abstractgateway[memory]` in `abstractgateway[server]` if persistent memory and
  semantic recall are part of the default Gateway value proposition.

Memory should not add real Apple/GPU-specific storage dependencies unless it later owns such
backends. The current `apple`/`gpu` aliases are compatibility-only, and `all-*` means "all
Memory-owned optional storage backends for that deployment profile."

Gateway should eventually stop hardcoding `LanceDBTripleStore` in request/bundle paths and instead
resolve a configured memory store backend with explicit capabilities. The immediate default can still
be LanceDB because it is the only current durable vector-capable backend.

## Configuration Boundary

Memory owns:

- triple assertion model;
- query model;
- store implementations;
- embedder protocol.

Gateway owns:

- where the Gateway memory store lives;
- which Gateway memory store backend is selected;
- embedding provider/model;
- memory KG workflow preflight;
- auth to the embeddings endpoint;
- capability/readiness reporting.

Semantics owns:

- predicate/entity vocabulary;
- schema validation.

Runtime owns:

- `memory_kg_*` effect semantics;
- the host-provided store/effect handler bridge;
- warnings when a configured store is volatile or lacks requested query capabilities.

## LanceDB Requirement Answer

LanceDB is not intrinsically required for AbstractMemory.

It is currently required for Gateway's implemented KG memory path because Gateway hardcodes
`LanceDBTripleStore` in bundle hosting and KG query code. It is also currently the only durable
vector-capable AbstractMemory backend, so it is the practical v0 requirement for persistent semantic
recall over text embeddings and, later, image embeddings.

LanceDB is not required for:

- the base `abstractmemory` package;
- triple assertion models;
- structured KG queries;
- SQLite-backed persistent structured memory;
- storing image/media artifacts by reference.

LanceDB, or another future vector backend, is required when the feature promise is durable semantic
retrieval over embeddings. For image memory, the durable bytes should remain artifact-backed; the
vector store should hold embeddings and metadata that point back to artifact ids and KG assertions.

## Pending Changes Guidance

Memory should remain lightweight. Do not change its base install to require LanceDB.

Related pending changes:

- Root and Gateway docs may say the current Gateway persistent/vector memory profile installs
  `abstractmemory[lancedb]`.
- Do not say "AbstractMemory requires LanceDB" without qualifying the Gateway implementation or
  vector-retrieval requirement.
- Root `abstractframework` extras should include the Gateway memory profile when default Gateway
  installs promise persistent semantic memory.
- Gateway should add memory install/profile decisions, store backend configuration, and preflight
  readiness checks.
- Runtime's in-memory warning should eventually point to "a durable store such as SQLite or
  LanceDB" for persistence, and only mention LanceDB when vector recall is requested.

## Promotion Criteria

Promote when Gateway profile work begins or when a Gateway bundle using `memory_kg_*` is expected
to work in default server installs.

## Validation Ideas

- Gateway starts without Memory installed and reports memory unavailable with install hints.
- Gateway `memory` profile imports the configured store backend and reports its capabilities.
- Gateway's v0 default memory backend can still be LanceDB for persistent vector recall.
- Runtime memory handlers work with a fake store exposing only `add(...)` and `query(...)`.
- SQLite-backed structured KG queries work without embeddings or LanceDB.
- Semantic `query_text` fails clearly when embeddings are disabled or missing.
- Semantic `query_text` fails clearly when the configured store is structured-only.
- `AbstractGatewayTextEmbedder` works against a stub Gateway embeddings endpoint.
- Image/media memory stores artifact refs and metadata without requiring vector storage.
- Image/media semantic retrieval is gated behind an explicit vector-capable backend.
