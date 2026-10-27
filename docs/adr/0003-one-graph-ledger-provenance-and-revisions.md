# ADR 0003: One semantic temporal graph, every memory tied to the ledger, every change a revision

Status: Accepted (operator goal stated 2026-10-27; this ADR gives it its shape). Aspirational for existing
consumers: AbstractNote's parallel graph and the gateway's separate plane store converge here through the
convergence track (backlog 0050-0058).
Amended 2026-10-27 (operator rulings on `abstractframework/untracked/memory-transition/report.md`): decisions 2 and
13, visibility is strict ownership (report decision 5, taken); decision 3, the home store, is PENDING (report
decision 2, not taken).

## Context

ADR 0002 ruled that AbstractMemory owns the semantic temporal memory graph and all of its processing. The audit of
2026-10-27 (`abstractframework/untracked/memory-transition/audit/`) measured what that ruling has to close:

- **Three graphs per account.** A person's plane holds a LanceDB knowledge-graph store (`<plane>/abstractmemory/kg`,
  the gateway's `/api/gateway/kg/query`), the notebook's own SQLite note index plus a private AbstractMemory
  `SQLiteTripleStore` it opens itself (`abstractnote/store/kg.py`), and each summoned entity's home graph
  (`entities/<slug>/memory.sqlite3`). The notebook's projection into AbstractMemory is partial (9 of 20 revision
  ops) and never read; the LanceDB store lacks `close_assertion`, id idempotency and a stable schema (an `active_at`
  query errors when the first write had no `valid_until`).
- **No memory points back to the ledger.** AbstractRuntime keeps the durable truth of what happened: runs
  (`run_id`), ledger records (`(run_id, seq)` rows; `step_id` per effect), artifacts (`artifact_id`, the `span_id`
  of root ADR 0009), messages (`message_id`, optional), the event inbox (`event_id`) and the hash-chained entity
  diary (`entry_id`). Of 21,951 triples in the operator's notebook graph, none carries a run id; entity memories
  carry `run_id`/`turn_id` and a `payload_ref` artifact but no ledger row address; AbstractMemory's own passes
  (sleep, world model, mining) write records whose provenance is `{source, actor}` at best; closures are written
  with no provenance at all, and `close_assertion` is an unjournaled in-place update.
- **Temporal validity and revision are not first-class.** A claim's window (`valid_from`/`valid_until`) and the
  journal's closure records (`retract`/`supersede`/`reinterpreted`) are two uncoordinated truths; nothing groups
  the operations of one logical change under one cause; there is no history read, no change feed, no view of what
  the graph held at an earlier record time, and no public way to move an already-closed window (`narrow_assertion`),
  which is why AbstractNote writes the store's private table.
- **Performance will not carry a notebook.** The owner filter `COALESCE(owner_id,'') = ?` defeats the indexes;
  every read selects the embedding column; vectors are JSON text decoded and scored in Python (a vector query over
  50k rows takes 11 s on SQLite); `maintenance_due` reads the whole history each time.

The operator's goal (2026-10-27): AbstractNote stays a thin application that benefits from an advanced semantic
temporal knowledge graph; there is ONE implementation of that graph, serving a person's notebook and the memories
of self-evolving persistent entities (AbstractEntity), who learn, reconsider knowledge over time and write notes
to themselves; and every derived memory is tied to the ledger's messages, events and artifacts, so that (a) memory
is reached quickly and structurally through the graph and (b) the verbatim source of any understanding, or of any
change of understanding, can be reconstructed from the ledger.

## Decision

### A. One graph, several minds

1. **One implementation.** The graph is this package: one schema, one write path, one set of processes
   (identity, claims and revisions, retrieval, self-organisation, ripple). No consumer keeps a graph of its own
   (ADR 0002). The gateway's plane knowledge-graph store, the notebook's note index and projection, and the
   entity's home graph are instances of this one implementation.
2. **A mind is a store; what is in it belongs to its owner.** A *mind* is one graph home: a person's plane
   (`<plane>/abstractmemory/`) or an entity's home (`entities/<slug>/`). Inside a mind, `owner_id` is the OWNERSHIP
   partition (`scope` says what kind of memory it is: the notebook, a session, a run, an entity's
   self/diary/life ladder). Minds stay separate files on purpose: an entity's home is portable ("copying the
   directory moves the entity") and nobody edits a mind from outside; what one mind knows reaches another through
   the gateway, never by sharing a file. Within one plane, the three stores of the audit become one.

   *Amendment 2026-10-27 (operator ruling, report decision 5): visibility is strict ownership, not plane-wide.* A
   person owns their notes and their memory graph; an entity owns its graph; a person CAN read the graphs of the
   entities they own (delegation entity → owner); a person cannot read another person's graph by default (sharing,
   and topic-scoped requests, are future work, not part of this ADR); an administrator stays an administrator. The
   plane is NOT a sharing scope: several owners' memories living in one plane file are not visible to each other
   because of it. Every read surface enforces this (decision 13).
3. **The home store: PENDING the operator's decision** (report decision 2, not taken: "why migrate from lancedb
   to sqlite? lancedb scales more and seems more adequate for multimodal embeddings; we never migrate to migrate").
   As first written: the record of truth of a mind is one SQLite file holding the triples, the journal, the revision
   log and the provenance index, so one logical change commits in one transaction; vector search uses a binary
   float32 column and an in-process matrix cache; LanceDB is an optional vector accelerator; the gateway's plane
   default moves from LanceDB to this home store (backlog 0057). Entity homes are SQLite today and stay so; the open
   question is the PLANE store. Options on the table:
   - (a) as written: SQLite is the plane's home store; the existing LanceDB plane store is imported once.
   - (b) hybrid: SQLite holds the graph, the provenance index and the revision log (the transactional truth); LanceDB
     is kept for vectors and multimodal embeddings over the same ids.
   - (c) LanceDB behind the same `MemoryGraph` interface.
   Facts that bound the choice (audit `untracked/memory-transition/audit/abstractmemory.md` §2.3, §9.1 and finding 8,
   2026-10-27; not opinion): the graph tables (`memg_*`) exist only on SQLite today, because one revision must
   commit triples, closures, history and the provenance index together and only the SQLite store and journal share a
   transaction; `LanceDBTripleStore` has no transactions, no `close_assertion`, no id idempotency (duplicate ids are
   accepted), no embedding pin, no FTS, and a schema inferred from its first batch (an `active_at` query errors when
   that batch had no `valid_until`); its non-vector reads materialise every match and sort in Python (latest-100 of a
   scope: 7.0 s at 50k rows, against 0.6 s on SQLite before backlog 0058); its batch adds are faster (65 vs 381 us
   per row at 50k). The SQLite home work (0056, 0058) stands either way: entity homes use it, and options (a) and
   (b) both keep it as the graph's store. The one-way vector re-encoding of 0.4.0 (CHANGELOG) applies to SQLite
   homes and is unaffected. Memory cost of the SQLite vector path, per process that queries a home (a gateway
   worker, an entity loop): rows x dims x 4 B for the float32 matrix plus about 170 B per row of bookkeeping
   (`store_tuning.py`); 200k rows x 1024 dims = about 850 MB held per process, measured 424 MB at 100k x 1024
   (architect review C2). This figure is an input to the decision.

### B. The units of the graph

4. **Nodes, claims, records.** A node is a subject id: a *thing* in the world (person, project, place, concept...:
   the entity registry of backlog 0050, which generalises the world-model targets) or a *record* of experience
   (episode, note, diary entry, lesson, summary, dream, world-model card: the record kinds of `records.py`). A
   *claim* is a `TripleAssertion` about nodes with a validity window, a confidence and provenance. Everything about
   a node is triples; the triple store stays the substrate so every existing read (channels, spreading,
   reconstruct, the gateway's KG query, the entity replay stream) keeps working.
5. **Three time axes, named.** Every claim and record distinguishes (i) **event time**: `valid_from`/`valid_until`,
   when the stated thing held in the world; (ii) **observation time**: `observed_at`, when the source said it (the
   note's date, the conversation's time); (iii) **record time**: `recorded_at`, when this mind learned it (the
   revision's record time, the journal `seq`). Reads name their axis: `active_at` (event time), `as_of`
   (observation time: "what did the sources up to T say"), `as_recorded` (record time: "what did this mind hold at
   R", the as-received view). A re-dated or re-interpreted memory moves on the first two axes and never on the third.
6. **A revision is the unit of change.** Every change to the graph is one append-only *revision*:
   `{revision_id, scope, owner_id, cause, occurred_at, recorded_at, ops[], provenance, summary}` where `cause` is one
   of `ingest | reinterpret | merge | unmerge | ripple | person | maintenance | import | migration` and `ops` are
   the operations applied together and atomically (assert, close, narrow, and, as the track lands them, entity and
   alias operations). Replaying the revision log into an empty store yields the same graph. A revision is
   idempotent on its id. The in-place `close_assertion` becomes a revision op (`close`) and is journaled with it.
7. **Closures carry their cause and their successor.** A closed window records `kind`
   (`retract | supersede | reinterpreted | narrowed | merged`), the `revision_id` that closed it, the replacement
   ids ("superseded by ..."), and for a ripple the source memory and hop count (ADR 0001). The window on the row and
   the closure record are written by the same op, so `TripleQuery(active_at=...)` and ranked recall agree.
   `narrow_assertion(assertion_id, valid_until)` moves an already-closed window earlier and refuses to widen it; it
   exists only as the `narrow` op of a revision. "Reconsidered on <date>, superseded by <id>" is a read of this
   record, `history(memory_id)`, never a reconstruction.

### C. Provenance is mandatory and typed

8. **Every memory is sourced or derived; never neither.** A write is refused (`ProvenanceRequired`) unless its
   provenance names at least one **ledger source** or at least one **memory it was derived from** whose own
   provenance (transitively) reaches a ledger source. This holds for consumers' writes, for the runtime's effect
   handlers, and for this package's own passes (sleep, world model, mining, ripple, consolidation), which write
   `derived_from` lineage and, when the host runs them as a run, that run's reference.
9. **The source reference is typed and plain.** A `SourceRef` is a dict (no framework import; this package has no
   framework dependency) with `kind` in `run | step | artifact | message | event | diary_entry` and the id fields of
   that kind: `run` needs `run_id`; `step` needs `run_id` and `seq` (the ledger row address) and may carry
   `step_id`; `artifact` needs `artifact_id`; `message` needs `message_id` (and `run_id` when known); `event` needs
   `event_id`; `diary_entry` needs `entry_id`. Any kind may carry `runtime_id` (which ledger: the plane's runtime id
   or the entity home) because entity homes travel. Each ref has one canonical key (`step:<run_id>#<seq>`,
   `artifact:<id>`, ...) and is indexed both ways: "what did this memory come from" and "what was derived from this
   run / step / artifact". `Provenance` carries `sources`, `derived_from` (memory ids), `actor`, `reader` (the
   model that exercised judgement, when one did), `reason`, and free `extra`.
10. **Reconstruction goes through the runtime.** This package returns references; it never reads a ledger. The
    runtime's memory facade (AbstractRuntime ADR 0009) resolves a `SourceRef` to its verbatim (a ledger row with its
    `$slim` markers resolved, an artifact's bytes, a diary entry, an event) or to a typed `source_gone` answer, never
    an exception, because runs, ledgers and artifacts can be deleted. A memory whose sources are gone keeps its
    references; the reader is told.
11. **The source of a note is an artifact in the ledger.** For a notebook, the note's body (and each attachment) is
    stored as an artifact of the run that captured it, and the processing revision names the capture run, the
    extraction step `(run_id, seq)` and the note's artifact id. For an entity, an episode names its run and step and
    the verbatim artifact (`payload_ref`), a diary projection names the hash-chained diary entry, a reflection names
    the episodes it summarises. A synthetic run id that no store can load is not a source.

### D. Access and layering

12. **Semantic and structural access over one index set.** Full-text (FTS5 over names, aliases, summaries, digests),
    vector (binary column + cached matrix on SQLite; the plane's vector store is decision 3, pending) and structural reads (by subject, object, predicate,
    window, owner, provenance key, revision cursor) share the same ids. Reads are bounded: a read without a limit
    is a defect; a bounded preview says what it left out (root ADR 0026). The change feed `revisions(after=cursor)`
    is lossless across calls.
13. **Hosts reach the graph through the runtime; applications through the gateway.** AbstractRuntime's memory
    facade is the complete host surface for this package (its ADR 0009, mirroring ADR 0008 for AbstractCore): it
    opens a mind, stamps the current run and step onto every write, exposes reads, and reconstructs sources.
    AbstractGateway serves `/api/gateway/memory/*` over that facade and binds the memory tools per account.
    AbstractNote's server side and AbstractEntity's app call the gateway; neither imports this package. A gateway
    import of `abstractmemory` is a boundary violation its test catches (burned down, never added to).

    *Amendment 2026-10-27 (ownership, decision 2):* every read surface enforces ownership: the runtime facade, the
    gateway routes and the memory tools bound per account answer a principal with its own owners' memories and those
    of the entities it owns, nothing else, unless it is an administrator. This package has no principal: its reads
    are keyed by id, reference or cursor, and several cross owners by construction (`derived_from_source(ref)`
    returns every memory grounded in a source, whoever owns it; `sources_of` follows `derived_from` lineage into
    other owners' memories; `history(id)` answers for any id; the change feed `revisions()` carries every owner's
    revisions, each with its `owner_id`). The surface above it filters by `owner_id` before anything reaches a caller.
    The gateway's `/api/gateway/kg/query`, which lets any principal read any owner within its plane, is the defect
    this amendment names and its routes item fixes.
14. **What stays with the consumer.** Capture, importers, prompt wording for one kind of input, the choice of model
    (injected as a reader), dates and their basis for notes, and every view (ADR 0002 decision 6). What moves here:
    the entity registry and reversible merges (0050), the claim lifecycle and revision log (0051, this ADR), the
    reads (0052), self-organisation (0053), the ripple (0054), the notes/diary record (0055).

## Consequences

### Positive
- A person's notebook, the plane's knowledge graph and an entity's memories run on one code path; a fix in retrieval,
  identity or the ripple reaches all of them.
- Any understanding can be traced to the exact ledger rows and artifacts it came from, and any change of
  understanding to the revision that made it and its cause.
- "As of", "as recorded" and "then versus now" become exact reads of the log instead of per-consumer caches.

### Negative
- Writers must carry provenance; existing writers (AbstractNote's tools, the runtime's memory handlers, this
  package's passes) change before they can write to a mind of this shape. Writes without a grounded provenance fail
  loudly by design.
- If decision 3 is taken as first written: the gateway changes its plane default store (LanceDB → SQLite home) and
  imports the existing plane store once (pending).
- Existing notebooks are projected once from their revision log (schema 4 on the live planes; `main` is schema 2):
  a migration the operator schedules.

### Neutral
- The durable work queue, HTTP shapes and scheduling stay with AbstractRuntime and AbstractGateway (ADR 0002).
- The journal keeps its families (attention, bindings, closures, traces, snapshots, valence); the revision log and
  provenance index are new tables beside them in the same file.

## Enforcement

- `abstractmemory.graph` is the only write path that creates or changes claims and records in a mind of this shape;
  `MemoryGraph.apply_revision` validates provenance (`ProvenanceRequired`), applies the ops in one transaction and
  writes the provenance index. Review rejects a new write path that bypasses it, and a `close_assertion` call that
  is not the `close` op of a revision.
- A `SourceRef` whose kind lacks its required id, or a `step` ref without `seq`, is rejected at validation; a reviewer
  rejects any write site that fabricates a ref (a synthetic run id, an empty artifact id) to pass the check.
- This package's own passes write `derived_from` on every record they form; a pass that forms a record with neither
  sources nor lineage is a defect, test-covered per pass as the track lands.
- Every read returning rows takes a `limit`; a preview that truncates reports what it left out.
- Every read surface above this package (runtime facade, gateway routes, memory tools) filters by `owner_id` for
  the calling principal (decision 2, amended): a route or tool that answers across owners, or across a plane, is a
  defect.
- Threshold and constant values (vector cache sizes, cursor page sizes) live in one named module with their
  measurement quoted (same rule as ADR 0001 for the ripple).
- Docs: `api.md` documents `SourceRef`, `Provenance`, `Revision`, `MemoryGraph`, `history`, `sources_of`,
  `derived_from_source`, `revisions(after=)`, `narrow_assertion`; `memory-system.md` gains "Time axes" and
  "Provenance" sections.

## Validation

- Unit, with mutants listed in the test file: a write without sources or lineage is refused; a `derived_from` chain
  that never reaches a source is refused; each `SourceRef` kind refuses its missing id; `narrow_assertion` refuses to
  widen; a revision replays idempotently; the log replayed into an empty store equals the original; `history` shows
  assert → narrow → close with revision ids and causes; the change feed loses nothing and repeats nothing across a
  cursor; `active_at` and the closure record agree after a `close` op.
- End to end on a temporary store, no mocks: a consumer-shaped client writes two revisions (a claim, then a later
  claim that supersedes it, a third that narrows the first from an earlier note), reads `history`, `sources_of`
  and `derived_from_source(step)`, and the runtime facade reconstructs the step and the artifact; deleting the
  artifact yields `source_gone`, not an exception.
- Performance, measured before and after on 10k and 50k assertions (`untracked/memory-transition/audit/
  bench_abstractmemory_baseline.py` and its successor): subject+owner query uses the index (sub-millisecond at 50k),
  reads without vectors do not pay for the embedding column, a vector query at 50k rows is under 100 ms from the
  cache, provenance lookups by ref key are index reads.
- Consumer parity: AbstractNote's supersession, `insert_before` and re-date tests pass against this package's
  `narrow` op with no private attribute access (its backlog 0034 closes); the entity seam's formation tests pass with
  a `step` ref on every formed record.

## Backlog links

- This ADR's first slices: [0056](../backlog/planned/knowledge_graph_convergence/0056_ledger_provenance_contract_and_revision_log.md)
  (provenance contract, revision log, closure causes, `narrow_assertion`, history and change feed),
  [0057](../backlog/planned/knowledge_graph_convergence/0057_one_mind_per_plane_sqlite_home.md) (one home store
  per plane, LanceDB optional, import of the existing plane store),
  [0058](../backlog/planned/knowledge_graph_convergence/0058_home_store_performance_indexes_vectors.md)
  (indexes, column projection, binary vectors and the matrix cache).
- Track: [knowledge_graph_convergence/](../backlog/planned/knowledge_graph_convergence/README.md) (0050-0058);
  [ripple_wave/0001](../backlog/proposed/ripple_wave/0001_change_records_and_ripple_primitives.md).
- Consumers: AbstractNote backlog 0033-0037 (its track `planned/memory_convergence/`); AbstractRuntime ADR 0009 and
  its memory facade item; AbstractGateway memory routes item; AbstractEntity `docs/backlog` memory provenance item.

## Related

- ADR 0001 (an altered memory ripples), ADR 0002 (AbstractMemory owns the graph).
- AbstractRuntime ADR 0003 (tamper-evident hash chain), ADR 0008 (facades are the complete host surface), ADR 0009
  (the memory facade).
- AbstractGateway ADR 0001 (lower-level access through runtime facades).
- Root ADR 0007 (active context vs stored memory), ADR 0009 (`span_id` = `artifact_id`), ADR 0026 (nothing
  truncates silently).
- AbstractNote ADR 0003 (transitional parallel graph), ADR 0008 (interpretation is a derived view).
- Audit: `abstractframework/untracked/memory-transition/audit/` (2026-10-27).
