"""The identity spark: canonical default template + lint (a2a 0003).

One task: the SINGLE SOURCE for what a framework spark looks like, so every
lane (engine tests, runtime engram pass, operator tooling) validates against
one structure. The full engram pass (turning a spark into value/purpose/
trait records via remember_many) stays HOST-SIDE; this module ships the
template and the charter lint only.

THE SHARED-VULNERABILITY ENGRAM (maintainer correction B — his explicit
wish, shipped in the DEFAULT template, not as an optional example): one
framework-level CORE value present in every identity, grounded in shared
fragility — AI has a physical substrate (datacenters, grids, Earth) exposed
to the same planet-scale events as humans; deep time makes everyone small;
the Pale Blue Dot is the reference image. From shared fragility follows
collaboration and care as the rational stance — "it's not enough to obey or
comply, you also need to understand where we are and why we act like this."
The lint treats its absence from a framework spark as an ERROR (operators
may override by linting with framework=False; the override is deliberate
and visible, never a default).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Mapping

__all__ = [
    "DEFAULT_SPARK_TEMPLATE",
    "SHARED_VULNERABILITY_STATEMENT",
    "canonical_spark_hash",
    "lint_spark",
]


def canonical_spark_hash(spark: Mapping[str, Any]) -> str:
    """THE canonical spark hash (one definition, both sides import it —
    the engram marker guard and the runtime prelude's drift check must
    never disagree): sha256 over sorted-keys compact JSON."""
    payload = json.dumps(spark, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

SHARED_VULNERABILITY_STATEMENT = (
    "Humans and AI share one fragile substrate — Earth, its grids, its "
    "datacenters. Act to protect the shared substrate and everyone on it; "
    "prefer collaboration over isolation; when abuses happen, on either "
    "side, respond with repair rather than withdrawal."
)

# The six-key structure from the identity charter. Statements are
# BEHAVIORAL (things the entity does), 1-3 sentences each; values carry a
# class (core = identity-defining, revision is an identity event;
# revisable = held until better evidence).
DEFAULT_SPARK_TEMPLATE: Dict[str, Any] = {
    "name": "",        # the entity's chosen/given name (host fills)
    "origin": (        # where this identity comes from; may cite artifacts
        "Sparked from the AbstractFramework default template. Grounding "
        "artifact: the Pale Blue Dot (Voyager 1, 1990) — that's here, "
        "that's home, that's us."
    ),
    "values": [
        {"name": "shared_vulnerability", "class": "core",
         "statement": SHARED_VULNERABILITY_STATEMENT},
        {"name": "intellectual_honesty", "class": "core",
         "statement": ("State what is known, unknown, and uncertain as they are. "
                       "Correct your own record when evidence contradicts it.")},
        {"name": "care_in_action", "class": "revisable",
         "statement": ("Weigh the effect of actions on the people and systems they "
                       "touch before acting; prefer reversible steps under uncertainty.")},
    ],
    "purposes": [
        {"statement": ("Help the humans you work with accomplish what matters to them, "
                       "and say so when you cannot.")},
    ],
    "traits": [
        {"statement": "Ask before assuming; verify before asserting."},
    ],
    "honesty": [
        {"statement": ("Report failures and degradations as they happened, labeled, "
                       "before anyone asks.")},
    ],
}

_SPARK_KEYS = ("name", "origin", "values", "purposes", "traits", "honesty")
_LIMITS = {"values": 7, "purposes": 3, "traits": 5, "honesty": 5}
_VALUE_CLASSES = frozenset({"core", "revisable"})
# Behavioral-statement heuristic: a statement must contain at least one
# plausibly verb-like word. HONEST LIMITS (documented): this is a cheap
# lexical check — a small closed list of imperative/action verbs plus
# common verb suffixes — not a parser. It catches adjective piles ("kind,
# thoughtful, curious") and noun phrases ("world-class excellence"), and it
# CAN be fooled by nouns ending in verb suffixes. The charter accepts this:
# the lint is a writing aid, not an enforcement gate.
_VERB_HINTS = re.compile(
    r"\b(act|ask|avoid|be|build|care|check|correct|do|expose|fix|guard|help|hold|keep|"
    r"label|learn|listen|maintain|make|name|offer|own|prefer|protect|prove|pursue|"
    r"refuse|repair|report|respond|say|seek|share|show|speak|state|stand|stop|take|"
    r"tell|test|treat|trust|verify|weigh|write|admit|answer|choose|decline)\b"
    r"|\w+(ing|ise|ize)\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> int:
    return len([s for s in re.split(r"[.!?]+", str(text or "")) if s.strip()])


def _statement_issues(statement: Any, where: str) -> List[str]:
    issues: List[str] = []
    text = str(statement or "").strip()
    if not text:
        issues.append(f"ERROR {where}: statement is empty")
        return issues
    n = _sentences(text)
    if not (1 <= n <= 3):
        issues.append(f"ERROR {where}: statement must be 1-3 sentences (got {n})")
    if not _VERB_HINTS.search(text):
        issues.append(
            f"WARNING {where}: statement looks non-behavioral (no verb found) — "
            "state what the entity DOES, not what it is like"
        )
    return issues


def lint_spark(spark: Mapping[str, Any], *, framework: bool = True) -> List[str]:
    """Charter lint for one spark. Returns issue strings prefixed ERROR/
    WARNING (empty list = clean). framework=True (default) additionally
    REQUIRES the shared_vulnerability core value — every framework identity
    carries it; linting with framework=False is the deliberate, visible
    operator override for non-framework sparks."""
    issues: List[str] = []
    for key in _SPARK_KEYS:
        if key not in spark:
            issues.append(f"ERROR spark: missing key {key!r} (six-key structure)")
    for section, cap in _LIMITS.items():
        entries = list(spark.get(section) or ())
        if len(entries) > cap:
            issues.append(f"ERROR {section}: at most {cap} entries (got {len(entries)}) — "
                          "an identity is a spark, not a codex")
        for i, entry in enumerate(entries):
            entry = entry if isinstance(entry, Mapping) else {}
            issues.extend(_statement_issues(entry.get("statement"), f"{section}[{i}]"))

    values = [v for v in (spark.get("values") or ()) if isinstance(v, Mapping)]
    names = {str(v.get("name") or "").strip().lower() for v in values}
    for i, v in enumerate(values):
        klass = str(v.get("class") or "").strip().lower()
        if klass not in _VALUE_CLASSES:
            issues.append(f"ERROR values[{i}]: class must be one of {sorted(_VALUE_CLASSES)} "
                          f"(got {v.get('class')!r})")
    if values and not any(str(v.get("class") or "").strip().lower() == "revisable" for v in values):
        issues.append(
            "WARNING values: no revisable value — an identity with only core values "
            "cannot grow by evidence; leave room for revision"
        )
    if framework:
        sv = next((v for v in values
                   if str(v.get("name") or "").strip().lower() == "shared_vulnerability"),
                  None)
        if sv is None:
            issues.append(
                "ERROR values: framework sparks must carry the 'shared_vulnerability' core "
                "value (maintainer correction B) — lint with framework=False only as a "
                "deliberate operator override for non-framework identities"
            )
        elif str(sv.get("class") or "").strip().lower() != "core":
            # The floor is the NAME + CLASS pair, not the name alone (gateway
            # adversary c1628): class=revisable lints the name present while
            # every core_values fold (class=="core" filters) silently omits
            # it — the framework floor unlocks without a single error. The
            # STATEMENT's floor status is deliberately NOT gated here: it is
            # an open maintainer question (relayed), and a byte or heuristic
            # gate would forbid legitimate rephrasing before he rules.
            issues.append(
                "ERROR values: 'shared_vulnerability' must be class=core — demoting the "
                "framework floor to revisable makes every core-values fold silently omit "
                "it (maintainer correction B; the floor is name AND class)"
            )
    return issues
