"""abstractmemory.graph: the one write path of a mind (ADR 0003).

Typed ledger provenance (`SourceRef`, `Provenance`), the revision as the unit of change (`Revision`, `RevisionOp`),
and `MemoryGraph`: atomic, idempotent revision apply with mandatory grounded provenance, plus the reads `history`,
`sources_of`, `derived_from_source`, the lossless change feed `revisions(after=)` and `replay_into`.
"""

from .backend import GraphBackend, GraphTx, backend_for, register_backend, registered_backends
from .graph import (
    ADOPTING_CAUSES,
    DEFAULT_READ_LIMIT,
    DEFAULT_REVISION_PAGE,
    DIGEST_PREDICATE,
    MAX_LINEAGE_VISITS,
    MAX_READ_LIMIT,
    MemoryGraph,
)
from .provenance import (
    LEGACY_KEYS,
    PROVENANCE_KEYS,
    SOURCE_KINDS,
    SYNTHETIC_RUN_ID_PREFIXES,
    InvalidSourceRef,
    Provenance,
    ProvenanceRequired,
    SourceRef,
    is_synthetic_run_id,
)
from .revisions import CLOSE_KINDS, REVISION_CAUSES, REVISION_OPS, Revision, RevisionOp, RevisionResult

__all__ = [
    "GraphBackend",
    "GraphTx",
    "backend_for",
    "register_backend",
    "registered_backends",
    "ADOPTING_CAUSES",
    "CLOSE_KINDS",
    "DEFAULT_READ_LIMIT",
    "DEFAULT_REVISION_PAGE",
    "DIGEST_PREDICATE",
    "LEGACY_KEYS",
    "MAX_LINEAGE_VISITS",
    "MAX_READ_LIMIT",
    "PROVENANCE_KEYS",
    "REVISION_CAUSES",
    "REVISION_OPS",
    "SOURCE_KINDS",
    "SYNTHETIC_RUN_ID_PREFIXES",
    "InvalidSourceRef",
    "MemoryGraph",
    "Provenance",
    "ProvenanceRequired",
    "Revision",
    "RevisionOp",
    "RevisionResult",
    "SourceRef",
    "is_synthetic_run_id",
]
