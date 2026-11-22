from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_rag.config import Settings
from agentic_rag.retrieval import RetrieverRegistry
from agentic_rag.tools import ToolError, ToolRegistry, calculator


@pytest.fixture()
def registry() -> ToolRegistry:
    settings = Settings(data_dir=Path("data"))
    return ToolRegistry(settings, RetrieverRegistry(settings))


def test_calculator_supports_arithmetic():
    assert json.loads(calculator("24*0.925"))["result"] == 22.2
    assert json.loads(calculator("45*24/60"))["result"] == 18.0


@pytest.mark.parametrize("expr", ["__import__('os')", "open('x')", "1/0", "2**99"])
def test_calculator_rejects_unsafe_or_invalid(expr: str):
    with pytest.raises(ToolError):
        calculator(expr)


def test_lookup_ticket_found_and_missing(registry: ToolRegistry):
    found = json.loads(registry.lookup_ticket("T-1001"))
    assert found["found"] is True
    assert found["status"] == "open"

    missing = json.loads(registry.lookup_ticket("T-9999"))
    assert missing["found"] is False
    assert "未找到" in missing["message"]


def test_tool_registry_validates_required_args(registry: ToolRegistry):
    with pytest.raises(ToolError):
        registry.call("calculator", {})
    with pytest.raises(ToolError):
        registry.call("lookup_ticket", {"ticket_id": 123})
    with pytest.raises(ToolError):
        registry.call("unknown", {})


def test_tool_catalog_has_three_tools(registry: ToolRegistry):
    names = [tool["name"] for tool in registry.specs()]
    assert names == ["search_kb", "lookup_ticket", "calculator"]
    assert "search_kb" in registry.catalog_text()
