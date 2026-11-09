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
    """rewrite_digest / retitle / declare_pending / rearm_pending / rekey_world_model / narrate_dream / revert_digest /
    versions / current_of / record_understanding, and the queue reads understanding_debt / enqueue_debt /
    pending_records / task_packet (0060)."""

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

    def retitle(
        self, record_id: str, *, title: str, author: Mapping[str, Any],
        cause: Union[str, Mapping[str, Any]], expected_version: int,
        reader: Optional[Mapping[str, Any]] = None, sources: Sequence[Mapping[str, Any]] = (),
        task_id: Optional[str] = None, understood_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Change only a record's title in place, keeping every earlier title as a version (understanding.retitle)."""
        return _u.retitle(
            self, record_id, title=title, author=author, cause=cause, expected_version=expected_version,
            reader=reader, sources=sources, task_id=task_id, understood_at=understood_at)

    def declare_pending(
        self, record_id: str, *, fields: Sequence[str] = ("title", "summary"),
        cause: Union[str, Mapping[str, Any]] = "repair", reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Declare a stored record's title and/or summary still being written: formation's marker and authoring
        tasks, in one transaction (understanding.declare_pending)."""
        return _u.declare_pending(self, record_id, fields=fields, cause=cause, reason=reason)

    def rearm_pending(
        self, record_id: str, *, cause: Union[str, Mapping[str, Any]] = "repair", reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Re-arm a pending record whose authoring ran out (a pending field with no live task): fresh formation
        tasks, the marker kept, in one transaction (understanding.rearm_pending)."""
        return _u.rearm_pending(self, record_id, cause=cause, reason=reason)

    def rekey_world_model(
        self, old_key: str, new_key: str, *, scope: str, owner_id: str, author: Mapping[str, Any],
        cause: Union[str, Mapping[str, Any]], reason: Optional[str] = None,
        reader: Optional[Mapping[str, Any]] = None, sources: Sequence[Mapping[str, Any]] = (),
    ) -> Dict[str, Any]:
        """Move a standing world-model card to a new key in place, the old key kept as an alias
        (world_model_alias.rekey_world_model)."""
        from .world_model_alias import rekey_world_model

        return rekey_world_model(self, old_key, new_key, scope=scope, owner_id=owner_id, author=author, cause=cause,
                                 reason=reason, reader=reader, sources=sources)

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

    # -- the memory task queue (0060; the queue object itself is `self.tasks`) --------------------------------

    def understanding_debt(self, *, scopes: Sequence[Any], methods: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        """What is still in mechanical words, and the queue's state (memory_tasks.understanding_debt)."""
        from .memory_tasks import understanding_debt

        return understanding_debt(self, scopes=scopes, methods=methods)

    def enqueue_debt(self, *, scopes: Sequence[Any], cause: str = "backfill", priority: int = 90,
                     dry_run: bool = True, methods: Optional[Sequence[str]] = None,
                     kinds: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        """The backfill: a task per un-queued debt record, dry-run by default (memory_tasks.enqueue_debt)."""
        from .memory_tasks import enqueue_debt

        return enqueue_debt(self, scopes=scopes, cause=cause, priority=priority, dry_run=dry_run,
                            methods=methods, kinds=kinds)

    def pending_records(self, *, scopes: Optional[Sequence[Any]] = None,
                        live_task: Optional[bool] = False) -> List[Dict[str, Any]]:
        """The records still marked pending; by default those with a pending field no live task owns, the ones
        `rearm_pending` re-arms (memory_tasks.pending_records)."""
        from .memory_tasks import pending_records

        return pending_records(self, scopes=scopes, live_task=live_task)

    # -- the ripple (0061) ---------------------------------------------------------------------------------------

    def seed_ripple(
        self, seed_id: str, *, cause: Union[str, Mapping[str, Any]], change: str = "revised",
        magnitude: Optional[float] = None, cosine_distance: Optional[float] = None, surprise: Optional[str] = None,
        reconsider_seed: Optional[bool] = None, budget: int = 20, dry_run: bool = False, now: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Open a ripple from a changed memory (ripple.seed_ripple)."""
        from .ripple import seed_ripple

        return seed_ripple(self, seed_id, cause=cause, change=change, magnitude=magnitude,
                           cosine_distance=cosine_distance, surprise=surprise, reconsider_seed=reconsider_seed,
                           budget=budget, dry_run=dry_run, now=now)

    def settle_reconsideration(
        self, task_id: str, *, holder: str, outcome: str, change: Optional[str] = None,
        cosine_distance: Optional[float] = None, result: Optional[Mapping[str, Any]] = None,
        now: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Settle one ripple.reconsider task and hand the change on (ripple.settle_reconsideration)."""
        from .ripple import settle_reconsideration

        return settle_reconsideration(self, task_id, holder=holder, outcome=outcome, change=change,
                                      cosine_distance=cosine_distance, result=result, now=now)

    def form_consolidation(
        self, task_id: str, *, holder: str, text: str, title: str, author: Mapping[str, Any],
        reader: Optional[Mapping[str, Any]] = None, sources: Sequence[Mapping[str, Any]] = (),
        keywords: Sequence[str] = (), now: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Form a ripple's "what this changes" record in a night window (ripple.form_consolidation)."""
        from .ripple import form_consolidation

        return form_consolidation(self, task_id, holder=holder, text=text, title=title, author=author,
                                  reader=reader, sources=sources, keywords=keywords, now=now)

    def refresh_ripples(self, *, now: Optional[str] = None) -> List[Dict[str, str]]:
        """Close settled ripples, enqueue their consolidations (ripple.refresh_ripples)."""
        from .ripple import refresh_ripples

        return refresh_ripples(self, now=now)

    def revert_ripple(self, ripple_id: str, *, by: Optional[Mapping[str, Any]] = None,
                      reason: Optional[str] = None) -> List[Dict[str, Any]]:
        """Restore what a ripple changed (ripple.revert_ripple)."""
        from .ripple import revert_ripple

        return revert_ripple(self, ripple_id, by=by, reason=reason)

    def ripples(self, *, scope: Optional[str] = None, owner_id: Optional[str] = None,
                status: Optional[Sequence[str]] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Ripples, newest first (ripple.ripples)."""
        from .ripple import ripples

        return ripples(self, scope=scope, owner_id=owner_id, status=status, limit=limit)

    def ripple(self, ripple_id: str) -> Dict[str, Any]:
        """One ripple with its members and gate decisions (ripple.ripple)."""
        from .ripple import ripple

        return ripple(self, ripple_id)

    def task_packet(self, task_id: str, *, token_budget: int = 56_000) -> Dict[str, Any]:
        """Everything a reader needs for one task, items whole within a token budget (memory_tasks.task_packet)."""
        from .memory_tasks import task_packet

        return task_packet(self, task_id, token_budget=token_budget)
