# A record's understanding is rewritten in place and every earlier reading is kept as a version

Created: 2026-11-07 (understanding pass; [ADR 0003](../../../adr/0003-one-graph-ledger-provenance-and-revisions.md)
decision 6a, [ADR 0001](../../../adr/0001-altered-memories-ripple.md) decision 6).
Track: `knowledge_graph_convergence` · Priority: P1 · Type: feature · Status: Planned — engine half implemented on
`main` (see Report), awaiting the maintainer's ship review; the runtime reader (runtime 0869) and the gateway routes
(gateway 1012) consume it.

## Summary
Add the verb `rewrite_digest`. It replaces a record's digest, title and keywords **in place**. The record keeps its
graph id, its digest assertion id, its edges and its usage. The previous reading is appended to the journal's
version family (`memj_versions`) with its provenance: who wrote it (author kind and id), which model (provider,
model, thinking), when, from which ledger step and for which cause. Companion verbs: `narrate_dream` (additive, a
narration beside the dream's summary), `revert_digest`, and the reads `versions`, `current_of`,
`record_understanding`. `author_world_model` rewrites a card in place while its evidence stands. `dream_pass`
returns its signals. The replay display block carries the current reading's provenance.

## Why
Operator ruling 2026-11-07, rule 2: "Rewrites happen IN PLACE: the record keeps its id, history and usage; the
previous text is kept as a version with provenance; the verbatim is never touched." Confirmed 2026-11-08 (decision
1). The only rewrite path before this item (`apply_redigestion`) minted a NEW record with zero usage by design: a
1,159-record backfill would reset usage on every hot memory and flood the replay. ADR 0001 decision 6 already asks
that "a reconsidered memory keeps its previous reading in the journal".

## Current code reality (audited 2026-11-07, before the change)
- The digest is the assertion `(gid, dcterms:abstract, digest)` (`records.py` `build_formation_plan`); usage is keyed
  on that assertion id (`journal.selected_count(a.assertion_id)` in `redigestion.py`), so a new assertion id meant
  zero usage.
- The store was append-only for content; the only in-place column writes were `close_assertion` /
  `narrow_assertion` and `replace_vectors` (bumps `vector_generation`). FTS5 is external-content, synced by the
  `fts_high_water` rowid cursor.
- `author_world_model` always minted revision N+1 and closed the prior card, even when only the words changed.
- `dream_pass` returned no `signals`; they existed only on the stored record, so the runtime's night voice read an
  empty stream.
- `MemoryGraph` has a revision log, but no live entity home holds its tables (homes open `MemorySystem`).

## Scope
In:
1. The version family `{prefix}versions` (journal-owned, created on open; one row per (record, field, version), seq
   on the journal's one axis, deterministic `version_id`). Version 0 = the original, captured at the first rewrite.
   No column carries a length cap; every text is stored whole.
2. `rewrite_digest` (CAS on `digest_version`; refuses the protected kinds diary, value, purpose, trait, interest,
   realization; redirects dreams and cards to their verbs; refuses closed records; embeds outside the transaction
   with the pinned embedder and refuses `embedder_unavailable` rather than writing a vectored row without its
   vector; one `BEGIN IMMEDIATE` transaction: version rows, row, FTS delete+insert, vector + `vector_generation`).
3. `narrate_dream`, `revert_digest`, `versions`, `current_of`, `record_understanding`, `understanding_fields`; facade
   methods on `MemorySystem`; in-memory parity; LanceDB raises `NotImplementedError` naming this item.
4. `author_world_model(in_place=True)` by default, `expected_fingerprint` refusal, `in_place=False` keeps the chain.
5. `dream_pass` returns `signals` and `signals_omitted` (the cancelled shape mirrors them).
6. Replay: display blocks carry the provenance fields; binding and revision envelopes carry the digest text; the
   opt-in family `revision`.
7. `journal_cold_cut` copies the version family.
8. Docs (`api.md`, `memory-system.md`, `architecture.md`, `stores.md`, `faq.md`, `operator.md`, README, llms files),
   the ADR 0003 amendment (decision 6a), the redigestion docstring (the ruling supersedes "never edit-in-place";
   `apply_redigestion` deprecated with a `DeprecationWarning`).

Out: who writes the words (the runtime), the queue (0060), the ripple (0061), prompt text; a `rewrite` revision op in
`MemoryGraph` (decision 6a: when homes hold the graph tables).

## Dependencies
None. 0060 and 0061 build on the verbs.

## Acceptance Criteria
- [x] After `rewrite_digest`, the record's graph id, digest assertion id, edge assertions, `selected_count` and the
  six journal families are byte-identical; the default replay stream has no new row.
- [x] The version family holds version 0 (the original) and version 1 with author, reader, sources and cause.
- [x] Keyword search finds the new words and no longer the old; the FTS5 integrity check passes; the stored vector
  is the new text's and a vector query ranks by it.
- [x] A stale `expected_version`, a protected kind, empty text and an unreachable embedder are each refused with a
  named reason, and nothing is written.
- [x] `revert_digest(r, 0)` restores the original text as a new version.
- [x] `author_world_model` keeps the card id; `in_place=False` still forms revision N+1.
- [x] `dream_pass` returns `signals`.
- [x] Each mechanism has a mutant that turns its test red.

## Testing
- `python -m pytest tests/test_rewrite_digest_in_place.py tests/test_dream_pass_signals.py -q`
- `python -m pytest tests -q -m "not integration and not lmstudio"` (the CI command)

## Risks
- Recall changes because digests are recall currency: deliberate, per the ruling.
- Every rewrite of a vectored row bumps `vector_generation`, so each process rebuilds its vector matrix before its
  next semantic query (measured cheap at live home sizes: at most about 2,200 vectored rows).

## Report

Implemented 2026-11-08 on `main` (commit recorded in the overview ledger once reviewed).

What landed:
- `understanding.py` (the verbs and reads), `system_understanding.py` (facade mixin), `UnderstandingVersion` in
  `journal.py`, the version family in `journal_sqlite.py` / `journal_sqlite_rows.py` (`_append_version_on` joins the
  store's transaction, the `MemoryGraph` closure precedent) and `journal_memory.py`; the row primitive
  `SQLiteTripleStore._rewrite_row_on` (FTS5 `delete` with the old indexed text, then the new text under the same
  rowid; only for rows the index holds) and `InMemoryTripleStore._rewrite_row`.
- Reserved row attributes: `digest_version`, `digest_method`, `authored_by` (label string, read by the card delta
  path), `understanding` `{version, field, author, reader, cause, sources, derived_from, understood_at}`; dreams
  `narration`, `narration_version`, `narration_provenance`.
- The runtime's two card-authoring suites (`abstractruntime/tests/test_topic_election_world_model.py`,
  `test_election_consequence_teaching.py`) pass unchanged against the in-place default.

Tests: `tests/test_rewrite_digest_in_place.py` (29 cases over both substrate pairs, plus the LanceDB refusal),
`tests/test_dream_pass_signals.py`, `tests/test_doctoring.py::test_cold_cut_keeps_understanding_versions`. Mutants
(listed in the test module docstring) were applied one at a time with a harness that restores the file byte-exact:
skip the version append (both backends), skip the FTS delete, never re-embed, ignore the CAS, skip the closure check,
drop the revision merge, drop the dream_pass signals, disable the card in-place branch, never capture version 0,
drop the versions table from the cold cut. Each turned its test red.
