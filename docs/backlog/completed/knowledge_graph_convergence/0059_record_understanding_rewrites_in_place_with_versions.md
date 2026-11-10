# A record's understanding is rewritten in place and every earlier reading is kept as a version

Status: Completed · Completed: 2026-11-10 · Shipped in: abstractmemory 0.5.0 (commit `5c6136b`, local `main`; not
yet tagged, pushed or published on 2026-11-10) · Original path:
`planned/knowledge_graph_convergence/0059_record_understanding_rewrites_in_place_with_versions.md` (a one-line pointer
since 2026-11-10; see the overview's planning note) · Item history: written with the code in `3fbaf10` (2026-11-08),
closed by the backlog commit that created this file.

Created: 2026-11-07 (understanding pass; [ADR 0003](../../../adr/0003-one-graph-ledger-provenance-and-revisions.md)
decision 6a, [ADR 0001](../../../adr/0001-altered-memories-ripple.md) decision 6).
Track: `knowledge_graph_convergence` · Priority: P1 · Type: feature · Status (as planned, 2026-11-08): Planned — engine half implemented on
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

## Completion report (2026-11-10)

Outcome: done. Every acceptance criterion above was met by `3fbaf10` (2026-11-08) and holds at the release commit
`5c6136b` (abstractmemory 0.5.0, CHANGELOG `[0.5.0]` "Added: understanding rewritten in place (0059)").

Shipped in 0.5.0 on top of the item, extending the same "rewritten in place, every earlier reading kept" contract
(no backlog item of their own; recorded here and in the overview ledger):
- `e74c29c` read-time provenance: `understanding.reading_provenance` makes every record say who wrote its words, when
  and why, even when its writer stamped nothing (a row without a stamp reads as its formation reading, derived from
  its origin); `remember_many` records that reading at formation. Test: `tests/test_reading_provenance.py`.
- `8ac6df4`, `566f174` stored text never cut (root ADR 0054): card gists, dream-signal fragments
  (`dream_signals.FRAGMENT_CAP` removed), canonical-text context (`CANONICAL_TEXT_VERSION` 3), snapshot titles and
  archive-import digests kept whole; `20cd1f4` titles explicit and whole. Tests: `tests/test_stored_text_whole.py`,
  `tests/test_titles_whole.py`.
- `d4fc7e4` `retitle` (`understanding.py`): a record's title changed alone, in place, every earlier title kept as a
  version, `title_version` the compare-and-set; refusals `empty_title`, `hash_chained`, `closed`, `stale`,
  `embedder_unavailable`. Test: `tests/test_retitle.py`.
- `6e4ca13` `rekey_world_model` (`world_model_alias.py`): a standing card moves to a new key in place, the old key
  kept as an alias; `retitle` re-keys an untitled interest's `topic:<graph id>` card (`card_rekey`). Test:
  `tests/test_world_model_rekey.py`.
- `15ef176` identical authored words settle a pending field (Codex review 3 finding 7,
  `untracked/entity-phases-2026-11-08/review/CODEX-REVIEW-3-runtime-memory.md` at the framework root). Test:
  `tests/test_identical_authoring_settles.py`.
- `cc1ed75` the identity card's `lessons` section counts the lessons written in the diary.

Validation:
- Release suite at `5c6136b`: `abstractmemory/untracked/release-0.5.0/pytest-full.log`, 2291 passed, 3 skipped,
  2 xfailed, exit 0 (the CI command, LM Studio tests deselected); `build.log`: sdist and wheel 0.5.0 built.
- Re-run on 2026-11-10 at `5c6136b` of the 17 modules behind the 0.5.0 features (this item's
  `test_rewrite_digest_in_place.py`, `test_dream_pass_signals.py`, plus provenance, retitle, rekey, stored text, the
  queue, ripple, fence, communities, pending, cadence, engram): 605 passed, 2 skipped.
- Mutants: listed in `tests/test_rewrite_digest_in_place.py`'s docstring (see the Report above), each red.
- Fable pre-tag review (framework root) `untracked/finish-plan-2026-11-09/graph-topics/REVIEW-memory-0.5.0.md`:
  GO for the tag; CHANGELOG, `api.md` and llms claims checked against the code.

Docs: CHANGELOG `[0.5.0]`; `docs/api.md`, `docs/memory-system.md`, `docs/architecture.md`; ADR 0003 decision 6a.
ADR state: ADR 0003 decision 6a (amended with this item). No new ADR; root ADR 0054 (stored text never cut) is the
framework's.

Behaviour changes for hosts: `apply_redigestion` emits `DeprecationWarning` (use `rewrite_digest`); `version_count`
is 1 for a record never rewritten; the LanceDB store refuses `rewrite_digest` (`NotImplementedError` naming this
item; the home store is SQLite).

Residual risks and follow-ups:
- Every rewrite of a vectored row bumps `vector_generation` (each process rebuilds its vector matrix before its next
  semantic query); measured cheap at live home sizes. The batching question for `embed_missing` is
  `proposed/0065_embed_missing_vector_generation_bump_batching.md`.
- Still out, as scoped: a `rewrite` revision op in `MemoryGraph` (decision 6a, when homes hold the graph tables).
- Who writes the words is the host's: the tracked runtime drain (`abstractruntime/identity/authoring.py`
  `drain_authoring`) runs only `title.author` / `digest.author`; the full drain is root backlog 1171 (planned, paused).

Backlog drift found: the header's "runtime 0869" and "gateway 1012" are draft numbers
(`untracked/understanding-pass-2026-11-07/drafts/` at the framework root) never filed under those numbers in their
repos (root `planned/understanding-pass/README.md`: "use the root ids"; gateway 1012 is another item there). The
gateway already serves the stored understanding (draft 1012, gateway `1b3832b7`, `fa75c70a`, `79f47c5b`, local); the
reader that writes the words is root 1171 (planned, paused).
