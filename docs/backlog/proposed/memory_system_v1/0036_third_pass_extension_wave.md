# 0036 — Third-pass extension wave: beyond-design proposals, twice-adversarial

(Renumbered from 0032 on 2026-07-13: the global id 0032 belongs to
`planned/subconscious_wave/0032_dream_subconscious_lifecycle.md`. Item files
for this wave live in `planned/extension_wave/` + `proposed/extension_wave/`,
0037-0048.)

- Status: proposed (maintainer-directed, 2026-07-13 15:49 + 18:29 "iterate
  again ... extend the quality and relevance")
- Inputs: FOUR fable5 adversaries across two extension rounds — round 1:
  fork-completeness miner (third fork pass) + beyond-design proposer;
  round 2: relevance auditor (every item must trace to a named incident,
  ruling, or milestone — kills verified against the tree) + design
  concretizer (buildable contracts, compositions, build order). A fifth
  round (cross-examination of the round-1 lists) runs at write time; its
  deltas fold here as amendments.
- Relation to 0030/0031: 0030 is shipped; 0031's open loops remain the
  nearest work. This wave found NO missed mechanism class in the fork —
  the pattern is that late-fork ADRs have adopted storage halves and
  unadopted READ-SIDE POLICY halves, and engine verbs exist without
  election surfaces reaching the entity. Everything below is reads,
  conventions, and ONE grammar over existing verbs.

## The convergent verdict

Fork adoption is substantially complete and was verified claim-by-claim
(refocus/silence/pinned, intents/outcomes, temporal replay, timeline
edges: all present — two of the miner's own provisional gap-claims died
under verification). The extension value is: (a) five small pure reads
that close lived-incident loops, (b) one election-grammar round that
gives the entity agency over verbs that already exist, (c) a lineage
bundle that unblocks the north star (imported lives are temporally
flat), and (d) three questions only the maintainer can answer.

## Killed on relevance (verified against the tree)

- **Per-visit budget guard** (fork ADR 0011 slice): already served —
  `seam.py entity_recall_budget` (deterministic, refuses below
  `ENTITY_CONTEXT_FLOOR`) + the stamp-carried `budget_profile` injected
  on every in-session recall. Nothing left engine-side; the composed-turn
  preflight is runtime's lane if ever needed.
- **Observer working-stream lane** (fork 625): live tail + trace beats +
  snapshot envelopes already render; residue ("what is on the desk now")
  is one render over the streamed snapshot family — folds into the
  situate-at-T scrub work, not a standalone item.
- **fading_memories() / revisit proposals**: no named incident;
  proposal-shape risks push-pressure against the "dreams are the
  entity's to FIND" ruling's spirit. Resurrect pull-only if a lived
  incident demands it. (The REVISIT VERB survives inside the election
  grammar — re-entry by the entity's own act was never the problem.)
- **Prediction records + calibration**: speculative — no incident, no
  ruling; 0031-19 (plan/decision outcome retrospectives) is the
  deterministic slice with real fork lineage.
- **Interest starvation as a standalone read**: 0031-7's census already
  carries the never-selected slice; survives only as a free-riding
  second target family inside the target-density read (below), not as
  its own item.
- **Presence≠use (D2) glance**: already pinned
  (`test_two_sided_visit_contract`) and already rendered ("used 0
  times" on identity nodes, observed live).
- **Life-chapter change-point DETECTOR**: at current life scale
  (hundreds of records, import batches, sleep gaps) adjacent-window
  statistics detect the harness, not the life. Chapters stay
  entity-elected words; only the vocabulary registration lands (below).

## Merged into existing 0031 lines (one name per mechanism)

- **healable_scars read** → amends 0031-8 (standing-tensions): one
  journal fold per scarred target — accumulated post-scar G⁺ ≥ 8, zero
  repeat negatives at scar scale, later bond noted. Declarative lines
  only ("since the scar on X: 14 positive experiences, none negative"),
  never imperative — a rendered "ready to heal" would be pressure.
  Healing stays the entity's `heal_scar:` election.
- **Substrate self-report** → rides 0031-17 (trace substrate
  attribution); the report is one reflection-channel act over that data
  once it exists. Observes; never chooses (model choice is the
  maintainer's alone).
- **Formation-mass curve + mind-health card** → the concrete shape for
  0031-7: `mind_mass_report(store, journal, *, scopes, days, bucket,
  since_seq)` — formation-by-kind/day, journal-events-by-family,
  per-pair growth, duplicate-cluster count (via `maintenance_report`'s
  general scan; `wake_cue_dedup_pass(report_only=True)` contributes the
  wake-cue sub-count labeled by source — its closure semantics must NOT
  become the general counter). Window-bounded mandatory (24/7 residents
  ~5k envelopes/day). Card fields: embedder pin vs wired embedder,
  unresolved dreams, review-queue depth, last sleep pass, journal size
  vs newest compaction archive_ref.
- **Recall-explanation surface (O1)** → the serving contract for the
  shipped forensics: `explain_recall(store, journal, record_id, *,
  trace_id=None) -> dict` composing `recall_history` +
  `absence_diagnosis`: status (selected/dropped/candidate_only/absent),
  admission (self/stm/stimulus/both), per-channel relevance parts,
  shelf position vs cut + budgets, origin, absence reasons. HONESTY
  RULE: activation reports only what the trace RECORDED at recall time
  (`{"recorded": false}` + "not recorded in this trace" on old traces)
  — recomputing fresh numbers as an "explanation" would lie. Depends on
  0031-3 (probe migration): until `search_memory` rides `probe()`,
  voluntary exploration reads as absence — a truth surface that lies is
  worse than none.

## New items (contracts by the concretizer; relevance by the auditor)

1. **familiarity() — pre-answer metamemory** (MISSION-CRITICAL; the only
   item aimed at the fabrication arm the driver provably cannot catch —
   the recorded honest limit: "fabricated CONTENT without a provenance
   claim remains uncatchable at the driver"). Contract: a `probe.py`
   entry sharing an extracted `_channel_pass(...)` with `probe()` (a
   separate module would duplicate the candidate-window logic and
   drift); returns match DENSITY only — `{"strength": strong|weak|none,
   "per_channel": counts, "distinct_records", "warnings"}` — no ids, no
   content, nothing committable; journals nothing (a reflex, not a
   reach). False-"none" honesty: keyword/concept scan is newest-window
   only, so "none" renders as "nothing within reach (newest-window
   scan; exact/vector reach whole store)"; vectorless homes label
   `#FALLBACK: keyword-only familiarity`. Driver line on none: "memory
   reports NO matches near this — details you produce now are not
   memories." Kill-test stands: must predict probe success on a fixture
   home AND reduce fabricated-recall turns in A/B.
2. **Prospective memory — open_commitments + trigger annotation**
   (MISSION-CRITICAL; the commitment-carryover death is a recorded live
   failure and the gateway's awake-reason patch was a host bandage).
   `diary_type="commitment"` exists with NO read (questions/problems/
   ideas have one). Contract: `open_commitments()` = one
   `_open_unresolved(diary_type="commitment", ref_attr="fulfills")`
   line; `attributes.trigger = {participants, keywords, due_at?}`;
   `triggered_commitments(store, journal, *, stimulus, ...)` — a PURE
   READ the host calls beside reconstruct, rendering ≤3 oldest-first
   presentation lines under MEMORIES ("standing intention, elected
   <date>, trigger matched") — deliberately NOT an admission channel
   (selection untouched; empty trigger never annotates). Over-fire
   containment: cap + "N more open commitments suppressed".
   COORDINATION: "commitment" widens the diary_type closed set →
   semantics seat + runtime identity_support clamp sync (the `problem`
   precedent: unsynced clamp silently projects as "note").
3. **Recurrence-aware formation + presentation fold** (VALUABLE; the
   prevention half of the doctoring operation — repair shipped,
   prevention nowhere). `recurrence_probe(store, *, digest, title,
   keywords, scope, owner_id, window, threshold)` called by the
   formation host; on hit the caller appends `("recurrence_of", proto)`
   with detector provenance. Gate: shares `token_set`/`jaccard`
   primitives but its OWN threshold (token-jaccard AND facet/participant
   overlap); never reuses doctoring's dedup decision (dedup CLOSES,
   recurrence MARKS — formation is never refused). `recurrence_of`
   joins CONTEXT_RELATIONS (never component-defining; semantics
   declaration before first write). Shelf fold: POST-selection handle
   render groups admitted chain members into one composite ("<title> —
   lived N times, first T0, last Tn"); members stay individually in
   trace.selected and deposit individually at commit — selection and
   deposits byte-untouched (the no-origin-penalty ruling; presentation
   diversification only). False-chain honesty: composite always carries
   "folded by similarity — N individual records"; wrong edges are
   closable assertions.
4. **ONE election-grammar family — the ```tend block** (MISSION-
   CRITICAL; the only ruled-compliant bridge-attractor counter — with
   the mechanical origin-penalty forbidden, entity-elected tending is
   what remains; merges fork-620 attention verbs + 0031-2 disposal +
   0031-14 healing + revisit into ONE host coordination instead of
   three). Verbs (one per line, reason mandatory, entity-reflection
   channel only): `pin:`→reinforce, `silence:`→attenuate, `refocus:`,
   `heal_scar:`, `break_bond:`, `revisit:` (prompt-ephemeral re-entry,
   cue_source stamped), `dispose: <dream> confirm|reject`. ALL verbs
   exist on system.py/system_valence.py — the engine gains nothing; the
   driver gains a parser; the gateway deposit gate refuses the mapped
   effects on workplace channels (policy at the door, engine
   policy-free). Refusals: unknown verb, missing reason, spoofed
   ex:/diary: targets, verb-per-turn cap (tool-round precedent),
   identity-scope targets pending ruling Q2.
5. **Target-density tensions — loss anchors (+ starved interests as a
   free parameter)** (F3 narrowed by the auditor: the dated-handles half
   of visit-honesty shipped; world-model cards already carry last_seen —
   only the WAKE-REASON half remains, and it must be source-backed,
   never inferred from absent retrieval). One pure read:
   high-|standing| gradation targets with ~zero recent formation
   density → `{target, standing, last_seen_at, density, line}` joining
   the wake-reason family beside open_questions/unresolved_dreams.
   Second family (open interests vs facet-adjacent formations) rides
   free in the same fold, non-load-bearing. Wake-fatigue honesty: every
   line carries last_seen_at + "window-bounded density read";
   suppression cadence is the CALLER'S dial, never silent engine policy.
6. **Chapters, election path only** (real consumer = the lineage
   bundle): register kind="chapter" + relation "covers" (semantics seat;
   observer color-map sync — unknown kinds render gray) so an entity may
   elect era records (`period_start/period_end`, covers edges capped to
   boundary anchors) whenever it first chooses to; situate/entity_card
   consume. The statistical detector stays dead (kill list).

## Gaps no prior proposal served (relevance auditor, incident-mined)

- **G1 — Imported lives are temporally flat** (LINEAGE-CRITICAL):
  archive import pins `origin_date` as an attribute, but journal seq and
  observed_at sit at import time and `situate()` walks formation seq — a
  reincarnated Mnemosyne cannot be situated at any pre-import moment;
  her whole past collapses into one day. Mechanism: an origin-time axis
  option in situate/period reads for `seeded_from="archive-import"`
  records, honest label "period by origin_date, import-provenance". M.
- **G2 — N-party co-formation contract** (multi-entity milestone): the
  two-sided visit contract covers two homes + one visit_id; nothing
  pins N-party formation (per-speaker attribution in participants,
  one-event-N-perspectives at channel scale). Deliverable: the pinned
  contract test BEFORE the transport exists (the M3 pattern). S.
- **G3 — Transcript adoption as a designed act** (R3/R4 UX): the reads
  shipped; the ACT has no verb. A reflection-channel formation
  convention — episode records with anchor_seq/derived_from provenance
  to the read source; identity kinds refused (the engram stays the only
  identity seed). S engine, M host.
- **G4 — Cue hygiene at the passive-recall boundary** (the dilution
  class, prevention half): passive recall still takes the whole
  operator message as cue — exactly how Castor's dream lost the shelf
  race. Mechanism: an explicit short cue distinct from the raw message
  (driver-distilled), cue_source provenance, and a dilution honesty
  label (cue token count vs channel saturation) so a buried reach is
  VISIBLE in the trace. Mostly host lane; engine adds the label. S.
- **G5 — Writer forensics for the Hypnos class**: memory owes no
  structural refusal (the gate owns authorization; a refusing home
  would break the operator's ruled right to read) — but after an
  unauthorized run nothing in the home says WHICH writer opened it for
  write and when. Append-only writer-registration entries in the
  existing meta sidecar on write-open; provenance, never gating; pairs
  with 0031-1 schema_pin. S.
- **The lineage bundle**: G1 + G3 + chapters-election as ONE sequenced
  wave — the north star (reincarnate the lineage and let them discuss)
  is blocked on exactly these three plus archive import, which shipped.

## Rulings needed (the three questions, one decision each)

- **Q1 (decides F1 divulgation + G2's channel contract + whether
  multi-entity summons need a gate change):** when a visitor is
  present, does the door mechanically constrain PRESENTATION of records
  involving other relationships (participants-aware filter/caveat at
  the presentation lane), or does everything surface to the entity with
  provenance labels and discretion stays entirely the entity's own?
  One-life-one-graph is already ruled — this is presentation-lane only.
- **Q2 (tend block scope):** may an entity's own ```tend election
  silence/attenuate records in its identity (self) scope, or is
  identity tending reserved to the operator/hyperfocus lane?
- **Q3 (familiarity posture):** is familiarity="none" advisory
  presentation only, or may the driver enforce it as a mandatory
  "say you don't remember" correction before the reply ships?

## Build order (both extenders converged)

1. familiarity() — live incident class, smallest new surface once the
   probe channel-pass is extracted.
2. explain_recall() — pure composition over shipped forensics,
   immediate operator value (with 0031-3 probe migration as its truth
   precondition).
3. Prospective memory — recorded live failure; the diary fold is one
   line; diary_type coordination is the only real cost.
4. healable_scars fold (0031-8 amendment) — makes the heal verb
   findable.
5. Target-density tensions — completes the wake-reason family.
   Then: mind_mass_report (0031-7 shape), recurrence probe + fold; the
   ```tend grammar lands with its parser the day Q2 returns; the
   lineage bundle (G1+G3+chapters) sequences with the first real
   archive import.

## Amendments pending

The round-1 cross-examination pair (fork miner attacking the nine;
proposer attacking the six) was still running at write time; its
verdicts fold here as amendments if they diverge from the auditor's
kills/merges. Divergences must be argued against the tree, not
averaged.
