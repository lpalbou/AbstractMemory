# One graph surface per mind: connectors, the LanceDB connector, the plane store imported through the abstraction

Created: 2026-10-27 ([ADR 0003](../../../adr/0003-one-graph-ledger-provenance-and-revisions.md) decisions 2-3).
Rewritten 2026-10-27 after the operator's decision (report decision 2: "we should have a graph, we should define the
key operations we want on it, and then we only manipulate the graph through those abstractions [...] if we need to
change db, we only have to rewrite the connectors").
Track: `knowledge_graph_convergence` · Priority: High · Status: Planned, unblocked (first slice S8 landed on
`feat/memory-graph-provenance`: the connector protocol, the conformance suite, the LanceDB connector)

## Summary
`MemoryGraph` is the only manipulation surface of a mind; every database is a connector behind it
(`abstractmemory.graph.backend`). SQLite is the default connector for a plane and an entity home. The LanceDB
connector is implemented and held to the same conformance suite. The existing LanceDB plane store enters the plane's
mind through `import` revisions (never a file copy), and the gateway's plane default becomes the SQLite connector.

## Why
Three stores per account today (audit 2026-10-27). The graph's daily operations (revisions, history, sources,
as-of reads, closes) need one transaction across tables and ordered structural reads; the measured comparison
(report decision 2, 200k rows) is decisive for the default: one revision 1.07 ms in one SQLite transaction vs 88 ms
over four LanceDB tables with no atomicity; latest-100 in a scope 0.73 ms vs 16.7 s. The operator's rule keeps the
choice reversible: a different database is a different connector.

## Scope
In:
- S8 (landed): the `GraphBackend` / `GraphTx` Protocols and their invariants; the registry; the SQLite and in-memory
  connectors declared as implementations; the LanceDB connector (`graph/lancedb_backend.py`); the conformance suite
  (`tests/test_graph_conformance.py`) over every connector; `bench_graph.py --backend lancedb`.
- Next: the importer of an existing LanceDB plane store into the plane's SQLite mind THROUGH `MemoryGraph`: `import`
  revisions (ids kept; provenance from `Provenance.from_legacy` on each row's flat provenance, a synthetic run id never
  becoming a ref; rows with no ground carried by the import run's artifact, report decision 8), resumable by
  revision id; then the gateway's plane default switches to the SQLite connector (its item).
Out: the notebook projection (AbstractNote 0037); a LanceDB vector index beside the SQLite truth (report decision 2,
option B: a later item, behind the same `MemoryGraph` surface).

## What the LanceDB connector cannot promise (strict xfails in the conformance suite)
- Writers of one mind in TWO PROCESSES are not serialized (no cross-table transaction, no shared lock): two
  processes can allocate the same seq (`test_two_processes_write_one_mind[lancedb]`).
- A crash in the middle of a commit leaves the rows of an unapplied revision visible to readers until `repair()`
  re-derives the projection from the log (`test_lancedb_a_crash_mid_projection_is_invisible_before_repair`).
Within one process every other invariant holds (staged transaction: a failing revision writes nothing; log-first
commit; serialized writers; the feed shows applied revisions only).

## Measured (bench_graph.py, 20k assertions written through MemoryGraph, no embedder, same machine)
`bench_graph.py --size 20000 --repeat 50 --backend {sqlite|lancedb}` (4000 revisions, 399 closes; median ms):

| | SQLite connector | LanceDB connector |
|---|---:|---:|
| build (revisions/s) | 1262 | 2 |
| on disk | 44 MB | 1830 MB (every commit a table version; `optimize()` keeps old versions 7 days) |
| `derived_from_source(step)` | 0.048 | 115 |
| `derived_from_source(run)`, 128 rows | 0.709 | 1357 |
| `sources_of` | 0.044 | 110 |
| `sources_of`, transitive | 0.097 | 177 |
| `history` | 0.020 | 74 |
| `revisions(limit=100)` | 5.2 | 18 |
| a replayed revision | 0.136 | 274 |

Every LanceDB commit is several table versions (log, triples, history, provenance, the applied mark) and every keyed
read takes all matches (LanceDB 0.30 drops rows when a query limit meets a compound filter over a scalar index: 233
of 10,848 lookups in the first 20k run, which is how the connector found it) and counts them. The numbers confirm the
default: SQLite for the graph; LanceDB where its strengths are wanted (vectors at scale, multimodal embeddings),
behind the same surface.

## Dependencies
0056 (landed). The gateway item for the default switch.

## Validation
The conformance suite on every connector (SQLite and in-memory green; LanceDB green but for the two strict xfails
above); an imported plane store answers the same `TripleQuery` set and replays to the same mind.
