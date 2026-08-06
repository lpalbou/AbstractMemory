# Contributing

Thanks for your interest in improving AbstractMemory.

This repository uses a `src/` layout and keeps the public API intentionally small.

AbstractMemory is part of the **AbstractFramework** ecosystem (see [`README.md`](README.md) and [`docs/architecture.md`](docs/architecture.md)).

## Development setup

Requirements:
- Python 3.10+ (see `pyproject.toml`)

Install (editable):

```bash
python -m pip install -e ".[dev]"
```

Optional (LanceDB backend + tests):

```bash
python -m pip install -e ".[lancedb]"
```

More details: [`docs/development.md`](docs/development.md).

## Run tests

```bash
python -m pytest -q
```

## What to contribute

Good first contributions:
- Improve docs (keep statements evidence-based and link to code/tests).
- Add tests for edge cases and contracts.
- Make error messages more actionable.
- Add small, well-scoped features that keep the v0 API minimal.

## Contribution guidelines

- Keep changes focused; avoid drive-by refactors.
- Add tests for behavior changes (especially store/query semantics).
- Update docs when you change public behavior:
  - `README.md` and `docs/getting-started.md` for user-facing usage
  - `docs/api.md` for public API contracts
  - `docs/architecture.md` when boundaries/diagrams change
  - `CHANGELOG.md` for notable changes
- If you add a new dependency, keep it optional unless strictly required.

## Citing design records

Three numbered series are referenced from code comments and docs, and their
numbers overlap. Always cite them in the form that names the series:

| Series | Cite as | Lives in |
| --- | --- | --- |
| This package's design records | `0026` (bare number) | [`docs/backlog/`](docs/backlog/) |
| AbstractFramework ADRs | `framework ADR-0026` | `docs/adr/` in the [monorepo](https://github.com/lpalbou/abstractframework) |
| Cross-package agreement threads | `a2a 0003`, `a2a 0001/012` | `a2a/threads/` in the monorepo |

A bare number always means this package's own backlog record. Framework ADRs
and a2a threads live outside this repository, so name them explicitly — both
series run in the same `0001`–`0037` range as the backlog and are otherwise
indistinguishable.

## PR checklist

- `python -m pytest -q` passes locally
- Docs stay evidence-based (link to code/tests for contracts)
- Public API changes are reflected in `src/abstractmemory/__init__.py` and `docs/api.md`

## Security issues

Please do not open public issues for vulnerabilities. See [`SECURITY.md`](SECURITY.md).
