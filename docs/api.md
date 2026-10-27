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

`InMemoryTripleStore` and `SQLiteTripleStore` also expose `close_assertion(assertion_id, valid_until) -> bool`: the one in-place change the stores allow. It sets `valid_until` on an assertion whose window is still open and touches nothing else (terms, provenance, attributes, the keyword index and the stored vector stay as written). It returns `True` when a row changed and `False` for an unknown id or a window that is already closed, so a replay is harmless; an empty `assertion_id` or `valid_until` raises `ValueError`. Use it when a later fact supersedes an earlier one and `TripleQuery(active_at=...)` must stop returning the old row from that moment on. The layer-2 `close_assertions` (below) is a different operation: it appends a closure record and leaves the row's window as written. In a mind written through [`MemoryGraph`](#the-memory-graph-revisions-and-provenance), a window is closed by a revision's `close` op, which writes the window and the closure together; a direct `close_assertion` call bypasses the revision log.

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

- `canonical_text(a) -> str` — the shared text rendering stores embed and index (`CANONICAL_TEXT_VERSION` names the current rendering, version 2). Changing this rendering invalidates stored vectors, so it must bump the version and ride a re-embed migration.
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
| `step` | `run_id`, `seq` (int ≥ 0, the ledger row address) | `step_id` | `step:<run_id>#<seq>` |
| `artifact` | `artifact_id` | `run_id` | `artifact:<artifact_id>` |
| `message` | `message_id` | `run_id` | `message:<message_id>` |
| `event` | `event_id` | `stream` | `event:<event_id>` |
| `diary_entry` | `entry_id` | `run_id` (`diary:<entity_id>`) | `diary_entry:<entry_id>` |

Every kind may carry `runtime_id` (which ledger: a plane's runtime or an entity home, since homes travel). An unknown kind, a missing required id, a blank id, a non-int or negative `seq`, an unknown key, or a field another kind owns (an `artifact` with a `seq`) raises `InvalidSourceRef` (a `ValueError`), and so does a `run` or `step` ref naming a run id no ledger can load: `SYNTHETIC_RUN_ID_PREFIXES` = `chat-`, `diary:`, `session_memory_`, `global_memory` (`is_synthetic_run_id(run_id)`; ADR 0003 decision 11: such an id is not a source, the artifact or diary entry it belongs to is). The key is the identity: two refs with the same key are the same source.

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
- `occurred_at` — observation time (when the source said it); `recorded_at` — record time (when this mind learned it; defaults to now and is kept as logged on replay).
- Every time of a revision (`occurred_at`, `recorded_at`, an assert's `observed_at` / `valid_from` / `valid_until`, a close's or narrow's `valid_until`) is parsed as ISO-8601 and normalized to the package's canonical UTC text form (microseconds, `+00:00`, as `utc_now_iso_seconds` writes; naive times are UTC, `Z` is accepted) when the revision is built; anything else ("next tuesday") raises `ValueError`. Stores and queries compare these strings, which is only correct in one form.
- `ops` (`REVISION_OPS`), validated and normalized at construction:
  - `assert` — payload = `TripleAssertion.to_dict()`. Missing `scope`/`owner_id` come from the revision, a missing `observed_at` is the revision's `occurred_at`, a missing `assertion_id` is derived deterministically from the revision id and the op index (so the logged revision replays identically). A `provenance` in the payload is that memory's own; without one the memory carries the revision's.
  - `close` — `{assertion_id, valid_until, kind, replacement_ids, reason, ripple_source, ripple_hops}` with `kind` ∈ `CLOSE_KINDS` = `retract`, `supersede`, `reinterpreted`, `merged`; `supersede` and `merged` require `replacement_ids`. It sets the row's end to the earlier of its current end and `valid_until` (compared as instants: an open window closes at `valid_until`; a claim "valid until December" retracted in March ends in March; an end already at or before it is kept) and writes the journal `ClosureRecord` in the same operation (the revision id, cause, record time and ripple fields ride the closure's `provenance`; its id is deterministic), so `TripleQuery(active_at=...)` and ranked recall agree after every close. A `valid_until` before the claim's `valid_from` raises `ValueError` (an equal one, an empty window, is allowed). A memory is closed once; a second close is reported in `skipped`.
  - `narrow` — `{assertion_id, valid_until, reason}`: moves an already-closed window earlier (`narrow_assertion`). An open window, or a date before the claim's `valid_from`, raises `ValueError` and the whole revision rolls back; a date at or after the current end is a no-op reported in `skipped`.
- `RevisionResult` — `revision_id`, `applied` (`False` when the id was already in the log: nothing changed), `assertion_ids`, `closed`, `narrowed`, `skipped` (`{op, index, assertion_id, why}` for ops that changed nothing) and `seq` (the revision's position in the log).

### `MemoryGraph`

```python
MemoryGraph(store, journal=None)
```

`store` is a `SQLiteTripleStore` (the home store: the graph's tables live in its file) or an `InMemoryTripleStore` (tests, dev; graph state is shared by every `MemoryGraph` over the same store object). Any other store raises `NotImplementedError` (LanceDB: backlog 0057). `journal` receives the `close` ops' closure records; `None` writes none (the history and the revision still record the close).

**`apply_revision(revision) -> RevisionResult`** — the one write path. In order:

1. Pure checks, before anything is read or embedded: every asserted memory and the revision itself must name sources or `derived_from`, else `ProvenanceRequired`.
2. A revision id already in the log returns `applied=False` (nothing embedded, nothing written).
3. Assertions are embedded outside the transaction (as `SQLiteTripleStore.add` does); a first embedded write's pin is written inside it.
4. One transaction: each `derived_from` chain must reach a ledger source (a memory already in the graph counts as grounded; a cycle, a self-derivation or a chain to nothing raises `ProvenanceRequired`); a revision whose ops are all `close`/`narrow` must name a source, or a memory other than the ones it changes, as its cause (`ProvenanceRequired`: citing the closed memory as the reason for closing it names no cause); an assertion id already in the store but never asserted through the graph may only be *adopted* by an `import` or `migration` revision that carries the row as stored (everything but provenance equal, else `ValueError`), which rewrites the row's provenance to the graph shape, keeps the old one in the history and logs it with the op (`adoption: {previous_provenance}`, so a replay reproduces the adoption); re-asserting an id the graph already holds is a reported skip when it is the same claim and a `ValueError` when its terms, scope, owner or `valid_from` differ (a changed claim gets a new id); a `close` or `narrow` may only name a memory of the graph (else `ProvenanceRequired`: adopt it first), and only after the op that asserts it when both are in one revision. Then the triples (with their keyword rows), window changes, closures, history, provenance and derivation rows and the revision row are written; any failure rolls all of it back.

On SQLite with a `SQLiteJournal` on the **same file**, the closures commit in that same transaction, so `TripleQuery(active_at=...)` and ranked recall never disagree. With a journal elsewhere (another file, `InMemoryJournal`) the closures are appended after the commit and the revision is marked `journal_applied = 0` until they are.

Reads (every read is bounded: `limit` must be a positive int and is clamped to `MAX_READ_LIMIT` = 1000; `0`, a negative, a bool or a float raises `ValueError`):

- `history(memory_id, *, limit=200) -> list[dict]` — the memory's lifecycle in record order: `{event: "asserted" | "closed" | "narrowed", at (record time), revision_id, cause, detail}`. `detail` holds the terms, window and sources of an assertion (`adopted` and `previous_provenance` for an adoption), the close payload with `closure_id`, `window_closed` (the op moved the row's end), `previous_valid_until` and `row_valid_until`, or `valid_until`, `previous_valid_until` and `reason` of a narrow. Accepts an assertion id or a record's graph id (resolved to its digest assertion). Unknown id: `[]`.
- `sources_of(memory_id, *, transitive=True, limit=200) -> list[SourceRef]` — the memory's ledger sources; with `transitive`, breadth-first through what it was derived from (deduplicated by key, at most `MAX_LINEAGE_VISITS` = 1000 memories visited).
- `derived_from_source(ref, *, limit=200) -> list[str]` — memory ids grounded in a source: those that name it, then everything derived from them. A `run` ref matches every ref stamped with that run (its own `run` ref and the steps, artifacts, messages and diary entries carrying its `run_id`), once per memory.
- `revisions(after=None, limit=100) -> (list[Revision], cursor)` — the change feed in log order, strictly after the cursor; the returned cursor is `str(seq)` of the last revision (unchanged when nothing is new). Lossless: a revision's position is allocated inside its write transaction and writers are serialized, so no revision is skipped or repeated across calls, also while other connections append. A cursor that is not a number, or one beyond the log's head (another graph's, or invented: it would silently skip every revision below it), raises `ValueError`.
- `replay_into(target) -> int` — re-applies this graph's log, in order, into another `MemoryGraph`; returns how many revisions it applied (ids already there are no-ops, so a replay resumes). Replaying into an empty SQLite home reproduces the original file's triples, keyword index, graph tables and closures exactly, adoptions included.
- `repair(*, limit=1000) -> int` — appends the closures of revisions a crash left with `journal_applied = 0` (only possible with a journal outside the store's file), oldest first; closure ids are deterministic, so it is idempotent. Raises `RuntimeError` when revisions await closures and no journal is attached.

Constants: `DEFAULT_READ_LIMIT` (200), `DEFAULT_REVISION_PAGE` (100), `MAX_READ_LIMIT` (1000), `MAX_LINEAGE_VISITS` (1000), `ADOPTING_CAUSES` (`import`, `migration`), `DIGEST_PREDICATE` (`dcterms:abstract`, how a record's graph id resolves to its digest assertion), `PROVENANCE_KEYS`, `LEGACY_KEYS`, `SYNTHETIC_RUN_ID_PREFIXES`.

Opening a `MemoryGraph` on a home whose graph tables and indexes exist is a read (no DDL transaction): a reader needs no write lock and does not wait behind a writer.

### The graph tables (SQLite)

In the store's file, beside the triple table and the journal's `memj_*` tables (a store with a custom `table_name` prefixes them `memg_<table>_`):

| Table | Columns | Indexes |
| --- | --- | --- |
| `memg_revisions` | `seq` (INTEGER PRIMARY KEY AUTOINCREMENT: the change-feed cursor), `revision_id` (UNIQUE), `scope`, `owner_id`, `cause`, `occurred_at`, `recorded_at`, `ops_json`, `provenance_json`, `summary`, `journal_applied` | `revision_id`; partial index on `seq` where `journal_applied = 0` |
| `memg_provenance` | `memory_id`, `ref_key`, `ref_kind`, `run_id`, `revision_id`, `ref_json`; PRIMARY KEY (`memory_id`, `ref_key`) | `ref_key`, `run_id` |
| `memg_derivations` | `memory_id`, `from_id`, `revision_id`; PRIMARY KEY (`memory_id`, `from_id`) | `from_id` |
| `memg_history` | `seq` (INTEGER PRIMARY KEY AUTOINCREMENT), `memory_id`, `event`, `at`, `revision_id`, `detail_json` | (`memory_id`, `seq`) |

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
- `MemoryHandle` — one scored memory: `record_id`, `kind`, `title`, `digest`, `token_estimate`, `relevance` (per present channel), `activation` (`base_level`/`spread`/`total`), `cues` (human-readable "why"), `binding` (folded `"{search_state}+{prompt_state}"`), `scope`, `owner_id`, `provenance` (including `global_count`), `payload_tiers`, and `admission` — `"self" | "stm" | "stimulus" | "both"` (`"historical"` is reserved). Only `stimulus`/`both` admissions deposit at commit.
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
- `MemoryRecordInput(kind, title, digest, intents=(), outcomes=(), keywords=(), participants=(), edges=(), payload_ref=None, topic=None, confidence=None, attributes={}, provenance={})` — one record to remember. The `digest` (1–3 sentences) is what gets indexed and embedded; `payload_ref` keeps the full verbatim reachable as a host artifact; `edges` are `(relation, target_record_id)` pairs stored as edge assertions; `participants` are identity strings (`person:ada`, `entity:castor`) — co-presence is explicit, and what a record says is its full co-presence.

Record kinds: `memory`, `episode`, `lesson`, `instruction`, `decision`, `claim`, `summary` (requires at least one edge naming what it summarizes), `question`, `answer`, `plan`, the identity kinds `value` (requires `attributes.value_class` ∈ {core, revisable}), `purpose`, `trait`, `diary`, `interest`, and the sleep artifact `dream`. Kind ranks order identity first (value < purpose < trait) and derived artifacts as summary peers.

Diary formation rules: `kind="diary"` requires `provenance.source` ∈ {`diary-projection`, `owner-direct`}; `diary_type` ∈ {note, idea, commitment, reflection, question, problem} (absent defaults to `note`; unknown values raise); projections must carry `attributes.entry_id`; resolution references ride `attributes.answers` (questions) and `attributes.resolves` (problems).

### Bindings and closures

- `bind(record_id, *, scope, owner_id, search_state, prompt_state="inactive", lifecycle="none", source="operator", reason=None, binding_id=None) -> ScopeBinding` — append a visibility event. A folded `hidden` binding removes the record from ranked retrieval in that scope pair only; re-binding `indexed` restores it. `prompt_state="active"` admits the record into the identity (self) component. Record-level bindings hide the digest and its edge assertions together. Direct `store.query` id lookups bypass folds by design.
- `close_assertions(assertion_ids, *, kind, replacement_ids=(), reason) -> list[str]` — append one closure per assertion (`retract` | `supersede` | `reinterpreted` | `merged`).
- `close_record(record_id, *, reason, kind="retract", replacement_ids=()) -> list[str]` — close a whole record (digest and its edges) as one belief-revision act; closure ids are deterministic, so replays dedupe.

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
- `dream_pass(system, *, scopes, owner_id, salience_floor=2, max_sources=8, embedder_similarity_floor=0.35, report_only=False, as_of=None) -> dict` — the night's DREAM sub-phase: report → cross-component bridge proposals (≥ 2 shared facets, participant + facet, or stored-vector cosine ≥ floor) and single-facet questions → at most ONE `kind="dream"` record (review-gated, `interpretation_required`, weak `mentions` edges to sources, idempotent by report fingerprint). Pairs already associated by trails or context edges are excluded and counted (`trail_associated`, `context_associated`). A quiet night forms nothing and says why. Unresolved dreams chain via `parent_dream_ids`.
- `unresolved_dreams(store, *, scope, owner_id, journal=None, limit=100) -> list` — standing dreams with `continuation_state="unresolved"`, oldest first.
- `sleep_pass(system, *, scopes, owner_id, ..., should_continue=None) -> dict` (in `maintenance.py`) — ONE FULL NIGHT in canonical order: `resolution` (`resolve_dreams_pass` — the day answers the night) → `maintenance` (`consolidation_pass` tending) → `world_models` (`world_model_pass` orientation cards) → `dream` (`dream_pass`). The result names its sub-phases (`phases` tuple) and carries each sub-phase's self-describing dict. **Graceful cancellation** (one-active-phase ruling): `should_continue` is a zero-arg host callable checked at sub-phase boundaries — the running sub-phase completes (never torn), later ones skip with `skipped_reason="cancelled: …"` and the night carries `cancelled_after`; cancelled shapes mirror the real pass shapes key-for-key. A cancelled night is valid: idempotent sub-phases mean the next sleep resumes the work.

Sleep proposes; waking evidence disposes: the passes write no load-bearing edges and deposit nothing (counters untouched).

### Replay stream

`export_replay(*, scope=None, owner_id=None, since_seq=0, until_seq=None, families=None, enrich=True) -> Iterator[dict]` — on `MemorySystem`, and as a module function `export_replay(store, journal, ...)`.

Yields verbatim journal records as envelopes in strict seq order: `{stream, stream_version, seq, family, observed_at, scope, owner_id, trace_id, turn_id, run_id, payload, display?}`. One shape serves history scrub and live tail (poll with your last seen seq as `since_seq`; it is exclusive, `until_seq` inclusive, `None` = high-water at call time).

- Families: `event`, `binding`, `closure`, `trace`, `snapshot`, `valence`. `family="host"` is reserved for host-authored markers (accepted by the filter, never emitted by this package).
- Correlation keys (`trace_id`, `turn_id`, `run_id`) are always present, null when absent.
- Enrichment resolves `{record_id, kind, title, token_estimate}` from the store (both members for `co_selected` pairs) and `graph_id` for formed records — absent when unresolvable, never fabricated. Diary display blocks arrive `{"redacted": "diary", "graph_id": ...}`: topology visible, content sealed.
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

Source: [`src/abstractmemory/world_model.py`](../src/abstractmemory/world_model.py), [`src/abstractmemory/world_model_alias.py`](../src/abstractmemory/world_model_alias.py). A card is what the entity currently holds about one target (a person, a topic), revised append-only.

- `current_world_models(store, *, scope, owner_id, journal=None) -> dict` — target → the CURRENT (closure-folded, highest-revision) card. `journal=None` is the layer-1 read with no fold.
- `standing_world_models(store, *, scope, owner_id, journal=None) -> dict` — target → ALL standing card assertions, revision ascending. More than one per target means an interrupted revision; the sleep pass repairs it.
- `author_world_model(system, *, target, text, scope, owner_id, author="entity-reflection") -> dict` — replace a card's words with AUTHORED prose. The engine never invents text: this applies words authored elsewhere through the same append-only revision chain the sleep pass uses.
- `world_model_update(system, *, scopes, owner_id, targets, scan_limit=400, tuning=SleepTuning()) -> dict` — the per-turn incremental update: revise the named targets' cards from a bounded newest-window evidence scan. Eventual-consistent by contract — the sleep pass normalizes over the full evidence.
- `alias_map(store, *, scope, owner_id, journal=None) -> dict` — alias → primary target, read from current cards. Derived state; the cards are the record.
- `alias_candidates(by_target, *, existing=None, overlap_floor=ALIAS_OVERLAP_FLOOR) -> list` — merge PROPOSALS from evidence overlap. Report data only; nothing forms.
- `alias_world_model(system, *, primary, alias, scope, owner_id, reason, actor="operator") -> dict` — the deliberate act that binds an alias to a primary card.

## Drives: what is alive and pressing

Source: [`src/abstractmemory/alive_drives.py`](../src/abstractmemory/alive_drives.py), [`drive_pressure.py`](../src/abstractmemory/drive_pressure.py), [`drive_grouping.py`](../src/abstractmemory/drive_grouping.py), [`cognition_health.py`](../src/abstractmemory/cognition_health.py). Drives are the standing open questions, problems, ideas, commitments, and unresolved dreams.

- `alive_drives(system, *, scopes, k=5) -> list[dict]` — the top-k alive drives as handle-shaped items, strongest first. Aliveness combines co-use trail activation with recency. Each item carries `record_id`, `kind`, `drive`, `title`, `digest`, `born_at`, `origin`, `aliveness`, and `alive_via`; a `digest_truncation` key appears only when the digest was cut. `aliveness` is within-read ordering currency only — never render it as a cross-day meter.
- `drive_pressure(store, journal, *, scopes) -> dict` — the standing drive sets folded across a scope ladder. Counts are journal-folded, so a retracted question is not pressure.
- `drive_groups(items, *, min_shared_terms=GROUP_MIN_SHARED_TERMS) -> list` — cluster drive items by shared discriminative terms. Pure, deterministic, order-independent.
- `open_drive_partition(store, journal, *, scopes) -> dict` — ONE partition over the full open drive families, the fold every grouping consumer reads, so day and sleep lanes can never group different corpora.
- `cognition_health(store, journal, *, scopes) -> dict` — the drive ratios as one compact dict.

## Candidates, disposal, and deliberate acts

Source: [`src/abstractmemory/candidate_miner.py`](../src/abstractmemory/candidate_miner.py), [`disposal.py`](../src/abstractmemory/disposal.py), [`identity_review.py`](../src/abstractmemory/identity_review.py). Machines propose; the entity or the operator disposes. Nothing here discharges a drive on its own.

- `mine_candidates_pass(system, *, scopes, owner_id, max_candidates=2, report_only=False, as_of=None, scan_limit=0, tuning=SleepTuning()) -> dict` — one mining pass: lesson candidates (resolved tensions that lived across sessions), interest candidates (recurring un-elected themes), and question-resolution proposals. Bounded and idempotent.
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
- `maintenance_due(store, journal, *, scopes, since_seq=None, min_new_records=12, min_signal=3) -> dict` — the deterministic cadence predicate. Due when enough new records formed, or when some new material exists and the fragmentation signal clears its floor. A store with zero new formations is never due. Late-local-time remains the host's clock. Bounded by a cursor (0058): for `SQLiteTripleStore` and `InMemoryTripleStore` the answer is folded from the store's `assertions_after` feed, per (store, journal, scopes) in the process, so a check reads only the rows written since the previous check and re-reads the journal's formation bindings only when the journal moved (a repeated check with nothing new costs well under a millisecond). Same answer as the full scan, which other stores (LanceDB) still use.
- `last_maintenance_seq(store, journal, *, scopes) -> int` — journal seq of the newest sleep artifact's formation; `0` means this store has never slept.
- `mind_mass_report(store, journal, *, scopes, days=30, bucket="day", embedder=None, now=None, vector_scan_limit=VECTOR_SCAN_LIMIT, wake_cue_kind="episode") -> dict` — formation cadence, journal mass, duplicate mass, embedding-space integrity, review backlog, and sleep recency, window-bounded. Warnings come from the closed `WARNING_WORDS` set.
- `redigestion_candidates(system, *, scopes, limit=50, min_residue_chars=24, methods=MECHANICAL_DIGEST_METHODS) -> dict` — enumerate the labeled mechanical-digest debt, worst first. Pure read: listing a debt is not using the memories.
- `apply_redigestion(system, entries, *, actor, digest_method="entity-authored", turn_id=None) -> dict` — apply authored digests to labeled-mechanical records.
- `RedigestionCandidate` — one labeled-mechanical record awaiting authored words, including `poverty` and `content_residue`.
- `reembed_store(system, *, embedder, owner_id, model_id=None, marker_scope="life", reason=..., batch_size=64) -> dict` — re-derive the whole vector index and swap atomically, pin written LAST. `reembed_home` is the same call under the name the operator guide uses.
- `read_embedding_pin(path, *, table_name="triples") -> dict | None` — a pure peek at a store file's embedding pin without opening the store. Raises `ValueError` if `table_name` is not a plain SQL identifier.
- `build_pin(model_id, dimension, *, source, claimed_by=None) -> dict` — the normalized pin payload. At least one of model/dimension must be present: an empty pin would enforce nothing and lie about it.
- `journal_cold_cut(src_path, dst_path, *, cut_seq=0, pair_cuts=None, archive_ref, exported_stream_ref=None, null_retired_embeddings=True, cut_traces=False) -> dict` — rebuild a home store file with the attention-event mass cold-cut.
- `verify_cold_cut(src_path, dst_path) -> {"ok", "checks"}` — parity checks between original and rebuilt file, measured rather than asserted; every check names its own numbers.
- `wake_cue_dedup_pass(system, *, scope, owner_id, actor, kind="episode", jaccard_floor=0.82, min_cluster=3, report_only=False) -> dict` — collapse near-identical same-day records into one day summary. Deliberately conservative: two similar episodes are a life, twenty near-identical ones are a loop artifact.
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
