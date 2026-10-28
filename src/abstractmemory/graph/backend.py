"""The connector contract of a mind (ADR 0003 decision 3): `MemoryGraph` is the ONLY manipulation surface of a mind;
every store is a CONNECTOR behind it that implements the operations below and keeps their invariants. Changing the
database of a mind means writing a connector, never touching `MemoryGraph` or its callers.

A connector is a `GraphBackend` (what the graph reads and how it opens a transaction) whose `transaction()` yields a
`GraphTx` (what one revision reads and writes while it applies). `MemoryGraph(store, journal)` picks the connector
registered for the store's class (`register_backend`). The conformance suite every connector must pass is
`tests/test_graph_conformance.py`; a connector that cannot keep an invariant marks that case `xfail(strict=True)`
there with the reason, and the ADR lists it.

INVARIANTS a connector keeps:
- ATOMICITY: the writes of one `transaction()` become visible together or not at all; an exception inside the
  `with` block leaves nothing behind (no triple, window change, history, provenance, derivation or revision row).
- ORDER: `insert_revision` allocates `seq` = the previous head + 1 inside the transaction, and transactions of one
  mind are serialized, so commit order is seq order (the change feed is lossless).
- IDENTITY: an assertion id is written once (`insert_assertions` skips ids already stored); a (memory, ref key)
  provenance row and a (memory, parent) derivation row are written once, the first one winning.
- READS ARE BOUNDED: every read that returns rows takes a `limit` (or is bounded by one revision's ops).
- OPENING IS A READ: constructing a connector over an up-to-date mind writes nothing.
"""

from __future__ import annotations

from typing import (TYPE_CHECKING, Any, Callable, ContextManager, Dict, Iterable, List, Optional, Protocol,
                    Sequence, Tuple, Type, runtime_checkable)

if TYPE_CHECKING:  # pragma: no cover
    from ..journal import ClosureRecord
    from ..models import TripleAssertion
    from .provenance import SourceRef
    from .revisions import Revision

Window = Tuple[Optional[str], Optional[str]]  # (valid_from, valid_until)


@runtime_checkable
class GraphTx(Protocol):
    """One revision's reads and writes, inside one atomic transaction of the connector."""

    # -- reads (they see this transaction's own earlier writes) --
    def revision_seq(self, rid: str) -> Optional[int]: ...
    def memory_known(self, mid: str) -> bool: ...  # asserted through the graph (a history 'asserted' event)
    def closing_revision(self, mid: str) -> Optional[str]: ...
    def open_same_claim(self, a: "TripleAssertion") -> Optional[str]: ...  # a held OPEN memory with a's identity
    def digest_assertion_for(self, graph_id: str) -> Optional[str]: ...
    def existing_ids(self, ids: Sequence[str]) -> set: ...
    def stored(self, aid: str) -> "TripleAssertion": ...
    def window(self, aid: str) -> Optional[Window]: ...

    # -- writes --
    def write_pin(self, pin: Optional[Dict[str, Any]]) -> None: ...
    def insert_assertions(self, rows: List[Any]) -> None: ...  # rows from GraphBackend.prepare_rows
    def set_provenance(self, aid: str, provenance: Dict[str, Any]) -> None: ...
    def end_row(self, aid: str, until: str) -> bool: ...
    def narrow_row(self, aid: str, until: str) -> bool: ...  # narrow_assertion semantics (ValueError on open)
    def write_closure(self, closure: "ClosureRecord") -> bool: ...  # True when it rides this transaction
    def add_history(self, mid: str, event: str, at: str, rid: str, detail: Dict[str, Any]) -> None: ...
    def add_source(self, mid: str, ref: "SourceRef", rid: str, owner: Optional[str], via: str = ...) -> None: ...
    def add_derivation(self, mid: str, from_id: str, rid: str) -> None: ...
    def insert_revision(self, rev: "Revision", journal_applied: bool) -> int: ...


@runtime_checkable
class GraphBackend(Protocol):
    """A mind's connector: transactions plus the bounded reads `MemoryGraph` serves."""

    def prepare_rows(self, assertions: List["TripleAssertion"]) -> Tuple[List[Any], Optional[Dict[str, Any]], bool]:
        """Embed and shape rows BEFORE the transaction: (rows, embedding pin to write in it or None, first-write)."""
        ...

    def transaction(self) -> ContextManager[GraphTx]: ...

    # -- reads --
    def applied_seq(self, rid: str) -> Optional[int]: ...
    def resolve(self, mid: str) -> Optional[str]: ...
    def history(self, mid: str, limit: int) -> List[Dict[str, Any]]: ...
    def sources(self, mid: str, limit: int) -> List[Tuple["SourceRef", str, str]]: ...  # (ref, via, revision id)
    def parents(self, mid: str, limit: int) -> List[str]: ...
    def children(self, fid: str, limit: int) -> List[str]: ...
    def with_ref(self, ref: "SourceRef", limit: int) -> List[str]: ...
    def names_ref(self, ref: "SourceRef", owners: List[str]) -> bool: ...
    def revisions_page(self, after: int, limit: int) -> List[Tuple[int, "Revision"]]: ...
    def log_head(self) -> int: ...
    def logged_outcome(self, rid: str) -> Tuple[Optional[str], List[Tuple[str, str]]]: ...

    # -- off-transaction journal and crash repair --
    def pending_journal(self, limit: int) -> List["Revision"]: ...
    def closed_payload(self, aid: str, rid: str) -> Optional[Dict[str, Any]]: ...
    def mark_journal_applied(self, rid: str) -> None: ...
    def repair_projections(self) -> int:
        """Finish revisions a crash left half-projected (a connector without cross-table transactions writes its
        log first); 0 for a connector whose transactions are atomic."""
        ...


BackendFactory = Callable[[Any, Any], GraphBackend]
_REGISTRY: List[Tuple[Type[Any], BackendFactory]] = []


def register_backend(store_class: Type[Any], factory: BackendFactory) -> None:
    """Make `MemoryGraph(store, journal)` use `factory(store, journal)` for stores of `store_class` (the most
    recently registered matching class wins)."""
    _REGISTRY.insert(0, (store_class, factory))


def backend_for(store: Any, journal: Any) -> GraphBackend:
    for store_class, factory in _REGISTRY:
        if isinstance(store, store_class):
            return factory(store, journal)
    raise NotImplementedError(
        f"MemoryGraph: no connector is registered for {type(store).__name__} "
        f"(registered: {[c.__name__ for c, _ in _REGISTRY]}); see abstractmemory.graph.backend"
    )


def registered_backends() -> List[Type[Any]]:
    return [c for c, _ in _REGISTRY]
