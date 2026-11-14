---
name: abstractmemory
description: Use AbstractMemory's Python APIs for scoped, provenance-aware memory, deterministic replay and read-only inspection.
license: MIT
compatibility: Python 3.10+. Semantic retrieval needs an explicitly configured embedder; LanceDB and numpy are optional extras.
metadata:
  package-version: "0.5.2"
---

# Use AbstractMemory

Use Python 3.10+ and `python -m pip install AbstractMemory`. Import `abstractmemory`;
`[fast]` adds numpy for SQLite vector scoring and `[lancedb]` adds that optional backend.
Verify the installed distribution and its API before opening a home:

```python
from importlib.metadata import version
from abstractmemory import MemorySystem
print(version("AbstractMemory"))
assert callable(MemorySystem)
```

AbstractMemory does not run an LLM or supply an embedding model. Configure an embedder
before semantic queries; `query_text` without one raises rather than doing keyword search.

Choose the surface before writing:

- Plain scoped triples: `InMemoryTripleStore`, `SQLiteTripleStore` or `LanceDBTripleStore`,
  with `TripleAssertion` and `TripleQuery`.
- A memory system: `MemorySystem` with a store and journal. Formation is separate from
  selected use; reconstruction is a pure read, `commit_selection` records what was used.
- A mind's graph: `abstractmemory.graph.MemoryGraph`. Apply atomic, idempotent `Revision`s
  with grounded `SourceRef`/`Provenance`; missing provenance raises `ProvenanceRequired`.
  Never edit the backing database directly.

For a new integration, first reproduce this isolated triples example:

```python
from abstractmemory import InMemoryTripleStore, TripleAssertion, TripleQuery
store = InMemoryTripleStore()
store.add([TripleAssertion(subject="Ada", predicate="uses", object="Python",
                          scope="session", owner_id="demo")])
hits = store.query(TripleQuery(subject="ada", scope="session", owner_id="demo"))
assert len(hits) == 1
```

Then choose a persistent store, explicit scope/owner pairs and a real provenance source.
Use stable idempotency keys for retried formations/revisions. Inspect the resulting record
and journal before committing selected use. Anchor historical reads at `as_of`/`at_seq`;
the journal's sequence is the replay axis. Do not invent run or artifact provenance.

Updates append assertions or closures; they do not delete history. Title/summary rewrites
retain earlier versions. A formation retry does not update an existing assertion's attributes.
Read-only inspection, reconstruction, replay and entity cards deposit nothing.

Diary prose belongs in the book. Replay projections describe the act; private projections
must stay content-free. A `resolves` claim alone is not a confirmed resolution: inspect
`resolves_status`; target graph id/title may be absent. Existing projections are not
backfilled by upgrading. Pending authored fields need a host author and a home opened with
`MemorySystem(task_queue=True)`; do not fill them with invented text. Preserve labelled
`#FALLBACK` warnings and handle invalid input errors explicitly.

Full contracts: `docs/api.md`, `docs/memory-system.md`, `docs/stores.md` and
`docs/operator.md`. Use the operator guide for an existing entity home; start with reads.
