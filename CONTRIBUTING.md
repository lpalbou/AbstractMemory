# Contributing

Thanks for your interest in improving AbstractMemory.

This repository uses a `src/` layout and keeps the public API intentionally small.

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
  - `CHANGELOG.md` for notable changes
- If you add a new dependency, keep it optional unless strictly required.

## Security issues

Please do not open public issues for vulnerabilities. See [`SECURITY.md`](SECURITY.md).
