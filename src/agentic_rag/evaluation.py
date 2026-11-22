"""Deterministic evaluation harness: answer checks + trajectory checks."""
from __future__ import annotations

import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from .config import Settings
from .llm import ChatFn
from .loop import DEFAULT_KB, RunResult, run_agent, run_baseline
from .retrieval import RetrieverRegistry
from .text import normalize_for_match
from .tools import ToolRegistry


def load_tasks(path: Path) -> list[dict]:
    tasks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tasks.append(json.loads(line))
    return tasks


def score_answer(result: RunResult, task: dict) -> tuple[bool, list[str]]:
    text = normalize_for_match(result.answer)
    missing = [
        str(key) for key in task.get("must_include", [])
        if normalize_for_match(str(key)) not in text
    ]
    for group in task.get("must_include_any", []):
        if not any(normalize_for_match(str(alt)) in text for alt in group):
            missing.append("/".join(str(item) for item in group))
    bad = [
        str(key) for key in task.get("must_not_include", [])
        if normalize_for_match(str(key)) in text
    ]
    if not task.get("answerable", True):
        ok = (result.answerable is False) and not bad
    else:
        ok = not missing and not bad
    return ok, missing + [f"!{item}" for item in bad]


def score_tools(result: RunResult, task: dict) -> tuple[bool, list[str]]:
    expected = set(task.get("expected_tools", []))
    forbidden = set(task.get("forbidden_tools", []))
    called = set(result.called_tools)
    problems = []
    if not expected.issubset(called):
        problems.append("缺少 " + ",".join(sorted(expected - called)))
    if forbidden & called:
        problems.append("不该调用 " + ",".join(sorted(forbidden & called)))
    return not problems, problems


def evaluate(tasks: list[dict], mode: str, *, llm: ChatFn,
             retrievers: RetrieverRegistry, tools: ToolRegistry,
             settings: Settings, runs: int = 1,
             trace_dir: Path | None = None, quiet: bool = False,
             delay_s: float = 0.0) -> dict:
    started = datetime.now().isoformat(timespec="seconds")
    task_rows = []
    all_latencies = []
    for ti, task in enumerate(tasks, start=1):
        runs_rows = []
        for ri in range(1, runs + 1):
            if mode == "agent":
                result = run_agent(
                    task["q"], task.get("kb", DEFAULT_KB),
                    max_steps=int(task.get("max_steps", settings.max_steps)),
                    llm=llm, tools=tools, trace_dir=trace_dir,
                    task_id=task["id"], run_id=str(ri), quiet=quiet,
                )
            else:
                result = run_baseline(
                    task["q"], task.get("kb", DEFAULT_KB),
                    llm=llm, retrievers=retrievers, trace_dir=trace_dir,
                    task_id=task["id"], run_id=str(ri),
                )
            answer_ok, answer_problems = score_answer(result, task)
            if mode == "agent":
                tool_ok, tool_problems = score_tools(result, task)
            else:
                tool_ok, tool_problems = True, []
            success = answer_ok and tool_ok
            all_latencies.append(result.latency_s)
            runs_rows.append({
                "run": ri,
                "success": success,
                "answer_ok": answer_ok,
                "tool_ok": tool_ok,
                "answer_problems": answer_problems,
                "tool_problems": tool_problems,
                "answer": result.answer,
                "answerable": result.answerable,
                "called_tools": result.called_tools,
                "steps": len(result.steps),
                "latency_s": round(result.latency_s, 2),
                "error": result.error,
                "trace": result.trace_path,
            })
            if delay_s > 0:
                time.sleep(delay_s)
        task_success = all(row["success"] for row in runs_rows)
        task_rows.append({
            "id": task["id"],
            "q": task["q"],
            "kb": task.get("kb", DEFAULT_KB),
            "answerable": task.get("answerable", True),
            "expected_tools": task.get("expected_tools", []),
            "runs": runs_rows,
            "passk": task_success,
            "first": runs_rows[0],
        })
        if not quiet:
            mark = "OK" if task_success else "FAIL"
            print(
                f"[{ti:02d}/{len(tasks)}] {mark:<4} {task['id']:<5} "
                f"answer={runs_rows[0]['answer_ok']} "
                f"tool={runs_rows[0]['tool_ok']} "
                f"steps={runs_rows[0]['steps']} "
                f"{runs_rows[0]['latency_s']}s"
            )

    n = len(task_rows)
    firsts = [row["first"] for row in task_rows]
    answer_rate = sum(1 for row in firsts if row["answer_ok"]) / n if n else 0
    success_rate = sum(1 for row in firsts if row["success"]) / n if n else 0
    tool_rate = (
        sum(1 for row in firsts if row["tool_ok"]) / n
        if mode == "agent" and n else None
    )
    passk_rate = sum(1 for row in task_rows if row["passk"]) / n if n else 0
    latencies = sorted(all_latencies)
    p95 = (
        latencies[min(len(latencies) - 1,
                      int(round(0.95 * (len(latencies) - 1))))]
        if latencies else 0
    )
    summary = {
        "mode": mode,
        "runs": runs,
        "n_tasks": n,
        "answer_rate": round(answer_rate, 4),
        "task_success_rate": round(success_rate, 4),
        "tool_selection_rate": round(tool_rate, 4) if tool_rate is not None else None,
        "passk_rate": round(passk_rate, 4),
        "avg_steps": round(statistics.mean([row["steps"] for row in firsts]), 2) if n else 0,
        "avg_latency_s": round(statistics.mean(all_latencies), 2) if latencies else 0,
        "p95_latency_s": round(p95, 2),
        "errors": sum(1 for row in firsts if row["error"]),
    }
    return {
        "started_at": started,
        "model": settings.llm_model,
        "embed_model": settings.emb_model,
        "summary": summary,
        "tasks": task_rows,
    }


def write_report_md(report: dict, path: Path) -> None:
    summary = report["summary"]
    lines = [
        "# Agentic RAG Evaluation Report",
        "",
        f"- started_at: {report['started_at']}",
        f"- model: {report['model']} | embedding: {report['embed_model']}",
        f"- mode: {summary['mode']} | runs: {summary['runs']} | tasks: {summary['n_tasks']}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Answer accuracy | {summary['answer_rate']:.2%} |",
        f"| Task success (answer + tools) | {summary['task_success_rate']:.2%} |",
    ]
    if summary["tool_selection_rate"] is not None:
        lines.append(f"| Tool selection | {summary['tool_selection_rate']:.2%} |")
    lines += [
        f"| pass^{summary['runs']} | {summary['passk_rate']:.2%} |",
        f"| Avg steps | {summary['avg_steps']} |",
        f"| Avg latency | {summary['avg_latency_s']}s |",
        f"| P95 latency | {summary['p95_latency_s']}s |",
        f"| Errors | {summary['errors']} |",
        "",
        "## Per task",
        "",
        "| ID | Question | Answer | Tool | Success | Steps | Latency | Tools called |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["tasks"]:
        first = row["first"]
        question = row["q"].replace("|", "\\|")[:38]
        answer = first["answer"].replace("\n", " ").replace("|", "\\|")[:42]
        tools = ", ".join(first["called_tools"]) or "-"
        lines.append(
            f"| {row['id']} | {question} | {answer} | "
            f"{'✓' if first['answer_ok'] else '✗'} | "
            f"{'✓' if first['success'] else '✗'} | {first['steps']} | "
            f"{first['latency_s']}s | {tools} |"
        )
    lines += ["", "## Failures", ""]
    failed = [row for row in report["tasks"] if not row["passk"]]
    if not failed:
        lines.append("None.")
    else:
        for row in failed:
            first = row["first"]
            lines.append(f"### {row['id']}  {row['q']}")
            lines.append(
                f"- answer_ok={first['answer_ok']}, tool_ok={first['tool_ok']}, "
                f"steps={first['steps']}, error={first['error'] or '-'}"
            )
            lines.append(f"- tools: {first['called_tools'] or '-'}")
            lines.append(f"- answer: {first['answer'][:300]}")
            lines.append(f"- missing keywords: {first['answer_problems'] or '-'}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_comparison_md(reports: dict, path: Path) -> None:
    lines = [
        "# RAG-only vs Agent",
        "",
        "| Mode | Task success | Answer | Tools | Avg steps | Avg latency | P95 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for mode in ("rag", "agent"):
        if mode not in reports:
            continue
        summary = reports[mode]["summary"]
        tool = summary["tool_selection_rate"]
        tool_text = "-" if tool is None else f"{tool:.2%}"
        lines.append(
            f"| {mode} | {summary['task_success_rate']:.2%} | "
            f"{summary['answer_rate']:.2%} | {tool_text} | "
            f"{summary['avg_steps']} | {summary['avg_latency_s']}s | "
            f"{summary['p95_latency_s']}s |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
