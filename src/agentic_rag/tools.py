# -*- coding: utf-8 -*-
"""Tool registry and three read-only tools.

Application-engineering rules:
  - tools are pure functions: JSON in, string out;
  - every tool has an explicit error contract;
  - no write tools in the demo, so a prompt injection cannot mutate state.
"""
from __future__ import annotations

import ast
import json
import operator
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .retrieval import RetrieverRegistry


class ToolError(ValueError):
    pass


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable[..., str]

    def public(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_node(node: ast.AST):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, (ast.Div, ast.Mod)) and right == 0:
            raise ToolError("除数不能为 0")
        if isinstance(node.op, ast.Pow) and abs(right) > 10:
            raise ToolError("指数绝对值不能超过 10")
        return _BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval_node(node.operand))
    raise ToolError("只支持数字和 + - * / % ** 运算")


def calculator(expression: str) -> str:
    expr = str(expression or "").strip()
    if not expr:
        raise ToolError("expression 不能为空")
    if len(expr) > 200:
        raise ToolError("表达式过长")
    try:
        tree = ast.parse(expr, mode="eval")
        value = _eval_node(tree)
    except SyntaxError as exc:
        raise ToolError(f"表达式语法错误：{exc.msg}") from exc
    if isinstance(value, float):
        value = round(value, 6)
    return json.dumps({"expression": expr, "result": value}, ensure_ascii=False)


class ToolRegistry:
    def __init__(self, settings: Settings, retrievers: RetrieverRegistry):
        self.settings = settings
        self.retrievers = retrievers
        self.tickets_path = Path(settings.data_dir) / "tickets.json"
        kb_ids = settings.kb_ids()
        self._tools: dict[str, Tool] = {}
        self._register(Tool(
            name="search_kb",
            description=(
                "检索本地知识库，返回带 doc/cid 的来源片段。"
                "适用于事实、流程、定义类问题。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索查询"},
                    "kb": {"type": "string", "enum": kb_ids,
                           "description": "知识库，默认使用任务指定的库"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["query"],
            },
            fn=self.search_kb,
        ))
        self._register(Tool(
            name="lookup_ticket",
            description=(
                "按工单号查状态、优先级、关联报警与备注。只读 mock 数据。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string",
                                  "description": "如 T-1001"},
                },
                "required": ["ticket_id"],
            },
            fn=self.lookup_ticket,
        ))
        self._register(Tool(
            name="calculator",
            description="计算四则运算表达式，如 24*0.925、45*24/60。",
            input_schema={
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
            fn=calculator,
        ))

    def _register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"未知工具 {name!r}，可用：{', '.join(self.names)}")
        return self._tools[name]

    def specs(self) -> list[dict]:
        return [tool.public() for tool in self._tools.values()]

    def catalog_text(self) -> str:
        lines = []
        for tool in self._tools.values():
            props = ", ".join(tool.input_schema.get("properties", {}))
            lines.append(f"- {tool.name}({props}): {tool.description}")
        return "\n".join(lines)

    def call(self, name: str, args: dict) -> str:
        if not isinstance(args, dict):
            raise ToolError("action_input 必须是 JSON 对象")
        tool = self.get(name)
        schema = tool.input_schema
        for key in schema.get("required", []):
            if key not in args:
                raise ToolError(f"{name} 缺少参数 {key}")
        for key, rule in schema.get("properties", {}).items():
            if key not in args:
                continue
            value = args[key]
            if rule.get("type") == "string" and not isinstance(value, str):
                raise ToolError(f"{name}.{key} 应为字符串")
            if rule.get("type") == "integer" and not isinstance(value, int):
                raise ToolError(f"{name}.{key} 应为整数")
            if "enum" in rule and value not in rule["enum"]:
                raise ToolError(f"{name}.{key} 必须是 {rule['enum']}")
        return tool.fn(**args)

    def search_kb(self, query: str, kb: str | None = None,
                  top_k: int = 3) -> str:
        if not isinstance(query, str) or not query.strip():
            raise ToolError("query 不能为空")
        kb = kb or (self.settings.kb_ids()[0] if self.settings.kb_ids() else "dram")
        top_k = max(1, min(int(top_k), 5))
        retriever = self.retrievers.get(kb)
        hits = retriever.search(
            query.strip(), top_k=top_k, mode="hybrid",
            rerank="max", rerank_pool=40, alpha=0.7,
        )
        if not hits:
            return json.dumps({"kb": kb, "query": query, "hits": []},
                              ensure_ascii=False)
        lines = [f"知识库 {kb} 的检索结果（共 {len(hits)} 条）："]
        for rank, (idx, score) in enumerate(hits, start=1):
            chunk = retriever.chunks[idx]
            text = " ".join(chunk["text"].split())
            if len(text) > 700:
                text = text[:700] + " …"
            lines.append(
                f"[{rank}] {chunk['doc']} / {chunk['cid']} "
                f"(score={float(score):.3f})\n{text}"
            )
        return "\n\n".join(lines)

    def lookup_ticket(self, ticket_id: str) -> str:
        tid = str(ticket_id or "").strip().upper()
        if not tid:
            raise ToolError("ticket_id 不能为空")
        if not self.tickets_path.exists():
            raise ToolError(f"tickets file not found: {self.tickets_path}")
        rows = json.loads(self.tickets_path.read_text(encoding="utf-8"))
        for row in rows:
            if row["id"].upper() == tid:
                return json.dumps({"found": True, **row}, ensure_ascii=False)
        return json.dumps(
            {"found": False, "ticket_id": tid,
             "message": f"未找到工单 {tid}"},
            ensure_ascii=False,
        )
