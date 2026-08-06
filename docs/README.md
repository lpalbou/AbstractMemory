# AbstractMemory Documentation

AbstractMemory is a Python library for durable, append-only agent memory: temporal, provenance-aware triple assertions with deterministic queries and optional vector retrieval (layer 1), plus a `MemorySystem` facade that composes them with an append-only journal into a usage-weighted memory graph — reconstruction, attention, identity, valence, diary, consolidation, and replay (layer 2).

## Start here

- Getting started: [`getting-started.md`](getting-started.md) — install, first triples, first `MemorySystem` session.
- Architecture: [`architecture.md`](architecture.md) — the two-layer model, the journal as the time axis, the reconstruction union, and the package's invariants.
- API reference: [`api.md`](api.md) — every public export, grouped by surface, with signatures.

## Topic deep dives

- The memory system: [`memory-system.md`](memory-system.md) — the cognitive model: how working memory emerges from use, the two access counts, valence and gradation, identity cores, diary conventions, and sleep/consolidation.
- Stores/backends: [`stores.md`](stores.md) — behavior and persistence details for the in-memory, SQLite, and LanceDB stores.
- Operator guide: [`operator.md`](operator.md) — observing and verifying a summoned entity's memory home, read-only.

## Reference

- FAQ: [`faq.md`](faq.md) — common questions and current limits.
- Troubleshooting: [`troubleshooting.md`](troubleshooting.md) — symptom-oriented fixes for setup, retrieval, embedding-space, durability, and maintenance problems.
- Development: [`development.md`](development.md) — local setup, tests, and the design backlog.

## Related

- Package overview: [`README.md`](../README.md)
- Changelog: [`CHANGELOG.md`](../CHANGELOG.md)
- Contributing: [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- Code of conduct: [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md)
- Security: [`SECURITY.md`](../SECURITY.md)
- License: [`LICENSE`](../LICENSE)
- Acknowledgments: [`ACKNOWLEDGMENTS.md`](../ACKNOWLEDGMENTS.md)
