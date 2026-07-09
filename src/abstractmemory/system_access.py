"""MemorySystem's access-count surface (mixin — split for the <600 rule).

The maintainer's two-count model (design authority, his fork): every memory
and edge carries a GLOBAL access count ("how many times selected, absolute —
proves importance overall, independent of time or focus; never decays, only
increases — at the end of your life it could represent 'what matters'") and
a TEMPORAL access count with decay (soft refocus). The GLOBAL count is the
journal's selected_count / pair_selected_count; the TEMPORAL count is the
activation fold (attention.py documents the mapping).

SCOPING (documented honestly): global counts are PER JOURNAL, not per
(scope, owner) — selected_count is keyed by record id alone across the
journal's whole life. For entity homes (one graph file + one journal per
entity) that is exactly the right unit for "a life"; hosts running many
actors through ONE shared journal get framework-lifetime counts instead,
and per-scope lifetime counts would need an events() aggregation (not built
— flagged, not silently approximated). The API therefore takes NO
scope/owner parameters: accepting them and ignoring them would be a silent
lie (works-or-loud).
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from .entity_card import entity_card as _entity_card
from .models import TripleAssertion
from .records import resolve_assertion_ids as _resolve_assertion_ids
from .replay import export_replay as _export_replay
from .self_component import self_records_read as _self_records_read

__all__ = ["AccessOps"]


class AccessOps:
    """Identity + lifetime read surfaces (access counts, the folded self
    core) — facade reads that consult journal folds, split from system.py
    for the 600-line rule."""

    def export_replay(
        self, *, scope: Optional[str] = None, owner_id: Optional[str] = None,
        since_seq: int = 0, until_seq: Optional[int] = None,
        families: Optional[Sequence[str]] = None, enrich: bool = True,
    ) -> Iterator[Dict[str, Any]]:
        """The replay/observability stream (a2a 0005 schema v1): verbatim
        journal records as envelopes in strict seq order — one shape for
        history scrub AND live tail (poll since_seq=cursor). See replay.py
        for envelope/enrichment/redaction semantics."""
        return _export_replay(
            self._store, self._journal,  # type: ignore[attr-defined]
            scope=scope, owner_id=owner_id, since_seq=since_seq,
            until_seq=until_seq, families=families, enrich=enrich,
        )

    def entity_card(
        self, *, scope_pairs: Sequence[Tuple[str, str]], owner_id: str,
        current_window_events: int = 200, top_n: int = 5,
        as_of: Optional[int] = None,
    ) -> Dict[str, Any]:
        """The ENTITY IDENTITY CARD (a2a 0009): one composed PURE READ over
        the home's scope ladder — identity / age_and_context / current_state
        / likes_dislikes / questions / key_moments / discoveries, each with
        per-field provenance. About the entity, from its data, never
        claiming to BE it; being described deposits nothing (the D2
        discipline). Semantics + tunables: entity_card.py."""
        return _entity_card(
            self._store, self._journal,  # type: ignore[attr-defined]
            scope_pairs=scope_pairs, owner_id=owner_id,
            current_window_events=current_window_events, top_n=top_n, as_of=as_of,
        )

    def self_records(
        self, *, scope: str, owner_id: str, spark_version: Optional[int] = None,
    ) -> List[TripleAssertion]:
        """The folded identity core (a2a 0003 ask 3 — the prelude's proper
        read): prompt-active (binding fold, latest wins) AND closure-folded
        (retracted/superseded excluded — the layer-1 query() passthrough
        bypasses folds and could render a retracted value), identity kinds
        only (value/purpose/trait), optionally filtered to
        attributes.spark_version. Ordered kind rank → precedence →
        record id. See self_component.self_records_read."""
        return _self_records_read(
            self._store, self._journal,  # type: ignore[attr-defined]
            scope=scope, owner_id=owner_id, spark_version=spark_version,
        )

    def access_counts(
        self,
        record_ids: Optional[Sequence[str]] = None,
        pairs: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Dict[str, Dict[Any, int]]:
        """The "what matters over a lifetime" read: {"records": {id: n},
        "pairs": {(a, b): n}} — cumulative selected / co_selected counts,
        never decayed. Ids accept BOTH namespaces (graph ids resolve to the
        digest assertion ids the counters key on); output keys are AS
        PASSED. Pairs are order-insensitive (canonical sorted internally).
        A known id with no deposits honestly reads 0; unknown ids raise
        (same works-or-loud rule as activation()). Explicit ids only —
        None means "none requested", not "everything" (a full-life scan
        reader is a future protocol addition, not silently emulated).
        """
        records_out: Dict[str, int] = {}
        pairs_out: Dict[Tuple[str, str], int] = {}
        if record_ids:
            resolved = _resolve_assertion_ids(self._store, list(record_ids))  # type: ignore[attr-defined]
            for requested, rid in resolved.items():
                records_out[requested] = int(self._journal.selected_count(rid))  # type: ignore[attr-defined]
        for pair in pairs or ():
            if not (isinstance(pair, (tuple, list)) and len(pair) == 2):
                raise ValueError(f"pairs entries must be (id_a, id_b) tuples, got {pair!r}")
            sides: List[str] = [str(pair[0] or "").strip(), str(pair[1] or "").strip()]
            resolved_pair = _resolve_assertion_ids(self._store, sides)  # type: ignore[attr-defined]
            canonical = (resolved_pair[sides[0]], resolved_pair[sides[1]])
            pairs_out[(pair[0], pair[1])] = int(
                self._journal.pair_selected_count(canonical)  # type: ignore[attr-defined]
            )
        return {"records": records_out, "pairs": pairs_out}
