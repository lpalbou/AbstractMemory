# Changelog

All notable changes to this package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (pre-1.0).

## Unreleased

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
