"""A realistic 19-turn assistant session driving the AbstractMemory engine.

    python examples/realistic_session.py

Environment:
    LMSTUDIO_URL          OpenAI-compatible API root (default http://127.0.0.1:1234/v1)
    LMSTUDIO_EMBED_MODEL  embedding model id (default: auto-detected, prefers
                          the qwen3 0.6b embedding model)

The scenario: Sam, a developer, builds "Hearth" — a local-first
home-automation hub. Along the way: a personal fact (daughter Chloé's piano
recital on Thursday), engineering decisions with recorded rationale
(PostgreSQL over SQLite because of concurrent writers; Zigbee vs WiFi
tradeoffs), a mid-session detour into an unrelated tax question, and a
return to the project.

Every turn runs the host loop against ONE MemorySystem, in runtime order:
    1. refocus() when the message is a topic shift,
    2. formation of the facts the USER just stated (typed records with
       titles, prose digests, topics) — before recall, so a fact stated
       this turn is selectable this turn,
    3. reconstruct(view="working_set") with the turn's question as the cue,
    4. the reply happens; records DERIVED from it (answers, decisions with
       rationale edges such as decision derived_from constraint) are formed
       now — they did not exist at recall time,
    5. ONE commit_selection for the turn's context: the handles the host
       rendered (top 4 by relevance) PLUS the reply-derived records (the
       reply itself was in the context by construction). Surfaced-but-not-
       rendered handles stay listed-only — reading is not using.

Printed per turn: the working-set titles, each handle's activation
decomposition (base + spread), and its cues (the "why"). Watch for:
    - SAME-TURN RECALL   a record formed this turn is already on the shelf;
    - CROSS-TURN RECALL  the Postgres decision resurfaces turns later;
    - DECAY              the tax detour drains out of the emergent working
                         memory once the project resumes (storage keeps it);
    - REACTIVATION       an indirect "Thursday evening" cue re-lifts the
                         recital fact.

When LMStudio is reachable the demo uses REAL embeddings; otherwise it
falls back to a deterministic hash-based embedder (loud #FALLBACK note) so
the walkthrough always runs — with reduced semantic fidelity.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from abstractmemory import (  # noqa: E402
    InMemoryJournal,
    InMemoryTripleStore,
    MemoryRecordInput,
    MemorySystem,
    OpenAICompatTextEmbedder,
    RecallBudget,
    ReconstructionResult,
    Stimulus,
)

LMSTUDIO_URL = os.environ.get("LMSTUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
SCOPE, OWNER, SESSION = "session", "sam-hearth", "hearth-demo"

# Tight per-turn budget: real selection pressure (~4-6 digests fit).
TURN_BUDGET = RecallBudget(shelf_size=6, token_budget=220)
# Membership probe: blank cue -> no channels -> pure recency+activation with
# a min_activation floor. This is "what is in working memory right now".
MEMBERSHIP_BUDGET = RecallBudget(shelf_size=12, token_budget=2400, min_activation=3.0)
COMMIT_TOP = 4  # the host renders the top 4 digests into its prompt


# ---------------------------------------------------------------------------
# Embedder selection: live LMStudio, else deterministic hash fallback
# ---------------------------------------------------------------------------


class HashedBagEmbedder:
    """Deterministic, dependency-free fallback: each token contributes a few
    sha256-derived signed components; vectors are L2-normalized. Similarity
    degrades to token overlap — good enough to run the walkthrough, NOT a
    semantic model."""

    def __init__(self, dim: int = 256) -> None:
        self._dim = dim

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for text in texts:
            v = [0.0] * self._dim
            for tok in re.findall(r"[a-z0-9]+", str(text or "").lower()):
                if len(tok) < 3:
                    continue
                h = hashlib.sha256(tok.encode("utf-8")).digest()
                for k in range(4):
                    idx = int.from_bytes(h[4 * k : 4 * k + 2], "big") % self._dim
                    v[idx] += 1.0 if h[4 * k + 2] % 2 == 0 else -1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


def detect_embedder() -> Tuple[object, str]:
    """Probe {LMSTUDIO_URL}/models (2s) and pick an embedding model; fall
    back to the hash embedder with a loud #FALLBACK note."""
    override = os.environ.get("LMSTUDIO_EMBED_MODEL", "").strip()
    try:
        with urlopen(Request(LMSTUDIO_URL + "/models", method="GET"), timeout=2.0) as resp:
            rows = json.loads(resp.read().decode("utf-8")).get("data") or []
        ids = [str(r.get("id")) for r in rows if isinstance(r, dict) and r.get("id")]
        model = None
        if override:
            model = override if override in ids else None
        else:
            for pred in (
                lambda m: "embedding" in m and "qwen" in m and "0.6b" in m,
                lambda m: "embedding" in m and "qwen" in m,
                lambda m: "embedding" in m or m.startswith("text-embedding"),
            ):
                found = [m for m in ids if pred(m.lower())]
                if found:
                    model = found[0]
                    break
        if model:
            return (
                OpenAICompatTextEmbedder(LMSTUDIO_URL, model, timeout_s=60.0),
                f"LMStudio {LMSTUDIO_URL} · embedding model {model!r} (REAL embeddings)",
            )
        reason = f"no usable embedding model among {len(ids)} served ids"
    except Exception as e:
        reason = f"{type(e).__name__}: {e}"
    print(
        "#FALLBACK: LMStudio unreachable or no embedding model "
        f"({reason}).\n#FALLBACK: using the deterministic hash-bag embedder — "
        "the demo runs, but semantic (non-overlapping-vocabulary) recall is degraded.\n"
    )
    return HashedBagEmbedder(), "hash-bag fallback embedder (#FALLBACK — not semantic)"


# ---------------------------------------------------------------------------
# The scenario: 19 turns
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rec:
    label: str
    kind: str
    title: str
    digest: str
    topic: str
    keywords: Tuple[str, ...] = ()
    edges: Tuple[Tuple[str, str], ...] = ()  # (relation, target label)


@dataclass(frozen=True)
class Turn:
    n: int
    user_text: str
    user_records: Tuple[Rec, ...] = ()   # stated by the user; formed BEFORE recall
    reply_records: Tuple[Rec, ...] = ()  # derived from the reply; formed at end of turn
    refocus_reason: Optional[str] = None
    note: Optional[str] = None  # what to watch for on this turn

    @property
    def records(self) -> Tuple[Rec, ...]:
        return self.user_records + self.reply_records


TURNS: Tuple[Turn, ...] = (
    Turn(
        1,
        "I'm starting a project called Hearth — a home-automation hub that runs "
        "entirely on my local network. Help me plan it.",
        (
            Rec("kickoff", "episode", "Hearth project kickoff",
                "Sam kicked off Hearth, a local-first home-automation hub that keeps "
                "every device and automation on the LAN.",
                "hearth/overview", ("hearth", "home-automation")),
            Rec("local-first", "instruction", "Local-first requirement",
                "All device data and automations stay on the local network; no cloud "
                "dependency is acceptable, even for voice control.",
                "hearth/overview", ("local-first", "privacy")),
        ),
    ),
    Turn(
        2,
        "Before I forget — I need to leave early on Thursday. My daughter Chloé "
        "has her piano recital.",
        (
            Rec("piano", "episode", "Chloé's piano recital (Thursday)",
                "Sam's daughter Chloé has her piano recital on Thursday evening at "
                "18:00 in the school auditorium; Sam plans to head out by 17:00.",
                "personal/family", ("chloé", "recital", "thursday")),
            Rec("leave-plan", "plan", "Leave early on Thursday",
                "Wrap up work early on Thursday: be out the door by 17:00 to reach "
                "the school auditorium before the performance starts.",
                "personal/family", ("thursday",), (("prepares_for", "piano"),)),
        ),
        note="SAME-TURN RECALL — the recital was formed THIS turn and is already on the shelf",
    ),
    Turn(
        3,
        "Hardware constraint for everything we choose: the hub runs on a "
        "Raspberry Pi 5 with 8 gigs of RAM.",
        (
            Rec("pi-constraint", "instruction", "Hub hardware: Raspberry Pi 5",
                "Target hardware is a Raspberry Pi 5 with 8 GB of RAM; every "
                "component we pick must run comfortably within that envelope.",
                "hearth/hardware", ("raspberry-pi",)),
        ),
    ),
    Turn(
        4,
        "For state and event history, should I use SQLite or Postgres on the hub?",
        user_records=(
            Rec("storage-question", "question", "SQLite vs PostgreSQL for the hub",
                "Open question: SQLite or PostgreSQL for the hub's state and event "
                "history, given the write patterns we expect.",
                "hearth/storage", ("sqlite", "postgresql")),
        ),
        reply_records=(
            Rec("storage-answer", "answer", "Prototype hit SQLite's writer lock",
                "SQLite's single-writer lock stalled the prototype whenever sensor "
                "ingest and the rule engine wrote at the same moment.",
                "hearth/storage", ("sqlite", "lock"), (("answers", "storage-question"),)),
        ),
    ),
    Turn(
        5,
        "Let's settle it — the rule engine, sensor ingest, and app sync all "
        "write at once, so pick accordingly.",
        reply_records=(
            Rec("postgres-decision", "decision", "PostgreSQL over SQLite for the hub",
                "Chose PostgreSQL over SQLite for the hub's state store because "
                "several processes write concurrently: sensor ingest, the rule "
                "engine, and mobile app sync.",
                "hearth/storage", ("postgresql",),
                (("derived_from", "storage-answer"),
                 ("derived_from", "pi-constraint"),
                 ("resolves", "storage-question"))),
        ),
        note="the reply forms a DECISION with rationale edges (derived_from the lock "
             "stall and the Pi constraint) — on the shelf from the NEXT turn on",
    ),
    Turn(
        6,
        "For the sensors themselves — Zigbee or WiFi?",
        reply_records=(
            Rec("zigbee-claim", "claim", "Zigbee vs WiFi power tradeoff",
                "Zigbee mesh radios sip battery on door and window sensors, while "
                "WiFi sensors drain coin cells in weeks; cameras still need WiFi "
                "bandwidth.",
                "hearth/radio", ("zigbee", "wifi")),
            Rec("zigbee-decision", "decision", "Zigbee for sensors, WiFi for cameras",
                "Chose Zigbee for battery-powered sensors and WiFi only for the two "
                "cameras, matching each radio to its power and bandwidth profile.",
                "hearth/radio", ("zigbee", "wifi"), (("derived_from", "zigbee-claim"),)),
        ),
    ),
    Turn(
        7,
        "Sketch the Postgres schema for device state and the event log.",
        reply_records=(
            Rec("schema-plan", "plan", "Hub database schema draft",
                "Draft schema: a devices table, a device_state table keyed by device "
                "id, and an append-only events table partitioned by month.",
                "hearth/storage", ("schema",), (("derived_from", "postgres-decision"),)),
        ),
        note="CROSS-TURN RECALL — the storage cue should resurface the turn-5 decision",
    ),
    Turn(
        8,
        "Completely different question — my consulting income jumped this year. "
        "Do I need to adjust my Q3 estimated tax payment?",
        user_records=(
            Rec("tax-question", "question", "Q3 estimated tax adjustment?",
                "Open question: does the jump in consulting income require adjusting "
                "the Q3 estimated tax payment.",
                "personal/taxes", ("taxes",)),
        ),
        reply_records=(
            Rec("tax-answer", "answer", "Safe-harbor rule for Q3 payment",
                "Increase the Q3 estimated payment to stay inside the safe-harbor "
                "rule: pay at least 110 percent of last year's liability to avoid an "
                "underpayment penalty.",
                "personal/taxes", ("taxes", "safe-harbor"), (("answers", "tax-question"),)),
        ),
        refocus_reason="user switched from the Hearth project to a personal tax question",
        note="TOPIC SHIFT — the host marks a refocus; watch the working set flip",
    ),
    Turn(
        9,
        "And can I deduct the workshop where I solder the sensor boards as a "
        "home office?",
        reply_records=(
            Rec("homeoffice-answer", "answer", "Home-office deduction for the workshop",
                "The workshop where the sensor boards are soldered can qualify for "
                "the home-office deduction if the space is used regularly and "
                "exclusively for the business.",
                "personal/taxes", ("taxes", "deduction"), (("relates_to", "tax-answer"),)),
        ),
    ),
    Turn(
        10,
        "Anyway — back to Hearth. Where did we land on storage, and what's next "
        "there?",
        reply_records=(
            Rec("storage-recap", "summary", "Storage track recap",
                "Storage recap: PostgreSQL is the hub's state store, the schema "
                "draft covers devices, state, and events, and ingest batching is the "
                "next open task.",
                "hearth/storage", ("postgresql", "recap"),
                (("summarizes", "postgres-decision"), ("summarizes", "schema-plan"))),
        ),
        refocus_reason="user returned to the Hearth project after the tax detour",
        note="RETURN — refocus accelerates the detour's decay; project facts recover through re-use",
    ),
    Turn(
        11,
        "Implement the sensor ingest writer — it was way too slow last time.",
        reply_records=(
            Rec("ingest-lesson", "lesson", "Batch sensor inserts",
                "Batch sensor readings and insert them in one transaction every two "
                "seconds; per-reading inserts saturated the Pi's SD card IO.",
                "hearth/ingest", ("ingest", "batching"),
                (("derived_from", "postgres-decision"),)),
        ),
    ),
    Turn(
        12,
        "Two automations keep fighting over the same light switch. How do we "
        "serialize their writes?",
        reply_records=(
            Rec("locking-lesson", "lesson", "Row locks serialize automation writes",
                "Serialize competing automation writes with SELECT FOR UPDATE on the "
                "device_state row so two rules cannot flip the same switch "
                "concurrently.",
                "hearth/rules", ("locking",), (("derived_from", "postgres-decision"),)),
        ),
    ),
    Turn(
        13,
        "What's the backup story for the hub database?",
        reply_records=(
            Rec("backup-plan", "plan", "Nightly dump to the NAS",
                "Nightly pg_dump of the hub database to the NAS over the LAN, "
                "keeping fourteen rotations; restores get rehearsed monthly.",
                "hearth/storage", ("backup",), (("relates_to", "postgres-decision"),)),
        ),
    ),
    Turn(
        14,
        "Add a guest mode — when visitors come over, keep the porch and hallway "
        "lights on until midnight.",
        reply_records=(
            Rec("guest-mode", "plan", "Guest-mode lighting scene",
                "Guest mode keeps the porch and hallway lights on until midnight and "
                "pauses the motion-triggered off rules while active.",
                "hearth/scenes", ("lighting", "scene")),
        ),
    ),
    Turn(
        15,
        "Do we need rate limiting on the mobile app sync API?",
        reply_records=(
            Rec("ratelimit-decision", "decision", "Token-bucket rate limit on app sync",
                "Added a token-bucket rate limit of thirty requests per minute per "
                "client on the app sync API to protect the Pi under reconnect storms.",
                "hearth/api", ("rate-limit",), (("derived_from", "pi-constraint"),)),
        ),
    ),
    Turn(
        16,
        "Should the hub also speak MQTT so third-party sensors can publish into it?",
        reply_records=(
            Rec("mqtt-decision", "decision", "Embedded MQTT broker for third parties",
                "Run an embedded MQTT broker on the hub for third-party sensors, "
                "bridged into the event pipeline with per-topic allowlists.",
                "hearth/api", ("mqtt",), (("derived_from", "local-first"),)),
        ),
    ),
    Turn(
        17,
        "What do I have Thursday evening — could I schedule the firmware flash "
        "for the sensors then?",
        reply_records=(
            Rec("flash-decision", "decision", "Firmware flash moved off Thursday",
                "Scheduled the sensor firmware flash for Friday morning instead of "
                "Thursday evening, which is blocked by a family commitment.",
                "hearth/ops", ("firmware",), (("derived_from", "piano"),)),
        ),
        note="REACTIVATION — an indirect scheduling cue should re-lift the turn-2 recital fact",
    ),
    Turn(
        18,
        "Write the key decisions into the README so contributors see the "
        "rationale.",
        reply_records=(
            Rec("readme-summary", "summary", "README: key decisions",
                "README now records the load-bearing decisions: PostgreSQL for "
                "concurrent writers, Zigbee for battery sensors with WiFi cameras, "
                "and the token-bucket rate limit on app sync.",
                "hearth/docs", ("readme",),
                (("summarizes", "postgres-decision"),
                 ("summarizes", "zigbee-decision"),
                 ("summarizes", "ratelimit-decision"))),
        ),
    ),
    Turn(
        19,
        "Quick sanity check before I log off — which database did we pick for "
        "the hub again, and why?",
        reply_records=(
            Rec("storage-confirm", "answer", "Storage choice reconfirmed",
                "Reconfirmed: the hub runs PostgreSQL because sensor ingest, the "
                "rule engine, and app sync write concurrently; SQLite's single "
                "writer could not keep up.",
                "hearth/storage", ("postgresql",),
                (("relates_to", "postgres-decision"),)),
        ),
        note="CROSS-TURN RECALL, 14 turns later — the decision plus its rationale come back",
    ),
)


# ---------------------------------------------------------------------------
# Host loop
# ---------------------------------------------------------------------------


class Host:
    """The minimal realistic host: forms records, reconstructs with the
    turn's question, renders the top handles, commits exactly those."""

    def __init__(self, system: MemorySystem) -> None:
        self.system = system
        self.graph_ids: Dict[str, str] = {}
        self.labels: Dict[str, str] = {}  # graph id -> label
        self.commit_counts: Dict[str, int] = {}
        self.seen_warnings: set = set()

    def label_of(self, handle) -> str:
        gid = handle.provenance.get("record_id") if isinstance(handle.provenance, dict) else None
        return self.labels.get(str(gid or ""), handle.record_id[:10])

    def form(self, records: Sequence[Rec], turn_n: int) -> None:
        # Sequential formation: edge targets must already exist, so records
        # that reference same-turn siblings are formed one remember() at a
        # time under per-label idempotency keys (replays stay no-ops).
        for rec in records:
            record = MemoryRecordInput(
                kind=rec.kind, title=rec.title, digest=rec.digest,
                keywords=rec.keywords, topic=rec.topic,
                edges=tuple((rel, self.graph_ids[t]) for rel, t in rec.edges),
                provenance={"turn": turn_n},
            )
            gid = self.system.remember(
                record, scope=SCOPE, owner_id=OWNER,
                idempotency_key=f"{SESSION}:{rec.label}", turn_id=f"t{turn_n:02d}",
            )
            self.graph_ids[rec.label] = gid
            self.labels[gid] = rec.label

    def run_turn(self, turn: Turn) -> ReconstructionResult:
        if turn.refocus_reason:
            self.system.refocus(reason=turn.refocus_reason, scope=SCOPE, owner_id=OWNER)
        self.form(turn.user_records, turn.n)   # user-stated: recallable NOW
        result = self.system.reconstruct(
            Stimulus(cue_text=turn.user_text, turn_id=f"t{turn.n:02d}"),
            scopes=[(SCOPE, OWNER)], budget=TURN_BUDGET, view="working_set",
            trace_id=f"{SESSION}:t{turn.n:02d}",
        )
        rendered = self.render_selection(result)
        self.form(turn.reply_records, turn.n)  # reply-derived: exist only now
        # ONE commit for the turn's context: rendered handles (assertion-id
        # namespace) + reply records (graph-id namespace — both accepted).
        used = [h.record_id for h in rendered] + [
            self.graph_ids[rec.label] for rec in turn.reply_records
        ]
        if used:
            self.system.commit_selection(
                result.trace_id, used,
                prompt_token_estimate=sum(h.token_estimate for h in rendered),
            )
            for label in [self.label_of(h) for h in rendered] + [r.label for r in turn.reply_records]:
                self.commit_counts[label] = self.commit_counts.get(label, 0) + 1
        self.print_turn(turn, result, rendered)
        return result

    def render_selection(self, result: ReconstructionResult) -> List:
        """What actually enters the prompt: top handles by fused relevance
        (shelf order breaks ties). The host re-ranks because shelf order
        places kind rank above fused relevance among channel-matched
        candidates — with a realistic embedder (high cosine baseline, so
        nearly everything channel-matches) that lets stale instructions
        outrank the direct answer to the current question."""
        indexed = list(enumerate(result.handles))
        indexed.sort(key=lambda p: (-max(p[1].relevance.values(), default=0.0), p[0]))
        return [h for _, h in indexed[:COMMIT_TOP]]

    # -- output -------------------------------------------------------------

    def print_turn(self, turn: Turn, result: ReconstructionResult, rendered: List) -> None:
        print("\n" + "─" * 78)
        print(f"Turn {turn.n:02d} · user: {turn.user_text!r}")
        if turn.refocus_reason:
            print(f"  refocus: {turn.refocus_reason}")
        for phase, records in (("user ", turn.user_records), ("reply", turn.reply_records)):
            for rec in records:
                edges = "  ".join(f"[{rel} -> {t}]" for rel, t in rec.edges)
                print(f"  formed ({phase.strip()}-stated): {rec.kind:<11s} {rec.title}"
                      + (f"  {edges}" if edges else ""))
        print(f"  working set ({len(result.handles)} handles, "
              f"{result.budget_spent.get('tokens_used')}/{TURN_BUDGET.token_budget} tokens, "
              f"stop={result.stop_reason}):")
        rendered_ids = {h.record_id for h in rendered}
        for h in result.handles:
            mark = "»" if h.record_id in rendered_ids else " "
            rel = " ".join(f"{k[0]}={v:.2f}" for k, v in sorted(h.relevance.items()))
            act = h.activation
            cue = h.cues[0] if h.cues else ""
            print(f"   {mark} {self.label_of(h):<18s} {h.kind:<11s} "
                  f"act {act['base_level']:5.2f}+{act['spread']:4.2f}  {rel:<22s} {cue}")
        committed = [self.label_of(h) for h in rendered] + [r.label for r in turn.reply_records]
        print(f"  context committed: {', '.join(dict.fromkeys(committed))}")
        new_warnings = [w for w in result.warnings if w not in self.seen_warnings]
        self.seen_warnings.update(new_warnings)
        for w in new_warnings:
            print(f"  engine warning (first occurrence): {w}")
        if turn.note:
            print(f"  WATCH: {turn.note}")

    def print_membership(self, tag: str) -> List[str]:
        result = self.system.reconstruct(
            Stimulus(cue_text=""), scopes=[(SCOPE, OWNER)],
            budget=MEMBERSHIP_BUDGET, view="working_set", journal=False,
            trace_id=f"{SESSION}:membership",
        )
        members = [self.label_of(h) for h in result.handles]
        print("\n" + "=" * 78)
        print(f"WORKING MEMORY {tag} (blank cue, min_activation="
              f"{MEMBERSHIP_BUDGET.min_activation}) — emergent membership:")
        for h in result.handles:
            print(f"    {self.label_of(h):<18s} {h.kind:<11s} "
                  f"base {h.activation['base_level']:5.2f}")
        detour = [m for m in members if m in ("tax-question", "tax-answer", "homeoffice-answer")]
        print(f"  tax-detour records present: {detour or 'none'}")
        return members

    def print_summary(self, final_members: List[str]) -> None:
        print("\n" + "=" * 78)
        print("SESSION SUMMARY — one durable graph, usage-weighted")
        print(f"{'label':<20s} {'kind':<11s} {'turn':>4s} {'commits':>7s} "
              f"{'final act':>9s} {'in final WM':>11s}")
        acts = self.system.activation(scope=SCOPE, owner_id=OWNER)
        by_assertion: Dict[str, float] = dict(acts)
        for turn in TURNS:
            for rec in turn.records:
                gid = self.graph_ids[rec.label]
                # activation() accepts graph ids too; use the cheap path we
                # already have (the unfiltered map keys on assertion ids).
                level = self.system.activation([gid], scope=SCOPE, owner_id=OWNER)[gid]["base_level"] \
                    if by_assertion else 0.0
                print(f"{rec.label:<20s} {rec.kind:<11s} {turn.n:>4d} "
                      f"{self.commit_counts.get(rec.label, 0):>7d} "
                      f"{level:>9.2f} {'yes' if rec.label in final_members else '—':>11s}")


def main() -> int:
    embedder, embedder_desc = detect_embedder()
    print(f"AbstractMemory realistic session · embedder: {embedder_desc}")
    print(f"scope=({SCOPE!r}, {OWNER!r}) · budget: shelf={TURN_BUDGET.shelf_size}, "
          f"tokens={TURN_BUDGET.token_budget} · host renders top {COMMIT_TOP}")

    store = InMemoryTripleStore(embedder=embedder)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # volatility #FALLBACK (demo store)
        journal = InMemoryJournal()
    print("note: InMemoryJournal/InMemoryTripleStore are volatile demo substrates "
          "(#FALLBACK) — production hosts use the SQLite pair.")
    system = MemorySystem(store=store, journal=journal, embedder=embedder)
    host = Host(system)

    for turn in TURNS[:9]:
        host.run_turn(turn)
    host.print_membership("right after the tax detour (turn 9)")

    for turn in TURNS[9:]:
        host.run_turn(turn)
    final_members = host.print_membership("at session end (turn 19)")

    host.print_summary(final_members)
    print("\nDone. Storage never decayed — every record above remains reachable by "
          "a matching cue; only its working-memory standing moved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
