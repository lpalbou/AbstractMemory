"""Archive import (fork 720): manifest-driven, dry-run-first, idempotent.

SYNTHETIC FIXTURES ONLY — the real lineage archive is the maintainer's and
is never touched by tests or agents (the module's standing guard).
"""

from __future__ import annotations

import warnings as _w

import pytest

_w.filterwarnings("ignore", message=".*InMemoryJournal is volatile.*")

from abstractmemory import (
    InMemoryJournal,
    InMemoryTripleStore,
    MemorySystem,
    Stimulus,
    TripleQuery,
)
from abstractmemory.archive_import import ArchiveFile, apply_import, plan_import

OWNER = "entity:import-test"
SCOPE = "life"


@pytest.fixture()
def archive(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "values.md").write_text(
        "# Intellectual honesty\nAlways say what is true, even when costly.\n",
        encoding="utf-8")
    (tmp_path / "notes" / "2025-03-14_first_meeting.md").write_text(
        "# The first meeting\nWe met at noon and talked about bridges for an hour.\n",
        encoding="utf-8")
    (tmp_path / "notes" / "protocol_sleep.md").write_text(
        "# Sleep protocol\n1. Tend the graph.\n2. Dream once.\n",
        encoding="utf-8")
    (tmp_path / "rel_laurent.md").write_text(
        "# Laurent\nThe maintainer. feel: person:laurent +3 trusted me with the archive\n",
        encoding="utf-8")
    (tmp_path / "index.md").write_text(
        "The first meeting: bridges, noon, beginnings\n", encoding="utf-8")
    (tmp_path / "verbatim_meeting.md").write_text(
        "FULL TRANSCRIPT: every word of the first meeting …\n", encoding="utf-8")
    return tmp_path


def _manifest():
    return [
        ArchiveFile(path="values.md", category="value"),
        ArchiveFile(path="notes/2025-03-14_first_meeting.md", category="history"),
        ArchiveFile(path="notes/protocol_sleep.md", category="protocol"),
        ArchiveFile(path="rel_laurent.md", category="relationship",
                    participants=("person:laurent",)),
        ArchiveFile(path="index.md", category="memory_index"),
        ArchiveFile(path="verbatim_meeting.md", category="verbatim",
                    attach_to="The first meeting"),
    ]


def test_unknown_category_refuses_loudly() -> None:
    with pytest.raises(ValueError, match="unknown archive category"):
        ArchiveFile(path="x.md", category="vibes")


def test_plan_is_a_pure_dry_run_with_pinned_provenance(archive) -> None:
    plan = plan_import(str(archive), _manifest())
    # Values → spark draft, never records.
    assert "value" in plan.spark_draft
    kinds = {r.kind for r in plan.records}
    assert kinds == {"episode", "instruction"}
    # Provenance: path + sha256 pinned on every record (fork 720).
    for r in plan.records:
        assert r.provenance["source"] == "archive-import"
        assert r.provenance["archive_path"] and r.provenance["archive_sha256"]
    # Dated file → origin_date attribute; observed_at stays import-time.
    meeting = next(r for r in plan.records if "first meeting" in r.title.lower())
    assert meeting.attributes["origin_date"] == "2025-03-14"
    # Index enrichment reached the record's keywords.
    assert "bridges" in meeting.keywords
    # Verbatim attached as a REFERENCE, never inlined.
    assert meeting.payload_ref == "verbatim_meeting.md"
    assert "FULL TRANSCRIPT" not in meeting.digest
    # Feelings are PROPOSED, not applied.
    assert plan.proposed_appraisals[0]["target"] == "person:laurent"
    assert plan.proposed_appraisals[0]["value"] == 3
    # The spark-review warning is on the plan.
    assert any("REVIEW REQUIRED" in w for w in plan.warnings)


def test_missing_files_warn_never_crash(archive) -> None:
    plan = plan_import(str(archive), [
        ArchiveFile(path="values.md", category="value"),
        ArchiveFile(path="ghost.md", category="history"),
    ])
    assert any("cannot read" in w for w in plan.warnings)


def test_reordered_manifest_reimports_into_the_same_records(archive) -> None:
    """Record ids derive from (batch key, position); batching is sorted by
    content key so manifest ORDER never changes identity — a reordered
    re-import mints zero new records."""
    system = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())
    manifest = _manifest()
    first = apply_import(system, plan_import(str(archive), manifest),
                         scope=SCOPE, owner_id=OWNER)
    reordered = list(reversed(manifest))
    second = apply_import(system, plan_import(str(archive), reordered),
                          scope=SCOPE, owner_id=OWNER)
    assert sorted(first["record_ids"]) == sorted(second["record_ids"])
    rows = [a for a in system.store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))
            if isinstance(a.attributes, dict) and a.attributes.get("record_kind")]
    assert len({a.subject for a in rows}) == len(first["record_ids"])


def test_incremental_import_never_remints_unchanged_files(archive) -> None:
    """THE adversary P0: record identity is a pure function of FILE CONTENT.
    Growing the archive (the normal incremental case) must not re-mint ids
    for unchanged files — no silent duplicates in a never-purge graph."""
    system = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())
    manifest = _manifest()
    first = apply_import(system, plan_import(str(archive), manifest),
                         scope=SCOPE, owner_id=OWNER)
    # Grow the archive by one file and re-import EVERYTHING.
    (archive / "notes" / "2025-06-01_second_meeting.md").write_text(
        "# The second meeting\nWe reviewed the bridges plan again.\n", encoding="utf-8")
    grown = manifest + [ArchiveFile(path="notes/2025-06-01_second_meeting.md",
                                    category="history")]
    second = apply_import(system, plan_import(str(archive), grown),
                          scope=SCOPE, owner_id=OWNER)
    assert set(first["record_ids"]) <= set(second["record_ids"])  # old ids unchanged
    assert len(set(second["record_ids"])) == len(first["record_ids"]) + 1
    rows = [a for a in system.store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))
            if isinstance(a.attributes, dict) and a.attributes.get("record_kind")]
    assert len({a.subject for a in rows}) == len(first["record_ids"]) + 1  # zero duplicates


def test_verbatim_and_index_paths_are_contained_and_typos_warn(archive) -> None:
    plan = plan_import(str(archive), [
        ArchiveFile(path="values.md", category="value"),
        ArchiveFile(path="notes/2025-03-14_first_meeting.md", category="history"),
        ArchiveFile(path="../outside.md", category="verbatim", attach_to="The first meeting"),
        ArchiveFile(path="../outside_index.md", category="memory_index"),
        ArchiveFile(path="verbatim_meeting.md", category="verbatim", attach_to="No Such Title"),
    ])
    text = " ".join(plan.warnings)
    assert text.count("escapes the archive root") == 2  # verbatim + index both contained
    assert "matched no imported record" in text          # attach_to typo named
    # The escaping verbatim never became a payload_ref.
    assert all(r.payload_ref != "../outside.md" for r in plan.records)


def test_paths_escaping_the_archive_root_are_refused(archive, tmp_path) -> None:
    outside = tmp_path.parent / "outside-secret.md"
    try:
        outside.write_text("secret", encoding="utf-8")
        plan = plan_import(str(archive), [
            ArchiveFile(path="values.md", category="value"),
            ArchiveFile(path="../outside-secret.md", category="history"),
        ])
        assert any("escapes the archive root" in w for w in plan.warnings)
        assert all("secret" not in r.digest for r in plan.records)
    finally:
        outside.unlink(missing_ok=True)


def test_apply_is_idempotent_and_never_touches_identity(archive) -> None:
    system = MemorySystem(store=InMemoryTripleStore(), journal=InMemoryJournal())
    plan = plan_import(str(archive), _manifest())
    first = apply_import(system, plan, scope=SCOPE, owner_id=OWNER)
    again = apply_import(system, plan, scope=SCOPE, owner_id=OWNER)
    assert first["record_ids"] == again["record_ids"]  # content-hash idempotency
    rows = [a for a in system.store.query(TripleQuery(scope=SCOPE, owner_id=OWNER, limit=0))
            if isinstance(a.attributes, dict) and a.attributes.get("record_kind")]
    subjects = {a.subject for a in rows}
    assert len(subjects) == len(first["record_ids"])  # no dupes
    # NOTHING landed in self scope; the spark draft is returned for review.
    self_rows = system.store.query(TripleQuery(scope="self", owner_id=OWNER, limit=0))
    assert not self_rows
    assert "value" in first["spark_draft"]
    # Imported records are recallable (life scope, on merit).
    r = system.reconstruct(Stimulus(cue_text="bridges meeting noon"),
                           scopes=[(SCOPE, OWNER)])
    assert any("first meeting" in h.title.lower() for h in r.handles)
    # And the observer can tell seeded from lived.
    assert all(a.attributes.get("seeded_from") == "archive-import"
               for a in rows if a.attributes.get("record_kind") in ("episode", "instruction"))
