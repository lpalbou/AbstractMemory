"""Binary vectors and the in-process vector matrix of the SQLite store
(backlog 0058; ADR 0003 decision 3).

Encoding: a stored vector is a float32 little-endian BLOB (4 bytes per
dimension; the JSON text it replaces cost ~20 bytes per dimension and a
`json.loads` per row per query). `decode_vector` reads both encodings, so a
home part-way through its in-place upgrade, or written to by an older
process, keeps serving every row. `encode_vector` refuses a finite value
float32 cannot hold (it would become infinity): nothing is clipped silently.

Scoring: `VectorMatrix` holds one store's vectored rows as a float32 matrix
in memory, keyed by assertion id, with the (scope, owner_id) of each row so
the vector channel's partition filter is a mask instead of a query. It is
built once from a scan, then APPENDED from the rows above its rowid
high-water (the store's own adds and any other writer's), and dropped when
the vectors are rewritten (`replace_vectors` or the in-place upgrade,
detected across handles and processes by the `vector_generation` meta key
and the embedding pin).

Ranking is EXACTLY the reference scan (`vector_scoring.rank_by_cosine`):
same rows, same order, bit-identical scores.
- A float32 pass over unit-scaled vectors selects the candidates. Its error
  is bounded by the standard dot-product bound (dim + 4) * 2**-24 in cosine
  units (the +4 covers the query's and a legacy row's rounding to float32);
  candidates are kept within TWICE that bound of the min_score floor and of
  the limit-th coarse score, so no row of the exact answer can be dropped.
- The candidates are re-scored in float64 with the reference arithmetic:
  products summed left to right (`cumsum`, never pairwise or BLAS
  summation, which differ from `vector_scoring.cosine` in the last bits on
  most rows), `sqrt(|q|^2) * sqrt(|r|^2)` as the denominator, 0.0 for a
  zero vector; min_score applies to those exact scores, before the limit;
  ties keep rowid order (the reference scan reads rows in rowid order).
- Legacy JSON rows hold float64 values: the matrix keeps their float64
  originals beside the float32 row and the exact pass scores those. A row
  outside the float32 pass's error bound (a norm outside `ROW_NORM_RANGE`,
  a legacy value beyond float32) is FORCED: always a candidate, scored
  exactly from its float64 values.

numpy is OPTIONAL (`pip install "abstractmemory[fast]"`). Without it, or
when a store holds vectors the matrix cannot score exactly (mixed
dimensions, non-finite values, an empty vector, JSON that is not a list of
numbers, a query of another dimension, a score that overflows), the store
uses the reference Python scan and says so once per store handle with a
`#FALLBACK` warning; results are the same, only slower.
"""

from __future__ import annotations

import json
import math
import sys
from array import array
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .store_tuning import (  # re-exported; the constants live in one place
    COARSE_MARGIN_FLOOR,
    EXACT_CHUNK_ROWS,
    ID_FETCH_CHUNK,
    ROW_NORM_RANGE,
    SUBSET_SHARE,
    SYNC_FETCH_ROWS,
    VECTOR_UPGRADE_BATCH,
)

try:  # optional accelerator; the Python scan is the labelled fallback
    import numpy as _np
except Exception:  # pragma: no cover - exercised by monkeypatching _np
    _np = None

__all__ = [
    "COARSE_MARGIN_FLOOR",
    "EXACT_CHUNK_ROWS",
    "ID_FETCH_CHUNK",
    "ROW_NORM_RANGE",
    "SUBSET_SHARE",
    "SYNC_FETCH_ROWS",
    "VECTOR_ENGINE_NUMPY",
    "VECTOR_ENGINE_PYTHON",
    "VECTOR_UPGRADE_BATCH",
    "VectorMatrix",
    "coarse_margin",
    "decode_vector",
    "encode_vector",
    "numpy_module",
    "VECTOR_ENCODING_KEY",
    "VECTOR_ENCODING_FLOAT32_BLOB",
]

VECTOR_ENGINE_NUMPY = "numpy-matrix-cache"
VECTOR_ENGINE_PYTHON = "python-linear-scan"
#: The stored vector encoding a 0.4.0 home declares in its meta table (key `vector_encoding`) once its JSON vectors
#: were rewritten: a ONE-WAY migration (a 0.3.x reader decodes JSON only and silently finds no vectors), so a reader
#: can tell what it opened.
VECTOR_ENCODING_KEY = "vector_encoding"
VECTOR_ENCODING_FLOAT32_BLOB = "float32-blob"

# float32 unit roundoff.
_U32 = 2.0 ** -24


def coarse_margin(dim: int) -> float:
    """Candidate margin of the float32 pass at `dim` dimensions: twice the
    worst-case error of a float32 cosine of unit-scaled vectors
    (gamma_{dim+4} = (dim+4)u / (1 - (dim+4)u)), floored."""
    n = (int(dim) + 4) * _U32
    return max(COARSE_MARGIN_FLOOR, 2.0 * n / (1.0 - n))


def numpy_module() -> Any:
    """The numpy module, or None when it is not importable."""
    return _np


def encode_vector(vector: Sequence[float]) -> bytes:
    """float32 little-endian bytes of a vector. Raises ValueError for a finite
    value outside the float32 range (it would be stored as infinity)."""
    values = [float(x) for x in vector]
    packed = array("f", values)
    for stored, given in zip(packed, values):
        if math.isinf(stored) and not math.isinf(given):
            raise ValueError(
                f"vector component {given!r} is outside the float32 range; "
                "the store keeps vectors as float32 (backlog 0058)")
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


# `_decode`'s norm for a forced row (see there).
_FORCED = -1.0


class _Unrepresentable(Exception):
    """The matrix cannot serve this query exactly; use the Python scan."""


def _sequential_sum(np: Any, products: Any) -> Any:
    """Row sums added left to right, as `vector_scoring.cosine` does
    (`np.sum` is pairwise and BLAS reorders: both differ in the last bits).
    `+ 0.0` turns the -0.0 of an all-negative-zero row into the reference's
    0.0."""
    return np.cumsum(products, axis=-1)[..., -1] + 0.0


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
        # False once a vector the matrix cannot score exactly was seen: the
        # store then serves the Python scan until the cache is rebuilt.
        self.exact = True
        self.inexact_reason = ""
        # Rows handed to `append` so far, i.e. read from the table (a
        # test/diagnostic counter: appends are O(new rows), never a rescan).
        self.rows_read = 0
        self._capacity = 0
        self._matrix = np.zeros((0, 0), dtype=np.float32)
        self._inv_norm = np.zeros(0, dtype=np.float64)
        self._forced = np.zeros(0, dtype=bool)
        self._scope = np.zeros(0, dtype=np.int32)
        self._owner = np.zeros(0, dtype=np.int32)
        self._ids: List[str] = []
        self._position: Dict[str, int] = {}
        self._scope_codes: Dict[Any, int] = {}
        self._owner_codes: Dict[Any, int] = {}
        # Rows whose float64 values float32 does not hold exactly (legacy
        # JSON) and forced rows: position -> float64 original (the exact
        # pass scores it).
        self._wide: Dict[int, Any] = {}

    # -- building ---------------------------------------------------------

    def append(self, rows: Iterable[Tuple[int, str, str, Optional[str], Any]]) -> int:
        """Add rows `(rowid, assertion_id, scope, owner_id, raw_embedding)`
        in rowid order. Rows without a vector only advance the high-water;
        an id already present is skipped. Returns the number of vectors
        added."""
        np = _np
        fresh: List[Tuple[str, str, Optional[str], Any, Any, float]] = []
        for rowid, assertion_id, scope, owner, raw in rows:
            rowid = int(rowid)
            if rowid > self.high_water:
                self.high_water = rowid
            self.rows_read += 1
            if raw is None or not self.exact or assertion_id in self._position:
                continue
            decoded = self._decode(raw)
            if decoded is None:
                continue  # unreadable / not a list: the reference skips it too
            if not self.exact:
                return 0
            narrow, wide, norm = decoded
            fresh.append((assertion_id, scope, owner, narrow, wide, norm))
        if not fresh:
            return 0
        start = self.size
        end = start + len(fresh)
        self._reserve(end)
        self._matrix[start:end] = np.vstack([f[3] for f in fresh])
        for offset, (assertion_id, scope, owner, _, wide, norm) in enumerate(fresh):
            pos = start + offset
            self._inv_norm[pos] = 1.0 / norm if norm > 0.0 else 0.0
            self._forced[pos] = norm == _FORCED
            if wide is not None:
                self._wide[pos] = wide
            self._scope[pos] = self._scope_codes.setdefault(scope, len(self._scope_codes))
            self._owner[pos] = self._owner_codes.setdefault(owner, len(self._owner_codes))
            self._ids.append(assertion_id)
            self._position[assertion_id] = pos
        self.size = end
        return len(fresh)

    def _inexact(self, reason: str) -> None:
        self.exact = False
        self.inexact_reason = reason

    def _decode(self, raw: Any) -> Optional[Tuple[Any, Any, float]]:
        """`(float32 row, float64 original or None, norm)` for a stored vector;
        None when the reference scan would skip the row; marks the matrix
        inexact (and returns a placeholder) when only the scan can score
        it."""
        np = _np
        wide = None
        if isinstance(raw, (bytes, bytearray, memoryview)):
            data = bytes(raw)
            if len(data) % 4:
                return None  # decode_vector: unreadable -> vectorless
            narrow = np.frombuffer(data, dtype="<f4")
        else:
            listed = decode_vector(raw)
            if listed is None:
                return None
            try:
                wide = np.asarray([float(x) for x in listed], dtype=np.float64)
            except (TypeError, ValueError, OverflowError):
                self._inexact("a stored JSON vector holds non-numeric values")
                return (None, None, 0.0)
            with np.errstate(over="ignore"):
                narrow = wide.astype(np.float32)
            if np.array_equal(narrow, wide):
                wide = None  # float32 holds it exactly: no side copy
        reference = wide if wide is not None else narrow
        if narrow.ndim != 1 or narrow.shape[0] == 0:
            self._inexact("a stored vector is empty")
            return (None, None, 0.0)
        if self.dim is not None and narrow.shape[0] != self.dim:
            self._inexact(f"stored vectors of {self.dim} and {narrow.shape[0]} dimensions")
            return (None, None, 0.0)
        if not np.isfinite(reference).all():
            self._inexact("a stored vector holds non-finite values")
            return (None, None, 0.0)
        if self.dim is None:
            self.dim = int(narrow.shape[0])
        wide64 = reference.astype(np.float64)
        with np.errstate(over="ignore"):
            norm = math.sqrt(float(wide64 @ wide64))
        low, high = ROW_NORM_RANGE
        if not np.isfinite(narrow).all() or (norm > 0.0 and not (low <= norm <= high)):
            # Outside the float32 pass's error bound (a legacy JSON value
            # beyond float32, or a norm outside ROW_NORM_RANGE): the row is
            # FORCED, i.e. always a candidate of the exact pass, scored from
            # its float64 values; its float32 row is zeros.
            return np.zeros(self.dim, dtype=np.float32), wide64, _FORCED
        return narrow, wide, norm

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
        self._forced = grown(self._forced, bool)
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

    def _exact_scores(self, positions: Any, q64: Any, q_sq: float) -> Any:
        """Reference cosine (`vector_scoring.cosine`), bit for bit, for the
        rows at `positions`."""
        np = _np
        out = np.zeros(len(positions), dtype=np.float64)
        if q_sq <= 0.0:
            return out  # reference: a zero query scores every row 0.0
        q_root = math.sqrt(q_sq)
        for k in range(0, len(positions), EXACT_CHUNK_ROWS):
            idx = positions[k:k + EXACT_CHUNK_ROWS]
            wide = self._matrix[idx].astype(np.float64)
            if self._wide:
                for j, pos in enumerate(idx.tolist()):
                    original = self._wide.get(pos)
                    if original is not None:
                        wide[j] = original
            dots = _sequential_sum(np, wide * q64)
            r_sq = _sequential_sum(np, wide * wide)
            with np.errstate(divide="ignore", invalid="ignore"):
                scores = np.where(r_sq > 0.0, dots / (q_root * np.sqrt(r_sq)), 0.0)
            out[k:k + len(idx)] = scores
        if not np.isfinite(out).all():
            raise _Unrepresentable("an exact score is not finite")
        return out

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
            raise _Unrepresentable(self.inexact_reason or "the matrix cannot score these vectors exactly")
        if len(positions) == 0:
            return []
        q64 = np.asarray([float(x) for x in query_vector], dtype=np.float64)
        if self.dim is None or q64.shape[0] != self.dim:
            raise _Unrepresentable(
                f"a {q64.shape[0]}-dimension query against {self.dim}-dimension vectors "
                "(the reference scores the overlapping prefix)")
        if not np.isfinite(q64).all():
            raise _Unrepresentable("the query vector holds non-finite values")
        q_sq = float(_sequential_sum(np, q64 * q64))
        if not math.isfinite(q_sq):
            raise _Unrepresentable("the query vector's norm overflows")
        candidates = positions
        forced = positions[self._forced[positions]] if self._wide else positions[:0]
        if len(forced):
            candidates = positions[~self._forced[positions]]
        if q_sq > 0.0:
            unit = (q64 / math.sqrt(q_sq)).astype(np.float32)
            matrix = self._matrix[: self.size]
            if len(candidates) < SUBSET_SHARE * self.size:
                dots = matrix[candidates] @ unit
            else:
                dots = (matrix @ unit)[candidates]
            coarse = dots.astype(np.float64) * self._inv_norm[candidates]
            margin = coarse_margin(self.dim)
            if min_score is not None:
                keep = coarse >= float(min_score) - margin
                candidates, coarse = candidates[keep], coarse[keep]
            if limit is not None and len(candidates) > limit:
                kth = np.partition(coarse, len(coarse) - limit)[len(coarse) - limit]
                candidates = candidates[coarse >= kth - margin]
        if len(forced):
            candidates = np.union1d(candidates, forced)  # sorted: rowid order
        if len(candidates) == 0:
            return []
        exact = self._exact_scores(candidates, q64, q_sq)
        if min_score is not None:
            keep = ~(exact < float(min_score))
            candidates, exact = candidates[keep], exact[keep]
        order = np.argsort(-exact, kind="stable")  # candidates are in rowid order
        if limit is not None:
            order = order[:limit]
        return [(float(exact[i]), self._ids[int(candidates[i])]) for i in order]
