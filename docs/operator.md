# Operator guide — observing and verifying an entity's memory

This guide shows what you, the human operator, can see and verify inside a summoned entity's memory home, with runnable snippets. It assumes a host (typically AbstractGateway) created the home; every snippet here works directly against the home's files with only `abstractmemory` installed. For the concepts behind these reads, see [`memory-system.md`](memory-system.md).

An entity home contains one store+journal pair:

```
<data_dir>/entities/<slug>/
  spark.yaml        # the attested seed (byte-verbatim)
  memory.sqlite3    # layer 1 (the graph) + the journal (one file)
  home.sqlite3      # the diary book (the host's hash-chained ledger)
  manifest.json     # entity id, spark hash
```

Open it read-only:

```python
from abstractmemory import MemorySystem, SQLiteTripleStore, SQLiteJournal

store = SQLiteTripleStore("memory.sqlite3")
journal = SQLiteJournal("memory.sqlite3")
system = MemorySystem(store=store, journal=journal)

eid = "entity:castor@<home-id>"   # the entity id, from manifest.json
```

The home's scope ladder is `("self", eid)` for identity, `("diary", eid)` for diary projections, and `("life", eid)` for lived episodes. Everything below is a **pure read** — nothing you do here strengthens, weakens, or touches the entity's memory (reading is not using; only `commit_selection` deposits).

## 1. Who is this entity right now? (the identity core)

```python
for a in system.self_records(scope="self", owner_id=eid):
    kind = a.attributes.get("record_kind")       # value | purpose | trait
    print(f"[{kind}] {a.attributes.get('title')}: {a.object}")
```

This is the same folded read the summon prelude renders — what the entity is reminded of about itself at every waking. Order is identity order: values first (by precedence), then purposes, then traits.

## 2. The identity card (one composed view)

```python
card = system.entity_card(
    scope_pairs=[("self", eid), ("diary", eid), ("life", eid)],
    owner_id=eid,
)
print(card["identity"]["values"])
print(card["current_state"])         # recent valence over a trailing window
print(card["questions"]["open"])     # what it still wonders
print(card["key_moments"]["moments"])
```

Every section carries a `provenance` string naming its source. The card is *about* the entity, derived from its data; composing it deposits nothing, and `as_of=` renders the card as of any past journal seq.

## 3. What would wake it? (wake reasons)

```python
from abstractmemory import open_questions, open_problems, open_ideas

qs = open_questions(store, scope="diary", owner_id=eid, journal=journal)
ps = open_problems(store, scope="diary", owner_id=eid, journal=journal)
ideas = open_ideas(store, scope="diary", owner_id=eid, journal=journal)
```

Curiosity / wrongness / direction: diary entries the entity wrote that no later entry has resolved.

## 4. How does it feel about things? (gradation)

```python
g = system.gradation(None, scope="self", owner_id=eid)   # every appraised target
print(g.get("person:albou"))   # {net, positive, negative, scarred, bonded, ...}
```

Gradation is the entity's accumulated signed experience per target (people, tools, topics, moments). Scars cap presentation at ≤ 0 until healed; bonds floor it at ≥ 0 unless broken. Both channels stay visible — a hundred +1s then one −10 reads net +90 *with* the −10 visible, preserving ambivalence.

## 5. Watch the graph live (or replay any past stretch)

```python
for item in system.export_replay(since_seq=0):
    print(item["seq"], item["family"], item.get("display"))
```

One stream, six families: `event` (attention: what got selected, what got reinforced), `binding` (visibility transitions), `closure` (belief lifecycle), `trace` (each recall: candidates, scores, what was dropped and why), `snapshot` (what actually entered a context), `valence` (appraisals, scars, bonds). Replay is a bounded read from `since_seq=0`; live is the same read polled with your last seen `seq` as the cursor. AbstractGateway serves this same stream over HTTP (`/api/gateway/entities/<name>/replay` and `/replay/stream` for SSE). Diary display blocks arrive `{"redacted": "diary"}`: topology visible, content sealed (the diary words stay in the book).

## 6. Verify integrity

**Diary chain** (graph plane): owner-direct diary entries carry a content-hash chain; a tampered or truncated chain fails loudly, naming the first broken entry:

```python
from abstractmemory import verify_diary_chain
report = verify_diary_chain(store, scope="diary", owner_id=eid)
# {"intact": bool, "break_at": record_id | None, "entries": n}
```

Diary *projections* attest through the host's book (`home.sqlite3`, a hash-chained ledger) instead — verifying the book is a host surface (for AbstractGateway, the `entity verify` command).

**Journal determinism**: any past reconstruction can be replayed by anchoring `as_of` to its trace's `as_of_seq` — same inputs, same result:

```python
traces = journal.traces(limit=10)          # most recent recalls
snapshots = journal.snapshots(limit=10)    # what entered contexts
```

**Spark attestation** is host-side (`manifest.json` records the spark hash; `spark.yaml` is byte-verbatim).

## 6b. The embedding space (pin, mismatches, repair)

Every home store is ONE embedding space, declared by a pin (`{model_id, dimension, source, pinned_at}`) written at creation — the embedder is a birth choice:

```python
store = SQLiteTripleStore(home / "memory.sqlite3", embedder=embedder,
                          embedding_pin={"model_id": "text-embedding-qwen3-embedding-0.6b",
                                         "dimension": 1024})
store.embedding_pin()   # read it back
```

No silent mixing of spaces: opening with a different known model refuses; a wrong-dimension write refuses with zero rows; a wrong-dimension query refuses at read and recall degrades loudly to exact/keyword (`#FALLBACK` on the vector channel). Homes created before pinning (Castor's) take the FIRST-WRITE path — pinned at their next embedded write from what actually embedded, with a labeled `#FALLBACK` warning naming it (ruled by the door's owner: the door pins only what it knows; a creation-source pin written years after birth would claim a fact nobody attested — the label is the home's history, not a blemish). First-write pins additionally record `claimed_by: "embedder-attribute"` — the model label was read off the embedder object, not asserted by an operator, and the engine cannot verify a label against the serving endpoint (2026-07-11 incident: a first-write pin captured a label the server never recognized). Pinning such a home deliberately remains one operator act: pass `embedding_pin=` on the pinless store and it writes as a creation-source pin from that moment on. When an embed call fails at query time, the error names the pin (`[store pin: <model>@<dim>d (...)]`) so claimed-vs-served is one line.

Changing the embedder is a deliberate, operator-gated repair — never routine:

```python
from abstractmemory import reembed_store
report = reembed_store(system, embedder=new_embedder, owner_id=eid)
# {'rows': n, 'vectored': m, 'old_pin': ..., 'new_pin': ..., 'marker_record_id': ...}
```

Vectors are derived data: the pass re-embeds every stored text, swaps atomically (pin last), backfills vectorless rows, and journals the act as a bookkeeping record — the life stream shows exactly when retrieval geometry changed. Memories, history, counts, and feelings are untouched; retrieval *neighbors* may shift (same memories, different neighbors — a substrate effect, on the record). Run it over a closed home under the maintenance lease. A runnable demonstration of all of this is `examples/entity_home_maintenance_proof.py` (nine numbered proofs; `--live` uses LMStudio).

## 7. What the engine will never do

- **Delete**: there is no delete surface. Forgetting is decay of retrieval strength + closure records + silencing — the substrate is lossless.
- **Compact**: no rewriting, no summarizing-in-place. Degradation through compaction cannot originate here.
- **Strengthen on read**: your inspection deposits nothing. Only the entity's own committed use moves its trails.
- **Mix embedding spaces**: the pin refuses wrong-space writes and reads; the only space change is the journaled reembed repair.

## Budget guidance (entity sessions)

Entity sessions require a context window of at least 20,000 tokens (`ENTITY_CONTEXT_FLOOR`). The engine ships the budget profile hosts inject at summon:

```python
from abstractmemory import entity_recall_budget, ENTITY_CONTEXT_FLOOR
budget = entity_recall_budget(20_000)                  # token_budget=2400, shelf_size=12
budget = entity_recall_budget(1_000_000)               # token_budget=120_000 — no upper cap
budget = entity_recall_budget(20_000, shelf_size=24)   # widened shelf
```

The token budget is 12% of the context window, uncapped above the 2,400-token starvation floor — wider contexts buy a wider working set at an efficiency tradeoff you can measure. The default shelf of 12 models limited attention (seats, like what a mind holds at once) and is a declared tunable.

## Resident homes and the attention window

The temporal-activation fold reads a bounded window of recent attention events (`AttentionConfig.window_limit`, default 512 — session-scale). A continuously active home emits on the order of 1,000 events per day, so at the default a record heavily used yesterday can fall past the window edge and read temporal-zero today — a cliff rather than the gradual decay the curve provides (at the edge an event still carries ~4% of its weight). For resident homes, size the window to about a week of the home's **measured** cadence:

```python
from abstractmemory import AttentionConfig, MemorySystem
system = MemorySystem(store=store, journal=journal,
                      attention_config=AttentionConfig(window_limit=8192))
```

The GLOBAL access count never windows — the two-count model's global half (`selected_count` / `pair_selected_count`, "what mattered over a lifetime") is untouched by this setting; only the temporal half reads through the window.
