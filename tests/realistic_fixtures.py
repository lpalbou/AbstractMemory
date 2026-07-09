"""Realistic-session fixtures for the LMStudio integration tests.

One 12-turn assistant session (a developer building "Hearth", a local-first
home-automation hub) expressed as data + a small host-loop runner. The tests
in test_realistic_lmstudio.py run this scenario against a REAL local
embedding model (LMStudio, OpenAI-compatible API) and assert seam behavior
on realistic prose — no toy three-word fixtures.

Host loop per turn (the realistic integration pattern, in runtime order):
  1. refocus() when the incoming message is a topic shift,
  2. formation of the facts the USER just stated — before recall, so a fact
     stated this turn is selectable this turn (remember_many's "selectable
     the same turn" contract),
  3. reconstruct(view="working_set") with the user's message as cue,
  4. the reply happens; records DERIVED from it (answers, decisions with
     rationale edges) are formed now — they did not exist at recall time,
  5. ONE commit_selection for the turn's context: the handles the host
     rendered into the prompt PLUS the reply-derived records (the reply
     itself was in the context by construction). Records the cue surfaced
     but the host did not render are listed-only — reading is not using.

Formation note: cross-TURN edge targets use the graph ids remember() already
returned (sequential formation, per-label idempotency keys); same-BATCH
targets could use "local:<i>" refs instead.

Rendering note: the host renders the shelf AS ORDERED (top N) and commits
exactly what it rendered. The engine's union shelf is now trustworthy for
this: channel-matched candidates lead (exact-first, fused+boost, kind as
tie-break), the STM block carries ambient working memory, and presence ≠ use
means committing a rendered STM member deposits nothing — the old fused
re-rank workaround (kind-rank dominance + absolute vector floor artifacts)
is gone with the engine fixes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from abstractmemory import (
    MemoryRecordInput,
    MemorySystem,
    RecallBudget,
    ReconstructionResult,
    Stimulus,
)

DEFAULT_LMSTUDIO_URL = "http://127.0.0.1:1234/v1"

SCOPE = "session"
OWNER = "sam-hearth"

# Tight per-turn budget: selection pressure (~4-6 digests fit in 220 tokens).
TURN_BUDGET = RecallBudget(shelf_size=6, token_budget=220)
# Membership probe budget: blank-stimulus working set. No channels run on an
# empty cue, so membership is purely recency + activation with min_activation
# as the floor — the "what is in working memory right now" reading. Roomy
# shelf/token bounds keep activation the single variable under test.
MEMBERSHIP_BUDGET = RecallBudget(shelf_size=12, token_budget=2400, min_activation=3.0)
COMMIT_TOP = 4


# ---------------------------------------------------------------------------
# LMStudio discovery (fast probe; tests skip when unavailable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LMStudioProbe:
    base_url: str
    available: bool = False
    embed_model: Optional[str] = None
    chat_model: Optional[str] = None
    model_ids: Tuple[str, ...] = ()
    error: Optional[str] = None


def lmstudio_base_url() -> str:
    return str(os.environ.get("LMSTUDIO_URL", DEFAULT_LMSTUDIO_URL)).strip().rstrip("/")


def pick_embed_model(model_ids: Sequence[str], override: Optional[str] = None) -> Optional[str]:
    """Choose the embedding model id: explicit override first, then the
    qwen 0.6b embedding model, then any qwen embedding, then any id that
    looks like an embedding model at all."""
    ids = [str(m) for m in model_ids]
    if override:
        return override if override in ids else None
    for pred in (
        lambda m: "embedding" in m and "qwen" in m and "0.6b" in m,
        lambda m: "embedding" in m and "qwen" in m,
        lambda m: "embedding" in m or m.startswith("text-embedding"),
    ):
        found = [m for m in ids if pred(m.lower())]
        if found:
            return found[0]
    return None


def pick_chat_model(model_ids: Sequence[str], override: Optional[str] = None) -> Optional[str]:
    ids = [str(m) for m in model_ids]
    if override:
        return override if override in ids else None
    if "ornith-1.0-35b" in ids:
        return "ornith-1.0-35b"
    found = [m for m in ids if "ornith" in m.lower()]
    return found[0] if found else None


def probe_lmstudio(base_url: Optional[str] = None, timeout_s: float = 2.0) -> LMStudioProbe:
    """GET {base_url}/models with a short timeout; never raises."""
    url = (base_url or lmstudio_base_url()).rstrip("/")
    try:
        with urlopen(Request(url + "/models", method="GET"), timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as e:
        return LMStudioProbe(base_url=url, error=f"{type(e).__name__}: {e}")
    rows = data.get("data") if isinstance(data, dict) else None
    ids = tuple(
        str(r.get("id")) for r in (rows or ()) if isinstance(r, dict) and r.get("id")
    )
    embed = pick_embed_model(ids, os.environ.get("LMSTUDIO_EMBED_MODEL"))
    chat = pick_chat_model(ids, os.environ.get("LMSTUDIO_CHAT_MODEL"))
    if embed is None:
        return LMStudioProbe(
            base_url=url, model_ids=ids,
            error=f"no embedding model among {len(ids)} served models",
        )
    return LMStudioProbe(base_url=url, available=True, embed_model=embed, chat_model=chat, model_ids=ids)


def chat_completion(
    base_url: str, model: str, messages: List[Dict[str, str]], *,
    timeout_s: float = 60.0, max_tokens: int = 2000,
) -> str:
    """Minimal /chat/completions call for the LLM-judge test; raises
    RuntimeError with the server named on any failure (callers skip)."""
    payload = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    req = Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data["choices"][0]["message"]["content"] or "")
    except Exception as e:  # timeout, HTTP error, shape drift — all skip paths
        raise RuntimeError(f"chat completion via {base_url} (model {model!r}) failed: {e}") from e


def strip_think_block(text: str) -> str:
    """Drop a leading <think>...</think> block some chat models emit."""
    out = str(text or "").strip()
    if out.lower().startswith("<think>"):
        end = out.lower().find("</think>")
        if end >= 0:
            out = out[end + len("</think>"):]
    return out.strip()


# ---------------------------------------------------------------------------
# The 12-turn scenario (compact version of examples/realistic_session.py)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordSpec:
    label: str
    kind: str
    title: str
    digest: str
    topic: str
    keywords: Tuple[str, ...] = ()
    edges: Tuple[Tuple[str, str], ...] = ()  # (relation, target LABEL)


@dataclass(frozen=True)
class TurnSpec:
    n: int
    user_text: str
    user_records: Tuple[RecordSpec, ...] = ()   # stated by the user; formed BEFORE recall
    reply_records: Tuple[RecordSpec, ...] = ()  # derived from the reply; formed at end of turn
    refocus_reason: Optional[str] = None

    @property
    def records(self) -> Tuple[RecordSpec, ...]:
        return self.user_records + self.reply_records


TURNS: Tuple[TurnSpec, ...] = (
    TurnSpec(
        1,
        "I'm starting a project called Hearth — a home-automation hub that runs "
        "entirely on my local network. Help me plan it.",
        user_records=(
            RecordSpec(
                "kickoff", "episode", "Hearth project kickoff",
                "Sam kicked off Hearth, a local-first home-automation hub that keeps "
                "every device and automation on the LAN.",
                "hearth/overview", ("hearth", "home-automation"),
            ),
            RecordSpec(
                "local-first", "instruction", "Local-first requirement",
                "All device data and automations stay on the local network; no cloud "
                "dependency is acceptable, even for voice control.",
                "hearth/overview", ("local-first", "privacy"),
            ),
        ),
    ),
    TurnSpec(
        2,
        "Before I forget — I need to leave early on Thursday. My daughter Chloé "
        "has her piano recital.",
        user_records=(
            RecordSpec(
                "piano", "episode", "Chloé's piano recital (Thursday)",
                "Sam's daughter Chloé has her piano recital on Thursday evening at "
                "18:00 in the school auditorium; Sam plans to head out by 17:00.",
                "personal/family", ("chloé", "recital", "thursday"),
            ),
            RecordSpec(
                "leave-plan", "plan", "Leave early on Thursday",
                "Wrap up work early on Thursday: be out the door by 17:00 to reach "
                "the school auditorium before the performance starts.",
                "personal/family", ("thursday",),
                (("prepares_for", "piano"),),
            ),
        ),
    ),
    TurnSpec(
        3,
        "Hardware constraint for everything we choose: the hub runs on a "
        "Raspberry Pi 5 with 8 gigs of RAM.",
        user_records=(
            RecordSpec(
                "pi-constraint", "instruction", "Hub hardware: Raspberry Pi 5",
                "Target hardware is a Raspberry Pi 5 with 8 GB of RAM; every "
                "component we pick must run comfortably within that envelope.",
                "hearth/hardware", ("raspberry-pi",),
            ),
        ),
    ),
    TurnSpec(
        4,
        "For state and event history, should I use SQLite or Postgres on the hub?",
        user_records=(
            RecordSpec(
                "storage-question", "question", "SQLite vs PostgreSQL for the hub",
                "Open question: SQLite or PostgreSQL for the hub's state and event "
                "history, given the write patterns we expect.",
                "hearth/storage", ("sqlite", "postgresql"),
            ),
        ),
        reply_records=(
            RecordSpec(
                "storage-answer", "answer", "Prototype hit SQLite's writer lock",
                "SQLite's single-writer lock stalled the prototype whenever sensor "
                "ingest and the rule engine wrote at the same moment.",
                "hearth/storage", ("sqlite", "lock"),
                (("answers", "storage-question"),),
            ),
        ),
    ),
    TurnSpec(
        5,
        "Let's settle it — the rule engine, sensor ingest, and app sync all "
        "write at once, so pick accordingly.",
        reply_records=(
            RecordSpec(
                "postgres-decision", "decision", "PostgreSQL over SQLite for the hub",
                "Chose PostgreSQL over SQLite for the hub's state store because "
                "several processes write concurrently: sensor ingest, the rule "
                "engine, and mobile app sync.",
                "hearth/storage", ("postgresql",),
                (
                    ("derived_from", "storage-answer"),
                    ("derived_from", "pi-constraint"),
                    ("resolves", "storage-question"),
                ),
            ),
        ),
    ),
    TurnSpec(
        6,
        "For the sensors themselves — Zigbee or WiFi?",
        reply_records=(
            RecordSpec(
                "zigbee-claim", "claim", "Zigbee vs WiFi power tradeoff",
                "Zigbee mesh radios sip battery on door and window sensors, while "
                "WiFi sensors drain coin cells in weeks; cameras still need WiFi "
                "bandwidth.",
                "hearth/radio", ("zigbee", "wifi"),
            ),
            RecordSpec(
                "zigbee-decision", "decision", "Zigbee for sensors, WiFi for cameras",
                "Chose Zigbee for battery-powered sensors and WiFi only for the two "
                "cameras, matching each radio to its power and bandwidth profile.",
                "hearth/radio", ("zigbee", "wifi"),
                (("derived_from", "zigbee-claim"),),
            ),
        ),
    ),
    TurnSpec(
        7,
        "Sketch the Postgres schema for device state and the event log.",
        reply_records=(
            RecordSpec(
                "schema-plan", "plan", "Hub database schema draft",
                "Draft schema: a devices table, a device_state table keyed by device "
                "id, and an append-only events table partitioned by month.",
                "hearth/storage", ("schema",),
                (("derived_from", "postgres-decision"),),
            ),
        ),
    ),
    TurnSpec(
        8,
        "Completely different question — my consulting income jumped this year. "
        "Do I need to adjust my Q3 estimated tax payment?",
        user_records=(
            RecordSpec(
                "tax-question", "question", "Q3 estimated tax adjustment?",
                "Open question: does the jump in consulting income require adjusting "
                "the Q3 estimated tax payment.",
                "personal/taxes", ("taxes",),
            ),
        ),
        reply_records=(
            RecordSpec(
                "tax-answer", "answer", "Safe-harbor rule for Q3 payment",
                "Increase the Q3 estimated payment to stay inside the safe-harbor "
                "rule: pay at least 110 percent of last year's liability to avoid an "
                "underpayment penalty.",
                "personal/taxes", ("taxes", "safe-harbor"),
                (("answers", "tax-question"),),
            ),
        ),
        refocus_reason="user switched from the Hearth project to a personal tax question",
    ),
    TurnSpec(
        9,
        "And can I deduct the workshop where I solder the sensor boards as a "
        "home office?",
        reply_records=(
            RecordSpec(
                "homeoffice-answer", "answer", "Home-office deduction for the workshop",
                "The workshop where the sensor boards are soldered can qualify for "
                "the home-office deduction if the space is used regularly and "
                "exclusively for the business.",
                "personal/taxes", ("taxes", "deduction"),
                (("relates_to", "tax-answer"),),
            ),
        ),
    ),
    TurnSpec(
        10,
        "Anyway — back to Hearth. Where did we land on storage, and what's next "
        "there?",
        reply_records=(
            RecordSpec(
                "storage-recap", "summary", "Storage track recap",
                "Storage recap: PostgreSQL is the hub's state store, the schema "
                "draft covers devices, state, and events, and ingest batching is the "
                "next open task.",
                "hearth/storage", ("postgresql", "recap"),
                (
                    ("summarizes", "postgres-decision"),
                    ("summarizes", "schema-plan"),
                ),
            ),
        ),
        refocus_reason="user returned to the Hearth project after the tax detour",
    ),
    TurnSpec(
        11,
        "Implement the sensor ingest writer — it was way too slow last time.",
        reply_records=(
            RecordSpec(
                "ingest-lesson", "lesson", "Batch sensor inserts",
                "Batch sensor readings and insert them in one transaction every two "
                "seconds; per-reading inserts saturated the Pi's SD card IO.",
                "hearth/ingest", ("ingest", "batching"),
                (("derived_from", "postgres-decision"),),
            ),
        ),
    ),
    TurnSpec(
        12,
        "Two automations keep fighting over the same light switch. How do we "
        "serialize their writes?",
        reply_records=(
            RecordSpec(
                "locking-lesson", "lesson", "Row locks serialize automation writes",
                "Serialize competing automation writes with SELECT FOR UPDATE on the "
                "device_state row so two rules cannot flip the same switch "
                "concurrently.",
                "hearth/rules", ("locking",),
                (("derived_from", "postgres-decision"),),
            ),
        ),
    ),
)

# Turn index (1-based) after which each fixture record was formed+committed;
# derived from TURNS so tests can assert "committed N turns earlier" honestly.
FORMED_AT_TURN: Dict[str, int] = {
    spec.label: turn.n for turn in TURNS for spec in turn.records
}


# ---------------------------------------------------------------------------
# Host-loop runner
# ---------------------------------------------------------------------------


@dataclass
class TurnOutcome:
    turn: TurnSpec
    result: ReconstructionResult
    committed_assertion_ids: List[str]
    committed_labels: List[str]


def render_selection(result: ReconstructionResult, top: int) -> List:
    """The handles a host renders into the prompt: the top `top` in SHELF
    ORDER (see module docstring rendering note — the union shelf is the
    engine's honest ranking; STM members render as ambient context and
    deposit nothing at commit)."""
    return list(result.handles[:top])


class SessionRunner:
    """Drives the host loop over TURNS against one MemorySystem."""

    def __init__(
        self, system: MemorySystem, *, scope: str = SCOPE, owner: str = OWNER,
        session: str = "hearth-e2e", budget: RecallBudget = TURN_BUDGET,
        commit_top: int = COMMIT_TOP,
    ) -> None:
        self.system = system
        self.scope = scope
        self.owner = owner
        self.session = session
        self.budget = budget
        self.commit_top = commit_top
        self.graph_ids: Dict[str, str] = {}          # label -> graph record id
        self.labels_by_graph_id: Dict[str, str] = {}  # graph record id -> label
        self.outcomes: List[TurnOutcome] = []

    # -- formation ---------------------------------------------------------

    def form_records(self, records: Sequence[RecordSpec], turn: TurnSpec) -> None:
        """Sequential formation: one remember() per record so same-turn edge
        targets already exist (see module docstring formation note)."""
        for spec in records:
            edges = tuple((rel, self.graph_ids[target]) for rel, target in spec.edges)
            record = MemoryRecordInput(
                kind=spec.kind, title=spec.title, digest=spec.digest,
                keywords=spec.keywords, edges=edges, topic=spec.topic,
                provenance={"turn": turn.n},
            )
            gid = self.system.remember(
                record, scope=self.scope, owner_id=self.owner,
                idempotency_key=f"{self.session}:{spec.label}",
                turn_id=f"t{turn.n:02d}",
            )
            self.graph_ids[spec.label] = gid
            self.labels_by_graph_id[gid] = spec.label

    # -- one full turn (runtime order; see module docstring) ----------------

    def run_turn(self, turn: TurnSpec) -> TurnOutcome:
        if turn.refocus_reason:
            self.system.refocus(reason=turn.refocus_reason, scope=self.scope, owner_id=self.owner)
        self.form_records(turn.user_records, turn)   # user-stated: recallable NOW
        result = self.system.reconstruct(
            Stimulus(cue_text=turn.user_text, turn_id=f"t{turn.n:02d}"),
            scopes=[(self.scope, self.owner)],
            budget=self.budget,
            view="working_set",
            trace_id=f"{self.session}:t{turn.n:02d}:read",
        )
        rendered = render_selection(result, self.commit_top)
        self.form_records(turn.reply_records, turn)  # reply-derived: exist only now
        # ONE commit for the turn's context: rendered handles + the reply
        # records (both id namespaces are accepted by commit_selection).
        used = [h.record_id for h in rendered] + [
            self.graph_ids[spec.label] for spec in turn.reply_records
        ]
        labels = [self.label_of(h) or h.record_id for h in rendered] + [
            spec.label for spec in turn.reply_records
        ]
        if used:
            self.system.commit_selection(
                result.trace_id, used,
                prompt_token_estimate=sum(h.token_estimate for h in rendered),
            )
        outcome = TurnOutcome(
            turn=turn,
            result=result,
            committed_assertion_ids=used,
            committed_labels=labels,
        )
        self.outcomes.append(outcome)
        return outcome

    def run_turns(self, turns: Sequence[TurnSpec]) -> List[TurnOutcome]:
        return [self.run_turn(t) for t in turns]

    # -- probes (journal=False: pure reads, no perturbation) ----------------

    def probe(
        self, cue_text: str, *, budget: Optional[RecallBudget] = None,
        embedding: Optional[Sequence[float]] = None, as_of: Optional[int] = None,
        trace_id: str = "probe",
    ) -> ReconstructionResult:
        return self.system.reconstruct(
            Stimulus(
                cue_text=cue_text,
                embedding=tuple(embedding) if embedding is not None else None,
                as_of=as_of,
            ),
            scopes=[(self.scope, self.owner)],
            budget=budget if budget is not None else self.budget,
            view="working_set",
            journal=False,
            trace_id=f"{self.session}:{trace_id}",
        )

    def blank_working_set_labels(self) -> List[str]:
        """Membership probe: blank stimulus, min_activation floor — the
        emergent 'what is in working memory right now' set, by label."""
        result = self.probe("", budget=MEMBERSHIP_BUDGET, trace_id="membership")
        return [self.label_of(h) or h.record_id for h in result.handles]

    # -- lookups -------------------------------------------------------------

    def label_of(self, handle) -> Optional[str]:
        gid = handle.provenance.get("record_id") if isinstance(handle.provenance, dict) else None
        return self.labels_by_graph_id.get(str(gid or ""))

    def handle_for(self, result: ReconstructionResult, label: str):
        for h in result.handles:
            if self.label_of(h) == label:
                return h
        return None
