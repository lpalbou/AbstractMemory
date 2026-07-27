"""Night review of identity-amendment proposals (dm#124 + the R2 fold).

Runtime's realize fence forms kind="realization" records — the entity's
own mid-turn/look-back realizations about the self, held for sleep:
his words verbatim, `derived_from` edges naming the evidence, INERT on
formation. This module is the REGISTRAR half memory owes on that seam
(c4802/c4817), under the ruling's hard line:

    THE REGISTRAR NEVER AUTHORS. Subconscious-formed proposals are
    SURFACE-ONLY — adoption is the entity's waking act (dm#124: the
    provenance bar "on day X I DECIDED Y" cannot be truthfully completed
    by a matcher matching). Sleep REVIEWS and REPORTS; it never promotes,
    never rejects, never rewrites.

So `identity_review_pass` is a PURE READ: it folds the pending set
(formed, believed, lifecycle still undisposed) and checks the BARS a
proposal must hold to stay serviceable — today exactly one mechanical
bar, evidence-alive (every `derived_from` evidence record still resolves
and is still believed; a proposal whose evidence was retracted from
under it must SAY so before anyone adopts it). Verdicts are pull-visible
by construction: enactment rides journal lifecycle bindings (see
`disposal.enact_realization`), so "pending" stays a pure query — the
same fold `cognition_health` runs for miner candidates.

WIRE CONTRACT (runtime c4802, corrected c4817): enactment is NEVER an
attribute mutation on the resting proposal (append-only law) — it is a
lifecycle="promoted" binding PLUS a `derived_from` edge from the
supersession record back to the proposal; `enacted_at` rides the
binding provenance and the edge attributes (fresh rows, append-only
legal). Rejection reuses `disposal.reject_candidate` verbatim.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .folds import binding_states, closure_exclusions
from .store import TripleQuery

__all__ = ["identity_review_pass"]

# Lifecycles that mean "the entity already disposed of this proposal".
DISPOSED_LIFECYCLES = frozenset({"promoted", "rejected", "superseded"})


def identity_review_pass(
    system: Any, *,
    scopes: Sequence[Tuple[str, str]], owner_id: str,
) -> Dict[str, Any]:
    """The pending identity-amendment proposals and their bar states —
    one report, deposits nothing, writes nothing (module docstring
    carries the ruling and the wire contract).

    Shape: {pass_name, unit, pending: [{record_id, title, formed_at,
    session_id?, phase?, evidence: {unit, total, alive}, bar_failures:
    [sentence...]}], counts: {pending, bars_failing, disposed},
    provenance}. Every count says what it counts (the 0043 consumer
    contract); bar failures are plain sentences naming the mechanism.
    """
    store, journal = system.store, system.journal
    as_of = int(journal.current_seq())
    excluded = set(closure_exclusions(journal, as_of))

    pairs: List[Tuple[str, str]] = []
    for scope, owner in scopes:
        pair = (str(scope).strip().lower(), str(owner).strip())
        if pair not in pairs:
            pairs.append(pair)

    lifecycle_of: Dict[str, str] = {}
    for scope, owner in pairs:
        _states, hidden, _active = binding_states(store, journal, [(scope, owner)], as_of)
        excluded |= set(hidden)
        for b in journal.bindings(scope=scope, owner_id=owner, fold=True):
            lifecycle_of[b.record_id] = b.lifecycle

    # One scan per pair: realization digest rows + their outgoing edges
    # (the evidence currency). Distinct by subject across pairs.
    proposals: Dict[str, Any] = {}
    edges_out: Dict[str, List[Any]] = {}
    for scope, owner in pairs:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_edge"):
                edges_out.setdefault(str(a.subject), []).append(a)
                continue
            if attrs.get("record_kind") == "realization":
                proposals.setdefault(str(a.subject), a)

    pending: List[Dict[str, Any]] = []
    disposed = 0
    bars_failing = 0
    for rid in sorted(proposals):
        a = proposals[rid]
        if a.assertion_id in excluded or rid in excluded:
            disposed += 1  # closed = disposed by closure (retract/supersede)
            continue
        lifecycle = lifecycle_of.get(rid, "inactive_candidate")
        if lifecycle in DISPOSED_LIFECYCLES:
            disposed += 1
            continue

        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        evidence_edges = [e for e in edges_out.get(rid, ())
                          if str(e.predicate) == "derived_from"]
        alive = 0
        failures: List[str] = []
        for edge in evidence_edges:
            target = str(edge.object)
            # BOTH id namespaces resolve (adversary P1-1, the facade
            # contract): recall hands hosts ROW ids and edge targets are
            # not normalized at formation — a row-id evidence edge must
            # not read as a false "no longer resolves".
            from .records import resolve_digest_assertion
            t = resolve_digest_assertion(store, target)
            if t is None:
                failures.append(
                    f"evidence record {target} no longer resolves — the "
                    "proposal cites a record this store does not hold")
                continue
            if (t.assertion_id in excluded or str(t.subject) in excluded
                    or target in excluded):
                failures.append(
                    f"evidence record {target} was closed after the proposal "
                    "formed — re-verify before adopting (the realization may "
                    "rest on retracted ground)")
                continue
            alive += 1
        if not evidence_edges:
            # The producer refuses evidence-free formation (runtime's fence),
            # so this names historical/foreign rows honestly rather than
            # trusting the invariant transitively.
            failures.append(
                "no derived_from evidence edges — an evidence-free proposal "
                "cannot clear the adoption bar (producer contract violation "
                "or a pre-contract row)")

        if failures:
            bars_failing += 1
        entry: Dict[str, Any] = {
            "record_id": rid,
            "title": str(attrs.get("title") or ""),
            "formed_at": str(a.observed_at or ""),
            "evidence": {"unit": "records", "total": len(evidence_edges),
                         "alive": alive},
            "bar_failures": failures,
        }
        for key in ("session_id", "phase"):
            if attrs.get(key):
                entry[key] = str(attrs[key])
        pending.append(entry)

    return {
        "pass_name": "identity_review_pass",
        "unit": "records",
        "pending": pending,
        "counts": {"pending": len(pending), "bars_failing": bars_failing,
                   "disposed": disposed},
        "provenance": (
            "pure read — the registrar never authors (dm#124: adoption is "
            "the entity's waking act); pending = formed + believed + "
            "lifecycle undisposed (the candidates fold); verdicts ride "
            "disposal.enact_realization / disposal.reject_candidate"),
    }
