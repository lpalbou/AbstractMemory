# Changelog

All notable changes to this package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (pre-1.0).

## Unreleased

*No unreleased changes.*

## [0.2.6] - 2026-05-09

### Changed
- The `test` optional dependency now installs `lancedb` so release CI exercises
  the persisted LanceDB store contract instead of skipping it.

### Fixed
- `LanceDBTripleStore` now recognizes the current LanceDB `list_tables()`
  response shape, restoring persisted table reopen/query behavior.

## [0.2.5] - 2026-05-08

### Added
- Added GitHub Actions CI for Python 3.10 through 3.12 with pytest and package
  build checks.
- Added a trusted-publishing release workflow for tagged or manually dispatched
  releases, including version/changelog validation, distribution artifacts,
  PyPI publication, and GitHub Release creation.
- Added an AbstractMemory GitHub bug report template.
- Added a `test` optional dependency extra for CI and release validation.

## 0.2.4 - 2026-05-08

### Added
- Added install-profile compatibility extras:
  `AbstractMemory[apple]`, `AbstractMemory[gpu]`,
  `AbstractMemory[all-apple]`, and `AbstractMemory[all-gpu]`.
- Planned backlog overview and standalone items for semantics-aligned memory records, SQLite compatibility/store capabilities, bounded graph traversal, recall traces, lineage, deterministic anchors, and read-only observer contracts.

### Changed
- `AbstractMemory[all-apple]` and `AbstractMemory[all-gpu]` now install the
  LanceDB-backed vector-capable store dependency, matching the existing
  `lancedb`/`all` profile behavior.
- `AbstractMemory[apple]` and `AbstractMemory[gpu]` remain no-op aliases
  because Memory itself has no hardware-specific runtime engine.
- Docs: clarify AbstractFramework ecosystem positioning, update PyPI install wording, and add a gateway-managed embeddings example.
- Docs: align README/API/store/FAQ/agent context with the exported `SQLiteTripleStore` and clarify semantic-query support by backend.
- Docs: document current release-channel drift between this source tree, PyPI, and remote tags.

### Fixed
- Test configuration now declares the local `basic` marker.
- `LanceDBTripleStore` avoids the deprecated LanceDB `table_names()` API when `list_tables()` is available.

## 0.0.2 - 2026-02-04

### Added
- User-facing documentation set with getting started, API, stores, architecture diagram, and FAQ.
- Agent-oriented context files: `llms.txt` and `llms-full.txt`.

### Changed
- `LanceDBTripleStore` non-semantic queries now apply `order` by `observed_at` before applying `limit` (deterministic behavior aligned with `InMemoryTripleStore`).

### Fixed
- Ordering/limit interaction for non-semantic queries in `LanceDBTripleStore` (covered by new tests).

## 0.0.1 - 2026-01-12

### Added
- `TripleAssertion` and `TripleQuery` data models.
- `InMemoryTripleStore` (dependency-free) and `LanceDBTripleStore` (optional).
- `AbstractGatewayTextEmbedder` adapter for gateway-managed embeddings.
