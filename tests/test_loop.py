# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from agentic_rag.config import Settings
from agentic_rag.loop import (
    parse_json_object,
    run_agent,
    validate_final,
)
from agentic_rag.retrieval import RetrieverRegistry
from agentic_rag.tools import ToolRegistry


def _registry() -> ToolRegistry:
    settings = Settings(data_dir=Path("data"))
    return ToolRegistry(settings, RetrieverRegistry(settings))


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json_object('```json\n{"action":"final"}\n```') == {"action": "final"}
    assert parse_json_object('noise {"a": 1} tail') == {"a": 1}
    assert parse_json_object("not json") is None


def test_validate_final_requires_fields():
    ok, err = validate_final(
        {"answer": "42", "answerable": True, "citations": [], "missing": ""}
    )
    assert ok is not None and err == ""
    bad, err = validate_final({"answer": "", "answerable": True})
    assert bad is None and "answer" in err


def test_agent_loop_calls_tool_then_final():
    responses = iter([
        json.dumps({
            "thought": "需要计算",
            "action": "calculator",
            "action_input": {"expression": "24*0.925"},
        }),
        json.dumps({
            "thought": "已完成",
            "action": "final",
            "action_input": {
                "answer": "良品 22.2 片",
                "citations": ["calculator"],
                "answerable": True,
                "missing": "",
            },
        }),
    ])

    def fake_llm(messages):
        return next(responses)

    trace_dir = Path("runs-test")
    result = run_agent(
        "24 片 92.5% 良率", "dram", max_steps=3,
        llm=fake_llm, tools=_registry(),
        trace_dir=trace_dir, task_id="T1",
    )
    assert result.answer == "良品 22.2 片"
    assert result.called_tools == ["calculator"]
    assert len(result.steps) == 2
    assert result.trace_path
    assert Path(result.trace_path).exists()


def test_agent_stops_at_max_steps():
    def always_tool(messages):
        return json.dumps({
            "thought": "反复算",
            "action": "calculator",
            "action_input": {"expression": "1+1"},
        })

    result = run_agent(
        "loop", "dram", max_steps=2, llm=always_tool, tools=_registry()
    )
    assert result.answer == "达到最大步数，未能完成。"
    assert result.answerable is False
