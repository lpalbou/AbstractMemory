# AbstractMemory — Architecture (Early / WIP)

> Updated: 2026-01-12

## Purpose
AbstractMemory is responsible for **semantic long-term memory**: representing knowledge as
structured, temporal assertions that can be queried and evolved over time.

It is intentionally separate from:
- **AbstractRuntime**: durable execution + provenance-first spans/notes/artifacts
- **AbstractCore**: LLM/tool access + text processing (summarization/extraction)

## Core representation
The base primitive is an **append-only temporal triple assertion**:

```
subject  --predicate-->  object
```

With metadata:
- `scope`: `run|session|global` (who “owns” this memory)
- `observed_at`: when the assertion was added/extracted
- optional `valid_from` / `valid_until`: when the assertion is considered true
- optional `confidence` and other attributes
- `provenance`: explicit pointers to runtime artifacts/spans (e.g. `span_id`)

## Why append-only?
Human memory is not static storage: retrieval triggers reconsolidation and updates.
Append-only assertions make updates explicit and auditable: “new knowledge” becomes new records
with time and provenance, rather than destructive rewrites.

## MVP storage
The MVP store is SQLite-backed (stdlib `sqlite3`) for:
- portability (single file)
- speed (indexes + simple SQL)
- inspectability (open with any SQLite client)

Future stores can implement the same interface (Postgres, remote, etc.).

## Planned integration points
- Ingestion: extract triples/JSON-LD from runtime spans/notes via `abstractcore.processing.BasicExtractor`
- Query: provide provenance-backed “memory packets” to workflows/agents
- Mapping: rebuild Active Memory blocks under `_limits.max_input_tokens`

