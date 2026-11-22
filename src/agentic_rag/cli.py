"""Command line entry point: ask / eval / demo / serve."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .config import Settings
from .evaluation import (
    evaluate,
    load_tasks,
    write_comparison_md,
    write_report_md,
)
from .loop import DEFAULT_KB, run_baseline
from .runtime import Runtime

DEMO_QUERIES = [
    ("dram", "ALM-1042 报警的触发条件和处理步骤是什么？"),
    ("dram", "T-1001 涉及的报警应该怎么处理？"),
    ("dram", "某批次 24 片，良率 92.5%，良品多少片？"),
]


def _print_result(result, show_trace: bool = True) -> None:
    if show_trace:
        for step in result.steps:
            print(f"[{step.n}] {step.action} "
                  f"{json.dumps(step.action_input, ensure_ascii=False)[:160]}")
            print(f"    -> {step.observation[:400].replace(chr(10), ' ')}")
    print("\n" + "=" * 60)
    print(f"answerable={result.answerable}  citations={result.citations}")
    print(result.answer)
    if result.missing:
        print(f"missing: {result.missing}")
    print(
        f"steps={len(result.steps)} latency={result.latency_s:.2f}s "
        f"tools={result.called_tools}"
    )
    if result.trace_path:
        print(f"trace={result.trace_path}")


def _runtime(settings: Settings) -> Runtime:
    runtime = Runtime(settings)
    problems = settings.validate()
    if problems:
        raise SystemExit("配置/数据有问题：\n- " + "\n- ".join(problems))
    if runtime.llm is None:
        raise SystemExit(
            "缺少 LLM 配置：请在 .env 里设置 LLM_API_KEY（以及 LLM_BASE_URL/LLM_MODEL）"
        )
    return runtime


def cmd_ask(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    runtime = _runtime(settings)
    try:
        if args.mode == "agent":
            result = runtime.run(
                args.q, args.kb, max_steps=args.max_steps,
                trace_id=args.trace_id or "adhoc",
            )
        else:
            if runtime.llm is None:
                raise SystemExit("RAG baseline 需要 LLM 配置")
            result = run_baseline(
                args.q, args.kb, llm=runtime.llm.chat,
                retrievers=runtime.retrievers,
                trace_dir=settings.runs_dir,
                task_id=args.trace_id or "adhoc",
            )
        _print_result(result, show_trace=args.show_trace or args.mode == "agent")
        return 0
    finally:
        runtime.close()


def cmd_eval(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    runtime = _runtime(settings)
    tasks_file = Path(args.tasks)
    if not tasks_file.exists():
        raise SystemExit(f"任务文件不存在：{tasks_file}")
    tasks = load_tasks(tasks_file)
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        tasks = [task for task in tasks if task["id"] in wanted]
    if args.limit:
        tasks = tasks[:args.limit]
    if not tasks:
        raise SystemExit("没有任务可跑（检查 --only/--limit）")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    trace_dir = Path(args.trace_dir)
    modes = ["rag", "agent"] if args.mode == "both" else [args.mode]
    reports = {}
    try:
        for mode in modes:
            print(f"\n=== eval {mode} | {len(tasks)} tasks | {args.runs} runs ===")
            reports[mode] = evaluate(
                tasks, mode, llm=runtime.llm.chat,
                retrievers=runtime.retrievers, tools=runtime.tools,
                settings=settings, runs=args.runs,
                trace_dir=trace_dir, quiet=args.quiet,
                delay_s=args.delay,
            )
            write_report_md(
                reports[mode], out.with_name(f"{mode}_report.md")
            )
    finally:
        runtime.close()

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tasks_file": str(tasks_file),
        "reports": reports,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    if len(reports) == 2:
        write_comparison_md(reports, out.with_name("comparison.md"))
    print(f"\n[report] {out}")
    print(json.dumps({mode: report["summary"]
                      for mode, report in reports.items()},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    demos_dir = Path(args.data_dir) / "demo_traces"
    if not args.live:
        files = sorted(demos_dir.glob("*.json"))
        if not files:
            raise SystemExit(f"没有 replay trace：{demos_dir}")
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            print("\n" + "#" * 72)
            print(f"# {data.get('task_id', path.stem)} | {data.get('q', '')}")
            print("#" * 72)
            for step in data.get("steps", []):
                print(f"[{step['n']}] {step['action']} "
                      f"{json.dumps(step.get('action_input', {}), ensure_ascii=False)[:160]}")
                print(f"    -> {str(step.get('observation', ''))[:400]}")
            print(f"\nanswerable={data.get('answerable')} "
                  f"citations={data.get('citations')}")
            print(data.get("answer", ""))
            print(f"steps={len(data.get('steps', []))} "
                  f"latency={data.get('latency_s')}s")
        print("\n这是 replay 模式，不需要 API key；加 --live 可跑真实模型。")
        return 0

    settings = Settings.from_env()
    runtime = _runtime(settings)
    try:
        for kb, query in DEMO_QUERIES:
            print("\n" + "#" * 72)
            print(f"# LIVE | {query}")
            print("#" * 72)
            result = runtime.run(query, kb, max_steps=settings.max_steps,
                                 trace_id="demo-live")
            _print_result(result, show_trace=True)
    finally:
        runtime.close()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "agentic_rag.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-rag",
        description="Agentic RAG: bounded ReAct agent over RAG + tools",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="ask one question")
    ask.add_argument("--q", required=True)
    ask.add_argument("--kb", default=DEFAULT_KB)
    ask.add_argument("--mode", choices=["agent", "rag"], default="agent")
    ask.add_argument("--max-steps", type=int, default=6)
    ask.add_argument("--show-trace", action="store_true")
    ask.add_argument("--trace-id", default=None)
    ask.set_defaults(func=cmd_ask)

    ev = sub.add_parser("eval", help="run the evaluation suite")
    ev.add_argument("--tasks", default="data/tasks.jsonl")
    ev.add_argument("--mode", choices=["agent", "rag", "both"], default="both")
    ev.add_argument("--runs", type=int, default=1)
    ev.add_argument("--only", default=None)
    ev.add_argument("--limit", type=int, default=None)
    ev.add_argument("--out", default="eval/report.json")
    ev.add_argument("--trace-dir", default="runs")
    ev.add_argument("--quiet", action="store_true")
    ev.add_argument("--delay", type=float, default=0.0,
                    help="sleep between runs; use for provider TPM limits")
    ev.set_defaults(func=cmd_eval)

    demo = sub.add_parser("demo", help="replay demo traces, or run live")
    demo.add_argument("--live", action="store_true")
    demo.add_argument("--data-dir", default="data")
    demo.set_defaults(func=cmd_demo)

    serve = sub.add_parser("serve", help="run the FastAPI service")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.add_argument("--log-level", default="info")
    serve.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
