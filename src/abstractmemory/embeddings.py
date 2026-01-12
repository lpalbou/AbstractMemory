from __future__ import annotations

import json
from typing import List, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TextEmbedder(Protocol):
    """Minimal text embedding interface used by AbstractMemory stores."""

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]: ...


class AbstractGatewayTextEmbedder:
    """Text embedder that calls AbstractGateway's embeddings API.

    AbstractMemory intentionally does not depend on AbstractCore directly. The gateway is responsible for:
    - selecting the embedding provider/model (singleton per gateway instance)
    - generating embeddings via AbstractRuntime+AbstractCore integration
    - enforcing a stable embedding space
    """

    def __init__(
        self,
        *,
        base_url: str,
        auth_token: str | None = None,
        endpoint_path: str = "/api/gateway/embeddings",
        timeout_s: float = 30.0,
    ) -> None:
        root = str(base_url or "").strip().rstrip("/")
        if not root:
            raise ValueError("base_url is required")
        path = str(endpoint_path or "").strip()
        if not path.startswith("/"):
            path = "/" + path
        self._url = root + path
        self._timeout_s = float(timeout_s)
        self._headers = {"Content-Type": "application/json"}
        if isinstance(auth_token, str) and auth_token.strip():
            self._headers["Authorization"] = f"Bearer {auth_token.strip()}"

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        items = [str(t or "") for t in texts]
        payload = {"input": items}
        req = Request(
            self._url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=dict(self._headers),
            method="POST",
        )
        try:
            with urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                detail = ""
            raise RuntimeError(f"Gateway embeddings HTTP {e.code}: {detail or e.reason}") from e
        except URLError as e:
            raise RuntimeError(f"Gateway embeddings request failed: {e}") from e

        try:
            data = json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"Gateway embeddings returned invalid JSON: {e}") from e

        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError("Gateway embeddings response missing 'data' list")

        # Preserve order via `index` when present.
        parsed: list[tuple[int, List[float]]] = []
        for i, row_any in enumerate(rows):
            row = row_any if isinstance(row_any, dict) else {}
            idx = row.get("index")
            try:
                index = int(idx) if idx is not None else i
            except Exception:
                index = i
            emb = row.get("embedding")
            if not isinstance(emb, list):
                raise RuntimeError("Gateway embeddings response contains non-list embedding")
            parsed.append((index, [float(x) for x in emb]))

        parsed.sort(key=lambda t: t[0])
        return [v for _, v in parsed]
