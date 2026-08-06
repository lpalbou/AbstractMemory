# Troubleshooting

Symptom-oriented fixes for setup, retrieval, embedding, and maintenance problems.

See also: [`getting-started.md`](getting-started.md) for setup, [`stores.md`](stores.md) for backend behavior, [`api.md`](api.md) for signatures, [`operator.md`](operator.md) for inspecting a live entity home, [`faq.md`](faq.md) for conceptual questions.

## Reading the package's own signals

Two conventions make most problems self-describing before you reach for this page.

- **`#FALLBACK` warnings** mark a degradation the package chose to survive rather than crash on — a vectorless row, a volatile journal, an embedder that failed mid-formation. They are Python `RuntimeWarning`s and appear in result `warnings` lists. They always name what degraded and what to do about it. Treat one as a diagnosis, not noise.
- **Errors are actionable.** Invalid input raises rather than silently doing something plausible: an unknown anchor never quietly means "latest", and an appraisal without a reason is refused because appraisals must be explainable.

## Setup

### `ImportError: cannot import name 'MemorySystem' from 'abstractmemory'`

The installed copy is an older release that predates the `MemorySystem` facade, and it is shadowing your working tree. Confirm which copy is being imported:

```bash
python -c "import abstractmemory; print(abstractmemory.__file__, len(abstractmemory.__all__))"
```

A path under `site-packages` with a small export count means the installed distribution is being used. Reinstall in editable mode from the repository root:

```bash
python -m pip install -e .
```

The import name is `abstractmemory`; the distribution name is `AbstractMemory`.

### `ImportError` mentioning `lancedb`

The LanceDB backend is an optional dependency. Install it, or use `SQLiteTripleStore`:

```bash
python -m pip install -e ".[lancedb]"
```

### Tests pass in the repository but the package fails elsewhere

The test suite bootstraps `src/` onto `sys.path`, so it exercises the working tree whether or not the package is installed. Anything outside the suite uses the installed distribution. Install editable (above) so both agree.

## Retrieval

### `ValueError: query_text requires a configured embedder`

`TripleQuery(query_text=...)` is semantic search, and there is no keyword fallback by design — silently returning keyword results from a semantic query would hide the missing embedder. Either construct the store with an `embedder`, or query with structured filters instead. See [Embedders](api.md#embedders).

### Vector queries return nothing, or miss rows you know exist

Rows written **without** an embedder are stored vectorless, and vector queries skip them. Adding an embedder later does not retroactively vectorize them. Re-derive the index:

```python
from abstractmemory import reembed_store
reembed_store(system, embedder=my_embedder, owner_id="entity:demo")
```

This re-embeds every row and swaps the space atomically, writing the new pin last. See [Maintenance, health, and operator tools](api.md#maintenance-health-and-operator-tools).

### A record exists but never surfaces in recall

Ask the engine rather than guessing — three reads answer this directly:

```python
from abstractmemory import absence_diagnosis, explain_recall, recall_history

absence_diagnosis(store, journal, record_id, scope="life", owner_id="entity:demo")
explain_recall(store, journal, record_id, trace_id=trace_id)
recall_history(journal, record_id)
```

`absence_diagnosis` reports structural reasons in plain sentences (never formed, retracted, hidden, out of scope, vectorless). `explain_recall` answers the same question against one specific recall. Common structural causes: the record is in a scope the ladder does not include; a closure retracted or superseded it; it is an inactive candidate; or it was formed after the `as_of` seq you anchored to.

### Recall results change between runs with the same input

Reconstruction is a pure function of (store truth ≤ `as_of`, journal ≤ `as_of`, stimulus, params). If results move, one of those inputs moved — usually the journal, because committed use changes retrieval strength. Anchor the read to reproduce it exactly:

```python
result = system.reconstruct(Stimulus(cue_text="…", as_of=result.as_of_seq), scopes=scopes)
```

Note that `reconstruct` is a pure read: rendering a memory does not strengthen it. Only `commit_selection` does.

## Embedding spaces

### `#FALLBACK: embedding pin created at FIRST WRITE`

The home predates creation-time pinning, so the embedding space was inferred from the first embedded write rather than declared up front. Existing homes keep working. New homes should pin the embedder at creation so the space is a stated choice rather than an accident.

### A home refuses your embedder, or reports a dimension mismatch

Each home pins one embedding space. Vectors from different models are not comparable, so the pin is enforced rather than trusted. Inspect a store file without opening it:

```python
from abstractmemory import read_embedding_pin
read_embedding_pin("memory.sqlite3")
```

To move a home to a different space deliberately, use `reembed_store(...)`, which re-derives every vector and swaps the pin last, so a crash never leaves a half-migrated space.

### `ValueError: table_name must match [A-Za-z_][A-Za-z0-9_]*`

Table names are interpolated into SQL identifiers, which cannot be bound as parameters, so they are validated at construction. Use a plain identifier. The same rule applies to `SQLiteJournal`'s `table_prefix`.

## Durability and replay

### `#FALLBACK: InMemoryJournal is volatile`

`InMemoryJournal` loses events, bindings, closures, traces, snapshots, and the seq axis on process exit, so `as_of` replay cannot survive a restart. It is meant for tests and experiments. For durable memory use `SQLiteJournal`, which can share one file with the store:

```python
store = SQLiteTripleStore("memory.sqlite3")
journal = SQLiteJournal("memory.sqlite3")   # sidecar tables in the same file
```

### Replay shows gaps in `seq`

Expected under family filters and under diary redaction. Gaps carry no meaning. The replay stream is an observability surface — not a payload export, not a second source of truth, and not a checkpoint format. See [Replay stream](api.md#replay-stream).

## Maintenance and sleep

### A sleep pass does nothing

Usually correct behavior. `maintenance_due(...)` is a deterministic predicate: a store with zero new formations since the last pass is never due, because the pass would only reproduce its own prior output. Check what it reports:

```python
from abstractmemory import maintenance_due, last_maintenance_seq
maintenance_due(store, journal, scopes=scopes)
last_maintenance_seq(store, journal, scopes=scopes)   # 0 = never slept
```

A quiet night is also a valid outcome of a pass that did run: `dream_pass` forms nothing when nothing crossed its floors, and says why.

### A cancelled night left work unfinished

By design. `sleep_pass(..., should_continue=...)` checks at sub-phase boundaries; the running sub-phase always completes rather than being torn, later ones skip with a stated `skipped_reason`, and the night carries `cancelled_after`. Sub-phases are idempotent, so the next sleep resumes the work.

### Unrelated records are proposed as near-duplicates

Near-duplicate detection fingerprints `title + digest` tokens and flags pairs at or above `SleepTuning.near_dup_jaccard_floor` (0.65). Genuine causes are templated titles or boilerplate shared across records — the tokenizer has a length floor rather than a stopword list, so repeated scaffolding counts as content. Raise the floor through `SleepTuning`, or give the records distinguishing digests. Note that truncation markers deliberately stay **out** of digest text for exactly this reason; the counts ride `attributes._truncation` instead.

## Getting more detail

- `engine_manifest()` returns the machine-readable inventory of what this build contains.
- `mind_mass_report(...)` reports formation cadence, journal mass, duplicate mass, embedding-space integrity, review backlog, and sleep recency in one bounded read.
- `export_replay(...)` streams the journal verbatim in seq order for scrubbing history or tailing live.
