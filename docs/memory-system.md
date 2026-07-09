# The memory system

This page explains the cognitive model behind `MemorySystem` — what the moving parts mean and why they fit together. For exact signatures see [`api.md`](api.md); for the structural invariants see [`architecture.md`](architecture.md).

## One graph, emergent working memory

Memory is a single durable, usage-weighted graph. There is no separate "short-term store" that copies things in and out; working memory *emerges* from two signals folded over the same substrate:

1. **A recency/frequency trail.** Every committed use deposits attention events; a record's *activation* is a decayed fold over those events. Decay is activity-relative (measured in events, not wall-clock), so a quiet home does not forget just because time passed.
2. **Stimulus-driven spreading.** A cue lights up records through retrieval channels — exact triple patterns, keyword scan, vector similarity, and participant co-presence — and activation spreads outward over recorded edges and co-use trails, so related memories surface with the ones that matched.

Reconstruction returns the union of three components, labeled per handle:

- `self` — identity records, present by binding state (reserved seats; see below),
- `stm` — trail-hot records (continuity: what was just in use),
- `stimulus` / `both` — what the cue matched (and matched-while-hot).

Storage never decays. Only retrieval strength does. Nothing is deleted; forgetting is decay plus closure records plus silencing.

## Use strengthens; presence does not

`reconstruct` is a pure read. Strengthening happens in exactly one place: `commit_selection(trace_id, used_ids)`, called with the records that actually entered your context. It deposits:

- one `selected` event per used record — the usage trail;
- `co_selected` pair events for all pairs used together in the same moment — the association trail (co-use is how the graph learns which memories belong together).

Records admitted as `self` or `stm` deposit nothing even when committed: rendering your own identity, or a memory that was already on your desk, is presence — not use. This keeps counters honest (they measure lived experience) and prevents the working set from becoming self-reinforcing.

## The two access counts

Every record and every association carries two counts:

- **Global** — cumulative selected-use over the journal's life. It never decays: at any point it answers "what has mattered, absolutely". Read it via `access_counts(...)`; every handle also surfaces it as `provenance["global_count"]`.
- **Temporal** — the decayed activation fold: "what matters right now". It reads through a bounded window of recent events (`AttentionConfig.window_limit`, default 512 — session-scale). Homes with continuous activity should size the window to about a week of their measured event cadence (for example `AttentionConfig(window_limit=8192)`); the global count is unaffected by the window entirely.

Deliberate acts adjust standing without pretending to be use: `reinforce` (strengthen with a mandatory reason), `attenuate` (nudge toward invisibility), `refocus` (a topic-shift marker that accelerates decay of everything older than it).

## Valence: how experience felt

Orthogonal to attention — valence never touches retrieval (enforced at behavior and import level). Feelings accumulate per *target*, and targets are anything nameable: records, people, tools, ideas, places, times of day — free strings by convention (`person:ada`, `tool:web_search`, `time:morning`).

- `appraise(target, sign=±1, magnitude=1..10, reason=...)` deposits one signed experience. Deterministic triggers may write only ±1..3; larger magnitudes require reflective or operator actorship (or a catastrophic outcome code) — amplitude carries authority.
- `gradation(...)` derives standing per target on **two channels**: G⁺ and G⁻ accumulate separately (each clamped 0..100), so ambivalence is preserved — a hundred small positives and one severe negative read as `net +90` *with* the negative permanently visible, never averaged away.
- **Scars and bonds** are explicit standing peaks, symmetric by design: an unhealed scar caps a target's presentation at ≤ 0; an unbroken bond floors it at ≥ 0; both standing at once presents exactly 0 with both flags up. Resolutions are append-only acts (`heal_scar`, `break_bond`); a betrayal-scale scar (magnitude ≥ 8 after a bond) breaks the bond without an explicit call.
- Valence never decays: it is accumulated experience. Plasticity comes only from new evidence and explicit resolutions.

## Identity: present by right, not by recall

A long-lived entity's identity is a set of records — values, purposes, traits — formed once from a **spark** document:

- `DEFAULT_SPARK_TEMPLATE` is the canonical six-key spark; `lint_spark` enforces its charter (behavioral statements, bounded sections, an explicit core/revisable class per value).
- `engram(system, spark, owner_id=...)` forms the identity records and binds each one *prompt-active* — membership in the always-warm core. The pass is idempotent by `canonical_spark_hash`; a modified spark under the same version is refused — identity content cannot change silently.
- On every reconstruction with `RecallBudget.self_fraction > 0`, those records occupy reserved seats (`admission="self"`), ordered by identity rank — regardless of what the cue was. Being present is their right; their counters stay untouched (presence ≠ use).
- `self_records(...)` is the folded identity read (binding- and closure-folded): what the entity currently is.
- Identity evolves at record level, by the entity's own act: close the old record (supersede), form the new one, bind it into the seats. Nothing is lost — the journal's time axis is the version history.

Two exported floors support entity hosting: `SELF_FRACTION_FLOOR` (0.05 — hosts refuse summons below it; a stripped identity is a different person) and `ENTITY_CONTEXT_FLOOR` (20,000 tokens — `entity_recall_budget(context_window)` sizes a session's recall budget and refuses smaller windows).

## Diary: what the entity elects to remember

The diary has two planes. The *book* (the verbatim words) lives host-side in a hash-chained ledger; the graph stores a **projection** — the memory of the act of writing ("wrote about X"), with `attributes.entry_id` pointing into the book. Private entries project as act-only records; their words never enter the graph, so no read surface here can leak them.

Conventions the engine enforces and reads:

- `kind="diary"` formation requires a declared write channel (`provenance.source`: `diary-projection` or `entity-direct`) — the diary has one writer per plane.
- `diary_type` ∈ {note, idea, commitment, reflection, question, problem}. Questions and problems are first-class autonomy drivers: a question is curiosity; a problem is something wrong that needs fixing.
- Resolution is append-only: a later entry references a question via `attributes.answers` or a problem via `attributes.resolves` (graph id or book entry id). `open_questions` / `open_problems` / `open_ideas` list what still stands — typical wake reasons for a scheduled entity.
- Entity-direct entries can carry a content hash chain (`prev_entry_hash`/`entry_hash`); `verify_diary_chain` audits it and names the first break. Projections attest through the book instead — nothing claimed, nothing broken.

## Sleep and dreams: consolidation without invention

`dream_pass(system, scopes=..., owner_id=...)` is deterministic maintenance — zero LLM calls, no invented narratives:

- `structural_report` computes the graph's shape: connected components over **semantic authored relations only** (`COMPONENT_RELATIONS`: summarizes, from_session, reflected_in, continues, derived_from, answers, supports, part_of). Mechanical co-presence edges (`CONTEXT_RELATIONS`: written_amid, mentions) and unknown predicates never define components — they count as "already associated", and unknown predicates are named in the report.
- Bridge proposals are cross-component pairs sharing weak signals (shared facets, shared participants, or stored-vector similarity). Pairs already associated by use (warm co-use trails) or by context edges are excluded and counted.
- At most **one** dream record forms per pass (`kind="dream"`, review-gated, idempotent by report fingerprint), with weak `mentions` links to its sources. A quiet night is a valid night: below the salience floor, nothing forms and the report says why.

**Sleep proposes; waking evidence disposes.** The dream never writes a load-bearing edge; unresolved dreams chain and stand as `unresolved_dreams(...)` — recurring dreams about unresolved tension, another wake reason. Maintenance deposits nothing: the pass never touches counters.

### Phase 1: data-quality tending

The dream is sleep's second phase. Phase 1 (`maintenance.py`) tends the graph first — organize the day's memories, name metadata issues, propose relationship repairs:

- `maintenance_report(store, journal, scopes=...)` is a pure read: metadata gaps (missing keywords/intents/outcomes — named for waking re-digestion, never filled while asleep), duplicate-title groups (same kind only), near-duplicate pairs (token-set Jaccard ≥ 0.65, or stored-vector cosine ≥ 0.90 for paraphrase duplicates), shared-source groups, isolated-link candidates (≥ 2 shared facets, proposal only), and edge-suppression candidates (duplicate or `mentions`-shadowed edges, reported as append-only closure candidates for waking acts).
- `consolidation_pass(system, scopes=..., owner_id=...)` is phase 1's one write: at most N (default 2) low-risk duplicate-title groups become **inactive, review-gated** `kind="summary"` candidates with `summarizes` edges to every source — idempotent by source set, sources byte-untouched, nothing merged or removed while asleep. Maintenance candidates are excluded from the next pass's inputs (tending never re-tends its own output).
- `maintenance_due(store, journal, scopes=...)` is the deterministic cadence predicate ("enough new records, or new material plus standing fragmentation"); when to sleep — late local time, the sleep window — stays the host's clock.
- `sleep_pass(system, scopes=..., owner_id=...)` runs one full sleep in the canonical order: tend, then dream over the tended graph.

## Observability: the replay stream and the identity card

- `export_replay(...)` streams verbatim journal records as envelopes (`stream`, `stream_version`, `seq`, `family`, `observed_at`, `scope`, `owner_id`, `trace_id`, `turn_id`, `run_id`, `payload`, optional `display`) across six families — `event`, `binding`, `closure`, `trace`, `snapshot`, `valence` — in strict seq order. One shape serves history scrub and live tail (poll with your last seen seq as the cursor). `family="host"` is reserved for host-authored markers (summons, sleep/wake) and is never emitted by this package. Enrichment adds `{record_id, kind, title, token_estimate}` and `graph_id` where resolvable — never fabricated; diary display blocks arrive redacted (`{"redacted": "diary"}`): topology visible, words sealed.
- `entity_card(...)` composes one pure read over a home: identity, age and accumulated context, current emotional state (a trailing window over recent appraisals — current is a window, not a point), top likes/dislikes (G⁺ and G⁻ reported separately), open/resolved questions, key moments (high-magnitude feelings and firsts, chronological), and discoveries (open interests, unresolved dreams). Every section names its source in a `provenance` string. The card is *about* the entity, derived from its data — being described strengthens nothing.

## Where hosts come in

This package owns mechanics, not policy. Hosts (AbstractRuntime, AbstractGateway) decide *when* to reconstruct and commit, *who* may write through which channel, and *what* enters prompts. Everything documented here works directly against a home's files with only `abstractmemory` installed — see [`operator.md`](operator.md) for the read-only inspection workflow.
