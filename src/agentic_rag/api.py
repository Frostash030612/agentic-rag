# -*- coding: utf-8 -*-
"""FastAPI production shell.

Endpoints:
  GET  /healthz              liveness (no auth)
  GET  /readyz               readiness: data + LLM + API keys
  GET  /v1/tools             tool catalog (auth)
  POST /v1/ask               run the agent (auth + rate limit)
  GET  /v1/traces/{id}       replay a trace (auth)
  GET  /v1/metrics           process metrics (auth)

Auth: X-API-Key header. If API_KEYS is empty the protected endpoints return
503 instead of silently allowing anonymous access.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .auth import verify_api_key
from .config import Settings
from .loop import RunResult
from .runtime import Runtime
from .schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    MetricsResponse,
    ReadyResponse,
    ToolInfo,
)

logger = logging.getLogger("agentic_rag.api")
AgentRunner = Callable[[str, str, int, str], RunResult]
TRACE_RE = re.compile(r"^[a-f0-9]{16,64}$")


def create_app(settings: Settings | None = None,
               agent_runner: AgentRunner | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    runtime = Runtime(settings)
    runner: AgentRunner = agent_runner or runtime.run

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "agentic-rag started env=%s model=%s kbs=%s",
            settings.environment, settings.llm_model, settings.kb_ids(),
        )
        yield
        runtime.close()

    app = FastAPI(
        title="Agentic RAG",
        version="0.1.0",
        description=(
            "A bounded ReAct agent over RAG + tools, with traces and "
            "deterministic evaluation."
        ),
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
    )
    app.state.runtime = runtime
    app.state.runner = runner

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001
            logger.exception("unhandled request error id=%s", request_id)
            raise
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(
            round((time.perf_counter() - started) * 1000, 2)
        )
        return response

    def require_api_key(
        request: Request,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> str:
        keys = runtime.settings.api_keys
        if not keys and runtime.settings.allow_anonymous:
            return "anonymous"
        if not keys:
            raise HTTPException(
                status_code=503,
                detail="API_KEYS is not configured; refusing to serve /v1 endpoints",
            )
        if not verify_api_key(x_api_key, keys):
            raise HTTPException(
                status_code=401,
                detail="invalid or missing X-API-Key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        allowed, retry_after = runtime.limiter.allow(x_api_key or "")
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )
        return x_api_key or ""

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": "agentic-rag",
            "version": "0.1.0",
            "docs": "/docs" if settings.docs_enabled else None,
            "health": "/healthz",
        }

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz():
        return HealthResponse(status="ok")

    @app.get("/readyz", response_model=ReadyResponse)
    async def readyz():
        ready, details = runtime.ready()
        return ReadyResponse(
            status="ok" if ready else "degraded",
            kbs=runtime.settings.kb_ids(),
            api_keys_configured=bool(runtime.settings.api_keys),
            details=details,
        )

    @app.get("/v1/tools", response_model=list[ToolInfo])
    async def list_tools(_key: str = Depends(require_api_key)):
        return [ToolInfo(**tool) for tool in runtime.tools.specs()]

    @app.post("/v1/ask", response_model=AskResponse)
    async def ask(
        payload: AskRequest,
        request: Request,
        _key: str = Depends(require_api_key),
    ):
        if payload.kb not in runtime.settings.kb_ids():
            raise HTTPException(
                status_code=400,
                detail=f"unknown kb {payload.kb!r}; available: {runtime.settings.kb_ids()}",
            )
        if runtime.llm is None and agent_runner is None:
            raise HTTPException(
                status_code=503,
                detail=runtime.llm_error or "LLM is not configured",
            )
        trace_id = uuid.uuid4().hex
        try:
            result = await run_in_threadpool(
                runner, payload.q, payload.kb, payload.max_steps, trace_id
            )
        except Exception as exc:  # noqa: BLE001
            runtime.metrics.record(0.0, error=True)
            logger.exception(
                "agent execution failed request_id=%s", request.state.request_id
            )
            raise HTTPException(
                status_code=502,
                detail=f"agent execution failed: {type(exc).__name__}",
            ) from exc
        runtime.metrics.record(result.latency_s, error=bool(result.error))
        if result.error and not result.answer:
            raise HTTPException(status_code=502, detail=result.error)
        return AskResponse(
            trace_id=trace_id,
            answerable=result.answerable,
            answer=result.answer,
            citations=result.citations,
            missing=result.missing,
            steps=len(result.steps),
            tools=result.called_tools,
            latency_s=round(result.latency_s, 3),
            model=runtime.settings.llm_model,
        )

    @app.get("/v1/traces/{trace_id}")
    async def get_trace(
        trace_id: str,
        _key: str = Depends(require_api_key),
    ):
        if not TRACE_RE.match(trace_id):
            raise HTTPException(status_code=400, detail="invalid trace id")
        path = runtime.trace_path(trace_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="trace not found")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/v1/metrics", response_model=MetricsResponse)
    async def metrics(_key: str = Depends(require_api_key)):
        return MetricsResponse(**runtime.metrics.snapshot())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # HTTPException is handled by FastAPI before this handler; this is the
        # last-resort path and must not leak stack traces or secrets.
        logger.exception("unhandled error request_id=%s", request.state.request_id)
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error",
                     "request_id": getattr(request.state, "request_id", "")},
        )

    return app


app = create_app()
