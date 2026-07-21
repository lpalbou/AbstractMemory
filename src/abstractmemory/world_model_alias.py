"""World-model aliasing: one understanding, many names (M3, 2026-07-18).

The maintainer's case verbatim: "identify and regroup the world model
entities (eg admin = laurent)". One human can arrive under several target
strings (person:admin at the door, person:laurent in prose); without a
fold the understanding SPLITS — two cards, two feeling streams, neither
complete. Aliasing repairs it in the append-only grammar:

- An alias is a DELIBERATE ACT (`alias_world_model`): the primary card
  gains `attributes.aliases` in a new revision; a standing card for the
  alias target (if any) is superseded INTO the primary. Never silent —
  the act carries a reason and an actor, like every belief revision.
- GROUPING honors aliases: evidence stamped with an alias lands on the
  primary's card at the next pass (the alias map normalizes targets).
- MENTION honors aliases: the primary card surfaces when ANY of its
  names is mentioned (participants or cue).
- The sleep pass PROPOSES, never merges: `alias_candidates` surfaces
  target pairs whose evidence overlaps heavily — waking review (operator
  or entity) confirms with the verb. The dream discipline applied to
  identity-of-others: proposals are candidates, lived confirmation
  decides. (The admin=laurent case itself is knowledge the OPERATOR
  holds, not evidence overlap — the verb is the load-bearing half.)

HONEST v1 LIMIT, stated: gradation streams stay per-target-string — the
feeling line on an aliased card reads the PRIMARY string's standing.
Appraisals should target the primary once the alias lands (the teaching
lane's sentence); folding historical valence across alias strings is a
separate ruled act if ever wanted, never an automatic rewrite.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .store import TripleQuery

__all__ = ["ALIAS_OVERLAP_FLOOR", "alias_candidates", "alias_map", "alias_world_model"]

# Evidence-overlap floor for a merge PROPOSAL (Jaccard over evidence sets).
# Declared tunable: high by design — a proposal accuses two names of being
# one thing; weak overlap is co-occurrence, not identity.
ALIAS_OVERLAP_FLOOR = 0.6


def _aliases_of(assertion: Any) -> List[str]:
    attrs = assertion.attributes if isinstance(assertion.attributes, dict) else {}
    raw = attrs.get("aliases")
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(a).strip() for a in raw if isinstance(a, str) and str(a).strip()]


def alias_map(
    store: Any, *, scope: str, owner_id: str, journal: Any = None,
) -> Dict[str, str]:
    """alias -> primary target, read from CURRENT cards' aliases attribute.
    Pure read; the map is derived state (the cards are the record)."""
    from .world_model import current_world_models

    out: Dict[str, str] = {}
    for target, card in current_world_models(
            store, scope=scope, owner_id=owner_id, journal=journal).items():
        for alias in _aliases_of(card):
            if alias != target:
                out[alias] = target
    return out


def alias_candidates(
    by_target: Dict[str, List[str]], *,
    existing: Optional[Dict[str, str]] = None,
    overlap_floor: float = ALIAS_OVERLAP_FLOOR,
) -> List[Dict[str, Any]]:
    """Merge PROPOSALS from evidence overlap: pairs of targets (same
    namespace) whose evidence sets share >= overlap_floor Jaccard and are
    not already aliased. Report data only — nothing forms, nothing closes;
    waking review confirms with alias_world_model. Deterministic order."""
    existing = existing or {}
    names = sorted(t for t in by_target if len(by_target[t]) >= 2)
    out: List[Dict[str, Any]] = []
    for i, a in enumerate(names):
        ns_a = a.split(":", 1)[0] if ":" in a else ""
        set_a = set(by_target[a])
        for b in names[i + 1:]:
            if (a in existing or b in existing
                    or existing.get(a) == b or existing.get(b) == a):
                continue
            ns_b = b.split(":", 1)[0] if ":" in b else ""
            if ns_a != ns_b:
                continue  # a person is never proposed as a topic's alias
            set_b = set(by_target[b])
            union = set_a | set_b
            if not union:
                continue
            jaccard = len(set_a & set_b) / len(union)
            if jaccard >= float(overlap_floor):
                out.append({
                    "targets": [a, b],
                    "overlap": round(jaccard, 4),
                    "shared_evidence": len(set_a & set_b),
                    "note": ("evidence overlap proposes one identity - confirm "
                             "with alias_world_model or leave standing (a "
                             "proposal is never a merge)"),
                })
    return out


def alias_world_model(
    system: Any, *, primary: str, alias: str,
    scope: str, owner_id: str, reason: str,
    actor: str = "operator",
) -> Dict[str, Any]:
    """Bind `alias` to `primary`'s card — the deliberate identity act.

    Mechanics (append-only): the primary card revises with the alias added
    (lead/words carried verbatim — an alias changes who the card is ABOUT
    in name-space, never what it says); a standing card for the alias
    target is superseded INTO the primary (its evidence regroups onto the
    primary at the next pass, since grouping normalizes through the alias
    map). Refusals are loud: no primary card, self-alias, alias already
    bound elsewhere, or empty reason (an identity claim is an audited act).
    """
    primary_n = str(primary or "").strip()
    alias_n = str(alias or "").strip()
    why = str(reason or "").strip()
    if not primary_n or not alias_n:
        raise ValueError("alias_world_model requires primary and alias targets")
    if primary_n == alias_n:
        raise ValueError("a target cannot alias itself")
    if not why:
        raise ValueError(
            "alias_world_model requires a reason — claiming two names are one "
            "identity is an audited act (the disposal-discipline rule)")

    from .world_model import current_world_models, _revision_of

    current = current_world_models(
        system.store, scope=scope, owner_id=owner_id, journal=system.journal)
    card = current.get(primary_n)
    if card is None:
        raise ValueError(
            f"no standing world-model card for primary {primary_n!r} — the "
            "identity being extended must exist first (run world_model_pass)")
    bound = alias_map(system.store, scope=scope, owner_id=owner_id,
                      journal=system.journal)
    if bound.get(alias_n) not in (None, primary_n):
        raise ValueError(
            f"{alias_n!r} is already aliased to {bound[alias_n]!r} — unbinding "
            "is its own deliberate act, never an overwrite")

    from .records import MemoryRecordInput

    attrs = dict(card.attributes if isinstance(card.attributes, dict) else {})
    aliases = sorted({*_aliases_of(card), alias_n})
    revision = _revision_of(card) + 1
    display = primary_n.split(":", 1)[1] if ":" in primary_n else primary_n
    known = [str(s) for s in (attrs.get("known_source_ids")
                              or attrs.get("source_ids") or ())]
    edges: List[Tuple[str, str]] = [
        ("derived_from", rid) for rid in list(reversed(known))[:8]]
    edges.append(("refines", card.subject))
    carried = {k: attrs[k] for k in (
        "evidence_fingerprint", "source_count", "known_source_ids",
        "first_seen", "last_seen", "digest_method",
        "authored_lead", "authored_known_ids", "authored_by",
    ) if k in attrs}
    new_card = MemoryRecordInput(
        kind="world_model",
        title=str(attrs.get("title") or f"World model: {display}"),
        digest=str(card.object or ""),
        keywords=tuple(str(k) for k in (attrs.get("keywords") or ())),
        participants=((primary_n, alias_n) if not primary_n.startswith("topic:")
                      else ()),
        edges=tuple(edges),
        attributes={
            "world_model": True,
            "target": primary_n,
            "revision": revision,
            "aliases": aliases,
            "alias_reason": why,
            **carried,
        },
        provenance={"source": "world-model-aliasing", "actor": str(actor or "")},
    )
    key = f"world-model-alias|{owner_id}|{primary_n}|{alias_n}|rev{revision}"
    [gid] = system.remember_many(
        [new_card], scope=scope, owner_id=owner_id, idempotency_key=key)
    closed: List[str] = []
    if card.subject != gid:
        system.close_record(
            card.subject, kind="supersede", replacement_ids=[gid],
            reason=f"alias {alias_n} bound to {primary_n} ({why})")
        closed.append(card.subject)
    # A standing card for the ALIAS target folds into the primary: one
    # identity, one card. Its history stays walkable (supersede, never
    # erasure); its evidence regroups onto the primary at the next pass.
    alias_card = current.get(alias_n)
    if alias_card is not None and alias_card.subject != gid:
        system.close_record(
            alias_card.subject, kind="supersede", replacement_ids=[gid],
            reason=f"{alias_n} aliased into {primary_n} ({why})")
        closed.append(alias_card.subject)
    return {"primary": primary_n, "alias": alias_n, "card_id": gid,
            "revision": revision, "aliases": aliases, "superseded": closed}
