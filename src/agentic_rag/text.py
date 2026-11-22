"""Text helpers shared by retrieval and evaluation."""
from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[A-Za-z0-9_./\-]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """Chinese characters as unigrams; Latin/number runs as words.

    This mirrors the RAG project's tokenizer: zero dependencies, deterministic,
    and good enough for alarm codes and short technical terms.
    """
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def normalize_for_match(text: str) -> str:
    """Remove all whitespace and lowercase, for deterministic answer checks."""
    return "".join(str(text or "").lower().split())
