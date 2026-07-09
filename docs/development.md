# Development

## Local setup

Editable install:

```bash
python -m pip install -e .
```

Dev extras (tests):

```bash
python -m pip install -e ".[dev]"
```

Optional LanceDB tests/backends:

```bash
python -m pip install -e ".[lancedb]"
```

## Run tests

```bash
python -m pytest -q
```

Notes:

- Most layer-2 suites run against both substrate stacks (in-memory and SQLite) via a parametrized fixture in [`tests/conftest.py`](../tests/conftest.py), which also bootstraps `sys.path` for monorepo layouts.
- LanceDB-dependent tests are skipped when `lancedb` is not installed (see [`tests/test_lancedb_triple_store.py`](../tests/test_lancedb_triple_store.py)).
- Integration tests marked `lmstudio` need a local OpenAI-compatible server with an embedding model and are skipped automatically when unreachable (see markers in [`pyproject.toml`](../pyproject.toml)).

## Design backlog

Design notes and planned work live under [`backlog/`](backlog/overview.md) (maintainer-facing). The user-facing documentation set is indexed in [`README.md`](README.md).
