# Proposed: Graph backend decision record — Memgraph rejected, promotion criteria for embedded alternatives

## Metadata

- Created: 2026-07-05
- Status: Proposed (decision record; no implementation work)
- Completed: N/A
- Priority: Low
- Components: none (documentation of an investigated decision + re-evaluation criteria)

## ADR status

- Governing ADRs: AbstractFramework `0029-permissive-dependency-and-licensing-policy.md`
- ADR impact: None (planned `003`'s "no graph database dependency" non-goal is
  CONFIRMED by this record)

## Context

The owner asked whether AbstractMemory should leverage Memgraph, suspecting
persistence issues. A dedicated adversarial investigation (2026-07-05, web
research + benchmarks over the actual SQLite schema) reached a decision-grade
verdict. This record preserves it so the question is not re-litigated without
new evidence.

## Current code reality

- Bounded traversal (planned 003) remains the committed direction, over
  existing backends.
- Benchmarks on the current SQLite schema: bounded BFS at 1M triples runs in
  2–25 ms once an `(object, predicate, subject)`-shaped reverse index is
  added (the one actionable schema gap — folded into planned 003 guidance via
  `0022`); a Python frontier loop beats recursive CTEs by 20–100x at this
  scale.

## Problem or opportunity

Verdict: REJECT Memgraph for AbstractMemory. Three independent reasons, each
sufficient:

1. Deployment model: Memgraph has no embedded mode — daemon/Docker only
   (Docker-only on macOS). The framework is local-first with in-process
   defaults; a mandatory daemon for the memory substrate is disqualifying.
2. Licensing: Memgraph Community is BSL-licensed (source-available, not open
   source); bundling/redistribution inside a permissively-licensed pip
   package conflicts with the framework's licensing policy (ADR 0029).
3. Persistence (the owner's suspicion — CONFIRMED, though not the decisive
   factor): in-memory-first architecture with snapshot + WAL persistence
   whose default durability window is wide (WAL fsync at large transaction
   intervals by default), a documented Docker-volume data-loss footgun, and
   recovery quirks around partial snapshots. Real durability requires
   non-default tuning and RAM sized to the whole graph.

Embedded alternatives, ranked (for the future, none needed now):

1. LadybugDB — the actively-maintained MIT-licensed fork of Kuzu (Kuzu Inc.
   shut down in 2025 and archived the project; maintenance risk was the
   lesson). Embedded, columnar, Cypher-ish. The candidate IF a real graph
   backend is ever justified.
2. oxigraph — embedded RDF/SPARQL (Rust + Python), semantically aligned with
   the triple model but a heavier query-language commitment.
3. DuckDB PGQ — experimental property-graph extension; not mature enough.

## Proposed direction

No implementation. Keep planned 003's non-goal. Fold two concrete findings
into implementation guidance elsewhere (done): the reverse-traversal index
and the frontier-loop-over-CTE preference (`0022`).

## Why it might matter

Prevents re-investigation churn and anchors the graph question to measurable
promotion criteria instead of technology curiosity.

## Promotion criteria

Re-evaluate an EMBEDDED graph backend (LadybugDB first) behind the
capabilities API (`graph_walk="native"`) only when ALL of:

1. a real consumer workload needs variable-length path queries, dense
   subgraph analytics, or graph algorithms that bounded BFS cannot express;
2. measured traversal performance over the tuned existing backends fails a
   concrete latency budget at a real dataset size (>5–10M edges sustained);
3. the candidate library is maintained, permissively licensed, and embedded
   (in-process, pip-installable, no daemon).

Memgraph specifically: reconsider only if it ships a supported embedded
in-process mode under a permissive license — both are currently structural,
not roadmap, gaps.

## Validation ideas

None (decision record). The traversal benchmarks that ground it should be
reproduced when planned 003 is implemented (its C-level validation).

## Non-goals

- No graph database dependency in the memory system v1 wave.
- No daemon-based backend ever becoming the default (local-first).

## Guidance for future agents

If asked about graph databases for AbstractMemory, read this record first and
check the promotion criteria against current evidence. New enthusiasm is not
new evidence.
