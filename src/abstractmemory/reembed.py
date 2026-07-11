"""The reembed repair pass (plan item 3 / M1b): deliberate embedding-space
migration over a CLOSED home.

VECTORS ARE DERIVED DATA. Digests, verbatim artifacts, and the append-only
journal are the truth and are never touched — this pass re-derives the
vector index from the stored canonical texts and swaps it atomically.
Activation, usage counts, and valence are embedding-independent and
untouched (guard-tested).

Contract (the plan's wording, mechanically honored):
- OPERATOR-GATED, over a closed home: the caller (gateway maintenance verb)
  holds the per-home lease — maintenance is a writer like any other. The
  engine cannot see the lease (GW-A's lock file is door machinery), so it
  enforces the OBSERVABLE half: the atomic swap verifies the store did not
  change between scan and swap and refuses with nothing written if it did.
- ALL-OR-NOTHING WITH INDEX SWAP: every record text is re-embedded first
  (any embedder failure aborts with zero writes); ONE store transaction
  rewrites all vectors and updates the pin LAST. A dimension change
  (1024 -> 2560) cannot be patched in place — it isn't: readers serve the
  OLD space consistently until the commit; after it, only the new. Never a
  mixed space (a strictly stronger guarantee than the plan's
  labeled-vectorless minimum, noted as such).
- THE ACT IS JOURNALED: a bookkeeping record (kind="claim", the engram-
  marker precedent) forms via remember_many with old -> new model ids and
  dimensions, so the life stream shows exactly WHEN retrieval geometry
  changed. The gateway's host marker is the door's half of the visibility.
- NOT ADVISED for the right reason: same memories, different neighbors — a
  substrate effect, reported, never silent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .canonical_text import canonical_text, is_record_edge
from .embedding_pin import build_pin, embedder_model_id
from .journal import utc_now_iso
from .records import MemoryRecordInput
from .store import TripleQuery

__all__ = ["reembed_home", "reembed_store"]

_EMBED_BATCH = 64  # default texts per embed_texts call (server request hygiene)


def reembed_store(
    system: Any, *,
    embedder: Any,
    owner_id: str,
    model_id: Optional[str] = None,
    marker_scope: str = "life",
    reason: str = "operator reembed",
    batch_size: int = _EMBED_BATCH,
) -> Dict[str, Any]:
    """Re-derive the whole store's vector index with `embedder` and swap
    atomically. `model_id` names the new space when the embedder cannot
    (embedder_model_id is preferred when exposed). The journal marker lands
    in (marker_scope, owner_id) — the scope whose life stream should show
    the act (default "life": the conventional first ladder scope).
    `batch_size` is an operator knob: embedding servers differ in what one
    request should carry. Returns {rows, vectored, skipped_edges, old_pin,
    new_pin, marker_record_id}.

    Named per-STORE (renaming sign-off, laurent c398): one store = one
    embedding space by its own contract; "home" is the reference
    deployment's noun for the containing directory.
    """
    step = int(batch_size)
    if step < 1:
        raise ValueError(f"batch_size must be >= 1 (got {batch_size!r})")
    if embedder is None:
        raise ValueError("reembed_store requires the NEW embedder (the space to migrate into)")
    store = system.store  # public substrate handle (composition surface)
    old_pin = store.embedding_pin() if hasattr(store, "embedding_pin") else None
    if not hasattr(store, "replace_vectors"):
        raise ValueError(
            f"this store ({type(store).__name__}) has no atomic vector-swap surface; "
            "reembed supports the SQLite and InMemory stores"
        )

    # SCAN: every row, one pass (reembed is per-STORE: one store = one
    # space; scopes do not partition an embedding space).
    rows = store.query(TripleQuery(limit=0))
    expected = len(rows)
    embeddable: List[Any] = [a for a in rows if not is_record_edge(a) and a.assertion_id]
    skipped_edges = expected - len(embeddable)

    # RE-EMBED before any write (all-or-nothing: an embedder failure here
    # aborts with the store untouched). Batched for server hygiene.
    vectors: Dict[str, List[float]] = {}
    dimension: Optional[int] = None
    for start in range(0, len(embeddable), step):
        batch = embeddable[start:start + step]
        embedded = embedder.embed_texts([canonical_text(a) for a in batch])
        if len(embedded) != len(batch):
            raise RuntimeError(
                f"embedder returned {len(embedded)} vectors for {len(batch)} texts — "
                "cannot align; reembed aborted with nothing written"
            )
        for a, vector in zip(batch, embedded):
            clean = [float(x) for x in vector]
            if dimension is None:
                dimension = len(clean)
            elif len(clean) != dimension:
                raise RuntimeError(
                    f"embedder produced mixed dimensions ({dimension} and {len(clean)}) — "
                    "reembed aborted with nothing written"
                )
            vectors[a.assertion_id] = clean

    new_model = (str(model_id).strip() if isinstance(model_id, str) and model_id.strip()
                 else embedder_model_id(embedder))
    new_pin = build_pin(new_model, dimension, source="reembed") if (new_model or dimension) else None
    if new_pin is None:
        raise ValueError(
            "reembed produced no vectors and no model identity — an empty store "
            "with an anonymous embedder has nothing to migrate; pass model_id"
        )

    # SWAP: one atomic transaction (count guard inside = the lease-violation
    # backstop), pin written LAST inside it, live embedder switched with it.
    vectored = store.replace_vectors(
        vectors, new_pin, expected_row_count=expected, embedder=embedder)

    # JOURNAL THE ACT: bookkeeping claim (engram-marker precedent) — off
    # working-set shelves, fully queryable, visible in the replay stream as
    # its formation binding. Each invocation is a distinct deliberate act.
    old_model = (old_pin or {}).get("model_id")
    old_dim = (old_pin or {}).get("dimension")
    stamp = utc_now_iso()
    marker = MemoryRecordInput(
        kind="claim",
        title="reembed: embedding space migrated",
        digest=(
            f"The vector index was re-derived by an operator reembed at {stamp}: "
            f"{old_model or 'unpinned'}"
            f"{f' ({old_dim}d)' if old_dim else ''} -> {new_model or 'unknown model'}"
            f" ({dimension}d), {vectored} of {expected} rows vectored. Memories and "
            "their history are untouched; retrieval neighbors may shift — a "
            "substrate effect, on the record."
        ),
        attributes={
            "bookkeeping": True, "maintenance": "reembed", "reason": str(reason or ""),
            "old_model_id": old_model, "old_dimension": old_dim,
            "new_model_id": new_model, "new_dimension": dimension,
            "rows_vectored": vectored,
        },
    )
    [marker_id] = system.remember_many(
        [marker], scope=marker_scope, owner_id=owner_id,
        idempotency_key=f"reembed|{owner_id}|{stamp}")
    return {
        "rows": expected, "vectored": vectored, "skipped_edges": skipped_edges,
        "old_pin": old_pin, "new_pin": new_pin, "marker_record_id": marker_id,
    }


# MIGRATION SHIM (dies before release — the lease pattern, sign-off row):
# the one gateway call site and observer's demo exporter move same-day per
# their turn-2 commitments; this alias exists only so the window has no
# broken imports.
reembed_home = reembed_store
