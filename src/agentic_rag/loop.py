"""Bounded ReAct loop, RAG-only baseline, and trace persistence."""
from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from . import prompts as P
from .llm import ChatFn
from .retrieval import RetrieverRegistry
from .tools import ToolRegistry

DEFAULT_KB = "dram"


@dataclass
class Step:
    n: int
    thought: str
    action: str
    action_input: dict
    observation: str
    latency_s: float
    error: bool = False


@dataclass
class RunResult:
    task_id: str
    q: str
    kb: str
    mode: str
    answer: str = ""
    answerable: bool = False
    citations: list = field(default_factory=list)
    missing: str = ""
    called_tools: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    latency_s: float = 0.0
    error: str = ""
    trace_path: str = ""
    started_at: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "q": self.q,
            "kb": self.kb,
            "mode": self.mode,
            "answer": self.answer,
            "answerable": self.answerable,
            "citations": self.citations,
            "missing": self.missing,
            "called_tools": self.called_tools,
            "steps": [asdict(step) for step in self.steps],
            "latency_s": round(self.latency_s, 3),
            "error": self.error,
            "trace_path": self.trace_path,
            "started_at": self.started_at,
        }


def parse_json_object(raw: str) -> dict | None:
    """Extract the first JSON object, tolerating fences and extra prose."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def validate_final(args: dict) -> tuple[dict | None, str]:
    if not isinstance(args, dict):
        return None, "action_input 必须是 JSON 对象"
    answer = args.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return None, "final.answer 必须是非空字符串"
    answerable = args.get("answerable", True)
    if not isinstance(answerable, bool):
        return None, "final.answerable 必须是布尔值"
    citations = args.get("citations", [])
    if not isinstance(citations, list) or not all(
            isinstance(item, (str, int)) for item in citations):
        return None, "final.citations 必须是字符串/整数数组"
    missing = args.get("missing", "")
    if not isinstance(missing, str):
        return None, "final.missing 必须是字符串"
    return {
        "answer": answer.strip(),
        "answerable": answerable,
        "citations": [str(item) for item in citations],
        "missing": missing,
    }, ""


def run_agent(q: str, kb: str = DEFAULT_KB, max_steps: int = 6,
              llm: ChatFn | None = None, tools: ToolRegistry | None = None,
              trace_dir: Path | None = None, task_id: str = "adhoc",
              run_id: str = "1", quiet: bool = False) -> RunResult:
    if llm is None or tools is None:
        raise ValueError("run_agent requires llm and tools")
    started = time.time()
    result = RunResult(
        task_id=task_id, q=q, kb=kb, mode="agent",
        started_at=datetime.now().isoformat(timespec="seconds"),
    )
    messages = [
        {"role": "system",
         "content": P.agent_system(tools.catalog_text(), max_steps)},
        {"role": "user", "content": P.agent_user(q, kb)},
    ]
    seen: Counter = Counter()
    final: dict | None = None

    for n in range(1, max_steps + 1):
        t0 = time.time()
        try:
            raw = llm(messages)
        except Exception as exc:  # noqa: BLE001
            result.error = f"LLM 调用失败：{type(exc).__name__}: {exc}"
            result.answer = "模型调用失败，未完成。"
            result.missing = result.error
            break

        obj = parse_json_object(raw)
        if obj is None:
            obs = "ERROR: 你的输出不是合法 JSON。请只输出一个 JSON 对象，不要解释。"
            result.steps.append(Step(n, "", "<invalid_json>", {}, obs,
                                     time.time() - t0, True))
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Observation: {obs}"})
            continue

        thought = str(obj.get("thought", ""))[:500]
        action = str(obj.get("action", "")).strip()
        args = obj.get("action_input") or {}
        if not isinstance(args, dict):
            args = {}

        if action == "final":
            final, err = validate_final(args)
            result.steps.append(Step(n, thought, "final", args,
                                     "final" if final else f"ERROR: {err}",
                                     time.time() - t0, bool(err)))
            if final:
                break
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"Observation: ERROR: {err}\n请修正 final 的字段。",
            })
            continue

        if action not in tools.names:
            obs = f"ERROR: 未知 action {action!r}。可用：{', '.join(tools.names)}, final"
            result.steps.append(Step(n, thought, action, args, obs,
                                     time.time() - t0, True))
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Observation: {obs}"})
            continue

        key = (action, json.dumps(args, sort_keys=True, ensure_ascii=False))
        if seen[key] >= 2:
            obs = ("ERROR: 相同工具和相同参数已经调用过两次，"
                   "不要重复；请换参数/换工具，或直接 final。")
            error = True
        else:
            try:
                obs = tools.call(action, args)
                error = False
            except Exception as exc:  # noqa: BLE001
                obs = f"ERROR: {type(exc).__name__}: {exc}"
                error = True
        seen[key] += 1
        result.called_tools.append(action)
        result.steps.append(Step(n, thought, action, args, obs[:4000],
                                 time.time() - t0, error))
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user",
                         "content": "Observation:\n" + obs[:4000]})

    if final is None:
        final = {
            "answer": "达到最大步数，未能完成。",
            "answerable": False,
            "citations": [],
            "missing": f"未在 {max_steps} 步内完成",
        }
    result.answer = final["answer"]
    result.answerable = final["answerable"]
    result.citations = final["citations"]
    result.missing = final["missing"]
    result.latency_s = time.time() - started
    if trace_dir is not None:
        result.trace_path = save_trace(result, trace_dir, run_id)
    return result


def run_baseline(q: str, kb: str = DEFAULT_KB, top_k: int = 3,
                 llm: ChatFn | None = None,
                 retrievers: RetrieverRegistry | None = None,
                 trace_dir: Path | None = None, task_id: str = "adhoc",
                 run_id: str = "1") -> RunResult:
    if llm is None or retrievers is None:
        raise ValueError("run_baseline requires llm and retrievers")
    started = time.time()
    result = RunResult(
        task_id=task_id, q=q, kb=kb, mode="rag",
        started_at=datetime.now().isoformat(timespec="seconds"),
    )
    t0 = time.time()
    try:
        retriever = retrievers.get(kb)
        hits = retriever.search(q, top_k=top_k, mode="hybrid", rerank="max",
                                rerank_pool=40, alpha=0.7)
        lines = []
        for n, (idx, _score) in enumerate(hits, start=1):
            chunk = retriever.chunks[idx]
            lines.append(f"[{n}] 来源：{chunk['doc']} / {chunk['cid']}\n{chunk['text']}")
        context = "<context>\n" + "\n\n".join(lines) + "\n</context>"
        result.steps.append(Step(1, "检索 Top-3 后一次生成", "search_kb",
                                 {"query": q, "kb": kb}, context[:4000],
                                 time.time() - t0))
        raw = llm(P.baseline_messages(q, context))
    except Exception as exc:  # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
        result.answer = "基线检索/生成失败，未完成。"
        result.missing = result.error
        result.latency_s = time.time() - started
        if trace_dir is not None:
            result.trace_path = save_trace(result, trace_dir, run_id)
        return result

    obj = parse_json_object(raw)
    if obj is None:
        result.error = "基线输出不是合法 JSON"
        result.answer = "结构化输出失败，未完成。"
        result.missing = result.error
    else:
        result.answer = str(obj.get("answer", "")) or "（空答案）"
        result.answerable = bool(obj.get("answerable", False))
        citations = obj.get("citations", [])
        result.citations = [str(x) for x in citations] if isinstance(citations, list) else []
        result.missing = str(obj.get("missing", ""))
    result.latency_s = time.time() - started
    if trace_dir is not None:
        result.trace_path = save_trace(result, trace_dir, run_id)
    return result


def save_trace(result: RunResult, trace_dir: Path, run_id: str = "1") -> str:
    path = trace_dir / result.mode / result.task_id / f"run-{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return str(path)
