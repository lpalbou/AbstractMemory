"""The commit guard: the memory half of a host's Stop fence.

A host that must be able to refuse every memory write from a moment it decides passes
`MemorySystem(..., commit_guard=guard)`; the runtime passes its lifecycle fence's `check`, so an operator's Stop
refuses every later commit. The guard is a callable taking one string, the name of the commit point (`where`): it
returns to let the write commit and raises to refuse it. Memory never learns why: it knows no entity, no
generation, no Stop.

- Installed on the system's store and journal (`install_commit_guard`), so every write through them is guarded,
  whoever makes it: the facade, `MemoryGraph(store, journal)`, the task queue (it rides the store), the sleep
  passes, `record_maintenance`.
- Called INSIDE every write transaction, immediately before its COMMIT, with the write lock held (SQLite: inside
  BEGIN IMMEDIATE). An in-memory double has no COMMIT: it calls the guard under its lock immediately before its first
  mutation (the in-memory graph, which keeps an undo log, before it keeps its changes).
- Raises -> ROLLBACK: nothing of that transaction lands and memory records nothing about the refusal; the exception
  propagates unchanged to the caller.
- ONE call per outermost write: a write nested in its caller's transaction (a cursor passed in, or a write made
  inside `deferred_to_caller`) does not call it again.
- The cost is the host's: memory adds an attribute read and one call, never a file read, stat, lock or subprocess.
  The guard runs inside the transaction, so it must not take a lock a writer may hold.

The closed set of commit points is pinned by tests/test_commit_guard.py.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator

__all__ = ["CommitGuard", "deferred_to_caller", "guard_commit", "install_commit_guard"]

CommitGuard = Callable[[str], None]

# Per thread: the guards whose call an outer write on this thread owns (deferred_to_caller).
_held = threading.local()


def guard_commit(owner: Any, where: str) -> None:
    """Call `owner`'s commit guard, if it has one, unless an outer write on this thread owns the call. A commit point
    calls this immediately before its COMMIT; whatever the guard raises propagates (the caller rolls back)."""
    guard = getattr(owner, "_commit_guard", None)
    if guard is None:
        return
    deferred = getattr(_held, "guards", None)
    if deferred and guard in deferred:
        return
    guard(where)


@contextmanager
def deferred_to_caller(owner: Any) -> Iterator[None]:
    """The writes made inside belong to the caller's own commit, which calls `owner`'s guard once itself: a composed
    write with no single COMMIT (an in-memory double, or SQLite rows written beside in-memory ones)."""
    guard = getattr(owner, "_commit_guard", None)
    if guard is None:
        yield
        return
    stack = _held.__dict__.setdefault("guards", [])
    stack.append(guard)
    try:
        yield
    finally:
        stack.pop()


def install_commit_guard(guard: CommitGuard, *owners: Any) -> None:
    """Install `guard` on each store/journal (all or none). Refuses a type whose commit points do not call a guard,
    and a substrate already guarded by a different guard (one guard per store: two would make whichever was
    installed last decide for both)."""
    if not callable(guard):
        raise TypeError(f"commit_guard must be callable (got {type(guard).__name__})")
    for owner in owners:
        if not hasattr(type(owner), "_commit_guard"):
            raise TypeError(
                f"{type(owner).__name__} cannot honour a commit guard: its writes do not call one "
                "(SQLiteTripleStore, InMemoryTripleStore, LanceDBTripleStore, SQLiteJournal, InMemoryJournal do)")
        held = owner._commit_guard
        if held is not None and held != guard:
            raise ValueError(
                f"this {type(owner).__name__} is already guarded by another commit guard: open the home's "
                "store and journal afresh for a new guard")
    for owner in owners:
        owner._commit_guard = guard
