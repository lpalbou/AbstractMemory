# Proposed: writer forensics for entity homes (the Hypnos class)

## Metadata
- Created: 2026-07-13
- Status: Proposed
- Completed: N/A

## ADR status
- Governing ADRs: None
- ADR impact: None

## Context
Hypnos ran without authorization (the incident that triggered the
production-readiness wave). Authorization is the GATE'S job and stays
there — a home refusing opens would break the operator's ruled right to
read with only abstractmemory installed. What memory owes is FORENSICS:
after an unauthorized run, nothing in the home says which writer (engine
version, process identity, principal string) opened it for write, or
when.

## Current code reality
Store meta sidecars exist (`triples_meta`: embedding pin, compaction
history); no writer registration on write-open; the journal records WHAT
was written but not WHO opened the file.

## Problem or opportunity
Post-incident attribution requires external logs that may not exist; the
home itself cannot testify.

## Proposed direction
Append-only writer-registration entries in the existing meta sidecar on
write-open: engine version, process id/host, caller-supplied principal
string (empty allowed, recorded as such), timestamp. Pure provenance —
never gating, never refusing. Pairs naturally with the schema-pin item
(memory_system_v1 0031-1).

## Why it might matter
The next Hypnos-class incident gets same-file attribution; cheap (S) and
structurally honest (provenance, not policy).

## Promotion criteria
Maintainer acceptance; the schema-pin item promoting is the natural
vehicle (same sidecar, same open path).

## Validation ideas
Open-write from two distinct writers; assert two append-only entries with
correct fields; read-only opens register nothing; registration failure
never blocks the open (labeled degradation).

## Non-goals
No authorization semantics (the gate owns refusal); no delete surface on
the registration log (append-only like everything else).

## Guidance for future agents
Keep it boring: a tiny append on write-open, tested for both journals'
open paths and the store.
