"""MemorySystem's valence surface (mixin — split for the <600-line rule).

One task: the facade write/read paths for the valence family (a2a 0003 §3).
`MemorySystem` inherits `ValenceOps`; the methods use only the facade's own
substrate handles (`_journal`, `_clock`, `_gradation_config`). Pure
derivations live in gradation.py; record shapes in journal.py. NOTHING here
is reachable from reconstruct/shelf — valence never touches retrieval by
contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .gradation import (
    NEUTRAL_GRADATION,
    GradationConfig,
    compute_gradation,
    validate_amplitude_authority,
)
from .journal import ValenceEvent

__all__ = ["ValenceOps"]


class ValenceOps:
    """Appraise / heal / break / read-gradation facade methods (identity wave)."""

    def _valence_config(self) -> GradationConfig:
        # Threaded by MemorySystem.__init__ (review F2: the exported config
        # used to be constructed fresh here — unreachable tuning surface);
        # the getattr default keeps the mixin usable standalone in tests.
        return getattr(self, "_gradation_config", None) or GradationConfig()

    def appraise(
        self, target_id: str, *, sign: int, magnitude: float, reason: str,
        scope: str, owner_id: str, value_refs: Sequence[str] = (),
        scar: bool = False, bond: bool = False, event_id: Optional[str] = None,
        actor: str = "runtime", provenance: Optional[Mapping[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> List[str]:
        """Deposit one signed appraisal (optionally with an EXPLICIT standing
        marker written alongside — markers are never auto-created); returns
        the written event ids (appraisal first). target_id may be a record
        id OR a free identity string ("tool:web_search"). Amplitude
        authority: magnitude > 3 requires entity-reflection/operator
        actorship or a catastrophic outcome code. SYMMETRIC PEAKS
        (maintainer correction A): scar=True marks a standing −peak (caps
        presentation ≤ 0 until healed; requires sign=-1), bond=True marks a
        standing +peak (floors ≥ 0 until broken; requires sign=+1) — one
        appraisal is one peak, never both. Idempotent: a supplied event_id
        dedupes at the journal; markers ride as "{event_id}:scar" /
        "{event_id}:bond" so pair replays are no-ops too. Marker magnitude
        is the caller's judgment (typically >= 8 per the charter)."""
        validate_amplitude_authority(magnitude, actor, provenance, config=self._valence_config())
        if scar and bond:
            raise ValueError("one appraisal is one peak: scar=True and bond=True are mutually exclusive")
        if scar and sign != -1:
            raise ValueError("scar=True requires sign=-1 (a scar marks a NEGATIVE peak)")
        if bond and sign != 1:
            raise ValueError("bond=True requires sign=+1 (a bond marks a POSITIVE peak)")
        supplied = str(event_id or "").strip()
        now = self._clock()  # type: ignore[attr-defined]
        base = dict(provenance or {})
        events = [ValenceEvent(
            target_id=target_id, sign=sign, magnitude=magnitude, kind="appraisal",
            value_refs=tuple(value_refs or ()), scope=scope, owner_id=owner_id,
            reason=reason, actor=actor, trace_id=trace_id, observed_at=now,
            provenance=base, event_id=supplied,
        )]
        if scar or bond:
            marker = "scar" if scar else "bond"
            events.append(ValenceEvent(
                target_id=target_id, sign=sign, magnitude=magnitude, kind=marker,
                value_refs=tuple(value_refs or ()), scope=scope, owner_id=owner_id,
                reason=reason, actor=actor, trace_id=trace_id, observed_at=now,
                provenance=dict(base), event_id=(f"{supplied}:{marker}" if supplied else ""),
            ))
        return [e.event_id for e in self._journal.append_valence(events)]  # type: ignore[attr-defined]

    def _require_privileged_actor(self, actor: Any, *, verb: str) -> None:
        """Amplitude-authority discipline for the DELIBERATE valence verbs
        (entity-seat fable5 P0-1, 2026-07-25: heal_scar/break_bond engraved
        whatever actor a caller claimed while revalue validated — one rule,
        three verbs now). Healing a scar, breaking a bond, and rescaling
        accumulated experience are reflective acts: entity-reflection/
        operator actors only, exactly revalue's original rule."""
        config = self._valence_config()
        if str(actor or "").strip().lower() not in config.privileged_actors:
            raise ValueError(
                f"{verb} requires a privileged actor ({sorted(config.privileged_actors)}); "
                f"got {actor!r} — deliberate revaluation of standing experience "
                "is a reflective act, never a trigger's")

    def heal_scar(
        self, scar_event_id: str, *, reason: str, lesson_record_id: Optional[str] = None,
        scope: str, owner_id: str, event_id: Optional[str] = None,
        actor: str = "entity-reflection",
    ) -> str:
        """Resolve a standing scar (append-only: writes a healing event that
        references it; the scar row is never rewritten). The healing id
        defaults to "heal:{scar_event_id}" — deterministic, so replays are
        journal no-ops WITHOUT the caller supplying anything. lesson_record_id
        (the reflection's lesson record) rides provenance for the audit
        trail. Unknown scar ids raise (healing without a wound is a bug)."""
        sid = str(scar_event_id or "").strip()
        if not sid:
            raise ValueError("heal_scar requires a scar_event_id")
        self._require_privileged_actor(actor, verb="heal_scar")
        rows = self._journal.valence_events(scope=scope, owner_id=owner_id, limit=0)  # type: ignore[attr-defined]
        scar = next((e for e in rows if e.event_id == sid and e.kind == "scar"), None)
        if scar is None:
            raise ValueError(
                f"heal_scar: no scar event {sid!r} in ({scope!r}, {owner_id!r}) — "
                "healing must reference an existing standing scar"
            )
        provenance: Dict[str, Any] = {"heals": sid}
        if lesson_record_id:
            provenance["lesson_record_id"] = str(lesson_record_id).strip()
        [healed] = self._journal.append_valence([ValenceEvent(  # type: ignore[attr-defined]
            target_id=scar.target_id, sign=1, magnitude=scar.magnitude, kind="healing",
            scope=scope, owner_id=owner_id, reason=reason, actor=actor,
            observed_at=self._clock(),  # type: ignore[attr-defined]
            provenance=provenance,
            event_id=(str(event_id or "").strip() or f"heal:{sid}"),
        )])
        return healed.event_id

    def break_bond(
        self, bond_event_id: str, *, reason: str, scope: str, owner_id: str,
        event_id: Optional[str] = None, actor: str = "entity-reflection",
    ) -> str:
        """Dissolve a standing bond (append-only, symmetric to heal_scar):
        writes a kind="break" event referencing it via provenance["breaks"];
        the bond row is never rewritten. Deterministic default id
        "break:{bond_event_id}" — replays are journal no-ops. Unknown bond
        ids raise. (A betrayal-scale scar — magnitude >= 8 AFTER the bond —
        also breaks it without this call; see gradation.py.)"""
        bid = str(bond_event_id or "").strip()
        if not bid:
            raise ValueError("break_bond requires a bond_event_id")
        self._require_privileged_actor(actor, verb="break_bond")
        rows = self._journal.valence_events(scope=scope, owner_id=owner_id, limit=0)  # type: ignore[attr-defined]
        bond = next((e for e in rows if e.event_id == bid and e.kind == "bond"), None)
        if bond is None:
            raise ValueError(
                f"break_bond: no bond event {bid!r} in ({scope!r}, {owner_id!r}) — "
                "a break must reference an existing standing bond"
            )
        [broke] = self._journal.append_valence([ValenceEvent(  # type: ignore[attr-defined]
            target_id=bond.target_id, sign=-1, magnitude=bond.magnitude, kind="break",
            scope=scope, owner_id=owner_id, reason=reason, actor=actor,
            observed_at=self._clock(),  # type: ignore[attr-defined]
            provenance={"breaks": bid},
            event_id=(str(event_id or "").strip() or f"break:{bid}"),
        )])
        return broke.event_id

    def revalue(
        self, target_id: str, *, factor: float, reason: str,
        scope: str, owner_id: str, event_id: Optional[str] = None,
        actor: str = "entity-reflection",
    ) -> str:
        """Deliberate reappraisal (W4, the revaluation marker landed):
        rescale a target's accumulated channels by `factor` (0..1) from
        this point in the walk — "the past weighs less now". NEVER
        automatic, never decay: entity-reflection/operator actors only
        (the amplitude-authority channel discipline — a trigger rewriting
        history would be fabricated forgetting). Scars/bonds are NOT
        touched (they resolve via heal_scar/break_bond); later appraisals
        land at full weight. Append-only; the event carries the factor in
        provenance and the mandatory reason."""
        tid = str(target_id or "").strip()
        if not tid:
            raise ValueError("revalue requires a target_id")
        f = float(factor)
        if not (0.0 <= f <= 1.0):
            raise ValueError(
                f"revalue factor must be in 0..1 (got {factor!r}) — a factor "
                "above 1 would retroactively amplify past experience")
        self._require_privileged_actor(actor, verb="revalue")
        [row] = self._journal.append_valence([ValenceEvent(  # type: ignore[attr-defined]
            target_id=tid, sign=1, magnitude=1.0, kind="revalued",
            scope=scope, owner_id=owner_id, reason=reason, actor=actor,
            observed_at=self._clock(),  # type: ignore[attr-defined]
            provenance={"factor": f},
            event_id=str(event_id or "").strip(),
        )])
        return row.event_id

    def gradation(
        self, target_ids: Optional[Sequence[str]] = None, *,
        scope: str, owner_id: str, at_seq: Optional[int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Derived valence standing per target (dual-channel; see
        gradation.py): {net, positive, negative, positive_count,
        negative_count, scarred, bonded, contributions}. Requested targets
        with no events return NEUTRAL — free-string targets are legitimate
        and "never appraised" is a real answer, unlike activation's unknown
        record ids (which raise: those must exist in the store)."""
        anchor = int(at_seq) if at_seq is not None else self._journal.current_seq()  # type: ignore[attr-defined]
        events = self._journal.valence_events(  # type: ignore[attr-defined]
            scope=scope, owner_id=owner_id, until_seq=anchor, limit=0,
        )
        scores = compute_gradation(events, config=self._valence_config())
        if target_ids is None:
            return {tid: s.to_dict() for tid, s in scores.items()}
        out: Dict[str, Dict[str, Any]] = {}
        for requested in target_ids:
            tid = str(requested or "").strip()
            found = scores.get(tid)
            out[requested] = found.to_dict() if found is not None else dict(NEUTRAL_GRADATION)
        return out
