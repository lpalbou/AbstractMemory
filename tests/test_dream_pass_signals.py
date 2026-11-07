"""dream_pass returns the night's signal stream (backlog 0059; the consolidation.py:558-575 gap).

The runtime's night voice read `signals` from the pass RESULT and found nothing: the key existed only on the stored
dream's attributes, so no narration ever fired. The result now carries the same stream the record rests with; a
quiet night returns an empty stream (the key is always present, the cancelled shape mirrors it).

MUTATION: delete `out["signals"] = signals` in dream_pass -> test_dream_pass_returns_the_stream_the_record_carries.
"""

from __future__ import annotations

from abstractmemory import dream_pass, sleep_pass
from abstractmemory.records import MemoryRecordInput, resolve_digest_assertion

SCOPE = "life"
OWNER = "entity:test"
SCOPES = [(SCOPE, OWNER)]


def _remember(system, key, kind, title, digest, **kw):
    [gid] = system.remember_many([MemoryRecordInput(kind=kind, title=title, digest=digest, **kw)],
                                 scope=SCOPE, owner_id=OWNER, idempotency_key=key)
    return gid


def _two_islands(system):
    a = _remember(system, "s-1", "episode", "Pool outage night", "The connection pool saturated at noon.",
                  keywords=("pool", "saturation", "noon"))
    _remember(system, "s-2", "lesson", "Batch the writers", "Batching the noon cron fixed the pool.",
              keywords=("pool", "batching"), edges=(("supports", a),))
    _remember(system, "s-3", "episode", "Garden sensor day", "Planted the garden moisture sensors at noon.",
              keywords=("garden", "sensors", "noon"))


def test_dream_pass_returns_the_stream_the_record_carries(system) -> None:
    _two_islands(system)
    out = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert out["created"] is True and out["dream_record_id"]
    stored = resolve_digest_assertion(system.store, out["dream_record_id"]).attributes
    assert out["signals"] and out["signals"] == stored["signals"]
    assert out["signals_omitted"] == stored["signals_omitted"]


def test_quiet_night_returns_an_empty_stream(system) -> None:
    out = dream_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert out["dream_record_id"] is None
    assert out["signals"] == [] and out["signals_omitted"] == 0


def test_sleep_pass_dream_result_carries_signals_and_the_cancelled_shape_mirrors_it(system) -> None:
    _two_islands(system)
    night = sleep_pass(system, scopes=SCOPES, owner_id=OWNER)
    assert night["dream"]["signals"]
    cancelled = sleep_pass(system, scopes=SCOPES, owner_id=OWNER, should_continue=lambda: False)
    assert cancelled["dream"]["signals"] == [] and cancelled["dream"]["signals_omitted"] == 0
