"""AbstractMemory test bootstrap for monorepo layouts + shared fixtures.

See `abstractruntime/tests/conftest.py` for the underlying motivation of the
sys.path bootstrap. The `stack`/`system` fixtures are shared by the facade,
seam-contract, and binding-visibility suites: both layer-1 stacks —
(InMemoryTripleStore + InMemoryJournal) and (SQLiteTripleStore + SQLiteJournal
sharing one file, the 0017 sidecar deployment) — under one facade, so seam
behavior is proven identical on the volatile and durable pairs (0011 parity).
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any, Tuple


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

# Imports below intentionally follow the bootstrap (they need the src path).
import pytest  # noqa: E402

from abstractmemory import (  # noqa: E402
    InMemoryJournal,
    InMemoryTripleStore,
    MemorySystem,
    SQLiteJournal,
    SQLiteTripleStore,
)


@pytest.fixture(params=["memory", "sqlite"])
def stack(request: pytest.FixtureRequest, tmp_path) -> Tuple[Any, Any]:
    if request.param == "memory":
        store = InMemoryTripleStore()
        with warnings.catch_warnings():
            # Volatility #FALLBACK is asserted in the journal suite; keep
            # other suites' warning assertions unpolluted.
            warnings.simplefilter("ignore", RuntimeWarning)
            journal = InMemoryJournal()
    else:
        path = tmp_path / "memory.sqlite3"
        store = SQLiteTripleStore(path)
        journal = SQLiteJournal(path)  # sidecar tables in the SAME file (0017)
    yield store, journal
    journal.close()
    store.close()


@pytest.fixture
def system(stack) -> MemorySystem:
    store, journal = stack
    return MemorySystem(store=store, journal=journal)

