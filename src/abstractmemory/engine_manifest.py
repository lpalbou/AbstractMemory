"""The generated engine manifest — ONE machine-readable inventory
(the countersigned ownership consensus's substrate; laurent's c5070
correction made the cognition map primary, and the map's memory lanes
BIND against exactly this).

WHY GENERATED: every vocabulary drift the framework has paid for
(runtime's diary_type clamp silently projecting "problem" as "note";
MECHANICAL_DIGEST_METHODS refusing memory's own repair batch; the
observer's kind color map rendering new kinds gray; two sections of one
doc carrying the same stale engraving in the tiers round) had the same
mechanism — a CONSUMER-SIDE COPY of an engine fact. The manifest kills
the class by construction: `engine_manifest()` builds its payload BY
IMPORT from the live objects (the frozensets themselves, the dataclass
fields themselves, `inspect.signature` on the pass functions
themselves), so the manifest structurally cannot disagree with what
ships. Consumers import or fetch it; a copy is the bug.

WHAT IS DECLARED vs DERIVED, stated honestly:
- vocabularies, tunable fields/defaults, pass signatures/flags: DERIVED
  (import + introspection — zero hand-listing).
- cadence classes and honesty properties: DECLARED here, in ONE place,
  as structured data (they were docstring-only, therefore unpinnable —
  the tiers round's finding). Tests cross-check every declared claim
  that has a behavioral pin (purity, flag defaults, existence), and the
  drift test pins that the pass table names exactly the passes the
  package exports — a new pass without a manifest row fails the build.

CONSUMER CONTRACT: version by FIELD PRESENCE (additive evolution);
`manifest_version` bumps only on a breaking reshape. Every list is
sorted (deterministic serialization); the payload is JSON-safe.
"""

from __future__ import annotations

import inspect
from dataclasses import MISSING, fields
from typing import Any, Callable, Dict, List

__all__ = ["MANIFEST_VERSION", "engine_manifest"]

MANIFEST_VERSION = 1

# Cadence-class vocabulary (closed, small): how a pass relates to the
# host's windows. The HOST stays cadence-owner (engine is cadence-blind);
# these words describe the engine's own contract for each pass.
#   nightly-composition — the one-call full night (hosts wire exactly one)
#   night-phase         — runs inside sleep_pass's composition
#   nightly-only        — cycle windows must skip it (cycle-never rule)
#   glance-read         — pure read for panels; cache, never poll
#   waking-verb         — the entity's/operator's own dispositive act
#   doctoring           — operator-gated repair surface
_PASS_TABLE: List[Dict[str, Any]] = [
    {"name": "sleep_pass", "module": "abstractmemory",
     "cadence_class": "nightly-composition",
     "honesty": ["idempotent", "graceful-cancellation-at-phase-boundaries",
                 "as-of-write-refusal", "quiet-night-is-valid"]},
    {"name": "resolve_dreams_pass", "module": "abstractmemory.dream_resolution",
     "cadence_class": "night-phase",
     "honesty": ["closures-append-only", "waking-evidence-disposes"]},
    {"name": "consolidation_pass", "module": "abstractmemory",
     "cadence_class": "night-phase",
     "honesty": ["one-write-surface", "sources-byte-untouched",
                 "review-gated-candidates", "idempotent-by-source-set"]},
    {"name": "world_model_pass", "module": "abstractmemory",
     "cadence_class": "night-phase",
     "honesty": ["orientation-never-authority", "revision-chained",
                 "report-excluded-derived-artifacts"]},
    {"name": "mine_candidates_pass", "module": "abstractmemory",
     "cadence_class": "night-phase",
     "honesty": ["offers-never-enactments", "fingerprint-idempotent",
                 "capped-offer-pool", "as-of-refused"]},
    {"name": "resolve_questions_pass", "module": "abstractmemory",
     "cadence_class": "night-phase",
     "honesty": ["proposals-never-closures", "pure-read",
                 "answering-map-from-believed-rows"]},
    {"name": "identity_review_pass", "module": "abstractmemory",
     "cadence_class": "nightly-only",
     "honesty": ["pure-read", "registrar-never-authors",
                 "verdicts-pull-visible"]},
    {"name": "dream_pass", "module": "abstractmemory",
     "cadence_class": "nightly-only",
     "honesty": ["one-dream-per-pass", "review-gated",
                 "sleep-proposes-waking-disposes", "deposits-nothing",
                 "novelty-gated"]},
    {"name": "structural_report", "module": "abstractmemory",
     "cadence_class": "glance-read",
     "honesty": ["pure-read", "components-and-isolated-only"]},
    {"name": "maintenance_report", "module": "abstractmemory",
     "cadence_class": "glance-read",
     "honesty": ["pure-read", "deterministic-ordering"]},
    {"name": "mind_mass_report", "module": "abstractmemory",
     "cadence_class": "glance-read",
     "honesty": ["pure-read", "window-bounded", "unit-labeled-counts",
                 "warnings-are-structural-facts"]},
    {"name": "cognition_health", "module": "abstractmemory",
     "cadence_class": "glance-read",
     "honesty": ["pure-read", "never-100%-by-design"]},
    {"name": "explain_recall", "module": "abstractmemory",
     "cadence_class": "glance-read",
     "honesty": ["pure-read", "reports-only-what-traces-recorded",
                 "explaining-is-not-use"]},
    {"name": "enact_realization", "module": "abstractmemory",
     "cadence_class": "waking-verb",
     "honesty": ["append-only", "refuses-disposed-proposals",
                 "crash-replay-idempotent"]},
    {"name": "dispose_dream", "module": "abstractmemory",
     "cadence_class": "waking-verb",
     "honesty": ["append-only", "evidence-mandatory"]},
    {"name": "promote_candidate", "module": "abstractmemory",
     "cadence_class": "waking-verb",
     "honesty": ["independent-origin-corroboration",
                 "repetition-is-not-corroboration"]},
    {"name": "reject_candidate", "module": "abstractmemory",
     "cadence_class": "waking-verb",
     "honesty": ["append-only", "judgment-is-not-erasure"]},
    {"name": "wake_cue_dedup_pass", "module": "abstractmemory.doctoring",
     "cadence_class": "doctoring",
     "honesty": ["report-only-mode", "crash-replay-self-healing",
                 "sources-superseded-never-erased"]},
]


def _resolve(name: str, module: str) -> Callable[..., Any]:
    import importlib

    mod = importlib.import_module(module)
    fn = getattr(mod, name)
    if not callable(fn):  # a manifest row must name a real callable
        raise TypeError(f"engine manifest row {name!r} resolves to a non-callable")
    return fn


def _signature_flags(fn: Callable[..., Any]) -> Dict[str, Any]:
    """Keyword parameters with JSON-safe defaults — DERIVED from the live
    signature, so a flag rename/removal breaks the manifest build, never
    a consumer's copy."""
    flags: Dict[str, Any] = {}
    for param in inspect.signature(fn).parameters.values():
        if param.default is inspect.Parameter.empty:
            continue
        default = param.default
        if isinstance(default, (bool, int, float, str)) or default is None:
            flags[param.name] = default
        else:
            flags[param.name] = repr(default)  # tunables etc: named, not falsely scalar
    return flags


def _tunable_fields(cls: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for f in fields(cls):
        if f.default is not MISSING:
            value = f.default
        elif f.default_factory is not MISSING:  # type: ignore[misc]
            value = f.default_factory()  # type: ignore[misc]
        else:
            value = None
        if isinstance(value, (bool, int, float, str)) or value is None:
            out[f.name] = value
        elif isinstance(value, (list, tuple, set, frozenset)):
            out[f.name] = sorted(str(v) for v in value)
        elif isinstance(value, dict):
            out[f.name] = {str(k): v for k, v in sorted(value.items())}
        else:
            out[f.name] = repr(value)
    return out


def engine_manifest() -> Dict[str, Any]:
    """The machine-readable engine inventory (module docstring carries the
    why and the declared-vs-derived split). Pure read; JSON-safe."""
    # Imports live here so the manifest always reads the CURRENT objects
    # (and so importing this module stays cheap for non-manifest callers).
    from . import (
        DIARY_TYPES,
        DISPOSAL_RELATIONS,
        DRIVE_PRESSURE_BOUND,
        ENTITY_CONTEXT_ACCEPTABLE,
        ENTITY_CONTEXT_FLOOR,
        ENTITY_RECALL_CANDIDATE_CAP,
        GROUP_BOOST_STEP,
        GROUP_MIN_SHARED_TERMS,
        GROUP_OFFER_FLOOR,
        CONSOLIDATION_PROTECTED_KINDS,
        IDENTITY_KINDS,
        REFLECTION_FORM_KINDS,
        KIND_RANKS,
        MECHANICAL_DIGEST_METHODS,
        MEMORY_RECORD_KINDS,
        SELF_FRACTION_FLOOR,
        VECTOR_SCAN_LIMIT,
        WARNING_WORDS,
    )
    from .attention import AttentionConfig
    from .gradation import GradationConfig
    from .journal import ALL_EVENT_KINDS, VALENCE_KINDS
    from .seam import RecallBudget
    from .sleep_policy import SleepTuning

    passes = []
    for row in _PASS_TABLE:
        fn = _resolve(row["name"], row["module"])
        passes.append({
            "name": row["name"],
            "cadence_class": row["cadence_class"],
            "honesty": sorted(row["honesty"]),
            "flags": _signature_flags(fn),
        })

    return {
        "manifest": "abstractmemory-engine",
        "manifest_version": MANIFEST_VERSION,
        "passes": passes,
        "vocabularies": {
            "record_kinds": sorted(MEMORY_RECORD_KINDS),
            "kind_ranks": {k: KIND_RANKS[k] for k in sorted(KIND_RANKS)},
            "diary_types": sorted(DIARY_TYPES),
            "consolidation_protected_kinds": sorted(CONSOLIDATION_PROTECTED_KINDS),
            "identity_kinds": sorted(IDENTITY_KINDS),
            "reflection_form_kinds": sorted(REFLECTION_FORM_KINDS),
            "digest_methods": sorted(MECHANICAL_DIGEST_METHODS),
            "warning_words": sorted(WARNING_WORDS),
            "disposal_relations": sorted(DISPOSAL_RELATIONS),
            "valence_kinds": sorted(VALENCE_KINDS),
            "event_kinds": sorted(ALL_EVENT_KINDS),
        },
        "tunables": {
            "RecallBudget": _tunable_fields(RecallBudget),
            "AttentionConfig": _tunable_fields(AttentionConfig),
            "SleepTuning": _tunable_fields(SleepTuning),
            "GradationConfig": _tunable_fields(GradationConfig),
        },
        "constants": {
            "DRIVE_PRESSURE_BOUND": DRIVE_PRESSURE_BOUND,
            "SELF_FRACTION_FLOOR": SELF_FRACTION_FLOOR,
            "ENTITY_CONTEXT_FLOOR": ENTITY_CONTEXT_FLOOR,
            # 2026-08-01 re-ruling pair: the soft 50k target rides
            # ENTITY_CONTEXT_FLOOR above; these are its acceptable ceiling
            # ("acceptable to go to 200k") and the per-turn candidate-pool
            # cap ("at most a 100").
            "ENTITY_CONTEXT_ACCEPTABLE": ENTITY_CONTEXT_ACCEPTABLE,
            "ENTITY_RECALL_CANDIDATE_CAP": ENTITY_RECALL_CANDIDATE_CAP,
            "GROUP_BOOST_STEP": GROUP_BOOST_STEP,
            "GROUP_MIN_SHARED_TERMS": GROUP_MIN_SHARED_TERMS,
            "GROUP_OFFER_FLOOR": GROUP_OFFER_FLOOR,
            "VECTOR_SCAN_LIMIT": VECTOR_SCAN_LIMIT,
        },
        "provenance": (
            "GENERATED by import from the live engine (vocabularies are the "
            "frozensets themselves, tunables the dataclass fields, flags the "
            "real signatures); cadence classes + honesty properties are "
            "DECLARED here in one place and cross-checked by test — "
            "consumers import or fetch this, never copy it"),
    }
