# AbstractMemory (WIP)

`abstractmemory/` is the semantic long-term memory substrate for AbstractFramework.

Design goals (MVP):
- Triples-first temporal assertions (append-only)
- Explicit provenance (`span_id`/`artifact_id` references)
- Deterministic, inspectable query APIs (pattern/time/scope)
- Optional semantic retrieval via embeddings (vector search)

The primary representation remains a temporal semantic graph (triples). Embeddings are treated as
an accelerator for retrieval (and later multimodal indexing), not as the meaning itself.
