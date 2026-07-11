"""Embedding-space pin helpers (plan item 3 / M1; backlog 0014's manifest).

One store = one embedding space. The pin `{model_id, dimension, source,
pinned_at}` is the store's declared space identity:

- CREATION pin (M1): the door writes it when the home is born — embedder
  identity is an explicit, customizable BIRTH choice, never discovered.
- FIRST-WRITE pin (labeled fallback): pre-M1 homes (Castor's) get pinned at
  their next embedded write, with a #FALLBACK warning naming the path.
- REEMBED pin (M1b): the ONLY replacement path — the repair pass re-derives
  every vector and updates the pin LAST (reembed.py).

Enforcement invariant (the plan's wording): NO SILENT MIXING OF EMBEDDING
SPACES. A door with a different model refuses loudly at WRITE (a wrong-space
vector would corrupt the index) and degrades loudly at READ (the vector
channel converts the store's refusal into its labeled-vectorless #FALLBACK —
recall keeps working on exact/keyword). Both paths loud, by construction.

These helpers are shared by the SQLite and InMemory stores so the two
backends cannot drift (the canonical_text / vector_scoring lesson). The pin
STORAGE is each backend's (meta table / in-object); the RULES live here.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

__all__ = [
    "annotate_embed_failure",
    "build_pin",
    "check_add_dimension",
    "check_model_compat",
    "check_query_dimension",
    "embedder_model_id",
    "pin_note",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def embedder_model_id(embedder: Any) -> Optional[str]:
    """Best-known model identity of an embedder: a `model` or `model_id`
    attribute when the implementation exposes one (OpenAICompatTextEmbedder
    does; the gateway HTTP embedder cannot — the model is server-side).
    None = unknown; enforcement then rests on DIMENSION, which is always
    measurable from the vectors themselves."""
    for attr in ("model", "model_id"):
        value = getattr(embedder, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def build_pin(
    model_id: Optional[str], dimension: Optional[int], *, source: str,
    claimed_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalized pin payload. model_id may be None (unknown-identity
    embedders); dimension may be None at creation (filled and locked by the
    first embedded write). At least one must be present — an empty pin
    would enforce nothing and lie about it.

    `claimed_by` marks the PROVENANCE of the model_id label when it was not
    an operator assertion (2026-07-11 incident: a first-write pin recorded
    an embedder attribute's label that the serving endpoint never
    recognized — the engine cannot verify a label against server truth, so
    the honest move is to say WHO claimed it). "embedder-attribute" =
    read off the bound embedder object, unverified. Absent = the caller
    (creation choice / explicit reembed model_id) vouches for the label."""
    mid = str(model_id).strip() if isinstance(model_id, str) and model_id.strip() else None
    dim = int(dimension) if dimension is not None else None
    if dim is not None and dim < 1:
        raise ValueError(f"embedding pin dimension must be >= 1, got {dimension!r}")
    if mid is None and dim is None:
        raise ValueError(
            "an embedding pin needs a model_id and/or a dimension — "
            "pinning nothing would enforce nothing"
        )
    pin: Dict[str, Any] = {"model_id": mid, "dimension": dim,
                           "source": str(source or "creation"), "pinned_at": _utc_now_iso()}
    if claimed_by and mid is not None:  # a claim marker without a label marks nothing
        pin["claimed_by"] = str(claimed_by)
    return pin


def pin_note(pin: Optional[Dict[str, Any]]) -> str:
    """One-line human rendering of a pin for error/warning text:
    'model@dim (source, claimed by X)'. Used where an embedding FAILURE
    should immediately show the operator claimed-vs-served identity
    (2026-07-11 incident: a server 400 naming the requested model was only
    diagnosable next to the store's pinned label)."""
    if not pin:
        return "unpinned"
    model = pin.get("model_id") or "unknown-model"
    dim = pin.get("dimension")
    note = f"{model}@{dim if dim is not None else '?'}d"
    source = pin.get("source")
    claimed = pin.get("claimed_by")
    inside = ", ".join(
        s for s in (str(source) if source else "", f"claimed by {claimed}" if claimed else "") if s)
    return f"{note} ({inside})" if inside else note


def annotate_embed_failure(exc: Exception, pin: Optional[Dict[str, Any]]) -> Optional[Exception]:
    """Rebuild an embed-time failure with the store's pin appended, so a
    server-side refusal (HTTP 400 naming the REQUESTED model) and the
    store's CLAIMED identity land in one line — the 2026-07-11 incident was
    diagnosable only by joining those two facts by hand. Returns the
    annotated exception, or None when `exc` is a subclass whose constructor
    we cannot safely call (caller re-raises the original bare)."""
    if type(exc) in (ValueError, RuntimeError):
        return type(exc)(f"{exc} [store pin: {pin_note(pin)}]")
    return None


def check_model_compat(pin: Optional[Dict[str, Any]], embedder: Any) -> None:
    """Refuse a KNOWN embedder identity that contradicts the pin. Unknown
    identities pass (dimension still guards); pinless stores pass (legacy —
    first-write pinning labels them at the write site)."""
    if not pin or embedder is None:
        return
    known = embedder_model_id(embedder)
    pinned = pin.get("model_id")
    if known and isinstance(pinned, str) and pinned and known != pinned:
        raise ValueError(
            f"embedding-space mismatch: this store is pinned to embedding model "
            f"{pinned!r} but the configured embedder is {known!r} — no silent mixing "
            "of embedding spaces (open the home with the pinned model, open it "
            "without an embedder for labeled vectorless reads, or run the "
            "operator-gated reembed repair)"
        )


def check_add_dimension(
    pin: Optional[Dict[str, Any]], vectors: Iterable[Any],
) -> Optional[int]:
    """Validate a batch of freshly produced vectors against the pin.

    Returns the batch dimension (for first-write pinning / dimension fill),
    or None when the batch is empty. Refuses internally inconsistent batches
    and any batch whose dimension contradicts a pinned dimension — the write
    aborts BEFORE the transaction, zero rows land."""
    dims = {len(v) for v in vectors if v is not None}
    if not dims:
        return None
    if len(dims) > 1:
        raise ValueError(
            f"embedder returned inconsistent vector dimensions in one batch "
            f"({sorted(dims)}) — refusing to write a mixed embedding space"
        )
    dim = dims.pop()
    pinned = pin.get("dimension") if pin else None
    if pinned is not None and int(pinned) != dim:
        model = (pin or {}).get("model_id")
        raise ValueError(
            f"embedding-space mismatch: store is pinned to dimension {int(pinned)}"
            f"{f' (model {model!r})' if model else ''} but the configured embedder "
            f"produced dimension {dim} — no silent mixing of embedding spaces "
            "(the reembed maintenance verb is the sanctioned migration)"
        )
    return dim


def check_query_dimension(
    pin: Optional[Dict[str, Any]], query_vector: Optional[Iterable[float]],
) -> None:
    """Refuse a query vector whose dimension contradicts the pin — the
    truncating-cosine behavior on mismatched dimensions is exactly the
    silent-garbage failure 0014 documented (cosine([1,0,0,0],[1,0])==1.0).
    The vector CHANNEL converts this refusal into its labeled #FALLBACK, so
    reads degrade loudly to keyword/exact instead of serving wrong-space
    similarity."""
    if not pin or query_vector is None:
        return
    pinned = pin.get("dimension")
    if pinned is None:
        return
    length = sum(1 for _ in query_vector)
    if length != int(pinned):
        model = pin.get("model_id")
        raise ValueError(
            f"embedding-space mismatch: query vector has dimension {length} but "
            f"this store is pinned to {int(pinned)}"
            f"{f' (model {model!r})' if model else ''} — no silent mixing of "
            "embedding spaces (query with the pinned model or read vectorless)"
        )


def warn_first_write_pin(pin: Dict[str, Any]) -> None:
    """The labeled fallback for pre-M1 homes: pinning at first write is
    allowed but LOUD — creation-time pinning is the contract going forward."""
    warnings.warn(
        "#FALLBACK: embedding pin created at FIRST WRITE "
        f"(model={pin.get('model_id')!r}, dimension={pin.get('dimension')!r}) — "
        "this home predates creation-time pinning (M1); new homes must pin the "
        "embedder at creation",
        RuntimeWarning,
        stacklevel=3,
    )
