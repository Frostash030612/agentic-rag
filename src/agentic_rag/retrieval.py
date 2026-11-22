"""Local hybrid retrieval: BM25 + dense vectors + RRF/weighted fusion.

This is a compact, dependency-light port of the retrieval layer used in the
original RAG project. It keeps the same formulas so the bundled index and the
published evaluation numbers remain comparable.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from .config import Settings
from .embeddings import EmbeddingClient, EmbeddingError, hash_embed
from .text import tokenize

RERANK_MODES = ("rrf", "max", "minmax", "lex")


class BM25:
    """Okapi BM25 with the same parameters as the RAG project (k1=1.5, b=0.75)."""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5,
                 b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = corpus_tokens
        self.n = len(corpus_tokens)
        self.avgdl = sum(len(d) for d in corpus_tokens) / max(self.n, 1)
        self.tf = [Counter(d) for d in corpus_tokens]
        df = Counter()
        for d in corpus_tokens:
            df.update(set(d))
        self.idf = {
            t: math.log(1 + (self.n - c + 0.5) / (c + 0.5))
            for t, c in df.items()
        }

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(self.n, dtype=np.float32)
        for token in tokenize(query):
            if token not in self.idf:
                continue
            idf = self.idf[token]
            for i, tf in enumerate(self.tf):
                freq = tf.get(token)
                if not freq:
                    continue
                dl = len(self.docs[i])
                denom = freq + self.k1 * (
                    1 - self.b + self.b * dl / self.avgdl
                )
                out[i] += idf * (freq * (self.k1 + 1)) / denom
        return out


def rrf(rank_lists: list[list[int]], k: int = 60) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranks in rank_lists:
        for pos, idx in enumerate(ranks, start=1):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + pos)
    return fused


def fuse_scores(vs: np.ndarray, bs: np.ndarray, cand: list[int],
                mode: str = "rrf", alpha: float = 0.5, rrf_k: int = 60,
                query: str = "", chunks: list[dict] | None = None,
                lex_w: float = 0.15) -> dict[int, float]:
    if mode == "rrf":
        cand_set = set(cand)
        v_rank = [i for i in np.argsort(-vs) if i in cand_set]
        b_rank = [i for i in np.argsort(-bs) if i in cand_set]
        fused = rrf([v_rank, b_rank], k=rrf_k)
        top = max(fused.values()) if fused else 1.0
        return {i: fused.get(i, 0.0) / top for i in cand}

    cv, cb = vs[cand], bs[cand]

    def norm(x: np.ndarray, how: str) -> np.ndarray:
        if how == "max":
            m = float(np.max(x)) if len(x) else 0.0
            return x / m if m > 0 else np.zeros_like(x)
        lo, hi = float(np.min(x)), float(np.max(x))
        if hi - lo < 1e-12:
            return np.ones_like(x)
        return (x - lo) / (hi - lo)

    how = "minmax" if mode == "minmax" else "max"
    score = alpha * norm(cv, how) + (1 - alpha) * norm(cb, how)
    if mode == "lex" and query and chunks:
        q_tokens = set(tokenize(query))
        if q_tokens:
            cov = np.array([
                len(q_tokens & set(tokenize(chunks[i]["text"]))) / len(q_tokens)
                for i in cand
            ], dtype=np.float32)
            score = score + lex_w * cov
    return {i: float(score[j]) for j, i in enumerate(cand)}


class Retriever:
    def __init__(self, index_dir: Path, settings: Settings,
                 embedder: EmbeddingClient | None = None):
        self.index_dir = index_dir
        self.settings = settings
        self.chunks = json.loads(
            (index_dir / "chunks.json").read_text(encoding="utf-8")
        )
        self.vectors = np.load(index_dir / "vectors.npy", allow_pickle=False)
        self.meta = json.loads(
            (index_dir / "meta.json").read_text(encoding="utf-8")
        )
        if len(self.chunks) != self.vectors.shape[0]:
            raise ValueError(
                f"index mismatch: {len(self.chunks)} chunks vs "
                f"{self.vectors.shape[0]} vectors in {index_dir}"
            )
        self.bm25 = BM25([tokenize(c["text"]) for c in self.chunks])
        self._embedder = embedder

    def _vec_scores(self, query: str) -> np.ndarray:
        if self.meta.get("embed_model") == "hash-512":
            qv = hash_embed([query])[0]
        else:
            if self._embedder is None:
                raise EmbeddingError(
                    "this index needs an embedding client; set LLM_API_KEY"
                )
            qv = self._embedder.embed([query])[0]
        return self.vectors @ qv

    def candidates(self, query: str, pool: int = 10
                   ) -> tuple[list[int], np.ndarray, np.ndarray]:
        vs = self._vec_scores(query)
        bs = self.bm25.scores(query)
        v_top = set(int(i) for i in np.argsort(-vs)[:pool])
        b_top = set(int(i) for i in np.argsort(-bs)[:pool])
        return sorted(v_top | b_top), vs, bs

    def search(self, query: str, top_k: int = 5, mode: str = "hybrid",
               pool: int = 30, rerank: str | None = None,
               rerank_pool: int = 10, alpha: float = 0.5,
               lex_w: float = 0.15) -> list[tuple[int, float]]:
        vs = self._vec_scores(query)
        bs = self.bm25.scores(query)
        if mode == "vector":
            return [(int(i), float(vs[i]))
                    for i in np.argsort(-vs)[:top_k]]
        if mode == "bm25":
            return [(int(i), float(bs[i]))
                    for i in np.argsort(-bs)[:top_k]]

        if rerank:
            cand, _, _ = self.candidates(query, pool=rerank_pool)
            fused = fuse_scores(vs, bs, cand, mode=rerank, alpha=alpha,
                                query=query, chunks=self.chunks, lex_w=lex_w)
            return [(int(i), float(s))
                    for i, s in sorted(fused.items(), key=lambda x: -x[1])[:top_k]]

        v_rank = list(np.argsort(-vs)[:pool])
        b_rank = list(np.argsort(-bs)[:pool])
        fused = rrf([v_rank, b_rank])
        return [(int(i), float(s))
                for i, s in sorted(fused.items(), key=lambda x: -x[1])[:top_k]]


class RetrieverRegistry:
    """Lazy per-KB retriever cache. A process loads a corpus only on first use."""

    def __init__(self, settings: Settings, embedder: EmbeddingClient | None = None):
        self.settings = settings
        self._embedder = embedder
        self._cache: dict[str, Retriever] = {}

    @property
    def embedder(self) -> EmbeddingClient | None:
        return self._embedder

    def set_embedder(self, embedder: EmbeddingClient | None) -> None:
        self._embedder = embedder
        self._cache.clear()

    def kbs(self) -> list[str]:
        return self.settings.kb_ids()

    def get(self, kb: str) -> Retriever:
        if kb not in self.kbs():
            raise KeyError(f"unknown knowledge base: {kb}")
        if kb not in self._cache:
            index_dir = self.settings.kb_dir / kb / "index"
            self._cache[kb] = Retriever(
                index_dir, self.settings, self._embedder
            )
        return self._cache[kb]

    def clear(self) -> None:
        self._cache.clear()
