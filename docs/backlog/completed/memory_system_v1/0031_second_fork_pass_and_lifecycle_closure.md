# 0031 — Second fork pass + lifecycle closure wave (proposals)

- Status: Completed (2026-07-20)
- Inputs: three adversarial reviews (fork CODE second pass; fork BACKLOG
  second pass; lifecycle/process critique across both frameworks), each
  instructed to reject deltas-without-value. This ledger is the
  deduplicated union of what survived, cross-checked against the tree.
- Relation to 0030: 0030's adoption list is SHIPPED (probe/expand,
  disposal, concept anchoring, recall reads, archive import, sleep
  phase-1 + cadence). This wave is what the second pass found BEYOND it —
  and one drift INSIDE it (probe reports, below).

## The convergent verdict (all three reviews, independently)

The phases are individually complete and honest; the LIFECYCLE has open
half-loops. The proposing/recording halves shipped engine-side; the
disposing/consuming halves were left to hosts and no host picked them up;
and there is no health surface that would make that debt visible. The
highest-value work is closing loops that already exist, not new
mechanisms.

Open half-loops found (verified against the tree, 2026-07-12):
- disposal verbs (`dispose_dream`/`promote_candidate`/`reject_candidate`)
  have ZERO callers in runtime/gateway — sleep proposes nightly into a
  queue nobody can discharge; the wake cue even tells the entity
  "candidates await your waking evidence" with no verb to give it;
- `probe()` has ZERO callers — the live entity search surface
  (`HomeMemoryReader.search_memory`, runtime) bypasses the engine's
  deliberate reach entirely: no traces, so `recall_history` reads
  voluntary exploration as "absent"; concept anchoring (ON in probe) is
  reachable by nobody in a live home;
- healing is entity-unreachable: the `MEMORY_APPRAISE` seam handler
  accepts `heal_scar`/`break_bond` (runtime seam_handlers.py) but no
  election grammar offers them — every scar is permanent by accident,
  against the ruled trauma model (healing = entity reflection);
- report surfaces with no consumers: `metadata_gaps` (re-digestion never
  built; `reflector` param dangling since v1), `maintenance_due` (no
  caller; the loop sleeps unconditionally), `unresolved_dreams` absent
  from gateway `wake_reasons()`.

## P0

1. **Schema pin + forward-compat refusal for home stores** (fork
   memory.rs CURRENT_SCHEMA_VERSION lesson). A `schema_pin` generation in
   the existing meta sidecars (journal + triple store; generation int +
   writer version as provenance). Open-time: pin newer than engine →
   loud refusal naming both; older → additive migrations + bump in one
   transaction. Mirrors `embedding_pin` ("store identity rides in the
   store"). Why now: homes are never-purge, travel by directory copy, and
   the engine has already widened schema twice (embedding,
   admissions_json) — an older engine opening a newer home today silently
   serves a PARTIAL LIFE. That is accidental aging, the exact class the
   fork refuses loudly.

2. **Review queue + disposal channel** (lifecycle closure). Engine half:
   `pending_review(store, journal, scopes)` — ONE pure read composing
   unresolved dreams + inactive review-gated candidates + edge-suppression
   proposals, each item carrying the verb that discharges it and the
   evidence it needs (today a host would hand-assemble three shapes from
   three modules). Host half (runtime/gateway ask): a reflection-channel
   election (```dispose``` block or tier-1 tool) wired to the disposal
   verbs — deposit gate already composes channel rules; verbs already
   take actor. Also completes dream delivery within the "his to find"
   ruling: the queue is where a dream is FOUND, not pushed.

3. **Probe becomes the live active-reconstruction surface** (runtime
   lane; engine ready). Migrate `search_memory` onto `probe()` so
   voluntary exploration lands in traces (recall_history stops lying),
   concept expansion runs where it was built for, and one cognitive act
   has one implementation. Book-plane merge and gist-only rendering stay
   runtime-side. ENGINE PREREQUISITE that must land first:
   **relation filter on `probe_expand`** — the walk currently traverses
   ALL record edges and ranks by connection count; dense diary
   `written_amid` edges will win the ranking from any diary-adjacent
   root (the same reasoning that forced CONTEXT_RELATIONS out of the
   dream pass's component definition). `relations`/`exclude_relations`
   threaded through the BFS, default excluding context relations.

4. **World-model orientation records** (fork 750 + ADR 0019; upgrade the
   0030 runner-up to a designed item). One review-gated, source-linked
   orientation record per (target, time-window); targets = the gradation
   universe (person/tool/place/project/time — free strings); formed only
   by the sleep pass; revised via `refines` chains (append-only,
   latest-as-current); digest = orientation + caveats, never authority;
   staleness/loss source-backed, never inferred from absent retrieval.
   Value: the maintainer's SITUATION "profile recall" leg (round 5) has
   no artifact — a returning visitor surfaces N raw episodes competing
   for shelf seats instead of one compact "shared history, where we left
   off" seat; multi-entity summons (the north star) need per-peer
   orientation. Guards ride with it: dream-only evidence can never
   source a participant model; live correction supersedes; never
   prompt-active by hand; formation-kind reserved (see P2-10).

## P1

5. **situate() — the composed historical read** (fork time_anchor is the
   battle-tested reference; the seam already reserves
   `admission="historical"` and journal threading calls itself "situate()
   groundwork"). One facade verb in a new `situate.py`: anchor (ISO/seq)
   → `seq_at` → snapshots + traces at-or-before + `compute_activation(
   at_seq)` + observed_at-windowed records + diary-around-T handles;
   every handle labeled historical; deposits nothing (anti
   trapped-in-the-past). Maintainer's temporal-graph HARD requirement;
   currently scheduled nowhere.

6. **Probe-report records** (adoption drift inside 0030 item 1: the
   ledger and 0022 both promise them; probe.py writes traces + inert
   audit events only). Optional report step: kind=`probe_report`, digest
   = source-cited synthesis with the advisory-boundary line,
   `derived_from` edges, provenance carrying the trace id; formed via
   `remember_many` with a trace-derived idempotency key. Closes
   "a deliberate reach leaves no findable residue" and lights up the
   existing `cited` audit kind.

7. **substrate_health() census** (the fork's 105/370/610 lesson — their
   selector-health line exists because silent selector death was a
   repeated live failure; our embedding-pin incident is the same class,
   fixed for embedder identity only). One pure read, folded into the
   tending report + entity card/operator CLI: reachability census
   (vectorless / keyword-less / past-all-windows / never-selected counts
   — `absence_diagnosis` logic in bulk), embedding-pin state,
   attention-window coverage vs MEASURED event cadence (say "your 512
   window covers ~7h at current cadence" instead of a docstring),
   pending-review debt, FTS availability once 0019 lands. The
   never-selected slice doubles as the fork-780 diagnostic half (the
   unconscious stratum made measurable) WITHOUT its ruled-out
   ephemerality half, and feeds re-digestion targets.

8. **standing_tensions() — one wake-reason read** (beside diary.py's
   open_* family): open questions + problems + ideas + unresolved dreams
   + unhealed scars + pending-review debt in one labeled shape. Gateway
   `wake_reasons()` and the loop's wake cue consume it instead of
   hand-assembling — the gateway already silently dropped dreams, which
   is the failure mode this kills.

9. **Deliberate-use strengthening convention** (needs an a2a ruling —
   touches presence≠use vocabulary). Reading search/probe RESULTS stays
   free (fork-aligned: their Shown/Expanded deposit nothing). But when a
   found record is RE-ENTERED into context as a memory (rendered, not
   merely listed), the host re-reconstructs with `anchor_record_ids` +
   `cue_source="probe_re_entry"` and commits through the existing path —
   the diary re-entry pattern generalized. Without it the global count
   systematically undercounts exactly the records the entity cares
   enough to go looking for ("at the end of your life, what matters").

10. **Dream/candidate formation metadata** (small): dreams form with
    keywords = the shared facets/participants their proposals carry
    (honest metadata — that IS the dream's content) and digest prose
    naming top facets, so sleep's one artifact stops being the least
    reachable record in the home.

11. **Scenario library from lived incidents** (fork 370/420/520/600's
    single most experience-shaping practice; tests-only, no engine
    machinery). Fixture-home harness where each OBSERVED failure is a
    named, repeatable scenario with structured grading and an explicit
    `known_gap` state (reproduced, tolerated, visible — never silently
    re-baselined): cue-dilution; bridge-attractor seat competition;
    dream-reach; cleanroom cross-summon recall; teach-bug honesty
    (record-vs-memory disagreement). Our incidents live as AGENTS.md
    prose + one-off pins today; this is the regression net for RECALL
    QUALITY, which unit tests don't cover.

12. **FTS5 (0019) priority correction**: keyword channel, concept
    anchoring, near-dup tending, and probe's saturation warning all
    bottleneck on the same window-bound scans; the fork treats FTS
    absence as a hard store error. Not new — evidence now compounding.

13. **Coverage bands + temporal density in the structural surface**
    (Mnemosyne-authored fork item): per-facet coverage (dense/sparse/
    absent, corpus-measured — no stopword lists per the fork's own ADR
    0017 line) + per-period formation density in `structural_report`,
    exposed through the planned tier-1 structural query. Turns felt
    absence ("which stretch of my life is thin?") into a self-serve
    check — the diagnosis method that worked live, given to the entity.

## P2 (one line each)

14. **Healing election grammar** (runtime lane): ```feel``` grammar gains
    heal/break ops → the EXISTING MEMORY_APPRAISE channel; engine change
    zero. (Correction recorded: the seam handler already accepts them.)
15. **Reserved formation kinds**: kind=`dream` (and future sleep-born
    kinds) require maintenance provenance — anyone can forge the origin
    class our corroboration currency leans on; enforcement hook offered
    engine-side (like summary-requires-edges), gate coordination for the
    channel half.
16. **Dream-only-support read caveat**: pure-read provenance check —
    records whose evidence closure is dream-only get the advisory label
    at read time (bridge-attractor laundering counter).
17. **Trace substrate attribution**: optional consumer identity
    (provider/model) into trace `need` — substrate swaps become
    SUBSTRATE EFFECTS in the record, not drift mysteries. Seam-additive.
18. **Re-digestion plan/apply** (`redigest.py`, archive-import two-stage
    pattern over `metadata_gaps` + `digest_method=mechanical-*` targets;
    revision + supersede with regeneration provenance; fork 790 shape).
    Retires or employs the dangling `reflector` param.
19. **Plan/decision outcome retrospectives** (fork 355): tending names
    plan/decision records with no outcome edge after N formations;
    capture stays a waking act. Cheapest deterministic slice of the
    stale-truth problem.
20. **Lesson/instruction applicability conventions**: `applies_when`/
    `caveats` attributes + instruction `category` (rule|instruction|
    process) — a taught procedure currently forms indistinguishable from
    a world lesson.
21. **Semantics-registry batch** (one c184 coordination): `raises`/
    `answers` (question lifecycle → wake reasons) beside the already-
    queued `disagrees_with`/`supports`.
22. **Attention event rollup/retention** for 24/7 residency (the
    512-window ~8h saturation is measured, not hypothetical).
23. **Epistemic-status labels** (observed/inferred/hypothesized/
    dream_signal/corrected) as an attribute convention surfaced in
    search origin lines.
24. **`maintenance_due` gets its caller** (host lane, trivial) — dead
    code presenting as a lifecycle phase otherwise.
25. **Per-relation direction validation in `confirm_relation`**
    (semantics c1151 ask 2a, accepted 2026-07-12): endpoints are
    caller-asserted with nothing enforcing per-relation direction —
    validate against the registry's declared semantics (subject=new/
    derived record for the derivation family; subject=evidence for
    supports; subject=part for part_of). DEPENDENCY SHIPPED same-day
    (semantics c1153): every memory_relations entry now declares
    machine-readable subject_role/object_role (MemoryRelationDef fields,
    test-pinned) — the validator reads the registry directly and error
    messages get the role nouns for free. Unblocked; build when the
    disposal channel work resumes.

## Ruled out this pass (so the next pass doesn't re-mine them)

Auto-disposal in sleep (violates waking-evidence); valence-aware recall
(valence never gates); ephemerality/archival tiers (storage never
decays; 0030 ruling re-confirmed); LLM selector pipeline + staging +
selector-health-as-LLM-eval (no selector here; deterministic channels);
qmult (maintainer-removed); participant identity heuristics (door-verified
principals are stronger); ai_self auto-participant (explicit co-presence
ruling is stronger); confirmation phrase lists (structural corroboration
instead); checkpoints/restore (append-only life; a copy is a fork);
canary self-tests in real homes (never-purge → engrave forever; census +
fixture harness are the compliant versions); time-driven confidence decay
(staleness arrives as evidence, never as a clock); persisted concept
index (FTS5 is the general fix); origin-diversity shelf quota (selection
gating dressed as presentation); observer model-backed summaries (an
observer that synthesizes is not a pure read); fork CLI/app-server/
context-block plumbing wholesale.

## Sequencing note

P0-1 (schema pin) should land before the next release that widens schema.
P0-3's engine prerequisite (expand relation filter) before probe goes
entity-facing. P0-2/8 (review queue + tensions) are the entity-lifecycle
unlock and want a runtime/gateway coordination round on the election
surface. P0-4 (world models) is the largest design item — own a2a round.


## Completion report (2026-07-20)

Executed: lifecycle closure shipped (dream disposal verbs, resolve_dreams_pass, promote/reject candidates with independence test, interest lifecycles) — the second-pass items landed across the extension + subconscious waves.
