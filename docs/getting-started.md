# Getting started

> Source of truth for the public API: [`src/abstractmemory/__init__.py`](../src/abstractmemory/__init__.py); full reference: [`api.md`](api.md).

Requires Python 3.10+ (see [`pyproject.toml`](../pyproject.toml)).

## 1) Install

From source (recommended inside the AbstractFramework monorepo):

```bash
python -m pip install -e .
```

Optional LanceDB backend:

```bash
python -m pip install -e ".[lancedb]"
```

PyPI (packaged release):

```bash
python -m pip install AbstractMemory
python -m pip install "AbstractMemory[lancedb]"
```

The distribution name is `AbstractMemory` (pip is case-insensitive); the import name is `abstractmemory`.

## 2) Layer 1: append-only triples

```python
from abstractmemory import InMemoryTripleStore, TripleAssertion, TripleQuery

store = InMemoryTripleStore()
store.add([
    TripleAssertion(
        subject="Scrooge",
        predicate="related_to",
        object="Christmas",
        scope="session",
        owner_id="sess-1",
        observed_at="2026-01-01T00:00:00+00:00",
        provenance={"span_id": "span_123"},
    )
])

hits = store.query(TripleQuery(subject="scrooge", scope="session", owner_id="sess-1", limit=10))
assert hits[0].object == "christmas"     # terms are canonicalized (trim + lowercase)
assert hits[0].assertion_id is not None  # read-side identity, stamped by the store
```

Notes:

- Canonicalization lowercases `subject`/`predicate`/`object`. To preserve original casing, store it separately (for example in `attributes`), or set `attributes={"literal": True}` to keep the `object` case-sensitive (typed records formed by the memory system use this for digest text).
- `scope` is a free-form partition label (lowercased). Common conventions: `"session"` + `owner_id` per conversation, `"run"` + `owner_id` per execution, `"global"` for shared memory, and the entity-home scopes `"self"`/`"diary"`/`"life"`. At layer 2, `"global"` is a broad scope: searching it requires an explicit `escalation_reason`.
- `TripleQuery(assertion_ids=(...,))` looks up rows by exact id; id lookups bypass visibility folds by design (audit completeness).

## 3) Persistent single-file store (SQLite), with optional vectors

`SQLiteTripleStore` uses only the Python standard library and supports both deterministic structured queries and native vector search when constructed with an embedder.

```python
from abstractmemory import SQLiteTripleStore, TripleAssertion, TripleQuery

store = SQLiteTripleStore("data/kg.sqlite")
store.add([TripleAssertion(subject="e:scrooge", predicate="is_a", object="person", scope="global")])

out = store.query(TripleQuery(scope="global", limit=10))
store.close()
```

With vectors (any `TextEmbedder`; here an OpenAI-compatible server such as LM Studio or Ollama):

```python
from abstractmemory import OpenAICompatTextEmbedder, SQLiteTripleStore, TripleQuery

embedder = OpenAICompatTextEmbedder(
    base_url="http://127.0.0.1:1234/v1",
    model="text-embedding-qwen3-embedding-0.6b",
)
store = SQLiteTripleStore("data/kg.sqlite", embedder=embedder)
# add(...) embeds each assertion's canonical text and persists the vector in the same file
hits = store.query(TripleQuery(query_text="who is scrooge", scope="global", limit=5))
```

Rows added while no embedder was configured stay vectorless; vector queries skip them, and layer-2 recall labels the degradation with a `#FALLBACK` warning. Files created before the vector column existed are upgraded in place on open.

## 4) LanceDB backend (optional)

```python
from abstractmemory import LanceDBTripleStore, TripleAssertion, TripleQuery

store = LanceDBTripleStore("data/kg")
store.add([TripleAssertion(subject="e:scrooge", predicate="is_a", object="person", scope="global")])
out = store.query(TripleQuery(scope="global", limit=10))
store.close()
```

See [`stores.md`](stores.md) for backend-by-backend behavior and persistence details.

## 5) Semantic/vector queries

Vector search is opt-in and consistent across vector-capable stores:

- `query_text=...` embeds the text and ranks by cosine similarity; it requires a configured embedder (a `ValueError` is raised otherwise — there is no keyword fallback).
- `query_vector=...` bypasses embedding generation (caller-supplied vector).
- `min_score=...` applies a cosine similarity threshold.
- Only rows stored with vectors participate; results carry retrieval metadata in `attributes["_retrieval"]`.

Embedder options:

- `OpenAICompatTextEmbedder(base_url, model, *, api_key=None, timeout_s=30.0, batch_size=64)` — any OpenAI-compatible `/embeddings` endpoint.
- `AbstractGatewayTextEmbedder(base_url, auth_token=None, ...)` — an AbstractGateway embeddings endpoint (default path `/api/gateway/embeddings`).
- Your own implementation of the `TextEmbedder` protocol: `embed_texts(texts) -> list[list[float]]`.

Keep one embedding model per store file: vectors from different models are not comparable, and the store does not enforce this for you.

## 6) Layer 2: the memory system

`MemorySystem` composes a store and a journal (both injected) into the full memory engine. The SQLite pair shares one file — one file is one home.

```python
from abstractmemory import (
    MemorySystem, MemoryRecordInput, SQLiteTripleStore, SQLiteJournal, Stimulus,
)

store = SQLiteTripleStore("memory.sqlite3")
journal = SQLiteJournal("memory.sqlite3")
system = MemorySystem(store=store, journal=journal)

# FORM: typed records with digests, keywords, edges (idempotent by key).
[gid] = system.remember_many(
    [MemoryRecordInput(kind="episode", title="Pool outage night",
                       digest="The connection pool saturated at noon.",
                       keywords=("pool", "saturation", "noon"))],
    scope="session", owner_id="s1", idempotency_key="turn-1",
)

# RECONSTRUCT: working memory for a cue (pure read; nothing is strengthened).
result = system.reconstruct(Stimulus(cue_text="pool outage"), scopes=[("session", "s1")])
for handle in result.handles:
    print(handle.admission, handle.title, handle.digest)

# COMMIT: deposit usage for the records that actually entered your context.
system.commit_selection(result.trace_id, [h.record_id for h in result.handles[:2]])
```

The loop above is the whole contract: **form → reconstruct → commit**. Reconstruction is a pure read; `commit_selection` is the only path that strengthens memories (usage trails and co-use associations). Records rendered from short-term standing or from the identity core are present but do not deposit — presence is not use.

From here:

- The cognitive model (how working memory emerges, attention, valence, dreams): [`memory-system.md`](memory-system.md)
- Every call and dataclass: [`api.md`](api.md)
- Architecture and invariants: [`architecture.md`](architecture.md)
- Inspecting an entity home as an operator: [`operator.md`](operator.md)
