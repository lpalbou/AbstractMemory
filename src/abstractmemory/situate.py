"""situate() — rebuild the full context of a past moment (backlog 0034).

THE MAINTAINER'S MODEL (2026-07-12): "'put me back at that time' (or more
like: what was I doing during/when X (time) or when I met X (relational))
is important. it's essentially rebuilding a full context at a given time,
to help us continue on that path we wouldn't continue at the time.
HOWEVER, when doing so, the identity has evolved, which can help (or not)
the resolution of that path." The temporal graph is a standing HARD
requirement of his model: situate = pure-read composition of snapshots +
activation(at_seq) + formation-window records + diary-around-T, always
labeled historical, never auto-depositing (the anti "trapped in the
past" rule).

EVERY PRIMITIVE EXISTED; this module is the missing composition. The seam
reserved admission="historical" for exactly this surface, and the
journal's until_seq threading calls itself "situate() groundwork".

ANCHORS — temporal and RELATIONAL (his "when I met X"):
- a journal seq (the exact axis position),
- an ISO timestamp (seq_at translates),
- a participant + occurrence ("first"/"last" encounter: the earliest/
  latest formed record stamped with that participant).

THE COMPOSED READ (all pure; the journal is untouched, access counts
never move — guard-tested):
- moment: the nearest reconstruction trace + snapshot at-or-before the
  anchor WHOSE SEARCHED SCOPES OVERLAP the requested scopes (a shared
  journal may interleave other owners' recalls — their moments are not
  this mind's; adversary P1.5), snapshot read anchored (a commit landing
  after the anchor never leaks into the past);
- activity: top-K activation at the anchor via the engine's own
  per-scope-then-MAX fold (folds.activation_inputs — cross-scope
  summing would double-count one usage; adversary P1.3);
- period: the record-count neighborhood around the anchor ON THE
  FORMATION AXIS (result carries period_axis="formation_seq" — inside
  the engine observed_at is pinned at encode time so the axes coincide,
  but archive-imported content carries origin_date in attributes while
  observed_at stays import time: the label keeps the read honest);
- elected: diary projections in the window (act-frames and gists as the
  projection carries them; private words stay in the book);
- then_identity: the prompt-active identity core as of the anchor
  (deduplicated across ladder scopes) — who I WAS;
- identity_evolution: what changed in me since — identity records added
  (added_and_closed_since when both happened after the anchor) or
  closed after it. KNOWN LIMIT (v1, labeled): bind-state flips (a value
  activated into or out of the prompt core without formation/closure)
  are not diffed;
- tensions_then: question/plan records and question/problem/commitment
  diary entries OPEN AT THE ANCHOR — closure-folded as-of the anchor
  AND resolution-folded as-of the anchor (the diary lane resolves by
  REFERENCE, not closure: an entry whose attributes.answers/resolves/
  fulfills names the record, or an authored answers/resolves/fulfills
  edge, formed at or before the anchor, settles the tension — adversary
  P1.2: presenting already-settled questions as the open tensions of
  that moment would corrupt exactly the resume judgment this surface
  serves).

Everything record-shaped is labeled admission="historical". Hosts MUST
NOT commit situate results as if they were displayed working memory —
re-living is a deliberate act (re-enter via anchor_record_ids on a
normal reconstruct), never a side effect of looking back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .attention import AttentionConfig
from .canonical_text import handle_digest, token_estimate
from .folds import activation_inputs, closure_exclusions
from .records import ReconstructConfig
from .store import TripleQuery

__all__ = ["SituateBudget", "situate", "situate_prompt_block"]


@dataclass(frozen=True)
class SituateBudget:
    """Declared bounds for one situate read (no magic numbers). Bounds of
    zero mean NOTHING of that section (the package convention: <=0 is
    never "unlimited"); negatives refuse loudly."""

    window_records: int = 24        # period records around the anchor
    activity_top_k: int = 12        # warm records at the anchor
    diary_entries: int = 8          # elected entries in the window
    tensions: int = 12              # open questions/problems/plans at T
    identity_delta: int = 24        # evolution entries (added/closed)
    token_budget: int = 2400        # display bound across the period
    moment_trace_walk: int = 50     # traces inspected for scope overlap

    def __post_init__(self) -> None:
        for name in ("window_records", "activity_top_k", "diary_entries",
                     "tensions", "identity_delta", "token_budget",
                     "moment_trace_walk"):
            if int(getattr(self, name)) < 0:
                raise ValueError(
                    f"SituateBudget.{name} must be >= 0 (0 = none of that "
                    f"section; negative bounds are refused, never wrapped)")


_TENSION_KINDS = frozenset({"question", "plan"})
_TENSION_DIARY_TYPES = frozenset({"question", "problem", "commitment"})
# "fulfills" joined when commitments gained their resolution convention
# (prospective memory, 2026-07-13): a fulfilled commitment presented as an
# open tension would be the same P1.2 corruption as a settled question.
_RESOLUTION_ATTRS = ("answers", "resolves", "fulfills")
_RESOLUTION_EDGES = frozenset({"answers", "resolves", "fulfills"})


def _resolve_anchor(
    journal: Any, *,
    at: Optional[str] = None, seq: Optional[int] = None,
    participant: Optional[str] = None, occurrence: str = "first",
    formed_at: Dict[str, int], rows_by_gid: Dict[str, Any],
) -> Tuple[int, Dict[str, Any]]:
    """One anchor from exactly one of (seq | at | participant). Loud on
    ambiguity, absence, and unknown participants (works-or-loud).
    Relational anchors resolve over the PREFETCHED digest scan — one
    store pass for the whole read, never a per-binding query storm."""
    supplied = [name for name, v in
                (("seq", seq), ("at", at), ("participant", participant))
                if v is not None]
    if len(supplied) != 1:
        raise ValueError(
            f"situate needs exactly ONE anchor of seq/at/participant, got {supplied or 'none'}")
    if seq is not None:
        anchor = int(seq)
        if not (0 <= anchor <= journal.current_seq()):
            raise ValueError(
                f"situate: seq={anchor} outside this journal's axis "
                f"(current_seq={journal.current_seq()})")
        return anchor, {"anchor_kind": "seq", "anchor": anchor}
    if at is not None:
        anchor = int(journal.seq_at(str(at)))
        if anchor <= 0:
            raise ValueError(
                f"situate: no journal activity at or before {at!r} — the life "
                "had not started yet at that time")
        return anchor, {"anchor_kind": "time", "anchor": str(at)}

    occ = str(occurrence or "first").strip().lower()
    if occ not in ("first", "last"):
        raise ValueError(f"situate: occurrence must be 'first' or 'last', got {occurrence!r}")
    who = str(participant or "").strip()
    stamped: List[Tuple[int, str]] = []  # (formation seq, graph id)
    for gid, a in rows_by_gid.items():
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        if who in (attrs.get("participants") or ()) and gid in formed_at:
            stamped.append((formed_at[gid], gid))
    if not stamped:
        raise ValueError(
            f"situate: no record in the searched scopes is stamped with "
            f"participant {who!r} — participants are namespaced identity "
            "strings (e.g. 'person:ada'); check the namespace and scopes")
    stamped.sort()
    anchor, gid = stamped[0] if occ == "first" else stamped[-1]
    return anchor, {"anchor_kind": "participant", "anchor": who,
                    "occurrence": occ, "encounter_record_id": gid}


def _historical_handle(assertion: Any, config: ReconstructConfig) -> Dict[str, Any]:
    attrs = assertion.attributes if isinstance(assertion.attributes, dict) else {}
    digest = handle_digest(assertion)
    return {
        "record_id": str(assertion.assertion_id or ""),
        "graph_id": str(assertion.subject or ""),
        "kind": config.kind_of(assertion),
        "title": str(attrs.get("title") or ""),
        "digest": digest,
        "observed_at": str(assertion.observed_at or ""),
        "token_estimate": token_estimate(digest),
        "admission": "historical",
    }


def situate(
    store: Any,
    journal: Any,
    *,
    scopes: Sequence[Tuple[str, str]],
    at: Optional[str] = None,
    seq: Optional[int] = None,
    participant: Optional[str] = None,
    occurrence: str = "first",
    budget: SituateBudget = SituateBudget(),
    attention_config: AttentionConfig = AttentionConfig(),
    config: ReconstructConfig = ReconstructConfig(),
) -> Dict[str, Any]:
    """Rebuild the context of one past moment. PURE READ: writes nothing,
    deposits nothing; every record-shaped result is labeled historical."""
    if not scopes:
        raise ValueError("situate requires at least one (scope, owner_id) pair")
    requested_pairs = {(str(s).strip().lower(), str(o).strip()) for s, o in scopes}

    # --- one bindings walk + one digest scan feed the whole read ----------
    formed_at: Dict[str, int] = {}
    for scope, owner in scopes:
        for b in journal.bindings(scope=scope, owner_id=owner, fold=False):
            if b.source == "remember":
                seq_b = int(b.seq)
                if b.record_id not in formed_at or seq_b < formed_at[b.record_id]:
                    formed_at[b.record_id] = seq_b

    rows_by_gid: Dict[str, Any] = {}
    resolution_edges: List[Tuple[str, str]] = []   # (source gid, target)
    for scope, owner in scopes:
        for a in store.query(TripleQuery(scope=scope, owner_id=owner or None, limit=0)):
            attrs = a.attributes if isinstance(a.attributes, dict) else {}
            if attrs.get("record_edge"):
                if str(a.predicate or "") in _RESOLUTION_EDGES:
                    resolution_edges.append((str(a.subject), str(a.object)))
                continue
            if attrs.get("bookkeeping") or not attrs.get("record_kind"):
                continue
            rows_by_gid[a.subject] = a

    anchor_seq, anchor_info = _resolve_anchor(
        journal, at=at, seq=seq, participant=participant,
        occurrence=occurrence, formed_at=formed_at, rows_by_gid=rows_by_gid)

    # Closures AS OF the anchor: what was still believed then.
    closed_then = closure_exclusions(journal, anchor_seq)

    def _existed_then(gid: str) -> bool:
        born = formed_at.get(gid)
        return born is not None and born <= anchor_seq

    # --- the moment: nearest OVERLAPPING trace + anchored snapshot --------
    moment: Dict[str, Any] = {"trace_id": None, "held_record_ids": (),
                              "cue": None, "observed_at": None}
    for t in journal.traces(limit=max(1, budget.moment_trace_walk),
                            until_seq=anchor_seq):
        trace_pairs = {(str(s.get("scope") or "").strip().lower(),
                        str(s.get("owner_id") or "").strip())
                       for s in (t.searched_scopes or ()) if isinstance(s, dict)}
        # A trace with no recorded scopes (expand traces, legacy) is
        # accepted only when the journal serves a single mind anyway.
        if trace_pairs and not (trace_pairs & requested_pairs):
            continue
        moment = {
            "trace_id": t.trace_id,
            "held_record_ids": tuple(t.selected or ()),
            "cue": (t.need or {}).get("cue_text"),
            "observed_at": t.observed_at,
        }
        # Anchored snapshot read (P1.5): a commit snapshot appended AFTER
        # the anchor is later-record truth and never leaks into the past.
        snaps = journal.snapshots(trace_id=t.trace_id, until_seq=anchor_seq, limit=1)
        if snaps:
            moment["snapshot_display"] = tuple(snaps[0].display or ())
        break

    # --- activity: the engine's own anchored fold (per-scope, MAX merge) --
    base, _trails, _cues = activation_inputs(
        journal, sorted(requested_pairs), anchor_seq, config=attention_config)
    warm = sorted(((rid, value) for rid, value in base.items() if value > 0.0),
                  key=lambda kv: (-kv[1], kv[0]))[: budget.activity_top_k]

    # --- period: formation-axis neighborhood around the anchor ------------
    before = sorted(
        ((born, gid) for gid, born in formed_at.items()
         if born <= anchor_seq and gid in rows_by_gid),
        key=lambda kv: (-kv[0], kv[1]),
    )
    after = sorted(
        ((born, gid) for gid, born in formed_at.items()
         if born > anchor_seq and gid in rows_by_gid),
        key=lambda kv: (kv[0], kv[1]),
    )
    window = max(0, int(budget.window_records))
    half = window // 2
    period_ids = [gid for _b, gid in before[:half]]
    remaining = max(0, window - len(period_ids))
    period_ids += [gid for _b, gid in after[:remaining]]
    if len(period_ids) < window:
        # End-of-life symmetry: an anchor near the newest edge fills the
        # window from the past instead of under-serving it.
        extra = window - len(period_ids)
        period_ids += [gid for _b, gid in before[half:half + extra]]

    tokens = 0
    token_exhausted = False
    period: List[Dict[str, Any]] = []
    diary: List[Dict[str, Any]] = []
    for gid in period_ids:
        a = rows_by_gid[gid]
        handle = _historical_handle(a, config)
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        if attrs.get("record_kind") == "diary":
            if len(diary) < int(budget.diary_entries):
                diary.append(handle)
            continue
        cost = handle["token_estimate"]
        if tokens + cost > int(budget.token_budget) and period:
            token_exhausted = True
            break
        tokens += cost
        period.append(handle)

    # --- then-identity (deduplicated) + evolution --------------------------
    from .self_component import self_records_read

    then_identity: List[Dict[str, Any]] = []
    seen_identity: Set[str] = set()
    for scope, owner in scopes:
        for a in self_records_read(store, journal, scope=scope, owner_id=owner,
                                   as_of=anchor_seq):
            rid = str(a.assertion_id or a.subject)
            if rid in seen_identity:
                continue
            seen_identity.add(rid)
            then_identity.append(_historical_handle(a, config))

    closed_now = closure_exclusions(journal, journal.current_seq())
    from .records import IDENTITY_KINDS as identity_kinds  # canonical (drift-class kill)
    evolution: List[Dict[str, Any]] = []
    for gid, a in sorted(rows_by_gid.items()):
        if len(evolution) >= int(budget.identity_delta):
            break
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        if attrs.get("record_kind") not in identity_kinds:
            continue
        born = formed_at.get(gid)
        added_since = born is not None and born > anchor_seq
        closed_now_flag = a.assertion_id in closed_now or gid in closed_now
        was_open_then = (_existed_then(gid)
                         and a.assertion_id not in closed_then and gid not in closed_then)
        closed_since = was_open_then and closed_now_flag
        if not (added_since or closed_since):
            continue
        entry = _historical_handle(a, config)
        if added_since and closed_now_flag:
            # Honest transient (adversary P2): formed after the anchor AND
            # already closed — "added_since" alone would present it as
            # still part of the evolved self.
            entry["change"] = "added_and_closed_since"
        else:
            entry["change"] = "added_since" if added_since else "closed_since"
        evolution.append(entry)

    # --- tensions open AT the anchor ---------------------------------------
    # Resolution fold as-of the anchor (adversary P1.2): the diary lane
    # settles questions/problems by REFERENCE (attributes.answers/resolves)
    # and the graph twin by authored answers/resolves edges — deliberately
    # without closures. A tension referenced by a resolver formed AT OR
    # BEFORE the anchor was not open at that moment.
    resolved_refs: Set[str] = set()
    for gid, a in rows_by_gid.items():
        if not _existed_then(gid):
            continue
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        for attr in _RESOLUTION_ATTRS:
            ref = attrs.get(attr)
            if isinstance(ref, str) and ref.strip():
                resolved_refs.add(ref.strip())
    for source_gid, target in resolution_edges:
        if _existed_then(source_gid) and target:
            resolved_refs.add(target)

    def _is_resolved_then(a: Any) -> bool:
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        candidates = {str(a.subject or ""), str(a.assertion_id or "")}
        entry_id = attrs.get("entry_id")
        if isinstance(entry_id, str) and entry_id.strip():
            candidates.add(entry_id.strip())
        return bool(candidates & resolved_refs)

    tensions: List[Dict[str, Any]] = []
    for gid, a in sorted(rows_by_gid.items()):
        if len(tensions) >= int(budget.tensions):
            break
        attrs = a.attributes if isinstance(a.attributes, dict) else {}
        kind = attrs.get("record_kind")
        is_tension = (kind in _TENSION_KINDS
                      or (kind == "diary"
                          and attrs.get("diary_type") in _TENSION_DIARY_TYPES))
        if not is_tension or not _existed_then(gid):
            continue
        if a.assertion_id in closed_then or gid in closed_then:
            continue
        if _is_resolved_then(a):
            continue
        tensions.append(_historical_handle(a, config))

    return {
        "pass_name": "situate",
        "anchor_seq": anchor_seq,
        **anchor_info,
        "moment": moment,
        "activity": [{"record_id": rid, "activation": round(total, 6),
                      "admission": "historical"} for rid, total in warm],
        "period": period,
        "period_axis": "formation_seq",  # honest label (docstring rationale)
        "elected": diary,
        "then_identity": then_identity,
        "identity_evolution": evolution,
        "tensions_then": tensions,
        "budget": {
            "window_records": window,
            "activity_top_k": int(budget.activity_top_k),
            "token_budget": int(budget.token_budget),
            "tokens_used": tokens,
            "token_exhausted": token_exhausted,
        },
        # The contract line, machine-readable: nothing here was deposited.
        "deposits": "none — situate is a pure read; re-living is a deliberate act",
    }


_BLOCK_OPEN = "[HISTORICAL CONTEXT — reconstructed, not the present]"
_BLOCK_CLOSE = "[END HISTORICAL CONTEXT]"


def situate_prompt_block(situation: Dict[str, Any]) -> str:
    """Render one situate() result as the LABELED PROMPT BLOCK the durable
    R4 re_explore session injects (design v4 §3/§6 step 2 — memory's block
    contract; the driver/door owns WHERE it lands in the prompt).

    THE CONTRACT (uic's wire-flag rule applied to prompt text):
    - ONE opening label carries the anchor (seq + human moment when the
      anchor resolution produced one) and states this is a reconstruction;
      one closing label bounds it — nothing historical ever renders
      outside the fence, so a model can never mistake past for present.
    - Every record line carries its formation-era date in place — the
      visit-honesty lesson (undated handles make "when?" unanswerable).
    - The block is PROMPT CONTEXT for the OWNING entity's own session.
      It is not an audience surface: serving a life to watchers goes
      through export_replay's redaction, never through this render.
      Diary lines render the projection's own act/gist text (the
      projection is already the leak-safe plane; private words stay in
      the book by formation-side construction).
    - The footer restates the deposit rule in the entity's own terms —
      remembering here is READING; re-living is a deliberate act.
    """
    lines: List[str] = []
    anchor_bits = [f"as of journal seq {situation.get('anchor_seq')}"]
    moment_iso = (situation.get("moment") or {}).get("observed_at")
    # situate() emits anchor_kind="time" (production-audit finding 7: the
    # old "timestamp" comparison was a dead branch — a time-anchored block
    # never rendered its requested moment).
    if situation.get("anchor_kind") in ("time", "timestamp") and situation.get("anchor"):
        anchor_bits.append(f"moment {situation['anchor']}")
    elif moment_iso:
        anchor_bits.append(f"around {moment_iso}")
    if situation.get("anchor_kind") == "participant":
        anchor_bits.append(
            f"{situation.get('occurrence', 'first')} encounter with {situation.get('anchor')}")
    lines.append(f"{_BLOCK_OPEN[:-1]}; {', '.join(anchor_bits)}]")

    def _record_line(h: Dict[str, Any]) -> str:
        date = str(h.get("observed_at") or "")[:10] or "undated"
        title = str(h.get("title") or "").strip()
        head = f"[{h.get('kind', 'memory')} {date}]"
        body = f"{title}: {h.get('digest', '')}" if title else str(h.get("digest", ""))
        return f"  {head} {body}".rstrip()

    moment = situation.get("moment") or {}
    if moment.get("cue"):
        lines.append(f"What I was attending to then: {moment['cue']}")
    period = situation.get("period") or ()
    if period:
        lines.append("What existed around that moment:")
        lines.extend(_record_line(h) for h in period)
    elected = situation.get("elected") or ()
    if elected:
        lines.append("What I elected to remember around then (my diary):")
        lines.extend(_record_line(h) for h in elected)
    then_identity = situation.get("then_identity") or ()
    if then_identity:
        lines.append("Who I was then (identity as it stood):")
        lines.extend(_record_line(h) for h in then_identity)
    evolution = situation.get("identity_evolution") or ()
    if evolution:
        lines.append("How I have changed since (my present self, for contrast):")
        for h in evolution:
            lines.append(f"{_record_line(h)} ({h.get('change', 'changed')})")
    tensions = situation.get("tensions_then") or ()
    if tensions:
        lines.append("What was still open at that moment:")
        lines.extend(_record_line(h) for h in tensions)

    lines.append(
        "This is a reconstruction of my past, read with my present identity. "
        "Nothing above re-entered my working memory by being shown here; if I "
        "want to truly re-live one of these, reaching for it is my own deliberate act.")
    lines.append(_BLOCK_CLOSE)
    return "\n".join(lines)
