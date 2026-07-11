# API Reference

> Pre-1.0: the API is versioned and tested; details may still evolve. The authoritative export list is [`src/abstractmemory/__init__.py`](../src/abstractmemory/__init__.py). Signatures below are verified against the source.

See also: [`getting-started.md`](getting-started.md) for first examples, [`architecture.md`](architecture.md) for invariants, [`memory-system.md`](memory-system.md) for the cognitive model, [`stores.md`](stores.md) for backend behavior.

Contents:

- [Layer 1: triples, queries, stores, embedders](#layer-1-triples-queries-stores-embedders)
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

- `InMemoryTripleStore(embedder=None)` — dependency-free, volatile, vector-capable.
- `SQLiteTripleStore(path, embedder=None)` — persistent single file (stdlib only), structured queries and native vector search. With an embedder, `add(...)` embeds each assertion's canonical text and persists the vector in the same file; files created before the vector column existed upgrade in place on open. Rows added without an embedder stay vectorless (vector queries skip them; layer-2 recall labels the degradation `#FALLBACK`).
- `LanceDBTripleStore(uri, embedder=None, ...)` — persistent, vector-capable; requires the optional `lancedb` dependency (constructing without it raises `ImportError` with an install hint).

Backend details and column layouts: [`stores.md`](stores.md).

### Embedders

- `TextEmbedder` (protocol): `embed_texts(texts: Sequence[str]) -> list[list[float]]`.
- `OpenAICompatTextEmbedder(base_url, model, *, api_key=None, timeout_s=30.0, batch_size=64)` — any OpenAI-compatible `/embeddings` endpoint (`base_url` includes the version prefix, e.g. `http://127.0.0.1:1234/v1`; `model` is required).
- `AbstractGatewayTextEmbedder(base_url, ...)` — POSTs `{"input": [...]}` to an AbstractGateway embeddings endpoint (default path `/api/gateway/embeddings`; Bearer auth via `auth_token`).

Keep one embedding model per store: vectors from different models are not comparable, and the store does not enforce this.

### Canonical text

- `canonical_text(assertion) -> str` — the shared text rendering stores embed and index (`CANONICAL_TEXT_VERSION` names the current rendering, version 2).
- `token_estimate(text) -> int` — the package-wide token estimate (~4 chars/token) used by budgets and handles.

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
- Constants and helpers: `SELF_FRACTION_FLOOR` (0.05), `ENTITY_CONTEXT_FLOOR` (20,000), and `entity_recall_budget(context_window, *, shelf_size=12, token_fraction=0.12) -> RecallBudget` — the entity-session budget profile (`token_budget = max(2400, round(0.12 × window))`, uncapped above the floor; refuses windows below `ENTITY_CONTEXT_FLOOR`).

### The journal

Source: [`src/abstractmemory/journal.py`](../src/abstractmemory/journal.py); backends `InMemoryJournal()` (volatile, emits a `#FALLBACK` warning) and `SQLiteJournal(path)` (sidecar tables; may share the store's file).

Record families (all append-only, all `seq`-stamped by the journal):

- `MemoryEvent` — attention events. Scoring kinds: `selected`, `co_selected` (pair trails), `pinned`, `silenced`; decay marker: `refocus`; audit-only (recorded, never scored): `listed`, `shown`, `expanded`, `cited`.
- `ScopeBinding` — visibility: `search_state` (`indexed`/`hidden`), `prompt_state` (`active`/`inactive`), `lifecycle`, `source`, `reason`. Latest per `(record_id, scope, owner_id)` wins; `fold_bindings(bindings)` applies that fold.
- `ClosureRecord` — belief lifecycle: `kind` (`retract`/`supersede`), mandatory `reason`, `replacement_ids` (required for supersede).
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
- `close_assertions(assertion_ids, *, kind, replacement_ids=(), reason) -> list[str]` — append one closure per assertion (`retract` | `supersede`).
- `close_record(record_id, *, reason, kind="retract", replacement_ids=()) -> list[str]` — close a whole record (digest and its edges) as one belief-revision act; closure ids are deterministic, so replays dedupe.

### Identity: spark, engram, self core, floors

- `DEFAULT_SPARK_TEMPLATE` — the canonical six-key spark (`name`, `origin`, `values`, `purposes`, `traits`, `honesty`); its values include the framework-level core value `shared_vulnerability` (`SHARED_VULNERABILITY_STATEMENT`).
- `lint_spark(spark, *, framework=True) -> list[str]` — charter lint (ERROR/WARNING strings): section caps, 1–3-sentence behavioral statements, explicit `class` per value; framework sparks must carry `shared_vulnerability` (`framework=False` is the explicit override).
- `canonical_spark_hash(spark) -> str` — the one hash definition shared by the engram guard and host-side spark verification.
- `engram(system, spark, *, scope="self", owner_id, spark_artifact_ref=None) -> EngramResult` — turn a linted spark into the identity core: value/purpose/trait records (honesty items are traits with `trait_class="limit"`), each bound prompt-active. Idempotent by spark hash; a modified spark under the same version is refused; a higher version is refused while the born core remains prompt-active (re-engram is an exceptional repair, not an amendment path). `EngramResult` carries `record_ids` per section, `binding_ids`, `warnings`, `created`.
- `self_records(*, scope, owner_id, spark_version=None) -> list[TripleAssertion]` — the folded identity read: prompt-active and closure-folded, identity kinds only, ordered kind rank → precedence → record id. Identity evolves at record level (close the old record, form and bind the new one); the journal's time axis is the version history.
- Floors: `SELF_FRACTION_FLOOR = 0.05` (summoned entities run at or above it; the engine keeps accepting lower values for non-entity callers) and `ENTITY_CONTEXT_FLOOR = 20_000` with `entity_recall_budget(...)` (see seam types).

### Valence and gradation

Orthogonal to attention by contract: valence never touches activation, never gates candidates, and the retrieval pipeline never reads it (enforced at behavior and import level).

- `appraise(target_id, *, sign, magnitude, reason, scope, owner_id, value_refs=(), scar=False, bond=False, event_id=None, actor="runtime", provenance=None, trace_id=None) -> list[str]` — deposit one signed appraisal (sign ±1, magnitude 1..10). Amplitude authority: magnitude > 3 requires actor `entity-reflection`/`operator` or `provenance["outcome_class"]=="catastrophic"`. `scar=True` (requires sign −1) / `bond=True` (requires sign +1) write an explicit standing marker alongside (`"{event_id}:scar"` / `"{event_id}:bond"`); markers are never auto-created.
- `heal_scar(scar_event_id, *, reason, lesson_record_id=None, scope, owner_id, event_id=None, actor="entity-reflection") -> str` and `break_bond(bond_event_id, *, reason, scope, owner_id, event_id=None, actor="entity-reflection") -> str` — append-only resolutions with deterministic default ids (`heal:{id}` / `break:{id}`). A betrayal-scale scar (magnitude ≥ 8 after the bond) breaks it without an explicit call.
- `gradation(target_ids=None, *, scope, owner_id, at_seq=None) -> dict` — derived dual-channel standing per target: `{net, positive, negative, positive_count, negative_count, scarred, bonded, contributions}`. G⁺/G⁻ accumulate chronologically, each clamped 0..100 — ambivalence is preserved. Presentation: unhealed scar → `net = min(net, 0)`; unbroken bond → `net = max(net, 0)`; both → exactly 0 with both flags visible. `target_ids=None` enumerates every appraised target; requested targets with no events return the neutral shape. No decay of any kind: plasticity comes only from new evidence and resolutions.
- `compute_gradation(events, *, config=GradationConfig()) -> dict[str, GradationScore]` — the pure fold behind `gradation` (`GradationConfig(channel_clamp=100.0, break_magnitude=8.0)`).

Targets are anything nameable — records, people, tools, ideas, places, moments in time. Namespace-prefixed free strings are the convention (`person:ada`, `tool:web_search`, `time:morning`); there is no registry.

### Diary reads and chain verification

- `open_questions(store, *, scope, owner_id, limit=100, journal=None)` — `diary_type="question"` entries no later entry answers (`attributes.answers`; either id namespace).
- `open_problems(...)` (same signature) — unresolved `diary_type="problem"` entries (`attributes.resolves`).
- `open_ideas(...)` (same signature) — incubating `diary_type="idea"` entries; with a journal, the folded binding lifecycle decides (inactive_candidate/reviewed incubate; rejected and promoted leave the open set).
- Pass the `journal` to apply closure/hidden folds; without it these are layer-1 store reads. All three return rows oldest-first; resolved entries stay retrievable as ordinary records.
- `verify_diary_chain(store, *, scope, owner_id) -> {"intact", "break_at", "entries"}` — audits the content-hash chain of owner-direct entries (`prev_entry_hash`/`entry_hash`); entries that make no chain claim fail nothing.
- `diary_entry_hash(title, digest, observed_at) -> str` — the chain's content hash (sha256).

### Consolidation (sleep and dreams)

Source: [`src/abstractmemory/consolidation.py`](../src/abstractmemory/consolidation.py). Deterministic maintenance — no LLM calls; all pure reads except the single dream record a pass may form.

- `structural_report(store, journal, *, scopes, as_of=None) -> dict` — pure structural analysis: connected components, isolated records, duplicate titles, facet coverage, adjacency. Components are computed over `COMPONENT_RELATIONS` edges only (semantic authored relations: `summarizes`, `from_session`, `reflected_in`, `continues`, `derived_from`, `answers`, `supports`, `part_of`). `CONTEXT_RELATIONS` (`written_amid`, `mentions`) and unknown predicates never define components; their pairs are reported as `context_pairs` (already-associated), unknown predicates are named in `unknown_relations`, and co-use trails are reported separately as `trail_pairs` — habit, never adjacency.
- `dream_pass(system, *, scopes, owner_id, salience_floor=2, max_sources=8, embedder_similarity_floor=0.35, report_only=False, as_of=None) -> dict` — one sleep pass: report → cross-component bridge proposals (≥ 2 shared facets, participant + facet, or stored-vector cosine ≥ floor) and single-facet questions → at most ONE `kind="dream"` record (review-gated, `interpretation_required`, weak `mentions` edges to sources, idempotent by report fingerprint). Pairs already associated by trails or context edges are excluded and counted (`trail_associated`, `context_associated`). A quiet night forms nothing and says why. Unresolved dreams chain via `parent_dream_ids`.
- `unresolved_dreams(store, *, scope, owner_id, journal=None, limit=100) -> list` — standing dreams with `continuation_state="unresolved"`, oldest first.

Sleep proposes; waking evidence disposes: the pass writes no load-bearing edges and deposits nothing (counters untouched).

### Replay stream

`export_replay(*, scope=None, owner_id=None, since_seq=0, until_seq=None, families=None, enrich=True) -> Iterator[dict]` — on `MemorySystem`, and as a module function `export_replay(store, journal, ...)`.

Yields verbatim journal records as envelopes in strict seq order: `{stream, stream_version, seq, family, observed_at, scope, owner_id, trace_id, turn_id, run_id, payload, display?}`. One shape serves history scrub and live tail (poll with your last seen seq as `since_seq`; it is exclusive, `until_seq` inclusive, `None` = high-water at call time).

- Families: `event`, `binding`, `closure`, `trace`, `snapshot`, `valence`. `family="host"` is reserved for host-authored markers (accepted by the filter, never emitted by this package).
- Correlation keys (`trace_id`, `turn_id`, `run_id`) are always present, null when absent.
- Enrichment resolves `{record_id, kind, title, token_estimate}` from the store (both members for `co_selected` pairs) and `graph_id` for formed records — absent when unresolvable, never fabricated. Diary display blocks arrive `{"redacted": "diary", "graph_id": ...}`: topology visible, content sealed.
- Under family filters or redaction, seq gaps are expected and carry no meaning. The stream is an observability surface — not a payload export, not a second source of truth, not a checkpoint format.

### Entity identity card

`entity_card(*, scope_pairs, owner_id, current_window_events=200, top_n=5, as_of=None) -> dict` — on `MemorySystem`, and as a module function `entity_card(store, journal, ...)`.

One composed pure read over a home's scope ladder (for example `[("self", eid), ("diary", eid), ("life", eid)]`), returning: `identity` (folded self core, spark version; `name` is the owner identity string), `age_and_context` (journal seq, record counts by kind per scope, diary entry count, first/last `observed_at` — timestamps only, never wall-clock now), `current_state` (a trailing window over the most recent appraisal events — current is a window, not a point), `likes_dislikes` (top targets by G⁺ and by G⁻ reported separately; record-backed targets carry resolved titles), `questions` (open and resolved, via the answers/resolves convention), `key_moments` (magnitude ≥ 8 valence events plus firsts — first dream, first interest, first supersession — chronological, most recent 20), and `discoveries` (open interests, unresolved dream count). Every section carries a `provenance` string naming its source.

Composing the card deposits nothing, and `as_of` anchors both journal signals and record existence (a card at seq T describes the entity at T; a question answered after T reads open at T).
