"""Binary vectors and the in-process vector matrix of the SQLite store
(backlog 0058; ADR 0003 decision 3).

Encoding: a stored vector is a float32 little-endian BLOB (4 bytes per
dimension; the JSON text it replaces cost ~20 bytes per dimension and a
`json.loads` per row per query). `decode_vector` reads both encodings, so a
home part-way through its in-place upgrade, or written to by an older
process, keeps serving every row.

Scoring: `VectorMatrix` holds one store's vectored rows as a float32 matrix
in memory, keyed by assertion id, with the (scope, owner_id) of each row so
the vector channel's partition filter is a mask instead of a query. It is
built once from a scan, then APPENDED from the rows above its rowid
high-water (the store's own adds and any other writer's), and dropped when
the vectors are rewritten (`replace_vectors`, detected across processes by
the `vector_generation` meta key and the embedding pin). Ranking is exact:
a float32 pass selects the candidates (with a margin wide enough for float32
error), and those are re-scored in float64 with the reference formula of
`vector_scoring.cosine`; ties order by rowid, as the reference scan does.

numpy is OPTIONAL (`pip install "abstractmemory[fast]"`). Without it, or when
a store holds vectors the matrix cannot represent exactly (mixed dimensions,
non-finite values, legacy JSON that is not a list of numbers), the store uses
the reference Python scan (`vector_scoring.rank_by_cosine`) and says so once
with a `#FALLBACK` warning; results are the same, only slower.
"""

from __future__ import annotations

import json
import sys
from array import array
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:  # optional accelerator; the Python scan is the labelled fallback
    import numpy as _np
except Exception:  # pragma: no cover - exercised by monkeypatching _np
    _np = None

__all__ = [
    "VECTOR_ENGINE_NUMPY",
    "VECTOR_ENGINE_PYTHON",
    "VectorMatrix",
    "decode_vector",
    "encode_vector",
    "numpy_module",
]

VECTOR_ENGINE_NUMPY = "numpy-matrix-cache"
VECTOR_ENGINE_PYTHON = "python-linear-scan"

# Candidate margin of the float32 pass, in cosine units. float32 dot products
# of unit-scaled vectors err by well under 1e-4 even at 4096 dimensions; the
# margin only widens the float64 re-scoring set, it never decides a result.
_COARSE_MARGIN = 1e-3
# Below this share of the matrix, score the candidate rows directly instead
# of the whole matrix.
_SUBSET_SHARE = 0.25


def numpy_module() -> Any:
    """The numpy module, or None when it is not importable."""
    return _np


def encode_vector(vector: Sequence[float]) -> bytes:
    """float32 little-endian bytes of a vector."""
    packed = array("f", [float(x) for x in vector])
    if sys.byteorder != "little":  # pragma: no cover - big-endian hosts
        packed.byteswap()
    return packed.tobytes()


def decode_vector(raw: Any) -> Optional[List[float]]:
    """A stored vector as a list of floats, or None (vectorless/unreadable).
    Reads the float32 BLOB and the legacy JSON text alike."""
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray, memoryview)):
        data = bytes(raw)
        if len(data) % 4:
            return None
        values = array("f")
        values.frombytes(data)
        if sys.byteorder != "little":  # pragma: no cover - big-endian hosts
            values.byteswap()
        return values.tolist()
    if not raw:
        return None
    try:
        vector = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return vector if isinstance(vector, list) else None


class _Unrepresentable(Exception):
    """The matrix cannot serve this query exactly; use the Python scan."""


class VectorMatrix:
    """One store's vectored rows as an in-memory float32 matrix.

    Not thread-safe by itself: the store calls it under its own lock.
    `token` identifies the vector space it was built from; `high_water` is
    the highest rowid it has seen (vectored or not)."""

    def __init__(self, token: Tuple[Any, ...]) -> None:
        np = _np
        if np is None:
            raise RuntimeError("VectorMatrix requires numpy")
        self.token = token
        self.high_water = 0
        self.size = 0
        self.dim: Optional[int] = None
        # False once a vector the matrix cannot represent exactly was seen:
        # the store then serves the Python scan until the cache is rebuilt.
        self.exact = True
        self._capacity = 0
        self._matrix = np.zeros((0, 0), dtype=np.float32)
        self._inv_norm = np.zeros(0, dtype=np.float64)
        self._rowid = np.zeros(0, dtype=np.int64)
        self._scope = np.zeros(0, dtype=np.int32)
        self._owner = np.zeros(0, dtype=np.int32)
        self._ids: List[str] = []
        self._position: Dict[str, int] = {}
        self._scope_codes: Dict[Any, int] = {}
        self._owner_codes: Dict[Any, int] = {}

    # -- building ---------------------------------------------------------

    def append(self, rows: Iterable[Tuple[int, str, str, Optional[str], Any]]) -> int:
        """Add rows `(rowid, assertion_id, scope, owner_id, raw_embedding)`
        in rowid order. Rows without a vector only advance the high-water;
        an id already present is skipped. Returns the number of vectors
        added."""
        np = _np
        fresh: List[Tuple[int, str, str, Optional[str], Any]] = []
        for rowid, assertion_id, scope, owner, vector in self._decoded(rows):
            if vector is None or assertion_id in self._position:
                continue
            fresh.append((rowid, assertion_id, scope, owner, vector))
        if not fresh or not self.exact:
            return 0
        block = np.vstack([v for *_, v in fresh])
        start = self.size
        self._reserve(start + len(fresh))
        end = start + len(fresh)
        self._matrix[start:end] = block
        wide = block.astype(np.float64)
        norms = np.sqrt(np.einsum("ij,ij->i", wide, wide))
        with np.errstate(divide="ignore"):
            self._inv_norm[start:end] = np.where(norms > 0.0, 1.0 / norms, 0.0)
        for offset, (rowid, assertion_id, scope, owner, _) in enumerate(fresh):
            pos = start + offset
            self._rowid[pos] = rowid
            self._scope[pos] = self._scope_codes.setdefault(scope, len(self._scope_codes))
            self._owner[pos] = self._owner_codes.setdefault(owner, len(self._owner_codes))
            self._ids.append(assertion_id)
            self._position[assertion_id] = pos
        self.size = end
        return len(fresh)

    def _decoded(self, rows):
        np = _np
        for rowid, assertion_id, scope, owner, raw in rows:
            rowid = int(rowid)
            if rowid > self.high_water:
                self.high_water = rowid
            if raw is None or not self.exact:
                yield rowid, assertion_id, scope, owner, None
                continue
            vector = None
            if isinstance(raw, (bytes, bytearray, memoryview)):
                data = bytes(raw)
                if len(data) % 4 == 0:
                    vector = np.frombuffer(data, dtype="<f4")
            else:
                listed = decode_vector(raw)
                if listed is None:
                    yield rowid, assertion_id, scope, owner, None  # reference skips it too
                    continue
                try:
                    vector = np.asarray([float(x) for x in listed], dtype=np.float64)
                except (TypeError, ValueError):
                    vector = None
                else:
                    # Legacy JSON holds float64: the matrix is float32, so
                    # only values float32 represents exactly stay exact.
                    narrowed = vector.astype(np.float32)
                    vector = narrowed if np.array_equal(narrowed, vector) else None
            if (vector is None or vector.ndim != 1 or vector.shape[0] == 0
                    or (self.dim is not None and vector.shape[0] != self.dim)
                    or not np.isfinite(vector).all()):
                self.exact = False
                yield rowid, assertion_id, scope, owner, None
                continue
            if self.dim is None:
                self.dim = int(vector.shape[0])
            yield rowid, assertion_id, scope, owner, vector

    def _reserve(self, needed: int) -> None:
        if needed <= self._capacity:
            return
        np = _np
        capacity = max(needed, self._capacity * 2, 1024)
        matrix = np.zeros((capacity, int(self.dim or 0)), dtype=np.float32)
        if self.size:
            matrix[: self.size] = self._matrix[: self.size]
        self._matrix = matrix

        def grown(old, dtype):
            new = np.zeros(capacity, dtype=dtype)
            new[: self.size] = old[: self.size]
            return new

        self._inv_norm = grown(self._inv_norm, np.float64)
        self._rowid = grown(self._rowid, np.int64)
        self._scope = grown(self._scope, np.int32)
        self._owner = grown(self._owner, np.int32)
        self._capacity = capacity

    # -- reading ----------------------------------------------------------

    def partition(self, scope: Optional[str], owner_id: Optional[str]) -> Any:
        """Positions of the rows in (scope, owner) — None means no filter on
        that column; an unknown value selects nothing."""
        np = _np
        mask = np.ones(self.size, dtype=bool)
        if scope is not None:
            code = self._scope_codes.get(scope)
            if code is None:
                return np.zeros(0, dtype=np.int64)
            mask &= self._scope[: self.size] == code
        if owner_id is not None:
            code = self._owner_codes.get(owner_id)
            if code is None:
                return np.zeros(0, dtype=np.int64)
            mask &= self._owner[: self.size] == code
        return np.flatnonzero(mask)

    def positions_of(self, assertion_ids: Iterable[str]) -> Any:
        """Positions of the given ids that hold a vector, in rowid order."""
        np = _np
        found = sorted(p for p in (self._position.get(a) for a in assertion_ids) if p is not None)
        return np.asarray(found, dtype=np.int64)

    def rank(
        self, query_vector: Sequence[float], positions: Any, *,
        min_score: Optional[float], limit: Optional[int],
    ) -> List[Tuple[float, str]]:
        """`(score, assertion_id)` best first — the reference semantics of
        `rank_by_cosine` (min_score before ranking, score desc, ties in rowid
        order, optional truncation). Raises `_Unrepresentable` when only the
        Python scan can answer exactly."""
        np = _np
        if not self.exact:
            raise _Unrepresentable("matrix holds vectors it cannot represent exactly")
        if len(positions) == 0:
            return []
        q64 = np.asarray([float(x) for x in query_vector], dtype=np.float64)
        if self.dim is None or q64.shape[0] != self.dim or not np.isfinite(q64).all():
            raise _Unrepresentable("query vector does not match the matrix dimension")
        q_norm = float(np.sqrt(q64 @ q64))
        matrix = self._matrix[: self.size]
        if q_norm <= 0.0:
            coarse = np.zeros(len(positions), dtype=np.float64)
        else:
            q32 = q64.astype(np.float32)
            if len(positions) < _SUBSET_SHARE * self.size:
                dots = matrix[positions] @ q32
            else:
                dots = (matrix @ q32)[positions]
            coarse = dots.astype(np.float64) * self._inv_norm[positions] / q_norm
            if not np.isfinite(coarse).all():
                raise _Unrepresentable("float32 pass overflowed")
        candidates = positions
        if min_score is not None:
            keep = coarse >= float(min_score) - _COARSE_MARGIN
            candidates, coarse = candidates[keep], coarse[keep]
        if limit is not None and len(candidates) > limit:
            kth = np.partition(coarse, len(coarse) - limit)[len(coarse) - limit]
            keep = coarse >= kth - _COARSE_MARGIN
            candidates = candidates[keep]
        if len(candidates) == 0:
            return []
        # Exact pass: float64, the formula of vector_scoring.cosine.
        wide = matrix[candidates].astype(np.float64)
        dots = wide @ q64
        norms = np.sqrt(np.einsum("ij,ij->i", wide, wide))
        denom = norms * q_norm
        with np.errstate(divide="ignore", invalid="ignore"):
            exact = np.where(denom > 0.0, dots / np.where(denom > 0.0, denom, 1.0), 0.0)
        if min_score is not None:
            keep = ~(exact < float(min_score))
            candidates, exact = candidates[keep], exact[keep]
        order = np.argsort(-exact, kind="stable")  # candidates are in rowid order
        if limit is not None:
            order = order[:limit]
        return [(float(exact[i]), self._ids[int(candidates[i])]) for i in order]
