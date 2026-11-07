"""MemorySystem's understanding surface (mixin — split for the <600 rule; backlog 0059).

Thin delegates to `understanding.py`: a record's digest, a card's text and a dream's narration are rewritten IN
PLACE with every earlier reading kept as a version (operator ruling 2026-11-07). See that module for the
transaction, the refusals and the provenance vocabulary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from . import understanding as _u

__all__ = ["UnderstandingOps"]


class UnderstandingOps:
    """rewrite_digest / narrate_dream / revert_digest / versions / current_of / record_understanding."""

    def rewrite_digest(
        self, record_id: str, *, text: str, author: Mapping[str, Any],
        cause: Union[str, Mapping[str, Any]], expected_version: int,
        reader: Optional[Mapping[str, Any]] = None, sources: Sequence[Mapping[str, Any]] = (),
        derived_from: Sequence[str] = (), title: Optional[str] = None,
        keywords: Optional[Sequence[str]] = None, digest_method: str = _u.DEFAULT_AUTHORED_METHOD,
        magnitude: Optional[Mapping[str, Any]] = None, task_id: Optional[str] = None,
        understood_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Replace a record's digest in place, keeping every earlier reading (understanding.rewrite_digest)."""
        return _u.rewrite_digest(
            self, record_id, text=text, author=author, cause=cause, expected_version=expected_version,
            reader=reader, sources=sources, derived_from=derived_from, title=title, keywords=keywords,
            digest_method=digest_method, magnitude=magnitude, task_id=task_id, understood_at=understood_at)

    def narrate_dream(
        self, dream_id: str, *, text: str, author: Mapping[str, Any], expected_version: int = 0,
        reader: Optional[Mapping[str, Any]] = None, sources: Sequence[Mapping[str, Any]] = (),
        cause: Union[str, Mapping[str, Any]] = "formation", task_id: Optional[str] = None,
        understood_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Store a narration beside a dream's mechanical summary (understanding.narrate_dream)."""
        return _u.narrate_dream(
            self, dream_id, text=text, author=author, expected_version=expected_version, reader=reader,
            sources=sources, cause=cause, task_id=task_id, understood_at=understood_at)

    def revert_digest(
        self, record_id: str, to_version: int, *, expected_version: int,
        by: Optional[Mapping[str, Any]] = None, reason: Optional[str] = None, field: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restore an earlier reading as a new version (understanding.revert_digest)."""
        return _u.revert_digest(self, record_id, to_version, expected_version=expected_version, by=by,
                                reason=reason, field=field)

    def versions(self, record_id: str, *, field: Optional[str] = None) -> List[Dict[str, Any]]:
        """Every reading of a record, oldest first (understanding.versions)."""
        return _u.versions(self, record_id, field=field)

    def current_of(self, record_id: str) -> Dict[str, Any]:
        """Follow supersede closures to the live record (understanding.current_of)."""
        return _u.current_of(self, record_id)

    def record_understanding(self, record_id: str) -> Dict[str, Any]:
        """The record read the gateway serves (understanding.record_understanding)."""
        return _u.record_understanding(self, record_id)
