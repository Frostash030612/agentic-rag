"""Pydantic request/response models for the HTTP API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    q: str = Field(min_length=1, max_length=2000, description="用户问题")
    kb: str = Field(default="dram", description="知识库 id")
    max_steps: int = Field(default=6, ge=1, le=8)
    include_trace: bool = Field(default=True, description="是否写入 trace")


class AskResponse(BaseModel):
    trace_id: str
    answerable: bool
    answer: str
    citations: list[str] = Field(default_factory=list)
    missing: str = ""
    steps: int
    tools: list[str] = Field(default_factory=list)
    latency_s: float
    model: str


class ToolInfo(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    service: str = "agentic-rag"
    version: str = "0.1.0"


class ReadyResponse(BaseModel):
    status: str
    kbs: list[str]
    api_keys_configured: bool
    details: dict[str, Any] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    requests_total: int
    errors_total: int
    avg_latency_s: float
    p95_latency_s: float
    uptime_s: float
