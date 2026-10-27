# Change records with magnitude and the ripple primitives

## Summary
Give AbstractMemory the primitives that [ADR 0001](../../../adr/0001-altered-memories-ripple.md) requires from the
store and journal, so that a consumer's (or a future pass's) ripple can be computed, bounded and explained:
1. a change record per meaning-altering operation (memory id, what changed, measured magnitude, cause);
2. closure records that carry a cause (`source` memory id, `hops`) for closures made by a ripple;
3. an additive `narrow_assertion(assertion_id, valid_until)` (move an already-closed window earlier) so consumers stop
   writing the store's table directly (AbstractNote `store/kg.py` seam, 2026-10-20);
4. `maintenance_due` counting pending ripple sources as work due, largest magnitude first;
5. a read that answers "what may follow if A changes by m" (the bound) without running anything.

## Why
Operator ruling 2026-10-21: an altered memory must ripple to the memories that relied on it, evaluated hop by hop by
effect, iteratively, bounded and visible. Amended 2026-10-27 (ADR 0002): AbstractMemory owns the whole ripple; these
primitives are its first step, and the process itself is planned in
`planned/knowledge_graph_convergence/0054_ripple_propagation_and_activation.md`. AbstractNote's lane R6 (its ADR 0008)
is a prototype to absorb.

## Current code reality
`close_assertion` (0.3.1) and the closure kind `reinterpreted` (0.3.2) exist; closures carry `reason` text but no
structured cause; there is no change record and no magnitude; `maintenance_due` counts new records and fragments only;
`narrow_assertion` does not exist (AbstractNote writes `valid_until` through the store's private table).

## Scope
In: the five primitives above, additive, both store backends and the journal, docs (`api.md`, `memory-system.md`),
tests with mutants. Out: the propagation and reconsideration process (item 0054, also in AbstractMemory) and any text rule on content.

## Validation
Unit tests per primitive with mutants; a consumer-shaped scenario test (a type change on one memory produces a change
record, a ripple closure with cause, and a bound read) ; docs regenerated (llms-full).
