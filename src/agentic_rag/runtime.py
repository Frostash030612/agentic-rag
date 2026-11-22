"""Process-level wiring shared by the CLI and the FastAPI app."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .auth import InMemoryRateLimiter
from .config import Settings
from .embeddings import EmbeddingClient, EmbeddingError
from .llm import LLMClient, LLMError
from .loop import RunResult, run_agent
from .retrieval import RetrieverRegistry
from .tools import ToolRegistry


@dataclass
class Metrics:
    requests_total: int = 0
    errors_total: int = 0
    latencies: list[float] = field(default_factory=list)
    started_at: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, latency_s: float, error: bool = False) -> None:
        with self._lock:
            self.requests_total += 1
            self.latencies.append(latency_s)
            if error:
                self.errors_total += 1

    def snapshot(self) -> dict:
        with self._lock:
            latencies = sorted(self.latencies)
            p95 = (
                latencies[min(len(latencies) - 1,
                              int(round(0.95 * (len(latencies) - 1))))]
                if latencies else 0.0
            )
            return {
                "requests_total": self.requests_total,
                "errors_total": self.errors_total,
                "avg_latency_s": round(
                    sum(latencies) / len(latencies), 3
                ) if latencies else 0.0,
                "p95_latency_s": round(p95, 3),
                "uptime_s": round(time.monotonic() - self.started_at, 1),
            }


class Runtime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm: LLMClient | None = None
        self.embedder: EmbeddingClient | None = None
        self.llm_error: str = ""
        if settings.llm_api_key:
            try:
                self.llm = LLMClient(settings)
                self.embedder = EmbeddingClient(settings)
            except (LLMError, EmbeddingError) as exc:
                self.llm_error = str(exc)
        else:
            self.llm_error = "LLM_API_KEY is not configured"

        self.retrievers = RetrieverRegistry(settings, self.embedder)
        self.tools = ToolRegistry(settings, self.retrievers)
        self.limiter = InMemoryRateLimiter(settings.rate_limit_per_minute)
        self.metrics = Metrics()

    def ready(self) -> tuple[bool, dict]:
        problems = self.settings.validate()
        if self.llm is None:
            problems.append(self.llm_error or "LLM is not configured")
        return not problems, {"problems": problems,
                              "kbs": self.settings.kb_ids()}

    def run(self, q: str, kb: str, max_steps: int, trace_id: str) -> RunResult:
        if self.llm is None:
            raise RuntimeError(self.llm_error or "LLM is not configured")
        return run_agent(
            q, kb, max_steps=max_steps, llm=self.llm.chat, tools=self.tools,
            trace_dir=self.settings.runs_dir, task_id=trace_id,
            run_id="1", quiet=True,
        )

    def trace_path(self, trace_id: str) -> Path:
        return self.settings.runs_dir / "agent" / trace_id / "run-1.json"

    def close(self) -> None:
        if self.llm:
            self.llm.close()
        if self.embedder:
            self.embedder.close()
