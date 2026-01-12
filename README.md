# AbstractMemory (WIP)

`abstractmemory/` is the semantic long-term memory substrate for AbstractFramework.

Design goals (MVP):
- Triples-first temporal assertions (append-only)
- Explicit provenance (`span_id`/`artifact_id` references)
- Deterministic, inspectable query APIs (pattern/time/scope)

This package intentionally avoids embedding/vector search at the core layer. Embeddings may be
added later as an optional retrieval accelerator, but the primary representation is a temporal
semantic graph that can be audited and evolved over time.

