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
from .embeddings import AbstractGatewayTextEmbedder, TextEmbedder
from .embeddings_openai_compat import OpenAICompatTextEmbedder
from .engram import EngramResult, engram
from .entity_card import entity_card
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
from .diary import open_ideas, open_problems, open_questions
from .models import TripleAssertion
from .records import MemoryRecordInput, diary_entry_hash, verify_diary_chain
from .replay import export_replay
from .spark import (
    DEFAULT_SPARK_TEMPLATE,
    SHARED_VULNERABILITY_STATEMENT,
    canonical_spark_hash,
    lint_spark,
)
from .seam import (
    ENTITY_CONTEXT_FLOOR,
    SELF_FRACTION_FLOOR,
    ActiveMemorySnapshot,
    MemoryHandle,
    RecallBudget,
    ReconstructionResult,
    Stimulus,
    entity_recall_budget,
)
from .spreading import SpreadParams
from .sqlite_store import SQLiteTripleStore
from .store import TripleQuery, TripleStore
from .system import MemorySystem

__all__ = [
    "AbstractGatewayTextEmbedder",
    "ActiveMemorySnapshot",
    "AttentionConfig",
    "CANONICAL_TEXT_VERSION",
    "COMPONENT_RELATIONS",
    "CONTEXT_RELATIONS",
    "ClosureRecord",
    "DEFAULT_SPARK_TEMPLATE",
    "ENTITY_CONTEXT_FLOOR",
    "EngramResult",
    "GradationConfig",
    "GradationScore",
    "InMemoryJournal",
    "InMemoryTripleStore",
    "LanceDBTripleStore",
    "MemoryEvent",
    "MemoryHandle",
    "MemoryJournal",
    "MemoryRecordInput",
    "MemorySystem",
    "OpenAICompatTextEmbedder",
    "RecallBudget",
    "ReconstructionResult",
    "ReconstructionTrace",
    "SELF_FRACTION_FLOOR",
    "SHARED_VULNERABILITY_STATEMENT",
    "SQLiteJournal",
    "SQLiteTripleStore",
    "ScopeBinding",
    "SpreadParams",
    "Stimulus",
    "TextEmbedder",
    "TripleAssertion",
    "TripleQuery",
    "TripleStore",
    "ValenceEvent",
    "canonical_spark_hash",
    "canonical_text",
    "compute_gradation",
    "consolidation_pass",
    "diary_entry_hash",
    "dream_pass",
    "engram",
    "entity_card",
    "entity_recall_budget",
    "export_replay",
    "fold_bindings",
    "last_maintenance_seq",
    "lint_spark",
    "maintenance_due",
    "maintenance_report",
    "open_ideas",
    "open_problems",
    "open_questions",
    "sleep_pass",
    "structural_report",
    "token_estimate",
    "unresolved_dreams",
    "verify_diary_chain",
]
