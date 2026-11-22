# HTTP API

Base URL: `http://localhost:8000` (Docker or `python -m agentic_rag serve`).

OpenAPI UI: `/docs` (disable with `DOCS_ENABLED=false`).

## Authentication

Every `/v1/*` request needs:

```http
X-API-Key: <one of API_KEYS>
```

`API_KEYS` is a comma-separated list. If it is empty, protected endpoints return
**503** instead of silently allowing anonymous access.

```bash
curl -s localhost:8000/v1/tools \
  -H "X-API-Key: dev-key-change-me"
```

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/healthz` | no | liveness |
| GET | `/readyz` | no | data / LLM / API key readiness |
| GET | `/v1/tools` | yes | tool catalog with JSON Schema |
| POST | `/v1/ask` | yes | run the agent |
| GET | `/v1/traces/{trace_id}` | yes | replay a trace |
| GET | `/v1/metrics` | yes | process counters and latency |

### POST /v1/ask

```json
{
  "q": "T-1001 涉及的报警应该怎么处理？",
  "kb": "dram",
  "max_steps": 6,
  "include_trace": true
}
```

Response:

```json
{
  "trace_id": "9f6c...",
  "answerable": true,
  "answer": "处理 ALM-1042 的步骤如下：……",
  "citations": ["02_alarm_manual.md#0", "T-1001"],
  "missing": "",
  "steps": 3,
  "tools": ["lookup_ticket", "search_kb"],
  "latency_s": 12.4,
  "model": "Qwen/Qwen3-8B"
}
```

`include_trace` is accepted for forward compatibility; traces are always written so
the request can be replayed. Use `GET /v1/traces/{trace_id}` to retrieve it.

### GET /v1/traces/{trace_id}

Trace ids are 32 hex characters. The endpoint returns the JSON persisted under
`runs/agent/<trace_id>/run-1.json`.

### GET /v1/metrics

Process-local counters:

```json
{
  "requests_total": 12,
  "errors_total": 1,
  "avg_latency_s": 7.8,
  "p95_latency_s": 12.1,
  "uptime_s": 3600.0
}
```

For multi-replica deployments, export metrics to Prometheus/OpenTelemetry instead.

## Error contract

| Status | Meaning |
| --- | --- |
| 400 | unknown `kb` or invalid trace id |
| 401 | missing/invalid `X-API-Key` |
| 422 | request schema validation failed |
| 429 | per-key rate limit exceeded; see `Retry-After` |
| 502 | upstream LLM/agent failure |
| 503 | `API_KEYS` missing, or LLM not configured |

All responses include `X-Request-ID`; error responses include the same id so logs can
be correlated.

## Rate limiting

In-memory token window per API key, default 60 requests/minute:

```dotenv
RATE_LIMIT_PER_MINUTE=60
```

The limiter is process-local. For multiple replicas, use Redis or an API gateway.

## Examples

```bash
# health
curl -s localhost:8000/healthz

# tool catalog
curl -s localhost:8000/v1/tools -H "X-API-Key: dev-key-change-me"

# ask
curl -s -X POST localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-change-me" \
  -d '{"q":"T-1001 涉及的报警应该怎么处理？","kb":"dram"}'

# replay
curl -s localhost:8000/v1/traces/<trace_id> \
  -H "X-API-Key: dev-key-change-me"
```
