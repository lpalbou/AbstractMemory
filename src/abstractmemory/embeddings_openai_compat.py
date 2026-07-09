"""OpenAI-compatible text embedder (LMStudio, Ollama, vLLM, OpenAI, ...).

Sibling of `embeddings.AbstractGatewayTextEmbedder`: same stdlib-urllib HTTP
style, same order-preserving OpenAI response parsing, but pointed at any
server that speaks the OpenAI `/v1/embeddings` shape and takes an explicit
`model` id. AbstractMemory stays dependency-free: no openai SDK, no requests.

Typical local use (LMStudio):

    embedder = OpenAICompatTextEmbedder(
        "http://127.0.0.1:1234/v1", "text-embedding-qwen3-embedding-0.6b"
    )
    store = InMemoryTripleStore(embedder=embedder)
    system = MemorySystem(store=store, journal=journal, embedder=embedder)

Contract notes:
- Requests are chunked into `batch_size` inputs per POST so large
  `remember_many` batches cannot exceed server request limits.
- Output order matches input order across chunks (OpenAI `index` field is
  honored within each chunk; chunks are concatenated in request order).
- Errors are actionable: they name the server URL and model so a dead or
  misconfigured local server reads as exactly that, not a stack trace.
"""

from __future__ import annotations

import json
from typing import List, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

__all__ = ["OpenAICompatTextEmbedder"]


class OpenAICompatTextEmbedder:
    """Text embedder for OpenAI-compatible `/embeddings` endpoints.

    base_url is the API root INCLUDING the version prefix when the server
    uses one (e.g. "http://127.0.0.1:1234/v1"); the endpoint path
    "/embeddings" is appended. `model` is the server-side embedding model id
    (OpenAI-compatible servers require it explicitly).
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        timeout_s: float = 30.0,
        batch_size: int = 64,
    ) -> None:
        root = str(base_url or "").strip().rstrip("/")
        if not root:
            raise ValueError("base_url is required (e.g. http://127.0.0.1:1234/v1)")
        model_id = str(model or "").strip()
        if not model_id:
            raise ValueError(
                "model is required: OpenAI-compatible servers embed with an explicit "
                "model id (e.g. 'text-embedding-qwen3-embedding-0.6b' on LMStudio)"
            )
        size = int(batch_size)
        if size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size!r}")
        self._url = root + "/embeddings"
        self._model = model_id
        self._timeout_s = float(timeout_s)
        self._batch_size = size
        self._headers = {"Content-Type": "application/json"}
        if isinstance(api_key, str) and api_key.strip():
            self._headers["Authorization"] = f"Bearer {api_key.strip()}"

    @property
    def model(self) -> str:
        return self._model

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        items = [str(t or "") for t in texts]
        if not items:
            return []
        out: List[List[float]] = []
        for start in range(0, len(items), self._batch_size):
            out.extend(self._embed_chunk(items[start : start + self._batch_size]))
        return out

    def _embed_chunk(self, chunk: List[str]) -> List[List[float]]:
        payload = {"model": self._model, "input": chunk}
        req = Request(
            self._url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=dict(self._headers),
            method="POST",
        )
        where = f"{self._url} (model {self._model!r})"
        try:
            with urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as e:
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                detail = ""
            raise RuntimeError(
                f"Embeddings server HTTP {e.code} at {where}: {detail or e.reason} "
                "(verify the server is serving this embedding model id)"
            ) from e
        except URLError as e:
            raise RuntimeError(
                f"Embeddings server unreachable at {where}: {e.reason} "
                "(is the OpenAI-compatible server, e.g. LMStudio, running?)"
            ) from e

        try:
            data = json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"Embeddings server at {where} returned invalid JSON: {e}") from e

        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError(f"Embeddings response from {where} missing 'data' list")
        if len(rows) != len(chunk):
            raise RuntimeError(
                f"Embeddings response from {where} returned {len(rows)} rows for "
                f"{len(chunk)} inputs — cannot align results to texts"
            )

        # Preserve input order via `index` when present (OpenAI contract).
        parsed: list[tuple[int, List[float]]] = []
        for i, row_any in enumerate(rows):
            row = row_any if isinstance(row_any, dict) else {}
            idx = row.get("index")
            try:
                index = int(idx) if idx is not None else i
            except Exception:
                index = i
            emb = row.get("embedding")
            if not isinstance(emb, list) or not emb:
                raise RuntimeError(f"Embeddings response from {where} contains a non-list or empty embedding")
            parsed.append((index, [float(x) for x in emb]))

        parsed.sort(key=lambda t: t[0])
        return [v for _, v in parsed]
