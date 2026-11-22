"""Embedding client and offline hash baseline.

The bundled indexes were built with BAAI/bge-m3 (1024-d). If you change
EMB_MODEL you must rebuild the index; the service refuses to mix vector spaces.
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable

import httpx
import numpy as np

from .config import Settings
from .text import tokenize


class EmbeddingError(RuntimeError):
    pass


def hash_embed(texts: Iterable[str], dim: int = 512) -> np.ndarray:
    """Offline bag-of-tokens baseline, used only for smoke tests."""
    texts = list(texts)
    mat = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        for tok in tokenize(text):
            h = int(hashlib.md5(tok.encode()).hexdigest()[:8], 16)
            mat[i, h % dim] += 1.0
    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
    return mat / norms


class EmbeddingClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if not settings.llm_api_key:
            raise EmbeddingError(
                "LLM_API_KEY is empty; set it in .env or the environment"
            )
        self.settings = settings
        self._client = client or httpx.Client(timeout=settings.request_timeout_s)

    @property
    def url(self) -> str:
        return f"{self.settings.llm_base_url}/embeddings"

    def embed(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        out: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            out.extend(self._embed_batch(batch))
        arr = np.asarray(out, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
        return arr / norms

    def _embed_batch(self, batch: list[str], retries: int = 3) -> list[list[float]]:
        last: Exception | None = None
        for attempt in range(retries):
            try:
                resp = self._client.post(
                    self.url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.settings.llm_api_key}",
                    },
                    json={"model": self.settings.emb_model, "input": batch},
                )
                if resp.status_code >= 400:
                    raise EmbeddingError(
                        f"embedding HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                data = resp.json()["data"]
                if data and isinstance(data[0], dict):
                    items = sorted(data, key=lambda item: item["index"])
                    return [item["embedding"] for item in items]
                return [list(map(float, row)) for row in data]
            except Exception as exc:  # noqa: BLE001
                last = exc
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        raise EmbeddingError(f"embedding failed after {retries} attempts: {last}")

    def close(self) -> None:
        self._client.close()
