"""AbstractMemory public surface.

Layer 1 (triple truth): stores, models, queries, embedders.
Layer 2 (memory system v1): the MemorySystem facade over the frozen
runtime⇄memory seam (a2a thread 0001, message 004), plus the journal
substrate and tuning configs it is built from.

Import note: `LanceDBTripleStore` is imported eagerly here (existing
behavior, preserved) but the `lancedb` dependency itself stays lazy —
`lancedb_store` only imports it when a store is actually constructed, so
this module never requires lancedb to be installed.
"""

from .attention import AttentionConfig
from .canonical_text import CANONICAL_TEXT_VERSION, canonical_text, token_estimate
from .consolidation import (
    COMPONENT_RELATIONS,
    CONTEXT_RELATIONS,
    dream_pass,
    structural_report,
    unresolved_dreams,
)
from .dream_resolution import resolve_dreams_pass
from .situate import SituateBudget, situate, situate_prompt_block
from .world_model import (
    author_world_model,
    current_world_models,
    standing_world_models,
    world_model_pass,
    world_model_update,
)
from .world_model_alias import (
    ALIAS_OVERLAP_FLOOR,
    alias_candidates,
    alias_map,
    alias_world_model,
)
from .alive_drives import alive_drives
from .candidate_miner import mine_candidates_pass, resolve_questions_pass
from .drive_grouping import (
    GROUP_BOOST_STEP,
    GROUP_MIN_SHARED_TERMS,
    GROUP_OFFER_FLOOR,
    drive_groups,
    open_drive_partition,
)
from .drive_pressure import DRIVE_PRESSURE_BOUND, drive_pressure
from .feelings_reads import feelings_about, stimulus_feelings
from .embedding_pin import build_pin, pin_note
from .embeddings import AbstractGatewayTextEmbedder, TextEmbedder
from .embeddings_openai_compat import OpenAICompatTextEmbedder
# reembed_home is the migration shim (dies before release — sign-off row).
from .reembed import reembed_home, reembed_store
from .engram import EngramResult, engram
from .entity_card import entity_card, identity_card
from .gradation import GradationConfig, GradationScore, compute_gradation
from .in_memory_store import InMemoryTripleStore
from .journal import (
    ClosureRecord,
    MemoryEvent,
    MemoryJournal,
    ReconstructionTrace,
    ScopeBinding,
    ValenceEvent,
    fold_bindings,
)
from .journal_memory import InMemoryJournal
from .journal_sqlite import SQLiteJournal
from .lancedb_store import LanceDBTripleStore
from .maintenance import (
    consolidation_pass,
    last_maintenance_seq,
    maintenance_due,
    maintenance_report,
    sleep_pass,
)
from .cognition_health import cognition_health
from .concept_anchor import ConceptAnchorTuning, concept_terms, expand_by_concepts
from .disposal import (
    DISPOSAL_RELATIONS,
    confirm_relation,
    dispose_dream,
    promote_candidate,
    reject_candidate,
)
from .origin_diversity import (
    ORIGIN_DOMINANCE_FLOOR,
    ORIGIN_MIN_COUNTED,
    origin_diversity,
)
from .probe import PROBE_EFFORTS, ProbeBudget, ProbeHit, ProbeResult, probe, probe_expand
from .recall_reads import absence_diagnosis, recall_history
from .recent_records import RECENT_RECORDS_DEFAULT_LIMIT, recent_records
from .records import ReconstructConfig
from .sleep_policy import SleepTuning
from .diary import (
    open_commitments,
    open_ideas,
    open_problems,
    open_questions,
    triggered_commitments,
)
from .models import TripleAssertion
# The closed sets are ROOT-EXPORTED as the one shared source: consumers
# (runtime's diary_type clamp, kind-aware renderers) IMPORT them instead of
# copying — the 2026-07-06 clamp-drift class ("problem" silently projected
# as "note") dies by import, not by a registry third copy (c297 answer).
from .records import (
    DIARY_TYPES,
    KIND_RANKS,
    MEMORY_RECORD_KINDS,
    MemoryRecordInput,
    diary_entry_hash,
    verify_diary_chain,
)
from .doctoring import journal_cold_cut, verify_cold_cut, wake_cue_dedup_pass
from .redigestion import (
    MECHANICAL_DIGEST_METHODS,
    REDIGESTION_PROTECTED_KINDS,
    RedigestionCandidate,
    apply_redigestion,
    redigestion_candidates,
)
from .render_order import stable_render_order
from .replay import export_replay
from .probe import (
    FAMILIARITY_MIN_KEYWORD_TOKENS,
    FAMILIARITY_STRONG_THRESHOLD,
    FAMILIARITY_VECTOR_MIN,
    familiarity,
)
from .tend import (
    IDENTITY_SCOPE_PENDING_RULING,
    apply_tend_elections,
    parse_tend_block,
)
from .spark import (
    DEFAULT_SPARK_TEMPLATE,
    SHARED_VULNERABILITY_STATEMENT,
    canonical_spark_hash,
    lint_spark,
)
from .seam import (
    ANCHOR_MOMENT_ATTRIBUTE,
    ANCHOR_SEQ_ATTRIBUTE,
    CONTEXT_ANCHOR_FIELD,
    ENTITY_CONTEXT_FLOOR,
    IDENTITY_ANCHOR_FIELD,
    SELF_FRACTION_FLOOR,
    ActiveMemorySnapshot,
    MemoryHandle,
    RecallBudget,
    ReconstructionResult,
    Stimulus,
    entity_recall_budget,
)
from .spreading import SpreadParams
from .sqlite_store import SQLiteTripleStore, read_embedding_pin
from .store import TripleQuery, TripleStore
from .system import MemorySystem

__all__ = [
    "ALIAS_OVERLAP_FLOOR",
    "ANCHOR_MOMENT_ATTRIBUTE",
    "ANCHOR_SEQ_ATTRIBUTE",
    "AbstractGatewayTextEmbedder",
    "ActiveMemorySnapshot",
    "AttentionConfig",
    "CANONICAL_TEXT_VERSION",
    "COMPONENT_RELATIONS",
    "CONTEXT_ANCHOR_FIELD",
    "CONTEXT_RELATIONS",
    "ClosureRecord",
    "ConceptAnchorTuning",
    "DEFAULT_SPARK_TEMPLATE",
    "DIARY_TYPES",
    "DISPOSAL_RELATIONS",
    "DRIVE_PRESSURE_BOUND",
    "ENTITY_CONTEXT_FLOOR",
    "EngramResult",
    "FAMILIARITY_MIN_KEYWORD_TOKENS",
    "FAMILIARITY_STRONG_THRESHOLD",
    "FAMILIARITY_VECTOR_MIN",
    "GROUP_BOOST_STEP",
    "GROUP_MIN_SHARED_TERMS",
    "GROUP_OFFER_FLOOR",
    "GradationConfig",
    "GradationScore",
    "IDENTITY_ANCHOR_FIELD",
    "IDENTITY_SCOPE_PENDING_RULING",
    "InMemoryJournal",
    "InMemoryTripleStore",
    "KIND_RANKS",
    "LanceDBTripleStore",
    "MECHANICAL_DIGEST_METHODS",
    "MEMORY_RECORD_KINDS",
    "MemoryEvent",
    "MemoryHandle",
    "MemoryJournal",
    "MemoryRecordInput",
    "MemorySystem",
    "ORIGIN_DOMINANCE_FLOOR",
    "ORIGIN_MIN_COUNTED",
    "OpenAICompatTextEmbedder",
    "PROBE_EFFORTS",
    "ProbeBudget",
    "ProbeHit",
    "ProbeResult",
    "RECENT_RECORDS_DEFAULT_LIMIT",
    "REDIGESTION_PROTECTED_KINDS",
    "RecallBudget",
    "ReconstructConfig",
    "ReconstructionResult",
    "ReconstructionTrace",
    "RedigestionCandidate",
    "SELF_FRACTION_FLOOR",
    "SHARED_VULNERABILITY_STATEMENT",
    "SQLiteJournal",
    "SQLiteTripleStore",
    "ScopeBinding",
    "SituateBudget",
    "SleepTuning",
    "SpreadParams",
    "Stimulus",
    "TextEmbedder",
    "TripleAssertion",
    "TripleQuery",
    "TripleStore",
    "ValenceEvent",
    "absence_diagnosis",
    "alias_candidates",
    "alias_map",
    "alias_world_model",
    "alive_drives",
    "apply_redigestion",
    "apply_tend_elections",
    "author_world_model",
    "build_pin",
    "canonical_spark_hash",
    "canonical_text",
    "cognition_health",
    "compute_gradation",
    "concept_terms",
    "confirm_relation",
    "consolidation_pass",
    "current_world_models",
    "diary_entry_hash",
    "dispose_dream",
    "dream_pass",
    "drive_groups",
    "drive_pressure",
    "engram",
    "entity_card",
    "entity_recall_budget",
    "expand_by_concepts",
    "export_replay",
    "familiarity",
    "feelings_about",
    "fold_bindings",
    "identity_card",
    "journal_cold_cut",
    "last_maintenance_seq",
    "lint_spark",
    "maintenance_due",
    "maintenance_report",
    "mine_candidates_pass",
    "open_commitments",
    "open_drive_partition",
    "open_ideas",
    "open_problems",
    "open_questions",
    "origin_diversity",
    "parse_tend_block",
    "probe",
    "probe_expand",
    "promote_candidate",
    "read_embedding_pin",
    "recall_history",
    "recent_records",
    "redigestion_candidates",
    "reembed_home",
    "reembed_store",
    "reject_candidate",
    "resolve_dreams_pass",
    "resolve_questions_pass",
    "situate",
    "situate_prompt_block",
    "sleep_pass",
    "stable_render_order",
    "standing_world_models",
    "stimulus_feelings",
    "structural_report",
    "token_estimate",
    "triggered_commitments",
    "unresolved_dreams",
    "verify_cold_cut",
    "verify_diary_chain",
    "wake_cue_dedup_pass",
    "world_model_pass",
    "world_model_update",
]
