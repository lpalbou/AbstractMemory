# Changelog

All notable changes to this package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (pre-1.0).

## Unreleased

### Changed
- Docs: clarify AbstractFramework ecosystem positioning, update PyPI install wording, and add a gateway-managed embeddings example.
- Docs: align README/API/store/FAQ/agent context with the exported `SQLiteTripleStore` and clarify semantic-query support by backend.
- Docs: document current release-channel drift between this source tree, PyPI, and remote tags.

### Added
- Planned backlog overview and standalone items for semantics-aligned memory records, SQLite compatibility/store capabilities, bounded graph traversal, recall traces, lineage, deterministic anchors, and read-only observer contracts.

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
