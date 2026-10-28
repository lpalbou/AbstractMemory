"""Tuning constants of the home store (backlog 0058): ONE place, each with
the measurement or the bound it rests on (ADR 0003 enforcement: "threshold
and constant values (vector cache sizes, cursor page sizes) live in one
named module with their measurement quoted").

Numbers measured 2026-10-27 on the operator's Mac (Darwin 27, Python 3.12,
numpy 2.4.6) with `tests/bench/bench_store.py`; the before/after table is in
backlog 0058's Report.
"""

from __future__ import annotations

__all__ = [
    "CADENCE_FEED_PAGE",
    "COARSE_MARGIN_FLOOR",
    "EXACT_CHUNK_ROWS",
    "ID_FETCH_CHUNK",
    "ROW_NORM_RANGE",
    "SUBSET_SHARE",
    "SYNC_FETCH_ROWS",
    "VECTOR_MATRIX_GROWTH",
    "VECTOR_MATRIX_MIN_ROWS",
    "VECTOR_UPGRADE_BATCH",
]

# -- vector matrix (vector_matrix.py) ---------------------------------------

# Floor of the coarse-pass candidate margin, in cosine units. The rigorous
# bound (`coarse_margin`) is 2 * 388 * 2**-24 = 4.6e-5 at 384 dimensions; the
# floor only widens the exact re-scoring set (at 50k random 384-d rows and
# limit 20 it adds no candidate in practice), it never decides a result.
COARSE_MARGIN_FLOOR = 1e-4
# Rows whose non-zero norm lies outside this range skip the float32 pass:
# below it float32 products with the unit-scaled query underflow, above it
# their sums can overflow, so the error bound above no longer holds. Such a
# row is FORCED: always a candidate, scored by the exact pass. Embedding
# models emit norms near 1 (at most a few hundred unnormalised).
ROW_NORM_RANGE = (1e-12, 1e12)
# Below this share of the matrix, the coarse pass multiplies only the
# partition's rows; above it one full matrix-vector product is cheaper than
# gathering the rows (gather copies, the product streams).
SUBSET_SHARE = 0.25
# Rows per exact float64 re-scoring chunk: 4096 x 384 x 8 B = 12.6 MB of
# temporaries, whatever the candidate count (a limit=0 query re-scores all).
EXACT_CHUNK_ROWS = 4096
# Rows per fetch while (re)building or appending the matrix from SQLite.
SYNC_FETCH_ROWS = 4096
# PER-PROCESS FOOTPRINT of the matrix cache (one per store handle that ran a semantic query), held for the
# handle's life: rows x dims x 4 B (float32) + rows x 17 B (inverse norm 8, scope code 4, owner code 4, forced flag
# 1) + the id list and position dict (~150 B per row in CPython). 200k rows x 1024 dims = 819 MB + 3 MB + ~30 MB;
# 50k x 384 = 77 MB. Every process (gateway worker, entity loop) that queries the same home pays it once more.
# A (re)build reserves exactly the vector rows the table holds (one COUNT); later appends grow the arrays by at
# most this share (no doubling: at 200k x 1024 doubling held 1074 MB for 819 MB of vectors, and a growth step
# briefly holds old + new), never less than what the append needs.
VECTOR_MATRIX_GROWTH = 0.10
# Smallest allocation (rows): a tiny home does not regrow on every append.
VECTOR_MATRIX_MIN_ROWS = 1024
# Ids per `assertion_id IN (...)` read of the ranked rows (old SQLite builds
# cap bound variables at 999).
ID_FETCH_CHUNK = 500
# Rows per transaction of the in-place JSON -> BLOB upgrade: bounds the WAL
# growth and the write-lock hold; the `vector_blob_high_water` cursor makes
# an interrupted upgrade resume. Measured: see `upgrade_open_s` in the 0058
# report (50k rows of 384-d JSON vectors).
VECTOR_UPGRADE_BATCH = 2000

# -- maintenance cadence (sleep_cadence.py) ---------------------------------

# Rows per page of the store change feed (`assertions_after`) the cadence
# fold reads: bounds one read whatever the backlog since the last check.
CADENCE_FEED_PAGE = 2000
