"""Tending elections: ONE fenced-block grammar giving a mind agency over its
own attention and emotional repair, parsed into engine verbs that already
exist (maintainer-accepted 2026-07-13: "agree in principle, it depends on
the implementation").

Until this module, only code could call reinforce / attenuate / refocus /
heal_scar / break_bond / dispose_dream / the payload+expand read pair — no
election surface reached them. The grammar IS that surface. The host driver
extracts the ```tend fence and hands the BODY here; one verb per line:

    pin: <record_id> — reason: <why this must stay near>
    silence: <record_id> — reason: <why this may recede>
    refocus: — reason: <the topic has shifted>
    heal_scar: <target_or_scar_event_id> — reason: <what changed>
    break_bond: <target_or_bond_event_id> — reason: <what broke>
    revisit: <record_id> — reason: <what I am looking for>
    dispose: <dream_record_id> confirm|reject [key=value …] — reason: <verdict>

Line grammar: `verb: <target> — reason: <text>` — em-dash, en-dash, or
double-hyphen separator; whitespace tolerated everywhere (the house
```feel/```diary tolerance: malformed lines become honest refusals, never
lost sessions). The reason is MANDATORY on every line: every underlying
engine verb is an audited act and refuses empty reasons — the grammar
refuses earlier, at parse, naming the rule.

Design rules (the maintainer's two inputs, honored):
(a) "a more controlled way for the entity to manage its emotions, attention
    and focus": pin/silence/refocus write the SAME deliberate attention
    events operators write (kind='pinned'/'silenced'/'refocus') — temporal
    access counts and edge trails stay the substrate; tending nudges them,
    never rewrites them. NOTE the engine's per-step clamp semantics
    (attention.py): a fresh silence on a saturated record floors at 0 and
    demotes via rank displacement; pairing silences WITH a refocus (the
    topic-shift stretch) is how previously unselected memories actually
    surface — the grammar offers both verbs so the entity can do exactly
    that in one block.
(b) "an ITERATIVE process… selecting first the closest nodes to our need,
    then letting it spread a bit, trying to find additional paths": the
    `revisit` verb is that iterative deliberate reach — see
    apply_tend_elections for the loop shape.

Hard contracts (grep-verifiable):
- ZERO new engine mutation paths: apply calls only the existing public
  facade surfaces (reinforce / attenuate / refocus / heal_scar / break_bond
  / dispose_dream / payload / probe_expand) plus read-only resolution
  (journal.valence_events, records.resolve_digest_assertion). This module
  never writes to a store or journal itself.
- Tend never deposits: no commit_selection call exists here; revisit is a
  pure read whose journal writes are the trace + inert audit events the
  existing probe surface already writes.
- Valence never gates recall; storage is never erased (silence is a nudge,
  closure/disposal remain the removal tools and dispose only composes them).
- Refusals are DATA returned to the caller (the driver shows them to the
  entity verbatim) — never exceptions. The single exception: an empty
  `actor` raises ValueError (words without an author are not elections).

Vocabulary neutrality: "tend" = tending elections over any memory system.
Nothing here is entity- or product-specific beyond the grammar keywords;
every knob (verb cap, spread bounds) is a parameter with a documented
default.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .journal import utc_now_iso
from .records import resolve_digest_assertion

__all__ = [
    "DEFAULT_MAX_ELECTIONS",
    "IDENTITY_SCOPE_PENDING_RULING",
    "TEND_VERBS",
    "apply_tend_elections",
    "parse_tend_block",
]

# The grammar's verb vocabulary (closed set — an unknown verb is a refusal,
# never a guess).
TEND_VERBS: Tuple[str, ...] = (
    "pin", "silence", "refocus", "heal_scar", "break_bond", "revisit", "dispose",
)

# Default per-block verb cap. A tending block is a deliberate, bounded act —
# the cap keeps one reply from rewriting a whole attention landscape; excess
# lines are refused naming the cap (the caller may raise it explicitly).
DEFAULT_MAX_ELECTIONS = 5

# Exact refusal text for identity-scope targets (records living in a "self"
# scope pair). Tending one's own identity records is a pending maintainer
# ruling — refused verbatim until ruled, so drivers surface one stable line.
IDENTITY_SCOPE_PENDING_RULING = (
    "identity-scope tending is pending the maintainer's ruling (Q2) — refused until ruled"
)

# The one channel apply accepts. The door may ALSO gate; refusing here keeps
# the contract visible at the engine boundary (same division as the deposit
# gate: enforcement at the door, a visible refusal in the engine).
_REFLECTION_CHANNEL = "entity-reflection"

# Targets that can never be graph records: book entry ids (both the book's
# "diary_" form and the "diary:" lookalike the reflection grammar reserves)
# and formation-batch locals. Refused as spoofs before any store lookup.
_SPOOF_TARGET_PREFIXES = ("diary_", "diary:", "local:")

# Verb line: "verb: rest". The separator regex splits "<middle> — reason:
# <text>" tolerating em-dash / en-dash / double-hyphen and any whitespace.
_VERB_LINE_RE = re.compile(r"^(?P<verb>[A-Za-z_]+)\s*:\s*(?P<rest>.*)$")
_REASON_SPLIT_RE = re.compile(r"\s*(?:\u2014|\u2013|--)\s*reason\s*:\s*", re.IGNORECASE)

_DISPOSITIONS = {"confirm": "confirmed", "reject": "dissolved"}
# Optional key=value extras on a dispose line, mapped to dispose_dream's
# kwargs. Confirming a dream REQUIRES relation/source/target/evidence
# (disposal.py: waking evidence disposes); the extras are how a single
# election line can carry them.
_DISPOSE_EXTRA_KEYS = {
    "relation": "relation",
    "source": "source_id",
    "target": "target_id",
    "evidence": "evidence_ids",
}


def _refusal(line: str, reason: str) -> Dict[str, str]:
    return {"line": line, "reason": reason}


def _parse_dispose_middle(middle: str, line: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, str]]]:
    """Parse "<dream_id> confirm|reject [key=value …]" → (fields, refusal)."""
    tokens = middle.split()
    if len(tokens) < 2:
        return None, _refusal(
            line, "dispose requires a dream record id AND a disposition "
                  "(confirm|reject): `dispose: <dream_id> confirm|reject — reason: …`")
    target, disposition = tokens[0], tokens[1].lower()
    if disposition not in _DISPOSITIONS:
        return None, _refusal(
            line, f"unknown disposition {tokens[1]!r} — dispose takes confirm "
                  "(waking evidence holds) or reject (the association does not hold)")
    args: Dict[str, Any] = {}
    for extra in tokens[2:]:
        key, sep, value = extra.partition("=")
        if not sep or not value:
            return None, _refusal(
                line, f"malformed dispose argument {extra!r} — extras are key=value "
                      f"(known keys: {', '.join(sorted(_DISPOSE_EXTRA_KEYS))})")
        if key not in _DISPOSE_EXTRA_KEYS:
            return None, _refusal(
                line, f"unknown dispose argument {key!r} — known keys: "
                      f"{', '.join(sorted(_DISPOSE_EXTRA_KEYS))} (nothing is dropped silently)")
        kwarg = _DISPOSE_EXTRA_KEYS[key]
        args[kwarg] = tuple(v for v in value.split(",") if v) if kwarg == "evidence_ids" else value
    return {"target": target, "disposition": disposition, "args": args}, None


def parse_tend_block(text: str, *, max_elections: int = DEFAULT_MAX_ELECTIONS) -> Dict[str, List[Dict[str, Any]]]:
    """Parse one ```tend block BODY into elections + refusals (both data).

    The caller (driver) extracts the fence; this parses the body, one verb
    per line. Blank lines and stray fence lines (```…) are skipped; every
    other unusable line becomes a refusal carrying the VERBATIM line and the
    rule it broke — the driver shows refusals to the author unedited.

    Parse refusals: unknown verb; missing/empty reason (mandatory on every
    line); malformed target (missing where required, present on refocus,
    several where one is expected, malformed dispose extras); elections
    beyond `max_elections` (default DEFAULT_MAX_ELECTIONS = 5), refused
    naming the cap.

    Returns {"elections": [...], "refusals": [...]}. Election dicts carry
    verb/target/reason/line (+ disposition/args for dispose) and feed
    apply_tend_elections unchanged.
    """
    cap = int(max_elections)
    if cap < 1:
        raise ValueError(f"max_elections must be >= 1, got {max_elections!r}")
    elections: List[Dict[str, Any]] = []
    refusals: List[Dict[str, str]] = []

    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("```"):
            continue  # blank / stray fence noise: not an election, not a refusal
        m = _VERB_LINE_RE.match(line)
        if not m:
            refusals.append(_refusal(
                line, "unparseable line — expected `verb: <target> — reason: <text>` "
                      f"with verb one of: {', '.join(TEND_VERBS)}"))
            continue
        verb = m.group("verb").lower()
        if verb not in TEND_VERBS:
            refusals.append(_refusal(
                line, f"unknown verb {m.group('verb')!r} — the tending vocabulary is: "
                      f"{', '.join(TEND_VERBS)}"))
            continue
        parts = _REASON_SPLIT_RE.split(m.group("rest"), maxsplit=1)
        if len(parts) != 2:
            refusals.append(_refusal(
                line, "reason is mandatory on every tending line (`… — reason: <text>`) "
                      "— tending is an audited act; a line with no reason is refused"))
            continue
        middle, reason = parts[0].strip(), parts[1].strip()
        if not reason:
            refusals.append(_refusal(
                line, "reason is mandatory on every tending line and may not be empty"))
            continue

        election: Dict[str, Any] = {"verb": verb, "reason": reason, "line": line}
        if verb == "refocus":
            if middle:
                refusals.append(_refusal(
                    line, "refocus is scope-wide and takes no target — write "
                          "`refocus: — reason: <text>`"))
                continue
            election["target"] = None
        elif verb == "dispose":
            fields, refusal = _parse_dispose_middle(middle, line)
            if refusal is not None:
                refusals.append(refusal)
                continue
            election.update(fields or {})
        else:
            tokens = middle.split()
            if not tokens:
                refusals.append(_refusal(
                    line, f"{verb} requires a target — write `{verb}: <target> — reason: <text>`"))
                continue
            if len(tokens) > 1:
                refusals.append(_refusal(
                    line, f"{verb} takes exactly one target per line (got {len(tokens)}: "
                          f"{', '.join(tokens)}) — one line, one act"))
                continue
            election["target"] = tokens[0]

        if len(elections) >= cap:
            refusals.append(_refusal(
                line, f"refused: over the per-block cap of {cap} elections — "
                      "tend in smaller, deliberate batches (or the host raises the cap)"))
            continue
        elections.append(election)

    return {"elections": elections, "refusals": refusals}


# ---------------------------------------------------------------------------
# Apply: elections → existing engine verbs (batch never aborts; per-election
# refusals are data)
# ---------------------------------------------------------------------------


def _normalize_pairs(pairs: Optional[Sequence[Tuple[str, str]]]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for s, o in pairs or ():
        pair = (str(s or "").strip().lower(), str(o or "").strip())
        if pair[0] and pair not in out:
            out.append(pair)
    return out


def _record_target_gate(
    system: Any, target: str, owner_id: str, self_pairs: List[Tuple[str, str]],
) -> Tuple[Optional[Any], Optional[str]]:
    """Shared gate for record-targeted verbs → (digest_assertion, refusal_text).

    Refuses spoofs (diary entry ids / batch locals), unresolvable targets
    (works-or-loud: both id namespaces are tried), targets owned by someone
    other than the tending owner (tending is over one's OWN memory), and
    identity-scope records (pending ruling — exact text, one stable line).
    """
    if any(target.startswith(p) for p in _SPOOF_TARGET_PREFIXES):
        return None, (
            f"target {target!r} is a diary-entry/batch-local id, not a graph record — "
            "the book is not tendable through the graph; name the projection's record id instead")
    digest = resolve_digest_assertion(system.store, target)
    if digest is None:
        return None, (
            f"target {target!r} resolves to no record in either id namespace "
            "(graph id or digest row id) — tending needs a formed record")
    attrs = digest.attributes if isinstance(digest.attributes, dict) else {}
    if attrs.get("record_edge") or attrs.get("bookkeeping"):
        return None, (
            f"target {target!r} names a graph edge/bookkeeping row, not a record — "
            "tend the records the edge connects instead")
    if (digest.owner_id or "") != owner_id:
        return None, (
            f"target {target!r} is owned by {digest.owner_id!r}, not the tending owner "
            f"{owner_id!r} — tending reaches only one's own memory")
    scope_pair = (str(digest.scope or "").lower(), digest.owner_id or "")
    if scope_pair[0] == "self" or scope_pair in self_pairs:
        # DREAMS ARE EXEMPT from the identity gate (flow's cycle-4 find,
        # c5270: four exact-id reasoned dispose verdicts refused because
        # sleep_pass writes dreams to scopes[0] = self — a STORAGE
        # artifact, not an identity classification; self_component
        # already kind-filters dreams from identity seats). A dream is
        # an ENGINE-authored, review-gated artifact whose designed
        # lifecycle is waking disposal — tending it is the entity
        # reviewing machine output, the exact relationship Q2 protects
        # identity FROM, not an instance of it.
        if str(attrs.get("record_kind") or "") != "dream":
            return None, IDENTITY_SCOPE_PENDING_RULING
    return digest, None


def _resolve_standing_valence(
    system: Any, target: str, *, scope: str, owner_id: str, kind: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve a heal/break target → (event_id, refusal_text).

    The target may be the standing event's id directly, or the APPRAISED
    target string ("person:x", a record id…) — in which case exactly one
    standing (unresolved) marker of `kind` must exist for it in the
    (scope, owner) stream: zero is an honest "no matching {kind}", several
    is an ambiguity refusal NAMING the candidate event ids so the author
    can re-elect precisely. Read-only: consults journal.valence_events.
    """
    resolution_kind = "healing" if kind == "scar" else "break"
    resolution_ref = "heals" if kind == "scar" else "breaks"
    rows = system.journal.valence_events(scope=scope, owner_id=owner_id, limit=0)
    resolved_ids = {
        str(dict(e.provenance or {}).get(resolution_ref) or "").strip()
        for e in rows if e.kind == resolution_kind
    }
    markers = [e for e in rows if e.kind == kind]
    direct = next((e for e in markers if e.event_id == target), None)
    if direct is not None:
        return direct.event_id, None
    standing = [e for e in markers
                if e.target_id == target and e.event_id not in resolved_ids]
    if not standing:
        return None, (
            f"no standing {kind} for {target!r} in ({scope!r}, {owner_id!r}) — "
            f"name a {kind} event id or an appraised target that carries an unresolved {kind}")
    if len(standing) > 1:
        ids = ", ".join(e.event_id for e in standing)
        return None, (
            f"{len(standing)} standing {kind}s match {target!r} ({ids}) — "
            "ambiguous; re-elect naming the exact event id")
    return standing[0].event_id, None


def apply_tend_elections(
    system: Any,
    elections: Sequence[Mapping[str, Any]],
    *,
    scope: str,
    owner_id: str,
    actor: str,
    channel: Optional[str] = None,
    now: Optional[str] = None,
    self_pairs: Sequence[Tuple[str, str]] = (),
    revisit_depth: int = 1,
    revisit_max_records: int = 12,
    revisit_token_budget: int = 1600,
) -> Dict[str, Any]:
    """Apply parsed tending elections through the EXISTING engine verbs.

    system is a MemorySystem-shaped facade; (scope, owner_id) anchor the
    batch: refocus marks THAT stream, heal/break resolve against THAT
    valence stream. Record-targeted verbs (pin/silence/revisit/dispose)
    resolve the target and act in the record's OWN scope pair — attention
    events must land where the record's usage trail lives (the same rule
    commit_selection applies), and the owner-containment gate keeps the
    reach inside the tender's own memory.

    Verb → engine mapping (nothing else is called; no new mutation paths):
      pin        → system.reinforce(record_id, reason=…, scope/owner=record's, actor=actor)
      silence    → system.attenuate(record_id, …)                    [same anchoring]
      refocus    → system.refocus(reason=…, scope=scope, owner_id=owner_id, actor=actor)
      heal_scar  → system.heal_scar(scar_event_id, …)   [target resolved, see below]
      break_bond → system.break_bond(bond_event_id, …)  [symmetric]
      revisit    → system.payload(target, "digest") + system.probe_expand([target], …)
      dispose    → system.dispose_dream(dream_id, disposition=confirmed|dissolved, …)

    Each verb journals exactly what its engine verb already journals —
    nothing extra. Tend never deposits usage (no commit_selection here);
    valence never gates recall; nothing is erased.

    REVISIT — the iterative deliberate reach (maintainer's design input:
    "ideas can lead to others; select the closest nodes first, let it
    spread a bit, find additional paths"). One election = ONE bounded
    spreading step, reusing the existing probe_expand surface: the seed's
    digest is fetched via the existing payload read, then record edges are
    walked `revisit_depth` (default 1) hops in BOTH directions, bounded by
    `revisit_max_records`/`revisit_token_budget` (probe_expand's own
    defaults). The result lands in "revisit_paths" as
    {"seed": …, "paths": [neighbor handles; cues carry the relation labels,
    e.g. "via summarizes from <id>"], "iterations": 1, "trace_id": …}.
    TO ITERATE, the caller re-elects `revisit` seeded on one of the
    returned path nodes — each iteration is its own deliberate, journaled
    act, so the spread stays bounded and auditable instead of running
    away. Revisit IS a real read and journals exactly what probe_expand
    already journals: one trace (trace_kind="expand", escalation_reason =
    the election's reason) plus inert "expanded" audit events — reading is
    not using, so access counts and activation are untouched.

    Apply-time refusals (per election; the batch NEVER aborts): a channel
    other than "entity-reflection" refuses every election (the door may
    also gate; refusing here keeps the contract visible); unresolvable /
    spoofed (diary-entry, batch-local) / foreign-owner targets; identity-
    scope records (IDENTITY_SCOPE_PENDING_RULING, exact text); heal/break
    with no (or several) matching standing markers; dispose without the
    evidence disposal.py demands (its raise converts to a refusal). The
    ONE exception: empty `actor` raises ValueError — words without an
    author are not elections.

    `now` (optional ISO string) stamps the returned report's "applied_at";
    the engine verbs keep stamping their own events with the system clock.

    Returns {"applied": [{"election", "result"}...],
             "refused": [{"election", "reason"}...],
             "revisit_paths": [...], "applied_at": iso}.
    """
    actor_text = str(actor or "").strip()
    if not actor_text:
        raise ValueError(
            "apply_tend_elections requires a non-empty actor — "
            "tending elections are audited acts; words without an author are refused")
    scope_text = str(scope or "").strip().lower()
    owner_text = str(owner_id or "").strip()
    if not scope_text:
        raise ValueError("apply_tend_elections requires a non-empty scope")

    applied: List[Dict[str, Any]] = []
    refused: List[Dict[str, Any]] = []
    revisit_paths: List[Dict[str, Any]] = []
    report: Dict[str, Any] = {
        "applied": applied, "refused": refused, "revisit_paths": revisit_paths,
        "applied_at": str(now).strip() if now else utc_now_iso(),
    }
    pairs = _normalize_pairs(self_pairs)

    # THE CHANNEL MUST BE STATED BY THE CALLER (entity-seat fable5 P0-1
    # root, 2026-07-25): the old default WAS the privileged channel, so a
    # caller omitting it self-satisfied this check — runtime's MEMORY_TEND
    # handler forwarded no channel and every workplace-stamped run tended
    # as the entity's own reflection. An engine privilege check may never
    # be satisfied by its own default: omission now refuses loudly. The
    # home-direct driver states entity-reflection (true by construction);
    # door-served handlers forward the DOOR-VERIFIED channel, never a
    # constant.
    channel_text = str(channel or "").strip()
    if not channel_text:
        for e in elections or ():
            refused.append({"election": dict(e), "reason": (
                "tending requires the caller's verified channel — the "
                f"privileged default was removed (state {_REFLECTION_CHANNEL!r} "
                "only where it is true by construction)")})
        return report
    if channel_text != _REFLECTION_CHANNEL:
        for e in elections or ():
            refused.append({"election": dict(e), "reason": (
                f"tending is an {_REFLECTION_CHANNEL} act; channel {channel_text!r} "
                "may not tend (all elections refused)")})
        return report

    for e in elections or ():
        election = dict(e)
        verb = str(election.get("verb") or "").strip().lower()
        reason = str(election.get("reason") or "").strip()
        target = election.get("target")
        target = str(target).strip() if target is not None else None

        def _refuse(text: str) -> None:
            refused.append({"election": election, "reason": text})

        if verb not in TEND_VERBS:
            _refuse(f"unknown verb {election.get('verb')!r} — the tending vocabulary is: "
                    f"{', '.join(TEND_VERBS)}")
            continue
        if not reason:
            _refuse("reason is mandatory on every tending election")
            continue

        try:
            if verb in ("pin", "silence"):
                if not target:
                    _refuse(f"{verb} requires a target record id")
                    continue
                digest, refusal = _record_target_gate(system, target, owner_text, pairs)
                if refusal is not None:
                    _refuse(refusal)
                    continue
                writer = system.reinforce if verb == "pin" else system.attenuate
                event_id = writer(
                    target, reason=reason, scope=digest.scope,
                    owner_id=digest.owner_id or "", actor=actor_text)
                applied.append({"election": election, "result": {
                    "event_id": event_id,
                    "kind": "pinned" if verb == "pin" else "silenced",
                    "scope": digest.scope, "owner_id": digest.owner_id or ""}})

            elif verb == "refocus":
                event_id = system.refocus(
                    reason=reason, scope=scope_text, owner_id=owner_text, actor=actor_text)
                applied.append({"election": election, "result": {
                    "event_id": event_id, "kind": "refocus",
                    "scope": scope_text, "owner_id": owner_text}})

            elif verb in ("heal_scar", "break_bond"):
                if not target:
                    _refuse(f"{verb} requires a target (an appraised target or the standing "
                            "marker's event id)")
                    continue
                marker_kind = "scar" if verb == "heal_scar" else "bond"
                # A target that resolves to an identity-scope RECORD is still
                # gated by the pending ruling; free-string targets (the
                # gradation currency) carry no record and pass through.
                # Dreams are exempt for parity with every other verb (the
                # c5270 exemption — same storage-artifact rationale).
                record = resolve_digest_assertion(system.store, target)
                if record is not None:
                    record_pair = (str(record.scope or "").lower(), record.owner_id or "")
                    record_attrs = record.attributes if isinstance(record.attributes, dict) else {}
                    if ((record_pair[0] == "self" or record_pair in pairs)
                            and str(record_attrs.get("record_kind") or "") != "dream"):
                        _refuse(IDENTITY_SCOPE_PENDING_RULING)
                        continue
                event_ref, refusal = _resolve_standing_valence(
                    system, target, scope=scope_text, owner_id=owner_text, kind=marker_kind)
                if refusal is not None:
                    _refuse(refusal)
                    continue
                if verb == "heal_scar":
                    resolved_id = system.heal_scar(
                        event_ref, reason=reason, scope=scope_text,
                        owner_id=owner_text, actor=actor_text)
                else:
                    resolved_id = system.break_bond(
                        event_ref, reason=reason, scope=scope_text,
                        owner_id=owner_text, actor=actor_text)
                applied.append({"election": election, "result": {
                    "event_id": resolved_id, "kind": verb,
                    f"{marker_kind}_event_id": event_ref}})

            elif verb == "revisit":
                if not target:
                    _refuse("revisit requires a seed record id")
                    continue
                digest, refusal = _record_target_gate(system, target, owner_text, pairs)
                if refusal is not None:
                    _refuse(refusal)
                    continue
                payload = system.payload(target, tier="digest")
                attrs = digest.attributes if isinstance(digest.attributes, dict) else {}
                seed = {
                    "record_id": str(digest.assertion_id or target),
                    "graph_id": str(digest.subject or target),
                    "title": str(attrs.get("title") or ""),
                    "digest": payload.get("content"),
                    "kind": str(attrs.get("record_kind") or ""),
                    "scope": digest.scope, "owner_id": digest.owner_id or "",
                    "token_estimate": payload.get("token_estimate"),
                }
                if payload.get("entry_id"):  # diary projections: progressive disclosure
                    seed["entry_id"] = payload["entry_id"]
                reach = system.probe_expand(
                    [target], reason=reason, depth=int(revisit_depth),
                    max_records=int(revisit_max_records),
                    token_budget=int(revisit_token_budget), journal=True)
                entry = {
                    "seed": seed,
                    "paths": [hit.to_dict() for hit in reach.hits],
                    "iterations": 1,
                    "trace_id": reach.trace_id,
                }
                revisit_paths.append(entry)
                applied.append({"election": election, "result": {
                    "kind": "revisit", "trace_id": reach.trace_id,
                    "paths_found": len(reach.hits)}})

            elif verb == "dispose":
                if not target:
                    _refuse("dispose requires a dream record id")
                    continue
                digest, refusal = _record_target_gate(system, target, owner_text, pairs)
                if refusal is not None:
                    _refuse(refusal)
                    continue
                disposition = _DISPOSITIONS.get(str(election.get("disposition") or "").lower())
                if disposition is None:
                    _refuse("dispose requires a disposition of confirm or reject")
                    continue
                args = dict(election.get("args") or {})
                result = system.dispose_dream(
                    target, disposition=disposition, reason=reason,
                    relation=args.get("relation"), source_id=args.get("source_id"),
                    target_id=args.get("target_id"),
                    evidence_ids=tuple(args.get("evidence_ids") or ()),
                    actor=actor_text)
                applied.append({"election": election, "result": result})

        except ValueError as err:
            # The engine's refusal currency: heal/break with no matching
            # marker, dispose without evidence/relation, unknown ids on the
            # facade paths — all convert to per-election refusal DATA.
            _refuse(str(err))

    return report
