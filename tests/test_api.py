from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agentic_rag.api import create_app
from agentic_rag.config import Settings
from agentic_rag.loop import RunResult


def _fake_runner():
    def runner(q: str, kb: str, max_steps: int, trace_id: str) -> RunResult:
        return RunResult(
            task_id=trace_id, q=q, kb=kb, mode="agent",
            answer="ok", answerable=True, citations=["doc#0"],
            latency_s=0.01,
        )
    return runner


def test_health_does_not_require_auth(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_endpoint_rejects_missing_key(client: TestClient):
    response = client.get("/v1/tools")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "ApiKey"


def test_tools_returns_catalog(client: TestClient):
    response = client.get("/v1/tools", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    names = [tool["name"] for tool in response.json()]
    assert names == ["search_kb", "lookup_ticket", "calculator"]


def test_ask_returns_answer_and_trace_id(client: TestClient):
    response = client.post(
        "/v1/ask",
        headers={"X-API-Key": "test-key"},
        json={"q": "T-1001 状态？", "kb": "dram", "max_steps": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "42"
    assert body["trace_id"]
    assert response.headers["X-Request-ID"]


def test_ask_rejects_unknown_kb(client: TestClient):
    response = client.post(
        "/v1/ask",
        headers={"X-API-Key": "test-key"},
        json={"q": "x", "kb": "nope"},
    )
    assert response.status_code == 400


def test_missing_api_keys_fails_closed():
    settings = Settings(
        data_dir=Path("data"), api_keys=(), allow_anonymous=False,
    )
    app = create_app(settings, agent_runner=_fake_runner())
    with TestClient(app) as client:
        response = client.get("/v1/tools")
        assert response.status_code == 503


def test_rate_limit_returns_429():
    settings = Settings(
        data_dir=Path("data"),
        api_keys=("k",),
        rate_limit_per_minute=1,
    )
    app = create_app(settings, agent_runner=_fake_runner())
    with TestClient(app) as client:
        assert client.get("/v1/tools", headers={"X-API-Key": "k"}).status_code == 200
        limited = client.get("/v1/tools", headers={"X-API-Key": "k"})
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers
