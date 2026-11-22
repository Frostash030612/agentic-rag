# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentic_rag.api import create_app
from agentic_rag.config import Settings
from agentic_rag.loop import RunResult, Step


@pytest.fixture()
def data_dir() -> Path:
    # tests run from the repository root (AgenticRAG/)
    return Path("data")


@pytest.fixture()
def settings(data_dir: Path) -> Settings:
    return Settings(
        data_dir=data_dir,
        runs_dir=Path("runs-test"),
        api_keys=("test-key",),
        rate_limit_per_minute=100,
        max_steps=4,
        environment="test",
    )


@pytest.fixture()
def fake_result() -> RunResult:
    return RunResult(
        task_id="trace-1",
        q="test?",
        kb="dram",
        mode="agent",
        answer="42",
        answerable=True,
        citations=["doc#0"],
        steps=[Step(1, "", "calculator", {"expression": "42"}, "42", 0.01)],
        latency_s=0.02,
    )


@pytest.fixture()
def client(settings: Settings, fake_result: RunResult) -> TestClient:
    def runner(q: str, kb: str, max_steps: int, trace_id: str) -> RunResult:
        fake_result.task_id = trace_id
        return fake_result

    app = create_app(settings, agent_runner=runner)
    with TestClient(app) as test_client:
        yield test_client
