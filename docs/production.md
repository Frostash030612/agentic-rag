# Production notes

This repository is a **production-shaped reference**, not a turnkey SaaS. The goal is to
make the operational concerns explicit and testable.

## Configuration

All configuration is environment-driven; `.env` is ignored by git.

| Variable | Default | Meaning |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.siliconflow.cn/v1` | OpenAI-compatible base URL |
| `LLM_API_KEY` | empty | chat + embedding key |
| `LLM_MODEL` | `Qwen/Qwen3-8B` | chat model |
| `EMB_MODEL` | `BAAI/bge-m3` | must match the bundled 1024-d index |
| `API_KEYS` | empty | comma-separated client keys |
| `RATE_LIMIT_PER_MINUTE` | `60` | per-key, in-process |
| `MAX_STEPS` | `6` | global default; tasks may override |
| `AGENTIC_RAG_DATA_DIR` | `./data` | data root |
| `RUNS_DIR` | `./runs` | trace root |
| `DOCS_ENABLED` | `true` | `/docs` and `/redoc` |
| `ALLOW_ANONYMOUS` | `false` | never enable in production |

## Authentication

- `API_KEYS` is a comma-separated allowlist.
- Comparison is constant-time (`secrets.compare_digest`).
- Empty `API_KEYS` makes `/v1/*` fail closed with **503**.
- Keys are not logged; request logs use request IDs.

Key rotation: append a new key, deploy, migrate clients, remove the old key. No restart
is needed if your platform reloads env; otherwise rolling restart.

## Rate limiting

`InMemoryRateLimiter` is a sliding window per key. It is process-local and intentionally
minimal:

- fine for a single container or local demo;
- not sufficient for multiple replicas (each replica has its own window);
- replace with Redis, Envoy, NGINX, or an API gateway for real traffic.

## Observability

- `X-Request-ID` is assigned/echoed on every response.
- `X-Response-Time-Ms` is added by middleware.
- `/v1/metrics` returns counters, average latency, P95, and uptime.
- Traces under `runs/agent/<trace_id>/run-1.json` contain per-step action, args,
  observation, latency, and error flags.
- Logs include request IDs; upstream errors are logged without API keys.

For production, ship traces/metrics to OpenTelemetry, Prometheus, or your APM. The trace
schema is deliberately plain JSON so it can be replayed offline.

## Docker

```bash
docker build -t agentic-rag .
docker run --rm -p 8000:8000 --env-file .env \
  -v "$PWD/runs:/app/runs" agentic-rag
```

The image:

- uses `python:3.12-slim`;
- installs the package, not a dev environment;
- runs as a non-root user;
- exposes `/healthz` as a Docker healthcheck;
- never copies `.env`.

## CI

`.github/workflows/ci.yml`:

1. matrix Python 3.11/3.12;
2. `pip install -e ".[dev]"`;
3. `ruff check src tests`;
4. `pytest --cov`;
5. Docker build;
6. start container with `API_KEYS=test-key`, poll `/healthz`, then remove it.

Tests use a fake LLM/runner, so CI does **not** need an API key.

## Security checklist

- [x] API key auth on all `/v1/*` endpoints;
- [x] constant-time key comparison;
- [x] fail closed when keys are missing;
- [x] rate limiting;
- [x] no secrets in image or repo;
- [x] read-only tools, no shell/exec in calculator;
- [x] request IDs and no stack traces in responses;
- [ ] per-document ACL (roadmap);
- [ ] human approval for write tools (roadmap);
- [ ] prompt-injection classifier / content sanitizer (roadmap);
- [ ] multi-tenant isolation (roadmap).

## Scaling path

1. Move rate limiting and metrics to Redis/APM.
2. Run multiple replicas behind a gateway; make traces write to object storage.
3. Replace the local `vectors.npy` retriever with a vector DB (pgvector/FAISS/Milvus)
   when the corpus exceeds ~10^5 chunks.
4. Move agent execution to a queue for long-running tasks; add checkpoint/resume.
5. Add per-KB ACL filters before retrieval, not after generation.
6. Add write tools only with an approval flow, idempotency keys, and audit logs.

## Failure modes

| Failure | Current behavior | Next step |
| --- | --- | --- |
| LLM 429/timeout | retries with backoff, then 502 | circuit breaker, provider fallback |
| invalid JSON | observation → retry → max_steps fallback | JSON mode + final fallback |
| tool error | observation, model decides | typed retry policy |
| no API key | `/v1/*` 503 | health/ready shows degraded |
| process restart | in-memory limiter/metrics reset | Redis/APM |
| large corpus | local matrix search | vector DB + sharding |
