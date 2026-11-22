# Security

## Reporting

Please open a private security advisory on GitHub rather than a public issue for
vulnerabilities. Include a minimal reproduction and the affected version.

## What this repository does

- API-key authentication on all `/v1/*` endpoints;
- constant-time comparison, fail-closed when `API_KEYS` is empty;
- per-key in-process rate limiting;
- read-only tools (`search_kb`, `lookup_ticket`, `calculator`);
- calculator uses an AST whitelist, never `eval`;
- no secrets committed; `.env` is gitignored;
- request IDs and generic error responses.

## Known limitations

- **Prompt injection**: documents and tickets are untrusted input. The agent treats
  them as data in `<context>`/Observation, but there is no content sanitizer or
  injection classifier. A poisoned document could steer a read-only tool call. Do not
  add write tools without an approval flow.
- **No per-document ACL**: any caller with a valid API key can query every KB.
- **No multi-tenancy**: a single process serves one deployment.
- **In-memory rate limit**: per process; add Redis/API gateway for replicas.
- **Provider trust**: prompts and retrieved text are sent to the configured LLM
  provider. Do not use sensitive data without a data-processing agreement.
- **Mock data**: tickets and DRAM documents are illustrative, not production records.

## Deployment checklist

- [ ] Rotate `API_KEYS`; never use the `dev-key-change-me` example.
- [ ] Keep `.env` out of images and logs.
- [ ] Run behind TLS and a reverse proxy.
- [ ] Restrict `/docs` in production if not needed.
- [ ] Add Redis/APM for multi-replica rate limiting and metrics.
- [ ] Add document-level ACL before retrieval if the corpus is sensitive.
- [ ] Add a human approval step before any write action.
