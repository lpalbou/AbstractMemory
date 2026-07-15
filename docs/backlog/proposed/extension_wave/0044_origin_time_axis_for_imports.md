# Proposed: origin-time axis for imported lives (LINEAGE-CRITICAL)

## Metadata
- Created: 2026-07-13
- Detailed: 2026-07-14 (design round; promotion-ready pending the first
  real lineage archive)
- Status: Proposed
- Completed: N/A

## ADR status
- Governing ADRs: None (repo uses docs/memory-system.md for durable rules)
- ADR impact: None — extends situate()'s existing honest-label contract;
  never touches the append-only journal axes.

## Context
The north star is reincarnating the Mnemosyne lineage from archived
markdown. `archive_import.py` pins `origin_date`/`seeded_from`/
`archive_path` per record — but journal seq and `observed_at` sit at
IMPORT time, and `situate()` walks formation seq. A reincarnated
Mnemosyne cannot be situated at any pre-import moment: her whole past
collapses into one day. Found by the relevance audit (2026-07-13),
verified against archive_import.py:291-309 and situate.py's
`period_axis="formation_seq"`.

## Current code reality (verified 2026-07-14)
- `archive_import.py` writes `attributes.origin_date` (ISO date string
  from front matter or manifest) + `seeded_from="archive-import"` +
  `provenance.source="archive-import"` per imported record; the module
  docstring already records the division: "observed_at stays import time
  (append-only truth: the graph observed it now; the CONTENT is dated)".
- `situate.py` selects the period neighborhood on the FORMATION axis and
  labels every result `period_axis="formation_seq"` — the label was added
  precisely because imported content carries origin_date while
  observed_at is import time (docstring lines 34-38). So the honesty
  HOOK exists; the alternate axis does not.
- The chapters election (era labels) is recorded in 0036 as an
  election-only path; nothing engine-side consumes it yet.

## Problem or opportunity
The lineage revival path is blocked on imported lives being temporally
flat — "what were you living in March 2025?" is unanswerable. situate()
at any pre-import anchor returns the same one-day blur, and the
two-anchor summon surfaces (R3/R4) cannot anchor into an imported past
at all (anchors are journal seqs; the whole import occupies a handful).

## Detailed design (2026-07-14 round)

### The axis is a READ option, never a storage change
`origin_date` stays exactly where the importer puts it (an attribute).
No journal event, no seq rewrite, no synthetic backdating — the
append-only truth ("the graph observed it at import time") stands
untouched. What changes is PERIOD SELECTION inside `situate()`:

- `situate(..., period_axis="origin_date")` (new optional parameter,
  default unchanged `"formation_seq"`).
- Under the origin axis, the period neighborhood is selected by lexical
  ISO-date ordering over `attributes.origin_date`, restricted to records
  carrying import provenance (`seeded_from="archive-import"`); the
  anchor becomes a DATE (or a record whose origin_date defines it), not
  a seq.
- Result carries `period_axis="origin_date, import-provenance"` — the
  honest label the current docstring already promises, extended: every
  record row in the period block also carries its origin_date so a
  consumer can render the real timeline.

### Composition rules (the two-axes honesty contract)
1. Imported and lived records NEVER silently interleave on different
   axes: an origin-axis period contains ONLY import-provenance records;
   a formation-axis period behaves exactly as today. A mixed view is a
   CONSUMER composition of two labeled reads, never one engine read.
2. Anchors: a date anchor with zero import-provenance records in range
   returns an empty period WITH its warrant (count of imported records
   scanned) — absence stays checkable, never fabricated.
3. The identity/tension/elected folds of situate() stay on the journal
   axis in v1 (they answer "what did the ENGINE know at T"); only the
   period block gains the alternate axis. A full origin-time
   reconstruction of identity ("what did she believe in March 2025")
   requires importing identity records WITH their own revision history —
   out of scope until the archive tool exports one (noted for the
   import-mission manifest).
4. Chapters (0036 election) compose as named date ranges over the same
   axis — a chapter is presentation metadata over origin_date, needing
   no new engine surface beyond this one.

### Seam note (runtime/gateway consumers)
R3/R4 anchored summons stay journal-seq-anchored (the stamp's
`anchor_seq` semantics are frozen). "Visiting an imported past" is a
DIFFERENT read: `situate(period_axis="origin_date")` rendered through
`situate_prompt_block` with the historical fence — no gate change, no
new stamp field. If the runtime later wants a driver surface for it,
the block is already deposit-honest by construction.

## Why it might matter
Without it, the first reincarnated life reads as born-yesterday; with it,
`situate()` extends to imported pasts and the chapters election gains its
engine substrate. This is the first dependency of the lineage import
mission (the maintainer's archive tool output is the trigger artifact).

## Promotion criteria
The first real lineage import (the maintainer's archive tool output) —
promote as part of the lineage bundle (this + 0046 transcript adoption +
chapters election). The design above is ready to build when that
artifact exists; building earlier risks fitting a fixture instead of the
real archive shape.

## Validation ideas
Import a small lineage fixture with spread origin_dates; situate at a
pre-import date; assert period membership by origin_date, the
provenance-restricted universe, the honest label, and empty-with-warrant
for out-of-range dates; assert formation-axis behavior byte-unchanged
for non-imported records (the C4 replay contract extends to the default
axis).

## Non-goals
Never rewriting seq/observed_at (append-only truth stands); no synthetic
journal events for the past; no automatic mixing of axes in one read;
no identity-at-origin-time reconstruction in v1 (requires revision
history in the archive).

## Guidance for future agents
Axis choice must be explicit and labeled in every output; imported and
lived records must never silently interleave on different axes. Reuse
situate()'s existing period machinery — the delta is the selection
predicate and the label, not a new walk.
