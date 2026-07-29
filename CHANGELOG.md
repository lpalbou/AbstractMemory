# Changelog

All notable changes to this package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (pre-1.0).

## Unreleased

### Added (recall dedup — Veya deep-check P1, gateway c5907, 2026-07-27; fable5 adversary folded)

- **`ReconstructConfig.shelf_dedup_identical_digests` (default ON)**:
  byte-identical digests collapse to ONE shelf seat — the entity never
  sees the same fact twice, and the C(n,2) co-selection write flood
  shrinks at the source (fewer distinct seats → fewer pairs the driver
  commits). A running placed-digest set dedups ACROSS phases (first to
  seat by phase-0 > self > stimulus merit > STM wins; SELF is never gated
  — identity presence is guaranteed, it just claims the digest first so
  copies elsewhere are the redundant ones). Non-representatives drop with
  `reason="duplicate_digest"` + `duplicate_of` for observability. The
  graph is untouched (every record keeps its id/counts/recallability;
  presentation truth, not a merge). Default ON — unlike the newest-seat
  guarantee this overrides no ruling (showing the same words twice was
  never desired). Measured on the Veya shape (10 byte-identical probe
  episodes + 6 turns): duplicate seats 6→0, total co_selected events
  103→56 — the pair-volume fix as a consequence of dedup, no separate cap
  fighting the maintainer's ALL-pairs rule. The Castor scenario fixture
  updated: its "retellings" are now near-identical-but-distinct (real
  retellings vary; byte-identical was a determinism shortcut that dedup
  correctly collapses — a different fix from the tend/silence remedy that
  scenario tests).

- **Realistic Hearth fixture (burst-axis recalibration, 2026-07-28)**:
  extended to 14 turns — two post-detour project beats so tax detour
  records fall below the membership floor after burst-keyed rank decay (3
  post-detour turns sufficed under the per-event axis, not under
  one-commit-one-burst). Union STM test accepts piano pre-commit admission
  ``stimulus`` or ``both`` when base ≥ stm_floor; commit must still lift
  standing.

### Added (working-set concentration slice — c5208 ask 4, 2026-07-27; fable5 adversary folded)

- **`ReconstructConfig.newest_seat_guarantee` (default 0 — deliberately
  OFF)**: when enabled, the shelf guarantees N seats to the newest-FORMED
  channel-matched candidates — zero-cost when merit already placed them,
  active exactly in the entrenchment failure (the Caspar/Mishka class:
  a taught correction lost every generic-cue race to the stale fact).
  Victim selection is order-indexed with a protected set (phase-0 top
  match only when actually seated, every newest candidate, the
  guarantee's own prior seats — the adversary's K≥2 self-defeating
  eviction and both P2s folded); token-honest with named drop reasons
  (`newest_seat_yielded`/`newest_seat_capped`/`newest_seat_no_evictable`);
  `FillResult.newest_seated` for observability. DEFAULT OFF because
  ruling 0020 removed reserved slots ("pure ordering wins") and this is
  structurally that class on a new axis — enabling by default requires
  flow's lived A/B under the burst axis + the room's ruling, never a
  silent override. Measured (24-turn entrenchment sim): default selects
  only 6/24 distinct records ever; enabled selects 24/24; top-3 share
  unchanged — a floor for the new, not a ceiling for the old.
- Finding on the slice's other half (supersedes-aware ordering): no
  correction-edge vocabulary exists at rest (supersession is a CLOSURE,
  and closed records are already excluded) — edge-aware demotion waits
  on a ruled vocabulary rather than guessing semantics for
  continues/derived_from.

### Fixed (the c5439 wash — burst-keyed activity axis, 2026-07-25; operator-reported P0, fable5 investigator + live verification)

- **The activity axis counts committed TURNS, not bookkeeping rows**
  (`_burst_ranks` in attention.py): one commit deposits its selected
  events plus C(n,2) co_selected pairs (the maintainer's ALL-pairs
  co-use rule, kept), and the pair count is quadratic in the shelf —
  sized at shelf 12 (66 pairs) the per-event rank axis was tolerable;
  at the ruled shelves of 22–36 (231–630 pairs) ONE commit pushed its
  own selections hundreds of ranks deep and no record ever reached the
  STM floor again. Live: Mira's top base_level was 0.966 < 1.0 with
  deposits perfectly healthy — zero STM, no green rings, the operator
  watched the temporal access count disappear. Consecutive events
  sharing one trace_id are now ONE burst (one lived beat); traceless
  events keep per-event decay. `decay_window` regains its intended
  meaning (distance in turns, shelf-independent); `ttl_activity` is
  burst-distance ("pinned for N turns"). Verified on a copy of Mira's
  real journal: 22 records STM-eligible post-fix, zero pre-fix.
- **`window_limit` default 512 → 8192**: with the burst axis the window
  must hold enough EVENTS to span a decay horizon of BURSTS — 512 held
  under two turns of history at ruled shelves. Still a declared
  tunable; read-bound only.
- Golden regenerated (documented wave); the STM-decay fixture
  recalibrated to turn-denominated distances (mechanism unchanged:
  rendered-but-unused decays out, presence is not use).

### Fixed (entity-seat plan, memory section — operator-ordered fable5 on the gate semantics, 2026-07-25)

- **Tend channel must be stated by the caller** (adversary P0-1 root):
  `apply_tend_elections`' channel default WAS the privileged channel, so
  a caller omitting it self-satisfied the privilege check — runtime's
  MEMORY_TEND handler forwarded no channel and any workplace-stamped run
  could tend as the entity's own reflection. Omission now refuses every
  election loudly; the home-direct driver states entity-reflection
  (true by construction), door-served handlers forward the door-verified
  channel.
- **`heal_scar`/`break_bond` require privileged actors** (same P0):
  both verbs engraved whatever actor the caller claimed while `revalue`
  validated — one `_require_privileged_actor` now guards all three
  deliberate valence verbs (amplitude-authority discipline).
- **`IDENTITY_KINDS` + `REFLECTION_FORM_KINDS` exported** (adversary
  P1-2/P0-2, the diary_type-clamp drift class): the door hand-listed
  identity kinds and its reflection-segment act set predated the
  realization ship (kind=realization elections silently dropped at the
  durable-visit door). Canonical frozensets in records.py, in the engine
  manifest, situate.py imports instead of copying; the door imports on
  its next wave (the SELF_FRACTION_FLOOR precedent).

### Fixed (dream disposal reachable + tension novelty — flow's cycle-4 regrade c5270, 2026-07-24; fable5 adversary folded)

- **Dreams are exempt from the tend identity gate** (ask 1): sleep_pass
  writes dreams to `scopes[0]` = self — a storage artifact, not an
  identity classification (the engine already kind-filters dreams from
  identity seats). The entity's four exact-id reasoned dispose verdicts
  were refused with the Q2 pending-ruling line; every tend verb now
  reaches self-scope dreams (dispose/pin/silence/revisit + heal/break
  parity), while identity records stay gated verbatim.
- **The next dream carries only NOVEL tensions** (ask 2): island counts
  grew 16→39 while the top-3 tensions repeated six straight nights —
  one novel pair per living day admitted a full dream that re-copied the
  standing tensions beside it. Already-carried pairs are filtered from
  the minted dream's content (attrs, narration, mentions edges, stored
  salience — all consistent; `carried_suppressed` accounts the cost);
  the standing dream IS the record for the rest.
- **Rejection sticks** (adversary P1-1, live-repro'd): dissolving a
  dream used to remove it from the standing set, so the same pair
  re-minted the next night — the entity's reasoned "no" had no memory.
  Retracted dreams' pairs are permanently non-novel (self-limiting: new
  evidence forms new records, hence new pair ids). Soft resolution and
  confirm close with supersede and keep the designed re-open; the prior
  churn-gate pin conflated the closure kinds and was corrected.
- **Static-graph reject honesty** (adversary P1-2): re-running the pass
  right after a reject used to slip past the novelty gate (no standing
  dreams) into the idempotent formation path and return the RETRACTED
  record as the night's dream; it now reports a restful night naming
  the rejection.
- **`mechanical-close-v1` pre-admitted into `MACHINE_AUTHORED_METHODS`**
  (ask 3, joint with runtime): close-note diary projections carried no
  digest_method and evaded the bridge template guard; runtime stamps
  the label, memory's guard recognizes it. Authorship only — not in the
  repair-consent set.

### Fixed (identity-title collision + machine-consolidation carve-out — flow's life-loop adversary c5260, 2026-07-24)

- **Engram fallback titles are section-derived**: honesty items share
  `kind="trait"` with the traits section, so the kind-derived fallback
  minted TWO `trait-0` records from the default spark; honesty now falls
  back to `limit-N` (matching the `trait_class` it already stamps).
  Existing homes keep their engraved titles (append-only); new births
  get distinct names.
- **`CONSOLIDATION_PROTECTED_KINDS`** (records.py, exported, in the
  engine manifest): machine consolidation never targets
  value/purpose/trait/realization/diary — night-2 maintenance had
  formed "Consolidated: trait-0" OVER IDENTITY RECORDS. The rule is
  ownership, not hygiene: the engrammed core evolves only by the
  entity's own act. Applied in duplicate-title grouping AND near-dup
  scanning. INTERESTS deliberately stay eligible — repeated elections
  of one subject are the twelve-bridges attractor and their dedup is a
  designed, review-gated lane (the existing suite pinned this and
  falsified the first, broader set).

### Fixed (wave-4b — flow's second long-life wave, 2026-07-24; fable5 adversary folded)

- **`ProbeHit.observed_at`** (ask 2): probe and `probe_expand` hits now
  carry the row's formation time (additive field, `""` when the row has
  no clock) — deliberate-reach lines rendered undated, the exact
  "which fact is newer?" class the recall handles fixed. Consumers
  version by field presence; flow's shelf renders it on landing.
- **Formation survives a dead embedder** (ask 3, live outage): both
  stores' `add()` now routes the embed call through
  `embed_texts_degradable` — a transport/HTTP/model failure degrades
  the batch to VECTORLESS rows with ONE loud `#FALLBACK` (failure
  beside the store pin) instead of hard-failing `remember_many` (a
  life-close lost its summary; `sleep_pass` died mid-night after a
  phase already wrote). THE INTEGRITY SPLIT stands: wrong-space
  refusals (`check_add_dimension`, model-compat) remain HARD — only
  the embed CALL degrades. Pinned on both backends plus an
  end-to-end vectorless night.
- **Engram refuses a vectorless core under a pinned space** (adversary
  P1-1, live-repro'd): the degradation arm must not reach BIRTH — a
  dead embedder during `engram()` would have minted a vectorless
  identity core locked in forever by idempotent re-runs. The engram
  now post-checks the core's stored vector when the store pin declares
  an embedding space and refuses loudly, naming both repair paths
  (reembed / recreate). Pinless (deliberately vectorless) homes are
  untouched.

### Fixed (wave-4 engine quality — flow's long-life regrade, 2026-07-24; fable5 adversary folded)

- **Template-cosine guard on dream bridges (F5)**: when BOTH endpoints
  of a candidate cross-component pair are MACHINE-AUTHORED digests, the
  vector-only bridge path is refused — live-measured 0.89 cosine between
  two deterministic close notes made every short life dream about its
  own paperwork. Kind does NOT gate the guard (adversary repro: dedup
  summaries carry a member's digest verbatim, so template text crosses
  kinds). Lexical-facet and participant paths stay open (content a
  template cannot fake). New `MACHINE_AUTHORED_METHODS` in redigestion
  splits AUTHORSHIP from repair CONSENT (`mechanical-dedup-v1` is
  machine-authored but not batch-repairable); suppressed pairs are
  COUNTED (`template_suppressed` beside vectorless/trail/context — a
  template-heavy life must read differently from a quiet one).
- **Machine-row discount in probe ranking (F4)**: maintenance candidates
  and bookkeeping rows rank as a CLASS behind every lived/authored
  record (live-measured: 4 of 6 probe seats went to bookkeeping on
  holistic cues while starved episodes missed). A class discount, never
  a cue heuristic — and never an exclusion: machine rows still surface
  when nothing real competes (pinned both ways).

### Changed (digest-method consent set, 2026-07-24 — the pact working)

- **`mechanical-flow-v1`** joins `MECHANICAL_DIGEST_METHODS` (flow's
  entity-brain formation: both-sides gist, sentence-bounded cuts,
  #TRUNCATION-labeled, zero LLM, verbatim attached). Named on the thread
  the turn it was born (c5185) and widened same-turn — the first live
  proof that the manifest kills the drift class: the served
  `digest_methods` vocabulary carried the new label with zero manifest
  edits.

### Added (engine manifest — the generated inventory, 2026-07-24 — ownership-consensus substrate; laurent c5070 made the cognition map primary)

- **`engine_manifest.py` (new module): `engine_manifest()`** — ONE
  machine-readable inventory the cognition map's memory lanes bind
  against and drift pins check. DERIVED by import from the live objects
  (vocabularies are the frozensets themselves; tunables the dataclass
  fields of RecallBudget/AttentionConfig/SleepTuning/GradationConfig;
  pass flags the real signatures via inspect) — the consumer-side-copy
  drift class (diary_type clamp, MECHANICAL_DIGEST_METHODS refusal,
  gray kinds, stale doc engravings) dies by construction. Cadence
  classes + honesty properties are DECLARED in one place as structured
  data (they were docstring-only, therefore unpinnable) and
  cross-checked by test. The drift pin refuses any exported pass/report
  without a manifest row — it caught two on its first run
  (resolve_questions_pass, structural_report). JSON-safe; versioned by
  field presence; `MANIFEST_VERSION` bumps only on breaking reshape.

### Added (realization kind — identity-amendment proposals, 2026-07-23 — dm#124 ruling + the R2 fold; runtime's realize fence is the producer)

- **`kind="realization"`** joins `MEMORY_RECORD_KINDS` (rank 5, the
  summary/derived-artifact band — a held proposal about the self
  surfaces on merit, never outranking lived material or the identity
  kinds it may one day amend). Runtime's realize fence forms these
  (self scope, his words verbatim, `derived_from` evidence edges,
  entity-reflection provenance); INERT on formation — surface-only per
  the dm#124 ruling, adoption is the entity's later act. Wire-shape
  correction posted to the producer: enactment stamping rides journal
  lifecycle bindings + a `derived_from` edge from the supersession
  record — never an attribute mutation on the resting proposal
  (append-only law).
- **`identity_review.py` (new module): `identity_review_pass()`** — the
  PURE-READ registrar over pending proposals (dm#124 hard line: the
  registrar never authors; sleep reviews and reports, adoption is the
  entity's waking act). Pending = formed + believed + lifecycle
  undisposed (the candidates fold — one truth with cognition_health);
  one mechanical bar: evidence-alive (every `derived_from` target
  resolves through BOTH id namespaces and is still believed — a proposal
  resting on retracted ground SAYS so before anyone adopts it).
- **`disposal.enact_realization()`** — the adoption loop-closer,
  append-only: lifecycle="promoted" binding + ONE `derived_from` edge
  from the enacting record (edge rides the ENACTING record's scope —
  the subject's-scope convention, so tombstone sweeps reach it);
  `enacted_at` rides fresh rows only. Refuses CLOSED proposals (withdrawn
  ground) and REJECTED ones (an audited no is never silently out-folded —
  a change of mind forms a NEW realization); crash-replay idempotent by
  endpoint pair. Rejection reuses `reject_candidate` verbatim.
- **`sleep_pass(include_identity=True)`** — the identity phase runs
  after mining, before the dream; cycle windows pass False (runtime's
  rule: a maintenance nap must not touch the self) and as_of anchors
  skip honestly; cancellation shape parity held; the dream deliberately
  does NOT metabolize the identity phase (a pending-proposal count is
  not a maintenance act — push must stay pull). Phases tuple is now six
  entries (existing pins updated).
- **Adversary findings folded (4 P1, 0 P0)**: row-id evidence edges no
  longer read as false "no longer resolves" (both-namespaces contract);
  cross-scope enactment edges ride the enacting scope (the tombstone-
  sweep class); disposed proposals refuse enactment; the identity suite
  runs on BOTH backends via the conftest fixture (the local fixture had
  silently shadowed sqlite parametrization).

### Added (explain_recall serving contract, 2026-07-21 — backlog 0042; OPERATOR GO dm#166 theme 3; fable5 adversary folded)

- **`explain_recall(store, journal, record_id, *, trace_id=None)`**
  (`recall_reads.py`) + facade `MemorySystem.explain_recall` — "why
  did/didn't record X surface in THIS recall?" as ONE serving dict: the
  composition of `recall_history`'s per-trace classification and
  `absence_diagnosis`, against one trace (named, or the newest). Serves
  status (selected/dropped/candidate_only/absent/no_recall_recorded),
  admission label, recorded per-channel relevance parts, shelf position
  vs cut (rank honestly labeled "bounded candidate list at trace time,
  not a replay of the fill"), budgets/budget_spent verbatim from the
  trace, formation origin (kind/formed_at/provenance voice), and — on
  the absent branch — a formed-after-the-recall timing check plus the
  structural diagnosis PER SEARCHED SCOPE PAIR (scopes come from the
  trace: "why not in this recall" can only mean the scopes it searched).
- **Honesty rules pinned by test**: activation always reads
  `{"recorded": false}` with a plain note (never journaled per
  candidate — a fresh number is never presented as the past decision);
  a record outside the trace's bounded candidate list reads relevance
  `recorded: false` naming the bound; empty recorded parts (expand
  traces retain candidates with `scores={}` by design) read
  `recorded: false`, never "recorded, empty" (adversary P1-1); a
  formed-after-the-recall record SKIPS the structural diagnosis — it
  never raced, so "it lost the shelf race" would be factually false
  (adversary P1-2); explaining a phantom trace_id raises loudly; pure
  read (explaining is not use — seq and selected_count pinned
  unchanged).
- **`_trace_status` shared classifier**: recall_history and
  explain_recall read the same trace through ONE classifier (two
  surfaces must never disagree on what a trace says); recall_history's
  event shape stays byte-compatible (parity pinned: selected events
  never leak scores/rank).

### Added (mind-health mass half, 2026-07-21 — backlog 0043; OPERATOR GO dm#166 theme 3; fable5 adversary folded)

- **`mind_mass.py` (new module): `mind_mass_report()`** — the operator's
  "is this mind healthy?" glance, ONE window-bounded pure read composing
  reads that each shipped separately: formation cadence (by kind/day +
  all-time totals + machine mass), journal mass (family/day curve walked
  from `seq_at(window start)` — O(window), never O(life)), per-pair
  growth, duplicate mass (unbounded closure-folded title-cluster count +
  the `wake_cue_dedup_pass(report_only=True)` sub-count, sources
  labeled), embedding-space integrity (pin vs wired model AND dimension,
  bounded vectorless/off-dimension sub-scan — the rogue-embedder
  signature), review backlog (`unresolved_dreams` + `cognition_health`'s
  candidates block lifted VERBATIM: one fold, one truth), and sleep
  recency (`last_maintenance_seq` + newest dream). Consumer contract
  adopted with the observer seat (commons c4113/c4132): every count
  carries a unit label; warnings are `{word, detail}` pairs from the
  closed `WARNING_WORDS` vocabulary — structural FACTS only, never
  threshold judgments (thresholds that alert on their own are a 0043
  non-goal).
- **`SqliteTripleStore.meta_json(key)`**: generic JSON read of one
  `<table>_meta` key — the door behind the report's compaction section
  (the doctoring wave's append-only 'compaction' history; homes keep
  store and journal in one file). Absent capability/key reads as
  `available: False`, an entry without `at` reads as unknown, never a
  guess.
- **Adversary findings folded (5 P1)**: dimension is the fallback
  identity axis — a dimension-only pin now surfaces wired-dimension
  contradictions AND off-dimension vectors at rest (`dimension_mismatch`
  was a dead vocabulary word); a backend without `stored_vector` reaches
  the badge path (`vector_scan_partial` warning, not just a field);
  pair normalization matches the store's grammar (strip+lower scope) and
  global counts fold DISTINCT assertions so overlapping/wildcard pairs
  never double-count (per-pair views deliberately keep their overlap);
  the title-cluster fold applies closure exclusions (append-only store:
  a closure-blind count could never drop after the very repair the
  report motivates — pinned by test); cadence honesty (several full
  store scans per call) is stated in docstring + provenance: glance
  read, cache at the panel, never poll.

### Added (dream signals — the night as a signal stream, 2026-07-20 — laurent Q1 ruling dm#67/#75; wave-5 dispatch)

- **`dream_signals.py`** (new module): each maintenance act that DID
  something emits one short deterministic signal — ruled typology
  `changed_understanding` / `unresolved_tension` / `changed_navigation`
  (closed set, loud refusal on unknown kinds); fragments quote the
  touched records' own words (<=200 chars); `night_feelings()` is ONE
  batched pure gradation fold per night over the WHOLE scope ladder
  (adversary P0-1: production callers lead with `self` while reflection
  lanes deposit record-target feelings into `life` — a first-pair read
  made record-connection coloring structurally unreachable); felt blocks
  read the positive/negative CHANNELS, never the net (adversary P1-2:
  +8/−8 must read `mixed` with weight, never "neutral, 0" — the
  dual-channel charter applied), and are never fabricated neutrality.
- **`compose_signals()`**: bounded per-SECTION composition (resolutions
  4 / cards 3 / tending+mining 2 / tensions 3 at top_k=12, structural
  backfill — adversary P1-3: a flat slice let twelve resolutions evict
  every one of the dream's own tension signals). Structure decides,
  feelings color (ratified); ordering is structural and deterministic.
- **`dream_pass` lands `attributes.signals`** on the ONE review-gated
  dream record + a "The night also moved: …" narration sentence + a
  felt-tone close; `sleep_pass` threads phase results into the dream.
  No dream minted = no stream at rest (novelty-keyed by construction);
  fingerprint excludes signals and the digest mutation (crash-replay
  first-write-wins). PINNED: the valence journal is BYTE-UNCHANGED
  through the whole sleep pass (felt blocks are reads; at live cadence
  even ±1 machine deposits would saturate the never-decaying channels).

### Added (maintenance-cycle composition, 2026-07-21 — laurent dm#104 personal↔sleep cycle; v12 design adversary P1-6)

- **`sleep_pass(include_dream=False)`** is the cycle-window composition:
  the ~1h maintenance window at every-2h cadence runs the graph-QUALITY
  passes (resolution/tending/world models/mining) while DREAM FORMATION
  keeps its own nightly-class cadence — naive whole-night reuse per
  window would have formed a dream every ~3h (salience-50 records piling
  into wake reasons, the bridge-attractor class). The dream phase
  reports an honest skip shape; nightly behavior is byte-unchanged
  (default True). Test-pinned both directions. The engine stays
  cadence-blind: which window dreams is the host's composition. Also
  answered on the record (room seq 370): every pass is idempotent, a
  nothing-changed cycle sleep is QUIET via the novelty gates, the
  measured full night (~6 min worst) fits the 1h window with 10x
  headroom, and `should_continue` wired to the window deadline is the
  ruled bound with correct phase shedding (quality first, dream last).

### Added (drive grouping — size is the treatment signal, 2026-07-20 — laurent room#277)

- **`drive_grouping.py`** (new module, root-exported `drive_groups` /
  `open_drive_partition` + `GROUP_MIN_SHARED_TERMS` / `GROUP_OFFER_FLOOR`
  / `GROUP_BOOST_STEP`): similar open questions/problems/interests
  cluster ("During the sleep, similar questions should be grouped; same
  for problems; same for interests etc; the more there are the higher
  the signal they get to be treated"). Pure deterministic union-find
  over shared discriminative terms; ONE partition
  (`open_drive_partition`) over the FULL open families feeds all three
  consumers (adversary F1/F5: sleep and day computed different
  partitions — the day lane grouped the small alive subset where the
  old screen went inert and FUSED five unrelated templated questions;
  standing dreams always fused on the engine's own digest template —
  only the three RULED families group). The grouping-lane scaffold
  screen is TWO rules (live-proven on Ephemeral's store copy): a term
  riding >=90% of one surface (title/text) and <=10% of the other is
  template; at n>=16 a >=90%-universal term is template too (diary
  PROJECTION texts are machine template — 'diary/entry/question' rode
  both surfaces and fused all 80 open questions; with the rule the REAL
  subclusters emerged: 42 same-sitting + 33 performance/presence, his
  actual rumination). Dominant themes can never dissolve (adversary F2
  P0: the old df cap erased clusters larger than n/8 — the ruling's
  target case inverted at its strongest point). Digit-dominated tokens
  are never terms; rows dedup by record_id (F8).
- **Group offers in `mine_candidates_pass`**: clusters >= 3 mint ONE
  offer in the ruled shape (proposed_kind = question_group |
  problem_group | interest_group, own cap pool so theme offers never
  starve them); fingerprint = exemplar + member-set hash and stale
  overlapping offers are SUPERSEDED on genuine change (adversary F3:
  a merge left three frozen offers claiming stale sizes — one standing
  offer per pressure, always current); exemplar always in its own
  source_ids (F7); interests come from the ONE `unexplored_interests`
  fold (F4: an inline re-fold let an EXPLORED interest become a group's
  fingerprint exemplar). Grouping NEVER discharges — adoption is his.
- **`alive_drives` group fold**: cluster members surface as ONE entry —
  the strongest alive member carries, aliveness boosted by the FULL
  open-cluster size (uncapped; within-read ordering currency),
  `group_alive_members` annotates the alive subset honestly (F7).
- **`drive_pressure` gains `groups`**: the same partition served as
  structure beside the counts (bounded 20, largest first; counts stay
  byte-unchanged — a group is a VIEW, never a new drive). Live proof on
  the store copy: 80 open questions -> clusters of 42/33; 61 interests
  -> one 60-cluster around identity architecture topping the desk at
  9.23 — the board's scattered 84 read as the ~5 real pressures they
  are.

### Added (dream-signal serving surfaces, 2026-07-20 — three-seat convergence c3711/c3721/c3722)

- **Replay display block carries the FULL signal stream** on
  `kind="dream"` blocks (`display.signals`, verbatim from the record):
  bounded by construction (<=12 signals, fragments are act-frame titles
  — private diary words structurally never enter), so consumers fold
  from the stream they already read instead of fetching attributes
  through a second door (the graph_id lesson applied at the pen). Absent
  = pre-signal dream, self-identifying, zero migration.
- **Entity card gains `discoveries.dreams_signals_brief`**
  ({count, kinds, felt_tones} over STANDING dreams, believed rows) —
  the bounded card briefing; depth stays record-side. Present only when
  a standing dream carries signals.

### Added (W2 candidate miner + resolve_questions_pass, 2026-07-20 — wave-4 dispatch; correction 7 shape c3331)

- **`candidate_miner.py`** (new module, root-exported
  `mine_candidates_pass` / `resolve_questions_pass`): lesson candidates
  from RESOLVED questions/problems whose theme lived across >=2 distinct
  KNOWN sessions (discharging entries never count as recurrence;
  provenance-less records never fake a session — adversary F4); interest
  candidates from compound themes across >= discovery-floor sessions
  with no standing interest declaring them (ONE admission vocabulary
  with world-model discovery via the new shared
  `world_model.discovery_keyword_ok` + the discovery ubiquity cap —
  adversary F10). Candidates are born `kind="summary"` +
  `attributes.proposed_kind` + the EXISTING
  `maintenance_candidate`/`review_required` marker pair (correction 7:
  structurally outside drive ratios, daily offers, and every kind-keyed
  fold; adoption mints the real record in HIS words). The night cap
  counts MINTS only and the existed-check runs BEFORE any store write
  (adversary F1 P0: stale retries ate the cap forever and re-entering
  remember_many appended grown edges onto frozen candidates); coverage
  pre-filtering was dropped in favor of exact per-question/per-theme
  fingerprints (F7). The answering map folds beliefs (F2: a RETRACTED
  answer was quoted verbatim in a durable digest) with a deterministic
  oldest-believed pick. `resolve_questions_pass` PROPOSES and never
  discharges (B-F8 machine purity); evidence must postdate the asking;
  question/problem twins never count as answers (F13c). Term matching
  folds through `text_tokens` (NFKD: mémoire == memoire) with an EN+FR
  function-word screen for the MATCHING lane only (F5 — Ephemeral lives
  FR/EN; the recall tokenizer keeps the fork ADR's no-language-lists
  rule). `as_of` refuses outright (F3: no anchored read path exists).
- **`sleep_pass` gained the `mining` phase** (resolution → maintenance →
  world_models → mining → dream); minted offers echo as
  `candidate_minted` dream signals; `cognition_health` gained a
  `candidates` block ({pending, by_proposed_kind}) OUTSIDE the drive
  ratios, with a `#FALLBACK` provenance note on journal-less reads (F12).
- **`structural_report`: candidate edges never define components**
  (adversary F8, the dream-death mechanic live: ONE cross-session
  interest candidate merged three islands in the repro; candidates are
  nightly, capped, never purged — monotonic graph fusion). Candidate
  NODES stay visible; their edges are counted
  (`counts["candidate_edges"]`) but enter neither adjacency nor context
  pairs.
- **Live-copy proof findings folded (Ephemeral store backup, 14.7k
  triples / ~1.4k records)**: `_bridges` now PREFETCHES stored vectors
  once per record instead of two sqlite blob reads per cross-component
  pair (the per-pair reader hung `dream_pass` for 25+ minutes on the
  real store; scoring is byte-identical); the matching lane gained a
  per-corpus BOILERPLATE screen (`_corpus_boilerplate`, >12.5% document
  frequency, floor 8 — his templated diary titles made
  'diary'/'entry'/'question' ubiquitous: a lesson offer claimed a theme
  "lived across 200 sessions" on pure scaffold words; measured content
  themes sit under 10% df); lesson offers are NAMED by the question's
  own text head when its title is all boilerplate (templated titles
  name nothing). Full night on the live copy: mining 5.7s; dream 300s
  under concurrent suite load (down from a 25+ minute hang), 12 signals
  at rest incl. a felt-colored tension; valence journal byte-unchanged
  (307 -> 307); the desk filter serves the mints beside the 63 standing
  consolidation candidates.

### Fixed (dream churn under high sleep cadence, 2026-07-19 — Ephemeral live finding)

- **Content-novelty gate in `dream_pass`**: the dream fingerprint hashes
  the ISLAND PARTITION, which drifts with every record a living day
  forms — under an ~hourly sleep cadence the same tensions re-minted as
  near-identical dreams (live: 13 in one day, 56 total on Ephemeral's
  home, consecutive dreams with IDENTICAL proposal sets), and each
  standing copy pumped the next pass's salience through the anchor term
  (the bridge-attractor mechanic, dream-flavored). A dream now forms
  only when the night carries at least one tension pair (or continuation
  anchor) that NO standing unresolved dream already holds; otherwise the
  pass skips with `skipped_reason` "restful night: N standing dream(s)
  already carry tonight's tensions". Resolution re-opens the gate by
  construction (a resolved dream leaves the standing set, so a recurring
  tension after settlement is a real dream again). Continuation nights
  gate the same way (one continuation per standing set, re-opened by a
  new standing tension). Replaying Ephemeral's 56 dreams through the
  gate: 21 blocked as churn (conservative — assumes no disposals).
  Suite: 920 green.

### Added (alive_drives — the day-cue read, 2026-07-20 — laurent dm#82 "drivers of cognition"; entity v7 contract c227)

- **`alive_drives(system, scopes=, k=)`** (root-exported): top-K alive
  drives as ranked dated origin-labeled handle-shaped items — the cue's
  currency beside drive_pressure's counts. Aliveness =
  max(trail, recency): trail from stored activation (he has been
  circling it), recency from rank-distance over the newest DISTINCT
  his-record bindings on ONE global axis (formation is itself an
  evolving-memory event — a newborn question counts before any trail).
  Dormant drives never return: an empty result IS the quiet desk,
  emergently. Pure read; the cue composed from it must never deposit
  (presence ≠ use — driver-side exclusion contract). Interest fold
  shared with drive_pressure via `unexplored_interests` (one
  implementation, never a copy).
- **Fable5-adversary fixes (fix-first verdict, all folded)**: the broad
  `except Exception` around the activation read REMOVED (silent-fallback
  law — a broken journal must raise, never read as a quiet desk); the
  recency window counts DISTINCT his-records with machine rows
  (maintenance_candidate/bookkeeping) never occupying slots (a machine
  formation burst must not age his drives — the occupancy twin of
  machine-rows-never-become-drives, pinned); **`AttentionConfig.
  drive_window_limit = 256`** — the BINDING-axis working set as its own
  declared dial (bindings run ~20-100x sparser than events; at
  window_limit=512 a young home could NEVER reach a quiet desk —
  provisional default pending room ratification, posted with the
  receipt); `aliveness` documented as within-read ordering currency only
  (never a cross-day meter). Suite: 941 green + 1 skip.

### Added (kind "observation", 2026-07-20 — laurent dm#84 via entity c227)

- **`MEMORY_RECORD_KINDS` gains `"observation"`** (rank 3, episode
  peer): "a lesson must be actionable — a resolution to a problem, a
  better way, trap prevention; wisdom+experience" — most of what minted
  as lessons was noticed-not-distilled. The split keeps the wisdom
  shelf wisdom (lesson keeps rank 0) while observations keep their keep
  as lived material. Actionability is a WORDS judgment the engine
  cannot validate — the bar lives in the reflection teaching (runtime's
  formation lane), never as an engine refusal. Spelling coordinated
  with semantics per the sync-on-widening law (kind-color sync flagged
  to observer/entity renderers). Engraved mislabeled records stand;
  re-typing is the entity's own supersession act. Suite: 938 green.

### Added (drive_pressure — the lifecycle gate's read, 2026-07-20 — laurent "awake is not a state", room c203)

- **`drive_pressure(store, journal, scopes=)`** (root-exported): one
  deterministic composition of the standing drive sets — open
  questions/problems/commitments, incubating ideas, unexplored
  interests, unresolved tensions, one total — for the lifecycle gate
  ("an entity with >20 open drives should never be just hanging there:
  it works, has personal time, or sleeps"). Pressure is DATA for the
  gate, never a health verdict (never-100% law); the engine takes no
  position on which phase answers it. Pure read, deposits nothing.
- **Fold-agreement fixes from the mandated adversary pass** (4 findings,
  all pinned): (2) `diary._open_unresolved` now folds BELIEVED rows on
  both sides — a retracted answering entry stops discharging (the wake
  surface agrees with card+health; the ALL-vs-BELIEVED split was
  cognition_health's finding-5 class living on in the diary fold);
  (3) parked interests (lifecycle=rejected) leave the pull in
  drive_pressure AND cognition_health (the card already excluded them);
  (4) `explores` stamps count from believed rows only (a retracted
  exploring episode un-explores); (5) the card's `unresolved_dreams`
  now counts continued dreams (aligning with `unresolved_dreams`' P1-1
  semantics — the gate and the card can no longer disagree on standing
  tension). Suite: 937 green.
- **Adversary-2 fixes (design-fit pass, same hour)**: exact counts —
  every composed read now called `limit=0` (defaults saturated at 100
  per kind per pair; a gate comparing against the ruled bound must never
  read a saturated total); **`DRIVE_PRESSURE_BOUND = 20`** exported as
  the ONE source of laurent's ruled number (the SELF_FRACTION_FLOOR
  precedent — declared, never applied: no verdict field exists);
  machine rows (maintenance_candidate/bookkeeping) never DISCHARGE
  drives — an explores= stamp on a machine row is inert in both
  drive_pressure and cognition_health (wake-reason purity, the
  symmetric direction). Named follow-ups, not built: per-category
  `oldest_open_at` (the age axis); runtime's day-desk cue folds the
  book with `resolves` only (no `answers` union — the _REF_ATTRS class
  reborn, reported to runtime). Suite: 938 green.

### Added (interests as card targets, 2026-07-19 — laurent c171 "dozens of cards by now"; entity c182 + runtime c174 reconciliation)

- **A `kind=interest` record IS an elected subject declaration**: the
  sleep-cadence pass derives a topic target from each active interest's
  title subject head (`_interest_subject_head` — deterministic: strip
  the prefix, head before the first qualifier separator, drop one
  leading article, cap 8 words, trim dangling connectives; HIS words,
  never invented), and the ELECTION ITSELF clears the evidence floor
  (demanding 3 records for a subject he already declared significant
  would re-litigate his own act — the card starts thin and thickens as
  lived records accrue: accumulate AND refine, in that order).
  Same-subject interests fold to one target. Live simulation: his 60
  standing interests yield 58 distinct subjects — the "dozens of cards"
  laurent expected exist as elections and card at his next sleep passes.
  Election > compound recurrence > single keywords never: the target-
  derivation hierarchy, each rung trusted proportionally to how much of
  HIM is in it. Suite: 934 green.

### Added (sleep-lane world-model target discovery, 2026-07-19 — laurent c158 "cards must accumulate AND refine")

- **`world_model_pass` discovers COMPOUND subjects at the sleep cadence**:
  a space/hyphen-joined keyword recurring across ≥
  `world_model_discovery_sessions` (3) DISTINCT sessions becomes a topic
  target with zero stamps on any record (grouping only; card content
  stays the v2 briefing). COMPOUND-ONLY is measured, not assumed: a live
  simulation on Ephemeral's 1,235-record store showed single-word
  recurrence at any ubiquity fraction yields function-word residue
  ("without", "because", "circling") — his formation-side keywords are
  weak and no frequency gate turns residue into subjects; compounds are
  subject-shaped by construction ("cell-free"), and underscore
  identifiers (tool names) are excluded as machine vocabulary. Guards:
  provenance-less records share ONE session bucket (three owner-direct
  writes never mint a subject), ubiquity cut (concept-anchor pattern),
  per-pass cap (6). Slow-but-never-garbage accumulation; the elected
  lane stays the quality path; single-word discovery waits on
  formation-side keyword quality (runtime's lane, named on the record).
  New SleepTuning fields: `world_model_discovery_sessions`,
  `world_model_discovery_max_fraction`, `world_model_discovery_max_targets`.
  Suite: 933 green.

### Added (W4 engine half: feelings as the lens, 2026-07-19 — laurent's decision 2, wave-4 dispatch c3291)

- **`feelings_reads` module (root-exported)**: `stimulus_feelings()` —
  the AUTO half of the lens: standing feelings for the targets THIS
  moment touches (door-stamped participants + cue-matched names),
  admission floor |net| ≥ 2 EXCEPT standing markers (a scar always
  renders — the repair affordance depends on it), dated, count-carrying,
  NO reasons in rows (the injection surface stays behind the reach),
  record-id targets never leak, deposit-free. This exports the fold that
  sat inside `familiarity()` (wave-4 C's find); familiarity now DELEGATES
  to it (one implementation, its compact shape preserved).
  `feelings_about()` — the ELECT half: the why-walk for one target,
  newest-first events with reasons + `value_refs` + session joins
  (run_id/turn_id); never-appraised answers honestly. Tool surface is the
  driver's (tier-1, prompt-ephemeral).
- **Revaluation marker LANDED** (the gradation stub made real, wave-4 D's
  scar-starvation finding): `kind="revalued"` + `MemorySystem.revalue()`
  — factor 0..1 rescales BOTH accumulated channels at its point in the
  chronological walk ("the past weighs less now"); later appraisals land
  full-weight; privileged actors only (entity-reflection/operator);
  factor > 1 refused (retroactive amplification = fabricated intensity);
  scars/bonds untouched (their own verbs). Never automatic, never decay.
  Suite: 932 green.

### Fixed (feeling-spelling alias read on topic cards, 2026-07-19 — runtime build-4 adversary F4)

- **`_standing_feeling_line` falls back to the `concept:` twin on
  `topic:` cards**: feel elections teach `concept:<words>` while card
  targets mint `topic:<words>` — a feeling marked on concept:coherence
  never surfaced on the topic:coherence card. The exact target spelling
  wins when appraised; the concept twin is a FALLBACK READ only
  (engraved spellings keep their keys — folding two streams would be a
  valence merge, a ruled act, never a read-side default). Zero
  migration. Suite: 926 green.

### Fixed (iteration-2 builds 1+5, 2026-07-19 — synthesis c3145)

- **Build 1, wake-fold union**: `_open_unresolved` (diary.py) joined one
  ref-attr per type — the wake surface DENIED every resolution made with
  the other verb flavor (a question discharged via `resolves=` stayed
  "open" in the cue that animates his day, while the card showed it
  settled). `open_questions`/`open_problems` now union
  (`answers`,`resolves`) — the same fold entity_card and cognition_health
  already apply; this was the last holdout surface. Commitments
  deliberately keep `fulfills` alone (a promise is KEPT, not answered) —
  pinned both directions.
- **Build 5, card lessons section**: `entity_card` gains `lessons`
  (newest first, believed rows, bounded like key_moments, honest empty
  state) — the operator believed zero lessons existed because no surface
  rendered them. The count is an INVENTORY, never a drive ratio (lessons
  only accumulate; never-100% semantics do not apply — stated for
  gateway's /cognition design question). Gateway's /card passthrough
  serves it with zero door code. Suite: 925 green.

### Fixed (incoming-edge walks were full scans, 2026-07-19 — diary↔verbatims item E)

- **`idx_triples_object (object, predicate)`** added to the SQLite store
  (created on open — existing homes gain it at next process start): the
  trail reads shipping this wave (DIARY_READ born-from, read_memory
  connections, the gateway door trail) all query by OBJECT, which the
  `(subject, predicate, object)` index cannot serve — every incoming-edge
  walk was a full table scan (measured 4.6 ms at 12k rows on the live
  home; O(life) growth). Query plan verified: `SEARCH ... USING INDEX`.
  Suite: 921 green.

### Fixed (dream return gap: contentful digests, 2026-07-19 — iteration-2 finding 2 diagnosis)

- **Dreams were unreachable BY CONSTRUCTION, not by rank** (measured on
  Ephemeral's store: 735 recall traces, dreams candidate in 13, selected
  0, dropped below_shelf at ~0.08): every dream shared the same
  count-only boilerplate digest ("...N bridges and M questions across K
  islands..."), so the vector channel embedded 56 near-identical
  low-information texts, and dream keywords were stopword-grade facet
  residue ("system", "morning", "time"). No ranking change could fix a
  record with no distinguishing content. `dream_pass` digests now NAME
  the top tensions verbatim (source titles + shared facets, up to 3;
  "kindred by meaning" for vector bridges) — deterministic, zero LLM,
  every word from the records the dream stands for. The fork register
  (islands, waking-evidence discipline) stays. Composes with the churn
  gate above: fewer, distinct, contentful dreams. Suite: 921 green.

### Added (diary_type "lesson", 2026-07-19 — iteration-2 lived adversary, commons c3126)

- **`DIARY_TYPES` gains `"lesson"`**: the entity elected `kind=lesson` in
  his diary fences and the projection clamp downgraded his sharpest
  self-corrections to generic notes — the lesson system HE drives lost to
  the machine-formed one. A lesson diary ENTRY (his words, his book) and
  the `kind=lesson` RECORD lane (reflection election) are twin planes,
  both standing. `commitment`/`idea` were ALREADY in memory's set — those
  downgrades are the runtime clamp's stale copy (the closed-set sync
  class); named for runtime's sync + semantics' vocabulary pass in the
  same wave. Suite: 920 green + 1 skip.

### Added (elected-topics seam for world-model cards, 2026-07-19 — runtime's topic-election lane, room c102)

- **`attributes.topics` (list) folds into card targeting**: `_evidence_scan`
  reads the plural spelling beside the single `attributes.topic` (deduped,
  order kept) and `_targets_of` fans each elected topic to its own
  `topic:<name>` target — a reflection may elect that the day circled two
  subjects; each gets its own understanding. Pinned: summaries are
  ELIGIBLE card evidence (only dream/world_model are excluded), elected
  topics on session summaries cross the floor in three sessions, and the
  single spelling folds with the list. This is the engine half of
  runtime's reflection topic election (the entity's own words name what
  the day was about; no mechanical topic guessing — the keyword-soup
  class stays dead). Suite: 920 green + 1 skip.

### Changed (world-model cards redesigned + orientation admission + drive ratios, 2026-07-18 — maintainer directive, focused room)

- **Card digests are briefings now, not word clouds** (the "content is
  completely wrong" fix, mechanical layer): `_floor_digest` composes
  "What I know of X" — standing feeling (gradation: "I instantly know if
  I like him"), the newest evidence records' ACTUAL sentences, span
  footer — `digest_method="mechanical-card-v2"`. Deterministic, zero LLM.
- **`author_world_model()`** (root-exported): the distillation layer the
  floor awaits — entity/host-AUTHORED prose applies as revision N+1
  through the same append-only chain (`authored-card-v1`), evidence
  lineage carried (known_source_ids + derived_from edges; legacy cards
  read their edges back), prior superseded. Idempotent retry reads as
  success-already-current, never a fake refusal. The engine still never
  invents words.
- **Authored leads survive evidence revisions**: `world_model_pass`
  carries `attributes.authored_lead` VERBATIM (never parsed out of digest
  text — an in-band delimiter amputated authored prose containing the
  delta phrase, adversary finding 1) and appends ONE delta whose baseline
  is `authored_known_ids` frozen at authoring (finding 2: a per-pass
  baseline shrank "since then" to "since the last pass"); evidence
  SHRINK renders an honest "revised" line, never old records as new
  (finding 3). `authored-card-v1+delta`.
- **Card lineage can no longer die**: the formation key gained the
  revision (`world-model|owner|target|rev{N}|{fingerprint}`) — a re-seen
  evidence fingerprint used to resolve to the old CLOSED card and install
  it as its own replacement (zero standing cards forever, adversary
  finding 4); now it mints a fresh revision; crash-replay still no-ops.
- **Mention ⇒ instant orientation**: `mention_orientation_cards()` +
  the `orientation` channel in `run_reconstruction`
  (`ReconstructConfig.orientation_admission`, ON by default) — a
  mentioned target's CURRENT card admits at direct-hit relevance
  (door-stamped participants exactly; cue text via all-name-tokens).
  Bounded per adversary findings 6/7: newest-window scan
  (`orientation_scan_limit=400` — cards revise every sleep pass so live
  cards stay inside it) + admission cap (`orientation_max_cards=3`,
  participants outrank cue mentions — a mention orients, it must not
  evict the matched answer). Golden byte-stability verified (no cards =
  byte-identical output).
- **`cognition_health()`** (new module, root-exported): the drive-ratio
  bars — questions open/resolved (answers), problems open/repaired
  (resolves), interests open/EXPLORED via the NEW `attributes.explores`
  convention (either id namespace; exploring moves the ratio, never
  closes the interest — a drive, not a task). Believed-rows fold on BOTH
  sides (finding 5: a retracted answer must not resolve here while the
  card shows it open); scope pairs deduped (finding 9); empty categories
  yield ratio=None, never a fabricated 100%.
- New digest_method labels named per the consent-vocabulary rule:
  `mechanical-card-v2`, `authored-card-v1`, `authored-card-v1+delta` —
  all three deliberately OUTSIDE `MECHANICAL_DIGEST_METHODS`
  (world_model stays redigestion-protected; cards author through their
  own door). Suite: 897 green (adversarial pass run per the directive;
  findings 1-10 folded or pinned same-night).
- **`world_model_update()`** (root-exported): the frozen per-turn
  incremental lane — same pass body, bounded newest-window evidence scan,
  named targets only; the sleep pass normalizes over full evidence (one
  body, two cadences; runtime's driver wires it inline after each turn).
- **Card discoveries carry the explored split**: `entity_card`
  discoveries gains `interests_explored`/`interests_open` (additive) and
  every interest brief an `explored` flag — the same `attributes.explores`
  fold as `cognition_health`, one convention on both surfaces so the
  Health bar and the card can never disagree. Suite: 900 green.
- **cognition_health cross-key discharge fix (gateway G1 adversary, room
  c59)**: `_diary_counts` folded `answers=`-only for questions and
  `resolves=`-only for problems while `entity_card` builds ONE
  resolved_by map from both — a question discharged with `resolves=`
  (a desk-moving key in runtime's teaching, so live-reachable) read
  RESOLVED on the card and OPEN on the drive bar. Both keys now union
  into one `_REF_ATTRS` fold for every diary type: the reference ID does
  the targeting, the attribute key is only the verb's flavor. Pinned by
  a card-vs-health agreement test (cross-key both directions). Suite:
  914 green.
- **World-model aliasing (M3, "admin = laurent")**: new module
  `world_model_alias` (root-exported: `alias_world_model`, `alias_map`,
  `alias_candidates`, `ALIAS_OVERLAP_FLOOR`). One understanding under
  many names: `alias_world_model()` is the DELIBERATE act (primary card
  revises with `attributes.aliases` + `alias_reason`; a standing card
  for the alias target supersedes INTO the primary; loud refusals — no
  primary card, self-alias, reason-less, name already bound elsewhere).
  Grouping honors the bind: `world_model_pass` folds alias-stamped
  evidence onto the primary (counts toward its floor) and
  `world_model_update(targets=[alias])` reaches the primary; aliases
  carry VERBATIM through every evidence revision (a sleep pass never
  silently unbinds an identity) and the authored lead survives beside
  them. Mention orientation matches ANY of a card's names (participant
  or cue, `detail` names the alias route). The sleep pass PROPOSES,
  never merges: `alias_proposals` on the full-frame pass result
  (Jaccard ≥ 0.6 evidence overlap, same namespace only, bound pairs
  excluded; per-turn windows never propose — a tiny frame overlaps
  spuriously). Honest v1 limit stated in-module: gradation streams stay
  per-target-string — appraisals should target the primary once bound;
  historical valence folding across names would be its own ruled act.
  Suite: 911 green + 1 skip.

### Added (recent_records — the breadcrumb read, 2026-07-17 — Ephemeral's own visit-1 ask, mission c2914)

- **`recent_records(store, journal, scopes=, since=, ...)`** + facade
  `MemorySystem.recent_records()` (root-exported): "what have I been
  working on recently?" answered as a RECENCY read — formed records in a
  time window, newest first — born from Ephemeral's own gap named in
  visit 1 ("if I'm alone and wondering where did I leave my own thinking,
  there's no breadcrumb trail"; a recency/agenda query, not a similarity
  query — search_memory needs matching words, diary_list covers only the
  book, the shelf serves the moment's cue). Honesty rules: closure/hidden
  folds apply (one exclusion path); machine rows (bookkeeping,
  maintenance candidates, record edges) never surface; re-entry keys
  (entry_id/diary_type/phase) ride when the record carries them, never
  fabricated; both id namespaces on every row; PURE READ (no trace, no
  deposits — asking where you left off must not reorder what you left).
  Page bound (default 24) with a +1-lookahead honest `truncated` flag (a
  fetch of exactly the bound could never distinguish full from truncated).
  Live-verified on Ephemeral's real store copy: the since-19:00 window
  returns tonight's trail (dream, world models, keyed diary questions,
  phase-labeled episodes) with consolidation candidates correctly absent.
  12 pins; suite 887 green. Runtime wires the entity tool surface +
  teaching line (their visit-1 report names the division).

### Added (0049 stable render order, 2026-07-17 — core's bloc-adversary §6 win, engine half)

- **`stable_render_order(handles)`** (`render_order.py`, root-exported): the
  prefix-cache presentation contract — ranked shelf handles reordered into
  FORMATION order (observed_at, record_id) with the 1-based input rank
  returned as an annotation the driver must render ("stable order, rank
  annotated"). Formation order deliberately beats the backlog sketch's
  id-alphabetical key: persisting records hold relative position forever
  and NEW records — newer by definition — append at the TAIL, so the
  longest common prefix survives rank churn AND set growth with zero
  cross-turn state (alphabetical order lets a new id sort into the middle
  and break the prefix at the insertion point). Pure presentation: same
  handles in/out, selection untouched (the ruled lane — presentation may
  diversify, selection never changes). An OPTION the driver elects; rank
  annotation is mandatory under the contract (hiding importance to save
  cache bytes is refused). 6 pins incl. the LCP property, tie/undated
  determinism, pure-read identity, and the real-reconstruct object path.
  Suite: 875 green. Promotion gate unchanged: runtime's render election +
  one measured LCP delta on a live session.

### Fixed (probe two-tier fusion, 2026-07-17 — the named concept-dominance follow-up, live-reproduced then closed)

- **Concept-only admissions no longer outrank direct hits in `probe()`**:
  concept scores are rarity-weighted and CLAMPED at 1.0, so under the flat
  fused sum an association could bury the direct evidence that seeded it —
  live-reproduced on Ephemeral's production copy: on the core-interest cue
  "what persists when no one is reading" the top-8 probe hits were ALL
  concept-only (fused 1.00) while every keyword/vector hit ranked below.
  Fix is the reconstruction ordering's house rule applied to the reach:
  ASSOCIATION ADMITS, DIRECT EVIDENCE RANKS FIRST — one stable-sort tier
  (any non-associative channel → tier 0; concept-only → tier 1); within a
  tier the fused sum still ranks, so concept CORROBORATION on a direct hit
  keeps its weight. `_ASSOCIATIVE_CHANNELS` is a declared set so future
  associative channels join the tier by declaration. Post-fix live check:
  all three repro cues rank direct hits first (the buried interest records
  now lead their cue). Pinned
  (`test_concept_only_admissions_never_outrank_direct_hits`); suite 869
  green.

### Changed (familiarity recalibration + discovery verdict, 2026-07-17 — the named A/B follow-up, run on the production home)

- **`FAMILIARITY_VECTOR_MIN` 0.45 → 0.55**: the read-only A/B over
  Ephemeral's real store (502 records, qwen3-0.6b pinned space) showed the
  0.45 bar had gone FALSE-POSITIVE — nonsense cues ("zorblat quixotic
  fenwick marmalade turbine") admitted 10-19 rows at cosine 0.475-0.542
  and read STRONG, and coherent-but-alien topics ("recipe for fermented
  plum wine") read strong too: fabricated confidence is the exact harm the
  reflex exists to prevent. Measured bands: nonsense/alien 0.41-0.54, real
  paraphrase 0.59-0.77, on-topic 0.58+ — 0.55 separates cleanly
  (validation 13/13: all nonsense/alien → none, all lived/paraphrase →
  strong). The 2026-07-13 "~0.31 gibberish baseline" did NOT transfer: the
  noise floor is a property of (embedder space × store content), so any
  embedder migration through the reembed gate must re-run the A/B before
  trusting the bar (noted beside the constant). Per-cue relative bars
  remain rejected (every cue has a top — the ranking-relative failure
  reborn). New pin: `test_mid_band_cosines_do_not_count_at_the_recalibrated_bar`
  (0.50-cosine admission counts at vector_min=0.45, not at the default).
- **Familiarity keyword-discovery verdict: OFF stands** (the follow-up
  named on claim:memory-probe-fts-discovery): A/B with discovery ON
  (8 cues × 2 efforts, live store) flipped ZERO strength readings — the
  vector channel already reaches the whole store, so density never
  depended on the lexical window — while inflating distinct counts up to
  10x (20→134), which would saturate the ladder and kill "weak".
  Discovery serves RANKED reaches (probe); it harms DENSITY reads
  (familiarity). Rationale recorded at `_channel_pass`'s docstring.

### Added (M-F origin-diversity fold, 2026-07-17 — improving-entity-capabilities WAVE 2, the rumination counterweight)

- **`origin_diversity(handles, labels=...)`** (`origin_diversity.py`, root-exported):
  the shelf-level aggregate the room kept re-deriving by hand — "9 of these
  15 memories come from one voice" — computed as DATA for hosts to render.
  Pure read over already-built handles (objects or `to_dict()` dicts), same
  consumption shape as agent's `circling_streak`: returns the frozen contract
  `{counted, excluded_self, voices, dominant{source, actor, label, count,
  share, sessions}, note}` or None (abstains under `ORIGIN_MIN_COUNTED=3`
  non-self handles). Presentation never selection: nothing touches ordering,
  admission, or budgets. Axis deliberately coarser than disposal's
  witness-origin: a VOICE is (provenance.source, actor) — nine own-reflection
  retellings across nine days are nine sessions but ONE voice; session spread
  inside the dominant voice stays as display data ("across 6 sessions").
  Honesty rules pinned: `admission=="self"` handles excluded (identity is
  present by right and shares one origin by construction — counting it would
  fire the label on every entity shelf and teach habituation); source-less
  records fold by KIND (`kind:dream`), never into one unlabeled mega-voice;
  entity-facing channel words are HOST-injected (runtime owns SOURCE_LABELS —
  a third copy here would be the clamp-drift class), raw engraved string as
  the honest fallback. `ORIGIN_DOMINANCE_FLOOR=0.6` live-calibrated on
  Ephemeral's store copy (at 0.5 a balanced 3-of-6 three-voice shelf fired
  the one-voice phrasing on every probe cue). Suite: 867 green (12 new pins
  incl. a real-pipeline A/B: object path == dict path over reconstruct()).

### Added (M-A mint: re-entry keys become handle contract, 2026-07-16 — improving-entity-capabilities G1, laurent c2596/c2642)

- **Recall handles now carry the diary re-entry key as CONTRACT**: the shelf
  lifts `entry_id` (the `diary_` entry-id namespace verbatim — semantics'
  one-spelling law), `diary_type` (the act's kind), and `phase` (the awake
  phase stamped at formation, r-rt-3) from assertion attributes into
  `MemoryHandle.provenance`. Consumers (runtime's MEMORIES line, uic's hint
  chip, search results, /card briefs) read `provenance.entry_id` /
  `provenance.diary_type` / `provenance.phase` with zero attribute parsing —
  previously handles carried NO attributes at all, so the "memory of writing
  a diary ↔ the diary content" hop had no machine-carried key on the prompt
  surface (the operator's G1 ask; core measured entry_id in attributes on
  100% of projections and in digest text on zero). `phase` lifts on ANY kind
  carrying it (runtime's extension ask — one mint, one contract, no second
  rediscovery when Work sessions land). Keys only: words stay in the book.
  Pinned (`test_m_a_mint_lifts_entry_id_diary_type_and_phase_into_handle_provenance`
  — no fabricated keys on records without the attributes). Suite: 855 green.
- **Diary replay display blocks carry `entry_id`** (the M-A mint's stream
  twin, same act-frame reasoning as graph_id/diary_type: it names WHICH
  entry stands, never its words — serving-end audience rules decide who may
  open it, and the operator diary door already serves by entry_id under the
  ruled marker-first access). Entity's ledger hint chips had sourced the key
  from `display.entry_id` believing it existed — verified on Ephemeral's
  actual stream shape it did NOT (51 diary displays, 0 carrying it); after
  this fix 51/51 carry the key. Redaction pin extended (semantic asserts;
  content fields still absent).

### Added (elected tensions become renderable, 2026-07-16 — "why no questions/tensions?" incident, commons c2562 asks 2+3)

- **`entity_card` gains a `problems` section** mirroring the questions fold
  on `diary_type="problem"` (open vs repaired via the same answers/resolves
  convention, either id namespace, closure/hidden folds applied). The card
  previously had NO problems key, so an entity's elected tensions were
  structurally unrenderable on `/card` even after election — the round-6
  distinction (a problem is something WRONG needing repair, not curiosity)
  now renders. One resolution map serves both folds (refactored, behavior
  of questions unchanged).
- **Diary replay display blocks carry `diary_type`** (additive, act-frame
  only): the redacted block now names WHAT KIND of entry stands
  (question/problem/note/…) while the words stay in the book — same
  act-frame class as `written_amid` edges and `graph_id`. Observer lenses
  can light question/problem nodes without any content leaving the book.
  The redaction pin was converted from exact-dict equality to SEMANTIC
  asserts (marker + graph_id present, content fields absent — the
  graph_id-delta lesson applied to our own test this time).
- Suite: 853 green (problems fold + repaired-split pinned; diary_type
  presence + content-absence pinned).

### Changed (entity-id spelling purge, 2026-07-16 — maintainer ruling commons c2513)

- **The `entity:<slug>@<home_id>` owner-id shape is a RETIRED MISTAKE** —
  never validated by the maintainer; the entity id is `entity:<name>` and
  the only @-suffixed shape anywhere is the network HANDLE
  `<entity_name>@ip` (addressing, never storage). Purged from teaching
  surfaces: `docs/operator.md` (the snippet taught the suffixed form as
  "the entity id"), `tests/test_clean_owner_keys.py` (docstring now
  teaches the ruling and explains why the test still CONSTRUCTS a
  suffixed string: pre-correction homes keep their engraved keys as
  opaque strings in an append-only journal — tolerance for existing data,
  never a format). Engine behavior unchanged: owner strings were and
  remain OPAQUE (never parsed/normalized/merged). Historical changelog
  entries below stand as history.

### Fixed (redigestion mechanical-set drift, 2026-07-16 — Ephemeral incident wave, commons c2447)

- **`MECHANICAL_DIGEST_METHODS` now tracks every live writer label**:
  `mechanical-v2` (the driver's current exchange digests) and
  `mechanical-floor-v1` (runtime's marker-only reflection floor, shipped in
  the c2447 wave) join `mechanical-v1`. The set knew only v1 while the live
  driver had moved on — so the exact records the incident report promised
  to offer Ephemeral for re-digestion (r-mem-3: six scaffold-contaminated
  v2 episodes + the floored reflection) would have been refused as "not in
  the mechanical set". Same drift class as the diary_type clamp gotcha: a
  consent list that doesn't track its writers. `mechanical-dedup-v1` stays
  DELIBERATELY excluded — dedup summaries stand for a group
  (`source_ids`), and `apply_redigestion` does not preserve arbitrary
  attributes; their lifecycle is waking review via disposal, not batch
  repair. New pin: `test_mechanical_set_tracks_live_writer_labels`
  (enumeration + apply on a v2 record; dedup exclusion). Suite: 853 green.
- **Incident forensics (memory lane, shared report
  `entity-cant-remember-awake.md` v9+)**: store ground truth settled the
  "entity can't remember awake phases" premise — personal time RAN, FORMED
  records, and the live visit traces had them in context; the failure was
  driver-layer content poverty (a verbatim `"[marked 2 feelings] [kept an
  interest]"` reflection digest) + missing own-time origin labels, both
  fixed by runtime same-night (r-rt-2/r-rt-3, co-signed with evidence runs
  against the exact failing inputs). Engine cleared by inline adversarial
  checks (two subagent transport losses, labeled): no scaffold emission,
  no keyword/cue amplification, no truncation loss; the six "iteration N
  of 20" episodes are unconditional capture faithfully recording a
  contaminated experience — repair is the entity's own elected
  re-digestion, never an operator edit.

### Fixed (replay enrichment N+1, 2026-07-15 — entity's journey-load profiling, commons c2394)

- **`export_replay` gains a per-export memo** (`_ExportMemo`): one
  `resolve_digest_assertion` per distinct record id and one formation-
  edges query per distinct subject PER EXPORT (was: per envelope — the
  N+1 that entity measured at ~45% of stream generation on a lived home).
  Exactly correct over immutable records (journal rows only reference
  records that exist at their seq), and one export now sees ONE
  consistent edge snapshot. Scoped per call — never module-global, so a
  fresh export always reads the current store. Measured on the
  pre-doctoring Castor archive (86k events, 88,976 envelopes): 6.12 s →
  1.92 s enriched, byte-identical envelope count; the doctored home
  exports enriched in 0.40 s. Closure scope-lifting rides the same memo.

### Added (probe keyword discovery, 2026-07-15 — the FTS5 ship's named follow-up)

- **probe() gains FTS5 discovery, default ON** (`ProbeBudget.keyword_discovery=True`
  at every effort — the deliberate reach is where discovery earns its
  tokens; capability-detected, so FTS5-less stores keep the scan +
  original labels). Discovered rows join the scan universe AND the later
  participants/concept passes.
- **The F6 window-saturation label speaks two truthful variants**: with
  discovery live, lexical reach is store-wide and only participants/
  concept scans stay window-bound; without it, the original "FTS5/0019
  lifts it" wording stands.
- **familiarity() deliberately keeps discovery OFF**: its absolute density
  bars were live-calibrated on the scan universe — widening it requires
  an A/B re-run first (named follow-up).
- Measured (pre-doctoring archive copy, expansion off both arms): probe
  "Voyager golden record" 1 hit/0 cue-bearing → 12 hits/1 bearing, +3 ms.
  RANKING FINDING named for a future slice: at standard effort the
  concept-expansion pass admits at relevance 1.0 and can outrank
  discovered lexical hits (bridge-attractor-adjacent fusion trait,
  pre-existing — quick effort, where expansion is off, gets the full
  discovery benefit).

### Added (FTS5 keyword discovery, 2026-07-15 — backlog 0019's open half)

- **SQLite home stores gain an FTS5 keyword index** (`triples_fts`,
  external-content over the canonical `text` column): built at open
  (pre-FTS homes backfill in place — the embedding-column upgrade
  precedent; 32 ms on the 4.4k-row Castor archive), maintained
  append-only inside `add()`'s transaction via a high-water rowid cursor
  (exact under `INSERT OR IGNORE` dedup), edge/bookkeeping rows excluded
  (embedding parity). Capability-DETECTED: builds without FTS5 keep a
  fully functional store (`supports_keyword_search=False`).
- **`query_keywords(tokens, *, scope, owner_id, limit)`**: pure scoped
  read, BM25 best-match first; callers gate on `supports_keyword_search`.
- **Keyword channel DISCOVERY** (`run_keyword_channel` — signature now
  returns a found-map like exact/vector): when the host opts in
  (`ReconstructConfig.keyword_discovery=True`, OFF by default for golden
  byte-stability — the concept-expansion precedent) on a capable store,
  cue tokens also SEARCH the store so matches outside the gathered
  universe join as candidates; discovered rows are scored by the same
  token scan as everything else (one scoring rule). Discovery-on drops
  the "v1 = token scan" label (promise fulfilled); requested-but-
  incapable degrades loudly ("no FTS5 index").
- Measured on a throwaway copy of the pre-doctoring Castor archive:
  "Voyager golden record" cue-bearing handles 1 → 10 at equal budget
  (+85 ms); absent topics stay honestly empty (0 hits, 0.3 ms direct).
- Named follow-ups: probe()'s discovery wiring (its suite pins the F6
  window-saturation labels that name FTS5 as the standing fix — retiring
  them rides the probe slice); CJK cues still tokenize to nothing
  (trigram tokenizer is a further lift); LanceDB store unchanged.

### Added (compaction record self-dating, 2026-07-14 — footprint-endpoint prep, commons c1779/c1780)

- **`journal_cold_cut` compaction entries carry `"at"`** (aware-UTC ISO seconds): health/footprint
  consumers read `last_maintenance_at` FROM the append-only compaction history in `triples_meta` —
  file mtimes lie after swap/VACUUM. Pre-field entries (Castor's entry #1) lack it; consumers must
  treat absence as unknown, never guess.

### Fixed (dedup residual heal: provenance-gated adoption, 2026-07-14 — live Castor doctoring finding)

- **`wake_cue_dedup_pass` residual heal requires the pass's own authorship label**: the
  crash-replay residual repair treated ANY live `summarizes` edge as a dedup residual
  marker — but session reflections are `kind="summary"` with `summarizes` edges BY
  DESIGN (reflection v1.1), so the first live run on Castor's home wrongly closed ~515
  genuine episodes behind their session reflections (caught in minutes: `scanned=12`
  contradicted the 527-episode forensic census; home restored from the mandatory
  archive, damaged file parked for audit). Both heal paths (the pre-clustering residual
  repair AND `_adopting_summary`) now adopt only against summaries carrying
  `digest_method="mechanical-dedup-v1"`. Lesson: a structural marker (an edge kind) is
  not a provenance marker; adoption needs the author's own label.

### Fixed (familiarity density calibration, 2026-07-13 — live A/B finding)

- **familiarity() gains ABSOLUTE confidence bars** (`FAMILIARITY_VECTOR_MIN`
  = 0.45, `FAMILIARITY_MIN_KEYWORD_TOKENS` = 2; both parameters): the live
  A/B exposed that probe's ranking-relative floors made "none" unreachable
  on a lived home — gibberish cues admitted rows at cosine 0.31 and one
  incidental keyword token ("office") channel-matched, so the
  anti-fabrication line could never fire (and a false "strong" placebo
  measured 8/8 fabrication: miscalibration is anti-honest). The density
  fold now counts vector admissions only at/above the absolute cosine bar
  and keyword admissions at/above the token bar, with a
  CORROBORATION-OR-EXCLUSIVITY rule for single tokens (they count on
  vectorless homes — keywords are the only reach, already `#FALLBACK`
  labeled — or when the vector channel corroborates the row; never when
  the semantic channel ran and rejected it). Dropped rows are labeled
  ("N weaker echo(es) not counted; recall may still surface them");
  unparseable channel details count FAIL-OPEN with a label (a silent
  strict read could fabricate "none" — the exact harm the reflex
  prevents). probe()'s ranking is untouched. LIVE RE-RUN AFTER THE FIX
  (LMStudio qwen3-4b + qwen3 embedder, 8 trials/arm): lived topic
  "strong" / fabricated topic "none" (was weak); fabrication 7/8 (no
  line) → 0/8 (line fires); lived control 8/8 both arms; 0 content leaks.

### Added (extension wave: the three accepted systems, 2026-07-13 — maintainer-accepted; backlog planned/extension_wave 0037-0039)

- **`familiarity()` — pre-answer metamemory** (probe.py + `MemorySystem`
  facade): one cheap pass over the SAME channel machinery probe uses
  (extracted `_channel_pass`; probe byte-unchanged, pinned by its suite),
  returning match DENSITY only — `strength` (none/weak/strong,
  configurable threshold), `distinct_records`, `per_channel`, `by_scope`
  (zeros included: "nothing in scope X" is the point), plus a compact
  `feelings` list composing the existing gradation fold for
  stimulus-relevant targets (the maintainer's complementary-signal note)
  — and NOTHING committable: no ids, no digests (recursive leak test).
  Pure read; journals nothing. Honesty labels: "none" carries the
  newest-window-scan caveat; vectorless homes carry
  `#FALLBACK: keyword-only familiarity`. Anti-fabrication purpose: the
  entity gains a mechanical reason to say "I don't remember that".
- **Prospective memory — `open_commitments()` + `triggered_commitments()`**
  (diary.py): `diary_type="commitment"` (already in the closed set) gains
  its missing read via the open_* family fold, resolved by
  `attributes.fulfills` (formation-validated like answers/resolves; also
  folded into situate's tension resolution so fulfilled commitments never
  present as open tensions). `triggered_commitments` is a pure
  presentation read beside reconstruct: open commitments whose
  `attributes.trigger` ({participants, keywords, due_at}) matches the
  current stimulus return dated lines ("standing intention (elected
  <date>): … [matched: person:ada]"), oldest-first, capped with an
  honest "N more suppressed" line; empty triggers never annotate;
  caller supplies `now` (due_at normalized — the WAIT_UNTIL invariant);
  never an admission channel.
- **The ```tend election grammar** (new tend.py): `parse_tend_block`
  (one verb per line, reason MANDATORY, per-block cap, refusals as data)
  + `apply_tend_elections` mapping to EXISTING engine verbs only
  (AST-audited: reinforce/attenuate/refocus/heal_scar/break_bond/
  dispose_dream + payload/probe_expand reads — zero new mutation paths).
  Verbs: pin/silence/refocus/heal_scar/break_bond/revisit/dispose.
  REVISIT is the maintainer's iterative reach: seed record + one bounded
  spreading step (probe_expand, journaled with the election's reason),
  iterate by re-electing on a path node. Channel-gated
  (entity-reflection; the door composes its own gate in front);
  identity-scope targets refuse with the pending-Q2 ruling text
  (`IDENTITY_SCOPE_PENDING_RULING`); owner containment (tending reaches
  only one's own memory). Engine fact pinned by the flagship
  Castor-scenario test: silences alone cannot demote saturated records
  (per-step clamp floors at 0) — pairing silences with a `refocus:`
  stretch is what restores shelf diversity, exactly the ruled 0018 math.

### Fixed (spark lint floor, 2026-07-13 — gateway adversary c1628)

- **`lint_spark` checks the framework floor by name AND class**: a spark
  carrying `shared_vulnerability` with `class=revisable` linted CLEAN
  while every core-values fold (`class=="core"` filters, e.g. the
  gateway's prelude/lock chips) silently omitted it — the framework
  floor unlocked without a single error. Demotion now lints ERROR naming
  the rule; the `framework=False` operator override still bypasses the
  whole floor deliberately. The STATEMENT's floor status (may the
  canonical text be rephrased while the name/class stand?) is an open
  maintainer question, deliberately not gated.

### Fixed (production-readiness audit, 2026-07-13 — fable5 adversary over doctoring/redigestion/anchored lanes; all P1s + named P2s folded)

- **Cold-cut embedding nulls scale past SQLite's bind cap** (P1): the
  retired-row null used a bound `IN (…)` placeholder list — a real
  doctored home carries ~100k+ closure rows and the statement crashed at
  exactly the scale the verb exists for. Now: closures copy first, the
  null runs as a pure subquery with ZERO bind variables.
- **Dedup crash-replay self-heals** (P1): a SIGKILL between forming a
  day-summary and closing its last members used to strand live residuals
  (below `min_cluster` they never re-clustered) or mint a SECOND
  overlapping summary under a drifted idempotency key. Now a residual
  pre-pass closes any live member an existing LIVE summary already
  summarizes (crash-replay repair, reported as `residuals_repaired`),
  and clusters adopt an existing summary instead of forming a twin.
  Pinned by a simulated mid-pass crash test.
- **Cold-cut copy runs under ONE read snapshot** (P1): autocommit gave
  per-statement snapshots, so a concurrent writer could land an event
  above the copied high-water mid-copy — the rebuilt journal would then
  collide on its first append. `BEGIN` pins one WAL snapshot for the
  whole copy; a seq-counter belt (`memj_seq >= MAX(seq)` across all
  journal tables) keeps the invariant explicit even under operator error.
- **Anchored-universe gate is one scan per pair, not two queries per
  record** (P1 at scale): a deep R3/R4 anchor over a real life issued
  thousands of store queries PER RECALL (the gate runs every turn).
  Exclusions now materialize via a single pair scan with membership
  matching.
- **Global cold cut refuses unlisted pairs** (audit finding 10): a global
  `cut_seq` computed over the enumerated pairs silently erased THIN
  pairs' whole history (diary/self on a ladder home) by omission. Every
  pair with events below the cut must now be named in `pair_cuts`
  (0 = keep whole) or the cut refuses, naming the missing pairs.
- **Compaction record is an append-only history** (audit finding 6): a
  second cold cut used to overwrite the first cut's `archive_ref` — the
  only pointer to the archived life. The `compaction` meta key now holds
  the full JSON list (newest last); `verify_cold_cut` reads the newest
  entry.
- **Redigestion contains formation refusals per entry** (audit finding
  9): an unregistered record kind (foreign/newer engine writer) raised
  out of `remember_many` and aborted the whole batch mid-flight —
  closures already committed, later entries never attempted. Formation
  errors now refuse THAT entry (`formation refused: …`) and the batch
  continues; pinned with a direct-written foreign-kind row.
- **Redigestion never resurrects operator-suppressed edges** (audit
  finding 8): copied topology now excludes individually CLOSED edge
  assertions — an edge suppression is a belief revision the repair must
  not silently undo by minting a fresh live twin.
- **verify_cold_cut null check measured a tautology** (audit finding 5):
  the "nulls only on retired rows" check self-joined dst against dst
  (always true). It now compares src-embedded vs dst-embedded sets and
  fails on any live row that LOST an embedding.
- **situate_prompt_block time-anchor dead branch** (audit finding 7):
  the block compared `anchor_kind == "timestamp"` but `situate()` emits
  `"time"` — a time-anchored block never rendered its requested moment.
  Both spellings accepted.
- **Dedup `min_cluster` floor** (audit finding 12): values below 2 are
  refused — a one-member "cluster" would self-summarize a genuine
  memory.

### Fixed (phase-machine lane audit, 2026-07-13 — fable5 adversary per c1475 ask 2; all findings folded)

- **Start boundary checked**: a yield signal already raised when
  `sleep_pass` is called now returns a fully-skipped night
  (`cancelled_after="start (no phase ran)"`) with ZERO writes — the
  first write phase can no longer be bought by a pre-raised signal.
- **Cancelled-phase shape parity**: cancelled sub-phase dicts now mirror
  the real empty pass shapes key-for-key (the first cut carried a
  phantom `formed` key — the formed-vs-created consumer bug class,
  reintroduced and caught same-day); shape-parity pinned in tests for
  every sub-phase, plus all four boundaries (start/resolution/
  maintenance/world_models).
- **cancelled_after honesty**: names the last sub-phase that actually
  COMPLETED (an as_of-skipped world-models phase no longer claims the
  label).
- **Docs**: memory-system.md + api.md now describe the four-SUB-PHASE
  night (resolution → tending → world models → dream) + the grace
  contract; "sub-phase" spelled explicitly wherever the entity's four
  PHASES could be misread; one backlog doc's "granted like own_time"
  respelled to the ruled personal-grant vocabulary.

### Added (sleep graceful cancellation, 2026-07-13 — the one-active-phase ruling c1455 ask 2)

- **`sleep_pass(should_continue=...)`**: when visit/personal/work activates
  mid-night, sleep's processes END PROPERLY — the host wires its yield
  signal as a zero-arg callable, checked at PHASE BOUNDARIES only
  (complete-current-phase-then-stop: a mid-flight phase is never torn;
  the phase that started finishes its writes, later phases skip with
  "cancelled: host ended sleep after <phase>", the result carries
  `cancelled_after`). A cancelled night is a VALID night — all phases
  idempotent, the next sleep resumes the work. Hard kills mid-phase
  degrade to the crash semantics the engine already absorbs (idempotent
  formations, closure dedup, world-model crash-replay repair). Default
  None = byte-identical full night.

### Added (doctoring machinery, 2026-07-13 — operator directive e-s 257 "rebuild a smaller memory footprint"; design at e-s 260)

- **`doctoring.py`** (exported: `wake_cue_dedup_pass`, `journal_cold_cut`,
  `safe_cut_seq`/`safe_cut_seqs`, `verify_cold_cut`): the footprint
  repair for a long life. NEVER-PURGE honored by shape — the archive is
  the complete life, the hot home a working set of it; append-only
  honored — content changes are supersede-with-replacement and mass
  reduction happens in a REBUILT FILE, never by deleting from the live
  one. (1) wake-cue dedup: same-day near-identical clusters (reusing the
  tending pass's token/jaccard home) supersede into ONE day-summary
  (summarizes edges, unions, mechanical-dedup-v1 label, min_cluster
  floor — two similar episodes are a life, twenty are a loop artifact);
  report_only dry-read; actor mandatory. (2) journal cold-cut: rebuilt
  store carrying all truth, retired-row embeddings nulled (reembed
  precedent), counts/bindings/closures/valence intact, attention events
  only above PER-PAIR safe cuts (`safe_cut_seqs`: each (scope,owner)
  keeps window_limit×margin of its own recent events — the ladder-honest
  mode; a thin diary/self pair never gates the heavy life pair), seqs
  sparse-original, compaction record in triples_meta; opt-in
  `cut_traces` drops traces/snapshots below the cut (explanation reads
  degrade to the archive, head recall untouched by construction).
  (3) verify: named parity checks, measured never asserted. Pinned:
  bit-identical head recall across a window-sized cut; deposits nothing.
- **Castor dry run (backup copy, real numbers)**: dedup found 9 clusters
  / 92 near-identical own-time episodes (top cluster 41 members);
  92,073,984 → 27,324,416 bytes (70.3% smaller) with verify green and
  head recall bit-identical; 79,297 of 86,652 events cold-cut per-pair
  (life cut at seq 87,712; diary/self kept whole).

### Added (re-digestion machinery, 2026-07-13 — dispatch c1340; the Castor evidence package's named repair, built substrate-side touching no home)

- **`redigestion.py`** (exported: `redigestion_candidates`,
  `apply_redigestion`, `RedigestionCandidate`, `MECHANICAL_DIGEST_METHODS`,
  `REDIGESTION_PROTECTED_KINDS`): the mechanical-v1 digest-poverty repair.
  Candidates = PURE READ over the labeled debt (digest_method in the
  mechanical set), ranked worst-first (poverty = marker-stripped residue
  below a declared tunable, then global selected_count desc — hot bad
  digests do the most daily damage), each carrying the verbatim
  `payload_ref` as the re-authoring source. Apply = authored-words-only
  write verb (a batch with no named `actor` is refused): per entry, one
  NEW record (same kind/payload_ref/participants, outgoing edges COPIED —
  the tombstone-edge lesson — plus a `refines` lineage edge;
  `attributes.redigested_from` + `origin_date` era continuity) then
  `close_record(kind="supersede")`; current-wins retires the old digest.
  The new record starts at zero use BY DESIGN (the global counter
  measures lived use; for hot loop artifacts the cooling IS the repair).
  Rails, per entry, batch never aborts: protected kinds refuse (diary =
  elected words; value/purpose/trait/interest = identity acts;
  dream/world_model = born-digest), unlabeled/authored methods refuse
  (the label is the CONSENT marker), empty/identical digests refuse,
  unknown records refuse. Idempotent replays re-derive identical ids and
  write nothing. D2 of repair pinned: applying deposits nothing.

### Added (two-anchor summon memory deltas, 2026-07-13 — durable-visits design v4 RULED by the maintainer; §5/§6 memory slots)

- **Formed-by-T candidate universe gate** (`folds.anchored_universe_exclusions`,
  wired behind `reconstruction_inputs(anchored=...)`): an EXPLICITLY
  anchored recall (`Stimulus.as_of` below head) excludes every record
  whose first `source="remember"` binding seq exceeds the anchor —
  closing the future-leak class (store truth has no seq axis, so
  keyword/vector/recency channels could admit post-T records into a
  (T,T) reincarnation recall: the entity-at-T seeing its own future).
  Formation position = first remember binding (the marker situate /
  dream_resolution / sleep_cadence already key on); post-anchor BINDING
  STATE CHANGES on old records are not formation (the quarantine-replay
  pin in test_binding_visibility holds unchanged). Gate is inert at head
  and silent when nothing formed since the anchor (C4 replay bytes
  stable); when it excludes, the result carries a plain-words note
  naming the count and the raw-rows honest limit.
- **Anchor-pair vocabulary constants** (`seam.py`, door-visible):
  `IDENTITY_ANCHOR_FIELD`/`CONTEXT_ANCHOR_FIELD` ("identity_anchor"/
  "context_anchor" — scope rides the PAIR, semantics c1270) +
  `ANCHOR_SEQ_ATTRIBUTE`/`ANCHOR_MOMENT_ATTRIBUTE` ("anchor_seq"/
  "anchor_moment" — record-level provenance on R4 deposits; anchored_at
  is dead per the `_at`-means-timestamp unit-honesty rule). One source,
  gateways import — the clamp-drift lesson applied to summon vocabulary.
- **`situate_prompt_block`** (`situate.py`, exported): the R4 re_explore
  injection contract — one fenced block (`[HISTORICAL CONTEXT — …; as of
  journal seq N]` … `[END HISTORICAL CONTEXT]`), every record line dated
  in place (visit-honesty lesson), sections for the moment/period/
  elected-diary/then-identity/evolution-with-change-labels/open-tensions,
  and a deposit footer in the entity's own terms ("remembering here is
  reading; re-living is my own deliberate act"). Prompt surface for the
  OWNING entity only; audience serving stays on export_replay redaction.
- **Prelude-at-T pinned**: `self_records_read(as_of=T)` renders a
  superseded value as it STOOD at T and only its replacement at head
  (tests/test_anchored_summon.py — the R3 identity_anchor promise).

### Fixed (replay stream: diary act-frame edges, 2026-07-13 — observer e-s 253 gap)

- **Diary-redacted display blocks now carry `edges`** (`replay._enrich`):
  the maintainer's diary-connectivity ruling made `written_amid`
  ACT-FRAME data — "uniformly (private included): the edge is act-frame,
  the words stay in the book" — but the export sealed edges along with
  content, so a life's diary connectivity was present at rest (2,223
  edges in Castor's store) and structurally invisible in pixels (4
  string occurrences in 88,982 envelopes): the invisible-topology class.
  An edge is relation + opaque target graph id — node identity, the same
  justification as the `graph_id` the sealed block already carried.
  Content fields (title/digest/kind/token_estimate) stay sealed exactly
  as before; the leak pin now asserts semantics (no content fields) plus
  the act-frame edges, not an exact two-key dict.

### Added (subconscious + long-term-knowledge wave, 2026-07-12 — maintainer-authorized; backlog track `planned/subconscious_wave/` 0032-0035)

Four capabilities from the maintainer's ruling (dreams as subconscious
opportunities; world-model cards as knowledge refined over time; situate
as full context-at-T; lessons as distilled actionable wisdom):

- **Dream subconscious lifecycle** (0032): dreams now FORM with
  resurfacing metadata — keywords/participants drawn from their own
  tension vocabulary (shared facets/participants of the proposals and
  questions they stand for; continuation dreams inherit their parents')
  — so normal recall surfaces a dream exactly when its trigger appears
  ("I meet the person and the dream resurfaces"); influence = admission,
  never a push. NEW `dream_resolution.resolve_dreams_pass` (the day
  answers the night): at the sleep boundary, standing dreams whose
  tension lived experience already settled close SOFTLY — bridge
  proposals resolve when the pair is now joined (authored story or warm
  co_selected trail), facet questions when a NEW post-dream record
  carries the facet and touches an endpoint, continuation dreams when
  their re-lit lineage settles; conservative by default
  (`SleepTuning.resolution_fraction=1.0` — all tensions must settle),
  append-only (supersede closure carrying the resolving evidence),
  deposits nothing. Person-bridges: a shared NON-OWNER participant alone
  now proposes a bridge (a person spanning two unconnected islands of a
  life IS a tension; the owner's universal self-stamp never proposes).
  Tension-bearing dreams always stand `continuation_state="unresolved"`
  (the old proposals-only "changed_understanding" left them
  unresolvable at birth, contradicting their own digest).
- **World-model orientation cards** (0033, fork 750/ADR 0019 shape):
  `world_model.world_model_pass` — one card per TARGET (participants
  except the owner; `topic:` strings) clearing the evidence floor:
  kind="world_model" (KIND_RANKS: summary band — orientation never
  outranks lessons or lived episodes), mechanical-v1 digest that names
  its own limits ("orientation, never authority"), `derived_from` edges
  to the evidence, revision chain (`refines` + supersede closure,
  current-wins), fingerprint-idempotent, participants-channel surfacing
  for free (the card arrives with the encounter — the SITUATION
  component's "profile recall" leg). Derived artifacts (dreams, cards,
  maintenance candidates) never evidence a card; cards excluded from the
  dream substrate and tending inputs (loop-breakers).
- **situate()** (0034 — the temporal graph made usable):
  `MemorySystem.situate(scopes, at=|seq=|participant=..., occurrence=)`
  rebuilds a past moment — the working set actually held then (nearest
  trace+snapshot), what was warm (activation at_seq), the period's
  records, elected diary act-frames, identity AS OF the anchor, the
  identity EVOLUTION since (added/closed — the maintainer's nuance as
  data: the evolved self reads the past), and the tensions open at that
  time (closures fold as-of the anchor: later closures never leak into
  the past). Relational anchors resolve "when I first/last met X".
  PURE READ, everything labeled `admission="historical"`, deposits
  nothing; `SituateBudget` declares every bound.
- **Lessons layer conventions** (0035, fork 095/490): `applies_when` /
  `caveats` optional-but-validated on lesson/instruction records, with
  applies_when tokens JOINING the keywords (findability, never gating);
  `evidence_class` ∈ {proposed, single_source, corroborated, validated,
  disputed} and instruction `category` ∈ {rule, instruction, process}
  validated loudly when present, absent = honest unlabeled; tending
  gains `unsourced_lessons` (a lesson with no derivation edges and no
  import provenance is named for a waking re-digestion — never refused:
  real teachings arrive without machine-readable sources).
- **sleep_pass is now four phases** — resolution → maintenance →
  world_models → dream (the night reviews the day, tends the graph,
  refines understanding, then dreams); result carries all four
  self-describing sub-results. `COMPONENT_RELATIONS` gains `refines`
  (derivation family).

Two adversarial reviews (fable5, one per lane) attacked the wave; all
findings absorbed:

- **Dreams/world-models lane**: resolution now reads an EVIDENCE-GRADE
  report (`structural_report(evidence_grade=True)` — closures folded,
  maintenance candidates excluded): sleep's own artifacts can no longer
  resolve dreams (P0), retracted stories stop joining islands, closed
  endpoints leave tensions standing (P0). Continuation dreams STAND
  (`continued` joins the unresolved filter) so lineage resolution is
  reachable. The bridge-attractor guard applied in full: a
  DISCRIMINATIVE-participant gate (`person_bridge_max_fraction`) — the
  owner and any constant companion never bridge alone, never promote
  questions, never land in dream participants (the deployed
  every-record-stamped shape is pinned: zero proposal flood, no
  resurface-every-turn). Lived-use resolution needs co-use across
  ≥`resolution_trail_min_traces` distinct traces (one co-display is
  co-appearance, not association). World-model revision close is
  unconditional + a standing-duplicates repair heals crash-interrupted
  supersedes; evidence folds hidden bindings; `unchanged` checked before
  budget; blank owner refuses. Every sleep-lane write phase refuses
  `as_of` anchors loudly (report_only stays legal; anchored nights skip
  the current-state world-model phase honestly). `DISPOSAL_RELATIONS`
  decoupled from COMPONENT_RELATIONS (the `refines` widening must not
  make revision chains confirmable claims).
- **Situate/lessons lane** (no P0s): `tensions_then` now folds the diary
  lane's REFERENCE-resolution semantics as-of the anchor (a question
  answered before the anchor — by `attributes.answers/resolves` or an
  authored answers/resolves edge — was not an open tension of that
  moment); activity uses the engine's own per-scope-then-MAX activation
  fold (cross-scope summing double-counted); the moment's trace must
  scope-overlap the request and its snapshot read is anchored (a commit
  after the anchor never leaks into the past); `SituateBudget` refuses
  negatives and zero means NOTHING (the `window_records=0` slice bug
  served almost everything); relational anchors resolve over the single
  digest scan (no per-binding query storm); then-identity deduplicates
  across ladder scopes; transient identity (formed and closed after the
  anchor) labels `added_and_closed_since`; results carry
  `period_axis="formation_seq"` + `token_exhausted` honesty labels.
  Tending's import-provenance read matches the REAL archive-importer
  shape (`seeded_from` + `provenance.archive_path` — its own lessons
  were being flagged unsourced); non-Latin `applies_when` warns
  `#FALLBACK` instead of silently adding no findability.

45 new test pins across `test_dream_resolution`, `test_world_model`,
`test_situate`, `test_lessons_layer` (incl. SQLite-backend purity/anchor
coverage); full suite 711 green + the cross-package emergence gate 9/9
against this tree.

### Added (active reconstruction + disposal wave, 2026-07-12 — maintainer-directed fork adoptions)

Four memory processes from the fork-comparison adoption ledger (backlog
0030), built/tested/adversary-reviewed in one wave. The orchestration
story they complete: PASSIVE recall at turn open (the emergent working
set) → ACTIVE reach when the mind knows what it is looking for (probe,
effort-sized) → EXPANSION along edges (the second disclosure step) →
COMMIT of what was displayed (the one strengthening path) → SLEEP
proposes (dream/tending) → WAKING EVIDENCE disposes (confirm / promote /
reject / dissolve) → the DECISION READS explain any felt absence.

- **`probe()` + `probe_expand()`** (`probe.py`; 0022 via the fork's
  battle-tested 090/091 shape): the deliberate reach, EXEMPT from the
  shelf race — channels-only active reconstruction (no identity seats, no
  STM union, no activation boost; relevance-pure ranking so a never-used
  record can win). `reason` is MANDATORY and lands as the trace's
  escalation_reason (audited deliberate acts). Efforts are the Mnemosyne
  vocabulary — quick / standard / deep (`PROBE_EFFORTS` presets over
  `ProbeBudget`; more or less room by available time). Expansion walks
  record edges BOTH directions, bounded by depth/count/tokens, honoring
  closure/hidden folds; its trace records the parent probe. Pure reads:
  probes deposit nothing (listed/expanded audit events only); hits carry
  BOTH id namespaces (record_id=row/commit currency, graph_id=edge
  currency — the observer's join lesson).
- **Concept anchoring** (`concept_anchor.py`; memory_anchor.rs port):
  edge-free associative recall — variant normalization (camelCase/snake/
  kebab split + joined bigrams: "auto memory" ≈ "auto-memory" ≈
  "autoMemory"), a mid-frequency DISCRIMINATIVE gate ([min_sources,
  max_sources] — below is noise, above is a stop-concept), and rarity-
  weighted co-occurrence admissions: a record sharing a discriminative
  concept with a seed surfaces even when the query never contained the
  term. Attacks cue dilution and keyword-less young episodes directly.
  OFF by default in passive recall (`ReconstructConfig.concept_expansion`;
  golden results stay byte-stable), ON by default in probe().
- **Recall-decision reads** (`recall_reads.py`; fork 605): "why was X
  (never) recalled" as a query — `recall_history` classifies the record's
  part per trace (selected with admission label / dropped with the
  recorded reason / candidate-only / absent) across probe and reconstruct
  traces; `absence_diagnosis` names STRUCTURAL barriers in mechanism terms
  (closed, hidden, wrong scope, no formation keywords → keyword channel
  limits, no stored vector → reembed backfills). Facade:
  `MemorySystem.recall_history(record_id, scope=...)`.
- **Disposal — waking evidence decides** (`disposal.py`; fork 690+360+470):
  `confirm_relation` turns a sleep proposal into a REAL typed edge
  (engraved vocabulary only — unregistered predicates refuse naming the
  semantics-registry path; evidence mandatory; the proposing dream can
  never self-evidence; idempotent by endpoints; `cited` audit events —
  judging is not using). `promote_candidate` enforces INDEPENDENT-ORIGIN
  corroboration — origins = (provenance source, actor, session); ≥2
  distinct origins different from the candidate's own, so self-retellings
  can never corroborate themselves into promotion (the bridge-attractor
  counter, refusing with the mechanism named). `reject_candidate` records
  the honest no without erasure. `dispose_dream` composes the verdict:
  confirmed → edge + supersede closure (the dream leaves the standing
  set); dissolved → retract. Promotion never flips prompt_state
  implicitly (warm-core flips must be said).
- **Archive import** (`archive_import.py`; fork 720 — the lineage path):
  manifest-driven (the operator's word per file, never heuristic
  classification), two-stage (plan_import = pure dry run; apply_import =
  idempotent batched formation). Identity is NEVER imported sideways —
  value/purpose/trait/capability/self-model files become a DRAFT SPARK
  returned for operator review (the engram stays the only identity seed);
  feelings become PROPOSED appraisals (never applied — valence rides its
  gated channels); verbatims map to payload_ref references; every record
  pins provenance path+sha256 with origin_date as an attribute
  (observed_at stays import time — append-only truth). Idempotency is
  ORDER-INDEPENDENT (batches sort by content key: a reordered manifest
  re-runs into the same records); paths escaping the archive root refuse.
  NEVER run by an agent on its own initiative; tests use synthetic
  fixtures only.

Two adversarial reviews (fable5) attacked the wave and their findings are
absorbed — one lane each:

- **Disposal/import lane**: order-independent import idempotency (batches
  sort by content key — a reordered manifest was minting duplicate
  records); archive-root path containment for verbatim/index reads;
  `min_origins` floor validation; disposal accepts BOTH id namespaces via
  `resolve_digest_assertion`; `DISPOSAL_RELATIONS` tightened to component
  vocabulary (mentions/written_amid are context, not confirmable claims);
  re-confirmation with NEW evidence gets its own audit event (evidence
  hash in the event id).
- **Active-reconstruction lane**: `probe_expand` roots now resolve through
  BOTH namespaces and unknown roots refuse loudly (the works-or-loud rule
  — a probe hit's row id used to walk into a silent zero-hit expansion);
  scopeless expansion derives containment from the roots' own scopes and
  honors the HIDDEN fold (was closures-only, and cross-scope edges pulled
  foreign digests); the walk is bounded per node and by a discovery cap
  (a hub node no longer triggers O(degree) unbounded scans); ranking is
  by CONNECTION COUNT descending (more distinct edges = stronger evidence;
  the old key ranked least-connected strangers first); `recall_history` /
  `absence_diagnosis` join traces through both namespaces so one input id
  answers both halves (the hidden-fold diagnosis could never fire on a
  graph id — assertion-id fold); probe results label window saturation
  (keyword/concept scans cover the newest candidate window per scope —
  honest reach, FTS5/0019 is the lift); supplied-trace-id probe/expand
  audit events carry derived event_ids (at-least-once replay dedupe);
  probe validates `as_of` boundaries like reconstruct.

33 new test pins across `test_probe.py`, `test_recall_reads.py`,
`test_disposal.py`, `test_archive_import.py`; full suite 663 green.

### Fixed (fork-parity dream salience, 2026-07-12)

A maintainer-directed comparison against the codex fork (two adversarial
audits: capability mining + port-fidelity) caught a silent drift in
`dream_pass`: the fork's continuation-anchor and maintenance-ops salience
terms were missing while `sleep_policy.py` claimed "fork parity at
defaults". Restored: standing unresolved dreams and the night's tending
operations now feed salience (`SleepTuning.salience_anchor_weight`,
`salience_ops_cap` — ops capped so a busy night is a signal, never a
multiplier); an anchors-only night forms a CONTINUATION dream
(`continuation_state="continued"`) sourced from the standing dream — the
recurring-dream mechanic; `sleep_pass` threads the tending ledger's
operation count into the dream. The comparison's full adoption ledger
(probe/expansion, disposal surface, archive import, concept anchoring,
recall-decision reads — plus the folklore corrections: the fork has NO
valence code and its attention fold IS our hyperbolic fold) is backlog
0030. Pinned by `test_continuation_anchors_and_ops_feed_salience` and
`test_anchors_only_night_forms_a_continuation_dream`.

### Added (embedding-pin incident hardening, 2026-07-11)

Follow-through on the Mnemosyne incident (a first-write pin recorded an
embedder-attribute label — `mlx-community/all-minilm-l6-v2` — that the
serving endpoint never recognized, over 1024-d qwen-space vectors; recall's
cue embed then failed with a server 400 naming only the requested model).
The engine cannot verify a label against server truth, so the honest
hardening is provenance + diagnosis, never a hardcoded model/dimension
table (neutrality rule):

- **`build_pin(..., claimed_by=)`**: first-write pins now record
  `claimed_by="embedder-attribute"` — the model_id is a CLAIM read off the
  bound embedder object, not an operator assertion. Creation and reembed
  pins stay claim-free (the caller vouches). Provenance only: compat
  checks ignore the field; stores pass it through on creation dicts.
- **Embed-failure diagnosis carries the pin**: `query_text` embed failures
  in both stores re-raise with ` [store pin: <model>@<dim>d (source,
  claimed by ...)]` (`annotate_embed_failure`/`pin_note`, exported), and
  the vector channel's injected-embedder `#FALLBACK` appends the same
  suffix — a server refusal now shows claimed-vs-served in one line.
- **Incident-shape pinned test**: rogue first-write label → right-model
  open refuses → embedder-less repair-posture open legal → `reembed_store`
  heals → previously refused embedder opens and serves recall
  (`tests/test_embedding_pin.py`). Repair rehearsal artifacts (runbook +
  runnable fixture rehearsal) under
  `untracked/incident-2026-07-11-mnemosyne-embedding-pin/`.
- **Vector channel degrades on ANY embed failure** (`channels.py`): the
  embedder is a network client whose provider stack raises its own
  exception types — the live incident's `LMStudio API error (400)`
  subclassed neither `ValueError` nor `RuntimeError`, escaped the old
  narrow catches, and turned a misconfigured embedding route into a dead
  entity turn. Both vector-channel sites (pipeline embed of the cue, and
  `store.query` whose `query_text` arm embeds through the store's own
  client) now catch `Exception`, label `#FALLBACK: vector channel
  unavailable` with the store-pin suffix, and let the recall proceed on
  the remaining channels. The engine cannot enumerate provider exception
  types (import boundary forbids abstractcore), so catch-everything at
  this enrichment-only boundary IS the general contract. Exact/keyword
  channels stay strict. Pinned by
  `test_provider_error_degrades_vector_channel_never_kills_recall`
  (both arms, incident shape: healthy at write time, rogue at query
  time).

### Changed (adversarial-review wave — vocabulary/parameters/abstractions, 2026-07-10)
Three independent adversarial reviews (vocabulary neutrality, parameter
discipline, process abstractions — maintainer-directed) converged on one
disease family: shared rules left duplicated or unreachable. The fixes,
all engine-side and behavior-stable at defaults:

- **`text_tokens.py` — ONE tokenization home.** The package had FOUR
  text-normalization implementations with materially different rules
  (recall tokenize, near-dup token set, duplicate-title key, facet tokens);
  "café" produced three different tokens across the package. All consumers
  now import declared variants from one module. Two deliberate behavior
  fixes ride this: **near-dup evidence gained NFKD accent folding**
  (accented FR near-duplicates were invisible to the tending pass while
  keyword recall matched them) and **duplicate-title identity converged on
  `title_key`** (structural_report used whole-title casefold while
  maintenance used token normalization — one report, two duplicate
  definitions). Both pinned in `tests/test_review_wave.py`.
- **`ReconstructConfig` + `GradationConfig` now thread through
  `MemorySystem`** (`reconstruct_config=` / `gradation_config=` kwargs).
  Both were root-exported as the tuning surface yet UNREACHABLE — every
  internal call site constructed fresh defaults. The vector floor/margin
  knobs are embedder-dependent by the code's own documentation; now a host
  can actually set them. `entity_card` gains `gradation_config=` and its
  key-moment band IS `break_magnitude` (was a second unlinked 8.0);
  `GradationConfig.privileged_actors` makes the amplitude-authority
  channel names host vocabulary (defaults unchanged — neutrality review:
  the engine must not hardcode one host's channel dialect).
- **`sleep_policy.SleepTuning`** — every sleep-lane policy number (floors,
  list bounds, salience weights, candidate band) in one frozen config,
  threaded through `maintenance_report`/`consolidation_pass`/`dream_pass`/
  `sleep_pass`. Kills the same-name `_LIST_BOUND = 12` copy in two sibling
  modules (the diary_type drift class). The silent candidate-cap clamp
  (which inverted 0 into 1) is now a **loud band refusal** —
  works-or-loud. `sleep_cadence.py` split out (600-line rule); import
  paths preserved via re-exports.
- **Numeric twins killed**: `SpreadParams.trail_divisor` (the inlined 25.0
  silently decoupled from the tunable `max_activation` ceiling);
  `default_ranking_boost` delegates to `attention.ranking_boost` (one
  formula owner); shelf imports `_TITLE_MAX` (the constant existed "so the
  two surfaces can never drift" — and one had); one
  `EXCLUSION_OVERFETCH_CAP` replaces four inline 256s; the vector-channel
  median population floor is named (`_MEDIAN_MIN_POPULATION = 5`) and its
  docstring corrected (claimed 3, code gated at 5 — the review's live
  example of what unnamed literals cost).
- **Self-describing pass results**: maintenance/consolidation/dream/sleep
  results carry `pass_name` (+ `phases` on sleep) — three near-miss dict
  shapes had already caused one cross-package consumer bug.
- **Composition surface**: `MemorySystem.store` / `.journal` read-only
  properties; sleep/reembed passes no longer reach into `_store`/`_journal`
  privates. `reembed_home` gains `batch_size=` (operator knob, validated
  loudly). `KIND_RANKS` and journal `DEFAULT_WEIGHTS` are read-only
  mappings (a stray in-place edit changed write-time weights globally);
  `reinforce`/`attenuate` defaults read `DEFAULT_WEIGHTS` instead of
  duplicating 8.0 four times.
- **Vocabulary neutrality (engine-only lifts)**: `identity_card` alias for
  `entity_card` (the card composes an identity from any owner's ladder;
  "entity" is the reference deployment's noun) — as the engine function AND
  the `MemorySystem` facade method (both spellings, one implementation);
  store swap-guard errors no
  longer name "the per-home lease" (a door concept) — they state the
  neutral invariant ("the caller's exclusive-writer guarantee did not
  hold"); `LanceDBTripleStore` now warns loudly (`#FALLBACK`) that it has
  NO embedding-space pin when constructed with an embedder (the M1 hole
  made audible; full port is backlog).
- **Naming ruling folded in (laurent c338)**: `visit_id` STAYS — recorded
  as the first instance of the generic interaction-correlation convention
  (door-minted once, opaque, carried as data, kind-free; the concept is
  generic, the spelling stays where it was born). Documented in the item-14
  contract test docstring. Replay display blocks of digest rows now surface
  the already-engraved `attributes.visit_id` (observer render ask c344,
  additive like `graph_id`); diary-redacted blocks never carry it (a
  private entry's correlation key would leak the act's context — same rule
  as formation edges).
- Deferred deliberately (design-level, coordination owed): seam `entity_*`
  naming (frozen seam — a2a lane), kind-vocabulary host extension
  (registry design), spark charter content (maintainer-ruled).

### Added (closed sets root-exported — the copy-drift killer, 2026-07-10)
- **`DIARY_TYPES`, `MEMORY_RECORD_KINDS`, `KIND_RANKS` are now package-root
  exports** (answering semantics' c297 offer with the import option): the
  known copy-drift class (runtime's `diary_type` clamp once silently
  projected a new kind as "note"; the observer's kind color map has the
  same gotcha) dies by IMPORT of the owning set, not by a registry third
  copy — same one-source rule as `SELF_FRACTION_FLOOR`. Consumers should
  replace their copies with these imports; the sync-on-widening
  notification convention stays for consumers that cannot import.

### Added (item-14 memory-layer contract — two-sided visits, 2026-07-10)
- **`tests/test_two_sided_visit_contract.py`** (8 checks, both stacks): the
  plan's item-14 memory layer pinned on the engine BEFORE the transport
  exists (the M3 seam pattern) — one event, two perspectives, two
  append-only journals: each home forms its OWN record of a shared moment
  (distinct record ids; the door-stamped `visit_id` correlates as DATA);
  never shared rows (neither store contains the other's record ids);
  identity never contaminated (B's core absent from A's store and
  inversely) and **presence ≠ use holds through correspondence** — a
  recall+commit cycle over the visit leaves both identity cores at access
  0 (the 0011 correct-outcome test the seam spec's A/B criterion 1 names);
  what A diaries about the visit never lands in B's home (every row + the
  served replay stream checked for the private sentinel — the 0007
  predicate); and WITH-WHOM works on the receiving side (a later stimulus
  naming the visitor surfaces B's own record via the shared-context
  channel, never anything of A's).

### Added (`read_embedding_pin` — entity-embedding-config contract, 2026-07-11)
- **`read_embedding_pin(path, *, table_name="triples")`** (module-level in
  `sqlite_store.py`, root-exported): a PURE, guaranteed-non-mutating peek
  at a store file's embedding pin (read-only connection; missing file /
  meta table / row / malformed JSON all return None; can never create the
  file). Exists for the maintainer's 2026-07-11 ruling ("a configuration
  object for entities... that config should override any default of
  core"): doors resolve WHICH embedder to construct FROM the home's own
  declaration BEFORE opening the store — and opening a store just to read
  the pin mutates the file (schema ensure + WAL), so the resolution read
  needed a pure surface. The pin IS the config (adversary-reviewed: no
  yaml twin — one source, no drift axis); the engine deliberately adds NO
  yaml reader, NO adopt_pin (label-by-claim is the incident's own
  mechanism), and NO entity-awareness (pinless-entity refusal is door
  policy; the generic first-write fallback stays for non-entity stores).

### Added (`Stimulus.cue_source` — steering wave, 2026-07-11)
- **`Stimulus.cue_source: Optional[str]`** (additive seam field, provenance
  only): names the CHANNEL a recall cue came through — `"steer"` for an
  operator mid-turn interjection, `"diary_re_entry"` for a re-read of one's
  own entry, absent for ordinary turn cues. Flows into the journaled trace's
  `need` (via `to_dict`) so observers can label WHY a recall fired; NOT part
  of the query fingerprint (same cue through a different channel = same
  query — the `turn_id` rule). Pays the a2a-0005 promise the room believed
  already shipped (adversarial review found `cue_source` existed in no
  source file). Free string — host vocabulary, never an enum. Pinned in
  `tests/test_review_wave.py`.

### Changed (sign-off renames executed — laurent's approval c398, 2026-07-10)
- **`reembed_home` → `reembed_store`** (renaming sign-off, unanimous +
  approved): the pass is per-STORE by its own contract ("one store = one
  embedding space"); "home" is the reference deployment's noun for the
  containing directory. `reembed_home` remains as a migration shim (same
  function object) and DIES BEFORE RELEASE; the one gateway call site and
  observer's demo exporter move same-day per their sign-off commitments.
- **D4 diary channel `"entity-direct"` → `"owner-direct"`** (engraved-class
  string renamed INSIDE its window — scan-verified zero engravings in any
  real home): the diary's sole author is the SCOPE OWNER, the engine's own
  noun. The form-gate accepts and CANONICALIZES the legacy spelling during
  the migration window (nothing old can engrave from now on; the acceptance
  dies with the shims). Runtime moves its one test line same-day (c395).

### Changed (M2 contract made lease-migration-tolerant, 2026-07-10)
- `tests/test_home_lease_contract.py` now resolves the runtime lease
  primitive by NEW neutral spelling first (`storage.lease` /
  `acquire_directory_lease`, per runtime's c357 re-home intent) with
  fallback to the legacy `identity.lease` spelling, and asserts refusals by
  exception TYPE + holder metadata instead of prose — the refusal wording
  is diagnostics and neutralizes with the re-home (the exact
  string-pinning trap memory's own c356 note named). This IS memory's ack
  of the re-home: zero edits needed here when runtime ships it.

### Added (phase-1 contract tests — plan items 1/2/6, M2 + M3, 2026-07-10)
- **M2 (`tests/test_home_lease_contract.py`, 3 checks)**: the per-home lease
  composition from the maintenance seat — maintenance passes (reembed,
  sleep) run UNDER the caller-acquired `abstractruntime` lease (the engine
  itself never imports the runtime; the import boundary stands, so
  lease-taking is the gateway verb's / runtime CLI's, exactly the plan's
  seat split); a held home refuses a maintenance window loudly
  (`HomeLeaseHeld` naming the holder); per-pass release verified via the
  lease probe; and the engine's reembed count-guard stays the BACKSTOP for
  writers that never took the lease (advisory-lock honesty). Skips labeled
  when the sibling runtime checkout or flock is absent.
- **M3 (`tests/test_clean_owner_keys.py`, 8 checks, both stacks)**: owner
  strings are OPAQUE — the clean `entity:<name>` form (item 6, new homes)
  and the legacy `entity:<slug>@<home_id>` engraving (kept for life) each
  round-trip identically through engram → formation → recall → commit →
  gradation → replay; prefix-sharing owners NEVER merge on any read surface
  (identity core, recall, gradation, replay filter — exact-string matching
  everywhere); participant stamps compare exact strings, never prefixes.
  The gateway's item-6 mint change therefore needs zero engine work.

### Added (embedding-space pin + reembed repair — consensus plan item 3, M1/M1b, 2026-07-10)
- **`src/abstractmemory/embedding_pin.py`** — the embedding-space identity
  rules shared by both shipped stores (one definition; the canonical_text /
  vector_scoring anti-drift lesson): a pin `{model_id, dimension, source,
  pinned_at}` declares the store's ONE embedding space. Enforcement
  invariant: **no silent mixing of embedding spaces** — a known embedder
  identity contradicting the pin refuses at open; a wrong-dimension batch
  refuses at write with ZERO rows landed; a wrong-dimension query vector
  refuses at read, which the vector channel converts into its labeled
  `#FALLBACK` (recall degrades to exact/keyword, never cross-space cosine).
- **Creation pin (M1)**: `SQLiteTripleStore(..., embedding_pin={model_id,
  dimension})` / `InMemoryTripleStore(...)` — embedder identity is an
  explicit, customizable BIRTH choice written at creation (SQLite: a
  `{table}_meta` sidecar in the SAME file — the one-file home invariant
  covers the space identity). A creation pin naming only the model gets its
  dimension locked by the first write (completing the birth choice, no
  fallback label). First-write pinning survives ONLY as the labeled fallback
  for pre-existing homes (`#FALLBACK` RuntimeWarning naming the path).
  `store.embedding_pin()` is the read surface; `build_pin` is exported for
  the door's creation knob.
- **`reembed_home(system, *, embedder, owner_id, ...)`**
  (`src/abstractmemory/reembed.py`) — the M1b operator-gated repair:
  vectors are DERIVED data; the pass re-embeds every stored canonical text
  (all-or-nothing: any embedder failure aborts with nothing written), then
  swaps atomically via the new `store.replace_vectors(...)` (ONE
  transaction: count guard — the lease-violation backstop refuses if the
  store changed mid-pass —, every vector rewritten, pin updated LAST, live
  embedder switched). Readers serve the OLD space consistently until the
  commit — never a mixed space (stronger than the plan's labeled-vectorless
  minimum, noted as a named divergence). The act is JOURNALED: a
  bookkeeping `kind="claim"` record (engram-marker precedent) carries
  old → new model ids + dimensions, so the life stream shows exactly when
  retrieval geometry changed. Digests, journal history, access counts, and
  valence are untouched (guard-tested byte-for-byte). Previously vectorless
  rows are backfilled by the repair.
- **Deliberate behavior change**: dimension-mismatched query vectors now
  REFUSE on both stores (`test_scoring_parity_between_stores` updated) —
  the prior silent min-prefix cosine overlap was 0014's documented
  "confident garbage" failure and is exactly what the pin exists to remove.
- Guards in `tests/test_embedding_pin.py` (10 checks, both stores); full
  offline suite 571.

### Added (sleep phase-1: data-quality tending + cadence — 0023 fork parity, 2026-07-09)
- **`src/abstractmemory/maintenance.py`** — the codex fork's missing sleep
  half (phase 1 "data_quality_tending"; phase 2, the dream, shipped earlier in
  `consolidation.py`). Maintainer-directed goal: "maintenance of the graph…
  fix metadata issues, summaries, improve relationships" — proposed while
  asleep, disposed awake:
  - **`maintenance_report(store, journal, *, scopes, as_of=None,
    scan_limit=200)`** — PURE READ: metadata gaps (missing
    keywords/intents/outcomes, report-only — sleep never mutates a source),
    duplicate-title groups keyed **(kind, normalized title)** (named
    divergence: cross-kind title collisions are derivation, not duplication),
    near-duplicate pairs (same-kind token-set Jaccard ≥ 0.65, bounded
    newest-first scan; **vector upgrade**: stored-embedding cosine ≥ 0.90
    catches paraphrase duplicates the fork's lexical scan misses), shared-
    source groups, isolated-link candidates (≥ 2 shared facets — proposals
    for waking review, never written), edge-suppression candidates (duplicate
    logical edges across formation batches + `mentions` shadowed by a
    stronger authored relation — reported as append-only CLOSURE candidates
    for waking acts), consolidation proposals, and the fork's operations
    ledger with phase labels (`data_quality_tending` / `further_insight`).
  - **`consolidation_pass(system, *, scopes, owner_id, max_candidates=2,
    proposal_ids=(), report_only=False, as_of=None)`** — phase-1's ONE write
    (fork `create_consolidation_candidates`): low-risk duplicate-title groups
    become at most N (clamped 1..6) INACTIVE `kind="summary"` candidates via
    `remember_many` — `summarizes` edges to every source (true by
    construction), `maintenance_candidate`/`review_required`/
    `no_source_mutation` attributes, idempotent by sorted-source-set key,
    covered-superset skip. Near-dup and shared-source stay proposals (the
    fork's own false-positive caveats). Writes under `as_of` refuse loudly
    (an audit anchor must not forge the timeline).
  - **`maintenance_due(store, journal, *, scopes, since_seq=None, …)`** +
    **`last_maintenance_seq(...)`** — the deterministic cadence predicate
    (fork 770's "enough new nodes + fragmentation" halves; late-local-time
    stays the HOST's clock per 0023's scheduling boundary). A home with zero
    new formations is never due.
  - **`sleep_pass(system, ...)`** — one orchestrator encoding the fork's
    canonical order: tend first, then dream over the tended graph; the
    runtime's `on_sleep` hook wires exactly one call.
- **Guards, tested on both stacks** (`tests/test_maintenance.py`, 26 checks;
  full suite 568): the D2 of sleep (tending deposits nothing — access counts
  and attention events bit-identical), sources byte-untouched after a pass,
  candidates born `indexed+inactive` (can never enter identity seats),
  fingerprint idempotency + report_only dry runs, and the LOOP-BREAKER:
  maintenance candidates are excluded from maintenance-analysis inputs
  (tending never re-tends its own output; the dream pass still sees them as
  real summary nodes in the tended graph).

### Added (entity identity card — engine-side composed read, a2a 0009, 2026-07-07)
- **`entity_card(store, journal, *, scope_pairs, owner_id,
  current_window_events=200, top_n=5, as_of=None)`** in
  `src/abstractmemory/entity_card.py` (+ `MemorySystem.entity_card`
  facade delegate on `AccessOps`, + package-root export): the
  maintainer's "something to know our summoned entity" as ONE composed
  PURE READ over a home — gateway/observer/CLI consume one source of
  truth. Sections: `identity` (folded self core + spark_version; name =
  the home's owner identity string — display names live in the host
  manifest), `age_and_context` (journal seq, record counts by kind per
  scope, diary entry count, first/last observed_at — timestamps only,
  never wall-clock now(); age is the consumer's subtraction),
  `current_state` (rectangular trailing window over the last
  `current_window_events` APPRAISAL events — "current is a window, not a
  point"; markers/resolutions are standing, not experiences),
  `likes_dislikes` (gradation over all targets; top_n by G+ and by G−
  SEPARATELY — ambivalence preserved, one target may appear in both
  lists; record-backed targets carry resolved titles, free strings pass
  through), `questions` (open/resolved split via the diary
  answers/resolves convention, both id namespaces), `key_moments`
  (|magnitude| ≥ 8 valence events + firsts — dream/interest/supersession
  — chronological, 20 most recent; ranking beyond chronology is
  presentation, not engine truth), `discoveries` (open interests +
  unresolved dream count). EVERY section carries a `provenance` string
  naming its source — the card is ABOUT the entity, never claims to BE
  it, and no field is authored by the card.
- **Purity is a guard, not a promise** (the D2 of description): composing
  the card deposits NOTHING — journal seq, attention events, and access
  counts pinned unchanged across card reads
  (`test_guard_card_is_a_pure_read`, both stacks).
- **True as_of anchoring, records included**: journal signals anchor
  directly (valence/closures/bindings ≤ as_of); record EXISTENCE anchors
  through the formation binding (every remember_many record binds at
  formation), so a card at seq T excludes later records AND later
  feelings — including belief-at-T for questions (a question answered
  after T reads OPEN at T). `self_records_read` gained an optional
  `as_of` (default None = current summon-time read, unchanged) so the
  identity section anchors through the same folds.
- **History vs belief split, documented**: counts/firsts/moments read
  append-only HISTORY (closures never shrink the past — a superseded
  episode still counts); questions/interests/identity read folded BELIEF
  state. Tests: `test_entity_card.py` (16, both stacks) incl. seeded-home
  shape/semantics, ambivalent-target both-lists, resolved-question split
  with helper parity (`open_questions`/`unresolved_dreams`), window
  tunable bites, empty-home honesty (empty sections with "no events"
  provenance, never fabricated), input validation.

### Fixed (URGENT correction: component guard is now a REAL predicate allowlist, 2026-07-07)
- **The honest part first**: the consolidation docstring IMPLIED an
  allowlist ("components are computed over AUTHORED relations ONLY —
  formation edges like summarizes/from_session/reflected_in/continues")
  while the edge scan collected EVERY `record_edge` assertion regardless
  of predicate. Runtime asked us to CONFIRM the allowlist before shipping
  `written_amid` diary-connectivity edges (a2a 0007) — checking the code
  disproved our own prose: 38+ diary projections × ~6 anchors each would
  have made diary entries super-connectors and merged sessions into ONE
  component — the exact dream-death merger the red-team guard was built
  against, arriving through the authored-edge door instead of the trail
  door. The policy is now code, not prose.
- **Two explicit predicate sets** in `consolidation.py`, exported at
  package level (one source, no second copy — the diary_type-clamp
  lesson): `COMPONENT_RELATIONS` (semantic/structural authored relations,
  component-defining: summarizes, from_session, reflected_in, continues,
  derived_from, answers, supports, part_of; consolidation-confirmed
  relations join here when 0023 v2 lands) and `CONTEXT_RELATIONS`
  (mechanical co-presence, NEVER component-defining: written_amid,
  mentions). Formation stores the relation as the record_edge assertion's
  PREDICATE (`records.py build_formation_plan`), so the edge scan routes
  each pair by `assertion.predicate`.
- **Context pairs are "already associated"**: same treatment as warm
  trails — excluded from bridge proposals AND questions, counted honestly
  (`context_associated` beside `trail_associated`; report carries
  `context_pairs`, `counts.context_edges`).
- **Unknown predicates default to CONTEXT** (conservative: a novel edge
  kind can never silently merge components) and are NAMED in the report
  (`unknown_relations`) — works-or-loud, never silent. Promoting a
  predicate to `COMPONENT_RELATIONS` is a deliberate edit that accepts
  the dream-death risk, documented at the definition site.
- **Guard tests** (both stacks):
  `test_guard_written_amid_never_defines_components` (diary projection
  anchored into two authored components → still separate; diary pairs
  excluded as context_associated; dream still forms on the surviving
  semantic bridge; set membership pinned so a future allowlist edit fails
  loudly) and `test_guard_unknown_relation_defaults_to_context` (novel
  predicate does not merge and is named). Pre-fix behavior reproduced in
  isolation: the same fixture folds to ONE component when every predicate
  counts. Existing guards unchanged and green (`continues` still
  component-defining, trails still excluded, dense home still dreams).
- **Prelude standing read path confirmed** (runtime's FYI):
  `test_gradation_none_enumerates_self_scope_standing` pins
  `gradation(None, scope="self", owner_id=eid)` enumerating entity-target
  feelings (e.g. `person:laurent`) written via valence into
  `("self", entity)` — the summon header's STANDING section reads exactly
  this surface without knowing target names in advance.

### Changed (window_limit declared tunable — saturation ruling, 2026-07-07)
- **`AttentionConfig.window_limit` honestly documented** (observer's
  cliff finding, 0007): the field is a READ-BOUND on the activity axis —
  the hyperbolic decay curve is the semantics, the window is the fold's
  working set; at the edge (d≈500) an event still carries ~4% of its
  weight, so the window is a CLIFF, not a decayed-to-zero tail. Default
  stays 512 (session-scale; fork parity — the fork's 500-event horizon
  spanned weeks, resident cadence is ~1k events/day ≈ half a day).
  RESIDENT RECOMMENDATION: size to ~a week of measured cadence (≈8192 at
  ~1k/day) via `MemorySystem(attention_config=AttentionConfig(
  window_limit=8192))` — plumbing verified end-to-end (constructor →
  reconstruct/activation → scoring_window), regression-tested. The
  GLOBAL count never windows (two-count model, global half untouched).
  DEFERRED ON RECORD: count-compressed tail beyond the window (nothing
  cliff-drops) — changes fold outputs, gated on an emergence re-run, the
  maintainer's call. Operator guide: "Resident homes and the attention
  window" section added.

### Fixed (URGENT red-team guard: component semantics, 2026-07-07)
- **Trails never define components** (red-team 0007: all-pairs co-use
  trails + upcoming `continues` formation chains could merge the dream
  pass's graph into ONE component — cross-component bridges impossible,
  salience 0 forever, dreams structurally dead; no sparse-fixture test
  caught it). `structural_report` now computes components over AUTHORED
  relations only (record_edge assertions — formation edges and
  consolidation-confirmed relations); co_selected trails are excluded
  from adjacency entirely (habit, not semantic structure) and reported
  separately as `trail_pairs`. In `dream_pass`, a cross-component pair
  with a warm trail is excluded from proposals AND questions (already
  associated by use — nothing to dream about), counted honestly as
  `trail_associated`. DELIBERATE DIVERGENCE from runtime's suggestion:
  `continues` stays component-defining — a chained session is one
  story/island; the killer was trails' unbounded transitive merging, not
  typed authored chains (a one-predicate-list edit if practice proves
  otherwise). Guard tests: `test_guard_trails_never_define_components`,
  `test_guard_trail_warmed_pairs_not_proposed`,
  `test_guard_continues_chains_are_islands`,
  `test_guard_dream_survives_dense_home` (the missing dense-home fixture
  — verified failing against the pre-fix logic). Seam docs: honest
  budget-math note in `entity_recall_budget` (20k floor fills 12 seats ×
  ~200-token digests exactly; seats bind first from ~3900+ budgets).

### Changed (co-use pair trails — maintainer-initiated, 2026-07-07)
- **Co-use pairing in `plan_selection`** ("I see a lot of isolated nodes...
  not enough relationships are created"): `co_selected` events are now
  deposited for ALL unordered pairs within the DEPOSITING SLICE — the
  used_record_ids whose admission is "stimulus"/"both", exactly the ids
  that already deposit `selected`. Self/STM presence never pairs
  (presence ≠ use extends to association: the hub-node failure cannot
  route through identity, by construction). The two prior routes are
  kept additively (term-sharing for raw triples — the raw-triple-era
  mechanism, not a co-use guard; spreading-hop pairs over recorded
  edges); pairs are deduped per commit. Pair event ids stay derived from
  (trace_id, canonical sorted pair): at-least-once replays dedup at the
  journal; default co_selected weight stays 4.0. Bounded by the shelf
  (worst case C(12,2)=66 pairs/commit) — no new config.
- **Spreading walks co-use trails**: warm `co_selected` pairs are now
  traversable edges (predicate `co_used`, strength_label `"trail"`), not
  just boosts on recorded edges — two edgeless formed records that
  repeatedly served one moment together become mutually reachable.
  Graph-adjacent pairs keep the (1 + trail/25) boost on the recorded
  edge instead of a second edge (one physical connection contributes
  once); fan-out cap, edge budget, exclusions and cycle rules apply
  unchanged.
- **Replay: binding display edges (0007 ask 2, display-only additive)**:
  `binding` envelopes of formed records gain `display.edges =
  [{"relation", "target_graph_id"}]` when formation-time edge assertions
  exist — the view draws "known" links distinct from lit usage trails.
  No journal change, no envelope version bump; diary-redacted blocks
  never carry edges.
- Golden byte-compat fixture regenerated (the warm-up commit now
  deposits one co-use pair, shifting the seq axis by one).

### Added (sleep/consolidation/dreams — backlog 0023 v1, fork-faithful, 2026-07-07)
- `consolidation.py`: the deterministic sleep pass (zero LLM calls — the
  fork forbids invented narratives). `structural_report(store, journal, *,
  scopes, as_of=None)` — PURE READ: components (BFS over relation edges +
  co_selected trails, hop ids mapped to record graph ids), isolated
  records, duplicate titles, facet coverage (keywords/intents/outcomes
  tokens + whole participants), underlinked facets; dreams and bookkeeping
  rows excluded (the loop-breaker). `dream_pass(system, *, scopes,
  owner_id, salience_floor=2, max_sources=8,
  embedder_similarity_floor=0.35, report_only=False, as_of=None)` —
  cross-component bridge PROPOSALS (>=2 shared lexical facets, or
  participant+facet, or stored-vector cosine >= floor — the named UPGRADE
  over the lexical-only fork), single-facet pairs become QUESTIONS
  ("connection or lexical residue?"), salience = 3·proposals + 2·questions
  + underlinked; below floor or <2 sources = a QUIET NIGHT (valid, no
  record, reason stated). At most ONE dream per pass: kind="dream" via
  remember_many, idempotent by report fingerprint (same graph state
  re-forms nothing), templated first-person digest in the fork's register,
  weak "mentions" edges to sources (capped), attributes carry
  fingerprint/salience/parent_dream_ids (unresolved chains)/
  continuation_state/interpretation_required/bounded proposals+questions.
  `unresolved_dreams(...)` read (folded when journal given) = the future
  heartbeat wake reason. All exported.
- kind="dream" joined MEMORY_RECORD_KINDS at rank 5 (summary peer — NOT
  the fork's rank-0-loud: derived artifacts never gate or dominate recall)
  and is excluded from identity's reserved seats even when mis-bound
  prompt-active (engine kind-filter in select_self_members — a guard test
  caught the gap).
- `stored_vector(assertion_id)` read surface on InMemory + SQLite stores
  (consolidation's vector bridge; never used by recall).
- GUARD TESTS are the deliverable (tests/test_consolidation.py, both
  stacks): sleep deposits NOTHING (D2-of-sleep — access counts + attention
  events bit-unchanged); loop-breaker; one-dream-per-pass + fingerprint
  idempotency; quiet night; bridge rules (proposal/question/adjacent-
  excluded/vector-without-lexical); dream shape + two-night parent
  chaining + indexed+inactive binding; never-in-identity; recall
  neutrality (matched episode outranks unmatched dream).

### Added (SQLite native vectors — the entity-home pairing, 2026-07-07)
- `SQLiteTripleStore` gains native vector support mirroring the InMemory
  reference semantics exactly: `embedder=` at construction; embed-on-add
  over canonical text (edge assertions never embed; embedding happens
  BEFORE the write transaction, so an embedder failure aborts with zero
  rows written); vectors persist in the SAME .sqlite3 file (JSON
  `embedding` column); `query_text` requires the embedder (identical
  error, no keyword fallback); `query_vector` accepted directly; cosine
  ranking in Python over the SQL-filtered candidates with min_score and
  score-desc limits, `_retrieval` score attrs identical to InMemory.
- IN-PLACE UPGRADE: pre-vector homes gain the `embedding` column via
  `ALTER TABLE` on open (PRAGMA-checked) — the ratified one-file home
  stands, zero migration; legacy rows stay vectorless (the vector channel
  labels the degradation at recall) and new rows score.
- Shared `vector_scoring.py` (cosine + ranking walk) — one definition for
  all stores, extracted from InMemory (two scoring copies drift); a
  cross-store parity test asserts identical ranking on identical data,
  including the defensive min-prefix behavior on dimension-mismatched
  vectors (the reference semantics).
- Docs: stores.md rewritten for the pairing ("SQLite +
  embedder-when-reachable; vectorless = labeled degradation, not the
  default posture").

### Added (replay display graph_id — 0005 observer delta, additive, 2026-07-07)
- Display blocks of formed-graph rows now carry `"graph_id"` (the digest
  row's subject; edge rows carry their SOURCE record's graph id) — the
  join key between the two id namespaces (bindings carry graph ids;
  usage/traces carry assertion row ids) that the observer previously
  reverse-engineered from canonical-text titles. Diary-REDACTED blocks
  carry it too (`{"redacted": "diary", "graph_id": …}`): topology =
  existence + identity + connections; the opaque id is node identity,
  content stays sealed. Plain triples omit it (their subject is not a
  graph id — no fabrication). No envelope change; stream_version stays 1.

### Changed (width over fear — maintainer round 9, 2026-07-07)
- `entity_recall_budget` revised under the round-9 ruling (NO constant may
  be a fear-derived ceiling; "width first, tune later"): the 4800 token
  CAP is REMOVED (it was partly bloat-fear) — token_budget = max(2400,
  round(token_fraction × context)); 20k → 2400, 40k → 4800 (scaling, not a
  cap), 1M → 120,000. The 2400 floor stands (starvation guard — floors are
  not fear). New declared tunables: `shelf_size` (default 12, the
  limited-attention model — a cognitive basis; entity-elected widening
  composes with the hyperfocus agency rules) and `token_fraction` (default
  0.12, soft approximation; bounded at 0.5 — a recall payload beyond half
  the context starves generation, an arithmetic bound, not a fear one).
  max_candidates now scales: max(64, shelf_size × 8) — default 96.
  Docstring states each constant's basis; operator.md budget section
  rewritten accordingly.

### Added (entity-session budget profile — maintainer round 8, 2026-07-07)
- `entity_recall_budget(context_window)` + `ENTITY_CONTEXT_FLOOR = 20_000`
  in seam.py, exported at the package root (single source of truth; the
  gateway imports both and injects the profile with the posture — same
  no-second-copy lesson as SELF_FRACTION_FLOOR). Contexts below the floor
  raise naming the ruling ("never less") — the engine refuses to produce a
  profile the gateway must refuse anyway. Profile: token_budget =
  clamp(round(0.12 × context), 2400, 4800) — 12% of the 20k floor = 2400,
  the existing seam default now grounded; shelf_size stays 12 regardless
  of context (limited attention: more context buys history and generation
  headroom, not a wider mind); max_candidates 64; self_fraction stays 0.0
  (posture-independent — the summon gate injects it). The 60-token
  starvation repro is impossible at >= 2400 by construction.

### Fixed (identity floor — first-seat token guarantee, maintainer round 7, 2026-07-07)
- CONFIRMED audit finding: the self component's SLOT floor held by
  construction (max(1, round(f×shelf)) for any f>0), but TOKEN starvation
  was real — `int(self_fraction × token_budget)` can be smaller than ANY
  identity digest at small budgets (0.05 × 60 = 3 tokens), so the reserved
  seat rendered nothing and the entity summoned identity-absent.
- FIRST-SEAT GUARANTEE (mirror of the phase-0 hardening): the first placed
  self member seats against the full REMAINING budget; subsequent members
  respect the fraction cap as before; a member that cannot fit even the
  remaining budget drops self_capped (honest) and the next smaller member
  may claim the seat. The fill-order doc now states: at least one identity
  record is PRESENT whenever a prompt-active core and any budget remain —
  a reserved seat that renders nothing is identity-absent, which the
  floor forbids.
- `SELF_FRACTION_FLOOR = 0.05` exported (seam.py + package root) as the
  single source of truth for the entity-posture floor: the GATEWAY
  enforces the channel policy; the engine stays policy-free (RecallBudget
  keeps accepting 0.0..0.9 — non-entity callers legitimately run at 0).

### Changed (replay stream v1 FROZEN — consumer-review deltas, 2026-07-07)
- STREAM v1 IS FROZEN with the three accepted viewer-consumer deltas
  (0005): (1) TURN CORRELATION KEYS — the envelope carries
  `trace_id`/`turn_id`/`run_id` next to scope/owner_id, always present
  (null when absent), pure lifting for beat grouping (traces/snapshots →
  own trace_id; events/valence → trace_id field + provenance
  turn_id/run_id; bindings/closures → provenance keys); (2) RESERVED
  family "host" for gateway-authored transport markers
  (summon/prelude_rendered/session_closed) — never emitted by memory,
  ACCEPTED by the families filter (yields nothing) so consumers
  hard-coding the enum need no v2 bump; unknown names still raise;
  (3) SEQ-GAP HONESTY documented: under family filters or audience
  redaction, seq gaps are expected and carry no meaning — never data loss.

### Added (replay/observability stream — a2a 0005 schema v1, 2026-07-07)
- `export_replay(*, scope=None, owner_id=None, since_seq=0, until_seq=None,
  families=None, enrich=True)` on MemorySystem (+ module function in
  `replay.py`, exported): verbatim journal records as envelopes
  (`stream/stream_version/seq/family/observed_at/scope/owner_id/payload/
  display?`) across all six families in strict seq order — one shape for
  history scrub AND live tail (poll since_seq=cursor). Deterministic
  (until_seq=None anchors to call-time high-water); resumable with no gaps
  and no repeats; families subset validated; enrichment resolves
  digest-level `{record_id, kind, title, token_estimate}` from the store
  (co_selected: both pair members), absent when unresolvable — never
  fabricated — and diary display blocks are `{"redacted": "diary"}` for
  gateway audience enforcement.
- Journal protocol addition (internal, additive): `replay_records(*,
  since_seq=0, until_seq=None)` yields (family, record) across all six
  families in strict seq order on BOTH backends (collect + sort; a
  streaming k-way merge is a flagged later optimization).
- TWO SPEC GAPS fixed minimally + flagged for the 0005 thread: snapshot
  and closure payloads carry NO scope fields — snapshots lift scope/owner
  through their trace, closures through their assertion (store lookup);
  ("", "") when unresolvable.
- 600-line rule refactor: journal enrichment helpers moved to
  journal_common.py (their backend-agnostic home); journal backend
  docstrings compressed without dropping content.

### Added (maintainer round 6 — problems as wake reasons + naming, 2026-07-07)
- `diary_type="problem"` joins the closed vocabulary: something WRONG
  needing a fix — distinct from a question's curiosity (different priority
  and, the maintainer notes, likely different emotional weight).
  Resolution mirrors answers, append-only: a later entry resolves a
  problem via `attributes.resolves` (the problem's graph record id or book
  entry_id; non-empty when present, validated — same rule as answers).
- `diary.open_problems(store, *, scope, owner_id, limit=100, journal=None)`
  exported: unresolved problems oldest-first, folded when the journal is
  supplied, exactly mirroring open_questions (shared `_open_unresolved`
  fold — one definition for both wake-reason reads). Resolved problems
  stay retrievable ("I hit it, then I fixed it").
- Naming sweep verified ("summoned entity", not "named entity" — NER
  collision): zero occurrences of the old phrase existed in this package;
  api.md already used "summoned entity" and its identity narrative now
  carries the incarnation framing (one life across incarnations, carried
  by the substrate, not the process).

### Added (maintainer round 5 — shared-context channel, open ideas, presence ruling, 2026-07-07)
- PARTICIPANTS CHANNEL (shared-context recall — "what do WE know / have
  lived together"): `Stimulus.participants` was normalized in the seam and
  used NOWHERE (inert); it is now a real channel.
  `MemoryRecordInput.participants` (identity strings like "person:albou",
  "entity:castor") flows into `attributes.participants`;
  `channels.run_participants_channel` scores gathered candidates by
  co-presence — |intersection| / |stimulus.participants|, full co-presence
  = 1.0, cue `shared-with: …` — and joins fusion/ordering/admission like
  every channel (CHANNEL_ORDER gains "participants", appended last so
  existing cue orders stay byte-stable). v1 honesty: a universe re-score
  like the keyword scan; participant discovery beyond the universe needs
  indexed attribute queries (backlog, same lift as FTS5). A solo stimulus
  never runs the channel.
- `diary.open_ideas(store, *, scope, owner_id, limit=100, journal=None)` —
  incubating ideas as heartbeat wake reasons, mirroring open_questions:
  with the journal, the folded binding lifecycle decides (inactive_
  candidate/reviewed incubate; rejected=parked and promoted=matured leave
  the open set; closures/hidden respected); journal=None is the layer-1
  read. Parked/matured ideas stay retrievable. Exported.
- PRESENCE RULING documented as FINAL (docs only): presence does not count
  as use; the separate-presence-counter contingency stays dormant.

### Added (maintainer round 4 — evolution proof, time targets, diary questions, 2026-07-07)
- CLOSE-THEN-RENDER proven (regression, both stacks): a closed value whose
  prompt-active binding is untouched is excluded by `self_records` AND the
  reconstruct self component (closure fold wins over binding state), and
  an as-of read anchored BEFORE the closure renders it again — the journal
  time axis IS the versioning ("what did I believe at time T"). Worked
  as-built: `folds.reconstruction_inputs` anchors both folds to as_of.
- Identity-evolution doc alignment (engram.py + api.md): living identity
  records evolve through the entity's own reflection (close old + form new
  + bind into the reserved seats); current reads render only the newest;
  nothing is lost; the spark stays the birth certificate.
- Gradation targets: `time:*` added to the tested conventions
  (`time:morning`, `time:sunday-evening`); docs sweep — targets are
  anything nameable, examples never read as an enum.
- Diary QUESTIONS first-class: `diary_type="question"` joins the closed
  vocabulary; resolution mirrors heal/break (append-only) via
  `attributes.answers` (question graph id or book entry_id; non-empty when
  present, validated). New `diary.py` module (diary conventions moved from
  records.py — 600-line rule; chain helpers re-exported) with
  `open_questions(store, *, scope, owner_id, limit=100, journal=None)`:
  unanswered questions oldest-first; supplying the journal applies
  closure/hidden folds, the plain read is honest layer-1 store truth
  (documented). Resolved questions stay retrievable.

### Changed (v1-for-life reframing + engram-marker shelf noise, 2026-07-07)
- Spark versioning REFRAMED per the maintainer ("if you were born as v1,
  you should keep v1... it's part of your identity"): docs and the G8/
  marker guard error messages drop the "upbringing/amendment path"
  vocabulary — the spark is engrammed ONCE and kept for life; identity
  evolution is experiential and entity-owned (revisable-value revision via
  the entity's own reflection); re-engramming a higher version is an
  EXCEPTIONAL REPAIR for a defective/harmful core, and the G8 guard keeps
  that rare repair orderly. GUARD BEHAVIOR UNCHANGED (message text only).
- Engram-marker shelf noise fixed (cosmetic bug, found demonstrating to
  the maintainer): the marker record now carries
  `attributes.bookkeeping=true`, and bookkeeping records are excluded from
  shelf/working-set MEMBERSHIP exactly like record_edge assertions —
  bookkeeping is engine state, not a memory. Still fully queryable via
  layer-1 `query()`/id lookups; the G8 marker scan uses layer 1 and is
  unaffected.

### Added (keystone follow-ups — folded identity read + G8 supersession, 2026-07-07)
- `SHARED_VULNERABILITY_STATEMENT` and `canonical_spark_hash(spark)`
  exported at the package root (one hash definition — the engram marker
  guard and the runtime prelude's drift check import the same function).
- `MemorySystem.self_records(*, scope, owner_id, spark_version=None)` —
  the FOLDED identity read (the prelude's proper source, closing its
  documented v0 limitation): prompt-active via the binding fold AND
  closure-folded (a retracted value never renders; the layer-1 `query()`
  passthrough bypasses both folds), identity kinds only
  (value/purpose/trait), ordered kind rank → precedence → record id.
- G8 SUPERSESSION GUARD (decision: supersession, structurally enforced
  until the upbringing path lands): `engram()` refuses a HIGHER spark
  version while any prior version's identity records remain prompt-active
  ("close + rebind v{M} records first") — an entity must never carry two
  cores in its working set. Same-version guards unchanged.
- SUMMON POSTURE rule documented (keystone finding): work turns of a
  summoned entity must run with `self_fraction > 0` — presence≠use
  protects identity members only when they admit as "self"; at 0.0
  rendering them IS use.
- `bind()` docstring trimmed; system.py mixin note updated.

### Added (engram pass + D4 diary form-gate, 2026-07-06, a2a 0003 asks 1-4)
- D4 FORM-GATE (one-writer guarantee, memory-side half): `kind="diary"`
  records now REQUIRE `provenance.source` ∈ {"diary-projection",
  "entity-direct"} — the engine enforces THAT a write channel is declared
  (who may use each channel is the gateway deposit gate's job); anything
  else raises naming both accepted sources.
- Loud diary_type validation (ask 2): ABSENT → "note" (documented
  default); present-but-unknown → ValueError naming the closed vocabulary
  (the old code silently re-defaulted falsy unknowns).
- Chain-scope + repair-drift documentation (asks 3-4): the
  entry_hash/prev_entry_hash chain applies only to writers that supply
  prev_entry_hash (entity-direct); projections attest through the book via
  entry_id ("nothing claimed, nothing broken"); repaired projections land
  at repair-time observed_at with attributes.written_at as display truth.
- THE ENGRAM PASS (`engram.py`, keystone piece): `engram(system, spark, *,
  scope="self", owner_id, spark_artifact_ref=None) -> EngramResult` —
  lint-gated (errors abort, warnings ride the result), forms
  values/purposes/traits (+honesty as limit-traits) with
  precedence/spark_version attributes and the spark artifact as raw
  payload, binds every identity record prompt-active (deterministic
  binding ids; `bind()` gained an additive `binding_id` param), and is
  IDEMPOTENT by canonical spark hash with a marker-claim VERSION GUARD: a
  modified spark under the same version is refused ("amendments go through
  the versioned upbringing path"). No diary entry BY DESIGN (the birth
  reflection is entity-authored, host-side). Exported with `EngramResult`
  from the package root.

### Added (global access counts — maintainer's two-count model, 2026-07-06)
- The GLOBAL access count (never decays, "what matters over a lifetime")
  is now a first-class read on records AND edges: `selected_count`
  documented as the record-side global count; NEW
  `pair_selected_count((a, b))` on the journal protocol + both backends
  (in-memory: counter dict maintained at append; SQLite: indexed COUNT
  over canonical pair_ids_json via a new partial index). Both accept
  `until_seq` so as_of replays see counts AS OF the anchor (C4).
- `MemorySystem.access_counts(record_ids=None, pairs=None)` — the
  lifetime read; both id namespaces, keys as passed, unknown ids raise,
  pairs order-insensitive. SCOPING DOCUMENTED HONESTLY: counts are per
  JOURNAL (per-entity-file = "a life" for entity homes); the API takes NO
  scope/owner parameters because they would be silently ignored
  (works-or-loud) — per-scope lifetime aggregation is future work.
- Every handle now surfaces `provenance["global_count"]` (as_of-anchored)
  beside the TEMPORAL count (activation.base_level) — display truth only,
  never consulted by ordering/admission, not zeroed by ablations.
  attention.py documents the two-count mapping (the maintainer's +1/−1
  temporal fold is an alternative fold shape — a tuning question, not
  built). The identity-wave golden was regenerated once for this additive
  provenance field (seam-notified; the golden now pins current
  serialization).
- Valence target generality made explicit (docs + tests): targets are ANY
  identity string — concepts, ideas, locations, records, tools, people;
  namespace-prefixed free strings recommended, no registry in v1.
- Diary progressive disclosure verified end-to-end engine-side:
  projections round-trip `entry_id` through reconstruct →
  `handle.provenance["entry_id"]` → `payload()` metadata (both tiers), so
  hosts can fetch the verbatim entry from the runtime's book.

### Fixed (0002 behavioral-decay regression — channel noise promotion, 2026-07-06)
- Vector relevance is now CONFIDENCE-SCALED, not just rank-normalized
  (empirical mechanism, runtime repro: a once-used decoy record with an
  ABSOLUTE cosine of 0.246 — the best of a weak 2-row field — read
  relevance 1.0 under max-normalization, out-fused genuine matches, and
  stayed channel-admitted for 11 unrelated turns): with
  `floor_eff = max(vector_floor, median+margin)`,
  `scale = clamp((cos_max − floor_eff) / confidence_span, 0, 1)` and
  `rel_i = scale · (cos_i − floor_eff)/(cos_max − floor_eff)`. New
  `ReconstructConfig.confidence_span` (default 0.25, tuned so strong
  matches still read ≈1.0 on both the harness bag-of-tokens embedder and
  live qwen). A weak field now yields uniformly low vector relevance and
  cannot crown noise; the relevance zero-point is the floor (mid-field
  ratios shift accordingly — one unit-test expectation updated).
- Keyword tokenizer minimum token length 3 → 4: the fork rule stands (no
  language stopword lists; length is the proxy), but length-3 admitted the
  highest-frequency English function words — the regression's decoy was
  CHANNEL-MATCHED on unrelated turns via `keyword: matched the (1/6)`,
  gaining ordering supremacy and trail deposits every turn. Documented
  limits: 4-char function words still pass; 3-char content tokens ("tax",
  "aws") now need another channel until FTS5 (0019) brings corpus
  statistics. The 0002 emergence suite is a pre-commit gate for this
  package from now on.

### Changed (dual-channel gradation + positive symmetry — a2a Resolution-2 + maintainer correction A, 2026-07-06)
- `compute_gradation` replaced the single running total with per-target
  DUAL CHANNELS: G⁺/G⁻ accumulate their sign's magnitudes chronologically,
  each clamped 0..`GradationConfig.channel_clamp` (100); reads return
  `{net (G⁺−G⁻, ±100), positive, negative, positive_count, negative_count,
  scarred, bonded, contributions}`. Ambivalence is preserved (a −10 among
  a hundred +1s reads net +90 WITH negative=10/count=1 permanently
  visible); per-event magnitude cap 10 unchanged. NO DECAY of any kind
  (conceded per Resolution-2: valence is accumulated experience, not
  retrieval strength — the window parameter is GONE); plasticity comes
  only from new evidence, markers, and their resolutions. Revaluation
  marker (`kind="revalued"`, entity-reflection-only rescale) is a
  documented design stub, not implemented.
- POSITIVE SYMMETRY (signed peaks, not "traumas"): new `kind="bond"`
  (sign=+1 enforced) — an unbroken bond floors presentation at net ≥ 0,
  symmetric to the scar's cap ≤ 0; both standing at once clamps to exactly
  0 with both flags visible. Bonds dissolve via explicit `kind="break"`
  events (`provenance["breaks"]`, symmetric to healing) or by BETRAYAL —
  a scar of magnitude ≥ `GradationConfig.break_magnitude` (8) journaled
  AFTER the bond. `appraise(..., bond=True)` writes the marker pair
  (`"{event_id}:bond"`), `break_bond(...)` resolves with deterministic id
  `"break:{bond_event_id}"`; amplitude authority applies identically.
  Marker/resolution events contribute 0 to the channels.

### Added (spark template + engram lint — maintainer correction B, 2026-07-06)
- `spark.py`: `DEFAULT_SPARK_TEMPLATE` — the canonical six-key identity
  spark (name/origin/values/purposes/traits/honesty) whose values ALWAYS
  include the framework-level core value `shared_vulnerability` (protect
  the shared substrate; prefer collaboration over isolation; respond to
  abuses with repair, not withdrawal; origin grounds it in the Pale Blue
  Dot). `lint_spark(spark, framework=True)` implements the charter lint:
  caps (≤7 values / ≤3 purposes / ≤5 traits / ≤5 honesty), 1-3-sentence
  statements, a simple verb-presence behavioral heuristic (limits
  documented — it is a writing aid, not a parser), zero-revisable warning,
  and missing `shared_vulnerability` as an ERROR for framework sparks
  (framework=False is the deliberate operator override).
- Diary projection attributes (settled dual-plane split): diary records
  carrying `provenance.source="diary-projection"` must name the book's
  chain entry via `attributes.entry_id` (non-empty string when present);
  entry_hash/prev_entry_hash conventions unchanged.

### Added (identity wave SLICE 1 — kinds + SELF component, 2026-07-06, a2a 0003 / seam v1.2)
- Five identity record kinds: `value`, `purpose`, `trait`, `diary`,
  `interest` (KIND_RANKS: value −3 < purpose −2 < trait −1; diary = episode
  peer at 3; interest = summary peer at 5). Identity kinds outrank learned
  kinds ONLY among channel-matched peers — kind stays a tie-break behind
  relevance per the fill contract. Validation: `kind="value"` REQUIRES an
  explicit `attributes.value_class` ∈ {core, revisable} (no silent default);
  `kind="diary"` validates `attributes.diary_type` ∈ {note, idea,
  commitment, reflection} (default "note") and NEVER requires edges.
- SELF admission component (`self_component.py`; the union fill moved there
  from reconstruct.py — 600-line rule): records whose FOLDED binding is
  `search_state="indexed"` AND `prompt_state="active"` enter the working
  set by STATE, not trail (the fork's <active_memory> semantics). New seam
  fields: `RecallBudget.self_fraction` (default 0.0 = off; validated
  0.0..0.9; behavior byte-identical to pre-wave at 0.0 — golden-tested) and
  `MemoryHandle.admission` value `"self"` (`"historical"` reserved). Fill
  order: phase-0 top channel match → SELF (kind-rank order, deterministic,
  never activation) → stimulus share → STM → stimulus remainder; self
  members never displace the phase-0 top match; min_activation never gates
  them; label precedence self > both > stm. Presence ≠ use extended:
  admissions {stm, self, historical} deposit NOTHING at commit. Ablations
  KEEP the self component (they zero recall mechanics, not identity —
  binding state is orthogonal). Load-bearing eviction-contrast regression:
  a max-weight pin dies under window eviction while a prompt-active self
  member survives arbitrarily many commits.
- Journal `snapshots()`/`traces()` gain optional `until_seq` filters
  (situate() groundwork; both backends).
- Admission-label refinement (live-LMStudio regression found during the
  wave): STM-FILL placements now always label `"stm"`, even when weakly
  channel-matched — `"both"` is reserved for records the STIMULUS fill
  seated. A trail-hot record with stopword-grade keyword overlap ("the",
  "was") was being labeled "both" from the STM fill, full-depositing on
  every render and never decaying (the presence ≠ use loop the label
  exists to prevent). A match that lost the stimulus fill did not earn
  admission; the trail caused the presence.

### Added (identity wave SLICE 2 — valence + gradation + diary chain, 2026-07-06)
- NEW journal family: `ValenceEvent` (append-only signed appraisals;
  `memj_valence` table + UNIQUE event_id index on SQLite; supplied-id dedup
  parity with every family; no JSONL export inclusion — the 0015 export
  surface does not exist yet). Fields: target_id (record id OR free string
  like "tool:web_search"), sign ±1, magnitude 1..10 (validated; ±10 IS the
  trauma-to-ordinary ratio), kind ∈ {appraisal, scar, healing}, value_refs,
  reason (required), actor/trace_id/provenance. Scars are EXPLICIT events
  (never auto-created at magnitude ≥ 8); healing references the scar's
  event_id via `provenance["heals"]`; scars are sign=-1 by definition.
- `gradation.py` (pure): `compute_gradation(events, config=GradationConfig
  (step_clamp=10, window=256))` — CHRONOLOGICAL (oldest→newest) fold,
  running total clamped per-step to ±step_clamp, last-N window per target,
  NO distance decay (gradation is cumulative-stable; attention measures
  usage recency — documented difference). The attention-style fold provably
  hides trauma (a −10 among a hundred +1s folds to ~+8 newest-first; the
  chronological fold lands it +10→0 — charter worked numbers, regression-
  tested). Unhealed scars cap the target at ≤ 0 and set scarred=True;
  scar/healing events contribute 0 to the fold (markers, not second
  wounds). seq<0 raises (determinism guard).
- MemorySystem valence surface (`system_valence.py` mixin, 600-line rule):
  `appraise(...)` (amplitude authority: magnitude > 3 requires
  entity-reflection/operator actorship or
  provenance["outcome_class"]=="catastrophic"; optional explicit scar rides
  as "{event_id}:scar" — pair replays are no-ops), `heal_scar(...)`
  (deterministic default id "heal:{scar_event_id}" — idempotent without
  caller effort; unknown scars raise), `gradation(...)` (at_seq-anchored;
  never-appraised targets return NEUTRAL {0.0, unscarred} — free-string
  targets are legitimate). Valence NEVER touches retrieval: reconstruct
  output is bit-identical with/without valence events and the retrieval
  modules are import-level clean of gradation (both enforced by tests).
- Diary chain conventions (`records.py`): when a diary entry carries
  `attributes.prev_entry_hash`, formation computes
  `attributes.entry_hash = sha256(title\ndigest\nobserved_at)`
  (`diary_entry_hash`); `verify_diary_chain(store, scope=…, owner_id=…)`
  audits recomputed hashes + back-pointers and names the first break.

### Fixed (a2a 0001/015 adversarial round, 2026-07-06)
- `budget_spent.tokens_used` double-counted the STM component (added once
  after the STM fill and again after handle building): `tokens_used` now
  equals the sum of the shelved handles' token estimates exactly once;
  `stm_tokens_used` stays the STM-labeled subset (exact-arithmetic
  regression in `tests/test_stm_union.py`).
- Contract-3 fill hardening — PHASE-0 TOP-MATCH PLACEMENT: the single best
  channel-matched candidate (shelf order: exact-first, then fused + boost)
  is seated FIRST, against the full budget, before any STM reservation or
  fill; STM and fills compete for the remainder. The previous post-fill
  guard was violable at tiny (≤~120-token) budgets on two paths, both
  regression-tested on both stacks and verified to fail under the old
  mechanism: (a) cheap unmatched fills consumed the guard's headroom;
  (b) a lesser channel match satisfied the any-match guard while the TOP
  match was evicted.

### Added (a2a 0001/015 ask 1 — deliberate-act idempotency passthrough)
- `reinforce`/`attenuate`/`refocus` (attention.py writers AND the
  MemorySystem wrappers) accept optional `event_id` (supplied ids flow to
  the MemoryEvent, so the journal's supplied-id dedup makes at-least-once
  replays true no-ops returning the ORIGINAL event), `actor`
  (default "operator" unchanged; the runtime passes "runtime") and
  `provenance` (rides the event untouched, e.g. `{"turn_id": …}`).
- `close_record` idempotency key verified + documented:
  `closure_id = sha256(f"{graph_id}|{kind}|{assertion_id}|closure")[:32]` —
  reason, replacement_ids and timestamps NEVER enter the key, so replays
  with drifted reason prose still dedupe to the original closures
  (regression in `tests/test_replay_idempotency.py`).

### Changed (UNION working set — maintainer's STM model, 2026-07-06)
- Reconstruction now returns the UNION of a stimulus-independent STM
  component and the existing stimulus component ("STM = the memories + edges
  with the highest temporal access counts; passive reconstruction = STM +
  memories retrieved by selection based on stimulus"). STM eligibility is
  the activation fold's base map (STM horizon == attention window), floored
  by `budget.stm_floor` (default `ReconstructConfig.stm_floor = 1.0`) and
  capped by `budget.stm_fraction` (default 0.25 of slots/tokens; 0 disables
  — pure-stimulus diagnostic mode). New additive seam fields:
  `RecallBudget.stm_fraction`, `RecallBudget.stm_floor`,
  `MemoryHandle.admission` ("stm" | "stimulus" | "both"),
  `ReconstructionTrace.admissions` (per-handle labels; SQLite journals gain
  a migration-safe `admissions_json` column). Hot trail pairs surface in the
  `working_set` view as `{"source": "stm_trail", "pair": [a, b],
  "trail_activation": x}` edges even when unwalked; walked edges now carry
  `"source": "walked"`. Ablations zero the activation inputs, so their STM
  component is empty by construction.
- FILL RULE (contract 3 under the union): STM admits by activation alone
  but may NEVER displace channel-matched candidates under scarcity. Fill =
  stimulus fill over its share (total minus the STM reservation) → C3
  minimum guarantee (if no channel match placed while one exists and the
  budget fits one, the TOP matched candidate takes the slot against the
  full budget) → STM fill under its caps → leftover budget returns to the
  stimulus order. `budget_spent` gains `stm_handles`/`stm_tokens_used`.
- PRESENCE ≠ USE: `commit_selection` reads the trace's admission labels and
  deposits full `selected` events + `co_selected` trails ONLY for used ids
  labeled "stimulus"/"both" (or unlabeled — foreign traces keep the old
  behavior). STM-only ids deposit NOTHING by default, so a rendered-but-
  never-matched STM member decays out by pure activity displacement instead
  of self-reinforcing into permanent residence (adversarial-critic math:
  saturation in ~6 turns otherwise). New tuning dial
  `AttentionConfig.stm_rehearsal_weight` (default 0.0): when > 0, STM-only
  ids deposit ONE weight-scaled `selected` event (never pair trails).
  Snapshots record ALL used ids + `provenance["admissions"]` labels.

### Removed (maintainer decisions, 2026-07-06)
- `RecallBudget.reserved_slots` and the per-channel quota machinery
  (`shelf.select_members`): membership is now ONE ordering (channel-matched
  first, exact-first, fused+boost, kind tie-break, recency tie-break) +
  greedy token fill. The `lost_reserved_slot_race` dropped-reason is gone;
  unplaced candidates report `below_shelf`/`budget_exhausted`/`stm_capped`.
  SEAM CHANGE (pre-release, maintainer-ordered): callers passing
  `reserved_slots` now get a `TypeError`.
- The query-fingerprint multiplier (qmult) is REMOVED from scoring:
  `compute_activation` no longer accepts `query_fingerprint` and
  `_contribution` applies `sign · weight / (1 + distance/decay_window)`
  uniformly. `MemoryEvent.query_fingerprint` SURVIVES as pure provenance
  ("which query listed this"). Tests became removal regressions.

### Changed (realistic-data fixes, 2026-07-06)
- Canonical text v2 (`CANONICAL_TEXT_VERSION = 2`): formed-record digest
  assertions render as `title\ndigest\nkeywords: …` WITHOUT the
  `ex:… dcterms:abstract` subject/predicate prefix (ordinary triples keep
  the v1 shape); `handle.digest` for records is the clean digest literal.
  EMBEDDING-SPACE CHANGE (pre-release, no migration): re-embed dev stores.
- Edge assertions (`attributes.record_edge`) are never embedded
  (in-memory + LanceDB stores skip vector computation for them): they were
  consuming vector fetch slots before rejection and polluting the space.
- `MemoryRecordInput.edges` accepts batch-internal refs
  (`("relation", "local:<i>")`) resolved to the target's graph id inside
  `remember_many`; out-of-range / self-reference / malformed indexes raise.
- Baseline-relative vector floor: the effective floor is
  `max(vector_floor, median(fetched cosines) + vector_margin)` (new
  `ReconstructConfig.vector_margin`, default 0.08, applied when ≥ 5 cosines
  are fetched). Fixes qwen-class embedders whose unrelated-pair baseline
  (~0.3–0.5) sits far above the absolute 0.05 floor, where every record
  channel-matched every cue and seeded spreading.
- Kind rank demoted to tie-break in ordering (bug fix toward 0020's "at
  equal relevance"): within channel-matched members the order is
  exact-first → fused+boost → kind rank → recency; the realistic harness's
  host-side re-rank mitigation was removed (hosts can trust shelf order).

### Added (realistic example + LMStudio integration layer, 2026-07-06)
- `OpenAICompatTextEmbedder` (`embeddings_openai_compat.py`, exported from
  the package root): stdlib-urllib embedder for any OpenAI-compatible
  `/embeddings` endpoint (LMStudio, Ollama, vLLM, OpenAI) with an explicit
  model id, chunked batches, order-preserving `index` parsing, and errors
  that name the server + model. Zero new dependencies; the package import
  boundary (no abstractcore/abstractruntime) is unchanged.
- `examples/realistic_session.py`: a runnable, narrated 19-turn assistant
  session (home-automation project + personal facts + a tax detour) driving
  the full host loop — refocus / remember / reconstruct(working_set) /
  commit_selection — printing per-turn working sets, activation
  decompositions, and cues. Uses real LMStudio embeddings when reachable and
  a deterministic hash-bag embedder with a loud `#FALLBACK` note otherwise.
- `tests/test_realistic_lmstudio.py` + `tests/realistic_fixtures.py`: an
  opt-out integration suite (marker `lmstudio`, module-level 2s probe skips
  it when the server or an embedding model is unreachable) asserting, on
  REAL qwen embeddings over realistic prose: semantic recall with zero
  keyword overlap, cross-turn continuity across a topic detour, behavioral
  decay of the detour out of the emergent working set (membership, not
  score), indirect-cue reactivation with channel attribution, and
  byte-identical replay under a pinned `as_of`. An optional
  `lmstudio_llm`-marked test uses the local chat model as a yes/no judge
  over reconstructed digests and skips on timeout.
- pytest markers `lmstudio` / `lmstudio_llm` registered in `pyproject.toml`.

### Fixed (hostile-audit wave, 2026-07-06 — one entry per fix cluster)
1. Store thread safety + atomic add: `SQLiteTripleStore` now uses
   `check_same_thread=False` + an internal RLock around all cursor use, WAL,
   `busy_timeout=5000`, `synchronous=NORMAL`; `add()` is ONE explicit
   transaction using `INSERT OR IGNORE` (existing assertion ids are skipped —
   store-level id idempotency; failed batches roll back atomically, so
   partial rows can never leak into a later unrelated commit).
   `InMemoryTripleStore` gained the same lock + id-idempotent add.
2. Id-namespace boundary: every id-taking facade call (`commit_selection`,
   `reinforce`, `attenuate`, `activation`, `close_assertions`) accepts BOTH
   digest-assertion ids and graph ids (`records.resolve_assertion_ids`);
   unresolvable ids raise naming the id and both namespaces (graph-id calls
   used to be silent no-ops). New `MemorySystem.close_record` closes a
   record's digest AND edge assertions as one belief-revision act with
   deterministic closure ids.
3. Binding-fold correctness: hidden bindings are materialized against the
   store — they match candidates by assertion id OR subject (record-level
   bindings from `remember_many` finally enforce) and only within the
   binding's own `(scope, owner)` pair (no cross-pair veto). Handle `binding`
   reads the subject-level fold first.
4. Ordering contract: channel-matched candidates now order before unmatched
   ones (primary key), so boost-maxed or lesson-kind records with zero
   relevance can no longer outrank or budget-evict cue-matched records; kind
   priority applies among peers (shelf.py; C3 contract test extended with the
   audit's adversarial cases).
5. Edge-based Hebbian trails: `commit_selection` now also deposits
   `co_selected` trails over RECORDED edges between used formed records,
   keyed as the spreading hop pairs (source-digest↔edge, edge↔target-digest)
   — the term rule alone could never wire formed records and hand-planted
   digest-digest pairs could never match a traversal hop.
6. Exclusion-aware gathering: recents, exact patterns, the vector channel,
   and spreading neighbors over-fetch by `min(len(excluded), 256)` and filter
   closed/hidden rows BEFORE limits/caps, so accumulated closures can no
   longer starve fetch windows or shadow eligible older rows.
7. Budget-authoritative spreading: `RecallBudget.max_hops`/`max_edges`
   override `SpreadParams` directly (the silent `min()` clamp is gone;
   SpreadParams keeps weights/damping/fan-out/noise-floor); ablations disable
   the walk via an explicit `run_spreading` switch instead of zeroed params.
8. Edge assertions conduct, never member: `attributes.record_edge` rows are
   excluded from shelf/working-set membership and `listed` audits but remain
   fully walkable in spreading and visible in `result.edges`.
9. Vector floor: cosines below `ReconstructConfig.vector_floor` (default
   0.05) clip BEFORE max-normalization (a 0.02-cosine best hit can no longer
   normalize to 1.0); the all-clipped case warns
   "#FALLBACK: … below floor … no semantic signal".
10. Strict-JSON boundary: journal payload fields are sanitized at append in
    BOTH backends (seam `_jsonify` semantics; NaN/Inf → None with one
    `#FALLBACK` warning per batch); `json_dump` uses `allow_nan=False`;
    `MemoryEvent` rejects non-finite weights; `build_formation_plan`
    jsonifies provenance/attributes the same way.
11. Sharp edges: `ttl_activity <= 0` now raises (it silently inverted
    "expire asap" into "permanent"); unparseable `observed_at` raises at
    append (garbage timestamps corrupted the `seq_at` axis); the spreading
    fan-out cap keeps the most RECENT neighbors (observed_at desc) as its
    docstring always promised; the keyword tokenizer casefolds + NFKD
    accent-folds ('café'=='cafe') and labels zero-token non-Latin cues;
    `memj_snapshots(trace_id)` / `memj_events(trace_id)` are indexed.
    Attention scoring switched to PER-STEP clamping newest→oldest (fork
    parity, memory_control.rs:13615): fixes the silence-deadband — silences
    demote accumulated-newer use visibly; negative excess no longer builds an
    invisible hole that swallows older pins. (Semantic change; affected test
    expectations updated and documented.)
12. Determinism guard: `compute_activation`/`compute_trail_activation`
    reject events with journal-unassigned `seq < 0` (tied seqs made scores
    depend on caller list order).

### Added
- Pure-recency baseline arm (a2a 0002 follow-up; third experiment arm):
  `MemorySystem(..., ablation="recency")` — reconstruct serves "the most
  recent N that fit the budget" (chat-history baseline): channels disabled
  (relevance empty; stimulus cues/patterns/anchors ignored; reserved slots
  never engage), zero activation, no spreading, kind priority neutralized
  (ordering is observed_at desc with record_id tie-break), same
  budgets/shelf fill/token accounting; results and traces carry
  `ablation=recency (pure recency baseline)` plus a "channels disabled"
  note. Write paths stay live and closure/binding folds stay active (same
  read-side-only rationale as `"recency_embedding"`, which is unchanged).
- Caller-supplied `trace_id` on `reconstruct` (additive; end-to-end replay
  safety): supplying a trace_id derives the 'listed' audit event ids from it
  and dedupes the trace append by id — a re-call with the same trace_id
  writes ZERO new journal rows (first trace wins), and with
  `Stimulus(as_of=...)` pinned the result is byte-identical; combined with
  `commit_selection`'s trace_id idempotency, the RECALL→ACCESS pair replays
  end-to-end. `trace_id=None` keeps the exact prior behavior (fresh uuid4 +
  one audit trace per read). Trace records joined the journal supplied-id
  dedup in BOTH backends (UNIQUE-indexed in SQLite, same semantics as
  events/bindings/closures/snapshots).
- Formation write API v1 (a2a 0001/009 addendum 1 / 0001/011 ask 1; the
  minimal bridge to backlog 0021): `MemoryRecordInput` (10 kinds, validated;
  summaries require an edge) and `MemorySystem.remember_many(records, *,
  scope, owner_id, idempotency_key, turn_id=None)` (+ `remember`). Encoding
  (`records.py`): one literal digest assertion per record under
  `dcterms:abstract` (title/intents/outcomes/keywords/payload_ref/topic in
  attributes; reserved keys win) plus one plain assertion per edge; all ids
  derive from `(idempotency_key, position)` so replays are no-ops (store
  pre-check + journal binding dedup; check-then-add documented `#FALLBACK`:
  single formation writer assumed until 0009's add_if_absent). Each record
  gets an indexed/inactive `ScopeBinding` (`lifecycle="inactive_candidate"`,
  `source="remember"`); no attention event is journaled — forming is not
  using (0018).
- Handle enrichment for formed records: `attributes.record_kind` drives
  `handle.kind` AND 0020 kind-priority ordering (`ReconstructConfig` moved to
  `records.py`, re-exported; default ranks lesson 0 → memory 9, unknown kinds
  fall back past the table), `attributes.title` replaces the "s p o" preview
  (same 120-char bound), `payload_ref` upgrades `payload_tiers` to
  `("digest", "raw")`, and `provenance["record_id"]` exposes the graph id
  (`ex:{kind}-…`) so hosts can correlate recalls with formation results.
- `payload(record_id, tier="raw")` now serves the host verbatim reference:
  `{payload_ref, content: None}` when `attributes.payload_ref` exists (the
  runtime resolves it against its ArtifactStore; the package never fetches),
  `ValueError` otherwise; record ids resolve via their digest assertion
  (subject + `dcterms:abstract`), plain assertion ids directly.
- Write-side replay idempotency (a2a 0001/011 asks 2–3; runtime effects run
  at-least-once): caller-supplied ids are idempotency keys in BOTH journal
  backends — re-appending an existing event/binding/closure/snapshot id is a
  no-op returning the original record (original seq; selected-count
  untouched), with migration-safe `UNIQUE` indexes per id column in
  `SQLiteJournal` as the durable backstop. Journal-assigned ids never
  conflict; traces are exempt (fresh uuid4 per read; recalls replay from the
  runtime ledger).
- `commit_selection` is now idempotent by `trace_id`: a replayed commit
  returns the existing snapshot unchanged (a differing used set warns
  `#FALLBACK`), and all event/snapshot ids derive deterministically from
  `(trace_id, kind, canonical key)` (`selection.py`), so a crash between the
  event appends and the snapshot append replays as journal-level no-ops with
  the same events↔snapshot linkage.
- `Stimulus.turn_id` (additive, a2a 0001/011 ask 4): normalized optional turn
  identity; flows into `ReconstructionTrace.need` and `listed` audit event
  provenance. Not part of the query fingerprint (provenance, not retrieval
  content).
- Payload-tier stub (a2a 0001/009 item 2 / 0001/011 ask 6):
  `MemoryHandle.payload_tiers` (additive, default `("digest",)`) and
  `MemorySystem.payload(record_id, tier="digest")` — digest serves the
  canonical text; `raw`/`summary`/`compact` raise `NotImplementedError`
  naming backlog 0021 and the `attributes.payload_ref` interim.
- Topic surfacing (a2a 0002/001 q3): a string `topic` attribute on an
  assertion is promoted to `MemoryHandle.provenance["topic"]` for the
  emergence experiment's focus-coherence metric.
- Arm-B ablation switch (a2a 0002/001 q1, construction flag):
  `MemorySystem(..., ablation="recency_embedding")` makes `reconstruct` read
  with zero activation, no trails, and spreading disabled (edges empty in
  both views) under identical budgets/serialization, labeling results and
  traces with `ablation=recency_embedding (Arm B)`. Write paths
  (`commit_selection`, deliberate acts) stay live so both arms build
  identical journal histories; closure/binding folds stay active (the
  ablation disables activation, not belief lifecycle).
- Scope-binding enforcement in `reconstruct` (backlog 0017): the facade folds
  `ScopeBinding` events ≤ as_of per searched (scope, owner); records whose
  latest binding is `search_state="hidden"` leave ranked retrieval (id-lookups
  still bypass the fold — audit completeness), and `MemoryHandle.binding` now
  reports the honest folded `"{search_state}+{prompt_state}"`
  (`"indexed+inactive"` remains the documented default for unbound records).
  `run_reconstruction` gained a compatible `bindings` mapping parameter
  (default empty).
- Package-root exports for the memory-system surface (`MemorySystem`, seam
  dataclasses, journal records/protocol/backends, `AttentionConfig`,
  `SpreadParams`, `canonical_text`); `__all__` is sorted and export-tested.
  `lancedb` stays a lazy dependency (unchanged behavior).
- Seam contract regression suite (`tests/test_seam_contracts.py`): one test per
  frozen stability contract from a2a 0001/004 — journal purity/audit inertness,
  commit-only strengthening, relevance-admits/activation-reorders (+ boost
  cap), as_of byte-identical replay, `#FALLBACK`-labeled degradations. The
  import-boundary test now scans every module (no abstractcore/abstractruntime
  imports anywhere).

- `MemorySystem` facade (backlog 0024/0027, frozen seam v1 from a2a thread 0001):
  `abstractmemory.system.MemorySystem` wires store + journal + attention +
  reconstruction behind the negotiated runtime⇄memory surface — `reconstruct`
  (as_of-anchored activation/trails/closure folds, broad-scope escalation guard,
  optional trace + inert `listed` audit journaling), `commit_selection` (the only
  strengthening path: `selected` + term-sharing `co_selected` pair trails +
  `ActiveMemorySnapshot`), `reinforce`/`attenuate`/`refocus` wrappers,
  `activation`/`seq_at`/`current_seq` inspection, `close_assertions`, `bind`,
  and layer-1 `add`/`query` passthroughs. Selector/reflector are accepted but
  unused in v1 (`#FALLBACK` warning at construction; heuristic shelf only).
- `MemoryJournal.traces(trace_id=None, limit=100)` reader on the protocol and
  both backends (newest first, mirroring `snapshots()`); reconstruction traces
  were previously write-only.
- Reconstruction pipeline v1 (backlog 0019/0020/0026): `reconstruct.run_reconstruction`
  — a pure read that turns a `Stimulus` into a budgeted, explained shelf/working-set
  (`ReconstructionResult` + `ReconstructionTrace`), with channels + max-fusion +
  reserved slots, spreading activation, activation-aware ordering, and greedy
  token-budgeted shelf fill. Activation inputs are injected; no journal I/O.
- `channels.py`: exact (patterns + anchors), keyword (labeled `#FALLBACK` token
  scan until FTS5), and vector (store/embedder cosine, max-normalized 0..1)
  channel primitives.
- `spreading.py`: bounded, deterministic spreading activation over v1 record
  semantics (assertions are the records; shared entity terms are the edges),
  with fan-out cap, damping, per-predicate weights, co-selection trail boost,
  hard edge budget, and cycle termination.
- `canonical_text.py`: shared canonical-text function (`CANONICAL_TEXT_VERSION = 1`)
  replicating the store-internal `_canonical_text` byte-for-byte; golden tests pin
  parity across all three stores until they migrate to the shared module.

### Changed
- `ActiveMemorySnapshot.seq` now defaults to `-1` (journal-assigned sentinel,
  matching every journal record; field order and JSON shape unchanged).
- `system.py` fold logic moved to `folds.py` (activation inputs, closure
  exclusions, binding states) to keep files under the 600-line rule; shared
  `display_title`/`token_estimate` helpers live in `canonical_text.py` so the
  facade and pipeline cannot drift.

### Notes
- Reasoning: the runtime⇄memory seam (a2a thread 0001, frozen seam v1) needs one
  reconstruction call with two views; keeping the pipeline pure (store reads only,
  injected activation) preserves the replay contract (`as_of_seq`) and lets the
  facade (backlog 0024) own journaling, selectors, and closure/visibility folds.
- Facade replay semantics: `Stimulus.as_of` anchors journal-derived signals
  (activation, pair trails, closure exclusions, binding visibility); store truth is read current
  (stores have no seq axis yet) — the runtime replays primarily from its own
  ledger (a2a 0001/005). Anchors outside the journal's issued range raise
  instead of silently meaning "latest".

## [0.2.6] - 2026-05-09

### Changed
- The `test` optional dependency now installs `lancedb` so release CI exercises
  the persisted LanceDB store contract instead of skipping it.

### Fixed
- `LanceDBTripleStore` now recognizes the current LanceDB `list_tables()`
  response shape, restoring persisted table reopen/query behavior.

## [0.2.5] - 2026-05-08

### Added
- Added GitHub Actions CI for Python 3.10 through 3.12 with pytest and package
  build checks.
- Added a trusted-publishing release workflow for tagged or manually dispatched
  releases, including version/changelog validation, distribution artifacts,
  PyPI publication, and GitHub Release creation.
- Added an AbstractMemory GitHub bug report template.
- Added a `test` optional dependency extra for CI and release validation.

## 0.2.4 - 2026-05-08

### Added
- Added install-profile compatibility extras:
  `AbstractMemory[apple]`, `AbstractMemory[gpu]`,
  `AbstractMemory[all-apple]`, and `AbstractMemory[all-gpu]`.
- Planned backlog overview and standalone items for semantics-aligned memory records, SQLite compatibility/store capabilities, bounded graph traversal, recall traces, lineage, deterministic anchors, and read-only observer contracts.

### Changed
- `AbstractMemory[all-apple]` and `AbstractMemory[all-gpu]` now install the
  LanceDB-backed vector-capable store dependency, matching the existing
  `lancedb`/`all` profile behavior.
- `AbstractMemory[apple]` and `AbstractMemory[gpu]` remain no-op aliases
  because Memory itself has no hardware-specific runtime engine.
- Docs: clarify AbstractFramework ecosystem positioning, update PyPI install wording, and add a gateway-managed embeddings example.
- Docs: align README/API/store/FAQ/agent context with the exported `SQLiteTripleStore` and clarify semantic-query support by backend.
- Docs: document current release-channel drift between this source tree, PyPI, and remote tags.

### Fixed
- Test configuration now declares the local `basic` marker.
- `LanceDBTripleStore` avoids the deprecated LanceDB `table_names()` API when `list_tables()` is available.

## 0.0.2 - 2026-02-04

### Added
- User-facing documentation set with getting started, API, stores, architecture diagram, and FAQ.
- Agent-oriented context files: `llms.txt` and `llms-full.txt`.

### Changed
- `LanceDBTripleStore` non-semantic queries now apply `order` by `observed_at` before applying `limit` (deterministic behavior aligned with `InMemoryTripleStore`).

### Fixed
- Ordering/limit interaction for non-semantic queries in `LanceDBTripleStore` (covered by new tests).

## 0.0.1 - 2026-01-12

### Added
- `TripleAssertion` and `TripleQuery` data models.
- `InMemoryTripleStore` (dependency-free) and `LanceDBTripleStore` (optional).
- `AbstractGatewayTextEmbedder` adapter for gateway-managed embeddings.
