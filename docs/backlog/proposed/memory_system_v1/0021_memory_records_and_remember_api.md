# Proposed: Typed memory records + remember() — semantics-aligned formation

## Metadata

- Created: 2026-07-05
- Status: Proposed
- Completed: N/A
- Priority: High
- Components: records module (kinds, specs, builders), remember API, quality gates, tests, docs

## ADR status

- Governing ADRs: AbstractFramework `0005-memory-architecture.md`,
  `0025-kg-entity-normalization-and-dedup.md`
- ADR impact: Needs new ADR (memory-record vocabulary governance — new kinds
  require registry evidence, mirroring the fork's vocabulary ADR); reshapes
  planned `001_semantics_aligned_memory_record_conventions.md` from doc-only
  into code (reconcile at promotion).

## Context

Higher layers need richer memory than bare triples: episodes, lessons, plans,
instructions, decisions, claims, summaries, questions, answers. The fork
proves the catalog and the write discipline; AbstractSemantics provides the
vocabulary authority; triples are the storage form (a record = a
subject-rooted triple cluster, no new tables).

## Current code reality

- No record layer exists; consumers hand-roll attribute conventions
  (SmartNote note_id stuffing, runtime evidence_quote conventions from the
  extraction prompt).
- Depends on: `0016` (vocabulary module + registry additions), `0009`
  (ids/idempotency), `0017` (bindings for the indexed-inactive default).
- Kind catalog (ported, minus deferred): `memory, episode, plan, summary,
  question, answer, decision, claim, lesson, instruction, probe_report,
  entity`. DEFERRED: `dream` (created only via `0023`), `world_model`
  (needs participant provenance not yet specced — explicitly out of v1).

## Problem or opportunity

Without a typed record layer, every consumer invents attribute conventions
that no query can rely on, and the reconstruction kind-priority (`0020`) has
nothing to prioritize.

## Proposed direction

1. Record encoding convention (one record = one subject id
   `ex:{kind}-{ulid-or-hash}`), all registry predicates (`0016`):
   - `rdf:type` → registry class (claim→cito:Claim, lesson→skos:Concept,
     episode→schema:Event, entity→registry entity type, else dcterms:Text);
   - `dcterms:type` → kind literal (the discriminator; registry addition);
   - `dcterms:title` / `dcterms:abstract` (digest; REQUIRED — feeds
     FTS+vector) / `dcterms:description` (body, capped ~8KiB default;
     larger payloads go to `attributes.payload_ref` as host-owned artifact
     refs — the package never fetches them);
   - `schema:result` per outcome; `dcterms:subject` per keyword;
     `schema:mentions` per entity; edge links per `0016`'s mapped vocabulary
     (part_of, precedes, supports, disagrees_with, refines, summarizes,
     raises, derived_from, answers, replaces, requires);
   - intents in `attributes.intents` (bounded list); instruction `category`
     (rule|instruction|process), lesson `evidence_state`, confidence in
     attributes of the type assertion.
2. `MemoryRecordSpec` (frozen dataclass: kind, title, digest, body, intents,
   outcomes, keywords, category, evidence ids, links, entities, participants,
   confidence, attributes) + `remember(spec, *, scope, owner_id,
   idempotency_key=None, operator=False, prompt_active=False, reason=None,
   provenance=None) -> RememberResult` and `remember_many(...)`.
3. Write semantics: one transaction per record cluster (via `0009`
   batch/add_if_absent + idempotency keys → re-runs are no-ops); one scope
   binding — DEFAULT indexed + prompt-INACTIVE; machine-formed records carry
   `lifecycle="inactive_candidate"`; `prompt_active=True` requires
   `operator=True`; one `auto_memory` audit event for machine writes.
4. Quality gates (actionable errors, never silent degradation):
   - summary requires ≥1 summarizes link (fork schema guard);
   - lesson requires ≥1 evidence/derived_from link ("a successful task is not
     enough");
   - instruction requires a valid category;
   - dream/world_model rejected here;
   - broad-scope writes: raw `memory` kind requires operator; lesson/
     instruction/decision require evidence + explicit reason (the election
     gate — matches the fork's narrow election: source evidence + explicit
     confirmation or corroboration, expressed as the host asserting reason);
   - empty title/digest rejected.
5. Revision is composition: remember the successor with a `replaces` link,
   then bind the old record hidden/inactive with `lifecycle="superseded"`,
   `source="revision"` (assertion-level closure stays `0010`'s job).
6. LLM dependency: NONE. Hosts may use an injected reflector (see `0023`'s
   `ReflectorProtocol`) to DRAFT titles/digests before calling remember —
   formation itself is never blocked by a model (fork's
   reflection-then-deterministic-fallback stays host-side).

## Why it might matter

This is where AbstractMemory becomes "the high-level functioning memory
system" the owner intended — typed, evidence-linked, safely-formed memory
records that reconstruction can rank and hosts can trust, with zero prompt
blast radius by default.

## Decision boundaries

- Records are ordinary triples: every store keeps working unchanged; plain
  `TripleAssertion` writes remain the layer-1 API (planned 001's rule).
- No new kinds without registry evidence + ADR note.
- The completed-turn formation RECIPE (turn boundaries, Question/Answer/
  Episode ledger shape) lives in the runtime (`0024`), composed from
  `remember_many` — the package provides mechanics, not turn semantics.

## Promotion criteria

Promote after `0016` (vocabulary + registry additions filed) and `0017`
(bindings). Gate: the registry additions must exist before implementation
uses them.

## Validation ideas

- Each kind round-trips: spec → triples → query → reconstructed spec-equal
  record, all backends (conformance suite extension).
- Idempotency: same spec + key re-remembered → `created=False`, zero new rows.
- Gates: each rejection case has a test with its actionable message.
- Defaults: machine-formed record is invisible to a prompt-state=active fold
  but findable via search (indexed).
- A Plan→Episode→Lesson→Evidence fixture graph traverses correctly (feeds
  planned 003 validation).

## Non-goals

- No LLM extraction in the package.
- No automatic turn-ledger formation here (runtime recipe, `0024`).
- No dream/world_model kinds in v1.
- No prompt activation semantics beyond the binding flag (hosts decide what
  active means for prompts).

## Guidance for future agents

Reconcile with planned 001 at promotion (001 becomes the documentation of
this convention). Verify the registry additions from `0016` landed before
building; if predicates are still missing, stop and file them — never invent
interim vocabulary.
