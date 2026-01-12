"""AbstractMemory test bootstrap for monorepo layouts.

See `abstractruntime/tests/conftest.py` for the underlying motivation.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _prepend_sys_path(path: Path) -> None:
    p = str(path)
    if p and p not in sys.path:
        sys.path.insert(0, p)


HERE = Path(__file__).resolve()
ABSTRACTMEMORY_ROOT = HERE.parents[1]  # .../abstractmemory
MONOREPO_ROOT = HERE.parents[2]  # .../abstractframework

# Ensure `abstractmemory` resolves to .../abstractmemory/src/abstractmemory (src-layout).
_prepend_sys_path(ABSTRACTMEMORY_ROOT / "src")

# Keep sibling packages stable if future tests import them.
_prepend_sys_path(MONOREPO_ROOT / "abstractcore")
_prepend_sys_path(MONOREPO_ROOT / "abstractruntime" / "src")

