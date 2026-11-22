from __future__ import annotations

from agentic_rag.retrieval import BM25, rrf
from agentic_rag.text import normalize_for_match, tokenize


def test_tokenize_keeps_codes_and_chinese():
    tokens = tokenize("ALM-1042 报警，24*0.925")
    assert "alm-1042" in tokens
    assert "报" in tokens
    assert "24" in tokens


def test_normalize_removes_spaces():
    assert normalize_for_match("连续 8 点") == normalize_for_match("连续8点")


def test_bm25_prefers_matching_document():
    corpus = [
        tokenize("ALM-1042 腔体压力异常"),
        tokenize("SPC 控制图判异规则"),
    ]
    scores = BM25(corpus).scores("ALM-1042")
    assert scores[0] > scores[1]


def test_rrf_rewards_consensus():
    fused = rrf([[0, 1, 2], [0, 1, 2]], k=60)
    assert fused[0] > fused[1] > fused[2]
