# Proposed: mind_mass_report() — the mind-health card's engine half

## Metadata
- Created: 2026-07-13
- Status: Proposed
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None

## Context
The rogue-embedder incident (recall failure from a misconfigured
embedding model) and the 92MB duplicate mass were both invisible until
forensic scripts ran. The observer redesign asked every seat for its
glance questions; memory's operator answer was "is this mind healthy?" —
one card. This item is the engine read behind that card; it absorbs the
0031-7 census shape (per the 0036 merge).

## Current code reality
`maintenance_report` scans duplicates/gaps; embedder pin lives in the
store meta; unresolved dreams and review-queue depth have reads;
compaction history (archive refs) now lives in `triples_meta` (doctoring
wave). Nothing composes them, and nothing curves formation cadence.

## Problem or opportunity
Chronic problems (mass accumulation, embedding skew, unread review
queues) surface only at incident scale.

## Proposed direction
`mind_mass_report(store, journal, *, scopes, days=30, bucket="day",
since_seq=0)` — pure read: formation-by-kind/day,
journal-events-by-family/day, per-pair growth, duplicate-cluster count
(from `maintenance_report`'s general scan; `wake_cue_dedup_pass(
report_only=True)` contributes the wake-cue sub-count labeled by source),
embedder pin vs wired embedder, unresolved dreams, review-queue depth,
last sleep pass, journal size vs newest compaction archive_ref.
Window-bounded mandatory (24/7 residents produce ~5k envelopes/day).

## Why it might matter
The daily glance that would have caught both named incidents before they
needed surgery; the operator's care question answered mechanically.

## Promotion criteria
Maintainer acceptance; the observer redesign's System/board surface
wanting the card is the natural trigger.

## Validation ideas
Castor-backup drive: the report must show the wake-cue mass curve and the
duplicate clusters the census found by hand; bounded-window perf at
real scale.

## Non-goals
Never doctoring's closure semantics as the general counter; no writes;
no thresholds that alert on their own (presentation only).

## Guidance for future agents
Reuse maintenance/doctoring reads; label every sub-count by source.
