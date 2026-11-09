# API Reference

> Pre-1.0: the API is versioned and tested; details may still evolve. The authoritative export list is [`src/abstractmemory/__init__.py`](../src/abstractmemory/__init__.py). Signatures below are verified against the source.

See also: [`getting-started.md`](getting-started.md) for first examples, [`architecture.md`](architecture.md) for invariants, [`memory-system.md`](memory-system.md) for the cognitive model, [`stores.md`](stores.md) for backend behavior.

Contents:

- [Layer 1: triples, queries, stores, embedders](#layer-1-triples-queries-stores-embedders)
- [The memory graph: revisions and provenance](#the-memory-graph-revisions-and-provenance)
- [Layer 2: the MemorySystem facade](#layer-2-the-memorysystem-facade)
  - [Seam types](#seam-types)
  - [The journal](#the-journal)
  - [Reconstruction](#reconstruction)
  - [Committing use, deliberate acts, inspection](#committing-use-deliberate-acts-inspection)
  - [Formation (typed records)](#formation-typed-records)
  - [Bindings and closures](#bindings-and-closures)
  - [Identity: spark, engram, self core, floors](#identity-spark-engram-self-core-floors)
  - [Valence and gradation](#valence-and-gradation)
  - [Diary reads and chain verification](#diary-reads-and-chain-verification)
  - [Consolidation (sleep and dreams)](#consolidation-sleep-and-dreams)
  - [Replay stream](#replay-stream)
  - [Entity identity card](#entity-identity-card)
- [Deliberate reach: probe, expansion, familiarity](#deliberate-reach-probe-expansion-familiarity)
- [Situating a past moment](#situating-a-past-moment)
- [World models (orientation cards)](#world-models-orientation-cards)
- [Drives: what is alive and pressing](#drives-what-is-alive-and-pressing)
- [Candidates, disposal, and deliberate acts](#candidates-disposal-and-deliberate-acts)
- [Tending elections](#tending-elections)
- [Recall diagnostics and rendering](#recall-diagnostics-and-rendering)
- [Maintenance, health, and operator tools](#maintenance-health-and-operator-tools)
- [Vocabularies and tuning constants](#vocabularies-and-tuning-constants)

---

## Layer 1: triples, queries, stores, embedders

### `TripleAssertion`

Source: [`src/abstractmemory/models.py`](../src/abstractmemory/models.py). Immutable (`@dataclass(frozen=True)`).

Fields:

- `subject`, `predicate`, `object` — canonicalized on creation (trim + lowercase). Setting `attributes={"literal": True}` preserves the `object` case-sensitively (trim only); typed records use this for digest text.
- `scope` — free-form partition label, lowercased (conventions: `run`, `session`, `global`, and the entity-home scopes `self`/`diary`/`life`); `owner_id` — optional identifier within the scope.
- `observed_at` — ISO-8601/RFC-3339 string (default: current UTC, microsecond precision); `valid_from`/`valid_until` — optional validity window.
- `confidence` — optional float; `provenance`, `attributes` — free-form dicts.
- `assertion_id` — read-side identity: stores stamp it on every query result; optional on writes (deterministic-id flows may supply their own).

Helpers: `to_dict()` (omits nulls) / `from_dict(...)` (validates required fields).

### `TripleQuery`

Source: [`src/abstractmemory/store.py`](../src/abstractmemory/store.py).

- Exact term filters: `subject`, `predicate`, `object` (canonicalized), `scope`, `owner_id`.
- Id lookup: `assertion_ids=(...,)` — returns only those rows; other filters still apply. Id lookups bypass closure/binding folds by design (audit completeness).
- Time: `since`/`until` compare `observed_at` (`>= since`, `<= until`); `active_at` intersects the validity window (`valid_until` is exclusive).
- Semantic: `query_text` (requires a store embedder; no keyword fallback — raises `ValueError` without one), `query_vector` (caller-supplied), `vector_column` (default `"vector"`), `min_score` (cosine threshold).
- Shaping: `limit` (`<= 0` means unbounded), `order` (`"asc" | "desc"` by `observed_at` for non-semantic queries).

Vector results carry retrieval metadata in `attributes["_retrieval"]` (`score`, `metric`, and for LanceDB `distance`).

### `TripleStore` protocol and the three stores

`add(assertions) -> list[str]` (returns assertion ids), `query(q) -> list[TripleAssertion]`, `close()`.

`InMemoryTripleStore` and `SQLiteTripleStore` also expose `close_assertion(assertion_id, valid_until) -> bool`: the one in-place window change the stores allow (a record's digest is rewritten in place only through the layer-2 [understanding verbs](#understanding-in-place-rewrites-and-versions)). It sets `valid_until` on an assertion whose window is still open and touches nothing else (terms, provenance, attributes, the keyword index and the stored vector stay as written). It returns `True` when a row changed and `False` for an unknown id or a window that is already closed, so a replay is harmless; an empty `assertion_id` or `valid_until` raises `ValueError`. Use it when a later fact supersedes an earlier one and `TripleQuery(active_at=...)` must stop returning the old row from that moment on. The layer-2 `close_assertions` (below) is a different operation: it appends a closure record and leaves the row's window as written. In a mind written through [`MemoryGraph`](#the-memory-graph-revisions-and-provenance), a window is closed by a revision's `close` op, which writes the window and the closure together; a direct `close_assertion` call bypasses the revision log.

The same two stores expose `narrow_assertion(assertion_id, valid_until) -> bool`: it moves an already-closed window **earlier** (a later, retrospective note dates the end before the recorded one). `True` when the row's `valid_until` was later and is now `valid_until`; `False` for an unknown id or a window already at or before that date (compared as instants, so mixed UTC offsets cannot move an end later; a value that is not a timestamp raises `ValueError`) (a replay, or a note that would widen it, changes nothing); `ValueError` for an open window (closing is `close_assertion`'s job) or an empty argument. Only `valid_until` moves, and the journal is not written: the revision that carries the `narrow` op records it. `LanceDBTripleStore.narrow_assertion` raises `NotImplementedError` (backlog 0057).

- `InMemoryTripleStore(embedder=None)` — dependency-free, volatile, vector-capable.
- `SQLiteTripleStore(path, embedder=None)` — persistent single file (stdlib only), structured queries and native vector search. With an embedder, `add(...)` embeds each assertion's canonical text and persists the vector in the same file as a float32 little-endian BLOB (a value float32 cannot hold raises `ValueError`, zero rows written); files created before the vector column existed, and homes holding JSON-text vectors (0.3.x), upgrade in place on open (resumable, `vector_blob_high_water` cursor). Rows added without an embedder stay vectorless (vector queries skip them; layer-2 recall labels the degradation `#FALLBACK`). Performance surfaces (backlog 0058):
  - `vector_engine -> str` — `"numpy-matrix-cache"` (vector queries served from the in-process float32 matrix cache, numpy installed: `pip install "abstractmemory[fast]"`) or `"python-linear-scan"` (numpy absent, or a stored vector the matrix cannot score exactly; labelled once per handle with a `#FALLBACK` `RuntimeWarning`). Both paths return the same rows, order and scores as `vector_scoring.rank_by_cosine`.
  - `query_plan(q) -> list[str]` — SQLite's `EXPLAIN QUERY PLAN` lines for the structured read `query(q)` would run.
  - `assertions_after(cursor, *, scope=None, owner_id=None, limit=1000) -> (list[(rowid, TripleAssertion)], next_cursor)` — bounded change feed in rowid order (append-only rows: a cursor never misses or repeats one). `InMemoryTripleStore` has the same method over its insertion order.
- `LanceDBTripleStore(uri, embedder=None, ...)` — persistent, vector-capable; requires the optional `lancedb` dependency (constructing without it raises `ImportError` with an install hint).

Backend details and column layouts: [`stores.md`](stores.md).

### Embedders

- `TextEmbedder` (protocol): `embed_texts(texts: Sequence[str]) -> list[list[float]]`.
- `OpenAICompatTextEmbedder(base_url, model, *, api_key=None, timeout_s=30.0, batch_size=64)` — any OpenAI-compatible `/embeddings` endpoint (`base_url` includes the version prefix, e.g. `http://127.0.0.1:1234/v1`; `model` is required).
- `AbstractGatewayTextEmbedder(base_url, ...)` — POSTs `{"input": [...]}` to an AbstractGateway embeddings endpoint (default path `/api/gateway/embeddings`; Bearer auth via `auth_token`).

Keep one embedding model per store: vectors from different models are not comparable, and the store does not enforce this.

### Canonical text

- `canonical_text(a) -> str` — the shared text rendering stores embed and index (`CANONICAL_TEXT_VERSION` names the current rendering, version 3: an assertion's `original_context` renders whole). Changing this rendering invalidates stored vectors, so it must bump the version and ride a re-embed migration.
- `token_estimate(text) -> int` — the package-wide token estimate (~4 chars/token) used by budgets and handles.

---

## The memory graph: revisions and provenance

Source: [`src/abstractmemory/graph/`](../src/abstractmemory/graph/) (`provenance.py`, `revisions.py`, `graph.py`). Decision record: [ADR 0003](adr/0003-one-graph-ledger-provenance-and-revisions.md). Importable from `abstractmemory.graph`; `SourceRef`, `Provenance`, `ProvenanceRequired`, `InvalidSourceRef`, `Revision`, `RevisionOp` and `MemoryGraph` are also top-level exports.

`MemoryGraph` is the write path of a *mind* (one graph home): every change is one **revision** whose operations apply together, atomically, and every memory it writes must say where it came from in the **ledger** (AbstractRuntime's runs, steps, artifacts, messages, events and diary entries), or which memories it was derived from. This package only stores and indexes these references; resolving one to its verbatim source is the runtime's job (ADR 0003 decision 10).

### `SourceRef`

A typed pointer into the ledger: a frozen dataclass, a plain dict on the wire (`SourceRef.from_dict(d)`, `.to_dict()`). `SOURCE_KINDS = ("run", "step", "artifact", "message", "event", "diary_entry")`.

| `kind` | required | optional | `key()` |
| --- | --- | --- | --- |
| `run` | `run_id` | | `run:<run_id>` |
| `step` | `run_id`, `seq` (int ≥ 1: the ledger row address; AbstractRuntime numbers rows from 1) | `step_id` | `step:<run_id>#<seq>` |
| `artifact` | `artifact_id` | `run_id` | `artifact:<artifact_id>` |
| `message` | `message_id` | `run_id` | `message:<message_id>` |
| `event` | `event_id` | `stream` | `event:<event_id>` |
| `diary_entry` | `entry_id` | `run_id` (`diary:<entity_id>`) | `diary_entry:<entry_id>` |

Every kind may carry `runtime_id` (which ledger: a plane's runtime or an entity home, since homes travel). An unknown kind, a missing required id, a blank id, a `seq` that is not an int ≥ 1 (0 is never a ledger row), an unknown key, or a field another kind owns (an `artifact` with a `seq`) raises `InvalidSourceRef` (a `ValueError`), and so does a `run` or `step` ref naming a run id no ledger can load: `SYNTHETIC_RUN_ID_PREFIXES` = `chat-`, `diary:`, `session_memory_`, `global_memory` (`is_synthetic_run_id(run_id)`; ADR 0003 decision 11: such an id is not a source, the artifact or diary entry it belongs to is). The key is the identity: two refs with the same key are the same source. Any kind may also carry `digest`, the sha256 hex of the verbatim at stamp time (the compact STARTED ledger record, the artifact's bytes, a diary entry's `record_hash`): it rides beside the address (not part of `key()`), is kept in the provenance index, and two refs to one key with different digests are refused. This package only validates it; the runtime stamps and verifies it.

### `Provenance`

```python
Provenance(sources=(...), derived_from=(...), actor="abstractnote", reader=None, reason=None, extra={})
```

- `sources` — `SourceRef`s (dicts accepted; duplicates collapse on the key, first wins).
- `derived_from` — memory ids this memory was derived from (assertion ids, or a record's graph id).
- `actor` — required, non-empty: `"abstractnote"`, `"entity:<id>"`, `"runtime"`, `"abstractmemory:<pass>"`.
- `reader` — the model that exercised judgement, when one did; `reason` — free text; `extra` — anything else (`turn_id`, `note_id`, the consumer's own revision ids).

`is_grounded()` is true when it names a source or a parent. `from_dict(d)` is strict: a key outside the six above raises `ProvenanceRequired`, and a legacy flat key (`run_id`, `turn_id`, `writer_run_id`, `span_id`, `payload_ref`, `entry_id`) names `from_legacy` in the error. `Provenance.from_legacy(flat, *, actor=None)` lifts the old flat shape in one place: `run_id` → a `run` ref unless it is synthetic (a `diary:<entity_id>` pseudo-run rides the `diary_entry` ref; any other synthetic id stays in `extra`), `span_id` and `payload_ref` → `artifact` refs, `entry_id` → a `diary_entry` ref, everything else into `extra`; it never fabricates a ref for an absent or empty key, and `actor` defaults to the dict's own, else `"runtime"`. A dict that already carries `sources` or `derived_from`, including the mixed shape the runtime stamps (its legacy flat keys kept for older readers plus the `sources` it vouches for), keeps its graph keys as they are and lifts every other key into `extra`, with no ref lifted from a flat key (an explicit `extra` wins over a flat key of the same name).

### `Revision`, `RevisionOp`, `RevisionResult`

```python
Revision(revision_id=..., scope=..., owner_id=..., cause=..., occurred_at=..., ops=(...), provenance=...,
         recorded_at=<now>, summary=None)          # keyword-only
RevisionOp(op, payload)
```

- `revision_id` — the idempotency key. `cause` ∈ `REVISION_CAUSES` = `ingest`, `reinterpret`, `merge`, `unmerge`, `ripple`, `person`, `maintenance`, `import`, `migration`.
- `occurred_at` — observation time (when the source said it); `recorded_at` — record time (when this mind learned it). Record time is the STORE's: a fresh `apply_revision` stamps it with the store's clock under the write lock and ignores the value on the `Revision`; only `apply_revision(rev, replay=True)` (what `replay_into` uses: a replay is not a new record) keeps the logged value. The log's `seq` is the record order.
- Every time of a revision (`occurred_at`, `recorded_at`, an assert's `observed_at` / `valid_from` / `valid_until`, a close's or narrow's `valid_until`) is parsed as ISO-8601 and normalized to the package's canonical UTC text form (microseconds, `+00:00`, as `utc_now_iso_seconds` writes; naive times are UTC, `Z` is accepted) when the revision is built; anything else ("next tuesday") raises `ValueError`. Stores and queries compare these strings, which is only correct in one form.
- `ops` (`REVISION_OPS`), validated and normalized at construction:
  - `assert` — payload = `TripleAssertion.to_dict()`. Missing `scope`/`owner_id` come from the revision, a missing `observed_at` is the revision's `occurred_at`, a missing `assertion_id` is derived deterministically from the revision id and the op index (so the logged revision replays identically). A `provenance` in the payload is that memory's own; without one the memory carries the revision's.
  - `close` — `{assertion_id, valid_until, kind, replacement_ids, reason, ripple_source, ripple_hops}` with `kind` ∈ `CLOSE_KINDS` = `retract`, `supersede`, `reinterpreted`, `merged`; `supersede` and `merged` require `replacement_ids`. It sets the row's end to the earlier of its current end and `valid_until` (compared as instants: an open window closes at `valid_until`; a claim "valid until December" retracted in March ends in March; an end already at or before it is kept) and writes the journal `ClosureRecord` in the same operation (the revision id, cause, record time and ripple fields ride the closure's `provenance`; its id is deterministic), so `TripleQuery(active_at=...)` and ranked recall agree after every close. A `valid_until` before the claim's `valid_from` raises `ValueError` (an equal one, an empty window, is allowed). A memory is closed once; a second close is reported in `skipped`.
  - `narrow` — `{assertion_id, valid_until, reason}`: moves an already-closed window earlier (`narrow_assertion`). An open window, or a date before the claim's `valid_from`, raises `ValueError` and the whole revision rolls back; a date at or after the current end is a no-op reported in `skipped`.
- `RevisionResult` — `revision_id`, `applied` (`False` when the id was already in the log: nothing changed), `assertion_ids`, `re_observed` (held memories the revision re-observed), `closed`, `narrowed`, `skipped` (`{op, index, assertion_id, why}` for ops that changed nothing; `why` = `"re-observed"` names the held memory), `seq` (the revision's position in the log) and `recorded_at`. When `applied` is `False` the lists are the revision's LOGGED outcome, read back from its history rows, so a retried step learns the memories its revision named.

### `MemoryGraph`

```python
MemoryGraph(store, journal=None)
```

`store` selects the CONNECTOR (see "Connectors" below): a `SQLiteTripleStore` (the default home: the graph's tables live in its file), a `LanceDBTripleStore` (the LanceDB connector; its journal lives in another file), or an `InMemoryTripleStore` (tests, dev; graph state is shared by every `MemoryGraph` over the same store object). A store with no registered connector raises `NotImplementedError`. `journal` receives the `close` ops' closure records; `None` writes none (the history and the revision still record the close).

**`apply_revision(revision, *, replay=False) -> RevisionResult`** — the one write path. In order:

1. Pure checks, before anything is read or embedded: every asserted memory and the revision itself must name sources or `derived_from`, else `ProvenanceRequired`.
2. A revision id already in the log returns `applied=False` (nothing embedded, nothing written).
3. Assertions are embedded outside the transaction (as `SQLiteTripleStore.add` does); a first embedded write's pin is written inside it.
4. One transaction: each `derived_from` chain must reach a ledger source (a memory already in the graph counts as grounded; a cycle, a self-derivation or a chain to nothing raises `ProvenanceRequired`); a revision whose ops are all `close`/`narrow` must name a source, or a memory other than the ones it changes, as its cause (`ProvenanceRequired`: citing the closed memory as the reason for closing it names no cause); an assertion id already in the store but never asserted through the graph may only be *adopted* by an `import` or `migration` revision that carries the row as stored (everything but provenance equal, else `ValueError`), which rewrites the row's provenance to the graph shape, keeps the old one in the history and logs it with the op (`adoption: {previous_provenance}`, so a replay reproduces the adoption); re-asserting an id the graph already holds is a reported skip when it is the same claim and a `ValueError` when its terms, scope, owner or `valid_from` differ (a changed claim gets a new id); a `close` or `narrow` may only name a memory of the graph (else `ProvenanceRequired`: adopt it first), and only after the op that asserts it when both are in one revision. Lineage never crosses owners: a memory (or a revision) whose `derived_from` names a memory of another `owner_id` raises `ProvenanceRequired` (knowledge from another owner enters as a source: the message or artifact it came through). Re-observation, not duplication: an open assert (no `valid_until`) of a claim the graph already holds OPEN (same subject, predicate, object, scope, owner and `valid_from`) writes no second row; it records the revision's sources and lineage on the held memory, adds a `re-observed` history event and reports it in `re_observed` (also for a duplicate inside one revision; a later op naming the duplicate's id acts on the held memory). A closed claim asserted again, or a bounded assert, is a new memory. Then the triples (with their keyword rows), window changes, closures, history, provenance and derivation rows and the revision row are written; any failure rolls all of it back.

On SQLite with a `SQLiteJournal` on the **same file**, the closures commit in that same transaction, so `TripleQuery(active_at=...)` and ranked recall never disagree. With a journal elsewhere (another file, `InMemoryJournal`) the closures are appended after the commit and the revision is marked `journal_applied = 0` until they are.

Ownership: the graph has no principal. Its reads are keyed by id, reference or cursor, and `derived_from_source`, transitive `sources_of` and `revisions` cross owners by construction (a revision carries its `owner_id`). Visibility is strict ownership ([ADR 0003](adr/0003-one-graph-ledger-provenance-and-revisions.md) decision 2): the host above this package filters by `owner_id` before a result reaches a caller.

Reads (every read is bounded: `limit` must be a positive int and is clamped to `MAX_READ_LIMIT` = 1000; `0`, a negative, a bool or a float raises `ValueError`):

- `history(memory_id, *, limit=200) -> list[dict]` — the memory's lifecycle in record order: `{event: "asserted" | "re-observed" | "closed" | "narrowed", at (record time), revision_id, cause, detail}`. `detail` holds the terms, window and sources of an assertion (`adopted` and `previous_provenance` for an adoption), the close payload with `closure_id`, `window_closed` (the op moved the row's end), `previous_valid_until` and `row_valid_until`, or `valid_until`, `previous_valid_until` and `reason` of a narrow. Accepts an assertion id or a record's graph id (resolved to its digest assertion). Unknown id: `[]`.
- `sources_of(memory_id, *, transitive=True, limit=200, labelled=False) -> list[SourceRef]` — the memory's ledger sources: the refs of its own provenance AND of every revision that asserted or re-observed it (so a memory whose own provenance is lineage only still names the step that produced it); with `transitive`, breadth-first through what it was derived from (deduplicated by key, at most `MAX_LINEAGE_VISITS` = 1000 memories visited). `labelled=True` returns `{"ref", "via": "memory" | "revision", "memory_id", "revision_id"}` dicts.
- `names_ref(ref, owner_ids) -> bool` — the owner gate in one covering-index probe: does any memory owned by one of `owner_ids` name this source (a `run` ref by its `run_id`)? `None`/`''` is the no-owner partition; no owners is `False`; more than `MAX_READ_LIMIT` owners raises `ValueError`.
- `derived_from_source(ref, *, limit=200) -> list[str]` — memory ids grounded in a source: those that name it, then everything derived from them. A `run` ref matches every ref stamped with that run (its own `run` ref and the steps, artifacts, messages and diary entries carrying its `run_id`), once per memory.
- `revisions(after=None, limit=100) -> (list[Revision], cursor)` — the change feed in log order, strictly after the cursor; the returned cursor is `str(seq)` of the last revision (unchanged when nothing is new). Lossless: a revision's position is allocated inside its write transaction and writers are serialized, so no revision is skipped or repeated across calls, also while other connections append. A cursor that is not a number, or one beyond the log's head (another graph's, or invented: it would silently skip every revision below it), raises `ValueError`.
- `replay_into(target) -> int` — re-applies this graph's log, in order, into another `MemoryGraph`; returns how many revisions it applied (ids already there are no-ops, so a replay resumes). Replaying into an empty SQLite home reproduces the original file's triples, keyword index, graph tables and closures exactly, adoptions included.
- `repair(*, limit=1000) -> int` — appends the closures of revisions a crash left with `journal_applied = 0`. Only meaningful for a journal OUTSIDE the store's file: plane and entity homes keep the journal in the same file, where closures commit with the revision and nothing is ever left to repair (it returns 0). Oldest first, oldest first; closure ids are deterministic, so it is idempotent. Raises `RuntimeError` when revisions await closures and no journal is attached.

Constants: `DEFAULT_READ_LIMIT` (200), `DEFAULT_REVISION_PAGE` (100), `MAX_READ_LIMIT` (1000), `MAX_LINEAGE_VISITS` (1000), `ADOPTING_CAUSES` (`import`, `migration`), `DIGEST_PREDICATE` (`dcterms:abstract`, how a record's graph id resolves to its digest assertion), `PROVENANCE_KEYS`, `LEGACY_KEYS`, `SYNTHETIC_RUN_ID_PREFIXES`.

Opening a `MemoryGraph` on a home whose graph tables and indexes exist is a read (no DDL transaction): a reader needs no write lock and does not wait behind a writer.

### Connectors (`abstractmemory.graph.backend`)

`MemoryGraph` is the only manipulation surface of a mind ([ADR 0003](adr/0003-one-graph-ledger-provenance-and-revisions.md) decision 3); a database is a connector behind it. A connector implements two Protocols:

- `GraphBackend` — `prepare_rows(assertions)` (embed and shape rows before the transaction), `transaction()` (a context manager yielding a `GraphTx`), the reads `applied_seq`, `resolve`, `history`, `sources`, `parents`, `children`, `with_ref`, `names_ref`, `revisions_page`, `log_head`, `logged_outcome`, and `pending_journal` / `closed_payload` / `mark_journal_applied` / `repair_projections` (crash repair).
- `GraphTx` — one revision's reads (`revision_seq`, `memory_known`, `closing_revision`, `open_same_claim`, `digest_assertion_for`, `existing_ids`, `stored`, `window`; they see the transaction's own writes) and writes (`write_pin`, `insert_assertions`, `set_provenance`, `end_row`, `narrow_row`, `write_closure`, `add_history`, `add_source`, `add_derivation`, `insert_revision`).

Invariants (the module docstring states them): the writes of one transaction become visible together or not at all; `insert_revision` allocates `seq` = head + 1 and transactions are serialized (the change feed is lossless); an assertion id, a (memory, ref key) provenance row and a (memory, parent) derivation row are written once, the first winning; every read is bounded; opening a mind writes nothing.

Connectors shipped: SQLite (`_SQLiteBackend`, one transaction per revision), in-memory (`_MemoryBackend`, an undo log), LanceDB (`abstractmemory.graph.lancedb_backend.LanceDBBackend`: a staged transaction whose reads overlay its writes, a log-first commit, `repair_projections()` re-deriving a half-projected revision from the log; one lock, table handles and counters per mind per process). What the LanceDB connector cannot promise: writers of one mind in two processes are not serialized, and a crash in the middle of a commit leaves the rows of an unapplied revision visible until `repair()`.

To add a connector: implement both Protocols for a store class, call `register_backend(StoreClass, factory)` (`factory(store, journal) -> GraphBackend`; the most recently registered matching class wins), add the backend to `BACKENDS` in `tests/graph_support.py` (an `open_home` branch), and run `tests/test_graph_conformance.py`: every case passes, or is marked `xfail(strict=True)` with the reason and listed in ADR 0003 decision 3. `backend_for(store, journal)` and `registered_backends()` inspect the registry.

### The graph tables (SQLite)

In the store's file, beside the triple table and the journal's `memj_*` tables (a store with a custom `table_name` prefixes them `memg_<table>_`):

| Table | Columns | Indexes |
| --- | --- | --- |
| `memg_revisions` | `seq` (INTEGER PRIMARY KEY AUTOINCREMENT: the change-feed cursor), `revision_id` (UNIQUE), `scope`, `owner_id`, `cause`, `occurred_at`, `recorded_at`, `ops_json`, `provenance_json`, `summary`, `journal_applied` | `revision_id`; partial index on `seq` where `journal_applied = 0` |
| `memg_provenance` | `memory_id`, `ref_key`, `ref_kind`, `run_id`, `revision_id`, `ref_json`, `via` (`memory` or `revision`), `owner_id` (the memory's, `''` for none); PRIMARY KEY (`memory_id`, `ref_key`) | `ref_key`, `run_id`, (`ref_key`, `owner_id`), (`run_id`, `owner_id`) |
| `memg_derivations` | `memory_id`, `from_id`, `revision_id`; PRIMARY KEY (`memory_id`, `from_id`) | `from_id` |
| `memg_history` | `seq` (INTEGER PRIMARY KEY AUTOINCREMENT), `memory_id`, `event`, `at`, `revision_id`, `detail_json` | (`memory_id`, `seq`), (`revision_id`, `seq`) |

Columns and indexes added after the tables first shipped (`via`, `owner_id`, the history revision index) are added in place when a graph opens a home that lacks them (`owner_id` backfilled from the memory rows); a home that has them opens without a write.

Every keyed read above is an index search (pinned by `tests/test_graph_performance.py`). Measured on a temporary home of 50,000 assertions written through the graph (`tests/bench/bench_graph.py`): `history` 0.02 ms, `sources_of` 0.04 ms (0.10 ms transitive over a derived memory), `derived_from_source` by step 0.05 ms and by run (128 memories) 0.8 ms, a change-feed page of 100 revisions 4 ms; the only provenance lookup a 0.3 home allowed, a scan of every row's provenance JSON, took 18 ms on vectorless rows and 38 ms with 384-d vectors in the rows.

---

## Layer 2: the MemorySystem facade

Source: [`src/abstractmemory/system.py`](../src/abstractmemory/system.py) (+ mixins `system_access.py`, `system_valence.py`).

```python
from abstractmemory import MemorySystem, SQLiteTripleStore, SQLiteJournal

store = SQLiteTripleStore("memory.sqlite3")
journal = SQLiteJournal("memory.sqlite3")   # sidecar tables in the same file
system = MemorySystem(store=store, journal=journal)
```

Constructor: `MemorySystem(*, store, journal, embedder=None, selector=None, reflector=None, attention_config=AttentionConfig(), spread_params=SpreadParams(), clock=None, broad_scopes=None, ablation=None)`.

- `embedder` enables the vector retrieval channel.
- `broad_scopes` (default `{"global"}`): searching one requires an explicit `escalation_reason`.
- `selector`/`reflector` are accepted for signature stability but unused (a `#FALLBACK` warning is emitted; the shelf is heuristic).
- `ablation` (`"recency_embedding"` or `"recency"`) switches read-side evaluation arms for experiments; write paths are unaffected.
- `close()` releases the journal only; the store is caller-owned.
- Layer-1 passthroughs: `system.add(...)`, `system.query(...)`, `system.seq_at(iso_ts)`, `system.current_seq()`.

Five stability contracts (each pinned by tests):

1. `reconstruct` is a pure read. `journal=True` appends one trace + inert `listed` audit events that never affect scores; `journal=False` writes nothing.
2. `commit_selection` is the only strengthening path; deliberate acts require a `reason` and support supplied-id idempotency.
3. Relevance admits, activation reorders: a channel-matched candidate can never be outranked or budget-evicted by an unmatched one.
4. Every result carries `as_of_seq`; anchoring `Stimulus(as_of=...)` reproduces it deterministically.
5. Degradations are labeled `#FALLBACK` in `warnings`; invalid input raises actionable errors (an invalid anchor never silently means "latest").

### Seam types

Source: [`src/abstractmemory/seam.py`](../src/abstractmemory/seam.py). All JSON-safe (`to_dict()`; tuples serialize as lists).

- `Stimulus(cue_text, patterns=(), anchor_record_ids=(), participants=(), embedding=None, as_of=None, turn_id=None)` — the incoming cue. `patterns` are serialized `TripleQuery` filters (exact channel); `participants` are identity strings for co-presence scoring; `as_of` anchors the read; `turn_id` is provenance.
- `RecallBudget(max_candidates=64, shelf_size=12, token_budget=2400, max_anchor_cues=4, max_hops=2, max_edges=100, min_activation=None, deadline_s=None, stm_fraction=0.25, stm_floor=None, self_fraction=0.0)` — hard bounds for one reconstruction. `stm_fraction` caps the short-term component (0 disables it); `stm_floor` is its activation eligibility bar (default 1.0); `self_fraction` caps identity's reserved seats (0.0..0.9; hosts set it for entity sessions). `max_hops`/`max_edges` bound spreading and override `SpreadParams`. `min_activation` filters `working_set` membership only and never gates channel matches. `deadline_s` is accepted but not enforced by the pure pipeline.
- `MemoryHandle` — one scored memory: `record_id`, `kind`, `title` (`None` while the record's title is pending), `digest`, `token_estimate`, `relevance` (per present channel), `activation` (`base_level`/`spread`/`total`), `cues` (human-readable "why"), `binding` (folded `"{search_state}+{prompt_state}"`), `scope`, `owner_id`, `provenance` (including `global_count`), `payload_tiers`, and `admission` — `"self" | "stm" | "stimulus" | "both"` (`"historical"` is reserved). Only `stimulus`/`both` admissions deposit at commit.
- `ReconstructionResult` — `trace_id`, `view`, `as_of_seq`, `handles`, `edges` (working-set view only; render-side, never handles), `dropped` (`{record_id, score, reason}`), `selector_route`, `stop_reason`, `warnings`, `budget_spent`.
- `ActiveMemorySnapshot` — what actually entered a context: `snapshot_id`, `trace_id`, `used_record_ids`, `display` rows, `prompt_token_estimate`, `observed_at`, `provenance` (including per-id admission labels). References and display metadata only, never payload copies.
- Constants and helpers: `SELF_FRACTION_FLOOR` (0.05), `ENTITY_CONTEXT_FLOOR` / `ENTITY_CONTEXT_RECOMMENDED` (40,000 — a recommended working size, not a minimum; operator 2026-08-01), and `entity_recall_budget(context_window, *, shelf_size=12, token_fraction=0.12) -> RecallBudget` — the entity-session budget profile (`token_budget = max(2400, round(0.12 × window))`, uncapped above the target; smaller windows are accepted — the 2400 floor is a starvation guard, not policy).

### The journal

Source: [`src/abstractmemory/journal.py`](../src/abstractmemory/journal.py); backends `InMemoryJournal()` (volatile, emits a `#FALLBACK` warning) and `SQLiteJournal(path)` (sidecar tables; may share the store's file).

Record families (all append-only, all `seq`-stamped by the journal):

- `MemoryEvent` — attention events. Scoring kinds: `selected`, `co_selected` (pair trails), `pinned`, `silenced`; decay marker: `refocus`; audit-only (recorded, never scored): `listed`, `shown`, `expanded`, `cited`.
- `ScopeBinding` — visibility: `search_state` (`indexed`/`hidden`), `prompt_state` (`active`/`inactive`), `lifecycle`, `source`, `reason`. Latest per `(record_id, scope, owner_id)` wins; `fold_bindings(bindings)` applies that fold.
- `ClosureRecord` — belief lifecycle: `kind` (`retract`/`supersede`/`reinterpreted`/`merged`; `abstractmemory.journal.CLOSURE_KINDS`), mandatory `reason`, `replacement_ids` (required for supersede, optional otherwise). `reinterpreted` means the writer no longer reads its source this way (a note understood again): neither a correction nor a later fact; `merged` means the memory was merged into another, named in `replacement_ids` (written by the graph's `close` op). Every kind leaves ranked retrieval.
- `ReconstructionTrace` — one recall: fingerprint, searched scopes, candidates, selected/dropped, cues, budgets, admission labels, warnings.
- `ActiveMemorySnapshot` — see seam types.
- `ValenceEvent` — signed appraisals and standing markers (see valence below).
- `UnderstandingVersion` — one reading of a record (see [understanding](#understanding-in-place-rewrites-and-versions)): `record_id`, `assertion_id`, `version`, `field` (`digest` | `card` | `narration` | `title` | `target`), `text` (`None` only on title version 0 of a record formed with its title pending), `title` (`None` while the title was pending), `keywords`, `digest_method`, `author`, `reader`, `sources`, `derived_from`, `cause`, `magnitude`, `task_id`, `understood_at`, `version_id` (deterministic), `seq`. Read with `versions(record_id=, assertion_id=, field=, until_seq=, limit=0)` (oldest first) and `revision_records(since_seq=, until_seq=)` (the replay family `revision`).

Write-side idempotency (all backends): a caller-supplied id (`event_id`, `binding_id`, `closure_id`, `trace_id`, `snapshot_id`) makes replays no-ops returning the original record — at-least-once delivery never double-writes. The `MemoryJournal` protocol also exposes readers (`events`, `bindings`, `closures`, `traces`, `snapshots`, `valence_events`, `replay_records`) and the global counters `selected_count(record_id)` / `pair_selected_count((a, b))` (both accept `until_seq`).

### Reconstruction

```python
result = system.reconstruct(
    Stimulus(cue_text="pool outage"),
    scopes=[("session", "s1"), ("global", "")],   # narrow → broad
    budget=RecallBudget(),
    view="shelf",                                  # or "working_set"
    escalation_reason="cross-session recall",      # required when a broad scope is searched
    journal=True,
    trace_id=None,                                 # supply one to make the journaled read replay-safe
)
```

The result is the union of three admission components — `self` (identity by binding state), `stm` (trail-hot standing), `stimulus`/`both` (channel matches) — with the single best channel match seated first against the full budget. Retrieval channels: exact (`Stimulus.patterns`), keyword (a casefolded, accent-folded token scan over gathered candidates; minimum token length 4; labeled `#FALLBACK`), vector (requires the system embedder and stored vectors; cosine with a confidence-scaled floor so a weak field never reads as full relevance), and participants (co-presence between `Stimulus.participants` and record `participants`, scored `|intersection| / |stimulus.participants|`). Spreading activation walks recorded edges and co-use trails from matches under `max_hops`/`max_edges`; `SpreadParams` keeps the walk-shape knobs (weights, damping, `fan_out_cap`, `min_contribution`).

In the `working_set` view, `result.edges` also surfaces walked edges and top trail pairs for rendering.

### Committing use, deliberate acts, inspection

- `commit_selection(trace_id, used_record_ids, *, prompt_token_estimate=None) -> ActiveMemorySnapshot` — deposit the usage trail for records that actually entered a context: one `selected` event per used record plus `co_selected` events for **all pairs used together** in the depositing slice (plus term-sharing and recorded-edge hop pairs). Only ids admitted as `stimulus`/`both` (or unlabeled, for foreign traces) deposit; `self`/`stm` ids deposit nothing (presence ≠ use; `AttentionConfig.stm_rehearsal_weight`, default 0.0, is the optional rehearsal dial for STM). Idempotent by `trace_id` — a replay returns the original snapshot unchanged.
- `reinforce(record_id, *, reason, weight=8, ttl_activity=None, scope, owner_id, event_id=None, actor="operator", provenance=None) -> str` — deliberate strengthen (weight clamps 1..25).
- `attenuate(...)` (same signature) — deliberate weaken: a nudge toward invisibility, never negative relevance (removal is closure).
- `refocus(*, reason, scope, owner_id, ...) -> str` — topic-shift marker; accelerates decay of everything older in that scope stream.
- `activation(record_ids=None, *, scope, owner_id, at_seq=None) -> dict` — stored activation per record (`base_level`/`total`); unknown ids raise.
- `access_counts(record_ids=None, pairs=None) -> {"records": {...}, "pairs": {...}}` — the never-decaying global counts (per journal; for one-journal entity homes, per life).
- `payload(record_id, tier="digest") -> dict` — pure payload read. `digest` returns the canonical text; `raw` returns the host artifact reference (`attributes.payload_ref`) with `content=None` — the package never fetches verbatim payloads. Diary projections additionally carry `entry_id` (the pointer into the host-side diary book).

`AttentionConfig` (all declared tunables): `window_limit=512` (the bounded read window of the temporal fold — size to about a week of measured event cadence for continuously active homes, e.g. 8192), `decay_window=20.0`, `refocus_multiplier=6.0`, `max_activation=25.0`, `boost_scale=4.0`, `max_boost=120.0`, `prior_scale=0.05`, `prior_cap=1.0`, `reason_threshold=0.5`, `stm_rehearsal_weight=0.0`. The global count never windows.

Id namespaces: every id-taking call (`commit_selection`, `reinforce`, `attenuate`, `activation`, `access_counts`, `payload`, `bind`, `close_assertions`, `close_record`) accepts both the digest-assertion id (`handle.record_id`) and the graph id (`remember_many`'s `ex:…` return); unresolvable ids raise naming both namespaces.

### Formation (typed records)

- `remember_many(records, *, scope, owner_id, idempotency_key, turn_id=None) -> list[str]` / `remember(record, ...) -> str` — form typed records. Idempotent: ids derive from `(idempotency_key, position)`, so replays are no-ops returning the same graph ids. Forming deposits no attention events (forming is not using). Edges may reference batch siblings as `"local:<i>"`.
- `MemoryRecordInput(kind, title, digest, intents=(), outcomes=(), keywords=(), participants=(), edges=(), payload_ref=None, topic=None, confidence=None, attributes={}, provenance={}, pending=())` — one record to remember. A title and a digest are mandatory metadata of every memory (operator rulings 2026-11-09). The one exception is an explicit, transient pending state: `pending=("title",)` with `title=None` (or `""`) forms the record untitled, `pending=("summary",)` marks the given digest provisional (refused on `UNDERSTANDING_PROTECTED_KINDS`). The record then carries `attributes.pending = {title: bool, summary: bool, since, attempts}` and `remember_many` queues its authoring task in the same call (`PENDING_TASK_KINDS`: `title.author` / `digest.author`; see the task queue); a home opened without `task_queue=True` refuses it, and a null title not declared pending is refused (`ValueError`). Reads serve the missing title as `None` (handles, display blocks with `pending`, `record_understanding` with `pending`, `recent_records`, card briefs, probe hits), never a placeholder or words from the body, and the canonical text is the body alone. The `digest` (1–3 sentences) is what gets indexed and embedded; `payload_ref` keeps the full verbatim reachable as a host artifact; `edges` are `(relation, target_record_id)` pairs stored as edge assertions; `participants` are identity strings (`person:ada`, `entity:castor`) — co-presence is explicit, and what a record says is its full co-presence.

Record kinds: `memory`, `episode`, `lesson`, `instruction`, `decision`, `claim`, `summary` (requires at least one edge naming what it summarizes), `question`, `answer`, `plan`, the identity kinds `value` (requires `attributes.value_class` ∈ {core, revisable}), `purpose`, `trait`, `diary`, `interest`, and the sleep artifact `dream`. Kind ranks order identity first (value < purpose < trait) and derived artifacts as summary peers.

Diary formation rules: `kind="diary"` requires `provenance.source` ∈ {`diary-projection`, `owner-direct`}; `diary_type` ∈ {note, idea, commitment, reflection, question, problem} (absent defaults to `note`; unknown values raise); projections must carry `attributes.entry_id`; resolution references ride `attributes.answers` (questions) and `attributes.resolves` (problems).

### Bindings and closures

- `bind(record_id, *, scope, owner_id, search_state, prompt_state="inactive", lifecycle="none", source="operator", reason=None, binding_id=None) -> ScopeBinding` — append a visibility event. A folded `hidden` binding removes the record from ranked retrieval in that scope pair only; re-binding `indexed` restores it. `prompt_state="active"` admits the record into the identity (self) component. Record-level bindings hide the digest and its edge assertions together. Direct `store.query` id lookups bypass folds by design.
- `close_assertions(assertion_ids, *, kind, replacement_ids=(), reason) -> list[str]` — append one closure per assertion (`retract` | `supersede` | `reinterpreted` | `merged`).
- `close_record(record_id, *, reason, kind="retract", replacement_ids=()) -> list[str]` — close a whole record (digest and its edges) as one belief-revision act; closure ids are deterministic, so replays dedupe.

### Understanding: in-place rewrites and versions

Source: [`src/abstractmemory/understanding.py`](../src/abstractmemory/understanding.py). A record's understanding (its digest, a card's text, a dream's narration) can be rewritten in place. The record keeps its graph id, its digest assertion id (usage keys on it), its edges and every journal record; the previous reading stays in the journal as an `UnderstandingVersion`. Version 0 is the original text, captured at the first rewrite. The verbatim behind a record is never touched, rewriting deposits nothing, and the engine never invents or edits the words it is given. All verbs are on `MemorySystem` and also exported as module functions taking the system first.

- `rewrite_digest(record_id, *, text, author, cause, expected_version, reader=None, sources=(), derived_from=(), title=None, keywords=None, digest_method="authored-v1", magnitude=None, task_id=None, understood_at=None) -> dict` — replace a record's digest (and optionally its title and keywords) in place. `record_id` is the graph id or the digest assertion id. `expected_version` is a compare-and-set on the record's `digest_version` (0 for a record never rewritten). On the SQLite home one transaction appends the version rows, updates the row, replaces its keyword-index entry and writes its new vector; the vector is computed first, outside the transaction, with the store's pinned embedder.
- `retitle(record_id, *, title, author, cause, expected_version, reader=None, sources=(), task_id=None, understood_at=None) -> dict` — change ONLY a record's title, in place, for every kind (episode, summary, world-model card, dream, interest, lesson, realization, observation, every diary entry). A title is an explicit, complete phrase, stored exactly as given and never cut (root ADR 0054). The body, the keywords and the digest's reading stay byte-identical; `attributes.title`, `title_version` and `title_provenance` change, and the canonical text (the title is its first line), the keyword-index entry and the vector are replaced in the same transaction. `expected_version` is the compare-and-set on `title_version` (0 for a record never retitled). The first retitle keeps the title it replaces as version 0 of field `title`, with the provenance of the reading that wrote it. The protected kinds are not refused: their protection covers the body (the entity's words), and a title the runtime cut at formation is not his words. For a diary entry the privacy rule concerns reading, and retitle reads nothing back: `record_understanding` still refuses the entry, its replay display block stays redacted, and the opt-in `revision` envelopes of its title versions are sealed the same way (payload `text`, `title`, `keywords` emptied, `redacted: "diary"`). `outcome="unchanged"` (no version) when the title is already the current one. A record formed with a pending title is retitled the same way: its title version 0 holds `None` (`text` and `title`), the write completes its live `title.author` tasks (named or not) and clears the marker (`pending_cleared: ["title"]` in the result; `rewrite_digest` does the same for a pending summary), and an interest's card keyed on its graph id moves to the title's subject head through `rekey_world_model` (`card_rekey` in the result). Refusals: `empty_title`, `hash_chained`, `closed`, `stale`, `embedder_unavailable`, `unknown_record`. A `rewrite_digest(..., title=...)` or a revert that changes the title writes the title version too (the result carries `title_version`), so `versions(record_id, field="title")` lists every title. Recall finds the record by its new title through the keyword index and the vector. Known limit, unchanged here: unless FTS keyword discovery runs, the reconstruct keyword channel is the v1 token scan over the newest candidate window per scope, so an old record in a large home can sit outside it (found by the 1181 backfill verify; backlog 0019).
- `declare_pending(record_id, *, fields=("title", "summary"), cause="repair", reason=None) -> dict` (also a module function `declare_pending(system, record_id, ...)`) — declare that a STORED record's title and/or summary is still being written: the record gets exactly what a record formed with `pending=fields` gets, for any kind. For the records stored before titles and summaries were mandatory: a legacy world-model card ("World model: <subject>", `mechanical-card-v2`), a legacy dream ("Dream: ..."), a placeholder or missing title. The marker `attributes.pending = {title, summary, since, attempts}` (`since` = now, merged into a marker already there) and, per newly declared field, formation's task (`title.author` / `digest.author`, capability `summaries`, `FORMATION_PRIORITY`, strength 1.0, basis `<assertion id>@pending-<field>`, `basis_version` 0; a live task with that identity queued earlier without the marker is adopted, and a field authored once and declared again gets the next free `...@pending-<field>@<k>`), written in one transaction on the SQLite home. A declared title is stored `None`, as a pending title is at formation: the title it held stays as a title version (version 0 with its provenance, then `None` with the declaration's), the canonical text, keyword entry and vector are replaced, and an interest's standing card moves to `topic:<its graph id>` (`card_rekey`; a card other active interests still elect stays, reason `shared_card`). A declared summary keeps the body as its provisional digest (never restored: `revert_digest` refuses it with `provisional_summary`), calls no embedder, and supersedes the record's live body task (`digest.rewrite`, a card's `card.author`). The drainer then completes the tasks through `retitle` and `rewrite_digest` exactly as for a record formed pending: a card's summary through the card's own write (target, evidence, revision untouched), a dream's in place (signals and the `dream.narrate` task untouched). The journal keeps the declaration as a version row (field `pending`, `pending_version` on the row; text = the fields declared, author `{"kind": "mechanical", "id": "declare_pending"}`, cause `{cause, reason?, pending, tasks, provisional?, already_pending?}`), shown by the opt-in replay family `revision`; it is not a reading and `revert_digest` refuses it (`not_revertible`). Returns the understanding result shape with `field="pending"` plus `declared`, `already_pending`, `pending` (the marker), `tasks` (`{field: task id}`), `enqueued`, `adopted`, `superseded`, `provisional` (`{field, version}`), `title_version` and `card_rekey` when they apply. Idempotent: every asked field already pending returns `outcome="unchanged"`, reason `already_pending`, nothing written or queued. Refusals: `unknown_record`, `no_task_queue`, `closed`, `protected_kind` (a summary of the entity's own act), `consolidation_record`, `hash_chained` (a declared title), `stale`, `embedder_unavailable` (a declared title). `fields` outside `PENDING_FIELDS`, empty, or a cause outside `REWRITE_CAUSES` raise `ValueError`.
- `narrate_dream(dream_id, *, text, author, expected_version=0, reader=None, sources=(), cause="formation", task_id=None, understood_at=None) -> dict` — store a narration beside a dream's mechanical summary (`attributes.narration`, `narration_version`, `narration_provenance`). The digest, the signals, the keyword index and the vector are untouched. Versioned under field `narration`; the first narration is version 1.
- `revert_digest(record_id, to_version, *, expected_version, by=None, reason=None, field=None) -> dict` — restore an earlier reading as a NEW version (cause `revert`, `reverted_to`; nothing is erased). The restored reading keeps the author and reader of the words it restores; `by` (`{kind, id}`, default the operator) is recorded in the cause. `field="title"` restores an earlier title; a version that held no title is refused (`null_title`: a title is mandatory), as is the provisional digest a record was formed with while its summary was pending (`provisional_summary`). A digest or card version restores its title too, unless the record was retitled since its current reading (that title stays).
- `versions(record_id, *, field=None) -> list[dict]` — every reading, oldest first, each with `current: bool`. `field` defaults to the record's own (`digest`, or `card` for a world-model card); pass `field="narration"` for a dream's narrations, `field="title"` for its titles, `field="target"` for a card's keys (`rekey_world_model`), `field="pending"` for its pending declarations (`declare_pending`). A record never rewritten returns `[]`.
- `current_of(record_id) -> dict` — follow supersede and merge closures to the live record: `{record_id, graph_id, current_id, current_assertion_id, hops, chain, closed}` (`closed` names a retract/reinterpreted end).
- `record_understanding(record_id) -> dict` — the record read a host serves: `{record_id, graph_id, assertion_id, kind, title, digest, keywords, payload_ref, observed_at, closed, current_id}` plus the provenance fields below; dreams add `narration`, `narration_by`, `narration_reader`, `narrated_at` and `signals`. Diary records raise `ValueError` (the book is their door).
- `understanding_fields(assertion, *, version_count=None, replaced_by=None) -> dict` — the pure provenance read the replay display blocks use: `digest_method`, `digest_version`, `version_count`, `authored_by`, `reader`, `understood_at`, `cause`; cards `target`, `target_type`, `card_revision`, `source_count`; dreams `narrated`, `narration_version`; `replaced_by`. Unknown values are absent, never guessed.
- `reading_provenance(assertion) -> dict` — the one derivation of who wrote a record's current reading, when and why: `{author, reader, understood_at, cause}`. `understanding_fields`, `record_understanding`, the replay display blocks, the identity card's briefs and formation all read through it. The row's own stamp (`attributes.understanding`) wins. A row nobody stamped reads as its formation reading (`cause` `"formation"`, `understood_at` = its `observed_at`), its author from its origin: a `mechanical*` digest_method gives `mechanical` (id = the method); a spark identity record (`attributes.spark_version`) gives `operator` (id `spark-v<N>`); a row whose provenance names the operator as actor (an archive import) gives `operator` (id = the source); a kind in `ENTITY_WORDS_KINDS` (lesson, interest, realization, observation, question, every diary entry, a value, purpose or trait he elected) gives `entity-mind` (id = the owner); anything else stays `unrecorded`. `remember_many` records the same reading at formation (`attributes.understanding`, version 0) when the caller stamped none and the author is known.

Provenance arguments (validated; a bad value raises `ValueError`):

- `author = {"kind": ..., "id": ...}`, `kind` in `AUTHOR_KINDS`: `entity-mind` (the entity's own model), `capability-model` (a model the host names for this capability), `operator`, `mechanical`. A model author (`entity-mind`, `capability-model`) must also pass `reader = {"provider", "model", "thinking"}` and at least one ledger `SourceRef` dict in `sources` (the step of its call, ADR 0003). A reading whose row names no origin (see `reading_provenance`) and a legacy label passed to `author_world_model` carry author kind `unrecorded`.
- `cause` is one of `REWRITE_CAUSES` (`formation`, `backfill`, `ripple`, `evidence`, `operator`, `revert`, `repair`: a correction of what a process wrote wrong, such as a title cut at formation), or a dict `{"cause": ..., ...}` whose extra keys (`task_id`, `ripple_id`, `seed_id`, `hops`, ...) are kept verbatim.

Every verb returns `{applied, outcome, reason, record_id, assertion_id, field, version, ...}`. `outcome="applied"` adds `previous_version`, `version_id`, `seq`, `captured_original`, `vector_rewritten`. `outcome="unchanged"` (byte-identical text) writes nothing and is safe to retry. `outcome="refused"` writes nothing and names its `reason`:

| Reason | When |
| --- | --- |
| `unknown_record` | no formed record with that id |
| `protected_kind` | `UNDERSTANDING_PROTECTED_KINDS`: diary, value, purpose, trait, interest, realization (the entity's own acts) |
| `use_narrate_dream` / `use_author_world_model` | a dream's written summary stays (a narration goes beside it); a card is authored through `author_world_model`. A dream or card whose summary is still PENDING takes it here: a card through its own in-place write (field `card`) |
| `card_keywords` | `keywords=` on a pending card: a card's keywords are its evidence facets |
| `not_a_dream` | `narrate_dream` on another kind |
| `closed` | the record is retracted or superseded (`replaced_by` names its replacement) |
| `consolidation_record` | a ripple's `summary_role: re-understanding` record, unless the cause is `operator` |
| `empty_text` | blank text |
| `empty_title` | `retitle` with an empty or whitespace title |
| `hash_chained` | `retitle` of an owner-direct diary entry whose `entry_hash` attests its title (`verify_diary_chain` would break) |
| `stale` | `expected_version` is not the record's current version (another writer moved it) |
| `embedder_unavailable` | the store's embedder failed, or the record is vectored and the store has no embedder |
| `unknown_version` | `revert_digest` to a version the record never had |
| `use_rekey_world_model` | `revert_digest(..., field="target")`: a card's key moves back through `rekey_world_model` |
| `provisional_summary` | `revert_digest` to the provisional digest a record was formed with, or to a reading `declare_pending` made provisional |
| `not_revertible` | `revert_digest(..., field="pending")`: a pending declaration is not a reading |
| `no_task_queue` | `declare_pending` on a home opened without `task_queue=True` (a pending field is stored only beside its task) |
| `already_pending` | `declare_pending` (`outcome="unchanged"`): every asked field is already pending; nothing written |

Backends: the in-memory pair and a SQLite store whose `SQLiteJournal` shares its file (the entity-home deployment). A SQLite store with a journal elsewhere raises `ValueError`; `LanceDBTripleStore` raises `NotImplementedError`.

### The memory task queue: understanding in the background

Source: [`src/abstractmemory/memory_tasks.py`](../src/abstractmemory/memory_tasks.py), [`src/abstractmemory/activation_gate.py`](../src/abstractmemory/activation_gate.py). A home opened with `MemorySystem(..., task_queue=True)` keeps a persistent queue of what still needs understanding (`memq_tasks`, `memq_log`, `memq_windows` in the home's file; a private in-memory database for the in-memory store). Memory enqueues where records form; the host decides when a window opens, how long it may run and which model reads; it applies results through the [understanding verbs](#understanding-in-place-rewrites-and-versions) with `task_id=`, which settle the task in the same transaction.

Task kinds (`TASK_KINDS`; capability in parentheses): `title.author` and `digest.author` (summaries) for a record formed pending (its `attributes.pending` marker), at `FORMATION_PRIORITY` (5, ahead of every rewrite) and strength 1.0, completed by `retitle` / `rewrite_digest` (which clear the marker), each claim mirrored into the marker's `attempts`, a diary target's packet redacted (its words come through the book by `entry_id`); `digest.rewrite` (summaries) for a record formed with a `MECHANICAL_DIGEST_METHODS` label (never beside a pending summary); `card.author` (summaries) for a LEGACY card still in mechanical words, or carrying a mechanical delta (a card formed now owes `title.author` / `digest.author` instead); `dream.narrate` (understanding) for a formed dream, in `night` and `nap` windows only; `ripple.reconsider` and `ripple.consolidate` (understanding) for the [ripple](#ripple-a-change-reconsidered-through-connected-memories), consolidation in `night` windows only. Review offers (maintenance candidates, dedup groups) and `UNDERSTANDING_PROTECTED_KINDS` are never rewrite tasks; their pending title or summary is (every record a memory pass forms is pending, below). Windows (`WINDOWS`): `turn`, `visit`, `nap`, `cycle`, `night`, `idle`.

Enqueue sites: `remember_many` (a `title.author` / `digest.author` per pending field; one `digest.rewrite` per labelled-mechanical record; a summary depends on the pending rewrites of the records it summarizes), `world_model_pass` (its cards form pending, so `remember_many` queues their `title.author` / `digest.author`; a revision supersedes the prior card's live `title.author` / `digest.author` / `card.author` tasks), `dream_pass` (pending title and summary, plus `dream.narrate`), `declare_pending` (a stored record declared pending: formation's `title.author` / `digest.author`, its live body task superseded), the ripple, and the backfill (`enqueue_debt`).

**What memory's own passes form is pending** (operator rulings 2026-11-09: no title or summary is ever the pass's words). `world_model_pass`, `dream_pass`, `mine_candidates_pass`, `consolidation_pass` and `wake_cue_dedup_pass` form their cards, dreams, offers, candidates and day summaries with `pending=("title", "summary")`: the bookkeeping text they compose (a card's evidence briefing, the night's tensions, an offer's invitation, a dedup witness) is only the provisional body the `title.author` / `digest.author` tasks author from, and display blocks and `record_understanding` carry `pending` so an app shows "being written…". A card revision carries an AUTHORED title (one with `title_provenance`, `carried_from` added) and forms `pending=("summary",)`. The drainer completes them with `retitle` and `rewrite_digest` like any pending record (a card's summary goes through the card's own in-place write). These passes, and `sleep_pass` once per night, refuse a home opened without `task_queue=True` before writing anything; `report_only` reads still run.

`system.tasks` is a `MemoryTaskQueue`:

- `enqueue(kind, target_id, *, scope, owner_id, basis, strength, cause, assertion_id="", basis_version=0, priority=None, depends_on=(), not_before=None, windows=None, cost_hint=None, max_attempts=3, ripple_id=None, hop=None, now=None) -> {task_id, enqueued, superseded, reason?}` — idempotent (`task_id = hash(kind|target|basis)`). `strength` in [0, 1] is the incoming memory's, change's or surprise's signal. A basis older than the record's current version is refused (`reason="stale_basis"`); a newer one supersedes the older pending task.
- `select_for_window(budget_seconds, sensitivity=1.0, *, window="turn", scopes=None, kinds=None, capabilities=None, hard_cap=64, cost_of=None, now=None) -> dict` — a pure read: the tasks this window should run, highest activation first. Each task's activation is `activation(strength, sensitivity) = 1 / (1 + e^-6(sensitivity·strength − 0.5))` (ADR 0001 decision 7); a task is a candidate at or above the floor 0.1. Candidates are taken while their cost fits `budget_seconds`, up to `hard_cap`, and at most 20 ripple reconsiderations. There is no fixed count: the host's Mind setting is the `sensitivity` and the `hard_cap`. Cost per task: `cost_of(task) -> seconds` when given, else the median `result.seconds` of the kind's recent completed tasks, else `DEFAULT_TASK_SECONDS`. Returns `{window, budget_seconds, sensitivity, hard_cap, gate, at, tasks: [task + activation + cost], planned_seconds, left_out: [{task_id, kind, target_id, reason, activation, cost_seconds}], left_out_counts}`. Every live task is either selected or left out with its reason: `below_gate`, `over_budget`, `hard_cap`, `window`, `blocked` (a dependency is pending), `not_before`, `leased`, `ripple_window_cap`, `scope`, `filtered`.
- `claim(tasks, *, holder, lease_seconds=600, window=None, now=None) -> {claimed: [task], refused: [{task_id, reason}]}` — lease a selection (its window and its `left_out` are recorded) or a list of task ids. Each claim spends one attempt; an expired lease returns the task; a task claimed `max_attempts` times without settling fails.
- `ack(task_id, *, holder, result, now=None) -> {acked, reason?, task?}` — settle a leased task as done (for example `{"outcome": "unchanged", "seconds": 41.2, "tokens": 3120, "run_id": ...}`); a task a verb already settled returns `reason="already_done"`.
- `release(task_id, *, holder, outcome, reason, until=None, detail=None, now=None) -> {released, task?}` — `outcome="retry"` (attempt spent; failed at `max_attempts`), `"defer"` (no attempt spent; not before `until`, for an unreachable endpoint or embedder), `"skip"` (terminal, for example `reason="over_context"` with the measured tokens in `detail`).
- `left_out(*, holder=None, window=None) -> list[dict]` — what the last claimed window of each `(holder, window)` left out, and why.
- `task(task_id)`, `tasks(*, status=None, kind=None, target_id=None, ripple_id=None, limit=0)`, `log(task_id)`, `counts()`, `cost_of(task)`, `supersede_stale(system)`, `supersede_target(target_id, *, reason)`.

On `MemorySystem` (and as module functions taking the system first):

- `understanding_debt(*, scopes, methods=None) -> dict` — a pure read of what is still mechanical: `{debt: {task kind: {record kind: n}}, total, unqueued, queue: {kind: {status: n}}, by_capability, oldest_pending, methods}`. `methods` widens the label set counted as debt.
- `enqueue_debt(*, scopes, cause="backfill", priority=90, dry_run=True, methods=None, kinds=None) -> dict` — the backfill: one task per debt record that has none. Strength comes from lived use, `0.1 + 0.9 · ln(1 + n) / ln(1 + n_max)` over the records' selected counts, so the most-used mechanical memories run first. Dry-run by default.
- `task_packet(task_id, *, token_budget=56000) -> dict` — everything a reader needs for one task: the target's `record_understanding`, `expected_version` for the compare-and-set, the `verbatim` reference, and its `sources` (summary), `evidence` (card) or `mentions` (dream), newest first. An item that does not fit the budget is left out whole and listed in `left_out`; no text is cut. `target_state` says when the target was closed or is gone.

`maintenance_due(..., tasks=system.tasks)` reports `pending_tasks` and is due when ripple work or night-only work (dream narrations, ripple consolidations) is pending. The gate's constants and their calibration live in `activation_gate.py` (`GATE_K=6`, `GATE_THETA=0.5`, `GATE_FLOOR=0.1`, `DECAY=0.5`, `MAX_HOPS=2`, `RIPPLE_BUDGET=20`, `RIPPLE_WINDOW_CAP=20`, `CHANGE_MAGNITUDE`, `RELATION_WEIGHTS`).

### Ripple: a change reconsidered through connected memories

Source: [`src/abstractmemory/ripple.py`](../src/abstractmemory/ripple.py) (ADR 0001, v1). When a memory's meaning changes, the ripple reconsiders the memories connected to it, hop by hop, until the activation falls below the gate's floor. Memory decides which memories are reconsidered and records why; the host's reader decides what each now means. It runs over the [task queue](#the-memory-task-queue-understanding-in-the-background), so the home must be opened with `task_queue=True`. All verbs are on `MemorySystem` and exported as module functions.

- `seed_ripple(seed_id, *, cause, change="revised", magnitude=None, cosine_distance=None, surprise=None, reconsider_seed=None, budget=20, dry_run=False, now=None) -> dict` — open a ripple. `cause` is `evidence` for the entity's own revise election (pass the election and its evidence in the cause mapping), or the cause of a rewrite whose reader reported `change` (`revised` or `overturned`). The magnitude is `magnitude` when given, else `measured_change(change, cosine_distance)`: the reader's enum (`CHANGE_MAGNITUDE`: unchanged 0, refined 0.25, revised 0.6, overturned 1.0), scaled down when the vectors show the text barely moved, never up. An election also re-reads the seed itself (hop 0; its neighbours wait for it). `surprise` is the entity's own words, stored as words; no feeling is written. `dry_run=True` writes nothing and returns the hop-1 decisions. Idempotent on (seed, cause, seed version). Returns `{ripple_id, opened, magnitude, decisions, reconsider_task_ids, left_out}`.
- Candidates of a source: record edges in both directions (reliance by relation, `RELATION_WEIGHTS`: summarizes / derived_from / refines 1.0, answers / supports / part_of 0.75, continues / from_session / reflected_in 0.5, mentions 0.25; `written_amid` and usage trails carry nothing), the world-model cards whose evidence holds the source, and the source's nearest digests by vector (`similarity_weight` of the cosine). A candidate's potential is the received impact × reliance × `DECAY` (0.5), accumulated over every source of the same ripple; it is reconsidered when `logistic(potential)` reaches the floor (potential ≥ 0.134), at most `MAX_HOPS` (2) hops out, at most `budget` reconsiderations per ripple, and once per ripple. Only the seed owner's memories are candidates. Every gate decision is stored with its potential: `reconsider`, `below_floor`, `refractory`, `closed`, `protected`, `max_hops`, `budget`. `protected` (the entity's own acts, diaries, consolidation records, review offers), `max_hops` and `budget` candidates are listed in the ripple's `left_out` with their potential; a budget stop also warns `#[WARNING:TRUNCATION]`.
- `settle_reconsideration(task_id, *, holder, outcome, change=None, cosine_distance=None, result=None, now=None) -> dict` — settle a `ripple.reconsider` task. `outcome="unchanged"` acks it and writes nothing. `outcome="rewritten"` follows the host's `rewrite_digest(..., cause={"cause": "ripple", ...}, task_id=task_id)`; the memory's onward impact, `min(received, measured)`, is handed one hop further (the distance the rewrite measured is used when `cosine_distance` is omitted). Returns `{ripple_id, outcome, onward, decisions, status}`.
- When no reconsideration is live, the ripple settles; if two or more memories changed it enqueues one `ripple.consolidate` task, leased only in a `night` window. `form_consolidation(task_id, *, holder, text, title, author, reader=None, sources=(), keywords=(), now=None) -> dict` forms the first-person "what this changes" record: kind `summary`, `summary_role: re-understanding`, `summarizes` edges to every changed memory, `derived_from` the seed, never batch-rewritten.
- `refresh_ripples(*, now=None) -> list` — close ripples whose reconsiderations were all settled, skipped or failed (call it when a window ends).
- `revert_ripple(ripple_id, *, by=None, reason=None) -> list` — restore, as new versions, what the ripple changed.
- `ripples(*, scope=None, owner_id=None, status=None, limit=50) -> list` and `ripple(ripple_id) -> dict` — the ripples (`open`, `settled`, `consolidating`, `consolidated`) with their cause, magnitude, surprise, budget, changed members and `left_out`; `ripple` adds the member tasks and every gate decision.

A `ripple.reconsider` packet (`task_packet`) carries `ripple`: the cause and surprise words, the seed's current reading and the one it replaced, how the memory was reached (`from`, `via`, `hops`) and the impact it received; a consolidation packet carries every change with its before and after. The ripple closes nothing.

### Identity: spark, engram, self core, floors

- `DEFAULT_SPARK_TEMPLATE` — the canonical six-key spark (`name`, `origin`, `values`, `purposes`, `traits`, `honesty`); its values include the framework-level core value `shared_vulnerability` (`SHARED_VULNERABILITY_STATEMENT`).
- `lint_spark(spark, *, framework=True) -> list[str]` — charter lint (ERROR/WARNING strings): section caps, 1–3-sentence behavioral statements, explicit `class` per value; framework sparks must carry `shared_vulnerability` (`framework=False` is the explicit override).
- `canonical_spark_hash(spark) -> str` — the one hash definition shared by the engram guard and host-side spark verification.
- `engram(system, spark, *, scope="self", owner_id, spark_artifact_ref=None) -> EngramResult` — turn a linted spark into the identity core: value/purpose/trait records (honesty items are traits with `trait_class="limit"`), each bound prompt-active. Idempotent by spark hash; a modified spark under the same version is refused; a higher version is refused while the born core remains prompt-active (re-engram is an exceptional repair, not an amendment path). `EngramResult` carries `record_ids` per section, `binding_ids`, `warnings`, `created`.
- `self_records(*, scope, owner_id, spark_version=None) -> list[TripleAssertion]` — the folded identity read: prompt-active and closure-folded, identity kinds only, ordered kind rank → precedence → record id. Identity evolves at record level (close the old record, form and bind the new one); the journal's time axis is the version history.
- Floors and targets: `SELF_FRACTION_FLOOR = 0.05` (summoned entities run at or above it; the engine keeps accepting lower values for non-entity callers) and `ENTITY_CONTEXT_FLOOR = 40_000` (= `ENTITY_CONTEXT_RECOMMENDED`; a soft recommendation since the operator's 2026-08-01 re-ruling) with `entity_recall_budget(...)` (see seam types).

### Valence and gradation

Orthogonal to attention by contract: valence never touches activation, never gates candidates, and the retrieval pipeline never reads it (enforced at behavior and import level).

- `appraise(target_id, *, sign, magnitude, reason, scope, owner_id, value_refs=(), scar=False, bond=False, event_id=None, actor="runtime", provenance=None, trace_id=None) -> list[str]` — deposit one signed appraisal (sign ±1, magnitude 1..10). Amplitude authority: magnitude > 3 requires actor `entity-reflection`/`operator` or `provenance["outcome_class"]=="catastrophic"`. `scar=True` (requires sign −1) / `bond=True` (requires sign +1) write an explicit standing marker alongside (`"{event_id}:scar"` / `"{event_id}:bond"`); markers are never auto-created.
- `heal_scar(scar_event_id, *, reason, lesson_record_id=None, scope, owner_id, event_id=None, actor="entity-reflection") -> str` and `break_bond(bond_event_id, *, reason, scope, owner_id, event_id=None, actor="entity-reflection") -> str` — append-only resolutions with deterministic default ids (`heal:{id}` / `break:{id}`). A betrayal-scale scar (magnitude ≥ 8 after the bond) breaks it without an explicit call.
- `gradation(target_ids=None, *, scope, owner_id, at_seq=None) -> dict` — derived dual-channel standing per target: `{net, positive, negative, positive_count, negative_count, scarred, bonded, contributions}`. G⁺/G⁻ accumulate chronologically, each clamped 0..100 — ambivalence is preserved. Presentation: unhealed scar → `net = min(net, 0)`; unbroken bond → `net = max(net, 0)`; both → exactly 0 with both flags visible. `target_ids=None` enumerates every appraised target; requested targets with no events return the neutral shape. No decay of any kind: plasticity comes only from new evidence and resolutions.
- `compute_gradation(events, *, config=GradationConfig()) -> dict[str, GradationScore]` — the pure fold behind `gradation` (`GradationConfig(channel_clamp=100.0, break_magnitude=8.0)`).
- `GradationScore` — one target's standing: `positive`, `negative`, `positive_count`, `negative_count`, `net`, `scarred`, `bonded`, `contributions`. The two channels are reported separately so ambivalence survives the fold.

Targets are anything nameable — records, people, tools, ideas, places, moments in time. Namespace-prefixed free strings are the convention (`person:ada`, `tool:web_search`, `time:morning`); there is no registry.

Two reads serve feelings without depositing any ([`feelings_reads.py`](../src/abstractmemory/feelings_reads.py)):

- `feelings_about(journal, target, *, scope_pairs, gradation_config=GradationConfig(), as_of_seq=None, limit=12) -> dict` — the why-walk for one target: "why do I feel this?", answered from the appraisal stream itself, only when the caller reaches for it.
- `stimulus_feelings(store, journal, stimulus, scope_pairs, *, gradation_config=GradationConfig(), as_of_seq=None, min_net=2.0, max_feelings=5, warnings=None) -> list` — standing feelings for the targets the current stimulus touches. Feelings COLOR content; they never select it.

### Diary reads and chain verification

- `open_questions(store, *, scope, owner_id, limit=100, journal=None)` — `diary_type="question"` entries no later entry answers (`attributes.answers`; either id namespace).
- `open_problems(...)` (same signature) — unresolved `diary_type="problem"` entries (`attributes.resolves`).
- `open_ideas(...)` (same signature) — incubating `diary_type="idea"` entries; with a journal, the folded binding lifecycle decides (inactive_candidate/reviewed incubate; rejected and promoted leave the open set).
- Pass the `journal` to apply closure/hidden folds; without it these are layer-1 store reads. All three return rows oldest-first; resolved entries stay retrievable as ordinary records.
- `open_commitments(store, *, scope, owner_id, limit=100, journal=None)` — standing PROMISES (prospective memory): `diary_type="commitment"` entries no other entry fulfills (`attributes.fulfills`, mirroring answers/resolves). Kept commitments stay retrievable — "I promised, then I kept my word".
- `triggered_commitments(store, journal, *, stimulus, scope, owner_id, max_lines=3, now=None) -> list` — a pure read the host calls beside `reconstruct`: which OPEN commitments does the current stimulus trigger (person appears, topic matches, date passes)? Nothing executes a commitment; this surfaces it at the right moment so the entity can keep its word or consciously let it go.
- `verify_diary_chain(store, *, scope, owner_id) -> {"intact", "break_at", "entries"}` — audits the content-hash chain of owner-direct entries (`prev_entry_hash`/`entry_hash`); entries that make no chain claim fail nothing.
- `diary_entry_hash(title, digest, observed_at) -> str` — the chain's content hash (sha256).

### Consolidation (sleep and dreams)

Source: [`src/abstractmemory/consolidation.py`](../src/abstractmemory/consolidation.py). Deterministic maintenance — no LLM calls; all pure reads except the single dream record a pass may form.

- `structural_report(store, journal, *, scopes, as_of=None) -> dict` — pure structural analysis: connected components, isolated records, duplicate titles, facet coverage, adjacency. Components are computed over `COMPONENT_RELATIONS` edges only (semantic authored relations: `summarizes`, `from_session`, `reflected_in`, `continues`, `derived_from`, `answers`, `supports`, `part_of`). `CONTEXT_RELATIONS` (`written_amid`, `mentions`) and unknown predicates never define components; their pairs are reported as `context_pairs` (already-associated), unknown predicates are named in `unknown_relations`, and co-use trails are reported separately as `trail_pairs` — habit, never adjacency.
- `dream_pass(system, *, scopes, owner_id, salience_floor=2, max_sources=8, embedder_similarity_floor=0.35, report_only=False, as_of=None) -> dict` — the night's DREAM sub-phase: report → cross-component bridge proposals (≥ 2 shared facets, participant + facet, or stored-vector cosine ≥ floor) and single-facet questions → at most ONE `kind="dream"` record (review-gated, `interpretation_required`, weak `mentions` edges to sources, idempotent by report fingerprint). Pairs already associated by trails or context edges are excluded and counted (`trail_associated`, `context_associated`). A quiet night forms nothing and says why. The dream forms with its title and summary pending (the night's composed text is its provisional body; a home without a task queue is refused). Unresolved dreams chain via `parent_dream_ids`. The result carries the night's `signals` and `signals_omitted` (the same stream the dream record rests with; empty on a quiet night). A narration is added beside the dream's summary with `narrate_dream`.
- `unresolved_dreams(store, *, scope, owner_id, journal=None, limit=100) -> list` — standing dreams with `continuation_state="unresolved"`, oldest first.
- `sleep_pass(system, *, scopes, owner_id, ..., should_continue=None) -> dict` (in `maintenance.py`) — ONE FULL NIGHT in canonical order: `resolution` (`resolve_dreams_pass` — the day answers the night) → `maintenance` (`consolidation_pass` tending) → `world_models` (`world_model_pass` orientation cards) → `dream` (`dream_pass`). The result names its sub-phases (`phases` tuple) and carries each sub-phase's self-describing dict. **Graceful cancellation** (one-active-phase ruling): `should_continue` is a zero-arg host callable checked at sub-phase boundaries — the running sub-phase completes (never torn), later ones skip with `skipped_reason="cancelled: …"` and the night carries `cancelled_after`; cancelled shapes mirror the real pass shapes key-for-key. A cancelled night is valid: idempotent sub-phases mean the next sleep resumes the work.

Sleep proposes; waking evidence disposes: the passes write no load-bearing edges and deposit nothing (counters untouched).

### Replay stream

`export_replay(*, scope=None, owner_id=None, since_seq=0, until_seq=None, families=None, enrich=True) -> Iterator[dict]` — on `MemorySystem`, and as a module function `export_replay(store, journal, ...)`.

Yields verbatim journal records as envelopes in strict seq order: `{stream, stream_version, seq, family, observed_at, scope, owner_id, trace_id, turn_id, run_id, payload, display?}`. One shape serves history scrub and live tail (poll with your last seen seq as `since_seq`; it is exclusive, `until_seq` inclusive, `None` = high-water at call time).

- Families: `event`, `binding`, `closure`, `trace`, `snapshot`, `valence` (the default). `family="host"` is reserved for host-authored markers (accepted by the filter, never emitted by this package). The opt-in family `revision` (`OPT_IN_FAMILIES`) is emitted only when you name it: one envelope per understanding version (payload = the `UnderstandingVersion`, `run_id` lifted from its first ledger source), so a rewrite adds nothing to the default stream.
- Correlation keys (`trace_id`, `turn_id`, `run_id`) are always present, null when absent.
- Enrichment resolves `{record_id, kind, title, token_estimate}` from the store (both members for `co_selected` pairs) and `graph_id` for formed records — absent when unresolvable, never fabricated. Diary display blocks arrive `{"redacted": "diary", "graph_id": ...}`: topology visible, content sealed; they carry who wrote the entry, when and why (`authored_by`, `understood_at`, `cause`), never its words.
- Formed non-diary records also carry the current reading's provenance (`understanding_fields`): `digest_method`, `digest_version` (0 = never rewritten), `version_count` (1 = never rewritten), `authored_by` (`{kind, id}`), `reader` (`{provider, model, thinking}`, when a model wrote it), `understood_at`, `cause`; cards add `target`, `target_type`, `card_revision`, `source_count`; dreams add `narrated`, `narration_version`; a superseded record adds `replaced_by`. `binding` and `revision` envelopes also carry the current `digest` text.
- Under family filters or redaction, seq gaps are expected and carry no meaning. The stream is an observability surface — not a payload export, not a second source of truth, not a checkpoint format.

### Entity identity card

`entity_card(*, scope_pairs, owner_id, current_window_events=200, top_n=5, as_of=None) -> dict` — on `MemorySystem`. The same composition is exported as the module function `identity_card(store, journal, *, scope_pairs, owner_id, ...)` in [`entity_card.py`](../src/abstractmemory/entity_card.py), for callers holding a store and journal rather than a facade.

One composed pure read over a home's scope ladder (for example `[("self", eid), ("diary", eid), ("life", eid)]`), returning: `identity` (folded self core, spark version; `name` is the owner identity string), `age_and_context` (journal seq, record counts by kind per scope, diary entry count, first/last `observed_at` — timestamps only, never wall-clock now), `current_state` (a trailing window over the most recent appraisal events — current is a window, not a point), `likes_dislikes` (top targets by G⁺ and by G⁻ reported separately; record-backed targets carry resolved titles), `questions` (open and resolved, via the answers/resolves convention), `key_moments` (magnitude ≥ 8 valence events plus firsts — first dream, first interest, first supersession — chronological, most recent 20), and `discoveries` (open interests, unresolved dream count). Every section carries a `provenance` string naming its source.

Composing the card deposits nothing, and `as_of` anchors both journal signals and record existence (a card at seq T describes the entity at T; a question answered after T reads open at T).

---

## Deliberate reach: probe, expansion, familiarity

Source: [`src/abstractmemory/probe.py`](../src/abstractmemory/probe.py), [`src/abstractmemory/concept_anchor.py`](../src/abstractmemory/concept_anchor.py). Reconstruction is what a stimulus pulls; a probe is what the entity *reaches* for on purpose, with a stated reason.

- `probe(store, journal, *, stimulus, scopes, reason, effort="standard", embedder=None, excluded_ids=None, config=ReconstructConfig(), as_of_seq=0, trace_id=None, write_journal=True) -> ProbeResult` — one deliberate reach. Pure over the store; journal writes are the trace plus inert audit events. `write_journal=False` writes nothing.
- `probe_expand(store, journal, *, record_ids, reason, depth=1, max_records=12, token_budget=1600, excluded_ids=None, scope_pairs=(), parent_trace_id=None, as_of_seq=0, trace_id=None, write_journal=True, edge_limit_per_node=64) -> ProbeResult` — bounded source expansion from chosen records: BFS over record edges in BOTH directions, depth/count/token bounded, closure and hidden folds honored. Root ids resolve through both namespaces (row ids and graph ids); unknown roots refuse loudly.
- `familiarity(store, *, stimulus, scopes, effort="quick", ...) -> dict` — pre-answer metamemory: "do I hold any trace near this topic, and how much?" Reports match DENSITY, never content — the anti-fabrication reflex, so a caller can tell "I know nothing here" from "I hold a lot" before composing an answer.
- `PROBE_EFFORTS` — the `quick` / `standard` / `deep` presets, each a `ProbeBudget`.
- `ProbeBudget` — `max_candidates`, `max_hits`, `token_budget`, `concept_expansion`, `concept_tuning`, `keyword_discovery`, `expand_depth`, `expand_max_records`, `expand_token_budget`. All bounds are hard.
- `ProbeHit` — `record_id`, `graph_id`, `title`, `digest`, `scope`, `owner_id`, `kind`, `relevance`, `cues`, `token_estimate`, `observed_at`.
- `ProbeResult` — `trace_id`, `as_of_seq`, `hits`, `dropped`, `channels`, `warnings`, `budget_spent`.
- `concept_terms(text, *, bigrams=True) -> list[str]` — normalized concept tokens: identifier-aware words plus adjacent-word bigrams joined with `_`. Variants collapse — `auto-memory`, `auto memory`, `autoMemory` and `auto_memory` all yield `['auto', 'memory', 'auto_memory']`.
- `expand_by_concepts(store, seeds, scope_pairs, *, excluded_ids=(), tuning=ConceptAnchorTuning()) -> (admissions, warnings)` — co-occurrence expansion: records sharing a DISCRIMINATIVE concept with a seed surface as admissions.
- `ConceptAnchorTuning` — `min_sources`, `max_sources`, `scan_limit`, `max_admissions`, `max_seed_concepts`, `bigrams`.

## Situating a past moment

Source: [`src/abstractmemory/situate.py`](../src/abstractmemory/situate.py).

- `situate(store, journal, *, scopes, at=None, seq=None, participant=None, occurrence="first", budget=SituateBudget(), attention_config=AttentionConfig(), config=ReconstructConfig()) -> dict` — rebuild the context of one past moment. Pure read: writes nothing, deposits nothing, and every record-shaped result is labeled historical. Address the moment by timestamp (`at`), journal seq (`seq`), or a `participant`'s first/last appearance.
- `situate_prompt_block(situation) -> str` — render one `situate()` result as a labeled prompt block. The caller owns where it lands in the prompt.
- `SituateBudget` — `window_records`, `activity_top_k`, `diary_entries`, `tensions`, `identity_delta`, `token_budget`, `moment_trace_walk`. A bound of zero means NOTHING of that section (`<= 0` is never "unlimited" in this package); negatives refuse loudly.

## World models (orientation cards)

Source: [`src/abstractmemory/world_model.py`](../src/abstractmemory/world_model.py), [`src/abstractmemory/world_model_alias.py`](../src/abstractmemory/world_model_alias.py). A card is what the entity currently holds about one target (a person, a topic), revised append-only. `world_model_pass` (sleep) and `world_model_update` (per turn) form each card PENDING its authored title and summary: `pending=("title", "summary")`, its evidence briefing (`mechanical-card-v2`, or the carried authored lead plus "Since then", `authored-card-v1+delta`) the provisional body; an authored title carries to the next revision (`pending=("summary",)`), the legacy "World model: <subject>" label never does. The key (`attributes.target`), evidence fingerprint, sources and revision are the pass's; the key never depends on the title. Each verdict carries `pending`.

- `current_world_models(store, *, scope, owner_id, journal=None) -> dict` — target → the CURRENT (closure-folded, highest-revision) card. `journal=None` is the layer-1 read with no fold.
- `standing_world_models(store, *, scope, owner_id, journal=None) -> dict` — target → ALL standing card assertions, revision ascending. More than one per target means an interrupted revision; the sleep pass repairs it.
- `author_world_model(system, *, target, text, scope, owner_id, author="entity-reflection", in_place=True, reader=None, sources=(), cause="formation", expected_version=None, expected_fingerprint=None, task_id=None) -> dict` — replace a card's words with AUTHORED prose. The engine never invents text. By default the card is rewritten in place: it keeps its id, revision, evidence and usage, and the previous text is kept as a version (field `card`). `author` is `{kind, id}` (see [understanding](#understanding-in-place-rewrites-and-versions)) or a label string (recorded as author kind `unrecorded`). `expected_fingerprint` is the evidence the author read: when the card's evidence changed since, the call raises `ValueError`. On a card whose summary is pending, the text is its summary (the marker clears, `digest.author` is done) and a pending title stays pending; handing back the provisional body raises `ValueError`. `in_place=False` forms revision N+1 and supersedes the prior card instead: the authored summary with the prior's authored title, else `pending=("title",)`. Returns `{target, card_id, revision, applied, digest_method, in_place, version?, pending?}`; byte-identical text returns `applied=False`.
- `world_model_update(system, *, scopes, owner_id, targets, scan_limit=400, tuning=SleepTuning()) -> dict` — the per-turn incremental update: revise the named targets' cards from a bounded newest-window evidence scan. Eventual-consistent by contract — the sleep pass normalizes over the full evidence.
- `alias_map(store, *, scope, owner_id, journal=None) -> dict` — alias → primary target, read from current cards. Derived state; the cards are the record.
- `alias_candidates(by_target, *, existing=None, overlap_floor=ALIAS_OVERLAP_FLOOR) -> list` — merge PROPOSALS from evidence overlap. Report data only; nothing forms.
- `alias_world_model(system, *, primary, alias, scope, owner_id, reason, actor="operator") -> dict` — the deliberate act that binds an alias to a primary card. The new revision carries the card's authored title and summary; what is not authored forms pending.
- `rekey_world_model(system, old_key, new_key, *, scope, owner_id, author, cause, reason=None, reader=None, sources=()) -> dict` (also `MemorySystem.rekey_world_model(old_key, new_key, ...)`) — move the standing card keyed `old_key` to `new_key` IN PLACE, keeping `old_key` as an alias. An interest's card is keyed on the subject head of the interest's title (`world_model.interest_target`; an interest whose title is pending keys on its own graph id, `topic:<graph id>`, never on its body, and `retitle` re-keys its card when the title lands), so retitling the interest moves the key the next `world_model_pass` computes; without a re-key that pass forms a second card beside the standing one. The card keeps its record id, assertion id, revision, evidence fingerprint, sources, text, title, keywords, vector, edges, versions and usage; `attributes.target` becomes `new_key`, `old_key` joins `attributes.aliases` (a person card's `participants` follow), so `current_world_models` holds one card for the subject, `alias_map`, mentions and `world_model_update(targets=[old_key])` resolve the old key to it, and the pass groups evidence under either key onto it (an interest still titled with the old words keeps clearing the floor). The move is a version row (field `target`: version 0 the old key, author mechanical, cause formation; version N+1 the new key with `author`, `reader`, `sources`, `cause` plus `reason` and `rekey: {from, to}`), `target_version` / `target_provenance` on the row; no embedder is called (the key is not in the canonical text) and pending `card.author` tasks stay. The title is not touched: `retitle` the card for that. Arguments are validated like `retitle` (bad ones raise `ValueError`, as do empty or equal keys). Returns the understanding result shape (`field="target"`) plus `old_key`, `new_key`, `card_id`, `revision`, `aliases`; `outcome="unchanged"` when the card on `new_key` already answers to `old_key`. Refusals (nothing written): `unknown_card`, `target_taken` (`new_key` already has a different standing card: the two must be merged, which this verb does not do), `alias_bound_elsewhere` (`new_key` is an alias of another card), `stale`. Run it with the home's writer lease.

## Drives: what is alive and pressing

Source: [`src/abstractmemory/alive_drives.py`](../src/abstractmemory/alive_drives.py), [`drive_pressure.py`](../src/abstractmemory/drive_pressure.py), [`drive_grouping.py`](../src/abstractmemory/drive_grouping.py), [`cognition_health.py`](../src/abstractmemory/cognition_health.py). Drives are the standing open questions, problems, ideas, commitments, and unresolved dreams.

- `alive_drives(system, *, scopes, k=5) -> list[dict]` — the top-k alive drives as handle-shaped items, strongest first. Aliveness combines co-use trail activation with recency. Each item carries `record_id`, `kind`, `drive`, `title`, `digest`, `born_at`, `origin`, `aliveness`, and `alive_via`; a `digest_truncation` key appears only when the digest was cut. `aliveness` is within-read ordering currency only — never render it as a cross-day meter.
- `drive_pressure(store, journal, *, scopes) -> dict` — the standing drive sets folded across a scope ladder. Counts are journal-folded, so a retracted question is not pressure.
- `drive_groups(items, *, min_shared_terms=GROUP_MIN_SHARED_TERMS) -> list` — cluster drive items by shared discriminative terms. Pure, deterministic, order-independent.
- `open_drive_partition(store, journal, *, scopes) -> dict` — ONE partition over the full open drive families, the fold every grouping consumer reads, so day and sleep lanes can never group different corpora.
- `cognition_health(store, journal, *, scopes) -> dict` — the drive ratios as one compact dict.

## Candidates, disposal, and deliberate acts

Source: [`src/abstractmemory/candidate_miner.py`](../src/abstractmemory/candidate_miner.py), [`disposal.py`](../src/abstractmemory/disposal.py), [`identity_review.py`](../src/abstractmemory/identity_review.py). Machines propose; the entity or the operator disposes. Nothing here discharges a drive on its own.

- `mine_candidates_pass(system, *, scopes, owner_id, max_candidates=2, report_only=False, as_of=None, scan_limit=0, tuning=SleepTuning()) -> dict` — one mining pass: lesson candidates (resolved tensions that lived across sessions), interest candidates (recurring un-elected themes), and question-resolution proposals. Bounded and idempotent. Each offer forms pending its authored title and summary (the result's `title` is a report label, never stored).
- `resolve_questions_pass(store, journal, *, scopes, ...) -> dict` — open questions and problems matched against LATER evidence. Proposals only, zero writes: a machine record must never discharge a drive. Only a diary entry with `answers=`/`resolves=` closes one.
- `promote_candidate(store, journal, *, record_id, scope, owner_id, corroborating_ids, reason, min_origins=2, prompt_state=None, actor="operator") -> dict` — promote an inactive candidate, with the independence test.
- `reject_candidate(store, journal, *, record_id, scope, owner_id, reason, hide=False, actor="operator") -> dict` — the honest no: `lifecycle="rejected"` with a mandatory reason. The record stays indexed unless `hide=True` — judgment is not erasure, and hiding is a separate stated act.
- `confirm_relation(store, journal, *, source_id, relation, target_id, evidence_ids, reason, proposed_by=None, actor="operator") -> dict` — turn a proposal into a real typed edge. Idempotent by (source, relation, target). Journals one inert `cited` audit event per endpoint: confirming is judging, not using, so it must not pump activation.
- `dispose_dream(system, *, dream_id, disposition, reason, relation=None, source_id=None, target_id=None, evidence_ids=(), actor="operator") -> dict` — one call for the whole dream verdict.
- `enact_realization(store, journal, *, realization_id, supersession_record_id, reason, actor="entity-reflection") -> dict` — the entity's adoption of a held identity-amendment proposal.
- `identity_review_pass(system, *, scopes, owner_id) -> dict` — pending identity-amendment proposals and their bar states. Deposits nothing, writes nothing.

## Tending elections

Source: [`src/abstractmemory/tend.py`](../src/abstractmemory/tend.py). Tending is the entity electing what to keep, revise, or let go, expressed as a parsed block and applied through existing engine verbs.

- `parse_tend_block(text, *, max_elections=5) -> {"elections": [...], "refusals": [...]}` — parse one ` ```tend ` block body. Refusals are data, not errors.
- `apply_tend_elections(system, elections, *, scope, owner_id, actor, channel=None, now=None, self_pairs=(), revisit_depth=1, revisit_max_records=12, revisit_token_budget=1600) -> dict` — apply parsed elections through the existing verbs.
- `IDENTITY_SCOPE_PENDING_RULING` — the refusal message for identity-scope tending, which is deliberately not implemented pending a ruling.

## Recall diagnostics and rendering

Source: [`src/abstractmemory/recall_reads.py`](../src/abstractmemory/recall_reads.py), [`origin_diversity.py`](../src/abstractmemory/origin_diversity.py), [`render_order.py`](../src/abstractmemory/render_order.py), [`recent_records.py`](../src/abstractmemory/recent_records.py). These answer "why did (or didn't) this surface?" without changing what surfaces next.

- `recall_history(journal, record_id, *, limit_traces=200, until_seq=None, store=None) -> dict` — the record's part in recent reconstructions, newest first.
- `explain_recall(store, journal, record_id, *, trace_id=None) -> dict` — "why did or didn't record X surface in THIS recall?" as one serving dict.
- `absence_diagnosis(store, journal, record_id, *, scope, owner_id) -> dict` — structural reasons a record may be unreachable, in plain sentences. An unformed id reads as honestly absent rather than as an error.
- `origin_diversity(handles, *, labels=None, min_counted=ORIGIN_MIN_COUNTED, dominance_floor=ORIGIN_DOMINANCE_FLOOR) -> dict | None` — fold a rendered shelf into its voice diversity. `None` means abstain: too little to judge.
- `stable_render_order(handles) -> list[(handle, rank)]` — reorder ranked shelf handles into the stable render order, so a prefix stays reusable across turns.
- `recent_records(store, journal, *, scopes, since, until=None, kinds=None, limit=RECENT_RECORDS_DEFAULT_LIMIT, as_of=None) -> dict` — formed records newest-first with folds applied. The result carries `truncated` when more exist in the window than the page shows.

## Maintenance, health, and operator tools

Source: [`src/abstractmemory/maintenance.py`](../src/abstractmemory/maintenance.py), [`sleep_cadence.py`](../src/abstractmemory/sleep_cadence.py), [`mind_mass.py`](../src/abstractmemory/mind_mass.py), [`redigestion.py`](../src/abstractmemory/redigestion.py), [`reembed.py`](../src/abstractmemory/reembed.py), [`doctoring.py`](../src/abstractmemory/doctoring.py), [`engine_manifest.py`](../src/abstractmemory/engine_manifest.py).

- `maintenance_report(store, journal, *, scopes, as_of=None, scan_limit=None, tuning=SleepTuning()) -> dict` — pure phase-1 analysis: structure plus an attribute-level scan (near-duplicates, metadata gaps, suppressions). Deterministic; deposits nothing. Every policy number rides `tuning`.
- `maintenance_due(store, journal, *, scopes, since_seq=None, min_new_records=12, min_signal=3, tasks=None) -> dict` — the deterministic cadence predicate (with `tasks`, pending ripple and night-only memory tasks count as due; see [the task queue](#the-memory-task-queue-understanding-in-the-background)). Due when enough new records formed, or when some new material exists and the fragmentation signal clears its floor. A store with zero new formations is never due. Late-local-time remains the host's clock. Bounded by a cursor (0058): for `SQLiteTripleStore` and `InMemoryTripleStore` the answer is folded from the store's `assertions_after` feed, per (store, journal, scopes) in the process, so a check reads only the rows written since the previous check and re-reads the journal's formation bindings only when the journal moved (a repeated check with nothing new costs well under a millisecond). Same answer as the full scan, which other stores (LanceDB) still use.
- `last_maintenance_seq(store, journal, *, scopes) -> int` — journal seq of the newest sleep artifact's formation; `0` means this store has never slept.
- `mind_mass_report(store, journal, *, scopes, days=30, bucket="day", embedder=None, now=None, vector_scan_limit=VECTOR_SCAN_LIMIT, wake_cue_kind="episode") -> dict` — formation cadence, journal mass, duplicate mass, embedding-space integrity, review backlog, and sleep recency, window-bounded. Warnings come from the closed `WARNING_WORDS` set.
- `redigestion_candidates(system, *, scopes, limit=50, min_residue_chars=24, methods=MECHANICAL_DIGEST_METHODS) -> dict` — enumerate the labeled mechanical-digest debt, worst first. Pure read: listing a debt is not using the memories.
- `apply_redigestion(system, entries, *, actor, digest_method="entity-authored", turn_id=None) -> dict` — deprecated (emits `DeprecationWarning`): forms a NEW record per entry and supersedes the old one, so the new record starts with zero usage. Use `rewrite_digest`, which rewrites in place.
- `RedigestionCandidate` — one labeled-mechanical record awaiting authored words, including `poverty` and `content_residue`.
- `reembed_store(system, *, embedder, owner_id, model_id=None, marker_scope="life", reason=..., batch_size=64) -> dict` — re-derive the whole vector index and swap atomically, pin written LAST. `reembed_home` is the same call under the name the operator guide uses.
- `read_embedding_pin(path, *, table_name="triples") -> dict | None` — a pure peek at a store file's embedding pin without opening the store. Raises `ValueError` if `table_name` is not a plain SQL identifier.
- `build_pin(model_id, dimension, *, source, claimed_by=None) -> dict` — the normalized pin payload. At least one of model/dimension must be present: an empty pin would enforce nothing and lie about it.
- `journal_cold_cut(src_path, dst_path, *, cut_seq=0, pair_cuts=None, archive_ref, exported_stream_ref=None, null_retired_embeddings=True, cut_traces=False) -> dict` — rebuild a home store file with the attention-event mass cold-cut.
- `verify_cold_cut(src_path, dst_path) -> {"ok", "checks"}` — parity checks between original and rebuilt file, measured rather than asserted; every check names its own numbers.
- `wake_cue_dedup_pass(system, *, scope, owner_id, actor, kind="episode", jaccard_floor=0.82, min_cluster=3, report_only=False) -> dict` — collapse near-identical same-day records into one day summary. Deliberately conservative: two similar episodes are a life, twenty near-identical ones are a loop artifact. The day summary forms pending its authored title and summary (the witness's digest its provisional body); the pass knows its own summary by `provenance.source` (`DEDUP_SOURCE`) once that summary is written.
- `engine_manifest() -> dict` — the machine-readable engine inventory. Pure and JSON-safe.

## Vocabularies and tuning constants

Closed vocabularies (frozensets) and declared tunables. Constructing a tuning object with defaults changes nothing — the defaults *are* today's behavior.

| Name | Value / meaning |
| --- | --- |
| `MEMORY_RECORD_KINDS` | every valid `record_kind` |
| `IDENTITY_KINDS` | `value`, `purpose`, `trait`, `interest` |
| `DIARY_TYPES` | `question`, `problem`, `idea`, `note`, `lesson`, `reflection`, `commitment` |
| `REFLECTION_FORM_KINDS` | kinds a reflection pass may form |
| `CONSOLIDATION_PROTECTED_KINDS` | never machine-consolidated |
| `REDIGESTION_PROTECTED_KINDS` | never machine-redigested |
| `MECHANICAL_DIGEST_METHODS` | digest methods that count as debt |
| `AUTHOR_KINDS` | `mechanical`, `entity-mind`, `capability-model`, `operator` — who may author a reading |
| `REWRITE_CAUSES` | `formation`, `backfill`, `ripple`, `evidence`, `operator`, `revert`, `repair` |
| `UNDERSTANDING_PROTECTED_KINDS` | never rewritten in place: diary, value, purpose, trait, interest, realization |
| `OPT_IN_FAMILIES` | replay families emitted only on request: `revision` |
| `TASK_KINDS` | `title.author`, `digest.author`, `digest.rewrite`, `card.author`, `dream.narrate`, `ripple.reconsider`, `ripple.consolidate` |
| `WINDOWS` | `turn`, `visit`, `nap`, `cycle`, `night`, `idle` |
| `DISPOSAL_RELATIONS` | relations `confirm_relation` may create |
| `KIND_RANKS` | ordering rank per kind (identity first, derived artifacts last) |
| `WARNING_WORDS` | the closed warning vocabulary of `mind_mass_report` |
| `ENTITY_RECALL_CANDIDATE_CAP` | `100` — the recall candidate pool bound |
| `ENTITY_CONTEXT_ACCEPTABLE` | `200000` |
| `RECENT_RECORDS_DEFAULT_LIMIT` | `24` |
| `VECTOR_SCAN_LIMIT` | `4000` |
| `DRIVE_PRESSURE_BOUND` | `20` |
| `GROUP_MIN_SHARED_TERMS`, `GROUP_OFFER_FLOOR`, `GROUP_BOOST_STEP` | drive-grouping thresholds |
| `FAMILIARITY_MIN_KEYWORD_TOKENS`, `FAMILIARITY_STRONG_THRESHOLD`, `FAMILIARITY_VECTOR_MIN` | familiarity thresholds |
| `ORIGIN_MIN_COUNTED`, `ORIGIN_DOMINANCE_FLOOR` | origin-diversity thresholds |
| `ALIAS_OVERLAP_FLOOR` | `0.6` — alias proposal Jaccard floor |
| `MANIFEST_VERSION` | engine-manifest schema version |
| `ANCHOR_SEQ_ATTRIBUTE`, `ANCHOR_MOMENT_ATTRIBUTE`, `CONTEXT_ANCHOR_FIELD`, `IDENTITY_ANCHOR_FIELD` | attribute/field names hosts stamp for anchoring |
| `SleepTuning` | every sleep-lane policy number, one frozen object |
| `ReconstructConfig` | kind policy and admission knobs for reconstruction |
