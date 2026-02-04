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
- LanceDB-dependent tests are skipped when `lancedb` is not installed. See [`tests/test_lancedb_triple_store.py`](../tests/test_lancedb_triple_store.py).
- The test suite bootstraps `sys.path` for monorepo layouts (see [`tests/conftest.py`](../tests/conftest.py)).
